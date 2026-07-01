"""Estimate advisory maintenance and breakdown impact on production planning."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHARED_OUTPUT_DIR = PROJECT_ROOT / "shared" / "outputs"
SHARED_DATA_DIR = PROJECT_ROOT / "shared" / "data"
PHASE4_DIR = PROJECT_ROOT / "phase 4"
PHASE4_OUTPUT_DIR = PHASE4_DIR / "outputs"

MAINTENANCE_PLANS_FILE = SHARED_DATA_DIR / "maintenance_plans.csv"
MACHINES_FILE = PHASE4_DIR / "data" / "machines.csv"
WORKSTATIONS_FILE = PHASE4_DIR / "data" / "workstations.csv"

MAINTENANCE_DUE_FILE = SHARED_OUTPUT_DIR / "maintenance_due_status_context.csv"
MAINTENANCE_COST_FILE = SHARED_OUTPUT_DIR / "maintenance_cost_downtime_context.csv"
MAINTENANCE_SPARE_FILE = SHARED_OUTPUT_DIR / "maintenance_spare_part_requirement_context.csv"
BREAKDOWN_RISK_FILE = SHARED_OUTPUT_DIR / "breakdown_risk_forecast.csv"
BREAKDOWN_FAILURE_FILE = SHARED_OUTPUT_DIR / "breakdown_failure_mode_exposure.csv"
BREAKDOWN_SPARE_FILE = SHARED_OUTPUT_DIR / "breakdown_spare_part_exposure.csv"
BREAKDOWN_CREW_FILE = SHARED_OUTPUT_DIR / "breakdown_crew_skill_exposure.csv"
MAINTENANCE_WORKLOAD_FILE = SHARED_OUTPUT_DIR / "maintenance_workload_by_skill.csv"
MAINTENANCE_REPAIR_QUEUE_FILE = SHARED_OUTPUT_DIR / "maintenance_repair_queue_risk.csv"
MAINTENANCE_BACKLOG_FILE = SHARED_OUTPUT_DIR / "maintenance_backlog_risk_summary.csv"
PHASE4_CREW_CONTEXT_FILE = PHASE4_OUTPUT_DIR / "phase4_maintenance_crew_capacity_context.csv"
CAPACITY_MACHINE_FILE = PHASE4_OUTPUT_DIR / "phase4_capacity_load_by_machine_type.csv"
CAPACITY_WORKSTATION_FILE = PHASE4_OUTPUT_DIR / "phase4_capacity_load_by_workstation.csv"
QUALITY_CAPACITY_FILE = PHASE4_OUTPUT_DIR / "phase4_quality_adjusted_capacity_by_workstation.csv"
BOTTLENECK_VISIBILITY_FILE = PHASE4_OUTPUT_DIR / "phase4_bottleneck_visibility_summary.csv"
PRODUCTION_FLOW_FILE = PHASE4_OUTPUT_DIR / "phase4_production_flow_view.csv"

WORKFORCE_VALIDATION_FILE = SHARED_OUTPUT_DIR / "workforce_crew_validation.csv"
SPARE_VALIDATION_FILE = SHARED_OUTPUT_DIR / "spare_part_validation.csv"
MAINTENANCE_VALIDATION_FILE = SHARED_OUTPUT_DIR / "maintenance_plan_validation.csv"
BREAKDOWN_VALIDATION_FILE = SHARED_OUTPUT_DIR / "breakdown_validation.csv"
CREW_CAPACITY_VALIDATION_FILE = SHARED_OUTPUT_DIR / "maintenance_crew_capacity_validation.csv"

MACHINE_AVAILABILITY_OUTPUT_FILE = SHARED_OUTPUT_DIR / "maintenance_machine_availability_impact.csv"
PRODUCTION_CAPACITY_OUTPUT_FILE = SHARED_OUTPUT_DIR / "maintenance_production_capacity_impact.csv"
COST_EXPOSURE_OUTPUT_FILE = SHARED_OUTPUT_DIR / "maintenance_breakdown_cost_exposure.csv"
BOTTLENECK_IMPACT_OUTPUT_FILE = SHARED_OUTPUT_DIR / "maintenance_bottleneck_impact.csv"
SCHEDULING_CANDIDATE_OUTPUT_FILE = SHARED_OUTPUT_DIR / "maintenance_scheduling_candidate_backlog.csv"
WINDOW_REQUIREMENTS_OUTPUT_FILE = SHARED_OUTPUT_DIR / "maintenance_window_requirements.csv"
MANAGER_REVIEW_OUTPUT_FILE = SHARED_OUTPUT_DIR / "maintenance_impact_manager_review_queue.csv"
VALIDATION_OUTPUT_FILE = SHARED_OUTPUT_DIR / "maintenance_production_impact_validation.csv"
PHASE4_CONTEXT_OUTPUT_FILE = PHASE4_OUTPUT_DIR / "phase4_maintenance_production_impact_context.csv"

SOURCE_PHASE = "SHARED_STEP7F_MAINTENANCE_PRODUCTION_IMPACT"
PHASE4_SOURCE_PHASE = "PHASE4_STEP7F_MAINTENANCE_PRODUCTION_IMPACT_CONTEXT"
CONFIRMATION_STATUS = "PLANNING_IMPACT_ESTIMATE_ONLY_NOT_EXECUTION_CONFIRMED"

VALID_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "REVIEW_REQUIRED"}
RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4, "REVIEW_REQUIRED": 5}


def build_maintenance_production_impact_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    checks: list[dict] = []
    frames = {
        "machines": _load_csv(MACHINES_FILE, "machines", checks),
        "workstations": _load_csv(WORKSTATIONS_FILE, "workstations", checks),
        "plans": _load_csv(MAINTENANCE_PLANS_FILE, "maintenance_plans", checks),
        "due": _load_csv(MAINTENANCE_DUE_FILE, "maintenance_due_status_context", checks),
        "cost": _load_csv(MAINTENANCE_COST_FILE, "maintenance_cost_downtime_context", checks),
        "maintenance_spare": _load_csv(MAINTENANCE_SPARE_FILE, "maintenance_spare_part_requirement_context", checks),
        "risk": _load_csv(BREAKDOWN_RISK_FILE, "breakdown_risk_forecast", checks),
        "failure": _load_csv(BREAKDOWN_FAILURE_FILE, "breakdown_failure_mode_exposure", checks),
        "breakdown_spare": _load_csv(BREAKDOWN_SPARE_FILE, "breakdown_spare_part_exposure", checks),
        "breakdown_crew": _load_csv(BREAKDOWN_CREW_FILE, "breakdown_crew_skill_exposure", checks),
        "workload": _load_csv(MAINTENANCE_WORKLOAD_FILE, "maintenance_workload_by_skill", checks),
        "repair_queue": _load_csv(MAINTENANCE_REPAIR_QUEUE_FILE, "maintenance_repair_queue_risk", checks),
        "backlog": _load_csv(MAINTENANCE_BACKLOG_FILE, "maintenance_backlog_risk_summary", checks),
        "crew_context": _load_csv(PHASE4_CREW_CONTEXT_FILE, "phase4_maintenance_crew_capacity_context", checks),
        "capacity_machine": _load_csv(CAPACITY_MACHINE_FILE, "phase4_capacity_load_by_machine_type", checks),
        "capacity_workstation": _load_csv(CAPACITY_WORKSTATION_FILE, "phase4_capacity_load_by_workstation", checks),
        "quality_capacity": _load_csv(QUALITY_CAPACITY_FILE, "phase4_quality_adjusted_capacity_by_workstation", checks),
        "bottleneck": _load_csv(BOTTLENECK_VISIBILITY_FILE, "phase4_bottleneck_visibility_summary", checks),
        "flow": _load_csv(PRODUCTION_FLOW_FILE, "phase4_production_flow_view", checks),
    }
    if all(frame is not None for frame in frames.values()):
        availability = _build_machine_availability(frames)
        capacity = _build_production_capacity_impact(frames, availability)
        cost = _build_cost_exposure(frames, availability)
        bottleneck = _build_bottleneck_impact(frames, availability)
        candidates = _build_scheduling_candidates(frames, availability, capacity, bottleneck)
        windows = _build_window_requirements(candidates)
        review = _build_manager_review(availability, capacity, cost, bottleneck, candidates)
        phase4_context = _build_phase4_context(availability, capacity, cost, bottleneck, candidates)
        _validate_outputs(availability, capacity, cost, bottleneck, candidates, windows, review, phase4_context, checks)
    else:
        availability = capacity = cost = bottleneck = candidates = windows = review = phase4_context = pd.DataFrame()
    _check_existing_validations(checks)
    _check_no_blocked_outputs(checks)

    SHARED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PHASE4_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    availability.to_csv(MACHINE_AVAILABILITY_OUTPUT_FILE, index=False)
    capacity.to_csv(PRODUCTION_CAPACITY_OUTPUT_FILE, index=False)
    cost.to_csv(COST_EXPOSURE_OUTPUT_FILE, index=False)
    bottleneck.to_csv(BOTTLENECK_IMPACT_OUTPUT_FILE, index=False)
    candidates.to_csv(SCHEDULING_CANDIDATE_OUTPUT_FILE, index=False)
    windows.to_csv(WINDOW_REQUIREMENTS_OUTPUT_FILE, index=False)
    review.to_csv(MANAGER_REVIEW_OUTPUT_FILE, index=False)
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    phase4_context.to_csv(PHASE4_CONTEXT_OUTPUT_FILE, index=False)
    return validation, availability, capacity, cost, bottleneck, candidates, windows, review, phase4_context


def _build_machine_availability(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    machines = frames["machines"].copy()
    risk = frames["risk"].copy()
    due = frames["due"].copy()
    cost = frames["cost"].copy()
    repair_queue = frames["repair_queue"].copy()
    backlog = frames["backlog"].copy()
    mspare = frames["maintenance_spare"].copy()
    bspare = frames["breakdown_spare"].copy()

    due_agg = due.groupby("machine_id", as_index=False).agg(
        maintenance_due_signal=("due_status", _worst_due),
        overdue_count=("due_status", lambda s: int((s.astype(str) == "OVERDUE").sum())),
        due_now_count=("due_status", lambda s: int((s.astype(str) == "DUE_NOW").sum())),
    )
    cost_factor = due[["machine_id", "maintenance_plan_id", "due_status"]].copy()
    cost_factor["due_factor"] = cost_factor["due_status"].map(_due_factor).fillna(0)
    planned = cost.merge(cost_factor, on=["machine_id", "maintenance_plan_id"], how="left")
    planned["due_factor"] = pd.to_numeric(planned["due_factor"], errors="coerce").fillna(0)
    planned["planned_downtime_weighted"] = _num(planned, "planned_downtime_hours") * planned["due_factor"]
    planned_agg = planned.groupby("machine_id", as_index=False).agg(
        planned_maintenance_downtime_hours=("planned_downtime_weighted", "sum"),
        planned_maintenance_cost=("estimated_total_maintenance_cost", "sum"),
    )
    queue_agg = repair_queue.groupby("machine_id", as_index=False).agg(
        repair_queue_risk_level=("estimated_repair_queue_risk_level", _highest_level),
        expected_repair_hours=("expected_repair_hours_next_period", "max"),
        crew_capacity_blocker_flag=("crew_capacity_status", lambda s: bool(s.astype(str).isin(["NO_ACTIVE_COVERAGE", "REVIEW_REQUIRED", "OVERLOADED"]).any())),
    )
    maint_spare = mspare.groupby("machine_id", as_index=False).agg(
        maintenance_spare_blocker=("spare_part_readiness_status", lambda s: bool((s.astype(str) != "READY").any())),
        maintenance_spare_cost=("quantity_required", "sum"),
    )
    b_spare = bspare.groupby("machine_id", as_index=False).agg(
        breakdown_spare_blocker=("spare_part_readiness_status", lambda s: bool((s.astype(str) != "READY").any())),
        expected_spare_part_exposure_qty=("expected_spare_part_exposure_qty", "sum"),
    )
    frame = machines.merge(risk[["machine_id", "breakdown_risk_level", "expected_downtime_hours_next_period", "expected_repair_hours_next_period"]], on="machine_id", how="left")
    frame = frame.merge(due_agg, on="machine_id", how="left").merge(planned_agg, on="machine_id", how="left").merge(queue_agg, on="machine_id", how="left").merge(maint_spare, on="machine_id", how="left").merge(b_spare, on="machine_id", how="left")
    frame["planned_maintenance_downtime_hours"] = _num(frame, "planned_maintenance_downtime_hours")
    frame["expected_breakdown_downtime_hours"] = _num(frame, "expected_downtime_hours_next_period")
    frame["expected_repair_hours"] = _num(frame, "expected_repair_hours").where(_num(frame, "expected_repair_hours") > 0, _num(frame, "expected_repair_hours_next_period"))
    frame["repair_queue_risk_level"] = frame["repair_queue_risk_level"].fillna("REVIEW_REQUIRED")
    frame["maintenance_due_signal"] = frame["maintenance_due_signal"].fillna("REVIEW_REQUIRED")
    frame["breakdown_risk_level"] = frame["breakdown_risk_level"].fillna("REVIEW_REQUIRED")
    frame["spare_part_blocker_flag"] = _to_bool(frame["maintenance_spare_blocker"]) | _to_bool(frame["breakdown_spare_blocker"])
    frame["crew_capacity_blocker_flag"] = _to_bool(frame["crew_capacity_blocker_flag"])
    frame["total_downtime_exposure_hours"] = (frame["planned_maintenance_downtime_hours"] + frame["expected_breakdown_downtime_hours"]).round(2)
    backlog_level = backlog.iloc[0]["backlog_risk_level"] if not backlog.empty else "REVIEW_REQUIRED"

    scores = []
    reasons = []
    for row in frame.itertuples():
        score = 0.0
        reason = []
        score += _risk_points(row.breakdown_risk_level)
        if row.maintenance_due_signal == "OVERDUE":
            score += 30; reason.append("OVERDUE_MAINTENANCE")
        elif row.maintenance_due_signal in {"DUE_NOW", "DUE_SOON"}:
            score += 15; reason.append(row.maintenance_due_signal)
        score += min(float(row.total_downtime_exposure_hours) * 5, 35)
        if row.repair_queue_risk_level in {"HIGH", "CRITICAL", "REVIEW_REQUIRED"}:
            score += 20; reason.append("REPAIR_QUEUE_RISK")
        if row.spare_part_blocker_flag:
            score += 20; reason.append("SPARE_PART_BLOCKER")
        if row.crew_capacity_blocker_flag:
            score += 25; reason.append("CREW_CAPACITY_BLOCKER")
        if backlog_level in {"HIGH", "CRITICAL", "REVIEW_REQUIRED"}:
            score += 10; reason.append(f"BACKLOG_{backlog_level}")
        scores.append(round(score, 2))
        reasons.append(";".join(reason) if reason else "LOW_MAINTENANCE_BREAKDOWN_IMPACT")
    frame["machine_availability_impact_score"] = scores
    frame["machine_availability_impact_level"] = frame["machine_availability_impact_score"].apply(_impact_level)
    frame["availability_impact_reason"] = reasons
    frame["planning_run_id"] = _planning_run_id()
    frame["confirmation_status"] = CONFIRMATION_STATUS
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[[
        "planning_run_id", "machine_id", "machine_name", "machine_type", "maintenance_due_signal", "breakdown_risk_level",
        "planned_maintenance_downtime_hours", "expected_breakdown_downtime_hours", "expected_repair_hours",
        "repair_queue_risk_level", "spare_part_blocker_flag", "crew_capacity_blocker_flag", "total_downtime_exposure_hours",
        "machine_availability_impact_score", "machine_availability_impact_level", "availability_impact_reason",
        "confirmation_status", "source_phase", "advisory_only_flag",
    ]].copy()


def _build_production_capacity_impact(frames: dict[str, pd.DataFrame], availability: pd.DataFrame) -> pd.DataFrame:
    machines = frames["machines"][["machine_id", "workstation_id"]].copy()
    workstations = frames["workstations"][["workstation_id", "workstation_name"]].copy()
    cap = frames["capacity_workstation"].copy()
    qcap = frames["quality_capacity"].copy()
    cap_agg = cap.groupby(["workstation_id", "workstation_name"], as_index=False).agg(
        current_capacity_status=("capacity_status", _worst_capacity_status),
        current_utilization_pct=("utilization_pct", "max"),
        available_hours=("available_hours", "max"),
    )
    q_agg = qcap.groupby("workstation_id", as_index=False).agg(quality_adjusted_utilization_pct=("quality_adjusted_utilization_pct", "max"))
    frame = availability.merge(machines, on="machine_id", how="left").merge(workstations, on="workstation_id", how="left")
    frame = frame.merge(cap_agg, on=["workstation_id", "workstation_name"], how="left").merge(q_agg, on="workstation_id", how="left")
    frame["current_utilization_pct"] = _num(frame, "current_utilization_pct")
    frame["quality_adjusted_utilization_pct"] = _num(frame, "quality_adjusted_utilization_pct")
    frame["available_hours"] = _num(frame, "available_hours")
    frame["capacity_at_risk_hours"] = _num(frame, "total_downtime_exposure_hours")
    frame["estimated_utilization_increase_if_downtime_applied_pct"] = frame.apply(lambda r: round((r["capacity_at_risk_hours"] / r["available_hours"] * 100), 2) if r["available_hours"] > 0 else 0.0, axis=1)
    frame["capacity_impact_level"] = frame.apply(_capacity_impact_level, axis=1)
    frame["production_capacity_review_required_flag"] = frame["capacity_impact_level"].isin(["HIGH", "CRITICAL", "REVIEW_REQUIRED"])
    frame["note_no_capacity_reduction_applied_flag"] = True
    frame["confirmation_status"] = CONFIRMATION_STATUS
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[[
        "planning_run_id", "machine_id", "machine_name", "workstation_id", "workstation_name", "current_capacity_status",
        "current_utilization_pct", "quality_adjusted_utilization_pct", "total_downtime_exposure_hours", "capacity_at_risk_hours",
        "estimated_utilization_increase_if_downtime_applied_pct", "capacity_impact_level", "production_capacity_review_required_flag",
        "note_no_capacity_reduction_applied_flag", "confirmation_status", "source_phase", "advisory_only_flag",
    ]].copy()


def _build_cost_exposure(frames: dict[str, pd.DataFrame], availability: pd.DataFrame) -> pd.DataFrame:
    machines = frames["machines"][["machine_id", "machine_name", "hourly_machine_cost"]].copy()
    cost = frames["cost"].copy()
    due = frames["due"][["machine_id", "maintenance_plan_id", "due_status"]].copy()
    due["due_factor"] = due["due_status"].map(_due_factor).fillna(0)
    planned = cost.merge(due, on=["machine_id", "maintenance_plan_id"], how="left")
    planned["weighted_maintenance_cost"] = _num(planned, "estimated_total_maintenance_cost") * _num(planned, "due_factor")
    planned_agg = planned.groupby("machine_id", as_index=False).agg(planned_maintenance_cost=("weighted_maintenance_cost", "sum"))
    failure = frames["failure"].copy()
    repair_agg = failure.groupby("machine_id", as_index=False).agg(expected_repair_hours=("expected_repair_hours", "sum"))
    spare = frames["breakdown_spare"].copy()
    spare_agg = spare.groupby("machine_id", as_index=False).agg(expected_spare_part_exposure_cost=("expected_spare_part_exposure_qty", "sum"))
    frame = availability[["planning_run_id", "machine_id", "machine_name", "total_downtime_exposure_hours"]].merge(machines, on=["machine_id", "machine_name"], how="left")
    frame = frame.merge(planned_agg, on="machine_id", how="left").merge(repair_agg, on="machine_id", how="left").merge(spare_agg, on="machine_id", how="left")
    frame["planned_maintenance_cost"] = _num(frame, "planned_maintenance_cost")
    frame["expected_breakdown_repair_cost"] = (_num(frame, "expected_repair_hours") * 65.0).round(2)
    frame["expected_spare_part_exposure_cost"] = (_num(frame, "expected_spare_part_exposure_cost") * 45.0).round(2)
    frame["expected_downtime_cost_exposure"] = (_num(frame, "total_downtime_exposure_hours") * (_num(frame, "hourly_machine_cost") + 125.0)).round(2)
    frame["total_maintenance_breakdown_cost_exposure"] = (frame["planned_maintenance_cost"] + frame["expected_breakdown_repair_cost"] + frame["expected_spare_part_exposure_cost"] + frame["expected_downtime_cost_exposure"]).round(2)
    frame["cost_exposure_level"] = frame["total_maintenance_breakdown_cost_exposure"].apply(lambda v: "CRITICAL" if v >= 1000 else ("HIGH" if v >= 500 else ("MEDIUM" if v >= 200 else "LOW")))
    frame["cost_basis"] = "PLANNED_MAINTENANCE_PLUS_BREAKDOWN_EXPOSURE_ESTIMATE"
    frame["note_no_financial_posting_flag"] = True
    frame["confirmation_status"] = CONFIRMATION_STATUS
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[[
        "planning_run_id", "machine_id", "machine_name", "planned_maintenance_cost", "expected_breakdown_repair_cost",
        "expected_spare_part_exposure_cost", "expected_downtime_cost_exposure", "total_maintenance_breakdown_cost_exposure",
        "cost_exposure_level", "cost_basis", "note_no_financial_posting_flag", "confirmation_status", "source_phase", "advisory_only_flag",
    ]].copy()


def _build_bottleneck_impact(frames: dict[str, pd.DataFrame], availability: pd.DataFrame) -> pd.DataFrame:
    machines = frames["machines"][["machine_id", "workstation_id"]].copy()
    workstations = frames["workstations"][["workstation_id", "workstation_name"]].copy()
    bottleneck = frames["bottleneck"][["workstation_id", "bottleneck_visibility_level"]].copy()
    frame = availability.merge(machines, on="machine_id", how="left").merge(workstations, on="workstation_id", how="left").merge(bottleneck, on="workstation_id", how="left")
    frame["original_bottleneck_visibility_level"] = frame["bottleneck_visibility_level"].fillna("REVIEW_REQUIRED")
    scores = []
    levels = []
    reasons = []
    focus = []
    for row in frame.itertuples():
        score = _risk_points(row.original_bottleneck_visibility_level) + _risk_points(row.breakdown_risk_level) + _risk_points(row.repair_queue_risk_level)
        score += min(float(row.total_downtime_exposure_hours) * 5, 35)
        if row.spare_part_blocker_flag:
            score += 20
        if row.crew_capacity_blocker_flag:
            score += 25
        level = _impact_level(score)
        scores.append(round(score, 2))
        levels.append(level)
        parts = [f"bottleneck={row.original_bottleneck_visibility_level}", f"breakdown={row.breakdown_risk_level}", f"queue={row.repair_queue_risk_level}"]
        if row.spare_part_blocker_flag:
            parts.append("SPARE_PART_BLOCKER")
        if row.crew_capacity_blocker_flag:
            parts.append("CREW_CAPACITY_BLOCKER")
        reasons.append(";".join(parts))
        focus.append("REVIEW_BOTTLENECK_MACHINE_MAINTENANCE" if level in {"HIGH", "CRITICAL"} else "MONITOR_MAINTENANCE_RISK")
    frame["bottleneck_worsening_score"] = scores
    frame["bottleneck_risk_after_maintenance_breakdown"] = levels
    frame["bottleneck_impact_reason"] = reasons
    frame["recommended_manager_focus"] = focus
    frame["confirmation_status"] = CONFIRMATION_STATUS
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[[
        "planning_run_id", "machine_id", "machine_name", "workstation_id", "workstation_name", "original_bottleneck_visibility_level",
        "breakdown_risk_level", "repair_queue_risk_level", "spare_part_blocker_flag", "crew_capacity_blocker_flag",
        "total_downtime_exposure_hours", "bottleneck_worsening_score", "bottleneck_risk_after_maintenance_breakdown",
        "bottleneck_impact_reason", "recommended_manager_focus", "confirmation_status", "source_phase", "advisory_only_flag",
    ]].copy()


def _build_scheduling_candidates(frames: dict[str, pd.DataFrame], availability: pd.DataFrame, capacity: pd.DataFrame, bottleneck: pd.DataFrame) -> pd.DataFrame:
    due = frames["due"].copy()
    cost = frames["cost"].copy()
    plan_master = frames["plans"].copy()
    risk = frames["risk"].copy()
    failure = frames["failure"].copy()
    queue = frames["repair_queue"].copy()
    plan_cols = [
        "maintenance_plan_id", "machine_id", "required_skill_id", "required_crew_type", "required_worker_count",
        "maintenance_level", "required_authorization_level", "estimated_maintenance_duration_hours",
        "planned_downtime_hours", "can_be_performed_by_production_flag", "can_be_performed_by_maintenance_flag",
    ]
    plans = due.drop(columns=[c for c in ["maintenance_level"] if c in due.columns]).merge(
        plan_master[plan_cols], on=["maintenance_plan_id", "machine_id"], how="left"
    )
    plans = plans.merge(
        cost[["maintenance_plan_id", "machine_id", "estimated_maintenance_duration_hours", "planned_downtime_hours", "required_worker_count"]],
        on=["maintenance_plan_id", "machine_id"], how="left", suffixes=("", "_cost")
    )
    for base in ["estimated_maintenance_duration_hours", "planned_downtime_hours", "required_worker_count"]:
        cost_col = f"{base}_cost"
        if cost_col in plans.columns:
            plans[base] = plans[base].where(plans[base].notna(), plans[cost_col])
    plans = plans[plans["due_status"].astype(str).isin(["OVERDUE", "DUE_NOW", "DUE_SOON", "REVIEW_REQUIRED"])].copy()
    cap_map = capacity.set_index("machine_id")["capacity_impact_level"].to_dict()
    bot_map = bottleneck.set_index("machine_id")["bottleneck_risk_after_maintenance_breakdown"].to_dict()
    spare_status = frames["maintenance_spare"].groupby("maintenance_plan_id")["spare_part_readiness_status"].apply(_worst_readiness).to_dict()
    candidates = []
    item = 1
    for row in plans.itertuples():
        due_status = str(row.due_status)
        ctype = "OVERDUE_MAINTENANCE" if due_status == "OVERDUE" else ("DUE_MAINTENANCE" if due_status in {"DUE_NOW", "DUE_SOON"} else "PLANNED_MAINTENANCE")
        machine_risk = risk.loc[risk["machine_id"].astype(str) == str(row.machine_id), "breakdown_risk_level"]
        breakdown_level = machine_risk.iloc[0] if not machine_risk.empty else "REVIEW_REQUIRED"
        spare_ready = spare_status.get(row.maintenance_plan_id, "READY")
        crew_status = "FEASIBLE" if str(row.maintenance_level) == "LIGHT" else "REVIEW_REQUIRED"
        priority = _priority(due_status, breakdown_level, spare_ready, crew_status, cap_map.get(row.machine_id, "LOW"), bot_map.get(row.machine_id, "LOW"))
        completeness = _candidate_completeness(
            getattr(row, "required_skill_id", ""),
            getattr(row, "required_crew_type", ""),
            getattr(row, "required_worker_count", ""),
            getattr(row, "maintenance_level", ""),
            getattr(row, "required_authorization_level", ""),
        )
        blocker = "REVIEW_REQUIRED" if completeness != "COMPLETE" else _blocker_status(spare_ready, crew_status)
        candidates.append(_candidate(
            item, row.machine_id, row.machine_name, ctype, "MAINTENANCE_DUE_STATUS", row.maintenance_plan_id, "",
            getattr(row, "required_skill_id", ""), getattr(row, "required_crew_type", ""),
            getattr(row, "required_worker_count", 0), getattr(row, "maintenance_level", ""),
            getattr(row, "required_authorization_level", ""), getattr(row, "can_be_performed_by_production_flag", False),
            getattr(row, "can_be_performed_by_maintenance_flag", False),
            row.estimated_maintenance_duration_hours, row.planned_downtime_hours, due_status, breakdown_level, spare_ready,
            crew_status, cap_map.get(row.machine_id, "LOW"), bot_map.get(row.machine_id, "LOW"), priority, blocker, completeness,
        ))
        item += 1
    q_by_machine_skill = queue.groupby(["machine_id", "required_skill_id"], as_index=False).agg(crew_capacity_status=("crew_capacity_status", _worst_capacity_status), spare_part_readiness_status=("spare_part_readiness_status", _worst_readiness))
    repair = failure.merge(risk[["machine_id", "breakdown_risk_level"]], on="machine_id", how="left").merge(q_by_machine_skill, on=["machine_id", "required_skill_id"], how="left")
    for row in repair.itertuples():
        ctype = "REPAIR_RISK_REVIEW" if str(row.breakdown_risk_level) in {"HIGH", "CRITICAL", "REVIEW_REQUIRED"} else "BREAKDOWN_RISK_PREVENTIVE_REVIEW"
        spare_ready = getattr(row, "spare_part_readiness_status", "REVIEW_REQUIRED")
        crew_status = getattr(row, "crew_capacity_status", "REVIEW_REQUIRED")
        priority = _priority("BREAKDOWN_RISK", row.breakdown_risk_level, spare_ready, crew_status, cap_map.get(row.machine_id, "LOW"), bot_map.get(row.machine_id, "LOW"))
        blocker = _blocker_status(spare_ready, crew_status)
        candidates.append(_candidate(
            item, row.machine_id, row.machine_name, ctype, "BREAKDOWN_RISK_FORECAST", "", row.failure_mode_id,
            row.required_skill_id, "MAINTENANCE", 1, row.required_maintenance_level, "REPAIR", False, True,
            row.expected_repair_hours, row.expected_downtime_hours, "", row.breakdown_risk_level, spare_ready, crew_status,
            cap_map.get(row.machine_id, "LOW"), bot_map.get(row.machine_id, "LOW"), priority, blocker, "COMPLETE",
        ))
        item += 1
    frame = pd.DataFrame(candidates)
    frame["planning_run_id"] = _planning_run_id()
    frame["schedule_assignment_status"] = "NOT_SCHEDULED_CANDIDATE_ONLY"
    frame["note_no_schedule_created_flag"] = True
    frame["confirmation_status"] = CONFIRMATION_STATUS
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    cols = [
        "planning_run_id", "candidate_id", "machine_id", "machine_name", "candidate_type", "source_signal", "maintenance_plan_id",
        "failure_mode_id", "required_skill_id", "required_crew_type", "required_worker_count", "maintenance_level",
        "required_authorization_level", "can_be_performed_by_production_flag", "can_be_performed_by_maintenance_flag",
        "candidate_requirement_completeness_status", "estimated_duration_hours", "planned_downtime_hours",
        "due_status", "breakdown_risk_level", "spare_part_readiness_status", "crew_capacity_status", "production_impact_level",
        "bottleneck_impact_level", "recommended_scheduling_priority", "scheduling_blocker_status", "earliest_start_placeholder",
        "latest_finish_placeholder", "schedule_assignment_status", "note_no_schedule_created_flag", "confirmation_status", "source_phase", "advisory_only_flag",
    ]
    return frame[cols].copy()


def _build_window_requirements(candidates: pd.DataFrame) -> pd.DataFrame:
    frame = candidates.copy()
    frame["required_downtime_window_hours"] = _num(frame, "planned_downtime_hours").where(_num(frame, "planned_downtime_hours") > 0, _num(frame, "estimated_duration_hours"))
    frame["required_worker_count"] = _num(frame, "required_worker_count").where(_num(frame, "required_worker_count") > 0, 1)
    frame["spare_part_ready_flag"] = frame["spare_part_readiness_status"].astype(str).eq("READY")
    frame["crew_ready_flag"] = frame["crew_capacity_status"].astype(str).eq("FEASIBLE")
    frame["production_bottleneck_sensitive_flag"] = frame["bottleneck_impact_level"].astype(str).isin(["HIGH", "CRITICAL", "REVIEW_REQUIRED"])
    frame["avoid_peak_production_flag"] = frame["production_impact_level"].astype(str).isin(["HIGH", "CRITICAL", "REVIEW_REQUIRED"]) | frame["production_bottleneck_sensitive_flag"]
    frame["preferred_window_basis"] = frame["avoid_peak_production_flag"].map({True: "OFF_PEAK_WINDOW_REQUIRED_BY_PRODUCTION_RISK", False: "STANDARD_MAINTENANCE_WINDOW"})
    frame["window_requirement_status"] = frame.apply(lambda r: "BLOCKED_REVIEW_REQUIRED" if not r["spare_part_ready_flag"] or not r["crew_ready_flag"] else "READY_FOR_STEP7G_REVIEW", axis=1)
    frame["note_no_calendar_assignment_flag"] = True
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[[
        "planning_run_id", "candidate_id", "machine_id", "machine_name", "required_downtime_window_hours", "required_crew_type",
        "required_skill_id", "required_worker_count", "maintenance_level", "required_authorization_level",
        "candidate_requirement_completeness_status", "spare_part_ready_flag", "crew_ready_flag", "production_bottleneck_sensitive_flag",
        "avoid_peak_production_flag", "preferred_window_basis", "window_requirement_status", "note_no_calendar_assignment_flag",
        "source_phase", "advisory_only_flag",
    ]].copy()


def _build_manager_review(availability: pd.DataFrame, capacity: pd.DataFrame, cost: pd.DataFrame, bottleneck: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    item = 1
    cost_map = cost.set_index("machine_id")["cost_exposure_level"].to_dict()
    for row in availability.itertuples():
        if row.machine_availability_impact_level in {"HIGH", "CRITICAL", "REVIEW_REQUIRED"}:
            rows.append(_review(item, row.machine_id, row.machine_name, "MACHINE_AVAILABILITY_IMPACT", row.machine_availability_impact_level, f"{row.machine_name} availability impact is {row.machine_availability_impact_level}.", "REVIEW_MACHINE_AVAILABILITY_RISK")); item += 1
        if row.spare_part_blocker_flag:
            rows.append(_review(item, row.machine_id, row.machine_name, "SPARE_PART_BLOCKER", "HIGH", f"{row.machine_name} has spare-part readiness blockers.", "REVIEW_SPARE_PART_READINESS")); item += 1
        if row.crew_capacity_blocker_flag:
            rows.append(_review(item, row.machine_id, row.machine_name, "CREW_CAPACITY_BLOCKER", "CRITICAL", f"{row.machine_name} has crew capacity blockers.", "REVIEW_MAINTENANCE_CREW_COVERAGE")); item += 1
    for row in capacity.itertuples():
        if row.capacity_impact_level in {"HIGH", "CRITICAL", "REVIEW_REQUIRED"}:
            rows.append(_review(item, row.machine_id, row.machine_name, "PRODUCTION_CAPACITY_IMPACT", row.capacity_impact_level, f"{row.machine_name} has {row.capacity_at_risk_hours} capacity-at-risk hours.", "REVIEW_PRODUCTION_CAPACITY_IMPACT")); item += 1
    for row in bottleneck.itertuples():
        if row.bottleneck_risk_after_maintenance_breakdown in {"HIGH", "CRITICAL", "REVIEW_REQUIRED"}:
            rows.append(_review(item, row.machine_id, row.machine_name, "BOTTLENECK_WORSENING_RISK", row.bottleneck_risk_after_maintenance_breakdown, f"{row.machine_name} may worsen bottleneck risk.", "REVIEW_BOTTLENECK_MACHINE_MAINTENANCE")); item += 1
    for machine_id, level in cost_map.items():
        if level in {"HIGH", "CRITICAL"}:
            name = cost.loc[cost["machine_id"] == machine_id, "machine_name"].iloc[0]
            rows.append(_review(item, machine_id, name, "HIGH_COST_EXPOSURE", level, f"{name} has {level} maintenance/breakdown cost exposure.", "REVIEW_MAINTENANCE_COST_EXPOSURE")); item += 1
    for row in candidates.itertuples():
        if row.scheduling_blocker_status != "READY_FOR_STEP7G":
            rows.append(_review(item, row.machine_id, row.machine_name, "SCHEDULING_CANDIDATE_BLOCKED", "HIGH", f"{row.machine_name} candidate {row.candidate_id} requires review before scheduling.", "REVIEW_BEFORE_STEP7G")); item += 1
        if row.due_status == "OVERDUE" and row.breakdown_risk_level in {"HIGH", "CRITICAL", "REVIEW_REQUIRED"}:
            rows.append(_review(item, row.machine_id, row.machine_name, "OVERDUE_MAINTENANCE_WITH_BREAKDOWN_RISK", "CRITICAL", f"{row.machine_name} is overdue with {row.breakdown_risk_level} breakdown risk.", "REVIEW_OVERDUE_MAINTENANCE")); item += 1
    return pd.DataFrame(rows, columns=["review_item_id", "planning_run_id", "machine_id", "machine_name", "issue_type", "issue_severity", "issue_description", "recommended_review_action", "auto_action_allowed", "advisory_only_flag"])


def _build_phase4_context(availability: pd.DataFrame, capacity: pd.DataFrame, cost: pd.DataFrame, bottleneck: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    candidates = candidates.copy()
    candidates["candidate_ready_for_step7g"] = (
        candidates["scheduling_blocker_status"].astype(str).eq("READY_FOR_STEP7G")
        & candidates["candidate_requirement_completeness_status"].astype(str).eq("COMPLETE")
    )
    cand = candidates.sort_values("recommended_scheduling_priority").groupby("machine_id", as_index=False).agg(
        recommended_scheduling_priority=("recommended_scheduling_priority", "min"),
        scheduling_blocker_status=("scheduling_blocker_status", _worst_blocker),
        candidate_requirement_completeness_status=("candidate_requirement_completeness_status", _worst_completeness),
        step7g_ready_candidate_flag=("candidate_ready_for_step7g", "any"),
    )
    frame = availability[["planning_run_id", "machine_id", "machine_name", "machine_availability_impact_level", "confirmation_status"]].merge(
        capacity[["machine_id", "workstation_id", "workstation_name", "capacity_impact_level"]], on="machine_id", how="left"
    ).merge(
        bottleneck[["machine_id", "bottleneck_risk_after_maintenance_breakdown"]], on="machine_id", how="left"
    ).merge(
        cost[["machine_id", "cost_exposure_level"]], on="machine_id", how="left"
    ).merge(cand, on="machine_id", how="left")
    frame["scheduling_blocker_status"] = frame["scheduling_blocker_status"].fillna("REVIEW_REQUIRED")
    frame["step7g_ready_candidate_flag"] = _to_bool(frame["step7g_ready_candidate_flag"])
    frame["maintenance_impact_planning_ready_flag"] = frame["step7g_ready_candidate_flag"] & ~frame["scheduling_blocker_status"].isin(["SPARE_PART_BLOCKED", "CREW_BLOCKED", "SPARE_AND_CREW_BLOCKED", "REVIEW_REQUIRED"])
    frame["source_phase"] = PHASE4_SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[[
        "planning_run_id", "machine_id", "machine_name", "workstation_id", "workstation_name", "machine_availability_impact_level",
        "capacity_impact_level", "bottleneck_risk_after_maintenance_breakdown", "cost_exposure_level", "recommended_scheduling_priority",
        "scheduling_blocker_status", "candidate_requirement_completeness_status", "maintenance_impact_planning_ready_flag",
        "step7g_ready_candidate_flag", "confirmation_status",
        "source_phase", "advisory_only_flag",
    ]].copy()


def _validate_outputs(availability: pd.DataFrame, capacity: pd.DataFrame, cost: pd.DataFrame, bottleneck: pd.DataFrame, candidates: pd.DataFrame, windows: pd.DataFrame, review: pd.DataFrame, phase4_context: pd.DataFrame, checks: list[dict]) -> None:
    required = {
        "availability": {"machine_id", "total_downtime_exposure_hours", "machine_availability_impact_score", "machine_availability_impact_level", "confirmation_status", "advisory_only_flag"},
        "capacity": {"capacity_at_risk_hours", "estimated_utilization_increase_if_downtime_applied_pct", "note_no_capacity_reduction_applied_flag", "confirmation_status", "advisory_only_flag"},
        "cost": {"total_maintenance_breakdown_cost_exposure", "note_no_financial_posting_flag", "confirmation_status", "advisory_only_flag"},
        "bottleneck": {"bottleneck_worsening_score", "bottleneck_risk_after_maintenance_breakdown", "confirmation_status", "advisory_only_flag"},
        "candidates": {
            "candidate_id", "required_skill_id", "required_crew_type", "required_worker_count", "maintenance_level",
            "required_authorization_level", "can_be_performed_by_production_flag", "can_be_performed_by_maintenance_flag",
            "candidate_requirement_completeness_status", "schedule_assignment_status", "note_no_schedule_created_flag",
            "confirmation_status", "advisory_only_flag",
        },
        "windows": {"candidate_id", "maintenance_level", "required_authorization_level", "candidate_requirement_completeness_status", "note_no_calendar_assignment_flag", "advisory_only_flag"},
        "review": {"auto_action_allowed", "advisory_only_flag"},
        "phase4": {"machine_availability_impact_level", "capacity_impact_level", "candidate_requirement_completeness_status", "confirmation_status", "advisory_only_flag"},
    }
    frames = {"availability": availability, "capacity": capacity, "cost": cost, "bottleneck": bottleneck, "candidates": candidates, "windows": windows, "review": review, "phase4": phase4_context}
    for name, frame in frames.items():
        checks.append(_result(f"maintenance_impact_{name}_not_empty", f"{name} not empty", "FAIL" if frame.empty else "PASS", f"{name} rows: {len(frame)}", int(frame.empty)))
        missing = sorted(required[name].difference(frame.columns))
        checks.append(_result(f"maintenance_impact_{name}_required_columns", f"{name} required columns", "FAIL" if missing else "PASS", f"Missing columns: {missing}" if missing else f"{name} has required columns.", len(missing)))
        if "advisory_only_flag" in frame.columns:
            bad = int((~_to_bool(frame["advisory_only_flag"])).sum())
            checks.append(_result(f"maintenance_impact_{name}_advisory", f"{name} advisory", "FAIL" if bad else "PASS", f"Non-advisory rows: {bad}", bad))
    numeric_checks = [
        (availability, ["planned_maintenance_downtime_hours", "expected_breakdown_downtime_hours", "expected_repair_hours", "total_downtime_exposure_hours", "machine_availability_impact_score"], "availability"),
        (capacity, ["capacity_at_risk_hours", "estimated_utilization_increase_if_downtime_applied_pct"], "capacity"),
        (cost, ["planned_maintenance_cost", "expected_breakdown_repair_cost", "expected_spare_part_exposure_cost", "expected_downtime_cost_exposure", "total_maintenance_breakdown_cost_exposure"], "cost"),
        (bottleneck, ["total_downtime_exposure_hours", "bottleneck_worsening_score"], "bottleneck"),
        (candidates, ["estimated_duration_hours", "planned_downtime_hours", "required_worker_count"], "candidates"),
        (windows, ["required_downtime_window_hours", "required_worker_count"], "windows"),
    ]
    for frame, columns, label in numeric_checks:
        bad = 0
        for col in columns:
            vals = pd.to_numeric(frame[col], errors="coerce")
            bad += int(vals.isna().sum()) + int((vals < 0).sum())
        checks.append(_result(f"maintenance_impact_{label}_numeric", f"{label} numeric non-negative", "FAIL" if bad else "PASS", f"Invalid numeric cells: {bad}", bad))
    checks.append(_result("maintenance_impact_no_capacity_reduction", "no capacity reduction applied", "FAIL" if not _all_true(capacity, "note_no_capacity_reduction_applied_flag") else "PASS", "Capacity impact is advisory-only.", 0 if _all_true(capacity, "note_no_capacity_reduction_applied_flag") else 1))
    checks.append(_result("maintenance_impact_no_financial_posting", "no financial posting", "FAIL" if not _all_true(cost, "note_no_financial_posting_flag") else "PASS", "Cost exposure is advisory-only.", 0 if _all_true(cost, "note_no_financial_posting_flag") else 1))
    checks.append(_result("maintenance_impact_no_schedule_created", "no schedule created", "FAIL" if not _all_true(candidates, "note_no_schedule_created_flag") or set(candidates["schedule_assignment_status"].astype(str)) != {"NOT_SCHEDULED_CANDIDATE_ONLY"} else "PASS", "Scheduling candidates are not scheduled.", 0))
    checks.append(_result("maintenance_impact_no_calendar_assignment", "no calendar assignment", "FAIL" if not _all_true(windows, "note_no_calendar_assignment_flag") else "PASS", "Window requirements do not assign calendar slots.", 0 if _all_true(windows, "note_no_calendar_assignment_flag") else 1))
    confirmation_bad = sum(int((frame["confirmation_status"].astype(str) != CONFIRMATION_STATUS).sum()) for frame in [availability, capacity, cost, bottleneck, candidates, phase4_context] if "confirmation_status" in frame.columns)
    checks.append(_result("maintenance_impact_confirmation_status", "confirmation status", "FAIL" if confirmation_bad else "PASS", f"Invalid confirmation rows: {confirmation_bad}", confirmation_bad))
    review_bad = int(_to_bool(review["auto_action_allowed"]).sum()) if not review.empty else 0
    checks.append(_result("maintenance_impact_review_queue_safe", "review queue safe", "FAIL" if review_bad else "PASS", "Review queue does not allow automatic action.", review_bad))
    plan_types = {"PLANNED_MAINTENANCE", "DUE_MAINTENANCE", "OVERDUE_MAINTENANCE"}
    plan_candidates = candidates[candidates["candidate_type"].astype(str).isin(plan_types)]
    missing_required = 0
    for col in ["required_skill_id", "required_crew_type", "maintenance_level", "required_authorization_level"]:
        missing_required += int(plan_candidates[col].apply(_is_blank).sum())
    missing_required += int((_num(plan_candidates, "required_worker_count") <= 0).sum())
    checks.append(_result("maintenance_impact_plan_candidate_requirements_complete", "maintenance-plan candidate requirements complete", "FAIL" if missing_required else "PASS", f"Missing required candidate fields: {missing_required}", missing_required))
    ready_incomplete = candidates[
        (candidates["scheduling_blocker_status"].astype(str) == "READY_FOR_STEP7G")
        & (candidates["candidate_requirement_completeness_status"].astype(str) != "COMPLETE")
    ]
    checks.append(_result("maintenance_impact_ready_candidates_complete", "Step 7G-ready candidates complete", "FAIL" if not ready_incomplete.empty else "PASS", "Step 7G-ready candidates have complete requirements.", len(ready_incomplete)))
    invalid_completeness = set(candidates["candidate_requirement_completeness_status"].dropna().astype(str)) - {"COMPLETE", "INCOMPLETE_REVIEW_REQUIRED"}
    checks.append(_result("maintenance_impact_candidate_completeness_values", "candidate completeness values valid", "FAIL" if invalid_completeness else "PASS", f"Invalid values: {sorted(invalid_completeness)}" if invalid_completeness else "Candidate completeness values are valid.", len(invalid_completeness)))


def _check_existing_validations(checks: list[dict]) -> None:
    for path, label in [
        (WORKFORCE_VALIDATION_FILE, "workforce"),
        (SPARE_VALIDATION_FILE, "spare-part"),
        (MAINTENANCE_VALIDATION_FILE, "maintenance"),
        (BREAKDOWN_VALIDATION_FILE, "breakdown"),
        (CREW_CAPACITY_VALIDATION_FILE, "maintenance crew capacity"),
    ]:
        if not path.exists():
            checks.append(_result(f"maintenance_impact_existing_{label}_validation", f"existing {label} validation", "FAIL", f"Missing {path}", 1))
            continue
        frame = pd.read_csv(path)
        fail_count = int((frame["status"].astype(str).str.upper() == "FAIL").sum()) if "status" in frame.columns else len(frame)
        checks.append(_result(f"maintenance_impact_existing_{label}_validation", f"existing {label} validation", "FAIL" if fail_count else "PASS", f"{label} validation FAIL rows: {fail_count}", fail_count))


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked = ["maintenance_work_order", "maintenance_schedule", "crew_dispatch", "production_order", "purchase_order", "inventory_reservation", "spare_part_consumption", "capacity_reduction", "simulation"]
    bad = []
    for folder in [SHARED_OUTPUT_DIR, PHASE4_OUTPUT_DIR]:
        if folder.exists():
            for path in folder.glob("*"):
                if path.is_file() and any(token in path.name.lower() for token in blocked):
                    bad.append(str(path))
    checks.append(_result("maintenance_impact_no_blocked_outputs", "no blocked execution outputs", "FAIL" if bad else "PASS", f"Blocked outputs found: {bad}" if bad else "No scheduling, work-order, dispatch, reservation, consumption, reduction, or simulation outputs found.", len(bad)))


def _candidate(
    item: int,
    machine_id: str,
    machine_name: str,
    candidate_type: str,
    source_signal: str,
    plan_id: str,
    failure_mode_id: str,
    skill_id: str,
    crew_type: str,
    worker_count: float,
    maintenance_level: str,
    auth_level: str,
    can_production: bool,
    can_maintenance: bool,
    duration: float,
    downtime: float,
    due_status: str,
    breakdown_level: str,
    spare_status: str,
    crew_status: str,
    production_level: str,
    bottleneck_level: str,
    priority: int,
    blocker: str,
    completeness: str,
) -> dict:
    return {
        "candidate_id": f"MAINT-CAND-{item:03d}",
        "machine_id": machine_id,
        "machine_name": machine_name,
        "candidate_type": candidate_type,
        "source_signal": source_signal,
        "maintenance_plan_id": plan_id,
        "failure_mode_id": failure_mode_id,
        "required_skill_id": skill_id,
        "required_crew_type": crew_type,
        "required_worker_count": round(float(worker_count or 0), 2),
        "maintenance_level": maintenance_level,
        "required_authorization_level": auth_level,
        "can_be_performed_by_production_flag": _bool_value(can_production),
        "can_be_performed_by_maintenance_flag": _bool_value(can_maintenance),
        "candidate_requirement_completeness_status": completeness,
        "estimated_duration_hours": round(float(duration or 0), 2),
        "planned_downtime_hours": round(float(downtime or 0), 2),
        "due_status": due_status,
        "breakdown_risk_level": breakdown_level,
        "spare_part_readiness_status": spare_status,
        "crew_capacity_status": crew_status,
        "production_impact_level": production_level,
        "bottleneck_impact_level": bottleneck_level,
        "recommended_scheduling_priority": priority,
        "scheduling_blocker_status": blocker,
        "earliest_start_placeholder": "STEP7G_TO_ASSIGN",
        "latest_finish_placeholder": "STEP7G_TO_ASSIGN",
    }


def _review(item: int, machine_id: str, machine_name: str, issue_type: str, severity: str, description: str, action: str) -> dict:
    return {
        "review_item_id": f"MAINT-IMPACT-REV-{item:03d}",
        "planning_run_id": _planning_run_id(),
        "machine_id": machine_id,
        "machine_name": machine_name,
        "issue_type": issue_type,
        "issue_severity": severity,
        "issue_description": description,
        "recommended_review_action": action,
        "auto_action_allowed": False,
        "advisory_only_flag": True,
    }


def _priority(due_status: str, breakdown_level: str, spare_status: str, crew_status: str, production_level: str, bottleneck_level: str) -> int:
    score = 100
    if due_status == "OVERDUE":
        score -= 40
    elif due_status in {"DUE_NOW", "DUE_SOON"}:
        score -= 25
    score -= _risk_points(breakdown_level)
    score -= _risk_points(production_level) // 2
    score -= _risk_points(bottleneck_level) // 2
    if spare_status != "READY":
        score += 20
    if crew_status in {"NO_ACTIVE_COVERAGE", "REVIEW_REQUIRED", "OVERLOADED"}:
        score += 20
    return max(1, min(999, int(score)))


def _candidate_completeness(skill_id: object, crew_type: object, worker_count: object, maintenance_level: object, auth_level: object) -> str:
    required = [skill_id, crew_type, maintenance_level, auth_level]
    if any(_is_blank(value) for value in required):
        return "INCOMPLETE_REVIEW_REQUIRED"
    worker = pd.to_numeric(pd.Series([worker_count]), errors="coerce").fillna(0).iloc[0]
    return "COMPLETE" if worker > 0 else "INCOMPLETE_REVIEW_REQUIRED"


def _blocker_status(spare_status: str, crew_status: str) -> str:
    spare_block = str(spare_status) != "READY"
    crew_block = str(crew_status) in {"NO_ACTIVE_COVERAGE", "REVIEW_REQUIRED", "OVERLOADED"}
    if spare_block and crew_block:
        return "SPARE_AND_CREW_BLOCKED"
    if spare_block:
        return "SPARE_PART_BLOCKED"
    if crew_block:
        return "CREW_BLOCKED"
    return "READY_FOR_STEP7G"


def _is_blank(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "nat"}


def _bool_value(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _capacity_impact_level(row: pd.Series) -> str:
    if row["current_capacity_status"] in {"NO_CAPACITY_RECORD", "REVIEW_REQUIRED"}:
        return "REVIEW_REQUIRED"
    if row["estimated_utilization_increase_if_downtime_applied_pct"] >= 20 or row["quality_adjusted_utilization_pct"] >= 200:
        return "CRITICAL"
    if row["estimated_utilization_increase_if_downtime_applied_pct"] >= 10 or row["current_capacity_status"] == "OVERLOADED":
        return "HIGH"
    if row["estimated_utilization_increase_if_downtime_applied_pct"] > 0:
        return "MEDIUM"
    return "LOW"


def _impact_level(score: float) -> str:
    if score >= 120:
        return "CRITICAL"
    if score >= 80:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def _due_factor(status: str) -> float:
    return {"OVERDUE": 1.0, "DUE_NOW": 1.0, "DUE_SOON": 0.5, "REVIEW_REQUIRED": 0.25}.get(str(status), 0.0)


def _risk_points(level: str) -> int:
    return {"LOW": 5, "MEDIUM": 20, "HIGH": 35, "CRITICAL": 55, "REVIEW_REQUIRED": 60}.get(str(level), 10)


def _worst_due(values: pd.Series) -> str:
    order = {"NOT_DUE": 0, "DUE_SOON": 1, "DUE_NOW": 2, "OVERDUE": 3, "REVIEW_REQUIRED": 4}
    vals = [str(v) for v in values.dropna()]
    return max(vals, key=lambda v: order.get(v, 0)) if vals else "REVIEW_REQUIRED"


def _highest_level(values: pd.Series) -> str:
    vals = [str(v) for v in values.dropna()]
    return max(vals, key=lambda v: RISK_ORDER.get(v, 0)) if vals else "REVIEW_REQUIRED"


def _worst_readiness(values: pd.Series) -> str:
    vals = [str(v) for v in values.dropna()]
    if not vals:
        return "REVIEW_REQUIRED"
    if "REVIEW_REQUIRED" in vals:
        return "REVIEW_REQUIRED"
    return "READY" if all(v == "READY" for v in vals) else vals[0]


def _worst_capacity_status(values: pd.Series) -> str:
    order = {"NO_LOAD": 0, "FEASIBLE": 1, "HIGH_UTILIZATION_WARNING": 2, "NEAR_CAPACITY": 2, "OVERLOADED": 3, "NO_ACTIVE_COVERAGE": 4, "NO_CAPACITY_RECORD": 4, "REVIEW_REQUIRED": 5}
    vals = [str(v) for v in values.dropna()]
    return max(vals, key=lambda v: order.get(v, 0)) if vals else "REVIEW_REQUIRED"


def _worst_blocker(values: pd.Series) -> str:
    order = {"READY_FOR_STEP7G": 0, "SPARE_PART_BLOCKED": 1, "CREW_BLOCKED": 2, "SPARE_AND_CREW_BLOCKED": 3, "REVIEW_REQUIRED": 4}
    vals = [str(v) for v in values.dropna()]
    return max(vals, key=lambda v: order.get(v, 0)) if vals else "REVIEW_REQUIRED"


def _worst_completeness(values: pd.Series) -> str:
    vals = [str(v) for v in values.dropna()]
    return "INCOMPLETE_REVIEW_REQUIRED" if any(v != "COMPLETE" for v in vals) else "COMPLETE"


def _planning_run_id() -> str:
    return os.environ.get("INTEGRATED_RUN_ID") or _existing_run_id() or f"PHASE4-MPS-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


def _existing_run_id() -> str | None:
    path = PHASE4_OUTPUT_DIR / "phase4_master_production_schedule.csv"
    if path.exists():
        try:
            frame = pd.read_csv(path, usecols=["planning_run_id"])
            vals = frame["planning_run_id"].dropna().astype(str).str.strip()
            if not vals.empty:
                return vals.iloc[0]
        except Exception:
            return None
    return None


def _load_csv(path: Path, label: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"maintenance_impact_input_{label}", f"{label} input exists", "FAIL", f"Missing {path}", 1))
        return None
    frame = pd.read_csv(path)
    checks.append(_result(f"maintenance_impact_input_{label}", f"{label} input exists", "FAIL" if frame.empty else "PASS", f"{label} rows: {len(frame)}", int(frame.empty)))
    return frame


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").fillna(0) if column in frame.columns else pd.Series(0.0, index=frame.index)


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _all_true(frame: pd.DataFrame, column: str) -> bool:
    return column in frame.columns and bool(_to_bool(frame[column]).all())


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
    validation, *_ = build_maintenance_production_impact_outputs()
    print(f"Maintenance production impact validation rows: {len(validation)}")
    print(f"Validation status counts: {validation['status'].value_counts().to_dict()}")
