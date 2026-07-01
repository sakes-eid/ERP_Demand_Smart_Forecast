"""Run Phase 4 initialization bridge logic only."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.bom_explosion_bridge import OUTPUT_FILE, build_bom_component_requirements
from core.bottleneck_visibility import MANAGER_REVIEW_OUTPUT_FILE as BOTTLENECK_MANAGER_REVIEW_OUTPUT_FILE
from core.bottleneck_visibility import PERIOD_EVIDENCE_OUTPUT_FILE as BOTTLENECK_PERIOD_EVIDENCE_OUTPUT_FILE
from core.bottleneck_visibility import VALIDATION_OUTPUT_FILE as BOTTLENECK_VALIDATION_OUTPUT_FILE
from core.bottleneck_visibility import VISIBILITY_SUMMARY_OUTPUT_FILE as BOTTLENECK_VISIBILITY_SUMMARY_OUTPUT_FILE
from core.bottleneck_visibility import build_bottleneck_visibility_outputs
from core.capacity_load import DETAIL_OUTPUT_FILE as CAPACITY_DETAIL_OUTPUT_FILE
from core.capacity_load import BOTTLENECK_CANDIDATE_OUTPUT_FILE as CAPACITY_BOTTLENECK_CANDIDATE_OUTPUT_FILE
from core.capacity_load import CONSTRAINT_BRIDGE_OUTPUT_FILE as CAPACITY_CONSTRAINT_BRIDGE_OUTPUT_FILE
from core.capacity_load import FEASIBILITY_SUMMARY_OUTPUT_FILE as CAPACITY_FEASIBILITY_SUMMARY_OUTPUT_FILE
from core.capacity_load import LABOR_OUTPUT_FILE as CAPACITY_LABOR_OUTPUT_FILE
from core.capacity_load import MACHINE_OUTPUT_FILE as CAPACITY_MACHINE_OUTPUT_FILE
from core.capacity_load import MANAGER_REVIEW_QUEUE_OUTPUT_FILE as CAPACITY_MANAGER_REVIEW_QUEUE_OUTPUT_FILE
from core.capacity_load import OUTPUT_FILE as CAPACITY_LOAD_OUTPUT_FILE
from core.capacity_load import VALIDATION_OUTPUT_FILE as CAPACITY_VALIDATION_OUTPUT_FILE
from core.capacity_load import build_workstation_capacity_load
from core.master_production_schedule import OUTPUT_FILE as MPS_OUTPUT_FILE
from core.master_production_schedule import build_master_production_schedule
from core.mrp_net_requirements import OUTPUT_FILE as MRP_OUTPUT_FILE
from core.mrp_net_requirements import PEGGING_OUTPUT_FILE, SUMMARY_OUTPUT_FILE
from core.mrp_net_requirements import build_mrp_net_component_requirements
from core.queue_pressure import QUEUE_MANAGER_REVIEW_OUTPUT_FILE
from core.queue_pressure import QUEUE_PRESSURE_OUTPUT_FILE
from core.queue_pressure import QUEUE_RISK_SUMMARY_OUTPUT_FILE
from core.queue_pressure import QUEUE_VALIDATION_OUTPUT_FILE
from core.queue_pressure import build_queue_pressure_outputs
from core.production_flow_view import FLOW_MANAGER_REVIEW_OUTPUT_FILE
from core.production_flow_view import FLOW_RISK_SUMMARY_OUTPUT_FILE
from core.production_flow_view import FLOW_VALIDATION_OUTPUT_FILE
from core.production_flow_view import PRODUCTION_FLOW_OUTPUT_FILE
from core.production_flow_view import build_production_flow_view_outputs
from core.quality_trends import PROCESSING_TIME_TREND_OUTPUT_FILE
from core.quality_trends import QUALITY_HISTORY_CLEAN_OUTPUT_FILE
from core.quality_trends import QUALITY_MANAGER_REVIEW_OUTPUT_FILE
from core.quality_trends import QUALITY_TREND_OPERATION_OUTPUT_FILE
from core.quality_trends import QUALITY_TREND_WORKSTATION_OUTPUT_FILE
from core.quality_trends import QUALITY_VALIDATION_OUTPUT_FILE
from core.quality_trends import WORKSTATION_PERFORMANCE_SUMMARY_OUTPUT_FILE
from core.quality_trends import build_quality_trend_outputs
from core.quality_adjusted_capacity import QUALITY_ADJUSTED_BOTTLENECK_OUTPUT_FILE
from core.quality_adjusted_capacity import QUALITY_ADJUSTED_CAPACITY_OUTPUT_FILE
from core.quality_adjusted_capacity import QUALITY_ADJUSTED_VALIDATION_OUTPUT_FILE
from core.quality_adjusted_capacity import QUALITY_IMPACT_MANAGER_REVIEW_OUTPUT_FILE
from core.quality_adjusted_capacity import QUALITY_IMPACT_OPERATION_OUTPUT_FILE
from core.quality_adjusted_capacity import QUALITY_MATERIAL_LOSS_OUTPUT_FILE
from core.quality_adjusted_capacity import build_quality_adjusted_capacity_outputs
from core.resource_master_data import OUTPUT_FILE as RESOURCE_VALIDATION_OUTPUT_FILE
from core.resource_master_data import validate_resource_master_data
from core.routing_master_data import FLOW_SUMMARY_OUTPUT_FILE
from core.routing_master_data import OUTPUT_FILE as ROUTING_VALIDATION_OUTPUT_FILE
from core.routing_master_data import validate_routing_master_data
from shared.core.workforce_master_data import CREW_CAPACITY_CONTEXT_FILE
from shared.core.workforce_master_data import MACHINE_AUTH_CONTEXT_FILE as WORKFORCE_MACHINE_AUTH_CONTEXT_FILE
from shared.core.workforce_master_data import MANAGER_REVIEW_QUEUE_FILE as WORKFORCE_MANAGER_REVIEW_QUEUE_FILE
from shared.core.workforce_master_data import PHASE4_WORKFORCE_CONTEXT_FILE
from shared.core.workforce_master_data import SKILL_COVERAGE_SUMMARY_FILE as WORKFORCE_SKILL_COVERAGE_SUMMARY_FILE
from shared.core.workforce_master_data import VALIDATION_OUTPUT_FILE as WORKFORCE_VALIDATION_OUTPUT_FILE
from shared.core.workforce_master_data import build_workforce_master_data_outputs
from shared.core.spare_parts_master_data import MACHINE_REQUIREMENT_CONTEXT_FILE as SPARE_MACHINE_REQUIREMENT_CONTEXT_FILE
from shared.core.spare_parts_master_data import MANAGER_REVIEW_QUEUE_FILE as SPARE_MANAGER_REVIEW_QUEUE_FILE
from shared.core.spare_parts_master_data import PHASE4_SPARE_PART_CONTEXT_FILE
from shared.core.spare_parts_master_data import PHASE_INTEGRATION_CONTEXT_FILE as SPARE_PHASE_INTEGRATION_CONTEXT_FILE
from shared.core.spare_parts_master_data import VALIDATION_OUTPUT_FILE as SPARE_VALIDATION_OUTPUT_FILE
from shared.core.spare_parts_master_data import build_spare_part_master_data_outputs
from shared.core.maintenance_master_data import COST_DOWNTIME_CONTEXT_FILE
from shared.core.maintenance_master_data import DUE_STATUS_CONTEXT_FILE
from shared.core.maintenance_master_data import MANAGER_REVIEW_QUEUE_FILE as MAINTENANCE_MANAGER_REVIEW_QUEUE_FILE
from shared.core.maintenance_master_data import PHASE4_MAINTENANCE_CONTEXT_FILE
from shared.core.maintenance_master_data import SPARE_PART_CONTEXT_FILE as MAINTENANCE_SPARE_PART_CONTEXT_FILE
from shared.core.maintenance_master_data import VALIDATION_OUTPUT_FILE as MAINTENANCE_VALIDATION_OUTPUT_FILE
from shared.core.maintenance_master_data import build_maintenance_master_data_outputs
from shared.core.breakdown_risk_forecast import BREAKDOWN_HISTORY_CLEAN_FILE
from shared.core.breakdown_risk_forecast import BREAKDOWN_RISK_FORECAST_FILE
from shared.core.breakdown_risk_forecast import BREAKDOWN_TREND_FILE
from shared.core.breakdown_risk_forecast import CREW_SKILL_EXPOSURE_FILE as BREAKDOWN_CREW_SKILL_EXPOSURE_FILE
from shared.core.breakdown_risk_forecast import FAILURE_MODE_EXPOSURE_FILE as BREAKDOWN_FAILURE_MODE_EXPOSURE_FILE
from shared.core.breakdown_risk_forecast import MANAGER_REVIEW_QUEUE_FILE as BREAKDOWN_MANAGER_REVIEW_QUEUE_FILE
from shared.core.breakdown_risk_forecast import PHASE4_BREAKDOWN_CONTEXT_FILE
from shared.core.breakdown_risk_forecast import SPARE_PART_EXPOSURE_FILE as BREAKDOWN_SPARE_PART_EXPOSURE_FILE
from shared.core.breakdown_risk_forecast import VALIDATION_OUTPUT_FILE as BREAKDOWN_VALIDATION_OUTPUT_FILE
from shared.core.breakdown_risk_forecast import build_breakdown_risk_outputs
from shared.core.maintenance_crew_capacity import BACKLOG_RISK_SUMMARY_FILE as MAINTENANCE_BACKLOG_RISK_SUMMARY_FILE
from shared.core.maintenance_crew_capacity import CREW_CAPACITY_SUMMARY_FILE as MAINTENANCE_CREW_CAPACITY_SUMMARY_FILE
from shared.core.maintenance_crew_capacity import MANAGER_REVIEW_QUEUE_FILE as MAINTENANCE_CREW_MANAGER_REVIEW_QUEUE_FILE
from shared.core.maintenance_crew_capacity import PHASE4_CREW_CAPACITY_CONTEXT_FILE
from shared.core.maintenance_crew_capacity import REPAIR_QUEUE_RISK_FILE as MAINTENANCE_REPAIR_QUEUE_RISK_FILE
from shared.core.maintenance_crew_capacity import VALIDATION_OUTPUT_FILE as MAINTENANCE_CREW_CAPACITY_VALIDATION_OUTPUT_FILE
from shared.core.maintenance_crew_capacity import WORKLOAD_BY_SKILL_FILE as MAINTENANCE_WORKLOAD_BY_SKILL_FILE
from shared.core.maintenance_crew_capacity import build_maintenance_crew_capacity_outputs
from shared.core.maintenance_production_impact import BOTTLENECK_IMPACT_OUTPUT_FILE as MAINTENANCE_BOTTLENECK_IMPACT_OUTPUT_FILE
from shared.core.maintenance_production_impact import COST_EXPOSURE_OUTPUT_FILE as MAINTENANCE_BREAKDOWN_COST_EXPOSURE_OUTPUT_FILE
from shared.core.maintenance_production_impact import MACHINE_AVAILABILITY_OUTPUT_FILE as MAINTENANCE_MACHINE_AVAILABILITY_OUTPUT_FILE
from shared.core.maintenance_production_impact import MANAGER_REVIEW_OUTPUT_FILE as MAINTENANCE_IMPACT_MANAGER_REVIEW_OUTPUT_FILE
from shared.core.maintenance_production_impact import PHASE4_CONTEXT_OUTPUT_FILE as PHASE4_MAINTENANCE_PRODUCTION_IMPACT_CONTEXT_FILE
from shared.core.maintenance_production_impact import PRODUCTION_CAPACITY_OUTPUT_FILE as MAINTENANCE_PRODUCTION_CAPACITY_IMPACT_OUTPUT_FILE
from shared.core.maintenance_production_impact import SCHEDULING_CANDIDATE_OUTPUT_FILE as MAINTENANCE_SCHEDULING_CANDIDATE_OUTPUT_FILE
from shared.core.maintenance_production_impact import VALIDATION_OUTPUT_FILE as MAINTENANCE_PRODUCTION_IMPACT_VALIDATION_OUTPUT_FILE
from shared.core.maintenance_production_impact import WINDOW_REQUIREMENTS_OUTPUT_FILE as MAINTENANCE_WINDOW_REQUIREMENTS_OUTPUT_FILE
from shared.core.maintenance_production_impact import build_maintenance_production_impact_outputs
from shared.core.maintenance_schedule_feasibility import CALENDAR_FEASIBILITY_FILE as MAINTENANCE_CALENDAR_FEASIBILITY_FILE
from shared.core.maintenance_schedule_feasibility import CREW_WINDOW_LOAD_FILE as MAINTENANCE_CREW_WINDOW_LOAD_FILE
from shared.core.maintenance_schedule_feasibility import MACHINE_WINDOW_IMPACT_FILE as MAINTENANCE_MACHINE_WINDOW_IMPACT_FILE
from shared.core.maintenance_schedule_feasibility import MANAGER_REVIEW_FILE as MAINTENANCE_SCHEDULE_MANAGER_REVIEW_FILE
from shared.core.maintenance_schedule_feasibility import PHASE4_CONTEXT_FILE as PHASE4_MAINTENANCE_SCHEDULE_FEASIBILITY_CONTEXT_FILE
from shared.core.maintenance_schedule_feasibility import SCHEDULE_CANDIDATE_WINDOWS_FILE as MAINTENANCE_SCHEDULE_CANDIDATE_WINDOWS_FILE
from shared.core.maintenance_schedule_feasibility import VALIDATION_OUTPUT_FILE as MAINTENANCE_SCHEDULE_VALIDATION_OUTPUT_FILE
from shared.core.maintenance_schedule_feasibility import build_maintenance_schedule_feasibility_outputs


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
    workforce_validation, workforce_capacity, workforce_machine_auth, workforce_skill_summary, workforce_review, phase4_workforce_context = build_workforce_master_data_outputs()
    spare_validation, spare_machine_context, spare_phase_context, spare_review, phase4_spare_context = build_spare_part_master_data_outputs()
    maintenance_validation, maintenance_due, maintenance_spare, maintenance_cost, maintenance_review, phase4_maintenance_context = build_maintenance_master_data_outputs()
    breakdown_validation, breakdown_clean, breakdown_trend, breakdown_risk, breakdown_failure, breakdown_spare, breakdown_crew, breakdown_review, phase4_breakdown_context = build_breakdown_risk_outputs()
    maintenance_crew_validation, maintenance_workload, maintenance_crew_summary, maintenance_repair_queue, maintenance_backlog, maintenance_crew_review, phase4_maintenance_crew_context = build_maintenance_crew_capacity_outputs()
    maintenance_impact_validation, maintenance_availability, maintenance_capacity_impact, maintenance_cost_exposure, maintenance_bottleneck_impact, maintenance_candidates, maintenance_windows, maintenance_impact_review, phase4_maintenance_impact_context = build_maintenance_production_impact_outputs()
    maintenance_schedule_validation, maintenance_schedule_windows, maintenance_calendar, maintenance_crew_window_load, maintenance_machine_window_impact, maintenance_schedule_review, phase4_maintenance_schedule_context = build_maintenance_schedule_feasibility_outputs()
    routing_validation = validate_routing_master_data()
    capacity_load, capacity_detail, capacity_validation = build_workstation_capacity_load()
    queue_pressure, queue_summary, queue_review, queue_validation = build_queue_pressure_outputs()
    bottleneck_summary, bottleneck_periods, bottleneck_review, bottleneck_validation = build_bottleneck_visibility_outputs()
    flow_view, flow_summary, flow_review, flow_validation = build_production_flow_view_outputs()
    quality_history, quality_operation, quality_workstation, processing_trend, performance_summary, quality_review, quality_validation = build_quality_trend_outputs()
    quality_impact, quality_adjusted_capacity, quality_bottleneck_impact, quality_material_loss, quality_impact_review, quality_adjusted_validation = build_quality_adjusted_capacity_outputs()
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
    print(f"Shared workforce validation rows: {len(workforce_validation)}")
    print(f"Shared workforce validation output written to: {WORKFORCE_VALIDATION_OUTPUT_FILE}")
    print(f"Workforce crew capacity context rows: {len(workforce_capacity)}")
    print(f"Workforce crew capacity context output written to: {CREW_CAPACITY_CONTEXT_FILE}")
    print(f"Workforce machine authorization context rows: {len(workforce_machine_auth)}")
    print(f"Workforce machine authorization context output written to: {WORKFORCE_MACHINE_AUTH_CONTEXT_FILE}")
    print(f"Workforce skill coverage summary rows: {len(workforce_skill_summary)}")
    print(f"Workforce skill coverage summary output written to: {WORKFORCE_SKILL_COVERAGE_SUMMARY_FILE}")
    print(f"Workforce manager review rows: {len(workforce_review)}")
    print(f"Workforce manager review output written to: {WORKFORCE_MANAGER_REVIEW_QUEUE_FILE}")
    print(f"Phase 4 workforce context rows: {len(phase4_workforce_context)}")
    print(f"Phase 4 workforce context output written to: {PHASE4_WORKFORCE_CONTEXT_FILE}")
    print(f"Shared spare-part validation rows: {len(spare_validation)}")
    print(f"Shared spare-part validation output written to: {SPARE_VALIDATION_OUTPUT_FILE}")
    print(f"Spare-part machine requirement context rows: {len(spare_machine_context)}")
    print(f"Spare-part machine requirement context output written to: {SPARE_MACHINE_REQUIREMENT_CONTEXT_FILE}")
    print(f"Spare-part phase integration context rows: {len(spare_phase_context)}")
    print(f"Spare-part phase integration context output written to: {SPARE_PHASE_INTEGRATION_CONTEXT_FILE}")
    print(f"Spare-part manager review rows: {len(spare_review)}")
    print(f"Spare-part manager review output written to: {SPARE_MANAGER_REVIEW_QUEUE_FILE}")
    print(f"Phase 4 spare-part context rows: {len(phase4_spare_context)}")
    print(f"Phase 4 spare-part context output written to: {PHASE4_SPARE_PART_CONTEXT_FILE}")
    print(f"Shared maintenance validation rows: {len(maintenance_validation)}")
    print(f"Shared maintenance validation output written to: {MAINTENANCE_VALIDATION_OUTPUT_FILE}")
    print(f"Maintenance due-status context rows: {len(maintenance_due)}")
    print(f"Maintenance due-status context output written to: {DUE_STATUS_CONTEXT_FILE}")
    print(f"Maintenance spare-part requirement rows: {len(maintenance_spare)}")
    print(f"Maintenance spare-part requirement output written to: {MAINTENANCE_SPARE_PART_CONTEXT_FILE}")
    print(f"Maintenance cost/downtime rows: {len(maintenance_cost)}")
    print(f"Maintenance cost/downtime output written to: {COST_DOWNTIME_CONTEXT_FILE}")
    print(f"Maintenance manager review rows: {len(maintenance_review)}")
    print(f"Maintenance manager review output written to: {MAINTENANCE_MANAGER_REVIEW_QUEUE_FILE}")
    print(f"Phase 4 maintenance readiness rows: {len(phase4_maintenance_context)}")
    print(f"Phase 4 maintenance readiness output written to: {PHASE4_MAINTENANCE_CONTEXT_FILE}")
    print(f"Breakdown validation rows: {len(breakdown_validation)}")
    print(f"Breakdown validation output written to: {BREAKDOWN_VALIDATION_OUTPUT_FILE}")
    print(f"Breakdown history clean rows: {len(breakdown_clean)}")
    print(f"Breakdown history clean output written to: {BREAKDOWN_HISTORY_CLEAN_FILE}")
    print(f"Breakdown trend rows: {len(breakdown_trend)}")
    print(f"Breakdown trend output written to: {BREAKDOWN_TREND_FILE}")
    print(f"Breakdown risk forecast rows: {len(breakdown_risk)}")
    print(f"Breakdown risk forecast output written to: {BREAKDOWN_RISK_FORECAST_FILE}")
    print(f"Breakdown failure-mode exposure rows: {len(breakdown_failure)}")
    print(f"Breakdown failure-mode exposure output written to: {BREAKDOWN_FAILURE_MODE_EXPOSURE_FILE}")
    print(f"Breakdown spare-part exposure rows: {len(breakdown_spare)}")
    print(f"Breakdown spare-part exposure output written to: {BREAKDOWN_SPARE_PART_EXPOSURE_FILE}")
    print(f"Breakdown crew-skill exposure rows: {len(breakdown_crew)}")
    print(f"Breakdown crew-skill exposure output written to: {BREAKDOWN_CREW_SKILL_EXPOSURE_FILE}")
    print(f"Breakdown manager review rows: {len(breakdown_review)}")
    print(f"Breakdown manager review output written to: {BREAKDOWN_MANAGER_REVIEW_QUEUE_FILE}")
    print(f"Phase 4 breakdown risk context rows: {len(phase4_breakdown_context)}")
    print(f"Phase 4 breakdown risk context output written to: {PHASE4_BREAKDOWN_CONTEXT_FILE}")
    print(f"Maintenance crew capacity validation rows: {len(maintenance_crew_validation)}")
    print(f"Maintenance crew capacity validation output written to: {MAINTENANCE_CREW_CAPACITY_VALIDATION_OUTPUT_FILE}")
    print(f"Maintenance workload by skill rows: {len(maintenance_workload)}")
    print(f"Maintenance workload by skill output written to: {MAINTENANCE_WORKLOAD_BY_SKILL_FILE}")
    print(f"Maintenance crew capacity summary rows: {len(maintenance_crew_summary)}")
    print(f"Maintenance crew capacity summary output written to: {MAINTENANCE_CREW_CAPACITY_SUMMARY_FILE}")
    print(f"Maintenance repair queue risk rows: {len(maintenance_repair_queue)}")
    print(f"Maintenance repair queue risk output written to: {MAINTENANCE_REPAIR_QUEUE_RISK_FILE}")
    print(f"Maintenance backlog risk summary rows: {len(maintenance_backlog)}")
    print(f"Maintenance backlog risk summary output written to: {MAINTENANCE_BACKLOG_RISK_SUMMARY_FILE}")
    print(f"Maintenance crew capacity manager review rows: {len(maintenance_crew_review)}")
    print(f"Maintenance crew capacity manager review output written to: {MAINTENANCE_CREW_MANAGER_REVIEW_QUEUE_FILE}")
    print(f"Phase 4 maintenance crew capacity context rows: {len(phase4_maintenance_crew_context)}")
    print(f"Phase 4 maintenance crew capacity context output written to: {PHASE4_CREW_CAPACITY_CONTEXT_FILE}")
    print(f"Maintenance production impact validation rows: {len(maintenance_impact_validation)}")
    print(f"Maintenance production impact validation output written to: {MAINTENANCE_PRODUCTION_IMPACT_VALIDATION_OUTPUT_FILE}")
    print(f"Machine availability impact rows: {len(maintenance_availability)}")
    print(f"Machine availability impact output written to: {MAINTENANCE_MACHINE_AVAILABILITY_OUTPUT_FILE}")
    print(f"Maintenance production capacity impact rows: {len(maintenance_capacity_impact)}")
    print(f"Maintenance production capacity impact output written to: {MAINTENANCE_PRODUCTION_CAPACITY_IMPACT_OUTPUT_FILE}")
    print(f"Maintenance breakdown cost exposure rows: {len(maintenance_cost_exposure)}")
    print(f"Maintenance breakdown cost exposure output written to: {MAINTENANCE_BREAKDOWN_COST_EXPOSURE_OUTPUT_FILE}")
    print(f"Maintenance bottleneck impact rows: {len(maintenance_bottleneck_impact)}")
    print(f"Maintenance bottleneck impact output written to: {MAINTENANCE_BOTTLENECK_IMPACT_OUTPUT_FILE}")
    print(f"Maintenance scheduling candidate rows: {len(maintenance_candidates)}")
    print(f"Maintenance scheduling candidate output written to: {MAINTENANCE_SCHEDULING_CANDIDATE_OUTPUT_FILE}")
    print(f"Maintenance window requirement rows: {len(maintenance_windows)}")
    print(f"Maintenance window requirement output written to: {MAINTENANCE_WINDOW_REQUIREMENTS_OUTPUT_FILE}")
    print(f"Maintenance impact manager review rows: {len(maintenance_impact_review)}")
    print(f"Maintenance impact manager review output written to: {MAINTENANCE_IMPACT_MANAGER_REVIEW_OUTPUT_FILE}")
    print(f"Phase 4 maintenance production impact context rows: {len(phase4_maintenance_impact_context)}")
    print(f"Phase 4 maintenance production impact context output written to: {PHASE4_MAINTENANCE_PRODUCTION_IMPACT_CONTEXT_FILE}")
    print(f"Maintenance schedule validation rows: {len(maintenance_schedule_validation)}")
    print(f"Maintenance schedule validation output written to: {MAINTENANCE_SCHEDULE_VALIDATION_OUTPUT_FILE}")
    print(f"Maintenance schedule candidate window rows: {len(maintenance_schedule_windows)}")
    print(f"Maintenance schedule candidate windows output written to: {MAINTENANCE_SCHEDULE_CANDIDATE_WINDOWS_FILE}")
    print(f"Maintenance calendar feasibility rows: {len(maintenance_calendar)}")
    print(f"Maintenance calendar feasibility output written to: {MAINTENANCE_CALENDAR_FEASIBILITY_FILE}")
    print(f"Maintenance crew window load rows: {len(maintenance_crew_window_load)}")
    print(f"Maintenance crew window load output written to: {MAINTENANCE_CREW_WINDOW_LOAD_FILE}")
    print(f"Maintenance machine window impact rows: {len(maintenance_machine_window_impact)}")
    print(f"Maintenance machine window impact output written to: {MAINTENANCE_MACHINE_WINDOW_IMPACT_FILE}")
    print(f"Maintenance schedule manager review rows: {len(maintenance_schedule_review)}")
    print(f"Maintenance schedule manager review output written to: {MAINTENANCE_SCHEDULE_MANAGER_REVIEW_FILE}")
    print(f"Phase 4 maintenance schedule feasibility context rows: {len(phase4_maintenance_schedule_context)}")
    print(f"Phase 4 maintenance schedule feasibility context output written to: {PHASE4_MAINTENANCE_SCHEDULE_FEASIBILITY_CONTEXT_FILE}")
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
    print(f"Capacity feasibility summary output written to: {CAPACITY_FEASIBILITY_SUMMARY_OUTPUT_FILE}")
    print(f"Bottleneck candidate summary output written to: {CAPACITY_BOTTLENECK_CANDIDATE_OUTPUT_FILE}")
    print(f"Capacity manager review queue output written to: {CAPACITY_MANAGER_REVIEW_QUEUE_OUTPUT_FILE}")
    print(f"Capacity validation rows: {len(capacity_validation)}")
    print(f"Capacity validation output written to: {CAPACITY_VALIDATION_OUTPUT_FILE}")
    print(f"Queue pressure rows: {len(queue_pressure)}")
    print(f"Queue pressure output written to: {QUEUE_PRESSURE_OUTPUT_FILE}")
    print(f"Queue risk summary rows: {len(queue_summary)}")
    print(f"Queue risk summary output written to: {QUEUE_RISK_SUMMARY_OUTPUT_FILE}")
    print(f"Queue manager review rows: {len(queue_review)}")
    print(f"Queue manager review output written to: {QUEUE_MANAGER_REVIEW_OUTPUT_FILE}")
    print(f"Queue validation rows: {len(queue_validation)}")
    print(f"Queue validation output written to: {QUEUE_VALIDATION_OUTPUT_FILE}")
    print(f"Bottleneck visibility summary rows: {len(bottleneck_summary)}")
    print(f"Bottleneck visibility summary output written to: {BOTTLENECK_VISIBILITY_SUMMARY_OUTPUT_FILE}")
    print(f"Bottleneck period evidence rows: {len(bottleneck_periods)}")
    print(f"Bottleneck period evidence output written to: {BOTTLENECK_PERIOD_EVIDENCE_OUTPUT_FILE}")
    print(f"Bottleneck manager review rows: {len(bottleneck_review)}")
    print(f"Bottleneck manager review output written to: {BOTTLENECK_MANAGER_REVIEW_OUTPUT_FILE}")
    print(f"Bottleneck validation rows: {len(bottleneck_validation)}")
    print(f"Bottleneck validation output written to: {BOTTLENECK_VALIDATION_OUTPUT_FILE}")
    print(f"Production flow view rows: {len(flow_view)}")
    print(f"Production flow view output written to: {PRODUCTION_FLOW_OUTPUT_FILE}")
    print(f"Flow-step risk summary rows: {len(flow_summary)}")
    print(f"Flow-step risk summary output written to: {FLOW_RISK_SUMMARY_OUTPUT_FILE}")
    print(f"Flow manager review rows: {len(flow_review)}")
    print(f"Flow manager review output written to: {FLOW_MANAGER_REVIEW_OUTPUT_FILE}")
    print(f"Flow validation rows: {len(flow_validation)}")
    print(f"Flow validation output written to: {FLOW_VALIDATION_OUTPUT_FILE}")
    print(f"Quality history clean rows: {len(quality_history)}")
    print(f"Quality history clean output written to: {QUALITY_HISTORY_CLEAN_OUTPUT_FILE}")
    print(f"Quality operation trend rows: {len(quality_operation)}")
    print(f"Quality operation trend output written to: {QUALITY_TREND_OPERATION_OUTPUT_FILE}")
    print(f"Quality workstation trend rows: {len(quality_workstation)}")
    print(f"Quality workstation trend output written to: {QUALITY_TREND_WORKSTATION_OUTPUT_FILE}")
    print(f"Processing time trend rows: {len(processing_trend)}")
    print(f"Processing time trend output written to: {PROCESSING_TIME_TREND_OUTPUT_FILE}")
    print(f"Workstation performance summary rows: {len(performance_summary)}")
    print(f"Workstation performance summary output written to: {WORKSTATION_PERFORMANCE_SUMMARY_OUTPUT_FILE}")
    print(f"Quality manager review rows: {len(quality_review)}")
    print(f"Quality manager review output written to: {QUALITY_MANAGER_REVIEW_OUTPUT_FILE}")
    print(f"Quality validation rows: {len(quality_validation)}")
    print(f"Quality validation output written to: {QUALITY_VALIDATION_OUTPUT_FILE}")
    print(f"Quality impact operation rows: {len(quality_impact)}")
    print(f"Quality impact operation output written to: {QUALITY_IMPACT_OPERATION_OUTPUT_FILE}")
    print(f"Quality-adjusted capacity rows: {len(quality_adjusted_capacity)}")
    print(f"Quality-adjusted capacity output written to: {QUALITY_ADJUSTED_CAPACITY_OUTPUT_FILE}")
    print(f"Quality-adjusted bottleneck impact rows: {len(quality_bottleneck_impact)}")
    print(f"Quality-adjusted bottleneck impact output written to: {QUALITY_ADJUSTED_BOTTLENECK_OUTPUT_FILE}")
    print(f"Quality material loss exposure rows: {len(quality_material_loss)}")
    print(f"Quality material loss exposure output written to: {QUALITY_MATERIAL_LOSS_OUTPUT_FILE}")
    print(f"Quality impact manager review rows: {len(quality_impact_review)}")
    print(f"Quality impact manager review output written to: {QUALITY_IMPACT_MANAGER_REVIEW_OUTPUT_FILE}")
    print(f"Quality-adjusted capacity validation rows: {len(quality_adjusted_validation)}")
    print(f"Quality-adjusted capacity validation output written to: {QUALITY_ADJUSTED_VALIDATION_OUTPUT_FILE}")


if __name__ == "__main__":
    run_initialization()
