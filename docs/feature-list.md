Rapsado feature list
---
List of shots with stats to drill down in to particular shots
Distribution of shots with length and lateral dispersion per club or multi club with colours
Dispersion index v.s. HCP range
Distance per club with Average and 90p, 10p calcualtion based on normal distribution
Club gapping
Landing side comparison
shot shape frequency
Shot shapecomparison with seletable club comparisons

Specific club comparison:
Accuracy - alanding side analysis, percentage of left, right straight, Dispersion
Distance - Landing side distance comprison, launch angle optimisation, smash factor optimisation
Consistency - Ball striking index, shot shape frequency, Perormance distribution with selectable metrics

All with key takeaways


Garmin
--
Overview of rounds with scores, stableford etc.
Full scorecard clicking in to each round
par/bogey/double bogey statistics
fairways hit, GIRs, Putts, Up & Downs, Penalties
Shot maps
Course stats - average round and distribution, avg of each statistic and distribution
Performance stats - Calculated Handicap, best score over 9/18 holes, avg score over 9/18 holes
Shot overview, Drive, approach, chip, putt strokes gained v.s. similar handicap

**Revisit — Garmin ESZ / distance heuristic:** When many holes only have the straight-line `meters` fallback (no pin / endLoc / orientation distances), ESZ can read **high** vs real geometry. Come back to: ESZ split or filter by distance tier, optional “geometry-only” ESZ, or a more conservative heuristic (`golf_analysis/garmin_esz_dsz.py`; Strategy tab shows Geometry vs Heuristic counts).


Things id also like to see
--
Per Course if played multiple times what is the most troublesome holes, avg. score and shot maps (multiple rounds on one graph coloured by outcome par/bogey/ db etc.+)

