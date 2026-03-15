from __future__ import annotations

import argparse
import re
from urllib.parse import urljoin

from common import (
    ROOT,
    download_binary,
    extract_links,
    fetch_html_and_parse,
    load_sources,
    make_logger,
    make_session,
    result_to_dict,
    sleep_briefly,
    validate_year_range,
    write_manifest,
)


YEAR_RE = re.compile(r"_d(\d{4})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Limit number of files for test runs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = make_logger("02_download_ncei_storm_events")
    session = make_session()
    cfg = load_sources()["ncei_storm_events"]

    raw_dir = ROOT / "data" / "raw" / "ncei_storm_events"
    index_html = raw_dir / "stormevents_index.html"
    index_parsed = raw_dir / "stormevents_index.parsed.txt"

    index_res = fetch_html_and_parse(session, cfg["index_url"], index_html, index_parsed, logger)
    if not index_res.ok:
        payload = {
            "script": "02_download_ncei_storm_events.py",
            "downloads": [result_to_dict(index_res)],
            "ok": False,
        }
        write_manifest("02_download_ncei_storm_events", payload)
        return 1

    html_text = index_html.read_text(encoding="utf-8", errors="ignore")
    files: list[tuple[str, int]] = []
    for href in extract_links(html_text):
        href = href.strip()
        if cfg["file_pattern"] not in href or not href.endswith(".csv.gz"):
            continue
        match = YEAR_RE.search(href)
        if not match:
            continue
        year = int(match.group(1))
        if cfg["year_start"] <= year <= cfg["year_end"]:
            files.append((href, year))

    files = sorted(set(files), key=lambda x: x[1])
    if args.limit and args.limit > 0:
        files = files[: args.limit]

    downloads = [result_to_dict(index_res)]
    years: list[int] = []
    for href, year in files:
        url = urljoin(cfg["index_url"], href)
        out_path = raw_dir / href
        bin_res = download_binary(session, url, out_path, logger)
        years.append(year) if bin_res.ok else None
        downloads.append(result_to_dict(bin_res))
        sleep_briefly(0.1)

    year_ok, year_msg = validate_year_range(years, cfg["year_start"], cfg["year_end"])
    payload = {
        "script": "02_download_ncei_storm_events.py",
        "requested_files": len(files),
        "downloaded_years": sorted(set(years)),
        "year_validation": {"ok": year_ok, "message": year_msg},
        "downloads": downloads,
        "ok": index_res.ok and all(item["ok"] for item in downloads[1:]) if files else False,
    }
    write_manifest("02_download_ncei_storm_events", payload)
    logger.info("Requested files: %d", len(files))
    logger.info("%s", year_msg)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
