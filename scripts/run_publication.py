from __future__ import annotations

import json
import argparse
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "data" / "processed"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"

STEPS = [
    ("Ingest author HCS", "scripts/11_ingest_author_hcs.py"),
    ("Parse SPC tornadoes", "scripts/12_parse_spc_tornado.py"),
    ("Parse OMNI", "scripts/13_parse_omni.py"),
    ("Parse ICME", "scripts/14_parse_icme.py"),
    ("Build daily analysis table", "scripts/15_build_daily_tornado_series.py"),
    ("Reconstruct daily HCS", "scripts/26_reconstruct_hcs_from_omni.py"),
    ("Build paper-style HCS composites", "scripts/16_reproduce_paper_hcs_spe.py"),
    ("Build independent HCS catalog", "scripts/17_build_independent_hcs_from_omni.py"),
    ("Detect CIR and HSS events", "scripts/18_detect_cir_hss_events.py"),
    ("Strict event study", "scripts/19_run_stricter_event_study.py"),
    ("Fit daily models", "scripts/20_run_daily_models.py"),
    ("Compare event catalogs", "scripts/21_compare_event_catalogs.py"),
    ("Generate core figures and tables", "scripts/22_generate_figures_and_tables.py"),
    ("Write core summary report", "scripts/23_write_summary_report.py"),
    ("Author HCS fast null", "scripts/25_fast_spe_null.py"),
    ("Reconstructed HCS event study", "scripts/27_event_study_reconstructed_hcs.py"),
    ("Seasonal controls", "scripts/28_seasonal_control_event_studies.py"),
    ("Phase-randomized null", "scripts/29_phase_randomized_null_test.py"),
    ("Write methods metadata", "scripts/33_write_methods_metadata.py"),
    ("Reconcile author HCS counts", "scripts/35_reconcile_author_hcs_counts.py"),
    ("Block-bootstrap null", "scripts/37_block_bootstrap_null_test.py"),
    ("Lag-zero permutation p-values", "scripts/38_lag0_permutation_pvalues.py"),
    ("Extract supplement table", "scripts/39c_extract_supplement_table_pdfplumber.py"),
    ("Prepare supplement table", "scripts/39d_prepare_pdfplumber_outbreak_table.py"),
    ("Replicate outbreak types", "scripts/40_replicate_outbreak_type_branch.py"),
    ("Independent outbreak reclassification", "scripts/41_independent_outbreak_reclassification.py"),
    ("Compare outbreak classifications", "scripts/42_compare_author_vs_reclassified_outbreaks.py"),
    ("Outbreak distance nulls", "scripts/43_author_outbreak_event_distance_test.py"),
    ("Outbreak coincidence nulls", "scripts/44_author_outbreak_event_coincidence_test.py"),
    ("Summarize outbreak branch", "scripts/45_author_outbreak_branch_summary.py"),
    ("Coverage and timing sensitivities", "scripts/46_observation_sensitivity.py"),
    ("Plot core null comparisons", "scripts/30_plot_core_null_comparisons.py"),
    ("Plot catalog comparisons", "scripts/31_plot_catalog_comparison_figures.py"),
    ("Build final paper bundle", "scripts/32_build_paper_results_bundle.py"),
    ("Refresh methods metadata", "scripts/33_write_methods_metadata.py"),
    ("Reconcile final manuscript tables", "scripts/35_reconcile_author_hcs_counts.py"),
    ("Build figure index", "scripts/34_generate_paper_figure_index.py"),
    ("Export canonical manuscript results", "scripts/36_export_canonical_manuscript_results.py"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the staged local-data publication workflow.")
    parser.add_argument(
        "--start-at",
        choices=[Path(script).name for _, script in STEPS],
        help="Resume at a script whose prerequisites have already been generated.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    results: list[dict[str, object]] = []
    start_index = 0
    if args.start_at:
        start_index = next(index for index, (_, script) in enumerate(STEPS) if Path(script).name == args.start_at)
    steps_to_run = STEPS[start_index:]

    for label, script in steps_to_run:
        started = time.perf_counter()
        process = subprocess.run(
            [str(VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)), str(ROOT / script)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        result = {
            "step": label,
            "script": script,
            "return_code": process.returncode,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "stdout_tail": process.stdout[-3000:],
            "stderr_tail": process.stderr[-3000:],
        }
        results.append(result)
        print(f"{label}: exit={process.returncode} ({result['elapsed_seconds']}s)", flush=True)
        if process.returncode != 0:
            break

    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "uses_network": False,
        "started_at_step": steps_to_run[0][1] if steps_to_run else None,
        "steps": results,
        "ok": len(results) == len(steps_to_run) and all(step["return_code"] == 0 for step in results),
    }
    report_path = REPORT_DIR / "publication_run_latest.json"
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Run report: {report_path.relative_to(ROOT)}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())