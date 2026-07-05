import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import CardContent from "@mui/material/CardContent";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import Container from "@mui/material/Container";
import Divider from "@mui/material/Divider";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Select from "@mui/material/Select";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import StarIcon from "@mui/icons-material/Star";
import StarBorderIcon from "@mui/icons-material/StarBorder";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import SettingsIcon from "@mui/icons-material/Settings";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiDelete, apiGet, apiPatch, apiPost } from "./api";
import {
  DRILL_CATEGORIES,
  DRILL_CATEGORY_LABELS,
  DRILL_SORT_LABELS,
  type DrillCategory,
  type DrillDefinition,
  type DrillSession,
  type DrillSortOrder,
  type DrillTrackingType,
} from "./drillTypes";

interface DrillsViewProps {
  onBack: () => void;
  initialDrillId?: string | null;
  sessionPrefill?: { club?: string; aim?: string };
}

function formatLoggedAt(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function formatDuration(minutes: number | null | undefined): string {
  if (minutes == null || minutes <= 0) return "";
  if (minutes < 60) return `~${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `~${h}h ${m}m` : `~${h}h`;
}

function formatDaysSince(days: number | null | undefined): string {
  if (days == null) return "";
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

function formatLastPlayed(drill: DrillDefinition): string {
  if (!drill.last_played_at) return "Never played";
  const when = formatLoggedAt(drill.last_played_at);
  const gap = formatDaysSince(drill.days_since_last_played);
  return gap ? `Last played ${when} (${gap})` : `Last played ${when}`;
}

function sortDrills(drills: DrillDefinition[], order: DrillSortOrder): DrillDefinition[] {
  const copy = [...drills];
  if (order === "catalog") return copy;
  if (order === "recently_practiced") {
    return copy.sort((a, b) => {
      const ta = a.last_played_at ? Date.parse(a.last_played_at) : 0;
      const tb = b.last_played_at ? Date.parse(b.last_played_at) : 0;
      return tb - ta;
    });
  }
  return copy.sort((a, b) => {
    const na = a.last_played_at == null;
    const nb = b.last_played_at == null;
    if (na !== nb) return na ? -1 : 1;
    const da = a.days_since_last_played ?? 0;
    const db = b.days_since_last_played ?? 0;
    return db - da;
  });
}

function DrillMetaRow({ drill, compact }: { drill: DrillDefinition; compact?: boolean }) {
  const duration = formatDuration(drill.expected_duration_minutes);
  const last = formatLastPlayed(drill);
  if (compact) {
    return (
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        {duration && (
          <Typography variant="body2" color="text.secondary">
            {duration}
          </Typography>
        )}
        <Typography variant="body2" color={drill.last_played_at ? "text.secondary" : "warning.main"}>
          {last}
        </Typography>
      </Stack>
    );
  }
  return (
    <Stack spacing={0.5}>
      {duration && (
        <Typography variant="body2" color="text.secondary">
          <strong>Expected time:</strong> {duration}
        </Typography>
      )}
      <Typography variant="body2" color={drill.last_played_at ? "text.secondary" : "warning.main"}>
        <strong>Practice history:</strong>{" "}
        {drill.last_played_at
          ? `${formatLoggedAt(drill.last_played_at)} (${formatDaysSince(drill.days_since_last_played)})`
          : "Never played"}
      </Typography>
    </Stack>
  );
}

function pointsFieldLabel(drillId: string): string {
  if (drillId === "par_18_putting" || drillId === "chip_par_18_challenge") {
    return "Total strokes";
  }
  if (drillId === "putt_20_tee_game") {
    return "Total points score";
  }
  if (drillId === "putt_overtake_game") {
    return "Total points score";
  }
  return "Points scored";
}

function defaultLogForm(
  drill: DrillDefinition,
  prefills?: { club?: string; aim?: string },
): Record<string, string> {
  switch (drill.tracking_type) {
    case "score_out_of_total":
      return {
        score: "",
        total: drill.expected_total_attempts != null ? String(drill.expected_total_attempts) : "",
      };
    case "boolean_completion":
      return { completed: "true" };
    case "points_based":
      return { points: "", max: drill.max_points != null ? String(drill.max_points) : "" };
    case "streak":
      return { streak: "" };
    case "total_attempts":
      return { attempts: "" };
    case "club_focus_session":
      return {
        club: prefills?.club ?? drill.suggested_clubs?.[0] ?? "",
        aim: prefills?.aim ?? drill.default_aim ?? "",
        completed: "true",
        combine_score: "",
      };
    default:
      return {};
  }
}

function buildResultPayload(
  tracking: DrillTrackingType,
  form: Record<string, string>,
): Record<string, unknown> {
  switch (tracking) {
    case "score_out_of_total":
      return {
        score: form.score ? Number(form.score) : null,
        total: form.total ? Number(form.total) : null,
      };
    case "boolean_completion":
      return { completed: form.completed === "true" };
    case "points_based":
      return { points: form.points ? Number(form.points) : null };
    case "streak":
      return { streak: form.streak ? Number(form.streak) : null };
    case "total_attempts":
      return { attempts: form.attempts ? Number(form.attempts) : null };
    case "club_focus_session":
      return {
        club:
          form.club?.trim().toLowerCase() === "__custom__"
            ? null
            : form.club?.trim().toLowerCase() || null,
        aim: form.aim?.trim() || null,
        completed: form.completed === "true",
        combine_score: form.combine_score ? Number(form.combine_score) : null,
      };
    default:
      return {};
  }
}

function sessionToForm(drill: DrillDefinition, session: DrillSession): Record<string, string> {
  const r = session.result || {};
  switch (drill.tracking_type) {
    case "score_out_of_total":
      return {
        score: r.score != null ? String(r.score) : "",
        total: r.total != null ? String(r.total) : "",
      };
    case "boolean_completion":
      return { completed: r.completed ? "true" : "false" };
    case "points_based":
      return { points: r.points != null ? String(r.points) : "" };
    case "streak":
      return { streak: r.streak != null ? String(r.streak) : "" };
    case "total_attempts":
      return { attempts: r.attempts != null ? String(r.attempts) : "" };
    case "club_focus_session":
      return {
        club: r.club != null ? String(r.club) : "",
        aim: r.aim != null ? String(r.aim) : "",
        completed: r.completed ? "true" : "false",
        combine_score: r.combine_score != null ? String(r.combine_score) : "",
      };
    default:
      return {};
  }
}

function isoToDatetimeLocal(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function datetimeLocalToIso(value: string): string {
  return new Date(value).toISOString();
}

function drillToEditForm(drill: DrillDefinition) {
  return {
    title: drill.title,
    description: drill.description,
    expected_duration_minutes: drill.expected_duration_minutes != null ? String(drill.expected_duration_minutes) : "",
    equipment_needed: drill.equipment_needed.join("\n"),
    distances: drill.distances.join("\n"),
    attempts_per_distance: drill.attempts_per_distance != null ? String(drill.attempts_per_distance) : "",
    is_timed: drill.is_timed,
    success_target: drill.success_target,
    penalty_reset_rule: drill.penalty_reset_rule ?? "",
  };
}

function SessionResultFields({
  drill,
  form,
  setForm,
  clubOptions,
}: {
  drill: DrillDefinition;
  form: Record<string, string>;
  setForm: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  clubOptions?: string[];
}) {
  if (drill.tracking_type === "score_out_of_total") {
    return (
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <TextField
          label="Made / success count"
          type="number"
          size="small"
          value={form.score}
          onChange={(e) => setForm((f) => ({ ...f, score: e.target.value }))}
          fullWidth
        />
        <TextField
          label="Total attempts"
          type="number"
          size="small"
          value={form.total}
          onChange={(e) => setForm((f) => ({ ...f, total: e.target.value }))}
          helperText={
            drill.expected_total_attempts != null
              ? `Drill target: ${drill.expected_total_attempts} attempts`
              : undefined
          }
          fullWidth
        />
      </Stack>
    );
  }
  if (drill.tracking_type === "boolean_completion") {
    return (
      <FormControlLabel
        control={
          <Checkbox
            checked={form.completed === "true"}
            onChange={(e) => setForm((f) => ({ ...f, completed: e.target.checked ? "true" : "false" }))}
          />
        }
        label="Completed without reset"
      />
    );
  }
  if (drill.tracking_type === "points_based") {
    return (
      <TextField
        label={pointsFieldLabel(drill.id)}
        type="number"
        size="small"
        value={form.points}
        onChange={(e) => setForm((f) => ({ ...f, points: e.target.value }))}
        helperText={drill.max_points != null ? `Max: ${drill.max_points} points` : undefined}
        fullWidth
      />
    );
  }
  if (drill.tracking_type === "streak") {
    return (
      <TextField
        label="Longest streak"
        type="number"
        size="small"
        value={form.streak}
        onChange={(e) => setForm((f) => ({ ...f, streak: e.target.value }))}
        fullWidth
      />
    );
  }
  if (drill.tracking_type === "total_attempts") {
    return (
      <TextField
        label={
          drill.id === "putt_10_foot_game"
            ? "Total putts to reach 10 points"
            : drill.id === "putt_20_tee_game"
              ? "Total putts to clear 20 tees"
              : drill.id === "ladder_drill"
                ? "Total attempts to clear ladder"
                : "Total attempts"
        }
        type="number"
        size="small"
        value={form.attempts}
        onChange={(e) => setForm((f) => ({ ...f, attempts: e.target.value }))}
        fullWidth
      />
    );
  }
  if (drill.tracking_type === "club_focus_session") {
    const clubs = [
      ...new Set([
        ...(clubOptions ?? []),
        ...(drill.suggested_clubs ?? []),
        form.club,
      ].filter(Boolean)),
    ].sort();
    return (
      <Stack spacing={2}>
        {drill.rapsodo_mode_label ? (
          <Typography variant="body2" color="text.secondary">
            Rapsodo mode: <strong>{drill.rapsodo_mode_label}</strong>
          </Typography>
        ) : null}
        <FormControl size="small" fullWidth>
          <InputLabel id="club-focus-label">Club focus</InputLabel>
          <Select
            labelId="club-focus-label"
            label="Club focus"
            value={form.club || ""}
            onChange={(e) => setForm((f) => ({ ...f, club: e.target.value }))}
          >
            {clubs.map((c) => (
              <MenuItem key={c} value={c}>
                {c}
              </MenuItem>
            ))}
            <MenuItem value="__custom__">Other (type below)</MenuItem>
          </Select>
        </FormControl>
        {form.club === "__custom__" || (form.club && !clubs.includes(form.club)) ? (
          <TextField
            label="Club name"
            size="small"
            value={form.club === "__custom__" ? "" : form.club}
            onChange={(e) => setForm((f) => ({ ...f, club: e.target.value }))}
            fullWidth
          />
        ) : null}
        <TextField
          label="Session aim"
          size="small"
          multiline
          minRows={2}
          value={form.aim}
          onChange={(e) => setForm((f) => ({ ...f, aim: e.target.value }))}
          helperText="What you were trying to achieve (e.g. 20 yd offline window)"
          fullWidth
        />
        {drill.rapsodo_mode === "combine" ? (
          <TextField
            label="Combine score (optional)"
            type="number"
            size="small"
            value={form.combine_score}
            onChange={(e) => setForm((f) => ({ ...f, combine_score: e.target.value }))}
            fullWidth
          />
        ) : null}
        <FormControlLabel
          control={
            <Checkbox
              checked={form.completed === "true"}
              onChange={(e) => setForm((f) => ({ ...f, completed: e.target.checked ? "true" : "false" }))}
            />
          }
          label="Session completed"
        />
      </Stack>
    );
  }
  return null;
}

function LogSessionForm({
  drill,
  onSaved,
  sessionPrefill,
  clubOptions,
}: {
  drill: DrillDefinition;
  onSaved: () => void;
  sessionPrefill?: { club?: string; aim?: string };
  clubOptions?: string[];
}) {
  const [form, setForm] = useState<Record<string, string>>(() => defaultLogForm(drill, sessionPrefill));
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(defaultLogForm(drill, sessionPrefill));
    setNotes("");
    setError(null);
  }, [drill.id, sessionPrefill?.club, sessionPrefill?.aim]);

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      await apiPost("/api/v1/drills/sessions", {
        drill_id: drill.id,
        result: buildResultPayload(drill.tracking_type, form),
        notes: notes.trim() || null,
      });
      setForm(defaultLogForm(drill, sessionPrefill));
      setNotes("");
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save session");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" fontWeight={700} gutterBottom>
        Log session
      </Typography>
      <Stack spacing={2}>
        <SessionResultFields drill={drill} form={form} setForm={setForm} clubOptions={clubOptions} />
        <TextField
          label="Notes (optional)"
          size="small"
          multiline
          minRows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          fullWidth
        />
        {error && (
          <Typography variant="body2" color="error">
            {error}
          </Typography>
        )}
        <Button variant="contained" onClick={() => void submit()} disabled={saving}>
          {saving ? "Saving…" : "Save session"}
        </Button>
      </Stack>
    </Paper>
  );
}

function EditDrillPanel({
  drill,
  onSaved,
  onReset,
}: {
  drill: DrillDefinition;
  onSaved: (updated: DrillDefinition) => void;
  onReset: (updated: DrillDefinition) => void;
}) {
  const [form, setForm] = useState(() => drillToEditForm(drill));
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(drillToEditForm(drill));
    setError(null);
  }, [drill.id, drill.title, drill.description, drill.expected_duration_minutes]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await apiPatch<DrillDefinition>(`/api/v1/drills/${drill.id}`, {
        title: form.title.trim(),
        description: form.description.trim(),
        expected_duration_minutes: form.expected_duration_minutes
          ? Number(form.expected_duration_minutes)
          : undefined,
        equipment_needed: form.equipment_needed,
        distances: form.distances,
        attempts_per_distance: form.attempts_per_distance ? Number(form.attempts_per_distance) : null,
        is_timed: form.is_timed,
        success_target: form.success_target.trim(),
        penalty_reset_rule: form.penalty_reset_rule.trim() || null,
      });
      onSaved(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save drill");
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    if (!window.confirm("Reset this drill to its default settings?")) return;
    setResetting(true);
    setError(null);
    try {
      const updated = await apiDelete<DrillDefinition>(`/api/v1/drills/${drill.id}/overrides`);
      onReset(updated);
      setForm(drillToEditForm(updated));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reset drill");
    } finally {
      setResetting(false);
    }
  };

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" fontWeight={700} gutterBottom>
        Drill settings
      </Typography>
      <Stack spacing={2}>
        <TextField
          label="Title"
          size="small"
          value={form.title}
          onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
          fullWidth
        />
        <TextField
          label="Description"
          size="small"
          multiline
          minRows={3}
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          fullWidth
        />
        <TextField
          label="Expected duration (minutes)"
          type="number"
          size="small"
          value={form.expected_duration_minutes}
          onChange={(e) => setForm((f) => ({ ...f, expected_duration_minutes: e.target.value }))}
          fullWidth
        />
        <TextField
          label="Equipment (one per line)"
          size="small"
          multiline
          minRows={2}
          value={form.equipment_needed}
          onChange={(e) => setForm((f) => ({ ...f, equipment_needed: e.target.value }))}
          fullWidth
        />
        <TextField
          label="Distances (one per line)"
          size="small"
          multiline
          minRows={2}
          value={form.distances}
          onChange={(e) => setForm((f) => ({ ...f, distances: e.target.value }))}
          fullWidth
        />
        <TextField
          label="Attempts per distance"
          type="number"
          size="small"
          value={form.attempts_per_distance}
          onChange={(e) => setForm((f) => ({ ...f, attempts_per_distance: e.target.value }))}
          fullWidth
        />
        <FormControlLabel
          control={
            <Checkbox
              checked={form.is_timed}
              onChange={(e) => setForm((f) => ({ ...f, is_timed: e.target.checked }))}
            />
          }
          label="Timed drill"
        />
        <TextField
          label="Success target"
          size="small"
          value={form.success_target}
          onChange={(e) => setForm((f) => ({ ...f, success_target: e.target.value }))}
          fullWidth
        />
        <TextField
          label="Reset rule (optional)"
          size="small"
          multiline
          minRows={2}
          value={form.penalty_reset_rule}
          onChange={(e) => setForm((f) => ({ ...f, penalty_reset_rule: e.target.value }))}
          fullWidth
        />
        {error && (
          <Typography variant="body2" color="error">
            {error}
          </Typography>
        )}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
          <Button variant="contained" onClick={() => void save()} disabled={saving}>
            {saving ? "Saving…" : "Save drill"}
          </Button>
          {drill.is_customized && (
            <Button variant="outlined" color="warning" onClick={() => void reset()} disabled={resetting}>
              {resetting ? "Resetting…" : "Reset to default"}
            </Button>
          )}
        </Stack>
      </Stack>
    </Paper>
  );
}

function SessionEditDialog({
  drill,
  session,
  open,
  clubOptions,
  onClose,
  onSaved,
}: {
  drill: DrillDefinition;
  session: DrillSession;
  open: boolean;
  clubOptions?: string[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState(() => sessionToForm(drill, session));
  const [notes, setNotes] = useState(session.notes ?? "");
  const [loggedAt, setLoggedAt] = useState(() => isoToDatetimeLocal(session.logged_at));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(sessionToForm(drill, session));
    setNotes(session.notes ?? "");
    setLoggedAt(isoToDatetimeLocal(session.logged_at));
    setError(null);
  }, [drill, session]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await apiPatch(`/api/v1/drills/sessions/${session.id}`, {
        result: buildResultPayload(drill.tracking_type, form),
        notes: notes.trim() || null,
        logged_at: loggedAt ? datetimeLocalToIso(loggedAt) : session.logged_at,
      });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save session");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Edit session</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField
            label="When"
            type="datetime-local"
            size="small"
            value={loggedAt}
            onChange={(e) => setLoggedAt(e.target.value)}
            InputLabelProps={{ shrink: true }}
            fullWidth
          />
          <SessionResultFields drill={drill} form={form} setForm={setForm} clubOptions={clubOptions} />
          <TextField
            label="Notes"
            size="small"
            multiline
            minRows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            fullWidth
          />
          {error && (
            <Typography variant="body2" color="error">
              {error}
            </Typography>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={() => void save()} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function SessionHistory({
  sessions,
  drill,
  editable,
  clubOptions,
  onChanged,
}: {
  sessions: DrillSession[];
  drill?: DrillDefinition;
  editable?: boolean;
  clubOptions?: string[];
  onChanged?: () => void;
}) {
  const [editingSession, setEditingSession] = useState<DrillSession | null>(null);

  if (!sessions.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No sessions logged yet.
      </Typography>
    );
  }

  const deleteSession = async (session: DrillSession) => {
    if (!window.confirm("Delete this session log?")) return;
    await apiDelete(`/api/v1/drills/sessions/${session.id}`);
    onChanged?.();
  };

  return (
    <>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>When</TableCell>
              <TableCell>Result</TableCell>
              <TableCell>Notes</TableCell>
              {editable && <TableCell align="right">Actions</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {sessions.map((s) => (
              <TableRow key={s.id}>
                <TableCell sx={{ whiteSpace: "nowrap" }}>{formatLoggedAt(s.logged_at)}</TableCell>
                <TableCell>
                  <Chip label={s.summary || "—"} size="small" variant="outlined" />
                </TableCell>
                <TableCell>{s.notes || "—"}</TableCell>
                {editable && drill && (
                  <TableCell align="right">
                    <IconButton size="small" aria-label="Edit session" onClick={() => setEditingSession(s)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      aria-label="Delete session"
                      onClick={() => void deleteSession(s)}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {editable && drill && editingSession && (
        <SessionEditDialog
          drill={drill}
          session={editingSession}
          open={Boolean(editingSession)}
          clubOptions={clubOptions}
          onClose={() => setEditingSession(null)}
          onSaved={() => onChanged?.()}
        />
      )}
    </>
  );
}

function DrillDetail({
  drill,
  isFavorite,
  sessions,
  sessionPrefill,
  clubOptions,
  onToggleFavorite,
  onSessionSaved,
  onDrillUpdated,
  onBack,
}: {
  drill: DrillDefinition;
  isFavorite: boolean;
  sessions: DrillSession[];
  sessionPrefill?: { club?: string; aim?: string };
  clubOptions?: string[];
  onToggleFavorite: () => void;
  onSessionSaved: () => void;
  onDrillUpdated: (updated: DrillDefinition) => void;
  onBack: () => void;
}) {
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <Stack spacing={2}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <IconButton onClick={onBack} aria-label="Back to list">
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h5" component="h2" fontWeight={600} sx={{ flex: 1 }}>
          {drill.title}
        </Typography>
        <IconButton
          onClick={() => setSettingsOpen((v) => !v)}
          aria-label="Drill settings"
          color={settingsOpen ? "primary" : "default"}
        >
          <SettingsIcon />
        </IconButton>
        <IconButton onClick={onToggleFavorite} aria-label="Toggle favorite">
          {isFavorite ? <StarIcon color="warning" /> : <StarBorderIcon />}
        </IconButton>
      </Stack>

      {settingsOpen ? (
        <>
          <EditDrillPanel
            drill={drill}
            onSaved={(updated) => {
              onDrillUpdated(updated);
              onSessionSaved();
            }}
            onReset={(updated) => {
              onDrillUpdated(updated);
              onSessionSaved();
            }}
          />
          <Typography variant="subtitle2" fontWeight={700}>
            Session history
          </Typography>
          <SessionHistory
            sessions={sessions}
            drill={drill}
            editable
            clubOptions={clubOptions}
            onChanged={onSessionSaved}
          />
        </>
      ) : (
        <>
          <Typography variant="body1">{drill.description}</Typography>

          <DrillMetaRow drill={drill} />

          <Stack direction="row" flexWrap="wrap" gap={1}>
            {drill.distances.map((d) => (
              <Chip key={d} label={d} size="small" />
            ))}
            {drill.rapsodo_mode_label ? (
              <Chip label={drill.rapsodo_mode_label} size="small" color="info" variant="outlined" />
            ) : null}
          </Stack>

          <Typography variant="body2" color="text.secondary">
            <strong>Equipment:</strong> {drill.equipment_needed.join(", ")}
          </Typography>
          {drill.attempts_per_distance != null && (
            <Typography variant="body2" color="text.secondary">
              <strong>Attempts per distance:</strong> {drill.attempts_per_distance}
            </Typography>
          )}
          {drill.penalty_reset_rule && (
            <Typography variant="body2" color="text.secondary">
              <strong>Reset rule:</strong> {drill.penalty_reset_rule}
            </Typography>
          )}
          <Typography variant="body2">
            <strong>Target:</strong> {drill.success_target}
          </Typography>

          <Divider />

          <LogSessionForm
            drill={drill}
            onSaved={onSessionSaved}
            sessionPrefill={sessionPrefill}
            clubOptions={clubOptions}
          />

          <Typography variant="subtitle2" fontWeight={700}>
            Session history
          </Typography>
          <SessionHistory sessions={sessions} />
        </>
      )}
    </Stack>
  );
}

function DrillListCard({
  drill,
  isFavorite,
  onOpen,
  onToggleFavorite,
}: {
  drill: DrillDefinition;
  isFavorite: boolean;
  onOpen: () => void;
  onToggleFavorite: (e: React.MouseEvent) => void;
}) {
  const sessionCount = drill.session_count ?? 0;
  return (
    <Card variant="outlined">
      <CardActionArea onClick={onOpen}>
        <CardContent>
          <Stack direction="row" alignItems="flex-start" spacing={1}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="subtitle1" fontWeight={600}>
                {drill.title}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {drill.description.length > 120
                  ? `${drill.description.slice(0, 120)}…`
                  : drill.description}
              </Typography>
              <Box sx={{ mt: 1 }}>
                <DrillMetaRow drill={drill} compact />
              </Box>
              <Stack direction="row" spacing={1} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
                <Chip label={drill.tracking_type.replace(/_/g, " ")} size="small" />
                {drill.is_timed && <Chip label="Timed" size="small" variant="outlined" />}
                {sessionCount > 0 && (
                  <Chip label={`${sessionCount} session${sessionCount === 1 ? "" : "s"}`} size="small" variant="outlined" />
                )}
              </Stack>
            </Box>
            <IconButton onClick={onToggleFavorite} aria-label="Toggle favorite" size="small">
              {isFavorite ? <StarIcon color="warning" fontSize="small" /> : <StarBorderIcon fontSize="small" />}
            </IconButton>
          </Stack>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

export default function DrillsView({ onBack, initialDrillId, sessionPrefill }: DrillsViewProps) {
  const [category, setCategory] = useState<DrillCategory>("putting");
  const [sortOrder, setSortOrder] = useState<DrillSortOrder>("catalog");
  const [clubOptions, setClubOptions] = useState<string[]>([]);
  const [catalog, setCatalog] = useState<Record<DrillCategory, DrillDefinition[]>>({
    putting: [],
    chipping: [],
    range: [],
  });
  const [favorites, setFavorites] = useState<string[]>([]);
  const [sessions, setSessions] = useState<DrillSession[]>([]);
  const [selectedDrillId, setSelectedDrillId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [catRes, favRes, sessRes] = await Promise.all([
        apiGet<{ categories: Record<DrillCategory, DrillDefinition[]> }>("/api/v1/drills/catalog"),
        apiGet<{ favorites: string[] }>("/api/v1/drills/favorites"),
        apiGet<{ sessions: DrillSession[] }>("/api/v1/drills/sessions"),
      ]);
      setCatalog({
        putting: catRes.categories.putting || [],
        chipping: catRes.categories.chipping || [],
        range: catRes.categories.range || [],
      });
      setFavorites(favRes.favorites || []);
      setSessions(sessRes.sessions || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load drills");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  useEffect(() => {
    void (async () => {
      try {
        const res = await apiGet<{ clubs: { club: string }[] }>("/api/v1/range/clubs-catalog");
        setClubOptions((res.clubs ?? []).map((c) => c.club).filter(Boolean));
      } catch {
        setClubOptions([]);
      }
    })();
  }, []);

  useEffect(() => {
    if (initialDrillId) {
      setSelectedDrillId(initialDrillId);
      const all = [...catalog.putting, ...catalog.chipping, ...catalog.range];
      const match = all.find((d) => d.id === initialDrillId);
      if (match?.category) setCategory(match.category);
    }
  }, [initialDrillId, catalog]);

  const favoriteDrills = useMemo(() => {
    const all = [...catalog.putting, ...catalog.chipping, ...catalog.range];
    return sortDrills(
      favorites
        .map((id) => all.find((d) => d.id === id))
        .filter((d): d is DrillDefinition => Boolean(d)),
      sortOrder,
    );
  }, [catalog, favorites, sortOrder]);

  const categoryDrills = useMemo(
    () => sortDrills(catalog[category] || [], sortOrder),
    [catalog, category, sortOrder],
  );
  const selectedDrill = useMemo(() => {
    if (!selectedDrillId) return null;
    return (
      [...catalog.putting, ...catalog.chipping, ...catalog.range].find((d) => d.id === selectedDrillId) ||
      null
    );
  }, [catalog, selectedDrillId]);

  const selectedSessions = useMemo(
    () => (selectedDrillId ? sessions.filter((s) => s.drill_id === selectedDrillId) : []),
    [sessions, selectedDrillId],
  );

  const toggleFavorite = async (drillId: string) => {
    const res = await apiPost<{ favorites: string[] }>(`/api/v1/drills/favorites/${drillId}/toggle`);
    setFavorites(res.favorites);
  };

  const refreshAfterSession = async () => {
    const [catRes, sessRes] = await Promise.all([
      apiGet<{ categories: Record<DrillCategory, DrillDefinition[]> }>("/api/v1/drills/catalog"),
      apiGet<{ sessions: DrillSession[] }>("/api/v1/drills/sessions"),
    ]);
    setCatalog({
      putting: catRes.categories.putting || [],
      chipping: catRes.categories.chipping || [],
      range: catRes.categories.range || [],
    });
    setSessions(sessRes.sessions || []);
  };

  const updateDrillInCatalog = (updated: DrillDefinition) => {
    setCatalog((prev) => {
      const next = { ...prev };
      for (const cat of DRILL_CATEGORIES) {
        next[cat] = prev[cat].map((d) => (d.id === updated.id ? { ...d, ...updated } : d));
      }
      return next;
    });
  };

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar position="sticky" color="default" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Toolbar>
          <Button startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ mr: 1, textTransform: "none" }}>
            Home
          </Button>
          <Typography variant="h6" component="div" sx={{ flex: 1, fontWeight: 600 }}>
            Drills
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="md" sx={{ py: 3 }}>
        {error && (
          <Typography color="error" sx={{ mb: 2 }}>
            {error}
          </Typography>
        )}

        {!selectedDrill && (
          <>
            <Stack
              direction={{ xs: "column", sm: "row" }}
              alignItems={{ xs: "stretch", sm: "center" }}
              justifyContent="space-between"
              spacing={2}
              sx={{ mb: 2 }}
            >
              <ToggleButtonGroup
                value={category}
                exclusive
                onChange={(_, v: DrillCategory | null) => v && setCategory(v)}
                sx={{ flexWrap: "wrap" }}
                size="small"
              >
                {DRILL_CATEGORIES.map((c) => (
                  <ToggleButton key={c} value={c} sx={{ textTransform: "none", px: 2.5 }}>
                    {DRILL_CATEGORY_LABELS[c]}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>

              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel id="drill-sort-label">Sort by</InputLabel>
                <Select
                  labelId="drill-sort-label"
                  label="Sort by"
                  value={sortOrder}
                  onChange={(e) => setSortOrder(e.target.value as DrillSortOrder)}
                >
                  {(Object.keys(DRILL_SORT_LABELS) as DrillSortOrder[]).map((key) => (
                    <MenuItem key={key} value={key}>
                      {DRILL_SORT_LABELS[key]}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Stack>

            {favoriteDrills.length > 0 && (
              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle2" fontWeight={700} gutterBottom>
                  Favorites
                </Typography>
                <Stack direction="row" flexWrap="wrap" gap={1}>
                  {favoriteDrills.map((d) => (
                    <Chip
                      key={d.id}
                      label={d.title}
                      onClick={() => setSelectedDrillId(d.id)}
                      icon={<StarIcon />}
                      color="warning"
                      variant="outlined"
                    />
                  ))}
                </Stack>
              </Box>
            )}

            {loading ? (
              <Typography color="text.secondary">Loading…</Typography>
            ) : categoryDrills.length === 0 ? (
              <Paper variant="outlined" sx={{ p: 3, textAlign: "center" }}>
                <Typography color="text.secondary">
                  {DRILL_CATEGORY_LABELS[category]} drills coming soon.
                </Typography>
              </Paper>
            ) : (
              <Stack spacing={1.5}>
                {categoryDrills.map((drill) => (
                  <DrillListCard
                    key={drill.id}
                    drill={drill}
                    isFavorite={favorites.includes(drill.id)}
                    onOpen={() => setSelectedDrillId(drill.id)}
                    onToggleFavorite={(e) => {
                      e.stopPropagation();
                      void toggleFavorite(drill.id);
                    }}
                  />
                ))}
              </Stack>
            )}
          </>
        )}

        {selectedDrill && (
          <DrillDetail
            drill={selectedDrill}
            isFavorite={favorites.includes(selectedDrill.id)}
            sessions={selectedSessions}
            sessionPrefill={sessionPrefill}
            clubOptions={clubOptions}
            onToggleFavorite={() => void toggleFavorite(selectedDrill.id)}
            onSessionSaved={() => void refreshAfterSession()}
            onDrillUpdated={updateDrillInCatalog}
            onBack={() => setSelectedDrillId(null)}
          />
        )}
      </Container>
    </Box>
  );
}
