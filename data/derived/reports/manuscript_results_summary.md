# Manuscript Results Summary

## Primary Question and Endpoint
The project-designated primary question is whether the full-year mean daily all-tornado count at lag 0 differs from its null expectation around HCS crossings (author catalog, with reconstructed HCS as a parallel validation branch).
The repository contains no dated preregistration or prospective analysis plan; ‘primary’ here describes the analysis hierarchy used in this reanalysis, not a prospectively registered endpoint.

## Authoritative Source Selection
- Curves and quoted lag-0 values use the SPE curve files as canonical sources to avoid mixed derivations.
- Seasonal event counts and iterations use seasonal_control_summary.csv.
- Phase-randomized event counts and iterations use phase_randomized_author_hcs_summary.csv.
- Author primary event count uses author_hcs_count_reconciliation.csv; reconstructed primary count/iterations use manifest 27.

## Exact Lag-0 Values
- author_hcs / core_fast_null / full_year: observed=2.989933, null_mean=2.847025, 95%=[2.539304, 3.139723], inside_band=True, event_count=1788, iterations=500
- reconstructed_hcs / core_fast_null / full_year: observed=3.061133, null_mean=2.847564, 95%=[2.548233, 3.151739], inside_band=True, event_count=1783, iterations=500
- author_hcs / seasonal_full_year / full_year: observed=2.989933, null_mean=2.856180, 95%=[2.555020, 3.178789], inside_band=True, event_count=1788, iterations=500
- reconstructed_hcs / seasonal_full_year / full_year: observed=3.061133, null_mean=2.838452, 95%=[2.552776, 3.151767], inside_band=True, event_count=1783, iterations=500
- author_hcs / seasonal_mar_jun / mar_jun: observed=5.355263, null_mean=5.175164, 95%=[4.520518, 5.940090], inside_band=True, event_count=608, iterations=500
- reconstructed_hcs / seasonal_mar_jun / mar_jun: observed=5.647359, null_mean=5.182201, 95%=[4.559497, 5.877385], inside_band=True, event_count=587, iterations=500
- author_hcs / seasonal_apr_jun / apr_jun: observed=6.378723, null_mean=6.167443, 95%=[5.360479, 6.986543], inside_band=True, event_count=470, iterations=500
- reconstructed_hcs / seasonal_apr_jun / apr_jun: observed=6.845133, null_mean=6.148248, 95%=[5.253042, 7.079038], inside_band=True, event_count=452, iterations=500
- author_hcs / phase_randomized / full_year: observed=2.989933, null_mean=2.833203, 95%=[2.545342, 3.154546], inside_band=True, event_count=1788, iterations=200

## Primary Author-HCS Result
Author-HCS full-year lag 0 remains within the null band (observed 2.989933 vs null mean 2.847025, 95% [2.539304, 3.139723]).

## Primary Reconstructed-HCS Result
Reconstructed-HCS full-year lag 0 remains within the null band (observed 3.061133 vs null mean 2.847564, 95% [2.548233, 3.151739]).

## Seasonal-Control Results
Seasonal subsets exported: 6 lag-0 rows; outside-band lag-0 rows: 0.

## All-Lag Exploratory Results
Unique complete-window dates and within-year cluster shifts are used consistently. The statistic is the maximum raw daily mean across lags; Holm adjustment covers 16 source/outcome tests.
- author_hcs: N=1788, peak=3.444072 at lag -1; Monte Carlo p=0.018981, Holm p=0.303696.
- reconstructed_hcs: N=1783, peak=3.337072 at lag -28; Monte Carlo p=0.293706, Holm p=1.000000.
- cir_proxy: N=917, peak=3.681570 at lag -3; Monte Carlo p=0.043956, Holm p=0.599401.
- hss_onset: N=1224, peak=3.522059 at lag -3; Monte Carlo p=0.214785, Holm p=1.000000.

## Phase-Randomized Results
Phase-randomized author-HCS lag 0 is inside band=True (observed 2.989933, null mean 2.833203, 95% [2.545342, 3.154546]).

## Block-Bootstrap Robustness
Across 4 7- and 14-day block-bootstrap checks, 0 lag-0 estimates fell outside their pointwise 95% null bands.
The bootstrap resamples contiguous daily tornado-count blocks and preserves short-range outcome clustering; it does not preserve the seasonal cycle by construction.

## Exploratory Author-Outbreak Analysis
These supplement-derived outbreak-list tests are post hoc and do not redefine the primary endpoint.
The branch reports 87 tests across all three null designs with one Holm adjustment; 4 remain below 0.05 after adjustment.
Author-HCS ±1-day under year_month_cluster_rotation: 151 observed vs 116.88 null mean (nominal p=0.000120; Holm-adjusted p=0.010200); exploratory, not causal evidence.
Author-HCS ±1-day under year_month_independent: 151 observed vs 116.98 null mean (nominal p=0.000080; Holm-adjusted p=0.006880); exploratory, not causal evidence.
Author-HCS ±1-day under year_season_cluster_shift_15d: 151 observed vs 116.04 null mean (nominal p=0.000040; Holm-adjusted p=0.003480); exploratory, not causal evidence.
The independent year-month null preserves stratum counts but not date clustering. Month rotations preserve within-month spacing; year-season shifts preserve within-year cluster spacing across month boundaries with a shared +/-15-day shift, but not clusters spanning years. Holm covers these 87 branch tests, not every analysis explored in the project.

