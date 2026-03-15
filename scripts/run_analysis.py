from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime

from _utils import make_logger


SCRIPTS = [
    "11_ingest_author_hcs.py",
    "12_parse_spc_tornado.py",
    "13_parse_omni.py",
    "14_parse_icme.py",
    "15_build_daily_tornado_series.py",
    "16_reproduce_paper_hcs_spe.py",
    "17_build_independent_hcs_from_omni.py",
    "18_detect_cir_hss_events.py",
    "19_run_stricter_event_study.py",
    "20_run_daily_models.py",
    "21_compare_event_catalogs.py",
    "22_generate_figures_and_tables.py",
    "23_write_summary_report.py",
]


def main() -> int:
    logger = make_logger("run_analysis")
    results = []
    run_id = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    for script in SCRIPTS:
        start = time.time()
        proc = subprocess.run([sys.executable, f"scripts/{script}"], text=True, capture_output=True, check=False)
        elapsed = round(time.time() - start, 3)
        results.append(
            {
                "script": script,
                "return_code": proc.returncode,
                "elapsed_seconds": elapsed,
                "stdout_tail": proc.stdout[-3000:],
                "stderr_tail": proc.stderr[-3000:],
            }
        )
        logger.info("%s completed with code=%s in %.3fs", script, proc.returncode, elapsed)
        if proc.returncode != 0:
            logger.error("Stopping pipeline at %s", script)
            break

    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "results": results,
        "ok": all(item["return_code"] == 0 for item in results) and len(results) == len(SCRIPTS),
    }
    out = "data/processed/analysis_run_latest.json"
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    logger.info("Analysis run summary written to %s", out)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())