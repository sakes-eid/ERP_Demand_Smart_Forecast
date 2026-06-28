"""Build advisory production flow and queue-bottleneck flow views."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PHASE4_DIR / "data"
OUTPUT_DIR = PHASE4_DIR / "outputs"

PRODUCT_ROUTINGS_FILE = DATA_DIR / "product_routings.csv"
PARALLEL_GROUPS_FILE = DATA_DIR / "routing_parallel_groups.csv"
WORKSTATIONS_FILE = DATA_DIR / "workstations.csv"
ROUTING_FLOW_SUMMARY_FILE = OUTPUT_DIR / "phase4_routing_flow_summary.csv"
WORKSTATION_LOAD_FILE = OUTPUT_DIR / "phase4_capacity_load_by_workstation.csv"
CONSTRAINT_BRIDGE_FILE = OUTPUT_DIR / "phase4_capacity_constraint_bridge.csv"
CAPACITY_FEASIBILITY_FILE = OUTPUT_DIR / "phase4_capacity_feasibility_summary.csv"
BOTTLENECK_CANDIDATE_FILE = OUTPUT_DIR / "phase4_bottleneck_candidate_summary.csv"
QUEUE_PRESSURE_FILE = OUTPUT_DIR / "phase4_queue_pressure_by_workstation.csv"
QUEUE_RISK_SUMMARY_FILE = OUTPUT_DIR / "phase4_queue_risk_summary.csv"
BOTTLENECK_VISIBILITY_FILE = OUTPUT_DIR / "phase4_bottleneck_visibility_summary.csv"
BOTTLENECK_PERIOD_EVIDENCE_FILE = OUTPUT_DIR / "phase4_bottleneck_period_evidence.csv"
QUEUE_VALIDATION_FILE = OUTPUT_DIR / "phase4_queue_validation.csv"
BOTTLENECK_VALIDATION_FILE = OUTPUT_DIR / "phase4_bottleneck_validation.csv"
CAPACITY_VALIDATION_FILE = OUTPUT_DIR / "phase4_capacity_validation.csv"

PRODUCTION_FLOW_OUTPUT_FILE = OUTPUT_DIR / "phase4_production_flow_view.csv"
FLOW_RISK_SUMMARY_OUTPUT_FILE = OUTPUT_DIR / "phase4_flow_step_risk_summary.csv"
FLOW_MANAGER_REVIEW_OUTPUT_FILE = OUTPUT_DIR / "phase4_flow_manager_review_queue.csv"
FLOW_VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_flow_validation.csv"

CONFIRMATION_STATUS = "PLANNING_EVIDENCE_ONLY_NOT_SIMULATION_CONFIRMED"
SOURCE_PHASE = "PHASE4_STEP5C_PRODUCTION_FLOW_VIEW"


def build_production_flow_view_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build Step 5C production flow view, risk summary, review queue, and validation."""
    checks: list[dict] = []
    frames = {
        "product_routings": _load_csv(PRODUCT_ROUTINGS_FILE, "product_routings", checks),
        "parallel_groups": _load_csv(PARALLEL_GROUPS_FILE, "parallel_groups", checks),
        "workstations": _load_csv(WORKSTATIONS_FILE, "workstations", checks),
        "routing_flow_summary": _load_csv(ROUTING_FLOW_SUMMARY_FILE, "routing_flow_summary", checks),
        "workstation_load": _load_csv(WORKSTATION_LOAD_FILE, "workstation_load", checks),
        "constraint_bridge": _load_csv(CONSTRAINT_BRIDGE_FILE, "constraint_bridge", checks),
        "capacity_feasibility": _load_csv(CAPACITY_FEASIBILITY_FILE, "capacity_feasibility", checks),
        "bottleneck_candidates": _load_csv(BOTTLENECK_CANDIDATE_FILE, "bottleneck_candidates", checks),
        "queue_pressure": _load_csv(QUEUE_PRESSURE_FILE, "queue_pressure", checks),
        "queue_risk_summary": _load_csv(QUEUE_RISK_SUMMARY_FILE, "queue_risk_summary", checks),
        "bottleneck_visibility": _load_csv(BOTTLENECK_VISIBILITY_FILE, "bottleneck_visibility", checks),
        "bottleneck_period_evidence": _load_csv(BOTTLENECK_PERIOD_EVIDENCE_FILE, "bottleneck_period_evidence", checks),
        "queue_validation": _load_csv(QUEUE_VALIDATION_FILE, "queue_validation", checks),
        "bottleneck_validation": _load_csv(BOTTLENECK_VALIDATION_FILE, "bottleneck_validation", checks),
        "capacity_validation": _load_csv(CAPACITY_VALIDATION_FILE, "capacity_validation", checks),
    }
    flow = pd.DataFrame()
    summary = pd.DataFrame()
    review = pd.DataFrame()
    if all(frame is not None for frame in frames.values()):
        flow = _build_production_flow_view(
            frames["product_routings"],
            frames["parallel_groups"],
            frames["workstations"],
            frames["workstation_load"],
            frames["queue_pressure"],
            frames["bottleneck_visibility"],
        )
        summary = _build_flow_step_risk_summary(flow)
        review = _build_flow_manager_review_queue(flow)
        _validate_flow_outputs(flow, summary, review, frames, checks)
    _check_no_blocked_outputs(checks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    flow.to_csv(PRODUCTION_FLOW_OUTPUT_FILE, index=False)
    summary.to_csv(FLOW_RISK_SUMMARY_OUTPUT_FILE, index=False)
    review.to_csv(FLOW_MANAGER_REVIEW_OUTPUT_FILE, index=False)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    validation.to_csv(FLOW_VALIDATION_OUTPUT_FILE, index=False)
    return flow, summary, review, validation


def _build_production_flow_view(
    routings: pd.DataFrame,
    parallel_groups: pd.DataFrame,
    workstations: pd.DataFrame,
    workstation_load: pd.DataFrame,
    queue_pressure: pd.DataFrame,
    bottleneck_visibility: pd.DataFrame,
) -> pd.DataFrame:
    active = routings[_to_bool(routings.get("active_flag", pd.Series(True, index=routings.index)))].copy()
    run_id = _planning_run_id(queue_pressure, workstation_load, bottleneck_visibility)
    active["planning_run_id"] = run_id
    active["operation_sequence"] = pd.to_numeric(active["operation_sequence"], errors="coerce").fillna(0)

    ws_ref = workstations[["workstation_id", "workstation_name", "queue_supported_flag"]].copy()
    flow = active.merge(ws_ref, on="workstation_id", how="left")
    join_ref = _join_reference(parallel_groups, active)
    flow = flow.merge(join_ref, on="operation_id", how="left")
    for column in ["routing_join_pressure_flag", "parallel_merge_pressure_flag"]:
        flow[column] = _to_bool(flow[column]) if column in flow.columns else False

    latest_capacity = _latest_capacity_by_workstation(workstation_load)
    queue_ref = _queue_reference(queue_pressure)
    bottleneck_ref = _bottleneck_reference(bottleneck_visibility)
    flow = flow.merge(latest_capacity, on=["planning_run_id", "workstation_id"], how="left")
    flow = flow.merge(queue_ref, on=["planning_run_id", "workstation_id"], how="left")
    flow = flow.merge(bottleneck_ref, on=["planning_run_id", "workstation_id"], how="left")

    flow["queue_supported_flag"] = _to_bool(flow["queue_supported_flag"])
    for column in ["can_run_in_parallel_flag", "join_required_before_next_flag"]:
        flow[column] = _to_bool(flow[column])
    for column in ["max_workstation_utilization_pct", "max_estimated_queue_pressure_score"]:
        flow[column] = pd.to_numeric(flow.get(column, 0), errors="coerce").fillna(0)
    flow["workstation_capacity_status_latest"] = flow["workstation_capacity_status_latest"].fillna("UNKNOWN")
    flow["estimated_queue_pressure_level"] = flow["estimated_queue_pressure_level"].fillna("LOW")
    flow["estimated_wip_risk_level"] = flow["estimated_wip_risk_level"].fillna("LOW")
    flow["bottleneck_visibility_level"] = flow["bottleneck_visibility_level"].fillna("LOW")
    flow["bottleneck_visibility_rank"] = pd.to_numeric(flow.get("bottleneck_visibility_rank", 0), errors="coerce").fillna(0).astype(int)
    flow["bottleneck_evidence_layers"] = flow["bottleneck_evidence_layers"].fillna("LOW_EVIDENCE")
    flow["flow_step_risk_level"] = flow.apply(_flow_step_level, axis=1)
    flow["flow_step_risk_reason"] = flow.apply(_flow_step_reason, axis=1)
    flow["confirmation_status"] = CONFIRMATION_STATUS
    flow["source_phase"] = SOURCE_PHASE
    flow["advisory_only_flag"] = True
    flow = flow.sort_values(["finished_sku", "operation_sequence", "operation_id"]).reset_index(drop=True)
    return flow[
        [
            "planning_run_id",
            "finished_sku",
            "finished_product_name",
            "routing_id",
            "routing_version",
            "operation_id",
            "operation_sequence",
            "operation_name",
            "operation_type",
            "workstation_id",
            "workstation_name",
            "predecessor_operation_ids",
            "successor_operation_ids",
            "parallel_group_id",
            "can_run_in_parallel_flag",
            "join_required_before_next_flag",
            "routing_join_pressure_flag",
            "parallel_merge_pressure_flag",
            "queue_supported_flag",
            "workstation_capacity_status_latest",
            "max_workstation_utilization_pct",
            "max_estimated_queue_pressure_score",
            "estimated_queue_pressure_level",
            "estimated_wip_risk_level",
            "bottleneck_visibility_level",
            "bottleneck_visibility_rank",
            "bottleneck_evidence_layers",
            "flow_step_risk_level",
            "flow_step_risk_reason",
            "confirmation_status",
            "source_phase",
            "advisory_only_flag",
        ]
    ].copy()


def _build_flow_step_risk_summary(flow: pd.DataFrame) -> pd.DataFrame:
    frame = flow.copy()
    frame["_parallel"] = _to_bool(frame["can_run_in_parallel_flag"])
    frame["_join"] = _to_bool(frame["join_required_before_next_flag"]) | _to_bool(frame["routing_join_pressure_flag"])
    frame["_score"] = frame.apply(_flow_step_score, axis=1)
    summary = frame.groupby(["planning_run_id", "finished_sku", "workstation_id"], as_index=False).agg(
        finished_product_name=("finished_product_name", "first"),
        workstation_name=("workstation_name", "first"),
        operation_count_for_product=("operation_id", "nunique"),
        operation_names=("operation_name", lambda s: "; ".join(dict.fromkeys(s.astype(str)))),
        parallel_operation_flag=("_parallel", "max"),
        join_operation_flag=("_join", "max"),
        max_workstation_utilization_pct=("max_workstation_utilization_pct", "max"),
        max_estimated_queue_pressure_score=("max_estimated_queue_pressure_score", "max"),
        bottleneck_visibility_level=("bottleneck_visibility_level", _max_level),
        bottleneck_visibility_rank=("bottleneck_visibility_rank", "min"),
        flow_step_risk_level=("flow_step_risk_level", _max_level),
        flow_step_risk_score=("_score", "max"),
        flow_step_risk_reason=("flow_step_risk_reason", lambda s: "; ".join(dict.fromkeys(s.astype(str)))),
    )
    summary["recommended_review_focus"] = summary.apply(_recommended_review_focus, axis=1)
    summary["confirmation_status"] = CONFIRMATION_STATUS
    summary["source_phase"] = SOURCE_PHASE
    summary["advisory_only_flag"] = True
    return summary[
        [
            "planning_run_id",
            "finished_sku",
            "finished_product_name",
            "workstation_id",
            "workstation_name",
            "operation_count_for_product",
            "operation_names",
            "parallel_operation_flag",
            "join_operation_flag",
            "max_workstation_utilization_pct",
            "max_estimated_queue_pressure_score",
            "bottleneck_visibility_level",
            "bottleneck_visibility_rank",
            "flow_step_risk_level",
            "flow_step_risk_score",
            "flow_step_risk_reason",
            "recommended_review_focus",
            "confirmation_status",
            "source_phase",
            "advisory_only_flag",
        ]
    ].copy()


def _build_flow_manager_review_queue(flow: pd.DataFrame) -> pd.DataFrame:
    rows = []
    risky = flow[
        flow["flow_step_risk_level"].isin(["HIGH", "CRITICAL"])
        | (_to_bool(flow["routing_join_pressure_flag"]) & flow["workstation_id"].astype(str).eq("WS-FINAL-ASM"))
    ].copy()
    for idx, row in risky.reset_index(drop=True).iterrows():
        issue_type = _flow_issue_type(row)
        rows.append(
            {
                "planning_run_id": row["planning_run_id"],
                "flow_review_item_id": f"FLOW-REV-{idx + 1:04d}",
                "finished_sku": row["finished_sku"],
                "finished_product_name": row["finished_product_name"],
                "operation_id": row["operation_id"],
                "operation_name": row["operation_name"],
                "workstation_id": row["workstation_id"],
                "workstation_name": row["workstation_name"],
                "flow_issue_type": issue_type,
                "flow_issue_severity": row["flow_step_risk_level"],
                "flow_issue_description": row["flow_step_risk_reason"],
                "evidence_layers": row["bottleneck_evidence_layers"],
                "suggested_review_action": _flow_review_action(row, issue_type),
                "auto_action_allowed": False,
                "advisory_only_flag": True,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "planning_run_id",
            "flow_review_item_id",
            "finished_sku",
            "finished_product_name",
            "operation_id",
            "operation_name",
            "workstation_id",
            "workstation_name",
            "flow_issue_type",
            "flow_issue_severity",
            "flow_issue_description",
            "evidence_layers",
            "suggested_review_action",
            "auto_action_allowed",
            "advisory_only_flag",
        ],
    )


def _join_reference(parallel_groups: pd.DataFrame, routings: pd.DataFrame) -> pd.DataFrame:
    rows = []
    operation_ids = set(routings["operation_id"].astype(str))
    for _, group in parallel_groups.iterrows():
        join_op = str(group.get("join_before_operation_id", "")).strip()
        if join_op and join_op in operation_ids:
            rows.append({"operation_id": join_op, "routing_join_pressure_flag": True, "parallel_merge_pressure_flag": True})
    return pd.DataFrame(rows, columns=["operation_id", "routing_join_pressure_flag", "parallel_merge_pressure_flag"]).drop_duplicates("operation_id")


def _latest_capacity_by_workstation(workstation_load: pd.DataFrame) -> pd.DataFrame:
    frame = workstation_load.copy()
    frame["period_start_dt"] = pd.to_datetime(frame["period_start"], errors="coerce")
    frame["utilization_pct"] = pd.to_numeric(frame["utilization_pct"], errors="coerce").fillna(0)
    latest = frame.sort_values("period_start_dt").groupby(["planning_run_id", "workstation_id"], as_index=False).tail(1)
    max_util = frame.groupby(["planning_run_id", "workstation_id"], as_index=False)["utilization_pct"].max().rename(columns={"utilization_pct": "max_workstation_utilization_pct"})
    latest = latest[["planning_run_id", "workstation_id", "capacity_status"]].rename(columns={"capacity_status": "workstation_capacity_status_latest"})
    return latest.merge(max_util, on=["planning_run_id", "workstation_id"], how="left")


def _queue_reference(queue_pressure: pd.DataFrame) -> pd.DataFrame:
    frame = queue_pressure.copy()
    frame["estimated_queue_pressure_score"] = pd.to_numeric(frame["estimated_queue_pressure_score"], errors="coerce").fillna(0)
    frame = frame.sort_values(["planning_run_id", "workstation_id", "estimated_queue_pressure_score"], ascending=[True, True, False])
    return frame.groupby(["planning_run_id", "workstation_id"], as_index=False).head(1)[
        [
            "planning_run_id",
            "workstation_id",
            "estimated_queue_pressure_score",
            "estimated_queue_pressure_level",
            "estimated_wip_risk_level",
        ]
    ].rename(columns={"estimated_queue_pressure_score": "max_estimated_queue_pressure_score"})


def _bottleneck_reference(bottleneck_visibility: pd.DataFrame) -> pd.DataFrame:
    return bottleneck_visibility[
        [
            "planning_run_id",
            "workstation_id",
            "bottleneck_visibility_level",
            "bottleneck_visibility_rank",
            "bottleneck_evidence_layers",
        ]
    ].copy()


def _flow_step_level(row: pd.Series) -> str:
    if str(row["bottleneck_visibility_level"]) == "CRITICAL" or str(row["estimated_queue_pressure_level"]) == "CRITICAL":
        return "CRITICAL"
    if str(row["bottleneck_visibility_level"]) == "HIGH" or str(row["estimated_queue_pressure_level"]) == "HIGH":
        return "HIGH"
    if str(row["workstation_capacity_status_latest"]) == "NEAR_CAPACITY" or _bool_value(row["routing_join_pressure_flag"]):
        return "MEDIUM"
    return "LOW"


def _flow_step_score(row: pd.Series) -> float:
    level_points = {"LOW": 10, "MEDIUM": 35, "HIGH": 70, "CRITICAL": 100}
    score = level_points.get(str(row["flow_step_risk_level"]), 0)
    score += min(float(row["max_estimated_queue_pressure_score"]) / 5, 40)
    if _bool_value(row["routing_join_pressure_flag"]):
        score += 15
    return round(score, 4)


def _flow_step_reason(row: pd.Series) -> str:
    parts = []
    if str(row["bottleneck_visibility_level"]) in {"HIGH", "CRITICAL"}:
        parts.append("BOTTLENECK_VISIBILITY_AT_FLOW_STEP")
    if str(row["estimated_queue_pressure_level"]) in {"HIGH", "CRITICAL"}:
        parts.append("QUEUE_PRESSURE_AT_FLOW_STEP")
    if str(row["workstation_capacity_status_latest"]) == "OVERLOADED":
        parts.append("CAPACITY_OVERLOAD_AT_FLOW_STEP")
    if _bool_value(row["routing_join_pressure_flag"]):
        parts.append("FINAL_ASSEMBLY_JOIN_PRESSURE" if str(row["workstation_id"]) == "WS-FINAL-ASM" else "ROUTING_JOIN_PRESSURE")
    return ";".join(parts) if parts else "LOW_PLANNING_FLOW_RISK"


def _recommended_review_focus(row: pd.Series) -> str:
    if _bool_value(row["join_operation_flag"]) and str(row["workstation_id"]) == "WS-FINAL-ASM":
        return "REVIEW_FINAL_ASSEMBLY_CAPACITY"
    if _bool_value(row["parallel_operation_flag"]):
        return "REVIEW_PARALLEL_BRANCH_BALANCE"
    if str(row["flow_step_risk_level"]) in {"HIGH", "CRITICAL"}:
        return "REVIEW_QUEUE_PRESSURE"
    return "NO_ACTION_REQUIRED"


def _flow_issue_type(row: pd.Series) -> str:
    if str(row["flow_step_risk_level"]) == "CRITICAL":
        return "CRITICAL_FLOW_STEP_RISK"
    if _bool_value(row["routing_join_pressure_flag"]) and str(row["workstation_id"]) == "WS-FINAL-ASM":
        return "FINAL_ASSEMBLY_JOIN_PRESSURE"
    if str(row["estimated_queue_pressure_level"]) in {"HIGH", "CRITICAL"}:
        return "QUEUE_PRESSURE_AT_FLOW_STEP"
    if str(row["bottleneck_visibility_level"]) in {"HIGH", "CRITICAL"}:
        return "BOTTLENECK_VISIBILITY_AT_FLOW_STEP"
    if str(row["workstation_capacity_status_latest"]) == "OVERLOADED":
        return "CAPACITY_OVERLOAD_AT_FLOW_STEP"
    return "HIGH_FLOW_STEP_RISK"


def _flow_review_action(row: pd.Series, issue_type: str) -> str:
    if issue_type == "FINAL_ASSEMBLY_JOIN_PRESSURE":
        return "REVIEW_FINAL_ASSEMBLY_CAPACITY"
    if _bool_value(row["routing_join_pressure_flag"]):
        return "REVIEW_ROUTING_JOIN_ASSUMPTIONS"
    if "QUEUE" in issue_type:
        return "REVIEW_QUEUE_PRESSURE"
    if "CAPACITY" in issue_type:
        return "REVIEW_WORKSTATION_CALENDAR"
    return "REVIEW_BEFORE_ACTION"


def _validate_flow_outputs(flow: pd.DataFrame, summary: pd.DataFrame, review: pd.DataFrame, frames: dict[str, pd.DataFrame], checks: list[dict]) -> None:
    required_flow = {
        "planning_run_id", "finished_sku", "operation_id", "operation_sequence", "workstation_id", "workstation_name",
        "can_run_in_parallel_flag", "join_required_before_next_flag", "routing_join_pressure_flag", "parallel_merge_pressure_flag",
        "max_estimated_queue_pressure_score", "estimated_queue_pressure_level", "bottleneck_visibility_level",
        "flow_step_risk_level", "confirmation_status", "advisory_only_flag",
    }
    required_summary = {"planning_run_id", "finished_sku", "workstation_id", "flow_step_risk_level", "flow_step_risk_score", "confirmation_status", "advisory_only_flag"}
    required_review = {"flow_review_item_id", "flow_issue_type", "flow_issue_severity", "auto_action_allowed", "advisory_only_flag"}
    invalid = int(flow.empty) + int(summary.empty)
    invalid += len(required_flow.difference(flow.columns))
    invalid += len(required_summary.difference(summary.columns))
    valid_levels = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    if not flow.empty:
        invalid += int((~flow["flow_step_risk_level"].astype(str).isin(valid_levels)).sum())
        invalid += int((flow["confirmation_status"].astype(str) != CONFIRMATION_STATUS).sum())
        invalid += int((~_to_bool(flow["advisory_only_flag"])).sum())
        invalid += 0 if {"SKU-BIKE-ROAD-001", "SKU-BIKE-MT-001"}.issubset(set(flow["finished_sku"].astype(str))) else 1
        invalid += 0 if _to_bool(flow["can_run_in_parallel_flag"]).any() else 1
        invalid += 0 if (_to_bool(flow["join_required_before_next_flag"]) | _to_bool(flow["routing_join_pressure_flag"])).any() else 1
        final_assembly = flow[flow["workstation_id"].astype(str).eq("WS-FINAL-ASM")]
        invalid += 0 if (not final_assembly.empty and _to_bool(final_assembly["routing_join_pressure_flag"]).any()) else 1
        invalid += _operation_order_issues(flow)
    high_or_critical = flow["flow_step_risk_level"].astype(str).isin({"HIGH", "CRITICAL"}).any() if not flow.empty else False
    if high_or_critical and review.empty:
        invalid += 1
    if not review.empty:
        invalid += len(required_review.difference(review.columns))
        invalid += int(_to_bool(review["auto_action_allowed"]).sum())
        invalid += int((~_to_bool(review["advisory_only_flag"])).sum())
    for key in ["queue_validation", "bottleneck_validation", "capacity_validation"]:
        validation = frames[key]
        if "status" in validation.columns:
            invalid += int((validation["status"].astype(str).str.upper() == "FAIL").sum())
    checks.append(_result("flow_step5c_outputs_valid", "Step 5C production flow outputs valid", "FAIL" if invalid else "PASS", f"Step 5C missing/invalid values: {invalid}" if invalid else f"Flow outputs valid; flow_rows={len(flow)}, summary_rows={len(summary)}, review_rows={len(review)}.", invalid))


def _operation_order_issues(flow: pd.DataFrame) -> int:
    issues = 0
    for _, group in flow.groupby("routing_id"):
        seq = pd.to_numeric(group.sort_values("operation_sequence")["operation_sequence"], errors="coerce")
        if seq.isna().any() or not seq.is_monotonic_increasing:
            issues += 1
    return issues


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked_tokens = [
        "streamlit", "actual_queue_length", "measured_wait_time", "simulation_result", "final_bottleneck",
        "dispatch_schedule", "detailed_schedule", "finite_schedule", "shop_floor_schedule", "production_sequence",
        "scheduling_engine", "simulation", "production_order", "purchase_order", "released_order", "inventory_reservation",
    ]
    bad_files = []
    if OUTPUT_DIR.exists():
        for path in OUTPUT_DIR.glob("*"):
            lower = path.name.lower()
            if path.is_file() and any(token in lower for token in blocked_tokens):
                bad_files.append(str(path))
    checks.append(_result("flow_no_blocked_outputs", "flow no blocked UI/scheduling/simulation/execution outputs", "FAIL" if bad_files else "PASS", f"Blocked UI/queue/scheduling/simulation/execution outputs found: {bad_files}" if bad_files else "No Streamlit/UI, real queue, scheduling, simulation, or execution outputs found.", len(bad_files)))


def _planning_run_id(*frames: pd.DataFrame) -> str:
    for frame in frames:
        if "planning_run_id" in frame.columns:
            values = frame["planning_run_id"].dropna().astype(str).str.strip()
            if not values.empty:
                return values.iloc[0]
    return "PHASE4-FLOW-UNKNOWN"


def _max_level(values: pd.Series) -> str:
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    cleaned = values.astype(str).map(order).fillna(0)
    reverse = {value: key for key, value in order.items()}
    return reverse[int(cleaned.max())]


def _load_csv(path: Path, name: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"flow_{name}_exists", f"{name} exists", "FAIL", f"Missing file: {path}", 1))
        return None
    frame = pd.read_csv(path, keep_default_na=False)
    checks.append(_result(f"flow_{name}_exists", f"{name} exists", "PASS", f"Loaded {path}", 0))
    if frame.empty:
        checks.append(_result(f"flow_{name}_not_empty", f"{name} not empty", "WARNING", f"{name} has no rows.", 1))
    return frame


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _bool_value(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


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
    _, _, _, validation = build_production_flow_view_outputs()
    status_counts = validation["status"].value_counts().to_dict() if not validation.empty else {}
    print(f"Flow validation rows: {len(validation)}")
    print(f"Flow validation status counts: {status_counts}")
