import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Alert from "@mui/material/Alert";
import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Breadcrumbs from "@mui/material/Breadcrumbs";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import Container from "@mui/material/Container";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import FormControl from "@mui/material/FormControl";
import Grid from "@mui/material/Grid";
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
import { apiGet, apiPatch, apiPost, apiPut } from "./api";
import HomeView, { type AppMode } from "./HomeView";
import OnCourseView from "./OnCourseView";
import DrillsView from "./DrillsView";
import DataSourcesSettings from "./DataSourcesSettings";
import PlaybookEditor from "./PlaybookEditor";

const TAB_KEYS = ["plans", "strategy", "performance", "range", "settings", "reference"] as const;
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

interface RangeClubCatalogRow {
  club: string;
  n: number;
}

interface Settings {
  maxRounds: number;
  maxPracticeSessions: number;
  maxAgeDays: number;
  calendarYear: number;
  trainingBlockSessions: number;
  troubleMinAvgStablefordPoints: number;
  stablefordColorGreenMin: number;
  stablefordColorYellowMin: number;
  avgPuttsHighThreshold: number;
  trainingDispersionRatioFlag: number;
  excludedTrainingClubs: string[];
}

interface PlanSession {
  index: number;
  title: string;
  description: string;
  priority_tag: string;
  focus?: string;
  drill_id: string;
  drill_title: string;
  drill_category?: string;
  expected_duration_minutes?: number | null;
  success_target?: string;
  rapsodo_mode_label?: string;
  default_aim?: string;
  suggested_club?: string | null;
  completed_at?: string | null;
  linked_session_id?: string | null;
}

interface PlanResponse {
  block_id: string;
  generated_at: string;
  calendar_year: number;
  sessions_planned: number;
  coach_summary: string;
  insights: string[];
  flagged_clubs: string[];
  sessions: PlanSession[];
  all_complete: boolean;
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
  stableford_zero_point_holes: number;
  stableford_holes_tracked: number;
  mean_strokes_per_hole: number | null;
}

type StrategyTrendKind = "percent" | "rate" | "count";

function holesPlayed(sc: GarminScorecardRow): number | null {
  const h = sc.holes_completed;
  return h != null && h > 0 ? h : null;
}

function perHolePlayed(total: number | null | undefined, holes: number | null): number | null {
  if (total == null || holes == null || holes <= 0) return null;
  return total / holes;
}

function pctOfHolesPlayed(count: number, holes: number | null): number | null {
  if (holes == null || holes <= 0) return null;
  return (100 * count) / holes;
}

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
  putts_per_hole: number | null;
  penalty_holes_pct: number | null;
  stableford_zero_pct: number | null;
  stableford_pts_per_hole: number | null;
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

const STRATEGY_CHART_METRICS_FALLBACK: StrategyChartMetric[] = [
  { id: "fw_pct", label: "Fairway %", kind: "percent", dataKey: "fw_pct" },
  { id: "esz_pct", label: "ESZ %", kind: "percent", dataKey: "esz_pct" },
  { id: "dsz_pct", label: "DSZ %", kind: "percent", dataKey: "dsz_pct" },
  { id: "strokes", label: "Strokes", kind: "count", dataKey: "strokes" },
  { id: "holes_completed", label: "Holes scored", kind: "count", dataKey: "holes_completed" },
  { id: "putts_per_hole", label: "Putts / hole played", kind: "rate", dataKey: "putts_per_hole" },
  { id: "penalty_holes_pct", label: "Penalty holes %", kind: "percent", dataKey: "penalty_holes_pct" },
  { id: "stableford_zero_pct", label: "0-pt holes %", kind: "percent", dataKey: "stableford_zero_pct" },
  {
    id: "stableford_pts_per_hole",
    label: "Stableford pts / hole",
    kind: "rate",
    dataKey: "stableford_pts_per_hole",
  },
  { id: "esz_holes_eval", label: "ESZ holes (evaluated)", kind: "count", dataKey: "esz_holes_eval" },
  { id: "dsz_zone_holes", label: "DSZ holes (in zone)", kind: "count", dataKey: "dsz_zone_holes" },
  { id: "esz_success_holes", label: "ESZ success holes", kind: "count", dataKey: "esz_success_holes" },
  { id: "dsz_success_holes", label: "DSZ success holes", kind: "count", dataKey: "dsz_success_holes" },
  { id: "mean_spi", label: "Mean strokes / hole", kind: "count", dataKey: "mean_strokes_per_hole" },
];

const DEFAULT_STRATEGY_CHART_METRIC_IDS = STRATEGY_CHART_METRICS_FALLBACK.filter((m) => m.kind === "percent").map(
  (m) => m.id,
);

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
    const played = holesPlayed(sc);
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
      putts_per_hole: perHolePlayed(sc.total_putts_holes, played),
      penalty_holes_pct: pctOfHolesPlayed(sc.penalty_holes, played),
      stableford_zero_pct: pctOfHolesPlayed(sc.stableford_zero_point_holes, played),
      stableford_pts_per_hole: perHolePlayed(sc.stableford_points, played),
      esz_holes_eval: typeof er?.holes_evaluated === "number" ? (er.holes_evaluated as number) : null,
      dsz_zone_holes:
        typeof er?.dsz_holes_with_zone_entry === "number" ? (er.dsz_holes_with_zone_entry as number) : null,
      esz_success_holes: typeof er?.esz_success_holes === "number" ? (er.esz_success_holes as number) : null,
      dsz_success_holes: typeof er?.dsz_success_holes === "number" ? (er.dsz_success_holes as number) : null,
      mean_strokes_per_hole: sc.mean_strokes_per_hole ?? null,
    };
  });
}

