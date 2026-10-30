# Methodology

## Manuscript and Implementation Audit

The full [manuscript](manuscript.md) documents the implemented methods. The following computational defects have been repaired:

- Paper-style counts are totals across events at each epoch day, not running sums over lags. Exact replication of the source's data/date conventions is not claimed.
- All-lag calculations use unique complete-window dates and the same eligible calendar for observed and randomized events. Shared annual shifts of up to 15 days preserve within-year event spacing and approximate season. Holm adjustment covers the 16 source/outcome lag scans. The statistic remains the maximum raw daily mean, not a standardized anomaly.
- Scripts 17, 19, 20, and 21 use the canonical daily `Bx` catalog from script 26. The invalid `sign(-Bx * By)` sector identifier is retired.
- The author analyses use 1,788 unique complete-window dates consistently. Source line 848's invalid November day zero is resolved to 1993-10-31 only because day-of-year 304 and elapsed hours 270264 agree; original fields, the invalid source timestamp, and a reconciliation note are preserved. Conflicting or unresolved dates fail explicitly.
- Lag-0 p-values are computed from actual simulated tail counts with the add-one correction and equal-tail two-sided definition. Percentile interpolation is removed; summary-only inputs fail explicitly rather than inventing p-values.
- The outbreak family uses 50,000 replicates per null and event family. Shared retained draws support all distance/coincidence specifications. The minimum Holm-adjusted value is now `87 / 50001 = 0.001740`, so rejection at 0.05 is attainable. Bonferroni-adjusted Clopper-Pearson bounds quantify Monte Carlo uncertainty across 87 tails.
- Both outbreak calculations use the direct Richardson-Cane ICME catalog and restrict the corresponding outbreak population to 1996 onward. Denominators are family-specific; observations outside catalog coverage are not interpreted as non-events.
- Count models estimate negative-binomial dispersion by maximum likelihood using stable initial values and use 14-day HAC covariance; the trend coefficient is per year.
- One exact duplicate SPC row is removed. Repeated year/event identifiers with distinct records are retained, since identifiers alone are not unique. Clock strings are parsed without discarding colon-separated times.
- The climatology uses the complete daily calendar, including zero-tornado days; catalog comparisons use a common 1963-2023 period and unique daily dates.
- Cross-month outbreak ranges are recognized during PDF text extraction, before date parsing; eight previously truncated starts are restored. End-to-end tests cover all eight source patterns.
- The literal source interval 31 May-24 June 1996 is retained with a 31 May start, not guessed to be a shorter interval. It and the inferred 2011 year were accepted by the project author on 2026-10-30. Their audit trail remains in `data/derived/catalogs/supplement_table_s1_source_date_review.csv` with `source_date_review_status=accepted` and no pending clarification. The seven-day duration screen was a review heuristic, not evidence that the interval was invalid; neither entry is excluded.
- Missing major-HSS declining-phase catalogs are reconstructed from OMNI, never substituted with HSS onset dates. The core summary writer creates its report directory on a clean start. Distance and coincidence CIR reconstruction use identical rule-description metadata.

Remaining design limitations are not erased by these repairs: the analyses are retrospective; historical reporting and measurement coverage are imperfect; annual shifts do not preserve cross-year clusters; seasonal-subset and surrogate checks preserve different properties; model fits are not held-out forecast validation; and timing associations do not demonstrate the proposed physical mechanism.

## Observation-Coverage and Timing Sensitivities

`scripts/46_observation_sensitivity.py` is part of the 38-step publication workflow. Its tests are exploratory additions, not replacements for the original 16 lag scans or 87 outbreak tests.

