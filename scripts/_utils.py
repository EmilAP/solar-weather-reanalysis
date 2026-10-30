from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from common import ROOT, DATA_DIR, make_logger as common_make_logger, sha256_file, write_manifest


CONFIG_PATH = ROOT / "config" / "analysis_config.yaml"
DERIVED_DIR = DATA_DIR / "derived"
CATALOG_DIR = DERIVED_DIR / "catalogs"
DAILY_DIR = DERIVED_DIR / "daily"
SPE_DIR = DERIVED_DIR / "spe"
MODEL_DIR = DERIVED_DIR / "models"
FIGURE_DIR = DERIVED_DIR / "figures"
TABLE_DIR = DERIVED_DIR / "tables"
REPORT_DIR = DERIVED_DIR / "reports"

SUPPLEMENT_MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
SUPPLEMENT_DATE_RANGE_PATTERNS = (
    re.compile(rf"(?P<start_day>\d{{1,2}})\s*-\s*(?P<end_day>\d{{1,2}})\s+(?P<month>{SUPPLEMENT_MONTH_RE})\.?\s*,?\s*(?P<year>\d{{4}})", re.IGNORECASE),
    re.compile(rf"(?P<month>{SUPPLEMENT_MONTH_RE})\.?\s+(?P<start_day>\d{{1,2}})\s*-\s*(?P<end_day>\d{{1,2}})\s*,?\s*(?P<year>\d{{4}})", re.IGNORECASE),
    re.compile(rf"(?P<start_day>\d{{1,2}})\s+(?P<start_month>{SUPPLEMENT_MONTH_RE})\.?\s*-\s*(?P<end_day>\d{{1,2}})\s+(?P<end_month>{SUPPLEMENT_MONTH_RE})\.?\s*,?\s*(?P<year>\d{{4}})", re.IGNORECASE),
    re.compile(rf"(?P<start_month>{SUPPLEMENT_MONTH_RE})\.?\s+(?P<start_day>\d{{1,2}})\s*-\s*(?P<end_month>{SUPPLEMENT_MONTH_RE})\.?\s+(?P<end_day>\d{{1,2}})\s*,?\s*(?P<year>\d{{4}})", re.IGNORECASE),
)
SUPPLEMENT_SINGLE_DATE_PATTERNS = (
    re.compile(rf"(?P<month>{SUPPLEMENT_MONTH_RE})\.?\s+(?P<day>\d{{1,2}}),?\s+(?P<year>\d{{4}})", re.IGNORECASE),
    re.compile(rf"(?P<day>\d{{1,2}})\s+(?P<month>{SUPPLEMENT_MONTH_RE})\.?\s*,?\s*(?P<year>\d{{4}})", re.IGNORECASE),
)


def _supplement_date(day: str, month: str, year: str) -> pd.Timestamp | pd.NaT:
    try:
        month_number = int(pd.to_datetime(month[:3], format="%b").month)
        return pd.Timestamp(year=int(year), month=month_number, day=int(day))
    except (TypeError, ValueError):
        return pd.NaT


def parse_supplement_date_range(value: object) -> tuple[pd.Timestamp | pd.NaT, pd.Timestamp | pd.NaT]:
    if pd.isna(value):
        return pd.NaT, pd.NaT

    text = re.sub(r"\s+", " ", str(value)).strip().replace("–", "-").replace("—", "-")
    if not text:
        return pd.NaT, pd.NaT

    for pattern in SUPPLEMENT_DATE_RANGE_PATTERNS:
        match = pattern.fullmatch(text)
        if match is None:
            continue

        values = match.groupdict()
        year = values["year"]
        start_month = values.get("start_month") or values.get("month")
        end_month = values.get("end_month") or values.get("month")
        start = _supplement_date(values["start_day"], start_month, year)
        end = _supplement_date(values["end_day"], end_month, year)
        if pd.isna(start) or pd.isna(end):
            return pd.NaT, pd.NaT
        if end < start and start.month > end.month:
            start = _supplement_date(values["start_day"], start_month, str(int(year) - 1))
        if end < start:
            return pd.NaT, pd.NaT
        return start, end

    for pattern in SUPPLEMENT_SINGLE_DATE_PATTERNS:
        match = pattern.fullmatch(text)
        if match is not None:
            values = match.groupdict()
            date = _supplement_date(values["day"], values["month"], values["year"])
            return date, date

    iso_match = re.fullmatch(r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})", text)
    if iso_match is not None:
        try:
            date = pd.Timestamp(year=int(iso_match["year"]), month=int(iso_match["month"]), day=int(iso_match["day"]))
            return date, date
        except ValueError:
            return pd.NaT, pd.NaT

    return pd.NaT, pd.NaT


