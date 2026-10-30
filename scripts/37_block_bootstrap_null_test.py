from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from _utils import null_tail_probabilities


ROOT = Path(__file__).resolve().parents[1]
DAILY_PATH = ROOT / "data" / "derived" / "daily" / "analysis_daily.csv"
AUTHOR_PATH = ROOT / "data" / "derived" / "catalogs" / "author_hcs_catalog.csv"
RECON_PATH = ROOT / "data" / "derived" / "catalogs" / "hcs_from_omni.csv"
RECONCILE_PATH = ROOT / "data" / "derived" / "tables" / "author_hcs_count_reconciliation.csv"

SPE_DIR = ROOT / "data" / "derived" / "spe"
TABLE_DIR = ROOT / "data" / "derived" / "tables"
FIG_DIR = ROOT / "data" / "derived" / "figures"
REPORT_DIR = ROOT / "data" / "derived" / "reports"

ANALYSIS_START = "1963-01-01"
ANALYSIS_END = "2023-12-31"
WINDOW_DAYS = 30
LAGS = np.arange(-WINDOW_DAYS, WINDOW_DAYS + 1)
BLOCK_LENGTHS = [7, 14]
ITERATIONS = 500
SEED = 42


def load_analysis_daily() -> pd.DataFrame:
    daily = pd.read_csv(DAILY_PATH, parse_dates=["date"])
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    daily = daily[(daily["date"] >= ANALYSIS_START) & (daily["date"] <= ANALYSIS_END)].copy()
    return daily


def load_author_event_dates() -> pd.Series:
    df = pd.read_csv(AUTHOR_PATH)
    dt = pd.to_datetime(df.get("datetime_utc"), utc=True, errors="coerce").dt.tz_convert(None).dt.normalize()
    years = pd.to_numeric(df.get("year"), errors="coerce")
    mask = (years >= 1963) & (years <= 2023)
    return dt[mask].dropna().drop_duplicates().sort_values().reset_index(drop=True)


def load_reconstructed_event_dates() -> pd.Series:
    df = pd.read_csv(RECON_PATH)
    dt = pd.to_datetime(df.get("date"), errors="coerce").dt.normalize()
    years = dt.dt.year
    mask = (years >= 1963) & (years <= 2023)
    return dt[mask].dropna().drop_duplicates().sort_values().reset_index(drop=True)


def match_event_indices(date_days: np.ndarray, event_days: np.ndarray) -> np.ndarray:
    idx = np.searchsorted(date_days, event_days)
    in_bounds = (idx >= 0) & (idx < len(date_days))
    valid = np.zeros(len(idx), dtype=bool)
    valid[in_bounds] = date_days[idx[in_bounds]] == event_days[in_bounds]
    idx = idx[valid]
    idx = idx[(idx >= WINDOW_DAYS) & (idx < len(date_days) - WINDOW_DAYS)]
    return np.unique(idx)


def compute_composite(series: np.ndarray, event_idx: np.ndarray) -> np.ndarray:
    return series[event_idx[:, None] + LAGS[None, :]].mean(axis=0)


def block_bootstrap_series(series: np.ndarray, block_length: int, rng: np.random.Generator) -> np.ndarray:
    n = len(series)
    max_start = n - block_length
    pieces = []
    total = 0
    while total < n:
        start = int(rng.integers(0, max_start + 1))
        block = series[start : start + block_length]
        pieces.append(block)
        total += len(block)
    out = np.concatenate(pieces)
    return out[:n]


