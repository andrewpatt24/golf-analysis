# Comprehensive analysis plan: WHERE → WHY (Garmin + Rapsodo)

This plan ties together the framework writeups in this folder with the repo’s **on-course** methodology and **range** data so you can prioritise practice that moves the scorecard.

**Inputs (read these first):**

| Doc | Role in this plan |
|-----|-------------------|
| [strokes-gained.md](./strokes-gained.md) | What SG means, categories (OTT / APP / ATG / Putting), interpretation (+/− vs benchmark). |
| [scoring-method.md](./scoring-method.md) | ESZ / DSZ mental model, 100-yd focus, “purposeful practice” loop from round stats. |
| [rapsado-metrics.md](./rapsado-metrics.md) | Sensible order for LM metrics (carry → speed → path → start line → smash → advanced). |
| [on-course-analysis-methodology.md](../on-course-analysis-methodology.md) | **Where** layer: `golf-export.json` / `shotDetails` for geometry; **100 yd / 30 yd** rings need haversine (not in CLI report yet). **SG:** per-shot SG is **not** on each `shotDetails` nested shot in typical exports; Garmin attaches **`strokesGained`** to **sample** rows under `last10DataApproach` / `last10DataChip` (`shotOrientationDetail`) and headline `last10DataStats.strokesGainedRatings` — see `golf_analysis.analysis_plan_report`. |

---

## 0. North-star questions

1. **WHERE** am I losing the most strokes relative to my target handicap (and relative to ESZ/DSZ-style goals)?
2. **WHY** might that be — which **recurring on-course situations** (club + distance + lie) match patterns in my **range** dispersion and delivery numbers?
3. **WHAT** should I practise on the range this week so the **next** on-course review moves the right SG / scoring-method levers?

---

## Phase A — WHERE (Garmin-first; score + SG + geography)

**Goal:** Rank **bag segments and course phases** by **expected score impact**, not raw averages alone.

### A.1 Strokes gained lens ([strokes-gained.md](./strokes-gained.md))

- **Aggregate** per round and rolling windows (e.g. last 5 / 20 rounds): **SG:OTT**, **SG:APP**, **SG:ATG**, **SG:Putting** vs a **single chosen benchmark** (handicap-appropriate, not necessarily Tour).
- **Drill-down:** within the worst category, split by **distance bucket** (e.g. approach: 150–175 yd, 125–150 yd) and **lie** where Garmin provides it.
- **Data in your export (verified):** `shotDetails` → nested `shots[]` **do not** include `strokesGained` on every shot. Garmin **does** include `strokesGained` on **sample** rows inside **`last10DataApproach.shotOrientationDetail`** and **`last10DataChip.shotOrientationDetail`**, plus **`last10DataStats.strokesGainedRatings`**. Use those for **first-pass WHERE** (`golf-ingest analysis-plan-report`). They summarise a **recent window**, not full history. A **custom baseline table** is still the path if you want SG on **every** shot without Garmin’s sampling.

### A.2 Scoring Method lens ([scoring-method.md](./scoring-method.md))

- **Map rounds to ESZ / DSZ style outcomes** using the same geometry you already use for analysis:
  - **Enter scoring zone:** ball first **≤100 yd** to pin within your chosen shot budget (regulation or skill-tier variant).
  - **Down in three:** once inside 100 yd, **≤3 strokes** to hole out (wedge game + two-putt cap), aligned with DSZ.
- **Purposeful practice link:** the **worst holes / worst flags** (failed ESZ, failed DSZ, penalties) become the **named problems** you later match to range work (Phase B).

### A.3 Hybrid geography + short game ([on-course-analysis-methodology.md §5](../on-course-analysis-methodology.md))

- Keep **100 yd** and **30 yd** rings and **putt vs chip residual** logic as the **canonical “where on earth”** view when `shotType` is noisy.
- **Report tiles:** e.g. “strokes / holes where ball never entered ≤100 yd in regulation”, “shots gained/lost inside 30 yd band”, “three-putt rate from X–Y feet” once putting distances are reliable.

### A.4 “Biggest gains” synthesis (WHERE dashboard)

Produce a **single ranked list** (refresh after each batch of rounds), for example:

| Rank | Theme | Evidence |
|------|--------|----------|
| 1 | Worst SG category (or proxy) | Sum SG or fallback metric |
| 2 | Worst ESZ/DSZ segment | % failures, penalties |
| 3 | Worst distance × lie bucket | Count + strokes vs par |

**Output:** “Top 3 themes this month” → those themes **select** which on-course **shot archetypes** you will mine in Phase B (e.g. “150-yd fairway approaches that miss green wide”).

---

