from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.fft import irfft, rfft

from _utils import ROOT, null_tail_probabilities, write_script_manifest
from common import make_logger


WINDOW_DAYS = 30


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Phase-randomized null test for author-HCS all-tornadoes event study.")
	parser.add_argument("--iterations", type=int, default=200, help="Number of phase-randomized surrogates (default >=200).")
	parser.add_argument("--seed", type=int, default=42, help="RNG seed.")
	return parser.parse_args()


def load_author_event_dates(path: Path) -> pd.Series:
	df = pd.read_csv(path)
	dt = pd.to_datetime(df.get("datetime_utc"), utc=True, errors="coerce").dt.tz_convert(None).dt.normalize()
	years = pd.to_numeric(df.get("year"), errors="coerce")
	mask = (years >= 1963) & (years <= 2023)
	return dt[mask].dropna().drop_duplicates().sort_values().reset_index(drop=True)


def match_event_indices(date_days: np.ndarray, event_days: np.ndarray, window_days: int) -> np.ndarray:
	idx = np.searchsorted(date_days, event_days)
	in_bounds = (idx >= 0) & (idx < len(date_days))
	valid = np.zeros(len(idx), dtype=bool)
	valid[in_bounds] = date_days[idx[in_bounds]] == event_days[in_bounds]
	idx = idx[valid]
	idx = idx[(idx >= window_days) & (idx < len(date_days) - window_days)]
	return np.unique(idx)


def event_composite(series: np.ndarray, event_idx: np.ndarray, lags: np.ndarray) -> np.ndarray:
	return series[event_idx[:, None] + lags[None, :]].mean(axis=0)


def phase_randomized_surrogate(series: np.ndarray, rng: np.random.Generator) -> np.ndarray:
	n = len(series)
	mean_val = float(series.mean())
	centered = series - mean_val

	spec = rfft(centered)
	amp = np.abs(spec)

	phase = np.zeros_like(spec, dtype=float)
	if len(phase) > 2:
		phase[1:-1] = rng.uniform(0, 2 * np.pi, size=len(phase) - 2)
	if n % 2 == 0 and len(phase) > 1:
		phase[-1] = 0.0

	randomized = amp * np.exp(1j * phase)
	randomized[0] = spec[0]
	if n % 2 == 0 and len(randomized) > 1:
		randomized[-1] = spec[-1].real + 0j

	surrogate = irfft(randomized, n=n) + mean_val
	return surrogate.real


