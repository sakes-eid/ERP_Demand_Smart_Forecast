"""Validate Phase 4 initialization readiness without enabling execution."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PHASE4_DIR.parent
OUTPUT_DIR = PHASE4_DIR / "outputs"

BIKE_SKUS = {"SKU-BIKE-ROAD-001", "SKU-BIKE-MT-001"}
PHASE4_OUTPUTS = {
    "master_production_schedule": PHASE4_DIR / "outputs" / "phase4_master_production_schedule.csv",
    "bom_component_requirements": PHASE4_DIR / "outputs" / "phase4_bom_component_requirements.csv",
    "mrp_net_component_requirements": PHASE4_DIR / "outputs" / "phase4_mrp_net_component_requirements.csv",
    "mrp_component_period_summary": PHASE4_DIR / "outputs" / "phase4_mrp_component_period_summary.csv",
    "mrp_pegging_detail": PHASE4_DIR / "outputs" / "phase4_mrp_pegging_detail.csv",
    "component_inventory_check": PROJECT_ROOT / "phase 3" / "outputs" / "phase4_component_inventory_check.csv",
    "component_supplier_check": PROJECT_ROOT / "phase 2" / "outputs" / "phase4_component_supplier_check.csv",
}
EXECUTION_FILE_TOKENS = [
    "production_order",
    "purchase_order",
    "released_order",
    "inventory_reservation",
]
RESOURCE_DATA_FILES = {
    "workstations": PHASE4_DIR / "data" / "workstations.csv",
    "machines": PHASE4_DIR / "data" / "machines.csv",
    "labor_resources": PHASE4_DIR / "data" / "labor_resources.csv",
    "resource_calendar": PHASE4_DIR / "data" / "resource_calendar.csv",
}
RESOURCE_VALIDATION_FILE = PHASE4_DIR / "outputs" / "phase4_resource_validation.csv"
ROUTING_DATA_FILES = {
    "product_routings": PHASE4_DIR / "data" / "product_routings.csv",
    "routing_parallel_groups": PHASE4_DIR / "data" / "routing_parallel_groups.csv",
    "routing_operation_resources": PHASE4_DIR / "data" / "routing_operation_resources.csv",
}
ROUTING_VALIDATION_FILE = PHASE4_DIR / "outputs" / "phase4_routing_validation.csv"
ROUTING_FLOW_SUMMARY_FILE = PHASE4_DIR / "outputs" / "phase4_routing_flow_summary.csv"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    checks = []

    checks.append(
        _check_existing_validation_summary(
            "phase1",
            PROJECT_ROOT / "phase 1" / "outputs" / "phase1_demand_context_validation_summary.csv",
        )
    )
    checks.append(
        _check_existing_validation_summary(
            "phase2",
            PROJECT_ROOT / "phase 2" / "outputs" / "phase2_procurement_validation_summary.csv",
        )
    )
    checks.append(
        _check_existing_validation_summary(
            "phase3",
            PROJECT_ROOT / "phase 3" / "outputs" / "phase3_validation_summary.csv",
        )
    )
    checks.append(_check_integrated_validation_json(PROJECT_ROOT / "shared" / "validation" / "integrated_validation_evidence.json"))
    checks.append(_check_bike_forecasts())
    checks.append(_check_bom())
    checks.append(_check_mps_output())
    checks.append(_check_bom_explosion())
    checks.append(_check_mrp_net_requirements())
    checks.append(_check_mrp_component_period_summary())
    checks.append(_check_mrp_pegging_detail())
    checks.append(_check_resource_master_data())
    checks.append(_check_routing_master_data())
    checks.append(_check_phase3_inventory_check())
    checks.append(_check_phase2_supplier_check())
    checks.append(_check_phase4_run_id_consistency())
    checks.append(_check_phase4_advisory_only())
    checks.append(_check_existing_outputs())
    checks.append(_check_safety_flags())
    checks.append(_check_no_routing_or_capacity_outputs())
    checks.append(_check_no_execution_outputs())

    fail_count = sum(check["status"] == "FAIL" for check in checks)
    warning_count = sum(check["status"] == "WARNING" for check in checks)
    overall_status = "FAIL" if fail_count else "PASS"
    evidence = {
        "validation_name": "phase4_initialization_validation",
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "overall_status": overall_status,
        "fail_count": fail_count,
        "warning_count": warning_count,
        "checks": checks,
    }
    json_path = OUTPUT_DIR / "phase4_initialization_validation.json"
    report_path = OUTPUT_DIR / "phase4_initialization_validation_report.txt"
    json_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    report_path.write_text(_format_report(evidence), encoding="utf-8")

    print(f"Phase 4 initialization validation status: {overall_status}")
    print(f"JSON evidence: {json_path}")
    print(f"Report: {report_path}")
    if overall_status == "FAIL":
        raise SystemExit(1)


def _check_existing_validation_summary(name: str, path: Path) -> dict:
    if not path.exists():
        return _result(name, "FAIL", f"Required {name} validation evidence is missing: {path}")
    summary = pd.read_csv(path)
    values = _status_values(summary)
    fail_count = sum(value == "FAIL" for value in values)
    warning_count = sum(value in {"WARNING", "WARN", "SKIPPED"} for value in values)
    if fail_count:
        return _result(name, "FAIL", f"FAIL = {fail_count}; required evidence exists but contains failure values.")
    if warning_count:
        return _result(name, "WARNING", f"WARNING = {warning_count}; evidence exists and no fail values were found.")
    return _result(name, "PASS", "Exists and no fail values were found.")


def _check_integrated_validation_json(path: Path) -> dict:
    if not path.exists():
        return _result("integrated", "FAIL", f"Required integrated validation evidence is missing: {path}")
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _result("integrated", "FAIL", f"Integrated validation evidence is not valid JSON: {exc}")

    overall = evidence.get("overall_result", {})
    fail_count = int(overall.get("fail_count", -1))
    status = str(overall.get("status", "UNKNOWN")).upper()
    expected_false = {
        "auto_apply_allowed": overall.get("auto_apply_allowed"),
        "purchase_order_creation_allowed": overall.get("purchase_order_creation_allowed"),
        "safe_for_execution_downstream_use": overall.get("safe_for_execution_downstream_use"),
    }
    bad_false_fields = [key for key, value in expected_false.items() if bool(value) is not False]
    if fail_count != 0:
        return _result("integrated", "FAIL", f"Integrated fail_count must be 0; found {fail_count}.")
    if bad_false_fields:
        return _result("integrated", "FAIL", f"Integrated safety fields must be false: {bad_false_fields}")
    if status == "FAIL":
        return _result("integrated", "FAIL", "Integrated status is FAIL.")
    if status == "WARNING":
        return _result("integrated", "WARNING", "Integrated status is WARNING with fail_count 0 and execution safety disabled.")
    return _result("integrated", "PASS", "Integrated evidence parsed; fail_count 0 and execution safety disabled.")


def _status_values(summary: pd.DataFrame) -> list[str]:
    status_columns = [col for col in summary.columns if col.lower() in {"status", "result", "validation_status"}]
    if not status_columns:
        status_columns = [col for col in summary.columns if "status" in col.lower() or "result" in col.lower()]
    values = []
    for column in status_columns:
        values.extend(summary[column].dropna().astype(str).str.upper().tolist())
    return values


def _check_bike_forecasts() -> dict:
    path = PROJECT_ROOT / "phase 1" / "outputs" / "future_forecast_results.csv"
    if not path.exists():
        return _result("bike_forecasts", "FAIL", "Phase 1 future forecast output is missing.")
    forecast = pd.read_csv(path)
    present = set(forecast.get("sku_id", pd.Series(dtype=str)).astype(str)) & BIKE_SKUS
    missing = sorted(BIKE_SKUS - present)
    if missing:
        return _result("bike_forecasts", "FAIL", f"Missing bike SKUs in Phase 1 forecast output: {missing}")
    return _result("bike_forecasts", "PASS", "Road Bike and Mountain Bike appear in Phase 1 future forecasts.")


def _check_bom() -> dict:
    path = PHASE4_DIR / "data" / "phase4_bom.csv"
    required = {
        "finished_sku",
        "finished_product_name",
        "component_sku",
        "component_name",
        "quantity_per_finished_unit",
        "component_type",
        "critical_component_flag",
        "phase4_active_flag",
    }
    if not path.exists():
        return _result("bom_master", "FAIL", "Phase 4 BOM file is missing.")
    bom = pd.read_csv(path)
    missing_columns = sorted(required.difference(bom.columns))
    if missing_columns:
        return _result("bom_master", "FAIL", f"BOM missing columns: {missing_columns}")
    if bom.empty or not BIKE_SKUS.issubset(set(bom["finished_sku"].astype(str))):
        return _result("bom_master", "FAIL", "BOM has no valid rows for both finished bike SKUs.")
    invalid_qty = pd.to_numeric(bom["quantity_per_finished_unit"], errors="coerce").fillna(0) <= 0
    if invalid_qty.any():
        return _result("bom_master", "FAIL", "BOM contains non-positive component quantities.")
    return _result("bom_master", "PASS", f"BOM exists with {len(bom)} valid seed rows.")


def _check_mps_output() -> dict:
    path = PHASE4_OUTPUTS["master_production_schedule"]
    if not path.exists():
        return _result("mps_step1", "FAIL", "MPS output is missing.")
    mps = pd.read_csv(path)
    if mps.empty:
        return _result("mps_step1", "FAIL", "MPS output has no rows.")
    required = {
        "planning_run_id",
        "period_start",
        "period_end",
        "finished_sku",
        "forecast_demand_qty",
        "period_sequence",
        "period_starting_inventory_qty",
        "net_finished_goods_requirement_qty",
        "planned_production_qty",
        "projected_ending_inventory_qty",
        "projected_shortage_qty",
        "rolling_balance_applied_flag",
        "mps_planning_basis",
        "mps_status",
        "advisory_only_flag",
    }
    missing_columns = sorted(required.difference(mps.columns))
    if missing_columns:
        return _result("mps_step1", "FAIL", f"MPS output missing columns: {missing_columns}")
    present = set(mps["finished_sku"].astype(str)) & BIKE_SKUS
    missing_skus = sorted(BIKE_SKUS - present)
    if missing_skus:
        return _result("mps_step1", "FAIL", f"MPS missing finished bike SKUs: {missing_skus}")
    period_start = pd.to_datetime(mps["period_start"], errors="coerce")
    period_end = pd.to_datetime(mps["period_end"], errors="coerce")
    if period_start.isna().any() or period_end.isna().any():
        return _result("mps_step1", "FAIL", "MPS period_start/period_end contains invalid dates.")
    invalid_periods = ((period_end - period_start).dt.days != 6).sum()
    if invalid_periods:
        return _result("mps_step1", "FAIL", f"MPS contains {int(invalid_periods)} non-weekly planning rows.")
    if not _valid_period_sequences(mps):
        return _result("mps_step1", "FAIL", "MPS period_sequence must be consecutive per finished_sku.")
    numeric_checks = {
        "period_starting_inventory_qty": False,
        "net_finished_goods_requirement_qty": True,
        "planned_production_qty": True,
        "projected_ending_inventory_qty": False,
        "projected_shortage_qty": True,
    }
    for column, require_non_negative in numeric_checks.items():
        values = pd.to_numeric(mps[column], errors="coerce")
        if values.isna().any():
            return _result("mps_step1", "FAIL", f"MPS {column} must be numeric.")
        if require_non_negative and (values < 0).any():
            return _result("mps_step1", "FAIL", f"MPS {column} must be non-negative.")
    if (pd.to_numeric(mps["projected_ending_inventory_qty"], errors="coerce") < 0).any():
        return _result("mps_step1", "FAIL", "MPS projected ending inventory should not be negative in Step 1B.")
    if not _all_true(mps, "rolling_balance_applied_flag"):
        return _result("mps_step1", "FAIL", "MPS rolling_balance_applied_flag must be true for all rows.")
    basis_values = set(mps["mps_planning_basis"].dropna().astype(str).str.strip())
    if basis_values != {"ROLLING_PROJECTED_AVAILABLE_BALANCE"}:
        return _result("mps_step1", "FAIL", f"Unexpected MPS planning basis values: {sorted(basis_values)}")
    if not _all_true(mps, "advisory_only_flag"):
        return _result("mps_step1", "FAIL", "MPS contains non-advisory rows.")
    return _result(
        "mps_step1",
        "PASS",
        f"MPS Step 1B rolling balance output contains {len(mps)} weekly advisory rows for Road Bike and Mountain Bike.",
    )


def _check_bom_explosion() -> dict:
    path = PHASE4_OUTPUTS["bom_component_requirements"]
    if not path.exists():
        return _result("bom_explosion", "FAIL", "BOM explosion output is missing.")
    requirements = pd.read_csv(path)
    if requirements.empty:
        return _result("bom_explosion", "FAIL", "BOM explosion output has no rows.")
    basis_values = set()
    if "bom_explosion_basis" in requirements.columns:
        basis_values = set(requirements["bom_explosion_basis"].dropna().astype(str).str.strip())
    mps_path = PHASE4_OUTPUTS["master_production_schedule"]
    if mps_path.exists():
        mps = pd.read_csv(mps_path)
        if not mps.empty and "MPS_PLANNED_PRODUCTION" not in basis_values:
            return _result(
                "bom_explosion",
                "FAIL",
                f"MPS exists but BOM explosion was not based on MPS planned production: {sorted(basis_values)}",
            )
    basis_message = f"; basis = {sorted(basis_values)}" if basis_values else ""
    return _result("bom_explosion", "PASS", f"BOM explosion produced {len(requirements)} requirement rows{basis_message}.")


def _check_mrp_net_requirements() -> dict:
    path = PHASE4_OUTPUTS["mrp_net_component_requirements"]
    if not path.exists():
        return _result("mrp_step2", "FAIL", "MRP net component requirements output is missing.")
    mrp = pd.read_csv(path)
    if mrp.empty:
        return _result("mrp_step2", "FAIL", "MRP net component requirements output has no rows.")
    required = {
        "planning_run_id",
        "period_start",
        "period_end",
        "component_sku",
        "gross_component_requirement_qty",
        "component_available_qty",
        "period_starting_component_inventory_qty",
        "net_component_requirement_qty",
        "projected_component_ending_inventory_qty",
        "projected_component_shortage_qty",
        "mrp_recommendation_status",
        "advisory_only_flag",
    }
    missing = sorted(required.difference(mrp.columns))
    if missing:
        return _result("mrp_step2", "FAIL", f"MRP output missing columns: {missing}")
    numeric_non_negative = [
        "net_component_requirement_qty",
        "projected_component_shortage_qty",
    ]
    for column in numeric_non_negative:
        values = pd.to_numeric(mrp[column], errors="coerce")
        if values.isna().any() or (values < 0).any():
            return _result("mrp_step2", "FAIL", f"MRP {column} must be numeric and non-negative.")
    ending = pd.to_numeric(mrp["projected_component_ending_inventory_qty"], errors="coerce")
    if ending.isna().any() or (ending < 0).any():
        return _result("mrp_step2", "FAIL", "MRP projected component ending inventory must be numeric and non-negative.")
    if not _all_true(mrp, "advisory_only_flag"):
        return _result("mrp_step2", "FAIL", "MRP output contains non-advisory rows.")
    basis_values = set(mrp.get("mrp_planning_basis", pd.Series(dtype=str)).dropna().astype(str).str.strip())
    if basis_values != {"MPS_BOM_COMPONENT_NETTING"}:
        return _result("mrp_step2", "FAIL", f"Unexpected MRP planning basis values: {sorted(basis_values)}")
    return _result("mrp_step2", "PASS", f"MRP Step 2 netted {len(mrp)} component requirement rows.")


def _check_mrp_component_period_summary() -> dict:
    path = PHASE4_OUTPUTS["mrp_component_period_summary"]
    if not path.exists():
        return _result("mrp_step2b_summary", "FAIL", "MRP component-period summary output is missing.")
    summary = pd.read_csv(path)
    if summary.empty:
        return _result("mrp_step2b_summary", "FAIL", "MRP component-period summary output has no rows.")
    required = {
        "planning_run_id",
        "period_start",
        "period_end",
        "component_sku",
        "gross_component_requirement_qty",
        "component_available_qty",
        "period_starting_component_inventory_qty",
        "net_component_requirement_qty",
        "projected_component_ending_inventory_qty",
        "projected_component_shortage_qty",
        "mrp_recommendation_status",
        "mrp_planning_basis",
        "component_period_summary_flag",
        "advisory_only_flag",
    }
    missing = sorted(required.difference(summary.columns))
    if missing:
        return _result("mrp_step2b_summary", "FAIL", f"Component-period summary missing columns: {missing}")
    duplicate_count = int(summary.duplicated(["planning_run_id", "period_start", "period_end", "component_sku"]).sum())
    if duplicate_count:
        return _result("mrp_step2b_summary", "FAIL", f"Component-period summary has duplicate component-period rows: {duplicate_count}")
    for column in ["net_component_requirement_qty", "projected_component_shortage_qty", "projected_component_ending_inventory_qty"]:
        values = pd.to_numeric(summary[column], errors="coerce")
        if values.isna().any() or (values < 0).any():
            return _result("mrp_step2b_summary", "FAIL", f"Component-period summary {column} must be numeric and non-negative.")
    if not _all_true(summary, "component_period_summary_flag"):
        return _result("mrp_step2b_summary", "FAIL", "component_period_summary_flag must be true for all summary rows.")
    basis_values = set(summary["mrp_planning_basis"].dropna().astype(str).str.strip())
    if basis_values != {"MPS_BOM_COMPONENT_NETTING_COMPONENT_PERIOD"}:
        return _result("mrp_step2b_summary", "FAIL", f"Unexpected component-period MRP basis values: {sorted(basis_values)}")
    if not _all_true(summary, "advisory_only_flag"):
        return _result("mrp_step2b_summary", "FAIL", "Component-period summary contains non-advisory rows.")
    return _result("mrp_step2b_summary", "PASS", f"Component-period MRP summary contains {len(summary)} advisory rows.")


def _check_mrp_pegging_detail() -> dict:
    path = PHASE4_OUTPUTS["mrp_pegging_detail"]
    if not path.exists():
        return _result("mrp_step2b_pegging", "FAIL", "MRP pegging detail output is missing.")
    pegging = pd.read_csv(path)
    if pegging.empty:
        return _result("mrp_step2b_pegging", "FAIL", "MRP pegging detail output has no rows.")
    required = {
        "planning_run_id",
        "period_start",
        "period_end",
        "component_sku",
        "finished_sku",
        "pegged_gross_component_requirement_qty",
        "component_period_gross_requirement_qty",
        "pegged_requirement_share_pct",
        "component_period_net_requirement_qty",
        "pegged_net_requirement_qty",
        "pegging_type",
        "advisory_only_flag",
    }
    missing = sorted(required.difference(pegging.columns))
    if missing:
        return _result("mrp_step2b_pegging", "FAIL", f"Pegging detail missing columns: {missing}")
    shares = pd.to_numeric(pegging["pegged_requirement_share_pct"], errors="coerce")
    if shares.isna().any() or (shares < -0.000001).any() or (shares > 1.000001).any():
        return _result("mrp_step2b_pegging", "FAIL", "Pegging shares must be between 0 and 1.")
    pegged_net = pd.to_numeric(pegging["pegged_net_requirement_qty"], errors="coerce")
    if pegged_net.isna().any() or (pegged_net < -0.000001).any():
        return _result("mrp_step2b_pegging", "FAIL", "Pegged net requirement quantities must be non-negative.")
    for column in [
        "pegged_gross_component_requirement_qty",
        "component_period_gross_requirement_qty",
        "component_period_net_requirement_qty",
    ]:
        pegging[column] = pd.to_numeric(pegging[column], errors="coerce")
        if pegging[column].isna().any():
            return _result("mrp_step2b_pegging", "FAIL", f"Pegging {column} must be numeric.")
    pegging["pegged_requirement_share_pct"] = shares
    pegging["pegged_net_requirement_qty"] = pegged_net
    if not _all_true(pegging, "advisory_only_flag"):
        return _result("mrp_step2b_pegging", "FAIL", "Pegging detail contains non-advisory rows.")
    if set(pegging["pegging_type"].dropna().astype(str).str.strip()) != {"SOFT_PEGGING_FINISHED_GOODS_DEMAND"}:
        return _result("mrp_step2b_pegging", "FAIL", "Unexpected pegging_type values.")

    keys = ["planning_run_id", "period_start", "period_end", "component_sku"]
    grouped = pegging.groupby(keys, as_index=False).agg(
        share_sum=("pegged_requirement_share_pct", "sum"),
        pegged_gross_sum=("pegged_gross_component_requirement_qty", "sum"),
        pegged_net_sum=("pegged_net_requirement_qty", "sum"),
        gross=("component_period_gross_requirement_qty", "max"),
        net=("component_period_net_requirement_qty", "max"),
    )
    nonzero_gross = grouped["gross"] > 0
    if ((grouped.loc[nonzero_gross, "share_sum"] - 1).abs() > 0.0001).any():
        return _result("mrp_step2b_pegging", "FAIL", "Pegging shares do not sum to 1 for all nonzero component-period groups.")
    if ((grouped["pegged_gross_sum"] - grouped["gross"]).abs() > 0.01).any():
        return _result("mrp_step2b_pegging", "FAIL", "Pegged gross requirements do not sum back to component-period gross requirements.")
    if ((grouped["pegged_net_sum"] - grouped["net"]).abs() > 0.05).any():
        return _result("mrp_step2b_pegging", "FAIL", "Pegged net requirements do not sum back to component-period net requirements.")
    return _result("mrp_step2b_pegging", "PASS", f"MRP pegging detail contains {len(pegging)} advisory rows with valid pegging sums.")


def _check_resource_master_data() -> dict:
    missing_files = [name for name, path in RESOURCE_DATA_FILES.items() if not path.exists()]
    if missing_files:
        return _result("resource_master_data", "FAIL", f"Missing resource master data files: {missing_files}")
    frames = {name: pd.read_csv(path) for name, path in RESOURCE_DATA_FILES.items()}
    empty_files = [name for name, frame in frames.items() if frame.empty]
    if empty_files:
        return _result("resource_master_data", "FAIL", f"Resource master data files are empty: {empty_files}")
    if not RESOURCE_VALIDATION_FILE.exists():
        return _result("resource_master_data", "FAIL", "Resource validation output is missing.")
    validation = pd.read_csv(RESOURCE_VALIDATION_FILE)
    if validation.empty:
        return _result("resource_master_data", "FAIL", "Resource validation output has no rows.")
    if "status" not in validation.columns:
        return _result("resource_master_data", "FAIL", "Resource validation output has no status column.")
    fail_count = int((validation["status"].astype(str).str.upper() == "FAIL").sum())
    if fail_count:
        return _result("resource_master_data", "FAIL", f"Resource validation contains FAIL rows: {fail_count}")
    required_unique = [
        ("workstations", "workstation_id"),
        ("machines", "machine_id"),
        ("labor_resources", "labor_resource_id"),
    ]
    for name, column in required_unique:
        if column not in frames[name].columns:
            return _result("resource_master_data", "FAIL", f"{name} missing {column}")
        duplicate_count = int(frames[name][column].astype(str).str.strip().duplicated().sum())
        if duplicate_count:
            return _result("resource_master_data", "FAIL", f"{name} has duplicate {column} values: {duplicate_count}")
    workstation_ids = set(frames["workstations"]["workstation_id"].astype(str).str.strip())
    for name in ["machines", "labor_resources"]:
        invalid_refs = int((~frames[name]["workstation_id"].astype(str).str.strip().isin(workstation_ids)).sum())
        if invalid_refs:
            return _result("resource_master_data", "FAIL", f"{name} contains invalid workstation references: {invalid_refs}")
    invalid_calendar_refs = _resource_calendar_invalid_reference_count(frames)
    if invalid_calendar_refs:
        return _result("resource_master_data", "FAIL", f"Resource calendar contains invalid resource references: {invalid_calendar_refs}")
    numeric_checks = [
        ("machines", "machine_count", True),
        ("machines", "available_hours_per_week", False),
        ("machines", "hourly_machine_cost", False),
        ("labor_resources", "workers_available", False),
        ("labor_resources", "hours_per_worker_per_week", False),
        ("labor_resources", "hourly_wage", False),
        ("labor_resources", "break_minutes_per_shift", False),
        ("resource_calendar", "planned_break_minutes", False),
    ]
    for name, column, positive in numeric_checks:
        values = pd.to_numeric(frames[name][column], errors="coerce")
        invalid = values.isna() | (values <= 0 if positive else values < 0)
        if bool(invalid.any()):
            return _result("resource_master_data", "FAIL", f"{name}.{column} has invalid numeric rows: {int(invalid.sum())}")
    return _result(
        "resource_master_data",
        "PASS",
        (
            "Step 3A resource master data valid; "
            f"workstations={len(frames['workstations'])}, machines={len(frames['machines'])}, "
            f"labor_resources={len(frames['labor_resources'])}, calendar_rows={len(frames['resource_calendar'])}."
        ),
    )


def _check_routing_master_data() -> dict:
    missing_files = [name for name, path in ROUTING_DATA_FILES.items() if not path.exists()]
    if missing_files:
        return _result("routing_master_data", "FAIL", f"Missing routing master data files: {missing_files}")
    frames = {name: pd.read_csv(path, keep_default_na=False) for name, path in ROUTING_DATA_FILES.items()}
    empty_files = [name for name, frame in frames.items() if frame.empty]
    if empty_files:
        return _result("routing_master_data", "FAIL", f"Routing master data files are empty: {empty_files}")
    if not ROUTING_VALIDATION_FILE.exists():
        return _result("routing_master_data", "FAIL", "Routing validation output is missing.")
    validation = pd.read_csv(ROUTING_VALIDATION_FILE)
    if validation.empty:
        return _result("routing_master_data", "FAIL", "Routing validation output has no rows.")
    if "status" not in validation.columns:
        return _result("routing_master_data", "FAIL", "Routing validation output has no status column.")
    fail_count = int((validation["status"].astype(str).str.upper() == "FAIL").sum())
    if fail_count:
        return _result("routing_master_data", "FAIL", f"Routing validation contains FAIL rows: {fail_count}")

    routings = frames["product_routings"]
    groups = frames["routing_parallel_groups"]
    resources = frames["routing_operation_resources"]
    active = routings[_to_bool(routings["active_flag"])]
    active_skus = set(active["finished_sku"].astype(str).str.strip())
    missing_skus = sorted(BIKE_SKUS - active_skus)
    if missing_skus:
        return _result("routing_master_data", "FAIL", f"Missing active routings for finished SKUs: {missing_skus}")
    mps_path = PHASE4_OUTPUTS["master_production_schedule"]
    if mps_path.exists():
        mps = pd.read_csv(mps_path)
        mps_skus = set(mps.get("finished_sku", pd.Series(dtype=str)).dropna().astype(str).str.strip())
        missing_mps_skus = sorted(mps_skus - active_skus)
        if missing_mps_skus:
            return _result("routing_master_data", "FAIL", f"MPS finished SKUs missing active routing: {missing_mps_skus}")

    workstations = pd.read_csv(RESOURCE_DATA_FILES["workstations"])
    machines = pd.read_csv(RESOURCE_DATA_FILES["machines"])
    labor = pd.read_csv(RESOURCE_DATA_FILES["labor_resources"])
    workstation_ids = set(workstations["workstation_id"].astype(str).str.strip())
    invalid_routing_ws = int((~routings["workstation_id"].astype(str).str.strip().isin(workstation_ids)).sum())
    invalid_resource_ws = int((~resources["workstation_id"].astype(str).str.strip().isin(workstation_ids)).sum())
    if invalid_routing_ws or invalid_resource_ws:
        return _result("routing_master_data", "FAIL", f"Invalid routing/resource workstation references: {invalid_routing_ws + invalid_resource_ws}")
    machine_types = set(machines["machine_type"].astype(str).str.strip())
    invalid_machine_types = int((~resources["required_machine_type"].astype(str).str.strip().isin(machine_types)).sum())
    if invalid_machine_types:
        return _result("routing_master_data", "FAIL", f"Invalid routing machine type references: {invalid_machine_types}")
    labor_skills = set(labor["skill_type"].astype(str).str.strip())
    invalid_labor_skills = int((~resources["required_labor_skill"].astype(str).str.strip().isin(labor_skills)).sum())
    if invalid_labor_skills:
        return _result("routing_master_data", "FAIL", f"Invalid routing labor skill references: {invalid_labor_skills}")

    operation_ids = set(routings["operation_id"].astype(str).str.strip())
    invalid_group_refs = 0
    for _, row in groups.iterrows():
        refs = [row["fork_after_operation_id"], row["join_before_operation_id"]]
        refs.extend(_split_ids(row["member_operation_ids"]))
        invalid_group_refs += sum(1 for ref in refs if str(ref).strip() not in operation_ids)
    if invalid_group_refs:
        return _result("routing_master_data", "FAIL", f"Parallel group invalid operation references: {invalid_group_refs}")

    if _routing_has_cycle(routings):
        return _result("routing_master_data", "FAIL", "Circular routing dependency found.")
    road_groups = groups[groups["finished_sku"].astype(str).str.strip() == "SKU-BIKE-ROAD-001"]
    mt_groups = groups[groups["finished_sku"].astype(str).str.strip() == "SKU-BIKE-MT-001"]
    if road_groups.empty or mt_groups.empty:
        return _result("routing_master_data", "FAIL", "Road Bike and Mountain Bike must each have at least one parallel group.")
    road_ws = set(routings.loc[routings["finished_sku"].astype(str).str.strip() == "SKU-BIKE-ROAD-001", "workstation_id"].astype(str).str.strip())
    mt_ws = set(routings.loc[routings["finished_sku"].astype(str).str.strip() == "SKU-BIKE-MT-001", "workstation_id"].astype(str).str.strip())
    if "WS-FORK-SUSP" not in mt_ws:
        return _result("routing_master_data", "FAIL", "Mountain Bike routing does not use WS-FORK-SUSP.")
    if "WS-FORK-SUSP" in road_ws:
        return _result("routing_master_data", "FAIL", "Road Bike routing incorrectly uses WS-FORK-SUSP.")
    if not ROUTING_FLOW_SUMMARY_FILE.exists():
        return _result("routing_master_data", "FAIL", "Routing flow summary output is missing.")
    flow = pd.read_csv(ROUTING_FLOW_SUMMARY_FILE)
    if flow.empty:
        return _result("routing_master_data", "FAIL", "Routing flow summary output has no rows.")
    if "advisory_only_flag" in flow.columns and not _all_true(flow, "advisory_only_flag"):
        return _result("routing_master_data", "FAIL", "Routing flow summary contains non-advisory rows.")
    return _result(
        "routing_master_data",
        "PASS",
        (
            "Step 3B routing master data valid; "
            f"routing_rows={len(routings)}, parallel_groups={len(groups)}, operation_resource_rows={len(resources)}."
        ),
    )


def _check_phase3_inventory_check() -> dict:
    path = PHASE4_OUTPUTS["component_inventory_check"]
    if not path.exists():
        return _result("phase3_component_inventory", "FAIL", "Phase 3 component inventory check output is missing.")
    check = pd.read_csv(path)
    if check.empty:
        return _result("phase3_component_inventory", "FAIL", "Phase 3 component inventory check has no rows.")
    summary_path = PHASE4_OUTPUTS["mrp_component_period_summary"]
    mrp_path = PHASE4_OUTPUTS["mrp_net_component_requirements"]
    if summary_path.exists() and not pd.read_csv(summary_path).empty:
        if "component_requirement_basis" not in check.columns:
            return _result("phase3_component_inventory", "FAIL", "Phase 3 output missing component_requirement_basis while component-period summary exists.")
        basis_values = set(check["component_requirement_basis"].dropna().astype(str).str.strip())
        if basis_values != {"MRP_COMPONENT_PERIOD_SUMMARY"}:
            return _result("phase3_component_inventory", "FAIL", f"Phase 3 did not use component-period MRP summary: {sorted(basis_values)}")
        if "component_period_summary_used_flag" not in check.columns or not _all_true(check, "component_period_summary_used_flag"):
            return _result("phase3_component_inventory", "FAIL", "Phase 3 did not flag component-period summary usage.")
    elif mrp_path.exists() and not pd.read_csv(mrp_path).empty:
        if "component_requirement_basis" not in check.columns:
            return _result("phase3_component_inventory", "FAIL", "Phase 3 output missing component_requirement_basis while MRP exists.")
        basis_values = set(check["component_requirement_basis"].dropna().astype(str).str.strip())
        if basis_values != {"MRP_NET_REQUIREMENT"}:
            return _result("phase3_component_inventory", "FAIL", f"Phase 3 did not use MRP net requirements: {sorted(basis_values)}")
    return _result("phase3_component_inventory", "PASS", f"Phase 3 checked inventory for {check['component_sku'].nunique()} components.")


def _check_phase2_supplier_check() -> dict:
    path = PHASE4_OUTPUTS["component_supplier_check"]
    if not path.exists():
        return _result("phase2_component_supplier", "FAIL", "Phase 2 component supplier check output is missing.")
    check = pd.read_csv(path)
    if check.empty:
        return _result("phase2_component_supplier", "WARNING", "No component shortages required supplier coverage checks.")
    if PHASE4_OUTPUTS["mrp_component_period_summary"].exists():
        required = {"net_component_requirement_qty", "component_requirement_basis", "mrp_planning_basis", "component_period_summary_used_flag"}
        missing = sorted(required.difference(check.columns))
        if missing:
            return _result("phase2_component_supplier", "FAIL", f"Phase 2 supplier output missing MRP trace columns: {missing}")
        basis_values = set(check["component_requirement_basis"].dropna().astype(str).str.strip())
        if basis_values and basis_values != {"MRP_COMPONENT_PERIOD_SUMMARY"}:
            return _result("phase2_component_supplier", "FAIL", f"Phase 2 did not preserve component-period basis: {sorted(basis_values)}")
        if not _all_true(check, "component_period_summary_used_flag"):
            return _result("phase2_component_supplier", "FAIL", "Phase 2 did not preserve component-period summary usage flag.")
    missing_count = int((check["supplier_risk_class"].astype(str) == "MISSING_SUPPLIER_COVERAGE").sum())
    status = "WARNING" if missing_count else "PASS"
    return _result("phase2_component_supplier", status, f"Phase 2 checked supplier coverage for {len(check)} shortage rows; missing coverage rows: {missing_count}.")


def _check_phase4_run_id_consistency() -> dict:
    run_ids_by_file = {}
    for name, path in PHASE4_OUTPUTS.items():
        if not path.exists():
            return _result("phase4_run_id_consistency", "FAIL", f"Missing Phase 4-related output: {path}")
        frame = pd.read_csv(path)
        if "planning_run_id" not in frame.columns:
            return _result("phase4_run_id_consistency", "WARNING", f"{name} has no planning_run_id column.")
        run_ids = sorted(set(frame["planning_run_id"].dropna().astype(str).str.strip()) - {""})
        run_ids_by_file[name] = run_ids
    all_sets = [set(values) for values in run_ids_by_file.values()]
    if not all_sets or any(not values for values in all_sets):
        return _result("phase4_run_id_consistency", "WARNING", f"One or more Phase 4 outputs has no run id: {run_ids_by_file}")
    common = set.intersection(*all_sets)
    unique_total = sorted(set.union(*all_sets))
    if not common:
        return _result("phase4_run_id_consistency", "FAIL", f"No common planning_run_id across Phase 4 outputs: {run_ids_by_file}")
    if len(unique_total) > 1:
        return _result("phase4_run_id_consistency", "WARNING", f"Multiple planning_run_id values found but a common run exists: {run_ids_by_file}")
    return _result("phase4_run_id_consistency", "PASS", f"Consistent planning_run_id across Phase 4 outputs: {unique_total[0]}")


def _check_phase4_advisory_only() -> dict:
    checked = []
    for name, path in PHASE4_OUTPUTS.items():
        if not path.exists():
            return _result("phase4_advisory_only", "FAIL", f"Missing Phase 4-related output: {path}")
        frame = pd.read_csv(path)
        if "advisory_only_flag" not in frame.columns:
            continue
        checked.append(name)
        if not _all_true(frame, "advisory_only_flag"):
            return _result("phase4_advisory_only", "FAIL", f"{name} contains non-advisory rows.")
    return _result("phase4_advisory_only", "PASS", f"All checked Phase 4 advisory flags are true: {checked}")


def _check_existing_outputs() -> dict:
    required_outputs = [
        PROJECT_ROOT / "phase 1" / "outputs" / "forecast_results.csv",
        PROJECT_ROOT / "phase 1" / "outputs" / "future_forecast_results.csv",
        PROJECT_ROOT / "phase 2" / "outputs" / "procurement_recommendations.csv",
        PROJECT_ROOT / "phase 3" / "outputs" / "inventory_status.csv",
    ]
    missing = [str(path) for path in required_outputs if not path.exists()]
    if missing:
        return _result("existing_outputs", "FAIL", f"Existing required outputs are missing: {missing}")
    return _result("existing_outputs", "PASS", "Existing Phase 1/2/3 outputs exist.")


def _check_safety_flags() -> dict:
    paths = [
        PROJECT_ROOT / "phase 3" / "outputs" / "inventory_re_evaluation.csv",
        PROJECT_ROOT / "phase 3" / "outputs" / "inventory_optimization_recommendations.csv",
        PROJECT_ROOT / "phase 3" / "outputs" / "inventory_control_master_decisions.csv",
        PROJECT_ROOT / "shared" / "outputs" / "integrated_replenishment_decisions.csv",
    ]
    true_count = 0
    checked_columns = []
    for path in paths:
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        for column in ["auto_apply_allowed", "purchase_order_creation_allowed", "production_order_release_allowed"]:
            if column in frame.columns:
                checked_columns.append(f"{path.name}.{column}")
                true_count += int(_to_bool(frame[column]).sum())
    if true_count:
        return _result("safety_flags", "FAIL", f"Safety flags enabled in {true_count} rows.")
    return _result("safety_flags", "PASS", f"No enabled execution flags found across {len(checked_columns)} checked columns.")


def _check_no_execution_outputs() -> dict:
    bad_files = []
    for path in (PHASE4_DIR / "outputs").glob("*"):
        if not path.is_file():
            continue
        lower_name = path.name.lower()
        if any(token in lower_name for token in EXECUTION_FILE_TOKENS):
            bad_files.append(str(path))
    if bad_files:
        return _result("no_execution_outputs", "FAIL", f"Execution-like Phase 4 output files found: {bad_files}")
    return _result("no_execution_outputs", "PASS", "No Phase 4 production/purchase/release/reservation output files found.")


def _check_no_routing_or_capacity_outputs() -> dict:
    blocked_tokens = [
        "capacity_feasibility",
        "capacity_plan",
        "utilization",
        "bottleneck",
        "queue",
        "detailed_schedule",
        "finite_schedule",
        "shop_floor_schedule",
        "production_sequence",
        "scheduling_engine",
        "simulation",
    ]
    bad_files = []
    for path in (PHASE4_DIR / "outputs").glob("*"):
        if not path.is_file():
            continue
        lower_name = path.name.lower()
        if any(token in lower_name for token in blocked_tokens):
            bad_files.append(str(path))
    if bad_files:
        return _result(
            "no_routing_or_capacity_outputs",
            "FAIL",
            f"Routing/capacity/scheduling/simulation-like Phase 4 outputs found: {bad_files}",
        )
    return _result(
        "no_routing_or_capacity_outputs",
        "PASS",
        "No Phase 4 capacity, utilization, bottleneck, queue, scheduling, or simulation outputs found.",
    )


def _resource_calendar_invalid_reference_count(frames: dict[str, pd.DataFrame]) -> int:
    valid_by_scope = {
        "WORKSTATION": set(frames["workstations"]["workstation_id"].astype(str).str.strip()),
        "MACHINE": set(frames["machines"]["machine_id"].astype(str).str.strip()),
        "LABOR": set(frames["labor_resources"]["labor_resource_id"].astype(str).str.strip()),
    }
    invalid_count = 0
    for _, row in frames["resource_calendar"].iterrows():
        scope = str(row.get("resource_scope", "")).strip()
        resource_id = str(row.get("resource_id", "")).strip()
        if resource_id not in valid_by_scope.get(scope, set()):
            invalid_count += 1
    return invalid_count


def _all_true(df: pd.DataFrame, column: str) -> bool:
    return column in df.columns and bool(_to_bool(df[column]).all())


def _valid_period_sequences(mps: pd.DataFrame) -> bool:
    sequence = pd.to_numeric(mps["period_sequence"], errors="coerce")
    if sequence.isna().any() or (sequence < 1).any():
        return False
    test = mps.assign(_period_sequence=sequence.astype(int)).sort_values(["finished_sku", "period_start"])
    for _, group in test.groupby("finished_sku"):
        expected = list(range(1, len(group) + 1))
        if group["_period_sequence"].tolist() != expected:
            return False
    return True


def _routing_has_cycle(routings: pd.DataFrame) -> bool:
    for _, group in routings.groupby("routing_id"):
        graph = {
            str(row["operation_id"]).strip(): _split_ids(row.get("successor_operation_ids", ""))
            for _, row in group.iterrows()
        }
        visiting = set()
        visited = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for next_node in graph.get(node, []):
                if visit(next_node):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        if any(visit(node) for node in graph):
            return True
    return False


def _split_ids(value: object) -> list[str]:
    text = "" if value is None else str(value).strip()
    if not text:
        return []
    return [item.strip() for item in text.split(";") if item.strip()]


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _result(name: str, status: str, message: str) -> dict:
    return {"check": name, "status": status, "message": message}


def _format_report(evidence: dict) -> str:
    lines = [
        "Phase 4 Initialization Validation with Step 3B Routing/Workflow Master Data",
        f"Generated at UTC: {evidence['generated_at_utc']}",
        f"Overall status: {evidence['overall_status']}",
        f"Fail count: {evidence['fail_count']}",
        f"Warning count: {evidence['warning_count']}",
        "",
        "Checks:",
    ]
    for check in evidence["checks"]:
        lines.append(f"- {check['status']}: {check['check']} - {check['message']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
