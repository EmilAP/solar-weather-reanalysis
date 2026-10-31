# Author Outbreak Event Coincidence Test

- Outbreak anchors analyzed: 457
- Null iterations: 50000
- Random seed: 20260316
- Null dates preserve each outbreak's year and month; dates are sampled without replacement within year-month strata when possible.
- Cluster-preserving sensitivity circularly shifts each year-month outbreak-day pattern as a unit, preserving monthly counts and cyclic within-month spacing; cross-month clusters are not preserved.
- Season-aware cluster sensitivity shifts each year's entire outbreak pattern by a shared offset within +/-15 days, preserving within-year cluster spacing across month boundaries.
- This outbreak-list analysis is exploratory. P-values here are nominal; the combined summary Holm-adjusts all 87 tests across three null designs.

## Event Catalog Status
- HCS_author_catalog: detected
- HCS_reconstructed_catalog: detected
- CIR_arrival_catalog: detected
- ICME_impact_catalog: detected
- major_HSS_declining_phase_catalog: detected

## Directional Window Definitions
- CIR_following_window: outbreak occurs 0 to +3 days after CIR arrival (implemented as event in [-3, 0] days relative to outbreak).
- HCS_preceding_window: outbreak occurs -3 to 0 days relative to HCS/HDP (implemented as event in [0, +3] days relative to outbreak).
- ICME_following_window: outbreak occurs 0 to +3 days after ICME impact (implemented as event in [-3, 0] days relative to outbreak).
- HSS_declining_phase_window: outbreak date falls on a reconstructed major-HSS declining-phase day.

## Reconstruction Rules
- CIR proxy: speed >= 500 km/s, speed jump >= 80 km/s, and compression signature from density/|B|/pressure.
- ICME: direct catalog only, with outbreak starts and null dates restricted to 1996 onward; no proxy substitution.
- major-HSS declining phase: local speed peak >= 600 km/s and include +1..+4 days with non-increasing speed.
- ICME distance and coincidence tests use the same direct catalog and exclude outbreak starts before 1996. All catalogs are restricted to the analysis calendar.

## Coincidence Highlights
- HCS_author_catalog | plus_minus_1d: observed=151 of 457, independent null mean=116.98, p=0.000; month-cluster null mean=116.88, p=0.000; year-season cluster null mean=116.04, p=0.000; Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.
- HCS_author_catalog | plus_minus_2d: observed=221 of 457, independent null mean=190.46, p=0.001; month-cluster null mean=190.34, p=0.001; year-season cluster null mean=188.49, p=0.000; Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.
- HCS_reconstructed_catalog | plus_minus_1d: observed=141 of 457, independent null mean=117.31, p=0.004; month-cluster null mean=117.26, p=0.003; year-season cluster null mean=116.74, p=0.004; Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.
- HCS_reconstructed_catalog | HCS_preceding_window_minus3_to_0: observed=177 of 457, independent null mean=152.73, p=0.005; month-cluster null mean=152.77, p=0.005; year-season cluster null mean=152.97, p=0.006; Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.
- HCS_reconstructed_catalog | plus_minus_2d: observed=207 of 457, independent null mean=185.58, p=0.013; month-cluster null mean=185.54, p=0.010; year-season cluster null mean=186.05, p=0.013; Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.
- CIR_arrival_catalog | plus_minus_3d: observed=142 of 457, independent null mean=127.90, p=0.048; month-cluster null mean=127.88, p=0.039; year-season cluster null mean=126.97, p=0.031; Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.
- HCS_reconstructed_catalog | plus_minus_3d: observed=259 of 457, independent null mean=244.24, p=0.061; month-cluster null mean=244.27, p=0.055; year-season cluster null mean=245.06, p=0.067; Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.
- CIR_arrival_catalog | plus_minus_2d: observed=108 of 457, independent null mean=96.14, p=0.070; month-cluster null mean=96.11, p=0.061; year-season cluster null mean=94.62, p=0.044; Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.

## Cluster-Preserving Sensitivity Highlights
- HCS_author_catalog | plus_minus_1d: observed=151, cluster-shift null mean=116.88, nominal p=0.000.
- HCS_author_catalog | plus_minus_2d: observed=221, cluster-shift null mean=190.34, nominal p=0.001.
- HCS_reconstructed_catalog | plus_minus_1d: observed=141, cluster-shift null mean=117.26, nominal p=0.003.
- HCS_reconstructed_catalog | HCS_preceding_window_minus3_to_0: observed=177, cluster-shift null mean=152.77, nominal p=0.005.
- HCS_reconstructed_catalog | plus_minus_2d: observed=207, cluster-shift null mean=185.54, nominal p=0.010.
- CIR_arrival_catalog | plus_minus_3d: observed=142, cluster-shift null mean=127.88, nominal p=0.039.
- HCS_reconstructed_catalog | plus_minus_3d: observed=259, cluster-shift null mean=244.27, nominal p=0.055.
- CIR_arrival_catalog | plus_minus_2d: observed=108, cluster-shift null mean=96.11, nominal p=0.061.

## Year-Season Cluster Sensitivity Highlights
- HCS_author_catalog | plus_minus_1d: observed=151, year-season cluster null mean=116.04, nominal p=0.000.
- HCS_author_catalog | plus_minus_2d: observed=221, year-season cluster null mean=188.49, nominal p=0.000.
- HCS_reconstructed_catalog | plus_minus_1d: observed=141, year-season cluster null mean=116.74, nominal p=0.004.
- HCS_reconstructed_catalog | HCS_preceding_window_minus3_to_0: observed=177, year-season cluster null mean=152.97, nominal p=0.006.
- HCS_reconstructed_catalog | plus_minus_2d: observed=207, year-season cluster null mean=186.05, nominal p=0.013.
- CIR_arrival_catalog | plus_minus_3d: observed=142, year-season cluster null mean=126.97, nominal p=0.031.
- CIR_arrival_catalog | plus_minus_2d: observed=108, year-season cluster null mean=94.62, nominal p=0.044.
- HCS_reconstructed_catalog | plus_minus_3d: observed=259, year-season cluster null mean=245.06, nominal p=0.067.
