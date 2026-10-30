from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPE_DIR = ROOT / "data" / "derived" / "spe"
TABLE_DIR = ROOT / "data" / "derived" / "tables"
REPORT_DIR = ROOT / "data" / "derived" / "reports"


def detect_iteration_columns(df: pd.DataFrame) -> list[str]:
    prefixes = (
        "null_iter_",
        "null_sim_",
        "sim_",
        "bootstrap_iter_",
        "null_draw_",
    )
    return [c for c in df.columns if c.lower().startswith(prefixes)]


def empirical_pvalues(null_values: np.ndarray, observed: float) -> tuple[float, float]:
    null_values = null_values[np.isfinite(null_values)]
    if null_values.size == 0:
        return np.nan, np.nan

    p_upper = float((1 + np.sum(null_values >= observed)) / (len(null_values) + 1))
    p_lower = float((1 + np.sum(null_values <= observed)) / (len(null_values) + 1))
    p_two = float(min(1.0, 2.0 * min(p_upper, p_lower)))
    return p_upper, p_two


def make_interpretation(p_two: float) -> str:
    if not np.isfinite(p_two):
        return "p-value unavailable from provided columns"
    if p_two < 0.01:
        return "two-sided p < 0.01"
    if p_two < 0.05:
        return "two-sided p < 0.05"
    return "not significant at p < 0.05"


def process_file(
    path: Path,
    analysis: str,
    branch: str,
    null_model: str,
    block_length_days: int | None,
) -> dict[str, object] | None:
    if not path.exists():
        return None

    df = pd.read_csv(path)
    required = {"lag", "observed_daily_mean", "null_mean", "null_q025", "null_q975"}
    if not required.issubset(df.columns):
        return None

    lag0 = df[df["lag"] == 0]
    if lag0.empty:
        return None
    row = lag0.iloc[0]

    observed = float(row["observed_daily_mean"])
    null_mean = float(row["null_mean"])
    q025 = float(row["null_q025"])
    q975 = float(row["null_q975"])

    iter_cols = detect_iteration_columns(df)
    if {"p_value_one_sided", "p_value_two_sided", "null_iterations"}.issubset(df.columns):
        p_one = float(row["p_value_one_sided"])
        p_two = float(row["p_value_two_sided"])
    elif iter_cols:
        null_values = row[iter_cols].to_numpy(dtype=float)
        p_one, p_two = empirical_pvalues(null_values, observed)
    else:
        raise ValueError(f"{path}: empirical null-tail counts are unavailable; rerun the generating script.")

    return {
        "analysis": analysis,
        "branch": branch,
        "null_model": null_model,
        "block_length_days": block_length_days,
        "observed_lag0": observed,
        "null_mean": null_mean,
        "null_q025": q025,
        "null_q975": q975,
        "p_value_one_sided": p_one,
        "p_value_two_sided": p_two,
        "interpretation": make_interpretation(p_two),
    }


