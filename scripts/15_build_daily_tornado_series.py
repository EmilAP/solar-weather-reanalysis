from __future__ import annotations

import pandas as pd

from _utils import load_config, make_logger, write_dataframe, write_script_manifest


def main() -> int:
    logger = make_logger("15_build_daily_tornado_series")
    cfg = load_config()
    start_date = pd.Timestamp(cfg["analysis_period"]["start_date"])
    end_date = pd.Timestamp(cfg["analysis_period"]["end_date"])

    tornado_path = pd.read_csv("data/derived/daily/tornado_daily.csv", parse_dates=["date"])
    omni_path = pd.read_csv("data/derived/daily/omni_daily.csv", parse_dates=["date"])

    idx = pd.DataFrame({"date": pd.date_range(start_date, end_date, freq="D")})
    merged = idx.merge(tornado_path, on="date", how="left").merge(omni_path, on="date", how="left")
    fill_cols = ["all_tornadoes", "strong_tornadoes", "daily_injuries", "daily_fatalities"]
    for column in fill_cols:
        if column in merged.columns:
            merged[column] = merged[column].fillna(0)

    merged["year"] = merged["date"].dt.year
    merged["month"] = merged["date"].dt.month
    merged["doy"] = merged["date"].dt.dayofyear
    merged["outbreak_day"] = (merged["all_tornadoes"] >= cfg["tornado"]["outbreak_day_threshold"]).astype(int)

    outputs = write_dataframe(merged, "data/derived/daily/analysis_daily")
    metrics = {
        "row_count": int(len(merged)),
        "min_date": str(merged["date"].min().date()),
        "max_date": str(merged["date"].max().date()),
        "outbreak_days": int(merged["outbreak_day"].sum()),
    }
    write_script_manifest(
        "15_build_daily_tornado_series.py",
        ["data/derived/daily/tornado_daily.csv", "data/derived/daily/omni_daily.csv"],
        outputs,
        metrics,
    )
    logger.info("Built master daily analysis table with %d rows", len(merged))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())