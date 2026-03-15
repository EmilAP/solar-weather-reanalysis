from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

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
        engine="python",
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
        out[f"{metric}_cumulative"] = out[metric].cumsum()
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
    available = pd.Series(date_index.normalize())
    matched: list[pd.Timestamp] = []
    for event in events:
        event = pd.Timestamp(event).normalize()
        same_year = available[available.dt.year == event.year]
        if same_year.empty:
            same_year = available
        distance = (same_year.dt.dayofyear - event.dayofyear).abs()
        pool = same_year[distance <= season_window_days]
        if pool.empty:
            pool = same_year
        matched.append(pd.Timestamp(pool.iloc[int(rng.integers(0, len(pool)))]))
    return matched


def empirical_pvalue(observed: float, null_values: Iterable[float]) -> float:
    arr = np.asarray(list(null_values), dtype=float)
    if arr.size == 0:
        return float("nan")
    return float((1 + np.sum(np.abs(arr) >= abs(observed))) / (arr.size + 1))


def nearest_event_differences(left: Sequence[pd.Timestamp], right: Sequence[pd.Timestamp]) -> pd.DataFrame:
    right_ts = pd.to_datetime(pd.Series(right)).sort_values().reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for event in pd.to_datetime(pd.Series(left)).sort_values():
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
    event_set = pd.to_datetime(pd.Series(event_dates)).dt.normalize().tolist()
    index_series = pd.to_datetime(index_dates).dt.normalize()
    flags = pd.Series(False, index=index_series.index)
    for event in event_set:
        delta = (index_series - event).dt.days.abs()
        flags = flags | (delta <= days)
    return flags.astype(int)


def dataset_sha256(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return sha256_file(path)
