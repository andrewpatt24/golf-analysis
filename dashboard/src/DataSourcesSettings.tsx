import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiPost, apiPostForm, apiPut } from "./api";

export interface DataSourceRow {
  id: string;
  label: string;
  description: string;
  configured: boolean;
  last_run_at: string | null;
  last_ok: boolean | null;
  last_message: string | null;
  last_error: string | null;
}

interface CredentialsResponse {
  credentials: {
    rapsodo: {
      configured: boolean;
      bearer_masked: string | null;
      authorization_scheme: string;
      stored_in_dashboard?: boolean;
      source?: string | null;
    };
    garmin: {
      configured: boolean;
      garth_dir: string | null;
      stored_in_dashboard?: boolean;
      source?: string | null;
    };
  };
  rapsodo_config: string | null;
  gcs_enabled: boolean;
  local_hints?: string[];
}

interface CredentialSaveResponse {
  persisted_to_cloud?: boolean;
}

interface RefreshJob {
  job_id: string;
  status: string;
  source_ids: string[];
  results: Array<{
    source_id: string;
    ok: boolean;
    message: string;
    error?: string | null;
  }>;
  error: string | null;
  gcs_uploaded: boolean;
}

interface DataSourcesSettingsProps {
  onRefreshed?: () => void;
}

function statusChip(row: DataSourceRow) {
  if (!row.configured && row.id !== "local_ingest") {
    return <Chip size="small" label="Not configured" color="warning" />;
  }
  if (row.last_ok === false) {
    return <Chip size="small" label="Error" color="error" />;
  }
  if (row.last_ok === true) {
    return <Chip size="small" label="OK" color="success" />;
  }
  return <Chip size="small" label="—" variant="outlined" />;
}