def year_month_matched_dates(
    observed_dates: Sequence[pd.Timestamp],
    valid_dates: Sequence[pd.Timestamp],
    rng: np.random.Generator,
) -> pd.Series:
    return year_month_matched_sampler(observed_dates, valid_dates)(rng)


def year_month_matched_sampler(
    observed_dates: Sequence[pd.Timestamp],
    valid_dates: Sequence[pd.Timestamp],
) -> Callable[[np.random.Generator], pd.Series]:
    observed = pd.DatetimeIndex(pd.to_datetime(observed_dates, errors="coerce")).dropna().normalize()
    available = pd.DatetimeIndex(pd.to_datetime(valid_dates, errors="coerce")).dropna().normalize().unique()
    available_by_stratum: dict[tuple[int, int], list[np.datetime64]] = {}
    observed_indices_by_stratum: dict[tuple[int, int], list[int]] = {}
    for date in available:
        available_by_stratum.setdefault((date.year, date.month), []).append(date.to_datetime64())
    for index, date in enumerate(observed):
        observed_indices_by_stratum.setdefault((date.year, date.month), []).append(index)

    strata: list[tuple[np.ndarray, np.ndarray]] = []
    for stratum, indices in observed_indices_by_stratum.items():
        choices = available_by_stratum.get(stratum)
        if not choices:
            raise ValueError(f"No valid null dates available for year-month stratum {stratum}.")
        strata.append(
            (
                np.asarray(indices, dtype=int),
                np.asarray(choices, dtype="datetime64[ns]"),
            )
        )

    def sample(rng: np.random.Generator) -> pd.Series:
        sampled = np.empty(len(observed), dtype="datetime64[ns]")
        for indices, choices in strata:
            sampled[indices] = rng.choice(choices, size=len(indices), replace=len(indices) > len(choices))
        return pd.Series(sampled)

    return sample


def year_month_cluster_shift_dates(
    observed_dates: Sequence[pd.Timestamp],
    valid_dates: Sequence[pd.Timestamp],
    rng: np.random.Generator,
) -> pd.Series:
    return year_month_cluster_shift_sampler(observed_dates, valid_dates)(rng)


