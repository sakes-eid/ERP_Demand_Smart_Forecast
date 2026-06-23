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
    "component_inventory_check": PROJECT_ROOT / "phase 3" / "outputs" / "phase4_component_inventory_check.csv",
    "component_supplier_check": PROJECT_ROOT / "phase 2" / "outputs" / "phase4_component_supplier_check.csv",
}
EXECUTION_FILE_TOKENS = [
    "production_order",
    "purchase_order",
    "released_order",
    "inventory_reservation",
]


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
    checks.append(_check_phase3_inventory_check())
    checks.append(_check_phase2_supplier_check())
    checks.append(_check_phase4_run_id_consistency())
    checks.append(_check_phase4_advisory_only())
    checks.append(_check_existing_outputs())
    checks.append(_check_safety_flags())
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


def _check_phase3_inventory_check() -> dict:
    path = PHASE4_OUTPUTS["component_inventory_check"]
    if not path.exists():
        return _result("phase3_component_inventory", "FAIL", "Phase 3 component inventory check output is missing.")
    check = pd.read_csv(path)
    if check.empty:
        return _result("phase3_component_inventory", "FAIL", "Phase 3 component inventory check has no rows.")
    return _result("phase3_component_inventory", "PASS", f"Phase 3 checked inventory for {check['component_sku'].nunique()} components.")


def _check_phase2_supplier_check() -> dict:
    path = PHASE4_OUTPUTS["component_supplier_check"]
    if not path.exists():
        return _result("phase2_component_supplier", "FAIL", "Phase 2 component supplier check output is missing.")
    check = pd.read_csv(path)
    if check.empty:
        return _result("phase2_component_supplier", "WARNING", "No component shortages required supplier coverage checks.")
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


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _result(name: str, status: str, message: str) -> dict:
    return {"check": name, "status": status, "message": message}


def _format_report(evidence: dict) -> str:
    lines = [
        "Phase 4 Initialization Validation with MPS Step 1B Rolling Inventory Balance",
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
