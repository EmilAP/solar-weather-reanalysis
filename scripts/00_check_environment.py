from __future__ import annotations

import importlib
import json
import platform
import sys
from pathlib import Path

from common import ROOT, make_logger, write_manifest


REQUIRED_DIRS = [
    ROOT / "config",
    ROOT / "data" / "raw" / "spc_tornado",
    ROOT / "data" / "raw" / "ncei_storm_events",
    ROOT / "data" / "raw" / "omni",
    ROOT / "data" / "raw" / "icme",
    ROOT / "data" / "raw" / "hcs",
    ROOT / "data" / "raw" / "green_corona",
    ROOT / "data" / "raw" / "era5",
    ROOT / "data" / "raw" / "spc_outlooks",
    ROOT / "data" / "interim",
    ROOT / "data" / "processed",
    ROOT / "data" / "logs",
    ROOT / "data" / "manifests",
    ROOT / "docs",
    ROOT / "scripts",
]


def main() -> int:
    logger = make_logger("00_check_environment")
    logger.info("Checking project environment")

    missing_dirs = [str(p) for p in REQUIRED_DIRS if not p.exists()]
    required_modules = ["urllib.request", "json", "logging"]
    import_status: dict[str, bool] = {}

    for module_name in required_modules:
        try:
            importlib.import_module(module_name)
            import_status[module_name] = True
        except Exception:  # noqa: BLE001
            import_status[module_name] = False

    payload = {
        "script": "00_check_environment.py",
        "python_version": sys.version,
        "platform": platform.platform(),
        "missing_dirs": missing_dirs,
        "imports": import_status,
        "ok": not missing_dirs and all(import_status.values()),
    }

    write_manifest("00_check_environment", payload)
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
