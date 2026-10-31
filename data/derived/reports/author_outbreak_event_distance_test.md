# Author Outbreak Event Distance Test

Primary analysis: outbreak_anchor_date = outbreak_start_date.
Sensitivity-only analysis: nearest event to any day within outbreak_start_date..outbreak_end_date.

- Null iterations: 50000
- Random seed: 20260316
- Outbreak rows analyzed: 457
- Null dates preserve each outbreak's year and month; dates are sampled without replacement within year-month strata when possible.
- Cluster-preserving sensitivity circularly shifts each year-month outbreak-day pattern as a unit, preserving monthly counts and cyclic within-month spacing; cross-month clusters are not preserved.
- Season-aware cluster sensitivity shifts each year's entire outbreak pattern by a shared offset within +/-15 days, preserving within-year cluster spacing across month boundaries.
- This outbreak-list analysis is exploratory. P-values here are nominal; the combined summary Holm-adjusts all 87 tests across three null designs.

## Event Catalog Status
- HCS_author_catalog: detected:data/derived/catalogs/author_hcs_catalog.csv
- HCS_reconstructed_catalog: detected:data/derived/catalogs/hcs_from_omni.csv
- CIR_arrival_catalog: detected:data/derived/catalogs/cir_arrival_catalog.csv
- ICME_impact_catalog: detected:data/derived/catalogs/icme_catalog.csv
- major_HSS_declining_phase_catalog: detected:data/derived/catalogs/major_hss_declining_phase_catalog.csv

## Reconstruction Rules
- CIR arrival proxy: speed >= 500 km/s and daily speed jump >= 80 km/s with compression signature (density >= 8 cm^-3 or |B| >= 8 nT or flow pressure >= 2.5 nPa).
- ICME: direct catalog only, with outbreak starts and null dates restricted to 1996 onward; no proxy substitution.
- Major-HSS declining phase: local speed peak >= 600 km/s, include +1..+4 days where speed is <= peak speed.
- ICME distance and coincidence tests use the same direct catalog and exclude outbreak starts before 1996. All catalogs are restricted to the analysis calendar.

## Null Comparison Summary
- HCS_author_catalog (N=457): observed mean abs distance=3.90; independent year-month null mean=4.10, p=0.063; month-cluster null mean=4.10, p=0.060; year-season cluster null mean=4.14, p=0.034; Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.
- HCS_reconstructed_catalog (N=457): observed mean abs distance=5.50; independent year-month null mean=5.65, p=0.160; month-cluster null mean=5.65, p=0.147; year-season cluster null mean=5.56, p=0.355; Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.
- CIR_arrival_catalog (N=457): observed mean abs distance=16.25; independent year-month null mean=16.65, p=0.066; month-cluster null mean=16.65, p=0.055; year-season cluster null mean=16.60, p=0.117; Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.
- ICME_impact_catalog (N=293): observed mean abs distance=18.84; independent year-month null mean=18.78, p=0.577; month-cluster null mean=18.78, p=0.579; year-season cluster null mean=18.76, p=0.578; Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.
- major_HSS_declining_phase_catalog (N=457): observed mean abs distance=27.97; independent year-month null mean=27.95, p=0.521; month-cluster null mean=27.95, p=0.522; year-season cluster null mean=27.79, p=0.674; Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.
