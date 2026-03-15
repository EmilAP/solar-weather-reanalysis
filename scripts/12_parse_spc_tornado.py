from __future__ import annotations

import pandas as pd

from _utils import load_config, find_one, make_logger, write_dataframe, write_script_manifest


def main() -> int:
    logger = make_logger("12_parse_spc_tornado")
    cfg = load_config()
    path = find_one(cfg["file_search"]["tornado_patterns"])

    df = pd.read_csv(path)

    numeric_cols = ["yr", "mo", "dy", "mag", "inj", "fat", "slat", "slon", "elat", "elon", "len", "wid"]
    for column in numeric_cols:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    # Build date from yr/mo/dy instead of assuming an existing usable "date" column
    df["date"] = pd.to_datetime(
        {
            "year": df["yr"],
            "month": df["mo"],
            "day": df["dy"],
        },
        errors="coerce",
    )

    # Normalize time field into HH:MM where possible
    if "time" in df.columns:
        time_str = (
            df["time"]
            .fillna("")
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.zfill(4)
        )
        df["event_datetime_local"] = pd.to_datetime(
            df["date"].dt.strftime("%Y-%m-%d") + " " + time_str.str[:2] + ":" + time_str.str[2:4],
            errors="coerce",
        )
    else:
        df["event_datetime_local"] = pd.NaT

    df["year"] = df["date"].dt.year
    df["rating_numeric"] = df["mag"]
    df["strong_tornado"] = (df["rating_numeric"] >= cfg["tornado"]["strong_rating_threshold"]).astype(int)
    df["all_tornado"] = 1
    df["injuries"] = pd.to_numeric(df.get("inj", 0), errors="coerce").fillna(0)
    df["fatalities"] = pd.to_numeric(df.get("fat", 0), errors="coerce").fillna(0)

    keep_cols = [
        "om",
        "date",
        "event_datetime_local",
        "year",
        "st",
        "stf",
        "stn",
        "mag",
        "rating_numeric",
        "strong_tornado",
        "injuries",
        "fatalities",
        "slat",
        "slon",
        "elat",
        "elon",
        "len",
        "wid",
        "f1",
        "f2",
        "f3",
        "f4",
    ]
    keep_cols = [col for col in keep_cols if col in df.columns]
    event_df = df[keep_cols].copy()

    # Explicit normalized date column avoids the groupby warning / missing date issue
    df["date_day"] = df["date"].dt.normalize()

    daily = (
        df.groupby("date_day", as_index=False)
        .agg(
            all_tornadoes=("all_tornado", "sum"),
            strong_tornadoes=("strong_tornado", "sum"),
            daily_injuries=("injuries", "sum"),
            daily_fatalities=("fatalities", "sum"),
        )
        .rename(columns={"date_day": "date"})
    )

    daily["year"] = daily["date"].dt.year
    daily["month"] = daily["date"].dt.month
    daily["doy"] = daily["date"].dt.dayofyear

    outputs = {
        "events": write_dataframe(event_df, "data/derived/daily/tornado_events_clean"),
        "daily": write_dataframe(daily, "data/derived/daily/tornado_daily"),
    }
    metrics = {
        "row_count": int(len(event_df)),
        "daily_rows": int(len(daily)),
        "min_date": str(daily["date"].min().date()),
        "max_date": str(daily["date"].max().date()),
        "strong_count": int(event_df["strong_tornado"].sum()),
    }
    assumptions = [
        cfg["tornado"]["utc_assumption"],
        cfg["tornado"]["fscale_harmonization"],
    ]
    write_script_manifest("12_parse_spc_tornado.py", [path], outputs, metrics, assumptions=assumptions)
    logger.info("Parsed %d tornado events", len(event_df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())