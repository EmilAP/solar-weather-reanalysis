from __future__ import annotations

from common import (
    ROOT,
    download_binary,
    load_sources,
    make_logger,
    make_session,
    result_to_dict,
    validate_year_range,
    write_manifest,
)


def main() -> int:
    logger = make_logger("03_download_omni")
    session = make_session()
    cfg = load_sources()["omni"]
    raw_dir = ROOT / "data" / "raw" / "omni"

    results = []
    for filename in cfg["files"]:
        url = f"{cfg['base_url']}{filename}"
        out = raw_dir / filename
        res = download_binary(session, url, out, logger)
        results.append(res)

    years: list[int] = []
    data_path = raw_dir / "omni2_all_years.dat"
    if data_path.exists():
        with data_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    years.append(int(line[:4].strip()))
                except ValueError:
                    continue

    year_ok, year_msg = validate_year_range(
        years,
        cfg["expected_start_year"],
        cfg["expected_end_year"],
    )

    payload = {
        "script": "03_download_omni.py",
        "downloads": [result_to_dict(r) for r in results],
        "row_count": sum(1 for _ in data_path.open("r", encoding="utf-8", errors="ignore")) if data_path.exists() else 0,
        "year_validation": {"ok": year_ok, "message": year_msg},
        "ok": data_path.exists() and year_ok,
    }
    write_manifest("03_download_omni", payload)
    logger.info("%s", year_msg)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
