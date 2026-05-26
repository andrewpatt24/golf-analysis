export interface PitchRow {
  dist: string;
  club: string;
  stance: string;
  gripSwing: string;
}

export interface OnCoursePlaybook {
  swingCue: string;
  swingThoughts: string;
  chipNotes: string;
  fixNotes: string;
  windNotes: string;
  puttingRoutine: string;
  pitchRows: PitchRow[];
}

export interface YardageClub {
  club: string;
  mean_carry_yards: number;
  n: number;
  needs_work?: boolean;
}

export interface OnCourseCourseRow {
  course_slug: string;
  course_name: string;
  rounds_count: number;
  worst_hole_numbers: number[];
}

export interface OnCourseHoleCard {
  hole_number: number;
  par: number | null;
  stroke_index: number | null;
  yardage_yards: number | null;
  plays_count: number;
  target: string;
  where_to_improve: string;
  top_improvement: string;
  avg_stableford_points: number | null;
  trouble_hole: boolean;
}

export interface OnCourseCourseStrategy {
  course_slug: string;
  course_name: string;
  rounds_count: number;
  attack_holes: number[];
  caution_holes: number[];
  summary_line: string;
  holes: OnCourseHoleCard[];
  note?: string;
}

export interface OnCoursePrepCourseRow {
  course_slug: string;
  course_name: string;
  tee_name?: string;
  hole_count?: number;
  par_total?: number;
  yardage_total?: number;
}

export interface OnCoursePrepHole {
  hole_number: number;
  par: number;
  stroke_index: number | null;
  yardage_yards: number;
  target: string;
  plan: string;
  press: boolean;
  respect: boolean;
}

export interface OnCoursePrepPlan {
  course_slug: string;
  course_name: string;
  tee_name?: string;
  par_total?: number;
  yardage_total?: number;
  course_rating?: number;
  slope_rating?: number;
  calendar_year: number;
  game_profile: {
    rounds: number;
    penalty_pct: number | null;
    fairway_hit_pct: number | null;
    putts_per_hole: number | null;
    headline: string;
  };
  attack_holes: number[];
  caution_holes: number[];
  summary_line: string;
  holes: OnCoursePrepHole[];
  note?: string;
}

/** Unified course tab view (history or prep). */
export type OnCourseCourseSource = "history" | "prep";

export interface OnCourseCourseOption {
  key: string;
  source: OnCourseCourseSource;
  course_slug: string;
  course_name: string;
  rounds_count?: number;
  tee_name?: string;
  not_played: boolean;
}

export interface OnCourseUnifiedHole {
  hole_number: number;
  par: number | null;
  stroke_index: number | null;
  yardage_yards: number | null;
  target: string;
  detail: string;
  subdetail?: string;
  tone: "caution" | "press" | "neutral";
}

export interface OnCourseUnifiedCourse {
  source: OnCourseCourseSource;
  course_slug: string;
  course_name: string;
  subtitle: string;
  headline: string;
  summary_line: string;
  attack_holes: number[];
  caution_holes: number[];
  holes: OnCourseUnifiedHole[];
  note?: string;
}

export type OnCourseTab = "swing" | "yards" | "pitch" | "chip" | "putt" | "fix" | "wind" | "course";

export const ON_COURSE_TABS: { id: OnCourseTab; label: string }[] = [
  { id: "swing", label: "Swing" },
  { id: "yards", label: "Yards" },
  { id: "pitch", label: "Pitch" },
  { id: "chip", label: "Chip" },
  { id: "putt", label: "Putt" },
  { id: "fix", label: "Fix" },
  { id: "wind", label: "Wind" },
  { id: "course", label: "Course" },
];
