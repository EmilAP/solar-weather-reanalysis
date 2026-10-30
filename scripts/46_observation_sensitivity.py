from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import hypergeom

from _hcs_reconstruction import reconstruct_hcs
from _utils import ROOT, complete_window_dates, holm_adjust_pvalues, make_logger, write_script_manifest


ITERATIONS = 10_000
SEED = 20261030
MIN_HOURS = (1, 12, 18, 24)
SPC_FORMAT_URL = "https://www.spc.noaa.gov/wcm/data/SPC_severe_database_description.pdf"
DERIVED = ROOT / "data/derived"


def utc_tornado_dates(events: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "event_datetime_local", "tz"}
    if not required.issubset(events):
        raise ValueError("Missing SPC timing fields; rerun script 12 to retain timezone codes.")
    dates = pd.to_datetime(events["date"], errors="raise")
    local = pd.to_datetime(events["event_datetime_local"], errors="raise", format="mixed")
    if local.isna().any() or dates.isna().any():
        raise ValueError("SPC timing sensitivity requires nonmissing dates and clock times.")
    codes = pd.to_numeric(events["tz"], errors="coerce")
    known = codes.isin([0, 3])
    utc = local + pd.to_timedelta(codes.eq(3).astype(int) * 6, unit="h")
    return pd.DataFrame({
        "catalog_date": dates.dt.normalize(), "timezone_code": codes,
        "timezone_documented": known, "utc_date": utc.dt.normalize().where(known),
    })


def yearly_profiles(
    index: pd.DatetimeIndex, events: pd.DatetimeIndex, outcome: np.ndarray,
) -> tuple[np.ndarray, list[np.ndarray]]:
    eligible = pd.DatetimeIndex(complete_window_dates(events, index, 30))
    if eligible.empty:
        raise ValueError("No complete-window HCS events in sensitivity variant.")
    positions = index.get_indexer(eligible)
    lags = np.arange(-30, 31)
    observed = outcome[positions[:, None] + lags].sum(axis=0)
    groups = []
    for year in sorted(set(eligible.year)):
        current = positions[eligible.year == year]
        shifts = [
            shift for shift in range(-15, 16)
            if (current + shift >= 30).all() and (current + shift < len(index) - 30).all()
            and (index[current + shift].year == year).all()
        ]
        if not shifts:
            raise ValueError(f"No valid annual shifts for {year}.")
        groups.append(np.stack([
            outcome[current[:, None] + shift + lags].sum(axis=0) for shift in shifts
        ]))
    return observed, groups


def daily_test(
    index: pd.DatetimeIndex, events: pd.DatetimeIndex, outcome: np.ndarray,
    iterations: int, seed: int,
) -> tuple[dict[str, float | int], pd.DataFrame, np.ndarray]:
    if iterations < 1:
        raise ValueError("Sensitivity iteration count must be positive.")
    count = len(complete_window_dates(events, index, 30))
    observed, groups = yearly_profiles(index, events, outcome)
    rng = np.random.default_rng(seed)
    draws = np.zeros((iterations, 61), dtype=np.int64)
    for profiles in groups:
        draws += profiles[rng.integers(len(profiles), size=iterations)]
    high = int(np.count_nonzero(draws[:, 30] >= observed[30]))
    low = int(np.count_nonzero(draws[:, 30] <= observed[30]))
    max_hits = int(np.count_nonzero(draws.max(axis=1) >= observed.max()))
    null = draws / count
    means = observed / count
    row = {
        "event_count": count, "iterations": iterations, "seed": seed,
        "lag0_observed": means[30], "lag0_null_mean": null[:, 30].mean(),
        "lag0_null_q025": np.quantile(null[:, 30], .025),
        "lag0_null_q975": np.quantile(null[:, 30], .975),
        "lag0_upper_hits": high, "lag0_lower_hits": low,
        "lag0_p_two_sided": min(1., 2 * (min(high, low) + 1) / (iterations + 1)),
        "maximum_observed": means.max(), "maximum_lag": int(np.argmax(means) - 30),
        "maximum_hits": max_hits, "maximum_p": (max_hits + 1) / (iterations + 1),
    }
    curve = pd.DataFrame({
        "lag": np.arange(-30, 31), "event_count": count, "observed_daily_mean": means,
        "null_mean": null.mean(axis=0), "null_q025": np.quantile(null, .025, axis=0),
        "null_q975": np.quantile(null, .975, axis=0),
    })
    return row, curve, draws


