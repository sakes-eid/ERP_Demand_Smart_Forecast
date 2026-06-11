"""Forecast uncertainty intervals, confidence scoring, and risk labels."""

import pandas as pd

CONFIDENCE_COLUMNS = [
    "p10",
    "p50",
    "p90",
    "lower_bound",
    "upper_bound",
    "forecast_confidence_score",
    "forecast_confidence_class",
    "forecast_risk_level",
    "confidence_reason",
]


def add_forecast_confidence(
    forecast_results: pd.DataFrame,
    demand_features: pd.DataFrame,
) -> pd.DataFrame:
    """Add prediction intervals, confidence scores, and risk classes."""
    if forecast_results.empty:
        return _empty_confidence_frame(forecast_results)

    enriched = forecast_results.copy()
    enriched = _add_prediction_intervals(enriched)
    enriched = _add_feature_context(enriched, demand_features)
    enriched = _add_confidence_scores(enriched)
    return enriched[forecast_results.columns.tolist() + CONFIDENCE_COLUMNS]


def _add_prediction_intervals(forecast_results: pd.DataFrame) -> pd.DataFrame:
    """Create p10/p50/p90 intervals from SKU/model residual distributions."""
    enriched = forecast_results.copy()
    enriched["residual"] = enriched["actual_demand"] - enriched["forecast_quantity"]
    enriched["p50"] = enriched["forecast_quantity"]

    interval_frames = []
    for _, group in enriched.groupby(["sku_id", "model_name"], sort=False):
        residual_q10 = group["residual"].quantile(0.10)
        residual_q90 = group["residual"].quantile(0.90)
        group = group.copy()
        group["p10"] = (group["forecast_quantity"] + residual_q10).clip(lower=0)
        group["p90"] = (group["forecast_quantity"] + residual_q90).clip(lower=0)
        group["p10"] = group[["p10", "p50"]].min(axis=1)
        group["p90"] = group[["p90", "p50"]].max(axis=1)
        group["lower_bound"] = group["p10"]
        group["upper_bound"] = group["p90"]
        interval_frames.append(group)

    return pd.concat(interval_frames, ignore_index=True).drop(columns=["residual"])


def _add_feature_context(forecast_results: pd.DataFrame, demand_features: pd.DataFrame) -> pd.DataFrame:
    """Join demand variability, anomaly, and event context onto forecasts."""
    context_columns = [
        "sku_id",
        "date",
        "coefficient_of_variation",
        "zero_demand_ratio",
        "anomaly_count_30",
        "has_event",
        "event_count",
    ]
    context = demand_features[context_columns].copy()
    context["target_date"] = pd.to_datetime(context["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    context = context.drop(columns=["date"])

    enriched = forecast_results.copy()
    enriched["target_date"] = pd.to_datetime(enriched["target_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return enriched.merge(context, on=["sku_id", "target_date"], how="left")


def _add_confidence_scores(forecast_results: pd.DataFrame) -> pd.DataFrame:
    """Calculate interpretable row-level confidence and risk values."""
    enriched = forecast_results.copy()
    group_wape = _model_wape(enriched)
    enriched = enriched.merge(group_wape, on=["sku_id", "model_name"], how="left")

    interval_width = enriched["upper_bound"] - enriched["lower_bound"]
    interval_width_ratio = interval_width / (enriched["p50"].abs() + 1)
    anomaly_frequency = pd.to_numeric(enriched["anomaly_count_30"], errors="coerce").fillna(0) / 30

    penalties = (
        0.35 * enriched["model_wape"].clip(lower=0, upper=1)
        + 0.20 * (pd.to_numeric(enriched["coefficient_of_variation"], errors="coerce").fillna(0) / 2).clip(0, 1)
        + 0.15 * pd.to_numeric(enriched["zero_demand_ratio"], errors="coerce").fillna(0).clip(0, 1)
        + 0.10 * anomaly_frequency.clip(0, 1)
        + 0.05 * (pd.to_numeric(enriched["has_event"], errors="coerce").fillna(0) > 0).astype(int)
        + 0.15 * interval_width_ratio.clip(0, 1)
    )

    enriched["forecast_confidence_score"] = (1 - penalties).clip(lower=0, upper=1)
    enriched["forecast_confidence_class"] = enriched["forecast_confidence_score"].apply(_confidence_class)
    enriched["forecast_risk_level"] = enriched.apply(_risk_level, axis=1)
    enriched["confidence_reason"] = enriched.apply(_confidence_reason, axis=1)
    enriched = enriched.drop(columns=["model_wape", "coefficient_of_variation", "zero_demand_ratio", "anomaly_count_30", "has_event", "event_count"])
    return enriched


def _model_wape(forecast_results: pd.DataFrame) -> pd.DataFrame:
    """Return SKU/model WAPE from available forecast residuals."""
    rows = []
    for (sku_id, model_name), group in forecast_results.groupby(["sku_id", "model_name"], sort=False):
        denominator = group["actual_demand"].abs().sum()
        if denominator == 0:
            wape = 0.0 if group["absolute_error"].sum() == 0 else 1.0
        else:
            wape = float(group["absolute_error"].sum() / denominator)
        rows.append({"sku_id": sku_id, "model_name": model_name, "model_wape": wape})
    return pd.DataFrame(rows)


def _confidence_class(score: float) -> str:
    """Map confidence score to a readable class."""
    if score >= 0.75:
        return "HIGH"
    if score >= 0.45:
        return "MEDIUM"
    return "LOW"


def _risk_level(row: pd.Series) -> str:
    """Classify forecast risk from confidence, interval width, and demand stability."""
    interval_width_ratio = (row["upper_bound"] - row["lower_bound"]) / (abs(row["p50"]) + 1)
    high_variability = row.get("forecast_confidence_score", 0) < 0.45 or interval_width_ratio >= 0.75
    medium_variability = row.get("forecast_confidence_score", 0) < 0.75 or interval_width_ratio >= 0.35

    if high_variability:
        return "HIGH_RISK"
    if medium_variability:
        return "MEDIUM_RISK"
    return "LOW_RISK"


def _confidence_reason(row: pd.Series) -> str:
    """Return an interpretable reason for the confidence class."""
    interval_width_ratio = (row["upper_bound"] - row["lower_bound"]) / (abs(row["p50"]) + 1)
    confidence_class = row["forecast_confidence_class"]

    if confidence_class == "HIGH":
        return "Low recent forecast error and stable demand"
    if interval_width_ratio >= 0.75:
        return "Wide uncertainty interval and elevated forecast risk"
    if row["forecast_risk_level"] == "HIGH_RISK":
        return "High intermittency or recent forecast error"
    return "Moderate uncertainty from variability, events, or recent errors"


def _empty_confidence_frame(forecast_results: pd.DataFrame) -> pd.DataFrame:
    """Return an empty forecast dataframe with confidence columns."""
    empty = forecast_results.copy()
    for column in CONFIDENCE_COLUMNS:
        empty[column] = []
    return empty
