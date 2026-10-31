# Supplement Table S1 pdfplumber Preparation

- Input row count: 457
- Retained row count: 457
- Excluded row count: 0
- Dates parsed: 457
- Dates unresolved (manual review): 0
- Rows with an inferred year: 1
- Rows requiring source-date clarification: 0
- Source-date interpretations accepted by the project author: 2
- Retained table appears usable for downstream outbreak analysis: yes

## Exclusion Logic
- Exclude if outbreak_date_text is blank.
- Exclude if raw_row_text is blank.
- Exclude if both author_type and key_event_text are blank.
- Exclude if outbreak date text cannot be parsed; these rows are retained in the manual-review file.
- Exclude if raw_row_text is shorter than 12 characters.

## Exclusion Reason Counts
- none

## Notes
- All rows are preserved in the flagged catalog with needs_manual_review and reason labels.
- Inferred dates are labeled in date_inference_note; source raw_row_text is preserved unchanged.
- Long intervals are screening flags, not invalid outbreak definitions. The literal 1996 interval and inferred 2011 year were accepted by the project author on 2026-10-30; neither requires exclusion or further source clarification. Audit notes remain preserved.
- Source-date review table: data/derived/catalogs/supplement_table_s1_source_date_review.csv.
- The retained output is intended as the standard downstream input for outbreak analysis scripts.
