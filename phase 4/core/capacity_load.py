"""Build advisory workstation capacity load from MPS and routings."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PHASE4_DIR / "data"
OUTPUT_DIR = PHASE4_DIR / "outputs"

MPS_FILE = OUTPUT_DIR / "phase4_master_production_schedule.csv"
PRODUCT_ROUTINGS_FILE = DATA_DIR / "product_routings.csv"
WORKSTATIONS_FILE = DATA_DIR / "workstations.csv"
OPERATION_RESOURCES_FILE = DATA_DIR / "routing_operation_resources.csv"
MACHINES_FILE = DATA_DIR / "machines.csv"
LABOR_FILE = DATA_DIR / "labor_resources.csv"
RESOURCE_CALENDAR_FILE = DATA_DIR / "resource_calendar.csv"
RESOURCE_VALIDATION_FILE = OUTPUT_DIR / "phase4_resource_validation.csv"
ROUTING_VALIDATION_FILE = OUTPUT_DIR / "phase4_routing_validation.csv"

OUTPUT_FILE = OUTPUT_DIR / "phase4_capacity_load_by_workstation.csv"
DETAIL_OUTPUT_FILE = OUTPUT_DIR / "phase4_capacity_operation_load_detail.csv"
MACHINE_OUTPUT_FILE = OUTPUT_DIR / "phase4_capacity_load_by_machine_type.csv"
LABOR_OUTPUT_FILE = OUTPUT_DIR / "phase4_capacity_load_by_labor_skill.csv"
CONSTRAINT_BRIDGE_OUTPUT_FILE = OUTPUT_DIR / "phase4_capacity_constraint_bridge.csv"
FEASIBILITY_SUMMARY_OUTPUT_FILE = OUTPUT_DIR / "phase4_capacity_feasibility_summary.csv"
BOTTLENECK_CANDIDATE_OUTPUT_FILE = OUTPUT_DIR / "phase4_bottleneck_candidate_summary.csv"
MANAGER_REVIEW_QUEUE_OUTPUT_FILE = OUTPUT_DIR / "phase4_capacity_manager_review_queue.csv"
VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_capacity_validation.csv"

CAPACITY_PLANNING_BASIS = "MPS_ROUTING_WORKSTATION_LOAD"
MACHINE_CAPACITY_PLANNING_BASIS = "MPS_ROUTING_MACHINE_TYPE_LOAD"
LABOR_CAPACITY_PLANNING_BASIS = "MPS_ROUTING_LABOR_SKILL_LOAD"
CONSTRAINT_BRIDGE_PLANNING_BASIS = "MPS_ROUTING_CAPACITY_CONSTRAINT_BRIDGE"
FEASIBILITY_SUMMARY_PLANNING_BASIS = "CRP_CAPACITY_FEASIBILITY_SUMMARY"
STEP4C_SOURCE_PHASE = "PHASE4_STEP4C_CAPACITY_SUMMARY"
LABOR_SOFT_WARNING_THRESHOLD_PCT = 80.0
LABOR_HARD_OVERLOAD_THRESHOLD_PCT = 95.0
WORKSTATION_CAPACITY_BASIS = "SINGLE_STATION_CALENDAR"

REQUIRED_COLUMNS = {
    "mps": {
        "planning_run_id",
        "period_start",
        "period_end",
        "finished_sku",
        "finished_product_name",
        "planned_production_qty",
    },
    "product_routings": {
        "finished_sku",
        "finished_product_name",
        "operation_id",
        "operation_sequence",
        "operation_name",
        "workstation_id",
        "parallel_group_id",
        "can_run_in_parallel_flag",
        "join_required_before_next_flag",
        "setup_time_minutes",
        "run_time_minutes_per_unit",
        "move_time_minutes",
        "active_flag",
        "advisory_only_flag",
    },
    "workstations": {
        "workstation_id",
        "workstation_name",
        "active_flag",
    },
    "resource_calendar": {
        "resource_scope",
        "resource_id",
        "weekday",
        "shift_start",
        "shift_end",
        "planned_break_minutes",
        "available_flag",
    },
    "routing_operation_resources": {
        "operation_id",
        "routing_id",
        "finished_sku",
        "workstation_id",
        "required_machine_type",
        "required_labor_skill",
        "required_machine_count",
        "required_worker_count",
        "active_flag",
        "advisory_only_flag",
    },
    "machines": {
        "workstation_id",
        "machine_type",
        "machine_count",
        "available_hours_per_week",
        "active_flag",
    },
    "labor_resources": {
        "workstation_id",
        "skill_type",
        "workers_available",
        "hours_per_worker_per_week",
        "active_flag",
    },
}


def build_workstation_capacity_load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build all Step 4A/4B advisory CRP capacity outputs."""
    checks: list[dict] = []
    frames = {
        "mps": _load_csv(MPS_FILE, "mps", checks),
        "product_routings": _load_csv(PRODUCT_ROUTINGS_FILE, "product_routings", checks),
        "workstations": _load_csv(WORKSTATIONS_FILE, "workstations", checks),
        "resource_calendar": _load_csv(RESOURCE_CALENDAR_FILE, "resource_calendar", checks),
        "routing_operation_resources": _load_csv(OPERATION_RESOURCES_FILE, "routing_operation_resources", checks),
        "machines": _load_csv(MACHINES_FILE, "machines", checks),
        "labor_resources": _load_csv(LABOR_FILE, "labor_resources", checks),
    }

    for name, required in REQUIRED_COLUMNS.items():
        frame = frames.get(name)
        if frame is None:
            continue
        _check_required_columns(name, frame, required, checks)
        _check_not_empty(name, frame, checks)

    _check_prior_validation("resource_validation", RESOURCE_VALIDATION_FILE, checks)
    _check_prior_validation("routing_validation", ROUTING_VALIDATION_FILE, checks)

    detail = pd.DataFrame()
    load = pd.DataFrame()
    machine_load = pd.DataFrame()
    labor_load = pd.DataFrame()
    constraint_bridge = pd.DataFrame()
    feasibility_summary = pd.DataFrame()
    bottleneck_candidates = pd.DataFrame()
    manager_review_queue = pd.DataFrame()
    if all(frames[name] is not None and REQUIRED_COLUMNS[name].issubset(frames[name].columns) for name in frames):
        mps = frames["mps"]
        routings = frames["product_routings"]
        workstations = frames["workstations"]
        calendar = frames["resource_calendar"]
        operation_resources = frames["routing_operation_resources"]
        machines = frames["machines"]
        labor = frames["labor_resources"]
        detail = _build_operation_detail(mps, routings, checks)
        load = _build_workstation_load(detail, mps, workstations, calendar, checks)
        machine_load = _build_machine_load(detail, operation_resources, machines)
        labor_load = _build_labor_load(detail, operation_resources, labor)
        constraint_bridge = _build_constraint_bridge(load, machine_load, labor_load)
        feasibility_summary = _build_capacity_feasibility_summary(load, machine_load, labor_load, constraint_bridge)
        bottleneck_candidates = _build_bottleneck_candidate_summary(load, machine_load, labor_load, constraint_bridge)
        manager_review_queue = _build_capacity_manager_review_queue(feasibility_summary, load, machine_load, labor_load, constraint_bridge)
        _validate_capacity_outputs(
            load,
            detail,
            machine_load,
            labor_load,
            constraint_bridge,
            feasibility_summary,
            bottleneck_candidates,
            manager_review_queue,
            checks,
        )

    _check_no_blocked_outputs(checks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL_OUTPUT_FILE, index=False)
    load.to_csv(OUTPUT_FILE, index=False)
    machine_load.to_csv(MACHINE_OUTPUT_FILE, index=False)
    labor_load.to_csv(LABOR_OUTPUT_FILE, index=False)
    constraint_bridge.to_csv(CONSTRAINT_BRIDGE_OUTPUT_FILE, index=False)
    feasibility_summary.to_csv(FEASIBILITY_SUMMARY_OUTPUT_FILE, index=False)
    bottleneck_candidates.to_csv(BOTTLENECK_CANDIDATE_OUTPUT_FILE, index=False)
    manager_review_queue.to_csv(MANAGER_REVIEW_QUEUE_OUTPUT_FILE, index=False)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    return load, detail, validation


