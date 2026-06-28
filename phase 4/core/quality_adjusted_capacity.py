"""Estimate advisory quality-adjusted capacity impact for Phase 4 Step 6B."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PHASE4_DIR / "data"
OUTPUT_DIR = PHASE4_DIR / "outputs"

QUALITY_RULES_FILE = DATA_DIR / "quality_rules.csv"
REWORK_RULES_FILE = DATA_DIR / "rework_rules.csv"
PRODUCT_ROUTINGS_FILE = DATA_DIR / "product_routings.csv"
WORKSTATIONS_FILE = DATA_DIR / "workstations.csv"

QUALITY_TREND_OPERATION_FILE = OUTPUT_DIR / "phase4_quality_trend_by_operation.csv"
PROCESSING_TIME_TREND_FILE = OUTPUT_DIR / "phase4_processing_time_trend_by_workstation.csv"
WORKSTATION_PERFORMANCE_FILE = OUTPUT_DIR / "phase4_workstation_performance_trend_summary.csv"
CAPACITY_OPERATION_DETAIL_FILE = OUTPUT_DIR / "phase4_capacity_operation_load_detail.csv"
CAPACITY_WORKSTATION_FILE = OUTPUT_DIR / "phase4_capacity_load_by_workstation.csv"
BOTTLENECK_VISIBILITY_FILE = OUTPUT_DIR / "phase4_bottleneck_visibility_summary.csv"
PRODUCTION_FLOW_FILE = OUTPUT_DIR / "phase4_production_flow_view.csv"
QUALITY_VALIDATION_FILE = OUTPUT_DIR / "phase4_quality_validation.csv"
FLOW_VALIDATION_FILE = OUTPUT_DIR / "phase4_flow_validation.csv"
CAPACITY_VALIDATION_FILE = OUTPUT_DIR / "phase4_capacity_validation.csv"
QUEUE_VALIDATION_FILE = OUTPUT_DIR / "phase4_queue_validation.csv"
BOTTLENECK_VALIDATION_FILE = OUTPUT_DIR / "phase4_bottleneck_validation.csv"

QUALITY_IMPACT_OPERATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_quality_impact_by_operation.csv"
QUALITY_ADJUSTED_CAPACITY_OUTPUT_FILE = OUTPUT_DIR / "phase4_quality_adjusted_capacity_by_workstation.csv"
QUALITY_ADJUSTED_BOTTLENECK_OUTPUT_FILE = OUTPUT_DIR / "phase4_quality_adjusted_bottleneck_impact.csv"
QUALITY_MATERIAL_LOSS_OUTPUT_FILE = OUTPUT_DIR / "phase4_quality_material_loss_exposure.csv"
QUALITY_IMPACT_MANAGER_REVIEW_OUTPUT_FILE = OUTPUT_DIR / "phase4_quality_impact_manager_review_queue.csv"
QUALITY_ADJUSTED_VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_quality_adjusted_capacity_validation.csv"

CONFIRMATION_STATUS = "PLANNING_ESTIMATE_ONLY_NOT_EXECUTION_CONFIRMED"
SOURCE_PHASE = "PHASE4_STEP6B_QUALITY_ADJUSTED_CAPACITY"
VALID_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_STATUSES = {"NO_LOAD", "FEASIBLE", "NEAR_CAPACITY", "OVERLOADED", "NO_CAPACITY_RECORD", "REVIEW_REQUIRED"}
DISPOSITION_MODEL_BASIS = "DEFECT_DISPOSITION_RECONCILIATION"
BALANCE_TOLERANCE = 0.0001


def build_quality_adjusted_capacity_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build Step 6B advisory quality impact, capacity impact, review, and validation outputs."""
    checks: list[dict] = []
    frames = {
        "quality_rules": _load_csv(QUALITY_RULES_FILE, "quality_rules", checks),
        "rework_rules": _load_csv(REWORK_RULES_FILE, "rework_rules", checks),
        "quality_trend_operation": _load_csv(QUALITY_TREND_OPERATION_FILE, "quality_trend_operation", checks),
        "processing_time_trend": _load_csv(PROCESSING_TIME_TREND_FILE, "processing_time_trend", checks),
        "workstation_performance": _load_csv(WORKSTATION_PERFORMANCE_FILE, "workstation_performance", checks),
        "capacity_operation_detail": _load_csv(CAPACITY_OPERATION_DETAIL_FILE, "capacity_operation_detail", checks),
        "capacity_workstation": _load_csv(CAPACITY_WORKSTATION_FILE, "capacity_workstation", checks),
        "bottleneck_visibility": _load_csv(BOTTLENECK_VISIBILITY_FILE, "bottleneck_visibility", checks),
        "production_flow": _load_csv(PRODUCTION_FLOW_FILE, "production_flow", checks),
        "product_routings": _load_csv(PRODUCT_ROUTINGS_FILE, "product_routings", checks),
        "workstations": _load_csv(WORKSTATIONS_FILE, "workstations", checks),
        "quality_validation": _load_csv(QUALITY_VALIDATION_FILE, "quality_validation", checks),
        "flow_validation": _load_csv(FLOW_VALIDATION_FILE, "flow_validation", checks),
        "capacity_validation": _load_csv(CAPACITY_VALIDATION_FILE, "capacity_validation", checks),
        "queue_validation": _load_csv(QUEUE_VALIDATION_FILE, "queue_validation", checks),
        "bottleneck_validation": _load_csv(BOTTLENECK_VALIDATION_FILE, "bottleneck_validation", checks),
    }
    impact = pd.DataFrame()
    adjusted_capacity = pd.DataFrame()
    bottleneck_impact = pd.DataFrame()
    material_loss = pd.DataFrame()
    review = pd.DataFrame()

    if all(frame is not None for frame in frames.values()):
        impact = _build_quality_impact_by_operation(
            frames["capacity_operation_detail"],
            frames["quality_rules"],
            frames["rework_rules"],
            frames["quality_trend_operation"],
            frames["processing_time_trend"],
            frames["workstations"],
        )
        adjusted_capacity = _build_quality_adjusted_capacity_by_workstation(impact, frames["capacity_workstation"])
        bottleneck_impact = _build_bottleneck_impact(adjusted_capacity, frames["bottleneck_visibility"], frames["workstation_performance"])
        material_loss = _build_material_loss_exposure(impact)
        review = _build_manager_review_queue(impact, adjusted_capacity, bottleneck_impact, material_loss)
        _validate_outputs(impact, adjusted_capacity, bottleneck_impact, material_loss, review, frames, checks)
    _check_no_blocked_outputs(checks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    impact.to_csv(QUALITY_IMPACT_OPERATION_OUTPUT_FILE, index=False)
    adjusted_capacity.to_csv(QUALITY_ADJUSTED_CAPACITY_OUTPUT_FILE, index=False)
    bottleneck_impact.to_csv(QUALITY_ADJUSTED_BOTTLENECK_OUTPUT_FILE, index=False)
    material_loss.to_csv(QUALITY_MATERIAL_LOSS_OUTPUT_FILE, index=False)
    review.to_csv(QUALITY_IMPACT_MANAGER_REVIEW_OUTPUT_FILE, index=False)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    validation.to_csv(QUALITY_ADJUSTED_VALIDATION_OUTPUT_FILE, index=False)
    return impact, adjusted_capacity, bottleneck_impact, material_loss, review, validation


def _build_quality_impact_by_operation(
    detail: pd.DataFrame,
    quality_rules: pd.DataFrame,
    rework_rules: pd.DataFrame,
    trend: pd.DataFrame,
    processing: pd.DataFrame,
    workstations: pd.DataFrame,
) -> pd.DataFrame:
    frame = detail.copy()
    frame = frame.merge(workstations[["workstation_id", "workstation_name"]].drop_duplicates("workstation_id"), on="workstation_id", how="left")
    if "workstation_name_x" in frame.columns:
        frame["workstation_name"] = frame["workstation_name_x"].fillna(frame.get("workstation_name_y", ""))
        frame = frame.drop(columns=[column for column in ["workstation_name_x", "workstation_name_y"] if column in frame.columns])
    active_quality = quality_rules[_to_bool(quality_rules.get("active_flag", pd.Series(True, index=quality_rules.index)))].copy()
    active_rework = rework_rules[_to_bool(rework_rules.get("active_flag", pd.Series(True, index=rework_rules.index)))].copy()
    quality_columns = ["operation_id", "workstation_id", "expected_defect_rate", "expected_rework_rate", "expected_scrap_rate"]
    if "discount_review_rate" in active_quality.columns:
        quality_columns.append("discount_review_rate")
    frame = frame.merge(
        active_quality[quality_columns].drop_duplicates(["operation_id", "workstation_id"]),
        on=["operation_id", "workstation_id"],
        how="left",
    )
    rework_columns = [
        "operation_id",
        "workstation_id",
        "defects_reworkable_flag",
        "defects_scrapable_flag",
        "discount_review_allowed_flag",
        "rework_success_probability",
        "extra_rework_time_minutes",
    ]
    if "discount_review_rate" in active_rework.columns:
        rework_columns.append("discount_review_rate")
    frame = frame.merge(
        active_rework[rework_columns].drop_duplicates(["operation_id", "workstation_id"]),
        on=["operation_id", "workstation_id"],
        how="left",
        suffixes=("", "_rework_rule"),
    )
    trend_ref = trend[
        ["finished_sku", "operation_id", "workstation_id", "avg_defect_rate", "avg_rework_rate", "avg_scrap_rate", "quality_trend_overall"]
    ].drop_duplicates(["finished_sku", "operation_id", "workstation_id"])
    frame = frame.merge(trend_ref, on=["finished_sku", "operation_id", "workstation_id"], how="left")
    processing_ref = processing[
        ["workstation_id", "avg_processing_time_variance_pct", "processing_time_trend"]
    ].drop_duplicates("workstation_id")
    frame = frame.merge(processing_ref, on="workstation_id", how="left")

    for column in ["planned_production_qty", "total_required_hours", "expected_defect_rate", "expected_rework_rate", "expected_scrap_rate", "avg_defect_rate", "avg_rework_rate", "avg_scrap_rate", "rework_success_probability", "extra_rework_time_minutes", "avg_processing_time_variance_pct", "discount_review_rate", "discount_review_rate_rework_rule"]:
        source = frame[column] if column in frame.columns else pd.Series(0, index=frame.index)
        frame[column] = pd.to_numeric(source, errors="coerce").fillna(0)
    frame["defect_rate_source"] = frame.apply(lambda row: _rate_source(row, "expected_defect_rate", "avg_defect_rate"), axis=1)
    frame["rework_rate_source"] = frame.apply(lambda row: _rate_source(row, "expected_rework_rate", "avg_rework_rate"), axis=1)
    frame["scrap_rate_source"] = frame.apply(lambda row: _rate_source(row, "expected_scrap_rate", "avg_scrap_rate"), axis=1)
    frame["defect_rate_used"] = frame["expected_defect_rate"].where(frame["expected_defect_rate"] > 0, frame["avg_defect_rate"]).clip(lower=0, upper=1)
    raw_rework_rate = frame["expected_rework_rate"].where(frame["expected_rework_rate"] > 0, frame["avg_rework_rate"]).clip(lower=0)
    raw_scrap_rate = frame["expected_scrap_rate"].where(frame["expected_scrap_rate"] > 0, frame["avg_scrap_rate"]).clip(lower=0)
    frame["rework_rate_used"] = _defect_share(raw_rework_rate, frame["defect_rate_used"])
    frame["scrap_rate_used"] = _defect_share(raw_scrap_rate, frame["defect_rate_used"])
    frame["discount_review_rate_used"] = frame["discount_review_rate"].where(frame["discount_review_rate"] > 0, frame["discount_review_rate_rework_rule"]).clip(lower=0, upper=1)
    frame["rework_success_probability"] = frame["rework_success_probability"].where(frame["rework_success_probability"] > 0, 0.85).clip(lower=0, upper=1)
    frame["extra_rework_time_minutes"] = frame["extra_rework_time_minutes"].clip(lower=0)
    frame["defects_reworkable_flag"] = _to_bool(frame.get("defects_reworkable_flag", pd.Series(False, index=frame.index)))
    frame["defects_scrapable_flag"] = _to_bool(frame.get("defects_scrapable_flag", pd.Series(False, index=frame.index)))
    frame["discount_review_allowed_flag"] = _to_bool(frame.get("discount_review_allowed_flag", pd.Series(False, index=frame.index)))

    planned = frame["planned_production_qty"].clip(lower=0)
    original_hours = frame["total_required_hours"].clip(lower=0)
    frame["defective_units"] = planned * frame["defect_rate_used"]
    frame["first_pass_good_units"] = (planned - frame["defective_units"]).clip(lower=0)
    frame["reworkable_share_used"] = frame["rework_rate_used"].where(frame["defects_reworkable_flag"], 0).clip(lower=0, upper=1)
    frame["direct_scrap_share_used"] = frame["scrap_rate_used"].where(frame["defects_scrapable_flag"], 0).clip(lower=0, upper=1)
    frame["discount_review_rate_used"] = frame["discount_review_rate_used"].where(frame["discount_review_allowed_flag"], 0).clip(lower=0, upper=1)
    initial_share_total = frame["reworkable_share_used"] + frame["direct_scrap_share_used"] + frame["discount_review_rate_used"]
    scale = initial_share_total.where(initial_share_total > 1, 1)
    frame.loc[initial_share_total > 1, "reworkable_share_used"] = frame.loc[initial_share_total > 1, "reworkable_share_used"] / scale.loc[initial_share_total > 1]
    frame.loc[initial_share_total > 1, "direct_scrap_share_used"] = frame.loc[initial_share_total > 1, "direct_scrap_share_used"] / scale.loc[initial_share_total > 1]
    frame.loc[initial_share_total > 1, "discount_review_rate_used"] = frame.loc[initial_share_total > 1, "discount_review_rate_used"] / scale.loc[initial_share_total > 1]
    frame["other_disposition_share_used"] = (1 - frame["reworkable_share_used"] - frame["direct_scrap_share_used"] - frame["discount_review_rate_used"]).clip(lower=0)
    frame["rework_rate_used"] = frame["reworkable_share_used"]
    frame["scrap_rate_used"] = frame["direct_scrap_share_used"]
    frame["disposition_rate_total"] = frame["reworkable_share_used"] + frame["direct_scrap_share_used"] + frame["discount_review_rate_used"] + frame["other_disposition_share_used"]
    frame["disposition_rate_balance_status"] = frame.apply(_disposition_rate_status, axis=1)
    frame["reworkable_defect_units"] = frame["defective_units"] * frame["reworkable_share_used"]
    frame["direct_scrap_units"] = frame["defective_units"] * frame["direct_scrap_share_used"]
    frame["discount_review_units"] = frame["defective_units"] * frame["discount_review_rate_used"]
    frame["other_defect_disposition_units"] = frame["defective_units"] * frame["other_disposition_share_used"]
    frame["defect_disposition_total_units"] = (
        frame["reworkable_defect_units"] + frame["direct_scrap_units"] + frame["discount_review_units"] + frame["other_defect_disposition_units"]
    )
    frame["defect_disposition_balance_check"] = frame["defective_units"] - frame["defect_disposition_total_units"]
    frame["defect_disposition_balance_status"] = frame["defect_disposition_balance_check"].abs().le(BALANCE_TOLERANCE).map({True: "BALANCED", False: "REVIEW_REQUIRED"})
    frame["rework_success_units"] = frame["reworkable_defect_units"] * frame["rework_success_probability"]
    frame["rework_failure_units"] = frame["reworkable_defect_units"] * (1 - frame["rework_success_probability"])
    frame["final_expected_good_units"] = (frame["first_pass_good_units"] + frame["rework_success_units"]).clip(lower=0)
    frame["total_expected_loss_units"] = (
        frame["direct_scrap_units"] + frame["rework_failure_units"] + frame["discount_review_units"] + frame["other_defect_disposition_units"]
    ).clip(lower=0)
    frame["final_quality_balance_check"] = planned - frame["final_expected_good_units"] - frame["total_expected_loss_units"]
    frame["final_quality_balance_status"] = frame["final_quality_balance_check"].abs().le(BALANCE_TOLERANCE).map({True: "BALANCED", False: "REVIEW_REQUIRED"})
    frame["disposition_model_basis"] = DISPOSITION_MODEL_BASIS
    frame["expected_defect_units"] = frame["defective_units"]
    frame["expected_rework_units"] = frame["reworkable_defect_units"]
    frame["expected_scrap_units"] = frame["direct_scrap_units"]
    frame["expected_rework_success_units"] = frame["rework_success_units"]
    frame["expected_rework_failure_units"] = frame["rework_failure_units"]
    frame["expected_good_units_after_quality"] = frame["final_expected_good_units"]
    frame["extra_rework_time_hours"] = frame["reworkable_defect_units"] * frame["extra_rework_time_minutes"] / 60
    frame["processing_time_trend"] = frame["processing_time_trend"].fillna("INSUFFICIENT_DATA")
    frame["processing_time_trend_adjustment_factor"] = frame.apply(_processing_adjustment_factor, axis=1)
    frame["processing_time_trend_adjustment_hours"] = original_hours * frame["processing_time_trend_adjustment_factor"]
    frame["quality_adjusted_required_hours"] = (
        original_hours + frame["extra_rework_time_hours"] + frame["processing_time_trend_adjustment_hours"]
    ).clip(lower=0)
    no_reduction_mask = (frame["extra_rework_time_hours"] > 0) | frame["processing_time_trend"].astype(str).eq("WORSENING")
    frame.loc[no_reduction_mask, "quality_adjusted_required_hours"] = frame.loc[no_reduction_mask, ["quality_adjusted_required_hours", "total_required_hours"]].max(axis=1)
    frame["quality_impact_level"] = frame.apply(_quality_impact_level, axis=1)
    frame["quality_impact_reason"] = frame.apply(_quality_impact_reason, axis=1)
    frame["confirmation_status"] = CONFIRMATION_STATUS
    frame["advisory_only_flag"] = True
    frame = frame.rename(columns={"total_required_hours": "original_total_required_hours"})
    return frame[
        [
            "planning_run_id",
            "period_start",
            "period_end",
            "finished_sku",
            "operation_id",
            "operation_name",
            "workstation_id",
            "workstation_name",
            "planned_production_qty",
            "original_total_required_hours",
            "defect_rate_used",
            "rework_rate_used",
            "scrap_rate_used",
            "defect_rate_source",
            "rework_rate_source",
            "scrap_rate_source",
            "discount_review_rate_used",
            "other_disposition_share_used",
            "disposition_rate_balance_status",
            "rework_success_probability",
            "first_pass_good_units",
            "defective_units",
            "reworkable_defect_units",
            "direct_scrap_units",
            "discount_review_units",
            "other_defect_disposition_units",
            "defect_disposition_total_units",
            "defect_disposition_balance_check",
            "defect_disposition_balance_status",
            "rework_success_units",
            "rework_failure_units",
            "final_expected_good_units",
            "total_expected_loss_units",
            "final_quality_balance_check",
            "final_quality_balance_status",
            "disposition_model_basis",
            "expected_defect_units",
            "expected_rework_units",
            "expected_scrap_units",
            "expected_good_units_after_quality",
            "expected_rework_success_units",
            "expected_rework_failure_units",
            "extra_rework_time_hours",
            "processing_time_trend",
            "processing_time_trend_adjustment_factor",
            "processing_time_trend_adjustment_hours",
            "quality_adjusted_required_hours",
            "quality_impact_level",
            "quality_impact_reason",
            "confirmation_status",
            "advisory_only_flag",
        ]
    ].copy()


def _build_quality_adjusted_capacity_by_workstation(impact: pd.DataFrame, workstation_capacity: pd.DataFrame) -> pd.DataFrame:
    grouped = impact.groupby(["planning_run_id", "period_start", "period_end", "workstation_id", "workstation_name"], as_index=False).agg(
        original_required_hours=("original_total_required_hours", "sum"),
        quality_extra_rework_hours=("extra_rework_time_hours", "sum"),
        processing_time_adjustment_hours=("processing_time_trend_adjustment_hours", "sum"),
        quality_adjusted_required_hours=("quality_adjusted_required_hours", "sum"),
        expected_defective_units=("defective_units", "sum"),
        expected_rework_units=("reworkable_defect_units", "sum"),
        expected_loss_units=("total_expected_loss_units", "sum"),
        expected_final_good_units=("final_expected_good_units", "sum"),
        disposition_review_required_count=("defect_disposition_balance_status", lambda s: int((s.astype(str) != "BALANCED").sum())),
        final_quality_review_required_count=("final_quality_balance_status", lambda s: int((s.astype(str) != "BALANCED").sum())),
    )
    capacity_ref = workstation_capacity[
        [
            "planning_run_id",
            "period_start",
            "period_end",
            "workstation_id",
            "available_hours",
            "utilization_pct",
            "capacity_status",
        ]
    ].drop_duplicates(["planning_run_id", "period_start", "period_end", "workstation_id"])
    grouped = grouped.merge(capacity_ref, on=["planning_run_id", "period_start", "period_end", "workstation_id"], how="left")
    grouped["available_hours"] = pd.to_numeric(grouped["available_hours"], errors="coerce").fillna(0).clip(lower=0)
    grouped["original_utilization_pct"] = pd.to_numeric(grouped["utilization_pct"], errors="coerce").fillna(0).clip(lower=0)
    grouped["quality_adjusted_utilization_pct"] = grouped.apply(
        lambda row: (row["quality_adjusted_required_hours"] / row["available_hours"] * 100) if row["available_hours"] > 0 else (0 if row["quality_adjusted_required_hours"] == 0 else 999.0),
        axis=1,
    )
    grouped["utilization_delta_pct"] = grouped["quality_adjusted_utilization_pct"] - grouped["original_utilization_pct"]
    grouped["original_capacity_status"] = grouped["capacity_status"].fillna("REVIEW_REQUIRED")
    grouped["quality_adjusted_capacity_status"] = grouped.apply(_capacity_status, axis=1)
    grouped["quality_capacity_impact_level"] = grouped.apply(_capacity_impact_level, axis=1)
    grouped["quality_balance_review_required_flag"] = (grouped["disposition_review_required_count"] > 0) | (grouped["final_quality_review_required_count"] > 0)
    grouped["quality_capacity_review_required_flag"] = grouped["quality_capacity_impact_level"].isin(["HIGH", "CRITICAL"]) | grouped["quality_balance_review_required_flag"]
    grouped["confirmation_status"] = CONFIRMATION_STATUS
    grouped["advisory_only_flag"] = True
    return grouped[
        [
            "planning_run_id",
            "period_start",
            "period_end",
            "workstation_id",
            "workstation_name",
            "original_required_hours",
            "quality_extra_rework_hours",
            "processing_time_adjustment_hours",
            "quality_adjusted_required_hours",
            "expected_defective_units",
            "expected_rework_units",
            "expected_loss_units",
            "expected_final_good_units",
            "disposition_review_required_count",
            "quality_balance_review_required_flag",
            "available_hours",
            "original_utilization_pct",
            "quality_adjusted_utilization_pct",
            "utilization_delta_pct",
            "original_capacity_status",
            "quality_adjusted_capacity_status",
            "quality_capacity_impact_level",
            "quality_capacity_review_required_flag",
            "confirmation_status",
            "advisory_only_flag",
        ]
    ].copy()


def _build_bottleneck_impact(adjusted: pd.DataFrame, bottleneck: pd.DataFrame, performance: pd.DataFrame) -> pd.DataFrame:
    summary = adjusted.groupby(["planning_run_id", "workstation_id", "workstation_name"], as_index=False).agg(
        quality_adjusted_utilization_pct=("quality_adjusted_utilization_pct", "max"),
        utilization_delta_pct=("utilization_delta_pct", "max"),
        quality_extra_rework_hours=("quality_extra_rework_hours", "sum"),
        quality_impact_level=("quality_capacity_impact_level", _max_level),
        expected_defective_units=("expected_defective_units", "sum"),
        expected_rework_units=("expected_rework_units", "sum"),
        expected_loss_units=("expected_loss_units", "sum"),
        quality_balance_review_required_flag=("quality_balance_review_required_flag", "max"),
    )
    ref = bottleneck[
        [
            "planning_run_id",
            "workstation_id",
            "bottleneck_visibility_level",
            "bottleneck_visibility_rank",
            "recommended_manager_focus",
        ]
    ].drop_duplicates(["planning_run_id", "workstation_id"])
    summary = summary.merge(ref, on=["planning_run_id", "workstation_id"], how="left")
    perf = performance[["workstation_id", "combined_workstation_performance_trend"]].drop_duplicates("workstation_id")
    summary = summary.merge(perf, on="workstation_id", how="left")
    summary["original_bottleneck_visibility_level"] = summary["bottleneck_visibility_level"].fillna("LOW")
    summary["original_bottleneck_visibility_rank"] = pd.to_numeric(summary["bottleneck_visibility_rank"], errors="coerce").fillna(0).astype(int)
    summary["bottleneck_risk_after_quality"] = summary.apply(_bottleneck_after_quality, axis=1)
    summary["bottleneck_rank_pressure_change"] = summary.apply(_rank_pressure_change, axis=1)
    summary["bottleneck_impact_reason"] = summary.apply(_bottleneck_impact_reason, axis=1)
    summary["recommended_manager_focus"] = summary["recommended_manager_focus"].fillna("REVIEW_QUALITY_AND_CAPACITY_IMPACT")
    summary["disposition_model_basis"] = DISPOSITION_MODEL_BASIS
    summary["confirmation_status"] = CONFIRMATION_STATUS
    summary["advisory_only_flag"] = True
    return summary[
        [
            "planning_run_id",
            "workstation_id",
            "workstation_name",
            "original_bottleneck_visibility_level",
            "original_bottleneck_visibility_rank",
            "quality_adjusted_utilization_pct",
            "utilization_delta_pct",
            "quality_extra_rework_hours",
            "expected_defective_units",
            "expected_rework_units",
            "expected_loss_units",
            "quality_balance_review_required_flag",
            "quality_impact_level",
            "bottleneck_risk_after_quality",
            "bottleneck_rank_pressure_change",
            "bottleneck_impact_reason",
            "recommended_manager_focus",
            "disposition_model_basis",
            "confirmation_status",
            "advisory_only_flag",
        ]
    ].copy()


def _build_material_loss_exposure(impact: pd.DataFrame) -> pd.DataFrame:
    material = impact[
        [
            "planning_run_id",
            "period_start",
            "period_end",
            "finished_sku",
            "operation_id",
            "workstation_id",
            "defective_units",
            "direct_scrap_units",
            "rework_failure_units",
            "discount_review_units",
            "other_defect_disposition_units",
            "total_expected_loss_units",
            "final_expected_good_units",
            "defect_disposition_balance_status",
            "final_quality_balance_status",
            "disposition_model_basis",
        ]
    ].copy()
    material["expected_scrap_units"] = material["direct_scrap_units"]
    material["expected_rework_failure_units"] = material["rework_failure_units"]
    material["potential_replacement_unit_exposure"] = material["total_expected_loss_units"]
    material["material_loss_review_required_flag"] = material["potential_replacement_unit_exposure"] > 0.5
    material["note_no_mrp_change_flag"] = True
    material["confirmation_status"] = CONFIRMATION_STATUS
    material["advisory_only_flag"] = True
    return material


def _build_manager_review_queue(
    impact: pd.DataFrame,
    adjusted: pd.DataFrame,
    bottleneck: pd.DataFrame,
    material: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    item = 1
    risky_operations = impact[
        impact["quality_impact_level"].isin(["HIGH", "CRITICAL"])
        | impact["processing_time_trend"].eq("WORSENING")
        | (pd.to_numeric(impact["expected_scrap_units"], errors="coerce").fillna(0) > 0.5)
        | (pd.to_numeric(impact["expected_rework_units"], errors="coerce").fillna(0) > 1.0)
        | (pd.to_numeric(impact["total_expected_loss_units"], errors="coerce").fillna(0) > 1.0)
        | (pd.to_numeric(impact["rework_failure_units"], errors="coerce").fillna(0) > 0.25)
        | (pd.to_numeric(impact["other_defect_disposition_units"], errors="coerce").fillna(0) > 0.5)
        | impact["defect_disposition_balance_status"].astype(str).ne("BALANCED")
        | impact["final_quality_balance_status"].astype(str).ne("BALANCED")
    ]
    for _, row in risky_operations.iterrows():
        rows.append(_review_row(item, row["planning_run_id"], row["period_start"], row["period_end"], row["workstation_id"], row["workstation_name"], row["operation_id"], _operation_issue_type(row), _severity(row["quality_impact_level"]), row["quality_impact_reason"], "REVIEW_QUALITY_REWORK_AND_PROCESSING_TIME"))
        item += 1
    for _, row in adjusted[adjusted["quality_capacity_review_required_flag"]].iterrows():
        rows.append(_review_row(item, row["planning_run_id"], row["period_start"], row["period_end"], row["workstation_id"], row["workstation_name"], "", "QUALITY_ADJUSTED_CAPACITY_RISK", _severity(row["quality_capacity_impact_level"]), f"Quality-adjusted utilization is {row['quality_adjusted_utilization_pct']:.2f}% with delta {row['utilization_delta_pct']:.2f} percentage points.", "REVIEW_WORKSTATION_CAPACITY_AND_QUALITY_DRIVERS"))
        item += 1
    for _, row in bottleneck[bottleneck["bottleneck_risk_after_quality"].isin(["HIGH", "CRITICAL"])].iterrows():
        rows.append(_review_row(item, row["planning_run_id"], "", "", row["workstation_id"], row["workstation_name"], "", "QUALITY_WORSENED_BOTTLENECK_RISK", _severity(row["bottleneck_risk_after_quality"]), row["bottleneck_impact_reason"], "REVIEW_BOTTLENECK_QUALITY_IMPACT"))
        item += 1
    material_risky = material[material["material_loss_review_required_flag"]]
    for _, row in material_risky.iterrows():
        rows.append(_review_row(item, row["planning_run_id"], row["period_start"], row["period_end"], row["workstation_id"], "", row["operation_id"], "HIGH_EXPECTED_LOSS_UNITS", "MEDIUM", f"Potential replacement unit exposure is {row['potential_replacement_unit_exposure']:.2f}; MRP is not changed by this advisory output.", "REVIEW_SCRAP_AND_REWORK_FAILURE_EXPOSURE"))
        item += 1
    return pd.DataFrame(
        rows,
        columns=[
            "review_item_id",
            "planning_run_id",
            "period_start",
            "period_end",
            "workstation_id",
            "workstation_name",
            "operation_id",
            "issue_type",
            "issue_severity",
            "issue_description",
            "recommended_review_action",
            "auto_action_allowed",
            "advisory_only_flag",
        ],
    )


def _processing_adjustment_factor(row: pd.Series) -> float:
    variance = float(row.get("avg_processing_time_variance_pct", 0) or 0)
    trend = str(row.get("processing_time_trend", "INSUFFICIENT_DATA"))
    if trend == "WORSENING":
        return min(max(variance, 0.05), 0.20)
    if trend == "IMPROVING":
        return -min(max(abs(variance), 0.02), 0.05)
    return 0.0


def _rate_source(row: pd.Series, rule_column: str, trend_column: str) -> str:
    if float(row.get(rule_column, 0) or 0) > 0:
        return "QUALITY_RULE"
    if float(row.get(trend_column, 0) or 0) > 0:
        return "QUALITY_TREND_FALLBACK"
    return "SAFE_DEFAULT_ZERO"


def _defect_share(raw_rate: pd.Series, defect_rate: pd.Series) -> pd.Series:
    raw = pd.to_numeric(raw_rate, errors="coerce").fillna(0).clip(lower=0)
    defect = pd.to_numeric(defect_rate, errors="coerce").fillna(0).clip(lower=0)
    share = raw.copy()
    per_unit_mask = (defect > 0) & (raw <= defect)
    share.loc[per_unit_mask] = raw.loc[per_unit_mask] / defect.loc[per_unit_mask]
    return share.clip(lower=0, upper=1)


def _disposition_rate_status(row: pd.Series) -> str:
    total = float(row.get("disposition_rate_total", 0) or 0)
    other = float(row.get("other_disposition_share_used", 0) or 0)
    safe_default = any(str(row.get(column, "")) == "SAFE_DEFAULT_ZERO" for column in ["defect_rate_source", "rework_rate_source", "scrap_rate_source"])
    if abs(1 - total) <= BALANCE_TOLERANCE and other <= 0.50 and not safe_default:
        return "BALANCED"
    return "REVIEW_REQUIRED"


def _quality_impact_level(row: pd.Series) -> str:
    original_hours = row["original_total_required_hours"] if "original_total_required_hours" in row else row["total_required_hours"]
    delta_hours = row["quality_adjusted_required_hours"] - original_hours
    defect_rate = row["defect_rate_used"]
    scrap = row["expected_scrap_units"]
    if delta_hours > 8 or scrap > 2 or defect_rate >= 0.10:
        return "CRITICAL"
    if delta_hours > 2 or scrap > 0.75 or defect_rate >= 0.06 or row["processing_time_trend"] == "WORSENING":
        return "HIGH"
    if delta_hours > 0 or defect_rate > 0:
        return "MEDIUM"
    return "LOW"


def _quality_impact_reason(row: pd.Series) -> str:
    return (
        f"defect_rate={row['defect_rate_used']:.4f}; rework_hours={row['extra_rework_time_hours']:.2f}; "
        f"processing_trend={row['processing_time_trend']}; adjusted_hours={row['quality_adjusted_required_hours']:.2f}"
    )


def _capacity_status(row: pd.Series) -> str:
    required = row["quality_adjusted_required_hours"]
    available = row["available_hours"]
    util = row["quality_adjusted_utilization_pct"]
    if required == 0:
        return "NO_LOAD"
    if available <= 0:
        return "NO_CAPACITY_RECORD"
    if util > 100:
        return "OVERLOADED"
    if util > 85:
        return "NEAR_CAPACITY"
    return "FEASIBLE"


def _capacity_impact_level(row: pd.Series) -> str:
    util = row["quality_adjusted_utilization_pct"]
    delta = row["utilization_delta_pct"]
    if util > 150 or delta > 25:
        return "CRITICAL"
    if util > 100 or delta > 10:
        return "HIGH"
    if util > 85 or delta > 2:
        return "MEDIUM"
    return "LOW"


def _bottleneck_after_quality(row: pd.Series) -> str:
    return _max_level(pd.Series([row["original_bottleneck_visibility_level"], row["quality_impact_level"]]))


def _rank_pressure_change(row: pd.Series) -> str:
    if row["quality_impact_level"] in {"HIGH", "CRITICAL"} and row["original_bottleneck_visibility_level"] in {"HIGH", "CRITICAL"}:
        return "QUALITY_PRESSURE_REINFORCES_EXISTING_BOTTLENECK_CANDIDATE"
    if row["quality_impact_level"] in {"HIGH", "CRITICAL"}:
        return "QUALITY_PRESSURE_INCREASES_REVIEW_PRIORITY"
    return "NO_MATERIAL_RANK_PRESSURE_CHANGE"


def _bottleneck_impact_reason(row: pd.Series) -> str:
    return (
        f"Original bottleneck level={row['original_bottleneck_visibility_level']}; quality impact={row['quality_impact_level']}; "
        f"max adjusted utilization={row['quality_adjusted_utilization_pct']:.2f}%; extra rework hours={row['quality_extra_rework_hours']:.2f}."
    )


def _operation_issue_type(row: pd.Series) -> str:
    if str(row.get("defect_disposition_balance_status", "")) != "BALANCED":
        return "DEFECT_DISPOSITION_REVIEW"
    if str(row.get("final_quality_balance_status", "")) != "BALANCED":
        return "FINAL_QUALITY_BALANCE_REVIEW"
    if row.get("total_expected_loss_units", 0) > 1.0:
        return "HIGH_EXPECTED_LOSS_UNITS"
    if row.get("rework_failure_units", 0) > 0.25:
        return "HIGH_REWORK_FAILURE_UNITS"
    if row.get("other_defect_disposition_units", 0) > 0.5:
        return "LARGE_OTHER_DEFECT_DISPOSITION"
    if row["processing_time_trend"] == "WORSENING":
        return "PROCESSING_TIME_QUALITY_CAPACITY_IMPACT"
    if row["expected_scrap_units"] > 0.5:
        return "SCRAP_EXPOSURE_REVIEW"
    if row["expected_rework_units"] > 1.0:
        return "REWORK_LOAD_REVIEW"
    return "QUALITY_IMPACT_REVIEW"


def _severity(level: str) -> str:
    return level if level in VALID_LEVELS else "MEDIUM"


def _review_row(item: int, planning_run_id: str, period_start: str, period_end: str, workstation_id: str, workstation_name: str, operation_id: str, issue_type: str, severity: str, description: str, action: str) -> dict:
    return {
        "review_item_id": f"QAC-REV-{item:04d}",
        "planning_run_id": planning_run_id,
        "period_start": period_start,
        "period_end": period_end,
        "workstation_id": workstation_id,
        "workstation_name": workstation_name,
        "operation_id": operation_id,
        "issue_type": issue_type,
        "issue_severity": severity,
        "issue_description": description,
        "recommended_review_action": action,
        "auto_action_allowed": False,
        "advisory_only_flag": True,
    }


def _validate_outputs(
    impact: pd.DataFrame,
    adjusted: pd.DataFrame,
    bottleneck: pd.DataFrame,
    material: pd.DataFrame,
    review: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    checks: list[dict],
) -> None:
    required = {
        "impact": {
            "planning_run_id", "period_start", "period_end", "finished_sku", "operation_id", "workstation_id",
            "planned_production_qty", "original_total_required_hours", "defect_rate_used", "rework_rate_used",
            "scrap_rate_used", "discount_review_rate_used", "other_disposition_share_used", "defective_units",
            "first_pass_good_units", "reworkable_defect_units", "direct_scrap_units", "discount_review_units",
            "other_defect_disposition_units", "defect_disposition_total_units", "defect_disposition_balance_check",
            "defect_disposition_balance_status", "rework_success_units", "rework_failure_units",
            "final_expected_good_units", "total_expected_loss_units", "final_quality_balance_check",
            "final_quality_balance_status", "disposition_model_basis", "expected_defect_units", "expected_rework_units", "expected_scrap_units",
            "extra_rework_time_hours", "quality_adjusted_required_hours", "quality_impact_level",
            "confirmation_status", "advisory_only_flag",
        },
        "adjusted": {
            "planning_run_id", "period_start", "period_end", "workstation_id", "original_required_hours",
            "quality_extra_rework_hours", "processing_time_adjustment_hours", "quality_adjusted_required_hours",
            "expected_defective_units", "expected_rework_units", "expected_loss_units", "expected_final_good_units",
            "disposition_review_required_count", "quality_balance_review_required_flag",
            "available_hours", "original_utilization_pct", "quality_adjusted_utilization_pct", "utilization_delta_pct",
            "quality_adjusted_capacity_status", "quality_capacity_impact_level", "confirmation_status", "advisory_only_flag",
        },
        "bottleneck": {
            "planning_run_id", "workstation_id", "original_bottleneck_visibility_level", "original_bottleneck_visibility_rank",
            "quality_adjusted_utilization_pct", "utilization_delta_pct", "quality_extra_rework_hours", "quality_impact_level",
            "expected_defective_units", "expected_rework_units", "expected_loss_units", "quality_balance_review_required_flag",
            "bottleneck_risk_after_quality", "disposition_model_basis", "confirmation_status", "advisory_only_flag",
        },
        "material": {
            "planning_run_id", "period_start", "period_end", "finished_sku", "operation_id", "workstation_id",
            "defective_units", "direct_scrap_units", "rework_failure_units", "discount_review_units",
            "other_defect_disposition_units", "total_expected_loss_units", "final_expected_good_units",
            "expected_scrap_units", "expected_rework_failure_units", "potential_replacement_unit_exposure",
            "defect_disposition_balance_status", "final_quality_balance_status", "disposition_model_basis",
            "material_loss_review_required_flag", "note_no_mrp_change_flag", "confirmation_status", "advisory_only_flag",
        },
    }
    invalid = 0
    for name, frame in [("impact", impact), ("adjusted", adjusted), ("bottleneck", bottleneck), ("material", material)]:
        invalid += int(frame.empty)
        invalid += len(required[name].difference(frame.columns))
    numeric_checks = [
        (impact, ["planned_production_qty", "original_total_required_hours", "defect_rate_used", "rework_rate_used", "scrap_rate_used", "discount_review_rate_used", "other_disposition_share_used", "defective_units", "first_pass_good_units", "reworkable_defect_units", "direct_scrap_units", "discount_review_units", "other_defect_disposition_units", "defect_disposition_total_units", "rework_success_units", "rework_failure_units", "final_expected_good_units", "total_expected_loss_units", "expected_defect_units", "expected_rework_units", "expected_scrap_units", "expected_good_units_after_quality", "expected_rework_success_units", "expected_rework_failure_units", "extra_rework_time_hours", "quality_adjusted_required_hours"]),
        (adjusted, ["original_required_hours", "quality_extra_rework_hours", "quality_adjusted_required_hours", "expected_defective_units", "expected_rework_units", "expected_loss_units", "expected_final_good_units", "available_hours", "original_utilization_pct", "quality_adjusted_utilization_pct"]),
        (bottleneck, ["quality_adjusted_utilization_pct", "quality_extra_rework_hours", "expected_defective_units", "expected_rework_units", "expected_loss_units"]),
        (material, ["defective_units", "direct_scrap_units", "rework_failure_units", "discount_review_units", "other_defect_disposition_units", "total_expected_loss_units", "final_expected_good_units", "expected_scrap_units", "expected_rework_failure_units", "potential_replacement_unit_exposure"]),
    ]
    for frame, columns in numeric_checks:
        for column in columns:
            values = pd.to_numeric(frame[column], errors="coerce") if column in frame.columns else pd.Series([None])
            invalid += int(values.isna().sum())
            invalid += int((values < 0).sum())
    if not impact.empty:
        worsening_or_rework = (impact["extra_rework_time_hours"] > 0) | impact["processing_time_trend"].astype(str).eq("WORSENING")
        invalid += int((impact.loc[worsening_or_rework, "quality_adjusted_required_hours"] + 1e-9 < impact.loc[worsening_or_rework, "original_total_required_hours"]).sum())
        invalid += int((impact["defect_disposition_balance_check"].abs() > BALANCE_TOLERANCE).sum())
        invalid += int((impact["final_quality_balance_check"].abs() > BALANCE_TOLERANCE).sum())
        valid_balance_statuses = {"BALANCED", "REVIEW_REQUIRED"}
        invalid += int((~impact["defect_disposition_balance_status"].astype(str).isin(valid_balance_statuses)).sum())
        invalid += int((~impact["final_quality_balance_status"].astype(str).isin(valid_balance_statuses)).sum())
        invalid += int((impact["disposition_model_basis"].astype(str) != DISPOSITION_MODEL_BASIS).sum())
        disposition_share_total = impact["rework_rate_used"] + impact["scrap_rate_used"] + impact["discount_review_rate_used"] + impact["other_disposition_share_used"]
        invalid += int(((impact["defective_units"] > 0) & (disposition_share_total.sub(1).abs() > BALANCE_TOLERANCE)).sum())
    for frame in [impact, adjusted, bottleneck, material]:
        if not frame.empty:
            invalid += int((frame["confirmation_status"].astype(str) != CONFIRMATION_STATUS).sum())
            invalid += int((~_to_bool(frame["advisory_only_flag"])).sum())
    if not review.empty:
        invalid += int(_to_bool(review["auto_action_allowed"]).sum())
        invalid += int((~_to_bool(review["advisory_only_flag"])).sum())
    if not material.empty:
        invalid += int((~_to_bool(material["note_no_mrp_change_flag"])).sum())
        invalid += int((material["potential_replacement_unit_exposure"].sub(material["total_expected_loss_units"]).abs() > BALANCE_TOLERANCE).sum())
        invalid += int((material["disposition_model_basis"].astype(str) != DISPOSITION_MODEL_BASIS).sum())
    for key in ["quality_validation", "flow_validation", "capacity_validation", "queue_validation", "bottleneck_validation"]:
        validation = frames[key]
        if "status" in validation.columns:
            invalid += int((validation["status"].astype(str).str.upper() == "FAIL").sum())
    checks.append(_result("quality_adjusted_capacity_outputs_valid", "Step 6B quality-adjusted capacity outputs valid", "FAIL" if invalid else "PASS", f"Invalid Step 6B values: {invalid}" if invalid else f"Step 6B outputs valid; impact_rows={len(impact)}, adjusted_rows={len(adjusted)}.", invalid))


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked_tokens = [
        "quality_adjusted_mrp",
        "quality_adjusted_bom",
        "quality_adjusted_purchase",
        "detailed_schedule",
        "finite_schedule",
        "shop_floor_schedule",
        "dispatch_schedule",
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
    checks.append(_result("quality_adjusted_no_blocked_outputs", "quality adjusted no blocked outputs", "FAIL" if bad_files else "PASS", f"Blocked MRP/scheduling/simulation/execution outputs found: {bad_files}" if bad_files else "No quality-adjusted MRP, scheduling, simulation, or execution outputs found.", len(bad_files)))


def _max_level(values: pd.Series) -> str:
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    cleaned = [str(value) for value in values if str(value) in order]
    if not cleaned:
        return "LOW"
    return max(cleaned, key=lambda value: order[value])


def _load_csv(path: Path, name: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"quality_adjusted_{name}_exists", f"{name} exists", "FAIL", f"Missing file: {path}", 1))
        return None
    frame = pd.read_csv(path, keep_default_na=False)
    checks.append(_result(f"quality_adjusted_{name}_exists", f"{name} exists", "PASS", f"Loaded {path}", 0))
    if frame.empty:
        checks.append(_result(f"quality_adjusted_{name}_not_empty", f"{name} not empty", "WARNING", f"{name} has no rows.", 1))
    return frame


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


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
    *_, validation = build_quality_adjusted_capacity_outputs()
    status_counts = validation["status"].value_counts().to_dict() if not validation.empty else {}
    print(f"Quality-adjusted capacity validation rows: {len(validation)}")
    print(f"Quality-adjusted capacity validation status counts: {status_counts}")
