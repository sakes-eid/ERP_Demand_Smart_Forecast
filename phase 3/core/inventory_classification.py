"""Inventory classification layer for Phase 3."""

from __future__ import annotations

import pandas as pd

from config import (
    ABC_CLASS_THRESHOLDS,
    CLASSIFICATION_SCORE_WEIGHTS,
    FSN_CLASS_THRESHOLDS,
    SEASONALITY_THRESHOLDS,
    SLOW_MOVING_DAYS,
    VITALITY_THRESHOLDS,
    XYZ_CLASS_THRESHOLDS,
)


def build_inventory_classification(planning_context: pd.DataFrame) -> pd.DataFrame:
    """Classify every SKU from the Phase 3 planning context."""
    classified = planning_context.copy()
    classified["selected_unit_cost"] = _selected_unit_cost(classified)
    classified["annual_demand_value"] = (
        _num(classified, "average_daily_demand") * 365 * classified["selected_unit_cost"]
    )
    classified = _add_abc_classification(classified)
    classified["xyz_class"] = classified.apply(_xyz_class, axis=1)
    classified["fsn_class"] = classified.apply(_fsn_class, axis=1)
    classified["movement_class"] = classified.apply(_movement_class, axis=1)
    classified["vitality_class"] = classified.apply(_vitality_class, axis=1)
    classified["seasonality_class"] = classified.apply(_seasonality_class, axis=1)
    classified["perishability_class"] = classified.apply(_perishability_class, axis=1)
    classified["handling_unit_class"] = classified.apply(_handling_unit_class, axis=1)
    classified["supplier_risk_class"] = classified.apply(_supplier_risk_class, axis=1)
    classified["inventory_priority_class"] = classified.apply(_inventory_priority_class, axis=1)
    classified["classification_score"] = classified.apply(_classification_score, axis=1)
    classified["classification_reason"] = classified.apply(_classification_reason, axis=1)
    return classified[_output_columns(classified)]


def _add_abc_classification(df: pd.DataFrame) -> pd.DataFrame:
    """Add ABC rank and cumulative value share."""
    enriched = df.copy()
    enriched = enriched.sort_values("annual_demand_value", ascending=False, na_position="last").reset_index(drop=True)
    total_value = enriched["annual_demand_value"].fillna(0).sum()
    enriched["abc_rank"] = range(1, len(enriched) + 1)
    if total_value > 0:
        enriched["cumulative_demand_value_share"] = enriched["annual_demand_value"].fillna(0).cumsum() / total_value
    else:
        enriched["cumulative_demand_value_share"] = 0.0
    enriched["abc_class"] = enriched["cumulative_demand_value_share"].apply(_abc_from_share)
    zero_value = enriched["annual_demand_value"].fillna(0) <= 0
    important_signal = _num(enriched, "stockout_penalty_per_unit") >= VITALITY_THRESHOLDS["important_stockout_penalty"]
    enriched.loc[zero_value, "abc_class"] = "C"
    enriched.loc[zero_value & important_signal, "abc_class"] = "B"
    return enriched


def _abc_from_share(share: float) -> str:
    """Map cumulative value share to ABC class."""
    if share <= ABC_CLASS_THRESHOLDS["A_cumulative_share"]:
        return "A"
    if share <= ABC_CLASS_THRESHOLDS["B_cumulative_share"]:
        return "B"
    return "C"


def _xyz_class(row: pd.Series) -> str:
    """Classify demand variability."""
    if row.get("phase1_context_status") != "LOADED_FROM_PHASE1":
        return "UNKNOWN"
    behavior = str(row.get("demand_behavior_class", "")).lower()
    cv = _float(row.get("coefficient_of_variation"), 0)
    if behavior == "smooth" or cv <= XYZ_CLASS_THRESHOLDS["X_cv_max"]:
        return "X"
    if behavior == "variable" or cv <= XYZ_CLASS_THRESHOLDS["Y_cv_max"]:
        return "Y"
    return "Z"


