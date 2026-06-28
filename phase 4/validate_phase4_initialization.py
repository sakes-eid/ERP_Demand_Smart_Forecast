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
    "capacity_load_by_workstation": PHASE4_DIR / "outputs" / "phase4_capacity_load_by_workstation.csv",
    "capacity_operation_load_detail": PHASE4_DIR / "outputs" / "phase4_capacity_operation_load_detail.csv",
    "capacity_load_by_machine_type": PHASE4_DIR / "outputs" / "phase4_capacity_load_by_machine_type.csv",
    "capacity_load_by_labor_skill": PHASE4_DIR / "outputs" / "phase4_capacity_load_by_labor_skill.csv",
    "capacity_constraint_bridge": PHASE4_DIR / "outputs" / "phase4_capacity_constraint_bridge.csv",
    "capacity_feasibility_summary": PHASE4_DIR / "outputs" / "phase4_capacity_feasibility_summary.csv",
    "bottleneck_candidate_summary": PHASE4_DIR / "outputs" / "phase4_bottleneck_candidate_summary.csv",
    "capacity_manager_review_queue": PHASE4_DIR / "outputs" / "phase4_capacity_manager_review_queue.csv",
    "queue_pressure_by_workstation": PHASE4_DIR / "outputs" / "phase4_queue_pressure_by_workstation.csv",
    "queue_risk_summary": PHASE4_DIR / "outputs" / "phase4_queue_risk_summary.csv",
    "queue_manager_review_queue": PHASE4_DIR / "outputs" / "phase4_queue_manager_review_queue.csv",
    "bottleneck_visibility_summary": PHASE4_DIR / "outputs" / "phase4_bottleneck_visibility_summary.csv",
    "bottleneck_period_evidence": PHASE4_DIR / "outputs" / "phase4_bottleneck_period_evidence.csv",
    "bottleneck_manager_review_queue": PHASE4_DIR / "outputs" / "phase4_bottleneck_manager_review_queue.csv",
    "production_flow_view": PHASE4_DIR / "outputs" / "phase4_production_flow_view.csv",
    "flow_step_risk_summary": PHASE4_DIR / "outputs" / "phase4_flow_step_risk_summary.csv",
    "flow_manager_review_queue": PHASE4_DIR / "outputs" / "phase4_flow_manager_review_queue.csv",
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
CAPACITY_LOAD_FILE = PHASE4_DIR / "outputs" / "phase4_capacity_load_by_workstation.csv"
CAPACITY_OPERATION_DETAIL_FILE = PHASE4_DIR / "outputs" / "phase4_capacity_operation_load_detail.csv"
MACHINE_CAPACITY_LOAD_FILE = PHASE4_DIR / "outputs" / "phase4_capacity_load_by_machine_type.csv"
LABOR_CAPACITY_LOAD_FILE = PHASE4_DIR / "outputs" / "phase4_capacity_load_by_labor_skill.csv"
CAPACITY_CONSTRAINT_BRIDGE_FILE = PHASE4_DIR / "outputs" / "phase4_capacity_constraint_bridge.csv"
CAPACITY_FEASIBILITY_SUMMARY_FILE = PHASE4_DIR / "outputs" / "phase4_capacity_feasibility_summary.csv"
BOTTLENECK_CANDIDATE_SUMMARY_FILE = PHASE4_DIR / "outputs" / "phase4_bottleneck_candidate_summary.csv"
CAPACITY_MANAGER_REVIEW_QUEUE_FILE = PHASE4_DIR / "outputs" / "phase4_capacity_manager_review_queue.csv"
CAPACITY_VALIDATION_FILE = PHASE4_DIR / "outputs" / "phase4_capacity_validation.csv"
QUEUE_PRESSURE_FILE = PHASE4_DIR / "outputs" / "phase4_queue_pressure_by_workstation.csv"
QUEUE_RISK_SUMMARY_FILE = PHASE4_DIR / "outputs" / "phase4_queue_risk_summary.csv"
QUEUE_MANAGER_REVIEW_QUEUE_FILE = PHASE4_DIR / "outputs" / "phase4_queue_manager_review_queue.csv"
QUEUE_VALIDATION_FILE = PHASE4_DIR / "outputs" / "phase4_queue_validation.csv"
BOTTLENECK_VISIBILITY_SUMMARY_FILE = PHASE4_DIR / "outputs" / "phase4_bottleneck_visibility_summary.csv"
BOTTLENECK_PERIOD_EVIDENCE_FILE = PHASE4_DIR / "outputs" / "phase4_bottleneck_period_evidence.csv"
BOTTLENECK_MANAGER_REVIEW_QUEUE_FILE = PHASE4_DIR / "outputs" / "phase4_bottleneck_manager_review_queue.csv"
BOTTLENECK_VALIDATION_FILE = PHASE4_DIR / "outputs" / "phase4_bottleneck_validation.csv"
PRODUCTION_FLOW_VIEW_FILE = PHASE4_DIR / "outputs" / "phase4_production_flow_view.csv"
FLOW_STEP_RISK_SUMMARY_FILE = PHASE4_DIR / "outputs" / "phase4_flow_step_risk_summary.csv"
FLOW_MANAGER_REVIEW_QUEUE_FILE = PHASE4_DIR / "outputs" / "phase4_flow_manager_review_queue.csv"
FLOW_VALIDATION_FILE = PHASE4_DIR / "outputs" / "phase4_flow_validation.csv"


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
    checks.append(_check_capacity_load())
    checks.append(_check_queue_pressure())
    checks.append(_check_bottleneck_visibility())
    checks.append(_check_production_flow_view())
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


