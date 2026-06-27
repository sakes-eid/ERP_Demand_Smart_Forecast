"""Validate Phase 4 product routing master data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PHASE4_DIR / "data"
OUTPUT_DIR = PHASE4_DIR / "outputs"

PRODUCT_ROUTINGS_FILE = DATA_DIR / "product_routings.csv"
PARALLEL_GROUPS_FILE = DATA_DIR / "routing_parallel_groups.csv"
OPERATION_RESOURCES_FILE = DATA_DIR / "routing_operation_resources.csv"
WORKSTATIONS_FILE = DATA_DIR / "workstations.csv"
MACHINES_FILE = DATA_DIR / "machines.csv"
LABOR_FILE = DATA_DIR / "labor_resources.csv"

OUTPUT_FILE = OUTPUT_DIR / "phase4_routing_validation.csv"
FLOW_SUMMARY_OUTPUT_FILE = OUTPUT_DIR / "phase4_routing_flow_summary.csv"

BIKE_SKUS = {"SKU-BIKE-ROAD-001", "SKU-BIKE-MT-001"}

REQUIRED_COLUMNS = {
    "product_routings": {
        "routing_id",
        "finished_sku",
        "finished_product_name",
        "routing_version",
        "operation_id",
        "operation_sequence",
        "operation_name",
        "operation_type",
        "workstation_id",
        "parallel_group_id",
        "predecessor_operation_ids",
        "successor_operation_ids",
        "can_run_in_parallel_flag",
        "join_required_before_next_flag",
        "setup_time_minutes",
        "run_time_minutes_per_unit",
        "move_time_minutes",
        "queue_placeholder_flag",
        "labor_skill_required",
        "machine_type_required",
        "active_flag",
        "advisory_only_flag",
        "notes",
    },
    "routing_parallel_groups": {
        "parallel_group_id",
        "routing_id",
        "finished_sku",
        "group_name",
        "fork_after_operation_id",
        "join_before_operation_id",
        "member_operation_ids",
        "parallel_group_type",
        "all_members_required_to_join_flag",
        "active_flag",
        "advisory_only_flag",
        "notes",
    },
    "routing_operation_resources": {
        "operation_id",
        "routing_id",
        "finished_sku",
        "workstation_id",
        "required_machine_type",
        "required_labor_skill",
        "required_machine_count",
        "required_worker_count",
        "simultaneous_resource_required_flag",
        "resource_notes",
        "active_flag",
        "advisory_only_flag",
    },
}


def validate_routing_master_data(output_file: Path = OUTPUT_FILE) -> pd.DataFrame:
    """Validate routing master data and write an advisory validation output."""
    checks: list[dict] = []
    frames = {
        "product_routings": _load_csv(PRODUCT_ROUTINGS_FILE, "product_routings", checks),
        "routing_parallel_groups": _load_csv(PARALLEL_GROUPS_FILE, "routing_parallel_groups", checks),
        "routing_operation_resources": _load_csv(OPERATION_RESOURCES_FILE, "routing_operation_resources", checks),
        "workstations": _load_csv(WORKSTATIONS_FILE, "workstations", checks),
        "machines": _load_csv(MACHINES_FILE, "machines", checks),
        "labor_resources": _load_csv(LABOR_FILE, "labor_resources", checks),
    }

    for name in ["product_routings", "routing_parallel_groups", "routing_operation_resources"]:
        frame = frames[name]
        if frame is None:
            continue
        _check_required_columns(name, frame, checks)
        _check_not_empty(name, frame, checks)

    routings = frames["product_routings"]
    groups = frames["routing_parallel_groups"]
    resources = frames["routing_operation_resources"]
    workstations = frames["workstations"]
    machines = frames["machines"]
    labor = frames["labor_resources"]

    if _has_columns(routings, REQUIRED_COLUMNS["product_routings"]):
        _check_finished_skus(routings, checks)
        _check_operation_ids_unique(routings, checks)
        _check_sequences(routings, checks)
        _check_numeric_timing(routings, checks)
        _check_advisory_and_active("product_routings", routings, checks)
        if workstations is not None and "workstation_id" in workstations.columns:
            _check_foreign_key(
                "routing_workstations_valid",
                "routing workstation references valid",
                routings,
                "workstation_id",
                set(_clean(workstations["workstation_id"])),
                checks,
            )
        _check_graph_references(routings, checks)
        _check_directional_consistency(routings, checks)
        _check_no_cycles(routings, checks)
        _check_start_end_structure(routings, checks)
        _check_product_specific_workstations(routings, checks)

    if (
        _has_columns(routings, REQUIRED_COLUMNS["product_routings"])
        and _has_columns(groups, REQUIRED_COLUMNS["routing_parallel_groups"])
    ):
        _check_parallel_groups(routings, groups, checks)
        _check_advisory_and_active("routing_parallel_groups", groups, checks)

    if (
        _has_columns(routings, REQUIRED_COLUMNS["product_routings"])
        and _has_columns(resources, REQUIRED_COLUMNS["routing_operation_resources"])
    ):
        _check_operation_resources(routings, resources, workstations, machines, labor, checks)
        _check_advisory_and_active("routing_operation_resources", resources, checks)

    _check_no_blocked_outputs(checks)

    result = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    output_file.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_file, index=False)
    if routings is not None and groups is not None and _has_columns(routings, REQUIRED_COLUMNS["product_routings"]):
        build_routing_flow_summary(routings, groups)
    return result


def build_routing_flow_summary(
    routings: pd.DataFrame | None = None,
    groups: pd.DataFrame | None = None,
    output_file: Path = FLOW_SUMMARY_OUTPUT_FILE,
) -> pd.DataFrame:
    """Create a human-readable advisory routing flow summary."""
    if routings is None:
        routings = pd.read_csv(PRODUCT_ROUTINGS_FILE)
    if groups is None:
        groups = pd.read_csv(PARALLEL_GROUPS_FILE)

    rows = []
    active = routings[_to_bool(routings["active_flag"])].copy()
    for routing_id, routing in active.sort_values(["routing_id", "operation_sequence"]).groupby("routing_id"):
        sku = str(routing["finished_sku"].iloc[0])
        product_name = str(routing["finished_product_name"].iloc[0])
        route_groups = groups[groups["routing_id"].astype(str).str.strip() == routing_id] if groups is not None else pd.DataFrame()
        flow_text = _format_flow_text(routing, route_groups)
        parallel_summaries = []
        for _, group in route_groups.iterrows():
            member_ids = _split_ids(group.get("member_operation_ids", ""))
            member_names = _operation_names(routing, member_ids)
            parallel_summaries.append(f"{group['parallel_group_id']}: {' || '.join(member_names)}")
        rows.append(
            {
                "routing_id": routing_id,
                "finished_sku": sku,
                "finished_product_name": product_name,
                "routing_flow_text": flow_text,
                "parallel_groups_summary": " | ".join(parallel_summaries),
                "operation_count": len(routing),
                "parallel_operation_count": int(_to_bool(routing["can_run_in_parallel_flag"]).sum()),
                "join_operation_count": int(_to_bool(routing["join_required_before_next_flag"]).sum()),
                "advisory_only_flag": True,
            }
        )
    summary = pd.DataFrame(rows)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_file, index=False)
    return summary


def _load_csv(path: Path, name: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"{name}_file_exists", f"{name} file exists", "FAIL", f"Missing file: {path}", 1))
        return None
    frame = pd.read_csv(path, keep_default_na=False)
    checks.append(_result(f"{name}_file_exists", f"{name} file exists", "PASS", f"Loaded {path}", 0))
    return frame


def _check_required_columns(name: str, frame: pd.DataFrame, checks: list[dict]) -> None:
    missing = sorted(REQUIRED_COLUMNS[name].difference(frame.columns))
    checks.append(
        _result(
            f"{name}_required_columns",
            f"{name} required columns",
            "FAIL" if missing else "PASS",
            f"Missing required columns: {missing}" if missing else "All required columns exist.",
            len(missing),
        )
    )


def _check_not_empty(name: str, frame: pd.DataFrame, checks: list[dict]) -> None:
    checks.append(
        _result(
            f"{name}_not_empty",
            f"{name} not empty",
            "FAIL" if frame.empty else "PASS",
            "File has no rows." if frame.empty else f"File has {len(frame)} rows.",
            1 if frame.empty else 0,
        )
    )


def _check_finished_skus(routings: pd.DataFrame, checks: list[dict]) -> None:
    active = routings[_to_bool(routings["active_flag"])]
    active_skus = set(_clean(active["finished_sku"]))
    missing = sorted(BIKE_SKUS - active_skus)
    unexpected = sorted(active_skus - BIKE_SKUS)
    if missing or unexpected:
        checks.append(_result("routing_finished_skus_valid", "routing finished SKUs valid", "FAIL", f"Missing={missing}; unexpected={unexpected}", len(missing) + len(unexpected)))
    else:
        checks.append(_result("routing_finished_skus_valid", "routing finished SKUs valid", "PASS", "Road Bike and Mountain Bike active routings exist.", 0))


def _check_operation_ids_unique(routings: pd.DataFrame, checks: list[dict]) -> None:
    duplicate_count = int(_clean(routings["operation_id"]).duplicated().sum())
    checks.append(_result("routing_operation_ids_unique", "routing operation IDs unique", "FAIL" if duplicate_count else "PASS", f"Duplicate operation IDs: {duplicate_count}" if duplicate_count else "Operation IDs are unique.", duplicate_count))


def _check_sequences(routings: pd.DataFrame, checks: list[dict]) -> None:
    sequence = pd.to_numeric(routings["operation_sequence"], errors="coerce")
    invalid = int(sequence.isna().sum() + (sequence <= 0).sum())
    duplicate_count = int(routings.assign(_seq=sequence).duplicated(["routing_id", "_seq"]).sum())
    if invalid or duplicate_count:
        checks.append(_result("routing_sequences_valid", "routing operation sequences valid", "FAIL", f"Invalid sequences={invalid}; duplicate routing sequences={duplicate_count}", invalid + duplicate_count))
        return
    unordered = 0
    for _, group in routings.assign(_seq=sequence).groupby("routing_id"):
        if group.sort_values("_seq")["_seq"].tolist() != sorted(group["_seq"].tolist()):
            unordered += 1
    checks.append(_result("routing_sequences_valid", "routing operation sequences valid", "FAIL" if unordered else "PASS", f"Unordered routing groups: {unordered}" if unordered else "Operation sequences are positive and ordered per routing.", unordered))


def _check_numeric_timing(routings: pd.DataFrame, checks: list[dict]) -> None:
    specs = [
        ("setup_time_minutes", False),
        ("run_time_minutes_per_unit", True),
        ("move_time_minutes", False),
    ]
    invalid_total = 0
    for column, positive in specs:
        values = pd.to_numeric(routings[column], errors="coerce")
        invalid = values.isna() | (values <= 0 if positive else values < 0)
        invalid_total += int(invalid.sum())
    checks.append(_result("routing_timing_values_valid", "routing timing values valid", "FAIL" if invalid_total else "PASS", f"Invalid timing rows: {invalid_total}" if invalid_total else "Setup/run/move timing values are valid.", invalid_total))


def _check_graph_references(routings: pd.DataFrame, checks: list[dict]) -> None:
    invalid = 0
    for routing_id, group in routings.groupby("routing_id"):
        operations = set(_clean(group["operation_id"]))
        for _, row in group.iterrows():
            refs = _split_ids(row["predecessor_operation_ids"]) + _split_ids(row["successor_operation_ids"])
            invalid += sum(1 for ref in refs if ref not in operations)
    checks.append(_result("routing_graph_references_valid", "routing graph references valid", "FAIL" if invalid else "PASS", f"Invalid predecessor/successor references: {invalid}" if invalid else "All predecessor and successor references are valid within routing.", invalid))


def _check_directional_consistency(routings: pd.DataFrame, checks: list[dict]) -> None:
    inconsistent = 0
    by_operation = {str(row["operation_id"]).strip(): row for _, row in routings.iterrows()}
    for _, row in routings.iterrows():
        operation_id = str(row["operation_id"]).strip()
        for succ in _split_ids(row["successor_operation_ids"]):
            succ_row = by_operation.get(succ)
            if succ_row is None or operation_id not in _split_ids(succ_row["predecessor_operation_ids"]):
                inconsistent += 1
        for pred in _split_ids(row["predecessor_operation_ids"]):
            pred_row = by_operation.get(pred)
            if pred_row is None or operation_id not in _split_ids(pred_row["successor_operation_ids"]):
                inconsistent += 1
    checks.append(_result("routing_directional_links_consistent", "routing directional links consistent", "FAIL" if inconsistent else "PASS", f"Inconsistent predecessor/successor links: {inconsistent}" if inconsistent else "Predecessor and successor links are directionally consistent.", inconsistent))


def _check_no_cycles(routings: pd.DataFrame, checks: list[dict]) -> None:
    cyclic_routes = 0
    for _, group in routings.groupby("routing_id"):
        graph = {str(row["operation_id"]).strip(): _split_ids(row["successor_operation_ids"]) for _, row in group.iterrows()}
        if _has_cycle(graph):
            cyclic_routes += 1
    checks.append(_result("routing_no_circular_dependencies", "routing no circular dependencies", "FAIL" if cyclic_routes else "PASS", f"Routing loops found: {cyclic_routes}" if cyclic_routes else "No circular routing dependencies found.", cyclic_routes))


def _check_start_end_structure(routings: pd.DataFrame, checks: list[dict]) -> None:
    invalid = 0
    messages = []
    for routing_id, group in routings.groupby("routing_id"):
        starts = [op for op in _clean(group["operation_id"]) if not _split_ids(group.loc[_clean(group["operation_id"]) == op, "predecessor_operation_ids"].iloc[0])]
        ends = [op for op in _clean(group["operation_id"]) if not _split_ids(group.loc[_clean(group["operation_id"]) == op, "successor_operation_ids"].iloc[0])]
        if len(starts) != 1 or len(ends) != 1:
            invalid += 1
            messages.append(f"{routing_id}: starts={starts}, ends={ends}")
    checks.append(_result("routing_start_end_structure_valid", "routing start/end structure valid", "FAIL" if invalid else "PASS", "; ".join(messages) if messages else "Each routing has exactly one start and one end operation.", invalid))


def _check_product_specific_workstations(routings: pd.DataFrame, checks: list[dict]) -> None:
    mt = routings[_clean(routings["finished_sku"]) == "SKU-BIKE-MT-001"]
    road = routings[_clean(routings["finished_sku"]) == "SKU-BIKE-ROAD-001"]
    mt_uses_fork = "WS-FORK-SUSP" in set(_clean(mt["workstation_id"]))
    road_uses_fork = "WS-FORK-SUSP" in set(_clean(road["workstation_id"]))
    status = "PASS" if mt_uses_fork and not road_uses_fork else "FAIL"
    message = f"Mountain uses fork/suspension={mt_uses_fork}; Road uses fork/suspension={road_uses_fork}."
    checks.append(_result("routing_product_specific_workstations_valid", "routing product-specific workstations valid", status, message, 0 if status == "PASS" else 1))


def _check_parallel_groups(routings: pd.DataFrame, groups: pd.DataFrame, checks: list[dict]) -> None:
    duplicate_count = int(_clean(groups["parallel_group_id"]).duplicated().sum())
    checks.append(_result("parallel_group_ids_unique", "parallel group IDs unique", "FAIL" if duplicate_count else "PASS", f"Duplicate parallel group IDs: {duplicate_count}" if duplicate_count else "Parallel group IDs are unique.", duplicate_count))

    invalid = 0
    road_groups = 0
    mt_groups = 0
    operation_lookup = {str(row["operation_id"]).strip(): row for _, row in routings.iterrows()}
    routing_ids = set(_clean(routings["routing_id"]))
    for _, group in groups.iterrows():
        routing_id = str(group["routing_id"]).strip()
        sku = str(group["finished_sku"]).strip()
        if sku == "SKU-BIKE-ROAD-001":
            road_groups += 1
        if sku == "SKU-BIKE-MT-001":
            mt_groups += 1
        fork = str(group["fork_after_operation_id"]).strip()
        join = str(group["join_before_operation_id"]).strip()
        members = _split_ids(group["member_operation_ids"])
        if routing_id not in routing_ids or fork not in operation_lookup or join not in operation_lookup:
            invalid += 1
            continue
        route_ops = {str(row["operation_id"]).strip(): row for _, row in routings[routings["routing_id"].astype(str).str.strip() == routing_id].iterrows()}
        if fork not in route_ops or join not in route_ops:
            invalid += 1
        join_row = route_ops.get(join)
        if join_row is None or (not _bool(join_row["join_required_before_next_flag"]) and str(join_row["operation_type"]).strip() != "FINAL_ASSEMBLY"):
            invalid += 1
        join_seq = float(join_row["operation_sequence"]) if join_row is not None else -1
        fork_seq = float(route_ops[fork]["operation_sequence"]) if fork in route_ops else 999999
        for member in members:
            member_row = route_ops.get(member)
            if member_row is None:
                invalid += 1
                continue
            if not _bool(member_row["can_run_in_parallel_flag"]):
                invalid += 1
            member_seq = float(member_row["operation_sequence"])
            if not (fork_seq < member_seq < join_seq):
                invalid += 1
    if road_groups < 1 or mt_groups < 1:
        invalid += 1
    checks.append(_result("parallel_groups_valid", "parallel groups valid", "FAIL" if invalid else "PASS", f"Invalid parallel group conditions: {invalid}; road_groups={road_groups}; mt_groups={mt_groups}" if invalid else "Parallel fork/join groups are valid for Road Bike and Mountain Bike.", invalid))


def _check_operation_resources(
    routings: pd.DataFrame,
    resources: pd.DataFrame,
    workstations: pd.DataFrame | None,
    machines: pd.DataFrame | None,
    labor: pd.DataFrame | None,
    checks: list[dict],
) -> None:
    operations = set(_clean(routings["operation_id"]))
    invalid_ops = int((~_clean(resources["operation_id"]).isin(operations)).sum())
    duplicate_ops = int(_clean(resources["operation_id"]).duplicated().sum())
    invalid_counts = 0
    for column in ["required_machine_count", "required_worker_count"]:
        values = pd.to_numeric(resources[column], errors="coerce")
        invalid_counts += int((values.isna() | (values < 0)).sum())
    invalid_ws = 0
    if workstations is not None and "workstation_id" in workstations.columns:
        invalid_ws = int((~_clean(resources["workstation_id"]).isin(set(_clean(workstations["workstation_id"])))).sum())
    invalid_machine_type = 0
    if machines is not None and "machine_type" in machines.columns:
        valid_machines = set(_clean(machines["machine_type"]))
        invalid_machine_type = int((~_clean(resources["required_machine_type"]).isin(valid_machines)).sum())
    invalid_labor_skill = 0
    if labor is not None and "skill_type" in labor.columns:
        valid_labor = set(_clean(labor["skill_type"]))
        invalid_labor_skill = int((~_clean(resources["required_labor_skill"]).isin(valid_labor)).sum())

    invalid_total = invalid_ops + duplicate_ops + invalid_counts + invalid_ws + invalid_machine_type + invalid_labor_skill
    message = (
        f"invalid_ops={invalid_ops}; duplicate_ops={duplicate_ops}; invalid_counts={invalid_counts}; "
        f"invalid_workstations={invalid_ws}; invalid_machine_types={invalid_machine_type}; invalid_labor_skills={invalid_labor_skill}"
    )
    checks.append(_result("routing_operation_resources_valid", "routing operation resources valid", "FAIL" if invalid_total else "PASS", message if invalid_total else "Operation resource mappings reference valid operations, workstations, machine types, and labor skills.", invalid_total))


def _check_advisory_and_active(name: str, frame: pd.DataFrame, checks: list[dict]) -> None:
    inactive = int((~_to_bool(frame["active_flag"])).sum()) if "active_flag" in frame.columns else 0
    non_advisory = int((~_to_bool(frame["advisory_only_flag"])).sum()) if "advisory_only_flag" in frame.columns else len(frame)
    status = "FAIL" if non_advisory else ("WARNING" if inactive else "PASS")
    message = f"inactive={inactive}; non_advisory={non_advisory}" if (inactive or non_advisory) else "All rows are active and advisory-only."
    checks.append(_result(f"{name}_advisory_active_flags", f"{name} advisory and active flags", status, message, inactive + non_advisory))


def _check_foreign_key(check_id: str, check_name: str, frame: pd.DataFrame, column: str, valid_values: set[str], checks: list[dict]) -> None:
    invalid = int((~_clean(frame[column]).isin(valid_values)).sum())
    checks.append(_result(check_id, check_name, "FAIL" if invalid else "PASS", f"Invalid {column} references: {invalid}" if invalid else f"All {column} references are valid.", invalid))


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked_tokens = [
        "capacity_plan",
        "utilization",
        "confirmed_bottleneck",
        "bottleneck_ranking",
        "workstation_queue",
        "operation_queue",
        "queue_simulation",
        "detailed_schedule",
        "finite_schedule",
        "shop_floor_schedule",
        "production_sequence",
        "scheduling_engine",
        "simulation",
        "production_order",
        "purchase_order",
        "released_order",
        "inventory_reservation",
    ]
    bad_files = []
    if OUTPUT_DIR.exists():
        for path in OUTPUT_DIR.glob("*"):
            if path.is_file() and any(token in path.name.lower() for token in blocked_tokens):
                bad_files.append(str(path))
    checks.append(
        _result(
            "routing_no_blocked_future_outputs",
            "routing no blocked future outputs",
            "FAIL" if bad_files else "PASS",
            f"Blocked future/execution outputs found: {bad_files}" if bad_files else "No future-only queue, detailed scheduling, simulation, or execution outputs found.",
            len(bad_files),
        )
    )


def _format_flow_text(routing: pd.DataFrame, groups: pd.DataFrame) -> str:
    if groups is None or groups.empty:
        return " -> ".join(routing.sort_values("operation_sequence")["operation_name"].astype(str).tolist())
    group = groups.iloc[0]
    fork = str(group["fork_after_operation_id"]).strip()
    join = str(group["join_before_operation_id"]).strip()
    members = _split_ids(group["member_operation_ids"])
    names = {str(row["operation_id"]).strip(): str(row["operation_name"]).strip() for _, row in routing.iterrows()}
    before = names.get(fork, fork)
    parallel = " || ".join(names.get(member, member) for member in members)
    after_rows = routing[pd.to_numeric(routing["operation_sequence"], errors="coerce") >= float(routing.loc[_clean(routing["operation_id"]) == join, "operation_sequence"].iloc[0])]
    after = " -> ".join(after_rows.sort_values("operation_sequence")["operation_name"].astype(str).tolist())
    return f"{before} -> [{parallel}] -> {after}"


def _operation_names(routing: pd.DataFrame, operation_ids: list[str]) -> list[str]:
    names = {str(row["operation_id"]).strip(): str(row["operation_name"]).strip() for _, row in routing.iterrows()}
    return [names.get(operation_id, operation_id) for operation_id in operation_ids]


def _has_cycle(graph: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in graph.get(node, []):
            if visit(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def _has_columns(frame: pd.DataFrame | None, columns: set[str]) -> bool:
    return frame is not None and columns.issubset(frame.columns)


def _split_ids(value: object) -> list[str]:
    text = "" if value is None else str(value).strip()
    if not text:
        return []
    return [item.strip() for item in text.split(";") if item.strip()]


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _clean(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip()


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
    validation = validate_routing_master_data()
    fail_count = int((validation["status"] == "FAIL").sum())
    print(f"Phase 4 routing validation rows: {len(validation)}")
    print(f"Phase 4 routing validation FAIL rows: {fail_count}")
    print(f"Output written to: {OUTPUT_FILE}")
    print(f"Routing flow summary written to: {FLOW_SUMMARY_OUTPUT_FILE}")
    if fail_count:
        raise SystemExit(1)
