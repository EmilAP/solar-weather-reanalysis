from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "papers" / "extracted" / "supplement_table_s1_outbreaks_extracted.csv"
OUTPUT_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_outbreaks.csv"
REPORT_PATH = ROOT / "data" / "derived" / "reports" / "supplement_table_s1_preparation.md"

MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_RANGE_RE = re.compile(rf"(?P<left>{MONTH_RE}\.?\s+\d{{1,2}})\s*[\-–]\s*(?P<right>\d{{1,2}}\s*{MONTH_RE}\.?|{MONTH_RE}\.?\s+\d{{1,2}})", re.IGNORECASE)
SINGLE_DATE_RE = re.compile(rf"(?P<d>{MONTH_RE}\.?\s+\d{{1,2}})\s*(?P<y>\d{{4}})", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def parse_date_text(date_text: object) -> tuple[str, str]:
    text = str(date_text or "").strip().replace("–", "-")
    if not text:
        return "", ""

    y_match = YEAR_RE.search(text)
    year = y_match.group(1) if y_match else ""

    range_match = DATE_RANGE_RE.search(text)
    if range_match and year:
        left = range_match.group("left").replace(".", "").strip()
        right = range_match.group("right").replace(".", "").strip()
        if re.match(r"^\d{1,2}\s+", right):
            # Right side like "1 Jun" -> normalize to "Jun 1"
            parts = right.split(maxsplit=1)
            right = f"{parts[1]} {parts[0]}"
        start = pd.to_datetime(f"{left} {year}", errors="coerce")
        end = pd.to_datetime(f"{right} {year}", errors="coerce")
        if pd.notna(start) and pd.notna(end):
            return str(start.date()), str(end.date())

    single = SINGLE_DATE_RE.search(text)
    if single:
        d = single.group("d").replace(".", "")
        y = single.group("y")
        dt = pd.to_datetime(f"{d} {y}", errors="coerce")
        if pd.notna(dt):
            s = str(dt.date())
            return s, s

    dt = pd.to_datetime(text, errors="coerce")
    if pd.notna(dt):
        s = str(dt.date())
        return s, s

    return "", ""


def parse_tornado_count(text: object) -> float:
    s = str(text or "")
    nums = [int(n) for n in re.findall(r"\d+", s)]
    if not nums:
        return float("nan")
    return float(max(nums))


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing extracted supplement CSV: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)
    input_count = int(len(df))

    if "parse_status" in df.columns:
        exclude_mask = df["parse_status"].astype(str).str.strip().eq("needs_manual_review")
    else:
        exclude_mask = pd.Series([False] * len(df), index=df.index)

    excluded = df.loc[exclude_mask].copy()
    retained = df.loc[~exclude_mask].copy()

    # Preserve retained rows/columns; add compatibility columns for downstream scripts.
    if "raw_row_text" not in retained.columns:
        retained["raw_row_text"] = retained.get("raw_row", "")
    if "outbreak_date_text" not in retained.columns:
        retained["outbreak_date_text"] = retained.get("date_text", "")

    starts = []
    ends = []
    for txt in retained.get("date_text", pd.Series(dtype=object)):
        s, e = parse_date_text(txt)
        starts.append(s)
        ends.append(e)
    retained["outbreak_date_start"] = starts
    retained["outbreak_date_end"] = ends

    retained["tornado_count_numeric"] = retained.get("tornado_counts_text", pd.Series(dtype=object)).map(parse_tornado_count)
    retained["key_event_type_text"] = retained.get("key_event_text", "")
    retained["notes"] = retained.get("notes", "")

    retained.to_csv(OUTPUT_PATH, index=False)

    excluded_status_values = sorted(set(excluded.get("parse_status", pd.Series(dtype=object)).astype(str).tolist())) if not excluded.empty else []

    lines = [
        "# Supplement Table S1 Preparation",
        "",
        f"- Input row count: {input_count}",
        f"- Excluded row count: {int(exclude_mask.sum())}",
        f"- Retained row count: {int((~exclude_mask).sum())}",
        f"- Excluded parse_status categories: {', '.join(excluded_status_values) if excluded_status_values else 'none'}",
        "",
        "Excluded rows were withheld only temporarily pending manual review.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Saved: {OUTPUT_PATH}")
    print(f"Saved: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