def _check_capacity_load() -> dict:
    if not CAPACITY_LOAD_FILE.exists():
        return _result("capacity_load", "FAIL", "Workstation capacity load output is missing.")
    load = pd.read_csv(CAPACITY_LOAD_FILE)
    if load.empty:
        return _result("capacity_load", "FAIL", "Workstation capacity load output has no rows.")
    required = {
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
    }
    missing = sorted(required.difference(load.columns))
    if missing:
        return _result("capacity_load", "FAIL", f"Capacity load output missing columns: {missing}")
    duplicate_count = int(load.duplicated(["planning_run_id", "period_start", "period_end", "workstation_id"]).sum())
    if duplicate_count:
        return _result("capacity_load", "FAIL", f"Capacity load has duplicate workstation-period rows: {duplicate_count}")
    for column in ["total_required_hours", "available_hours", "utilization_pct"]:
        values = pd.to_numeric(load[column], errors="coerce")
        if values.isna().any() or (values < 0).any():
            return _result("capacity_load", "FAIL", f"{column} must be numeric and non-negative.")
    if load["capacity_status"].astype(str).str.strip().eq("").any():
        return _result("capacity_load", "FAIL", "capacity_status must be populated for all rows.")
    basis_values = set(load["capacity_planning_basis"].dropna().astype(str).str.strip())
    if basis_values != {"MPS_ROUTING_WORKSTATION_LOAD"}:
        return _result("capacity_load", "FAIL", f"Unexpected capacity planning basis values: {sorted(basis_values)}")
    for flag in ["overload_flag", "near_capacity_flag", "no_capacity_record_flag"]:
        if flag not in load.columns:
            return _result("capacity_load", "FAIL", f"Missing capacity flag column: {flag}")
    if not _all_true(load, "advisory_only_flag"):
        return _result("capacity_load", "FAIL", "Capacity load contains non-advisory rows.")
    if not CAPACITY_VALIDATION_FILE.exists():
        return _result("capacity_load", "FAIL", "Capacity validation output is missing.")
    validation = pd.read_csv(CAPACITY_VALIDATION_FILE)
    if validation.empty:
        return _result("capacity_load", "FAIL", "Capacity validation output has no rows.")
    if "status" not in validation.columns:
        return _result("capacity_load", "FAIL", "Capacity validation output has no status column.")
    fail_count = int((validation["status"].astype(str).str.upper() == "FAIL").sum())
    if fail_count:
        return _result("capacity_load", "FAIL", f"Capacity validation contains FAIL rows: {fail_count}")
    if not CAPACITY_OPERATION_DETAIL_FILE.exists():
        return _result("capacity_load", "FAIL", "Capacity operation load detail output is missing.")
    detail = pd.read_csv(CAPACITY_OPERATION_DETAIL_FILE)
    if detail.empty:
        return _result("capacity_load", "FAIL", "Capacity operation load detail output has no rows.")
    if "advisory_only_flag" in detail.columns and not _all_true(detail, "advisory_only_flag"):
        return _result("capacity_load", "FAIL", "Capacity operation load detail contains non-advisory rows.")
    step4b_check = _check_step4b_capacity_outputs()
    if step4b_check["status"] == "FAIL":
        return step4b_check
    step4c_check = _check_step4c_capacity_outputs()
    if step4c_check["status"] == "FAIL":
        return step4c_check
    return _result(
        "capacity_load",
        "PASS",
        (
            "Step 4C capacity feasibility summary and bottleneck candidates valid; "
            f"rows={len(load)}, periods={load[['planning_run_id', 'period_start', 'period_end']].drop_duplicates().shape[0]}, "
            f"workstations={load['workstation_id'].nunique()}."
        ),
    )


