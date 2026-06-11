"""Inventory cost visibility layer for Phase 3 Step 8."""

from __future__ import annotations

import pandas as pd

from config import (
    DEFAULT_OVERSTOCK_PENALTY_PER_UNIT,
    DEFAULT_STOCKOUT_PENALTY_PER_UNIT,
    HOLDING_COST_COMPONENTS,
    INVENTORY_COST_DEFAULTS,
    INVENTORY_COST_RISK_THRESHOLDS,
    INVENTORY_STATUS_THRESHOLDS,
)


def build_inventory_costs(
    inventory_policy: pd.DataFrame,
    inventory_policy_parameters: pd.DataFrame,
    inventory_status: pd.DataFrame,
    inventory_action_recommendations: pd.DataFrame,
    planning_context: pd.DataFrame,
    inventory_classification: pd.DataFrame,
    inventory_service_levels: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build SKU-level inventory cost exposure and grouped cost summaries."""
    cost_input = _build_cost_input(
        inventory_policy,
        inventory_policy_parameters,
        inventory_status,
        inventory_action_recommendations,
        planning_context,
        inventory_classification,
        inventory_service_levels,
    )
    rows = []
    for _, row in cost_input.iterrows():
        result = row.to_dict()
        result.update(_calculate_costs(row))
        rows.append(result)

    costs_df = pd.DataFrame(rows)
    costs_df = _ensure_columns(costs_df, _cost_output_columns())
    costs_df = costs_df[_cost_output_columns()]
    summary_df = _build_cost_summary(costs_df)
    return costs_df, summary_df


def _build_cost_input(
    inventory_policy: pd.DataFrame,
    inventory_policy_parameters: pd.DataFrame,
    inventory_status: pd.DataFrame,
    inventory_action_recommendations: pd.DataFrame,
    planning_context: pd.DataFrame,
    inventory_classification: pd.DataFrame,
    inventory_service_levels: pd.DataFrame,
) -> pd.DataFrame:
    """Start from status output and merge missing policy, parameter, and context fields."""
    merged = inventory_status.copy()
    for supplement in [
        inventory_action_recommendations,
        inventory_policy_parameters,
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


def _calculate_costs(row: pd.Series) -> dict:
    """Calculate current, recommended-action, projected, and risk-adjusted cost fields."""
    warnings: list[str] = []
    reason_parts: list[str] = []

    selected_unit_cost, selected_unit_cost_fallback = _selected_unit_cost(row)
    if selected_unit_cost_fallback:
        warnings.append("COST_USES_FALLBACKS")
        reason_parts.append("Unit cost fallback was used.")

    holding_rate = sum(HOLDING_COST_COMPONENTS.values())
    current_inventory = _float(row.get("current_inventory"))
    available_inventory = _float(row.get("available_inventory"))
    inventory_position = _float(row.get("inventory_position"))
    recommended_order_quantity = max(_float(row.get("recommended_order_quantity")), 0.0)
    effective_order_quantity = _effective_order_quantity_for_action(
        row,
        recommended_order_quantity,
        warnings,
        reason_parts,
    )
    average_daily_demand = max(_float(row.get("average_daily_demand")), 0.0)
    movement_count = max(_float(row.get("movement_count")), 0.0)
    unit_volume = _positive_or_default(row.get("unit_volume_m3"), INVENTORY_COST_DEFAULTS["fallback_unit_volume_m3"], warnings)
    storage_cost_per_m3 = _positive_or_default(
        row.get("storage_cost_per_m3"),
        INVENTORY_COST_DEFAULTS["fallback_storage_cost_per_m3"],
        warnings,
    )
    handling_cost_per_unit = _positive_or_default(
        row.get("handling_cost_per_unit"),
        INVENTORY_COST_DEFAULTS["fallback_handling_cost_per_unit"],
        warnings,
    )

    current_inventory_value = _current_inventory_value(row, current_inventory, selected_unit_cost)
    current_holding_cost = current_inventory_value * holding_rate
    storage_space_cost = max(current_inventory, 0.0) * unit_volume * storage_cost_per_m3
    handling_cost = _handling_cost(row, movement_count, recommended_order_quantity, current_inventory, handling_cost_per_unit)

    stockout_units, stockout_estimated = _stockout_units(row, current_inventory, available_inventory)
    if stockout_estimated:
        warnings.append("STOCKOUT_UNITS_ESTIMATED")
    stockout_penalty = _positive_or_default(
        row.get("stockout_penalty_per_unit"),
        DEFAULT_STOCKOUT_PENALTY_PER_UNIT,
        warnings,
    )
    current_stockout_cost = stockout_units * stockout_penalty
    expected_stockout_risk_cost = _expected_stockout_risk_cost(row, stockout_penalty, average_daily_demand)
    if current_stockout_cost > 0:
        warnings.append("CURRENT_STOCKOUT_COST_ACTIVE")
        reason_parts.append("Current stockout cost is active.")
    if expected_stockout_risk_cost > 0:
        warnings.append("EXPECTED_STOCKOUT_RISK_ACTIVE")
        warnings.append("STOCKOUT_DURATION_UNKNOWN")

    overstock_penalty = _positive_or_default(
        row.get("overstock_penalty_per_unit"),
        DEFAULT_OVERSTOCK_PENALTY_PER_UNIT,
        warnings,
    )
    overstock_units, overstock_reason = _overstock_details(
        row,
        max(inventory_position, current_inventory, 0.0),
        average_daily_demand,
    )
    current_overstock_cost = overstock_units * overstock_penalty
    if current_overstock_cost > 0:
        warnings.append("OVERSTOCK_COST_ACTIVE")
        reason_parts.append(overstock_reason)

    expired_units = max(_float(row.get("expired_units")), 0.0)
    near_expiry_units = max(_float(row.get("near_expiry_units")), 0.0)
    expired_stock_cost = expired_units * selected_unit_cost * INVENTORY_COST_DEFAULTS["fallback_scrap_loss_rate"]
    near_expiry_risk_cost = near_expiry_units * selected_unit_cost * INVENTORY_COST_DEFAULTS["fallback_markdown_loss_rate"]
    if expired_stock_cost > 0 or near_expiry_risk_cost > 0:
        warnings.append("EXPIRY_COST_ACTIVE")
        reason_parts.append("Expiry or near-expiry exposure contributes to cost.")

    return_recovery_estimate = _return_recovery_estimate(
        row,
        overstock_units,
        near_expiry_units,
        selected_unit_cost,
        warnings,
        reason_parts,
    )
    dead_stock_cost = _dead_stock_cost(row, current_inventory, selected_unit_cost)
    non_moving_cost = _non_moving_cost(row, current_holding_cost, storage_space_cost)
    if dead_stock_cost > 0:
        warnings.append("DEAD_STOCK_COST_ACTIVE")

    order_costs = _recommended_order_costs(
        row,
        effective_order_quantity,
        selected_unit_cost,
        warnings,
        reason_parts,
    )
    if order_costs["recommended_total_order_cost"] <= 0:
        warnings.append("NO_RECOMMENDED_ORDER_COST")

    projected_inventory_after_order = max(inventory_position, 0.0) + effective_order_quantity
    projected_inventory_value_after_order = projected_inventory_after_order * selected_unit_cost
    projected_holding_cost_after_order = projected_inventory_value_after_order * holding_rate
    projected_overstock_units_after_order, _ = _overstock_details(
        row,
        projected_inventory_after_order,
        average_daily_demand,
    )
    projected_overstock_cost_after_order = projected_overstock_units_after_order * overstock_penalty

    risk_score = max(min(_float(row.get("demand_adjusted_procurement_risk_score")), 1.0), 0.0)
    supplier_risk_cost = order_costs["recommended_purchase_cost"] * risk_score * INVENTORY_COST_DEFAULTS["fallback_supplier_risk_cost_rate"]
    if _bool(row.get("supplier_review_signal")) or _bool(row.get("watchlist_supplier_signal")):
        supplier_risk_cost *= 1.5
    if supplier_risk_cost > 0 or _bool(row.get("recommended_supplier_requires_review")):
        warnings.append("SUPPLIER_RISK_COST_ACTIVE")

    phase4_review_cost_risk = _phase4_review_cost_risk(row, current_inventory_value)
    if phase4_review_cost_risk > 0:
        warnings.append("PHASE4_COST_RISK_INFORMATIONAL")

    total_current_inventory_cost = (
        current_holding_cost
        + storage_space_cost
        + handling_cost
        + current_stockout_cost
        + current_overstock_cost
        + expired_stock_cost
        + near_expiry_risk_cost
        + dead_stock_cost
        + non_moving_cost
    )
    total_recommended_action_cost = max(order_costs["recommended_total_order_cost"] - return_recovery_estimate, 0.0)
    total_projected_cost_after_action = (
        projected_holding_cost_after_order
        + projected_overstock_cost_after_order
        + expected_stockout_risk_cost
        + supplier_risk_cost
        + phase4_review_cost_risk
    )
    total_relevant_inventory_cost = (
        total_current_inventory_cost
        + total_recommended_action_cost
        + expected_stockout_risk_cost
        + supplier_risk_cost
        + phase4_review_cost_risk
    )

    cost_components = {
        "HOLDING_COST": current_holding_cost,
        "ORDERING_COST": order_costs["recommended_fixed_order_cost"]
        + order_costs["recommended_delivery_cost"]
        + order_costs["recommended_expected_delay_cost"]
        + order_costs["recommended_expected_quality_cost"]
        + order_costs["recommended_expedite_cost"],
        "PURCHASE_COST": order_costs["recommended_purchase_cost"],
        "STOCKOUT_COST": current_stockout_cost + expected_stockout_risk_cost,
        "OVERSTOCK_COST": current_overstock_cost + projected_overstock_cost_after_order,
        "EXPIRY_COST": expired_stock_cost + near_expiry_risk_cost,
        "DEAD_STOCK_COST": dead_stock_cost + non_moving_cost,
        "SUPPLIER_RISK_COST": supplier_risk_cost,
        "STORAGE_SPACE_COST": storage_space_cost,
        "HANDLING_COST": handling_cost,
        "PHASE4_REVIEW_COST_RISK": phase4_review_cost_risk,
    }
    main_cost_driver = _main_cost_driver(cost_components)
    cost_risk_level = _cost_risk_level(row, total_relevant_inventory_cost, cost_components, order_costs)
    cost_action_recommendation = _cost_action_recommendation(row, main_cost_driver)
    if _holding_cost_justified(row, main_cost_driver):
        warnings.append("HIGH_HOLDING_COST_JUSTIFIED")

    cost_justification_reason = _cost_justification_reason(row, main_cost_driver, cost_risk_level)
    cost_reason = _cost_reason(
        row,
        main_cost_driver,
        total_relevant_inventory_cost,
        order_costs["recommended_total_order_cost"],
        reason_parts,
    )

    return {
        "selected_unit_cost": _money(selected_unit_cost),
        "current_inventory_value": _money(current_inventory_value),
        "current_holding_cost": _money(current_holding_cost),
        "storage_space_cost": _money(storage_space_cost),
        "handling_cost": _money(handling_cost),
        "current_stockout_cost": _money(current_stockout_cost),
        "expected_stockout_risk_cost": _money(expected_stockout_risk_cost),
        "overstock_units": round(overstock_units, 2),
        "current_overstock_cost": _money(current_overstock_cost),
        "expired_stock_cost": _money(expired_stock_cost),
        "near_expiry_risk_cost": _money(near_expiry_risk_cost),
        "return_recovery_estimate": _money(return_recovery_estimate),
        "dead_stock_cost": _money(dead_stock_cost),
        "non_moving_cost": _money(non_moving_cost),
        **{key: _money(value) for key, value in order_costs.items()},
        "projected_inventory_after_order": round(projected_inventory_after_order, 2),
        "projected_inventory_value_after_order": _money(projected_inventory_value_after_order),
        "projected_holding_cost_after_order": _money(projected_holding_cost_after_order),
        "projected_overstock_units_after_order": round(projected_overstock_units_after_order, 2),
        "projected_overstock_cost_after_order": _money(projected_overstock_cost_after_order),
        "supplier_risk_cost": _money(supplier_risk_cost),
        "phase4_review_cost_risk": _money(phase4_review_cost_risk),
        "total_current_inventory_cost": _money(total_current_inventory_cost),
        "total_recommended_action_cost": _money(total_recommended_action_cost),
        "total_projected_cost_after_action": _money(total_projected_cost_after_action),
        "total_relevant_inventory_cost": _money(total_relevant_inventory_cost),
        "main_cost_driver": main_cost_driver,
        "cost_risk_level": cost_risk_level,
        "cost_action_recommendation": cost_action_recommendation,
        "cost_justification_reason": cost_justification_reason,
        "cost_reason": cost_reason,
        "cost_warning_flags": ";".join(_unique(warnings)),
        "storage_cost_per_m3": storage_cost_per_m3,
        "stockout_units": round(stockout_units, 2),
    }


def _current_inventory_value(row: pd.Series, current_inventory: float, selected_unit_cost: float) -> float:
    """Use validated inventory value when available, otherwise calculate it."""
    inventory_value = _float(row.get("inventory_value"), default=-1.0)
    if inventory_value >= 0:
        return inventory_value
    return max(current_inventory, 0.0) * selected_unit_cost


def _handling_cost(
    row: pd.Series,
    movement_count: float,
    recommended_order_quantity: float,
    current_inventory: float,
    handling_cost_per_unit: float,
) -> float:
    """Estimate handling burden from movement volume or a small fallback base."""
    if movement_count > 0:
        return movement_count * handling_cost_per_unit
    if recommended_order_quantity > 0:
        return recommended_order_quantity * INVENTORY_COST_DEFAULTS["fallback_handling_cost_per_unit"]
    return max(current_inventory, 0.0) * INVENTORY_COST_DEFAULTS["fallback_handling_cost_per_unit"] * 0.05


def _stockout_units(row: pd.Series, current_inventory: float, available_inventory: float) -> tuple[float, bool]:
    """Return explicit or estimated stockout units."""
    stockout_units = _float(row.get("stockout_units"), default=-1.0)
    if stockout_units > 0:
        return stockout_units, False
    if row.get("main_inventory_status") == "STOCKOUT" or _bool(row.get("stockout_signal")):
        estimate = abs(min(current_inventory, available_inventory, 0.0))
        return max(estimate, 1.0), True
    return 0.0, False


def _expected_stockout_risk_cost(row: pd.Series, stockout_penalty: float, average_daily_demand: float) -> float:
    """Estimate near-term stockout exposure for stockout and low-stock statuses."""
    status = str(row.get("main_inventory_status", ""))
    if status not in {"STOCKOUT", "ZERO_STOCK", "CRITICAL_LOW_STOCK", "REORDER_NOW"}:
        return 0.0
    probability = INVENTORY_COST_DEFAULTS["fallback_stockout_probability"]
    if status == "STOCKOUT":
        probability = 1.0
    elif status == "ZERO_STOCK":
        probability = 0.75
    elif status == "CRITICAL_LOW_STOCK":
        probability = 0.50
    multiplier = 1.0
    if row.get("inventory_priority_class") == "CRITICAL_PRIORITY" or row.get("vitality_class") == "VITAL":
        multiplier = 1.5
    elif row.get("inventory_priority_class") == "HIGH_PRIORITY" or row.get("vitality_class") == "IMPORTANT":
        multiplier = 1.2
    fallback_demand = max(average_daily_demand, 1.0)
    return stockout_penalty * fallback_demand * INVENTORY_COST_DEFAULTS["fallback_stockout_duration_days"] * probability * multiplier


def _overstock_units(row: pd.Series, inventory_position: float, average_daily_demand: float) -> float:
    """Estimate overstock units against max-stock and days-of-supply thresholds."""
    units, _ = _overstock_details(row, inventory_position, average_daily_demand)
    return units


def _overstock_details(row: pd.Series, inventory_position: float, average_daily_demand: float) -> tuple[float, str]:
    """Estimate overstock units and explain whether max stock, days of supply, or both drove it."""
    max_stock_level = _float(row.get("max_stock_level"), default=-1.0)
    excess_by_max_stock = max(inventory_position - max_stock_level, 0.0) if max_stock_level >= 0 else 0.0
    threshold = _float(row.get("overstock_days_of_supply_threshold"), default=_overstock_days_threshold(row))
    max_units_by_days = max(average_daily_demand * threshold, 0.0)
    excess_by_days_supply = max(inventory_position - max_units_by_days, 0.0) if average_daily_demand > 0 else 0.0
    units = max(excess_by_max_stock, excess_by_days_supply)
    if excess_by_max_stock > 0 and excess_by_days_supply > 0:
        reason = "Overstock cost is driven by both max-stock excess and days-of-supply excess."
    elif excess_by_max_stock > 0:
        reason = "Overstock cost is driven by inventory position above max stock level."
    elif excess_by_days_supply > 0:
        reason = "Overstock cost is driven by days of supply above the configured threshold."
    else:
        reason = "No overstock cost driver is active."
    return units, reason


def _overstock_days_threshold(row: pd.Series) -> int:
    """Return days-of-supply threshold using the Step 7 status rules."""
    if row.get("perishability_class") == "SPOILAGE_RISK":
        return INVENTORY_STATUS_THRESHOLDS["spoilage_risk_overstock_days_of_supply"]
    if row.get("seasonality_class") == "SEASONAL_DRAWDOWN":
        return INVENTORY_STATUS_THRESHOLDS["seasonal_drawdown_overstock_days_of_supply"]
    if row.get("movement_class") == "NON_MOVING":
        return INVENTORY_STATUS_THRESHOLDS["non_moving_overstock_days_of_supply"]
    if row.get("inventory_priority_class") == "LOW_PRIORITY":
        return INVENTORY_STATUS_THRESHOLDS["low_priority_overstock_days_of_supply"]
    if row.get("perishability_class") in {"EXPIRY_TRACKED", "PERISHABLE"} or _bool(row.get("perishable")):
        return INVENTORY_STATUS_THRESHOLDS["perishable_overstock_days_of_supply"]
    return INVENTORY_STATUS_THRESHOLDS["default_overstock_days_of_supply"]


def _return_recovery_estimate(
    row: pd.Series,
    overstock_units: float,
    near_expiry_units: float,
    selected_unit_cost: float,
    warnings: list[str],
    reason_parts: list[str],
) -> float:
    """Estimate recoverable value from returns without inventing supplier policy."""
    if (
        not _bool(row.get("supplier_accepts_returns"))
        or _float(row.get("return_window_days")) <= 0
        or not _valid_return_policy_status(row.get("return_policy_status"))
    ):
        if overstock_units > 0 or near_expiry_units > 0:
            warnings.append("RETURN_POLICY_UNAVAILABLE")
            reason_parts.append("Supplier return recovery is unavailable or missing.")
        return 0.0
    returnable_units = max(overstock_units, 0.0) + max(near_expiry_units, 0.0)
    if returnable_units <= 0:
        return 0.0
    deduction = max(min(_float(row.get("return_deduction_rate"), default=1.0), 1.0), 0.0)
    transport_cost = max(_float(row.get("return_transport_cost")), 0.0)
    return max(returnable_units * selected_unit_cost * (1 - deduction) - transport_cost, 0.0)


def _dead_stock_cost(row: pd.Series, current_inventory: float, selected_unit_cost: float) -> float:
    """Estimate markdown loss for dead stock."""
    if not _bool(row.get("dead_stock_signal")):
        return 0.0
    return max(current_inventory, 0.0) * selected_unit_cost * INVENTORY_COST_DEFAULTS["fallback_dead_stock_markdown_loss_rate"]


def _non_moving_cost(row: pd.Series, current_holding_cost: float, storage_space_cost: float) -> float:
    """Estimate frozen-capital burden for non-moving inventory."""
    if _bool(row.get("non_moving_signal")) or row.get("movement_class") == "NON_MOVING":
        return current_holding_cost + storage_space_cost
    return 0.0


def _recommended_order_costs(
    row: pd.Series,
    recommended_order_quantity: float,
    selected_unit_cost: float,
    warnings: list[str],
    reason_parts: list[str],
) -> dict:
    """Calculate immediate recommended order cost components."""
    if recommended_order_quantity <= 0:
        return {
            "recommended_purchase_cost": 0.0,
            "recommended_fixed_order_cost": 0.0,
            "recommended_delivery_cost": 0.0,
            "recommended_expected_delay_cost": 0.0,
            "recommended_expected_quality_cost": 0.0,
            "recommended_expedite_cost": 0.0,
            "recommended_total_order_cost": 0.0,
        }

    purchase_cost = recommended_order_quantity * selected_unit_cost
    fixed_order_cost = _first_positive(
        row,
        ["estimated_fixed_order_cost", "fixed_order_cost"],
        INVENTORY_COST_DEFAULTS["fallback_fixed_order_cost"],
        warnings,
    )
    delivery_cost = _first_positive(
        row,
        ["estimated_delivery_cost", "delivery_cost"],
        INVENTORY_COST_DEFAULTS["fallback_delivery_cost"],
        warnings,
    )
    delay_cost = _float(row.get("estimated_expected_delay_cost"))
    if delay_cost <= 0:
        delay_cost = (
            max(_float(row.get("demand_adjusted_procurement_risk_score")), 0.0)
            * INVENTORY_COST_DEFAULTS["fallback_delay_cost_per_day"]
            * max(_float(row.get("expected_lead_time_days")), 1.0)
        )
        warnings.append("PROCUREMENT_COST_COMPONENTS_PARTIAL")
    quality_cost = _float(row.get("estimated_expected_quality_cost"))
    if quality_cost <= 0:
        quality_cost = (
            recommended_order_quantity
            * INVENTORY_COST_DEFAULTS["fallback_quality_cost_per_unit"]
            * max(_float(row.get("demand_adjusted_procurement_risk_score")), 0.0)
        )
        warnings.append("PROCUREMENT_COST_COMPONENTS_PARTIAL")

    expedite_cost = 0.0
    if row.get("primary_action") == "EXPEDITE_ORDER" or row.get("secondary_action") == "USE_FAST_RELIABLE_SUPPLIER":
        expedite_cost = purchase_cost * INVENTORY_COST_DEFAULTS["fallback_expedite_cost_rate"]
        reason_parts.append("Expedite cost is included because the action recommends urgent recovery.")

    total_order_cost = purchase_cost + fixed_order_cost + delivery_cost + delay_cost + quality_cost + expedite_cost
    if total_order_cost >= INVENTORY_COST_RISK_THRESHOLDS["high_recommended_order_cost"]:
        warnings.append("HIGH_ORDER_COST")
    return {
        "recommended_purchase_cost": purchase_cost,
        "recommended_fixed_order_cost": fixed_order_cost,
        "recommended_delivery_cost": delivery_cost,
        "recommended_expected_delay_cost": delay_cost,
        "recommended_expected_quality_cost": quality_cost,
        "recommended_expedite_cost": expedite_cost,
        "recommended_total_order_cost": total_order_cost,
    }


def _effective_order_quantity_for_action(
    row: pd.Series,
    recommended_order_quantity: float,
    warnings: list[str],
    reason_parts: list[str],
) -> float:
    """Use order quantity for cost only when the current action is order-related."""
    if recommended_order_quantity <= 0:
        return 0.0
    order_actions = {"ORDER_RECOMMENDED_QUANTITY", "EXPEDITE_ORDER", "REVIEW_SUPPLIER_BEFORE_ORDER"}
    if row.get("primary_action") in order_actions or row.get("secondary_action") == "ORDER_RECOMMENDED_QUANTITY":
        return recommended_order_quantity
    warnings.append("NO_RECOMMENDED_ORDER_COST")
    reason_parts.append(
        f"No immediate order cost is counted because primary action is {str(row.get('primary_action')).lower()}."
    )
    return 0.0


def _phase4_review_cost_risk(row: pd.Series, current_inventory_value: float) -> float:
    """Add a small informational placeholder for Phase 4 production/BOM/MRP review risk."""
    if _bool(row.get("phase4_review_flag")) or _bool(row.get("phase4_review_before_final_policy")):
        return current_inventory_value * 0.02
    return 0.0


def _main_cost_driver(cost_components: dict[str, float]) -> str:
    """Return the largest meaningful cost driver."""
    if not cost_components:
        return "LOW_COST_NORMAL"
    driver, value = max(cost_components.items(), key=lambda item: item[1])
    if value <= 0:
        return "LOW_COST_NORMAL"
    return driver


def _cost_risk_level(row: pd.Series, total_relevant_cost: float, cost_components: dict, order_costs: dict) -> str:
    """Classify cost risk from total exposure and severe component signals."""
    if (
        row.get("main_inventory_status") == "STOCKOUT"
        and (row.get("inventory_priority_class") == "CRITICAL_PRIORITY" or row.get("vitality_class") == "VITAL")
    ):
        return "CRITICAL"
    if total_relevant_cost >= INVENTORY_COST_RISK_THRESHOLDS["critical_total_cost"]:
        return "CRITICAL"
    if total_relevant_cost >= INVENTORY_COST_RISK_THRESHOLDS["high_total_cost"]:
        return "HIGH"
    if (
        cost_components.get("STOCKOUT_COST", 0.0) >= INVENTORY_COST_RISK_THRESHOLDS["high_stockout_cost"]
        or cost_components.get("EXPIRY_COST", 0.0) >= INVENTORY_COST_RISK_THRESHOLDS["high_expiry_cost"]
        or cost_components.get("OVERSTOCK_COST", 0.0) >= INVENTORY_COST_RISK_THRESHOLDS["high_overstock_cost"]
        or order_costs.get("recommended_total_order_cost", 0.0)
        >= INVENTORY_COST_RISK_THRESHOLDS["high_recommended_order_cost"]
    ):
        return "HIGH"
    if total_relevant_cost >= INVENTORY_COST_RISK_THRESHOLDS["low_total_cost"]:
        return "MEDIUM"
    return "LOW"


def _cost_action_recommendation(row: pd.Series, main_cost_driver: str) -> str:
    """Translate the cost driver into a cost-focused recommendation."""
    if "PARAMETER_INCONSISTENCY" in str(row.get("secondary_status_flags", "")):
        return "REVIEW_POLICY_PARAMETERS"
    if row.get("primary_action") == "EXPEDITE_ORDER":
        return "EXPEDITE_REPLENISHMENT"
    if row.get("primary_action") == "REVIEW_SUPPLIER_BEFORE_ORDER":
        return "REVIEW_SUPPLIER_COST_RISK"
    if row.get("primary_action") == "WAIT_FOR_TRIGGER" or _bool(row.get("no_order_recommended_flag")):
        return "WAIT_FOR_TRIGGER"
    if main_cost_driver == "STOCKOUT_COST":
        return "EXPEDITE_REPLENISHMENT" if row.get("action_priority") == "URGENT" else "REVIEW_POLICY_PARAMETERS"
    if main_cost_driver == "OVERSTOCK_COST":
        return "REDUCE_FUTURE_ORDERS"
    if main_cost_driver == "EXPIRY_COST":
        return "SCRAP_OR_QUARANTINE_EXPIRED" if _float(row.get("expired_units")) > 0 else "MARKDOWN_OR_RETURN_STOCK"
    if main_cost_driver == "DEAD_STOCK_COST":
        return "LIQUIDATE_DEAD_STOCK"
    if main_cost_driver == "SUPPLIER_RISK_COST":
        return "REVIEW_SUPPLIER_COST_RISK"
    if main_cost_driver == "PHASE4_REVIEW_COST_RISK":
        return "REVIEW_POLICY_PARAMETERS"
    if main_cost_driver in {"HOLDING_COST", "STORAGE_SPACE_COST", "HANDLING_COST"}:
        return "JUSTIFY_HIGHER_HOLDING_COST"
    if main_cost_driver in {"PURCHASE_COST", "ORDERING_COST"}:
        return "REVIEW_POLICY_PARAMETERS" if _bool(row.get("quantity_constraint_flag")) else "NO_COST_ACTION_REQUIRED"
    return "NO_COST_ACTION_REQUIRED"


def _holding_cost_justified(row: pd.Series, main_cost_driver: str) -> bool:
    """Return True when high holding cost is expected for protected SKUs."""
    return bool(
        main_cost_driver == "HOLDING_COST"
        and (
            row.get("inventory_priority_class") in {"CRITICAL_PRIORITY", "HIGH_PRIORITY"}
            or row.get("vitality_class") == "VITAL"
        )
    )


def _cost_justification_reason(row: pd.Series, main_cost_driver: str, cost_risk_level: str) -> str:
    """Explain whether the visible cost appears justified or review-worthy."""
    if _holding_cost_justified(row, main_cost_driver):
        return "Higher holding cost may be justified because the SKU is priority or vital."
    if cost_risk_level in {"HIGH", "CRITICAL"}:
        return f"Cost risk is {cost_risk_level}; review the dominant driver before final action."
    if row.get("primary_action") in {"WAIT_FOR_TRIGGER", "NO_ACTION"}:
        return "Cost exposure is visible, but current action does not require an order."
    return "Cost exposure aligns with the current status and recommended action."


def _cost_reason(
    row: pd.Series,
    main_cost_driver: str,
    total_relevant_cost: float,
    recommended_total_order_cost: float,
    reason_parts: list[str],
) -> str:
    """Create readable cost explanation text."""
    reason = (
        f"Main cost driver is {main_cost_driver.replace('_', ' ').lower()} with total relevant cost "
        f"{_money(total_relevant_cost):.2f}."
    )
    if recommended_total_order_cost > 0:
        reason += f" Recommended action cost is {_money(recommended_total_order_cost):.2f}."
    if row.get("main_inventory_status") in {"STOCKOUT", "ZERO_STOCK"}:
        reason += " Stock availability risk is included in the cost exposure."
    if reason_parts:
        reason += " " + " ".join(_unique(reason_parts))
    return reason


def _build_cost_summary(costs_df: pd.DataFrame) -> pd.DataFrame:
    """Create grouped cost totals for later dashboard and decision layers."""
    rows = [_summary_row(costs_df, "ALL_SKUS", "ALL_SKUS")]
    groupings = [
        ("BY_MAIN_COST_DRIVER", "main_cost_driver"),
        ("BY_COST_RISK_LEVEL", "cost_risk_level"),
        ("BY_MAIN_INVENTORY_STATUS", "main_inventory_status"),
        ("BY_ACTION_PRIORITY", "action_priority"),
        ("BY_INVENTORY_MODEL_TYPE", "inventory_model_type"),
        ("BY_CATEGORY", "category"),
    ]
    for summary_type, column in groupings:
        if column not in costs_df.columns:
            continue
        for group_name, group_df in costs_df.groupby(costs_df[column].fillna("UNKNOWN"), dropna=False):
            rows.append(_summary_row(group_df, summary_type, str(group_name)))
    return pd.DataFrame(rows)


def _summary_row(df: pd.DataFrame, summary_type: str, group_name: str) -> dict:
    """Return a summary row."""
    return {
        "summary_type": summary_type,
        "group_name": group_name,
        "total_current_inventory_cost": _money(df["total_current_inventory_cost"].sum()) if "total_current_inventory_cost" in df else 0.0,
        "total_recommended_action_cost": _money(df["total_recommended_action_cost"].sum()) if "total_recommended_action_cost" in df else 0.0,
        "total_projected_cost_after_action": _money(df["total_projected_cost_after_action"].sum()) if "total_projected_cost_after_action" in df else 0.0,
        "total_relevant_inventory_cost": _money(df["total_relevant_inventory_cost"].sum()) if "total_relevant_inventory_cost" in df else 0.0,
        "sku_count": int(len(df)),
    }


def _selected_unit_cost(row: pd.Series) -> tuple[float, bool]:
    """Select procurement cost, inventory cost, then fallback."""
    procurement_cost = _float(row.get("unit_cost_procurement"))
    if procurement_cost > 0:
        return procurement_cost, False
    inventory_cost = _float(row.get("unit_cost_inventory"))
    if inventory_cost > 0:
        return inventory_cost, False
    return INVENTORY_COST_DEFAULTS["fallback_unit_cost"], True


def _first_positive(row: pd.Series, columns: list[str], fallback: float, warnings: list[str]) -> float:
    """Return the first positive numeric value from a row."""
    for column in columns:
        value = _float(row.get(column))
        if value > 0:
            return value
    warnings.append("COST_USES_FALLBACKS")
    return fallback


def _positive_or_default(value, default: float, warnings: list[str]) -> float:
    """Return positive value or default and flag fallback use."""
    number = _float(value)
    if number > 0:
        return number
    warnings.append("COST_USES_FALLBACKS")
    return default


def _valid_return_policy_status(value) -> bool:
    """Return True only when return policy status is available enough to count recovery."""
    status = str(value or "").strip().upper()
    if not status:
        return False
    unavailable_terms = {"MISSING", "UNKNOWN", "PLACEHOLDER", "UNAVAILABLE", "NONE"}
    return not any(term in status for term in unavailable_terms)


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Ensure a dataframe has every requested output column."""
    for column in columns:
        if column not in df.columns:
            df[column] = pd.NA
    return df


def _cost_output_columns() -> list[str]:
    """Return ordered columns for inventory_costs.csv."""
    return [
        "sku_id",
        "product_name",
        "category",
        "inventory_model_type",
        "review_policy",
        "main_inventory_status",
        "secondary_status_flags",
        "primary_action",
        "secondary_action",
        "action_priority",
        "action_reason",
        "policy_review_required",
        "quantity_constraint_flag",
        "warning_codes",
        "current_inventory",
        "available_inventory",
        "inventory_position",
        "recommended_order_quantity",
        "safety_stock",
        "reorder_point",
        "min_stock_level",
        "max_stock_level",
        "days_of_supply_current",
        "days_of_supply_after_recommended_order",
        "abc_class",
        "xyz_class",
        "fsn_class",
        "vitality_class",
        "seasonality_class",
        "perishability_class",
        "movement_class",
        "inventory_priority_class",
        "service_level_target",
        "recommended_supplier_id",
        "backup_supplier_id",
        "recommended_supplier_feasible",
        "recommended_supplier_requires_review",
        "supplier_review_signal",
        "watchlist_supplier_signal",
        "supplier_review_before_order",
        "supplier_accepts_returns",
        "return_window_days",
        "return_deduction_rate",
        "return_transport_cost",
        "return_policy_status",
        "unit_cost_inventory",
        "unit_cost_procurement",
        "inventory_value",
        "stockout_units",
        "stockout_penalty_per_unit",
        "overstock_penalty_per_unit",
        "near_expiry_units",
        "expired_units",
        "average_daily_demand",
        "moq",
        "batch_size",
        "expected_yield_rate",
        "expected_lead_time_days",
        "lead_time_std_days",
        "demand_adjusted_procurement_risk_score",
        "demand_adjusted_procurement_risk_class",
        "estimated_fixed_order_cost",
        "fixed_order_cost",
        "delivery_cost",
        "estimated_delivery_cost",
        "estimated_expected_delay_cost",
        "estimated_expected_quality_cost",
        "cost_per_late_day",
        "partial_delivery_penalty",
        "quality_rejection_cost_per_unit",
        "unit_volume_m3",
        "handling_cost_per_unit",
        "storage_cost_per_m3",
        "selected_unit_cost",
        "current_inventory_value",
        "current_holding_cost",
        "storage_space_cost",
        "handling_cost",
        "current_stockout_cost",
        "expected_stockout_risk_cost",
        "overstock_units",
        "current_overstock_cost",
        "expired_stock_cost",
        "near_expiry_risk_cost",
        "return_recovery_estimate",
        "dead_stock_cost",
        "non_moving_cost",
        "recommended_purchase_cost",
        "recommended_fixed_order_cost",
        "recommended_delivery_cost",
        "recommended_expected_delay_cost",
        "recommended_expected_quality_cost",
        "recommended_expedite_cost",
        "recommended_total_order_cost",
        "projected_inventory_after_order",
        "projected_inventory_value_after_order",
        "projected_holding_cost_after_order",
        "projected_overstock_units_after_order",
        "projected_overstock_cost_after_order",
        "supplier_risk_cost",
        "phase4_review_cost_risk",
        "total_current_inventory_cost",
        "total_recommended_action_cost",
        "total_projected_cost_after_action",
        "total_relevant_inventory_cost",
        "main_cost_driver",
        "cost_risk_level",
        "cost_action_recommendation",
        "cost_justification_reason",
        "cost_reason",
        "cost_warning_flags",
    ]


def _bool(value) -> bool:
    """Safely convert scalar values to boolean."""
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def _float(value, default: float = 0.0) -> float:
    """Safely convert scalar values to float."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _money(value: float) -> float:
    """Round currency-like values."""
    return round(max(_float(value), 0.0), 2)


def _unique(values: list[str]) -> list[str]:
    """Return unique values preserving order."""
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
