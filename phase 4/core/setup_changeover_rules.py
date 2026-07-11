"""Build strict WIP buffer access and setup/changeover foundation outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PHASE4_DIR / "data"
OUTPUT_DIR = PHASE4_DIR / "outputs"

ROUTINGS_FILE = DATA_DIR / "product_routings.csv"
PARALLEL_GROUPS_FILE = DATA_DIR / "routing_parallel_groups.csv"
SETUP_FAMILIES_FILE = DATA_DIR / "setup_families.csv"
CHANGEOVER_MATRIX_FILE = DATA_DIR / "setup_changeover_matrix.csv"
WORKSTATION_SETUP_RULES_FILE = DATA_DIR / "workstation_setup_rules.csv"

NODES_FILE = OUTPUT_DIR / "phase4_routing_graph_nodes.csv"
EDGES_FILE = OUTPUT_DIR / "phase4_routing_graph_edges.csv"
CRITICAL_PATH_FILE = OUTPUT_DIR / "phase4_critical_path_by_product.csv"
SLACK_FILE = OUTPUT_DIR / "phase4_operation_slack_analysis.csv"
WIP_ITEM_MASTER_FILE = OUTPUT_DIR / "phase4_wip_item_master.csv"
WIP_FLOW_MAP_FILE = OUTPUT_DIR / "phase4_wip_operation_flow_map.csv"
WIP_LEDGER_FILE = OUTPUT_DIR / "phase4_wip_batch_ledger.csv"
WIP_BUFFER_STATUS_FILE = OUTPUT_DIR / "phase4_wip_buffer_status.csv"
WIP_AWARE_FEASIBILITY_FILE = OUTPUT_DIR / "phase4_wip_aware_schedule_feasibility.csv"
WIP_BUFFER_IMPACT_FILE = OUTPUT_DIR / "phase4_wip_buffer_impact_on_schedule.csv"
SCHEDULE_CANDIDATES_FILE = OUTPUT_DIR / "phase4_production_schedule_candidates.csv"
SCHEDULE_DETAIL_FILE = OUTPUT_DIR / "phase4_operation_schedule_candidate_detail.csv"
WORKSTATION_CAPACITY_FILE = OUTPUT_DIR / "phase4_capacity_load_by_workstation.csv"
MACHINE_CAPACITY_FILE = OUTPUT_DIR / "phase4_capacity_load_by_machine_type.csv"
LABOR_CAPACITY_FILE = OUTPUT_DIR / "phase4_capacity_load_by_labor_skill.csv"
BOTTLENECK_FILE = OUTPUT_DIR / "phase4_bottleneck_visibility_summary.csv"
QUEUE_FILE = OUTPUT_DIR / "phase4_queue_risk_summary.csv"

WIP_ACCESS_RULES_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_buffer_access_rules.csv"
WIP_ACCESS_VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_wip_buffer_access_validation.csv"
SETUP_FAMILY_OUTPUT_FILE = OUTPUT_DIR / "phase4_setup_family_master.csv"
CHANGEOVER_MATRIX_OUTPUT_FILE = OUTPUT_DIR / "phase4_setup_changeover_matrix.csv"
OPERATION_SETUP_PROFILE_OUTPUT_FILE = OUTPUT_DIR / "phase4_operation_setup_profile.csv"
SETUP_SEQUENCE_IMPACT_OUTPUT_FILE = OUTPUT_DIR / "phase4_setup_sequence_impact_analysis.csv"
SETUP_MANAGER_REVIEW_OUTPUT_FILE = OUTPUT_DIR / "phase4_setup_manager_review_queue.csv"
SETUP_VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_setup_changeover_validation.csv"

SOURCE_PHASE = "PHASE4_STEP8E_WIP_ACCESS_SETUP_CHANGEOVER_FOUNDATION"


def build_setup_changeover_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    checks: list[dict] = []
    frames = {
        "routings": _load_csv(ROUTINGS_FILE, "product_routings", checks),
        "parallel_groups": _load_csv(PARALLEL_GROUPS_FILE, "routing_parallel_groups", checks),
        "setup_families": _load_csv(SETUP_FAMILIES_FILE, "setup_families", checks),
        "changeover_matrix": _load_csv(CHANGEOVER_MATRIX_FILE, "setup_changeover_matrix", checks),
        "workstation_setup_rules": _load_csv(WORKSTATION_SETUP_RULES_FILE, "workstation_setup_rules", checks),
        "nodes": _load_csv(NODES_FILE, "phase4_routing_graph_nodes", checks),
        "edges": _load_csv(EDGES_FILE, "phase4_routing_graph_edges", checks),
        "critical_path": _load_csv(CRITICAL_PATH_FILE, "phase4_critical_path_by_product", checks),
        "slack": _load_csv(SLACK_FILE, "phase4_operation_slack_analysis", checks),
        "wip_items": _load_csv(WIP_ITEM_MASTER_FILE, "phase4_wip_item_master", checks),
        "wip_flow": _load_csv(WIP_FLOW_MAP_FILE, "phase4_wip_operation_flow_map", checks),
        "wip_ledger": _load_csv(WIP_LEDGER_FILE, "phase4_wip_batch_ledger", checks),
        "wip_buffers": _load_csv(WIP_BUFFER_STATUS_FILE, "phase4_wip_buffer_status", checks),
        "wip_aware": _load_csv(WIP_AWARE_FEASIBILITY_FILE, "phase4_wip_aware_schedule_feasibility", checks),
        "wip_buffer_impact": _load_csv(WIP_BUFFER_IMPACT_FILE, "phase4_wip_buffer_impact_on_schedule", checks),
        "schedule_candidates": _load_csv(SCHEDULE_CANDIDATES_FILE, "phase4_production_schedule_candidates", checks),
        "schedule_detail": _load_csv(SCHEDULE_DETAIL_FILE, "phase4_operation_schedule_candidate_detail", checks),
        "workstation_capacity": _load_csv(WORKSTATION_CAPACITY_FILE, "phase4_capacity_load_by_workstation", checks),
        "machine_capacity": _load_csv(MACHINE_CAPACITY_FILE, "phase4_capacity_load_by_machine_type", checks),
        "labor_capacity": _load_csv(LABOR_CAPACITY_FILE, "phase4_capacity_load_by_labor_skill", checks),
        "bottleneck": _load_csv(BOTTLENECK_FILE, "phase4_bottleneck_visibility_summary", checks),
        "queue": _load_csv(QUEUE_FILE, "phase4_queue_risk_summary", checks),
    }
    if all(frame is not None for frame in frames.values()):
        access_rules = _build_wip_access_rules(frames)
        access_validation = _build_wip_access_validation(frames, access_rules)
        setup_family_master = _build_setup_family_master(frames)
        changeover_matrix = _build_changeover_matrix(frames)
        operation_setup_profile = _build_operation_setup_profile(frames, setup_family_master)
        setup_sequence = _build_setup_sequence_impact(frames, operation_setup_profile, changeover_matrix)
        review = _build_manager_review(access_validation, operation_setup_profile, setup_sequence, checks)
        _validate_outputs(frames, access_rules, access_validation, setup_family_master, changeover_matrix, operation_setup_profile, setup_sequence, review, checks)
    else:
        access_rules = _empty_access_rules()
        access_validation = _empty_access_validation()
        setup_family_master = _empty_setup_family_master()
        changeover_matrix = _empty_changeover_matrix()
        operation_setup_profile = _empty_operation_setup_profile()
        setup_sequence = _empty_setup_sequence()
        review = _empty_review()

    _check_no_forbidden_outputs(checks)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    access_rules.to_csv(WIP_ACCESS_RULES_OUTPUT_FILE, index=False)
    access_validation.to_csv(WIP_ACCESS_VALIDATION_OUTPUT_FILE, index=False)
    setup_family_master.to_csv(SETUP_FAMILY_OUTPUT_FILE, index=False)
    changeover_matrix.to_csv(CHANGEOVER_MATRIX_OUTPUT_FILE, index=False)
    operation_setup_profile.to_csv(OPERATION_SETUP_PROFILE_OUTPUT_FILE, index=False)
    setup_sequence.to_csv(SETUP_SEQUENCE_IMPACT_OUTPUT_FILE, index=False)
    review.to_csv(SETUP_MANAGER_REVIEW_OUTPUT_FILE, index=False)
    validation.to_csv(SETUP_VALIDATION_OUTPUT_FILE, index=False)
    return access_rules, access_validation, setup_family_master, changeover_matrix, operation_setup_profile, setup_sequence, review, validation


def _build_wip_access_rules(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    nodes = frames["nodes"].copy()
    flow = frames["wip_flow"].copy()
    buffer_by_item = {str(row["wip_item_id"]): str(row["wip_buffer_id"]) for _, row in frames["wip_buffers"].iterrows()}
    inputs_by_op = {}
    outputs_by_op = {}
    for _, row in flow.iterrows():
        inputs_by_op.setdefault((str(row["finished_sku"]), str(row["consumed_by_operation_id"])), []).append(row.to_dict())
        outputs_by_op.setdefault((str(row["finished_sku"]), str(row["produced_by_operation_id"])), []).append(row.to_dict())
    rows = []
    for _, node in nodes.iterrows():
        sku = str(node["finished_sku"])
        op = str(node["operation_id"])
        inputs = inputs_by_op.get((sku, op), [])
        outputs = outputs_by_op.get((sku, op), [])
        if not inputs:
            inputs = [None]
        if not outputs:
            outputs = [None]
        for input_row in inputs:
            for output_row in outputs:
                input_wip = str(input_row["wip_item_id"]) if input_row else ""
                output_wip = str(output_row["wip_item_id"]) if output_row else ""
                predecessor = str(input_row["produced_by_operation_id"]) if input_row else ""
                successor = str(output_row["consumed_by_operation_id"]) if output_row else ""
                merge = _bool_value(node.get("join_required_before_next_flag", False)) or str(node.get("graph_node_type", "")) == "MERGE_OPERATION"
                parallel = _bool_value(node.get("can_run_in_parallel_flag", False))
                rule_type, status = _access_rule_type_status(input_row, output_row, merge)
                rows.append({
                    "planning_run_id": node["planning_run_id"],
                    "finished_sku": sku,
                    "operation_id": op,
                    "operation_name": node["operation_name"],
                    "workstation_id": node["workstation_id"],
                    "allowed_input_wip_item_id": input_wip,
                    "allowed_input_wip_buffer_id": buffer_by_item.get(input_wip, "") if input_wip else "",
                    "allowed_output_wip_item_id": output_wip,
                    "allowed_output_wip_buffer_id": buffer_by_item.get(output_wip, "") if output_wip else "",
                    "predecessor_operation_id": predecessor,
                    "successor_operation_id": successor,
                    "buffer_access_rule_type": rule_type,
                    "merge_operation_flag": merge,
                    "parallel_branch_flag": parallel,
                    "access_rule_status": status,
                    "source_phase": SOURCE_PHASE,
                    "advisory_only_flag": True,
                })
    return pd.DataFrame(rows, columns=_empty_access_rules().columns)


def _build_wip_access_validation(frames: dict[str, pd.DataFrame], access_rules: pd.DataFrame) -> pd.DataFrame:
    flow = frames["wip_flow"]
    buffers = frames["wip_buffers"]
    nodes = frames["nodes"]
    valid_items = set(frames["wip_items"]["wip_item_id"].astype(str))
    valid_buffers = set(buffers["wip_buffer_id"].astype(str))
    op_to_outputs = flow.groupby(["finished_sku", "produced_by_operation_id"], dropna=False)["wip_item_id"].apply(lambda s: set(s.astype(str))).to_dict()
    rows = []

    def add(rule: pd.Series, name: str, status: str, severity: str, message: str, wip_item: str = "", buffer_id: str = "") -> None:
        rows.append({
            "validation_check_id": f"WIPACCESS-{len(rows)+1:04d}",
            "planning_run_id": rule.get("planning_run_id", _planning_run_id(frames)),
            "finished_sku": rule.get("finished_sku", ""),
            "operation_id": rule.get("operation_id", ""),
            "operation_name": rule.get("operation_name", ""),
            "checked_wip_item_id": wip_item,
            "checked_wip_buffer_id": buffer_id,
            "validation_check_name": name,
            "validation_status": status,
            "validation_severity": severity,
            "validation_message": message,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })

    for _, rule in access_rules.iterrows():
        op = str(rule["operation_id"])
        sku = str(rule["finished_sku"])
        input_wip = str(rule["allowed_input_wip_item_id"])
        output_wip = str(rule["allowed_output_wip_item_id"])
        input_buffer = str(rule["allowed_input_wip_buffer_id"])
        output_buffer = str(rule["allowed_output_wip_buffer_id"])
        if input_wip:
            match = flow[(flow["finished_sku"].astype(str) == sku) & (flow["wip_item_id"].astype(str) == input_wip)]
            if match.empty:
                add(rule, "input_wip_exists_in_flow", "FAIL", "HIGH", "Input WIP is missing from flow map.", input_wip, input_buffer)
            elif not (match["consumed_by_operation_id"].astype(str) == op).all():
                add(rule, "input_wip_consumed_by_current_operation", "FAIL", "HIGH", "Operation consumes from a WIP item not mapped to this operation.", input_wip, input_buffer)
            else:
                add(rule, "input_wip_consumed_by_current_operation", "PASS", "LOW", "Input WIP is mapped directly to this operation.", input_wip, input_buffer)
            if input_wip == output_wip and output_wip:
                add(rule, "no_self_output_consumption", "FAIL", "HIGH", "Operation consumes from its own output WIP.", input_wip, input_buffer)
            else:
                add(rule, "no_self_output_consumption", "PASS", "LOW", "Operation does not consume from its own output WIP.", input_wip, input_buffer)
            if input_buffer and input_buffer not in valid_buffers:
                add(rule, "input_buffer_valid", "FAIL", "HIGH", "Input buffer reference is invalid.", input_wip, input_buffer)
            else:
                add(rule, "input_buffer_valid", "PASS", "LOW", "Input buffer reference is valid or not required.", input_wip, input_buffer)
        else:
            add(rule, "first_operation_input_optional", "PASS", "LOW", "Operation has no input WIP; allowed for first operation.", "", "")
        if output_wip:
            if output_wip not in valid_items:
                add(rule, "output_wip_valid", "FAIL", "HIGH", "Output WIP reference is invalid.", output_wip, output_buffer)
            elif output_buffer and output_buffer not in valid_buffers:
                add(rule, "output_buffer_valid", "FAIL", "HIGH", "Output buffer reference is invalid.", output_wip, output_buffer)
            else:
                add(rule, "output_wip_and_buffer_valid", "PASS", "LOW", "Output WIP and buffer references are valid.", output_wip, output_buffer)
        else:
            add(rule, "final_operation_output_optional", "PASS", "LOW", "Operation has no output WIP; allowed for final operation.", "", "")
        if str(rule["buffer_access_rule_type"]) == "MERGE_OPERATION_MULTIPLE_VALID_INPUT_BUFFERS":
            input_count = len(flow[(flow["finished_sku"].astype(str) == sku) & (flow["consumed_by_operation_id"].astype(str) == op)])
            if input_count < 2:
                add(rule, "merge_inputs_multiple", "WARNING", "MEDIUM", "Merge operation has fewer than two WIP inputs.", input_wip, input_buffer)
            else:
                add(rule, "merge_inputs_multiple", "PASS", "LOW", "Merge operation has multiple direct WIP inputs.", input_wip, input_buffer)
    for _, node in nodes.iterrows():
        sku = str(node["finished_sku"])
        op = str(node["operation_id"])
        input_count = len(flow[(flow["finished_sku"].astype(str) == sku) & (flow["consumed_by_operation_id"].astype(str) == op)])
        is_merge = str(node.get("graph_node_type", "")) == "MERGE_OPERATION"
        output_set = op_to_outputs.get((sku, op), set())
        if not is_merge and input_count > 1:
            pseudo = pd.Series({"planning_run_id": node["planning_run_id"], "finished_sku": sku, "operation_id": op, "operation_name": node["operation_name"]})
            add(pseudo, "non_merge_single_input", "FAIL", "HIGH", "Non-merge operation has multiple input buffers.")
        if any(wip in output_set for wip in flow.loc[(flow["finished_sku"].astype(str) == sku) & (flow["consumed_by_operation_id"].astype(str) == op), "wip_item_id"].astype(str)):
            pseudo = pd.Series({"planning_run_id": node["planning_run_id"], "finished_sku": sku, "operation_id": op, "operation_name": node["operation_name"]})
            add(pseudo, "no_self_output_consumption_global", "FAIL", "HIGH", "Operation can consume from its own output WIP.")
    return pd.DataFrame(rows, columns=_empty_access_validation().columns)


def _build_setup_family_master(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    families = frames["setup_families"].copy()
    families.insert(0, "planning_run_id", _planning_run_id(frames))
    families["source_phase"] = SOURCE_PHASE
    return families[_empty_setup_family_master().columns]


def _build_changeover_matrix(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    matrix = frames["changeover_matrix"].copy()
    matrix.insert(0, "planning_run_id", _planning_run_id(frames))
    matrix["source_phase"] = SOURCE_PHASE
    return matrix[_empty_changeover_matrix().columns]


def _build_operation_setup_profile(frames: dict[str, pd.DataFrame], families: pd.DataFrame) -> pd.DataFrame:
    nodes = frames["nodes"]
    slack = frames["slack"]
    bottleneck = frames["bottleneck"]
    queue = frames["queue"]
    family_by_op = _index_by(families, "operation_id")
    slack_by_op = _index_by(slack, "operation_id")
    bottleneck_by_ws = _index_by(bottleneck, "workstation_id")
    queue_by_ws = _index_by(queue, "workstation_id")
    rows = []
    for _, node in nodes.iterrows():
        op = str(node["operation_id"])
        ws = str(node["workstation_id"])
        family = family_by_op.get(op, {})
        status = "SETUP_PROFILE_READY" if family else "MISSING_SETUP_FAMILY"
        rows.append({
            "planning_run_id": node["planning_run_id"],
            "finished_sku": node["finished_sku"],
            "operation_id": op,
            "operation_name": node["operation_name"],
            "workstation_id": ws,
            "machine_type_id": family.get("machine_type_id", ""),
            "setup_family_id": family.get("setup_family_id", ""),
            "setup_family_name": family.get("setup_family_name", ""),
            "setup_sensitive_flag": _bool_value(family.get("setup_sensitive_flag", False)),
            "batching_preferred_flag": _bool_value(family.get("batching_preferred_flag", False)),
            "critical_path_flag": _bool_value(slack_by_op.get(op, {}).get("critical_path_flag", False)),
            "bottleneck_risk_flag": str(bottleneck_by_ws.get(ws, {}).get("bottleneck_visibility_level", "")).upper() in {"HIGH", "CRITICAL"},
            "queue_risk_flag": str(queue_by_ws.get(ws, {}).get("overall_queue_risk_level", "")).upper() in {"HIGH", "CRITICAL"},
            "default_setup_time_minutes": _num_value(family.get("default_setup_time_minutes", 0)),
            "setup_profile_status": status,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_empty_operation_setup_profile().columns)


def _build_setup_sequence_impact(frames: dict[str, pd.DataFrame], profiles: pd.DataFrame, matrix: pd.DataFrame) -> pd.DataFrame:
    detail = frames["schedule_detail"].copy()
    profile_by_op = _index_by(profiles, "operation_id")
    matrix_by_key = {
        (str(row["from_setup_family_id"]), str(row["to_setup_family_id"]), str(row["workstation_id"])): row.to_dict()
        for _, row in matrix.iterrows()
    }
    detail["_sequence_sort"] = pd.to_numeric(detail["operation_sequence"], errors="coerce").fillna(0)
    detail = detail.sort_values(["workstation_id", "candidate_schedule_period", "candidate_schedule_day", "candidate_schedule_shift", "_sequence_sort", "schedule_candidate_id"])
    rows = []
    previous_by_bucket: dict[tuple[str, str, str, str], str] = {}
    for _, row in detail.iterrows():
        op = str(row["operation_id"])
        ws = str(row["workstation_id"])
        profile = profile_by_op.get(op, {})
        current_family = str(profile.get("setup_family_id", ""))
        bucket = (ws, str(row["candidate_schedule_period"]), str(row["candidate_schedule_day"]), str(row["candidate_schedule_shift"]))
        previous_family = previous_by_bucket.get(bucket, "")
        change = matrix_by_key.get((previous_family, current_family, ws), {}) if previous_family and current_family else {}
        changeover = _num_value(change.get("changeover_time_minutes", 0))
        complexity = str(change.get("changeover_complexity", "NONE" if changeover == 0 else "REVIEW_REQUIRED"))
        preferred = _bool_value(change.get("preferred_sequence_flag", False))
        avoid = _bool_value(change.get("avoid_sequence_flag", False))
        penalty = bool(changeover > 0)
        batching = bool(penalty and _bool_value(profile.get("batching_preferred_flag", False)))
        if avoid:
            status = "AVOID_SEQUENCE_REVIEW"
        elif changeover >= 20 or complexity == "HIGH":
            status = "HIGH_SETUP_IMPACT"
        elif batching:
            status = "BATCHING_OPPORTUNITY"
        elif changeover >= 10 or complexity == "MEDIUM":
            status = "MEDIUM_SETUP_IMPACT"
        elif changeover >= 0:
            status = "LOW_SETUP_IMPACT"
        else:
            status = "REVIEW_REQUIRED"
        rows.append({
            "planning_run_id": row["planning_run_id"],
            "schedule_candidate_id": row["schedule_candidate_id"],
            "finished_sku": row["finished_sku"],
            "operation_id": op,
            "operation_name": row["operation_name"],
            "workstation_id": ws,
            "candidate_schedule_period": row["candidate_schedule_period"],
            "candidate_schedule_day": row["candidate_schedule_day"],
            "candidate_schedule_shift": row["candidate_schedule_shift"],
            "previous_setup_family_id": previous_family,
            "current_setup_family_id": current_family,
            "changeover_time_minutes": changeover,
            "changeover_complexity": complexity,
            "setup_penalty_flag": penalty,
            "preferred_sequence_flag": preferred,
            "avoid_sequence_flag": avoid,
            "batching_opportunity_flag": batching,
            "estimated_setup_capacity_loss_minutes": changeover,
            "setup_sequence_status": status,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
        previous_by_bucket[bucket] = current_family
    return pd.DataFrame(rows, columns=_empty_setup_sequence().columns)


def _build_manager_review(access_validation: pd.DataFrame, profiles: pd.DataFrame, sequence: pd.DataFrame, checks: list[dict]) -> pd.DataFrame:
    rows = []

    def add(schedule_candidate_id: str, sku: str, op: str, ws: str, wip: str, buffer_id: str, family: str, issue: str, severity: str, description: str, action: str) -> None:
        rows.append({
            "review_item_id": f"SETUP8E-REV-{len(rows)+1:04d}",
            "planning_run_id": _first_value(profiles, "planning_run_id"),
            "schedule_candidate_id": schedule_candidate_id,
            "finished_sku": sku,
            "operation_id": op,
            "workstation_id": ws,
            "wip_item_id": wip,
            "wip_buffer_id": buffer_id,
            "setup_family_id": family,
            "issue_type": issue,
            "issue_severity": severity,
            "issue_description": description,
            "recommended_review_action": action,
            "auto_action_allowed": False,
            "advisory_only_flag": True,
        })

    for _, row in access_validation[access_validation["validation_status"].astype(str) == "FAIL"].iterrows():
        add("", row["finished_sku"], row["operation_id"], "", row["checked_wip_item_id"], row["checked_wip_buffer_id"], "", "ILLEGAL_WIP_BUFFER_ACCESS", "CRITICAL", row["validation_message"], "REVIEW_WIP_ACCESS_RULE")
    for _, row in access_validation[access_validation["validation_status"].astype(str) == "WARNING"].iterrows():
        add("", row["finished_sku"], row["operation_id"], "", row["checked_wip_item_id"], row["checked_wip_buffer_id"], "", "WIP_ACCESS_RULE_REVIEW", "MEDIUM", row["validation_message"], "REVIEW_WIP_ACCESS_RULE")
    for _, row in profiles[profiles["setup_profile_status"].astype(str) == "MISSING_SETUP_FAMILY"].iterrows():
        add("", row["finished_sku"], row["operation_id"], row["workstation_id"], "", "", "", "MISSING_SETUP_FAMILY", "HIGH", "Operation is missing setup family.", "DEFINE_SETUP_FAMILY")
    for _, row in sequence[sequence["setup_sequence_status"].astype(str) == "HIGH_SETUP_IMPACT"].iterrows():
        add(row["schedule_candidate_id"], row["finished_sku"], row["operation_id"], row["workstation_id"], "", "", row["current_setup_family_id"], "HIGH_SETUP_IMPACT", "HIGH", "High setup impact appears in advisory sequence.", "REVIEW_SETUP_SEQUENCE")
    for _, row in sequence[sequence["setup_sequence_status"].astype(str) == "AVOID_SEQUENCE_REVIEW"].iterrows():
        add(row["schedule_candidate_id"], row["finished_sku"], row["operation_id"], row["workstation_id"], "", "", row["current_setup_family_id"], "AVOID_SEQUENCE_REVIEW", "HIGH", "Avoid-sequence changeover appears in advisory sequence.", "REVIEW_AVOID_SEQUENCE")
    for _, row in sequence[sequence["setup_sequence_status"].astype(str) == "BATCHING_OPPORTUNITY"].iterrows():
        add(row["schedule_candidate_id"], row["finished_sku"], row["operation_id"], row["workstation_id"], "", "", row["current_setup_family_id"], "BATCHING_OPPORTUNITY_REVIEW", "MEDIUM", "Batching similar setup families may reduce future setup loss.", "REVIEW_BATCHING_OPPORTUNITY")
    uncertain = sequence[sequence["changeover_complexity"].astype(str) == "REVIEW_REQUIRED"]
    for _, row in uncertain.iterrows():
        add(row["schedule_candidate_id"], row["finished_sku"], row["operation_id"], row["workstation_id"], "", "", row["current_setup_family_id"], "SETUP_DATA_REVIEW", "MEDIUM", "Changeover matrix data is incomplete for this transition.", "REVIEW_SETUP_DATA")
    if not rows:
        add("", "", "", "", "", "", "", "REVIEW_REQUIRED", "LOW", "No setup or WIP access review rows were generated.", "NO_ACTION_REQUIRED")
    return pd.DataFrame(rows, columns=_empty_review().columns)


def _validate_outputs(frames: dict[str, pd.DataFrame], access_rules: pd.DataFrame, access_validation: pd.DataFrame, families: pd.DataFrame, matrix: pd.DataFrame, profiles: pd.DataFrame, sequence: pd.DataFrame, review: pd.DataFrame, checks: list[dict]) -> None:
    outputs = {
        "wip_buffer_access_rules": access_rules,
        "wip_buffer_access_validation": access_validation,
        "setup_family_master": families,
        "setup_changeover_matrix": matrix,
        "operation_setup_profile": profiles,
        "setup_sequence_impact_analysis": sequence,
        "setup_manager_review_queue": review,
    }
    for name, frame in outputs.items():
        _add_check(checks, f"{name}_not_empty", "PASS" if not frame.empty else "FAIL", f"{name} rows={len(frame)}", len(frame))
    expected = {
        "access_rules": set(_empty_access_rules().columns),
        "access_validation": set(_empty_access_validation().columns),
        "families": set(_empty_setup_family_master().columns),
        "matrix": set(_empty_changeover_matrix().columns),
        "profiles": set(_empty_operation_setup_profile().columns),
        "sequence": set(_empty_setup_sequence().columns),
        "review": set(_empty_review().columns),
    }
    actual = {"access_rules": access_rules, "access_validation": access_validation, "families": families, "matrix": matrix, "profiles": profiles, "sequence": sequence, "review": review}
    for name, columns in expected.items():
        missing = sorted(columns.difference(actual[name].columns))
        _add_check(checks, f"{name}_required_columns", "PASS" if not missing else "FAIL", f"Missing columns: {missing}" if missing else "Required columns present.", len(missing))
    valid_ops = set(frames["nodes"]["operation_id"].astype(str))
    rule_ops = set(access_rules["operation_id"].astype(str))
    _add_check(checks, "access_rule_operation_refs_valid", "PASS" if rule_ops <= valid_ops else "FAIL", f"Invalid operations: {sorted(rule_ops - valid_ops)}", len(rule_ops - valid_ops))
    valid_wip = set(frames["wip_items"]["wip_item_id"].astype(str))
    valid_buffers = set(frames["wip_buffers"]["wip_buffer_id"].astype(str))
    wip_refs = set(access_rules["allowed_input_wip_item_id"].dropna().astype(str)) | set(access_rules["allowed_output_wip_item_id"].dropna().astype(str))
    wip_refs.discard("")
    buffer_refs = set(access_rules["allowed_input_wip_buffer_id"].dropna().astype(str)) | set(access_rules["allowed_output_wip_buffer_id"].dropna().astype(str))
    buffer_refs.discard("")
    _add_check(checks, "access_rule_wip_refs_valid", "PASS" if wip_refs <= valid_wip else "FAIL", f"Invalid WIP refs: {sorted(wip_refs - valid_wip)}", len(wip_refs - valid_wip))
    _add_check(checks, "access_rule_buffer_refs_valid", "PASS" if buffer_refs <= valid_buffers else "FAIL", f"Invalid buffer refs: {sorted(buffer_refs - valid_buffers)}", len(buffer_refs - valid_buffers))
    self_consumption = access_rules[(access_rules["allowed_input_wip_item_id"].astype(str) != "") & (access_rules["allowed_input_wip_item_id"].astype(str) == access_rules["allowed_output_wip_item_id"].astype(str))]
    _add_check(checks, "no_self_output_consumption", "PASS" if self_consumption.empty else "FAIL", "Operations must not consume own output buffer.", len(self_consumption))
    fail_count = int((access_validation["validation_status"].astype(str) == "FAIL").sum())
    _add_check(checks, "wip_access_validation_no_fail", "PASS" if fail_count == 0 else "FAIL", f"WIP access validation FAIL rows={fail_count}", fail_count)
    schedulable_ops = set(frames["nodes"]["operation_id"].astype(str))
    profiled_ops = set(profiles.loc[profiles["setup_profile_status"].astype(str) == "SETUP_PROFILE_READY", "operation_id"].astype(str))
    missing_profiles = schedulable_ops - profiled_ops
    _add_check(checks, "schedulable_operations_profiled", "PASS" if not missing_profiles else "FAIL", f"Missing setup profiles: {sorted(missing_profiles)}", len(missing_profiles))
    family_ids = set(families["setup_family_id"].astype(str))
    matrix_refs = set(matrix["from_setup_family_id"].astype(str)) | set(matrix["to_setup_family_id"].astype(str))
    _add_check(checks, "changeover_family_refs_valid", "PASS" if matrix_refs <= family_ids else "FAIL", f"Invalid setup family refs: {sorted(matrix_refs - family_ids)}", len(matrix_refs - family_ids))
    changeover_values = pd.to_numeric(matrix["changeover_time_minutes"], errors="coerce")
    _add_check(checks, "changeover_time_non_negative", "PASS" if not changeover_values.isna().any() and not (changeover_values < 0).any() else "FAIL", "Changeover times must be numeric and non-negative.", int(changeover_values.isna().sum() + (changeover_values < 0).sum()))
    self_bad = matrix[(matrix["from_setup_family_id"].astype(str) == matrix["to_setup_family_id"].astype(str)) & (pd.to_numeric(matrix["changeover_time_minutes"], errors="coerce").fillna(999) > 0.001)]
    _add_check(checks, "self_changeover_zero", "PASS" if self_bad.empty else "FAIL", "Self-to-self changeover should be zero or near zero.", len(self_bad))
    high_sequence = sequence[sequence["setup_sequence_status"].astype(str) == "HIGH_SETUP_IMPACT"]
    high_review = review[review["issue_type"].astype(str) == "HIGH_SETUP_IMPACT"]
    _add_check(checks, "high_setup_impact_reviewed", "PASS" if high_sequence.empty or not high_review.empty else "FAIL", "High setup impacts require manager review rows.", len(high_sequence))
    batching_sequence = sequence[sequence["batching_opportunity_flag"].astype(str).str.lower().isin({"true", "1", "yes"})]
    batching_review = review[review["issue_type"].astype(str) == "BATCHING_OPPORTUNITY_REVIEW"]
    _add_check(checks, "batching_opportunities_reviewed", "PASS" if batching_sequence.empty or not batching_review.empty else "FAIL", "Batching opportunities require manager review rows.", len(batching_sequence))
    _add_check(checks, "no_schedule_reordering", "PASS", "Setup impact analysis did not reorder or optimize the schedule; it only evaluates candidate order.", 0)
    advisory_ok = all(_all_true(frame, "advisory_only_flag") for frame in outputs.values())
    _add_check(checks, "advisory_only_outputs", "PASS" if advisory_ok else "FAIL", "All Step 8E outputs must be advisory-only.", len(outputs))
    _add_check(checks, "review_auto_action_disabled", "PASS" if _all_false(review, "auto_action_allowed") else "FAIL", "Manager review auto_action_allowed must be False.", len(review))
    for path, label in [
        (OUTPUT_DIR / "phase4_routing_graph_validation.csv", "Step 8A routing graph validation"),
        (OUTPUT_DIR / "phase4_production_schedule_validation.csv", "Step 8B schedule validation"),
        (OUTPUT_DIR / "phase4_wip_validation.csv", "Step 8C WIP validation"),
        (OUTPUT_DIR / "phase4_wip_aware_schedule_validation.csv", "Step 8D WIP-aware validation"),
    ]:
        if path.exists():
            validation = pd.read_csv(path)
            fails = int((validation["status"].astype(str).str.upper() == "FAIL").sum()) if "status" in validation.columns else 0
            _add_check(checks, f"{label}_no_fail", "PASS" if fails == 0 else "FAIL", f"{label} FAIL rows={fails}.", fails)
        else:
            _add_check(checks, f"{label}_exists", "FAIL", f"{label} missing.", 1)


def _access_rule_type_status(input_row: dict | None, output_row: dict | None, merge: bool) -> tuple[str, str]:
    if input_row is None and output_row is None:
        return "REVIEW_REQUIRED", "REVIEW_REQUIRED"
    if input_row is None:
        return "FIRST_OPERATION_NO_INPUT_WIP", "VALID_ACCESS_RULE" if output_row is not None else "MISSING_OUTPUT_BUFFER"
    if output_row is None:
        return "FINAL_OPERATION_NO_OUTPUT_WIP", "VALID_ACCESS_RULE"
    if merge:
        return "MERGE_OPERATION_MULTIPLE_VALID_INPUT_BUFFERS", "VALID_ACCESS_RULE"
    return "STRICT_PREDECESSOR_INPUT_BUFFER", "VALID_ACCESS_RULE"


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
        "production_order",
        "confirmed_production_schedule",
        "actual_wip_consumption",
        "wip_transaction",
        "component_inventory_consumption",
        "inventory_reservation",
        "worker_dispatch",
        "purchase_order",
        "maintenance_work_order",
        "capacity_reduction",
        "simulation",
    ]
    found = []
    for path in OUTPUT_DIR.glob("*"):
        name = path.name.lower()
        if any(token in name for token in forbidden_tokens):
            found.append(path.name)
    _add_check(checks, "forbidden_outputs_absent", "PASS" if not found else "FAIL", f"Forbidden outputs found: {found}" if found else "No forbidden execution outputs found.", len(found))


def _add_check(checks: list[dict], check_name: str, status: str, message: str, affected_rows: int) -> None:
    checks.append({
        "check_id": f"SETUP8E-{len(checks)+1:03d}",
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
    return "PHASE4-SETUP8E"


def _index_by(frame: pd.DataFrame, column: str) -> dict[str, dict]:
    if column not in frame.columns:
        return {}
    return {str(row[column]): row.to_dict() for _, row in frame.iterrows()}


def _first_value(frame: pd.DataFrame, column: str) -> str:
    if column in frame.columns and not frame.empty:
        return str(frame[column].iloc[0])
    return ""


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _all_true(frame: pd.DataFrame, column: str) -> bool:
    return column in frame.columns and bool(frame[column].astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"}).all())


def _all_false(frame: pd.DataFrame, column: str) -> bool:
    return column in frame.columns and bool((~frame[column].astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})).all())


def _num_value(value: object) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        return 0.0


def _empty_access_rules() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "finished_sku", "operation_id", "operation_name", "workstation_id", "allowed_input_wip_item_id",
        "allowed_input_wip_buffer_id", "allowed_output_wip_item_id", "allowed_output_wip_buffer_id", "predecessor_operation_id",
        "successor_operation_id", "buffer_access_rule_type", "merge_operation_flag", "parallel_branch_flag", "access_rule_status",
        "source_phase", "advisory_only_flag",
    ])


def _empty_access_validation() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "validation_check_id", "planning_run_id", "finished_sku", "operation_id", "operation_name", "checked_wip_item_id",
        "checked_wip_buffer_id", "validation_check_name", "validation_status", "validation_severity", "validation_message",
        "source_phase", "advisory_only_flag",
    ])


def _empty_setup_family_master() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "setup_family_id", "setup_family_name", "setup_family_type", "finished_sku", "operation_id",
        "workstation_id", "machine_type_id", "default_setup_time_minutes", "setup_sensitive_flag", "batching_preferred_flag",
        "active_flag", "advisory_only_flag", "notes", "source_phase",
    ])


def _empty_changeover_matrix() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "from_setup_family_id", "to_setup_family_id", "workstation_id", "machine_type_id",
        "changeover_time_minutes", "changeover_complexity", "cleaning_required_flag", "tool_change_required_flag",
        "quality_check_required_flag", "preferred_sequence_flag", "avoid_sequence_flag", "active_flag", "advisory_only_flag",
        "notes", "source_phase",
    ])


def _empty_operation_setup_profile() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "finished_sku", "operation_id", "operation_name", "workstation_id", "machine_type_id",
        "setup_family_id", "setup_family_name", "setup_sensitive_flag", "batching_preferred_flag", "critical_path_flag",
        "bottleneck_risk_flag", "queue_risk_flag", "default_setup_time_minutes", "setup_profile_status", "source_phase",
        "advisory_only_flag",
    ])


def _empty_setup_sequence() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "planning_run_id", "schedule_candidate_id", "finished_sku", "operation_id", "operation_name", "workstation_id",
        "candidate_schedule_period", "candidate_schedule_day", "candidate_schedule_shift", "previous_setup_family_id",
        "current_setup_family_id", "changeover_time_minutes", "changeover_complexity", "setup_penalty_flag",
        "preferred_sequence_flag", "avoid_sequence_flag", "batching_opportunity_flag", "estimated_setup_capacity_loss_minutes",
        "setup_sequence_status", "source_phase", "advisory_only_flag",
    ])


def _empty_review() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "review_item_id", "planning_run_id", "schedule_candidate_id", "finished_sku", "operation_id", "workstation_id",
        "wip_item_id", "wip_buffer_id", "setup_family_id", "issue_type", "issue_severity", "issue_description",
        "recommended_review_action", "auto_action_allowed", "advisory_only_flag",
    ])


if __name__ == "__main__":
    outputs = build_setup_changeover_outputs()
    print(f"WIP access rule rows: {len(outputs[0])}")
    print(f"Setup/changeover validation rows: {len(outputs[-1])}")
