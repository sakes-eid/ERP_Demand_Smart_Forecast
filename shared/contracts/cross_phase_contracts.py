"""Shared cross-phase bridge contracts for the planning project.

The phase codebases remain independently runnable. This module contains only
schema definitions and small helpers used by bridge writers, orchestrators, and
validators.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = PROJECT_ROOT / "shared"
SHARED_OUTPUT_DIR = SHARED_DIR / "outputs"
SHARED_VALIDATION_DIR = SHARED_DIR / "validation"

PHASE_1 = "PHASE_1"
PHASE_2 = "PHASE_2"
PHASE_3 = "PHASE_3"
INTEGRATED = "INTEGRATED"

PHASE2_SUPPLY_CONTEXT_SCHEMA_VERSION = "1.0"
PHASE3_REQUIREMENT_SCHEMA_VERSION = "1.0"
PHASE2_ALLOCATION_SCHEMA_VERSION = "1.0"
PHASE3_ALLOCATION_VALIDATION_SCHEMA_VERSION = "1.0"
INTEGRATED_DECISION_SCHEMA_VERSION = "1.0"

BRIDGE_METADATA_COLUMNS = [
    "schema_version",
    "run_id",
    "planning_iteration",
    "generated_at",
    "source_phase",
    "target_phase",
    "data_as_of_date",
    "sku_id",
]

PHASE2_SUPPLY_CAPABILITY_COLUMNS = [
    *BRIDGE_METADATA_COLUMNS,
    "supplier_id",
    "supplier_name",
    "supplier_status",
    "base_supplier_feasible_flag",
    "supplier_active_flag",
    "supplier_history_status",
    "supplier_evidence_status",
    "supplier_requires_review",
    "supplier_watchlist_flag",
    "supplier_risk_score",
    "supplier_risk_class",
    "supplier_reliability_score",
    "expected_lead_time_days",
    "lead_time_std_days",
    "minimum_lead_time_days",
    "maximum_lead_time_days",
    "unit_cost",
    "landed_cost_per_unit",
    "quality_adjusted_unit_cost",
    "moq",
    "order_multiple",
    "batch_size",
    "minimum_order_value",
    "fixed_order_cost",
    "delivery_cost",
    "yield_rate",
    "defect_rate",
    "expected_quality_loss_rate",
    "supplier_capacity_period_unit",
    "supplier_capacity_period_days",
    "supplier_capacity_per_day",
    "supplier_capacity_7d",
    "supplier_capacity_30d",
    "supplier_per_order_capacity_units",
    "order_acceptance_probability",
    "expedite_available",
    "expedite_eligible",
    "expedite_lead_time_days",
    "expedite_capacity_limit",
    "expedite_reliability",
    "split_delivery_available",
    "split_delivery_eligible",
    "minimum_split_quantity",
    "maximum_split_shipments",
    "first_shipment_lead_time_days",
    "remaining_shipment_lead_time_days",
    "accepts_returns",
    "return_eligible",
    "near_expiry_return_possible",
    "expired_return_possible",
    "expected_return_recovery_rate",
    "open_po_confirmed_units_7d",
    "open_po_confirmed_units_30d",
    "open_po_confirmed_units_60d",
    "open_po_confirmed_units_90d",
    "uncertain_inbound_units",
    "next_confirmed_receipt_date",
    "inbound_data_quality_flag",
    "inbound_warning_codes",
]

PHASE2_INBOUND_SUMMARY_COLUMNS = [
    *BRIDGE_METADATA_COLUMNS,
    "confirmed_inbound_units_7d",
    "confirmed_inbound_units_30d",
    "confirmed_inbound_units_60d",
    "confirmed_inbound_units_90d",
    "confirmed_inbound_before_need_date_units",
    "uncertain_inbound_units",
    "next_confirmed_receipt_date",
    "inbound_confidence",
    "inbound_warning_codes",
]

PHASE3_REQUIREMENT_COLUMNS = [
    *BRIDGE_METADATA_COLUMNS,
    "gross_forecast_demand_7d",
    "gross_forecast_demand_30d",
    "gross_forecast_demand_60d",
    "gross_forecast_demand_90d",
    "average_daily_forecast_demand",
    "forecast_uncertainty_level",
    "underforecast_risk_flag",
    "stockout_censored_demand_flag",
    "demand_urgency_score",
    "current_inventory_units",
    "reserved_inventory_units",
    "available_inventory_units",
    "usable_on_hand_inventory_units",
    "available_to_promise_units",
    "expired_inventory_units",
    "near_expiry_inventory_units",
    "quarantined_inventory_units",
    "unusable_inventory_units",
    "batch_inventory_reconciliation_difference",
    "batch_inventory_reconciliation_flag",
    "inventory_source_used",
    "inventory_model_type",
    "review_policy",
    "review_period_days",
    "service_level_target",
    "safety_stock_units",
    "reorder_point_units",
    "min_stock_level_units",
    "max_stock_level_units",
    "base_stock_level_units",
    "order_up_to_level_units",
    "policy_order_quantity_units",
    "confirmed_inbound_units_7d",
    "confirmed_inbound_units_30d",
    "confirmed_inbound_before_need_date_units",
    "uncertain_inbound_units",
    "active_backorder_units",
    "reserved_or_committed_demand_units",
    "current_inventory_position_units",
    "pre_clipped_inventory_position_units",
    "inventory_position_clipped_flag",
    "integrated_inventory_position_units",
    "inventory_position_method",
    "backorder_in_inventory_position_flag",
    "commitment_definition",
    "double_count_prevention_flag",
    "replenishment_triggered_flag",
    "gross_replenishment_requirement_units",
    "net_replenishment_requirement_units",
    "immediate_shortage_units",
    "remaining_horizon_shortage_units",
    "minimum_required_order_units",
    "order_quantity_before_supplier_constraints",
    "maximum_safe_order_units",
    "expiry_constrained_max_order_units",
    "movement_constrained_max_order_units",
    "existing_inventory_constrained_max_order_units",
    "warehouse_constrained_max_order_units",
    "final_inventory_constraint_cap_units",
    "main_inventory_status",
    "primary_action",
    "action_priority",
    "inventory_priority_class",
    "vitality_class",
    "perishability_class",
    "replenishment_urgency",
    "supplier_capability_requirement",
    "preferred_delivery_strategy",
    "split_sourcing_allowed",
    "expedite_allowed",
    "return_to_supplier_review_required",
    "requirement_source",
    "requirement_confidence",
    "requirement_warning_codes",
    "inventory_context_complete_flag",
]

PHASE2_ALLOCATION_COLUMNS = [
    *BRIDGE_METADATA_COLUMNS,
    "allocation_id",
    "supplier_id",
    "supplier_role",
    "requested_usable_quantity_units",
    "allocated_usable_quantity_units",
    "unallocated_requirement_units",
    "yield_adjusted_purchase_quantity",
    "moq_adjusted_purchase_quantity",
    "batch_rounded_purchase_quantity",
    "final_supplier_purchase_quantity",
    "normal_delivery_quantity",
    "expedite_quantity",
    "split_delivery_quantity",
    "first_shipment_quantity",
    "remaining_shipment_quantity",
    "expected_first_arrival_date",
    "expected_final_arrival_date",
    "supplier_per_order_capacity_units",
    "supplier_horizon_capacity_units",
    "capacity_used_units",
    "capacity_remaining_units",
    "per_order_capacity_feasible_flag",
    "horizon_capacity_feasible_flag",
    "allocation_capacity_feasible_flag",
    "unit_cost",
    "landed_cost_per_unit",
    "quality_adjusted_unit_cost",
    "estimated_product_cost",
    "estimated_fixed_order_cost",
    "estimated_delivery_cost",
    "estimated_expedite_cost",
    "estimated_delay_cost",
    "estimated_quality_cost",
    "estimated_total_procurement_cost",
    "supplier_reliability_score",
    "supplier_risk_score",
    "supplier_risk_class",
    "return_eligible",
    "expedite_used_flag",
    "split_delivery_used_flag",
    "allocation_feasible_flag",
    "allocation_execution_allowed",
    "human_review_required",
    "allocation_warning_codes",
    "allocation_reason",
]

PHASE2_ALLOCATION_SUMMARY_COLUMNS = [
    *BRIDGE_METADATA_COLUMNS,
    "requested_requirement_units",
    "total_allocated_usable_quantity",
    "total_supplier_purchase_quantity",
    "allocation_coverage_rate",
    "primary_supplier_id",
    "backup_supplier_id",
    "supplier_count",
    "split_sourcing_used_flag",
    "expedite_used_flag",
    "earliest_arrival_date",
    "final_arrival_date",
    "total_procurement_cost",
    "total_risk_adjusted_procurement_cost",
    "allocation_feasible_flag",
    "unallocated_requirement_units",
    "human_review_required",
    "allocation_warning_codes",
]

PHASE3_ALLOCATION_VALIDATION_COLUMNS = [
    *BRIDGE_METADATA_COLUMNS,
    "requested_requirement_units",
    "allocated_usable_quantity_units",
    "accepted_allocated_quantity_units",
    "projected_usable_inventory_after_allocation",
    "projected_inventory_position_after_allocation",
    "projected_overstock_units",
    "projected_stockout_units",
    "warehouse_capacity_feasible_flag",
    "receiving_capacity_feasible_flag",
    "service_level_guardrail_feasible_flag",
    "inventory_policy_feasible_flag",
    "allocation_accepted_flag",
    "adjustment_required_flag",
    "requested_adjusted_quantity_units",
    "validation_severity",
    "validation_warning_codes",
    "validation_reason",
]

INTEGRATED_DECISION_COLUMNS = [
    "schema_version",
    "run_id",
    "sku_id",
    "final_iteration",
    "convergence_status",
    "forecast_demand_30d",
    "demand_urgency_score",
    "forecast_uncertainty_level",
    "usable_on_hand_inventory_units",
    "integrated_inventory_position_units",
    "safety_stock_units",
    "reorder_point_units",
    "main_inventory_status",
    "net_replenishment_requirement_units",
    "maximum_safe_order_units",
    "selected_supplier_ids",
    "supplier_allocation_plan",
    "total_allocated_usable_quantity",
    "total_supplier_purchase_quantity",
    "split_sourcing_used_flag",
    "expedite_used_flag",
    "earliest_arrival_date",
    "final_arrival_date",
    "total_procurement_cost",
    "projected_holding_cost",
    "projected_stockout_cost",
    "projected_expiry_cost",
    "projected_warehouse_cost",
    "projected_total_relevant_cost",
    "procurement_capacity_feasible_flag",
    "inventory_policy_feasible_flag",
    "warehouse_capacity_feasible_flag",
    "service_level_feasible_flag",
    "allocation_accepted_flag",
    "final_recommendation",
    "final_action_owner",
    "final_priority",
    "final_review_required",
    "final_review_reason",
    "auto_apply_allowed",
    "purchase_order_creation_allowed",
    "procurement_execution_ready_flag",
    "approval_status",
    "approval_owner",
]

SUPPORTED_SCHEMA_VERSIONS = {
    "phase2_supply_capability_context": PHASE2_SUPPLY_CONTEXT_SCHEMA_VERSION,
    "phase2_inbound_supply_summary": PHASE2_SUPPLY_CONTEXT_SCHEMA_VERSION,
    "phase3_procurement_requirement_context": PHASE3_REQUIREMENT_SCHEMA_VERSION,
    "phase2_procurement_allocation_context": PHASE2_ALLOCATION_SCHEMA_VERSION,
    "phase2_procurement_allocation_summary": PHASE2_ALLOCATION_SCHEMA_VERSION,
    "phase3_allocation_validation": PHASE3_ALLOCATION_VALIDATION_SCHEMA_VERSION,
    "integrated_replenishment_decisions": INTEGRATED_DECISION_SCHEMA_VERSION,
}

SUPPLIER_ROLES = ["PRIMARY", "BACKUP", "SPLIT_SOURCE", "EXPEDITE", "REVIEW_CANDIDATE"]
VALIDATION_SEVERITIES = ["ACCEPTED", "ACCEPTED_WITH_WARNING", "ADJUSTMENT_REQUIRED", "BLOCKED"]


def utc_timestamp() -> str:
    """Return an ISO timestamp for bridge metadata."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def make_run_id(prefix: str = "RUN") -> str:
    """Create a stable-looking local run identifier."""
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