def main() -> int:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    used_files: list[str] = []
    missing_files: list[str] = []

    targets = [
        # Requested fast-random-date files.
        {
            "path": SPE_DIR / "author_hcs_fast_null_all_tornadoes.csv",
            "analysis": "core_fast_null",
            "branch": "author_hcs",
            "null_model": "fast_random_date",
            "block_length_days": np.nan,
        },
        {
            "path": SPE_DIR / "reconstructed_hcs_fast_null_all_tornadoes.csv",
            "analysis": "core_fast_null",
            "branch": "reconstructed_hcs",
            "null_model": "fast_random_date",
            "block_length_days": np.nan,
        },
        {
            "path": SPE_DIR / "phase_randomized_author_hcs_all_tornadoes.csv",
            "analysis": "phase_randomized",
            "branch": "author_hcs",
            "null_model": "phase_randomized",
            "block_length_days": np.nan,
        },
        {
            "path": SPE_DIR / "block_bootstrap_author_hcs_block7.csv",
            "analysis": "block_bootstrap_author_block7",
            "branch": "author_hcs",
            "null_model": "block_bootstrap",
            "block_length_days": 7,
        },
        {
            "path": SPE_DIR / "block_bootstrap_author_hcs_block14.csv",
            "analysis": "block_bootstrap_author_block14",
            "branch": "author_hcs",
            "null_model": "block_bootstrap",
            "block_length_days": 14,
        },
        {
            "path": SPE_DIR / "block_bootstrap_reconstructed_hcs_block7.csv",
            "analysis": "block_bootstrap_reconstructed_block7",
            "branch": "reconstructed_hcs",
            "null_model": "block_bootstrap",
            "block_length_days": 7,
        },
        {
            "path": SPE_DIR / "block_bootstrap_reconstructed_hcs_block14.csv",
            "analysis": "block_bootstrap_reconstructed_block14",
            "branch": "reconstructed_hcs",
            "null_model": "block_bootstrap",
            "block_length_days": 14,
        },
    ]

    # Compatibility fallback for prior naming used by core author fast-null output.
    fallback_author_fast = SPE_DIR / "fast_null_test_all_tornadoes.csv"

    for cfg in targets:
        path = cfg["path"]
        if cfg["analysis"] == "core_fast_null" and cfg["branch"] == "author_hcs" and (not path.exists()) and fallback_author_fast.exists():
            path = fallback_author_fast

        result = process_file(
            path=path,
            analysis=str(cfg["analysis"]),
            branch=str(cfg["branch"]),
            null_model=str(cfg["null_model"]),
            block_length_days=None if pd.isna(cfg["block_length_days"]) else int(cfg["block_length_days"]),
        )

        if result is None:
            missing_files.append(str(cfg["path"].relative_to(ROOT)))
        else:
            rows.append(result)
            used_files.append(str(path.relative_to(ROOT)))

    for branch in ("author_hcs", "reconstructed_hcs"):
        for season in ("full_year", "mar_jun", "apr_jun"):
            path = SPE_DIR / f"{branch}_{season}_fast_null_all_tornadoes.csv"
            result = process_file(path, f"seasonal_{season}", branch, "seasonal_random_date", None)
            if result is None:
                raise FileNotFoundError(path)
            rows.append(result)
            used_files.append(str(path.relative_to(ROOT)))

    out_df = pd.DataFrame(
        rows,
        columns=[
            "analysis",
            "branch",
            "null_model",
            "block_length_days",
            "observed_lag0",
            "null_mean",
            "null_q025",
            "null_q975",
            "p_value_one_sided",
            "p_value_two_sided",
            "interpretation",
        ],
    )

    csv_out = TABLE_DIR / "lag0_permutation_pvalues.csv"
    out_df.to_csv(csv_out, index=False)

    lines = ["# Lag-0 Permutation P-values", ""]
    if out_df.empty:
        lines.append("No eligible lag-0 files were available.")
    else:
        lines.append("## P-value Table")
        lines.append("")
        header = "| analysis | branch | null_model | block_length_days | observed_lag0 | null_mean | null_q025 | null_q975 | p_value_one_sided | p_value_two_sided | interpretation |"
        sep = "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"
        lines.append(header)
        lines.append(sep)
        for r in out_df.itertuples(index=False):
            lines.append(
                f"| {r.analysis} | {r.branch} | {r.null_model} | {r.block_length_days} | "
                f"{r.observed_lag0:.6f} | {r.null_mean:.6f} | {r.null_q025:.6f} | {r.null_q975:.6f} | "
                f"{r.p_value_one_sided:.6f} | {r.p_value_two_sided:.6f} | {r.interpretation} |"
            )

        lines.append("")
        lines.append("## Interpretation")
        any_p05 = bool((out_df["p_value_two_sided"] < 0.05).any())
        any_p01 = bool((out_df["p_value_two_sided"] < 0.01).any())
        lines.append(f"- Any p < 0.05: {any_p05}")
        lines.append(f"- Any p < 0.01: {any_p01}")
        if any_p05:
            lines.append("- At least one lag-0 test approaches conventional significance under the available null summaries.")
        else:
            lines.append(
                "- None of these lag-0 Monte Carlo comparisons rejects at 0.05. "
                "This is not an equivalence test or evidence of an exactly zero effect; distinct null constructions preserve different properties."
            )

    lines.append("")
    lines.append("## Source Files Used")
    for p in sorted(set(used_files)):
        lines.append(f"- {p}")

    if missing_files:
        lines.append("")
        lines.append("## Missing/Skipped Requested Files")
        for p in sorted(set(missing_files)):
            lines.append(f"- {p}")

    md_out = REPORT_DIR / "lag0_permutation_pvalues.md"
    md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Saved: {csv_out}")
    print(f"Saved: {md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
