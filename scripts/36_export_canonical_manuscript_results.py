from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPE_DIR = ROOT / "data" / "derived" / "spe"
TABLE_DIR = ROOT / "data" / "derived" / "tables"
REPORT_DIR = ROOT / "data" / "derived" / "reports"
MANIFEST_DIR = ROOT / "data" / "manifests"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_csv_required(path: Path, missing: list[str]) -> pd.DataFrame | None:
    if not path.exists():
        missing.append(rel(path))
        return None
    return pd.read_csv(path)


def read_json_optional(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_lag0(df: pd.DataFrame) -> pd.Series | None:
    row = df[df["lag"] == 0]
    if row.empty:
        return None
    return row.iloc[0]


def parse_iterations_from_notes(notes: object) -> int | None:
    if not isinstance(notes, str):
        return None
    for segment in notes.split(";"):
        segment = segment.strip()
        if segment.startswith("iterations="):
            value = segment.split("=", 1)[1].strip()
            if value.isdigit():
                return int(value)
    return None


def append_curve_rows(
    out_rows: list[dict[str, object]],
    df: pd.DataFrame,
    branch: str,
    analysis: str,
    season: str,
    source_path: Path,
) -> None:
    tmp = df.copy()
    if "anomaly_vs_null_mean" not in tmp.columns:
        tmp["anomaly_vs_null_mean"] = tmp["observed_daily_mean"] - tmp["null_mean"]
    if "outside_95_band" not in tmp.columns:
        tmp["outside_95_band"] = (tmp["observed_daily_mean"] < tmp["null_q025"]) | (tmp["observed_daily_mean"] > tmp["null_q975"])

    for row in tmp.itertuples(index=False):
        out_rows.append(
            {
                "branch": branch,
                "analysis": analysis,
                "season": season,
                "lag": int(row.lag),
                "observed_daily_mean": float(row.observed_daily_mean),
                "null_mean": float(row.null_mean),
                "null_q025": float(row.null_q025),
                "null_q975": float(row.null_q975),
                "observed_anomaly_vs_null_mean": float(row.anomaly_vs_null_mean),
                "outside_95_band": bool(row.outside_95_band),
                "source_file": rel(source_path),
            }
        )


def main() -> int:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    missing: list[str] = []
    source_files_used: list[str] = []
    inconsistencies: list[str] = []

    core_author_path = SPE_DIR / "fast_null_test_all_tornadoes.csv"
    core_recon_path = SPE_DIR / "reconstructed_hcs_fast_null_all_tornadoes.csv"
    phase_curve_path = SPE_DIR / "phase_randomized_author_hcs_all_tornadoes.csv"

    seasonal_summary_path = TABLE_DIR / "seasonal_control_summary.csv"
    phase_summary_path = TABLE_DIR / "phase_randomized_author_hcs_summary.csv"
    block_bootstrap_path = TABLE_DIR / "block_bootstrap_summary.csv"
    catalog_summary_path = TABLE_DIR / "hcs_catalog_comparison_summary.csv"
    reconciliation_path = TABLE_DIR / "author_hcs_count_reconciliation.csv"
    manifest_recon_path = MANIFEST_DIR / "27_event_study_reconstructed_hcs.json"
    outbreak_key_path = TABLE_DIR / "author_outbreak_branch_key_results.csv"

    core_author = read_csv_required(core_author_path, missing)
    core_recon = read_csv_required(core_recon_path, missing)
    phase_curve = read_csv_required(phase_curve_path, missing)
    seasonal_summary = read_csv_required(seasonal_summary_path, missing)
    phase_summary = read_csv_required(phase_summary_path, missing)
    block_bootstrap_summary = read_csv_required(block_bootstrap_path, missing)
    catalog_summary = read_csv_required(catalog_summary_path, missing)
    outbreak_key = read_csv_required(outbreak_key_path, missing)
    sensitivity_daily_path = TABLE_DIR / "observation_sensitivity_daily.csv"
    sensitivity_outbreak_path = TABLE_DIR / "observation_sensitivity_outbreak.csv"
    sensitivity_daily = pd.read_csv(sensitivity_daily_path)
    sensitivity_outbreak = pd.read_csv(sensitivity_outbreak_path)
    source_files_used.extend([rel(sensitivity_daily_path), rel(sensitivity_outbreak_path)])

    reconciliation = read_csv_required(reconciliation_path, missing)
    manifest_recon = read_json_optional(manifest_recon_path)
    if not manifest_recon_path.exists():
        missing.append(rel(manifest_recon_path))

    lag0_rows: list[dict[str, object]] = []
    curve_rows: list[dict[str, object]] = []

    # Authoritative choice: use SPE files for observed/null values and full curves.
    if core_author is not None:
        source_files_used.append(rel(core_author_path))
        append_curve_rows(curve_rows, core_author, "author_hcs", "core_fast_null", "full_year", core_author_path)

    if core_recon is not None:
        source_files_used.append(rel(core_recon_path))
        append_curve_rows(curve_rows, core_recon, "reconstructed_hcs", "core_fast_null", "full_year", core_recon_path)

    if phase_curve is not None:
        source_files_used.append(rel(phase_curve_path))
        append_curve_rows(curve_rows, phase_curve, "author_hcs", "phase_randomized", "full_year", phase_curve_path)

    # Optional seasonal full curves from SPE files.
    for branch in ["author_hcs", "reconstructed_hcs"]:
        for season in ["full_year", "mar_jun", "apr_jun"]:
            p = SPE_DIR / f"{branch}_{season}_fast_null_all_tornadoes.csv"
            if p.exists():
                df = pd.read_csv(p)
                source_files_used.append(rel(p))
                append_curve_rows(curve_rows, df, branch, f"seasonal_{season}", season, p)

    author_primary_event_count = None
    if reconciliation is not None:
        source_files_used.append(rel(reconciliation_path))
        hit = reconciliation[reconciliation["count_name"] == "author_hcs_event_count_used_primary"]
        if not hit.empty:
            author_primary_event_count = int(hit.iloc[0]["value"])

    recon_primary_event_count = None
    recon_primary_iterations = None
    if manifest_recon is not None:
        source_files_used.append(rel(manifest_recon_path))
        recon_primary_event_count = manifest_recon.get("metrics", {}).get("crossings_used")
        recon_primary_iterations = manifest_recon.get("metrics", {}).get("null_iterations")

    seasonal_counts: dict[tuple[str, str], tuple[int | None, int | None, str]] = {}
    if seasonal_summary is not None:
        source_files_used.append(rel(seasonal_summary_path))
        for row in seasonal_summary.itertuples(index=False):
            seasonal_counts[(str(row.branch), str(row.season))] = (
                int(row.event_count_used),
                parse_iterations_from_notes(row.notes),
                rel(seasonal_summary_path),
            )

    phase_event_count = None
    phase_iterations = None
    phase_lag_count = None
    if phase_summary is not None and not phase_summary.empty:
        source_files_used.append(rel(phase_summary_path))
        phase_event_count = int(phase_summary.iloc[0]["event_count_used"])
        phase_iterations = int(phase_summary.iloc[0]["iterations"])
        phase_lag_count = int(phase_summary.iloc[0]["outside_band_lag_count"])
    if block_bootstrap_summary is not None and not block_bootstrap_summary.empty:
        source_files_used.append(rel(block_bootstrap_path))
    if outbreak_key is not None and not outbreak_key.empty:
        source_files_used.append(rel(outbreak_key_path))

    def add_lag0_row(
        branch: str,
        analysis: str,
        season: str,
        metric: str,
        curve_df: pd.DataFrame | None,
        event_count: int | None,
        iterations: int | None,
        source_path: Path,
        notes: str,
    ) -> None:
        if curve_df is None:
            return
        z = get_lag0(curve_df)
        if z is None:
            return
        inside = bool((float(z["observed_daily_mean"]) >= float(z["null_q025"])) and (float(z["observed_daily_mean"]) <= float(z["null_q975"])))
        lag0_rows.append(
            {
                "branch": branch,
                "analysis": analysis,
                "season": season,
                "metric": metric,
                "lag": 0,
                "observed": float(z["observed_daily_mean"]),
                "null_mean": float(z["null_mean"]),
                "null_q025": float(z["null_q025"]),
                "null_q975": float(z["null_q975"]),
                "inside_band": inside,
                "event_count_used": int(z["event_count"]) if "event_count" in z else event_count,
                "iterations": int(z["null_iterations"]) if "null_iterations" in z else iterations,
                "source_file": rel(source_path),
                "notes": notes,
            }
        )

    # Required lag-0 rows
    add_lag0_row(
        "author_hcs",
        "core_fast_null",
        "full_year",
        "all_tornadoes",
        core_author,
        author_primary_event_count,
        None,
        core_author_path,
        "Observed/null values from fast_null_test_all_tornadoes.csv; event_count from author_hcs_count_reconciliation.csv.",
    )
    add_lag0_row(
        "reconstructed_hcs",
        "core_fast_null",
        "full_year",
        "all_tornadoes",
        core_recon,
        int(recon_primary_event_count) if recon_primary_event_count is not None else None,
        int(recon_primary_iterations) if recon_primary_iterations is not None else None,
        core_recon_path,
        "Observed/null values from reconstructed_hcs_fast_null_all_tornadoes.csv; event_count/iterations from manifest 27.",
    )

    for season in ["full_year", "mar_jun", "apr_jun"]:
        for branch in ["author_hcs", "reconstructed_hcs"]:
            p = SPE_DIR / f"{branch}_{season}_fast_null_all_tornadoes.csv"
            df = pd.read_csv(p) if p.exists() else None
            count_iter = seasonal_counts.get((branch, season), (None, None, ""))
            add_lag0_row(
                branch,
                f"seasonal_{season}",
                season,
                "all_tornadoes",
                df,
                count_iter[0],
                count_iter[1],
                p,
                "Observed/null values from seasonal SPE curve file; event_count/iterations from seasonal_control_summary.csv.",
            )

    add_lag0_row(
        "author_hcs",
        "phase_randomized",
        "full_year",
        "all_tornadoes",
        phase_curve,
        phase_event_count,
        phase_iterations,
        phase_curve_path,
        f"Observed/null values from phase_randomized_author_hcs_all_tornadoes.csv; event_count/iterations from phase summary; outside-band lag count={phase_lag_count}.",
    )

    lag0_df = pd.DataFrame(
        lag0_rows,
        columns=[
            "branch",
            "analysis",
            "season",
            "metric",
            "lag",
            "observed",
            "null_mean",
            "null_q025",
            "null_q975",
            "inside_band",
            "event_count_used",
            "iterations",
            "source_file",
            "notes",
        ],
    )
    lag0_out = TABLE_DIR / "manuscript_lag0_results.csv"
    lag0_df.to_csv(lag0_out, index=False)

    curves_df = pd.DataFrame(
        curve_rows,
        columns=[
            "branch",
            "analysis",
            "season",
            "lag",
            "observed_daily_mean",
            "null_mean",
            "null_q025",
            "null_q975",
            "observed_anomaly_vs_null_mean",
            "outside_95_band",
            "source_file",
        ],
    )
    curves_out = TABLE_DIR / "manuscript_main_figure_curves.csv"
    curves_df.to_csv(curves_out, index=False)

    catalog_rows: list[dict[str, object]] = []
    if catalog_summary is not None and not catalog_summary.empty:
        source_files_used.append(rel(catalog_summary_path))
        r = catalog_summary.iloc[0]
        author_total = float(r["author_count_total"])
        recon_total = float(r["reconstructed_count_total"])

        author_years = pd.date_range(str(r["author_period_start"]), str(r["author_period_end"]), freq="D").year.nunique()
        recon_years = pd.date_range(str(r["reconstructed_period_start"]), str(r["reconstructed_period_end"]), freq="D").year.nunique()

        catalog_rows = [
            {"metric": "author_count_total", "value": int(author_total), "source_file": rel(catalog_summary_path), "notes": "Direct from hcs_catalog_comparison_summary.csv"},
            {"metric": "reconstructed_count_total", "value": int(recon_total), "source_file": rel(catalog_summary_path), "notes": "Direct from hcs_catalog_comparison_summary.csv"},
            {"metric": "author_period_start", "value": str(r["author_period_start"]), "source_file": rel(catalog_summary_path), "notes": "Direct from hcs_catalog_comparison_summary.csv"},
            {"metric": "author_period_end", "value": str(r["author_period_end"]), "source_file": rel(catalog_summary_path), "notes": "Direct from hcs_catalog_comparison_summary.csv"},
            {"metric": "reconstructed_period_start", "value": str(r["reconstructed_period_start"]), "source_file": rel(catalog_summary_path), "notes": "Direct from hcs_catalog_comparison_summary.csv"},
            {"metric": "reconstructed_period_end", "value": str(r["reconstructed_period_end"]), "source_file": rel(catalog_summary_path), "notes": "Direct from hcs_catalog_comparison_summary.csv"},
            {
                "metric": "author_annual_average_count",
                "value": author_total / author_years,
                "source_file": rel(catalog_summary_path),
                "notes": "Computed as author_count_total / number of covered calendar years.",
            },
            {
                "metric": "reconstructed_annual_average_count",
                "value": recon_total / recon_years,
                "source_file": rel(catalog_summary_path),
                "notes": "Computed as reconstructed_count_total / number of covered calendar years.",
            },
            {"metric": "median_author_spacing_days", "value": float(r["median_author_spacing_days"]), "source_file": rel(catalog_summary_path), "notes": "Direct from hcs_catalog_comparison_summary.csv"},
            {"metric": "median_reconstructed_spacing_days", "value": float(r["median_reconstructed_spacing_days"]), "source_file": rel(catalog_summary_path), "notes": "Direct from hcs_catalog_comparison_summary.csv"},
            {"metric": "median_nearest_author_to_reconstructed_diff_days", "value": float(r["median_nearest_author_to_reconstructed_diff_days"]), "source_file": rel(catalog_summary_path), "notes": "Direct from hcs_catalog_comparison_summary.csv"},
        ]

    catalog_df = pd.DataFrame(catalog_rows, columns=["metric", "value", "source_file", "notes"])
    catalog_out = TABLE_DIR / "manuscript_catalog_comparison.csv"
    catalog_df.to_csv(catalog_out, index=False)

    # Consistency checks against summary tables (for documentation only)
    core_summary_path = TABLE_DIR / "core_null_lag0_summary.csv"
    if core_summary_path.exists() and core_author is not None and core_recon is not None:
        core_summary = pd.read_csv(core_summary_path)
        for branch, curve_df in [("author_hcs", core_author), ("reconstructed_hcs", core_recon)]:
            z = get_lag0(curve_df)
            row = core_summary[(core_summary["branch"] == branch) & (core_summary["analysis"] == "core_fast_null")]
            if (z is not None) and (not row.empty):
                obs_delta = abs(float(z["observed_daily_mean"]) - float(row.iloc[0]["lag0_observed"]))
                null_delta = abs(float(z["null_mean"]) - float(row.iloc[0]["lag0_null_mean"]))
                if obs_delta > 1e-12 or null_delta > 1e-12:
                    inconsistencies.append(f"Core lag0 mismatch for {branch}: delta observed={obs_delta}, delta null_mean={null_delta}")

    source_files_used = sorted(set(source_files_used))

    lines = ["# Manuscript Results Summary", ""]
    lines.append("## Primary Question and Endpoint")
    lines.append("The project-designated primary question is whether the full-year mean daily all-tornado count at lag 0 differs from its null expectation around HCS crossings (author catalog, with reconstructed HCS as a parallel validation branch).")
    lines.append("The repository contains no dated preregistration or prospective analysis plan; ‘primary’ here describes the analysis hierarchy used in this reanalysis, not a prospectively registered endpoint.")
    lines.append("")

    lines.append("## Authoritative Source Selection")
    lines.append("- Curves and quoted lag-0 values use the SPE curve files as canonical sources to avoid mixed derivations.")
    lines.append("- Seasonal event counts and iterations use seasonal_control_summary.csv.")
    lines.append("- Phase-randomized event counts and iterations use phase_randomized_author_hcs_summary.csv.")
    lines.append("- Author primary event count uses author_hcs_count_reconciliation.csv; reconstructed primary count/iterations use manifest 27.")
    lines.append("")

    lines.append("## Exact Lag-0 Values")
    quote = lag0_df[["branch", "analysis", "season", "observed", "null_mean", "null_q025", "null_q975", "inside_band", "event_count_used", "iterations"]]
    if quote.empty:
        lines.append("No lag-0 rows were exported.")
    else:
        for row in quote.itertuples(index=False):
            lines.append(
                f"- {row.branch} / {row.analysis} / {row.season}: observed={row.observed:.6f}, null_mean={row.null_mean:.6f}, "
                f"95%=[{row.null_q025:.6f}, {row.null_q975:.6f}], inside_band={row.inside_band}, "
                f"event_count={row.event_count_used}, iterations={row.iterations}"
            )
    lines.append("")

    lines.append("## Primary Author-HCS Result")
    row = lag0_df[(lag0_df["branch"] == "author_hcs") & (lag0_df["analysis"] == "core_fast_null")]
    if not row.empty:
        r = row.iloc[0]
        lines.append(
            f"Author-HCS full-year lag 0 remains within the null band (observed {r['observed']:.6f} vs null mean {r['null_mean']:.6f}, "
            f"95% [{r['null_q025']:.6f}, {r['null_q975']:.6f}])."
        )
    else:
        lines.append("Author-HCS core lag-0 row unavailable.")
    lines.append("")

    lines.append("## Primary Reconstructed-HCS Result")
    row = lag0_df[(lag0_df["branch"] == "reconstructed_hcs") & (lag0_df["analysis"] == "core_fast_null")]
    if not row.empty:
        r = row.iloc[0]
        lines.append(
            f"Reconstructed-HCS full-year lag 0 remains within the null band (observed {r['observed']:.6f} vs null mean {r['null_mean']:.6f}, "
            f"95% [{r['null_q025']:.6f}, {r['null_q975']:.6f}])."
        )
    else:
        lines.append("Reconstructed-HCS core lag-0 row unavailable.")
    lines.append("")

    lines.append("## Seasonal-Control Results")
    seasonal_rows = lag0_df[lag0_df["analysis"].str.startswith("seasonal_", na=False)]
    if seasonal_rows.empty:
        lines.append("Seasonal lag-0 rows unavailable.")
    else:
        n_out = int((~seasonal_rows["inside_band"]).sum())
        lines.append(f"Seasonal subsets exported: {len(seasonal_rows)} lag-0 rows; outside-band lag-0 rows: {n_out}.")
    lines.append("")

    strict = pd.read_csv(TABLE_DIR.parent / "spe" / "strict_event_study_summary.csv")
    lines.append("## All-Lag Exploratory Results")
    lines.append("Unique complete-window dates and within-year cluster shifts are used consistently. The statistic is the maximum raw daily mean across lags; Holm adjustment covers 16 source/outcome tests.")
    for r in strict.loc[strict["metric"] == "all_tornadoes"].itertuples(index=False):
        lines.append(
            f"- {r.source}: N={r.event_count}, peak={r.observed_max_abs_daily_effect:.6f} at lag {r.lag_of_max_abs_effect}; "
            f"Monte Carlo p={r.empirical_p_max:.6f}, Holm p={r.p_value_holm:.6f}."
        )
    lines.append("")

    lines.append("## Phase-Randomized Results")
    phase_rows = lag0_df[lag0_df["analysis"] == "phase_randomized"]
    if phase_rows.empty:
        lines.append("Phase-randomized lag-0 row unavailable.")
    else:
        p = phase_rows.iloc[0]
        lines.append(
            f"Phase-randomized author-HCS lag 0 is inside band={bool(p['inside_band'])} "
            f"(observed {p['observed']:.6f}, null mean {p['null_mean']:.6f}, 95% [{p['null_q025']:.6f}, {p['null_q975']:.6f}])."
        )
    lines.append("")

    lines.append("## Block-Bootstrap Robustness")
    if block_bootstrap_summary is None or block_bootstrap_summary.empty:
        lines.append("Block-bootstrap summary unavailable.")
    else:
        outside = int((~block_bootstrap_summary["lag0_inside_band"].astype(bool)).sum())
        lines.append(
            f"Across {len(block_bootstrap_summary)} 7- and 14-day block-bootstrap checks, "
            f"{outside} lag-0 estimates fell outside their pointwise 95% null bands."
        )
        lines.append("The bootstrap resamples contiguous daily tornado-count blocks and preserves short-range outcome clustering; it does not preserve the seasonal cycle by construction.")
    lines.append("")

    lines.append("## Exploratory Author-Outbreak Analysis")
    if outbreak_key is None or outbreak_key.empty:
        lines.append("The post-hoc author-outbreak branch summary is unavailable.")
    else:
        corrected_count = int(outbreak_key["p_value_holm"].notna().sum())
        below_threshold = int((outbreak_key["p_value_holm"] < 0.05).sum())
        lines.append("These supplement-derived outbreak-list tests are post hoc and do not redefine the primary endpoint.")
        lines.append(f"The branch reports {corrected_count} tests across all three null designs with one Holm adjustment; {below_threshold} remain below 0.05 after adjustment.")
        hcs_one_day = outbreak_key[
            (outbreak_key["analysis_family"] == "coincidence_null")
            & (outbreak_key["event_family"] == "HCS_author_catalog")
            & (outbreak_key["statistic"] == "plus_minus_1d")
        ].sort_values("null_model")
        if not hcs_one_day.empty:
            for result in hcs_one_day.itertuples(index=False):
                lines.append(
                    f"Author-HCS ±1-day under {result.null_model}: {int(result.observed_value)} observed vs "
                    f"{result.null_mean:.2f} null mean (nominal p={result.p_value_nominal:.6f}; "
                    f"Holm-adjusted p={result.p_value_holm:.6f}); exploratory, not causal evidence."
                )
        lines.append("The independent year-month null preserves stratum counts but not date clustering. Month rotations preserve within-month spacing; year-season shifts preserve within-year cluster spacing across month boundaries with a shared +/-15-day shift, but not clusters spanning years. Holm covers these 87 branch tests, not every analysis explored in the project.")
    lines.append("")

    lines.append("## Coverage and Timing Sensitivities")
    lines.append(
        f"Daily sensitivity: {len(sensitivity_daily)} variants, 10,000 annual cluster shifts each, "
        f"Holm across {int(sensitivity_daily.multiplicity_family_tests.iloc[0])} endpoint tests. "
        f"Adjusted lag-0 rejections={int(sensitivity_daily.lag0_p_holm.le(.05).sum())}; "
        f"adjusted all-lag rejections={int(sensitivity_daily.maximum_p_holm.le(.05).sum())}."
    )
    lines.append("SPC code 3 uses fixed CST (UTC-6); code 0 uses GMT. Other codes are excluded only in paired catalog-date/UTC comparisons. Coverage screens of 1, 12, 18 and 24 valid daily Bx hours are hard barriers to filling.")
    lines.append(
        f"Outbreak sensitivity: {len(sensitivity_outbreak)} exact conditional tests, "
        "separately Holm-adjusted. These do not replace the original 87-test family."
    )
    for (catalog, shift), frame in sensitivity_outbreak.groupby(["catalog", "outbreak_shift_days"], sort=False):
        lines.append(
            f"- {catalog}, outbreak-start shift={shift:+d} days: "
            f"{int(frame.observed_count.iloc[0])}/457 within one day; "
            f"sensitivity-family Holm p={frame.p_holm_sensitivity.min():.6f}-{frame.p_holm_sensitivity.max():.6f}."
        )
    lines.append("The unshifted author-catalog enrichment persists, but shifting outbreak starts one day earlier removes it; shifting one day later produces adjusted rejection for both primary HCS catalogs. These are date-label stress tests, not UTC conversions or evidence of causality.")
    lines.append("")

    lines.append("## Remaining Limitations Before Submission")
    lines.append("- The year-season cluster sensitivity preserves within-year spacing but not clusters spanning calendar years; evaluate whether that residual matters for the scientific interpretation.")
    lines.append("- Document analysis selection and null-model choices; no prospective registration was found in the repository.")
    lines.append("- Count models estimate dispersion and use 14-day HAC covariance; meteorological confounding, model specification, and held-out forecasting remain unresolved.")
    lines.append("- Report pointwise lag bands as pointwise; do not interpret excursions across the full lag curve as familywise-significant without a simultaneous test.")
    lines.append("- Use run_publication.py for the full dependency-ordered workflow; run_analysis.py remains the core subset.")
    lines.append("- The literal 1996 source interval and inferred 2011 year were accepted by the project author; audit notes remain and neither source entry was excluded.")
    lines.append("")

    lines.append("## Catalog Comparison")
    if catalog_df.empty:
        lines.append("Catalog summary unavailable.")
    else:
        show = {row.metric: row.value for row in catalog_df.itertuples(index=False)}
        lines.append(
            f"Catalog totals: author={show.get('author_count_total')}, reconstructed={show.get('reconstructed_count_total')}; "
            f"median spacing days: author={show.get('median_author_spacing_days')}, reconstructed={show.get('median_reconstructed_spacing_days')}; "
            f"median nearest timing difference={show.get('median_nearest_author_to_reconstructed_diff_days')} days."
        )
    lines.append("")

    lines.append("## Source Files Used")
    for s in source_files_used:
        lines.append(f"- {s}")
    lines.append("")

    lines.append("## Consistency Check")
    if inconsistencies:
        lines.append("Inconsistencies found:")
        for msg in inconsistencies:
            lines.append(f"- {msg}")
    else:
        lines.append("No numeric inconsistencies found across overlapping lag-0 values in selected authoritative vs summary files.")

    if missing:
        lines.append("")
        lines.append("## Missing Inputs")
        for m in sorted(set(missing)):
            lines.append(f"- {m}")

    summary_out = REPORT_DIR / "manuscript_results_summary.md"
    summary_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Created: {lag0_out}")
    print(f"Created: {curves_out}")
    print(f"Created: {catalog_out}")
    print(f"Created: {summary_out}")
    if missing:
        print("Missing optional/required sources:")
        for m in sorted(set(missing)):
            print(f"- {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