function strategyMetricColor(metricId: string, defs: StrategyChartMetric[]): string {
  const ix = defs.findIndex((m) => m.id === metricId);
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

type StrategySubview = "overview" | "courses" | "course";

interface MetricsReferenceResponse {
  version: number;
  year: number;
  constants: Record<string, number>;
  scoring_zone: {
    title: string;
    esz: { title: string; definition: string; calculation: string };
    dsz: { title: string; definition: string; calculation: string };
  };
  proxy_tiles: Array<{
    key: string;
    title: string;
    label: string;
    metric: string;
    calculation: string;
    direction: string;
  }>;
  entry_distance: {
    title: string;
    band_note: string;
    columns: Array<{ id: string; title: string; calculation: string }>;
    data_quality: Record<string, string>;
  };
  trends: {
    note: string;
    metrics: Array<{
      id: string;
      label: string;
      kind: "percent" | "rate" | "count";
      data_key: string;
      calculation: string;
    }>;
    default_metric_ids: string[];
  };
  esz_dsz_data_model: Record<string, unknown>;
  data_sources: { primary: string; distance_tiers: unknown; caveat: string };
  engine_snapshot?: Record<string, unknown>;
}

interface CourseListRow {
  course_slug: string;
  course_name: string;
  rounds_count: number;
  avg_gross: number | null;
  partial_rounds_count?: number;
  avg_gross_note?: string | null;
  worst_hole_numbers: number[];
  esz_pct: number | null;
  penalty_hole_pct: number | null;
  course_coach_summary: string;
}

interface HoleCoachSection {
  title: string;
  body: string;
}

interface HoleCoach {
  headline: string;
  sections: HoleCoachSection[];
  confidence_note: string;
}

interface CourseScoringRates {
  sample_plays: number;
  esz_evaluated?: number;
  dsz_eligible?: number;
  esz_pct: number | null;
  dsz_pct: number | null;
  avg_putts: number | null;
  avg_stableford_points: number | null;
}

interface CourseParScoringRow extends CourseScoringRates {
  par: number;
  diff_vs_course_overall_pct?: Record<string, number | null | undefined>;
}

interface CourseScoringStats {
  overall: CourseScoringRates;
  by_par: Record<string, CourseParScoringRow>;
}

interface HoleMetricCompare {
  value: number;
  diff_vs_course_overall_pct?: number | null;
  diff_vs_par_on_course_pct?: number | null;
}

interface HoleCompare {
  metrics: Record<string, HoleMetricCompare>;
  lower_is_better?: string[];
}

interface CourseHoleAgg {
  hole_number: number;
  stroke_index: number | null;
  plays_count: number;
  par: number | null;
  yardage_yards: number | null;
  avg_score: number | null;
  avg_vs_par: number | null;
  scores: number[];
  avg_putts: number | null;
  putts_tracked_plays: number;
  penalty_count: number;
  penalty_rate: number | null;
  blowup_count: number;
  fairway_hit_pct: number | null;
  esz_evaluated_count: number;
  esz_success_rate: number | null;
  esz_miss_rate: number | null;
  dsz_eligible_count: number;
  dsz_success_rate: number | null;
  avg_stableford_points: number | null;
  stableford_tracked_plays: number;
  trouble_hole: boolean;
  trouble_reasons: string[];
  trouble_min_avg_stableford?: number;
  compare?: HoleCompare | null;
  coach: HoleCoach;
}

interface CourseDetailResponse {
  source_available?: boolean;
  found?: boolean;
  year?: number;
  course_slug: string;
  course_name: string;
  rounds_count: number;
  avg_gross: number | null;
  course_coach_summary: string;
  scoring_stats?: CourseScoringStats;
  holes: CourseHoleAgg[];
  partial_rounds_count?: number;
  avg_gross_note?: string | null;
  round_history: {
    scorecard_id: string;
    started_at: string | null;
    strokes: number | null;
    gross_raw?: number | null;
    gross_net_18?: number | null;
    gross_actual?: number | null;
    gross_estimated_18?: number | null;
    is_partial?: boolean;
    holes_scored?: number;
    holes_capped?: number;
    leak_holes: number[];
  }[];
}

interface SgRatingRow {
  stat_shot_type: string;
  label: string;
  player_strokes_gained: number | null;
  group_strokes_gained: number | null;
  player_rating?: number | null;
  group_rating?: number | null;
  trend?: string | null;
}

interface PerfBundleResponse {
  available: boolean;
  year?: number;
  source?: string;
  round_rollups: Record<string, unknown>;
  last10: Record<string, unknown>;
  sg_ratings?: SgRatingRow[];
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

interface RangeAnalyticsResponse {
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

interface RangeShotRow {
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

function fmtVsPar(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v >= 0 ? `+${v.toFixed(1)}` : v.toFixed(1);
}

function holeCardSx(
  avgStableford: number | null | undefined,
  greenMin: number,
  yellowMin: number,
) {
  if (avgStableford == null) return {};
  if (avgStableford >= greenMin) {
    return { borderLeft: 4, borderColor: "success.main" };
  }
  if (avgStableford >= yellowMin) {
    return { borderLeft: 4, borderColor: "warning.main" };
  }
  return { borderLeft: 4, borderColor: "error.main" };
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

function asOptionalNumber(v: unknown): number | null {
  if (typeof v === "number" && !Number.isNaN(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

const STRATEGY_PAR_BUCKETS = [3, 4, 5] as const;

function buildStrategyCoachSummary(overview: StrategyOverviewResponse): {
  headline: string;
  focus: string[];
  secondary: string[];
} {
  const sm = overview.scoring_method;
  const esz = asRecord(sm.proxy_esz);
  const dsz = asRecord(sm.proxy_dsz);
  const puttsBlock = asRecord(sm.proxy_putting_load);
  const pen = asRecord(sm.proxy_penalties);
  const entry = dsz ? asRecord(dsz.entry_distance) : null;
  const bandsRaw = entry?.bands_geometry;
  const bands: Record<string, unknown>[] = Array.isArray(bandsRaw)
    ? bandsRaw.map((b) => asRecord(b)).filter((b): b is Record<string, unknown> => b != null)
    : [];

  const eszPct = typeof esz?.pct_success === "number" ? (esz.pct_success as number) : null;
  const dszPct = typeof dsz?.pct_success === "number" ? (dsz.pct_success as number) : null;
  const putts =
    typeof puttsBlock?.putts_per_hole === "number" ? (puttsBlock.putts_per_hole as number) : null;

  const outerBands = bands.filter((b) => {
    const id = String(b.band_id ?? "");
    return id !== "0_30" && id !== "";
  });
  const avgBeforePutts = (() => {
    const vals = outerBands
      .map((b) => asOptionalNumber(b.mean_shots_before_putts))
      .filter((v): v is number => v != null);
    return vals.length ? vals.reduce((a, c) => a + c, 0) / vals.length : null;
  })();
  const avgInside = (() => {
    const vals = outerBands
      .map((b) => asOptionalNumber(b.mean_strokes_inside_zone))
      .filter((v): v is number => v != null);
    return vals.length ? vals.reduce((a, c) => a + c, 0) / vals.length : null;
  })();

  const focus: string[] = [];
  const secondary: string[] = [];

  if (avgBeforePutts != null && avgBeforePutts > 2.4) {
    focus.push(
      `Pitching and approach proximity — from ~30 yd entry onward you average ~${avgBeforePutts.toFixed(1)} scorecard shots before putts (target ≤2 to set up wedge + two putts).`,
    );
  }
  if (avgInside != null && avgInside > 3.2) {
    focus.push(
      `Strokes from zone entry — about ${avgInside.toFixed(1)} per hole inside 100 yd; DSZ needs ≤3 on the card.`,
    );
  }
  if (dszPct != null && dszPct < 20) {
    focus.push(
      `Down in three (DSZ) — only ${dszPct.toFixed(0)}% of in-zone holes on the scorecard; biggest gain is fewer swings before you putt, not two-putting.`,
    );
  }
  if (eszPct != null && eszPct < 35) {
    secondary.push(
      `Enter scoring zone (ESZ) — ${eszPct.toFixed(0)}% in regulation inside 100 yd; work on tee and approach lines that leave you inside ~30 yd when possible.`,
    );
  }
  if (putts != null && putts <= 2.25) {
    secondary.push(
      `Putting load ~${putts.toFixed(2)} per hole when recorded — stable; maintain speed control rather than over-investing practice time here.`,
    );
  }
  const penPct = typeof pen?.pct_holes === "number" ? (pen.pct_holes as number) : null;
  if (penPct != null && penPct > 8) {
    secondary.push(`Penalty holes — ${penPct.toFixed(0)}% of holes; course management and keeping the ball in play.`);
  }

  if (focus.length === 0 && dszPct != null) {
    focus.push(`Keep refining short game from 30–60 yd entry — DSZ ${dszPct.toFixed(0)}% with room to tighten proximity.`);
  }

  const headline =
    focus.length > 0
      ? "Biggest gain: get closer into the scoring zone and on the green in fewer strokes before you putt."
      : "Review the entry-distance table and headline metrics for this year; no single dominant leak flagged automatically.";

  return { headline, focus: focus.slice(0, 3), secondary: secondary.slice(0, 2) };
}

function StrategyCoachSummary({ overview }: { overview: StrategyOverviewResponse }) {
  const { headline, focus, secondary } = buildStrategyCoachSummary(overview);
  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2, borderColor: "primary.main", bgcolor: "action.hover" }}>
      <Typography variant="subtitle2" fontWeight={600} gutterBottom>
        Coach summary
      </Typography>
      <Typography variant="body1" paragraph sx={{ mb: focus.length ? 1.5 : 0 }}>
        {headline}
      </Typography>
      {focus.length > 0 ? (
        <Box component="ul" sx={{ m: 0, pl: 2.25 }}>
          {focus.map((line) => (
            <Typography key={line} component="li" variant="body2" paragraph sx={{ mb: 0.75 }}>
              {line}
            </Typography>
          ))}
        </Box>
      ) : null}
      {secondary.length > 0 ? (
        <>
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1, mb: 0.5 }}>
            Also worth attention
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 2.25 }}>
            {secondary.map((line) => (
              <Typography key={line} component="li" variant="caption" color="text.secondary" paragraph sx={{ mb: 0.5 }}>
                {line}
              </Typography>
            ))}
          </Box>
        </>
      ) : null}
    </Paper>
  );
}

function MetricsReferencePage({ doc }: { doc: MetricsReferenceResponse }) {
  const engine = doc.engine_snapshot;
  const methods = engine?.distance_to_pin_methods as Record<string, number> | undefined;
  const dataModel = (engine?.data_model ?? doc.esz_dsz_data_model) as Record<string, unknown>;

  return (
    <Stack spacing={3}>
      <Typography variant="body2" color="text.secondary">
        Canonical definitions for Strategy, Performance, and charts — same formulas as the API ({doc.year}).
      </Typography>

      <Box>
        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
          {doc.scoring_zone.title}
        </Typography>
        <Typography variant="body2" paragraph>
          <strong>{doc.scoring_zone.esz.title}</strong> — {doc.scoring_zone.esz.definition}
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
          {doc.scoring_zone.esz.calculation}
        </Typography>
        <Typography variant="body2" paragraph>
          <strong>{doc.scoring_zone.dsz.title}</strong> — {doc.scoring_zone.dsz.definition}
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block">
          {doc.scoring_zone.dsz.calculation}
        </Typography>
      </Box>

      <Box>
        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
          Headline tiles (Scoring Method)
        </Typography>
        <Stack spacing={1.5}>
          {doc.proxy_tiles.map((tile) => (
            <Box key={tile.key}>
              <Typography variant="body2">
                <strong>{tile.title}</strong> — {tile.label}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {tile.calculation}
              </Typography>
            </Box>
          ))}
        </Stack>
      </Box>

      <Box>
        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
          {doc.entry_distance.title}
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          {doc.entry_distance.band_note}
        </Typography>
        <Stack spacing={1}>
          {doc.entry_distance.columns.map((col) => (
            <Typography key={col.id} variant="body2">
              <strong>{col.title}</strong> — {col.calculation}
            </Typography>
          ))}
        </Stack>
      </Box>

      <Box>
        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
          Round-by-round trends
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          {doc.trends.note}
        </Typography>
        <Stack spacing={1}>
          {doc.trends.metrics.map((m) => (
            <Typography key={m.id} variant="body2">
              <strong>{m.label}</strong> — {m.calculation}
            </Typography>
          ))}
        </Stack>
      </Box>

      {engine && engine.source_available !== false ? (
        <Box>
          <Typography variant="subtitle2" fontWeight={600} gutterBottom>
            ESZ / DSZ distance engine ({doc.year})
          </Typography>
          {typeof engine.holes_evaluated === "number" ? (
            <Typography variant="body2" paragraph>
              Holes evaluated: <strong>{String(engine.holes_evaluated)}</strong>
              {typeof engine.esz_pct === "number" ? (
                <>
                  {" "}
                  · ESZ: <strong>{(engine.esz_pct as number).toFixed(1)}%</strong>
                </>
              ) : null}
              {typeof engine.dsz_pct === "number" ? (
                <>
                  {" "}
                  · DSZ: <strong>{(engine.dsz_pct as number).toFixed(1)}%</strong>
                </>
              ) : null}
            </Typography>
          ) : null}
          {methods ? (
            <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 1 }}>
              <Chip size="small" variant="outlined" label={`Geometry: ${methods.geometry ?? 0}`} />
              <Chip size="small" variant="outlined" label={`remainingDistance: ${methods.orientation ?? 0}`} />
              <Chip
                size="small"
                variant="outlined"
                label={`start − shot: ${methods.orientation_starting_minus_shot ?? 0}`}
              />
              <Chip size="small" variant="outlined" label={`Heuristic: ${methods.heuristic_straight_hole ?? 0}`} />
            </Stack>
          ) : null}
          {typeof engine.note === "string" ? (
            <Typography variant="caption" color="text.secondary" display="block">
              {engine.note}
            </Typography>
          ) : null}
        </Box>
      ) : engine?.reason ? (
        <Alert severity="info">{String(engine.reason)}</Alert>
      ) : null}

      <Box>
        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
          Garmin JSON → ESZ / DSZ (data model)
        </Typography>
        <Stack spacing={0.75}>
          {Object.entries(dataModel).map(([k, v]) => (
            <Typography key={k} variant="body2" color="text.secondary" component="div">
              <strong>{k}</strong>: {typeof v === "string" ? v : JSON.stringify(v)}
            </Typography>
          ))}
        </Stack>
      </Box>

      <Box>
        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
          Data sources & caveats
        </Typography>
        <Typography variant="body2" paragraph>
          {doc.data_sources.primary}
        </Typography>
        {Array.isArray(doc.data_sources.distance_tiers) ? (
          <Box component="ol" sx={{ m: 0, pl: 2.5 }}>
            {(doc.data_sources.distance_tiers as string[]).map((tier) => (
              <Typography key={tier} component="li" variant="body2" color="text.secondary">
                {tier}
              </Typography>
            ))}
          </Box>
        ) : null}
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {doc.data_sources.caveat}
        </Typography>
      </Box>
    </Stack>
  );
}

interface DszEntryBandRow {
  band_id: string;
  label: string;
  pct_success: number | null;
  zone_entry_holes: number;
  dsz_success_holes: number;
  diff_vs_avg_pct: number | null | undefined;
  pct_green: number | null;
  green_hit_holes: number;
  green_lie_known_holes: number;
  diff_green_vs_avg_pct: number | null | undefined;
  mean_putts: number | null;
  putts_holes: number;
  diff_putts_vs_avg_pct: number | null | undefined;
  mean_shots_before_putts: number | null;
  shots_before_putts_holes: number;
  mean_strokes_inside_zone: number | null;
}

