"""Signal-gated scenario optimizer for Phase 3 inventory recommendations."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from config import (
    SCENARIO_CONTRADICTION_RULES,
    SCENARIO_COST_DEFAULTS,
    SCENARIO_COST_REPORTING,
    SCENARIO_COST_WEIGHTS,
    SCENARIO_FEASIBILITY_RULES,
    SCENARIO_IMPACT_FACTORS,
    SCENARIO_OPTIMIZATION_CONFIG,
    SCENARIO_PENALTY_CAPS,
    SCENARIO_RECEIVING_CAPACITY_PENALTY,
    SCENARIO_SELECTION_CONFIG,
    SCENARIO_SEVERITY_PENALTIES,
)


def build_inventory_scenario_optimization(
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
    inventory_re_evaluation: pd.DataFrame,
    inventory_parameter_adjustment_recommendations: pd.DataFrame,
    re_evaluation_summary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build scenario rows, scored results, selected recommendations, and summary."""
    context = _merge_context(
        inventory_re_evaluation,
        [
            inventory_policy_parameters,
            inventory_costs,
            inventory_status,
            planning_context,
            inventory_classification,
            inventory_policy,
            warehouse_slotting,
            warehouse_travel_costs,
            warehouse_visual_skus,
            inventory_parameter_adjustment_recommendations,
        ],
    )
    scenarios = []
    results = []
    recommendations = []
    for _, row in context.iterrows():
        row_dict = row.to_dict()
        sku_scenarios = _generate_scenarios_for_sku(row_dict, _generate_relevant_levers(row_dict))
        scenarios.extend(sku_scenarios)
        sku_results = [_score_scenario(row_dict, scenario) for scenario in sku_scenarios if not scenario["scenario_contradiction_flag"]]
        results.extend(sku_results)
        recommendations.append(_select_best_scenario(row_dict, sku_results))
    scenarios_df = pd.DataFrame(scenarios)
    results_df = pd.DataFrame(results)
    recommendations_df = pd.DataFrame(recommendations)
    summary_df = _build_summary(recommendations_df, results_df)
    return (
        scenarios_df[_SCENARIO_COLUMNS],
        results_df[_RESULT_COLUMNS],
        recommendations_df[_RECOMMENDATION_COLUMNS],
        summary_df,
    )


def _merge_context(base_df: pd.DataFrame, source_dfs: list[pd.DataFrame]) -> pd.DataFrame:
    if base_df.empty or "sku_id" not in base_df.columns:
        return pd.DataFrame()
    merged = base_df.copy()
    merged["sku_id"] = merged["sku_id"].astype(str).str.strip()
    for source in source_dfs:
        if source.empty or "sku_id" not in source.columns:
            continue
        source = source.copy()
        source["sku_id"] = source["sku_id"].astype(str).str.strip()
        keep = ["sku_id"] + [col for col in source.columns if col != "sku_id" and col not in merged.columns]
        if len(keep) > 1:
            merged = merged.merge(source[keep].drop_duplicates("sku_id"), on="sku_id", how="left")
    return merged


def _generate_relevant_levers(row: dict[str, Any]) -> dict[str, list[str]]:
    levers = {
        "buffer_strategy": ["CURRENT_BUFFER"],
        "supplier_strategy": ["CURRENT_SUPPLIER"],
        "delivery_strategy": ["NORMAL_DELIVERY"],
        "order_cap_strategy": ["CURRENT_ORDER_CAP"],
        "expiry_strategy": ["NO_EXPIRY_ACTION"],
        "warehouse_strategy": ["CURRENT_WAREHOUSE_PLAN"],
    }
    status = _text(row.get("main_inventory_status")).upper()
    vital = _text(row.get("vitality_class")).upper() == "VITAL"
    critical = _text(row.get("inventory_priority_class")).upper() == "CRITICAL_PRIORITY"
    shortage = _bool(row.get("stockout_re_eval_signal")) or _bool(row.get("zero_stock_re_eval_signal")) or _bool(row.get("critical_low_stock_re_eval_signal")) or status == "REORDER_NOW" or vital or critical
    supplier_risk = _bool(row.get("supplier_risk_re_eval_signal")) or _bool(row.get("recommended_supplier_requires_review")) or _num(row.get("demand_adjusted_procurement_risk_score")) >= 0.50
    receiving = _bool(row.get("receiving_capacity_re_eval_signal")) or _bool(row.get("sku_causes_projected_staging_pressure")) or _bool(row.get("replenishment_location_projected_over_capacity_flag"))
    excess = _bool(row.get("overstock_re_eval_signal")) or _bool(row.get("non_moving_re_eval_signal")) or _bool(row.get("dead_stock_re_eval_signal"))
    expiry = _bool(row.get("expiry_re_eval_signal")) or _num(row.get("near_expiry_units")) > 0 or _num(row.get("expired_units")) > 0
    travel = _text(row.get("visual_travel_risk_group")).upper() not in {"", "NORMAL_TRAVEL"} or _bool(row.get("travel_re_eval_signal"))
    z_warning = _bool(row.get("z_level_re_eval_signal"))
    phase4 = _text(row.get("order_model_review_recommendation")).upper() == "REVIEW_PHASE4_PRODUCTION_ORDER_MODEL"

    if shortage:
        _extend(levers["buffer_strategy"], ["INCREASE_BUFFER"])
        _extend(levers["supplier_strategy"], ["FAST_RELIABLE_SUPPLIER", "MOST_RELIABLE_SUPPLIER"])
        _extend(levers["delivery_strategy"], ["EXPEDITE_DELIVERY"])
        if not receiving:
            _extend(levers["order_cap_strategy"], ["LOOSEN_ORDER_CAP"])
    if supplier_risk:
        _extend(levers["supplier_strategy"], ["FAST_RELIABLE_SUPPLIER", "MOST_RELIABLE_SUPPLIER", "BALANCED_SUPPLIER", "SUPPLIER_REVIEW_ONLY"])
    if receiving:
        _extend(levers["delivery_strategy"], ["SPLIT_DELIVERY"])
        _extend(levers["order_cap_strategy"], ["TIGHTEN_ORDER_CAP"])
        _extend(levers["warehouse_strategy"], ["REVIEW_RECEIVING_CAPACITY"])
        if not shortage:
            _extend(levers["delivery_strategy"], ["DELAY_NONURGENT_ORDER"])
    if excess:
        _extend(levers["buffer_strategy"], ["DECREASE_BUFFER", "MINIMUM_SAFE_BUFFER"])
        _extend(levers["order_cap_strategy"], ["TIGHTEN_ORDER_CAP"])
        _extend(levers["delivery_strategy"], ["DELAY_NONURGENT_ORDER"])
        _extend(levers["expiry_strategy"], ["LIQUIDATE_DEAD_STOCK"])
    if expiry:
        _extend(levers["order_cap_strategy"], ["CAP_BY_EXPIRY_OR_MOVEMENT"])
        _extend(levers["expiry_strategy"], ["MARKDOWN_NEAR_EXPIRY", "RETURN_TO_SUPPLIER_IF_ALLOWED", "QUARANTINE_OR_SCRAP_EXPIRED"])
        _extend(levers["warehouse_strategy"], ["REVIEW_QUARANTINE_OR_FEFO"])
    if travel:
        _extend(levers["warehouse_strategy"], ["REVIEW_TRAVEL_DISTANCE", "REVIEW_SLOT_LOCATION"])
    if z_warning:
        _extend(levers["warehouse_strategy"], ["REVIEW_Z_LEVEL_ERGONOMICS"])
    if row.get("buffer_adjustment_scope") == "PARTIAL_BUFFER_DECREASE_SERVICE_LEVEL_PROTECTED":
        _extend(levers["buffer_strategy"], ["SERVICE_LEVEL_GUARDED_BUFFER"])
    if phase4:
        _extend(levers["warehouse_strategy"], ["REVIEW_SLOT_LOCATION"])
    return levers


