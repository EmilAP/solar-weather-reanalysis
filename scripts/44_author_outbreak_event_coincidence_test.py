from __future__ import annotations

from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _utils import parse_supplement_date_range, year_month_cluster_shift_sampler, year_month_matched_sampler, year_season_cluster_shift_sampler
from _outbreak_inference import ITERATIONS, coincidence_summary


ROOT = Path(__file__).resolve().parents[1]
OUTBREAKS_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_outbreaks.csv"
ANALYSIS_DAILY_PATH = ROOT / "data" / "derived" / "daily" / "analysis_daily.csv"
OMNI_DAILY_PATH = ROOT / "data" / "derived" / "daily" / "omni_daily.csv"
AUTHOR_HCS_PATH = ROOT / "data" / "derived" / "catalogs" / "author_hcs_catalog.csv"
RECON_HCS_PATH = ROOT / "data" / "derived" / "catalogs" / "hcs_from_omni.csv"

CIR_PATH = ROOT / "data" / "derived" / "catalogs" / "cir_arrival_catalog.csv"
ICME_PATH = ROOT / "data" / "derived" / "catalogs" / "icme_catalog.csv"
HSS_DECLINE_PATH = ROOT / "data" / "derived" / "catalogs" / "major_hss_declining_phase_catalog.csv"

SUMMARY_PATH = ROOT / "data" / "derived" / "tables" / "author_outbreak_event_coincidence_summary.csv"
FIG_PATH = ROOT / "data" / "derived" / "figures" / "author_outbreak_event_coincidence_summary.png"
REPORT_PATH = ROOT / "data" / "derived" / "reports" / "author_outbreak_event_coincidence_test.md"

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


def parse_date_text(date_text: object) -> tuple[pd.Timestamp | pd.NaT, pd.Timestamp | pd.NaT]:
    return parse_supplement_date_range(date_text)


def load_outbreaks(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing outbreak input: {path}")
    out = pd.read_csv(path)
    out = out.reset_index(drop=True)
    if "outbreak_id" not in out.columns:
        out["outbreak_id"] = np.arange(1, len(out) + 1, dtype=int)

    start = pd.to_datetime(out.get("outbreak_date_start"), errors="coerce")
    end = pd.to_datetime(out.get("outbreak_date_end"), errors="coerce")

    parsed_starts = []
    parsed_ends = []
    for txt in out.get("outbreak_date_text", pd.Series(dtype=object)):
        s, e = parse_date_text(txt)
        parsed_starts.append(s)
        parsed_ends.append(e)

    start = start.where(~start.isna(), pd.to_datetime(pd.Series(parsed_starts), errors="coerce"))
    end = end.where(~end.isna(), pd.to_datetime(pd.Series(parsed_ends), errors="coerce"))
    end = end.where(~end.isna(), start)

    out["outbreak_start_date"] = pd.to_datetime(start, errors="coerce").dt.normalize()
    out["outbreak_end_date"] = pd.to_datetime(end, errors="coerce").dt.normalize()
    out["outbreak_anchor_date"] = out["outbreak_start_date"]
    return out


def load_catalog_dates(path: Path, cols: list[str]) -> pd.Series:
    if not path.exists():
        return pd.Series(dtype="datetime64[ns]")
    df = pd.read_csv(path)
    for c in cols:
        if c in df.columns:
            dt = pd.to_datetime(df[c], errors="coerce").dropna().dt.normalize()
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
    return cir.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)


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
    icme["rule"] = "|B|>=10 nT, speed>=450 km/s, Dst<=-50 nT with >1-day spacing."
    return icme.drop(columns=["gap"]).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)


