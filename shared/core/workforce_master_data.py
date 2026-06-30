"""Validate shared workforce master data and build advisory workforce contexts."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = PROJECT_ROOT / "shared"
DATA_DIR = SHARED_DIR / "data"
OUTPUT_DIR = SHARED_DIR / "outputs"
PHASE4_DIR = PROJECT_ROOT / "phase 4"
PHASE4_OUTPUT_DIR = PHASE4_DIR / "outputs"

CREWS_FILE = DATA_DIR / "workforce_crews.csv"
SKILLS_FILE = DATA_DIR / "workforce_skills.csv"
SKILL_MATRIX_FILE = DATA_DIR / "crew_skill_matrix.csv"
MACHINE_AUTH_FILE = DATA_DIR / "crew_machine_authorizations.csv"
CREW_CALENDAR_FILE = DATA_DIR / "crew_calendar.csv"
CREW_COST_FILE = DATA_DIR / "crew_cost_rates.csv"
PHASE4_MACHINES_FILE = PHASE4_DIR / "data" / "machines.csv"
PHASE4_MPS_FILE = PHASE4_OUTPUT_DIR / "phase4_master_production_schedule.csv"

VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "workforce_crew_validation.csv"
CREW_CAPACITY_CONTEXT_FILE = OUTPUT_DIR / "workforce_crew_capacity_context.csv"
MACHINE_AUTH_CONTEXT_FILE = OUTPUT_DIR / "workforce_machine_authorization_context.csv"
SKILL_COVERAGE_SUMMARY_FILE = OUTPUT_DIR / "workforce_skill_coverage_summary.csv"
MANAGER_REVIEW_QUEUE_FILE = OUTPUT_DIR / "workforce_manager_review_queue.csv"
PHASE4_WORKFORCE_CONTEXT_FILE = PHASE4_OUTPUT_DIR / "phase4_workforce_resource_context.csv"

SOURCE_PHASE = "SHARED_STEP7A_WORKFORCE_MASTER_DATA"
WORKFORCE_CONTEXT_BASIS = "SHARED_WORKFORCE_CREW_SKILL_MATRIX"
ALLOWED_CREW_TYPES = {"PRODUCTION", "MAINTENANCE", "WAREHOUSE", "DELIVERY", "QUALITY", "SHARED", "SUPERVISORY"}
ACTIVE_CREW_TYPES = {"PRODUCTION", "MAINTENANCE"}
PRODUCTION_OPERATION_SKILL_CATEGORIES = {"PRODUCTION_OPERATION", "MACHINE_SETUP", "QUALITY_INSPECTION", "SAFETY"}
LIGHT_AUTONOMOUS_MAINTENANCE_CATEGORIES = {"LIGHT_AUTONOMOUS_MAINTENANCE"}
MEDIUM_HEAVY_MAINTENANCE_CATEGORIES = {"MEDIUM_MAINTENANCE", "HEAVY_MAINTENANCE"}
REPAIR_SKILL_CATEGORIES = {"CORRECTIVE_REPAIR", "ELECTRICAL_MAINTENANCE"}
MAINTENANCE_SKILL_CATEGORIES = {
    "LIGHT_AUTONOMOUS_MAINTENANCE",
    "MECHANICAL_MAINTENANCE",
    "ELECTRICAL_MAINTENANCE",
    "GENERAL_MAINTENANCE",
    "MEDIUM_MAINTENANCE",
    "HEAVY_MAINTENANCE",
    "CORRECTIVE_REPAIR",
    "SAFETY",
}
PRODUCTION_FORBIDDEN_MAINTENANCE_CATEGORIES = {
    "MEDIUM_MAINTENANCE",
    "HEAVY_MAINTENANCE",
    "CORRECTIVE_REPAIR",
    "ELECTRICAL_MAINTENANCE",
    "MECHANICAL_MAINTENANCE",
    "GENERAL_MAINTENANCE",
}
VALID_SKILL_LEVELS = {"BASIC", "INTERMEDIATE", "ADVANCED", "EXPERT"}
VALID_AUTH_SCOPES = {"OPERATE", "SETUP", "MAINTAIN", "REPAIR", "OPERATE_AND_SETUP", "MAINTAIN_AND_REPAIR", "LIGHT_AUTONOMOUS_MAINTENANCE"}
VALID_MAINT_LEVELS = {"NONE", "LIGHT", "MEDIUM", "HEAVY", "FULL"}
VALID_CALENDAR_TYPES = {"NORMAL_SHIFT", "MAINTENANCE_COVERAGE", "FUTURE_PLACEHOLDER"}


def build_workforce_master_data_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Validate shared workforce data and write advisory context outputs."""
    checks: list[dict] = []
    frames = {
        "crews": _load_csv(CREWS_FILE, "workforce_crews", checks),
        "skills": _load_csv(SKILLS_FILE, "workforce_skills", checks),
        "skill_matrix": _load_csv(SKILL_MATRIX_FILE, "crew_skill_matrix", checks),
        "machine_auth": _load_csv(MACHINE_AUTH_FILE, "crew_machine_authorizations", checks),
        "crew_calendar": _load_csv(CREW_CALENDAR_FILE, "crew_calendar", checks),
        "crew_cost": _load_csv(CREW_COST_FILE, "crew_cost_rates", checks),
        "phase4_machines": _load_csv(PHASE4_MACHINES_FILE, "phase4_machines", checks),
    }
    crew_capacity = pd.DataFrame()
    machine_context = pd.DataFrame()
    skill_summary = pd.DataFrame()
    review = pd.DataFrame()
    phase4_context = pd.DataFrame()
    if all(frame is not None for frame in frames.values()):
        _validate_master_data(frames, checks)
        crew_capacity = _build_crew_capacity_context(frames["crews"], frames["crew_cost"])
        machine_context = _build_machine_authorization_context(frames["crews"], frames["machine_auth"])
        skill_summary = _build_skill_coverage_summary(frames["skills"], frames["skill_matrix"], frames["crews"])
        review = _build_manager_review_queue(frames, skill_summary)
        phase4_context = _build_phase4_workforce_context(frames["crews"], frames["skill_matrix"], frames["skills"], frames["machine_auth"])
        _validate_outputs(crew_capacity, machine_context, skill_summary, review, phase4_context, checks)
    _check_no_blocked_outputs(checks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PHASE4_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    crew_capacity.to_csv(CREW_CAPACITY_CONTEXT_FILE, index=False)
    machine_context.to_csv(MACHINE_AUTH_CONTEXT_FILE, index=False)
    skill_summary.to_csv(SKILL_COVERAGE_SUMMARY_FILE, index=False)
    review.to_csv(MANAGER_REVIEW_QUEUE_FILE, index=False)
    phase4_context.to_csv(PHASE4_WORKFORCE_CONTEXT_FILE, index=False)
    return validation, crew_capacity, machine_context, skill_summary, review, phase4_context


def _validate_master_data(frames: dict[str, pd.DataFrame], checks: list[dict]) -> None:
    required = {
        "crews": {"crew_id", "crew_name", "crew_type", "crew_group", "primary_work_area", "workers_available", "default_shift_hours_per_day", "default_workdays_per_week", "weekly_capacity_hours", "soft_utilization_threshold_pct", "hard_utilization_threshold_pct", "hourly_wage", "active_flag", "future_use_allowed_flag", "notes"},
        "skills": {"skill_id", "skill_name", "skill_category", "skill_description", "applies_to_crew_type", "certification_required_flag", "active_flag", "future_use_allowed_flag", "notes"},
        "skill_matrix": {"crew_id", "skill_id", "skill_level", "certified_flag", "can_work_unsupervised_flag", "max_hours_per_week_for_skill", "cross_trained_flag", "primary_skill_flag", "active_flag", "notes"},
        "machine_auth": {"crew_id", "machine_id", "machine_type", "authorization_scope", "can_operate_flag", "can_setup_flag", "can_maintain_flag", "can_repair_flag", "maintenance_level_authorized", "authorization_level", "certification_required_flag", "certified_flag", "active_flag", "notes"},
        "crew_calendar": {"calendar_id", "crew_id", "weekday", "shift_start", "shift_end", "planned_break_minutes", "available_flag", "calendar_type", "notes"},
        "crew_cost": {"crew_id", "standard_hourly_cost", "overtime_hourly_cost", "maintenance_callout_cost", "currency", "effective_from", "active_flag", "notes"},
    }
    for name, columns in required.items():
        missing = sorted(columns.difference(frames[name].columns))
        checks.append(_result(f"workforce_{name}_required_columns", f"{name} required columns", "FAIL" if missing else "PASS", f"Missing columns: {missing}" if missing else f"{name} has required columns.", len(missing)))

    crews = frames["crews"]
    skills = frames["skills"]
    matrix = frames["skill_matrix"]
    auth = frames["machine_auth"]
    calendar = frames["crew_calendar"]
    cost = frames["crew_cost"]
    machines = frames["phase4_machines"]

    _check_unique(crews, "crew_id", "workforce_crews_unique", checks)
    _check_unique(skills, "skill_id", "workforce_skills_unique", checks)
    _check_refs(matrix, "crew_id", crews, "crew_id", "skill_matrix_crew_refs", checks)
    _check_refs(matrix, "skill_id", skills, "skill_id", "skill_matrix_skill_refs", checks)
    _check_refs(auth, "crew_id", crews, "crew_id", "machine_auth_crew_refs", checks)
    _check_refs(auth, "machine_id", machines, "machine_id", "machine_auth_machine_refs", checks)
    _check_refs(calendar, "crew_id", crews, "crew_id", "crew_calendar_crew_refs", checks)
    _check_refs(cost, "crew_id", crews, "crew_id", "crew_cost_crew_refs", checks)

    active_crews = crews[_to_bool(crews["active_flag"])].copy()
    inactive_crews = crews[~_to_bool(crews["active_flag"])].copy()
    invalid_active_type = active_crews[~active_crews["crew_type"].astype(str).isin(ACTIVE_CREW_TYPES)]
    checks.append(_result("workforce_active_crew_types", "active crews are production or maintenance", "FAIL" if not invalid_active_type.empty else "PASS", f"Invalid active crew types: {invalid_active_type['crew_id'].tolist()}" if not invalid_active_type.empty else "Active crews are limited to PRODUCTION and MAINTENANCE.", len(invalid_active_type)))
    future_active = inactive_crews[inactive_crews["crew_type"].astype(str).isin(ALLOWED_CREW_TYPES - ACTIVE_CREW_TYPES) & ~_to_bool(inactive_crews["future_use_allowed_flag"])]
    checks.append(_result("workforce_future_crew_inactive", "future crew types inactive", "FAIL" if not future_active.empty else "PASS", "Future crew placeholders are inactive and future-use allowed." if future_active.empty else f"Future crew placeholders missing future flag: {future_active['crew_id'].tolist()}", len(future_active)))
    invalid_crew_type = crews[~crews["crew_type"].astype(str).isin(ALLOWED_CREW_TYPES)]
    checks.append(_result("workforce_allowed_crew_types", "crew types allowed", "FAIL" if not invalid_crew_type.empty else "PASS", "Crew types are in the allowed list." if invalid_crew_type.empty else f"Invalid crew types: {invalid_crew_type['crew_type'].tolist()}", len(invalid_crew_type)))

    _check_nonnegative(crews, ["workers_available", "default_shift_hours_per_day", "default_workdays_per_week", "weekly_capacity_hours", "soft_utilization_threshold_pct", "hard_utilization_threshold_pct", "hourly_wage"], "workforce_crew_numeric_nonnegative", checks)
    _check_nonnegative(matrix, ["max_hours_per_week_for_skill"], "workforce_skill_hours_nonnegative", checks)
    _check_nonnegative(cost, ["standard_hourly_cost", "overtime_hourly_cost", "maintenance_callout_cost"], "workforce_cost_nonnegative", checks)
    _check_nonnegative(calendar, ["planned_break_minutes"], "workforce_calendar_breaks_nonnegative", checks)

    invalid_levels = matrix[~matrix["skill_level"].astype(str).isin(VALID_SKILL_LEVELS)]
    checks.append(_result("workforce_skill_levels_valid", "skill levels valid", "FAIL" if not invalid_levels.empty else "PASS", "Skill levels are valid." if invalid_levels.empty else f"Invalid skill levels: {invalid_levels['skill_level'].tolist()}", len(invalid_levels)))
    invalid_scope = auth[~auth["authorization_scope"].astype(str).isin(VALID_AUTH_SCOPES)]
    checks.append(_result("workforce_authorization_scopes_valid", "authorization scopes valid", "FAIL" if not invalid_scope.empty else "PASS", "Authorization scopes are valid.", len(invalid_scope)))
    invalid_maint_level = auth[~auth["maintenance_level_authorized"].astype(str).isin(VALID_MAINT_LEVELS)]
    checks.append(_result("workforce_maintenance_levels_valid", "maintenance levels valid", "FAIL" if not invalid_maint_level.empty else "PASS", "Maintenance authorization levels are valid.", len(invalid_maint_level)))
    invalid_calendar_type = calendar[~calendar["calendar_type"].astype(str).isin(VALID_CALENDAR_TYPES)]
    checks.append(_result("workforce_calendar_types_valid", "calendar types valid", "FAIL" if not invalid_calendar_type.empty else "PASS", "Calendar types are valid.", len(invalid_calendar_type)))

    production_skill_issue, maintenance_skill_issue = _crew_skill_type_issues(crews, skills, matrix)
    checks.append(_result("workforce_production_crews_have_production_skills", "production crews have production skills", "FAIL" if production_skill_issue else "PASS", f"Production crews missing production skills: {production_skill_issue}" if production_skill_issue else "Production crews have production skills.", len(production_skill_issue)))
    checks.append(_result("workforce_maintenance_crews_have_maintenance_skills", "maintenance crews have maintenance skills", "FAIL" if maintenance_skill_issue else "PASS", f"Maintenance crews missing maintenance skills: {maintenance_skill_issue}" if maintenance_skill_issue else "Maintenance crews have maintenance skills.", len(maintenance_skill_issue)))

    active_skill_detail = (
        matrix[_to_bool(matrix["active_flag"])]
        .merge(crews[["crew_id", "crew_type"]], on="crew_id", how="left")
        .merge(skills[["skill_id", "skill_category", "active_flag"]], on="skill_id", how="left")
    )
    production_forbidden_skills = active_skill_detail[
        (active_skill_detail["crew_type"] == "PRODUCTION")
        & active_skill_detail["skill_category"].astype(str).isin(PRODUCTION_FORBIDDEN_MAINTENANCE_CATEGORIES)
    ]
    production_light_skills = active_skill_detail[
        (active_skill_detail["crew_type"] == "PRODUCTION")
        & active_skill_detail["skill_category"].astype(str).isin(LIGHT_AUTONOMOUS_MAINTENANCE_CATEGORIES)
    ]
    maintenance_production_skills = active_skill_detail[
        (active_skill_detail["crew_type"] == "MAINTENANCE")
        & active_skill_detail["skill_category"].astype(str).isin(PRODUCTION_OPERATION_SKILL_CATEGORIES)
    ]
    general_as_production = active_skill_detail[
        (active_skill_detail["crew_type"] == "PRODUCTION")
        & (active_skill_detail["skill_category"].astype(str) == "GENERAL_MAINTENANCE")
    ]
    checks.append(_result("workforce_production_light_autonomous_maintenance_allowed", "production light autonomous maintenance allowed", "PASS", f"Production light autonomous maintenance assignments: {len(production_light_skills)}", len(production_light_skills)))
    checks.append(_result("workforce_production_no_medium_heavy_or_repair_skills", "production crews have no medium heavy or repair skills", "FAIL" if not production_forbidden_skills.empty else "PASS", "Production crews have no medium/heavy/repair/electrical/general maintenance skills." if production_forbidden_skills.empty else f"Forbidden production crew skills: {production_forbidden_skills[['crew_id','skill_id','skill_category']].to_dict('records')}", len(production_forbidden_skills)))
    checks.append(_result("workforce_maintenance_not_production_skill_crews", "maintenance crews not production operators by skill", "FAIL" if not maintenance_production_skills.empty else "PASS", "Maintenance crews have no production operation skills." if maintenance_production_skills.empty else f"Maintenance crews have production skills: {maintenance_production_skills[['crew_id','skill_id']].to_dict('records')}", len(maintenance_production_skills)))
    checks.append(_result("workforce_general_maintenance_not_production", "general maintenance treated as maintenance", "FAIL" if not general_as_production.empty else "PASS", "GENERAL_MAINTENANCE is not assigned to production crews.", len(general_as_production)))

    active_auth = auth[_to_bool(auth["active_flag"])].merge(crews[["crew_id", "crew_type"]], on="crew_id", how="left")
    production_repair = active_auth[(active_auth["crew_type"] == "PRODUCTION") & _to_bool(active_auth["can_repair_flag"])]
    production_bad_maintain = active_auth[
        (active_auth["crew_type"] == "PRODUCTION")
        & _to_bool(active_auth["can_maintain_flag"])
        & (active_auth["maintenance_level_authorized"].astype(str) != "LIGHT")
    ]
    production_medium_heavy_auth = active_auth[
        (active_auth["crew_type"] == "PRODUCTION")
        & active_auth["maintenance_level_authorized"].astype(str).isin({"MEDIUM", "HEAVY", "FULL"})
    ]
    maintenance_operate = active_auth[(active_auth["crew_type"] == "MAINTENANCE") & (_to_bool(active_auth["can_operate_flag"]) | _to_bool(active_auth["can_setup_flag"]))]
    checks.append(_result("workforce_production_not_repair_crews", "production crews not repair crews", "FAIL" if not production_repair.empty else "PASS", "Production crews have no repair authorization." if production_repair.empty else f"Production crews have repair authorization: {production_repair['crew_id'].tolist()}", len(production_repair)))
    checks.append(_result("workforce_production_maintain_light_only", "production crews maintain light only", "FAIL" if not production_bad_maintain.empty else "PASS", "Production crews with maintain authorization are limited to LIGHT.", len(production_bad_maintain)))
    checks.append(_result("workforce_production_no_medium_heavy_machine_auth", "production crews no medium heavy machine authorization", "FAIL" if not production_medium_heavy_auth.empty else "PASS", "Production crews have no MEDIUM/HEAVY/FULL maintenance machine authorization.", len(production_medium_heavy_auth)))
    checks.append(_result("workforce_maintenance_not_production_operators", "maintenance crews not production operators", "FAIL" if not maintenance_operate.empty else "PASS", "Maintenance crews are not marked as production operators." if maintenance_operate.empty else f"Maintenance crews have operate/setup authorization: {maintenance_operate['crew_id'].tolist()}", len(maintenance_operate)))
    cert_issues = _certification_issues(skills, matrix, auth)
    checks.append(_result("workforce_certification_requirements_respected", "certification requirements respected", "FAIL" if cert_issues else "PASS", "Certification requirements are respected." if not cert_issues else f"Certification issues: {cert_issues}", len(cert_issues)))
    shift_issues = _shift_time_issues(calendar)
    checks.append(_result("workforce_shift_times_valid", "shift times valid", "FAIL" if shift_issues else "PASS", "Crew shift times are valid where available." if not shift_issues else f"Invalid shift rows: {shift_issues}", len(shift_issues)))


def _build_crew_capacity_context(crews: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    active_cost = cost[_to_bool(cost["active_flag"])].drop_duplicates("crew_id")
    context = crews.merge(active_cost[["crew_id", "standard_hourly_cost", "overtime_hourly_cost"]], on="crew_id", how="left")
    context["standard_hourly_cost"] = pd.to_numeric(context["standard_hourly_cost"], errors="coerce").fillna(0)
    context["overtime_hourly_cost"] = pd.to_numeric(context["overtime_hourly_cost"], errors="coerce").fillna(0)
    context["source_phase"] = SOURCE_PHASE
    context["advisory_only_flag"] = True
    return context[["crew_id", "crew_name", "crew_type", "workers_available", "weekly_capacity_hours", "soft_utilization_threshold_pct", "hard_utilization_threshold_pct", "standard_hourly_cost", "overtime_hourly_cost", "active_flag", "future_use_allowed_flag", "source_phase", "advisory_only_flag"]].copy()


def _build_machine_authorization_context(crews: pd.DataFrame, auth: pd.DataFrame) -> pd.DataFrame:
    context = auth.merge(crews[["crew_id", "crew_name", "crew_type"]], on="crew_id", how="left")
    context["source_phase"] = SOURCE_PHASE
    context["advisory_only_flag"] = True
    return context[["crew_id", "crew_name", "crew_type", "machine_id", "machine_type", "can_operate_flag", "can_setup_flag", "can_maintain_flag", "can_repair_flag", "maintenance_level_authorized", "authorization_level", "certified_flag", "source_phase", "advisory_only_flag"]].copy()


def _build_skill_coverage_summary(skills: pd.DataFrame, matrix: pd.DataFrame, crews: pd.DataFrame) -> pd.DataFrame:
    active_matrix = matrix[_to_bool(matrix["active_flag"])].merge(crews[["crew_id", "crew_type", "active_flag"]], on="crew_id", how="left")
    active_matrix = active_matrix[_to_bool(active_matrix["active_flag_y"])]
    active_matrix["max_hours_per_week_for_skill"] = pd.to_numeric(active_matrix["max_hours_per_week_for_skill"], errors="coerce").fillna(0)
    grouped = active_matrix.groupby("skill_id", as_index=False).agg(
        active_crew_count=("crew_id", "nunique"),
        production_crew_count=("crew_type", lambda s: int((s == "PRODUCTION").sum())),
        maintenance_crew_count=("crew_type", lambda s: int((s == "MAINTENANCE").sum())),
        total_max_skill_hours_per_week=("max_hours_per_week_for_skill", "sum"),
    )
    summary = skills.merge(grouped, on="skill_id", how="left")
    for column in ["active_crew_count", "production_crew_count", "maintenance_crew_count", "total_max_skill_hours_per_week"]:
        summary[column] = pd.to_numeric(summary[column], errors="coerce").fillna(0)
    summary["coverage_status"] = summary.apply(_coverage_status, axis=1)
    summary["source_phase"] = SOURCE_PHASE
    summary["advisory_only_flag"] = True
    return summary[["skill_id", "skill_name", "skill_category", "active_crew_count", "production_crew_count", "maintenance_crew_count", "total_max_skill_hours_per_week", "certification_required_flag", "coverage_status", "source_phase", "advisory_only_flag"]].copy()


def _build_manager_review_queue(frames: dict[str, pd.DataFrame], skill_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    item = 1
    for _, row in skill_summary[skill_summary["coverage_status"].isin(["NO_ACTIVE_COVERAGE", "LIMITED_COVERAGE", "REVIEW_REQUIRED"])].iterrows():
        rows.append(_review_row(item, "SKILL_COVERAGE_REVIEW", "HIGH" if row["coverage_status"] == "NO_ACTIVE_COVERAGE" else "MEDIUM", "", row["skill_id"], "", f"Skill {row['skill_id']} coverage status is {row['coverage_status']}.", "REVIEW_CREW_SKILL_COVERAGE"))
        item += 1
    crews = frames["crews"]
    matrix = frames["skill_matrix"]
    calendar = frames["crew_calendar"]
    cost = frames["crew_cost"]
    active_crews = crews[_to_bool(crews["active_flag"])]
    for _, crew in active_crews.iterrows():
        crew_id = crew["crew_id"]
        if matrix[(matrix["crew_id"] == crew_id) & _to_bool(matrix["active_flag"])].empty:
            rows.append(_review_row(item, "ACTIVE_CREW_WITH_NO_SKILLS", "HIGH", crew_id, "", "", f"Active crew {crew_id} has no active skill assignment.", "ADD_OR_REVIEW_CREW_SKILLS"))
            item += 1
        if calendar[(calendar["crew_id"] == crew_id) & _to_bool(calendar["available_flag"])].empty:
            rows.append(_review_row(item, "ACTIVE_CREW_WITH_NO_CALENDAR", "HIGH", crew_id, "", "", f"Active crew {crew_id} has no available calendar rows.", "ADD_OR_REVIEW_CREW_CALENDAR"))
            item += 1
        if cost[(cost["crew_id"] == crew_id) & _to_bool(cost["active_flag"])].empty:
            rows.append(_review_row(item, "ACTIVE_CREW_WITH_NO_COST_RATE", "MEDIUM", crew_id, "", "", f"Active crew {crew_id} has no active cost rate.", "ADD_OR_REVIEW_CREW_COST_RATE"))
            item += 1
    future_active = crews[_to_bool(crews["active_flag"]) & crews["crew_type"].isin(ALLOWED_CREW_TYPES - ACTIVE_CREW_TYPES)]
    for _, crew in future_active.iterrows():
        rows.append(_review_row(item, "FUTURE_CREW_TYPE_ACTIVE", "HIGH", crew["crew_id"], "", "", f"Future crew type {crew['crew_type']} is active in Step 7A.", "DEACTIVATE_OR_REVIEW_FUTURE_CREW_TYPE"))
        item += 1
    return pd.DataFrame(rows, columns=["review_item_id", "issue_type", "issue_severity", "crew_id", "skill_id", "machine_id", "issue_description", "recommended_review_action", "auto_action_allowed", "advisory_only_flag"])


def _build_phase4_workforce_context(crews: pd.DataFrame, matrix: pd.DataFrame, skills: pd.DataFrame, auth: pd.DataFrame) -> pd.DataFrame:
    active_crews = crews[_to_bool(crews["active_flag"]) & crews["crew_type"].isin(ACTIVE_CREW_TYPES)].copy()
    skill_detail = matrix[_to_bool(matrix["active_flag"])].merge(skills[["skill_id", "skill_category"]], on="skill_id", how="left")
    skill_summary = skill_detail.groupby("crew_id", as_index=False).agg(
        production_operation_skill_count=("skill_category", lambda s: int(s.isin(PRODUCTION_OPERATION_SKILL_CATEGORIES).sum())),
        light_autonomous_maintenance_skill_count=("skill_category", lambda s: int(s.isin(LIGHT_AUTONOMOUS_MAINTENANCE_CATEGORIES).sum())),
        maintenance_skill_count=("skill_category", lambda s: int(s.isin(MAINTENANCE_SKILL_CATEGORIES).sum())),
        medium_heavy_maintenance_skill_count=("skill_category", lambda s: int(s.isin(MEDIUM_HEAVY_MAINTENANCE_CATEGORIES).sum())),
        repair_skill_count=("skill_category", lambda s: int(s.isin(REPAIR_SKILL_CATEGORIES).sum())),
    )
    active_auth = auth[_to_bool(auth["active_flag"])].copy()
    active_auth["_can_light_maintain"] = _to_bool(active_auth["can_maintain_flag"]) & active_auth["maintenance_level_authorized"].astype(str).eq("LIGHT")
    active_auth["_can_medium_heavy_maintain"] = _to_bool(active_auth["can_maintain_flag"]) & active_auth["maintenance_level_authorized"].astype(str).isin({"MEDIUM", "HEAVY", "FULL"})
    active_auth["_can_repair"] = _to_bool(active_auth["can_repair_flag"])
    auth_summary = active_auth.groupby("crew_id", as_index=False).agg(
        authorized_machine_count=("machine_id", "nunique"),
        can_operate_machine_count=("can_operate_flag", lambda s: int(_to_bool(s).sum())),
        can_setup_machine_count=("can_setup_flag", lambda s: int(_to_bool(s).sum())),
        can_maintain_machine_count=("can_maintain_flag", lambda s: int(_to_bool(s).sum())),
        can_repair_machine_count=("can_repair_flag", lambda s: int(_to_bool(s).sum())),
        authorized_light_maintenance_machine_count=("_can_light_maintain", "sum"),
        authorized_medium_heavy_maintenance_machine_count=("_can_medium_heavy_maintain", "sum"),
        authorized_repair_machine_count=("_can_repair", "sum"),
    )
    context = active_crews.merge(skill_summary, on="crew_id", how="left").merge(auth_summary, on="crew_id", how="left")
    count_columns = [
        "production_operation_skill_count",
        "light_autonomous_maintenance_skill_count",
        "maintenance_skill_count",
        "medium_heavy_maintenance_skill_count",
        "repair_skill_count",
        "authorized_machine_count",
        "can_operate_machine_count",
        "can_setup_machine_count",
        "can_maintain_machine_count",
        "can_repair_machine_count",
        "authorized_light_maintenance_machine_count",
        "authorized_medium_heavy_maintenance_machine_count",
        "authorized_repair_machine_count",
    ]
    for column in count_columns:
        context[column] = pd.to_numeric(context[column], errors="coerce").fillna(0).astype(int)
    context["crew_role_separation_status"] = context.apply(_crew_role_separation_status, axis=1)
    context["planning_run_id"] = _planning_run_id()
    context["workforce_context_basis"] = WORKFORCE_CONTEXT_BASIS
    context["source_phase"] = SOURCE_PHASE
    context["advisory_only_flag"] = True
    return context[
        [
            "planning_run_id",
            "crew_id",
            "crew_name",
            "crew_type",
            "workers_available",
            "weekly_capacity_hours",
            "production_operation_skill_count",
            "light_autonomous_maintenance_skill_count",
            "maintenance_skill_count",
            "medium_heavy_maintenance_skill_count",
            "repair_skill_count",
            "authorized_machine_count",
            "can_operate_machine_count",
            "can_setup_machine_count",
            "can_maintain_machine_count",
            "can_repair_machine_count",
            "authorized_light_maintenance_machine_count",
            "authorized_medium_heavy_maintenance_machine_count",
            "authorized_repair_machine_count",
            "active_flag",
            "future_use_allowed_flag",
            "crew_role_separation_status",
            "workforce_context_basis",
            "source_phase",
            "advisory_only_flag",
        ]
    ].copy()


def _crew_role_separation_status(row: pd.Series) -> str:
    crew_type = str(row.get("crew_type", ""))
    if crew_type == "PRODUCTION":
        if int(row.get("medium_heavy_maintenance_skill_count", 0)) or int(row.get("repair_skill_count", 0)):
            return "REVIEW_REQUIRED"
        if int(row.get("authorized_medium_heavy_maintenance_machine_count", 0)) or int(row.get("authorized_repair_machine_count", 0)):
            return "REVIEW_REQUIRED"
        return "OK"
    if crew_type == "MAINTENANCE":
        if int(row.get("production_operation_skill_count", 0)):
            return "REVIEW_REQUIRED"
        if int(row.get("can_operate_machine_count", 0)) or int(row.get("can_setup_machine_count", 0)):
            return "WARNING"
        return "OK"
    return "WARNING"


def _validate_outputs(crew_capacity: pd.DataFrame, machine_context: pd.DataFrame, skill_summary: pd.DataFrame, review: pd.DataFrame, phase4_context: pd.DataFrame, checks: list[dict]) -> None:
    invalid = int(crew_capacity.empty) + int(machine_context.empty) + int(skill_summary.empty) + int(phase4_context.empty)
    for frame in [crew_capacity, machine_context, skill_summary, phase4_context]:
        invalid += int((~_to_bool(frame["advisory_only_flag"])).sum()) if "advisory_only_flag" in frame.columns else len(frame)
    if not review.empty:
        invalid += int(_to_bool(review["auto_action_allowed"]).sum())
        invalid += int((~_to_bool(review["advisory_only_flag"])).sum())
    basis_bad = 0 if phase4_context.empty else int((phase4_context["workforce_context_basis"].astype(str) != WORKFORCE_CONTEXT_BASIS).sum())
    invalid += basis_bad
    if not phase4_context.empty:
        invalid += int((phase4_context["crew_role_separation_status"].astype(str) == "REVIEW_REQUIRED").sum())
    checks.append(_result("workforce_context_outputs_valid", "workforce context outputs valid", "FAIL" if invalid else "PASS", f"Invalid workforce context values: {invalid}" if invalid else "Workforce context outputs are valid and advisory-only.", invalid))


def _check_unique(df: pd.DataFrame, column: str, check_id: str, checks: list[dict]) -> None:
    duplicated = int(df[column].astype(str).duplicated().sum())
    checks.append(_result(check_id, f"{column} unique", "FAIL" if duplicated else "PASS", f"Duplicate {column} rows: {duplicated}", duplicated))


def _check_refs(child: pd.DataFrame, child_column: str, parent: pd.DataFrame, parent_column: str, check_id: str, checks: list[dict]) -> None:
    missing = sorted(set(child[child_column].dropna().astype(str)) - set(parent[parent_column].dropna().astype(str)))
    checks.append(_result(check_id, f"{child_column} references valid", "FAIL" if missing else "PASS", f"Missing references: {missing}" if missing else f"{child_column} references are valid.", len(missing)))


def _check_nonnegative(df: pd.DataFrame, columns: list[str], check_id: str, checks: list[dict]) -> None:
    bad = 0
    for column in columns:
        values = pd.to_numeric(df[column], errors="coerce")
        bad += int(values.isna().sum()) + int((values < 0).sum())
    checks.append(_result(check_id, "numeric fields non-negative", "FAIL" if bad else "PASS", f"Invalid numeric values: {bad}" if bad else "Numeric fields are non-negative.", bad))


def _crew_skill_type_issues(crews: pd.DataFrame, skills: pd.DataFrame, matrix: pd.DataFrame) -> tuple[list[str], list[str]]:
    active_crews = crews[_to_bool(crews["active_flag"])]
    active_matrix = matrix[_to_bool(matrix["active_flag"])].merge(skills[["skill_id", "skill_category"]], on="skill_id", how="left")
    production_missing = []
    maintenance_missing = []
    for _, crew in active_crews.iterrows():
        categories = set(active_matrix.loc[active_matrix["crew_id"] == crew["crew_id"], "skill_category"].astype(str))
        if crew["crew_type"] == "PRODUCTION" and not categories.intersection(PRODUCTION_OPERATION_SKILL_CATEGORIES):
            production_missing.append(crew["crew_id"])
        if crew["crew_type"] == "MAINTENANCE" and not categories.intersection(MAINTENANCE_SKILL_CATEGORIES):
            maintenance_missing.append(crew["crew_id"])
    return production_missing, maintenance_missing


def _certification_issues(skills: pd.DataFrame, matrix: pd.DataFrame, auth: pd.DataFrame) -> list[str]:
    issues = []
    certified_skills = matrix.merge(skills[["skill_id", "certification_required_flag"]], on="skill_id", how="left")
    bad_skill = certified_skills[_to_bool(certified_skills["active_flag"]) & _to_bool(certified_skills["certification_required_flag"]) & ~_to_bool(certified_skills["certified_flag"])]
    issues.extend(f"skill:{row.crew_id}:{row.skill_id}" for row in bad_skill.itertuples())
    bad_auth = auth[_to_bool(auth["active_flag"]) & _to_bool(auth["certification_required_flag"]) & ~_to_bool(auth["certified_flag"])]
    issues.extend(f"machine:{row.crew_id}:{row.machine_id}" for row in bad_auth.itertuples())
    return issues


def _shift_time_issues(calendar: pd.DataFrame) -> list[str]:
    issues = []
    available = calendar[_to_bool(calendar["available_flag"])]
    for row in available.itertuples():
        try:
            start = datetime.strptime(str(row.shift_start), "%H:%M")
            end = datetime.strptime(str(row.shift_end), "%H:%M")
            if end <= start:
                issues.append(str(row.calendar_id))
        except ValueError:
            issues.append(str(row.calendar_id))
    return issues


def _coverage_status(row: pd.Series) -> str:
    if not _bool_value(row.get("active_flag", False)):
        category = str(row.get("skill_category", ""))
        future_allowed = _bool_value(row.get("future_use_allowed_flag", False))
        if future_allowed or category in {"FUTURE_WAREHOUSE", "FUTURE_DELIVERY"}:
            return "FUTURE_INACTIVE_NOT_REQUIRED"
        return "NO_ACTIVE_COVERAGE"
    count = int(row["active_crew_count"])
    hours = float(row["total_max_skill_hours_per_week"])
    if count == 0:
        return "NO_ACTIVE_COVERAGE"
    if count == 1 or hours < 40:
        return "LIMITED_COVERAGE"
    return "COVERED"


def _review_row(item: int, issue_type: str, severity: str, crew_id: str, skill_id: str, machine_id: str, description: str, action: str) -> dict:
    return {
        "review_item_id": f"WF-REV-{item:04d}",
        "issue_type": issue_type,
        "issue_severity": severity,
        "crew_id": crew_id,
        "skill_id": skill_id,
        "machine_id": machine_id,
        "issue_description": description,
        "recommended_review_action": action,
        "auto_action_allowed": False,
        "advisory_only_flag": True,
    }


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked_tokens = ["production_order", "maintenance_work_order", "purchase_order", "inventory_reservation", "finite_schedule", "dispatch_schedule", "crew_schedule", "simulation"]
    bad = []
    for folder in [OUTPUT_DIR, PHASE4_OUTPUT_DIR]:
        if not folder.exists():
            continue
        for path in folder.glob("*"):
            if path.is_file() and any(token in path.name.lower() for token in blocked_tokens):
                bad.append(str(path))
    checks.append(_result("workforce_no_blocked_outputs", "no workforce blocked outputs", "FAIL" if bad else "PASS", f"Blocked scheduling/execution outputs found: {bad}" if bad else "No workforce scheduling, work-order, simulation, or execution outputs found.", len(bad)))


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
    return f"SHARED-WORKFORCE-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


def _load_csv(path: Path, name: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"workforce_{name}_exists", f"{name} exists", "FAIL", f"Missing file: {path}", 1))
        return None
    frame = pd.read_csv(path, keep_default_na=False)
    checks.append(_result(f"workforce_{name}_exists", f"{name} exists", "PASS", f"Loaded {path}", 0))
    if frame.empty:
        checks.append(_result(f"workforce_{name}_not_empty", f"{name} not empty", "FAIL", f"{name} has no rows.", 1))
    return frame


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _bool_value(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


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
    validation, *_ = build_workforce_master_data_outputs()
    print(f"Workforce validation rows: {len(validation)}")
    print(f"Workforce validation status counts: {validation['status'].value_counts().to_dict() if not validation.empty else {}}")
