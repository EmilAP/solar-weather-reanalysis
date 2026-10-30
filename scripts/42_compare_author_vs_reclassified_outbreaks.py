from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
AUTHOR_PATH = ROOT / "data" / "derived" / "catalogs" / "supplement_table_s1_outbreaks_clean.csv"
IND_PATH = ROOT / "data" / "derived" / "catalogs" / "outbreaks_reclassified_independent.csv"
COMPARE_PATH = ROOT / "data" / "derived" / "tables" / "outbreak_type_author_vs_independent_comparison.csv"
CONFUSION_PATH = ROOT / "data" / "derived" / "tables" / "outbreak_type_confusion_matrix.csv"
AGREE_PATH = ROOT / "data" / "derived" / "tables" / "outbreak_type_agreement_summary.csv"
CONFUSION_FIG = ROOT / "data" / "derived" / "figures" / "outbreak_type_confusion_matrix.png"
AGREE_FIG = ROOT / "data" / "derived" / "figures" / "outbreak_type_agreement_bars.png"
REPORT_PATH = ROOT / "data" / "derived" / "reports" / "outbreak_type_comparison_summary.md"


MAP_AUTHOR = {
    "A": "A_like_CIR_following",
    "B": "B_like_HCS_HDP_preceding",
    "C": "C_like_ICME_following",
    "D": "D_like_major_HSS_declining_phase",
}


def normalize_author_type(value: object) -> str:
    text = str(value).strip()
    return MAP_AUTHOR.get(text, "author_missing")


def plot_confusion(confusion: pd.DataFrame) -> None:
    rows = confusion.index.tolist()
    cols = confusion.columns.tolist()
    matrix = confusion.to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(9, 6))
    im = ax.imshow(matrix, cmap="Greys")
    ax.set_xticks(np.arange(len(cols)))
    ax.set_yticks(np.arange(len(rows)))
    ax.set_xticklabels(cols, rotation=35, ha="right")
    ax.set_yticklabels(rows)
    ax.set_xlabel("Independent type")
    ax.set_ylabel("Author type")
    ax.set_title("Author vs independent outbreak-type confusion matrix")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, int(matrix[i, j]), ha="center", va="center", color="black")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    CONFUSION_FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CONFUSION_FIG, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_agreement(summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    labels = ["Exact agreement", "Disagreement", "Author missing", "Independent unclassified"]
    values = [
        int(row["exact_agreement_count"]),
        int(row["total_compared"] - row["exact_agreement_count"]),
        int(row["author_missing_count"]),
        int(row["independent_unclassified_count"]),
    ]
    fig, ax = plt.subplots(figsize=(8.4, 5.1))
    ax.bar(labels, values, color=["0.3", "0.55", "0.75", "0.85"])
    ax.set_ylabel("Outbreak count")
    ax.set_title("Outbreak-type agreement summary")
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    fig.tight_layout()
    AGREE_FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(AGREE_FIG, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    for path in [AUTHOR_PATH, IND_PATH]:
        if not path.exists():
            raise FileNotFoundError(f"Missing required input: {path}")

    author = pd.read_csv(AUTHOR_PATH)
    independent = pd.read_csv(IND_PATH)

    author["outbreak_date_start"] = pd.to_datetime(author.get("outbreak_date_start"), errors="coerce").dt.normalize()
    independent["outbreak_date_start"] = pd.to_datetime(independent.get("outbreak_date_start"), errors="coerce").dt.normalize()
    author["outbreak_id"] = pd.to_numeric(author.get("outbreak_id"), errors="coerce").astype("Int64")
    independent["outbreak_id"] = pd.to_numeric(independent.get("outbreak_id"), errors="coerce").astype("Int64")

    if author["outbreak_id"].isna().any() or independent["outbreak_id"].isna().any():
        raise ValueError("Both author and independent catalogs must contain non-null outbreak_id values.")
    if author["outbreak_id"].duplicated().any() or independent["outbreak_id"].duplicated().any():
        raise ValueError("outbreak_id must be unique in both author and independent catalogs.")

    author["author_type_for_compare"] = author.get("author_type_normalized", author.get("author_type", "")).map(normalize_author_type)

    merged = author.merge(
        independent[["outbreak_id", "independent_type", "notes"]],
        on="outbreak_id",
        how="inner",
        suffixes=("_author", "_independent"),
    )
    merged["author_type"] = merged.get("author_type_for_compare", "author_missing")
    merged["independent_type"] = merged.get("independent_type", "independent_missing").fillna("independent_missing")
    merged["agreement"] = merged["author_type"] == merged["independent_type"]
    merged["notes"] = merged.get("notes_independent", merged.get("notes", "")).fillna("")

    comparison = merged[["outbreak_id", "outbreak_date_start", "author_type", "independent_type", "agreement", "notes"]].copy()
    comparison["outbreak_date_start"] = comparison["outbreak_date_start"].astype("string")
    comparison.to_csv(COMPARE_PATH, index=False)

    confusion = pd.crosstab(comparison["author_type"], comparison["independent_type"], dropna=False)
    confusion.to_csv(CONFUSION_PATH)

    total = int(len(comparison))
    exact = int(comparison["agreement"].sum())
    author_missing = int((comparison["author_type"] == "author_missing").sum())
    independent_unclassified = int((comparison["independent_type"] == "unclassified").sum())
    agreement_summary = pd.DataFrame(
        [
            {
                "total_compared": total,
                "exact_agreement_count": exact,
                "exact_agreement_percent": 100.0 * exact / total if total > 0 else np.nan,
                "author_missing_count": author_missing,
                "independent_unclassified_count": independent_unclassified,
            }
        ]
    )
    agreement_summary.to_csv(AGREE_PATH, index=False)

    if not confusion.empty:
        plot_confusion(confusion)
    if not agreement_summary.empty:
        plot_agreement(agreement_summary)

    report_lines = [
        "# Outbreak Type Comparison Summary",
        "",
        f"- Supplement outbreak list incorporated successfully: {total > 0}",
        f"- Total compared outbreaks: {total}",
        f"- Exact agreement count: {exact}",
        f"- Exact agreement percent: {agreement_summary.iloc[0]['exact_agreement_percent'] if total > 0 else np.nan:.1f}",
        f"- Author missing count: {author_missing}",
        f"- Independent unclassified count: {independent_unclassified}",
        "",
        "## Interpretation",
        "- Independent reclassification agreement should be evaluated against the confusion matrix rather than a single percentage alone.",
        "- If many events remain unclassified or disagree, the paper's outbreak-type narrative is likely sensitive to classification rules.",
        "- A further event-study branch keyed directly to CIR/HSS arrivals would still be useful if agreement is limited or context windows remain ambiguous.",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"Agreement percentage: {agreement_summary.iloc[0]['exact_agreement_percent'] if total > 0 else np.nan:.1f}%")
    print("Confusion matrix:")
    if confusion.empty:
        print("No overlapping outbreaks available for comparison.")
    else:
        print(confusion.to_string())
    print(f"Saved: {COMPARE_PATH}")
    print(f"Saved: {CONFUSION_PATH}")
    print(f"Saved: {AGREE_PATH}")
    print(f"Saved: {CONFUSION_FIG}")
    print(f"Saved: {AGREE_FIG}")
    print(f"Saved: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
