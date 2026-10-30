from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "hcs" / "SBCtorlist1963-2024.txt"
CATALOG_PATH = ROOT / "data" / "derived" / "catalogs" / "author_hcs_catalog.csv"
ANALYSIS_DAILY_PATH = ROOT / "data" / "derived" / "daily" / "analysis_daily.csv"
SEASONAL_PATH = ROOT / "data" / "derived" / "tables" / "seasonal_control_summary.csv"
PHASE_PATH = ROOT / "data" / "derived" / "tables" / "phase_randomized_author_hcs_summary.csv"

RECON_TABLE_PATH = ROOT / "data" / "derived" / "tables" / "author_hcs_count_reconciliation.csv"
RECON_REPORT_PATH = ROOT / "data" / "derived" / "reports" / "author_hcs_count_reconciliation.md"
METHODS_JSON_PATH = ROOT / "data" / "derived" / "reports" / "methods_metadata.json"
METHODS_MD_PATH = ROOT / "data" / "derived" / "reports" / "methods_metadata.md"
PAPER_T1_PATH = ROOT / "data" / "derived" / "tables" / "paper_table_1_datasets_and_catalogs.csv"
PAPER_T2_PATH = ROOT / "data" / "derived" / "tables" / "paper_table_2_primary_results.csv"
PAPER_T3_PATH = ROOT / "data" / "derived" / "tables" / "paper_table_3_robustness_checks.csv"

DATA_LINE_RE = re.compile(r"^\s*(19|20)\d{2}\s+")
WINDOW_DAYS = 30


def count_raw_lines(path: Path) -> tuple[int, int, int]:
    nonblank = 0
    data_any = 0
    data_1963_2023 = 0
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.strip():
                nonblank += 1
            if DATA_LINE_RE.match(line):
                data_any += 1
                year = int(line.split()[0])
                if 1963 <= year <= 2023:
                    data_1963_2023 += 1
    return nonblank, data_any, data_1963_2023


def compute_primary_used_count(catalog_1963_2023: pd.DataFrame, analysis_daily: pd.DataFrame) -> int:
    date_days = pd.DatetimeIndex(analysis_daily["date"]).to_numpy(dtype="datetime64[ns]")

    event_dates = (
        pd.to_datetime(catalog_1963_2023["datetime_utc"], utc=True, errors="coerce")
        .dt.tz_convert(None)
        .dt.normalize()
        .dropna()
        .drop_duplicates()
        .sort_values()
    )
    event_days = event_dates.to_numpy(dtype="datetime64[ns]")

    idx = np.searchsorted(date_days, event_days)
    in_bounds = (idx >= 0) & (idx < len(date_days))
    valid = np.zeros(len(idx), dtype=bool)
    valid[in_bounds] = date_days[idx[in_bounds]] == event_days[in_bounds]
    idx = idx[valid]
    idx = idx[(idx >= WINDOW_DAYS) & (idx < len(date_days) - WINDOW_DAYS)]
    idx = np.unique(idx)
    return int(len(idx))


def get_author_seasonal_counts(seasonal_df: pd.DataFrame) -> dict[str, int | None]:
    out: dict[str, int | None] = {
        "full_year": None,
        "mar_jun": None,
        "apr_jun": None,
    }
    author = seasonal_df[seasonal_df["branch"] == "author_hcs"].copy()
    for season in out:
        row = author[author["season"] == season]
        if not row.empty:
            out[season] = int(row.iloc[0]["event_count_used"])
    return out


