"""Downstream demand planning context for Phase 2 and Phase 3."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

import pandas as pd

from config import DEMAND_PLANNING_CONTEXT_CONFIG


REQUIRED_OUTPUT_COLUMNS = [
    "sku_id",
    "product_name",
    "category",
    "demand_profile",
    "demand_cv",
    "demand_std_daily",
    "average_daily_demand_observed",
    "median_daily_demand_observed",
    "max_daily_demand_observed",
    "zero_demand_day_ratio",
    "intermittency_ratio",
    "average_demand_interval",
    "demand_spikiness_score",
    "demand_variability_class",
    "champion_model",
    "model_confidence_score",
    "forecast_confidence_band",
    "forecast_bias",
    "bias_direction",
    "bias_severity",
    "underforecast_risk_flag",
    "overforecast_risk_flag",
    "forecast_demand_7d",
    "forecast_demand_14d",
    "forecast_demand_30d",
    "forecast_demand_60d",
    "forecast_demand_90d",
    "average_daily_forecast_demand_7d",
    "average_daily_forecast_demand_14d",
    "average_daily_forecast_demand_30d",
    "average_daily_forecast_demand_60d",
    "average_daily_forecast_demand_90d",
    "forecast_p10_30d",
    "forecast_p50_30d",
    "forecast_p90_30d",
    "forecast_uncertainty_width_30d",
    "forecast_uncertainty_ratio_30d",
    "forecast_uncertainty_level",
    "high_uncertainty_flag",
    "seasonality_flag",
    "seasonality_strength",
    "seasonal_phase",
    "seasonal_index",
    "upcoming_event_flag",
    "upcoming_event_count",
    "next_event_name",
    "next_event_start_date",
    "event_uplift_factor",
    "event_risk_window_flag",
    "stockout_censored_demand_flag",
    "suspected_stockout_days_30d",
    "suspected_stockout_windows_30d",
    "lost_sales_estimate_30d",
    "adjusted_demand_30d",
    "stockout_censor_method",
    "stockout_censor_confidence",
    "demand_urgency_score",
    "demand_pressure_7d",
    "demand_pressure_30d",
    "demand_data_quality_score",
    "demand_planning_warning_codes",
    "downstream_planning_notes",
]


def build_demand_planning_context(
    products_df: pd.DataFrame,
    demand_history_df: pd.DataFrame,
    events_df: pd.DataFrame | None,
    forecast_results_df: pd.DataFrame,
    demand_profiles_df: pd.DataFrame | None,
    champion_registry_df: pd.DataFrame | None,
    model_performance_df: pd.DataFrame | None,
    future_forecast_results_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build one downstream demand planning context row per SKU."""
    products = _prepare_products(products_df)
    demand = _prepare_demand(demand_history_df)
    events = _prepare_events(events_df)
    forecasts = _prepare_forecasts(forecast_results_df)
    future_forecasts = _prepare_future_forecasts(future_forecast_results_df)
    profiles = _index_by_sku(demand_profiles_df)
    champions = _index_by_sku(champion_registry_df)
    performance = model_performance_df.copy() if model_performance_df is not None else pd.DataFrame()

    rows = []
    for product in products.to_dict("records"):
        sku_id = str(product["sku_id"])
        sku_demand = demand[demand["sku_id"] == sku_id].sort_values("date")
        sku_forecasts = forecasts[forecasts["sku_id"] == sku_id].sort_values("target_date")
        sku_future_forecasts = future_forecasts[future_forecasts["sku_id"] == sku_id].sort_values("horizon_day")
        profile = profiles.get(sku_id, {})
        champion = champions.get(sku_id, {})
        sku_performance = performance[performance["sku_id"].astype(str) == sku_id] if not performance.empty and "sku_id" in performance.columns else pd.DataFrame()
        warnings: list[str] = []

        demand_metrics = _demand_metrics(sku_demand, profile, warnings)
        model_metrics = _model_metrics(champion, sku_performance, sku_forecasts, demand_metrics, warnings)
        forecast_metrics = _forecast_horizon_metrics(sku_forecasts, sku_future_forecasts, model_metrics, demand_metrics, warnings)
        uncertainty_metrics = _uncertainty_metrics(sku_forecasts, sku_future_forecasts, forecast_metrics, demand_metrics, warnings)
        seasonal_metrics = _seasonality_metrics(sku_demand, warnings)
        event_metrics = _event_metrics(sku_id, sku_demand, events, warnings)
        censor_metrics = _stockout_censor_metrics(sku_demand, demand_metrics, warnings)
        planning_metrics = _planning_metrics(
            demand_metrics,
            model_metrics,
            forecast_metrics,
            uncertainty_metrics,
            event_metrics,
            censor_metrics,
            warnings,
        )

        row = {
            "sku_id": sku_id,
            "product_name": product.get("product_name", ""),
            "category": product.get("category", ""),
            **demand_metrics,
            **model_metrics,
            **forecast_metrics,
            **uncertainty_metrics,
            **seasonal_metrics,
            **event_metrics,
            **censor_metrics,
            **planning_metrics,
        }
        row["demand_planning_warning_codes"] = _join_codes(warnings)
        row["downstream_planning_notes"] = _planning_note(row)
        rows.append(row)

    return pd.DataFrame(rows, columns=REQUIRED_OUTPUT_COLUMNS)


