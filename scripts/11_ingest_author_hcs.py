from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from _utils import CATALOG_DIR, find_one, load_config, make_logger, write_dataframe, write_script_manifest


DATA_LINE_RE = re.compile(r"^\s*(19|20)\d{2}\s+")


def parse_line(raw_line: str) -> dict[str, object] | None:
    line = raw_line.strip()
    if not line:
        return None
    tokens = re.split(r"\s+", line)
    if len(tokens) < 3 or not tokens[0].isdigit():
        return None

    year = int(tokens[0])
    if year < 1900 or year > 2100:
        return None

    row: dict[str, object] = {
        "raw_line": raw_line.rstrip("\n"),
        "year": year,
        "month": int(tokens[1]) if len(tokens) > 1 and tokens[1].lstrip("+-").isdigit() else None,
        "day": int(tokens[2]) if len(tokens) > 2 and tokens[2].lstrip("+-").isdigit() else None,
        "hour": int(tokens[3]) if len(tokens) > 3 and tokens[3].lstrip("+-").isdigit() else 0,
        "sign": tokens[4] if len(tokens) > 4 else None,
        "doy": int(tokens[5]) if len(tokens) > 5 and tokens[5].lstrip("+-").isdigit() else None,
        "hoursfrom1963": float(tokens[6]) if len(tokens) > 6 and re.fullmatch(r"[-+]?\d+(\.\d+)?", tokens[6]) else None,
    }
    return row


def reconcile_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    original = pd.to_datetime(
        dict(year=out["year"], month=out["month"], day=out["day"], hour=out["hour"].fillna(0)),
        errors="coerce", utc=True,
    )
    year_start = pd.to_datetime(out["year"].astype(str), format="%Y", utc=True)
    doy = pd.to_numeric(out["doy"], errors="coerce")
    hour = pd.to_numeric(out["hour"], errors="coerce")
    from_doy = year_start + pd.to_timedelta(doy - 1, unit="D") + pd.to_timedelta(hour, unit="h")
    from_hours = pd.Timestamp("1963-01-01", tz="UTC") + pd.to_timedelta(
        pd.to_numeric(out["hoursfrom1963"], errors="coerce"), unit="h"
    )
    redundant_valid = (
        from_doy.notna() & from_hours.notna() & from_doy.eq(from_hours)
        & from_doy.dt.year.eq(out["year"]) & doy.ge(1)
        & hour.between(0, 23) & hour.eq(hour.round())
    )
    conflict = original.notna() & (
        (from_doy.notna() & original.ne(from_doy))
        | (from_hours.notna() & original.ne(from_hours))
    )
    unresolved = original.isna() & ~redundant_valid
    if (conflict | unresolved).any():
        lines = out.loc[conflict | unresolved, "line_number"].tolist()
        raise ValueError(f"Conflicting or unresolved author HCS dates at source lines {lines}.")
    repaired = original.isna() & redundant_valid
    out["datetime_source_utc"] = original
    out["datetime_utc"] = original.where(~repaired, from_doy)
    out["date_reconciliation_note"] = ""
    out.loc[repaired, "date_reconciliation_note"] = (
        "Invalid source Y/M/D resolved using agreement of year/day-of-year/hour "
        "and elapsed hours since 1963-01-01; raw source fields preserved."
    )
    out["date"] = out["datetime_utc"].dt.date.astype("string")
    out["duplicate_datetime"] = out["datetime_utc"].duplicated(keep=False)
    return out


def main() -> int:
    logger = make_logger("11_ingest_author_hcs")
    cfg = load_config()
    path = find_one(cfg["file_search"]["author_hcs_patterns"], required=False)

    if path is None:
        write_script_manifest(
            "11_ingest_author_hcs.py",
            [],
            [],
            {"error": "Author HCS/SBC file not found in workspace"},
            assumptions=["This script searches the workspace automatically and does not fabricate the author file."],
            ok=False,
        )
        logger.error("Author HCS/SBC file not found in workspace")
        return 1

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    parsed_rows: list[dict[str, object]] = []
    malformed: list[dict[str, object]] = []

    for line_number, line in enumerate(lines, start=1):
        parsed = parse_line(line)
        if parsed is None:
            if DATA_LINE_RE.match(line):
                malformed.append({"line_number": line_number, "raw_line": line})
            continue
        parsed["line_number"] = line_number
        parsed_rows.append(parsed)

    df = pd.DataFrame(parsed_rows)
    if df.empty:
        write_script_manifest(
            "11_ingest_author_hcs.py",
            [path],
            [],
            {"error": "No parseable rows found in author HCS file"},
            ok=False,
        )
        return 1

    df = reconcile_dates(df)
    repaired = df["date_reconciliation_note"].ne("")
    if repaired.any():
        logger.warning("Reconciled %d invalid author dates from agreeing redundant fields: source lines %s.",
                       int(repaired.sum()), df.loc[repaired, "line_number"].tolist())

    malformed_df = pd.DataFrame(malformed)
    catalog_outputs = write_dataframe(df, "data/derived/catalogs/author_hcs_catalog")
    outputs: dict[str, object] = {**catalog_outputs}
    if not malformed_df.empty:
        outputs["malformed_csv"] = write_dataframe(malformed_df, "data/derived/catalogs/author_hcs_malformed")["csv"]

    metrics = {
        "source_path": str(path.relative_to(Path(__file__).resolve().parents[1])),
        "row_count": int(len(df)),
        "count_1963_2023": int(((df["year"] >= 1963) & (df["year"] <= 2023)).sum()),
        "count_1963_2024": int(((df["year"] >= 1963) & (df["year"] <= 2024)).sum()),
        "min_datetime_utc": None if df["datetime_utc"].isna().all() else str(df["datetime_utc"].min()),
        "max_datetime_utc": None if df["datetime_utc"].isna().all() else str(df["datetime_utc"].max()),
        "duplicate_rows": int(df["duplicate_datetime"].sum()),
        "malformed_rows": int(len(malformed_df)),
        "dates_reconciled": int(repaired.sum()),
        "reconciled_source_lines": df.loc[repaired, "line_number"].tolist(),
        "paper_count_note": "Paper states 1792, but author note says actual count is 1793 because of IDL indexing.",
    }
    write_script_manifest(
        "11_ingest_author_hcs.py",
        [path],
        outputs,
        metrics,
        assumptions=[
            "Parsed irregular spacing and optional header lines by tokenizing numeric rows.",
            "Invalid Y/M/D is resolved only when year/day-of-year/hour and elapsed hours agree; conflicts fail explicitly. Original fields and reconciliation notes are retained.",
        ],
    )
    logger.info("Parsed %d author HCS rows from %s", len(df), path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