def year_month_cluster_shift_sampler(
    observed_dates: Sequence[pd.Timestamp],
    valid_dates: Sequence[pd.Timestamp],
) -> Callable[[np.random.Generator], pd.Series]:
    observed = pd.DatetimeIndex(pd.to_datetime(observed_dates, errors="coerce")).dropna().normalize()
    available_days_by_stratum: dict[tuple[int, int], set[int]] = {}
    indices_by_stratum: dict[tuple[int, int], list[int]] = {}
    offsets_by_stratum: dict[tuple[int, int], list[int]] = {}
    for date in pd.DatetimeIndex(pd.to_datetime(valid_dates, errors="coerce")).dropna().normalize():
        available_days_by_stratum.setdefault((date.year, date.month), set()).add(date.day)
    for index, date in enumerate(observed):
        stratum = (date.year, date.month)
        indices_by_stratum.setdefault(stratum, []).append(index)
        offsets_by_stratum.setdefault(stratum, []).append(date.day - 1)

    stratum_keys = list(indices_by_stratum)
    stratum_ids = np.empty(len(observed), dtype=int)
    day_offsets = np.empty(len(observed), dtype=int)
    stratum_days_in_month = np.empty(len(stratum_keys), dtype=int)
    stratum_month_starts = np.empty(len(stratum_keys), dtype="datetime64[D]")
    eligible_by_stratum: list[np.ndarray] = []

    for stratum_id, (year, month) in enumerate(stratum_keys):
        indices = indices_by_stratum[(year, month)]
        days_in_month = pd.Timestamp(year=year, month=month, day=1).days_in_month
        offsets = np.asarray(offsets_by_stratum[(year, month)], dtype=int)
        available_days = available_days_by_stratum.get((year, month), set())
        eligible_shifts = [
            shift
            for shift in range(days_in_month)
            if all(int(day) in available_days for day in (offsets + shift) % days_in_month + 1)
        ]
        if not eligible_shifts:
            raise ValueError(f"No cluster-preserving shifts available for year-month stratum {(year, month)}.")
        indices_array = np.asarray(indices, dtype=int)
        stratum_ids[indices_array] = stratum_id
        day_offsets[indices_array] = offsets
        stratum_days_in_month[stratum_id] = days_in_month
        stratum_month_starts[stratum_id] = np.datetime64(f"{year:04d}-{month:02d}-01", "D")
        eligible_by_stratum.append(np.asarray(eligible_shifts, dtype=int))

    max_eligible = max(len(shifts) for shifts in eligible_by_stratum)
    eligible_matrix = np.zeros((len(eligible_by_stratum), max_eligible), dtype=int)
    eligible_lengths = np.empty(len(eligible_by_stratum), dtype=int)
    for index, shifts in enumerate(eligible_by_stratum):
        eligible_lengths[index] = len(shifts)
        eligible_matrix[index, : len(shifts)] = shifts

    def sample(rng: np.random.Generator) -> pd.Series:
        choices = np.floor(rng.random(len(eligible_lengths)) * eligible_lengths).astype(int)
        shifts = eligible_matrix[np.arange(len(eligible_lengths)), choices]
        shifted_days = (day_offsets + shifts[stratum_ids]) % stratum_days_in_month[stratum_ids]
        sampled = stratum_month_starts[stratum_ids] + shifted_days.astype("timedelta64[D]")
        return pd.Series(sampled.astype("datetime64[ns]"))

    return sample


def year_season_cluster_shift_sampler(
    observed_dates: Sequence[pd.Timestamp],
    valid_dates: Sequence[pd.Timestamp],
    season_window_days: int,
) -> Callable[[np.random.Generator], pd.Series]:
    observed = pd.DatetimeIndex(pd.to_datetime(observed_dates, errors="coerce")).dropna().normalize()
    available_doys_by_year: dict[int, set[int]] = {}
    indices_by_year: dict[int, list[int]] = {}
    doys_by_year: dict[int, list[int]] = {}
    for date in pd.DatetimeIndex(pd.to_datetime(valid_dates, errors="coerce")).dropna().normalize():
        available_doys_by_year.setdefault(date.year, set()).add(date.dayofyear)
    for index, date in enumerate(observed):
        indices_by_year.setdefault(date.year, []).append(index)
        doys_by_year.setdefault(date.year, []).append(date.dayofyear)

    years = list(indices_by_year)
    indices_by_group: list[np.ndarray] = []
    doys_by_group: list[np.ndarray] = []
    eligible_by_group: list[np.ndarray] = []
    year_starts: list[np.datetime64] = []
    for year in years:
        indices = np.asarray(indices_by_year[year], dtype=int)
        doys = np.asarray(doys_by_year[year], dtype=int)
        days_in_year = pd.Timestamp(year=year, month=12, day=31).dayofyear
        available_doys = available_doys_by_year.get(year, set())
        eligible_shifts = [
            shift
            for shift in range(-season_window_days, season_window_days + 1)
            if np.all((doys + shift >= 1) & (doys + shift <= days_in_year))
            and all(int(day) in available_doys for day in doys + shift)
        ]
        if not eligible_shifts:
            raise ValueError(f"No season-matched cluster shifts available for year {year}.")
        indices_by_group.append(indices)
        doys_by_group.append(doys)
        eligible_by_group.append(np.asarray(eligible_shifts, dtype=int))
        year_starts.append(np.datetime64(f"{year:04d}-01-01", "D"))

    max_eligible = max(len(shifts) for shifts in eligible_by_group)
    eligible_matrix = np.zeros((len(eligible_by_group), max_eligible), dtype=int)
    eligible_lengths = np.empty(len(eligible_by_group), dtype=int)
    for index, shifts in enumerate(eligible_by_group):
        eligible_lengths[index] = len(shifts)
        eligible_matrix[index, : len(shifts)] = shifts
    year_starts_array = np.asarray(year_starts, dtype="datetime64[D]")

    def sample(rng: np.random.Generator) -> pd.Series:
        choices = np.floor(rng.random(len(eligible_lengths)) * eligible_lengths).astype(int)
        shifts = eligible_matrix[np.arange(len(eligible_lengths)), choices]
        sampled = np.empty(len(observed), dtype="datetime64[D]")
        for group_index, (indices, doys) in enumerate(zip(indices_by_group, doys_by_group, strict=True)):
            sampled[indices] = year_starts_array[group_index] + (doys + shifts[group_index] - 1).astype("timedelta64[D]")
        return pd.Series(sampled.astype("datetime64[ns]"))

    return sample


