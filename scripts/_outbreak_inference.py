from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
from scipy.stats import beta

from _utils import (
    ROOT,
    year_month_matched_sampler,
    year_month_cluster_shift_sampler,
    year_season_cluster_shift_sampler,
)


ITERATIONS = 50_000
SEED = 20260316
MODELS = ("year_month_independent", "year_month_cluster_rotation", "year_season_cluster_shift_15d")
FAMILIES = (
    "HCS_author_catalog", "HCS_reconstructed_catalog", "CIR_arrival_catalog",
    "ICME_impact_catalog", "major_HSS_declining_phase_catalog",
)


def specifications(family: str) -> list[tuple[str, int, int]]:
    specs = [(f"plus_minus_{n}d", -n, n) for n in (1, 2, 3)]
    directional = {
        "CIR_arrival_catalog": ("CIR_following_window_0_to_plus3", -3, 0),
        "HCS_reconstructed_catalog": ("HCS_preceding_window_minus3_to_0", 0, 3),
        "ICME_impact_catalog": ("ICME_following_window_0_to_plus3", -3, 0),
        "major_HSS_declining_phase_catalog": ("HSS_declining_phase_window_membership", 0, 0),
    }
    if family in directional:
        specs.append(directional[family])
    return specs


def exposure_population(
    anchors: pd.Series, valid_dates: pd.Series, family: str
) -> tuple[pd.Series, pd.Series]:
    valid = pd.Series(pd.to_datetime(valid_dates)).dt.normalize().drop_duplicates().sort_values()
    if family == "ICME_impact_catalog":
        valid = valid[valid >= pd.Timestamp("1996-01-01")]
    anchors = pd.Series(pd.to_datetime(anchors)).dt.normalize()
    selected = anchors[anchors.isin(valid)]
    if selected.empty or valid.empty:
        raise ValueError(f"{family}: no outbreak dates in documented exposure coverage.")
    return selected.reset_index(drop=True), valid.reset_index(drop=True)


def tail_summary(observed: float, draws: np.ndarray, lower: bool = False) -> dict[str, float | int]:
    draws = np.asarray(draws, dtype=float)
    if not len(draws) or not np.isfinite(draws).all() or not np.isfinite(observed):
        raise ValueError("Monte Carlo statistics must be nonempty and finite.")
    hits = int(np.sum(draws <= observed) if lower else np.sum(draws >= observed))
    count = len(draws)
    return {
        "p": (hits + 1) / (count + 1),
        "exceedances": hits,
        "iterations": count,
        "mc_low": 0.0 if hits == 0 else float(beta.ppf(0.05 / (2 * 87), hits, count - hits + 1)),
        "mc_high": 1.0 if hits == count else float(beta.ppf(1 - 0.05 / (2 * 87), hits + 1, count - hits)),
    }


