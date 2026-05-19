"""
Inspect Garmin (or any) FIT exports: message type histograms and field samples.

Use this to discover where per-hole scores, putts, or other golf metrics live
before extending the parser in ``garmin_fit.py``.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import Path
from typing import Any, TextIO

from fitparse import FitFile
from fitparse.utils import FitParseError

from golf_analysis.connectors.garmin_fit import iter_fit_bytes_from_path
from golf_analysis.serialization import json_safe


def dump_fit_bytes_to_jsonable(
    data: bytes,
    *,
    label: str,
    omit_records: bool = False,
    record_every: int = 1,
) -> dict[str, Any]:
    """
    Decode a FIT payload to a JSON-serializable structure: every data message
    fitparse exposes via ``get_values()``, not only sport/session/lap/record.

    ``record`` rows can dominate file size; use ``omit_records`` or
    ``record_every`` to thin them. When ``record_every > 1``, the last record is
    always included if it was not already emitted.
    """

    out: dict[str, Any] = {
        "label": label,
        "fit_error": None,
        "record_stats": {
            "total": 0,
            "included": 0,
            "omit_records": omit_records,
            "record_every": max(1, record_every),
        },
        "messages": [],
    }
    try:
        fit = FitFile(BytesIO(data))
    except FitParseError as e:
        out["fit_error"] = str(e)
        return out

    messages: list[dict[str, Any]] = out["messages"]
    stats = out["record_stats"]
    revery = max(1, record_every)
    record_total = 0
    record_included = 0
    last_record: dict[str, Any] | None = None
    last_record_index: int | None = None
    last_emitted_record_index: int | None = None

    def append_msg(seq: int, msg: Any, values: dict[str, Any] | None) -> None:
        try:
            mn = int(msg.mesg_num)
        except (TypeError, ValueError):
            mn = None
        messages.append(
            {
                "seq": seq,
                "mesg_num": mn,
                "name": str(msg.name),
                "values": json_safe(dict(values)) if values is not None else None,
            }
        )

    for seq, msg in enumerate(fit.messages):
        if not hasattr(msg, "get_values"):
            continue
        name = str(msg.name)
        vals = msg.get_values()

        if name == "record":
            record_total += 1
            if omit_records:
                continue
            if vals is None:
                vals = {}
            last_record_index = record_total
            last_record = {"seq": seq, "msg": msg, "values": dict(vals)}
            emit = revery == 1 or (record_total - 1) % revery == 0
            if emit:
                append_msg(seq, msg, dict(vals))
                record_included += 1
                last_emitted_record_index = record_total
            continue

        if vals is not None:
            append_msg(seq, msg, dict(vals))

    if (
        not omit_records
        and revery > 1
        and last_record is not None
        and last_record_index is not None
        and last_emitted_record_index != last_record_index
    ):
        lr = last_record
        append_msg(lr["seq"], lr["msg"], lr["values"])
        record_included += 1

    stats["total"] = record_total
    stats["included"] = record_included
    return out


def dump_path_to_json_stream(
    path: Path,
    *,
    out_stream: TextIO,
    omit_records: bool = False,
    record_every: int = 1,
    indent: int | None = None,
) -> None:
    """Write JSON for each ``.fit`` inside ``path`` (``.fit`` or ``.zip``)."""

    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in (".fit", ".zip"):
        raise ValueError(f"Expected .fit or .zip, got {path.suffix}")

    chunks = iter_fit_bytes_from_path(path)
    if not chunks:
        doc = {"path": str(path), "fit_error": "No .fit payload in archive", "payloads": []}
        json.dump(json_safe(doc), out_stream, indent=indent, ensure_ascii=False)
        out_stream.write("\n")
        return

    payloads: list[dict[str, Any]] = []
    for logical_name, data in chunks:
        label = f"{path.name} :: {logical_name}"
        payloads.append(dump_fit_bytes_to_jsonable(data, label=label, omit_records=omit_records, record_every=record_every))
    doc = {"path": str(path), "payloads": payloads}
    json.dump(json_safe(doc), out_stream, indent=indent, ensure_ascii=False)
    out_stream.write("\n")

# Garmin golf exports often use global message numbers that are **not** in the
# public FIT profile bundled with fitparse (nor in garmin_fit_sdk 21.x ``mesg_num``
# enums). Field **253** is still almost always ``timestamp`` (FIT convention).
_GOLF_VENDOR_MESG = frozenset({18, 19, 22, 79, 216, 288, 325, 326})


def _short_repr(val: Any, max_len: int) -> str:
    if val is None:
        return "None"
    try:
        s = json.dumps(json_safe(val), ensure_ascii=False)
    except (TypeError, ValueError):
        s = repr(val)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _collect_messages_by_mesg_num(data: bytes, mesg_nums: frozenset[int]) -> dict[int, list[dict[Any, Any]]]:
    rows: dict[int, list[dict[Any, Any]]] = defaultdict(list)
    try:
        fit = FitFile(BytesIO(data))
    except FitParseError:
        return {}
    for msg in fit.messages:
        if not hasattr(msg, "get_values"):
            continue
        try:
            mn = int(msg.mesg_num)
        except (TypeError, ValueError):
            continue
        if mn not in mesg_nums:
            continue
        vals = msg.get_values()
        if vals:
            rows[mn].append(dict(vals))
    return rows


def _write_golf_vendor_forensics(rows: dict[int, list[dict[Any, Any]]], out: TextIO) -> None:
    """
    When mesg 325 / 326 (vendor golf shot / hole payloads) are present, print
    compact statistics to help map ``unknown_*`` fields before official names exist.
    """

    r325 = rows.get(325) or []
    r326 = rows.get(326) or []
    if not r325 and not r326:
        return

    out.write("--- Golf vendor forensics (mesg 325 / 326 + related) ---\n")
    out.write(
        "FIT field 253 is conventionally ``timestamp``; fitparse names it ``unknown_253`` "
        "when the message type is outside the bundled profile.\n\n"
    )

    sess = (rows.get(18) or [{}])[0]
    lap = (rows.get(19) or [{}])[0]
    if sess or lap:
        out.write("Session / lap vendor fields (for cross-check):\n")
        for label, d in (("session", sess), ("lap", lap)):
            u196 = d.get("unknown_196")
            u178 = d.get("unknown_178")
            u155 = d.get("unknown_155")
            u145 = d.get("unknown_145")
            if any(x is not None for x in (u196, u178, u155, u145)):
                out.write(
                    f"  {label}: unknown_196={u196!r} unknown_178={u178!r} "
                    f"unknown_155={u155!r} unknown_145={u145!r}\n"
                )
        out.write("\n")

    hdr = (rows.get(79) or [{}])[0]
    if hdr:
        out.write("Mesg 79 (likely round / scorecard header) sample keys:\n")
        for k in ("unknown_0", "unknown_2", "unknown_6", "unknown_7", "unknown_253"):
            if k in hdr:
                out.write(f"  {k}: {_short_repr(hdr[k], 120)}\n")
        if len(r325) and hdr.get("unknown_6") == len(r325):
            out.write(
                f"  → unknown_6 ({hdr.get('unknown_6')}) equals mesg 325 row count ({len(r325)}).\n"
            )
        out.write("\n")

    if r325:
        out.write(f"Mesg 325 × {len(r325)} (candidate **per-shot** or rich lie rows)\n")
        holes = [r.get("unknown_2") for r in r325 if r.get("unknown_2") is not None]
        hole_counts = Counter(holes)
        out.write(f"  Distinct unknown_2 (candidate hole index): {len(hole_counts)} — {sorted(hole_counts)}\n")
        u1 = [r.get("unknown_1") for r in r325 if isinstance(r.get("unknown_1"), int)]
        if u1:
            out.write(f"  unknown_1 (candidate stroke index / club code): min={min(u1)} max={max(u1)}\n")
        u0 = [r.get("unknown_0") for r in r325 if isinstance(r.get("unknown_0"), int)]
        if u0:
            out.write(f"  unknown_0 (often distance-ish, device units): min={min(u0)} max={max(u0)}\n")
        by_hole: dict[Any, list[int]] = defaultdict(list)
        for r in r325:
            h = r.get("unknown_2")
            v1 = r.get("unknown_1")
            if h is not None and isinstance(v1, int):
                by_hole[h].append(v1)
        if by_hole:
            out.write("  Per unknown_2: row count, max(unknown_1) (rough shot count per hole):\n")
            for h in sorted(by_hole, key=lambda x: (isinstance(x, int), x)):
                xs = by_hole[h]
                out.write(f"    hole_key={h!r}: n={len(xs)} max_u1={max(xs)}\n")
        out.write("\n")

    if r326:
        out.write(f"Mesg 326 × {len(r326)} (candidate **putt / green / hazard** rows; often < 325)\n")
        u0c = Counter(r.get("unknown_0") for r in r326)
        out.write(f"  unknown_0 value counts (top 8): {u0c.most_common(8)}\n")
        holes326 = {r.get("unknown_253") for r in r326}
        out.write(f"  Distinct unknown_253 (timestamps): {len(holes326)}\n")
        out.write("\n")

    r216 = rows.get(216) or []
    if r216:
        out.write(f"Mesg 216 × {len(r216)} (often **time-in-zone** in SDK; here may carry golf indices)\n")
        for i, r in enumerate(r216[:2], 1):
            out.write(f"  sample {i}: {_short_repr(r, 400)}\n")
        out.write("\n")

    out.write(
        "Next step for exact semantics: compare with Connect hole-by-hole UI, "
        "or decode with a newer Garmin FIT profile when mesg 325/326 are documented.\n\n"
    )


def inspect_fit_bytes(
    data: bytes,
    *,
    label: str,
    out: TextIO,
    sample_per_type: int = 3,
    max_value_len: int = 200,
    record_sample_stride: int = 50,
) -> None:
    """
    Write a human-readable report: counts per (mesg_num, name), field unions,
    and a few sample ``get_values()`` payloads per type. ``record`` messages are
    summarized (count + first / stride / last) to avoid flooding output.
    """

    try:
        fit = FitFile(BytesIO(data))
    except FitParseError as e:
        out.write(f"=== {label} ===\nFitParseError: {e}\n\n")
        return

    counts: Counter[tuple[int, str]] = Counter()
    samples: dict[tuple[int, str], list[dict[Any, Any]]] = defaultdict(list)
    field_union: dict[tuple[int, str], set[str]] = defaultdict(set)
    record_field_keys: set[str] = set()

    record_count = 0
    first_record_vals: dict[Any, Any] | None = None
    mid_record_vals: dict[Any, Any] | None = None
    last_record_vals: dict[Any, Any] | None = None

    for msg in fit.messages:
        if not hasattr(msg, "get_values"):
            continue
        try:
            mesg_num = int(msg.mesg_num)
        except (TypeError, ValueError):
            mesg_num = -1
        name = str(msg.name)
        key = (mesg_num, name)
        counts[key] += 1
        vals = msg.get_values()
        if vals:
            for k in vals:
                field_union[key].add(str(k))
        if name == "record":
            record_count += 1
            if vals:
                record_field_keys.update(str(k) for k in vals)
            if record_count == 1 and vals:
                first_record_vals = dict(vals)
            if (
                record_sample_stride > 0
                and record_count == record_sample_stride
                and vals
                and mid_record_vals is None
            ):
                mid_record_vals = dict(vals)
            if vals:
                last_record_vals = dict(vals)
            continue
        if len(samples[key]) < sample_per_type and vals is not None:
            samples[key].append(dict(vals))

    total_msgs = sum(counts.values())
    out.write(f"=== {label} ===\n")
    out.write(f"Total data messages: {total_msgs}\n")
    out.write(f"Distinct (mesg_num, name) types: {len(counts)}\n\n")

    out.write(f"{'mesg#':>6}  {'name':<36}  {'count':>6}\n")
    out.write("-" * 56 + "\n")
    for (mn, nm), c in sorted(counts.items(), key=lambda x: (-x[1], x[0][0], x[0][1])):
        out.write(f"{mn:>6}  {nm:<36}  {c:>6}\n")
    out.write("\n")

    if record_count:
        out.write(f"--- message type: record × {record_count} ---\n")
        keys_sorted = sorted(record_field_keys)
        out.write(f"Union of field keys ({len(keys_sorted)}): {', '.join(keys_sorted[:50])}")
        if len(keys_sorted) > 50:
            out.write(f", … (+{len(keys_sorted) - 50} more)")
        out.write("\n")
        if first_record_vals:
            out.write("Sample: first record (subset of keys):\n")
            for k in sorted(first_record_vals, key=str)[:25]:
                out.write(f"  {k}: {_short_repr(first_record_vals[k], max_value_len)}\n")
            if len(first_record_vals) > 25:
                out.write(f"  … ({len(first_record_vals) - 25} more keys)\n")
        if mid_record_vals:
            out.write(f"Sample: record #{record_sample_stride} (subset):\n")
            for k in sorted(mid_record_vals, key=str)[:15]:
                out.write(f"  {k}: {_short_repr(mid_record_vals[k], max_value_len)}\n")
        if last_record_vals and record_count > 1:
            out.write("Sample: last record (subset):\n")
            for k in sorted(last_record_vals, key=str)[:15]:
                out.write(f"  {k}: {_short_repr(last_record_vals[k], max_value_len)}\n")
        out.write("\n")

    for (mn, nm), c in sorted(counts.items(), key=lambda x: (-x[1], x[0][0], x[0][1])):
        if nm == "record":
            continue
        out.write(f"--- {nm} (mesg_num={mn}) × {c} ---\n")
        keys = sorted(field_union[(mn, nm)])
        out.write(f"Field keys ({len(keys)}): {', '.join(keys)}\n")
        samps = samples.get((mn, nm), [])
        for i, svals in enumerate(samps, 1):
            out.write(f"Sample {i}/{len(samps)}:\n")
            for k in sorted(svals, key=str):
                out.write(f"  {k}: {_short_repr(svals[k], max_value_len)}\n")
        out.write("\n")

    if counts.get((325, "unknown_325")) or counts.get((326, "unknown_326")):
        vendor_rows = _collect_messages_by_mesg_num(data, _GOLF_VENDOR_MESG)
        _write_golf_vendor_forensics(vendor_rows, out)


def inspect_path(
    path: Path,
    *,
    out: TextIO,
    sample_per_type: int = 3,
    max_value_len: int = 200,
    record_stride: int = 50,
) -> None:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in (".fit", ".zip"):
        raise ValueError(f"Expected .fit or .zip, got {path.suffix}")

    chunks = iter_fit_bytes_from_path(path)
    if not chunks:
        out.write(f"No .fit payload in {path}\n")
        return
    for logical_name, data in chunks:
        inspect_fit_bytes(
            data,
            label=f"{path.name} :: {logical_name}",
            out=out,
            sample_per_type=sample_per_type,
            max_value_len=max_value_len,
            record_sample_stride=record_stride,
        )
