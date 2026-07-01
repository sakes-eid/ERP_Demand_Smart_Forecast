"""Estimate advisory maintenance crew capacity and repair queue risk."""

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
CREW_SKILL_MATRIX_FILE = DATA_DIR / "crew_skill_matrix.csv"
WORKFORCE_SKILLS_FILE = DATA_DIR / "workforce_skills.csv"
MACHINES_FILE = PHASE4_DIR / "data" / "machines.csv"
MPS_FILE = PHASE4_OUTPUT_DIR / "phase4_master_production_schedule.csv"

WORKFORCE_VALIDATION_FILE = OUTPUT_DIR / "workforce_crew_validation.csv"
SPARE_VALIDATION_FILE = OUTPUT_DIR / "spare_part_validation.csv"
MAINTENANCE_VALIDATION_FILE = OUTPUT_DIR / "maintenance_plan_validation.csv"
BREAKDOWN_VALIDATION_FILE = OUTPUT_DIR / "breakdown_validation.csv"
CREW_CAPACITY_FILE = OUTPUT_DIR / "workforce_crew_capacity_context.csv"
WORKFORCE_AUTH_FILE = OUTPUT_DIR / "workforce_machine_authorization_context.csv"
MAINTENANCE_DUE_FILE = OUTPUT_DIR / "maintenance_due_status_context.csv"
BREAKDOWN_RISK_FILE = OUTPUT_DIR / "breakdown_risk_forecast.csv"
BREAKDOWN_CREW_EXPOSURE_FILE = OUTPUT_DIR / "breakdown_crew_skill_exposure.csv"
BREAKDOWN_SPARE_EXPOSURE_FILE = OUTPUT_DIR / "breakdown_spare_part_exposure.csv"

WORKLOAD_BY_SKILL_FILE = OUTPUT_DIR / "maintenance_workload_by_skill.csv"
CREW_CAPACITY_SUMMARY_FILE = OUTPUT_DIR / "maintenance_crew_capacity_summary.csv"
REPAIR_QUEUE_RISK_FILE = OUTPUT_DIR / "maintenance_repair_queue_risk.csv"
BACKLOG_RISK_SUMMARY_FILE = OUTPUT_DIR / "maintenance_backlog_risk_summary.csv"
MANAGER_REVIEW_QUEUE_FILE = OUTPUT_DIR / "maintenance_crew_capacity_manager_review_queue.csv"
VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "maintenance_crew_capacity_validation.csv"
PHASE4_CREW_CAPACITY_CONTEXT_FILE = PHASE4_OUTPUT_DIR / "phase4_maintenance_crew_capacity_context.csv"

SOURCE_PHASE = "SHARED_STEP7E_MAINTENANCE_CREW_CAPACITY"
PHASE4_SOURCE_PHASE = "PHASE4_STEP7E_MAINTENANCE_CREW_CAPACITY_CONTEXT"
QUEUE_MEASUREMENT_TYPE = "ESTIMATED_FROM_MAINTENANCE_PLAN_AND_BREAKDOWN_RISK"
VALID_CAPACITY_STATUS = {"FEASIBLE", "HIGH_UTILIZATION_WARNING", "OVERLOADED", "NO_ACTIVE_COVERAGE", "REVIEW_REQUIRED"}
VALID_QUEUE_LEVEL = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "REVIEW_REQUIRED"}
RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4, "REVIEW_REQUIRED": 5}


