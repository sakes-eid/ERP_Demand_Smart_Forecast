"""Validate maintenance master data and build advisory maintenance readiness contexts."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = PROJECT_ROOT / "shared"
DATA_DIR = SHARED_DIR / "data"
OUTPUT_DIR = SHARED_DIR / "outputs"
PHASE4_DIR = PROJECT_ROOT / "phase 4"
PHASE4_OUTPUT_DIR = PHASE4_DIR / "outputs"

MAINTENANCE_PLANS_FILE = DATA_DIR / "maintenance_plans.csv"
PLAN_SPARE_PARTS_FILE = DATA_DIR / "maintenance_plan_spare_parts.csv"
MACHINE_STATE_FILE = DATA_DIR / "machine_maintenance_state.csv"
MACHINES_FILE = PHASE4_DIR / "data" / "machines.csv"
SPARE_PARTS_FILE = DATA_DIR / "spare_parts_master.csv"
WORKFORCE_CONTEXT_FILE = PHASE4_OUTPUT_DIR / "phase4_workforce_resource_context.csv"
WORKFORCE_MACHINE_AUTH_FILE = OUTPUT_DIR / "workforce_machine_authorization_context.csv"
SPARE_PART_PHASE_CONTEXT_FILE = OUTPUT_DIR / "spare_part_phase_integration_context.csv"
SPARE_PART_REQUIREMENT_CONTEXT_FILE = PHASE4_OUTPUT_DIR / "phase4_spare_part_requirement_context.csv"
PHASE4_MPS_FILE = PHASE4_OUTPUT_DIR / "phase4_master_production_schedule.csv"

VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "maintenance_plan_validation.csv"
DUE_STATUS_CONTEXT_FILE = OUTPUT_DIR / "maintenance_due_status_context.csv"
SPARE_PART_CONTEXT_FILE = OUTPUT_DIR / "maintenance_spare_part_requirement_context.csv"
COST_DOWNTIME_CONTEXT_FILE = OUTPUT_DIR / "maintenance_cost_downtime_context.csv"
MANAGER_REVIEW_QUEUE_FILE = OUTPUT_DIR / "maintenance_manager_review_queue.csv"
PHASE4_MAINTENANCE_CONTEXT_FILE = PHASE4_OUTPUT_DIR / "phase4_maintenance_readiness_context.csv"

SOURCE_PHASE = "SHARED_STEP7C_MAINTENANCE_MASTER_DATA"
VALID_LEVELS = {"LIGHT", "MEDIUM", "HEAVY", "BREAKDOWN_REPAIR_PLACEHOLDER"}
VALID_CATEGORIES = {"AUTONOMOUS_MAINTENANCE", "PREVENTIVE_MAINTENANCE", "CALIBRATION", "INSPECTION", "OVERHAUL", "BREAKDOWN_REPAIR_PLACEHOLDER"}
VALID_TRIGGERS = {"OPERATIONS_BASED", "TIME_BASED", "OPERATIONS_OR_TIME_BASED", "CONDITION_BASED_PLACEHOLDER", "BREAKDOWN_PLACEHOLDER"}
VALID_RISK = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_CONDITION = {"GOOD", "MONITOR", "DEGRADED", "UNKNOWN"}
VALID_STATE_SOURCE = {"SYNTHETIC_PLANNING_STATE", "MANUFACTURER_ASSUMPTION", "MANUAL_ESTIMATE"}
RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def build_maintenance_master_data_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    checks: list[dict] = []
    frames = {
        "plans": _load_csv(MAINTENANCE_PLANS_FILE, "maintenance_plans", checks),
        "plan_spares": _load_csv(PLAN_SPARE_PARTS_FILE, "maintenance_plan_spare_parts", checks),
        "state": _load_csv(MACHINE_STATE_FILE, "machine_maintenance_state", checks),
        "machines": _load_csv(MACHINES_FILE, "phase4_machines", checks),
        "spares": _load_csv(SPARE_PARTS_FILE, "spare_parts_master", checks),
        "workforce": _load_csv(WORKFORCE_CONTEXT_FILE, "phase4_workforce_resource_context", checks),
        "workforce_auth": _load_csv(WORKFORCE_MACHINE_AUTH_FILE, "workforce_machine_authorization_context", checks),
        "spare_phase": _load_csv(SPARE_PART_PHASE_CONTEXT_FILE, "spare_part_phase_integration_context", checks),
        "spare_req": _load_csv(SPARE_PART_REQUIREMENT_CONTEXT_FILE, "phase4_spare_part_requirement_context", checks),
    }
    due = pd.DataFrame()
    spare_context = pd.DataFrame()
    cost_context = pd.DataFrame()
    review = pd.DataFrame()
    phase4_context = pd.DataFrame()
    if all(frame is not None for frame in frames.values()):
        _validate_master_data(frames, checks)
        due = _build_due_status_context(frames["plans"], frames["state"], frames["machines"])
        spare_context = _build_spare_part_context(frames["plans"], frames["plan_spares"], frames["spare_phase"], frames["spare_req"])
        cost_context = _build_cost_downtime_context(frames["plans"], frames["plan_spares"], frames["spares"])
        review = _build_manager_review_queue(due, spare_context, cost_context, frames["plans"], frames["workforce_auth"])
        phase4_context = _build_phase4_readiness_context(due, spare_context, cost_context, review)
        _validate_outputs(due, spare_context, cost_context, review, phase4_context, checks)
    _check_no_blocked_outputs(checks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PHASE4_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    due.to_csv(DUE_STATUS_CONTEXT_FILE, index=False)
    spare_context.to_csv(SPARE_PART_CONTEXT_FILE, index=False)
    cost_context.to_csv(COST_DOWNTIME_CONTEXT_FILE, index=False)
    review.to_csv(MANAGER_REVIEW_QUEUE_FILE, index=False)
    phase4_context.to_csv(PHASE4_MAINTENANCE_CONTEXT_FILE, index=False)
    return validation, due, spare_context, cost_context, review, phase4_context


def _validate_master_data(frames: dict[str, pd.DataFrame], checks: list[dict]) -> None:
    required = {
        "plans": {"maintenance_plan_id", "machine_id", "machine_type", "machine_name", "maintenance_level", "maintenance_category", "trigger_type", "operations_between_maintenance", "days_between_maintenance", "condition_trigger_placeholder", "estimated_maintenance_duration_hours", "planned_downtime_hours", "required_crew_type", "required_skill_id", "required_authorization_level", "required_worker_count", "can_be_performed_by_production_flag", "can_be_performed_by_maintenance_flag", "can_defer_flag", "max_defer_operations", "max_defer_days", "deferral_risk_level", "estimated_labor_hours", "estimated_external_service_cost", "active_flag", "advisory_only_flag", "notes"},
        "plan_spares": {"maintenance_plan_id", "spare_part_sku", "spare_part_name", "quantity_required", "mandatory_flag", "substitutable_flag", "spare_part_criticality", "inventory_check_required_flag", "active_flag", "advisory_only_flag", "notes"},
        "state": {"machine_id", "maintenance_plan_id", "last_maintenance_date", "operations_since_last_maintenance", "days_since_last_maintenance", "last_maintenance_level", "current_condition_status", "known_issue_flag", "maintenance_state_source", "active_flag", "advisory_only_flag", "notes"},
    }
    for name, cols in required.items():
        missing = sorted(cols.difference(frames[name].columns))
        checks.append(_result(f"maintenance_{name}_required_columns", f"{name} required columns", "FAIL" if missing else "PASS", f"Missing columns: {missing}" if missing else f"{name} has required columns.", len(missing)))
    plans = frames["plans"]
    spares = frames["plan_spares"]
    state = frames["state"]
    machines = frames["machines"]
    spare_master = frames["spares"]
    auth = frames["workforce_auth"]

    dup = int(plans["maintenance_plan_id"].astype(str).duplicated().sum())
    checks.append(_result("maintenance_plan_id_unique", "maintenance plan IDs unique", "FAIL" if dup else "PASS", f"Duplicate maintenance_plan_id rows: {dup}", dup))
    _check_refs(plans, "machine_id", machines, "machine_id", "maintenance_plan_machine_refs", checks)
    _check_refs(spares, "maintenance_plan_id", plans, "maintenance_plan_id", "maintenance_spare_plan_refs", checks)
    _check_refs(spares, "spare_part_sku", spare_master, "spare_part_sku", "maintenance_spare_sku_refs", checks)
    _check_refs(state, "machine_id", machines, "machine_id", "maintenance_state_machine_refs", checks)
    _check_refs(state, "maintenance_plan_id", plans, "maintenance_plan_id", "maintenance_state_plan_refs", checks)
    _valid_values(plans, "maintenance_level", VALID_LEVELS, "maintenance_levels_valid", checks)
    _valid_values(plans, "maintenance_category", VALID_CATEGORIES, "maintenance_categories_valid", checks)
    _valid_values(plans, "trigger_type", VALID_TRIGGERS, "maintenance_triggers_valid", checks)
    _valid_values(plans, "deferral_risk_level", VALID_RISK, "maintenance_deferral_risk_valid", checks)
    _valid_values(state, "current_condition_status", VALID_CONDITION, "maintenance_condition_status_valid", checks)
    _valid_values(state, "maintenance_state_source", VALID_STATE_SOURCE, "maintenance_state_source_valid", checks)
    _check_nonnegative(plans, ["estimated_maintenance_duration_hours", "planned_downtime_hours", "max_defer_operations", "max_defer_days", "estimated_labor_hours", "estimated_external_service_cost"], "maintenance_plan_numeric_nonnegative", checks)
    _check_nonnegative(spares, ["quantity_required"], "maintenance_spare_quantities_nonnegative", checks)
    _check_nonnegative(state, ["operations_since_last_maintenance", "days_since_last_maintenance"], "maintenance_state_numeric_nonnegative", checks)
    active = plans[_to_bool(plans["active_flag"])]
    bad_workers = active[pd.to_numeric(active["required_worker_count"], errors="coerce").fillna(0) <= 0]
    checks.append(_result("maintenance_required_worker_count_positive", "active plan worker counts positive", "FAIL" if not bad_workers.empty else "PASS", "Active plans have positive worker counts." if bad_workers.empty else f"Invalid worker counts: {bad_workers['maintenance_plan_id'].tolist()}", len(bad_workers)))
    op_trigger = active[active["trigger_type"].isin(["OPERATIONS_BASED", "OPERATIONS_OR_TIME_BASED"])]
    bad_op = op_trigger[pd.to_numeric(op_trigger["operations_between_maintenance"], errors="coerce").fillna(0) <= 0]
    time_trigger = active[active["trigger_type"].isin(["TIME_BASED", "OPERATIONS_OR_TIME_BASED"])]
    bad_days = time_trigger[pd.to_numeric(time_trigger["days_between_maintenance"], errors="coerce").fillna(0) <= 0]
    checks.append(_result("maintenance_operation_triggers_positive", "operation triggers positive", "FAIL" if not bad_op.empty else "PASS", "Operation-based triggers are positive.", len(bad_op)))
    checks.append(_result("maintenance_time_triggers_positive", "time triggers positive", "FAIL" if not bad_days.empty else "PASS", "Time-based triggers are positive.", len(bad_days)))
    prod_light_auth = auth[(auth["crew_type"] == "PRODUCTION") & _to_bool(auth["can_maintain_flag"]) & (auth["maintenance_level_authorized"].astype(str) == "LIGHT")]
    bad_light = active[(active["maintenance_level"] == "LIGHT") & _to_bool(active["can_be_performed_by_production_flag"]) & ~active["machine_id"].astype(str).isin(set(prod_light_auth["machine_id"].astype(str)))]
    checks.append(_result("maintenance_light_production_authorized", "light maintenance production authorization valid", "FAIL" if not bad_light.empty else "PASS", "Light production-performed plans have production LIGHT authorization.", len(bad_light)))
    bad_medium_heavy = active[active["maintenance_level"].isin(["MEDIUM", "HEAVY"]) & (active["required_crew_type"] != "MAINTENANCE")]
    checks.append(_result("maintenance_medium_heavy_requires_maintenance", "medium heavy requires maintenance crews", "FAIL" if not bad_medium_heavy.empty else "PASS", "Medium/heavy plans require maintenance crews.", len(bad_medium_heavy)))
    breakdown = active[active["maintenance_level"] == "BREAKDOWN_REPAIR_PLACEHOLDER"]
    invalid_breakdown = breakdown[breakdown["trigger_type"] != "BREAKDOWN_PLACEHOLDER"]
    checks.append(_result("maintenance_breakdown_placeholder_only", "breakdown placeholders only", "FAIL" if not invalid_breakdown.empty else "PASS", "Breakdown repair rows are placeholders only.", len(invalid_breakdown)))
    if not _all_true(plans, "advisory_only_flag") or not _all_true(spares, "advisory_only_flag") or not _all_true(state, "advisory_only_flag"):
        checks.append(_result("maintenance_master_advisory_only", "maintenance master advisory-only", "FAIL", "Maintenance master data advisory flags must be true.", 1))
    else:
        checks.append(_result("maintenance_master_advisory_only", "maintenance master advisory-only", "PASS", "Maintenance master data advisory flags are true.", 0))


def _build_due_status_context(plans: pd.DataFrame, state: pd.DataFrame, machines: pd.DataFrame) -> pd.DataFrame:
    frame = plans.merge(state, on=["machine_id", "maintenance_plan_id"], how="left", suffixes=("", "_state"))
    frame = frame.merge(machines[["machine_id", "machine_name", "machine_type"]], on="machine_id", how="left", suffixes=("", "_machine"))
    frame["operations_since_last_maintenance"] = pd.to_numeric(frame["operations_since_last_maintenance"], errors="coerce")
    frame["days_since_last_maintenance"] = pd.to_numeric(frame["days_since_last_maintenance"], errors="coerce")
    frame["operations_between_maintenance"] = pd.to_numeric(frame["operations_between_maintenance"], errors="coerce")
    frame["days_between_maintenance"] = pd.to_numeric(frame["days_between_maintenance"], errors="coerce")
    frame["operations_until_due"] = (frame["operations_between_maintenance"] - frame["operations_since_last_maintenance"]).where(frame["operations_between_maintenance"] > 0, pd.NA)
    frame["days_until_due"] = (frame["days_between_maintenance"] - frame["days_since_last_maintenance"]).where(frame["days_between_maintenance"] > 0, pd.NA)
    statuses = frame.apply(_due_status, axis=1)
    frame["due_status"] = [item[0] for item in statuses]
    frame["due_status_reason"] = [item[1] for item in statuses]
    frame["deferral_review_required_flag"] = frame["due_status"].isin(["DUE_NOW", "OVERDUE"]) & frame["deferral_risk_level"].isin(["HIGH", "CRITICAL"])
    frame["planning_run_id"] = _planning_run_id()
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[["planning_run_id", "machine_id", "machine_name", "machine_type", "maintenance_plan_id", "maintenance_level", "maintenance_category", "trigger_type", "operations_between_maintenance", "days_between_maintenance", "operations_since_last_maintenance", "days_since_last_maintenance", "operations_until_due", "days_until_due", "due_status", "due_status_reason", "deferral_risk_level", "can_defer_flag", "max_defer_operations", "max_defer_days", "deferral_review_required_flag", "current_condition_status", "maintenance_state_source", "source_phase", "advisory_only_flag"]].copy()


def _build_spare_part_context(plans: pd.DataFrame, plan_spares: pd.DataFrame, spare_phase: pd.DataFrame, phase4_spares: pd.DataFrame) -> pd.DataFrame:
    frame = plan_spares.merge(plans[["maintenance_plan_id", "machine_id", "machine_name"]], on="maintenance_plan_id", how="left")
    inventory = phase4_spares[["spare_part_sku", "inventory_status", "supplier_coverage_status", "spare_part_readiness_status"]].drop_duplicates("spare_part_sku")
    frame = frame.merge(inventory, on="spare_part_sku", how="left")
    frame["spare_part_review_required_flag"] = ~frame["spare_part_readiness_status"].astype(str).eq("READY")
    frame["note_no_consumption_flag"] = True
    frame["planning_run_id"] = _planning_run_id()
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[["planning_run_id", "maintenance_plan_id", "machine_id", "machine_name", "spare_part_sku", "spare_part_name", "quantity_required", "mandatory_flag", "spare_part_criticality", "inventory_status", "supplier_coverage_status", "spare_part_readiness_status", "spare_part_review_required_flag", "note_no_consumption_flag", "source_phase", "advisory_only_flag"]].copy()


def _build_cost_downtime_context(plans: pd.DataFrame, plan_spares: pd.DataFrame, spares: pd.DataFrame) -> pd.DataFrame:
    sp = plan_spares.merge(spares[["spare_part_sku", "unit_cost"]], on="spare_part_sku", how="left")
    sp["quantity_required"] = pd.to_numeric(sp["quantity_required"], errors="coerce").fillna(0)
    sp["unit_cost"] = pd.to_numeric(sp["unit_cost"], errors="coerce").fillna(0)
    spare_cost = sp.assign(_cost=sp["quantity_required"] * sp["unit_cost"]).groupby("maintenance_plan_id", as_index=False).agg(estimated_spare_part_cost=("_cost", "sum"))
    frame = plans.merge(spare_cost, on="maintenance_plan_id", how="left")
    frame["estimated_spare_part_cost"] = pd.to_numeric(frame["estimated_spare_part_cost"], errors="coerce").fillna(0)
    frame["estimated_labor_hours"] = pd.to_numeric(frame["estimated_labor_hours"], errors="coerce").fillna(0)
    frame["estimated_labor_cost"] = frame["estimated_labor_hours"] * 42.0
    frame["estimated_external_service_cost"] = pd.to_numeric(frame["estimated_external_service_cost"], errors="coerce").fillna(0)
    frame["estimated_total_maintenance_cost"] = frame["estimated_labor_cost"] + frame["estimated_spare_part_cost"] + frame["estimated_external_service_cost"]
    frame["cost_basis"] = "PLANNING_ESTIMATE_ONLY"
    frame["downtime_basis"] = "MAINTENANCE_PLAN_MASTER_DATA"
    frame["planning_run_id"] = _planning_run_id()
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[["planning_run_id", "maintenance_plan_id", "machine_id", "machine_name", "maintenance_level", "estimated_maintenance_duration_hours", "planned_downtime_hours", "required_worker_count", "estimated_labor_hours", "estimated_labor_cost", "estimated_spare_part_cost", "estimated_external_service_cost", "estimated_total_maintenance_cost", "cost_basis", "downtime_basis", "source_phase", "advisory_only_flag"]].copy()


def _build_manager_review_queue(due: pd.DataFrame, spare: pd.DataFrame, cost: pd.DataFrame, plans: pd.DataFrame, auth: pd.DataFrame) -> pd.DataFrame:
    rows = []
    item = 1
    for row in due.itertuples():
        if row.due_status in {"OVERDUE", "DUE_NOW", "DUE_SOON", "REVIEW_REQUIRED"}:
            severity = "CRITICAL" if row.due_status == "OVERDUE" else ("HIGH" if row.due_status == "DUE_NOW" else "MEDIUM")
            rows.append(_review_row(item, row.planning_run_id, row.machine_id, row.machine_name, row.maintenance_plan_id, f"MAINTENANCE_{row.due_status}", severity, row.due_status_reason, "REVIEW_MAINTENANCE_PLAN"))
            item += 1
        if row.deferral_review_required_flag:
            rows.append(_review_row(item, row.planning_run_id, row.machine_id, row.machine_name, row.maintenance_plan_id, "HIGH_DEFERRAL_RISK", "HIGH", f"Deferral risk is {row.deferral_risk_level}.", "REVIEW_DEFERRAL_RISK"))
            item += 1
        if row.maintenance_level == "BREAKDOWN_REPAIR_PLACEHOLDER":
            rows.append(_review_row(item, row.planning_run_id, row.machine_id, row.machine_name, row.maintenance_plan_id, "PLACEHOLDER_REVIEW", "LOW", "Breakdown repair placeholder exists but no event or work order is generated.", "REVIEW_BEFORE_ACTION"))
            item += 1
    for row in spare[spare["spare_part_review_required_flag"]].itertuples():
        rows.append(_review_row(item, row.planning_run_id, row.machine_id, row.machine_name, row.maintenance_plan_id, "SPARE_PART_READINESS_REVIEW", "HIGH" if row.spare_part_criticality == "CRITICAL" else "MEDIUM", f"Spare part {row.spare_part_sku} readiness is {row.spare_part_readiness_status}.", "REVIEW_SPARE_PART_AVAILABILITY"))
        item += 1
    for row in cost.itertuples():
        if float(row.planned_downtime_hours) >= 6:
            rows.append(_review_row(item, row.planning_run_id, row.machine_id, row.machine_name, row.maintenance_plan_id, "HIGH_DOWNTIME_REVIEW", "HIGH", f"Estimated planned downtime is {row.planned_downtime_hours} hours.", "REVIEW_DOWNTIME_IMPACT"))
            item += 1
        if float(row.estimated_total_maintenance_cost) >= 700:
            rows.append(_review_row(item, row.planning_run_id, row.machine_id, row.machine_name, row.maintenance_plan_id, "HIGH_COST_REVIEW", "MEDIUM", f"Estimated maintenance cost is {row.estimated_total_maintenance_cost:.2f}.", "REVIEW_MAINTENANCE_PLAN"))
            item += 1
    return pd.DataFrame(rows, columns=["review_item_id", "planning_run_id", "machine_id", "machine_name", "maintenance_plan_id", "issue_type", "issue_severity", "issue_description", "recommended_review_action", "auto_action_allowed", "advisory_only_flag"])


def _build_phase4_readiness_context(due: pd.DataFrame, spare: pd.DataFrame, cost: pd.DataFrame, review: pd.DataFrame) -> pd.DataFrame:
    due_counts = due.groupby(["planning_run_id", "machine_id", "machine_name", "machine_type"], as_index=False).agg(
        maintenance_plan_count=("maintenance_plan_id", "nunique"),
        due_now_count=("due_status", lambda s: int((s == "DUE_NOW").sum())),
        overdue_count=("due_status", lambda s: int((s == "OVERDUE").sum())),
        due_soon_count=("due_status", lambda s: int((s == "DUE_SOON").sum())),
        highest_deferral_risk_level=("deferral_risk_level", _highest_risk),
    )
    spare_counts = spare.groupby("machine_id", as_index=False).agg(spare_part_review_required_count=("spare_part_review_required_flag", lambda s: int(_to_bool(s).sum())))
    cost_sum = cost.groupby("machine_id", as_index=False).agg(
        estimated_total_planned_downtime_hours=("planned_downtime_hours", "sum"),
        estimated_total_maintenance_cost=("estimated_total_maintenance_cost", "sum"),
    )
    crew_review = review[review["issue_type"] == "CREW_AUTHORIZATION_REVIEW"].groupby("machine_id", as_index=False).size().rename(columns={"size": "crew_authorization_review_required_count"})
    frame = due_counts.merge(spare_counts, on="machine_id", how="left").merge(cost_sum, on="machine_id", how="left").merge(crew_review, on="machine_id", how="left")
    for col in ["spare_part_review_required_count", "crew_authorization_review_required_count", "estimated_total_planned_downtime_hours", "estimated_total_maintenance_cost"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)
    frame["maintenance_readiness_status"] = frame.apply(_readiness_status, axis=1)
    frame["maintenance_planning_ready_flag"] = frame["maintenance_readiness_status"].isin(["READY", "DUE_SOON_REVIEW"])
    frame["source_phase"] = "PHASE4_STEP7C_MAINTENANCE_READINESS_CONTEXT"
    frame["advisory_only_flag"] = True
    return frame[["planning_run_id", "machine_id", "machine_name", "machine_type", "maintenance_plan_count", "due_now_count", "overdue_count", "due_soon_count", "highest_deferral_risk_level", "spare_part_review_required_count", "crew_authorization_review_required_count", "estimated_total_planned_downtime_hours", "estimated_total_maintenance_cost", "maintenance_readiness_status", "maintenance_planning_ready_flag", "source_phase", "advisory_only_flag"]].copy()


def _due_status(row: pd.Series) -> tuple[str, str]:
    if row.get("trigger_type") in {"BREAKDOWN_PLACEHOLDER", "CONDITION_BASED_PLACEHOLDER"}:
        return "REVIEW_REQUIRED", f"{row.get('trigger_type')} is a placeholder only."
    statuses = []
    reasons = []
    if row.get("trigger_type") in {"OPERATIONS_BASED", "OPERATIONS_OR_TIME_BASED"}:
        status = _threshold_status(row.get("operations_since_last_maintenance"), row.get("operations_between_maintenance"))
        statuses.append(status)
        reasons.append(f"operations trigger {status}")
    if row.get("trigger_type") in {"TIME_BASED", "OPERATIONS_OR_TIME_BASED"}:
        status = _threshold_status(row.get("days_since_last_maintenance"), row.get("days_between_maintenance"))
        statuses.append(status)
        reasons.append(f"time trigger {status}")
    if not statuses:
        return "REVIEW_REQUIRED", "No valid due-status trigger."
    order = {"NOT_DUE": 0, "DUE_SOON": 1, "DUE_NOW": 2, "OVERDUE": 3, "REVIEW_REQUIRED": 4}
    worst = max(statuses, key=lambda s: order[s])
    return worst, "; ".join(reasons)


def _threshold_status(actual: object, threshold: object) -> str:
    actual = pd.to_numeric(pd.Series([actual]), errors="coerce").iloc[0]
    threshold = pd.to_numeric(pd.Series([threshold]), errors="coerce").iloc[0]
    if pd.isna(actual) or pd.isna(threshold) or threshold <= 0:
        return "REVIEW_REQUIRED"
    if actual > threshold:
        return "OVERDUE"
    if actual >= threshold * 0.98:
        return "DUE_NOW"
    if actual >= threshold * 0.80:
        return "DUE_SOON"
    return "NOT_DUE"


def _readiness_status(row: pd.Series) -> str:
    if int(row["overdue_count"]):
        return "OVERDUE_REVIEW"
    if int(row["due_now_count"]):
        return "DUE_NOW_REVIEW"
    if int(row["spare_part_review_required_count"]):
        return "SPARE_PART_REVIEW"
    if int(row["crew_authorization_review_required_count"]):
        return "CREW_AUTHORIZATION_REVIEW"
    if int(row["due_soon_count"]):
        return "DUE_SOON_REVIEW"
    return "READY"


def _highest_risk(values: pd.Series) -> str:
    values = [str(v) for v in values.dropna()]
    if not values:
        return "LOW"
    return max(values, key=lambda v: RISK_ORDER.get(v, 0))


def _validate_outputs(due: pd.DataFrame, spare: pd.DataFrame, cost: pd.DataFrame, review: pd.DataFrame, phase4: pd.DataFrame, checks: list[dict]) -> None:
    frames = [due, spare, cost, phase4]
    bad = sum(int(frame.empty) for frame in frames)
    bad += sum(int((~_to_bool(frame["advisory_only_flag"])).sum()) for frame in frames if "advisory_only_flag" in frame.columns)
    if not review.empty:
        bad += int(_to_bool(review["auto_action_allowed"]).sum())
        bad += int((~_to_bool(review["advisory_only_flag"])).sum())
    for col in ["estimated_labor_cost", "estimated_spare_part_cost", "estimated_external_service_cost", "estimated_total_maintenance_cost"]:
        bad += int((pd.to_numeric(cost[col], errors="coerce").fillna(-1) < 0).sum())
    if "note_no_consumption_flag" in spare.columns:
        bad += int((~_to_bool(spare["note_no_consumption_flag"])).sum())
    checks.append(_result("maintenance_context_outputs_valid", "maintenance context outputs valid", "FAIL" if bad else "PASS", "Maintenance contexts are valid and advisory-only." if not bad else f"Invalid maintenance context values: {bad}", bad))


def _review_row(item: int, run_id: str, machine_id: str, machine_name: str, plan_id: str, issue_type: str, severity: str, description: str, action: str) -> dict:
    return {
        "review_item_id": f"MAINT-REV-{item:04d}",
        "planning_run_id": run_id,
        "machine_id": machine_id,
        "machine_name": machine_name,
        "maintenance_plan_id": plan_id,
        "issue_type": issue_type,
        "issue_severity": severity,
        "issue_description": description,
        "recommended_review_action": action,
        "auto_action_allowed": False,
        "advisory_only_flag": True,
    }


def _check_refs(child: pd.DataFrame, child_column: str, parent: pd.DataFrame, parent_column: str, check_id: str, checks: list[dict]) -> None:
    missing = sorted(set(child[child_column].dropna().astype(str)) - set(parent[parent_column].dropna().astype(str)))
    checks.append(_result(check_id, f"{child_column} references valid", "FAIL" if missing else "PASS", f"Missing references: {missing}" if missing else f"{child_column} references are valid.", len(missing)))


def _valid_values(df: pd.DataFrame, column: str, allowed: set[str], check_id: str, checks: list[dict]) -> None:
    bad = df[~df[column].astype(str).isin(allowed)]
    checks.append(_result(check_id, f"{column} values valid", "FAIL" if not bad.empty else "PASS", f"{column} values are valid." if bad.empty else f"Invalid {column}: {bad[column].tolist()}", len(bad)))


def _check_nonnegative(df: pd.DataFrame, columns: list[str], check_id: str, checks: list[dict]) -> None:
    bad = 0
    for column in columns:
        values = pd.to_numeric(df[column], errors="coerce")
        bad += int(values.isna().sum()) + int((values < 0).sum())
    checks.append(_result(check_id, "numeric fields non-negative", "FAIL" if bad else "PASS", f"Invalid numeric values: {bad}" if bad else "Numeric fields are non-negative.", bad))


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked = ["maintenance_work_order", "production_order", "purchase_order", "spare_part_consumption", "inventory_reservation", "finite_schedule", "dispatch_schedule", "crew_schedule", "simulation"]
    bad = []
    for folder in [OUTPUT_DIR, PHASE4_OUTPUT_DIR]:
        if not folder.exists():
            continue
        for path in folder.glob("*"):
            if path.is_file() and any(token in path.name.lower() for token in blocked):
                bad.append(str(path))
    checks.append(_result("maintenance_no_blocked_outputs", "no blocked maintenance outputs", "FAIL" if bad else "PASS", f"Blocked outputs found: {bad}" if bad else "No maintenance work-order, scheduling, reservation, purchase-order, or simulation outputs found.", len(bad)))


def _planning_run_id() -> str:
    if os.environ.get("INTEGRATED_RUN_ID"):
        return os.environ["INTEGRATED_RUN_ID"]
    if PHASE4_MPS_FILE.exists():
        try:
            frame = pd.read_csv(PHASE4_MPS_FILE, usecols=["planning_run_id"])
            values = frame["planning_run_id"].dropna().astype(str).str.strip()
            if not values.empty:
                return values.iloc[0]
        except ValueError:
            pass
    return f"SHARED-MAINT-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


def _load_csv(path: Path, name: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"maintenance_{name}_exists", f"{name} exists", "FAIL", f"Missing file: {path}", 1))
        return None
    frame = pd.read_csv(path, keep_default_na=False)
    checks.append(_result(f"maintenance_{name}_exists", f"{name} exists", "PASS", f"Loaded {path}", 0))
    if frame.empty:
        checks.append(_result(f"maintenance_{name}_not_empty", f"{name} not empty", "FAIL", f"{name} has no rows.", 1))
    return frame


def _all_true(df: pd.DataFrame, column: str) -> bool:
    return column in df.columns and bool(_to_bool(df[column]).all())


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _result(check_id: str, check_name: str, status: str, message: str, affected_rows: int) -> dict:
    return {
        "check_id": check_id,
        "check_name": check_name,
        "status": status,
        "message": message,
        "affected_rows": affected_rows,
        "advisory_only_flag": True,
    }


if __name__ == "__main__":
    validation, *_ = build_maintenance_master_data_outputs()
    print(f"Maintenance validation rows: {len(validation)}")
    print(f"Maintenance validation status counts: {validation['status'].value_counts().to_dict() if not validation.empty else {}}")