def _check_step4b_capacity_outputs() -> dict:
    checks = [
        (
            MACHINE_CAPACITY_LOAD_FILE,
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
                "machine_overload_flag",
                "machine_near_capacity_flag",
                "no_machine_capacity_record_flag",
                "capacity_planning_basis",
                "advisory_only_flag",
            },
            ["machine_required_hours", "available_machine_hours", "machine_utilization_pct"],
            "machine_capacity_status",
            {"MPS_ROUTING_MACHINE_TYPE_LOAD"},
            "machine capacity",
        ),
        (
            LABOR_CAPACITY_LOAD_FILE,
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
                "labor_overload_flag",
                "labor_near_capacity_flag",
                "no_labor_capacity_record_flag",
                "labor_soft_warning_threshold_pct",
                "labor_hard_overload_threshold_pct",
                "labor_high_utilization_warning_flag",
                "labor_hard_overload_flag",
                "labor_capacity_interpretation",
                "capacity_planning_basis",
                "advisory_only_flag",
            },
            ["labor_required_hours", "available_labor_hours", "labor_utilization_pct"],
            "labor_capacity_status",
            {"MPS_ROUTING_LABOR_SKILL_LOAD"},
            "labor capacity",
        ),
    ]
    valid_statuses = {"NO_LOAD", "FEASIBLE", "NEAR_CAPACITY", "HIGH_UTILIZATION_WARNING", "OVERLOADED", "NO_CAPACITY_RECORD", "REVIEW_REQUIRED"}
    total_rows = 0
    for path, required, numeric_columns, status_column, basis_expected, label in checks:
        if not path.exists():
            return _result("capacity_load", "FAIL", f"{label} output is missing.")
        frame = pd.read_csv(path)
        total_rows += len(frame)
        if frame.empty:
            return _result("capacity_load", "FAIL", f"{label} output has no rows.")
        missing = sorted(required.difference(frame.columns))
        if missing:
            return _result("capacity_load", "FAIL", f"{label} output missing columns: {missing}")
        for column in numeric_columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            if values.isna().any() or (values < 0).any():
                return _result("capacity_load", "FAIL", f"{label} {column} must be numeric and non-negative.")
        if (~frame[status_column].astype(str).isin(valid_statuses)).any():
            return _result("capacity_load", "FAIL", f"{label} contains invalid status values.")
        if set(frame["capacity_planning_basis"].dropna().astype(str).str.strip()) != basis_expected:
            return _result("capacity_load", "FAIL", f"{label} contains unexpected planning basis values.")
        if not _all_true(frame, "advisory_only_flag"):
            return _result("capacity_load", "FAIL", f"{label} output contains non-advisory rows.")
        if label == "labor capacity":
            labor_check = _validate_labor_capacity_thresholds(frame)
            if labor_check:
                return labor_check
    workstation_load = pd.read_csv(CAPACITY_LOAD_FILE)
    workstation_required = {
        "workstation_capacity_basis",
        "workstation_capacity_unit_count",
        "effective_workstation_available_hours",
        "workstation_capacity_interpretation",
    }
    workstation_missing = sorted(workstation_required.difference(workstation_load.columns))
    if workstation_missing:
        return _result("capacity_load", "FAIL", f"Workstation capacity output missing basis columns: {workstation_missing}")
    basis_values = set(workstation_load["workstation_capacity_basis"].dropna().astype(str).str.strip())
    if basis_values != {"SINGLE_STATION_CALENDAR"}:
        return _result("capacity_load", "FAIL", f"Unexpected workstation capacity basis values: {sorted(basis_values)}")
    if workstation_load["workstation_capacity_interpretation"].astype(str).str.strip().eq("").any():
        return _result("capacity_load", "FAIL", "Workstation capacity interpretation must be populated.")
    if not CAPACITY_CONSTRAINT_BRIDGE_FILE.exists():
        return _result("capacity_load", "FAIL", "Capacity constraint bridge output is missing.")
    bridge = pd.read_csv(CAPACITY_CONSTRAINT_BRIDGE_FILE)
    if bridge.empty:
        return _result("capacity_load", "FAIL", "Capacity constraint bridge output has no rows.")
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
        "capacity_planning_basis",
        "advisory_only_flag",
    }
    missing_bridge = sorted(bridge_required.difference(bridge.columns))
    if missing_bridge:
        return _result("capacity_load", "FAIL", f"Constraint bridge missing columns: {missing_bridge}")
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
    if (~bridge["combined_constraint_type"].astype(str).isin(valid_constraint_types)).any():
        return _result("capacity_load", "FAIL", "Constraint bridge contains invalid combined_constraint_type values.")
    warning_without_review = _to_bool(bridge["labor_high_utilization_warning_flag"]) & ~_to_bool(bridge["constraint_review_required_flag"])
    if warning_without_review.any():
        return _result("capacity_load", "FAIL", "Constraint bridge must require review when labor high-utilization warning exists.")
    if not _all_true(bridge, "advisory_only_flag"):
        return _result("capacity_load", "FAIL", "Constraint bridge contains non-advisory rows.")
    return _result("capacity_load", "PASS", f"Step 4B outputs valid; machine/labor rows={total_rows}, bridge_rows={len(bridge)}.")


