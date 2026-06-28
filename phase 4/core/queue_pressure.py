"""Build advisory estimated queue pressure and WIP risk visibility."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PHASE4_DIR / "data"
OUTPUT_DIR = PHASE4_DIR / "outputs"

WORKSTATION_LOAD_FILE = OUTPUT_DIR / "phase4_capacity_load_by_workstation.csv"
MACHINE_LOAD_FILE = OUTPUT_DIR / "phase4_capacity_load_by_machine_type.csv"
LABOR_LOAD_FILE = OUTPUT_DIR / "phase4_capacity_load_by_labor_skill.csv"
CONSTRAINT_BRIDGE_FILE = OUTPUT_DIR / "phase4_capacity_constraint_bridge.csv"
CAPACITY_FEASIBILITY_FILE = OUTPUT_DIR / "phase4_capacity_feasibility_summary.csv"
BOTTLENECK_CANDIDATE_FILE = OUTPUT_DIR / "phase4_bottleneck_candidate_summary.csv"
CAPACITY_REVIEW_QUEUE_FILE = OUTPUT_DIR / "phase4_capacity_manager_review_queue.csv"
OPERATION_DETAIL_FILE = OUTPUT_DIR / "phase4_capacity_operation_load_detail.csv"
PRODUCT_ROUTINGS_FILE = DATA_DIR / "product_routings.csv"
PARALLEL_GROUPS_FILE = DATA_DIR / "routing_parallel_groups.csv"
WORKSTATIONS_FILE = DATA_DIR / "workstations.csv"

QUEUE_PRESSURE_OUTPUT_FILE = OUTPUT_DIR / "phase4_queue_pressure_by_workstation.csv"
QUEUE_RISK_SUMMARY_OUTPUT_FILE = OUTPUT_DIR / "phase4_queue_risk_summary.csv"
QUEUE_MANAGER_REVIEW_OUTPUT_FILE = OUTPUT_DIR / "phase4_queue_manager_review_queue.csv"
QUEUE_VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_queue_validation.csv"

QUEUE_MEASUREMENT_TYPE = "ESTIMATED_FROM_CAPACITY_PLAN"
SOURCE_PHASE = "PHASE4_STEP5A_ESTIMATED_QUEUE_PRESSURE"


def build_queue_pressure_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build Step 5A queue pressure, risk summary, review queue, and validation outputs."""
    checks: list[dict] = []
    frames = {
        "workstation_load": _load_csv(WORKSTATION_LOAD_FILE, "workstation_load", checks),
        "machine_load": _load_csv(MACHINE_LOAD_FILE, "machine_load", checks),
        "labor_load": _load_csv(LABOR_LOAD_FILE, "labor_load", checks),
        "constraint_bridge": _load_csv(CONSTRAINT_BRIDGE_FILE, "constraint_bridge", checks),
        "capacity_feasibility": _load_csv(CAPACITY_FEASIBILITY_FILE, "capacity_feasibility", checks),
        "bottleneck_candidates": _load_csv(BOTTLENECK_CANDIDATE_FILE, "bottleneck_candidates", checks),
        "capacity_review_queue": _load_csv(CAPACITY_REVIEW_QUEUE_FILE, "capacity_review_queue", checks),
        "operation_detail": _load_csv(OPERATION_DETAIL_FILE, "operation_detail", checks),
        "product_routings": _load_csv(PRODUCT_ROUTINGS_FILE, "product_routings", checks),
        "parallel_groups": _load_csv(PARALLEL_GROUPS_FILE, "parallel_groups", checks),
        "workstations": _load_csv(WORKSTATIONS_FILE, "workstations", checks),
    }
    queue_pressure = pd.DataFrame()
    queue_summary = pd.DataFrame()
    review_queue = pd.DataFrame()
    if all(frame is not None for frame in frames.values()):
        queue_pressure = _build_queue_pressure_by_workstation(
            frames["workstation_load"],
            frames["constraint_bridge"],
            frames["operation_detail"],
            frames["product_routings"],
            frames["parallel_groups"],
            frames["workstations"],
        )
        queue_summary = _build_queue_risk_summary(queue_pressure, frames["bottleneck_candidates"])
        review_queue = _build_queue_manager_review_queue(queue_pressure)
        _validate_queue_outputs(queue_pressure, queue_summary, review_queue, checks)
    _check_no_blocked_outputs(checks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    queue_pressure.to_csv(QUEUE_PRESSURE_OUTPUT_FILE, index=False)
    queue_summary.to_csv(QUEUE_RISK_SUMMARY_OUTPUT_FILE, index=False)
    review_queue.to_csv(QUEUE_MANAGER_REVIEW_OUTPUT_FILE, index=False)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    validation.to_csv(QUEUE_VALIDATION_OUTPUT_FILE, index=False)
    return queue_pressure, queue_summary, review_queue, validation


def _build_queue_pressure_by_workstation(
    workstation: pd.DataFrame,
    bridge: pd.DataFrame,
    detail: pd.DataFrame,
    routings: pd.DataFrame,
    parallel_groups: pd.DataFrame,
    workstations: pd.DataFrame,
) -> pd.DataFrame:
    keys = ["planning_run_id", "period_start", "period_end", "workstation_id"]
    base = workstation.merge(
        bridge[
            keys
            + [
                "labor_high_utilization_warning_flag",
                "machine_constraint_flag",
                "labor_constraint_flag",
            ]
        ],
        on=keys,
        how="left",
    )
    join_info = _build_join_pressure_reference(routings, parallel_groups)
    base = base.merge(join_info, on="workstation_id", how="left")
    queue_supported = workstations[["workstation_id", "queue_supported_flag"]].copy()
    base = base.merge(queue_supported, on="workstation_id", how="left")
    for column in [
        "overload_flag",
        "near_capacity_flag",
        "labor_high_utilization_warning_flag",
        "machine_constraint_flag",
        "labor_constraint_flag",
        "routing_join_pressure_flag",
        "parallel_merge_pressure_flag",
        "queue_supported_flag",
    ]:
        base[column] = _to_bool(base[column]) if column in base.columns else False
    for column in ["upstream_parallel_operation_count", "downstream_join_operation_count"]:
        base[column] = pd.to_numeric(base.get(column, 0), errors="coerce").fillna(0).astype(int)
    for column in ["utilization_pct", "total_required_hours", "available_hours", "capacity_gap_hours"]:
        base[column] = pd.to_numeric(base[column], errors="coerce").fillna(0)
    base["estimated_queue_pressure_score"] = base.apply(_queue_pressure_score, axis=1)
    base["estimated_queue_pressure_level"] = base["estimated_queue_pressure_score"].apply(_pressure_level)
    base["estimated_wip_risk_level"] = base["estimated_queue_pressure_level"]
    base["queue_risk_reason"] = base.apply(_queue_risk_reason, axis=1)
    base["queue_measurement_type"] = QUEUE_MEASUREMENT_TYPE
    base["actual_queue_length_available_flag"] = False
    base["actual_wait_time_available_flag"] = False
    base["future_actual_queue_tracking_flag"] = True
    base["source_phase"] = SOURCE_PHASE
    base["advisory_only_flag"] = True
    return base[
        [
            "planning_run_id",
            "period_start",
            "period_end",
            "workstation_id",
            "workstation_name",
            "capacity_status",
            "utilization_pct",
            "total_required_hours",
            "available_hours",
            "capacity_gap_hours",
            "overload_flag",
            "near_capacity_flag",
            "labor_high_utilization_warning_flag",
            "machine_constraint_flag",
            "labor_constraint_flag",
            "workstation_capacity_basis",
            "routing_join_pressure_flag",
            "parallel_merge_pressure_flag",
            "upstream_parallel_operation_count",
            "downstream_join_operation_count",
            "estimated_queue_pressure_score",
            "estimated_queue_pressure_level",
            "estimated_wip_risk_level",
            "queue_risk_reason",
            "queue_measurement_type",
            "actual_queue_length_available_flag",
            "actual_wait_time_available_flag",
            "queue_supported_flag",
            "future_actual_queue_tracking_flag",
            "source_phase",
            "advisory_only_flag",
        ]
    ].rename(
        columns={
            "capacity_status": "workstation_capacity_status",
            "utilization_pct": "workstation_utilization_pct",
        }
    ).copy()


def _build_join_pressure_reference(routings: pd.DataFrame, parallel_groups: pd.DataFrame) -> pd.DataFrame:
    if parallel_groups.empty or routings.empty:
        return pd.DataFrame(columns=["workstation_id", "routing_join_pressure_flag", "parallel_merge_pressure_flag", "upstream_parallel_operation_count", "downstream_join_operation_count"])
    rows = []
    operation_to_workstation = routings.set_index("operation_id")["workstation_id"].astype(str).to_dict()
    for _, group in parallel_groups.iterrows():
        join_op = str(group.get("join_before_operation_id", "")).strip()
        if not join_op:
            continue
        members = _split_ids(group.get("member_operation_ids", ""))
        workstation_id = operation_to_workstation.get(join_op, "")
        if workstation_id:
            rows.append(
                {
                    "workstation_id": workstation_id,
                    "routing_join_pressure_flag": True,
                    "parallel_merge_pressure_flag": True,
                    "upstream_parallel_operation_count": len(members),
                    "downstream_join_operation_count": 1,
                }
            )
    if not rows:
        return pd.DataFrame(columns=["workstation_id", "routing_join_pressure_flag", "parallel_merge_pressure_flag", "upstream_parallel_operation_count", "downstream_join_operation_count"])
    ref = pd.DataFrame(rows).groupby("workstation_id", as_index=False).agg(
        routing_join_pressure_flag=("routing_join_pressure_flag", "max"),
        parallel_merge_pressure_flag=("parallel_merge_pressure_flag", "max"),
        upstream_parallel_operation_count=("upstream_parallel_operation_count", "max"),
        downstream_join_operation_count=("downstream_join_operation_count", "sum"),
    )
    return ref


def _build_queue_risk_summary(queue_pressure: pd.DataFrame, bottleneck_candidates: pd.DataFrame) -> pd.DataFrame:
    frame = queue_pressure.copy()
    frame["_critical"] = frame["estimated_queue_pressure_level"].eq("CRITICAL")
    frame["_high"] = frame["estimated_queue_pressure_level"].eq("HIGH")
    frame["_medium"] = frame["estimated_queue_pressure_level"].eq("MEDIUM")
    frame["_low"] = frame["estimated_queue_pressure_level"].eq("LOW")
    frame["_negative_gap"] = pd.to_numeric(frame["capacity_gap_hours"], errors="coerce").clip(upper=0)
    summary = frame.groupby(["planning_run_id", "workstation_id"], as_index=False).agg(
        workstation_name=("workstation_name", "first"),
        periods_observed=("period_start", "nunique"),
        critical_queue_pressure_period_count=("_critical", "sum"),
        high_queue_pressure_period_count=("_high", "sum"),
        medium_queue_pressure_period_count=("_medium", "sum"),
        low_queue_pressure_period_count=("_low", "sum"),
        max_estimated_queue_pressure_score=("estimated_queue_pressure_score", "max"),
        avg_estimated_queue_pressure_score=("estimated_queue_pressure_score", "mean"),
        max_workstation_utilization_pct=("workstation_utilization_pct", "max"),
        avg_workstation_utilization_pct=("workstation_utilization_pct", "mean"),
        total_negative_capacity_gap_hours=("_negative_gap", "sum"),
        labor_high_utilization_warning_period_count=("labor_high_utilization_warning_flag", lambda s: int(_to_bool(s).sum())),
        routing_join_pressure_period_count=("routing_join_pressure_flag", lambda s: int(_to_bool(s).sum())),
        parallel_merge_pressure_period_count=("parallel_merge_pressure_flag", lambda s: int(_to_bool(s).sum())),
    )
    reference = bottleneck_candidates[["planning_run_id", "workstation_id", "bottleneck_candidate_level"]].rename(
        columns={"bottleneck_candidate_level": "bottleneck_candidate_reference_level"}
    )
    summary = summary.merge(reference, on=["planning_run_id", "workstation_id"], how="left")
    summary["bottleneck_candidate_reference_level"] = summary["bottleneck_candidate_reference_level"].fillna("LOW")
    summary = summary.sort_values(
        [
            "max_estimated_queue_pressure_score",
            "critical_queue_pressure_period_count",
            "total_negative_capacity_gap_hours",
            "avg_workstation_utilization_pct",
        ],
        ascending=[False, False, True, False],
    ).reset_index(drop=True)
    summary["queue_risk_rank"] = range(1, len(summary) + 1)
    summary["overall_queue_risk_level"] = summary.apply(_overall_queue_risk_level, axis=1)
    summary["queue_risk_summary_reason"] = summary.apply(_queue_summary_reason, axis=1)
    summary["source_phase"] = SOURCE_PHASE
    summary["advisory_only_flag"] = True
    return summary[
        [
            "planning_run_id",
            "workstation_id",
            "workstation_name",
            "periods_observed",
            "critical_queue_pressure_period_count",
            "high_queue_pressure_period_count",
            "medium_queue_pressure_period_count",
            "low_queue_pressure_period_count",
            "max_estimated_queue_pressure_score",
            "avg_estimated_queue_pressure_score",
            "max_workstation_utilization_pct",
            "avg_workstation_utilization_pct",
            "total_negative_capacity_gap_hours",
            "labor_high_utilization_warning_period_count",
            "routing_join_pressure_period_count",
            "parallel_merge_pressure_period_count",
            "queue_risk_rank",
            "overall_queue_risk_level",
            "queue_risk_summary_reason",
            "bottleneck_candidate_reference_level",
            "source_phase",
            "advisory_only_flag",
        ]
    ].copy()


def _build_queue_manager_review_queue(queue_pressure: pd.DataFrame) -> pd.DataFrame:
    rows = []
    counter = 1
    for _, row in queue_pressure.iterrows():
        level = str(row["estimated_queue_pressure_level"])
        include = level in {"HIGH", "CRITICAL"} or _bool_value(row["parallel_merge_pressure_flag"]) or (
            _bool_value(row["overload_flag"]) and _bool_value(row["labor_high_utilization_warning_flag"])
        ) or float(row["workstation_utilization_pct"]) > 250
        if not include:
            continue
        issue_type = _queue_issue_type(row)
        rows.append(
            {
                "planning_run_id": row["planning_run_id"],
                "queue_review_item_id": f"QUEUE-REV-{counter:04d}",
                "period_start": row["period_start"],
                "period_end": row["period_end"],
                "workstation_id": row["workstation_id"],
                "workstation_name": row["workstation_name"],
                "queue_issue_type": issue_type,
                "queue_issue_severity": level if level in {"HIGH", "CRITICAL"} else "MEDIUM",
                "estimated_queue_pressure_score": row["estimated_queue_pressure_score"],
                "estimated_queue_pressure_level": level,
                "estimated_wip_risk_level": row["estimated_wip_risk_level"],
                "queue_issue_description": f"{row['workstation_name']} has {level} estimated queue pressure from {row['queue_risk_reason']}.",
                "suggested_review_action": _queue_review_action(row, issue_type),
                "auto_action_allowed": False,
                "advisory_only_flag": True,
            }
        )
        counter += 1
    columns = [
        "planning_run_id",
        "queue_review_item_id",
        "period_start",
        "period_end",
        "workstation_id",
        "workstation_name",
        "queue_issue_type",
        "queue_issue_severity",
        "estimated_queue_pressure_score",
        "estimated_queue_pressure_level",
        "estimated_wip_risk_level",
        "queue_issue_description",
        "suggested_review_action",
        "auto_action_allowed",
        "advisory_only_flag",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)[columns].copy()


def _queue_pressure_score(row: pd.Series) -> float:
    score = 0.0
    utilization = float(row["utilization_pct"])
    gap = float(row["capacity_gap_hours"])
    if _bool_value(row["overload_flag"]):
        score += 40
    if _bool_value(row["near_capacity_flag"]):
        score += 15
    if _bool_value(row["labor_high_utilization_warning_flag"]):
        score += 20
    if _bool_value(row["machine_constraint_flag"]):
        score += 20
    if _bool_value(row["labor_constraint_flag"]):
        score += 20
    if utilization > 100:
        score += 10
    if utilization > 150:
        score += 20
    if utilization > 250:
        score += 30
    if gap < 0:
        score += 10
    if gap < -40:
        score += 20
    if _bool_value(row["routing_join_pressure_flag"]):
        score += 10
    if _bool_value(row["parallel_merge_pressure_flag"]):
        score += 10
    score += min(int(row["upstream_parallel_operation_count"]) * 5, 15)
    return round(score, 4)


def _pressure_level(score: float) -> str:
    if score >= 100:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def _queue_risk_reason(row: pd.Series) -> str:
    if _bool_value(row["overload_flag"]) and _bool_value(row["labor_high_utilization_warning_flag"]):
        return "WORKSTATION_OVERLOAD_AND_LABOR_STRESS"
    if _bool_value(row["routing_join_pressure_flag"]) and _bool_value(row["overload_flag"]):
        return "PARALLEL_BRANCH_JOIN_PRESSURE"
    if _bool_value(row["overload_flag"]) and float(row["capacity_gap_hours"]) < 0:
        return "HIGH_UTILIZATION_WITH_NEGATIVE_CAPACITY_GAP"
    if _bool_value(row["overload_flag"]):
        return "WORKSTATION_OVERLOAD"
    if _bool_value(row["labor_high_utilization_warning_flag"]):
        return "LABOR_STRESS_QUEUE_RISK"
    if _bool_value(row["routing_join_pressure_flag"]):
        return "PARALLEL_BRANCH_JOIN_PRESSURE"
    return "NO_SIGNIFICANT_QUEUE_PRESSURE"


def _overall_queue_risk_level(row: pd.Series) -> str:
    if row["critical_queue_pressure_period_count"] > 0 or row["max_estimated_queue_pressure_score"] >= 100:
        return "CRITICAL"
    if row["high_queue_pressure_period_count"] > 0 or row["max_estimated_queue_pressure_score"] >= 60:
        return "HIGH"
    if row["medium_queue_pressure_period_count"] > 0 or row["max_estimated_queue_pressure_score"] >= 25:
        return "MEDIUM"
    return "LOW"


def _queue_summary_reason(row: pd.Series) -> str:
    return (
        f"Estimated queue risk from capacity plan: critical_periods={int(row['critical_queue_pressure_period_count'])}, "
        f"high_periods={int(row['high_queue_pressure_period_count'])}, "
        f"join_pressure_periods={int(row['routing_join_pressure_period_count'])}, "
        f"max_score={float(row['max_estimated_queue_pressure_score']):.2f}."
    )


def _queue_issue_type(row: pd.Series) -> str:
    if _bool_value(row["overload_flag"]) and _bool_value(row["labor_high_utilization_warning_flag"]):
        return "LABOR_STRESS_QUEUE_RISK"
    if _bool_value(row["overload_flag"]):
        return "WORKSTATION_OVERLOAD_QUEUE_RISK"
    if _bool_value(row["parallel_merge_pressure_flag"]):
        return "PARALLEL_MERGE_PRESSURE"
    if str(row["estimated_wip_risk_level"]) in {"HIGH", "CRITICAL"}:
        return "WIP_BUILDUP_RISK"
    return "ESTIMATED_QUEUE_PRESSURE"


def _queue_review_action(row: pd.Series, issue_type: str) -> str:
    if issue_type == "PARALLEL_MERGE_PRESSURE":
        return "REVIEW_ROUTING_JOIN_ASSUMPTIONS"
    if issue_type == "LABOR_STRESS_QUEUE_RISK":
        return "REVIEW_LABOR_STRESS"
    if _bool_value(row["parallel_merge_pressure_flag"]):
        return "REVIEW_PARALLEL_BRANCH_BALANCE"
    if _bool_value(row["overload_flag"]):
        return "REVIEW_WORKSTATION_CALENDAR"
    return "REVIEW_BEFORE_ACTION"


def _validate_queue_outputs(
    pressure: pd.DataFrame,
    summary: pd.DataFrame,
    review: pd.DataFrame,
    checks: list[dict],
) -> None:
    required_pressure = {
        "planning_run_id",
        "period_start",
        "period_end",
        "workstation_id",
        "workstation_name",
        "estimated_queue_pressure_score",
        "estimated_queue_pressure_level",
        "estimated_wip_risk_level",
        "queue_measurement_type",
        "actual_queue_length_available_flag",
        "actual_wait_time_available_flag",
        "future_actual_queue_tracking_flag",
        "advisory_only_flag",
    }
    required_summary = {
        "planning_run_id",
        "workstation_id",
        "workstation_name",
        "periods_observed",
        "max_estimated_queue_pressure_score",
        "queue_risk_rank",
        "overall_queue_risk_level",
        "advisory_only_flag",
    }
    required_review = {
        "planning_run_id",
        "queue_review_item_id",
        "queue_issue_type",
        "queue_issue_severity",
        "auto_action_allowed",
        "advisory_only_flag",
    }
    invalid = int(pressure.empty) + int(summary.empty)
    invalid += len(required_pressure.difference(pressure.columns))
    invalid += len(required_summary.difference(summary.columns))
    if not pressure.empty:
        scores = pd.to_numeric(pressure["estimated_queue_pressure_score"], errors="coerce")
        invalid += int(scores.isna().sum() + (scores < 0).sum())
        invalid += int((~pressure["estimated_queue_pressure_level"].astype(str).isin({"LOW", "MEDIUM", "HIGH", "CRITICAL"})).sum())
        invalid += int((~pressure["estimated_wip_risk_level"].astype(str).isin({"LOW", "MEDIUM", "HIGH", "CRITICAL"})).sum())
        invalid += int((pressure["queue_measurement_type"].astype(str) != QUEUE_MEASUREMENT_TYPE).sum())
        invalid += int(_to_bool(pressure["actual_queue_length_available_flag"]).sum())
        invalid += int(_to_bool(pressure["actual_wait_time_available_flag"]).sum())
        invalid += int((~_to_bool(pressure["future_actual_queue_tracking_flag"])).sum())
        invalid += int((~_to_bool(pressure["advisory_only_flag"])).sum())
        final_assembly = pressure[pressure["workstation_id"].astype(str).eq("WS-FINAL-ASM")]
        if final_assembly.empty or not _to_bool(final_assembly["routing_join_pressure_flag"]).any():
            invalid += 1
    high_or_critical = pressure["estimated_queue_pressure_level"].astype(str).isin({"HIGH", "CRITICAL"}).any() if not pressure.empty else False
    if high_or_critical and review.empty:
        invalid += 1
    if not review.empty:
        invalid += len(required_review.difference(review.columns))
        invalid += int(_to_bool(review["auto_action_allowed"]).sum())
        invalid += int((~_to_bool(review["advisory_only_flag"])).sum())
    if not summary.empty:
        invalid += int((~summary["overall_queue_risk_level"].astype(str).isin({"LOW", "MEDIUM", "HIGH", "CRITICAL"})).sum())
        invalid += int((~_to_bool(summary["advisory_only_flag"])).sum())
    checks.append(
        _result(
            "queue_step5a_outputs_valid",
            "Step 5A queue pressure outputs valid",
            "FAIL" if invalid else "PASS",
            f"Step 5A missing/invalid values: {invalid}" if invalid else f"Queue outputs valid; pressure_rows={len(pressure)}, summary_rows={len(summary)}, review_rows={len(review)}.",
            invalid,
        )
    )


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked_tokens = [
        "actual_queue_length",
        "measured_wait_time",
        "real_queue_time",
        "observed_queue_length",
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
            lower = path.name.lower()
            if path.is_file() and any(token in lower for token in blocked_tokens):
                bad_files.append(str(path))
    checks.append(
        _result(
            "queue_no_blocked_execution_outputs",
            "queue no blocked execution outputs",
            "FAIL" if bad_files else "PASS",
            f"Blocked real-queue/scheduling/simulation/execution outputs found: {bad_files}" if bad_files else "No real queue measurement, scheduling, simulation, or execution outputs found.",
            len(bad_files),
        )
    )


def _load_csv(path: Path, name: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"queue_{name}_exists", f"{name} exists", "FAIL", f"Missing file: {path}", 1))
        return None
    frame = pd.read_csv(path, keep_default_na=False)
    checks.append(_result(f"queue_{name}_exists", f"{name} exists", "PASS", f"Loaded {path}", 0))
    if frame.empty:
        checks.append(_result(f"queue_{name}_not_empty", f"{name} not empty", "WARNING", f"{name} has no rows.", 1))
    return frame


def _split_ids(value: object) -> list[str]:
    text = "" if value is None else str(value).strip()
    if not text:
        return []
    return [item.strip() for item in text.split(";") if item.strip()]


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
    _, _, _, validation = build_queue_pressure_outputs()
    status_counts = validation["status"].value_counts().to_dict() if not validation.empty else {}
    print(f"Queue validation rows: {len(validation)}")
    print(f"Queue validation status counts: {status_counts}")