def run_block_bootstrap(
    branch: str,
    block_length: int,
    series: np.ndarray,
    event_idx: np.ndarray,
    iterations: int,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, dict[str, object]]:
    observed = compute_composite(series, event_idx)
    null = np.empty((iterations, len(LAGS)), dtype=float)

    for i in range(iterations):
        surrogate = block_bootstrap_series(series, block_length, rng)
        null[i, :] = compute_composite(surrogate, event_idx)
        if (i + 1) % 50 == 0:
            print(f"{branch} block={block_length}: completed {i + 1}/{iterations}")

    null_mean = null.mean(axis=0)
    low = np.percentile(null, 2.5, axis=0)
    high = np.percentile(null, 97.5, axis=0)
    outside = (observed < low) | (observed > high)

    out = pd.DataFrame(
        {
            "branch": branch,
            "block_length_days": int(block_length),
            "lag": LAGS,
            "observed_daily_mean": observed,
            "null_mean": null_mean,
            "null_q025": low,
            "null_q975": high,
            "observed_anomaly_vs_null_mean": observed - null_mean,
            "outside_95_band": outside,
        }
    )

    out = out.assign(**null_tail_probabilities(observed, null), event_count=len(event_idx))
    lag0 = out.loc[out["lag"] == 0].iloc[0]
    summary = {
        "branch": branch,
        "block_length_days": int(block_length),
        "event_count_used": int(len(event_idx)),
        "iterations": int(iterations),
        "lag0_observed": float(lag0["observed_daily_mean"]),
        "lag0_null_mean": float(lag0["null_mean"]),
        "lag0_null_q025": float(lag0["null_q025"]),
        "lag0_null_q975": float(lag0["null_q975"]),
        "lag0_inside_band": bool(not lag0["outside_95_band"]),
        "outside_band_lag_count": int(out["outside_95_band"].sum()),
    }
    return out, summary


def plot_single(result_df: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.8, 5.1))
    ax.plot(result_df["lag"], result_df["observed_daily_mean"], color="black", linewidth=1.9, label="Observed daily mean")
    ax.plot(result_df["lag"], result_df["null_mean"], color="tab:blue", linewidth=1.6, label="Block-bootstrap null mean")
    ax.fill_between(result_df["lag"], result_df["null_q025"], result_df["null_q975"], color="0.85", alpha=0.9, label="95% null band")
    ax.axvline(0, color="0.5", linestyle="--", linewidth=1.1)
    ax.set_xlabel("Lag (days)")
    ax.set_ylabel("Daily all_tornadoes mean")
    b = int(result_df["block_length_days"].iloc[0])
    br = str(result_df["branch"].iloc[0])
    ax.set_title(f"{br} block-bootstrap null (block={b} days)")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_combined(results: dict[tuple[str, int], pd.DataFrame], out_path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9), sharex=True, sharey=True)
    panel_order = [
        ("author_hcs", 7),
        ("author_hcs", 14),
        ("reconstructed_hcs", 7),
        ("reconstructed_hcs", 14),
    ]

    for ax, key in zip(axes.flatten(), panel_order):
        df = results[key]
        ax.plot(df["lag"], df["observed_daily_mean"], color="black", linewidth=1.8, label="Observed")
        ax.plot(df["lag"], df["null_mean"], color="tab:blue", linewidth=1.4, label="Null mean")
        ax.fill_between(df["lag"], df["null_q025"], df["null_q975"], color="0.85", alpha=0.9, label="95% null band")
        ax.axvline(0, color="0.5", linestyle="--", linewidth=1)
        ax.set_title(f"{key[0]} | block={key[1]} days")
        ax.set_xlabel("Lag (days)")
        ax.set_ylabel("Daily all_tornadoes mean")

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def maybe_reconciled_author_count() -> int | None:
    if not RECONCILE_PATH.exists():
        return None
    df = pd.read_csv(RECONCILE_PATH)
    row = df[df["count_name"] == "author_hcs_event_count_used_primary"]
    if row.empty:
        return None
    return int(row.iloc[0]["value"])