function StrategyDszEntryDistance({ entryDistance }: { entryDistance: Record<string, unknown> }) {
  const [geometryOnly, setGeometryOnly] = useState(true);
  const bandsRaw = geometryOnly ? entryDistance.bands_geometry : entryDistance.bands;
  const bands: DszEntryBandRow[] = [];
  if (Array.isArray(bandsRaw)) {
    for (const item of bandsRaw) {
      const row = asRecord(item);
      if (!row || typeof row.label !== "string") continue;
      bands.push({
        band_id: String(row.band_id ?? row.label),
        label: row.label,
        pct_success: asOptionalNumber(row.pct_success),
        zone_entry_holes: Number(row.zone_entry_holes) || 0,
        dsz_success_holes: Number(row.dsz_success_holes) || 0,
        diff_vs_avg_pct: asOptionalNumber(row.diff_vs_avg_pct) ?? undefined,
        pct_green: asOptionalNumber(row.pct_green),
        green_hit_holes: Number(row.green_hit_holes) || 0,
        green_lie_known_holes: Number(row.green_lie_known_holes) || 0,
        diff_green_vs_avg_pct: asOptionalNumber(row.diff_green_vs_avg_pct) ?? undefined,
        mean_putts: asOptionalNumber(row.mean_putts),
        putts_holes: Number(row.putts_holes) || 0,
        diff_putts_vs_avg_pct: asOptionalNumber(row.diff_putts_vs_avg_pct) ?? undefined,
        mean_shots_before_putts: asOptionalNumber(row.mean_shots_before_putts),
        shots_before_putts_holes: Number(row.shots_before_putts_holes) || 0,
        mean_strokes_inside_zone: asOptionalNumber(row.mean_strokes_inside_zone),
      });
    }
  }
  if (bands.length === 0 && geometryOnly && Array.isArray(entryDistance.bands)) {
    return (
      <Alert severity="info" sx={{ mt: 2 }}>
        No geometry-based entry distances for this filter. Try including heuristic distances (less reliable).
      </Alert>
    );
  }
  if (bands.length === 0) return null;

  const meanEntry =
    typeof entryDistance.mean_entry_yards === "number" ? (entryDistance.mean_entry_yards as number) : null;
  const meanInsideZone =
    typeof entryDistance.mean_strokes_inside_zone === "number"
      ? (entryDistance.mean_strokes_inside_zone as number)
      : null;
  return (
    <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
      <Typography variant="subtitle2" fontWeight={600} gutterBottom>
        DSZ by entry distance
      </Typography>
      <Stack direction="row" spacing={2} sx={{ mb: 1 }} flexWrap="wrap" useFlexGap>
        {meanEntry != null ? (
          <Typography variant="caption" color="text.secondary">
            Mean entry <strong>{meanEntry.toFixed(0)} yd</strong>
          </Typography>
        ) : null}
        {meanInsideZone != null ? (
          <Typography variant="caption" color="text.secondary">
            Inside zone <strong>{meanInsideZone.toFixed(1)}</strong> strokes
          </Typography>
        ) : null}
      </Stack>
      <FormControlLabel
        control={
          <Checkbox
            size="small"
            checked={geometryOnly}
            onChange={(e) => setGeometryOnly(e.target.checked)}
          />
        }
        label={<Typography variant="caption">Geometry distances only</Typography>}
        sx={{ mb: 1, ml: 0 }}
      />
      <TableContainer sx={{ maxHeight: 360, overflow: "auto" }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell>Entry</TableCell>
              <TableCell align="right">DSZ %</TableCell>
              <TableCell align="right">Reached green %</TableCell>
              <TableCell align="right">Shots before putts</TableCell>
              <TableCell align="right">Mean putts</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {bands.map((band) => {
              const closeBand = band.band_id === "0_30";
              const diffCell = (
                diff: number | null | undefined,
                higherIsBetter: boolean
              ) => {
                if (typeof diff !== "number" || Number.isNaN(diff)) {
                  return (
                    <Typography variant="caption" color="text.disabled" display="block">
                      —
                    </Typography>
                  );
                }
                return (
                  <Typography
                    variant="caption"
                    display="block"
                    sx={{ color: strategyDiffVsAvgColor(diff, higherIsBetter), fontWeight: 600 }}
                  >
                    {diff > 0 ? "+" : ""}
                    {diff.toFixed(0)}% vs avg
                  </Typography>
                );
              };
              return (
                <TableRow
                  key={band.band_id}
                  hover
                  sx={{
                    opacity: closeBand ? 0.85 : 1,
                  }}
                >
                  <TableCell>
                    <Typography variant="body2" fontWeight={400}>
                      {band.label}
                    </Typography>
                    {closeBand ? (
                      <Typography variant="caption" color="text.disabled" display="block">
                        noisy entry / trace
                      </Typography>
                    ) : null}
                    <Typography variant="caption" color="text.secondary" display="block">
                      {band.dsz_success_holes}/{band.zone_entry_holes} DSZ
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" fontWeight={600}>
                      {band.pct_success != null ? fmtPct(band.pct_success) : "—"}
                    </Typography>
                    {band.mean_strokes_inside_zone != null ? (
                      <Typography variant="caption" color="text.secondary" display="block">
                        avg {band.mean_strokes_inside_zone.toFixed(1)} strokes inside
                      </Typography>
                    ) : null}
                    {diffCell(band.diff_vs_avg_pct, false)}
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" fontWeight={600}>
                      {band.pct_green != null
                        ? fmtPct(band.pct_green)
                        : "—"}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block">
                      {band.green_hit_holes}/{band.green_lie_known_holes} reached green
                    </Typography>
                    {diffCell(band.diff_green_vs_avg_pct, false)}
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" fontWeight={600}>
                      {band.mean_shots_before_putts != null ? band.mean_shots_before_putts.toFixed(2) : "—"}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block">
                      scorecard · n={band.shots_before_putts_holes}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" fontWeight={600}>
                      {band.mean_putts != null ? band.mean_putts.toFixed(2) : "—"}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block">
                      scorecard · n={band.putts_holes}
                    </Typography>
                    {diffCell(band.diff_putts_vs_avg_pct, true)}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}

type StrategyProxyMetricKind = "pct_holes" | "pct_hit" | "pct_success" | "putts_per_hole";

function formatStrategyProxyValue(metric: StrategyProxyMetricKind, value: number): string {
  if (metric === "putts_per_hole") return value.toFixed(2);
  if (metric === "pct_hit" || metric === "pct_holes" || metric === "pct_success") return fmtPct(value);
  return value.toFixed(1);
}

function strategyDiffVsAvgColor(diff: number, lowerIsBetter: boolean): string {
  const worse = lowerIsBetter ? diff > 0 : diff < 0;
  return worse ? "error.main" : "success.main";
}

function formatCompareDiffLine(
  diff: number | null | undefined,
  lowerIsBetter: boolean,
  label: "course" | "par",
): { text: string; color: string } {
  if (typeof diff !== "number" || Number.isNaN(diff)) {
    return { text: label === "course" ? "— vs course" : "— vs par", color: "text.disabled" };
  }
  const sign = diff > 0 ? "+" : "";
  const prefix = label === "course" ? "course" : `par`;
  return {
    text: `${sign}${diff.toFixed(0)}% vs ${prefix}`,
    color: strategyDiffVsAvgColor(diff, lowerIsBetter),
  };
}

function HoleCompareChip({
  label,
  metricKey,
  compare,
}: {
  label: string;
  metricKey: string;
  compare: HoleCompare;
}) {
  const m = compare.metrics[metricKey];
  if (!m) return null;
  const lowerIsBetter = (compare.lower_is_better ?? []).includes(metricKey);
  const valueText =
    metricKey === "avg_putts"
      ? m.value.toFixed(1)
      : metricKey === "avg_stableford_points"
        ? m.value.toFixed(2)
        : fmtPct(m.value);
  const courseDiff = formatCompareDiffLine(m.diff_vs_course_overall_pct, lowerIsBetter, "course");
  const parDiff = formatCompareDiffLine(m.diff_vs_par_on_course_pct, lowerIsBetter, "par");
  const worse =
    typeof m.diff_vs_course_overall_pct === "number" &&
    !Number.isNaN(m.diff_vs_course_overall_pct) &&
    ((lowerIsBetter && m.diff_vs_course_overall_pct > 0) ||
      (!lowerIsBetter && m.diff_vs_course_overall_pct < 0));
  return (
    <Chip
      size="small"
      label={
        <Box component="span" sx={{ display: "block", lineHeight: 1.3, py: 0.25 }}>
          <Box component="span" sx={{ fontWeight: 600 }}>
            {label} {valueText}
          </Box>
          <Box component="span" sx={{ display: "block", fontSize: "0.65rem", color: courseDiff.color }}>
            {courseDiff.text}
            {typeof m.diff_vs_par_on_course_pct === "number" ? ` · ${parDiff.text}` : ""}
          </Box>
        </Box>
      }
      color={worse ? "warning" : "success"}
      variant="outlined"
      sx={{ height: "auto", "& .MuiChip-label": { whiteSpace: "normal" } }}
    />
  );
}

function CourseScoringStatsPanel({ stats }: { stats: CourseScoringStats }) {
  const overall = stats.overall;
  const rows = STRATEGY_PAR_BUCKETS.map((par) => stats.by_par[String(par)]).filter(Boolean);

  const renderCell = (
    row: CourseScoringRates | CourseParScoringRow,
    key: "esz_pct" | "dsz_pct" | "avg_putts" | "avg_stableford_points",
    lowerIsBetter: boolean,
    format: (v: number) => string,
  ) => {
    const val = row[key];
    if (val == null) return "—";
    const diffs =
      "diff_vs_course_overall_pct" in row
        ? (row as CourseParScoringRow).diff_vs_course_overall_pct
        : undefined;
    const diff = diffs?.[key];
    const diffLine = formatCompareDiffLine(diff, lowerIsBetter, "course");
    return (
      <Box>
        <Typography variant="body2" component="span" fontWeight={500}>
          {format(val)}
        </Typography>
        {typeof diff === "number" ? (
          <Typography variant="caption" component="div" sx={{ color: diffLine.color, fontWeight: 600 }}>
            {diffLine.text}
          </Typography>
        ) : null}
      </Box>
    );
  };

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
      <Typography variant="h3" component="h3" gutterBottom>
        Scoring method on this course
      </Typography>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 2 }}>
        Par splits compare to your average across all holes played here (course round average). Per-hole chips
        also compare to the average for that par on this course.
      </Typography>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell />
              <TableCell align="right">ESZ %</TableCell>
              <TableCell align="right">DSZ %</TableCell>
              <TableCell align="right">Putts / hole</TableCell>
              <TableCell align="right">Pts / hole</TableCell>
              <TableCell align="right">Plays</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            <TableRow>
              <TableCell>
                <strong>All holes</strong>
              </TableCell>
              <TableCell align="right">{renderCell(overall, "esz_pct", false, (v) => fmtPct(v))}</TableCell>
              <TableCell align="right">{renderCell(overall, "dsz_pct", false, (v) => fmtPct(v))}</TableCell>
              <TableCell align="right">
                {renderCell(overall, "avg_putts", true, (v) => v.toFixed(2))}
              </TableCell>
              <TableCell align="right">
                {renderCell(overall, "avg_stableford_points", false, (v) => v.toFixed(2))}
              </TableCell>
              <TableCell align="right">{overall.sample_plays}</TableCell>
            </TableRow>
            {rows.map((row) => (
              <TableRow key={row.par}>
                <TableCell>Par {row.par}</TableCell>
                <TableCell align="right">{renderCell(row, "esz_pct", false, (v) => fmtPct(v))}</TableCell>
                <TableCell align="right">{renderCell(row, "dsz_pct", false, (v) => fmtPct(v))}</TableCell>
                <TableCell align="right">
                  {renderCell(row, "avg_putts", true, (v) => v.toFixed(2))}
                </TableCell>
                <TableCell align="right">
                  {renderCell(row, "avg_stableford_points", false, (v) => v.toFixed(2))}
                </TableCell>
                <TableCell align="right">{row.sample_plays}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}

function StrategyProxyParSplits({
  block,
  metricKey,
}: {
  block: Record<string, unknown>;
  metricKey: StrategyProxyMetricKind;
}) {
  const byParRaw = block.by_par;
  const direction = block.direction === "higher_is_better" ? "higher_is_better" : "lower_is_better";
  const lowerIsBetter = direction === "lower_is_better";
  const metric = (typeof block.metric === "string" ? block.metric : metricKey) as StrategyProxyMetricKind;
  if (!byParRaw || typeof byParRaw !== "object") return null;

  const rows = STRATEGY_PAR_BUCKETS.map((par) => {
    const row = asRecord((byParRaw as Record<string, unknown>)[String(par)]);
    if (!row || typeof row.value !== "number") return null;
    return { par, value: row.value as number, diff: row.diff_vs_avg_pct as number | null | undefined };
  }).filter((r): r is { par: number; value: number; diff: number | null | undefined } => r != null);

  if (rows.length === 0) return null;

  return (
    <Stack spacing={0.75} sx={{ mt: 1.5, pt: 1.25, borderTop: 1, borderColor: "divider" }}>
      {rows.map(({ par, value, diff }) => {
        const diffText =
          typeof diff === "number" && !Number.isNaN(diff)
            ? `${diff > 0 ? "+" : ""}${diff.toFixed(0)}% vs avg`
            : "— vs avg";
        const diffColor =
          typeof diff === "number" && !Number.isNaN(diff)
            ? strategyDiffVsAvgColor(diff, lowerIsBetter)
            : "text.disabled";
        return (
          <Box
            key={par}
            sx={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 1 }}
          >
            <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
              Par {par}
            </Typography>
            <Typography variant="caption" component="div" sx={{ textAlign: "right" }}>
              <Box component="span" sx={{ fontWeight: 500 }}>
                {formatStrategyProxyValue(metric, value)}
              </Box>{" "}
              <Box component="span" sx={{ color: diffColor, fontWeight: 600 }}>
                {diffText}
              </Box>
            </Typography>
          </Box>
        );
      })}
    </Stack>
  );
}

const LAST10_SG_LABELS: Record<string, string> = {
  approach: "Approach",
  around_the_green: "Around the green",
  putting: "Putting",
  tee: "Tee",
};

function last10SgChartRows(
  last10: Record<string, unknown> | undefined,
): { name: string; mean: number; sum: number; count: number }[] {
  if (!last10) return [];
  return Object.entries(last10)
    .filter(([k]) => k !== "_overall")
    .map(([k, v]) => {
      const o = asRecord(v);
      return {
        name: LAST10_SG_LABELS[k] ?? k,
        mean: typeof o?.mean_sg === "number" ? o.mean_sg : Number(o?.mean_sg) || 0,
        sum: typeof o?.sum_sg === "number" ? o.sum_sg : Number(o?.sum_sg) || 0,
        count: typeof o?.count === "number" ? o.count : Number(o?.count) || 0,
      };
    });
}

const SG_RATING_ORDER = ["DRIVE", "APPROACH", "CHIP", "PUTT", "BUNKER", "RECOVERY"];

function sgRatingChartRows(ratings: SgRatingRow[] | undefined): SgRatingRow[] {
  if (!ratings?.length) return [];
  const order = new Map(SG_RATING_ORDER.map((k, i) => [k, i]));
  return [...ratings].sort(
    (a, b) => (order.get(a.stat_shot_type) ?? 99) - (order.get(b.stat_shot_type) ?? 99),
  );
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
  const [appMode, setAppMode] = useState<AppMode>("home");
  const [tab, setTab] = useState<Tab>("plans");
  const [drillNav, setDrillNav] = useState<{
    drillId: string;
    planSessionIndex: number;
    club?: string;
    aim?: string;
  } | null>(null);
  const [planActionLoading, setPlanActionLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [year, setYear] = useState(2026);

  const [strategyOverview, setStrategyOverview] = useState<StrategyOverviewResponse | null>(null);
  const [metricsReference, setMetricsReference] = useState<MetricsReferenceResponse | null>(null);
  const [strategySubview, setStrategySubview] = useState<StrategySubview>("overview");
  const [coursesList, setCoursesList] = useState<CourseListRow[] | null>(null);
  const [courseDetail, setCourseDetail] = useState<CourseDetailResponse | null>(null);
  const [selectedCourseSlug, setSelectedCourseSlug] = useState<string | null>(null);
  const [holeDrawer, setHoleDrawer] = useState<CourseHoleAgg | null>(null);
  const [strategyChartMetrics, setStrategyChartMetrics] = useState<string[]>(
    () => [...DEFAULT_STRATEGY_CHART_METRIC_IDS],
  );
  const [perfBundle, setPerfBundle] = useState<PerfBundleResponse | null>(null);
  const [roundSummary, setRoundSummary] = useState<Record<string, unknown> | null>(null);
  const [clubs, setClubs] = useState<ClubRow[]>([]);
  const [scatter, setScatter] = useState<ScatterPoint[]>([]);
  const [rangeAnalytics, setRangeAnalytics] = useState<RangeAnalyticsResponse | null>(null);
  const [rangeShots, setRangeShots] = useState<RangeShotRow[]>([]);
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
  const [clubsCatalog, setClubsCatalog] = useState<RangeClubCatalogRow[]>([]);
  const [saving, setSaving] = useState(false);

  const excludedTrainingClubs = useMemo(() => {
    const raw = settingsDirty.excludedTrainingClubs ?? settings?.excludedTrainingClubs ?? [];
    return new Set(raw.map((c) => c.trim().toLowerCase()).filter(Boolean));
  }, [settings, settingsDirty.excludedTrainingClubs]);

  const activeRangeClubs = useMemo(
    () => clubsCatalog.filter((c) => !excludedTrainingClubs.has(c.club)).map((c) => c.club),
    [clubsCatalog, excludedTrainingClubs],
  );

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

  const strategyChartMetricDefs = useMemo((): StrategyChartMetric[] => {
    const metrics = metricsReference?.trends?.metrics;
    if (Array.isArray(metrics) && metrics.length > 0) {
      return metrics.map((m) => ({
        id: m.id,
        label: m.label,
        kind: m.kind,
        dataKey: m.data_key,
      }));
    }
    return STRATEGY_CHART_METRICS_FALLBACK;
  }, [metricsReference]);

  const defaultStrategyChartMetricIds = useMemo(
    () =>
      metricsReference?.trends?.default_metric_ids?.length
        ? metricsReference.trends.default_metric_ids
        : DEFAULT_STRATEGY_CHART_METRIC_IDS,
    [metricsReference],
  );

  const onStrategyChartMetricsChange = useCallback(
    (e: SelectChangeEvent<string[]>) => {
      const raw = e.target.value;
      const next = typeof raw === "string" ? raw.split(",") : [...raw];
      const valid = new Set(strategyChartMetricDefs.map((m) => m.id));
      const filtered = next.filter((id) => valid.has(id));
      setStrategyChartMetrics(filtered.length > 0 ? filtered : [...defaultStrategyChartMetricIds]);
    },
    [strategyChartMetricDefs, defaultStrategyChartMetricIds],
  );

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

  const refreshRange = useCallback(async (y: number) => {
    const [c, sc, an, sh] = await Promise.all([
      apiGet<ClubRow[]>(`/api/v1/range/clubs?year=${y}`),
      apiGet<ScatterPoint[]>(`/api/v1/range/scatter?year=${y}`),
      apiGet<RangeAnalyticsResponse>(`/api/v1/range/analytics?year=${y}`),
      apiGet<RangeShotRow[]>(`/api/v1/range/shots?year=${y}&limit=80`),
    ]);
    setClubs(c);
    setScatter(sc);
    setRangeAnalytics(an);
    setRangeShots(sh);
    setClubCompare(null);
  }, []);

  const refreshPlans = useCallback(async () => {
    const p = await apiGet<PlanResponse>("/api/v1/plans/training-block");
    setPlan(p);
  }, []);

  const markPlanSessionComplete = async (sessionIndex: number) => {
    setPlanActionLoading(true);
    setErr(null);
    try {
      const updated = await apiPatch<PlanResponse>(
        `/api/v1/plans/training-block/sessions/${sessionIndex}/complete`,
        {},
      );
      setPlan(updated);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setPlanActionLoading(false);
    }
  };

  const regeneratePlan = async () => {
    setPlanActionLoading(true);
    setErr(null);
    try {
      const updated = await apiPost<PlanResponse>("/api/v1/plans/training-block/regenerate");
      setPlan(updated);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setPlanActionLoading(false);
    }
  };

  const openPlanDrill = (session: PlanSession) => {
    setDrillNav({
      drillId: session.drill_id,
      planSessionIndex: session.index,
      club: session.suggested_club ?? undefined,
      aim: session.default_aim,
    });
    setAppMode("drills");
  };

  const loadClubsCatalog = useCallback(async () => {
    try {
      const cat = await apiGet<{ clubs: RangeClubCatalogRow[] }>("/api/v1/range/clubs-catalog");
      setClubsCatalog(cat.clubs ?? []);
    } catch {
      setClubsCatalog([]);
    }
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
      const d = await apiGet<ClubCompareResponse>(`/api/v1/range/club-compare?${q.toString()}`);
      setClubCompare(d);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setCompareBusy(false);
    }
  }, [compareClubA, compareClubB, year]);

  useEffect(() => {
    if (appMode !== "coach") return;
    setErr(null);
    void (async () => {
      try {
        await loadMeta();
        await loadSettings();
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [appMode, loadMeta, loadSettings]);

  useEffect(() => {
    if (appMode !== "coach" || tab !== "range" || !settings) return;
    setErr(null);
    void (async () => {
      try {
        await refreshRange(year);
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [appMode, tab, year, settings, refreshRange]);

  useEffect(() => {
    if (appMode !== "coach" || tab !== "settings") return;
    void loadClubsCatalog();
  }, [appMode, tab, loadClubsCatalog]);

  useEffect(() => {
    if (appMode !== "coach") return;
    if (activeRangeClubs.length === 0) return;
    if (!activeRangeClubs.includes(compareClubA)) {
      setCompareClubA(activeRangeClubs[0]);
    }
    if (!activeRangeClubs.includes(compareClubB)) {
      setCompareClubB(activeRangeClubs[1] ?? activeRangeClubs[0]);
    }
  }, [appMode, activeRangeClubs, compareClubA, compareClubB]);

  useEffect(() => {
    if (appMode !== "coach" || tab !== "strategy") return;
    setErr(null);
    void (async () => {
      try {
        if (strategySubview === "overview") {
          const ov = await apiGet<StrategyOverviewResponse>(`/api/v1/strategy/overview?year=${year}&limit=50`);
          setStrategyOverview(ov);
        } else if (strategySubview === "courses") {
          const cl = await apiGet<{ courses: CourseListRow[]; source_available: boolean }>(
            `/api/v1/strategy/courses?year=${year}`,
          );
          setCoursesList(cl.courses ?? []);
        } else if (strategySubview === "course" && selectedCourseSlug) {
          const cd = await apiGet<CourseDetailResponse>(
            `/api/v1/strategy/courses/${encodeURIComponent(selectedCourseSlug)}?year=${year}`,
          );
          if (cd.found === false) {
            setErr(`Course not found: ${selectedCourseSlug}`);
            setStrategySubview("courses");
          } else {
            setCourseDetail(cd);
          }
        }
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [appMode, tab, year, strategySubview, selectedCourseSlug]);

  useEffect(() => {
    if (appMode !== "coach") return;
    void apiGet<MetricsReferenceResponse>(`/api/v1/reference?year=${year}`)
      .then(setMetricsReference)
      .catch(() => setMetricsReference(null));
  }, [appMode, year]);

  useEffect(() => {
    if (appMode !== "coach" || tab !== "performance") return;
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
  }, [appMode, tab, year]);

  useEffect(() => {
    if (appMode !== "coach" || tab !== "plans") return;
    setErr(null);
    void (async () => {
      try {
        await refreshPlans();
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [appMode, tab, refreshPlans]);

  async function saveSettingsForm() {
    if (!settings) return;
    setSaving(true);
    setErr(null);
    try {
      const body: Settings = {
        ...settings,
        ...settingsDirty,
        excludedTrainingClubs:
          settingsDirty.excludedTrainingClubs ?? settings.excludedTrainingClubs ?? [],
      };
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
  const sgRatingRows = useMemo(() => sgRatingChartRows(perfBundle?.sg_ratings), [perfBundle?.sg_ratings]);

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

  const shapeBars = shotShapeBarData(rangeAnalytics?.shot_shape);
  const fiveWayBars = fiveWaySpinAxisBars(rangeAnalytics?.shot_shape?.["five_way_spin_axis"]);

  if (appMode === "home") {
    return (
      <HomeView
        onSelect={(mode) => {
          setAppMode(mode);
          if (mode === "coach") setTab("plans");
        }}
      />
    );
  }

  if (appMode === "on-course") {
    return <OnCourseView onBack={() => setAppMode("home")} />;
  }

  if (appMode === "drills") {
    return (
      <DrillsView
        initialDrillId={drillNav?.drillId ?? null}
        sessionPrefill={
          drillNav?.club || drillNav?.aim
            ? { club: drillNav.club, aim: drillNav.aim }
            : undefined
        }
        onBack={() => {
          setAppMode("coach");
          setTab("plans");
          setDrillNav(null);
          void refreshPlans();
        }}
      />
    );
  }

  const handleTabChange = (_: React.SyntheticEvent, value: number) => {
    setTab(TAB_KEYS[value] ?? "plans");
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar position="sticky" color="inherit" sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Toolbar variant="dense" sx={{ gap: 2, flexWrap: "wrap" }}>
          <Button
            onClick={() => setAppMode("home")}
            size="small"
            sx={{ minWidth: 0, px: 1, textTransform: "none", flexShrink: 0 }}
          >
            ← Home
          </Button>
          <Typography variant="h6" component="h1" sx={{ flexGrow: 1, fontWeight: 500 }}>
            Coach Analysis
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
          <Tab label="Plans" />
          <Tab label="Strategy" />
          <Tab label="Performance" />
          <Tab label="Range" />
          <Tab label="Settings" />
          <Tab label="Reference" />
        </Tabs>
      </AppBar>

      <Container maxWidth="lg" sx={{ py: { xs: 2, sm: 3 }, px: { xs: 1.5, sm: 3 }, flex: 1 }}>
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
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 2 }}>
              <ToggleButtonGroup
                size="small"
                exclusive
                value={strategySubview === "course" ? "courses" : strategySubview}
                onChange={(_, v) => {
                  if (!v) return;
                  setStrategySubview(v as StrategySubview);
                  if (v === "overview") {
                    setSelectedCourseSlug(null);
                    setCourseDetail(null);
                    setHoleDrawer(null);
                  }
                  if (v === "courses") {
                    setSelectedCourseSlug(null);
                    setCourseDetail(null);
                    setHoleDrawer(null);
                  }
                }}
                aria-label="Strategy section"
              >
                <ToggleButton value="overview">Rounds overview</ToggleButton>
                <ToggleButton value="courses">Courses & holes</ToggleButton>
              </ToggleButtonGroup>
              {strategySubview === "course" && courseDetail ? (
                <Breadcrumbs aria-label="Course navigation" sx={{ fontSize: "0.875rem" }}>
                  <Link
                    component="button"
                    variant="body2"
                    underline="hover"
                    onClick={() => {
                      setStrategySubview("courses");
                      setSelectedCourseSlug(null);
                      setCourseDetail(null);
                      setHoleDrawer(null);
                    }}
                  >
                    Courses
                  </Link>
                  <Typography variant="body2" color="text.primary">
                    {courseDetail.course_name}
                  </Typography>
                </Breadcrumbs>
              ) : null}
            </Stack>

            {strategySubview === "courses" ? (
              <>
                <Typography variant="body2" color="text.secondary" paragraph>
                  Hole-by-hole patterns on courses you have played (year <strong>{year}</strong>). Tap a course, then a
                  hole for Scoring Method stats and a play plan — no shot maps.
                </Typography>
                {coursesList == null ? (
                  <Typography color="text.secondary">Loading courses…</Typography>
                ) : coursesList.length === 0 ? (
                  <Alert severity="warning">
                    No courses in this year. Check <code>GOLF_GARMIN_JSON</code> and Settings calendar year.
                  </Alert>
                ) : (
                  <TableContainer>
                    <Table size="small" stickyHeader>
                      <TableHead>
                        <TableRow>
                          <TableCell>Course</TableCell>
                          <TableCell align="right">Rounds</TableCell>
                          <TableCell align="right">Avg net 18h</TableCell>
                          <TableCell>Worst holes</TableCell>
                          <TableCell align="right">ESZ %</TableCell>
                          <TableCell align="right">Pen %</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {coursesList.map((c) => (
                          <TableRow
                            key={c.course_slug}
                            hover
                            sx={{ cursor: "pointer" }}
                            onClick={() => {
                              setSelectedCourseSlug(c.course_slug);
                              setStrategySubview("course");
                              setCourseDetail(null);
                              setHoleDrawer(null);
                            }}
                          >
                            <TableCell>{c.course_name}</TableCell>
                            <TableCell align="right">{c.rounds_count}</TableCell>
                            <TableCell align="right">
                              {c.avg_gross != null ? c.avg_gross.toFixed(1) : "—"}
                            </TableCell>
                            <TableCell>
                              {c.worst_hole_numbers.length
                                ? c.worst_hole_numbers.map((n) => `#${n}`).join(", ")
                                : "—"}
                            </TableCell>
                            <TableCell align="right">{fmtPct(c.esz_pct)}</TableCell>
                            <TableCell align="right">{fmtPct(c.penalty_hole_pct)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </>
            ) : null}

            {strategySubview === "course" && courseDetail ? (
              <>
                <Alert severity="info" sx={{ mb: 2 }}>
                  {courseDetail.course_coach_summary}
                </Alert>
                <Typography variant="body2" color="text.secondary" paragraph>
                  <strong>{courseDetail.rounds_count}</strong> round(s) · avg gross (18-hole est.){" "}
                  <strong>
                    {courseDetail.avg_gross != null ? courseDetail.avg_gross.toFixed(1) : "—"}
                  </strong>
                  {courseDetail.partial_rounds_count ? (
                    <>
                      {" "}
                      · <strong>{courseDetail.partial_rounds_count}</strong> partial round(s) grossed up
                      net 18h gross caps blow-ups and imputes unplayed holes at net double bogey (par+2+handicap by SI)
                    </>
                  ) : null}
                  . ESZ/DSZ/putts/points chips compare to your averages on this course and for that par. Tap a
                  hole for the coach play plan.
                </Typography>
                {courseDetail.avg_gross_note ? (
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 2 }}>
                    {courseDetail.avg_gross_note}
                  </Typography>
                ) : null}
                {courseDetail.scoring_stats ? (
                  <CourseScoringStatsPanel stats={courseDetail.scoring_stats} />
                ) : null}
                <Grid container spacing={1.5} sx={{ mb: 3 }}>
                  {courseDetail.holes.map((h) => (
                    <Grid item xs={6} sm={4} md={3} key={h.hole_number}>
                      <Card
                        variant="outlined"
                        sx={holeCardSx(
                          h.avg_stableford_points,
                          settings?.stablefordColorGreenMin ?? 2,
                          settings?.stablefordColorYellowMin ?? 1,
                        )}
                      >
                        <CardActionArea onClick={() => setHoleDrawer(h)}>
                          <Box sx={{ p: 1.5 }}>
                            <Stack direction="row" justifyContent="space-between" alignItems="center">
                              <Typography variant="h6" component="div" fontWeight={700}>
                                {h.hole_number}
                              </Typography>
                              {h.trouble_hole ? (
                                <Chip size="small" label="Trouble" color="error" variant="outlined" />
                              ) : null}
                            </Stack>
                            <Typography variant="caption" color="text.secondary" display="block">
                              Par {h.par ?? "—"}
                              {h.stroke_index != null ? ` · SI ${h.stroke_index}` : ""}
                              {h.yardage_yards != null ? ` · ${Math.round(h.yardage_yards)} yd` : ""}
                            </Typography>
                            <Typography variant="body2" sx={{ mt: 0.5 }}>
                              Avg{" "}
                              <strong>
                                {h.avg_score != null ? h.avg_score.toFixed(1) : "—"}
                              </strong>
                              {h.avg_vs_par != null ? (
                                <>
                                  {" "}
                                  ({fmtVsPar(h.avg_vs_par)} vs par)
                                </>
                              ) : null}
                              {h.plays_count > 1 ? ` · ${h.plays_count} plays` : ""}
                            </Typography>
                            {h.stableford_tracked_plays > 0 ? (
                              <Typography variant="caption" color="text.secondary" display="block">
                                Stableford avg{" "}
                                <strong>
                                  {h.avg_stableford_points != null
                                    ? h.avg_stableford_points.toFixed(2)
                                    : "—"}
                                </strong>{" "}
                                pts
                              </Typography>
                            ) : null}
                            <Stack direction="row" flexWrap="wrap" gap={0.5} sx={{ mt: 1 }}>
                              {h.compare ? (
                                <>
                                  <HoleCompareChip label="ESZ" metricKey="esz_pct" compare={h.compare} />
                                  <HoleCompareChip label="DSZ" metricKey="dsz_pct" compare={h.compare} />
                                  <HoleCompareChip label="Putts" metricKey="avg_putts" compare={h.compare} />
                                  <HoleCompareChip
                                    label="Pts"
                                    metricKey="avg_stableford_points"
                                    compare={h.compare}
                                  />
                                </>
                              ) : (
                                <>
                                  {h.esz_evaluated_count > 0 && h.esz_success_rate != null ? (
                                    <Chip
                                      size="small"
                                      label={`ESZ ${fmtPct(100 * h.esz_success_rate)}`}
                                      variant="outlined"
                                    />
                                  ) : null}
                                  {h.dsz_eligible_count > 0 && h.dsz_success_rate != null ? (
                                    <Chip
                                      size="small"
                                      label={`DSZ ${fmtPct(100 * h.dsz_success_rate)}`}
                                      variant="outlined"
                                    />
                                  ) : null}
                                  {h.avg_putts != null ? (
                                    <Chip
                                      size="small"
                                      label={`Putts ${h.avg_putts.toFixed(1)}`}
                                      variant="outlined"
                                    />
                                  ) : null}
                                </>
                              )}
                              {h.penalty_rate != null && h.penalty_rate > 0 ? (
                                <Chip
                                  size="small"
                                  label={`Pen ${fmtPct(100 * h.penalty_rate)}`}
                                  color="warning"
                                  variant="outlined"
                                />
                              ) : null}
                            </Stack>
                          </Box>
                        </CardActionArea>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
                {courseDetail.round_history.length > 0 ? (
                  <>
                    <Typography variant="h3" component="h3" gutterBottom>
                      Rounds on this course
                    </Typography>
                    <TableContainer sx={{ mb: 2 }}>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Date</TableCell>
                            <TableCell align="right">Net 18h</TableCell>
                            <TableCell align="right">Raw</TableCell>
                            <TableCell align="right">Played</TableCell>
                            <TableCell>Leak holes</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {courseDetail.round_history.map((r) => (
                            <TableRow key={r.scorecard_id} hover>
                              <TableCell>{r.started_at?.slice(0, 10) ?? "—"}</TableCell>
                              <TableCell align="right">
                                {r.gross_net_18 ?? r.gross_estimated_18 ?? r.strokes ?? "—"}
                                {r.is_partial ? (
                                  <Typography variant="caption" color="text.secondary" display="block">
                                    est. 18h
                                  </Typography>
                                ) : null}
                                {(r.holes_capped ?? 0) > 0 ? (
                                  <Typography variant="caption" color="warning.main" display="block">
                                    {r.holes_capped} capped
                                  </Typography>
                                ) : null}
                              </TableCell>
                              <TableCell align="right">
                                {r.gross_raw ?? r.gross_actual ?? "—"}
                                {r.is_partial && r.gross_raw != null ? (
                                  <Typography variant="caption" color="text.secondary" display="block">
                                    {r.holes_scored ?? "?"} holes
                                  </Typography>
                                ) : null}
                              </TableCell>
                              <TableCell align="right">{r.holes_scored ?? "—"}</TableCell>
                              <TableCell>
                                {r.leak_holes?.length
                                  ? r.leak_holes.map((n) => `#${n}`).join(", ")
                                  : "—"}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </>
                ) : null}
              </>
            ) : null}

            {strategySubview === "overview" ? (
              <>
            {strategyOverview ? (
              <Stack spacing={2} sx={{ mb: 3 }}>
                {!strategyOverview.source_available ? (
                  <Alert severity="warning">
                    {strategyOverview.reason ?? "Garmin export not available."} Configure{" "}
                    <code>GOLF_GARMIN_JSON</code> for scorecard-backed tiles.
                  </Alert>
                ) : (
                  <StrategyCoachSummary overview={strategyOverview} />
                )}
                <Typography variant="h3" component="h3" gutterBottom>
                  Scoring Method · {strategyOverview.year}
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                  ESZ = in zone by regulation · DSZ = down in three from zone entry. See Reference tab for formulas.
                </Typography>
                <Stack direction={{ xs: "column", md: "row" }} spacing={2} flexWrap="wrap" useFlexGap>
                  {(
                    [
                      ["proxy_avoid_big_numbers", "pct_holes"],
                      ["proxy_penalties", "pct_holes"],
                      ["proxy_fairway", "pct_hit"],
                      ["proxy_putting_load", "putts_per_hole"],
                      ["proxy_esz", "pct_success"],
                      ["proxy_dsz", "pct_success"],
                    ] as const
                  ).map(([key, metricKey]) => {
                    const block = asRecord(strategyOverview.scoring_method[key]);
                    if (!block) return null;
                    const title =
                      typeof block.title === "string"
                        ? block.title
                        : (metricsReference?.proxy_tiles.find((t) => t.key === key)?.title ?? key);
                    const raw = block[metricKey];
                    if (raw == null && (key === "proxy_esz" || key === "proxy_dsz")) return null;
                    const headline =
                      metricKey === "putts_per_hole" && typeof raw === "number"
                        ? raw.toFixed(2)
                        : typeof raw === "number"
                          ? metricKey.startsWith("pct")
                            ? fmtPct(raw)
                            : raw.toFixed(1)
                          : "—";
                    return (
                      <Paper key={key} variant="outlined" sx={{ p: 2, flex: "1 1 220px", minWidth: 220 }}>
                        <Typography variant="subtitle2" fontWeight={600}>
                          {title}
                        </Typography>
                        <Typography variant="h5" component="div" sx={{ mt: 0.5 }}>
                          {headline}
                        </Typography>
                        <StrategyProxyParSplits block={block} metricKey={metricKey} />
                      </Paper>
                    );
                  })}
                </Stack>
                {(() => {
                  const dsz =
                    asRecord(strategyOverview.scoring_method.proxy_dsz) ??
                    asRecord(
                      (strategyOverview.esz_dsz_from_shots as Record<string, unknown> | undefined)?.proxy_dsz
                    );
                  const entry = dsz ? asRecord(dsz.entry_distance) : null;
                  if (
                    !entry ||
                    (!Array.isArray(entry.bands_geometry) && !Array.isArray(entry.bands))
                  ) {
                    return null;
                  }
                  return <StrategyDszEntryDistance entryDistance={entry} />;
                })()}
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
                            <TableCell align="right">0 pts</TableCell>
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
                                <TableCell align="right">{sc.stableford_zero_point_holes}</TableCell>
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
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                  Oldest → newest. Rates are per hole played; see Reference for axis rules.
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
                        .map((id) => strategyChartMetricDefs.find((m) => m.id === id)?.label ?? id)
                        .join(" · ")
                    }
                  >
                    <ListSubheader disableSticky>Percent</ListSubheader>
                    {strategyChartMetricDefs.filter((m) => m.kind === "percent").map((m) => (
                      <MenuItem key={m.id} value={m.id}>
                        {m.label}
                      </MenuItem>
                    ))}
                    <ListSubheader disableSticky>Per hole played</ListSubheader>
                    {strategyChartMetricDefs.filter((m) => m.kind === "rate").map((m) => (
                      <MenuItem key={m.id} value={m.id}>
                        {m.label}
                      </MenuItem>
                    ))}
                    <ListSubheader disableSticky>Raw totals</ListSubheader>
                    {strategyChartMetricDefs.filter((m) => m.kind === "count").map((m) => (
                      <MenuItem key={m.id} value={m.id}>
                        {m.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                {(() => {
                  const defs = strategyChartMetricDefs.filter((m) => strategyChartMetrics.includes(m.id));
                  const pctDefs = defs.filter((m) => m.kind === "percent");
                  const rateDefs = defs.filter((m) => m.kind === "rate");
                  const cntDefs = defs.filter((m) => m.kind === "count");
                  const numericDefs = [...rateDefs, ...cntDefs];
                  const dual = pctDefs.length > 0 && numericDefs.length > 0;
                  const pctOnly = pctDefs.length > 0 && numericDefs.length === 0;
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
                              <YAxis
                                yAxisId="num"
                                orientation="right"
                                domain={[0, "auto"]}
                                tickFormatter={(v) => Number(v).toFixed(1)}
                                width={40}
                              />
                            </>
                          ) : pctOnly ? (
                            <YAxis
                              yAxisId="main"
                              orientation="left"
                              domain={[0, "auto"]}
                              tickFormatter={(v) => `${Number(v).toFixed(0)}%`}
                              width={44}
                            />
                          ) : (
                            <YAxis
                              yAxisId="main"
                              orientation="left"
                              domain={[0, "auto"]}
                              tickFormatter={(v) => Number(v).toFixed(1)}
                              width={40}
                            />
                          )}
                          <Tooltip
                            formatter={(value: number | string, name: string) => {
                              const meta = strategyChartMetricDefs.find((m) => m.label === name);
                              const v = typeof value === "number" ? value : Number(value);
                              if (Number.isNaN(v)) return ["—", name];
                              if (meta?.kind === "percent") return [`${v.toFixed(1)}%`, name];
                              if (meta?.kind === "rate") return [v.toFixed(2), name];
                              return [`${v}`, name];
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
                              stroke={strategyMetricColor(m.id, strategyChartMetricDefs)}
                              strokeWidth={2}
                              dot={{ r: 2 }}
                              connectNulls
                              isAnimationActive={false}
                            />
                          ))}
                          {numericDefs.map((m) => (
                            <Line
                              key={m.id}
                              yAxisId={dual ? "num" : "main"}
                              type="monotone"
                              dataKey={m.dataKey as string}
                              name={m.label}
                              stroke={strategyMetricColor(m.id, strategyChartMetricDefs)}
                              strokeWidth={2}
                              dot={{ r: 2 }}
                              strokeDasharray={m.kind === "count" ? "6 3" : undefined}
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
              </>
            ) : null}
          </Paper>
        ) : null}

        {tab === "reference" ? (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h2" component="h2" gutterBottom>
              Reference
            </Typography>
            {metricsReference ? (
              <MetricsReferencePage doc={metricsReference} />
            ) : (
              <Typography color="text.secondary">Loading…</Typography>
            )}
          </Paper>
        ) : null}

        <Drawer
          anchor="right"
          open={holeDrawer != null}
          onClose={() => setHoleDrawer(null)}
          PaperProps={{ sx: { width: { xs: "100%", sm: 420 }, p: 2 } }}
        >
          {holeDrawer ? (
            <Stack spacing={2}>
              <Typography variant="h5" component="h2" fontWeight={600}>
                Hole {holeDrawer.hole_number}
                {holeDrawer.par != null ? ` · Par ${holeDrawer.par}` : ""}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {holeDrawer.par != null ? `Par ${holeDrawer.par}` : "Par —"}
                {holeDrawer.stroke_index != null ? ` · Stroke index ${holeDrawer.stroke_index}` : ""}
                {holeDrawer.yardage_yards != null
                  ? ` · ~${Math.round(holeDrawer.yardage_yards)} yd`
                  : ""}
              </Typography>
              <Table size="small">
                <TableBody>
                  <TableRow>
                    <TableCell>Plays</TableCell>
                    <TableCell align="right">{holeDrawer.plays_count}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Avg score</TableCell>
                    <TableCell align="right">
                      {holeDrawer.avg_score != null ? holeDrawer.avg_score.toFixed(1) : "—"} (
                      {fmtVsPar(holeDrawer.avg_vs_par)} vs par)
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Scores</TableCell>
                    <TableCell align="right">
                      {holeDrawer.scores.length ? holeDrawer.scores.join(", ") : "—"}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Avg Stableford pts</TableCell>
                    <TableCell align="right">
                      {holeDrawer.compare?.metrics.avg_stableford_points ? (
                        <>
                          {holeDrawer.compare.metrics.avg_stableford_points.value.toFixed(2)}
                          {typeof holeDrawer.compare.metrics.avg_stableford_points
                            .diff_vs_course_overall_pct === "number" ? (
                            <Typography
                              variant="caption"
                              display="block"
                              sx={{
                                color: strategyDiffVsAvgColor(
                                  holeDrawer.compare.metrics.avg_stableford_points
                                    .diff_vs_course_overall_pct,
                                  false,
                                ),
                              }}
                            >
                              {formatCompareDiffLine(
                                holeDrawer.compare.metrics.avg_stableford_points
                                  .diff_vs_course_overall_pct,
                                false,
                                "course",
                              ).text}
                              {typeof holeDrawer.compare.metrics.avg_stableford_points
                                .diff_vs_par_on_course_pct === "number"
                                ? ` · ${formatCompareDiffLine(holeDrawer.compare.metrics.avg_stableford_points.diff_vs_par_on_course_pct, false, "par").text}`
                                : ""}
                            </Typography>
                          ) : null}
                        </>
                      ) : holeDrawer.avg_stableford_points != null ? (
                        holeDrawer.avg_stableford_points.toFixed(2)
                      ) : (
                        "—"
                      )}
                      {holeDrawer.stableford_tracked_plays > 0
                        ? ` (${holeDrawer.stableford_tracked_plays} plays)`
                        : ""}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Trouble threshold</TableCell>
                    <TableCell align="right">
                      {holeDrawer.trouble_min_avg_stableford != null
                        ? `< ${holeDrawer.trouble_min_avg_stableford} pt`
                        : "< 1 pt"}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>ESZ success</TableCell>
                    <TableCell align="right">
                      {holeDrawer.compare?.metrics.esz_pct ? (
                        <>
                          {fmtPct(holeDrawer.compare.metrics.esz_pct.value)}
                          {typeof holeDrawer.compare.metrics.esz_pct.diff_vs_course_overall_pct ===
                          "number" ? (
                            <Typography
                              variant="caption"
                              display="block"
                              sx={{
                                color: strategyDiffVsAvgColor(
                                  holeDrawer.compare.metrics.esz_pct.diff_vs_course_overall_pct,
                                  false,
                                ),
                              }}
                            >
                              {formatCompareDiffLine(
                                holeDrawer.compare.metrics.esz_pct.diff_vs_course_overall_pct,
                                false,
                                "course",
                              ).text}
                              {typeof holeDrawer.compare.metrics.esz_pct.diff_vs_par_on_course_pct ===
                              "number"
                                ? ` · ${formatCompareDiffLine(holeDrawer.compare.metrics.esz_pct.diff_vs_par_on_course_pct, false, "par").text}`
                                : ""}
                            </Typography>
                          ) : null}
                        </>
                      ) : holeDrawer.esz_success_rate != null ? (
                        fmtPct(100 * holeDrawer.esz_success_rate)
                      ) : (
                        "—"
                      )}
                      {holeDrawer.esz_evaluated_count > 0
                        ? ` (${holeDrawer.esz_evaluated_count} traced)`
                        : ""}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>DSZ (in zone)</TableCell>
                    <TableCell align="right">
                      {holeDrawer.compare?.metrics.dsz_pct ? (
                        <>
                          {fmtPct(holeDrawer.compare.metrics.dsz_pct.value)}
                          {typeof holeDrawer.compare.metrics.dsz_pct.diff_vs_course_overall_pct ===
                          "number" ? (
                            <Typography
                              variant="caption"
                              display="block"
                              sx={{
                                color: strategyDiffVsAvgColor(
                                  holeDrawer.compare.metrics.dsz_pct.diff_vs_course_overall_pct,
                                  false,
                                ),
                              }}
                            >
                              {formatCompareDiffLine(
                                holeDrawer.compare.metrics.dsz_pct.diff_vs_course_overall_pct,
                                false,
                                "course",
                              ).text}
                              {typeof holeDrawer.compare.metrics.dsz_pct.diff_vs_par_on_course_pct ===
                              "number"
                                ? ` · ${formatCompareDiffLine(holeDrawer.compare.metrics.dsz_pct.diff_vs_par_on_course_pct, false, "par").text}`
                                : ""}
                            </Typography>
                          ) : null}
                        </>
                      ) : holeDrawer.dsz_success_rate != null ? (
                        fmtPct(100 * holeDrawer.dsz_success_rate)
                      ) : (
                        "—"
                      )}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Penalties</TableCell>
                    <TableCell align="right">
                      {holeDrawer.penalty_count}/{holeDrawer.plays_count}
                      {holeDrawer.penalty_rate != null ? ` (${fmtPct(100 * holeDrawer.penalty_rate)})` : ""}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Fairway</TableCell>
                    <TableCell align="right">{fmtPct(holeDrawer.fairway_hit_pct)}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Avg putts</TableCell>
                    <TableCell align="right">
                      {holeDrawer.compare?.metrics.avg_putts ? (
                        <>
                          {holeDrawer.compare.metrics.avg_putts.value.toFixed(1)}
                          {typeof holeDrawer.compare.metrics.avg_putts.diff_vs_course_overall_pct ===
                          "number" ? (
                            <Typography
                              variant="caption"
                              display="block"
                              sx={{
                                color: strategyDiffVsAvgColor(
                                  holeDrawer.compare.metrics.avg_putts.diff_vs_course_overall_pct,
                                  true,
                                ),
                              }}
                            >
                              {formatCompareDiffLine(
                                holeDrawer.compare.metrics.avg_putts.diff_vs_course_overall_pct,
                                true,
                                "course",
                              ).text}
                              {typeof holeDrawer.compare.metrics.avg_putts.diff_vs_par_on_course_pct ===
                              "number"
                                ? ` · ${formatCompareDiffLine(holeDrawer.compare.metrics.avg_putts.diff_vs_par_on_course_pct, true, "par").text}`
                                : ""}
                            </Typography>
                          ) : null}
                        </>
                      ) : holeDrawer.avg_putts != null ? (
                        holeDrawer.avg_putts.toFixed(1)
                      ) : (
                        "—"
                      )}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
              {holeDrawer.trouble_reasons.length > 0 ? (
                <Alert severity="warning" variant="outlined">
                  {holeDrawer.trouble_reasons.join(" · ")}
                </Alert>
              ) : null}
              <Divider />
              <Typography variant="subtitle1" fontWeight={600}>
                How to play it next time
              </Typography>
              <Typography variant="body2">{holeDrawer.coach.headline}</Typography>
              {holeDrawer.coach.sections.map((s) => (
                <Box key={s.title}>
                  <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                    {s.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {s.body}
                  </Typography>
                </Box>
              ))}
              <Typography variant="caption" color="text.secondary">
                {holeDrawer.coach.confidence_note}
              </Typography>
              <Button variant="outlined" onClick={() => setHoleDrawer(null)}>
                Close
              </Button>
            </Stack>
          ) : null}
        </Drawer>

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
            <Typography variant="body2" color="text.secondary" paragraph sx={{ maxWidth: 720 }}>
              Garmin does <strong>not</strong> put strokes gained on every shot in <code>shotDetails</code>. This tab uses
              two export sources: headline <strong>SG ratings</strong> (all shot types) and per-shot{" "}
              <strong>last-10 samples</strong> (only categories Garmin populated). For full-round scoring proxies (ESZ,
              DSZ, fairway, putts), use <strong>Strategy</strong>.
            </Typography>

            <Typography variant="h3" component="h3" gutterBottom>
              SG ratings (vs similar handicap)
            </Typography>
            {perfBundle?.available && sgRatingRows.length > 0 ? (
              <Stack spacing={2} sx={{ mb: 3 }}>
                <Box sx={{ width: "100%", height: 280 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={sgRatingRows.filter((r) => r.player_strokes_gained != null)}
                      margin={{ top: 8, right: 16, left: 8, bottom: 56 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                      <XAxis dataKey="label" angle={-18} textAnchor="end" height={52} interval={0} />
                      <YAxis
                        stroke={theme.palette.text.secondary}
                        tickFormatter={(v) => Number(v).toFixed(2)}
                      />
                      <Tooltip
                        formatter={(v: number, name: string) => [v.toFixed(3), name]}
                        labelFormatter={(label) => String(label)}
                      />
                      <Legend />
                      <Bar
                        dataKey="player_strokes_gained"
                        name="You"
                        fill={theme.palette.primary.main}
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar
                        dataKey="group_strokes_gained"
                        name="Similar handicap"
                        fill={theme.palette.text.disabled}
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </Box>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Category</TableCell>
                        <TableCell align="right">Your SG</TableCell>
                        <TableCell align="right">Cohort SG</TableCell>
                        <TableCell>Trend</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {sgRatingRows.map((r) => (
                        <TableRow key={r.stat_shot_type}>
                          <TableCell>{r.label}</TableCell>
                          <TableCell align="right">
                            {r.player_strokes_gained != null ? r.player_strokes_gained.toFixed(2) : "—"}
                          </TableCell>
                          <TableCell align="right">
                            {r.group_strokes_gained != null ? r.group_strokes_gained.toFixed(2) : "—"}
                          </TableCell>
                          <TableCell>{r.trend ?? "—"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Stack>
            ) : perfBundle?.available ? (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                No <code>last10DataStats.strokesGainedRatings</code> in this export.
              </Typography>
            ) : null}

            <Typography variant="h3" component="h3" gutterBottom>
              Last-10 shot samples (per-shot SG)
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
              Only categories with sample rows in <code>last10DataApproach</code> / <code>last10DataChip</code> /{" "}
              <code>last10DataPutt</code> / <code>last10DataDrive</code> appear — your export may omit tee and putting
              samples even when ratings exist above.
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
                      <Tooltip
                        formatter={(v: number, name: string) => {
                          if (name === "Mean strokes gained" || name === "Sum strokes gained") {
                            return [v.toFixed(3), name];
                          }
                          return [v, name];
                        }}
                        labelFormatter={(label, payload) => {
                          const p = payload?.[0]?.payload as { count?: number } | undefined;
                          const n = p?.count;
                          return n != null && n > 0 ? `${label} (n=${n})` : String(label);
                        }}
                      />
                      <Legend />
                      <Bar
                        dataKey={sgAgg}
                        name={sgAgg === "mean" ? "Mean strokes gained" : "Sum strokes gained"}
                        fill={theme.palette.secondary.main}
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
                No last-10 sample shots with <code>strokesGained</code> for this year filter.
              </Typography>
            )}
          </Paper>
        ) : null}

        {tab === "range" ? (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h2" component="h2" gutterBottom>
              Range
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Rapsodo LM cohort · Year <strong>{year}</strong>. Ratio = mean |offline| / mean carry.{" "}
              <strong>FLAG</strong> when ratio &gt;{" "}
              {(settings?.trainingDispersionRatioFlag ?? 0.1).toFixed(2)} (Settings). Excluded clubs
              are hidden here and in compare.
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

            {rangeAnalytics && rangeAnalytics.takeaways?.length ? (
              <Box sx={{ mb: 3 }}>
                <Typography variant="h3" component="h3" gutterBottom>
                  Key takeaways
                </Typography>
                <Stack spacing={1}>
                  {rangeAnalytics.takeaways.map((t, i) => (
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
              <FormControl size="small" sx={{ minWidth: 160 }}>
                <InputLabel id="club-a-label">Club A</InputLabel>
                <Select
                  labelId="club-a-label"
                  label="Club A"
                  value={activeRangeClubs.includes(compareClubA) ? compareClubA : ""}
                  onChange={(e) => setCompareClubA(String(e.target.value))}
                >
                  {activeRangeClubs.map((c) => (
                    <MenuItem key={c} value={c}>
                      {c}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 160 }}>
                <InputLabel id="club-b-label">Club B</InputLabel>
                <Select
                  labelId="club-b-label"
                  label="Club B"
                  value={activeRangeClubs.includes(compareClubB) ? compareClubB : ""}
                  onChange={(e) => setCompareClubB(String(e.target.value))}
                >
                  {activeRangeClubs.map((c) => (
                    <MenuItem key={c} value={c}>
                      {c}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Button
                variant="outlined"
                disabled={compareBusy || activeRangeClubs.length < 2}
                onClick={() => void runClubCompare()}
              >
                {compareBusy ? "Loading…" : "Compare"}
              </Button>
            </Stack>
            {activeRangeClubs.length < 2 ? (
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 2 }}>
                Need at least two active clubs — uncheck exclusions in Settings.
              </Typography>
            ) : null}
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

            {rangeAnalytics ? (
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
                      {rangeAnalytics.carry_distribution.map((row) => (
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
                      {rangeAnalytics.landing_side.map((row) => (
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
                      {rangeAnalytics.gapping.map((row) => (
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
                  {typeof rangeAnalytics.shot_shape.note === "string"
                    ? rangeAnalytics.shot_shape.note
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
                      const fw = asRecord(rangeAnalytics.shot_shape["five_way_spin_axis"]);
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
                      {rangeShots.map((sh) => (
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
              Training plan
            </Typography>
            {plan ? (
              <Stack spacing={3}>
                <Alert severity="info" sx={{ alignItems: "flex-start" }}>
                  <Typography variant="subtitle2" fontWeight={700} gutterBottom>
                    Coach summary
                  </Typography>
                  <Typography variant="body2">{plan.coach_summary}</Typography>
                </Alert>

                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
                  <Chip
                    label={`${plan.sessions.filter((s) => s.completed_at).length}/${plan.sessions_planned} complete`}
                    color={plan.all_complete ? "success" : "default"}
                  />
                  <Chip label={`Year ${plan.calendar_year}`} variant="outlined" />
                  {plan.flagged_clubs.length > 0 ? (
                    <Chip
                      label={`Range flags: ${plan.flagged_clubs.slice(0, 3).join(", ")}`}
                      color="warning"
                      variant="outlined"
                    />
                  ) : null}
                </Stack>

                {plan.insights.length > 0 ? (
                  <>
                    <Typography variant="h3" component="h3">
                      Data insights
                    </Typography>
                    <List dense disablePadding>
                      {plan.insights.map((s, i) => (
                        <ListItem key={i} sx={{ py: 0.5, alignItems: "flex-start" }}>
                          <ListItemText primary={s} />
                        </ListItem>
                      ))}
                    </List>
                    <Divider />
                  </>
                ) : null}

                <Typography variant="h3" component="h3">
                  Training block
                </Typography>
                <Stack spacing={2}>
                  {plan.sessions.map((s) => {
                    const done = Boolean(s.completed_at);
                    return (
                      <Paper key={s.index} variant="outlined" sx={{ p: 2, opacity: done ? 0.85 : 1 }}>
                        <Stack spacing={1.5}>
                          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                            <Typography variant="subtitle1" fontWeight={600}>
                              {s.index}. {s.title}
                            </Typography>
                            <Chip label={s.priority_tag} size="small" color="primary" />
                            {done ? <Chip label="Complete" size="small" color="success" /> : null}
                          </Stack>
                          <Typography variant="body2" color="text.secondary">
                            {s.description}
                          </Typography>
                          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                            <Chip label={s.drill_title} size="small" variant="outlined" />
                            {s.expected_duration_minutes ? (
                              <Chip label={`~${s.expected_duration_minutes} min`} size="small" variant="outlined" />
                            ) : null}
                            {s.rapsodo_mode_label ? (
                              <Chip label={s.rapsodo_mode_label} size="small" color="info" variant="outlined" />
                            ) : null}
                            {s.suggested_club ? (
                              <Chip label={`Focus: ${s.suggested_club}`} size="small" variant="outlined" />
                            ) : null}
                          </Stack>
                          <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                            <Button
                              variant="contained"
                              size="small"
                              disabled={done}
                              onClick={() => openPlanDrill(s)}
                              sx={{ textTransform: "none" }}
                            >
                              {done ? "Drill logged" : "Open drill & log session"}
                            </Button>
                            {!done ? (
                              <Button
                                variant="outlined"
                                size="small"
                                disabled={planActionLoading}
                                onClick={() => void markPlanSessionComplete(s.index)}
                                sx={{ textTransform: "none" }}
                              >
                                Mark complete
                              </Button>
                            ) : null}
                          </Stack>
                        </Stack>
                      </Paper>
                    );
                  })}
                </Stack>

                {plan.all_complete ? (
                  <Box>
                    <Alert severity="success" sx={{ mb: 2 }}>
                      Block complete — regenerate a fresh plan from your latest Garmin and Rapsodo data.
                    </Alert>
                    <Button
                      variant="contained"
                      disabled={planActionLoading}
                      onClick={() => void regeneratePlan()}
                      sx={{ textTransform: "none" }}
                    >
                      {planActionLoading ? "Generating…" : "Regenerate training block"}
                    </Button>
                  </Box>
                ) : null}
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
                  label="Calendar year (range / plans)"
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
                <Typography variant="subtitle2" sx={{ pt: 1 }}>
                  Range (Rapsodo)
                </Typography>
                <TextField
                  label="FLAG ratio threshold"
                  type="number"
                  fullWidth
                  inputProps={{ min: 0.01, max: 1, step: 0.01 }}
                  helperText="FLAG when mean |offline| ÷ mean carry exceeds this (default 0.1 = 10%)."
                  value={
                    settingsDirty.trainingDispersionRatioFlag ?? settings.trainingDispersionRatioFlag ?? 0.1
                  }
                  onChange={(e) =>
                    setSettingsDirty((d) => ({
                      ...d,
                      trainingDispersionRatioFlag: Number(e.target.value),
                    }))
                  }
                />
                <Typography variant="body2" color="text.secondary">
                  Clubs in your library — exclude ones not in your bag (e.g. old hybrids).
                </Typography>
                {clubsCatalog.length === 0 ? (
                  <Typography variant="caption" color="text.secondary">
                    No clubs in library yet, or still loading catalog…
                  </Typography>
                ) : (
                  <FormGroup sx={{ maxHeight: 280, overflow: "auto", border: 1, borderColor: "divider", borderRadius: 1, px: 1 }}>
                    {clubsCatalog.map((row) => {
                      const excluded = excludedTrainingClubs.has(row.club);
                      return (
                        <FormControlLabel
                          key={row.club}
                          control={
                            <Checkbox
                              size="small"
                              checked={excluded}
                              onChange={() => {
                                const next = new Set(excludedTrainingClubs);
                                if (next.has(row.club)) next.delete(row.club);
                                else next.add(row.club);
                                setSettingsDirty((d) => ({
                                  ...d,
                                  excludedTrainingClubs: [...next],
                                }));
                              }}
                            />
                          }
                          label={
                            <Typography variant="body2">
                              {row.club}{" "}
                              <Typography component="span" variant="caption" color="text.secondary">
                                ({row.n} shots)
                              </Typography>
                            </Typography>
                          }
                        />
                      );
                    })}
                  </FormGroup>
                )}
                <Typography variant="caption" color="text.secondary">
                  Checked = excluded from Range table, Plans flags, and club compare lists.
                </Typography>
                <Accordion disableGutters sx={{ mt: 1 }}>
                  <AccordionSummary>
                    <Typography variant="subtitle2">Advanced</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Stack spacing={2}>
                      <TextField
                        label="Trouble hole: min avg Stableford points"
                        type="number"
                        fullWidth
                        inputProps={{ min: 0, max: 4, step: 0.1 }}
                        helperText="Flag Trouble when avg Garmin typeScore (Stableford points per hole) is below this value. Default 1."
                        value={
                          settingsDirty.troubleMinAvgStablefordPoints ??
                          settings.troubleMinAvgStablefordPoints
                        }
                        onChange={(e) =>
                          setSettingsDirty((d) => ({
                            ...d,
                            troubleMinAvgStablefordPoints: Number(e.target.value),
                          }))
                        }
                      />
                      <TextField
                        label="Hole colour: green from (avg pts)"
                        type="number"
                        fullWidth
                        inputProps={{ min: 0, max: 4, step: 0.1 }}
                        helperText="Left stripe green when average Stableford points on the hole is at or above this value (default 2)."
                        value={
                          settingsDirty.stablefordColorGreenMin ?? settings.stablefordColorGreenMin
                        }
                        onChange={(e) =>
                          setSettingsDirty((d) => ({
                            ...d,
                            stablefordColorGreenMin: Number(e.target.value),
                          }))
                        }
                      />
                      <TextField
                        label="Hole colour: yellow from (avg pts)"
                        type="number"
                        fullWidth
                        inputProps={{ min: 0, max: 4, step: 0.1 }}
                        helperText="Yellow stripe from this value up to (but not including) green. Red below this (default 1)."
                        value={
                          settingsDirty.stablefordColorYellowMin ??
                          settings.stablefordColorYellowMin
                        }
                        onChange={(e) =>
                          setSettingsDirty((d) => ({
                            ...d,
                            stablefordColorYellowMin: Number(e.target.value),
                          }))
                        }
                      />
                      <TextField
                        label="Putts chip: high avg from"
                        type="number"
                        fullWidth
                        inputProps={{ min: 0, max: 6, step: 0.05 }}
                        helperText="Orange Putts pill when average putts on the hole is at or above this (default 2.25). Green below."
                        value={
                          settingsDirty.avgPuttsHighThreshold ?? settings.avgPuttsHighThreshold
                        }
                        onChange={(e) =>
                          setSettingsDirty((d) => ({
                            ...d,
                            avgPuttsHighThreshold: Number(e.target.value),
                          }))
                        }
                      />
                    </Stack>
                  </AccordionDetails>
                </Accordion>
                <Accordion defaultExpanded>
                  <AccordionSummary expandIcon={<Typography component="span">▾</Typography>}>
                    <Typography fontWeight={600}>Data sources</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <DataSourcesSettings
                      onRefreshed={() => {
                        void loadMeta();
                        void refreshRange(year);
                        void loadClubsCatalog();
                      }}
                    />
                  </AccordionDetails>
                </Accordion>
                <Accordion defaultExpanded={false}>
                  <AccordionSummary expandIcon={<Typography component="span">▾</Typography>}>
                    <Typography fontWeight={600}>On Course playbook</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <PlaybookEditor showIntro />
                  </AccordionDetails>
                </Accordion>
                <Button variant="contained" disabled={saving} onClick={() => void saveSettingsForm()}>
                  {saving ? "Saving…" : "Save settings"}
                </Button>
              </Stack>
            ) : (
              <Typography color="text.secondary">Loading…</Typography>
            )}
          </Paper>
        ) : null}

        {import.meta.env.DEV ? (
          <Box sx={{ mt: 4, pb: 2 }}>
            <Typography variant="caption" color="text.secondary" display="block">
              Dev: run <code>uv run golf-ingest dashboard-api</code> then <code>npm run dev</code> in{" "}
              <code>dashboard/</code>.
            </Typography>
          </Box>
        ) : null}
      </Container>
    </Box>
  );
}
