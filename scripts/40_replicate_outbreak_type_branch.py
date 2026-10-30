
from __future__ import annotations

from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_outbreaks.csv"
ANALYSIS_DAILY_PATH = ROOT / "data" / "derived" / "daily" / "analysis_daily.csv"
OMNI_DAILY_PATH = ROOT / "data" / "derived" / "daily" / "omni_daily.csv"
CLEAN_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_outbreaks_clean.csv"
SUMMARY_PATH = ROOT / "data" / "derived" / "tables" / "outbreak_type_author_summary.csv"
FIGURE_PATH = ROOT / "data" / "derived" / "figures" / "outbreak_type_author_counts.png"
REPORT_PATH = ROOT / "data" / "derived" / "reports" / "outbreak_type_author_replication.md"


TYPE_PATTERNS = [
    re.compile(r"Type\s*([ABCD])", flags=re.IGNORECASE),
    re.compile(r"^\s*([ABCD])\s", flags=re.IGNORECASE),
    re.compile(r"\(([ABCD])\)", flags=re.IGNORECASE),
]


def normalize_author_type(value: object, raw_text: object) -> str:
    raw_value = "" if pd.isna(value) else str(value).strip()
    if raw_value.upper() in {"A", "B", "C", "D", "A*", "B*", "C*", "D*"}:
        return raw_value[0].upper()

    for candidate in [raw_value, "" if pd.isna(raw_text) else str(raw_text)]:
        for pattern in TYPE_PATTERNS:
            match = pattern.search(candidate)
            if match:
                return match.group(1).upper()
    return "unknown"


def main() -> int:
    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIGURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing extracted supplement outbreak table: {INPUT_PATH}")

    outbreaks = pd.read_csv(INPUT_PATH)
    if ANALYSIS_DAILY_PATH.exists():
        pd.read_csv(ANALYSIS_DAILY_PATH, nrows=1)
    if OMNI_DAILY_PATH.exists():
        pd.read_csv(OMNI_DAILY_PATH, nrows=1)

    outbreaks["outbreak_date_start"] = pd.to_datetime(outbreaks.get("outbreak_date_start"), errors="coerce")
    outbreaks["outbreak_date_end"] = pd.to_datetime(outbreaks.get("outbreak_date_end"), errors="coerce")
    outbreaks["tornado_count_numeric"] = pd.to_numeric(outbreaks.get("tornado_count_numeric"), errors="coerce")
    outbreaks = outbreaks.reset_index(drop=True)
    outbreaks["outbreak_id"] = np.arange(1, len(outbreaks) + 1, dtype=int)
    raw_row_series = outbreaks.get("raw_row", pd.Series(dtype=object))
    raw_row_text_series = outbreaks.get("raw_row_text", raw_row_series)
    outbreaks["author_type_normalized"] = [
        normalize_author_type(v, raw)
        for v, raw in zip(outbreaks.get("author_type", pd.Series(dtype=object)), raw_row_text_series, strict=False)
    ]
    outbreaks["author_type_standardized"] = outbreaks["author_type_normalized"]
    outbreaks["outbreak_mid_date"] = outbreaks["outbreak_date_start"]
    valid_end = outbreaks["outbreak_date_end"].notna()
    outbreaks.loc[valid_end, "outbreak_mid_date"] = outbreaks.loc[valid_end, "outbreak_date_start"] + (
        (outbreaks.loc[valid_end, "outbreak_date_end"] - outbreaks.loc[valid_end, "outbreak_date_start"]) / 2
    )
    outbreaks["date_parse_ok"] = outbreaks["outbreak_date_start"].notna()
    outbreaks.to_csv(CLEAN_PATH, index=False)

    summary = (
        outbreaks.groupby("author_type_normalized", dropna=False)
        .agg(
            outbreak_count=("author_type_normalized", "size"),
            first_date=("outbreak_date_start", "min"),
            last_date=("outbreak_date_start", "max"),
            median_tornado_count_if_available=("tornado_count_numeric", "median"),
        )
        .reset_index()
        .rename(columns={"author_type_normalized": "author_type"})
    )
    summary["author_type"] = pd.Categorical(summary["author_type"], categories=["A", "B", "C", "D", "unknown"], ordered=True)
    summary = summary.sort_values("author_type").reset_index(drop=True)
    total = int(summary["outbreak_count"].sum()) if not summary.empty else 0
    summary["percent_of_total"] = np.where(total > 0, 100.0 * summary["outbreak_count"] / total, np.nan)
    summary["notes"] = np.where(
        summary["author_type"].isin(["A", "B", "C", "D"]),
        "Parsed from supplement author labels or raw row text.",
        "Label missing or not cleanly recoverable from supplement text.",
    )
    summary = summary[
        [
            "author_type",
            "outbreak_count",
            "percent_of_total",
            "first_date",
            "last_date",
            "median_tornado_count_if_available",
            "notes",
        ]
    ]
    summary.to_csv(SUMMARY_PATH, index=False)

    if not summary.empty:
        fig, ax = plt.subplots(figsize=(8.4, 5.2))
        ax.bar(summary["author_type"].astype(str), summary["outbreak_count"], color="0.35")
        ax.set_xlabel("Author-assigned outbreak type")
        ax.set_ylabel("Outbreak count")
        ax.set_title("Supplement outbreak counts by author type")
        plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
        fig.tight_layout()
        fig.savefig(FIGURE_PATH, dpi=300, bbox_inches="tight")
        plt.close(fig)

    typed = int(outbreaks["author_type_normalized"].isin(["A", "B", "C", "D"]).sum()) if not outbreaks.empty else 0
    report_lines = [
        "# Outbreak Type Author Replication",
        "",
        f"- Outbreak rows extracted: {len(outbreaks)}",
        f"- Rows assigned to Type A/B/C/D from supplement text: {typed}",
        f"- Date range: {'' if outbreaks['outbreak_date_start'].dropna().empty else outbreaks['outbreak_date_start'].min().date()} to {'' if outbreaks['outbreak_date_start'].dropna().empty else outbreaks['outbreak_date_start'].max().date()}",
        "",
        "## Type Framing",
        "- Type A interpreted as outbreaks closely following CIR context.",
        "- Type B interpreted as outbreaks closely preceded by HCS/CIR with HDP context.",
        "- Type C interpreted as outbreaks closely following ICME context.",
        "- Type D interpreted as outbreaks during the declining phase of major HSS context.",
        "- These descriptions are kept as supplement/paper framing unless directly extractable from the supplement row text.",
        "",
        "## Approximate Proportions",
    ]
    if summary.empty:
        report_lines.append("- No outbreak rows available.")
    else:
        for row in summary.itertuples(index=False):
            report_lines.append(f"- {row.author_type}: {row.outbreak_count} ({row.percent_of_total:.1f}%)")
        report_lines.append("- Automatic verification against paper-stated proportions may remain incomplete if the supplement extraction is partial or ambiguous.")

    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print("Author type counts:")
    if summary.empty:
        print("No outbreak rows available.")
    else:
        print(summary[["author_type", "outbreak_count"]].to_string(index=False))
    print(f"Saved: {CLEAN_PATH}")
    print(f"Saved: {SUMMARY_PATH}")
    print(f"Saved: {FIGURE_PATH}")
    print(f"Saved: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