def main() -> int:
    for p in [DAILY_PATH, AUTHOR_PATH, RECON_PATH]:
        if not p.exists():
            raise FileNotFoundError(f"Missing required input: {p}")

    daily = load_analysis_daily()
    date_days = pd.DatetimeIndex(daily["date"]).to_numpy(dtype="datetime64[ns]")
    series = daily["all_tornadoes"].to_numpy(dtype=float)

    author_days = load_author_event_dates().to_numpy(dtype="datetime64[ns]")
    recon_days = load_reconstructed_event_dates().to_numpy(dtype="datetime64[ns]")

    author_idx = match_event_indices(date_days, author_days)
    recon_idx = match_event_indices(date_days, recon_days)

    reconciled_author = maybe_reconciled_author_count()

    rng = np.random.default_rng(SEED)

    results: dict[tuple[str, int], pd.DataFrame] = {}
    summary_rows: list[dict[str, object]] = []

    branch_to_idx = {
        "author_hcs": author_idx,
        "reconstructed_hcs": recon_idx,
    }

    for branch, idx in branch_to_idx.items():
        for block in BLOCK_LENGTHS:
            result_df, summary = run_block_bootstrap(branch, block, series, idx, ITERATIONS, rng)

            expected_note = ""
            if branch == "author_hcs" and reconciled_author is not None:
                expected_note = f" reconciled_author_primary={reconciled_author}."
            summary["notes"] = (
                f"Block bootstrap preserves local clustering with contiguous blocks sampled with replacement.{expected_note}"
            )

            out_csv = SPE_DIR / f"block_bootstrap_{branch}_block{block}.csv"
            out_csv.parent.mkdir(parents=True, exist_ok=True)
            result_df.to_csv(out_csv, index=False)

            out_png = FIG_DIR / f"block_bootstrap_{branch}_block{block}.png"
            plot_single(result_df, out_png)

            results[(branch, block)] = result_df
            summary_rows.append(summary)

    combined_png = FIG_DIR / "block_bootstrap_combined_comparison.png"
    plot_combined(results, combined_png)

    summary_df = pd.DataFrame(
        summary_rows,
        columns=[
            "branch",
            "block_length_days",
            "event_count_used",
            "iterations",
            "lag0_observed",
            "lag0_null_mean",
            "lag0_null_q025",
            "lag0_null_q975",
            "lag0_inside_band",
            "outside_band_lag_count",
            "notes",
        ],
    )
    summary_csv = TABLE_DIR / "block_bootstrap_summary.csv"
    summary_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(summary_csv, index=False)

    lines = ["# Block Bootstrap Null Summary", ""]
    lines.append(f"Analysis period: {ANALYSIS_START} to {ANALYSIS_END}")
    lines.append(f"Lag window: +/-{WINDOW_DAYS} days")
    lines.append(f"Iterations per analysis: {ITERATIONS}")
    lines.append("")
    lines.append("## Lag-0 Results")
    for row in summary_df.itertuples(index=False):
        lines.append(
            f"- {row.branch}, block={row.block_length_days}: observed={row.lag0_observed:.6f}, "
            f"null_mean={row.lag0_null_mean:.6f}, 95%=[{row.lag0_null_q025:.6f}, {row.lag0_null_q975:.6f}], "
            f"inside_band={row.lag0_inside_band}, outside_band_lag_count={row.outside_band_lag_count}, "
            f"event_count={row.event_count_used}"
        )

    any_outside = bool((summary_df["lag0_inside_band"] == False).any())
    lines.append("")
    lines.append("## Interpretation")
    if any_outside:
        lines.append("At least one lag-0 estimate falls outside the block-bootstrap 95% null band.")
    else:
        lines.append("No lag-0 estimate falls outside the block-bootstrap 95% null band.")
    lines.append("This indicates whether preserving short-range clustering changes the null conclusion for lag 0.")

    summary_md = REPORT_DIR / "block_bootstrap_summary.md"
    summary_md.parent.mkdir(parents=True, exist_ok=True)
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Saved: {summary_csv}")
    print(f"Saved: {summary_md}")
    print(f"Saved: {combined_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