def demand_planning_warning_counts(context_df: pd.DataFrame) -> dict[str, int]:
    """Return warning-code counts from a generated planning context dataframe."""
    counter: Counter[str] = Counter()
    if context_df.empty or "demand_planning_warning_codes" not in context_df.columns:
        return {}
    for value in context_df["demand_planning_warning_codes"].fillna(""):
        for code in str(value).split(";"):
            code = code.strip()
            if code:
                counter[code] += 1
    return dict(sorted(counter.items()))


def _prepare_products(products: pd.DataFrame) -> pd.DataFrame:
    prepared = products.copy()
    prepared["sku_id"] = prepared["sku_id"].astype(str).str.strip()
    if "sku_name" in prepared.columns:
        prepared["product_name"] = prepared["sku_name"]
    elif "product_name" not in prepared.columns:
        prepared["product_name"] = prepared["sku_id"]
    if "category" not in prepared.columns:
        prepared["category"] = ""
    return prepared[["sku_id", "product_name", "category"]].drop_duplicates("sku_id")


def _prepare_demand(demand: pd.DataFrame) -> pd.DataFrame:
    prepared = demand.copy()
    prepared["sku_id"] = prepared["sku_id"].astype(str).str.strip()
    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce")
    prepared["quantity_demanded"] = pd.to_numeric(prepared["quantity_demanded"], errors="coerce").fillna(0).clip(lower=0)
    return prepared.dropna(subset=["date", "sku_id"]).sort_values(["sku_id", "date"])


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
    return prepared.dropna(subset=["event_start_date"])


def _prepare_forecasts(forecasts: pd.DataFrame) -> pd.DataFrame:
    prepared = forecasts.copy()
    if prepared.empty:
        return prepared
    prepared["sku_id"] = prepared["sku_id"].astype(str).str.strip()
    prepared["target_date"] = pd.to_datetime(prepared["target_date"], errors="coerce")
    for column in ["forecast_quantity", "p10", "p50", "p90", "forecast_confidence_score", "error"]:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    return prepared.dropna(subset=["sku_id"])


def _prepare_future_forecasts(future_forecasts: pd.DataFrame | None) -> pd.DataFrame:
    if future_forecasts is None or future_forecasts.empty:
        return pd.DataFrame(columns=["sku_id", "horizon_day", "forecast_quantity", "p10", "p50", "p90"])
    prepared = future_forecasts.copy()
    prepared["sku_id"] = prepared["sku_id"].astype(str).str.strip()
    prepared["horizon_day"] = pd.to_numeric(prepared["horizon_day"], errors="coerce")
    for column in ["forecast_quantity", "p10", "p50", "p90"]:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce").fillna(0).clip(lower=0)
    return prepared.dropna(subset=["sku_id", "horizon_day"])


