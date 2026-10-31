# Author Outbreak Branch Summary

This summary treats the supplement author outbreak list as the fixed event set.
All tests in this post-hoc branch are exploratory; no confirmatory primary endpoint was prespecified.
Independent nulls preserve year-month counts; month rotations preserve within-month spacing; year-season shifts preserve within-year cluster spacing across month boundaries with a shared +/-15-day shift.
Holm adjustment covers all 87 tests across all three null models and all distance/coincidence specifications in this branch.
Each null uses 50,000 replicates; retained draws are shared across specifications within a family. Monte Carlo intervals use Clopper-Pearson bounds with Bonferroni coverage across 87 tails; Holm-transformed endpoint bounds are reported separately from adjusted estimates.
ICME tests use the same direct Richardson-Cane catalog and only post-1996 outbreak starts; counts and denominators are family-specific.
The key-results CSV contains 87 nominal and Holm-adjusted tests.

## Inputs
- Distance summary present: True
- Coincidence summary present: True
- Author type summary present: True
- Agreement summary present: True

## Key Questions
1. Do the author-provided outbreak dates cluster unusually near HCS crossings?
- independent dates, distance observed_mean_abs_distance: observed 3.90 vs null 4.10 (nominal p=0.063019; Holm p=1.000000); independent dates, coincidence plus_minus_1d: observed 151.00 vs null 116.98 (nominal p=0.000080; Holm p=0.006880); month-cluster rotations, distance observed_mean_abs_distance: observed 3.90 vs null 4.10 (nominal p=0.060179; Holm p=1.000000); month-cluster rotations, coincidence plus_minus_1d: observed 151.00 vs null 116.88 (nominal p=0.000120; Holm p=0.010200); year-season cluster shifts, distance observed_mean_abs_distance: observed 3.90 vs null 4.14 (nominal p=0.034119; Holm p=1.000000); year-season cluster shifts, coincidence plus_minus_1d: observed 151.00 vs null 116.04 (nominal p=0.000040; Holm p=0.003480)
2. Do they cluster unusually near CIR arrivals?
- independent dates, distance observed_mean_abs_distance: observed 16.25 vs null 16.65 (nominal p=0.066119; Holm p=1.000000); independent dates, coincidence plus_minus_1d: observed 63.00 vs null 59.79 (nominal p=0.338673; Holm p=1.000000); month-cluster rotations, distance observed_mean_abs_distance: observed 16.25 vs null 16.65 (nominal p=0.054759; Holm p=1.000000); month-cluster rotations, coincidence plus_minus_1d: observed 63.00 vs null 59.78 (nominal p=0.329933; Holm p=1.000000); year-season cluster shifts, distance observed_mean_abs_distance: observed 16.25 vs null 16.60 (nominal p=0.117278; Holm p=1.000000); year-season cluster shifts, coincidence plus_minus_1d: observed 63.00 vs null 58.74 (nominal p=0.270695; Holm p=1.000000)
3. Do they cluster unusually near ICME impacts?
- independent dates, distance observed_mean_abs_distance: observed 18.84 vs null 18.78 (nominal p=0.577188; Holm p=1.000000); independent dates, coincidence plus_minus_1d: observed 42.00 vs null 42.70 (nominal p=0.585768; Holm p=1.000000); month-cluster rotations, distance observed_mean_abs_distance: observed 18.84 vs null 18.78 (nominal p=0.579108; Holm p=1.000000); month-cluster rotations, coincidence plus_minus_1d: observed 42.00 vs null 42.63 (nominal p=0.584728; Holm p=1.000000); year-season cluster shifts, distance observed_mean_abs_distance: observed 18.84 vs null 18.76 (nominal p=0.578108; Holm p=1.000000); year-season cluster shifts, coincidence plus_minus_1d: observed 42.00 vs null 42.43 (nominal p=0.572809; Holm p=1.000000)
4. Do they cluster unusually near major-HSS declining phases?
- independent dates, distance observed_mean_abs_distance: observed 27.97 vs null 27.95 (nominal p=0.521270; Holm p=1.000000); independent dates, coincidence plus_minus_1d: observed 84.00 vs null 82.37 (nominal p=0.431611; Holm p=1.000000); month-cluster rotations, distance observed_mean_abs_distance: observed 27.97 vs null 27.95 (nominal p=0.521790; Holm p=1.000000); month-cluster rotations, coincidence plus_minus_1d: observed 84.00 vs null 82.37 (nominal p=0.430231; Holm p=1.000000); year-season cluster shifts, distance observed_mean_abs_distance: observed 27.97 vs null 27.79 (nominal p=0.674027; Holm p=1.000000); year-season cluster shifts, coincidence plus_minus_1d: observed 84.00 vs null 83.69 (nominal p=0.510150; Holm p=1.000000)
5. Does taking the author outbreak list at face value rescue the paper's narrative?
- 4 exploratory adjusted estimates are at or below 0.05; 3 remain below 0.05 at their simultaneous Monte Carlo upper bounds, and 2 intervals span 0.05. These tests are neither causal nor confirmatory.
6. Does this justify an additional direct HSS/CIR arrival event study?
- A direct CIR/HSS timing study could be considered as a separate exploratory analysis, not as a follow-up justified by adjusted significance here.

## Author Outbreak Type Distribution
- A: 139 (30.4%)
- B: 147 (32.2%)
- C: 46 (10.1%)
- D: 84 (18.4%)
- unknown: 41 (9.0%)

## Existing Author-vs-Independent Agreement Context
- Total compared: 457
- Exact agreement count: 94
- Exact agreement percent: 20.57%
