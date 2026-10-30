from __future__ import annotations

from pathlib import Path
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


METRICS = [
    "all_tornadoes",
    "strong_tornadoes",
    "daily_injuries",
    "daily_fatalities",
]


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPE_DIR = PROJECT_ROOT / "data" / "derived" / "spe"
FIG_DIR = PROJECT_ROOT / "data" / "derived" / "figures"
TABLE_DIR = PROJECT_ROOT / "data" / "derived" / "tables"

OBSERVED_PATH = SPE_DIR / "paper_author_hcs_observed.csv"
NULL_PATH = SPE_DIR / "paper_author_hcs_null_summary.csv"


def _find_null_columns(null_df: pd.DataFrame, metric: str) -> tuple[str, str, str]:
    """
    Return the mean / q025 / q975 column names for a given cumulative metric.
    Handles a few possible naming variations.
    """
    candidates = [
        (
            f"{metric}_cumulative_mean",
            f"{metric}_cumulative_q025",
            f"{metric}_cumulative_q975",
        ),
        (
            f"{metric}_cumulative_mean",
            f"{metric}_cumulative_<lambda_0>",
            f"{metric}_cumulative_<lambda_1>",
        ),
    ]

    for mean_col, low_col, high_col in candidates:
        if mean_col in null_df.columns and low_col in null_df.columns and high_col in null_df.columns:
            return mean_col, low_col, high_col

    raise KeyError(
        f"Could not find null summary columns for {metric}. "
        f"Available columns: {list(null_df.columns)}"
    )


def _safe_mkdirs() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not OBSERVED_PATH.exists():
        raise FileNotFoundError(f"Missing observed file: {OBSERVED_PATH}")
    if not NULL_PATH.exists():
        raise FileNotFoundError(f"Missing null summary file: {NULL_PATH}")

    observed = pd.read_csv(OBSERVED_PATH)
    null_df = pd.read_csv(NULL_PATH)

    if "lag" not in observed.columns or "lag" not in null_df.columns:
        raise ValueError("Both observed and null summary files must contain a 'lag' column.")
    for frame in (observed, null_df):
        if "statistic" not in frame or not frame["statistic"].eq("across_event_total").all():
            raise ValueError("Stale or incompatible paper-style statistics; rerun script 16 with --run-null.")
    if "event_count" not in observed or "event_count" not in null_df:
        raise ValueError("Missing paper-style event counts; rerun script 16 with --run-null.")
    if observed["event_count"].nunique() != 1 or not null_df["event_count"].eq(observed["event_count"].iloc[0]).all():
        raise ValueError("Observed and null paper-style event populations differ; rerun script 16 with --run-null.")

    observed = observed.sort_values("lag").reset_index(drop=True)
    null_df = null_df.sort_values("lag").reset_index(drop=True)

    return observed, null_df