def _generate_scenarios_for_sku(row: dict[str, Any], levers: dict[str, list[str]]) -> list[dict]:
    baseline = {
        "buffer_strategy": "CURRENT_BUFFER",
        "supplier_strategy": "CURRENT_SUPPLIER",
        "delivery_strategy": "NORMAL_DELIVERY",
        "order_cap_strategy": "CURRENT_ORDER_CAP",
        "expiry_strategy": "NO_EXPIRY_ACTION",
        "warehouse_strategy": "CURRENT_WAREHOUSE_PLAN",
    }
    lever_to_axis = {value: axis for axis, values in levers.items() for value in values}
    scenario_defs = [baseline.copy()]
    non_baseline = [value for axis, values in levers.items() for value in values if value != baseline[axis]]
    for value in non_baseline:
        scenario = baseline.copy()
        scenario[lever_to_axis[value]] = value
        scenario_defs.append(scenario)
    for combo in _smart_combinations(row, non_baseline):
        scenario = baseline.copy()
        for value in combo:
            scenario[lever_to_axis[value]] = value
        scenario_defs.append(scenario)
    unique = []
    seen = set()
    for scenario in scenario_defs:
        key = tuple(scenario[axis] for axis in baseline)
        if key not in seen:
            seen.add(key)
            unique.append(scenario)
        if len(unique) >= SCENARIO_OPTIMIZATION_CONFIG["max_scenarios_per_sku"]:
            break
    rows = []
    sku = _text(row.get("sku_id"))
    for idx, scenario in enumerate(unique, start=1):
        values = list(scenario.values())
        non_base_values = [value for value in values if value not in baseline.values()]
        contradiction, reason = _contradiction(non_base_values)
        scenario_name = "CURRENT_POLICY" if not non_base_values else "__".join(non_base_values)
        rows.append(
            {
                "sku_id": sku,
                "product_name": row.get("product_name"),
                "category": row.get("category"),
                "scenario_id": f"{sku}-SCN-{idx:03d}",
                "scenario_name": scenario_name,
                "scenario_rank_generated": idx,
                "lever_count": len(non_base_values),
                **scenario,
                "scenario_generation_reason": _generation_reason(row),
                "scenario_contradiction_flag": contradiction,
                "scenario_contradiction_reason": reason,
                "generated_from_re_evaluation_direction": row.get("recommended_adjustment_direction"),
                "generated_from_main_status": row.get("main_inventory_status"),
                "generated_from_cost_driver": row.get("main_cost_driver"),
                "generated_from_warehouse_signal": row.get("warehouse_review_recommendation"),
            }
        )
    return rows


def _smart_combinations(row: dict[str, Any], values: list[str]) -> list[tuple[str, ...]]:
    desired = []
    def add(*items):
        if all(item in values for item in items):
            desired.append(tuple(items))
    add("INCREASE_BUFFER", "FAST_RELIABLE_SUPPLIER")
    add("INCREASE_BUFFER", "MOST_RELIABLE_SUPPLIER")
    add("INCREASE_BUFFER", "SPLIT_DELIVERY")
    add("FAST_RELIABLE_SUPPLIER", "SPLIT_DELIVERY")
    add("INCREASE_BUFFER", "FAST_RELIABLE_SUPPLIER", "SPLIT_DELIVERY")
    add("BALANCED_SUPPLIER", "SPLIT_DELIVERY")
    add("DECREASE_BUFFER", "MARKDOWN_NEAR_EXPIRY")
    add("TIGHTEN_ORDER_CAP", "MARKDOWN_NEAR_EXPIRY")
    add("DECREASE_BUFFER", "CAP_BY_EXPIRY_OR_MOVEMENT")
    add("DECREASE_BUFFER", "LIQUIDATE_DEAD_STOCK")
    add("MINIMUM_SAFE_BUFFER", "TIGHTEN_ORDER_CAP")
    add("RETURN_TO_SUPPLIER_IF_ALLOWED", "TIGHTEN_ORDER_CAP")
    add("REVIEW_SLOT_LOCATION", "REVIEW_TRAVEL_DISTANCE")
    add("REVIEW_SLOT_LOCATION", "REVIEW_Z_LEVEL_ERGONOMICS")
    return [combo for combo in desired if len(combo) <= SCENARIO_OPTIMIZATION_CONFIG["max_combined_levers_per_scenario"] and not _contradiction(combo)[0]]


