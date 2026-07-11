"""Build advisory WIP batch tracking and buffer foundation outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE4_DIR.parent
DATA_DIR = PHASE4_DIR / "data"
OUTPUT_DIR = PHASE4_DIR / "outputs"

WIP_ITEMS_FILE = DATA_DIR / "wip_items.csv"
WIP_BUFFERS_FILE = DATA_DIR / "wip_buffer_locations.csv"
WIP_BATCH_SEED_FILE = DATA_DIR / "wip_batch_seed.csv"
ROUTINGS_FILE = DATA_DIR / "product_routings.csv"
PARALLEL_GROUPS_FILE = DATA_DIR / "routing_parallel_groups.csv"
NODES_FILE = OUTPUT_DIR / "phase4_routing_graph_nodes.csv"
EDGES_FILE = OUTPUT_DIR / "phase4_routing_graph_edges.csv"
SLACK_FILE = OUTPUT_DIR / "phase4_operation_slack_analysis.csv"
SCHEDULE_CANDIDATES_FILE = OUTPUT_DIR / "phase4_production_schedule_candidates.csv"
SCHEDULE_DETAIL_FILE = OUTPUT_DIR / "phase4_operation_schedule_candidate_detail.csv"
FLOW_VIEW_FILE = OUTPUT_DIR / "phase4_production_flow_view.csv"
QUALITY_IMPACT_FILE = OUTPUT_DIR / "phase4_quality_impact_by_operation.csv"
CAPACITY_CHECK_FILE = OUTPUT_DIR / "phase4_production_schedule_capacity_check.csv"
MAINTENANCE_SCHEDULE_FILE = OUTPUT_DIR / "phase4_maintenance_schedule_feasibility_context.csv"
MAINTENANCE_IMPACT_FILE = OUTPUT_DIR / "phase4_maintenance_production_impact_context.csv"

WIP_ITEM_MASTER_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_item_master.csv"
WIP_FLOW_MAP_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_operation_flow_map.csv"
WIP_BATCH_LEDGER_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_batch_ledger.csv"
WIP_BUFFER_STATUS_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_buffer_status.csv"
WIP_QUALITY_STATUS_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_quality_status.csv"
WIP_CONTINUITY_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_line_continuity_analysis.csv"
WIP_MANAGER_REVIEW_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_manager_review_queue.csv"
WIP_VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_validation.csv"

SOURCE_PHASE = "PHASE4_STEP8C_WIP_BATCH_TRACKING_BUFFER_FOUNDATION"
VALID_FLOW_STATUS = {"VALID_FLOW", "MISSING_PRODUCER", "MISSING_CONSUMER", "REVIEW_REQUIRED"}
VALID_BUFFER_STATUS = {"BELOW_MINIMUM", "WITHIN_TARGET", "ABOVE_TARGET", "FULL", "OVERFLOW_RISK", "NO_BUFFER_DEFINED", "REVIEW_REQUIRED"}
VALID_CONTINUITY_STATUS = {"CONTINUITY_SUPPORTED", "BUFFER_FULL_STOP_UPSTREAM", "WIP_SHORTAGE_RISK", "DOWNSTREAM_CAN_RESUME_FROM_WIP", "REVIEW_REQUIRED"}


def build_wip_batch_tracking_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    checks: list[dict] = []
    frames = {
        "wip_items": _load_csv(WIP_ITEMS_FILE, "wip_items", checks),
        "wip_buffers": _load_csv(WIP_BUFFERS_FILE, "wip_buffer_locations", checks),
        "wip_batches": _load_csv(WIP_BATCH_SEED_FILE, "wip_batch_seed", checks),
        "routings": _load_csv(ROUTINGS_FILE, "product_routings", checks),
        "parallel_groups": _load_csv(PARALLEL_GROUPS_FILE, "routing_parallel_groups", checks),
        "nodes": _load_csv(NODES_FILE, "phase4_routing_graph_nodes", checks),
        "edges": _load_csv(EDGES_FILE, "phase4_routing_graph_edges", checks),
        "slack": _load_csv(SLACK_FILE, "phase4_operation_slack_analysis", checks),
        "schedule_candidates": _load_csv(SCHEDULE_CANDIDATES_FILE, "phase4_production_schedule_candidates", checks),
        "schedule_detail": _load_csv(SCHEDULE_DETAIL_FILE, "phase4_operation_schedule_candidate_detail", checks),
        "flow_view": _load_csv(FLOW_VIEW_FILE, "phase4_production_flow_view", checks),
        "quality_impact": _load_csv(QUALITY_IMPACT_FILE, "phase4_quality_impact_by_operation", checks),
        "capacity_check": _load_csv(CAPACITY_CHECK_FILE, "phase4_production_schedule_capacity_check", checks),
        "maintenance_schedule": _load_csv(MAINTENANCE_SCHEDULE_FILE, "phase4_maintenance_schedule_feasibility_context", checks),
        "maintenance_impact": _load_csv(MAINTENANCE_IMPACT_FILE, "phase4_maintenance_production_impact_context", checks),
    }
    if all(frame is not None for frame in frames.values()):
        item_master = _build_item_master(frames)
        flow_map = _build_flow_map(frames)
        ledger = _build_batch_ledger(frames)
        buffer_status = _build_buffer_status(frames, ledger)
        quality_status = _build_quality_status(frames, ledger)
        continuity = _build_continuity(frames, ledger, buffer_status)
        review = _build_review_queue(flow_map, ledger, buffer_status, quality_status, continuity)
        _validate_outputs(frames, item_master, flow_map, ledger, buffer_status, quality_status, continuity, review, checks)
    else:
        item_master = _empty_item_master()
        flow_map = _empty_flow_map()
        ledger = _empty_ledger()
        buffer_status = _empty_buffer_status()
        quality_status = _empty_quality_status()
        continuity = _empty_continuity()
        review = _empty_review()

    _check_no_forbidden_outputs(checks)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    item_master.to_csv(WIP_ITEM_MASTER_OUTPUT_FILE, index=False)
    flow_map.to_csv(WIP_FLOW_MAP_OUTPUT_FILE, index=False)
    ledger.to_csv(WIP_BATCH_LEDGER_OUTPUT_FILE, index=False)
    buffer_status.to_csv(WIP_BUFFER_STATUS_OUTPUT_FILE, index=False)
    quality_status.to_csv(WIP_QUALITY_STATUS_OUTPUT_FILE, index=False)
    continuity.to_csv(WIP_CONTINUITY_OUTPUT_FILE, index=False)
    review.to_csv(WIP_MANAGER_REVIEW_OUTPUT_FILE, index=False)
    validation.to_csv(WIP_VALIDATION_OUTPUT_FILE, index=False)
    return item_master, flow_map, ledger, buffer_status, quality_status, continuity, review, validation


def _build_item_master(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    items = frames["wip_items"].copy()
    planning_run_id = _planning_run_id(frames)
    items.insert(0, "planning_run_id", planning_run_id)
    items["source_phase"] = SOURCE_PHASE
    return items[_empty_item_master().columns]


def _build_flow_map(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    items = frames["wip_items"].copy()
    nodes = frames["nodes"].copy()
    edges = frames["edges"].copy()
    planning_run_id = _planning_run_id(frames)
    node_by_op = _index_by(nodes, "operation_id")
    edge_keys = {
        (str(row["finished_sku"]), str(row["from_operation_id"]), str(row["to_operation_id"])): row.to_dict()
        for _, row in edges.iterrows()
    }
    rows = []
    for _, item in items[_to_bool(items["active_flag"])].iterrows():
        sku = str(item["finished_sku"])
        producer = str(item["produced_by_operation_id"])
        consumer = str(item["consumed_by_operation_id"])
        edge = edge_keys.get((sku, producer, consumer), {})
        producer_node = node_by_op.get(producer, {})
        consumer_node = node_by_op.get(consumer, {})
        status = "VALID_FLOW"
        if not producer_node:
            status = "MISSING_PRODUCER"
        elif not consumer_node:
            status = "MISSING_CONSUMER"
        rows.append({
            "planning_run_id": planning_run_id,
            "finished_sku": sku,
            "wip_item_id": item["wip_item_id"],
            "wip_item_name": item["wip_item_name"],
            "produced_by_operation_id": producer,
            "produced_by_operation_name": producer_node.get("operation_name", ""),
            "consumed_by_operation_id": consumer,
            "consumed_by_operation_name": consumer_node.get("operation_name", ""),
            "produced_by_workstation_id": item["produced_by_workstation_id"],
            "consumed_by_workstation_id": item["consumed_by_workstation_id"],
            "routing_edge_id": f"{producer}->{consumer}" if edge else "",
            "parallel_branch_flag": str(edge.get("dependency_type", "")) == "PARALLEL_BRANCH",
            "merge_dependency_flag": _bool_value(edge.get("merge_edge_flag", False)),
            "final_assembly_input_flag": str(consumer_node.get("operation_type", "")).upper() == "FINAL_ASSEMBLY",
            "flow_map_status": status,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_empty_flow_map().columns)


def _build_batch_ledger(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    batches = frames["wip_batches"].copy()
    items = _index_by(frames["wip_items"], "wip_item_id")
    planning_run_id = _planning_run_id(frames)
    rows = []
    for _, batch in batches[_to_bool(batches["active_flag"])].iterrows():
        produced = _num_value(batch.get("produced_qty", 0))
        accepted = _num_value(batch.get("accepted_qty", 0))
        defective = _num_value(batch.get("defective_qty", 0))
        rework = _num_value(batch.get("rework_qty", 0))
        scrap = _num_value(batch.get("scrap_qty", 0))
        blocked = max(defective, 0)
        status = str(batch["wip_batch_status"])
        quality = str(batch["quality_status"])
        location_type = str(batch["current_location_type"])
        available = accepted if status in {"READY_FOR_NEXT_OPERATION", "IN_WIP_BUFFER", "ON_PRODUCTION_LINE"} and quality in {"ACCEPTED", "PARTIAL_ACCEPTED"} else 0.0
        rows.append({
            "planning_run_id": planning_run_id,
            "wip_batch_id": batch["wip_batch_id"],
            "wip_item_id": batch["wip_item_id"],
            "wip_item_name": items.get(str(batch["wip_item_id"]), {}).get("wip_item_name", ""),
            "finished_sku": batch["finished_sku"],
            "source_schedule_candidate_id": batch["source_schedule_candidate_id"],
            "produced_by_operation_id": batch["produced_by_operation_id"],
            "next_operation_id": batch["next_operation_id"],
            "current_location_type": location_type,
            "current_location_id": batch["current_location_id"],
            "produced_qty": produced,
            "accepted_qty": accepted,
            "defective_qty": defective,
            "rework_qty": rework,
            "scrap_qty": scrap,
            "available_accepted_qty": max(available, 0),
            "blocked_qty": max(blocked, 0),
            "quality_status": quality,
            "wip_batch_status": status,
            "ready_for_next_operation_flag": status == "READY_FOR_NEXT_OPERATION" and available > 0,
            "off_production_line_flag": location_type in {"WIP_STORAGE", "LINE_SIDE_BUFFER", "QUALITY_HOLD", "REWORK_HOLD"},
            "callable_back_to_line_flag": status == "READY_FOR_NEXT_OPERATION" and quality in {"ACCEPTED", "PARTIAL_ACCEPTED"} and available > 0,
            "note_no_wip_consumption_flag": True,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_empty_ledger().columns)


def _build_buffer_status(frames: dict[str, pd.DataFrame], ledger: pd.DataFrame) -> pd.DataFrame:
    buffers = frames["wip_buffers"].copy()
    planning_run_id = _planning_run_id(frames)
    rows = []
    for _, buf in buffers[_to_bool(buffers["active_flag"])].iterrows():
        batches = ledger[ledger["current_location_id"].astype(str) == str(buf["wip_buffer_id"])]
        current_qty = _num_series(batches, "accepted_qty").sum() + _num_series(batches, "blocked_qty").sum()
        accepted_qty = _num_series(batches, "available_accepted_qty").sum()
        blocked_qty = _num_series(batches, "blocked_qty").sum()
        max_qty = _num_value(buf["max_buffer_qty"])
        target = _num_value(buf["target_buffer_qty"])
        minimum = _num_value(buf["min_buffer_qty"])
        available = max(max_qty - current_qty, 0)
        util = (current_qty / max_qty * 100) if max_qty > 0 else 0
        if max_qty <= 0:
            status = "NO_BUFFER_DEFINED"
        elif current_qty > max_qty:
            status = "OVERFLOW_RISK"
        elif current_qty >= max_qty:
            status = "FULL"
        elif current_qty < minimum:
            status = "BELOW_MINIMUM"
        elif current_qty <= target:
            status = "WITHIN_TARGET"
        else:
            status = "ABOVE_TARGET"
        rows.append({
            "planning_run_id": planning_run_id,
            "wip_buffer_id": buf["wip_buffer_id"],
            "wip_buffer_name": buf["wip_buffer_name"],
            "wip_item_id": buf["wip_item_id"],
            "linked_workstation_id": buf["linked_workstation_id"],
            "max_buffer_qty": max_qty,
            "target_buffer_qty": target,
            "min_buffer_qty": minimum,
            "current_wip_qty": current_qty,
            "accepted_wip_qty": accepted_qty,
            "blocked_wip_qty": blocked_qty,
            "available_buffer_capacity_qty": available,
            "buffer_utilization_pct": round(util, 4),
            "buffer_status": status,
            "upstream_can_continue_flag": status not in {"FULL", "OVERFLOW_RISK", "NO_BUFFER_DEFINED", "REVIEW_REQUIRED"},
            "downstream_can_consume_wip_flag": accepted_qty > 0,
            "overflow_risk_flag": status in {"FULL", "OVERFLOW_RISK"},
            "shortage_risk_flag": status == "BELOW_MINIMUM",
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_empty_buffer_status().columns)


def _build_quality_status(frames: dict[str, pd.DataFrame], ledger: pd.DataFrame) -> pd.DataFrame:
    items = _index_by(frames["wip_items"], "wip_item_id")
    rows = []
    for _, row in ledger.iterrows():
        produced = _num_value(row["produced_qty"])
        accepted = _num_value(row["accepted_qty"])
        defective = _num_value(row["defective_qty"])
        rework = _num_value(row["rework_qty"])
        scrap = _num_value(row["scrap_qty"])
        review_qty = max(defective - rework - scrap, 0)
        balance = produced - accepted - defective
        defect_balance = defective - rework - scrap - review_qty
        balanced = abs(balance) <= 0.0001 and abs(defect_balance) <= 0.0001
        rows.append({
            "planning_run_id": row["planning_run_id"],
            "wip_batch_id": row["wip_batch_id"],
            "wip_item_id": row["wip_item_id"],
            "finished_sku": row["finished_sku"],
            "produced_qty": produced,
            "accepted_qty": accepted,
            "defective_qty": defective,
            "rework_qty": rework,
            "scrap_qty": scrap,
            "quality_review_qty": review_qty,
            "quality_status": row["quality_status"],
            "quality_balance_check": round(balance, 6),
            "quality_balance_status": "BALANCED" if balanced else "REVIEW_REQUIRED",
            "rework_allowed_flag": _bool_value(items.get(str(row["wip_item_id"]), {}).get("rework_allowed_flag", False)),
            "quality_review_required_flag": row["quality_status"] in {"QUALITY_REVIEW_REQUIRED", "REWORK_REQUIRED", "REVIEW_REQUIRED"} or not balanced,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_empty_quality_status().columns)


def _build_continuity(frames: dict[str, pd.DataFrame], ledger: pd.DataFrame, buffer_status: pd.DataFrame) -> pd.DataFrame:
    items = frames["wip_items"].copy()
    nodes = _index_by(frames["nodes"], "operation_id")
    capacity = frames["capacity_check"].copy()
    maint_by_machine = _index_by(frames["maintenance_schedule"], "machine_id")
    buffer_by_item = _index_by(buffer_status, "wip_item_id")
    planning_run_id = _planning_run_id(frames)
    blocked_ops = set(capacity.loc[_to_bool(capacity["capacity_blocker_flag"]), "operation_id"].astype(str))
    for _, node in frames["nodes"].iterrows():
        if str(maint_by_machine.get(str(node.get("machine_id", "")), {}).get("best_schedule_feasibility_status", "")) in {"MULTI_BLOCKED", "BLOCKED_BY_CREW", "BLOCKED_BY_SPARE_PART", "BLOCKED_BY_PRODUCTION_IMPACT", "REVIEW_REQUIRED"}:
            blocked_ops.add(str(node["operation_id"]))
    rows = []
    for _, item in items.iterrows():
        consumer = str(item["consumed_by_operation_id"])
        producer = str(item["produced_by_operation_id"])
        if consumer not in blocked_ops:
            continue
        buf = buffer_by_item.get(str(item["wip_item_id"]), {})
        accepted = _num_series(ledger[ledger["wip_item_id"].astype(str) == str(item["wip_item_id"])], "available_accepted_qty").sum()
        available_capacity = _num_value(buf.get("available_buffer_capacity_qty", 0))
        target = _num_value(buf.get("target_buffer_qty", 0))
        upstream_can = bool(buf.get("upstream_can_continue_flag", False))
        downstream_can = accepted > 0
        maint_status = str(maint_by_machine.get(str(nodes.get(consumer, {}).get("machine_id", "")), {}).get("best_schedule_feasibility_status", ""))
        if "MAINTENANCE" in maint_status or maint_status in {"MULTI_BLOCKED", "BLOCKED_BY_CREW", "BLOCKED_BY_SPARE_PART"}:
            reason = "DOWNSTREAM_MAINTENANCE_BLOCKED"
        elif consumer in blocked_ops:
            reason = "DOWNSTREAM_CAPACITY_BLOCKED"
        else:
            reason = "REVIEW_REQUIRED"
        if not upstream_can:
            action = "HOLD_UPSTREAM_PRODUCTION"
            status = "BUFFER_FULL_STOP_UPSTREAM"
        elif downstream_can:
            action = "USE_WIP_FOR_DOWNSTREAM_RESUME"
            status = "DOWNSTREAM_CAN_RESUME_FROM_WIP"
        elif available_capacity > 0:
            action = "BUILD_WIP_TO_TARGET"
            status = "CONTINUITY_SUPPORTED"
        else:
            action = "REVIEW_BUFFER_CAPACITY"
            status = "REVIEW_REQUIRED"
        rows.append({
            "planning_run_id": planning_run_id,
            "finished_sku": item["finished_sku"],
            "blocking_operation_id": consumer,
            "blocking_operation_name": nodes.get(consumer, {}).get("operation_name", ""),
            "blocking_reason": reason,
            "upstream_operation_id": producer,
            "upstream_operation_name": nodes.get(producer, {}).get("operation_name", ""),
            "upstream_workstation_id": item["produced_by_workstation_id"],
            "wip_item_id": item["wip_item_id"],
            "wip_buffer_id": buf.get("wip_buffer_id", ""),
            "current_accepted_wip_qty": accepted,
            "target_buffer_qty": target,
            "available_buffer_capacity_qty": available_capacity,
            "upstream_can_continue_flag": upstream_can,
            "downstream_can_resume_from_wip_flag": downstream_can,
            "suggested_continuity_action": action,
            "maintenance_opportunity_flag": upstream_can and accepted >= target and target > 0,
            "continuity_status": status,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_empty_continuity().columns)


def _build_review_queue(flow_map: pd.DataFrame, ledger: pd.DataFrame, buffer_status: pd.DataFrame, quality_status: pd.DataFrame, continuity: pd.DataFrame) -> pd.DataFrame:
    rows = []
    idx = 1

    def add(issue_type: str, severity: str, desc: str, action: str, batch: str = "", item: str = "", buffer_id: str = "", op: str = "", run_id: str = "") -> None:
        nonlocal idx
        rows.append({
            "review_item_id": f"WIPR-{idx:04d}",
            "planning_run_id": run_id or _first_run_id([flow_map, ledger, buffer_status, quality_status, continuity]),
            "wip_batch_id": batch,
            "wip_item_id": item,
            "wip_buffer_id": buffer_id,
            "operation_id": op,
            "issue_type": issue_type,
            "issue_severity": severity,
            "issue_description": desc,
            "recommended_review_action": action,
            "auto_action_allowed": False,
            "advisory_only_flag": True,
        })
        idx += 1

    for _, row in buffer_status.iterrows():
        if _bool_value(row["overflow_risk_flag"]):
            add("WIP_BUFFER_OVERFLOW_RISK", "HIGH", "WIP buffer is full or above capacity.", "REVIEW_BUFFER_CAPACITY", item=row["wip_item_id"], buffer_id=row["wip_buffer_id"], run_id=row["planning_run_id"])
        if _bool_value(row["shortage_risk_flag"]):
            add("WIP_SHORTAGE_RISK", "MEDIUM", "WIP buffer is below minimum target.", "REVIEW_WIP_BUILD_PLAN", item=row["wip_item_id"], buffer_id=row["wip_buffer_id"], run_id=row["planning_run_id"])
    for _, row in quality_status.iterrows():
        if _bool_value(row["quality_review_required_flag"]):
            add("WIP_QUALITY_REVIEW", "HIGH", "WIP batch requires quality or rework review.", "REVIEW_WIP_QUALITY", batch=row["wip_batch_id"], item=row["wip_item_id"], run_id=row["planning_run_id"])
    for _, row in ledger.iterrows():
        if row["wip_batch_status"] in {"BLOCKED_BY_QUALITY_REVIEW", "IN_REWORK", "REVIEW_REQUIRED"}:
            add("WIP_BLOCKED", "HIGH", "WIP batch is blocked before next operation.", "REVIEW_BLOCKED_WIP", batch=row["wip_batch_id"], item=row["wip_item_id"], op=row["next_operation_id"], run_id=row["planning_run_id"])
    for _, row in flow_map.iterrows():
        if row["flow_map_status"] != "VALID_FLOW":
            add("WIP_FLOW_MAPPING_REVIEW", "HIGH", "WIP item has missing producer or consumer mapping.", "REVIEW_WIP_ROUTING_MAP", item=row["wip_item_id"], op=row["consumed_by_operation_id"], run_id=row["planning_run_id"])
    for _, row in continuity.iterrows():
        if row["continuity_status"] in {"BUFFER_FULL_STOP_UPSTREAM", "WIP_SHORTAGE_RISK", "REVIEW_REQUIRED"}:
            add("LINE_CONTINUITY_REVIEW", "HIGH", "Line continuity requires manager review.", "REVIEW_LINE_CONTINUITY", item=row["wip_item_id"], buffer_id=row["wip_buffer_id"], op=row["blocking_operation_id"], run_id=row["planning_run_id"])
        if _bool_value(row["maintenance_opportunity_flag"]):
            add("MAINTENANCE_OPPORTUNITY_REVIEW", "MEDIUM", "WIP buffer may support a maintenance opportunity review.", "REVIEW_MAINTENANCE_OPPORTUNITY", item=row["wip_item_id"], buffer_id=row["wip_buffer_id"], op=row["upstream_operation_id"], run_id=row["planning_run_id"])
    return pd.DataFrame(rows, columns=_empty_review().columns)


def _validate_outputs(frames: dict[str, pd.DataFrame], item_master: pd.DataFrame, flow_map: pd.DataFrame, ledger: pd.DataFrame, buffer_status: pd.DataFrame, quality_status: pd.DataFrame, continuity: pd.DataFrame, review: pd.DataFrame, checks: list[dict]) -> None:
    outputs = {
        "wip_item_master": item_master,
        "wip_operation_flow_map": flow_map,
        "wip_batch_ledger": ledger,
        "wip_buffer_status": buffer_status,
        "wip_quality_status": quality_status,
        "wip_line_continuity_analysis": continuity,
        "wip_manager_review_queue": review,
    }
    data_files = {"wip_items": frames["wip_items"], "wip_buffer_locations": frames["wip_buffers"], "wip_batch_seed": frames["wip_batches"]}
    for name, frame in {**outputs, **data_files}.items():
        checks.append(_check(name, "PASS" if not frame.empty else "FAIL", f"{name} rows={len(frame)}", len(frame)))
    required = {
        "wip_item_master": set(_empty_item_master().columns),
        "wip_operation_flow_map": set(_empty_flow_map().columns),
        "wip_batch_ledger": set(_empty_ledger().columns),
        "wip_buffer_status": set(_empty_buffer_status().columns),
        "wip_quality_status": set(_empty_quality_status().columns),
        "wip_line_continuity_analysis": set(_empty_continuity().columns),
        "wip_manager_review_queue": set(_empty_review().columns),
    }
    for name, cols in required.items():
        missing = sorted(cols.difference(outputs[name].columns))
        checks.append(_check(f"{name}_required_columns", "PASS" if not missing else "FAIL", f"missing={missing}", len(missing)))
    checks.append(_check("unique_wip_items", "PASS" if frames["wip_items"]["wip_item_id"].is_unique else "FAIL", "wip_item_id values must be unique.", 0))
    checks.append(_check("unique_seed_batches", "PASS" if frames["wip_batches"]["wip_batch_id"].is_unique else "FAIL", "Seed wip_batch_id values must be unique.", 0))
    checks.append(_check("unique_ledger_batches", "PASS" if ledger["wip_batch_id"].is_unique else "FAIL", "Ledger wip_batch_id values must be unique.", 0))
    valid_ops = set(frames["nodes"]["operation_id"].astype(str))
    map_ops = set(flow_map["produced_by_operation_id"].astype(str)) | set(flow_map["consumed_by_operation_id"].astype(str))
    checks.append(_check("flow_map_valid_operations", "PASS" if map_ops <= valid_ops else "FAIL", f"invalid_ops={sorted(map_ops - valid_ops)}", len(map_ops - valid_ops)))
    valid_items = set(frames["wip_items"]["wip_item_id"].astype(str))
    checks.append(_check("batches_valid_wip_items", "PASS" if set(ledger["wip_item_id"].astype(str)) <= valid_items else "FAIL", "WIP batches must reference valid WIP items.", 0))
    next_ops = set(ledger["next_operation_id"].dropna().astype(str))
    checks.append(_check("batches_valid_next_operations", "PASS" if next_ops <= valid_ops else "FAIL", f"invalid_next_ops={sorted(next_ops - valid_ops)}", len(next_ops - valid_ops)))
    checks.append(_check("buffers_valid_wip_items", "PASS" if set(frames["wip_buffers"]["wip_item_id"].astype(str)) <= valid_items else "FAIL", "WIP buffers must reference valid WIP items.", 0))
    for frame, columns, name in [
        (ledger, ["produced_qty", "accepted_qty", "defective_qty", "rework_qty", "scrap_qty", "available_accepted_qty", "blocked_qty"], "ledger"),
        (buffer_status, ["max_buffer_qty", "target_buffer_qty", "min_buffer_qty", "current_wip_qty", "buffer_utilization_pct"], "buffer_status"),
    ]:
        invalid = sum(int((_num_series(frame, col) < 0).sum()) for col in columns)
        checks.append(_check(f"{name}_non_negative_numeric", "PASS" if invalid == 0 else "FAIL", f"invalid_numeric_rows={invalid}", invalid))
    checks.append(_check("quality_balances_valid_or_review", "PASS" if set(quality_status["quality_balance_status"].astype(str)) <= {"BALANCED", "REVIEW_REQUIRED"} else "FAIL", "Quality balance statuses must be valid.", len(quality_status)))
    off_line = ledger[ledger["current_location_type"].isin(["WIP_STORAGE", "LINE_SIDE_BUFFER", "QUALITY_HOLD", "REWORK_HOLD"])]
    checks.append(_check("off_line_flags", "PASS" if _to_bool(off_line["off_production_line_flag"]).all() else "FAIL", "Buffer/hold locations must be off production line.", len(off_line)))
    callable_bad = ledger[_to_bool(ledger["callable_back_to_line_flag"]) & ~ledger["quality_status"].isin(["ACCEPTED", "PARTIAL_ACCEPTED"])]
    checks.append(_check("callable_only_accepted", "PASS" if callable_bad.empty else "FAIL", "Callable WIP must be accepted or partially accepted.", len(callable_bad)))
    checks.append(_check("no_wip_consumption", "PASS" if _all_true(ledger, "note_no_wip_consumption_flag") else "FAIL", "No WIP consumption flag must be True.", len(ledger)))
    for name, frame in outputs.items():
        checks.append(_check(f"{name}_advisory_only", "PASS" if _all_true(frame, "advisory_only_flag") else "FAIL", f"{name} advisory-only.", len(frame)))
    checks.append(_check("review_no_auto_action", "PASS" if _all_false(review, "auto_action_allowed") else "FAIL", "Review queue auto_action_allowed must be False.", len(review)))


def _check_no_forbidden_outputs(checks: list[dict]) -> None:
    blocked = ["confirmed_production_schedule", "production_order", "actual_wip_consumption", "inventory_consumption", "inventory_reservation", "worker_dispatch", "purchase_order", "capacity_reduction", "simulation"]
    bad = [str(path) for path in OUTPUT_DIR.glob("*") if path.is_file() and any(token in path.name.lower() for token in blocked)]
    checks.append(_check("no_forbidden_wip_outputs", "PASS" if not bad else "FAIL", f"bad={bad}", len(bad)))


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


def _planning_run_id(frames: dict[str, pd.DataFrame]) -> str:
    return _first_run_id([frame for frame in frames.values() if frame is not None])


def _first_run_id(frames: list[pd.DataFrame]) -> str:
    for frame in frames:
        if frame is not None and not frame.empty and "planning_run_id" in frame.columns:
            values = frame["planning_run_id"].dropna().astype(str).str.strip()
            if not values.empty:
                return values.iloc[0]
    return "PHASE4-STEP8C-WIP"


def _num_value(value: object) -> float:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0).iloc[0]
    return float(number)


def _num_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame.empty or column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(0)


def _bool_value(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _all_true(frame: pd.DataFrame, column: str) -> bool:
    return column in frame.columns and bool(_to_bool(frame[column]).all())


def _all_false(frame: pd.DataFrame, column: str) -> bool:
    return column in frame.columns and bool((~_to_bool(frame[column])).all())


def _check(check_id: str, status: str, message: str, affected_rows: int = 0) -> dict:
    return {"check_id": check_id, "check_name": check_id.replace("_", " ").title(), "status": status, "message": message, "affected_rows": int(affected_rows), "advisory_only_flag": True}


def _empty_item_master() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "wip_item_id", "wip_item_name", "finished_sku", "produced_by_operation_id", "consumed_by_operation_id", "produced_by_workstation_id", "consumed_by_workstation_id", "wip_item_type", "unit_of_measure", "batch_tracking_required_flag", "serial_tracking_required_flag", "quality_check_required_flag", "rework_allowed_flag", "shelf_life_hours", "active_flag", "advisory_only_flag", "notes", "source_phase"])


def _empty_flow_map() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "finished_sku", "wip_item_id", "wip_item_name", "produced_by_operation_id", "produced_by_operation_name", "consumed_by_operation_id", "consumed_by_operation_name", "produced_by_workstation_id", "consumed_by_workstation_id", "routing_edge_id", "parallel_branch_flag", "merge_dependency_flag", "final_assembly_input_flag", "flow_map_status", "source_phase", "advisory_only_flag"])


def _empty_ledger() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "wip_batch_id", "wip_item_id", "wip_item_name", "finished_sku", "source_schedule_candidate_id", "produced_by_operation_id", "next_operation_id", "current_location_type", "current_location_id", "produced_qty", "accepted_qty", "defective_qty", "rework_qty", "scrap_qty", "available_accepted_qty", "blocked_qty", "quality_status", "wip_batch_status", "ready_for_next_operation_flag", "off_production_line_flag", "callable_back_to_line_flag", "note_no_wip_consumption_flag", "source_phase", "advisory_only_flag"])


def _empty_buffer_status() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "wip_buffer_id", "wip_buffer_name", "wip_item_id", "linked_workstation_id", "max_buffer_qty", "target_buffer_qty", "min_buffer_qty", "current_wip_qty", "accepted_wip_qty", "blocked_wip_qty", "available_buffer_capacity_qty", "buffer_utilization_pct", "buffer_status", "upstream_can_continue_flag", "downstream_can_consume_wip_flag", "overflow_risk_flag", "shortage_risk_flag", "source_phase", "advisory_only_flag"])


def _empty_quality_status() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "wip_batch_id", "wip_item_id", "finished_sku", "produced_qty", "accepted_qty", "defective_qty", "rework_qty", "scrap_qty", "quality_review_qty", "quality_status", "quality_balance_check", "quality_balance_status", "rework_allowed_flag", "quality_review_required_flag", "source_phase", "advisory_only_flag"])


def _empty_continuity() -> pd.DataFrame:
    return pd.DataFrame(columns=["planning_run_id", "finished_sku", "blocking_operation_id", "blocking_operation_name", "blocking_reason", "upstream_operation_id", "upstream_operation_name", "upstream_workstation_id", "wip_item_id", "wip_buffer_id", "current_accepted_wip_qty", "target_buffer_qty", "available_buffer_capacity_qty", "upstream_can_continue_flag", "downstream_can_resume_from_wip_flag", "suggested_continuity_action", "maintenance_opportunity_flag", "continuity_status", "source_phase", "advisory_only_flag"])


def _empty_review() -> pd.DataFrame:
    return pd.DataFrame(columns=["review_item_id", "planning_run_id", "wip_batch_id", "wip_item_id", "wip_buffer_id", "operation_id", "issue_type", "issue_severity", "issue_description", "recommended_review_action", "auto_action_allowed", "advisory_only_flag"])


if __name__ == "__main__":
    outputs = build_wip_batch_tracking_outputs()
    print(f"WIP item rows: {len(outputs[0])}")
    print(f"WIP validation rows: {len(outputs[-1])}")
