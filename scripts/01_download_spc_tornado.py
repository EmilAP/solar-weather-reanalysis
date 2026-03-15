from __future__ import annotations

import csv
import re

from common import (
    ROOT,
    download_binary,
    fetch_html_and_parse,
    load_sources,
    make_logger,
    make_session,
    result_to_dict,
    validate_year_range,
    write_manifest,
)


YEAR_PATTERN = re.compile(r"^(19|20)\d{2}$")


def main() -> int:
    logger = make_logger("01_download_spc_tornado")
    session = make_session()
    cfg = load_sources()["spc_tornado"]

    raw_dir = ROOT / "data" / "raw" / "spc_tornado"
    csv_path = raw_dir / "spc_actual_tornadoes_1950_2023.csv"
    html_path = raw_dir / "spc_wcm_index.html"
    parsed_path = raw_dir / "spc_wcm_index.parsed.txt"

    tornado_res = fetch_html_and_parse(
        session,
        cfg["metadata_page"],
        html_path,
        parsed_path,
        logger,
    )
    csv_res = download_binary(session, cfg["tornado_csv_url"], csv_path, logger)

    years: list[int] = []
    row_count = 0
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_count += 1
                for key in ("yr", "year", "Year", "YR"):
                    val = row.get(key)
                    if val and YEAR_PATTERN.match(val.strip()):
                        years.append(int(val))
                        break

    year_ok, year_msg = validate_year_range(years, 1950, 2023)
    payload = {
        "script": "01_download_spc_tornado.py",
        "downloads": [result_to_dict(tornado_res), result_to_dict(csv_res)],
        "row_count": row_count,
        "year_validation": {"ok": year_ok, "message": year_msg},
        "ok": tornado_res.ok and csv_res.ok and row_count > 0,
    }
    write_manifest("01_download_spc_tornado", payload)
    logger.info("Rows: %s; %s", row_count, year_msg)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
