"""True future forecast generation for downstream planning horizons."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from config import FUTURE_FORECAST_CONFIG


ML_OR_COMPLEX_MODELS = {"linear_regression", "random_forest", "knn_regressor", "knn", "gradient_boosting"}

FUTURE_FORECAST_COLUMNS = [
    "sku_id",
    "forecast_date",
    "horizon_day",
    "champion_model",
    "forecast_quantity",
    "p10",
    "p50",
    "p90",
    "forecast_generation_method",
    "interval_generation_method",
    "future_forecast_warning_codes",
    "event_flag",
    "event_name",
    "event_uplift_factor",
    "day_of_week",
    "month",
    "week_of_year",
]


def build_future_forecasts(
    demand_history_df: pd.DataFrame,
    demand_features_df: pd.DataFrame,
    model_registry_df: pd.DataFrame,
    model_performance_df: pd.DataFrame,
    forecast_results_df: pd.DataFrame,
    events_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Generate one future forecast row per SKU per future date."""
    del demand_features_df, model_performance_df  # Reserved for future persisted-model support.
    demand = _prepare_demand(demand_history_df)
    registry = _prepare_registry(model_registry_df)
    backtests = _prepare_backtests(forecast_results_df)
    events = _prepare_events(events_df)
    rows: list[dict[str, Any]] = []

    for sku_id, sku_demand in demand.groupby("sku_id", sort=True):
        ordered = sku_demand.sort_values("date").copy()
        latest_date = ordered["date"].max()
        if pd.isna(latest_date):
            continue
        registry_row = registry.get(sku_id, {})
        champion_model = str(registry_row.get("champion_model") or FUTURE_FORECAST_CONFIG["fallback_model"])
        persisted = _load_persisted_model(registry_row)
        residual_quantiles = _residual_quantiles(sku_id, champion_model, backtests)
        interval_method = (
            "BACKTEST_RESIDUAL_QUANTILES"
            if residual_quantiles["available"]
            else "HISTORICAL_DEMAND_STD_FALLBACK"
        )

        history_values = ordered["quantity_demanded"].astype(float).clip(lower=0).tolist()
        forecast_history = history_values.copy()
        for horizon_day in range(1, FUTURE_FORECAST_CONFIG["future_horizon_days"] + 1):
            forecast_date = latest_date + pd.Timedelta(days=horizon_day)
            warnings: list[str] = []
            event_context = _event_context(sku_id, forecast_date, events, warnings)
            base_forecast, generation_method = _forecast_for_day(
                champion_model,
                forecast_history,
                horizon_day,
                warnings,
                persisted,
                forecast_date,
                event_context,
                ordered,
            )
            forecast_quantity = base_forecast * event_context["event_uplift_factor"]
            if forecast_quantity < 0 and FUTURE_FORECAST_CONFIG["clip_negative_forecasts"]:
                forecast_quantity = 0
                warnings.append("NEGATIVE_FUTURE_FORECAST_CLIPPED")
            p10, p50, p90 = _future_interval(forecast_quantity, residual_quantiles, ordered, warnings)
            forecast_history.append(forecast_quantity)
            rows.append(
                {
                    "sku_id": sku_id,
                    "forecast_date": forecast_date.strftime("%Y-%m-%d"),
                    "horizon_day": horizon_day,
                    "champion_model": champion_model,
                    "forecast_quantity": round(float(forecast_quantity), 4),
                    "p10": round(float(p10), 4),
                    "p50": round(float(p50), 4),
                    "p90": round(float(p90), 4),
                    "forecast_generation_method": generation_method,
                    "interval_generation_method": interval_method,
                    "future_forecast_warning_codes": _join_codes(warnings),
                    "event_flag": event_context["event_flag"],
                    "event_name": event_context["event_name"],
                    "event_uplift_factor": event_context["event_uplift_factor"],
                    "day_of_week": int(forecast_date.dayofweek),
                    "month": int(forecast_date.month),
                    "week_of_year": int(forecast_date.isocalendar().week),
                }
            )

    return pd.DataFrame(rows, columns=FUTURE_FORECAST_COLUMNS)


def future_forecast_warning_counts(future_forecasts: pd.DataFrame) -> dict[str, int]:
    """Return warning-code counts from future forecast rows."""
    counter: Counter[str] = Counter()
    if future_forecasts.empty or "future_forecast_warning_codes" not in future_forecasts.columns:
        return {}
    for value in future_forecasts["future_forecast_warning_codes"].fillna(""):
        for code in str(value).split(";"):
            code = code.strip()
            if code:
                counter[code] += 1
    return dict(sorted(counter.items()))