def _check_step4c_capacity_outputs() -> dict:
    for path, label in [
        (CAPACITY_FEASIBILITY_SUMMARY_FILE, "capacity feasibility summary"),
        (BOTTLENECK_CANDIDATE_SUMMARY_FILE, "bottleneck candidate summary"),
    ]:
        if not path.exists():
            return _result("capacity_load", "FAIL", f"{label} output is missing.")
        if pd.read_csv(path).empty:
            return _result("capacity_load", "FAIL", f"{label} output has no rows.")

    feasibility = pd.read_csv(CAPACITY_FEASIBILITY_SUMMARY_FILE)
    candidates = pd.read_csv(BOTTLENECK_CANDIDATE_SUMMARY_FILE)
    review_queue = pd.read_csv(CAPACITY_MANAGER_REVIEW_QUEUE_FILE) if CAPACITY_MANAGER_REVIEW_QUEUE_FILE.exists() else pd.DataFrame()
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
    missing_feasibility = sorted(feasibility_required.difference(feasibility.columns))
    if missing_feasibility:
        return _result("capacity_load", "FAIL", f"Capacity feasibility summary missing columns: {missing_feasibility}")
    missing_candidates = sorted(candidate_required.difference(candidates.columns))
    if missing_candidates:
        return _result("capacity_load", "FAIL", f"Bottleneck candidate summary missing columns: {missing_candidates}")
    valid_statuses = {"FEASIBLE", "FEASIBLE_WITH_LABOR_WARNING", "CAPACITY_REVIEW_REQUIRED", "NOT_CAPACITY_FEASIBLE", "REVIEW_REQUIRED"}
    valid_layers = {"NONE", "WORKSTATION_CALENDAR", "MACHINE", "LABOR", "LABOR_HIGH_UTILIZATION", "MULTI_LAYER", "REVIEW_REQUIRED"}
    valid_levels = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    if (~feasibility["capacity_feasibility_status"].astype(str).isin(valid_statuses)).any():
        return _result("capacity_load", "FAIL", "Capacity feasibility summary contains invalid statuses.")
    if (~feasibility["main_constraint_layer"].astype(str).isin(valid_layers)).any():
        return _result("capacity_load", "FAIL", "Capacity feasibility summary contains invalid constraint layers.")
    if not _all_true(feasibility, "advisory_only_flag"):
        return _result("capacity_load", "FAIL", "Capacity feasibility summary contains non-advisory rows.")
    overload_not_flagged = (pd.to_numeric(feasibility["overloaded_workstation_count"], errors="coerce") > 0) & (
        feasibility["capacity_feasibility_status"].astype(str) != "NOT_CAPACITY_FEASIBLE"
    )
    if overload_not_flagged.any():
        return _result("capacity_load", "FAIL", "Periods with workstation overload must be NOT_CAPACITY_FEASIBLE.")
    scores = pd.to_numeric(candidates["bottleneck_candidate_score"], errors="coerce")
    ranks = pd.to_numeric(candidates["bottleneck_candidate_rank"], errors="coerce")
    if scores.isna().any() or (scores < 0).any():
        return _result("capacity_load", "FAIL", "Bottleneck candidate scores must be numeric and non-negative.")
    if ranks.isna().any() or candidates["bottleneck_candidate_rank"].duplicated().any():
        return _result("capacity_load", "FAIL", "Bottleneck candidate ranks must be numeric and unique.")
    if (~candidates["bottleneck_candidate_level"].astype(str).isin(valid_levels)).any():
        return _result("capacity_load", "FAIL", "Bottleneck candidate summary contains invalid levels.")
    if candidates["bottleneck_candidate_reason"].astype(str).str.contains("FINAL_BOTTLENECK", case=False, na=False).any():
        return _result("capacity_load", "FAIL", "Bottleneck candidate summary must not mark final bottlenecks.")
    if not _all_true(candidates, "advisory_only_flag"):
        return _result("capacity_load", "FAIL", "Bottleneck candidate summary contains non-advisory rows.")
    infeasible_exists = feasibility["capacity_feasibility_status"].astype(str).isin(["NOT_CAPACITY_FEASIBLE", "CAPACITY_REVIEW_REQUIRED", "REVIEW_REQUIRED"]).any()
    if infeasible_exists:
        if review_queue.empty:
            return _result("capacity_load", "FAIL", "Capacity manager review queue is required when infeasibility exists.")
        missing_review = sorted(review_required.difference(review_queue.columns))
        if missing_review:
            return _result("capacity_load", "FAIL", f"Capacity manager review queue missing columns: {missing_review}")
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
        if (~review_queue["issue_type"].astype(str).isin(valid_issue_types)).any():
            return _result("capacity_load", "FAIL", "Capacity manager review queue contains invalid issue types.")
        if (~review_queue["issue_severity"].astype(str).isin(valid_severities)).any():
            return _result("capacity_load", "FAIL", "Capacity manager review queue contains invalid issue severities.")
        if _to_bool(review_queue["auto_action_allowed"]).any():
            return _result("capacity_load", "FAIL", "Capacity manager review queue cannot allow automatic action.")
        if not _all_true(review_queue, "advisory_only_flag"):
            return _result("capacity_load", "FAIL", "Capacity manager review queue contains non-advisory rows.")
    return _result(
        "capacity_load",
        "PASS",
        f"Step 4C outputs valid; feasibility_rows={len(feasibility)}, candidate_rows={len(candidates)}, review_rows={len(review_queue)}.",
    )


