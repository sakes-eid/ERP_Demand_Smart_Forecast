"""Create a clean Phase 4 Step 7C maintenance master review bundle."""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PHASE4_OUTPUTS = PROJECT_ROOT / "phase 4" / "outputs"
ZIP_PATH = PROJECT_ROOT / "phase4_step7c_maintenance_master_review_bundle.zip"
MANIFEST_PATH = PHASE4_OUTPUTS / "phase4_review_bundle_manifest.txt"

REQUIRED_RELATIVE_FILES = [
    ".gitignore",
    "planning_orchestrator.py",
    "shared/validation/integrated_validation_evidence.json",
    "shared/validation/integrated_validation_report.txt",
    "shared/data/workforce_crews.csv",
    "shared/data/workforce_skills.csv",
    "shared/data/crew_skill_matrix.csv",
    "shared/data/crew_machine_authorizations.csv",
    "shared/data/spare_parts_master.csv",
    "shared/data/machine_spare_part_requirements.csv",
    "shared/data/maintenance_plans.csv",
    "shared/data/maintenance_plan_spare_parts.csv",
    "shared/data/machine_maintenance_state.csv",
    "shared/data/crew_calendar.csv",
    "shared/data/crew_cost_rates.csv",
    "shared/core/workforce_master_data.py",
    "shared/core/spare_parts_master_data.py",
    "shared/core/maintenance_master_data.py",
    "shared/outputs/workforce_crew_validation.csv",
    "shared/outputs/workforce_crew_capacity_context.csv",
    "shared/outputs/workforce_machine_authorization_context.csv",
    "shared/outputs/workforce_skill_coverage_summary.csv",
    "shared/outputs/workforce_manager_review_queue.csv",
    "shared/outputs/spare_part_validation.csv",
    "shared/outputs/spare_part_machine_requirement_context.csv",
    "shared/outputs/spare_part_phase_integration_context.csv",
    "shared/outputs/spare_part_manager_review_queue.csv",
    "shared/outputs/maintenance_plan_validation.csv",
    "shared/outputs/maintenance_due_status_context.csv",
    "shared/outputs/maintenance_spare_part_requirement_context.csv",
    "shared/outputs/maintenance_cost_downtime_context.csv",
    "shared/outputs/maintenance_manager_review_queue.csv",
    "phase 4/README.md",
    "phase 4/main.py",
    "phase 4/validate_phase4_initialization.py",
    "phase 4/create_phase4_review_bundle.py",
    "phase 4/data/phase4_bom.csv",
    "phase 4/data/workstations.csv",
    "phase 4/data/machines.csv",
    "phase 4/data/labor_resources.csv",
    "phase 4/data/resource_calendar.csv",
    "phase 4/data/product_routings.csv",
    "phase 4/data/routing_parallel_groups.csv",
    "phase 4/data/routing_operation_resources.csv",
    "phase 4/data/quality_history.csv",
    "phase 4/data/quality_rules.csv",
    "phase 4/data/rework_rules.csv",
    "phase 4/core/bom_explosion_bridge.py",
    "phase 4/core/component_inventory_bridge.py",
    "phase 4/core/component_supplier_bridge.py",
    "phase 4/core/master_production_schedule.py",
    "phase 4/core/mrp_net_requirements.py",
    "phase 4/core/resource_master_data.py",
    "phase 4/core/routing_master_data.py",
    "phase 4/core/capacity_load.py",
    "phase 4/core/queue_pressure.py",
    "phase 4/core/bottleneck_visibility.py",
    "phase 4/core/production_flow_view.py",
    "phase 4/core/quality_trends.py",
    "phase 4/core/quality_adjusted_capacity.py",
    "phase 4/outputs/phase4_master_production_schedule.csv",
    "phase 4/outputs/phase4_bom_component_requirements.csv",
    "phase 4/outputs/phase4_mrp_net_component_requirements.csv",
    "phase 4/outputs/phase4_mrp_component_period_summary.csv",
    "phase 4/outputs/phase4_mrp_pegging_detail.csv",
    "phase 4/outputs/phase4_resource_validation.csv",
    "phase 4/outputs/phase4_workforce_resource_context.csv",
    "phase 4/outputs/phase4_spare_part_requirement_context.csv",
    "phase 4/outputs/phase4_maintenance_readiness_context.csv",
    "phase 4/outputs/phase4_routing_validation.csv",
    "phase 4/outputs/phase4_routing_flow_summary.csv",
    "phase 4/outputs/phase4_capacity_load_by_workstation.csv",
    "phase 4/outputs/phase4_capacity_operation_load_detail.csv",
    "phase 4/outputs/phase4_capacity_load_by_machine_type.csv",
    "phase 4/outputs/phase4_capacity_load_by_labor_skill.csv",
    "phase 4/outputs/phase4_capacity_constraint_bridge.csv",
    "phase 4/outputs/phase4_capacity_feasibility_summary.csv",
    "phase 4/outputs/phase4_bottleneck_candidate_summary.csv",
    "phase 4/outputs/phase4_capacity_manager_review_queue.csv",
    "phase 4/outputs/phase4_capacity_validation.csv",
    "phase 4/outputs/phase4_queue_pressure_by_workstation.csv",
    "phase 4/outputs/phase4_queue_risk_summary.csv",
    "phase 4/outputs/phase4_queue_manager_review_queue.csv",
    "phase 4/outputs/phase4_queue_validation.csv",
    "phase 4/outputs/phase4_bottleneck_visibility_summary.csv",
    "phase 4/outputs/phase4_bottleneck_period_evidence.csv",
    "phase 4/outputs/phase4_bottleneck_manager_review_queue.csv",
    "phase 4/outputs/phase4_bottleneck_validation.csv",
    "phase 4/outputs/phase4_production_flow_view.csv",
    "phase 4/outputs/phase4_flow_step_risk_summary.csv",
    "phase 4/outputs/phase4_flow_manager_review_queue.csv",
    "phase 4/outputs/phase4_flow_validation.csv",
    "phase 4/outputs/phase4_quality_history_clean.csv",
    "phase 4/outputs/phase4_quality_trend_by_operation.csv",
    "phase 4/outputs/phase4_quality_trend_by_workstation.csv",
    "phase 4/outputs/phase4_processing_time_trend_by_workstation.csv",
    "phase 4/outputs/phase4_workstation_performance_trend_summary.csv",
    "phase 4/outputs/phase4_quality_manager_review_queue.csv",
    "phase 4/outputs/phase4_quality_validation.csv",
    "phase 4/outputs/phase4_quality_impact_by_operation.csv",
    "phase 4/outputs/phase4_quality_adjusted_capacity_by_workstation.csv",
    "phase 4/outputs/phase4_quality_adjusted_bottleneck_impact.csv",
    "phase 4/outputs/phase4_quality_material_loss_exposure.csv",
    "phase 4/outputs/phase4_quality_impact_manager_review_queue.csv",
    "phase 4/outputs/phase4_quality_adjusted_capacity_validation.csv",
    "phase 4/outputs/phase4_initialization_validation.json",
    "phase 4/outputs/phase4_initialization_validation_report.txt",
    "phase 4/outputs/phase4_review_bundle_manifest.txt",
    "phase 1/core/data_loader.py",
    "phase 1/data/products.csv",
    "phase 1/data/demand_history.csv",
    "phase 1/outputs/phase1_spare_part_demand_context.csv",
    "phase 1/outputs/future_forecast_results.csv",
    "phase 1/outputs/phase1_demand_context_validation_report.txt",
    "phase 1/outputs/phase1_demand_context_validation_summary.csv",
    "phase 2/main.py",
    "phase 2/data/supplier_sku.csv",
    "phase 2/outputs/phase4_component_supplier_check.csv",
    "phase 2/outputs/phase4_spare_part_supplier_check.csv",
    "phase 2/outputs/phase2_procurement_validation_summary.csv",
    "phase 2/outputs/phase2_procurement_validation_report.txt",
    "phase 2/outputs/phase2_validation_report.txt",
    "phase 3/main.py",
    "phase 3/data/inventory.csv",
    "phase 3/data/sku_storage_requirements.csv",
    "phase 3/outputs/phase4_component_inventory_check.csv",
    "phase 3/outputs/phase4_spare_part_inventory_check.csv",
    "phase 3/outputs/phase3_validation_summary.csv",
    "phase 3/outputs/phase3_validation_report.txt",
]

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".pytest_cache",
    "__pycache__",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip", ".tmp", ".bak"}
