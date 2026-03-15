from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _utils import FIGURE_DIR, ROOT, save_figure, write_dataframe, write_script_manifest
from common import make_logger


METRICS = ["all_tornadoes", "strong_tornadoes", "daily_injuries", "daily_fatalities"]
WINDOW_DAYS = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Event study using reconstructed HCS crossings.")
    parser.add_argument("--iterations", type=int, default=500, help="Fast null iterations for all_tornadoes daily mean.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for fast null.")
    return parser.parse_args()


def extract_metric_windows(series: np.ndarray, event_idx: np.ndarray, lags: np.ndarray) -> np.ndarray:
    return series[event_idx[:, None] + lags[None, :]]


def build_observed_table(df: pd.DataFrame, event_idx: np.ndarray, lags: np.ndarray) -> pd.DataFrame:
    out = pd.DataFrame({"lag": lags})
    for metric in METRICS:
        values = df[metric].to_numpy(dtype=float)
        window = extract_metric_windows(values, event_idx, lags)
        mean_series = window.mean(axis=0)
        out[f"{metric}_daily_mean"] = mean_series
        out[f"{metric}_cumulative"] = np.cumsum(mean_series)
        out[f"{metric}_anomaly"] = mean_series - mean_series.mean()
    out["event_count"] = len(event_idx)
    return out


def plot_family(observed: pd.DataFrame, suffix: str, title_prefix: str, value_suffix: str, ylabel: str, rel_stem: str) -> dict[str, str]:
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharex=True)
    for ax, metric in zip(axes.flat, METRICS, strict=False):
        ax.plot(observed["lag"], observed[f"{metric}_{value_suffix}"], color="black", linewidth=1.8)
        ax.axvline(0, color="0.6", linestyle="--", linewidth=1)
        ax.set_title(f"{title_prefix}: {metric.replace('_', ' ')}")
        ax.set_xlabel("Days from reconstructed HCS")
        ax.set_ylabel(ylabel)
    fig.tight_layout()
    return save_figure(fig, rel_stem)