def _prepare_demand(demand: pd.DataFrame) -> pd.DataFrame:
    prepared = demand.copy()
    prepared["sku_id"] = prepared["sku_id"].astype(str).str.strip()
    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce")
    prepared["quantity_demanded"] = pd.to_numeric(prepared["quantity_demanded"], errors="coerce").fillna(0)
    if FUTURE_FORECAST_CONFIG["clip_negative_forecasts"]:
        prepared["quantity_demanded"] = prepared["quantity_demanded"].clip(lower=0)
    return prepared.dropna(subset=["sku_id", "date"]).sort_values(["sku_id", "date"])


def _prepare_registry(registry: pd.DataFrame) -> dict[str, str]:
    if registry is None or registry.empty or "sku_id" not in registry.columns or "champion_model" not in registry.columns:
        return {}
    return {str(row["sku_id"]).strip(): row for row in registry.to_dict("records")}


def _prepare_backtests(forecasts: pd.DataFrame) -> pd.DataFrame:
    if forecasts is None or forecasts.empty:
        return pd.DataFrame()
    prepared = forecasts.copy()
    prepared["sku_id"] = prepared["sku_id"].astype(str).str.strip()
    for column in ["actual_demand", "forecast_quantity", "error"]:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    return prepared


def _prepare_events(events: pd.DataFrame | None) -> pd.DataFrame:
    if events is None or events.empty:
        return pd.DataFrame()
    prepared = events.copy()
    prepared["event_start_date"] = pd.to_datetime(prepared["event_start_date"], errors="coerce")
    prepared["event_end_date"] = pd.to_datetime(prepared["event_end_date"], errors="coerce")
    if "sku_id" not in prepared.columns:
        prepared["sku_id"] = ""
    if "event_name" not in prepared.columns:
        prepared["event_name"] = ""
    if "event_intensity" not in prepared.columns:
        prepared["event_intensity"] = 0
    prepared["sku_id"] = prepared["sku_id"].fillna("").astype(str).str.strip()
    prepared["event_name"] = prepared["event_name"].fillna("").astype(str).str.strip()
    prepared["event_intensity"] = pd.to_numeric(prepared["event_intensity"], errors="coerce").fillna(0)
    return prepared.dropna(subset=["event_start_date", "event_end_date"])


def _forecast_for_day(
    champion_model: str,
    forecast_history: list[float],
    horizon_day: int,
    warnings: list[str],
    persisted: dict[str, Any] | None = None,
    forecast_date: pd.Timestamp | None = None,
    event_context: dict[str, Any] | None = None,
    sku_demand: pd.DataFrame | None = None,
) -> tuple[float, str]:
    model = str(champion_model).strip()
    if len(forecast_history) < FUTURE_FORECAST_CONFIG["min_training_days"]:
        warnings.append("INSUFFICIENT_HISTORY_FOR_FUTURE_FORECAST")
    if persisted and forecast_date is not None and sku_demand is not None:
        predicted = _predict_with_persisted_model(persisted, forecast_history, forecast_date, event_context or {}, sku_demand, warnings)
        if predicted is not None:
            return predicted, "PERSISTED_CHAMPION_MODEL"
    if model == "naive":
        return _last_value(forecast_history), "NAIVE_CHAMPION"
    if model in {"seasonal_naive_7", "seasonal_naive_lag_7"}:
        return _seasonal_naive_7(forecast_history, horizon_day), "SEASONAL_NAIVE_7_CHAMPION"
    if model == "moving_average_7":
        return _moving_average(forecast_history, 7), "MOVING_AVERAGE_7_CHAMPION"
    if model == "moving_average_14":
        return _moving_average(forecast_history, 14), "MOVING_AVERAGE_14_CHAMPION"
    if model == "moving_average_30":
        return _moving_average(forecast_history, 30), "MOVING_AVERAGE_30_CHAMPION"
    if model in ML_OR_COMPLEX_MODELS:
        warnings.append("CHAMPION_MODEL_NOT_REUSABLE_FOR_FUTURE")
        warnings.append("FUTURE_MODEL_FALLBACK_USED")
        return _fallback_forecast(forecast_history, horizon_day), "FALLBACK_SEASONAL_NAIVE_7_FOR_NONPERSISTED_CHAMPION"
    warnings.append("FUTURE_MODEL_FALLBACK_USED")
    return _fallback_forecast(forecast_history, horizon_day), "FALLBACK_SEASONAL_NAIVE_7"


def _load_persisted_model(registry_row: dict[str, Any]) -> dict[str, Any] | None:
    reusable = _bool(registry_row.get("future_forecast_reusable_flag"))
    artifact_path = Path(str(registry_row.get("model_artifact_path") or ""))
    metadata_path = Path(str(registry_row.get("model_metadata_path") or ""))
    if not reusable or not artifact_path.exists() or not metadata_path.exists():
        return None
    try:
        artifact = joblib.load(artifact_path)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return {"artifact": artifact, "metadata": metadata}


