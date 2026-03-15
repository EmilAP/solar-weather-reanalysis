from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

from _utils import build_event_window, empirical_pvalue, load_config, make_logger, save_figure, season_matched_random_dates, write_dataframe, write_script_manifest


EVENT_SOURCES = {
    "author_hcs": "data/derived/catalogs/author_hcs_catalog.csv",
    "reconstructed_hcs": "data/derived/catalogs/independent_hcs_catalog.csv",
    "cir_proxy": "data/derived/catalogs/cir_proxy_catalog.csv",
    "hss_onset": "data/derived/catalogs/hss_onset_catalog.csv",
}
METRICS = ["all_tornadoes", "strong_tornadoes", "daily_injuries", "daily_fatalities"]


def load_event_dates(path: str) -> list[pd.Timestamp]:
    df = pd.read_csv(path)
    for candidate in ["datetime_utc", "analysis_time_utc", "date"]:
        if candidate in df.columns:
            series = pd.to_datetime(df[candidate], errors="coerce")
            return series.dropna().dt.normalize().tolist()
    return []


def main() -> int:
    logger = make_logger("19_run_stricter_event_study")
    cfg = load_config()
    daily = pd.read_csv("data/derived/daily/analysis_daily.csv", parse_dates=["date"])
    window_days = int(cfg["spe"]["window_days"])
    date_index = pd.DatetimeIndex(daily["date"])
    rng = np.random.default_rng(20250307)

    summary_rows: list[dict[str, object]] = []
    output_paths: dict[str, object] = {}

    for source_name, path in EVENT_SOURCES.items():
        source_path = Path(path)
        if not source_path.exists():
            logger.warning("Skipping %s because %s is missing", source_name, path)
            continue
        events = load_event_dates(path)
        if not events:
            continue

        observed = build_event_window(daily, events, METRICS, window_days)
        observed_path = write_dataframe(observed, f"data/derived/spe/{source_name}_strict_observed")
        output_paths[f"{source_name}_observed"] = observed_path

        perm_rows: list[dict[str, object]] = []
        max_stats: dict[str, list[float]] = {metric: [] for metric in METRICS}
        for _ in range(int(cfg["spe"]["strict_permutations"])):
            fake_events = season_matched_random_dates(events, date_index, int(cfg["spe"]["season_match_window_days"]), rng)
            fake = build_event_window(daily, fake_events, METRICS, window_days)
            for metric in METRICS:
                aligned = fake.set_index("lag").reindex(range(-window_days, window_days + 1))[metric]
                max_stats[metric].append(float(np.nanmax(np.abs(aligned.values))))
            fake["iteration"] = len(max_stats[METRICS[0]])
            perm_rows.append(fake)

        perm_df = pd.concat(perm_rows, ignore_index=True)
        output_paths[f"{source_name}_permutations"] = write_dataframe(perm_df, f"data/derived/spe/{source_name}_strict_permutations")

        for metric in METRICS:
            observed_stat = float(observed[metric].abs().max())
            summary_rows.append(
                {
                    "source": source_name,
                    "metric": metric,
                    "event_count": len(events),
                    "observed_max_abs_daily_effect": observed_stat,
                    "empirical_p_max": empirical_pvalue(observed_stat, max_stats[metric]),
                    "lag_of_max_abs_effect": int(observed.loc[observed[metric].abs().idxmax(), "lag"]),
                }
            )

        fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharex=True)
        for ax, metric in zip(axes.flat, METRICS, strict=False):
            ax.plot(observed["lag"], observed[metric], color="black", linewidth=1.8)
            ax.axvline(0, color="0.6", linestyle="--", linewidth=1)
            ax.set_title(f"{source_name}: {metric}")
            ax.set_xlabel("Lag (days)")
            ax.set_ylabel("Daily mean")
        fig.tight_layout()
        output_paths[f"{source_name}_figure"] = save_figure(fig, f"data/derived/figures/{source_name}_strict_daily_rates")

    summary = pd.DataFrame(summary_rows)
    output_paths["summary"] = write_dataframe(summary, "data/derived/spe/strict_event_study_summary")
    write_script_manifest(
        "19_run_stricter_event_study.py",
        ["data/derived/daily/analysis_daily.csv", *EVENT_SOURCES.values()],
        output_paths,
        {"rows": int(len(summary))},
        assumptions=["Strict permutations preserve year distribution and approximately match day-of-year."],
        ok=not summary.empty,
    )
    logger.info("Finished stricter event study for %d source/metric combinations", len(summary))
    return 0 if not summary.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