def update_methods_metadata(
    parsed_rows_1963_2023: int,
    unique_datetime_rows_1963_2023: int,
    invalid_datetime_rows_1963_2023: int,
    duplicate_rows_1963_2023: int,
    primary_used: int,
    reconciled_dates: int,
) -> list[str]:
    updated: list[str] = []

    if METHODS_JSON_PATH.exists():
        import json

        data = json.loads(METHODS_JSON_PATH.read_text(encoding="utf-8"))
        author = data.setdefault("author_hcs_catalog", {})
        author["raw_count_1963_2023"] = int(parsed_rows_1963_2023)
        author["unique_datetime_rows_1963_2023"] = int(unique_datetime_rows_1963_2023)
        author["invalid_datetime_rows_1963_2023"] = int(invalid_datetime_rows_1963_2023)
        author["duplicate_datetime_rows_1963_2023"] = int(duplicate_rows_1963_2023)
        author["event_count_used_primary"] = int(primary_used)
        author["dates_reconciled_1963_2023"] = int(reconciled_dates)
        author["count_reconciliation_note"] = (
            "Raw 1963-2023 rows include duplicates; invalid source dates are reconciled only from agreeing redundant fields. "
            "primary event-study count additionally applies date matching and +/-30-day edge filtering."
        )
        METHODS_JSON_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        updated.append(str(METHODS_JSON_PATH.relative_to(ROOT)))

    if METHODS_MD_PATH.exists():
        md_lines = [
            "# Methods Metadata",
            "",
            "## Tornado Dataset",
            "- Path: data/derived/daily/analysis_daily.csv",
            "- Apparent period: 1963-01-01 to 2023-12-31",
            "",
            "## Author HCS Catalog",
            "- Path: data/derived/catalogs/author_hcs_catalog.csv",
            f"- Raw parsed rows 1963-2023: {parsed_rows_1963_2023}",
            f"- Unique valid datetimes 1963-2023: {unique_datetime_rows_1963_2023}",
            f"- Invalid datetime rows 1963-2023: {invalid_datetime_rows_1963_2023}",
            f"- Source dates reconciled using redundant fields: {reconciled_dates}",
            f"- Duplicate datetime rows 1963-2023: {duplicate_rows_1963_2023}",
            f"- Event count used in primary event study (+/-{WINDOW_DAYS}-day edge filter): {primary_used}",
            "",
            "## Reconciliation Note",
            "- Differences arise from duplicate rows and edge filtering. The source day=0 row is reconciled as 1993-10-31 using agreement of day-of-year and elapsed hours, with raw fields retained.",
        ]
        METHODS_MD_PATH.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
        updated.append(str(METHODS_MD_PATH.relative_to(ROOT)))

    return updated


def update_paper_tables(
    parsed_rows_1963_2023: int,
    unique_datetime_rows_1963_2023: int,
    primary_used: int,
    seasonal_counts: dict[str, int | None],
    phase_used: int | None,
) -> list[str]:
    updated: list[str] = []

    if PAPER_T1_PATH.exists():
        t1 = pd.read_csv(PAPER_T1_PATH)
        mask = t1["dataset"] == "author_hcs_catalog"
        if mask.any():
            t1.loc[mask, "notes"] = (
                f"Author HCS catalog parsed from source text file. "
                f"Raw 1963-2023 rows={parsed_rows_1963_2023}; unique valid datetimes={unique_datetime_rows_1963_2023}; "
                f"primary event-study used={primary_used} after date matching and +/-{WINDOW_DAYS}-day edge filtering."
            )
            t1.to_csv(PAPER_T1_PATH, index=False)
            updated.append(str(PAPER_T1_PATH.relative_to(ROOT)))

    if PAPER_T2_PATH.exists():
        t2 = pd.read_csv(PAPER_T2_PATH)
        mask = (t2["branch"] == "author_hcs") & (t2["analysis"] == "core_fast_null")
        if mask.any():
            t2.loc[mask, "notes"] = (
                f"Primary daily-rate lag-0 comparison; author events used={primary_used} after date matching and +/-{WINDOW_DAYS}-day edge filtering."
            )
            t2.to_csv(PAPER_T2_PATH, index=False)
            updated.append(str(PAPER_T2_PATH.relative_to(ROOT)))

    if PAPER_T3_PATH.exists():
        t3 = pd.read_csv(PAPER_T3_PATH)
        season_map = {
            "author_hcs_full_year": seasonal_counts.get("full_year"),
            "author_hcs_mar_jun": seasonal_counts.get("mar_jun"),
            "author_hcs_apr_jun": seasonal_counts.get("apr_jun"),
            "author_hcs_phase_randomized": phase_used,
        }
        changed = False
        for test_name, value in season_map.items():
            if value is None:
                continue
            mask = t3["test"] == test_name
            if mask.any():
                t3.loc[mask, "event_count"] = int(value)
                changed = True
        if changed:
            t3.to_csv(PAPER_T3_PATH, index=False)
            updated.append(str(PAPER_T3_PATH.relative_to(ROOT)))

    return updated