def build_maintenance_crew_capacity_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    checks: list[dict] = []
    frames = {
        "plans": _load_csv(MAINTENANCE_PLANS_FILE, "maintenance_plans", checks),
        "skills": _load_csv(WORKFORCE_SKILLS_FILE, "workforce_skills", checks),
        "crew_skills": _load_csv(CREW_SKILL_MATRIX_FILE, "crew_skill_matrix", checks),
        "crew_capacity": _load_csv(CREW_CAPACITY_FILE, "workforce_crew_capacity_context", checks),
        "auth": _load_csv(WORKFORCE_AUTH_FILE, "workforce_machine_authorization_context", checks),
        "due": _load_csv(MAINTENANCE_DUE_FILE, "maintenance_due_status_context", checks),
        "risk": _load_csv(BREAKDOWN_RISK_FILE, "breakdown_risk_forecast", checks),
        "crew_exposure": _load_csv(BREAKDOWN_CREW_EXPOSURE_FILE, "breakdown_crew_skill_exposure", checks),
        "spare_exposure": _load_csv(BREAKDOWN_SPARE_EXPOSURE_FILE, "breakdown_spare_part_exposure", checks),
        "machines": _load_csv(MACHINES_FILE, "phase4_machines", checks),
    }
    if all(frame is not None for frame in frames.values()):
        workload = _build_workload_by_skill(frames)
        crew_summary = _build_crew_capacity_summary(frames, workload)
        queue = _build_repair_queue_risk(frames, workload)
        backlog = _build_backlog_summary(workload, queue)
        review = _build_manager_review_queue(workload, crew_summary, queue, backlog)
        phase4_context = _build_phase4_context(queue, backlog, frames)
        _validate_outputs(workload, crew_summary, queue, backlog, review, phase4_context, frames, checks)
    else:
        workload = crew_summary = queue = backlog = review = phase4_context = pd.DataFrame()
    _check_existing_validations(checks)
    _check_no_blocked_outputs(checks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PHASE4_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    workload.to_csv(WORKLOAD_BY_SKILL_FILE, index=False)
    crew_summary.to_csv(CREW_CAPACITY_SUMMARY_FILE, index=False)
    queue.to_csv(REPAIR_QUEUE_RISK_FILE, index=False)
    backlog.to_csv(BACKLOG_RISK_SUMMARY_FILE, index=False)
    review.to_csv(MANAGER_REVIEW_QUEUE_FILE, index=False)
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    phase4_context.to_csv(PHASE4_CREW_CAPACITY_CONTEXT_FILE, index=False)
    return validation, workload, crew_summary, queue, backlog, review, phase4_context


def _build_workload_by_skill(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    plans = frames["plans"]
    due = frames["due"]
    crew_exposure = frames["crew_exposure"]
    risk = frames["risk"]
    skills = frames["skills"]
    planned = due.merge(plans[["maintenance_plan_id", "required_skill_id", "estimated_labor_hours", "required_crew_type"]], on="maintenance_plan_id", how="left")
    planned["planned_maintenance_hours"] = pd.to_numeric(planned["estimated_labor_hours"], errors="coerce").fillna(0) * planned["due_status"].map(_due_factor).fillna(0)
    planned_rows = planned[planned["planned_maintenance_hours"] > 0].groupby(["required_skill_id", "maintenance_level"], as_index=False).agg(planned_maintenance_hours=("planned_maintenance_hours", "sum"))
    planned_rows["expected_repair_hours"] = 0.0
    planned_rows["workload_source"] = planned_rows["maintenance_level"].astype(str).apply(
        lambda level: "PLANNED_LIGHT_AUTONOMOUS_MAINTENANCE" if level == "LIGHT" else "PLANNED_MAINTENANCE"
    )

    repair = crew_exposure.merge(risk[["machine_id", "expected_repair_hours_next_period"]], on="machine_id", how="left")
    repair["expected_repair_hours_next_period"] = pd.to_numeric(repair["expected_repair_hours_next_period"], errors="coerce").fillna(0)
    mode_counts = repair.groupby("machine_id")["failure_mode_id"].transform("count").replace(0, 1)
    repair["expected_repair_hours"] = repair["expected_repair_hours_next_period"] / mode_counts
    repair_rows = repair.groupby(["required_skill_id", "required_maintenance_level"], as_index=False).agg(expected_repair_hours=("expected_repair_hours", "sum")).rename(columns={"required_maintenance_level": "maintenance_level"})
    repair_rows["planned_maintenance_hours"] = 0.0
    repair_rows["workload_source"] = "EXPECTED_BREAKDOWN_REPAIR"

    frame = pd.concat([
        planned_rows[["required_skill_id", "maintenance_level", "workload_source", "planned_maintenance_hours", "expected_repair_hours"]],
        repair_rows[["required_skill_id", "maintenance_level", "workload_source", "planned_maintenance_hours", "expected_repair_hours"]],
    ], ignore_index=True)
    frame[["planned_maintenance_hours", "expected_repair_hours"]] = frame[["planned_maintenance_hours", "expected_repair_hours"]].fillna(0)
    frame["total_required_hours"] = frame["planned_maintenance_hours"] + frame["expected_repair_hours"]
    coverage = _skill_capacity(frames, frame)
    frame = frame.merge(coverage, on=["required_skill_id", "maintenance_level", "workload_source"], how="left")
    frame = frame.merge(skills[["skill_id", "skill_name"]], left_on="required_skill_id", right_on="skill_id", how="left")
    for col in ["active_maintenance_crew_count", "light_authorized_production_crew_count", "available_crew_hours"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)
    frame["utilization_pct"] = frame.apply(lambda r: round((r["total_required_hours"] / r["available_crew_hours"] * 100), 2) if r["available_crew_hours"] > 0 else (0.0 if r["total_required_hours"] == 0 else 999.0), axis=1)
    frame["backlog_hours"] = (frame["total_required_hours"] - frame["available_crew_hours"]).clip(lower=0).round(2)
    frame["skill_coverage_status"] = frame.apply(_coverage_status, axis=1)
    frame["capacity_status"] = frame.apply(_capacity_status, axis=1)
    frame["planning_run_id"] = _planning_run_id()
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame.rename(columns={"skill_name": "required_skill_name"})[["planning_run_id", "required_skill_id", "required_skill_name", "maintenance_level", "workload_source", "planned_maintenance_hours", "expected_repair_hours", "total_required_hours", "active_maintenance_crew_count", "light_authorized_production_crew_count", "available_crew_hours", "utilization_pct", "capacity_status", "backlog_hours", "skill_coverage_status", "source_phase", "advisory_only_flag"]].copy()


def _skill_capacity(frames: dict[str, pd.DataFrame], workload: pd.DataFrame) -> pd.DataFrame:
    crew_capacity = frames["crew_capacity"][_to_bool(frames["crew_capacity"]["active_flag"])].copy()
    crew_skills = frames["crew_skills"][_to_bool(frames["crew_skills"]["active_flag"])].copy()
    auth = frames["auth"].copy()
    crew_skill_capacity = crew_skills.merge(crew_capacity[["crew_id", "crew_type", "weekly_capacity_hours"]], on="crew_id", how="left")
    crew_skill_capacity["max_hours_per_week_for_skill"] = pd.to_numeric(crew_skill_capacity["max_hours_per_week_for_skill"], errors="coerce").fillna(0)
    rows = []
    light_prod_crews = set(auth[
        (auth["crew_type"].astype(str) == "PRODUCTION")
        & _to_bool(auth["can_maintain_flag"])
        & (auth["maintenance_level_authorized"].astype(str) == "LIGHT")
    ]["crew_id"].astype(str))
    for key in workload[["required_skill_id", "maintenance_level", "workload_source"]].drop_duplicates().itertuples(index=False):
        skill_id = str(key.required_skill_id)
        level = str(key.maintenance_level)
        source = str(key.workload_source)
        maint = crew_skill_capacity[
            (crew_skill_capacity["skill_id"].astype(str) == skill_id)
            & (crew_skill_capacity["crew_type"].astype(str) == "MAINTENANCE")
        ]
        prod = crew_skill_capacity.iloc[0:0]
        if level == "LIGHT" and source == "PLANNED_LIGHT_AUTONOMOUS_MAINTENANCE":
            prod = crew_skill_capacity[
                (crew_skill_capacity["skill_id"].astype(str) == skill_id)
                & (crew_skill_capacity["crew_type"].astype(str) == "PRODUCTION")
                & (crew_skill_capacity["crew_id"].astype(str).isin(light_prod_crews))
            ]
        rows.append({
            "required_skill_id": skill_id,
            "maintenance_level": level,
            "workload_source": source,
            "active_maintenance_crew_count": maint["crew_id"].nunique(),
            "light_authorized_production_crew_count": prod["crew_id"].nunique(),
            "available_crew_hours": float(maint["max_hours_per_week_for_skill"].sum() + prod["max_hours_per_week_for_skill"].sum()),
        })
    return pd.DataFrame(rows)


def _build_crew_capacity_summary(frames: dict[str, pd.DataFrame], workload: pd.DataFrame) -> pd.DataFrame:
    crew_capacity = frames["crew_capacity"][_to_bool(frames["crew_capacity"]["active_flag"])].copy()
    crew_skills = frames["crew_skills"][_to_bool(frames["crew_skills"]["active_flag"])].copy()
    auth = frames["auth"].copy()
    total_skill_hours = workload.groupby("required_skill_id", as_index=False).agg(total_required_hours=("total_required_hours", "sum"))
    crew_skill = crew_skills.merge(total_skill_hours, left_on="skill_id", right_on="required_skill_id", how="left")
    crew_skill["total_required_hours"] = pd.to_numeric(crew_skill["total_required_hours"], errors="coerce").fillna(0)
    eligible = crew_skill.merge(crew_capacity[["crew_id", "crew_type", "weekly_capacity_hours"]], on="crew_id", how="left")
    eligible = eligible[eligible["crew_type"].astype(str) == "MAINTENANCE"]
    assigned = eligible.groupby("crew_id", as_index=False).agg(assigned_planning_workload_hours=("total_required_hours", "sum"), supported_skill_count=("skill_id", "nunique"))
    summary = crew_capacity.merge(assigned, on="crew_id", how="left")
    summary[["assigned_planning_workload_hours", "supported_skill_count"]] = summary[["assigned_planning_workload_hours", "supported_skill_count"]].fillna(0)
    machine_counts = auth.groupby("crew_id", as_index=False).agg(supported_machine_count=("machine_id", "nunique"))
    summary = summary.merge(machine_counts, on="crew_id", how="left")
    summary["supported_machine_count"] = pd.to_numeric(summary["supported_machine_count"], errors="coerce").fillna(0).astype(int)
    summary["available_hours"] = pd.to_numeric(summary["weekly_capacity_hours"], errors="coerce").fillna(0)
    summary["utilization_pct"] = summary.apply(lambda r: round(r["assigned_planning_workload_hours"] / r["available_hours"] * 100, 2) if r["available_hours"] > 0 else 0.0, axis=1)
    summary["utilization_status"] = summary["utilization_pct"].apply(_util_status)
    summary["workload_mix"] = summary["crew_type"].map({"MAINTENANCE": "MAINTENANCE_REPAIR_AND_DUE_STATUS", "PRODUCTION": "LIGHT_AUTONOMOUS_SUPPORT_ONLY"}).fillna("REVIEW_REQUIRED")
    summary["planning_run_id"] = _planning_run_id()
    summary["source_phase"] = SOURCE_PHASE
    summary["advisory_only_flag"] = True
    return summary[["planning_run_id", "crew_id", "crew_name", "crew_type", "available_hours", "assigned_planning_workload_hours", "utilization_pct", "utilization_status", "supported_skill_count", "supported_machine_count", "workload_mix", "source_phase", "advisory_only_flag"]].copy()


def _build_repair_queue_risk(frames: dict[str, pd.DataFrame], workload: pd.DataFrame) -> pd.DataFrame:
    crew = frames["crew_exposure"].copy()
    risk = frames["risk"][["machine_id", "breakdown_risk_level", "expected_repair_hours_next_period"]]
    spares = frames["spare_exposure"].copy()
    spare_status = spares.groupby(["machine_id", "failure_mode_id"], as_index=False).agg(spare_part_readiness_status=("spare_part_readiness_status", _worst_readiness))
    frame = crew.merge(risk, on="machine_id", how="left").merge(spare_status, on=["machine_id", "failure_mode_id"], how="left")
    repair_workload = workload[workload["workload_source"].astype(str) == "EXPECTED_BREAKDOWN_REPAIR"]
    status_map = repair_workload.set_index(["required_skill_id", "maintenance_level"])["capacity_status"].to_dict()
    maint_count_map = repair_workload.set_index(["required_skill_id", "maintenance_level"])["active_maintenance_crew_count"].to_dict()
    frame["crew_capacity_status"] = frame.apply(lambda r: status_map.get((r["required_skill_id"], r["required_maintenance_level"]), "REVIEW_REQUIRED"), axis=1)
    frame["active_maintenance_crew_count"] = frame.apply(lambda r: maint_count_map.get((r["required_skill_id"], r["required_maintenance_level"]), 0), axis=1)
    no_maint = pd.to_numeric(frame["active_maintenance_crew_count"], errors="coerce").fillna(0) <= 0
    repair_load = pd.to_numeric(frame["expected_repair_hours_next_period"], errors="coerce").fillna(0) > 0
    frame.loc[no_maint & repair_load, "crew_capacity_status"] = "NO_ACTIVE_COVERAGE"
    frame.loc[no_maint & repair_load, "crew_skill_coverage_status"] = "NO_ACTIVE_COVERAGE"
    rows = []
    for row in frame.itertuples():
        score = 10 + _risk_points(row.breakdown_risk_level)
        if float(row.expected_repair_hours_next_period) > 4:
            score += 20
        elif float(row.expected_repair_hours_next_period) > 1:
            score += 8
        if row.spare_part_readiness_status != "READY":
            score += 20
        if row.crew_skill_coverage_status in {"NO_ACTIVE_COVERAGE", "REVIEW_REQUIRED"}:
            score += 35
        elif row.crew_skill_coverage_status == "LIMITED_COVERAGE":
            score += 10
        if row.crew_capacity_status in {"OVERLOADED", "NO_ACTIVE_COVERAGE"}:
            score += 25
        if row.crew_capacity_status == "NO_ACTIVE_COVERAGE":
            score = max(score, 90)
        level = _queue_level(score)
        reasons = [str(row.breakdown_risk_level), str(row.crew_skill_coverage_status)]
        if row.spare_part_readiness_status != "READY":
            reasons.append("SPARE_PART_REVIEW")
        if row.crew_capacity_status != "FEASIBLE":
            reasons.append(row.crew_capacity_status)
        rows.append({
            "planning_run_id": row.planning_run_id,
            "machine_id": row.machine_id,
            "machine_name": row.machine_name,
            "required_skill_id": row.required_skill_id,
            "breakdown_risk_level": row.breakdown_risk_level,
            "expected_repair_hours_next_period": row.expected_repair_hours_next_period,
            "spare_part_readiness_status": row.spare_part_readiness_status,
            "crew_skill_coverage_status": row.crew_skill_coverage_status,
            "crew_capacity_status": row.crew_capacity_status,
            "active_maintenance_crew_count": row.active_maintenance_crew_count,
            "estimated_repair_queue_risk_score": round(score, 2),
            "estimated_repair_queue_risk_level": level,
            "repair_queue_risk_reason": ";".join(reasons),
            "queue_measurement_type": QUEUE_MEASUREMENT_TYPE,
            "actual_repair_queue_available_flag": False,
            "actual_wait_time_available_flag": False,
            "note_no_scheduling_flag": True,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows)


def _build_backlog_summary(workload: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    total_planned = float(workload["planned_maintenance_hours"].sum())
    total_repair = float(workload["expected_repair_hours"].sum())
    total_required = float(workload["total_required_hours"].sum())
    total_available = float(workload["available_crew_hours"].sum())
    total_backlog = float(workload["backlog_hours"].sum())
    overloaded = int(workload["capacity_status"].isin(["OVERLOADED"]).sum())
    workload_no_coverage = set(
        workload.loc[
            workload["capacity_status"].isin(["NO_ACTIVE_COVERAGE"]) | workload["skill_coverage_status"].isin(["NO_ACTIVE_COVERAGE"]),
            "required_skill_id",
        ].astype(str)
    )
    queue_no_coverage = set()
    if not queue.empty:
        queue_no_coverage = set(
            queue.loc[
                queue["crew_skill_coverage_status"].isin(["NO_ACTIVE_COVERAGE"]) | queue.get("crew_capacity_status", pd.Series(dtype=str)).isin(["NO_ACTIVE_COVERAGE"]),
                "required_skill_id",
            ].astype(str)
        )
    no_coverage = len(workload_no_coverage.union(queue_no_coverage))
    high_queue = int(queue["estimated_repair_queue_risk_level"].isin(["HIGH", "CRITICAL", "REVIEW_REQUIRED"]).sum()) if not queue.empty else 0
    level = "CRITICAL" if no_coverage or total_backlog > 20 else ("HIGH" if overloaded or high_queue else ("MEDIUM" if total_backlog > 0 else "LOW"))
    return pd.DataFrame([{
        "planning_run_id": _planning_run_id(),
        "total_planned_maintenance_hours": round(total_planned, 2),
        "total_expected_repair_hours": round(total_repair, 2),
        "total_required_maintenance_hours": round(total_required, 2),
        "total_available_maintenance_hours": round(total_available, 2),
        "total_backlog_hours": round(total_backlog, 2),
        "overloaded_skill_count": overloaded,
        "no_coverage_skill_count": no_coverage,
        "high_or_critical_repair_queue_count": high_queue,
        "backlog_risk_level": level,
        "backlog_risk_reason": f"required={total_required:.2f}; available={total_available:.2f}; backlog={total_backlog:.2f}; high_queue={high_queue}",
        "source_phase": SOURCE_PHASE,
        "advisory_only_flag": True,
    }])


def _build_manager_review_queue(workload: pd.DataFrame, crew_summary: pd.DataFrame, queue: pd.DataFrame, backlog: pd.DataFrame) -> pd.DataFrame:
    rows = []
    item = 1
    for row in workload.itertuples():
        if row.capacity_status == "OVERLOADED":
            rows.append(_review(item, "MAINTENANCE_SKILL_OVERLOAD", "HIGH", "", "", row.required_skill_id, f"{row.required_skill_id} workload exceeds available capacity by {row.backlog_hours} hours.", "REVIEW_CREW_CAPACITY")); item += 1
        if row.capacity_status == "NO_ACTIVE_COVERAGE":
            rows.append(_review(item, "NO_ACTIVE_CREW_COVERAGE", "CRITICAL", "", "", row.required_skill_id, f"{row.required_skill_id} has no active eligible crew coverage.", "REVIEW_CREW_REPAIR_COVERAGE")); item += 1
        if row.workload_source == "EXPECTED_BREAKDOWN_REPAIR" and row.light_authorized_production_crew_count:
            rows.append(_review(item, "PRODUCTION_CREW_REPAIR_BLOCKED", "HIGH", "", "", row.required_skill_id, f"{row.required_skill_id} is repair exposure and production light-maintenance capacity is blocked from covering it.", "REVIEW_CREW_REPAIR_COVERAGE")); item += 1
        if row.light_authorized_production_crew_count and row.maintenance_level == "LIGHT" and row.workload_source == "PLANNED_LIGHT_AUTONOMOUS_MAINTENANCE":
            rows.append(_review(item, "LIGHT_MAINTENANCE_PRODUCTION_SUPPORT_REVIEW", "LOW", "", "", row.required_skill_id, f"{row.required_skill_id} includes light autonomous production support only.", "REVIEW_BEFORE_ACTION")); item += 1
    for row in queue.itertuples():
        if row.crew_skill_coverage_status == "NO_ACTIVE_COVERAGE" or row.crew_capacity_status == "NO_ACTIVE_COVERAGE":
            rows.append(_review(item, "NO_ACTIVE_CREW_COVERAGE", "CRITICAL", row.machine_id, "", row.required_skill_id, f"{row.machine_name} repair exposure for {row.required_skill_id} has no active maintenance crew coverage.", "REVIEW_CREW_REPAIR_COVERAGE")); item += 1
            rows.append(_review(item, "REPAIR_REQUIRES_MAINTENANCE_CREW", "CRITICAL", row.machine_id, "", row.required_skill_id, f"{row.machine_name} breakdown repair requires maintenance crew coverage; production crews are not eligible.", "REVIEW_CREW_REPAIR_COVERAGE")); item += 1
        if row.estimated_repair_queue_risk_level in {"HIGH", "CRITICAL", "REVIEW_REQUIRED"}:
            rows.append(_review(item, "HIGH_REPAIR_QUEUE_RISK", row.estimated_repair_queue_risk_level if row.estimated_repair_queue_risk_level != "REVIEW_REQUIRED" else "HIGH", row.machine_id, "", row.required_skill_id, f"{row.machine_name} estimated repair queue risk is {row.estimated_repair_queue_risk_level}.", "REVIEW_DOWNTIME_RISK")); item += 1
        if row.spare_part_readiness_status != "READY":
            rows.append(_review(item, "SPARE_PART_BLOCKED_REPAIR_RISK", "HIGH", row.machine_id, "", row.required_skill_id, f"{row.machine_name} has repair exposure with spare readiness {row.spare_part_readiness_status}.", "REVIEW_SPARE_PART_AVAILABILITY")); item += 1
    b = backlog.iloc[0]
    if b["backlog_risk_level"] in {"HIGH", "CRITICAL"}:
        rows.append(_review(item, "MAINTENANCE_BACKLOG_RISK", b["backlog_risk_level"], "", "", "", f"Maintenance backlog risk is {b['backlog_risk_level']} with {b['total_backlog_hours']} backlog hours.", "REVIEW_CREW_CAPACITY")); item += 1
    return pd.DataFrame(rows, columns=["review_item_id", "planning_run_id", "issue_type", "issue_severity", "machine_id", "crew_id", "required_skill_id", "issue_description", "recommended_review_action", "auto_action_allowed", "advisory_only_flag"])


def _build_phase4_context(queue: pd.DataFrame, backlog: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    due = frames["due"].groupby("machine_id", as_index=False).agg(maintenance_due_signal=("due_status", _worst_due))
    workload = _build_workload_by_skill(frames)
    repair_workload = workload[workload["workload_source"].astype(str) == "EXPECTED_BREAKDOWN_REPAIR"]
    status_map = repair_workload.set_index(["required_skill_id", "maintenance_level"])["capacity_status"].to_dict()
    crew_exp = frames["crew_exposure"].copy()
    crew_exp["crew_capacity_status"] = crew_exp.apply(lambda r: status_map.get((r["required_skill_id"], r["required_maintenance_level"]), "REVIEW_REQUIRED"), axis=1)
    queue_agg = queue.groupby(["machine_id", "required_skill_id"], as_index=False).agg(estimated_repair_queue_risk_level=("estimated_repair_queue_risk_level", _highest_risk))
    risk = frames["risk"][["machine_id", "machine_name", "breakdown_risk_level"]]
    frame = crew_exp[["machine_id", "machine_name", "required_skill_id", "crew_capacity_status"]].drop_duplicates().merge(risk, on=["machine_id", "machine_name"], how="left").merge(due, on="machine_id", how="left").merge(queue_agg, on=["machine_id", "required_skill_id"], how="left")
    backlog_level = backlog.iloc[0]["backlog_risk_level"] if not backlog.empty else "REVIEW_REQUIRED"
    frame["backlog_risk_level"] = backlog_level
    frame["maintenance_crew_planning_ready_flag"] = ~frame["crew_capacity_status"].isin(["NO_ACTIVE_COVERAGE", "REVIEW_REQUIRED"]) & ~frame["estimated_repair_queue_risk_level"].isin(["CRITICAL", "REVIEW_REQUIRED"])
    frame["planning_run_id"] = _planning_run_id()
    frame["source_phase"] = PHASE4_SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[["planning_run_id", "machine_id", "machine_name", "breakdown_risk_level", "maintenance_due_signal", "required_skill_id", "crew_capacity_status", "estimated_repair_queue_risk_level", "backlog_risk_level", "maintenance_crew_planning_ready_flag", "source_phase", "advisory_only_flag"]].copy()


def _validate_outputs(workload: pd.DataFrame, crew_summary: pd.DataFrame, queue: pd.DataFrame, backlog: pd.DataFrame, review: pd.DataFrame, phase4_context: pd.DataFrame, frames: dict[str, pd.DataFrame], checks: list[dict]) -> None:
    required = {
        "workload": {"planning_run_id", "required_skill_id", "maintenance_level", "planned_maintenance_hours", "expected_repair_hours", "total_required_hours", "available_crew_hours", "utilization_pct", "capacity_status", "backlog_hours", "advisory_only_flag"},
        "queue": {"queue_measurement_type", "actual_repair_queue_available_flag", "actual_wait_time_available_flag", "note_no_scheduling_flag", "crew_capacity_status", "active_maintenance_crew_count", "advisory_only_flag"},
        "phase4": {"crew_capacity_status", "estimated_repair_queue_risk_level", "backlog_risk_level", "maintenance_crew_planning_ready_flag", "advisory_only_flag"},
    }
    for frame, label in [(workload, "workload"), (crew_summary, "crew summary"), (queue, "repair queue risk"), (backlog, "backlog summary"), (phase4_context, "Phase 4 context")]:
        checks.append(_result(f"maintenance_crew_{label.replace(' ', '_')}_not_empty", f"{label} output not empty", "FAIL" if frame.empty else "PASS", f"{label} rows: {len(frame)}", int(frame.empty)))
        if not frame.empty and not _all_true(frame, "advisory_only_flag"):
            checks.append(_result(f"maintenance_crew_{label.replace(' ', '_')}_advisory", f"{label} advisory", "FAIL", f"{label} must be advisory-only.", 1))
        else:
            checks.append(_result(f"maintenance_crew_{label.replace(' ', '_')}_advisory", f"{label} advisory", "PASS", f"{label} advisory-only flags are true.", 0))
    for name, cols in required.items():
        frame = {"workload": workload, "queue": queue, "phase4": phase4_context}[name]
        missing = sorted(cols.difference(frame.columns))
        checks.append(_result(f"maintenance_crew_{name}_required_columns", f"{name} required columns", "FAIL" if missing else "PASS", f"Missing columns: {missing}" if missing else f"{name} has required columns.", len(missing)))
    for frame, columns, label in [
        (workload, ["planned_maintenance_hours", "expected_repair_hours", "total_required_hours", "available_crew_hours", "utilization_pct", "backlog_hours"], "workload"),
        (crew_summary, ["available_hours", "assigned_planning_workload_hours", "utilization_pct"], "crew summary"),
        (queue, ["expected_repair_hours_next_period", "estimated_repair_queue_risk_score"], "repair queue"),
        (backlog, ["total_planned_maintenance_hours", "total_expected_repair_hours", "total_required_maintenance_hours", "total_available_maintenance_hours", "total_backlog_hours"], "backlog"),
    ]:
        bad = 0
        for col in columns:
            values = pd.to_numeric(frame[col], errors="coerce")
            bad += int(values.isna().sum()) + int((values < 0).sum())
        checks.append(_result(f"maintenance_crew_{label.replace(' ', '_')}_numeric", f"{label} numeric non-negative", "FAIL" if bad else "PASS", f"Invalid numeric values: {bad}" if bad else "Numeric fields are non-negative.", bad))
    prod_nonlight = workload[(pd.to_numeric(workload["light_authorized_production_crew_count"], errors="coerce").fillna(0) > 0) & (workload["maintenance_level"] != "LIGHT")]
    checks.append(_result("maintenance_crew_production_light_only", "production crews used only for light maintenance", "FAIL" if not prod_nonlight.empty else "PASS", "Production crews are only included for LIGHT maintenance capacity.", len(prod_nonlight)))
    repair_prod = workload[
        (workload["workload_source"].astype(str) == "EXPECTED_BREAKDOWN_REPAIR")
        & (pd.to_numeric(workload["light_authorized_production_crew_count"], errors="coerce").fillna(0) > 0)
    ]
    checks.append(_result("maintenance_crew_no_production_repair_capacity", "production crews not counted for repair", "FAIL" if not repair_prod.empty else "PASS", "Expected breakdown repair uses maintenance crews only.", len(repair_prod)))
    repair_bad_feasible = workload[
        (workload["workload_source"].astype(str) == "EXPECTED_BREAKDOWN_REPAIR")
        & (workload["capacity_status"].astype(str) == "FEASIBLE")
        & (pd.to_numeric(workload["active_maintenance_crew_count"], errors="coerce").fillna(0) <= 0)
        & (pd.to_numeric(workload["expected_repair_hours"], errors="coerce").fillna(0) > 0)
    ]
    checks.append(_result("maintenance_crew_repair_feasible_requires_maintenance", "repair feasible requires maintenance crew", "FAIL" if not repair_bad_feasible.empty else "PASS", "Repair workload is not made feasible by production light-maintenance capacity.", len(repair_bad_feasible)))
    queue_no_coverage = queue[queue["crew_skill_coverage_status"].astype(str).eq("NO_ACTIVE_COVERAGE") | queue["crew_capacity_status"].astype(str).eq("NO_ACTIVE_COVERAGE")]
    backlog_no_coverage = int(pd.to_numeric(backlog["no_coverage_skill_count"], errors="coerce").fillna(0).max()) if "no_coverage_skill_count" in backlog.columns and not backlog.empty else 0
    checks.append(_result("maintenance_crew_queue_no_coverage_rollup", "queue no coverage rolls into backlog", "FAIL" if not queue_no_coverage.empty and backlog_no_coverage <= 0 else "PASS", "Repair queue no-coverage rows are reflected in backlog no-coverage count.", len(queue_no_coverage)))
    review_no_coverage = review[review["issue_type"].astype(str) == "NO_ACTIVE_CREW_COVERAGE"] if not review.empty and "issue_type" in review.columns else pd.DataFrame()
    missing_review = max(0, int(queue_no_coverage[["machine_id", "required_skill_id"]].drop_duplicates().shape[0]) - int(review_no_coverage[["machine_id", "required_skill_id"]].drop_duplicates().shape[0]) if not review_no_coverage.empty else int(queue_no_coverage[["machine_id", "required_skill_id"]].drop_duplicates().shape[0]))
    checks.append(_result("maintenance_crew_no_coverage_review_rows", "no coverage review rows exist", "FAIL" if missing_review else "PASS", "Every no-coverage repair exposure has a manager review row.", missing_review))
    if set(queue["queue_measurement_type"].dropna().astype(str)) != {QUEUE_MEASUREMENT_TYPE}:
        checks.append(_result("maintenance_crew_queue_measurement_type", "queue measurement type", "FAIL", "Repair queue measurement type must be estimated.", 1))
    else:
        checks.append(_result("maintenance_crew_queue_measurement_type", "queue measurement type", "PASS", "Repair queue measurement is estimated from planning data.", 0))
    flag_bad = int(_to_bool(queue["actual_repair_queue_available_flag"]).sum()) + int(_to_bool(queue["actual_wait_time_available_flag"]).sum()) + int((~_to_bool(queue["note_no_scheduling_flag"])).sum())
    checks.append(_result("maintenance_crew_queue_no_actuals", "queue actual flags disabled", "FAIL" if flag_bad else "PASS", "No actual repair queue/wait time or scheduling flags are enabled.", flag_bad))
    if not review.empty and (_to_bool(review["auto_action_allowed"]).any() or not _all_true(review, "advisory_only_flag")):
        checks.append(_result("maintenance_crew_review_queue_safe", "review queue safe", "FAIL", "Review queue must be advisory-only with auto action disabled.", 1))
    else:
        checks.append(_result("maintenance_crew_review_queue_safe", "review queue safe", "PASS", "Review queue has no automatic action.", 0))


def _check_existing_validations(checks: list[dict]) -> None:
    for path, label in [(WORKFORCE_VALIDATION_FILE, "workforce"), (SPARE_VALIDATION_FILE, "spare-part"), (MAINTENANCE_VALIDATION_FILE, "maintenance"), (BREAKDOWN_VALIDATION_FILE, "breakdown")]:
        if not path.exists():
            checks.append(_result(f"maintenance_crew_existing_{label}_validation", f"existing {label} validation", "FAIL", f"Missing {path}", 1))
            continue
        frame = pd.read_csv(path)
        fail_count = int((frame["status"].astype(str).str.upper() == "FAIL").sum()) if "status" in frame.columns else len(frame)
        checks.append(_result(f"maintenance_crew_existing_{label}_validation", f"existing {label} validation", "FAIL" if fail_count else "PASS", f"{label} validation FAIL rows: {fail_count}", fail_count))


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked = ["maintenance_schedule", "maintenance_work_order", "production_order", "purchase_order", "inventory_reservation", "spare_part_consumption", "capacity_reduction", "simulation"]
    bad = []
    for folder in [OUTPUT_DIR, PHASE4_OUTPUT_DIR]:
        if folder.exists():
            for path in folder.glob("*"):
                if path.is_file() and any(token in path.name.lower() for token in blocked):
                    bad.append(str(path))
    checks.append(_result("maintenance_crew_no_blocked_outputs", "no blocked execution outputs", "FAIL" if bad else "PASS", f"Blocked outputs found: {bad}" if bad else "No work-order, scheduling, reservation, capacity reduction, or simulation outputs found.", len(bad)))


def _due_factor(status: str) -> float:
    return {"OVERDUE": 1.0, "DUE_NOW": 1.0, "DUE_SOON": 0.5, "REVIEW_REQUIRED": 0.25}.get(str(status), 0.0)


def _capacity_status(row: pd.Series) -> str:
    if row["total_required_hours"] > 0 and row["available_crew_hours"] <= 0:
        return "NO_ACTIVE_COVERAGE"
    if row["utilization_pct"] > 95:
        return "OVERLOADED"
    if row["utilization_pct"] > 80:
        return "HIGH_UTILIZATION_WARNING"
    return "FEASIBLE"


def _coverage_status(row: pd.Series) -> str:
    if row["available_crew_hours"] <= 0 and row["total_required_hours"] > 0:
        return "NO_ACTIVE_COVERAGE"
    if row["active_maintenance_crew_count"] <= 0 and row["maintenance_level"] != "LIGHT":
        return "NO_ACTIVE_COVERAGE"
    if row["active_maintenance_crew_count"] <= 1:
        return "LIMITED_COVERAGE"
    return "COVERED"


def _util_status(value: float) -> str:
    if value > 95:
        return "OVERLOADED"
    if value > 80:
        return "HIGH_UTILIZATION_WARNING"
    return "FEASIBLE"


def _risk_points(level: str) -> float:
    return {"LOW": 0, "MEDIUM": 15, "HIGH": 30, "CRITICAL": 45, "REVIEW_REQUIRED": 50}.get(str(level), 10)


def _queue_level(score: float) -> str:
    if score >= 90:
        return "CRITICAL"
    if score >= 65:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def _worst_readiness(values: pd.Series) -> str:
    values = [str(v) for v in values.dropna()]
    if not values:
        return "REVIEW_REQUIRED"
    if "REVIEW_REQUIRED" in values:
        return "REVIEW_REQUIRED"
    if any(v != "READY" for v in values):
        return values[0]
    return "READY"


def _worst_due(values: pd.Series) -> str:
    order = {"NOT_DUE": 0, "DUE_SOON": 1, "DUE_NOW": 2, "OVERDUE": 3, "REVIEW_REQUIRED": 4}
    vals = [str(v) for v in values.dropna()]
    return max(vals, key=lambda v: order.get(v, 0)) if vals else "REVIEW_REQUIRED"


def _highest_risk(values: pd.Series) -> str:
    vals = [str(v) for v in values.dropna()]
    return max(vals, key=lambda v: RISK_ORDER.get(v, 0)) if vals else "LOW"


def _review(item: int, issue_type: str, severity: str, machine_id: str, crew_id: str, skill_id: str, description: str, action: str) -> dict:
    return {
        "review_item_id": f"MCC-REV-{item:04d}",
        "planning_run_id": _planning_run_id(),
        "issue_type": issue_type,
        "issue_severity": severity,
        "machine_id": machine_id,
        "crew_id": crew_id,
        "required_skill_id": skill_id,
        "issue_description": description,
        "recommended_review_action": action,
        "auto_action_allowed": False,
        "advisory_only_flag": True,
    }


def _planning_run_id() -> str:
    if os.environ.get("INTEGRATED_RUN_ID"):
        return os.environ["INTEGRATED_RUN_ID"]
    if MPS_FILE.exists():
        try:
            frame = pd.read_csv(MPS_FILE, usecols=["planning_run_id"])
            values = frame["planning_run_id"].dropna().astype(str).str.strip()
            if not values.empty:
                return values.iloc[0]
        except ValueError:
            pass
    return f"SHARED-MAINT-CREW-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


def _load_csv(path: Path, name: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"maintenance_crew_{name}_exists", f"{name} exists", "FAIL", f"Missing file: {path}", 1))
        return None
    frame = pd.read_csv(path, keep_default_na=False)
    checks.append(_result(f"maintenance_crew_{name}_exists", f"{name} exists", "PASS", f"Loaded {path}", 0))
    if frame.empty:
        checks.append(_result(f"maintenance_crew_{name}_not_empty", f"{name} not empty", "FAIL", f"{name} has no rows.", 1))
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
    validation, *_ = build_maintenance_crew_capacity_outputs()
    print(f"Maintenance crew capacity validation rows: {len(validation)}")
    print(f"Maintenance crew capacity validation status counts: {validation['status'].value_counts().to_dict() if not validation.empty else {}}")