def holm_adjust_pvalues(p_values: Sequence[float]) -> np.ndarray:
    values = np.asarray(p_values, dtype=float)
    adjusted = np.full(values.shape, np.nan, dtype=float)
    valid_indices = np.flatnonzero(np.isfinite(values))
    if valid_indices.size == 0:
        return adjusted
    valid_values = values[valid_indices]
    if np.any((valid_values < 0.0) | (valid_values > 1.0)):
        raise ValueError("P-values must be between 0 and 1.")

    order = np.argsort(valid_values)
    sorted_values = valid_values[order]
    factors = valid_indices.size - np.arange(valid_indices.size)
    sorted_adjusted = np.maximum.accumulate(factors * sorted_values).clip(max=1.0)
    adjusted[valid_indices[order]] = sorted_adjusted
    return adjusted

OMNI_COLUMN_NAMES = [
    "year",
    "doy",
    "hour",
    "bartels_rotation",
    "imf_sc_id",
    "plasma_sc_id",
    "imf_points",
    "plasma_points",
    "f_scalar",
    "b_mag",
    "lat_avg_field",
    "lon_avg_field",
    "bx_gse",
    "by_gse",
    "bz_gse",
    "by_gsm",
    "bz_gsm",
    "sigma_b_mag",
    "sigma_b",
    "sigma_bx",
    "sigma_by",
    "sigma_bz",
    "proton_temp",
    "proton_density",
    "speed",
    "flow_longitude",
    "flow_latitude",
    "alpha_proton_ratio",
    "flow_pressure",
    "sigma_temp",
    "sigma_density",
    "sigma_speed",
    "sigma_flow_longitude",
    "sigma_flow_latitude",
    "sigma_alpha_proton_ratio",
    "electric_field",
    "plasma_beta",
    "alfven_mach",
    "kp_x10",
    "sunspot_number",
    "dst",
    "ae",
    "pflux_gt1",
    "pflux_gt2",
    "pflux_gt4",
    "pflux_gt10",
    "pflux_gt30",
    "pflux_gt60",
    "magnetosphere_flux_flag",
    "ap",
    "f107",
    "pcn",
    "al",
    "au",
    "magnetosonic_mach",
    "lyman_alpha",
    "proton_qi",
]

OMNI_FILL_LIMITS = {
    "f_scalar": 999.0,
    "b_mag": 999.0,
    "bx_gse": 999.0,
    "by_gse": 999.0,
    "bz_gse": 999.0,
    "by_gsm": 999.0,
    "bz_gsm": 999.0,
    "sigma_bz": 999.0,
    "proton_temp": 9_999_999.0,
    "proton_density": 999.0,
    "speed": 9999.0,
    "flow_pressure": 99.99,
    "electric_field": 999.99,
    "plasma_beta": 999.99,
    "alfven_mach": 999.9,
    "kp_x10": 99,
    "dst": 99999,
    "ae": 99999,
    "ap": 999,
    "f107": 999.9,
    "pcn": 999.9,
    "al": 99999,
    "au": 99999,
    "magnetosonic_mach": 99.9,
    "lyman_alpha": 0.999999,
    "proton_qi": 9.9999,
}


