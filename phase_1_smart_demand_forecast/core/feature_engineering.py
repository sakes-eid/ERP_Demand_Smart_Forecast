"""Model-ready feature engineering for future demand forecasting."""

import pandas as pd

from config import DATE_FORMAT

PROFILE_FEATURE_COLUMNS = [
    "demand_behavior_class",
    "coefficient_of_variation",
    "zero_demand_ratio",
    "event_affected_ratio",
    "data_sufficiency_class",
]

STANDARD_EVENT_COLUMNS = [
    "has_event",
    "promotion_flag",
    "holiday_flag",
    "before_event_flag",
    "during_event_flag",
    "after_event_flag",
    "event_count",
]


def build_demand_features(
    demand_with_event_features: pd.DataFrame,
    demand_profile: pd.DataFrame,
) -> pd.DataFrame:
    """Build a model-ready feature dataset without dropping history rows."""
    features = _prepare_base_frame(demand_with_event_features)
    features = add_time_features(features)
    features = add_lag_features(features)
    features = add_rolling_statistics(features)
    features = add_demand_dynamics(features)
    features = standardize_event_features(features)
    features = add_recent_event_features(features)
    features = add_anomaly_features(features)
    features = merge_profile_features(features, demand_profile)
    features["date"] = features["date"].dt.strftime(DATE_FORMAT)
    return features


def add_time_features(features: pd.DataFrame) -> pd.DataFrame:
    """Add calendar-based features from the demand date."""
    enriched = features.copy()
    enriched["day_of_week"] = enriched["date"].dt.dayofweek
    enriched["week_of_year"] = enriched["date"].dt.isocalendar().week.astype(int)
    enriched["month"] = enriched["date"].dt.month
    enriched["quarter"] = enriched["date"].dt.quarter
    enriched["weekend_flag"] = enriched["day_of_week"].isin([5, 6]).astype(int)
    enriched["month_start_flag"] = enriched["date"].dt.is_month_start.astype(int)
    enriched["month_end_flag"] = enriched["date"].dt.is_month_end.astype(int)
    return enriched


def add_lag_features(features: pd.DataFrame) -> pd.DataFrame:
    """Add SKU-specific demand lag features."""
    enriched = features.copy()
    grouped_demand = enriched.groupby("sku_id")["quantity_demanded"]

    for lag_days in (1, 3, 7, 14, 30):
        enriched[f"lag_{lag_days}"] = grouped_demand.shift(lag_days)

    return enriched


def add_rolling_statistics(features: pd.DataFrame) -> pd.DataFrame:
    """Add SKU-specific rolling statistics using only prior demand values."""
    enriched = features.copy()
    prior_demand = enriched.groupby("sku_id")["quantity_demanded"].shift(1)

    for window in (7, 14, 30):
        rolling = prior_demand.groupby(enriched["sku_id"]).rolling(window=window, min_periods=1)
        enriched[f"rolling_mean_{window}"] = rolling.mean().reset_index(level=0, drop=True)
        enriched[f"rolling_std_{window}"] = rolling.std().reset_index(level=0, drop=True)

    rolling_30 = prior_demand.groupby(enriched["sku_id"]).rolling(window=30, min_periods=1)
    enriched["rolling_min_30"] = rolling_30.min().reset_index(level=0, drop=True)
    enriched["rolling_max_30"] = rolling_30.max().reset_index(level=0, drop=True)
    return enriched


def add_demand_dynamics(features: pd.DataFrame) -> pd.DataFrame:
    """Add simple SKU-specific change, trend, and momentum features."""
    enriched = features.copy()
    enriched["demand_change_1"] = enriched["quantity_demanded"] - enriched["lag_1"]
    enriched["demand_change_7"] = enriched["quantity_demanded"] - enriched["lag_7"]
    enriched["rolling_trend_7"] = enriched["rolling_mean_7"] - enriched["rolling_mean_14"]
    enriched["rolling_trend_30"] = enriched["rolling_mean_7"] - enriched["rolling_mean_30"]
    enriched["momentum_7"] = enriched["lag_1"] - enriched["lag_7"]
    enriched["momentum_30"] = enriched["lag_1"] - enriched["lag_30"]
    return enriched


