from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "data" / "derived" / "catalogs"
FIG_DIR = ROOT / "data" / "derived" / "figures"
TABLE_DIR = ROOT / "data" / "derived" / "tables"


def parse_author_dates(df: pd.DataFrame) -> pd.Series:
    if "datetime_utc" in df.columns:
        dt = pd.to_datetime(df["datetime_utc"], utc=True, errors="coerce").dt.tz_convert(None)
    elif {"year", "month", "day"}.issubset(df.columns):
        dt = pd.to_datetime(df[["year", "month", "day"]], errors="coerce")
    elif "date" in df.columns:
        dt = pd.to_datetime(df["date"], errors="coerce")
    else:
        raise ValueError("Author catalog has no parseable date columns.")
    dt = dt.dt.normalize().dropna().drop_duplicates()
    return dt[dt.dt.year.between(1963, 2023)].sort_values().reset_index(drop=True)


def parse_reconstructed_dates(df: pd.DataFrame) -> pd.Series:
    if "date" not in df.columns:
        raise ValueError("Reconstructed catalog is missing 'date' column.")
    dt = pd.to_datetime(df["date"], errors="coerce")
    dt = dt.dt.normalize().dropna().drop_duplicates()
    return dt[dt.dt.year.between(1963, 2023)].sort_values().reset_index(drop=True)


def nearest_abs_day_differences_days(author_dates: pd.Series, reconstructed_dates: pd.Series) -> np.ndarray:
    if author_dates.empty or reconstructed_dates.empty:
        return np.array([], dtype=float)

    a_days = author_dates.to_numpy(dtype="datetime64[D]")
    r_days = reconstructed_dates.to_numpy(dtype="datetime64[D]")

    idx = np.searchsorted(r_days, a_days)
    right_ok = idx < len(r_days)
    left_ok = idx > 0

    right_diffs = np.full(len(a_days), np.inf, dtype=float)
    left_diffs = np.full(len(a_days), np.inf, dtype=float)

    if right_ok.any():
        right_diffs[right_ok] = np.abs((r_days[idx[right_ok]] - a_days[right_ok]).astype("timedelta64[D]").astype(int))

    if left_ok.any():
        left_diffs[left_ok] = np.abs((r_days[idx[left_ok] - 1] - a_days[left_ok]).astype("timedelta64[D]").astype(int))

    diffs = np.minimum(left_diffs, right_diffs)
    return diffs[np.isfinite(diffs)]


def inter_event_spacing_days(dates: pd.Series) -> np.ndarray:
    if len(dates) < 2:
        return np.array([], dtype=float)
    d = dates.to_numpy(dtype="datetime64[D]")
    return np.diff(d).astype("timedelta64[D]").astype(int)


def main() -> int:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    author_path = CATALOG_DIR / "author_hcs_catalog.csv"
    reconstructed_path = CATALOG_DIR / "hcs_from_omni.csv"

    if not author_path.exists() or not reconstructed_path.exists():
        raise FileNotFoundError("Required catalog input files are missing.")

    author_df = pd.read_csv(author_path)
    reconstructed_df = pd.read_csv(reconstructed_path)

    author_dates = parse_author_dates(author_df)
    reconstructed_dates = parse_reconstructed_dates(reconstructed_df)

    author_yearly = author_dates.dt.year.value_counts().sort_index()
    reconstructed_yearly = reconstructed_dates.dt.year.value_counts().sort_index()
    all_years = np.arange(
        min(author_yearly.index.min(), reconstructed_yearly.index.min()),
        max(author_yearly.index.max(), reconstructed_yearly.index.max()) + 1,
    )
    author_yearly = author_yearly.reindex(all_years, fill_value=0)
    reconstructed_yearly = reconstructed_yearly.reindex(all_years, fill_value=0)

    fig, ax = plt.subplots(figsize=(13.5, 5.4))
    x = np.arange(len(all_years))
    w = 0.42
    ax.bar(x - w / 2, author_yearly.to_numpy(), width=w, color="tab:blue", alpha=0.85, label="Author catalog")
    ax.bar(x + w / 2, reconstructed_yearly.to_numpy(), width=w, color="tab:orange", alpha=0.75, label="Reconstructed catalog")
    tick_step = 2 if len(all_years) > 25 else 1
    ax.set_xticks(x[::tick_step])
    ax.set_xticklabels(all_years[::tick_step], rotation=45, ha="right")
    ax.set_xlabel("Year")
    ax.set_ylabel("HCS crossing count")
    ax.set_title("Annual HCS crossing counts: author vs reconstructed catalogs")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "hcs_catalog_yearly_counts_comparison.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    nearest_abs = nearest_abs_day_differences_days(author_dates, reconstructed_dates)
    if nearest_abs.size > 0:
        fig, ax = plt.subplots(figsize=(8.8, 5.0))
        bins = np.arange(0, max(31, int(np.nanmax(nearest_abs)) + 2)) - 0.5
        ax.hist(nearest_abs, bins=bins, color="0.35", alpha=0.9)
        ax.set_xlabel("Absolute nearest-event difference (days)")
        ax.set_ylabel("Author event count")
        ax.set_title("Nearest reconstructed crossing difference for each author event")
        fig.tight_layout()
        fig.savefig(FIG_DIR / "hcs_catalog_nearest_difference_histogram.png", dpi=300, bbox_inches="tight")
        plt.close(fig)

    author_spacing = inter_event_spacing_days(author_dates)
    reconstructed_spacing = inter_event_spacing_days(reconstructed_dates)
    if author_spacing.size > 0 and reconstructed_spacing.size > 0:
        max_space = int(max(np.nanmax(author_spacing), np.nanmax(reconstructed_spacing)))
        bins = np.arange(0, max(31, max_space + 2)) - 0.5

        fig, ax = plt.subplots(figsize=(8.8, 5.0))
        ax.hist(author_spacing, bins=bins, density=True, alpha=0.45, color="tab:blue", label="Author spacing")
        ax.hist(reconstructed_spacing, bins=bins, density=True, alpha=0.45, color="tab:orange", label="Reconstructed spacing")
        ax.set_xlabel("Inter-event spacing (days)")
        ax.set_ylabel("Density")
        ax.set_title("Inter-event spacing comparison")
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(FIG_DIR / "hcs_catalog_spacing_comparison.png", dpi=300, bbox_inches="tight")
        plt.close(fig)

    summary = pd.DataFrame(
        [
            {
                "author_count_total": int(len(author_dates)),
                "reconstructed_count_total": int(len(reconstructed_dates)),
                "author_period_start": str(author_dates.min().date()) if not author_dates.empty else "",
                "author_period_end": str(author_dates.max().date()) if not author_dates.empty else "",
                "reconstructed_period_start": str(reconstructed_dates.min().date()) if not reconstructed_dates.empty else "",
                "reconstructed_period_end": str(reconstructed_dates.max().date()) if not reconstructed_dates.empty else "",
                "median_author_spacing_days": float(np.nanmedian(author_spacing)) if author_spacing.size > 0 else np.nan,
                "median_reconstructed_spacing_days": float(np.nanmedian(reconstructed_spacing)) if reconstructed_spacing.size > 0 else np.nan,
                "median_nearest_author_to_reconstructed_diff_days": float(np.nanmedian(nearest_abs)) if nearest_abs.size > 0 else np.nan,
            }
        ]
    )
    summary.to_csv(TABLE_DIR / "hcs_catalog_comparison_summary.csv", index=False)

    print("Created catalog comparison figures and summary table.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
