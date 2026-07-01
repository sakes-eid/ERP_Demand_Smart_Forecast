"""Build advisory maintenance schedule feasibility candidates for Step 7G."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHARED_DATA_DIR = PROJECT_ROOT / "shared" / "data"
SHARED_OUTPUT_DIR = PROJECT_ROOT / "shared" / "outputs"
PHASE4_OUTPUT_DIR = PROJECT_ROOT / "phase 4" / "outputs"

CANDIDATE_BACKLOG_FILE = SHARED_OUTPUT_DIR / "maintenance_scheduling_candidate_backlog.csv"
WINDOW_REQUIREMENTS_FILE = SHARED_OUTPUT_DIR / "maintenance_window_requirements.csv"
CREW_CAPACITY_FILE = SHARED_OUTPUT_DIR / "maintenance_crew_capacity_summary.csv"
WORKLOAD_BY_SKILL_FILE = SHARED_OUTPUT_DIR / "maintenance_workload_by_skill.csv"
REPAIR_QUEUE_FILE = SHARED_OUTPUT_DIR / "maintenance_repair_queue_risk.csv"
PRODUCTION_CAPACITY_IMPACT_FILE = SHARED_OUTPUT_DIR / "maintenance_production_capacity_impact.csv"
BOTTLENECK_IMPACT_FILE = SHARED_OUTPUT_DIR / "maintenance_bottleneck_impact.csv"
MACHINE_AVAILABILITY_FILE = SHARED_OUTPUT_DIR / "maintenance_machine_availability_impact.csv"
SPARE_PHASE_CONTEXT_FILE = SHARED_OUTPUT_DIR / "spare_part_phase_integration_context.csv"
CREW_CALENDAR_FILE = SHARED_DATA_DIR / "crew_calendar.csv"
WORKFORCE_CREWS_FILE = SHARED_DATA_DIR / "workforce_crews.csv"
PHASE4_MAINTENANCE_IMPACT_CONTEXT_FILE = PHASE4_OUTPUT_DIR / "phase4_maintenance_production_impact_context.csv"
CAPACITY_FEASIBILITY_FILE = PHASE4_OUTPUT_DIR / "phase4_capacity_feasibility_summary.csv"
BOTTLENECK_VISIBILITY_FILE = PHASE4_OUTPUT_DIR / "phase4_bottleneck_visibility_summary.csv"
PRODUCTION_FLOW_FILE = PHASE4_OUTPUT_DIR / "phase4_production_flow_view.csv"

WORKFORCE_VALIDATION_FILE = SHARED_OUTPUT_DIR / "workforce_crew_validation.csv"
SPARE_VALIDATION_FILE = SHARED_OUTPUT_DIR / "spare_part_validation.csv"
MAINTENANCE_VALIDATION_FILE = SHARED_OUTPUT_DIR / "maintenance_plan_validation.csv"
BREAKDOWN_VALIDATION_FILE = SHARED_OUTPUT_DIR / "breakdown_validation.csv"
CREW_CAPACITY_VALIDATION_FILE = SHARED_OUTPUT_DIR / "maintenance_crew_capacity_validation.csv"
MAINTENANCE_IMPACT_VALIDATION_FILE = SHARED_OUTPUT_DIR / "maintenance_production_impact_validation.csv"

SCHEDULE_CANDIDATE_WINDOWS_FILE = SHARED_OUTPUT_DIR / "maintenance_schedule_candidate_windows.csv"
CALENDAR_FEASIBILITY_FILE = SHARED_OUTPUT_DIR / "maintenance_calendar_feasibility.csv"
CREW_WINDOW_LOAD_FILE = SHARED_OUTPUT_DIR / "maintenance_crew_window_load.csv"
MACHINE_WINDOW_IMPACT_FILE = SHARED_OUTPUT_DIR / "maintenance_machine_window_impact.csv"
MANAGER_REVIEW_FILE = SHARED_OUTPUT_DIR / "maintenance_schedule_manager_review_queue.csv"
VALIDATION_OUTPUT_FILE = SHARED_OUTPUT_DIR / "maintenance_schedule_validation.csv"
PHASE4_CONTEXT_FILE = PHASE4_OUTPUT_DIR / "phase4_maintenance_schedule_feasibility_context.csv"

SOURCE_PHASE = "SHARED_STEP7G_MAINTENANCE_SCHEDULE_FEASIBILITY"
PHASE4_SOURCE_PHASE = "PHASE4_STEP7G_MAINTENANCE_SCHEDULE_FEASIBILITY_CONTEXT"
CONFIRMATION_STATUS = "ADVISORY_SCHEDULE_FEASIBILITY_ONLY_NOT_EXECUTION_CONFIRMED"

VALID_FEASIBILITY = {
    "FEASIBLE_CANDIDATE",
    "BLOCKED_BY_CREW",
    "BLOCKED_BY_SPARE_PART",
    "BLOCKED_BY_PRODUCTION_IMPACT",
    "MULTI_BLOCKED",
    "REVIEW_REQUIRED",
}
VALID_CREW_WINDOW_STATUS = {"AVAILABLE", "HIGH_UTILIZATION_WARNING", "OVERLOADED", "NO_ACTIVE_COVERAGE", "REVIEW_REQUIRED"}
VALID_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "REVIEW_REQUIRED"}
PRIORITY_POINTS = {"LOW": 10, "MEDIUM": 30, "HIGH": 60, "CRITICAL": 90, "REVIEW_REQUIRED": 75}
LEVEL_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4, "REVIEW_REQUIRED": 5}


def build_maintenance_schedule_feasibility_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    checks: list[dict] = []
    frames = {
        "candidates": _load_csv(CANDIDATE_BACKLOG_FILE, "maintenance_scheduling_candidate_backlog", checks),
        "windows": _load_csv(WINDOW_REQUIREMENTS_FILE, "maintenance_window_requirements", checks),
        "crew_capacity": _load_csv(CREW_CAPACITY_FILE, "maintenance_crew_capacity_summary", checks),
        "workload": _load_csv(WORKLOAD_BY_SKILL_FILE, "maintenance_workload_by_skill", checks),
        "repair_queue": _load_csv(REPAIR_QUEUE_FILE, "maintenance_repair_queue_risk", checks),
        "production_capacity": _load_csv(PRODUCTION_CAPACITY_IMPACT_FILE, "maintenance_production_capacity_impact", checks),
        "bottleneck_impact": _load_csv(BOTTLENECK_IMPACT_FILE, "maintenance_bottleneck_impact", checks),
        "availability": _load_csv(MACHINE_AVAILABILITY_FILE, "maintenance_machine_availability_impact", checks),
        "spare_phase": _load_csv(SPARE_PHASE_CONTEXT_FILE, "spare_part_phase_integration_context", checks),
        "crew_calendar": _load_csv(CREW_CALENDAR_FILE, "crew_calendar", checks),
        "crews": _load_csv(WORKFORCE_CREWS_FILE, "workforce_crews", checks),
        "phase4_impact": _load_csv(PHASE4_MAINTENANCE_IMPACT_CONTEXT_FILE, "phase4_maintenance_production_impact_context", checks),
        "capacity_feasibility": _load_csv(CAPACITY_FEASIBILITY_FILE, "phase4_capacity_feasibility_summary", checks),
        "bottleneck_visibility": _load_csv(BOTTLENECK_VISIBILITY_FILE, "phase4_bottleneck_visibility_summary", checks),
        "flow": _load_csv(PRODUCTION_FLOW_FILE, "phase4_production_flow_view", checks),
    }
    if all(frame is not None for frame in frames.values()):
        candidate_windows = _build_candidate_windows(frames)
        calendar = _build_calendar_feasibility(candidate_windows)
        crew_load = _build_crew_window_load(candidate_windows, frames)
        machine_impact = _build_machine_window_impact(candidate_windows, frames)
        review = _build_manager_review(candidate_windows, crew_load, machine_impact)
        phase4_context = _build_phase4_context(candidate_windows)
        _validate_outputs(candidate_windows, calendar, crew_load, machine_impact, review, phase4_context, checks)
    else:
        candidate_windows = calendar = crew_load = machine_impact = review = phase4_context = pd.DataFrame()
    _check_existing_validations(checks)
    _check_no_forbidden_outputs(checks)

    SHARED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PHASE4_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    candidate_windows.to_csv(SCHEDULE_CANDIDATE_WINDOWS_FILE, index=False)
    calendar.to_csv(CALENDAR_FEASIBILITY_FILE, index=False)
    crew_load.to_csv(CREW_WINDOW_LOAD_FILE, index=False)
    machine_impact.to_csv(MACHINE_WINDOW_IMPACT_FILE, index=False)
    review.to_csv(MANAGER_REVIEW_FILE, index=False)
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    phase4_context.to_csv(PHASE4_CONTEXT_FILE, index=False)
    return validation, candidate_windows, calendar, crew_load, machine_impact, review, phase4_context


def _build_candidate_windows(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    candidates = frames["candidates"].copy()
    window_req = frames["windows"].copy()
    workload = frames["workload"].copy()
    calendars = _calendar_capacity(frames["crew_calendar"], frames["crews"])
    prod = frames["production_capacity"][["machine_id", "capacity_impact_level", "production_capacity_review_required_flag"]].copy()
    bottleneck = frames["bottleneck_impact"][["machine_id", "bottleneck_risk_after_maintenance_breakdown"]].copy()
    availability = frames["availability"][["machine_id", "machine_availability_impact_level"]].copy()

    candidates = candidates.merge(
        window_req[[
            "candidate_id", "spare_part_ready_flag", "crew_ready_flag", "production_bottleneck_sensitive_flag",
            "avoid_peak_production_flag", "window_requirement_status",
        ]],
        on="candidate_id",
        how="left",
    )
    candidates = candidates.merge(prod, on="machine_id", how="left").merge(bottleneck, on="machine_id", how="left").merge(availability, on="machine_id", how="left")
    workload_key = workload[["required_skill_id", "maintenance_level", "capacity_status", "available_crew_hours", "skill_coverage_status"]].copy()
    candidates = candidates.merge(workload_key, on=["required_skill_id", "maintenance_level"], how="left")

    rows = []
    for cand in candidates.itertuples(index=False):
        possible = calendars[calendars["crew_type"].astype(str) == str(cand.required_crew_type)]
        if possible.empty:
            possible = pd.DataFrame([{
                "candidate_window_day": "NO_AVAILABLE_CALENDAR",
                "candidate_window_shift": "NO_SHIFT",
                "available_crew_hours": 0.0,
            }])
        for win_idx, win in possible.reset_index(drop=True).iterrows():
            required_hours = float(_safe_number(cand.estimated_duration_hours)) * max(float(_safe_number(cand.required_worker_count)), 1.0)
            available_hours = float(_safe_number(win.get("available_crew_hours", 0.0)))
            skill_hours = float(_safe_number(getattr(cand, "available_crew_hours", 0.0)))
            crew_capacity_available = bool(available_hours >= required_hours and skill_hours >= required_hours and str(getattr(cand, "crew_capacity_status", "")) not in {"NO_ACTIVE_COVERAGE", "REVIEW_REQUIRED", "OVERLOADED"})
            spare_ready = _to_bool(getattr(cand, "spare_part_ready_flag", False)) and str(getattr(cand, "spare_part_readiness_status", "")) == "READY"
            prod_sensitive = _to_bool(getattr(cand, "production_bottleneck_sensitive_flag", False)) and _level_rank(getattr(cand, "production_impact_level", "LOW")) >= _level_rank("CRITICAL")
            complete = str(getattr(cand, "candidate_requirement_completeness_status", "")) == "COMPLETE"
            blockers = []
            if not complete:
                blockers.append("REVIEW_REQUIRED")
            if not crew_capacity_available:
                blockers.append("CREW")
            if not spare_ready:
                blockers.append("SPARE_PART")
            if prod_sensitive:
                blockers.append("PRODUCTION_IMPACT")
            status = _feasibility_status(blockers)
            priority_score = _priority_score(cand, status, prod_sensitive)
            rows.append({
                "planning_run_id": cand.planning_run_id,
                "schedule_candidate_window_id": f"SCHED-WIN-{len(rows)+1:03d}",
                "candidate_id": cand.candidate_id,
                "machine_id": cand.machine_id,
                "machine_name": cand.machine_name,
                "candidate_type": cand.candidate_type,
                "maintenance_plan_id": getattr(cand, "maintenance_plan_id", ""),
                "required_skill_id": cand.required_skill_id,
                "required_crew_type": cand.required_crew_type,
                "required_worker_count": _safe_number(cand.required_worker_count),
                "maintenance_level": cand.maintenance_level,
                "estimated_duration_hours": _safe_number(cand.estimated_duration_hours),
                "planned_downtime_hours": _safe_number(cand.planned_downtime_hours),
                "candidate_window_period": "STEP7G_WEEKLY_FEASIBILITY_PERIOD",
                "candidate_window_day": win.get("candidate_window_day", "REVIEW_REQUIRED"),
                "candidate_window_shift": win.get("candidate_window_shift", "REVIEW_REQUIRED"),
                "crew_capacity_available_flag": crew_capacity_available,
                "spare_part_ready_flag": spare_ready,
                "production_bottleneck_sensitive_flag": prod_sensitive,
                "schedule_feasibility_status": status,
                "schedule_feasibility_reason": _feasibility_reason(blockers, complete),
                "scheduling_priority_score": priority_score,
                "recommended_scheduling_priority": _priority_label(priority_score),
                "schedule_assignment_status": "NOT_SCHEDULED_CANDIDATE_ONLY",
                "note_no_schedule_created_flag": True,
                "source_phase": SOURCE_PHASE,
                "advisory_only_flag": True,
            })
    return pd.DataFrame(rows)


def _build_calendar_feasibility(candidate_windows: pd.DataFrame) -> pd.DataFrame:
    grouped = candidate_windows.groupby(["planning_run_id", "candidate_window_period", "candidate_window_day", "candidate_window_shift"], as_index=False).agg(
        feasible_candidate_count=("schedule_feasibility_status", lambda s: int((s == "FEASIBLE_CANDIDATE").sum())),
        blocked_candidate_count=("schedule_feasibility_status", lambda s: int((s != "FEASIBLE_CANDIDATE").sum())),
        crew_blocked_count=("schedule_feasibility_status", lambda s: int(s.isin(["BLOCKED_BY_CREW", "MULTI_BLOCKED"]).sum())),
        spare_part_blocked_count=("schedule_feasibility_status", lambda s: int(s.isin(["BLOCKED_BY_SPARE_PART", "MULTI_BLOCKED"]).sum())),
        production_impact_blocked_count=("schedule_feasibility_status", lambda s: int(s.isin(["BLOCKED_BY_PRODUCTION_IMPACT", "MULTI_BLOCKED"]).sum())),
        max_priority=("scheduling_priority_score", "max"),
    )
    highest = candidate_windows.sort_values(["candidate_window_period", "candidate_window_day", "candidate_window_shift", "scheduling_priority_score"], ascending=[True, True, True, False]).drop_duplicates(["planning_run_id", "candidate_window_period", "candidate_window_day", "candidate_window_shift"])
    grouped = grouped.merge(highest[["planning_run_id", "candidate_window_period", "candidate_window_day", "candidate_window_shift", "candidate_id"]].rename(columns={"candidate_id": "highest_priority_candidate_id"}), on=["planning_run_id", "candidate_window_period", "candidate_window_day", "candidate_window_shift"], how="left")
    grouped["calendar_feasibility_status"] = grouped.apply(lambda r: "HAS_FEASIBLE_CANDIDATES" if r["feasible_candidate_count"] > 0 else "ALL_CANDIDATES_BLOCKED", axis=1)
    grouped["calendar_feasibility_reason"] = grouped.apply(lambda r: f"feasible={r.feasible_candidate_count};blocked={r.blocked_candidate_count};crew_blocked={r.crew_blocked_count};spare_blocked={r.spare_part_blocked_count};production_blocked={r.production_impact_blocked_count}", axis=1)
    grouped["source_phase"] = SOURCE_PHASE
    grouped["advisory_only_flag"] = True
    return grouped[[
        "planning_run_id", "candidate_window_period", "candidate_window_day", "candidate_window_shift",
        "feasible_candidate_count", "blocked_candidate_count", "crew_blocked_count", "spare_part_blocked_count",
        "production_impact_blocked_count", "highest_priority_candidate_id", "calendar_feasibility_status",
        "calendar_feasibility_reason", "source_phase", "advisory_only_flag",
    ]]


def _build_crew_window_load(candidate_windows: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    calendar_capacity = _calendar_capacity(frames["crew_calendar"], frames["crews"])
    load = candidate_windows.copy()
    load["candidate_required_hours"] = _num(load, "estimated_duration_hours") * _num(load, "required_worker_count").clip(lower=1)
    grouped = load.groupby(["planning_run_id", "candidate_window_period", "candidate_window_day", "candidate_window_shift", "required_crew_type", "required_skill_id"], as_index=False).agg(candidate_required_hours=("candidate_required_hours", "sum"))
    grouped = grouped.merge(calendar_capacity, left_on=["candidate_window_day", "candidate_window_shift", "required_crew_type"], right_on=["candidate_window_day", "candidate_window_shift", "crew_type"], how="left")
    grouped["available_crew_hours"] = _num(grouped, "available_crew_hours")
    grouped["remaining_crew_hours"] = (grouped["available_crew_hours"] - grouped["candidate_required_hours"]).round(2)
    grouped["crew_window_utilization_pct"] = grouped.apply(lambda r: round(r["candidate_required_hours"] / r["available_crew_hours"] * 100, 2) if r["available_crew_hours"] > 0 else 0.0, axis=1)
    grouped["crew_window_status"] = grouped.apply(_crew_window_status, axis=1)
    grouped["double_booking_risk_flag"] = grouped["remaining_crew_hours"] < 0
    grouped["note_no_dispatch_created_flag"] = True
    grouped["source_phase"] = SOURCE_PHASE
    grouped["advisory_only_flag"] = True
    return grouped[[
        "planning_run_id", "candidate_window_period", "candidate_window_day", "candidate_window_shift", "required_crew_type",
        "required_skill_id", "available_crew_hours", "candidate_required_hours", "remaining_crew_hours",
        "crew_window_utilization_pct", "crew_window_status", "double_booking_risk_flag",
        "note_no_dispatch_created_flag", "source_phase", "advisory_only_flag",
    ]]


def _build_machine_window_impact(candidate_windows: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    capacity = frames["production_capacity"][["machine_id", "workstation_id", "workstation_name", "capacity_at_risk_hours", "capacity_impact_level"]].copy()
    bottleneck = frames["bottleneck_impact"][["machine_id", "bottleneck_risk_after_maintenance_breakdown"]].copy()
    availability = frames["availability"][["machine_id", "machine_availability_impact_level"]].copy()
    frame = candidate_windows.merge(capacity, on="machine_id", how="left").merge(bottleneck, on="machine_id", how="left").merge(availability, on="machine_id", how="left")
    frame["production_impact_level"] = frame["capacity_impact_level"].fillna("REVIEW_REQUIRED")
    frame["bottleneck_impact_level"] = frame["bottleneck_risk_after_maintenance_breakdown"].fillna("REVIEW_REQUIRED")
    frame["machine_availability_impact_level"] = frame["machine_availability_impact_level"].fillna("REVIEW_REQUIRED")
    frame["estimated_capacity_at_risk_hours"] = _num(frame, "capacity_at_risk_hours")
    frame["window_impact_level"] = frame.apply(lambda r: _highest_level([r["production_impact_level"], r["bottleneck_impact_level"], r["machine_availability_impact_level"]]), axis=1)
    frame["note_no_capacity_reduction_applied_flag"] = True
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[[
        "planning_run_id", "schedule_candidate_window_id", "candidate_id", "machine_id", "machine_name", "workstation_id",
        "workstation_name", "planned_downtime_hours", "production_impact_level", "bottleneck_impact_level",
        "machine_availability_impact_level", "estimated_capacity_at_risk_hours", "window_impact_level",
        "note_no_capacity_reduction_applied_flag", "source_phase", "advisory_only_flag",
    ]]


def _build_manager_review(candidate_windows: pd.DataFrame, crew_load: pd.DataFrame, machine_impact: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in candidate_windows.itertuples(index=False):
        issue_type = None
        if row.schedule_feasibility_status in {"BLOCKED_BY_CREW", "MULTI_BLOCKED", "REVIEW_REQUIRED"}:
            issue_type = "CREW_BLOCKED_SCHEDULE_CANDIDATE"
        elif row.schedule_feasibility_status == "BLOCKED_BY_SPARE_PART":
            issue_type = "SPARE_PART_BLOCKED_SCHEDULE_CANDIDATE"
        elif row.schedule_feasibility_status == "BLOCKED_BY_PRODUCTION_IMPACT":
            issue_type = "PRODUCTION_IMPACT_BLOCKED_CANDIDATE"
        elif row.recommended_scheduling_priority in {"HIGH", "CRITICAL"}:
            issue_type = "HIGH_PRIORITY_SCHEDULING_REVIEW"
        if issue_type:
            severity = "CRITICAL" if row.recommended_scheduling_priority == "CRITICAL" else "HIGH"
            rows.append(_review_row(len(rows) + 1, row.planning_run_id, row.candidate_id, row.schedule_candidate_window_id, row.machine_id, issue_type, severity, f"{row.candidate_id} status={row.schedule_feasibility_status}; priority={row.recommended_scheduling_priority}", _review_action(issue_type)))
    for row in crew_load[crew_load["crew_window_status"].isin(["OVERLOADED", "NO_ACTIVE_COVERAGE", "REVIEW_REQUIRED"])].itertuples(index=False):
        issue_type = "NO_ACTIVE_CREW_COVERAGE" if row.crew_window_status == "NO_ACTIVE_COVERAGE" else "CREW_WINDOW_OVERLOAD"
        rows.append(_review_row(len(rows) + 1, row.planning_run_id, "", "", "", issue_type, "CRITICAL", f"{row.required_crew_type}/{row.required_skill_id} window status={row.crew_window_status}", "REVIEW_CREW_WINDOW_CAPACITY"))
    for row in machine_impact[machine_impact["window_impact_level"].isin(["HIGH", "CRITICAL", "REVIEW_REQUIRED"])].itertuples(index=False):
        rows.append(_review_row(len(rows) + 1, row.planning_run_id, row.candidate_id, row.schedule_candidate_window_id, row.machine_id, "PRODUCTION_IMPACT_BLOCKED_CANDIDATE", "HIGH", f"{row.machine_id} window impact={row.window_impact_level}", "REVIEW_PRODUCTION_IMPACT_BEFORE_SCHEDULING"))
    return pd.DataFrame(rows).drop_duplicates(subset=["planning_run_id", "candidate_id", "schedule_candidate_window_id", "issue_type"], keep="first")


def _build_phase4_context(candidate_windows: pd.DataFrame) -> pd.DataFrame:
    grouped = candidate_windows.groupby(["planning_run_id", "machine_id", "machine_name"], as_index=False).agg(
        feasible_candidate_window_count=("schedule_feasibility_status", lambda s: int((s == "FEASIBLE_CANDIDATE").sum())),
        blocked_candidate_window_count=("schedule_feasibility_status", lambda s: int((s != "FEASIBLE_CANDIDATE").sum())),
        highest_score=("scheduling_priority_score", "max"),
        best_schedule_feasibility_status=("schedule_feasibility_status", _best_feasibility),
        main_schedule_blocker=("schedule_feasibility_status", _main_blocker),
    )
    grouped["highest_recommended_scheduling_priority"] = grouped["highest_score"].apply(_priority_label)
    grouped["scheduling_feasibility_ready_flag"] = grouped["feasible_candidate_window_count"] > 0
    grouped["confirmation_status"] = CONFIRMATION_STATUS
    grouped["source_phase"] = PHASE4_SOURCE_PHASE
    grouped["advisory_only_flag"] = True
    return grouped[[
        "planning_run_id", "machine_id", "machine_name", "feasible_candidate_window_count", "blocked_candidate_window_count",
        "highest_recommended_scheduling_priority", "best_schedule_feasibility_status", "main_schedule_blocker",
        "scheduling_feasibility_ready_flag", "confirmation_status", "source_phase", "advisory_only_flag",
    ]]


def _validate_outputs(candidate_windows: pd.DataFrame, calendar: pd.DataFrame, crew_load: pd.DataFrame, machine_impact: pd.DataFrame, review: pd.DataFrame, phase4_context: pd.DataFrame, checks: list[dict]) -> None:
    outputs = {
        "maintenance_schedule_candidate_windows": candidate_windows,
        "maintenance_calendar_feasibility": calendar,
        "maintenance_crew_window_load": crew_load,
        "maintenance_machine_window_impact": machine_impact,
        "maintenance_schedule_manager_review_queue": review,
        "phase4_maintenance_schedule_feasibility_context": phase4_context,
    }
    for name, frame in outputs.items():
        _add_check(checks, f"{name}_not_empty", "PASS" if not frame.empty else "FAIL", f"{name} rows={len(frame)}", len(frame))
    required = {
        "maintenance_schedule_candidate_windows": {"planning_run_id", "schedule_candidate_window_id", "candidate_id", "machine_id", "machine_name", "candidate_type", "maintenance_plan_id", "required_skill_id", "required_crew_type", "required_worker_count", "maintenance_level", "estimated_duration_hours", "planned_downtime_hours", "candidate_window_period", "candidate_window_day", "candidate_window_shift", "crew_capacity_available_flag", "spare_part_ready_flag", "production_bottleneck_sensitive_flag", "schedule_feasibility_status", "schedule_feasibility_reason", "scheduling_priority_score", "recommended_scheduling_priority", "schedule_assignment_status", "note_no_schedule_created_flag", "source_phase", "advisory_only_flag"},
        "maintenance_calendar_feasibility": {"planning_run_id", "candidate_window_period", "candidate_window_day", "candidate_window_shift", "feasible_candidate_count", "blocked_candidate_count", "crew_blocked_count", "spare_part_blocked_count", "production_impact_blocked_count", "highest_priority_candidate_id", "calendar_feasibility_status", "calendar_feasibility_reason", "source_phase", "advisory_only_flag"},
        "maintenance_crew_window_load": {"planning_run_id", "candidate_window_period", "candidate_window_day", "candidate_window_shift", "required_crew_type", "required_skill_id", "available_crew_hours", "candidate_required_hours", "remaining_crew_hours", "crew_window_utilization_pct", "crew_window_status", "double_booking_risk_flag", "note_no_dispatch_created_flag", "source_phase", "advisory_only_flag"},
        "maintenance_machine_window_impact": {"planning_run_id", "schedule_candidate_window_id", "candidate_id", "machine_id", "machine_name", "workstation_id", "workstation_name", "planned_downtime_hours", "production_impact_level", "bottleneck_impact_level", "machine_availability_impact_level", "estimated_capacity_at_risk_hours", "window_impact_level", "note_no_capacity_reduction_applied_flag", "source_phase", "advisory_only_flag"},
        "maintenance_schedule_manager_review_queue": {"review_item_id", "planning_run_id", "candidate_id", "schedule_candidate_window_id", "machine_id", "issue_type", "issue_severity", "issue_description", "recommended_review_action", "auto_action_allowed", "advisory_only_flag"},
        "phase4_maintenance_schedule_feasibility_context": {"planning_run_id", "machine_id", "machine_name", "feasible_candidate_window_count", "blocked_candidate_window_count", "highest_recommended_scheduling_priority", "best_schedule_feasibility_status", "main_schedule_blocker", "scheduling_feasibility_ready_flag", "confirmation_status", "source_phase", "advisory_only_flag"},
    }
    for name, cols in required.items():
        missing = sorted(cols - set(outputs[name].columns))
        _add_check(checks, f"{name}_required_columns", "PASS" if not missing else "FAIL", f"missing={missing}", len(missing))
    numeric_checks = [
        (candidate_windows, ["required_worker_count", "estimated_duration_hours", "planned_downtime_hours", "scheduling_priority_score"]),
        (calendar, ["feasible_candidate_count", "blocked_candidate_count", "crew_blocked_count", "spare_part_blocked_count", "production_impact_blocked_count"]),
        (crew_load, ["available_crew_hours", "candidate_required_hours", "crew_window_utilization_pct"]),
        (machine_impact, ["planned_downtime_hours", "estimated_capacity_at_risk_hours"]),
    ]
    bad_numeric = 0
    for frame, cols in numeric_checks:
        for col in cols:
            if col in frame.columns:
                bad_numeric += int((_num(frame, col) < 0).sum())
    _add_check(checks, "numeric_fields_non_negative", "PASS" if bad_numeric == 0 else "FAIL", f"negative_rows={bad_numeric}", bad_numeric)
    _add_check(checks, "schedule_assignment_candidate_only", "PASS" if candidate_windows["schedule_assignment_status"].eq("NOT_SCHEDULED_CANDIDATE_ONLY").all() else "FAIL", "No confirmed schedule assignments are created.", len(candidate_windows))
    _add_check(checks, "no_schedule_created_flag", "PASS" if _to_bool(candidate_windows["note_no_schedule_created_flag"]).all() else "FAIL", "Candidate windows must not create schedules.", len(candidate_windows))
    _add_check(checks, "no_dispatch_created_flag", "PASS" if _to_bool(crew_load["note_no_dispatch_created_flag"]).all() else "FAIL", "Crew window load must not create dispatch records.", len(crew_load))
    _add_check(checks, "no_capacity_reduction_applied_flag", "PASS" if _to_bool(machine_impact["note_no_capacity_reduction_applied_flag"]).all() else "FAIL", "Machine window impact must not reduce capacity.", len(machine_impact))
    _add_check(checks, "phase4_confirmation_status", "PASS" if phase4_context["confirmation_status"].eq(CONFIRMATION_STATUS).all() else "FAIL", CONFIRMATION_STATUS, len(phase4_context))
    invalid_status = int((~candidate_windows["schedule_feasibility_status"].isin(VALID_FEASIBILITY)).sum())
    invalid_crew = int((~crew_load["crew_window_status"].isin(VALID_CREW_WINDOW_STATUS)).sum())
    _add_check(checks, "valid_schedule_feasibility_status", "PASS" if invalid_status == 0 else "FAIL", f"invalid={invalid_status}", invalid_status)
    _add_check(checks, "valid_crew_window_status", "PASS" if invalid_crew == 0 else "FAIL", f"invalid={invalid_crew}", invalid_crew)
    incomplete = candidate_windows[candidate_windows[["required_skill_id", "required_crew_type", "maintenance_level"]].apply(lambda s: s.map(_is_blank)).any(axis=1)]
    bad_incomplete = int((incomplete["schedule_feasibility_status"] != "REVIEW_REQUIRED").sum()) if not incomplete.empty else 0
    _add_check(checks, "incomplete_candidates_review_required", "PASS" if bad_incomplete == 0 else "FAIL", f"bad_incomplete={bad_incomplete}", bad_incomplete)
    for name, frame in outputs.items():
        if "advisory_only_flag" in frame.columns:
            _add_check(checks, f"{name}_advisory_only", "PASS" if _to_bool(frame["advisory_only_flag"]).all() else "FAIL", f"{name} advisory_only_flag must be True.", len(frame))
    if not review.empty:
        _add_check(checks, "review_queue_no_auto_action", "PASS" if (~_to_bool(review["auto_action_allowed"])).all() else "FAIL", "Review queue cannot allow auto action.", len(review))


def _calendar_capacity(calendar: pd.DataFrame, crews: pd.DataFrame) -> pd.DataFrame:
    active = crews[_to_bool(crews["active_flag"])].copy()
    cal = calendar[_to_bool(calendar["available_flag"])].copy().merge(active[["crew_id", "crew_type", "workers_available"]], on="crew_id", how="inner")
    if cal.empty:
        return pd.DataFrame(columns=["candidate_window_day", "candidate_window_shift", "crew_type", "available_crew_hours"])
    cal["shift_hours"] = cal.apply(lambda r: max((_parse_time(r["shift_end"]) - _parse_time(r["shift_start"])) - _safe_number(r.get("planned_break_minutes", 0)) / 60, 0), axis=1)
    cal["available_crew_hours"] = cal["shift_hours"] * _num(cal, "workers_available")
    cal["candidate_window_day"] = cal["weekday"].astype(str)
    cal["candidate_window_shift"] = cal["shift_start"].astype(str) + "-" + cal["shift_end"].astype(str)
    return cal.groupby(["candidate_window_day", "candidate_window_shift", "crew_type"], as_index=False).agg(available_crew_hours=("available_crew_hours", "sum"))


def _parse_time(value: object) -> float:
    try:
        t = datetime.strptime(str(value), "%H:%M")
        return t.hour + t.minute / 60
    except ValueError:
        return 0.0


def _feasibility_status(blockers: list[str]) -> str:
    unique = set(blockers)
    if "REVIEW_REQUIRED" in unique:
        return "REVIEW_REQUIRED"
    if not unique:
        return "FEASIBLE_CANDIDATE"
    if len(unique) > 1:
        return "MULTI_BLOCKED"
    return {
        "CREW": "BLOCKED_BY_CREW",
        "SPARE_PART": "BLOCKED_BY_SPARE_PART",
        "PRODUCTION_IMPACT": "BLOCKED_BY_PRODUCTION_IMPACT",
    }.get(next(iter(unique)), "REVIEW_REQUIRED")


def _feasibility_reason(blockers: list[str], complete: bool) -> str:
    if not complete:
        return "INCOMPLETE_CANDIDATE_REQUIREMENTS_REVIEW_REQUIRED"
    if not blockers:
        return "CREW_SPARE_AND_DOWNTIME_WINDOW_ACCEPTABLE_FOR_ADVISORY_REVIEW"
    return "BLOCKERS=" + "+".join(sorted(set(blockers)))


def _priority_score(row: object, status: str, production_sensitive: bool) -> float:
    score = 0.0
    if str(row.candidate_type) == "OVERDUE_MAINTENANCE":
        score += 40
    elif str(row.candidate_type) == "DUE_MAINTENANCE":
        score += 25
    elif str(row.candidate_type) == "BREAKDOWN_RISK_PREVENTIVE_REVIEW":
        score += 30
    score += PRIORITY_POINTS.get(str(getattr(row, "breakdown_risk_level", "LOW")), 25)
    score += PRIORITY_POINTS.get(str(getattr(row, "bottleneck_impact_level", "LOW")), 10) / 2
    score += PRIORITY_POINTS.get(str(getattr(row, "production_impact_level", "LOW")), 10) / 2
    score += min(_safe_number(getattr(row, "planned_downtime_hours", 0)) * 5, 30)
    if production_sensitive:
        score += 15
    if status != "FEASIBLE_CANDIDATE":
        score += 10
    return round(score, 2)


def _priority_label(score: float) -> str:
    if score >= 130:
        return "CRITICAL"
    if score >= 90:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _crew_window_status(row: pd.Series) -> str:
    if row["available_crew_hours"] <= 0:
        return "NO_ACTIVE_COVERAGE"
    util = row["crew_window_utilization_pct"]
    if util > 95:
        return "OVERLOADED"
    if util > 80:
        return "HIGH_UTILIZATION_WARNING"
    return "AVAILABLE"


def _best_feasibility(values: pd.Series) -> str:
    vals = list(values.astype(str))
    if "FEASIBLE_CANDIDATE" in vals:
        return "FEASIBLE_CANDIDATE"
    for status in ["MULTI_BLOCKED", "BLOCKED_BY_CREW", "BLOCKED_BY_SPARE_PART", "BLOCKED_BY_PRODUCTION_IMPACT", "REVIEW_REQUIRED"]:
        if status in vals:
            return status
    return "REVIEW_REQUIRED"


def _main_blocker(values: pd.Series) -> str:
    vals = list(values.astype(str))
    for status, blocker in [
        ("MULTI_BLOCKED", "MULTIPLE_BLOCKERS"),
        ("BLOCKED_BY_CREW", "CREW"),
        ("BLOCKED_BY_SPARE_PART", "SPARE_PART"),
        ("BLOCKED_BY_PRODUCTION_IMPACT", "PRODUCTION_IMPACT"),
        ("REVIEW_REQUIRED", "REVIEW_REQUIRED"),
    ]:
        if status in vals:
            return blocker
    return "NONE"


def _review_row(idx: int, run_id: str, candidate_id: str, window_id: str, machine_id: str, issue_type: str, severity: str, description: str, action: str) -> dict:
    return {
        "review_item_id": f"SCHED-REVIEW-{idx:03d}",
        "planning_run_id": run_id,
        "candidate_id": candidate_id,
        "schedule_candidate_window_id": window_id,
        "machine_id": machine_id,
        "issue_type": issue_type,
        "issue_severity": severity,
        "issue_description": description,
        "recommended_review_action": action,
        "auto_action_allowed": False,
        "advisory_only_flag": True,
    }


def _review_action(issue_type: str) -> str:
    return {
        "CREW_BLOCKED_SCHEDULE_CANDIDATE": "REVIEW_CREW_CAPACITY_AND_SKILL_COVERAGE",
        "SPARE_PART_BLOCKED_SCHEDULE_CANDIDATE": "REVIEW_SPARE_PART_READINESS",
        "PRODUCTION_IMPACT_BLOCKED_CANDIDATE": "REVIEW_PRODUCTION_IMPACT_WINDOW",
        "HIGH_PRIORITY_SCHEDULING_REVIEW": "REVIEW_HIGH_PRIORITY_CANDIDATE",
    }.get(issue_type, "REVIEW_BEFORE_ACTION")


def _load_csv(path: Path, label: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        _add_check(checks, f"{label}_exists", "FAIL", f"Missing input: {path}", 1)
        return None
    frame = pd.read_csv(path)
    _add_check(checks, f"{label}_exists", "PASS", f"{label} rows={len(frame)}", len(frame))
    if frame.empty:
        _add_check(checks, f"{label}_not_empty", "FAIL", f"{label} is empty.", 0)
    return frame


def _check_existing_validations(checks: list[dict]) -> None:
    for label, path in {
        "workforce_validation": WORKFORCE_VALIDATION_FILE,
        "spare_part_validation": SPARE_VALIDATION_FILE,
        "maintenance_plan_validation": MAINTENANCE_VALIDATION_FILE,
        "breakdown_validation": BREAKDOWN_VALIDATION_FILE,
        "maintenance_crew_capacity_validation": CREW_CAPACITY_VALIDATION_FILE,
        "maintenance_production_impact_validation": MAINTENANCE_IMPACT_VALIDATION_FILE,
    }.items():
        if not path.exists():
            _add_check(checks, f"{label}_exists", "FAIL", f"Missing validation: {path}", 1)
            continue
        frame = pd.read_csv(path)
        fail_count = int((frame.get("status", pd.Series(dtype=str)).astype(str).str.upper() == "FAIL").sum())
        _add_check(checks, f"{label}_no_fail_rows", "PASS" if fail_count == 0 else "FAIL", f"fail_count={fail_count}", fail_count)


def _check_no_forbidden_outputs(checks: list[dict]) -> None:
    allowed = {
        SCHEDULE_CANDIDATE_WINDOWS_FILE.name,
        VALIDATION_OUTPUT_FILE.name,
        PHASE4_CONTEXT_FILE.name,
    }
    forbidden_terms = [
        "maintenance_work_order",
        "work_order",
        "crew_dispatch",
        "spare_part_consumption",
        "inventory_reservation",
        "purchase_order",
        "capacity_reduction",
        "simulation",
    ]
    found = []
    for directory in [SHARED_OUTPUT_DIR, PHASE4_OUTPUT_DIR]:
        if not directory.exists():
            continue
        for path in directory.iterdir():
            name = path.name.lower()
            if path.name in allowed:
                continue
            if any(term in name for term in forbidden_terms):
                found.append(str(path))
    _add_check(checks, "no_forbidden_execution_outputs", "PASS" if not found else "FAIL", "; ".join(found) if found else "No forbidden execution outputs found.", len(found))


def _add_check(checks: list[dict], name: str, status: str, message: str, affected_rows: int) -> None:
    checks.append({
        "check_id": f"S7G-{len(checks)+1:03d}",
        "check_name": name,
        "status": status,
        "message": message,
        "affected_rows": int(affected_rows),
        "advisory_only_flag": True,
    })


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series([0.0] * len(frame), index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _safe_number(value: object) -> float:
    return float(pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0).iloc[0])


def _to_bool(series: pd.Series | object) -> pd.Series | bool:
    if isinstance(series, pd.Series):
        return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})
    return str(series).strip().lower() in {"true", "1", "yes", "y"}


def _is_blank(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "nat"}


def _level_rank(value: object) -> int:
    return LEVEL_ORDER.get(str(value), 5)


def _highest_level(values: list[object] | pd.Series) -> str:
    vals = [str(v) for v in values if str(v) in LEVEL_ORDER]
    if not vals:
        return "REVIEW_REQUIRED"
    return max(vals, key=lambda v: LEVEL_ORDER[v])


if __name__ == "__main__":
    result = build_maintenance_schedule_feasibility_outputs()
    validation = result[0]
    print(f"Maintenance schedule validation rows: {len(validation)}")
    print(f"Validation status counts: {validation['status'].value_counts().to_dict()}")