def _validate_labor_capacity_thresholds(frame: pd.DataFrame) -> dict | None:
    utilization = pd.to_numeric(frame["labor_utilization_pct"], errors="coerce")
    soft = pd.to_numeric(frame["labor_soft_warning_threshold_pct"], errors="coerce")
    hard = pd.to_numeric(frame["labor_hard_overload_threshold_pct"], errors="coerce")
    if (soft != 80).any() or (hard != 95).any():
        return _result("capacity_load", "FAIL", "Labor threshold columns must be 80 and 95 for all rows.")
    warning_band = (utilization > 80) & (utilization <= 95)
    hard_band = utilization > 95
    if (_to_bool(frame["labor_high_utilization_warning_flag"]) != warning_band).any():
        return _result("capacity_load", "FAIL", "Labor high-utilization warning flags do not match >80 and <=95 utilization.")
    if (_to_bool(frame["labor_hard_overload_flag"]) != hard_band).any():
        return _result("capacity_load", "FAIL", "Labor hard overload flags do not match >95 utilization.")
    if (frame.loc[warning_band, "labor_capacity_status"].astype(str) != "HIGH_UTILIZATION_WARNING").any():
        return _result("capacity_load", "FAIL", "Labor utilization >80 and <=95 must use HIGH_UTILIZATION_WARNING.")
    if (frame.loc[warning_band, "labor_capacity_status"].astype(str) == "FEASIBLE").any():
        return _result("capacity_load", "FAIL", "Labor utilization >80 and <=95 must not be marked FEASIBLE.")
    if (frame.loc[hard_band, "labor_capacity_status"].astype(str) != "OVERLOADED").any():
        return _result("capacity_load", "FAIL", "Labor utilization >95 must be marked OVERLOADED.")
    return None