OPTIONAL_RELATIVE_FILES = {
    "phase 2/outputs/phase2_validation_report.txt",
}


def main() -> None:
    PHASE4_OUTPUTS.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    included, missing, excluded = _collect_files()

    provisional = _build_manifest(
        generated_at=generated_at,
        included=included,
        missing=missing,
        excluded=excluded,
        verification_status="PENDING",
        verification_messages=["Verification pending until zip is written."],
    )
    MANIFEST_PATH.write_text(provisional, encoding="utf-8")
    if MANIFEST_PATH.relative_to(PROJECT_ROOT).as_posix() not in included:
        included.append(MANIFEST_PATH.relative_to(PROJECT_ROOT).as_posix())
        missing = [item for item in missing if item != MANIFEST_PATH.relative_to(PROJECT_ROOT).as_posix()]

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel_path in included:
            archive.write(PROJECT_ROOT / rel_path, arcname=rel_path)

    verification_status, verification_messages = _verify_zip()
    final_manifest = _build_manifest(
        generated_at=generated_at,
        included=included,
        missing=missing,
        excluded=excluded,
        verification_status=verification_status,
        verification_messages=verification_messages,
    )
    MANIFEST_PATH.write_text(final_manifest, encoding="utf-8")
    _replace_manifest_in_zip()

    zip_size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"Zip path: {ZIP_PATH}")
    print(f"Zip size MB: {zip_size_mb:.3f}")
    print(f"Included file count: {len(included)}")
    print(f"Missing file count: {len(missing)}")
    print(f"Verification status: {verification_status}")
    if missing:
        print("Missing files:")
        for item in missing:
            print(f"- {item}")


