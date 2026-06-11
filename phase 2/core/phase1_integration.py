"""Load Phase 1 demand planning context for Phase 2 procurement scoring."""

import pandas as pd

from config import (
    PHASE1_DEMAND_PLANNING_CONTEXT_FILE,
    PHASE1_DEMAND_PROFILE_FILE,
    PHASE1_FORECAST_RESULTS_FILE,
    PHASE1_MODEL_REGISTRY_FILE,
    PHASE1_PRODUCTS_CLEAN_FILES,
)


NEW_CONTEXT_COLUMNS = [
    "sku_id",
    "product_name",
    "category",
    "demand_profile",
    "demand_variability_class",
    "demand_cv",
    "demand_std_daily",
    "average_daily_demand_observed",
    "zero_demand_day_ratio",
    "demand_spikiness_score",
    "forecast_demand_7d",
    "forecast_demand_14d",
    "forecast_demand_30d",
    "forecast_demand_60d",
    "forecast_demand_90d",
    "average_daily_forecast_demand_30d",
    "champion_model",
    "model_confidence_score",
    "forecast_confidence_band",
    "forecast_uncertainty_level",
    "forecast_uncertainty_ratio_30d",
    "high_uncertainty_flag",
    "forecast_bias",
    "bias_direction",
    "bias_severity",
    "underforecast_risk_flag",
    "overforecast_risk_flag",
    "stockout_censored_demand_flag",
    "suspected_stockout_days_30d",
    "lost_sales_estimate_30d",
    "adjusted_demand_30d",
    "stockout_censor_confidence",
    "seasonality_flag",
    "seasonality_strength",
    "seasonal_phase",
    "upcoming_event_flag",
    "upcoming_event_count",
    "event_uplift_factor",
    "event_risk_window_flag",
    "demand_urgency_score",
    "demand_pressure_7d",
    "demand_pressure_30d",
    "demand_data_quality_score",
    "demand_planning_warning_codes",
    "downstream_planning_notes",
]

DEMAND_CONTEXT_COLUMNS = [
    *NEW_CONTEXT_COLUMNS,
    "phase1_context_source",
    "phase1_context_version",
    "phase1_demand_warning_codes",
    "demand_integration_notes",
    "demand_behavior_class",
    "coefficient_of_variation",
    "event_affected_ratio",
    "data_sufficiency_class",
    "total_demand",
    "average_daily_demand",
    "champion_confidence_score",
    "champion_risk_level",
    "average_p50_forecast",
    "average_p90_forecast",
    "average_forecast_confidence_score",
    "dominant_forecast_risk_level",
    "demand_context_status",
]


def load_phase1_demand_context(sku_ids: set[str]) -> tuple[pd.DataFrame, dict[str, object]]:
    """Load the new Phase 1 planning bridge, falling back to legacy outputs."""
    warnings: list[str] = []
    sku_frame = pd.DataFrame({"sku_id": sorted(sku_ids)})

    new_context = _load_new_context(warnings)
    if not new_context.empty:
        context = sku_frame.merge(new_context, on="sku_id", how="left")
        source = "PHASE1_DEMAND_PLANNING_CONTEXT"
        version = "DEMAND_PLANNING_CONTEXT_V1"
        fallback_used = False
    else:
        warnings.append("PHASE1_DEMAND_CONTEXT_FALLBACK_USED")
        context = _legacy_context(sku_frame, warnings)
        source = "LEGACY_PHASE1_OUTPUTS" if (context["demand_context_status"] == "LOADED_FROM_PHASE1").any() else "INTERNAL_FALLBACK"
        version = "LEGACY_COMPATIBILITY"
        fallback_used = True

    context = _fill_context_defaults(context, source, version)
    missing_count = int((context["demand_context_status"] != "LOADED_FROM_PHASE1").sum())
    if missing_count:
        warnings.append("PHASE1_DEMAND_CONTEXT_MISSING_SKUS")
    if source == "INTERNAL_FALLBACK":
        warnings.append("PHASE1_DEMAND_CONTEXT_UNAVAILABLE")

    metadata = {
        "phase1_context_loaded": bool((context["demand_context_status"] == "LOADED_FROM_PHASE1").any()),
        "phase1_context_source": source if source != "INTERNAL_FALLBACK" else "INTERNAL_FALLBACK",
        "phase1_context_version": version,
        "phase1_context_row_count": int(len(context)),
        "phase1_context_missing_sku_count": missing_count,
        "phase1_context_fallback_used": fallback_used,
        "phase1_context_warning_codes": ";".join(sorted(set(warnings))) if warnings else "NONE",
        "phase1_warnings": warnings,
        "phase1_product_sku_count": int(len(context)),
    }
    return context[DEMAND_CONTEXT_COLUMNS], metadata


