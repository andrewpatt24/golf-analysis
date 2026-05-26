"""Canonical metric definitions — shared by API reference, Strategy proxies, and ESZ/DSZ blocks."""

from __future__ import annotations

from typing import Any

from golf_analysis.scoring_zone_constants import (
    DSZ_ENTRY_BAND_STEP_YARDS,
    DSZ_ENTRY_CLOSE_MAX_YARDS,
    SCORING_ZONE_YARDS,
)

# Short titles for dashboard tiles (Strategy overview chips).
PROXY_SCORECARD_TILES: tuple[dict[str, str], ...] = (
    {
        "key": "proxy_avoid_big_numbers",
        "title": "Avoid big numbers",
        "label": "0 Stableford points per hole (handicap-adjusted blow-up)",
        "metric": "pct_holes",
        "calculation": "100 × (holes with Stableford 0 pts) / (holes with Stableford points recorded).",
        "direction": "lower_is_better",
    },
    {
        "key": "proxy_penalties",
        "title": "Penalties",
        "label": "Penalty holes (hole penalties > 0)",
        "metric": "pct_holes",
        "calculation": "100 × (holes with penalty > 0) / (holes with scorecard strokes).",
        "direction": "lower_is_better",
    },
    {
        "key": "proxy_fairway",
        "title": "Fairway",
        "label": "Fairway outcomes (HIT / LEFT / RIGHT only)",
        "metric": "pct_hit",
        "calculation": "100 × HIT / (HIT + LEFT + RIGHT) among holes with a fairway decision.",
        "direction": "higher_is_better",
    },
    {
        "key": "proxy_putting_load",
        "title": "Putting load",
        "label": "Putting load (sum putts / holes with putt count)",
        "metric": "putts_per_hole",
        "calculation": "Sum of hole putts / holes where putts are recorded on the scorecard.",
        "direction": "lower_is_better",
    },
)

PROXY_ESZ: dict[str, str] = {
    "key": "proxy_esz",
    "title": "ESZ",
    "label": "ESZ — in scoring zone by regulation (≤100 yd by stroke par−2)",
    "metric": "pct_success",
    "calculation": (
        "Per hole with shot trace: first shot end within scoring zone on or before stroke (par − 2). "
        "ESZ % = 100 × success holes / holes evaluated."
    ),
    "direction": "higher_is_better",
}

PROXY_DSZ: dict[str, str] = {
    "key": "proxy_dsz",
    "title": "DSZ",
    "label": "DSZ — down in three from inside scoring zone",
    "metric": "pct_success",
    "calculation": (
        "Per hole that entered the zone with scorecard gross S: strokes inside zone = S − traced shots before "
        "first ≤100 yd end. DSZ success when ≤3. DSZ % = 100 × success / zone-entry holes (not mean shots + mean putts)."
    ),
    "direction": "higher_is_better",
}

ENTRY_DISTANCE_COLUMNS: tuple[dict[str, str], ...] = (
    {
        "id": "pct_success",
        "title": "DSZ %",
        "calculation": "Share of band holes with scorecard strokes inside zone ≤3 (per hole, then averaged).",
    },
    {
        "id": "mean_strokes_inside_zone",
        "title": "avg strokes inside",
        "calculation": "Mean (gross − traced shots before 100 yd) for holes in the band.",
    },
    {
        "id": "pct_green",
        "title": "Reached green %",
        "calculation": "Any in-zone traced shot with end lie = Green (indicative; trace often incomplete).",
    },
    {
        "id": "mean_shots_before_putts",
        "title": "Shots before putts",
        "calculation": "Scorecard: gross − putts − traced shots before zone (pitch/chip/approach).",
    },
    {
        "id": "mean_putts",
        "title": "Mean putts",
        "calculation": "Scorecard putts on the hole.",
    },
)

ENTRY_DISTANCE_NOTE = (
    "Bands: 0–30 yd then 10 yd steps. DSZ and shots-before-putts use scorecard gross minus "
    "traced shots before 100 yd (and minus putts for the pitching split). "
    "Reached-green % uses Garmin shot lie on the trace — often incomplete. "
    "The 0–30 yd band has noisy entry distances and trace lies; prefer 30+ yd rows for trends."
)

