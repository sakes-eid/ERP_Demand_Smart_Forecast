"""Build advisory production schedule candidates from MPS, routing graph, and risk context."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE4_DIR.parent
OUTPUT_DIR = PHASE4_DIR / "outputs"
PHASE3_OUTPUT_DIR = PROJECT_ROOT / "phase 3" / "outputs"
PHASE2_OUTPUT_DIR = PROJECT_ROOT / "phase 2" / "outputs"

MPS_FILE = OUTPUT_DIR / "phase4_master_production_schedule.csv"
MRP_SUMMARY_FILE = OUTPUT_DIR / "phase4_mrp_component_period_summary.csv"
MRP_PEGGING_FILE = OUTPUT_DIR / "phase4_mrp_pegging_detail.csv"
ROUTING_NODES_FILE = OUTPUT_DIR / "phase4_routing_graph_nodes.csv"
ROUTING_EDGES_FILE = OUTPUT_DIR / "phase4_routing_graph_edges.csv"
CRITICAL_PATH_FILE = OUTPUT_DIR / "phase4_critical_path_by_product.csv"
SLACK_FILE = OUTPUT_DIR / "phase4_operation_slack_analysis.csv"
WORKSTATION_CAPACITY_FILE = OUTPUT_DIR / "phase4_capacity_load_by_workstation.csv"
MACHINE_CAPACITY_FILE = OUTPUT_DIR / "phase4_capacity_load_by_machine_type.csv"
LABOR_CAPACITY_FILE = OUTPUT_DIR / "phase4_capacity_load_by_labor_skill.csv"
QUEUE_RISK_FILE = OUTPUT_DIR / "phase4_queue_risk_summary.csv"
BOTTLENECK_FILE = OUTPUT_DIR / "phase4_bottleneck_visibility_summary.csv"
QUALITY_CAPACITY_FILE = OUTPUT_DIR / "phase4_quality_adjusted_capacity_by_workstation.csv"
MAINTENANCE_SCHEDULE_FILE = OUTPUT_DIR / "phase4_maintenance_schedule_feasibility_context.csv"
MAINTENANCE_IMPACT_FILE = OUTPUT_DIR / "phase4_maintenance_production_impact_context.csv"
INVENTORY_CHECK_FILE = PHASE3_OUTPUT_DIR / "phase4_component_inventory_check.csv"
SUPPLIER_CHECK_FILE = PHASE2_OUTPUT_DIR / "phase4_component_supplier_check.csv"

SCHEDULE_CANDIDATES_OUTPUT_FILE = OUTPUT_DIR / "phase4_production_schedule_candidates.csv"
OPERATION_DETAIL_OUTPUT_FILE = OUTPUT_DIR / "phase4_operation_schedule_candidate_detail.csv"
MATERIAL_READINESS_OUTPUT_FILE = OUTPUT_DIR / "phase4_production_schedule_material_readiness.csv"
CAPACITY_CHECK_OUTPUT_FILE = OUTPUT_DIR / "phase4_production_schedule_capacity_check.csv"
CALENDAR_VIEW_OUTPUT_FILE = OUTPUT_DIR / "phase4_production_calendar_candidate_view.csv"
MANAGER_REVIEW_OUTPUT_FILE = OUTPUT_DIR / "phase4_production_schedule_manager_review_queue.csv"
VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_production_schedule_validation.csv"

SOURCE_PHASE = "PHASE4_STEP8B_ADVISORY_PRODUCTION_SCHEDULE_CANDIDATES"
VALID_SCHEDULE_STATUSES = {"FEASIBLE_CANDIDATE", "MATERIAL_BLOCKED", "CAPACITY_BLOCKED", "MAINTENANCE_BLOCKED", "MULTI_BLOCKED", "REVIEW_REQUIRED"}
VALID_ASSIGNMENT_STATUS = {"NOT_SCHEDULED_CANDIDATE_ONLY"}
VALID_REVIEW_TYPES = {
    "MATERIAL_BLOCKED_SCHEDULE_CANDIDATE",
    "CAPACITY_BLOCKED_SCHEDULE_CANDIDATE",
    "MAINTENANCE_BLOCKED_SCHEDULE_CANDIDATE",
    "CRITICAL_PATH_SCHEDULE_RISK",
    "BOTTLENECK_SCHEDULE_RISK",
    "QUEUE_RISK_SCHEDULE_CANDIDATE",
    "MULTI_BLOCKED_SCHEDULE_CANDIDATE",
    "REVIEW_REQUIRED",
}


def build_production_schedule_candidate_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    checks: list[dict] = []
    frames = {
        "mps": _load_csv(MPS_FILE, "phase4_master_production_schedule", checks),
        "mrp_summary": _load_csv(MRP_SUMMARY_FILE, "phase4_mrp_component_period_summary", checks),
        "mrp_pegging": _load_csv(MRP_PEGGING_FILE, "phase4_mrp_pegging_detail", checks),
        "nodes": _load_csv(ROUTING_NODES_FILE, "phase4_routing_graph_nodes", checks),
        "edges": _load_csv(ROUTING_EDGES_FILE, "phase4_routing_graph_edges", checks),
        "critical": _load_csv(CRITICAL_PATH_FILE, "phase4_critical_path_by_product", checks),
        "slack": _load_csv(SLACK_FILE, "phase4_operation_slack_analysis", checks),
        "workstation_capacity": _load_csv(WORKSTATION_CAPACITY_FILE, "phase4_capacity_load_by_workstation", checks),
        "machine_capacity": _load_csv(MACHINE_CAPACITY_FILE, "phase4_capacity_load_by_machine_type", checks),
        "labor_capacity": _load_csv(LABOR_CAPACITY_FILE, "phase4_capacity_load_by_labor_skill", checks),
        "queue": _load_csv(QUEUE_RISK_FILE, "phase4_queue_risk_summary", checks),
        "bottleneck": _load_csv(BOTTLENECK_FILE, "phase4_bottleneck_visibility_summary", checks),
        "quality_capacity": _load_csv(QUALITY_CAPACITY_FILE, "phase4_quality_adjusted_capacity_by_workstation", checks),
        "maintenance_schedule": _load_csv(MAINTENANCE_SCHEDULE_FILE, "phase4_maintenance_schedule_feasibility_context", checks),
        "maintenance_impact": _load_csv(MAINTENANCE_IMPACT_FILE, "phase4_maintenance_production_impact_context", checks),
        "inventory": _load_csv(INVENTORY_CHECK_FILE, "phase4_component_inventory_check", checks),
        "supplier": _load_csv(SUPPLIER_CHECK_FILE, "phase4_component_supplier_check", checks),
    }

    if all(frame is not None for frame in frames.values()):
        material = _build_material_readiness(frames)
        capacity = _build_capacity_checks(frames)
        candidates, details, calendar, review = _build_schedule_candidates(frames, material, capacity)
        _validate_outputs(frames, candidates, details, material, capacity, calendar, review, checks)
    else:
        candidates = _empty_schedule_candidates()
        details = _empty_operation_detail()
        material = _empty_material_readiness()
        capacity = _empty_capacity_check()
        calendar = _empty_calendar_view()
        review = _empty_manager_review()

    _check_no_forbidden_outputs(checks)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(SCHEDULE_CANDIDATES_OUTPUT_FILE, index=False)
    details.to_csv(OPERATION_DETAIL_OUTPUT_FILE, index=False)
    material.to_csv(MATERIAL_READINESS_OUTPUT_FILE, index=False)
    capacity.to_csv(CAPACITY_CHECK_OUTPUT_FILE, index=False)
    calendar.to_csv(CALENDAR_VIEW_OUTPUT_FILE, index=False)
    review.to_csv(MANAGER_REVIEW_OUTPUT_FILE, index=False)
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    return candidates, details, material, capacity, calendar, review, validation


def _build_schedule_candidates(frames: dict[str, pd.DataFrame], material: pd.DataFrame, capacity: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    mps = frames["mps"].copy()
    nodes = frames["nodes"].copy()
    edges = frames["edges"].copy()
    slack = frames["slack"].copy()
    queue = frames["queue"].copy()
    bottleneck = frames["bottleneck"].copy()
    maintenance_schedule = frames["maintenance_schedule"].copy()
    maintenance_impact = frames["maintenance_impact"].copy()

    planned_mps = mps[pd.to_numeric(mps["planned_production_qty"], errors="coerce").fillna(0) > 0].copy()
    planning_run_id = _planning_run_id([mps, nodes])
    predecessor_map, successor_map = _edge_maps(edges)
    topo_positions = _topological_positions(nodes, edges)
    queue_by_ws = _index_by(queue, "workstation_id")
    bottleneck_by_ws = _index_by(bottleneck, "workstation_id")
    maint_schedule_by_machine = _index_by(maintenance_schedule, "machine_id")
    maint_impact_by_machine = _index_by(maintenance_impact, "machine_id")
    slack_by_op = _index_by(slack, "operation_id")
    material_by_candidate = material.groupby("schedule_candidate_id") if not material.empty else {}
    capacity_by_candidate = capacity.groupby("schedule_candidate_id") if not capacity.empty else {}

    candidate_rows: list[dict] = []
    detail_rows: list[dict] = []
    calendar_rows: list[dict] = []
    review_rows: list[dict] = []
    review_id = 1

    for _, mps_row in planned_mps.iterrows():
        finished_sku = str(mps_row["finished_sku"])
        sku_nodes = nodes[nodes["finished_sku"].astype(str) == finished_sku].copy()
        if sku_nodes.empty:
            continue
        period_start = str(mps_row["period_start"])
        period_end = str(mps_row["period_end"])
        period_sequence = int(pd.to_numeric(mps_row.get("period_sequence", 1), errors="coerce") or 1)
        schedule_candidate_id = f"PSC-{finished_sku}-{period_start.replace('-', '')}"
        day = _candidate_day(period_start, period_sequence)
        shift = _candidate_shift(period_sequence)

        material_rows = material_by_candidate.get_group(schedule_candidate_id) if hasattr(material_by_candidate, "groups") and schedule_candidate_id in material_by_candidate.groups else pd.DataFrame()
        capacity_rows = capacity_by_candidate.get_group(schedule_candidate_id) if hasattr(capacity_by_candidate, "groups") and schedule_candidate_id in capacity_by_candidate.groups else pd.DataFrame()
        material_blocked = bool(_to_bool(material_rows.get("material_blocker_flag", pd.Series(dtype=object))).any()) if not material_rows.empty else True
        capacity_blocked = bool(_to_bool(capacity_rows.get("capacity_blocker_flag", pd.Series(dtype=object))).any()) if not capacity_rows.empty else True

        operation_blockers = []
        critical_path_risk = False
        bottleneck_risk = False
        queue_risk = False
        maintenance_blocked = False
        max_priority = 0.0

        for _, node in sku_nodes.sort_values("operation_sequence").iterrows():
            operation_id = str(node["operation_id"])
            machine_id = str(node.get("machine_id", ""))
            workstation_id = str(node["workstation_id"])
            slack_row = slack_by_op.get(operation_id, {})
            critical = _bool_value(slack_row.get("critical_path_flag", node.get("graph_node_type") == "START_OPERATION"))
            low_slack = _bool_value(slack_row.get("low_slack_warning_flag", False))
            queue_level = str(queue_by_ws.get(workstation_id, {}).get("overall_queue_risk_level", node.get("queue_risk_level", "LOW")))
            bottleneck_level = str(bottleneck_by_ws.get(workstation_id, {}).get("bottleneck_visibility_level", node.get("bottleneck_visibility_level", "LOW")))
            maint_schedule_status = str(maint_schedule_by_machine.get(machine_id, {}).get("best_schedule_feasibility_status", "FEASIBLE_CANDIDATE"))
            maint_blocker = str(maint_schedule_by_machine.get(machine_id, {}).get("main_schedule_blocker", "NONE"))
            maint_impact_level = str(maint_impact_by_machine.get(machine_id, {}).get("machine_availability_impact_level", node.get("maintenance_risk_context_level", "LOW")))
            op_maintenance_blocked = maint_schedule_status in {"BLOCKED_BY_CREW", "BLOCKED_BY_SPARE_PART", "BLOCKED_BY_PRODUCTION_IMPACT", "MULTI_BLOCKED", "REVIEW_REQUIRED"} or maint_impact_level in {"HIGH", "CRITICAL", "REVIEW_REQUIRED"}
            maintenance_blocked = maintenance_blocked or op_maintenance_blocked
            critical_path_risk = critical_path_risk or critical or low_slack
            bottleneck_risk = bottleneck_risk or bottleneck_level in {"HIGH", "CRITICAL", "REVIEW_REQUIRED"}
            queue_risk = queue_risk or queue_level in {"HIGH", "CRITICAL", "REVIEW_REQUIRED"}

            if op_maintenance_blocked:
                operation_blockers.append("MAINTENANCE")

            duration = float(pd.to_numeric(node.get("quality_adjusted_cycle_time_minutes", node.get("base_cycle_time_minutes", 0)), errors="coerce") or 0)
            es = float(pd.to_numeric(slack_row.get("earliest_start_offset_minutes", 0), errors="coerce") or 0)
            ef = float(pd.to_numeric(slack_row.get("earliest_finish_offset_minutes", es + duration), errors="coerce") or (es + duration))
            detail_rows.append({
                "planning_run_id": planning_run_id,
                "schedule_candidate_id": schedule_candidate_id,
                "finished_sku": finished_sku,
                "operation_id": operation_id,
                "operation_name": node.get("operation_name", ""),
                "operation_sequence": node.get("operation_sequence", ""),
                "predecessor_operation_ids": ";".join(predecessor_map.get(operation_id, [])),
                "successor_operation_ids": ";".join(successor_map.get(operation_id, [])),
                "workstation_id": workstation_id,
                "workstation_name": node.get("workstation_name", ""),
                "machine_id": machine_id,
                "machine_name": node.get("machine_name", ""),
                "candidate_schedule_period": period_start,
                "candidate_schedule_day": day,
                "candidate_schedule_shift": shift,
                "estimated_operation_duration_minutes": round(max(duration, 0), 4),
                "earliest_start_offset_minutes": round(max(es, 0), 4),
                "earliest_finish_offset_minutes": round(max(ef, 0), 4),
                "slack_time_minutes": round(max(float(pd.to_numeric(slack_row.get("slack_time_minutes", 0), errors="coerce") or 0), 0), 4),
                "critical_path_flag": bool(critical),
                "can_run_in_parallel_flag": _bool_value(node.get("can_run_in_parallel_flag", False)),
                "merge_operation_flag": str(node.get("graph_node_type", "")) == "MERGE_OPERATION",
                "operation_precedence_status": "PRECEDENCE_OK" if _predecessors_before(operation_id, predecessor_map, topo_positions) else "REVIEW_REQUIRED",
                "operation_schedule_status": "MAINTENANCE_REVIEW" if op_maintenance_blocked else "CANDIDATE_ONLY",
                "source_phase": SOURCE_PHASE,
                "advisory_only_flag": True,
            })
            priority = 10.0 + (30.0 if critical else 0.0) + (15.0 if low_slack else 0.0) + _risk_points(bottleneck_level) + _risk_points(queue_level) + _risk_points(maint_impact_level)
            max_priority = max(max_priority, priority)

            calendar_rows.append({
                "planning_run_id": planning_run_id,
                "candidate_schedule_period": period_start,
                "candidate_schedule_day": day,
                "candidate_schedule_shift": shift,
                "finished_sku": finished_sku,
                "operation_id": operation_id,
                "operation_name": node.get("operation_name", ""),
                "workstation_id": workstation_id,
                "machine_id": machine_id,
                "schedule_candidate_status": "REVIEW_REQUIRED",
                "recommended_schedule_priority": "REVIEW",
                "critical_path_flag": bool(critical),
                "bottleneck_risk_flag": bottleneck_level in {"HIGH", "CRITICAL", "REVIEW_REQUIRED"},
                "material_blocker_flag": material_blocked,
                "capacity_blocker_flag": capacity_blocked,
                "maintenance_blocker_flag": op_maintenance_blocked,
                "schedule_assignment_status": "NOT_SCHEDULED_CANDIDATE_ONLY",
                "source_phase": SOURCE_PHASE,
                "advisory_only_flag": True,
            })

        blocker_types = set()
        if material_blocked:
            blocker_types.add("MATERIAL")
        if capacity_blocked:
            blocker_types.add("CAPACITY")
        if maintenance_blocked:
            blocker_types.add("MAINTENANCE")
        blocker_types.update(operation_blockers)
        status = _candidate_status(blocker_types)
        priority_score = max_priority + (20.0 if material_blocked else 0.0) + (20.0 if capacity_blocked else 0.0) + (20.0 if maintenance_blocked else 0.0)
        recommended_priority = _priority_label(priority_score)
        material_status = _aggregate_material_status(material_rows)
        capacity_status = _aggregate_capacity_status(capacity_rows)
        maintenance_status = "MAINTENANCE_BLOCKED" if maintenance_blocked else "FEASIBLE"

        candidate_rows.append({
            "planning_run_id": planning_run_id,
            "schedule_candidate_id": schedule_candidate_id,
            "finished_sku": finished_sku,
            "finished_product_name": mps_row.get("finished_product_name", ""),
            "mps_period_start": period_start,
            "mps_period_end": period_end,
            "planned_production_qty": mps_row.get("planned_production_qty", 0),
            "candidate_schedule_period": period_start,
            "candidate_schedule_day": day,
            "candidate_schedule_shift": shift,
            "schedule_candidate_status": status,
            "schedule_priority_score": round(priority_score, 4),
            "recommended_schedule_priority": recommended_priority,
            "material_readiness_status": material_status,
            "capacity_feasibility_status": capacity_status,
            "maintenance_feasibility_status": maintenance_status,
            "critical_path_risk_flag": bool(critical_path_risk),
            "bottleneck_risk_flag": bool(bottleneck_risk),
            "queue_risk_flag": bool(queue_risk),
            "schedule_assignment_status": "NOT_SCHEDULED_CANDIDATE_ONLY",
            "note_no_production_order_created_flag": True,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })

        matching_calendar_idx = [i for i, row in enumerate(calendar_rows) if row["schedule_candidate_status"] == "REVIEW_REQUIRED" and row["finished_sku"] == finished_sku and row["candidate_schedule_period"] == period_start]
        for idx in matching_calendar_idx:
            calendar_rows[idx]["schedule_candidate_status"] = status
            calendar_rows[idx]["recommended_schedule_priority"] = recommended_priority

        for issue_type, severity, condition, description, action in [
            ("MATERIAL_BLOCKED_SCHEDULE_CANDIDATE", "HIGH", material_blocked, "Material readiness blocks or requires review for the advisory production schedule candidate.", "REVIEW_COMPONENT_AVAILABILITY"),
            ("CAPACITY_BLOCKED_SCHEDULE_CANDIDATE", "HIGH", capacity_blocked, "Capacity feasibility blocks or requires review for one or more operations.", "REVIEW_WORKSTATION_CAPACITY"),
            ("MAINTENANCE_BLOCKED_SCHEDULE_CANDIDATE", "HIGH", maintenance_blocked, "Maintenance feasibility or machine availability risk blocks or requires review.", "REVIEW_MAINTENANCE_WINDOW"),
            ("CRITICAL_PATH_SCHEDULE_RISK", "MEDIUM", critical_path_risk, "Candidate contains zero/low-slack critical-path operations.", "REVIEW_CRITICAL_PATH_SEQUENCE"),
            ("BOTTLENECK_SCHEDULE_RISK", "HIGH", bottleneck_risk, "Candidate touches high/critical bottleneck visibility workstations.", "REVIEW_BOTTLENECK_CAPACITY"),
            ("QUEUE_RISK_SCHEDULE_CANDIDATE", "HIGH", queue_risk, "Candidate touches high/critical estimated queue-risk workstations.", "REVIEW_QUEUE_PRESSURE"),
            ("MULTI_BLOCKED_SCHEDULE_CANDIDATE", "CRITICAL", status == "MULTI_BLOCKED", "Candidate has multiple blocker layers.", "REVIEW_BEFORE_ACTION"),
        ]:
            if condition:
                review_rows.append({
                    "review_item_id": f"PSR-{review_id:04d}",
                    "planning_run_id": planning_run_id,
                    "schedule_candidate_id": schedule_candidate_id,
                    "finished_sku": finished_sku,
                    "operation_id": "",
                    "issue_type": issue_type,
                    "issue_severity": severity,
                    "issue_description": description,
                    "recommended_review_action": action,
                    "auto_action_allowed": False,
                    "advisory_only_flag": True,
                })
                review_id += 1

    return (
        pd.DataFrame(candidate_rows, columns=_empty_schedule_candidates().columns),
        pd.DataFrame(detail_rows, columns=_empty_operation_detail().columns),
        pd.DataFrame(calendar_rows, columns=_empty_calendar_view().columns),
        pd.DataFrame(review_rows, columns=_empty_manager_review().columns),
    )


def _build_material_readiness(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    mps = frames["mps"].copy()
    pegging = frames["mrp_pegging"].copy()
    mrp_summary = frames["mrp_summary"].copy()
    inventory = frames["inventory"].copy()
    supplier = frames["supplier"].copy()
    planning_run_id = _planning_run_id([mps, pegging])
    inv_by_component = _index_by(inventory, "component_sku")
    sup_by_component = _index_by(supplier, "component_sku")
    mrp_by_period_component = _multi_index(mrp_summary, ["period_start", "component_sku"])
    planned_mps = mps[pd.to_numeric(mps["planned_production_qty"], errors="coerce").fillna(0) > 0].copy()
    rows: list[dict] = []

    for _, mps_row in planned_mps.iterrows():
        finished_sku = str(mps_row["finished_sku"])
        period_start = str(mps_row["period_start"])
        schedule_candidate_id = f"PSC-{finished_sku}-{period_start.replace('-', '')}"
        peg_rows = pegging[
            (pegging["finished_sku"].astype(str) == finished_sku)
            & (pegging["period_start"].astype(str) == period_start)
        ]
        for _, peg in peg_rows.iterrows():
            component = str(peg["component_sku"])
            inv = inv_by_component.get(component, {})
            sup = sup_by_component.get(component, {})
            mrp_rows = mrp_by_period_component.get((period_start, component), pd.DataFrame())
            mrp = mrp_rows.iloc[0].to_dict() if not mrp_rows.empty else {}
            required_qty = float(pd.to_numeric(peg.get("pegged_gross_component_requirement_qty", 0), errors="coerce") or 0)
            available_qty = float(pd.to_numeric(inv.get("available_qty", 0), errors="coerce") or 0)
            supplier_status = _supplier_status(sup)
            period_gross = float(pd.to_numeric(mrp.get("gross_component_requirement_qty", required_qty), errors="coerce") or required_qty)
            period_net = float(pd.to_numeric(mrp.get("net_component_requirement_qty", 0), errors="coerce") or 0)
            projected_ending = float(pd.to_numeric(mrp.get("projected_component_ending_inventory_qty", 0), errors="coerce") or 0)
            projected_shortage = float(pd.to_numeric(mrp.get("projected_component_shortage_qty", 0), errors="coerce") or 0)
            mrp_period_status = str(mrp.get("mrp_recommendation_status", "MISSING_MRP_PERIOD"))
            status, basis = _period_material_status(
                mrp,
                period_net,
                projected_ending,
                projected_shortage,
                supplier_status,
            )
            rows.append({
                "planning_run_id": planning_run_id,
                "schedule_candidate_id": schedule_candidate_id,
                "finished_sku": finished_sku,
                "component_sku": component,
                "required_qty": round(required_qty, 4),
                "available_qty": round(max(available_qty, 0), 4),
                "mrp_period_status": mrp_period_status,
                "period_gross_requirement_qty": round(max(period_gross, 0), 4),
                "period_net_requirement_qty": round(max(period_net, 0), 4),
                "projected_component_ending_inventory": round(max(projected_ending, 0), 4),
                "projected_component_shortage_qty": round(max(projected_shortage, 0), 4),
                "inventory_coverage_basis": basis,
                "supplier_coverage_status": supplier_status,
                "material_readiness_status": status,
                "material_blocker_flag": status in {"MATERIAL_BLOCKED", "MATERIAL_REVIEW_REQUIRED"},
                "note_no_inventory_consumption_flag": True,
                "note_no_inventory_reservation_flag": True,
                "source_phase": SOURCE_PHASE,
                "advisory_only_flag": True,
            })
    return pd.DataFrame(rows, columns=_empty_material_readiness().columns)


def _build_capacity_checks(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    mps = frames["mps"].copy()
    nodes = frames["nodes"].copy()
    ws_capacity = frames["workstation_capacity"].copy()
    machine_capacity = frames["machine_capacity"].copy()
    labor_capacity = frames["labor_capacity"].copy()
    quality_capacity = frames["quality_capacity"].copy()
    maintenance_impact = frames["maintenance_impact"].copy()
    planning_run_id = _planning_run_id([mps, nodes])
    planned_mps = mps[pd.to_numeric(mps["planned_production_qty"], errors="coerce").fillna(0) > 0].copy()
    machine_capacity_by_ws_period = _multi_index(machine_capacity, ["period_start", "workstation_id"])
    labor_capacity_by_ws_period = _multi_index(labor_capacity, ["period_start", "workstation_id"])
    quality_by_ws_period = _multi_index(quality_capacity, ["period_start", "workstation_id"])
    maintenance_by_machine = _index_by(maintenance_impact, "machine_id")
    rows: list[dict] = []

    for _, mps_row in planned_mps.iterrows():
        finished_sku = str(mps_row["finished_sku"])
        period_start = str(mps_row["period_start"])
        period_end = str(mps_row["period_end"])
        schedule_candidate_id = f"PSC-{finished_sku}-{period_start.replace('-', '')}"
        sku_nodes = nodes[nodes["finished_sku"].astype(str) == finished_sku].copy()
        for _, node in sku_nodes.iterrows():
            ws = str(node["workstation_id"])
            op = str(node["operation_id"])
            machine_id = str(node.get("machine_id", ""))
            ws_rows = ws_capacity[
                (ws_capacity["period_start"].astype(str) == period_start)
                & (ws_capacity["workstation_id"].astype(str) == ws)
            ]
            ws_row = ws_rows.iloc[0].to_dict() if not ws_rows.empty else {}
            machine_rows = machine_capacity_by_ws_period.get((period_start, ws), pd.DataFrame())
            labor_rows = labor_capacity_by_ws_period.get((period_start, ws), pd.DataFrame())
            q_row_df = quality_by_ws_period.get((period_start, ws), pd.DataFrame())
            q_row = q_row_df.iloc[0].to_dict() if not q_row_df.empty else {}
            maint = maintenance_by_machine.get(machine_id, {})
            required_hours = _operation_hours(node, mps_row)
            current_util = float(pd.to_numeric(ws_row.get("utilization_pct", 0), errors="coerce") or 0)
            qa_util = float(pd.to_numeric(q_row.get("quality_adjusted_utilization_pct", current_util), errors="coerce") or current_util)
            available_hours = float(pd.to_numeric(ws_row.get("available_hours", 0), errors="coerce") or 0)
            maintenance_level = str(maint.get("capacity_impact_level", maint.get("machine_availability_impact_level", "LOW")))
            capacity_status = _capacity_status(ws_row, machine_rows, labor_rows, q_row)
            rows.append({
                "planning_run_id": planning_run_id,
                "schedule_candidate_id": schedule_candidate_id,
                "operation_id": op,
                "workstation_id": ws,
                "machine_id": machine_id,
                "required_hours": round(max(required_hours, 0), 4),
                "available_hours_reference": round(max(available_hours, 0), 4),
                "current_utilization_pct": round(max(current_util, 0), 4),
                "quality_adjusted_utilization_pct": round(max(qa_util, 0), 4),
                "maintenance_impact_level": maintenance_level,
                "capacity_feasibility_status": capacity_status,
                "capacity_blocker_flag": capacity_status in {"CAPACITY_BLOCKED", "REVIEW_REQUIRED"},
                "note_no_capacity_change_flag": True,
                "source_phase": SOURCE_PHASE,
                "advisory_only_flag": True,
            })
    return pd.DataFrame(rows, columns=_empty_capacity_check().columns)


def _validate_outputs(frames: dict[str, pd.DataFrame], candidates: pd.DataFrame, details: pd.DataFrame, material: pd.DataFrame, capacity: pd.DataFrame, calendar: pd.DataFrame, review: pd.DataFrame, checks: list[dict]) -> None:
    outputs = {
        "production_schedule_candidates": candidates,
        "operation_schedule_candidate_detail": details,
        "production_schedule_material_readiness": material,
        "production_schedule_capacity_check": capacity,
        "production_calendar_candidate_view": calendar,
        "production_schedule_manager_review_queue": review,
    }
    for name, frame in outputs.items():
        checks.append(_check(name, "PASS" if not frame.empty else "FAIL", f"{name} row_count={len(frame)}", len(frame)))

    required = {
        "production_schedule_candidates": set(_empty_schedule_candidates().columns),
        "operation_schedule_candidate_detail": set(_empty_operation_detail().columns),
        "production_schedule_material_readiness": set(_empty_material_readiness().columns),
        "production_schedule_capacity_check": set(_empty_capacity_check().columns),
        "production_calendar_candidate_view": set(_empty_calendar_view().columns),
        "production_schedule_manager_review_queue": set(_empty_manager_review().columns),
    }
    for name, columns in required.items():
        missing = sorted(columns.difference(outputs[name].columns))
        checks.append(_check(f"{name}_required_columns", "PASS" if not missing else "FAIL", f"missing={missing}", len(missing)))

    products = set(candidates["finished_sku"].astype(str)) if not candidates.empty else set()
    checks.append(_check("road_and_mountain_bike_included", "PASS" if {"SKU-BIKE-ROAD-001", "SKU-BIKE-MT-001"}.issubset(products) else "FAIL", f"products={sorted(products)}", len(products)))
    mps_positive = frames["mps"][pd.to_numeric(frames["mps"]["planned_production_qty"], errors="coerce").fillna(0) > 0]
    checks.append(_check("positive_mps_rows_generate_candidates", "PASS" if len(candidates) == len(mps_positive) else "FAIL", f"candidate_rows={len(candidates)}, positive_mps_rows={len(mps_positive)}", abs(len(candidates) - len(mps_positive))))
    checks.append(_check("operation_precedence_respected", "PASS" if not details.empty and (details["operation_precedence_status"].astype(str) == "PRECEDENCE_OK").all() else "FAIL", "All operation candidate detail rows should have precedence OK.", 0))
    checks.append(_check("parallel_operations_represented", "PASS" if _to_bool(details.get("can_run_in_parallel_flag", pd.Series(dtype=object))).any() else "FAIL", "Parallel operation detail rows are represented.", int(_to_bool(details.get("can_run_in_parallel_flag", pd.Series(dtype=object))).sum())))
    checks.append(_check("merge_operations_represented", "PASS" if _to_bool(details.get("merge_operation_flag", pd.Series(dtype=object))).any() else "FAIL", "Merge operation detail rows are represented.", int(_to_bool(details.get("merge_operation_flag", pd.Series(dtype=object))).sum())))
    final_detail = details[details["operation_name"].astype(str).str.contains("Final Assembly", case=False, na=False)] if not details.empty else pd.DataFrame()
    final_ok = not final_detail.empty and _to_bool(final_detail["merge_operation_flag"]).all() and final_detail["predecessor_operation_ids"].astype(str).str.len().gt(0).all()
    checks.append(_check("final_assembly_waits_for_branches", "PASS" if final_ok else "FAIL", "Final Assembly candidate rows are merge operations with predecessors.", len(final_detail)))
    checks.append(_check("critical_path_flags_carried", "PASS" if _to_bool(details.get("critical_path_flag", pd.Series(dtype=object))).any() else "FAIL", "Critical path flags carried from Step 8A.", int(_to_bool(details.get("critical_path_flag", pd.Series(dtype=object))).sum())))

    checks.append(_check("no_inventory_consumption", "PASS" if _all_true(material, "note_no_inventory_consumption_flag") else "FAIL", "Material readiness does not consume inventory.", len(material)))
    checks.append(_check("no_inventory_reservation", "PASS" if _all_true(material, "note_no_inventory_reservation_flag") else "FAIL", "Material readiness does not reserve inventory.", len(material)))
    checks.append(_check("no_capacity_change", "PASS" if _all_true(capacity, "note_no_capacity_change_flag") else "FAIL", "Capacity check does not modify capacity.", len(capacity)))
    covered_period_rows = material[
        (pd.to_numeric(material["period_net_requirement_qty"], errors="coerce").fillna(0) <= 0)
        & (pd.to_numeric(material["projected_component_ending_inventory"], errors="coerce").fillna(0) > 0)
        & (pd.to_numeric(material["projected_component_shortage_qty"], errors="coerce").fillna(0) <= 0)
    ]
    covered_period_blockers = covered_period_rows[_to_bool(covered_period_rows["material_blocker_flag"])]
    all_inventory_review = not material.empty and material["material_readiness_status"].astype(str).eq("INVENTORY_REVIEW_REQUIRED").all()
    checks.append(_check("period_mrp_material_readiness_used", "PASS" if not (all_inventory_review and not covered_period_rows.empty) else "FAIL", "Material readiness must use period-level MRP and not mark all rows as horizon inventory review.", len(covered_period_rows)))
    checks.append(_check("covered_period_rows_not_blocked", "PASS" if covered_period_blockers.empty else "FAIL", f"covered_period_blocker_rows={len(covered_period_blockers)}", len(covered_period_blockers)))
    maintenance_capacity_rows = capacity[capacity["capacity_feasibility_status"].astype(str).eq("MAINTENANCE_REVIEW_REQUIRED")]
    checks.append(_check("capacity_maintenance_status_separated", "PASS" if maintenance_capacity_rows.empty else "FAIL", "Capacity feasibility status must not contain MAINTENANCE_REVIEW_REQUIRED.", len(maintenance_capacity_rows)))
    checks.append(_check("no_production_order_created", "PASS" if _all_true(candidates, "note_no_production_order_created_flag") else "FAIL", "No production orders created.", len(candidates)))
    checks.append(_check("candidate_assignment_only", "PASS" if set(candidates["schedule_assignment_status"].dropna().astype(str)) <= VALID_ASSIGNMENT_STATUS and set(calendar["schedule_assignment_status"].dropna().astype(str)) <= VALID_ASSIGNMENT_STATUS else "FAIL", "Schedule assignment status remains candidate-only.", len(candidates) + len(calendar)))
    for name, frame in outputs.items():
        checks.append(_check(f"{name}_advisory_only", "PASS" if _all_true(frame, "advisory_only_flag") else "FAIL", f"{name} advisory-only flag true.", len(frame)))
    checks.append(_check("manager_review_no_auto_action", "PASS" if _all_false(review, "auto_action_allowed") else "FAIL", "Manager review queue has auto_action_allowed False.", len(review)))
    checks.append(_check("valid_schedule_candidate_statuses", "PASS" if set(candidates["schedule_candidate_status"].dropna().astype(str)) <= VALID_SCHEDULE_STATUSES else "FAIL", f"statuses={sorted(set(candidates['schedule_candidate_status'].astype(str)))}", len(candidates)))


def _check_no_forbidden_outputs(checks: list[dict]) -> None:
    blocked_tokens = [
        "released_production_order",
        "confirmed_production_schedule",
        "worker_dispatch",
        "inventory_consumption",
        "inventory_reservation",
        "purchase_order",
        "capacity_reduction",
        "simulation",
    ]
    bad_files = []
    for path in OUTPUT_DIR.glob("*"):
        lower = path.name.lower()
        if any(token in lower for token in blocked_tokens):
            bad_files.append(path.name)
    checks.append(_check("no_forbidden_step8b_outputs", "PASS" if not bad_files else "FAIL", f"forbidden_outputs={bad_files}", len(bad_files)))


def _edge_maps(edges: pd.DataFrame) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    pred: dict[str, list[str]] = defaultdict(list)
    succ: dict[str, list[str]] = defaultdict(list)
    for _, edge in edges.iterrows():
        from_op = str(edge["from_operation_id"])
        to_op = str(edge["to_operation_id"])
        succ[from_op].append(to_op)
        pred[to_op].append(from_op)
    return {key: sorted(value) for key, value in pred.items()}, {key: sorted(value) for key, value in succ.items()}


def _topological_positions(nodes: pd.DataFrame, edges: pd.DataFrame) -> dict[str, int]:
    positions: dict[str, int] = {}
    for sku, sku_nodes in nodes.groupby("finished_sku"):
        op_ids = [str(v) for v in sku_nodes.sort_values("operation_sequence")["operation_id"]]
        indegree = {op: 0 for op in op_ids}
        graph = {op: [] for op in op_ids}
        sku_edges = edges[edges["finished_sku"].astype(str) == str(sku)]
        for _, edge in sku_edges.iterrows():
            from_op = str(edge["from_operation_id"])
            to_op = str(edge["to_operation_id"])
            if from_op in graph and to_op in indegree:
                graph[from_op].append(to_op)
                indegree[to_op] += 1
        queue = deque([op for op in op_ids if indegree[op] == 0])
        order: list[str] = []
        while queue:
            op = queue.popleft()
            order.append(op)
            for nxt in graph.get(op, []):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        if len(order) != len(op_ids):
            order = op_ids
        positions.update({op: idx for idx, op in enumerate(order)})
    return positions


def _predecessors_before(operation_id: str, predecessor_map: dict[str, list[str]], positions: dict[str, int]) -> bool:
    position = positions.get(operation_id, 0)
    return all(positions.get(pred, -1) < position for pred in predecessor_map.get(operation_id, []))


def _operation_hours(node: pd.Series, mps_row: pd.Series) -> float:
    minutes = float(pd.to_numeric(node.get("quality_adjusted_cycle_time_minutes", node.get("base_cycle_time_minutes", 0)), errors="coerce") or 0)
    qty = float(pd.to_numeric(mps_row.get("planned_production_qty", 0), errors="coerce") or 0)
    return minutes * qty / 60.0


def _candidate_status(blocker_types: set[str]) -> str:
    if len(blocker_types) > 1:
        return "MULTI_BLOCKED"
    if "MATERIAL" in blocker_types:
        return "MATERIAL_BLOCKED"
    if "CAPACITY" in blocker_types:
        return "CAPACITY_BLOCKED"
    if "MAINTENANCE" in blocker_types:
        return "MAINTENANCE_BLOCKED"
    return "FEASIBLE_CANDIDATE"


def _aggregate_material_status(material_rows: pd.DataFrame) -> str:
    if material_rows.empty:
        return "MATERIAL_REVIEW_REQUIRED"
    statuses = set(material_rows["material_readiness_status"].astype(str))
    if "MATERIAL_BLOCKED" in statuses:
        return "MATERIAL_BLOCKED"
    if "MATERIAL_REVIEW_REQUIRED" in statuses:
        return "MATERIAL_REVIEW_REQUIRED"
    if "INVENTORY_REVIEW_REQUIRED" in statuses:
        return "INVENTORY_REVIEW_REQUIRED"
    if "SUPPLIER_COVERED_REVIEW" in statuses:
        return "SUPPLIER_COVERED_REVIEW"
    return "MATERIAL_READY"


def _aggregate_capacity_status(capacity_rows: pd.DataFrame) -> str:
    if capacity_rows.empty:
        return "REVIEW_REQUIRED"
    statuses = set(capacity_rows["capacity_feasibility_status"].astype(str))
    if "CAPACITY_BLOCKED" in statuses:
        return "CAPACITY_BLOCKED"
    if "MAINTENANCE_REVIEW_REQUIRED" in statuses:
        return "MAINTENANCE_REVIEW_REQUIRED"
    if "REVIEW_REQUIRED" in statuses:
        return "REVIEW_REQUIRED"
    if "HIGH_UTILIZATION_WARNING" in statuses:
        return "HIGH_UTILIZATION_WARNING"
    return "FEASIBLE"


def _period_material_status(mrp: dict, period_net: float, projected_ending: float, projected_shortage: float, supplier_status: str) -> tuple[str, str]:
    if not mrp:
        return "MATERIAL_REVIEW_REQUIRED", "MISSING_DATA_REVIEW"
    if (period_net <= 0 or projected_ending > 0) and projected_shortage <= 0:
        return "MATERIAL_READY", "PERIOD_LEVEL_MRP_PROJECTED_INVENTORY"
    if projected_shortage > 0 and supplier_status in {"NO_SUPPLIER_COVERAGE", "REVIEW_REQUIRED"}:
        return "MATERIAL_BLOCKED", "MISSING_DATA_REVIEW"
    if period_net > 0 and supplier_status in {"COVERED", "LIMITED_COVERAGE"}:
        return "SUPPLIER_COVERED_REVIEW", "SUPPLIER_COVERAGE_REVIEW"
    if projected_shortage > 0:
        return "INVENTORY_REVIEW_REQUIRED", "HORIZON_INVENTORY_CHECK_FALLBACK"
    return "MATERIAL_REVIEW_REQUIRED", "MISSING_DATA_REVIEW"


def _supplier_status(row: dict) -> str:
    if not row:
        return "NO_SUPPLIER_COVERAGE"
    available = _bool_value(row.get("supplier_available_flag", False))
    review = _bool_value(row.get("supplier_review_required_flag", False))
    if available and not review:
        return "COVERED"
    if available:
        return "LIMITED_COVERAGE"
    return "NO_SUPPLIER_COVERAGE"


def _capacity_status(ws_row: dict, machine_rows: pd.DataFrame, labor_rows: pd.DataFrame, q_row: dict) -> str:
    if not ws_row:
        return "REVIEW_REQUIRED"
    ws_status = str(ws_row.get("capacity_status", "REVIEW_REQUIRED"))
    quality_status = str(q_row.get("quality_adjusted_capacity_status", ws_status))
    machine_blocked = not machine_rows.empty and machine_rows["machine_capacity_status"].astype(str).isin(["OVERLOADED", "NO_CAPACITY_RECORD", "REVIEW_REQUIRED"]).any()
    labor_blocked = not labor_rows.empty and labor_rows["labor_capacity_status"].astype(str).isin(["OVERLOADED", "NO_CAPACITY_RECORD", "REVIEW_REQUIRED"]).any()
    labor_warn = not labor_rows.empty and labor_rows["labor_capacity_status"].astype(str).isin(["HIGH_UTILIZATION_WARNING"]).any()
    if ws_status in {"OVERLOADED", "NO_CAPACITY_RECORD", "REVIEW_REQUIRED"} or quality_status in {"OVERLOADED", "NO_CAPACITY_RECORD", "REVIEW_REQUIRED"} or machine_blocked or labor_blocked:
        return "CAPACITY_BLOCKED"
    if ws_status == "NEAR_CAPACITY" or quality_status == "HIGH_UTILIZATION_WARNING" or labor_warn:
        return "HIGH_UTILIZATION_WARNING"
    return "FEASIBLE"


def _priority_label(score: float) -> str:
    if score >= 120:
        return "CRITICAL"
    if score >= 80:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _risk_points(level: str) -> float:
    return {"CRITICAL": 35.0, "HIGH": 25.0, "MEDIUM": 10.0, "LOW": 0.0, "REVIEW_REQUIRED": 30.0}.get(str(level), 0.0)


def _candidate_day(period_start: str, period_sequence: int) -> str:
    try:
        return (pd.to_datetime(period_start) + pd.Timedelta(days=(period_sequence - 1) % 5)).date().isoformat()
    except Exception:
        return f"PERIOD_DAY_{((period_sequence - 1) % 5) + 1}"


def _candidate_shift(period_sequence: int) -> str:
    return "SHIFT-A" if period_sequence % 2 else "SHIFT-B"


def _load_csv(path: Path, label: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_check(f"load_{label}", "FAIL", f"Missing input: {path}", 0))
        return None
    frame = pd.read_csv(path)
    checks.append(_check(f"load_{label}", "PASS" if not frame.empty else "FAIL", f"{label} rows={len(frame)}", len(frame)))
    return frame


def _index_by(frame: pd.DataFrame, column: str) -> dict[str, dict]:
    if frame.empty or column not in frame.columns:
        return {}
    return {str(row[column]): row.to_dict() for _, row in frame.iterrows()}


def _multi_index(frame: pd.DataFrame, columns: list[str]) -> dict[tuple[str, ...], pd.DataFrame]:
    if frame.empty or any(column not in frame.columns for column in columns):
        return {}
    result = {}
    for key, group in frame.groupby(columns):
        if not isinstance(key, tuple):
            key = (key,)
        result[tuple(str(part) for part in key)] = group
    return result


def _planning_run_id(frames: list[pd.DataFrame]) -> str:
    for frame in frames:
        if frame is not None and not frame.empty and "planning_run_id" in frame.columns:
            values = frame["planning_run_id"].dropna().astype(str).str.strip()
            if not values.empty:
                return values.iloc[0]
    return "PHASE4-STEP8B-UNKNOWN"


def _bool_value(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _all_true(frame: pd.DataFrame, column: str) -> bool:
    return column in frame.columns and bool(_to_bool(frame[column]).all())


def _all_false(frame: pd.DataFrame, column: str) -> bool:
    return column in frame.columns and bool(~_to_bool(frame[column]).any())


def _check(check_id: str, status: str, message: str, affected_rows: int = 0) -> dict:
    return {
        "check_id": check_id,
        "check_name": check_id.replace("_", " ").title(),
        "status": status,
        "message": message,
        "affected_rows": int(affected_rows),
        "advisory_only_flag": True,
    }


def _empty_schedule_candidates() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "schedule_candidate_id", "finished_sku", "finished_product_name", "mps_period_start", "mps_period_end",
        "planned_production_qty", "candidate_schedule_period", "candidate_schedule_day", "candidate_schedule_shift",
        "schedule_candidate_status", "schedule_priority_score", "recommended_schedule_priority", "material_readiness_status",
        "capacity_feasibility_status", "maintenance_feasibility_status", "critical_path_risk_flag", "bottleneck_risk_flag",
        "queue_risk_flag", "schedule_assignment_status", "note_no_production_order_created_flag", "source_phase", "advisory_only_flag",
    ])


def _empty_operation_detail() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "schedule_candidate_id", "finished_sku", "operation_id", "operation_name", "operation_sequence",
        "predecessor_operation_ids", "successor_operation_ids", "workstation_id", "workstation_name", "machine_id", "machine_name",
        "candidate_schedule_period", "candidate_schedule_day", "candidate_schedule_shift", "estimated_operation_duration_minutes",
        "earliest_start_offset_minutes", "earliest_finish_offset_minutes", "slack_time_minutes", "critical_path_flag",
        "can_run_in_parallel_flag", "merge_operation_flag", "operation_precedence_status", "operation_schedule_status",
        "source_phase", "advisory_only_flag",
    ])


def _empty_material_readiness() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "schedule_candidate_id", "finished_sku", "component_sku", "required_qty", "available_qty",
        "mrp_period_status", "period_gross_requirement_qty", "period_net_requirement_qty", "projected_component_ending_inventory",
        "projected_component_shortage_qty", "inventory_coverage_basis", "supplier_coverage_status",
        "material_readiness_status", "material_blocker_flag", "note_no_inventory_consumption_flag",
        "note_no_inventory_reservation_flag", "source_phase", "advisory_only_flag",
    ])


def _empty_capacity_check() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "schedule_candidate_id", "operation_id", "workstation_id", "machine_id", "required_hours",
        "available_hours_reference", "current_utilization_pct", "quality_adjusted_utilization_pct", "maintenance_impact_level",
        "capacity_feasibility_status", "capacity_blocker_flag", "note_no_capacity_change_flag", "source_phase", "advisory_only_flag",
    ])


def _empty_calendar_view() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "candidate_schedule_period", "candidate_schedule_day", "candidate_schedule_shift", "finished_sku",
        "operation_id", "operation_name", "workstation_id", "machine_id", "schedule_candidate_status", "recommended_schedule_priority",
        "critical_path_flag", "bottleneck_risk_flag", "material_blocker_flag", "capacity_blocker_flag", "maintenance_blocker_flag",
        "schedule_assignment_status", "source_phase", "advisory_only_flag",
    ])


def _empty_manager_review() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "review_item_id", "planning_run_id", "schedule_candidate_id", "finished_sku", "operation_id", "issue_type",
        "issue_severity", "issue_description", "recommended_review_action", "auto_action_allowed", "advisory_only_flag",
    ])


if __name__ == "__main__":
    outputs = build_production_schedule_candidate_outputs()
    print(f"Production schedule candidate rows: {len(outputs[0])}")
    print(f"Production schedule validation rows: {len(outputs[-1])}")