## Phase B — WHY (course archetypes ↔ range distributions)

**Goal:** For each **high-impact on-course theme** from Phase A, find **matching range shots** and judge **dispersion + delivery** vs simple rules of thumb.

### B.1 Define “usual on-course shots”

From Garmin `shotDetails` (and scorecard context):

- **Bin** shots by: **club label** (or inferred club), **start distance to pin** (or start lie category), **lie**, optional **miss direction** if derivable.
- **Match key:** loose join to range — e.g. same **club** + **carry distance bucket** (±10–15 yd) on `range_shots` / `list_source_kind` in **practice + combine** cohort only (see `golf_analysis.range_analysis`).

Document **match tolerance** explicitly in your notebooks/scripts so you can tighten or loosen it.

### B.2 Dispersion gate (first-pass rule)

For matched range shots at a comparable **carry** \(L\) (yards):

- Use **lateral dispersion** vs **length dispersion** (define length as along-target or as carry spread — **pick one convention** and keep it consistent).
- **Simple ratio rule (your spec):** lateral should not dominate length; operationally: **lateral spread ≤ 10% of nominal distance** for a **target** shot (e.g. 150 yd carry → lateral spread cap **15 yd** on the *dispersion* summary you use — e.g. std or IQR of `offline_yards`, not a single shot).
- **Flag clubs/buckets** that violate the gate most often → priority **WHY** candidates.

*Clarification to lock when implementing:* use **std**, **IQR**, or **95% interval** for “spread”; offline sign convention from Rapsodo export should match “left/right” in your plots.

### B.3 “Which LM metrics explain the lateral miss?” ([rapsado-metrics.md](./rapsado-metrics.md))

For buckets that fail the dispersion gate, walk **diagnostics** in the coach order, but **filter** by what physics plausibly ties to **curve / start line**:

1. **Carry + club speed** — distance control vs effort (is the miss long/short systematic?).
2. **Club path** and **launch direction** — start line + shape ([rapsado-metrics.md](./rapsado-metrics.md) §3–4).
3. **Smash factor** — strike quality if distance is erratic at same speed.
4. **Spin axis / spin** and **descent angle** (irons) — tilt and landing behaviour when lateral is OK but left-right misses persist on course from curvature.

### B.4 “Ideal range” vs your distribution

- Build a **small table per club** (you maintain): ideal ranges for **path**, **launch direction**, **descent angle** (irons), **spin axis**, etc. (seed hints from [rapsado-metrics.md](./rapsado-metrics.md) §6 where applicable).
- For each **failing bucket**, compare **your distribution** (median, IQR, % outside band) to the ideal band.
- **Rank LM metrics** by: (a) how far the distribution sits outside the band, (b) how strong the bucket’s link is to Phase A **score** themes.

**Output:** “For 7i 145–160 yd: dispersion fails gate; path skewed out-to-in; launch direction left — primary range focus: path + start line; secondary: spin axis.”

---

## Phase C — WHAT (practice plan for the week)

- **1–2 themes max** from Phase A (score impact).
- **2–3 measurable range targets** from Phase B (dispersion gate + 1–2 LM metrics each).
- **Re-check** after N range sessions or M rounds: did the **WHERE** tiles move?

---

## Dependencies and honesty list

| Item | Status |
|------|--------|
| Garmin round + shot geometry in SQLite / JSON | `shotDetails` in `extra_json` when ingested; geometry reports still to be built. |
| Rapsodo shots + `list_source_kind` | Available via current pipeline. |
| **Per-shot SG on every historical shot** | **Not** in `shotDetails` tree in sample export — use **`last10Data*`** samples or roll your own baseline ([methodology §3](../on-course-analysis-methodology.md)). |
| **Automated Garmin ↔ range join** | Design in Phase B; not in `analysis-plan-report` v1. |

---

## Open decisions (v1 defaults in tooling)

1. **SG benchmark:** Garmin’s embedded values (implicit benchmark). For custom handicap benchmarks, replace with your own table later.
2. **Dispersion statistic:** **Sample stdev** of `offline_yards` and `carry_yards` (`golf-ingest analysis-plan-report`).
3. **Length dispersion:** `std(carry)` vs **mean carry** for the 10% lateral cap.
4. **Club mapping:** manual until a normalisation table exists.
5. **Combine in cohort:** **Yes** (included with practice in `range_analysis` cohort).

*This document is the umbrella plan; the sibling files in `docs/frameworks/` supply the conceptual vocabulary; `docs/on-course-analysis-methodology.md` supplies the Garmin-side mechanics.*

**First-pass automation:** `golf-ingest analysis-plan-report` (Garmin JSON + SQLite library).
