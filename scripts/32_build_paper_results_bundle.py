from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "data" / "derived" / "tables"
REPORT_DIR = ROOT / "data" / "derived" / "reports"
MANIFEST_DIR = ROOT / "data" / "manifests"
CATALOG_DIR = ROOT / "data" / "derived" / "catalogs"
DAILY_DIR = ROOT / "data" / "derived" / "daily"


def read_csv_if_exists(path: Path, missing: list[str]) -> pd.DataFrame | None:
    if not path.exists():
        missing.append(str(path.relative_to(ROOT)))
        return None
    return pd.read_csv(path)


def read_json_if_exists(path: Path, missing: list[str]) -> dict | None:
    if not path.exists():
        missing.append(str(path.relative_to(ROOT)))
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iterations(text: object) -> int | None:
    if pd.isna(text):
        return None
    if not isinstance(text, str):
        return None
    parts = [segment.strip() for segment in text.split(";")]
    for part in parts:
        if part.startswith("iterations="):
            value = part.split("=", 1)[1].strip()
            if value.isdigit():
                return int(value)
    return None


def dataset_period_from_catalog(df: pd.DataFrame, date_col: str) -> tuple[str, str]:
    dt = pd.to_datetime(df[date_col], errors="coerce")
    dt = dt.dropna()
    if dt.empty:
        return "", ""
    return str(dt.min().date()), str(dt.max().date())


