"""Build advisory WIP- and setup-aware finite-capacity schedule alternatives.

This module uses a transparent greedy heuristic. It allocates candidate
operations against dated resource windows but does not create a confirmed
schedule, production order, dispatch record, reservation, consumption, or
capacity reduction.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE4_DIR.parent
DATA_DIR = PHASE4_DIR / "data"
OUTPUT_DIR = PHASE4_DIR / "outputs"
SHARED_DATA_DIR = PROJECT_ROOT / "shared" / "data"

RESOURCE_CALENDAR_FILE = DATA_DIR / "resource_calendar.csv"
WORKSTATIONS_FILE = DATA_DIR / "workstations.csv"
MACHINES_FILE = DATA_DIR / "machines.csv"
LABOR_FILE = DATA_DIR / "labor_resources.csv"
ROUTING_RESOURCES_FILE = DATA_DIR / "routing_operation_resources.csv"
COST_ASSUMPTIONS_FILE = DATA_DIR / "schedule_cost_assumptions.csv"

MPS_FILE = OUTPUT_DIR / "phase4_master_production_schedule.csv"
MRP_SUMMARY_FILE = OUTPUT_DIR / "phase4_mrp_component_period_summary.csv"
SCHEDULE_CANDIDATES_FILE = OUTPUT_DIR / "phase4_production_schedule_candidates.csv"
SCHEDULE_DETAIL_FILE = OUTPUT_DIR / "phase4_operation_schedule_candidate_detail.csv"
MATERIAL_READINESS_FILE = OUTPUT_DIR / "phase4_production_schedule_material_readiness.csv"
CAPACITY_CHECK_FILE = OUTPUT_DIR / "phase4_production_schedule_capacity_check.csv"
WIP_ITEM_MASTER_FILE = OUTPUT_DIR / "phase4_wip_item_master.csv"
WIP_FLOW_MAP_FILE = OUTPUT_DIR / "phase4_wip_operation_flow_map.csv"
WIP_LEDGER_FILE = OUTPUT_DIR / "phase4_wip_batch_ledger.csv"
WIP_BUFFER_STATUS_FILE = OUTPUT_DIR / "phase4_wip_buffer_status.csv"
WIP_BUFFER_LOCATIONS_FILE = DATA_DIR / "wip_buffer_locations.csv"
WIP_AWARE_FILE = OUTPUT_DIR / "phase4_wip_aware_schedule_feasibility.csv"
WIP_BALANCE_FILE = OUTPUT_DIR / "phase4_wip_supply_demand_balance.csv"
WIP_BUFFER_IMPACT_FILE = OUTPUT_DIR / "phase4_wip_buffer_impact_on_schedule.csv"
WIP_ACCESS_RULES_FILE = OUTPUT_DIR / "phase4_wip_buffer_access_rules.csv"
WIP_ACCESS_VALIDATION_FILE = OUTPUT_DIR / "phase4_wip_buffer_access_validation.csv"
SETUP_FAMILY_FILE = OUTPUT_DIR / "phase4_setup_family_master.csv"
CHANGEOVER_MATRIX_FILE = OUTPUT_DIR / "phase4_setup_changeover_matrix.csv"
SETUP_PROFILE_FILE = OUTPUT_DIR / "phase4_operation_setup_profile.csv"
SETUP_SEQUENCE_FILE = OUTPUT_DIR / "phase4_setup_sequence_impact_analysis.csv"
WORKSTATION_CAPACITY_FILE = OUTPUT_DIR / "phase4_capacity_load_by_workstation.csv"
MACHINE_CAPACITY_FILE = OUTPUT_DIR / "phase4_capacity_load_by_machine_type.csv"
LABOR_CAPACITY_FILE = OUTPUT_DIR / "phase4_capacity_load_by_labor_skill.csv"
BOTTLENECK_FILE = OUTPUT_DIR / "phase4_bottleneck_visibility_summary.csv"
QUEUE_FILE = OUTPUT_DIR / "phase4_queue_risk_summary.csv"
QUALITY_CAPACITY_FILE = OUTPUT_DIR / "phase4_quality_adjusted_capacity_by_workstation.csv"
MAINTENANCE_SCHEDULE_FILE = OUTPUT_DIR / "phase4_maintenance_schedule_feasibility_context.csv"
MAINTENANCE_IMPACT_FILE = OUTPUT_DIR / "phase4_maintenance_production_impact_context.csv"
BREAKDOWN_FILE = OUTPUT_DIR / "phase4_breakdown_risk_context.csv"

ALTERNATIVE_MASTER_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_master.csv"
ALTERNATIVE_OPERATION_DETAIL_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_operation_detail.csv"
ALTERNATIVE_CAPACITY_IMPACT_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_capacity_impact.csv"
ALTERNATIVE_WIP_IMPACT_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_wip_impact.csv"
ALTERNATIVE_SETUP_IMPACT_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_setup_impact.csv"
ALTERNATIVE_MAINTENANCE_IMPACT_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_maintenance_impact.csv"
ALTERNATIVE_COST_SCORE_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_cost_score.csv"
ALTERNATIVE_RECOMMENDATIONS_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_recommendations.csv"
ALTERNATIVE_MANAGER_REVIEW_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_manager_review_queue.csv"
ALTERNATIVE_VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_validation.csv"
ALTERNATIVE_OPERATION_SEGMENTS_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_operation_segments.csv"
ALTERNATIVE_QUANTITY_FLOW_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_quantity_flow.csv"
ALTERNATIVE_SHADOW_WIP_LEDGER_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_shadow_wip_ledger.csv"
ALTERNATIVE_MAINTENANCE_WINDOW_CHECK_OUTPUT_FILE = OUTPUT_DIR / "phase4_schedule_alternative_maintenance_window_check.csv"

SOURCE_PHASE = "PHASE4_STEP8F_FINITE_CAPACITY_SCHEDULE_ALTERNATIVES"
SHIFT_ID = "SHIFT-A"
ALTERNATIVES = [
    ("ALT-BASELINE", "BASELINE_FROM_STEP_8B", "Baseline from Step 8B", "Forward schedules Step 8B candidates in original routing order."),
    ("ALT-BN-CP", "BOTTLENECK_CRITICAL_PATH_PRIORITY", "Bottleneck and critical path priority", "Prioritizes zero-slack, merge, and bottleneck-sensitive operations."),
    ("ALT-SETUP", "SETUP_REDUCTION_BATCHING", "Setup reduction batching", "Uses setup-family priority when multiple operations are ready."),
    ("ALT-WIP", "WIP_PROTECTED_CONTINUITY", "WIP protected continuity", "Uses accepted WIP and buffer capacity evidence without consuming WIP."),
    ("ALT-MAINT", "MAINTENANCE_AWARE_SHIFTING", "Maintenance-aware shifting", "Searches later valid windows when maintenance conflict exists."),
    ("ALT-COMBINED", "LEAST_RISK_COMBINED", "Least-risk combined", "Combines critical-path priority, setup awareness, WIP continuity, and maintenance-aware search."),
]
VALID_HARD_STATUS = {"HARD_FEASIBLE", "HARD_FEASIBLE_WITH_REVIEW", "PARTIAL_FINITE_SCHEDULE", "HARD_INFEASIBLE", "NO_COMPLETE_SCHEDULE", "REVIEW_REQUIRED"}


def build_schedule_alternative_outputs() -> tuple[pd.DataFrame, ...]:
    _ensure_cost_assumptions()
    checks: list[dict] = []
    frames = {
        "resource_calendar": _load_csv(RESOURCE_CALENDAR_FILE, "resource_calendar", checks),
        "workstations": _load_csv(WORKSTATIONS_FILE, "workstations", checks),
        "machines": _load_csv(MACHINES_FILE, "machines", checks),
        "labor": _load_csv(LABOR_FILE, "labor_resources", checks),
        "routing_resources": _load_csv(ROUTING_RESOURCES_FILE, "routing_operation_resources", checks),
        "cost_assumptions": _load_csv(COST_ASSUMPTIONS_FILE, "schedule_cost_assumptions", checks),
        "mps": _load_csv(MPS_FILE, "phase4_master_production_schedule", checks),
        "mrp": _load_csv(MRP_SUMMARY_FILE, "phase4_mrp_component_period_summary", checks),
        "candidates": _load_csv(SCHEDULE_CANDIDATES_FILE, "phase4_production_schedule_candidates", checks),
        "detail": _load_csv(SCHEDULE_DETAIL_FILE, "phase4_operation_schedule_candidate_detail", checks),
        "material": _load_csv(MATERIAL_READINESS_FILE, "phase4_production_schedule_material_readiness", checks),
        "capacity": _load_csv(CAPACITY_CHECK_FILE, "phase4_production_schedule_capacity_check", checks),
        "wip_items": _load_csv(WIP_ITEM_MASTER_FILE, "phase4_wip_item_master", checks),
        "wip_flow": _load_csv(WIP_FLOW_MAP_FILE, "phase4_wip_operation_flow_map", checks),
        "wip_ledger": _load_csv(WIP_LEDGER_FILE, "phase4_wip_batch_ledger", checks),
        "wip_buffers": _load_csv(WIP_BUFFER_STATUS_FILE, "phase4_wip_buffer_status", checks),
        "wip_buffer_locations": _load_csv(WIP_BUFFER_LOCATIONS_FILE, "wip_buffer_locations", checks),
        "wip_aware": _load_csv(WIP_AWARE_FILE, "phase4_wip_aware_schedule_feasibility", checks),
        "wip_balance": _load_csv(WIP_BALANCE_FILE, "phase4_wip_supply_demand_balance", checks),
        "wip_buffer_impact": _load_csv(WIP_BUFFER_IMPACT_FILE, "phase4_wip_buffer_impact_on_schedule", checks),
        "wip_access_rules": _load_csv(WIP_ACCESS_RULES_FILE, "phase4_wip_buffer_access_rules", checks),
        "wip_access_validation": _load_csv(WIP_ACCESS_VALIDATION_FILE, "phase4_wip_buffer_access_validation", checks),
        "setup_family": _load_csv(SETUP_FAMILY_FILE, "phase4_setup_family_master", checks),
        "changeover": _load_csv(CHANGEOVER_MATRIX_FILE, "phase4_setup_changeover_matrix", checks),
        "setup_profile": _load_csv(SETUP_PROFILE_FILE, "phase4_operation_setup_profile", checks),
        "setup_sequence": _load_csv(SETUP_SEQUENCE_FILE, "phase4_setup_sequence_impact_analysis", checks),
        "workstation_capacity": _load_csv(WORKSTATION_CAPACITY_FILE, "phase4_capacity_load_by_workstation", checks),
        "machine_capacity": _load_csv(MACHINE_CAPACITY_FILE, "phase4_capacity_load_by_machine_type", checks),
        "labor_capacity": _load_csv(LABOR_CAPACITY_FILE, "phase4_capacity_load_by_labor_skill", checks),
        "bottleneck": _load_csv(BOTTLENECK_FILE, "phase4_bottleneck_visibility_summary", checks),
        "queue": _load_csv(QUEUE_FILE, "phase4_queue_risk_summary", checks),
        "quality_capacity": _load_csv(QUALITY_CAPACITY_FILE, "phase4_quality_adjusted_capacity_by_workstation", checks),
        "maintenance_schedule": _load_csv(MAINTENANCE_SCHEDULE_FILE, "phase4_maintenance_schedule_feasibility_context", checks),
        "maintenance_impact": _load_csv(MAINTENANCE_IMPACT_FILE, "phase4_maintenance_production_impact_context", checks),
        "breakdown": _load_csv(BREAKDOWN_FILE, "phase4_breakdown_risk_context", checks),
    }
    if all(frame is not None for frame in frames.values()):
        frames["wip_buffers"] = _merge_buffer_policy(frames["wip_buffers"], frames["wip_buffer_locations"])
        built = _build_all_alternatives(frames)
        master, operation_detail, capacity_impact, wip_impact, setup_impact, maintenance_impact, cost_score, recommendations, review, operation_segments, quantity_flow, shadow_wip, maintenance_windows = built
        _validate_outputs(frames, master, operation_detail, capacity_impact, wip_impact, setup_impact, maintenance_impact, cost_score, recommendations, review, operation_segments, quantity_flow, shadow_wip, maintenance_windows, checks)
    else:
        master = _empty_master()
        operation_detail = _empty_operation_detail()
        capacity_impact = _empty_capacity_impact()
        wip_impact = _empty_wip_impact()
        setup_impact = _empty_setup_impact()
        maintenance_impact = _empty_maintenance_impact()
        cost_score = _empty_cost_score()
        recommendations = _empty_recommendations()
        review = _empty_review()
        operation_segments = _empty_operation_segments()
        quantity_flow = _empty_quantity_flow()
        shadow_wip = _empty_shadow_wip()
        maintenance_windows = _empty_maintenance_window_check()
    _check_no_forbidden_outputs(checks)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    master.to_csv(ALTERNATIVE_MASTER_OUTPUT_FILE, index=False)
    operation_detail.to_csv(ALTERNATIVE_OPERATION_DETAIL_OUTPUT_FILE, index=False)
    capacity_impact.to_csv(ALTERNATIVE_CAPACITY_IMPACT_OUTPUT_FILE, index=False)
    wip_impact.to_csv(ALTERNATIVE_WIP_IMPACT_OUTPUT_FILE, index=False)
    setup_impact.to_csv(ALTERNATIVE_SETUP_IMPACT_OUTPUT_FILE, index=False)
    maintenance_impact.to_csv(ALTERNATIVE_MAINTENANCE_IMPACT_OUTPUT_FILE, index=False)
    cost_score.to_csv(ALTERNATIVE_COST_SCORE_OUTPUT_FILE, index=False)
    recommendations.to_csv(ALTERNATIVE_RECOMMENDATIONS_OUTPUT_FILE, index=False)
    review.to_csv(ALTERNATIVE_MANAGER_REVIEW_OUTPUT_FILE, index=False)
    operation_segments.to_csv(ALTERNATIVE_OPERATION_SEGMENTS_OUTPUT_FILE, index=False)
    quantity_flow.to_csv(ALTERNATIVE_QUANTITY_FLOW_OUTPUT_FILE, index=False)
    shadow_wip.to_csv(ALTERNATIVE_SHADOW_WIP_LEDGER_OUTPUT_FILE, index=False)
    maintenance_windows.to_csv(ALTERNATIVE_MAINTENANCE_WINDOW_CHECK_OUTPUT_FILE, index=False)
    validation.to_csv(ALTERNATIVE_VALIDATION_OUTPUT_FILE, index=False)
    return master, operation_detail, capacity_impact, wip_impact, setup_impact, maintenance_impact, cost_score, recommendations, review, validation


def _build_all_alternatives(frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, ...]:
    all_ops: list[dict] = []
    all_capacity: list[dict] = []
    all_wip: list[dict] = []
    all_setup: list[dict] = []
    all_maint: list[dict] = []
    summaries = []
    baseline_setup_by_op: dict[tuple[str, str], float] = {}
    for alt_id, alt_type, alt_name, alt_desc in ALTERNATIVES:
        result = _schedule_alternative(frames, alt_id, alt_type)
        if alt_type == "BASELINE_FROM_STEP_8B":
            baseline_setup_by_op = {(row["schedule_candidate_id"], row["operation_id"]): row["actual_sequence_setup_minutes"] for row in result["operations"]}
        _apply_setup_savings(result["setup"], baseline_setup_by_op)
        all_ops.extend(result["operations"])
        all_capacity.extend(result["capacity"])
        all_wip.extend(result["wip"])
        all_setup.extend(result["setup"])
        all_maint.extend(result["maintenance"])
        summaries.append({**result["summary"], "alternative_name": alt_name, "alternative_description": alt_desc})
    operation_detail = pd.DataFrame(all_ops, columns=_empty_operation_detail().columns)
    capacity_impact = pd.DataFrame(all_capacity, columns=_empty_capacity_impact().columns)
    wip_impact = pd.DataFrame(all_wip, columns=_empty_wip_impact().columns)
    setup_impact = pd.DataFrame(all_setup, columns=_empty_setup_impact().columns)
    maintenance_impact = pd.DataFrame(all_maint, columns=_empty_maintenance_impact().columns)
    operation_detail, operation_segments, quantity_flow, shadow_wip, maintenance_windows, summaries = _reconcile_quantity_segments_and_shadow_wip(
        frames, operation_detail, setup_impact, maintenance_impact, summaries
    )
    setup_impact = _sync_setup_impact_from_segments(setup_impact, operation_segments, operation_detail)
    wip_impact = _sync_wip_buffer_evidence_from_detail(wip_impact, operation_detail)
    cost_score = _build_cost_score(frames, summaries, operation_detail, capacity_impact, wip_impact, setup_impact, maintenance_impact, operation_segments)
    master = _build_master(frames, summaries, cost_score)
    recommendations = _build_recommendations(master)
    review = _build_review_queue(master, operation_detail, capacity_impact, wip_impact, setup_impact, maintenance_impact, recommendations)
    return master, operation_detail, capacity_impact, wip_impact, setup_impact, maintenance_impact, cost_score, recommendations, review, operation_segments, quantity_flow, shadow_wip, maintenance_windows


def _schedule_alternative(frames: dict[str, pd.DataFrame], alt_id: str, alt_type: str) -> dict:
    planning_run_id = _planning_run_id(frames)
    windows = _build_windows(frames)
    ledgers = {
        "workstation": {key: value["available_minutes"] for key, value in windows["workstation"].items()},
        "machine": {key: value["available_minutes"] for key, value in windows["machine"].items()},
        "labor": {key: value["available_minutes"] for key, value in windows["labor"].items()},
        "machine_busy_end": {},
    }
    detail = frames["detail"].copy()
    candidates = _index_by(frames["candidates"], "schedule_candidate_id")
    capacity_by_op = _index_by2(frames["capacity"], "schedule_candidate_id", "operation_id")
    routing_by_op = _index_by2(frames["routing_resources"], "finished_sku", "operation_id")
    setup_profile = _index_by2(frames["setup_profile"], "finished_sku", "operation_id")
    material_by_candidate = frames["material"].groupby("schedule_candidate_id", dropna=False)["material_blocker_flag"].apply(lambda s: bool(_to_bool(s).any())).to_dict()
    wip_by_key = _first_by2(frames["wip_aware"], "schedule_candidate_id", "operation_id")
    wip_inputs_by_key = _group_by2(frames["wip_aware"], "schedule_candidate_id", "operation_id")
    wip_flow = frames["wip_flow"].copy()
    buffer_by_id = _index_by(frames["wip_buffers"], "wip_buffer_id")
    maint_by_machine = _index_by(frames["maintenance_impact"], "machine_id")
    breakdown_by_machine = _index_by(frames["breakdown"], "machine_id")
    bottleneck_by_ws = _index_by(frames["bottleneck"], "workstation_id")
    queue_by_ws = _index_by(frames["queue"], "workstation_id")
    changeover = _changeover_lookup(frames["changeover"])
    op_rows = detail.to_dict("records")
    op_by_key = {(str(r["schedule_candidate_id"]), str(r["operation_id"])): r for r in op_rows}
    successors, predecessors = _candidate_graph(op_rows)
    unscheduled = set(op_by_key)
    completed: dict[tuple[str, str], datetime] = {}
    completed_qty: dict[tuple[str, str], float] = {}
    evaluated: set[tuple[str, str]] = set()
    horizon_start = _parse_date(str(detail["candidate_schedule_period"].min()))
    live_shadow_lots = _seed_shadow_lots(_starting_wip_by_item_buffer(frames["wip_ledger"]), horizon_start)
    live_buffer_events = _seed_buffer_events(_starting_wip_by_item_buffer(frames["wip_ledger"]), horizon_start)
    sched_qty: dict[tuple[str, str], float] = {}
    last_setup_by_ws: dict[str, tuple[str, str, str]] = {}
    operation_rows: list[dict] = []
    capacity_rows: list[dict] = []
    wip_rows: list[dict] = []
    setup_rows: list[dict] = []
    maintenance_rows: list[dict] = []

    while unscheduled:
        ready = [key for key in unscheduled if all(pred in evaluated or _wip_covers_predecessor(pred, key, wip_inputs_by_key) for pred in predecessors.get(key, []))]
        if not ready:
            key = sorted(unscheduled)[0]
            ready = [key]
        key = _choose_ready_key(ready, op_by_key, alt_type, setup_profile, bottleneck_by_ws, queue_by_ws, last_setup_by_ws)
        unscheduled.remove(key)
        op = op_by_key[key]
        candidate_id = str(op["schedule_candidate_id"])
        operation_id = str(op["operation_id"])
        candidate = candidates[candidate_id]
        route_res = routing_by_op.get((str(op["finished_sku"]), operation_id), {})
        setup = setup_profile.get((str(op["finished_sku"]), operation_id), {})
        cap_ref = capacity_by_op.get((candidate_id, operation_id), {})
        wip = wip_by_key.get((candidate_id, operation_id), {})
        input_rows = wip_inputs_by_key.get((candidate_id, operation_id), [])
        machine_id = str(op["machine_id"])
        workstation_id = str(op["workstation_id"])
        labor_skill = str(route_res.get("required_labor_skill", ""))
        requested_qty = _num(candidate.get("planned_production_qty"))
        step8b_required_minutes = max(_num(cap_ref.get("required_hours")) * 60.0, 0.0)
        per_unit_minutes = step8b_required_minutes / requested_qty if requested_qty > 0 and step8b_required_minutes > 0 else _num(op.get("estimated_operation_duration_minutes"))
        quantity_support = _calculate_live_quantity_support(
            key,
            op,
            requested_qty,
            predecessors,
            completed,
            completed_qty,
            live_shadow_lots,
            wip_flow,
            buffer_by_id,
        )
        quantity_supported_before_capacity = _num(quantity_support["quantity_supported_before_capacity"])
        scheduling_target_qty = min(requested_qty, quantity_supported_before_capacity)
        pred_ready = quantity_support["input_quantity_availability_datetime"] or _parse_date(str(op["candidate_schedule_period"]))
        buffer_support = _empty_buffer_support(op, scheduling_target_qty, wip_flow, buffer_by_id)
        buffer_blocked_qty = 0.0
        family_id = "" if _blank(setup.get("setup_family_id", "")) else str(setup["setup_family_id"])
        prev_op, prev_family, prev_candidate = last_setup_by_ws.get(workstation_id, ("", "", ""))
        setup_minutes = _lookup_changeover(changeover, workstation_id, prev_family, family_id)
        if not prev_family or scheduling_target_qty <= 0.0001:
            setup_minutes = 0.0
        material_blocked = bool(material_by_candidate.get(candidate_id, False))
        original_maint_conflict = _maintenance_conflict(maint_by_machine.get(machine_id, {}))
        remaining_wip_blocker = _remaining_wip_blocker(input_rows, requested_qty, alt_type)
        workload_basis = "STEP8B_REQUIRED_HOURS" if step8b_required_minutes > 0 else "QUANTITY_X_ROUTING_TIME_PLUS_SETUP"
        required_machine_count = max(int(_num(route_res.get("required_machine_count"))), 1)
        required_worker_count = max(int(_num(route_res.get("required_worker_count"))), 1)
        if scheduling_target_qty <= 0.0001:
            blocker_reason = "OUTPUT_BUFFER_CAPACITY_BLOCK" if buffer_blocked_qty > 0.0001 else "NO_PREDECESSOR_OR_SHADOW_WIP_QUANTITY_AVAILABLE"
            placement = _blank_placement("FINITE_CAPACITY_BLOCKED", blocker_reason)
            placement["resource_profile"] = _resource_profile_for_operation(windows, workstation_id, machine_id, labor_skill, required_machine_count, required_worker_count)
            processing_total = 0.0
            total_requested = 0.0
        else:
            placement, scheduled_qty_candidate, scheduling_target_qty, processing_total, total_requested, buffer_support, ledgers = _place_with_time_aware_buffer(
                windows=windows,
                ledgers=ledgers,
                workstation_id=workstation_id,
                machine_id=machine_id,
                labor_skill=labor_skill,
                pred_ready=pred_ready,
                requested_qty=requested_qty,
                initial_target_qty=scheduling_target_qty,
                per_unit_minutes=per_unit_minutes,
                setup_minutes=setup_minutes,
                required_machine_count=required_machine_count,
                required_worker_count=required_worker_count,
                alt_type=alt_type,
                original_maint_conflict=original_maint_conflict,
                maint_row=maint_by_machine.get(machine_id, {}),
                op=op,
                live_buffer_events=live_buffer_events,
                flow=wip_flow,
                buffers=buffer_by_id,
            )
            buffer_blocked_qty = _num(buffer_support["buffer_blocked_output_qty"])
        scheduled = placement["scheduled"]
        allocated_processing = _num(placement.get("allocated_processing_minutes", max(placement["allocated_minutes"] - setup_minutes, 0.0))) if scheduled else 0.0
        if scheduled and placement["allocated_minutes"] < total_requested:
            scheduled_qty = min(scheduling_target_qty, allocated_processing / per_unit_minutes) if per_unit_minutes > 0 else 0.0
            workload_basis = "PARTIAL_QUANTITY_CAPACITY_LIMIT"
        elif scheduled:
            scheduled_qty = scheduling_target_qty
        else:
            scheduled_qty = 0.0
            workload_basis = "REVIEW_REQUIRED"
        if scheduled:
            completed[key] = placement["end_dt"]
            completed_qty[key] = scheduled_qty
            sched_qty[key] = scheduled_qty
            if family_id:
                last_setup_by_ws[workstation_id] = (operation_id, family_id, candidate_id)
        evaluated.add(key)
        _apply_live_shadow_draws_and_production(
            key,
            op,
            scheduled_qty,
            placement.get("start_dt"),
            placement.get("end_dt"),
            quantity_support,
            live_shadow_lots,
            wip_flow,
            buffer_by_id,
        )
        _record_live_buffer_events(
            key,
            op,
            scheduled_qty,
            placement.get("start_dt"),
            placement.get("end_dt"),
            quantity_support,
            live_buffer_events,
            wip_flow,
            buffer_by_id,
        )
        precedence_ok = all(pred in evaluated or _wip_covers_predecessor(pred, key, wip_inputs_by_key) for pred in predecessors.get(key, []))
        merge_ok = not _bool(op.get("merge_operation_flag")) or precedence_ok
        operation_status = _operation_status(scheduled, scheduled_qty, requested_qty, material_blocked, remaining_wip_blocker, placement["capacity_status"], placement["selected_maintenance_conflict"])
        hard_status = _operation_hard_status(scheduled, precedence_ok, merge_ok, operation_status, placement["capacity_status"])
        resource_profile = placement.get("resource_profile", {})
        placement_segments = placement.get("segments", [])
        assigned_machine_units = _join_unique([unit for segment in placement_segments for unit in str(segment.get("assigned_machine_unit_ids", "")).split(";")])
        assigned_labor_units = _join_unique([unit for segment in placement_segments for unit in str(segment.get("assigned_labor_unit_ids", "")).split(";")])
        resource_bundle_change_count = sum(
            1
            for prev, cur in zip(
                [(str(segment.get("assigned_machine_unit_ids", "")), str(segment.get("assigned_labor_unit_ids", ""))) for segment in placement_segments],
                [(str(segment.get("assigned_machine_unit_ids", "")), str(segment.get("assigned_labor_unit_ids", ""))) for segment in placement_segments][1:],
            )
            if prev != cur
        )
        row_common = {
            "planning_run_id": planning_run_id,
            "alternative_id": alt_id,
            "alternative_type": alt_type,
            "schedule_candidate_id": candidate_id,
            "finished_sku": op["finished_sku"],
            "operation_id": operation_id,
            "operation_name": op["operation_name"],
            "operation_sequence": op["operation_sequence"],
            "workstation_id": workstation_id,
            "machine_id": machine_id,
            "candidate_schedule_period": op["candidate_schedule_period"],
            "candidate_schedule_day": op["candidate_schedule_day"],
            "candidate_schedule_shift": op["candidate_schedule_shift"],
            "proposed_schedule_period": placement["date"],
            "proposed_schedule_day": placement["date"],
            "proposed_schedule_shift": placement["shift"],
            "proposed_schedule_date": placement["date"],
            "proposed_shift_id": placement["shift"],
            "proposed_start_datetime": placement["start"],
            "proposed_end_datetime": placement["end"],
            "proposed_window_id": placement["window_id"],
            "predecessor_operation_ids": "" if _blank(op.get("predecessor_operation_ids")) else op.get("predecessor_operation_ids", ""),
            "successor_operation_ids": "" if _blank(op.get("successor_operation_ids")) else op.get("successor_operation_ids", ""),
            "critical_path_flag": _bool(op.get("critical_path_flag")),
            "merge_operation_flag": _bool(op.get("merge_operation_flag")),
            "parallel_branch_flag": _bool(op.get("can_run_in_parallel_flag")),
            "required_input_wip_item_id": _join_unique([r.get("required_input_wip_item_id", "") for r in input_rows]),
            "output_wip_item_id": "" if _blank(wip.get("output_wip_item_id", "")) else wip.get("output_wip_item_id", ""),
            "wip_buffer_id": buffer_support["output_wip_buffer_id"] or _join_unique([r.get("related_wip_buffer_id", "") for r in input_rows]),
            "setup_family_id": family_id,
            "estimated_processing_time_minutes": round(processing_total, 4),
            "estimated_setup_time_minutes": round(setup_minutes, 4),
            "estimated_total_time_minutes": round(total_requested, 4),
            "requested_production_qty": round(requested_qty, 4),
            "schedulable_production_qty": round(scheduled_qty, 4),
            "quantity_supported_before_capacity": round(quantity_supported_before_capacity, 4),
            "scheduling_target_qty": round(scheduling_target_qty, 4),
            "capacity_scheduled_qty": round(scheduled_qty, 4),
            "final_reconciled_scheduled_qty": round(scheduled_qty, 4),
            "post_schedule_quantity_adjustment_qty": 0.0,
            "post_schedule_quantity_adjustment_flag": False,
            "input_quantity_availability_datetime": pred_ready.isoformat(timespec="minutes") if pred_ready else "",
            "quantity_support_status": quantity_support["quantity_support_status"],
            "quantity_support_blocker_reason": quantity_support["quantity_support_blocker_reason"],
            "resource_reserved_for_supported_qty_flag": bool(scheduled_qty > 0 or scheduling_target_qty <= 0.0001),
            "buffer_capacity_before_production": round(_num(buffer_support["buffer_capacity_before_production"]), 4),
            "buffer_balance_before_production": round(_num(buffer_support["buffer_balance_before_production"]), 4),
            "available_buffer_space_qty": round(_num(buffer_support["available_buffer_space_qty"]), 4),
            "buffer_supported_output_qty": round(_num(buffer_support["buffer_supported_output_qty"]), 4),
            "buffer_blocked_output_qty": round(buffer_blocked_qty, 4),
            "allowed_buffer_capacity_qty": round(_num(buffer_support["allowed_buffer_capacity_qty"]), 4),
            "overflow_policy": buffer_support["overflow_policy"],
            "buffer_capacity_status": buffer_support["buffer_capacity_status"],
            "buffer_capacity_blocker_reason": buffer_support["buffer_capacity_blocker_reason"],
            "buffer_check_datetime": buffer_support["buffer_check_datetime"],
            "projected_balance_at_completion": round(_num(buffer_support["projected_balance_at_completion"]), 4),
            "projected_space_at_completion": round(_num(buffer_support["projected_space_at_completion"]), 4),
            "buffer_release_datetime": buffer_support["buffer_release_datetime"],
            "buffer_delay_minutes": round(_num(buffer_support["buffer_delay_minutes"]), 4),
            "buffer_reservation_qty": round(_num(buffer_support["buffer_reservation_qty"]), 4),
            "buffer_reservation_status": buffer_support["buffer_reservation_status"],
            "buffer_search_attempt_count": int(_num(buffer_support["buffer_search_attempt_count"])),
            "processing_minutes_per_unit": round(per_unit_minutes, 6),
            "processing_minutes_total": round(processing_total, 4),
            "actual_sequence_setup_minutes": round(setup_minutes, 4),
            "total_required_minutes": round(total_requested, 4),
            "required_hours_total": round(total_requested / 60.0, 4),
            "workload_calculation_basis": workload_basis,
            "effective_parallel_lane_count": max(int(_num(resource_profile.get("effective_parallel_lane_count", 1))), 1),
            "parallel_capacity_applied_flag": _bool(resource_profile.get("parallel_capacity_applied_flag")),
            "assigned_machine_unit_ids": assigned_machine_units,
            "assigned_labor_unit_ids": assigned_labor_units,
            "resource_bundle_change_count": resource_bundle_change_count,
            "resource_bundle_assignment_status": "RESOURCE_BUNDLE_ASSIGNED" if scheduled and assigned_machine_units and assigned_labor_units else "RESOURCE_BUNDLE_NOT_ASSIGNED",
            "predecessor_ready_datetime": pred_ready.isoformat(timespec="minutes"),
            "precedence_check_status": "PRECEDENCE_OK" if precedence_ok else "PRECEDENCE_VIOLATION",
            "merge_input_completion_status": "MERGE_INPUTS_READY" if merge_ok else "MERGE_INPUTS_NOT_READY",
            "precedence_violation_flag": scheduled and (not precedence_ok or not merge_ok),
            "operation_hard_feasibility_status": hard_status,
            "operation_schedule_status": operation_status,
            "schedule_blocker_reason": placement["reason"],
            "segment_schedule_json": _segment_schedule_json(placement.get("segments", []), scheduling_target_qty, processing_total),
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        }
        operation_rows.append(row_common)
        _append_capacity_row(capacity_rows, row_common, route_res, placement, cap_ref)
        _append_wip_row(wip_rows, row_common, input_rows, buffer_by_id, requested_qty, scheduled_qty, alt_type)
        _append_setup_row(setup_rows, row_common, prev_op, prev_family, family_id, setup_minutes)
        _append_maintenance_row(maintenance_rows, row_common, maint_by_machine.get(machine_id, {}), breakdown_by_machine.get(machine_id, {}), original_maint_conflict, placement)
    summary = _alternative_summary(frames, alt_id, alt_type, operation_rows)
    return {"operations": operation_rows, "capacity": capacity_rows, "wip": wip_rows, "setup": setup_rows, "maintenance": maintenance_rows, "summary": summary}


def _find_window(windows: dict, ledgers: dict, workstation_id: str, machine_id: str, labor_skill: str, earliest: datetime, total_minutes: float, processing_minutes: float, setup_minutes: float, required_machine_count: int, required_worker_count: int, alt_type: str, original_maint_conflict: bool, maint_row: dict) -> dict:
    sorted_windows = sorted(windows["base"].values(), key=lambda w: w["start_dt"])
    resource_profile = _resource_profile_for_operation(windows, workstation_id, machine_id, labor_skill, required_machine_count, required_worker_count)
    segments: list[dict] = []
    remaining_processing = max(processing_minutes, 0.0)
    search_after = earliest
    preferred_machine_units: tuple[str, ...] | None = None
    preferred_labor_units: tuple[str, ...] | None = None
    for window in sorted_windows:
        if remaining_processing <= 0.0001:
            break
        if window["end_dt"] <= search_after:
            continue
        # Step 8F Patch 2: maintenance risk alone is not horizon-wide downtime.
        # Only dated maintenance reservations would block a specific interval; none are execution-created here.
        keys = _resource_keys(window["date"], window["shift"], workstation_id, machine_id, labor_skill)
        workstation_available = windows["workstation"].get(keys["workstation"], {}).get("available_minutes", 0.0)
        machine_available = windows["machine"].get(keys["machine"], {}).get("available_minutes", 0.0)
        labor_available = windows["labor"].get(keys["labor"], {}).get("available_minutes", 10**9) if labor_skill else 10**9
        setup_for_segment = setup_minutes if not segments else 0.0
        bundle = _find_resource_bundle(
            window,
            ledgers,
            resource_profile,
            search_after,
            setup_for_segment,
            remaining_processing,
            preferred_machine_units,
            preferred_labor_units,
        )
        if bundle is None:
            continue
        start_offset = bundle["start_offset"]
        remaining = bundle["available_minutes"]
        if remaining <= setup_for_segment + 0.0001:
            continue
        segment_total = min(remaining, remaining_processing + setup_for_segment)
        segment_processing = max(segment_total - setup_for_segment, 0.0)
        if segment_processing <= 0.0001:
            continue
        start = window["start_dt"] + timedelta(minutes=start_offset)
        end = start + timedelta(minutes=segment_total)
        if end > window["end_dt"]:
            end = window["end_dt"]
            segment_total = max((end - start).total_seconds() / 60.0, 0.0)
            segment_processing = max(segment_total - setup_for_segment, 0.0)
        if segment_total < 1.0 or segment_processing <= 0.0001:
            search_after = max(search_after, end)
            continue
        for ledger_name in ["workstation", "machine", "labor"]:
            if ledger_name == "labor" and not labor_skill:
                continue
            ledgers[ledger_name][keys[ledger_name]] = max(ledgers[ledger_name].get(keys[ledger_name], 0.0) - segment_total, 0.0)
        remaining_processing = max(remaining_processing - segment_processing, 0.0)
        search_after = end
        ledgers.setdefault("workstation_lane_busy_end", {})[(window["date"], window["shift"], bundle["parallel_lane_id"])] = end
        for unit_id in bundle["machine_unit_ids"]:
            ledgers.setdefault("machine_unit_busy_end", {})[(window["date"], window["shift"], unit_id)] = end
        for unit_id in bundle["labor_unit_ids"]:
            ledgers.setdefault("labor_unit_busy_end", {})[(window["date"], window["shift"], unit_id)] = end
        changed_bundle = False
        current_machine_units = tuple(bundle["machine_unit_ids"])
        current_labor_units = tuple(bundle["labor_unit_ids"])
        if preferred_machine_units is None:
            preferred_machine_units = current_machine_units
            preferred_labor_units = current_labor_units
        else:
            changed_bundle = current_machine_units != preferred_machine_units or current_labor_units != preferred_labor_units
        available_reference = min(
            windows["workstation"].get(keys["workstation"], {}).get("available_minutes", 0.0),
            windows["machine"].get(keys["machine"], {}).get("available_minutes", 0.0),
            windows["labor"].get(keys["labor"], {}).get("available_minutes", 0.0) if labor_skill else 10**9,
        )
        segments.append({
            "date": window["date"],
            "shift": window["shift"],
            "window_id": window["window_id"],
            "start": start.isoformat(timespec="minutes"),
            "end": end.isoformat(timespec="minutes"),
            "start_dt": start,
            "end_dt": end,
            "keys": keys,
            "available_minutes": available_reference,
            "allocated_minutes": segment_total,
            "processing_minutes": segment_processing,
            "setup_minutes": setup_for_segment,
            "remaining_minutes": min(ledgers["workstation"].get(keys["workstation"], 0.0), ledgers["machine"].get(keys["machine"], 0.0)),
            "parallel_capacity_applied_flag": resource_profile["parallel_capacity_applied_flag"],
            "effective_parallel_lane_count": resource_profile["effective_parallel_lane_count"],
            "parallel_lane_id": bundle["parallel_lane_id"],
            "assigned_machine_unit_ids": ";".join(bundle["machine_unit_ids"]),
            "assigned_labor_unit_ids": ";".join(bundle["labor_unit_ids"]),
            "required_machine_count": required_machine_count,
            "required_worker_count": required_worker_count,
            "workstation_parallel_authorized_flag": resource_profile["workstation_parallel_authorized_flag"],
            "labor_parallel_authorized_flag": resource_profile["labor_parallel_authorized_flag"],
            "resource_bundle_status": "RESOURCE_BUNDLE_ASSIGNED",
            "continuation_resource_bundle_changed_flag": changed_bundle,
        })
    if not segments:
        placement = _blank_placement("FINITE_CAPACITY_BLOCKED", "No real calendar window has enough remaining cumulative capacity.")
        placement["resource_profile"] = resource_profile
        return placement
    allocated = sum(_num(segment["allocated_minutes"]) for segment in segments)
    allocated_processing = sum(_num(segment["processing_minutes"]) for segment in segments)
    first = segments[0]
    last = segments[-1]
    cap_status = "FINITE_CAPACITY_FEASIBLE" if allocated_processing + 0.0001 >= processing_minutes else "FINITE_CAPACITY_PARTIAL_QUANTITY"
    selected_conflict = False
    return {
        "scheduled": True,
        "date": first["date"],
        "shift": first["shift"],
        "window_id": ";".join(segment["window_id"] for segment in segments),
        "start": first["start"],
        "end": last["end"],
        "start_dt": first["start_dt"],
        "end_dt": last["end_dt"],
        "keys": last["keys"],
        "available_minutes": sum(_num(segment["available_minutes"]) for segment in segments),
        "previously_allocated_minutes": 0.0,
        "allocated_minutes": allocated,
        "allocated_processing_minutes": allocated_processing,
        "remaining_minutes": _num(last["remaining_minutes"]),
        "overload_minutes": max(total_minutes - allocated, 0.0),
        "capacity_status": cap_status,
        "selected_maintenance_conflict": selected_conflict,
        "selected_maintenance_status": "FEASIBLE" if not selected_conflict else "MAINTENANCE_REVIEW_REQUIRED",
        "reason": "Allocated across real dated resource calendar window(s).",
        "segments": segments,
        "resource_profile": resource_profile,
    }


def _place_with_time_aware_buffer(
    *,
    windows: dict,
    ledgers: dict,
    workstation_id: str,
    machine_id: str,
    labor_skill: str,
    pred_ready: datetime,
    requested_qty: float,
    initial_target_qty: float,
    per_unit_minutes: float,
    setup_minutes: float,
    required_machine_count: int,
    required_worker_count: int,
    alt_type: str,
    original_maint_conflict: bool,
    maint_row: dict,
    op: dict,
    live_buffer_events: list[dict],
    flow: pd.DataFrame,
    buffers: dict[str, dict],
) -> tuple[dict, float, float, float, float, dict, dict]:
    target_qty = max(initial_target_qty, 0.0)
    earliest = pred_ready
    attempts = 0
    last_buffer_support = _empty_buffer_support(op, target_qty, flow, buffers)
    while attempts < 8 and target_qty > 0.0001:
        attempts += 1
        processing_minutes = target_qty * per_unit_minutes
        total_minutes = processing_minutes + setup_minutes
        attempt_ledgers = _clone_ledgers(ledgers)
        placement = _find_window(
            windows,
            attempt_ledgers,
            workstation_id,
            machine_id,
            labor_skill,
            earliest,
            total_minutes,
            processing_minutes,
            setup_minutes,
            required_machine_count,
            required_worker_count,
            alt_type,
            original_maint_conflict,
            maint_row,
        )
        if not placement["scheduled"]:
            placement["reason"] = placement["reason"] if attempts == 1 else f"{placement['reason']} Buffer retry attempts={attempts}."
            last_buffer_support["buffer_search_attempt_count"] = attempts
            return placement, 0.0, target_qty, processing_minutes, total_minutes, last_buffer_support, ledgers
        allocated_processing = _num(placement.get("allocated_processing_minutes", max(_num(placement.get("allocated_minutes")) - setup_minutes, 0.0)))
        provisional_qty = target_qty if placement["allocated_minutes"] + 0.0001 >= total_minutes else min(target_qty, allocated_processing / per_unit_minutes) if per_unit_minutes > 0 else 0.0
        completion_dt = placement.get("end_dt")
        buffer_support = _calculate_output_buffer_support_at_datetime(
            op,
            requested_qty,
            provisional_qty,
            live_buffer_events,
            flow,
            buffers,
            completion_dt,
            attempts,
        )
        last_buffer_support = buffer_support
        supported_at_completion = min(provisional_qty, _num(buffer_support["buffer_supported_output_qty"]))
        if supported_at_completion + 0.0001 >= provisional_qty:
            placement["reason"] = f"{placement['reason']} Output buffer space reserved at completion time."
            return placement, provisional_qty, target_qty, processing_minutes, total_minutes, buffer_support, attempt_ledgers
        release_dt = _next_output_buffer_release_datetime(op, live_buffer_events, flow, buffers, completion_dt)
        if release_dt and release_dt > completion_dt and attempts < 7:
            earliest = release_dt
            continue
        if supported_at_completion > 0.0001 and supported_at_completion + 0.0001 < target_qty:
            target_qty = supported_at_completion
            earliest = pred_ready
            continue
        blocked = _blank_placement("FINITE_CAPACITY_BLOCKED", "OUTPUT_BUFFER_CAPACITY_BLOCK")
        blocked["resource_profile"] = placement.get("resource_profile", {})
        blocked["reason"] = "OUTPUT_BUFFER_CAPACITY_BLOCK"
        buffer_support["buffer_search_attempt_count"] = attempts
        return blocked, 0.0, 0.0, 0.0, 0.0, buffer_support, ledgers
    blocked = _blank_placement("FINITE_CAPACITY_BLOCKED", "OUTPUT_BUFFER_CAPACITY_BLOCK")
    blocked["resource_profile"] = _resource_profile_for_operation(windows, workstation_id, machine_id, labor_skill, required_machine_count, required_worker_count)
    last_buffer_support["buffer_search_attempt_count"] = attempts
    return blocked, 0.0, 0.0, 0.0, 0.0, last_buffer_support, ledgers


def _clone_ledgers(ledgers: dict) -> dict:
    cloned = {}
    for key, value in ledgers.items():
        cloned[key] = dict(value) if isinstance(value, dict) else value
    return cloned


def _blank_placement(status: str, reason: str) -> dict:
    return {
        "scheduled": False,
        "date": "",
        "shift": "",
        "window_id": "",
        "start": "",
        "end": "",
        "start_dt": None,
        "end_dt": None,
        "keys": {},
        "available_minutes": 0.0,
        "previously_allocated_minutes": 0.0,
        "allocated_minutes": 0.0,
        "remaining_minutes": 0.0,
        "overload_minutes": 0.0,
        "capacity_status": status,
        "selected_maintenance_conflict": False,
        "selected_maintenance_status": "REVIEW_REQUIRED",
        "reason": reason,
        "segments": [],
        "resource_profile": {},
    }


def _calculate_live_quantity_support(
    key: tuple[str, str],
    op: dict,
    requested_qty: float,
    predecessors: dict,
    completed: dict[tuple[str, str], datetime],
    completed_qty: dict[tuple[str, str], float],
    shadow_lots: dict[tuple[str, str], list[dict]],
    flow: pd.DataFrame,
    buffers: dict[str, dict],
) -> dict:
    candidate_id, operation_id = key
    sku = str(op["finished_sku"])
    input_rows = flow[(flow["finished_sku"].astype(str) == sku) & (flow["consumed_by_operation_id"].astype(str) == operation_id)]
    pred_ids = [str(value) for value in input_rows["produced_by_operation_id"].dropna().astype(str).unique() if str(value).strip()] or _split_ids(op.get("predecessor_operation_ids", ""))
    base_ready = _parse_date(str(op.get("candidate_schedule_period", "")))
    if not pred_ids:
        return {
            "quantity_supported_before_capacity": requested_qty,
            "input_quantity_availability_datetime": base_ready,
            "quantity_support_status": "NO_INPUT_REQUIRED_FIRST_OPERATION",
            "quantity_support_blocker_reason": "",
            "input_evidence": [],
        }
    supported = []
    ready_datetimes = []
    evidence = []
    blocker = ""
    for pred in pred_ids:
        direct_flow = input_rows[input_rows["produced_by_operation_id"].astype(str) == pred]
        flow_row = direct_flow.iloc[0].to_dict() if not direct_flow.empty else {}
        wip_item = str(flow_row.get("wip_item_id", ""))
        buffer_id = _buffer_for_wip(buffers, wip_item)
        balance_key = (wip_item, buffer_id)
        available = _lot_remaining_qty(shadow_lots, balance_key) if wip_item else _num(completed_qty.get((candidate_id, pred), 0.0))
        ratio = 1.0
        supported_qty = available / ratio if ratio > 0 else 0.0
        supported.append(max(supported_qty, 0.0))
        ready_dt = _lot_availability_datetime_for_qty(shadow_lots, balance_key, min(requested_qty, supported_qty) * ratio) if wip_item else completed.get((candidate_id, pred)) or base_ready
        ready_dt = ready_dt or base_ready
        ready_datetimes.append(ready_dt)
        evidence.append({
            "predecessor_operation_id": pred,
            "wip_item_id": wip_item,
            "buffer_id": buffer_id,
            "available_qty": available,
            "required_input_qty_per_output_unit": ratio,
            "availability_datetime": ready_dt,
        })
        if available <= 0.0001:
            blocker = "NO_PREDECESSOR_OR_SHADOW_WIP_QUANTITY_AVAILABLE"
    max_supported = min(supported) if supported else 0.0
    target_qty = min(requested_qty, max_supported)
    if target_qty > 0:
        ready_datetimes = []
        for evidence_row in evidence:
            wip_item = str(evidence_row.get("wip_item_id", ""))
            buffer_id = str(evidence_row.get("buffer_id", ""))
            if wip_item:
                ready_dt = _lot_availability_datetime_for_qty(shadow_lots, (wip_item, buffer_id), target_qty * _num(evidence_row.get("required_input_qty_per_output_unit", 1.0)))
            else:
                ready_dt = completed.get((candidate_id, str(evidence_row.get("predecessor_operation_id")))) or base_ready
            ready_dt = ready_dt or base_ready
            evidence_row["availability_datetime"] = ready_dt
            ready_datetimes.append(ready_dt)
    if max_supported <= 0.0001:
        status = "QUANTITY_FLOW_BLOCKED"
    elif max_supported + 0.0001 < requested_qty:
        status = "MERGE_INPUT_SHORTAGE" if len(pred_ids) > 1 else "PARTIAL_QUANTITY_SUPPORTED"
    else:
        status = "FULL_QUANTITY_SUPPORTED"
    return {
        "quantity_supported_before_capacity": max_supported,
        "input_quantity_availability_datetime": max(ready_datetimes) if ready_datetimes else base_ready,
        "quantity_support_status": status,
        "quantity_support_blocker_reason": blocker,
        "input_evidence": evidence,
    }


def _apply_live_shadow_draws_and_production(
    key: tuple[str, str],
    op: dict,
    scheduled_qty: float,
    start_dt: datetime | None,
    completion_dt: datetime | None,
    quantity_support: dict,
    shadow_lots: dict[tuple[str, str], list[dict]],
    flow: pd.DataFrame,
    buffers: dict[str, dict],
) -> None:
    if scheduled_qty <= 0.0001:
        return
    candidate_id, operation_id = key
    sku = str(op["finished_sku"])
    for evidence in quantity_support.get("input_evidence", []):
        wip_item = str(evidence.get("wip_item_id", ""))
        buffer_id = str(evidence.get("buffer_id", ""))
        if not wip_item:
            continue
        balance_key = (wip_item, buffer_id)
        required_draw = scheduled_qty * _num(evidence.get("required_input_qty_per_output_unit", 1.0))
        _draw_shadow_lots(shadow_lots, balance_key, required_draw, start_dt)
    output_rows = flow[(flow["finished_sku"].astype(str) == sku) & (flow["produced_by_operation_id"].astype(str) == operation_id)]
    for _, output_row in output_rows.iterrows():
        wip_item = str(output_row.get("wip_item_id", ""))
        buffer_id = _buffer_for_wip(buffers, wip_item)
        if not wip_item:
            continue
        balance_key = (wip_item, buffer_id)
        if completion_dt:
            shadow_lots.setdefault(balance_key, []).append({
                "lot_id": f"LOT-{key[0]}-{operation_id}-{wip_item}-{len(shadow_lots.get(balance_key, [])) + 1:04d}",
                "wip_item_id": wip_item,
                "wip_buffer_id": buffer_id,
                "quantity": scheduled_qty,
                "remaining_qty": scheduled_qty,
                "availability_datetime": completion_dt,
                "producer_candidate_id": candidate_id,
                "producer_operation_id": operation_id,
            })


def _calculate_output_buffer_support(
    op: dict,
    requested_qty: float,
    input_supported_qty: float,
    shadow_lots: dict[tuple[str, str], list[dict]],
    flow: pd.DataFrame,
    buffers: dict[str, dict],
) -> dict:
    sku = str(op["finished_sku"])
    operation_id = str(op["operation_id"])
    output_rows = flow[(flow["finished_sku"].astype(str) == sku) & (flow["produced_by_operation_id"].astype(str) == operation_id)]
    if output_rows.empty:
        return {
            "output_wip_item_id": "",
            "output_wip_buffer_id": "",
            "buffer_capacity_before_production": 0.0,
            "buffer_balance_before_production": 0.0,
            "available_buffer_space_qty": input_supported_qty,
            "buffer_supported_output_qty": input_supported_qty,
            "buffer_blocked_output_qty": 0.0,
            "allowed_buffer_capacity_qty": 0.0,
            "overflow_policy": "FINAL_OPERATION_NO_OUTPUT_WIP",
            "buffer_capacity_status": "NO_OUTPUT_WIP_REQUIRED",
            "buffer_capacity_blocker_reason": "",
        }
    supported_values: list[float] = []
    evidence_rows: list[dict] = []
    for _, output_row in output_rows.iterrows():
        wip_item = str(output_row.get("wip_item_id", ""))
        buffer_id = _buffer_for_wip(buffers, wip_item)
        buffer = buffers.get(buffer_id, {})
        allowed, policy, reason = _allowed_buffer_capacity(buffer)
        balance = _lot_remaining_qty(shadow_lots, (wip_item, buffer_id))
        space = max(allowed - balance, 0.0) if allowed > 0 else 0.0
        supported = min(input_supported_qty, space)
        supported_values.append(supported)
        status = "BUFFER_CAPACITY_AVAILABLE" if supported + 0.0001 >= input_supported_qty else "OUTPUT_BUFFER_CAPACITY_BLOCK"
        if reason:
            status = "TEMPORARY_OVERFLOW_CAPACITY_UNDEFINED" if supported + 0.0001 >= input_supported_qty else "OUTPUT_BUFFER_CAPACITY_BLOCK"
        evidence_rows.append({
            "output_wip_item_id": wip_item,
            "output_wip_buffer_id": buffer_id,
            "buffer_capacity_before_production": allowed,
            "buffer_balance_before_production": balance,
            "available_buffer_space_qty": space,
            "buffer_supported_output_qty": supported,
            "allowed_buffer_capacity_qty": allowed,
            "overflow_policy": policy,
            "buffer_capacity_status": status,
            "buffer_capacity_blocker_reason": reason or ("OUTPUT_BUFFER_CAPACITY_BLOCK" if supported + 0.0001 < input_supported_qty else ""),
        })
    supported_qty = min(supported_values) if supported_values else input_supported_qty
    blocked_qty = max(min(requested_qty, input_supported_qty) - supported_qty, 0.0)
    primary = min(evidence_rows, key=lambda row: row["buffer_supported_output_qty"]) if evidence_rows else {}
    return {
        **primary,
        "buffer_supported_output_qty": supported_qty,
        "buffer_blocked_output_qty": blocked_qty,
    }


def _empty_buffer_support(op: dict, requested_qty: float, flow: pd.DataFrame, buffers: dict[str, dict]) -> dict:
    sku = str(op.get("finished_sku", ""))
    operation_id = str(op.get("operation_id", ""))
    output_rows = flow[(flow["finished_sku"].astype(str) == sku) & (flow["produced_by_operation_id"].astype(str) == operation_id)]
    if output_rows.empty:
        return {
            "output_wip_item_id": "",
            "output_wip_buffer_id": "",
            "buffer_capacity_before_production": 0.0,
            "buffer_balance_before_production": 0.0,
            "available_buffer_space_qty": requested_qty,
            "buffer_supported_output_qty": requested_qty,
            "buffer_blocked_output_qty": 0.0,
            "allowed_buffer_capacity_qty": 0.0,
            "overflow_policy": "FINAL_OPERATION_NO_OUTPUT_WIP",
            "buffer_capacity_status": "NO_OUTPUT_WIP_REQUIRED",
            "buffer_capacity_blocker_reason": "",
            "buffer_check_datetime": "",
            "projected_balance_at_completion": 0.0,
            "projected_space_at_completion": requested_qty,
            "buffer_release_datetime": "",
            "buffer_delay_minutes": 0.0,
            "buffer_reservation_qty": 0.0,
            "buffer_reservation_status": "NO_OUTPUT_WIP_REQUIRED",
            "buffer_search_attempt_count": 0,
        }
    output_row = output_rows.iloc[0]
    wip_item = str(output_row.get("wip_item_id", ""))
    buffer_id = _buffer_for_wip(buffers, wip_item)
    allowed, policy, reason = _allowed_buffer_capacity(buffers.get(buffer_id, {}))
    return {
        "output_wip_item_id": wip_item,
        "output_wip_buffer_id": buffer_id,
        "buffer_capacity_before_production": allowed,
        "buffer_balance_before_production": 0.0,
        "available_buffer_space_qty": 0.0,
        "buffer_supported_output_qty": 0.0,
        "buffer_blocked_output_qty": requested_qty,
        "allowed_buffer_capacity_qty": allowed,
        "overflow_policy": policy,
        "buffer_capacity_status": "OUTPUT_BUFFER_CAPACITY_BLOCK",
        "buffer_capacity_blocker_reason": reason or "OUTPUT_BUFFER_CAPACITY_BLOCK",
        "buffer_check_datetime": "",
        "projected_balance_at_completion": 0.0,
        "projected_space_at_completion": 0.0,
        "buffer_release_datetime": "",
        "buffer_delay_minutes": 0.0,
        "buffer_reservation_qty": 0.0,
        "buffer_reservation_status": "BUFFER_NOT_RESERVED",
        "buffer_search_attempt_count": 0,
    }


def _calculate_output_buffer_support_at_datetime(
    op: dict,
    requested_qty: float,
    candidate_output_qty: float,
    buffer_events: list[dict],
    flow: pd.DataFrame,
    buffers: dict[str, dict],
    completion_dt: datetime | None,
    attempt_count: int,
) -> dict:
    sku = str(op["finished_sku"])
    operation_id = str(op["operation_id"])
    output_rows = flow[(flow["finished_sku"].astype(str) == sku) & (flow["produced_by_operation_id"].astype(str) == operation_id)]
    if output_rows.empty:
        support = _empty_buffer_support(op, candidate_output_qty, flow, buffers)
        support["buffer_search_attempt_count"] = attempt_count
        support["buffer_check_datetime"] = completion_dt.isoformat(timespec="minutes") if completion_dt else ""
        return support
    evidence_rows: list[dict] = []
    supported_values: list[float] = []
    release_candidates: list[datetime] = []
    for _, output_row in output_rows.iterrows():
        wip_item = str(output_row.get("wip_item_id", ""))
        buffer_id = _buffer_for_wip(buffers, wip_item)
        allowed, policy, reason = _allowed_buffer_capacity(buffers.get(buffer_id, {}))
        balance = _projected_buffer_balance(buffer_events, (wip_item, buffer_id), completion_dt, buffers)
        space = max(allowed - balance, 0.0) if allowed > 0 else 0.0
        supported = min(candidate_output_qty, space)
        supported_values.append(supported)
        release_dt = _next_buffer_release_datetime(buffer_events, (wip_item, buffer_id), completion_dt)
        if release_dt:
            release_candidates.append(release_dt)
        status = "BUFFER_RESERVATION_ACCEPTED" if supported + 0.0001 >= candidate_output_qty else "OUTPUT_BUFFER_CAPACITY_BLOCK"
        blocker = ""
        if reason:
            blocker = reason
            if supported + 0.0001 < candidate_output_qty:
                status = "OUTPUT_BUFFER_CAPACITY_BLOCK"
        elif supported + 0.0001 < candidate_output_qty:
            blocker = "OUTPUT_BUFFER_CAPACITY_BLOCK"
        evidence_rows.append({
            "output_wip_item_id": wip_item,
            "output_wip_buffer_id": buffer_id,
            "buffer_capacity_before_production": allowed,
            "buffer_balance_before_production": balance,
            "available_buffer_space_qty": space,
            "buffer_supported_output_qty": supported,
            "allowed_buffer_capacity_qty": allowed,
            "overflow_policy": policy,
            "buffer_capacity_status": "BUFFER_CAPACITY_AVAILABLE" if supported + 0.0001 >= candidate_output_qty and not reason else status,
            "buffer_capacity_blocker_reason": blocker,
        })
    supported_qty = min(supported_values) if supported_values else candidate_output_qty
    blocked_qty = max(candidate_output_qty - supported_qty, 0.0)
    primary = min(evidence_rows, key=lambda row: row["buffer_supported_output_qty"]) if evidence_rows else {}
    release_dt = min(release_candidates) if release_candidates else None
    delay = 0.0
    if release_dt and completion_dt and release_dt > completion_dt:
        delay = (release_dt - completion_dt).total_seconds() / 60.0
    return {
        **primary,
        "buffer_supported_output_qty": supported_qty,
        "buffer_blocked_output_qty": blocked_qty,
        "buffer_check_datetime": completion_dt.isoformat(timespec="minutes") if completion_dt else "",
        "projected_balance_at_completion": primary.get("buffer_balance_before_production", 0.0),
        "projected_space_at_completion": primary.get("available_buffer_space_qty", 0.0),
        "buffer_release_datetime": release_dt.isoformat(timespec="minutes") if release_dt else "",
        "buffer_delay_minutes": delay,
        "buffer_reservation_qty": supported_qty if blocked_qty <= 0.0001 else 0.0,
        "buffer_reservation_status": "BUFFER_SPACE_RESERVED" if blocked_qty <= 0.0001 else "BUFFER_SPACE_NOT_RESERVED",
        "buffer_search_attempt_count": attempt_count,
    }


def _seed_buffer_events(starting: dict[tuple[str, str], float], horizon_start: datetime) -> list[dict]:
    return [
        {"event_datetime": horizon_start, "wip_item_id": item, "wip_buffer_id": buffer, "event_type": "STARTING_ACCEPTED_WIP", "produced": qty, "drawn": 0.0}
        for (item, buffer), qty in sorted(starting.items())
        if qty > 0
    ]


def _projected_buffer_balance(events: list[dict], key: tuple[str, str], as_of: datetime | None, buffers: dict[str, dict]) -> float:
    if as_of is None:
        return 0.0
    balance = 0.0
    allowed, _, _ = _allowed_buffer_capacity(buffers.get(key[1], {}))
    for event in sorted(events, key=lambda row: (row["event_datetime"], 0 if row["event_type"] != "ADVISORY_DRAW_FOR_OPERATION" else 1)):
        if (str(event["wip_item_id"]), str(event["wip_buffer_id"])) != key:
            continue
        if event["event_datetime"] > as_of:
            continue
        balance += _num(event.get("produced")) - _num(event.get("drawn"))
        if allowed > 0:
            balance = min(balance, allowed)
        balance = max(balance, 0.0)
    return balance


def _next_buffer_release_datetime(events: list[dict], key: tuple[str, str], after_dt: datetime | None) -> datetime | None:
    if after_dt is None:
        return None
    releases = [
        event["event_datetime"]
        for event in events
        if (str(event["wip_item_id"]), str(event["wip_buffer_id"])) == key
        and event["event_type"] == "ADVISORY_DRAW_FOR_OPERATION"
        and event["event_datetime"] > after_dt
        and _num(event.get("drawn")) > 0
    ]
    return min(releases) if releases else None


def _next_output_buffer_release_datetime(op: dict, events: list[dict], flow: pd.DataFrame, buffers: dict[str, dict], after_dt: datetime | None) -> datetime | None:
    sku = str(op["finished_sku"])
    operation_id = str(op["operation_id"])
    releases = []
    output_rows = flow[(flow["finished_sku"].astype(str) == sku) & (flow["produced_by_operation_id"].astype(str) == operation_id)]
    for _, output_row in output_rows.iterrows():
        wip_item = str(output_row.get("wip_item_id", ""))
        release_dt = _next_buffer_release_datetime(events, (wip_item, _buffer_for_wip(buffers, wip_item)), after_dt)
        if release_dt:
            releases.append(release_dt)
    return min(releases) if releases else None


def _record_live_buffer_events(
    key: tuple[str, str],
    op: dict,
    scheduled_qty: float,
    start_dt: datetime | None,
    completion_dt: datetime | None,
    quantity_support: dict,
    events: list[dict],
    flow: pd.DataFrame,
    buffers: dict[str, dict],
) -> None:
    if scheduled_qty <= 0.0001:
        return
    for evidence in quantity_support.get("input_evidence", []):
        wip_item = str(evidence.get("wip_item_id", ""))
        buffer_id = str(evidence.get("buffer_id", ""))
        if wip_item and start_dt:
            events.append({"event_datetime": start_dt, "wip_item_id": wip_item, "wip_buffer_id": buffer_id, "event_type": "ADVISORY_DRAW_FOR_OPERATION", "produced": 0.0, "drawn": scheduled_qty * _num(evidence.get("required_input_qty_per_output_unit", 1.0))})
    sku = str(op["finished_sku"])
    operation_id = str(op["operation_id"])
    output_rows = flow[(flow["finished_sku"].astype(str) == sku) & (flow["produced_by_operation_id"].astype(str) == operation_id)]
    for _, output_row in output_rows.iterrows():
        wip_item = str(output_row.get("wip_item_id", ""))
        buffer_id = _buffer_for_wip(buffers, wip_item)
        if wip_item and completion_dt:
            events.append({"event_datetime": completion_dt, "wip_item_id": wip_item, "wip_buffer_id": buffer_id, "event_type": "ADVISORY_PRODUCTION_TO_BUFFER", "produced": scheduled_qty, "drawn": 0.0})


def _allowed_buffer_capacity(buffer: dict) -> tuple[float, str, str]:
    max_qty = _num(buffer.get("max_buffer_qty"))
    policy = str(buffer.get("overflow_policy", "MANAGER_REVIEW")).strip() or "MANAGER_REVIEW"
    temp_limit = 0.0
    for column in ["temporary_overflow_limit_qty", "temporary_overflow_max_qty", "max_temporary_overflow_qty"]:
        if column in buffer:
            temp_limit = max(temp_limit, _num(buffer.get(column)))
    if policy == "TEMPORARY_OVERFLOW_ALLOWED":
        if temp_limit > 0:
            return max(max_qty, temp_limit), policy, ""
        return max_qty, policy, "TEMPORARY_OVERFLOW_CAPACITY_UNDEFINED"
    return max_qty, policy, ""


def _seed_shadow_lots(starting: dict[tuple[str, str], float], horizon_start: datetime) -> dict[tuple[str, str], list[dict]]:
    lots: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for (wip_item, buffer_id), qty in sorted(starting.items()):
        if qty <= 0:
            continue
        lots[(wip_item, buffer_id)].append({
            "lot_id": f"LOT-START-{wip_item}-{buffer_id}",
            "wip_item_id": wip_item,
            "wip_buffer_id": buffer_id,
            "quantity": qty,
            "remaining_qty": qty,
            "availability_datetime": horizon_start,
            "producer_candidate_id": "",
            "producer_operation_id": "",
        })
    return lots


def _lot_remaining_qty(lots: dict[tuple[str, str], list[dict]], key: tuple[str, str], as_of: datetime | None = None) -> float:
    total = 0.0
    for lot in lots.get(key, []):
        if as_of is None or lot["availability_datetime"] <= as_of:
            total += _num(lot.get("remaining_qty"))
    return total


def _lot_availability_datetime_for_qty(lots: dict[tuple[str, str], list[dict]], key: tuple[str, str], required_qty: float) -> datetime | None:
    if required_qty <= 0.0001:
        dated = [lot["availability_datetime"] for lot in lots.get(key, []) if _num(lot.get("remaining_qty")) > 0.0001]
        return min(dated) if dated else None
    cumulative = 0.0
    for lot in sorted(lots.get(key, []), key=lambda item: (item["availability_datetime"], item["lot_id"])):
        remaining = _num(lot.get("remaining_qty"))
        if remaining <= 0.0001:
            continue
        cumulative += remaining
        if cumulative + 0.0001 >= required_qty:
            return lot["availability_datetime"]
    return None


def _draw_shadow_lots(lots: dict[tuple[str, str], list[dict]], key: tuple[str, str], required_qty: float, as_of: datetime | None) -> float:
    remaining_draw = max(required_qty, 0.0)
    drawn = 0.0
    for lot in sorted(lots.get(key, []), key=lambda item: (item["availability_datetime"], item["lot_id"])):
        if as_of is not None and lot["availability_datetime"] > as_of:
            continue
        lot_remaining = _num(lot.get("remaining_qty"))
        if lot_remaining <= 0.0001:
            continue
        take = min(lot_remaining, remaining_draw)
        lot["remaining_qty"] = lot_remaining - take
        remaining_draw -= take
        drawn += take
        if remaining_draw <= 0.0001:
            break
    return drawn


def _resource_profile_for_operation(windows: dict, workstation_id: str, machine_id: str, labor_skill: str, required_machine_count: int, required_worker_count: int) -> dict:
    units = windows.get("resource_units", {})
    ws_row = units.get("workstations", {}).get(workstation_id, {})
    machine_units = list(units.get("machine_units", {}).get(machine_id, []))
    labor_units = list(units.get("labor_units", {}).get((workstation_id, labor_skill), [])) if labor_skill else []
    ws_parallel = _bool(ws_row.get("supports_parallel_work_flag"))
    labor_parallel = bool(units.get("labor_flags", {}).get((workstation_id, labor_skill), False)) if labor_skill else True
    machine_lanes = len(machine_units) // max(required_machine_count, 1)
    worker_lanes = (len(labor_units) // max(required_worker_count, 1)) if labor_skill else machine_lanes
    lane_count = max(min(machine_lanes, worker_lanes), 1) if ws_parallel and labor_parallel else 1
    lane_count = min(lane_count, max(len(machine_units), 1), max(len(labor_units), 1) if labor_skill else lane_count)
    return {
        "workstation_parallel_authorized_flag": ws_parallel,
        "labor_parallel_authorized_flag": labor_parallel,
        "parallel_capacity_applied_flag": bool(lane_count > 1 and ws_parallel and labor_parallel),
        "effective_parallel_lane_count": int(lane_count),
        "machine_units": machine_units[: max(len(machine_units), required_machine_count)],
        "labor_units": labor_units[: max(len(labor_units), required_worker_count)] if labor_skill else [],
        "lane_ids": [f"{workstation_id}#LANE-{idx:02d}" for idx in range(1, int(lane_count) + 1)],
        "required_machine_count": required_machine_count,
        "required_worker_count": required_worker_count,
    }


def _find_resource_bundle(window: dict, ledgers: dict, profile: dict, search_after: datetime, setup_minutes: float, remaining_processing: float, preferred_machine_units: tuple[str, ...] | None, preferred_labor_units: tuple[str, ...] | None) -> dict | None:
    req_m = max(int(profile.get("required_machine_count", 1)), 1)
    req_w = max(int(profile.get("required_worker_count", 1)), 1)
    machine_combos = list(combinations(profile.get("machine_units", []), req_m))
    labor_source = profile.get("labor_units", [])
    labor_combos = list(combinations(labor_source, req_w)) if labor_source else [tuple()]
    if not machine_combos or not labor_combos:
        return None
    if preferred_machine_units in machine_combos:
        machine_combos.remove(preferred_machine_units)
        machine_combos.insert(0, preferred_machine_units)
    if preferred_labor_units in labor_combos:
        labor_combos.remove(preferred_labor_units)
        labor_combos.insert(0, preferred_labor_units)
    best = None
    lane_ids = profile.get("lane_ids", ["LANE-01"])
    for lane_id in lane_ids:
        lane_busy = ledgers.get("workstation_lane_busy_end", {}).get((window["date"], window["shift"], lane_id))
        for machine_combo in machine_combos:
            machine_busy_values = [ledgers.get("machine_unit_busy_end", {}).get((window["date"], window["shift"], unit)) for unit in machine_combo]
            for labor_combo in labor_combos:
                labor_busy_values = [ledgers.get("labor_unit_busy_end", {}).get((window["date"], window["shift"], unit)) for unit in labor_combo]
                busy_candidates = [search_after, window["start_dt"], lane_busy, *machine_busy_values, *labor_busy_values]
                start_dt = max([value for value in busy_candidates if value is not None])
                if start_dt >= window["end_dt"]:
                    continue
                available = max((window["end_dt"] - start_dt).total_seconds() / 60.0, 0.0)
                if available <= setup_minutes + 0.0001:
                    continue
                start_offset = max((start_dt - window["start_dt"]).total_seconds() / 60.0, 0.0)
                score = (start_dt, -available, lane_id)
                candidate = {
                    "start_dt": start_dt,
                    "start_offset": start_offset,
                    "available_minutes": min(available, remaining_processing + setup_minutes),
                    "parallel_lane_id": lane_id,
                    "machine_unit_ids": list(machine_combo),
                    "labor_unit_ids": list(labor_combo),
                    "score": score,
                }
                if best is None or candidate["score"] < best["score"]:
                    best = candidate
    return best


def _append_capacity_row(rows: list[dict], op: dict, route_res: dict, placement: dict, cap_ref: dict) -> None:
    total = _num(op["total_required_minutes"])
    allocated = _num(placement["allocated_minutes"])
    available = _num(placement["available_minutes"])
    util = allocated / available * 100.0 if available > 0 else 0.0
    lane_count = max(int(_num(op.get("effective_parallel_lane_count", 1))), 1)
    net_per_unit = 435.0
    segment_windows = {
        (segment.get("date"), segment.get("shift"), segment.get("window_id"))
        for segment in placement.get("segments", [])
        if not _blank(segment.get("date"))
    }
    window_count = max(len(segment_windows), 1)
    aggregate_capacity = net_per_unit * lane_count * window_count
    workstation_util = allocated / max(aggregate_capacity, 1.0) * 100.0
    machine_util = allocated / max(aggregate_capacity, 1.0) * 100.0
    labor_util = allocated / max(aggregate_capacity, 1.0) * 100.0
    rows.append({
        "planning_run_id": op["planning_run_id"],
        "alternative_id": op["alternative_id"],
        "schedule_candidate_id": op["schedule_candidate_id"],
        "operation_id": op["operation_id"],
        "final_operation_segment_ids": ";".join(
            f"SEG-{op['alternative_id']}-{op['schedule_candidate_id']}-{op['operation_id']}-{idx:02d}"
            for idx, segment in enumerate(placement.get("segments", []), start=1)
            if _num(segment.get("processing_minutes")) > 0
        ),
        "workstation_id": op["workstation_id"],
        "machine_id": op["machine_id"],
        "labor_skill_id": route_res.get("required_labor_skill", ""),
        "proposed_schedule_period": op["proposed_schedule_period"],
        "proposed_schedule_day": op["proposed_schedule_day"],
        "proposed_schedule_shift": op["proposed_schedule_shift"],
        "proposed_schedule_date": op["proposed_schedule_date"],
        "proposed_shift_id": op["proposed_shift_id"],
        "proposed_window_id": op["proposed_window_id"],
        "available_minutes": round(available, 4),
        "net_minutes_per_resource_unit": round(net_per_unit, 4),
        "effective_parallel_lane_count": lane_count,
        "aggregate_workstation_capacity_minutes": round(aggregate_capacity, 4),
        "aggregate_machine_capacity_minutes": round(aggregate_capacity, 4),
        "aggregate_labor_capacity_minutes": round(aggregate_capacity, 4),
        "scheduled_minutes_by_machine_unit": _segment_unit_minutes(placement.get("segments", []), "assigned_machine_unit_ids"),
        "scheduled_minutes_by_labor_unit": _segment_unit_minutes(placement.get("segments", []), "assigned_labor_unit_ids"),
        "total_scheduled_workload_minutes": round(allocated, 4),
        "remaining_aggregate_capacity_minutes": round(max(aggregate_capacity - allocated, 0.0), 4),
        "workstation_utilization_pct": round(workstation_util, 4),
        "machine_utilization_pct": round(machine_util, 4),
        "labor_utilization_pct": round(labor_util, 4),
        "workstation_utilization_percentage": round(workstation_util, 4),
        "machine_utilization_percentage": round(machine_util, 4),
        "labor_utilization_percentage": round(labor_util, 4),
        "binding_resource_type": _binding_resource_type(workstation_util, machine_util, labor_util),
        "previously_allocated_minutes": round(max(available - placement["remaining_minutes"] - allocated, 0.0), 4),
        "requested_minutes": round(total, 4),
        "newly_allocated_minutes": round(allocated, 4),
        "remaining_minutes": round(placement["remaining_minutes"], 4),
        "overload_minutes": round(max(total - allocated, 0.0), 4),
        "required_processing_hours": round(_num(op["processing_minutes_total"]) / 60.0, 4),
        "required_setup_hours": round(_num(op["actual_sequence_setup_minutes"]) / 60.0, 4),
        "total_required_hours": round(total / 60.0, 4),
        "available_hours_reference": round(available / 60.0, 4),
        "utilization_pct": round(util, 4),
        "quality_adjusted_utilization_pct": round(max(_num(cap_ref.get("quality_adjusted_utilization_pct")), util), 4),
        "capacity_feasibility_status": placement["capacity_status"],
        "capacity_overload_hours": round(max(total - allocated, 0.0) / 60.0, 4),
        "capacity_overload_penalty": round(max(total - allocated, 0.0) / 60.0 * 140.0, 4),
        "underutilization_hours": round(max(available - allocated, 0.0) / 60.0 if util < 50 else 0.0, 4),
        "underutilization_penalty": round((max(available - allocated, 0.0) / 60.0 if util < 50 else 0.0) * 8.0, 4),
        "note_no_capacity_change_flag": True,
        "source_phase": SOURCE_PHASE,
        "advisory_only_flag": True,
    })


def _append_wip_row(rows: list[dict], op: dict, input_rows: list[dict], buffers: dict[str, dict], requested_qty: float, scheduled_qty: float, alt_type: str) -> None:
    output_buffer_id = str(op.get("wip_buffer_id", ""))
    output_item = str(op.get("output_wip_item_id", ""))
    if not input_rows:
        status = "OUTPUT_BUFFER_CAPACITY_BLOCK" if _num(op.get("buffer_blocked_output_qty")) > 0.0001 else "NO_WIP_REQUIRED"
        rows.append(_wip_row(op, "", output_item, output_buffer_id, 0.0, 0.0, scheduled_qty, 0.0, status, _num(op.get("buffer_balance_before_production")) + scheduled_qty, 0.0, 0.0))
        return
    for input_row in input_rows:
        item = "" if _blank(input_row.get("required_input_wip_item_id", "")) else str(input_row.get("required_input_wip_item_id"))
        buffer_id = "" if _blank(input_row.get("related_wip_buffer_id", "")) else str(input_row.get("related_wip_buffer_id"))
        buffer = buffers.get(buffer_id, {})
        accepted = _num(input_row.get("accepted_wip_available_qty"))
        required = requested_qty if item else 0.0
        draw = min(accepted, scheduled_qty) if alt_type in {"WIP_PROTECTED_CONTINUITY", "LEAST_RISK_COMBINED"} else 0.0
        build = max(min(_num(buffer.get("target_buffer_qty")) - _num(buffer.get("current_wip_qty")), _num(buffer.get("available_buffer_capacity_qty"))), 0.0) if alt_type in {"WIP_PROTECTED_CONTINUITY", "LEAST_RISK_COMBINED"} else 0.0
        ending = max(_num(buffer.get("current_wip_qty")) + build - draw, 0.0)
        overflow = max(ending - _num(buffer.get("max_buffer_qty")), 0.0) if buffer_id else 0.0
        shortage = max(required - accepted, 0.0)
        status = "WIP_SUPPORTS_OPERATION" if item and shortage <= 0 else "WIP_PARTIALLY_SUPPORTS_OPERATION" if item and accepted > 0 else "WIP_SHORTAGE_RISK" if item else "NO_WIP_REQUIRED"
        if build > 0:
            status = "BUILD_WIP_TO_TARGET"
        if overflow > 0:
            status = "WIP_OVERFLOW_RISK"
        if _num(op.get("buffer_blocked_output_qty")) > 0.0001:
            status = "OUTPUT_BUFFER_CAPACITY_BLOCK"
        if output_item:
            rows.append(_wip_row(op, item, output_item, output_buffer_id, accepted, required, scheduled_qty, draw, status, _num(op.get("buffer_balance_before_production")) + scheduled_qty, shortage, 0.0))
        else:
            rows.append(_wip_row(op, item, output_item, buffer_id, accepted, required, build, draw, status, ending, shortage, overflow))


def _wip_row(op: dict, input_item: str, output_item: str, buffer_id: str, accepted: float, required: float, build: float, draw: float, status: str, ending: float = 0.0, shortage: float = 0.0, overflow: float = 0.0) -> dict:
    return {
        "planning_run_id": op["planning_run_id"],
        "alternative_id": op["alternative_id"],
        "finished_sku": op["finished_sku"],
        "operation_id": op["operation_id"],
        "required_input_wip_item_id": input_item,
        "output_wip_item_id": output_item,
        "wip_buffer_id": buffer_id,
        "accepted_wip_available_qty": round(accepted, 4),
        "required_wip_qty": round(required, 4),
        "projected_wip_build_qty": round(build, 4),
        "projected_wip_draw_qty_advisory": round(draw, 4),
        "projected_wip_ending_qty_advisory": round(ending, 4),
        "wip_shortage_qty": round(shortage, 4),
        "wip_overflow_qty": round(overflow, 4),
        "wip_impact_status": status,
        "wip_shortage_penalty": round(shortage * 25.0, 4),
        "wip_overflow_penalty": round(overflow * 20.0, 4),
        "buffer_capacity_before_production": round(_num(op.get("buffer_capacity_before_production")), 4),
        "buffer_balance_before_production": round(_num(op.get("buffer_balance_before_production")), 4),
        "available_buffer_space_qty": round(_num(op.get("available_buffer_space_qty")), 4),
        "requested_output_qty": round(_num(op.get("requested_production_qty")), 4),
        "buffer_supported_output_qty": round(_num(op.get("buffer_supported_output_qty")), 4),
        "buffer_blocked_output_qty": round(_num(op.get("buffer_blocked_output_qty")), 4),
        "allowed_buffer_capacity_qty": round(_num(op.get("allowed_buffer_capacity_qty")), 4),
        "overflow_policy": op.get("overflow_policy", ""),
        "buffer_capacity_status": op.get("buffer_capacity_status", ""),
        "buffer_capacity_blocker_reason": op.get("buffer_capacity_blocker_reason", ""),
        "buffer_check_datetime": op.get("buffer_check_datetime", ""),
        "projected_balance_at_completion": round(_num(op.get("projected_balance_at_completion")), 4),
        "projected_space_at_completion": round(_num(op.get("projected_space_at_completion")), 4),
        "buffer_release_datetime": op.get("buffer_release_datetime", ""),
        "buffer_delay_minutes": round(_num(op.get("buffer_delay_minutes")), 4),
        "buffer_reservation_qty": round(_num(op.get("buffer_reservation_qty")), 4),
        "buffer_reservation_status": op.get("buffer_reservation_status", ""),
        "buffer_search_attempt_count": int(_num(op.get("buffer_search_attempt_count"))),
        "note_no_wip_consumption_flag": True,
        "source_phase": SOURCE_PHASE,
        "advisory_only_flag": True,
    }


def _segment_unit_minutes(segments: list[dict], unit_field: str) -> str:
    totals: dict[str, float] = defaultdict(float)
    for segment in segments:
        for unit in str(segment.get(unit_field, "")).split(";"):
            if unit.strip():
                totals[unit.strip()] += _num(segment.get("allocated_minutes"))
    return ";".join(f"{unit}={round(minutes, 4)}" for unit, minutes in sorted(totals.items()))


def _binding_resource_type(workstation_util: float, machine_util: float, labor_util: float) -> str:
    values = {"WORKSTATION": workstation_util, "MACHINE": machine_util, "LABOR": labor_util}
    return max(values.items(), key=lambda item: item[1])[0]


def _append_setup_row(rows: list[dict], op: dict, prev_op: str, prev_family: str, family_id: str, setup_minutes: float) -> None:
    switch = bool(prev_family and prev_family != family_id)
    rows.append({
        "planning_run_id": op["planning_run_id"],
        "alternative_id": op["alternative_id"],
        "schedule_candidate_id": op["schedule_candidate_id"],
        "operation_id": op["operation_id"],
        "workstation_id": op["workstation_id"],
        "machine_id": op["machine_id"],
        "proposed_schedule_period": op["proposed_schedule_period"],
        "proposed_schedule_day": op["proposed_schedule_day"],
        "proposed_schedule_shift": op["proposed_schedule_shift"],
        "operation_sequence_position": len([r for r in rows if r["alternative_id"] == op["alternative_id"] and r["workstation_id"] == op["workstation_id"]]) + 1,
        "previous_operation_id": prev_op,
        "previous_setup_family_id": prev_family,
        "current_setup_family_id": family_id,
        "changeover_time_minutes": round(setup_minutes, 4),
        "actual_changeover_minutes": round(setup_minutes, 4),
        "setup_switch_flag": switch,
        "baseline_changeover_minutes": 0.0,
        "setup_minutes_saved_vs_baseline": 0.0,
        "setup_saving_supported_flag": False,
        "changeover_complexity": "HIGH" if setup_minutes >= 20 else "MEDIUM" if setup_minutes >= 10 else "LOW" if setup_minutes > 0 else "NONE",
        "setup_capacity_loss_minutes": round(setup_minutes, 4),
        "setup_changeover_cost": 0.0,
        "batching_applied_flag": op["alternative_type"] == "SETUP_REDUCTION_BATCHING" and switch,
        "batching_opportunity_flag": switch,
        "setup_impact_status": "HIGH_SETUP_IMPACT" if setup_minutes >= 30 else "MEDIUM_SETUP_IMPACT" if setup_minutes >= 15 else "LOW_SETUP_IMPACT",
        "source_phase": SOURCE_PHASE,
        "advisory_only_flag": True,
    })


def _append_maintenance_row(rows: list[dict], op: dict, maint_row: dict, breakdown_row: dict, original_conflict: bool, placement: dict) -> None:
    selected_conflict = bool(placement["selected_maintenance_conflict"])
    avoided = original_conflict and not selected_conflict and bool(op["proposed_schedule_date"])
    rows.append({
        "planning_run_id": op["planning_run_id"],
        "alternative_id": op["alternative_id"],
        "workstation_id": op["workstation_id"],
        "machine_id": op["machine_id"],
        "operation_id": op["operation_id"],
        "proposed_schedule_period": op["proposed_schedule_period"],
        "proposed_schedule_day": op["proposed_schedule_day"],
        "proposed_schedule_shift": op["proposed_schedule_shift"],
        "maintenance_feasibility_status": "MAINTENANCE_BLOCKED" if selected_conflict else "FEASIBLE",
        "breakdown_risk_level": breakdown_row.get("breakdown_risk_level", "LOW"),
        "maintenance_conflict_flag": selected_conflict,
        "maintenance_conflict_penalty": round((1200.0 if selected_conflict else 0.0), 4),
        "breakdown_risk_penalty": round(_risk_points(str(breakdown_row.get("breakdown_risk_level", "LOW"))) * 15.0, 4),
        "maintenance_avoidance_applied_flag": avoided,
        "original_maintenance_conflict_flag": original_conflict,
        "selected_window_maintenance_conflict_flag": selected_conflict,
        "selected_window_maintenance_status": placement["selected_maintenance_status"],
        "maintenance_conflict_avoided_flag": avoided,
        "maintenance_avoidance_evidence": "Selected later non-conflicting real resource-calendar window." if avoided else "No non-conflicting production window selected; conflict remains or was absent.",
        "note_no_maintenance_order_created_flag": True,
        "source_phase": SOURCE_PHASE,
        "advisory_only_flag": True,
    })


def _reconcile_quantity_segments_and_shadow_wip(
    frames: dict[str, pd.DataFrame],
    detail: pd.DataFrame,
    setup: pd.DataFrame,
    maintenance: pd.DataFrame,
    summaries: list[dict],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict]]:
    planning_run_id = _planning_run_id(frames)
    flow = frames["wip_flow"].copy()
    buffers = _index_by(frames["wip_buffers"], "wip_buffer_id")
    starting = _starting_wip_by_item_buffer(frames["wip_ledger"])
    schedule_by_op = _index_by2(frames["detail"], "schedule_candidate_id", "operation_id")
    setup_by_op = _index_by2(setup, "schedule_candidate_id", "operation_id")
    maint_by_op = _index_by2(maintenance, "alternative_id", "operation_id")
    candidates = _index_by(frames["candidates"], "schedule_candidate_id")

    new_detail_rows: list[dict] = []
    segment_rows: list[dict] = []
    quantity_rows: list[dict] = []
    shadow_rows: list[dict] = []
    maintenance_window_rows: list[dict] = []
    summary_by_alt = {row["alternative_id"]: dict(row) for row in summaries}

    for alt_id, alt_group in detail.groupby("alternative_id", sort=False):
        shadow_balance = dict(starting)
        shadow_sequence = 0
        # Seed each starting accepted WIP quantity exactly once per alternative.
        for (wip_item_id, buffer_id), qty in sorted(shadow_balance.items()):
            if qty <= 0:
                continue
            shadow_sequence += 1
            shadow_rows.append(_shadow_event_row(
                planning_run_id, alt_id, shadow_sequence, "", "", "", wip_item_id, buffer_id, "", "",
                "STARTING_ACCEPTED_WIP", qty, 0.0, 0.0, 0.0, qty, buffers
            ))

        alt_completed: dict[tuple[str, str], float] = {}
        alt_completed_time: dict[tuple[str, str], datetime] = {}
        alt_finished_by_candidate: dict[str, float] = {}
        alt_finished_time_by_candidate: dict[str, datetime] = {}

        for candidate_id, cand_group in alt_group.groupby("schedule_candidate_id", sort=False):
            cand = candidates.get(str(candidate_id), {})
            requested_candidate_qty = _num(cand.get("planned_production_qty"))
            completed_by_op: dict[str, float] = {}
            completed_time_by_op: dict[str, datetime] = {}
            ordered = cand_group.sort_values(["operation_sequence", "operation_id"])
            for _, row in ordered.iterrows():
                op = row.to_dict()
                sku = str(op["finished_sku"])
                op_id = str(op["operation_id"])
                op_name = str(op["operation_name"])
                requested_qty = _num(op["requested_production_qty"]) or requested_candidate_qty
                original_sched_qty = _num(op["schedulable_production_qty"])
                start_dt = _maybe_datetime(op.get("proposed_start_datetime"))
                end_dt = _maybe_datetime(op.get("proposed_end_datetime"))
                input_rows = flow[(flow["finished_sku"].astype(str) == sku) & (flow["consumed_by_operation_id"].astype(str) == op_id)]
                pred_ids = [str(value) for value in input_rows["produced_by_operation_id"].dropna().astype(str).unique() if str(value).strip()] or _split_ids(op.get("predecessor_operation_ids", ""))
                mandatory_count = len(pred_ids)
                ready_count = 0
                supported_by_input: list[float] = []
                input_evidence_by_pred: dict[str, dict[str, object]] = {}
                quantity_flow_status = "NO_INPUT_REQUIRED_FIRST_OPERATION"
                latest_pred_ready = _parse_date(str(op.get("candidate_schedule_period", "")))
                if pred_ids:
                    quantity_flow_status = "PREDECESSOR_OUTPUT_SUPPORTED"
                    for pred in pred_ids:
                        direct_flow = input_rows[input_rows["produced_by_operation_id"].astype(str) == pred]
                        flow_row = direct_flow.iloc[0].to_dict() if not direct_flow.empty else {}
                        wip_item = str(flow_row.get("wip_item_id", ""))
                        buffer_id = _buffer_for_wip(buffers, wip_item)
                        pred_completed = _num(completed_by_op.get(pred, 0.0))
                        pred_ready_time = completed_time_by_op.get(pred)
                        # The shadow buffer is the single drawable source. It already includes
                        # starting accepted WIP plus advisory predecessor production minus prior draws.
                        pre_draw_available = _num(shadow_balance.get((wip_item, buffer_id), 0.0)) if wip_item else pred_completed
                        if pred_ready_time and pre_draw_available <= pred_completed + 0.0001:
                            latest_pred_ready = max(latest_pred_ready, pred_ready_time)
                        total_available = pre_draw_available
                        supported_qty = max(total_available, 0.0)
                        input_evidence_by_pred[pred] = {
                            "wip_item": wip_item,
                            "buffer_id": buffer_id,
                            "pred_completed": pred_completed,
                            "pre_draw_available": pre_draw_available,
                        }
                        if supported_qty > 0:
                            ready_count += 1
                        supported_by_input.append(supported_qty)
                    max_supported = min(supported_by_input) if supported_by_input else 0.0
                    if len(pred_ids) > 1 and max_supported < requested_qty:
                        quantity_flow_status = "MERGE_INPUT_SHORTAGE"
                    elif max_supported <= 0:
                        quantity_flow_status = "QUANTITY_FLOW_BLOCKED"
                    elif max_supported < requested_qty:
                        quantity_flow_status = "PARTIAL_QUANTITY_SUPPORTED"
                    else:
                        quantity_flow_status = "FULL_QUANTITY_SUPPORTED"
                else:
                    max_supported = requested_qty
                    ready_count = 0

                adjusted_scheduled_qty = min(original_sched_qty, max_supported, requested_qty)
                segment_plan = _load_segment_plan(op.get("segment_schedule_json", "[]"))
                per_unit = _num(op["processing_minutes_per_unit"])
                segment_specs: list[dict] = []
                cumulative_qty = 0.0
                if adjusted_scheduled_qty > 0:
                    for planned_segment in segment_plan:
                        if cumulative_qty >= adjusted_scheduled_qty - 0.0001:
                            break
                        raw_qty = _num(planned_segment.get("segment_qty"))
                        if raw_qty <= 0:
                            continue
                        segment_qty = min(raw_qty, adjusted_scheduled_qty - cumulative_qty)
                        if segment_qty <= 0.0001:
                            break
                        segment_start = _maybe_datetime(planned_segment.get("start"))
                        if not segment_start:
                            continue
                        setup_for_segment = _num(planned_segment.get("setup_minutes")) if not segment_specs else 0.0
                        processing_for_segment = segment_qty * per_unit
                        total_for_segment = processing_for_segment + setup_for_segment
                        segment_end = segment_start + timedelta(minutes=total_for_segment)
                        cumulative_qty += segment_qty
                        segment_specs.append({
                            "qty": segment_qty,
                            "cumulative_qty": cumulative_qty,
                            "remaining_qty": max(requested_qty - cumulative_qty, 0.0),
                            "start_dt": segment_start,
                            "end_dt": segment_end,
                            "date": planned_segment.get("date", segment_start.date().isoformat()),
                            "shift": planned_segment.get("shift", SHIFT_ID),
                            "window_id": planned_segment.get("window_id", ""),
                            "processing_minutes": processing_for_segment,
                            "setup_minutes": setup_for_segment,
                            "total_minutes": total_for_segment,
                            "parallel_capacity_applied_flag": _bool(planned_segment.get("parallel_capacity_applied_flag")),
                            "effective_parallel_lane_count": max(int(_num(planned_segment.get("effective_parallel_lane_count", 1))), 1),
                            "parallel_lane_id": planned_segment.get("parallel_lane_id", ""),
                            "assigned_machine_unit_ids": planned_segment.get("assigned_machine_unit_ids", ""),
                            "assigned_labor_unit_ids": planned_segment.get("assigned_labor_unit_ids", ""),
                            "required_machine_count": max(int(_num(planned_segment.get("required_machine_count", 1))), 1),
                            "required_worker_count": max(int(_num(planned_segment.get("required_worker_count", 1))), 1),
                            "workstation_parallel_authorized_flag": _bool(planned_segment.get("workstation_parallel_authorized_flag")),
                            "labor_parallel_authorized_flag": _bool(planned_segment.get("labor_parallel_authorized_flag")),
                            "resource_bundle_status": planned_segment.get("resource_bundle_status", "RESOURCE_BUNDLE_ASSIGNED"),
                            "continuation_resource_bundle_changed_flag": _bool(planned_segment.get("continuation_resource_bundle_changed_flag")),
                        })
                if adjusted_scheduled_qty > 0 and not segment_specs and start_dt and end_dt:
                    cumulative_qty = adjusted_scheduled_qty
                    segment_specs.append({
                        "qty": adjusted_scheduled_qty,
                        "cumulative_qty": adjusted_scheduled_qty,
                        "remaining_qty": max(requested_qty - adjusted_scheduled_qty, 0.0),
                        "start_dt": start_dt,
                        "end_dt": end_dt,
                        "date": start_dt.date().isoformat(),
                        "shift": op.get("proposed_shift_id", SHIFT_ID),
                        "window_id": op.get("proposed_window_id", ""),
                        "processing_minutes": adjusted_scheduled_qty * per_unit,
                        "setup_minutes": _num(op["actual_sequence_setup_minutes"]),
                        "total_minutes": adjusted_scheduled_qty * per_unit + _num(op["actual_sequence_setup_minutes"]),
                        "parallel_capacity_applied_flag": False,
                        "effective_parallel_lane_count": 1,
                        "parallel_lane_id": "",
                        "assigned_machine_unit_ids": "",
                        "assigned_labor_unit_ids": "",
                        "required_machine_count": 1,
                        "required_worker_count": 1,
                        "workstation_parallel_authorized_flag": False,
                        "labor_parallel_authorized_flag": False,
                        "resource_bundle_status": "RESOURCE_BUNDLE_ASSIGNED",
                        "continuation_resource_bundle_changed_flag": False,
                    })
                adjusted_scheduled_qty = min(cumulative_qty, adjusted_scheduled_qty)
                if adjusted_scheduled_qty <= 0.0001:
                    adjusted_scheduled_qty = 0.0
                    segment_specs = []
                unscheduled_qty = max(requested_qty - adjusted_scheduled_qty, 0.0)
                start_dt = segment_specs[0]["start_dt"] if segment_specs else None
                end_dt = segment_specs[-1]["end_dt"] if segment_specs else None
                live_input_ready_dt = _maybe_datetime(op.get("input_quantity_availability_datetime"))
                if live_input_ready_dt:
                    latest_pred_ready = live_input_ready_dt
                if start_dt and latest_pred_ready and start_dt + timedelta(minutes=1) < latest_pred_ready and adjusted_scheduled_qty > 0:
                    segment_specs = []
                    adjusted_scheduled_qty = 0.0
                    unscheduled_qty = requested_qty
                    start_dt = None
                    end_dt = None
                completed_by_op[op_id] = adjusted_scheduled_qty
                if end_dt and adjusted_scheduled_qty > 0:
                    completed_time_by_op[op_id] = end_dt
                    alt_completed_time[(str(candidate_id), op_id)] = end_dt
                alt_completed[(str(candidate_id), op_id)] = adjusted_scheduled_qty

                # Draw from the alternative-specific shadow WIP exactly once for each direct input.
                for pred in pred_ids:
                    evidence = input_evidence_by_pred.get(pred, {})
                    wip_item = str(evidence.get("wip_item", ""))
                    buffer_id = str(evidence.get("buffer_id", ""))
                    begin = _num(shadow_balance.get((wip_item, buffer_id), 0.0)) if wip_item else 0.0
                    draw = min(adjusted_scheduled_qty, begin) if wip_item else 0.0
                    if draw > 0:
                        shadow_balance[(wip_item, buffer_id)] = max(begin - draw, 0.0)
                        shadow_sequence += 1
                        shadow_rows.append(_shadow_event_row(
                            planning_run_id, alt_id, shadow_sequence, str(candidate_id), "", sku, wip_item, buffer_id, pred, op_id,
                            "ADVISORY_DRAW_FOR_OPERATION", begin, 0.0, draw, 0.0, shadow_balance[(wip_item, buffer_id)], buffers,
                            event_dt=start_dt
                        ))

                output_rows = flow[(flow["finished_sku"].astype(str) == sku) & (flow["produced_by_operation_id"].astype(str) == op_id)]
                for _, out_flow in output_rows.iterrows():
                    wip_item = str(out_flow.get("wip_item_id", ""))
                    buffer_id = _buffer_for_wip(buffers, wip_item)
                    if adjusted_scheduled_qty > 0 and wip_item:
                        begin = shadow_balance.get((wip_item, buffer_id), 0.0)
                        shadow_balance[(wip_item, buffer_id)] = begin + adjusted_scheduled_qty
                        shadow_sequence += 1
                        shadow_rows.append(_shadow_event_row(
                            planning_run_id, alt_id, shadow_sequence, str(candidate_id), "", sku, wip_item, buffer_id, op_id, str(out_flow.get("consumed_by_operation_id", "")),
                            "ADVISORY_PRODUCTION_TO_BUFFER", begin, adjusted_scheduled_qty, 0.0, 0.0, shadow_balance[(wip_item, buffer_id)], buffers,
                            event_dt=end_dt
                        ))

                merge_status = "NOT_A_MERGE_OPERATION"
                if _bool(op.get("merge_operation_flag")):
                    merge_status = "ALL_MANDATORY_INPUTS_READY" if ready_count == mandatory_count and adjusted_scheduled_qty > 0 else "MANDATORY_INPUT_SHORTAGE"
                    if ready_count and ready_count < mandatory_count:
                        merge_status = "PARTIAL_INPUTS_READY"
                predecessor_ready_flag = (not pred_ids) or (ready_count == mandatory_count and max_supported >= adjusted_scheduled_qty)
                precedence_violation = bool(adjusted_scheduled_qty > 0 and start_dt and latest_pred_ready and start_dt + timedelta(minutes=1) < latest_pred_ready)

                op["schedulable_production_qty"] = round(adjusted_scheduled_qty, 4)
                op["final_reconciled_scheduled_qty"] = round(adjusted_scheduled_qty, 4)
                op["post_schedule_quantity_adjustment_qty"] = round(_num(op.get("capacity_scheduled_qty")) - adjusted_scheduled_qty, 6)
                op["post_schedule_quantity_adjustment_flag"] = abs(_num(op.get("capacity_scheduled_qty")) - adjusted_scheduled_qty) > 0.0001
                op["proposed_schedule_period"] = segment_specs[0]["date"] if segment_specs else ""
                op["proposed_schedule_day"] = segment_specs[0]["date"] if segment_specs else ""
                op["proposed_schedule_shift"] = segment_specs[0]["shift"] if segment_specs else ""
                op["proposed_schedule_date"] = segment_specs[0]["date"] if segment_specs else ""
                op["proposed_shift_id"] = segment_specs[0]["shift"] if segment_specs else ""
                op["proposed_window_id"] = ";".join(str(segment["window_id"]) for segment in segment_specs if not _blank(segment.get("window_id", "")))
                op["proposed_start_datetime"] = start_dt.isoformat(timespec="minutes") if start_dt else ""
                op["proposed_end_datetime"] = end_dt.isoformat(timespec="minutes") if end_dt else ""
                op["effective_parallel_lane_count"] = max([int(_num(segment.get("effective_parallel_lane_count", 1))) for segment in segment_specs] or [1])
                op["parallel_capacity_applied_flag"] = any(_bool(segment.get("parallel_capacity_applied_flag")) for segment in segment_specs)
                op["assigned_machine_unit_ids"] = _join_unique([unit for segment in segment_specs for unit in str(segment.get("assigned_machine_unit_ids", "")).split(";")])
                op["assigned_labor_unit_ids"] = _join_unique([unit for segment in segment_specs for unit in str(segment.get("assigned_labor_unit_ids", "")).split(";")])
                segment_bundles = [
                    (str(segment.get("assigned_machine_unit_ids", "")), str(segment.get("assigned_labor_unit_ids", "")))
                    for segment in segment_specs
                ]
                op["resource_bundle_change_count"] = sum(1 for prev, cur in zip(segment_bundles, segment_bundles[1:]) if prev != cur)
                op["resource_bundle_assignment_status"] = "RESOURCE_BUNDLE_ASSIGNED" if adjusted_scheduled_qty > 0 and op["assigned_machine_unit_ids"] and op["assigned_labor_unit_ids"] else "RESOURCE_BUNDLE_NOT_ASSIGNED"
                op["mandatory_predecessor_count"] = mandatory_count
                op["ready_predecessor_count"] = ready_count
                op["predecessor_quantity_ready_flag"] = predecessor_ready_flag
                op["predecessor_ready_datetime"] = latest_pred_ready.isoformat(timespec="minutes") if latest_pred_ready else ""
                op["merge_supported_qty"] = round(max_supported, 4)
                op["quantity_supported_before_capacity"] = round(_num(op.get("quantity_supported_before_capacity", max_supported)), 4)
                op["scheduling_target_qty"] = round(_num(op.get("scheduling_target_qty", min(requested_qty, max_supported))), 4)
                op["capacity_scheduled_qty"] = round(_num(op.get("capacity_scheduled_qty", adjusted_scheduled_qty)), 4)
                op["input_quantity_availability_datetime"] = op.get("input_quantity_availability_datetime", op["predecessor_ready_datetime"])
                op["quantity_support_status"] = op.get("quantity_support_status", quantity_flow_status)
                op["quantity_support_blocker_reason"] = op.get("quantity_support_blocker_reason", "")
                op["resource_reserved_for_supported_qty_flag"] = _bool(op.get("resource_reserved_for_supported_qty_flag", adjusted_scheduled_qty > 0 or _num(op.get("scheduling_target_qty")) <= _num(op.get("quantity_supported_before_capacity")) + 0.0001))
                if _num(op.get("buffer_blocked_output_qty")) > 0.0001 and adjusted_scheduled_qty + 0.0001 < requested_qty:
                    op["quantity_support_blocker_reason"] = "OUTPUT_BUFFER_CAPACITY_BLOCK"
                op["merge_input_completion_status"] = merge_status
                op["independently_calculated_precedence_status"] = "PRECEDENCE_RECALCULATED_OK" if not precedence_violation and predecessor_ready_flag else "PRECEDENCE_OR_QUANTITY_REVIEW_REQUIRED"
                op["precedence_violation_flag"] = precedence_violation
                if adjusted_scheduled_qty <= 0:
                    op["operation_schedule_status"] = "UNSCHEDULED_NO_FEASIBLE_WINDOW"
                    op["operation_hard_feasibility_status"] = "REVIEW_REQUIRED"
                elif unscheduled_qty > 0:
                    op["operation_schedule_status"] = "PARTIAL_QUANTITY_ADVISORY_CANDIDATE"
                    op["operation_hard_feasibility_status"] = "HARD_FEASIBLE_WITH_REVIEW"

                if input_rows.empty:
                    quantity_rows.append(_quantity_flow_row(planning_run_id, alt_id, op, "", "", "", requested_qty, 0.0, 0.0, 0.0, 0.0, requested_qty, adjusted_scheduled_qty, unscheduled_qty, "NO_INPUT_REQUIRED_FIRST_OPERATION"))
                else:
                    for _, input_row in input_rows.iterrows():
                        pred = str(input_row.get("produced_by_operation_id", ""))
                        evidence = input_evidence_by_pred.get(pred, {})
                        wip_item = str(evidence.get("wip_item", input_row.get("wip_item_id", "")))
                        buffer_id = str(evidence.get("buffer_id", _buffer_for_wip(buffers, wip_item)))
                        pred_completed = _num(evidence.get("pred_completed", completed_by_op.get(pred, 0.0)))
                        pre_draw_available = _num(evidence.get("pre_draw_available", 0.0))
                        starting_available = max(pre_draw_available - pred_completed, 0.0)
                        total_available = pre_draw_available
                        max_out = min(total_available, max_supported)
                        quantity_rows.append(_quantity_flow_row(planning_run_id, alt_id, op, pred, wip_item, buffer_id, requested_qty, pred_completed, starting_available, pred_completed, min(adjusted_scheduled_qty, pre_draw_available), max_out, adjusted_scheduled_qty, unscheduled_qty, quantity_flow_status))

                for segment_index, segment in enumerate(segment_specs, start=1):
                    status = "FULL_OPERATION_SEGMENT" if segment["remaining_qty"] <= 0.0001 else "PARTIAL_OPERATION_SEGMENT" if segment_index == 1 else "CONTINUATION_SEGMENT"
                    segment_op = {
                        **op,
                        "proposed_shift_id": segment["shift"],
                        "proposed_window_id": segment["window_id"],
                        "parallel_capacity_applied_flag": segment["parallel_capacity_applied_flag"],
                        "effective_parallel_lane_count": segment["effective_parallel_lane_count"],
                        "parallel_lane_id": segment["parallel_lane_id"],
                        "assigned_machine_unit_ids": segment["assigned_machine_unit_ids"],
                        "assigned_labor_unit_ids": segment["assigned_labor_unit_ids"],
                        "required_machine_count": segment["required_machine_count"],
                        "required_worker_count": segment["required_worker_count"],
                        "workstation_parallel_authorized_flag": segment["workstation_parallel_authorized_flag"],
                        "labor_parallel_authorized_flag": segment["labor_parallel_authorized_flag"],
                        "resource_bundle_status": segment["resource_bundle_status"],
                        "continuation_resource_bundle_changed_flag": segment["continuation_resource_bundle_changed_flag"],
                    }
                    segment_rows.append(_segment_row(planning_run_id, alt_id, segment_op, segment_index, requested_qty, max_supported, segment["qty"], segment["cumulative_qty"], segment["remaining_qty"], per_unit, segment["setup_minutes"], segment["start_dt"], segment["end_dt"], status))
                    segment_id = segment_rows[-1]["operation_segment_id"]
                    maintenance_window_rows.append(_maintenance_window_row(planning_run_id, alt_id, segment_op, segment_id, segment["start_dt"], segment["end_dt"], "MAINTENANCE_RISK_REVIEW" if _bool(maint_by_op.get((str(alt_id), op_id), {}).get("original_maintenance_conflict_flag")) else "NO_DATED_CONFLICT"))
                if unscheduled_qty > 0:
                    status = "UNSCHEDULED_WIP_SHORTAGE" if _num(op.get("buffer_blocked_output_qty")) > 0.0001 else "UNSCHEDULED_PREDECESSOR_SHORTAGE" if pred_ids and max_supported < requested_qty else "UNSCHEDULED_NO_CAPACITY"
                    segment_rows.append(_segment_row(planning_run_id, alt_id, op, len(segment_specs) + 1, requested_qty, max_supported, 0.0, adjusted_scheduled_qty, unscheduled_qty, per_unit, 0.0, None, None, status))
                new_detail_rows.append(op)

            final_ops = [str(row["operation_id"]) for _, row in ordered.iterrows() if _blank(row.get("successor_operation_ids", ""))]
            finished_qty = min([completed_by_op.get(op_id, 0.0) for op_id in final_ops] or [0.0])
            if final_ops:
                times = [completed_time_by_op[op_id] for op_id in final_ops if op_id in completed_time_by_op]
                if times:
                    alt_finished_time_by_candidate[str(candidate_id)] = max(times)
            alt_finished_by_candidate[str(candidate_id)] = finished_qty

        planned = sum(_num(candidates.get(str(cid), {}).get("planned_production_qty")) for cid in alt_finished_by_candidate)
        covered = sum(alt_finished_by_candidate.values())
        on_time = 0.0
        late = 0.0
        weighted_late = 0.0
        for cand_id, qty in alt_finished_by_candidate.items():
            due = _parse_date(str(candidates.get(cand_id, {}).get("mps_period_end", "")))
            done = alt_finished_time_by_candidate.get(cand_id)
            if done and done <= due + timedelta(days=1):
                on_time += qty
            else:
                late += qty
                if done:
                    weighted_late += max((done.date() - due.date()).days, 0) * qty
        summary = summary_by_alt.get(str(alt_id))
        if summary is not None:
            summary["planned_demand_qty"] = round(planned, 4)
            summary["covered_demand_qty"] = round(covered, 4)
            summary["uncovered_demand_qty"] = round(max(planned - covered, 0.0), 4)
            summary["demand_coverage_pct"] = round(covered / planned * 100.0 if planned else 100.0, 4)
            summary["on_time_completed_qty"] = round(on_time, 4)
            summary["late_completed_qty"] = round(late, 4)
            summary["unscheduled_qty"] = round(max(planned - covered, 0.0), 4)
            summary["lateness_days_weighted"] = round(weighted_late, 4)
            summary["demand_coverage_calculation_basis"] = "SEGMENTED_FULL_ROUTE_QUANTITY_FLOW" if covered > 0 else "NO_FULL_ROUTE_COMPLETION"
            has_violation = any(_bool(row.get("precedence_violation_flag")) for row in new_detail_rows if str(row.get("alternative_id")) == str(alt_id))
            if has_violation:
                summary["hard_feasibility_status"] = "HARD_INFEASIBLE"
            elif covered <= 0:
                summary["hard_feasibility_status"] = "NO_COMPLETE_SCHEDULE"
            elif covered + 0.0001 < planned:
                summary["hard_feasibility_status"] = "PARTIAL_FINITE_SCHEDULE"
            else:
                summary["hard_feasibility_status"] = "HARD_FEASIBLE_WITH_REVIEW"

    shadow_df = _build_time_causal_shadow_rows(
        planning_run_id,
        new_detail_rows,
        starting,
        flow,
        buffers,
    )
    detail_df = _sync_detail_buffer_evidence_from_shadow(
        pd.DataFrame(new_detail_rows, columns=_empty_operation_detail().columns),
        shadow_df,
    )
    segment_df = _sync_segment_buffer_evidence_from_detail(
        pd.DataFrame(segment_rows, columns=_empty_operation_segments().columns),
        detail_df,
    )
    return (
        detail_df,
        segment_df,
        pd.DataFrame(quantity_rows, columns=_empty_quantity_flow().columns),
        shadow_df,
        pd.DataFrame(maintenance_window_rows, columns=_empty_maintenance_window_check().columns),
        list(summary_by_alt.values()),
    )


def _starting_wip_by_item_buffer(ledger: pd.DataFrame) -> dict[tuple[str, str], float]:
    result: dict[tuple[str, str], float] = defaultdict(float)
    if ledger.empty:
        return result
    callable_mask = _to_bool(ledger.get("callable_back_to_line_flag", pd.Series(False, index=ledger.index)))
    for _, row in ledger[callable_mask].iterrows():
        item = str(row.get("wip_item_id", ""))
        buffer_id = str(row.get("current_location_id", ""))
        result[(item, buffer_id)] += _num(row.get("available_accepted_qty"))
    return dict(result)


def _sync_detail_buffer_evidence_from_shadow(detail: pd.DataFrame, shadow: pd.DataFrame) -> pd.DataFrame:
    if detail.empty or shadow.empty:
        return detail
    produced = shadow[shadow["shadow_event_type"].astype(str) == "ADVISORY_PRODUCTION_TO_BUFFER"]
    if produced.empty:
        return detail
    beginning_by_key = produced.groupby(["alternative_id", "schedule_candidate_id", "producer_operation_id"], dropna=False)["shadow_beginning_qty"].first().to_dict()
    detail = detail.copy()
    for idx, row in detail.iterrows():
        if _blank(row.get("output_wip_item_id")) or _num(row.get("final_reconciled_scheduled_qty")) <= 0.0001:
            continue
        key = (str(row["alternative_id"]), str(row["schedule_candidate_id"]), str(row["operation_id"]))
        if key not in beginning_by_key:
            continue
        balance = _num(beginning_by_key[key])
        allowed = _num(row.get("allowed_buffer_capacity_qty"))
        space = max(allowed - balance, 0.0) if allowed > 0 else 0.0
        detail.at[idx, "buffer_balance_before_production"] = round(balance, 4)
        detail.at[idx, "projected_balance_at_completion"] = round(balance, 4)
        detail.at[idx, "available_buffer_space_qty"] = round(space, 4)
        detail.at[idx, "projected_space_at_completion"] = round(space, 4)
    return detail


def _sync_segment_buffer_evidence_from_detail(segments: pd.DataFrame, detail: pd.DataFrame) -> pd.DataFrame:
    if segments.empty or detail.empty:
        return segments
    fields = [
        "buffer_balance_before_production",
        "projected_balance_at_completion",
        "available_buffer_space_qty",
        "projected_space_at_completion",
        "buffer_supported_output_qty",
        "buffer_blocked_output_qty",
        "buffer_check_datetime",
        "buffer_release_datetime",
        "buffer_delay_minutes",
        "buffer_reservation_qty",
        "buffer_reservation_status",
        "buffer_search_attempt_count",
    ]
    lookup = _index_by3(detail, "alternative_id", "schedule_candidate_id", "operation_id")
    segments = segments.copy()
    for idx, row in segments.iterrows():
        source = lookup.get((str(row["alternative_id"]), str(row["schedule_candidate_id"]), str(row["operation_id"])), {})
        for field in fields:
            if field in segments.columns and field in source:
                segments.at[idx, field] = source[field]
    return segments


def _sync_wip_buffer_evidence_from_detail(wip: pd.DataFrame, detail: pd.DataFrame) -> pd.DataFrame:
    if wip.empty or detail.empty:
        return wip
    fields = [
        "buffer_capacity_before_production",
        "buffer_balance_before_production",
        "available_buffer_space_qty",
        "buffer_supported_output_qty",
        "buffer_blocked_output_qty",
        "allowed_buffer_capacity_qty",
        "overflow_policy",
        "buffer_capacity_status",
        "buffer_capacity_blocker_reason",
        "buffer_check_datetime",
        "projected_balance_at_completion",
        "projected_space_at_completion",
        "buffer_release_datetime",
        "buffer_delay_minutes",
        "buffer_reservation_qty",
        "buffer_reservation_status",
        "buffer_search_attempt_count",
    ]
    lookup = _index_by3(detail, "alternative_id", "finished_sku", "operation_id")
    wip = wip.copy()
    for idx, row in wip.iterrows():
        source = lookup.get((str(row["alternative_id"]), str(row["finished_sku"]), str(row["operation_id"])), {})
        for field in fields:
            if field in wip.columns and field in source:
                wip.at[idx, field] = source[field]
    return wip


def _sync_setup_impact_from_segments(setup: pd.DataFrame, segments: pd.DataFrame, detail: pd.DataFrame) -> pd.DataFrame:
    if setup.empty or segments.empty or detail.empty:
        return setup
    result = setup.copy()
    segment_setup = segments[segments["segment_scheduled_qty"].map(_num) > 0].groupby(
        ["alternative_id", "schedule_candidate_id", "operation_id"], dropna=False
    )["segment_setup_minutes"].sum().to_dict()
    detail_lookup = _index_by3(detail, "alternative_id", "schedule_candidate_id", "operation_id")
    for idx, row in result.iterrows():
        key = (str(row.get("alternative_id", "")), str(row.get("schedule_candidate_id", "")), str(row.get("operation_id", "")))
        setup_minutes = _num(segment_setup.get(key, 0.0))
        detail_row = detail_lookup.get(key, {})
        result.at[idx, "setup_capacity_loss_minutes"] = round(setup_minutes, 4)
        result.at[idx, "changeover_time_minutes"] = round(setup_minutes, 4)
        result.at[idx, "actual_changeover_minutes"] = round(setup_minutes, 4)
        if "proposed_schedule_period" in result.columns:
            result.at[idx, "proposed_schedule_period"] = detail_row.get("proposed_schedule_period", row.get("proposed_schedule_period", ""))
        if "proposed_schedule_day" in result.columns:
            result.at[idx, "proposed_schedule_day"] = detail_row.get("proposed_schedule_day", row.get("proposed_schedule_day", ""))
        if "proposed_schedule_shift" in result.columns:
            result.at[idx, "proposed_schedule_shift"] = detail_row.get("proposed_schedule_shift", row.get("proposed_schedule_shift", ""))
        result.at[idx, "setup_switch_flag"] = bool(setup_minutes > 0.0001 and not _blank(row.get("previous_setup_family_id")))
        result.at[idx, "batching_opportunity_flag"] = bool(setup_minutes > 0.0001 and not _blank(row.get("previous_setup_family_id")))
        result.at[idx, "batching_applied_flag"] = bool(row.get("alternative_id") == "ALT-SETUP" and setup_minutes > 0.0001 and not _blank(row.get("previous_setup_family_id")))
        if setup_minutes >= 30:
            status = "HIGH_SETUP_IMPACT"
        elif setup_minutes >= 15:
            status = "MEDIUM_SETUP_IMPACT"
        elif setup_minutes > 0:
            status = "LOW_SETUP_IMPACT"
        else:
            status = "LOW_SETUP_IMPACT"
        result.at[idx, "setup_impact_status"] = status
        result.at[idx, "changeover_complexity"] = "HIGH" if setup_minutes >= 20 else "MEDIUM" if setup_minutes >= 10 else "LOW" if setup_minutes > 0 else "NONE"
    return result


def _build_time_causal_shadow_rows(
    planning_run_id: str,
    detail_rows: list[dict],
    starting: dict[tuple[str, str], float],
    flow: pd.DataFrame,
    buffers: dict[str, dict],
) -> pd.DataFrame:
    detail = pd.DataFrame(detail_rows)
    if detail.empty:
        return _empty_shadow_wip()
    horizon_start = _parse_date(str(detail["candidate_schedule_period"].min()))
    raw_events: list[dict] = []
    for (wip_item_id, buffer_id), qty in sorted(starting.items()):
        if qty <= 0:
            continue
        raw_events.append({
            "alternative_id": "",
            "event_datetime": horizon_start,
            "event_type": "STARTING_ACCEPTED_WIP",
            "schedule_candidate_id": "",
            "operation_segment_id": "",
            "finished_sku": "",
            "wip_item_id": wip_item_id,
            "wip_buffer_id": buffer_id,
            "producer_operation_id": "",
            "consumer_operation_id": "",
            "produced": 0.0,
            "drawn": 0.0,
            "blocked": 0.0,
            "starting_qty": qty,
        })
    for _, op in detail.iterrows():
        scheduled_qty = _num(op.get("final_reconciled_scheduled_qty", op.get("schedulable_production_qty")))
        if scheduled_qty <= 0.0001:
            continue
        alt_id = str(op["alternative_id"])
        candidate_id = str(op["schedule_candidate_id"])
        sku = str(op["finished_sku"])
        op_id = str(op["operation_id"])
        start_dt = _maybe_datetime(op.get("proposed_start_datetime"))
        end_dt = _maybe_datetime(op.get("proposed_end_datetime"))
        if not start_dt or not end_dt:
            continue
        input_rows = flow[(flow["finished_sku"].astype(str) == sku) & (flow["consumed_by_operation_id"].astype(str) == op_id)]
        for _, input_row in input_rows.iterrows():
            wip_item = str(input_row.get("wip_item_id", ""))
            buffer_id = _buffer_for_wip(buffers, wip_item)
            if _blank(wip_item):
                continue
            raw_events.append({
                "alternative_id": alt_id,
                "event_datetime": start_dt,
                "period": str(op.get("candidate_schedule_period", "")),
                "event_type": "ADVISORY_DRAW_FOR_OPERATION",
                "schedule_candidate_id": candidate_id,
                "operation_segment_id": "",
                "finished_sku": sku,
                "wip_item_id": wip_item,
                "wip_buffer_id": buffer_id,
                "producer_operation_id": str(input_row.get("produced_by_operation_id", "")),
                "consumer_operation_id": op_id,
                "produced": 0.0,
                "drawn": scheduled_qty,
                "blocked": 0.0,
                "starting_qty": 0.0,
            })
        output_rows = flow[(flow["finished_sku"].astype(str) == sku) & (flow["produced_by_operation_id"].astype(str) == op_id)]
        for _, output_row in output_rows.iterrows():
            wip_item = str(output_row.get("wip_item_id", ""))
            buffer_id = _buffer_for_wip(buffers, wip_item)
            if _blank(wip_item):
                continue
            raw_events.append({
                "alternative_id": alt_id,
                "event_datetime": end_dt,
                "period": str(op.get("candidate_schedule_period", "")),
                "event_type": "ADVISORY_PRODUCTION_TO_BUFFER",
                "schedule_candidate_id": candidate_id,
                "operation_segment_id": "",
                "finished_sku": sku,
                "wip_item_id": wip_item,
                "wip_buffer_id": buffer_id,
                "producer_operation_id": op_id,
                "consumer_operation_id": str(output_row.get("consumed_by_operation_id", "")),
                "produced": scheduled_qty,
                "drawn": 0.0,
                "blocked": 0.0,
                "starting_qty": 0.0,
            })
    alt_ids = sorted(detail["alternative_id"].astype(str).unique())
    seeded_events = []
    for event in raw_events:
        if event["event_type"] == "STARTING_ACCEPTED_WIP":
            for alt_id in alt_ids:
                seeded_events.append({**event, "alternative_id": alt_id})
        else:
            seeded_events.append(event)
    type_order = {"STARTING_ACCEPTED_WIP": 0, "ADVISORY_PRODUCTION_TO_BUFFER": 1, "ADVISORY_DRAW_FOR_OPERATION": 2}
    seeded_events.sort(key=lambda item: (
        item["alternative_id"],
        item["event_datetime"],
        type_order.get(item["event_type"], 9),
        item["schedule_candidate_id"],
        item["producer_operation_id"],
        item["consumer_operation_id"],
        item["wip_item_id"],
        item["wip_buffer_id"],
    ))
    rows = []
    balances: dict[tuple[str, str, str], float] = defaultdict(float)
    lots: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    sequence_by_alt: dict[str, int] = defaultdict(int)
    pending_rows: list[dict] = []
    for event in seeded_events:
        alt_id = event["alternative_id"]
        key = (alt_id, event["wip_item_id"], event["wip_buffer_id"])
        beginning = balances[key]
        if event["event_type"] == "STARTING_ACCEPTED_WIP":
            produced = _num(event["starting_qty"])
            drawn = blocked = 0.0
            ending = beginning + produced
            lot_id = f"LOT-START-{event['wip_item_id']}-{event['wip_buffer_id']}"
            lots[key].append({
                "lot_id": lot_id,
                "availability_datetime": event["event_datetime"],
                "remaining_qty": produced,
            })
            balances[key] = ending
            sequence_by_alt[alt_id] += 1
            pending_rows.append(_shadow_event_row(
                planning_run_id,
                alt_id,
                sequence_by_alt[alt_id],
                event["schedule_candidate_id"],
                event["operation_segment_id"],
                event["finished_sku"],
                event["wip_item_id"],
                event["wip_buffer_id"],
                event["producer_operation_id"],
                event["consumer_operation_id"],
                event["event_type"],
                beginning,
                produced,
                drawn,
                blocked,
                ending,
                buffers,
                event_dt=event["event_datetime"],
                lot_id=lot_id,
                lot_availability_datetime=event["event_datetime"],
                lot_beginning_qty=0.0,
                lot_drawn_qty=0.0,
                lot_ending_qty=produced,
            ))
            continue
        if event["event_type"] == "ADVISORY_PRODUCTION_TO_BUFFER":
            produced = _num(event["produced"])
            drawn = _num(event["drawn"])
            blocked = _num(event["blocked"])
            ending = beginning + produced - drawn - blocked
            allowed, _, _ = _allowed_buffer_capacity(buffers.get(event["wip_buffer_id"], {}))
            if allowed > 0 and ending > allowed:
                overflow_block = ending - allowed
                blocked += overflow_block
                ending = allowed
            drawable_produced = max(produced - blocked, 0.0)
            lot_id = f"LOT-{alt_id}-{event['schedule_candidate_id']}-{event['producer_operation_id']}-{event['wip_item_id']}"
            if drawable_produced > 0.0001:
                lots[key].append({
                    "lot_id": lot_id,
                    "availability_datetime": event["event_datetime"],
                    "remaining_qty": drawable_produced,
                })
            balances[key] = ending
            sequence_by_alt[alt_id] += 1
            pending_rows.append(_shadow_event_row(
                planning_run_id,
                alt_id,
                sequence_by_alt[alt_id],
                event["schedule_candidate_id"],
                event["operation_segment_id"],
                event["finished_sku"],
                event["wip_item_id"],
                event["wip_buffer_id"],
                event["producer_operation_id"],
                event["consumer_operation_id"],
                event["event_type"],
                beginning,
                produced,
                drawn,
                blocked,
                ending,
                buffers,
                event_dt=event["event_datetime"],
                lot_id=lot_id,
                lot_availability_datetime=event["event_datetime"],
                lot_beginning_qty=0.0,
                lot_drawn_qty=0.0,
                lot_ending_qty=drawable_produced,
            ))
            continue
        if event["event_type"] == "ADVISORY_DRAW_FOR_OPERATION":
            remaining_draw = _num(event["drawn"])
            for lot in sorted(lots.get(key, []), key=lambda item: (item["availability_datetime"], item["lot_id"])):
                if remaining_draw <= 0.0001:
                    break
                if lot["availability_datetime"] > event["event_datetime"]:
                    continue
                lot_beginning = _num(lot.get("remaining_qty"))
                if lot_beginning <= 0.0001:
                    continue
                take = min(lot_beginning, remaining_draw)
                event_beginning = balances[key]
                event_ending = event_beginning - take
                lot["remaining_qty"] = lot_beginning - take
                balances[key] = event_ending
                remaining_draw -= take
                sequence_by_alt[alt_id] += 1
                pending_rows.append(_shadow_event_row(
                    planning_run_id,
                    alt_id,
                    sequence_by_alt[alt_id],
                    event["schedule_candidate_id"],
                    event["operation_segment_id"],
                    event["finished_sku"],
                    event["wip_item_id"],
                    event["wip_buffer_id"],
                    event["producer_operation_id"],
                    event["consumer_operation_id"],
                    event["event_type"],
                    event_beginning,
                    0.0,
                    take,
                    0.0,
                    event_ending,
                    buffers,
                    event_dt=event["event_datetime"],
                    lot_id=str(lot.get("lot_id", "")),
                    lot_availability_datetime=lot.get("availability_datetime"),
                    lot_beginning_qty=lot_beginning,
                    lot_drawn_qty=take,
                    lot_ending_qty=lot["remaining_qty"],
                ))
            continue
    rows.extend(pending_rows)
    return pd.DataFrame(rows, columns=_empty_shadow_wip().columns)


def _segment_schedule_json(segments: list[dict], requested_qty: float, processing_total: float) -> str:
    serializable = []
    for segment in segments:
        processing_minutes = _num(segment.get("processing_minutes"))
        segment_qty = requested_qty * processing_minutes / processing_total if processing_total > 0 else 0.0
        serializable.append({
            "date": segment.get("date", ""),
            "shift": segment.get("shift", ""),
            "window_id": segment.get("window_id", ""),
            "start": segment.get("start", ""),
            "end": segment.get("end", ""),
            "allocated_minutes": round(_num(segment.get("allocated_minutes")), 6),
            "processing_minutes": round(processing_minutes, 6),
            "setup_minutes": round(_num(segment.get("setup_minutes")), 6),
            "segment_qty": round(segment_qty, 6),
            "remaining_minutes": round(_num(segment.get("remaining_minutes")), 6),
            "parallel_capacity_applied_flag": bool(segment.get("parallel_capacity_applied_flag", False)),
            "effective_parallel_lane_count": int(_num(segment.get("effective_parallel_lane_count", 1))) or 1,
            "parallel_lane_id": segment.get("parallel_lane_id", ""),
            "assigned_machine_unit_ids": segment.get("assigned_machine_unit_ids", ""),
            "assigned_labor_unit_ids": segment.get("assigned_labor_unit_ids", ""),
            "required_machine_count": int(_num(segment.get("required_machine_count", 1))) or 1,
            "required_worker_count": int(_num(segment.get("required_worker_count", 1))) or 1,
            "workstation_parallel_authorized_flag": bool(segment.get("workstation_parallel_authorized_flag", False)),
            "labor_parallel_authorized_flag": bool(segment.get("labor_parallel_authorized_flag", False)),
            "resource_bundle_status": segment.get("resource_bundle_status", "RESOURCE_BUNDLE_ASSIGNED"),
            "continuation_resource_bundle_changed_flag": bool(segment.get("continuation_resource_bundle_changed_flag", False)),
        })
    return json.dumps(serializable, separators=(",", ":"))


def _load_segment_plan(value: object) -> list[dict]:
    if _blank(value):
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _buffer_for_wip(buffers: dict[str, dict], wip_item_id: str) -> str:
    for buffer_id, row in buffers.items():
        if str(row.get("wip_item_id", "")) == str(wip_item_id):
            return str(buffer_id)
    return ""


def _maybe_datetime(value: object) -> datetime | None:
    if _blank(value):
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _quantity_flow_row(planning_run_id: str, alt_id: str, op: dict, pred: str, wip_item: str, buffer_id: str, requested: float, pred_completed: float, starting_wip: float, advisory_available: float, drawn: float, max_supported: float, scheduled: float, unscheduled: float, status: str) -> dict:
    balance = requested - scheduled - unscheduled
    return {
        "planning_run_id": planning_run_id,
        "alternative_id": alt_id,
        "schedule_candidate_id": op["schedule_candidate_id"],
        "finished_sku": op["finished_sku"],
        "operation_id": op["operation_id"],
        "operation_name": op["operation_name"],
        "predecessor_operation_id": pred,
        "direct_input_wip_item_id": wip_item,
        "direct_input_wip_buffer_id": buffer_id,
        "required_input_qty_per_output_unit": 1.0,
        "quantity_ratio_basis": "ASSUMED_ONE_TO_ONE",
        "requested_output_qty": round(requested, 4),
        "predecessor_completed_qty_available": round(pred_completed, 4),
        "starting_accepted_wip_available": round(starting_wip, 4),
        "advisory_wip_produced_available": round(advisory_available, 4),
        "advisory_wip_already_drawn": round(drawn, 4),
        "total_input_qty_available": round(pred_completed + starting_wip, 4),
        "maximum_supported_output_qty": round(max_supported, 4),
        "scheduled_output_qty": round(scheduled, 4),
        "unscheduled_output_qty": round(unscheduled, 4),
        "quantity_flow_status": status,
        "quantity_balance_check": round(balance, 6),
        "quantity_balance_status": "BALANCED" if abs(balance) <= 0.0001 and scheduled <= max_supported + 0.0001 else "REVIEW_REQUIRED",
        "advisory_only_flag": True,
    }


def _segment_row(planning_run_id: str, alt_id: str, op: dict, seq: int, requested: float, available: float, segment_qty: float, cumulative_qty: float, remaining_qty: float, per_unit: float, setup_minutes: float, start_dt: datetime | None, end_dt: datetime | None, status: str) -> dict:
    segment_id = f"SEG-{alt_id}-{op['schedule_candidate_id']}-{op['operation_id']}-{seq:02d}"
    processing_minutes = segment_qty * per_unit
    return {
        "planning_run_id": planning_run_id,
        "alternative_id": alt_id,
        "operation_segment_id": segment_id,
        "schedule_candidate_id": op["schedule_candidate_id"],
        "finished_sku": op["finished_sku"],
        "operation_id": op["operation_id"],
        "operation_name": op["operation_name"],
        "segment_sequence": seq,
        "requested_operation_qty": round(requested, 4),
        "quantity_available_from_predecessors": round(available, 4),
        "quantity_supported_before_capacity": round(_num(op.get("quantity_supported_before_capacity", available)), 4),
        "scheduling_target_qty": round(_num(op.get("scheduling_target_qty", min(requested, available))), 4),
        "segment_scheduled_qty": round(segment_qty, 4),
        "cumulative_scheduled_qty": round(cumulative_qty, 4),
        "remaining_unscheduled_qty": round(remaining_qty, 4),
        "buffer_capacity_before_production": round(_num(op.get("buffer_capacity_before_production")), 4),
        "buffer_balance_before_production": round(_num(op.get("buffer_balance_before_production")), 4),
        "available_buffer_space_qty": round(_num(op.get("available_buffer_space_qty")), 4),
        "buffer_supported_output_qty": round(_num(op.get("buffer_supported_output_qty")), 4),
        "buffer_blocked_output_qty": round(_num(op.get("buffer_blocked_output_qty")), 4),
        "allowed_buffer_capacity_qty": round(_num(op.get("allowed_buffer_capacity_qty")), 4),
        "overflow_policy": op.get("overflow_policy", ""),
        "buffer_capacity_status": op.get("buffer_capacity_status", ""),
        "buffer_capacity_blocker_reason": op.get("buffer_capacity_blocker_reason", ""),
        "buffer_check_datetime": op.get("buffer_check_datetime", ""),
        "projected_balance_at_completion": round(_num(op.get("projected_balance_at_completion")), 4),
        "projected_space_at_completion": round(_num(op.get("projected_space_at_completion")), 4),
        "buffer_release_datetime": op.get("buffer_release_datetime", ""),
        "buffer_delay_minutes": round(_num(op.get("buffer_delay_minutes")), 4),
        "buffer_reservation_qty": round(_num(op.get("buffer_reservation_qty")), 4),
        "buffer_reservation_status": op.get("buffer_reservation_status", ""),
        "buffer_search_attempt_count": int(_num(op.get("buffer_search_attempt_count"))),
        "proposed_schedule_date": start_dt.date().isoformat() if start_dt else "",
        "proposed_shift_id": op.get("proposed_shift_id", ""),
        "proposed_window_id": op.get("proposed_window_id", ""),
        "proposed_start_datetime": start_dt.isoformat(timespec="minutes") if start_dt else "",
        "proposed_end_datetime": end_dt.isoformat(timespec="minutes") if end_dt else "",
        "workstation_id": op["workstation_id"],
        "machine_id": op["machine_id"],
        "labor_skill_id": "",
        "processing_minutes_per_unit": round(per_unit, 6),
        "segment_processing_minutes": round(processing_minutes, 4),
        "segment_setup_minutes": round(setup_minutes, 4),
        "segment_total_minutes": round(processing_minutes + setup_minutes, 4),
        "setup_applied_flag": setup_minutes > 0,
        "parallel_capacity_applied_flag": _bool(op.get("parallel_capacity_applied_flag")),
        "effective_parallel_lane_count": int(_num(op.get("effective_parallel_lane_count", 1))) or 1,
        "parallel_lane_id": op.get("parallel_lane_id", ""),
        "assigned_machine_unit_ids": op.get("assigned_machine_unit_ids", ""),
        "assigned_labor_unit_ids": op.get("assigned_labor_unit_ids", ""),
        "required_machine_count": int(_num(op.get("required_machine_count", 1))) or 1,
        "required_worker_count": int(_num(op.get("required_worker_count", 1))) or 1,
        "workstation_parallel_authorized_flag": _bool(op.get("workstation_parallel_authorized_flag")),
        "labor_parallel_authorized_flag": _bool(op.get("labor_parallel_authorized_flag")),
        "resource_bundle_status": op.get("resource_bundle_status", "RESOURCE_BUNDLE_ASSIGNED" if segment_qty > 0 else "RESOURCE_BUNDLE_NOT_ASSIGNED"),
        "continuation_resource_bundle_changed_flag": _bool(op.get("continuation_resource_bundle_changed_flag")),
        "segment_predecessor_ready_datetime": op.get("predecessor_ready_datetime", ""),
        "input_quantity_availability_datetime": op.get("input_quantity_availability_datetime", op.get("predecessor_ready_datetime", "")),
        "resource_reserved_for_supported_qty_flag": _bool(op.get("resource_reserved_for_supported_qty_flag")),
        "segment_capacity_status": op.get("operation_schedule_status", ""),
        "segment_maintenance_status": "MAINTENANCE_RISK_REVIEW" if status.startswith("UNSCHEDULED_MAINTENANCE") else "NO_DATED_CONFLICT",
        "segment_schedule_status": status,
        "advisory_only_flag": True,
    }


def _shadow_event_row(
    planning_run_id: str,
    alt_id: str,
    sequence: int,
    candidate_id: str,
    segment_id: str,
    sku: str,
    wip_item: str,
    buffer_id: str,
    producer: str,
    consumer: str,
    event_type: str,
    beginning: float,
    produced: float,
    drawn: float,
    blocked: float,
    ending: float,
    buffers: dict[str, dict],
    event_dt: datetime | None = None,
    lot_id: str = "",
    lot_availability_datetime: datetime | None = None,
    lot_beginning_qty: float = 0.0,
    lot_drawn_qty: float = 0.0,
    lot_ending_qty: float = 0.0,
) -> dict:
    max_qty = _num(buffers.get(buffer_id, {}).get("max_buffer_qty"))
    overflow = max(ending - max_qty, 0.0) if max_qty > 0 else 0.0
    return {
        "planning_run_id": planning_run_id,
        "alternative_id": alt_id,
        "shadow_wip_event_id": f"SWIP-{alt_id}-{sequence:05d}",
        "event_sequence": sequence,
        "event_datetime": event_dt.isoformat(timespec="minutes") if event_dt else "",
        "lot_id": lot_id,
        "lot_availability_datetime": lot_availability_datetime.isoformat(timespec="minutes") if lot_availability_datetime else "",
        "lot_selection_method": "FIFO" if event_type == "ADVISORY_DRAW_FOR_OPERATION" else "",
        "lot_beginning_qty": round(lot_beginning_qty, 4),
        "lot_drawn_qty": round(lot_drawn_qty, 4),
        "lot_ending_qty": round(lot_ending_qty, 4),
        "shelf_life_controlled_flag": False,
        "shelf_life_hours": "",
        "expiration_datetime": "",
        "schedule_candidate_id": candidate_id,
        "operation_segment_id": segment_id,
        "finished_sku": sku,
        "wip_item_id": wip_item,
        "wip_buffer_id": buffer_id,
        "producer_operation_id": producer,
        "consumer_operation_id": consumer,
        "shadow_event_type": event_type,
        "shadow_beginning_qty": round(beginning, 4),
        "advisory_produced_qty": round(produced, 4),
        "advisory_drawn_qty": round(drawn, 4),
        "advisory_blocked_qty": round(blocked, 4),
        "shadow_ending_qty": round(ending, 4),
        "buffer_max_qty": round(max_qty, 4),
        "buffer_overflow_qty": round(overflow, 4),
        "shadow_balance_status": "BALANCED" if ending >= -0.0001 and overflow <= 0.0001 else "REVIEW_REQUIRED",
        "note_no_actual_wip_consumption_flag": True,
        "advisory_only_flag": True,
    }


def _maintenance_window_row(planning_run_id: str, alt_id: str, op: dict, segment_id: str, start_dt: datetime, end_dt: datetime, status: str) -> dict:
    risk = "HIGH" if status == "MAINTENANCE_RISK_REVIEW" else "LOW"
    return {
        "planning_run_id": planning_run_id,
        "alternative_id": alt_id,
        "machine_id": op["machine_id"],
        "workstation_id": op["workstation_id"],
        "maintenance_plan_id": "",
        "production_operation_segment_id": segment_id,
        "production_start_datetime": start_dt.isoformat(timespec="minutes"),
        "production_end_datetime": end_dt.isoformat(timespec="minutes"),
        "maintenance_window_id": "",
        "maintenance_start_datetime": "",
        "maintenance_end_datetime": "",
        "maintenance_window_source": "RISK_ONLY_NO_DATED_DOWNTIME",
        "maintenance_window_selected_flag": False,
        "dated_overlap_flag": False,
        "machine_state_unavailable_flag": False,
        "maintenance_risk_level": risk,
        "maintenance_window_check_status": status,
        "maintenance_avoidance_applied_flag": False,
        "maintenance_avoidance_evidence": "Maintenance risk is review-only without dated downtime; no horizon-wide production block applied.",
        "note_no_maintenance_order_created_flag": True,
        "advisory_only_flag": True,
    }


def _apply_setup_savings(rows: list[dict], baseline: dict[tuple[str, str], float]) -> None:
    baseline_total = sum(_num(value) for value in baseline.values())
    scheduled_rows = [row for row in rows if not _blank(row.get("proposed_schedule_period"))]
    actual_total = sum(_num(row.get("actual_changeover_minutes")) for row in scheduled_rows)
    total_saved = max(baseline_total - actual_total, 0.0) if baseline_total > 0 and actual_total > 0 and scheduled_rows else 0.0
    eligible_indexes = [
        index
        for index, row in enumerate(rows)
        if not _blank(row.get("proposed_schedule_period")) and (_bool(row.get("batching_applied_flag")) or _bool(row.get("setup_switch_flag")))
    ]
    if total_saved > 0 and not eligible_indexes:
        eligible_indexes = list(range(len(rows)))
    distributed = total_saved / len(eligible_indexes) if eligible_indexes else 0.0
    for row in rows:
        key = (str(row.get("schedule_candidate_id", "")), str(row.get("operation_id", "")))
        baseline_minutes = _num(baseline.get(key, row.get("actual_changeover_minutes")))
        row["baseline_changeover_minutes"] = round(baseline_minutes, 4)
        row["setup_minutes_saved_vs_baseline"] = 0.0
        row["setup_saving_supported_flag"] = False
    for index in eligible_indexes:
        rows[index]["setup_minutes_saved_vs_baseline"] = round(distributed, 4)
        rows[index]["setup_saving_supported_flag"] = total_saved > 0


def _alternative_summary(frames: dict[str, pd.DataFrame], alt_id: str, alt_type: str, ops: list[dict]) -> dict:
    candidates = frames["candidates"]
    planned = candidates["planned_production_qty"].map(_num).sum()
    final_ops = [row for row in ops if not row["successor_operation_ids"] and row["schedulable_production_qty"] > 0 and row["operation_schedule_status"] not in {"UNSCHEDULED_NO_FEASIBLE_WINDOW", "HARD_INFEASIBLE"}]
    covered = sum(_num(row["schedulable_production_qty"]) for row in final_ops)
    late = sum(_num(row["schedulable_production_qty"]) for row in final_ops if row["proposed_schedule_date"] and row["proposed_schedule_date"] > str(candidates.set_index("schedule_candidate_id").loc[row["schedule_candidate_id"], "mps_period_end"]))
    unscheduled_qty = max(planned - covered, 0.0)
    coverage = covered / planned * 100.0 if planned > 0 else 100.0
    hard_values = {row["operation_hard_feasibility_status"] for row in ops}
    if not final_ops:
        hard = "NO_COMPLETE_SCHEDULE"
    elif "HARD_INFEASIBLE" in hard_values:
        hard = "HARD_INFEASIBLE"
    elif "REVIEW_REQUIRED" in hard_values:
        hard = "REVIEW_REQUIRED"
    elif "HARD_FEASIBLE_WITH_REVIEW" in hard_values or unscheduled_qty > 0:
        hard = "HARD_FEASIBLE_WITH_REVIEW"
    else:
        hard = "HARD_FEASIBLE"
    return {
        "planning_run_id": _planning_run_id(frames),
        "alternative_id": alt_id,
        "alternative_type": alt_type,
        "finished_sku_count": candidates["finished_sku"].nunique(),
        "schedule_candidate_count": candidates["schedule_candidate_id"].nunique(),
        "operation_count": len(ops),
        "planned_demand_qty": round(planned, 4),
        "covered_demand_qty": round(covered, 4),
        "uncovered_demand_qty": round(max(planned - covered, 0.0), 4),
        "demand_coverage_pct": round(max(min(coverage, 100.0), 0.0), 4),
        "on_time_completed_qty": round(max(covered - late, 0.0), 4),
        "late_completed_qty": round(late, 4),
        "unscheduled_qty": round(unscheduled_qty, 4),
        "lateness_days_weighted": round(late * 1.0, 4),
        "demand_coverage_calculation_basis": "PARTIAL_LOT_FULL_ROUTE_COMPLETION" if covered > 0 and unscheduled_qty > 0 else "FULL_ROUTE_COMPLETED_QUANTITY" if covered > 0 else "NO_FULL_ROUTE_COMPLETION",
        "hard_feasibility_status": hard,
    }


def _build_cost_score(frames: dict[str, pd.DataFrame], summaries: list[dict], operation_detail: pd.DataFrame, capacity_impact: pd.DataFrame, wip_impact: pd.DataFrame, setup_impact: pd.DataFrame, maintenance_impact: pd.DataFrame, operation_segments: pd.DataFrame) -> pd.DataFrame:
    rows = []
    labor_rate_by_ws = _labor_rate_by_workstation(frames["labor"])
    machine_cost_by_id = {str(row["machine_id"]): _num(row.get("hourly_machine_cost")) for _, row in frames["machines"].iterrows()}
    for summary in summaries:
        alt_id = summary["alternative_id"]
        ops = operation_detail[operation_detail["alternative_id"] == alt_id]
        seg = operation_segments[operation_segments["alternative_id"] == alt_id]
        cap = capacity_impact[capacity_impact["alternative_id"] == alt_id]
        wip = wip_impact[wip_impact["alternative_id"] == alt_id]
        setup = setup_impact[setup_impact["alternative_id"] == alt_id]
        maint = maintenance_impact[maintenance_impact["alternative_id"] == alt_id]
        scheduled_seg = seg[seg["segment_scheduled_qty"].map(_num) > 0]
        validated_machine = sum((_num(row["segment_processing_minutes"]) / 60.0) * machine_cost_by_id.get(str(row["machine_id"]), 0.0) for _, row in scheduled_seg.iterrows())
        validated_labor = sum((_num(row["segment_total_minutes"]) / 60.0) * labor_rate_by_ws.get(str(row["workstation_id"]), 0.0) for _, row in scheduled_seg.iterrows())
        assumed_setup = scheduled_seg["segment_setup_minutes"].map(_num).sum() / 60.0 * 20.0
        assumed_wip = wip["projected_wip_ending_qty_advisory"].map(_num).sum() * 0.08
        proxy_late = _num(summary["uncovered_demand_qty"]) * 80.0
        proxy_customer = _num(summary["uncovered_demand_qty"]) * 45.0
        proxy_capacity = cap["capacity_overload_penalty"].map(_num).sum()
        proxy_maint = maint["maintenance_conflict_penalty"].map(_num).sum()
        proxy_breakdown = maint["breakdown_risk_penalty"].map(_num).sum()
        proxy_wip_short = wip["wip_shortage_penalty"].map(_num).sum()
        proxy_wip_over = wip["wip_overflow_penalty"].map(_num).sum()
        proxy_bq = _bottleneck_queue_penalty(frames, ops)
        proxy_under = cap["underutilization_penalty"].map(_num).sum()
        infeasible = int((ops["operation_hard_feasibility_status"] == "HARD_INFEASIBLE").sum()) * 50000.0
        review = int(ops["operation_hard_feasibility_status"].isin(["HARD_FEASIBLE_WITH_REVIEW", "REVIEW_REQUIRED"]).sum()) * 450.0
        validated_total = validated_machine + validated_labor
        assumed_total = assumed_setup + assumed_wip
        proxy_total = proxy_late + proxy_customer + proxy_capacity + proxy_maint + proxy_breakdown + proxy_wip_short + proxy_wip_over + proxy_bq + proxy_under
        rows.append({
            "planning_run_id": _planning_run_id(frames),
            "alternative_id": alt_id,
            "alternative_type": summary["alternative_type"],
            "real_setup_cost": 0.0,
            "real_processing_cost": round(validated_machine, 4),
            "real_labor_cost": round(validated_labor, 4),
            "real_quality_cost": 0.0,
            "real_maintenance_cost": 0.0,
            "real_wip_holding_cost": 0.0,
            "validated_real_cost_total": round(validated_total, 4),
            "assumed_monetary_cost_total": round(assumed_total, 4),
            "proxy_late_demand_penalty": round(proxy_late, 4),
            "proxy_customer_dissatisfaction_penalty": round(proxy_customer, 4),
            "proxy_capacity_overload_penalty": round(proxy_capacity, 4),
            "proxy_maintenance_conflict_penalty": round(proxy_maint, 4),
            "proxy_breakdown_risk_penalty": round(proxy_breakdown, 4),
            "proxy_wip_shortage_penalty": round(proxy_wip_short, 4),
            "proxy_wip_overflow_penalty": round(proxy_wip_over, 4),
            "proxy_bottleneck_queue_penalty": round(proxy_bq, 4),
            "proxy_underutilization_penalty": round(proxy_under, 4),
            "infeasibility_penalty": round(infeasible, 4),
            "review_required_penalty": round(review, 4),
            "total_real_cost": round(validated_total, 4),
            "total_proxy_penalty": round(proxy_total, 4),
            "total_advisory_schedule_score": round(validated_total + assumed_total + proxy_total + infeasible + review, 4),
            "cost_basis": "VALIDATED_PLUS_ASSUMED" if proxy_total == 0 else "ASSUMED_AND_PROXY",
            "cost_confidence": "LOW",
            "assumption_flag": True,
            "scheduled_processing_minutes": round(scheduled_seg["segment_processing_minutes"].map(_num).sum(), 4),
            "scheduled_setup_minutes": round(scheduled_seg["segment_setup_minutes"].map(_num).sum(), 4),
            "scheduled_labor_minutes": round(scheduled_seg["segment_total_minutes"].map(_num).sum(), 4),
            "unscheduled_quantity": round(seg["remaining_unscheduled_qty"].map(_num).sum(), 4),
            "scheduled_cost_calculation_basis": "ALLOCATED_OPERATION_SEGMENTS" if not scheduled_seg.empty else "NO_SCHEDULED_WORK",
            "unscheduled_penalty_calculation_basis": "UNSCHEDULED_ROUTE_QUANTITY_PROXY_PENALTY",
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_empty_cost_score().columns)


def _build_master(frames: dict[str, pd.DataFrame], summaries: list[dict], cost_score: pd.DataFrame) -> pd.DataFrame:
    cost_by_alt = _index_by(cost_score, "alternative_id")
    rows = []
    for summary in summaries:
        cost = cost_by_alt.get(summary["alternative_id"], {})
        rows.append({
            **summary,
            "alternative_name": summary["alternative_name"],
            "alternative_description": summary["alternative_description"],
            "total_real_cost": cost.get("total_real_cost", 0.0),
            "validated_real_cost_total": cost.get("validated_real_cost_total", 0.0),
            "assumed_monetary_cost_total": cost.get("assumed_monetary_cost_total", 0.0),
            "total_proxy_penalty": cost.get("total_proxy_penalty", 0.0),
            "total_advisory_schedule_score": cost.get("total_advisory_schedule_score", 0.0),
            "cost_basis": cost.get("cost_basis", "REVIEW_REQUIRED"),
            "cost_confidence": cost.get("cost_confidence", "LOW"),
            "recommendation_rank": 0,
            "recommendation_status": "REVIEW_REQUIRED",
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    rows = sorted(rows, key=lambda r: (_hard_sort(r["hard_feasibility_status"]), -_num(r["demand_coverage_pct"]), _num(r["total_advisory_schedule_score"])))
    any_feasible = any(row["hard_feasibility_status"] in {"HARD_FEASIBLE", "HARD_FEASIBLE_WITH_REVIEW"} for row in rows)
    any_partial = any(row["hard_feasibility_status"] == "PARTIAL_FINITE_SCHEDULE" for row in rows)
    for idx, row in enumerate(rows, start=1):
        row["recommendation_rank"] = idx
        if row["hard_feasibility_status"] in {"HARD_INFEASIBLE", "NO_COMPLETE_SCHEDULE"}:
            row["recommendation_status"] = "LEAST_RISK_BLOCKED_ALTERNATIVE" if idx == 1 and not any_feasible else "NOT_RECOMMENDED_INFEASIBLE"
        elif row["hard_feasibility_status"] == "PARTIAL_FINITE_SCHEDULE":
            row["recommendation_status"] = "LEAST_RISK_PARTIAL_ALTERNATIVE" if idx == 1 or (not any_feasible and any_partial) else "LEAST_COST_PARTIAL_ALTERNATIVE"
        elif idx == 1 and row["alternative_type"] == "LEAST_RISK_COMBINED":
            row["recommendation_status"] = "LEAST_RISK_ALTERNATIVE"
        elif idx == 1:
            row["recommendation_status"] = "RECOMMENDED_ADVISORY_ALTERNATIVE"
        else:
            row["recommendation_status"] = "FEASIBLE_WITH_REVIEW"
    return pd.DataFrame(rows, columns=_empty_master().columns)


def _build_recommendations(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in master.iterrows():
        readiness = "READY_FOR_MANAGER_REVIEW"
        if row["hard_feasibility_status"] in {"HARD_INFEASIBLE", "NO_COMPLETE_SCHEDULE"}:
            readiness = "NOT_READY"
        elif "MAINT" in str(row["alternative_id"]):
            readiness = "NEEDS_MAINTENANCE_REVIEW"
        elif "WIP" in str(row["alternative_id"]):
            readiness = "NEEDS_WIP_REVIEW"
        elif "SETUP" in str(row["alternative_id"]):
            readiness = "NEEDS_CAPACITY_REVIEW"
        rows.append({
            "recommendation_id": f"REC-{int(row['recommendation_rank']):02d}",
            "planning_run_id": row["planning_run_id"],
            "alternative_id": row["alternative_id"],
            "alternative_type": row["alternative_type"],
            "recommendation_rank": row["recommendation_rank"],
            "recommendation_status": row["recommendation_status"],
            "recommendation_summary": f"{row['alternative_type']} ranked {row['recommendation_rank']} with completed-demand coverage {row['demand_coverage_pct']}%.",
            "demand_coverage_pct": row["demand_coverage_pct"],
            "total_real_cost": row["total_real_cost"],
            "validated_real_cost_total": row["validated_real_cost_total"],
            "assumed_monetary_cost_total": row["assumed_monetary_cost_total"],
            "total_proxy_penalty": row["total_proxy_penalty"],
            "total_advisory_schedule_score": row["total_advisory_schedule_score"],
            "main_benefit": _main_benefit(row["alternative_type"]),
            "main_risk": _main_risk(row["hard_feasibility_status"], row["cost_confidence"]),
            "remaining_blocker_summary": f"Hard feasibility={row['hard_feasibility_status']}; unscheduled_qty={row['unscheduled_qty']}.",
            "recommended_manager_action": "REVIEW_ADVISORY_ALTERNATIVE_BEFORE_RELEASE",
            "implementation_readiness_status": readiness,
            "auto_action_allowed": False,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_empty_recommendations().columns)


def _build_review_queue(master: pd.DataFrame, detail: pd.DataFrame, capacity: pd.DataFrame, wip: pd.DataFrame, setup: pd.DataFrame, maintenance: pd.DataFrame, recommendations: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def add(alt: str, cand: str, sku: str, op: str, issue: str, sev: str, msg: str, action: str) -> None:
        rows.append({
            "review_item_id": f"SALT-REV-{len(rows)+1:04d}",
            "planning_run_id": master.iloc[0]["planning_run_id"],
            "alternative_id": alt,
            "schedule_candidate_id": cand,
            "finished_sku": sku,
            "operation_id": op,
            "issue_type": issue,
            "issue_severity": sev,
            "issue_description": msg,
            "recommended_review_action": action,
            "auto_action_allowed": False,
            "advisory_only_flag": True,
        })
    for _, row in master.iterrows():
        if row["hard_feasibility_status"] in {"HARD_INFEASIBLE", "NO_COMPLETE_SCHEDULE"}:
            add(row["alternative_id"], "", "", "", "HARD_INFEASIBLE_ALTERNATIVE", "CRITICAL", "Alternative does not produce a complete hard-feasible schedule.", "REVIEW_HARD_FEASIBILITY")
        if _num(row["total_proxy_penalty"]) > 100000:
            add(row["alternative_id"], "", "", "", "HIGH_PROXY_COST_ASSUMPTION", "HIGH", "Alternative uses high proxy penalties; these are not real euros.", "REVIEW_COST_ASSUMPTIONS")
        if _num(row["demand_coverage_pct"]) < 95:
            add(row["alternative_id"], "", "", "", "LOW_DEMAND_COVERAGE", "HIGH", "Completed full-route quantity does not cover planned demand.", "REVIEW_DEMAND_SATISFACTION")
    for _, row in detail[detail["operation_schedule_status"].isin(["UNSCHEDULED_NO_FEASIBLE_WINDOW", "BLOCKED_REVIEW_REQUIRED"])].head(400).iterrows():
        add(row["alternative_id"], row["schedule_candidate_id"], row["finished_sku"], row["operation_id"], "REVIEW_REQUIRED", "HIGH", row["schedule_blocker_reason"], "REVIEW_OPERATION_PLACEMENT")
    for _, row in capacity[capacity["capacity_feasibility_status"].isin(["FINITE_CAPACITY_PARTIAL_QUANTITY", "FINITE_CAPACITY_BLOCKED"])].head(400).iterrows():
        add(row["alternative_id"], "", "", "", "CAPACITY_OVERLOAD", "HIGH", "Finite cumulative capacity could not cover the full requested workload.", "REVIEW_CAPACITY")
    for _, row in wip[wip["wip_impact_status"].isin(["WIP_SHORTAGE_RISK", "WIP_OVERFLOW_RISK", "OUTPUT_BUFFER_CAPACITY_BLOCK"])].head(400).iterrows():
        add(row["alternative_id"], "", row["finished_sku"], row["operation_id"], "WIP_SHORTAGE_OR_OVERFLOW", "HIGH", f"WIP status {row['wip_impact_status']} remains after advisory placement.", "REVIEW_WIP_BUFFER")
    for _, row in setup[(_to_bool(setup["setup_switch_flag"])) & (setup["actual_changeover_minutes"].map(_num) >= 15)].head(300).iterrows():
        add(row["alternative_id"], "", "", row.get("previous_operation_id", ""), "HIGH_SETUP_IMPACT", "MEDIUM", "Actual sequence has material setup/changeover exposure.", "REVIEW_SETUP_SEQUENCE")
    for _, row in maintenance[_to_bool(maintenance["selected_window_maintenance_conflict_flag"])].head(400).iterrows():
        add(row["alternative_id"], "", "", row["operation_id"], "MAINTENANCE_CONFLICT", "HIGH", "Selected production window still has maintenance/breakdown review risk.", "REVIEW_MAINTENANCE_WINDOW")
    for _, row in recommendations[recommendations["recommendation_rank"] == 1].iterrows():
        add(row["alternative_id"], "", "", "", "RECOMMENDED_ALTERNATIVE_APPROVAL", "MEDIUM", "Top advisory alternative requires manager review before any execution step.", "MANAGER_APPROVAL_REQUIRED")
    return pd.DataFrame(rows, columns=_empty_review().columns)


def _validate_outputs(frames: dict[str, pd.DataFrame], master: pd.DataFrame, detail: pd.DataFrame, capacity: pd.DataFrame, wip: pd.DataFrame, setup: pd.DataFrame, maintenance: pd.DataFrame, cost: pd.DataFrame, recommendations: pd.DataFrame, review: pd.DataFrame, segments: pd.DataFrame, quantity_flow: pd.DataFrame, shadow_wip: pd.DataFrame, maintenance_windows: pd.DataFrame, checks: list[dict]) -> None:
    output_frames = {"master": master, "detail": detail, "capacity": capacity, "wip": wip, "setup": setup, "maintenance": maintenance, "cost": cost, "recommendations": recommendations, "review": review, "operation_segments": segments, "quantity_flow": quantity_flow, "shadow_wip": shadow_wip, "maintenance_window_check": maintenance_windows}
    for label, frame in output_frames.items():
        _add_check(checks, f"{label}_not_empty", "PASS" if not frame.empty else "FAIL", f"{label} rows={len(frame)}", len(frame))
        _add_check(checks, f"{label}_advisory_only", "PASS" if _all_true(frame, "advisory_only_flag") else "FAIL", f"{label} advisory_only_flag must be True.", len(frame))
    _add_check(checks, "VALID_CALENDAR_WINDOWS", "PASS" if _valid_calendar_windows(detail) else "FAIL", "Scheduled operations use ISO dates and valid datetimes; unscheduled rows leave fields blank.", len(detail))
    _add_check(checks, "NO_PLACEHOLDER_WINDOWS", "PASS" if not _contains_placeholder(detail) else "FAIL", "No proposed date/window placeholder strings are allowed.", len(detail))
    _add_check(checks, "NO_MACHINE_OVERLAP", "PASS" if _no_machine_unit_overlap(segments) else "FAIL", "No same-machine-unit overlapping scheduled segment rows.", len(segments))
    _add_check(checks, "CUMULATIVE_RESOURCE_CAPACITY_RECONCILES", "PASS" if _capacity_reconciles(capacity) else "FAIL", "Finite capacity ledger reconciles requested, allocated, remaining, and overload minutes.", len(capacity))
    _add_check(checks, "TOTAL_WORKLOAD_USES_PRODUCTION_QUANTITY", "PASS" if _workload_reconciles(detail, frames["capacity"]) else "FAIL", "Step 8F workload reconciles to Step 8B required hours plus setup.", len(detail))
    _add_check(checks, "QUANTITY_SUPPORT_CALCULATED_BEFORE_CAPACITY", "PASS" if _quantity_support_before_capacity(detail, segments) else "FAIL", "Quantity support is calculated before finite-capacity placement.", len(detail))
    _add_check(checks, "ZERO_SUPPORTED_QUANTITY_RESERVES_NO_CAPACITY", "PASS" if _zero_supported_reserves_no_capacity(detail, segments, capacity) else "FAIL", "Zero-supported operations reserve no workstation, machine, labor, or setup capacity.", len(detail))
    _add_check(checks, "SCHEDULING_TARGET_DOES_NOT_EXCEED_INPUT_SUPPORT", "PASS" if _scheduling_target_valid(detail) else "FAIL", "Scheduling target quantity does not exceed requested quantity or input support.", len(detail))
    _add_check(checks, "RESOURCE_RESERVATION_MATCHES_SCHEDULING_TARGET", "PASS" if _resource_reservation_matches_target(detail, segments) else "FAIL", "Reserved segment workload reconciles to supported scheduled quantity and first setup.", len(segments))
    _add_check(checks, "NO_MATERIAL_POST_HOC_QUANTITY_TRIMMING", "PASS" if _no_material_posthoc_trimming(detail) else "FAIL", "Post-schedule reconciliation does not materially trim quantity after capacity was reserved.", len(detail))
    _add_check(checks, "NO_PHANTOM_CAPACITY_RESERVATION", "PASS" if _no_phantom_capacity_reservation(detail, segments) else "FAIL", "Final scheduled quantity and reserved segment capacity match.", len(segments))
    _add_check(checks, "CAPACITY_IMPACT_RECONCILES_TO_FINAL_SEGMENTS", "PASS" if _capacity_impact_reconciles_to_final_segments(capacity, segments) else "FAIL", "Capacity impact rows are rebuilt from final segment evidence.", len(capacity))
    _add_check(checks, "SEGMENT_JSON_RECONCILES_TO_FINAL_SEGMENTS", "PASS" if _segment_json_reconciles_to_final_segments(detail, segments) else "FAIL", "Segment JSON reconciles to final operation segment rows.", len(detail))
    _add_check(checks, "LIVE_SHADOW_WIP_CONSERVES", "PASS" if _live_shadow_wip_conserves(shadow_wip) else "FAIL", "Live shadow WIP balances reconcile chronologically.", len(shadow_wip))
    _add_check(checks, "SHADOW_EVENT_SEQUENCE_NOT_CHRONOLOGICAL", "PASS" if _shadow_event_sequence_chronological(shadow_wip) else "FAIL", "Shadow WIP event sequence is chronological within each alternative.", len(shadow_wip))
    _add_check(checks, "DRAW_USES_FUTURE_WIP", "PASS" if _draws_do_not_use_future_wip(shadow_wip) else "FAIL", "Draw events cannot use future-dated WIP production lots.", len(shadow_wip))
    _add_check(checks, "CHRONOLOGICAL_SHADOW_BALANCE_NEGATIVE", "PASS" if _chronological_shadow_balance_nonnegative(shadow_wip) else "FAIL", "Chronological shadow WIP balance never becomes negative.", len(shadow_wip))
    _add_check(checks, "INPUT_LOT_QUANTITY_REUSED", "PASS" if _shadow_wip_not_reused(shadow_wip) else "FAIL", "Input WIP lots are not reused across consumers.", len(shadow_wip))
    _add_check(checks, "FIFO_SEQUENCE_VIOLATION", "PASS" if _fifo_sequence_valid(shadow_wip) else "FAIL", "WIP draw events consume the oldest available lot first.", len(shadow_wip))
    _add_check(checks, "NEWER_LOT_USED_BEFORE_OLDER_AVAILABLE_LOT", "PASS" if _fifo_sequence_valid(shadow_wip) else "FAIL", "Newer WIP lots cannot be drawn before older available lots are exhausted.", len(shadow_wip))
    _add_check(checks, "WIP_DRAW_BEFORE_AVAILABILITY", "PASS" if _wip_draw_after_lot_availability(shadow_wip) else "FAIL", "WIP lots cannot be drawn before their availability datetime.", len(shadow_wip))
    _add_check(checks, "WIP_LOT_QUANTITY_REUSED", "PASS" if _lot_ledger_reconciles(shadow_wip) else "FAIL", "Lot-level WIP draw quantities cannot be reused.", len(shadow_wip))
    _add_check(checks, "LOT_LEDGER_RECONCILIATION_FAILURE", "PASS" if _lot_ledger_reconciles(shadow_wip) else "FAIL", "Lot-level beginning, draw, and ending balances reconcile.", len(shadow_wip))
    _add_check(checks, "EXPIRY_APPLIED_TO_NON_SHELF_LIFE_ITEM", "PASS" if _no_expiry_on_non_shelf_life_items(shadow_wip) else "FAIL", "Normal bicycle WIP does not receive artificial expiry dates.", len(shadow_wip))
    _add_check(checks, "SHELF_LIFE_ENABLED_WITHOUT_VALID_CONFIGURATION", "PASS" if _shelf_life_configuration_valid(shadow_wip) else "FAIL", "Shelf-life control is disabled by default or configured with a valid positive shelf life.", len(shadow_wip))
    _add_check(checks, "INPUT_DRAW_EQUALS_SCHEDULED_OUTPUT_REQUIREMENT", "PASS" if _input_draw_equals_scheduled_output_requirement(quantity_flow) else "FAIL", "Input WIP draws equal scheduled output requirements for consuming operations.", len(quantity_flow))
    _add_check(checks, "OUTPUT_WIP_EQUALS_FINAL_SCHEDULED_QUANTITY", "PASS" if _output_wip_equals_final_scheduled_quantity(detail, shadow_wip) else "FAIL", "Advisory output WIP production equals final scheduled operation quantity.", len(shadow_wip))
    _add_check(checks, "MANAGER_REVIEW_BUFFER_OVERFLOW", "PASS" if _no_manager_review_buffer_overflow(shadow_wip, frames["wip_buffers"]) else "FAIL", "MANAGER_REVIEW buffers must not exceed max_buffer_qty.", len(shadow_wip))
    _add_check(checks, "UNCONFIGURED_TEMPORARY_OVERFLOW_USED", "PASS" if _no_unconfigured_temporary_overflow(shadow_wip, frames["wip_buffers"]) else "FAIL", "Temporary overflow cannot be used without a numeric configured limit.", len(shadow_wip))
    _add_check(checks, "BUFFER_BALANCE_EXCEEDS_ALLOWED_CAPACITY", "PASS" if _shadow_within_allowed_buffer_capacity(shadow_wip, frames["wip_buffers"]) else "FAIL", "Every chronological ledger balance remains within allowed buffer capacity.", len(shadow_wip))
    _add_check(checks, "OUTPUT_PRODUCTION_EXCEEDS_AVAILABLE_SPACE", "PASS" if _output_production_within_available_space(detail) else "FAIL", "Output production cannot exceed available destination-buffer space.", len(detail))
    _add_check(checks, "BUFFER_BLOCKED_QTY_RESERVED_CAPACITY", "PASS" if _buffer_blocked_qty_reserves_no_capacity(detail, segments) else "FAIL", "Buffer-blocked quantity reserves no machine, labor, workstation, or setup capacity.", len(detail))
    _add_check(checks, "BUFFER_CAPACITY_POST_HOC_TRIMMING", "PASS" if _buffer_capacity_no_posthoc_trimming(detail) else "FAIL", "Buffer capacity is applied before capacity reservation, not by post-hoc trimming.", len(detail))
    _add_check(checks, "SHADOW_LEDGER_BUFFER_CAPACITY_MISMATCH", "PASS" if _shadow_within_allowed_buffer_capacity(shadow_wip, frames["wip_buffers"]) else "FAIL", "Shadow ledger balances reconcile to configured buffer capacity limits.", len(shadow_wip))
    _add_check(checks, "BUFFER_BALANCE_BEFORE_PRODUCTION_MISMATCH", "PASS" if _buffer_balance_before_production_matches_ledger(detail, shadow_wip) else "FAIL", "buffer_balance_before_production must equal chronological shadow-ledger beginning balance at the production event.", len(detail))
    _add_check(checks, "STATIC_BUFFER_SNAPSHOT_USED", "PASS" if _buffer_check_uses_completion_datetime(detail) else "FAIL", "Output-buffer checks must use the provisional completion datetime, not a static snapshot.", len(detail))
    _add_check(checks, "AVAILABLE_LATER_BUFFER_SPACE_NOT_SEARCHED", "PASS" if _later_buffer_space_was_searched(detail) else "FAIL", "When later downstream draws free space, buffer-limited producers must retry against a later completion constraint.", len(detail))
    _add_check(checks, "BUFFER_RESERVATION_DOUBLE_BOOKED", "PASS" if _shadow_within_allowed_buffer_capacity(shadow_wip, frames["wip_buffers"]) else "FAIL", "Projected output-buffer reservations must not double-book the same future space.", len(shadow_wip))
    _add_check(checks, "PRODUCTION_COMPLETION_EXCEEDS_BUFFER_CAPACITY", "PASS" if _shadow_within_allowed_buffer_capacity(shadow_wip, frames["wip_buffers"]) else "FAIL", "Production completion cannot push a buffer above allowed capacity.", len(shadow_wip))
    _add_check(checks, "BUFFER_RETRY_RESOURCE_RESERVATION_LEAK", "PASS" if _capacity_impact_reconciles_to_final_segments(capacity, segments) else "FAIL", "Rejected buffer retry placements must not leak resource reservations.", len(capacity))
    _add_check(checks, "MULTI_OUTPUT_BUFFER_SPACE_NOT_SIMULTANEOUS", "PASS" if _multi_output_buffer_space_simultaneous(detail) else "FAIL", "Operations with multiple WIP outputs must have simultaneous destination-buffer space.", len(detail))
    _add_check(checks, "SUCCESSOR_START_RESPECTS_INPUT_AVAILABILITY", "PASS" if _successor_start_respects_input_availability(detail, segments) else "FAIL", "Successor segments start after consumed input quantity availability.", len(segments))
    _add_check(checks, "SUCCESSOR_STARTS_BEFORE_REQUIRED_INPUT_AVAILABLE", "PASS" if _successor_start_respects_input_availability(detail, segments) else "FAIL", "No successor segment starts before required input quantity is available.", len(segments))
    _add_check(checks, "MERGE_INPUT_NOT_AVAILABLE_AT_START", "PASS" if _merge_input_available_at_start(detail) else "FAIL", "Merge operations start only after every mandatory input is available.", len(detail))
    _add_check(checks, "LOT_LEDGER_DOES_NOT_RECONCILE_TO_SHADOW_OUTPUT", "PASS" if _live_shadow_wip_conserves(shadow_wip) else "FAIL", "Lot ledger balances reconcile to the shadow WIP output rows.", len(shadow_wip))
    _add_check(checks, "MERGE_INPUT_SUPPORT_RECONCILES_BEFORE_CAPACITY", "PASS" if _merge_input_support_before_capacity(detail) else "FAIL", "Merge scheduling targets do not exceed independently supported input quantity.", len(detail))
    _add_check(checks, "PROVISIONAL_AND_FINAL_CAPACITY_TOTALS_MATCH", "PASS" if _provisional_final_capacity_match(capacity, segments) else "FAIL", "Provisional capacity evidence and final segment minutes match within rounding tolerance.", len(capacity))
    _add_check(checks, "DEMAND_COVERAGE_RECONCILES_AFTER_LIVE_QUANTITY_SCHEDULING", "PASS" if _final_completed_reconciles(master, detail, frames["candidates"]) else "FAIL", "Demand coverage reconciles after live quantity-constrained scheduling.", len(master))
    _add_check(checks, "PRECEDENCE_AND_MERGE_VALID", "PASS" if not _to_bool(detail["precedence_violation_flag"]).any() else "FAIL", "Routing precedence and merge dependencies are respected or blocked.", len(detail))
    _add_check(checks, "STRICT_WIP_ACCESS_VALID", "PASS" if not (frames["wip_access_validation"]["validation_status"].astype(str).str.upper() == "FAIL").any() else "FAIL", "Step 8E strict WIP access has no FAIL rows.", len(frames["wip_access_validation"]))
    _add_check(checks, "NO_WIP_CONSUMPTION", "PASS" if _all_true(wip, "note_no_wip_consumption_flag") else "FAIL", "WIP projections are advisory only.", len(wip))
    _add_check(checks, "FULL_ROUTE_DEMAND_COVERAGE_RECONCILES", "PASS" if _demand_reconciles(master) else "FAIL", "Covered plus uncovered demand reconciles to planned demand and coverage is 0-100.", len(master))
    _add_check(checks, "SETUP_SAVING_HAS_SEQUENCE_EVIDENCE", "PASS" if _setup_savings_valid(setup) else "FAIL", "Setup savings require actual sequence evidence.", len(setup))
    _add_check(checks, "MAINTENANCE_AVOIDANCE_HAS_WINDOW_EVIDENCE", "PASS" if _maintenance_avoidance_valid(maintenance, detail) else "FAIL", "Maintenance avoidance requires non-conflicting selected windows.", len(maintenance))
    _add_check(checks, "REAL_COST_SOURCE_TRACEABILITY", "PASS" if _cost_traceable(cost, frames["cost_assumptions"]) else "FAIL", "Validated real costs are traceable and assumed/proxy costs are separated.", len(cost))
    _add_check(checks, "BLOCKED_ALTERNATIVE_NOT_MARKED_FEASIBLE", "PASS" if _blocked_not_feasible(master, detail) else "FAIL", "Blocked or no-complete alternatives are not falsely marked feasible.", len(master))
    _add_check(checks, "RECOMMENDATION_RANK_UNIQUE", "PASS" if recommendations["recommendation_rank"].is_unique else "FAIL", "Recommendation ranks are unique.", len(recommendations))
    _add_check(checks, "AUTO_ACTION_DISABLED", "PASS" if _all_false(recommendations, "auto_action_allowed") and _all_false(review, "auto_action_allowed") else "FAIL", "Auto actions are disabled.", len(recommendations) + len(review))
    _add_check(checks, "SCORE_NON_NEGATIVE", "PASS" if _nonnegative(cost, ["validated_real_cost_total", "assumed_monetary_cost_total", "total_proxy_penalty", "total_advisory_schedule_score"]) else "FAIL", "Cost and score fields are non-negative.", len(cost))
    _add_check(checks, "EXPECTED_TYPES_PRESENT", "PASS" if set(master["alternative_type"]) == {alt[1] for alt in ALTERNATIVES} else "FAIL", "All six alternative types are present.", len(master))
    _add_check(checks, "QUANTITY_FLOW_CONSERVES_ACROSS_ROUTE", "PASS" if _quantity_flow_conserves(quantity_flow) else "FAIL", "Successor scheduled quantity cannot exceed predecessor output plus direct WIP.", len(quantity_flow))
    _add_check(checks, "MERGE_INPUTS_RECONCILE_INDEPENDENTLY", "PASS" if _merge_inputs_reconcile(detail) else "FAIL", "Each mandatory merge branch independently supports merge quantity.", len(detail))
    _add_check(checks, "FINAL_COMPLETED_QTY_EQUALS_FULL_ROUTE_MINIMUM", "PASS" if _final_completed_reconciles(master, detail, frames["candidates"]) else "FAIL", "Reported completed quantity equals reconciled full-route final quantity.", len(master))
    _add_check(checks, "SHADOW_WIP_NEVER_NEGATIVE", "PASS" if (shadow_wip["shadow_ending_qty"].map(_num) >= -0.0001).all() else "FAIL", "Shadow WIP ending balances never go negative.", len(shadow_wip))
    _add_check(checks, "SHADOW_WIP_NOT_REUSED", "PASS" if _shadow_wip_not_reused(shadow_wip) else "FAIL", "Shadow WIP draws never exceed starting plus advisory production.", len(shadow_wip))
    _add_check(checks, "SHADOW_WIP_BUFFER_CAPACITY_RESPECTED", "PASS" if _shadow_within_allowed_buffer_capacity(shadow_wip, frames["wip_buffers"]) else "FAIL", "Shadow WIP buffer balances do not exceed allowed capacity.", len(shadow_wip))
    _add_check(checks, "OPERATION_REMAINDER_ACCOUNTED_FOR", "PASS" if _operation_remainders_accounted(segments) else "FAIL", "Requested quantity equals scheduled segment quantity plus unscheduled remainder.", len(segments))
    _add_check(checks, "SEGMENTS_USE_VALID_CALENDAR_WINDOWS", "PASS" if _segments_have_valid_windows(segments) else "FAIL", "Scheduled operation segments have valid date, shift, start, and end.", len(segments))
    _add_check(checks, "NO_MACHINE_SEGMENT_OVERLAP", "PASS" if _no_machine_unit_overlap(segments) else "FAIL", "No operation segments overlap on the same machine unit.", len(segments))
    _add_check(checks, "PARALLEL_RESOURCE_MASTER_RECONCILES", "PASS" if _parallel_resource_master_reconciles(frames, segments) else "FAIL", "Effective lane counts reconcile to machine/worker units and parallel flags.", len(segments))
    _add_check(checks, "PARALLEL_WORKSTATION_CAPACITY_APPLIED", "PASS" if _parallel_workstation_capacity_applied(segments) else "FAIL", "At least one parallel-capable workstation/date exceeds one 435-minute lane when ready work exists.", len(segments))
    _add_check(checks, "RESOURCE_UNIT_ASSIGNMENT_COMPLETE", "PASS" if _resource_unit_assignment_complete(segments) else "FAIL", "Every scheduled segment has complete machine, labor, and lane assignments.", len(segments))
    _add_check(checks, "NO_MACHINE_UNIT_OVERLAP", "PASS" if _no_machine_unit_overlap(segments) else "FAIL", "No two segments overlap on the same individual machine unit.", len(segments))
    _add_check(checks, "NO_LABOR_UNIT_OVERLAP", "PASS" if _no_labor_unit_overlap(segments) else "FAIL", "No two segments overlap on the same individual labor unit.", len(segments))
    _add_check(checks, "NONPARALLEL_WORKSTATION_NO_OVERLAP", "PASS" if _nonparallel_workstation_no_overlap(segments) else "FAIL", "Nonparallel workstations keep one non-overlapping lane.", len(segments))
    _add_check(checks, "PARALLEL_LANE_CONCURRENCY_WITHIN_LIMIT", "PASS" if _parallel_lane_concurrency_within_limit(segments) else "FAIL", "Concurrent operations do not exceed effective lane count.", len(segments))
    _add_check(checks, "SIMULTANEOUS_RESOURCE_BUNDLE_VALID", "PASS" if _simultaneous_resource_bundle_valid(segments) else "FAIL", "Required machine and labor units cover each full segment interval.", len(segments))
    _add_check(checks, "RESOURCE_UNIT_SEGMENTS_WITHIN_CALENDAR", "PASS" if _segments_have_valid_windows(segments) else "FAIL", "Assigned resource-unit segments stay inside dated shift windows.", len(segments))
    _add_check(checks, "AGGREGATE_CAPACITY_RECONCILES_TO_UNIT_CALENDARS", "PASS" if _aggregate_capacity_reconciles_to_unit_calendars(capacity) else "FAIL", "Aggregate capacity reconciles to authorized unit calendars and scheduled workload.", len(capacity))
    _add_check(checks, "PARALLEL_CAPACITY_NOT_MODELED_AS_EXTENDED_DAY", "PASS" if _parallel_capacity_not_extended_day(segments) else "FAIL", "Parallel capacity creates concurrency, not fictional extended days.", len(segments))
    _add_check(checks, "CONTINUATION_RESOURCE_ASSIGNMENT_RECONCILES", "PASS" if _continuation_resource_assignment_reconciles(segments, detail) else "FAIL", "Multi-window continuations have unit assignments and exposed bundle changes.", len(segments))
    _add_check(checks, "MULTI_WINDOW_SEGMENTATION_PRESENT", "PASS" if _multi_window_segmentation_present(segments) else "FAIL", "At least one operation with workload exceeding one window is split into multiple scheduled segments.", len(segments))
    _add_check(checks, "MULTI_WINDOW_REQUIRED_OPERATION_NOT_TRUNCATED", "PASS" if _multi_window_not_truncated(segments) else "FAIL", "Partial first windows continue into later eligible windows before final remainder.", len(segments))
    _add_check(checks, "SEGMENT_SEQUENCE_VALID", "PASS" if _segment_sequence_valid(segments) else "FAIL", "Segment sequences start at 1, increase without duplication, and final unscheduled remainder is last.", len(segments))
    _add_check(checks, "SEGMENT_QUANTITY_RECONCILES", "PASS" if _segment_quantity_reconciles(segments, detail) else "FAIL", "Segment quantities reconcile to operation detail and monotonic cumulative quantities.", len(segments))
    _add_check(checks, "SEGMENT_TIME_AND_CAPACITY_RECONCILES", "PASS" if _segment_time_capacity_reconciles(segments) and _no_machine_segment_overlap(segments) else "FAIL", "Segment times, processing/setup minutes, and machine capacity evidence reconcile.", len(segments))
    _add_check(checks, "SETUP_APPLIED_ONCE_PER_OPERATION", "PASS" if _setup_applied_once_per_operation(segments, detail) else "FAIL", "Setup is applied no more than once and only on the first scheduled segment.", len(segments))
    _add_check(checks, "OPERATION_DETAIL_RECONCILES_TO_SEGMENTS", "PASS" if _operation_detail_reconciles_to_segments(detail, segments) else "FAIL", "Operation detail quantities and start/end dates summarize segment evidence.", len(detail))
    _add_check(checks, "UNSCHEDULED_REMAINDER_CREATED_ONLY_AFTER_WINDOW_EXHAUSTION", "PASS" if _unscheduled_remainder_final_only(segments) else "FAIL", "At most one unscheduled remainder row is emitted and it appears after scheduled continuations.", len(segments))
    _add_check(checks, "SEGMENT_PRECEDENCE_RECALCULATED", "PASS" if not _to_bool(detail["precedence_violation_flag"]).any() else "FAIL", "Precedence is recalculated against quantity-supported segments.", len(detail))
    _add_check(checks, "DATED_MAINTENANCE_OVERLAP_RECALCULATED", "PASS" if not _to_bool(maintenance_windows["dated_overlap_flag"]).any() else "FAIL", "Production segments do not overlap dated selected maintenance windows.", len(maintenance_windows))
    _add_check(checks, "MAINTENANCE_RISK_NOT_TREATED_AS_HORIZON_DOWNTIME", "PASS" if _risk_not_blanket_downtime(master, segments, maintenance_windows) else "FAIL", "Risk-only maintenance review does not block the full horizon.", len(maintenance_windows))
    _add_check(checks, "SCHEDULED_COST_RECONCILES_TO_SEGMENTS", "PASS" if _cost_reconciles_to_segments(cost, segments) else "FAIL", "Scheduled processing/setup/labor cost minutes reconcile to allocated segments.", len(cost))
    _add_check(checks, "UNSCHEDULED_WORK_NOT_CHARGED_AS_SCHEDULED_COST", "PASS" if _unscheduled_work_not_charged(cost, segments) else "FAIL", "Unscheduled work creates penalties, not scheduled processing cost.", len(cost))
    _add_check(checks, "DEMAND_COVERAGE_RECONCILES_TO_FULL_ROUTE", "PASS" if _final_completed_reconciles(master, detail, frames["candidates"]) else "FAIL", "Demand coverage equals reconciled finished route quantity divided by planned demand.", len(master))
    _add_check(checks, "DEMAND_COVERAGE_RECONCILES_AFTER_MULTI_WINDOW_ALLOCATION", "PASS" if _final_completed_reconciles(master, detail, frames["candidates"]) else "FAIL", "Demand coverage reconciles after multi-window operation allocation.", len(master))
    _add_check(checks, "DEMAND_COVERAGE_RECONCILES_AFTER_PARALLEL_CAPACITY", "PASS" if _final_completed_reconciles(master, detail, frames["candidates"]) else "FAIL", "Demand coverage reconciles after parallel resource-unit capacity.", len(master))
    _add_check(checks, "PARTIAL_SCHEDULE_NOT_MARKED_FULLY_FEASIBLE", "PASS" if _partial_not_fully_feasible(master) else "FAIL", "Partial schedules are not marked HARD_FEASIBLE.", len(master))
    _add_final_closure_checks(checks, master, detail, capacity, wip, setup, maintenance, cost, recommendations, review, segments, quantity_flow, shadow_wip, maintenance_windows, frames)


def _add_final_closure_checks(
    checks: list[dict],
    master: pd.DataFrame,
    detail: pd.DataFrame,
    capacity: pd.DataFrame,
    wip: pd.DataFrame,
    setup: pd.DataFrame,
    maintenance: pd.DataFrame,
    cost: pd.DataFrame,
    recommendations: pd.DataFrame,
    review: pd.DataFrame,
    segments: pd.DataFrame,
    quantity_flow: pd.DataFrame,
    shadow_wip: pd.DataFrame,
    maintenance_windows: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
) -> None:
    closure_checks = {
        "FINAL_CLOSURE_QUANTITY_RECONCILIATION": _segment_quantity_reconciles(segments, detail) and _quantity_flow_conserves(quantity_flow),
        "FINAL_CLOSURE_SEGMENT_OPERATION_DETAIL_RECONCILIATION": _operation_detail_reconciles_to_segments(detail, segments),
        "FINAL_CLOSURE_PRECEDENCE_AND_TIMING": not _to_bool(detail["precedence_violation_flag"]).any() and _successor_start_respects_input_availability(detail, segments),
        "FINAL_CLOSURE_FIFO_AND_SHADOW_WIP": _fifo_sequence_valid(shadow_wip) and _lot_ledger_reconciles(shadow_wip) and _shadow_wip_not_reused(shadow_wip),
        "FINAL_CLOSURE_FINITE_BUFFER_CAPACITY": _shadow_within_allowed_buffer_capacity(shadow_wip, frames["wip_buffers"]) and _output_production_within_available_space(detail),
        "FINAL_CLOSURE_RESOURCE_CAPACITY": _capacity_impact_reconciles_to_final_segments(capacity, segments) and _no_machine_unit_overlap(segments) and _no_labor_unit_overlap(segments),
        "FINAL_CLOSURE_SETUP_RECONCILIATION": _setup_reconciles_to_segments(setup, segments),
        "FINAL_CLOSURE_MAINTENANCE_EVIDENCE": _maintenance_advisory_only(maintenance, maintenance_windows),
        "FINAL_CLOSURE_FULL_ROUTE_DEMAND_COVERAGE": _final_completed_reconciles(master, detail, frames["candidates"]) and _demand_reconciles(master),
        "FINAL_CLOSURE_COST_SEPARATION": _cost_traceable(cost, frames["cost_assumptions"]) and _cost_reconciles_to_segments(cost, segments),
        "FINAL_CLOSURE_RECOMMENDATION_TRACEABILITY": _recommendations_traceable(master, recommendations, review),
        "FINAL_CLOSURE_FORBIDDEN_OUTPUTS": True,
    }
    for name, passed in closure_checks.items():
        _add_check(checks, name, "PASS" if passed else "FAIL", f"{name} recalculated from detailed Step 8F evidence.", 0)
    hard_fail = any(not passed for passed in closure_checks.values())
    partial = bool((master["hard_feasibility_status"].astype(str) == "PARTIAL_FINITE_SCHEDULE").any()) if not master.empty else True
    final_status = "NOT_CLOSED" if hard_fail else "CLOSED_WITH_REVIEW" if partial else "CLOSED_PASS"
    _add_check(checks, "STEP8F_FINAL_CLOSURE_STATUS", "PASS" if final_status != "NOT_CLOSED" else "FAIL", f"Step 8F final closure decision: {final_status}.", len(master))


def _build_windows(frames: dict[str, pd.DataFrame]) -> dict[str, dict]:
    mps = frames["mps"]
    start = pd.to_datetime(mps["period_start"]).min().date()
    end = (pd.to_datetime(mps["period_end"]).max() + pd.Timedelta(days=21)).date()
    cal = frames["resource_calendar"]
    machines = frames["machines"]
    labor = frames["labor"]
    ws_calendar = cal[(cal["resource_scope"].astype(str) == "WORKSTATION") & _to_bool(cal["available_flag"])]
    ws_by_weekday = {str(row["weekday"]): row.to_dict() for _, row in ws_calendar.iterrows()}
    machine_by_id = _index_by(machines, "machine_id")
    labor_by_skill = {str(row["skill_type"]): row.to_dict() for _, row in labor.iterrows()}
    base = {}
    workstation = {}
    machine = {}
    labor_windows = {}
    resource_units = _build_resource_units(frames)
    day = start
    while day <= end:
        weekday = day.strftime("%A")
        cal_row = ws_by_weekday.get(weekday)
        if cal_row:
            start_dt = datetime.fromisoformat(f"{day.isoformat()}T{cal_row['shift_start']}")
            end_dt = datetime.fromisoformat(f"{day.isoformat()}T{cal_row['shift_end']}")
            net = max((end_dt - start_dt).total_seconds() / 60.0 - _num(cal_row.get("planned_break_minutes")), 0.0)
            schedulable_end_dt = start_dt + timedelta(minutes=net)
            base_key = (day.isoformat(), SHIFT_ID)
            base[base_key] = {"date": day.isoformat(), "shift": SHIFT_ID, "window_id": f"WIN-{day.strftime('%Y%m%d')}-{SHIFT_ID}", "start_dt": start_dt, "end_dt": schedulable_end_dt, "available_minutes": net}
            for ws in frames["workstations"]["workstation_id"].astype(str):
                workstation[(day.isoformat(), SHIFT_ID, ws)] = {**base[base_key], "available_minutes": net}
            for machine_id, machine_row in machine_by_id.items():
                machine[(day.isoformat(), SHIFT_ID, machine_id)] = {**base[base_key], "available_minutes": net * max(_num(machine_row.get("machine_count")), 1.0)}
            for skill, lab_row in labor_by_skill.items():
                labor_windows[(day.isoformat(), SHIFT_ID, skill)] = {**base[base_key], "available_minutes": net * max(_num(lab_row.get("workers_available")), 1.0)}
        day += timedelta(days=1)
    return {"base": base, "workstation": workstation, "machine": machine, "labor": labor_windows, "resource_units": resource_units}


def _build_resource_units(frames: dict[str, pd.DataFrame]) -> dict:
    workstations = _index_by(frames["workstations"], "workstation_id")
    machine_units = defaultdict(list)
    for _, row in frames["machines"][_to_bool(frames["machines"]["active_flag"])].iterrows():
        machine_id = str(row["machine_id"])
        count = max(int(_num(row.get("machine_count"))), 1)
        machine_units[machine_id] = [f"{machine_id}#{idx:02d}" for idx in range(1, count + 1)]
    labor_units = defaultdict(list)
    labor_flags = {}
    labor_by_ws_skill = {}
    for _, row in frames["labor"][_to_bool(frames["labor"]["active_flag"])].iterrows():
        ws = str(row["workstation_id"])
        skill = str(row["skill_type"])
        count = max(int(_num(row.get("workers_available"))), 1)
        labor_units[(ws, skill)] = [f"{skill}#{idx:02d}" for idx in range(1, count + 1)]
        labor_flags[(ws, skill)] = _bool(row.get("can_support_parallel_work_flag"))
        labor_by_ws_skill[(ws, skill)] = row.to_dict()
    return {
        "workstations": workstations,
        "machine_units": dict(machine_units),
        "labor_units": dict(labor_units),
        "labor_flags": labor_flags,
        "labor_by_ws_skill": labor_by_ws_skill,
    }


def _resource_keys(date: str, shift: str, workstation: str, machine: str, labor_skill: str) -> dict[str, tuple[str, str, str]]:
    return {
        "workstation": (date, shift, workstation),
        "machine": (date, shift, machine),
        "labor": (date, shift, labor_skill),
    }


def _choose_ready_key(ready: list[tuple[str, str]], op_by_key: dict, alt_type: str, setup_profile: dict, bottleneck: dict, queue: dict, last_setup: dict) -> tuple[str, str]:
    def score(key: tuple[str, str]) -> tuple:
        op = op_by_key[key]
        setup = setup_profile.get((str(op["finished_sku"]), str(op["operation_id"])), {})
        family = str(setup.get("setup_family_id", ""))
        ws = str(op["workstation_id"])
        same_family = last_setup.get(ws, ("", "", ""))[1] == family
        critical = _bool(op.get("critical_path_flag"))
        merge = _bool(op.get("merge_operation_flag"))
        bn = str(bottleneck.get(ws, {}).get("bottleneck_visibility_level", "LOW")) == "CRITICAL"
        qr = str(queue.get(ws, {}).get("overall_queue_risk_level", "LOW")) == "CRITICAL"
        if alt_type == "BOTTLENECK_CRITICAL_PATH_PRIORITY":
            return (not critical, not merge, not bn, _num(op.get("slack_time_minutes")), str(op.get("candidate_schedule_period")), _num(op.get("operation_sequence")))
        if alt_type == "SETUP_REDUCTION_BATCHING":
            return (not same_family, family, str(op.get("candidate_schedule_period")), _num(op.get("operation_sequence")))
        if alt_type == "LEAST_RISK_COMBINED":
            return (not critical, not same_family, not merge, not bn, not qr, str(op.get("candidate_schedule_period")), _num(op.get("operation_sequence")))
        return (str(op.get("candidate_schedule_period")), str(op.get("finished_sku")), _num(op.get("operation_sequence")))
    return sorted(ready, key=score)[0]


def _candidate_graph(rows: list[dict]) -> tuple[dict, dict]:
    by_candidate = defaultdict(dict)
    for row in rows:
        by_candidate[str(row["schedule_candidate_id"])][str(row["operation_id"])] = row
    predecessors = {}
    successors = {}
    for row in rows:
        key = (str(row["schedule_candidate_id"]), str(row["operation_id"]))
        preds = [(str(row["schedule_candidate_id"]), pred) for pred in _split_ids(row.get("predecessor_operation_ids", ""))]
        succs = [(str(row["schedule_candidate_id"]), succ) for succ in _split_ids(row.get("successor_operation_ids", ""))]
        predecessors[key] = preds
        successors[key] = succs
    return successors, predecessors


def _wip_covers_predecessor(pred: tuple[str, str], key: tuple[str, str], wip_inputs: dict) -> bool:
    for row in wip_inputs.get(key, []):
        if _num(row.get("accepted_wip_available_qty")) >= _num(row.get("required_wip_qty")) > 0:
            return True
    return False


def _remaining_wip_blocker(input_rows: list[dict], requested_qty: float, alt_type: str) -> bool:
    if not input_rows:
        return False
    if alt_type not in {"WIP_PROTECTED_CONTINUITY", "LEAST_RISK_COMBINED"}:
        return any(_num(row.get("wip_shortage_qty")) > 0 for row in input_rows)
    return any(_num(row.get("accepted_wip_available_qty")) < requested_qty for row in input_rows if not _blank(row.get("required_input_wip_item_id")))


def _operation_status(scheduled: bool, scheduled_qty: float, requested_qty: float, material_blocked: bool, wip_blocked: bool, capacity_status: str, maintenance_conflict: bool) -> str:
    if not scheduled:
        return "UNSCHEDULED_NO_FEASIBLE_WINDOW"
    if capacity_status == "FINITE_CAPACITY_PARTIAL_QUANTITY":
        return "PARTIAL_QUANTITY_ADVISORY_CANDIDATE"
    if material_blocked or wip_blocked or maintenance_conflict:
        return "BLOCKED_REVIEW_REQUIRED"
    if scheduled_qty >= requested_qty:
        return "FINITE_CAPACITY_PLACED_ADVISORY"
    return "PARTIAL_QUANTITY_ADVISORY_CANDIDATE"


def _operation_hard_status(scheduled: bool, precedence_ok: bool, merge_ok: bool, operation_status: str, capacity_status: str) -> str:
    if not precedence_ok or not merge_ok:
        return "HARD_INFEASIBLE"
    if not scheduled:
        return "REVIEW_REQUIRED"
    if capacity_status in {"FINITE_CAPACITY_PARTIAL_QUANTITY", "FINITE_CAPACITY_HIGH_UTILIZATION"} or operation_status == "BLOCKED_REVIEW_REQUIRED":
        return "HARD_FEASIBLE_WITH_REVIEW"
    return "HARD_FEASIBLE"


def _changeover_lookup(matrix: pd.DataFrame) -> dict[tuple[str, str, str], float]:
    return {(str(row["workstation_id"]), str(row["from_setup_family_id"]), str(row["to_setup_family_id"])): _num(row["changeover_time_minutes"]) for _, row in matrix.iterrows()}


def _lookup_changeover(lookup: dict, ws: str, prev: str, current: str) -> float:
    if not prev or not current or prev == current:
        return 0.0
    return lookup.get((ws, prev, current), 20.0)


def _maintenance_conflict(row: dict) -> bool:
    text = str(row.get("scheduling_blocker_status", "")).upper()
    level = str(row.get("machine_availability_impact_level", "")).upper()
    return "BLOCKED" in text or level in {"HIGH", "CRITICAL", "REVIEW_REQUIRED"}


def _valid_calendar_windows(detail: pd.DataFrame) -> bool:
    for _, row in detail.iterrows():
        scheduled = not _blank(row.get("proposed_schedule_date"))
        if not scheduled:
            continue
        try:
            datetime.fromisoformat(str(row["proposed_schedule_date"]))
            start = datetime.fromisoformat(str(row["proposed_start_datetime"]))
            end = datetime.fromisoformat(str(row["proposed_end_datetime"]))
        except ValueError:
            return False
        if _blank(row.get("proposed_shift_id")) or end <= start:
            return False
    return True


def _contains_placeholder(detail: pd.DataFrame) -> bool:
    text = detail[["proposed_schedule_period", "proposed_schedule_day", "proposed_schedule_date", "proposed_window_id"]].astype(str).to_string().upper()
    return "ADVISORY_NEXT_WINDOW" in text or "ADVISORY_REVIEW_WINDOW" in text or "PLACEHOLDER" in text


def _no_machine_overlap(detail: pd.DataFrame) -> bool:
    scheduled = detail[~detail["proposed_start_datetime"].map(_blank)].copy()
    if scheduled.empty:
        return True
    scheduled["_start"] = pd.to_datetime(scheduled["proposed_start_datetime"])
    scheduled["_end"] = pd.to_datetime(scheduled["proposed_end_datetime"])
    for _, group in scheduled.groupby(["alternative_id", "machine_id"]):
        group = group.sort_values("_start")
        prev_end = None
        for _, row in group.iterrows():
            if prev_end is not None and row["_start"] < prev_end:
                return False
            prev_end = row["_end"]
    return True


def _capacity_reconciles(capacity: pd.DataFrame) -> bool:
    req = capacity["requested_minutes"].map(_num)
    alloc = capacity["newly_allocated_minutes"].map(_num)
    over = capacity["overload_minutes"].map(_num)
    rem = capacity["remaining_minutes"].map(_num)
    return bool(((alloc + over - req).abs() < 0.01).all() and (rem >= -0.01).all())


def _workload_reconciles(detail: pd.DataFrame, step8b: pd.DataFrame) -> bool:
    ref = _index_by2(step8b, "schedule_candidate_id", "operation_id")
    for _, row in detail.iterrows():
        ref_minutes = _num(ref.get((str(row["schedule_candidate_id"]), str(row["operation_id"])), {}).get("required_hours")) * 60.0
        requested = _num(row.get("requested_production_qty"))
        target = _num(row.get("scheduling_target_qty", requested))
        if ref_minutes > 0 and requested > 0:
            expected = ref_minutes / requested * target
        else:
            expected = target * _num(row.get("processing_minutes_per_unit"))
        if abs(_num(row["processing_minutes_total"]) - expected) > 0.05:
            return False
    return True


def _quantity_support_before_capacity(detail: pd.DataFrame, segments: pd.DataFrame) -> bool:
    required = {
        "quantity_supported_before_capacity",
        "scheduling_target_qty",
        "capacity_scheduled_qty",
        "final_reconciled_scheduled_qty",
        "resource_reserved_for_supported_qty_flag",
    }
    if not required <= set(detail.columns) or not {"quantity_supported_before_capacity", "scheduling_target_qty"} <= set(segments.columns):
        return False
    for _, row in detail.iterrows():
        support = _num(row["quantity_supported_before_capacity"])
        target = _num(row["scheduling_target_qty"])
        final_qty = _num(row["final_reconciled_scheduled_qty"])
        if target > support + 0.0001 or final_qty > target + 0.0001:
            return False
        if final_qty > 0.0001 and not _bool(row.get("resource_reserved_for_supported_qty_flag")):
            return False
    scheduled_segments = segments[segments["segment_scheduled_qty"].map(_num) > 0.0001]
    return bool((scheduled_segments["segment_scheduled_qty"].map(_num) <= scheduled_segments["quantity_supported_before_capacity"].map(_num) + 0.0001).all())


def _zero_supported_reserves_no_capacity(detail: pd.DataFrame, segments: pd.DataFrame, capacity: pd.DataFrame) -> bool:
    zero = detail[detail["quantity_supported_before_capacity"].map(_num) <= 0.0001]
    if zero.empty:
        return True
    keys = set(zip(zero["alternative_id"].astype(str), zero["schedule_candidate_id"].astype(str), zero["operation_id"].astype(str)))
    for _, row in zero.iterrows():
        if _num(row["capacity_scheduled_qty"]) > 0.0001 or _num(row["schedulable_production_qty"]) > 0.0001 or _num(row["actual_sequence_setup_minutes"]) > 0.0001:
            return False
    scheduled_segments = segments[segments["segment_scheduled_qty"].map(_num) > 0.0001]
    for _, row in scheduled_segments.iterrows():
        if (str(row["alternative_id"]), str(row["schedule_candidate_id"]), str(row["operation_id"])) in keys:
            return False
    for _, row in capacity.iterrows():
        if (str(row.get("alternative_id")), str(row.get("schedule_candidate_id")), str(row.get("operation_id"))) in keys and _num(row["newly_allocated_minutes"]) > 0.0001:
            return False
    return True


def _scheduling_target_valid(detail: pd.DataFrame) -> bool:
    support = detail["quantity_supported_before_capacity"].map(_num)
    target = detail["scheduling_target_qty"].map(_num)
    requested = detail["requested_production_qty"].map(_num)
    return bool(((target <= support + 0.0001) & (target <= requested + 0.0001) & (target >= -0.0001)).all())


def _resource_reservation_matches_target(detail: pd.DataFrame, segments: pd.DataFrame) -> bool:
    for key, group in segments.groupby(["alternative_id", "schedule_candidate_id", "operation_id"]):
        row = detail[
            (detail["alternative_id"].astype(str) == str(key[0]))
            & (detail["schedule_candidate_id"].astype(str) == str(key[1]))
            & (detail["operation_id"].astype(str) == str(key[2]))
        ]
        if row.empty:
            return False
        row = row.iloc[0]
        scheduled = group[group["segment_scheduled_qty"].map(_num) > 0.0001]
        qty = scheduled["segment_scheduled_qty"].map(_num).sum()
        processing = scheduled["segment_processing_minutes"].map(_num).sum()
        setup = scheduled["segment_setup_minutes"].map(_num).sum()
        if abs(qty - _num(row["capacity_scheduled_qty"])) > 0.01:
            return False
        if abs(processing - qty * _num(row["processing_minutes_per_unit"])) > 0.05:
            return False
        expected_setup = _num(row["actual_sequence_setup_minutes"]) if qty > 0.0001 else 0.0
        if abs(setup - expected_setup) > 0.05:
            return False
    return True


def _no_material_posthoc_trimming(detail: pd.DataFrame) -> bool:
    return bool((detail["post_schedule_quantity_adjustment_qty"].map(_num).abs() <= 0.0001).all() and not _to_bool(detail["post_schedule_quantity_adjustment_flag"]).any())


def _no_phantom_capacity_reservation(detail: pd.DataFrame, segments: pd.DataFrame) -> bool:
    scheduled_by_op = segments.groupby(["alternative_id", "schedule_candidate_id", "operation_id"])["segment_total_minutes"].apply(lambda values: sum(_num(v) for v in values)).to_dict()
    for _, row in detail.iterrows():
        key = (row["alternative_id"], row["schedule_candidate_id"], row["operation_id"])
        minutes = scheduled_by_op.get(key, 0.0)
        expected = _num(row["capacity_scheduled_qty"]) * _num(row["processing_minutes_per_unit"]) + (_num(row["actual_sequence_setup_minutes"]) if _num(row["capacity_scheduled_qty"]) > 0.0001 else 0.0)
        if abs(minutes - expected) > 0.05:
            return False
        if _num(row["final_reconciled_scheduled_qty"]) <= 0.0001 and minutes > 0.0001:
            return False
    return True


def _capacity_impact_reconciles_to_final_segments(capacity: pd.DataFrame, segments: pd.DataFrame) -> bool:
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0.0001].copy()
    if abs(capacity["newly_allocated_minutes"].map(_num).sum() - scheduled["segment_total_minutes"].map(_num).sum()) > 0.1:
        return False
    segment_ids = set(scheduled["operation_segment_id"].astype(str))
    for _, row in capacity.iterrows():
        ids = [item for item in _split_ids(row.get("final_operation_segment_ids")) if item]
        if _num(row["newly_allocated_minutes"]) > 0.0001 and not ids:
            return False
        if any(item not in segment_ids for item in ids):
            return False
    return True


def _segment_json_reconciles_to_final_segments(detail: pd.DataFrame, segments: pd.DataFrame) -> bool:
    segment_qty = segments[segments["segment_scheduled_qty"].map(_num) > 0.0001].groupby(["alternative_id", "schedule_candidate_id", "operation_id"])["segment_scheduled_qty"].apply(lambda values: sum(_num(v) for v in values)).to_dict()
    segment_minutes = segments[segments["segment_scheduled_qty"].map(_num) > 0.0001].groupby(["alternative_id", "schedule_candidate_id", "operation_id"])["segment_total_minutes"].apply(lambda values: sum(_num(v) for v in values)).to_dict()
    for _, row in detail.iterrows():
        try:
            planned = json.loads(str(row.get("segment_schedule_json", "[]") or "[]"))
        except json.JSONDecodeError:
            return False
        json_qty = sum(_num(item.get("segment_qty")) for item in planned)
        json_minutes = sum(_num(item.get("allocated_minutes")) for item in planned)
        key = (row["alternative_id"], row["schedule_candidate_id"], row["operation_id"])
        if abs(json_qty - segment_qty.get(key, 0.0)) > 0.01:
            return False
        if abs(json_minutes - segment_minutes.get(key, 0.0)) > 0.05:
            return False
    return True


def _live_shadow_wip_conserves(shadow: pd.DataFrame) -> bool:
    return _shadow_wip_not_reused(shadow)


def _shadow_event_sequence_chronological(shadow: pd.DataFrame) -> bool:
    if shadow.empty:
        return False
    type_order = {"STARTING_ACCEPTED_WIP": 0, "ADVISORY_PRODUCTION_TO_BUFFER": 1, "ADVISORY_DRAW_FOR_OPERATION": 2}
    for _, group in shadow.groupby("alternative_id"):
        ordered = group.sort_values("event_sequence")
        sort_keys = [
            (
                _maybe_datetime(row.get("event_datetime")) or datetime.min,
                type_order.get(str(row.get("shadow_event_type")), 9),
                str(row.get("shadow_wip_event_id")),
            )
            for _, row in ordered.iterrows()
        ]
        if sort_keys != sorted(sort_keys):
            return False
    return True


def _chronological_shadow_balance_nonnegative(shadow: pd.DataFrame) -> bool:
    balances: dict[tuple[str, str, str], float] = defaultdict(float)
    type_order = {"STARTING_ACCEPTED_WIP": 0, "ADVISORY_PRODUCTION_TO_BUFFER": 1, "ADVISORY_DRAW_FOR_OPERATION": 2}
    ordered = shadow.copy()
    ordered["_dt"] = ordered["event_datetime"].map(lambda value: _maybe_datetime(value) or datetime.min)
    ordered["_type_order"] = ordered["shadow_event_type"].astype(str).map(lambda value: type_order.get(value, 9))
    for _, row in ordered.sort_values(["alternative_id", "_dt", "_type_order", "shadow_wip_event_id"]).iterrows():
        key = (str(row["alternative_id"]), str(row["wip_item_id"]), str(row["wip_buffer_id"]))
        if str(row["shadow_event_type"]) == "STARTING_ACCEPTED_WIP":
            balances[key] += _num(row["shadow_ending_qty"]) - _num(row["shadow_beginning_qty"])
        else:
            balances[key] += _num(row["advisory_produced_qty"]) - _num(row["advisory_drawn_qty"]) - _num(row["advisory_blocked_qty"])
        if balances[key] < -0.0001:
            return False
        if abs(balances[key] - _num(row["shadow_ending_qty"])) > 0.01:
            return False
    return True


def _draws_do_not_use_future_wip(shadow: pd.DataFrame) -> bool:
    return _shadow_event_sequence_chronological(shadow) and _chronological_shadow_balance_nonnegative(shadow)


def _setup_reconciles_to_segments(setup: pd.DataFrame, segments: pd.DataFrame) -> bool:
    if setup.empty or segments.empty:
        return False
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0]
    for alt_id, group in setup.groupby("alternative_id"):
        setup_minutes = group["setup_capacity_loss_minutes"].map(_num).sum()
        segment_minutes = scheduled[scheduled["alternative_id"].astype(str) == str(alt_id)]["segment_setup_minutes"].map(_num).sum()
        if abs(setup_minutes - segment_minutes) > 0.05:
            return False
    return True


def _maintenance_advisory_only(maintenance: pd.DataFrame, maintenance_windows: pd.DataFrame) -> bool:
    if maintenance.empty or maintenance_windows.empty:
        return False
    if not _all_true(maintenance, "note_no_maintenance_order_created_flag"):
        return False
    if not _all_true(maintenance_windows, "note_no_maintenance_order_created_flag"):
        return False
    if "dated_overlap_flag" in maintenance_windows and _to_bool(maintenance_windows["dated_overlap_flag"]).any():
        return False
    return True


def _recommendations_traceable(master: pd.DataFrame, recommendations: pd.DataFrame, review: pd.DataFrame) -> bool:
    if master.empty or recommendations.empty or review.empty:
        return False
    if not recommendations["alternative_id"].astype(str).isin(set(master["alternative_id"].astype(str))).all():
        return False
    if not recommendations["recommendation_rank"].is_unique:
        return False
    if not _all_false(recommendations, "auto_action_allowed") or not _all_false(review, "auto_action_allowed"):
        return False
    ranked = master.set_index("alternative_id")["recommendation_rank"].to_dict()
    for _, row in recommendations.iterrows():
        if _num(row.get("recommendation_rank")) != _num(ranked.get(str(row.get("alternative_id")), 0)):
            return False
    return True


def _fifo_sequence_valid(shadow: pd.DataFrame) -> bool:
    if shadow.empty:
        return False
    required = {"lot_id", "lot_availability_datetime", "lot_beginning_qty", "lot_drawn_qty", "lot_ending_qty", "lot_selection_method"}
    if not required.issubset(set(shadow.columns)):
        return False
    type_order = {"STARTING_ACCEPTED_WIP": 0, "ADVISORY_PRODUCTION_TO_BUFFER": 1, "ADVISORY_DRAW_FOR_OPERATION": 2}
    ordered = shadow.copy()
    ordered["_dt"] = ordered["event_datetime"].map(lambda value: _maybe_datetime(value) or datetime.min)
    ordered["_lot_dt"] = ordered["lot_availability_datetime"].map(lambda value: _maybe_datetime(value) or datetime.min)
    ordered["_type_order"] = ordered["shadow_event_type"].astype(str).map(lambda value: type_order.get(value, 9))
    lots: dict[tuple[str, str, str], dict[str, dict]] = defaultdict(dict)
    for _, row in ordered.sort_values(["alternative_id", "_dt", "_type_order", "shadow_wip_event_id"]).iterrows():
        key = (str(row["alternative_id"]), str(row["wip_item_id"]), str(row["wip_buffer_id"]))
        lot_id = str(row.get("lot_id", ""))
        event_type = str(row.get("shadow_event_type", ""))
        if event_type in {"STARTING_ACCEPTED_WIP", "ADVISORY_PRODUCTION_TO_BUFFER"}:
            if _num(row.get("advisory_produced_qty")) > 0.0001:
                if _blank(lot_id):
                    return False
                lots[key][lot_id] = {
                    "availability_datetime": _maybe_datetime(row.get("lot_availability_datetime")) or _maybe_datetime(row.get("event_datetime")) or datetime.min,
                    "remaining_qty": _num(row.get("lot_ending_qty", row.get("advisory_produced_qty"))),
                }
            continue
        if event_type != "ADVISORY_DRAW_FOR_OPERATION" or _num(row.get("advisory_drawn_qty")) <= 0.0001:
            continue
        if str(row.get("lot_selection_method", "")) != "FIFO" or _blank(lot_id):
            return False
        event_dt = _maybe_datetime(row.get("event_datetime")) or datetime.min
        available = [
            (lot["availability_datetime"], existing_lot_id)
            for existing_lot_id, lot in lots.get(key, {}).items()
            if lot["availability_datetime"] <= event_dt and _num(lot.get("remaining_qty")) > 0.0001
        ]
        if not available:
            return False
        expected_lot_id = sorted(available, key=lambda item: (item[0], item[1]))[0][1]
        if lot_id != expected_lot_id:
            return False
        current = _num(lots[key][lot_id].get("remaining_qty"))
        drawn = _num(row.get("advisory_drawn_qty"))
        if abs(_num(row.get("lot_beginning_qty")) - current) > 0.01 or drawn - current > 0.0001:
            return False
        lots[key][lot_id]["remaining_qty"] = current - drawn
        if abs(_num(row.get("lot_ending_qty")) - lots[key][lot_id]["remaining_qty"]) > 0.01:
            return False
    return True


def _wip_draw_after_lot_availability(shadow: pd.DataFrame) -> bool:
    if shadow.empty or "lot_availability_datetime" not in shadow.columns:
        return False
    draws = shadow[(shadow["shadow_event_type"].astype(str) == "ADVISORY_DRAW_FOR_OPERATION") & (shadow["advisory_drawn_qty"].map(_num) > 0.0001)]
    for _, row in draws.iterrows():
        event_dt = _maybe_datetime(row.get("event_datetime"))
        lot_dt = _maybe_datetime(row.get("lot_availability_datetime"))
        if not event_dt or not lot_dt or event_dt < lot_dt:
            return False
    return True


def _lot_ledger_reconciles(shadow: pd.DataFrame) -> bool:
    if shadow.empty:
        return False
    required = {"lot_id", "lot_beginning_qty", "lot_drawn_qty", "lot_ending_qty"}
    if not required.issubset(set(shadow.columns)):
        return False
    type_order = {"STARTING_ACCEPTED_WIP": 0, "ADVISORY_PRODUCTION_TO_BUFFER": 1, "ADVISORY_DRAW_FOR_OPERATION": 2}
    ordered = shadow.copy()
    ordered["_dt"] = ordered["event_datetime"].map(lambda value: _maybe_datetime(value) or datetime.min)
    ordered["_type_order"] = ordered["shadow_event_type"].astype(str).map(lambda value: type_order.get(value, 9))
    lots: dict[tuple[str, str, str, str], float] = defaultdict(float)
    for _, row in ordered.sort_values(["alternative_id", "_dt", "_type_order", "shadow_wip_event_id"]).iterrows():
        lot_id = str(row.get("lot_id", ""))
        if _blank(lot_id):
            continue
        key = (str(row["alternative_id"]), str(row["wip_item_id"]), str(row["wip_buffer_id"]), lot_id)
        event_type = str(row.get("shadow_event_type", ""))
        if event_type in {"STARTING_ACCEPTED_WIP", "ADVISORY_PRODUCTION_TO_BUFFER"}:
            produced = max(_num(row.get("advisory_produced_qty")) - _num(row.get("advisory_blocked_qty")), 0.0)
            if produced <= 0.0001:
                continue
            if abs(_num(row.get("lot_beginning_qty")) - lots[key]) > 0.01:
                return False
            lots[key] += produced
            if abs(_num(row.get("lot_ending_qty")) - lots[key]) > 0.01:
                return False
        elif event_type == "ADVISORY_DRAW_FOR_OPERATION":
            drawn = _num(row.get("advisory_drawn_qty"))
            if drawn <= 0.0001:
                continue
            if abs(_num(row.get("lot_beginning_qty")) - lots[key]) > 0.01 or drawn - lots[key] > 0.0001:
                return False
            lots[key] -= drawn
            if lots[key] < -0.0001 or abs(_num(row.get("lot_ending_qty")) - lots[key]) > 0.01:
                return False
    return True


def _no_expiry_on_non_shelf_life_items(shadow: pd.DataFrame) -> bool:
    if shadow.empty or "shelf_life_controlled_flag" not in shadow.columns or "expiration_datetime" not in shadow.columns:
        return False
    non_controlled = shadow[~_to_bool(shadow["shelf_life_controlled_flag"])]
    return bool(non_controlled["expiration_datetime"].map(_blank).all())


def _shelf_life_configuration_valid(shadow: pd.DataFrame) -> bool:
    if shadow.empty or "shelf_life_controlled_flag" not in shadow.columns:
        return False
    controlled = shadow[_to_bool(shadow["shelf_life_controlled_flag"])]
    if controlled.empty:
        return True
    if "shelf_life_hours" not in controlled.columns or "expiration_datetime" not in controlled.columns:
        return False
    return bool((controlled["shelf_life_hours"].map(_num) > 0).all() and controlled["expiration_datetime"].map(lambda value: _maybe_datetime(value) is not None).all())


def _input_draw_equals_scheduled_output_requirement(quantity_flow: pd.DataFrame) -> bool:
    consuming = quantity_flow[~quantity_flow["direct_input_wip_item_id"].map(_blank)]
    if consuming.empty:
        return True
    expected = consuming["scheduled_output_qty"].map(_num) * consuming["required_input_qty_per_output_unit"].map(_num)
    actual = consuming["advisory_wip_already_drawn"].map(_num)
    return bool(((actual - expected).abs() <= 0.01).all())


def _output_wip_equals_final_scheduled_quantity(detail: pd.DataFrame, shadow: pd.DataFrame) -> bool:
    produced = shadow[shadow["shadow_event_type"].astype(str) == "ADVISORY_PRODUCTION_TO_BUFFER"]
    qty_by_op = detail.set_index(["alternative_id", "schedule_candidate_id", "operation_id"])["final_reconciled_scheduled_qty"].map(_num).to_dict()
    for _, event in produced.iterrows():
        key = (event["alternative_id"], event["schedule_candidate_id"], event["producer_operation_id"])
        if abs(_num(event["advisory_produced_qty"]) - qty_by_op.get(key, 0.0)) > 0.01:
            return False
    produced_keys = set(zip(produced["alternative_id"].astype(str), produced["schedule_candidate_id"].astype(str), produced["producer_operation_id"].astype(str)))
    for _, row in detail.iterrows():
        key = (str(row["alternative_id"]), str(row["schedule_candidate_id"]), str(row["operation_id"]))
        if _blank(row.get("output_wip_item_id")):
            if key in produced_keys:
                return False
        elif _num(row["final_reconciled_scheduled_qty"]) > 0.0001 and key not in produced_keys:
            return False
    return True


def _buffer_policy_lookup(buffers: pd.DataFrame) -> dict[str, dict]:
    if buffers.empty or "wip_buffer_id" not in buffers.columns:
        return {}
    return {str(row["wip_buffer_id"]): row.to_dict() for _, row in buffers.iterrows()}


def _allowed_capacity_for_buffer_id(buffer_id: str, buffer_lookup: dict[str, dict]) -> tuple[float, str, str]:
    return _allowed_buffer_capacity(buffer_lookup.get(str(buffer_id), {}))


def _no_manager_review_buffer_overflow(shadow: pd.DataFrame, buffers: pd.DataFrame) -> bool:
    lookup = _buffer_policy_lookup(buffers)
    for _, row in shadow.iterrows():
        allowed, policy, _ = _allowed_capacity_for_buffer_id(str(row.get("wip_buffer_id", "")), lookup)
        if policy == "MANAGER_REVIEW" and allowed > 0 and _num(row.get("shadow_ending_qty")) > allowed + 0.0001:
            return False
    return True


def _no_unconfigured_temporary_overflow(shadow: pd.DataFrame, buffers: pd.DataFrame) -> bool:
    lookup = _buffer_policy_lookup(buffers)
    for _, row in shadow.iterrows():
        allowed, policy, reason = _allowed_capacity_for_buffer_id(str(row.get("wip_buffer_id", "")), lookup)
        if policy == "TEMPORARY_OVERFLOW_ALLOWED" and reason and allowed > 0 and _num(row.get("shadow_ending_qty")) > allowed + 0.0001:
            return False
    return True


def _shadow_within_allowed_buffer_capacity(shadow: pd.DataFrame, buffers: pd.DataFrame) -> bool:
    lookup = _buffer_policy_lookup(buffers)
    for _, row in shadow.iterrows():
        allowed, _, _ = _allowed_capacity_for_buffer_id(str(row.get("wip_buffer_id", "")), lookup)
        if allowed > 0 and _num(row.get("shadow_ending_qty")) > allowed + 0.0001:
            return False
    return True


def _output_production_within_available_space(detail: pd.DataFrame) -> bool:
    if detail.empty or "buffer_supported_output_qty" not in detail.columns:
        return False
    has_output = ~detail["output_wip_item_id"].map(_blank)
    scheduled = detail.loc[has_output, "final_reconciled_scheduled_qty"].map(_num)
    supported = detail.loc[has_output, "buffer_supported_output_qty"].map(_num)
    return bool((scheduled <= supported + 0.0001).all())


def _buffer_blocked_qty_reserves_no_capacity(detail: pd.DataFrame, segments: pd.DataFrame) -> bool:
    if "buffer_blocked_output_qty" not in detail.columns:
        return False
    blocked = detail[detail["buffer_blocked_output_qty"].map(_num) > 0.0001]
    if blocked.empty:
        return True
    for _, row in blocked.iterrows():
        seg = segments[
            (segments["alternative_id"].astype(str) == str(row["alternative_id"]))
            & (segments["schedule_candidate_id"].astype(str) == str(row["schedule_candidate_id"]))
            & (segments["operation_id"].astype(str) == str(row["operation_id"]))
            & (segments["segment_scheduled_qty"].map(_num) > 0.0001)
        ]
        if _num(row.get("final_reconciled_scheduled_qty")) - _num(row.get("buffer_supported_output_qty")) > 0.01:
            return False
        if seg["segment_scheduled_qty"].map(_num).sum() - _num(row.get("buffer_supported_output_qty")) > 0.01:
            return False
    return True


def _buffer_capacity_no_posthoc_trimming(detail: pd.DataFrame) -> bool:
    if "buffer_blocked_output_qty" not in detail.columns:
        return False
    blocked = detail["buffer_blocked_output_qty"].map(_num) > 0.0001
    return bool((detail.loc[blocked, "post_schedule_quantity_adjustment_qty"].map(_num).abs() <= 0.0001).all())


def _buffer_balance_before_production_matches_ledger(detail: pd.DataFrame, shadow: pd.DataFrame) -> bool:
    produced = shadow[shadow["shadow_event_type"].astype(str) == "ADVISORY_PRODUCTION_TO_BUFFER"]
    if produced.empty:
        return True
    beginning_by_key = produced.groupby(["alternative_id", "schedule_candidate_id", "producer_operation_id"], dropna=False)["shadow_beginning_qty"].first().to_dict()
    scheduled_output = detail[(~detail["output_wip_item_id"].map(_blank)) & (detail["final_reconciled_scheduled_qty"].map(_num) > 0.0001)]
    for _, row in scheduled_output.iterrows():
        key = (str(row["alternative_id"]), str(row["schedule_candidate_id"]), str(row["operation_id"]))
        if abs(_num(row.get("buffer_balance_before_production")) - _num(beginning_by_key.get(key))) > 0.01:
            return False
    return True


def _buffer_check_uses_completion_datetime(detail: pd.DataFrame) -> bool:
    output = detail[(~detail["output_wip_item_id"].map(_blank)) & (detail["final_reconciled_scheduled_qty"].map(_num) > 0.0001)]
    if output.empty:
        return True
    for _, row in output.iterrows():
        check_dt = _maybe_datetime(row.get("buffer_check_datetime"))
        end_dt = _maybe_datetime(row.get("proposed_end_datetime"))
        if not check_dt or not end_dt or abs((check_dt - end_dt).total_seconds()) > 60:
            return False
    return True


def _later_buffer_space_was_searched(detail: pd.DataFrame) -> bool:
    blocked = detail[(detail["buffer_blocked_output_qty"].map(_num) > 0.0001) & (~detail["buffer_release_datetime"].map(_blank))]
    if blocked.empty:
        return True
    return bool((blocked["buffer_search_attempt_count"].map(_num) > 1).all())


def _multi_output_buffer_space_simultaneous(detail: pd.DataFrame) -> bool:
    output = detail[(~detail["output_wip_item_id"].map(_blank)) & (detail["final_reconciled_scheduled_qty"].map(_num) > 0.0001)]
    if output.empty:
        return True
    return bool((output["buffer_reservation_qty"].map(_num) + 0.0001 >= output["final_reconciled_scheduled_qty"].map(_num)).all())


def _successor_start_respects_input_availability(detail: pd.DataFrame, segments: pd.DataFrame) -> bool:
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0.0001]
    if scheduled.empty:
        return True
    ready_by_op = detail.set_index(["alternative_id", "schedule_candidate_id", "operation_id"])["input_quantity_availability_datetime"].to_dict()
    for _, row in scheduled.iterrows():
        ready = _maybe_datetime(ready_by_op.get((row["alternative_id"], row["schedule_candidate_id"], row["operation_id"])))
        start = _maybe_datetime(row.get("proposed_start_datetime"))
        if ready and start and start + timedelta(minutes=1) < ready:
            return False
    return True


def _merge_input_support_before_capacity(detail: pd.DataFrame) -> bool:
    merge = detail[_to_bool(detail["merge_operation_flag"])]
    if merge.empty:
        return True
    return bool((merge["scheduling_target_qty"].map(_num) <= merge["merge_supported_qty"].map(_num) + 0.0001).all())


def _merge_input_available_at_start(detail: pd.DataFrame) -> bool:
    merge = detail[_to_bool(detail["merge_operation_flag"]) & (detail["final_reconciled_scheduled_qty"].map(_num) > 0.0001)]
    for _, row in merge.iterrows():
        start = _maybe_datetime(row.get("proposed_start_datetime"))
        ready = _maybe_datetime(row.get("input_quantity_availability_datetime"))
        if start and ready and start + timedelta(minutes=1) < ready:
            return False
    return True


def _provisional_final_capacity_match(capacity: pd.DataFrame, segments: pd.DataFrame) -> bool:
    return _capacity_impact_reconciles_to_final_segments(capacity, segments)


def _demand_reconciles(master: pd.DataFrame) -> bool:
    planned = master["planned_demand_qty"].map(_num)
    covered = master["covered_demand_qty"].map(_num)
    uncovered = master["uncovered_demand_qty"].map(_num)
    pct = master["demand_coverage_pct"].map(_num)
    return bool(((covered + uncovered - planned).abs() < 0.01).all() and ((pct >= 0) & (pct <= 100)).all())


def _setup_savings_valid(setup: pd.DataFrame) -> bool:
    bad = setup[(setup["setup_minutes_saved_vs_baseline"].map(_num) > 0) & ~_to_bool(setup["setup_saving_supported_flag"])]
    return bad.empty


def _maintenance_avoidance_valid(maintenance: pd.DataFrame, detail: pd.DataFrame) -> bool:
    bad = maintenance[_to_bool(maintenance["maintenance_avoidance_applied_flag"]) & _to_bool(maintenance["selected_window_maintenance_conflict_flag"])]
    return bad.empty


def _cost_traceable(cost: pd.DataFrame, assumptions: pd.DataFrame) -> bool:
    if "cost_classification" not in assumptions.columns:
        return False
    invalid_real = assumptions[(assumptions["cost_classification"].astype(str) == "VALIDATED_REAL_COST") & assumptions["source_file"].map(_blank)]
    return invalid_real.empty and (cost["total_real_cost"].map(_num) == cost["validated_real_cost_total"].map(_num)).all()


def _blocked_not_feasible(master: pd.DataFrame, detail: pd.DataFrame) -> bool:
    blocked_all = detail.groupby("alternative_id")["operation_schedule_status"].apply(lambda s: s.astype(str).eq("BLOCKED_REVIEW_REQUIRED").all()).to_dict()
    for _, row in master.iterrows():
        if blocked_all.get(str(row["alternative_id"]), False) and row["hard_feasibility_status"] == "HARD_FEASIBLE_WITH_REVIEW":
            return False
        if row["hard_feasibility_status"] in {"HARD_INFEASIBLE", "NO_COMPLETE_SCHEDULE"} and row["recommendation_status"] in {"RECOMMENDED_ADVISORY_ALTERNATIVE", "LEAST_RISK_ALTERNATIVE", "FEASIBLE_WITH_REVIEW"}:
            return False
    return True


def _quantity_flow_conserves(flow: pd.DataFrame) -> bool:
    if flow.empty:
        return False
    nonnegative_cols = [
        "requested_output_qty", "predecessor_completed_qty_available", "starting_accepted_wip_available",
        "advisory_wip_produced_available", "advisory_wip_already_drawn", "total_input_qty_available",
        "maximum_supported_output_qty", "scheduled_output_qty", "unscheduled_output_qty",
    ]
    if not _nonnegative(flow, nonnegative_cols):
        return False
    if (flow["scheduled_output_qty"].map(_num) > flow["maximum_supported_output_qty"].map(_num) + 0.0001).any():
        return False
    if (flow["quantity_balance_check"].map(_num).abs() > 0.0001).any():
        return False
    return True


def _merge_inputs_reconcile(detail: pd.DataFrame) -> bool:
    merge = detail[_to_bool(detail["merge_operation_flag"])]
    if merge.empty:
        return True
    scheduled = merge["schedulable_production_qty"].map(_num)
    supported = merge["merge_supported_qty"].map(_num)
    mandatory = merge["mandatory_predecessor_count"].map(_num)
    ready = merge["ready_predecessor_count"].map(_num)
    return bool(((scheduled <= supported + 0.0001) & ((ready >= mandatory) | (scheduled <= 0.0001))).all())


def _final_completed_reconciles(master: pd.DataFrame, detail: pd.DataFrame, candidates: pd.DataFrame) -> bool:
    candidate_planned = _index_by(candidates, "schedule_candidate_id")
    for _, row in master.iterrows():
        alt = str(row["alternative_id"])
        final_rows = detail[(detail["alternative_id"].astype(str) == alt) & detail["successor_operation_ids"].map(_blank)]
        covered = final_rows["schedulable_production_qty"].map(_num).sum()
        planned = sum(_num(candidate_planned.get(str(cid), {}).get("planned_production_qty")) for cid in final_rows["schedule_candidate_id"].astype(str).unique())
        if abs(covered - _num(row["covered_demand_qty"])) > 0.01:
            return False
        if planned > 0 and abs((_num(row["covered_demand_qty"]) / planned * 100.0) - _num(row["demand_coverage_pct"])) > 0.01:
            return False
    return True


def _shadow_wip_not_reused(shadow: pd.DataFrame) -> bool:
    balances: dict[tuple[str, str, str], float] = defaultdict(float)
    for _, row in shadow.sort_values(["alternative_id", "event_sequence"]).iterrows():
        key = (str(row["alternative_id"]), str(row["wip_item_id"]), str(row["wip_buffer_id"]))
        expected = balances[key] + _num(row["advisory_produced_qty"]) - _num(row["advisory_drawn_qty"]) - _num(row["advisory_blocked_qty"])
        if str(row["shadow_event_type"]) == "STARTING_ACCEPTED_WIP":
            expected = _num(row["shadow_ending_qty"])
        elif expected < -0.0001 or abs(expected - _num(row["shadow_ending_qty"])) > 0.01:
            return False
        balances[key] = _num(row["shadow_ending_qty"])
    return True


def _shadow_wip_buffer_ok(shadow: pd.DataFrame) -> bool:
    over = shadow[shadow["buffer_overflow_qty"].map(_num) > 0.0001]
    return over.empty or (over["shadow_balance_status"].astype(str) == "REVIEW_REQUIRED").all()


def _operation_remainders_accounted(segments: pd.DataFrame) -> bool:
    if segments.empty:
        return False
    for _, group in segments.groupby(["alternative_id", "schedule_candidate_id", "operation_id"]):
        requested = group["requested_operation_qty"].map(_num).max()
        scheduled = group["segment_scheduled_qty"].map(_num).sum()
        group = group.sort_values("segment_sequence")
        unscheduled = group[group["segment_scheduled_qty"].map(_num) <= 0.0001]
        remaining = unscheduled["remaining_unscheduled_qty"].map(_num).iloc[-1] if not unscheduled.empty else group["remaining_unscheduled_qty"].map(_num).iloc[-1]
        if abs(requested - scheduled - remaining) > 0.01:
            return False
    return True


def _multi_window_segmentation_present(segments: pd.DataFrame) -> bool:
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0]
    if scheduled.empty:
        return False
    counts = scheduled.groupby(["alternative_id", "schedule_candidate_id", "operation_id"]).size()
    return bool((counts > 1).any())


def _multi_window_not_truncated(segments: pd.DataFrame) -> bool:
    if not _multi_window_segmentation_present(segments):
        return False
    for _, group in segments.groupby(["alternative_id", "schedule_candidate_id", "operation_id"]):
        scheduled_count = int((group["segment_scheduled_qty"].map(_num) > 0).sum())
        final_remaining = _num(group.sort_values("segment_sequence")["remaining_unscheduled_qty"].iloc[-1])
        if scheduled_count == 1 and final_remaining > 0.0001:
            statuses = set(group["segment_schedule_status"].astype(str))
            if "PARTIAL_OPERATION_SEGMENT" in statuses and not statuses.intersection({"UNSCHEDULED_NO_CAPACITY", "UNSCHEDULED_PREDECESSOR_SHORTAGE", "UNSCHEDULED_WIP_SHORTAGE"}):
                return False
    return True


def _segment_sequence_valid(segments: pd.DataFrame) -> bool:
    for _, group in segments.groupby(["alternative_id", "schedule_candidate_id", "operation_id"]):
        ordered = group.sort_values("segment_sequence")
        seqs = [int(_num(value)) for value in ordered["segment_sequence"]]
        if seqs != list(range(1, len(seqs) + 1)):
            return False
        unscheduled_positions = [idx for idx, qty in enumerate(ordered["segment_scheduled_qty"].map(_num).tolist()) if qty <= 0.0001]
        if unscheduled_positions and unscheduled_positions[-1] != len(ordered) - 1:
            return False
        if len(unscheduled_positions) > 1:
            return False
    return True


def _segment_quantity_reconciles(segments: pd.DataFrame, detail: pd.DataFrame) -> bool:
    detail_index = _index_by3(detail, "alternative_id", "schedule_candidate_id", "operation_id")
    for key, group in segments.groupby(["alternative_id", "schedule_candidate_id", "operation_id"]):
        ordered = group.sort_values("segment_sequence")
        requested = ordered["requested_operation_qty"].map(_num).max()
        scheduled_values = ordered["segment_scheduled_qty"].map(_num)
        if (scheduled_values < -0.0001).any() or ((scheduled_values <= 0.0001) & (ordered["segment_schedule_status"].astype(str).str.startswith(("FULL", "PARTIAL", "CONTINUATION")))).any():
            return False
        cumulative = ordered["cumulative_scheduled_qty"].map(_num)
        if (cumulative.diff().fillna(cumulative.iloc[0]) < -0.0001).any():
            return False
        scheduled = scheduled_values.sum()
        remaining = ordered["remaining_unscheduled_qty"].map(_num).iloc[-1]
        if abs(requested - scheduled - remaining) > 0.01:
            return False
        detail_row = detail_index.get(tuple(map(str, key)), {})
        if detail_row and abs(scheduled - _num(detail_row.get("schedulable_production_qty"))) > 0.01:
            return False
    return True


def _segment_time_capacity_reconciles(segments: pd.DataFrame) -> bool:
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0]
    for _, row in scheduled.iterrows():
        if abs(_num(row["segment_scheduled_qty"]) * _num(row["processing_minutes_per_unit"]) - _num(row["segment_processing_minutes"])) > 0.02:
            return False
        if abs(_num(row["segment_processing_minutes"]) + _num(row["segment_setup_minutes"]) - _num(row["segment_total_minutes"])) > 0.02:
            return False
    return _segments_have_valid_windows(segments)


def _setup_applied_once_per_operation(segments: pd.DataFrame, detail: pd.DataFrame) -> bool:
    detail_index = _index_by3(detail, "alternative_id", "schedule_candidate_id", "operation_id")
    for key, group in segments.groupby(["alternative_id", "schedule_candidate_id", "operation_id"]):
        scheduled = group[group["segment_scheduled_qty"].map(_num) > 0].sort_values("segment_sequence")
        if scheduled.empty:
            continue
        setup_rows = scheduled[scheduled["segment_setup_minutes"].map(_num) > 0.0001]
        if len(setup_rows) > 1:
            return False
        if not setup_rows.empty and int(_num(setup_rows.iloc[0]["segment_sequence"])) != 1:
            return False
        detail_row = detail_index.get(tuple(map(str, key)), {})
        expected_setup = _num(detail_row.get("actual_sequence_setup_minutes")) if detail_row else 0.0
        if abs(scheduled["segment_setup_minutes"].map(_num).sum() - expected_setup) > 0.02:
            return False
    return True


def _operation_detail_reconciles_to_segments(detail: pd.DataFrame, segments: pd.DataFrame) -> bool:
    for key, group in segments.groupby(["alternative_id", "schedule_candidate_id", "operation_id"]):
        detail_rows = detail[
            (detail["alternative_id"].astype(str) == str(key[0]))
            & (detail["schedule_candidate_id"].astype(str) == str(key[1]))
            & (detail["operation_id"].astype(str) == str(key[2]))
        ]
        if detail_rows.empty:
            return False
        row = detail_rows.iloc[0]
        scheduled = group[group["segment_scheduled_qty"].map(_num) > 0].copy()
        scheduled_qty = scheduled["segment_scheduled_qty"].map(_num).sum()
        if abs(scheduled_qty - _num(row["schedulable_production_qty"])) > 0.01:
            return False
        if scheduled.empty:
            if not _blank(row.get("proposed_start_datetime")) or not _blank(row.get("proposed_end_datetime")):
                return False
            continue
        scheduled["_start"] = pd.to_datetime(scheduled["proposed_start_datetime"])
        scheduled["_end"] = pd.to_datetime(scheduled["proposed_end_datetime"])
        if str(scheduled["_start"].min().isoformat(timespec="minutes")) != str(row["proposed_start_datetime"]):
            return False
        if str(scheduled["_end"].max().isoformat(timespec="minutes")) != str(row["proposed_end_datetime"]):
            return False
    return True


def _unscheduled_remainder_final_only(segments: pd.DataFrame) -> bool:
    for _, group in segments.groupby(["alternative_id", "schedule_candidate_id", "operation_id"]):
        ordered = group.sort_values("segment_sequence")
        unscheduled = ordered[ordered["segment_scheduled_qty"].map(_num) <= 0.0001]
        if len(unscheduled) > 1:
            return False
        if not unscheduled.empty and int(_num(unscheduled.iloc[0]["segment_sequence"])) != int(_num(ordered.iloc[-1]["segment_sequence"])):
            return False
    return True


def _segments_have_valid_windows(segments: pd.DataFrame) -> bool:
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0]
    for _, row in scheduled.iterrows():
        try:
            start = datetime.fromisoformat(str(row["proposed_start_datetime"]))
            end = datetime.fromisoformat(str(row["proposed_end_datetime"]))
            datetime.fromisoformat(str(row["proposed_schedule_date"]))
        except ValueError:
            return False
        if end <= start or _blank(row.get("proposed_shift_id")):
            return False
    return True


def _no_machine_segment_overlap(segments: pd.DataFrame) -> bool:
    return _no_machine_unit_overlap(segments)


def _explode_unit_intervals(segments: pd.DataFrame, unit_column: str) -> list[tuple[str, str, datetime, datetime]]:
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0].copy()
    if scheduled.empty:
        return []
    intervals = []
    for _, row in scheduled.iterrows():
        try:
            start = datetime.fromisoformat(str(row["proposed_start_datetime"]))
            end = datetime.fromisoformat(str(row["proposed_end_datetime"]))
        except ValueError:
            continue
        for unit_id in str(row.get(unit_column, "")).split(";"):
            unit_id = unit_id.strip()
            if unit_id:
                intervals.append((str(row["alternative_id"]), unit_id, start, end))
    return intervals


def _no_unit_overlap(segments: pd.DataFrame, unit_column: str) -> bool:
    grouped: dict[tuple[str, str], list[tuple[datetime, datetime]]] = defaultdict(list)
    for alt_id, unit_id, start, end in _explode_unit_intervals(segments, unit_column):
        grouped[(alt_id, unit_id)].append((start, end))
    for spans in grouped.values():
        spans = sorted(spans)
        prev_end = None
        for start, end in spans:
            if prev_end is not None and start < prev_end:
                return False
            prev_end = end
    return True


def _no_machine_unit_overlap(segments: pd.DataFrame) -> bool:
    return _no_unit_overlap(segments, "assigned_machine_unit_ids")


def _no_labor_unit_overlap(segments: pd.DataFrame) -> bool:
    return _no_unit_overlap(segments, "assigned_labor_unit_ids")


def _parallel_resource_master_reconciles(frames: dict[str, pd.DataFrame], segments: pd.DataFrame) -> bool:
    expected = _expected_parallel_lanes(frames)
    for ws, count in expected.items():
        if ws in {"WS-FRAME-PREP", "WS-WHEEL-SUB", "WS-BRAKE-SUB", "WS-FORK-SUSP"} and count not in {2, 3}:
            return False
        if ws in {"WS-FINAL-ASM", "WS-QC", "WS-PACK"} and count != 1:
            return False
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0]
    observed = scheduled.groupby("workstation_id")["effective_parallel_lane_count"].max().map(lambda v: int(_num(v))).to_dict()
    for ws, lane_count in observed.items():
        if expected.get(str(ws), 1) != lane_count:
            return False
    return True


def _expected_parallel_lanes(frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    workstations = _index_by(frames["workstations"], "workstation_id")
    machines_by_ws = defaultdict(int)
    for _, row in frames["machines"][_to_bool(frames["machines"]["active_flag"])].iterrows():
        machines_by_ws[str(row["workstation_id"])] += max(int(_num(row.get("machine_count"))), 1)
    workers_by_ws = defaultdict(int)
    labor_parallel_by_ws = {}
    for _, row in frames["labor"][_to_bool(frames["labor"]["active_flag"])].iterrows():
        ws = str(row["workstation_id"])
        workers_by_ws[ws] += max(int(_num(row.get("workers_available"))), 1)
        labor_parallel_by_ws[ws] = _bool(row.get("can_support_parallel_work_flag"))
    result = {}
    for ws, ws_row in workstations.items():
        if _bool(ws_row.get("supports_parallel_work_flag")) and labor_parallel_by_ws.get(ws, False):
            result[ws] = max(min(machines_by_ws.get(ws, 1), workers_by_ws.get(ws, 1)), 1)
        else:
            result[ws] = 1
    return result


def _parallel_workstation_capacity_applied(segments: pd.DataFrame) -> bool:
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0]
    parallel = scheduled[_to_bool(scheduled["parallel_capacity_applied_flag"])]
    if parallel.empty:
        return False
    grouped = parallel.groupby(["alternative_id", "workstation_id", "proposed_schedule_date"])["segment_total_minutes"].apply(lambda s: s.map(_num).sum())
    return bool((grouped > 435.0001).any())


def _resource_unit_assignment_complete(segments: pd.DataFrame) -> bool:
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0]
    for _, row in scheduled.iterrows():
        machine_units = [u for u in str(row.get("assigned_machine_unit_ids", "")).split(";") if u.strip()]
        labor_units = [u for u in str(row.get("assigned_labor_unit_ids", "")).split(";") if u.strip()]
        if len(machine_units) < max(int(_num(row.get("required_machine_count", 1))), 1):
            return False
        if len(labor_units) < max(int(_num(row.get("required_worker_count", 1))), 1):
            return False
        if _blank(row.get("parallel_lane_id")) or _blank(row.get("resource_bundle_status")):
            return False
    return True


def _nonparallel_workstation_no_overlap(segments: pd.DataFrame) -> bool:
    scheduled = segments[(segments["segment_scheduled_qty"].map(_num) > 0) & (~_to_bool(segments["workstation_parallel_authorized_flag"]))].copy()
    if scheduled.empty:
        return True
    scheduled["_start"] = pd.to_datetime(scheduled["proposed_start_datetime"])
    scheduled["_end"] = pd.to_datetime(scheduled["proposed_end_datetime"])
    for _, group in scheduled.groupby(["alternative_id", "workstation_id"]):
        group = group.sort_values("_start")
        prev_end = None
        for _, row in group.iterrows():
            if prev_end is not None and row["_start"] < prev_end:
                return False
            prev_end = row["_end"]
    return True


def _parallel_lane_concurrency_within_limit(segments: pd.DataFrame) -> bool:
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0].copy()
    if scheduled.empty:
        return True
    for _, group in scheduled.groupby(["alternative_id", "workstation_id"]):
        events = []
        lane_count = max(group["effective_parallel_lane_count"].map(_num).max(), 1.0)
        for _, row in group.iterrows():
            try:
                events.append((datetime.fromisoformat(str(row["proposed_start_datetime"])), 1))
                events.append((datetime.fromisoformat(str(row["proposed_end_datetime"])), -1))
            except ValueError:
                return False
        active = 0
        for _, delta in sorted(events, key=lambda item: (item[0], item[1])):
            active += delta
            if active > lane_count + 0.0001:
                return False
    return True


def _simultaneous_resource_bundle_valid(segments: pd.DataFrame) -> bool:
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0]
    return _resource_unit_assignment_complete(scheduled) and _segments_have_valid_windows(scheduled)


def _aggregate_capacity_reconciles_to_unit_calendars(capacity: pd.DataFrame) -> bool:
    required = [
        "net_minutes_per_resource_unit",
        "effective_parallel_lane_count",
        "aggregate_workstation_capacity_minutes",
        "aggregate_machine_capacity_minutes",
        "aggregate_labor_capacity_minutes",
        "total_scheduled_workload_minutes",
        "remaining_aggregate_capacity_minutes",
    ]
    if any(column not in capacity.columns for column in required):
        return False
    for _, row in capacity.iterrows():
        net = _num(row["net_minutes_per_resource_unit"])
        lanes = max(_num(row["effective_parallel_lane_count"]), 1.0)
        aggregate = _num(row["aggregate_workstation_capacity_minutes"])
        if aggregate + 0.01 < net * lanes:
            return False
        if abs(_num(row["aggregate_machine_capacity_minutes"]) - aggregate) > 0.01:
            return False
        if abs(_num(row["aggregate_labor_capacity_minutes"]) - aggregate) > 0.01:
            return False
        if _num(row["remaining_aggregate_capacity_minutes"]) < -0.0001:
            return False
        if _num(row["total_scheduled_workload_minutes"]) - aggregate > 0.01:
            return False
    return True


def _parallel_capacity_not_extended_day(segments: pd.DataFrame) -> bool:
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0]
    for _, row in scheduled.iterrows():
        try:
            start = datetime.fromisoformat(str(row["proposed_start_datetime"]))
            end = datetime.fromisoformat(str(row["proposed_end_datetime"]))
        except ValueError:
            return False
        if start.hour < 8 or end.hour > 16 or (end.hour == 16 and end.minute > 0) or start.date() != end.date():
            return False
    return True


def _continuation_resource_assignment_reconciles(segments: pd.DataFrame, detail: pd.DataFrame) -> bool:
    scheduled = segments[segments["segment_scheduled_qty"].map(_num) > 0]
    for key, group in scheduled.groupby(["alternative_id", "schedule_candidate_id", "operation_id"]):
        if not _resource_unit_assignment_complete(group):
            return False
        setup_rows = group[_to_bool(group["setup_applied_flag"])].sort_values("segment_sequence")
        if len(setup_rows) > 1:
            return False
        if len(setup_rows) == 1 and int(_num(setup_rows.iloc[0]["segment_sequence"])) != 1:
            return False
        bundles = group.apply(lambda r: (str(r.get("assigned_machine_unit_ids", "")), str(r.get("assigned_labor_unit_ids", ""))), axis=1).tolist()
        bundle_changes = sum(1 for prev, cur in zip(bundles, bundles[1:]) if prev != cur)
        detail_row = detail[
            (detail["alternative_id"].astype(str) == str(key[0]))
            & (detail["schedule_candidate_id"].astype(str) == str(key[1]))
            & (detail["operation_id"].astype(str) == str(key[2]))
        ]
        if not detail_row.empty and int(_num(detail_row.iloc[0].get("resource_bundle_change_count", 0))) != bundle_changes:
            return False
    return True


def _risk_not_blanket_downtime(master: pd.DataFrame, segments: pd.DataFrame, maintenance_windows: pd.DataFrame) -> bool:
    risk_rows = maintenance_windows[maintenance_windows["maintenance_window_check_status"].astype(str) == "MAINTENANCE_RISK_REVIEW"]
    if risk_rows.empty:
        return True
    scheduled_by_alt = segments[segments["segment_scheduled_qty"].map(_num) > 0].groupby("alternative_id").size().to_dict()
    return any(count > 0 for count in scheduled_by_alt.values())


def _cost_reconciles_to_segments(cost: pd.DataFrame, segments: pd.DataFrame) -> bool:
    for _, row in cost.iterrows():
        seg = segments[(segments["alternative_id"].astype(str) == str(row["alternative_id"])) & (segments["segment_scheduled_qty"].map(_num) > 0)]
        if abs(seg["segment_processing_minutes"].map(_num).sum() - _num(row["scheduled_processing_minutes"])) > 0.01:
            return False
        if abs(seg["segment_setup_minutes"].map(_num).sum() - _num(row["scheduled_setup_minutes"])) > 0.01:
            return False
    return True


def _unscheduled_work_not_charged(cost: pd.DataFrame, segments: pd.DataFrame) -> bool:
    for _, row in cost.iterrows():
        seg = segments[segments["alternative_id"].astype(str) == str(row["alternative_id"])]
        if seg["segment_scheduled_qty"].map(_num).sum() <= 0.0001 and (_num(row["real_processing_cost"]) > 0.0001 or _num(row["real_labor_cost"]) > 0.0001):
            return False
    return True


def _partial_not_fully_feasible(master: pd.DataFrame) -> bool:
    partial = master[master["covered_demand_qty"].map(_num) + 0.0001 < master["planned_demand_qty"].map(_num)]
    return not (partial["hard_feasibility_status"].astype(str) == "HARD_FEASIBLE").any()


def _check_no_forbidden_outputs(checks: list[dict]) -> None:
    tokens = ["production_order", "confirmed_production_schedule", "actual_wip_consumption", "wip_transaction", "component_inventory_consumption", "inventory_reservation", "worker_dispatch", "purchase_order", "maintenance_work_order", "capacity_reduction", "simulation"]
    bad = [str(path) for path in OUTPUT_DIR.glob("*") if any(token in path.name.lower() for token in tokens)]
    _add_check(checks, "NO_FORBIDDEN_EXECUTION_OUTPUTS", "PASS" if not bad else "FAIL", f"Forbidden outputs found: {bad}", len(bad))


def _ensure_cost_assumptions() -> None:
    if COST_ASSUMPTIONS_FILE.exists():
        return
    rows = [
        ["LABOR_STANDARD_HOURLY_WAGE", "Production labor standard wage", "labor_resources.hourly_wage", "EUR_PER_HOUR", "VALIDATED_REAL_COST", "phase 4/data/labor_resources.csv", "hourly_wage", "MEDIUM", False, "Traceable production labor cost.", True, True],
        ["MACHINE_HOURLY_COST", "Machine hourly cost", "machines.hourly_machine_cost", "EUR_PER_HOUR", "VALIDATED_REAL_COST", "phase 4/data/machines.csv", "hourly_machine_cost", "MEDIUM", False, "Traceable machine cost.", True, True],
        ["ASSUMED_SETUP_SUPPORT_RATE", "Assumed setup support rate", 20, "EUR_PER_HOUR", "ASSUMED_MONETARY_RATE", "", "", "LOW", True, "Used only in assumed monetary cost, not validated real cost.", True, True],
        ["PROXY_LATE_DEMAND", "Late demand proxy penalty", 80, "POINTS_PER_UNIT", "PROXY_PENALTY", "", "", "LOW", True, "Proxy score only, not euros.", True, True],
        ["PROXY_CUSTOMER_DISSATISFACTION", "Customer dissatisfaction proxy", 45, "POINTS_PER_UNIT", "PROXY_PENALTY", "", "", "LOW", True, "Proxy score only, not euros.", True, True],
    ]
    pd.DataFrame(rows, columns=["cost_component_id", "cost_component_name", "rate_value", "rate_unit", "cost_classification", "source_file", "source_field", "confidence", "assumption_flag", "notes", "active_flag", "advisory_only_flag"]).to_csv(COST_ASSUMPTIONS_FILE, index=False)


def _labor_rate_by_workstation(labor: pd.DataFrame) -> dict[str, float]:
    return {str(row["workstation_id"]): _num(row.get("hourly_wage")) for _, row in labor.iterrows()}


def _bottleneck_queue_penalty(frames: dict[str, pd.DataFrame], ops: pd.DataFrame) -> float:
    bottleneck = _index_by(frames["bottleneck"], "workstation_id")
    queue = _index_by(frames["queue"], "workstation_id")
    total = 0.0
    for ws in ops["workstation_id"].drop_duplicates().astype(str):
        total += _risk_points(str(bottleneck.get(ws, {}).get("bottleneck_visibility_level", "LOW"))) * 10
        total += _risk_points(str(queue.get(ws, {}).get("overall_queue_risk_level", "LOW"))) * 10
    return total


def _risk_points(level: str) -> float:
    return {"LOW": 0.0, "MEDIUM": 10.0, "HIGH": 25.0, "CRITICAL": 45.0, "REVIEW_REQUIRED": 35.0}.get(str(level), 0.0)


def _hard_sort(status: str) -> int:
    return {"HARD_FEASIBLE": 0, "HARD_FEASIBLE_WITH_REVIEW": 1, "PARTIAL_FINITE_SCHEDULE": 2, "REVIEW_REQUIRED": 3, "NO_COMPLETE_SCHEDULE": 4, "HARD_INFEASIBLE": 5}.get(str(status), 6)


def _main_benefit(alt_type: str) -> str:
    return {
        "BASELINE_FROM_STEP_8B": "Provides finite-capacity comparison baseline.",
        "BOTTLENECK_CRITICAL_PATH_PRIORITY": "Protects critical path and bottleneck operations.",
        "SETUP_REDUCTION_BATCHING": "Uses setup-family sequence evidence to reduce switches where possible.",
        "WIP_PROTECTED_CONTINUITY": "Uses accepted WIP and buffer capacity as advisory continuity support.",
        "MAINTENANCE_AWARE_SHIFTING": "Avoids maintenance conflicts only when a real non-conflicting window is selected.",
        "LEAST_RISK_COMBINED": "Combines the strongest advisory risk-reduction rules.",
    }.get(str(alt_type), "Review required.")


def _main_risk(hard_status: str, confidence: str) -> str:
    if hard_status in {"NO_COMPLETE_SCHEDULE", "HARD_INFEASIBLE"}:
        return "No hard-feasible complete advisory schedule."
    if confidence == "LOW":
        return "Important monetary and proxy assumptions have low confidence."
    return "Manager review required before execution."


def _load_csv(path: Path, label: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        _add_check(checks, f"{label}_exists", "FAIL", f"Missing input: {path}", 0)
        return None
    frame = pd.read_csv(path)
    _add_check(checks, f"{label}_exists", "PASS" if not frame.empty else "FAIL", f"{label} rows={len(frame)}", len(frame))
    return frame


def _merge_buffer_policy(status: pd.DataFrame, locations: pd.DataFrame) -> pd.DataFrame:
    if status.empty or locations.empty or "wip_buffer_id" not in status.columns or "wip_buffer_id" not in locations.columns:
        return status
    policy_cols = [col for col in ["wip_buffer_id", "overflow_policy", "temporary_overflow_limit_qty", "temporary_overflow_max_qty", "max_temporary_overflow_qty"] if col in locations.columns]
    merged = status.merge(locations[policy_cols].drop_duplicates("wip_buffer_id"), on="wip_buffer_id", how="left")
    if "overflow_policy" not in merged.columns:
        merged["overflow_policy"] = "MANAGER_REVIEW"
    merged["overflow_policy"] = merged["overflow_policy"].fillna("MANAGER_REVIEW")
    return merged


def _planning_run_id(frames: dict[str, pd.DataFrame]) -> str:
    for frame in frames.values():
        if isinstance(frame, pd.DataFrame) and "planning_run_id" in frame.columns and not frame.empty:
            vals = frame["planning_run_id"].dropna().astype(str).str.strip()
            if not vals.empty:
                return vals.iloc[0]
    return "PHASE4-SCHEDULE-ALTERNATIVES"


def _index_by(df: pd.DataFrame, col: str) -> dict[str, dict]:
    if df.empty or col not in df.columns:
        return {}
    return {str(row[col]): row.to_dict() for _, row in df.iterrows()}


def _index_by2(df: pd.DataFrame, c1: str, c2: str) -> dict[tuple[str, str], dict]:
    if df.empty or c1 not in df.columns or c2 not in df.columns:
        return {}
    return {(str(row[c1]), str(row[c2])): row.to_dict() for _, row in df.iterrows()}


def _index_by3(df: pd.DataFrame, c1: str, c2: str, c3: str) -> dict[tuple[str, str, str], dict]:
    if df.empty or c1 not in df.columns or c2 not in df.columns or c3 not in df.columns:
        return {}
    return {(str(row[c1]), str(row[c2]), str(row[c3])): row.to_dict() for _, row in df.iterrows()}


def _first_by2(df: pd.DataFrame, c1: str, c2: str) -> dict[tuple[str, str], dict]:
    grouped = _group_by2(df, c1, c2)
    return {key: rows[0] for key, rows in grouped.items()}


def _group_by2(df: pd.DataFrame, c1: str, c2: str) -> dict[tuple[str, str], list[dict]]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    if df.empty or c1 not in df.columns or c2 not in df.columns:
        return groups
    for _, row in df.iterrows():
        groups[(str(row[c1]), str(row[c2]))].append(row.to_dict())
    return groups


def _parse_date(value: str) -> datetime:
    return datetime.fromisoformat(str(value)[:10] + "T08:00")


def _split_ids(value: object) -> list[str]:
    if _blank(value):
        return []
    return [item.strip() for item in str(value).split(";") if item.strip()]


def _join_unique(values: list[object]) -> str:
    return ";".join(dict.fromkeys([str(v) for v in values if not _blank(v)]))


def _num(value: object) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return 0.0 if pd.isna(parsed) else float(parsed)


def _bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _blank(value: object) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "nat"}


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _all_true(df: pd.DataFrame, column: str) -> bool:
    return column in df.columns and bool(_to_bool(df[column]).all())


def _all_false(df: pd.DataFrame, column: str) -> bool:
    return column in df.columns and bool((~_to_bool(df[column])).all())


def _nonnegative(df: pd.DataFrame, columns: list[str]) -> bool:
    for column in columns:
        if column not in df.columns:
            return False
        values = pd.to_numeric(df[column], errors="coerce")
        if values.isna().any() or (values < -0.0001).any():
            return False
    return True


def _add_check(checks: list[dict], check_id: str, status: str, message: str, affected_rows: int) -> None:
    checks.append({"check_id": check_id, "check_name": check_id, "status": status, "message": message, "affected_rows": affected_rows, "advisory_only_flag": True})


def _empty_master() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "alternative_id", "alternative_type", "alternative_name", "alternative_description", "finished_sku_count", "schedule_candidate_count", "operation_count", "planned_demand_qty", "covered_demand_qty", "uncovered_demand_qty", "demand_coverage_pct", "on_time_completed_qty", "late_completed_qty", "unscheduled_qty", "lateness_days_weighted", "demand_coverage_calculation_basis", "hard_feasibility_status", "total_real_cost", "validated_real_cost_total", "assumed_monetary_cost_total", "total_proxy_penalty", "total_advisory_schedule_score", "cost_basis", "cost_confidence", "recommendation_rank", "recommendation_status", "source_phase", "advisory_only_flag"])


def _empty_operation_detail() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "alternative_id", "alternative_type", "schedule_candidate_id", "finished_sku", "operation_id", "operation_name", "operation_sequence", "workstation_id", "machine_id", "candidate_schedule_period", "candidate_schedule_day", "candidate_schedule_shift", "proposed_schedule_period", "proposed_schedule_day", "proposed_schedule_shift", "proposed_schedule_date", "proposed_shift_id", "proposed_start_datetime", "proposed_end_datetime", "proposed_window_id", "predecessor_operation_ids", "successor_operation_ids", "critical_path_flag", "merge_operation_flag", "parallel_branch_flag", "required_input_wip_item_id", "output_wip_item_id", "wip_buffer_id", "setup_family_id", "estimated_processing_time_minutes", "estimated_setup_time_minutes", "estimated_total_time_minutes", "requested_production_qty", "quantity_supported_before_capacity", "scheduling_target_qty", "capacity_scheduled_qty", "final_reconciled_scheduled_qty", "post_schedule_quantity_adjustment_qty", "post_schedule_quantity_adjustment_flag", "input_quantity_availability_datetime", "quantity_support_status", "quantity_support_blocker_reason", "resource_reserved_for_supported_qty_flag", "buffer_capacity_before_production", "buffer_balance_before_production", "available_buffer_space_qty", "buffer_supported_output_qty", "buffer_blocked_output_qty", "allowed_buffer_capacity_qty", "overflow_policy", "buffer_capacity_status", "buffer_capacity_blocker_reason", "buffer_check_datetime", "projected_balance_at_completion", "projected_space_at_completion", "buffer_release_datetime", "buffer_delay_minutes", "buffer_reservation_qty", "buffer_reservation_status", "buffer_search_attempt_count", "schedulable_production_qty", "processing_minutes_per_unit", "processing_minutes_total", "actual_sequence_setup_minutes", "total_required_minutes", "required_hours_total", "workload_calculation_basis", "effective_parallel_lane_count", "parallel_capacity_applied_flag", "assigned_machine_unit_ids", "assigned_labor_unit_ids", "resource_bundle_change_count", "resource_bundle_assignment_status", "mandatory_predecessor_count", "ready_predecessor_count", "predecessor_quantity_ready_flag", "predecessor_ready_datetime", "merge_supported_qty", "precedence_check_status", "merge_input_completion_status", "independently_calculated_precedence_status", "precedence_violation_flag", "operation_hard_feasibility_status", "operation_schedule_status", "schedule_blocker_reason", "segment_schedule_json", "source_phase", "advisory_only_flag"])


def _empty_capacity_impact() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "alternative_id", "schedule_candidate_id", "operation_id", "final_operation_segment_ids", "workstation_id", "machine_id", "labor_skill_id", "proposed_schedule_period", "proposed_schedule_day", "proposed_schedule_shift", "proposed_schedule_date", "proposed_shift_id", "proposed_window_id", "available_minutes", "net_minutes_per_resource_unit", "effective_parallel_lane_count", "aggregate_workstation_capacity_minutes", "aggregate_machine_capacity_minutes", "aggregate_labor_capacity_minutes", "scheduled_minutes_by_machine_unit", "scheduled_minutes_by_labor_unit", "total_scheduled_workload_minutes", "remaining_aggregate_capacity_minutes", "workstation_utilization_pct", "machine_utilization_pct", "labor_utilization_pct", "workstation_utilization_percentage", "machine_utilization_percentage", "labor_utilization_percentage", "binding_resource_type", "previously_allocated_minutes", "requested_minutes", "newly_allocated_minutes", "remaining_minutes", "overload_minutes", "required_processing_hours", "required_setup_hours", "total_required_hours", "available_hours_reference", "utilization_pct", "quality_adjusted_utilization_pct", "capacity_feasibility_status", "capacity_overload_hours", "capacity_overload_penalty", "underutilization_hours", "underutilization_penalty", "note_no_capacity_change_flag", "source_phase", "advisory_only_flag"])


def _empty_wip_impact() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "alternative_id", "finished_sku", "operation_id", "required_input_wip_item_id", "output_wip_item_id", "wip_buffer_id", "accepted_wip_available_qty", "required_wip_qty", "projected_wip_build_qty", "projected_wip_draw_qty_advisory", "projected_wip_ending_qty_advisory", "wip_shortage_qty", "wip_overflow_qty", "wip_impact_status", "wip_shortage_penalty", "wip_overflow_penalty", "buffer_capacity_before_production", "buffer_balance_before_production", "available_buffer_space_qty", "requested_output_qty", "buffer_supported_output_qty", "buffer_blocked_output_qty", "allowed_buffer_capacity_qty", "overflow_policy", "buffer_capacity_status", "buffer_capacity_blocker_reason", "buffer_check_datetime", "projected_balance_at_completion", "projected_space_at_completion", "buffer_release_datetime", "buffer_delay_minutes", "buffer_reservation_qty", "buffer_reservation_status", "buffer_search_attempt_count", "note_no_wip_consumption_flag", "source_phase", "advisory_only_flag"])


def _empty_setup_impact() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "alternative_id", "schedule_candidate_id", "operation_id", "workstation_id", "machine_id", "proposed_schedule_period", "proposed_schedule_day", "proposed_schedule_shift", "operation_sequence_position", "previous_operation_id", "previous_setup_family_id", "current_setup_family_id", "changeover_time_minutes", "actual_changeover_minutes", "setup_switch_flag", "baseline_changeover_minutes", "setup_minutes_saved_vs_baseline", "setup_saving_supported_flag", "changeover_complexity", "setup_capacity_loss_minutes", "setup_changeover_cost", "batching_applied_flag", "batching_opportunity_flag", "setup_impact_status", "source_phase", "advisory_only_flag"])


def _empty_maintenance_impact() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "alternative_id", "workstation_id", "machine_id", "operation_id", "proposed_schedule_period", "proposed_schedule_day", "proposed_schedule_shift", "maintenance_feasibility_status", "breakdown_risk_level", "maintenance_conflict_flag", "maintenance_conflict_penalty", "breakdown_risk_penalty", "maintenance_avoidance_applied_flag", "original_maintenance_conflict_flag", "selected_window_maintenance_conflict_flag", "selected_window_maintenance_status", "maintenance_conflict_avoided_flag", "maintenance_avoidance_evidence", "note_no_maintenance_order_created_flag", "source_phase", "advisory_only_flag"])


def _empty_cost_score() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "alternative_id", "alternative_type", "real_setup_cost", "real_processing_cost", "real_labor_cost", "real_quality_cost", "real_maintenance_cost", "real_wip_holding_cost", "validated_real_cost_total", "assumed_monetary_cost_total", "proxy_late_demand_penalty", "proxy_customer_dissatisfaction_penalty", "proxy_capacity_overload_penalty", "proxy_maintenance_conflict_penalty", "proxy_breakdown_risk_penalty", "proxy_wip_shortage_penalty", "proxy_wip_overflow_penalty", "proxy_bottleneck_queue_penalty", "proxy_underutilization_penalty", "infeasibility_penalty", "review_required_penalty", "total_real_cost", "total_proxy_penalty", "total_advisory_schedule_score", "cost_basis", "cost_confidence", "assumption_flag", "scheduled_processing_minutes", "scheduled_setup_minutes", "scheduled_labor_minutes", "unscheduled_quantity", "scheduled_cost_calculation_basis", "unscheduled_penalty_calculation_basis", "source_phase", "advisory_only_flag"])


def _empty_recommendations() -> pd.DataFrame:
    return pd.DataFrame(columns=["recommendation_id", "planning_run_id", "alternative_id", "alternative_type", "recommendation_rank", "recommendation_status", "recommendation_summary", "demand_coverage_pct", "total_real_cost", "validated_real_cost_total", "assumed_monetary_cost_total", "total_proxy_penalty", "total_advisory_schedule_score", "main_benefit", "main_risk", "remaining_blocker_summary", "recommended_manager_action", "implementation_readiness_status", "auto_action_allowed", "advisory_only_flag"])


def _empty_review() -> pd.DataFrame:
    return pd.DataFrame(columns=["review_item_id", "planning_run_id", "alternative_id", "schedule_candidate_id", "finished_sku", "operation_id", "issue_type", "issue_severity", "issue_description", "recommended_review_action", "auto_action_allowed", "advisory_only_flag"])


def _empty_operation_segments() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "alternative_id", "operation_segment_id", "schedule_candidate_id", "finished_sku", "operation_id", "operation_name", "segment_sequence", "requested_operation_qty", "quantity_available_from_predecessors", "quantity_supported_before_capacity", "scheduling_target_qty", "segment_scheduled_qty", "cumulative_scheduled_qty", "remaining_unscheduled_qty", "buffer_capacity_before_production", "buffer_balance_before_production", "available_buffer_space_qty", "buffer_supported_output_qty", "buffer_blocked_output_qty", "allowed_buffer_capacity_qty", "overflow_policy", "buffer_capacity_status", "buffer_capacity_blocker_reason", "buffer_check_datetime", "projected_balance_at_completion", "projected_space_at_completion", "buffer_release_datetime", "buffer_delay_minutes", "buffer_reservation_qty", "buffer_reservation_status", "buffer_search_attempt_count", "proposed_schedule_date", "proposed_shift_id", "proposed_window_id", "proposed_start_datetime", "proposed_end_datetime", "workstation_id", "machine_id", "labor_skill_id", "processing_minutes_per_unit", "segment_processing_minutes", "segment_setup_minutes", "segment_total_minutes", "setup_applied_flag", "parallel_capacity_applied_flag", "effective_parallel_lane_count", "parallel_lane_id", "assigned_machine_unit_ids", "assigned_labor_unit_ids", "required_machine_count", "required_worker_count", "workstation_parallel_authorized_flag", "labor_parallel_authorized_flag", "resource_bundle_status", "continuation_resource_bundle_changed_flag", "segment_predecessor_ready_datetime", "input_quantity_availability_datetime", "resource_reserved_for_supported_qty_flag", "segment_capacity_status", "segment_maintenance_status", "segment_schedule_status", "advisory_only_flag"])


def _empty_quantity_flow() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "alternative_id", "schedule_candidate_id", "finished_sku", "operation_id", "operation_name", "predecessor_operation_id", "direct_input_wip_item_id", "direct_input_wip_buffer_id", "required_input_qty_per_output_unit", "quantity_ratio_basis", "requested_output_qty", "predecessor_completed_qty_available", "starting_accepted_wip_available", "advisory_wip_produced_available", "advisory_wip_already_drawn", "total_input_qty_available", "maximum_supported_output_qty", "scheduled_output_qty", "unscheduled_output_qty", "quantity_flow_status", "quantity_balance_check", "quantity_balance_status", "advisory_only_flag"])


def _empty_shadow_wip() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "alternative_id", "shadow_wip_event_id", "event_sequence", "event_datetime",
        "lot_id", "lot_availability_datetime", "lot_selection_method", "lot_beginning_qty",
        "lot_drawn_qty", "lot_ending_qty", "shelf_life_controlled_flag", "shelf_life_hours",
        "expiration_datetime", "schedule_candidate_id", "operation_segment_id", "finished_sku",
        "wip_item_id", "wip_buffer_id", "producer_operation_id", "consumer_operation_id",
        "shadow_event_type", "shadow_beginning_qty", "advisory_produced_qty", "advisory_drawn_qty",
        "advisory_blocked_qty", "shadow_ending_qty", "buffer_max_qty", "buffer_overflow_qty",
        "shadow_balance_status", "note_no_actual_wip_consumption_flag", "advisory_only_flag",
    ])


def _empty_maintenance_window_check() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "alternative_id", "machine_id", "workstation_id", "maintenance_plan_id", "production_operation_segment_id", "production_start_datetime", "production_end_datetime", "maintenance_window_id", "maintenance_start_datetime", "maintenance_end_datetime", "maintenance_window_source", "maintenance_window_selected_flag", "dated_overlap_flag", "machine_state_unavailable_flag", "maintenance_risk_level", "maintenance_window_check_status", "maintenance_avoidance_applied_flag", "maintenance_avoidance_evidence", "note_no_maintenance_order_created_flag", "advisory_only_flag"])


if __name__ == "__main__":
    outputs = build_schedule_alternative_outputs()
    print(f"Schedule alternative count: {len(outputs[0])}")
    print(f"Operation detail rows: {len(outputs[1])}")
    print(f"Validation rows: {len(outputs[-1])}")
