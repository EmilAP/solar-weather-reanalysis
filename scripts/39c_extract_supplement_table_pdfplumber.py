from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "papers" / "tornado-paper-supplement.pdf"
CSV_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_outbreaks_pdfplumber.csv"
RAW_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_raw_pdfplumber.txt"
REPORT_PATH = ROOT / "data" / "derived" / "reports" / "supplement_table_s1_pdfplumber_extraction.md"

PAGE_START = 6
PAGE_END = 17

MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
LEADING_AUTHOR_RE = re.compile(r"^\s*([ABCD])\*?(?:\s|$)", re.IGNORECASE)
LEADING_UNKNOWN_RE = re.compile(r"^\s*\?(?:\s|$)")
DATE_RE = re.compile(
    rf"(\d{{1,2}}\s*{MONTH_RE}\.?\s*[\-\u2013]\s*\d{{1,2}}\s*{MONTH_RE}\.?\s*\d{{4}}|{MONTH_RE}\.?\s*\d{{1,2}}\s*[\-\u2013]\s*{MONTH_RE}\.?\s*\d{{1,2}},?\s*\d{{4}}|\d{{1,2}}\s*[\-\u2013]\s*\d{{1,2}}\s*{MONTH_RE}\.?\s*\d{{4}}|\d{{1,2}}\s*{MONTH_RE}\.?\s*\d{{4}}|{MONTH_RE}\.?\s*\d{{1,2}}\s*[\-\u2013]\s*\d{{1,2}},?\s*\d{{4}}|{MONTH_RE}\.?\s*\d{{1,2}},?\s*\d{{4}})",
    re.IGNORECASE,
)
TORNADO_COUNTS_RE = re.compile(r"\(([^)]*\d[^)]*)\)")
HEADER_LINE_RE = re.compile(r"^(table\s+s1|supplement|outbreak|type\s*[abcd]|date|location|key\s*event)", re.IGNORECASE)


