"""Validate shared spare-part master data and build advisory integration contexts."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = PROJECT_ROOT / "shared"
DATA_DIR = SHARED_DIR / "data"
OUTPUT_DIR = SHARED_DIR / "outputs"
PHASE1_DIR = PROJECT_ROOT / "phase 1"
PHASE2_DIR = PROJECT_ROOT / "phase 2"
PHASE3_DIR = PROJECT_ROOT / "phase 3"
PHASE4_DIR = PROJECT_ROOT / "phase 4"
PHASE4_OUTPUT_DIR = PHASE4_DIR / "outputs"

SPARE_PARTS_FILE = DATA_DIR / "spare_parts_master.csv"
MACHINE_REQUIREMENTS_FILE = DATA_DIR / "machine_spare_part_requirements.csv"
PHASE4_MACHINES_FILE = PHASE4_DIR / "data" / "machines.csv"
PHASE4_MPS_FILE = PHASE4_OUTPUT_DIR / "phase4_master_production_schedule.csv"
PHASE1_PRODUCTS_FILE = PHASE1_DIR / "data" / "products.csv"
PHASE1_DEMAND_FILE = PHASE1_DIR / "data" / "demand_history.csv"
PHASE2_SUPPLIER_SKU_FILE = PHASE2_DIR / "data" / "supplier_sku.csv"
PHASE3_INVENTORY_FILE = PHASE3_DIR / "data" / "inventory.csv"

PHASE1_SPARE_DEMAND_CONTEXT_FILE = PHASE1_DIR / "outputs" / "phase1_spare_part_demand_context.csv"
PHASE2_SPARE_SUPPLIER_CHECK_FILE = PHASE2_DIR / "outputs" / "phase4_spare_part_supplier_check.csv"
PHASE3_SPARE_INVENTORY_CHECK_FILE = PHASE3_DIR / "outputs" / "phase4_spare_part_inventory_check.csv"
VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "spare_part_validation.csv"
MACHINE_REQUIREMENT_CONTEXT_FILE = OUTPUT_DIR / "spare_part_machine_requirement_context.csv"
PHASE_INTEGRATION_CONTEXT_FILE = OUTPUT_DIR / "spare_part_phase_integration_context.csv"
MANAGER_REVIEW_QUEUE_FILE = OUTPUT_DIR / "spare_part_manager_review_queue.csv"
PHASE4_SPARE_PART_CONTEXT_FILE = PHASE4_OUTPUT_DIR / "phase4_spare_part_requirement_context.csv"

SOURCE_PHASE = "SHARED_STEP7B_SPARE_PART_SKU_INTEGRATION"
ALLOWED_TYPES = {"LUBRICANT", "BEARING", "SENSOR", "TOOLING", "FIXTURE", "CALIBRATION", "CONSUMABLE", "ELECTRICAL", "MECHANICAL", "SAFETY", "GENERAL_MRO"}
ALLOWED_CRITICALITY = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
ALLOWED_MAINT_LEVELS = {"LIGHT", "MEDIUM", "HEAVY", "BREAKDOWN_REPAIR", "GENERAL", "CALIBRATION"}
ALLOWED_USAGE_BASIS = {"OPERATIONS_BASED_MAINTENANCE", "TIME_BASED_MAINTENANCE", "BREAKDOWN_REPAIR", "GENERAL_CONSUMABLE", "CALIBRATION"}
INVENTORY_STATUSES = {"SUFFICIENT", "BELOW_SAFETY_STOCK", "BELOW_REORDER_POINT", "OUT_OF_STOCK", "NO_INVENTORY_RECORD", "REVIEW_REQUIRED"}
SUPPLIER_STATUSES = {"COVERED", "LIMITED_COVERAGE", "NO_SUPPLIER_COVERAGE", "REVIEW_REQUIRED"}
INTEGRATION_STATUSES = {"FULLY_INTEGRATED", "PARTIAL_INTEGRATION_REVIEW", "MISSING_DEMAND_CONTEXT", "MISSING_INVENTORY_CONTEXT", "MISSING_SUPPLIER_CONTEXT", "REVIEW_REQUIRED"}


def build_spare_part_master_data_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    checks: list[dict] = []
    frames = {
        "spares": _load_csv(SPARE_PARTS_FILE, "spare_parts_master", checks),
        "requirements": _load_csv(MACHINE_REQUIREMENTS_FILE, "machine_spare_part_requirements", checks),
        "machines": _load_csv(PHASE4_MACHINES_FILE, "phase4_machines", checks),
        "products": _load_csv(PHASE1_PRODUCTS_FILE, "phase1_products", checks),
        "demand": _load_csv(PHASE1_DEMAND_FILE, "phase1_demand_history", checks),
        "supplier_sku": _load_csv(PHASE2_SUPPLIER_SKU_FILE, "phase2_supplier_sku", checks),
        "inventory": _load_csv(PHASE3_INVENTORY_FILE, "phase3_inventory", checks),
    }
    demand_context = pd.DataFrame()
    supplier_check = pd.DataFrame()
    inventory_check = pd.DataFrame()
    requirement_context = pd.DataFrame()
    integration_context = pd.DataFrame()
    review_queue = pd.DataFrame()
    phase4_context = pd.DataFrame()

    if all(frame is not None for frame in frames.values()):
        _validate_master_data(frames, checks)
        demand_context = _build_phase1_demand_context(frames["spares"], frames["demand"])
        inventory_check = _build_phase3_inventory_check(frames["spares"], frames["requirements"], frames["inventory"])
        supplier_check = _build_phase2_supplier_check(frames["spares"], frames["supplier_sku"])
        requirement_context = _build_machine_requirement_context(frames["spares"], frames["requirements"])
        integration_context = _build_phase_integration_context(frames["spares"], frames["requirements"], demand_context, inventory_check, supplier_check)
        review_queue = _build_manager_review_queue(integration_context, inventory_check, supplier_check, frames["spares"])
        phase4_context = _build_phase4_spare_part_context(frames["spares"], frames["requirements"], frames["machines"], inventory_check, supplier_check)
        _validate_context_outputs(demand_context, supplier_check, inventory_check, requirement_context, integration_context, review_queue, phase4_context, checks)
    _check_no_blocked_outputs(checks)

    for directory in [OUTPUT_DIR, PHASE1_SPARE_DEMAND_CONTEXT_FILE.parent, PHASE2_SPARE_SUPPLIER_CHECK_FILE.parent, PHASE3_SPARE_INVENTORY_CHECK_FILE.parent, PHASE4_OUTPUT_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    demand_context.to_csv(PHASE1_SPARE_DEMAND_CONTEXT_FILE, index=False)
    supplier_check.to_csv(PHASE2_SPARE_SUPPLIER_CHECK_FILE, index=False)
    inventory_check.to_csv(PHASE3_SPARE_INVENTORY_CHECK_FILE, index=False)
    requirement_context.to_csv(MACHINE_REQUIREMENT_CONTEXT_FILE, index=False)
    integration_context.to_csv(PHASE_INTEGRATION_CONTEXT_FILE, index=False)
    review_queue.to_csv(MANAGER_REVIEW_QUEUE_FILE, index=False)
    phase4_context.to_csv(PHASE4_SPARE_PART_CONTEXT_FILE, index=False)
    return validation, requirement_context, integration_context, review_queue, phase4_context


def _validate_master_data(frames: dict[str, pd.DataFrame], checks: list[dict]) -> None:
    required = {
        "spares": {"spare_part_sku", "spare_part_name", "spare_part_type", "linked_machine_type", "linked_machine_id", "criticality", "unit_cost", "currency", "storage_type", "shelf_life_days", "lead_time_sensitivity", "emergency_purchase_allowed_flag", "substitutable_flag", "active_flag", "advisory_only_flag", "notes"},
        "requirements": {"requirement_id", "machine_id", "machine_type", "spare_part_sku", "maintenance_level", "quantity_per_light_maintenance", "quantity_per_medium_maintenance", "quantity_per_heavy_maintenance", "quantity_per_breakdown_repair", "expected_usage_basis", "criticality", "substitutable_flag", "active_flag", "advisory_only_flag", "notes"},
    }
    for name, columns in required.items():
        missing = sorted(columns.difference(frames[name].columns))
        checks.append(_result(f"spare_{name}_required_columns", f"{name} required columns", "FAIL" if missing else "PASS", f"Missing columns: {missing}" if missing else f"{name} has required columns.", len(missing)))

    spares = frames["spares"]
    req = frames["requirements"]
    machines = frames["machines"]
    products = frames["products"]
    supplier_sku = frames["supplier_sku"]
    inventory = frames["inventory"]

    duplicate_sku = int(spares["spare_part_sku"].astype(str).duplicated().sum())
    checks.append(_result("spare_part_sku_unique", "spare part SKU unique", "FAIL" if duplicate_sku else "PASS", f"Duplicate spare SKUs: {duplicate_sku}", duplicate_sku))
    _check_refs(req, "spare_part_sku", spares, "spare_part_sku", "spare_requirement_sku_refs", checks)
    _check_refs(req, "machine_id", machines, "machine_id", "spare_requirement_machine_refs", checks)
    _check_refs(spares, "spare_part_sku", products, "sku_id", "spare_phase1_product_refs", checks)

    invalid_types = spares[~spares["spare_part_type"].astype(str).isin(ALLOWED_TYPES)]
    invalid_crit = spares[~spares["criticality"].astype(str).isin(ALLOWED_CRITICALITY)]
    invalid_levels = req[~req["maintenance_level"].astype(str).isin(ALLOWED_MAINT_LEVELS)]
    invalid_basis = req[~req["expected_usage_basis"].astype(str).isin(ALLOWED_USAGE_BASIS)]
    checks.append(_result("spare_part_types_valid", "spare part types valid", "FAIL" if not invalid_types.empty else "PASS", "Spare part types are valid.", len(invalid_types)))
    checks.append(_result("spare_part_criticality_valid", "spare criticality valid", "FAIL" if not invalid_crit.empty else "PASS", "Spare criticality values are valid.", len(invalid_crit)))
    checks.append(_result("spare_maintenance_levels_valid", "spare maintenance levels valid", "FAIL" if not invalid_levels.empty else "PASS", "Maintenance levels are valid.", len(invalid_levels)))
    checks.append(_result("spare_usage_basis_valid", "spare usage basis valid", "FAIL" if not invalid_basis.empty else "PASS", "Usage basis values are valid.", len(invalid_basis)))

    _check_nonnegative(spares, ["unit_cost", "shelf_life_days"], "spare_master_numeric_nonnegative", checks, allow_blank={"shelf_life_days"})
    _check_nonnegative(req, ["quantity_per_light_maintenance", "quantity_per_medium_maintenance", "quantity_per_heavy_maintenance", "quantity_per_breakdown_repair"], "spare_requirement_quantities_nonnegative", checks)
    critical_unlinked = spares[spares["criticality"].astype(str).isin({"HIGH", "CRITICAL"}) & spares["linked_machine_type"].astype(str).str.strip().eq("") & spares["linked_machine_id"].astype(str).str.strip().eq("")]
    checks.append(_result("critical_spares_linked_to_machine_context", "critical spares linked to machine context", "FAIL" if not critical_unlinked.empty else "PASS", "Critical/high spare parts have linked machine type or machine id.", len(critical_unlinked)))
    if not _all_true(spares, "advisory_only_flag") or not _all_true(req, "advisory_only_flag"):
        checks.append(_result("spare_master_advisory_only", "spare master advisory-only", "FAIL", "Spare data advisory flags must be true.", 1))
    else:
        checks.append(_result("spare_master_advisory_only", "spare master advisory-only", "PASS", "Spare data advisory flags are true.", 0))

    critical_skus = set(spares.loc[spares["criticality"].astype(str) == "CRITICAL", "spare_part_sku"].astype(str))
    inv_skus = set(inventory["sku_id"].astype(str))
    supplier_skus = set(supplier_sku["sku_id"].astype(str))
    missing_inv = sorted(critical_skus - inv_skus)
    missing_supplier = sorted(critical_skus - supplier_skus)
    checks.append(_result("critical_spares_have_inventory_records", "critical spares have inventory records", "FAIL" if missing_inv else "PASS", f"Critical spare parts missing inventory records: {missing_inv}" if missing_inv else "Critical spare parts have inventory records.", len(missing_inv)))
    checks.append(_result("critical_spares_have_supplier_records", "critical spares have supplier records", "FAIL" if missing_supplier else "PASS", f"Critical spare parts missing supplier records: {missing_supplier}" if missing_supplier else "Critical spare parts have supplier coverage records.", len(missing_supplier)))


def _build_phase1_demand_context(spares: pd.DataFrame, demand: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in spares.itertuples():
        history = demand[demand["sku_id"].astype(str) == row.spare_part_sku].copy()
        qty = pd.to_numeric(history.get("quantity_demanded", pd.Series(dtype=float)), errors="coerce").fillna(0)
        active_weeks = history["date"].nunique() if not history.empty else 0
        total = float(qty.sum())
        avg_weekly = total / max(active_weeks, 1)
        rows.append({
            "spare_part_sku": row.spare_part_sku,
            "demand_rows": len(history),
            "total_historical_demand": total,
            "avg_weekly_demand": round(avg_weekly, 4),
            "intermittent_demand_flag": True,
            "source_phase": "PHASE1_SPARE_PART_DEMAND_CONTEXT",
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows)


def _build_phase3_inventory_check(spares: pd.DataFrame, requirements: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    linked = requirements.groupby("spare_part_sku", as_index=False).agg(linked_machine_count=("machine_id", "nunique"))
    frame = spares.merge(linked, on="spare_part_sku", how="left").merge(inventory, left_on="spare_part_sku", right_on="sku_id", how="left")
    frame["linked_machine_count"] = pd.to_numeric(frame["linked_machine_count"], errors="coerce").fillna(0).astype(int)
    frame["on_hand_qty"] = pd.to_numeric(frame["current_inventory"], errors="coerce")
    frame["available_qty"] = pd.to_numeric(frame["available_inventory"], errors="coerce")
    frame["reserved_qty"] = pd.to_numeric(frame["reserved_inventory"], errors="coerce")
    frame["safety_stock"] = frame["criticality"].map({"LOW": 1, "MEDIUM": 2, "HIGH": 4, "CRITICAL": 3}).fillna(1)
    frame["reorder_point"] = frame["criticality"].map({"LOW": 2, "MEDIUM": 4, "HIGH": 6, "CRITICAL": 5}).fillna(2)
    frame["inventory_status"] = frame.apply(_inventory_status, axis=1)
    frame["shortage_risk_flag"] = frame["inventory_status"].isin(["BELOW_SAFETY_STOCK", "BELOW_REORDER_POINT", "OUT_OF_STOCK", "NO_INVENTORY_RECORD", "REVIEW_REQUIRED"])
    frame["critical_shortage_flag"] = frame["criticality"].eq("CRITICAL") & frame["shortage_risk_flag"]
    frame["coverage_status"] = frame["inventory_status"].map({
        "SUFFICIENT": "COVERED",
        "BELOW_SAFETY_STOCK": "LIMITED_COVERAGE",
        "BELOW_REORDER_POINT": "LIMITED_COVERAGE",
        "OUT_OF_STOCK": "REVIEW_REQUIRED",
        "NO_INVENTORY_RECORD": "REVIEW_REQUIRED",
        "REVIEW_REQUIRED": "REVIEW_REQUIRED",
    })
    frame["planning_run_id"] = _planning_run_id()
    frame["source_phase"] = "PHASE3_SPARE_PART_INVENTORY_CHECK"
    frame["advisory_only_flag"] = True
    for column in ["on_hand_qty", "available_qty", "reserved_qty"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    return frame[["planning_run_id", "spare_part_sku", "spare_part_name", "linked_machine_count", "criticality", "on_hand_qty", "available_qty", "reserved_qty", "reorder_point", "safety_stock", "inventory_status", "shortage_risk_flag", "critical_shortage_flag", "coverage_status", "source_phase", "advisory_only_flag"]].copy()


def _build_phase2_supplier_check(spares: pd.DataFrame, supplier_sku: pd.DataFrame) -> pd.DataFrame:
    spare_supplier = supplier_sku[supplier_sku["sku_id"].astype(str).isin(set(spares["spare_part_sku"].astype(str)))].copy()
    for col in ["unit_cost", "lead_time_mean_days", "yield_rate"]:
        spare_supplier[col] = pd.to_numeric(spare_supplier[col], errors="coerce").fillna(0)
    grouped = spare_supplier.groupby("sku_id", as_index=False).agg(
        supplier_count=("supplier_id", "nunique"),
        preferred_supplier_id=("supplier_id", "first"),
        best_supplier_score=("yield_rate", "max"),
        min_lead_time_days=("lead_time_mean_days", "min"),
        min_unit_cost=("unit_cost", "min"),
        emergency_supplier_available_flag=("expedite_eligible", lambda s: bool(_to_bool(s).any())),
    )
    frame = spares.merge(grouped, left_on="spare_part_sku", right_on="sku_id", how="left")
    frame["supplier_count"] = pd.to_numeric(frame["supplier_count"], errors="coerce").fillna(0).astype(int)
    frame["best_supplier_score"] = pd.to_numeric(frame["best_supplier_score"], errors="coerce").fillna(0)
    frame["min_lead_time_days"] = pd.to_numeric(frame["min_lead_time_days"], errors="coerce").fillna(0)
    frame["min_unit_cost"] = pd.to_numeric(frame["min_unit_cost"], errors="coerce").fillna(0)
    frame["emergency_supplier_available_flag"] = frame["emergency_supplier_available_flag"].fillna(False)
    frame["supplier_coverage_status"] = frame["supplier_count"].map(lambda count: "NO_SUPPLIER_COVERAGE" if count == 0 else ("LIMITED_COVERAGE" if count == 1 else "COVERED"))
    frame["critical_supplier_gap_flag"] = frame["criticality"].eq("CRITICAL") & frame["supplier_coverage_status"].isin(["NO_SUPPLIER_COVERAGE", "REVIEW_REQUIRED"])
    frame["planning_run_id"] = _planning_run_id()
    frame["source_phase"] = "PHASE2_SPARE_PART_SUPPLIER_CHECK"
    frame["advisory_only_flag"] = True
    return frame[["planning_run_id", "spare_part_sku", "spare_part_name", "supplier_count", "preferred_supplier_id", "best_supplier_score", "min_lead_time_days", "min_unit_cost", "emergency_supplier_available_flag", "supplier_coverage_status", "critical_supplier_gap_flag", "source_phase", "advisory_only_flag"]].copy()


def _build_machine_requirement_context(spares: pd.DataFrame, req: pd.DataFrame) -> pd.DataFrame:
    frame = req.merge(spares[["spare_part_sku", "spare_part_name"]], on="spare_part_sku", how="left")
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[["spare_part_sku", "spare_part_name", "machine_id", "machine_type", "maintenance_level", "quantity_per_light_maintenance", "quantity_per_medium_maintenance", "quantity_per_heavy_maintenance", "quantity_per_breakdown_repair", "criticality", "source_phase", "advisory_only_flag"]].copy()


def _build_phase_integration_context(spares: pd.DataFrame, req: pd.DataFrame, demand: pd.DataFrame, inventory: pd.DataFrame, supplier: pd.DataFrame) -> pd.DataFrame:
    linked = req.groupby("spare_part_sku", as_index=False).agg(linked_machine_count=("machine_id", "nunique"))
    frame = spares.merge(linked, on="spare_part_sku", how="left")
    frame = frame.merge(demand[["spare_part_sku", "demand_rows"]], on="spare_part_sku", how="left")
    frame = frame.merge(inventory[["spare_part_sku", "inventory_status"]], on="spare_part_sku", how="left")
    frame = frame.merge(supplier[["spare_part_sku", "supplier_coverage_status"]], on="spare_part_sku", how="left")
    frame["linked_machine_count"] = pd.to_numeric(frame["linked_machine_count"], errors="coerce").fillna(0).astype(int)
    frame["phase1_demand_context_available_flag"] = pd.to_numeric(frame["demand_rows"], errors="coerce").fillna(0) > 0
    frame["phase2_supplier_context_available_flag"] = frame["supplier_coverage_status"].notna() & ~frame["supplier_coverage_status"].isin(["NO_SUPPLIER_COVERAGE"])
    frame["phase3_inventory_context_available_flag"] = frame["inventory_status"].notna() & ~frame["inventory_status"].isin(["NO_INVENTORY_RECORD"])
    frame["integration_status"] = frame.apply(_integration_status, axis=1)
    frame["integration_review_required_flag"] = frame["integration_status"] != "FULLY_INTEGRATED"
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[["spare_part_sku", "spare_part_name", "criticality", "phase1_demand_context_available_flag", "phase2_supplier_context_available_flag", "phase3_inventory_context_available_flag", "linked_machine_count", "supplier_coverage_status", "inventory_status", "integration_status", "integration_review_required_flag", "source_phase", "advisory_only_flag"]].copy()


def _build_phase4_spare_part_context(spares: pd.DataFrame, req: pd.DataFrame, machines: pd.DataFrame, inventory: pd.DataFrame, supplier: pd.DataFrame) -> pd.DataFrame:
    frame = req.merge(machines[["machine_id", "machine_name"]], on="machine_id", how="left")
    frame = frame.merge(spares[["spare_part_sku", "spare_part_name", "spare_part_type"]], on="spare_part_sku", how="left")
    frame = frame.merge(inventory[["spare_part_sku", "inventory_status"]], on="spare_part_sku", how="left")
    frame = frame.merge(supplier[["spare_part_sku", "supplier_coverage_status"]], on="spare_part_sku", how="left")
    frame["spare_part_readiness_status"] = frame.apply(_readiness_status, axis=1)
    frame["maintenance_planning_ready_flag"] = frame["spare_part_readiness_status"].eq("READY")
    frame["planning_run_id"] = _planning_run_id()
    frame["source_phase"] = "PHASE4_STEP7B_SPARE_PART_REQUIREMENT_CONTEXT"
    frame["advisory_only_flag"] = True
    return frame[["planning_run_id", "machine_id", "machine_type", "machine_name", "spare_part_sku", "spare_part_name", "spare_part_type", "criticality", "quantity_per_light_maintenance", "quantity_per_medium_maintenance", "quantity_per_heavy_maintenance", "quantity_per_breakdown_repair", "inventory_status", "supplier_coverage_status", "spare_part_readiness_status", "maintenance_planning_ready_flag", "source_phase", "advisory_only_flag"]].copy()


def _build_manager_review_queue(integration: pd.DataFrame, inventory: pd.DataFrame, supplier: pd.DataFrame, spares: pd.DataFrame) -> pd.DataFrame:
    rows = []
    item = 1
    merged = integration.merge(spares[["spare_part_sku", "spare_part_name"]], on="spare_part_sku", how="left", suffixes=("", "_master"))
    for row in merged.itertuples():
        name = row.spare_part_name if pd.notna(row.spare_part_name) else getattr(row, "spare_part_name_master", "")
        if row.linked_machine_count == 0:
            rows.append(_review_row(item, row.spare_part_sku, name, "MISSING_MACHINE_LINK", "HIGH", "Spare part has no machine requirement link.", "LINK_SPARE_PART_TO_MACHINE"))
            item += 1
        if not row.phase1_demand_context_available_flag:
            rows.append(_review_row(item, row.spare_part_sku, name, "MISSING_DEMAND_CONTEXT", "MEDIUM", "Spare part has no Phase 1 demand context.", "REVIEW_SPARE_PART_DEMAND_HISTORY"))
            item += 1
        if not row.phase3_inventory_context_available_flag:
            rows.append(_review_row(item, row.spare_part_sku, name, "MISSING_INVENTORY_CONTEXT", "HIGH", "Spare part has no Phase 3 inventory context.", "ADD_OR_REVIEW_SPARE_PART_INVENTORY"))
            item += 1
        if not row.phase2_supplier_context_available_flag:
            rows.append(_review_row(item, row.spare_part_sku, name, "MISSING_SUPPLIER_CONTEXT", "HIGH", "Spare part has no Phase 2 supplier context.", "ADD_OR_REVIEW_SPARE_PART_SUPPLIERS"))
            item += 1
    inv_risk = inventory[inventory["critical_shortage_flag"]]
    for row in inv_risk.itertuples():
        rows.append(_review_row(item, row.spare_part_sku, row.spare_part_name, "CRITICAL_SPARE_PART_LOW_STOCK", "CRITICAL", f"Critical spare part inventory status is {row.inventory_status}.", "REVIEW_CRITICAL_SPARE_STOCK"))
        item += 1
    supplier_gap = supplier[supplier["critical_supplier_gap_flag"]]
    for row in supplier_gap.itertuples():
        rows.append(_review_row(item, row.spare_part_sku, row.spare_part_name, "CRITICAL_SPARE_PART_NO_SUPPLIER", "CRITICAL", "Critical spare part lacks supplier coverage.", "REVIEW_CRITICAL_SPARE_SUPPLIER"))
        item += 1
    return pd.DataFrame(rows, columns=["review_item_id", "spare_part_sku", "spare_part_name", "issue_type", "issue_severity", "issue_description", "recommended_review_action", "auto_action_allowed", "advisory_only_flag"])


def _validate_context_outputs(demand: pd.DataFrame, supplier: pd.DataFrame, inventory: pd.DataFrame, requirement: pd.DataFrame, integration: pd.DataFrame, review: pd.DataFrame, phase4: pd.DataFrame, checks: list[dict]) -> None:
    frames = [(demand, "phase1 demand"), (supplier, "phase2 supplier"), (inventory, "phase3 inventory"), (requirement, "machine requirement"), (integration, "phase integration"), (phase4, "phase4 context")]
    empty_count = sum(int(frame.empty) for frame, _ in frames)
    bad_advisory = sum(int((~_to_bool(frame["advisory_only_flag"])).sum()) if "advisory_only_flag" in frame.columns else len(frame) for frame, _ in frames)
    if not review.empty:
        bad_advisory += int((~_to_bool(review["advisory_only_flag"])).sum())
        bad_advisory += int(_to_bool(review["auto_action_allowed"]).sum())
    invalid_status = int((~inventory["inventory_status"].astype(str).isin(INVENTORY_STATUSES)).sum())
    invalid_status += int((~supplier["supplier_coverage_status"].astype(str).isin(SUPPLIER_STATUSES)).sum())
    invalid_status += int((~integration["integration_status"].astype(str).isin(INTEGRATION_STATUSES)).sum())
    affected = empty_count + bad_advisory + invalid_status
    checks.append(_result("spare_part_context_outputs_valid", "spare part context outputs valid", "FAIL" if affected else "PASS", "Spare part context outputs are valid and advisory-only." if not affected else f"Invalid spare-part context output values: {affected}", affected))


def _inventory_status(row: pd.Series) -> str:
    if pd.isna(row.get("sku_id")):
        return "NO_INVENTORY_RECORD"
    available = pd.to_numeric(row.get("available_qty"), errors="coerce")
    if pd.isna(available):
        return "REVIEW_REQUIRED"
    if available <= 0:
        return "OUT_OF_STOCK"
    if available < float(row.get("safety_stock", 0)):
        return "BELOW_SAFETY_STOCK"
    if available < float(row.get("reorder_point", 0)):
        return "BELOW_REORDER_POINT"
    return "SUFFICIENT"


def _integration_status(row: pd.Series) -> str:
    if not row.get("phase1_demand_context_available_flag", False):
        return "MISSING_DEMAND_CONTEXT"
    if not row.get("phase3_inventory_context_available_flag", False):
        return "MISSING_INVENTORY_CONTEXT"
    if not row.get("phase2_supplier_context_available_flag", False):
        return "MISSING_SUPPLIER_CONTEXT"
    if row.get("inventory_status") != "SUFFICIENT" or row.get("supplier_coverage_status") not in {"COVERED", "LIMITED_COVERAGE"}:
        return "PARTIAL_INTEGRATION_REVIEW"
    return "FULLY_INTEGRATED"


def _readiness_status(row: pd.Series) -> str:
    inventory_ok = row.get("inventory_status") == "SUFFICIENT"
    supplier_ok = row.get("supplier_coverage_status") in {"COVERED", "LIMITED_COVERAGE"}
    if inventory_ok and supplier_ok:
        return "READY"
    if not inventory_ok and not supplier_ok:
        return "INVENTORY_AND_SUPPLIER_REVIEW_REQUIRED"
    if not inventory_ok:
        return "INVENTORY_REVIEW_REQUIRED"
    if not supplier_ok:
        return "SUPPLIER_REVIEW_REQUIRED"
    return "REVIEW_REQUIRED"


def _review_row(item: int, sku: str, name: str, issue_type: str, severity: str, description: str, action: str) -> dict:
    return {
        "review_item_id": f"SP-REV-{item:04d}",
        "spare_part_sku": sku,
        "spare_part_name": name,
        "issue_type": issue_type,
        "issue_severity": severity,
        "issue_description": description,
        "recommended_review_action": action,
        "auto_action_allowed": False,
        "advisory_only_flag": True,
    }


def _check_refs(child: pd.DataFrame, child_column: str, parent: pd.DataFrame, parent_column: str, check_id: str, checks: list[dict]) -> None:
    missing = sorted(set(child[child_column].dropna().astype(str)) - set(parent[parent_column].dropna().astype(str)))
    checks.append(_result(check_id, f"{child_column} references valid", "FAIL" if missing else "PASS", f"Missing references: {missing}" if missing else f"{child_column} references are valid.", len(missing)))


def _check_nonnegative(df: pd.DataFrame, columns: list[str], check_id: str, checks: list[dict], allow_blank: set[str] | None = None) -> None:
    allow_blank = allow_blank or set()
    bad = 0
    for column in columns:
        series = df[column]
        if column in allow_blank:
            series = series.replace("", pd.NA)
            values = pd.to_numeric(series.dropna(), errors="coerce")
            bad += int(values.isna().sum()) + int((values < 0).sum())
        else:
            values = pd.to_numeric(series, errors="coerce")
            bad += int(values.isna().sum()) + int((values < 0).sum())
    checks.append(_result(check_id, "numeric fields non-negative", "FAIL" if bad else "PASS", f"Invalid numeric values: {bad}" if bad else "Numeric fields are non-negative.", bad))


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked_tokens = ["spare_part_consumption", "inventory_reservation", "purchase_order", "maintenance_work_order", "finite_schedule", "dispatch_schedule", "crew_schedule", "simulation"]
    bad = []
    for folder in [OUTPUT_DIR, PHASE2_DIR / "outputs", PHASE3_DIR / "outputs", PHASE4_OUTPUT_DIR]:
        if not folder.exists():
            continue
        for path in folder.glob("*"):
            if path.is_file() and any(token in path.name.lower() for token in blocked_tokens):
                bad.append(str(path))
    checks.append(_result("spare_no_blocked_outputs", "no spare-part blocked outputs", "FAIL" if bad else "PASS", f"Blocked scheduling/execution outputs found: {bad}" if bad else "No spare-part consumption, reservation, work-order, scheduling, or simulation outputs found.", len(bad)))


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
    return f"SHARED-SPARE-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


def _load_csv(path: Path, name: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"spare_{name}_exists", f"{name} exists", "FAIL", f"Missing file: {path}", 1))
        return None
    frame = pd.read_csv(path, keep_default_na=False)
    checks.append(_result(f"spare_{name}_exists", f"{name} exists", "PASS", f"Loaded {path}", 0))
    if frame.empty:
        checks.append(_result(f"spare_{name}_not_empty", f"{name} not empty", "FAIL", f"{name} has no rows.", 1))
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
    validation, *_ = build_spare_part_master_data_outputs()
    print(f"Spare-part validation rows: {len(validation)}")
    print(f"Spare-part validation status counts: {validation['status'].value_counts().to_dict() if not validation.empty else {}}")
