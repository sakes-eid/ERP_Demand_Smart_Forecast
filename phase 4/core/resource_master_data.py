"""Validate Phase 4 production resource master data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PHASE4_DIR / "data"
OUTPUT_FILE = PHASE4_DIR / "outputs" / "phase4_resource_validation.csv"

WORKSTATIONS_FILE = DATA_DIR / "workstations.csv"
MACHINES_FILE = DATA_DIR / "machines.csv"
LABOR_FILE = DATA_DIR / "labor_resources.csv"
CALENDAR_FILE = DATA_DIR / "resource_calendar.csv"

REQUIRED_COLUMNS = {
    "workstations": {
        "workstation_id",
        "workstation_name",
        "workstation_type",
        "operation_family",
        "production_area",
        "supports_parallel_work_flag",
        "queue_supported_flag",
        "active_flag",
        "notes",
    },
    "machines": {
        "machine_id",
        "workstation_id",
        "machine_name",
        "machine_type",
        "automation_level",
        "machine_count",
        "available_hours_per_week",
        "setup_capable_flag",
        "hourly_machine_cost",
        "active_flag",
        "notes",
    },
    "labor_resources": {
        "labor_resource_id",
        "workstation_id",
        "skill_type",
        "role_name",
        "workers_available",
        "hours_per_worker_per_week",
        "hourly_wage",
        "break_minutes_per_shift",
        "can_support_parallel_work_flag",
        "active_flag",
        "notes",
    },
    "resource_calendar": {
        "calendar_id",
        "resource_scope",
        "resource_id",
        "weekday",
        "shift_start",
        "shift_end",
        "planned_break_minutes",
        "available_flag",
        "notes",
    },
}


def validate_resource_master_data(output_file: Path = OUTPUT_FILE) -> pd.DataFrame:
    """Validate Step 3A resource master data without calculating capacity."""
    checks: list[dict] = []
    frames = {
        "workstations": _load_csv(WORKSTATIONS_FILE, "workstations", checks),
        "machines": _load_csv(MACHINES_FILE, "machines", checks),
        "labor_resources": _load_csv(LABOR_FILE, "labor_resources", checks),
        "resource_calendar": _load_csv(CALENDAR_FILE, "resource_calendar", checks),
    }

    for name, frame in frames.items():
        if frame is None:
            continue
        _check_required_columns(name, frame, checks)
        _check_not_empty(name, frame, checks)

    workstations = frames.get("workstations")
    machines = frames.get("machines")
    labor = frames.get("labor_resources")
    calendar = frames.get("resource_calendar")

    if workstations is not None and REQUIRED_COLUMNS["workstations"].issubset(workstations.columns):
        _check_unique("workstation_ids_unique", "workstation_id", workstations, checks)
        _check_active_flags("workstations_active_flags", workstations, checks)

    if machines is not None and REQUIRED_COLUMNS["machines"].issubset(machines.columns):
        _check_unique("machine_ids_unique", "machine_id", machines, checks)
        _check_positive_numeric("machine_count_positive", machines, "machine_count", checks)
        _check_non_negative_numeric("machine_available_hours_non_negative", machines, "available_hours_per_week", checks)
        _check_non_negative_numeric("machine_hourly_cost_non_negative", machines, "hourly_machine_cost", checks)
        _check_active_flags("machines_active_flags", machines, checks)
        if workstations is not None and "workstation_id" in workstations.columns:
            _check_foreign_key(
                "machine_workstations_valid",
                machines,
                "workstation_id",
                set(workstations["workstation_id"].astype(str).str.strip()),
                checks,
            )

    if labor is not None and REQUIRED_COLUMNS["labor_resources"].issubset(labor.columns):
        _check_unique("labor_resource_ids_unique", "labor_resource_id", labor, checks)
        _check_non_negative_numeric("workers_available_non_negative", labor, "workers_available", checks)
        _check_non_negative_numeric("labor_hours_non_negative", labor, "hours_per_worker_per_week", checks)
        _check_non_negative_numeric("hourly_wage_non_negative", labor, "hourly_wage", checks)
        _check_non_negative_numeric("break_minutes_non_negative", labor, "break_minutes_per_shift", checks)
        _check_active_flags("labor_active_flags", labor, checks)
        if workstations is not None and "workstation_id" in workstations.columns:
            _check_foreign_key(
                "labor_workstations_valid",
                labor,
                "workstation_id",
                set(workstations["workstation_id"].astype(str).str.strip()),
                checks,
            )

    if calendar is not None and REQUIRED_COLUMNS["resource_calendar"].issubset(calendar.columns):
        _check_unique("calendar_ids_unique", "calendar_id", calendar, checks)
        _check_non_negative_numeric("calendar_break_minutes_non_negative", calendar, "planned_break_minutes", checks)
        _check_calendar_scope_values(calendar, checks)
        _check_calendar_weekdays(calendar, checks)
        if workstations is not None and machines is not None and labor is not None:
            _check_calendar_references(workstations, machines, labor, calendar, checks)

    result = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    output_file.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_file, index=False)
    return result


def _load_csv(path: Path, name: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"{name}_file_exists", f"{name} file exists", "FAIL", f"Missing file: {path}", 1))
        return None
    frame = pd.read_csv(path)
    checks.append(_result(f"{name}_file_exists", f"{name} file exists", "PASS", f"Loaded {path}", 0))
    return frame


def _check_required_columns(name: str, frame: pd.DataFrame, checks: list[dict]) -> None:
    missing = sorted(REQUIRED_COLUMNS[name].difference(frame.columns))
    status = "FAIL" if missing else "PASS"
    message = f"Missing required columns: {missing}" if missing else "All required columns exist."
    checks.append(_result(f"{name}_required_columns", f"{name} required columns", status, message, len(missing)))


def _check_not_empty(name: str, frame: pd.DataFrame, checks: list[dict]) -> None:
    status = "FAIL" if frame.empty else "PASS"
    message = "File has no rows." if frame.empty else f"File has {len(frame)} rows."
    checks.append(_result(f"{name}_not_empty", f"{name} not empty", status, message, 1 if frame.empty else 0))


def _check_unique(check_id: str, column: str, frame: pd.DataFrame, checks: list[dict]) -> None:
    duplicate_count = int(frame[column].astype(str).str.strip().duplicated().sum())
    status = "FAIL" if duplicate_count else "PASS"
    message = f"Duplicate {column} rows: {duplicate_count}" if duplicate_count else f"{column} values are unique."
    checks.append(_result(check_id, check_id.replace("_", " "), status, message, duplicate_count))


def _check_foreign_key(check_id: str, frame: pd.DataFrame, column: str, valid_values: set[str], checks: list[dict]) -> None:
    values = frame[column].astype(str).str.strip()
    invalid_count = int((~values.isin(valid_values)).sum())
    status = "FAIL" if invalid_count else "PASS"
    message = f"Invalid {column} references: {invalid_count}" if invalid_count else f"All {column} references are valid."
    checks.append(_result(check_id, check_id.replace("_", " "), status, message, invalid_count))


def _check_positive_numeric(check_id: str, frame: pd.DataFrame, column: str, checks: list[dict]) -> None:
    values = pd.to_numeric(frame[column], errors="coerce")
    invalid_count = int(values.isna().sum() + (values <= 0).sum())
    status = "FAIL" if invalid_count else "PASS"
    message = f"{column} must be positive; invalid rows: {invalid_count}" if invalid_count else f"{column} is positive."
    checks.append(_result(check_id, check_id.replace("_", " "), status, message, invalid_count))


def _check_non_negative_numeric(check_id: str, frame: pd.DataFrame, column: str, checks: list[dict]) -> None:
    values = pd.to_numeric(frame[column], errors="coerce")
    invalid_count = int(values.isna().sum() + (values < 0).sum())
    status = "FAIL" if invalid_count else "PASS"
    message = f"{column} must be non-negative; invalid rows: {invalid_count}" if invalid_count else f"{column} is non-negative."
    checks.append(_result(check_id, check_id.replace("_", " "), status, message, invalid_count))


def _check_active_flags(check_id: str, frame: pd.DataFrame, checks: list[dict]) -> None:
    inactive_count = int((~_to_bool(frame["active_flag"])).sum())
    status = "WARNING" if inactive_count else "PASS"
    message = f"Inactive rows found: {inactive_count}" if inactive_count else "All rows are active."
    checks.append(_result(check_id, check_id.replace("_", " "), status, message, inactive_count))


def _check_calendar_scope_values(calendar: pd.DataFrame, checks: list[dict]) -> None:
    valid = {"WORKSTATION", "MACHINE", "LABOR"}
    invalid_count = int((~calendar["resource_scope"].astype(str).str.strip().isin(valid)).sum())
    status = "FAIL" if invalid_count else "PASS"
    message = f"Invalid resource_scope rows: {invalid_count}" if invalid_count else "All resource_scope values are valid."
    checks.append(_result("calendar_scope_values_valid", "calendar scope values valid", status, message, invalid_count))


def _check_calendar_weekdays(calendar: pd.DataFrame, checks: list[dict]) -> None:
    required = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}
    present = set(calendar["weekday"].astype(str).str.strip())
    missing = sorted(required - present)
    status = "FAIL" if missing else "PASS"
    message = f"Missing weekdays: {missing}" if missing else "Calendar covers Monday through Friday."
    checks.append(_result("calendar_weekdays_covered", "calendar weekdays covered", status, message, len(missing)))


def _check_calendar_references(
    workstations: pd.DataFrame,
    machines: pd.DataFrame,
    labor: pd.DataFrame,
    calendar: pd.DataFrame,
    checks: list[dict],
) -> None:
    valid_by_scope = {
        "WORKSTATION": set(workstations["workstation_id"].astype(str).str.strip()),
        "MACHINE": set(machines["machine_id"].astype(str).str.strip()),
        "LABOR": set(labor["labor_resource_id"].astype(str).str.strip()),
    }
    invalid_count = 0
    for _, row in calendar.iterrows():
        scope = str(row["resource_scope"]).strip()
        resource_id = str(row["resource_id"]).strip()
        if resource_id not in valid_by_scope.get(scope, set()):
            invalid_count += 1
    status = "FAIL" if invalid_count else "PASS"
    message = f"Invalid calendar resource references: {invalid_count}" if invalid_count else "All calendar resource references are valid."
    checks.append(_result("calendar_resource_references_valid", "calendar resource references valid", status, message, invalid_count))


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
    validation = validate_resource_master_data()
    fail_count = int((validation["status"] == "FAIL").sum())
    print(f"Phase 4 resource validation rows: {len(validation)}")
    print(f"Phase 4 resource validation FAIL rows: {fail_count}")
    print(f"Output written to: {OUTPUT_FILE}")
    if fail_count:
        raise SystemExit(1)
