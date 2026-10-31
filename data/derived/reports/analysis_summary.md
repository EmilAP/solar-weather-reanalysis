# Analysis Summary

## Executive Summary

This report separates paper-style replication from the stricter reanalysis branch.

## Validation Questions

1. Exact replication of the source article has not been established; event/date conventions remain distinct.
2. Across-event totals and daily means have identical shapes with a fixed event population; neither is an across-lag running sum.
3. Does it remain under stricter season-matched permutation nulls? Maximum raw daily mean: 3.444 at lag -1; lag-scan Monte Carlo p=0.0190, Holm p=0.3037 across the 16 source/outcome tests. Exploratory, not causal evidence.
4. Does it remain using independently reconstructed HCS events? Maximum raw daily mean: 3.337 at lag -28; lag-scan Monte Carlo p=0.2937, Holm p=1.0000 across the 16 source/outcome tests. Exploratory, not causal evidence.
5. Does it appear stronger for HCS, CIR, or HSS proxy events? [{'source': 'author_hcs', 'metric': 'all_tornadoes', 'event_count': 1788, 'observed_max_abs_daily_effect': 3.4440715883668904, 'empirical_p_max': 0.0189810189810189, 'lag_of_max_abs_effect': -1, 'statistic': 'maximum_raw_daily_mean', 'null_model': 'within_year_cluster_shift_15d', 'iterations': 1000, 'p_value_holm': 0.3036963036963037}, {'source': 'cir_proxy', 'metric': 'daily_fatalities', 'event_count': 917, 'observed_max_abs_daily_effect': 0.93020719738277, 'empirical_p_max': 0.0399600399600399, 'lag_of_max_abs_effect': -3, 'statistic': 'maximum_raw_daily_mean', 'null_model': 'within_year_cluster_shift_15d', 'iterations': 1000, 'p_value_holm': 0.5994005994005994}, {'source': 'cir_proxy', 'metric': 'daily_injuries', 'event_count': 917, 'observed_max_abs_daily_effect': 14.016357688113413, 'empirical_p_max': 0.0399600399600399, 'lag_of_max_abs_effect': -3, 'statistic': 'maximum_raw_daily_mean', 'null_model': 'within_year_cluster_shift_15d', 'iterations': 1000, 'p_value_holm': 0.5994005994005994}]
6. How sensitive is it to outbreak definition and lag window? Inspect strict_event_study_summary.csv and model coefficients for sensitivity by metric and lag.

## What Replicates

- The paper-style branch reproduces the event-centered cumulative framework using the author HCS list when available.
- The stricter branch preserves the same event windows but evaluates daily rates with stronger null models.

## What Does Not Hold Up Automatically

- Visual peaks require an explicit lag-scanning and analysis-family reference distribution.
- Reconstructed HCS and CIR/HSS proxies must be treated as separate hypotheses, not interchangeable proofs of the same mechanism.

## Likely Methodological Traps

- Confusing totals across events with running sums across lags.
- Overlapping windows and non-independence of event-centered samples.
- Weak null models based on unconstrained random dates.
- Multiple-comparison risk across lags, metrics, and event definitions.
- Circular event classification if solar proxies are tuned against tornado outcomes.

## Inputs Used

- Strict event study summary present: True
- Model coefficient summary present: True
- Catalog comparison summary present: True
- Paper-style observed SPE present: True
