"""Load Phase 1 demand intelligence context for Phase 2 procurement scoring."""

import pandas as pd

from config import (
    PHASE1_DEMAND_PROFILE_FILE,
    PHASE1_FORECAST_RESULTS_FILE,
    PHASE1_MODEL_REGISTRY_FILE,
    PHASE1_PRODUCTS_CLEAN_FILES,
)

DEMAND_CONTEXT_COLUMNS = [
    "sku_id",
    "demand_behavior_class",
    "zero_demand_ratio",
    "coefficient_of_variation",
    "event_affected_ratio",
    "data_sufficiency_class",
    "total_demand",
    "average_daily_demand",
    "champion_model",
    "champion_confidence_score",
    "champion_risk_level",
    "average_p50_forecast",
    "average_p90_forecast",
    "average_forecast_confidence_score",
    "dominant_forecast_risk_level",
    "demand_context_status",
]


def load_phase1_demand_context(sku_ids: set[str]) -> tuple[pd.DataFrame, dict[str, object]]:
    """Load Phase 1 SKU demand context with fallbacks for missing files."""
    warnings: list[str] = []
    profile = _load_csv(PHASE1_DEMAND_PROFILE_FILE, warnings)
    registry = _load_csv(PHASE1_MODEL_REGISTRY_FILE, warnings)
    forecasts = _load_csv(PHASE1_FORECAST_RESULTS_FILE, warnings)
    products = _load_first_available(PHASE1_PRODUCTS_CLEAN_FILES, warnings)

    context = pd.DataFrame({"sku_id": sorted(sku_ids)})
    context = context.merge(_profile_context(profile), on="sku_id", how="left")
    context = context.merge(_registry_context(registry), on="sku_id", how="left")
    context = context.merge(_forecast_context(forecasts, registry), on="sku_id", how="left")

    context = _fill_context_defaults(context)
    context["demand_context_status"] = context.apply(_context_status, axis=1)
    if not products.empty and "sku_id" in products.columns:
        loaded_sku_count = int(products["sku_id"].nunique())
    else:
        loaded_sku_count = int((context["demand_context_status"] == "LOADED_FROM_PHASE1").sum())

    metadata = {
        "phase1_context_loaded": bool((context["demand_context_status"] == "LOADED_FROM_PHASE1").any()),
        "phase1_warnings": warnings,
        "phase1_product_sku_count": loaded_sku_count,
    }
    return context[DEMAND_CONTEXT_COLUMNS], metadata


def _load_csv(path, warnings: list[str]) -> pd.DataFrame:
    """Load a CSV if it exists, otherwise record a warning."""
    if not path.exists():
        warnings.append(f"Missing Phase 1 file: {path.name}")
        return pd.DataFrame()
    return pd.read_csv(path)


def _load_first_available(paths, warnings: list[str]) -> pd.DataFrame:
    """Load the first available CSV from candidate paths."""
    for path in paths:
        if path.exists():
            return pd.read_csv(path)
    warnings.append("Missing Phase 1 products file: products_clean.csv or products_cleaned.csv")
    return pd.DataFrame()


def _profile_context(profile: pd.DataFrame) -> pd.DataFrame:
    """Extract demand profile columns by SKU."""
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
    """Extract champion model context by SKU."""
    columns = ["sku_id", "champion_model", "champion_confidence_score", "champion_risk_level"]
    return _select_existing_columns(registry, columns)


def _forecast_context(forecasts: pd.DataFrame, registry: pd.DataFrame) -> pd.DataFrame:
    """Aggregate champion forecast context by SKU."""
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
        risk = risk.rename(columns={"forecast_risk_level": "dominant_forecast_risk_level"})
        context = context.merge(risk, on="sku_id", how="left")
    return context


def _select_existing_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Return existing requested columns or an empty SKU frame."""
    if df.empty or "sku_id" not in df.columns:
        return pd.DataFrame(columns=["sku_id"])
    existing_columns = [column for column in columns if column in df.columns]
    return df[existing_columns].drop_duplicates("sku_id")


def _mode_or_default(series: pd.Series) -> str:
    """Return the most common non-null value or MEDIUM_RISK."""
    mode = series.dropna().mode()
    if mode.empty:
        return "MEDIUM_RISK"
    return str(mode.iloc[0])


def _fill_context_defaults(context: pd.DataFrame) -> pd.DataFrame:
    """Fill sensible defaults for missing demand context."""
    filled = context.copy()
    defaults = {
        "demand_behavior_class": "UNKNOWN",
        "zero_demand_ratio": 0.0,
        "coefficient_of_variation": 0.0,
        "event_affected_ratio": 0.0,
        "data_sufficiency_class": "UNKNOWN",
        "total_demand": pd.NA,
        "average_daily_demand": pd.NA,
        "champion_model": "UNKNOWN",
        "champion_confidence_score": 0.50,
        "champion_risk_level": "MEDIUM_RISK",
        "average_p50_forecast": pd.NA,
        "average_p90_forecast": pd.NA,
        "average_forecast_confidence_score": 0.50,
        "dominant_forecast_risk_level": "MEDIUM_RISK",
    }
    for column, default_value in defaults.items():
        if column not in filled.columns:
            filled[column] = default_value
        else:
            filled[column] = filled[column].fillna(default_value)
    return filled


def _context_status(row: pd.Series) -> str:
    """Return whether a SKU has useful Phase 1 context."""
    has_profile = row["demand_behavior_class"] != "UNKNOWN"
    has_registry = row["champion_model"] != "UNKNOWN"
    return "LOADED_FROM_PHASE1" if has_profile or has_registry else "MISSING_PHASE1_CONTEXT"