def _fsn_class(row: pd.Series) -> str:
    """Classify movement frequency."""
    movement_count = _float(row.get("movement_count"), 0)
    days_since = _float(row.get("days_since_last_movement"), 9999)
    if days_since >= FSN_CLASS_THRESHOLDS["non_moving_days"] or movement_count == 0:
        return "N"
    if movement_count >= FSN_CLASS_THRESHOLDS["fast_movement_count_min"] and days_since < SLOW_MOVING_DAYS:
        return "F"
    return "S"


def _movement_class(row: pd.Series) -> str:
    """Classify movement in readable terms."""
    fsn = row.get("fsn_class")
    movement_count = _float(row.get("movement_count"), 0)
    days_since = _float(row.get("days_since_last_movement"), 9999)
    if fsn == "F":
        return "FAST_MOVING"
    if fsn == "N":
        return "NON_MOVING"
    if movement_count <= FSN_CLASS_THRESHOLDS["slow_movement_count_min"] or days_since >= SLOW_MOVING_DAYS:
        return "SLOW_MOVING"
    return "MEDIUM_MOVING"


def _vitality_class(row: pd.Series) -> str:
    """Classify SKU stockout/customer impact criticality."""
    penalty = _float(row.get("stockout_penalty_per_unit"), 0)
    stockout_units = _float(row.get("stockout_units"), 0)
    avg_demand = _float(row.get("average_daily_demand"), 0)
    stockout_signal = _bool(row.get("stockout_signal"))
    supplier_risk = str(row.get("demand_adjusted_procurement_risk_class", "")).upper()
    supplier_review = _bool(row.get("supplier_review_signal"))
    watchlist = _bool(row.get("watchlist_supplier_signal"))

    if (
        penalty >= VITALITY_THRESHOLDS["vital_stockout_penalty"]
        or (
            stockout_units >= VITALITY_THRESHOLDS["high_stockout_units"]
            and avg_demand >= VITALITY_THRESHOLDS["high_average_daily_demand"]
        )
        or (stockout_signal and penalty >= VITALITY_THRESHOLDS["important_stockout_penalty"])
        or (supplier_risk == "HIGH" and penalty >= VITALITY_THRESHOLDS["important_stockout_penalty"])
    ):
        return "VITAL"
    if (
        penalty >= VITALITY_THRESHOLDS["important_stockout_penalty"]
        or avg_demand >= VITALITY_THRESHOLDS["high_average_daily_demand"]
        or supplier_risk in {"MEDIUM", "HIGH"}
        or supplier_review
        or watchlist
    ):
        return "IMPORTANT"
    return "NORMAL"


def _seasonality_class(row: pd.Series) -> str:
    """Classify seasonal or event-sensitive inventory context."""
    category = str(row.get("category", "")).lower()
    event_ratio = _float(row.get("event_affected_ratio"), 0)
    p50 = _float(row.get("average_p50_forecast"), 0)
    p90 = _float(row.get("average_p90_forecast"), 0)
    current_inventory = _float(row.get("current_inventory"), 0)
    zero_inventory = _bool(row.get("zero_inventory_signal"))
    expiry_risk = _bool(row.get("expiry_risk_signal"))
    seasonal_terms = set(SEASONALITY_THRESHOLDS["seasonal_categories"]) | {"gift", "sun", "bbq", "sun care"}
    seasonal_sensitive = (
        event_ratio >= SEASONALITY_THRESHOLDS["high_event_affected_ratio"]
        or any(term in category for term in seasonal_terms)
    )
    if not seasonal_sensitive:
        return "NON_SEASONAL"
    forecast_reference = max(p50, p90)
    if forecast_reference > current_inventory and (zero_inventory or current_inventory < forecast_reference * 0.8):
        return "SEASONAL_BUILDUP"
    if current_inventory > max(forecast_reference * 2, 1) or expiry_risk:
        return "SEASONAL_DRAWDOWN"
    return "SEASONAL_UNKNOWN"