def _predict_with_persisted_model(
    persisted: dict[str, Any],
    forecast_history: list[float],
    forecast_date: pd.Timestamp,
    event_context: dict[str, Any],
    sku_demand: pd.DataFrame,
    warnings: list[str],
) -> float | None:
    metadata = persisted["metadata"]
    feature_columns = metadata.get("feature_columns", [])
    if not feature_columns:
        warnings.append("FUTURE_FEATURES_INCOMPLETE_MODEL_FALLBACK")
        return None
    feature_values = _future_feature_values(forecast_history, forecast_date, event_context, sku_demand)
    missing = [column for column in feature_columns if column not in feature_values]
    if missing:
        warnings.append("FUTURE_FEATURES_INCOMPLETE_MODEL_FALLBACK")
        return None
    if _uses_recursive_features(feature_columns):
        warnings.append("RECURSIVE_FUTURE_FEATURES_USED")
    features = pd.DataFrame([{column: feature_values[column] for column in feature_columns}])
    artifact = persisted["artifact"]
    try:
        if isinstance(artifact, dict) and artifact.get("model_type") == "linear_regression":
            coefficients = artifact["coefficients"]
            values = [1.0] + [float(features.iloc[0][column]) for column in feature_columns]
            prediction = sum(coef * value for coef, value in zip(coefficients, values))
        else:
            prediction = float(artifact.predict(features)[0])
    except Exception:
        warnings.append("FUTURE_FEATURES_INCOMPLETE_MODEL_FALLBACK")
        return None
    return max(float(prediction), 0)


def _future_feature_values(
    forecast_history: list[float],
    forecast_date: pd.Timestamp,
    event_context: dict[str, Any],
    sku_demand: pd.DataFrame,
) -> dict[str, float]:
    series = pd.Series(forecast_history, dtype=float)
    nonzero = series.gt(0)
    recent_7 = series.tail(7)
    recent_30 = series.tail(30)
    values: dict[str, float] = {
        "day_of_week": float(forecast_date.dayofweek),
        "week_of_year": float(forecast_date.isocalendar().week),
        "month": float(forecast_date.month),
        "quarter": float(forecast_date.quarter),
        "weekend_flag": float(forecast_date.dayofweek >= 5),
        "month_start_flag": float(forecast_date.is_month_start),
        "month_end_flag": float(forecast_date.is_month_end),
        "event_count": float(1 if event_context.get("event_flag") else 0),
        "has_event": float(1 if event_context.get("event_flag") else 0),
        "before_event_flag": 0.0,
        "during_event_flag": float(1 if event_context.get("event_flag") else 0),
        "after_event_flag": 0.0,
        "promotion_flag": 0.0,
        "holiday_flag": 0.0,
        "stockout_flag": 0.0,
        "breakdown_flag": 0.0,
        "marketing_flag": 0.0,
        "recent_event_count_7": float(1 if event_context.get("event_flag") else 0),
        "recent_event_count_30": float(1 if event_context.get("event_flag") else 0),
        "anomaly_recent_flag": 0.0,
        "anomaly_count_30": 0.0,
        "coefficient_of_variation": _safe_ratio(float(series.std()), float(series.mean())),
        "zero_demand_ratio": float((~nonzero).mean()) if len(series) else 0.0,
        "event_affected_ratio": 0.0,
        "sales_value": 0.0,
        "is_invalid_quantity": 0.0,
    }
    for lag in [1, 3, 7, 14, 30]:
        values[f"lag_{lag}"] = _lag(series, lag)
    values["rolling_mean_7"] = float(recent_7.mean()) if len(recent_7) else 0.0
    values["rolling_std_7"] = float(recent_7.std()) if len(recent_7) > 1 else 0.0
    values["rolling_mean_14"] = float(series.tail(14).mean()) if len(series) else 0.0
    values["rolling_std_14"] = float(series.tail(14).std()) if len(series.tail(14)) > 1 else 0.0
    values["rolling_mean_30"] = float(recent_30.mean()) if len(recent_30) else 0.0
    values["rolling_std_30"] = float(recent_30.std()) if len(recent_30) > 1 else 0.0
    values["rolling_min_30"] = float(recent_30.min()) if len(recent_30) else 0.0
    values["rolling_max_30"] = float(recent_30.max()) if len(recent_30) else 0.0
    values["demand_change_1"] = values["lag_1"] - values["lag_3"]
    values["demand_change_7"] = values["lag_1"] - values["lag_7"]
    values["rolling_trend_7"] = values["rolling_mean_7"] - values["rolling_mean_14"]
    values["rolling_trend_30"] = values["rolling_mean_7"] - values["rolling_mean_30"]
    values["momentum_7"] = values["demand_change_7"]
    values["momentum_30"] = values["lag_1"] - values["rolling_mean_30"]
    if not sku_demand.empty and "sales_value" in sku_demand.columns:
        values["sales_value"] = float(pd.to_numeric(sku_demand["sales_value"], errors="coerce").fillna(0).tail(30).mean())
    return {key: (0.0 if pd.isna(value) else float(value)) for key, value in values.items()}


