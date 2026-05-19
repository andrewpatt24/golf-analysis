from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from golf_analysis.models import IngestPayload, RangeShot, RoundHole, RoundTrackPoint
from golf_analysis.serialization import dumps_json


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            connector_id TEXT NOT NULL,
            source_path TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            file_size_bytes INTEGER,
            UNIQUE(content_sha256)
        );

        CREATE TABLE IF NOT EXISTS range_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
            title TEXT,
            started_at TEXT,
            ended_at TEXT,
            venue TEXT,
            notes TEXT,
            practice_kind TEXT,
            list_source_kind TEXT,
            raw_headers_json TEXT
        );

        CREATE TABLE IF NOT EXISTS range_shots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES range_sessions(id) ON DELETE CASCADE,
            shot_index INTEGER,
            club TEXT,
            ball_speed_mph REAL,
            club_speed_mph REAL,
            smash_factor REAL,
            launch_angle_deg REAL,
            launch_direction_deg REAL,
            spin_rpm REAL,
            spin_axis_deg REAL,
            carry_yards REAL,
            total_yards REAL,
            apex_yards REAL,
            descent_angle_deg REAL,
            offline_yards REAL,
            attack_angle_deg REAL,
            club_path_deg REAL,
            face_to_path_deg REAL,
            extra_json TEXT
        );

        CREATE TABLE IF NOT EXISTS golf_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
            title TEXT,
            course_name TEXT,
            started_at TEXT,
            ended_at TEXT,
            total_strokes INTEGER,
            total_putts INTEGER,
            score_relative_to_par INTEGER,
            extra_json TEXT
        );

        CREATE TABLE IF NOT EXISTS round_holes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL REFERENCES golf_rounds(id) ON DELETE CASCADE,
            hole_number INTEGER,
            par INTEGER,
            stroke_index INTEGER,
            score INTEGER,
            putts INTEGER,
            fairway_hit INTEGER,
            green_in_regulation INTEGER,
            penalty_strokes INTEGER,
            distance_meters REAL,
            duration_s REAL,
            extra_json TEXT
        );

        CREATE TABLE IF NOT EXISTS round_track_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL REFERENCES golf_rounds(id) ON DELETE CASCADE,
            seq INTEGER NOT NULL,
            time TEXT,
            lat REAL,
            lon REAL,
            altitude_m REAL,
            distance_m REAL,
            heart_rate INTEGER,
            extra_json TEXT,
            UNIQUE(round_id, seq)
        );

        CREATE INDEX IF NOT EXISTS idx_range_sessions_import ON range_sessions(import_id);
        CREATE INDEX IF NOT EXISTS idx_range_shots_session ON range_shots(session_id);
        CREATE INDEX IF NOT EXISTS idx_rounds_import ON golf_rounds(import_id);
        CREATE INDEX IF NOT EXISTS idx_holes_round ON round_holes(round_id);
        CREATE INDEX IF NOT EXISTS idx_track_round ON round_track_points(round_id);
        """
    )
    _migrate_range_sessions_practice_kind(conn)
    _migrate_range_sessions_list_source_kind(conn)
    conn.commit()


def _migrate_range_sessions_practice_kind(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(range_sessions)").fetchall()}
    if "practice_kind" not in cols:
        conn.execute("ALTER TABLE range_sessions ADD COLUMN practice_kind TEXT")


def _migrate_range_sessions_list_source_kind(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(range_sessions)").fetchall()}
    if "list_source_kind" not in cols:
        conn.execute("ALTER TABLE range_sessions ADD COLUMN list_source_kind TEXT")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _insert_range_shots(cur: sqlite3.Cursor, session_id: int, shots: list[RangeShot]) -> None:
    rows = []
    for s in shots:
        rows.append(
            (
                session_id,
                s.shot_index,
                s.club,
                s.ball_speed_mph,
                s.club_speed_mph,
                s.smash_factor,
                s.launch_angle_deg,
                s.launch_direction_deg,
                s.spin_rpm,
                s.spin_axis_deg,
                s.carry_yards,
                s.total_yards,
                s.apex_yards,
                s.descent_angle_deg,
                s.offline_yards,
                s.attack_angle_deg,
                s.club_path_deg,
                s.face_to_path_deg,
                dumps_json(s.extra) if s.extra else None,
            )
        )
    cur.executemany(
        """
        INSERT INTO range_shots (
            session_id, shot_index, club, ball_speed_mph, club_speed_mph, smash_factor,
            launch_angle_deg, launch_direction_deg, spin_rpm, spin_axis_deg,
            carry_yards, total_yards, apex_yards, descent_angle_deg, offline_yards,
            attack_angle_deg, club_path_deg, face_to_path_deg, extra_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        rows,
    )