def load_config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def make_logger(name: str):
    return common_make_logger(name)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def find_files(patterns: Sequence[str]) -> list[Path]:
    hits: list[Path] = []
    for pattern in patterns:
        hits.extend(ROOT.glob(pattern))
    unique = sorted({path.resolve() for path in hits if path.is_file()})
    return unique


def find_one(patterns: Sequence[str], required: bool = True) -> Path | None:
    matches = find_files(patterns)
    if matches:
        return matches[0]
    if required:
        raise FileNotFoundError(f"No files found for patterns: {patterns}")
    return None


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def write_dataframe(df: pd.DataFrame, rel_stem: str) -> dict[str, str]:
    base = ROOT / rel_stem
    ensure_parent(base)
    csv_path = base.with_suffix(".csv")
    df.to_csv(csv_path, index=False)
    outputs = {"csv": str(csv_path.relative_to(ROOT))}

    parquet_path = base.with_suffix(".parquet")
    try:
        df.to_parquet(parquet_path, index=False)
        outputs["parquet"] = str(parquet_path.relative_to(ROOT))
    except Exception:
        outputs["parquet"] = "not-written"
    return outputs


def save_figure(fig: plt.Figure, rel_stem: str) -> dict[str, str]:
    base = ROOT / rel_stem
    ensure_parent(base)
    png_path = base.with_suffix(".png")
    svg_path = base.with_suffix(".svg")
    fig.savefig(png_path, dpi=180, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)
    return {"png": str(png_path.relative_to(ROOT)), "svg": str(svg_path.relative_to(ROOT))}


def manifest_payload(
    script_name: str,
    inputs: Sequence[Path | str],
    outputs: Sequence[Path | str] | dict[str, Any],
    metrics: dict[str, Any],
    assumptions: Sequence[str] | None = None,
) -> dict[str, Any]:
    normalized_inputs = [str(Path(p).relative_to(ROOT)) if isinstance(p, Path) and p.is_absolute() else str(p) for p in inputs]
    payload = {
        "script": script_name,
        "inputs": normalized_inputs,
        "outputs": outputs,
        "metrics": metrics,
        "assumptions": list(assumptions or []),
        "generated_at": utc_now(),
        "ok": True,
    }
    return payload


def write_script_manifest(
    script_name: str,
    inputs: Sequence[Path | str],
    outputs: Sequence[Path | str] | dict[str, Any],
    metrics: dict[str, Any],
    assumptions: Sequence[str] | None = None,
    ok: bool = True,
) -> Path:
    payload = manifest_payload(script_name, inputs, outputs, metrics, assumptions)
    payload["ok"] = ok
    return write_manifest(script_name.replace(".py", ""), payload)


def parse_omni_hourly(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        sep=r"\s+",
        header=None,
        names=OMNI_COLUMN_NAMES,
        engine="c",
    )
    for column, fill_limit in OMNI_FILL_LIMITS.items():
        if column in df.columns:
            df.loc[df[column] >= fill_limit, column] = np.nan

    dt = pd.to_datetime(df["year"].astype(int).astype(str), format="%Y")
    dt = dt + pd.to_timedelta(df["doy"].astype(int) - 1, unit="D") + pd.to_timedelta(df["hour"].astype(int), unit="h")
    df["datetime_utc"] = dt.dt.tz_localize("UTC")
    df["date"] = df["datetime_utc"].dt.date.astype("string")
    return df


def daily_summary(df: pd.DataFrame, aggregations: dict[str, Any]) -> pd.DataFrame:
    tmp = df.copy()
    tmp["date"] = pd.to_datetime(tmp["date"])
    out = tmp.groupby("date", as_index=False).agg(aggregations)
    out["year"] = out["date"].dt.year
    out["month"] = out["date"].dt.month
    out["doy"] = out["date"].dt.dayofyear
    return out