def derive_major_hss_decline_catalog(omni: pd.DataFrame) -> pd.DataFrame:
    speed = omni["speed_mean"].to_numpy(dtype=float)
    peaks: list[pd.Timestamp] = []
    for i in range(1, len(omni) - 1):
        if not np.isfinite(speed[i]):
            continue
        if speed[i] >= MAJOR_HSS_PEAK_THRESHOLD and speed[i] >= speed[i - 1] and speed[i] >= speed[i + 1]:
            peaks.append(pd.Timestamp(omni.iloc[i]["date"]).normalize())

    records: list[dict[str, object]] = []
    if not peaks:
        return pd.DataFrame(columns=["date", "peak_date", "event_type", "rule"])

    peaks = sorted(set(peaks))
    omni_idx = omni.set_index("date")
    for peak in peaks:
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
                        "event_type": "major_hss_declining_phase_day",
                        "rule": f"peak>= {MAJOR_HSS_PEAK_THRESHOLD:.0f} km/s then days +{HSS_DECLINE_MIN_DAYS}..+{HSS_DECLINE_MAX_DAYS} with non-increasing speed",
                    }
                )

    out = pd.DataFrame(records)
    if out.empty:
        return pd.DataFrame(columns=["date", "peak_date", "event_type", "rule"])
    return out.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)


def build_catalogs(omni: pd.DataFrame) -> tuple[dict[str, pd.Series], dict[str, str], list[str]]:
    notes: list[str] = []
    status: dict[str, str] = {}

    hcs_author = load_catalog_dates(AUTHOR_HCS_PATH, ["date", "datetime_utc"])
    hcs_recon = load_catalog_dates(RECON_HCS_PATH, ["date"])
    status["HCS_author_catalog"] = "detected" if not hcs_author.empty else "missing"
    status["HCS_reconstructed_catalog"] = "detected" if not hcs_recon.empty else "missing"

    cir = load_catalog_dates(CIR_PATH, ["date", "analysis_date"])
    if cir.empty:
        cir_df = derive_cir_catalog(omni)
        cir_df.to_csv(CIR_PATH, index=False)
        cir = pd.to_datetime(cir_df["date"], errors="coerce").dropna().dt.normalize().reset_index(drop=True)
        status["CIR_arrival_catalog"] = "reconstructed"
        notes.append(f"Reconstructed CIR arrivals using OMNI speed-jump/compression rule; saved {CIR_PATH.relative_to(ROOT)}.")
    else:
        status["CIR_arrival_catalog"] = "detected"

    icme = load_catalog_dates(ICME_PATH, ["analysis_date", "date", "storm_start_date"])
    if icme.empty:
        raise ValueError("Direct ICME catalog required; run script 14. Proxy fallback is not permitted.")
    else:
        status["ICME_impact_catalog"] = "detected"

    hss = load_catalog_dates(HSS_DECLINE_PATH, ["date", "analysis_date"])
    if hss.empty:
        hss_df = derive_major_hss_decline_catalog(omni)
        hss_df.to_csv(HSS_DECLINE_PATH, index=False)
        hss = pd.to_datetime(hss_df.get("date", pd.Series(dtype=object)), errors="coerce").dropna().dt.normalize().reset_index(drop=True)
        status["major_HSS_declining_phase_catalog"] = "reconstructed"
        notes.append(f"Reconstructed major-HSS declining-phase dates from OMNI local speed peaks; saved {HSS_DECLINE_PATH.relative_to(ROOT)}.")
    else:
        status["major_HSS_declining_phase_catalog"] = "detected"

    catalogs = {
        "HCS_author_catalog": hcs_author,
        "HCS_reconstructed_catalog": hcs_recon,
        "CIR_arrival_catalog": cir,
        "ICME_impact_catalog": icme,
        "major_HSS_declining_phase_catalog": hss,
    }
    return catalogs, status, notes


def count_with_window(dates: pd.Series, events: pd.Series, low: int, high: int) -> int:
    if events.empty:
        return 0
    date_days = pd.DatetimeIndex(pd.to_datetime(dates, errors="coerce")).dropna().normalize().to_numpy(dtype="datetime64[D]").astype(np.int64)
    event_days = pd.DatetimeIndex(pd.to_datetime(events, errors="coerce")).dropna().normalize().to_numpy(dtype="datetime64[D]").astype(np.int64)
    event_days.sort()
    matched = np.zeros(len(date_days), dtype=bool)
    for shift in range(low, high + 1):
        targets = date_days + shift
        positions = np.searchsorted(event_days, targets)
        in_bounds = positions < len(event_days)
        shift_matches = np.zeros(len(date_days), dtype=bool)
        shift_matches[in_bounds] = event_days[positions[in_bounds]] == targets[in_bounds]
        matched |= shift_matches
    return int(matched.sum())


