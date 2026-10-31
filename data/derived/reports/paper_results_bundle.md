# Paper Results Bundle

## Primary Question and Endpoint
The project-designated primary question is whether the full-year mean daily all-tornado count at lag 0 differs from its null expectation around author HCS crossings; the reconstructed-HCS branch is a parallel validation analysis.
No dated preregistration or prospective analysis plan was found in the repository, so ‘primary’ denotes the current analysis hierarchy, not prospective registration.

## Main Result
Daily-rate comparisons do not show a special lag-0 effect in the primary author or reconstructed HCS branches.

No available lag-0 test fell outside its 95% null band in the assembled primary results table.

## Robustness Checks
Seasonal, phase-randomized, and 7/14-day block-bootstrap robustness checks kept lag 0 inside the corresponding pointwise null bands.
Block bootstrap resamples contiguous daily outcome blocks, preserving short-range clustering but not the seasonal cycle by construction.

## Interpretation
Daily means and totals accumulated across events have identical lag shapes for fixed event populations. Neither is a running sum across lags. Pointwise lag-0 comparisons do not settle the significance of nonzero-lag peaks.

## Exploratory Author-Outbreak Analysis
This post-hoc branch does not redefine the primary result.
Holm adjustment covers 87 tests across all three null designs; 4 remain below 0.05.
Author-HCS ±1-day coincidence under year_month_cluster_rotation: 151 observed vs 116.88 null mean; nominal p=0.000120, Holm-adjusted p=0.010200. This remains exploratory and is not causal evidence.
Author-HCS ±1-day coincidence under year_month_independent: 151 observed vs 116.98 null mean; nominal p=0.000080, Holm-adjusted p=0.006880. This remains exploratory and is not causal evidence.
Author-HCS ±1-day coincidence under year_season_cluster_shift_15d: 151 observed vs 116.04 null mean; nominal p=0.000040, Holm-adjusted p=0.003480. This remains exploratory and is not causal evidence.
The independent year-month null does not preserve date clustering; month rotations preserve within-month spacing; year-season shifts preserve within-year clusters across month boundaries but not clusters spanning years. The adjustment does not cover every analysis explored across the project.

## Limitations Before Submission
The annual cluster shifts preserve season approximately and within-year spacing, not clusters spanning years. Count models now estimate dispersion and use 14-day HAC covariance, but remain exploratory in-sample fits. Document retrospective analysis selection, use Monte Carlo uncertainty when interpreting adjusted p-values, report pointwise lag bands as pointwise, and retain the supplement inference audit note. Temporal association is not causal attribution.

