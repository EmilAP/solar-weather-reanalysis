from __future__ import annotations

import numpy as np
import pandas as pd


BX_PREFERENCE = ["bx_gsm", "bx_gse", "bx"]


def detect_bx_column(df: pd.DataFrame) -> str:
    for preferred in BX_PREFERENCE:
        for column in (f"{preferred}_mean", preferred):
            if column in df:
                return column
    for column in df:
        lower = column.lower()
        if "bx" in lower and ("mean" in lower or lower == "bx"):
            return column
    raise ValueError("No Bx-like OMNI daily column found.")


def compute_run_lengths(series: pd.Series) -> pd.Series:
    change = series.ne(series.shift()) | series.isna() | series.shift().isna()
    lengths = series.groupby(change.cumsum()).transform("size")
    lengths[series.isna()] = 0
    return lengths.astype(int)


def reconstruct_hcs(
    daily: pd.DataFrame,
    bx_threshold: float = 0.3,
    gap_fill_days: int = 1,
    min_side_days: int = 2,
    min_spacing_days: int = 2,
    coverage_ok: pd.Series | None = None,
) -> tuple[pd.DataFrame, int]:
    bx_column = detect_bx_column(daily)
    work = daily[["date", bx_column]].copy()
    if coverage_ok is not None:
        if not coverage_ok.index.equals(daily.index) or coverage_ok.isna().any():
            raise ValueError("Coverage eligibility must match the daily frame without missing values.")
        work["coverage_ok"] = coverage_ok.astype(bool)
    work = work.sort_values("date").reset_index(drop=True).rename(columns={bx_column: "bx"})
    work["bx"] = pd.to_numeric(work["bx"], errors="coerce")
    if coverage_ok is not None:
        work.loc[~work["coverage_ok"], "bx"] = np.nan
    work["polarity_raw"] = np.sign(work["bx"])
    work.loc[work["bx"].abs() < bx_threshold, "polarity_raw"] = np.nan
    work["polarity_filled"] = work["polarity_raw"].ffill(limit=gap_fill_days)
    if coverage_ok is not None:
        work.loc[~work["coverage_ok"], "polarity_filled"] = np.nan
    work["polarity_prev"] = work["polarity_filled"].shift()
    work["bx_prev"] = work["bx"].shift()
    work["run_length"] = compute_run_lengths(work["polarity_filled"])
    work["run_length_prev"] = work["run_length"].shift()
    candidates = work.loc[
        work["polarity_filled"].notna() & work["polarity_prev"].notna()
        & work["polarity_filled"].ne(work["polarity_prev"])
        & work["run_length"].ge(min_side_days)
        & work["run_length_prev"].ge(min_side_days)
    ].copy()
    candidate_count = len(candidates)
    retained = []
    last_date = None
    for _, row in candidates.iterrows():
        date = pd.Timestamp(row["date"]).normalize()
        if last_date is not None and (date - last_date).days <= min_spacing_days:
            continue
        retained.append({
            "date": date, "bx_before": row["bx_prev"], "bx_after": row["bx"],
            "polarity_before": int(row["polarity_prev"]), "polarity_after": int(row["polarity_filled"]),
            "method": "later_date_of_consecutive_daily_polarity_flip",
            "notes": (
                f"Bx threshold={bx_threshold} nT; ambiguous gaps ffilled up to {gap_fill_days} day; "
                f"required run lengths >= {min_side_days} days on both sides when available."
            ),
        })
        last_date = date
    columns = ["date", "bx_before", "bx_after", "polarity_before", "polarity_after", "method", "notes"]
    result = pd.DataFrame(retained, columns=columns)
    for column in ("polarity_before", "polarity_after"):
        result[column] = result[column].astype("Int64")
    return result, candidate_count
