from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

from _utils import make_logger, save_figure, write_dataframe, write_script_manifest


def main() -> int:
    logger = make_logger("22_generate_figures_and_tables")
    outputs: dict[str, object] = {}

    tornado = pd.read_csv("data/derived/daily/tornado_daily.csv", parse_dates=["date"])
    climatology = tornado.groupby(tornado["date"].dt.dayofyear, as_index=False).agg(
        all_tornadoes=("all_tornadoes", "mean"),
        strong_tornadoes=("strong_tornadoes", "mean"),
    )
    outputs["daily_climatology_table"] = write_dataframe(climatology, "data/derived/tables/daily_tornado_climatology")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(climatology["date"], climatology["all_tornadoes"], color="black", linewidth=1.5, label="All tornadoes")
    ax.plot(climatology["date"], climatology["strong_tornadoes"], color="0.5", linewidth=1.2, label="Strong tornadoes")
    ax.set_title("Daily tornado climatology")
    ax.set_xlabel("Day of year")
    ax.set_ylabel("Mean daily count")
    ax.legend(frameon=False)
    fig.tight_layout()
    outputs["daily_climatology_figure"] = save_figure(fig, "data/derived/figures/daily_tornado_climatology")

    for path, name in [
        ("data/derived/catalogs/author_hcs_catalog.csv", "author_hcs"),
        ("data/derived/catalogs/independent_hcs_catalog.csv", "independent_hcs"),
    ]:
        source = Path(path)
        if not source.exists():
            continue
        df = pd.read_csv(path)
        if "year" not in df.columns:
            for candidate in ["datetime_utc", "date"]:
                if candidate in df.columns:
                    df["year"] = pd.to_datetime(df[candidate], errors="coerce").dt.year
                    break
        yearly = df.groupby("year", as_index=False).size().rename(columns={"size": "count"})
        outputs[f"{name}_yearly_table"] = write_dataframe(yearly, f"data/derived/tables/{name}_yearly_counts")
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(yearly["year"], yearly["count"], color="0.35")
        ax.set_title(f"{name.replace('_', ' ')} event counts by year")
        ax.set_xlabel("Year")
        ax.set_ylabel("Count")
        fig.tight_layout()
        outputs[f"{name}_yearly_figure"] = save_figure(fig, f"data/derived/figures/{name}_counts_by_year")

    coverage_rows = []
    for path in [
        "data/derived/daily/tornado_daily.csv",
        "data/derived/daily/omni_daily.csv",
        "data/derived/catalogs/icme_catalog.csv",
        "data/derived/catalogs/author_hcs_catalog.csv",
        "data/derived/catalogs/independent_hcs_catalog.csv",
        "data/derived/catalogs/cir_hss_catalog.csv",
    ]:
        source = Path(path)
        if not source.exists():
            continue
        df = pd.read_csv(source)
        coverage_rows.append({"dataset": source.name, "rows": len(df)})
    outputs["dataset_coverage_summary"] = write_dataframe(pd.DataFrame(coverage_rows), "data/derived/tables/dataset_coverage_summary")

    model_coef = Path("data/derived/models/model_coefficients.csv")
    if model_coef.exists():
        coef_df = pd.read_csv(model_coef)
        outputs["model_coefficient_summary"] = write_dataframe(coef_df, "data/derived/tables/model_coefficient_summary")

    strict_summary = Path("data/derived/spe/strict_event_study_summary.csv")
    if strict_summary.exists():
        summary_df = pd.read_csv(strict_summary)
        outputs["robustness_summary"] = write_dataframe(summary_df, "data/derived/tables/robustness_summary")

    write_script_manifest("22_generate_figures_and_tables.py", [], outputs, {"output_count": int(len(outputs))}, ok=bool(outputs))
    logger.info("Generated %d figure/table outputs", len(outputs))
    return 0 if outputs else 1


if __name__ == "__main__":
    raise SystemExit(main())
