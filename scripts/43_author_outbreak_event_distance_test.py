from __future__ import annotations

from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _utils import parse_supplement_date_range, year_month_cluster_shift_sampler, year_month_matched_sampler, year_season_cluster_shift_sampler
from _outbreak_inference import ITERATIONS, distance_summary


ROOT = Path(__file__).resolve().parents[1]
OUTBREAKS_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_outbreaks.csv"
ANALYSIS_DAILY_PATH = ROOT / "data" / "derived" / "daily" / "analysis_daily.csv"
OMNI_DAILY_PATH = ROOT / "data" / "derived" / "daily" / "omni_daily.csv"
AUTHOR_HCS_PATH = ROOT / "data" / "derived" / "catalogs" / "author_hcs_catalog.csv"
RECON_HCS_PATH = ROOT / "data" / "derived" / "catalogs" / "hcs_from_omni.csv"

CIR_OUT_PATH = ROOT / "data" / "derived" / "catalogs" / "cir_arrival_catalog.csv"
ICME_OUT_PATH = ROOT / "data" / "derived" / "catalogs" / "icme_impact_catalog_for_outbreak_tests.csv"
HSS_DECLINE_OUT_PATH = ROOT / "data" / "derived" / "catalogs" / "major_hss_declining_phase_catalog.csv"

DISTANCE_TABLE_PATH = ROOT / "data" / "derived" / "tables" / "author_outbreak_nearest_event_distances.csv"
NULL_SUMMARY_PATH = ROOT / "data" / "derived" / "tables" / "author_outbreak_event_distance_null_summary.csv"
FIG_NULL_PATH = ROOT / "data" / "derived" / "figures" / "author_outbreak_distance_null_comparison.png"
FIG_DIST_PATH = ROOT / "data" / "derived" / "figures" / "author_outbreak_distance_distributions.png"
REPORT_PATH = ROOT / "data" / "derived" / "reports" / "author_outbreak_event_distance_test.md"

RNG_SEED = 20260316
NULL_ITERATIONS = ITERATIONS
MAJOR_HSS_PEAK_THRESHOLD = 600.0
HSS_DECLINE_MIN_DAYS = 1
HSS_DECLINE_MAX_DAYS = 4
SEASON_CLUSTER_SHIFT_DAYS = 15

MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_RANGE_RE = re.compile(rf"(?P<left>{MONTH_RE}\.?\s+\d{{1,2}})\s*[\-–]\s*(?P<right>\d{{1,2}}\s*{MONTH_RE}\.?|{MONTH_RE}\.?\s+\d{{1,2}})", re.IGNORECASE)
SINGLE_DATE_RE = re.compile(rf"(?P<d>{MONTH_RE}\.?\s+\d{{1,2}})\s*(?P<y>\d{{4}})", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")

EVENT_FAMILY_ORDER = [
    "HCS_author_catalog",
    "HCS_reconstructed_catalog",
    "CIR_arrival_catalog",
    "ICME_impact_catalog",
    "major_HSS_declining_phase_catalog",
]


def parse_date_text(date_text: object) -> tuple[pd.Timestamp | pd.NaT, pd.Timestamp | pd.NaT]:
    return parse_supplement_date_range(date_text)


def normalize_author_type(value: object) -> str:
    txt = str(value or "").strip().upper()
    if txt in {"A", "B", "C", "D"}:
        return txt
    if txt in {"A*", "B*", "C*", "D*"}:
        return txt[0]
    return "unknown"


def load_outbreaks(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing outbreak input: {path}")

    out = pd.read_csv(path)
    out = out.reset_index(drop=True)
    if "outbreak_id" not in out.columns:
        out["outbreak_id"] = np.arange(1, len(out) + 1, dtype=int)

    start = pd.to_datetime(out.get("outbreak_date_start"), errors="coerce")
    end = pd.to_datetime(out.get("outbreak_date_end"), errors="coerce")

    missing_mask = start.isna() | (end.isna() & out.get("outbreak_date_text", pd.Series(dtype=object)).astype(str).str.strip().ne(""))
    parsed_starts: list[pd.Timestamp | pd.NaT] = []
    parsed_ends: list[pd.Timestamp | pd.NaT] = []
    for txt in out.get("outbreak_date_text", pd.Series(dtype=object)):
        s, e = parse_date_text(txt)
        parsed_starts.append(s)
        parsed_ends.append(e)

    parsed_start_series = pd.to_datetime(pd.Series(parsed_starts), errors="coerce")
    parsed_end_series = pd.to_datetime(pd.Series(parsed_ends), errors="coerce")

    start = start.where(~start.isna(), parsed_start_series)
    end = end.where(~end.isna(), parsed_end_series)
    end = end.where(~end.isna(), start)

    out["outbreak_start_date"] = start.dt.normalize()
    out["outbreak_end_date"] = end.dt.normalize()
    out["outbreak_anchor_date"] = out["outbreak_start_date"]
    out["author_type_normalized"] = out.get("author_type", pd.Series(dtype=object)).map(normalize_author_type)
    return out


def load_catalog_dates(path: Path, candidate_cols: list[str]) -> pd.Series:
    if not path.exists():
        return pd.Series(dtype="datetime64[ns]")
    df = pd.read_csv(path)
    for col in candidate_cols:
        if col in df.columns:
            dt = pd.to_datetime(df[col], errors="coerce").dropna().dt.normalize()
            if not dt.empty:
                return dt.drop_duplicates().sort_values().reset_index(drop=True)
    return pd.Series(dtype="datetime64[ns]")


def derive_cir_catalog(omni: pd.DataFrame) -> pd.DataFrame:
    tmp = omni.copy()
    tmp["speed_jump"] = tmp["speed_mean"].diff()
    cir = tmp.loc[
        (tmp["speed_mean"] >= 500.0)
        & (tmp["speed_jump"] >= 80.0)
        & (
            (tmp["proton_density_mean"] >= 8.0)
            | (tmp["b_mag_mean"] >= 8.0)
            | (tmp["flow_pressure_mean"] >= 2.5)
        ),
        ["date", "speed_mean", "speed_jump", "proton_density_mean", "b_mag_mean", "flow_pressure_mean"],
    ].copy()
    cir["event_type"] = "cir_arrival_proxy"
    cir["rule"] = "speed_mean>=500 and speed jump>=80 km/s with compression signature (density>=8 or |B|>=8 or pressure>=2.5)."
    cir = cir.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return cir


def derive_icme_catalog(omni: pd.DataFrame) -> pd.DataFrame:
    icme = omni.loc[
        (omni["b_mag_mean"] >= 10.0) & (omni["speed_mean"] >= 450.0) & (omni["dst_mean"] <= -50.0),
        ["date", "b_mag_mean", "speed_mean", "dst_mean"],
    ].copy()
    if icme.empty:
        icme["event_type"] = []
        icme["rule"] = []
        return icme
    icme["gap"] = icme["date"].diff().dt.days.fillna(99)
    icme = icme.loc[icme["gap"] > 1].copy()
    icme["event_type"] = "icme_impact_proxy"
    icme["rule"] = "|B|>=10 nT and speed>=450 km/s and Dst<=-50 nT; clustered days collapsed by requiring >1-day separation."
    return icme.drop(columns=["gap"]).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)


def derive_major_hss_decline_catalog(omni: pd.DataFrame) -> pd.DataFrame:
    speed = omni["speed_mean"].to_numpy(dtype=float)
    peak_dates: list[pd.Timestamp] = []
    for i in range(1, len(omni) - 1):
        if not np.isfinite(speed[i]):
            continue
        if speed[i] >= MAJOR_HSS_PEAK_THRESHOLD and speed[i] >= speed[i - 1] and speed[i] >= speed[i + 1]:
            peak_dates.append(pd.Timestamp(omni.iloc[i]["date"]).normalize())

    if not peak_dates:
        return pd.DataFrame(columns=["date", "peak_date", "peak_speed", "event_type", "rule"])

    peak_dates = sorted(set(peak_dates))
    records: list[dict[str, object]] = []
    omni_idx = omni.set_index("date")
    for peak in peak_dates:
        peak_speed = float(omni_idx.loc[peak, "speed_mean"]) if peak in omni_idx.index and pd.notna(omni_idx.loc[peak, "speed_mean"]) else np.nan
        for d in range(HSS_DECLINE_MIN_DAYS, HSS_DECLINE_MAX_DAYS + 1):
            day = peak + pd.Timedelta(days=d)
            if day not in omni_idx.index:
                continue
            now_speed = omni_idx.loc[day, "speed_mean"]
            if pd.isna(now_speed) or pd.isna(peak_speed):
                continue
            if float(now_speed) <= peak_speed:
                records.append(
                    {
                        "date": day,
                        "peak_date": peak,
                        "peak_speed": peak_speed,
                        "event_type": "major_hss_declining_phase_day",
                        "rule": f"major HSS peak >= {MAJOR_HSS_PEAK_THRESHOLD} km/s, then include +{HSS_DECLINE_MIN_DAYS}..+{HSS_DECLINE_MAX_DAYS} days with non-increasing speed.",
                    }
                )

    out = pd.DataFrame(records)
    if out.empty:
        return pd.DataFrame(columns=["date", "peak_date", "peak_speed", "event_type", "rule"])
    out = out.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return out


def get_event_catalogs(omni: pd.DataFrame) -> tuple[dict[str, pd.Series], dict[str, str], list[str]]:
    notes: list[str] = []
    status: dict[str, str] = {}

    hcs_author = load_catalog_dates(AUTHOR_HCS_PATH, ["date", "datetime_utc"])
    hcs_recon = load_catalog_dates(RECON_HCS_PATH, ["date"])

    cir_candidates = [
        ROOT / "data" / "derived" / "catalogs" / "cir_arrival_catalog.csv",
        ROOT / "data" / "derived" / "catalogs" / "cir_proxy_catalog.csv",
    ]
    cir_dates = pd.Series(dtype="datetime64[ns]")
    used_cir_file: Path | None = None
    for p in cir_candidates:
        cir_dates = load_catalog_dates(p, ["date", "analysis_date"])
        if not cir_dates.empty:
            used_cir_file = p
            break
    if cir_dates.empty:
        cir_df = derive_cir_catalog(omni)
        cir_df.to_csv(CIR_OUT_PATH, index=False)
        cir_dates = pd.to_datetime(cir_df["date"], errors="coerce").dropna().dt.normalize().reset_index(drop=True)
        status["CIR_arrival_catalog"] = "reconstructed"
        notes.append(f"CIR catalog reconstructed and saved to {CIR_OUT_PATH.relative_to(ROOT)}.")
    else:
        status["CIR_arrival_catalog"] = f"detected:{used_cir_file.relative_to(ROOT)}"

    icme_candidates = [
        ROOT / "data" / "derived" / "catalogs" / "icme_catalog.csv",
    ]
    icme_dates = pd.Series(dtype="datetime64[ns]")
    used_icme_file: Path | None = None
    for p in icme_candidates:
        icme_dates = load_catalog_dates(p, ["analysis_date", "date", "storm_start_date"])
        if not icme_dates.empty:
            used_icme_file = p
            break
    if icme_dates.empty:
        raise ValueError("Direct ICME catalog required; run script 14. Proxy fallback is not permitted.")
    else:
        status["ICME_impact_catalog"] = f"detected:{used_icme_file.relative_to(ROOT)}"

    hss_candidates = [
        ROOT / "data" / "derived" / "catalogs" / "major_hss_declining_phase_catalog.csv",
    ]
    hss_decline_dates = pd.Series(dtype="datetime64[ns]")
    used_hss_file: Path | None = None
    for p in hss_candidates:
        hss_decline_dates = load_catalog_dates(p, ["date", "analysis_date"])
        if not hss_decline_dates.empty:
            used_hss_file = p
            break
    if hss_decline_dates.empty:
        hss_df = derive_major_hss_decline_catalog(omni)
        hss_df.to_csv(HSS_DECLINE_OUT_PATH, index=False)
        hss_decline_dates = pd.to_datetime(hss_df.get("date", pd.Series(dtype=object)), errors="coerce").dropna().dt.normalize().reset_index(drop=True)
        status["major_HSS_declining_phase_catalog"] = "reconstructed"
        notes.append(f"Major-HSS declining-phase catalog reconstructed and saved to {HSS_DECLINE_OUT_PATH.relative_to(ROOT)}.")
    else:
        status["major_HSS_declining_phase_catalog"] = f"detected:{used_hss_file.relative_to(ROOT)}"

    status["HCS_author_catalog"] = "detected:data/derived/catalogs/author_hcs_catalog.csv" if not hcs_author.empty else "missing"
    status["HCS_reconstructed_catalog"] = "detected:data/derived/catalogs/hcs_from_omni.csv" if not hcs_recon.empty else "missing"

    catalogs = {
        "HCS_author_catalog": hcs_author,
        "HCS_reconstructed_catalog": hcs_recon,
        "CIR_arrival_catalog": cir_dates,
        "ICME_impact_catalog": icme_dates,
        "major_HSS_declining_phase_catalog": hss_decline_dates,
    }
    return catalogs, status, notes


def nearest_signed_distance(anchor: pd.Timestamp, events: pd.Series) -> tuple[pd.Timestamp | pd.NaT, float, float]:
    if pd.isna(anchor) or events.empty:
        return pd.NaT, np.nan, np.nan
    deltas = (events - anchor).dt.days.astype(float)
    if deltas.empty:
        return pd.NaT, np.nan, np.nan
    abs_deltas = np.abs(deltas.to_numpy(dtype=float))
    idx = int(np.argmin(abs_deltas))
    nearest = events.iloc[idx]
    signed = float(deltas.iloc[idx])
    return nearest, signed, abs(signed)


def nearest_signed_distance_range(start: pd.Timestamp, end: pd.Timestamp, events: pd.Series) -> tuple[pd.Timestamp | pd.NaT, float, float]:
    if pd.isna(start) or events.empty:
        return pd.NaT, np.nan, np.nan
    if pd.isna(end):
        end = start
    days = pd.date_range(start=start, end=end, freq="D")
    best_event = pd.NaT
    best_signed = np.nan
    best_abs = np.nan
    for day in days:
        event, signed, absd = nearest_signed_distance(day, events)
        if pd.isna(event):
            continue
        if np.isnan(best_abs) or absd < best_abs:
            best_event = event
            best_signed = signed
            best_abs = absd
    return best_event, best_signed, best_abs


def build_distance_table(outbreaks: pd.DataFrame, catalogs: dict[str, pd.Series]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in outbreaks.itertuples(index=False):
        outbreak_id = int(row.outbreak_id)
        anchor = pd.to_datetime(row.outbreak_anchor_date, errors="coerce")
        start = pd.to_datetime(row.outbreak_start_date, errors="coerce")
        end = pd.to_datetime(row.outbreak_end_date, errors="coerce")
        author_type = str(row.author_type_normalized)

        for family in EVENT_FAMILY_ORDER:
            events = catalogs.get(family, pd.Series(dtype="datetime64[ns]"))
            if family == "ICME_impact_catalog" and anchor < pd.Timestamp("1996-01-01"):
                continue

            nearest, signed, absd = nearest_signed_distance(anchor, events)
            rows.append(
                {
                    "outbreak_id": outbreak_id,
                    "outbreak_anchor_date": "" if pd.isna(anchor) else str(anchor.date()),
                    "author_type_normalized": author_type,
                    "event_family": family,
                    "nearest_event_date": "" if pd.isna(nearest) else str(pd.Timestamp(nearest).date()),
                    "signed_days_to_nearest_event": signed,
                    "absolute_days_to_nearest_event": absd,
                    "matching_mode": "anchor_start_date_primary",
                    "notes": "Primary analysis uses outbreak start date as anchor.",
                }
            )

            nearest_s, signed_s, absd_s = nearest_signed_distance_range(start, end, events)
            rows.append(
                {
                    "outbreak_id": outbreak_id,
                    "outbreak_anchor_date": "" if pd.isna(anchor) else str(anchor.date()),
                    "author_type_normalized": author_type,
                    "event_family": family,
                    "nearest_event_date": "" if pd.isna(nearest_s) else str(pd.Timestamp(nearest_s).date()),
                    "signed_days_to_nearest_event": signed_s,
                    "absolute_days_to_nearest_event": absd_s,
                    "matching_mode": "any_day_within_outbreak_range_sensitivity",
                    "notes": "Sensitivity analysis: nearest event to any day within outbreak start-end range.",
                }
            )
    return pd.DataFrame(rows)


def compute_abs_distances(dates: pd.Series, events: pd.Series) -> np.ndarray:
    event_days = pd.DatetimeIndex(pd.to_datetime(events, errors="coerce")).dropna().normalize().to_numpy(dtype="datetime64[D]").astype(np.int64)
    date_days = pd.DatetimeIndex(pd.to_datetime(dates, errors="coerce")).dropna().normalize().to_numpy(dtype="datetime64[D]").astype(np.int64)
    if event_days.size == 0 or date_days.size == 0:
        return np.asarray([], dtype=float)

    insertion = np.searchsorted(event_days, date_days)
    left_positions = np.clip(insertion - 1, 0, len(event_days) - 1)
    right_positions = np.clip(insertion, 0, len(event_days) - 1)
    left_distance = np.abs(date_days - event_days[left_positions])
    right_distance = np.abs(event_days[right_positions] - date_days)
    return np.minimum(left_distance, right_distance).astype(float)


def run_null_distance_test(outbreaks: pd.DataFrame, catalogs: dict[str, pd.Series], valid_dates: pd.Series) -> pd.DataFrame:
    return distance_summary(outbreaks["outbreak_anchor_date"], catalogs, valid_dates)


def make_figures(distance_table: pd.DataFrame, null_summary: pd.DataFrame) -> None:
    primary = distance_table.loc[distance_table["matching_mode"] == "anchor_start_date_primary"].copy()

    fig1, ax1 = plt.subplots(figsize=(10.5, 5.4))
    x = np.arange(len(EVENT_FAMILY_ORDER))
    observed = [
        float(null_summary.loc[null_summary["event_family"] == fam, "observed_mean_abs_distance"].iloc[0])
        if not null_summary.loc[null_summary["event_family"] == fam].empty
        else np.nan
        for fam in EVENT_FAMILY_ORDER
    ]
    lower = [
        float(null_summary.loc[null_summary["event_family"] == fam, "null_q025"].iloc[0])
        if not null_summary.loc[null_summary["event_family"] == fam].empty
        else np.nan
        for fam in EVENT_FAMILY_ORDER
    ]
    upper = [
        float(null_summary.loc[null_summary["event_family"] == fam, "null_q975"].iloc[0])
        if not null_summary.loc[null_summary["event_family"] == fam].empty
        else np.nan
        for fam in EVENT_FAMILY_ORDER
    ]
    ax1.plot(x, observed, marker="o", color="black", label="Observed mean abs distance")
    ax1.fill_between(x, lower, upper, color="0.8", label="Null 2.5-97.5%")
    ax1.set_xticks(x)
    ax1.set_xticklabels(EVENT_FAMILY_ORDER, rotation=25, ha="right")
    ax1.set_ylabel("Days")
    ax1.set_title("Author outbreaks: mean absolute distance to nearest event vs null")
    ax1.legend(loc="best")
    fig1.tight_layout()
    FIG_NULL_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig1.savefig(FIG_NULL_PATH, dpi=300, bbox_inches="tight")
    plt.close(fig1)

    fig2, ax2 = plt.subplots(figsize=(10.5, 5.4))
    values = []
    labels = []
    for fam in EVENT_FAMILY_ORDER:
        fam_vals = primary.loc[primary["event_family"] == fam, "absolute_days_to_nearest_event"].to_numpy(dtype=float)
        fam_vals = fam_vals[np.isfinite(fam_vals)]
        values.append(fam_vals)
        labels.append(fam)
    ax2.boxplot(values, labels=labels, showfliers=False)
    ax2.set_ylabel("Absolute days to nearest event")
    ax2.set_title("Distribution of primary outbreak-event distances")
    plt.setp(ax2.get_xticklabels(), rotation=25, ha="right")
    fig2.tight_layout()
    fig2.savefig(FIG_DIST_PATH, dpi=300, bbox_inches="tight")
    plt.close(fig2)


def write_report(outbreaks: pd.DataFrame, status: dict[str, str], catalog_notes: list[str], null_summary: pd.DataFrame) -> None:
    lines = [
        "# Author Outbreak Event Distance Test",
        "",
        "Primary analysis: outbreak_anchor_date = outbreak_start_date.",
        "Sensitivity-only analysis: nearest event to any day within outbreak_start_date..outbreak_end_date.",
        "",
        f"- Null iterations: {NULL_ITERATIONS}",
        f"- Random seed: {RNG_SEED}",
        f"- Outbreak rows analyzed: {len(outbreaks)}",
        "- Null dates preserve each outbreak's year and month; dates are sampled without replacement within year-month strata when possible.",
        "- Cluster-preserving sensitivity circularly shifts each year-month outbreak-day pattern as a unit, preserving monthly counts and cyclic within-month spacing; cross-month clusters are not preserved.",
        f"- Season-aware cluster sensitivity shifts each year's entire outbreak pattern by a shared offset within +/-{SEASON_CLUSTER_SHIFT_DAYS} days, preserving within-year cluster spacing across month boundaries.",
        "- This outbreak-list analysis is exploratory. P-values here are nominal; the combined summary Holm-adjusts all 87 tests across three null designs.",
        "",
        "## Event Catalog Status",
    ]
    for fam in EVENT_FAMILY_ORDER:
        lines.append(f"- {fam}: {status.get(fam, 'unknown')}")

    lines.extend(
        [
            "",
            "## Reconstruction Rules",
            "- CIR arrival proxy: speed >= 500 km/s and daily speed jump >= 80 km/s with compression signature (density >= 8 cm^-3 or |B| >= 8 nT or flow pressure >= 2.5 nPa).",
            "- ICME: direct catalog only, with outbreak starts and null dates restricted to 1996 onward; no proxy substitution.",
            f"- Major-HSS declining phase: local speed peak >= {MAJOR_HSS_PEAK_THRESHOLD:.0f} km/s, include +{HSS_DECLINE_MIN_DAYS}..+{HSS_DECLINE_MAX_DAYS} days where speed is <= peak speed.",
        ]
    )
    for n in catalog_notes:
        lines.append(f"- {n}")

    lines.extend(["", "## Null Comparison Summary"])
    if null_summary.empty:
        lines.append("- No summary rows generated.")
    else:
        for row in null_summary.itertuples(index=False):
            lines.append(
                f"- {row.event_family} (N={row.outbreak_count}): observed mean abs distance={row.observed_mean_abs_distance:.2f}; "
                f"independent year-month null mean={row.null_mean_abs_distance:.2f}, p={row.p_value_mean:.3f}; "
                f"month-cluster null mean={row.cluster_null_mean_abs_distance:.2f}, p={row.p_value_mean_cluster:.3f}; "
                f"year-season cluster null mean={row.season_cluster_null_mean_abs_distance:.2f}, "
                f"p={row.p_value_mean_season_cluster:.3f}; {row.interpretation}"
            )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    DISTANCE_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    NULL_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not ANALYSIS_DAILY_PATH.exists() or not OMNI_DAILY_PATH.exists():
        raise FileNotFoundError("Missing required daily files: analysis_daily.csv and/or omni_daily.csv")

    outbreaks = load_outbreaks(OUTBREAKS_PATH)
    outbreaks = outbreaks.loc[outbreaks["outbreak_anchor_date"].notna()].copy()

    analysis_daily = pd.read_csv(ANALYSIS_DAILY_PATH, parse_dates=["date"])
    valid_dates = pd.to_datetime(analysis_daily["date"], errors="coerce").dropna().dt.normalize()

    omni = pd.read_csv(OMNI_DAILY_PATH, parse_dates=["date"])
    omni["date"] = pd.to_datetime(omni["date"], errors="coerce").dt.normalize()
    omni = omni.dropna(subset=["date"]).reset_index(drop=True)

    catalogs, status, catalog_notes = get_event_catalogs(omni)
    catalogs = {key: dates[dates.between(valid_dates.min(), valid_dates.max())].reset_index(drop=True) for key, dates in catalogs.items()}
    catalog_notes.append("ICME distance and coincidence tests use the same direct catalog and exclude outbreak starts before 1996. All catalogs are restricted to the analysis calendar.")

    distance_table = build_distance_table(outbreaks, catalogs)
    distance_table.to_csv(DISTANCE_TABLE_PATH, index=False)

    null_summary = run_null_distance_test(outbreaks, catalogs, valid_dates)
    null_summary.to_csv(NULL_SUMMARY_PATH, index=False)

    make_figures(distance_table, null_summary)
    write_report(outbreaks, status, catalog_notes, null_summary)

    print(f"Saved: {DISTANCE_TABLE_PATH}")
    print(f"Saved: {NULL_SUMMARY_PATH}")
    print(f"Saved: {FIG_NULL_PATH}")
    print(f"Saved: {FIG_DIST_PATH}")
    print(f"Saved: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