def _score_scenario(row: dict[str, Any], scenario: dict[str, Any]) -> dict:
    service, ss, rop, order_qty, cap_days, lead_time, lead_std = _scenario_parameters(row, scenario)
    unit_cost = _unit_cost(row)
    purchase_cost = order_qty * unit_cost
    ordering_cost = _num(row.get("recommended_fixed_order_cost"), SCENARIO_COST_DEFAULTS["fallback_ordering_cost"])
    holding_cost = _num(row.get("current_holding_cost"), order_qty * SCENARIO_COST_DEFAULTS["fallback_holding_cost_per_unit"])
    stockout_cost = _num(row.get("current_stockout_cost")) + _num(row.get("expected_stockout_risk_cost"))
    overstock_cost = _num(row.get("current_overstock_cost"))
    expiry_cost = _num(row.get("expired_stock_cost")) + _num(row.get("near_expiry_risk_cost"))
    dead_cost = _num(row.get("dead_stock_cost"))
    supplier_cost = _num(row.get("supplier_risk_cost"))
    space_cost = _num(row.get("storage_space_cost")) + _num(row.get("projected_space_utilization_cost"))
    travel_cost = _num(row.get("frequency_adjusted_travel_cost")) or _num(row.get("travel_cost"))
    receiving_penalty = _receiving_capacity_penalty(row, scenario)

    buffer = scenario["buffer_strategy"]
    supplier = scenario["supplier_strategy"]
    delivery = scenario["delivery_strategy"]
    expiry = scenario["expiry_strategy"]
    warehouse = scenario["warehouse_strategy"]
    if buffer == "INCREASE_BUFFER":
        holding_cost *= 1.12
        stockout_cost *= 0.70
    elif buffer in {"DECREASE_BUFFER", "MINIMUM_SAFE_BUFFER", "SERVICE_LEVEL_GUARDED_BUFFER"}:
        holding_cost *= 0.85
        overstock_cost *= 0.75
        stockout_cost *= 1.10 if _bool(row.get("stockout_re_eval_signal")) else 1.0
    if supplier == "FAST_RELIABLE_SUPPLIER":
        purchase_cost *= SCENARIO_IMPACT_FACTORS["fast_supplier_purchase_cost_multiplier"]
        stockout_cost *= SCENARIO_IMPACT_FACTORS["fast_supplier_stockout_risk_multiplier"]
        supplier_cost *= 0.60
    elif supplier == "MOST_RELIABLE_SUPPLIER":
        purchase_cost *= 1.15
        supplier_cost *= SCENARIO_IMPACT_FACTORS["reliable_supplier_risk_multiplier"]
    elif supplier == "CHEAPEST_SUPPLIER":
        purchase_cost *= SCENARIO_IMPACT_FACTORS["cheapest_supplier_purchase_cost_multiplier"]
        supplier_cost *= SCENARIO_IMPACT_FACTORS["cheapest_supplier_risk_multiplier"]
    elif supplier == "BALANCED_SUPPLIER":
        purchase_cost *= 1.03
        supplier_cost *= 0.75
    if delivery == "SPLIT_DELIVERY":
        receiving_penalty *= SCENARIO_IMPACT_FACTORS["split_delivery_receiving_penalty_multiplier"]
        ordering_cost *= SCENARIO_IMPACT_FACTORS["split_delivery_ordering_cost_multiplier"]
    elif delivery == "EXPEDITE_DELIVERY":
        ordering_cost *= SCENARIO_IMPACT_FACTORS["expedite_delivery_cost_multiplier"]
        stockout_cost *= 0.65
    elif delivery in {"DELAY_NONURGENT_ORDER", "NO_ORDER_WAIT_FOR_TRIGGER"}:
        purchase_cost *= 0.25 if delivery == "DELAY_NONURGENT_ORDER" else 0
        receiving_penalty *= 0
        stockout_cost *= 1.20 if _bool(row.get("stockout_re_eval_signal")) else 1.0
    if expiry == "MARKDOWN_NEAR_EXPIRY":
        expiry_cost *= SCENARIO_IMPACT_FACTORS["markdown_expiry_cost_multiplier"]
        overstock_cost *= 0.80
    elif expiry == "RETURN_TO_SUPPLIER_IF_ALLOWED":
        expiry_cost *= SCENARIO_IMPACT_FACTORS["return_supplier_expiry_cost_multiplier"]
    elif expiry == "QUARANTINE_OR_SCRAP_EXPIRED":
        expiry_cost *= 0.75
    elif expiry == "LIQUIDATE_DEAD_STOCK":
        dead_cost *= SCENARIO_IMPACT_FACTORS["liquidation_dead_stock_cost_multiplier"]
        holding_cost *= 0.80
    if warehouse in {"REVIEW_SLOT_LOCATION", "REVIEW_TRAVEL_DISTANCE", "REVIEW_Z_LEVEL_ERGONOMICS"}:
        travel_cost *= 0.75
        pass
    if warehouse == "REVIEW_RECEIVING_CAPACITY":
        pass

    feasibility = _evaluate_scenario_feasibility(row, scenario, service, ss, rop, order_qty)
    raw_constraint_penalty = feasibility["severity_based_constraint_penalty"]
    constraint_weight = SCENARIO_COST_WEIGHTS["constraint_violation_penalty"]
    weighted_constraint_penalty = feasibility["severity_based_constraint_penalty"]
    operational_cost = (
        purchase_cost * SCENARIO_COST_WEIGHTS["purchase_cost"]
        + ordering_cost
        + holding_cost
        + stockout_cost
        + overstock_cost
        + expiry_cost
        + dead_cost
        + supplier_cost
        + space_cost
        + travel_cost
    )
    risk_penalty_cost = receiving_penalty + feasibility["severity_based_review_penalty"] + feasibility["severity_based_soft_warning_penalty"]

    # Reporting buckets are the single source of truth for scenario totals.
    # Every detailed cost component must belong to exactly one of these buckets:
    # operational cost, risk/review penalty cost, or constraint penalty cost.
    scenario_operational_cost = round(float(max(operational_cost, 0)), 2)
    scenario_risk_penalty_cost = round(float(max(risk_penalty_cost, 0)), 2)
    scenario_constraint_penalty_cost = round(float(max(weighted_constraint_penalty, 0)), 2)
    total = round(
        scenario_operational_cost
        + scenario_risk_penalty_cost
        + scenario_constraint_penalty_cost,
        2,
    )
    reconciliation_difference = round(
        total
        - (
            scenario_operational_cost
            + scenario_risk_penalty_cost
            + scenario_constraint_penalty_cost
        ),
        4,
    )
    penalty_share = (
        (scenario_risk_penalty_cost + scenario_constraint_penalty_cost) / total
        if total > 0
        else 0
    )
    penalty_driven = penalty_share >= SCENARIO_COST_REPORTING["penalty_driven_saving_share_threshold"]
    return {
        **{col: scenario[col] for col in _SCENARIO_COLUMNS if col in scenario},
        "scenario_service_level": round(service, 3),
        "scenario_safety_stock": round(ss, 2),
        "scenario_reorder_point": _round_up_2(rop),
        "scenario_order_quantity": round(order_qty, 2),
        "scenario_order_cap_days": round(cap_days, 2),
        "scenario_expected_lead_time_days": round(lead_time, 2),
        "scenario_lead_time_std_days": round(lead_std, 2),
        "scenario_purchase_cost": round(purchase_cost, 2),
        "scenario_ordering_cost": round(ordering_cost, 2),
        "scenario_holding_cost": round(holding_cost, 2),
        "scenario_stockout_cost": round(stockout_cost, 2),
        "scenario_overstock_cost": round(overstock_cost, 2),
        "scenario_expiry_cost": round(expiry_cost, 2),
        "scenario_dead_stock_cost": round(dead_cost, 2),
        "scenario_supplier_risk_cost": round(supplier_cost, 2),
        "scenario_warehouse_space_cost": round(space_cost, 2),
        "scenario_warehouse_travel_cost": round(travel_cost, 2),
        "scenario_receiving_capacity_penalty": round(receiving_penalty, 2),
        "scenario_manual_review_penalty": round(feasibility["severity_based_review_penalty"], 2),
        "raw_constraint_violation_penalty": round(raw_constraint_penalty, 2),
        "weighted_constraint_violation_penalty": round(weighted_constraint_penalty, 2),
        "constraint_violation_penalty_weight": round(constraint_weight, 3),
        "scenario_constraint_violation_penalty": round(weighted_constraint_penalty, 2),
        "scenario_operational_cost": scenario_operational_cost,
        "scenario_risk_penalty_cost": scenario_risk_penalty_cost,
        "scenario_constraint_penalty_cost": scenario_constraint_penalty_cost,
        "scenario_total_penalty_adjusted_cost": total,
        "scenario_total_relevant_cost": total,
        "scenario_cost_reconciliation_difference": reconciliation_difference,
        "scenario_cost_reconciliation_ok": abs(reconciliation_difference) <= 0.01,
        "scenario_cost_basis": "PENALTY_ADJUSTED_TOTAL_COST",
        "scenario_penalty_share_of_total": round(penalty_share, 4),
        "scenario_penalty_driven_flag": penalty_driven,
        "scenario_cost_interpretation": _scenario_cost_interpretation(feasibility, receiving_penalty),
        "constraint_penalty_reason": _constraint_penalty_reason(feasibility),
        "scenario_cost_estimation_method": "RULE_BASED_ESTIMATE",
        **feasibility,
        "scenario_result_reason": _scenario_reason(scenario, feasibility),
    }


def _scenario_parameters(row, scenario):
    service = _num(row.get("current_service_level_target") or row.get("service_level_target"), 0.95)
    ss = _num(row.get("current_safety_stock") or row.get("safety_stock"))
    rop = _num(row.get("current_reorder_point") or row.get("reorder_point"))
    qty = _num(row.get("current_recommended_order_quantity") or row.get("recommended_order_quantity"))
    cap = _num(row.get("current_order_cap_days"), 30)
    lead = _num(row.get("expected_lead_time_days"), 7)
    lead_std = _num(row.get("lead_time_std_days"), 2)
    buffer = scenario["buffer_strategy"]
    if buffer == "INCREASE_BUFFER":
        service = max(service + SCENARIO_IMPACT_FACTORS["increase_buffer_service_level_delta"], _num(row.get("recommended_service_level_target"), service))
        ss = max(ss * SCENARIO_IMPACT_FACTORS["increase_buffer_safety_stock_multiplier"], _num(row.get("recommended_safety_stock"), ss))
        rop = max(rop * SCENARIO_IMPACT_FACTORS["increase_buffer_rop_multiplier"], _num(row.get("recommended_reorder_point"), rop))
    elif buffer == "DECREASE_BUFFER":
        service += SCENARIO_IMPACT_FACTORS["decrease_buffer_service_level_delta"]
        ss *= SCENARIO_IMPACT_FACTORS["decrease_buffer_safety_stock_multiplier"]
        rop *= SCENARIO_IMPACT_FACTORS["decrease_buffer_rop_multiplier"]
    elif buffer == "MINIMUM_SAFE_BUFFER":
        ss *= SCENARIO_IMPACT_FACTORS["minimum_safe_buffer_safety_stock_multiplier"]
        rop = max(rop * 0.80, ss)
    elif buffer == "SERVICE_LEVEL_GUARDED_BUFFER":
        service = max(service, _num(row.get("recommended_service_level_target"), service))
        ss = _num(row.get("recommended_safety_stock"), ss)
        rop = _num(row.get("recommended_reorder_point"), rop)
    if scenario["order_cap_strategy"] == "TIGHTEN_ORDER_CAP":
        qty *= SCENARIO_IMPACT_FACTORS["tighten_order_cap_multiplier"]
        cap *= SCENARIO_IMPACT_FACTORS["tighten_order_cap_multiplier"]
    elif scenario["order_cap_strategy"] == "LOOSEN_ORDER_CAP":
        qty *= SCENARIO_IMPACT_FACTORS["loosen_order_cap_multiplier"]
        cap *= SCENARIO_IMPACT_FACTORS["loosen_order_cap_multiplier"]
    elif scenario["order_cap_strategy"] == "CAP_BY_EXPIRY_OR_MOVEMENT":
        qty *= 0.60
        cap = min(cap, 21)
    if scenario["delivery_strategy"] == "NO_ORDER_WAIT_FOR_TRIGGER":
        qty = 0
    elif scenario["delivery_strategy"] == "DELAY_NONURGENT_ORDER":
        qty *= 0.25
    elif scenario["delivery_strategy"] == "EXPEDITE_DELIVERY":
        lead = max(1, lead * 0.70)
    min_service = _minimum_service(row)
    service = max(min(service, SCENARIO_FEASIBILITY_RULES["critical_priority_min_service_level"] if _text(row.get("inventory_priority_class")) == "CRITICAL_PRIORITY" else 0.99), min_service)
    ltd = _num(row.get("average_daily_demand"), 1) * lead
    rop = max(rop, ss + ltd, 0)
    return service, max(ss, 0), rop, max(qty, 0), max(cap, 1), lead, lead_std


