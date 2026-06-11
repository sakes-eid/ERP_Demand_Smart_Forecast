"""Read-only Phase 1 demand intelligence integration for Phase 3."""

from __future__ import annotations

import pandas as pd

from config import (
    PHASE1_DEMAND_EVENT_FEATURES_FILE,
    PHASE1_DEMAND_PLANNING_CONTEXT_FILE,
    PHASE1_DEMAND_PROFILE_FILE,
    PHASE1_FORECAST_RESULTS_FILE,
    PHASE1_MODEL_REGISTRY_FILE,
    PHASE1_PRODUCTS_CLEAN_FILES,
)

PHASE1_DEFAULTS = {
    "product_name": "UNKNOWN",
    "category": "UNKNOWN",
    "demand_behavior_class": "UNKNOWN",
    "zero_demand_ratio": 0,
    "coefficient_of_variation": 0,
    "event_affected_ratio": 0,
    "data_sufficiency_class": "UNKNOWN",
    "total_demand": 0,
    "average_daily_demand": 0,
    "champion_model": "UNKNOWN",
    "champion_confidence_score": 0.50,
    "champion_risk_level": "MEDIUM_RISK",
    "average_p50_forecast": 0,
    "average_p90_forecast": 0,
    "average_forecast_confidence_score": 0.50,
    "dominant_forecast_risk_level": "MEDIUM_RISK",
    "seasonal_flag": False,
    "event_frequency": 0,
    "recent_event_flag": False,
    "promotion_sensitive_flag": False,
    "phase1_context_status": "MISSING_PHASE1_CONTEXT",
    "phase1_context_source": "LEGACY_PHASE1_OUTPUTS",
    "forecast_demand_7d": 0,
    "forecast_demand_30d": 0,
    "forecast_demand_60d": 0,
    "forecast_demand_90d": 0,
    "average_daily_forecast_demand_30d": 0,
    "forecast_uncertainty_level": "UNKNOWN",
    "underforecast_risk_flag": False,
    "stockout_censored_demand_flag": False,
    "demand_urgency_score": 0,
}


def load_phase1_inventory_context(sku_ids: set[str]) -> tuple[pd.DataFrame, dict]:
    """Load Phase 1 context as one row per SKU with safe fallbacks."""
    warnings: list[str] = []
    context = _base_context(sku_ids)

    demand_planning_context = _load_optional(PHASE1_DEMAND_PLANNING_CONTEXT_FILE, "phase1_demand_planning_context", warnings)
    if not demand_planning_context.empty and "sku_id" in demand_planning_context.columns:
        context = _merge_demand_planning_context(context, demand_planning_context)
        context = _fill_defaults(context)
        context.loc[:, "phase1_context_status"] = "LOADED_FROM_PHASE1"
        context.loc[:, "phase1_context_source"] = "PHASE1_DEMAND_PLANNING_CONTEXT"
        metadata = {
            "phase1_context_loaded": True,
            "phase1_warnings": warnings,
            "phase1_skus_loaded": int(len(context)),
            "phase1_context_source": "PHASE1_DEMAND_PLANNING_CONTEXT",
        }
        return context, metadata

    products = _load_first_existing(PHASE1_PRODUCTS_CLEAN_FILES, "products", warnings)
    demand_profile = _load_optional(PHASE1_DEMAND_PROFILE_FILE, "demand_profile", warnings)
    forecast_results = _load_optional(PHASE1_FORECAST_RESULTS_FILE, "forecast_results", warnings)
    model_registry = _load_optional(PHASE1_MODEL_REGISTRY_FILE, "model_registry", warnings)
    event_features = _load_optional(PHASE1_DEMAND_EVENT_FEATURES_FILE, "demand_with_event_features", warnings)

    loaded_any = any(not df.empty for df in [products, demand_profile, forecast_results, model_registry, event_features])

    context = _merge_products(context, products)
    context = _merge_demand_profile(context, demand_profile)
    context = _merge_model_registry(context, model_registry)
    context = _merge_forecast_summary(context, forecast_results, model_registry)
    context = _merge_event_summary(context, event_features)
    context = _fill_defaults(context)
    if loaded_any:
        loaded_columns = context.drop(columns=["sku_id"], errors="ignore").notna().any(axis=1)
        context.loc[loaded_columns, "phase1_context_status"] = "LOADED_FROM_PHASE1"

    metadata = {
        "phase1_context_loaded": bool((context["phase1_context_status"] == "LOADED_FROM_PHASE1").any()),
        "phase1_warnings": warnings,
        "phase1_skus_loaded": int((context["phase1_context_status"] == "LOADED_FROM_PHASE1").sum()),
        "phase1_context_source": "LEGACY_PHASE1_OUTPUTS",
    }
    return context, metadata