def _perishability_class(row: pd.Series) -> str:
    """Classify perishability and spoilage risk."""
    if _float(row.get("expired_units"), 0) > 0 or _float(row.get("near_expiry_units"), 0) > 0:
        return "SPOILAGE_RISK"
    if _bool(row.get("expiry_tracking_required")) or _bool(row.get("fefo_required")):
        return "EXPIRY_TRACKED"
    if _bool(row.get("perishable")):
        return "PERISHABLE"
    return "NON_PERISHABLE"


def _handling_unit_class(row: pd.Series) -> str:
    """Classify handling unit."""
    handling_unit = str(row.get("handling_unit", "")).upper()
    if handling_unit in {"PALLET", "CASE", "EACH", "MIXED"}:
        return handling_unit
    return "UNKNOWN"


def _supplier_risk_class(row: pd.Series) -> str:
    """Classify supplier-side planning risk."""
    if _bool(row.get("supplier_review_signal")) or _bool(row.get("watchlist_supplier_signal")):
        return "REVIEW_REQUIRED_SUPPLIER_RISK"
    risk = str(row.get("demand_adjusted_procurement_risk_class", "")).upper()
    if risk == "HIGH":
        return "HIGH_SUPPLIER_RISK"
    if risk == "MEDIUM":
        return "MEDIUM_SUPPLIER_RISK"
    return "LOW_SUPPLIER_RISK"


def _inventory_priority_class(row: pd.Series) -> str:
    """Create an overall inventory priority label."""
    if row.get("vitality_class") == "VITAL" and _bool(row.get("stockout_signal")):
        return "CRITICAL_PRIORITY"
    if (
        row.get("abc_class") == "A" and row.get("fsn_class") == "F"
    ) or row.get("vitality_class") == "VITAL" or (
        row.get("supplier_risk_class") in {"HIGH_SUPPLIER_RISK", "REVIEW_REQUIRED_SUPPLIER_RISK"}
        and _float(row.get("current_inventory"), 0) <= 0
    ):
        return "HIGH_PRIORITY"
    if (
        row.get("perishability_class") == "SPOILAGE_RISK"
        and row.get("movement_class") in {"SLOW_MOVING", "NON_MOVING"}
    ) or _bool(row.get("dead_stock_signal")):
        return "LIQUIDATION_PRIORITY"
    if row.get("abc_class") == "B" or row.get("vitality_class") == "IMPORTANT":
        return "MEDIUM_PRIORITY"
    return "LOW_PRIORITY"


def _classification_score(row: pd.Series) -> float:
    """Calculate a weighted classification score from 0 to 1."""
    score = (
        CLASSIFICATION_SCORE_WEIGHTS["abc"] * {"A": 1.0, "B": 0.6, "C": 0.3}.get(row.get("abc_class"), 0.2)
        + CLASSIFICATION_SCORE_WEIGHTS["xyz"] * {"X": 0.8, "Y": 0.6, "Z": 0.4}.get(row.get("xyz_class"), 0.3)
        + CLASSIFICATION_SCORE_WEIGHTS["fsn"] * {"F": 1.0, "S": 0.5, "N": 0.2}.get(row.get("fsn_class"), 0.2)
        + CLASSIFICATION_SCORE_WEIGHTS["vitality"] * {"VITAL": 1.0, "IMPORTANT": 0.7, "NORMAL": 0.4}.get(row.get("vitality_class"), 0.4)
        + CLASSIFICATION_SCORE_WEIGHTS["perishability"] * _perishability_score(row.get("perishability_class"))
        + CLASSIFICATION_SCORE_WEIGHTS["supplier_risk"] * _supplier_risk_score(row.get("supplier_risk_class"))
    )
    if _bool(row.get("stockout_signal")):
        score += 0.05
    if row.get("inventory_priority_class") == "LIQUIDATION_PRIORITY":
        score -= 0.10
    return round(max(0.0, min(1.0, score)), 4)