def _build_operation_detail(mps: pd.DataFrame, routings: pd.DataFrame, checks: list[dict]) -> pd.DataFrame:
    active_routings = routings[_to_bool(routings["active_flag"])].copy()
    mps = mps.copy()
    mps["planned_production_qty"] = pd.to_numeric(mps["planned_production_qty"], errors="coerce").fillna(0).clip(lower=0)
    merged = mps.merge(active_routings, on=["finished_sku", "finished_product_name"], how="left", suffixes=("", "_routing"))
    missing_routing = int(merged["operation_id"].isna().sum())
    checks.append(
        _result(
            "capacity_mps_skus_have_routings",
            "MPS SKUs have routing operations",
            "FAIL" if missing_routing else "PASS",
            f"MPS rows without routing operations: {missing_routing}" if missing_routing else "Every MPS finished SKU has routing operations.",
            missing_routing,
        )
    )
    merged = merged.dropna(subset=["operation_id"]).copy()
    for column in ["setup_time_minutes", "run_time_minutes_per_unit", "move_time_minutes", "operation_sequence"]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce")
    invalid_timing = int(
        merged["setup_time_minutes"].isna().sum()
        + (merged["setup_time_minutes"] < 0).sum()
        + merged["run_time_minutes_per_unit"].isna().sum()
        + (merged["run_time_minutes_per_unit"] <= 0).sum()
        + merged["move_time_minutes"].isna().sum()
        + (merged["move_time_minutes"] < 0).sum()
    )
    checks.append(
        _result(
            "capacity_routing_times_valid",
            "routing operation times valid",
            "FAIL" if invalid_timing else "PASS",
            f"Invalid setup/run/move time rows: {invalid_timing}" if invalid_timing else "Routing setup/run/move times are valid.",
            invalid_timing,
        )
    )
    merged["required_setup_hours"] = (merged["setup_time_minutes"] / 60).where(merged["planned_production_qty"] > 0, 0)
    merged["required_run_hours"] = merged["planned_production_qty"] * merged["run_time_minutes_per_unit"] / 60
    merged["required_move_hours"] = merged["planned_production_qty"] * merged["move_time_minutes"] / 60
    merged["total_required_hours"] = merged["required_setup_hours"] + merged["required_run_hours"] + merged["required_move_hours"]
    detail_columns = [
        "planning_run_id",
        "period_start",
        "period_end",
        "finished_sku",
        "finished_product_name",
        "operation_id",
        "operation_sequence",
        "operation_name",
        "workstation_id",
        "planned_production_qty",
        "setup_time_minutes",
        "run_time_minutes_per_unit",
        "move_time_minutes",
        "required_setup_hours",
        "required_run_hours",
        "required_move_hours",
        "total_required_hours",
        "can_run_in_parallel_flag",
        "parallel_group_id",
        "join_required_before_next_flag",
    ]
    detail = merged[detail_columns].copy()
    detail["advisory_only_flag"] = True
    return detail


def _build_workstation_load(
    detail: pd.DataFrame,
    mps: pd.DataFrame,
    workstations: pd.DataFrame,
    calendar: pd.DataFrame,
    checks: list[dict],
) -> pd.DataFrame:
    periods = mps[["planning_run_id", "period_start", "period_end"]].drop_duplicates().copy()
    active_workstations = workstations[_to_bool(workstations["active_flag"])].copy()
    grid = periods.merge(active_workstations[["workstation_id", "workstation_name"]], how="cross")
    if detail.empty:
        grouped = pd.DataFrame()
    else:
        grouped = detail.groupby(["planning_run_id", "period_start", "period_end", "workstation_id"], as_index=False).agg(
            operation_count=("operation_id", "nunique"),
            finished_sku_count=("finished_sku", "nunique"),
            total_planned_production_qty=("planned_production_qty", "sum"),
            required_setup_hours=("required_setup_hours", "sum"),
            required_run_hours=("required_run_hours", "sum"),
            required_move_hours=("required_move_hours", "sum"),
            total_required_hours=("total_required_hours", "sum"),
        )
    load = grid.merge(grouped, on=["planning_run_id", "period_start", "period_end", "workstation_id"], how="left")
    fill_cols = [
        "operation_count",
        "finished_sku_count",
        "total_planned_production_qty",
        "required_setup_hours",
        "required_run_hours",
        "required_move_hours",
        "total_required_hours",
    ]
    for column in fill_cols:
        load[column] = pd.to_numeric(load[column], errors="coerce").fillna(0)
    availability, fallback_count = _build_calendar_availability(load, calendar)
    checks.append(
        _result(
            "capacity_calendar_shift_hours_parsed",
            "calendar shift hours parsed",
            "WARNING" if fallback_count else "PASS",
            f"Calendar rows using fallback shift hours: {fallback_count}" if fallback_count else "Calendar shift hours parsed without fallback.",
            fallback_count,
        )
    )
    load = load.merge(availability, on=["period_start", "period_end", "workstation_id"], how="left")
    load["available_hours"] = pd.to_numeric(load["available_hours"], errors="coerce").fillna(0).clip(lower=0)
    load["no_capacity_record_flag"] = (load["available_hours"] <= 0) & (load["total_required_hours"] > 0)
    load["utilization_pct"] = 0.0
    has_capacity = load["available_hours"] > 0
    load.loc[has_capacity, "utilization_pct"] = load.loc[has_capacity, "total_required_hours"] / load.loc[has_capacity, "available_hours"] * 100
    load["capacity_gap_hours"] = load["available_hours"] - load["total_required_hours"]
    load["overload_flag"] = load["utilization_pct"] > 100
    load["near_capacity_flag"] = (load["utilization_pct"] > 85) & (load["utilization_pct"] <= 100)
    load["capacity_status"] = load.apply(_capacity_status, axis=1)
    load["workstation_capacity_basis"] = WORKSTATION_CAPACITY_BASIS
    load["workstation_capacity_unit_count"] = 1
    load["effective_workstation_available_hours"] = load["available_hours"]
    load["workstation_capacity_interpretation"] = load.apply(_workstation_capacity_interpretation, axis=1)
    load["capacity_planning_basis"] = CAPACITY_PLANNING_BASIS
    load["source_phase"] = "PHASE4_MPS_ROUTING_RESOURCE_CALENDAR"
    load["advisory_only_flag"] = True
    return load[
        [
            "planning_run_id",
            "period_start",
            "period_end",
            "workstation_id",
            "workstation_name",
            "operation_count",
            "finished_sku_count",
            "total_planned_production_qty",
            "required_setup_hours",
            "required_run_hours",
            "required_move_hours",
            "total_required_hours",
            "available_hours",
            "utilization_pct",
            "capacity_gap_hours",
            "capacity_status",
            "overload_flag",
            "near_capacity_flag",
            "no_capacity_record_flag",
            "workstation_capacity_basis",
            "workstation_capacity_unit_count",
            "effective_workstation_available_hours",
            "workstation_capacity_interpretation",
            "capacity_planning_basis",
            "source_phase",
            "advisory_only_flag",
        ]
    ].copy()


