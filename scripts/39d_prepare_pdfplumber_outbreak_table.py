from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from _utils import parse_supplement_date_range


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_outbreaks_pdfplumber.csv"
FLAGGED_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_outbreaks_pdfplumber_flagged.csv"
OUTPUT_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_outbreaks.csv"
REVIEW_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_rows_for_manual_review.csv"
SOURCE_REVIEW_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_source_date_review.csv"
REPORT_PATH = ROOT / "data" / "derived" / "reports" / "supplement_table_s1_pdfplumber_preparation.md"

SHORT_RAW_THRESHOLD = 12
DATE_TEXT_OVERRIDES = {
    329: {
        "expected_raw_fragment": "28 Feb - 1 Mar",
        "date_text": "28 Feb - 1 Mar 2011",
        "note": "Year inferred as 2011 from adjacent dated records on source page 14.",
    }
}
MONTH_RE = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_RANGE_RE = re.compile(rf"(?P<left>{MONTH_RE}\.?\s+\d{{1,2}})\s*[\-–]\s*(?P<right>\d{{1,2}}\s*{MONTH_RE}\.?|{MONTH_RE}\.?\s+\d{{1,2}})", re.IGNORECASE)
SINGLE_DATE_RE = re.compile(rf"(?P<d>{MONTH_RE}\.?\s+\d{{1,2}})\s*(?P<y>\d{{4}})", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def compact_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def parse_date_text(date_text: object) -> tuple[str, str]:
    start, end = parse_supplement_date_range(date_text)
    return (
        "" if pd.isna(start) else str(start.date()),
        "" if pd.isna(end) else str(end.date()),
    )


def parse_tornado_count(text: object) -> float:
    s = compact_text(text)
    nums = [int(n) for n in re.findall(r"\d+", s)]
    if not nums:
        return float("nan")
    return float(max(nums))


def apply_date_text_overrides(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date_inference_note"] = ""
    row_ids = pd.to_numeric(out["row_id"], errors="coerce")

    for row_id, override in DATE_TEXT_OVERRIDES.items():
        mask = row_ids.eq(row_id)
        if int(mask.sum()) != 1:
            raise ValueError(f"Expected exactly one supplement row with row_id={row_id}.")
        raw_text = compact_text(out.loc[mask, "raw_row_text"].iloc[0])
        if override["expected_raw_fragment"] not in raw_text:
            raise ValueError(f"Raw text for supplement row_id={row_id} no longer matches the reviewed date override.")
        out.loc[mask, "outbreak_date_text"] = override["date_text"]
        out.loc[mask, "date_inference_note"] = override["note"]

    return out


def build_review_flags(row: pd.Series) -> tuple[bool, str]:
    reasons: list[str] = []

    outbreak_date_text = compact_text(row.get("outbreak_date_text", ""))
    raw_row_text = compact_text(row.get("raw_row_text", ""))
    author_type = compact_text(row.get("author_type", ""))
    key_event_text = compact_text(row.get("key_event_text", ""))

    if not outbreak_date_text:
        reasons.append("missing_outbreak_date_text")
    if not compact_text(row.get("outbreak_date_start", "")) or not compact_text(row.get("outbreak_date_end", "")):
        reasons.append("date_parse_failed")
    if not raw_row_text:
        reasons.append("missing_raw_row_text")
    if not author_type and not key_event_text:
        reasons.append("missing_author_type_and_key_event_text")
    if 0 < len(raw_row_text) < SHORT_RAW_THRESHOLD:
        reasons.append("raw_row_text_too_short")

    needs_review = len(reasons) > 0
    return needs_review, ";".join(reasons)


def main() -> int:
    FLAGGED_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing pdfplumber outbreak CSV: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)
    input_count = int(len(df))

    if "row_id" not in df.columns:
        df = df.reset_index(drop=True)
        df["row_id"] = df.index + 1

    df = df.reset_index(drop=True)
    if "raw_row_text" not in df.columns:
        df["raw_row_text"] = ""
    df = apply_date_text_overrides(df)

    starts = []
    ends = []
    for txt in df.get("outbreak_date_text", pd.Series(dtype=object)):
        start, end = parse_supplement_date_range(txt)
        s = "" if pd.isna(start) else str(start.date())
        e = "" if pd.isna(end) else str(end.date())
        starts.append(s)
        ends.append(e)
    df["outbreak_date_start"] = starts
    df["outbreak_date_end"] = ends
    df["date_parse_ok"] = [bool(start and end) for start, end in zip(starts, ends)]
    df["source_date_review_note"] = df["date_inference_note"]
    duration = (
        pd.to_datetime(df["outbreak_date_end"], errors="coerce")
        - pd.to_datetime(df["outbreak_date_start"], errors="coerce")
    ).dt.days
    long_range = duration > 7
    df.loc[long_range, "source_date_review_note"] = (
        "Source interval exceeds seven days; retained literally and anchored on its "
        "stated start. End date or episode grouping requires source-author clarification; "
        "no guessed replacement is applied."
    )
    df["source_date_review_required"] = df["source_date_review_note"].ne("")
    df["source_date_review_status"] = df["source_date_review_required"].map(
        {True: "pending", False: "not_required"}
    )
    for row_id, note in {
        169: "Literal 31 May-24 June 1996 interval accepted by the project author on 2026-10-30; retain the 31 May start and 24 June end.",
        329: "Year 2011 inferred from adjacent source records; interpretation accepted by the project author on 2026-10-30.",
    }.items():
        accepted = pd.to_numeric(df["row_id"], errors="raise").eq(row_id)
        if accepted.any():
            expected = ("1996-05-31", "1996-06-24") if row_id == 169 else ("2011-02-28", "2011-03-01")
            dates = df.loc[accepted, ["outbreak_date_start", "outbreak_date_end"]]
            if len(dates) != 1 or tuple(dates.iloc[0]) != expected:
                raise ValueError(f"Accepted source dates changed for supplement row {row_id}.")
            df.loc[accepted, "source_date_review_note"] = note
            df.loc[accepted, "source_date_review_required"] = False
            df.loc[accepted, "source_date_review_status"] = "accepted"

    flags = [build_review_flags(row) for _, row in df.iterrows()]
    df["needs_manual_review"] = [x[0] for x in flags]
    df["manual_review_reasons"] = [x[1] for x in flags]
    df["tornado_count_numeric"] = df.get("tornado_counts_text", pd.Series(dtype=object)).map(parse_tornado_count)
    df["key_event_type_text"] = df.get("key_event_text", "")

    df.to_csv(FLAGGED_PATH, index=False)

    excluded = df.loc[df["needs_manual_review"]].copy()
    retained = df.loc[~df["needs_manual_review"]].copy()

    retained.to_csv(OUTPUT_PATH, index=False)
    excluded.to_csv(REVIEW_PATH, index=False)
    source_review = df.loc[df["source_date_review_note"].ne("")]
    source_review.to_csv(SOURCE_REVIEW_PATH, index=False)

    reason_counts: dict[str, int] = {}
    for reasons in excluded.get("manual_review_reasons", pd.Series(dtype=object)).astype(str):
        for reason in [r.strip() for r in reasons.split(";") if r.strip()]:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    retained_critical_complete = bool(
        retained.get("outbreak_date_text", pd.Series(dtype=object)).astype(str).str.strip().ne("").all()
        and retained.get("raw_row_text", pd.Series(dtype=object)).astype(str).str.strip().ne("").all()
        and retained.get("date_parse_ok", pd.Series(dtype=bool)).all()
    )
    usable_text = "yes" if retained_critical_complete and len(retained) > 0 else "needs_additional_review"

    lines = [
        "# Supplement Table S1 pdfplumber Preparation",
        "",
        f"- Input row count: {input_count}",
        f"- Retained row count: {len(retained)}",
        f"- Excluded row count: {len(excluded)}",
        f"- Dates parsed: {int(df['date_parse_ok'].sum())}",
        f"- Dates unresolved (manual review): {int((~df['date_parse_ok']).sum())}",
        f"- Rows with an inferred year: {int(df['date_inference_note'].astype(str).str.strip().ne('').sum())}",
        f"- Rows requiring source-date clarification: {int(df['source_date_review_required'].sum())}",
        f"- Source-date interpretations accepted by the project author: {int(df['source_date_review_status'].eq('accepted').sum())}",
        f"- Retained table appears usable for downstream outbreak analysis: {usable_text}",
        "",
        "## Exclusion Logic",
        "- Exclude if outbreak_date_text is blank.",
        "- Exclude if raw_row_text is blank.",
        "- Exclude if both author_type and key_event_text are blank.",
        "- Exclude if outbreak date text cannot be parsed; these rows are retained in the manual-review file.",
        f"- Exclude if raw_row_text is shorter than {SHORT_RAW_THRESHOLD} characters.",
        "",
        "## Exclusion Reason Counts",
    ]

    if reason_counts:
        for key in sorted(reason_counts):
            lines.append(f"- {key}: {reason_counts[key]}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Notes",
            "- All rows are preserved in the flagged catalog with needs_manual_review and reason labels.",
            "- Inferred dates are labeled in date_inference_note; source raw_row_text is preserved unchanged.",
            "- Long intervals are screening flags, not invalid outbreak definitions. The literal 1996 interval and inferred 2011 year were accepted by the project author on 2026-10-30; neither requires exclusion or further source clarification. Audit notes remain preserved.",
            f"- Source-date review table: {SOURCE_REVIEW_PATH.relative_to(ROOT)}.",
            "- The retained output is intended as the standard downstream input for outbreak analysis scripts.",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Input row count: {input_count}")
    print(f"Retained row count: {len(retained)}")
    print(f"Excluded row count: {len(excluded)}")
    print("Exclusion reasons:")
    if reason_counts:
        for key in sorted(reason_counts):
            print(f"- {key}: {reason_counts[key]}")
    else:
        print("- none")
    print(f"Saved: {FLAGGED_PATH}")
    print(f"Saved: {OUTPUT_PATH}")
    print(f"Saved: {REVIEW_PATH}")
    print(f"Saved: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