def main() -> int:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    missing: list[str] = []

    core_path = TABLE_DIR / "core_null_lag0_summary.csv"
    seasonal_path = TABLE_DIR / "seasonal_control_summary.csv"
    phase_path = TABLE_DIR / "phase_randomized_author_hcs_summary.csv"
    block_bootstrap_path = TABLE_DIR / "block_bootstrap_summary.csv"
    outbreak_key_path = TABLE_DIR / "author_outbreak_branch_key_results.csv"
    catalog_summary_path = TABLE_DIR / "hcs_catalog_comparison_summary.csv"
    author_catalog_path = CATALOG_DIR / "author_hcs_catalog.csv"
    reconstructed_catalog_path = CATALOG_DIR / "hcs_from_omni.csv"

    core_df = read_csv_if_exists(core_path, missing)
    seasonal_df = read_csv_if_exists(seasonal_path, missing)
    phase_df = read_csv_if_exists(phase_path, missing)
    block_bootstrap_df = read_csv_if_exists(block_bootstrap_path, missing)
    outbreak_key_df = read_csv_if_exists(outbreak_key_path, missing)
    catalog_summary_df = read_csv_if_exists(catalog_summary_path, missing)
    author_catalog_df = read_csv_if_exists(author_catalog_path, missing)
    reconstructed_catalog_df = read_csv_if_exists(reconstructed_catalog_path, missing)

    manifest_11 = read_json_if_exists(MANIFEST_DIR / "11_ingest_author_hcs.json", missing)
    manifest_15 = read_json_if_exists(MANIFEST_DIR / "15_build_daily_tornado_series.json", missing)
    manifest_26 = read_json_if_exists(MANIFEST_DIR / "26_reconstruct_hcs_from_omni.json", missing)
    manifest_27 = read_json_if_exists(MANIFEST_DIR / "27_event_study_reconstructed_hcs.json", missing)
    manifest_28 = read_json_if_exists(MANIFEST_DIR / "28_seasonal_control_event_studies.json", missing)
    manifest_29 = read_json_if_exists(MANIFEST_DIR / "29_phase_randomized_null_test.json", missing)

    dataset_rows: list[dict[str, object]] = []

    analysis_period_start = ""
    analysis_period_end = ""
    if manifest_15 is not None:
        analysis_period_start = manifest_15.get("metrics", {}).get("min_date", "")
        analysis_period_end = manifest_15.get("metrics", {}).get("max_date", "")

    dataset_rows.append(
        {
            "dataset": "tornado_analysis_daily",
            "source": "data/derived/daily/analysis_daily.csv",
            "period_start": analysis_period_start,
            "period_end": analysis_period_end,
            "notes": "Merged daily tornado and OMNI analysis table used by later event-study outputs.",
        }
    )

    if author_catalog_df is not None:
        start, end = dataset_period_from_catalog(author_catalog_df, "date")
        notes = "Author HCS catalog parsed from source text file."
        if manifest_11 is not None:
            paper_note = manifest_11.get("metrics", {}).get("paper_count_note", "")
            if paper_note:
                notes = f"{notes} {paper_note}"
        dataset_rows.append(
            {
                "dataset": "author_hcs_catalog",
                "source": "data/derived/catalogs/author_hcs_catalog.csv",
                "period_start": start,
                "period_end": end,
                "notes": notes,
            }
        )

    if reconstructed_catalog_df is not None:
        start, end = dataset_period_from_catalog(reconstructed_catalog_df, "date")
        bx_col = ""
        if manifest_26 is not None:
            bx_col = manifest_26.get("metrics", {}).get("bx_column_used", "")
        notes = "Independent HCS reconstruction from daily OMNI polarity flips."
        if bx_col:
            notes = f"{notes} Bx column used: {bx_col}."
        dataset_rows.append(
            {
                "dataset": "reconstructed_hcs_catalog",
                "source": "data/derived/catalogs/hcs_from_omni.csv",
                "period_start": start,
                "period_end": end,
                "notes": notes,
            }
        )

    dataset_rows.extend(
        [
            {
                "dataset": "author_hcs_core_null",
                "source": "data/derived/tables/core_null_lag0_summary.csv",
                "period_start": analysis_period_start,
                "period_end": analysis_period_end,
                "notes": "Core lag-0 summary includes author and reconstructed fast-null comparisons.",
            },
            {
                "dataset": "seasonal_controls",
                "source": "data/derived/tables/seasonal_control_summary.csv",
                "period_start": analysis_period_start,
                "period_end": analysis_period_end,
                "notes": "Season-restricted random-date null comparisons for full year, Mar-Jun, and Apr-Jun subsets.",
            },
            {
                "dataset": "phase_randomized_null",
                "source": "data/derived/tables/phase_randomized_author_hcs_summary.csv",
                "period_start": analysis_period_start,
                "period_end": analysis_period_end,
                "notes": "Author-HCS lag-0 summary under phase-randomized surrogate nulls.",
            },
            {
                "dataset": "catalog_comparison",
                "source": "data/derived/tables/hcs_catalog_comparison_summary.csv",
                "period_start": "",
                "period_end": "",
                "notes": "Direct summary comparison of author and reconstructed HCS catalogs.",
            },
        ]
    )
    dataset_table = pd.DataFrame(dataset_rows, columns=["dataset", "source", "period_start", "period_end", "notes"])
    dataset_table.to_csv(TABLE_DIR / "paper_table_1_datasets_and_catalogs.csv", index=False)

    primary_rows: list[dict[str, object]] = []
    if core_df is not None:
        reconstructed_iterations = None
        if manifest_27 is not None:
            reconstructed_iterations = manifest_27.get("metrics", {}).get("null_iterations")
        phase_iterations = None
        if manifest_29 is not None:
            phase_iterations = manifest_29.get("metrics", {}).get("iterations")

        for row in core_df.itertuples(index=False):
            iterations = None
            notes = ""
            if row.analysis == "core_fast_null":
                if row.branch == "reconstructed_hcs":
                    iterations = reconstructed_iterations
                notes = "Primary daily-rate lag-0 comparison against fast random-date null."
            elif str(row.analysis).startswith("seasonal_"):
                if seasonal_df is not None:
                    match = seasonal_df[(seasonal_df["branch"] == row.branch) & ("seasonal_" + seasonal_df["season"] == row.analysis)]
                    if not match.empty:
                        iterations = parse_iterations(match.iloc[0]["notes"])
                        notes = str(match.iloc[0]["notes"])
            elif row.analysis == "phase_randomized":
                iterations = phase_iterations
                notes = "Phase-randomized surrogate null test for author-HCS branch."

            primary_rows.append(
                {
                    "branch": row.branch,
                    "analysis": row.analysis,
                    "lag0_observed": row.lag0_observed,
                    "lag0_null_mean": row.lag0_null_mean,
                    "lag0_null_q025": row.lag0_null_q025,
                    "lag0_null_q975": row.lag0_null_q975,
                    "lag0_inside_band": row.lag0_inside_band,
                    "iterations": iterations,
                    "notes": notes,
                }
            )
    pd.DataFrame(
        primary_rows,
        columns=[
            "branch",
            "analysis",
            "lag0_observed",
            "lag0_null_mean",
            "lag0_null_q025",
            "lag0_null_q975",
            "lag0_inside_band",
            "iterations",
            "notes",
        ],
    ).to_csv(TABLE_DIR / "paper_table_2_primary_results.csv", index=False)

    robustness_rows: list[dict[str, object]] = []
    if seasonal_df is not None:
        for row in seasonal_df.itertuples(index=False):
            interpretation = "Lag 0 remains inside the seasonal null band."
            if bool(row.lag0_outside_band_all_tornadoes):
                interpretation = "Lag 0 falls outside the seasonal null band."
            robustness_rows.append(
                {
                    "test": f"{row.branch}_{row.season}",
                    "event_count": int(row.event_count_used),
                    "lag0_outside_band": bool(row.lag0_outside_band_all_tornadoes),
                    "outside_band_lag_count_if_available": pd.NA,
                    "interpretation": interpretation,
                }
            )
    if phase_df is not None and not phase_df.empty:
        phase_row = phase_df.iloc[0]
        robustness_rows.append(
            {
                "test": "author_hcs_phase_randomized",
                "event_count": int(phase_row["event_count_used"]),
                "lag0_outside_band": bool(phase_row["lag0_outside_band"]),
                "outside_band_lag_count_if_available": int(phase_row["outside_band_lag_count"]),
                "interpretation": str(phase_row["interpretation"]),
            }
        )
    if block_bootstrap_df is not None and not block_bootstrap_df.empty:
        for row in block_bootstrap_df.itertuples(index=False):
            robustness_rows.append(
                {
                    "test": f"{row.branch}_block_bootstrap_{int(row.block_length_days)}d",
                    "event_count": int(row.event_count_used),
                    "lag0_outside_band": not bool(row.lag0_inside_band),
                    "outside_band_lag_count_if_available": int(row.outside_band_lag_count),
                    "interpretation": f"Block bootstrap lag 0 inside pointwise 95% band={bool(row.lag0_inside_band)}.",
                }
            )
    pd.DataFrame(
        robustness_rows,
        columns=[
            "test",
            "event_count",
            "lag0_outside_band",
            "outside_band_lag_count_if_available",
            "interpretation",
        ],
    ).to_csv(TABLE_DIR / "paper_table_3_robustness_checks.csv", index=False)

    catalog_rows: list[dict[str, object]] = []
    if catalog_summary_df is not None and not catalog_summary_df.empty:
        row = catalog_summary_df.iloc[0]
        author_years = pd.date_range(row["author_period_start"], row["author_period_end"], freq="D").year.nunique()
        reconstructed_years = pd.date_range(row["reconstructed_period_start"], row["reconstructed_period_end"], freq="D").year.nunique()
        catalog_rows = [
            {
                "metric": "author_total_count",
                "value": int(row["author_count_total"]),
                "notes": "Total author-catalog crossings.",
            },
            {
                "metric": "reconstructed_total_count",
                "value": int(row["reconstructed_count_total"]),
                "notes": "Total reconstructed-catalog crossings.",
            },
            {
                "metric": "author_annual_average_count",
                "value": float(row["author_count_total"]) / float(author_years),
                "notes": "Total count divided by number of calendar years covered.",
            },
            {
                "metric": "reconstructed_annual_average_count",
                "value": float(row["reconstructed_count_total"]) / float(reconstructed_years),
                "notes": "Total count divided by number of calendar years covered.",
            },
            {
                "metric": "author_median_spacing_days",
                "value": float(row["median_author_spacing_days"]),
                "notes": "Median days between consecutive author-catalog crossings.",
            },
            {
                "metric": "reconstructed_median_spacing_days",
                "value": float(row["median_reconstructed_spacing_days"]),
                "notes": "Median days between consecutive reconstructed-catalog crossings.",
            },
            {
                "metric": "median_nearest_event_timing_difference_days",
                "value": float(row["median_nearest_author_to_reconstructed_diff_days"]),
                "notes": "Median absolute nearest-date difference from author to reconstructed catalog.",
            },
        ]
    pd.DataFrame(catalog_rows, columns=["metric", "value", "notes"]).to_csv(
        TABLE_DIR / "paper_table_4_catalog_comparison.csv", index=False
    )

    report_lines = ["# Paper Results Bundle", ""]
    report_lines.extend(
        [
            "## Primary Question and Endpoint",
            "The project-designated primary question is whether the full-year mean daily all-tornado count at lag 0 differs from its null expectation around author HCS crossings; the reconstructed-HCS branch is a parallel validation analysis.",
            "No dated preregistration or prospective analysis plan was found in the repository, so ‘primary’ denotes the current analysis hierarchy, not prospective registration.",
            "",
        ]
    )
    if primary_rows:
        primary_df = pd.DataFrame(primary_rows)
        lag0_special = primary_df[primary_df["lag0_inside_band"] == False]
        report_lines.append("## Main Result")
        report_lines.append("Daily-rate comparisons do not show a special lag-0 effect in the primary author or reconstructed HCS branches.")
        report_lines.append("")
        if lag0_special.empty:
            report_lines.append("No available lag-0 test fell outside its 95% null band in the assembled primary results table.")
        else:
            report_lines.append("Some lag-0 tests fell outside their null band:")
            for row in lag0_special.itertuples(index=False):
                report_lines.append(f"- {row.branch} / {row.analysis}")
        report_lines.append("")

    report_lines.append("## Robustness Checks")
    if robustness_rows:
        any_outside = any(bool(row["lag0_outside_band"]) for row in robustness_rows)
        if any_outside:
            report_lines.append("At least one robustness check showed lag 0 outside its null envelope.")
        else:
            report_lines.append("Seasonal, phase-randomized, and 7/14-day block-bootstrap robustness checks kept lag 0 inside the corresponding pointwise null bands.")
        report_lines.append("Block bootstrap resamples contiguous daily outcome blocks, preserving short-range clustering but not the seasonal cycle by construction.")
    else:
        report_lines.append("No robustness output tables were available.")
    report_lines.append("")
    report_lines.append("## Interpretation")
    report_lines.append("Daily means and totals accumulated across events have identical lag shapes for fixed event populations. Neither is a running sum across lags. Pointwise lag-0 comparisons do not settle the significance of nonzero-lag peaks.")
    report_lines.append("")
    report_lines.append("## Exploratory Author-Outbreak Analysis")
    if outbreak_key_df is None or outbreak_key_df.empty:
        report_lines.append("The post-hoc supplement outbreak-list analysis is unavailable; it does not alter the primary endpoint.")
    else:
        corrected_count = int(outbreak_key_df["p_value_holm"].notna().sum())
        below_threshold = int((outbreak_key_df["p_value_holm"] < 0.05).sum())
        report_lines.append("This post-hoc branch does not redefine the primary result.")
        report_lines.append(f"Holm adjustment covers {corrected_count} tests across all three null designs; {below_threshold} remain below 0.05.")
        hcs_one_day = outbreak_key_df[
            (outbreak_key_df["analysis_family"] == "coincidence_null")
            & (outbreak_key_df["event_family"] == "HCS_author_catalog")
            & (outbreak_key_df["statistic"] == "plus_minus_1d")
        ].sort_values("null_model")
        if not hcs_one_day.empty:
            for result in hcs_one_day.itertuples(index=False):
                report_lines.append(
                    f"Author-HCS ±1-day coincidence under {result.null_model}: {int(result.observed_value)} observed vs "
                    f"{result.null_mean:.2f} null mean; nominal p={result.p_value_nominal:.6f}, "
                    f"Holm-adjusted p={result.p_value_holm:.6f}. This remains exploratory and is not causal evidence."
                )
        report_lines.append("The independent year-month null does not preserve date clustering; month rotations preserve within-month spacing; year-season shifts preserve within-year clusters across month boundaries but not clusters spanning years. The adjustment does not cover every analysis explored across the project.")
    report_lines.append("")
    report_lines.append("## Limitations Before Submission")
    report_lines.append("The annual cluster shifts preserve season approximately and within-year spacing, not clusters spanning years. Count models now estimate dispersion and use 14-day HAC covariance, but remain exploratory in-sample fits. Document retrospective analysis selection, use Monte Carlo uncertainty when interpreting adjusted p-values, report pointwise lag bands as pointwise, and retain the supplement inference audit note. Temporal association is not causal attribution.")
    report_lines.append("")
    if missing:
        report_lines.append("## Missing Inputs")
        for item in missing:
            report_lines.append(f"- {item}")
        report_lines.append("")

    (REPORT_DIR / "paper_results_bundle.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print("Created paper bundle tables and report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
