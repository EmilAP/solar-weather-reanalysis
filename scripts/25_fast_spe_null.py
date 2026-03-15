from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DAILY_PATH = PROJECT_ROOT / "data" / "derived" / "daily" / "analysis_daily.csv"
EVENT_PATH = PROJECT_ROOT / "data" / "derived" / "catalogs" / "author_hcs_catalog.csv"
OUT_PATH = PROJECT_ROOT / "data" / "derived" / "spe" / "fast_null_test_all_tornadoes.csv"

WINDOW = 30
ITER = 500
SEED = 42


def main() -> int:
    rng = np.random.default_rng(SEED)

    df = pd.read_csv(DAILY_PATH, parse_dates=["date"])
    events = pd.read_csv(EVENT_PATH)

    # Clean daily dates to naive normalized daily timestamps
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()

    # Parse event datetimes robustly, convert to naive daily timestamps
    events["datetime_utc"] = pd.to_datetime(events["datetime_utc"], utc=True, errors="coerce")
    events = events.dropna(subset=["datetime_utc"]).copy()
    events["event_date"] = events["datetime_utc"].dt.tz_convert(None).dt.normalize()

    # Match paper period exactly
    events = events[(events["year"] >= 1963) & (events["year"] <= 2023)].copy()

    tornado = df["all_tornadoes"].to_numpy(dtype=float)
    dates = pd.DatetimeIndex(df["date"])

    # Convert event dates to matching daily numpy datetime type
    event_days = events["event_date"].to_numpy(dtype="datetime64[ns]")
    date_days = dates.to_numpy(dtype="datetime64[ns]")

    event_idx = np.searchsorted(date_days, event_days)

    # Keep only exact matches that fall on valid daily rows
    valid = (
        (event_idx >= 0)
        & (event_idx < len(date_days))
        & (date_days[event_idx] == event_days)
    )
    event_idx = event_idx[valid]

    lags = np.arange(-WINDOW, WINDOW + 1)

    # Exclude edge events that cannot support full window
    event_idx = event_idx[(event_idx >= WINDOW) & (event_idx < len(tornado) - WINDOW)]

    if len(event_idx) == 0:
        raise ValueError("No valid event indices found after date matching and edge filtering.")

    def extract_windows(indices: np.ndarray) -> np.ndarray:
        # Shape: (n_events, n_lags)
        return tornado[indices[:, None] + lags[None, :]]

    observed = extract_windows(event_idx)
    obs_mean = observed.mean(axis=0)

    null_means = np.empty((ITER, len(lags)), dtype=float)

    for i in range(ITER):
        rand_idx = rng.integers(WINDOW, len(tornado) - WINDOW, size=len(event_idx))
        sim = extract_windows(rand_idx)
        null_means[i, :] = sim.mean(axis=0)

        if (i + 1) % 50 == 0:
            print(f"Completed {i + 1}/{ITER} iterations")

    low = np.percentile(null_means, 2.5, axis=0)
    high = np.percentile(null_means, 97.5, axis=0)
    null_mean = null_means.mean(axis=0)

    result = pd.DataFrame(
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

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT_PATH, index=False)

    print(f"Saved: {OUT_PATH}")
    print(f"Event count used: {len(event_idx)}")
    print(result.loc[result['lag'] == 0].to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