def _load_new_context(warnings: list[str]) -> pd.DataFrame:
    if not PHASE1_DEMAND_PLANNING_CONTEXT_FILE.exists():
        warnings.append("Missing Phase 1 demand planning context file.")
        return pd.DataFrame()
    try:
        context = pd.read_csv(PHASE1_DEMAND_PLANNING_CONTEXT_FILE)
    except Exception as exc:
        warnings.append(f"Could not read Phase 1 demand planning context: {exc}")
        return pd.DataFrame()
    if "sku_id" not in context.columns:
        warnings.append("Phase 1 demand planning context missing sku_id.")
        return pd.DataFrame()
    context = context.drop_duplicates("sku_id")
    for column in NEW_CONTEXT_COLUMNS:
        if column not in context.columns:
            context[column] = _default_for_column(column)
            warnings.append(f"PHASE1_FIELD_MISSING_{column.upper()}")
    context["phase1_context_source"] = "PHASE1_DEMAND_PLANNING_CONTEXT"
    context["phase1_context_version"] = "DEMAND_PLANNING_CONTEXT_V1"
    context["phase1_demand_warning_codes"] = context["demand_planning_warning_codes"].fillna("NONE")
    context["demand_integration_notes"] = context["downstream_planning_notes"].fillna(
        "Loaded from Phase 1 demand planning context."
    )
    context["demand_behavior_class"] = context["demand_profile"].fillna("UNKNOWN")
    context["coefficient_of_variation"] = pd.to_numeric(context["demand_cv"], errors="coerce").fillna(0)
    context["event_affected_ratio"] = _bool_series(context["upcoming_event_flag"]).astype(float)
    context["data_sufficiency_class"] = context["demand_data_quality_score"].apply(_data_quality_class)
    context["total_demand"] = pd.to_numeric(context["adjusted_demand_30d"], errors="coerce")
    context["average_daily_demand"] = pd.to_numeric(context["average_daily_demand_observed"], errors="coerce")
    context["champion_confidence_score"] = pd.to_numeric(context["model_confidence_score"], errors="coerce").fillna(0.5)
    context["champion_risk_level"] = context["forecast_uncertainty_level"].apply(_forecast_risk_level)
    context["average_p50_forecast"] = pd.to_numeric(context["average_daily_forecast_demand_30d"], errors="coerce")
    context["average_p90_forecast"] = pd.to_numeric(context["forecast_demand_30d"], errors="coerce") / 30
    context["average_forecast_confidence_score"] = context["champion_confidence_score"]
    context["dominant_forecast_risk_level"] = context["champion_risk_level"]
    context["demand_context_status"] = "LOADED_FROM_PHASE1"
    return context