- Count nonmissing hourly GSE Bx observations; reject duplicate timestamps. Reconstruct crossings at 1, 12, 18 and 24 valid hours per day. Failing days are hard barriers, including to forward filling. The one-hour variant separates removal of missing-day bridging from stronger completeness screens; qualified ambiguous days retain the original one-day fill rule.
- Retain timezone codes in the cleaned SPC event table. The [official SPC format specification](https://www.spc.noaa.gov/wcm/data/SPC_severe_database_description.pdf), field 7, documents code 3 as fixed CST (UTC-6) and code 0 as GMT. Do not apply daylight-saving adjustments or infer offsets from geography. Exclude the 29 analysis-period records with other codes only in paired catalog-date/UTC comparisons. Convert the full input before calendar restriction and report boundary flows.
- Cross six HCS definitions (author, primary reconstruction, four screens) with all-record catalog dates, documented-code catalog dates, and documented-code UTC dates. Add -1/+1-day shifts of each primary HCS catalog: 22 daily scenarios. Use 10,000 annual cluster shifts, save integer-total draws, and separately Holm-adjust the 44 lag-0/max-raw-count endpoint tests. This is not the seasonal full-year random-date reference.
- Compare exact one-day outbreak coincidence under the six catalogs and under -1/+1-day outbreak-start shifts against each primary catalog: ten variants times three original null models, with a separate 30-test Holm correction. Keep all 457 starts. Shifts are timing stress tests, not UTC conversions of the source list.
- Keep the full null calendar fixed: coverage screening does not solve exposure missingness, source-list ascertainment, meteorological confounding, or physical timing.

Products are `data/derived/tables/observation_sensitivity_*.csv`, the retained integer-total bank in `data/derived/spe/observation_sensitivity_daily_draws.npz`, and design/audit reports in `data/derived/reports/observation_sensitivity.*`. No adjusted daily test rejects. The unshifted author outbreak association remains, but one-day-earlier starts remove it and one-day-later starts give adjusted rejection for both primary catalogs. Interpret the association as alignment-sensitive.

This project separates two branches of analysis.

## Branch 1: Paper-Style Replication

- Use the author-provided HCS/SBC list when available.
- Build superposed-epoch windows around HCS crossing days.
- Compute tornado, strong-tornado, injury, and fatality totals across events at each epoch day, not across-lag running sums.
- Include a paper-style random-date Monte Carlo null for comparability.

## Branch 2: Stricter Reanalysis

- Use mean daily rates as the primary inferential target; their lag shapes equal across-event totals when the event count is fixed.
- The project-designated primary endpoint is the full-year lag-0 mean daily all-tornado count around HCS crossings; the reconstructed-HCS catalog is a parallel validation branch. No prospective registration is claimed.
- Compare author HCS, independently reconstructed HCS, and CIR/HSS proxy events.
- Use season-matched permutation nulls that preserve year structure.
- Correct across lags with a max-statistic.
- Fit daily count and outbreak-day models with seasonality and trend controls.
- Negative-binomial count models estimate `alpha`; model inference remains exploratory and potentially affected by unmodeled meteorological confounding and seasonal specification.

## Post-Hoc Author-Outbreak Branch

- Treat supplement-derived outbreak-date proximity and event-coincidence analyses as exploratory; they do not redefine the primary endpoint.
- The independent year-month null preserves the number of outbreak dates in each calendar stratum but samples dates independently within strata; it does not preserve clustering or serial dependence.
- The cluster-rotation sensitivity shifts each year-month's outbreak-day pattern as a unit, preserving monthly counts and cyclic within-month spacing. It does not preserve cross-month clusters or dependence between adjacent strata.
- The year-season cluster sensitivity shifts the full annual outbreak pattern as a unit by up to 15 days, preserving within-year cluster spacing across month boundaries and approximate season. It does not preserve clusters spanning calendar years.
- Holm adjustment covers all 87 distance and coincidence tests across the three null designs, not the full set of analyses explored in the project.
- These shifts are sensitivity analyses, not complete models of serial dependence; interpretation must acknowledge the calendar-year boundary limitation.
- The standard `run_analysis.py` workflow stops at script 23; `run_publication.py` runs the later analyses and manuscript exporters in dependency order. Running it does not resolve the inferential limitations noted above.

## Core Data Products

- Clean event catalogs in `data/derived/catalogs/`
- Daily tornado and solar-wind summaries in `data/derived/daily/`
- Superposed-epoch outputs in `data/derived/spe/`
- Model outputs in `data/derived/models/`
- Final figures, tables, and reports in `data/derived/`
