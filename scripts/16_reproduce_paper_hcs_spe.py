from __future__ import annotations

import argparse
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _utils import add_cumulative_columns, build_event_window, complete_window_dates, load_config, make_logger, random_dates_like, save_figure, write_dataframe, write_script_manifest


METRICS = ["all_tornadoes", "strong_tornadoes", "daily_injuries", "daily_fatalities"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reproduce paper-style author-HCS SPE with optional Monte Carlo null.")
    parser.add_argument(
        "--run-null",
        action="store_true",
        help="Run Monte Carlo null analysis. Default is observed-only for fast debugging.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=20,
        help="Monte Carlo iterations for null analysis (used only with --run-null).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for Monte Carlo null analysis.",
    )
    return parser.parse_args()


def _build_null_summary(
    daily: pd.DataFrame,
    event_dates: list[pd.Timestamp],
    window_days: int,
    iterations: int,
    rng: np.random.Generator,
    logger,
) -> pd.DataFrame:
    lags = np.arange(-window_days, window_days + 1)
    lag_index = list(lags)
    date_index = pd.DatetimeIndex(daily["date"])[window_days:-window_days]

    samples: dict[str, np.ndarray] = {
        metric: np.full((iterations, len(lags)), np.nan, dtype=float) for metric in METRICS
    }

    for idx in range(iterations):
        random_events = random_dates_like(event_dates, date_index, rng)
        random_window = build_event_window(daily, random_events, METRICS, window_days)
        aligned = random_window.set_index("lag").reindex(lag_index)
        for metric in METRICS:
            samples[metric][idx, :] = (aligned[metric] * aligned["event_count"]).to_numpy()

        if (idx + 1) % 10 == 0 or (idx + 1) == iterations:
            logger.info("Monte Carlo progress: %d/%d iterations", idx + 1, iterations)

    out = pd.DataFrame({"lag": lags, "statistic": "across_event_total", "event_count": len(event_dates)})
    for metric in METRICS:
        arr = samples[metric]
        out[f"{metric}_cumulative_mean"] = np.nanmean(arr, axis=0)
        out[f"{metric}_cumulative_q025"] = np.nanquantile(arr, 0.025, axis=0)
        out[f"{metric}_cumulative_q975"] = np.nanquantile(arr, 0.975, axis=0)
    return out


def main() -> int:
    args = parse_args()
    t0 = time.perf_counter()
    logger = make_logger("16_reproduce_paper_hcs_spe")
    cfg = load_config()
    daily = pd.read_csv("data/derived/daily/analysis_daily.csv", parse_dates=["date"])
    author_path = "data/derived/catalogs/author_hcs_catalog.csv"

    try:
        author = pd.read_csv(author_path, parse_dates=["datetime_utc"])
    except FileNotFoundError:
        write_script_manifest(
            "16_reproduce_paper_hcs_spe.py",
            ["data/derived/daily/analysis_daily.csv"],
            [],
            {"error": "author_hcs_catalog.csv not found; replication branch cannot run"},
            ok=False,
        )
        return 1

    author = author[(author["year"] >= 1963) & (author["year"] <= 2023)].copy()
    event_dates = pd.to_datetime(author["datetime_utc"], utc=True, errors="coerce").dropna().dt.tz_convert(None).dt.normalize().tolist()
    window_days = int(cfg["spe"]["window_days"])
    event_dates = complete_window_dates(event_dates, pd.DatetimeIndex(daily["date"]), window_days)

    # Keep the observed author-HCS composite as the first stage and persist immediately.
    observed = build_event_window(daily, event_dates, METRICS, window_days)
    observed = add_cumulative_columns(observed, METRICS)
    observed["statistic"] = "across_event_total"

    outputs: dict[str, object] = {
        "observed": write_dataframe(observed, "data/derived/spe/paper_author_hcs_observed"),
    }

    fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharex=True)
    for ax, metric in zip(axes.flat, METRICS, strict=False):
        ax.plot(observed["lag"], observed[f"{metric}_cumulative"], color="black", linewidth=1.8, label="Observed")
        ax.set_title(metric.replace("_", " "))
        ax.axvline(0, color="0.6", linestyle="--", linewidth=1)
        ax.set_xlabel("Days from HCS crossing")
        ax.set_ylabel("Total across events at each epoch day")
    fig.tight_layout()
    outputs["paper_style_figure"] = save_figure(fig, "data/derived/figures/paper_style_author_hcs_cumulative")

    fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharex=True)
    for ax, metric in zip(axes.flat, METRICS, strict=False):
        ax.plot(observed["lag"], observed[metric], color="black", linewidth=1.8, label="Observed daily mean")
        ax.axvline(0, color="0.6", linestyle="--", linewidth=1)
        ax.set_title(metric.replace("_", " "))
        ax.set_xlabel("Days from HCS crossing")
        ax.set_ylabel("Daily mean")
    fig.tight_layout()
    outputs["daily_rate_figure"] = save_figure(fig, "data/derived/figures/paper_style_author_hcs_daily_rates")

    iterations = int(args.iterations)
    ran_null = bool(args.run_null)
    if ran_null:
        rng = np.random.default_rng(args.seed)
        null_summary = _build_null_summary(daily, event_dates, window_days, iterations, rng, logger)
        outputs["null_summary"] = write_dataframe(null_summary, "data/derived/spe/paper_author_hcs_null_summary")
    else:
        logger.info("Observed-only mode: skipping Monte Carlo null analysis")

    metrics = {
        "event_count": int(len(event_dates)),
        "window_days": window_days,
        "run_null": ran_null,
        "monte_carlo_iterations": iterations if ran_null else 0,
        "runtime_seconds": round(time.perf_counter() - t0, 3),
    }
    write_script_manifest(
        "16_reproduce_paper_hcs_spe.py",
        ["data/derived/daily/analysis_daily.csv", author_path],
        outputs,
        metrics,
        assumptions=["Cumulative counts mean totals across events at each epoch day, not running sums over lags. Unique complete-window event dates are used; exact source-data replication is not claimed."],
    )
    logger.info(
        "Built paper-style author-HCS SPE with %d events in %.3fs (run_null=%s)",
        len(event_dates),
        metrics["runtime_seconds"],
        ran_null,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
