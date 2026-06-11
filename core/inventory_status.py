"""Inventory status and action signal layer for Phase 3 Step 7."""

from __future__ import annotations

import pandas as pd

from config import INVENTORY_STATUS_THRESHOLDS


def build_inventory_status(
    inventory_policy: pd.DataFrame,
    inventory_policy_parameters: pd.DataFrame,
    planning_context: pd.DataFrame,
    inventory_classification: pd.DataFrame,
    inventory_service_levels: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create inventory status and action recommendation rows per SKU."""
    status_input = _build_status_input(
        inventory_policy,
        inventory_policy_parameters,
        planning_context,
        inventory_classification,
        inventory_service_levels,
    )
    rows = []
    for _, row in status_input.iterrows():
        result = row.to_dict()
        metrics = _status_metrics(row)
        consistency_flag, consistency_reason = _parameter_consistency(row)
        main_status = _main_inventory_status(row, metrics, consistency_flag)
        secondary_flags = _secondary_flags(row, metrics, consistency_flag)
        primary_action, secondary_action, priority, reason = _actions(
            row,
            main_status,
            secondary_flags,
            consistency_flag,
            consistency_reason,
        )
        result.update(metrics)
        result["parameter_consistency_flag"] = consistency_flag
        result["parameter_consistency_reason"] = consistency_reason
        result["main_inventory_status"] = main_status
        result["secondary_status_flags"] = ";".join(secondary_flags)
        result["primary_action"] = primary_action
        result["secondary_action"] = secondary_action
        result["action_priority"] = priority
        result["action_reason"] = reason
        rows.append(result)

    status_df = pd.DataFrame(rows)
    status_df = status_df[_status_output_columns(status_df)]
    action_df = status_df[_action_output_columns(status_df)].copy()
    return status_df, action_df


def _build_status_input(
    inventory_policy: pd.DataFrame,
    inventory_policy_parameters: pd.DataFrame,
    planning_context: pd.DataFrame,
    inventory_classification: pd.DataFrame,
    inventory_service_levels: pd.DataFrame,
) -> pd.DataFrame:
    """Start from parameter output and merge missing context columns."""
    merged = inventory_policy_parameters.copy()
    for supplement in [
        inventory_policy,
        planning_context,
        inventory_classification,
        inventory_service_levels,
    ]:
        merged = _merge_missing_columns(merged, supplement)
    return merged


def _merge_missing_columns(base: pd.DataFrame, supplement: pd.DataFrame) -> pd.DataFrame:
    """Merge columns that are missing from base, keyed by sku_id."""
    if base.empty or supplement.empty or "sku_id" not in base.columns or "sku_id" not in supplement.columns:
        return base
    missing_columns = [column for column in supplement.columns if column not in base.columns]
    if not missing_columns:
        return base
    return base.merge(supplement[["sku_id", *missing_columns]], on="sku_id", how="left")


def _status_metrics(row: pd.Series) -> dict:
    """Calculate days of supply and reorder/overstock thresholds."""
    average_daily_demand = _float(row.get("average_daily_demand"))
    inventory_position = _float(row.get("inventory_position"), default=float("nan"))
    recommended_order_quantity = _float(row.get("recommended_order_quantity"))
    reorder_point = _float(row.get("reorder_point"), default=float("nan"))
    max_stock_level = _float(row.get("max_stock_level"), default=float("nan"))

    if average_daily_demand > 0:
        days_current = max(inventory_position, 0) / average_daily_demand if not pd.isna(inventory_position) else float("nan")
        days_after = (
            max(inventory_position, 0) + max(recommended_order_quantity, 0)
        ) / average_daily_demand if not pd.isna(inventory_position) else float("nan")
    else:
        days_current = 999999 if _float(row.get("inventory_position")) > 0 else 0
        days_after = 999999 if (_float(row.get("inventory_position")) + recommended_order_quantity) > 0 else 0

    buffer = max(
        average_daily_demand * INVENTORY_STATUS_THRESHOLDS["approaching_reorder_warning_days"],
        _safe_number(reorder_point) * INVENTORY_STATUS_THRESHOLDS["approaching_reorder_warning_pct"],
    )
    approaching_threshold = _safe_number(reorder_point) + buffer
    overstock_days_threshold = _overstock_days_threshold(row)
    return {
        "days_of_supply_current": round(days_current, 2) if not pd.isna(days_current) else pd.NA,
        "days_of_supply_after_recommended_order": round(days_after, 2) if not pd.isna(days_after) else pd.NA,
        "approaching_reorder_warning_buffer": round(buffer, 2),
        "approaching_reorder_threshold": round(approaching_threshold, 2),
        "overstock_days_of_supply_threshold": overstock_days_threshold,
        "_inventory_position_value": inventory_position,
        "_reorder_point_value": reorder_point,
        "_max_stock_level_value": max_stock_level,
    }


def _parameter_consistency(row: pd.Series) -> tuple[bool, str]:
    """Check parameter consistency without crashing on missing fields."""
    reasons = []
    safety_stock = _float(row.get("safety_stock"), default=float("nan"))
    reorder_point = _float(row.get("reorder_point"), default=float("nan"))
    max_stock_level = _float(row.get("max_stock_level"), default=float("nan"))
    min_stock_level = _float(row.get("min_stock_level"), default=float("nan"))
    recommended_order_quantity = _float(row.get("recommended_order_quantity"), default=float("nan"))
    inventory_position = _float(row.get("inventory_position"), default=float("nan"))

    required = {
        "inventory_position": inventory_position,
        "reorder_point": reorder_point,
        "max_stock_level": max_stock_level,
    }
    for name, value in required.items():
        if pd.isna(value):
            reasons.append(f"{name} is missing.")
    no_order_above_reorder = (
        _bool(row.get("no_order_recommended_flag"))
        and not pd.isna(inventory_position)
        and not pd.isna(reorder_point)
        and inventory_position > reorder_point
    )
    if (
        not pd.isna(max_stock_level)
        and not pd.isna(reorder_point)
        and max_stock_level < reorder_point
        and not no_order_above_reorder
    ):
        reasons.append("max_stock_level is below reorder_point.")
    if not pd.isna(min_stock_level) and not pd.isna(max_stock_level) and min_stock_level > max_stock_level:
        reasons.append("min_stock_level is above max_stock_level.")
    if not pd.isna(safety_stock) and not pd.isna(reorder_point) and safety_stock > reorder_point:
        reasons.append("safety_stock is above reorder_point.")
    for name, value in {
        "recommended_order_quantity": recommended_order_quantity,
        "safety_stock": safety_stock,
        "reorder_point": reorder_point,
        "max_stock_level": max_stock_level,
    }.items():
        if pd.isna(value):
            reasons.append(f"{name} is missing.")
        elif value < 0:
            reasons.append(f"{name} is negative.")
    if reasons:
        return True, " ".join(reasons)
    return False, "Inventory policy parameters are internally consistent."


def _main_inventory_status(row: pd.Series, metrics: dict, consistency_flag: bool) -> str:
    """Classify main status from current position versus policy parameters."""
    if consistency_flag or pd.isna(metrics["_inventory_position_value"]) or pd.isna(metrics["_reorder_point_value"]):
        return "UNKNOWN_STATUS"
    current_inventory = _float(row.get("current_inventory"))
    available_inventory = _float(row.get("available_inventory"))
    inventory_position = metrics["_inventory_position_value"]
    safety_stock = _float(row.get("safety_stock"))
    reorder_point = metrics["_reorder_point_value"]
    approaching_threshold = _float(metrics["approaching_reorder_threshold"])
    max_stock_level = metrics["_max_stock_level_value"]
    days_current = _float(metrics["days_of_supply_current"])

    if current_inventory < 0 or available_inventory < 0 or _bool(row.get("stockout_signal")):
        return "STOCKOUT"
    if current_inventory == 0 or available_inventory == 0 or _bool(row.get("zero_inventory_signal")):
        return "ZERO_STOCK"
    if inventory_position <= safety_stock:
        return "CRITICAL_LOW_STOCK"
    if inventory_position <= reorder_point:
        return "REORDER_NOW"
    if inventory_position <= approaching_threshold:
        return "APPROACHING_REORDER_POINT"
    if not pd.isna(max_stock_level) and inventory_position > max_stock_level:
        return "OVERSTOCK"
    if _severe_days_of_supply_overstock(row, days_current):
        return "OVERSTOCK"
    return "HEALTHY"


def _secondary_flags(row: pd.Series, metrics: dict, consistency_flag: bool) -> list[str]:
    """Build semicolon-friendly secondary flags."""
    flags = []
    days_current = _float(metrics["days_of_supply_current"])
    warning_codes = str(row.get("warning_codes", ""))
    if _float(row.get("near_expiry_units")) > 0:
        flags.append("NEAR_EXPIRY")
    if _float(row.get("expired_units")) > 0:
        flags.append("EXPIRED_STOCK")
    if row.get("perishability_class") == "SPOILAGE_RISK" or _bool(row.get("expiry_risk_signal")):
        flags.append("SPOILAGE_RISK")
    if _bool(row.get("non_moving_signal")) or row.get("movement_class") == "NON_MOVING":
        flags.append("NON_MOVING")
    if _bool(row.get("dead_stock_signal")):
        flags.append("DEAD_STOCK")
    if (
        _bool(row.get("supplier_review_signal"))
        or _bool(row.get("recommended_supplier_requires_review"))
        or _bool(row.get("supplier_review_before_order"))
    ):
        flags.append("SUPPLIER_REVIEW_REQUIRED")
    if _bool(row.get("watchlist_supplier_signal")):
        flags.append("WATCHLIST_SUPPLIER")
    if _bool(row.get("phase4_review_flag")) or _bool(row.get("phase4_review_before_final_policy")):
        flags.append("PHASE4_REVIEW_REQUIRED")
    if _bool(row.get("policy_review_required")):
        flags.append("POLICY_REVIEW_REQUIRED")
    if _bool(row.get("quantity_constraint_flag")):
        flags.append("QUANTITY_CONSTRAINT_ACTIVE")
    if _bool(row.get("no_order_recommended_flag")) or _bool(row.get("no_order_event_based")) or _bool(row.get("no_order_one_to_one")):
        flags.append("NO_ORDER_RECOMMENDED")
    if _bool(row.get("existing_inventory_cap_applied")):
        flags.append("EXISTING_INVENTORY_CAP_ACTIVE")
    if "HIGH_MOQ_MAY_CAUSE_OVERSTOCK" in warning_codes:
        flags.append("HIGH_MOQ_OVERSTOCK_RISK")
    if days_current > _float(metrics["overstock_days_of_supply_threshold"]):
        flags.append("OVERSTOCK_RISK_BY_DAYS_OF_SUPPLY")
    if consistency_flag:
        flags.append("PARAMETER_INCONSISTENCY")
    return _unique(flags)


def _actions(
    row: pd.Series,
    main_status: str,
    secondary_flags: list[str],
    consistency_flag: bool,
    consistency_reason: str,
) -> tuple[str, str, str, str]:
    """Recommend primary and secondary action from status and flags."""
    recommended_quantity = _float(row.get("recommended_order_quantity"))
    supplier_review = "SUPPLIER_REVIEW_REQUIRED" in secondary_flags or "WATCHLIST_SUPPLIER" in secondary_flags
    expired = "EXPIRED_STOCK" in secondary_flags
    near_expiry = "NEAR_EXPIRY" in secondary_flags
    phase4 = "PHASE4_REVIEW_REQUIRED" in secondary_flags
    no_order = "NO_ORDER_RECOMMENDED" in secondary_flags

    if consistency_flag:
        return "REVIEW_POLICY_PARAMETERS", "NO_ACTION", "HIGH", f"Policy parameters are inconsistent: {consistency_reason}"
    if main_status == "STOCKOUT":
        if row.get("inventory_priority_class") == "CRITICAL_PRIORITY" or row.get("vitality_class") == "VITAL":
            reason = "Stockout on critical or vital SKU requires urgent recovery."
            if supplier_review:
                reason += " Supplier review/watchlist signal is active, so use the fastest reliable approved path."
            return "EXPEDITE_ORDER", "USE_FAST_RELIABLE_SUPPLIER", "URGENT", reason
        if supplier_review:
            return (
                "REVIEW_SUPPLIER_BEFORE_ORDER",
                "ORDER_RECOMMENDED_QUANTITY",
                "HIGH",
                "Stockout exists but supplier review is required before placing the recommended order.",
            )
        return "ORDER_RECOMMENDED_QUANTITY", "NO_ACTION", "HIGH", "Stockout exists; order the recommended quantity."
    if main_status == "ZERO_STOCK":
        if recommended_quantity > 0:
            return "ORDER_RECOMMENDED_QUANTITY", "NO_ACTION", "HIGH", "Zero stock exists and a recommended order quantity is available."
        return "REVIEW_POLICY_PARAMETERS", "NO_ACTION", "HIGH", "Zero stock exists but no order quantity was recommended."
    if main_status == "CRITICAL_LOW_STOCK":
        if recommended_quantity > 0:
            return "ORDER_RECOMMENDED_QUANTITY", "NO_ACTION", "HIGH", "Inventory position is at or below safety stock."
        return "MONITOR_CLOSELY", "REVIEW_POLICY_PARAMETERS", "MEDIUM", "Inventory is critically low but no order quantity was recommended."
    if main_status == "REORDER_NOW":
        if supplier_review:
            return (
                "REVIEW_SUPPLIER_BEFORE_ORDER",
                "ORDER_RECOMMENDED_QUANTITY",
                "HIGH",
                "Inventory is at or below reorder point and supplier review is required before ordering.",
            )
        return "ORDER_RECOMMENDED_QUANTITY", "NO_ACTION", "HIGH", "Inventory position is at or below reorder point."
    if main_status == "APPROACHING_REORDER_POINT":
        return "MONITOR_CLOSELY", "NO_ACTION", "MEDIUM", "Inventory is approaching reorder point using the configured warning buffer."
    if main_status == "OVERSTOCK":
        secondary_action = _expiry_or_return_action(row, secondary_flags)
        priority = "HIGH" if expired or near_expiry or "SPOILAGE_RISK" in secondary_flags else "MEDIUM"
        return "REDUCE_FUTURE_ORDERS", secondary_action, priority, "Inventory exceeds max stock or days-of-supply threshold."
    if main_status == "HEALTHY":
        return _healthy_action(row, secondary_flags, no_order, phase4, expired, near_expiry)
    return "REVIEW_POLICY_PARAMETERS", "NO_ACTION", "MEDIUM", "Inventory status could not be determined from available parameters."


def _healthy_action(
    row: pd.Series,
    secondary_flags: list[str],
    no_order: bool,
    phase4: bool,
    expired: bool,
    near_expiry: bool,
) -> tuple[str, str, str, str]:
    """Choose action for healthy inventory with optional secondary risks."""
    if expired:
        return "SCRAP_OR_QUARANTINE_EXPIRED", "REDUCE_FUTURE_ORDERS", "HIGH", "Inventory is otherwise healthy, but expired stock requires quarantine or scrap."
    if near_expiry:
        return "PRIORITIZE_FEFO_PICKING", _expiry_or_return_action(row, secondary_flags), "MEDIUM", "Inventory is healthy, but near-expiry stock should be consumed first."
    if "DEAD_STOCK" in secondary_flags:
        return "LIQUIDATE_DEAD_STOCK", "REVIEW_POLICY_PARAMETERS", "MEDIUM", "Inventory is not below reorder point, but dead-stock signal requires action."
    if "NON_MOVING" in secondary_flags:
        return "LIQUIDATE_DEAD_STOCK", "REVIEW_POLICY_PARAMETERS", "LOW", "Inventory is healthy by policy position, but non-moving stock should be reviewed."
    if no_order:
        return "WAIT_FOR_TRIGGER", "NO_ACTION", "LOW", "No order is recommended because no event or replacement trigger is active."
    if "SUPPLIER_REVIEW_REQUIRED" in secondary_flags:
        return "REVIEW_SUPPLIER_BEFORE_ORDER", "NO_ACTION", "LOW", "Inventory is healthy, but supplier review remains open before future orders."
    if phase4:
        return "REVIEW_PHASE4_PRODUCTION_LOGIC", "NO_ACTION", "LOW", "Inventory is healthy, but Phase 4 production/BOM/MRP logic may later override policy."
    if secondary_flags:
        return "MONITOR_CLOSELY", "NO_ACTION", "LOW", "Inventory is healthy with secondary flags that should be monitored."
    return "NO_ACTION", "NO_ACTION", "NO_ACTION", "Inventory is healthy and no immediate action is required."


def _expiry_or_return_action(row: pd.Series, secondary_flags: list[str]) -> str:
    """Choose expiry, markdown, return, or no secondary action."""
    if "EXPIRED_STOCK" in secondary_flags:
        return "SCRAP_OR_QUARANTINE_EXPIRED"
    if "NEAR_EXPIRY" in secondary_flags or "SPOILAGE_RISK" in secondary_flags:
        if _bool(row.get("supplier_accepts_returns")) and _float(row.get("return_window_days")) > 0:
            return "RETURN_TO_SUPPLIER_IF_ALLOWED"
        return "MARKDOWN_NEAR_EXPIRY"
    if "DEAD_STOCK" in secondary_flags or "NON_MOVING" in secondary_flags:
        return "LIQUIDATE_DEAD_STOCK"
    return "NO_ACTION"


def _severe_days_of_supply_overstock(row: pd.Series, days_current: float) -> bool:
    """Allow days-of-supply overstock to drive main overstock for special cases."""
    special = (
        row.get("perishability_class") == "SPOILAGE_RISK"
        or row.get("seasonality_class") == "SEASONAL_DRAWDOWN"
        or row.get("movement_class") == "NON_MOVING"
        or row.get("inventory_priority_class") == "LOW_PRIORITY"
        or _bool(row.get("perishable"))
    )
    return bool(special and days_current > _overstock_days_threshold(row))


def _overstock_days_threshold(row: pd.Series) -> int:
    """Select days-of-supply threshold by SKU risk type."""
    threshold = INVENTORY_STATUS_THRESHOLDS["default_overstock_days_of_supply"]
    if row.get("perishability_class") == "SPOILAGE_RISK":
        threshold = INVENTORY_STATUS_THRESHOLDS["spoilage_risk_overstock_days_of_supply"]
    elif row.get("seasonality_class") == "SEASONAL_DRAWDOWN":
        threshold = INVENTORY_STATUS_THRESHOLDS["seasonal_drawdown_overstock_days_of_supply"]
    elif row.get("movement_class") == "NON_MOVING":
        threshold = INVENTORY_STATUS_THRESHOLDS["non_moving_overstock_days_of_supply"]
    elif row.get("inventory_priority_class") == "LOW_PRIORITY":
        threshold = INVENTORY_STATUS_THRESHOLDS["low_priority_overstock_days_of_supply"]
    elif row.get("perishability_class") in {"EXPIRY_TRACKED", "PERISHABLE"} or _bool(row.get("perishable")):
        threshold = INVENTORY_STATUS_THRESHOLDS["perishable_overstock_days_of_supply"]
    return threshold


def _status_output_columns(df: pd.DataFrame) -> list[str]:
    """Return ordered columns for inventory_status.csv."""
    columns = [
        "sku_id",
        "product_name",
        "category",
        "main_inventory_status",
        "secondary_status_flags",
        "primary_action",
        "secondary_action",
        "action_priority",
        "action_reason",
        "current_inventory",
        "available_inventory",
        "inventory_position",
        "safety_stock",
        "reorder_point",
        "recommended_order_quantity",
        "min_stock_level",
        "max_stock_level",
        "reorder_point_s",
        "order_quantity_Q",
        "review_period_R",
        "order_up_to_level_S",
        "base_stock_level",
        "inventory_model_type",
        "review_policy",
        "policy_urgency",
        "policy_review_required",
        "policy_review_reason",
        "quantity_constraint_flag",
        "quantity_constraint_reason",
        "warning_codes",
        "abc_class",
        "xyz_class",
        "fsn_class",
        "vitality_class",
        "seasonality_class",
        "perishability_class",
        "movement_class",
        "supplier_risk_class",
        "inventory_priority_class",
        "service_level_target",
        "safety_factor_z",
        "stockout_signal",
        "stockout_units",
        "zero_inventory_signal",
        "expiry_risk_signal",
        "near_expiry_units",
        "expired_units",
        "non_moving_signal",
        "dead_stock_signal",
        "supplier_review_signal",
        "watchlist_supplier_signal",
        "recommended_supplier_requires_review",
        "supplier_review_before_order",
        "phase4_review_flag",
        "phase4_review_before_final_policy",
        "no_order_recommended_flag",
        "no_order_event_based",
        "no_order_one_to_one",
        "existing_inventory_cap_applied",
        "recommended_supplier_id",
        "backup_supplier_id",
        "recommended_supplier_feasible",
        "supplier_accepts_returns",
        "return_window_days",
        "return_deduction_rate",
        "return_transport_cost",
        "return_policy_status",
        "days_of_supply_current",
        "days_of_supply_after_recommended_order",
        "approaching_reorder_threshold",
        "approaching_reorder_warning_buffer",
        "overstock_days_of_supply_threshold",
        "parameter_consistency_flag",
        "parameter_consistency_reason",
    ]
    return [column for column in columns if column in df.columns]


def _action_output_columns(df: pd.DataFrame) -> list[str]:
    """Return focused action recommendation columns."""
    columns = [
        "sku_id",
        "product_name",
        "category",
        "main_inventory_status",
        "secondary_status_flags",
        "primary_action",
        "secondary_action",
        "action_priority",
        "action_reason",
        "recommended_order_quantity",
        "recommended_supplier_id",
        "backup_supplier_id",
        "supplier_review_signal",
        "watchlist_supplier_signal",
        "phase4_review_flag",
        "quantity_constraint_flag",
        "warning_codes",
    ]
    return [column for column in columns if column in df.columns]


def _safe_number(value: float) -> float:
    """Return zero for NaN values."""
    return 0.0 if pd.isna(value) else value


def _float(value, default: float = 0.0) -> float:
    """Safely convert scalar values to float."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value) -> bool:
    """Safely convert scalar values to boolean."""
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def _unique(values: list[str]) -> list[str]:
    """Return unique values preserving order."""
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
