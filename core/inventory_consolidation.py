"""Final manager-facing consolidation outputs for Phase 3 inventory control."""

from __future__ import annotations

from typing import Any

import pandas as pd

from config import FINAL_PRIORITY_TUNING, INVENTORY_CONSOLIDATION_CONFIG


PRIORITY_ORDER = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NO_ACTION": 4}
RISK_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}


def build_inventory_control_consolidation(
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
    inventory_cost_summary: pd.DataFrame,
    warehouse_slotting: pd.DataFrame,
    batch_slotting: pd.DataFrame,
    location_utilization: pd.DataFrame,
    space_utilization: pd.DataFrame,
    warehouse_travel_costs: pd.DataFrame,
    warehouse_visual_grid: pd.DataFrame,
    warehouse_visual_locations: pd.DataFrame,
    warehouse_visual_skus: pd.DataFrame,
    warehouse_visual_batches: pd.DataFrame,
    warehouse_visual_summary: pd.DataFrame,
    inventory_re_evaluation: pd.DataFrame,
    inventory_parameter_adjustment_recommendations: pd.DataFrame,
    re_evaluation_summary: pd.DataFrame,
    inventory_scenarios: pd.DataFrame,
    inventory_scenario_results: pd.DataFrame,
    inventory_optimization_recommendations: pd.DataFrame,
    inventory_optimization_summary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build final master decisions and compact manager reporting files."""
    master = _merge_sku_context(
        inventory_optimization_recommendations,
        [
            inventory_clean,
            planning_context,
            inventory_classification,
            inventory_service_levels,
            inventory_policy,
            inventory_policy_parameters,
            inventory_status,
            inventory_action_recommendations,
            inventory_costs,
            warehouse_slotting,
            warehouse_visual_skus,
            inventory_re_evaluation,
            inventory_parameter_adjustment_recommendations,
        ],
    )
    if master.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, empty, empty, empty, empty, empty

    enriched_rows = []
    for _, row in master.iterrows():
        record = row.to_dict()
        record.update(_final_risk(record))
        record.update(_final_review(record))
        record.update(_final_priority(record))
        record.update(_final_action(record))
        record.update(_traceability(record))
        record["auto_apply_allowed"] = False
        enriched_rows.append(record)
    master = pd.DataFrame(enriched_rows)
    master = _ensure_columns(master, MASTER_COLUMNS)[MASTER_COLUMNS]

    review_queue = _build_human_review_queue(master)
    advisory_queue = _build_advisory_review_queue(master)
    action_plan = _build_action_plan(master)
    risk_register = _build_risk_register(master)
    executive_summary = _build_executive_summary(master, inventory_status, warehouse_slotting)
    kpi_summary = _build_kpi_summary(master, inventory_service_levels, inventory_policy_parameters, inventory_scenarios, location_utilization)
    dashboard = _build_manager_dashboard(master)
    return master, review_queue, advisory_queue, executive_summary, kpi_summary, action_plan, risk_register, dashboard


def _merge_sku_context(base_df: pd.DataFrame, source_dfs: list[pd.DataFrame]) -> pd.DataFrame:
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


def _final_priority(row: dict[str, Any]) -> dict[str, Any]:
    status = _text(row.get("main_inventory_status")).upper()
    action_priority = _text(row.get("action_priority")).upper()
    cost_risk = _text(row.get("cost_risk_level")).upper()
    vitality = _text(row.get("vitality_class")).upper()
    priority_class = _text(row.get("inventory_priority_class")).upper()
    score = 0.0
    reasons = []

    if status in {"STOCKOUT", "ZERO_STOCK"}:
        score += FINAL_PRIORITY_TUNING["stockout_score_add"] if status == "STOCKOUT" else FINAL_PRIORITY_TUNING["zero_stock_score_add"]
        reasons.append(f"{status} inventory status.")
    elif status in {"CRITICAL_LOW_STOCK", "REORDER_NOW"}:
        score += FINAL_PRIORITY_TUNING["critical_low_score_add"] if status == "CRITICAL_LOW_STOCK" else FINAL_PRIORITY_TUNING["reorder_now_score_add"]
        reasons.append(f"{status} requires replenishment attention.")
    elif status == "APPROACHING_REORDER_POINT":
        score += FINAL_PRIORITY_TUNING["approaching_rop_score_add"]
        reasons.append("Approaching reorder point.")
    elif status == "OVERSTOCK":
        score += FINAL_PRIORITY_TUNING["overstock_score_add"]
        reasons.append("Overstock requires inventory control attention.")

    if action_priority == "URGENT":
        score += 20
        reasons.append("Underlying action priority is urgent.")
    elif action_priority == "HIGH":
        score += 12
    elif action_priority == "MEDIUM":
        score += 6

    if cost_risk == "CRITICAL":
        score += FINAL_PRIORITY_TUNING["cost_critical_score_add"]
        reasons.append("CRITICAL cost risk.")
    elif cost_risk == "HIGH":
        score += FINAL_PRIORITY_TUNING["cost_high_score_add"]
        reasons.append(f"{cost_risk} cost risk.")
    elif cost_risk == "MEDIUM":
        score += 4

    if _bool(row.get("final_mandatory_review_required")):
        score += FINAL_PRIORITY_TUNING["mandatory_review_score_add"]
        reasons.append("Mandatory review blocks direct action.")
    elif _bool(row.get("final_advisory_review_required")):
        score += FINAL_PRIORITY_TUNING["advisory_review_score_add"]
        reasons.append("Advisory review is recommended but not blocking.")
    elif _bool(row.get("final_info_warning_only")):
        score += FINAL_PRIORITY_TUNING["info_warning_score_add"]
    if _num(row.get("selected_major_risk_count")) > 0:
        score += FINAL_PRIORITY_TUNING["major_risk_score_add"]
        reasons.append("Selected scenario has major risk.")
    if _num(row.get("selected_review_required_count")) > 0:
        score += FINAL_PRIORITY_TUNING["review_required_score_add"]
    if _num(row.get("selected_hard_blocker_count")) > 0:
        score += 40
        reasons.append("Selected scenario has hard blocker.")
    if _bool(row.get("sku_causes_projected_staging_pressure")):
        score += 4
        reasons.append("Projected receiving or staging pressure exists.")
    if _text(row.get("supplier_review_recommendation")).upper() not in {"", "NO_SUPPLIER_REVIEW"}:
        score += 3
    if _text(row.get("warehouse_review_recommendation")).upper() not in {"", "NO_WAREHOUSE_REVIEW"}:
        score += 3
    if _text(row.get("perishability_class")).upper() in {"SPOILAGE_RISK", "EXPIRY_TRACKED"} or _num(row.get("expired_units")) > 0:
        score += 6

    urgent_blocking = (
        _bool(row.get("final_mandatory_review_required"))
        and status in {"STOCKOUT", "ZERO_STOCK", "CRITICAL_LOW_STOCK"}
        and (vitality == "VITAL" or priority_class == "CRITICAL_PRIORITY" or action_priority == "URGENT")
    )
    if FINAL_PRIORITY_TUNING["vital_critical_stockout_override"] and status in {"STOCKOUT", "ZERO_STOCK"} and (vitality == "VITAL" or priority_class == "CRITICAL_PRIORITY"):
        priority = "URGENT"
        reasons.append("Vital/critical SKU is stocked out or at zero stock.")
    elif _num(row.get("selected_hard_blocker_count")) > 0:
        priority = "URGENT"
    elif urgent_blocking:
        priority = "URGENT"
    elif score >= FINAL_PRIORITY_TUNING["urgent_score_threshold"]:
        priority = "URGENT"
    elif score >= FINAL_PRIORITY_TUNING["high_score_threshold"]:
        priority = "HIGH"
    elif score >= FINAL_PRIORITY_TUNING["medium_score_threshold"]:
        priority = "MEDIUM"
    elif score >= FINAL_PRIORITY_TUNING["low_score_threshold"]:
        priority = "LOW"
    else:
        priority = "NO_ACTION"
        reasons.append("No immediate risk or action signal.")
    return {
        "final_decision_priority": priority,
        "final_priority_score": round(score, 2),
        "final_priority_reason": _reason(reasons),
    }


def _final_action(row: dict[str, Any]) -> dict[str, Any]:
    proposed_action, proposed_owner, proposed_reason = _proposed_operational_action(row)
    blocking_action = _blocking_review_action(row)
    review_type = _text(row.get("final_review_type")).upper()
    mandatory_gates = _text(row.get("mandatory_review_gates")).upper()
    final_action = proposed_action
    if blocking_action == "REVIEW_PHASE4_PRODUCTION_LOGIC":
        final_action = blocking_action
    elif blocking_action == "REVIEW_SUPPLIER_BEFORE_ORDER":
        final_action = blocking_action
    elif blocking_action == "REVIEW_WAREHOUSE_CAPACITY" and proposed_action == "SPLIT_DELIVERY":
        final_action = "SPLIT_DELIVERY"
    elif blocking_action == "REVIEW_EXPIRY_DISPOSITION":
        final_action = proposed_action
    elif blocking_action == "REVIEW_POLICY_PARAMETERS" and _bool(row.get("final_mandatory_review_required")):
        final_action = proposed_action if proposed_action not in {"MONITOR_ONLY", "NO_ACTION"} else blocking_action

    review_owner = _review_owner(review_type if review_type != "NO_REVIEW_REQUIRED" else _text(row.get("primary_review_type")).upper())
    if not _bool(row.get("final_mandatory_review_required")) and not _bool(row.get("final_advisory_review_required")):
        review_owner = "NO_REVIEW_REQUIRED"
    execution_owner = _determine_execution_owner(proposed_action, review_type, mandatory_gates, _text(row.get("advisory_review_gates")).upper())
    if final_action == "SPLIT_DELIVERY" and review_type == "WAREHOUSE_REVIEW":
        owner = "WAREHOUSE_TEAM"
        review_owner = "WAREHOUSE_TEAM"
        execution_owner = "PROCUREMENT_TEAM; WAREHOUSE_TEAM"
    elif review_type == "MANDATORY_MULTI_DEPARTMENT_REVIEW" or _num(row.get("mandatory_review_gate_count")) > 1 and final_action.startswith("REVIEW_"):
        owner = "MULTI_DEPARTMENT_REVIEW"
        review_owner = "MULTI_DEPARTMENT_REVIEW"
    else:
        owner = _determine_execution_owner(final_action, review_type, mandatory_gates, _text(row.get("advisory_review_gates")).upper())

    reasons = [proposed_reason]
    if blocking_action != "NO_BLOCKING_REVIEW" and final_action.startswith("REVIEW_"):
        reasons.append(f"{blocking_action} is the blocking step. Proposed operational action after review: {proposed_action}.")
    elif blocking_action != "NO_BLOCKING_REVIEW":
        reasons.append(f"{blocking_action} must be completed before execution approval.")
    visibility = (
        "Final action shows the blocking review gate; proposed operational action is listed separately."
        if blocking_action != "NO_BLOCKING_REVIEW" and final_action.startswith("REVIEW_")
        else "Final action shows the proposed operational execution action."
    )
    owner_reason = _owner_assignment_reason(proposed_action, final_action, review_type, execution_owner, review_owner)

    manager_status = "MONITOR"
    actionable = proposed_action not in {"NO_ACTION", "MONITOR_ONLY", "WAIT_FOR_TRIGGER"}
    priority = _text(row.get("final_decision_priority")).upper()
    if _bool(row.get("final_mandatory_review_required")):
        manager_status = "REVIEW_BEFORE_ACTION"
    elif priority in {"URGENT", "HIGH"} and actionable:
        manager_status = "TAKE_ACTION_NOW"
    elif priority in {"MEDIUM", "LOW"} or _bool(row.get("final_advisory_review_required")):
        manager_status = "MONITOR"
    elif proposed_action == "NO_ACTION":
        manager_status = "NO_ACTION_REQUIRED"
    readiness = _action_readiness(proposed_action, priority, _bool(row.get("final_mandatory_review_required")), _bool(row.get("final_advisory_review_required")))
    return {
        "final_recommended_action": final_action,
        "final_action_reason": _reason(reasons),
        "final_action_owner": owner,
        "final_manager_status": manager_status,
        "blocking_review_action": blocking_action,
        "proposed_operational_action": proposed_action,
        "proposed_operational_owner": proposed_owner,
        "execution_owner": execution_owner,
        "review_owner": review_owner,
        "owner_assignment_reason": owner_reason,
        "action_visibility_note": visibility,
        "action_blocked_by_mandatory_review": _bool(row.get("final_mandatory_review_required")),
        "advisory_review_exists": _bool(row.get("final_advisory_review_required")),
        "action_readiness": readiness,
    }


def _final_review(row: dict[str, Any]) -> dict[str, Any]:
    mandatory = []
    advisory = []
    info = []
    mandatory_types = []
    advisory_types = []
    info_types = []
    reasons = []

    selected_changes_policy = _text(row.get("selected_buffer_strategy")).upper() != "CURRENT_BUFFER" or _text(row.get("selected_order_cap_strategy")).upper() != "CURRENT_ORDER_CAP"
    supplier_changed = _text(row.get("selected_supplier_strategy")).upper() not in {"", "CURRENT_SUPPLIER"}
    supplier_review = _text(row.get("supplier_review_recommendation")).upper() not in {"", "NO_SUPPLIER_REVIEW"}
    warehouse_review = _text(row.get("warehouse_review_recommendation")).upper() not in {"", "NO_WAREHOUSE_REVIEW"}
    policy_review = _text(row.get("policy_review_recommendation")).upper() not in {"", "KEEP_POLICY"}
    phase4_signal = "PHASE4" in _text(row.get("order_model_review_recommendation")).upper()
    split_delivery = _text(row.get("selected_delivery_strategy")).upper() == "SPLIT_DELIVERY"
    receiving_pressure = _bool(row.get("sku_causes_projected_staging_pressure"))
    expiry_strategy = _text(row.get("selected_expiry_strategy")).upper()
    selected_review = _bool(row.get("selected_requires_human_review")) and _text(row.get("selected_feasibility_status")).upper() == "FEASIBLE_WITH_REVIEW"

    if _num(row.get("selected_hard_blocker_count")) > 0:
        mandatory.append("HARD_BLOCKER_GATE")
        mandatory_types.append("POLICY_REVIEW")
        reasons.append("Selected scenario has hard blocker.")
    if selected_review:
        mandatory.append("SELECTED_SCENARIO_REVIEW_GATE")
        mandatory_types.append("POLICY_REVIEW")
        reasons.append("Selected scenario is feasible only with human review.")
    if phase4_signal and selected_changes_policy:
        mandatory.append("PHASE4_GATE")
        mandatory_types.append("PHASE4_REVIEW")
        reasons.append("Selected action changes policy/order assumptions for a Phase 4-related SKU.")
    elif phase4_signal:
        advisory.append("ADVISORY_POLICY_SIGNAL")
        advisory_types.append("PHASE4_REVIEW")
    if supplier_changed and supplier_review:
        mandatory.append("SUPPLIER_CHANGE_GATE")
        mandatory_types.append("SUPPLIER_REVIEW")
        reasons.append("Selected scenario changes supplier while supplier review is active.")
    elif supplier_review:
        advisory.append("ADVISORY_SUPPLIER_SIGNAL")
        advisory_types.append("SUPPLIER_REVIEW")
    if split_delivery and receiving_pressure:
        mandatory.append("RECEIVING_CAPACITY_GATE")
        mandatory_types.append("WAREHOUSE_REVIEW")
        reasons.append("Selected split delivery depends on receiving/staging capacity review.")
    elif warehouse_review or receiving_pressure:
        advisory.append("ADVISORY_WAREHOUSE_SIGNAL")
        advisory_types.append("WAREHOUSE_REVIEW")
    if expiry_strategy in {"MARKDOWN_NEAR_EXPIRY", "RETURN_TO_SUPPLIER_IF_ALLOWED", "QUARANTINE_OR_SCRAP_EXPIRED", "LIQUIDATE_DEAD_STOCK"}:
        mandatory.append("EXPIRY_DISPOSITION_GATE")
        mandatory_types.append("EXPIRY_REVIEW")
        reasons.append("Selected expiry/dead-stock disposition needs approval.")
    if selected_changes_policy and selected_review:
        mandatory.append("POLICY_PARAMETER_GATE")
        mandatory_types.append("POLICY_REVIEW")
    elif policy_review:
        advisory.append("ADVISORY_POLICY_SIGNAL")
        advisory_types.append("POLICY_REVIEW")
    if _bool(row.get("penalty_driven_saving_flag")) or _text(row.get("cost_risk_level")).upper() in {"CRITICAL", "HIGH"}:
        advisory.append("ADVISORY_COST_SIGNAL")
        advisory_types.append("FINANCE_COST_REVIEW")
    if _num(row.get("selected_soft_warning_count")) > 0 and not mandatory and not advisory:
        info.append("INFO_WARNING_ONLY")
        info_types.append("POLICY_REVIEW")

    mandatory = _dedupe(mandatory)
    advisory = _dedupe(advisory)
    info = _dedupe(info)
    mandatory_types = _dedupe(mandatory_types)
    advisory_types = _dedupe(advisory_types)
    info_types = _dedupe(info_types)
    if mandatory:
        severity = "MANDATORY"
        required = True
        primary_type = mandatory_types[0] if mandatory_types else "POLICY_REVIEW"
        review_type = "MANDATORY_MULTI_DEPARTMENT_REVIEW" if len(mandatory_types) > 1 else primary_type
        owner = "MULTI_DEPARTMENT_REVIEW" if len(mandatory_types) > 1 else _review_owner(primary_type)
    elif advisory:
        severity = "ADVISORY"
        required = False
        primary_type = advisory_types[0] if advisory_types else "POLICY_REVIEW"
        review_type = primary_type
        owner = _review_owner(primary_type)
        reasons.append("Advisory review is recommended but does not block action.")
    elif info:
        severity = "INFO_ONLY"
        required = False
        primary_type = info_types[0] if info_types else "NO_REVIEW_REQUIRED"
        review_type = "NO_REVIEW_REQUIRED"
        owner = "NO_OWNER_REQUIRED"
        reasons.append("Only informational warnings are present.")
    else:
        severity = "NO_REVIEW"
        required = False
        primary_type = "NO_REVIEW_REQUIRED"
        review_type = "NO_REVIEW_REQUIRED"
        owner = "NO_OWNER_REQUIRED"
        reasons.append("No review gate is active.")
    secondary_types = [item for item in _dedupe(mandatory_types + advisory_types + info_types) if item != primary_type]
    return {
        "final_review_required": required,
        "final_mandatory_review_required": bool(mandatory),
        "final_advisory_review_required": bool(advisory) and not mandatory,
        "final_info_warning_only": bool(info) and not mandatory and not advisory,
        "final_review_severity": severity,
        "final_review_type": review_type,
        "primary_review_type": primary_type,
        "secondary_review_types": "; ".join(secondary_types),
        "mandatory_review_gates": "; ".join(mandatory),
        "advisory_review_gates": "; ".join(advisory),
        "info_review_gates": "; ".join(info),
        "review_gate_count": len(mandatory) + len(advisory) + len(info),
        "mandatory_review_gate_count": len(mandatory),
        "advisory_review_gate_count": len(advisory),
        "info_review_gate_count": len(info),
        "final_review_reason": _reason(reasons),
        "final_review_owner": owner,
    }


def _final_risk(row: dict[str, Any]) -> dict[str, Any]:
    status = _text(row.get("main_inventory_status")).upper()
    risk_types = []
    reasons = []
    if status in {"STOCKOUT", "ZERO_STOCK", "CRITICAL_LOW_STOCK", "REORDER_NOW"}:
        risk_types.append("STOCKOUT_RISK")
        reasons.append(f"{status} status creates shortage risk.")
    if status == "OVERSTOCK" or "OVERSTOCK" in _text(row.get("secondary_status_flags")).upper():
        risk_types.append("OVERSTOCK_RISK")
        reasons.append("Overstock or days-of-supply risk exists.")
    if _num(row.get("expired_units")) > 0 or "EXPIRY" in _text(row.get("secondary_status_flags")).upper():
        risk_types.append("EXPIRY_RISK")
        reasons.append("Expiry or near-expiry signal exists.")
    if "DEAD_STOCK" in _text(row.get("secondary_status_flags")).upper() or _text(row.get("movement_class")).upper() == "NON_MOVING":
        risk_types.append("DEAD_STOCK_RISK")
        reasons.append("Dead stock or non-moving signal exists.")
    if _text(row.get("supplier_review_recommendation")).upper() not in {"", "NO_SUPPLIER_REVIEW"}:
        risk_types.append("SUPPLIER_RISK")
        reasons.append("Supplier review signal exists.")
    if _bool(row.get("sku_causes_projected_staging_pressure")) or "CAPACITY" in _text(row.get("slotting_warning_flags")).upper():
        risk_types.append("RECEIVING_STAGING_RISK")
        risk_types.append("WAREHOUSE_CAPACITY_RISK")
        reasons.append("Warehouse capacity or staging risk exists.")
    if "TRAVEL" in _text(row.get("slotting_warning_flags")).upper() or "Z_LEVEL" in _text(row.get("slotting_warning_flags")).upper():
        risk_types.append("TRAVEL_OR_SLOT_RISK")
        reasons.append("Travel, slotting, or z-level warning exists.")
    if _text(row.get("policy_review_recommendation")).upper() not in {"", "KEEP_POLICY"}:
        risk_types.append("POLICY_RISK")
    if "PHASE4" in _text(row.get("order_model_review_recommendation")).upper():
        risk_types.append("PHASE4_PRODUCTION_RISK")
    if _text(row.get("cost_risk_level")).upper() in {"CRITICAL", "HIGH"}:
        risk_types.append("COST_RISK")
    if _bool(row.get("cost_fallback_flag")):
        risk_types.append("DATA_QUALITY_RISK")

    risk_types = _dedupe(risk_types)
    severity_points = len(risk_types)
    if status in {"STOCKOUT", "ZERO_STOCK"} or _text(row.get("cost_risk_level")).upper() == "CRITICAL":
        level = "CRITICAL"
    elif _num(row.get("selected_major_risk_count")) > 0 or severity_points >= 4:
        level = "HIGH"
    elif severity_points >= 2 or _num(row.get("selected_review_required_count")) > 0:
        level = "MEDIUM"
    elif severity_points == 1:
        level = "LOW"
    else:
        level = "NONE"
        reasons.append("No material risk signal found.")
    return {
        "final_risk_level": level,
        "final_risk_types": "; ".join(risk_types) if risk_types else "NONE",
        "final_risk_reason": _reason(reasons),
    }


def _traceability(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_inventory_status": row.get("main_inventory_status"),
        "source_re_evaluation_direction": row.get("recommended_adjustment_direction"),
        "source_optimization_selection_status": row.get("selection_status"),
        "source_selected_scenario_status": row.get("selected_feasibility_status"),
        "source_main_cost_driver": row.get("main_cost_driver"),
        "source_warehouse_review": row.get("warehouse_review_recommendation"),
        "source_supplier_review": row.get("supplier_review_recommendation"),
        "source_policy_review": row.get("policy_review_recommendation"),
    }


def _build_human_review_queue(master: pd.DataFrame) -> pd.DataFrame:
    queue = master[master["final_mandatory_review_required"].map(_bool)].copy()
    queue["_priority_sort"] = queue["final_decision_priority"].map(PRIORITY_ORDER).fillna(9)
    queue["_risk_sort"] = queue["final_risk_level"].map(RISK_ORDER).fillna(9)
    queue = queue.sort_values(
        ["_priority_sort", "_risk_sort", "penalty_adjusted_saving_vs_baseline", "operational_cost_saving_vs_baseline"],
        ascending=[True, True, False, False],
    ).drop(columns=["_priority_sort", "_risk_sort"], errors="ignore")
    queue.insert(0, "review_rank", range(1, len(queue) + 1))
    queue["next_review_step"] = queue.apply(_next_review_step, axis=1)
    return _ensure_columns(queue, REVIEW_QUEUE_COLUMNS)[REVIEW_QUEUE_COLUMNS]


def _build_advisory_review_queue(master: pd.DataFrame) -> pd.DataFrame:
    queue = master[(~master["final_mandatory_review_required"].map(_bool)) & master["final_advisory_review_required"].map(_bool)].copy()
    queue["_priority_sort"] = queue["final_decision_priority"].map(PRIORITY_ORDER).fillna(9)
    queue["_risk_sort"] = queue["final_risk_level"].map(RISK_ORDER).fillna(9)
    queue = queue.sort_values(
        ["_priority_sort", "_risk_sort", "penalty_adjusted_saving_vs_baseline", "operational_cost_saving_vs_baseline"],
        ascending=[True, True, False, False],
    ).drop(columns=["_priority_sort", "_risk_sort"], errors="ignore")
    queue.insert(0, "advisory_rank", range(1, len(queue) + 1))
    queue["suggested_advisory_step"] = queue.apply(_suggested_advisory_step, axis=1)
    return _ensure_columns(queue, ADVISORY_QUEUE_COLUMNS)[ADVISORY_QUEUE_COLUMNS]


def _build_action_plan(master: pd.DataFrame) -> pd.DataFrame:
    plan = master[master["final_manager_status"] != "NO_ACTION_REQUIRED"].copy()
    readiness_order = {
        "READY_TO_ACT": 0,
        "REVIEW_REQUIRED_BEFORE_ACTION": 1,
        "ADVISORY_REVIEW_RECOMMENDED": 2,
        "MONITOR_ONLY": 3,
        "NO_ACTION": 4,
    }
    plan["_readiness_sort"] = plan["action_readiness"].map(readiness_order).fillna(9)
    plan["_priority_sort"] = plan["final_decision_priority"].map(PRIORITY_ORDER).fillna(9)
    plan = plan.sort_values(["_readiness_sort", "_priority_sort", "penalty_adjusted_saving_vs_baseline"], ascending=[True, True, False])
    plan = plan.drop(columns=["_priority_sort"], errors="ignore")
    plan = plan.drop(columns=["_readiness_sort"], errors="ignore")
    plan.insert(0, "action_rank", range(1, len(plan) + 1))
    plan["suggested_next_step"] = plan.apply(_suggested_next_step, axis=1)
    return _ensure_columns(plan, ACTION_PLAN_COLUMNS)[ACTION_PLAN_COLUMNS]


def _build_risk_register(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in master.iterrows():
        risks = [risk.strip() for risk in _text(row.get("final_risk_types")).split(";") if risk.strip() and risk.strip() != "NONE"]
        for risk in risks:
            rows.append(
                {
                    "risk_id": f"{row['sku_id']}-{risk}",
                    "sku_id": row.get("sku_id"),
                    "product_name": row.get("product_name"),
                    "category": row.get("category"),
                    "risk_type": risk,
                    "risk_level": row.get("final_risk_level"),
                    "risk_source": _risk_source(risk),
                    "risk_description": _risk_description(risk),
                    "risk_driver": row.get("final_risk_reason"),
                    "related_status": row.get("main_inventory_status"),
                    "related_cost_driver": row.get("main_cost_driver"),
                    "related_selected_scenario": row.get("selected_scenario_name"),
                    "mitigation_action": row.get("final_recommended_action"),
                    "risk_owner": row.get("final_action_owner"),
                    "review_required": row.get("final_review_required"),
                    "review_type": row.get("final_review_type"),
                    "risk_priority": row.get("final_decision_priority"),
                    "review_severity": row.get("final_review_severity"),
                    "mandatory_review_gate": row.get("mandatory_review_gates"),
                    "advisory_review_gate": row.get("advisory_review_gates"),
                    "action_readiness": row.get("action_readiness"),
                }
            )
    return pd.DataFrame(rows, columns=RISK_REGISTER_COLUMNS)


def _build_executive_summary(master: pd.DataFrame, inventory_status: pd.DataFrame, warehouse_slotting: pd.DataFrame) -> pd.DataFrame:
    rows = []
    add = rows.append
    total = len(master)
    for metric, value, note in [
        ("total_skus", total, "Total SKUs in final Phase 3 decision set."),
        ("stockout_skus", _count(master, "main_inventory_status", "STOCKOUT"), "SKUs currently in stockout."),
        ("zero_stock_skus", _count(master, "main_inventory_status", "ZERO_STOCK"), "SKUs with zero stock."),
        ("critical_low_stock_skus", _count(master, "main_inventory_status", "CRITICAL_LOW_STOCK"), "SKUs below safety protection."),
        ("reorder_now_skus", _count(master, "main_inventory_status", "REORDER_NOW"), "SKUs at or below reorder point."),
        ("overstock_skus", _count(master, "main_inventory_status", "OVERSTOCK"), "SKUs carrying excess inventory."),
        ("healthy_skus", _count(master, "main_inventory_status", "HEALTHY"), "SKUs with healthy inventory position."),
    ]:
        add(_summary_row("INVENTORY_STATUS", metric, value, "count", note))
    for metric, col, value in [
        ("urgent_decisions", "final_decision_priority", "URGENT"),
        ("high_priority_decisions", "final_decision_priority", "HIGH"),
        ("medium_priority_decisions", "final_decision_priority", "MEDIUM"),
        ("low_priority_decisions", "final_decision_priority", "LOW"),
        ("no_action_decisions", "final_decision_priority", "NO_ACTION"),
        ("take_action_now_count", "final_manager_status", "TAKE_ACTION_NOW"),
        ("review_before_action_count", "final_manager_status", "REVIEW_BEFORE_ACTION"),
        ("monitor_count", "final_manager_status", "MONITOR"),
        ("no_action_required_count", "final_manager_status", "NO_ACTION_REQUIRED"),
        ("ready_to_act_count", "action_readiness", "READY_TO_ACT"),
        ("advisory_review_recommended_count", "action_readiness", "ADVISORY_REVIEW_RECOMMENDED"),
    ]:
        add(_summary_row("FINAL_DECISIONS", metric, _count(master, col, value), "count", f"{value} final decision count."))
    for metric, value in [
        ("mandatory_review_required_count", _true_count(master, "final_mandatory_review_required")),
        ("advisory_review_required_count", _true_count(master, "final_advisory_review_required")),
        ("info_warning_only_count", _true_count(master, "final_info_warning_only")),
        ("no_review_required_count", _count(master, "final_review_severity", "NO_REVIEW")),
        ("multi_department_review_count", _count(master, "final_review_type", "MANDATORY_MULTI_DEPARTMENT_REVIEW")),
        ("primary_procurement_review_count", _count(master, "primary_review_type", "PROCUREMENT_REVIEW")),
        ("primary_supplier_review_count", _count(master, "primary_review_type", "SUPPLIER_REVIEW")),
        ("primary_warehouse_review_count", _count(master, "primary_review_type", "WAREHOUSE_REVIEW")),
        ("primary_expiry_review_count", _count(master, "primary_review_type", "EXPIRY_REVIEW")),
        ("primary_policy_review_count", _count(master, "primary_review_type", "POLICY_REVIEW")),
        ("primary_phase4_review_count", _count(master, "primary_review_type", "PHASE4_REVIEW")),
        ("primary_finance_review_count", _count(master, "primary_review_type", "FINANCE_COST_REVIEW")),
    ]:
        add(_summary_row("HUMAN_REVIEW", metric, value, "count", "Mandatory review blocks action; advisory review is non-blocking; info warnings are trace-only."))
    for metric, value in [
        ("total_baseline_operational_cost", _sum(master, "baseline_operational_cost")),
        ("total_selected_operational_cost", _sum(master, "selected_operational_cost")),
        ("total_operational_saving", _sum(master, "operational_cost_saving_vs_baseline")),
        ("total_baseline_penalty_adjusted_cost", _sum(master, "baseline_total_penalty_adjusted_cost")),
        ("total_selected_penalty_adjusted_cost", _sum(master, "selected_total_penalty_adjusted_cost")),
        ("total_penalty_adjusted_saving", _sum(master, "penalty_adjusted_saving_vs_baseline")),
        ("operational_saving_sku_count", _count(master, "saving_interpretation_type", "OPERATIONAL_SAVING")),
        ("penalty_avoidance_sku_count", _count(master, "saving_interpretation_type", "PENALTY_AVOIDANCE")),
        ("review_required_sku_count", _count(master, "saving_interpretation_type", "REVIEW_REQUIRED")),
    ]:
        add(_summary_row("OPTIMIZATION_RESULTS", metric, value, "value", "Optimization result metric."))
    for metric, value in [
        ("projected_receiving_overcapacity_skus", _true_count(master, "sku_causes_projected_staging_pressure")),
        ("selected_split_delivery_skus", _count(master, "selected_delivery_strategy", "SPLIT_DELIVERY")),
        ("warehouse_review_skus", _contains_count(master, "final_review_type", "WAREHOUSE")),
        ("travel_or_slot_review_skus", _contains_count(master, "final_risk_types", "TRAVEL_OR_SLOT_RISK")),
        ("z_level_warning_skus", _contains_count(master, "slotting_warning_flags", "Z_LEVEL")),
    ]:
        add(_summary_row("WAREHOUSE", metric, value, "count", "Warehouse risk/action indicator."))
    for metric, value in [
        ("expired_stock_skus", _contains_count(master, "secondary_status_flags", "EXPIRED_STOCK")),
        ("near_expiry_skus", _contains_count(master, "secondary_status_flags", "NEAR_EXPIRY")),
        ("dead_stock_or_non_moving_skus", _contains_count(master, "final_risk_types", "DEAD_STOCK_RISK")),
        ("markdown_or_liquidation_action_skus", _contains_any_count(master, "final_recommended_action", ["MARKDOWN", "LIQUIDATE"])),
        ("quarantine_or_scrap_action_skus", _contains_count(master, "final_recommended_action", "QUARANTINE")),
    ]:
        add(_summary_row("EXPIRY_AND_DEAD_STOCK", metric, value, "count", "Expiry/dead-stock action indicator."))
    for metric, value in [
        ("selected_lowest_feasible_cost_count", _count(master, "selection_status", "SELECTED_LOWEST_FEASIBLE_COST")),
        ("selected_with_human_review_count", _count(master, "selection_status", "SELECTED_LOWEST_COST_WITH_HUMAN_REVIEW")),
        ("selected_no_issue_count", _count(master, "selected_feasibility_severity", "NO_ISSUE")),
        ("selected_review_required_count", _count(master, "selected_feasibility_severity", "REVIEW_REQUIRED")),
        ("selected_soft_warning_count", _count(master, "selected_feasibility_severity", "SOFT_WARNING")),
        ("selected_major_risk_count", _count(master, "selected_feasibility_severity", "MAJOR_RISK")),
        ("selected_hard_blocker_count", _count(master, "selected_feasibility_severity", "HARD_BLOCKER")),
    ]:
        add(_summary_row("SCENARIO_SELECTION", metric, value, "count", "Selected scenario quality indicator."))
    for metric, value in [
        ("phase4_blocking_review_count", _count(master, "blocking_review_action", "REVIEW_PHASE4_PRODUCTION_LOGIC")),
        ("split_delivery_action_count", _count(master, "proposed_operational_action", "SPLIT_DELIVERY")),
        ("proposed_liquidation_action_count", _count(master, "proposed_operational_action", "LIQUIDATE_DEAD_STOCK")),
        ("proposed_buffer_change_action_count", _contains_any_count(master, "proposed_operational_action", ["INCREASE_BUFFER", "REDUCE_BUFFER"])),
        ("proposed_supplier_change_action_count", _count(master, "proposed_operational_action", "USE_FAST_RELIABLE_SUPPLIER")),
        ("ready_to_execute_after_review_count", _count(master, "action_readiness", "REVIEW_REQUIRED_BEFORE_ACTION")),
        ("advisory_not_blocking_count", _true_count(master, "final_advisory_review_required")),
    ]:
        add(_summary_row("ACTION_CLARITY", metric, value, "count", "Separates blocking review from proposed operational execution."))
    return pd.DataFrame(rows)


def _build_kpi_summary(master: pd.DataFrame, service_levels: pd.DataFrame, policy_parameters: pd.DataFrame, scenarios: pd.DataFrame, locations: pd.DataFrame) -> pd.DataFrame:
    total = max(len(master), 1)
    kpis = [
        ("Inventory Health", "stockout_rate", _rate(_count(master, "main_inventory_status", "STOCKOUT"), total), "%", "<5%", "BAD" if _count(master, "main_inventory_status", "STOCKOUT") else "GOOD", "Share of SKUs in stockout."),
        ("Inventory Health", "overstock_rate", _rate(_count(master, "main_inventory_status", "OVERSTOCK"), total), "%", "<20%", "WATCH", "Share of SKUs overstocked."),
        ("Review Load", "review_required_rate", _rate(_true_count(master, "final_review_required"), total), "%", "Lower is better", "WATCH", "Share of SKUs requiring human review."),
        ("Review Load", "mandatory_review_rate", _rate(_true_count(master, "final_mandatory_review_required"), total), "%", "Lower is better", "WATCH", "Mandatory review share."),
        ("Review Load", "advisory_review_rate", _rate(_true_count(master, "final_advisory_review_required"), total), "%", "Informational", "INFO", "Non-blocking advisory review share."),
        ("Review Load", "ready_to_act_rate", _rate(_count(master, "action_readiness", "READY_TO_ACT"), total), "%", "Higher is better", "GOOD", "Share ready for direct action."),
        ("Review Load", "review_before_action_rate", _rate(_count(master, "final_manager_status", "REVIEW_BEFORE_ACTION"), total), "%", "Lower is better", "WATCH", "Share blocked by mandatory review."),
        ("Review Load", "monitor_rate", _rate(_count(master, "final_manager_status", "MONITOR"), total), "%", "Informational", "INFO", "Share that should be monitored."),
        ("Review Load", "no_action_rate", _rate(_count(master, "final_manager_status", "NO_ACTION_REQUIRED"), total), "%", "Informational", "INFO", "Share requiring no action."),
        ("Review Load", "mandatory_multi_department_review_rate", _rate(_count(master, "final_review_type", "MANDATORY_MULTI_DEPARTMENT_REVIEW"), total), "%", "Lower is better", "WATCH", "Share with multiple mandatory review gates."),
        ("Review Load", "urgent_action_rate", _rate(_count(master, "final_decision_priority", "URGENT"), total), "%", "Lower is better", "WATCH", "Share of urgent final decisions."),
        ("Cost", "projected_operational_saving", _sum(master, "operational_cost_saving_vs_baseline"), "currency", "Positive", "GOOD", "Estimated operating cost saving."),
        ("Cost", "projected_penalty_adjusted_saving", _sum(master, "penalty_adjusted_saving_vs_baseline"), "currency", "Positive", "INFO", "Penalty-adjusted saving includes risk/review penalties."),
        ("Optimization", "selected_scenarios_with_review_rate", _rate(_true_count(master, "selected_requires_human_review"), total), "%", "Lower is better", "WATCH", "Selected scenarios needing review."),
        ("Optimization", "selected_scenarios_no_hard_blocker_rate", _rate(total - _numeric_positive_count(master, "selected_hard_blocker_count"), total), "%", "100%", "GOOD", "Selected scenarios without hard blockers."),
        ("Warehouse", "warehouse_capacity_pressure_rate", _rate(_true_count(locations, "projected_capacity_pressure_flag") + _true_count(locations, "projected_over_capacity_flag"), max(len(locations), 1)), "%", "Lower is better", "WATCH", "Projected capacity pressure by location."),
        ("Inventory Health", "expiry_risk_rate", _rate(_contains_count(master, "final_risk_types", "EXPIRY_RISK"), total), "%", "Lower is better", "WATCH", "SKUs with expiry risk."),
        ("Review Load", "phase4_review_rate", _rate(_contains_count(master, "final_review_type", "PHASE4") + _contains_count(master, "final_risk_types", "PHASE4"), total), "%", "As needed", "INFO", "SKUs needing Phase 4 production review."),
        ("Service Level", "average_service_level", _mean(service_levels, "service_level_target"), "ratio", "Policy dependent", "INFO", "Average configured service level."),
        ("Service Level", "average_safety_stock", _mean(policy_parameters, "safety_stock"), "units", "Policy dependent", "INFO", "Average calculated safety stock."),
        ("Inventory Health", "total_recommended_order_quantity", _sum(policy_parameters, "recommended_order_quantity"), "units", "Policy dependent", "INFO", "Total recommended order quantity from Step 6."),
        ("Optimization", "average_scenarios_tested_per_sku", float(scenarios.groupby("sku_id").size().mean()) if not scenarios.empty and "sku_id" in scenarios else 0, "scenarios/SKU", "Controlled by config", "INFO", "Average Step 12 scenarios tested per SKU."),
        ("Review Load", "phase4_blocking_review_rate", _rate(_count(master, "blocking_review_action", "REVIEW_PHASE4_PRODUCTION_LOGIC"), total), "%", "As needed", "INFO", "Phase 4 blocking review share."),
        ("Review Load", "owner_assignment_completeness_rate", _rate(total - _blank_count(master, "execution_owner"), total), "%", "100%", "GOOD", "Rows with execution owner populated."),
        ("Optimization", "proposed_operational_action_completeness_rate", _rate(total - _blank_count(master, "proposed_operational_action"), total), "%", "100%", "GOOD", "Rows with proposed operational action populated."),
    ]
    return pd.DataFrame(kpis, columns=["kpi_category", "kpi_name", "kpi_value", "kpi_unit", "target_or_reference", "status", "explanation"])


def _build_manager_dashboard(master: pd.DataFrame) -> pd.DataFrame:
    dashboard = master.copy()
    dashboard["suggested_dashboard_badge"] = dashboard.apply(_dashboard_badge, axis=1)
    dashboard["suggested_dashboard_color_group"] = dashboard.apply(_dashboard_color, axis=1)
    return _ensure_columns(dashboard, DASHBOARD_COLUMNS)[DASHBOARD_COLUMNS]


def _next_review_step(row):
    proposed = _text(row.get("proposed_operational_action"))
    review_type = _text(row.get("final_review_type")).upper()
    blocking = _text(row.get("blocking_review_action")).upper()
    if blocking == "REVIEW_PHASE4_PRODUCTION_LOGIC":
        return f"Confirm Phase 4 production/BOM logic before approving proposed operational action: {proposed}."
    if proposed == "SPLIT_DELIVERY" or "WAREHOUSE" in review_type:
        return "Confirm receiving and staging capacity before approving split delivery."
    if "SUPPLIER" in review_type:
        return "Confirm supplier choice and lead time before ordering."
    if "EXPIRY" in review_type:
        return "Approve expiry/dead-stock disposition before warehouse or commercial execution."
    if "FINANCE" in review_type:
        return "Validate cost assumptions before approving the scenario."
    return "Review final recommendation before action."


def _suggested_next_step(row):
    action = _text(row.get("proposed_operational_action"))
    readiness = _text(row.get("action_readiness"))
    if readiness == "READY_TO_ACT":
        return f"Execute {action} with {row.get('execution_owner')}."
    if readiness == "REVIEW_REQUIRED_BEFORE_ACTION":
        return f"Complete {row.get('blocking_review_action')} with {row.get('review_owner')}, then execute {action} with {row.get('execution_owner')}."
    if readiness == "ADVISORY_REVIEW_RECOMMENDED":
        return f"Proceed or monitor {action}; advisory review by {row.get('review_owner')} is recommended."
    if readiness == "MONITOR_ONLY":
        return "Monitor next cycle; no immediate execution."
    if readiness == "NO_ACTION":
        return "No action required."
    if action in {"REDUCE_BUFFER", "TIGHTEN_ORDER_CAP"}:
        return "Reduce future orders and monitor excess inventory."
    if action == "LIQUIDATE_DEAD_STOCK":
        return "Liquidate dead stock and tighten future ordering."
    if action in {"MONITOR_ONLY", "NO_ACTION"}:
        return "Monitor current policy; no immediate change."
    return f"Proceed with {action.lower().replace('_', ' ')} as recommendation-only action."


def _dashboard_badge(row):
    proposed = _text(row.get("proposed_operational_action")).upper()
    if _bool(row.get("final_mandatory_review_required")) and _text(row.get("blocking_review_action")).upper() != "NO_BLOCKING_REVIEW":
        return "REVIEW_GATE"
    if proposed == "SPLIT_DELIVERY":
        return "SPLIT_DELIVERY"
    if proposed == "LIQUIDATE_DEAD_STOCK":
        return "LIQUIDATE"
    if proposed == "USE_FAST_RELIABLE_SUPPLIER":
        return "SUPPLIER"
    if proposed in {"TIGHTEN_ORDER_CAP", "REDUCE_BUFFER"}:
        return "REDUCE_EXCESS"
    if proposed == "INCREASE_BUFFER":
        return "BUFFER"
    status = _text(row.get("main_inventory_status")).upper()
    if status in {"STOCKOUT", "ZERO_STOCK"}:
        return "STOCKOUT"
    if "EXPIRY_RISK" in _text(row.get("final_risk_types")).upper():
        return "EXPIRY"
    if status == "OVERSTOCK":
        return "OVERSTOCK"
    if _bool(row.get("final_mandatory_review_required")):
        return "REVIEW"
    if _num(row.get("operational_cost_saving_vs_baseline")) > 0:
        return "SAVING"
    if _text(row.get("final_manager_status")) == "NO_ACTION_REQUIRED":
        return "NO_ACTION"
    return "MONITOR"


def _dashboard_color(row):
    priority = _text(row.get("final_decision_priority")).upper()
    if priority == "URGENT":
        return "RED"
    if priority == "HIGH" or _bool(row.get("final_mandatory_review_required")):
        return "ORANGE"
    if priority == "MEDIUM" or _bool(row.get("final_advisory_review_required")):
        return "YELLOW"
    if _num(row.get("operational_cost_saving_vs_baseline")) > 0:
        return "BLUE"
    if priority == "NO_ACTION":
        return "GREEN"
    return "GRAY"


def _review_owner(review_type):
    return {
        "SUPPLIER_REVIEW": "PROCUREMENT_TEAM",
        "PROCUREMENT_REVIEW": "PROCUREMENT_TEAM",
        "WAREHOUSE_REVIEW": "WAREHOUSE_TEAM",
        "EXPIRY_REVIEW": "WAREHOUSE_TEAM",
        "POLICY_REVIEW": "INVENTORY_PLANNER",
        "PHASE4_REVIEW": "PRODUCTION_PLANNER_PHASE4",
        "FINANCE_COST_REVIEW": "FINANCE_MANAGER",
        "MANDATORY_MULTI_DEPARTMENT_REVIEW": "MULTI_DEPARTMENT_REVIEW",
        "NO_REVIEW_REQUIRED": "NO_REVIEW_REQUIRED",
    }.get(review_type, "INVENTORY_PLANNER")


def _proposed_operational_action(row):
    selected_name = _text(row.get("selected_scenario_name")).upper()
    buffer_strategy = _text(row.get("selected_buffer_strategy")).upper()
    supplier_strategy = _text(row.get("selected_supplier_strategy")).upper()
    delivery_strategy = _text(row.get("selected_delivery_strategy")).upper()
    order_cap_strategy = _text(row.get("selected_order_cap_strategy")).upper()
    expiry_strategy = _text(row.get("selected_expiry_strategy")).upper()
    primary_action = _text(row.get("primary_action")).upper()
    if expiry_strategy == "LIQUIDATE_DEAD_STOCK":
        action = "LIQUIDATE_DEAD_STOCK"
        reason = "Selected scenario proposes dead-stock liquidation."
    elif expiry_strategy == "QUARANTINE_OR_SCRAP_EXPIRED":
        action = "QUARANTINE_OR_SCRAP_EXPIRED"
        reason = "Selected scenario proposes expired-stock quarantine or scrap."
    elif expiry_strategy == "MARKDOWN_NEAR_EXPIRY":
        action = "MARKDOWN_NEAR_EXPIRY"
        reason = "Selected scenario proposes markdown for near-expiry stock."
    elif expiry_strategy == "RETURN_TO_SUPPLIER_IF_ALLOWED":
        action = "RETURN_TO_SUPPLIER_REVIEW"
        reason = "Selected scenario proposes supplier return review."
    elif delivery_strategy == "SPLIT_DELIVERY":
        action = "SPLIT_DELIVERY"
        reason = "Selected scenario proposes split delivery to reduce receiving pressure."
    elif supplier_strategy == "FAST_RELIABLE_SUPPLIER":
        action = "USE_FAST_RELIABLE_SUPPLIER"
        reason = "Selected scenario proposes faster reliable supply."
    elif buffer_strategy == "INCREASE_BUFFER":
        action = "INCREASE_BUFFER"
        reason = "Selected scenario proposes increasing buffer."
    elif buffer_strategy == "DECREASE_BUFFER":
        action = "REDUCE_BUFFER"
        reason = "Selected scenario proposes reducing buffer."
    elif order_cap_strategy in {"TIGHTEN_ORDER_CAP", "CAP_BY_EXPIRY_OR_MOVEMENT"}:
        action = "TIGHTEN_ORDER_CAP"
        reason = "Selected scenario proposes tightening order cap."
    elif order_cap_strategy == "LOOSEN_ORDER_CAP":
        action = "LOOSEN_ORDER_CAP"
        reason = "Selected scenario proposes loosening order cap."
    elif primary_action in {"EXPEDITE_ORDER", "ORDER_RECOMMENDED_QUANTITY"}:
        action = "ORDER_RECOMMENDED_QUANTITY"
        reason = "Inventory status recommends replenishment."
    elif primary_action == "WAIT_FOR_TRIGGER":
        action = "WAIT_FOR_TRIGGER"
        reason = "Event/replacement trigger is not active."
    elif selected_name and selected_name != "CURRENT_POLICY":
        action = "USE_SELECTED_OPTIMIZED_SCENARIO"
        reason = "Selected optimized scenario is the proposed operational path."
    elif _text(row.get("final_decision_priority")).upper() == "NO_ACTION":
        action = "NO_ACTION"
        reason = "No action is required."
    else:
        action = "MONITOR_ONLY"
        reason = "Monitor current policy and revisit next cycle."
    return action, _determine_execution_owner(action, _text(row.get("final_review_type")).upper(), _text(row.get("mandatory_review_gates")).upper(), _text(row.get("advisory_review_gates")).upper()), reason


def _blocking_review_action(row):
    gates = _text(row.get("mandatory_review_gates")).upper()
    if not _bool(row.get("final_mandatory_review_required")):
        return "NO_BLOCKING_REVIEW"
    if "PHASE4_GATE" in gates:
        return "REVIEW_PHASE4_PRODUCTION_LOGIC"
    if "SUPPLIER_CHANGE_GATE" in gates:
        return "REVIEW_SUPPLIER_BEFORE_ORDER"
    if "RECEIVING_CAPACITY_GATE" in gates:
        return "REVIEW_WAREHOUSE_CAPACITY"
    if "EXPIRY_DISPOSITION_GATE" in gates:
        return "REVIEW_EXPIRY_DISPOSITION"
    if "POLICY_PARAMETER_GATE" in gates or "SELECTED_SCENARIO_REVIEW_GATE" in gates or "HARD_BLOCKER_GATE" in gates:
        return "REVIEW_POLICY_PARAMETERS"
    return "NO_BLOCKING_REVIEW"


def _determine_execution_owner(action, review_type="", mandatory_gates="", advisory_gates=""):
    if action == "REVIEW_PHASE4_PRODUCTION_LOGIC":
        return "PRODUCTION_PLANNER_PHASE4"
    if action in {"REVIEW_SUPPLIER_BEFORE_ORDER", "USE_FAST_RELIABLE_SUPPLIER", "ORDER_RECOMMENDED_QUANTITY", "RETURN_TO_SUPPLIER_REVIEW"}:
        return "PROCUREMENT_TEAM"
    if action == "SPLIT_DELIVERY":
        return "PROCUREMENT_TEAM; WAREHOUSE_TEAM"
    if action in {"INCREASE_BUFFER", "REDUCE_BUFFER", "TIGHTEN_ORDER_CAP", "LOOSEN_ORDER_CAP", "USE_SELECTED_OPTIMIZED_SCENARIO", "MONITOR_ONLY", "WAIT_FOR_TRIGGER"}:
        return "INVENTORY_PLANNER"
    if action in {"LIQUIDATE_DEAD_STOCK", "MARKDOWN_NEAR_EXPIRY"}:
        return "OPERATIONS_MANAGER"
    if action in {"QUARANTINE_OR_SCRAP_EXPIRED", "REVIEW_WAREHOUSE_CAPACITY", "REVIEW_WAREHOUSE_SLOT"}:
        return "WAREHOUSE_TEAM"
    if action == "FINANCE_COST_REVIEW":
        return "FINANCE_MANAGER"
    if action == "MANDATORY_MULTI_DEPARTMENT_REVIEW":
        return "MULTI_DEPARTMENT_REVIEW"
    if action == "NO_ACTION":
        return "NO_OWNER_REQUIRED"
    return _review_owner(review_type) if review_type else "INVENTORY_PLANNER"


def _owner_assignment_reason(proposed_action, final_action, review_type, execution_owner, review_owner):
    if proposed_action == "SPLIT_DELIVERY":
        return "Split delivery requires procurement scheduling and warehouse receiving-capacity confirmation."
    if final_action.startswith("REVIEW_") and final_action != proposed_action:
        return f"{review_owner} owns the blocking review; {execution_owner} owns execution after approval."
    return f"{execution_owner} owns the proposed operational action."


def _action_readiness(action, priority, mandatory_review, advisory_review):
    if mandatory_review:
        return "REVIEW_REQUIRED_BEFORE_ACTION"
    if action in {"NO_ACTION", ""}:
        return "NO_ACTION"
    if action in {"MONITOR_ONLY", "WAIT_FOR_TRIGGER"}:
        return "ADVISORY_REVIEW_RECOMMENDED" if advisory_review else "MONITOR_ONLY"
    if priority in {"URGENT", "HIGH"}:
        return "READY_TO_ACT"
    if advisory_review:
        return "ADVISORY_REVIEW_RECOMMENDED"
    return "MONITOR_ONLY"


def _suggested_advisory_step(row):
    primary = _text(row.get("primary_review_type")).upper()
    if primary == "SUPPLIER_REVIEW":
        return "Review supplier signal during the next procurement cycle; action is not blocked."
    if primary == "WAREHOUSE_REVIEW":
        return "Review warehouse signal during slotting/capacity planning; action is not blocked."
    if primary == "FINANCE_COST_REVIEW":
        return "Review cost assumptions during management review; action is not blocked."
    if primary == "PHASE4_REVIEW":
        return "Keep Phase 4 dependency visible for production planning."
    return "Track advisory signal during the next planning review."


def _summary_row(section, metric, value, unit, note):
    return {
        "summary_section": section,
        "metric_name": metric,
        "metric_value": round(value, 4) if isinstance(value, float) else value,
        "metric_unit": unit,
        "interpretation": note,
        "manager_note": note,
    }


def _risk_source(risk):
    if risk in {"STOCKOUT_RISK", "OVERSTOCK_RISK", "EXPIRY_RISK", "DEAD_STOCK_RISK"}:
        return "INVENTORY_STATUS"
    if risk == "SUPPLIER_RISK":
        return "SUPPLIER_CONTEXT"
    if risk in {"WAREHOUSE_CAPACITY_RISK", "RECEIVING_STAGING_RISK", "TRAVEL_OR_SLOT_RISK"}:
        return "WAREHOUSE_SLOTTING"
    if risk == "PHASE4_PRODUCTION_RISK":
        return "PHASE4_FLAG"
    if risk == "COST_RISK":
        return "COST_ENGINE"
    return "RE_EVALUATION_ENGINE"


def _risk_description(risk):
    return {
        "STOCKOUT_RISK": "Shortage or replenishment risk.",
        "OVERSTOCK_RISK": "Excess inventory risk.",
        "EXPIRY_RISK": "Expiry, near-expiry, or spoilage risk.",
        "DEAD_STOCK_RISK": "Dead-stock or non-moving inventory risk.",
        "SUPPLIER_RISK": "Supplier reliability or supplier review risk.",
        "WAREHOUSE_CAPACITY_RISK": "Warehouse capacity risk.",
        "RECEIVING_STAGING_RISK": "Receiving/staging pressure risk.",
        "TRAVEL_OR_SLOT_RISK": "Travel, slotting, or ergonomic risk.",
        "POLICY_RISK": "Policy or parameter review risk.",
        "PHASE4_PRODUCTION_RISK": "Production/BOM/MRP dependency risk.",
        "COST_RISK": "High or uncertain cost exposure.",
        "DATA_QUALITY_RISK": "Fallback or incomplete data risk.",
    }.get(risk, "Inventory control risk.")


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for column in columns:
        if column not in df.columns:
            df[column] = pd.NA
    return df


def _reason(parts):
    text = " ".join([_text(part) for part in parts if _text(part)])
    limit = INVENTORY_CONSOLIDATION_CONFIG.get("max_reason_length", 500)
    return text[:limit]


def _dedupe(values):
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


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


def _sum(df, column):
    if df.empty or column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())


def _mean(df, column):
    if df.empty or column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).mean())


def _count(df, column, value):
    if df.empty or column not in df.columns:
        return 0
    return int((df[column].fillna("").astype(str).str.upper() == str(value).upper()).sum())


def _true_count(df, column):
    if df.empty or column not in df.columns:
        return 0
    return int(df[column].map(_bool).sum())


def _contains_count(df, column, pattern):
    if df.empty or column not in df.columns:
        return 0
    return int(df[column].fillna("").astype(str).str.upper().str.contains(str(pattern).upper(), regex=False).sum())


def _contains_any_count(df, column, patterns):
    if df.empty or column not in df.columns:
        return 0
    values = df[column].fillna("").astype(str).str.upper()
    return int(values.map(lambda value: any(pattern.upper() in value for pattern in patterns)).sum())


def _numeric_positive_count(df, column):
    if df.empty or column not in df.columns:
        return 0
    return int((pd.to_numeric(df[column], errors="coerce").fillna(0) > 0).sum())


def _blank_count(df, column):
    if df.empty or column not in df.columns:
        return 0
    return int(df[column].fillna("").astype(str).str.strip().eq("").sum())


def _rate(count, total):
    return round((count / total) * 100, 2) if total else 0.0


MASTER_COLUMNS = [
    "sku_id", "product_name", "category", "current_inventory", "available_inventory", "inventory_position",
    "main_inventory_status", "secondary_status_flags", "primary_action", "action_priority", "abc_class", "xyz_class",
    "fsn_class", "movement_class", "vitality_class", "perishability_class", "seasonality_class",
    "inventory_priority_class", "inventory_model_type", "review_policy", "service_level_target", "safety_stock",
    "reorder_point", "eoq", "recommended_order_quantity", "selected_scenario_id", "selected_scenario_name",
    "selected_buffer_strategy", "selected_supplier_strategy", "selected_delivery_strategy", "selected_order_cap_strategy",
    "selected_expiry_strategy", "selected_warehouse_strategy", "selected_service_level", "selected_safety_stock",
    "selected_reorder_point", "selected_order_quantity", "baseline_operational_cost", "selected_operational_cost",
    "operational_cost_saving_vs_baseline", "baseline_total_penalty_adjusted_cost",
    "selected_total_penalty_adjusted_cost", "penalty_adjusted_saving_vs_baseline", "saving_interpretation_type",
    "saving_interpretation_reason", "penalty_driven_saving_flag", "selected_feasibility_status",
    "selected_feasibility_severity", "selected_requires_human_review", "selected_major_risk_count",
    "selected_review_required_count", "selected_soft_warning_count", "final_risk_level", "final_risk_types",
    "final_risk_reason", "final_review_required", "final_mandatory_review_required",
    "final_advisory_review_required", "final_info_warning_only", "final_review_severity",
    "final_review_type", "primary_review_type", "secondary_review_types", "mandatory_review_gates",
    "advisory_review_gates", "info_review_gates", "review_gate_count", "mandatory_review_gate_count",
    "advisory_review_gate_count", "info_review_gate_count", "final_review_reason", "final_review_owner",
    "final_decision_priority", "final_priority_score", "final_priority_reason", "final_recommended_action",
    "final_action_reason", "final_action_owner", "final_manager_status", "action_blocked_by_mandatory_review",
    "advisory_review_exists", "action_readiness", "blocking_review_action", "proposed_operational_action",
    "proposed_operational_owner", "execution_owner", "review_owner", "owner_assignment_reason",
    "action_visibility_note", "auto_apply_allowed",
    "source_inventory_status", "source_re_evaluation_direction", "source_optimization_selection_status",
    "source_selected_scenario_status", "source_main_cost_driver", "source_warehouse_review",
    "source_supplier_review", "source_policy_review",
]

REVIEW_QUEUE_COLUMNS = [
    "review_rank", "sku_id", "product_name", "category", "final_decision_priority", "final_risk_level",
    "final_review_type", "final_review_severity", "primary_review_type", "mandatory_review_gates",
    "advisory_review_gates", "review_gate_count", "mandatory_review_gate_count",
    "final_review_owner", "final_review_reason", "final_recommended_action",
    "final_action_reason", "blocking_review_action", "proposed_operational_action",
    "proposed_operational_owner", "execution_owner", "review_owner", "owner_assignment_reason",
    "action_visibility_note", "selected_scenario_name", "selected_requires_human_review",
    "selected_feasibility_status", "selected_feasibility_severity", "selected_major_risk_count",
    "selected_review_required_count", "selected_soft_warning_count", "operational_cost_saving_vs_baseline",
    "penalty_adjusted_saving_vs_baseline", "saving_interpretation_type", "next_review_step",
]

ADVISORY_QUEUE_COLUMNS = [
    "advisory_rank", "sku_id", "product_name", "category", "final_decision_priority", "final_risk_level",
    "primary_review_type", "secondary_review_types", "advisory_review_gates", "final_recommended_action",
    "final_action_reason", "proposed_operational_action", "proposed_operational_owner", "execution_owner",
    "review_owner", "owner_assignment_reason", "action_visibility_note", "selected_scenario_name", "operational_cost_saving_vs_baseline",
    "penalty_adjusted_saving_vs_baseline", "suggested_advisory_step",
]

ACTION_PLAN_COLUMNS = [
    "action_rank", "sku_id", "product_name", "category", "final_decision_priority", "final_manager_status",
    "final_recommended_action", "final_action_owner", "final_action_reason", "final_review_required",
    "final_review_type", "action_blocked_by_mandatory_review", "advisory_review_exists", "action_readiness",
    "blocking_review_action", "proposed_operational_action", "proposed_operational_owner",
    "execution_owner", "review_owner", "owner_assignment_reason", "action_visibility_note",
    "selected_scenario_name", "selected_buffer_strategy", "selected_supplier_strategy",
    "selected_delivery_strategy", "selected_order_cap_strategy", "selected_expiry_strategy",
    "selected_warehouse_strategy", "selected_order_quantity", "selected_service_level", "selected_safety_stock",
    "selected_reorder_point", "operational_cost_saving_vs_baseline", "penalty_adjusted_saving_vs_baseline",
    "final_risk_level", "final_risk_types", "suggested_next_step",
]

RISK_REGISTER_COLUMNS = [
    "risk_id", "sku_id", "product_name", "category", "risk_type", "risk_level", "risk_source",
    "risk_description", "risk_driver", "related_status", "related_cost_driver", "related_selected_scenario",
    "mitigation_action", "risk_owner", "review_required", "review_type", "risk_priority",
    "review_severity", "mandatory_review_gate", "advisory_review_gate", "action_readiness",
]

DASHBOARD_COLUMNS = [
    "sku_id", "product_name", "category", "current_inventory", "main_inventory_status",
    "final_decision_priority", "final_manager_status", "final_recommended_action", "final_action_owner",
    "final_review_required", "final_mandatory_review_required", "final_advisory_review_required",
    "final_review_severity", "primary_review_type", "action_readiness", "mandatory_review_gate_count",
    "advisory_review_gate_count", "final_review_type", "final_risk_level", "final_risk_types",
    "blocking_review_action", "proposed_operational_action", "execution_owner", "review_owner",
    "action_visibility_note",
    "selected_scenario_name", "selected_buffer_strategy", "selected_supplier_strategy",
    "selected_delivery_strategy", "selected_expiry_strategy", "selected_warehouse_strategy",
    "operational_cost_saving_vs_baseline", "penalty_adjusted_saving_vs_baseline", "saving_interpretation_type",
    "final_action_reason", "suggested_dashboard_badge", "suggested_dashboard_color_group",
]
