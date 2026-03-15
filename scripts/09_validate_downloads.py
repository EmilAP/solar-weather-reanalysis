from __future__ import annotations

import json
from pathlib import Path

from common import ROOT, make_logger, write_manifest


EXPECTED = [
    "00_check_environment",
    "01_download_spc_tornado",
    "02_download_ncei_storm_events",
    "03_download_omni",
    "04_download_icme",
    "05_get_hcs_catalog",
    "06_get_green_corona",
    "07_prepare_era5_requests",
    "08_get_spc_outlooks",
]


def main() -> int:
    logger = make_logger("09_validate_downloads")
    manifest_dir = ROOT / "data" / "manifests"

    missing = []
    loaded: dict[str, dict] = {}
    for name in EXPECTED:
        path = manifest_dir / f"{name}.json"
        if not path.exists():
            missing.append(name)
            continue
        loaded[name] = json.loads(path.read_text(encoding="utf-8"))

    checks: list[dict[str, object]] = []

    for name, payload in loaded.items():
        checks.append({"dataset": name, "ok": bool(payload.get("ok", False))})

    overall_ok = not missing and all(item["ok"] for item in checks)
    report = {
        "script": "09_validate_downloads.py",
        "missing_manifests": missing,
        "checks": checks,
        "overall_ok": overall_ok,
        "datasets_checked": len(checks),
    }

    out = ROOT / "data" / "processed" / "validation_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_manifest("09_validate_downloads", report)
    logger.info("Validation overall_ok=%s", overall_ok)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