def _evaluate_scenario_feasibility(row, scenario, service, ss, rop, qty) -> dict:
    hard_blockers = []
    major_risks = []
    review_required = []
    soft_warnings = []
    if service < _minimum_service(row):
        priority = _text(row.get("inventory_priority_class")).upper()
        vitality = _text(row.get("vitality_class")).upper()
        abc = _text(row.get("abc_class")).upper()
        movement = _text(row.get("movement_class")).upper()
        if vitality == "VITAL":
            hard_blockers.append("VITAL_SERVICE_LEVEL_BELOW_MIN")
        elif priority == "CRITICAL_PRIORITY":
            hard_blockers.append("CRITICAL_PRIORITY_SERVICE_LEVEL_BELOW_MIN")
        elif abc == "A":
            major_risks.append("ABC_A_SERVICE_LEVEL_BELOW_MIN")
        elif movement == "FAST_MOVING":
            major_risks.append("FAST_MOVING_SERVICE_LEVEL_BELOW_MIN")
        else:
            major_risks.append("SERVICE_LEVEL_BELOW_MINIMUM")
    ltd = _num(row.get("average_daily_demand"), 1) * _num(row.get("expected_lead_time_days"), 7)
    if rop < ss:
        hard_blockers.append("ROP_BELOW_SAFETY_STOCK")
    if rop < ss + ltd:
        hard_blockers.append("ROP_BELOW_SAFETY_STOCK_PLUS_LEAD_TIME_DEMAND")
    if qty < 0:
        hard_blockers.append("NEGATIVE_SCENARIO_ORDER_QUANTITY")
    receiving = _bool(row.get("sku_causes_projected_staging_pressure")) or _bool(row.get("replenishment_location_projected_over_capacity_flag"))
    if receiving and scenario["delivery_strategy"] != "SPLIT_DELIVERY" and scenario["warehouse_strategy"] != "REVIEW_RECEIVING_CAPACITY":
        major_risks.append("PROJECTED_RECEIVING_OVER_CAPACITY_WITHOUT_SPLIT_OR_REVIEW")
    elif receiving and scenario["warehouse_strategy"] == "REVIEW_RECEIVING_CAPACITY":
        review_required.append("PROJECTED_RECEIVING_CAPACITY_REVIEW_REQUIRED")
    if _bool(row.get("recommended_supplier_requires_review")) and scenario["supplier_strategy"] not in {"CURRENT_SUPPLIER", "SUPPLIER_REVIEW_ONLY"}:
        review_required.append("SUPPLIER_REVIEW_REQUIRED_WITH_SUPPLIER_CHANGE")
    elif _bool(row.get("supplier_risk_re_eval_signal")):
        soft_warnings.append("SUPPLIER_RISK_REMAINS")
    if _text(row.get("order_model_review_recommendation")) == "REVIEW_PHASE4_PRODUCTION_ORDER_MODEL":
        if scenario["buffer_strategy"] != "CURRENT_BUFFER" or scenario["order_cap_strategy"] != "CURRENT_ORDER_CAP":
            review_required.append("PHASE4_FINAL_POLICY_WITHOUT_REVIEW")
        else:
            review_required.append("PHASE4_FINAL_POLICY_REVIEW_REQUIRED")
    if _bool(row.get("forecast_uncertainty_re_eval_signal")):
        soft_warnings.append("FORECAST_CONFIDENCE_LOW")
    if _text(row.get("visual_travel_risk_group")).upper() not in {"", "NORMAL_TRAVEL"} and scenario["warehouse_strategy"] not in {"REVIEW_TRAVEL_DISTANCE", "REVIEW_SLOT_LOCATION"}:
        soft_warnings.append("TRAVEL_WARNING_REMAINS")
    if _bool(row.get("z_level_re_eval_signal")) and scenario["warehouse_strategy"] != "REVIEW_Z_LEVEL_ERGONOMICS":
        soft_warnings.append("Z_LEVEL_WARNING_REMAINS")
    if scenario["warehouse_strategy"].startswith("REVIEW"):
        review_required.append(f"{scenario['warehouse_strategy']}_REQUIRES_REVIEW")
    if scenario["supplier_strategy"] == "SUPPLIER_REVIEW_ONLY":
        review_required.append("SUPPLIER_REVIEW_ONLY_SELECTED")

    hard_blockers = _dedupe(hard_blockers)
    major_risks = _dedupe(major_risks)
    review_required = _dedupe(review_required)
    soft_warnings = _dedupe(soft_warnings)
    hard = bool(hard_blockers)
    requires_review = bool(review_required) or bool(major_risks and SCENARIO_SELECTION_CONFIG["allow_review_required_selection"])
    if hard:
        feasible = False
        status = "INFEASIBLE"
    elif major_risks or requires_review:
        feasible = True
        status = "FEASIBLE_WITH_REVIEW"
    else:
        feasible = True
        status = "FEASIBLE" if scenario["scenario_name"] != "CURRENT_POLICY" else "BASELINE_ONLY"
    constraint_penalty = min(
        len(hard_blockers) * SCENARIO_SEVERITY_PENALTIES["HARD_BLOCKER"]
        + len(major_risks) * SCENARIO_SEVERITY_PENALTIES["MAJOR_RISK"],
        SCENARIO_PENALTY_CAPS["max_constraint_penalty_per_scenario"],
        SCENARIO_PENALTY_CAPS["max_major_risk_penalty_per_scenario"] if not hard_blockers else SCENARIO_PENALTY_CAPS["max_constraint_penalty_per_scenario"],
    )
    review_penalty = min(
        len(review_required) * SCENARIO_SEVERITY_PENALTIES["REVIEW_REQUIRED"],
        SCENARIO_PENALTY_CAPS["max_review_penalty_per_scenario"],
    )
    soft_penalty = min(
        len(soft_warnings) * SCENARIO_SEVERITY_PENALTIES["SOFT_WARNING"],
        SCENARIO_PENALTY_CAPS["max_soft_warning_penalty_per_scenario"],
    )
    return {
        "feasible_flag": feasible,
        "hard_constraint_violation_flag": hard,
        "soft_constraint_warning_flag": bool(major_risks or soft_warnings),
        "requires_human_review": requires_review,
        "feasibility_status": status,
        "constraint_violations": "; ".join(hard_blockers + major_risks),
        "soft_warnings": "; ".join(review_required + soft_warnings),
        "hard_blocker_count": len(hard_blockers),
        "major_risk_count": len(major_risks),
        "review_required_count": len(review_required),
        "soft_warning_count": len(soft_warnings),
        "feasibility_severity": _feasibility_severity(hard_blockers, major_risks, review_required, soft_warnings),
        "hard_blocker_reasons": "; ".join(hard_blockers),
        "major_risk_reasons": "; ".join(major_risks),
        "review_required_reasons": "; ".join(review_required),
        "soft_warning_reasons": "; ".join(soft_warnings),
        "severity_based_constraint_penalty": round(constraint_penalty, 2),
        "severity_based_review_penalty": round(review_penalty, 2),
        "severity_based_soft_warning_penalty": round(soft_penalty, 2),
        "severity_penalty_total": round(constraint_penalty + review_penalty + soft_penalty, 2),
        "legacy_constraint_penalty_used_flag": False,
    }


