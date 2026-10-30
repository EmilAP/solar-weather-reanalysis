from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPE_DIR = ROOT / "data" / "derived" / "spe"
FIG_DIR = ROOT / "data" / "derived" / "figures"
TABLE_DIR = ROOT / "data" / "derived" / "tables"


def read_null_file(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"lag", "observed_daily_mean", "null_mean", "null_q025", "null_q975"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in {path}: {sorted(missing)}")
    if "anomaly_vs_null_mean" not in df.columns:
        df["anomaly_vs_null_mean"] = df["observed_daily_mean"] - df["null_mean"]
    df["band_low_centered_zero"] = df["null_q025"] - df["null_mean"]
    df["band_high_centered_zero"] = df["null_q975"] - df["null_mean"]
    return df.sort_values("lag").reset_index(drop=True)


def add_lag0_row(summary_rows: list[dict], branch: str, analysis: str, df: pd.DataFrame) -> None:
    lag0 = df.loc[df["lag"] == 0]
    if lag0.empty:
        return
    row = lag0.iloc[0]
    inside = bool((row["observed_daily_mean"] >= row["null_q025"]) and (row["observed_daily_mean"] <= row["null_q975"]))
    summary_rows.append(
        {
            "branch": branch,
            "analysis": analysis,
            "lag0_observed": float(row["observed_daily_mean"]),
            "lag0_null_mean": float(row["null_mean"]),
            "lag0_null_q025": float(row["null_q025"]),
            "lag0_null_q975": float(row["null_q975"]),
            "lag0_inside_band": inside,
        }
    )


def draw_anomaly_panel(ax: plt.Axes, df: pd.DataFrame, title: str) -> None:
    ax.plot(df["lag"], df["anomaly_vs_null_mean"], color="black", linewidth=2.0, label="Observed anomaly")
    ax.fill_between(
        df["lag"],
        df["band_low_centered_zero"],
        df["band_high_centered_zero"],
        color="0.85",
        alpha=0.9,
        label="95% null band (centered at 0)",
    )
    ax.axhline(0.0, color="0.4", linewidth=1.0)
    ax.axvline(0, color="0.5", linestyle="--", linewidth=1.2)
    ax.set_xlim(-30, 30)
    ax.set_xlabel("Lag (days)")
    ax.set_ylabel("Daily tornado-rate anomaly")
    ax.set_title(title)


def save_author_reconstructed_figures(
    author_df: pd.DataFrame | None,
    reconstructed_df: pd.DataFrame | None,
) -> None:
    if author_df is not None:
        fig, ax = plt.subplots(figsize=(8.8, 5.0))
        draw_anomaly_panel(ax, author_df, "Author HCS: Daily anomaly vs null")
        ax.legend(loc="upper right", frameon=False)
        fig.tight_layout()
        fig.savefig(FIG_DIR / "author_hcs_daily_anomaly_vs_null.png", dpi=300, bbox_inches="tight")
        plt.close(fig)

    if reconstructed_df is not None:
        fig, ax = plt.subplots(figsize=(8.8, 5.0))
        draw_anomaly_panel(ax, reconstructed_df, "Reconstructed HCS: Daily anomaly vs null")
        ax.legend(loc="upper right", frameon=False)
        fig.tight_layout()
        fig.savefig(FIG_DIR / "reconstructed_hcs_daily_anomaly_vs_null.png", dpi=300, bbox_inches="tight")
        plt.close(fig)


def save_combined_figure(author_df: pd.DataFrame, reconstructed_df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.8, 5.2), sharex=True, sharey=True)

    draw_anomaly_panel(axes[0], author_df, "Panel A: Author HCS")
    draw_anomaly_panel(axes[1], reconstructed_df, "Panel B: Reconstructed HCS")

    ymin = min(
        author_df["anomaly_vs_null_mean"].min(),
        author_df["band_low_centered_zero"].min(),
        reconstructed_df["anomaly_vs_null_mean"].min(),
        reconstructed_df["band_low_centered_zero"].min(),
    )
    ymax = max(
        author_df["anomaly_vs_null_mean"].max(),
        author_df["band_high_centered_zero"].max(),
        reconstructed_df["anomaly_vs_null_mean"].max(),
        reconstructed_df["band_high_centered_zero"].max(),
    )
    pad = 0.08 * (ymax - ymin if ymax > ymin else 1.0)
    axes[0].set_ylim(ymin - pad, ymax + pad)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIG_DIR / "combined_author_vs_reconstructed_anomaly_null.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_seasonal_figure(
    seasonal_author: dict[str, pd.DataFrame],
    seasonal_reconstructed: dict[str, pd.DataFrame],
    summary_rows: list[dict],
) -> None:
    common_seasons = [s for s in ["full_year", "mar_jun", "apr_jun"] if s in seasonal_author and s in seasonal_reconstructed]
    if not common_seasons:
        return

    ncols = len(common_seasons)
    fig, axes = plt.subplots(2, ncols, figsize=(5.2 * ncols, 8.2), sharex=True)
    if ncols == 1:
        axes = np.array([[axes[0]], [axes[1]]])

    for j, season in enumerate(common_seasons):
        adf = seasonal_author[season]
        rdf = seasonal_reconstructed[season]

        draw_anomaly_panel(axes[0, j], adf, f"Author HCS ({season})")
        draw_anomaly_panel(axes[1, j], rdf, f"Reconstructed HCS ({season})")

        for ax, df in [(axes[0, j], adf), (axes[1, j], rdf)]:
            lag0 = df.loc[df["lag"] == 0]
            if not lag0.empty:
                y0 = float(lag0["anomaly_vs_null_mean"].iloc[0])
                ax.scatter([0], [y0], color="tab:red", s=24, zorder=5)

        add_lag0_row(summary_rows, "author_hcs", f"seasonal_{season}", adf)
        add_lag0_row(summary_rows, "reconstructed_hcs", f"seasonal_{season}", rdf)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIG_DIR / "seasonal_control_anomaly_null_comparison.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_phase_figure(phase_df: pd.DataFrame, summary_rows: list[dict]) -> None:
    fig, ax = plt.subplots(figsize=(8.8, 5.0))
    ax.plot(phase_df["lag"], phase_df["observed_daily_mean"], color="black", linewidth=2.0, label="Observed")
    ax.plot(phase_df["lag"], phase_df["null_mean"], color="tab:blue", linewidth=1.6, label="Phase-randomized null mean")
    ax.fill_between(phase_df["lag"], phase_df["null_q025"], phase_df["null_q975"], color="0.85", alpha=0.9, label="95% surrogate band")
    ax.axvline(0, color="0.5", linestyle="--", linewidth=1.2)
    ax.set_xlim(-30, 30)
    ax.set_xlabel("Lag (days)")
    ax.set_ylabel("Daily all-tornadoes mean")
    ax.set_title("Author HCS: Phase-randomized null comparison")
    ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "phase_randomized_author_hcs_all_tornadoes_final.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    add_lag0_row(summary_rows, "author_hcs", "phase_randomized", phase_df)