def build_test_specs() -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    families = [
        "HCS_author_catalog",
        "HCS_reconstructed_catalog",
        "CIR_arrival_catalog",
        "ICME_impact_catalog",
        "major_HSS_declining_phase_catalog",
    ]
    for fam in families:
        for n in [1, 2, 3]:
            specs.append({"event_family": fam, "window_definition": f"plus_minus_{n}d", "low": -n, "high": n})

    specs.extend(
        [
            {"event_family": "CIR_arrival_catalog", "window_definition": "CIR_following_window_0_to_plus3", "low": -3, "high": 0},
            {"event_family": "HCS_reconstructed_catalog", "window_definition": "HCS_preceding_window_minus3_to_0", "low": 0, "high": 3},
            {"event_family": "ICME_impact_catalog", "window_definition": "ICME_following_window_0_to_plus3", "low": -3, "high": 0},
            {"event_family": "major_HSS_declining_phase_catalog", "window_definition": "HSS_declining_phase_window_membership", "low": 0, "high": 0},
        ]
    )
    return specs


def run_coincidence_test(outbreaks: pd.DataFrame, valid_dates: pd.Series, catalogs: dict[str, pd.Series]) -> pd.DataFrame:
    return coincidence_summary(outbreaks["outbreak_anchor_date"], catalogs, valid_dates)


