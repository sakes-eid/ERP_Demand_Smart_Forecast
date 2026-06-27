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
RESOURCE_CALENDAR_FILE = DATA_DIR / "resource_calendar.csv"
RESOURCE_VALIDATION_FILE = OUTPUT_DIR / "phase4_resource_validation.csv"
ROUTING_VALIDATION_FILE = OUTPUT_DIR / "phase4_routing_validation.csv"

OUTPUT_FILE = OUTPUT_DIR / "phase4_capacity_load_by_workstation.csv"
DETAIL_OUTPUT_FILE = OUTPUT_DIR / "phase4_capacity_operation_load_detail.csv"
VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_capacity_validation.csv"

CAPACITY_PLANNING_BASIS = "MPS_ROUTING_WORKSTATION_LOAD"

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
}


def build_workstation_capacity_load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build operation detail, workstation-period load, and validation outputs."""
    checks: list[dict] = []
    frames = {
        "mps": _load_csv(MPS_FILE, "mps", checks),
        "product_routings": _load_csv(PRODUCT_ROUTINGS_FILE, "product_routings", checks),
        "workstations": _load_csv(WORKSTATIONS_FILE, "workstations", checks),
        "resource_calendar": _load_csv(RESOURCE_CALENDAR_FILE, "resource_calendar", checks),
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
    if all(frames[name] is not None and REQUIRED_COLUMNS[name].issubset(frames[name].columns) for name in frames):
        mps = frames["mps"]
        routings = frames["product_routings"]
        workstations = frames["workstations"]
        calendar = frames["resource_calendar"]
        detail = _build_operation_detail(mps, routings, checks)
        load = _build_workstation_load(detail, mps, workstations, calendar, checks)
        _validate_capacity_outputs(load, detail, checks)

    _check_no_blocked_outputs(checks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL_OUTPUT_FILE, index=False)
    load.to_csv(OUTPUT_FILE, index=False)
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


def _validate_capacity_outputs(load: pd.DataFrame, detail: pd.DataFrame, checks: list[dict]) -> None:
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
    checks.append(_result("capacity_operation_detail_exists", "capacity operation detail exists", "FAIL" if detail.empty else "PASS", "Operation detail output has no rows." if detail.empty else f"Operation detail output has {len(detail)} rows.", 1 if detail.empty else 0))


def _check_prior_validation(name: str, path: Path, checks: list[dict]) -> None:
    if not path.exists():
        checks.append(_result(f"capacity_{name}_exists", f"{name} exists", "FAIL", f"Missing validation output: {path}", 1))
        return
    frame = pd.read_csv(path)
    fail_count = int((frame.get("status", pd.Series(dtype=str)).astype(str).str.upper() == "FAIL").sum())
    checks.append(_result(f"capacity_{name}_has_no_fail", f"{name} has no FAIL rows", "FAIL" if fail_count else "PASS", f"{name} FAIL rows: {fail_count}" if fail_count else f"{name} has no FAIL rows.", fail_count))


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked_tokens = [
        "machine_capacity",
        "labor_capacity",
        "queue",
        "bottleneck",
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
    checks.append(_result("capacity_no_blocked_future_outputs", "capacity no blocked future outputs", "FAIL" if bad_files else "PASS", f"Blocked future/execution outputs found: {bad_files}" if bad_files else "No machine/labor capacity, queue, bottleneck, scheduling, simulation, or execution outputs found.", len(bad_files)))


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
