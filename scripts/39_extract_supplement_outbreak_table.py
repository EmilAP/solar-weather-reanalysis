from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "papers" / "tornado-paper-supplement.pdf"
RAW_TEXT_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_raw.txt"
CSV_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_outbreaks.csv"
REPORT_PATH = ROOT / "data" / "derived" / "reports" / "supplement_table_s1_extraction.md"

PRINTED_PAGE_START = 6
PRINTED_PAGE_END = 17
PDF_PAGE_START = 7
PDF_PAGE_END = 18

MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_TEXT_RE = re.compile(rf"({MONTH_RE}\s+\d{{1,2}}(?:\s*[\-–]\s*\d{{1,2}})?(?:,\s*\d{{4}})?|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}(?:\s*[\-–]\s*\d{{1,2}}/\d{{1,2}}/\d{{2,4}})?)", re.IGNORECASE)
TYPE_RE = re.compile(r"\b(?:Type\s*)?([ABCD])\b")
TORNADO_COUNT_RE = re.compile(r"(\d{1,4})\s*(?:tornado(?:es)?|tors?\b)", re.IGNORECASE)
EVENT_KIND_RE = re.compile(r"\b(CIR|HCS(?:-HDP)?|HDP|ICME|HSS)\b", re.IGNORECASE)
PAGE_HEADER_RE = re.compile(r"^(supplement|table\s+s1|page\s+\d+|prikryl|ru[sš]in)", re.IGNORECASE)


def has_command(name: str) -> bool:
    result = subprocess.run(["bash", "-lc", f"command -v {name}"], capture_output=True, text=True)
    return result.returncode == 0 and bool(result.stdout.strip())


