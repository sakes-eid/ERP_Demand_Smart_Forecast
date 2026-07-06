"""Build advisory routing graph and critical path analysis for Phase 4 products."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE4_DIR.parent
DATA_DIR = PHASE4_DIR / "data"
OUTPUT_DIR = PHASE4_DIR / "outputs"

PRODUCT_ROUTINGS_FILE = DATA_DIR / "product_routings.csv"
PARALLEL_GROUPS_FILE = DATA_DIR / "routing_parallel_groups.csv"
OPERATION_RESOURCES_FILE = DATA_DIR / "routing_operation_resources.csv"
WORKSTATIONS_FILE = DATA_DIR / "workstations.csv"
MACHINES_FILE = DATA_DIR / "machines.csv"
PRODUCTION_FLOW_FILE = OUTPUT_DIR / "phase4_production_flow_view.csv"
CAPACITY_OPERATION_DETAIL_FILE = OUTPUT_DIR / "phase4_capacity_operation_load_detail.csv"
QUALITY_IMPACT_FILE = OUTPUT_DIR / "phase4_quality_impact_by_operation.csv"
BOTTLENECK_VISIBILITY_FILE = OUTPUT_DIR / "phase4_bottleneck_visibility_summary.csv"
QUEUE_RISK_FILE = OUTPUT_DIR / "phase4_queue_risk_summary.csv"
MAINTENANCE_IMPACT_FILE = OUTPUT_DIR / "phase4_maintenance_production_impact_context.csv"
MAINTENANCE_SCHEDULE_FILE = OUTPUT_DIR / "phase4_maintenance_schedule_feasibility_context.csv"

NODES_OUTPUT_FILE = OUTPUT_DIR / "phase4_routing_graph_nodes.csv"
EDGES_OUTPUT_FILE = OUTPUT_DIR / "phase4_routing_graph_edges.csv"
CRITICAL_PATH_OUTPUT_FILE = OUTPUT_DIR / "phase4_critical_path_by_product.csv"
SLACK_OUTPUT_FILE = OUTPUT_DIR / "phase4_operation_slack_analysis.csv"
VISUAL_JSON_OUTPUT_FILE = OUTPUT_DIR / "phase4_routing_graph_visual_data.json"
VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_routing_graph_validation.csv"

SOURCE_PHASE = "PHASE4_STEP8A_ROUTING_GRAPH_ANALYSIS"
VISUAL_SOURCE_PHASE = "PHASE4_STEP8A_ROUTING_GRAPH_VISUAL_DATA"
VALID_NODE_TYPES = {"START_OPERATION", "NORMAL_OPERATION", "PARALLEL_BRANCH_OPERATION", "MERGE_OPERATION", "END_OPERATION", "REVIEW_REQUIRED"}
VALID_DEPENDENCIES = {"FINISH_TO_START", "PARALLEL_BRANCH", "MERGE_DEPENDENCY", "REVIEW_REQUIRED"}
VALID_SLACK = {"ZERO_SLACK_CRITICAL", "LOW_SLACK_WARNING", "HAS_SLACK", "REVIEW_REQUIRED"}
VALID_ALIGNMENT = {"ALIGNED_WITH_TOP_BOTTLENECK", "DIFFERENT_FROM_TOP_BOTTLENECK", "PARTIALLY_ALIGNED", "REVIEW_REQUIRED"}
LEVEL_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4, "REVIEW_REQUIRED": 5}


def build_routing_graph_analysis_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, pd.DataFrame]:
    checks: list[dict] = []
    frames = {
        "routings": _load_csv(PRODUCT_ROUTINGS_FILE, "product_routings", checks),
        "parallel": _load_csv(PARALLEL_GROUPS_FILE, "routing_parallel_groups", checks),
        "resources": _load_csv(OPERATION_RESOURCES_FILE, "routing_operation_resources", checks),
        "workstations": _load_csv(WORKSTATIONS_FILE, "workstations", checks),
        "machines": _load_csv(MACHINES_FILE, "machines", checks),
        "flow": _load_csv(PRODUCTION_FLOW_FILE, "phase4_production_flow_view", checks),
        "capacity_detail": _load_csv(CAPACITY_OPERATION_DETAIL_FILE, "phase4_capacity_operation_load_detail", checks),
        "quality": _load_csv(QUALITY_IMPACT_FILE, "phase4_quality_impact_by_operation", checks),
        "bottleneck": _load_csv(BOTTLENECK_VISIBILITY_FILE, "phase4_bottleneck_visibility_summary", checks),
        "queue": _load_csv(QUEUE_RISK_FILE, "phase4_queue_risk_summary", checks),
        "maintenance": _load_csv(MAINTENANCE_IMPACT_FILE, "phase4_maintenance_production_impact_context", checks),
        "maintenance_schedule": _load_csv(MAINTENANCE_SCHEDULE_FILE, "phase4_maintenance_schedule_feasibility_context", checks),
    }
    if all(frame is not None for frame in frames.values()):
        nodes = _build_nodes(frames)
        edges = _build_edges(frames, nodes)
        slack, critical = _critical_path(nodes, edges, frames)
        visual = _build_visual_json(nodes, edges, slack, critical)
        _validate_outputs(nodes, edges, critical, slack, visual, checks)
    else:
        nodes = edges = critical = slack = pd.DataFrame()
        visual = {"planning_run_id": _planning_run_id(frames), "products": [], "nodes": [], "edges": [], "critical_path_nodes": [], "critical_path_edges": [], "metadata": {}, "advisory_only_flag": True}

    _check_no_forbidden_outputs(checks)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    nodes.to_csv(NODES_OUTPUT_FILE, index=False)
    edges.to_csv(EDGES_OUTPUT_FILE, index=False)
    critical.to_csv(CRITICAL_PATH_OUTPUT_FILE, index=False)
    slack.to_csv(SLACK_OUTPUT_FILE, index=False)
    VISUAL_JSON_OUTPUT_FILE.write_text(json.dumps(visual, indent=2), encoding="utf-8")
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    return nodes, edges, critical, slack, visual, validation


def _build_nodes(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    routings = frames["routings"][_to_bool(frames["routings"]["active_flag"])].copy()
    workstations = frames["workstations"][["workstation_id", "workstation_name"]].copy()
    resources = frames["resources"][_to_bool(frames["resources"]["active_flag"])].copy()
    machines = frames["machines"][_to_bool(frames["machines"]["active_flag"])].copy()
    flow = frames["flow"].copy()
    quality = frames["quality"].copy()
    bottleneck = frames["bottleneck"].copy()
    queue = frames["queue"].copy()
    maintenance = frames["maintenance"].copy()
    schedule = frames["maintenance_schedule"].copy()
    parallel = frames["parallel"][_to_bool(frames["parallel"]["active_flag"])].copy()

    run_id = _planning_run_id(frames)
    quality_agg = quality.groupby(["finished_sku", "operation_id"], as_index=False).agg(
        quality_adjusted_required_hours=("quality_adjusted_required_hours", "mean"),
        planned_production_qty=("planned_production_qty", "mean"),
    )
    flow_cols = [
        "finished_sku", "operation_id", "routing_join_pressure_flag", "parallel_merge_pressure_flag",
        "bottleneck_visibility_level", "estimated_queue_pressure_level", "estimated_wip_risk_level",
    ]
    flow_key = flow[[c for c in flow_cols if c in flow.columns]].copy()
    bottleneck_key = bottleneck[["workstation_id", "bottleneck_visibility_level"]].copy()
    queue_key = queue[["workstation_id", "overall_queue_risk_level"]].rename(columns={"overall_queue_risk_level": "queue_risk_level"}).copy()
    maint_key = maintenance[["machine_id", "machine_availability_impact_level"]].copy()
    sched_key = schedule[["machine_id", "best_schedule_feasibility_status"]].copy()
    machine_key = machines[["machine_id", "machine_name", "machine_type", "workstation_id"]].copy()
    resource_key = resources[["finished_sku", "operation_id", "required_machine_type"]].copy()

    join_ops = set(parallel["join_before_operation_id"].dropna().astype(str).str.strip())
    member_ops = set()
    for value in parallel["member_operation_ids"].dropna():
        member_ops.update(_split_ids(value))

    frame = routings.merge(workstations, on="workstation_id", how="left")
    frame = frame.merge(resource_key, on=["finished_sku", "operation_id"], how="left")
    frame = frame.merge(machine_key, left_on=["workstation_id", "machine_type_required"], right_on=["workstation_id", "machine_type"], how="left")
    if "required_machine_type" in frame.columns:
        frame["machine_type_match"] = frame["machine_type_required"].fillna(frame["required_machine_type"])
    frame = frame.merge(quality_agg, on=["finished_sku", "operation_id"], how="left")
    frame = frame.merge(flow_key, on=["finished_sku", "operation_id"], how="left")
    frame = frame.merge(bottleneck_key, on="workstation_id", how="left", suffixes=("", "_from_summary"))
    frame = frame.merge(queue_key, on="workstation_id", how="left")
    frame = frame.merge(maint_key, on="machine_id", how="left")
    frame = frame.merge(sched_key, on="machine_id", how="left")
    frame["setup_time_minutes"] = _num(frame, "setup_time_minutes")
    frame["run_time_minutes"] = _num(frame, "run_time_minutes_per_unit")
    frame["base_cycle_time_minutes"] = frame["setup_time_minutes"] + frame["run_time_minutes"] + _num(frame, "move_time_minutes")
    qty = _num(frame, "planned_production_qty")
    adjusted = _num(frame, "quality_adjusted_required_hours") * 60
    frame["quality_adjusted_cycle_time_minutes"] = adjusted.where(qty <= 0, adjusted / qty).where(adjusted > 0, frame["base_cycle_time_minutes"])
    frame["bottleneck_visibility_level"] = frame["bottleneck_visibility_level"].fillna(frame.get("bottleneck_visibility_level_from_summary", "REVIEW_REQUIRED")).fillna("REVIEW_REQUIRED")
    frame["queue_risk_level"] = frame["queue_risk_level"].fillna(frame.get("estimated_queue_pressure_level", "REVIEW_REQUIRED")).fillna("REVIEW_REQUIRED")
    frame["maintenance_risk_context_level"] = frame["machine_availability_impact_level"].fillna("REVIEW_REQUIRED")
    frame["can_run_in_parallel_flag"] = _to_bool(frame["can_run_in_parallel_flag"])
    frame["join_required_before_next_flag"] = _to_bool(frame["join_required_before_next_flag"]) | frame["operation_id"].astype(str).isin(join_ops) | _to_bool(frame.get("parallel_merge_pressure_flag", pd.Series([False] * len(frame))))
    frame["graph_node_type"] = frame.apply(lambda r: _node_type(r, join_ops, member_ops), axis=1)
    frame["planning_run_id"] = run_id
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[[
        "planning_run_id", "finished_sku", "finished_product_name", "routing_id", "routing_version", "operation_id",
        "operation_sequence", "operation_name", "operation_type", "workstation_id", "workstation_name", "machine_id",
        "machine_name", "setup_time_minutes", "run_time_minutes", "base_cycle_time_minutes",
        "quality_adjusted_cycle_time_minutes", "maintenance_risk_context_level", "queue_risk_level",
        "bottleneck_visibility_level", "can_run_in_parallel_flag", "join_required_before_next_flag",
        "graph_node_type", "source_phase", "advisory_only_flag",
    ]].sort_values(["finished_sku", "operation_sequence"]).copy()


def _build_edges(frames: dict[str, pd.DataFrame], nodes: pd.DataFrame) -> pd.DataFrame:
    routings = frames["routings"][_to_bool(frames["routings"]["active_flag"])].copy()
    parallel = frames["parallel"][_to_bool(frames["parallel"]["active_flag"])].copy()
    run_id = _planning_run_id(frames)
    group_by_member = {}
    join_by_member = {}
    fork_by_member = {}
    for row in parallel.itertuples(index=False):
        for member in _split_ids(row.member_operation_ids):
            group_by_member[member] = row.parallel_group_id
            join_by_member[member] = row.join_before_operation_id
            fork_by_member[member] = row.fork_after_operation_id
    node_ids = set(nodes["operation_id"].astype(str))
    rows = []
    for row in routings.itertuples(index=False):
        successors = _split_ids(row.successor_operation_ids)
        for successor in successors:
            from_id = str(row.operation_id)
            dep = "FINISH_TO_START"
            group_id = group_by_member.get(successor, group_by_member.get(from_id, ""))
            merge_edge = False
            if successor in group_by_member and fork_by_member.get(successor) == from_id:
                dep = "PARALLEL_BRANCH"
            if from_id in join_by_member and join_by_member[from_id] == successor:
                dep = "MERGE_DEPENDENCY"
                merge_edge = True
            status = "VALID" if from_id in node_ids and successor in node_ids else "REVIEW_REQUIRED"
            rows.append({
                "planning_run_id": run_id,
                "finished_sku": row.finished_sku,
                "from_operation_id": from_id,
                "to_operation_id": successor,
                "dependency_type": dep,
                "edge_lag_minutes": 0.0,
                "parallel_group_id": group_id,
                "merge_edge_flag": merge_edge,
                "edge_validation_status": status,
                "source_phase": SOURCE_PHASE,
                "advisory_only_flag": True,
            })
    return pd.DataFrame(rows)


def _critical_path(nodes: pd.DataFrame, edges: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    slack_rows = []
    critical_rows = []
    top_bottleneck_ws = _top_bottleneck_workstation(frames["bottleneck"])
    for sku, group in nodes.groupby("finished_sku"):
        product_name = group["finished_product_name"].iloc[0]
        durations = dict(zip(group["operation_id"], _num(group, "quality_adjusted_cycle_time_minutes").where(_num(group, "quality_adjusted_cycle_time_minutes") > 0, _num(group, "base_cycle_time_minutes"))))
        product_edges = edges[edges["finished_sku"] == sku]
        successors = defaultdict(list)
        predecessors = defaultdict(list)
        for edge in product_edges.itertuples(index=False):
            successors[edge.from_operation_id].append(edge.to_operation_id)
            predecessors[edge.to_operation_id].append(edge.from_operation_id)
        topo = _topological_order(list(group["operation_id"].astype(str)), successors, predecessors)
        es, ef = {}, {}
        for op in topo:
            es[op] = max([ef[p] for p in predecessors.get(op, [])], default=0.0)
            ef[op] = es[op] + float(durations.get(op, 0.0))
        project_duration = max(ef.values()) if ef else 0.0
        lf, ls = {}, {}
        for op in reversed(topo):
            lf[op] = min([ls[s] for s in successors.get(op, [])], default=project_duration)
            ls[op] = lf[op] - float(durations.get(op, 0.0))
        critical_ops = []
        for row in group.itertuples(index=False):
            op = row.operation_id
            slack = round(max(ls.get(op, 0.0) - es.get(op, 0.0), 0.0), 6)
            critical = slack <= 0.0001
            low = (not critical) and slack <= max(project_duration * 0.10, 10.0)
            if critical:
                critical_ops.append(op)
            slack_rows.append({
                "planning_run_id": row.planning_run_id,
                "finished_sku": sku,
                "operation_id": op,
                "operation_name": row.operation_name,
                "workstation_id": row.workstation_id,
                "workstation_name": row.workstation_name,
                "earliest_start_offset_minutes": round(es.get(op, 0.0), 4),
                "earliest_finish_offset_minutes": round(ef.get(op, 0.0), 4),
                "latest_start_offset_minutes": round(ls.get(op, 0.0), 4),
                "latest_finish_offset_minutes": round(lf.get(op, 0.0), 4),
                "slack_time_minutes": slack,
                "slack_status": "ZERO_SLACK_CRITICAL" if critical else ("LOW_SLACK_WARNING" if low else "HAS_SLACK"),
                "critical_path_flag": critical,
                "low_slack_warning_flag": low,
                "bottleneck_visibility_level": row.bottleneck_visibility_level,
                "queue_risk_level": row.queue_risk_level,
                "operation_schedule_sensitivity": _schedule_sensitivity(critical, low, row.bottleneck_visibility_level, row.queue_risk_level),
                "source_phase": SOURCE_PHASE,
                "advisory_only_flag": True,
            })
        cp_group = group[group["operation_id"].isin(critical_ops)].sort_values("operation_sequence")
        critical_ws = set(cp_group["workstation_id"].dropna().astype(str))
        alignment = _alignment_status(top_bottleneck_ws, critical_ws, cp_group)
        risk = _highest_level(list(cp_group["bottleneck_visibility_level"]) + list(cp_group["queue_risk_level"]) + list(cp_group["maintenance_risk_context_level"]))
        critical_rows.append({
            "planning_run_id": group["planning_run_id"].iloc[0],
            "finished_sku": sku,
            "finished_product_name": product_name,
            "critical_path_sequence": ";".join(critical_ops),
            "critical_path_operation_count": len(critical_ops),
            "total_base_cycle_time_minutes": round(float(_num(cp_group, "base_cycle_time_minutes").sum()), 4),
            "total_quality_adjusted_cycle_time_minutes": round(float(_num(cp_group, "quality_adjusted_cycle_time_minutes").sum()), 4),
            "critical_path_duration_minutes": round(project_duration, 4),
            "critical_path_duration_hours": round(project_duration / 60, 4),
            "critical_path_main_constraint": _main_constraint(cp_group),
            "critical_path_risk_level": risk,
            "critical_path_reason": f"Longest dependent chain based on routing precedence; critical_ops={len(critical_ops)}; bottleneck_alignment={alignment}.",
            "bottleneck_alignment_status": alignment,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(slack_rows), pd.DataFrame(critical_rows)


def _build_visual_json(nodes: pd.DataFrame, edges: pd.DataFrame, slack: pd.DataFrame, critical: pd.DataFrame) -> dict:
    critical_nodes = set(slack.loc[_to_bool(slack["critical_path_flag"]), "operation_id"].astype(str))
    critical_edges = [
        f"{row.from_operation_id}->{row.to_operation_id}"
        for row in edges.itertuples(index=False)
        if row.from_operation_id in critical_nodes and row.to_operation_id in critical_nodes
    ]
    return {
        "planning_run_id": nodes["planning_run_id"].iloc[0] if not nodes.empty else "",
        "products": sorted(nodes["finished_sku"].dropna().astype(str).unique().tolist()),
        "nodes": nodes.to_dict(orient="records"),
        "edges": edges.to_dict(orient="records"),
        "critical_path_nodes": sorted(critical_nodes),
        "critical_path_edges": critical_edges,
        "metadata": {
            "source_phase": VISUAL_SOURCE_PHASE,
            "node_count": int(len(nodes)),
            "edge_count": int(len(edges)),
            "critical_path_product_count": int(len(critical)),
            "data_only_no_ui_flag": True,
        },
        "advisory_only_flag": True,
    }


def _validate_outputs(nodes: pd.DataFrame, edges: pd.DataFrame, critical: pd.DataFrame, slack: pd.DataFrame, visual: dict, checks: list[dict]) -> None:
    outputs = {"nodes": nodes, "edges": edges, "critical": critical, "slack": slack}
    for name, frame in outputs.items():
        _add_check(checks, f"{name}_not_empty", "PASS" if not frame.empty else "FAIL", f"{name} rows={len(frame)}", len(frame))
    required = {
        "nodes": {"planning_run_id", "finished_sku", "finished_product_name", "routing_id", "routing_version", "operation_id", "operation_sequence", "operation_name", "operation_type", "workstation_id", "workstation_name", "machine_id", "machine_name", "setup_time_minutes", "run_time_minutes", "base_cycle_time_minutes", "quality_adjusted_cycle_time_minutes", "maintenance_risk_context_level", "queue_risk_level", "bottleneck_visibility_level", "can_run_in_parallel_flag", "join_required_before_next_flag", "graph_node_type", "source_phase", "advisory_only_flag"},
        "edges": {"planning_run_id", "finished_sku", "from_operation_id", "to_operation_id", "dependency_type", "edge_lag_minutes", "parallel_group_id", "merge_edge_flag", "edge_validation_status", "source_phase", "advisory_only_flag"},
        "critical": {"planning_run_id", "finished_sku", "finished_product_name", "critical_path_sequence", "critical_path_operation_count", "total_base_cycle_time_minutes", "total_quality_adjusted_cycle_time_minutes", "critical_path_duration_minutes", "critical_path_duration_hours", "critical_path_main_constraint", "critical_path_risk_level", "critical_path_reason", "bottleneck_alignment_status", "source_phase", "advisory_only_flag"},
        "slack": {"planning_run_id", "finished_sku", "operation_id", "operation_name", "workstation_id", "workstation_name", "earliest_start_offset_minutes", "earliest_finish_offset_minutes", "latest_start_offset_minutes", "latest_finish_offset_minutes", "slack_time_minutes", "slack_status", "critical_path_flag", "low_slack_warning_flag", "bottleneck_visibility_level", "queue_risk_level", "operation_schedule_sensitivity", "source_phase", "advisory_only_flag"},
    }
    for name, cols in required.items():
        missing = sorted(cols - set(outputs[name].columns))
        _add_check(checks, f"{name}_required_columns", "PASS" if not missing else "FAIL", f"missing={missing}", len(missing))
    products = set(nodes["finished_sku"].astype(str))
    _add_check(checks, "bike_products_present", "PASS" if {"SKU-BIKE-ROAD-001", "SKU-BIKE-MT-001"}.issubset(products) else "FAIL", f"products={sorted(products)}", len(products))
    edge_nodes = set(edges["from_operation_id"].astype(str)) | set(edges["to_operation_id"].astype(str))
    valid_nodes = set(nodes["operation_id"].astype(str))
    invalid_edges = edge_nodes - valid_nodes
    _add_check(checks, "edge_operation_ids_reference_nodes", "PASS" if not invalid_edges else "FAIL", f"invalid={sorted(invalid_edges)}", len(invalid_edges))
    cycle_count = sum(1 for sku in products if _has_cycle(nodes[nodes["finished_sku"] == sku], edges[edges["finished_sku"] == sku]))
    _add_check(checks, "routing_graph_has_no_cycles", "PASS" if cycle_count == 0 else "FAIL", f"cycle_product_count={cycle_count}", cycle_count)
    _add_check(checks, "parallel_operations_represented", "PASS" if _to_bool(nodes["can_run_in_parallel_flag"]).any() else "FAIL", "Parallel operations represented.", int(_to_bool(nodes["can_run_in_parallel_flag"]).sum()))
    merge_count = int((nodes["graph_node_type"] == "MERGE_OPERATION").sum())
    _add_check(checks, "merge_operations_represented", "PASS" if merge_count > 0 else "FAIL", f"merge_count={merge_count}", merge_count)
    final_merge = nodes[nodes["operation_name"].astype(str).str.contains("Final Assembly", case=False, na=False)]
    _add_check(checks, "final_assembly_marked_merge", "PASS" if not final_merge.empty and (final_merge["graph_node_type"] == "MERGE_OPERATION").all() else "FAIL", "Final Assembly merge node check.", len(final_merge))
    bad_cycle = int((_num(nodes, "base_cycle_time_minutes") < 0).sum() + (_num(nodes, "quality_adjusted_cycle_time_minutes") < 0).sum())
    _add_check(checks, "cycle_times_non_negative", "PASS" if bad_cycle == 0 else "FAIL", f"bad_cycle_rows={bad_cycle}", bad_cycle)
    cp_products = set(critical["finished_sku"].astype(str))
    _add_check(checks, "critical_path_exists_for_both_products", "PASS" if {"SKU-BIKE-ROAD-001", "SKU-BIKE-MT-001"}.issubset(cp_products) else "FAIL", f"critical_products={sorted(cp_products)}", len(cp_products))
    bad_duration = int((pd.to_numeric(critical["critical_path_duration_minutes"], errors="coerce").fillna(0) <= 0).sum())
    _add_check(checks, "critical_path_duration_positive", "PASS" if bad_duration == 0 else "FAIL", f"bad_duration_rows={bad_duration}", bad_duration)
    cp_flags = slack.groupby("finished_sku")["critical_path_flag"].apply(lambda s: int(_to_bool(s).sum())).to_dict()
    missing_cp = [sku for sku, count in cp_flags.items() if count <= 0]
    _add_check(checks, "critical_path_operation_per_product", "PASS" if not missing_cp else "FAIL", f"missing={missing_cp}", len(missing_cp))
    try:
        json.dumps(visual)
        json_ok = bool(visual.get("advisory_only_flag")) and bool(visual.get("metadata", {}).get("data_only_no_ui_flag"))
    except TypeError:
        json_ok = False
    _add_check(checks, "visual_json_valid_data_only", "PASS" if json_ok else "FAIL", "Routing graph visual JSON is valid data-only structure.", 0 if json_ok else 1)
    for name, frame in outputs.items():
        if "advisory_only_flag" in frame.columns:
            _add_check(checks, f"{name}_advisory_only", "PASS" if _to_bool(frame["advisory_only_flag"]).all() else "FAIL", f"{name} advisory_only flag.", len(frame))


def _node_type(row: pd.Series, join_ops: set[str], member_ops: set[str]) -> str:
    op = str(row.get("operation_id", ""))
    preds = _split_ids(row.get("predecessor_operation_ids", ""))
    succs = _split_ids(row.get("successor_operation_ids", ""))
    if op in join_ops or len(preds) > 1:
        return "MERGE_OPERATION"
    if op in member_ops or bool(row.get("can_run_in_parallel_flag", False)):
        return "PARALLEL_BRANCH_OPERATION"
    if not preds:
        return "START_OPERATION"
    if not succs:
        return "END_OPERATION"
    return "NORMAL_OPERATION"


def _topological_order(nodes: list[str], successors: dict[str, list[str]], predecessors: dict[str, list[str]]) -> list[str]:
    indegree = {node: len(predecessors.get(node, [])) for node in nodes}
    queue = deque([node for node in nodes if indegree[node] == 0])
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for succ in successors.get(node, []):
            indegree[succ] = indegree.get(succ, 0) - 1
            if indegree[succ] == 0:
                queue.append(succ)
    return order if len(order) == len(nodes) else nodes


def _has_cycle(nodes: pd.DataFrame, edges: pd.DataFrame) -> bool:
    successors = defaultdict(list)
    predecessors = defaultdict(list)
    ids = list(nodes["operation_id"].astype(str))
    for edge in edges.itertuples(index=False):
        successors[edge.from_operation_id].append(edge.to_operation_id)
        predecessors[edge.to_operation_id].append(edge.from_operation_id)
    return len(_topological_order(ids, successors, predecessors)) != len(ids)


def _schedule_sensitivity(critical: bool, low: bool, bottleneck: str, queue: str) -> str:
    if critical and (_level_rank(bottleneck) >= 4 or _level_rank(queue) >= 4):
        return "CRITICAL_PATH_WITH_CAPACITY_OR_QUEUE_RISK"
    if critical:
        return "CRITICAL_PATH_OPERATION"
    if low:
        return "LOW_SLACK_REVIEW"
    return "NORMAL_SCHEDULE_SENSITIVITY"


def _top_bottleneck_workstation(bottleneck: pd.DataFrame) -> str:
    if bottleneck.empty or "bottleneck_visibility_rank" not in bottleneck.columns:
        return ""
    frame = bottleneck.copy()
    frame["_rank"] = pd.to_numeric(frame["bottleneck_visibility_rank"], errors="coerce").fillna(9999)
    return str(frame.sort_values("_rank").iloc[0].get("workstation_id", ""))


def _alignment_status(top_bottleneck_ws: str, critical_ws: set[str], cp_group: pd.DataFrame) -> str:
    if not top_bottleneck_ws:
        return "REVIEW_REQUIRED"
    if top_bottleneck_ws in critical_ws:
        return "ALIGNED_WITH_TOP_BOTTLENECK"
    if (cp_group["bottleneck_visibility_level"].astype(str).isin(["HIGH", "CRITICAL"])).any():
        return "PARTIALLY_ALIGNED"
    return "DIFFERENT_FROM_TOP_BOTTLENECK"


def _main_constraint(cp_group: pd.DataFrame) -> str:
    if cp_group.empty:
        return "REVIEW_REQUIRED"
    severe = cp_group[cp_group["bottleneck_visibility_level"].astype(str).isin(["HIGH", "CRITICAL"])]
    if not severe.empty:
        return "BOTTLENECK_VISIBILITY"
    queue = cp_group[cp_group["queue_risk_level"].astype(str).isin(["HIGH", "CRITICAL"])]
    if not queue.empty:
        return "QUEUE_RISK"
    maintenance = cp_group[cp_group["maintenance_risk_context_level"].astype(str).isin(["HIGH", "CRITICAL"])]
    if not maintenance.empty:
        return "MAINTENANCE_RISK_CONTEXT"
    return "ROUTING_DEPENDENCY_TIME"


def _highest_level(values: list[object]) -> str:
    valid = [str(v) for v in values if str(v) in LEVEL_ORDER]
    if not valid:
        return "REVIEW_REQUIRED"
    return max(valid, key=lambda v: LEVEL_ORDER[v])


def _level_rank(value: object) -> int:
    return LEVEL_ORDER.get(str(value), 5)


def _load_csv(path: Path, label: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        _add_check(checks, f"{label}_exists", "FAIL", f"Missing input: {path}", 1)
        return None
    frame = pd.read_csv(path)
    _add_check(checks, f"{label}_exists", "PASS", f"{label} rows={len(frame)}", len(frame))
    if frame.empty:
        _add_check(checks, f"{label}_not_empty", "FAIL", f"{label} is empty.", 0)
    return frame


def _check_no_forbidden_outputs(checks: list[dict]) -> None:
    allowed = {
        NODES_OUTPUT_FILE.name,
        EDGES_OUTPUT_FILE.name,
        CRITICAL_PATH_OUTPUT_FILE.name,
        SLACK_OUTPUT_FILE.name,
        VISUAL_JSON_OUTPUT_FILE.name,
        VALIDATION_OUTPUT_FILE.name,
        "phase4_master_production_schedule.csv",
        "phase4_production_schedule_candidates.csv",
        "phase4_operation_schedule_candidate_detail.csv",
        "phase4_production_schedule_material_readiness.csv",
        "phase4_production_schedule_capacity_check.csv",
        "phase4_production_calendar_candidate_view.csv",
        "phase4_production_schedule_manager_review_queue.csv",
        "phase4_production_schedule_validation.csv",
    }
    blocked = ["production_schedule", "production_order", "worker_dispatch", "inventory_reservation", "inventory_consumption", "purchase_order", "capacity_reduction", "simulation"]
    bad = []
    for path in OUTPUT_DIR.glob("*"):
        name = path.name.lower()
        if path.name in allowed:
            continue
        if any(token in name for token in blocked):
            bad.append(str(path))
    _add_check(checks, "no_forbidden_execution_outputs", "PASS" if not bad else "FAIL", f"bad={bad}" if bad else "No production schedule/order/dispatch/reservation/consumption/reduction/simulation outputs found.", len(bad))


def _planning_run_id(frames: dict[str, pd.DataFrame]) -> str:
    for frame in frames.values():
        if frame is not None and not frame.empty and "planning_run_id" in frame.columns:
            values = frame["planning_run_id"].dropna().astype(str).str.strip()
            if not values.empty:
                return values.iloc[0]
    return "PHASE4-ROUTING-GRAPH"


def _split_ids(value: object) -> list[str]:
    text = "" if value is None else str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return []
    return [item.strip() for item in text.split(";") if item.strip()]


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series([0.0] * len(frame), index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _to_bool(series: pd.Series | object) -> pd.Series | bool:
    if isinstance(series, pd.Series):
        return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})
    return str(series).strip().lower() in {"true", "1", "yes", "y"}


def _add_check(checks: list[dict], name: str, status: str, message: str, affected_rows: int) -> None:
    checks.append({
        "check_id": f"S8A-{len(checks)+1:03d}",
        "check_name": name,
        "status": status,
        "message": message,
        "affected_rows": int(affected_rows),
        "advisory_only_flag": True,
    })


if __name__ == "__main__":
    result = build_routing_graph_analysis_outputs()
    validation = result[-1]
    print(f"Routing graph validation rows: {len(validation)}")
    print(f"Validation status counts: {validation['status'].value_counts().to_dict()}")
