"""Controlled cross-phase planning orchestrator.

The orchestrator runs phases as separate processes and coordinates them through
versioned bridge files under shared/outputs. It does not import Phase 2 or Phase
3 business logic directly.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from shared.contracts.cross_phase_contracts import (
    INTEGRATED_DECISION_COLUMNS,
    INTEGRATED_DECISION_SCHEMA_VERSION,
    SHARED_OUTPUT_DIR,
    ensure_columns,
    make_run_id,
)


PROJECT_ROOT = Path(__file__).resolve().parent
PHASE2_DIR = PROJECT_ROOT / "phase 2"
PHASE3_DIR = PROJECT_ROOT / "phase 3"

INTEGRATED_PLANNING_CONFIG = {
    "enabled": True,
    "max_iterations": 3,
    "quantity_tolerance_units": 1.0,
    "cost_change_tolerance_pct": 0.01,
    "require_supplier_allocation_stability": True,
    "require_no_hard_blockers": True,
    "require_warehouse_feasibility": True,
    "require_service_level_guardrails": True,
    "auto_apply_allowed": False,
}


def main() -> None:
    run_id = os.environ.get("INTEGRATED_RUN_ID") or make_run_id("INTEGRATED")
    planning_data_as_of_date = os.environ.get("PLANNING_DATA_AS_OF_DATE") or datetime.utcnow().date().isoformat()
    SHARED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Integrated run id: {run_id}")

    convergence_status = "NOT_EVALUATED"
    final_iteration = 0
    previous_signature = ""
    for iteration in range(INTEGRATED_PLANNING_CONFIG["max_iterations"]):
        env = os.environ.copy()
        env["INTEGRATED_RUN_ID"] = run_id
        env["PLANNING_ITERATION"] = str(iteration)
        env["PLANNING_DATA_AS_OF_DATE"] = planning_data_as_of_date

        _run_phase(PHASE2_DIR / "main.py", env, f"Phase 2 iteration {iteration}")
        _run_phase(PHASE3_DIR / "main.py", env, f"Phase 3 iteration {iteration}")
        _run_phase(PHASE2_DIR / "main.py", env, f"Phase 2 allocation iteration {iteration}")
        _run_phase(PHASE3_DIR / "main.py", env, f"Phase 3 validation iteration {iteration}")

        signature = _allocation_signature()
        final_iteration = iteration
        if signature and signature == previous_signature:
            convergence_status = _derive_convergence_status()
            break
        previous_signature = signature
    else:
        convergence_status = "NOT_CONVERGED"

    decisions = build_integrated_decisions(run_id, final_iteration, convergence_status)
    output_path = SHARED_OUTPUT_DIR / "integrated_replenishment_decisions.csv"
    decisions.to_csv(output_path, index=False)
    print(f"Integrated decisions: {output_path}")
    print(f"Convergence status: {convergence_status}")
    print(f"Final iteration: {final_iteration}")
    print(f"Decision rows: {len(decisions)}")


def build_integrated_decisions(run_id: str, final_iteration: int, convergence_status: str) -> pd.DataFrame:
    requirement = _read_shared("phase3_procurement_requirement_context.csv")
    allocation = _read_shared("phase2_procurement_allocation_summary.csv")
    validation = _read_shared("phase3_allocation_validation.csv")
    rows = []
    for _, req in requirement.iterrows():
        sku_id = str(req.get("sku_id", "")).strip()
        alloc = _first(allocation, sku_id)
        valid = _first(validation, sku_id)
        supplier_plan = _supplier_plan(sku_id)
        requested = _num(req, "net_replenishment_requirement_units")
        allocated = _num(alloc, "total_allocated_usable_quantity")
        unallocated = _num(alloc, "unallocated_requirement_units")
        allocation_accepted = _to_bool(valid.get("allocation_accepted_flag", False))
        adjustment_required = _to_bool(valid.get("adjustment_required_flag", False))
        allocation_feasible = _to_bool(alloc.get("allocation_feasible_flag", False))
        human_review = (
            requested > 0
            and (
            not allocation_accepted
            or adjustment_required
            or not allocation_feasible
            or convergence_status != "CONVERGED"
            or unallocated > 0.01
            )
        )
        total_cost = _num(alloc, "total_procurement_cost")
        if requested <= 0 and allocated <= 0:
            final_recommendation = "NO_PROCUREMENT_ACTION_REQUIRED"
            final_action_owner = "NO_OWNER_REQUIRED"
            final_review_required = False
            review_reason = "NO_REPLENISHMENT_REQUIREMENT"
        elif human_review:
            final_recommendation = "REVIEW_BEFORE_ACTION"
            final_action_owner = "MULTI_DEPARTMENT_REVIEW"
            final_review_required = True
            review_reason = _review_reason(convergence_status, alloc, valid)
        else:
            final_recommendation = "PROCUREMENT_ALLOCATION_READY"
            final_action_owner = "PROCUREMENT_TEAM"
            final_review_required = False
            review_reason = "NO_BLOCKING_REVIEW"
        rows.append(
            {
                "schema_version": INTEGRATED_DECISION_SCHEMA_VERSION,
                "run_id": run_id,
                "sku_id": sku_id,
                "final_iteration": final_iteration,
                "convergence_status": convergence_status,
                "forecast_demand_30d": _num(req, "gross_forecast_demand_30d"),
                "demand_urgency_score": _num(req, "demand_urgency_score"),
                "forecast_uncertainty_level": req.get("forecast_uncertainty_level", "UNKNOWN"),
                "usable_on_hand_inventory_units": _num(req, "usable_on_hand_inventory_units"),
                "integrated_inventory_position_units": _num(req, "integrated_inventory_position_units"),
                "safety_stock_units": _num(req, "safety_stock_units"),
                "reorder_point_units": _num(req, "reorder_point_units"),
                "main_inventory_status": req.get("main_inventory_status", "UNKNOWN"),
                "net_replenishment_requirement_units": _num(req, "net_replenishment_requirement_units"),
                "maximum_safe_order_units": _num(req, "maximum_safe_order_units"),
                "selected_supplier_ids": supplier_plan["supplier_ids"],
                "supplier_allocation_plan": supplier_plan["allocation_plan"],
                "total_allocated_usable_quantity": allocated,
                "total_supplier_purchase_quantity": _num(alloc, "total_supplier_purchase_quantity"),
                "split_sourcing_used_flag": _to_bool(alloc.get("split_sourcing_used_flag", False)),
                "expedite_used_flag": _to_bool(alloc.get("expedite_used_flag", False)),
                "earliest_arrival_date": alloc.get("earliest_arrival_date", ""),
                "final_arrival_date": alloc.get("final_arrival_date", ""),
                "total_procurement_cost": total_cost,
                "projected_holding_cost": 0.0,
                "projected_stockout_cost": max(_num(req, "net_replenishment_requirement_units") - _num(alloc, "total_allocated_usable_quantity"), 0) * 25,
                "projected_expiry_cost": 0.0,
                "projected_warehouse_cost": 0.0,
                "projected_total_relevant_cost": total_cost,
                "procurement_capacity_feasible_flag": allocation_feasible,
                "inventory_policy_feasible_flag": _to_bool(valid.get("inventory_policy_feasible_flag", False)),
                "warehouse_capacity_feasible_flag": _to_bool(valid.get("warehouse_capacity_feasible_flag", False)),
                "service_level_feasible_flag": _to_bool(valid.get("service_level_guardrail_feasible_flag", False)),
                "allocation_accepted_flag": allocation_accepted,
                "final_recommendation": final_recommendation,
                "final_action_owner": final_action_owner,
                "final_priority": _priority(req, human_review),
                "final_review_required": final_review_required,
                "final_review_reason": review_reason,
                "auto_apply_allowed": False,
                "purchase_order_creation_allowed": False,
                "procurement_execution_ready_flag": False,
                "approval_status": "NOT_REQUESTED",
                "approval_owner": "HUMAN_MANAGER",
            }
        )
    return ensure_columns(pd.DataFrame(rows), INTEGRATED_DECISION_COLUMNS)


def _run_phase(script: Path, env: dict, label: str) -> None:
    print(f"Running {label}: {script}")
    subprocess.run([sys.executable, str(script)], cwd=str(script.parent), env=env, check=True)


def _read_shared(filename: str) -> pd.DataFrame:
    path = SHARED_OUTPUT_DIR / filename
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _allocation_signature() -> str:
    summary = _read_shared("phase2_procurement_allocation_summary.csv")
    if summary.empty:
        return ""
    columns = [column for column in ["sku_id", "primary_supplier_id", "backup_supplier_id", "total_allocated_usable_quantity"] if column in summary.columns]
    return "|".join(summary[columns].sort_values("sku_id").astype(str).agg(":".join, axis=1))


def _derive_convergence_status() -> str:
    """Classify convergence separately from unresolved review work."""
    allocation = _read_shared("phase2_procurement_allocation_summary.csv")
    validation = _read_shared("phase3_allocation_validation.csv")
    if allocation.empty or validation.empty:
        return "NOT_CONVERGED"
    adjustment_count = _bool_series(validation.get("adjustment_required_flag", pd.Series(dtype=object))).sum()
    warehouse_blocked = (~_bool_series(validation.get("warehouse_capacity_feasible_flag", pd.Series(True, index=validation.index)))).sum()
    service_blocked = (~_bool_series(validation.get("service_level_guardrail_feasible_flag", pd.Series(True, index=validation.index)))).sum()
    inventory_blocked = (~_bool_series(validation.get("inventory_policy_feasible_flag", pd.Series(True, index=validation.index)))).sum()
    unallocated_total = pd.to_numeric(allocation.get("unallocated_requirement_units", 0), errors="coerce").fillna(0).sum()
    if warehouse_blocked or service_blocked or inventory_blocked:
        return "PARTIALLY_CONVERGED"
    if adjustment_count:
        return "CONVERGED_WITH_REVIEW"
    if unallocated_total > 0.01:
        return "CONVERGED_WITH_REVIEW"
    return "CONVERGED"


def _supplier_plan(sku_id: str) -> dict:
    allocation = _read_shared("phase2_procurement_allocation_context.csv")
    if allocation.empty:
        return {"supplier_ids": "", "allocation_plan": ""}
    rows = allocation[allocation["sku_id"].astype(str).str.strip().eq(sku_id)]
    supplier_ids = []
    plan = []
    for _, row in rows.iterrows():
        supplier_id = str(row.get("supplier_id", ""))
        if supplier_id and supplier_id not in {"NO_SUPPLIER_REQUIRED", "NO_FEASIBLE_SUPPLIER"}:
            supplier_ids.append(supplier_id)
            plan.append(f"{supplier_id}:{_num(row, 'allocated_usable_quantity_units'):.2f}")
    return {"supplier_ids": ";".join(sorted(set(supplier_ids))), "allocation_plan": ";".join(plan)}


def _first(df: pd.DataFrame, sku_id: str) -> pd.Series:
    if df.empty or "sku_id" not in df.columns:
        return pd.Series(dtype=object)
    rows = df[df["sku_id"].astype(str).str.strip().eq(str(sku_id).strip())]
    return rows.iloc[0] if not rows.empty else pd.Series(dtype=object)


def _num(row: pd.Series, column: str) -> float:
    if row is None or column not in row:
        return 0.0
    return float(pd.to_numeric(pd.Series([row[column]]), errors="coerce").fillna(0).iloc[0])


def _to_bool(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def _bool_series(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.lower().isin({"true", "1", "yes", "y", "t"})


def _priority(req: pd.Series, human_review: bool) -> str:
    if str(req.get("action_priority", "")).upper() == "URGENT":
        return "URGENT"
    if human_review:
        return "HIGH"
    return "MEDIUM" if _num(req, "net_replenishment_requirement_units") > 0 else "LOW"


def _review_reason(convergence_status: str, alloc: pd.Series, valid: pd.Series) -> str:
    reasons = []
    if convergence_status != "CONVERGED":
        reasons.append(convergence_status)
    if _num(alloc, "unallocated_requirement_units") > 0.01:
        reasons.append("UNALLOCATED_REQUIREMENT_REMAINS")
    if not _to_bool(valid.get("allocation_accepted_flag", False)):
        reasons.append("PHASE3_ALLOCATION_VALIDATION_NOT_ACCEPTED")
    return ";".join(reasons) if reasons else "NO_BLOCKING_REVIEW"


if __name__ == "__main__":
    main()