def _classification_reason(row: pd.Series) -> str:
    """Create readable classification reason text."""
    parts = []
    if row.get("inventory_priority_class") == "CRITICAL_PRIORITY":
        parts.append("Vital SKU with stockout signal.")
    elif row.get("inventory_priority_class") == "LIQUIDATION_PRIORITY":
        parts.append("C-class or slow/non-moving SKU with expiry or dead-stock risk.")
    elif row.get("abc_class") == "A" and row.get("fsn_class") == "F":
        parts.append("A-class fast-moving SKU.")
    elif row.get("vitality_class") == "VITAL":
        parts.append("Vital SKU due to stockout/customer impact.")
    elif row.get("xyz_class") in {"Y", "Z"}:
        parts.append(f"{row.get('demand_behavior_class')} demand SKU with {row.get('supplier_risk_class').lower().replace('_', ' ')}.")
    if row.get("seasonality_class") in {"SEASONAL_BUILDUP", "SEASONAL_DRAWDOWN", "SEASONAL_UNKNOWN"}:
        parts.append(f"Seasonal context: {row.get('seasonality_class').lower().replace('_', ' ')}.")
    if row.get("perishability_class") == "SPOILAGE_RISK":
        parts.append("Expiry risk requires review.")
    if row.get("supplier_risk_class") == "REVIEW_REQUIRED_SUPPLIER_RISK":
        parts.append("Supplier review or watchlist signal is present.")
    if not parts:
        parts.append("Normal inventory classification with no dominant risk signal.")
    return " ".join(parts)


def _perishability_score(perishability_class: str) -> float:
    """Score perishability for protection, not holding encouragement."""
    return {
        "NON_PERISHABLE": 0.5,
        "PERISHABLE": 0.6,
        "EXPIRY_TRACKED": 0.65,
        "SPOILAGE_RISK": 0.45,
    }.get(perishability_class, 0.5)


def _supplier_risk_score(supplier_risk_class: str) -> float:
    """Score supplier risk for planning attention."""
    return {
        "LOW_SUPPLIER_RISK": 0.3,
        "MEDIUM_SUPPLIER_RISK": 0.6,
        "HIGH_SUPPLIER_RISK": 0.85,
        "REVIEW_REQUIRED_SUPPLIER_RISK": 1.0,
    }.get(supplier_risk_class, 0.5)


def _selected_unit_cost(df: pd.DataFrame) -> pd.Series:
    """Use procurement unit cost when available, otherwise inventory unit cost."""
    procurement = _num(df, "unit_cost_procurement")
    inventory = _num(df, "unit_cost_inventory")
    return procurement.where(procurement > 0, inventory).fillna(0)


def _num(df: pd.DataFrame, column: str) -> pd.Series:
    """Return numeric column or zero series."""
    if column not in df.columns:
        return pd.Series(0, index=df.index)
    return pd.to_numeric(df[column], errors="coerce").fillna(0)


def _float(value, default: float = 0.0) -> float:
    """Safely convert scalar to float."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value) -> bool:
    """Safely convert scalar to bool."""
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def _output_columns(df: pd.DataFrame) -> list[str]:
    """Return ordered output columns while preserving support fields."""
    priority = [
        "sku_id",
        "product_name",
        "category",
        "abc_class",
        "abc_rank",
        "annual_demand_value",
        "cumulative_demand_value_share",
        "xyz_class",
        "fsn_class",
        "vitality_class",
        "seasonality_class",
        "perishability_class",
        "handling_unit_class",
        "movement_class",
        "supplier_risk_class",
        "inventory_priority_class",
        "classification_score",
        "classification_reason",
        "average_daily_demand",
        "coefficient_of_variation",
        "demand_behavior_class",
        "total_demand",
        "unit_cost_inventory",
        "unit_cost_procurement",
        "stockout_penalty_per_unit",
        "stockout_units",
        "current_inventory",
        "movement_count",
        "days_since_last_movement",
        "perishable",
        "expiry_tracking_required",
        "fefo_required",
        "near_expiry_units",
        "expired_units",
        "demand_adjusted_procurement_risk_class",
        "supplier_review_signal",
        "watchlist_supplier_signal",
        "units_per_case",
        "cases_per_pallet",
        "handling_cost_per_unit",
        "handling_cost_per_case",
        "handling_cost_per_pallet",
    ]
    return [column for column in priority if column in df.columns]
