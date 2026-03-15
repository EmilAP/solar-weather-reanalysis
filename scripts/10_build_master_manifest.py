from __future__ import annotations

import json
from pathlib import Path

from common import ROOT, make_logger


def main() -> int:
    logger = make_logger("10_build_master_manifest")
    manifest_dir = ROOT / "data" / "manifests"
    master = {
        "manifests": [],
        "ok_count": 0,
        "fail_count": 0,
    }

    for path in sorted(manifest_dir.glob("*.json")):
        if path.name == "master_manifest.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        ok = bool(payload.get("ok", payload.get("overall_ok", False)))
        master["manifests"].append(
            {
                "name": path.stem,
                "path": str(path.relative_to(ROOT)),
                "ok": ok,
                "generated_at": payload.get("generated_at"),
            }
        )
        if ok:
            master["ok_count"] += 1
        else:
            master["fail_count"] += 1

    out = manifest_dir / "master_manifest.json"
    out.write_text(json.dumps(master, indent=2), encoding="utf-8")
    logger.info("Master manifest written: %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
