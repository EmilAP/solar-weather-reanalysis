from __future__ import annotations

import argparse
import pandas as pd

from _utils import write_dataframe, write_script_manifest
from common import ROOT, make_logger
from _hcs_reconstruction import compute_run_lengths, detect_bx_column, reconstruct_hcs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconstruct daily HCS crossings from OMNI IMF polarity.")
    parser.add_argument("--bx-threshold", type=float, default=0.3, help="Absolute Bx threshold below which polarity is ambiguous.")
    parser.add_argument("--gap-fill-days", type=int, default=1, help="Forward-fill ambiguous polarity gaps up to this many days.")
    parser.add_argument("--min-side-days", type=int, default=2, help="Require at least this many consecutive valid days on each side of a crossing.")
    parser.add_argument("--min-spacing-days", type=int, default=2, help="Drop crossings closer than this many days to the previous retained crossing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = make_logger("26_reconstruct_hcs_from_omni")

    omni_path = ROOT / "data" / "derived" / "daily" / "omni_daily.csv"
    df = pd.read_csv(omni_path, parse_dates=["date"])
    bx_column = detect_bx_column(df)

    retained, candidate_count = reconstruct_hcs(
        df, args.bx_threshold, args.gap_fill_days, args.min_side_days, args.min_spacing_days,
    )
    if not retained.empty:
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
