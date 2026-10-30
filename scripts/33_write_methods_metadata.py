from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "data" / "derived" / "reports"
TABLE_DIR = ROOT / "data" / "derived" / "tables"
MANIFEST_DIR = ROOT / "data" / "manifests"
CATALOG_DIR = ROOT / "data" / "derived" / "catalogs"


def read_json_if_exists(path: Path, missing: list[str]) -> dict | None:
    if not path.exists():
        missing.append(str(path.relative_to(ROOT)))
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_if_exists(path: Path, missing: list[str]) -> pd.DataFrame | None:
    if not path.exists():
        missing.append(str(path.relative_to(ROOT)))
        return None
    return pd.read_csv(path)


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    missing: list[str] = []

    manifest_11 = read_json_if_exists(MANIFEST_DIR / "11_ingest_author_hcs.json", missing)
    manifest_15 = read_json_if_exists(MANIFEST_DIR / "15_build_daily_tornado_series.json", missing)
    manifest_26 = read_json_if_exists(MANIFEST_DIR / "26_reconstruct_hcs_from_omni.json", missing)
    manifest_27 = read_json_if_exists(MANIFEST_DIR / "27_event_study_reconstructed_hcs.json", missing)
    manifest_28 = read_json_if_exists(MANIFEST_DIR / "28_seasonal_control_event_studies.json", missing)
    manifest_29 = read_json_if_exists(MANIFEST_DIR / "29_phase_randomized_null_test.json", missing)

    seasonal_df = read_csv_if_exists(TABLE_DIR / "seasonal_control_summary.csv", missing)
    phase_df = read_csv_if_exists(TABLE_DIR / "phase_randomized_author_hcs_summary.csv", missing)
    author_catalog_df = read_csv_if_exists(CATALOG_DIR / "author_hcs_catalog.csv", missing)
    reconstructed_catalog_df = read_csv_if_exists(CATALOG_DIR / "hcs_from_omni.csv", missing)

    author_event_count_used = None
    if seasonal_df is not None:
        match = seasonal_df[(seasonal_df["branch"] == "author_hcs") & (seasonal_df["season"] == "full_year")]
        if not match.empty:
            author_event_count_used = int(match.iloc[0]["event_count_used"])

    reconstructed_rules = []
    if manifest_26 is not None:
        reconstructed_rules.extend(manifest_26.get("assumptions", []))
    if reconstructed_catalog_df is not None and "notes" in reconstructed_catalog_df.columns and not reconstructed_catalog_df.empty:
        first_note = str(reconstructed_catalog_df.iloc[0]["notes"])
        if first_note and first_note not in reconstructed_rules:
            reconstructed_rules.append(first_note)

    seasonal_subsets = []
    if seasonal_df is not None and "season" in seasonal_df.columns:
        seasonal_subsets = list(dict.fromkeys(seasonal_df["season"].astype(str).tolist()))

    metadata = {
        "tornado_dataset": {
            "path": (manifest_15 or {}).get("outputs", {}).get("csv", ""),
            "apparent_period_start": (manifest_15 or {}).get("metrics", {}).get("min_date", ""),
            "apparent_period_end": (manifest_15 or {}).get("metrics", {}).get("max_date", ""),
        },
        "author_hcs_catalog": {
            "path": (manifest_11 or {}).get("outputs", {}).get("csv", "data/derived/catalogs/author_hcs_catalog.csv"),
            "raw_count_1963_2023": (manifest_11 or {}).get("metrics", {}).get("count_1963_2023"),
            "event_count_used": author_event_count_used,
            "source_path": (manifest_11 or {}).get("metrics", {}).get("source_path", ""),
        },
        "omni_reconstruction": {
            "catalog_path": (manifest_26 or {}).get("outputs", {}).get("catalog", {}).get("csv", "data/derived/catalogs/hcs_from_omni.csv"),
            "variable_used": (manifest_26 or {}).get("metrics", {}).get("bx_column_used"),
            "rules": reconstructed_rules,
            "date_range": {
                "start": (manifest_26 or {}).get("metrics", {}).get("date_min", ""),
                "end": (manifest_26 or {}).get("metrics", {}).get("date_max", ""),
            },
        },
        "event_study": {
            "lag_window_days": (manifest_28 or {}).get("metrics", {}).get("window_days") or (manifest_27 or {}).get("metrics", {}).get("window_days"),
            "date_ranges_actually_analyzed": {
                "analysis_daily_start": (manifest_15 or {}).get("metrics", {}).get("min_date", ""),
                "analysis_daily_end": (manifest_15 or {}).get("metrics", {}).get("max_date", ""),
                "author_catalog_start": (manifest_11 or {}).get("metrics", {}).get("min_datetime_utc", ""),
                "author_catalog_end": (manifest_11 or {}).get("metrics", {}).get("max_datetime_utc", ""),
                "reconstructed_catalog_start": (manifest_26 or {}).get("metrics", {}).get("date_min", ""),
                "reconstructed_catalog_end": (manifest_26 or {}).get("metrics", {}).get("date_max", ""),
            },
        },
        "null_models": {
            "seasonal_random_date_iterations": (manifest_28 or {}).get("metrics", {}).get("iterations"),
            "reconstructed_fast_null_iterations": (manifest_27 or {}).get("metrics", {}).get("null_iterations"),
            "phase_randomization_iterations": (manifest_29 or {}).get("metrics", {}).get("iterations") if manifest_29 else None,
        },
        "seasonal_subsets_used": seasonal_subsets,
        "phase_randomization": {
            "event_count_used": int(phase_df.iloc[0]["event_count_used"]) if phase_df is not None and not phase_df.empty else None,
            "outside_band_lag_count": int(phase_df.iloc[0]["outside_band_lag_count"]) if phase_df is not None and not phase_df.empty else None,
        },
        "missing_inputs": missing,
    }

    (REPORT_DIR / "methods_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    lines = ["# Methods Metadata", ""]
    lines.append("## Tornado Dataset")
    lines.append(f"- Path: {metadata['tornado_dataset']['path']}")
    lines.append(f"- Apparent period: {metadata['tornado_dataset']['apparent_period_start']} to {metadata['tornado_dataset']['apparent_period_end']}")
    lines.append("")
    lines.append("## Author HCS Catalog")
    lines.append(f"- Path: {metadata['author_hcs_catalog']['path']}")
    lines.append(f"- Raw count 1963-2023: {metadata['author_hcs_catalog']['raw_count_1963_2023']}")
    lines.append(f"- Event count used: {metadata['author_hcs_catalog']['event_count_used']}")
    lines.append("")
    lines.append("## OMNI Reconstruction")
    lines.append(f"- Variable used: {metadata['omni_reconstruction']['variable_used']}")
    lines.append(f"- Catalog path: {metadata['omni_reconstruction']['catalog_path']}")
    lines.append(f"- Date range: {metadata['omni_reconstruction']['date_range']['start']} to {metadata['omni_reconstruction']['date_range']['end']}")
    if metadata["omni_reconstruction"]["rules"]:
        lines.append("- Rules:")
        for rule in metadata["omni_reconstruction"]["rules"]:
            lines.append(f"  - {rule}")
    lines.append("")
    lines.append("## Event Study Settings")
    lines.append(f"- Lag window: +/-{metadata['event_study']['lag_window_days']} days")
    lines.append(f"- Seasonal subsets: {', '.join(metadata['seasonal_subsets_used']) if metadata['seasonal_subsets_used'] else 'unavailable'}")
    lines.append(f"- Seasonal null iterations: {metadata['null_models']['seasonal_random_date_iterations']}")
    lines.append(f"- Reconstructed fast-null iterations: {metadata['null_models']['reconstructed_fast_null_iterations']}")
    lines.append(f"- Phase-randomization iterations: {metadata['null_models']['phase_randomization_iterations']}")
    lines.append("")
    lines.append("## Date Ranges Actually Analyzed")
    for key, value in metadata["event_study"]["date_ranges_actually_analyzed"].items():
        lines.append(f"- {key}: {value}")
    if missing:
        lines.append("")
        lines.append("## Missing Inputs")
        for item in missing:
            lines.append(f"- {item}")

    (REPORT_DIR / "methods_metadata.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Created methods metadata JSON and Markdown outputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