def exact_coincidence(
    index: pd.DatetimeIndex, anchors: pd.DatetimeIndex, events: pd.DatetimeIndex,
) -> list[dict[str, float | int | str]]:
    if not anchors.isin(index).all():
        raise ValueError("Outbreak anchors must be within the analysis calendar.")
    events = events[events.isin(index)]
    if events.empty:
        raise ValueError("No HCS dates for exact coincidence sensitivity.")
    membership = np.zeros(len(index), dtype=int)
    event_positions = index.get_indexer(events)
    for shift in (-1, 0, 1):
        positions = event_positions + shift
        membership[positions[(positions >= 0) & (positions < len(index))]] = 1
    observed = int(membership[index.get_indexer(anchors)].sum())
    distributions = [np.array([1.]), np.array([1.]), np.array([1.])]
    starts = pd.DataFrame({"date": anchors})
    for (year, month), group in starts.groupby([starts.date.dt.year, starts.date.dt.month]):
        first = pd.Timestamp(year=year, month=month, day=1)
        month_dates = pd.date_range(first, periods=first.days_in_month)
        month_positions = index.get_indexer(month_dates)
        if (month_positions < 0).any():
            raise ValueError("Exact coincidence requires complete calendar months.")
        values = membership[month_positions]
        n, k = len(values), len(group)
        if k > n:
            raise ValueError("Exact hypergeometric sensitivity requires at most one start per day.")
        distributions[0] = np.convolve(
            distributions[0], hypergeom.pmf(np.arange(k + 1), n, values.sum(), k),
        )
        offsets = group.date.dt.day.to_numpy() - 1
        counts = [int(values[(offsets + shift) % n].sum()) for shift in range(n)]
        distributions[1] = np.convolve(
            distributions[1], np.bincount(counts, minlength=k + 1) / n,
        )
    for year, group in starts.groupby(starts.date.dt.year):
        dates = pd.DatetimeIndex(group.date)
        positions = index.get_indexer(dates)
        shifts = [
            shift for shift in range(-15, 16)
            if ((dates + pd.Timedelta(days=shift)).year == year).all()
        ]
        counts = [int(membership[positions + shift].sum()) for shift in shifts]
        distributions[2] = np.convolve(
            distributions[2], np.bincount(counts, minlength=len(group) + 1) / len(shifts),
        )
    rows = []
    models = ("year_month_independent", "year_month_cluster_rotation", "year_season_cluster_shift_15d")
    for model, distribution in zip(models, distributions, strict=True):
        if not np.isclose(distribution.sum(), 1, atol=1e-12, rtol=0):
            raise ValueError(f"Exact distribution fails normalization: {model}.")
        rows.append({
            "null_model": model, "outbreak_count": len(anchors), "observed_count": observed,
            "null_mean": float(distribution @ np.arange(len(distribution))),
            "p_exact": float(distribution[observed:].sum()),
        })
    return rows


