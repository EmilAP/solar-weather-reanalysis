from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import statsmodels.api as sm

from _utils import day_of_year_features, load_config, make_logger, within_days_indicator, write_dataframe, write_script_manifest


EVENT_FILES = {
    "near_author_hcs": "data/derived/catalogs/author_hcs_catalog.csv",
    "near_reconstructed_hcs": "data/derived/catalogs/independent_hcs_catalog.csv",
    "near_cir": "data/derived/catalogs/cir_proxy_catalog.csv",
    "near_hss": "data/derived/catalogs/hss_onset_catalog.csv",
}


def load_event_dates(path: str) -> list[pd.Timestamp]:
    df = pd.read_csv(path)
    for column in ["datetime_utc", "analysis_time_utc", "date"]:
        if column in df.columns:
            return pd.to_datetime(df[column], errors="coerce").dropna().dt.normalize().tolist()
    return []


def fit_and_collect(model_name: str, endog: pd.Series, exog: pd.DataFrame, family) -> tuple[pd.DataFrame, dict[str, float]]:
    fit = sm.GLM(endog, exog, family=family).fit()
    coef = pd.DataFrame(
        {
            "model": model_name,
            "term": fit.params.index,
            "coef": fit.params.values,
            "stderr": fit.bse.values,
            "pvalue": fit.pvalues.values,
        }
    )
    metrics = {
        "aic": float(fit.aic),
        "deviance": float(fit.deviance),
    }
    return coef, metrics


def main() -> int:
    logger = make_logger("20_run_daily_models")
    cfg = load_config()
    daily = pd.read_csv("data/derived/daily/analysis_daily.csv", parse_dates=["date"])

    features = day_of_year_features(daily["date"])
    model_df = pd.concat([daily.reset_index(drop=True), features], axis=1)
    model_df["trend_days"] = (model_df["date"] - model_df["date"].min()).dt.days

    for indicator, path in EVENT_FILES.items():
        if Path(path).exists():
            event_dates = load_event_dates(path)
            model_df[indicator] = within_days_indicator(model_df["date"], event_dates, int(cfg["models"]["event_indicator_window_days"]))
        else:
            model_df[indicator] = 0

    baseline_cols = ["sin_doy", "cos_doy", "trend_days"]
    augmented_cols = baseline_cols + cfg["models"]["predictors"]

    baseline_x = sm.add_constant(model_df[baseline_cols], has_constant="add")
    augmented_x = sm.add_constant(model_df[augmented_cols], has_constant="add")

    coef_frames = []
    metrics_rows = []
    for target in ["all_tornadoes", "strong_tornadoes"]:
        coef, metrics = fit_and_collect(f"baseline_nb_{target}", model_df[target], baseline_x, sm.families.NegativeBinomial())
        coef_frames.append(coef)
        metrics_rows.append({"model": f"baseline_nb_{target}", **metrics})
        coef, metrics = fit_and_collect(f"augmented_nb_{target}", model_df[target], augmented_x, sm.families.NegativeBinomial())
        coef_frames.append(coef)
        metrics_rows.append({"model": f"augmented_nb_{target}", **metrics})

    coef, metrics = fit_and_collect("outbreak_logit", model_df["outbreak_day"], augmented_x, sm.families.Binomial())
    coef_frames.append(coef)
    metrics_rows.append({"model": "outbreak_logit", **metrics})

    coef_df = pd.concat(coef_frames, ignore_index=True)
    metrics_df = pd.DataFrame(metrics_rows)
    outputs = {
        "coefficients": write_dataframe(coef_df, "data/derived/models/model_coefficients"),
        "metrics": write_dataframe(metrics_df, "data/derived/models/model_metrics"),
    }
    write_script_manifest(
        "20_run_daily_models.py",
        ["data/derived/daily/analysis_daily.csv", *EVENT_FILES.values()],
        outputs,
        {"model_count": int(len(metrics_df))},
        assumptions=["Negative-binomial GLMs are used for counts; a logistic GLM is used for outbreak-day probability."],
    )
    logger.info("Fitted %d daily models", len(metrics_df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