def build_event_window(
    daily_df: pd.DataFrame,
    event_dates: Sequence[pd.Timestamp],
    metrics: Sequence[str],
    window_days: int,
    date_col: str = "date",
) -> pd.DataFrame:
    if not event_dates:
        return pd.DataFrame(columns=["lag", "event_count", *metrics])

    indexed = daily_df.copy()
    indexed[date_col] = pd.to_datetime(indexed[date_col])
    indexed = indexed.set_index(date_col).sort_index()
    rows: list[dict[str, Any]] = []

    for lag in range(-window_days, window_days + 1):
        values = []
        for event_date in event_dates:
            target = pd.Timestamp(event_date).normalize() + pd.Timedelta(days=lag)
            if target in indexed.index:
                values.append(indexed.loc[target, list(metrics)])
        if values:
            block = pd.DataFrame(values)
            row = {"lag": lag, "event_count": len(values)}
            for metric in metrics:
                row[metric] = float(block[metric].mean())
            rows.append(row)
    return pd.DataFrame(rows)


def add_cumulative_columns(df: pd.DataFrame, metrics: Sequence[str]) -> pd.DataFrame:
    out = df.copy()
    out = out.sort_values("lag")
    for metric in metrics:
        out[f"{metric}_cumulative"] = out[metric] * out["event_count"]
    return out


def random_dates_like(
    events: Sequence[pd.Timestamp],
    date_index: pd.DatetimeIndex,
    rng: np.random.Generator,
) -> list[pd.Timestamp]:
    usable = date_index.to_series().sort_values().tolist()
    draw = rng.choice(len(usable), size=len(events), replace=False)
    return [pd.Timestamp(usable[i]).normalize() for i in draw]


def season_matched_random_dates(
    events: Sequence[pd.Timestamp],
    date_index: pd.DatetimeIndex,
    season_window_days: int,
    rng: np.random.Generator,
) -> list[pd.Timestamp]:
    return season_matched_random_sampler(events, date_index, season_window_days)(rng)


def season_matched_random_sampler(
    events: Sequence[pd.Timestamp],
    date_index: pd.DatetimeIndex,
    season_window_days: int,
) -> Callable[[np.random.Generator], list[pd.Timestamp]]:
    available = pd.DatetimeIndex(date_index.normalize()).sort_values()
    available_years = available.year.to_numpy(dtype=int)
    available_doys = available.dayofyear.to_numpy(dtype=int)
    pool_starts = np.empty(len(events), dtype=int)
    pool_sizes = np.empty(len(events), dtype=int)
    irregular_pools: dict[int, np.ndarray] = {}

    for index, value in enumerate(events):
        event = pd.Timestamp(value).normalize()
        year_start = int(np.searchsorted(available_years, event.year, side="left"))
        year_end = int(np.searchsorted(available_years, event.year, side="right"))
        if year_start < year_end:
            same_year_doys = available_doys[year_start:year_end]
            pool_start = year_start + int(np.searchsorted(same_year_doys, event.dayofyear - season_window_days, side="left"))
            pool_end = year_start + int(np.searchsorted(same_year_doys, event.dayofyear + season_window_days, side="right"))
            if pool_start == pool_end:
                pool_start, pool_end = year_start, year_end
            pool_starts[index] = pool_start
            pool_sizes[index] = pool_end - pool_start
        else:
            pool = np.flatnonzero(np.abs(available_doys - event.dayofyear) <= season_window_days)
            if pool.size == 0:
                pool = np.arange(len(available), dtype=int)
            irregular_pools[index] = pool
            pool_starts[index] = 0
            pool_sizes[index] = pool.size

    available_values = available.to_numpy(dtype="datetime64[ns]")

    def sample(rng: np.random.Generator) -> list[pd.Timestamp]:
        offsets = np.floor(rng.random(len(events)) * pool_sizes).astype(int)
        indices = pool_starts + offsets
        for event_index, pool in irregular_pools.items():
            indices[event_index] = int(rng.choice(pool))
        return [pd.Timestamp(date) for date in available_values[indices]]

    return sample


