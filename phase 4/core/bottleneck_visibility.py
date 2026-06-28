"""Build advisory bottleneck visibility from capacity and estimated queue evidence."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PHASE4_DIR / "data"
OUTPUT_DIR = PHASE4_DIR / "outputs"

BOTTLENECK_CANDIDATE_FILE = OUTPUT_DIR / "phase4_bottleneck_candidate_summary.csv"
CAPACITY_FEASIBILITY_FILE = OUTPUT_DIR / "phase4_capacity_feasibility_summary.csv"
CAPACITY_REVIEW_QUEUE_FILE = OUTPUT_DIR / "phase4_capacity_manager_review_queue.csv"
CONSTRAINT_BRIDGE_FILE = OUTPUT_DIR / "phase4_capacity_constraint_bridge.csv"
WORKSTATION_LOAD_FILE = OUTPUT_DIR / "phase4_capacity_load_by_workstation.csv"
MACHINE_LOAD_FILE = OUTPUT_DIR / "phase4_capacity_load_by_machine_type.csv"
LABOR_LOAD_FILE = OUTPUT_DIR / "phase4_capacity_load_by_labor_skill.csv"
QUEUE_PRESSURE_FILE = OUTPUT_DIR / "phase4_queue_pressure_by_workstation.csv"
QUEUE_RISK_SUMMARY_FILE = OUTPUT_DIR / "phase4_queue_risk_summary.csv"
QUEUE_REVIEW_QUEUE_FILE = OUTPUT_DIR / "phase4_queue_manager_review_queue.csv"
QUEUE_VALIDATION_FILE = OUTPUT_DIR / "phase4_queue_validation.csv"
PRODUCT_ROUTINGS_FILE = DATA_DIR / "product_routings.csv"
PARALLEL_GROUPS_FILE = DATA_DIR / "routing_parallel_groups.csv"
WORKSTATIONS_FILE = DATA_DIR / "workstations.csv"

VISIBILITY_SUMMARY_OUTPUT_FILE = OUTPUT_DIR / "phase4_bottleneck_visibility_summary.csv"
PERIOD_EVIDENCE_OUTPUT_FILE = OUTPUT_DIR / "phase4_bottleneck_period_evidence.csv"
MANAGER_REVIEW_OUTPUT_FILE = OUTPUT_DIR / "phase4_bottleneck_manager_review_queue.csv"
VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_bottleneck_validation.csv"

CONFIRMATION_STATUS = "PLANNING_EVIDENCE_ONLY_NOT_SIMULATION_CONFIRMED"
EVIDENCE_TYPE = "CAPACITY_AND_ESTIMATED_QUEUE_PRESSURE"
SOURCE_PHASE = "PHASE4_STEP5B_BOTTLENECK_VISIBILITY"


def build_bottleneck_visibility_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build bottleneck visibility summary, period evidence, review queue, and validation."""
    checks: list[dict] = []
    frames = {
        "bottleneck_candidates": _load_csv(BOTTLENECK_CANDIDATE_FILE, "bottleneck_candidates", checks),
        "capacity_feasibility": _load_csv(CAPACITY_FEASIBILITY_FILE, "capacity_feasibility", checks),
        "capacity_review_queue": _load_csv(CAPACITY_REVIEW_QUEUE_FILE, "capacity_review_queue", checks),
        "constraint_bridge": _load_csv(CONSTRAINT_BRIDGE_FILE, "constraint_bridge", checks),
        "workstation_load": _load_csv(WORKSTATION_LOAD_FILE, "workstation_load", checks),
        "machine_load": _load_csv(MACHINE_LOAD_FILE, "machine_load", checks),
        "labor_load": _load_csv(LABOR_LOAD_FILE, "labor_load", checks),
        "queue_pressure": _load_csv(QUEUE_PRESSURE_FILE, "queue_pressure", checks),
        "queue_summary": _load_csv(QUEUE_RISK_SUMMARY_FILE, "queue_summary", checks),
        "queue_review_queue": _load_csv(QUEUE_REVIEW_QUEUE_FILE, "queue_review_queue", checks),
        "queue_validation": _load_csv(QUEUE_VALIDATION_FILE, "queue_validation", checks),
        "product_routings": _load_csv(PRODUCT_ROUTINGS_FILE, "product_routings", checks),
        "parallel_groups": _load_csv(PARALLEL_GROUPS_FILE, "parallel_groups", checks),
        "workstations": _load_csv(WORKSTATIONS_FILE, "workstations", checks),
    }
    summary = pd.DataFrame()
    period_evidence = pd.DataFrame()
    review_queue = pd.DataFrame()
    if all(frame is not None for frame in frames.values()):
        period_evidence = _build_period_evidence(frames["queue_pressure"])
        summary = _build_visibility_summary(frames["bottleneck_candidates"], frames["queue_summary"], period_evidence)
        review_queue = _build_manager_review_queue(summary, period_evidence)
        _validate_bottleneck_outputs(summary, period_evidence, review_queue, frames["queue_validation"], checks)
    _check_no_blocked_outputs(checks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(VISIBILITY_SUMMARY_OUTPUT_FILE, index=False)
    period_evidence.to_csv(PERIOD_EVIDENCE_OUTPUT_FILE, index=False)
    review_queue.to_csv(MANAGER_REVIEW_OUTPUT_FILE, index=False)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    return summary, period_evidence, review_queue, validation


def _build_period_evidence(queue_pressure: pd.DataFrame) -> pd.DataFrame:
    frame = queue_pressure.copy()
    for column in [
        "workstation_utilization_pct",
        "capacity_gap_hours",
        "estimated_queue_pressure_score",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    frame["period_bottleneck_visibility_score"] = frame.apply(_period_score, axis=1)
    frame["period_bottleneck_visibility_level"] = frame["period_bottleneck_visibility_score"].apply(_level)
    frame["period_bottleneck_reason"] = frame.apply(_period_reason, axis=1)
    frame["evidence_type"] = EVIDENCE_TYPE
    frame["confirmation_status"] = CONFIRMATION_STATUS
    frame["source_phase"] = SOURCE_PHASE
    frame["advisory_only_flag"] = True
    return frame[
        [
            "planning_run_id",
            "period_start",
            "period_end",
            "workstation_id",
            "workstation_name",
            "workstation_capacity_status",
            "workstation_utilization_pct",
            "capacity_gap_hours",
            "machine_constraint_flag",
            "labor_constraint_flag",
            "labor_high_utilization_warning_flag",
            "estimated_queue_pressure_score",
            "estimated_queue_pressure_level",
            "estimated_wip_risk_level",
            "routing_join_pressure_flag",
            "parallel_merge_pressure_flag",
            "period_bottleneck_visibility_score",
            "period_bottleneck_visibility_level",
            "period_bottleneck_reason",
            "evidence_type",
            "confirmation_status",
            "source_phase",
            "advisory_only_flag",
        ]
    ].copy()


def _build_visibility_summary(
    candidates: pd.DataFrame,
    queue_summary: pd.DataFrame,
    period_evidence: pd.DataFrame,
) -> pd.DataFrame:
    candidate = candidates.copy()
    queue = queue_summary.copy()
    for column in [
        "bottleneck_candidate_score",
        "max_workstation_utilization_pct",
        "avg_workstation_utilization_pct",
        "total_required_workstation_hours",
        "total_available_workstation_hours",
        "cumulative_capacity_gap_hours",
    ]:
        if column in candidate.columns:
            candidate[column] = pd.to_numeric(candidate[column], errors="coerce").fillna(0)
    for column in [
        "max_estimated_queue_pressure_score",
        "avg_estimated_queue_pressure_score",
        "total_negative_capacity_gap_hours",
    ]:
        if column in queue.columns:
            queue[column] = pd.to_numeric(queue[column], errors="coerce").fillna(0)

    summary = candidate.merge(
        queue[
            [
                "planning_run_id",
                "workstation_id",
                "overall_queue_risk_level",
                "critical_queue_pressure_period_count",
                "high_queue_pressure_period_count",
                "max_estimated_queue_pressure_score",
                "avg_estimated_queue_pressure_score",
                "total_negative_capacity_gap_hours",
                "routing_join_pressure_period_count",
                "parallel_merge_pressure_period_count",
            ]
        ],
        on=["planning_run_id", "workstation_id"],
        how="left",
    )
    summary = summary.rename(
        columns={
            "bottleneck_candidate_level": "capacity_candidate_level",
            "overall_queue_risk_level": "queue_risk_level",
            "bottleneck_candidate_score": "capacity_bottleneck_score",
        }
    )
    fill_zero = [
        "critical_queue_pressure_period_count",
        "high_queue_pressure_period_count",
        "max_estimated_queue_pressure_score",
        "avg_estimated_queue_pressure_score",
        "routing_join_pressure_period_count",
        "parallel_merge_pressure_period_count",
        "capacity_bottleneck_score",
    ]
    for column in fill_zero:
        summary[column] = pd.to_numeric(summary.get(column, 0), errors="coerce").fillna(0)
    summary["queue_risk_level"] = summary["queue_risk_level"].fillna("LOW")
    summary["queue_pressure_score"] = summary.apply(_queue_score_contribution, axis=1)
    summary["combined_bottleneck_visibility_score"] = summary["capacity_bottleneck_score"] + summary["queue_pressure_score"]
    summary = summary.sort_values(
        [
            "combined_bottleneck_visibility_score",
            "critical_queue_pressure_period_count",
            "overloaded_period_count",
            "max_workstation_utilization_pct",
        ],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    summary["bottleneck_visibility_rank"] = range(1, len(summary) + 1)
    summary["bottleneck_visibility_level"] = summary.apply(_summary_level, axis=1)
    summary["bottleneck_visibility_reason"] = summary.apply(_summary_reason, axis=1)
    summary["bottleneck_evidence_layers"] = summary.apply(_evidence_layers, axis=1)
    summary["recommended_manager_focus"] = summary.apply(_manager_focus, axis=1)
    summary["confirmation_status"] = CONFIRMATION_STATUS
    summary["source_phase"] = SOURCE_PHASE
    summary["advisory_only_flag"] = True

    required = [
        "planning_run_id",
        "workstation_id",
        "workstation_name",
        "periods_observed",
        "capacity_candidate_level",
        "queue_risk_level",
        "max_workstation_utilization_pct",
        "avg_workstation_utilization_pct",
        "overloaded_period_count",
        "near_capacity_period_count",
        "labor_high_utilization_warning_period_count",
        "machine_constraint_period_count",
        "labor_hard_overload_period_count",
        "critical_queue_pressure_period_count",
        "high_queue_pressure_period_count",
        "max_estimated_queue_pressure_score",
        "avg_estimated_queue_pressure_score",
        "total_negative_capacity_gap_hours",
        "routing_join_pressure_period_count",
        "parallel_merge_pressure_period_count",
        "capacity_bottleneck_score",
        "queue_pressure_score",
        "combined_bottleneck_visibility_score",
        "bottleneck_visibility_rank",
        "bottleneck_visibility_level",
        "bottleneck_visibility_reason",
        "bottleneck_evidence_layers",
        "recommended_manager_focus",
        "confirmation_status",
        "source_phase",
        "advisory_only_flag",
    ]
    for column in required:
        if column not in summary.columns:
            summary[column] = 0 if column.endswith("_count") or column.endswith("_score") else ""
    return summary[required].copy()


def _build_manager_review_queue(summary: pd.DataFrame, period_evidence: pd.DataFrame) -> pd.DataFrame:
    rows = []
    item = 1
    high_summary = summary[summary["bottleneck_visibility_level"].isin(["HIGH", "CRITICAL"])]
    for _, row in high_summary.iterrows():
        severity = str(row["bottleneck_visibility_level"])
        issue_type = "QUEUE_PRESSURE_SUPPORTED_BOTTLENECK_CANDIDATE" if "QUEUE_PRESSURE" in str(row["bottleneck_evidence_layers"]) else "CAPACITY_BOTTLENECK_CANDIDATE"
        rows.append(_review_row(item, row, "", "", issue_type, severity, float(row["combined_bottleneck_visibility_score"]), str(row["bottleneck_visibility_level"]), str(row["bottleneck_visibility_reason"]), str(row["bottleneck_evidence_layers"]), _review_action(row)))
        item += 1

    period_rows = period_evidence[period_evidence["period_bottleneck_visibility_level"].isin(["HIGH", "CRITICAL"])]
    for _, row in period_rows.iterrows():
        issue_type = _period_issue_type(row)
        severity = str(row["period_bottleneck_visibility_level"])
        rows.append(_review_row(item, row, row["period_start"], row["period_end"], issue_type, severity, float(row["period_bottleneck_visibility_score"]), severity, str(row["period_bottleneck_reason"]), _period_layers(row), _period_review_action(row)))
        item += 1
    return pd.DataFrame(
        rows,
        columns=[
            "planning_run_id",
            "bottleneck_review_item_id",
            "period_start",
            "period_end",
            "workstation_id",
            "workstation_name",
            "bottleneck_issue_type",
            "bottleneck_issue_severity",
            "bottleneck_visibility_score",
            "bottleneck_visibility_level",
            "bottleneck_issue_description",
            "evidence_layers",
            "suggested_review_action",
            "auto_action_allowed",
            "advisory_only_flag",
        ],
    )


def _period_score(row: pd.Series) -> float:
    score = float(row["estimated_queue_pressure_score"]) * 0.6
    if str(row["workstation_capacity_status"]) == "OVERLOADED":
        score += 45
    if _bool_value(row["machine_constraint_flag"]):
        score += 20
    if _bool_value(row["labor_constraint_flag"]):
        score += 20
    if _bool_value(row["labor_high_utilization_warning_flag"]):
        score += 10
    if _bool_value(row["routing_join_pressure_flag"]):
        score += 10
    if _bool_value(row["parallel_merge_pressure_flag"]):
        score += 10
    if float(row["capacity_gap_hours"]) < -40:
        score += 20
    return max(score, 0)


def _queue_score_contribution(row: pd.Series) -> float:
    score = 0.0
    if float(row["critical_queue_pressure_period_count"]) > 0:
        score += 30
    if float(row["high_queue_pressure_period_count"]) > 0:
        score += 15
    if float(row["routing_join_pressure_period_count"]) > 0:
        score += 10
    if float(row["parallel_merge_pressure_period_count"]) > 0:
        score += 10
    if float(row["labor_high_utilization_warning_period_count"]) > 0:
        score += 10
    if float(row["periods_observed"]) and float(row["overloaded_period_count"]) / float(row["periods_observed"]) >= 0.5:
        score += 20
    if float(row["total_negative_capacity_gap_hours"]) < -250:
        score += 20
    return score


def _level(score: float) -> str:
    if score >= 130:
        return "CRITICAL"
    if score >= 80:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def _summary_level(row: pd.Series) -> str:
    if float(row["overloaded_period_count"]) > 0 and float(row["critical_queue_pressure_period_count"]) > 0:
        return "CRITICAL"
    if float(row["overloaded_period_count"]) > 0 or float(row["high_queue_pressure_period_count"]) > 0:
        return "HIGH"
    if float(row["near_capacity_period_count"]) > 0 or float(row["labor_high_utilization_warning_period_count"]) > 0:
        return "MEDIUM"
    return "LOW"


def _period_reason(row: pd.Series) -> str:
    parts = []
    if str(row["workstation_capacity_status"]) == "OVERLOADED":
        parts.append("WORKSTATION_OVERLOAD")
    if _bool_value(row["machine_constraint_flag"]):
        parts.append("MACHINE_CONSTRAINT")
    if _bool_value(row["labor_constraint_flag"]):
        parts.append("LABOR_HARD_CONSTRAINT")
    if _bool_value(row["labor_high_utilization_warning_flag"]):
        parts.append("LABOR_STRESS_WARNING")
    if str(row["estimated_queue_pressure_level"]) in {"HIGH", "CRITICAL"}:
        parts.append("QUEUE_PRESSURE")
    if _bool_value(row["routing_join_pressure_flag"]):
        parts.append("ROUTING_JOIN_PRESSURE")
    return ";".join(parts) if parts else "LOW_PLANNING_BOTTLENECK_EVIDENCE"


def _summary_reason(row: pd.Series) -> str:
    return (
        "Planning-based bottleneck candidate: "
        f"capacity_level={row['capacity_candidate_level']}, queue_level={row['queue_risk_level']}, "
        f"overloaded_periods={int(row['overloaded_period_count'])}, "
        f"critical_queue_periods={int(row['critical_queue_pressure_period_count'])}, "
        f"combined_score={float(row['combined_bottleneck_visibility_score']):.2f}."
    )


def _evidence_layers(row: pd.Series) -> str:
    layers = []
    if float(row["overloaded_period_count"]) > 0 or float(row["near_capacity_period_count"]) > 0:
        layers.append("WORKSTATION_CAPACITY")
    if float(row["machine_constraint_period_count"]) > 0:
        layers.append("MACHINE_CAPACITY")
    if float(row["labor_hard_overload_period_count"]) > 0:
        layers.append("LABOR_CAPACITY")
    if float(row["labor_high_utilization_warning_period_count"]) > 0:
        layers.append("LABOR_STRESS")
    if float(row["critical_queue_pressure_period_count"]) > 0 or float(row["high_queue_pressure_period_count"]) > 0:
        layers.append("QUEUE_PRESSURE")
    if float(row["routing_join_pressure_period_count"]) > 0:
        layers.append("ROUTING_JOIN_PRESSURE")
    return ";".join(layers) if layers else "LOW_EVIDENCE"


def _manager_focus(row: pd.Series) -> str:
    if str(row["workstation_id"]) == "WS-FINAL-ASM":
        return "REVIEW_FINAL_ASSEMBLY_CAPACITY"
    if float(row["labor_high_utilization_warning_period_count"]) > 0:
        return "REVIEW_LABOR_STRESS"
    if float(row["routing_join_pressure_period_count"]) > 0:
        return "REVIEW_ROUTING_JOIN_ASSUMPTIONS"
    if float(row["overloaded_period_count"]) > 0:
        return "REVIEW_WORKSTATION_CALENDAR"
    return "REVIEW_BEFORE_ACTION"


def _period_issue_type(row: pd.Series) -> str:
    if _bool_value(row["routing_join_pressure_flag"]) and str(row["period_bottleneck_visibility_level"]) in {"HIGH", "CRITICAL"}:
        return "ROUTING_JOIN_PRESSURE_BOTTLENECK_RISK"
    if _bool_value(row["labor_high_utilization_warning_flag"]):
        return "LABOR_STRESS_BOTTLENECK_RISK"
    if str(row["workstation_capacity_status"]) == "OVERLOADED":
        return "RECURRING_WORKSTATION_OVERLOAD"
    if str(row["estimated_queue_pressure_level"]) in {"HIGH", "CRITICAL"}:
        return "QUEUE_PRESSURE_SUPPORTED_BOTTLENECK_CANDIDATE"
    return "CAPACITY_BOTTLENECK_CANDIDATE"


def _period_layers(row: pd.Series) -> str:
    return _period_reason(row).replace(";", ";")


def _period_review_action(row: pd.Series) -> str:
    if str(row["workstation_id"]) == "WS-FINAL-ASM":
        return "REVIEW_FINAL_ASSEMBLY_CAPACITY"
    if _bool_value(row["routing_join_pressure_flag"]):
        return "REVIEW_ROUTING_JOIN_ASSUMPTIONS"
    if _bool_value(row["labor_high_utilization_warning_flag"]):
        return "REVIEW_LABOR_STRESS"
    if str(row["workstation_capacity_status"]) == "OVERLOADED":
        return "REVIEW_WORKSTATION_CALENDAR"
    return "REVIEW_BEFORE_ACTION"


def _review_action(row: pd.Series) -> str:
    return _manager_focus(row)


def _review_row(
    item: int,
    row: pd.Series,
    period_start: object,
    period_end: object,
    issue_type: str,
    severity: str,
    score: float,
    level: str,
    description: str,
    layers: str,
    action: str,
) -> dict:
    return {
        "planning_run_id": row["planning_run_id"],
        "bottleneck_review_item_id": f"BN-REV-{item:04d}",
        "period_start": period_start,
        "period_end": period_end,
        "workstation_id": row["workstation_id"],
        "workstation_name": row["workstation_name"],
        "bottleneck_issue_type": issue_type,
        "bottleneck_issue_severity": severity,
        "bottleneck_visibility_score": round(score, 4),
        "bottleneck_visibility_level": level,
        "bottleneck_issue_description": description,
        "evidence_layers": layers,
        "suggested_review_action": action,
        "auto_action_allowed": False,
        "advisory_only_flag": True,
    }


def _validate_bottleneck_outputs(
    summary: pd.DataFrame,
    period_evidence: pd.DataFrame,
    review: pd.DataFrame,
    queue_validation: pd.DataFrame,
    checks: list[dict],
) -> None:
    required_summary = {
        "planning_run_id",
        "workstation_id",
        "workstation_name",
        "combined_bottleneck_visibility_score",
        "bottleneck_visibility_rank",
        "bottleneck_visibility_level",
        "confirmation_status",
        "advisory_only_flag",
    }
    required_period = {
        "planning_run_id",
        "period_start",
        "period_end",
        "workstation_id",
        "period_bottleneck_visibility_score",
        "period_bottleneck_visibility_level",
        "evidence_type",
        "confirmation_status",
        "advisory_only_flag",
    }
    required_review = {
        "planning_run_id",
        "bottleneck_review_item_id",
        "bottleneck_issue_type",
        "bottleneck_issue_severity",
        "auto_action_allowed",
        "advisory_only_flag",
    }
    invalid = int(summary.empty) + int(period_evidence.empty)
    invalid += len(required_summary.difference(summary.columns))
    invalid += len(required_period.difference(period_evidence.columns))
    if not summary.empty:
        scores = pd.to_numeric(summary["combined_bottleneck_visibility_score"], errors="coerce")
        ranks = pd.to_numeric(summary["bottleneck_visibility_rank"], errors="coerce")
        invalid += int(scores.isna().sum() + (scores < 0).sum())
        invalid += int(ranks.isna().sum())
        invalid += int(summary["bottleneck_visibility_rank"].duplicated().sum())
        invalid += int((~summary["bottleneck_visibility_level"].astype(str).isin({"LOW", "MEDIUM", "HIGH", "CRITICAL"})).sum())
        invalid += int((summary["confirmation_status"].astype(str) != CONFIRMATION_STATUS).sum())
        invalid += int((~_to_bool(summary["advisory_only_flag"])).sum())
        final_assembly = summary[summary["workstation_id"].astype(str).eq("WS-FINAL-ASM")]
        if final_assembly.empty or final_assembly["bottleneck_visibility_level"].astype(str).isin({"HIGH", "CRITICAL"}).sum() == 0:
            invalid += 1
    if not period_evidence.empty:
        invalid += int((~period_evidence["period_bottleneck_visibility_level"].astype(str).isin({"LOW", "MEDIUM", "HIGH", "CRITICAL"})).sum())
        invalid += int((period_evidence["confirmation_status"].astype(str) != CONFIRMATION_STATUS).sum())
        invalid += int((~_to_bool(period_evidence["advisory_only_flag"])).sum())
    high_or_critical = summary["bottleneck_visibility_level"].astype(str).isin({"HIGH", "CRITICAL"}).any() if not summary.empty else False
    if high_or_critical and review.empty:
        invalid += 1
    if not review.empty:
        invalid += len(required_review.difference(review.columns))
        invalid += int((~review["bottleneck_issue_type"].astype(str).isin({
            "CAPACITY_BOTTLENECK_CANDIDATE",
            "QUEUE_PRESSURE_SUPPORTED_BOTTLENECK_CANDIDATE",
            "RECURRING_WORKSTATION_OVERLOAD",
            "ROUTING_JOIN_PRESSURE_BOTTLENECK_RISK",
            "LABOR_STRESS_BOTTLENECK_RISK",
            "REVIEW_REQUIRED",
        })).sum())
        invalid += int((~review["bottleneck_issue_severity"].astype(str).isin({"LOW", "MEDIUM", "HIGH", "CRITICAL"})).sum())
        invalid += int(_to_bool(review["auto_action_allowed"]).sum())
        invalid += int((~_to_bool(review["advisory_only_flag"])).sum())
    if not queue_validation.empty and "status" in queue_validation.columns:
        invalid += int((queue_validation["status"].astype(str).str.upper() == "FAIL").sum())
    forbidden_columns = [column for column in summary.columns if any(token in column.lower() for token in ["final_bottleneck", "actual_bottleneck", "measured_bottleneck", "simulation_confirmed_bottleneck"])]
    invalid += len(forbidden_columns)
    checks.append(
        _result(
            "bottleneck_step5b_outputs_valid",
            "Step 5B bottleneck visibility outputs valid",
            "FAIL" if invalid else "PASS",
            f"Step 5B missing/invalid values: {invalid}" if invalid else f"Bottleneck visibility outputs valid; summary_rows={len(summary)}, period_rows={len(period_evidence)}, review_rows={len(review)}.",
            invalid,
        )
    )


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked_tokens = [
        "actual_bottleneck",
        "measured_bottleneck",
        "final_bottleneck",
        "simulation_confirmed_bottleneck",
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
            "bottleneck_no_blocked_execution_outputs",
            "bottleneck no blocked execution outputs",
            "FAIL" if bad_files else "PASS",
            f"Blocked measured-bottleneck/queue/scheduling/simulation/execution outputs found: {bad_files}" if bad_files else "No measured bottleneck, real queue measurement, scheduling, simulation, or execution outputs found.",
            len(bad_files),
        )
    )


def _load_csv(path: Path, name: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"bottleneck_{name}_exists", f"{name} exists", "FAIL", f"Missing file: {path}", 1))
        return None
    frame = pd.read_csv(path, keep_default_na=False)
    checks.append(_result(f"bottleneck_{name}_exists", f"{name} exists", "PASS", f"Loaded {path}", 0))
    if frame.empty:
        checks.append(_result(f"bottleneck_{name}_not_empty", f"{name} not empty", "WARNING", f"{name} has no rows.", 1))
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
    _, _, _, validation = build_bottleneck_visibility_outputs()
    status_counts = validation["status"].value_counts().to_dict() if not validation.empty else {}
    print(f"Bottleneck validation rows: {len(validation)}")
    print(f"Bottleneck validation status counts: {status_counts}")
