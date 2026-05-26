import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Tabs from "@mui/material/Tabs";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet } from "./api";
import {
  buildCourseOptions,
  defaultCourseKey,
  prepToUnified,
  strategyToUnified,
} from "./onCourseCourseView";
import {
  ON_COURSE_TABS,
  type OnCourseCourseOption,
  type OnCourseCourseRow,
  type OnCourseCourseStrategy,
  type OnCoursePlaybook,
  type OnCoursePrepCourseRow,
  type OnCoursePrepPlan,
  type OnCourseTab,
  type OnCourseUnifiedCourse,
  type OnCourseUnifiedHole,
  type YardageClub,
} from "./onCourseTypes";

interface OnCourseViewProps {
  onBack: () => void;
}

const COURSE_SELECT_KEY = "onCourseSelectedCourse";

function holeCardSx(tone: OnCourseUnifiedHole["tone"]) {
  if (tone === "caution") {
    return { bgcolor: "warning.50", borderColor: "warning.light" };
  }
  if (tone === "press") {
    return { bgcolor: "success.50", borderColor: "success.light" };
  }
  return { bgcolor: "grey.50", borderColor: "divider" };
}

function UnifiedHoleCard({ h }: { h: OnCourseUnifiedHole }) {
  const sx = holeCardSx(h.tone);
  return (
    <Box
      sx={{
        p: 1,
        borderRadius: 1,
        border: 1,
        ...sx,
      }}
    >
      <Typography variant="body2" fontWeight={700}>
        #{h.hole_number}
        {h.par != null ? ` · par ${h.par}` : ""}
        {h.yardage_yards != null ? ` · ${Math.round(h.yardage_yards)}y` : ""}
        {h.stroke_index != null ? ` · SI ${h.stroke_index}` : ""}
        {" · "}
        {h.target}
      </Typography>
      <Typography
        variant="body2"
        sx={{
          mt: 0.5,
          lineHeight: 1.4,
          color: h.tone === "caution" ? "warning.dark" : h.tone === "press" ? "success.dark" : "text.primary",
          fontWeight: h.tone === "caution" ? 600 : 400,
        }}
      >
        {h.detail}
      </Typography>
      {h.subdetail ? (
        <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.25 }}>
          {h.subdetail}
        </Typography>
      ) : null}
    </Box>
  );
}