def _check_queue_pressure() -> dict:
    for path, label in [
        (QUEUE_PRESSURE_FILE, "queue pressure by workstation"),
        (QUEUE_RISK_SUMMARY_FILE, "queue risk summary"),
        (QUEUE_VALIDATION_FILE, "queue validation"),
    ]:
        if not path.exists():
            return _result("queue_pressure", "FAIL", f"{label} output is missing.")
        if pd.read_csv(path).empty:
            return _result("queue_pressure", "FAIL", f"{label} output has no rows.")
    pressure = pd.read_csv(QUEUE_PRESSURE_FILE)
    summary = pd.read_csv(QUEUE_RISK_SUMMARY_FILE)
    validation = pd.read_csv(QUEUE_VALIDATION_FILE)
    fail_count = int((validation["status"].astype(str).str.upper() == "FAIL").sum()) if "status" in validation.columns else len(validation)
    if fail_count:
        return _result("queue_pressure", "FAIL", f"Queue validation contains FAIL rows: {fail_count}")
    pressure_required = {
        "planning_run_id",
        "period_start",
        "period_end",
        "workstation_id",
        "workstation_name",
        "estimated_queue_pressure_score",
        "estimated_queue_pressure_level",
        "estimated_wip_risk_level",
        "queue_measurement_type",
        "actual_queue_length_available_flag",
        "actual_wait_time_available_flag",
        "future_actual_queue_tracking_flag",
        "routing_join_pressure_flag",
        "parallel_merge_pressure_flag",
        "advisory_only_flag",
    }
    summary_required = {
        "planning_run_id",
        "workstation_id",
        "workstation_name",
        "max_estimated_queue_pressure_score",
        "queue_risk_rank",
        "overall_queue_risk_level",
        "advisory_only_flag",
    }
    missing_pressure = sorted(pressure_required.difference(pressure.columns))
    if missing_pressure:
        return _result("queue_pressure", "FAIL", f"Queue pressure output missing columns: {missing_pressure}")
    missing_summary = sorted(summary_required.difference(summary.columns))
    if missing_summary:
        return _result("queue_pressure", "FAIL", f"Queue risk summary missing columns: {missing_summary}")
    scores = pd.to_numeric(pressure["estimated_queue_pressure_score"], errors="coerce")
    if scores.isna().any() or (scores < 0).any():
        return _result("queue_pressure", "FAIL", "Queue pressure scores must be numeric and non-negative.")
    valid_levels = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    if (~pressure["estimated_queue_pressure_level"].astype(str).isin(valid_levels)).any():
        return _result("queue_pressure", "FAIL", "Queue pressure output contains invalid pressure levels.")
    if (~pressure["estimated_wip_risk_level"].astype(str).isin(valid_levels)).any():
        return _result("queue_pressure", "FAIL", "Queue pressure output contains invalid WIP risk levels.")
    if set(pressure["queue_measurement_type"].dropna().astype(str).str.strip()) != {"ESTIMATED_FROM_CAPACITY_PLAN"}:
        return _result("queue_pressure", "FAIL", "Queue measurement type must be ESTIMATED_FROM_CAPACITY_PLAN.")
    if _to_bool(pressure["actual_queue_length_available_flag"]).any():
        return _result("queue_pressure", "FAIL", "Actual queue length availability must be False.")
    if _to_bool(pressure["actual_wait_time_available_flag"]).any():
        return _result("queue_pressure", "FAIL", "Actual wait time availability must be False.")
    if not _all_true(pressure, "future_actual_queue_tracking_flag"):
        return _result("queue_pressure", "FAIL", "Future actual queue tracking flag must be True.")
    if not _all_true(pressure, "advisory_only_flag") or not _all_true(summary, "advisory_only_flag"):
        return _result("queue_pressure", "FAIL", "Step 5A queue outputs must be advisory-only.")
    final_assembly = pressure[pressure["workstation_id"].astype(str) == "WS-FINAL-ASM"]
    if final_assembly.empty or not _to_bool(final_assembly["routing_join_pressure_flag"]).any():
        return _result("queue_pressure", "FAIL", "Final Assembly must be flagged as routing join pressure when routing supports it.")
    high_or_critical = pressure["estimated_queue_pressure_level"].astype(str).isin({"HIGH", "CRITICAL"}).any()
    if high_or_critical:
        if not QUEUE_MANAGER_REVIEW_QUEUE_FILE.exists():
            return _result("queue_pressure", "FAIL", "Queue manager review queue is missing while high/critical queue risk exists.")
        review = pd.read_csv(QUEUE_MANAGER_REVIEW_QUEUE_FILE)
        if review.empty:
            return _result("queue_pressure", "FAIL", "Queue manager review queue has no rows while high/critical queue risk exists.")
        required_review = {"queue_review_item_id", "queue_issue_type", "queue_issue_severity", "auto_action_allowed", "advisory_only_flag"}
        missing_review = sorted(required_review.difference(review.columns))
        if missing_review:
            return _result("queue_pressure", "FAIL", f"Queue manager review queue missing columns: {missing_review}")
        if _to_bool(review["auto_action_allowed"]).any():
            return _result("queue_pressure", "FAIL", "Queue manager review queue cannot allow automatic action.")
        if not _all_true(review, "advisory_only_flag"):
            return _result("queue_pressure", "FAIL", "Queue manager review queue must be advisory-only.")
    return _result(
        "queue_pressure",
        "PASS",
        f"Step 5A queue pressure valid; pressure_rows={len(pressure)}, summary_rows={len(summary)}.",
    )


