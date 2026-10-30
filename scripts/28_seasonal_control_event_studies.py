from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _utils import ROOT, null_tail_probabilities, write_script_manifest
from common import make_logger


METRICS = ["all_tornadoes", "strong_tornadoes", "daily_injuries", "daily_fatalities"]
WINDOW_DAYS = 30
SEASONS = {
    "full_year": set(range(1, 13)),
    "mar_jun": {3, 4, 5, 6},
    "apr_jun": {4, 5, 6},
}
BRANCHES = {
    "author_hcs": ROOT / "data" / "derived" / "catalogs" / "author_hcs_catalog.csv",
    "reconstructed_hcs": ROOT / "data" / "derived" / "catalogs" / "hcs_from_omni.csv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seasonal-control event studies for author and reconstructed HCS catalogs.")
    parser.add_argument("--iterations", type=int, default=500, help="Null iterations for all_tornadoes fast null.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for null draws.")
    return parser.parse_args()


def load_branch_events(path: Path, branch: str) -> pd.Series:
    df = pd.read_csv(path)
    if branch == "author_hcs":
        dt = pd.to_datetime(df.get("datetime_utc"), utc=True, errors="coerce").dt.tz_convert(None).dt.normalize()
        years = pd.to_numeric(df.get("year"), errors="coerce")
        mask = (years >= 1963) & (years <= 2023)
        return dt[mask].dropna().drop_duplicates().sort_values().reset_index(drop=True)

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


def build_observed(daily: pd.DataFrame, event_idx: np.ndarray, lags: np.ndarray) -> pd.DataFrame:
    out = pd.DataFrame({"lag": lags})
    for metric in METRICS:
        series = daily[metric].to_numpy(dtype=float)
        windows = series[event_idx[:, None] + lags[None, :]]
        mean_series = windows.mean(axis=0)
        out[f"{metric}_daily_mean"] = mean_series
        out[f"{metric}_anomaly"] = mean_series - mean_series.mean()
    out["event_count"] = int(len(event_idx))
    return out