def _merge_demand_planning_context(context: pd.DataFrame, demand_planning_context: pd.DataFrame) -> pd.DataFrame:
    """Merge the official Phase 1 downstream demand planning bridge."""
    source = demand_planning_context.copy()
    rename = {
        "average_daily_demand_observed": "average_daily_demand",
        "demand_cv": "coefficient_of_variation",
        "demand_variability_class": "demand_behavior_class",
        "model_confidence_score": "champion_confidence_score",
    }
    source = source.rename(columns={old: new for old, new in rename.items() if old in source.columns and new not in source.columns})
    columns = [
        "sku_id",
        "product_name",
        "category",
        "demand_behavior_class",
        "coefficient_of_variation",
        "average_daily_demand",
        "champion_model",
        "champion_confidence_score",
        "forecast_demand_7d",
        "forecast_demand_30d",
        "forecast_demand_60d",
        "forecast_demand_90d",
        "average_daily_forecast_demand_30d",
        "forecast_uncertainty_level",
        "dominant_forecast_risk_level",
        "underforecast_risk_flag",
        "stockout_censored_demand_flag",
        "demand_urgency_score",
    ]
    merged = _merge_available(context, source, columns)
    if "average_p50_forecast" not in merged.columns and "forecast_demand_30d" in merged.columns:
        merged["average_p50_forecast"] = pd.to_numeric(merged["forecast_demand_30d"], errors="coerce").fillna(0) / 30
    if "average_p90_forecast" not in merged.columns and "forecast_demand_30d" in merged.columns:
        merged["average_p90_forecast"] = pd.to_numeric(merged["forecast_demand_30d"], errors="coerce").fillna(0) / 30
    return merged


def _base_context(sku_ids: set[str]) -> pd.DataFrame:
    """Create base SKU rows with defaults."""
    return pd.DataFrame({"sku_id": sorted(str(sku_id).strip() for sku_id in sku_ids)})


def _load_optional(path, label: str, warnings: list[str]) -> pd.DataFrame:
    """Load a CSV if it exists, otherwise record a warning."""
    if not path.exists():
        warnings.append(f"Phase 1 {label} file missing: {path.name}")
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        warnings.append(f"Could not read Phase 1 {label}: {exc}")
        return pd.DataFrame()


def _load_first_existing(paths, label: str, warnings: list[str]) -> pd.DataFrame:
    """Load the first existing CSV from naming variants."""
    for path in paths:
        if path.exists():
            try:
                return pd.read_csv(path)
            except Exception as exc:
                warnings.append(f"Could not read Phase 1 {label}: {exc}")
                return pd.DataFrame()
    warnings.append(f"Phase 1 {label} file missing: expected one of {[path.name for path in paths]}")
    return pd.DataFrame()


