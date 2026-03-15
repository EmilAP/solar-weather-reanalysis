from __future__ import annotations

import csv

from common import (
    ROOT,
    extract_links,
    fetch_html_and_parse,
    load_sources,
    make_logger,
    make_session,
    result_to_dict,
    write_manifest,
)


def main() -> int:
    logger = make_logger("08_get_spc_outlooks")
    session = make_session()
    cfg = load_sources()["spc_outlooks"]
    raw_dir = ROOT / "data" / "raw" / "spc_outlooks"

    downloads = []
    link_rows: list[tuple[str, str]] = []
    for idx, url in enumerate(cfg["archive_urls"], start=1):
        html = raw_dir / f"archive_{idx}.html"
        parsed = raw_dir / f"archive_{idx}.parsed.txt"
        res = fetch_html_and_parse(session, url, html, parsed, logger)
        downloads.append(result_to_dict(res))
        if res.ok and html.exists():
            html_text = html.read_text(encoding="utf-8", errors="ignore")
            for href in extract_links(html_text):
                href = href.strip()
                if href:
                    link_rows.append((url, href))

    links_csv = raw_dir / "archive_links.csv"
    with links_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source_archive", "href"])
        writer.writerows(link_rows)

    payload = {
        "script": "08_get_spc_outlooks.py",
        "downloads": downloads,
        "extracted_links_csv": str(links_csv.relative_to(ROOT)),
        "link_count": len(link_rows),
        "ok": any(item["ok"] for item in downloads) and len(link_rows) > 0,
    }
    write_manifest("08_get_spc_outlooks", payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
