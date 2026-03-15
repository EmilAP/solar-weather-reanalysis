from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

from _utils import find_one, load_config, make_logger, nearest_event_differences, parse_omni_hourly, write_dataframe, write_script_manifest


def main() -> int:
    logger = make_logger("17_build_independent_hcs_from_omni")
    cfg = load_config()
    path = find_one(cfg["file_search"]["omni_patterns"])
    omni = parse_omni_hourly(path)
    omni = omni[["datetime_utc", "bx_gse", "by_gse", "bz_gse", "speed"]].copy().dropna(subset=["bx_gse", "by_gse"])

    omni["sector_raw"] = np.sign(-(omni["bx_gse"] * omni["by_gse"]))
    omni.loc[omni["sector_raw"] == 0, "sector_raw"] = np.nan
    rolling_hours = int(cfg["independent_hcs"]["rolling_hours"])
    omni["sector_smooth"] = np.sign(
        pd.Series(omni["sector_raw"], index=omni.index).rolling(rolling_hours, center=True, min_periods=max(3, rolling_hours // 2)).median()
    )
    omni["sector_prev"] = omni["sector_smooth"].shift(1)
    omni["sign_flip"] = (omni["sector_smooth"].notna()) & (omni["sector_prev"].notna()) & (omni["sector_smooth"] != omni["sector_prev"])
    candidates = omni.loc[omni["sign_flip"], ["datetime_utc", "sector_prev", "sector_smooth", "speed"]].copy()

    min_gap_hours = int(cfg["independent_hcs"]["min_gap_hours"])
    selected: list[pd.Series] = []
    last_time: pd.Timestamp | None = None
    for _, row in candidates.iterrows():
        current = pd.Timestamp(row["datetime_utc"])
        if last_time is None or (current - last_time) >= pd.Timedelta(hours=min_gap_hours):
            selected.append(row)
            last_time = current

    catalog = pd.DataFrame(selected)
    if catalog.empty:
        write_script_manifest("17_build_independent_hcs_from_omni.py", [path], [], {"error": "No reconstructed HCS events found"}, ok=False)
        return 1

    catalog = catalog.rename(columns={"sector_prev": "sector_before", "sector_smooth": "sector_after", "speed": "speed_at_crossing"})
    catalog["date"] = pd.to_datetime(catalog["datetime_utc"]).dt.date.astype("string")
    catalog["year"] = pd.to_datetime(catalog["datetime_utc"]).dt.year

    outputs = {"catalog": write_dataframe(catalog, "data/derived/catalogs/independent_hcs_catalog")}
    metrics = {
        "event_count": int(len(catalog)),
        "median_spacing_days": float(pd.Series(pd.to_datetime(catalog["datetime_utc"])).diff().dropna().dt.total_seconds().median() / 86400.0) if len(catalog) > 1 else None,
    }

    author_path = Path("data/derived/catalogs/author_hcs_catalog.csv")
    if author_path.exists():
        author = pd.read_csv(author_path, parse_dates=["datetime_utc"])
        diffs = nearest_event_differences(author["datetime_utc"].dropna().tolist(), catalog["datetime_utc"].dropna().tolist())
        outputs["nearest_author_diffs"] = write_dataframe(diffs, "data/derived/catalogs/author_vs_independent_hcs_nearest")
        metrics["author_event_count"] = int(author["datetime_utc"].notna().sum())
        metrics["median_author_to_independent_days"] = float(diffs["delta_days"].abs().median()) if not diffs.empty else None

    write_script_manifest(
        "17_build_independent_hcs_from_omni.py",
        [path],
        outputs,
        metrics,
        assumptions=[cfg["independent_hcs"]["polarity_rule"]],
    )
    logger.info("Built %d reconstructed HCS events", len(catalog))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