function CoursePanel({
  options,
  selectedKey,
  onSelect,
  course,
  loading,
}: {
  options: OnCourseCourseOption[];
  selectedKey: string;
  onSelect: (key: string) => void;
  course: OnCourseUnifiedCourse | null;
  loading: boolean;
}) {
  return (
    <Stack spacing={1.5} height="100%">
      <FormControl fullWidth size="small">
        <InputLabel id="on-course-pick">Course</InputLabel>
        <Select
          labelId="on-course-pick"
          label="Course"
          value={selectedKey}
          onChange={(e) => onSelect(String(e.target.value))}
        >
          {options.length === 0 ? (
            <MenuItem value="">
              <em>No courses</em>
            </MenuItem>
          ) : null}
          {options.map((o) => (
            <MenuItem key={o.key} value={o.key}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" width="100%" gap={1}>
                <Box component="span" sx={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                  {o.course_name}
                  {o.tee_name ? ` (${o.tee_name})` : ""}
                  {!o.not_played && o.rounds_count != null ? ` · ${o.rounds_count} rnd` : ""}
                </Box>
                {o.not_played ? <Chip label="Not Played" size="small" sx={{ flexShrink: 0 }} /> : null}
              </Stack>
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {loading ? (
        <Typography color="text.secondary" variant="body2">
          Loading…
        </Typography>
      ) : null}

      {course ? (
        <>
          <Box>
            <Typography variant="subtitle1" fontWeight={700} lineHeight={1.25}>
              {course.course_name}
            </Typography>
            {course.subtitle ? (
              <Typography variant="caption" color="text.secondary" display="block">
                {course.subtitle}
              </Typography>
            ) : null}
          </Box>
          <Typography variant="body2" fontWeight={600} sx={{ lineHeight: 1.4 }}>
            {course.headline}
          </Typography>
          {course.headline !== course.summary_line ? (
            <Typography variant="body2" fontWeight={600}>
              {course.summary_line}
            </Typography>
          ) : null}
          <Stack direction="row" flexWrap="wrap" gap={0.5}>
            {course.attack_holes.map((n) => (
              <Chip key={`a${n}`} size="small" color="success" label={`Press ${n}`} />
            ))}
            {course.caution_holes.map((n) => (
              <Chip key={`c${n}`} size="small" color="warning" label={`Respect ${n}`} />
            ))}
          </Stack>
          <Stack spacing={1.25} sx={{ overflow: "auto", flex: 1, minHeight: 0 }}>
            {course.holes.map((h) => (
              <UnifiedHoleCard key={h.hole_number} h={h} />
            ))}
          </Stack>
          {course.note ? (
            <Typography variant="caption" color="text.secondary">
              {course.note}
            </Typography>
          ) : null}
        </>
      ) : !loading && selectedKey ? (
        <Typography color="text.secondary" variant="body2">
          Could not load this course.
        </Typography>
      ) : null}
    </Stack>
  );
}

function tabIndex(t: OnCourseTab): number {
  return ON_COURSE_TABS.findIndex((x) => x.id === t);
}

function CueBlock({ text, dense }: { text: string; dense?: boolean }) {
  return (
    <Typography
      component="div"
      variant={dense ? "caption" : "body2"}
      sx={{ whiteSpace: "pre-line", lineHeight: 1.45 }}
    >
      {text}
    </Typography>
  );
}

export default function OnCourseView({ onBack }: OnCourseViewProps) {
  const [tab, setTab] = useState<OnCourseTab>("swing");
  const [playbook, setPlaybook] = useState<OnCoursePlaybook | null>(null);
  const [yardages, setYardages] = useState<YardageClub[] | null>(null);
  const [courses, setCourses] = useState<OnCourseCourseRow[] | null>(null);
  const [prepCourses, setPrepCourses] = useState<OnCoursePrepCourseRow[] | null>(null);
  const [selectedCourseKey, setSelectedCourseKey] = useState<string>(() => {
    try {
      return sessionStorage.getItem(COURSE_SELECT_KEY) ?? "";
    } catch {
      return "";
    }
  });
  const [unifiedCourse, setUnifiedCourse] = useState<OnCourseUnifiedCourse | null>(null);
  const [courseLoading, setCourseLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [year, setYear] = useState<number>(2026);

  useEffect(() => {
    void apiGet<{ calendarYear?: number }>("/api/v1/settings")
      .then((s) => setYear(Number(s.calendarYear ?? 2026)))
      .catch(() => undefined);
    void apiGet<OnCoursePlaybook>("/api/v1/on-course/playbook")
      .then(setPlaybook)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(() => {
    if (tab !== "yards") return;
    void apiGet<{ clubs: YardageClub[] }>(`/api/v1/on-course/yardages?year=${year}`)
      .then((r) => setYardages(r.clubs))
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : String(e)));
  }, [tab, year]);

  useEffect(() => {
    if (tab !== "course") return;
    void apiGet<{ courses: OnCourseCourseRow[] }>(`/api/v1/on-course/courses?year=${year}`)
      .then((r) => setCourses(r.courses))
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : String(e)));
    void apiGet<{ courses: OnCoursePrepCourseRow[] }>("/api/v1/on-course/prep/courses")
      .then((r) => setPrepCourses(r.courses))
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : String(e)));
  }, [tab, year]);

  const courseOptions = useMemo(
    () => buildCourseOptions(courses ?? [], prepCourses ?? []),
    [courses, prepCourses],
  );

  useEffect(() => {
    if (courseOptions.length === 0) return;
    if (selectedCourseKey && courseOptions.some((o) => o.key === selectedCourseKey)) return;
    setSelectedCourseKey(defaultCourseKey(courseOptions));
  }, [courseOptions, selectedCourseKey]);

  useEffect(() => {
    if (tab !== "course" || !selectedCourseKey) {
      setUnifiedCourse(null);
      setCourseLoading(false);
      return;
    }

    const option = courseOptions.find((o) => o.key === selectedCourseKey);
    if (!option) return;

    try {
      sessionStorage.setItem(COURSE_SELECT_KEY, selectedCourseKey);
    } catch {
      /* ignore */
    }

    setCourseLoading(true);
    setUnifiedCourse(null);

    const load =
      option.source === "history"
        ? apiGet<OnCourseCourseStrategy>(
            `/api/v1/on-course/course-strategy/${encodeURIComponent(option.course_slug)}?year=${year}`,
          ).then((s) => strategyToUnified(s))
        : apiGet<OnCoursePrepPlan>(
            `/api/v1/on-course/prep/${encodeURIComponent(option.course_slug)}?year=${year}`,
          ).then((p) => prepToUnified(p));

    void load
      .then(setUnifiedCourse)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setCourseLoading(false));
  }, [tab, selectedCourseKey, courseOptions, year]);

  const handleTabChange = useCallback((_: React.SyntheticEvent, value: number) => {
    setTab(ON_COURSE_TABS[value]?.id ?? "swing");
  }, []);

  const panel = (() => {
    if (!playbook && tab !== "yards" && tab !== "course") {
      return <Typography color="text.secondary">Loading…</Typography>;
    }

    switch (tab) {
      case "swing":
        return (
          <Stack spacing={1.5} height="100%">
            <Typography
              variant="h3"
              component="p"
              textAlign="center"
              fontWeight={700}
              sx={{ fontSize: { xs: "2rem", sm: "2.25rem" } }}
            >
              {playbook?.swingCue}
            </Typography>
            <CueBlock text={playbook?.swingThoughts ?? ""} />
          </Stack>
        );
      case "yards":
        if (!yardages) return <Typography color="text.secondary">Loading yardages…</Typography>;
        if (yardages.length === 0) {
          return (
            <Typography color="text.secondary" variant="body2">
              No clubs ≥100 yd carry in {year} range data.
            </Typography>
          );
        }
        return (
          <Table size="small" padding="none">
            <TableHead>
              <TableRow>
                <TableCell>Club</TableCell>
                <TableCell align="right">Carry</TableCell>
                <TableCell align="right">n</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {yardages.map((c) => (
                <TableRow key={c.club}>
                  <TableCell sx={{ fontWeight: 500 }}>{c.club}</TableCell>
                  <TableCell align="right">{c.mean_carry_yards} yd</TableCell>
                  <TableCell align="right" sx={{ color: "text.secondary" }}>
                    {c.n}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        );
      case "pitch":
        return (
          <Table size="small" padding="none">
            <TableHead>
              <TableRow>
                <TableCell>Dist</TableCell>
                <TableCell>Club</TableCell>
                <TableCell>Setup</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(playbook?.pitchRows ?? []).map((row) => (
                <TableRow key={row.dist}>
                  <TableCell>{row.dist}</TableCell>
                  <TableCell>{row.club}</TableCell>
                  <TableCell sx={{ fontSize: "0.75rem", lineHeight: 1.35 }}>
                    {row.stance} · {row.gripSwing}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        );
      case "chip":
        return <CueBlock text={playbook?.chipNotes ?? ""} />;
      case "putt":
        return <CueBlock text={playbook?.puttingRoutine ?? ""} />;
      case "fix":
        return <CueBlock text={playbook?.fixNotes ?? ""} />;
      case "wind":
        return <CueBlock text={playbook?.windNotes ?? ""} />;
      case "course":
        if (courses === null || prepCourses === null) {
          return <Typography color="text.secondary">Loading courses…</Typography>;
        }
        return (
          <CoursePanel
            options={courseOptions}
            selectedKey={selectedCourseKey}
            onSelect={setSelectedCourseKey}
            course={unifiedCourse}
            loading={courseLoading}
          />
        );
      default:
        return null;
    }
  })();

  return (
    <Box
      sx={{
        height: "100dvh",
        display: "flex",
        flexDirection: "column",
        bgcolor: "background.default",
        overflow: "hidden",
      }}
    >
      <AppBar position="static" color="inherit" sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Toolbar variant="dense" sx={{ gap: 1, minHeight: 44 }}>
          <Button onClick={onBack} size="small" sx={{ minWidth: 0, px: 1, textTransform: "none" }}>
            ← Home
          </Button>
          <Typography variant="subtitle1" component="h1" sx={{ fontWeight: 600, flex: 1 }}>
            On Course
          </Typography>
        </Toolbar>
      </AppBar>

      <Tabs
        value={tabIndex(tab)}
        onChange={handleTabChange}
        variant="scrollable"
        scrollButtons="auto"
        allowScrollButtonsMobile
        aria-label="On course sections"
        sx={{
          borderBottom: 1,
          borderColor: "divider",
          minHeight: 56,
          flexShrink: 0,
          bgcolor: "background.paper",
          "& .MuiTab-root": {
            minHeight: 56,
            minWidth: 72,
            px: 1.5,
            py: 1,
            fontSize: "0.9375rem",
            textTransform: "none",
            fontWeight: 700,
            letterSpacing: 0,
          },
          "& .Mui-selected": {
            color: "primary.main",
          },
          "& .MuiTabs-indicator": {
            height: 3,
          },
        }}
      >
        {ON_COURSE_TABS.map((t) => (
          <Tab key={t.id} label={t.label} />
        ))}
      </Tabs>

      {err ? (
        <Typography color="error" variant="caption" sx={{ px: 1.5, pt: 0.5 }}>
          {err}
        </Typography>
      ) : null}

      <Box sx={{ flex: 1, minHeight: 0, overflow: "auto", px: 1.5, py: 1.25 }}>{panel}</Box>
    </Box>
  );
}
