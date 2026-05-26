import type {
  OnCourseCourseOption,
  OnCourseCourseRow,
  OnCourseCourseStrategy,
  OnCoursePrepCourseRow,
  OnCoursePrepPlan,
  OnCourseUnifiedCourse,
  OnCourseUnifiedHole,
} from "./onCourseTypes";

export function buildCourseOptions(
  history: OnCourseCourseRow[],
  prep: OnCoursePrepCourseRow[],
): OnCourseCourseOption[] {
  const historySlugs = new Set(history.map((c) => c.course_slug));
  const played: OnCourseCourseOption[] = history.map((c) => ({
    key: `history:${c.course_slug}`,
    source: "history",
    course_slug: c.course_slug,
    course_name: c.course_name,
    rounds_count: c.rounds_count,
    not_played: false,
  }));
  const manual: OnCourseCourseOption[] = prep
    .filter((c) => !historySlugs.has(c.course_slug))
    .map((c) => ({
      key: `prep:${c.course_slug}`,
      source: "prep",
      course_slug: c.course_slug,
      course_name: c.course_name,
      tee_name: c.tee_name,
      not_played: true,
    }));
  return [...played, ...manual];
}

export function strategyToUnified(s: OnCourseCourseStrategy): OnCourseUnifiedCourse {
  const attack = new Set(s.attack_holes);
  const caution = new Set(s.caution_holes);

  const holes: OnCourseUnifiedHole[] = s.holes.map((h) => {
    let tone: OnCourseUnifiedHole["tone"] = "neutral";
    if (h.trouble_hole || caution.has(h.hole_number)) tone = "caution";
    else if (attack.has(h.hole_number)) tone = "press";

    const detail = h.trouble_hole
      ? h.top_improvement
      : attack.has(h.hole_number)
        ? "Maintain your scoring method — this hole has been a strength."
        : h.top_improvement;

    return {
      hole_number: h.hole_number,
      par: h.par,
      stroke_index: h.stroke_index,
      yardage_yards: h.yardage_yards,
      target: h.target,
      detail,
      subdetail: h.trouble_hole ? h.where_to_improve : undefined,
      tone,
    };
  });

  return {
    source: "history",
    course_slug: s.course_slug,
    course_name: s.course_name,
    subtitle: `${s.rounds_count} round${s.rounds_count === 1 ? "" : "s"} in your history`,
    headline: s.summary_line,
    summary_line: s.summary_line,
    attack_holes: s.attack_holes,
    caution_holes: s.caution_holes,
    holes,
    note: s.note,
  };
}

export function prepToUnified(p: OnCoursePrepPlan): OnCourseUnifiedCourse {
  const holes: OnCourseUnifiedHole[] = p.holes.map((h) => ({
    hole_number: h.hole_number,
    par: h.par,
    stroke_index: h.stroke_index,
    yardage_yards: h.yardage_yards,
    target: h.target,
    detail: h.plan,
    tone: h.respect ? "caution" : h.press ? "press" : "neutral",
  }));

  const meta: string[] = [];
  if (p.tee_name) meta.push(p.tee_name);
  if (p.yardage_total != null) meta.push(`${p.yardage_total} yd`);
  if (p.par_total != null) meta.push(`par ${p.par_total}`);
  if (p.course_rating != null) meta.push(`CR ${p.course_rating}`);
  if (p.slope_rating != null) meta.push(`SR ${p.slope_rating}`);

  return {
    source: "prep",
    course_slug: p.course_slug,
    course_name: p.course_name,
    subtitle: meta.join(" · "),
    headline: p.game_profile.headline,
    summary_line: p.summary_line,
    attack_holes: p.attack_holes,
    caution_holes: p.caution_holes,
    holes,
    note: p.note,
  };
}

export function defaultCourseKey(options: OnCourseCourseOption[]): string {
  const woldingham = options.find((o) => o.course_slug === "woldingham-white");
  if (woldingham) return woldingham.key;
  return options[0]?.key ?? "";
}
