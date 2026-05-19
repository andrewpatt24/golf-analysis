import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Alert from "@mui/material/Alert";
import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import Container from "@mui/material/Container";
import Divider from "@mui/material/Divider";
import FormControl from "@mui/material/FormControl";
import FormControlLabel from "@mui/material/FormControlLabel";
import FormGroup from "@mui/material/FormGroup";
import InputLabel from "@mui/material/InputLabel";
import ListSubheader from "@mui/material/ListSubheader";
import MenuItem from "@mui/material/MenuItem";
import Select, { type SelectChangeEvent } from "@mui/material/Select";
import Link from "@mui/material/Link";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Tabs from "@mui/material/Tabs";
import TextField from "@mui/material/TextField";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Paper from "@mui/material/Paper";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import { useTheme } from "@mui/material/styles";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiGet, apiPut } from "./api";

const TAB_KEYS = ["strategy", "performance", "training", "plans", "settings"] as const;
type Tab = (typeof TAB_KEYS)[number];

const COLORS = [
  "#1a73e8",
  "#d93025",
  "#188038",
  "#f9ab00",
  "#9334e6",
  "#c5221f",
  "#087f8c",
  "#e8710a",
];

function sessionColor(sid: number): string {
  return COLORS[Math.abs(sid) % COLORS.length];
}

interface Meta {
  library_db: string;
  golf_rounds: number;
  range_sessions: number;
  range_shots: number;
}

interface ClubRow {
  club: string;
  n: number;
  mean_carry_yards: number | null;
  mean_abs_offline_yards: number | null;
  dispersion_ratio_mean_abs_offline_per_carry: number | null;
  lateral_to_length_ratio_sd: number | null;
  needs_work: boolean;
}

interface ScatterPoint {
  carry_yards: number;
  offline_yards: number | null;
  club: string | null;
  session_id: number;
  session_title: string | null;
}

interface Settings {
  maxRounds: number;
  maxPracticeSessions: number;
  maxAgeDays: number;
  calendarYear: number;
  trainingBlockSessions: number;
}

interface PlanResponse {
  calendar_year: number;
  sessions_planned: number;
  insights: string[];
  flagged_clubs: string[];
  sessions: { index: number; title: string; description: string; priority_tag: string }[];
}

interface GarminScorecardRow {
  scorecard_id: string | null;
  course_name: string | null;
  started_at: string | null;
  strokes: number | null;
  holes_completed: number | null;
  score_type: string | null;
  stableford_points: number | null;
  total_putts_holes: number;
  fairway_decided: number;
  fairway_hit: number;
  penalty_holes: number;
  blowup_holes_ge7: number;
  mean_strokes_per_hole: number | null;
}

type StrategyTrendKind = "percent" | "count";

interface StrategyTrendPoint {
  order: number;
  xTick: string;
  started_at: string | null;
  course_name: string | null;
  scorecard_id: string | null;
  fw_pct: number | null;
  esz_pct: number | null;
  dsz_pct: number | null;
  strokes: number | null;
  holes_completed: number | null;
  putts: number | null;
  penalty_holes: number | null;
  blowup_ge7: number | null;
  stableford_points: number | null;
  esz_holes_eval: number | null;
  dsz_zone_holes: number | null;
  esz_success_holes: number | null;
  dsz_success_holes: number | null;
  mean_strokes_per_hole: number | null;
}

interface StrategyChartMetric {
  id: string;
  label: string;
  kind: StrategyTrendKind;
  dataKey: keyof StrategyTrendPoint;
}

const STRATEGY_CHART_METRICS: StrategyChartMetric[] = [
  { id: "fw_pct", label: "Fairway %", kind: "percent", dataKey: "fw_pct" },
  { id: "esz_pct", label: "ESZ %", kind: "percent", dataKey: "esz_pct" },
  { id: "dsz_pct", label: "DSZ %", kind: "percent", dataKey: "dsz_pct" },
  { id: "strokes", label: "Strokes", kind: "count", dataKey: "strokes" },
  { id: "holes_completed", label: "Holes scored", kind: "count", dataKey: "holes_completed" },
  { id: "putts", label: "Putts (Σ holes)", kind: "count", dataKey: "putts" },
  { id: "penalty_holes", label: "Penalty holes", kind: "count", dataKey: "penalty_holes" },
  { id: "blowup_ge7", label: "Blow-up holes (≥7)", kind: "count", dataKey: "blowup_ge7" },
  { id: "stableford_points", label: "Stableford points", kind: "count", dataKey: "stableford_points" },
  { id: "esz_holes_eval", label: "ESZ holes (evaluated)", kind: "count", dataKey: "esz_holes_eval" },
  { id: "dsz_zone_holes", label: "DSZ holes (in zone)", kind: "count", dataKey: "dsz_zone_holes" },
  { id: "esz_success_holes", label: "ESZ success holes", kind: "count", dataKey: "esz_success_holes" },
  { id: "dsz_success_holes", label: "DSZ success holes", kind: "count", dataKey: "dsz_success_holes" },
  { id: "mean_spi", label: "Mean strokes / hole", kind: "count", dataKey: "mean_strokes_per_hole" },
];

const DEFAULT_STRATEGY_CHART_METRIC_IDS = STRATEGY_CHART_METRICS.filter((m) => m.kind === "percent").map((m) => m.id);

function buildStrategyTrendSeries(
  scorecards: GarminScorecardRow[],
  eszByRound: Map<string, Record<string, unknown>>,
): StrategyTrendPoint[] {
  const sorted = [...scorecards].sort((a, b) => {
    const ta = a.started_at ?? "";
    const tb = b.started_at ?? "";
    return ta.localeCompare(tb);
  });
  return sorted.map((sc, order) => {
    const sid =
      sc.scorecard_id != null && String(sc.scorecard_id).trim() !== ""
        ? String(sc.scorecard_id).trim()
        : null;
    const er = sid ? eszByRound.get(sid) : undefined;
    const fw = sc.fairway_decided > 0 ? (100 * sc.fairway_hit) / sc.fairway_decided : null;
    const date = sc.started_at?.slice(0, 10) ?? `R${order + 1}`;
    const course = sc.course_name?.trim() || "";
    const short = course.length > 14 ? `${course.slice(0, 12)}…` : course;
    const xTick = short ? `${date} · ${short}` : date;
    return {
      order,
      xTick,
      started_at: sc.started_at ?? null,
      course_name: sc.course_name ?? null,
      scorecard_id: sid,
      fw_pct: fw,
      esz_pct: typeof er?.esz_pct === "number" ? (er.esz_pct as number) : null,
      dsz_pct: typeof er?.dsz_pct === "number" ? (er.dsz_pct as number) : null,
      strokes: sc.strokes ?? null,
      holes_completed: sc.holes_completed ?? null,
      putts: sc.total_putts_holes,
      penalty_holes: sc.penalty_holes,
      blowup_ge7: sc.blowup_holes_ge7,
      stableford_points: sc.stableford_points,
      esz_holes_eval: typeof er?.holes_evaluated === "number" ? (er.holes_evaluated as number) : null,
      dsz_zone_holes:
        typeof er?.dsz_holes_with_zone_entry === "number" ? (er.dsz_holes_with_zone_entry as number) : null,
      esz_success_holes: typeof er?.esz_success_holes === "number" ? (er.esz_success_holes as number) : null,
      dsz_success_holes: typeof er?.dsz_success_holes === "number" ? (er.dsz_success_holes as number) : null,
      mean_strokes_per_hole: sc.mean_strokes_per_hole ?? null,
    };
  });
}

function strategyMetricColor(metricId: string): string {
  const ix = STRATEGY_CHART_METRICS.findIndex((m) => m.id === metricId);
  return COLORS[Math.max(0, ix) % COLORS.length];
}

interface StrategyOverviewResponse {
  source_available: boolean;
  year: number;
  reason?: string;
  source?: string;
  scoring_method: Record<string, unknown>;
  performance: Record<string, unknown>;
  scorecards: GarminScorecardRow[];
  esz_dsz_in_sql: boolean;
  esz_dsz_from_shots?: Record<string, unknown>;
}

interface PerfBundleResponse {
  available: boolean;
  year?: number;
  source?: string;
  round_rollups: Record<string, unknown>;
  last10: Record<string, unknown>;
  rounds_in_bundle?: number;
}