def main() -> int:
    logger = make_logger("46_observation_sensitivity")
    daily = pd.read_csv(DERIVED / "daily/analysis_daily.csv", parse_dates=["date"])
    index = pd.DatetimeIndex(daily.date)
    if not index.equals(pd.date_range(index.min(), index.max())):
        raise ValueError("Sensitivity analysis requires a complete daily calendar.")
    events = pd.read_csv(DERIVED / "daily/tornado_events_clean.csv")
    timing = utc_tornado_dates(events)
    in_period = timing.catalog_date.isin(index)
    audit = timing.loc[in_period].groupby(
        ["timezone_code", "timezone_documented"], dropna=False,
    ).size().reset_index(name="record_count")
    if not audit.record_count.sum() == daily.all_tornadoes.sum():
        raise ValueError("SPC timing records do not match primary daily totals.")
    def counts(column: str, selected: pd.Series) -> np.ndarray:
        return timing.loc[selected, column].value_counts().reindex(index, fill_value=0).to_numpy(dtype=np.int64)
    known = timing.timezone_documented
    outcomes = {
        "catalog_all": daily.all_tornadoes.to_numpy(dtype=np.int64),
        "catalog_documented": counts("catalog_date", known),
        "utc_documented": counts("utc_date", known),
    }
    hourly = pd.read_parquet(DERIVED / "daily/omni_hourly_clean.parquet", columns=["datetime_utc", "bx_gse"])
    hours = pd.to_datetime(hourly.datetime_utc, utc=True)
    if hours.duplicated().any():
        raise ValueError("Duplicate OMNI hourly timestamps would inflate coverage.")
    coverage = hourly.bx_gse.notna().groupby(hours.dt.tz_convert(None).dt.normalize()).sum()
    omni = pd.read_csv(DERIVED / "daily/omni_daily.csv", parse_dates=["date"])
    valid_hours = omni.date.map(coverage).fillna(0).astype(int)
    catalogs = {}
    author = pd.read_csv(DERIVED / "catalogs/author_hcs_catalog.csv")
    catalogs["author"] = pd.DatetimeIndex(pd.to_datetime(author.datetime_utc, utc=True)).tz_convert(None).normalize().unique().sort_values()
    canonical = pd.read_csv(DERIVED / "catalogs/hcs_from_omni.csv")
    reconstructed, _ = reconstruct_hcs(omni)
    pd.testing.assert_frame_equal(
        canonical.assign(date=pd.to_datetime(canonical.date)),
        reconstructed, check_dtype=False,
    )
    catalogs["reconstructed_primary"] = pd.DatetimeIndex(reconstructed.date)
    coverage_rows = []
    catalog_rows = []
    for minimum in MIN_HOURS:
        constrained, _ = reconstruct_hcs(omni, coverage_ok=valid_hours.ge(minimum))
        name = f"reconstructed_min_{minimum:02d}h"
        catalogs[name] = pd.DatetimeIndex(constrained.date)
        available = valid_hours[omni.date.isin(index)]
        primary_dates = catalogs["reconstructed_primary"]
        analyzed = catalogs[name][catalogs[name].isin(index)]
        coverage_rows.append({
            "catalog": name, "minimum_valid_bx_hours": minimum,
            "qualified_analysis_days": int(available.ge(minimum).sum()),
            "removed_observed_bx_days": int(((available > 0) & (available < minimum)).sum()),
            "analysis_crossings": len(analyzed),
            "complete_window_crossings": len(complete_window_dates(analyzed, index, 30)),
            "retained_primary_dates": int(analyzed.isin(primary_dates).sum()),
            "new_dates_relative_to_primary": int((~analyzed.isin(primary_dates)).sum()),
            "coverage_gap_fill": "Disallowed on days failing the coverage threshold.",
        })
    for name, catalog in catalogs.items():
        for date in catalog[catalog.isin(index)]:
            catalog_rows.append({"catalog": name, "date": date})
    scenarios = [(name, 0, calendar) for name in catalogs for calendar in outcomes]
    scenarios += [(name, shift, "catalog_all") for name in ("author", "reconstructed_primary") for shift in (-1, 1)]
    summaries, curves, banks = [], [], {}
    for number, (name, shift, calendar) in enumerate(scenarios):
        scenario = f"{name}__event_shift_{shift:+d}__{calendar}"
        row, curve, draws = daily_test(
            index, catalogs[name] + pd.Timedelta(days=shift), outcomes[calendar],
            ITERATIONS, SEED + list(catalogs).index(name),
        )
        row.update(scenario=scenario, catalog=name, event_shift_days=shift, tornado_calendar=calendar)
        summaries.append(row)
        curve.insert(0, "scenario", scenario)
        curves.append(curve)
        banks[f"scenario_{number:02d}"] = draws
        logger.info("Daily sensitivity %d/%d: %s", number + 1, len(scenarios), scenario)
    summary = pd.DataFrame(summaries)
    pvalues = summary[["lag0_p_two_sided", "maximum_p"]].to_numpy().ravel()
    adjusted = holm_adjust_pvalues(pvalues).reshape(-1, 2)
    summary[["lag0_p_holm", "maximum_p_holm"]] = adjusted
    summary["multiplicity_family_tests"] = len(pvalues)
    outbreak_table = pd.read_csv(DERIVED / "catalogs/supplement_table_s1_outbreaks.csv")
    anchors = pd.DatetimeIndex(pd.to_datetime(outbreak_table.outbreak_date_start))
    if anchors.has_duplicates:
        raise ValueError("Outbreak sensitivity requires unique start dates.")
    outbreak_rows = []
    variants = [(name, 0) for name in catalogs]
    variants += [(name, shift) for name in ("author", "reconstructed_primary") for shift in (-1, 1)]
    for name, shift in variants:
        for row in exact_coincidence(index, anchors + pd.Timedelta(days=shift), catalogs[name]):
            row.update(catalog=name, outbreak_shift_days=shift)
            outbreak_rows.append(row)
    outbreak = pd.DataFrame(outbreak_rows)
    outbreak["p_holm_sensitivity"] = holm_adjust_pvalues(outbreak.p_exact)
    outbreak["multiplicity_family_tests"] = len(outbreak)
    paths = {}
    for stem, frame in {
        "observation_sensitivity_coverage": pd.DataFrame(coverage_rows),
        "observation_sensitivity_timezone_audit": audit,
        "observation_sensitivity_daily": summary,
        "observation_sensitivity_curves": pd.concat(curves, ignore_index=True),
        "observation_sensitivity_outbreak": outbreak,
        "observation_sensitivity_catalogs": pd.DataFrame(catalog_rows),
    }.items():
        path = DERIVED / "tables" / f"{stem}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
        paths[stem] = path
    bank_path = DERIVED / "spe/observation_sensitivity_daily_draws.npz"
    np.savez_compressed(bank_path, **banks)
    paths["retained_daily_integer_totals"] = bank_path
    metadata = {
        "seed": SEED, "iterations": ITERATIONS, "spc_timezone_documentation": SPC_FORMAT_URL,
        "timezone_policy": "SPC format field 7: code 3=CST (fixed UTC-6), code 0=GMT; all other codes unresolved and excluded only in paired timing analyses.",
        "unresolved_timezone_records": int((in_period & ~known).sum()),
        "documented_records_changing_date": int((in_period & known & timing.utc_date.ne(timing.catalog_date)).sum()),
        "documented_utc_records_outside_analysis": int((in_period & known & ~timing.utc_date.isin(index)).sum()),
        "documented_utc_records_entering_analysis": int((~in_period & known & timing.utc_date.isin(index)).sum()),
        "coverage_policy": "Count valid Bx hours, reconstruct whole available OMNI period, disallow fills on failing days; retain primary ambiguity and spacing rules. Threshold 1 isolates missing-day bridging.",
        "daily_null": "Shared uniform annual shifts up to 15 days, preserving year and complete-window eligibility. Integer totals avoid floating-point tie errors.",
        "daily_scenarios": summary.scenario.tolist(), "daily_family_tests": len(pvalues),
        "outbreak_family_tests": len(outbreak),
        "outbreak_policy": "Exact one-day coincidence tails under all three original null designs. Full analysis calendar held fixed. No source entry excluded. Start-date shifts are stress tests, not UTC conversions.",
        "scope": "Separate retrospective sensitivity families, not a new preregistration or a rerun of the original 87-test family; no meteorological adjustment or causal validation.",
    }
    metadata_path = DERIVED / "reports/observation_sensitivity.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    paths["metadata"] = metadata_path
    report_path = DERIVED / "reports/observation_sensitivity.md"
    report_path.write_text(
        "# Observation sensitivity analyses\n\n"
        f"- Daily scenarios: {len(summary)}; two endpoints each, Holm across {len(pvalues)} tests.\n"
        f"- Daily null: {ITERATIONS:,} annual cluster shifts; retained integer-total draws.\n"
        f"- Outbreak family: {len(outbreak)} exact one-day tests across three nulls, separately Holm-adjusted.\n"
        f"- Unresolved timezone records: {metadata['unresolved_timezone_records']}.\n"
        f"- Documented records changing calendar date: {metadata['documented_records_changing_date']}.\n"
        f"- Daily adjusted rejections: lag 0={int(summary.lag0_p_holm.le(.05).sum())}; "
        f"maximum={int(summary.maximum_p_holm.le(.05).sum())}.\n"
        f"- Outbreak adjusted rejections: {int(outbreak.p_holm_sensitivity.le(.05).sum())}.\n\n"
        f"Timezone source: {SPC_FORMAT_URL} (field 7, page 1; accessed 2026-10-30).\n\n"
        "Coverage screens affect only the reconstructed HCS catalog, not the supplied author catalog. "
        "Low-coverage days are hard barriers, even to one-day filling. The 1-hour screen separates "
        "this change from increasing coverage thresholds. Full-calendar nulls do not solve exposure "
        "missingness or meteorological confounding. UTC timing uses a paired known-code subset, "
        "not guessed geographic timezones. Boundary flows are reported in JSON. "
        "Outbreak shifts do not change source interpretations or simulate known physical times. "
        "Sensitivity multiplicity families do not replace the original 16- or 87-test families. "
        "Daily p-values have finite Monte Carlo precision; outbreak tails are exact conditional on the nulls.\n",
    )
    paths["report"] = report_path
    write_script_manifest(
        "46_observation_sensitivity.py",
        [DERIVED / path for path in [
            "daily/analysis_daily.csv", "daily/tornado_events_clean.csv", "daily/omni_daily.csv",
            "daily/omni_hourly_clean.parquet", "catalogs/author_hcs_catalog.csv",
            "catalogs/hcs_from_omni.csv", "catalogs/supplement_table_s1_outbreaks.csv",
        ]], {name: str(path.relative_to(ROOT)) for name, path in paths.items()}, metadata,
        assumptions=[metadata["timezone_policy"], metadata["coverage_policy"], metadata["scope"]],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
