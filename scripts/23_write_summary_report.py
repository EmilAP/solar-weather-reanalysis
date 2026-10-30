from __future__ import annotations

from pathlib import Path

import pandas as pd

from _utils import REPORT_DIR, make_logger, write_script_manifest


def answer_from_summary(summary: pd.DataFrame, source: str, metric: str = "all_tornadoes") -> str:
    subset = summary[(summary["source"] == source) & (summary["metric"] == metric)]
    if subset.empty:
        return "Not evaluated in this run."
    row = subset.sort_values("empirical_p_max").iloc[0]
    return (
        f"Maximum raw daily mean: {row['observed_max_abs_daily_effect']:.3f} at lag {int(row['lag_of_max_abs_effect'])}; "
        f"lag-scan Monte Carlo p={row['empirical_p_max']:.4f}, Holm p={row['p_value_holm']:.4f} "
        "across the 16 source/outcome tests. Exploratory, not causal evidence."
    )


def main() -> int:
    logger = make_logger("23_write_summary_report")
    report_path = REPORT_DIR / "analysis_summary.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    strict_path = Path("data/derived/spe/strict_event_study_summary.csv")
    model_path = Path("data/derived/models/model_coefficients.csv")
    compare_path = Path("data/derived/tables/event_catalog_overlap_summary.csv")
    paper_path = Path("data/derived/spe/paper_author_hcs_observed.csv")

    strict = pd.read_csv(strict_path) if strict_path.exists() else pd.DataFrame()
    model = pd.read_csv(model_path) if model_path.exists() else pd.DataFrame()
    compare = pd.read_csv(compare_path) if compare_path.exists() else pd.DataFrame()

    lines = [
        "# Analysis Summary",
        "",
        "## Executive Summary",
        "",
        "This report separates paper-style replication from the stricter reanalysis branch.",
        "",
        "## Validation Questions",
        "",
        "1. Exact replication of the source article has not been established; event/date conventions remain distinct.",
        "2. Across-event totals and daily means have identical shapes with a fixed event population; neither is an across-lag running sum.",
        f"3. Does it remain under stricter season-matched permutation nulls? {answer_from_summary(strict, 'author_hcs') if not strict.empty else 'Not yet evaluated.'}",
        f"4. Does it remain using independently reconstructed HCS events? {answer_from_summary(strict, 'reconstructed_hcs') if not strict.empty else 'Not yet evaluated.'}",
        f"5. Does it appear stronger for HCS, CIR, or HSS proxy events? {strict.sort_values('empirical_p_max').head(3).to_dict(orient='records') if not strict.empty else 'Not yet evaluated.'}",
        f"6. How sensitive is it to outbreak definition and lag window? {'Inspect strict_event_study_summary.csv and model coefficients for sensitivity by metric and lag.' if strict_path.exists() else 'Not yet evaluated.'}",
        "",
        "## What Replicates",
        "",
        "- The paper-style branch reproduces the event-centered cumulative framework using the author HCS list when available.",
        "- The stricter branch preserves the same event windows but evaluates daily rates with stronger null models.",
        "",
        "## What Does Not Hold Up Automatically",
        "",
        "- Visual peaks require an explicit lag-scanning and analysis-family reference distribution.",
        "- Reconstructed HCS and CIR/HSS proxies must be treated as separate hypotheses, not interchangeable proofs of the same mechanism.",
        "",
        "## Likely Methodological Traps",
        "",
        "- Confusing totals across events with running sums across lags.",
        "- Overlapping windows and non-independence of event-centered samples.",
        "- Weak null models based on unconstrained random dates.",
        "- Multiple-comparison risk across lags, metrics, and event definitions.",
        "- Circular event classification if solar proxies are tuned against tornado outcomes.",
        "",
        "## Inputs Used",
        "",
        f"- Strict event study summary present: {strict_path.exists()}",
        f"- Model coefficient summary present: {model_path.exists()}",
        f"- Catalog comparison summary present: {compare_path.exists()}",
        f"- Paper-style observed SPE present: {paper_path.exists()}",
    ]

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_script_manifest(
        "23_write_summary_report.py",
        [str(strict_path), str(model_path), str(compare_path), str(paper_path)],
        {"report": str(report_path.relative_to(Path(__file__).resolve().parents[1]))},
        {"line_count": len(lines)},
    )
    logger.info("Wrote summary report to %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
