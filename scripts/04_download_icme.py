from __future__ import annotations

import csv
import re
from pathlib import Path

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


ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", flags=re.IGNORECASE | re.DOTALL)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", flags=re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def convert_txt_to_csv(txt_path: Path, csv_path: Path) -> tuple[int, list[int]]:
    years: list[int] = []
    rows = 0
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with txt_path.open("r", encoding="utf-8", errors="ignore") as src, csv_path.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        writer = csv.writer(dst)
        writer.writerow(["raw_line"])
        for line in src:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            writer.writerow([stripped])
            rows += 1
            token = stripped[:4]
            if token.isdigit():
                years.append(int(token))

    return rows, years


def convert_html_to_csv(html_path: Path, csv_path: Path) -> tuple[int, list[int]]:
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    rows = 0
    years: list[int] = []
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst)
        writer.writerow(["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "c10"])
        for tr_match in ROW_RE.findall(html):
            cells = CELL_RE.findall(tr_match)
            if not cells:
                continue
            cleaned = [TAG_RE.sub("", c).replace("\xa0", " ").strip() for c in cells]
            if not any(cleaned):
                continue
            writer.writerow(cleaned)
            rows += 1
            year_token = cleaned[0][:4] if cleaned and cleaned[0] else ""
            if year_token.isdigit():
                years.append(int(year_token))

    return rows, years


def main() -> int:
    logger = make_logger("04_download_icme")
    session = make_session()
    cfg = load_sources()["icme"]
    raw_dir = ROOT / "data" / "raw" / "icme"

    html = raw_dir / "icmetable2.html"
    parsed = raw_dir / "icmetable2.parsed.txt"
    txt = raw_dir / "icmetable2.txt"
    csv_out = raw_dir / "icmetable2.csv"

    html_res = fetch_html_and_parse(session, cfg["richardson_cane_html"], html, parsed, logger)
    txt_res = download_binary(session, cfg["richardson_cane_txt"], txt, logger)

    csv_rows = 0
    years: list[int] = []
    if txt_res.ok and txt.exists():
        csv_rows, years = convert_txt_to_csv(txt, csv_out)
    elif html_res.ok and html.exists():
        csv_rows, years = convert_html_to_csv(html, csv_out)

    year_ok, year_msg = validate_year_range(years, 1963, 2023)
    payload = {
        "script": "04_download_icme.py",
        "downloads": [result_to_dict(html_res), result_to_dict(txt_res)],
        "converted_csv": str(csv_out.relative_to(ROOT)) if csv_out.exists() else None,
        "row_count": csv_rows,
        "year_validation": {"ok": year_ok, "message": year_msg},
        "ok": html_res.ok and csv_rows > 0,
    }
    write_manifest("04_download_icme", payload)
    logger.info("ICME rows: %d", csv_rows)
    logger.info("%s", year_msg)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
