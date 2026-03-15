from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from _utils import TABLE_DIR, write_dataframe, write_script_manifest
from common import ROOT, make_logger


BX_PREFERENCE = ["bx_gsm", "bx_gse", "bx"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconstruct daily HCS crossings from OMNI IMF polarity.")
    parser.add_argument("--bx-threshold", type=float, default=0.3, help="Absolute Bx threshold below which polarity is ambiguous.")
    parser.add_argument("--gap-fill-days", type=int, default=1, help="Forward-fill ambiguous polarity gaps up to this many days.")
    parser.add_argument("--min-side-days", type=int, default=2, help="Require at least this many consecutive valid days on each side of a crossing.")
    parser.add_argument("--min-spacing-days", type=int, default=2, help="Drop crossings closer than this many days to the previous retained crossing.")
    return parser.parse_args()


def detect_bx_column(df: pd.DataFrame) -> str:
    columns = list(df.columns)
    for preferred in BX_PREFERENCE:
        direct = f"{preferred}_mean"
        if direct in columns:
            return direct
        if preferred in columns:
            return preferred
    for column in columns:
        lower = column.lower()
        if "bx" in lower and ("mean" in lower or lower == "bx"):
            return column
    raise ValueError("No Bx-like OMNI daily column found.")


def compute_run_lengths(series: pd.Series) -> pd.Series:
    change = series.ne(series.shift()) | series.isna() | series.shift().isna()
    group_id = change.cumsum()
    lengths = series.groupby(group_id).transform("size")
    lengths[series.isna()] = 0
    return lengths.astype(int)


def main() -> int:
    args = parse_args()
    logger = make_logger("26_reconstruct_hcs_from_omni")

    omni_path = ROOT / "data" / "derived" / "daily" / "omni_daily.csv"
    df = pd.read_csv(omni_path, parse_dates=["date"])
    bx_column = detect_bx_column(df)

    work = df[["date", bx_column]].copy().sort_values("date").reset_index(drop=True)
    work = work.rename(columns={bx_column: "bx"})
    work["bx"] = pd.to_numeric(work["bx"], errors="coerce")
    work["polarity_raw"] = np.sign(work["bx"])
    work.loc[work["bx"].abs() < args.bx_threshold, "polarity_raw"] = np.nan

    work["polarity_filled"] = work["polarity_raw"].ffill(limit=args.gap_fill_days)
    valid = work["polarity_filled"].notna()
    work["polarity_prev"] = work["polarity_filled"].shift(1)
    work["bx_prev"] = work["bx"].shift(1)
    work["run_length"] = compute_run_lengths(work["polarity_filled"])
    work["run_length_prev"] = work["run_length"].shift(1)
    work["candidate_flip"] = (
        valid
        & work["polarity_prev"].notna()
        & (work["polarity_filled"] != work["polarity_prev"])
    )
    work["side_length_ok"] = (
        work["run_length"].fillna(0) >= args.min_side_days
    ) & (
        work["run_length_prev"].fillna(0) >= args.min_side_days
    )

    candidates = work.loc[work["candidate_flip"] & work["side_length_ok"]].copy()
    candidate_count = int(len(candidates))

    candidates["date"] = candidates["date"].dt.normalize()
    candidates["bx_before"] = candidates["bx_prev"]
    candidates["bx_after"] = candidates["bx"]
    candidates["polarity_before"] = candidates["polarity_prev"].astype("Int64")
    candidates["polarity_after"] = candidates["polarity_filled"].astype("Int64")
    candidates["method"] = "later_date_of_consecutive_daily_polarity_flip"
    candidates["notes"] = (
        f"Bx threshold={args.bx_threshold} nT; ambiguous gaps ffilled up to {args.gap_fill_days} day; "
        f"required run lengths >= {args.min_side_days} days on both sides when available."
    )

    retained_rows: list[pd.Series] = []
    last_date: pd.Timestamp | None = None
    for _, row in candidates.iterrows():
        current_date = pd.Timestamp(row["date"]) 
        if last_date is None or (current_date - last_date).days > args.min_spacing_days:
            retained_rows.append(row)
            last_date = current_date

    retained = pd.DataFrame(retained_rows)
    if retained.empty:
        retained = pd.DataFrame(columns=["date", "bx_before", "bx_after", "polarity_before", "polarity_after", "method", "notes"])
    else:
        retained = retained[["date", "bx_before", "bx_after", "polarity_before", "polarity_after", "method", "notes"]].copy()
        retained["year"] = pd.to_datetime(retained["date"]).dt.year

    outputs = {
        "catalog": write_dataframe(retained.drop(columns=["year"], errors="ignore"), "data/derived/catalogs/hcs_from_omni"),
    }

    summary = retained.groupby("year", as_index=False).size().rename(columns={"size": "crossing_count"}) if not retained.empty else pd.DataFrame(columns=["year", "crossing_count"])
    summary_path = ROOT / "data" / "derived" / "tables" / "hcs_from_omni_summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    outputs["year_summary"] = str(summary_path.relative_to(ROOT))

    metrics = {
        "bx_column_used": bx_column,
        "candidate_crossings_before_spacing": candidate_count,
        "retained_crossings": int(len(retained)),
        "date_min": None if retained.empty else str(pd.to_datetime(retained["date"]).min().date()),
        "date_max": None if retained.empty else str(pd.to_datetime(retained["date"]).max().date()),
        "bx_threshold": args.bx_threshold,
        "min_spacing_days": args.min_spacing_days,
    }
    assumptions = [
        "Polarity is defined as sign(Bx) using the preferred available daily OMNI Bx-like component.",
        "Crossing date is set to the later of two consecutive daily observations because a midpoint is not a clean daily date.",
    ]
    write_script_manifest("26_reconstruct_hcs_from_omni.py", [omni_path], outputs, metrics, assumptions=assumptions, ok=not retained.empty)

    logger.info("Bx column used: %s", bx_column)
    logger.info("Candidate crossings before spacing filter: %d", candidate_count)
    logger.info("Retained crossings: %d", len(retained))
    return 0 if not retained.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
