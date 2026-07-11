"""Build advisory WIP-aware production schedule feasibility outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PHASE4_DIR / "outputs"

SCHEDULE_CANDIDATES_FILE = OUTPUT_DIR / "phase4_production_schedule_candidates.csv"
SCHEDULE_DETAIL_FILE = OUTPUT_DIR / "phase4_operation_schedule_candidate_detail.csv"
CAPACITY_CHECK_FILE = OUTPUT_DIR / "phase4_production_schedule_capacity_check.csv"
MATERIAL_READINESS_FILE = OUTPUT_DIR / "phase4_production_schedule_material_readiness.csv"
WIP_ITEM_MASTER_FILE = OUTPUT_DIR / "phase4_wip_item_master.csv"
WIP_FLOW_MAP_FILE = OUTPUT_DIR / "phase4_wip_operation_flow_map.csv"
WIP_BATCH_LEDGER_FILE = OUTPUT_DIR / "phase4_wip_batch_ledger.csv"
WIP_BUFFER_STATUS_FILE = OUTPUT_DIR / "phase4_wip_buffer_status.csv"
WIP_QUALITY_STATUS_FILE = OUTPUT_DIR / "phase4_wip_quality_status.csv"
WIP_CONTINUITY_FILE = OUTPUT_DIR / "phase4_wip_line_continuity_analysis.csv"
ROUTING_GRAPH_NODES_FILE = OUTPUT_DIR / "phase4_routing_graph_nodes.csv"
ROUTING_GRAPH_EDGES_FILE = OUTPUT_DIR / "phase4_routing_graph_edges.csv"
CRITICAL_PATH_FILE = OUTPUT_DIR / "phase4_critical_path_by_product.csv"
SLACK_FILE = OUTPUT_DIR / "phase4_operation_slack_analysis.csv"
BOTTLENECK_FILE = OUTPUT_DIR / "phase4_bottleneck_visibility_summary.csv"
QUEUE_RISK_FILE = OUTPUT_DIR / "phase4_queue_risk_summary.csv"
MAINTENANCE_SCHEDULE_FILE = OUTPUT_DIR / "phase4_maintenance_schedule_feasibility_context.csv"
MAINTENANCE_IMPACT_FILE = OUTPUT_DIR / "phase4_maintenance_production_impact_context.csv"

WIP_AWARE_FEASIBILITY_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_aware_schedule_feasibility.csv"
WIP_SUPPLY_DEMAND_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_supply_demand_balance.csv"
WIP_BUFFER_IMPACT_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_buffer_impact_on_schedule.csv"
WIP_CONTINUITY_RECOMMENDATIONS_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_based_continuity_recommendations.csv"
WIP_MAINTENANCE_OPPORTUNITY_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_maintenance_opportunity_analysis.csv"
WIP_AWARE_REVIEW_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_aware_schedule_manager_review_queue.csv"
WIP_AWARE_VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_aware_schedule_validation.csv"

SOURCE_PHASE = "PHASE4_STEP8D_WIP_AWARE_SCHEDULE_FEASIBILITY"
NO_WIP = ""

VALID_WIP_AWARE_STATUS = {
    "WIP_SUPPORTED_FEASIBLE_CANDIDATE",
    "WIP_PARTIALLY_SUPPORTS_CANDIDATE",
    "WIP_BUFFER_CAN_ABSORB_UPSTREAM_PRODUCTION",
    "WIP_SHORTAGE_BLOCKED",
    "WIP_BUFFER_FULL_BLOCKED",
    "CAPACITY_STILL_BLOCKED",
    "MAINTENANCE_STILL_BLOCKED",
    "MULTI_BLOCKED_AFTER_WIP",
    "REVIEW_REQUIRED",
}
VALID_BALANCE_STATUS = {
    "WIP_FULLY_COVERS_OPERATION",
    "WIP_PARTIALLY_COVERS_OPERATION",
    "WIP_SHORTAGE",
    "NO_WIP_REQUIRED_FIRST_OPERATION",
    "REVIEW_REQUIRED",
}
VALID_BUFFER_IMPACT_STATUS = {
    "BUFFER_PROTECTS_DOWNSTREAM",
    "BUFFER_CAN_ABSORB_UPSTREAM",
    "BUFFER_BELOW_TARGET_BUILD_WIP",
    "BUFFER_FULL_STOP_UPSTREAM",
    "BUFFER_INSUFFICIENT",
    "REVIEW_REQUIRED",
}
VALID_RECOMMENDED_ACTION = {
    "USE_ACCEPTED_WIP_TO_SUPPORT_DOWNSTREAM",
    "BUILD_WIP_TO_TARGET",
    "HOLD_UPSTREAM_BECAUSE_BUFFER_FULL",
    "CONTINUE_UPSTREAM_PRODUCTION_TO_BUFFER",
    "KEEP_BLOCKED_REVIEW_REQUIRED",
    "REVIEW_REQUIRED",
}
VALID_MAINT_OPPORTUNITY_STATUS = {
    "MAINTENANCE_OPPORTUNITY_AFTER_WIP_TARGET",
    "NO_OPPORTUNITY_BUFFER_BELOW_TARGET",
    "NO_OPPORTUNITY_DOWNSTREAM_NOT_PROTECTED",
    "NO_OPPORTUNITY_MACHINE_STILL_NEEDED",
    "REVIEW_REQUIRED",
}


def build_wip_aware_schedule_feasibility_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    checks: list[dict] = []
    frames = {
        "candidates": _load_csv(SCHEDULE_CANDIDATES_FILE, "phase4_production_schedule_candidates", checks),
        "details": _load_csv(SCHEDULE_DETAIL_FILE, "phase4_operation_schedule_candidate_detail", checks),
        "capacity": _load_csv(CAPACITY_CHECK_FILE, "phase4_production_schedule_capacity_check", checks),
        "material": _load_csv(MATERIAL_READINESS_FILE, "phase4_production_schedule_material_readiness", checks),
        "wip_items": _load_csv(WIP_ITEM_MASTER_FILE, "phase4_wip_item_master", checks),
        "flow_map": _load_csv(WIP_FLOW_MAP_FILE, "phase4_wip_operation_flow_map", checks),
        "ledger": _load_csv(WIP_BATCH_LEDGER_FILE, "phase4_wip_batch_ledger", checks),
        "buffer_status": _load_csv(WIP_BUFFER_STATUS_FILE, "phase4_wip_buffer_status", checks),
        "quality": _load_csv(WIP_QUALITY_STATUS_FILE, "phase4_wip_quality_status", checks),
        "continuity": _load_csv(WIP_CONTINUITY_FILE, "phase4_wip_line_continuity_analysis", checks),
        "nodes": _load_csv(ROUTING_GRAPH_NODES_FILE, "phase4_routing_graph_nodes", checks),
        "edges": _load_csv(ROUTING_GRAPH_EDGES_FILE, "phase4_routing_graph_edges", checks),
        "critical_path": _load_csv(CRITICAL_PATH_FILE, "phase4_critical_path_by_product", checks),
        "slack": _load_csv(SLACK_FILE, "phase4_operation_slack_analysis", checks),
        "bottleneck": _load_csv(BOTTLENECK_FILE, "phase4_bottleneck_visibility_summary", checks),
        "queue": _load_csv(QUEUE_RISK_FILE, "phase4_queue_risk_summary", checks),
        "maintenance_schedule": _load_csv(MAINTENANCE_SCHEDULE_FILE, "phase4_maintenance_schedule_feasibility_context", checks),
        "maintenance_impact": _load_csv(MAINTENANCE_IMPACT_FILE, "phase4_maintenance_production_impact_context", checks),
    }
    if all(frame is not None for frame in frames.values()):
        feasibility = _build_feasibility(frames)
        balance = _build_supply_demand_balance(feasibility)
        buffer_impact = _build_buffer_impact(frames, feasibility)
        recommendations = _build_continuity_recommendations(frames, feasibility)
        maintenance_opportunity = _build_maintenance_opportunity(frames, feasibility)
        review = _build_review_queue(feasibility, balance, buffer_impact, maintenance_opportunity)
        _validate_outputs(frames, feasibility, balance, buffer_impact, recommendations, maintenance_opportunity, review, checks)
    else:
        feasibility = _empty_feasibility()
        balance = _empty_balance()
        buffer_impact = _empty_buffer_impact()
        recommendations = _empty_recommendations()
        maintenance_opportunity = _empty_maintenance_opportunity()
        review = _empty_review()

    _check_no_forbidden_outputs(checks)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    feasibility.to_csv(WIP_AWARE_FEASIBILITY_OUTPUT_FILE, index=False)
    balance.to_csv(WIP_SUPPLY_DEMAND_OUTPUT_FILE, index=False)
    buffer_impact.to_csv(WIP_BUFFER_IMPACT_OUTPUT_FILE, index=False)
    recommendations.to_csv(WIP_CONTINUITY_RECOMMENDATIONS_OUTPUT_FILE, index=False)
    maintenance_opportunity.to_csv(WIP_MAINTENANCE_OPPORTUNITY_OUTPUT_FILE, index=False)
    review.to_csv(WIP_AWARE_REVIEW_OUTPUT_FILE, index=False)
    validation.to_csv(WIP_AWARE_VALIDATION_OUTPUT_FILE, index=False)
    return feasibility, balance, buffer_impact, recommendations, maintenance_opportunity, review, validation


def _build_feasibility(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    candidates = frames["candidates"]
    details = frames["details"]
    flow = frames["flow_map"]
    ledger = frames["ledger"]
    buffers = frames["buffer_status"]
    capacity = frames["capacity"]
    material = frames["material"]
    planning_run_id = _planning_run_id(frames)

    cand_by_id = _index_by(candidates, "schedule_candidate_id")
    capacity_by_key = {
        (str(row["schedule_candidate_id"]), str(row["operation_id"])): row.to_dict()
        for _, row in capacity.iterrows()
    }
    material_by_candidate = material.groupby("schedule_candidate_id", dropna=False).agg(
        original_material_readiness_status=("material_readiness_status", _worst_material_status),
        material_blocker_flag=("material_blocker_flag", lambda s: bool(_to_bool(s).any())),
    ).to_dict("index")
    accepted_by_item = ledger.groupby("wip_item_id", dropna=False)["available_accepted_qty"].sum().to_dict()
    buffer_by_item = {str(row["wip_item_id"]): row.to_dict() for _, row in buffers.iterrows()}
    input_flow = {}
    for _, row in flow.iterrows():
        input_flow.setdefault((str(row["finished_sku"]), str(row["consumed_by_operation_id"])), []).append(row.to_dict())
    output_flow = {}
    for _, row in flow.iterrows():
        output_flow.setdefault((str(row["finished_sku"]), str(row["produced_by_operation_id"])), []).append(row.to_dict())

    rows = []
    for _, detail in details.iterrows():
        candidate_id = str(detail["schedule_candidate_id"])
        op_id = str(detail["operation_id"])
        sku = str(detail["finished_sku"])
        candidate = cand_by_id.get(candidate_id, {})
        candidate_inputs = input_flow.get((sku, op_id), [])
        if not candidate_inputs:
            candidate_inputs = [None]
        outputs = output_flow.get((sku, op_id), [])
        output_wip = str(outputs[0]["wip_item_id"]) if outputs else NO_WIP
        cap_row = capacity_by_key.get((candidate_id, op_id), {})
        material_row = material_by_candidate.get(candidate_id, {})
        for input_row in candidate_inputs:
            input_wip = str(input_row["wip_item_id"]) if input_row else NO_WIP
            related_buffer = _buffer_id_for_wip(input_wip, input_row, buffer_by_item)
            buffer_row = buffer_by_item.get(input_wip, {})
            accepted_qty = _num_value(accepted_by_item.get(input_wip, 0.0)) if input_wip else 0.0
            required_qty = _num_value(candidate.get("planned_production_qty", 0.0)) if input_wip else 0.0
            shortage = max(required_qty - accepted_qty, 0.0)
            available_capacity = _num_value(buffer_row.get("available_buffer_capacity_qty", 0.0))
            buffer_status = str(buffer_row.get("buffer_status", "REVIEW_REQUIRED")) if input_wip else ""
            downstream_resume = bool(input_wip and accepted_qty > 0)
            upstream_build = bool(output_wip and _output_buffer_capacity(output_wip, buffer_by_item) > 0)
            original_status = str(candidate.get("schedule_candidate_status", "REVIEW_REQUIRED"))
            original_material = str(material_row.get("original_material_readiness_status", candidate.get("material_readiness_status", "REVIEW_REQUIRED")))
            original_capacity = str(cap_row.get("capacity_feasibility_status", candidate.get("capacity_feasibility_status", "REVIEW_REQUIRED")))
            original_maintenance = str(candidate.get("maintenance_feasibility_status", "REVIEW_REQUIRED"))
            material_blocker = bool(material_row.get("material_blocker_flag", False)) or original_status == "MATERIAL_BLOCKED"
            capacity_blocker = _is_capacity_blocked(original_capacity) or original_status == "CAPACITY_BLOCKED"
            maintenance_blocker = _is_maintenance_blocked(original_maintenance) or original_status == "MAINTENANCE_BLOCKED"
            wip_blocker = bool(input_wip and shortage > 0 and not downstream_resume)
            wip_reduces = bool(input_wip and downstream_resume and (material_blocker or "BLOCKED" in original_status or original_status == "REVIEW_REQUIRED"))
            if wip_reduces and not capacity_blocker and not maintenance_blocker and shortage <= 0:
                material_blocker = False
            status = _wip_aware_status(
                has_input=bool(input_wip),
                accepted_qty=accepted_qty,
                required_qty=required_qty,
                shortage=shortage,
                buffer_status=buffer_status,
                upstream_build=upstream_build,
                capacity_blocker=capacity_blocker,
                maintenance_blocker=maintenance_blocker,
                material_blocker=material_blocker,
                wip_blocker=wip_blocker,
            )
            score = _score_feasibility(status, accepted_qty, required_qty, available_capacity, capacity_blocker, maintenance_blocker)
            rows.append({
                "planning_run_id": planning_run_id,
                "schedule_candidate_id": candidate_id,
                "finished_sku": sku,
                "operation_id": op_id,
                "operation_name": detail.get("operation_name", ""),
                "workstation_id": detail.get("workstation_id", ""),
                "machine_id": detail.get("machine_id", ""),
                "candidate_schedule_period": detail.get("candidate_schedule_period", candidate.get("candidate_schedule_period", "")),
                "candidate_schedule_day": detail.get("candidate_schedule_day", candidate.get("candidate_schedule_day", "")),
                "candidate_schedule_shift": detail.get("candidate_schedule_shift", candidate.get("candidate_schedule_shift", "")),
                "original_schedule_candidate_status": original_status,
                "original_material_readiness_status": original_material,
                "original_capacity_feasibility_status": original_capacity,
                "original_maintenance_feasibility_status": original_maintenance,
                "required_input_wip_item_id": input_wip,
                "output_wip_item_id": output_wip,
                "related_wip_buffer_id": related_buffer,
                "accepted_wip_available_qty": accepted_qty,
                "required_wip_qty": required_qty,
                "wip_shortage_qty": shortage,
                "available_buffer_capacity_qty": available_capacity,
                "downstream_can_resume_from_wip_flag": downstream_resume,
                "upstream_can_build_wip_flag": upstream_build,
                "wip_reduces_schedule_blocker_flag": wip_reduces,
                "remaining_material_blocker_flag": material_blocker and not wip_reduces,
                "remaining_capacity_blocker_flag": capacity_blocker,
                "remaining_maintenance_blocker_flag": maintenance_blocker,
                "remaining_wip_blocker_flag": wip_blocker,
                "wip_aware_schedule_status": status,
                "wip_aware_feasibility_score": score,
                "source_phase": SOURCE_PHASE,
                "advisory_only_flag": True,
            })
    return pd.DataFrame(rows, columns=_empty_feasibility().columns)


def _build_supply_demand_balance(feasibility: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in feasibility.iterrows():
        input_wip = str(row["required_input_wip_item_id"])
        required = _num_value(row["required_wip_qty"])
        accepted = _num_value(row["accepted_wip_available_qty"])
        shortage = max(required - accepted, 0.0)
        surplus = max(accepted - required, 0.0)
        if not input_wip:
            status = "NO_WIP_REQUIRED_FIRST_OPERATION"
            coverage = 0.0
        elif required <= 0:
            status = "REVIEW_REQUIRED"
            coverage = 0.0
        elif accepted >= required:
            status = "WIP_FULLY_COVERS_OPERATION"
            coverage = 100.0
        elif accepted > 0:
            status = "WIP_PARTIALLY_COVERS_OPERATION"
            coverage = accepted / required * 100
        else:
            status = "WIP_SHORTAGE"
            coverage = 0.0
        rows.append({
            "planning_run_id": row["planning_run_id"],
            "finished_sku": row["finished_sku"],
            "operation_id": row["operation_id"],
            "operation_name": row["operation_name"],
            "required_input_wip_item_id": input_wip,
            "wip_buffer_id": row["related_wip_buffer_id"],
            "accepted_wip_available_qty": accepted,
            "required_wip_qty": required,
            "wip_surplus_qty": surplus,
            "wip_shortage_qty": shortage,
            "wip_coverage_pct": coverage,
            "downstream_can_consume_wip_flag": bool(input_wip and accepted > 0),
            "note_no_wip_consumption_flag": True,
            "balance_status": status,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_empty_balance().columns)


def _build_buffer_impact(frames: dict[str, pd.DataFrame], feasibility: pd.DataFrame) -> pd.DataFrame:
    buffers = frames["buffer_status"]
    planning_run_id = _planning_run_id(frames)
    rows = []
    for _, buf in buffers.iterrows():
        buffer_id = str(buf["wip_buffer_id"])
        impacted = feasibility[feasibility["related_wip_buffer_id"].astype(str) == buffer_id]
        reduced_count = int(_to_bool(impacted.get("wip_reduces_schedule_blocker_flag", pd.Series(dtype=bool))).sum()) if not impacted.empty else 0
        remaining_count = int((_to_bool(impacted.get("remaining_capacity_blocker_flag", pd.Series(dtype=bool))) | _to_bool(impacted.get("remaining_maintenance_blocker_flag", pd.Series(dtype=bool))) | _to_bool(impacted.get("remaining_wip_blocker_flag", pd.Series(dtype=bool)))).sum()) if not impacted.empty else 0
        accepted = _num_value(buf.get("accepted_wip_qty", 0.0))
        available = _num_value(buf.get("available_buffer_capacity_qty", 0.0))
        status = str(buf.get("buffer_status", "REVIEW_REQUIRED"))
        if status in {"FULL", "OVERFLOW_RISK"}:
            impact = "BUFFER_FULL_STOP_UPSTREAM"
        elif accepted > 0:
            impact = "BUFFER_PROTECTS_DOWNSTREAM"
        elif status == "BELOW_MINIMUM" and available > 0:
            impact = "BUFFER_BELOW_TARGET_BUILD_WIP"
        elif available > 0:
            impact = "BUFFER_CAN_ABSORB_UPSTREAM"
        else:
            impact = "BUFFER_INSUFFICIENT"
        rows.append({
            "planning_run_id": planning_run_id,
            "wip_buffer_id": buffer_id,
            "wip_buffer_name": buf.get("wip_buffer_name", ""),
            "wip_item_id": buf.get("wip_item_id", ""),
            "linked_workstation_id": buf.get("linked_workstation_id", ""),
            "current_wip_qty": _num_value(buf.get("current_wip_qty", 0)),
            "accepted_wip_qty": accepted,
            "blocked_wip_qty": _num_value(buf.get("blocked_wip_qty", 0)),
            "min_buffer_qty": _num_value(buf.get("min_buffer_qty", 0)),
            "target_buffer_qty": _num_value(buf.get("target_buffer_qty", 0)),
            "max_buffer_qty": _num_value(buf.get("max_buffer_qty", 0)),
            "available_buffer_capacity_qty": available,
            "buffer_utilization_pct": _num_value(buf.get("buffer_utilization_pct", 0)),
            "buffer_status": status,
            "upstream_can_continue_flag": _bool_value(buf.get("upstream_can_continue_flag", False)),
            "downstream_can_resume_from_wip_flag": accepted > 0,
            "impacted_schedule_candidate_count": int(impacted["schedule_candidate_id"].nunique()) if not impacted.empty else 0,
            "schedule_blockers_reduced_count": reduced_count,
            "schedule_blockers_remaining_count": remaining_count,
            "buffer_schedule_impact_status": impact,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_empty_buffer_impact().columns)


def _build_continuity_recommendations(frames: dict[str, pd.DataFrame], feasibility: pd.DataFrame) -> pd.DataFrame:
    edges = frames["edges"]
    edge_by_to = {(str(row["finished_sku"]), str(row["to_operation_id"])): str(row["from_operation_id"]) for _, row in edges.iterrows()}
    op_names = {str(row["operation_id"]): str(row["operation_name"]) for _, row in frames["nodes"].iterrows()}
    rows = []
    index = 1
    for _, row in feasibility.iterrows():
        input_wip = str(row["required_input_wip_item_id"])
        if not input_wip and not _bool_value(row["upstream_can_build_wip_flag"]):
            continue
        capacity_blocked = _bool_value(row["remaining_capacity_blocker_flag"])
        maintenance_blocked = _bool_value(row["remaining_maintenance_blocker_flag"])
        wip_blocked = _bool_value(row["remaining_wip_blocker_flag"])
        if _bool_value(row["downstream_can_resume_from_wip_flag"]) and _bool_value(row["wip_reduces_schedule_blocker_flag"]):
            action = "USE_ACCEPTED_WIP_TO_SUPPORT_DOWNSTREAM"
            effect = "REDUCES_BLOCKER"
            reason = "Accepted WIP is available for the downstream operation, but capacity and maintenance blockers remain visible if present."
        elif wip_blocked and _bool_value(row["upstream_can_build_wip_flag"]):
            action = "BUILD_WIP_TO_TARGET"
            effect = "PARTIALLY_REDUCES_BLOCKER"
            reason = "Input WIP is short, while an upstream buffer can absorb useful production."
        elif str(row["wip_aware_schedule_status"]) == "WIP_BUFFER_FULL_BLOCKED":
            action = "HOLD_UPSTREAM_BECAUSE_BUFFER_FULL"
            effect = "PREVENTS_OVERPRODUCTION"
            reason = "The related WIP buffer is full or at overflow risk."
        elif _bool_value(row["upstream_can_build_wip_flag"]):
            action = "CONTINUE_UPSTREAM_PRODUCTION_TO_BUFFER"
            effect = "PARTIALLY_REDUCES_BLOCKER" if capacity_blocked or maintenance_blocked else "REDUCES_BLOCKER"
            reason = "The operation can produce useful output WIP into available buffer capacity."
        else:
            action = "KEEP_BLOCKED_REVIEW_REQUIRED"
            effect = "DOES_NOT_REDUCE_BLOCKER"
            reason = "WIP does not reduce the remaining blocker."
        rows.append({
            "recommendation_id": f"WIPREC-{index:04d}",
            "planning_run_id": row["planning_run_id"],
            "finished_sku": row["finished_sku"],
            "schedule_candidate_id": row["schedule_candidate_id"],
            "blocking_operation_id": row["operation_id"],
            "blocking_operation_name": row["operation_name"],
            "blocking_reason": _blocking_reason(row),
            "upstream_operation_id": edge_by_to.get((str(row["finished_sku"]), str(row["operation_id"])), ""),
            "upstream_operation_name": op_names.get(edge_by_to.get((str(row["finished_sku"]), str(row["operation_id"])), ""), ""),
            "downstream_operation_id": row["operation_id"],
            "downstream_operation_name": row["operation_name"],
            "wip_item_id": input_wip or row["output_wip_item_id"],
            "wip_buffer_id": row["related_wip_buffer_id"],
            "current_accepted_wip_qty": row["accepted_wip_available_qty"],
            "target_buffer_qty": _target_for_buffer(frames["buffer_status"], row["related_wip_buffer_id"]),
            "available_buffer_capacity_qty": row["available_buffer_capacity_qty"],
            "recommended_action": action,
            "recommendation_reason": reason,
            "expected_schedule_effect": effect,
            "auto_action_allowed": False,
            "advisory_only_flag": True,
        })
        index += 1
    return pd.DataFrame(rows, columns=_empty_recommendations().columns)


def _build_maintenance_opportunity(frames: dict[str, pd.DataFrame], feasibility: pd.DataFrame) -> pd.DataFrame:
    rows = []
    seen = set()
    for _, row in feasibility.iterrows():
        output_wip = str(row["output_wip_item_id"])
        if not output_wip:
            continue
        buffer_row = _buffer_for_wip(frames["buffer_status"], output_wip)
        if not buffer_row:
            continue
        key = (str(row["workstation_id"]), str(row["machine_id"]), str(row["operation_id"]), output_wip)
        if key in seen:
            continue
        seen.add(key)
        accepted = _num_value(buffer_row.get("accepted_wip_qty", 0))
        target = _num_value(buffer_row.get("target_buffer_qty", 0))
        max_qty = _num_value(buffer_row.get("max_buffer_qty", 0))
        can_pause = accepted >= target and target > 0
        downstream_protected = accepted > 0
        related_maintenance = _bool_value(row["remaining_maintenance_blocker_flag"])
        if can_pause and downstream_protected:
            opportunity = True
            status = "MAINTENANCE_OPPORTUNITY_AFTER_WIP_TARGET"
            reason = "Accepted WIP is at or above target, so upstream pause can be reviewed as a maintenance opportunity."
        elif accepted < target:
            opportunity = False
            status = "NO_OPPORTUNITY_BUFFER_BELOW_TARGET"
            reason = "Buffer is below target; build WIP before considering an upstream maintenance opportunity."
        elif not downstream_protected:
            opportunity = False
            status = "NO_OPPORTUNITY_DOWNSTREAM_NOT_PROTECTED"
            reason = "Downstream operation is not protected by accepted WIP."
        else:
            opportunity = False
            status = "NO_OPPORTUNITY_MACHINE_STILL_NEEDED"
            reason = "Machine still appears needed for WIP continuity."
        rows.append({
            "planning_run_id": row["planning_run_id"],
            "workstation_id": row["workstation_id"],
            "machine_id": row["machine_id"],
            "operation_id": row["operation_id"],
            "operation_name": row["operation_name"],
            "wip_item_id": output_wip,
            "wip_buffer_id": buffer_row.get("wip_buffer_id", ""),
            "current_accepted_wip_qty": accepted,
            "target_buffer_qty": target,
            "max_buffer_qty": max_qty,
            "downstream_can_resume_from_wip_flag": downstream_protected,
            "upstream_can_pause_after_target_flag": can_pause,
            "maintenance_opportunity_flag": opportunity,
            "maintenance_opportunity_reason": reason,
            "related_maintenance_blocker_flag": related_maintenance,
            "advisory_maintenance_window_candidate_status": status,
            "note_no_maintenance_order_created_flag": True,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    if not rows:
        # Keep the required output non-empty with a review row if no operation has output WIP.
        rows.append({
            "planning_run_id": _planning_run_id(frames),
            "workstation_id": "",
            "machine_id": "",
            "operation_id": "",
            "operation_name": "",
            "wip_item_id": "",
            "wip_buffer_id": "",
            "current_accepted_wip_qty": 0.0,
            "target_buffer_qty": 0.0,
            "max_buffer_qty": 0.0,
            "downstream_can_resume_from_wip_flag": False,
            "upstream_can_pause_after_target_flag": False,
            "maintenance_opportunity_flag": False,
            "maintenance_opportunity_reason": "No output WIP buffers were available for maintenance opportunity analysis.",
            "related_maintenance_blocker_flag": False,
            "advisory_maintenance_window_candidate_status": "REVIEW_REQUIRED",
            "note_no_maintenance_order_created_flag": True,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_empty_maintenance_opportunity().columns)


def _build_review_queue(feasibility: pd.DataFrame, balance: pd.DataFrame, buffer_impact: pd.DataFrame, maintenance_opportunity: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def add(candidate_id: str, sku: str, operation_id: str, wip_item_id: str, wip_buffer_id: str, issue_type: str, severity: str, description: str, action: str) -> None:
        rows.append({
            "review_item_id": f"WIP8D-REV-{len(rows)+1:04d}",
            "planning_run_id": _first_value(feasibility, "planning_run_id"),
            "schedule_candidate_id": candidate_id,
            "finished_sku": sku,
            "operation_id": operation_id,
            "wip_item_id": wip_item_id,
            "wip_buffer_id": wip_buffer_id,
            "issue_type": issue_type,
            "issue_severity": severity,
            "issue_description": description,
            "recommended_review_action": action,
            "auto_action_allowed": False,
            "advisory_only_flag": True,
        })

    for _, row in feasibility.iterrows():
        if _bool_value(row["remaining_wip_blocker_flag"]):
            add(row["schedule_candidate_id"], row["finished_sku"], row["operation_id"], row["required_input_wip_item_id"], row["related_wip_buffer_id"], "WIP_SHORTAGE_SCHEDULE_RISK", "HIGH", "Accepted WIP does not cover the downstream operation requirement.", "REVIEW_WIP_BUFFER_BUILD_PLAN")
        if str(row["wip_aware_schedule_status"]) == "WIP_BUFFER_FULL_BLOCKED":
            add(row["schedule_candidate_id"], row["finished_sku"], row["operation_id"], row["required_input_wip_item_id"], row["related_wip_buffer_id"], "WIP_BUFFER_FULL_SCHEDULE_RISK", "HIGH", "Related buffer is full or at overflow risk; upstream production should be reviewed.", "REVIEW_BUFFER_CAPACITY")
        if str(row["wip_aware_schedule_status"]) == "WIP_PARTIALLY_SUPPORTS_CANDIDATE":
            add(row["schedule_candidate_id"], row["finished_sku"], row["operation_id"], row["required_input_wip_item_id"], row["related_wip_buffer_id"], "WIP_PARTIAL_SUPPORT_REVIEW", "MEDIUM", "Accepted WIP partially supports this candidate but does not fully cover required quantity.", "REVIEW_WIP_SHORTAGE")
        if _bool_value(row["remaining_capacity_blocker_flag"]):
            add(row["schedule_candidate_id"], row["finished_sku"], row["operation_id"], row["required_input_wip_item_id"], row["related_wip_buffer_id"], "CAPACITY_STILL_BLOCKED_AFTER_WIP", "CRITICAL", "Capacity remains blocked after WIP is considered.", "REVIEW_CAPACITY_CONSTRAINT")
        if _bool_value(row["remaining_maintenance_blocker_flag"]):
            add(row["schedule_candidate_id"], row["finished_sku"], row["operation_id"], row["required_input_wip_item_id"], row["related_wip_buffer_id"], "MAINTENANCE_STILL_BLOCKED_AFTER_WIP", "CRITICAL", "Maintenance remains blocked after WIP is considered.", "REVIEW_MAINTENANCE_BLOCKER")
        if not str(row["required_input_wip_item_id"]) and _bool_value(row["remaining_material_blocker_flag"]):
            add(row["schedule_candidate_id"], row["finished_sku"], row["operation_id"], "", "", "WIP_DATA_REVIEW", "MEDIUM", "Candidate has a material-style blocker but no input WIP exists for this operation.", "REVIEW_MATERIAL_AND_WIP_MAPPING")
    for _, row in buffer_impact.iterrows():
        if str(row["buffer_schedule_impact_status"]) == "BUFFER_FULL_STOP_UPSTREAM":
            add("", "", "", row["wip_item_id"], row["wip_buffer_id"], "WIP_BUFFER_FULL_SCHEDULE_RISK", "HIGH", "WIP buffer is full or at overflow risk.", "REVIEW_BUFFER_OVERFLOW_POLICY")
    for _, row in maintenance_opportunity.iterrows():
        if _bool_value(row["maintenance_opportunity_flag"]):
            add("", "", row["operation_id"], row["wip_item_id"], row["wip_buffer_id"], "WIP_MAINTENANCE_OPPORTUNITY_REVIEW", "MEDIUM", "WIP buffer may allow advisory upstream maintenance review after target is reached.", "REVIEW_MAINTENANCE_OPPORTUNITY")
    if not rows:
        add("", "", "", "", "", "REVIEW_REQUIRED", "LOW", "No WIP-aware schedule review issues were generated.", "NO_ACTION_REQUIRED")
    return pd.DataFrame(rows, columns=_empty_review().columns)


def _validate_outputs(
    frames: dict[str, pd.DataFrame],
    feasibility: pd.DataFrame,
    balance: pd.DataFrame,
    buffer_impact: pd.DataFrame,
    recommendations: pd.DataFrame,
    maintenance_opportunity: pd.DataFrame,
    review: pd.DataFrame,
    checks: list[dict],
) -> None:
    outputs = {
        "wip_aware_schedule_feasibility": feasibility,
        "wip_supply_demand_balance": balance,
        "wip_buffer_impact_on_schedule": buffer_impact,
        "wip_based_continuity_recommendations": recommendations,
        "wip_maintenance_opportunity_analysis": maintenance_opportunity,
        "wip_aware_schedule_manager_review_queue": review,
    }
    for name, frame in outputs.items():
        _add_check(checks, f"{name}_not_empty", "PASS" if not frame.empty else "FAIL", f"{name} rows={len(frame)}", len(frame))
    required = {
        "feasibility": set(_empty_feasibility().columns),
        "balance": set(_empty_balance().columns),
        "buffer_impact": set(_empty_buffer_impact().columns),
        "recommendations": set(_empty_recommendations().columns),
        "maintenance_opportunity": set(_empty_maintenance_opportunity().columns),
        "review": set(_empty_review().columns),
    }
    actual = {
        "feasibility": feasibility,
        "balance": balance,
        "buffer_impact": buffer_impact,
        "recommendations": recommendations,
        "maintenance_opportunity": maintenance_opportunity,
        "review": review,
    }
    for name, columns in required.items():
        missing = sorted(columns.difference(actual[name].columns))
        _add_check(checks, f"{name}_required_columns", "PASS" if not missing else "FAIL", f"Missing columns: {missing}" if missing else "Required columns present.", len(missing))
    represented = set(frames["details"]["schedule_candidate_id"].astype(str)) <= set(feasibility["schedule_candidate_id"].astype(str))
    _add_check(checks, "step8b_candidates_represented", "PASS" if represented else "FAIL", "Step 8B operation candidates represented in WIP-aware feasibility.", len(feasibility))
    valid_wip = set(frames["wip_items"]["wip_item_id"].astype(str))
    valid_buffers = set(frames["buffer_status"]["wip_buffer_id"].astype(str))
    valid_ops = set(frames["nodes"]["operation_id"].astype(str))
    wip_refs = set(feasibility["required_input_wip_item_id"].dropna().astype(str)) | set(feasibility["output_wip_item_id"].dropna().astype(str))
    wip_refs.discard("")
    buffer_refs = set(feasibility["related_wip_buffer_id"].dropna().astype(str))
    buffer_refs.discard("")
    op_refs = set(feasibility["operation_id"].dropna().astype(str))
    _add_check(checks, "valid_wip_references", "PASS" if wip_refs <= valid_wip else "FAIL", f"Invalid WIP refs: {sorted(wip_refs - valid_wip)}", len(wip_refs - valid_wip))
    _add_check(checks, "valid_buffer_references", "PASS" if buffer_refs <= valid_buffers else "FAIL", f"Invalid buffer refs: {sorted(buffer_refs - valid_buffers)}", len(buffer_refs - valid_buffers))
    _add_check(checks, "valid_operation_references", "PASS" if op_refs <= valid_ops else "FAIL", f"Invalid operation refs: {sorted(op_refs - valid_ops)}", len(op_refs - valid_ops))
    for frame, columns, label in [
        (feasibility, ["accepted_wip_available_qty", "required_wip_qty", "wip_shortage_qty", "available_buffer_capacity_qty", "wip_aware_feasibility_score"], "feasibility"),
        (balance, ["accepted_wip_available_qty", "required_wip_qty", "wip_surplus_qty", "wip_shortage_qty", "wip_coverage_pct"], "balance"),
        (buffer_impact, ["current_wip_qty", "accepted_wip_qty", "blocked_wip_qty", "available_buffer_capacity_qty", "buffer_utilization_pct"], "buffer_impact"),
    ]:
        bad = _non_negative_bad_count(frame, columns)
        _add_check(checks, f"{label}_numeric_non_negative", "PASS" if bad == 0 else "FAIL", f"Bad numeric values={bad}", bad)
    resume_bad = feasibility[_to_bool(feasibility["downstream_can_resume_from_wip_flag"]) & (_num_series(feasibility, "accepted_wip_available_qty") <= 0)]
    _add_check(checks, "downstream_resume_requires_accepted_wip", "PASS" if resume_bad.empty else "FAIL", "Downstream resume flag requires accepted WIP.", len(resume_bad))
    full_bad = feasibility[_to_bool(feasibility["upstream_can_build_wip_flag"]) & (feasibility["wip_aware_schedule_status"].astype(str) == "WIP_BUFFER_FULL_BLOCKED")]
    _add_check(checks, "upstream_build_false_when_full", "PASS" if full_bad.empty else "FAIL", "Upstream build must not be true for full-buffer blocked rows.", len(full_bad))
    reduce_bad = feasibility[_to_bool(feasibility["wip_reduces_schedule_blocker_flag"]) & ~_to_bool(feasibility["downstream_can_resume_from_wip_flag"])]
    _add_check(checks, "wip_reduction_requires_resume", "PASS" if reduce_bad.empty else "FAIL", "WIP blocker reduction requires accepted WIP resume support.", len(reduce_bad))
    capacity_hidden = feasibility[_to_bool(feasibility["remaining_capacity_blocker_flag"]) & ~feasibility["wip_aware_schedule_status"].astype(str).isin(["CAPACITY_STILL_BLOCKED", "MULTI_BLOCKED_AFTER_WIP"])]
    maintenance_hidden = feasibility[_to_bool(feasibility["remaining_maintenance_blocker_flag"]) & ~feasibility["wip_aware_schedule_status"].astype(str).isin(["MAINTENANCE_STILL_BLOCKED", "MULTI_BLOCKED_AFTER_WIP"])]
    _add_check(checks, "capacity_blockers_not_hidden_by_wip", "PASS" if capacity_hidden.empty else "FAIL", "Capacity blockers remain visible after WIP.", len(capacity_hidden))
    _add_check(checks, "maintenance_blockers_not_hidden_by_wip", "PASS" if maintenance_hidden.empty else "FAIL", "Maintenance blockers remain visible after WIP.", len(maintenance_hidden))
    _add_check(checks, "valid_wip_aware_status", "PASS" if set(feasibility["wip_aware_schedule_status"].astype(str)) <= VALID_WIP_AWARE_STATUS else "FAIL", "WIP-aware status values valid.", len(feasibility))
    _add_check(checks, "valid_balance_status", "PASS" if set(balance["balance_status"].astype(str)) <= VALID_BALANCE_STATUS else "FAIL", "Balance status values valid.", len(balance))
    _add_check(checks, "valid_buffer_impact_status", "PASS" if set(buffer_impact["buffer_schedule_impact_status"].astype(str)) <= VALID_BUFFER_IMPACT_STATUS else "FAIL", "Buffer impact status values valid.", len(buffer_impact))
    _add_check(checks, "valid_recommendation_actions", "PASS" if set(recommendations["recommended_action"].astype(str)) <= VALID_RECOMMENDED_ACTION else "FAIL", "Recommendation action values valid.", len(recommendations))
    _add_check(checks, "valid_maintenance_opportunity_status", "PASS" if set(maintenance_opportunity["advisory_maintenance_window_candidate_status"].astype(str)) <= VALID_MAINT_OPPORTUNITY_STATUS else "FAIL", "Maintenance opportunity status values valid.", len(maintenance_opportunity))
    _add_check(checks, "no_wip_consumption", "PASS" if _all_true(balance, "note_no_wip_consumption_flag") else "FAIL", "No WIP consumption flag must be True.", len(balance))
    _add_check(checks, "no_maintenance_orders", "PASS" if _all_true(maintenance_opportunity, "note_no_maintenance_order_created_flag") else "FAIL", "No maintenance order flag must be True.", len(maintenance_opportunity))
    advisory_ok = all(_all_true(frame, "advisory_only_flag") for frame in outputs.values())
    _add_check(checks, "advisory_only_outputs", "PASS" if advisory_ok else "FAIL", "All Step 8D outputs are advisory-only.", len(outputs))
    _add_check(checks, "review_auto_action_disabled", "PASS" if _all_false(review, "auto_action_allowed") else "FAIL", "Review queue auto action must be False.", len(review))
    for path, name in [
        (OUTPUT_DIR / "phase4_routing_graph_validation.csv", "Step 8A routing graph validation"),
        (OUTPUT_DIR / "phase4_production_schedule_validation.csv", "Step 8B production schedule validation"),
        (OUTPUT_DIR / "phase4_wip_validation.csv", "Step 8C WIP validation"),
    ]:
        if not path.exists():
            _add_check(checks, f"{name}_exists", "FAIL", f"{name} missing.", 1)
        else:
            validation = pd.read_csv(path)
            fail_count = int((validation["status"].astype(str).str.upper() == "FAIL").sum()) if "status" in validation.columns else 0
            _add_check(checks, f"{name}_no_fail", "PASS" if fail_count == 0 else "FAIL", f"{name} FAIL rows={fail_count}.", fail_count)


def _wip_aware_status(
    has_input: bool,
    accepted_qty: float,
    required_qty: float,
    shortage: float,
    buffer_status: str,
    upstream_build: bool,
    capacity_blocker: bool,
    maintenance_blocker: bool,
    material_blocker: bool,
    wip_blocker: bool,
) -> str:
    if buffer_status in {"FULL", "OVERFLOW_RISK"} and has_input and shortage > 0:
        return "WIP_BUFFER_FULL_BLOCKED"
    blocker_count = sum([capacity_blocker, maintenance_blocker, material_blocker, wip_blocker])
    if blocker_count > 1:
        return "MULTI_BLOCKED_AFTER_WIP"
    if capacity_blocker:
        return "CAPACITY_STILL_BLOCKED"
    if maintenance_blocker:
        return "MAINTENANCE_STILL_BLOCKED"
    if has_input and shortage > 0 and accepted_qty > 0:
        return "WIP_PARTIALLY_SUPPORTS_CANDIDATE"
    if has_input and shortage > 0:
        return "WIP_SHORTAGE_BLOCKED"
    if upstream_build and not has_input:
        return "WIP_BUFFER_CAN_ABSORB_UPSTREAM_PRODUCTION"
    if has_input and required_qty > 0 and accepted_qty >= required_qty:
        return "WIP_SUPPORTED_FEASIBLE_CANDIDATE"
    if material_blocker:
        return "REVIEW_REQUIRED"
    return "WIP_SUPPORTED_FEASIBLE_CANDIDATE"


def _score_feasibility(status: str, accepted: float, required: float, available_capacity: float, capacity_blocker: bool, maintenance_blocker: bool) -> float:
    score = 50.0
    if status == "WIP_SUPPORTED_FEASIBLE_CANDIDATE":
        score += 30
    if status == "WIP_PARTIALLY_SUPPORTS_CANDIDATE":
        score += 10
    if status == "WIP_BUFFER_CAN_ABSORB_UPSTREAM_PRODUCTION":
        score += 20
    if capacity_blocker:
        score -= 25
    if maintenance_blocker:
        score -= 25
    if required > 0:
        score += min(accepted / required * 20, 20)
    if available_capacity > 0:
        score += 5
    return max(round(score, 3), 0.0)


def _blocking_reason(row: pd.Series) -> str:
    if _bool_value(row["remaining_capacity_blocker_flag"]):
        return "DOWNSTREAM_CAPACITY_BLOCKED"
    if _bool_value(row["remaining_maintenance_blocker_flag"]):
        return "DOWNSTREAM_MAINTENANCE_BLOCKED"
    if _bool_value(row["remaining_wip_blocker_flag"]):
        return "WIP_SHORTAGE"
    if _bool_value(row["remaining_material_blocker_flag"]):
        return "MATERIAL_REVIEW_REQUIRED"
    return "REVIEW_REQUIRED"


def _is_capacity_blocked(status: str) -> bool:
    return str(status).upper() in {"CAPACITY_BLOCKED", "OVERLOADED", "REVIEW_REQUIRED"}


def _is_maintenance_blocked(status: str) -> bool:
    return str(status).upper() in {"MAINTENANCE_BLOCKED", "MAINTENANCE_REVIEW_REQUIRED", "REVIEW_REQUIRED"}


def _worst_material_status(statuses: pd.Series) -> str:
    values = set(statuses.dropna().astype(str))
    for status in ["MATERIAL_BLOCKED", "MATERIAL_REVIEW_REQUIRED", "INVENTORY_REVIEW_REQUIRED", "SUPPLIER_COVERED_REVIEW", "MATERIAL_READY"]:
        if status in values:
            return status
    return "MATERIAL_REVIEW_REQUIRED"


def _buffer_id_for_wip(wip_item_id: str, flow_row: dict | None, buffer_by_item: dict[str, dict]) -> str:
    if not wip_item_id:
        return ""
    buffer_row = buffer_by_item.get(wip_item_id, {})
    return str(buffer_row.get("wip_buffer_id", "")) if buffer_row else ""


def _output_buffer_capacity(wip_item_id: str, buffer_by_item: dict[str, dict]) -> float:
    if not wip_item_id:
        return 0.0
    return _num_value(buffer_by_item.get(wip_item_id, {}).get("available_buffer_capacity_qty", 0.0))


def _buffer_for_wip(buffer_status: pd.DataFrame, wip_item_id: str) -> dict:
    if not wip_item_id:
        return {}
    match = buffer_status[buffer_status["wip_item_id"].astype(str) == str(wip_item_id)]
    return match.iloc[0].to_dict() if not match.empty else {}


def _target_for_buffer(buffer_status: pd.DataFrame, buffer_id: str) -> float:
    if not buffer_id:
        return 0.0
    match = buffer_status[buffer_status["wip_buffer_id"].astype(str) == str(buffer_id)]
    return _num_value(match.iloc[0].get("target_buffer_qty", 0.0)) if not match.empty else 0.0


def _load_csv(path: Path, label: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        _add_check(checks, f"{label}_exists", "FAIL", f"{label} is missing: {path}", 1)
        return None
    frame = pd.read_csv(path)
    if frame.empty:
        _add_check(checks, f"{label}_not_empty", "FAIL", f"{label} is empty.", 0)
        return None
    _add_check(checks, f"{label}_loaded", "PASS", f"{label} loaded with {len(frame)} rows.", len(frame))
    return frame


def _check_no_forbidden_outputs(checks: list[dict]) -> None:
    forbidden_tokens = [
        "actual_wip_consumption",
        "wip_transaction",
        "component_inventory_consumption",
        "inventory_reservation",
        "production_order",
        "confirmed_production_schedule",
        "worker_dispatch",
        "purchase_order",
        "capacity_reduction",
        "simulation",
    ]
    found = []
    for path in OUTPUT_DIR.glob("*"):
        name = path.name.lower()
        if any(token in name for token in forbidden_tokens):
            found.append(path.name)
    _add_check(checks, "forbidden_outputs_absent", "PASS" if not found else "FAIL", f"Forbidden outputs found: {found}" if found else "No forbidden execution/scheduling/transaction outputs found.", len(found))


def _add_check(checks: list[dict], check_name: str, status: str, message: str, affected_rows: int) -> None:
    checks.append({
        "check_id": f"WIP8D-{len(checks)+1:03d}",
        "check_name": check_name,
        "status": status,
        "message": message,
        "affected_rows": affected_rows,
        "advisory_only_flag": True,
    })


def _planning_run_id(frames: dict[str, pd.DataFrame]) -> str:
    for frame in frames.values():
        if frame is not None and "planning_run_id" in frame.columns and not frame.empty:
            return str(frame["planning_run_id"].iloc[0])
    return "PHASE4-WIP8D"


def _index_by(frame: pd.DataFrame, column: str) -> dict[str, dict]:
    if column not in frame.columns:
        return {}
    return {str(row[column]): row.to_dict() for _, row in frame.iterrows()}


def _first_value(frame: pd.DataFrame, column: str) -> str:
    if column in frame.columns and not frame.empty:
        return str(frame[column].iloc[0])
    return ""


def _num_value(value: object) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        return 0.0


def _num_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series([0.0] * len(frame), index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _all_true(frame: pd.DataFrame, column: str) -> bool:
    return column in frame.columns and bool(_to_bool(frame[column]).all())


def _all_false(frame: pd.DataFrame, column: str) -> bool:
    return column in frame.columns and bool((~_to_bool(frame[column])).all())


def _non_negative_bad_count(frame: pd.DataFrame, columns: list[str]) -> int:
    bad = 0
    for column in columns:
        if column not in frame.columns:
            bad += len(frame)
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        bad += int(values.isna().sum() + (values < 0).sum())
    return bad


def _empty_feasibility() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "schedule_candidate_id", "finished_sku", "operation_id", "operation_name", "workstation_id", "machine_id",
        "candidate_schedule_period", "candidate_schedule_day", "candidate_schedule_shift", "original_schedule_candidate_status",
        "original_material_readiness_status", "original_capacity_feasibility_status", "original_maintenance_feasibility_status",
        "required_input_wip_item_id", "output_wip_item_id", "related_wip_buffer_id", "accepted_wip_available_qty", "required_wip_qty",
        "wip_shortage_qty", "available_buffer_capacity_qty", "downstream_can_resume_from_wip_flag", "upstream_can_build_wip_flag",
        "wip_reduces_schedule_blocker_flag", "remaining_material_blocker_flag", "remaining_capacity_blocker_flag",
        "remaining_maintenance_blocker_flag", "remaining_wip_blocker_flag", "wip_aware_schedule_status", "wip_aware_feasibility_score",
        "source_phase", "advisory_only_flag",
    ])


def _empty_balance() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "finished_sku", "operation_id", "operation_name", "required_input_wip_item_id", "wip_buffer_id",
        "accepted_wip_available_qty", "required_wip_qty", "wip_surplus_qty", "wip_shortage_qty", "wip_coverage_pct",
        "downstream_can_consume_wip_flag", "note_no_wip_consumption_flag", "balance_status", "source_phase", "advisory_only_flag",
    ])


def _empty_buffer_impact() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "wip_buffer_id", "wip_buffer_name", "wip_item_id", "linked_workstation_id", "current_wip_qty",
        "accepted_wip_qty", "blocked_wip_qty", "min_buffer_qty", "target_buffer_qty", "max_buffer_qty", "available_buffer_capacity_qty",
        "buffer_utilization_pct", "buffer_status", "upstream_can_continue_flag", "downstream_can_resume_from_wip_flag",
        "impacted_schedule_candidate_count", "schedule_blockers_reduced_count", "schedule_blockers_remaining_count",
        "buffer_schedule_impact_status", "source_phase", "advisory_only_flag",
    ])


def _empty_recommendations() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "recommendation_id", "planning_run_id", "finished_sku", "schedule_candidate_id", "blocking_operation_id",
        "blocking_operation_name", "blocking_reason", "upstream_operation_id", "upstream_operation_name", "downstream_operation_id",
        "downstream_operation_name", "wip_item_id", "wip_buffer_id", "current_accepted_wip_qty", "target_buffer_qty",
        "available_buffer_capacity_qty", "recommended_action", "recommendation_reason", "expected_schedule_effect",
        "auto_action_allowed", "advisory_only_flag",
    ])


def _empty_maintenance_opportunity() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "workstation_id", "machine_id", "operation_id", "operation_name", "wip_item_id", "wip_buffer_id",
        "current_accepted_wip_qty", "target_buffer_qty", "max_buffer_qty", "downstream_can_resume_from_wip_flag",
        "upstream_can_pause_after_target_flag", "maintenance_opportunity_flag", "maintenance_opportunity_reason",
        "related_maintenance_blocker_flag", "advisory_maintenance_window_candidate_status", "note_no_maintenance_order_created_flag",
        "source_phase", "advisory_only_flag",
    ])


def _empty_review() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "review_item_id", "planning_run_id", "schedule_candidate_id", "finished_sku", "operation_id", "wip_item_id",
        "wip_buffer_id", "issue_type", "issue_severity", "issue_description", "recommended_review_action",
        "auto_action_allowed", "advisory_only_flag",
    ])


if __name__ == "__main__":
    outputs = build_wip_aware_schedule_feasibility_outputs()
    print(f"WIP-aware schedule feasibility rows: {len(outputs[0])}")
    print(f"WIP-aware schedule validation rows: {len(outputs[-1])}")