def _build_calendar_availability(load: pd.DataFrame, calendar: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    rows = []
    fallback_count = 0
    workstation_calendar = calendar[
        (calendar["resource_scope"].astype(str).str.strip() == "WORKSTATION") & _to_bool(calendar["available_flag"])
    ].copy()
    for _, row in load[["period_start", "period_end", "workstation_id"]].drop_duplicates().iterrows():
        period_start = pd.to_datetime(row["period_start"], errors="coerce")
        period_end = pd.to_datetime(row["period_end"], errors="coerce")
        workstation_id = str(row["workstation_id"]).strip()
        available_hours = 0.0
        if pd.isna(period_start) or pd.isna(period_end):
            rows.append({**row.to_dict(), "available_hours": 0.0})
            continue
        period_weekdays = _weekdays_between(period_start.to_pydatetime(), period_end.to_pydatetime())
        relevant = workstation_calendar[
            (workstation_calendar["resource_id"].astype(str).str.strip() == workstation_id)
            & (workstation_calendar["weekday"].astype(str).str.strip().isin(period_weekdays))
        ]
        for _, cal_row in relevant.iterrows():
            hours, used_fallback = _calendar_daily_hours(cal_row)
            available_hours += hours
            fallback_count += int(used_fallback)
        rows.append(
            {
                "period_start": row["period_start"],
                "period_end": row["period_end"],
                "workstation_id": workstation_id,
                "available_hours": round(available_hours, 4),
            }
        )
    return pd.DataFrame(rows), fallback_count


def _build_machine_load(detail: pd.DataFrame, operation_resources: pd.DataFrame, machines: pd.DataFrame) -> pd.DataFrame:
    resources = operation_resources[_to_bool(operation_resources["active_flag"])].copy()
    resources["required_machine_count"] = pd.to_numeric(resources["required_machine_count"], errors="coerce").fillna(0).clip(lower=0)
    merged = detail.merge(
        resources[["operation_id", "workstation_id", "required_machine_type", "required_machine_count"]],
        on=["operation_id", "workstation_id"],
        how="left",
    )
    merged["required_machine_type"] = merged["required_machine_type"].fillna("")
    merged["required_machine_count"] = pd.to_numeric(merged["required_machine_count"], errors="coerce").fillna(0).clip(lower=0)
    merged = merged[merged["required_machine_count"] > 0].copy()
    merged["machine_required_hours"] = merged["total_required_hours"] * merged["required_machine_count"]
    grouped = merged.groupby(
        ["planning_run_id", "period_start", "period_end", "workstation_id", "required_machine_type"],
        as_index=False,
    ).agg(
        operation_count=("operation_id", "nunique"),
        finished_sku_count=("finished_sku", "nunique"),
        total_planned_production_qty=("planned_production_qty", "sum"),
        machine_required_hours=("machine_required_hours", "sum"),
    )
    active_machines = machines[_to_bool(machines["active_flag"])].copy()
    active_machines["machine_count"] = pd.to_numeric(active_machines["machine_count"], errors="coerce").fillna(0).clip(lower=0)
    active_machines["available_hours_per_week"] = pd.to_numeric(active_machines["available_hours_per_week"], errors="coerce").fillna(0).clip(lower=0)
    active_machines["available_machine_hours"] = active_machines["machine_count"] * active_machines["available_hours_per_week"]
    availability = active_machines.groupby(["workstation_id", "machine_type"], as_index=False).agg(
        available_machine_hours=("available_machine_hours", "sum")
    ).rename(columns={"machine_type": "required_machine_type"})
    result = grouped.merge(availability, on=["workstation_id", "required_machine_type"], how="left")
    result["available_machine_hours"] = pd.to_numeric(result["available_machine_hours"], errors="coerce").fillna(0).clip(lower=0)
    result["no_machine_capacity_record_flag"] = (result["available_machine_hours"] <= 0) & (result["machine_required_hours"] > 0)
    result["machine_utilization_pct"] = 0.0
    has_capacity = result["available_machine_hours"] > 0
    result.loc[has_capacity, "machine_utilization_pct"] = (
        result.loc[has_capacity, "machine_required_hours"] / result.loc[has_capacity, "available_machine_hours"] * 100
    )
    result["machine_capacity_gap_hours"] = result["available_machine_hours"] - result["machine_required_hours"]
    result["machine_overload_flag"] = result["machine_utilization_pct"] > 100
    result["machine_near_capacity_flag"] = (result["machine_utilization_pct"] > 85) & (result["machine_utilization_pct"] <= 100)
    result["machine_capacity_status"] = result.apply(
        lambda row: _layer_status(
            required=row["machine_required_hours"],
            available=row["available_machine_hours"],
            utilization=row["machine_utilization_pct"],
            no_record=row["no_machine_capacity_record_flag"],
        ),
        axis=1,
    )
    result["capacity_planning_basis"] = MACHINE_CAPACITY_PLANNING_BASIS
    result["source_phase"] = "PHASE4_OPERATION_DETAIL_ROUTING_MACHINE_MASTER"
    result["advisory_only_flag"] = True
    return result[
        [
            "planning_run_id",
            "period_start",
            "period_end",
            "workstation_id",
            "required_machine_type",
            "operation_count",
            "finished_sku_count",
            "total_planned_production_qty",
            "machine_required_hours",
            "available_machine_hours",
            "machine_utilization_pct",
            "machine_capacity_gap_hours",
            "machine_capacity_status",
            "machine_overload_flag",
            "machine_near_capacity_flag",
            "no_machine_capacity_record_flag",
            "capacity_planning_basis",
            "source_phase",
            "advisory_only_flag",
        ]
    ].copy()


def _build_labor_load(detail: pd.DataFrame, operation_resources: pd.DataFrame, labor: pd.DataFrame) -> pd.DataFrame:
    resources = operation_resources[_to_bool(operation_resources["active_flag"])].copy()
    resources["required_worker_count"] = pd.to_numeric(resources["required_worker_count"], errors="coerce").fillna(0).clip(lower=0)
    merged = detail.merge(
        resources[["operation_id", "workstation_id", "required_labor_skill", "required_worker_count"]],
        on=["operation_id", "workstation_id"],
        how="left",
    )
    merged["required_labor_skill"] = merged["required_labor_skill"].fillna("")
    merged["required_worker_count"] = pd.to_numeric(merged["required_worker_count"], errors="coerce").fillna(0).clip(lower=0)
    merged = merged[merged["required_worker_count"] > 0].copy()
    merged["labor_required_hours"] = merged["total_required_hours"] * merged["required_worker_count"]
    grouped = merged.groupby(
        ["planning_run_id", "period_start", "period_end", "workstation_id", "required_labor_skill"],
        as_index=False,
    ).agg(
        operation_count=("operation_id", "nunique"),
        finished_sku_count=("finished_sku", "nunique"),
        total_planned_production_qty=("planned_production_qty", "sum"),
        labor_required_hours=("labor_required_hours", "sum"),
    )
    active_labor = labor[_to_bool(labor["active_flag"])].copy()
    active_labor["workers_available"] = pd.to_numeric(active_labor["workers_available"], errors="coerce").fillna(0).clip(lower=0)
    active_labor["hours_per_worker_per_week"] = pd.to_numeric(active_labor["hours_per_worker_per_week"], errors="coerce").fillna(0).clip(lower=0)
    active_labor["available_labor_hours"] = active_labor["workers_available"] * active_labor["hours_per_worker_per_week"]
    availability = active_labor.groupby(["workstation_id", "skill_type"], as_index=False).agg(
        available_labor_hours=("available_labor_hours", "sum")
    ).rename(columns={"skill_type": "required_labor_skill"})
    result = grouped.merge(availability, on=["workstation_id", "required_labor_skill"], how="left")
    result["available_labor_hours"] = pd.to_numeric(result["available_labor_hours"], errors="coerce").fillna(0).clip(lower=0)
    result["no_labor_capacity_record_flag"] = (result["available_labor_hours"] <= 0) & (result["labor_required_hours"] > 0)
    result["labor_utilization_pct"] = 0.0
    has_capacity = result["available_labor_hours"] > 0
    result.loc[has_capacity, "labor_utilization_pct"] = (
        result.loc[has_capacity, "labor_required_hours"] / result.loc[has_capacity, "available_labor_hours"] * 100
    )
    result["labor_capacity_gap_hours"] = result["available_labor_hours"] - result["labor_required_hours"]
    result["labor_soft_warning_threshold_pct"] = LABOR_SOFT_WARNING_THRESHOLD_PCT
    result["labor_hard_overload_threshold_pct"] = LABOR_HARD_OVERLOAD_THRESHOLD_PCT
    result["labor_high_utilization_warning_flag"] = (
        (result["labor_utilization_pct"] > LABOR_SOFT_WARNING_THRESHOLD_PCT)
        & (result["labor_utilization_pct"] <= LABOR_HARD_OVERLOAD_THRESHOLD_PCT)
    )
    result["labor_hard_overload_flag"] = result["labor_utilization_pct"] > LABOR_HARD_OVERLOAD_THRESHOLD_PCT
    result["labor_overload_flag"] = result["labor_hard_overload_flag"] | result["no_labor_capacity_record_flag"]
    result["labor_near_capacity_flag"] = result["labor_high_utilization_warning_flag"]
    result["labor_capacity_status"] = result.apply(
        lambda row: _labor_layer_status(
            required=row["labor_required_hours"],
            available=row["available_labor_hours"],
            utilization=row["labor_utilization_pct"],
            no_record=row["no_labor_capacity_record_flag"],
        ),
        axis=1,
    )
    result["labor_capacity_interpretation"] = result.apply(_labor_capacity_interpretation, axis=1)
    result["capacity_planning_basis"] = LABOR_CAPACITY_PLANNING_BASIS
    result["source_phase"] = "PHASE4_OPERATION_DETAIL_ROUTING_LABOR_MASTER"
    result["advisory_only_flag"] = True
    return result[
        [
            "planning_run_id",
            "period_start",
            "period_end",
            "workstation_id",
            "required_labor_skill",
            "operation_count",
            "finished_sku_count",
            "total_planned_production_qty",
            "labor_required_hours",
            "available_labor_hours",
            "labor_utilization_pct",
            "labor_capacity_gap_hours",
            "labor_capacity_status",
            "labor_overload_flag",
            "labor_near_capacity_flag",
            "no_labor_capacity_record_flag",
            "labor_soft_warning_threshold_pct",
            "labor_hard_overload_threshold_pct",
            "labor_high_utilization_warning_flag",
            "labor_hard_overload_flag",
            "labor_capacity_interpretation",
            "capacity_planning_basis",
            "source_phase",
            "advisory_only_flag",
        ]
    ].copy()


def _build_constraint_bridge(workstation: pd.DataFrame, machine: pd.DataFrame, labor: pd.DataFrame) -> pd.DataFrame:
    bridge = workstation[
        [
            "planning_run_id",
            "period_start",
            "period_end",
            "workstation_id",
            "workstation_name",
            "capacity_status",
            "utilization_pct",
            "overload_flag",
            "workstation_capacity_basis",
            "workstation_capacity_interpretation",
        ]
    ].rename(
        columns={
            "capacity_status": "workstation_capacity_status",
            "utilization_pct": "workstation_utilization_pct",
            "overload_flag": "workstation_overload_flag",
        }
    )
    keys = ["planning_run_id", "period_start", "period_end", "workstation_id"]
    machine_summary = machine.assign(
        _machine_constrained=machine["machine_capacity_status"].isin(["OVERLOADED", "NO_CAPACITY_RECORD"])
    ).groupby(keys, as_index=False).agg(
        machine_constraint_flag=("_machine_constrained", "max"),
        overloaded_machine_types=("required_machine_type", lambda s: ";".join(sorted(set(s[machine.loc[s.index, "machine_capacity_status"].isin(["OVERLOADED", "NO_CAPACITY_RECORD"])])))),
        highest_machine_utilization_pct=("machine_utilization_pct", "max"),
    )
    labor_summary = labor.assign(
        _labor_constrained=labor["labor_capacity_status"].isin(["OVERLOADED", "NO_CAPACITY_RECORD"]),
        _labor_high_warning=labor["labor_capacity_status"].isin(["HIGH_UTILIZATION_WARNING"]),
    ).groupby(keys, as_index=False).agg(
        labor_constraint_flag=("_labor_constrained", "max"),
        overloaded_labor_skills=("required_labor_skill", lambda s: ";".join(sorted(set(s[labor.loc[s.index, "labor_capacity_status"].isin(["OVERLOADED", "NO_CAPACITY_RECORD"])])))),
        labor_high_utilization_warning_flag=("_labor_high_warning", "max"),
        labor_hard_overload_flag=("labor_hard_overload_flag", "max"),
        high_utilization_labor_skills=("required_labor_skill", lambda s: ";".join(sorted(set(s[labor.loc[s.index, "labor_capacity_status"].isin(["HIGH_UTILIZATION_WARNING"])])))),
        highest_labor_utilization_pct=("labor_utilization_pct", "max"),
    )
    bridge = bridge.merge(machine_summary, on=keys, how="left").merge(labor_summary, on=keys, how="left")
    bridge["machine_constraint_flag"] = bridge["machine_constraint_flag"].fillna(False).astype(bool)
    bridge["labor_constraint_flag"] = bridge["labor_constraint_flag"].fillna(False).astype(bool)
    bridge["overloaded_machine_types"] = bridge["overloaded_machine_types"].fillna("")
    bridge["overloaded_labor_skills"] = bridge["overloaded_labor_skills"].fillna("")
    bridge["high_utilization_labor_skills"] = bridge["high_utilization_labor_skills"].fillna("")
    bridge["labor_high_utilization_warning_flag"] = bridge["labor_high_utilization_warning_flag"].fillna(False).astype(bool)
    bridge["labor_hard_overload_flag"] = bridge["labor_hard_overload_flag"].fillna(False).astype(bool)
    bridge["highest_machine_utilization_pct"] = pd.to_numeric(bridge["highest_machine_utilization_pct"], errors="coerce").fillna(0)
    bridge["highest_labor_utilization_pct"] = pd.to_numeric(bridge["highest_labor_utilization_pct"], errors="coerce").fillna(0)
    bridge["combined_constraint_type"] = bridge.apply(_combined_constraint_type, axis=1)
    bridge["constraint_review_required_flag"] = (
        bridge["workstation_overload_flag"].astype(bool)
        | bridge["machine_constraint_flag"].astype(bool)
        | bridge["labor_constraint_flag"].astype(bool)
        | bridge["labor_high_utilization_warning_flag"].astype(bool)
    )
    bridge["constraint_interpretation"] = bridge.apply(_constraint_interpretation, axis=1)
    bridge["capacity_planning_basis"] = CONSTRAINT_BRIDGE_PLANNING_BASIS
    bridge["source_phase"] = "PHASE4_WORKSTATION_MACHINE_LABOR_CAPACITY"
    bridge["advisory_only_flag"] = True
    return bridge[
        [
            "planning_run_id",
            "period_start",
            "period_end",
            "workstation_id",
            "workstation_name",
            "workstation_capacity_status",
            "workstation_utilization_pct",
            "workstation_overload_flag",
            "machine_constraint_flag",
            "overloaded_machine_types",
            "highest_machine_utilization_pct",
            "labor_constraint_flag",
            "overloaded_labor_skills",
            "labor_high_utilization_warning_flag",
            "labor_hard_overload_flag",
            "high_utilization_labor_skills",
            "highest_labor_utilization_pct",
            "workstation_capacity_basis",
            "workstation_capacity_interpretation",
            "combined_constraint_type",
            "constraint_interpretation",
            "constraint_review_required_flag",
            "capacity_planning_basis",
            "source_phase",
            "advisory_only_flag",
        ]
    ].copy()


def _build_capacity_feasibility_summary(
    workstation: pd.DataFrame,
    machine: pd.DataFrame,
    labor: pd.DataFrame,
    bridge: pd.DataFrame,
) -> pd.DataFrame:
    keys = ["planning_run_id", "period_start", "period_end"]
    work = workstation.copy()
    work["_overloaded"] = work["capacity_status"].astype(str).isin(["OVERLOADED", "NO_CAPACITY_RECORD"])
    work["_near"] = work["capacity_status"].astype(str).eq("NEAR_CAPACITY")
    work["_feasible"] = work["capacity_status"].astype(str).isin(["FEASIBLE", "NO_LOAD"])
    summary = work.groupby(keys, as_index=False).agg(
        workstation_count=("workstation_id", "nunique"),
        overloaded_workstation_count=("_overloaded", "sum"),
        near_capacity_workstation_count=("_near", "sum"),
        feasible_workstation_count=("_feasible", "sum"),
        max_workstation_utilization_pct=("utilization_pct", "max"),
        avg_workstation_utilization_pct=("utilization_pct", "mean"),
        total_required_workstation_hours=("total_required_hours", "sum"),
        total_available_workstation_hours=("available_hours", "sum"),
        total_workstation_capacity_gap_hours=("capacity_gap_hours", "sum"),
    )
    machine_period = machine.assign(
        _machine_constraint=machine["machine_capacity_status"].astype(str).isin(["OVERLOADED", "NO_CAPACITY_RECORD"])
    ).groupby(keys, as_index=False).agg(
        machine_constraint_count=("_machine_constraint", "sum"),
        max_machine_utilization_pct=("machine_utilization_pct", "max"),
    )
    labor_period = labor.assign(
        _labor_hard=labor["labor_capacity_status"].astype(str).isin(["OVERLOADED", "NO_CAPACITY_RECORD"]),
        _labor_warning=labor["labor_capacity_status"].astype(str).eq("HIGH_UTILIZATION_WARNING"),
    ).groupby(keys, as_index=False).agg(
        labor_hard_overload_count=("_labor_hard", "sum"),
        labor_high_utilization_warning_count=("_labor_warning", "sum"),
        max_labor_utilization_pct=("labor_utilization_pct", "max"),
    )
    review_period = bridge.groupby(keys, as_index=False).agg(
        constraint_review_required_count=("constraint_review_required_flag", lambda s: int(_to_bool(s).sum()))
    )
    summary = summary.merge(machine_period, on=keys, how="left").merge(labor_period, on=keys, how="left").merge(review_period, on=keys, how="left")
    fill_zero = [
        "machine_constraint_count",
        "max_machine_utilization_pct",
        "labor_hard_overload_count",
        "labor_high_utilization_warning_count",
        "max_labor_utilization_pct",
        "constraint_review_required_count",
    ]
    for column in fill_zero:
        summary[column] = pd.to_numeric(summary[column], errors="coerce").fillna(0)
    summary["main_constraint_layer"] = summary.apply(_main_constraint_layer, axis=1)
    summary["capacity_feasibility_status"] = summary.apply(_capacity_feasibility_status, axis=1)
    summary["capacity_feasibility_reason"] = summary.apply(_capacity_feasibility_reason, axis=1)
    summary["capacity_planning_basis"] = FEASIBILITY_SUMMARY_PLANNING_BASIS
    summary["source_phase"] = STEP4C_SOURCE_PHASE
    summary["advisory_only_flag"] = True
    return summary[
        [
            "planning_run_id",
            "period_start",
            "period_end",
            "workstation_count",
            "overloaded_workstation_count",
            "near_capacity_workstation_count",
            "feasible_workstation_count",
            "max_workstation_utilization_pct",
            "avg_workstation_utilization_pct",
            "total_required_workstation_hours",
            "total_available_workstation_hours",
            "total_workstation_capacity_gap_hours",
            "machine_constraint_count",
            "labor_hard_overload_count",
            "labor_high_utilization_warning_count",
            "max_machine_utilization_pct",
            "max_labor_utilization_pct",
            "constraint_review_required_count",
            "main_constraint_layer",
            "capacity_feasibility_status",
            "capacity_feasibility_reason",
            "capacity_planning_basis",
            "source_phase",
            "advisory_only_flag",
        ]
    ].copy()


def _build_bottleneck_candidate_summary(
    workstation: pd.DataFrame,
    machine: pd.DataFrame,
    labor: pd.DataFrame,
    bridge: pd.DataFrame,
) -> pd.DataFrame:
    keys = ["planning_run_id", "workstation_id"]
    work = workstation.copy()
    work["_overloaded"] = work["capacity_status"].astype(str).isin(["OVERLOADED", "NO_CAPACITY_RECORD"])
    work["_near"] = work["capacity_status"].astype(str).eq("NEAR_CAPACITY")
    candidates = work.groupby(keys, as_index=False).agg(
        workstation_name=("workstation_name", "first"),
        periods_observed=("period_start", "nunique"),
        overloaded_period_count=("_overloaded", "sum"),
        near_capacity_period_count=("_near", "sum"),
        max_workstation_utilization_pct=("utilization_pct", "max"),
        avg_workstation_utilization_pct=("utilization_pct", "mean"),
        total_required_workstation_hours=("total_required_hours", "sum"),
        total_available_workstation_hours=("available_hours", "sum"),
        cumulative_capacity_gap_hours=("capacity_gap_hours", "sum"),
        workstation_capacity_basis=("workstation_capacity_basis", "first"),
    )
    machine_summary = machine.assign(
        _machine_constraint=machine["machine_capacity_status"].astype(str).isin(["OVERLOADED", "NO_CAPACITY_RECORD"])
    ).groupby(keys, as_index=False).agg(
        machine_constraint_period_count=("_machine_constraint", "sum"),
        max_machine_utilization_pct=("machine_utilization_pct", "max"),
    )
    labor_summary = labor.assign(
        _labor_warning=labor["labor_capacity_status"].astype(str).eq("HIGH_UTILIZATION_WARNING"),
        _labor_hard=labor["labor_capacity_status"].astype(str).isin(["OVERLOADED", "NO_CAPACITY_RECORD"]),
    ).groupby(keys, as_index=False).agg(
        labor_high_utilization_warning_period_count=("_labor_warning", "sum"),
        labor_hard_overload_period_count=("_labor_hard", "sum"),
        max_labor_utilization_pct=("labor_utilization_pct", "max"),
    )
    candidates = candidates.merge(machine_summary, on=keys, how="left").merge(labor_summary, on=keys, how="left")
    for column in [
        "machine_constraint_period_count",
        "max_machine_utilization_pct",
        "labor_high_utilization_warning_period_count",
        "labor_hard_overload_period_count",
        "max_labor_utilization_pct",
    ]:
        candidates[column] = pd.to_numeric(candidates[column], errors="coerce").fillna(0)
    candidates["bottleneck_candidate_score"] = candidates.apply(_bottleneck_candidate_score, axis=1)
    candidates = candidates.sort_values(
        ["bottleneck_candidate_score", "max_workstation_utilization_pct", "cumulative_capacity_gap_hours"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    candidates["bottleneck_candidate_rank"] = range(1, len(candidates) + 1)
    candidates["bottleneck_candidate_level"] = candidates.apply(_bottleneck_candidate_level, axis=1)
    candidates["bottleneck_candidate_reason"] = candidates.apply(_bottleneck_candidate_reason, axis=1)
    candidates["source_phase"] = STEP4C_SOURCE_PHASE
    candidates["advisory_only_flag"] = True
    return candidates[
        [
            "planning_run_id",
            "workstation_id",
            "workstation_name",
            "periods_observed",
            "overloaded_period_count",
            "near_capacity_period_count",
            "labor_high_utilization_warning_period_count",
            "machine_constraint_period_count",
            "labor_hard_overload_period_count",
            "max_workstation_utilization_pct",
            "avg_workstation_utilization_pct",
            "max_machine_utilization_pct",
            "max_labor_utilization_pct",
            "total_required_workstation_hours",
            "total_available_workstation_hours",
            "cumulative_capacity_gap_hours",
            "bottleneck_candidate_score",
            "bottleneck_candidate_rank",
            "bottleneck_candidate_level",
            "bottleneck_candidate_reason",
            "workstation_capacity_basis",
            "source_phase",
            "advisory_only_flag",
        ]
    ].copy()


def _build_capacity_manager_review_queue(
    feasibility: pd.DataFrame,
    workstation: pd.DataFrame,
    machine: pd.DataFrame,
    labor: pd.DataFrame,
    bridge: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    counter = 1
    for _, row in feasibility.iterrows():
        if str(row["capacity_feasibility_status"]) in {"NOT_CAPACITY_FEASIBLE", "CAPACITY_REVIEW_REQUIRED", "REVIEW_REQUIRED"}:
            rows.append(
                _review_row(
                    counter,
                    row,
                    workstation_id="ALL",
                    workstation_name="All Workstations",
                    issue_type="PERIOD_NOT_CAPACITY_FEASIBLE" if row["capacity_feasibility_status"] == "NOT_CAPACITY_FEASIBLE" else "REVIEW_REQUIRED",
                    issue_severity="CRITICAL" if row["capacity_feasibility_status"] == "NOT_CAPACITY_FEASIBLE" else "HIGH",
                    issue_description=str(row["capacity_feasibility_reason"]),
                    main_constraint_layer=str(row["main_constraint_layer"]),
                    utilization_pct=row["max_workstation_utilization_pct"],
                    capacity_gap_hours=row["total_workstation_capacity_gap_hours"],
                    suggested_review_action="REVIEW_MPS_VOLUME",
                )
            )
            counter += 1
    for _, row in workstation.iterrows():
        status = str(row["capacity_status"])
        if status in {"OVERLOADED", "NO_CAPACITY_RECORD", "NEAR_CAPACITY"}:
            if status == "OVERLOADED":
                issue_type, severity, action = "WORKSTATION_OVERLOAD", "HIGH", "REVIEW_WORKSTATION_CALENDAR"
            elif status == "NO_CAPACITY_RECORD":
                issue_type, severity, action = "NO_CAPACITY_RECORD", "CRITICAL", "REVIEW_WORKSTATION_CALENDAR"
            else:
                issue_type, severity, action = "WORKSTATION_NEAR_CAPACITY", "MEDIUM", "REVIEW_SHIFT_CAPACITY"
            rows.append(
                _review_row(
                    counter,
                    row,
                    workstation_id=row["workstation_id"],
                    workstation_name=row["workstation_name"],
                    issue_type=issue_type,
                    issue_severity=severity,
                    issue_description=f"{row['workstation_name']} has {status} workstation calendar load.",
                    main_constraint_layer="WORKSTATION_CALENDAR",
                    utilization_pct=row["utilization_pct"],
                    capacity_gap_hours=row["capacity_gap_hours"],
                    suggested_review_action=action,
                )
            )
            counter += 1
    machine_lookup = bridge.set_index(["planning_run_id", "period_start", "period_end", "workstation_id"])[["workstation_name"]].to_dict("index")
    for _, row in machine.iterrows():
        status = str(row["machine_capacity_status"])
        if status in {"OVERLOADED", "NO_CAPACITY_RECORD"}:
            key = (row["planning_run_id"], row["period_start"], row["period_end"], row["workstation_id"])
            workstation_name = machine_lookup.get(key, {}).get("workstation_name", row["workstation_id"])
            rows.append(
                _review_row(
                    counter,
                    row,
                    workstation_id=row["workstation_id"],
                    workstation_name=workstation_name,
                    issue_type="MACHINE_CAPACITY_CONSTRAINT" if status == "OVERLOADED" else "NO_CAPACITY_RECORD",
                    issue_severity="HIGH" if status == "OVERLOADED" else "CRITICAL",
                    issue_description=f"{row['required_machine_type']} has {status} machine capacity.",
                    main_constraint_layer="MACHINE",
                    utilization_pct=row["machine_utilization_pct"],
                    capacity_gap_hours=row["machine_capacity_gap_hours"],
                    suggested_review_action="REVIEW_MACHINE_RESOURCE_DATA",
                )
            )
            counter += 1
    for _, row in labor.iterrows():
        status = str(row["labor_capacity_status"])
        if status in {"HIGH_UTILIZATION_WARNING", "OVERLOADED", "NO_CAPACITY_RECORD"}:
            key = (row["planning_run_id"], row["period_start"], row["period_end"], row["workstation_id"])
            workstation_name = machine_lookup.get(key, {}).get("workstation_name", row["workstation_id"])
            if status == "HIGH_UTILIZATION_WARNING":
                issue_type, severity, layer, action = "LABOR_HIGH_UTILIZATION_WARNING", "MEDIUM", "LABOR_HIGH_UTILIZATION", "REVIEW_LABOR_RESOURCE_DATA"
            elif status == "OVERLOADED":
                issue_type, severity, layer, action = "LABOR_HARD_OVERLOAD", "HIGH", "LABOR", "REVIEW_LABOR_RESOURCE_DATA"
            else:
                issue_type, severity, layer, action = "NO_CAPACITY_RECORD", "CRITICAL", "LABOR", "REVIEW_LABOR_RESOURCE_DATA"
            rows.append(
                _review_row(
                    counter,
                    row,
                    workstation_id=row["workstation_id"],
                    workstation_name=workstation_name,
                    issue_type=issue_type,
                    issue_severity=severity,
                    issue_description=f"{row['required_labor_skill']} has {status} labor capacity.",
                    main_constraint_layer=layer,
                    utilization_pct=row["labor_utilization_pct"],
                    capacity_gap_hours=row["labor_capacity_gap_hours"],
                    suggested_review_action=action,
                )
            )
            counter += 1
    review = pd.DataFrame(rows)
    columns = [
        "planning_run_id",
        "review_item_id",
        "period_start",
        "period_end",
        "workstation_id",
        "workstation_name",
        "issue_type",
        "issue_severity",
        "issue_description",
        "main_constraint_layer",
        "utilization_pct",
        "capacity_gap_hours",
        "suggested_review_action",
        "auto_action_allowed",
        "advisory_only_flag",
    ]
    if review.empty:
        return pd.DataFrame(columns=columns)
    return review[columns].copy()


def _calendar_daily_hours(row: pd.Series) -> tuple[float, bool]:
    break_minutes = pd.to_numeric(pd.Series([row.get("planned_break_minutes", 0)]), errors="coerce").fillna(0).iloc[0]
    try:
        start = datetime.strptime(str(row.get("shift_start", "")).strip(), "%H:%M")
        end = datetime.strptime(str(row.get("shift_end", "")).strip(), "%H:%M")
        hours = (end - start).total_seconds() / 3600
        if hours < 0:
            hours += 24
        return max(hours - float(break_minutes) / 60, 0), False
    except ValueError:
        return max(8 - float(break_minutes) / 60, 0), True


def _weekdays_between(start: datetime, end: datetime) -> set[str]:
    current = start
    names = set()
    while current <= end:
        names.add(current.strftime("%A"))
        current += timedelta(days=1)
    return names


def _capacity_status(row: pd.Series) -> str:
    if row["total_required_hours"] < 0 or row["available_hours"] < 0:
        return "REVIEW_REQUIRED"
    if row["total_required_hours"] == 0:
        return "NO_LOAD"
    if bool(row["no_capacity_record_flag"]):
        return "NO_CAPACITY_RECORD"
    if row["utilization_pct"] > 100:
        return "OVERLOADED"
    if row["utilization_pct"] > 85:
        return "NEAR_CAPACITY"
    return "FEASIBLE"


def _workstation_capacity_interpretation(row: pd.Series) -> str:
    if row["total_required_hours"] < 0 or row["available_hours"] < 0:
        return "REVIEW_REQUIRED"
    if bool(row["no_capacity_record_flag"]):
        return "NO_WORKSTATION_CAPACITY_RECORD"
    if str(row["capacity_status"]) == "OVERLOADED":
        return "SINGLE_CALENDAR_SLOT_OVERLOADED"
    if str(row["capacity_status"]) == "NEAR_CAPACITY":
        return "SINGLE_CALENDAR_SLOT_NEAR_CAPACITY"
    return "SINGLE_CALENDAR_SLOT_FEASIBLE"


def _layer_status(required: float, available: float, utilization: float, no_record: bool) -> str:
    if required < 0 or available < 0:
        return "REVIEW_REQUIRED"
    if required == 0:
        return "NO_LOAD"
    if bool(no_record):
        return "NO_CAPACITY_RECORD"
    if utilization > 100:
        return "OVERLOADED"
    if utilization > 85:
        return "NEAR_CAPACITY"
    return "FEASIBLE"


def _labor_layer_status(required: float, available: float, utilization: float, no_record: bool) -> str:
    if required < 0 or available < 0:
        return "REVIEW_REQUIRED"
    if required == 0:
        return "NO_LOAD"
    if bool(no_record):
        return "NO_CAPACITY_RECORD"
    if utilization > LABOR_HARD_OVERLOAD_THRESHOLD_PCT:
        return "OVERLOADED"
    if utilization > LABOR_SOFT_WARNING_THRESHOLD_PCT:
        return "HIGH_UTILIZATION_WARNING"
    return "FEASIBLE"


def _labor_capacity_interpretation(row: pd.Series) -> str:
    status = str(row["labor_capacity_status"])
    if status == "OVERLOADED":
        return "LABOR_HARD_OVERLOAD"
    if status == "HIGH_UTILIZATION_WARNING":
        return "HIGH_LABOR_UTILIZATION_REVIEW"
    if status == "NO_CAPACITY_RECORD":
        return "NO_LABOR_CAPACITY_RECORD"
    if status == "REVIEW_REQUIRED":
        return "REVIEW_REQUIRED"
    return "LOW_OR_NORMAL_LABOR_LOAD"


def _combined_constraint_type(row: pd.Series) -> str:
    workstation = bool(row["workstation_overload_flag"]) or str(row["workstation_capacity_status"]) == "NO_CAPACITY_RECORD"
    machine = bool(row["machine_constraint_flag"])
    labor = bool(row["labor_constraint_flag"])
    labor_warning = bool(row.get("labor_high_utilization_warning_flag", False))
    if workstation and machine and labor:
        return "WORKSTATION_MACHINE_AND_LABOR"
    if workstation and machine:
        return "WORKSTATION_AND_MACHINE"
    if workstation and labor:
        return "WORKSTATION_AND_LABOR"
    if machine and labor:
        return "MACHINE_AND_LABOR"
    if workstation and labor_warning:
        return "WORKSTATION_WITH_LABOR_HIGH_UTILIZATION_WARNING"
    if workstation:
        return "WORKSTATION_ONLY"
    if machine:
        return "MACHINE_ONLY"
    if labor:
        return "LABOR_ONLY"
    if labor_warning:
        return "LABOR_HIGH_UTILIZATION_WARNING_ONLY"
    return "NONE"


def _constraint_interpretation(row: pd.Series) -> str:
    if bool(row["machine_constraint_flag"]) or bool(row["labor_constraint_flag"]):
        return "HARD_MACHINE_OR_LABOR_CAPACITY_BLOCK"
    if str(row["workstation_capacity_status"]) == "NO_CAPACITY_RECORD":
        return "NO_CAPACITY_REVIEW_REQUIRED"
    if bool(row["workstation_overload_flag"]) and bool(row.get("labor_high_utilization_warning_flag", False)):
        return "WORKSTATION_CALENDAR_LIMITED_WITH_LABOR_STRESS_WARNING"
    if bool(row["workstation_overload_flag"]):
        return "WORKSTATION_CALENDAR_LIMITED_MACHINE_AND_LABOR_OK"
    if bool(row.get("labor_high_utilization_warning_flag", False)):
        return "LABOR_STRESS_WARNING_NO_HARD_CAPACITY_BLOCK"
    return "NO_CONSTRAINT_DETECTED"


def _main_constraint_layer(row: pd.Series) -> str:
    layers = []
    if row["overloaded_workstation_count"] > 0:
        layers.append("WORKSTATION_CALENDAR")
    if row["machine_constraint_count"] > 0:
        layers.append("MACHINE")
    if row["labor_hard_overload_count"] > 0:
        layers.append("LABOR")
    if row["labor_high_utilization_warning_count"] > 0:
        layers.append("LABOR_HIGH_UTILIZATION")
    if len(layers) > 1:
        return "MULTI_LAYER"
    if layers:
        return layers[0]
    return "NONE"


def _capacity_feasibility_status(row: pd.Series) -> str:
    if row["overloaded_workstation_count"] > 0 or row["machine_constraint_count"] > 0 or row["labor_hard_overload_count"] > 0:
        return "NOT_CAPACITY_FEASIBLE"
    if row["labor_high_utilization_warning_count"] > 0:
        return "FEASIBLE_WITH_LABOR_WARNING"
    if row["near_capacity_workstation_count"] > 0:
        return "CAPACITY_REVIEW_REQUIRED"
    return "FEASIBLE"


def _capacity_feasibility_reason(row: pd.Series) -> str:
    status = str(row["capacity_feasibility_status"])
    if status == "NOT_CAPACITY_FEASIBLE":
        return (
            f"Capacity review required: workstation_overloads={int(row['overloaded_workstation_count'])}, "
            f"machine_constraints={int(row['machine_constraint_count'])}, "
            f"labor_hard_overloads={int(row['labor_hard_overload_count'])}."
        )
    if status == "FEASIBLE_WITH_LABOR_WARNING":
        return f"No hard capacity block, but labor high-utilization warnings exist: {int(row['labor_high_utilization_warning_count'])}."
    if status == "CAPACITY_REVIEW_REQUIRED":
        return f"No hard overload, but near-capacity workstation count is {int(row['near_capacity_workstation_count'])}."
    return "No hard capacity constraints or high-utilization warnings detected."


def _bottleneck_candidate_score(row: pd.Series) -> float:
    score = 0.0
    overloaded_periods = float(row["overloaded_period_count"])
    if overloaded_periods > 0:
        score += 50
    score += 2 * overloaded_periods
    score += float(row["near_capacity_period_count"])
    score += float(row["labor_high_utilization_warning_period_count"])
    if float(row["max_workstation_utilization_pct"]) > 150:
        score += 10
    if float(row["max_workstation_utilization_pct"]) > 250:
        score += 20
    if float(row["cumulative_capacity_gap_hours"]) < 0:
        score += 10
    if float(row["machine_constraint_period_count"]) > 0:
        score += 5
    if float(row["labor_hard_overload_period_count"]) > 0:
        score += 5
    return round(score, 4)


def _bottleneck_candidate_level(row: pd.Series) -> str:
    overloaded = float(row["overloaded_period_count"])
    max_utilization = float(row["max_workstation_utilization_pct"])
    score = float(row["bottleneck_candidate_score"])
    if overloaded >= max(float(row["periods_observed"]) * 0.75, 1) or max_utilization > 250 or score >= 90:
        return "CRITICAL"
    if overloaded > 0 or score >= 60:
        return "HIGH"
    if float(row["near_capacity_period_count"]) > 0 or float(row["labor_high_utilization_warning_period_count"]) > 0 or score >= 20:
        return "MEDIUM"
    return "LOW"


def _bottleneck_candidate_reason(row: pd.Series) -> str:
    parts = [
        f"CRP bottleneck candidate evidence: overloaded_periods={int(row['overloaded_period_count'])}",
        f"near_capacity_periods={int(row['near_capacity_period_count'])}",
        f"labor_warning_periods={int(row['labor_high_utilization_warning_period_count'])}",
        f"max_workstation_utilization_pct={float(row['max_workstation_utilization_pct']):.2f}",
    ]
    return "; ".join(parts) + ". CRP candidate only; queue confirmation comes later."


def _review_row(
    counter: int,
    row: pd.Series,
    workstation_id: str,
    workstation_name: str,
    issue_type: str,
    issue_severity: str,
    issue_description: str,
    main_constraint_layer: str,
    utilization_pct: float,
    capacity_gap_hours: float,
    suggested_review_action: str,
) -> dict:
    return {
        "planning_run_id": row["planning_run_id"],
        "review_item_id": f"CAP-REV-{counter:04d}",
        "period_start": row["period_start"],
        "period_end": row["period_end"],
        "workstation_id": workstation_id,
        "workstation_name": workstation_name,
        "issue_type": issue_type,
        "issue_severity": issue_severity,
        "issue_description": issue_description,
        "main_constraint_layer": main_constraint_layer,
        "utilization_pct": utilization_pct,
        "capacity_gap_hours": capacity_gap_hours,
        "suggested_review_action": suggested_review_action,
        "auto_action_allowed": False,
        "advisory_only_flag": True,
    }


def _validate_capacity_outputs(
    load: pd.DataFrame,
    detail: pd.DataFrame,
    machine_load: pd.DataFrame,
    labor_load: pd.DataFrame,
    constraint_bridge: pd.DataFrame,
    feasibility_summary: pd.DataFrame,
    bottleneck_candidates: pd.DataFrame,
    manager_review_queue: pd.DataFrame,
    checks: list[dict],
) -> None:
    checks.append(_result("capacity_load_output_not_empty", "capacity load output not empty", "FAIL" if load.empty else "PASS", "Capacity load output has no rows." if load.empty else f"Capacity load output has {len(load)} rows.", 1 if load.empty else 0))
    duplicate_count = int(load.duplicated(["planning_run_id", "period_start", "period_end", "workstation_id"]).sum()) if not load.empty else 0
    checks.append(_result("capacity_load_grain_unique", "capacity load grain unique", "FAIL" if duplicate_count else "PASS", f"Duplicate workstation-period rows: {duplicate_count}" if duplicate_count else "Capacity load has one row per planning_run_id/period/workstation.", duplicate_count))
    invalid_numeric = 0
    for column in ["total_required_hours", "available_hours", "utilization_pct"]:
        values = pd.to_numeric(load[column], errors="coerce") if column in load.columns else pd.Series([None])
        invalid_numeric += int(values.isna().sum() + (values < 0).sum())
    checks.append(_result("capacity_load_numeric_values_valid", "capacity load numeric values valid", "FAIL" if invalid_numeric else "PASS", f"Invalid capacity numeric values: {invalid_numeric}" if invalid_numeric else "Capacity required, available, and utilization values are numeric and non-negative.", invalid_numeric))
    missing_status = int(load["capacity_status"].astype(str).str.strip().eq("").sum()) if "capacity_status" in load.columns else len(load)
    checks.append(_result("capacity_status_populated", "capacity status populated", "FAIL" if missing_status else "PASS", f"Rows missing capacity_status: {missing_status}" if missing_status else "capacity_status is populated for all rows.", missing_status))
    non_advisory = int((~_to_bool(load["advisory_only_flag"])).sum()) if "advisory_only_flag" in load.columns else len(load)
    checks.append(_result("capacity_load_advisory_only", "capacity load advisory only", "FAIL" if non_advisory else "PASS", f"Non-advisory capacity load rows: {non_advisory}" if non_advisory else "All capacity load rows are advisory-only.", non_advisory))
    workstation_basis_required = {
        "workstation_capacity_basis",
        "workstation_capacity_unit_count",
        "effective_workstation_available_hours",
        "workstation_capacity_interpretation",
    }
    missing_workstation_basis = sorted(workstation_basis_required.difference(load.columns))
    invalid_workstation_basis = len(missing_workstation_basis)
    if "workstation_capacity_basis" in load.columns:
        invalid_workstation_basis += int((load["workstation_capacity_basis"].astype(str) != WORKSTATION_CAPACITY_BASIS).sum())
    if "workstation_capacity_interpretation" in load.columns:
        invalid_workstation_basis += int(load["workstation_capacity_interpretation"].astype(str).str.strip().eq("").sum())
    if "effective_workstation_available_hours" in load.columns:
        values = pd.to_numeric(load["effective_workstation_available_hours"], errors="coerce")
        invalid_workstation_basis += int(values.isna().sum() + (values < 0).sum())
    checks.append(
        _result(
            "capacity_workstation_basis_valid",
            "workstation capacity basis valid",
            "FAIL" if invalid_workstation_basis else "PASS",
            f"Missing/invalid workstation capacity basis values: {invalid_workstation_basis}" if invalid_workstation_basis else f"Workstation capacity basis is {WORKSTATION_CAPACITY_BASIS}.",
            invalid_workstation_basis,
        )
    )
    checks.append(_result("capacity_operation_detail_exists", "capacity operation detail exists", "FAIL" if detail.empty else "PASS", "Operation detail output has no rows." if detail.empty else f"Operation detail output has {len(detail)} rows.", 1 if detail.empty else 0))
    _validate_layer_output(
        "machine",
        machine_load,
        {
            "planning_run_id",
            "period_start",
            "period_end",
            "workstation_id",
            "required_machine_type",
            "machine_required_hours",
            "available_machine_hours",
            "machine_utilization_pct",
            "machine_capacity_status",
            "advisory_only_flag",
        },
        ["machine_required_hours", "available_machine_hours", "machine_utilization_pct"],
        "machine_capacity_status",
        checks,
    )
    _validate_layer_output(
        "labor",
        labor_load,
        {
            "planning_run_id",
            "period_start",
            "period_end",
            "workstation_id",
            "required_labor_skill",
            "labor_required_hours",
            "available_labor_hours",
            "labor_utilization_pct",
            "labor_capacity_status",
            "labor_soft_warning_threshold_pct",
            "labor_hard_overload_threshold_pct",
            "labor_high_utilization_warning_flag",
            "labor_hard_overload_flag",
            "labor_capacity_interpretation",
            "advisory_only_flag",
        },
        ["labor_required_hours", "available_labor_hours", "labor_utilization_pct"],
        "labor_capacity_status",
        checks,
    )
    _validate_labor_thresholds(labor_load, checks)
    bridge_required = {
        "planning_run_id",
        "period_start",
        "period_end",
        "workstation_id",
        "workstation_name",
        "workstation_capacity_status",
        "workstation_utilization_pct",
        "workstation_overload_flag",
        "machine_constraint_flag",
        "overloaded_machine_types",
        "highest_machine_utilization_pct",
        "labor_constraint_flag",
        "overloaded_labor_skills",
        "labor_high_utilization_warning_flag",
        "labor_hard_overload_flag",
        "high_utilization_labor_skills",
        "highest_labor_utilization_pct",
        "workstation_capacity_basis",
        "workstation_capacity_interpretation",
        "combined_constraint_type",
        "constraint_interpretation",
        "constraint_review_required_flag",
        "advisory_only_flag",
    }
    missing_bridge = sorted(bridge_required.difference(constraint_bridge.columns))
    valid_constraint_types = {
        "NONE",
        "WORKSTATION_ONLY",
        "MACHINE_ONLY",
        "LABOR_ONLY",
        "MACHINE_AND_LABOR",
        "WORKSTATION_AND_MACHINE",
        "WORKSTATION_AND_LABOR",
        "WORKSTATION_MACHINE_AND_LABOR",
        "WORKSTATION_WITH_LABOR_HIGH_UTILIZATION_WARNING",
        "LABOR_HIGH_UTILIZATION_WARNING_ONLY",
        "REVIEW_REQUIRED",
    }
    invalid_bridge = len(missing_bridge)
    if not constraint_bridge.empty and "combined_constraint_type" in constraint_bridge.columns:
        invalid_bridge += int((~constraint_bridge["combined_constraint_type"].astype(str).isin(valid_constraint_types)).sum())
    if "advisory_only_flag" in constraint_bridge.columns:
        invalid_bridge += int((~_to_bool(constraint_bridge["advisory_only_flag"])).sum())
    else:
        invalid_bridge += len(constraint_bridge)
    if {"labor_high_utilization_warning_flag", "constraint_review_required_flag"}.issubset(constraint_bridge.columns):
        warning_without_review = _to_bool(constraint_bridge["labor_high_utilization_warning_flag"]) & ~_to_bool(
            constraint_bridge["constraint_review_required_flag"]
        )
        invalid_bridge += int(warning_without_review.sum())
    checks.append(
        _result(
            "capacity_constraint_bridge_valid",
            "capacity constraint bridge valid",
            "FAIL" if constraint_bridge.empty or invalid_bridge else "PASS",
            f"Constraint bridge rows={len(constraint_bridge)}; missing/invalid={invalid_bridge}" if invalid_bridge or constraint_bridge.empty else f"Constraint bridge has {len(constraint_bridge)} advisory rows.",
            invalid_bridge + (1 if constraint_bridge.empty else 0),
        )
    )
    _validate_step4c_outputs(feasibility_summary, bottleneck_candidates, manager_review_queue, load, checks)


def _validate_step4c_outputs(
    feasibility: pd.DataFrame,
    candidates: pd.DataFrame,
    review_queue: pd.DataFrame,
    workstation: pd.DataFrame,
    checks: list[dict],
) -> None:
    feasibility_required = {
        "planning_run_id",
        "period_start",
        "period_end",
        "workstation_count",
        "overloaded_workstation_count",
        "near_capacity_workstation_count",
        "feasible_workstation_count",
        "max_workstation_utilization_pct",
        "avg_workstation_utilization_pct",
        "total_required_workstation_hours",
        "total_available_workstation_hours",
        "total_workstation_capacity_gap_hours",
        "machine_constraint_count",
        "labor_hard_overload_count",
        "labor_high_utilization_warning_count",
        "max_machine_utilization_pct",
        "max_labor_utilization_pct",
        "constraint_review_required_count",
        "main_constraint_layer",
        "capacity_feasibility_status",
        "capacity_feasibility_reason",
        "capacity_planning_basis",
        "advisory_only_flag",
    }
    candidate_required = {
        "planning_run_id",
        "workstation_id",
        "workstation_name",
        "periods_observed",
        "overloaded_period_count",
        "near_capacity_period_count",
        "labor_high_utilization_warning_period_count",
        "machine_constraint_period_count",
        "labor_hard_overload_period_count",
        "max_workstation_utilization_pct",
        "avg_workstation_utilization_pct",
        "max_machine_utilization_pct",
        "max_labor_utilization_pct",
        "total_required_workstation_hours",
        "total_available_workstation_hours",
        "cumulative_capacity_gap_hours",
        "bottleneck_candidate_score",
        "bottleneck_candidate_rank",
        "bottleneck_candidate_level",
        "bottleneck_candidate_reason",
        "workstation_capacity_basis",
        "advisory_only_flag",
    }
    review_required = {
        "planning_run_id",
        "review_item_id",
        "period_start",
        "period_end",
        "workstation_id",
        "workstation_name",
        "issue_type",
        "issue_severity",
        "issue_description",
        "main_constraint_layer",
        "utilization_pct",
        "capacity_gap_hours",
        "suggested_review_action",
        "auto_action_allowed",
        "advisory_only_flag",
    }
    valid_feasibility_status = {"FEASIBLE", "FEASIBLE_WITH_LABOR_WARNING", "CAPACITY_REVIEW_REQUIRED", "NOT_CAPACITY_FEASIBLE", "REVIEW_REQUIRED"}
    valid_layers = {"NONE", "WORKSTATION_CALENDAR", "MACHINE", "LABOR", "LABOR_HIGH_UTILIZATION", "MULTI_LAYER", "REVIEW_REQUIRED"}
    valid_levels = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    valid_issue_types = {
        "WORKSTATION_OVERLOAD",
        "WORKSTATION_NEAR_CAPACITY",
        "LABOR_HIGH_UTILIZATION_WARNING",
        "MACHINE_CAPACITY_CONSTRAINT",
        "LABOR_HARD_OVERLOAD",
        "NO_CAPACITY_RECORD",
        "PERIOD_NOT_CAPACITY_FEASIBLE",
        "REVIEW_REQUIRED",
    }
    valid_severities = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

    invalid = 0
    invalid += int(feasibility.empty) + len(feasibility_required.difference(feasibility.columns))
    invalid += int(candidates.empty) + len(candidate_required.difference(candidates.columns))
    infeasible_exists = False
    if not feasibility.empty and "capacity_feasibility_status" in feasibility.columns:
        infeasible_exists = feasibility["capacity_feasibility_status"].astype(str).isin(["NOT_CAPACITY_FEASIBLE", "CAPACITY_REVIEW_REQUIRED", "REVIEW_REQUIRED"]).any()
    if infeasible_exists and review_queue.empty:
        invalid += 1
    if not review_queue.empty:
        invalid += len(review_required.difference(review_queue.columns))
    if not feasibility.empty and feasibility_required.issubset(feasibility.columns):
        invalid += int((~feasibility["capacity_feasibility_status"].astype(str).isin(valid_feasibility_status)).sum())
        invalid += int((~feasibility["main_constraint_layer"].astype(str).isin(valid_layers)).sum())
        invalid += int((feasibility["capacity_planning_basis"].astype(str) != FEASIBILITY_SUMMARY_PLANNING_BASIS).sum())
        invalid += int((~_to_bool(feasibility["advisory_only_flag"])).sum())
        overload_not_flagged = (pd.to_numeric(feasibility["overloaded_workstation_count"], errors="coerce") > 0) & (
            feasibility["capacity_feasibility_status"].astype(str) != "NOT_CAPACITY_FEASIBLE"
        )
        invalid += int(overload_not_flagged.sum())
    if not candidates.empty and candidate_required.issubset(candidates.columns):
        scores = pd.to_numeric(candidates["bottleneck_candidate_score"], errors="coerce")
        ranks = pd.to_numeric(candidates["bottleneck_candidate_rank"], errors="coerce")
        invalid += int(scores.isna().sum() + (scores < 0).sum())
        invalid += int(ranks.isna().sum() + candidates["bottleneck_candidate_rank"].duplicated().sum())
        invalid += int((~candidates["bottleneck_candidate_level"].astype(str).isin(valid_levels)).sum())
        invalid += int(candidates["bottleneck_candidate_reason"].astype(str).str.contains("FINAL_BOTTLENECK", case=False, na=False).sum())
        invalid += int((~_to_bool(candidates["advisory_only_flag"])).sum())
    if not review_queue.empty and review_required.issubset(review_queue.columns):
        invalid += int((~review_queue["issue_type"].astype(str).isin(valid_issue_types)).sum())
        invalid += int((~review_queue["issue_severity"].astype(str).isin(valid_severities)).sum())
        invalid += int(_to_bool(review_queue["auto_action_allowed"]).sum())
        invalid += int((~_to_bool(review_queue["advisory_only_flag"])).sum())
    checks.append(
        _result(
            "capacity_step4c_outputs_valid",
            "Step 4C capacity summary outputs valid",
            "FAIL" if invalid else "PASS",
            f"Step 4C missing/invalid values: {invalid}" if invalid else (
                f"Step 4C outputs valid; feasibility_rows={len(feasibility)}, "
                f"candidate_rows={len(candidates)}, review_rows={len(review_queue)}."
            ),
            invalid,
        )
    )


def _validate_labor_thresholds(frame: pd.DataFrame, checks: list[dict]) -> None:
    invalid = 0
    if frame.empty:
        invalid += 1
    required = {
        "labor_soft_warning_threshold_pct",
        "labor_hard_overload_threshold_pct",
        "labor_high_utilization_warning_flag",
        "labor_hard_overload_flag",
        "labor_capacity_status",
        "labor_utilization_pct",
    }
    missing = sorted(required.difference(frame.columns))
    invalid += len(missing)
    if not missing:
        utilization = pd.to_numeric(frame["labor_utilization_pct"], errors="coerce")
        soft = pd.to_numeric(frame["labor_soft_warning_threshold_pct"], errors="coerce")
        hard = pd.to_numeric(frame["labor_hard_overload_threshold_pct"], errors="coerce")
        warning_band = (utilization > LABOR_SOFT_WARNING_THRESHOLD_PCT) & (utilization <= LABOR_HARD_OVERLOAD_THRESHOLD_PCT)
        hard_band = utilization > LABOR_HARD_OVERLOAD_THRESHOLD_PCT
        invalid += int((soft != LABOR_SOFT_WARNING_THRESHOLD_PCT).sum())
        invalid += int((hard != LABOR_HARD_OVERLOAD_THRESHOLD_PCT).sum())
        invalid += int((_to_bool(frame["labor_high_utilization_warning_flag"]) != warning_band).sum())
        invalid += int((_to_bool(frame["labor_hard_overload_flag"]) != hard_band).sum())
        invalid += int((frame.loc[warning_band, "labor_capacity_status"].astype(str) != "HIGH_UTILIZATION_WARNING").sum())
        invalid += int((frame.loc[hard_band, "labor_capacity_status"].astype(str) != "OVERLOADED").sum())
    checks.append(
        _result(
            "capacity_labor_thresholds_valid",
            "labor capacity thresholds valid",
            "FAIL" if invalid else "PASS",
            f"Missing/invalid labor threshold rows: {invalid}" if invalid else "Labor capacity uses 80% warning and 95% hard-overload thresholds.",
            invalid,
        )
    )


def _validate_layer_output(
    name: str,
    frame: pd.DataFrame,
    required_columns: set[str],
    numeric_columns: list[str],
    status_column: str,
    checks: list[dict],
) -> None:
    valid_statuses = {"NO_LOAD", "FEASIBLE", "NEAR_CAPACITY", "HIGH_UTILIZATION_WARNING", "OVERLOADED", "NO_CAPACITY_RECORD", "REVIEW_REQUIRED"}
    missing = sorted(required_columns.difference(frame.columns))
    invalid = len(missing)
    if frame.empty:
        invalid += 1
    for column in numeric_columns:
        if column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            invalid += int(values.isna().sum() + (values < 0).sum())
        else:
            invalid += 1
    if status_column in frame.columns:
        invalid += int((~frame[status_column].astype(str).isin(valid_statuses)).sum())
    else:
        invalid += 1
    if "advisory_only_flag" in frame.columns:
        invalid += int((~_to_bool(frame["advisory_only_flag"])).sum())
    else:
        invalid += len(frame)
    checks.append(
        _result(
            f"capacity_{name}_load_valid",
            f"{name} capacity load valid",
            "FAIL" if invalid else "PASS",
            f"{name} capacity rows={len(frame)}; missing/invalid={invalid}" if invalid else f"{name} capacity load has {len(frame)} advisory rows.",
            invalid,
        )
    )


def _check_prior_validation(name: str, path: Path, checks: list[dict]) -> None:
    if not path.exists():
        checks.append(_result(f"capacity_{name}_exists", f"{name} exists", "FAIL", f"Missing validation output: {path}", 1))
        return
    frame = pd.read_csv(path)
    fail_count = int((frame.get("status", pd.Series(dtype=str)).astype(str).str.upper() == "FAIL").sum())
    checks.append(_result(f"capacity_{name}_has_no_fail", f"{name} has no FAIL rows", "FAIL" if fail_count else "PASS", f"{name} FAIL rows: {fail_count}" if fail_count else f"{name} has no FAIL rows.", fail_count))


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked_tokens = [
        "workstation_queue",
        "operation_queue",
        "queue_simulation",
        "confirmed_bottleneck",
        "bottleneck_ranking",
        "detailed_schedule",
        "finite_schedule",
        "shop_floor_schedule",
        "production_sequence",
        "scheduling_engine",
        "simulation",
        "production_order",
        "purchase_order",
        "released_order",
        "inventory_reservation",
    ]
    bad_files = []
    if OUTPUT_DIR.exists():
        for path in OUTPUT_DIR.glob("*"):
            if not path.is_file():
                continue
            lower = path.name.lower()
            if any(token in lower for token in blocked_tokens):
                bad_files.append(str(path))
    checks.append(_result("capacity_no_blocked_future_outputs", "capacity no blocked future outputs", "FAIL" if bad_files else "PASS", f"Blocked future/execution outputs found: {bad_files}" if bad_files else "No queue, bottleneck ranking, scheduling, simulation, or execution outputs found.", len(bad_files)))


def _load_csv(path: Path, name: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"capacity_{name}_exists", f"{name} exists", "FAIL", f"Missing file: {path}", 1))
        return None
    frame = pd.read_csv(path, keep_default_na=False)
    checks.append(_result(f"capacity_{name}_exists", f"{name} exists", "PASS", f"Loaded {path}", 0))
    return frame


def _check_required_columns(name: str, frame: pd.DataFrame, required: set[str], checks: list[dict]) -> None:
    missing = sorted(required.difference(frame.columns))
    checks.append(_result(f"capacity_{name}_required_columns", f"{name} required columns", "FAIL" if missing else "PASS", f"Missing columns: {missing}" if missing else "All required columns exist.", len(missing)))


def _check_not_empty(name: str, frame: pd.DataFrame, checks: list[dict]) -> None:
    checks.append(_result(f"capacity_{name}_not_empty", f"{name} not empty", "FAIL" if frame.empty else "PASS", "File has no rows." if frame.empty else f"File has {len(frame)} rows.", 1 if frame.empty else 0))


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
    capacity_load, detail, validation = build_workstation_capacity_load()
    fail_count = int((validation["status"] == "FAIL").sum())
    print(f"Phase 4 capacity load rows: {len(capacity_load)}")
    print(f"Phase 4 capacity operation detail rows: {len(detail)}")
    print(f"Phase 4 capacity validation FAIL rows: {fail_count}")
    print(f"Capacity load output written to: {OUTPUT_FILE}")
    print(f"Operation detail output written to: {DETAIL_OUTPUT_FILE}")
    print(f"Capacity validation output written to: {VALIDATION_OUTPUT_FILE}")
    if fail_count:
        raise SystemExit(1)
