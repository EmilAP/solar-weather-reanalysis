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
    logger = make_logger("06_get_green_corona")
    session = make_session()
    cfg = load_sources()["green_corona"]
    raw_dir = ROOT / "data" / "raw" / "green_corona"

    downloads = []
    success_count = 0
    for idx, url in enumerate(cfg["candidate_urls"], start=1):
        html = raw_dir / f"candidate_{idx}.html"
        parsed = raw_dir / f"candidate_{idx}.parsed.txt"
        res = fetch_html_and_parse(session, url, html, parsed, logger)
        downloads.append(result_to_dict(res))
        if res.ok:
            success_count += 1

    manual_note = raw_dir / "MANUAL_REQUIRED_GREEN_CORONA.txt"
    if success_count == 0:
        manual_note.write_text(
            "Automatic download from candidate official sources failed.\n"
            "Manual action required: obtain official green coronal line dataset cited in paper and place raw files in this folder.\n",
            encoding="utf-8",
        )
    elif manual_note.exists():
        manual_note.unlink()

    payload = {
        "script": "06_get_green_corona.py",
        "downloads": downloads,
        "manual_note": str(manual_note.relative_to(ROOT)) if manual_note.exists() else None,
        "ok": success_count > 0,
        "manual_required": success_count == 0,
    }
    write_manifest("06_get_green_corona", payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