def main() -> int:
    args = parse_args()
    logger = make_logger("27_event_study_reconstructed_hcs")

    catalog_path = ROOT / "data" / "derived" / "catalogs" / "hcs_from_omni.csv"
    analysis_path = ROOT / "data" / "derived" / "daily" / "analysis_daily.csv"
    catalog = pd.read_csv(catalog_path, parse_dates=["date"])
    daily = pd.read_csv(analysis_path, parse_dates=["date"])

    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    catalog["date"] = pd.to_datetime(catalog["date"], errors="coerce").dt.normalize()
    catalog = catalog.dropna(subset=["date"]).drop_duplicates(subset=["date"]).sort_values("date")

    lags = np.arange(-WINDOW_DAYS, WINDOW_DAYS + 1)
    date_days = pd.DatetimeIndex(daily["date"]).to_numpy(dtype="datetime64[ns]")
    event_days = catalog["date"].to_numpy(dtype="datetime64[ns]")
    event_idx = np.searchsorted(date_days, event_days)
    in_bounds = (event_idx >= 0) & (event_idx < len(date_days))
    valid = np.zeros(len(event_idx), dtype=bool)
    valid[in_bounds] = date_days[event_idx[in_bounds]] == event_days[in_bounds]
    event_idx = event_idx[valid]
    event_idx = event_idx[(event_idx >= WINDOW_DAYS) & (event_idx < len(date_days) - WINDOW_DAYS)]

    if len(event_idx) == 0:
        write_script_manifest(
            "27_event_study_reconstructed_hcs.py",
            [catalog_path, analysis_path],
            [],
            {"error": "No reconstructed HCS events remain after date matching and edge filtering."},
            ok=False,
        )
        return 1

    observed = build_observed_table(daily, event_idx, lags)
    observed_outputs = write_dataframe(observed, "data/derived/spe/reconstructed_hcs_observed")

    outputs: dict[str, object] = {
        "observed": observed_outputs,
        "daily_rate_figure": plot_family(observed, "daily_rates", "Reconstructed HCS daily rates", "daily_mean", "Daily mean", "data/derived/figures/reconstructed_hcs_daily_rates"),
        "cumulative_figure": plot_family(observed, "cumulative", "Reconstructed HCS cumulative", "cumulative", "Cumulative mean", "data/derived/figures/reconstructed_hcs_cumulative"),
        "anomaly_figure": plot_family(observed, "anomaly", "Reconstructed HCS anomalies", "anomaly", "Lag anomaly", "data/derived/figures/reconstructed_hcs_anomalies"),
    }

    tornado = daily["all_tornadoes"].to_numpy(dtype=float)
    rng = np.random.default_rng(args.seed)
    null_means = np.empty((args.iterations, len(lags)), dtype=float)
    low_idx = WINDOW_DAYS
    high_idx = len(tornado) - WINDOW_DAYS
    for idx in range(args.iterations):
        rand_idx = rng.integers(low_idx, high_idx, size=len(event_idx))
        sim = extract_metric_windows(tornado, rand_idx, lags)
        null_means[idx, :] = sim.mean(axis=0)
        if (idx + 1) % 50 == 0 or (idx + 1) == args.iterations:
            logger.info("Fast null progress: %d/%d iterations", idx + 1, args.iterations)

    obs_mean = observed["all_tornadoes_daily_mean"].to_numpy(dtype=float)
    null_mean = null_means.mean(axis=0)
    low = np.percentile(null_means, 2.5, axis=0)
    high = np.percentile(null_means, 97.5, axis=0)
    null_df = pd.DataFrame(
        {
            "lag": lags,
            "observed_daily_mean": obs_mean,
            "null_mean": null_mean,
            "null_q025": low,
            "null_q975": high,
            "anomaly_vs_null_mean": obs_mean - null_mean,
            "outside_95_band": (obs_mean < low) | (obs_mean > high),
        }
    )
    outputs["fast_null"] = write_dataframe(null_df, "data/derived/spe/reconstructed_hcs_fast_null_all_tornadoes")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(null_df["lag"], null_df["observed_daily_mean"], color="black", linewidth=1.8, label="Observed")
    ax.plot(null_df["lag"], null_df["null_mean"], color="0.35", linewidth=1.4, label="Null mean")
    ax.fill_between(null_df["lag"], null_df["null_q025"], null_df["null_q975"], color="0.8", alpha=0.7, label="95% null band")
    ax.axvline(0, color="0.6", linestyle="--", linewidth=1)
    ax.set_title("Reconstructed HCS fast null: all tornadoes")
    ax.set_xlabel("Days from reconstructed HCS")
    ax.set_ylabel("Daily mean tornado count")
    ax.legend(frameon=False)
    fig.tight_layout()
    outputs["fast_null_figure"] = save_figure(fig, "data/derived/figures/reconstructed_hcs_fast_null_all_tornadoes")

    lag0 = null_df.loc[null_df["lag"] == 0].iloc[0]
    diagnostics = pd.DataFrame(
        [
            {
                "crossings_used": int(len(event_idx)),
                "lag0_observed_daily_mean": float(lag0["observed_daily_mean"]),
                "lag0_null_mean": float(lag0["null_mean"]),
                "lag0_null_q025": float(lag0["null_q025"]),
                "lag0_null_q975": float(lag0["null_q975"]),
                "lag0_outside_95_band": bool(lag0["outside_95_band"]),
            }
        ]
    )
    diagnostics_path = ROOT / "data" / "derived" / "tables" / "reconstructed_hcs_event_study_diagnostics.csv"
    diagnostics.to_csv(diagnostics_path, index=False)
    outputs["diagnostics"] = str(diagnostics_path.relative_to(ROOT))

    metrics = {
        "crossings_used": int(len(event_idx)),
        "window_days": WINDOW_DAYS,
        "null_iterations": int(args.iterations),
        "lag0_observed_daily_mean": float(lag0["observed_daily_mean"]),
        "lag0_null_mean": float(lag0["null_mean"]),
        "lag0_null_q025": float(lag0["null_q025"]),
        "lag0_null_q975": float(lag0["null_q975"]),
        "lag0_outside_95_band": bool(lag0["outside_95_band"]),
    }
    write_script_manifest(
        "27_event_study_reconstructed_hcs.py",
        [catalog_path, analysis_path],
        outputs,
        metrics,
        assumptions=["Observed composite uses the reconstructed daily HCS crossings with a symmetric +/-30 day window."],
    )

    print(f"Reconstructed HCS crossings used: {len(event_idx)}")
    print(f"Lag 0 observed daily mean (all_tornadoes): {lag0['observed_daily_mean']:.6f}")
    print(f"Lag 0 null mean (all_tornadoes): {lag0['null_mean']:.6f}")
    print(f"Lag 0 null 95% band: [{lag0['null_q025']:.6f}, {lag0['null_q975']:.6f}]")
    print(f"Lag 0 outside 95% band: {bool(lag0['outside_95_band'])}")
    logger.info("Reconstructed HCS event study completed with %d crossings", len(event_idx))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())