def extract_pdf_text() -> tuple[str, str, list[str]]:
    assumptions: list[str] = []

    if has_command("pdftotext"):
        cmd = [
            "pdftotext",
            "-f",
            str(PDF_PAGE_START),
            "-l",
            str(PDF_PAGE_END),
            "-layout",
            str(PDF_PATH),
            "-",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            assumptions.append(
                f"Used pdftotext on PDF pages {PDF_PAGE_START}-{PDF_PAGE_END}, assuming they correspond to printed supplement pages {PRINTED_PAGE_START}-{PRINTED_PAGE_END} after excluding the cover page."
            )
            return result.stdout, "pdftotext", assumptions

    if has_command("mutool"):
        cmd = ["mutool", "draw", "-F", "txt", "-i", str(PDF_PATH), f"{PDF_PAGE_START}-{PDF_PAGE_END}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            assumptions.append(
                f"Used mutool draw on PDF pages {PDF_PAGE_START}-{PDF_PAGE_END}, assuming they correspond to printed supplement pages {PRINTED_PAGE_START}-{PRINTED_PAGE_END}."
            )
            return result.stdout, "mutool", assumptions

    if has_command("strings"):
        result = subprocess.run(["strings", str(PDF_PATH)], capture_output=True, text=True)
        assumptions.append("No PDF text extractor was available; fell back to raw strings() extraction, which is likely incomplete and high-ambiguity.")
        return result.stdout, "strings", assumptions

    raw = PDF_PATH.read_bytes().decode("latin-1", errors="ignore")
    assumptions.append("No PDF extraction tool was available; fell back to a raw binary decode, which is likely incomplete and high-ambiguity.")
    return raw, "binary_decode", assumptions


def split_pages(text: str) -> list[tuple[int | None, str]]:
    if "\f" in text:
        pages = [part for part in text.split("\f") if part.strip()]
        return [(PRINTED_PAGE_START + i, page) for i, page in enumerate(pages)]
    return [(None, text)]


def normalize_lines(page_text: str) -> list[str]:
    lines: list[str] = []
    for raw in page_text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if PAGE_HEADER_RE.match(line):
            continue
        if line.isdigit():
            continue
        lines.append(line)
    return lines


def group_candidate_rows(page_no: int | None, lines: list[str]) -> list[tuple[int | None, str]]:
    groups: list[tuple[int | None, str]] = []
    buffer = ""
    for line in lines:
        starts_new = bool(DATE_TEXT_RE.search(line)) or bool(re.search(r"\b19\d{2}\b|\b20\d{2}\b", line))
        if starts_new and buffer:
            groups.append((page_no, buffer.strip()))
            buffer = line
        else:
            buffer = f"{buffer} {line}".strip()
    if buffer:
        groups.append((page_no, buffer.strip()))
    return groups


def parse_date_bounds(date_text: str) -> tuple[pd.Timestamp | pd.NaT, pd.Timestamp | pd.NaT]:
    date_text = date_text.replace("–", "-")
    if "-" in date_text and "/" not in date_text:
        parts = [p.strip() for p in date_text.split("-")]
        if len(parts) == 2:
            left = pd.to_datetime(parts[0], errors="coerce")
            if re.search(r"\d{4}", parts[1]) and not re.search(r"\d{4}", parts[0]):
                left = pd.to_datetime(f"{parts[0]}, {re.search(r'\d{4}', parts[1]).group(0)}", errors="coerce")
            right = pd.to_datetime(parts[1], errors="coerce")
            return left, right
    dt = pd.to_datetime(date_text, errors="coerce")
    return dt, dt


def parse_row(row_text: str, source_page: int | None) -> dict[str, object]:
    date_matches = DATE_TEXT_RE.findall(row_text)
    outbreak_date_text = date_matches[0] if date_matches else ""
    outbreak_start, outbreak_end = parse_date_bounds(outbreak_date_text) if outbreak_date_text else (pd.NaT, pd.NaT)

    tornado_match = TORNADO_COUNT_RE.search(row_text)
    tornado_num = int(tornado_match.group(1)) if tornado_match else np.nan
    author_type_match = TYPE_RE.search(row_text)
    author_type = author_type_match.group(1).upper() if author_type_match else ""

    event_kind_match = EVENT_KIND_RE.search(row_text)
    key_event_type = event_kind_match.group(1).upper() if event_kind_match else ""
    key_date_text = date_matches[1] if len(date_matches) > 1 else ""

    notes: list[str] = []
    if not outbreak_date_text:
        notes.append("missing_date")
    if not author_type:
        notes.append("missing_author_type")
    if not key_event_type:
        notes.append("missing_event_kind")
    if pd.isna(outbreak_start):
        notes.append("date_parse_ambiguous")

    location_text = ""
    return {
        "outbreak_date_text": outbreak_date_text,
        "outbreak_date_start": "" if pd.isna(outbreak_start) else str(pd.Timestamp(outbreak_start).date()),
        "outbreak_date_end": "" if pd.isna(outbreak_end) else str(pd.Timestamp(outbreak_end).date()),
        "tornado_count_text": tornado_match.group(0) if tornado_match else "",
        "tornado_count_numeric": tornado_num,
        "author_type": author_type,
        "location_text": location_text,
        "key_date_text": key_date_text,
        "key_event_type_text": key_event_type,
        "notes": ";".join(notes),
        "source_page": source_page,
        "raw_row_text": row_text,
    }


def main() -> int:
    RAW_TEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not PDF_PATH.exists():
        raise FileNotFoundError(f"Missing supplement PDF: {PDF_PATH}")

    text, method, assumptions = extract_pdf_text()
    RAW_TEXT_PATH.write_text(text, encoding="utf-8", errors="ignore")

    rows: list[dict[str, object]] = []
    for page_no, page_text in split_pages(text):
        page_lines = normalize_lines(page_text)
        for _, row_text in group_candidate_rows(page_no, page_lines):
            if len(row_text) < 12:
                continue
            parsed = parse_row(row_text, page_no)
            rows.append(parsed)

    df = pd.DataFrame(
        rows,
        columns=[
            "outbreak_date_text",
            "outbreak_date_start",
            "outbreak_date_end",
            "tornado_count_text",
            "tornado_count_numeric",
            "author_type",
            "location_text",
            "key_date_text",
            "key_event_type_text",
            "notes",
            "source_page",
            "raw_row_text",
        ],
    )
    df.to_csv(CSV_PATH, index=False)

    ambiguous_count = int(df["notes"].fillna("").ne("").sum()) if not df.empty else 0
    report_lines = [
        "# Supplement Table S1 Extraction",
        "",
        f"- Extraction method: {method}",
        f"- Extracted rows: {len(df)}",
        f"- Ambiguous rows: {ambiguous_count}",
        f"- Raw text saved to: {RAW_TEXT_PATH.relative_to(ROOT)}",
        "",
        "## Assumptions / Cleanup",
    ]
    if assumptions:
        for item in assumptions:
            report_lines.append(f"- {item}")
    else:
        report_lines.append("- None")
    report_lines.append("- Rows were grouped heuristically from extracted text blocks; unparsed or partial fields were preserved in raw_row_text and flagged in notes.")
    if method in {"strings", "binary_decode"}:
        report_lines.append("- Parsing difficulty is high because the supplement text is not cleanly extractable with the currently available tools.")

    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"Saved: {CSV_PATH}")
    print(f"Saved: {RAW_TEXT_PATH}")
    print(f"Saved: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