def _collect_files() -> tuple[list[str], list[str], list[str]]:
    included = []
    missing = []
    excluded = []
    for rel_path in REQUIRED_RELATIVE_FILES:
        normalized = rel_path.replace("\\", "/")
        if _is_excluded(normalized):
            excluded.append(normalized)
            continue
        path = PROJECT_ROOT / normalized
        if path.exists() and path.is_file():
            included.append(normalized)
        elif normalized in OPTIONAL_RELATIVE_FILES:
            continue
        else:
            missing.append(normalized)
    return included, missing, excluded


def _is_excluded(rel_path: str) -> bool:
    path = Path(rel_path)
    parts = set(path.parts)
    if parts & EXCLUDED_PARTS:
        return True
    lower = rel_path.lower()
    return any(lower.endswith(suffix) for suffix in EXCLUDED_SUFFIXES)


def _verify_zip() -> tuple[str, list[str]]:
    messages = []
    status = "PASS"
    with zipfile.ZipFile(ZIP_PATH, "r") as archive:
        names = archive.namelist()
    name_set = set(names)

    required_checks = {
        "shared/data/spare_parts_master.csv": "Shared spare-parts master data exists inside the zip",
        "shared/data/machine_spare_part_requirements.csv": "Shared machine spare-part requirements data exists inside the zip",
        "shared/core/spare_parts_master_data.py": "Shared spare-parts master data module exists inside the zip",
        "shared/outputs/spare_part_validation.csv": "Shared spare-part validation output exists inside the zip",
        "shared/outputs/spare_part_machine_requirement_context.csv": "Shared spare-part machine requirement context exists inside the zip",
        "shared/outputs/spare_part_phase_integration_context.csv": "Shared spare-part phase integration context exists inside the zip",
        "shared/outputs/spare_part_manager_review_queue.csv": "Shared spare-part manager review queue exists inside the zip",
        "shared/data/maintenance_plans.csv": "Shared maintenance plans data exists inside the zip",
        "shared/data/maintenance_plan_spare_parts.csv": "Shared maintenance plan spare-parts data exists inside the zip",
        "shared/data/machine_maintenance_state.csv": "Shared machine maintenance state data exists inside the zip",
        "shared/core/maintenance_master_data.py": "Shared maintenance master data module exists inside the zip",
        "shared/outputs/maintenance_plan_validation.csv": "Shared maintenance validation output exists inside the zip",
        "shared/outputs/maintenance_due_status_context.csv": "Shared maintenance due-status context exists inside the zip",
        "shared/outputs/maintenance_spare_part_requirement_context.csv": "Shared maintenance spare-part requirement context exists inside the zip",
        "shared/outputs/maintenance_cost_downtime_context.csv": "Shared maintenance cost/downtime context exists inside the zip",
        "shared/outputs/maintenance_manager_review_queue.csv": "Shared maintenance manager review queue exists inside the zip",
        "phase 4/outputs/phase4_maintenance_readiness_context.csv": "Phase 4 maintenance readiness context exists inside the zip",
        "phase 1/outputs/phase1_spare_part_demand_context.csv": "Phase 1 spare-part demand context exists inside the zip",
        "phase 2/outputs/phase4_spare_part_supplier_check.csv": "Phase 2 spare-part supplier check exists inside the zip",
        "phase 3/outputs/phase4_spare_part_inventory_check.csv": "Phase 3 spare-part inventory check exists inside the zip",
        "phase 4/outputs/phase4_spare_part_requirement_context.csv": "Phase 4 spare-part requirement context exists inside the zip",
        "shared/data/workforce_crews.csv": "Shared workforce crews data exists inside the zip",
        "shared/data/workforce_skills.csv": "Shared workforce skills data exists inside the zip",
        "shared/data/crew_skill_matrix.csv": "Shared crew skill matrix exists inside the zip",
        "shared/data/crew_machine_authorizations.csv": "Shared crew machine authorizations exists inside the zip",
        "shared/core/workforce_master_data.py": "Shared workforce master data module exists inside the zip",
        "shared/outputs/workforce_crew_validation.csv": "Shared workforce validation output exists inside the zip",
        "shared/outputs/workforce_crew_capacity_context.csv": "Shared workforce crew capacity context exists inside the zip",
        "shared/outputs/workforce_machine_authorization_context.csv": "Shared workforce machine authorization context exists inside the zip",
        "shared/outputs/workforce_skill_coverage_summary.csv": "Shared workforce skill coverage summary exists inside the zip",
        "shared/outputs/workforce_manager_review_queue.csv": "Shared workforce manager review queue exists inside the zip",
        "phase 4/outputs/phase4_workforce_resource_context.csv": "Phase 4 workforce resource context exists inside the zip",
        "phase 4/data/quality_history.csv": "Phase 4 quality history seed data exists inside the zip",
        "phase 4/data/quality_rules.csv": "Phase 4 quality rules seed data exists inside the zip",
        "phase 4/data/rework_rules.csv": "Phase 4 rework rules seed data exists inside the zip",
        "phase 4/core/quality_trends.py": "Phase 4 quality trend module exists inside the zip",
        "phase 4/outputs/phase4_quality_history_clean.csv": "Phase 4 clean quality history output exists inside the zip",
        "phase 4/outputs/phase4_quality_trend_by_operation.csv": "Phase 4 operation quality trend output exists inside the zip",
        "phase 4/outputs/phase4_quality_trend_by_workstation.csv": "Phase 4 workstation quality trend output exists inside the zip",
        "phase 4/outputs/phase4_processing_time_trend_by_workstation.csv": "Phase 4 processing time trend output exists inside the zip",
        "phase 4/outputs/phase4_workstation_performance_trend_summary.csv": "Phase 4 workstation performance trend summary exists inside the zip",
        "phase 4/outputs/phase4_quality_manager_review_queue.csv": "Phase 4 quality manager review queue exists inside the zip",
        "phase 4/outputs/phase4_quality_validation.csv": "Phase 4 quality validation output exists inside the zip",
        "phase 4/core/quality_adjusted_capacity.py": "Phase 4 quality-adjusted capacity module exists inside the zip",
        "phase 4/outputs/phase4_quality_impact_by_operation.csv": "Phase 4 quality impact by operation output exists inside the zip",
        "phase 4/outputs/phase4_quality_adjusted_capacity_by_workstation.csv": "Phase 4 quality-adjusted capacity output exists inside the zip",
        "phase 4/outputs/phase4_quality_adjusted_bottleneck_impact.csv": "Phase 4 quality-adjusted bottleneck impact output exists inside the zip",
        "phase 4/outputs/phase4_quality_material_loss_exposure.csv": "Phase 4 quality material loss exposure output exists inside the zip",
        "phase 4/outputs/phase4_quality_impact_manager_review_queue.csv": "Phase 4 quality impact manager review queue exists inside the zip",
        "phase 4/outputs/phase4_quality_adjusted_capacity_validation.csv": "Phase 4 quality-adjusted capacity validation exists inside the zip",
        "phase 4/core/production_flow_view.py": "Phase 4 production flow view module exists inside the zip",
        "phase 4/outputs/phase4_production_flow_view.csv": "Phase 4 production flow view exists inside the zip",
        "phase 4/outputs/phase4_flow_step_risk_summary.csv": "Phase 4 flow-step risk summary exists inside the zip",
        "phase 4/outputs/phase4_flow_manager_review_queue.csv": "Phase 4 flow manager review queue exists inside the zip",
        "phase 4/outputs/phase4_flow_validation.csv": "Phase 4 flow validation output exists inside the zip",
        "phase 4/core/bottleneck_visibility.py": "Phase 4 bottleneck visibility module exists inside the zip",
        "phase 4/outputs/phase4_bottleneck_visibility_summary.csv": "Phase 4 bottleneck visibility summary exists inside the zip",
        "phase 4/outputs/phase4_bottleneck_period_evidence.csv": "Phase 4 bottleneck period evidence exists inside the zip",
        "phase 4/outputs/phase4_bottleneck_manager_review_queue.csv": "Phase 4 bottleneck manager review queue exists inside the zip",
        "phase 4/outputs/phase4_bottleneck_validation.csv": "Phase 4 bottleneck validation output exists inside the zip",
        "phase 4/core/capacity_load.py": "Phase 4 capacity load module exists inside the zip",
        "phase 4/core/queue_pressure.py": "Phase 4 queue pressure module exists inside the zip",
        "phase 4/outputs/phase4_capacity_load_by_machine_type.csv": "Phase 4 machine-type capacity output exists inside the zip",
        "phase 4/outputs/phase4_capacity_load_by_labor_skill.csv": "Phase 4 labor-skill capacity output exists inside the zip",
        "phase 4/outputs/phase4_capacity_constraint_bridge.csv": "Phase 4 capacity constraint bridge exists inside the zip",
        "phase 4/outputs/phase4_capacity_feasibility_summary.csv": "Phase 4 capacity feasibility summary exists inside the zip",
        "phase 4/outputs/phase4_bottleneck_candidate_summary.csv": "Phase 4 bottleneck candidate summary exists inside the zip",
        "phase 4/outputs/phase4_capacity_manager_review_queue.csv": "Phase 4 capacity manager review queue exists inside the zip",
        "phase 4/outputs/phase4_queue_pressure_by_workstation.csv": "Phase 4 queue pressure output exists inside the zip",
        "phase 4/outputs/phase4_queue_risk_summary.csv": "Phase 4 queue risk summary exists inside the zip",
        "phase 4/outputs/phase4_queue_manager_review_queue.csv": "Phase 4 queue manager review queue exists inside the zip",
        "phase 4/outputs/phase4_queue_validation.csv": "Phase 4 queue validation output exists inside the zip",
        "phase 4/outputs/phase4_capacity_load_by_workstation.csv": "Phase 4 workstation capacity load output exists inside the zip",
        "phase 4/outputs/phase4_capacity_validation.csv": "Phase 4 capacity validation output exists inside the zip",
        "phase 4/outputs/phase4_capacity_operation_load_detail.csv": "Phase 4 capacity operation detail output exists inside the zip",
        "phase 4/data/product_routings.csv": "Phase 4 product routings master exists inside the zip",
        "phase 4/data/routing_parallel_groups.csv": "Phase 4 routing parallel groups master exists inside the zip",
        "phase 4/data/routing_operation_resources.csv": "Phase 4 routing operation resources master exists inside the zip",
        "phase 4/core/routing_master_data.py": "Phase 4 routing validation module exists inside the zip",
        "phase 4/outputs/phase4_routing_validation.csv": "Phase 4 routing validation output exists inside the zip",
        "phase 4/outputs/phase4_routing_flow_summary.csv": "Phase 4 routing flow summary exists inside the zip",
        "phase 4/data/workstations.csv": "Phase 4 workstations master exists inside the zip",
        "phase 4/data/machines.csv": "Phase 4 machines master exists inside the zip",
        "phase 4/data/labor_resources.csv": "Phase 4 labor resources master exists inside the zip",
        "phase 4/data/resource_calendar.csv": "Phase 4 resource calendar exists inside the zip",
        "phase 4/core/resource_master_data.py": "Phase 4 resource validation module exists inside the zip",
        "phase 4/outputs/phase4_resource_validation.csv": "Phase 4 resource validation output exists inside the zip",
        "phase 4/outputs/phase4_mrp_component_period_summary.csv": "Phase 4 MRP component-period summary exists inside the zip",
        "phase 4/outputs/phase4_mrp_pegging_detail.csv": "Phase 4 MRP pegging detail exists inside the zip",
        "phase 4/core/mrp_net_requirements.py": "Phase 4 MRP net requirements builder exists inside the zip",
        "phase 4/outputs/phase4_mrp_net_component_requirements.csv": "Phase 4 MRP net requirements output exists inside the zip",
        "phase 4/core/master_production_schedule.py": "Phase 4 MPS builder exists inside the zip",
        "phase 4/outputs/phase4_master_production_schedule.csv": "Phase 4 MPS output exists inside the zip",
        "phase 4/core/bom_explosion_bridge.py": "Phase 4 BOM bridge exists inside the zip",
        "phase 2/main.py": "phase 2/main.py exists inside the zip",
        "phase 3/main.py": "phase 3/main.py exists inside the zip",
        "planning_orchestrator.py": "planning_orchestrator.py exists inside the zip",
        ".gitignore": ".gitignore exists inside the zip",
        "phase 4/outputs/phase4_bom_component_requirements.csv": "Phase 4 BOM requirements output exists inside the zip",
        "phase 4/outputs/phase4_initialization_validation.json": "Phase 4 validation JSON exists inside the zip",
        "phase 4/outputs/phase4_initialization_validation_report.txt": "Phase 4 validation report exists inside the zip",
    }
    for rel_path, message in required_checks.items():
        if rel_path in name_set:
            messages.append(f"PASS: {message}")
        else:
            messages.append(f"FAIL: Missing {rel_path}")
            status = "FAIL"

    if "main.py" in name_set:
        messages.append("FAIL: root-level main.py found in zip.")
        status = "FAIL"
    else:
        messages.append("PASS: no duplicate flattened root-level main.py found.")

    bad_cache = [name for name in names if "__pycache__" in Path(name).parts or name.lower().endswith(".pyc")]
    if bad_cache:
        messages.append(f"FAIL: cache/bytecode files found: {bad_cache}")
        status = "FAIL"
    else:
        messages.append("PASS: no __pycache__ or .pyc files found.")

    if len(names) != len(name_set):
        messages.append("FAIL: duplicate archive names found.")
        status = "FAIL"
    else:
        messages.append("PASS: no duplicate archive names found.")

    return status, messages