def _check_bottleneck_visibility() -> dict:
    for path, label in [
        (BOTTLENECK_VISIBILITY_SUMMARY_FILE, "bottleneck visibility summary"),
        (BOTTLENECK_PERIOD_EVIDENCE_FILE, "bottleneck period evidence"),
        (BOTTLENECK_VALIDATION_FILE, "bottleneck validation"),
    ]:
        if not path.exists():
            return _result("bottleneck_visibility", "FAIL", f"{label} output is missing.")
        if pd.read_csv(path).empty:
            return _result("bottleneck_visibility", "FAIL", f"{label} output has no rows.")
    summary = pd.read_csv(BOTTLENECK_VISIBILITY_SUMMARY_FILE)
    period = pd.read_csv(BOTTLENECK_PERIOD_EVIDENCE_FILE)
    validation = pd.read_csv(BOTTLENECK_VALIDATION_FILE)
    fail_count = int((validation["status"].astype(str).str.upper() == "FAIL").sum()) if "status" in validation.columns else len(validation)
    if fail_count:
        return _result("bottleneck_visibility", "FAIL", f"Bottleneck validation contains FAIL rows: {fail_count}")
    summary_required = {
        "planning_run_id",
        "workstation_id",
        "workstation_name",
        "combined_bottleneck_visibility_score",
        "bottleneck_visibility_rank",
        "bottleneck_visibility_level",
        "confirmation_status",
        "advisory_only_flag",
    }
    period_required = {
        "planning_run_id",
        "period_start",
        "period_end",
        "workstation_id",
        "period_bottleneck_visibility_score",
        "period_bottleneck_visibility_level",
        "evidence_type",
        "confirmation_status",
        "advisory_only_flag",
    }
    missing_summary = sorted(summary_required.difference(summary.columns))
    missing_period = sorted(period_required.difference(period.columns))
    if missing_summary:
        return _result("bottleneck_visibility", "FAIL", f"Bottleneck visibility summary missing columns: {missing_summary}")
    if missing_period:
        return _result("bottleneck_visibility", "FAIL", f"Bottleneck period evidence missing columns: {missing_period}")
    scores = pd.to_numeric(summary["combined_bottleneck_visibility_score"], errors="coerce")
    if scores.isna().any() or (scores < 0).any():
        return _result("bottleneck_visibility", "FAIL", "Combined bottleneck visibility scores must be numeric and non-negative.")
    valid_levels = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    if (~summary["bottleneck_visibility_level"].astype(str).isin(valid_levels)).any():
        return _result("bottleneck_visibility", "FAIL", "Bottleneck visibility summary contains invalid levels.")
    if (~period["period_bottleneck_visibility_level"].astype(str).isin(valid_levels)).any():
        return _result("bottleneck_visibility", "FAIL", "Bottleneck period evidence contains invalid levels.")
    expected_status = "PLANNING_EVIDENCE_ONLY_NOT_SIMULATION_CONFIRMED"
    if set(summary["confirmation_status"].dropna().astype(str).str.strip()) != {expected_status}:
        return _result("bottleneck_visibility", "FAIL", "Bottleneck summary confirmation status must be planning evidence only.")
    if set(period["confirmation_status"].dropna().astype(str).str.strip()) != {expected_status}:
        return _result("bottleneck_visibility", "FAIL", "Bottleneck period confirmation status must be planning evidence only.")
    if not _all_true(summary, "advisory_only_flag") or not _all_true(period, "advisory_only_flag"):
        return _result("bottleneck_visibility", "FAIL", "Step 5B bottleneck outputs must be advisory-only.")
    forbidden_columns = [
        column
        for column in list(summary.columns) + list(period.columns)
        if any(token in column.lower() for token in ["final_bottleneck", "actual_bottleneck", "measured_bottleneck", "simulation_confirmed_bottleneck"])
    ]
    if forbidden_columns:
        return _result("bottleneck_visibility", "FAIL", f"Forbidden final/measured bottleneck column names found: {forbidden_columns}")
    high_or_critical = summary["bottleneck_visibility_level"].astype(str).isin({"HIGH", "CRITICAL"}).any()
    if high_or_critical:
        if not BOTTLENECK_MANAGER_REVIEW_QUEUE_FILE.exists():
            return _result("bottleneck_visibility", "FAIL", "Bottleneck manager review queue is missing while high/critical candidates exist.")
        review = pd.read_csv(BOTTLENECK_MANAGER_REVIEW_QUEUE_FILE)
        if review.empty:
            return _result("bottleneck_visibility", "FAIL", "Bottleneck manager review queue has no rows while high/critical candidates exist.")
        required_review = {"bottleneck_review_item_id", "bottleneck_issue_type", "bottleneck_issue_severity", "auto_action_allowed", "advisory_only_flag"}
        missing_review = sorted(required_review.difference(review.columns))
        if missing_review:
            return _result("bottleneck_visibility", "FAIL", f"Bottleneck manager review queue missing columns: {missing_review}")
        if _to_bool(review["auto_action_allowed"]).any():
            return _result("bottleneck_visibility", "FAIL", "Bottleneck manager review queue cannot allow automatic action.")
        if not _all_true(review, "advisory_only_flag"):
            return _result("bottleneck_visibility", "FAIL", "Bottleneck manager review queue must be advisory-only.")
    return _result(
        "bottleneck_visibility",
        "PASS",
        f"Step 5B bottleneck visibility valid; summary_rows={len(summary)}, period_rows={len(period)}.",
    )


