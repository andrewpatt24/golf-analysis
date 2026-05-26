import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useState } from "react";
import { apiGet, apiPut } from "./api";
import type { OnCoursePlaybook, PitchRow } from "./onCourseTypes";

interface PlaybookEditorProps {
  /** When true, show intro copy for Coach Analysis settings. */
  showIntro?: boolean;
}

export default function PlaybookEditor({ showIntro = false }: PlaybookEditorProps) {
  const [playbook, setPlaybook] = useState<OnCoursePlaybook | null>(null);
  const [dirty, setDirty] = useState<Partial<OnCoursePlaybook>>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  useEffect(() => {
    void apiGet<OnCoursePlaybook>("/api/v1/on-course/playbook")
      .then(setPlaybook)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : String(e)));
  }, []);

  const merged = playbook ? { ...playbook, ...dirty } : null;

  function setField<K extends keyof OnCoursePlaybook>(key: K, value: OnCoursePlaybook[K]) {
    setDirty((d) => ({ ...d, [key]: value }));
    setOk(false);
  }

  function setPitchRow(i: number, field: keyof PitchRow, value: string) {
    if (!merged) return;
    const rows = [...merged.pitchRows];
    rows[i] = { ...rows[i], [field]: value };
    setField("pitchRows", rows);
  }

  async function save() {
    if (!merged) return;
    setSaving(true);
    setErr(null);
    setOk(false);
    try {
      const next = await apiPut<OnCoursePlaybook>("/api/v1/on-course/playbook", merged);
      setPlaybook(next);
      setDirty({});
      setOk(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  if (!merged) {
    return <Typography color="text.secondary">Loading playbook…</Typography>;
  }

  return (
    <Stack spacing={2}>
      {showIntro ? (
        <Typography variant="body2" color="text.secondary">
          Your swing thoughts, chip strategy, and fixes — edited here, read on course. Coach
          analysis stays focused on <em>where</em> to improve; this is your own technique crib
          sheet.
        </Typography>
      ) : null}
      {err ? (
        <Typography color="error" variant="body2">
          {err}
        </Typography>
      ) : null}
      {ok ? (
        <Typography color="success.main" variant="body2">
          Playbook saved.
        </Typography>
      ) : null}
      <TextField
        label="Swing box cue (one thought)"
        fullWidth
        value={merged.swingCue}
        onChange={(e) => setField("swingCue", e.target.value)}
      />
      <TextField
        label="Swing thoughts"
        fullWidth
        multiline
        minRows={4}
        value={merged.swingThoughts}
        onChange={(e) => setField("swingThoughts", e.target.value)}
      />
      <TextField
        label="Chip strategy"
        fullWidth
        multiline
        minRows={4}
        value={merged.chipNotes}
        onChange={(e) => setField("chipNotes", e.target.value)}
      />
      <TextField
        label="Putting routine"
        fullWidth
        multiline
        minRows={5}
        value={merged.puttingRoutine}
        onChange={(e) => setField("puttingRoutine", e.target.value)}
      />
      <TextField
        label="Quick fixes (your cues)"
        fullWidth
        multiline
        minRows={3}
        value={merged.fixNotes}
        onChange={(e) => setField("fixNotes", e.target.value)}
      />
      <TextField
        label="Wind"
        fullWidth
        multiline
        minRows={3}
        value={merged.windNotes}
        onChange={(e) => setField("windNotes", e.target.value)}
      />
      <Typography variant="subtitle2">Pitching matrix</Typography>
      {merged.pitchRows.map((row, i) => (
        <Stack key={i} direction={{ xs: "column", sm: "row" }} spacing={1}>
          <TextField
            label="Dist"
            size="small"
            value={row.dist}
            onChange={(e) => setPitchRow(i, "dist", e.target.value)}
            sx={{ flex: 1 }}
          />
          <TextField
            label="Club"
            size="small"
            value={row.club}
            onChange={(e) => setPitchRow(i, "club", e.target.value)}
            sx={{ flex: 1 }}
          />
          <TextField
            label="Stance"
            size="small"
            value={row.stance}
            onChange={(e) => setPitchRow(i, "stance", e.target.value)}
            sx={{ flex: 1 }}
          />
          <TextField
            label="Grip / swing"
            size="small"
            value={row.gripSwing}
            onChange={(e) => setPitchRow(i, "gripSwing", e.target.value)}
            sx={{ flex: 2 }}
          />
        </Stack>
      ))}
      <Box>
        <Button variant="contained" disabled={saving} onClick={() => void save()}>
          {saving ? "Saving…" : "Save playbook"}
        </Button>
      </Box>
    </Stack>
  );
}