TREND_METRICS: tuple[dict[str, Any], ...] = (
    {
        "id": "fw_pct",
        "label": "Fairway %",
        "kind": "percent",
        "data_key": "fw_pct",
        "calculation": "100 × fairway HIT / fairway decided for the round.",
    },
    {
        "id": "esz_pct",
        "label": "ESZ %",
        "kind": "percent",
        "data_key": "esz_pct",
        "calculation": "Round rollup from shot trace (same ESZ rule as headline).",
    },
    {
        "id": "dsz_pct",
        "label": "DSZ %",
        "kind": "percent",
        "data_key": "dsz_pct",
        "calculation": "Round rollup from shot trace + scorecard (same DSZ rule as headline).",
    },
    {
        "id": "strokes",
        "label": "Strokes",
        "kind": "count",
        "data_key": "strokes",
        "calculation": "Round gross strokes on the scorecard.",
    },
    {
        "id": "holes_completed",
        "label": "Holes scored",
        "kind": "count",
        "data_key": "holes_completed",
        "calculation": "Holes with scores on the card.",
    },
    {
        "id": "putts_per_hole",
        "label": "Putts / hole played",
        "kind": "rate",
        "data_key": "putts_per_hole",
        "calculation": "Total putts on scored holes ÷ holes played (fair for 9- and 18-hole rounds).",
    },
    {
        "id": "penalty_holes_pct",
        "label": "Penalty holes %",
        "kind": "percent",
        "data_key": "penalty_holes_pct",
        "calculation": "100 × penalty holes ÷ holes played.",
    },
    {
        "id": "stableford_zero_pct",
        "label": "0-pt holes %",
        "kind": "percent",
        "data_key": "stableford_zero_pct",
        "calculation": "100 × Stableford 0-pt holes ÷ holes played.",
    },
    {
        "id": "stableford_pts_per_hole",
        "label": "Stableford pts / hole",
        "kind": "rate",
        "data_key": "stableford_pts_per_hole",
        "calculation": "Round Stableford points ÷ holes played.",
    },
    {
        "id": "esz_holes_eval",
        "label": "ESZ holes (evaluated)",
        "kind": "count",
        "data_key": "esz_holes_eval",
        "calculation": "Holes with ESZ evaluation in trace for the round.",
    },
    {
        "id": "dsz_zone_holes",
        "label": "DSZ holes (in zone)",
        "kind": "count",
        "data_key": "dsz_zone_holes",
        "calculation": "Holes that entered the scoring zone (DSZ denominator).",
    },
    {
        "id": "esz_success_holes",
        "label": "ESZ success holes",
        "kind": "count",
        "data_key": "esz_success_holes",
        "calculation": "ESZ successes in the round.",
    },
    {
        "id": "dsz_success_holes",
        "label": "DSZ success holes",
        "kind": "count",
        "data_key": "dsz_success_holes",
        "calculation": "DSZ successes in the round.",
    },
    {
        "id": "mean_spi",
        "label": "Mean strokes / hole",
        "kind": "count",
        "data_key": "mean_strokes_per_hole",
        "calculation": "Gross strokes ÷ holes played.",
    },
)

TRENDS_NOTE = (
    "Round-by-round chart: oldest → newest. Rates and percentages use holes played as the divisor "
    "so partial rounds compare fairly. Mixed percent + rate/count series use left / right Y-axes."
)

def proxy_tile_spec(key: str) -> dict[str, str] | None:
    for spec in PROXY_SCORECARD_TILES:
        if spec["key"] == key:
            return spec
    if key == PROXY_ESZ["key"]:
        return PROXY_ESZ
    if key == PROXY_DSZ["key"]:
        return PROXY_DSZ
    return None


def build_metrics_reference() -> dict[str, Any]:
    """Static reference payload (no Garmin file required)."""

    from golf_analysis.garmin_esz_dsz import ESZ_DSZ_DATA_MODEL

    return {
        "version": 1,
        "constants": {
            "scoring_zone_yards": SCORING_ZONE_YARDS,
            "dsz_entry_band_step_yards": DSZ_ENTRY_BAND_STEP_YARDS,
            "dsz_entry_close_max_yards": DSZ_ENTRY_CLOSE_MAX_YARDS,
        },
        "scoring_zone": {
            "title": f"Scoring zone ({int(SCORING_ZONE_YARDS)} yd)",
            "esz": {
                "title": PROXY_ESZ["title"],
                "definition": PROXY_ESZ["label"],
                "calculation": PROXY_ESZ["calculation"],
            },
            "dsz": {
                "title": PROXY_DSZ["title"],
                "definition": PROXY_DSZ["label"],
                "calculation": PROXY_DSZ["calculation"],
            },
        },
        "proxy_tiles": [*PROXY_SCORECARD_TILES, PROXY_ESZ, PROXY_DSZ],
        "entry_distance": {
            "title": "DSZ by entry distance",
            "band_note": ENTRY_DISTANCE_NOTE,
            "columns": list(ENTRY_DISTANCE_COLUMNS),
            "data_quality": {
                "shots_before_putts": "scorecard",
                "mean_putts": "scorecard",
                "pct_green": "shot_trace_lie",
                "pct_success": "scorecard_minus_traced_outside",
            },
        },
        "trends": {
            "note": TRENDS_NOTE,
            "metrics": list(TREND_METRICS),
            "default_metric_ids": [m["id"] for m in TREND_METRICS if m["kind"] == "percent"],
        },
        "esz_dsz_data_model": ESZ_DSZ_DATA_MODEL,
        "data_sources": {
            "primary": "Garmin Golf Community export JSON (GOLF_GARMIN_JSON).",
            "distance_tiers": list(ESZ_DSZ_DATA_MODEL.get("distance_to_pin_per_shot_end", [])),
            "caveat": (
                "Incomplete shot traces can mis-state shots before zone when the first traced shot is already "
                "inside 100 yd."
            ),
        },
    }
