# On-course analysis methodology (Garmin Golf Community)

This document describes **how we want to analyse** Garmin / on-course data to answer **where** the game leaks strokes and proximity, and what we must build or license ourselves. **Rapsodo / range data** is intentionally out of scope here; that layer is for **how** (mechanics, delivery) and will be wired in later.

---

## 1. Purpose: “where” vs “how”

| Layer | Source (planned) | Question |
|-------|------------------|----------|
| **Where** | Garmin Golf Community export (`golf-export.json` + `shotDetails`) | On the course, from which **lies and distances** do we lose shots vs a baseline? Where do we fail the **100 yd / 30 yd** gates? |
| **How** | Rapsodo / range (later) | What are the **swing / strike** patterns that explain the misses? |

All logic below applies to the **where** layer only.

---

## 2. What we already have (Garmin export)

From `garmin-golf-sync` / bookmarklet-shaped JSON:

- **Scorecards:** `summary`, `details` — holes, pars, strokes, putts (where recorded), Stableford, etc.
- **Shots:** `shotDetails` → `holeShots` → `shots[]` with `startLoc` / `endLoc` (semicircles + `lie`), `pinPosition`, `shotType`, `meters`, order fields.

**Verified on a full export:** we can derive **straight-line distance to the pin** before and after essentially every tracked shot (pin + start/end present). **`strokesGained` is not** present on each nested shot inside `shotDetails` / `holeShots` / `shots[]` in the export we checked. Garmin **does** attach **`strokesGained`** to **sample** rows in **`last10DataApproach.shotOrientationDetail`**, **`last10DataChip.shotOrientationDetail`**, and headline **`last10DataStats.strokesGainedRatings`** — use those for quick SG views, or compute SG yourself from a baseline table ([§3](#3-external-dependency-strokes-gained-baseline-table)) if you need **every** shot.

---

## 3. External dependency: strokes gained baseline table

To compute **our own** strokes gained per shot we need a **baseline expected strokes** function \(E(\text{lie}, \text{yards to pin})\) (or equivalent tables).

- **Input:** lie bucket (tee, fairway, rough, bunker, green — mapped from Garmin `lie` strings) + distance to pin (yards; we use haversine on published coordinates).
- **Output:** expected remaining strokes to hole out from that state.
- **Per-shot SG (model-relative):**  
  \(\text{SG} \approx E_{\text{before}} - E_{\text{after}} - 1\)  
  (hole-out ⇒ \(E_{\text{after}} \approx 0\)).

**We must obtain or build:**

1. A **licensed or openly documented** SG table (CSV/JSON) with fine enough bins by lie + distance, **or**
2. A **smoothed model** fit to public aggregate data, with documented assumptions.

**Project tasks:** vendor the table file (e.g. `data/reference/sg_baseline.json`), document **source + version + date**, and pin **reproducibility** (same table → same SG numbers). Legal/licence text belongs next to the artefact, not only in this doc.

**Caveats to bake into analysis:** penalties / drops, wrong lie labels, and “distance to pin” vs tour definitions (we stay internally consistent).

---

## 4. Bucketing for “driving / approach / chipping / putting”

We want a **single story** that mixes:

1. **Strokes gained** (vs our baseline) aggregated by **shot category** — e.g. tee, approach (>100 yd or off-green long), short game, putt — using Garmin `shotType` + lie where helpful, **and**
2. **Geography / scoring-method flags** from shot geometry (below), so we can say e.g. “approach SG is fine from 150 but poor when the ball never enters the 100 yd ring in regulation.”

**Implementation sketch:**

- Map each shot to an **SG bucket** (drive / approach / chip / putt) for reporting, aligned as closely as possible to Mark Broadie–style categories, while **also** storing the **geography flags** from §5 as orthogonal columns (not mutually exclusive filters).

---

## 5. Hybrid geography + putts model (100 yd, 30 yd, chip inference)

Putting vs chipping is **ambiguous** in raw `shotType` (e.g. many `UNKNOWN` shots). We therefore use **distance rings** plus **official putt counts** to structure short-game analysis.

### 5.1 Step (a) — Outside vs inside **100 yards** to pin

Using shot **end** positions vs **pin**:

- Compute **yardage to pin** after each shot (same method as already validated on the export).
- **Flag / hole metrics:** first shot index where ball ends **≤ 100 yd** to pin; compare to “regulation” windows (e.g. by par, or par−2) for **position vs plan** narratives.

This is the **outer ring** for “you are in scoring range.”

### 5.2 Step (b) — **Inside 100 yards**: split **30 yd ring**, **putts**, **residual = chips**

Once the ball has entered the **≤ 100 yd** zone (first qualifying shot end), we analyse only shots **from that point until the ball is holed** (or until the scorecard closes the hole).

**(a1) Inside 30 yards (approach / proximity band)**  
- Using shot ends vs pin: flag shots that end **≤ 30 yd** from pin (and optionally strokes that **cross** the ring).  
- Use this as a **tight proximity** signal (almost on green or short pitch range) distinct from “merely inside 100.”

**(a2) Putts vs inferred chips**  
- **Putts:** prefer **hole-level `putts`** from the scorecard when present; align to terminal green / `UNKNOWN` / last strokes where possible. When misalignment appears, fall back to **lie = Green** + order heuristics.  
- **Chips (operational definition):** strokes in the **inside-100** segment that are **not** counted as the **inside-30** “approach proximity” bucket in the sense of (a1), and **not** counted as **putts** in (a2).  

Equivalently, a working formula to document in code comments:

> **Chip-like strokes (inside 100)** ≈ *(strokes from first “inside 100” until hole-out)* **minus** *(strokes classified as inside-30 proximity per (a1) rules)* **minus** *(putts attributed to that closing segment)*.

**Refinement note:** (a1) can be defined as “**ends** inside 30” only, or “**any** shot whose arc crosses into 30” — pick one in implementation and keep it stable. The first is simpler given we only have start/end, not full ball flight.

### 5.3 Edge case — **holed out (or closed) with 0 putts** after a shot that ends on the green

Sometimes a **drive, approach, or pitch** ends **on the green** (per `endLoc.lie` / geometry), the scorecard records **0 putts** for the hole, and that stroke is **the last tracked shot** on the hole (i.e. it **agrees with the scorecard** as finishing the hole — no further shots listed).

Treat this as a **closed hole without a separate putting phase**:

- **Do not** run the **chip vs putt residual** split for a “short game segment” after the ball was already on the green (there is nothing left to decompose).
- **Do not** force **chip / inside-30** bookkeeping that would imply extra strokes around the green when the official line is **zero putts** and the narrative is **one stroke to the green that ended the hole** (e.g. holed approach, or scorecard/stats alignment that folded the close into that shot).

Still record **SG** for that terminal shot if the baseline applies, and optional flags like **“hole out / GIR finish, 0 putts”** for reporting.

This rule is **scorecard-truth wins** when shot trace + `putts` + **last shot** all agree; it prevents bogus “missing chips” when the model would otherwise expect putt strokes that never happened on the card.

### 5.4 Why mix with SG

- **SG** answers “**value** of this shot vs baseline” (good bad luck vs skill over many rounds).  
- **100 / 30 / putt-residual** answers “**where on the map** did the hole go wrong?” even when SG noise is high.

**Reporting:** for each hole (or round), emit both **SG sum by bucket** and **geography flags** (e.g. never inside 100 in par−2; inside 100 but high chip-like count; low putts but many 30–100 yd strokes, etc.).

---

## 6. What we need to implement effectively

| Item | Owner | Notes |
|------|--------|------|
| SG baseline table | External file + licence | Versioned artefact in repo or `data/reference/`. |
| `lie` → SG bucket mapping | Us | Normalise Garmin strings (`TeeBox`, `Fairway`, `Rough`, …). |
| Haversine yardages pin↔start / pin↔end | Us | Already validated on export. |
| Per-shot SG pipeline | Us | `E(before) - E(after) - 1` + hole boundaries + penalties. |
| 100 yd / 30 yd flags + chip residual | Us | Implement §5–§5.3; unit tests on synthetic hole geometry + hole-out edge case. |
| Round / hole joins | Us | `scorecardId` + `holeNumber`; merge `details` with `shotDetails`. |
| QA dashboard or CLI report | Us | Regenerate insights after each new `golf-export.json`. |

---

## 7. Out of scope (next document)

- **Rapsodo / range:** club delivery, speed, spin, dispersion — “**how**” to change the pattern the **where** layer already highlighted.

---

## 8. Open decisions

1. **Exact (a1) rule:** end position only vs crossing 30 yd with segment–pin distance (needs more geometry).  
2. **Putt alignment:** strict use of scorecard `putts` vs shot-level detection when they disagree; **§5.3** when scorecard says **0 putts** and the last shot lands on green and matches the hole end, **skip** chip/putt residual for that hole’s closing.  
3. **SG table choice:** tour baselines vs amateur-adjusted baselines (amateur is usually more realistic for club golf).  
4. **Stableford rounds:** narrative should reference **both** points and strokes where useful.

---

*Last updated: aligns with current `golf-export.json` shape and the hybrid 100 yd / 30 yd / putt-residual chip logic requested for documentation.*
