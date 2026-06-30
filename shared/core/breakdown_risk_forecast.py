"""Build advisory breakdown history, trend, and risk forecast contexts."""

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

BREAKDOWN_HISTORY_FILE = DATA_DIR / "breakdown_history.csv"
FAILURE_MODES_FILE = DATA_DIR / "machine_failure_modes.csv"
OEM_ASSUMPTIONS_FILE = DATA_DIR / "manufacturer_reliability_assumptions.csv"
MACHINES_FILE = PHASE4_DIR / "data" / "machines.csv"
SPARE_PARTS_FILE = DATA_DIR / "spare_parts_master.csv"
WORKFORCE_SKILLS_FILE = DATA_DIR / "workforce_skills.csv"
WORKFORCE_CREWS_FILE = DATA_DIR / "workforce_crews.csv"
CREW_SKILL_MATRIX_FILE = DATA_DIR / "crew_skill_matrix.csv"
WORKFORCE_AUTH_FILE = OUTPUT_DIR / "workforce_machine_authorization_context.csv"
WORKFORCE_VALIDATION_FILE = OUTPUT_DIR / "workforce_crew_validation.csv"
SPARE_VALIDATION_FILE = OUTPUT_DIR / "spare_part_validation.csv"
MAINTENANCE_VALIDATION_FILE = OUTPUT_DIR / "maintenance_plan_validation.csv"
MAINTENANCE_DUE_FILE = OUTPUT_DIR / "maintenance_due_status_context.csv"
MAINTENANCE_READINESS_FILE = PHASE4_OUTPUT_DIR / "phase4_maintenance_readiness_context.csv"
PHASE4_SPARE_CONTEXT_FILE = PHASE4_OUTPUT_DIR / "phase4_spare_part_requirement_context.csv"
QUALITY_ADJUSTED_CAPACITY_FILE = PHASE4_OUTPUT_DIR / "phase4_quality_adjusted_capacity_by_workstation.csv"
CAPACITY_LOAD_FILE = PHASE4_OUTPUT_DIR / "phase4_capacity_load_by_workstation.csv"
PHASE4_MPS_FILE = PHASE4_OUTPUT_DIR / "phase4_master_production_schedule.csv"
PHASE4_VALIDATION_FILE = PHASE4_OUTPUT_DIR / "phase4_initialization_validation.json"

BREAKDOWN_HISTORY_CLEAN_FILE = OUTPUT_DIR / "breakdown_history_clean.csv"
BREAKDOWN_TREND_FILE = OUTPUT_DIR / "breakdown_trend_by_machine.csv"
BREAKDOWN_RISK_FORECAST_FILE = OUTPUT_DIR / "breakdown_risk_forecast.csv"
FAILURE_MODE_EXPOSURE_FILE = OUTPUT_DIR / "breakdown_failure_mode_exposure.csv"
SPARE_PART_EXPOSURE_FILE = OUTPUT_DIR / "breakdown_spare_part_exposure.csv"
CREW_SKILL_EXPOSURE_FILE = OUTPUT_DIR / "breakdown_crew_skill_exposure.csv"
MANAGER_REVIEW_QUEUE_FILE = OUTPUT_DIR / "breakdown_manager_review_queue.csv"
VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "breakdown_validation.csv"
PHASE4_BREAKDOWN_CONTEXT_FILE = PHASE4_OUTPUT_DIR / "phase4_breakdown_risk_context.csv"

SOURCE_PHASE = "SHARED_STEP7D_BREAKDOWN_RISK_FORECAST"
PHASE4_SOURCE_PHASE = "PHASE4_STEP7D_BREAKDOWN_RISK_CONTEXT"
CONFIRMATION_STATUS = "PLANNING_RISK_ESTIMATE_ONLY_NOT_EXECUTION_CONFIRMED"
NEW_MACHINE_ID = "M-FORK-BENCH-001"

VALID_ROOT_CAUSES = {"WEAR", "LUBRICATION", "ALIGNMENT", "CALIBRATION", "SENSOR", "ELECTRICAL", "TOOLING", "OPERATOR_REPORTED", "UNKNOWN"}
VALID_FAILURE_CATEGORIES = {"BEARING_WEAR", "SENSOR_FAILURE", "ALIGNMENT_DRIFT", "LUBRICATION_ISSUE", "SEAL_LEAKAGE", "CALIBRATION_DRIFT", "TOOL_WEAR", "ELECTRICAL_FAULT", "FIXTURE_WEAR", "GENERAL_FAILURE"}
VALID_SEVERITY = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_DETECTABILITY = {"EASY", "MODERATE", "HARD", "UNKNOWN"}
VALID_OEM_BASIS = {"OPERATIONS", "RUN_HOURS", "CALENDAR_DAYS", "OPERATIONS_OR_TIME", "MANUFACTURER_GENERAL_GUIDELINE"}
VALID_OEM_SOURCE = {"OEM_GUIDELINE", "HISTORICAL_BREAKDOWN_DATA", "HYBRID_HISTORY_AND_OEM", "PLANNING_ASSUMPTION"}
VALID_TREND = {"IMPROVING", "STABLE", "WORSENING", "INSUFFICIENT_DATA", "OEM_BASELINE_ONLY"}
VALID_HISTORY_STATUS = {"SUFFICIENT_HISTORY", "LIMITED_HISTORY", "NO_HISTORY_NEW_MACHINE", "NO_HISTORY_REVIEW_REQUIRED"}
VALID_RISK_BASIS = {"HISTORICAL_BREAKDOWN_DATA", "HYBRID_HISTORY_AND_OEM", "OEM_GUIDELINE_NEW_MACHINE", "OEM_GUIDELINE_INSUFFICIENT_HISTORY", "PLANNING_ASSUMPTION_REVIEW"}
VALID_RISK_LEVEL = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "REVIEW_REQUIRED"}
VALID_COVERAGE = {"COVERED", "LIMITED_COVERAGE", "NO_ACTIVE_COVERAGE", "REVIEW_REQUIRED"}
RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4, "REVIEW_REQUIRED": 5}


