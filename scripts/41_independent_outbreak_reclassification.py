from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTBREAKS_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_outbreaks_clean.csv"
OMNI_DAILY_PATH = ROOT / "data" / "derived" / "daily" / "omni_daily.csv"
AUTHOR_HCS_PATH = ROOT / "data" / "derived" / "catalogs" / "author_hcs_catalog.csv"
RECON_HCS_PATH = ROOT / "data" / "derived" / "catalogs" / "hcs_from_omni.csv"
ICME_PATH = ROOT / "data" / "derived" / "catalogs" / "icme_catalog.csv"
CIR_PATH = ROOT / "data" / "derived" / "catalogs" / "cir_proxy_catalog.csv"
HSS_PATH = ROOT / "data" / "derived" / "catalogs" / "hss_onset_catalog.csv"

OUT_PATH = ROOT / "data" / "derived" / "catalogs" / "outbreaks_reclassified_independent.csv"
SUMMARY_PATH = ROOT / "data" / "derived" / "tables" / "outbreak_type_independent_summary.csv"
REPORT_PATH = ROOT / "data" / "derived" / "reports" / "outbreak_type_independent_reclassification.md"

CIR_LOOKBACK_DAYS = 3
HCS_LOOKBACK_DAYS = 3
ICME_LOOKBACK_DAYS = 3
MAJOR_HSS_PEAK_THRESHOLD = 600.0
MAJOR_HSS_DECLINE_MIN_DAYS = 1
MAJOR_HSS_DECLINE_MAX_DAYS = 4
HDP_DENSITY_THRESHOLD = 8.0


def load_optional_date_catalog(path: Path, date_col: str) -> pd.Series:
    if not path.exists():
        return pd.Series(dtype="datetime64[ns]")
    df = pd.read_csv(path)
    dt = pd.to_datetime(df[date_col], errors="coerce")
    return dt.dropna().dt.normalize().sort_values().reset_index(drop=True)