def compact_text(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def parse_row_text(raw_row_text: str) -> dict[str, str]:
    text = compact_text(raw_row_text)

    author_type = ""
    m_author = LEADING_AUTHOR_RE.search(text)
    if m_author:
        author_type = m_author.group(1).upper()
    elif LEADING_UNKNOWN_RE.search(text):
        author_type = "?"

    outbreak_date_text = ""
    m_date = DATE_RE.search(text)
    if m_date:
        outbreak_date_text = compact_text(m_date.group(1))

    tornado_counts_text = ""
    m_counts = TORNADO_COUNTS_RE.search(text)
    if m_counts:
        tornado_counts_text = compact_text(m_counts.group(1))

    key_event_text = ""
    key_match = re.search(r"(HCS[^;,.]*|CIR[^;,.]*|ICME[^;,.]*|HSS[^;,.]*)", text, re.IGNORECASE)
    if key_match:
        key_event_text = compact_text(key_match.group(1))

    location_text = ""
    if outbreak_date_text:
        post_date = text.split(outbreak_date_text, maxsplit=1)
        if len(post_date) == 2:
            tail = post_date[1].strip()
            if tornado_counts_text:
                tail = tail.replace(f"({tornado_counts_text})", "").strip()
            if key_event_text:
                loc = re.split(re.escape(key_event_text), tail, maxsplit=1, flags=re.IGNORECASE)[0]
                location_text = compact_text(loc)
            else:
                location_text = compact_text(tail)

    notes = []
    if not author_type:
        notes.append("missing_author_type")
    if not outbreak_date_text:
        notes.append("missing_outbreak_date")
    if not tornado_counts_text:
        notes.append("missing_tornado_counts")
    if not location_text:
        notes.append("missing_location")
    if not key_event_text:
        notes.append("missing_key_event")

    return {
        "author_type": author_type,
        "outbreak_date_text": outbreak_date_text,
        "tornado_counts_text": tornado_counts_text,
        "location_text": location_text,
        "key_event_text": key_event_text,
        "notes": ";".join(notes),
        "raw_row_text": text,
    }


def rows_from_table(page_no: int, table: list[list[object]]) -> tuple[list[dict[str, object]], list[str], int]:
    rows: list[dict[str, object]] = []
    raw_lines: list[str] = []
    max_cols = 0

    for row in table:
        if row is None:
            continue
        cells = [compact_text(cell) for cell in row]
        if not any(cells):
            continue
        max_cols = max(max_cols, len(cells))

        row_text = " | ".join(cells)
        if HEADER_LINE_RE.match(compact_text(cells[0])):
            raw_lines.append(f"[page {page_no}] [table-header] {row_text}")
            continue

        parsed = parse_row_text(" ".join(cells))
        parsed["source_page"] = page_no
        rows.append(parsed)
        raw_lines.append(f"[page {page_no}] [table-row] {row_text}")

    return rows, raw_lines, max_cols


def rows_from_text(page_no: int, text: str) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    raw_lines: list[str] = []
    if not text:
        return rows, raw_lines

    lines = [compact_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    for line in lines:
        if line.isdigit():
            continue
        raw_lines.append(f"[page {page_no}] [text-line] {line}")

    buffer = ""
    for line in lines:
        if HEADER_LINE_RE.match(line):
            continue
        starts_row = bool(DATE_RE.search(line)) or bool(re.match(r"^\??\s*[ABCD]\*?\b", line, flags=re.IGNORECASE))
        if starts_row and buffer:
            parsed = parse_row_text(buffer)
            if parsed["outbreak_date_text"] or parsed["tornado_counts_text"] or parsed["key_event_text"]:
                parsed["source_page"] = page_no
                rows.append(parsed)
            buffer = line
        else:
            buffer = f"{buffer} {line}".strip()

    if buffer:
        parsed = parse_row_text(buffer)
        if parsed["outbreak_date_text"] or parsed["tornado_counts_text"] or parsed["key_event_text"]:
            parsed["source_page"] = page_no
            rows.append(parsed)

    filtered_rows = [row for row in rows if row["raw_row_text"]]
    return filtered_rows, raw_lines


def main() -> int:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not PDF_PATH.exists():
        raise FileNotFoundError(f"Missing supplement PDF: {PDF_PATH}")

    extracted_rows: list[dict[str, object]] = []
    raw_lines_all: list[str] = []
    table_count = 0
    pages_scanned = 0
    table_col_counts: list[int] = []

    with pdfplumber.open(PDF_PATH) as pdf:
        total_pages = len(pdf.pages)
        start = max(1, PAGE_START)
        end = min(PAGE_END, total_pages)

        for page_no in range(start, end + 1):
            pages_scanned += 1
            page = pdf.pages[page_no - 1]

            tables = page.extract_tables() or []
            if tables:
                table_count += len(tables)
                for table in tables:
                    table_rows, table_raw, max_cols = rows_from_table(page_no, table)
                    extracted_rows.extend(table_rows)
                    raw_lines_all.extend(table_raw)
                    if max_cols > 0:
                        table_col_counts.append(max_cols)
            else:
                text = page.extract_text() or ""
                text_rows, text_raw = rows_from_text(page_no, text)
                extracted_rows.extend(text_rows)
                raw_lines_all.extend(text_raw)

    output_rows = []
    for idx, row in enumerate(extracted_rows, start=1):
        output_rows.append(
            {
                "row_id": idx,
                "author_type": row.get("author_type", ""),
                "outbreak_date_text": row.get("outbreak_date_text", ""),
                "tornado_counts_text": row.get("tornado_counts_text", ""),
                "location_text": row.get("location_text", ""),
                "key_event_text": row.get("key_event_text", ""),
                "notes": row.get("notes", ""),
                "source_page": row.get("source_page", ""),
                "raw_row_text": row.get("raw_row_text", ""),
            }
        )

    out = pd.DataFrame(
        output_rows,
        columns=[
            "row_id",
            "author_type",
            "outbreak_date_text",
            "tornado_counts_text",
            "location_text",
            "key_event_text",
            "notes",
            "source_page",
            "raw_row_text",
        ],
    )

    out.to_csv(CSV_PATH, index=False)
    RAW_PATH.write_text("\n".join(raw_lines_all) + "\n", encoding="utf-8")

    required_cols = ["author_type", "outbreak_date_text", "tornado_counts_text", "location_text", "key_event_text"]
    if out.empty:
        missing_columns_rows = 0
    else:
        missing_columns_rows = int(
            out[required_cols].fillna("").apply(lambda s: any(not str(v).strip() for v in s), axis=1).sum()
        )

    consistent_structure = "no"
    if table_count == 0:
        consistent_structure = "not_assessable_no_tables_detected"
    elif len(set(table_col_counts)) == 1:
        consistent_structure = "yes"

    report_lines = [
        "# Supplement Table S1 pdfplumber Extraction",
        "",
        f"- Pages scanned: {pages_scanned} (requested pages {PAGE_START}-{PAGE_END})",
        f"- Tables detected by pdfplumber: {table_count}",
        f"- Rows extracted: {len(out)}",
        f"- Rows with missing columns: {missing_columns_rows}",
        f"- Table structure appears consistent across pages: {consistent_structure}",
        "",
        "## Notes",
        "- Structured extraction uses page.extract_tables() when available.",
        "- Pages without detected tables fall back to page.extract_text() with heuristic line grouping.",
        "- Raw extracted lines are preserved verbatim in the raw text output for traceability.",
    ]
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"Pages scanned: {pages_scanned}")
    print(f"Tables detected: {table_count}")
    print(f"Rows extracted: {len(out)}")
    print(f"Rows with missing columns: {missing_columns_rows}")
    print(f"Table structure consistent: {consistent_structure}")
    print(f"Saved: {CSV_PATH}")
    print(f"Saved: {RAW_PATH}")
    print(f"Saved: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