def _insert_round_holes(cur: sqlite3.Cursor, round_id: int, holes: list[RoundHole]) -> None:
    rows = []
    for h in holes:
        rows.append(
            (
                round_id,
                h.hole_number,
                h.par,
                h.stroke_index,
                h.score,
                h.putts,
                1 if h.fairway_hit is True else (0 if h.fairway_hit is False else None),
                1 if h.green_in_regulation is True else (0 if h.green_in_regulation is False else None),
                h.penalty_strokes,
                h.distance_meters,
                h.duration_s,
                dumps_json(h.extra) if h.extra else None,
            )
        )
    if rows:
        cur.executemany(
            """
            INSERT INTO round_holes (
                round_id, hole_number, par, stroke_index, score, putts,
                fairway_hit, green_in_regulation, penalty_strokes,
                distance_meters, duration_s, extra_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )


def _insert_track(cur: sqlite3.Cursor, round_id: int, track: list[RoundTrackPoint]) -> None:
    rows = []
    for seq, p in enumerate(track):
        rows.append(
            (
                round_id,
                seq,
                _iso(p.time),
                p.lat,
                p.lon,
                p.altitude_m,
                p.distance_m,
                p.heart_rate,
                dumps_json(p.extra) if p.extra else None,
            )
        )
    if rows:
        cur.executemany(
            """
            INSERT INTO round_track_points (
                round_id, seq, time, lat, lon, altitude_m, distance_m, heart_rate, extra_json
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )


def insert_payload(
    conn: sqlite3.Connection,
    *,
    connector_id: str,
    source_path: Path,
    content_sha256: str,
    file_size_bytes: int,
    payload: IngestPayload,
) -> tuple[int, int, int]:
    """
    Persist payload rows. Caller must verify import row does not already exist for this hash.
    Returns (import_id, range_sessions_written, rounds_written).
    """

    cur = conn.cursor()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cur.execute(
            """
            INSERT INTO imports (connector_id, source_path, content_sha256, imported_at, file_size_bytes)
            VALUES (?,?,?,?,?)
            """,
            (connector_id, str(source_path.resolve()), content_sha256, now, file_size_bytes),
        )
        import_id = int(cur.lastrowid)
        rs_count = 0
        rr_count = 0

        for sess in payload.range_sessions:
            cur.execute(
                """
                INSERT INTO range_sessions (
                    import_id, title, started_at, ended_at, venue, notes,
                    practice_kind, list_source_kind, raw_headers_json
                )
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    import_id,
                    sess.title,
                    _iso(sess.started_at),
                    _iso(sess.ended_at),
                    sess.venue,
                    sess.notes,
                    sess.practice_kind,
                    sess.list_source_kind,
                    dumps_json(sess.raw_headers) if sess.raw_headers else None,
                ),
            )
            sid = int(cur.lastrowid)
            _insert_range_shots(cur, sid, sess.shots)
            rs_count += 1

        for rnd in payload.rounds:
            cur.execute(
                """
                INSERT INTO golf_rounds (
                    import_id, title, course_name, started_at, ended_at,
                    total_strokes, total_putts, score_relative_to_par, extra_json
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    import_id,
                    rnd.title,
                    rnd.course_name,
                    _iso(rnd.started_at),
                    _iso(rnd.ended_at),
                    rnd.total_strokes,
                    rnd.total_putts,
                    rnd.score_relative_to_par,
                    dumps_json(rnd.extra) if rnd.extra else None,
                ),
            )
            rid = int(cur.lastrowid)
            _insert_round_holes(cur, rid, rnd.holes)
            _insert_track(cur, rid, rnd.track)
            rr_count += 1

        conn.commit()
        return import_id, rs_count, rr_count
    except Exception:
        conn.rollback()
        raise


@dataclass
class LibraryStats:
    imports: int
    range_sessions: int
    range_shots: int
    golf_rounds: int
    round_holes: int
    track_points: int


def library_stats(conn: sqlite3.Connection) -> LibraryStats:
    cur = conn.cursor()
    def c(sql: str) -> int:
        row = cur.execute(sql).fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    return LibraryStats(
        imports=c("SELECT COUNT(*) FROM imports"),
        range_sessions=c("SELECT COUNT(*) FROM range_sessions"),
        range_shots=c("SELECT COUNT(*) FROM range_shots"),
        golf_rounds=c("SELECT COUNT(*) FROM golf_rounds"),
        round_holes=c("SELECT COUNT(*) FROM round_holes"),
        track_points=c("SELECT COUNT(*) FROM round_track_points"),
    )


def existing_import_id(conn: sqlite3.Connection, content_sha256: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM imports WHERE content_sha256 = ?",
        (content_sha256,),
    ).fetchone()
    return int(row[0]) if row else None