def _index_by_sku(df: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
    if df is None or df.empty or "sku_id" not in df.columns:
        return {}
    indexed = {}
    for row in df.to_dict("records"):
        indexed[str(row["sku_id"])] = row
    return indexed


def _demand_metrics(sku_demand: pd.DataFrame, profile: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    demand = sku_demand["quantity_demanded"] if not sku_demand.empty else pd.Series(dtype=float)
    history_days = len(demand)
    if history_days < DEMAND_PLANNING_CONTEXT_CONFIG["minimum_history_days_for_context"]:
        warnings.append("INSUFFICIENT_HISTORY_FOR_CONTEXT")

    mean = _num(profile.get("average_daily_demand"), demand.mean() if not demand.empty else 0)
    median = _num(profile.get("median_daily_demand"), demand.median() if not demand.empty else 0)
    std = _num(profile.get("std_demand"), demand.std() if not demand.empty else 0)
    max_demand = _num(profile.get("max_demand"), demand.max() if not demand.empty else 0)
    zero_ratio = _num(profile.get("zero_demand_ratio"), float((demand == 0).mean()) if history_days else 0)
    cv = _num(profile.get("coefficient_of_variation"), std / mean if mean else 0)
    if mean <= 0:
        warnings.append("ZERO_MEAN_DEMAND_CV_SAFE_FALLBACK")

    nonzero_dates = sku_demand.loc[sku_demand["quantity_demanded"] > 0, "date"].sort_values()
    if len(nonzero_dates) >= 2:
        avg_interval = float(nonzero_dates.diff().dt.days.dropna().mean())
    else:
        avg_interval = float(history_days or 0)
        warnings.append("INSUFFICIENT_NONZERO_DEMAND_FOR_INTERVAL")

    spikiness = max_demand / mean if mean > 0 else 0
    variability = _variability_class(cv, zero_ratio, spikiness, history_days)
    demand_profile = str(profile.get("demand_behavior_class") or variability).upper()

    return {
        "demand_profile": demand_profile,
        "demand_cv": round(cv, 4),
        "demand_std_daily": round(std, 4),
        "average_daily_demand_observed": round(mean, 4),
        "median_daily_demand_observed": round(median, 4),
        "max_daily_demand_observed": round(max_demand, 4),
        "zero_demand_day_ratio": round(zero_ratio, 4),
        "intermittency_ratio": round(zero_ratio, 4),
        "average_demand_interval": round(avg_interval, 4),
        "demand_spikiness_score": round(spikiness, 4),
        "demand_variability_class": variability,
        "_history_days": history_days,
    }


def _variability_class(cv: float, zero_ratio: float, spikiness: float, history_days: int) -> str:
    if history_days < DEMAND_PLANNING_CONTEXT_CONFIG["minimum_history_days_for_context"]:
        return "UNKNOWN"
    if cv < 0.50 and zero_ratio < 0.20:
        return "STABLE"
    if cv >= 0.50 and zero_ratio < 0.40:
        return "VARIABLE"
    if zero_ratio >= 0.40 and spikiness < 5:
        return "INTERMITTENT"
    if zero_ratio >= 0.40 and spikiness >= 5:
        return "ERRATIC"
    return "UNKNOWN"


def _model_metrics(
    champion: dict[str, Any],
    sku_performance: pd.DataFrame,
    sku_forecasts: pd.DataFrame,
    demand_metrics: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    champion_model = str(champion.get("champion_model") or "UNKNOWN")
    confidence = _num(champion.get("champion_confidence_score"), math.nan)
    if math.isnan(confidence):
        confidence = _derived_confidence(sku_performance, sku_forecasts, demand_metrics)
        warnings.append("MODEL_CONFIDENCE_DERIVED")
    confidence = min(max(confidence, 0), 1)

    bias = _num(champion.get("champion_bias"), math.nan)
    if math.isnan(bias):
        bias = _estimate_bias_from_forecasts(sku_forecasts)
        if math.isnan(bias):
            warnings.append("FORECAST_BIAS_UNAVAILABLE")

    direction = _bias_direction(bias)
    severity = _bias_severity(bias)
    return {
        "champion_model": champion_model,
        "model_confidence_score": round(confidence, 4),
        "forecast_confidence_band": _confidence_band(confidence),
        "forecast_bias": round(bias, 4) if not math.isnan(bias) else pd.NA,
        "bias_direction": direction,
        "bias_severity": severity,
        "underforecast_risk_flag": direction == "UNDERFORECAST",
        "overforecast_risk_flag": direction == "OVERFORECAST",
    }


def _forecast_horizon_metrics(
    sku_forecasts: pd.DataFrame,
    sku_future_forecasts: pd.DataFrame,
    model_metrics: dict[str, Any],
    demand_metrics: dict[str, Any],
    warnings: list[str],
) -> dict[str, float]:
    horizons = DEMAND_PLANNING_CONTEXT_CONFIG["forecast_horizons_days"]
    if _future_forecasts_complete(sku_future_forecasts, max(horizons)):
        output = {}
        for horizon in horizons:
            horizon_rows = sku_future_forecasts[sku_future_forecasts["horizon_day"] <= horizon]
            total = float(horizon_rows["forecast_quantity"].clip(lower=0).sum())
            output[f"forecast_demand_{horizon}d"] = round(total, 4)
            output[f"average_daily_forecast_demand_{horizon}d"] = round(total / horizon if horizon else 0, 4)
        warnings.append("FORECAST_HORIZON_FROM_TRUE_FUTURE_FORECAST")
        return output

    warnings.append("FUTURE_FORECAST_INCOMPLETE_FOR_CONTEXT")
    champion = model_metrics["champion_model"]
    rows = sku_forecasts.copy()
    if not rows.empty and champion != "UNKNOWN" and "model_name" in rows.columns:
        champion_rows = rows[rows["model_name"].astype(str) == champion]
        if not champion_rows.empty:
            rows = champion_rows

    if rows.empty or "forecast_quantity" not in rows.columns:
        daily = demand_metrics["average_daily_demand_observed"]
        warnings.append("FORECAST_FIELDS_UNAVAILABLE")
    else:
        values = rows.sort_values("target_date")["forecast_quantity"].clip(lower=0).dropna()
        if len(values) == 0:
            daily = demand_metrics["average_daily_demand_observed"]
            warnings.append("FORECAST_FIELDS_UNAVAILABLE")
        else:
            if (rows["forecast_quantity"].dropna() < 0).any():
                warnings.append("NEGATIVE_FORECAST_CLIPPED")
            daily = float(values.tail(min(30, len(values))).mean())
            warnings.append("FORECAST_HORIZON_APPROXIMATED")

    output = {}
    for horizon in horizons:
        total = max(daily * horizon, 0)
        output[f"forecast_demand_{horizon}d"] = round(total, 4)
        output[f"average_daily_forecast_demand_{horizon}d"] = round(total / horizon if horizon else 0, 4)
    return output


def _uncertainty_metrics(
    sku_forecasts: pd.DataFrame,
    sku_future_forecasts: pd.DataFrame,
    forecast_metrics: dict[str, Any],
    demand_metrics: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    p50 = forecast_metrics["forecast_demand_30d"]
    if _future_forecasts_complete(sku_future_forecasts, 30) and {"p10", "p50", "p90"}.issubset(sku_future_forecasts.columns):
        horizon_rows = sku_future_forecasts[sku_future_forecasts["horizon_day"] <= 30]
        p10 = float(horizon_rows["p10"].clip(lower=0).sum())
        p50 = float(horizon_rows["p50"].clip(lower=0).sum())
        p90 = float(horizon_rows["p90"].clip(lower=0).sum())
        width = max(p90 - p10, 0)
        ratio = width / p50 if p50 > 0 else 0
        level = _uncertainty_level(ratio)
        return {
            "forecast_p10_30d": round(p10, 4),
            "forecast_p50_30d": round(p50, 4),
            "forecast_p90_30d": round(p90, 4),
            "forecast_uncertainty_width_30d": round(width, 4),
            "forecast_uncertainty_ratio_30d": round(ratio, 4),
            "forecast_uncertainty_level": level,
            "high_uncertainty_flag": level == "HIGH",
        }

    if not sku_forecasts.empty and {"p10", "p50", "p90"}.issubset(sku_forecasts.columns):
        tail = sku_forecasts.sort_values("target_date").tail(30)
        p10 = float(tail["p10"].clip(lower=0).fillna(0).sum())
        p50_sum = float(tail["p50"].clip(lower=0).fillna(0).sum())
        p90 = float(tail["p90"].clip(lower=0).fillna(0).sum())
        if p50_sum > 0:
            p50 = p50_sum
        else:
            warnings.append("FORECAST_UNCERTAINTY_APPROXIMATED")
    else:
        spread = demand_metrics["demand_std_daily"] * math.sqrt(30)
        p10 = max(p50 - spread, 0)
        p90 = max(p50 + spread, p50)
        warnings.append("FORECAST_UNCERTAINTY_APPROXIMATED")

    width = max(p90 - p10, 0)
    ratio = width / p50 if p50 > 0 else 0
    level = _uncertainty_level(ratio)
    return {
        "forecast_p10_30d": round(p10, 4),
        "forecast_p50_30d": round(p50, 4),
        "forecast_p90_30d": round(p90, 4),
        "forecast_uncertainty_width_30d": round(width, 4),
        "forecast_uncertainty_ratio_30d": round(ratio, 4),
        "forecast_uncertainty_level": level,
        "high_uncertainty_flag": level == "HIGH",
    }


def _future_forecasts_complete(sku_future_forecasts: pd.DataFrame, max_horizon: int) -> bool:
    if sku_future_forecasts.empty or "horizon_day" not in sku_future_forecasts.columns:
        return False
    required = set(range(1, int(max_horizon) + 1))
    available = set(pd.to_numeric(sku_future_forecasts["horizon_day"], errors="coerce").dropna().astype(int))
    return required.issubset(available)


def _seasonality_metrics(sku_demand: pd.DataFrame, warnings: list[str]) -> dict[str, Any]:
    if sku_demand.empty or sku_demand["date"].nunique() < 90:
        warnings.append("INSUFFICIENT_HISTORY_FOR_SEASONALITY")
        return {
            "seasonality_flag": False,
            "seasonality_strength": 0.0,
            "seasonal_phase": "UNKNOWN",
            "seasonal_index": 1.0,
        }
    monthly = sku_demand.assign(month=sku_demand["date"].dt.month).groupby("month")["quantity_demanded"].mean()
    if len(monthly) < 3 or monthly.mean() <= 0:
        warnings.append("INSUFFICIENT_HISTORY_FOR_SEASONALITY")
        strength = 0.0
    else:
        strength = float(monthly.std() / monthly.mean())
    flag = strength >= DEMAND_PLANNING_CONTEXT_CONFIG["seasonality_min_strength"]
    recent_month = int(sku_demand["date"].max().month)
    seasonal_index = float(monthly.get(recent_month, monthly.mean()) / monthly.mean()) if len(monthly) and monthly.mean() else 1.0
    return {
        "seasonality_flag": bool(flag),
        "seasonality_strength": round(strength, 4),
        "seasonal_phase": _seasonal_phase(seasonal_index, flag),
        "seasonal_index": round(seasonal_index, 4),
    }


def _event_metrics(sku_id: str, sku_demand: pd.DataFrame, events: pd.DataFrame, warnings: list[str]) -> dict[str, Any]:
    if events.empty:
        return _empty_event_metrics()
    anchor = sku_demand["date"].max() if not sku_demand.empty else pd.Timestamp.today().normalize()
    lookahead_end = anchor + pd.Timedelta(days=DEMAND_PLANNING_CONTEXT_CONFIG["event_lookahead_days"])
    event_sku = events["sku_id"].fillna("").astype(str)
    applies = event_sku.isin(["", sku_id])
    upcoming = events[applies & (events["event_start_date"] > anchor) & (events["event_start_date"] <= lookahead_end)].sort_values("event_start_date")
    if upcoming.empty:
        return _empty_event_metrics()
    first = upcoming.iloc[0]
    intensity = _num(first.get("event_intensity"), 0)
    uplift = 1.0 + max(intensity, 0)
    if intensity <= 0:
        warnings.append("EVENT_UPLIFT_UNKNOWN")
    return {
        "upcoming_event_flag": True,
        "upcoming_event_count": int(len(upcoming)),
        "next_event_name": str(first.get("event_name", "")),
        "next_event_start_date": first["event_start_date"].strftime("%Y-%m-%d"),
        "event_uplift_factor": round(uplift, 4),
        "event_risk_window_flag": True,
    }


def _empty_event_metrics() -> dict[str, Any]:
    return {
        "upcoming_event_flag": False,
        "upcoming_event_count": 0,
        "next_event_name": "",
        "next_event_start_date": "",
        "event_uplift_factor": 1.0,
        "event_risk_window_flag": False,
    }


def _stockout_censor_metrics(
    sku_demand: pd.DataFrame,
    demand_metrics: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    if len(sku_demand) < DEMAND_PLANNING_CONTEXT_CONFIG["minimum_history_days_for_context"]:
        warnings.append("INSUFFICIENT_HISTORY_FOR_CENSORING")
        return _empty_censor_metrics("LOW")

    recent = sku_demand.sort_values("date").tail(DEMAND_PLANNING_CONTEXT_CONFIG["stockout_censor_recent_window_days"])
    qty = recent["quantity_demanded"].reset_index(drop=True)
    nonzero = qty[qty > 0]
    threshold = float(nonzero.quantile(DEMAND_PLANNING_CONTEXT_CONFIG["stockout_censor_high_demand_quantile"])) if not nonzero.empty else 0
    expected_daily = float(nonzero.median()) if not nonzero.empty else demand_metrics["average_daily_demand_observed"]
    min_streak = DEMAND_PLANNING_CONTEXT_CONFIG["stockout_censor_zero_window_days"]
    suspected_days = 0
    windows = 0
    high_signal_windows = 0
    index = 0
    while index < len(qty):
        if qty.iloc[index] != 0:
            index += 1
            continue
        start = index
        while index < len(qty) and qty.iloc[index] == 0:
            index += 1
        length = index - start
        previous = qty.iloc[max(0, start - 7):start]
        strong_preceding_demand = bool((previous > max(threshold, demand_metrics["median_daily_demand_observed"])).any())
        if length >= min_streak and strong_preceding_demand:
            suspected_days += length
            windows += 1
            if length >= min_streak + 2 or previous.mean() > threshold:
                high_signal_windows += 1

    observed_30d = float(qty.sum())
    lost_sales = max(expected_daily * suspected_days, 0)
    if windows:
        warnings.append("POSSIBLE_STOCKOUT_CENSORED_DEMAND")
    confidence = "NONE"
    if windows >= 2 or high_signal_windows >= 2:
        confidence = "HIGH"
    elif windows == 1 and high_signal_windows >= 1:
        confidence = "MEDIUM"
    elif windows == 1:
        confidence = "LOW"
        warnings.append("STOCKOUT_CENSOR_LOW_CONFIDENCE")
    return {
        "stockout_censored_demand_flag": windows > 0,
        "suspected_stockout_days_30d": int(suspected_days),
        "suspected_stockout_windows_30d": int(windows),
        "lost_sales_estimate_30d": round(lost_sales, 4),
        "adjusted_demand_30d": round(observed_30d + lost_sales, 4),
        "stockout_censor_method": "PHASE1_ZERO_STREAK_HEURISTIC",
        "stockout_censor_confidence": confidence,
    }


def _empty_censor_metrics(confidence: str = "NONE") -> dict[str, Any]:
    return {
        "stockout_censored_demand_flag": False,
        "suspected_stockout_days_30d": 0,
        "suspected_stockout_windows_30d": 0,
        "lost_sales_estimate_30d": 0.0,
        "adjusted_demand_30d": 0.0,
        "stockout_censor_method": "PHASE1_ZERO_STREAK_HEURISTIC",
        "stockout_censor_confidence": confidence,
    }


def _planning_metrics(
    demand_metrics: dict[str, Any],
    model_metrics: dict[str, Any],
    forecast_metrics: dict[str, Any],
    uncertainty_metrics: dict[str, Any],
    event_metrics: dict[str, Any],
    censor_metrics: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    observed_7d = max(demand_metrics["average_daily_demand_observed"] * 7, 0.0001)
    observed_30d = max(demand_metrics["average_daily_demand_observed"] * 30, 0.0001)
    pressure_7d = forecast_metrics["forecast_demand_7d"] / observed_7d
    pressure_30d = forecast_metrics["forecast_demand_30d"] / observed_30d
    base = min(forecast_metrics["forecast_demand_7d"] / max(observed_7d, 1) * 30, 40)
    score = base
    if censor_metrics["stockout_censored_demand_flag"]:
        score += 20
    if event_metrics["upcoming_event_flag"]:
        score += 15
    if model_metrics["underforecast_risk_flag"]:
        score += 15
    if uncertainty_metrics["high_uncertainty_flag"]:
        score += 10
    if demand_metrics["demand_variability_class"] == "ERRATIC":
        score += 10
    quality = 1.0
    penalties = {
        "INSUFFICIENT_HISTORY_FOR_CONTEXT": 0.25,
        "FORECAST_FIELDS_UNAVAILABLE": 0.25,
        "FORECAST_BIAS_UNAVAILABLE": 0.10,
        "FORECAST_HORIZON_APPROXIMATED": 0.10,
        "HIGH_ZERO_DEMAND_RATIO": 0.10,
        "STOCKOUT_CENSOR_LOW_CONFIDENCE": 0.10,
    }
    if demand_metrics["zero_demand_day_ratio"] >= 0.40:
        warnings.append("HIGH_ZERO_DEMAND_RATIO")
    for code, penalty in penalties.items():
        if code in warnings:
            quality -= penalty
    return {
        "demand_urgency_score": round(min(max(score, 0), 100), 2),
        "demand_pressure_7d": round(pressure_7d, 4),
        "demand_pressure_30d": round(pressure_30d, 4),
        "demand_data_quality_score": round(min(max(quality, 0), 1), 4),
    }


def _derived_confidence(sku_performance: pd.DataFrame, sku_forecasts: pd.DataFrame, demand_metrics: dict[str, Any]) -> float:
    if not sku_performance.empty and "wape" in sku_performance.columns:
        wape = pd.to_numeric(sku_performance["wape"], errors="coerce").min()
        if pd.notna(wape):
            return float(1 - min(max(wape, 0), 1))
    if not sku_forecasts.empty and "forecast_confidence_score" in sku_forecasts.columns:
        score = pd.to_numeric(sku_forecasts["forecast_confidence_score"], errors="coerce").mean()
        if pd.notna(score):
            return float(score)
    penalty = min(demand_metrics["demand_cv"] / 2, 0.4) + min(demand_metrics["zero_demand_day_ratio"], 0.3)
    return 1 - penalty


def _estimate_bias_from_forecasts(sku_forecasts: pd.DataFrame) -> float:
    if sku_forecasts.empty or "error" not in sku_forecasts.columns:
        return math.nan
    value = pd.to_numeric(sku_forecasts["error"], errors="coerce").mean()
    return float(value) if pd.notna(value) else math.nan


def _bias_direction(bias: float) -> str:
    if math.isnan(bias):
        return "UNKNOWN"
    if bias <= DEMAND_PLANNING_CONTEXT_CONFIG["underforecast_bias_threshold"]:
        return "UNDERFORECAST"
    if bias >= DEMAND_PLANNING_CONTEXT_CONFIG["overforecast_bias_threshold"]:
        return "OVERFORECAST"
    return "NEUTRAL"


def _bias_severity(bias: float) -> str:
    if math.isnan(bias):
        return "UNKNOWN"
    abs_bias = abs(bias)
    if abs_bias >= 1:
        return "HIGH"
    if abs_bias >= 0.25:
        return "MEDIUM"
    return "LOW"


def _confidence_band(score: float) -> str:
    if score >= DEMAND_PLANNING_CONTEXT_CONFIG["medium_confidence_threshold"]:
        return "HIGH"
    if score >= DEMAND_PLANNING_CONTEXT_CONFIG["low_confidence_threshold"]:
        return "MEDIUM"
    return "LOW"


def _uncertainty_level(ratio: float) -> str:
    if ratio < 0.30:
        return "LOW"
    if ratio < DEMAND_PLANNING_CONTEXT_CONFIG["high_uncertainty_ratio_threshold"]:
        return "MEDIUM"
    return "HIGH"


def _seasonal_phase(index: float, flag: bool) -> str:
    if not flag:
        return "NON_SEASONAL"
    if index >= 1.15:
        return "PEAK"
    if index >= 1.0:
        return "BUILDUP"
    if index >= 0.85:
        return "DRAWDOWN"
    return "OFF_SEASON"


def _planning_note(row: dict[str, Any]) -> str:
    if row["stockout_censored_demand_flag"]:
        return "Use caution: possible censored demand may cause underforecasting."
    if row["high_uncertainty_flag"]:
        return "High uncertainty: inventory buffers should be reviewed."
    if row["upcoming_event_flag"]:
        return "Upcoming event may increase demand."
    if row["demand_variability_class"] == "STABLE":
        return "Stable demand profile; suitable for standard replenishment logic."
    if row["underforecast_risk_flag"]:
        return "Underforecast risk: downstream planning should review urgency and buffers."
    return "Use as downstream demand planning context with standard review."


def _join_codes(codes: list[str]) -> str:
    seen = []
    for code in codes:
        if code and code not in seen:
            seen.append(code)
    return ";".join(seen)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)
