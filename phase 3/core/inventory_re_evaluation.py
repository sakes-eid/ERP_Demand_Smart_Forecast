"""Recommendation-only inventory re-evaluation engine for Phase 3."""

from __future__ import annotations

from typing import Any

import pandas as pd

from config import (
    RE_EVALUATION_AUTO_APPLY,
    RE_EVALUATION_CONFIG,
    RE_EVALUATION_SIGNAL_WEIGHTS,
    RE_EVALUATION_THRESHOLDS,
)


def build_inventory_re_evaluation(
    inventory_clean: pd.DataFrame,
    inventory_batches_clean: pd.DataFrame,
    inventory_movements_clean: pd.DataFrame,
    planning_context: pd.DataFrame,
    inventory_classification: pd.DataFrame,
    inventory_service_levels: pd.DataFrame,
    inventory_policy: pd.DataFrame,
    inventory_policy_parameters: pd.DataFrame,
    inventory_status: pd.DataFrame,
    inventory_action_recommendations: pd.DataFrame,
    inventory_costs: pd.DataFrame,
    warehouse_slotting: pd.DataFrame,
    batch_slotting: pd.DataFrame,
    location_utilization: pd.DataFrame,
    space_utilization: pd.DataFrame,
    warehouse_travel_costs: pd.DataFrame,
    warehouse_visual_skus: pd.DataFrame,
    warehouse_visual_locations: pd.DataFrame,
    warehouse_visual_batches: pd.DataFrame,
    warehouse_visual_summary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build re-evaluation recommendations without changing current parameters."""
    context = _merge_context(
        inventory_policy_parameters,
        [
            inventory_clean,
            planning_context,
            inventory_classification,
            inventory_service_levels,
            inventory_policy,
            inventory_status,
            inventory_action_recommendations,
            inventory_costs,
            warehouse_slotting,
            warehouse_travel_costs,
            warehouse_visual_skus,
        ],
    )
    re_eval_rows = [_evaluate_sku(row.to_dict()) for _, row in context.iterrows()]
    re_eval_df = pd.DataFrame(re_eval_rows)
    adjustment_df = _build_adjustment_output(re_eval_df)
    summary_df = _build_summary(re_eval_df)
    return re_eval_df[_RE_EVALUATION_COLUMNS], adjustment_df[_ADJUSTMENT_COLUMNS], summary_df


def _merge_context(base_df: pd.DataFrame, source_dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """Merge available SKU context without suffix clutter."""
    if base_df.empty:
        return pd.DataFrame()
    merged = base_df.copy()
    if "sku_id" not in merged.columns:
        return merged
    merged["sku_id"] = merged["sku_id"].astype(str).str.strip()
    for source in source_dfs:
        if source.empty or "sku_id" not in source.columns:
            continue
        source = source.copy()
        source["sku_id"] = source["sku_id"].astype(str).str.strip()
        keep = ["sku_id"] + [column for column in source.columns if column != "sku_id" and column not in merged.columns]
        if len(keep) <= 1:
            continue
        merged = merged.merge(source[keep].drop_duplicates("sku_id"), on="sku_id", how="left")
    return merged


def _evaluate_sku(row: dict[str, Any]) -> dict[str, Any]:
    status = _text(row.get("main_inventory_status")).upper()
    flags = _joined_flags(
        row.get("secondary_status_flags"),
        row.get("warning_codes"),
        row.get("slotting_warning_flags"),
        row.get("visual_warning_flags"),
        row.get("travel_warning_flags"),
    )
    abc = _text(row.get("abc_class")).upper()
    movement = _text(row.get("movement_class")).upper()
    vitality = _text(row.get("vitality_class")).upper()
    priority = _text(row.get("inventory_priority_class")).upper()
    perishability = _text(row.get("perishability_class")).upper()
    seasonality = _text(row.get("seasonality_class")).upper()
    model = _text(row.get("inventory_model_type"))

    stockout_signal = status == "STOCKOUT" or _bool(row.get("stockout_signal")) or _num(row.get("stockout_units")) > 0
    zero_signal = status == "ZERO_STOCK" or _bool(row.get("zero_inventory_signal"))
    critical_low_signal = status == "CRITICAL_LOW_STOCK"
    reorder_signal = status == "REORDER_NOW"
    overstock_signal = status == "OVERSTOCK" or "OVERSTOCK_RISK_BY_DAYS_OF_SUPPLY" in flags
    high_days_signal = _high_days_signal(row, perishability, movement)
    expiry_signal = _num(row.get("near_expiry_units")) > 0 or _num(row.get("expired_units")) > 0 or "EXPIRED_STOCK" in flags
    near_expiry_signal = _num(row.get("near_expiry_units")) > 0
    expired_signal = _num(row.get("expired_units")) > 0
    non_moving_signal = _bool(row.get("non_moving_signal")) or movement == "NON_MOVING" or "NON_MOVING" in flags
    dead_stock_signal = _bool(row.get("dead_stock_signal")) or "DEAD_STOCK" in flags
    supplier_signal = _supplier_signal(row, flags)
    warehouse_capacity_signal = _warehouse_capacity_signal(row, flags)
    receiving_capacity_signal = _bool(row.get("sku_causes_projected_staging_pressure")) or _bool(row.get("replenishment_location_projected_over_capacity_flag"))
    slotting_signal = any(code in flags for code in ["NO_FEASIBLE_LOCATION_FOUND", "SLOW_OR_NON_MOVING_ITEM_IN_FAST_PICK", "PROJECTED_LOCATION_OVER_CAPACITY"])
    travel_signal = _travel_signal(row, flags)
    z_signal = any(code in flags for code in ["FAST_MOVING_ITEM_NOT_ERGONOMIC", "FRAGILE_ITEM_HIGH_LEVEL", "HEAVY_ITEM_NOT_LOW_LEVEL"])
    forecast_signal = _forecast_uncertainty_signal(row)
    high_cost_signal = _num(row.get("total_relevant_inventory_cost")) >= RE_EVALUATION_THRESHOLDS["high_total_relevant_cost"]

    shortage_score = _score_shortage(row, stockout_signal, zero_signal, critical_low_signal, reorder_signal, supplier_signal)
    excess_score = _score_excess(row, overstock_signal, high_days_signal, non_moving_signal, dead_stock_signal)
    spoilage_score = _score_spoilage(row, expiry_signal, near_expiry_signal, expired_signal, perishability, seasonality)
    supplier_score = _score_supplier(row, supplier_signal)
    warehouse_score = _score_warehouse(warehouse_capacity_signal, receiving_capacity_signal, slotting_signal, travel_signal, z_signal)
    forecast_score = _score_forecast(row, forecast_signal)
    cost_score = _score_cost(row, high_cost_signal)
    pressure = _clamp(shortage_score + excess_score + spoilage_score + supplier_score + warehouse_score + forecast_score + cost_score, 0, 1)

    order_review = _order_review_details(row, flags, receiving_capacity_signal)
    direction = _direction(
        row,
        shortage_score,
        excess_score,
        spoilage_score,
        warehouse_score,
        supplier_signal,
        forecast_signal,
        stockout_signal,
        receiving_capacity_signal,
        flags,
        order_review,
    )
    current_service = _num(row.get("service_level_target"))
    (
        raw_recommended_service,
        recommended_service,
        service_guardrail_action,
        service_guardrail_reason,
        service_reason,
    ) = _recommend_service_level(row, direction, current_service, shortage_score, excess_score, spoilage_score)
    current_ss = _num(row.get("safety_stock"))
    recommended_ss, ss_reason = _recommend_stock_parameter(
        current_ss,
        direction,
        shortage_score,
        excess_score + spoilage_score,
        RE_EVALUATION_CONFIG["max_safety_stock_adjustment_pct_per_cycle"],
        "safety stock",
    )
    current_rop = _num(row.get("reorder_point"))
    raw_recommended_rop, rop_reason = _recommend_stock_parameter(
        current_rop,
        direction,
        shortage_score,
        excess_score + spoilage_score,
        RE_EVALUATION_CONFIG["max_reorder_point_adjustment_pct_per_cycle"],
        "reorder point",
    )
    (
        recommended_rop,
        average_daily_demand_used,
        expected_lead_time_days_used,
        estimated_lead_time_demand,
        minimum_recommended_reorder_point,
        rop_lead_time_guardrail_applied,
        rop_guardrail_action,
        rop_guardrail_reason,
    ) = _apply_rop_guardrail(row, raw_recommended_rop, recommended_ss)
    current_cap_days = _current_order_cap_days(row)
    recommended_cap_days, cap_reason = _recommend_order_cap(row, direction, current_cap_days, warehouse_score, spoilage_score, excess_score, shortage_score)

    policy_recommendation, policy_reason = _policy_review(row, direction, flags, model)
    supplier_recommendation, supplier_reason = _supplier_review(row, supplier_signal, flags)
    warehouse_recommendation, warehouse_reason = _warehouse_review(row, receiving_capacity_signal, slotting_signal, travel_signal, z_signal, expiry_signal)
    order_qty_review = order_review["recommended_order_quantity_review_flag"]
    order_qty_review_reason = _order_quantity_review_reason(row, order_review, flags)
    eoq_recommendation, eoq_reason = _eoq_review(row, order_review, high_cost_signal, forecast_signal)
    order_model_recommendation, order_model_reason = _order_model_review(
        row,
        order_review,
        direction,
        high_cost_signal,
        stockout_signal or critical_low_signal or reorder_signal,
        overstock_signal or high_days_signal,
        expiry_signal,
    )
    confidence, confidence_level = _confidence(row, direction, pressure, shortage_score, excess_score, spoilage_score, supplier_signal, receiving_capacity_signal, forecast_signal, flags)
    review_required, review_level, review_reason = _human_review(
        row,
        direction,
        confidence,
        pressure,
        receiving_capacity_signal,
        supplier_signal,
        forecast_signal,
        flags,
    )

    recommendation_strength = _recommendation_strength(direction, confidence, review_level, pressure, order_review)
    buffer_scope, guarded_explanation = _buffer_adjustment_scope(direction, service_guardrail_action)
    recommendation_basis = _recommendation_basis(
        direction,
        shortage_score,
        excess_score,
        spoilage_score,
        supplier_score,
        warehouse_score,
        forecast_score,
        review_level,
    )
    auto_apply_allowed = bool(RE_EVALUATION_AUTO_APPLY.get("allow_auto_apply_in_step_11", False)) and False
    re_eval_reason = _reason(direction, shortage_score, excess_score, spoilage_score, warehouse_score, supplier_score, cost_score)
    result = {
        "sku_id": row.get("sku_id"),
        "product_name": row.get("product_name"),
        "category": row.get("category"),
        "abc_class": row.get("abc_class"),
        "xyz_class": row.get("xyz_class"),
        "fsn_class": row.get("fsn_class"),
        "movement_class": row.get("movement_class"),
        "vitality_class": row.get("vitality_class"),
        "perishability_class": row.get("perishability_class"),
        "seasonality_class": row.get("seasonality_class"),
        "inventory_priority_class": row.get("inventory_priority_class"),
        "main_inventory_status": row.get("main_inventory_status"),
        "primary_action": row.get("primary_action"),
        "action_priority": row.get("action_priority"),
        "main_cost_driver": row.get("main_cost_driver"),
        "cost_risk_level": row.get("cost_risk_level"),
        "current_service_level_target": round(current_service, 3),
        "current_safety_stock": round(current_ss, 2),
        "current_reorder_point": round(current_rop, 2),
        "current_eoq": round(_num(row.get("eoq")), 2),
        "current_recommended_order_quantity": round(_num(row.get("recommended_order_quantity")), 2),
        "inventory_model_type": row.get("inventory_model_type"),
        "review_policy": row.get("review_policy"),
        "stockout_re_eval_signal": stockout_signal,
        "zero_stock_re_eval_signal": zero_signal,
        "critical_low_stock_re_eval_signal": critical_low_signal,
        "reorder_now_re_eval_signal": reorder_signal,
        "overstock_re_eval_signal": overstock_signal,
        "high_days_of_supply_signal": high_days_signal,
        "expiry_re_eval_signal": expiry_signal,
        "near_expiry_re_eval_signal": near_expiry_signal,
        "expired_stock_re_eval_signal": expired_signal,
        "non_moving_re_eval_signal": non_moving_signal,
        "dead_stock_re_eval_signal": dead_stock_signal,
        "supplier_risk_re_eval_signal": supplier_signal,
        "supplier_delay_buffer_signal": _num(row.get("lead_time_std_days")) > 3,
        "supplier_review_re_eval_signal": supplier_signal,
        "warehouse_capacity_re_eval_signal": warehouse_capacity_signal,
        "receiving_capacity_re_eval_signal": receiving_capacity_signal,
        "slotting_re_eval_signal": slotting_signal,
        "travel_re_eval_signal": travel_signal,
        "z_level_re_eval_signal": z_signal,
        "forecast_uncertainty_re_eval_signal": forecast_signal,
        "high_cost_re_eval_signal": high_cost_signal,
        "shortage_pressure_score": round(shortage_score, 3),
        "excess_pressure_score": round(excess_score, 3),
        "spoilage_pressure_score": round(spoilage_score, 3),
        "supplier_pressure_score": round(supplier_score, 3),
        "warehouse_pressure_score": round(warehouse_score, 3),
        "forecast_pressure_score": round(forecast_score, 3),
        "cost_pressure_score": round(cost_score, 3),
        "total_re_evaluation_pressure_score": round(pressure, 3),
        "recommended_adjustment_direction": direction,
        "recommendation_strength": recommendation_strength,
        "recommendation_basis": recommendation_basis,
        "auto_apply_allowed": auto_apply_allowed,
        "buffer_adjustment_scope": buffer_scope,
        "guarded_reduction_explanation": guarded_explanation,
        "raw_recommended_service_level_target": round(raw_recommended_service, 3),
        "recommended_service_level_target": round(recommended_service, 3),
        "service_level_adjustment": round(recommended_service - current_service, 3),
        "service_level_guardrail_action": service_guardrail_action,
        "service_level_guardrail_reason": service_guardrail_reason,
        "recommended_safety_stock": round(recommended_ss, 2),
        "safety_stock_adjustment_units": round(recommended_ss - current_ss, 2),
        "safety_stock_adjustment_pct": round(_pct_change(current_ss, recommended_ss), 3),
        "average_daily_demand_used_for_rop": round(average_daily_demand_used, 4),
        "expected_lead_time_days_used_for_rop": round(expected_lead_time_days_used, 2),
        "estimated_lead_time_demand": round(estimated_lead_time_demand, 2),
        "minimum_recommended_reorder_point": round(minimum_recommended_reorder_point, 2),
        "recommended_reorder_point": round(recommended_rop, 2),
        "reorder_point_adjustment_units": round(recommended_rop - current_rop, 2),
        "reorder_point_adjustment_pct": round(_pct_change(current_rop, recommended_rop), 3),
        "rop_lead_time_guardrail_applied": rop_lead_time_guardrail_applied,
        "rop_guardrail_action": rop_guardrail_action,
        "rop_guardrail_reason": rop_guardrail_reason,
        "current_order_cap_days": round(current_cap_days, 2),
        "recommended_order_cap_days": round(recommended_cap_days, 2),
        "order_cap_adjustment_days": round(recommended_cap_days - current_cap_days, 2),
        "recommended_order_quantity_review_flag": order_qty_review,
        "recommended_order_quantity_review_reason": order_qty_review_reason,
        "receiving_capacity_order_review_flag": order_review["receiving_capacity_order_review_flag"],
        "moq_overstock_review_flag": order_review["moq_overstock_review_flag"],
        "batch_rounding_review_flag": order_review["batch_rounding_review_flag"],
        "yield_review_flag": order_review["yield_review_flag"],
        "perishability_cap_review_flag": order_review["perishability_cap_review_flag"],
        "phase4_order_review_flag": order_review["phase4_order_review_flag"],
        "supplier_order_review_flag": order_review["supplier_order_review_flag"],
        "quantity_constraint_review_only_flag": order_review["quantity_constraint_review_only_flag"],
        "order_review_type": order_review["order_review_type"],
        "order_review_severity": order_review["order_review_severity"],
        "order_review_info_type": order_review["order_review_info_type"],
        "order_review_info_reason": order_review["order_review_info_reason"],
        "eoq_review_recommendation": eoq_recommendation,
        "eoq_review_reason": eoq_reason,
        "order_model_review_recommendation": order_model_recommendation,
        "order_model_review_reason": order_model_reason,
        "policy_review_recommendation": policy_recommendation,
        "supplier_review_recommendation": supplier_recommendation,
        "warehouse_review_recommendation": warehouse_recommendation,
        "re_evaluation_confidence_score": round(confidence, 3),
        "re_evaluation_confidence_level": confidence_level,
        "requires_human_review": review_required,
        "human_review_level": review_level,
        "re_evaluation_reason": re_eval_reason,
        "service_level_adjustment_reason": service_reason,
        "safety_stock_adjustment_reason": ss_reason,
        "reorder_point_adjustment_reason": rop_reason,
        "order_cap_adjustment_reason": cap_reason,
        "policy_review_reason": policy_reason,
        "supplier_review_reason": supplier_reason,
        "warehouse_review_reason": warehouse_reason,
        "human_review_reason": review_reason,
    }
    return result


def _score_shortage(row, stockout, zero, critical_low, reorder, supplier) -> float:
    score = 0.0
    score += RE_EVALUATION_SIGNAL_WEIGHTS["stockout"] if stockout else 0
    score += RE_EVALUATION_SIGNAL_WEIGHTS["zero_stock"] if zero else 0
    score += RE_EVALUATION_SIGNAL_WEIGHTS["critical_low_stock"] if critical_low else 0
    score += RE_EVALUATION_SIGNAL_WEIGHTS["reorder_now"] if reorder else 0
    if _num(row.get("current_stockout_cost")) >= RE_EVALUATION_THRESHOLDS["high_stockout_cost"]:
        score += 0.12
    if _text(row.get("vitality_class")).upper() == "VITAL" or _text(row.get("inventory_priority_class")).upper() == "CRITICAL_PRIORITY":
        score += 0.10
    if supplier:
        score += 0.05
    return _clamp(score, 0, 1)


def _score_excess(row, overstock, high_days, non_moving, dead_stock) -> float:
    score = 0.0
    score += RE_EVALUATION_SIGNAL_WEIGHTS["overstock"] if overstock else 0
    score += 0.12 if high_days else 0
    score += RE_EVALUATION_SIGNAL_WEIGHTS["non_moving"] if non_moving else 0
    score += RE_EVALUATION_SIGNAL_WEIGHTS["dead_stock"] if dead_stock else 0
    if _num(row.get("current_overstock_cost")) + _num(row.get("current_holding_cost")) >= RE_EVALUATION_THRESHOLDS["high_holding_or_overstock_cost"]:
        score += 0.12
    if "ORDER_QUANTITY_CAPPED_BY_EXISTING_INVENTORY" in _text(row.get("warning_codes")):
        score += 0.08
    return _clamp(score, 0, 1)


def _score_spoilage(row, expiry, near_expiry, expired, perishability, seasonality) -> float:
    score = RE_EVALUATION_SIGNAL_WEIGHTS["expiry"] if expiry else 0.0
    score += 0.08 if near_expiry else 0
    score += 0.12 if expired else 0
    score += 0.08 if perishability in {"SPOILAGE_RISK", "EXPIRY_TRACKED"} else 0
    score += 0.05 if seasonality == "SEASONAL_DRAWDOWN" else 0
    if _num(row.get("expired_stock_cost")) + _num(row.get("near_expiry_risk_cost")) >= RE_EVALUATION_THRESHOLDS["high_expiry_cost"]:
        score += 0.12
    return _clamp(score, 0, 1)


def _score_supplier(row, supplier_signal) -> float:
    score = RE_EVALUATION_SIGNAL_WEIGHTS["supplier_risk"] if supplier_signal else 0.0
    if _num(row.get("demand_adjusted_procurement_risk_score")) >= RE_EVALUATION_THRESHOLDS["high_procurement_risk_score"]:
        score += 0.10
    if _num(row.get("lead_time_std_days")) > 3:
        score += 0.05
    return _clamp(score, 0, 1)


def _score_warehouse(capacity, receiving, slotting, travel, z_warning) -> float:
    score = RE_EVALUATION_SIGNAL_WEIGHTS["warehouse_capacity"] if capacity else 0.0
    score += 0.10 if receiving else 0
    score += 0.06 if slotting else 0
    score += RE_EVALUATION_SIGNAL_WEIGHTS["travel_or_z_warning"] if travel or z_warning else 0
    return _clamp(score, 0, 1)


def _score_forecast(row, signal) -> float:
    score = RE_EVALUATION_SIGNAL_WEIGHTS["forecast_uncertainty"] if signal else 0.0
    if _num(row.get("coefficient_of_variation")) >= 1.0:
        score += 0.05
    return _clamp(score, 0, 1)


def _score_cost(row, signal) -> float:
    score = RE_EVALUATION_SIGNAL_WEIGHTS["high_cost"] if signal else 0.0
    if _num(row.get("total_relevant_inventory_cost")) >= RE_EVALUATION_THRESHOLDS["critical_total_relevant_cost"]:
        score += 0.10
    return _clamp(score, 0, 1)


def _direction(row, shortage, excess, spoilage, warehouse, supplier_signal, forecast_signal, stockout, receiving_capacity, flags, order_review) -> str:
    phase4 = _bool(row.get("phase4_review_flag")) or _bool(row.get("phase4_review_before_final_policy"))
    mandatory_review = phase4 or (_bool(row.get("recommended_supplier_requires_review")) and _num(row.get("recommended_order_quantity")) > 0)
    high_order_cost = _num(row.get("recommended_total_order_cost")) >= RE_EVALUATION_THRESHOLDS["high_order_cost"]
    critical_or_vital = _text(row.get("vitality_class")).upper() == "VITAL" or _text(row.get("inventory_priority_class")).upper() == "CRITICAL_PRIORITY"
    supplier_vs_excess = supplier_signal and (spoilage + excess >= 0.25)
    shortage_capacity_conflict = shortage >= 0.25 and order_review["receiving_capacity_order_review_flag"]
    critical_pressure_conflict = critical_or_vital and shortage >= 0.25 and (spoilage + excess + warehouse) >= 0.30
    costly_capacity_conflict = high_order_cost and shortage >= 0.25 and warehouse >= 0.20
    if (
        (shortage >= 0.25 and (excess + spoilage + warehouse) >= 0.30)
        or (stockout and receiving_capacity)
        or shortage_capacity_conflict
        or critical_pressure_conflict
        or costly_capacity_conflict
        or supplier_vs_excess
    ):
        return "MIXED_SIGNALS"
    if mandatory_review and shortage < 0.25:
        return "REVIEW_ONLY"
    if shortage >= 0.25 and (excess + spoilage) < 0.30:
        return "INCREASE_BUFFER"
    if (excess + spoilage) >= 0.30 and shortage < 0.20:
        return "DECREASE_BUFFER"
    if supplier_signal or forecast_signal or "BATCH_QUANTITY_RECONCILIATION_REVIEW" in flags:
        return "REVIEW_ONLY"
    return "KEEP_STABLE"


def _recommend_service_level(row, direction, current, shortage, excess, spoilage) -> tuple[float, float, str, str, str]:
    max_delta = RE_EVALUATION_CONFIG["max_service_level_adjustment_per_cycle"]
    raw_target = current
    reason = "Service level kept stable because re-evaluation signals are weak or balanced."
    if direction == "INCREASE_BUFFER":
        raw_target += max_delta * max(0.5, shortage)
        reason = "Service level increase recommended because shortage or supplier-risk pressure is elevated."
    elif direction == "DECREASE_BUFFER":
        raw_target -= max_delta * max(0.5, excess + spoilage)
        reason = "Service level decrease recommended because excess, expiry, or non-moving pressure is elevated."
    target = _apply_service_guardrails(row, raw_target)
    guardrail_action = "NO_GUARDRAIL_APPLIED"
    guardrail_reason = "No service-level guardrail changed the raw recommendation."
    if target > raw_target:
        if direction == "DECREASE_BUFFER" and raw_target < current and target >= current:
            guardrail_action = "GUARDRAIL_PROTECTED_NO_REDUCTION"
            guardrail_reason = (
                "Buffer reduction was suggested by excess/expiry pressure, but service level reduction was blocked "
                "by guardrails for IMPORTANT/VITAL/CRITICAL/A-class/fast-moving protection."
            )
            reason = f"{reason} {guardrail_reason}"
        else:
            guardrail_action = "GUARDRAIL_LIMITED_DECREASE"
            guardrail_reason = "Service-level guardrail raised the raw recommendation to a protected minimum."
            reason = f"{reason} {guardrail_reason}"
    elif target < raw_target:
        guardrail_action = "GUARDRAIL_LIMITED_INCREASE"
        guardrail_reason = "Service-level guardrail capped the raw recommendation at the configured maximum."
        reason = f"{reason} {guardrail_reason}"
    return round(raw_target, 3), round(target, 3), guardrail_action, guardrail_reason, reason


def _apply_service_guardrails(row, target: float) -> float:
    target = _clamp(target, RE_EVALUATION_CONFIG["min_service_level"], RE_EVALUATION_CONFIG["max_service_level"])
    if _text(row.get("inventory_priority_class")).upper() == "CRITICAL_PRIORITY":
        target = max(target, RE_EVALUATION_CONFIG["do_not_reduce_critical_below"])
    if _text(row.get("vitality_class")).upper() == "VITAL":
        target = max(target, RE_EVALUATION_CONFIG["do_not_reduce_vital_below"])
    if _text(row.get("movement_class")).upper() == "FAST_MOVING":
        target = max(target, RE_EVALUATION_CONFIG["do_not_reduce_fast_moving_below"])
    if _text(row.get("abc_class")).upper() == "A":
        target = max(target, RE_EVALUATION_CONFIG["do_not_reduce_abc_a_below"])
    return target


def _recommend_stock_parameter(current, direction, positive_pressure, negative_pressure, max_pct, label) -> tuple[float, str]:
    current = max(current, 0)
    if current == 0:
        base = 1.0
    else:
        base = current
    if direction == "INCREASE_BUFFER":
        recommended = current + base * max_pct * max(0.5, positive_pressure)
        return max(recommended, 0), f"{label.title()} increase recommended due to shortage, supplier, or forecast pressure."
    if direction == "DECREASE_BUFFER":
        recommended = current - base * max_pct * max(0.5, negative_pressure)
        return max(recommended, 0), f"{label.title()} reduction recommended due to overstock, expiry, or non-moving pressure."
    return current, f"{label.title()} kept stable pending stronger or clearer re-evaluation signals."


def _recommend_order_cap(row, direction, current_cap, warehouse_score, spoilage_score, excess_score, shortage_score) -> tuple[float, str]:
    pct = RE_EVALUATION_CONFIG["max_order_cap_adjustment_pct_per_cycle"]
    if direction == "DECREASE_BUFFER" or (warehouse_score + spoilage_score + excess_score) >= 0.30:
        return max(1, current_cap * (1 - pct)), "Order cap tightening recommended to reduce overstock, expiry, or warehouse pressure."
    if direction == "INCREASE_BUFFER" and shortage_score >= 0.30 and warehouse_score < 0.20:
        return current_cap * (1 + pct), "Order cap loosening recommended because shortage pressure is high and warehouse pressure is manageable."
    return current_cap, "Order cap kept stable; no safe directional change is recommended."


def _apply_rop_guardrail(row, raw_rop: float, recommended_safety_stock: float) -> tuple[float, float, float, float, float, bool, str, str]:
    avg_missing = _text(row.get("average_daily_demand")) == ""
    lead_missing = _text(row.get("expected_lead_time_days")) == ""
    average_daily_demand = _num(row.get("average_daily_demand"), 1.0)
    expected_lead_time = _num(row.get("expected_lead_time_days"), 7.0)
    if average_daily_demand <= 0:
        average_daily_demand = 1.0
        avg_missing = True
    if expected_lead_time <= 0:
        expected_lead_time = 7.0
        lead_missing = True
    lead_time_demand = average_daily_demand * expected_lead_time
    minimum_rop = max(recommended_safety_stock + lead_time_demand, 0)
    final_rop = max(raw_rop, minimum_rop, 0)
    applied = final_rop > raw_rop
    if avg_missing or lead_missing:
        action = "ROP_REVIEW_REQUIRED"
        reason = "ROP guardrail used fallback demand or lead-time values; review demand/lead-time inputs."
    elif applied:
        action = "ROP_LEAD_TIME_GUARDRAIL_APPLIED"
        reason = "ROP increased to cover recommended safety stock plus expected lead-time demand."
    else:
        action = "NO_GUARDRAIL_APPLIED"
        reason = "ROP already covers recommended safety stock plus expected lead-time demand."
    return final_rop, average_daily_demand, expected_lead_time, lead_time_demand, minimum_rop, applied, action, reason


def _order_review_details(row, flags: str, receiving_capacity_signal: bool) -> dict:
    receiving = receiving_capacity_signal and _num(row.get("recommended_order_quantity")) > 0
    moq = "HIGH_MOQ_MAY_CAUSE_OVERSTOCK" in flags
    batch = "BATCH_ROUNDING_INCREASED_ORDER" in flags
    yield_review = "LOW_YIELD_REQUIRES_EXTRA_ORDERING" in flags
    perishability = "PERISHABLE_ORDER_CAPPED" in flags or "ORDER_QUANTITY_CAPPED_BY_EXPIRY_OR_MOVEMENT" in flags
    phase4 = _bool(row.get("phase4_review_before_final_policy")) or "PHASE4_REVIEW_BEFORE_FINAL_POLICY" in flags
    supplier = "SUPPLIER_REVIEW_BEFORE_ORDER" in flags or _bool(row.get("supplier_review_signal")) or _bool(row.get("recommended_supplier_requires_review"))
    specific = [receiving, moq, batch, yield_review, perishability, phase4, supplier]
    quantity_only = _bool(row.get("quantity_constraint_flag")) and not any(specific)
    review_flag = any(specific)
    if receiving:
        review_type = "RECEIVING_CAPACITY_ORDER_REVIEW"
        severity = "URGENT"
    elif phase4:
        review_type = "PHASE4_ORDER_REVIEW"
        severity = "HIGH"
    elif supplier:
        review_type = "SUPPLIER_REVIEW_BEFORE_ORDER"
        severity = "HIGH"
    elif moq:
        review_type = "MOQ_OVERSTOCK_REVIEW"
        severity = "MEDIUM"
    elif perishability:
        review_type = "PERISHABILITY_CAP_REVIEW"
        severity = "MEDIUM"
    elif yield_review:
        review_type = "YIELD_REVIEW"
        severity = "MEDIUM"
    elif batch:
        review_type = "BATCH_ROUNDING_REVIEW"
        severity = "LOW"
    else:
        review_type = "NO_ORDER_REVIEW"
        severity = "NO_ACTION"
    info_type = "NO_ORDER_REVIEW_INFO"
    info_reason = "No non-actionable order review information."
    if quantity_only:
        info_type = "QUANTITY_CONSTRAINT_REVIEW_ONLY"
        info_reason = "Quantity constraint exists but does not require active order quantity review in this cycle."
    elif batch and not review_flag:
        info_type = "BATCH_ROUNDING_INFO_ONLY"
        info_reason = "Batch rounding exists as context only."
    elif yield_review and not review_flag:
        info_type = "YIELD_INFO_ONLY"
        info_reason = "Yield adjustment exists as context only."
    elif perishability and not review_flag:
        info_type = "PERISHABILITY_CAP_INFO_ONLY"
        info_reason = "Perishability cap exists as context only."
    elif phase4 and not review_flag:
        info_type = "PHASE4_INFO_ONLY"
        info_reason = "Phase 4 context exists as information only."
    elif supplier and not review_flag:
        info_type = "SUPPLIER_INFO_ONLY"
        info_reason = "Supplier context exists as information only."
    return {
        "receiving_capacity_order_review_flag": receiving,
        "moq_overstock_review_flag": moq,
        "batch_rounding_review_flag": batch,
        "yield_review_flag": yield_review,
        "perishability_cap_review_flag": perishability,
        "phase4_order_review_flag": phase4,
        "supplier_order_review_flag": supplier,
        "quantity_constraint_review_only_flag": quantity_only,
        "recommended_order_quantity_review_flag": review_flag,
        "order_review_type": review_type,
        "order_review_severity": severity,
        "order_review_info_type": info_type,
        "order_review_info_reason": info_reason,
    }


def _policy_review(row, direction, flags, model) -> tuple[str, str]:
    phase4 = _bool(row.get("phase4_review_flag")) or _bool(row.get("phase4_review_before_final_policy"))
    if phase4:
        return "REVIEW_PHASE4_PRODUCTION_POLICY", "Phase 4 production, BOM, or MRP logic may override this policy."
    if direction == "KEEP_STABLE":
        return "KEEP_POLICY", "Current policy appears acceptable for the next review cycle."
    if model == "CONTINUOUS_REVIEW_sQ":
        return "REVIEW_CONTINUOUS_REVIEW", "Continuous review parameters should be reviewed against current pressure signals."
    if model == "PERIODIC_REVIEW_RS":
        return "REVIEW_PERIODIC_REVIEW", "Periodic review cycle or order-up-to assumptions should be reviewed."
    if model == "EOQ":
        return "REVIEW_EOQ_POLICY", "EOQ assumptions should be reviewed against current cost and constraint signals."
    if model == "BASE_STOCK":
        return "REVIEW_BASE_STOCK_POLICY", "Base-stock target should be reviewed against current buffer signals."
    if model == "NEWSVENDOR_CANDIDATE":
        return "REVIEW_NEWSVENDOR_POLICY", "Seasonal/perishable tradeoffs should be reviewed before next cycle."
    if model == "EVENT_BASED_REPLENISHMENT":
        return "REVIEW_EVENT_BASED_POLICY", "Event triggers should be reviewed before changing stock buffers."
    if model == "ONE_TO_ONE_REPLACEMENT":
        return "REVIEW_ONE_TO_ONE_POLICY", "Replacement trigger assumptions should be reviewed."
    return "REVIEW_INVENTORY_POLICY", "Inventory policy needs review due to re-evaluation signals."


def _supplier_review(row, supplier_signal, flags) -> tuple[str, str]:
    if not supplier_signal:
        return "NO_SUPPLIER_REVIEW", "No supplier review signal is active."
    if _bool(row.get("watchlist_supplier_signal")) or "WATCHLIST_SUPPLIER" in flags:
        return "REVIEW_WATCHLIST_SUPPLIER", "Watchlist supplier signal requires procurement review."
    if _num(row.get("lead_time_std_days")) > 3:
        return "REVIEW_SUPPLIER_LEAD_TIME", "Lead-time variability may require supplier or buffer review."
    if _bool(row.get("recommended_supplier_requires_review")):
        return "REVIEW_SUPPLIER_BEFORE_ORDER", "Recommended supplier requires review before order action."
    return "REVIEW_SUPPLIER_RELIABILITY", "Supplier risk signals require reliability review."


def _warehouse_review(row, receiving, slotting, travel, z_warning, expiry) -> tuple[str, str]:
    if receiving:
        return "REVIEW_RECEIVING_CAPACITY", "Projected replenishment creates receiving or staging capacity pressure."
    if travel:
        return "REVIEW_TRAVEL_DISTANCE", "Travel-distance warning suggests slot review."
    if z_warning:
        return "REVIEW_Z_LEVEL_ERGONOMICS", "Z-level warning suggests ergonomic or vertical slotting review."
    if expiry:
        return "REVIEW_QUARANTINE_OR_FEFO", "Active expiry/FEFO signals require warehouse handling review."
    if slotting:
        return "REVIEW_SLOT_LOCATION", "Slotting warning suggests location review."
    return "NO_WAREHOUSE_REVIEW", "No warehouse review signal is active."


def _confidence(row, direction, pressure, shortage, excess, spoilage, supplier_signal, receiving, forecast_signal, flags) -> tuple[float, str]:
    score = 0.70
    if direction in {"INCREASE_BUFFER", "DECREASE_BUFFER"} and max(shortage, excess + spoilage) >= 0.30:
        score += 0.12
    if direction == "KEEP_STABLE" and pressure < 0.20:
        score += 0.08
    if direction == "MIXED_SIGNALS":
        score -= 0.20
    if supplier_signal or receiving or forecast_signal:
        score -= 0.08
    if _bool(row.get("phase4_review_flag")) or "BATCH_QUANTITY_RECONCILIATION_REVIEW" in flags:
        score -= 0.10
    score = _clamp(score, 0, 1)
    if score >= 0.80:
        return score, "HIGH"
    if score >= 0.60:
        return score, "MEDIUM"
    return score, "LOW"


def _human_review(row, direction, confidence, pressure, receiving, supplier_signal, forecast_signal, flags) -> tuple[bool, str, str]:
    phase4 = _bool(row.get("phase4_review_flag")) or _bool(row.get("phase4_review_before_final_policy"))
    critical_conflict = direction == "MIXED_SIGNALS" or (_text(row.get("inventory_priority_class")).upper() == "CRITICAL_PRIORITY" and receiving)
    if critical_conflict or phase4 or receiving or "BATCH_QUANTITY_RECONCILIATION_REVIEW" in flags:
        return True, "MANDATORY_REVIEW", "Mandatory review because mixed, Phase 4, receiving-capacity, or data-reconciliation risk is active."
    if supplier_signal and _num(row.get("recommended_order_quantity")) > 0:
        return True, "MANDATORY_REVIEW", "Supplier review is mandatory before changing parameters or ordering."
    if pressure >= 0.55 or _text(row.get("cost_risk_level")).upper() in {"HIGH", "CRITICAL"}:
        return True, "HIGH_REVIEW", "High pressure or cost risk requires human review."
    if confidence < RE_EVALUATION_CONFIG["human_review_confidence_threshold"] or forecast_signal:
        return True, "MEDIUM_REVIEW", "Moderate uncertainty or lower confidence requires review."
    if direction == "KEEP_STABLE":
        return False, "NO_REVIEW", "No human review required for stable recommendation."
    return False, "LOW_REVIEW", "Low-risk parameter recommendation can be queued for next planning cycle review."


def _build_adjustment_output(re_eval_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in re_eval_df.iterrows():
        direction = row["recommended_adjustment_direction"]
        rows.append(
            {
                "sku_id": row["sku_id"],
                "product_name": row["product_name"],
                "category": row["category"],
                "recommended_adjustment_direction": direction,
                "recommendation_strength": row["recommendation_strength"],
                "recommendation_basis": row["recommendation_basis"],
                "auto_apply_allowed": row["auto_apply_allowed"],
                "buffer_adjustment_scope": row["buffer_adjustment_scope"],
                "guarded_reduction_explanation": row["guarded_reduction_explanation"],
                "current_service_level_target": row["current_service_level_target"],
                "raw_recommended_service_level_target": row["raw_recommended_service_level_target"],
                "recommended_service_level_target": row["recommended_service_level_target"],
                "service_level_adjustment": row["service_level_adjustment"],
                "service_level_guardrail_action": row["service_level_guardrail_action"],
                "current_safety_stock": row["current_safety_stock"],
                "recommended_safety_stock": row["recommended_safety_stock"],
                "safety_stock_adjustment_units": row["safety_stock_adjustment_units"],
                "current_reorder_point": row["current_reorder_point"],
                "estimated_lead_time_demand": row["estimated_lead_time_demand"],
                "minimum_recommended_reorder_point": row["minimum_recommended_reorder_point"],
                "recommended_reorder_point": row["recommended_reorder_point"],
                "reorder_point_adjustment_units": row["reorder_point_adjustment_units"],
                "rop_lead_time_guardrail_applied": row["rop_lead_time_guardrail_applied"],
                "current_order_cap_days": row["current_order_cap_days"],
                "recommended_order_cap_days": row["recommended_order_cap_days"],
                "order_cap_adjustment_days": row["order_cap_adjustment_days"],
                "recommended_order_quantity_review_flag": row["recommended_order_quantity_review_flag"],
                "order_review_type": row["order_review_type"],
                "order_review_severity": row["order_review_severity"],
                "order_review_info_type": row["order_review_info_type"],
                "order_review_info_reason": row["order_review_info_reason"],
                "eoq_review_recommendation": row["eoq_review_recommendation"],
                "eoq_review_reason": row["eoq_review_reason"],
                "order_model_review_recommendation": row["order_model_review_recommendation"],
                "order_model_review_reason": row["order_model_review_reason"],
                "policy_review_recommendation": row["policy_review_recommendation"],
                "supplier_review_recommendation": row["supplier_review_recommendation"],
                "warehouse_review_recommendation": row["warehouse_review_recommendation"],
                "expected_cost_tradeoff_direction": _cost_tradeoff(direction, row),
                "expected_risk_tradeoff": _risk_tradeoff(direction, row),
                "requires_human_review": row["requires_human_review"],
                "human_review_level": row["human_review_level"],
                "recommendation_priority": _recommendation_priority(row),
                "recommendation_summary": _recommendation_summary(row),
            }
        )
    return pd.DataFrame(rows)


def _build_summary(re_eval_df: pd.DataFrame) -> pd.DataFrame:
    groups = [
        ("ALL_SKUS", None),
        ("BY_RECOMMENDED_DIRECTION", "recommended_adjustment_direction"),
        ("BY_HUMAN_REVIEW_LEVEL", "human_review_level"),
        ("BY_INVENTORY_STATUS", "main_inventory_status"),
        ("BY_COST_RISK_LEVEL", "cost_risk_level"),
        ("BY_INVENTORY_MODEL_TYPE", "inventory_model_type"),
        ("BY_CATEGORY", "category"),
        ("BY_WAREHOUSE_REVIEW_RECOMMENDATION", "warehouse_review_recommendation"),
        ("BY_SUPPLIER_REVIEW_RECOMMENDATION", "supplier_review_recommendation"),
        ("BY_POLICY_REVIEW_RECOMMENDATION", "policy_review_recommendation"),
        ("BY_RECOMMENDATION_STRENGTH", "recommendation_strength"),
        ("BY_ORDER_REVIEW_TYPE", "order_review_type"),
        ("BY_ORDER_REVIEW_SEVERITY", "order_review_severity"),
        ("BY_EOQ_REVIEW_RECOMMENDATION", "eoq_review_recommendation"),
        ("BY_SERVICE_LEVEL_GUARDRAIL_ACTION", "service_level_guardrail_action"),
        ("BY_ROP_GUARDRAIL_ACTION", "rop_guardrail_action"),
        ("BY_AUTO_APPLY_ALLOWED", "auto_apply_allowed"),
        ("BY_BUFFER_ADJUSTMENT_SCOPE", "buffer_adjustment_scope"),
        ("BY_ORDER_REVIEW_INFO_TYPE", "order_review_info_type"),
        ("BY_ORDER_MODEL_REVIEW_RECOMMENDATION", "order_model_review_recommendation"),
    ]
    rows = []
    for summary_type, column in groups:
        if column is None:
            rows.append(_summary_row(summary_type, "ALL", re_eval_df))
        elif column in re_eval_df.columns:
            for value, group in re_eval_df.groupby(re_eval_df[column].fillna("UNKNOWN").astype(str), dropna=False):
                rows.append(_summary_row(summary_type, value or "UNKNOWN", group))
    return pd.DataFrame(rows)


def _summary_row(summary_type: str, group_name: str, df: pd.DataFrame) -> dict:
    return {
        "summary_type": summary_type,
        "group_name": group_name,
        "sku_count": len(df),
        "average_pressure_score": round(float(df["total_re_evaluation_pressure_score"].mean()) if not df.empty else 0, 3),
        "average_confidence_score": round(float(df["re_evaluation_confidence_score"].mean()) if not df.empty else 0, 3),
        "human_review_count": _count_true(df, "requires_human_review"),
        "mandatory_review_count": _count_value(df, "human_review_level", "MANDATORY_REVIEW"),
        "increase_buffer_count": _count_value(df, "recommended_adjustment_direction", "INCREASE_BUFFER"),
        "decrease_buffer_count": _count_value(df, "recommended_adjustment_direction", "DECREASE_BUFFER"),
        "keep_stable_count": _count_value(df, "recommended_adjustment_direction", "KEEP_STABLE"),
        "mixed_signals_count": _count_value(df, "recommended_adjustment_direction", "MIXED_SIGNALS"),
        "review_only_count": _count_value(df, "recommended_adjustment_direction", "REVIEW_ONLY"),
    }


def _reason(direction, shortage, excess, spoilage, warehouse, supplier, cost) -> str:
    return (
        f"{direction} recommended from shortage={shortage:.2f}, excess={excess:.2f}, "
        f"spoilage={spoilage:.2f}, warehouse={warehouse:.2f}, supplier={supplier:.2f}, cost={cost:.2f}."
    )


def _order_quantity_review_reason(row, order_review, flags) -> str:
    reasons = []
    if order_review["receiving_capacity_order_review_flag"]:
        reasons.append("recommended order creates receiving/staging pressure")
    if order_review["phase4_order_review_flag"]:
        reasons.append("Phase 4 production logic may override order assumptions")
    if order_review["supplier_order_review_flag"]:
        reasons.append("supplier review is required before order action")
    if order_review["moq_overstock_review_flag"]:
        reasons.append("MOQ may create overstock")
    if order_review["perishability_cap_review_flag"]:
        reasons.append("perishability or movement cap affected quantity")
    if order_review["yield_review_flag"]:
        reasons.append("yield adjustment affects gross order need")
    if order_review["batch_rounding_review_flag"]:
        reasons.append("batch rounding changed order quantity")
    if order_review["quantity_constraint_review_only_flag"]:
        reasons.append("generic quantity constraint is active without a specific order issue")
    return "; ".join(reasons) if reasons else "No order quantity review signal is active."


def _cost_tradeoff(direction, row) -> str:
    if row.get("buffer_adjustment_scope") == "PARTIAL_BUFFER_DECREASE_SERVICE_LEVEL_PROTECTED":
        return "Lower safety stock, ROP, or order cap may reduce excess cost, while service-level reduction remains blocked by guardrails."
    if _bool(row.get("receiving_capacity_order_review_flag")):
        return "Split delivery or receiving-capacity review may reduce projected staging overcapacity risk."
    if direction == "INCREASE_BUFFER":
        return "Higher buffer may increase holding cost but reduce stockout exposure."
    if direction == "DECREASE_BUFFER":
        return "Lower buffer may reduce holding, overstock, or expiry cost but can increase stockout risk."
    if direction == "MIXED_SIGNALS":
        return "Conflicting signals require review; changing buffer blindly could move cost from one risk area to another."
    if direction == "REVIEW_ONLY":
        return "No parameter change should be applied until review is complete."
    if direction == "KEEP_STABLE":
        return "No parameter change recommended; current settings remain stable for the next cycle."
    return "No parameter change recommended."


def _risk_tradeoff(direction, row) -> str:
    if row.get("buffer_adjustment_scope") == "PARTIAL_BUFFER_DECREASE_SERVICE_LEVEL_PROTECTED":
        return "Excess risk may be reduced through stock/ROP/cap review while service protection is preserved."
    if direction == "INCREASE_BUFFER":
        return "Reduces shortage risk while increasing carrying and capacity exposure."
    if direction == "DECREASE_BUFFER":
        return "Reduces excess and spoilage risk while increasing shortage exposure."
    if direction == "MIXED_SIGNALS":
        return "Shortage and excess/capacity risks conflict."
    if direction == "REVIEW_ONLY":
        return "Risk should be reviewed before changing parameters."
    return "Current risk balance appears stable."


def _recommendation_priority(row) -> str:
    status = _text(row["main_inventory_status"]).upper()
    vital_or_critical = _text(row.get("vitality_class")).upper() == "VITAL" or _text(row.get("inventory_priority_class")).upper() == "CRITICAL_PRIORITY"
    active_expired_high_cost = _bool(row.get("expired_stock_re_eval_signal")) and _text(row.get("cost_risk_level")).upper() in {"HIGH", "CRITICAL"}
    if (status in {"STOCKOUT", "CRITICAL_LOW_STOCK"} and vital_or_critical) or (_bool(row.get("receiving_capacity_order_review_flag")) and row["human_review_level"] == "MANDATORY_REVIEW") or active_expired_high_cost:
        return "URGENT"
    if row["recommendation_strength"] == "STRONGLY_SUGGESTED_CHANGE" or row["human_review_level"] == "HIGH_REVIEW" or row["cost_risk_level"] in {"HIGH", "CRITICAL"} or row["order_review_type"] in {"PHASE4_ORDER_REVIEW", "SUPPLIER_REVIEW_BEFORE_ORDER"}:
        return "HIGH"
    if row["recommended_adjustment_direction"] in {"INCREASE_BUFFER", "DECREASE_BUFFER", "MIXED_SIGNALS", "REVIEW_ONLY"}:
        return "MEDIUM"
    if row["recommended_adjustment_direction"] == "KEEP_STABLE":
        return "LOW" if row["human_review_level"] in {"LOW_REVIEW", "MEDIUM_REVIEW"} else "NO_ACTION"
    return "LOW"


def _recommendation_summary(row) -> str:
    if row.get("buffer_adjustment_scope") == "PARTIAL_BUFFER_DECREASE_SERVICE_LEVEL_PROTECTED":
        return (
            f"{row['sku_id']}: Decrease safety stock / ROP / order cap only; "
            "service-level reduction blocked by guardrail."
        )
    return (
        f"{row['recommended_adjustment_direction']} for {row['sku_id']}; "
        f"service {row['current_service_level_target']} -> {row['recommended_service_level_target']}, "
        f"safety stock {row['current_safety_stock']} -> {row['recommended_safety_stock']}, "
        f"ROP {row['current_reorder_point']} -> {row['recommended_reorder_point']}."
    )


def _recommendation_strength(direction, confidence, review_level, pressure, order_review) -> str:
    if review_level == "MANDATORY_REVIEW" and direction not in {"INCREASE_BUFFER", "DECREASE_BUFFER"}:
        return "REVIEW_ONLY"
    if direction == "MIXED_SIGNALS":
        return "REVIEW_ONLY"
    if direction == "REVIEW_ONLY":
        return "REVIEW_ONLY"
    if direction == "KEEP_STABLE" and not order_review["recommended_order_quantity_review_flag"]:
        return "DO_NOT_CHANGE"
    if direction in {"INCREASE_BUFFER", "DECREASE_BUFFER"} and confidence >= 0.80 and pressure >= 0.45 and review_level not in {"MANDATORY_REVIEW", "HIGH_REVIEW"}:
        return "STRONGLY_SUGGESTED_CHANGE"
    if direction in {"INCREASE_BUFFER", "DECREASE_BUFFER"}:
        return "SUGGESTED_CHANGE"
    if order_review["recommended_order_quantity_review_flag"]:
        return "REVIEW_ONLY"
    return "DO_NOT_CHANGE"


def _buffer_adjustment_scope(direction: str, service_guardrail_action: str) -> tuple[str, str]:
    if direction == "DECREASE_BUFFER" and service_guardrail_action == "GUARDRAIL_PROTECTED_NO_REDUCTION":
        return (
            "PARTIAL_BUFFER_DECREASE_SERVICE_LEVEL_PROTECTED",
            "Re-evaluation suggests reducing safety stock, reorder point, or order cap due to excess/expiry pressure, but service-level reduction is blocked by guardrails. Do not interpret the service-level increase/protection as a full buffer increase.",
        )
    if direction == "DECREASE_BUFFER":
        return "FULL_BUFFER_DECREASE", "Full buffer decrease can be reviewed across service level, safety stock, ROP, and order cap."
    if direction == "INCREASE_BUFFER":
        return "FULL_BUFFER_INCREASE", "Full buffer increase can be reviewed across service level, safety stock, ROP, and order cap."
    if direction in {"REVIEW_ONLY", "MIXED_SIGNALS"}:
        return "PARAMETER_REVIEW_ONLY", "Signals require review before changing buffer parameters."
    return "NO_BUFFER_CHANGE", "No buffer change is recommended."


def _recommendation_basis(direction, shortage, excess, spoilage, supplier, warehouse, forecast, review_level) -> str:
    bases = []
    if shortage >= 0.20:
        bases.append("stockout/shortage")
    if excess >= 0.20:
        bases.append("overstock/excess")
    if spoilage >= 0.15:
        bases.append("expiry/spoilage")
    if supplier >= 0.10:
        bases.append("supplier risk")
    if warehouse >= 0.12:
        bases.append("warehouse capacity")
    if forecast >= 0.10:
        bases.append("forecast uncertainty")
    if review_level == "MANDATORY_REVIEW":
        bases.append("mandatory human review")
    if direction == "MIXED_SIGNALS":
        bases.append("mixed signals")
    basis = ", ".join(bases) if bases else "stable signals"
    return f"Signal-based recommendation only; not optimized and not auto-applied. Main basis: {basis}."


def _eoq_review(row, order_review, high_cost_signal, forecast_signal) -> tuple[str, str]:
    model = _text(row.get("inventory_model_type")).upper()
    if model != "EOQ":
        return "NO_EOQ_REVIEW", "SKU is not using EOQ policy; EOQ-specific review is not applicable."
    flags_active = order_review["recommended_order_quantity_review_flag"]
    high_order = _num(row.get("recommended_total_order_cost")) >= RE_EVALUATION_THRESHOLDS["high_order_cost"]
    high_holding = _num(row.get("current_holding_cost")) + _num(row.get("current_overstock_cost")) >= RE_EVALUATION_THRESHOLDS["high_holding_or_overstock_cost"]
    if model == "EOQ" and (high_cost_signal or high_order or flags_active):
        return "REVIEW_EOQ_INPUTS", "EOQ policy should be reviewed against current cost, demand, and constraint signals."
    if high_order:
        return "REVIEW_ORDER_COST", "Recommended order cost is high; review fixed/order-cost assumptions before changing EOQ-like settings."
    if high_holding:
        return "REVIEW_HOLDING_COST", "Holding or overstock cost is high; review holding-cost assumptions before EOQ changes."
    if forecast_signal:
        return "REVIEW_DEMAND_INPUT", "Forecast confidence or demand variability suggests reviewing demand inputs before EOQ changes."
    if flags_active:
        return "REVIEW_EOQ_CONSTRAINTS", "MOQ, batch, yield, perishability, supplier, or receiving constraints affect EOQ-like decisions."
    return "NO_EOQ_REVIEW", "No EOQ-specific review signal is active; current EOQ is not recalculated or overwritten."


def _order_model_review(row, order_review, direction, high_cost_signal, shortage_signal, overstock_signal, expiry_signal) -> tuple[str, str]:
    model = _text(row.get("inventory_model_type")).upper()
    phase4 = _bool(row.get("phase4_review_flag")) or _bool(row.get("phase4_review_before_final_policy"))
    if phase4:
        return "REVIEW_PHASE4_PRODUCTION_ORDER_MODEL", "Phase 4 production/BOM/MRP logic may override the order model."
    if model == "EOQ":
        return "REVIEW_EOQ_POLICY_INPUTS", "EOQ policy inputs should be reviewed through the EOQ-specific recommendation."
    if model == "BASE_STOCK" and (shortage_signal or overstock_signal or high_cost_signal):
        return "REVIEW_BASE_STOCK_TARGET", "Base-stock target should be reviewed against shortage, excess, or cost pressure."
    if model == "CONTINUOUS_REVIEW_SQ" and direction in {"INCREASE_BUFFER", "DECREASE_BUFFER", "MIXED_SIGNALS", "REVIEW_ONLY"}:
        return "REVIEW_CONTINUOUS_REVIEW_PARAMETERS", "Continuous-review safety stock, ROP, or order cap should be reviewed."
    if model == "NEWSVENDOR_CANDIDATE" and (expiry_signal or overstock_signal or high_cost_signal):
        return "REVIEW_NEWSVENDOR_ASSUMPTIONS", "Seasonality, perishability, excess, or shortage assumptions should be reviewed."
    if model == "EVENT_BASED_REPLENISHMENT" and (order_review["recommended_order_quantity_review_flag"] or direction != "KEEP_STABLE"):
        return "REVIEW_EVENT_BASED_TRIGGERS", "Event-based replenishment triggers should be reviewed."
    if model == "ONE_TO_ONE_REPLACEMENT" and (order_review["recommended_order_quantity_review_flag"] or direction != "KEEP_STABLE"):
        return "REVIEW_ONE_TO_ONE_TRIGGER_LOGIC", "One-to-one replacement trigger logic should be reviewed."
    if order_review["recommended_order_quantity_review_flag"]:
        return "REVIEW_ORDER_CONSTRAINTS", "Order constraints should be reviewed before the next cycle."
    return "NO_ORDER_MODEL_REVIEW", "No order-model review signal is active."


def _high_days_signal(row, perishability, movement) -> bool:
    days = _num(row.get("days_of_supply_current"))
    threshold = RE_EVALUATION_THRESHOLDS["high_days_of_supply"]
    if perishability in {"SPOILAGE_RISK", "EXPIRY_TRACKED"}:
        threshold = RE_EVALUATION_THRESHOLDS["perishable_high_days_of_supply"]
    if movement == "NON_MOVING":
        threshold = RE_EVALUATION_THRESHOLDS["non_moving_high_days_of_supply"]
    return days > threshold


def _supplier_signal(row, flags: str) -> bool:
    return (
        _bool(row.get("recommended_supplier_requires_review"))
        or _bool(row.get("supplier_review_signal"))
        or _bool(row.get("watchlist_supplier_signal"))
        or "SUPPLIER_REVIEW_REQUIRED" in flags
        or _num(row.get("demand_adjusted_procurement_risk_score")) >= RE_EVALUATION_THRESHOLDS["high_procurement_risk_score"]
    )


def _warehouse_capacity_signal(row, flags: str) -> bool:
    return (
        _bool(row.get("sku_causes_projected_staging_pressure"))
        or _bool(row.get("replenishment_location_projected_over_capacity_flag"))
        or _bool(row.get("replenishment_location_projected_capacity_pressure_flag"))
        or "PROJECTED_LOCATION_OVER_CAPACITY" in flags
        or "REPLENISHMENT_STAGING_OVER_CAPACITY" in flags
    )


def _travel_signal(row, flags: str) -> bool:
    travel_group = _text(row.get("visual_travel_risk_group")).upper()
    return travel_group not in {"", "NORMAL_TRAVEL"} or "FAST_MOVING_ITEM_TOO_FAR" in flags or "HIGH_TRAVEL_DISTANCE" in flags


def _forecast_uncertainty_signal(row) -> bool:
    confidence = _num(row.get("average_forecast_confidence_score") or row.get("forecast_confidence") or row.get("champion_confidence_score"), 1.0)
    cv = _num(row.get("coefficient_of_variation"))
    behavior = _text(row.get("demand_behavior_class") or row.get("demand_pattern")).lower()
    return confidence < RE_EVALUATION_THRESHOLDS["low_forecast_confidence"] or cv >= 1.0 or behavior in {"erratic", "intermittent"}


def _current_order_cap_days(row) -> float:
    avg = _num(row.get("average_daily_demand"))
    max_stock = _num(row.get("max_stock_level"))
    if avg <= 0:
        return RE_EVALUATION_CONFIG["default_review_period_days"]
    return max_stock / avg


def _joined_flags(*values) -> str:
    flags = []
    for value in values:
        for item in _text(value).replace(",", ";").split(";"):
            item = item.strip()
            if item and item not in flags:
                flags.append(item)
    return "; ".join(flags)


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"true", "1", "yes", "y"}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _pct_change(current: float, recommended: float) -> float:
    if current == 0:
        return 0 if recommended == 0 else 1
    return (recommended - current) / current


def _count_true(df: pd.DataFrame, column: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    return int(df[column].apply(_bool).sum())


def _count_value(df: pd.DataFrame, column: str, value: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    return int((df[column].astype(str) == value).sum())


_RE_EVALUATION_COLUMNS = [
    "sku_id", "product_name", "category", "abc_class", "xyz_class", "fsn_class", "movement_class",
    "vitality_class", "perishability_class", "seasonality_class", "inventory_priority_class",
    "main_inventory_status", "primary_action", "action_priority", "main_cost_driver", "cost_risk_level",
    "current_service_level_target", "current_safety_stock", "current_reorder_point", "current_eoq",
    "current_recommended_order_quantity", "inventory_model_type", "review_policy",
    "stockout_re_eval_signal", "zero_stock_re_eval_signal", "critical_low_stock_re_eval_signal",
    "reorder_now_re_eval_signal", "overstock_re_eval_signal", "high_days_of_supply_signal",
    "expiry_re_eval_signal", "non_moving_re_eval_signal", "supplier_risk_re_eval_signal",
    "warehouse_capacity_re_eval_signal", "receiving_capacity_re_eval_signal", "slotting_re_eval_signal",
    "travel_re_eval_signal", "z_level_re_eval_signal", "forecast_uncertainty_re_eval_signal",
    "high_cost_re_eval_signal", "shortage_pressure_score", "excess_pressure_score",
    "spoilage_pressure_score", "supplier_pressure_score", "warehouse_pressure_score",
    "forecast_pressure_score", "cost_pressure_score", "total_re_evaluation_pressure_score",
    "recommended_adjustment_direction", "recommendation_strength", "recommendation_basis", "auto_apply_allowed",
    "buffer_adjustment_scope", "guarded_reduction_explanation",
    "raw_recommended_service_level_target", "recommended_service_level_target", "service_level_adjustment",
    "service_level_guardrail_action", "service_level_guardrail_reason",
    "recommended_safety_stock", "safety_stock_adjustment_units", "safety_stock_adjustment_pct",
    "average_daily_demand_used_for_rop", "expected_lead_time_days_used_for_rop",
    "estimated_lead_time_demand", "minimum_recommended_reorder_point",
    "recommended_reorder_point", "reorder_point_adjustment_units", "reorder_point_adjustment_pct",
    "rop_lead_time_guardrail_applied", "rop_guardrail_action", "rop_guardrail_reason",
    "recommended_order_cap_days", "order_cap_adjustment_days", "recommended_order_quantity_review_flag",
    "receiving_capacity_order_review_flag", "moq_overstock_review_flag", "batch_rounding_review_flag",
    "yield_review_flag", "perishability_cap_review_flag", "phase4_order_review_flag",
    "supplier_order_review_flag", "quantity_constraint_review_only_flag", "order_review_type",
    "order_review_severity", "order_review_info_type", "order_review_info_reason",
    "eoq_review_recommendation", "eoq_review_reason",
    "order_model_review_recommendation", "order_model_review_reason",
    "policy_review_recommendation", "supplier_review_recommendation", "warehouse_review_recommendation",
    "re_evaluation_confidence_score", "re_evaluation_confidence_level", "requires_human_review",
    "human_review_level", "re_evaluation_reason", "service_level_adjustment_reason",
    "safety_stock_adjustment_reason", "reorder_point_adjustment_reason", "order_cap_adjustment_reason",
    "policy_review_reason", "supplier_review_reason", "warehouse_review_reason", "human_review_reason",
]

_ADJUSTMENT_COLUMNS = [
    "sku_id", "product_name", "category", "recommended_adjustment_direction",
    "recommendation_strength", "recommendation_basis", "auto_apply_allowed",
    "buffer_adjustment_scope", "guarded_reduction_explanation",
    "current_service_level_target", "raw_recommended_service_level_target",
    "recommended_service_level_target", "service_level_adjustment", "service_level_guardrail_action",
    "current_safety_stock", "recommended_safety_stock", "safety_stock_adjustment_units",
    "current_reorder_point", "estimated_lead_time_demand", "minimum_recommended_reorder_point",
    "recommended_reorder_point", "reorder_point_adjustment_units", "rop_lead_time_guardrail_applied",
    "current_order_cap_days", "recommended_order_cap_days", "order_cap_adjustment_days",
    "recommended_order_quantity_review_flag", "order_review_type", "order_review_severity",
    "order_review_info_type", "order_review_info_reason",
    "eoq_review_recommendation", "eoq_review_reason",
    "order_model_review_recommendation", "order_model_review_reason", "policy_review_recommendation",
    "supplier_review_recommendation", "warehouse_review_recommendation", "expected_cost_tradeoff_direction",
    "expected_risk_tradeoff", "requires_human_review", "human_review_level", "recommendation_priority",
    "recommendation_summary",
]