def _check_production_flow_view() -> dict:
    for path, label in [
        (PRODUCTION_FLOW_VIEW_FILE, "production flow view"),
        (FLOW_STEP_RISK_SUMMARY_FILE, "flow-step risk summary"),
        (FLOW_VALIDATION_FILE, "flow validation"),
    ]:
        if not path.exists():
            return _result("production_flow_view", "FAIL", f"{label} output is missing.")
        if pd.read_csv(path).empty:
            return _result("production_flow_view", "FAIL", f"{label} output has no rows.")
    flow = pd.read_csv(PRODUCTION_FLOW_VIEW_FILE)
    summary = pd.read_csv(FLOW_STEP_RISK_SUMMARY_FILE)
    validation = pd.read_csv(FLOW_VALIDATION_FILE)
    fail_count = int((validation["status"].astype(str).str.upper() == "FAIL").sum()) if "status" in validation.columns else len(validation)
    if fail_count:
        return _result("production_flow_view", "FAIL", f"Flow validation contains FAIL rows: {fail_count}")
    flow_required = {
        "planning_run_id",
        "finished_sku",
        "operation_id",
        "operation_sequence",
        "workstation_id",
        "workstation_name",
        "can_run_in_parallel_flag",
        "join_required_before_next_flag",
        "routing_join_pressure_flag",
        "parallel_merge_pressure_flag",
        "estimated_queue_pressure_level",
        "bottleneck_visibility_level",
        "flow_step_risk_level",
        "confirmation_status",
        "advisory_only_flag",
    }
    summary_required = {
        "planning_run_id",
        "finished_sku",
        "workstation_id",
        "flow_step_risk_level",
        "flow_step_risk_score",
        "confirmation_status",
        "advisory_only_flag",
    }
    missing_flow = sorted(flow_required.difference(flow.columns))
    missing_summary = sorted(summary_required.difference(summary.columns))
    if missing_flow:
        return _result("production_flow_view", "FAIL", f"Production flow view missing columns: {missing_flow}")
    if missing_summary:
        return _result("production_flow_view", "FAIL", f"Flow-step risk summary missing columns: {missing_summary}")
    if not BIKE_SKUS.issubset(set(flow["finished_sku"].astype(str))):
        return _result("production_flow_view", "FAIL", "Road Bike and Mountain Bike must both appear in production flow view.")
    if not _to_bool(flow["can_run_in_parallel_flag"]).any():
        return _result("production_flow_view", "FAIL", "Production flow view must represent parallel operations.")
    if not (_to_bool(flow["join_required_before_next_flag"]) | _to_bool(flow["routing_join_pressure_flag"])).any():
        return _result("production_flow_view", "FAIL", "Production flow view must represent join operations.")
    final_assembly = flow[flow["workstation_id"].astype(str) == "WS-FINAL-ASM"]
    if final_assembly.empty or not _to_bool(final_assembly["routing_join_pressure_flag"]).any():
        return _result("production_flow_view", "FAIL", "Final Assembly must be marked as join/merge pressure.")
    valid_levels = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    if (~flow["flow_step_risk_level"].astype(str).isin(valid_levels)).any():
        return _result("production_flow_view", "FAIL", "Production flow view contains invalid flow risk levels.")
    expected_status = "PLANNING_EVIDENCE_ONLY_NOT_SIMULATION_CONFIRMED"
    if set(flow["confirmation_status"].dropna().astype(str).str.strip()) != {expected_status}:
        return _result("production_flow_view", "FAIL", "Production flow confirmation status must be planning evidence only.")
    if set(summary["confirmation_status"].dropna().astype(str).str.strip()) != {expected_status}:
        return _result("production_flow_view", "FAIL", "Flow summary confirmation status must be planning evidence only.")
    if not _all_true(flow, "advisory_only_flag") or not _all_true(summary, "advisory_only_flag"):
        return _result("production_flow_view", "FAIL", "Step 5C flow outputs must be advisory-only.")
    high_or_critical = flow["flow_step_risk_level"].astype(str).isin({"HIGH", "CRITICAL"}).any()
    if high_or_critical:
        if not FLOW_MANAGER_REVIEW_QUEUE_FILE.exists():
            return _result("production_flow_view", "FAIL", "Flow manager review queue is missing while high/critical flow risks exist.")
        review = pd.read_csv(FLOW_MANAGER_REVIEW_QUEUE_FILE)
        if review.empty:
            return _result("production_flow_view", "FAIL", "Flow manager review queue has no rows while high/critical flow risks exist.")
        required_review = {"flow_review_item_id", "flow_issue_type", "flow_issue_severity", "auto_action_allowed", "advisory_only_flag"}
        missing_review = sorted(required_review.difference(review.columns))
        if missing_review:
            return _result("production_flow_view", "FAIL", f"Flow manager review queue missing columns: {missing_review}")
        if _to_bool(review["auto_action_allowed"]).any():
            return _result("production_flow_view", "FAIL", "Flow manager review queue cannot allow automatic action.")
        if not _all_true(review, "advisory_only_flag"):
            return _result("production_flow_view", "FAIL", "Flow manager review queue must be advisory-only.")
    return _result(
        "production_flow_view",
        "PASS",
        f"Step 5C production flow view valid; flow_rows={len(flow)}, summary_rows={len(summary)}.",
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
        "capacity_plan",
        "utilization",
        "streamlit",
        "final_bottleneck",
        "actual_bottleneck",
        "measured_bottleneck",
        "simulation_confirmed_bottleneck",
        "confirmed_bottleneck",
        "bottleneck_ranking",
        "workstation_queue",
        "operation_queue",
        "queue_simulation",
        "actual_queue_length",
        "measured_wait_time",
        "real_queue_time",
        "observed_queue_length",
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
            f"Future-only queue/scheduling/simulation-like Phase 4 outputs found: {bad_files}",
        )
    return _result(
        "no_routing_or_capacity_outputs",
        "PASS",
        "No UI, measured/final bottleneck, detailed scheduling, or simulation outputs found.",
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
        "Phase 4 Initialization Validation with Step 5C Production Flow and Queue-Bottleneck Flow View",
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
