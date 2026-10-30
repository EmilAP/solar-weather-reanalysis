from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

from _utils import nearest_event_differences, make_logger, save_figure, write_dataframe, write_script_manifest


CATALOGS = {
    "author_hcs": "data/derived/catalogs/author_hcs_catalog.csv",
    "reconstructed_hcs": "data/derived/catalogs/hcs_from_omni.csv",
    "cir_proxy": "data/derived/catalogs/cir_proxy_catalog.csv",
    "hss_onset": "data/derived/catalogs/hss_onset_catalog.csv",
}


def load_dates(path: str) -> list[pd.Timestamp]:
    df = pd.read_csv(path)
    for column in ["datetime_utc", "analysis_time_utc", "date"]:
        if column in df.columns:
            dates = pd.to_datetime(df[column], utc=True, errors="coerce").dt.tz_convert(None).dropna().dt.normalize().drop_duplicates()
            return dates[dates.dt.year.between(1963, 2023)].sort_values().tolist()
    return []


def main() -> int:
    logger = make_logger("21_compare_event_catalogs")
    available = {name: path for name, path in CATALOGS.items() if Path(path).exists()}
    if len(available) < 2:
        write_script_manifest("21_compare_event_catalogs.py", list(CATALOGS.values()), [], {"error": "Fewer than two catalogs available"}, ok=False)
        return 1

    comparison_rows: list[dict[str, object]] = []
    outputs: dict[str, object] = {}
    loaded = {name: load_dates(path) for name, path in available.items()}

    for left_name, left_dates in loaded.items():
        for right_name, right_dates in loaded.items():
            if left_name >= right_name:
                continue
            diffs = nearest_event_differences(left_dates, right_dates)
            outputs[f"{left_name}_vs_{right_name}"] = write_dataframe(diffs, f"data/derived/catalogs/{left_name}_vs_{right_name}_nearest")
            comparison_rows.append(
                {
                    "left_catalog": left_name,
                    "right_catalog": right_name,
                    "left_count": len(left_dates),
                    "right_count": len(right_dates),
                    "median_abs_delta_days": float(diffs["delta_days"].abs().median()) if not diffs.empty else None,
                    "overlap_within_1_day": int((diffs["delta_days"].abs() <= 1).sum()) if not diffs.empty else 0,
                    "overlap_within_3_days": int((diffs["delta_days"].abs() <= 3).sum()) if not diffs.empty else 0,
                }
            )

    summary = pd.DataFrame(comparison_rows)
    outputs["summary"] = write_dataframe(summary, "data/derived/tables/event_catalog_overlap_summary")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(summary["left_catalog"] + " vs " + summary["right_catalog"], summary["median_abs_delta_days"], color="0.4")
    ax.set_ylabel("Median absolute nearest-event delta (days)")
    ax.set_title("Event catalog timing differences")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    outputs["comparison_plot"] = save_figure(fig, "data/derived/figures/event_catalog_timing_differences")

    write_script_manifest("21_compare_event_catalogs.py", list(available.values()), outputs, {"comparisons": int(len(summary))})
    logger.info("Compared %d catalog pairs", len(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
