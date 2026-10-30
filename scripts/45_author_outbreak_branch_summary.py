from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from _utils import holm_adjust_pvalues


ROOT = Path(__file__).resolve().parents[1]
DISTANCE_SUMMARY_PATH = ROOT / "data" / "derived" / "tables" / "author_outbreak_event_distance_null_summary.csv"
COINCIDENCE_SUMMARY_PATH = ROOT / "data" / "derived" / "tables" / "author_outbreak_event_coincidence_summary.csv"
AUTHOR_TYPE_SUMMARY_PATH = ROOT / "data" / "derived" / "tables" / "outbreak_type_author_summary.csv"
AGREEMENT_SUMMARY_PATH = ROOT / "data" / "derived" / "tables" / "outbreak_type_agreement_summary.csv"

KEY_RESULTS_PATH = ROOT / "data" / "derived" / "tables" / "author_outbreak_branch_key_results.csv"
REPORT_PATH = ROOT / "data" / "derived" / "reports" / "author_outbreak_branch_summary.md"


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def build_key_results(distance_df: pd.DataFrame, coincidence_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    if not distance_df.empty:
        for row in distance_df.itertuples(index=False):
            distance_tests = [
                (
                    "observed_mean_abs_distance",
                    row.observed_mean_abs_distance,
                    [
                        ("year_month_independent", row.null_mean_abs_distance, row.null_q025, row.null_q975, row.p_value_mean),
                        ("year_month_cluster_rotation", row.cluster_null_mean_abs_distance, row.cluster_null_q025, row.cluster_null_q975, row.p_value_mean_cluster),
                        ("year_season_cluster_shift_15d", row.season_cluster_null_mean_abs_distance, row.season_cluster_null_q025, row.season_cluster_null_q975, row.p_value_mean_season_cluster),
                    ],
                ),
                (
                    "observed_median_abs_distance",
                    row.observed_median_abs_distance,
                    [
                        ("year_month_independent", row.null_median, np.nan, np.nan, row.p_value_median),
                        ("year_month_cluster_rotation", row.cluster_null_median, np.nan, np.nan, row.p_value_median_cluster),
                        ("year_season_cluster_shift_15d", row.season_cluster_null_median, np.nan, np.nan, row.p_value_median_season_cluster),
                    ],
                ),
            ]
            for statistic, observed, models in distance_tests:
                for null_model, model_mean, model_q025, model_q975, model_p in models:
                    rows.append(
                        {
                            "analysis_family": "distance_null",
                            "null_model": null_model,
                            "event_family": row.event_family,
                            "statistic": statistic,
                            "observed_value": observed,
                            "null_mean": model_mean,
                            "null_q025": model_q025,
                            "null_q975": model_q975,
                            "p_value": model_p,
                            "null_interpretation": row.interpretation,
                        }
                    )

    if not coincidence_df.empty:
        for row in coincidence_df.itertuples(index=False):
            for null_model, model_mean, model_q025, model_q975, model_p in [
                ("year_month_independent", row.null_mean_count, row.null_q025_count, row.null_q975_count, row.p_value),
                (
                    "year_month_cluster_rotation",
                    row.cluster_null_mean_count,
                    row.cluster_null_q025_count,
                    row.cluster_null_q975_count,
                    row.p_value_cluster,
                ),
                (
                    "year_season_cluster_shift_15d",
                    row.season_cluster_null_mean_count,
                    row.season_cluster_null_q025_count,
                    row.season_cluster_null_q975_count,
                    row.p_value_season_cluster,
                ),
            ]:
                rows.append(
                    {
                        "analysis_family": "coincidence_null",
                        "null_model": null_model,
                        "event_family": row.event_family,
                        "statistic": row.window_definition,
                        "observed_value": row.observed_count,
                        "null_mean": model_mean,
                        "null_q025": model_q025,
                        "null_q975": model_q975,
                        "p_value": model_p,
                        "null_interpretation": row.interpretation,
                    }
                )

    out = pd.DataFrame(
        rows,
        columns=[
            "analysis_family",
            "null_model",
            "event_family",
            "statistic",
            "observed_value",
            "null_mean",
            "null_q025",
            "null_q975",
            "p_value",
            "null_interpretation",
        ],
    )
    out = out.rename(columns={"p_value": "p_value_nominal"})
    model_suffix = {
        "year_month_independent": "", "year_month_cluster_rotation": "_cluster",
        "year_season_cluster_shift_15d": "_season_cluster",
    }
    for index, result in out.iterrows():
        frame = distance_df if result["analysis_family"] == "distance_null" else coincidence_df
        matching = frame[frame["event_family"] == result["event_family"]]
        if result["analysis_family"] == "coincidence_null":
            matching = matching[matching["window_definition"] == result["statistic"]]
            key = "p_value" + model_suffix[result["null_model"]]
        else:
            metric = "median" if result["statistic"] == "observed_median_abs_distance" else "mean"
            key = f"p_value_{metric}" + model_suffix[result["null_model"]]
        source = matching.iloc[0]
        for field in ("mc_low", "mc_high", "iterations", "exceedances"):
            if f"{key}_{field}" in frame:
                out.loc[index, field] = source[f"{key}_{field}"]
        if "outbreak_count" in frame:
            out.loc[index, "outbreak_count"] = source["outbreak_count"]
    out["p_value_holm"] = holm_adjust_pvalues(out["p_value_nominal"].to_numpy(dtype=float))
    if "mc_low" in out:
        out["p_value_holm_mc_low"] = holm_adjust_pvalues(out["mc_low"])
        out["p_value_holm_mc_high"] = holm_adjust_pvalues(out["mc_high"])
    out["interpretation"] = np.where(
        out["p_value_holm"] <= 0.05,
        "Exploratory result remains below 0.05 after Holm adjustment.",
        "Not below 0.05 after Holm adjustment; treat as exploratory.",
    )
    if "p_value_holm_mc_low" in out:
        uncertain = (out["p_value_holm_mc_low"] <= 0.05) & (out["p_value_holm_mc_high"] >= 0.05)
        out.loc[uncertain, "interpretation"] = "Monte Carlo uncertainty spans the adjusted 0.05 threshold; do not make a definite threshold decision."
    return out


def best_text_for_event(key_results: pd.DataFrame, event_family: str) -> str:
    chunks: list[str] = []
    for null_model in ("year_month_independent", "year_month_cluster_rotation", "year_season_cluster_shift_15d"):
        for analysis_family in ("distance_null", "coincidence_null"):
            rows = key_results.loc[
                (key_results["event_family"] == event_family)
                & (key_results["analysis_family"] == analysis_family)
                & (key_results["null_model"] == null_model)
            ].dropna(subset=["p_value_holm"])
            if rows.empty:
                continue
            best = rows.sort_values("p_value_holm").iloc[0]
            label = "distance" if analysis_family == "distance_null" else "coincidence"
            model_label = {
                "year_month_independent": "independent dates",
                "year_month_cluster_rotation": "month-cluster rotations",
                "year_season_cluster_shift_15d": "year-season cluster shifts",
            }[null_model]
            chunks.append(
                f"{model_label}, {label} {best['statistic']}: observed {best['observed_value']:.2f} vs null {best['null_mean']:.2f} "
                f"(nominal p={best['p_value_nominal']:.6f}; Holm p={best['p_value_holm']:.6f})"
            )
    if not chunks:
        return "No available result rows for this event family."
    return "; ".join(chunks)


def interpret_rescue(key_results: pd.DataFrame) -> str:
    pvals = key_results["p_value_holm"].dropna().to_numpy(dtype=float) if not key_results.empty else np.array([])
    if pvals.size == 0:
        return "Insufficient outputs to judge whether the author-list branch rescues the narrative."

    if "p_value_holm_mc_high" in key_results:
        definite = int((key_results["p_value_holm_mc_high"] < 0.05).sum())
        uncertain = int(
            ((key_results["p_value_holm_mc_low"] <= 0.05) & (key_results["p_value_holm_mc_high"] >= 0.05)).sum()
        )
        return (
            f"{int((pvals <= 0.05).sum())} exploratory adjusted estimates are at or below 0.05; "
            f"{definite} remain below 0.05 at their simultaneous Monte Carlo upper bounds, and "
            f"{uncertain} intervals span 0.05. These tests are neither causal nor confirmatory."
        )
    strong = sum(v <= 0.05 for v in pvals)
    if strong >= 3:
        return f"{strong} exploratory tests remain below 0.05 after Holm adjustment; this is not causal or confirmatory evidence."
    if strong >= 1:
        return f"{strong} exploratory test remains below 0.05 after Holm adjustment; this does not establish causality."
    return "No test remains below 0.05 after Holm adjustment; this branch does not provide confirmatory evidence."


def hss_cir_followup_recommendation(key_results: pd.DataFrame) -> str:
    coincidence = key_results.loc[key_results["analysis_family"] == "coincidence_null"] if not key_results.empty else pd.DataFrame()
    cir_rows = coincidence.loc[coincidence["event_family"] == "CIR_arrival_catalog"]
    hss_rows = coincidence.loc[coincidence["event_family"] == "major_HSS_declining_phase_catalog"]
    cir_best = float(cir_rows["p_value_holm"].min()) if not cir_rows.empty else np.nan
    hss_best = float(hss_rows["p_value_holm"].min()) if not hss_rows.empty else np.nan

    if np.isfinite(cir_best) and cir_best <= 0.10:
        return "A direct CIR arrival-keyed event study may clarify timing; the adjusted result is exploratory and does not establish an effect."
    if np.isfinite(hss_best) and hss_best <= 0.10:
        return "A direct HSS arrival/decline study may clarify timing; the adjusted result is exploratory and does not establish an effect."
    return "A direct CIR/HSS timing study could be considered as a separate exploratory analysis, not as a follow-up justified by adjusted significance here."


def main() -> int:
    KEY_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    distance_df = safe_read_csv(DISTANCE_SUMMARY_PATH)
    coincidence_df = safe_read_csv(COINCIDENCE_SUMMARY_PATH)
    author_type_df = safe_read_csv(AUTHOR_TYPE_SUMMARY_PATH)
    agreement_df = safe_read_csv(AGREEMENT_SUMMARY_PATH)

    key = build_key_results(distance_df, coincidence_df)
    key.to_csv(KEY_RESULTS_PATH, index=False)

    hcs_text = best_text_for_event(key, "HCS_author_catalog")
    cir_text = best_text_for_event(key, "CIR_arrival_catalog")
    icme_text = best_text_for_event(key, "ICME_impact_catalog")
    hss_text = best_text_for_event(key, "major_HSS_declining_phase_catalog")

    rescue_text = interpret_rescue(key)
    followup_text = hss_cir_followup_recommendation(key)

    lines = [
        "# Author Outbreak Branch Summary",
        "",
        "This summary treats the supplement author outbreak list as the fixed event set.",
        "All tests in this post-hoc branch are exploratory; no confirmatory primary endpoint was prespecified.",
        "Independent nulls preserve year-month counts; month rotations preserve within-month spacing; year-season shifts preserve within-year cluster spacing across month boundaries with a shared +/-15-day shift.",
        "Holm adjustment covers all 87 tests across all three null models and all distance/coincidence specifications in this branch.",
        "Each null uses 50,000 replicates; retained draws are shared across specifications within a family. Monte Carlo intervals use Clopper-Pearson bounds with Bonferroni coverage across 87 tails; Holm-transformed endpoint bounds are reported separately from adjusted estimates.",
        "ICME tests use the same direct Richardson-Cane catalog and only post-1996 outbreak starts; counts and denominators are family-specific.",
        f"The key-results CSV contains {int(key['p_value_nominal'].notna().sum())} nominal and Holm-adjusted tests.",
        "",
        "## Inputs",
        f"- Distance summary present: {not distance_df.empty}",
        f"- Coincidence summary present: {not coincidence_df.empty}",
        f"- Author type summary present: {not author_type_df.empty}",
        f"- Agreement summary present: {not agreement_df.empty}",
        "",
        "## Key Questions",
        "1. Do the author-provided outbreak dates cluster unusually near HCS crossings?",
        f"- {hcs_text}",
        "2. Do they cluster unusually near CIR arrivals?",
        f"- {cir_text}",
        "3. Do they cluster unusually near ICME impacts?",
        f"- {icme_text}",
        "4. Do they cluster unusually near major-HSS declining phases?",
        f"- {hss_text}",
        "5. Does taking the author outbreak list at face value rescue the paper's narrative?",
        f"- {rescue_text}",
        "6. Does this justify an additional direct HSS/CIR arrival event study?",
        f"- {followup_text}",
    ]

    if not author_type_df.empty:
        lines.append("")
        lines.append("## Author Outbreak Type Distribution")
        for row in author_type_df.itertuples(index=False):
            lines.append(f"- {row.author_type}: {int(row.outbreak_count)} ({float(row.percent_of_total):.1f}%)")

    if not agreement_df.empty:
        row = agreement_df.iloc[0]
        lines.append("")
        lines.append("## Existing Author-vs-Independent Agreement Context")
        lines.append(f"- Total compared: {int(row['total_compared'])}")
        lines.append(f"- Exact agreement count: {int(row['exact_agreement_count'])}")
        lines.append(f"- Exact agreement percent: {float(row['exact_agreement_percent']):.2f}%")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Saved: {KEY_RESULTS_PATH}")
    print(f"Saved: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
