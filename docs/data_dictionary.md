# Data Dictionary

## Catalogs

- `author_hcs_catalog`: parsed author-provided HCS/SBC crossings.
- `independent_hcs_catalog`: reconstructed HCS proxy from OMNI IMF polarity reversals.
- `cir_hss_catalog`: CIR/HSS proxy event catalog from OMNI daily summaries.
- `icme_catalog`: parsed Richardson-Cane ICME events.

## Daily data

- `tornado_daily`: daily tornado counts and severity aggregates.
- `omni_daily`: daily solar-wind and IMF summaries.
- `analysis_daily`: merged daily table used in event studies and models.
- `tornado_events_clean`: retains `tz` alongside the parsed catalog clock time. Primary aggregation uses `date`; sensitivity conversion uses only documented codes 3 (fixed CST, UTC-6) and 0 (GMT). Other codes are not converted.

## SPE outputs

- `*_window`: event-centered lag tables.
- `*_null`: permutation or Monte Carlo null summaries.
- `*_summary`: effect-size and p-value summaries.

## Coverage and timing sensitivity outputs

- `observation_sensitivity_coverage`: valid-hour threshold, qualified days, reconstructed crossing counts, and membership changes. Low-coverage days cannot be filled; the 1-hour screen isolates missing-day bridging.
- `observation_sensitivity_timezone_audit`: SPC timezone codes, documented conversion eligibility, and analysis-period record counts.
- `observation_sensitivity_catalogs`: analysis-period dates for all six HCS definitions.
- `observation_sensitivity_daily`: 22 scenarios, with event counts, lag-0 and maximum-raw-count statistics, retained tail counts, and Holm adjustment over 44 endpoints. `event_shift_days` shifts HCS dates; `tornado_calendar` distinguishes all-record catalog dates, documented-code catalog dates, and documented-code UTC dates.
- `observation_sensitivity_curves`: all 61 observed lags and pointwise null summaries for each daily scenario.
- `observation_sensitivity_daily_draws.npz`: integer count-total arrays, one per daily scenario in the order recorded by `observation_sensitivity.json`. Divide by the scenario's event count for daily means.
- `observation_sensitivity_outbreak`: exact one-day coincidence tests, separately Holm-adjusted across 30 tests. `outbreak_shift_days` shifts outbreak starts, not HCS dates; these shifts are not UTC conversions.
- `observation_sensitivity.json`: analysis design, timezone documentation, scenario ordering, conversion boundary audit, and interpretation limits.
- `supplement_table_s1_source_date_review`: retains accepted source interpretations with `source_date_review_status=accepted` and `source_date_review_required=False`; audit presence does not imply a pending question.