def family_statistics(
    anchors: pd.Series,
    events: pd.Series,
    valid_dates: pd.Series,
    family: str,
    iterations: int = ITERATIONS,
) -> tuple[np.ndarray, np.ndarray, int]:
    anchors, valid = exposure_population(anchors, valid_dates, family)
    events = pd.Series(pd.to_datetime(events)).dt.normalize().dropna().drop_duplicates().sort_values()
    events = events[events.between(valid.min(), valid.max())]
    if events.empty:
        raise ValueError(f"{family}: empty event catalog in analysis coverage.")
    if iterations < 1:
        raise ValueError("Monte Carlo iteration count must be positive.")
    specs = specifications(family)
    day0 = valid.min()
    n_days = int((valid.max() - day0).days) + 1
    calendar = np.arange(n_days)
    event_offsets = (events - day0).dt.days.to_numpy()
    pos = np.searchsorted(event_offsets, calendar)
    distance = np.minimum(
        abs(calendar - event_offsets[np.clip(pos, 0, len(event_offsets) - 1)]),
        abs(calendar - event_offsets[np.clip(pos - 1, 0, len(event_offsets) - 1)]),
    )
    membership = []
    for _, low, high in specs:
        matched = np.zeros(n_days, dtype=bool)
        for offset in range(low, high + 1):
            targets = event_offsets - offset
            matched[targets[(targets >= 0) & (targets < n_days)]] = True
        membership.append(matched)
    membership = np.asarray(membership)

    def statistics(offsets: np.ndarray) -> np.ndarray:
        d = distance[offsets]
        return np.concatenate(([d.mean(), np.median(d)], membership[:, offsets].sum(axis=1)))

    observed = statistics((anchors - day0).dt.days.to_numpy())
    signature = hashlib.sha256()
    signature.update(json.dumps({"version": 1, "iterations": iterations, "seed": SEED, "family": family}).encode())
    for dates in (anchors, events, valid):
        signature.update(dates.to_numpy(dtype="datetime64[D]").tobytes())
    cache = ROOT / "data" / "derived" / "spe" / f"outbreak_null_{family}.npz"
    if cache.exists():
        with np.load(cache, allow_pickle=False) as saved:
            if str(saved["signature"]) == signature.hexdigest():
                draws = saved["draws"]
                if draws.shape != (3, iterations, len(observed)) or not np.isfinite(draws).all():
                    raise ValueError(f"Invalid cached null statistics: {cache}")
                return observed, draws, len(anchors)

    samplers = (
        year_month_matched_sampler(anchors, valid),
        year_month_cluster_shift_sampler(anchors, valid),
        year_season_cluster_shift_sampler(anchors, valid, 15),
    )
    draws = np.empty((3, iterations, len(observed)))
    for model, sampler in enumerate(samplers):
        rng = np.random.default_rng(np.random.SeedSequence([SEED, FAMILIES.index(family), model]))
        for i in range(iterations):
            sampled = sampler(rng)
            draws[model, i] = statistics((sampled - day0).dt.days.to_numpy())
            if (i + 1) % 10_000 == 0:
                print(f"{family} {MODELS[model]}: {i + 1}/{iterations}", flush=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, signature=signature.hexdigest(), draws=draws)
    return observed, draws, len(anchors)


def distance_summary(anchors: pd.Series, catalogs: dict[str, pd.Series], valid: pd.Series) -> pd.DataFrame:
    rows = []
    for family in FAMILIES:
        obs, draws, count = family_statistics(anchors, catalogs[family], valid, family)
        row = {
            "event_family": family, "outbreak_count": count,
            "observed_mean_abs_distance": obs[0], "observed_median_abs_distance": obs[1],
            "interpretation": "Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.",
        }
        for model, prefix, suffix in ((0, "", ""), (1, "cluster_", "_cluster"), (2, "season_cluster_", "_season_cluster")):
            row.update({
                f"{prefix}null_mean_abs_distance": draws[model, :, 0].mean(),
                f"{prefix}null_median": draws[model, :, 1].mean(),
                f"{prefix}null_q025": np.quantile(draws[model, :, 0], 0.025),
                f"{prefix}null_q975": np.quantile(draws[model, :, 0], 0.975),
            })
            for col, metric in ((0, "mean"), (1, "median")):
                tail = tail_summary(obs[col], draws[model, :, col], lower=True)
                key = f"p_value_{metric}{suffix}"
                row[key] = tail["p"]
                for field in ("mc_low", "mc_high", "iterations", "exceedances"):
                    row[f"{key}_{field}"] = tail[field]
        rows.append(row)
    return pd.DataFrame(rows)


def coincidence_summary(anchors: pd.Series, catalogs: dict[str, pd.Series], valid: pd.Series) -> pd.DataFrame:
    rows = []
    for family in FAMILIES:
        obs, draws, count = family_statistics(anchors, catalogs[family], valid, family)
        for col, (name, _, _) in enumerate(specifications(family), start=2):
            row = {
                "event_family": family, "window_definition": name, "outbreak_count": count,
                "observed_count": int(obs[col]), "observed_proportion": obs[col] / count,
                "interpretation": "Exploratory: use the combined Holm-adjusted results and Monte Carlo uncertainty.",
            }
            for model, prefix, suffix in ((0, "", ""), (1, "cluster_", "_cluster"), (2, "season_cluster_", "_season_cluster")):
                values = draws[model, :, col]
                row.update({
                    f"{prefix}null_mean_count": values.mean(),
                    f"{prefix}null_q025_count": np.quantile(values, 0.025),
                    f"{prefix}null_q975_count": np.quantile(values, 0.975),
                })
                tail = tail_summary(obs[col], values)
                key = f"p_value{suffix}"
                row[key] = tail["p"]
                for field in ("mc_low", "mc_high", "iterations", "exceedances"):
                    row[f"{key}_{field}"] = tail[field]
            rows.append(row)
    return pd.DataFrame(rows)
