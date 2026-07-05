export type DrillCategory = "putting" | "chipping" | "range";

export type DrillTrackingType =
  | "score_out_of_total"
  | "boolean_completion"
  | "points_based"
  | "streak"
  | "total_attempts"
  | "club_focus_session";

export interface DrillDefinition {
  id: string;
  title: string;
  description: string;
  equipment_needed: string[];
  distances: string[];
  attempts_per_distance: number | null;
  is_timed: boolean;
  tracking_type: DrillTrackingType;
  tracking_metrics: string[];
  penalty_reset_rule: string | null;
  success_target: string;
  expected_duration_minutes?: number | null;
  expected_total_attempts?: number | null;
  max_points?: number | null;
  category: DrillCategory;
  last_played_at?: string | null;
  days_since_last_played?: number | null;
  session_count?: number;
  is_customized?: boolean;
  rapsodo_mode?: string;
  rapsodo_mode_label?: string;
  default_aim?: string;
  suggested_clubs?: string[];
}

export type DrillSortOrder = "catalog" | "recently_practiced" | "due_for_practice";

export const DRILL_SORT_LABELS: Record<DrillSortOrder, string> = {
  catalog: "Default order",
  recently_practiced: "Recently practiced",
  due_for_practice: "Due for practice",
};

export interface DrillSessionResult {
  score?: number | null;
  total?: number | null;
  completed?: boolean | null;
  points?: number | null;
  max_points?: number | null;
  streak?: number | null;
  attempts?: number | null;
  club?: string | null;
  aim?: string | null;
  combine_score?: number | null;
}

export interface DrillSession {
  id: string;
  drill_id: string;
  category: DrillCategory;
  tracking_type: DrillTrackingType;
  logged_at: string;
  result: DrillSessionResult;
  notes?: string | null;
  summary?: string;
}

export const DRILL_CATEGORY_LABELS: Record<DrillCategory, string> = {
  putting: "Putting",
  chipping: "Chipping",
  range: "Range",
};

export const DRILL_CATEGORIES: DrillCategory[] = ["putting", "chipping", "range"];