def empirical_pvalue(observed: float, null_values: Iterable[float]) -> float:
    arr = np.asarray(list(null_values), dtype=float)
    if arr.size == 0:
        return float("nan")
    return float((1 + np.sum(np.abs(arr) >= abs(observed))) / (arr.size + 1))


def null_tail_probabilities(observed: np.ndarray, draws: np.ndarray) -> dict[str, np.ndarray]:
    observed = np.asarray(observed, dtype=float)
    draws = np.asarray(draws, dtype=float)
    if draws.ndim != 2 or draws.shape[1:] != observed.shape or not len(draws):
        raise ValueError("Null draws must have shape (replicates, observed lags).")
    if not np.isfinite(draws).all() or not np.isfinite(observed).all():
        raise ValueError("Observed statistics and null draws must be finite.")
    upper = (1 + (draws >= observed).sum(axis=0)) / (len(draws) + 1)
    lower = (1 + (draws <= observed).sum(axis=0)) / (len(draws) + 1)
    return {
        "p_value_one_sided": upper,
        "p_value_two_sided": np.minimum(1.0, 2 * np.minimum(upper, lower)),
        "null_iterations": np.full(observed.shape, len(draws), dtype=int),
    }


def complete_window_dates(
    events: Sequence[pd.Timestamp], date_index: pd.DatetimeIndex, window_days: int
) -> list[pd.Timestamp]:
    dates = pd.DatetimeIndex(date_index).normalize()
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("Daily dates must be unique and increasing.")
    if len(dates) < 2 * window_days + 1 or not (dates[1:] - dates[:-1] == pd.Timedelta(days=1)).all():
        raise ValueError("Complete windows require a contiguous daily calendar of sufficient length.")
    parsed = pd.DatetimeIndex(pd.to_datetime(events, utc=True, errors="coerce", format="mixed")).tz_convert(None)
    parsed = parsed.dropna().normalize().unique().sort_values()
    return parsed[(parsed >= dates[window_days]) & (parsed <= dates[-window_days - 1])].tolist()


def nearest_event_differences(left: Sequence[pd.Timestamp], right: Sequence[pd.Timestamp]) -> pd.DataFrame:
    right_ts = (
        pd.to_datetime(pd.Series(right), utc=True, errors="coerce")
        .dt.tz_convert(None)
        .dropna()
        .sort_values()
        .reset_index(drop=True)
    )
    rows: list[dict[str, Any]] = []
    left_ts = (
        pd.to_datetime(pd.Series(left), utc=True, errors="coerce")
        .dt.tz_convert(None)
        .dropna()
        .sort_values()
    )
    for event in left_ts:
        if right_ts.empty:
            rows.append({"event": event, "nearest_event": pd.NaT, "delta_days": np.nan})
            continue
        deltas = (right_ts - event).dt.total_seconds() / 86400.0
        idx = deltas.abs().idxmin()
        rows.append({"event": event, "nearest_event": right_ts.iloc[idx], "delta_days": float(deltas.iloc[idx])})
    return pd.DataFrame(rows)


def day_of_year_features(dates: pd.Series) -> pd.DataFrame:
    doy = pd.to_datetime(dates).dt.dayofyear
    angle = 2.0 * math.pi * doy / 365.25
    return pd.DataFrame({
        "sin_doy": np.sin(angle),
        "cos_doy": np.cos(angle),
    })


def within_days_indicator(index_dates: pd.Series, event_dates: Sequence[pd.Timestamp], days: int) -> pd.Series:
    event_set = (
        pd.to_datetime(pd.Series(event_dates), utc=True, errors="coerce")
        .dt.tz_convert(None)
        .dt.normalize()
        .dropna()
        .tolist()
    )
    index_series = pd.to_datetime(index_dates, errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
    flags = pd.Series(False, index=index_series.index)
    for event in event_set:
        delta = (index_series - event).dt.days.abs()
        flags = flags | (delta <= days)
    return flags.astype(int)


def dataset_sha256(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return sha256_file(path)
