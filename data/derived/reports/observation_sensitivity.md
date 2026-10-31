# Observation sensitivity analyses

- Daily scenarios: 22; two endpoints each, Holm across 44 tests.
- Daily null: 10,000 annual cluster shifts; retained integer-total draws.
- Outbreak family: 30 exact one-day tests across three nulls, separately Holm-adjusted.
- Unresolved timezone records: 29.
- Documented records changing calendar date: 20980.
- Daily adjusted rejections: lag 0=0; maximum=0.
- Outbreak adjusted rejections: 9.

Timezone source: https://www.spc.noaa.gov/wcm/data/SPC_severe_database_description.pdf (field 7, page 1; accessed 2026-10-30).

Coverage screens affect only the reconstructed HCS catalog, not the supplied author catalog. Low-coverage days are hard barriers, even to one-day filling. The 1-hour screen separates this change from increasing coverage thresholds. Full-calendar nulls do not solve exposure missingness or meteorological confounding. UTC timing uses a paired known-code subset, not guessed geographic timezones. Boundary flows are reported in JSON. Outbreak shifts do not change source interpretations or simulate known physical times. Sensitivity multiplicity families do not replace the original 16- or 87-test families. Daily p-values have finite Monte Carlo precision; outbreak tails are exact conditional on the nulls.