def _select_best_scenario(row: dict[str, Any], results: list[dict]) -> dict:
    if not results:
        return {}
    baseline = next((result for result in results if result["scenario_name"] == "CURRENT_POLICY"), results[0])
    feasible = [result for result in results if result["feasibility_status"] in {"FEASIBLE", "BASELINE_ONLY"}]
    reviewable = [result for result in results if result["feasibility_status"] == "FEASIBLE_WITH_REVIEW"]
    if feasible:
        best_feasible = min(feasible, key=lambda item: item["scenario_total_penalty_adjusted_cost"])
        best_reviewable = min(reviewable, key=lambda item: item["scenario_total_penalty_adjusted_cost"], default=None)
        selected = best_feasible
        if best_reviewable and SCENARIO_SELECTION_CONFIG["allow_review_required_selection"]:
            saving_pct = (
                (best_feasible["scenario_total_penalty_adjusted_cost"] - best_reviewable["scenario_total_penalty_adjusted_cost"])
                / best_feasible["scenario_total_penalty_adjusted_cost"]
                if best_feasible["scenario_total_penalty_adjusted_cost"]
                else 0
            )
            if saving_pct > SCENARIO_SELECTION_CONFIG["prefer_no_review_if_cost_difference_pct_below"]:
                selected = best_reviewable
        if selected["scenario_name"] == "CURRENT_POLICY":
            status = "BASELINE_SELECTED"
        elif selected["requires_human_review"]:
            status = "SELECTED_LOWEST_COST_WITH_HUMAN_REVIEW"
        else:
            status = "SELECTED_LOWEST_FEASIBLE_COST"
    elif reviewable:
        selected = min(reviewable, key=lambda item: item["scenario_total_penalty_adjusted_cost"])
        status = "SELECTED_LOWEST_COST_WITH_HUMAN_REVIEW"
    else:
        selected = baseline
        status = "NO_FEASIBLE_SCENARIO_FOUND"
    candidate_pool = (feasible + reviewable) or [baseline]
    lowest_operational = min(candidate_pool, key=lambda item: item["scenario_operational_cost"])
    lowest_penalty_adjusted = min(candidate_pool, key=lambda item: item["scenario_total_penalty_adjusted_cost"])
    saving = baseline["scenario_total_penalty_adjusted_cost"] - selected["scenario_total_penalty_adjusted_cost"]
    operational_saving = baseline["scenario_operational_cost"] - selected["scenario_operational_cost"]
    risk_avoidance = baseline["scenario_risk_penalty_cost"] - selected["scenario_risk_penalty_cost"]
    constraint_avoidance = baseline["scenario_constraint_penalty_cost"] - selected["scenario_constraint_penalty_cost"]
    penalty_saving = risk_avoidance + constraint_avoidance
    penalty_driven = penalty_saving > abs(operational_saving)
    saving_type, saving_reason = _saving_interpretation(selected, operational_saving, penalty_saving)
    best_infeasible = min([r for r in results if r["feasibility_status"] == "INFEASIBLE"], key=lambda item: item["scenario_total_penalty_adjusted_cost"], default={})
    selected_for_lowest_operational = selected["scenario_id"] == lowest_operational["scenario_id"]
    selected_for_lowest_penalty = selected["scenario_id"] == lowest_penalty_adjusted["scenario_id"]
    return {
        "sku_id": row.get("sku_id"),
        "product_name": row.get("product_name"),
        "category": row.get("category"),
        "current_inventory": row.get("current_inventory"),
        "main_inventory_status": row.get("main_inventory_status"),
        "inventory_model_type": row.get("inventory_model_type"),
        "recommended_adjustment_direction": row.get("recommended_adjustment_direction"),
        "recommendation_strength": row.get("recommendation_strength"),
        "selected_scenario_id": selected["scenario_id"],
        "selected_scenario_name": selected["scenario_name"],
        "selected_buffer_strategy": selected["buffer_strategy"],
        "selected_supplier_strategy": selected["supplier_strategy"],
        "selected_delivery_strategy": selected["delivery_strategy"],
        "selected_order_cap_strategy": selected["order_cap_strategy"],
        "selected_expiry_strategy": selected["expiry_strategy"],
        "selected_warehouse_strategy": selected["warehouse_strategy"],
        "selected_service_level": selected["scenario_service_level"],
        "selected_safety_stock": selected["scenario_safety_stock"],
        "selected_reorder_point": selected["scenario_reorder_point"],
        "selected_order_quantity": selected["scenario_order_quantity"],
        "selected_total_relevant_cost": selected["scenario_total_relevant_cost"],
        "baseline_total_relevant_cost": baseline["scenario_total_relevant_cost"],
        "cost_saving_vs_baseline": round(saving, 2),
        "cost_saving_pct_vs_baseline": round((saving / baseline["scenario_total_penalty_adjusted_cost"]) if baseline["scenario_total_penalty_adjusted_cost"] else 0, 4),
        "selected_operational_cost": selected["scenario_operational_cost"],
        "baseline_operational_cost": baseline["scenario_operational_cost"],
        "operational_cost_saving_vs_baseline": round(operational_saving, 2),
        "operational_cost_saving_pct_vs_baseline": round((operational_saving / baseline["scenario_operational_cost"]) if baseline["scenario_operational_cost"] else 0, 4),
        "selected_risk_penalty_cost": selected["scenario_risk_penalty_cost"],
        "baseline_risk_penalty_cost": baseline["scenario_risk_penalty_cost"],
        "risk_penalty_avoidance_vs_baseline": round(risk_avoidance, 2),
        "selected_constraint_penalty_cost": selected["scenario_constraint_penalty_cost"],
        "baseline_constraint_penalty_cost": baseline["scenario_constraint_penalty_cost"],
        "constraint_penalty_avoidance_vs_baseline": round(constraint_avoidance, 2),
        "selected_total_penalty_adjusted_cost": selected["scenario_total_penalty_adjusted_cost"],
        "baseline_total_penalty_adjusted_cost": baseline["scenario_total_penalty_adjusted_cost"],
        "penalty_adjusted_saving_vs_baseline": round(saving, 2),
        "penalty_adjusted_saving_pct_vs_baseline": round((saving / baseline["scenario_total_penalty_adjusted_cost"]) if baseline["scenario_total_penalty_adjusted_cost"] else 0, 4),
        "saving_interpretation_type": saving_type,
        "saving_interpretation_reason": saving_reason,
        "penalty_driven_saving_flag": penalty_driven,
        "selection_cost_basis": "PENALTY_ADJUSTED_TOTAL_COST",
        "selected_for_lowest_operational_cost_flag": selected_for_lowest_operational,
        "selected_for_lowest_penalty_adjusted_cost_flag": selected_for_lowest_penalty,
        "lowest_operational_cost_scenario_id": lowest_operational["scenario_id"],
        "lowest_operational_cost_scenario_name": lowest_operational["scenario_name"],
        "lowest_operational_cost": lowest_operational["scenario_operational_cost"],
        "lowest_penalty_adjusted_cost_scenario_id": lowest_penalty_adjusted["scenario_id"],
        "lowest_penalty_adjusted_cost_scenario_name": lowest_penalty_adjusted["scenario_name"],
        "lowest_penalty_adjusted_cost": lowest_penalty_adjusted["scenario_total_penalty_adjusted_cost"],
        "selected_hard_blocker_count": selected["hard_blocker_count"],
        "selected_major_risk_count": selected["major_risk_count"],
        "selected_review_required_count": selected["review_required_count"],
        "selected_soft_warning_count": selected["soft_warning_count"],
        "selected_feasibility_severity": selected["feasibility_severity"],
        "selected_hard_blocker_reasons": selected["hard_blocker_reasons"],
        "selected_major_risk_reasons": selected["major_risk_reasons"],
        "selected_review_required_reasons": selected["review_required_reasons"],
        "selected_soft_warning_reasons": selected["soft_warning_reasons"],
        "selected_severity_based_constraint_penalty": selected["severity_based_constraint_penalty"],
        "selected_severity_based_review_penalty": selected["severity_based_review_penalty"],
        "selected_severity_based_soft_warning_penalty": selected["severity_based_soft_warning_penalty"],
        "selected_operational_vs_penalty_tradeoff_reason": _tradeoff_reason(selected, selected_for_lowest_operational, saving_type),
        "selected_feasibility_status": selected["feasibility_status"],
        "selected_requires_human_review": selected["requires_human_review"],
        "selected_constraint_violations": selected["constraint_violations"],
        "selected_soft_warnings": selected["soft_warnings"],
        "selection_status": status,
        "optimization_recommendation": _optimization_recommendation(selected, status),
        "optimization_reason": _optimization_reason(selected, saving, status, selected_for_lowest_operational, saving_type),
        "auto_apply_allowed": False,
        "scenario_count_tested": len(results),
        "feasible_scenario_count": len([r for r in results if r["feasibility_status"] in {"FEASIBLE", "BASELINE_ONLY", "FEASIBLE_WITH_REVIEW"}]),
        "infeasible_scenario_count": len([r for r in results if r["feasibility_status"] == "INFEASIBLE"]),
        "human_review_scenario_count": len([r for r in results if r["requires_human_review"]]),
        "best_infeasible_scenario_name": best_infeasible.get("scenario_name", ""),
        "best_infeasible_scenario_cost": best_infeasible.get("scenario_total_relevant_cost", 0),
    }


