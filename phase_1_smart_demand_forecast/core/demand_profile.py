"""SKU-level demand profiling from cleaned, event-enriched demand data."""

import pandas as pd

PROFILE_COLUMNS = [
    "sku_id",
    "total_demand",
    "average_daily_demand",
    "median_daily_demand",
    "std_demand",
    "min_demand",
    "max_demand",
    "coefficient_of_variation",
    "zero_demand_days",
    "zero_demand_ratio",
    "active_days",
    "event_affected_days",
    "event_affected_ratio",
    "promotion_days",
    "holiday_days",
    "anomaly_days",
    "demand_behavior_class",
    "data_sufficiency_class",
]


def build_demand_profile(demand_with_event_features: pd.DataFrame) -> pd.DataFrame:
    """Create one demand profile row per SKU."""
    prepared = _prepare_demand(demand_with_event_features)
    profile_rows = [_profile_sku(sku_id, sku_demand) for sku_id, sku_demand in prepared.groupby("sku_id")]
    return pd.DataFrame(profile_rows, columns=PROFILE_COLUMNS)


def _prepare_demand(demand: pd.DataFrame) -> pd.DataFrame:
    """Normalize required numeric columns for profiling."""
    prepared = demand.copy()
    prepared["sku_id"] = prepared["sku_id"].astype(str).str.strip()
    prepared["quantity_demanded"] = pd.to_numeric(prepared["quantity_demanded"], errors="coerce").fillna(0)

    for column in ("has_event", "promotion_flag", "holiday_flag", "is_invalid_quantity"):
        if column not in prepared.columns:
            prepared[column] = 0
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce").fillna(0)

    return prepared


def _profile_sku(sku_id: str, sku_demand: pd.DataFrame) -> dict[str, object]:
    """Calculate all profile metrics for a single SKU."""
    demand_values = sku_demand["quantity_demanded"]
    active_days = len(sku_demand)
    average_daily_demand = demand_values.mean()
    std_demand = demand_values.std()
    coefficient_of_variation = _coefficient_of_variation(average_daily_demand, std_demand)
    zero_demand_days = int((demand_values == 0).sum())
    zero_demand_ratio = _safe_ratio(zero_demand_days, active_days)
    event_affected_days = int((sku_demand["has_event"] > 0).sum())

    return {
        "sku_id": sku_id,
        "total_demand": demand_values.sum(),
        "average_daily_demand": average_daily_demand,
        "median_daily_demand": demand_values.median(),
        "std_demand": std_demand,
        "min_demand": demand_values.min(),
        "max_demand": demand_values.max(),
        "coefficient_of_variation": coefficient_of_variation,
        "zero_demand_days": zero_demand_days,
        "zero_demand_ratio": zero_demand_ratio,
        "active_days": active_days,
        "event_affected_days": event_affected_days,
        "event_affected_ratio": _safe_ratio(event_affected_days, active_days),
        "promotion_days": int((sku_demand["promotion_flag"] > 0).sum()),
        "holiday_days": int((sku_demand["holiday_flag"] > 0).sum()),
        "anomaly_days": _count_anomaly_days(sku_demand),
        "demand_behavior_class": _classify_demand_behavior(coefficient_of_variation, zero_demand_ratio),
        "data_sufficiency_class": _classify_data_sufficiency(active_days),
    }


def _coefficient_of_variation(mean: float, std: float) -> float:
    """Return standard deviation divided by mean demand."""
    if pd.isna(mean) or mean == 0 or pd.isna(std):
        return 0.0
    return float(std / mean)


def _safe_ratio(numerator: int, denominator: int) -> float:
    """Return a ratio while avoiding division by zero."""
    if denominator == 0:
        return 0.0
    return float(numerator / denominator)


def _count_anomaly_days(sku_demand: pd.DataFrame) -> int:
    """Count invalid quantity rows and simple statistical outlier rows."""
    demand_values = sku_demand["quantity_demanded"]
    invalid_mask = sku_demand["is_invalid_quantity"] > 0
    std_demand = demand_values.std()

    if pd.isna(std_demand) or std_demand == 0:
        outlier_mask = pd.Series(False, index=sku_demand.index)
    else:
        z_scores = (demand_values - demand_values.mean()) / std_demand
        outlier_mask = z_scores.abs() >= 3

    return int((invalid_mask | outlier_mask).sum())


def _classify_demand_behavior(coefficient_of_variation: float, zero_demand_ratio: float) -> str:
    """Classify SKU demand behavior using simple profiling rules."""
    if zero_demand_ratio >= 0.30:
        return "intermittent"
    if coefficient_of_variation >= 1.00:
        return "erratic"
    if coefficient_of_variation < 0.50 and zero_demand_ratio < 0.10:
        return "smooth"
    return "variable"


def _classify_data_sufficiency(active_days: int) -> str:
    """Classify how much demand history is available for a SKU."""
    if active_days < 60:
        return "low"
    if active_days < 180:
        return "medium"
    return "high"
