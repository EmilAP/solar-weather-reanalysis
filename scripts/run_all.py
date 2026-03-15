from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from common import ROOT, make_logger


SCRIPTS = [
    "00_check_environment.py",
    "01_download_spc_tornado.py",
    "02_download_ncei_storm_events.py",
    "03_download_omni.py",
    "04_download_icme.py",
    "05_get_hcs_catalog.py",
    "06_get_green_corona.py",
    "07_prepare_era5_requests.py",
    "08_get_spc_outlooks.py",
    "09_validate_downloads.py",
    "10_build_master_manifest.py",
]


def utc_stamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def run_script(script_name: str, logger_name: str) -> dict[str, Any]:
    scripts_dir = ROOT / "scripts"
    script_path = scripts_dir / script_name

    start = time.time()
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed = round(time.time() - start, 3)

    return {
        "script": script_name,
        "command": f"{sys.executable} {script_path}",
        "return_code": proc.returncode,
        "ok": proc.returncode == 0,
        "elapsed_seconds": elapsed,
        "stdout_tail": proc.stdout[-4000:] if proc.stdout else "",
        "stderr_tail": proc.stderr[-4000:] if proc.stderr else "",
    }


def main() -> int:
    logger = make_logger("run_all")
    processed_dir = ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    run_id = utc_stamp()
    logger.info("Starting full pipeline run: %s", run_id)

    results: list[dict[str, Any]] = []
    for script in SCRIPTS:
        logger.info("Running %s", script)
        result = run_script(script, "run_all")
        results.append(result)
        logger.info(
            "%s finished with code=%d in %.3fs",
            script,
            result["return_code"],
            result["elapsed_seconds"],
        )

    all_ok = all(item["ok"] for item in results)
    report = {
        "run_id": run_id,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "workspace": str(ROOT),
        "all_ok": all_ok,
        "step_count": len(results),
        "ok_count": sum(1 for r in results if r["ok"]),
        "fail_count": sum(1 for r in results if not r["ok"]),
        "results": results,
    }

    out_path = processed_dir / f"pipeline_run_{run_id}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Run report written: %s", out_path)

    latest_path = processed_dir / "pipeline_run_latest.json"
    latest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Updated latest report: %s", latest_path)

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
