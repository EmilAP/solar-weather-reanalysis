from __future__ import annotations

from pathlib import Path

from common import (
    ROOT,
    fetch_html_and_parse,
    load_sources,
    make_logger,
    make_session,
    result_to_dict,
    write_manifest,
)


def main() -> int:
    logger = make_logger("05_get_hcs_catalog")
    session = make_session()
    cfg = load_sources()["hcs"]
    raw_dir = ROOT / "data" / "raw" / "hcs"

    downloads = []
    success_count = 0
    for idx, url in enumerate(cfg["candidate_urls"], start=1):
        html = raw_dir / f"candidate_{idx}.html"
        parsed = raw_dir / f"candidate_{idx}.parsed.txt"
        res = fetch_html_and_parse(session, url, html, parsed, logger)
        downloads.append(result_to_dict(res))
        if res.ok:
            success_count += 1

    gap_note = raw_dir / "GAP_HCS_CATALOG.txt"
    if success_count == 0:
        gap_note.write_text(
            "No candidate public HCS list URL was downloadable automatically.\n"
            "Manual action required: identify the exact HCS crossing/public list cited in the paper and place it in this folder.\n",
            encoding="utf-8",
        )
    elif gap_note.exists():
        gap_note.unlink()

    payload = {
        "script": "05_get_hcs_catalog.py",
        "downloads": downloads,
        "gap_note": str(gap_note.relative_to(ROOT)) if gap_note.exists() else None,
        "ok": success_count > 0,
        "manual_required": success_count == 0,
    }
    write_manifest("05_get_hcs_catalog", payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