## Coverage and Timing Sensitivities
Daily sensitivity: 22 variants, 10,000 annual cluster shifts each, Holm across 44 endpoint tests. Adjusted lag-0 rejections=0; adjusted all-lag rejections=0.
SPC code 3 uses fixed CST (UTC-6); code 0 uses GMT. Other codes are excluded only in paired catalog-date/UTC comparisons. Coverage screens of 1, 12, 18 and 24 valid daily Bx hours are hard barriers to filling.
Outbreak sensitivity: 30 exact conditional tests, separately Holm-adjusted. These do not replace the original 87-test family.
- author, outbreak-start shift=+0 days: 151/457 within one day; sensitivity-family Holm p=0.001049-0.002544.
- reconstructed_primary, outbreak-start shift=+0 days: 141/457 within one day; sensitivity-family Holm p=0.067336-0.070195.
- reconstructed_min_01h, outbreak-start shift=+0 days: 136/457 within one day; sensitivity-family Holm p=0.064769-0.068141.
- reconstructed_min_12h, outbreak-start shift=+0 days: 120/457 within one day; sensitivity-family Holm p=0.445630-0.476066.
- reconstructed_min_18h, outbreak-start shift=+0 days: 113/457 within one day; sensitivity-family Holm p=0.476066-0.476066.
- reconstructed_min_24h, outbreak-start shift=+0 days: 102/457 within one day; sensitivity-family Holm p=0.476066-0.476066.
- author, outbreak-start shift=-1 days: 121/457 within one day; sensitivity-family Holm p=1.000000-1.000000.
- author, outbreak-start shift=+1 days: 161/457 within one day; sensitivity-family Holm p=0.000008-0.000026.
- reconstructed_primary, outbreak-start shift=-1 days: 119/457 within one day; sensitivity-family Holm p=1.000000-1.000000.
- reconstructed_primary, outbreak-start shift=+1 days: 148/457 within one day; sensitivity-family Holm p=0.005222-0.007132.
The unshifted author-catalog enrichment persists, but shifting outbreak starts one day earlier removes it; shifting one day later produces adjusted rejection for both primary HCS catalogs. These are date-label stress tests, not UTC conversions or evidence of causality.

## Remaining Limitations Before Submission
- The year-season cluster sensitivity preserves within-year spacing but not clusters spanning calendar years; evaluate whether that residual matters for the scientific interpretation.
- Document analysis selection and null-model choices; no prospective registration was found in the repository.
- Count models estimate dispersion and use 14-day HAC covariance; meteorological confounding, model specification, and held-out forecasting remain unresolved.
- Report pointwise lag bands as pointwise; do not interpret excursions across the full lag curve as familywise-significant without a simultaneous test.
- Use run_publication.py for the full dependency-ordered workflow; run_analysis.py remains the core subset.
- The literal 1996 source interval and inferred 2011 year were accepted by the project author; audit notes remain and neither source entry was excluded.

## Catalog Comparison
Catalog totals: author=1792, reconstructed=1786; median spacing days: author=11.0, reconstructed=10.0; median nearest timing difference=1.0 days.

## Source Files Used
- data/derived/spe/author_hcs_apr_jun_fast_null_all_tornadoes.csv
- data/derived/spe/author_hcs_full_year_fast_null_all_tornadoes.csv
- data/derived/spe/author_hcs_mar_jun_fast_null_all_tornadoes.csv
- data/derived/spe/fast_null_test_all_tornadoes.csv
- data/derived/spe/phase_randomized_author_hcs_all_tornadoes.csv
- data/derived/spe/reconstructed_hcs_apr_jun_fast_null_all_tornadoes.csv
- data/derived/spe/reconstructed_hcs_fast_null_all_tornadoes.csv
- data/derived/spe/reconstructed_hcs_full_year_fast_null_all_tornadoes.csv
- data/derived/spe/reconstructed_hcs_mar_jun_fast_null_all_tornadoes.csv
- data/derived/tables/author_hcs_count_reconciliation.csv
- data/derived/tables/author_outbreak_branch_key_results.csv
- data/derived/tables/block_bootstrap_summary.csv
- data/derived/tables/hcs_catalog_comparison_summary.csv
- data/derived/tables/observation_sensitivity_daily.csv
- data/derived/tables/observation_sensitivity_outbreak.csv
- data/derived/tables/phase_randomized_author_hcs_summary.csv
- data/derived/tables/seasonal_control_summary.csv
- data/manifests/27_event_study_reconstructed_hcs.json

## Consistency Check
No numeric inconsistencies found across overlapping lag-0 values in selected authoritative vs summary files.
