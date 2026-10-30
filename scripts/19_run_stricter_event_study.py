from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

from _utils import complete_window_dates, empirical_pvalue, holm_adjust_pvalues, load_config, make_logger, save_figure, year_season_cluster_shift_sampler, write_dataframe, write_script_manifest


EVENT_SOURCES = {
    "author_hcs": "data/derived/catalogs/author_hcs_catalog.csv",
    "reconstructed_hcs": "data/derived/catalogs/hcs_from_omni.csv",
    "cir_proxy": "data/derived/catalogs/cir_proxy_catalog.csv",
    "hss_onset": "data/derived/catalogs/hss_onset_catalog.csv",
}
METRICS = ["all_tornadoes", "strong_tornadoes", "daily_injuries", "daily_fatalities"]


def load_event_dates(path: str) -> list[pd.Timestamp]:
    df = pd.read_csv(path)
    for candidate in ["datetime_utc", "analysis_time_utc", "date"]:
        if candidate in df.columns:
            series = pd.to_datetime(df[candidate], utc=True, errors="coerce").dt.tz_convert(None)
            return series.dropna().dt.normalize().tolist()
    return []


def build_event_window_fast(
    daily: pd.DataFrame,
    event_dates: list[pd.Timestamp],
    metrics: list[str],
    window_days: int,
) -> pd.DataFrame:
    dates = pd.DatetimeIndex(pd.to_datetime(daily["date"], errors="coerce")).normalize()
    events = pd.DatetimeIndex(complete_window_dates(event_dates, dates, window_days))
    if events.empty:
        raise ValueError("No complete event windows remain.")
    lags = np.arange(-window_days, window_days + 1)
    target_dates = events.to_numpy(dtype="datetime64[ns]")[:, None] + lags.astype("timedelta64[D]")
    positions = dates.get_indexer(target_dates.ravel()).reshape(target_dates.shape)
    metric_values = {metric: daily[metric].to_numpy(dtype=float) for metric in metrics}

    rows: list[dict[str, object]] = []
    for lag_index, lag in enumerate(lags):
        event_positions = positions[:, lag_index]
        matched = event_positions >= 0
        if not matched.any():
            continue
        row: dict[str, object] = {"lag": int(lag), "event_count": int(matched.sum())}
        for metric, values in metric_values.items():
            row[metric] = float(pd.Series(values[event_positions[matched]]).mean())
        rows.append(row)

    return pd.DataFrame(rows, columns=["lag", "event_count", *metrics])


def main() -> int:
    logger = make_logger("19_run_stricter_event_study")
    cfg = load_config()
    daily = pd.read_csv("data/derived/daily/analysis_daily.csv", parse_dates=["date"])
    window_days = int(cfg["spe"]["window_days"])
    date_index = pd.DatetimeIndex(daily["date"])
    eligible_dates = date_index[window_days:-window_days]
    rng = np.random.default_rng(20250307)

    summary_rows: list[dict[str, object]] = []
    output_paths: dict[str, object] = {}

    for source_name, path in EVENT_SOURCES.items():
        source_path = Path(path)
        if not source_path.exists():
            logger.warning("Skipping %s because %s is missing", source_name, path)
            continue
        events = complete_window_dates(load_event_dates(path), date_index, window_days)
        if not events:
            raise ValueError(f"No complete-window events for {source_name}.")

        observed = build_event_window_fast(daily, events, METRICS, window_days)
        observed_path = write_dataframe(observed, f"data/derived/spe/{source_name}_strict_observed")
        output_paths[f"{source_name}_observed"] = observed_path

        perm_rows: list[dict[str, object]] = []
        max_stats: dict[str, list[float]] = {metric: [] for metric in METRICS}
        fake_event_sampler = year_season_cluster_shift_sampler(
            events,
            eligible_dates,
            int(cfg["spe"]["season_match_window_days"]),
        )
        for _ in range(int(cfg["spe"]["strict_permutations"])):
            fake_events = fake_event_sampler(rng)
            fake = build_event_window_fast(daily, fake_events, METRICS, window_days)
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
                    "statistic": "maximum_raw_daily_mean",
                    "null_model": "within_year_cluster_shift_15d",
                    "iterations": int(cfg["spe"]["strict_permutations"]),
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
    summary["p_value_holm"] = holm_adjust_pvalues(summary["empirical_p_max"])
    output_paths["summary"] = write_dataframe(summary, "data/derived/spe/strict_event_study_summary")
    write_script_manifest(
        "19_run_stricter_event_study.py",
        ["data/derived/daily/analysis_daily.csv", *EVENT_SOURCES.values()],
        output_paths,
        {"rows": int(len(summary))},
        assumptions=["Unique complete-window dates; observed and null eligibility identical. Shared annual shifts preserve within-year event spacing and approximate season. Holm adjustment covers 16 source/outcome lag-scan tests."],
        ok=not summary.empty,
    )
    logger.info("Finished stricter event study for %d source/metric combinations", len(summary))
    return 0 if not summary.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
