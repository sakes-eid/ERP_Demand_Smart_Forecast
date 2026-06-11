"""Inventory parameter calculations for Phase 3 Step 6."""

from __future__ import annotations

import math

import pandas as pd

from config import (
    DEMAND_VARIABILITY_FALLBACKS,
    EVENT_BASED_REPLENISHMENT_RULES,
    HOLDING_COST_COMPONENTS,
    INVENTORY_PARAMETER_ADJUSTMENTS,
    INVENTORY_PARAMETER_DEFAULTS,
    INVENTORY_PARAMETER_LIMITS,
    INVENTORY_POSITION_CAP_RULES,
    ONE_TO_ONE_REPLACEMENT_RULES,
)


def calculate_inventory_parameters(inventory_policy: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fill selected policy rows with inventory control parameters."""
    rows = []
    for _, row in inventory_policy.iterrows():
        result = row.to_dict()
        context = _calculation_context(row)
        input_reason = context.pop("_input_reason", "")
        flags = _empty_flags(row)
        parameters = _policy_parameters(row, context, flags)
        result.update(context)
        result.update(parameters)
        result.update(_finalize_flags_and_reasons(row, flags, parameters, input_reason))
        rows.append(result)

    updated_policy = pd.DataFrame(rows)
    parameter_output = updated_policy[_parameter_output_columns(updated_policy)].copy()
    return updated_policy, parameter_output


def _calculation_context(row: pd.Series) -> dict:
    """Calculate demand and lead-time uncertainty inputs."""
    reasons = []
    demand = _float(row.get("average_daily_demand"))
    if demand <= 0:
        demand = INVENTORY_PARAMETER_DEFAULTS["fallback_average_daily_demand"]
        reasons.append("Average daily demand fallback was used.")

    behavior = str(row.get("demand_behavior_class", "unknown")).lower()
    cv = _float(row.get("coefficient_of_variation"))
    if cv <= 0:
        cv = DEMAND_VARIABILITY_FALLBACKS.get(behavior, DEMAND_VARIABILITY_FALLBACKS["unknown"])
        reasons.append("Demand variability fallback was used.")

    lead_time = _float(row.get("expected_lead_time_days"))
    if lead_time <= 0:
        lead_time = INVENTORY_PARAMETER_DEFAULTS["fallback_lead_time_days"]
        reasons.append("Lead time fallback was used.")

    lead_time_std = _float(row.get("lead_time_std_days"), default=-1)
    if lead_time_std < 0:
        lead_time_std = INVENTORY_PARAMETER_DEFAULTS["fallback_lead_time_std_days"]
        reasons.append("Lead time variability fallback was used.")

    demand_std_daily = max(demand * cv, 0.0)
    mean_demand_during_lead_time = demand * lead_time
    variance_during_lead_time = (lead_time * demand_std_daily**2) + (demand**2 * lead_time_std**2)
    std_demand_during_lead_time = math.sqrt(max(variance_during_lead_time, 0.0))

    return {
        "average_daily_demand": round(demand, 4),
        "coefficient_of_variation": round(cv, 4),
        "expected_lead_time_days": round(lead_time, 4),
        "lead_time_std_days": round(lead_time_std, 4),
        "demand_std_daily": round(demand_std_daily, 4),
        "mean_demand_during_lead_time": round(mean_demand_during_lead_time, 4),
        "std_demand_during_lead_time": round(std_demand_during_lead_time, 4),
        "_input_reason": " ".join(reasons),
    }


def _policy_parameters(row: pd.Series, context: dict, flags: dict) -> dict:
    """Calculate policy-specific parameters."""
    safety_stock = _safety_stock(row, context)
    reorder_point = _round_units(context["mean_demand_during_lead_time"] + safety_stock)
    eoq = _eoq(row, context)
    model_type = row.get("inventory_model_type")

    common = {
        "safety_stock": safety_stock,
        "reorder_point": reorder_point,
        "eoq": round(eoq, 2),
        "eoq_rounded": pd.NA,
        "recommended_order_quantity": 0,
        "min_stock_level": safety_stock,
        "max_stock_level": reorder_point,
        "reorder_point_s": reorder_point,
        "order_quantity_Q": pd.NA,
        "order_up_to_level_S": pd.NA,
        "base_stock_level": pd.NA,
        "newsvendor_critical_ratio": pd.NA,
    }

    if model_type == "CONTINUOUS_REVIEW_sQ":
        return _continuous_review_parameters(row, context, flags, common)
    if model_type == "EOQ":
        return _eoq_parameters(row, context, flags, common)
    if model_type == "PERIODIC_REVIEW_RS":
        return _periodic_review_parameters(row, context, flags, common)
    if model_type == "BASE_STOCK":
        return _base_stock_parameters(row, context, flags, common)
    if model_type == "NEWSVENDOR_CANDIDATE":
        return _newsvendor_parameters(row, context, flags, common)
    if model_type == "EVENT_BASED_REPLENISHMENT":
        return _event_based_parameters(row, context, flags, common)
    if model_type == "ONE_TO_ONE_REPLACEMENT":
        return _one_to_one_parameters(row, context, flags, common)
    return _periodic_review_parameters(row, context, flags, common)


def _continuous_review_parameters(row: pd.Series, context: dict, flags: dict, common: dict) -> dict:
    """Calculate continuous-review s,Q parameters."""
    base_quantity = common["eoq"]
    if _bool(row.get("stockout_signal")):
        base_quantity = max(base_quantity, _float(row.get("stockout_units")) + common["reorder_point"])
        base_quantity *= INVENTORY_PARAMETER_ADJUSTMENTS["stockout_order_boost_multiplier"]
        flags["stockout_order_boost_applied"] = True
        flags["warning_codes"].append("STOCKOUT_ORDER_BOOSTED")
    order_quantity = _constrained_order_quantity(base_quantity, row, context, flags, allow_zero=False)
    common.update(
        {
            "eoq_rounded": order_quantity,
            "order_quantity_Q": order_quantity,
            "recommended_order_quantity": order_quantity,
            "min_stock_level": common["safety_stock"],
            "max_stock_level": _round_units(common["reorder_point"] + order_quantity),
            "parameter_calculation_reason": "Calculated continuous-review s,Q using demand during lead time, safety stock, and EOQ-based order quantity.",
        }
    )
    return common


def _eoq_parameters(row: pd.Series, context: dict, flags: dict, common: dict) -> dict:
    """Calculate EOQ policy parameters."""
    order_quantity = _constrained_order_quantity(common["eoq"], row, context, flags, allow_zero=False)
    common.update(
        {
            "eoq_rounded": order_quantity,
            "order_quantity_Q": order_quantity,
            "recommended_order_quantity": order_quantity,
            "min_stock_level": common["safety_stock"],
            "max_stock_level": _round_units(common["reorder_point"] + order_quantity),
            "parameter_calculation_reason": "Calculated EOQ policy using annual demand, setup cost, holding cost, MOQ, batch, and yield constraints.",
        }
    )
    return common


def _periodic_review_parameters(row: pd.Series, context: dict, flags: dict, common: dict) -> dict:
    """Calculate periodic review R,S parameters."""
    review_period = max(_float(row.get("review_period_R")), 0.0)
    protection_period = review_period + context["expected_lead_time_days"]
    mean_protection = context["average_daily_demand"] * protection_period
    variance_protection = (
        protection_period * context["demand_std_daily"] ** 2
        + context["average_daily_demand"] ** 2 * context["lead_time_std_days"] ** 2
    )
    std_protection = math.sqrt(max(variance_protection, 0.0))
    order_up_to = _round_units(mean_protection + _safety_factor(row) * std_protection)
    raw_quantity = max(order_up_to - _float(row.get("inventory_position")), 0.0)
    order_quantity = _constrained_order_quantity(raw_quantity, row, context, flags, allow_zero=True)
    common.update(
        {
            "order_up_to_level_S": order_up_to,
            "recommended_order_quantity": order_quantity,
            "min_stock_level": common["safety_stock"],
            "max_stock_level": max(order_up_to, order_quantity),
            "parameter_calculation_reason": "Calculated periodic review R,S using review period, lead time, demand uncertainty, and inventory position.",
        }
    )
    return common


def _base_stock_parameters(row: pd.Series, context: dict, flags: dict, common: dict) -> dict:
    """Calculate base-stock policy parameters."""
    p90_reference = max(_float(row.get("average_p90_forecast")), _float(row.get("average_p50_forecast")), 0.0)
    base_stock = _round_units(
        max(
            common["reorder_point"],
            p90_reference * context["expected_lead_time_days"],
            context["mean_demand_during_lead_time"] + common["safety_stock"],
        )
    )
    raw_quantity = max(base_stock - _float(row.get("inventory_position")), 0.0)
    order_quantity = _constrained_order_quantity(raw_quantity, row, context, flags, allow_zero=True)
    common.update(
        {
            "base_stock_level": base_stock,
            "recommended_order_quantity": order_quantity,
            "min_stock_level": common["safety_stock"],
            "max_stock_level": max(base_stock, _round_units(_float(row.get("inventory_position")) + order_quantity)),
            "parameter_calculation_reason": "Calculated base-stock policy using reorder point and p90 demand reference.",
        }
    )
    return common


def _newsvendor_parameters(row: pd.Series, context: dict, flags: dict, common: dict) -> dict:
    """Calculate newsvendor candidate parameters."""
    critical_ratio = _newsvendor_critical_ratio(row)
    p50 = max(_float(row.get("average_p50_forecast")), context["mean_demand_during_lead_time"])
    p90 = max(_float(row.get("average_p90_forecast")), context["mean_demand_during_lead_time"])
    if row.get("seasonality_class") == "SEASONAL_BUILDUP" or critical_ratio >= 0.70:
        raw_quantity = p90
    elif row.get("seasonality_class") == "SEASONAL_DRAWDOWN" or row.get("perishability_class") == "SPOILAGE_RISK":
        raw_quantity = min(p50, _order_cap_quantity(row, context))
    elif critical_ratio >= 0.40:
        raw_quantity = p50
    else:
        raw_quantity = context["mean_demand_during_lead_time"] * 0.5
    order_quantity = _constrained_order_quantity(raw_quantity, row, context, flags, allow_zero=True)
    max_stock = min(_round_units(common["reorder_point"] + order_quantity), _order_cap_quantity(row, context))
    common.update(
        {
            "newsvendor_critical_ratio": critical_ratio,
            "recommended_order_quantity": order_quantity,
            "min_stock_level": common["safety_stock"],
            "max_stock_level": max(max_stock, common["safety_stock"]),
            "parameter_calculation_reason": "Calculated newsvendor candidate using shortage-vs-excess critical ratio and capped quantity for perishability.",
        }
    )
    return common


def _event_based_parameters(row: pd.Series, context: dict, flags: dict, common: dict) -> dict:
    """Calculate event-based replenishment parameters."""
    trigger, trigger_reason = _event_based_order_trigger(row, context)
    if trigger:
        raw_quantity = max(_float(row.get("stockout_units")), context["mean_demand_during_lead_time"], 1.0)
        order_quantity = _constrained_order_quantity(raw_quantity, row, context, flags, allow_zero=False)
        reason = f"Event-based replenishment recommends a small trigger-based order because {trigger_reason}"
    else:
        order_quantity = EVENT_BASED_REPLENISHMENT_RULES["default_no_order_quantity"]
        flags["no_order_recommended_flag"] = True
        flags["no_order_event_based"] = True
        flags["warning_codes"].append("NO_ORDER_RECOMMENDED_FOR_EVENT_BASED")
        _mark_existing_inventory_no_order_cap(row, context, flags)
        if row.get("vitality_class") == "IMPORTANT" and EVENT_BASED_REPLENISHMENT_RULES["important_review_only_without_trigger"]:
            flags["additional_reasons"].append("Important SKU requires review, but no event-based order trigger is active.")
        reason = "Event-based replenishment recommends no order because no stockout, low-inventory, or event trigger is active."
    common.update(
        {
            "recommended_order_quantity": order_quantity,
            "min_stock_level": common["safety_stock"] if trigger else 0,
            "max_stock_level": max(order_quantity, common["safety_stock"], _round_units(context["average_daily_demand"] * 7)),
            "parameter_calculation_reason": reason,
        }
    )
    return common


def _one_to_one_parameters(row: pd.Series, context: dict, flags: dict, common: dict) -> dict:
    """Calculate one-to-one replacement parameters."""
    trigger, trigger_reason, replacement_quantity = _one_to_one_order_trigger(row)
    if trigger:
        raw_quantity = max(replacement_quantity, 1.0)
        order_quantity = _constrained_order_quantity(raw_quantity, row, context, flags, allow_zero=False)
        reason = f"One-to-one replacement quantity based on {trigger_reason} and procurement constraints."
    else:
        order_quantity = ONE_TO_ONE_REPLACEMENT_RULES["default_no_order_quantity"]
        flags["no_order_recommended_flag"] = True
        flags["no_order_one_to_one"] = True
        flags["warning_codes"].append("NO_ORDER_RECOMMENDED_FOR_ONE_TO_ONE")
        _mark_existing_inventory_no_order_cap(row, context, flags)
        flags["additional_reasons"].append("Phase 4 item remains review-flagged, but no replacement order is triggered yet.")
        reason = "One-to-one replacement recommends no order because no stockout, issue, or replacement trigger is active."
    common.update(
        {
            "recommended_order_quantity": order_quantity,
            "min_stock_level": common["safety_stock"],
            "max_stock_level": max(order_quantity, common["safety_stock"]),
            "parameter_calculation_reason": reason,
        }
    )
    return common


def _event_based_order_trigger(row: pd.Series, context: dict) -> tuple[bool, str]:
    """Return whether an event-based SKU has a real ordering trigger."""
    inventory_position = _float(row.get("inventory_position"))
    current_inventory = _float(row.get("current_inventory"))
    low_inventory_trigger = (
        context["average_daily_demand"]
        * EVENT_BASED_REPLENISHMENT_RULES["trigger_when_inventory_below_days_of_supply"]
    )
    p_forecast = max(_float(row.get("average_p50_forecast")), _float(row.get("average_p90_forecast")))
    if EVENT_BASED_REPLENISHMENT_RULES["trigger_when_stockout"] and _bool(row.get("stockout_signal")):
        return True, "a stockout signal is active."
    if EVENT_BASED_REPLENISHMENT_RULES["trigger_when_inventory_position_lte_zero"] and inventory_position <= 0:
        return True, "inventory position is zero or negative."
    if current_inventory <= 0:
        return True, "current inventory is zero or negative."
    if inventory_position <= low_inventory_trigger:
        return True, "inventory position is below the configured days-of-supply trigger."
    if _bool(row.get("recent_event_flag")):
        return True, "a recent event trigger is active."
    if _bool(row.get("promotion_sensitive_flag")) and row.get("seasonality_class") in {"SEASONAL_BUILDUP", "PEAK_SEASON"}:
        return True, "promotion-sensitive demand is entering a seasonal/event period."
    if row.get("seasonality_class") == "SEASONAL_BUILDUP" and inventory_position < p_forecast:
        return True, "seasonal buildup demand is above inventory position."
    if row.get("vitality_class") == "VITAL" and inventory_position <= low_inventory_trigger:
        return True, "vital SKU has very low inventory."
    return False, "no stockout, low-inventory, or event trigger is active."


def _one_to_one_order_trigger(row: pd.Series) -> tuple[bool, str, float]:
    """Return whether a one-to-one SKU has a real replacement trigger."""
    stockout_units = _float(row.get("stockout_units"))
    inventory_position = _float(row.get("inventory_position"))
    current_inventory = _float(row.get("current_inventory"))
    if ONE_TO_ONE_REPLACEMENT_RULES["trigger_when_stockout"] and (_bool(row.get("stockout_signal")) or stockout_units > 0):
        return True, "stockout or replacement backlog", max(stockout_units, 1.0)
    if ONE_TO_ONE_REPLACEMENT_RULES["trigger_when_inventory_position_lte_zero"] and inventory_position <= 0:
        return True, "inventory position is zero or negative", max(_float(row.get("moq")), 1.0)
    if current_inventory <= 0:
        return True, "current inventory is zero or negative", max(_float(row.get("moq")), 1.0)
    if ONE_TO_ONE_REPLACEMENT_RULES["trigger_when_recent_outbound_exists"]:
        recent_outbound = _float(row.get("total_outbound_quantity")) > 0 and (
            _float(row.get("days_since_last_movement"), default=999999)
            <= ONE_TO_ONE_REPLACEMENT_RULES["recent_outbound_lookback_days"]
        )
        if recent_outbound:
            return True, "recent outbound or issue demand", max(_float(row.get("total_outbound_quantity")), 1.0)
    return False, "no stockout, issue, or replacement trigger", 0.0


def _safety_stock(row: pd.Series, context: dict) -> int:
    """Calculate safety stock from demand and lead-time uncertainty."""
    safety_stock = _safety_factor(row) * context["std_demand_during_lead_time"]
    if row.get("inventory_priority_class") == "CRITICAL_PRIORITY":
        safety_stock *= INVENTORY_PARAMETER_ADJUSTMENTS["critical_safety_stock_multiplier"]
    elif row.get("inventory_priority_class") == "HIGH_PRIORITY":
        safety_stock *= INVENTORY_PARAMETER_ADJUSTMENTS["high_priority_safety_stock_multiplier"]
    if row.get("demand_adjusted_procurement_risk_class") == "HIGH":
        safety_stock *= INVENTORY_PARAMETER_ADJUSTMENTS["supplier_high_risk_safety_stock_multiplier"]
    elif row.get("demand_adjusted_procurement_risk_class") == "MEDIUM":
        safety_stock *= INVENTORY_PARAMETER_ADJUSTMENTS["supplier_medium_risk_safety_stock_multiplier"]
    if (
        _float(row.get("average_forecast_confidence_score"), 1.0) < 0.60
        and row.get("vitality_class") in {"VITAL", "IMPORTANT"}
    ):
        safety_stock *= INVENTORY_PARAMETER_ADJUSTMENTS["low_forecast_confidence_safety_stock_multiplier"]
    if row.get("movement_class") == "NON_MOVING" and row.get("vitality_class") == "NORMAL":
        safety_stock *= INVENTORY_PARAMETER_ADJUSTMENTS["non_moving_cap_multiplier"]
    safety_stock = max(safety_stock, INVENTORY_PARAMETER_LIMITS["minimum_safety_stock"])
    return _round_units(safety_stock)


def _eoq(row: pd.Series, context: dict) -> float:
    """Calculate EOQ as a reference quantity."""
    annual_demand = max(context["average_daily_demand"] * 365, 0.0)
    if annual_demand <= 0:
        return INVENTORY_PARAMETER_DEFAULTS["minimum_order_quantity"]
    setup_cost = _float(row.get("estimated_fixed_order_cost"))
    if setup_cost <= 0:
        setup_cost = INVENTORY_PARAMETER_DEFAULTS["fallback_order_setup_cost"]
    unit_cost = _selected_unit_cost(row)
    holding_rate = sum(HOLDING_COST_COMPONENTS.values()) or INVENTORY_PARAMETER_DEFAULTS["fallback_holding_cost_rate"]
    annual_holding_cost_per_unit = unit_cost * holding_rate
    if annual_holding_cost_per_unit <= 0:
        annual_holding_cost_per_unit = max(unit_cost, 1.0) * INVENTORY_PARAMETER_DEFAULTS["fallback_holding_cost_rate"]
    eoq = math.sqrt((2 * annual_demand * setup_cost) / annual_holding_cost_per_unit)
    return max(eoq, INVENTORY_PARAMETER_LIMITS["minimum_eoq"])


def _constrained_order_quantity(base_quantity: float, row: pd.Series, context: dict, flags: dict, allow_zero: bool) -> int:
    """Apply yield, MOQ, batch, and cap constraints in sequence."""
    quantity = max(_float(base_quantity), 0.0)
    if quantity <= 0 and allow_zero:
        return 0
    quantity, yield_applied = apply_yield_adjustment(quantity, row.get("expected_yield_rate"))
    if yield_applied:
        flags["yield_adjustment_applied"] = True
        flags["warning_codes"].append("LOW_YIELD_REQUIRES_EXTRA_ORDERING")
    quantity, moq_applied = apply_moq(quantity, row.get("moq"))
    if moq_applied:
        flags["moq_adjustment_applied"] = True
    quantity, batch_applied = round_to_batch_size(quantity, row.get("batch_size"))
    if batch_applied:
        flags["batch_rounding_applied"] = True
        flags["warning_codes"].append("BATCH_ROUNDING_INCREASED_ORDER")
    quantity, cap_applied, cap_conflict = apply_order_cap(quantity, row, context)
    if cap_applied:
        flags["perishability_cap_applied"] = True
        flags["warning_codes"].append("ORDER_QUANTITY_CAPPED_BY_EXPIRY_OR_MOVEMENT")
        if row.get("perishability_class") in {"SPOILAGE_RISK", "EXPIRY_TRACKED", "PERISHABLE"} or _bool(row.get("perishable")):
            flags["warning_codes"].append("PERISHABLE_ORDER_CAPPED")
    quantity, position_cap_applied, position_cap_conflict = apply_position_aware_cap(quantity, row, context, flags)
    if position_cap_applied:
        flags["existing_inventory_cap_applied"] = True
        flags["warning_codes"].append("ORDER_QUANTITY_CAPPED_BY_EXISTING_INVENTORY")
    if cap_conflict or _high_moq_vs_demand(row, context, quantity):
        flags["warning_codes"].append("HIGH_MOQ_MAY_CAUSE_OVERSTOCK")
    if position_cap_conflict:
        flags["warning_codes"].append("HIGH_MOQ_MAY_CAUSE_OVERSTOCK")
        flags["warning_codes"].append("ORDER_QUANTITY_CAPPED_BY_EXPIRY_OR_MOVEMENT")
    return _round_units(quantity)


def apply_yield_adjustment(quantity: float, expected_yield_rate) -> tuple[float, bool]:
    """Gross up quantity for expected yield."""
    yield_rate = _float(expected_yield_rate)
    if yield_rate <= 0:
        yield_rate = INVENTORY_PARAMETER_DEFAULTS["default_yield_rate"]
    if yield_rate < INVENTORY_PARAMETER_DEFAULTS["minimum_yield_rate"]:
        yield_rate = INVENTORY_PARAMETER_DEFAULTS["minimum_yield_rate"]
    gross_quantity = quantity / yield_rate
    return gross_quantity, gross_quantity > quantity


def apply_moq(quantity: float, moq) -> tuple[float, bool]:
    """Apply minimum order quantity."""
    minimum = max(_float(moq), INVENTORY_PARAMETER_DEFAULTS["minimum_order_quantity"])
    if quantity < minimum:
        return minimum, True
    return quantity, False


def round_to_batch_size(quantity: float, batch_size) -> tuple[float, bool]:
    """Round quantity upward to a batch multiple."""
    batch = max(_float(batch_size), INVENTORY_PARAMETER_DEFAULTS["minimum_batch_size"])
    if batch <= 1:
        return quantity, False
    rounded = math.ceil(quantity / batch) * batch
    return rounded, rounded > quantity


def apply_order_cap(quantity: float, row: pd.Series, context: dict) -> tuple[float, bool, bool]:
    """Cap excessive quantities for expiry, movement, and seasonal drawdown cases."""
    cap = _order_cap_quantity(row, context)
    if cap <= 0 or quantity <= cap:
        return quantity, False, False
    minimum_feasible = max(_float(row.get("moq")), INVENTORY_PARAMETER_DEFAULTS["minimum_order_quantity"])
    if cap < minimum_feasible:
        return quantity, True, True
    capped_quantity, batch_applied = round_to_batch_size(cap, row.get("batch_size"))
    return capped_quantity, True, capped_quantity > cap or batch_applied


def apply_position_aware_cap(quantity: float, row: pd.Series, context: dict, flags: dict) -> tuple[float, bool, bool]:
    """Cap orders when current inventory already covers the policy-specific days of supply."""
    if not INVENTORY_POSITION_CAP_RULES["apply_position_aware_cap"] or not _position_cap_applies(row):
        return quantity, False, False
    if _position_cap_override(row):
        if _float(row.get("current_inventory")) > 0 or _float(row.get("inventory_position")) > 0:
            flags["additional_reasons"].append("Stockout, vital, or critical recovery overrides the position-aware cap.")
        return quantity, False, False

    existing_position = max(_float(row.get("inventory_position")), _float(row.get("current_inventory")), 0.0)
    max_allowed_position = _position_cap_quantity(row, context)
    if existing_position >= max_allowed_position:
        flags["no_order_recommended_flag"] = True
        if row.get("inventory_model_type") == "EVENT_BASED_REPLENISHMENT":
            flags["no_order_event_based"] = True
        if row.get("inventory_model_type") == "ONE_TO_ONE_REPLACEMENT":
            flags["no_order_one_to_one"] = True
        flags["additional_reasons"].append(
            "No order recommended because current inventory already exceeds the allowed days-of-supply cap."
        )
        return 0.0, True, False

    position_after_order = existing_position + quantity
    if position_after_order <= max_allowed_position:
        return quantity, False, False

    max_additional_quantity = max_allowed_position - existing_position
    minimum_feasible = max(_float(row.get("moq")), INVENTORY_PARAMETER_DEFAULTS["minimum_order_quantity"])
    if max_additional_quantity < minimum_feasible:
        flags["additional_reasons"].append(
            "MOQ or batch constraints prevent reducing the order below the position-aware cap."
        )
        return quantity, True, True

    reduced_quantity, reduction_possible = _round_down_to_batch_size(max_additional_quantity, row.get("batch_size"))
    if reduction_possible and reduced_quantity > 0:
        flags["additional_reasons"].append("Order quantity was reduced by the position-aware days-of-supply cap.")
        return reduced_quantity, True, False
    flags["additional_reasons"].append("Batch constraints prevent reducing the order below the position-aware cap.")
    return quantity, True, True


def _mark_existing_inventory_no_order_cap(row: pd.Series, context: dict, flags: dict) -> None:
    """Mark no-order cases where existing inventory already exceeds the position cap."""
    if not INVENTORY_POSITION_CAP_RULES["apply_position_aware_cap"] or not _position_cap_applies(row):
        return
    if _position_cap_override(row):
        return
    existing_position = max(_float(row.get("inventory_position")), _float(row.get("current_inventory")), 0.0)
    if existing_position >= _position_cap_quantity(row, context):
        flags["existing_inventory_cap_applied"] = True
        flags["warning_codes"].append("ORDER_QUANTITY_CAPPED_BY_EXISTING_INVENTORY")
        flags["additional_reasons"].append(
            "No order recommended because current inventory already exceeds the allowed days-of-supply cap."
        )


def _order_cap_quantity(row: pd.Series, context: dict) -> int:
    """Calculate an order cap based on days of supply."""
    days = INVENTORY_PARAMETER_LIMITS["maximum_order_days_of_supply_default"]
    if row.get("movement_class") == "NON_MOVING":
        days = INVENTORY_PARAMETER_LIMITS["maximum_order_days_of_supply_non_moving"]
    elif row.get("perishability_class") == "SPOILAGE_RISK":
        days = INVENTORY_PARAMETER_LIMITS["maximum_order_days_of_supply_spoilage_risk"]
    elif row.get("seasonality_class") == "SEASONAL_DRAWDOWN":
        days = INVENTORY_PARAMETER_LIMITS["maximum_order_days_of_supply_seasonal_drawdown"]
    elif row.get("perishability_class") in {"EXPIRY_TRACKED", "PERISHABLE"} or _bool(row.get("perishable")):
        days = INVENTORY_PARAMETER_LIMITS["maximum_order_days_of_supply_perishable"]
    return _round_units(max(context["average_daily_demand"] * days, INVENTORY_PARAMETER_DEFAULTS["minimum_order_quantity"]))


def _position_cap_applies(row: pd.Series) -> bool:
    """Return True for policies/classes that should consider current inventory before ordering."""
    return bool(
        row.get("inventory_model_type") in {"EVENT_BASED_REPLENISHMENT", "ONE_TO_ONE_REPLACEMENT"}
        or row.get("movement_class") == "NON_MOVING"
        or row.get("inventory_priority_class") == "LOW_PRIORITY"
    )


def _position_cap_override(row: pd.Series) -> bool:
    """Return True when stockout/vital/critical recovery should override caps."""
    return bool(
        _bool(row.get("stockout_signal"))
        or _float(row.get("stockout_units")) > 0
        or row.get("vitality_class") == "VITAL"
        or row.get("inventory_priority_class") == "CRITICAL_PRIORITY"
    )


def _position_cap_quantity(row: pd.Series, context: dict) -> float:
    """Return max allowed inventory position for position-aware cap checks."""
    days = INVENTORY_PARAMETER_LIMITS["maximum_order_days_of_supply_default"]
    if row.get("inventory_model_type") == "EVENT_BASED_REPLENISHMENT":
        days = INVENTORY_POSITION_CAP_RULES["event_based_max_days_of_supply"]
    elif row.get("inventory_model_type") == "ONE_TO_ONE_REPLACEMENT":
        days = INVENTORY_POSITION_CAP_RULES["one_to_one_max_days_of_supply"]
    if row.get("movement_class") == "NON_MOVING":
        days = min(days, INVENTORY_POSITION_CAP_RULES["non_moving_max_days_of_supply"])
    if row.get("inventory_priority_class") == "LOW_PRIORITY":
        days = min(days, INVENTORY_POSITION_CAP_RULES["low_priority_max_days_of_supply"])
    return max(context["average_daily_demand"] * days, INVENTORY_PARAMETER_DEFAULTS["minimum_order_quantity"])


def _round_down_to_batch_size(quantity: float, batch_size) -> tuple[float, bool]:
    """Round quantity downward to a batch multiple when reducing an order."""
    batch = max(_float(batch_size), INVENTORY_PARAMETER_DEFAULTS["minimum_batch_size"])
    if batch <= 1:
        return max(quantity, 0.0), True
    rounded = math.floor(quantity / batch) * batch
    return rounded, rounded > 0


def _newsvendor_critical_ratio(row: pd.Series) -> float:
    """Calculate shortage-vs-excess critical ratio."""
    shortage_cost = max(_float(row.get("stockout_penalty_per_unit")), 0.0)
    unit_cost = _selected_unit_cost(row)
    holding_rate = sum(HOLDING_COST_COMPONENTS.values()) or INVENTORY_PARAMETER_DEFAULTS["fallback_holding_cost_rate"]
    excess_cost = max(_float(row.get("overstock_penalty_per_unit")), 0.0) + unit_cost * holding_rate
    if row.get("perishability_class") in {"SPOILAGE_RISK", "EXPIRY_TRACKED", "PERISHABLE"} or _bool(row.get("expiry_risk_signal")):
        excess_cost += unit_cost * 0.25
    denominator = shortage_cost + excess_cost
    if denominator <= 0:
        return 0.5
    return round(max(0.05, min(0.99, shortage_cost / denominator)), 3)


def _empty_flags(row: pd.Series) -> dict:
    """Initialize quantity diagnostic flags."""
    supplier_review = _bool(row.get("supplier_review_signal")) or _bool(row.get("recommended_supplier_requires_review"))
    phase4_review = _bool(row.get("phase4_review_flag"))
    warning_codes = []
    if supplier_review:
        warning_codes.append("SUPPLIER_REVIEW_BEFORE_ORDER")
    if phase4_review:
        warning_codes.append("PHASE4_REVIEW_BEFORE_FINAL_POLICY")
    return {
        "warning_codes": warning_codes,
        "additional_reasons": [],
        "moq_adjustment_applied": False,
        "batch_rounding_applied": False,
        "yield_adjustment_applied": False,
        "perishability_cap_applied": False,
        "existing_inventory_cap_applied": False,
        "stockout_order_boost_applied": False,
        "supplier_review_before_order": supplier_review,
        "phase4_review_before_final_policy": phase4_review,
        "no_order_recommended_flag": False,
        "no_order_event_based": False,
        "no_order_one_to_one": False,
    }


def _finalize_flags_and_reasons(row: pd.Series, flags: dict, parameters: dict, input_reason: str) -> dict:
    """Create final warning and reason fields."""
    warning_codes = _unique(flags["warning_codes"])
    reasons = []
    if flags["moq_adjustment_applied"]:
        reasons.append("MOQ increased the calculated quantity.")
    if flags["batch_rounding_applied"]:
        reasons.append("Batch rounding increased the calculated quantity.")
    if flags["yield_adjustment_applied"]:
        reasons.append("Yield adjustment increased the order quantity.")
    if flags["perishability_cap_applied"]:
        reasons.append("Order quantity was capped for expiry, movement, or seasonality risk.")
    if flags["existing_inventory_cap_applied"]:
        reasons.append("Existing inventory already exceeds the position-aware days-of-supply cap.")
    if flags["stockout_order_boost_applied"]:
        reasons.append("Stockout signal boosted the recommended order quantity.")
    if flags["supplier_review_before_order"]:
        reasons.append("Supplier should be reviewed before ordering.")
    if flags["phase4_review_before_final_policy"]:
        reasons.append("Phase 4 production/BOM/MRP review should happen before final policy.")
    if flags["no_order_recommended_flag"]:
        reasons.append("No order is recommended because no policy trigger is active.")
    reasons.extend(flags["additional_reasons"])
    if row.get("policy_review_required") is True or _bool(row.get("policy_review_required")):
        reasons.append("Policy review flag remains active.")
    if not reasons:
        reasons.append("No major quantity constraints were applied.")

    calculation_reason = str(parameters.get("parameter_calculation_reason", "") or "")
    if input_reason:
        calculation_reason = f"{calculation_reason} {input_reason}".strip()

    return {
        "quantity_constraint_flag": bool(warning_codes),
        "quantity_constraint_reason": " ".join(reasons),
        "warning_codes": ";".join(warning_codes),
        "moq_adjustment_applied": flags["moq_adjustment_applied"],
        "batch_rounding_applied": flags["batch_rounding_applied"],
        "yield_adjustment_applied": flags["yield_adjustment_applied"],
        "perishability_cap_applied": flags["perishability_cap_applied"],
        "existing_inventory_cap_applied": flags["existing_inventory_cap_applied"],
        "stockout_order_boost_applied": flags["stockout_order_boost_applied"],
        "supplier_review_before_order": flags["supplier_review_before_order"],
        "phase4_review_before_final_policy": flags["phase4_review_before_final_policy"],
        "no_order_recommended_flag": flags["no_order_recommended_flag"],
        "no_order_event_based": flags["no_order_event_based"],
        "no_order_one_to_one": flags["no_order_one_to_one"],
        "parameter_calculation_reason": calculation_reason,
    }


def _high_moq_vs_demand(row: pd.Series, context: dict, quantity: float) -> bool:
    """Return True when MOQ/batch causes high order coverage."""
    days_of_supply = quantity / max(context["average_daily_demand"], 1.0)
    return days_of_supply > INVENTORY_PARAMETER_LIMITS["maximum_order_days_of_supply_default"]


def _selected_unit_cost(row: pd.Series) -> float:
    """Select procurement cost, inventory cost, then safe fallback."""
    unit_cost = _float(row.get("unit_cost_procurement"))
    if unit_cost <= 0:
        unit_cost = _float(row.get("unit_cost_inventory"))
    return unit_cost if unit_cost > 0 else 1.0


def _safety_factor(row: pd.Series) -> float:
    """Return configured safety factor from service level output."""
    safety_factor = _float(row.get("safety_factor_z"))
    return safety_factor if safety_factor > 0 else 1.65


def _round_units(value: float) -> int:
    """Round non-negative inventory quantities to whole units."""
    return int(math.ceil(max(_float(value), 0.0)))


def _unique(values: list[str]) -> list[str]:
    """Return unique values preserving order."""
    seen = set()
    unique_values = []
    for value in values:
        if value and value not in seen:
            unique_values.append(value)
            seen.add(value)
    return unique_values


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


def _parameter_output_columns(df: pd.DataFrame) -> list[str]:
    """Return focused parameter output columns."""
    columns = [
        "sku_id",
        "product_name",
        "category",
        "inventory_model_type",
        "review_policy",
        "policy_urgency",
        "policy_review_required",
        "policy_review_reason",
        "service_level_target",
        "safety_factor_z",
        "average_daily_demand",
        "demand_std_daily",
        "coefficient_of_variation",
        "demand_behavior_class",
        "expected_lead_time_days",
        "lead_time_std_days",
        "mean_demand_during_lead_time",
        "std_demand_during_lead_time",
        "safety_stock",
        "reorder_point",
        "eoq",
        "eoq_rounded",
        "recommended_order_quantity",
        "min_stock_level",
        "max_stock_level",
        "reorder_point_s",
        "order_quantity_Q",
        "review_period_R",
        "order_up_to_level_S",
        "base_stock_level",
        "newsvendor_critical_ratio",
        "moq",
        "batch_size",
        "expected_yield_rate",
        "final_feasible_order_quantity",
        "recommended_supplier_id",
        "backup_supplier_id",
        "recommended_supplier_feasible",
        "recommended_supplier_requires_review",
        "split_sourcing_recommendation",
        "recommended_primary_share",
        "recommended_backup_share",
        "quantity_constraint_flag",
        "quantity_constraint_reason",
        "moq_adjustment_applied",
        "batch_rounding_applied",
        "yield_adjustment_applied",
        "perishability_cap_applied",
        "existing_inventory_cap_applied",
        "stockout_order_boost_applied",
        "supplier_review_before_order",
        "phase4_review_before_final_policy",
        "no_order_recommended_flag",
        "no_order_event_based",
        "no_order_one_to_one",
        "parameter_calculation_reason",
        "warning_codes",
    ]
    return [column for column in columns if column in df.columns]