export default function DataSourcesSettings({ onRefreshed }: DataSourcesSettingsProps) {
  const [sources, setSources] = useState<DataSourceRow[]>([]);
  const [credentials, setCredentials] = useState<CredentialsResponse | null>(null);
  const [rapsodoToken, setRapsodoToken] = useState("");
  const [garthJson, setGarthJson] = useState("");
  const [busy, setBusy] = useState(false);
  const [jobLog, setJobLog] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const cloud = credentials?.gcs_enabled ?? false;

  const load = useCallback(async () => {
    const [src, cred] = await Promise.all([
      apiGet<{ sources: DataSourceRow[] }>("/api/v1/data-sources"),
      apiGet<CredentialsResponse>("/api/v1/data-sources/credentials"),
    ]);
    setSources(src.sources ?? []);
    setCredentials(cred);
  }, []);

  useEffect(() => {
    void load().catch((e: unknown) => setErr(e instanceof Error ? e.message : String(e)));
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [load]);

  const noteSaved = useCallback((res: CredentialSaveResponse) => {
    if (res.persisted_to_cloud) {
      setSavedMsg("Credentials saved to cloud storage.");
    } else if (cloud) {
      setSavedMsg("Credentials saved.");
    } else {
      setSavedMsg("Credentials saved on this machine.");
    }
  }, [cloud]);

  const pollJob = useCallback(
    (jobId: string) => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(() => {
        void (async () => {
          try {
            const job = await apiGet<RefreshJob>(`/api/v1/data-sources/jobs/${jobId}`);
            const lines = (job.results ?? []).map(
              (r) => `${r.source_id}: ${r.ok ? r.message : r.error ?? "failed"}`,
            );
            setJobLog(lines.join("\n") || `Status: ${job.status}`);
            if (job.status === "succeeded" || job.status === "failed") {
              if (pollRef.current) clearInterval(pollRef.current);
              pollRef.current = null;
              setBusy(false);
              await load();
              if (job.status === "succeeded") onRefreshed?.();
              if (job.error) setErr(job.error);
            }
          } catch (e) {
            setErr(e instanceof Error ? e.message : String(e));
            setBusy(false);
            if (pollRef.current) clearInterval(pollRef.current);
          }
        })();
      }, 1500);
    },
    [load, onRefreshed],
  );

  const startRefresh = useCallback(
    async (path: string) => {
      setErr(null);
      setSavedMsg(null);
      setBusy(true);
      setJobLog("Starting…");
      try {
        const started = await apiPost<{ job_id: string }>(path);
        pollJob(started.job_id);
      } catch (e) {
        setBusy(false);
        setErr(e instanceof Error ? e.message : String(e));
      }
    },
    [pollJob],
  );

  const saveRapsodo = useCallback(async () => {
    setErr(null);
    setSavedMsg(null);
    try {
      const res = await apiPut<CredentialSaveResponse>("/api/v1/data-sources/credentials/rapsodo", {
        bearer: rapsodoToken.trim(),
        authorization_scheme: credentials?.credentials.rapsodo.authorization_scheme ?? "JWT",
      });
      setRapsodoToken("");
      noteSaved(res);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [rapsodoToken, credentials, load, noteSaved]);

  const uploadGarth = useCallback(
    async (file: File | null) => {
      if (!file) return;
      setErr(null);
      setSavedMsg(null);
      setBusy(true);
      try {
        const res = await apiPostForm<CredentialSaveResponse>(
          "/api/v1/data-sources/credentials/garth",
          (() => {
            const form = new FormData();
            form.append("file", file);
            return form;
          })(),
        );
        noteSaved(res);
        await load();
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [load, noteSaved],
  );

  const saveGarthJson = useCallback(async () => {
    if (!garthJson.trim()) return;
    setErr(null);
    setSavedMsg(null);
    setBusy(true);
    try {
      const res = await apiPost<CredentialSaveResponse>("/api/v1/data-sources/credentials/garth-json", {
        content: garthJson,
      });
      setGarthJson("");
      noteSaved(res);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [garthJson, load, noteSaved]);

  const garminOk = credentials?.credentials.garmin.configured ?? false;
  const rapsodoOk = credentials?.credentials.rapsodo.configured ?? false;

  const importLocal = useCallback(async () => {
    setErr(null);
    try {
      await apiPost("/api/v1/data-sources/credentials/import-local");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [load]);

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        {cloud
          ? "Connect Rapsodo and Garmin here, then refresh to pull new data. Credentials are saved to your private cloud bucket automatically."
          : "Pull new data from Rapsodo and Garmin. Local dev can auto-detect repo secrets.json and ~/.garth."}
      </Typography>

      {!cloud && (credentials?.local_hints?.length ?? 0) > 0 ? (
        <Alert severity="info">Using local credentials: {credentials?.local_hints?.join("; ")}.</Alert>
      ) : null}

      {!cloud &&
      ((credentials?.credentials.rapsodo.configured &&
        !credentials.credentials.rapsodo.stored_in_dashboard) ||
        (credentials?.credentials.garmin.configured &&
          !credentials.credentials.garmin.stored_in_dashboard)) ? (
        <Button variant="outlined" size="small" onClick={() => void importLocal()}>
          Import local credentials into dashboard
        </Button>
      ) : null}

      {savedMsg ? (
        <Alert severity="success" onClose={() => setSavedMsg(null)}>
          {savedMsg}
        </Alert>
      ) : null}

      {err ? (
        <Alert severity="error" onClose={() => setErr(null)}>
          {err}
        </Alert>
      ) : null}

      <Box sx={{ p: 1.5, border: 1, borderColor: "divider", borderRadius: 1 }}>
        <Typography variant="subtitle2" fontWeight={700} gutterBottom>
          Rapsodo
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
          {cloud
            ? "Paste your R-Cloud JWT from browser DevTools (Authorization header, without the \"JWT \" prefix)."
            : "Paste JWT, or use repo secrets.json for CLI sync."}
          {rapsodoOk && credentials?.credentials.rapsodo.bearer_masked
            ? ` Saved: ${credentials.credentials.rapsodo.bearer_masked}`
            : rapsodoOk
              ? " Configured."
              : " Not configured yet."}
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
          <TextField
            size="small"
            fullWidth
            type="password"
            label="Rapsodo JWT"
            value={rapsodoToken}
            onChange={(e) => setRapsodoToken(e.target.value)}
          />
          <Button variant="outlined" disabled={!rapsodoToken.trim()} onClick={() => void saveRapsodo()}>
            Save
          </Button>
        </Stack>
      </Box>

      <Box sx={{ p: 1.5, border: 1, borderColor: "divider", borderRadius: 1 }}>
        <Typography variant="subtitle2" fontWeight={700} gutterBottom>
          Garmin Connect
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
          {cloud ? (
            <>
              Paste the contents of your Garth <code>oauth2_token.json</code> (from{" "}
              <code>garth login</code> on any machine — copy the file, not your Garmin password).
            </>
          ) : (
            <>
              Paste Garth <code>oauth2_token.json</code>, or use <code>~/.garth</code> after{" "}
              <code>garth login</code>.
            </>
          )}
          {garminOk ? " Configured." : " Not configured yet."}
        </Typography>
        <Stack spacing={1}>
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={4}
            label="Garth oauth2_token.json"
            placeholder='{"scope": "...", "token_type": "bearer", ...}'
            value={garthJson}
            onChange={(e) => setGarthJson(e.target.value)}
          />
          <Stack direction="row" spacing={1} flexWrap="wrap">
            <Button
              variant="contained"
              disabled={!garthJson.trim() || busy}
              onClick={() => void saveGarthJson()}
            >
              Save Garmin token
            </Button>
            {!cloud ? (
              <Button variant="outlined" component="label" disabled={busy}>
                Upload .zip
                <input
                  type="file"
                  accept=".zip"
                  hidden
                  onChange={(e) => void uploadGarth(e.target.files?.[0] ?? null)}
                />
              </Button>
            ) : null}
          </Stack>
        </Stack>
      </Box>

      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
        <Button
          variant="contained"
          disabled={busy}
          onClick={() => void startRefresh("/api/v1/data-sources/refresh-all")}
        >
          {busy ? "Refreshing…" : "Refresh all"}
        </Button>
        {busy ? <CircularProgress size={22} /> : null}
      </Stack>

      {jobLog ? (
        <Typography
          component="pre"
          variant="caption"
          sx={{ whiteSpace: "pre-wrap", bgcolor: "grey.100", p: 1, borderRadius: 1 }}
        >
          {jobLog}
        </Typography>
      ) : null}

      {sources.map((row) => (
        <Box
          key={row.id}
          sx={{ p: 1.5, border: 1, borderColor: "divider", borderRadius: 1 }}
        >
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={1}>
            <Box>
              <Typography variant="subtitle2" fontWeight={700}>
                {row.label}
              </Typography>
              <Typography variant="caption" color="text.secondary" display="block">
                {row.description}
              </Typography>
              {row.last_message ? (
                <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                  {row.last_message}
                </Typography>
              ) : null}
              {row.last_error ? (
                <Typography variant="caption" color="error" display="block">
                  {row.last_error}
                </Typography>
              ) : null}
            </Box>
            <Stack alignItems="flex-end" spacing={0.5}>
              {statusChip(row)}
              <Button
                size="small"
                variant="outlined"
                disabled={busy}
                onClick={() =>
                  void startRefresh(`/api/v1/data-sources/${encodeURIComponent(row.id)}/refresh`)
                }
              >
                Refresh
              </Button>
            </Stack>
          </Stack>
        </Box>
      ))}

      {cloud ? (
        <Typography variant="caption" color="text.secondary">
          After refresh, your library and exports are updated in cloud storage automatically.
        </Typography>
      ) : null}
    </Stack>
  );
}