def _merge_products(context: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Merge product name and category when available."""
    if products.empty or "sku_id" not in products.columns:
        return context
    product_columns = ["sku_id"]
    for column in ["product_name", "sku_name", "name", "category"]:
        if column in products.columns:
            product_columns.append(column)
    products = products[product_columns].drop_duplicates("sku_id")
    products = products.rename(columns={"sku_name": "product_name", "name": "product_name"})
    return context.merge(products, on="sku_id", how="left")


def _merge_demand_profile(context: pd.DataFrame, demand_profile: pd.DataFrame) -> pd.DataFrame:
    """Merge demand profile fields."""
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
    return _merge_available(context, demand_profile, columns)


def _merge_model_registry(context: pd.DataFrame, model_registry: pd.DataFrame) -> pd.DataFrame:
    """Merge champion model fields."""
    columns = [
        "sku_id",
        "champion_model",
        "champion_confidence_score",
        "champion_risk_level",
    ]
    return _merge_available(context, model_registry, columns)


def _merge_forecast_summary(
    context: pd.DataFrame,
    forecast_results: pd.DataFrame,
    model_registry: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate champion forecast context per SKU."""
    if forecast_results.empty or "sku_id" not in forecast_results.columns:
        return context
    forecasts = forecast_results.copy()
    if not model_registry.empty and {"sku_id", "champion_model"}.issubset(model_registry.columns) and "model_name" in forecasts.columns:
        champions = model_registry[["sku_id", "champion_model"]].drop_duplicates("sku_id")
        forecasts = forecasts.merge(champions, on="sku_id", how="left")
        forecasts = forecasts[forecasts["model_name"] == forecasts["champion_model"]]
    summary = forecasts.groupby("sku_id", dropna=False).agg(
        average_p50_forecast=("p50", "mean") if "p50" in forecasts.columns else ("forecast_quantity", "mean"),
        average_p90_forecast=("p90", "mean") if "p90" in forecasts.columns else ("forecast_quantity", "mean"),
        average_forecast_confidence_score=("forecast_confidence_score", "mean")
        if "forecast_confidence_score" in forecasts.columns
        else ("sku_id", "size"),
    ).reset_index()
    if "forecast_risk_level" in forecasts.columns:
        risk = forecasts.groupby("sku_id")["forecast_risk_level"].agg(_mode_or_unknown).reset_index()
        risk = risk.rename(columns={"forecast_risk_level": "dominant_forecast_risk_level"})
        summary = summary.merge(risk, on="sku_id", how="left")
    return context.merge(summary, on="sku_id", how="left")


def _merge_event_summary(context: pd.DataFrame, event_features: pd.DataFrame) -> pd.DataFrame:
    """Aggregate optional event context per SKU."""
    if event_features.empty or "sku_id" not in event_features.columns:
        return context
    working = event_features.copy()
    if "date" in working.columns:
        working["date"] = pd.to_datetime(working["date"], errors="coerce")
    if "has_event" not in working.columns:
        working["has_event"] = False
    summary = working.groupby("sku_id", dropna=False).agg(
        event_frequency=("has_event", "mean"),
        recent_event_flag=("has_event", "max"),
    ).reset_index()
    summary["promotion_sensitive_flag"] = False
    if "promotion_flag" in working.columns:
        promo = working.groupby("sku_id")["promotion_flag"].max().reset_index()
        promo = promo.rename(columns={"promotion_flag": "promotion_sensitive_flag"})
        summary = summary.drop(columns=["promotion_sensitive_flag"]).merge(promo, on="sku_id", how="left")
    summary["seasonal_flag"] = False
    return context.merge(summary, on="sku_id", how="left")


def _merge_available(context: pd.DataFrame, source: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Merge only columns that are present."""
    if source.empty or "sku_id" not in source.columns:
        return context
    available = [column for column in columns if column in source.columns]
    if available == ["sku_id"]:
        return context
    return context.merge(source[available].drop_duplicates("sku_id"), on="sku_id", how="left")


def _fill_defaults(context: pd.DataFrame) -> pd.DataFrame:
    """Fill missing columns and values with Phase 1 defaults."""
    filled = context.copy()
    for column, default in PHASE1_DEFAULTS.items():
        if column not in filled.columns:
            filled[column] = default
        else:
            filled[column] = filled[column].fillna(default)
    return filled[["sku_id", *PHASE1_DEFAULTS.keys()]]


def _mode_or_unknown(series: pd.Series) -> str:
    """Return the most frequent non-null value."""
    values = series.dropna()
    if values.empty:
        return "MEDIUM_RISK"
    return str(values.mode().iloc[0])