def _replace_manifest_in_zip() -> None:
    temp_path = ZIP_PATH.with_suffix(".tmp.zip")
    manifest_arcname = MANIFEST_PATH.relative_to(PROJECT_ROOT).as_posix()
    with zipfile.ZipFile(ZIP_PATH, "r") as source, zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            if item.filename == manifest_arcname:
                continue
            target.writestr(item, source.read(item.filename))
        target.write(MANIFEST_PATH, arcname=manifest_arcname)
    ZIP_PATH.unlink()
    temp_path.rename(ZIP_PATH)


def _build_manifest(
    generated_at: str,
    included: list[str],
    missing: list[str],
    excluded: list[str],
    verification_status: str,
    verification_messages: list[str],
) -> str:
    zip_size_mb = ZIP_PATH.stat().st_size / (1024 * 1024) if ZIP_PATH.exists() else 0.0
    lines = [
        "Phase 4 Step 7C Maintenance Master Review Bundle Manifest",
        f"Generated zip path: {ZIP_PATH}",
        f"Generated timestamp UTC: {generated_at}",
        f"Included file count: {len(included)}",
        f"Missing file count: {len(missing)}",
        f"Excluded file count: {len(excluded)}",
        f"Final zip size MB: {zip_size_mb:.3f}",
        f"Verification status: {verification_status}",
        "",
        "Verification messages:",
    ]
    lines.extend(f"- {message}" for message in verification_messages)
    lines.extend(["", "Missing files:"])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.extend(["", "Excluded files:"])
    lines.extend(f"- {item}" for item in excluded) if excluded else lines.append("- none")
    lines.extend(["", "Included files:"])
    lines.extend(f"- {item}" for item in included)
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