def main() -> int:
    missing: list[str] = []
    required = [RAW_PATH, CATALOG_PATH, ANALYSIS_DAILY_PATH, SEASONAL_PATH, PHASE_PATH]
    for path in required:
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
    if missing:
        msg = "Missing required inputs:\n" + "\n".join(f"- {p}" for p in missing)
        raise FileNotFoundError(msg)

    raw_nonblank, raw_data_any, raw_data_1963_2023 = count_raw_lines(RAW_PATH)

    cat = pd.read_csv(CATALOG_PATH)
    parsed_rows = int(len(cat))
    cat["datetime_utc"] = pd.to_datetime(cat["datetime_utc"], utc=True, errors="coerce")

    cat_1963_2023 = cat[(cat["year"] >= 1963) & (cat["year"] <= 2023)].copy()
    parsed_rows_1963_2023 = int(len(cat_1963_2023))
    invalid_datetime_rows_1963_2023 = int(cat_1963_2023["datetime_utc"].isna().sum())
    duplicate_rows_1963_2023 = int(cat_1963_2023["datetime_utc"].duplicated(keep=False).sum())
    unique_datetime_rows_1963_2023 = int(cat_1963_2023["datetime_utc"].nunique(dropna=True))
    reconciled_dates = int(cat_1963_2023["date_reconciliation_note"].fillna("").ne("").sum())

    analysis_daily = pd.read_csv(ANALYSIS_DAILY_PATH, parse_dates=["date"])
    analysis_daily["date"] = pd.to_datetime(analysis_daily["date"], errors="coerce").dt.normalize()
    analysis_daily = analysis_daily[
        (analysis_daily["date"].dt.year >= 1963) & (analysis_daily["date"].dt.year <= 2023)
    ].copy()
    primary_used = compute_primary_used_count(cat_1963_2023, analysis_daily)

    seasonal_df = pd.read_csv(SEASONAL_PATH)
    seasonal_counts = get_author_seasonal_counts(seasonal_df)

    phase_df = pd.read_csv(PHASE_PATH)
    phase_used = int(phase_df.iloc[0]["event_count_used"]) if not phase_df.empty else None

    rows = [
        {
            "count_name": "dates_reconciled_1963_2023",
            "value": reconciled_dates,
            "notes": "Invalid source Y/M/D resolved only from agreeing day-of-year/hour and elapsed-hours dates; raw fields retained.",
        },
        {
            "count_name": "raw_text_nonblank_lines",
            "value": raw_nonblank,
            "notes": "All non-empty lines in SBCtorlist1963-2024.txt, including non-data header lines.",
        },
        {
            "count_name": "raw_text_data_lines_any_year",
            "value": raw_data_any,
            "notes": "Lines beginning with year token (parsed as data rows across full file).",
        },
        {
            "count_name": "raw_text_data_lines_1963_2023",
            "value": raw_data_1963_2023,
            "notes": "Year-token data lines restricted to 1963-2023 before datetime validation and deduplication.",
        },
        {
            "count_name": "parsed_catalog_rows",
            "value": parsed_rows,
            "notes": "Rows present in data/derived/catalogs/author_hcs_catalog.csv.",
        },
        {
            "count_name": "parsed_catalog_rows_1963_2023",
            "value": parsed_rows_1963_2023,
            "notes": "Parsed catalog rows with year between 1963 and 2023 inclusive.",
        },
        {
            "count_name": "unique_datetime_rows_1963_2023",
            "value": unique_datetime_rows_1963_2023,
            "notes": "Unique non-NA datetime_utc values in 1963-2023 after dropping duplicate timestamps.",
        },
        {
            "count_name": "author_hcs_event_count_used_primary",
            "value": primary_used,
            "notes": "Count after date matching to analysis_daily, dropping NA/duplicates, and applying +/-30-day edge filter.",
        },
        {
            "count_name": "author_hcs_event_count_used_seasonal_full_year",
            "value": seasonal_counts.get("full_year"),
            "notes": "From seasonal_control_summary.csv for author_hcs full_year.",
        },
        {
            "count_name": "author_hcs_event_count_used_seasonal_mar_jun",
            "value": seasonal_counts.get("mar_jun"),
            "notes": "From seasonal_control_summary.csv for author_hcs mar_jun.",
        },
        {
            "count_name": "author_hcs_event_count_used_seasonal_apr_jun",
            "value": seasonal_counts.get("apr_jun"),
            "notes": "From seasonal_control_summary.csv for author_hcs apr_jun.",
        },
        {
            "count_name": "author_hcs_event_count_used_phase_randomized",
            "value": phase_used,
            "notes": "From phase_randomized_author_hcs_summary.csv event_count_used.",
        },
    ]

    recon_df = pd.DataFrame(rows, columns=["count_name", "value", "notes"])
    RECON_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    recon_df.to_csv(RECON_TABLE_PATH, index=False)

    updated_files = []
    updated_files.extend(
        update_methods_metadata(
            parsed_rows_1963_2023=parsed_rows_1963_2023,
            unique_datetime_rows_1963_2023=unique_datetime_rows_1963_2023,
            invalid_datetime_rows_1963_2023=invalid_datetime_rows_1963_2023,
            duplicate_rows_1963_2023=duplicate_rows_1963_2023,
            primary_used=primary_used,
            reconciled_dates=reconciled_dates,
        )
    )
    updated_files.extend(
        update_paper_tables(
            parsed_rows_1963_2023=parsed_rows_1963_2023,
            unique_datetime_rows_1963_2023=unique_datetime_rows_1963_2023,
            primary_used=primary_used,
            seasonal_counts=seasonal_counts,
            phase_used=phase_used,
        )
    )

    report_lines = [
        "# Author HCS Count Reconciliation",
        "",
        "## Summary",
        f"- Raw nonblank lines in source text: {raw_nonblank}",
        f"- Parsed catalog rows: {parsed_rows}",
        f"- Parsed rows in 1963-2023: {parsed_rows_1963_2023}",
        f"- Unique valid datetimes in 1963-2023: {unique_datetime_rows_1963_2023}",
        f"- Primary event-study count used: {primary_used}",
        f"- Seasonal author counts (full_year, mar_jun, apr_jun): {seasonal_counts.get('full_year')}, {seasonal_counts.get('mar_jun')}, {seasonal_counts.get('apr_jun')}",
        f"- Phase-randomized author count used: {phase_used}",
        "",
        "## Discrepancy Source",
        "- Two duplicate datetime pairs exist in 1963-2023 (4 duplicate rows total).",
        f"- {reconciled_dates} invalid source dates reconciled from agreeing redundant fields; {invalid_datetime_rows_1963_2023} dates remain invalid.",
        "- Source line 848 has day=0; day-of-year 304 and elapsed hours 270264 both identify 1993-10-31. The resolved timestamp is used while raw fields are preserved.",
        "- Primary and robustness event studies drop NA dates, deduplicate dates, and apply +/-30-day edge filtering, reducing usable events further.",
        "",
        "## Metadata Files Updated",
    ]
    if updated_files:
        for item in updated_files:
            report_lines.append(f"- {item}")
    else:
        report_lines.append("- None")

    RECON_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECON_REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"Saved reconciliation table: {RECON_TABLE_PATH}")
    print(f"Saved reconciliation report: {RECON_REPORT_PATH}")
    if updated_files:
        print("Updated metadata/reporting files:")
        for item in updated_files:
            print(f"- {item}")
    else:
        print("No metadata/reporting files needed updates.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