def metadata_frame(
    df: pd.DataFrame,
    *,
    schema_version: str,
    run_id: str,
    planning_iteration: int,
    source_phase: str,
    target_phase: str,
    data_as_of_date: str,
) -> pd.DataFrame:
    """Add standard bridge metadata columns to a dataframe with sku_id."""
    out = df.copy()
    out["schema_version"] = schema_version
    out["run_id"] = run_id
    out["planning_iteration"] = planning_iteration
    out["generated_at"] = utc_timestamp()
    out["source_phase"] = source_phase
    out["target_phase"] = target_phase
    out["data_as_of_date"] = data_as_of_date
    for column in BRIDGE_METADATA_COLUMNS:
        if column not in out.columns:
            out[column] = "" if column != "sku_id" else ""
    return out


def ensure_columns(df: pd.DataFrame, columns: Iterable[str], defaults: dict | None = None) -> pd.DataFrame:
    """Return a dataframe containing all requested columns in order."""
    defaults = defaults or {}
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = defaults.get(column, "")
    return out[list(columns)]


def schema_status(df: pd.DataFrame, required_columns: Iterable[str]) -> dict:
    """Return compact schema validation metadata."""
    required = list(required_columns)
    present = list(df.columns)
    missing = [column for column in required if column not in df.columns]
    extra = [column for column in present if column not in required]
    return {
        "required_columns": required,
        "present_columns": present,
        "missing_columns": missing,
        "extra_columns": extra,
        "schema_status": "PASS" if not missing else "FAIL",
    }