def _build_summary(recommendations: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    groups = [
        ("ALL_SKUS", None),
        ("BY_SELECTION_STATUS", "selection_status"),
        ("BY_SELECTED_SCENARIO_NAME", "selected_scenario_name"),
        ("BY_SELECTED_BUFFER_STRATEGY", "selected_buffer_strategy"),
        ("BY_SELECTED_SUPPLIER_STRATEGY", "selected_supplier_strategy"),
        ("BY_SELECTED_DELIVERY_STRATEGY", "selected_delivery_strategy"),
        ("BY_SELECTED_ORDER_CAP_STRATEGY", "selected_order_cap_strategy"),
        ("BY_SELECTED_EXPIRY_STRATEGY", "selected_expiry_strategy"),
        ("BY_SELECTED_WAREHOUSE_STRATEGY", "selected_warehouse_strategy"),
        ("BY_FEASIBILITY_STATUS", "selected_feasibility_status"),
        ("BY_REQUIRES_HUMAN_REVIEW", "selected_requires_human_review"),
        ("BY_INVENTORY_STATUS", "main_inventory_status"),
        ("BY_INVENTORY_MODEL_TYPE", "inventory_model_type"),
        ("BY_CATEGORY", "category"),
        ("BY_SAVING_INTERPRETATION_TYPE", "saving_interpretation_type"),
        ("BY_PENALTY_DRIVEN_SAVING_FLAG", "penalty_driven_saving_flag"),
        ("BY_SELECTION_COST_BASIS", "selection_cost_basis"),
        ("BY_SELECTED_FOR_LOWEST_OPERATIONAL_COST", "selected_for_lowest_operational_cost_flag"),
        ("BY_SELECTED_FOR_LOWEST_PENALTY_ADJUSTED_COST", "selected_for_lowest_penalty_adjusted_cost_flag"),
        ("BY_SELECTED_FEASIBILITY_SEVERITY", "selected_feasibility_severity"),
        ("BY_SELECTED_HARD_BLOCKER_COUNT", "selected_hard_blocker_count"),
        ("BY_SELECTED_MAJOR_RISK_COUNT", "selected_major_risk_count"),
        ("BY_SELECTED_REVIEW_REQUIRED_COUNT", "selected_review_required_count"),
        ("BY_SELECTED_SOFT_WARNING_COUNT", "selected_soft_warning_count"),
    ]
    rows = []
    for summary_type, column in groups:
        if column is None:
            rows.append(_summary_row(summary_type, "ALL", recommendations, results))
        else:
            for value, group in recommendations.groupby(recommendations[column].fillna("UNKNOWN").astype(str), dropna=False):
                rows.append(_summary_row(summary_type, value or "UNKNOWN", group, results[results["sku_id"].isin(group["sku_id"])]))
    pos = recommendations[recommendations["cost_saving_vs_baseline"] > 0]
    non_pos = recommendations[recommendations["cost_saving_vs_baseline"] <= 0]
    rows.append(_summary_row("BY_COST_SAVING_POSITIVE_NEGATIVE", "POSITIVE_SAVING", pos, results[results["sku_id"].isin(pos["sku_id"])]))
    rows.append(_summary_row("BY_COST_SAVING_POSITIVE_NEGATIVE", "NO_OR_NEGATIVE_SAVING", non_pos, results[results["sku_id"].isin(non_pos["sku_id"])]))
    result_groups = [
        ("BY_SCENARIO_FEASIBILITY_SEVERITY", "feasibility_severity"),
        ("BY_SCENARIO_HARD_BLOCKER_COUNT", "hard_blocker_count"),
        ("BY_SCENARIO_MAJOR_RISK_COUNT", "major_risk_count"),
        ("BY_SCENARIO_REVIEW_REQUIRED_COUNT", "review_required_count"),
        ("BY_SCENARIO_SOFT_WARNING_COUNT", "soft_warning_count"),
    ]
    for summary_type, column in result_groups:
        if column not in results.columns:
            continue
        for value, group in results.groupby(results[column].fillna("UNKNOWN").astype(str), dropna=False):
            rows.append(_summary_row(summary_type, value or "UNKNOWN", recommendations[recommendations["sku_id"].isin(group["sku_id"])], group))
    return pd.DataFrame(rows)


def _summary_row(summary_type, group_name, recs, res):
    selected_operational = _sum(recs, "selected_operational_cost")
    baseline_operational = _sum(recs, "baseline_operational_cost")
    selected_risk_penalty = _sum(recs, "selected_risk_penalty_cost")
    baseline_risk_penalty = _sum(recs, "baseline_risk_penalty_cost")
    selected_constraint_penalty = _sum(recs, "selected_constraint_penalty_cost")
    baseline_constraint_penalty = _sum(recs, "baseline_constraint_penalty_cost")
    selected_adjusted = _sum(recs, "selected_total_penalty_adjusted_cost")
    baseline_adjusted = _sum(recs, "baseline_total_penalty_adjusted_cost")
    return {
        "summary_type": summary_type,
        "group_name": group_name,
        "sku_count": len(recs),
        "scenario_count": len(res),
        "feasible_scenario_count": int(res["feasible_flag"].sum()) if not res.empty and "feasible_flag" in res else 0,
        "infeasible_scenario_count": int((res["feasibility_status"] == "INFEASIBLE").sum()) if not res.empty else 0,
        "human_review_scenario_count": int(res["requires_human_review"].sum()) if not res.empty and "requires_human_review" in res else 0,
        "average_selected_cost": round(float(recs["selected_total_relevant_cost"].mean()) if not recs.empty else 0, 2),
        "total_selected_cost": round(float(recs["selected_total_relevant_cost"].sum()) if not recs.empty else 0, 2),
        "total_baseline_cost": round(float(recs["baseline_total_relevant_cost"].sum()) if not recs.empty else 0, 2),
        "total_cost_saving_vs_baseline": round(float(recs["cost_saving_vs_baseline"].sum()) if not recs.empty else 0, 2),
        "average_cost_saving_pct": round(float(recs["cost_saving_pct_vs_baseline"].mean()) if not recs.empty else 0, 4),
        "selected_requires_human_review_count": int(recs["selected_requires_human_review"].sum()) if not recs.empty else 0,
        "total_selected_operational_cost": round(selected_operational, 2),
        "total_baseline_operational_cost": round(baseline_operational, 2),
        "total_operational_cost_saving_vs_baseline": round(baseline_operational - selected_operational, 2),
        "total_selected_risk_penalty_cost": round(selected_risk_penalty, 2),
        "total_baseline_risk_penalty_cost": round(baseline_risk_penalty, 2),
        "total_risk_penalty_avoidance_vs_baseline": round(baseline_risk_penalty - selected_risk_penalty, 2),
        "total_selected_constraint_penalty_cost": round(selected_constraint_penalty, 2),
        "total_baseline_constraint_penalty_cost": round(baseline_constraint_penalty, 2),
        "total_constraint_penalty_avoidance_vs_baseline": round(baseline_constraint_penalty - selected_constraint_penalty, 2),
        "total_selected_penalty_adjusted_cost": round(selected_adjusted, 2),
        "total_baseline_penalty_adjusted_cost": round(baseline_adjusted, 2),
        "total_penalty_adjusted_saving_vs_baseline": round(baseline_adjusted - selected_adjusted, 2),
        "penalty_driven_saving_count": _true_sum(recs, "penalty_driven_saving_flag"),
        "operational_saving_count": int((recs.get("saving_interpretation_type", pd.Series(dtype=str)) == "OPERATIONAL_SAVING").sum()) if not recs.empty else 0,
        "cost_increase_with_risk_reduction_count": int((recs.get("saving_interpretation_type", pd.Series(dtype=str)) == "COST_INCREASE_WITH_RISK_REDUCTION").sum()) if not recs.empty else 0,
        "total_hard_blocker_count": int(_sum(res, "hard_blocker_count")),
        "total_major_risk_count": int(_sum(res, "major_risk_count")),
        "total_review_required_count": int(_sum(res, "review_required_count")),
        "total_soft_warning_count": int(_sum(res, "soft_warning_count")),
        "selected_hard_blocker_count": int(_sum(recs, "selected_hard_blocker_count")),
        "selected_major_risk_count": int(_sum(recs, "selected_major_risk_count")),
        "selected_review_required_count": int(_sum(recs, "selected_review_required_count")),
        "selected_soft_warning_count": int(_sum(recs, "selected_soft_warning_count")),
        "average_constraint_penalty": round(_mean(res, "severity_based_constraint_penalty"), 2),
        "average_review_penalty": round(_mean(res, "severity_based_review_penalty"), 2),
        "average_soft_warning_penalty": round(_mean(res, "severity_based_soft_warning_penalty"), 2),
    }


def _sum(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())


def _true_sum(df: pd.DataFrame, column: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    return int(df[column].map(_bool).sum())


def _mean(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).mean())


def _unit_cost(row):
    qty = _num(row.get("recommended_order_quantity") or row.get("current_recommended_order_quantity"))
    order_cost = _num(row.get("recommended_total_order_cost"))
    if qty > 0 and order_cost > 0:
        return order_cost / qty
    return _num(row.get("unit_cost_procurement") or row.get("unit_cost_inventory"), SCENARIO_COST_DEFAULTS["fallback_purchase_unit_cost"])


def _minimum_service(row):
    minimum = 0.70
    if _text(row.get("vitality_class")).upper() == "VITAL":
        minimum = max(minimum, SCENARIO_FEASIBILITY_RULES["vital_min_service_level"])
    if _text(row.get("inventory_priority_class")).upper() == "CRITICAL_PRIORITY":
        minimum = max(minimum, SCENARIO_FEASIBILITY_RULES["critical_priority_min_service_level"])
    if _text(row.get("abc_class")).upper() == "A":
        minimum = max(minimum, SCENARIO_FEASIBILITY_RULES["abc_a_min_service_level"])
    if _text(row.get("movement_class")).upper() == "FAST_MOVING":
        minimum = max(minimum, SCENARIO_FEASIBILITY_RULES["fast_moving_min_service_level"])
    return minimum


def _scenario_requires_review(row, scenario):
    return (
        _bool(row.get("requires_human_review"))
        or scenario["supplier_strategy"] == "SUPPLIER_REVIEW_ONLY"
        or scenario["warehouse_strategy"].startswith("REVIEW")
        or _text(row.get("order_model_review_recommendation")) == "REVIEW_PHASE4_PRODUCTION_ORDER_MODEL"
    )


def _receiving_capacity_penalty(row, scenario):
    receiving = _bool(row.get("sku_causes_projected_staging_pressure")) or _bool(row.get("replenishment_location_projected_over_capacity_flag"))
    if not receiving:
        return 0.0
    base = SCENARIO_RECEIVING_CAPACITY_PENALTY["base_penalty"]
    if _bool(row.get("replenishment_location_projected_over_capacity_flag")):
        multiplier = SCENARIO_RECEIVING_CAPACITY_PENALTY["over_capacity_multiplier"]
    else:
        multiplier = SCENARIO_RECEIVING_CAPACITY_PENALTY["capacity_pressure_multiplier"]
    split = scenario["delivery_strategy"] == "SPLIT_DELIVERY"
    review = scenario["warehouse_strategy"] == "REVIEW_RECEIVING_CAPACITY"
    if split and review:
        multiplier *= SCENARIO_RECEIVING_CAPACITY_PENALTY["split_and_review_penalty_multiplier"]
    elif split:
        multiplier *= SCENARIO_RECEIVING_CAPACITY_PENALTY["split_delivery_penalty_multiplier"]
    elif review:
        multiplier *= SCENARIO_RECEIVING_CAPACITY_PENALTY["review_receiving_penalty_multiplier"]
    return base * multiplier


def _feasibility_severity(hard_blockers, major_risks, review_required, soft_warnings):
    if hard_blockers:
        return "HARD_BLOCKER"
    if major_risks:
        return "MAJOR_RISK"
    if review_required:
        return "REVIEW_REQUIRED"
    if soft_warnings:
        return "SOFT_WARNING"
    return "NO_ISSUE"


def _dedupe(values):
    unique = []
    for value in values:
        if value and value not in unique:
            unique.append(value)
    return unique


def _optimization_recommendation(selected, status):
    if status == "BASELINE_SELECTED":
        return "KEEP_CURRENT_POLICY"
    if status == "NO_FEASIBLE_SCENARIO_FOUND":
        return "NO_FEASIBLE_SCENARIO_REVIEW_REQUIRED"
    if selected["requires_human_review"]:
        return "APPLY_SELECTED_SCENARIO_AFTER_REVIEW"
    name = selected["scenario_name"]
    if "SPLIT_DELIVERY" in name:
        return "SPLIT_DELIVERY_TO_AVOID_RECEIVING_OVERLOAD"
    if "DECREASE_BUFFER" in name or "TIGHTEN_ORDER_CAP" in name:
        return "REDUCE_BUFFER_AND_TIGHTEN_CAP"
    if "INCREASE_BUFFER" in name or "FAST_RELIABLE_SUPPLIER" in name:
        return "INCREASE_BUFFER_WITH_FAST_SUPPLIER"
    if "MARKDOWN" in name or "RETURN_TO_SUPPLIER" in name:
        return "MARKDOWN_OR_RETURN_EXPIRY_RISK_STOCK"
    return "REVIEW_SELECTED_SCENARIO"


def _saving_interpretation(selected, operational_saving: float, penalty_saving: float) -> tuple[str, str]:
    total_saving = operational_saving + penalty_saving
    requires_review = _bool(selected.get("requires_human_review"))
    if requires_review:
        return (
            "REVIEW_REQUIRED",
            "Selected scenario requires human review; cost and penalty changes are recommendation-only and not direct cash savings.",
        )
    if total_saving <= 0:
        return "NO_SAVING", "Selected scenario does not reduce penalty-adjusted total cost versus baseline."
    if operational_saving > 0 and penalty_saving <= max(abs(operational_saving) * 0.25, 1):
        return "OPERATIONAL_SAVING", "Selected scenario reduces estimated operational cost."
    if operational_saving < 0 and penalty_saving > abs(operational_saving):
        return (
            "COST_INCREASE_WITH_RISK_REDUCTION",
            "Selected scenario increases operating cost but lowers risk or constraint penalties.",
        )
    if penalty_saving > abs(operational_saving):
        return (
            "PENALTY_AVOIDANCE",
            "Selected scenario mainly avoids risk or hard-constraint penalties; this is risk avoidance, not direct cash saving.",
        )
    return (
        "MIXED_OPERATIONAL_AND_PENALTY_SAVING",
        "Selected scenario reduces both operating cost and risk or constraint penalty exposure.",
    )


def _tradeoff_reason(selected, selected_for_lowest_operational, saving_type):
    pieces = []
    if selected.get("feasibility_severity") in {"MAJOR_RISK", "REVIEW_REQUIRED"}:
        pieces.append(
            f"Selected scenario has {selected.get('feasibility_severity')} severity and must be reviewed before action."
        )
    if not selected_for_lowest_operational:
        pieces.append("Lowest operational-cost scenario differs from the selected penalty-adjusted scenario.")
    if saving_type == "PENALTY_AVOIDANCE":
        pieces.append("Selection is driven mainly by avoiding risk/review/constraint penalty exposure.")
    if not pieces:
        pieces.append("Selected scenario has the best feasible cost profile without a material operational-vs-penalty conflict.")
    return " ".join(pieces)


def _optimization_reason(selected, saving, status, selected_for_lowest_operational=True, saving_type="NO_SAVING"):
    reason = (
        f"{status}: selected {selected['scenario_name']} using PENALTY_ADJUSTED_TOTAL_COST "
        f"with penalty-adjusted saving {saving:.2f}; recommendation only, not auto-applied."
    )
    if saving_type == "PENALTY_AVOIDANCE":
        reason += " Reported saving is mainly penalty avoidance, not direct operational cash saving."
    elif saving_type == "COST_INCREASE_WITH_RISK_REDUCTION":
        reason += " Operational cost may increase while risk or constraint penalty exposure decreases."
    elif saving_type == "OPERATIONAL_SAVING":
        reason += " Selected scenario also reduces estimated operational cost."
    if not selected_for_lowest_operational:
        reason += " Lowest operational-cost scenario differs because penalties or risk constraints make the selected scenario safer."
    return reason


def _constraint_penalty_reason(feasibility):
    hard = _num(feasibility.get("hard_blocker_count"))
    major = _num(feasibility.get("major_risk_count"))
    review = _num(feasibility.get("review_required_count"))
    soft = _num(feasibility.get("soft_warning_count"))
    reasons = []
    for key in ("hard_blocker_reasons", "major_risk_reasons", "review_required_reasons", "soft_warning_reasons"):
        text = _text(feasibility.get(key))
        if text:
            reasons.append(text)
    if not any([hard, major, review, soft]):
        return "No severity-based feasibility penalty."
    return (
        f"Severity-based penalty used: hard blockers={int(hard)}, major risks={int(major)}, "
        f"review-required={int(review)}, soft warnings={int(soft)}. Reasons: {'; '.join(reasons)}"
    )


def _scenario_cost_interpretation(feasibility, receiving_penalty):
    severity = feasibility.get("feasibility_severity", "NO_ISSUE")
    if severity == "HARD_BLOCKER":
        return "Contains hard blocker; severity-based penalty prevents normal selection."
    if receiving_penalty > 0 and feasibility.get("major_risk_count", 0) > 0:
        return "Operational cost plus receiving capacity major-risk penalty; not direct cash cost."
    if feasibility.get("review_required_count", 0) > 0:
        return "Operational cost plus review-required penalty; review penalty is not direct operating cost."
    return "Operational cost plus severity-based risk/review/constraint penalties; not direct cash cost."


def _scenario_reason(scenario, feasibility):
    return f"Scenario {scenario['scenario_name']} scored with {feasibility['feasibility_status']} feasibility."


def _contradiction(values):
    value_set = set(values)
    for pair in SCENARIO_CONTRADICTION_RULES:
        if set(pair).issubset(value_set):
            return True, "Contradictory levers: " + " + ".join(pair)
    return False, ""


def _generation_reason(row):
    return f"Generated from {row.get('recommended_adjustment_direction')} / {row.get('main_inventory_status')} / {row.get('main_cost_driver')} signals."


def _extend(target, values):
    for value in values:
        if value not in target:
            target.append(value)


def _text(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _num(value, default=0.0):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value):
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"true", "1", "yes", "y"}


