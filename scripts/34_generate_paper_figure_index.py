from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "data" / "derived" / "figures"
REPORT_DIR = ROOT / "data" / "derived" / "reports"


def infer_title(filename: str) -> str:
    stem = Path(filename).stem.replace("_", " ")
    replacements = {
        "hcs": "HCS",
        "omni": "OMNI",
        "apr jun": "Apr-Jun",
        "mar jun": "Mar-Jun",
    }
    title = stem
    for old, new in replacements.items():
        title = title.replace(old, new)
    return title.title().replace("Hcs", "HCS").replace("Omni", "OMNI")


def infer_role(filename: str) -> str:
    name = filename.lower()
    if "combined_author_vs_reconstructed" in name or "daily_anomaly_vs_null" in name:
        return "main figure"
    if "seasonal" in name or "phase_randomized" in name:
        return "robustness figure"
    if "catalog" in name:
        return "catalog comparison"
    if "fast_null" in name or "null" in name:
        return "null-model figure"
    return "supplement"


def infer_notes(filename: str) -> str:
    name = filename.lower()
    if "combined_author_vs_reconstructed" in name:
        return "Side-by-side comparison of author and reconstructed anomaly-vs-null curves."
    if "phase_randomized" in name:
        return "Surrogate-null comparison preserving broad autocorrelation structure."
    if "seasonal" in name:
        return "Season-restricted robustness panel set."
    if "catalog_yearly_counts" in name:
        return "Shows annual event-count agreement and divergence between catalogs."
    if "nearest_difference" in name:
        return "Summarizes timing offsets between nearest author and reconstructed events."
    if "spacing_comparison" in name:
        return "Compares inter-event spacing distributions across catalogs."
    if "cumulative" in name:
        return "Cumulative curves are more interpretive than inferential; likely supplement."
    if "daily_rates" in name:
        return "Daily-rate composite figure."
    if "anomal" in name:
        return "Anomaly-oriented event-study figure."
    return "General manuscript-supporting figure."


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    if FIG_DIR.exists():
        for path in sorted(FIG_DIR.glob("*")):
            if not path.is_file():
                continue
            rows.append(
                {
                    "filename": path.name,
                    "short_title": infer_title(path.name),
                    "likely_manuscript_role": infer_role(path.name),
                    "notes": infer_notes(path.name),
                }
            )

    index_df = pd.DataFrame(rows, columns=["filename", "short_title", "likely_manuscript_role", "notes"])
    index_df.to_csv(REPORT_DIR / "paper_figure_index.csv", index=False)

    lines = ["# Paper Figure Index", ""]
    if index_df.empty:
        lines.append("No figure files were found in data/derived/figures.")
    else:
        for row in index_df.itertuples(index=False):
            lines.append(f"## {row.filename}")
            lines.append(f"- Short title: {row.short_title}")
            lines.append(f"- Likely manuscript role: {row.likely_manuscript_role}")
            lines.append(f"- Notes: {row.notes}")
            lines.append("")

    (REPORT_DIR / "paper_figure_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Created paper figure index CSV and Markdown outputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
