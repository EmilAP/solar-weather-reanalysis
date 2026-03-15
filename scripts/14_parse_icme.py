from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from _utils import find_one, load_config, make_logger, write_dataframe, write_script_manifest


ICME_COLUMNS = [
    "disturbance_time",
    "plasma_field_start",
    "plasma_field_end",
    "compression_start",
    "compression_end",
    "mc_start",
    "mc_end",
    "bde_flag",
    "bif_flag",
    "quality",
    "dv_kms",
    "v_icme_kms",
    "v_max_kms",
    "b_nt",
    "mc_flag",
    "dst_nt",
    "v_transit_kms",
    "lasco_ref",
]


def read_icme_csv(path: Path) -> pd.DataFrame:
    rows: list[list[str]] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            if row[0].startswith("Disturbance"):
                continue
            if not row[0][:4].isdigit():
                continue
            padded = row[: len(ICME_COLUMNS)] + [None] * max(0, len(ICME_COLUMNS) - len(row))
            rows.append(padded[: len(ICME_COLUMNS)])
    return pd.DataFrame(rows, columns=ICME_COLUMNS)


def main() -> int:
    logger = make_logger("14_parse_icme")
    cfg = load_config()
    path = find_one(cfg["file_search"]["icme_patterns"])

    if path.suffix.lower() != ".csv":
        csv_candidate = find_one(["**/icmetable2.csv"], required=False)
        if csv_candidate is None:
            write_script_manifest("14_parse_icme.py", [path], [], {"error": "ICME CSV not found"}, ok=False)
            return 1
        path = csv_candidate

    df = read_icme_csv(path)
    for column in ["disturbance_time", "plasma_field_start", "plasma_field_end"]:
        df[f"{column}_utc"] = pd.to_datetime(df[column], errors="coerce", utc=True, format="%Y/%m/%d %H%M")
    df["analysis_time_utc"] = df["plasma_field_start_utc"].fillna(df["disturbance_time_utc"])
    df["analysis_date"] = df["analysis_time_utc"].dt.date.astype("string")

    outputs = write_dataframe(df, "data/derived/catalogs/icme_catalog")
    metrics = {
        "row_count": int(len(df)),
        "min_analysis_time": None if df["analysis_time_utc"].isna().all() else str(df["analysis_time_utc"].min()),
        "max_analysis_time": None if df["analysis_time_utc"].isna().all() else str(df["analysis_time_utc"].max()),
        "missing_analysis_time": int(df["analysis_time_utc"].isna().sum()),
    }
    write_script_manifest(
        "14_parse_icme.py",
        [path],
        outputs,
        metrics,
        assumptions=["ICME analysis time defaults to plasma/field start, then disturbance time when missing."],
    )
    logger.info("Parsed %d ICME rows", len(df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