def standardize_event_features(features: pd.DataFrame) -> pd.DataFrame:
    """Ensure standard event feature columns are numeric and present."""
    enriched = features.copy()
    for column in STANDARD_EVENT_COLUMNS:
        if column not in enriched.columns:
            enriched[column] = 0
        enriched[column] = pd.to_numeric(enriched[column], errors="coerce").fillna(0).astype(int)
    return enriched


def add_recent_event_features(features: pd.DataFrame) -> pd.DataFrame:
    """Add recent SKU-specific event counts based on prior rows."""
    enriched = features.copy()
    prior_event_count = enriched.groupby("sku_id")["event_count"].shift(1).fillna(0)

    for window in (7, 30):
        rolling = prior_event_count.groupby(enriched["sku_id"]).rolling(window=window, min_periods=1)
        enriched[f"recent_event_count_{window}"] = rolling.sum().reset_index(level=0, drop=True)

    return enriched


def add_anomaly_features(features: pd.DataFrame) -> pd.DataFrame:
    """Add recent anomaly features using known invalid/anomaly markers."""
    enriched = features.copy()
    anomaly_indicator = _build_anomaly_indicator(enriched)
    prior_anomaly = anomaly_indicator.groupby(enriched["sku_id"]).shift(1).fillna(0)

    anomaly_count_7 = prior_anomaly.groupby(enriched["sku_id"]).rolling(window=7, min_periods=1).sum()
    anomaly_count_30 = prior_anomaly.groupby(enriched["sku_id"]).rolling(window=30, min_periods=1).sum()

    enriched["anomaly_recent_flag"] = (anomaly_count_7.reset_index(level=0, drop=True) > 0).astype(int)
    enriched["anomaly_count_30"] = anomaly_count_30.reset_index(level=0, drop=True)
    return enriched


def merge_profile_features(features: pd.DataFrame, demand_profile: pd.DataFrame) -> pd.DataFrame:
    """Merge SKU-level profile features into the row-level feature dataset."""
    profile_columns = ["sku_id"] + PROFILE_FEATURE_COLUMNS
    profile = demand_profile[profile_columns].copy()
    return features.merge(profile, on="sku_id", how="left")


def count_nan_lag_rows(features: pd.DataFrame) -> int:
    """Count rows with at least one unavailable lag value."""
    lag_columns = [column for column in features.columns if column.startswith("lag_")]
    if not lag_columns:
        return 0
    return int(features[lag_columns].isna().any(axis=1).sum())


def count_generated_feature_columns(features: pd.DataFrame) -> int:
    """Count generated columns beyond the base cleaned/event columns."""
    generated_columns = [
        column
        for column in features.columns
        if column
        not in {
            "date",
            "sku_id",
            "quantity_demanded",
            "location_id",
            "channel",
            "sales_value",
            "event_label",
            "notes",
            "is_invalid_quantity",
            "event_names",
            "event_types",
        }
    ]
    return len(generated_columns)


def _prepare_base_frame(demand_with_event_features: pd.DataFrame) -> pd.DataFrame:
    """Sort demand by SKU/date and normalize required fields."""
    prepared = demand_with_event_features.copy()
    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce")
    prepared["sku_id"] = prepared["sku_id"].astype(str).str.strip()
    prepared["quantity_demanded"] = pd.to_numeric(prepared["quantity_demanded"], errors="coerce")
    return prepared.sort_values(["sku_id", "date"]).reset_index(drop=True)


def _build_anomaly_indicator(features: pd.DataFrame) -> pd.Series:
    """Create a row-level anomaly marker from existing Phase 1 signals."""
    invalid_quantity = pd.Series(0, index=features.index)
    event_label_anomaly = pd.Series(False, index=features.index)

    if "is_invalid_quantity" in features.columns:
        invalid_quantity = pd.to_numeric(features["is_invalid_quantity"], errors="coerce").fillna(0)
    if "event_label" in features.columns:
        event_label_anomaly = features["event_label"].fillna("").astype(str).str.lower().eq("anomaly")

    return ((invalid_quantity > 0) | event_label_anomaly).astype(int)