def build_breakdown_risk_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    checks: list[dict] = []
    frames = {
        "history": _load_csv(BREAKDOWN_HISTORY_FILE, "breakdown_history", checks),
        "failure_modes": _load_csv(FAILURE_MODES_FILE, "machine_failure_modes", checks),
        "oem": _load_csv(OEM_ASSUMPTIONS_FILE, "manufacturer_reliability_assumptions", checks),
        "machines": _load_csv(MACHINES_FILE, "phase4_machines", checks),
        "spares": _load_csv(SPARE_PARTS_FILE, "spare_parts_master", checks),
        "skills": _load_csv(WORKFORCE_SKILLS_FILE, "workforce_skills", checks),
        "crews": _load_csv(WORKFORCE_CREWS_FILE, "workforce_crews", checks),
        "crew_skills": _load_csv(CREW_SKILL_MATRIX_FILE, "crew_skill_matrix", checks),
        "workforce_auth": _load_csv(WORKFORCE_AUTH_FILE, "workforce_machine_authorization_context", checks),
        "maintenance_due": _load_csv(MAINTENANCE_DUE_FILE, "maintenance_due_status_context", checks),
        "maintenance_readiness": _load_csv(MAINTENANCE_READINESS_FILE, "phase4_maintenance_readiness_context", checks),
        "spare_context": _load_csv(PHASE4_SPARE_CONTEXT_FILE, "phase4_spare_part_requirement_context", checks),
        "capacity": _load_optional_csv(CAPACITY_LOAD_FILE),
        "quality_capacity": _load_optional_csv(QUALITY_ADJUSTED_CAPACITY_FILE),
    }
    if all(frames[name] is not None for name in ["history", "failure_modes", "oem", "machines", "spares", "skills", "crews", "crew_skills", "workforce_auth", "maintenance_due", "maintenance_readiness", "spare_context"]):
        _validate_inputs(frames, checks)
        clean = _build_clean_history(frames["history"], frames["machines"])
        trend = _build_trend_by_machine(clean, frames["machines"], frames["oem"])
        risk = _build_risk_forecast(trend, frames["oem"], frames["maintenance_due"], frames["maintenance_readiness"], frames["capacity"], frames["quality_capacity"])
        failure_exposure = _build_failure_mode_exposure(frames["failure_modes"], frames["machines"], frames["spare_context"])
        spare_exposure = _build_spare_part_exposure(failure_exposure, risk, frames["spares"], frames["spare_context"])
        crew_exposure = _build_crew_skill_exposure(failure_exposure, frames["skills"], frames["crews"], frames["crew_skills"], frames["workforce_auth"])
        review = _build_manager_review_queue(risk, trend, spare_exposure, crew_exposure)
        phase4_context = _build_phase4_context(risk, failure_exposure, spare_exposure, crew_exposure, frames["maintenance_readiness"])
        _validate_outputs(clean, trend, risk, failure_exposure, spare_exposure, crew_exposure, review, phase4_context, frames, checks)
    else:
        clean = trend = risk = failure_exposure = spare_exposure = crew_exposure = review = phase4_context = pd.DataFrame()
    _check_existing_validations(checks)
    _check_no_blocked_outputs(checks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PHASE4_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    clean.to_csv(BREAKDOWN_HISTORY_CLEAN_FILE, index=False)
    trend.to_csv(BREAKDOWN_TREND_FILE, index=False)
    risk.to_csv(BREAKDOWN_RISK_FORECAST_FILE, index=False)
    failure_exposure.to_csv(FAILURE_MODE_EXPOSURE_FILE, index=False)
    spare_exposure.to_csv(SPARE_PART_EXPOSURE_FILE, index=False)
    crew_exposure.to_csv(CREW_SKILL_EXPOSURE_FILE, index=False)
    review.to_csv(MANAGER_REVIEW_QUEUE_FILE, index=False)
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    phase4_context.to_csv(PHASE4_BREAKDOWN_CONTEXT_FILE, index=False)
    return validation, clean, trend, risk, failure_exposure, spare_exposure, crew_exposure, review, phase4_context


def _validate_inputs(frames: dict[str, pd.DataFrame], checks: list[dict]) -> None:
    required = {
        "history": {"breakdown_history_id", "machine_id", "machine_type", "period_start", "period_end", "breakdown_count", "minor_stop_count", "downtime_hours", "repair_hours", "failure_mode_id", "root_cause_category", "spare_part_sku_used", "maintenance_deferred_flag", "operations_since_last_maintenance", "days_since_last_maintenance", "breakdown_history_source", "data_source_type", "active_flag", "advisory_only_flag", "notes"},
        "failure_modes": {"failure_mode_id", "machine_id", "machine_type", "failure_mode_name", "failure_mode_category", "severity_level", "expected_downtime_hours", "expected_repair_hours", "required_maintenance_level", "required_skill_id", "likely_spare_part_sku", "root_cause_category", "detectability_level", "active_flag", "advisory_only_flag", "notes"},
        "oem": {"machine_id", "machine_type", "machine_name", "oem_name", "oem_model", "oem_interval_basis", "oem_operations_between_service", "oem_hours_between_service", "oem_days_between_service", "oem_mtbf_hours", "oem_mttr_hours", "oem_baseline_failure_probability_per_period", "oem_recommended_maintenance_level", "oem_failure_mode_notes", "oem_confidence_level", "use_oem_when_history_missing_flag", "new_machine_flag", "history_available_flag", "reliability_data_source", "active_flag", "advisory_only_flag", "notes"},
    }
    for name, columns in required.items():
        missing = sorted(columns.difference(frames[name].columns))
        checks.append(_result(f"breakdown_{name}_required_columns", f"{name} required columns", "FAIL" if missing else "PASS", f"Missing columns: {missing}" if missing else f"{name} has required columns.", len(missing)))
    machines = frames["machines"]
    machine_ids = set(machines["machine_id"].astype(str))
    _check_refs(frames["history"], "machine_id", machine_ids, "breakdown_history_machine_refs", checks)
    _check_refs(frames["failure_modes"], "machine_id", machine_ids, "failure_mode_machine_refs", checks)
    _check_refs(frames["oem"], "machine_id", machine_ids, "oem_machine_refs", checks)
    active_machine_ids = set(machines["machine_id"].astype(str))
    active_oem_ids = set(frames["oem"].loc[_to_bool(frames["oem"]["active_flag"]), "machine_id"].astype(str))
    missing_oem = sorted(active_machine_ids - active_oem_ids)
    checks.append(_result("breakdown_every_machine_has_oem", "every machine has OEM assumption", "FAIL" if missing_oem else "PASS", f"Missing OEM rows: {missing_oem}" if missing_oem else "Every active machine has OEM/manufacturer assumptions.", len(missing_oem)))
    failure_ids = set(frames["failure_modes"]["failure_mode_id"].astype(str))
    history_failure_refs = sorted(set(frames["history"]["failure_mode_id"].dropna().astype(str)) - failure_ids - {""})
    checks.append(_result("breakdown_history_failure_mode_refs", "history failure mode refs valid", "FAIL" if history_failure_refs else "PASS", f"Missing failure modes: {history_failure_refs}" if history_failure_refs else "Breakdown history failure modes are valid.", len(history_failure_refs)))
    spare_skus = set(frames["spares"]["spare_part_sku"].astype(str))
    for frame_name, column, check_id in [("history", "spare_part_sku_used", "breakdown_history_spare_refs"), ("failure_modes", "likely_spare_part_sku", "failure_mode_spare_refs")]:
        refs = sorted(set(frames[frame_name][column].dropna().astype(str)) - spare_skus - {""})
        checks.append(_result(check_id, f"{column} references valid spares", "FAIL" if refs else "PASS", f"Missing spares: {refs}" if refs else f"{column} spare references are valid.", len(refs)))
    skill_ids = set(frames["skills"]["skill_id"].astype(str))
    skill_refs = sorted(set(frames["failure_modes"]["required_skill_id"].dropna().astype(str)) - skill_ids - {""})
    checks.append(_result("failure_mode_skill_refs", "failure mode skill refs valid", "FAIL" if skill_refs else "PASS", f"Missing skills: {skill_refs}" if skill_refs else "Failure mode skill references are valid.", len(skill_refs)))
    _valid_values(frames["history"], "root_cause_category", VALID_ROOT_CAUSES, "breakdown_history_root_causes_valid", checks)
    _valid_values(frames["failure_modes"], "failure_mode_category", VALID_FAILURE_CATEGORIES, "failure_mode_categories_valid", checks)
    _valid_values(frames["failure_modes"], "severity_level", VALID_SEVERITY, "failure_mode_severity_valid", checks)
    _valid_values(frames["failure_modes"], "detectability_level", VALID_DETECTABILITY, "failure_mode_detectability_valid", checks)
    _valid_values(frames["oem"], "oem_interval_basis", VALID_OEM_BASIS, "oem_interval_basis_valid", checks)
    _valid_values(frames["oem"], "reliability_data_source", VALID_OEM_SOURCE, "oem_reliability_source_valid", checks)
    _check_nonnegative(frames["history"], ["breakdown_count", "minor_stop_count", "downtime_hours", "repair_hours", "operations_since_last_maintenance", "days_since_last_maintenance"], "breakdown_history_numeric_nonnegative", checks)
    _check_nonnegative(frames["failure_modes"], ["expected_downtime_hours", "expected_repair_hours"], "failure_mode_numeric_nonnegative", checks)
    _check_nonnegative(frames["oem"], ["oem_operations_between_service", "oem_hours_between_service", "oem_days_between_service", "oem_mtbf_hours", "oem_mttr_hours", "oem_baseline_failure_probability_per_period"], "oem_numeric_nonnegative", checks)
    new_rows = frames["oem"][frames["oem"]["machine_id"].astype(str) == NEW_MACHINE_ID]
    bad_new = new_rows.empty or not bool(_to_bool(new_rows["new_machine_flag"]).all()) or bool(_to_bool(new_rows["history_available_flag"]).any()) or not bool(_to_bool(new_rows["use_oem_when_history_missing_flag"]).all()) or set(new_rows["reliability_data_source"].astype(str)) != {"OEM_GUIDELINE"}
    checks.append(_result("breakdown_new_machine_oem_setup", "new-to-us machine uses OEM guideline", "FAIL" if bad_new else "PASS", f"{NEW_MACHINE_ID} is configured as new-to-us OEM-guideline machine." if not bad_new else f"{NEW_MACHINE_ID} OEM setup is invalid.", 1 if bad_new else 0))
    active_history_new = frames["history"][(frames["history"]["machine_id"].astype(str) == NEW_MACHINE_ID) & _to_bool(frames["history"]["active_flag"])]
    checks.append(_result("breakdown_new_machine_no_history", "new-to-us machine has no active history", "FAIL" if not active_history_new.empty else "PASS", "New-to-us machine has no active breakdown history.", len(active_history_new)))
    if not _all_true(frames["history"], "advisory_only_flag") or not _all_true(frames["failure_modes"], "advisory_only_flag") or not _all_true(frames["oem"], "advisory_only_flag"):
        checks.append(_result("breakdown_master_advisory_only", "breakdown master data advisory-only", "FAIL", "Breakdown master advisory flags must be true.", 1))
    else:
        checks.append(_result("breakdown_master_advisory_only", "breakdown master data advisory-only", "PASS", "Breakdown master advisory flags are true.", 0))


def _build_clean_history(history: pd.DataFrame, machines: pd.DataFrame) -> pd.DataFrame:
    frame = history[_to_bool(history["active_flag"])].copy()
    frame = frame.merge(machines[["machine_id", "machine_name", "machine_type"]], on="machine_id", how="left", suffixes=("", "_machine"))
    for column in ["breakdown_count", "minor_stop_count", "downtime_hours", "repair_hours", "operations_since_last_maintenance", "days_since_last_maintenance"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).clip(lower=0)
    frame["planning_run_id"] = _planning_run_id()
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[["planning_run_id", "breakdown_history_id", "machine_id", "machine_name", "machine_type", "period_start", "period_end", "breakdown_count", "minor_stop_count", "downtime_hours", "repair_hours", "failure_mode_id", "root_cause_category", "spare_part_sku_used", "maintenance_deferred_flag", "operations_since_last_maintenance", "days_since_last_maintenance", "breakdown_history_source", "data_source_type", "source_phase", "advisory_only_flag"]].copy()


def _build_trend_by_machine(clean: pd.DataFrame, machines: pd.DataFrame, oem: pd.DataFrame) -> pd.DataFrame:
    rows = []
    run_id = _planning_run_id()
    for machine in machines.itertuples():
        machine_id = str(machine.machine_id)
        hist = clean[clean["machine_id"].astype(str) == machine_id].sort_values("period_start")
        oem_row = oem[oem["machine_id"].astype(str) == machine_id].iloc[0]
        new_machine = _bool_value(oem_row.get("new_machine_flag"))
        history_available = _bool_value(oem_row.get("history_available_flag")) and not hist.empty
        periods = len(hist)
        if new_machine and not history_available:
            status = "NO_HISTORY_NEW_MACHINE"
            trend_values = ("OEM_BASELINE_ONLY",) * 5
            reason = "New-to-us machine has no local breakdown history; OEM guideline is used."
        elif periods >= 4:
            status = "SUFFICIENT_HISTORY"
            breakdown = _trend(hist["breakdown_count"])
            minor = _trend(hist["minor_stop_count"])
            downtime = _trend(hist["downtime_hours"])
            repair = _trend(hist["repair_hours"])
            overall = _overall_trend([breakdown, minor, downtime, repair])
            trend_values = (breakdown, minor, downtime, repair, overall)
            reason = f"Recent history compared with earlier periods; overall trend is {overall}."
        elif periods > 0:
            status = "LIMITED_HISTORY"
            breakdown = _trend(hist["breakdown_count"])
            minor = _trend(hist["minor_stop_count"])
            downtime = _trend(hist["downtime_hours"])
            repair = _trend(hist["repair_hours"])
            overall = "INSUFFICIENT_DATA" if periods < 3 else _overall_trend([breakdown, minor, downtime, repair])
            trend_values = (breakdown, minor, downtime, repair, overall)
            reason = "Limited local history exists; OEM baseline should remain part of the risk basis."
        else:
            status = "NO_HISTORY_REVIEW_REQUIRED"
            trend_values = ("INSUFFICIENT_DATA",) * 5
            reason = "No local history exists and machine is not marked as new; review required."
        rows.append({
            "planning_run_id": run_id,
            "machine_id": machine_id,
            "machine_name": machine.machine_name,
            "machine_type": machine.machine_type,
            "periods_observed": periods,
            "total_breakdown_count": float(hist["breakdown_count"].sum()) if not hist.empty else 0.0,
            "total_minor_stop_count": float(hist["minor_stop_count"].sum()) if not hist.empty else 0.0,
            "total_downtime_hours": float(hist["downtime_hours"].sum()) if not hist.empty else 0.0,
            "total_repair_hours": float(hist["repair_hours"].sum()) if not hist.empty else 0.0,
            "avg_breakdown_count_per_period": float(hist["breakdown_count"].mean()) if not hist.empty else 0.0,
            "avg_minor_stop_count_per_period": float(hist["minor_stop_count"].mean()) if not hist.empty else 0.0,
            "avg_downtime_hours_per_period": float(hist["downtime_hours"].mean()) if not hist.empty else 0.0,
            "avg_repair_hours_per_period": float(hist["repair_hours"].mean()) if not hist.empty else 0.0,
            "breakdown_count_trend": trend_values[0],
            "minor_stop_trend": trend_values[1],
            "downtime_trend": trend_values[2],
            "repair_time_trend": trend_values[3],
            "breakdown_trend_overall": trend_values[4],
            "trend_reason": reason,
            "history_available_flag": history_available,
            "history_sufficiency_status": status,
            "reliability_data_source": oem_row["reliability_data_source"],
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows)


def _build_risk_forecast(trend: pd.DataFrame, oem: pd.DataFrame, due: pd.DataFrame, maintenance: pd.DataFrame, capacity: pd.DataFrame | None, quality_capacity: pd.DataFrame | None) -> pd.DataFrame:
    run_id = _planning_run_id()
    due_agg = due.groupby("machine_id", as_index=False).agg(
        overdue_count=("due_status", lambda s: int((s == "OVERDUE").sum())),
        due_soon_count=("due_status", lambda s: int((s == "DUE_SOON").sum())),
        due_now_count=("due_status", lambda s: int((s == "DUE_NOW").sum())),
        highest_deferral_risk_level=("deferral_risk_level", _highest_risk),
    )
    frame = trend.merge(oem, on=["machine_id", "machine_type", "machine_name"], how="left", suffixes=("", "_oem")).merge(due_agg, on="machine_id", how="left")
    frame = frame.merge(maintenance[["machine_id", "maintenance_readiness_status"]], on="machine_id", how="left")
    frame[["overdue_count", "due_soon_count", "due_now_count"]] = frame[["overdue_count", "due_soon_count", "due_now_count"]].fillna(0).astype(int)
    frame["highest_deferral_risk_level"] = frame["highest_deferral_risk_level"].fillna("LOW")
    ws_stress = _workstation_stress(capacity, "utilization_pct", "capacity_utilization_stress_level")
    q_stress = _workstation_stress(quality_capacity, "quality_adjusted_utilization_pct", "quality_capacity_stress_level")
    machines = pd.read_csv(MACHINES_FILE)
    stress = machines[["machine_id", "workstation_id"]].merge(ws_stress, on="workstation_id", how="left").merge(q_stress, on="workstation_id", how="left")
    frame = frame.merge(stress[["machine_id", "capacity_utilization_stress_level", "quality_capacity_stress_level"]], on="machine_id", how="left")
    frame["capacity_utilization_stress_level"] = frame["capacity_utilization_stress_level"].fillna("LOW")
    frame["quality_capacity_stress_level"] = frame["quality_capacity_stress_level"].fillna("LOW")
    rows = []
    for row in frame.itertuples():
        risk_basis = _risk_basis(row)
        score = 10.0
        if risk_basis == "HISTORICAL_BREAKDOWN_DATA":
            score += min(float(row.avg_breakdown_count_per_period) * 18.0, 35.0)
            score += min(float(row.avg_downtime_hours_per_period) * 4.0, 25.0)
        elif risk_basis.startswith("OEM_GUIDELINE"):
            score += float(row.oem_baseline_failure_probability_per_period) * 250.0
        elif risk_basis == "HYBRID_HISTORY_AND_OEM":
            score += min(float(row.avg_breakdown_count_per_period) * 12.0, 25.0)
            score += float(row.oem_baseline_failure_probability_per_period) * 150.0
        else:
            score += 25.0
        if row.overdue_count:
            score += 25.0
        if row.due_now_count:
            score += 15.0
        if row.due_soon_count:
            score += 8.0
        if row.highest_deferral_risk_level in {"HIGH", "CRITICAL"}:
            score += 12.0 if row.highest_deferral_risk_level == "HIGH" else 20.0
        if row.breakdown_trend_overall == "WORSENING":
            score += 18.0
        elif row.breakdown_trend_overall == "IMPROVING":
            score -= 8.0
        score += _stress_points(row.capacity_utilization_stress_level)
        score += _stress_points(row.quality_capacity_stress_level)
        score = max(0.0, round(score, 2))
        level = _risk_level(score)
        expected_breakdowns = _expected_breakdowns(row, risk_basis)
        expected_downtime = expected_breakdowns * float(row.oem_mttr_hours)
        if risk_basis == "HISTORICAL_BREAKDOWN_DATA" and float(row.avg_downtime_hours_per_period) > 0:
            expected_downtime = max(expected_downtime, float(row.avg_downtime_hours_per_period) * (1.15 if row.breakdown_trend_overall == "WORSENING" else 1.0))
        expected_repair = max(expected_breakdowns * float(row.oem_mttr_hours), float(row.avg_repair_hours_per_period) if risk_basis == "HISTORICAL_BREAKDOWN_DATA" else 0.0)
        reasons = []
        if risk_basis.startswith("OEM_GUIDELINE"):
            reasons.append("OEM_BASELINE_USED")
        if row.overdue_count:
            reasons.append("OVERDUE_MAINTENANCE")
        if row.breakdown_trend_overall == "WORSENING":
            reasons.append("WORSENING_HISTORY")
        if row.capacity_utilization_stress_level in {"HIGH", "CRITICAL"}:
            reasons.append("CAPACITY_STRESS")
        if row.quality_capacity_stress_level in {"HIGH", "CRITICAL"}:
            reasons.append("QUALITY_CAPACITY_STRESS")
        rows.append({
            "planning_run_id": run_id,
            "machine_id": row.machine_id,
            "machine_name": row.machine_name,
            "machine_type": row.machine_type,
            "new_machine_flag": bool(row.new_machine_flag),
            "history_available_flag": bool(row.history_available_flag),
            "reliability_data_source": row.reliability_data_source,
            "risk_basis": risk_basis,
            "breakdown_trend_overall": row.breakdown_trend_overall,
            "due_status": _due_signal(row),
            "overdue_count": row.overdue_count,
            "due_soon_count": row.due_soon_count,
            "highest_deferral_risk_level": row.highest_deferral_risk_level,
            "quality_capacity_stress_level": row.quality_capacity_stress_level,
            "capacity_utilization_stress_level": row.capacity_utilization_stress_level,
            "oem_mtbf_hours": row.oem_mtbf_hours,
            "oem_mttr_hours": row.oem_mttr_hours,
            "oem_baseline_failure_probability_per_period": row.oem_baseline_failure_probability_per_period,
            "expected_breakdown_count_next_period": round(expected_breakdowns, 4),
            "expected_downtime_hours_next_period": round(expected_downtime, 2),
            "expected_repair_hours_next_period": round(expected_repair, 2),
            "breakdown_risk_score": score,
            "breakdown_risk_level": level,
            "breakdown_risk_reason": ";".join(reasons) if reasons else "LOW_OR_NORMAL_PLANNING_RISK",
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows)


def _build_failure_mode_exposure(failure_modes: pd.DataFrame, machines: pd.DataFrame, spare_context: pd.DataFrame) -> pd.DataFrame:
    frame = failure_modes[_to_bool(failure_modes["active_flag"])].merge(machines[["machine_id", "machine_name"]], on="machine_id", how="left", suffixes=("", "_machine"))
    spare_status = spare_context[["spare_part_sku", "spare_part_readiness_status"]].drop_duplicates("spare_part_sku")
    frame = frame.merge(spare_status, left_on="likely_spare_part_sku", right_on="spare_part_sku", how="left")
    frame["spare_part_readiness_status"] = frame["spare_part_readiness_status"].fillna("REVIEW_REQUIRED")
    frame["failure_mode_exposure_level"] = frame.apply(_failure_exposure_level, axis=1)
    frame["exposure_reason"] = frame.apply(lambda r: f"{r['severity_level']} severity; spare readiness {r['spare_part_readiness_status']}", axis=1)
    frame["planning_run_id"] = _planning_run_id()
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[["planning_run_id", "machine_id", "machine_name", "failure_mode_id", "failure_mode_name", "failure_mode_category", "severity_level", "expected_downtime_hours", "expected_repair_hours", "required_maintenance_level", "required_skill_id", "likely_spare_part_sku", "spare_part_readiness_status", "failure_mode_exposure_level", "exposure_reason", "source_phase", "advisory_only_flag"]].copy()


def _build_spare_part_exposure(failure_exposure: pd.DataFrame, risk: pd.DataFrame, spares: pd.DataFrame, spare_context: pd.DataFrame) -> pd.DataFrame:
    frame = failure_exposure.merge(risk[["machine_id", "expected_breakdown_count_next_period"]], on="machine_id", how="left")
    frame = frame.merge(spares[["spare_part_sku", "spare_part_name", "criticality"]], left_on="likely_spare_part_sku", right_on="spare_part_sku", how="left")
    status = spare_context[["spare_part_sku", "inventory_status", "supplier_coverage_status", "spare_part_readiness_status"]].drop_duplicates("spare_part_sku")
    frame = frame.merge(status, left_on="likely_spare_part_sku", right_on="spare_part_sku", how="left", suffixes=("", "_ctx"))
    frame["expected_spare_part_exposure_qty"] = pd.to_numeric(frame["expected_breakdown_count_next_period"], errors="coerce").fillna(0).clip(lower=0).round(4)
    frame["breakdown_spare_part_review_required_flag"] = ~frame["spare_part_readiness_status_ctx"].fillna("REVIEW_REQUIRED").eq("READY")
    frame["note_no_consumption_flag"] = True
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame.rename(columns={"spare_part_readiness_status_ctx": "spare_part_readiness_status"})[["planning_run_id", "machine_id", "machine_name", "failure_mode_id", "likely_spare_part_sku", "spare_part_name", "criticality", "expected_breakdown_count_next_period", "expected_spare_part_exposure_qty", "inventory_status", "supplier_coverage_status", "spare_part_readiness_status", "breakdown_spare_part_review_required_flag", "note_no_consumption_flag", "source_phase", "advisory_only_flag"]].copy()


def _build_crew_skill_exposure(failure_exposure: pd.DataFrame, skills: pd.DataFrame, crews: pd.DataFrame, crew_skills: pd.DataFrame, auth: pd.DataFrame) -> pd.DataFrame:
    active_crews = crews[_to_bool(crews["active_flag"])]
    active_maint_crews = active_crews[active_crews["crew_type"].astype(str) == "MAINTENANCE"]
    active_skill = crew_skills[_to_bool(crew_skills["active_flag"])]
    maint_skill = active_skill[active_skill["crew_id"].astype(str).isin(set(active_maint_crews["crew_id"].astype(str)))]
    skill_counts = maint_skill.groupby("skill_id", as_index=False).agg(active_maintenance_crew_count=("crew_id", "nunique"))
    repair_counts = auth[(auth["crew_type"].astype(str) == "MAINTENANCE") & _to_bool(auth["can_repair_flag"])].groupby("machine_id", as_index=False).agg(authorized_repair_crew_count=("crew_id", "nunique"))
    frame = failure_exposure.merge(skills[["skill_id", "skill_name"]], left_on="required_skill_id", right_on="skill_id", how="left")
    frame = frame.merge(skill_counts, left_on="required_skill_id", right_on="skill_id", how="left", suffixes=("", "_skill"))
    frame = frame.merge(repair_counts, on="machine_id", how="left")
    frame["active_maintenance_crew_count"] = pd.to_numeric(frame["active_maintenance_crew_count"], errors="coerce").fillna(0).astype(int)
    frame["authorized_repair_crew_count"] = pd.to_numeric(frame["authorized_repair_crew_count"], errors="coerce").fillna(0).astype(int)
    frame["crew_skill_coverage_status"] = frame.apply(_crew_coverage, axis=1)
    frame["breakdown_crew_review_required_flag"] = frame["crew_skill_coverage_status"].isin(["NO_ACTIVE_COVERAGE", "REVIEW_REQUIRED"])
    frame["note_no_scheduling_flag"] = True
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame.rename(columns={"skill_name": "required_skill_name"})[["planning_run_id", "machine_id", "machine_name", "failure_mode_id", "required_skill_id", "required_skill_name", "required_maintenance_level", "active_maintenance_crew_count", "authorized_repair_crew_count", "crew_skill_coverage_status", "breakdown_crew_review_required_flag", "note_no_scheduling_flag", "source_phase", "advisory_only_flag"]].copy()


def _build_manager_review_queue(risk: pd.DataFrame, trend: pd.DataFrame, spare: pd.DataFrame, crew: pd.DataFrame) -> pd.DataFrame:
    rows = []
    item = 1
    for row in risk.itertuples():
        if row.breakdown_risk_level == "CRITICAL":
            rows.append(_review_row(item, row, "CRITICAL_BREAKDOWN_RISK", "CRITICAL", f"{row.machine_name} has critical breakdown risk score {row.breakdown_risk_score}.", "REVIEW_DOWNTIME_RISK")); item += 1
        elif row.breakdown_risk_level == "HIGH":
            rows.append(_review_row(item, row, "HIGH_BREAKDOWN_RISK", "HIGH", f"{row.machine_name} has high breakdown risk score {row.breakdown_risk_score}.", "REVIEW_BREAKDOWN_HISTORY")); item += 1
        if row.risk_basis == "OEM_GUIDELINE_NEW_MACHINE":
            rows.append(_review_row(item, row, "NEW_MACHINE_OEM_BASELINE", "MEDIUM", f"{row.machine_name} is new-to-us and uses OEM reliability guidance.", "REVIEW_OEM_GUIDELINE")); item += 1
        if row.risk_basis in {"OEM_GUIDELINE_INSUFFICIENT_HISTORY", "PLANNING_ASSUMPTION_REVIEW"}:
            rows.append(_review_row(item, row, "INSUFFICIENT_BREAKDOWN_HISTORY", "MEDIUM", f"{row.machine_name} has insufficient breakdown history.", "REVIEW_BREAKDOWN_HISTORY")); item += 1
        if row.breakdown_trend_overall == "WORSENING":
            rows.append(_review_row(item, row, "WORSENING_BREAKDOWN_TREND", "HIGH", f"{row.machine_name} breakdown trend is worsening.", "REVIEW_MAINTENANCE_DUE_STATUS")); item += 1
        if int(row.overdue_count) and row.breakdown_risk_level in {"HIGH", "CRITICAL"}:
            rows.append(_review_row(item, row, "OVERDUE_MAINTENANCE_BREAKDOWN_RISK", "CRITICAL", f"{row.machine_name} has overdue maintenance and high breakdown risk.", "REVIEW_MAINTENANCE_DUE_STATUS")); item += 1
        if float(row.expected_downtime_hours_next_period) >= 5:
            rows.append(_review_row(item, row, "HIGH_EXPECTED_DOWNTIME", "HIGH", f"Expected downtime next period is {row.expected_downtime_hours_next_period} hours.", "REVIEW_DOWNTIME_RISK")); item += 1
    for row in spare[spare["breakdown_spare_part_review_required_flag"]].itertuples():
        rows.append({"review_item_id": f"BDR-REV-{item:04d}", "planning_run_id": row.planning_run_id, "machine_id": row.machine_id, "machine_name": row.machine_name, "issue_type": "SPARE_PART_EXPOSURE_REVIEW", "issue_severity": "HIGH" if row.criticality == "CRITICAL" else "MEDIUM", "issue_description": f"Breakdown exposure spare {row.likely_spare_part_sku} readiness is {row.spare_part_readiness_status}.", "recommended_review_action": "REVIEW_SPARE_PART_AVAILABILITY", "auto_action_allowed": False, "advisory_only_flag": True}); item += 1
    for row in crew[crew["breakdown_crew_review_required_flag"]].itertuples():
        rows.append({"review_item_id": f"BDR-REV-{item:04d}", "planning_run_id": row.planning_run_id, "machine_id": row.machine_id, "machine_name": row.machine_name, "issue_type": "CREW_SKILL_EXPOSURE_REVIEW", "issue_severity": "HIGH", "issue_description": f"Breakdown skill {row.required_skill_id} coverage is {row.crew_skill_coverage_status}.", "recommended_review_action": "REVIEW_CREW_REPAIR_COVERAGE", "auto_action_allowed": False, "advisory_only_flag": True}); item += 1
    return pd.DataFrame(rows, columns=["review_item_id", "planning_run_id", "machine_id", "machine_name", "issue_type", "issue_severity", "issue_description", "recommended_review_action", "auto_action_allowed", "advisory_only_flag"])


def _build_phase4_context(risk: pd.DataFrame, failure: pd.DataFrame, spare: pd.DataFrame, crew: pd.DataFrame, maintenance: pd.DataFrame) -> pd.DataFrame:
    severity = failure.groupby("machine_id", as_index=False).agg(highest_failure_mode_severity=("severity_level", _highest_risk))
    spare_review = spare.groupby("machine_id", as_index=False).agg(spare_part_exposure_review_required_count=("breakdown_spare_part_review_required_flag", lambda s: int(_to_bool(s).sum())))
    crew_review = crew.groupby("machine_id", as_index=False).agg(crew_skill_exposure_review_required_count=("breakdown_crew_review_required_flag", lambda s: int(_to_bool(s).sum())))
    frame = risk.merge(severity, on="machine_id", how="left").merge(spare_review, on="machine_id", how="left").merge(crew_review, on="machine_id", how="left")
    frame = frame.merge(maintenance[["machine_id", "maintenance_readiness_status"]], on="machine_id", how="left")
    for col in ["spare_part_exposure_review_required_count", "crew_skill_exposure_review_required_count"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0).astype(int)
    frame["highest_failure_mode_severity"] = frame["highest_failure_mode_severity"].fillna("LOW")
    frame["maintenance_due_status_signal"] = frame["maintenance_readiness_status"].fillna("REVIEW_REQUIRED")
    frame["breakdown_planning_ready_flag"] = ~frame["breakdown_risk_level"].isin(["REVIEW_REQUIRED"]) & (frame["crew_skill_exposure_review_required_count"] == 0)
    frame["confirmation_status"] = CONFIRMATION_STATUS
    frame["source_phase"] = PHASE4_SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[["planning_run_id", "machine_id", "machine_name", "machine_type", "new_machine_flag", "reliability_data_source", "risk_basis", "breakdown_trend_overall", "breakdown_risk_level", "breakdown_risk_score", "expected_breakdown_count_next_period", "expected_downtime_hours_next_period", "expected_repair_hours_next_period", "highest_failure_mode_severity", "spare_part_exposure_review_required_count", "crew_skill_exposure_review_required_count", "maintenance_due_status_signal", "breakdown_planning_ready_flag", "confirmation_status", "source_phase", "advisory_only_flag"]].copy()


def _validate_outputs(clean: pd.DataFrame, trend: pd.DataFrame, risk: pd.DataFrame, failure: pd.DataFrame, spare: pd.DataFrame, crew: pd.DataFrame, review: pd.DataFrame, phase4: pd.DataFrame, frames: dict[str, pd.DataFrame], checks: list[dict]) -> None:
    output_frames = [(clean, "breakdown_history_clean"), (trend, "breakdown_trend_by_machine"), (risk, "breakdown_risk_forecast"), (failure, "breakdown_failure_mode_exposure"), (spare, "breakdown_spare_part_exposure"), (crew, "breakdown_crew_skill_exposure"), (phase4, "phase4_breakdown_risk_context")]
    for frame, name in output_frames:
        checks.append(_result(f"{name}_not_empty", f"{name} not empty", "FAIL" if frame.empty else "PASS", f"{name} rows: {len(frame)}", int(frame.empty)))
        if not frame.empty and not _all_true(frame, "advisory_only_flag"):
            checks.append(_result(f"{name}_advisory_only", f"{name} advisory-only", "FAIL", f"{name} has non-advisory rows.", 1))
        else:
            checks.append(_result(f"{name}_advisory_only", f"{name} advisory-only", "PASS", f"{name} advisory flags are true.", 0))
    for frame, column, allowed, check_id in [
        (trend, "breakdown_trend_overall", VALID_TREND, "breakdown_trend_values_valid"),
        (trend, "history_sufficiency_status", VALID_HISTORY_STATUS, "breakdown_history_sufficiency_valid"),
        (risk, "risk_basis", VALID_RISK_BASIS, "breakdown_risk_basis_valid"),
        (risk, "breakdown_risk_level", VALID_RISK_LEVEL, "breakdown_risk_level_valid"),
        (failure, "failure_mode_exposure_level", VALID_RISK_LEVEL, "failure_mode_exposure_level_valid"),
        (crew, "crew_skill_coverage_status", VALID_COVERAGE, "crew_skill_coverage_valid"),
    ]:
        _valid_values(frame, column, allowed, check_id, checks)
    new_risk = risk[risk["machine_id"].astype(str) == NEW_MACHINE_ID]
    bad_new = new_risk.empty or set(new_risk["risk_basis"].astype(str)) != {"OEM_GUIDELINE_NEW_MACHINE"} or set(new_risk["reliability_data_source"].astype(str)) != {"OEM_GUIDELINE"} or bool(_to_bool(new_risk["history_available_flag"]).any())
    checks.append(_result("breakdown_new_machine_forecast_oem", "new machine forecast uses OEM", "FAIL" if bad_new else "PASS", f"{NEW_MACHINE_ID} forecast uses OEM guideline new-machine basis." if not bad_new else f"{NEW_MACHINE_ID} forecast basis invalid.", int(bad_new)))
    if not _all_true(spare, "note_no_consumption_flag"):
        checks.append(_result("breakdown_spare_no_consumption", "spare exposure no consumption", "FAIL", "Breakdown spare exposure must not consume parts.", 1))
    else:
        checks.append(_result("breakdown_spare_no_consumption", "spare exposure no consumption", "PASS", "Breakdown spare exposure flags no consumption.", 0))
    if not _all_true(crew, "note_no_scheduling_flag"):
        checks.append(_result("breakdown_crew_no_scheduling", "crew exposure no scheduling", "FAIL", "Breakdown crew exposure must not schedule crews.", 1))
    else:
        checks.append(_result("breakdown_crew_no_scheduling", "crew exposure no scheduling", "PASS", "Breakdown crew exposure flags no scheduling.", 0))
    if not review.empty and (_to_bool(review["auto_action_allowed"]).any() or not _all_true(review, "advisory_only_flag")):
        checks.append(_result("breakdown_review_queue_safe", "review queue safe", "FAIL", "Breakdown review queue must be advisory-only with no auto action.", 1))
    else:
        checks.append(_result("breakdown_review_queue_safe", "review queue safe", "PASS", "Breakdown review queue has no automatic action.", 0))
    if set(phase4["confirmation_status"].dropna().astype(str)) != {CONFIRMATION_STATUS}:
        checks.append(_result("phase4_breakdown_confirmation_status", "Phase 4 breakdown confirmation status", "FAIL", "Invalid Phase 4 breakdown confirmation status.", 1))
    else:
        checks.append(_result("phase4_breakdown_confirmation_status", "Phase 4 breakdown confirmation status", "PASS", "Phase 4 breakdown context is planning risk estimate only.", 0))


def _check_existing_validations(checks: list[dict]) -> None:
    for path, label in [(WORKFORCE_VALIDATION_FILE, "workforce"), (SPARE_VALIDATION_FILE, "spare-part"), (MAINTENANCE_VALIDATION_FILE, "maintenance")]:
        if not path.exists():
            checks.append(_result(f"breakdown_existing_{label}_validation", f"existing {label} validation", "FAIL", f"Missing {path}", 1))
            continue
        frame = pd.read_csv(path)
        fail_count = int((frame["status"].astype(str).str.upper() == "FAIL").sum()) if "status" in frame.columns else len(frame)
        checks.append(_result(f"breakdown_existing_{label}_validation", f"existing {label} validation", "FAIL" if fail_count else "PASS", f"{label} validation FAIL rows: {fail_count}", fail_count))


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked = ["breakdown_event", "maintenance_work_order", "production_order", "purchase_order", "spare_part_consumption", "inventory_reservation", "finite_schedule", "dispatch_schedule", "crew_schedule", "simulation"]
    bad = []
    for folder in [OUTPUT_DIR, PHASE4_OUTPUT_DIR]:
        if not folder.exists():
            continue
        for path in folder.glob("*"):
            if path.is_file() and any(token in path.name.lower() for token in blocked):
                bad.append(str(path))
    checks.append(_result("breakdown_no_blocked_outputs", "no blocked breakdown outputs", "FAIL" if bad else "PASS", f"Blocked outputs found: {bad}" if bad else "No breakdown events, work orders, scheduling, reservation, purchase-order, or simulation outputs found.", len(bad)))


def _trend(series: pd.Series) -> str:
    values = pd.to_numeric(series, errors="coerce").dropna().tolist()
    if len(values) < 3:
        return "INSUFFICIENT_DATA"
    split = max(1, len(values) // 2)
    earlier = sum(values[:split]) / split
    recent = sum(values[split:]) / max(1, len(values[split:]))
    diff = recent - earlier
    tolerance = max(0.25, abs(earlier) * 0.15)
    if diff > tolerance:
        return "WORSENING"
    if diff < -tolerance:
        return "IMPROVING"
    return "STABLE"


def _overall_trend(values: list[str]) -> str:
    if "WORSENING" in values:
        return "WORSENING"
    if values.count("IMPROVING") >= 2:
        return "IMPROVING"
    if all(value == "INSUFFICIENT_DATA" for value in values):
        return "INSUFFICIENT_DATA"
    return "STABLE"


def _risk_basis(row: object) -> str:
    if bool(row.new_machine_flag) and not bool(row.history_available_flag):
        return "OEM_GUIDELINE_NEW_MACHINE"
    if row.history_sufficiency_status == "SUFFICIENT_HISTORY":
        return "HISTORICAL_BREAKDOWN_DATA"
    if row.history_sufficiency_status == "LIMITED_HISTORY":
        return "HYBRID_HISTORY_AND_OEM"
    if row.reliability_data_source == "OEM_GUIDELINE":
        return "OEM_GUIDELINE_INSUFFICIENT_HISTORY"
    return "PLANNING_ASSUMPTION_REVIEW"


def _expected_breakdowns(row: object, risk_basis: str) -> float:
    if risk_basis == "HISTORICAL_BREAKDOWN_DATA":
        value = float(row.avg_breakdown_count_per_period)
        if row.breakdown_trend_overall == "WORSENING":
            value *= 1.25
        elif row.breakdown_trend_overall == "IMPROVING":
            value *= 0.85
        return round(max(value, 0.0), 4)
    if risk_basis == "HYBRID_HISTORY_AND_OEM":
        hist = float(row.avg_breakdown_count_per_period) if float(row.avg_breakdown_count_per_period) > 0 else 0.05
        oem = float(row.oem_baseline_failure_probability_per_period)
        return round(max((hist * 0.55) + (oem * 0.45), 0.0), 4)
    return round(max(float(row.oem_baseline_failure_probability_per_period), 0.0), 4)


def _risk_level(score: float) -> str:
    if score >= 90:
        return "CRITICAL"
    if score >= 65:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def _due_signal(row: object) -> str:
    if int(row.overdue_count):
        return "OVERDUE"
    if int(row.due_now_count):
        return "DUE_NOW"
    if int(row.due_soon_count):
        return "DUE_SOON"
    if str(row.maintenance_readiness_status) == "REVIEW_REQUIRED":
        return "REVIEW_REQUIRED"
    return "NOT_DUE"


def _workstation_stress(frame: pd.DataFrame | None, utilization_column: str, output_column: str) -> pd.DataFrame:
    if frame is None or frame.empty or utilization_column not in frame.columns:
        return pd.DataFrame(columns=["workstation_id", output_column])
    temp = frame.copy()
    temp[utilization_column] = pd.to_numeric(temp[utilization_column], errors="coerce").fillna(0)
    grouped = temp.groupby("workstation_id", as_index=False).agg(max_util=(utilization_column, "max"))
    grouped[output_column] = grouped["max_util"].apply(_stress_level)
    return grouped[["workstation_id", output_column]]


def _stress_level(value: float) -> str:
    if value > 150:
        return "CRITICAL"
    if value > 100:
        return "HIGH"
    if value > 85:
        return "MEDIUM"
    return "LOW"


def _stress_points(level: str) -> float:
    return {"LOW": 0.0, "MEDIUM": 5.0, "HIGH": 10.0, "CRITICAL": 18.0}.get(str(level), 0.0)


def _failure_exposure_level(row: pd.Series) -> str:
    if row["spare_part_readiness_status"] != "READY" and row["severity_level"] in {"HIGH", "CRITICAL"}:
        return "CRITICAL"
    if row["severity_level"] == "CRITICAL":
        return "CRITICAL"
    if row["severity_level"] == "HIGH":
        return "HIGH"
    if row["severity_level"] == "MEDIUM":
        return "MEDIUM"
    return "LOW"


def _crew_coverage(row: pd.Series) -> str:
    if int(row["active_maintenance_crew_count"]) <= 0:
        return "NO_ACTIVE_COVERAGE"
    if str(row["required_maintenance_level"]) in {"MEDIUM", "HEAVY", "CALIBRATION"} and int(row["authorized_repair_crew_count"]) <= 0:
        return "REVIEW_REQUIRED"
    if int(row["active_maintenance_crew_count"]) == 1:
        return "LIMITED_COVERAGE"
    return "COVERED"


def _review_row(item: int, risk_row: object, issue_type: str, severity: str, description: str, action: str) -> dict:
    return {
        "review_item_id": f"BDR-REV-{item:04d}",
        "planning_run_id": risk_row.planning_run_id,
        "machine_id": risk_row.machine_id,
        "machine_name": risk_row.machine_name,
        "issue_type": issue_type,
        "issue_severity": severity,
        "issue_description": description,
        "recommended_review_action": action,
        "auto_action_allowed": False,
        "advisory_only_flag": True,
    }


def _highest_risk(values: pd.Series) -> str:
    values = [str(value) for value in values.dropna() if str(value)]
    if not values:
        return "LOW"
    return max(values, key=lambda value: RISK_ORDER.get(value, 0))


def _check_refs(df: pd.DataFrame, column: str, valid_values: set[str], check_id: str, checks: list[dict]) -> None:
    missing = sorted(set(df[column].dropna().astype(str)) - valid_values - {""})
    checks.append(_result(check_id, f"{column} references valid", "FAIL" if missing else "PASS", f"Missing references: {missing}" if missing else f"{column} references are valid.", len(missing)))


def _valid_values(df: pd.DataFrame, column: str, allowed: set[str], check_id: str, checks: list[dict]) -> None:
    if df.empty:
        checks.append(_result(check_id, f"{column} values valid", "FAIL", f"{column} cannot be checked on an empty frame.", 1))
        return
    bad = df[~df[column].astype(str).isin(allowed)]
    checks.append(_result(check_id, f"{column} values valid", "FAIL" if not bad.empty else "PASS", f"{column} values are valid." if bad.empty else f"Invalid {column}: {bad[column].tolist()}", len(bad)))


def _check_nonnegative(df: pd.DataFrame, columns: list[str], check_id: str, checks: list[dict]) -> None:
    bad = 0
    for column in columns:
        values = pd.to_numeric(df[column], errors="coerce")
        bad += int(values.isna().sum()) + int((values < 0).sum())
    checks.append(_result(check_id, "numeric fields non-negative", "FAIL" if bad else "PASS", f"Invalid numeric values: {bad}" if bad else "Numeric fields are non-negative.", bad))


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
    return f"SHARED-BREAKDOWN-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


def _load_csv(path: Path, name: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"breakdown_{name}_exists", f"{name} exists", "FAIL", f"Missing file: {path}", 1))
        return None
    frame = pd.read_csv(path, keep_default_na=False)
    checks.append(_result(f"breakdown_{name}_exists", f"{name} exists", "PASS", f"Loaded {path}", 0))
    if frame.empty:
        checks.append(_result(f"breakdown_{name}_not_empty", f"{name} not empty", "FAIL", f"{name} has no rows.", 1))
    return frame


def _load_optional_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path, keep_default_na=False)


def _all_true(df: pd.DataFrame, column: str) -> bool:
    return column in df.columns and bool(_to_bool(df[column]).all())


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
    validation, *_ = build_breakdown_risk_outputs()
    print(f"Breakdown validation rows: {len(validation)}")
    print(f"Breakdown validation status counts: {validation['status'].value_counts().to_dict() if not validation.empty else {}}")