def make_figure(summary: pd.DataFrame) -> None:
    shown = summary.loc[summary["window_definition"].isin(["plus_minus_3d", "CIR_following_window_0_to_plus3", "HCS_preceding_window_minus3_to_0", "ICME_following_window_0_to_plus3", "HSS_declining_phase_window_membership"])].copy()
    if shown.empty:
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.text(0.5, 0.5, "No coincidence summary rows", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(FIG_PATH, dpi=300, bbox_inches="tight")
        plt.close(fig)
        return

    labels = [f"{r.event_family}\n{r.window_definition}" for r in shown.itertuples(index=False)]
    obs = shown["observed_count"].to_numpy(dtype=float)
    null_mean = shown["null_mean_count"].to_numpy(dtype=float)
    x = np.arange(len(shown))
    w = 0.38

    fig, ax = plt.subplots(figsize=(12.0, 5.6))
    ax.bar(x - w / 2, obs, width=w, color="0.25", label="Observed")
    ax.bar(x + w / 2, null_mean, width=w, color="0.70", label="Null mean")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("Coincident outbreaks (count)")
    ax.set_title("Author outbreaks: observed vs null coincidence counts")
    ax.legend(loc="best")
    fig.tight_layout()
    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_PATH, dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_report(outbreaks: pd.DataFrame, status: dict[str, str], notes: list[str], summary: pd.DataFrame) -> None:
    lines = [
        "# Author Outbreak Event Coincidence Test",
        "",
        f"- Outbreak anchors analyzed: {len(outbreaks)}",
        f"- Null iterations: {NULL_ITERATIONS}",
        f"- Random seed: {RNG_SEED}",
        "- Null dates preserve each outbreak's year and month; dates are sampled without replacement within year-month strata when possible.",
        "- Cluster-preserving sensitivity circularly shifts each year-month outbreak-day pattern as a unit, preserving monthly counts and cyclic within-month spacing; cross-month clusters are not preserved.",
        f"- Season-aware cluster sensitivity shifts each year's entire outbreak pattern by a shared offset within +/-{SEASON_CLUSTER_SHIFT_DAYS} days, preserving within-year cluster spacing across month boundaries.",
        "- This outbreak-list analysis is exploratory. P-values here are nominal; the combined summary Holm-adjusts all 87 tests across three null designs.",
        "",
        "## Event Catalog Status",
    ]
    for key in ["HCS_author_catalog", "HCS_reconstructed_catalog", "CIR_arrival_catalog", "ICME_impact_catalog", "major_HSS_declining_phase_catalog"]:
        lines.append(f"- {key}: {status.get(key, 'unknown')}")

    lines.extend(
        [
            "",
            "## Directional Window Definitions",
            "- CIR_following_window: outbreak occurs 0 to +3 days after CIR arrival (implemented as event in [-3, 0] days relative to outbreak).",
            "- HCS_preceding_window: outbreak occurs -3 to 0 days relative to HCS/HDP (implemented as event in [0, +3] days relative to outbreak).",
            "- ICME_following_window: outbreak occurs 0 to +3 days after ICME impact (implemented as event in [-3, 0] days relative to outbreak).",
            "- HSS_declining_phase_window: outbreak date falls on a reconstructed major-HSS declining-phase day.",
            "",
            "## Reconstruction Rules",
            "- CIR proxy: speed >= 500 km/s, speed jump >= 80 km/s, and compression signature from density/|B|/pressure.",
            "- ICME: direct catalog only, with outbreak starts and null dates restricted to 1996 onward; no proxy substitution.",
            f"- major-HSS declining phase: local speed peak >= {MAJOR_HSS_PEAK_THRESHOLD:.0f} km/s and include +{HSS_DECLINE_MIN_DAYS}..+{HSS_DECLINE_MAX_DAYS} days with non-increasing speed.",
        ]
    )
    for n in notes:
        lines.append(f"- {n}")

    lines.extend(["", "## Coincidence Highlights"])
    top = summary.sort_values("p_value").head(8) if not summary.empty else pd.DataFrame()
    if top.empty:
        lines.append("- No coincidence summary rows generated.")
    else:
        for row in top.itertuples(index=False):
            lines.append(
                f"- {row.event_family} | {row.window_definition}: observed={row.observed_count} of {row.outbreak_count}, "
                f"independent null mean={row.null_mean_count:.2f}, p={row.p_value:.3f}; "
                f"month-cluster null mean={row.cluster_null_mean_count:.2f}, p={row.p_value_cluster:.3f}; "
                f"year-season cluster null mean={row.season_cluster_null_mean_count:.2f}, "
                f"p={row.p_value_season_cluster:.3f}; {row.interpretation}"
            )

    lines.extend(["", "## Cluster-Preserving Sensitivity Highlights"])
    cluster_top = summary.sort_values("p_value_cluster").head(8) if not summary.empty else pd.DataFrame()
    for row in cluster_top.itertuples(index=False):
        lines.append(
            f"- {row.event_family} | {row.window_definition}: observed={row.observed_count}, "
            f"cluster-shift null mean={row.cluster_null_mean_count:.2f}, nominal p={row.p_value_cluster:.3f}."
        )
    lines.extend(["", "## Year-Season Cluster Sensitivity Highlights"])
    season_cluster_top = summary.sort_values("p_value_season_cluster").head(8) if not summary.empty else pd.DataFrame()
    for row in season_cluster_top.itertuples(index=False):
        lines.append(
            f"- {row.event_family} | {row.window_definition}: observed={row.observed_count}, "
            f"year-season cluster null mean={row.season_cluster_null_mean_count:.2f}, "
            f"nominal p={row.p_value_season_cluster:.3f}."
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not ANALYSIS_DAILY_PATH.exists() or not OMNI_DAILY_PATH.exists():
        raise FileNotFoundError("Missing required daily files: analysis_daily.csv and/or omni_daily.csv")

    outbreaks = load_outbreaks(OUTBREAKS_PATH)
    outbreaks = outbreaks.loc[outbreaks["outbreak_anchor_date"].notna()].copy()

    analysis_daily = pd.read_csv(ANALYSIS_DAILY_PATH, parse_dates=["date"])
    valid_dates = pd.to_datetime(analysis_daily["date"], errors="coerce").dropna().dt.normalize()

    omni = pd.read_csv(OMNI_DAILY_PATH, parse_dates=["date"])
    omni["date"] = pd.to_datetime(omni["date"], errors="coerce").dt.normalize()
    omni = omni.dropna(subset=["date"]).reset_index(drop=True)

    catalogs, status, notes = build_catalogs(omni)
    catalogs = {key: dates[dates.between(valid_dates.min(), valid_dates.max())].reset_index(drop=True) for key, dates in catalogs.items()}
    notes.append("ICME distance and coincidence tests use the same direct catalog and exclude outbreak starts before 1996. All catalogs are restricted to the analysis calendar.")

    summary = run_coincidence_test(outbreaks, valid_dates, catalogs)
    summary.to_csv(SUMMARY_PATH, index=False)

    make_figure(summary)
    write_report(outbreaks, status, notes, summary)

    print(f"Saved: {SUMMARY_PATH}")
    print(f"Saved: {FIG_PATH}")
    print(f"Saved: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