def derive_cir_hss_proxies(omni: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    speed = omni["speed_mean"]
    speed_jump = speed.diff()
    hss = omni.loc[(speed >= 500.0) & (speed_jump >= 80.0), ["date", "speed_mean", "proton_density_mean", "b_mag_mean", "flow_pressure_mean"]].copy()
    hss["event_type"] = "hss_onset_proxy"

    cir = hss.loc[
        (hss["proton_density_mean"] >= 8.0)
        | (hss["b_mag_mean"] >= 8.0)
        | (hss["flow_pressure_mean"] >= 2.5)
    ].copy()
    cir["event_type"] = "cir_proxy"
    return cir, hss


def derive_icme_proxy(omni: pd.DataFrame) -> pd.Series:
    proxy = omni.loc[
        (omni["b_mag_mean"] >= 10.0) & (omni["speed_mean"] >= 450.0) & (omni["dst_mean"] <= -50.0),
        ["date"],
    ].copy()
    if proxy.empty:
        return pd.Series(dtype="datetime64[ns]")
    proxy["gap"] = proxy["date"].diff().dt.days.fillna(99)
    proxy = proxy.loc[proxy["gap"] > 1, ["date"]]
    return proxy["date"].dropna().dt.normalize().reset_index(drop=True)


def derive_major_hss_peaks(omni: pd.DataFrame) -> pd.Series:
    speed = omni["speed_mean"].to_numpy(dtype=float)
    peaks = []
    for i in range(1, len(omni) - 1):
        if not np.isfinite(speed[i]):
            continue
        if speed[i] >= MAJOR_HSS_PEAK_THRESHOLD and speed[i] >= speed[i - 1] and speed[i] >= speed[i + 1]:
            peaks.append(omni.iloc[i]["date"])
    return pd.Series(pd.to_datetime(peaks, errors="coerce")).dropna().dt.normalize().drop_duplicates().sort_values().reset_index(drop=True)


def nearest_prior_date(event_dates: pd.Series, target_date: pd.Timestamp, max_days: int) -> pd.Timestamp | pd.NaT:
    if event_dates.empty or pd.isna(target_date):
        return pd.NaT
    eligible = event_dates[(event_dates <= target_date) & ((target_date - event_dates).dt.days <= max_days)]
    if eligible.empty:
        return pd.NaT
    return eligible.max()


def classify_outbreak(row: pd.Series, cir_dates: pd.Series, hss_dates: pd.Series, hcs_dates: pd.Series, icme_dates: pd.Series, hss_peaks: pd.Series, omni: pd.DataFrame) -> dict[str, object]:
    start = pd.to_datetime(row.get("outbreak_date_start"), errors="coerce")
    if pd.isna(start):
        return {
            "independent_type": "unclassified",
            "matched_event_date": "",
            "matched_event_kind": "",
            "rule_used": "missing_outbreak_date",
            "confidence": "low",
            "notes": "Outbreak start date missing or unparseable.",
        }

    start = start.normalize()
    local = omni.loc[omni["date"] == start]
    density = float(local["proton_density_mean"].iloc[0]) if not local.empty and pd.notna(local["proton_density_mean"].iloc[0]) else np.nan

    icme_match = nearest_prior_date(icme_dates, start, ICME_LOOKBACK_DAYS)
    if pd.notna(icme_match):
        delta = int((start - icme_match).days)
        return {
            "independent_type": "C_like_ICME_following",
            "matched_event_date": str(icme_match.date()),
            "matched_event_kind": "ICME",
            "rule_used": f"ICME prior within {ICME_LOOKBACK_DAYS} days",
            "confidence": "high" if delta <= 1 else "medium",
            "notes": "Classified from direct ICME catalog or OMNI-derived ICME proxy.",
        }

    if not hss_peaks.empty:
        prior_peaks = hss_peaks[hss_peaks < start]
        if not prior_peaks.empty:
            peak = prior_peaks.max()
            delta = int((start - peak).days)
            if MAJOR_HSS_DECLINE_MIN_DAYS <= delta <= MAJOR_HSS_DECLINE_MAX_DAYS:
                peak_speed = omni.loc[omni["date"] == peak, "speed_mean"]
                now_speed = omni.loc[omni["date"] == start, "speed_mean"]
                if not peak_speed.empty and not now_speed.empty and float(now_speed.iloc[0]) <= float(peak_speed.iloc[0]):
                    return {
                        "independent_type": "D_like_major_HSS_declining_phase",
                        "matched_event_date": str(peak.date()),
                        "matched_event_kind": "major_HSS_peak",
                        "rule_used": f"Outbreak {delta} days after major HSS peak with non-increasing speed",
                        "confidence": "medium" if delta > 1 else "high",
                        "notes": "Major HSS peak defined from OMNI daily speed local maxima >= 600 km/s.",
                    }

    hcs_match = nearest_prior_date(hcs_dates, start, HCS_LOOKBACK_DAYS)
    if pd.notna(hcs_match) and np.isfinite(density) and density >= HDP_DENSITY_THRESHOLD:
        delta = int((start - hcs_match).days)
        return {
            "independent_type": "B_like_HCS_HDP_preceding",
            "matched_event_date": str(hcs_match.date()),
            "matched_event_kind": "HCS_HDP",
            "rule_used": f"Reconstructed HCS prior within {HCS_LOOKBACK_DAYS} days and proton density >= {HDP_DENSITY_THRESHOLD} cm^-3 on outbreak date",
            "confidence": "high" if delta <= 1 else "medium",
            "notes": "HCS comes from OMNI-derived reconstruction; HDP proxied by elevated daily proton density.",
        }

    cir_match = nearest_prior_date(cir_dates, start, CIR_LOOKBACK_DAYS)
    if pd.notna(cir_match):
        delta = int((start - cir_match).days)
        return {
            "independent_type": "A_like_CIR_following",
            "matched_event_date": str(cir_match.date()),
            "matched_event_kind": "CIR",
            "rule_used": f"CIR proxy prior within {CIR_LOOKBACK_DAYS} days",
            "confidence": "high" if delta <= 1 else "medium",
            "notes": "CIR proxy from existing catalog or speed-rise/compression OMNI rule.",
        }

    return {
        "independent_type": "unclassified",
        "matched_event_date": "",
        "matched_event_kind": "",
        "rule_used": "no_rule_matched",
        "confidence": "low",
        "notes": "No ICME, major-HSS-decline, HCS+HDP, or CIR proxy match within the configured windows.",
    }


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not OUTBREAKS_PATH.exists() or not OMNI_DAILY_PATH.exists() or not RECON_HCS_PATH.exists():
        raise FileNotFoundError("Required outbreak clean catalog, OMNI daily, or reconstructed HCS catalog is missing.")

    outbreaks = pd.read_csv(OUTBREAKS_PATH)
    outbreaks["outbreak_date_start"] = pd.to_datetime(outbreaks.get("outbreak_date_start"), errors="coerce")
    outbreaks["outbreak_date_end"] = pd.to_datetime(outbreaks.get("outbreak_date_end"), errors="coerce")

    omni = pd.read_csv(OMNI_DAILY_PATH, parse_dates=["date"])
    omni["date"] = pd.to_datetime(omni["date"], errors="coerce").dt.normalize()

    hcs_dates = load_optional_date_catalog(RECON_HCS_PATH, "date")
    _ = load_optional_date_catalog(AUTHOR_HCS_PATH, "date") if AUTHOR_HCS_PATH.exists() else pd.Series(dtype="datetime64[ns]")

    cir_dates = load_optional_date_catalog(CIR_PATH, "date")
    hss_dates = load_optional_date_catalog(HSS_PATH, "date")
    if cir_dates.empty or hss_dates.empty:
        cir_proxy, hss_proxy = derive_cir_hss_proxies(omni)
        if cir_dates.empty:
            cir_dates = pd.to_datetime(cir_proxy["date"], errors="coerce").dropna().dt.normalize().reset_index(drop=True)
        if hss_dates.empty:
            hss_dates = pd.to_datetime(hss_proxy["date"], errors="coerce").dropna().dt.normalize().reset_index(drop=True)

    icme_dates = load_optional_date_catalog(ICME_PATH, "analysis_date")
    if icme_dates.empty:
        icme_dates = derive_icme_proxy(omni)

    hss_peaks = derive_major_hss_peaks(omni)

    classified_rows = []
    for row in outbreaks.itertuples(index=False):
        base = row._asdict()
        cls = classify_outbreak(pd.Series(base), cir_dates, hss_dates, hcs_dates, icme_dates, hss_peaks, omni)
        classified_rows.append(
            {
                "outbreak_id": int(base.get("outbreak_id")),
                "outbreak_date_start": "" if pd.isna(base.get("outbreak_date_start")) else str(pd.Timestamp(base.get("outbreak_date_start")).date()),
                "outbreak_date_end": "" if pd.isna(base.get("outbreak_date_end")) else str(pd.Timestamp(base.get("outbreak_date_end")).date()),
                "author_type": base.get("author_type_normalized", base.get("author_type", "")),
                "independent_type": cls["independent_type"],
                "matched_event_date": cls["matched_event_date"],
                "matched_event_kind": cls["matched_event_kind"],
                "rule_used": cls["rule_used"],
                "confidence": cls["confidence"],
                "notes": cls["notes"],
            }
        )

    classified = pd.DataFrame(classified_rows)
    classified.to_csv(OUT_PATH, index=False)

    summary = classified.groupby("independent_type", dropna=False).size().reset_index(name="outbreak_count")
    total = int(summary["outbreak_count"].sum()) if not summary.empty else 0
    summary["percent_of_total"] = np.where(total > 0, 100.0 * summary["outbreak_count"] / total, np.nan)
    summary["notes"] = "Independent OMNI-based reclassification using explicit date-window rules."
    summary.to_csv(SUMMARY_PATH, index=False)

    unclassified = int((classified["independent_type"] == "unclassified").sum()) if not classified.empty else 0
    report_lines = [
        "# Independent Outbreak Reclassification",
        "",
        "## Rules",
        f"- A_like_CIR_following: CIR proxy within {CIR_LOOKBACK_DAYS} days prior to outbreak.",
        f"- B_like_HCS_HDP_preceding: reconstructed HCS within {HCS_LOOKBACK_DAYS} days prior plus proton density >= {HDP_DENSITY_THRESHOLD} cm^-3 on outbreak date.",
        f"- C_like_ICME_following: ICME catalog date or OMNI-derived ICME proxy within {ICME_LOOKBACK_DAYS} days prior.",
        f"- D_like_major_HSS_declining_phase: outbreak {MAJOR_HSS_DECLINE_MIN_DAYS}-{MAJOR_HSS_DECLINE_MAX_DAYS} days after a local speed peak >= {MAJOR_HSS_PEAK_THRESHOLD} km/s with non-increasing speed.",
        "",
        f"- Total outbreaks processed: {len(classified)}",
        f"- Classifiable outbreaks: {len(classified) - unclassified}",
        f"- Unclassified outbreaks: {unclassified}",
        "",
        "## Notes",
        "- Existing ICME/CIR/HSS catalogs are used when present; otherwise transparent OMNI daily proxies are constructed.",
        "- This branch is intentionally independent of the author outbreak labels and does not hard-code their classifications.",
    ]
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("Independent type counts:")
    if summary.empty:
        print("No outbreak rows available.")
    else:
        print(summary[["independent_type", "outbreak_count"]].to_string(index=False))
    print(f"Saved: {OUT_PATH}")
    print(f"Saved: {SUMMARY_PATH}")
    print(f"Saved: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
