"""Evaluation utilities for baseline demand forecasting models."""

import math

import pandas as pd

from config import INTERMITTENT_SELECTION_WEIGHTS

MODEL_SIMPLICITY_RANK = {
    "naive": 1,
    "seasonal_naive_lag_7": 2,
    "moving_average_7": 3,
    "moving_average_14": 4,
    "moving_average_30": 5,
    "linear_regression": 6,
    "knn_regressor": 7,
    "random_forest": 8,
    "gradient_boosting": 9,
}


def evaluate_forecasts(forecast_results: pd.DataFrame) -> pd.DataFrame:
    """Calculate per-SKU, per-model forecast performance metrics."""
    if forecast_results.empty:
        return _empty_performance_frame()

    performance_rows = []
    grouped = forecast_results.groupby(["sku_id", "model_name"], sort=True)
    for (sku_id, model_name), model_results in grouped:
        performance_rows.append(_evaluate_model_results(sku_id, model_name, model_results))

    performance = pd.DataFrame(performance_rows)
    performance = _add_mase(performance)
    performance = _add_metric_warnings(performance)
    performance = _add_selection_scores(performance)
    return performance


def build_model_registry(model_performance: pd.DataFrame) -> pd.DataFrame:
    """Select one champion model per SKU using WAPE and model simplicity."""
    if model_performance.empty:
        return pd.DataFrame(
            columns=[
                "sku_id",
                "champion_model",
                "champion_wape",
                "champion_mae",
                "champion_bias",
                "champion_confidence_score",
                "champion_risk_level",
                "champion_selection_score",
                "champion_selection_metric",
                "champion_metric_warning",
                "selection_reason",
            ]
        )

    registry_rows = []
    for sku_id, sku_performance in model_performance.groupby("sku_id", sort=True):
        champion = _select_champion(sku_performance)
        registry_rows.append(
            {
                "sku_id": sku_id,
                "champion_model": champion["model_name"],
                "champion_wape": champion["wape"],
                "champion_mae": champion["mae"],
                "champion_bias": champion["bias"],
                "champion_confidence_score": champion["average_confidence_score"],
                "champion_risk_level": champion["dominant_risk_level"],
                "champion_selection_score": champion["selection_score"],
                "champion_selection_metric": champion["selection_metric"],
                "champion_metric_warning": champion["metric_warning"],
                "selection_reason": _selection_reason(champion, sku_performance),
            }
        )

    return pd.DataFrame(registry_rows)


def _evaluate_model_results(sku_id: str, model_name: str, results: pd.DataFrame) -> dict[str, object]:
    """Return metric values for one SKU/model result set."""
    errors = results["error"]
    absolute_errors = results["absolute_error"]
    actuals = results["actual_demand"]

    return {
        "sku_id": sku_id,
        "model_name": model_name,
        "mae": float(absolute_errors.mean()),
        "rmse": float(math.sqrt((errors.pow(2)).mean())),
        "wape": _wape(absolute_errors, actuals),
        "smape": _smape(results["forecast_quantity"], actuals),
        "bias": float(errors.mean()),
        "zero_demand_ratio": float((actuals == 0).mean()),
        "test_period_start": results["target_date"].min(),
        "test_period_end": results["target_date"].max(),
        "observations_used": int(len(results)),
        "average_confidence_score": _average_confidence_score(results),
        "average_interval_width": _average_interval_width(results),
        "dominant_risk_level": _dominant_risk_level(results),
    }


def _wape(absolute_errors: pd.Series, actuals: pd.Series) -> float:
    """Return weighted absolute percentage error."""
    denominator = actuals.abs().sum()
    if denominator == 0:
        return 0.0 if absolute_errors.sum() == 0 else float("inf")
    return float(absolute_errors.sum() / denominator)


def _smape(forecasts: pd.Series, actuals: pd.Series) -> float:
    """Return symmetric MAPE with safe zero handling."""
    denominator = forecasts.abs() + actuals.abs()
    smape_values = pd.Series(0.0, index=actuals.index)
    valid_denominator = denominator > 0
    smape_values.loc[valid_denominator] = (
        2 * (forecasts.loc[valid_denominator] - actuals.loc[valid_denominator]).abs()
    ) / denominator.loc[valid_denominator]
    return float(smape_values.mean())


def _add_mase(performance: pd.DataFrame) -> pd.DataFrame:
    """Add MASE using the SKU naive model MAE as the scaling denominator."""
    enriched = performance.copy()
    naive_mae = (
        enriched[enriched["model_name"] == "naive"][["sku_id", "mae"]]
        .rename(columns={"mae": "naive_mae"})
        .copy()
    )
    enriched = enriched.merge(naive_mae, on="sku_id", how="left")
    enriched["mase"] = enriched["mae"] / enriched["naive_mae"]
    invalid_mase = enriched["naive_mae"].isna() | (enriched["naive_mae"] <= 0)
    enriched.loc[invalid_mase, "mase"] = pd.NA
    return enriched.drop(columns=["naive_mae"])


def _add_metric_warnings(performance: pd.DataFrame) -> pd.DataFrame:
    """Add metric stability warnings for low or intermittent demand."""
    enriched = performance.copy()
    warnings = []
    for row in enriched.itertuples(index=False):
        row_warnings = []
        average_actual = _average_actual_demand(row)
        if average_actual < 1:
            row_warnings.append("LOW_DEMAND_WAPE_UNSTABLE")
        if row.zero_demand_ratio >= 0.30:
            row_warnings.append("INTERMITTENT_DEMAND_USE_MASE")
        if pd.isna(row.mase):
            row_warnings.append("INSUFFICIENT_NAIVE_BASELINE_FOR_MASE")
        warnings.append(";".join(row_warnings))
    enriched["metric_warning"] = warnings
    return enriched


