"""Run Phase 4 initialization bridge logic only."""

from __future__ import annotations

from core.bom_explosion_bridge import OUTPUT_FILE, build_bom_component_requirements
from core.capacity_load import DETAIL_OUTPUT_FILE as CAPACITY_DETAIL_OUTPUT_FILE
from core.capacity_load import CONSTRAINT_BRIDGE_OUTPUT_FILE as CAPACITY_CONSTRAINT_BRIDGE_OUTPUT_FILE
from core.capacity_load import LABOR_OUTPUT_FILE as CAPACITY_LABOR_OUTPUT_FILE
from core.capacity_load import MACHINE_OUTPUT_FILE as CAPACITY_MACHINE_OUTPUT_FILE
from core.capacity_load import OUTPUT_FILE as CAPACITY_LOAD_OUTPUT_FILE
from core.capacity_load import VALIDATION_OUTPUT_FILE as CAPACITY_VALIDATION_OUTPUT_FILE
from core.capacity_load import build_workstation_capacity_load
from core.master_production_schedule import OUTPUT_FILE as MPS_OUTPUT_FILE
from core.master_production_schedule import build_master_production_schedule
from core.mrp_net_requirements import OUTPUT_FILE as MRP_OUTPUT_FILE
from core.mrp_net_requirements import PEGGING_OUTPUT_FILE, SUMMARY_OUTPUT_FILE
from core.mrp_net_requirements import build_mrp_net_component_requirements
from core.resource_master_data import OUTPUT_FILE as RESOURCE_VALIDATION_OUTPUT_FILE
from core.resource_master_data import validate_resource_master_data
from core.routing_master_data import FLOW_SUMMARY_OUTPUT_FILE
from core.routing_master_data import OUTPUT_FILE as ROUTING_VALIDATION_OUTPUT_FILE
from core.routing_master_data import validate_routing_master_data


def run_initialization() -> None:
    """Regenerate Phase 4 advisory MPS, BOM, and MRP net requirements."""
    mps = build_master_production_schedule()
    planning_run_id = None
    if not mps.empty and "planning_run_id" in mps.columns:
        run_ids = mps["planning_run_id"].dropna().astype(str).str.strip()
        if not run_ids.empty:
            planning_run_id = run_ids.iloc[0]
    requirements = build_bom_component_requirements(planning_run_id=planning_run_id)
    mrp = build_mrp_net_component_requirements(planning_run_id=planning_run_id)
    resource_validation = validate_resource_master_data()
    routing_validation = validate_routing_master_data()
    capacity_load, capacity_detail, capacity_validation = build_workstation_capacity_load()
    print("Phase 4 initialization bridge completed.")
    print(f"MPS rows: {len(mps)}")
    print(f"MPS output written to: {MPS_OUTPUT_FILE}")
    print(f"BOM component requirement rows: {len(requirements)}")
    print(f"Output written to: {OUTPUT_FILE}")
    print(f"MRP net component requirement rows: {len(mrp)}")
    print(f"MRP output written to: {MRP_OUTPUT_FILE}")
    print(f"MRP component-period summary written to: {SUMMARY_OUTPUT_FILE}")
    print(f"MRP pegging detail written to: {PEGGING_OUTPUT_FILE}")
    print(f"Resource validation rows: {len(resource_validation)}")
    print(f"Resource validation output written to: {RESOURCE_VALIDATION_OUTPUT_FILE}")
    print(f"Routing validation rows: {len(routing_validation)}")
    print(f"Routing validation output written to: {ROUTING_VALIDATION_OUTPUT_FILE}")
    print(f"Routing flow summary written to: {FLOW_SUMMARY_OUTPUT_FILE}")
    print(f"Capacity load rows: {len(capacity_load)}")
    print(f"Capacity load output written to: {CAPACITY_LOAD_OUTPUT_FILE}")
    print(f"Capacity operation detail rows: {len(capacity_detail)}")
    print(f"Capacity operation detail output written to: {CAPACITY_DETAIL_OUTPUT_FILE}")
    print(f"Machine capacity output written to: {CAPACITY_MACHINE_OUTPUT_FILE}")
    print(f"Labor capacity output written to: {CAPACITY_LABOR_OUTPUT_FILE}")
    print(f"Capacity constraint bridge output written to: {CAPACITY_CONSTRAINT_BRIDGE_OUTPUT_FILE}")
    print(f"Capacity validation rows: {len(capacity_validation)}")
    print(f"Capacity validation output written to: {CAPACITY_VALIDATION_OUTPUT_FILE}")


if __name__ == "__main__":
    run_initialization()
