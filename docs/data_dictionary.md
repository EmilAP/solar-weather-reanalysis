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

## SPE outputs

- `*_window`: event-centered lag tables.
- `*_null`: permutation or Monte Carlo null summaries.
- `*_summary`: effect-size and p-value summaries.