def _round_up_2(value: float) -> float:
    return math.ceil((value - 1e-9) * 100) / 100


_SCENARIO_COLUMNS = [
    "sku_id", "product_name", "category", "scenario_id", "scenario_name", "scenario_rank_generated",
    "lever_count", "buffer_strategy", "supplier_strategy", "delivery_strategy", "order_cap_strategy",
    "expiry_strategy", "warehouse_strategy", "scenario_generation_reason", "scenario_contradiction_flag",
    "scenario_contradiction_reason", "generated_from_re_evaluation_direction", "generated_from_main_status",
    "generated_from_cost_driver", "generated_from_warehouse_signal",
]

_RESULT_COLUMNS = _SCENARIO_COLUMNS[:13] + [
    "scenario_service_level", "scenario_safety_stock", "scenario_reorder_point", "scenario_order_quantity",
    "scenario_order_cap_days", "scenario_expected_lead_time_days", "scenario_lead_time_std_days",
    "scenario_purchase_cost", "scenario_ordering_cost", "scenario_holding_cost", "scenario_stockout_cost",
    "scenario_overstock_cost", "scenario_expiry_cost", "scenario_dead_stock_cost", "scenario_supplier_risk_cost",
    "scenario_warehouse_space_cost", "scenario_warehouse_travel_cost", "scenario_receiving_capacity_penalty",
    "scenario_manual_review_penalty", "raw_constraint_violation_penalty", "weighted_constraint_violation_penalty",
    "constraint_violation_penalty_weight", "scenario_constraint_violation_penalty", "scenario_operational_cost",
    "scenario_risk_penalty_cost", "scenario_constraint_penalty_cost", "scenario_total_penalty_adjusted_cost",
    "scenario_total_relevant_cost", "scenario_cost_reconciliation_difference",
    "scenario_cost_reconciliation_ok", "scenario_cost_basis", "scenario_penalty_share_of_total",
    "scenario_penalty_driven_flag", "scenario_cost_interpretation", "constraint_penalty_reason",
    "hard_blocker_count", "major_risk_count", "review_required_count", "soft_warning_count",
    "feasibility_severity", "hard_blocker_reasons", "major_risk_reasons", "review_required_reasons",
    "soft_warning_reasons", "severity_based_constraint_penalty", "severity_based_review_penalty",
    "severity_based_soft_warning_penalty", "severity_penalty_total", "legacy_constraint_penalty_used_flag",
    "scenario_cost_estimation_method", "feasible_flag", "hard_constraint_violation_flag",
    "soft_constraint_warning_flag", "requires_human_review", "feasibility_status", "constraint_violations",
    "soft_warnings", "scenario_result_reason",
]

