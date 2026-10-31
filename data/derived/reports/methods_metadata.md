# Methods Metadata

## Tornado Dataset
- Path: data/derived/daily/analysis_daily.csv
- Apparent period: 1963-01-01 to 2023-12-31

## Author HCS Catalog
- Path: data/derived/catalogs/author_hcs_catalog.csv
- Raw parsed rows 1963-2023: 1794
- Unique valid datetimes 1963-2023: 1792
- Invalid datetime rows 1963-2023: 0
- Source dates reconciled using redundant fields: 1
- Duplicate datetime rows 1963-2023: 4
- Event count used in primary event study (+/-30-day edge filter): 1788

## Reconciliation Note
- Differences arise from duplicate rows and edge filtering. The source day=0 row is reconciled as 1993-10-31 using agreement of day-of-year and elapsed hours, with raw fields retained.