def build_lag0_summary(observed: pd.DataFrame, null_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a compact lag-0 diagnostic table.

    Since the null summary only contains mean/q025/q975 rather than the full
    permutation distribution, the z-like score here is only approximate:
        sigma ~= (q975 - q025) / 3.92
    """
    rows = []

    obs0 = observed.loc[observed["lag"] == 0]
    null0 = null_df.loc[null_df["lag"] == 0]

    if obs0.empty or null0.empty:
        raise ValueError("Lag 0 not found in observed or null summary.")

    obs0 = obs0.iloc[0]
    null0 = null0.iloc[0]

    for metric in METRICS:
        mean_col, low_col, high_col = _find_null_columns(null_df, metric)
        obs_col = f"{metric}_cumulative"

        obs_val = float(obs0[obs_col])
        null_mean = float(null0[mean_col])
        q025 = float(null0[low_col])
        q975 = float(null0[high_col])

        approx_sigma = (q975 - q025) / 3.92 if np.isfinite(q975 - q025) and (q975 > q025) else np.nan
        approx_z = (obs_val - null_mean) / approx_sigma if approx_sigma and approx_sigma > 0 else np.nan
        outside_95 = bool(obs_val < q025 or obs_val > q975)

        rows.append(
            {
                "metric": metric,
                "observed_cumulative_lag0": obs_val,
                "null_mean_cumulative_lag0": null_mean,
                "null_q025_cumulative_lag0": q025,
                "null_q975_cumulative_lag0": q975,
                "approx_sigma_from_quantiles": approx_sigma,
                "approx_zscore_lag0": approx_z,
                "outside_null_95_band_at_lag0": outside_95,
            }
        )

    return pd.DataFrame(rows)


def make_cumulative_overlay_figure(observed: pd.DataFrame, null_df: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)

    for ax, metric in zip(axes.flat, METRICS, strict=False):
        mean_col, low_col, high_col = _find_null_columns(null_df, metric)

        ax.fill_between(
            null_df["lag"],
            null_df[low_col],
            null_df[high_col],
            alpha=0.25,
            label="Null 95% band",
        )
        ax.plot(
            null_df["lag"],
            null_df[mean_col],
            linewidth=1.5,
            label="Null mean",
        )
        ax.plot(
            observed["lag"],
            observed[f"{metric}_cumulative"],
            color="black",
            linewidth=2.0,
            label="Observed",
        )
        ax.axvline(0, color="0.5", linestyle="--", linewidth=1)
        ax.set_title(metric.replace("_", " "))
        ax.set_xlabel("Days from HCS crossing")
        ax.set_ylabel("Total across events at each epoch day")

    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    fig.suptitle("Author HCS replication: across-event totals vs null envelope", y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    out_path = FIG_DIR / "author_hcs_cumulative_vs_null.png"
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_daily_anomaly_figure(observed: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)

    for ax, metric in zip(axes.flat, METRICS, strict=False):
        baseline = observed[metric].mean()
        anomaly = observed[metric] - baseline

        ax.plot(
            observed["lag"],
            anomaly,
            color="black",
            linewidth=1.8,
        )
        ax.axhline(0, color="0.6", linestyle=":", linewidth=1)
        ax.axvline(0, color="0.5", linestyle="--", linewidth=1)

        lag0_val = float(anomaly.loc[observed["lag"] == 0].iloc[0])
        ax.scatter([0], [lag0_val], s=35, zorder=3)

        ax.set_title(f"{metric.replace('_', ' ')} anomaly")
        ax.set_xlabel("Days from HCS crossing")
        ax.set_ylabel("Observed daily mean - overall lag mean")

    fig.suptitle("Author HCS replication: daily-rate anomalies", y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    out_path = FIG_DIR / "author_hcs_daily_anomalies.png"
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_daily_rate_raw_figure(observed: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)

    for ax, metric in zip(axes.flat, METRICS, strict=False):
        ax.plot(
            observed["lag"],
            observed[metric],
            color="black",
            linewidth=1.8,
        )
        ax.axvline(0, color="0.5", linestyle="--", linewidth=1)
        ax.set_title(metric.replace("_", " "))
        ax.set_xlabel("Days from HCS crossing")
        ax.set_ylabel("Observed daily mean")

    fig.suptitle("Author HCS replication: observed daily rates", y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    out_path = FIG_DIR / "author_hcs_daily_rates_check.png"
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main() -> int:
    _safe_mkdirs()

    observed, null_df = load_inputs()

    lag0_summary = build_lag0_summary(observed, null_df)
    lag0_summary_path = TABLE_DIR / "author_hcs_lag0_null_check.csv"
    lag0_summary.to_csv(lag0_summary_path, index=False)

    cumulative_fig = make_cumulative_overlay_figure(observed, null_df)
    anomaly_fig = make_daily_anomaly_figure(observed)
    raw_daily_fig = make_daily_rate_raw_figure(observed)

    print("\n=== Author HCS replication check ===")
    print(f"Observed file: {OBSERVED_PATH}")
    print(f"Null summary file: {NULL_PATH}")
    print(f"Cumulative overlay figure: {cumulative_fig}")
    print(f"Daily anomaly figure: {anomaly_fig}")
    print(f"Daily raw-rate figure: {raw_daily_fig}")
    print(f"Lag-0 summary table: {lag0_summary_path}")
    print("\nLag-0 diagnostic table:")
    print(lag0_summary.to_string(index=False))

    print("\nInterpretation guide:")
    print("- A lag-0 total inside the pointwise null band does not establish equivalence or exclude an effect.")
    print("- Across-event totals and means have identical shapes with a fixed event population.")
    print("- Approx z-scores here are only rough because they are derived from quantiles, not raw null draws.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
