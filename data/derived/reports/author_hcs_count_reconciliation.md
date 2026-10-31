# Author HCS Count Reconciliation

## Summary
- Raw nonblank lines in source text: 1827
- Parsed catalog rows: 1825
- Parsed rows in 1963-2023: 1794
- Unique valid datetimes in 1963-2023: 1792
- Primary event-study count used: 1788
- Seasonal author counts (full_year, mar_jun, apr_jun): 1788, 608, 470
- Phase-randomized author count used: 1788

## Discrepancy Source
- Two duplicate datetime pairs exist in 1963-2023 (4 duplicate rows total).
- 1 invalid source dates reconciled from agreeing redundant fields; 0 dates remain invalid.
- Source line 848 has day=0; day-of-year 304 and elapsed hours 270264 both identify 1993-10-31. The resolved timestamp is used while raw fields are preserved.
- Primary and robustness event studies drop NA dates, deduplicate dates, and apply +/-30-day edge filtering, reducing usable events further.

## Metadata Files Updated
- data/derived/reports/methods_metadata.json
- data/derived/reports/methods_metadata.md
- data/derived/tables/paper_table_1_datasets_and_catalogs.csv
- data/derived/tables/paper_table_2_primary_results.csv
- data/derived/tables/paper_table_3_robustness_checks.csv