def _add_selection_scores(performance: pd.DataFrame) -> pd.DataFrame:
    """Add robust champion selection scores per SKU."""
    scored_frames = []
    for _, sku_performance in performance.groupby("sku_id", sort=False):
        sku_scored = sku_performance.copy()
        use_rank_score = _should_use_rank_score(sku_scored)
        if use_rank_score:
            sku_scored["selection_score"] = _weighted_rank_score(sku_scored)
            sku_scored["selection_metric"] = "weighted_rank_wape_mae_mase_bias"
        else:
            sku_scored["selection_score"] = sku_scored["wape"]
            sku_scored["selection_metric"] = "wape"
        scored_frames.append(sku_scored)
    return pd.concat(scored_frames, ignore_index=True)


def _average_actual_demand(row: object) -> float:
    """Estimate average actual demand from WAPE inputs when available."""
    if row.wape == 0:
        return float("inf") if row.mae == 0 else 0.0
    return float(row.mae / row.wape)


def _should_use_rank_score(sku_performance: pd.DataFrame) -> bool:
    """Return True for intermittent or very low-demand SKU test periods."""
    zero_ratio = sku_performance["zero_demand_ratio"].max()
    average_actual = sku_performance.apply(_average_actual_demand, axis=1).replace([float("inf")], pd.NA).min()
    return bool(zero_ratio >= 0.30 or (pd.notna(average_actual) and average_actual < 1))


def _weighted_rank_score(sku_performance: pd.DataFrame) -> pd.Series:
    """Return a robust rank-based score using multiple error views."""
    weights = INTERMITTENT_SELECTION_WEIGHTS
    wape_rank = sku_performance["wape"].rank(method="average", na_option="bottom")
    mae_rank = sku_performance["mae"].rank(method="average", na_option="bottom")
    bias_rank = sku_performance["bias"].abs().rank(method="average", na_option="bottom")
    mase_rank = sku_performance["mase"].rank(method="average", na_option="bottom")

    return (
        weights["wape_rank"] * wape_rank
        + weights["mae_rank"] * mae_rank
        + weights["mase_rank"] * mase_rank
        + weights["absolute_bias_rank"] * bias_rank
    )


def _select_champion(sku_performance: pd.DataFrame) -> pd.Series:
    """Select the best model, preferring simpler models for close ties."""
    ranked = sku_performance.copy()
    ranked["simplicity_rank"] = ranked["model_name"].map(MODEL_SIMPLICITY_RANK).fillna(999)
    ranked["absolute_bias"] = ranked["bias"].abs()
    best_score = ranked["selection_score"].min()
    close_candidates = ranked[ranked["selection_score"] <= best_score + 0.01]
    if ranked["selection_metric"].iloc[0] == "wape":
        return close_candidates.sort_values(["selection_score", "mae", "absolute_bias", "simplicity_rank"]).iloc[0]
    return close_candidates.sort_values(["selection_score", "simplicity_rank", "wape", "mae", "absolute_bias"]).iloc[0]


def _average_confidence_score(results: pd.DataFrame) -> float:
    """Return average confidence when available."""
    if "forecast_confidence_score" not in results.columns:
        return 0.0
    return float(pd.to_numeric(results["forecast_confidence_score"], errors="coerce").mean())


def _average_interval_width(results: pd.DataFrame) -> float:
    """Return average prediction interval width when available."""
    if "lower_bound" not in results.columns or "upper_bound" not in results.columns:
        return 0.0
    width = pd.to_numeric(results["upper_bound"], errors="coerce") - pd.to_numeric(results["lower_bound"], errors="coerce")
    return float(width.mean())


def _dominant_risk_level(results: pd.DataFrame) -> str:
    """Return the most common forecast risk level for a model."""
    if "forecast_risk_level" not in results.columns or results["forecast_risk_level"].dropna().empty:
        return "UNKNOWN"
    return str(results["forecast_risk_level"].mode().iloc[0])


def _selection_reason(champion: pd.Series, sku_performance: pd.DataFrame) -> str:
    """Build a readable champion model selection reason."""
    best_score = sku_performance["selection_score"].min()
    if champion["selection_metric"] == "wape":
        return f"Selected lowest WAPE on the shared final test period ({champion['wape']:.4f})."
    if champion["selection_score"] == best_score:
        return (
            "Selected best robust rank score for intermittent or low-demand SKU "
            f"({champion['selection_score']:.4f}); considered WAPE, MAE, MASE, and bias."
        )
    return (
        "Selected simpler model because its selection score was within 0.01 of the best "
        f"score ({champion['selection_score']:.4f} vs {best_score:.4f})."
    )


def _empty_performance_frame() -> pd.DataFrame:
    """Return an empty performance dataframe with the expected columns."""
    return pd.DataFrame(
        columns=[
            "sku_id",
            "model_name",
            "mae",
            "rmse",
            "wape",
            "smape",
            "mase",
            "bias",
            "zero_demand_ratio",
            "metric_warning",
            "selection_score",
            "selection_metric",
            "test_period_start",
            "test_period_end",
            "observations_used",
            "average_confidence_score",
            "average_interval_width",
            "dominant_risk_level",
        ]
    )