interface CarryDistRow {
  club: string;
  n: number;
  mean_carry_yards: number;
  p10_carry_yards: number | null;
  p90_carry_yards: number | null;
  mean_abs_offline_yards: number | null;
  dispersion_index_mean_abs_per_carry: number | null;
}

interface LandingSideRow {
  club: string;
  n: number;
  pct_left: number;
  pct_right: number;
  pct_straight: number;
  straight_band_yards: number;
}

interface GappingRow {
  club: string;
  median_carry_yards: number;
  n: number;
  gap_from_previous_club_yards: number | null;
  previous_club_in_order: string | null;
}

interface TrainingAnalyticsResponse {
  carry_distribution: CarryDistRow[];
  landing_side: LandingSideRow[];
  gapping: GappingRow[];
  shot_shape: Record<string, unknown>;
  takeaways: string[];
}

interface ClubSideCompareDetail {
  club: string;
  n: number;
  pct_left: number;
  pct_straight: number;
  pct_right: number;
  mean_carry_yards_left: number | null;
  mean_carry_yards_straight: number | null;
  mean_carry_yards_right: number | null;
  mean_launch_angle_deg: number | null;
  mean_smash_factor: number | null;
  straight_band_yards: number;
}

interface ClubCompareResponse {
  error?: string;
  club_a: ClubSideCompareDetail | null;
  club_b: ClubSideCompareDetail | null;
  straight_band_yards?: number;
  calendar_year?: number | null;
}