def _legacy_context(sku_frame: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    profile = _load_csv(PHASE1_DEMAND_PROFILE_FILE, warnings)
    registry = _load_csv(PHASE1_MODEL_REGISTRY_FILE, warnings)
    forecasts = _load_csv(PHASE1_FORECAST_RESULTS_FILE, warnings)
    _load_first_available(PHASE1_PRODUCTS_CLEAN_FILES, warnings)
    context = sku_frame.merge(_profile_context(profile), on="sku_id", how="left")
    context = context.merge(_registry_context(registry), on="sku_id", how="left")
    context = context.merge(_forecast_context(forecasts, registry), on="sku_id", how="left")
    context["demand_context_status"] = context.apply(_legacy_context_status, axis=1)
    return context


def _load_csv(path, warnings: list[str]) -> pd.DataFrame:
    if not path.exists():
        warnings.append(f"Missing Phase 1 file: {path.name}")
        return pd.DataFrame()
    return pd.read_csv(path)


def _load_first_available(paths, warnings: list[str]) -> pd.DataFrame:
    for path in paths:
        if path.exists():
            return pd.read_csv(path)
    warnings.append("Missing Phase 1 products file: products_clean.csv or products_cleaned.csv")
    return pd.DataFrame()


def _profile_context(profile: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "sku_id",
        "demand_behavior_class",
        "zero_demand_ratio",
        "coefficient_of_variation",
        "event_affected_ratio",
        "data_sufficiency_class",
        "total_demand",
        "average_daily_demand",
    ]
    return _select_existing_columns(profile, columns)


def _registry_context(registry: pd.DataFrame) -> pd.DataFrame:
    columns = ["sku_id", "champion_model", "champion_confidence_score", "champion_risk_level"]
    return _select_existing_columns(registry, columns)


def _forecast_context(forecasts: pd.DataFrame, registry: pd.DataFrame) -> pd.DataFrame:
    if forecasts.empty or "sku_id" not in forecasts.columns:
        return pd.DataFrame(columns=["sku_id"])
    working = forecasts.copy()
    if not registry.empty and {"sku_id", "champion_model"}.issubset(registry.columns) and "model_name" in working.columns:
        working = working.merge(registry[["sku_id", "champion_model"]], on="sku_id", how="left")
        working = working[working["model_name"] == working["champion_model"]]
    aggregation = {}
    if "p50" in working.columns:
        aggregation["average_p50_forecast"] = ("p50", "mean")
    elif "forecast_quantity" in working.columns:
        aggregation["average_p50_forecast"] = ("forecast_quantity", "mean")
    if "p90" in working.columns:
        aggregation["average_p90_forecast"] = ("p90", "mean")
    if "forecast_confidence_score" in working.columns:
        aggregation["average_forecast_confidence_score"] = ("forecast_confidence_score", "mean")
    if not aggregation:
        return pd.DataFrame({"sku_id": sorted(working["sku_id"].dropna().unique())})
    context = working.groupby("sku_id").agg(**aggregation).reset_index()
    if "forecast_risk_level" in working.columns:
        risk = working.groupby("sku_id")["forecast_risk_level"].agg(_mode_or_default).reset_index()
        context = context.merge(risk.rename(columns={"forecast_risk_level": "dominant_forecast_risk_level"}), on="sku_id", how="left")
    return context


def _select_existing_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df.empty or "sku_id" not in df.columns:
        return pd.DataFrame(columns=["sku_id"])
    return df[[column for column in columns if column in df.columns]].drop_duplicates("sku_id")


def _fill_context_defaults(context: pd.DataFrame, source: str, version: str) -> pd.DataFrame:
    filled = context.copy()
    defaults = {column: _default_for_column(column) for column in DEMAND_CONTEXT_COLUMNS if column != "sku_id"}
    defaults.update(
        {
            "phase1_context_source": source,
            "phase1_context_version": version,
            "phase1_demand_warning_codes": "NONE",
            "demand_integration_notes": "Phase 1 context loaded for procurement planning.",
            "demand_context_status": "MISSING_PHASE1_CONTEXT",
        }
    )
    for column, default in defaults.items():
        if column not in filled.columns:
            filled[column] = default
        else:
            filled[column] = filled[column].fillna(default)
    loaded_mask = filled["phase1_context_source"].eq("PHASE1_DEMAND_PLANNING_CONTEXT") & filled["champion_model"].ne("UNKNOWN")
    legacy_loaded = filled["demand_behavior_class"].ne("UNKNOWN") | filled["champion_model"].ne("UNKNOWN")
    filled.loc[loaded_mask | legacy_loaded, "demand_context_status"] = "LOADED_FROM_PHASE1"
    return filled


def _default_for_column(column: str):
    bool_columns = {
        "high_uncertainty_flag",
        "underforecast_risk_flag",
        "overforecast_risk_flag",
        "stockout_censored_demand_flag",
        "seasonality_flag",
        "upcoming_event_flag",
        "event_risk_window_flag",
    }
    numeric_defaults = {
        "demand_cv": 0.0,
        "demand_std_daily": 0.0,
        "average_daily_demand_observed": 0.0,
        "zero_demand_day_ratio": 0.0,
        "demand_spikiness_score": 0.0,
        "forecast_demand_7d": 0.0,
        "forecast_demand_14d": 0.0,
        "forecast_demand_30d": 0.0,
        "forecast_demand_60d": 0.0,
        "forecast_demand_90d": 0.0,
        "average_daily_forecast_demand_30d": 0.0,
        "model_confidence_score": 0.5,
        "forecast_uncertainty_ratio_30d": 0.0,
        "forecast_bias": 0.0,
        "suspected_stockout_days_30d": 0,
        "lost_sales_estimate_30d": 0.0,
        "adjusted_demand_30d": 0.0,
        "seasonality_strength": 0.0,
        "upcoming_event_count": 0,
        "event_uplift_factor": 1.0,
        "demand_urgency_score": 0.0,
        "demand_pressure_7d": 0.0,
        "demand_pressure_30d": 0.0,
        "demand_data_quality_score": 0.5,
        "coefficient_of_variation": 0.0,
        "event_affected_ratio": 0.0,
        "total_demand": 0.0,
        "average_daily_demand": 0.0,
        "champion_confidence_score": 0.5,
        "average_p50_forecast": 0.0,
        "average_p90_forecast": 0.0,
        "average_forecast_confidence_score": 0.5,
    }
    if column in bool_columns:
        return False
    if column in numeric_defaults:
        return numeric_defaults[column]
    return {
        "demand_profile": "UNKNOWN",
        "demand_variability_class": "UNKNOWN",
        "forecast_confidence_band": "UNKNOWN",
        "forecast_uncertainty_level": "UNKNOWN",
        "bias_direction": "UNKNOWN",
        "bias_severity": "UNKNOWN",
        "stockout_censor_confidence": "NONE",
        "seasonal_phase": "UNKNOWN",
        "demand_planning_warning_codes": "NONE",
        "downstream_planning_notes": "",
        "champion_model": "UNKNOWN",
        "champion_risk_level": "MEDIUM_RISK",
        "dominant_forecast_risk_level": "MEDIUM_RISK",
        "data_sufficiency_class": "UNKNOWN",
    }.get(column, "")


def _data_quality_class(score) -> str:
    value = pd.to_numeric(pd.Series([score]), errors="coerce").fillna(0.5).iloc[0]
    if value >= 0.75:
        return "HIGH"
    if value >= 0.45:
        return "MEDIUM"
    return "LOW"


def _forecast_risk_level(level) -> str:
    text = str(level).upper()
    if text == "HIGH":
        return "HIGH_RISK"
    if text == "LOW":
        return "LOW_RISK"
    return "MEDIUM_RISK"


def _legacy_context_status(row: pd.Series) -> str:
    return "LOADED_FROM_PHASE1" if row.get("demand_behavior_class", "UNKNOWN") != "UNKNOWN" or row.get("champion_model", "UNKNOWN") != "UNKNOWN" else "MISSING_PHASE1_CONTEXT"


def _mode_or_default(series: pd.Series) -> str:
    mode = series.dropna().mode()
    return "MEDIUM_RISK" if mode.empty else str(mode.iloc[0])


def _bool_series(series: pd.Series) -> pd.Series:
    normalized = series.where(series.notna(), False)
    if normalized.dtype == bool:
        return normalized
    return normalized.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y", "t"})