def run_fast_null(
    all_tornadoes: np.ndarray,
    event_count: int,
    random_pool_idx: np.ndarray,
    lags: np.ndarray,
    iterations: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    null_means = np.empty((iterations, len(lags)), dtype=float)
    replace = event_count > len(random_pool_idx)
    for i in range(iterations):
        picked = rng.choice(random_pool_idx, size=event_count, replace=replace)
        sim = all_tornadoes[picked[:, None] + lags[None, :]]
        null_means[i, :] = sim.mean(axis=0)
    return null_means.mean(axis=0), np.percentile(null_means, 2.5, axis=0), np.percentile(null_means, 97.5, axis=0), null_means


def plot_metrics(observed: pd.DataFrame, value_suffix: str, title_prefix: str, out_path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharex=True)
    for ax, metric in zip(axes.flat, METRICS, strict=False):
        ax.plot(observed["lag"], observed[f"{metric}_{value_suffix}"], color="black", linewidth=1.8)
        ax.axvline(0, color="0.6", linestyle="--", linewidth=1)
        ax.set_title(f"{title_prefix}: {metric.replace('_', ' ')}")
        ax.set_xlabel("Days from crossing")
        ax.set_ylabel("Daily mean" if value_suffix == "daily_mean" else "Anomaly")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_fast_null(lags: np.ndarray, observed_all: np.ndarray, null_mean: np.ndarray, low: np.ndarray, high: np.ndarray, title: str, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(lags, observed_all, color="black", linewidth=1.8, label="Observed")
    ax.plot(lags, null_mean, color="0.35", linewidth=1.4, label="Null mean")
    ax.fill_between(lags, low, high, color="0.8", alpha=0.7, label="95% null band")
    ax.axvline(0, color="0.6", linestyle="--", linewidth=1)
    ax.set_title(title)
    ax.set_xlabel("Days from crossing")
    ax.set_ylabel("Daily mean all tornadoes")
    ax.legend(frameon=False)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    logger = make_logger("28_seasonal_control_event_studies")

    analysis_path = ROOT / "data" / "derived" / "daily" / "analysis_daily.csv"
    daily = pd.read_csv(analysis_path, parse_dates=["date"])
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    daily = daily[(daily["date"].dt.year >= 1963) & (daily["date"].dt.year <= 2023)].copy()

    lags = np.arange(-WINDOW_DAYS, WINDOW_DAYS + 1)
    date_days = pd.DatetimeIndex(daily["date"]).to_numpy(dtype="datetime64[ns]")
    all_tornadoes = daily["all_tornadoes"].to_numpy(dtype=float)

    summary_rows: list[dict[str, object]] = []
    report_lines = ["# Seasonal Control Summary", ""]

    rng = np.random.default_rng(args.seed)

    for branch, event_path in BRANCHES.items():
        if not event_path.exists():
            logger.warning("Skipping %s: missing %s", branch, event_path)
            continue
        events = load_branch_events(event_path, branch)
        event_days = events.to_numpy(dtype="datetime64[ns]")
        event_idx_all = match_event_indices(date_days, event_days)

        for season_name, months in SEASONS.items():
            season_mask = daily["date"].dt.month.isin(months).to_numpy()
            event_idx = event_idx_all[season_mask[event_idx_all]]
            if len(event_idx) == 0:
                summary_rows.append(
                    {
                        "branch": branch,
                        "season": season_name,
                        "event_count_used": 0,
                        "lag0_observed_all_tornadoes": np.nan,
                        "lag0_null_mean_all_tornadoes": np.nan,
                        "lag0_null_q025_all_tornadoes": np.nan,
                        "lag0_null_q975_all_tornadoes": np.nan,
                        "lag0_outside_band_all_tornadoes": False,
                        "notes": "No events after seasonal and edge filtering.",
                    }
                )
                continue

            observed = build_observed(daily, event_idx, lags)

            stem = f"{branch}_{season_name}"
            observed_out = ROOT / "data" / "derived" / "spe" / f"{stem}_observed.csv"
            observed_out.parent.mkdir(parents=True, exist_ok=True)
            observed.to_csv(observed_out, index=False)

            random_pool_idx = np.where(season_mask)[0]
            random_pool_idx = random_pool_idx[(random_pool_idx >= WINDOW_DAYS) & (random_pool_idx < len(date_days) - WINDOW_DAYS)]
            null_mean, low, high, null_draws = run_fast_null(all_tornadoes, len(event_idx), random_pool_idx, lags, args.iterations, rng)

            null_df = pd.DataFrame(
                {
                    "lag": lags,
                    "observed_daily_mean": observed["all_tornadoes_daily_mean"].to_numpy(dtype=float),
                    "null_mean": null_mean,
                    "null_q025": low,
                    "null_q975": high,
                    "anomaly_vs_null_mean": observed["all_tornadoes_daily_mean"].to_numpy(dtype=float) - null_mean,
                    "outside_95_band": (observed["all_tornadoes_daily_mean"].to_numpy(dtype=float) < low)
                    | (observed["all_tornadoes_daily_mean"].to_numpy(dtype=float) > high),
                }
            )
            null_df = null_df.assign(
                **null_tail_probabilities(observed["all_tornadoes_daily_mean"].to_numpy(), null_draws),
                event_count=len(event_idx),
            )
            null_out = ROOT / "data" / "derived" / "spe" / f"{stem}_fast_null_all_tornadoes.csv"
            null_df.to_csv(null_out, index=False)

            plot_metrics(
                observed,
                value_suffix="daily_mean",
                title_prefix=f"{branch} {season_name} daily rates",
                out_path=ROOT / "data" / "derived" / "figures" / f"{stem}_daily_rates.png",
            )
            plot_metrics(
                observed,
                value_suffix="anomaly",
                title_prefix=f"{branch} {season_name} anomalies",
                out_path=ROOT / "data" / "derived" / "figures" / f"{stem}_anomalies.png",
            )
            plot_fast_null(
                lags,
                observed["all_tornadoes_daily_mean"].to_numpy(dtype=float),
                null_mean,
                low,
                high,
                title=f"{branch} {season_name} fast null (all tornadoes)",
                out_path=ROOT / "data" / "derived" / "figures" / f"{stem}_fast_null_all_tornadoes.png",
            )

            lag0 = null_df.loc[null_df["lag"] == 0].iloc[0]
            summary_rows.append(
                {
                    "branch": branch,
                    "season": season_name,
                    "event_count_used": int(len(event_idx)),
                    "lag0_observed_all_tornadoes": float(lag0["observed_daily_mean"]),
                    "lag0_null_mean_all_tornadoes": float(lag0["null_mean"]),
                    "lag0_null_q025_all_tornadoes": float(lag0["null_q025"]),
                    "lag0_null_q975_all_tornadoes": float(lag0["null_q975"]),
                    "lag0_outside_band_all_tornadoes": bool(lag0["outside_95_band"]),
                    "notes": f"iterations={args.iterations}; random dates drawn within same seasonal subset",
                }
            )
            logger.info("%s %s: events=%d lag0_outside=%s", branch, season_name, len(event_idx), bool(lag0["outside_95_band"]))

    summary_df = pd.DataFrame(summary_rows)
    summary_path = ROOT / "data" / "derived" / "tables" / "seasonal_control_summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(summary_path, index=False)

    lag0_hits = summary_df[summary_df["lag0_outside_band_all_tornadoes"] == True]  # noqa: E712
    report_lines.append(f"Total branch-season checks: {len(summary_df)}")
    report_lines.append(f"Lag-0 outside-band cases: {len(lag0_hits)}")
    report_lines.append("")
    if lag0_hits.empty:
        report_lines.append("No seasonal subset produced a lag-0 all-tornadoes value outside the 95% seasonal null band.")
        report_lines.append("Seasonal controls do not materially change the null conclusion.")
    else:
        report_lines.append("Lag-0 outside-band cases were found in these branch/season combinations:")
        for _, row in lag0_hits.iterrows():
            report_lines.append(f"- {row['branch']} / {row['season']}: lag0={row['lag0_observed_all_tornadoes']:.4f}, band=[{row['lag0_null_q025_all_tornadoes']:.4f}, {row['lag0_null_q975_all_tornadoes']:.4f}]")
        report_lines.append("Seasonal controls may change the null conclusion in at least one subset.")

    report_path = ROOT / "data" / "derived" / "reports" / "seasonal_control_summary.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    write_script_manifest(
        "28_seasonal_control_event_studies.py",
        [analysis_path, BRANCHES["author_hcs"], BRANCHES["reconstructed_hcs"]],
        {
            "summary_table": str(summary_path.relative_to(ROOT)),
            "summary_report": str(report_path.relative_to(ROOT)),
        },
        {
            "checks": int(len(summary_df)),
            "lag0_outside_count": int(len(lag0_hits)),
            "iterations": int(args.iterations),
            "window_days": WINDOW_DAYS,
        },
        assumptions=["Random null dates are season-restricted and keep event count equal to observed seasonal count."],
        ok=not summary_df.empty,
    )

    print(f"Saved seasonal summary: {summary_path}")
    print(f"Saved seasonal report: {report_path}")
    return 0 if not summary_df.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