def main() -> int:
	args = parse_args()
	logger = make_logger("29_phase_randomized_null_test")

	analysis_path = ROOT / "data" / "derived" / "daily" / "analysis_daily.csv"
	author_path = ROOT / "data" / "derived" / "catalogs" / "author_hcs_catalog.csv"

	daily = pd.read_csv(analysis_path, parse_dates=["date"])
	daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
	daily = daily[(daily["date"].dt.year >= 1963) & (daily["date"].dt.year <= 2023)].copy()

	author_dates = load_author_event_dates(author_path)

	lags = np.arange(-WINDOW_DAYS, WINDOW_DAYS + 1)
	date_days = pd.DatetimeIndex(daily["date"]).to_numpy(dtype="datetime64[ns]")
	event_days = author_dates.to_numpy(dtype="datetime64[ns]")
	event_idx = match_event_indices(date_days, event_days, WINDOW_DAYS)

	if len(event_idx) == 0:
		write_script_manifest(
			"29_phase_randomized_null_test.py",
			[analysis_path, author_path],
			[],
			{"error": "No valid author-HCS events after date matching and edge filtering."},
			ok=False,
		)
		return 1

	observed_series = daily["all_tornadoes"].to_numpy(dtype=float)
	observed = event_composite(observed_series, event_idx, lags)

	rng = np.random.default_rng(args.seed)
	null = np.empty((args.iterations, len(lags)), dtype=float)
	for i in range(args.iterations):
		surrogate = phase_randomized_surrogate(observed_series, rng)
		null[i, :] = event_composite(surrogate, event_idx, lags)
		if (i + 1) % 25 == 0 or (i + 1) == args.iterations:
			logger.info("Phase-randomized progress: %d/%d", i + 1, args.iterations)

	null_mean = null.mean(axis=0)
	low = np.percentile(null, 2.5, axis=0)
	high = np.percentile(null, 97.5, axis=0)

	out_df = pd.DataFrame(
		{
			"lag": lags,
			"observed_daily_mean": observed,
			"null_mean": null_mean,
			"null_q025": low,
			"null_q975": high,
			"anomaly_vs_null_mean": observed - null_mean,
			"outside_95_band": (observed < low) | (observed > high),
		}
	)

	out_df = out_df.assign(**null_tail_probabilities(observed, null), event_count=len(event_idx))
	spe_path = ROOT / "data" / "derived" / "spe" / "phase_randomized_author_hcs_all_tornadoes.csv"
	spe_path.parent.mkdir(parents=True, exist_ok=True)
	out_df.to_csv(spe_path, index=False)

	fig_path = ROOT / "data" / "derived" / "figures" / "phase_randomized_author_hcs_all_tornadoes.png"
	fig_path.parent.mkdir(parents=True, exist_ok=True)
	fig, ax = plt.subplots(figsize=(9, 5))
	ax.plot(lags, observed, color="black", linewidth=1.8, label="Observed")
	ax.plot(lags, null_mean, color="0.35", linewidth=1.4, label="Phase-randomized null mean")
	ax.fill_between(lags, low, high, color="0.8", alpha=0.7, label="95% surrogate band")
	ax.axvline(0, color="0.6", linestyle="--", linewidth=1)
	ax.set_xlabel("Days from author HCS crossing")
	ax.set_ylabel("Daily mean all tornadoes")
	ax.set_title("Phase-randomized null test: author-HCS all tornadoes")
	ax.legend(frameon=False)
	fig.tight_layout()
	fig.savefig(fig_path, dpi=180, bbox_inches="tight")
	plt.close(fig)

	lag0 = out_df.loc[out_df["lag"] == 0].iloc[0]
	outside_count = int(out_df["outside_95_band"].sum())
	lag0_outside = bool(lag0["outside_95_band"])

	interpretation = (
		"Lag 0 is outside the surrogate null band; possible event alignment signal."
		if lag0_outside
		else "Lag 0 is within the surrogate null band; this does not establish equivalence or absence of an effect."
	)

	summary_df = pd.DataFrame(
		[
			{
				"event_count_used": int(len(event_idx)),
				"iterations": int(args.iterations),
				"lag0_observed": float(lag0["observed_daily_mean"]),
				"lag0_null_mean": float(lag0["null_mean"]),
				"lag0_null_q025": float(lag0["null_q025"]),
				"lag0_null_q975": float(lag0["null_q975"]),
				"lag0_outside_band": lag0_outside,
				"outside_band_lag_count": outside_count,
				"interpretation": interpretation,
			}
		]
	)
	table_path = ROOT / "data" / "derived" / "tables" / "phase_randomized_author_hcs_summary.csv"
	table_path.parent.mkdir(parents=True, exist_ok=True)
	summary_df.to_csv(table_path, index=False)

	report_lines = [
		"# Phase-Randomized Null Test Summary",
		"",
		f"Event count used: {len(event_idx)}",
		f"Iterations: {args.iterations}",
		f"Lag 0 observed: {lag0['observed_daily_mean']:.6f}",
		f"Lag 0 null mean: {lag0['null_mean']:.6f}",
		f"Lag 0 null 95% band: [{lag0['null_q025']:.6f}, {lag0['null_q975']:.6f}]",
		f"Lag 0 outside band: {lag0_outside}",
		f"Count of lags outside 95% band: {outside_count}",
		"",
		interpretation,
		"",
		"Interpretation should emphasize whether lag 0 is special; scattered outside-band lags are expected under multiple testing across 61 lags.",
	]
	report_path = ROOT / "data" / "derived" / "reports" / "phase_randomized_author_hcs_summary.md"
	report_path.parent.mkdir(parents=True, exist_ok=True)
	report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

	write_script_manifest(
		"29_phase_randomized_null_test.py",
		[analysis_path, author_path],
		{
			"spe_csv": str(spe_path.relative_to(ROOT)),
			"figure_png": str(fig_path.relative_to(ROOT)),
			"summary_csv": str(table_path.relative_to(ROOT)),
			"summary_md": str(report_path.relative_to(ROOT)),
		},
		{
			"event_count_used": int(len(event_idx)),
			"iterations": int(args.iterations),
			"lag0_outside_band": lag0_outside,
			"outside_band_lag_count": outside_count,
		},
		assumptions=["Phase-randomized surrogates preserve Fourier amplitudes while randomizing phase, maintaining broad autocorrelation structure."],
	)

	print(f"Saved: {spe_path}")
	print(f"Saved: {fig_path}")
	print(f"Saved: {table_path}")
	print(f"Saved: {report_path}")
	print(summary_df.to_string(index=False))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
