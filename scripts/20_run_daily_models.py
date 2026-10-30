from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import numpy as np
import statsmodels.api as sm

from _utils import day_of_year_features, load_config, make_logger, within_days_indicator, write_dataframe, write_script_manifest


EVENT_FILES = {
    "near_author_hcs": "data/derived/catalogs/author_hcs_catalog.csv",
    "near_reconstructed_hcs": "data/derived/catalogs/hcs_from_omni.csv",
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
    if isinstance(family, sm.families.NegativeBinomial):
        poisson = sm.GLM(endog, exog, family=sm.families.Poisson()).fit()
        mu = poisson.fittedvalues.to_numpy()
        alpha_start = max(float(np.sum((endog.to_numpy() - mu) ** 2 - mu) / np.sum(mu ** 2)), 0.01)
        start = np.append(poisson.params.to_numpy(), alpha_start)
        fit = sm.NegativeBinomial(endog, exog).fit(
            start_params=start, method="bfgs", maxiter=1000, disp=False,
            cov_type="HAC", cov_kwds={"maxlags": 14},
        )
        if not fit.mle_retvals["converged"]:
            raise RuntimeError(f"{model_name}: estimated-dispersion count model failed to converge.")
    else:
        fit = sm.GLM(endog, exog, family=family).fit(cov_type="HAC", cov_kwds={"maxlags": 14})
    if not np.isfinite(fit.params).all() or not np.isfinite(fit.bse).all():
        raise RuntimeError(f"{model_name}: nonfinite model estimates or uncertainty.")
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
        "deviance": float(fit.deviance) if hasattr(fit, "deviance") else np.nan,
        "dispersion_alpha": float(fit.params["alpha"]) if "alpha" in fit.params else np.nan,
        "covariance": "HAC_14_days",
    }
    return coef, metrics


def main() -> int:
    logger = make_logger("20_run_daily_models")
    cfg = load_config()
    daily = pd.read_csv("data/derived/daily/analysis_daily.csv", parse_dates=["date"])

    features = day_of_year_features(daily["date"])
    model_df = pd.concat([daily.reset_index(drop=True), features], axis=1)
    model_df["trend_days"] = (model_df["date"] - model_df["date"].min()).dt.days / 365.25

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
        coef, metrics = fit_and_collect(f"baseline_nb_{target}", model_df[target], baseline_x, sm.families.NegativeBinomial(alpha=1.0))
        coef_frames.append(coef)
        metrics_rows.append({"model": f"baseline_nb_{target}", **metrics})
        coef, metrics = fit_and_collect(f"augmented_nb_{target}", model_df[target], augmented_x, sm.families.NegativeBinomial(alpha=1.0))
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
        assumptions=["Negative-binomial count models estimate alpha by maximum likelihood; count and logistic models use 14-day HAC covariance. Trend is measured in years. Models are exploratory in-sample fits, not forecast validation."],
    )
    logger.info("Fitted %d daily models", len(metrics_df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
