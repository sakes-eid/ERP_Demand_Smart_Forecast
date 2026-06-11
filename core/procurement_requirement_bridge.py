"""Authoritative Phase 3 replenishment requirement bridge."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.contracts.cross_phase_contracts import (  # noqa: E402
    PHASE3_ALLOCATION_VALIDATION_COLUMNS,
    PHASE3_ALLOCATION_VALIDATION_SCHEMA_VERSION,
    PHASE3_REQUIREMENT_COLUMNS,
    PHASE3_REQUIREMENT_SCHEMA_VERSION,
    PHASE_2,
    PHASE_3,
    SHARED_OUTPUT_DIR,
    ensure_columns,
    metadata_frame,
)


def build_procurement_requirement_bridge(
    *,
    inventory: pd.DataFrame,
    batches: pd.DataFrame,
    policy: pd.DataFrame,
    parameters: pd.DataFrame,
    status: pd.DataFrame,
    classification: pd.DataFrame,
    service_levels: pd.DataFrame,
    action_recommendations: pd.DataFrame,
    phase1_context: pd.DataFrame,
    inbound_summary: pd.DataFrame | None,
    run_id: str,
    planning_iteration: int = 0,
    data_as_of_date: str = "",
) -> pd.DataFrame:
    """Build exactly one Phase 3 replenishment requirement row per SKU."""
    rows = []
    inbound_summary = inbound_summary if inbound_summary is not None else pd.DataFrame()
    for _, inv in inventory.iterrows():
        sku_id = str(inv.get("sku_id", "")).strip()
        batch = batches[batches["sku_id"].astype(str).str.strip().eq(sku_id)] if "sku_id" in batches.columns else pd.DataFrame()
        pol = _first(policy, sku_id)
        param = _first(parameters, sku_id)
        stat = _first(status, sku_id)
        cls = _first(classification, sku_id)
        svc = _first(service_levels, sku_id)
        action = _first(action_recommendations, sku_id)
        demand = _first(phase1_context, sku_id)
        inbound = _first(inbound_summary, sku_id)

        stock = _stock_from_batches(inv, batch)
        current_inventory = _num(inv, "current_inventory")
        reserved = _num(inv, "reserved_inventory")
        available = _num(inv, "available_inventory")
        active_backorders = 0.0
        committed = reserved
        confirmed_before_need = _num(inbound, "confirmed_inbound_before_need_date_units")
        confirmed_7 = _num(inbound, "confirmed_inbound_units_7d")
        confirmed_30 = _num(inbound, "confirmed_inbound_units_30d")
        pre_clipped_position = stock["usable_on_hand_inventory_units"] + confirmed_before_need - committed - active_backorders
        integrated_position = max(pre_clipped_position, 0)

        requirement = _policy_requirement(pol, param, stat, integrated_position)
        caps = _inventory_caps(pol, param, stat, stock)
        valid_caps = [value for value in caps.values() if value > 0]
        final_cap = min(valid_caps) if valid_caps else requirement["order_quantity_before_supplier_constraints"]
        net_requirement = min(requirement["order_quantity_before_supplier_constraints"], final_cap)
        row = {
            "sku_id": sku_id,
            "gross_forecast_demand_7d": _num(demand, "forecast_demand_7d"),
            "gross_forecast_demand_30d": _num(demand, "forecast_demand_30d"),
            "gross_forecast_demand_60d": _num(demand, "forecast_demand_60d"),
            "gross_forecast_demand_90d": _num(demand, "forecast_demand_90d"),
            "average_daily_forecast_demand": _num(demand, "average_daily_forecast_demand_30d"),
            "forecast_uncertainty_level": demand.get("forecast_uncertainty_level", "UNKNOWN"),
            "underforecast_risk_flag": demand.get("underforecast_risk_flag", False),
            "stockout_censored_demand_flag": demand.get("stockout_censored_demand_flag", False),
            "demand_urgency_score": _num(demand, "demand_urgency_score"),
            "current_inventory_units": current_inventory,
            "reserved_inventory_units": reserved,
            "available_inventory_units": available,
            **stock,
            "available_to_promise_units": max(stock["usable_on_hand_inventory_units"] + confirmed_before_need - committed, 0),
            "inventory_model_type": pol.get("inventory_model_type", param.get("inventory_model_type", "UNKNOWN")),
            "review_policy": pol.get("review_policy", param.get("review_policy", "UNKNOWN")),
            "review_period_days": _num(param, "review_period_R"),
            "service_level_target": _num(svc, "service_level_target") or _num(pol, "service_level_target"),
            "safety_stock_units": _num(param, "safety_stock") or _num(pol, "safety_stock"),
            "reorder_point_units": _num(param, "reorder_point") or _num(pol, "reorder_point"),
            "min_stock_level_units": _num(param, "min_stock_level") or _num(pol, "min_stock_level"),
            "max_stock_level_units": _num(param, "max_stock_level") or _num(pol, "max_stock_level"),
            "base_stock_level_units": _num(param, "base_stock_level") or _num(pol, "base_stock_level"),
            "order_up_to_level_units": _num(param, "order_up_to_level_S") or _num(pol, "order_up_to_level_S"),
            "policy_order_quantity_units": _num(param, "recommended_order_quantity") or _num(pol, "recommended_order_quantity"),
            "confirmed_inbound_units_7d": confirmed_7,
            "confirmed_inbound_units_30d": confirmed_30,
            "confirmed_inbound_before_need_date_units": confirmed_before_need,
            "uncertain_inbound_units": _num(inbound, "uncertain_inbound_units"),
            "active_backorder_units": active_backorders,
            "reserved_or_committed_demand_units": committed,
            "current_inventory_position_units": _num(inv, "inventory_position"),
            "pre_clipped_inventory_position_units": round(pre_clipped_position, 2),
            "inventory_position_clipped_flag": pre_clipped_position < 0,
            "integrated_inventory_position_units": integrated_position,
            "inventory_position_method": "USABLE_ON_HAND_PLUS_CONFIRMED_INBOUND_MINUS_RESERVED",
            "backorder_in_inventory_position_flag": False,
            "commitment_definition": "RESERVED_INVENTORY_ONLY",
            "double_count_prevention_flag": True,
            **requirement,
            "net_replenishment_requirement_units": round(max(net_requirement, 0), 2),
            **caps,
            "final_inventory_constraint_cap_units": round(final_cap, 2),
            "main_inventory_status": stat.get("main_inventory_status", "UNKNOWN"),
            "primary_action": action.get("primary_action", stat.get("primary_action", "UNKNOWN")),
            "action_priority": stat.get("action_priority", action.get("action_priority", "LOW")),
            "inventory_priority_class": cls.get("inventory_priority_class", pol.get("inventory_priority_class", "UNKNOWN")),
            "vitality_class": cls.get("vitality_class", pol.get("vitality_class", "UNKNOWN")),
            "perishability_class": cls.get("perishability_class", pol.get("perishability_class", "UNKNOWN")),
            "replenishment_urgency": _urgency(stat, requirement["replenishment_triggered_flag"]),
            "supplier_capability_requirement": _supplier_requirement(stat, action),
            "preferred_delivery_strategy": "SPLIT_DELIVERY" if _num(demand, "demand_urgency_score") >= 70 else "STANDARD_DELIVERY",
            "split_sourcing_allowed": True,
            "expedite_allowed": _num(demand, "demand_urgency_score") >= 70,
            "return_to_supplier_review_required": bool(_num(stat, "near_expiry_units") or _num(stat, "expired_units")),
            "requirement_source": "PHASE3_POLICY_AND_USABLE_INVENTORY",
            "requirement_confidence": "HIGH" if stock["batch_inventory_reconciliation_flag"] in {"RECONCILED", "RECONCILED_NEGATIVE_INVENTORY_AS_SHORTAGE"} else "MEDIUM",
            "requirement_warning_codes": _requirement_warnings(stock, final_cap, requirement),
            "inventory_context_complete_flag": True,
        }
        rows.append(row)

    out = pd.DataFrame(rows)
    out = metadata_frame(
        out,
        schema_version=PHASE3_REQUIREMENT_SCHEMA_VERSION,
        run_id=run_id,
        planning_iteration=planning_iteration,
        source_phase=PHASE_3,
        target_phase=PHASE_2,
        data_as_of_date=data_as_of_date,
    )
    return ensure_columns(out, PHASE3_REQUIREMENT_COLUMNS)


def save_procurement_requirement_bridge(**kwargs) -> pd.DataFrame:
    """Build and save the Phase 3 requirement bridge."""
    SHARED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bridge = build_procurement_requirement_bridge(**kwargs)
    bridge.to_csv(SHARED_OUTPUT_DIR / "phase3_procurement_requirement_context.csv", index=False)
    return bridge


def build_phase3_allocation_validation(
    requirement_context: pd.DataFrame,
    allocation_summary: pd.DataFrame,
    *,
    run_id: str,
    planning_iteration: int = 0,
    data_as_of_date: str = "",
) -> pd.DataFrame:
    """Validate Phase 2 allocation against Phase 3 inventory caps."""
    rows = []
    allocation_summary = allocation_summary if allocation_summary is not None else pd.DataFrame()
    for _, req in requirement_context.iterrows():
        sku_id = str(req.get("sku_id", "")).strip()
        alloc = _first(allocation_summary, sku_id)
        requested = _num(req, "net_replenishment_requirement_units")
        allocated = _num(alloc, "total_allocated_usable_quantity")
        cap = _num(req, "final_inventory_constraint_cap_units")
        accepted = min(allocated, cap) if cap > 0 else allocated
        warehouse_ok = allocated <= cap + 0.01 if cap > 0 else True
        coverage_ok = allocated + 0.01 >= requested or requested == 0
        accepted_flag = warehouse_ok and coverage_ok
        severity = "ACCEPTED" if accepted_flag else ("ADJUSTMENT_REQUIRED" if allocated > cap and cap > 0 else "ACCEPTED_WITH_WARNING")
        rows.append(
            {
                "sku_id": sku_id,
                "requested_requirement_units": requested,
                "allocated_usable_quantity_units": allocated,
                "accepted_allocated_quantity_units": round(accepted, 2),
                "projected_usable_inventory_after_allocation": round(_num(req, "usable_on_hand_inventory_units") + accepted, 2),
                "projected_inventory_position_after_allocation": round(_num(req, "integrated_inventory_position_units") + accepted, 2),
                "projected_overstock_units": max(round((_num(req, "integrated_inventory_position_units") + accepted) - _num(req, "max_stock_level_units"), 2), 0),
                "projected_stockout_units": max(round(requested - accepted, 2), 0),
                "warehouse_capacity_feasible_flag": warehouse_ok,
                "receiving_capacity_feasible_flag": True,
                "service_level_guardrail_feasible_flag": True,
                "inventory_policy_feasible_flag": accepted <= cap + 0.01 if cap > 0 else True,
                "allocation_accepted_flag": accepted_flag,
                "adjustment_required_flag": not accepted_flag,
                "requested_adjusted_quantity_units": round(accepted, 2),
                "validation_severity": severity,
                "validation_warning_codes": "NONE" if accepted_flag else "ALLOCATION_REQUIRES_REVIEW",
                "validation_reason": "Allocation accepted." if accepted_flag else "Allocation coverage or cap requires review.",
            }
        )
    out = pd.DataFrame(rows)
    out = metadata_frame(
        out,
        schema_version=PHASE3_ALLOCATION_VALIDATION_SCHEMA_VERSION,
        run_id=run_id,
        planning_iteration=planning_iteration,
        source_phase=PHASE_3,
        target_phase=PHASE_2,
        data_as_of_date=data_as_of_date,
    )
    return ensure_columns(out, PHASE3_ALLOCATION_VALIDATION_COLUMNS)


def save_phase3_allocation_validation(requirement_context: pd.DataFrame, allocation_summary: pd.DataFrame, *, run_id: str, planning_iteration: int = 0, data_as_of_date: str = "") -> pd.DataFrame:
    SHARED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    validation = build_phase3_allocation_validation(
        requirement_context,
        allocation_summary,
        run_id=run_id,
        planning_iteration=planning_iteration,
        data_as_of_date=data_as_of_date,
    )
    validation.to_csv(SHARED_OUTPUT_DIR / "phase3_allocation_validation.csv", index=False)
    return validation


def _stock_from_batches(inv: pd.Series, batches: pd.DataFrame) -> dict:
    if batches.empty:
        usable = _num(inv, "available_inventory")
        return {
            "usable_on_hand_inventory_units": usable,
            "expired_inventory_units": 0.0,
            "near_expiry_inventory_units": 0.0,
            "quarantined_inventory_units": 0.0,
            "unusable_inventory_units": max(_num(inv, "current_inventory") - usable, 0),
            "batch_inventory_reconciliation_difference": 0.0,
            "batch_inventory_reconciliation_flag": "NO_BATCH_ROWS",
            "inventory_source_used": "INVENTORY_SUMMARY",
        }
    qty = pd.to_numeric(batches.get("quantity_available", 0), errors="coerce").fillna(0)
    expired = qty[_bool_series(batches.get("expired_flag", False))].sum()
    near = qty[_bool_series(batches.get("near_expiry_flag", False)) & ~_bool_series(batches.get("expired_flag", False))].sum()
    quarantine_mask = batches.get("batch_status", "").astype(str).str.upper().str.contains("QUARANTINE", regex=False)
    quarantined = qty[quarantine_mask].sum()
    usable_mask = (qty > 0) & ~_bool_series(batches.get("expired_flag", False)) & ~quarantine_mask
    usable = float(qty[usable_mask].sum())
    summary_current = _num(inv, "current_inventory")
    batch_total = float(pd.to_numeric(batches.get("quantity_on_hand", 0), errors="coerce").fillna(0).sum())
    physical_summary_current = max(summary_current, 0)
    diff = round(batch_total - physical_summary_current, 2)
    if summary_current < 0 and abs(diff) <= 1.0:
        reconciliation_flag = "RECONCILED_NEGATIVE_INVENTORY_AS_SHORTAGE"
    else:
        reconciliation_flag = "RECONCILED" if abs(diff) <= 1.0 else "REVIEW_REQUIRED"
    return {
        "usable_on_hand_inventory_units": round(max(usable, 0), 2),
        "expired_inventory_units": round(float(expired), 2),
        "near_expiry_inventory_units": round(float(near), 2),
        "quarantined_inventory_units": round(float(quarantined), 2),
        "unusable_inventory_units": round(max(float(expired + quarantined), 0), 2),
        "batch_inventory_reconciliation_difference": diff,
        "batch_inventory_reconciliation_flag": reconciliation_flag,
        "inventory_source_used": "BATCH_LAYER",
    }


def _policy_requirement(pol: pd.Series, param: pd.Series, stat: pd.Series, position: float) -> dict:
    model = str(pol.get("inventory_model_type", param.get("inventory_model_type", ""))).upper()
    reorder_point = _num(param, "reorder_point") or _num(pol, "reorder_point")
    immediate_shortage = _num(stat, "stockout_units")
    triggered = position <= reorder_point or immediate_shortage > 0
    if "BASE" in model:
        raw = max((_num(param, "base_stock_level") or _num(pol, "base_stock_level")) - position, 0)
    elif "PERIODIC" in model or "RS" in model:
        raw = max((_num(param, "order_up_to_level_S") or _num(pol, "order_up_to_level_S")) - position, 0)
    elif "EVENT" in model:
        raw = _num(param, "recommended_order_quantity") if triggered else 0
    else:
        raw = (_num(param, "order_quantity_Q") or _num(param, "eoq") or _num(param, "recommended_order_quantity") or _num(pol, "recommended_order_quantity")) if triggered else 0
    before_supplier = max(raw, immediate_shortage, 0)
    return {
        "replenishment_triggered_flag": triggered,
        "gross_replenishment_requirement_units": round(raw, 2),
        "immediate_shortage_units": round(immediate_shortage, 2),
        "remaining_horizon_shortage_units": round(max(raw - immediate_shortage, 0), 2),
        "minimum_required_order_units": round(before_supplier, 2),
        "order_quantity_before_supplier_constraints": round(before_supplier, 2),
    }


def _inventory_caps(pol: pd.Series, param: pd.Series, stat: pd.Series, stock: dict) -> dict:
    max_stock = _num(param, "max_stock_level") or _num(pol, "max_stock_level")
    available_room = max(max_stock - stock["usable_on_hand_inventory_units"], 0) if max_stock > 0 else 0
    existing_cap = available_room
    expiry_cap = existing_cap if str(pol.get("perishability_class", "")).upper() in {"PERISHABLE", "HIGH"} else 0
    movement_cap = existing_cap if str(pol.get("movement_class", "")).upper() in {"SLOW", "NON_MOVING"} else 0
    warehouse_cap = existing_cap
    return {
        "maximum_safe_order_units": round(existing_cap, 2),
        "expiry_constrained_max_order_units": round(expiry_cap, 2),
        "movement_constrained_max_order_units": round(movement_cap, 2),
        "existing_inventory_constrained_max_order_units": round(existing_cap, 2),
        "warehouse_constrained_max_order_units": round(warehouse_cap, 2),
    }


def _first(df: pd.DataFrame | None, sku_id: str) -> pd.Series:
    if df is None or df.empty or "sku_id" not in df.columns:
        return pd.Series(dtype=object)
    rows = df[df["sku_id"].astype(str).str.strip().eq(str(sku_id).strip())]
    return rows.iloc[0] if not rows.empty else pd.Series(dtype=object)


def _num(row: pd.Series, column: str) -> float:
    if row is None or column not in row:
        return 0.0
    return float(pd.to_numeric(pd.Series([row[column]]), errors="coerce").fillna(0).iloc[0])


def _bool_series(series) -> pd.Series:
    if isinstance(series, pd.Series):
        return series.fillna(False).astype(str).str.lower().isin({"true", "1", "yes", "y", "t"})
    return pd.Series([series]).astype(str).str.lower().isin({"true", "1", "yes", "y", "t"})


def _urgency(status: pd.Series, triggered: bool) -> str:
    priority = str(status.get("action_priority", "")).upper()
    if priority in {"URGENT", "HIGH"}:
        return priority
    return "MEDIUM" if triggered else "LOW"


def _supplier_requirement(status: pd.Series, action: pd.Series) -> str:
    text = f"{status.get('warning_codes', '')};{action.get('warning_codes', '')}".upper()
    if "SUPPLIER" in text:
        return "RELIABLE_SUPPLIER_REQUIRED"
    return "STANDARD_SUPPLIER_CAPABILITY"


def _requirement_warnings(stock: dict, final_cap: float, requirement: dict) -> str:
    warnings = []
    if stock["batch_inventory_reconciliation_flag"] not in {"RECONCILED", "RECONCILED_NEGATIVE_INVENTORY_AS_SHORTAGE"}:
        warnings.append("BATCH_INVENTORY_RECONCILIATION_REVIEW")
    if final_cap <= 0 and requirement["order_quantity_before_supplier_constraints"] > 0:
        warnings.append("MISSING_OR_ZERO_INVENTORY_CAP_REVIEW")
    return ";".join(warnings) if warnings else "NONE"