interface TrainingShotRow {
  shot_id: number;
  shot_index: number | null;
  club: string | null;
  carry_yards: number | null;
  offline_yards: number | null;
  ball_speed_mph: number | null;
  smash_factor: number | null;
  launch_angle_deg: number | null;
  spin_rpm: number | null;
  spin_axis_deg: number | null;
  session_id: number;
  session_title: string | null;
  session_started_at: string | null;
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v.toFixed(1)}%`;
}

function shotShapeBarData(shape: Record<string, unknown> | undefined): { name: string; pct: number }[] {
  if (!shape || typeof shape !== "object") return [];
  const n = Number(shape.n_shots);
  if (!n) return [];
  return [
    { name: "Straight band", pct: Number(shape.pct_straight_band) || 0 },
    { name: "Hook side", pct: Number(shape.pct_hook_side) || 0 },
    { name: "Slice side", pct: Number(shape.pct_slice_side) || 0 },
  ];
}

function fiveWaySpinAxisBars(fw: unknown): { name: string; pct: number }[] {
  const r = asRecord(fw);
  if (!r || r.usable !== true) return [];
  return [
    { name: "Hook", pct: Number(r.pct_hook) || 0 },
    { name: "Draw", pct: Number(r.pct_draw) || 0 },
    { name: "Straight", pct: Number(r.pct_straight) || 0 },
    { name: "Fade", pct: Number(r.pct_fade) || 0 },
    { name: "Slice", pct: Number(r.pct_slice) || 0 },
  ];
}

function asRecord(v: unknown): Record<string, unknown> | null {
  if (v && typeof v === "object" && !Array.isArray(v)) return v as Record<string, unknown>;
  return null;
}

const LAST10_SG_LABELS: Record<string, string> = {
  approach: "Approach",
  around_the_green: "Around the green",
  putting: "Putting",
  tee: "Tee",
};

function last10SgChartRows(last10: Record<string, unknown> | undefined): { name: string; mean: number; sum: number }[] {
  if (!last10) return [];
  return Object.entries(last10)
    .filter(([k]) => k !== "_overall")
    .map(([k, v]) => {
      const o = asRecord(v);
      return {
        name: LAST10_SG_LABELS[k] ?? k,
        mean: typeof o?.mean_sg === "number" ? o.mean_sg : Number(o?.mean_sg) || 0,
        sum: typeof o?.sum_sg === "number" ? o.sum_sg : Number(o?.sum_sg) || 0,
      };
    });
}

function clubColorFromName(club: string): string {
  let h = 0;
  const s = club || "—";
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return COLORS[Math.abs(h) % COLORS.length];
}

function tabIndex(t: Tab): number {
  return TAB_KEYS.indexOf(t);
}

export default function App() {
  const theme = useTheme();
  const [tab, setTab] = useState<Tab>("training");
  const [err, setErr] = useState<string | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [year, setYear] = useState(2026);

  const [strategyOverview, setStrategyOverview] = useState<StrategyOverviewResponse | null>(null);
  const [strategyChartMetrics, setStrategyChartMetrics] = useState<string[]>(
    () => [...DEFAULT_STRATEGY_CHART_METRIC_IDS],
  );
  const [perfBundle, setPerfBundle] = useState<PerfBundleResponse | null>(null);
  const [roundSummary, setRoundSummary] = useState<Record<string, unknown> | null>(null);
  const [clubs, setClubs] = useState<ClubRow[]>([]);
  const [scatter, setScatter] = useState<ScatterPoint[]>([]);
  const [trainingAnalytics, setTrainingAnalytics] = useState<TrainingAnalyticsResponse | null>(null);
  const [trainingShots, setTrainingShots] = useState<TrainingShotRow[]>([]);
  const [compareClubA, setCompareClubA] = useState("driver");
  const [compareClubB, setCompareClubB] = useState("3w");
  const [clubCompare, setClubCompare] = useState<ClubCompareResponse | null>(null);
  const [compareBusy, setCompareBusy] = useState(false);
  const [sgAgg, setSgAgg] = useState<"mean" | "sum">("mean");
  const [scatterColorBy, setScatterColorBy] = useState<"session" | "club">("session");
  const [shotCols, setShotCols] = useState({
    carry: true,
    offline: true,
    smash: true,
    launch: true,
    ball: false,
    spin: false,
    axis: false,
    shotIx: false,
    session: true,
  });
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [settingsDirty, setSettingsDirty] = useState<Partial<Settings>>({});
  const [saving, setSaving] = useState(false);

  const eszByRoundMap = useMemo(() => {
    const raw = strategyOverview?.esz_dsz_from_shots as { by_round?: unknown } | undefined;
    const br = raw?.by_round;
    const m = new Map<string, Record<string, unknown>>();
    if (!Array.isArray(br)) return m;
    for (const row of br) {
      if (!row || typeof row !== "object") continue;
      const o = row as Record<string, unknown>;
      const sid = o.scorecard_id;
      if (sid != null && String(sid).trim() !== "") m.set(String(sid).trim(), o);
    }
    return m;
  }, [strategyOverview]);

  const strategyTrendSeries = useMemo(() => {
    if (!strategyOverview?.scorecards?.length) return [];
    return buildStrategyTrendSeries(strategyOverview.scorecards, eszByRoundMap);
  }, [strategyOverview?.scorecards, eszByRoundMap]);

  const onStrategyChartMetricsChange = useCallback((e: SelectChangeEvent<string[]>) => {
    const raw = e.target.value;
    const next = typeof raw === "string" ? raw.split(",") : [...raw];
    setStrategyChartMetrics(next.length > 0 ? next : [...DEFAULT_STRATEGY_CHART_METRIC_IDS]);
  }, []);

  const eszDataModel = useMemo(() => {
    const dm = (strategyOverview?.esz_dsz_from_shots as { data_model?: Record<string, unknown> } | undefined)
      ?.data_model;
    return dm && typeof dm === "object" ? dm : null;
  }, [strategyOverview]);

  const loadMeta = useCallback(async () => {
    const m = await apiGet<Meta>("/api/v1/meta");
    setMeta(m);
  }, []);

  const loadSettings = useCallback(async () => {
    const s = await apiGet<Settings>("/api/v1/settings");
    setSettings(s);
    setYear(Number(s.calendarYear));
    setSettingsDirty({});
  }, []);

  const refreshTraining = useCallback(async (y: number) => {
    const [c, sc, an, sh] = await Promise.all([
      apiGet<ClubRow[]>(`/api/v1/training/clubs?year=${y}`),
      apiGet<ScatterPoint[]>(`/api/v1/training/scatter?year=${y}`),
      apiGet<TrainingAnalyticsResponse>(`/api/v1/training/analytics?year=${y}`),
      apiGet<TrainingShotRow[]>(`/api/v1/training/shots?year=${y}&limit=80`),
    ]);
    setClubs(c);
    setScatter(sc);
    setTrainingAnalytics(an);
    setTrainingShots(sh);
    setClubCompare(null);
  }, []);

  const refreshPlans = useCallback(async () => {
    const p = await apiGet<PlanResponse>("/api/v1/plans/training-block");
    setPlan(p);
  }, []);

  const runClubCompare = useCallback(async () => {
    setCompareBusy(true);
    setErr(null);
    try {
      const q = new URLSearchParams({
        club_a: compareClubA.trim(),
        club_b: compareClubB.trim(),
        year: String(year),
      });
      const d = await apiGet<ClubCompareResponse>(`/api/v1/training/club-compare?${q.toString()}`);
      setClubCompare(d);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setCompareBusy(false);
    }
  }, [compareClubA, compareClubB, year]);

  useEffect(() => {
    setErr(null);
    void (async () => {
      try {
        await loadMeta();
        await loadSettings();
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [loadMeta, loadSettings]);

  useEffect(() => {
    if (!settings) return;
    setErr(null);
    void (async () => {
      try {
        await refreshTraining(year);
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [year, settings, refreshTraining]);

  useEffect(() => {
    if (tab !== "strategy") return;
    setErr(null);
    void (async () => {
      try {
        const ov = await apiGet<StrategyOverviewResponse>(`/api/v1/strategy/overview?year=${year}&limit=50`);
        setStrategyOverview(ov);
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [tab, year]);

  useEffect(() => {
    if (tab !== "performance") return;
    setErr(null);
    void (async () => {
      try {
        const [b, rs] = await Promise.all([
          apiGet<PerfBundleResponse>(`/api/v1/performance/garmin-bundle?year=${year}&limit=50`),
          apiGet<Record<string, unknown>>("/api/v1/rounds/summary"),
        ]);
        setPerfBundle(b);
        setRoundSummary(rs);
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [tab, year]);

  useEffect(() => {
    if (tab !== "plans") return;
    setErr(null);
    void (async () => {
      try {
        await refreshPlans();
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [tab, refreshPlans]);

  async function saveSettingsForm() {
    if (!settings) return;
    setSaving(true);
    setErr(null);
    try {
      const body = { ...settings, ...settingsDirty };
      const next = await apiPut<Settings>("/api/v1/settings", body);
      setSettings(next);
      setSettingsDirty({});
      setYear(Number(next.calendarYear));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  const barData = clubs.map((c) => ({
    name: c.club,
    carry: c.mean_carry_yards ?? 0,
    n: c.n,
  }));

  const sgRows = useMemo(() => last10SgChartRows(perfBundle?.last10 as Record<string, unknown> | undefined), [perfBundle?.last10]);

  const scatterPlotted = useMemo(
    () =>
      scatter
        .filter((p) => p.offline_yards != null)
        .map((p) => ({
          x: p.carry_yards,
          y: p.offline_yards as number,
          session_id: p.session_id,
          club: p.club ?? "",
          label: p.session_title ?? String(p.session_id),
          colorKey: scatterColorBy === "session" ? String(p.session_id) : p.club || "—",
        })),
    [scatter, scatterColorBy],
  );

  const scatterLegendKeys = useMemo(() => [...new Set(scatterPlotted.map((p) => p.colorKey))].sort(), [scatterPlotted]);

  const scatterColorFn = useCallback(
    (key: string) => (scatterColorBy === "session" ? sessionColor(Number(key)) : clubColorFromName(key)),
    [scatterColorBy],
  );

  const shapeBars = shotShapeBarData(trainingAnalytics?.shot_shape);
  const fiveWayBars = fiveWaySpinAxisBars(trainingAnalytics?.shot_shape?.["five_way_spin_axis"]);

  const handleTabChange = (_: React.SyntheticEvent, value: number) => {
    setTab(TAB_KEYS[value] ?? "training");
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar position="sticky" color="inherit" sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Toolbar variant="dense" sx={{ gap: 2, flexWrap: "wrap" }}>
          <Typography variant="h6" component="h1" sx={{ flexGrow: 1, fontWeight: 500 }}>
            Golf analysis
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ display: { xs: "none", sm: "block" } }}>
            API <code>/api/v1</code>
            {import.meta.env.DEV ? (
              <Chip size="small" label="dev" sx={{ ml: 1, height: 22 }} variant="outlined" />
            ) : null}
          </Typography>
        </Toolbar>
        <Tabs
          value={tabIndex(tab)}
          onChange={handleTabChange}
          variant="scrollable"
          scrollButtons="auto"
          aria-label="Main navigation"
          sx={{
            px: 1,
            minHeight: 44,
            "& .MuiTab-root": { minHeight: 44, textTransform: "none", fontWeight: 500 },
          }}
        >
          <Tab label="Strategy" />
          <Tab label="Performance" />
          <Tab label="Training" />
          <Tab label="Plans" />
          <Tab label="Settings" />
        </Tabs>
      </AppBar>

      <Container maxWidth="lg" sx={{ py: 3, flex: 1 }}>
        {err ? (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErr(null)}>
            {err}
          </Alert>
        ) : null}

        {tab === "strategy" ? (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h2" component="h2" gutterBottom>
              Strategy
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              UX reference captures live in{" "}
              <code>tmp/screenshots/</code> (Rapsodo Session Insights + Garmin; local only, not in git). Cursor search may
              skip binary folders; use Finder or <code>ls</code> for parity checks.
            </Typography>
            <Typography variant="h3" component="h3" gutterBottom sx={{ mt: 2 }}>
              The Scoring Method (round proxies)
            </Typography>
            <Typography variant="body2" paragraph>
              ESZ (≤100 yd by end of stroke ≤ par−2) and DSZ (≤3 strokes from first in-zone;{" "}
              <strong>DSZ</strong> uses
              scorecard <strong>gross strokes</strong> on the hole vs the entry stroke from the trace when Garmin lists{" "}
              <code>holes[].strokes</code> / <code>score</code>, otherwise the shot list) use
              Garmin <strong>shotDetails</strong> when possible: <strong>geometry</strong> (end vs pin), then{" "}
              <strong>Garmin distances</strong> by shot id, then <strong>straight-hole heuristics</strong> from hole
              yardage or par defaults. See the panel below for how many holes used each tier.
            </Typography>
            {strategyOverview?.source_available && strategyOverview.esz_dsz_from_shots ? (
              <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: "action.hover" }}>
                <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                  ESZ / DSZ distance engine
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
                  v2 — multi-method (not geometry-only). Year <strong>{strategyOverview.year}</strong>
                  {typeof (strategyOverview.esz_dsz_from_shots as { shot_detail_blocks?: unknown })
                    .shot_detail_blocks === "number" ? (
                    <>
                      {" "}
                      · shotDetails blocks in file:{" "}
                      <strong>
                        {(strategyOverview.esz_dsz_from_shots as { shot_detail_blocks: number }).shot_detail_blocks}
                      </strong>
                    </>
                  ) : null}
                  {typeof (strategyOverview.esz_dsz_from_shots as { holes_evaluated?: unknown }).holes_evaluated ===
                  "number" ? (
                    <>
                      {" "}
                      · holes evaluated:{" "}
                      <strong>
                        {(strategyOverview.esz_dsz_from_shots as { holes_evaluated: number }).holes_evaluated}
                      </strong>
                    </>
                  ) : null}
                </Typography>
                <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 1 }}>
                  {(() => {
                    const m = (
                      strategyOverview.esz_dsz_from_shots as {
                        distance_to_pin_methods?: Record<string, number>;
                      }
                    ).distance_to_pin_methods;
                    const g = m?.geometry ?? 0;
                    const o = m?.orientation ?? 0;
                    const s = m?.orientation_starting_minus_shot ?? 0;
                    const h = m?.heuristic_straight_hole ?? 0;
                    return (
                      <>
                        <Chip size="small" variant="outlined" label={`Geometry: ${g}`} />
                        <Chip size="small" variant="outlined" label={`remainingDistance: ${o}`} />
                        <Chip size="small" variant="outlined" label={`start − shot: ${s}`} />
                        <Chip size="small" variant="outlined" label={`Heuristic: ${h}`} />
                      </>
                    );
                  })()}
                </Stack>
                <Typography variant="caption" color="text.secondary" display="block">
                  First scoring-zone hit per hole is counted in exactly one chip. If your export is rich in lat/lon,
                  Geometry usually dominates.
                </Typography>
              </Paper>
            ) : null}
            {strategyOverview?.source_available && eszDataModel ? (
              <Accordion disableGutters sx={{ mb: 2 }}>
                <AccordionSummary>
                  <Typography variant="subtitle2">Garmin JSON → ESZ / DSZ (data model)</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Stack spacing={1}>
                    {Object.entries(eszDataModel).map(([k, v]) => (
                      <Typography key={k} variant="body2" color="text.secondary" component="div">
                        <strong>{k}</strong>: {typeof v === "string" ? v : JSON.stringify(v)}
                      </Typography>
                    ))}
                  </Stack>
                </AccordionDetails>
              </Accordion>
            ) : null}
            {strategyOverview?.source_available && strategyOverview.esz_dsz_from_shots ? (
              typeof (strategyOverview.esz_dsz_from_shots as { holes_evaluated?: unknown }).holes_evaluated ===
                "number" &&
              (strategyOverview.esz_dsz_from_shots as { holes_evaluated: number }).holes_evaluated > 0 ? (
                <Alert severity="success" sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                    ESZ / DSZ results ({strategyOverview.year})
                  </Typography>
                  <Typography variant="body2" component="div">
                    Holes evaluated:{" "}
                    <strong>
                      {(strategyOverview.esz_dsz_from_shots as { holes_evaluated: number }).holes_evaluated}
                    </strong>
                    {typeof (strategyOverview.esz_dsz_from_shots as { esz_pct?: unknown }).esz_pct === "number" ? (
                      <>
                        {" "}
                        · ESZ (≤100 yd by end of stroke ≤ par−2):{" "}
                        <strong>
                          {(strategyOverview.esz_dsz_from_shots as { esz_pct: number }).esz_pct.toFixed(1)}%
                        </strong>
                      </>
                    ) : null}
                    {typeof (strategyOverview.esz_dsz_from_shots as { dsz_pct?: unknown }).dsz_pct === "number" ? (
                      <>
                        {" "}
                        · DSZ (≤3 strokes from first in-zone through finish; uses scorecard gross on the hole when listed, else shot trace):{" "}
                        <strong>
                          {(strategyOverview.esz_dsz_from_shots as { dsz_pct: number }).dsz_pct.toFixed(1)}%
                        </strong>
                      </>
                    ) : null}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                    {(strategyOverview.esz_dsz_from_shots as { note?: string }).note}
                  </Typography>
                  {(() => {
                    const m = (
                      strategyOverview.esz_dsz_from_shots as {
                        distance_to_pin_methods?: Record<string, number>;
                      }
                    ).distance_to_pin_methods;
                    if (!m) return null;
                    const ori = m.orientation ?? 0;
                    const osm = m.orientation_starting_minus_shot ?? 0;
                    const heu = m.heuristic_straight_hole ?? 0;
                    if (ori + osm + heu === 0) return null;
                    return (
                      <Typography variant="caption" color="warning.main" display="block" sx={{ mt: 1 }}>
                        {ori > 0 ? `${ori} hole(s) used Garmin remainingDistance (shot id). ` : null}
                        {osm > 0 ? `${osm} hole(s) used startingDistanceToHole − shot length. ` : null}
                        {heu > 0
                          ? `${heu} hole(s) used straight-line cumulative meters heuristic (see API heuristic_note).`
                          : null}
                      </Typography>
                    );
                  })()}
                </Alert>
              ) : (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                    ESZ / DSZ — no holes matched yet
                  </Typography>
                  <Typography variant="body2" paragraph sx={{ mb: 1 }}>
                    {(strategyOverview.esz_dsz_from_shots as { availability_hint?: string }).availability_hint ??
                      "No matching holes. Check calendar year in Settings, and that your Garmin export includes shotDetails with pin + end locations and holePars."}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" component="div">
                    Shot detail blocks in file:{" "}
                    <strong>
                      {String(
                        (strategyOverview.esz_dsz_from_shots as { shot_detail_blocks?: number })
                          .shot_detail_blocks ?? "—",
                      )}
                    </strong>
                    {" · "}
                    Year filter: <strong>{strategyOverview.year}</strong>
                  </Typography>
                  {(() => {
                    const diag = (
                      strategyOverview.esz_dsz_from_shots as { diagnostics?: Record<string, number> }
                    ).diagnostics;
                    if (!diag || Object.keys(diag).length === 0) return null;
                    const lines = Object.entries(diag)
                      .filter(([, v]) => v > 0)
                      .map(([k, v]) => `${k}: ${v}`);
                    if (lines.length === 0) return null;
                    return (
                      <Typography
                        variant="caption"
                        component="pre"
                        sx={{ mt: 1, display: "block", whiteSpace: "pre-wrap", fontFamily: "monospace" }}
                      >
                        {lines.join("\n")}
                      </Typography>
                    );
                  })()}
                </Alert>
              )
            ) : null}
            {strategyOverview ? (
              <Stack spacing={2} sx={{ mb: 3 }}>
                {typeof strategyOverview.scoring_method.esz_dsz_note === "string" ? (
                  <Alert severity="info">{strategyOverview.scoring_method.esz_dsz_note}</Alert>
                ) : null}
                {!strategyOverview.source_available ? (
                  <Alert severity="warning">
                    {strategyOverview.reason ?? "Garmin export not available."} Configure{" "}
                    <code>GOLF_GARMIN_JSON</code> for scorecard-backed tiles.
                  </Alert>
                ) : null}
                <Stack direction={{ xs: "column", md: "row" }} spacing={2} flexWrap="wrap" useFlexGap>
                  {(
                    [
                      ["proxy_avoid_big_numbers", "Avoid big numbers", "pct_holes"],
                      ["proxy_penalties", "Penalties", "pct_holes"],
                      ["proxy_fairway", "Fairway (tee line)", "pct_hit"],
                      ["proxy_putting_load", "Putting load", "putts_per_hole"],
                    ] as const
                  ).map(([key, title, metricKey]) => {
                    const block = asRecord(strategyOverview.scoring_method[key]);
                    if (!block) return null;
                    const sub = typeof block.label === "string" ? block.label : "";
                    const raw = block[metricKey];
                    const headline =
                      metricKey === "putts_per_hole" && typeof raw === "number"
                        ? raw.toFixed(2)
                        : typeof raw === "number"
                          ? metricKey.startsWith("pct")
                            ? fmtPct(raw)
                            : raw.toFixed(1)
                          : "—";
                    return (
                      <Paper key={key} variant="outlined" sx={{ p: 2, flex: "1 1 200px", minWidth: 200 }}>
                        <Typography variant="subtitle2" fontWeight={600}>
                          {title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                          {sub}
                        </Typography>
                        <Typography variant="h5" component="div">
                          {headline}
                          {metricKey === "putts_per_hole" ? (
                            <Typography component="div" variant="caption" color="text.secondary">
                              putts / hole (holes with putt counts)
                            </Typography>
                          ) : null}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" component="div">
                          {key === "proxy_avoid_big_numbers" &&
                          typeof block.holes_ge7 === "number" &&
                          typeof block.holes_tracked === "number"
                            ? `${block.holes_ge7} holes ≥7 / ${block.holes_tracked} tracked`
                            : null}
                          {key === "proxy_penalties" &&
                          typeof block.penalty_holes === "number" &&
                          typeof block.holes_tracked === "number"
                            ? `${block.penalty_holes} penalty holes / ${block.holes_tracked} tracked`
                            : null}
                          {key === "proxy_fairway" &&
                          typeof block.fairway_hit === "number" &&
                          typeof block.fairway_decided === "number"
                            ? `${block.fairway_hit} HIT / ${block.fairway_decided} decided`
                            : null}
                          {key === "proxy_putting_load" &&
                          typeof block.total_putts === "number" &&
                          typeof block.holes_with_putts === "number"
                            ? `${block.total_putts} putts on ${block.holes_with_putts} holes`
                            : null}
                        </Typography>
                      </Paper>
                    );
                  })}
                </Stack>
                {(() => {
                  const sf = asRecord(strategyOverview.scoring_method.stableford);
                  if (!sf || (sf.rounds_with_points as number | undefined) === 0) return null;
                  return (
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      Stableford (when points exist in export): mean{" "}
                      <strong>
                        {typeof sf.mean_points === "number" ? (sf.mean_points as number).toFixed(2) : "—"}
                      </strong>{" "}
                      over <strong>{String(sf.rounds_with_points)}</strong> rounds.
                    </Typography>
                  );
                })()}
                {strategyOverview.scorecards.length > 0 ? (
                  <>
                    <Typography variant="h3" component="h3" gutterBottom>
                      Garmin scorecards ({strategyOverview.year})
                    </Typography>
                    <TableContainer sx={{ mb: 3 }}>
                      <Table size="small" stickyHeader>
                        <TableHead>
                          <TableRow>
                            <TableCell>Date</TableCell>
                            <TableCell>Course</TableCell>
                            <TableCell align="right">Strokes</TableCell>
                            <TableCell align="right">Holes</TableCell>
                            <TableCell align="right">Putts Σ</TableCell>
                            <TableCell align="right">FW %</TableCell>
                            <TableCell align="right">Pen holes</TableCell>
                            <TableCell align="right">≥7</TableCell>
                            <TableCell align="right">ESZ holes</TableCell>
                            <TableCell align="right">ESZ %</TableCell>
                            <TableCell align="right">DSZ %</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {strategyOverview.scorecards.map((sc, idx) => {
                            const fw =
                              sc.fairway_decided > 0
                                ? (100 * sc.fairway_hit) / sc.fairway_decided
                                : null;
                            const er = sc.scorecard_id
                              ? eszByRoundMap.get(String(sc.scorecard_id).trim())
                              : undefined;
                            const hev = er && typeof er.holes_evaluated === "number" ? er.holes_evaluated : null;
                            const eszP = er && typeof er.esz_pct === "number" ? (er.esz_pct as number) : null;
                            const dszP = er && typeof er.dsz_pct === "number" ? (er.dsz_pct as number) : null;
                            return (
                              <TableRow key={String(sc.scorecard_id ?? sc.started_at ?? idx)} hover>
                                <TableCell>{sc.started_at?.slice(0, 10) ?? "—"}</TableCell>
                                <TableCell>{sc.course_name ?? "—"}</TableCell>
                                <TableCell align="right">{sc.strokes ?? "—"}</TableCell>
                                <TableCell align="right">{sc.holes_completed ?? "—"}</TableCell>
                                <TableCell align="right">{sc.total_putts_holes}</TableCell>
                                <TableCell align="right">{fw != null ? fmtPct(fw) : "—"}</TableCell>
                                <TableCell align="right">{sc.penalty_holes}</TableCell>
                                <TableCell align="right">{sc.blowup_holes_ge7}</TableCell>
                                <TableCell align="right">{hev != null ? hev : "—"}</TableCell>
                                <TableCell align="right">{eszP != null ? `${eszP.toFixed(1)}%` : "—"}</TableCell>
                                <TableCell align="right">{dszP != null ? `${dszP.toFixed(1)}%` : "—"}</TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </>
                ) : null}
              </Stack>
            ) : (
              <Typography color="text.secondary">Loading…</Typography>
            )}
            {strategyTrendSeries.length > 0 ? (
              <>
                <Divider sx={{ my: 2 }} />
                <Typography variant="h3" component="h3" gutterBottom>
                  Round-by-round trends
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph sx={{ maxWidth: 720 }}>
                  Same rounds as the Garmin scorecards table, oldest → newest. Choose metrics below (defaults: all
                  percentages). Counts use the <strong>right Y-axis</strong> when mixed with a percentage; otherwise a
                  single axis.
                </Typography>
                <FormControl size="small" sx={{ minWidth: 280, maxWidth: "100%", mb: 2 }}>
                  <InputLabel id="strategy-chart-metrics-label">Metrics</InputLabel>
                  <Select<string[]>
                    labelId="strategy-chart-metrics-label"
                    multiple
                    value={strategyChartMetrics}
                    onChange={onStrategyChartMetricsChange}
                    label="Metrics"
                    renderValue={(selected) =>
                      selected
                        .map((id) => STRATEGY_CHART_METRICS.find((m) => m.id === id)?.label ?? id)
                        .join(" · ")
                    }
                  >
                    <ListSubheader disableSticky>Percent</ListSubheader>
                    {STRATEGY_CHART_METRICS.filter((m) => m.kind === "percent").map((m) => (
                      <MenuItem key={m.id} value={m.id}>
                        {m.label}
                      </MenuItem>
                    ))}
                    <ListSubheader disableSticky>Counts</ListSubheader>
                    {STRATEGY_CHART_METRICS.filter((m) => m.kind === "count").map((m) => (
                      <MenuItem key={m.id} value={m.id}>
                        {m.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                {(() => {
                  const defs = STRATEGY_CHART_METRICS.filter((m) => strategyChartMetrics.includes(m.id));
                  const pctDefs = defs.filter((m) => m.kind === "percent");
                  const cntDefs = defs.filter((m) => m.kind === "count");
                  const dual = pctDefs.length > 0 && cntDefs.length > 0;
                  return (
                    <Box sx={{ width: "100%", height: 420 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart
                          data={strategyTrendSeries}
                          margin={{ top: 12, right: dual ? 28 : 12, left: 4, bottom: 56 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                          <XAxis
                            dataKey="xTick"
                            tick={{ fontSize: 10 }}
                            angle={-32}
                            textAnchor="end"
                            height={60}
                            interval="preserveStartEnd"
                          />
                          {dual ? (
                            <>
                              <YAxis
                                yAxisId="pct"
                                orientation="left"
                                domain={[0, "auto"]}
                                tickFormatter={(v) => `${Number(v).toFixed(0)}%`}
                                width={40}
                              />
                              <YAxis yAxisId="cnt" orientation="right" domain={[0, "auto"]} width={36} />
                            </>
                          ) : pctDefs.length > 0 ? (
                            <YAxis
                              yAxisId="main"
                              orientation="left"
                              domain={[0, "auto"]}
                              tickFormatter={(v) => `${Number(v).toFixed(0)}%`}
                              width={44}
                            />
                          ) : (
                            <YAxis yAxisId="main" orientation="left" domain={[0, "auto"]} width={40} />
                          )}
                          <Tooltip
                            formatter={(value: number | string, name: string) => {
                              const meta = STRATEGY_CHART_METRICS.find((m) => m.label === name);
                              const v = typeof value === "number" ? value : Number(value);
                              if (Number.isNaN(v)) return ["—", name];
                              return [meta?.kind === "percent" ? `${v.toFixed(1)}%` : `${v}`, name];
                            }}
                          />
                          <Legend wrapperStyle={{ fontSize: 12 }} />
                          {pctDefs.map((m) => (
                            <Line
                              key={m.id}
                              yAxisId={dual ? "pct" : "main"}
                              type="monotone"
                              dataKey={m.dataKey as string}
                              name={m.label}
                              stroke={strategyMetricColor(m.id)}
                              strokeWidth={2}
                              dot={{ r: 2 }}
                              connectNulls
                              isAnimationActive={false}
                            />
                          ))}
                          {cntDefs.map((m) => (
                            <Line
                              key={m.id}
                              yAxisId={dual ? "cnt" : "main"}
                              type="monotone"
                              dataKey={m.dataKey as string}
                              name={m.label}
                              stroke={strategyMetricColor(m.id)}
                              strokeWidth={2}
                              dot={{ r: 2 }}
                              strokeDasharray="6 3"
                              connectNulls
                              isAnimationActive={false}
                            />
                          ))}
                        </LineChart>
                      </ResponsiveContainer>
                    </Box>
                  );
                })()}
              </>
            ) : null}
          </Paper>
        ) : null}

        {tab === "performance" ? (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h2" component="h2" gutterBottom>
              Performance
            </Typography>
            {roundSummary ? (
              <Typography variant="body1" paragraph>
                Rounds in window: <strong>{String(roundSummary.rounds_in_window)}</strong>
                {roundSummary.mean_score_relative_to_par != null ? (
                  <>
                    {" "}
                    · Mean vs par:{" "}
                    <strong>
                      {Number(roundSummary.mean_score_relative_to_par) >= 0 ? "+" : ""}
                      {Number(roundSummary.mean_score_relative_to_par).toFixed(2)}
                    </strong>
                  </>
                ) : null}
              </Typography>
            ) : null}
            <Divider sx={{ my: 2 }} />
            <Typography variant="h3" component="h3" gutterBottom>
              Garmin rounds (export, {year})
            </Typography>
            {perfBundle == null ? (
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                Loading…
              </Typography>
            ) : !perfBundle.available ? (
              <Alert severity="warning" sx={{ mb: 2 }}>
                Garmin bundle unavailable. Set <code>GOLF_GARMIN_JSON</code> to your export path.
              </Alert>
            ) : (
              <Stack spacing={1} sx={{ mb: 2 }}>
                <Typography variant="body2">
                  Rounds in bundle: <strong>{perfBundle.rounds_in_bundle ?? "—"}</strong>
                  {typeof perfBundle.round_rollups?.mean_strokes_per_round === "number" ? (
                    <>
                      {" "}
                      · Mean strokes/round:{" "}
                      <strong>{(perfBundle.round_rollups.mean_strokes_per_round as number).toFixed(2)}</strong>
                    </>
                  ) : null}
                  {typeof perfBundle.round_rollups?.best_strokes_round === "number" ? (
                    <>
                      {" "}
                      · Best round: <strong>{perfBundle.round_rollups.best_strokes_round as number}</strong>
                    </>
                  ) : null}
                </Typography>
                {perfBundle.round_rollups?.score_types &&
                typeof perfBundle.round_rollups.score_types === "object" ? (
                  <Typography variant="caption" color="text.secondary" component="div">
                    Score types:{" "}
                    {JSON.stringify(perfBundle.round_rollups.score_types as Record<string, unknown>)}
                  </Typography>
                ) : null}
              </Stack>
            )}
            <Typography variant="h3" component="h3" gutterBottom>
              Garmin last-10 samples (SG vs handicap cohort)
            </Typography>
            {perfBundle?.available && sgRows.length > 0 ? (
              <Stack spacing={2} sx={{ mb: 2 }}>
                <ToggleButtonGroup
                  size="small"
                  exclusive
                  value={sgAgg}
                  onChange={(_, v) => v && setSgAgg(v)}
                  aria-label="SG aggregation"
                >
                  <ToggleButton value="mean">Mean SG</ToggleButton>
                  <ToggleButton value="sum">Sum SG</ToggleButton>
                </ToggleButtonGroup>
                <Box sx={{ width: "100%", height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={sgRows} margin={{ top: 8, right: 16, left: 8, bottom: 56 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                      <XAxis dataKey="name" angle={-20} textAnchor="end" height={52} interval={0} />
                      <YAxis stroke={theme.palette.text.secondary} label={{ value: "Strokes gained", angle: -90, position: "insideLeft" }} />
                      <Tooltip formatter={(v: number) => v.toFixed(3)} />
                      <Legend />
                      <Bar
                        dataKey={sgAgg}
                        name={sgAgg === "mean" ? "Mean strokes gained" : "Sum strokes gained"}
                        fill={theme.palette.primary.main}
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </Box>
              </Stack>
            ) : perfBundle?.available && perfBundle.last10 && Object.keys(perfBundle.last10).length > 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Last-10 SG summary has no per-category rows (only overall or empty).
              </Typography>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No last-10 SG blocks in export for this filter, or file missing.
              </Typography>
            )}
          </Paper>
        ) : null}

        {tab === "training" ? (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h2" component="h2" gutterBottom>
              Training
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Rapsodo LM cohort · Year <strong>{year}</strong> (change in Settings). Ratio = mean
              |offline| / mean carry; FLAG uses SD rules from the analysis plan.
            </Typography>
            <TableContainer sx={{ mb: 3 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Club</TableCell>
                    <TableCell align="right">n</TableCell>
                    <TableCell align="right">Mean carry</TableCell>
                    <TableCell align="right">Mean |off|</TableCell>
                    <TableCell align="right">Ratio (mean)</TableCell>
                    <TableCell align="right">Lat/len (SD)</TableCell>
                    <TableCell align="center" />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {clubs.map((c) => (
                    <TableRow key={c.club} hover>
                      <TableCell>{c.club}</TableCell>
                      <TableCell align="right">{c.n}</TableCell>
                      <TableCell align="right">{c.mean_carry_yards?.toFixed(1) ?? "—"}</TableCell>
                      <TableCell align="right">{c.mean_abs_offline_yards?.toFixed(1) ?? "—"}</TableCell>
                      <TableCell align="right">
                        {c.dispersion_ratio_mean_abs_offline_per_carry != null
                          ? c.dispersion_ratio_mean_abs_offline_per_carry.toFixed(3)
                          : "—"}
                      </TableCell>
                      <TableCell align="right">
                        {c.lateral_to_length_ratio_sd != null
                          ? c.lateral_to_length_ratio_sd.toFixed(3)
                          : "—"}
                      </TableCell>
                      <TableCell align="center">
                        {c.needs_work ? (
                          <Chip label="FLAG" size="small" color="error" variant="outlined" />
                        ) : null}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            {trainingAnalytics && trainingAnalytics.takeaways?.length ? (
              <Box sx={{ mb: 3 }}>
                <Typography variant="h3" component="h3" gutterBottom>
                  Key takeaways
                </Typography>
                <Stack spacing={1}>
                  {trainingAnalytics.takeaways.map((t, i) => (
                    <Alert key={i} severity="info" variant="outlined" icon={false}>
                      {t}
                    </Alert>
                  ))}
                </Stack>
              </Box>
            ) : null}

            <Typography variant="h3" component="h3" gutterBottom>
              Club comparison (landing + carry by miss)
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
              Use the same labels as in your library (e.g. <code>driver</code>, <code>3w</code>). Matches
              Rapsodo Session Insights two-club view at a high level.
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }} sx={{ mb: 2 }}>
              <TextField
                size="small"
                label="Club A"
                value={compareClubA}
                onChange={(e) => setCompareClubA(e.target.value)}
                sx={{ minWidth: 140 }}
              />
              <TextField
                size="small"
                label="Club B"
                value={compareClubB}
                onChange={(e) => setCompareClubB(e.target.value)}
                sx={{ minWidth: 140 }}
              />
              <Button variant="outlined" disabled={compareBusy} onClick={() => void runClubCompare()}>
                {compareBusy ? "Loading…" : "Compare"}
              </Button>
            </Stack>
            {clubCompare?.error ? (
              <Alert severity="warning" sx={{ mb: 3 }}>
                {clubCompare.error}
              </Alert>
            ) : clubCompare && (clubCompare.club_a || clubCompare.club_b) ? (
              <TableContainer sx={{ mb: 3 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Metric</TableCell>
                      <TableCell align="right">{clubCompare.club_a?.club ?? "Club A"}</TableCell>
                      <TableCell align="right">{clubCompare.club_b?.club ?? "Club B"}</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(
                      [
                        ["Shots", (x: ClubSideCompareDetail | null) => x?.n ?? "—"],
                        ["Left %", (x) => (x ? fmtPct(x.pct_left) : "—")],
                        ["Straight %", (x) => (x ? fmtPct(x.pct_straight) : "—")],
                        ["Right %", (x) => (x ? fmtPct(x.pct_right) : "—")],
                        ["Mean carry (left)", (x) => (x?.mean_carry_yards_left != null ? x.mean_carry_yards_left.toFixed(1) : "—")],
                        ["Mean carry (straight)", (x) => (x?.mean_carry_yards_straight != null ? x.mean_carry_yards_straight.toFixed(1) : "—")],
                        ["Mean carry (right)", (x) => (x?.mean_carry_yards_right != null ? x.mean_carry_yards_right.toFixed(1) : "—")],
                        ["Mean launch °", (x) => (x?.mean_launch_angle_deg != null ? x.mean_launch_angle_deg.toFixed(1) : "—")],
                        ["Mean smash", (x) => (x?.mean_smash_factor != null ? x.mean_smash_factor.toFixed(2) : "—")],
                      ] as const
                    ).map(([label, fn]) => (
                      <TableRow key={label}>
                        <TableCell>{label}</TableCell>
                        <TableCell align="right">{String(fn(clubCompare.club_a ?? null))}</TableCell>
                        <TableCell align="right">{String(fn(clubCompare.club_b ?? null))}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : null}

            {trainingAnalytics ? (
              <>
                <Typography variant="h3" component="h3" gutterBottom sx={{ mt: 2 }}>
                  Carry distribution (p10 / p90)
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                  Mirrors Rapsodo “Distance” style bands; from LM cohort for {year}.
                </Typography>
                <TableContainer sx={{ mb: 3 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>Club</TableCell>
                        <TableCell align="right">n</TableCell>
                        <TableCell align="right">Mean</TableCell>
                        <TableCell align="right">p10</TableCell>
                        <TableCell align="right">p90</TableCell>
                        <TableCell align="right">Disp. idx</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {trainingAnalytics.carry_distribution.map((row) => (
                        <TableRow key={row.club} hover>
                          <TableCell>{row.club}</TableCell>
                          <TableCell align="right">{row.n}</TableCell>
                          <TableCell align="right">{row.mean_carry_yards.toFixed(1)}</TableCell>
                          <TableCell align="right">{row.p10_carry_yards?.toFixed(1) ?? "—"}</TableCell>
                          <TableCell align="right">{row.p90_carry_yards?.toFixed(1) ?? "—"}</TableCell>
                          <TableCell align="right">
                            {row.dispersion_index_mean_abs_per_carry != null
                              ? row.dispersion_index_mean_abs_per_carry.toFixed(3)
                              : "—"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>

                <Typography variant="h3" component="h3" gutterBottom>
                  Landing side (L / straight / R)
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                  Session Insights “Accuracy” style; straight = |offline| under band (yd).
                </Typography>
                <TableContainer sx={{ mb: 3 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>Club</TableCell>
                        <TableCell align="right">n</TableCell>
                        <TableCell align="right">Left</TableCell>
                        <TableCell align="right">Straight</TableCell>
                        <TableCell align="right">Right</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {trainingAnalytics.landing_side.map((row) => (
                        <TableRow key={row.club} hover>
                          <TableCell>{row.club}</TableCell>
                          <TableCell align="right">{row.n}</TableCell>
                          <TableCell align="right">{fmtPct(row.pct_left)}</TableCell>
                          <TableCell align="right">{fmtPct(row.pct_straight)}</TableCell>
                          <TableCell align="right">{fmtPct(row.pct_right)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>

                <Typography variant="h3" component="h3" gutterBottom>
                  Club gapping (median carry, longest first)
                </Typography>
                <TableContainer sx={{ mb: 3 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>Club</TableCell>
                        <TableCell align="right">Median yd</TableCell>
                        <TableCell align="right">Gap vs longer (above)</TableCell>
                        <TableCell>Longer club</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {trainingAnalytics.gapping.map((row) => (
                        <TableRow key={row.club} hover>
                          <TableCell>{row.club}</TableCell>
                          <TableCell align="right">{row.median_carry_yards.toFixed(1)}</TableCell>
                          <TableCell align="right">
                            {row.gap_from_previous_club_yards != null
                              ? row.gap_from_previous_club_yards.toFixed(1)
                              : "—"}
                          </TableCell>
                          <TableCell>{row.previous_club_in_order ?? "—"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>

                <Typography variant="h3" component="h3" gutterBottom>
                  Shot shape
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  {typeof trainingAnalytics.shot_shape.note === "string"
                    ? trainingAnalytics.shot_shape.note
                    : null}
                </Typography>
                <Typography variant="subtitle2" gutterBottom>
                  Offline lateral sign (three-way)
                </Typography>
                {shapeBars.length > 0 ? (
                  <Box sx={{ width: "100%", height: 220, mb: 2 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={shapeBars} layout="vertical" margin={{ top: 8, right: 16, left: 96, bottom: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                        <XAxis type="number" unit="%" domain={[0, 100]} stroke={theme.palette.text.secondary} />
                        <YAxis type="category" dataKey="name" width={88} stroke={theme.palette.text.secondary} />
                        <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
                        <Bar dataKey="pct" name="% of shots" fill={theme.palette.secondary.main} radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </Box>
                ) : null}
                {fiveWayBars.length > 0 ? (
                  <>
                    <Typography variant="subtitle2" gutterBottom>
                      Spin axis bins (Rapsodo-style five-way, n ≥ 15)
                    </Typography>
                    {(() => {
                      const fw = asRecord(trainingAnalytics.shot_shape["five_way_spin_axis"]);
                      return fw && typeof fw.note === "string" ? (
                        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                          {fw.note as string}
                        </Typography>
                      ) : null;
                    })()}
                    <Box sx={{ width: "100%", height: 260, mb: 3 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={fiveWayBars}
                          layout="vertical"
                          margin={{ top: 8, right: 16, left: 88, bottom: 8 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                          <XAxis type="number" unit="%" domain={[0, 100]} stroke={theme.palette.text.secondary} />
                          <YAxis type="category" dataKey="name" width={72} stroke={theme.palette.text.secondary} />
                          <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
                          <Bar dataKey="pct" name="% of shots" radius={[0, 4, 4, 0]}>
                            {fiveWayBars.map((entry, i) => (
                              <Cell
                                key={entry.name}
                                fill={
                                  entry.name === "Hook" || entry.name === "Slice"
                                    ? theme.palette.error.main
                                    : theme.palette.success.main
                                }
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </Box>
                  </>
                ) : null}

                <Typography variant="h3" component="h3" gutterBottom>
                  Recent shots (drill-down)
                </Typography>
                <FormGroup row sx={{ flexWrap: "wrap", gap: 0.5, mb: 1 }}>
                  {(
                    [
                      ["carry", "Carry"],
                      ["offline", "Offline"],
                      ["smash", "Smash"],
                      ["launch", "Launch °"],
                      ["ball", "Ball mph"],
                      ["spin", "Spin rpm"],
                      ["axis", "Spin axis °"],
                      ["shotIx", "Shot #"],
                      ["session", "Session"],
                    ] as const
                  ).map(([key, label]) => (
                    <FormControlLabel
                      key={key}
                      control={
                        <Checkbox
                          size="small"
                          checked={shotCols[key]}
                          onChange={(_, c) => setShotCols((s) => ({ ...s, [key]: c }))}
                        />
                      }
                      label={<Typography variant="caption">{label}</Typography>}
                    />
                  ))}
                </FormGroup>
                <TableContainer sx={{ mb: 3, maxHeight: 360 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>When</TableCell>
                        {shotCols.shotIx ? <TableCell align="right">#</TableCell> : null}
                        <TableCell>Club</TableCell>
                        {shotCols.carry ? <TableCell align="right">Carry</TableCell> : null}
                        {shotCols.offline ? <TableCell align="right">Offline</TableCell> : null}
                        {shotCols.smash ? <TableCell align="right">Smash</TableCell> : null}
                        {shotCols.launch ? <TableCell align="right">LA°</TableCell> : null}
                        {shotCols.ball ? <TableCell align="right">Ball</TableCell> : null}
                        {shotCols.spin ? <TableCell align="right">Spin</TableCell> : null}
                        {shotCols.axis ? <TableCell align="right">Axis</TableCell> : null}
                        {shotCols.session ? <TableCell>Session</TableCell> : null}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {trainingShots.map((sh) => (
                        <TableRow key={sh.shot_id} hover>
                          <TableCell>{sh.session_started_at?.slice(0, 16) ?? "—"}</TableCell>
                          {shotCols.shotIx ? (
                            <TableCell align="right">{sh.shot_index ?? "—"}</TableCell>
                          ) : null}
                          <TableCell>{sh.club ?? "—"}</TableCell>
                          {shotCols.carry ? (
                            <TableCell align="right">{sh.carry_yards?.toFixed(1) ?? "—"}</TableCell>
                          ) : null}
                          {shotCols.offline ? (
                            <TableCell align="right">{sh.offline_yards?.toFixed(1) ?? "—"}</TableCell>
                          ) : null}
                          {shotCols.smash ? (
                            <TableCell align="right">{sh.smash_factor?.toFixed(2) ?? "—"}</TableCell>
                          ) : null}
                          {shotCols.launch ? (
                            <TableCell align="right">{sh.launch_angle_deg?.toFixed(1) ?? "—"}</TableCell>
                          ) : null}
                          {shotCols.ball ? (
                            <TableCell align="right">{sh.ball_speed_mph?.toFixed(1) ?? "—"}</TableCell>
                          ) : null}
                          {shotCols.spin ? (
                            <TableCell align="right">{sh.spin_rpm != null ? Math.round(sh.spin_rpm) : "—"}</TableCell>
                          ) : null}
                          {shotCols.axis ? (
                            <TableCell align="right">{sh.spin_axis_deg?.toFixed(1) ?? "—"}</TableCell>
                          ) : null}
                          {shotCols.session ? (
                            <TableCell sx={{ maxWidth: 180 }} noWrap title={sh.session_title ?? ""}>
                              {sh.session_title ?? sh.session_id}
                            </TableCell>
                          ) : null}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </>
            ) : null}

            <Typography variant="h3" component="h3" gutterBottom>
              Carry by club
            </Typography>
            <Box sx={{ width: "100%", height: 320, mb: 3 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                  <XAxis dataKey="name" angle={-25} textAnchor="end" height={56} interval={0} />
                  <YAxis
                    label={{ value: "yd", angle: -90, position: "insideLeft" }}
                    stroke={theme.palette.text.secondary}
                  />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="carry" name="Mean carry (yd)" fill={theme.palette.primary.main} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Box>

            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }} sx={{ mb: 1 }}>
              <Typography variant="h3" component="h3" sx={{ flex: 1 }}>
                Scatter: carry vs offline
              </Typography>
              <ToggleButtonGroup
                size="small"
                exclusive
                value={scatterColorBy}
                onChange={(_, v) => v && setScatterColorBy(v)}
                aria-label="Scatter colour"
              >
                <ToggleButton value="session">Colour by session</ToggleButton>
                <ToggleButton value="club">Colour by club</ToggleButton>
              </ToggleButtonGroup>
            </Stack>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
              Hover shows carry, offline, club, and session. Legend lists up to 20 {scatterColorBy === "session" ? "sessions" : "clubs"}.
            </Typography>
            <Box sx={{ width: "100%", height: 360 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                  <XAxis type="number" dataKey="x" name="Carry" unit=" yd" stroke={theme.palette.text.secondary} />
                  <YAxis type="number" dataKey="y" name="Offline" unit=" yd" stroke={theme.palette.text.secondary} />
                  <Tooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.[0]) return null;
                      const p = payload[0].payload as {
                        x: number;
                        y: number;
                        club: string;
                        label: string | number;
                      };
                      return (
                        <Paper variant="outlined" sx={{ px: 1.5, py: 1 }}>
                          <Typography variant="caption" display="block">
                            Carry {p.x.toFixed(1)} yd · Offline {p.y.toFixed(1)} yd
                          </Typography>
                          <Typography variant="caption" display="block">
                            Club: {p.club || "—"}
                          </Typography>
                          <Typography variant="caption" display="block">
                            Session: {p.label}
                          </Typography>
                        </Paper>
                      );
                    }}
                  />
                  <Legend
                    verticalAlign="top"
                    height={scatterLegendKeys.length > 12 ? 72 : 36}
                    payload={scatterLegendKeys.slice(0, 20).map((k) => ({
                      id: k,
                      value: scatterColorBy === "session" ? `Session ${k}` : k,
                      type: "square" as const,
                      color: scatterColorFn(k),
                    }))}
                  />
                  <Scatter name="Shots" data={scatterPlotted}>
                    {scatterPlotted.map((entry, i) => (
                      <Cell key={i} fill={scatterColorFn(entry.colorKey)} />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </Box>
            {scatterLegendKeys.length > 20 ? (
              <Typography variant="caption" color="text.secondary">
                +{scatterLegendKeys.length - 20} more {scatterColorBy === "session" ? "sessions" : "clubs"} not shown in legend
              </Typography>
            ) : null}
          </Paper>
        ) : null}

        {tab === "plans" ? (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h2" component="h2" gutterBottom>
              Plans
            </Typography>
            {plan ? (
              <Stack spacing={2}>
                <Typography variant="body1">
                  <strong>{plan.sessions_planned}</strong> sessions · year{" "}
                  <strong>{plan.calendar_year}</strong>
                </Typography>
                <Typography variant="h3" component="h3">
                  Insights
                </Typography>
                <List dense disablePadding>
                  {plan.insights.map((s, i) => (
                    <ListItem key={i} sx={{ py: 0.5, alignItems: "flex-start" }}>
                      <ListItemText primary={s} />
                    </ListItem>
                  ))}
                </List>
                <Divider />
                <Typography variant="h3" component="h3">
                  Training block
                </Typography>
                <Stack component="ol" spacing={2} sx={{ m: 0, pl: 3 }}>
                  {plan.sessions.map((s) => (
                    <Box component="li" key={s.index} sx={{ display: "list-item" }}>
                      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 0.5 }}>
                        <Typography variant="subtitle1" component="span" fontWeight={600}>
                          {s.title}
                        </Typography>
                        <Chip label={s.priority_tag} size="small" color="primary" variant="filled" />
                      </Stack>
                      <Typography variant="body2" color="text.secondary">
                        {s.description}
                      </Typography>
                    </Box>
                  ))}
                </Stack>
              </Stack>
            ) : (
              <Typography color="text.secondary">Loading…</Typography>
            )}
          </Paper>
        ) : null}

        {tab === "settings" ? (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h2" component="h2" gutterBottom>
              Settings
            </Typography>
            {meta ? (
              <Typography variant="body2" color="text.secondary" paragraph>
                Library <code>{meta.library_db}</code> — {meta.golf_rounds} rounds,{" "}
                {meta.range_shots} range shots
              </Typography>
            ) : null}
            {settings ? (
              <Stack spacing={2} sx={{ maxWidth: 480 }}>
                <TextField
                  label="Max rounds (window)"
                  type="number"
                  fullWidth
                  value={settingsDirty.maxRounds ?? settings.maxRounds}
                  onChange={(e) =>
                    setSettingsDirty((d) => ({ ...d, maxRounds: Number(e.target.value) }))
                  }
                />
                <TextField
                  label="Max practice sessions"
                  type="number"
                  fullWidth
                  value={settingsDirty.maxPracticeSessions ?? settings.maxPracticeSessions}
                  onChange={(e) =>
                    setSettingsDirty((d) => ({
                      ...d,
                      maxPracticeSessions: Number(e.target.value),
                    }))
                  }
                />
                <TextField
                  label="Max age (days)"
                  type="number"
                  fullWidth
                  value={settingsDirty.maxAgeDays ?? settings.maxAgeDays}
                  onChange={(e) =>
                    setSettingsDirty((d) => ({ ...d, maxAgeDays: Number(e.target.value) }))
                  }
                />
                <TextField
                  label="Calendar year (training / plans)"
                  type="number"
                  fullWidth
                  value={settingsDirty.calendarYear ?? settings.calendarYear}
                  onChange={(e) =>
                    setSettingsDirty((d) => ({ ...d, calendarYear: Number(e.target.value) }))
                  }
                />
                <TextField
                  label="Training block session count"
                  type="number"
                  fullWidth
                  value={settingsDirty.trainingBlockSessions ?? settings.trainingBlockSessions}
                  onChange={(e) =>
                    setSettingsDirty((d) => ({
                      ...d,
                      trainingBlockSessions: Number(e.target.value),
                    }))
                  }
                />
                <Button variant="contained" disabled={saving} onClick={() => void saveSettingsForm()}>
                  {saving ? "Saving…" : "Save settings"}
                </Button>
                <Typography variant="caption" color="text.secondary" display="block">
                  Secrets (bearer tokens) are not in this UI yet; configure the API host with env
                  vars per tech spec.
                </Typography>
              </Stack>
            ) : (
              <Typography color="text.secondary">Loading…</Typography>
            )}
          </Paper>
        ) : null}

        <Box sx={{ mt: 4, pb: 2 }}>
          <Typography variant="caption" color="text.secondary" display="block">
            Dev: run <code>uv run golf-ingest dashboard-api</code> then <code>npm run dev</code> in{" "}
            <code>dashboard/</code>. Guidelines:{" "}
            <Link href="https://m2.material.io/" target="_blank" rel="noopener noreferrer">
              Material Design
            </Link>{" "}
            · Components:{" "}
            <Link href="https://mui.com/material-ui/" target="_blank" rel="noopener noreferrer">
              MUI
            </Link>
          </Typography>
        </Box>
      </Container>
    </Box>
  );
}
