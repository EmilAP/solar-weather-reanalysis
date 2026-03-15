from __future__ import annotations

import pandas as pd

from _utils import daily_summary, find_one, load_config, make_logger, parse_omni_hourly, write_dataframe, write_script_manifest


def main() -> int:
    logger = make_logger("13_parse_omni")
    cfg = load_config()
    path = find_one(cfg["file_search"]["omni_patterns"])

    hourly = parse_omni_hourly(path)
    keep_cols = [
        "datetime_utc",
        "date",
        "year",
        "doy",
        "hour",
        "f_scalar",
        "b_mag",
        "bx_gse",
        "by_gse",
        "bz_gse",
        "by_gsm",
        "bz_gsm",
        "sigma_bz",
        "proton_density",
        "speed",
        "flow_pressure",
        "electric_field",
        "plasma_beta",
        "dst",
        "ae",
        "ap",
        "f107",
    ]
    hourly = hourly[keep_cols].copy()
    daily = daily_summary(
        hourly,
        {
            "f_scalar": "mean",
            "b_mag": "mean",
            "bx_gse": "mean",
            "by_gse": "mean",
            "bz_gse": "mean",
            "by_gsm": "mean",
            "bz_gsm": "mean",
            "sigma_bz": "mean",
            "proton_density": "mean",
            "speed": ["mean", "max"],
            "flow_pressure": "mean",
            "electric_field": "mean",
            "plasma_beta": "mean",
            "dst": "mean",
            "ae": "mean",
            "ap": "mean",
            "f107": "mean",
        },
    )
    daily.columns = ["_".join(col).strip("_") if isinstance(col, tuple) else col for col in daily.columns]
    daily = daily.rename(columns={"date_": "date", "year_": "year", "month_": "month", "doy_": "doy"})

    counts_per_year = hourly.groupby("year", as_index=False).size().rename(columns={"size": "hour_count"})
    missingness = hourly.isna().mean().round(4).to_dict()

    outputs = {
        "hourly": write_dataframe(hourly, "data/derived/daily/omni_hourly_clean"),
        "daily": write_dataframe(daily, "data/derived/daily/omni_daily"),
        "counts_per_year": write_dataframe(counts_per_year, "data/derived/tables/omni_counts_per_year"),
    }
    metrics = {
        "row_count_hourly": int(len(hourly)),
        "row_count_daily": int(len(daily)),
        "year_start": int(hourly["year"].min()),
        "year_end": int(hourly["year"].max()),
        "missingness": missingness,
    }
    write_script_manifest(
        "13_parse_omni.py",
        [path],
        outputs,
        metrics,
        assumptions=["OMNI fields parsed using the public OMNI2 hourly format definition from OMNIWeb documentation."],
    )
    logger.info("Parsed %d OMNI hourly rows", len(hourly))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