_RECOMMENDATION_COLUMNS = [
    "sku_id", "product_name", "category", "current_inventory", "main_inventory_status", "inventory_model_type",
    "recommended_adjustment_direction", "recommendation_strength", "selected_scenario_id", "selected_scenario_name",
    "selected_buffer_strategy", "selected_supplier_strategy", "selected_delivery_strategy",
    "selected_order_cap_strategy", "selected_expiry_strategy", "selected_warehouse_strategy",
    "selected_service_level", "selected_safety_stock", "selected_reorder_point", "selected_order_quantity",
    "selected_total_relevant_cost", "baseline_total_relevant_cost", "cost_saving_vs_baseline",
    "cost_saving_pct_vs_baseline", "selected_operational_cost", "baseline_operational_cost",
    "operational_cost_saving_vs_baseline", "operational_cost_saving_pct_vs_baseline",
    "selected_risk_penalty_cost", "baseline_risk_penalty_cost", "risk_penalty_avoidance_vs_baseline",
    "selected_constraint_penalty_cost", "baseline_constraint_penalty_cost", "constraint_penalty_avoidance_vs_baseline",
    "selected_total_penalty_adjusted_cost", "baseline_total_penalty_adjusted_cost",
    "penalty_adjusted_saving_vs_baseline", "penalty_adjusted_saving_pct_vs_baseline",
    "saving_interpretation_type", "saving_interpretation_reason", "penalty_driven_saving_flag",
    "selection_cost_basis", "selected_for_lowest_operational_cost_flag",
    "selected_for_lowest_penalty_adjusted_cost_flag", "lowest_operational_cost_scenario_id",
    "lowest_operational_cost_scenario_name", "lowest_operational_cost",
    "lowest_penalty_adjusted_cost_scenario_id", "lowest_penalty_adjusted_cost_scenario_name",
    "lowest_penalty_adjusted_cost", "selected_hard_blocker_count", "selected_major_risk_count",
    "selected_review_required_count", "selected_soft_warning_count", "selected_feasibility_severity",
    "selected_hard_blocker_reasons", "selected_major_risk_reasons", "selected_review_required_reasons",
    "selected_soft_warning_reasons", "selected_severity_based_constraint_penalty",
    "selected_severity_based_review_penalty", "selected_severity_based_soft_warning_penalty",
    "selected_operational_vs_penalty_tradeoff_reason",
    "selected_feasibility_status", "selected_requires_human_review",
    "selected_constraint_violations", "selected_soft_warnings", "selection_status", "optimization_recommendation",
    "optimization_reason", "auto_apply_allowed", "scenario_count_tested", "feasible_scenario_count",
    "infeasible_scenario_count", "human_review_scenario_count", "best_infeasible_scenario_name",
    "best_infeasible_scenario_cost",
]