def main() -> int:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict] = []

    author_core_path = SPE_DIR / "fast_null_test_all_tornadoes.csv"
    reconstructed_core_path = SPE_DIR / "reconstructed_hcs_fast_null_all_tornadoes.csv"

    author_df = read_null_file(author_core_path) if author_core_path.exists() else None
    reconstructed_df = read_null_file(reconstructed_core_path) if reconstructed_core_path.exists() else None

    if author_df is not None:
        add_lag0_row(summary_rows, "author_hcs", "core_fast_null", author_df)
    if reconstructed_df is not None:
        add_lag0_row(summary_rows, "reconstructed_hcs", "core_fast_null", reconstructed_df)

    save_author_reconstructed_figures(author_df, reconstructed_df)

    if (author_df is not None) and (reconstructed_df is not None):
        save_combined_figure(author_df, reconstructed_df)

    seasonal_author = {}
    seasonal_reconstructed = {}
    for season in ["full_year", "mar_jun", "apr_jun"]:
        a_path = SPE_DIR / f"author_hcs_{season}_fast_null_all_tornadoes.csv"
        r_path = SPE_DIR / f"reconstructed_hcs_{season}_fast_null_all_tornadoes.csv"
        if a_path.exists():
            seasonal_author[season] = read_null_file(a_path)
        if r_path.exists():
            seasonal_reconstructed[season] = read_null_file(r_path)

    save_seasonal_figure(seasonal_author, seasonal_reconstructed, summary_rows)

    phase_path = SPE_DIR / "phase_randomized_author_hcs_all_tornadoes.csv"
    if phase_path.exists():
        phase_df = read_null_file(phase_path)
        save_phase_figure(phase_df, summary_rows)

    summary = pd.DataFrame(summary_rows, columns=[
        "branch",
        "analysis",
        "lag0_observed",
        "lag0_null_mean",
        "lag0_null_q025",
        "lag0_null_q975",
        "lag0_inside_band",
    ])
    summary.to_csv(TABLE_DIR / "core_null_lag0_summary.csv", index=False)

    print("Created figures and lag-0 summary table for available null comparisons.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