def _uses_recursive_features(feature_columns: list[str]) -> bool:
    recursive_prefixes = ("lag_", "rolling_", "demand_change_", "momentum_")
    return any(column.startswith(recursive_prefixes) for column in feature_columns)


def _lag(series: pd.Series, lag: int) -> float:
    if len(series) >= lag:
        return float(series.iloc[-lag])
    if len(series):
        return float(series.iloc[-1])
    return 0.0


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0 or pd.isna(denominator):
        return 0.0
    return float(numerator / denominator) if not pd.isna(numerator) else 0.0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _last_value(values: list[float]) -> float:
    return max(float(values[-1]), 0) if values else 0.0


def _moving_average(values: list[float], window: int) -> float:
    if not values:
        return 0.0
    return max(float(pd.Series(values[-window:]).mean()), 0)


def _seasonal_naive_7(values: list[float], horizon_day: int) -> float:
    del horizon_day
    if len(values) >= 7:
        return max(float(values[-7]), 0)
    return _moving_average(values, min(len(values), 7))


def _fallback_forecast(values: list[float], horizon_day: int) -> float:
    if len(values) >= 7:
        return _seasonal_naive_7(values, horizon_day)
    return _moving_average(values, min(len(values), 14))


def _residual_quantiles(sku_id: str, champion_model: str, backtests: pd.DataFrame) -> dict[str, float | bool]:
    if backtests.empty or "model_name" not in backtests.columns:
        return {"available": False, "q10": 0.0, "q90": 0.0}
    rows = backtests[
        (backtests["sku_id"] == sku_id)
        & (backtests["model_name"].astype(str) == str(champion_model))
    ].copy()
    if rows.empty or "actual_demand" not in rows.columns or "forecast_quantity" not in rows.columns:
        return {"available": False, "q10": 0.0, "q90": 0.0}
    residuals = rows["actual_demand"] - rows["forecast_quantity"]
    residuals = residuals.dropna()
    if residuals.empty:
        return {"available": False, "q10": 0.0, "q90": 0.0}
    return {
        "available": True,
        "q10": float(residuals.quantile(FUTURE_FORECAST_CONFIG["p10_quantile"])),
        "q90": float(residuals.quantile(FUTURE_FORECAST_CONFIG["p90_quantile"])),
    }


def _future_interval(
    forecast_quantity: float,
    residual_quantiles: dict[str, float | bool],
    sku_demand: pd.DataFrame,
    warnings: list[str],
) -> tuple[float, float, float]:
    p50 = max(float(forecast_quantity), 0)
    if residual_quantiles.get("available"):
        p10 = max(p50 + float(residual_quantiles["q10"]), 0)
        p90 = max(p50 + float(residual_quantiles["q90"]), p50)
    else:
        std = pd.to_numeric(sku_demand["quantity_demanded"], errors="coerce").fillna(0).std()
        width = float(std if pd.notna(std) else 0) * FUTURE_FORECAST_CONFIG["default_interval_width_multiplier"]
        p10 = max(p50 - width, 0)
        p90 = max(p50 + width, p50)
        warnings.append("FUTURE_INTERVAL_APPROXIMATED")
    p10 = min(p10, p50)
    p90 = max(p90, p50)
    return p10, p50, p90


def _event_context(sku_id: str, forecast_date: pd.Timestamp, events: pd.DataFrame, warnings: list[str]) -> dict[str, Any]:
    if events.empty:
        return {"event_flag": False, "event_name": "", "event_uplift_factor": 1.0}
    event_sku = events["sku_id"].fillna("").astype(str)
    applies = event_sku.isin(["", sku_id])
    active = events[
        applies
        & (events["event_start_date"] <= forecast_date)
        & (events["event_end_date"] >= forecast_date)
    ]
    if active.empty:
        return {"event_flag": False, "event_name": "", "event_uplift_factor": 1.0}
    event_names = "; ".join(active["event_name"].dropna().astype(str).unique().tolist())
    intensity = float(pd.to_numeric(active["event_intensity"], errors="coerce").fillna(0).max())
    if intensity <= 0:
        warnings.append("FUTURE_EVENT_UPLIFT_UNKNOWN")
        uplift = 1.0
    else:
        uplift = 1.0 + intensity
    return {"event_flag": True, "event_name": event_names, "event_uplift_factor": round(uplift, 4)}


def _join_codes(codes: list[str]) -> str:
    seen: list[str] = []
    for code in codes:
        if code and code not in seen:
            seen.append(code)
    return ";".join(seen)
