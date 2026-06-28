"""Build advisory quality and workstation performance trend outputs."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PHASE4_DIR / "data"
OUTPUT_DIR = PHASE4_DIR / "outputs"

QUALITY_HISTORY_FILE = DATA_DIR / "quality_history.csv"
QUALITY_RULES_FILE = DATA_DIR / "quality_rules.csv"
REWORK_RULES_FILE = DATA_DIR / "rework_rules.csv"
PRODUCT_ROUTINGS_FILE = DATA_DIR / "product_routings.csv"
WORKSTATIONS_FILE = DATA_DIR / "workstations.csv"
FLOW_VALIDATION_FILE = OUTPUT_DIR / "phase4_flow_validation.csv"
CAPACITY_VALIDATION_FILE = OUTPUT_DIR / "phase4_capacity_validation.csv"
QUEUE_VALIDATION_FILE = OUTPUT_DIR / "phase4_queue_validation.csv"
BOTTLENECK_VALIDATION_FILE = OUTPUT_DIR / "phase4_bottleneck_validation.csv"
PRODUCTION_FLOW_FILE = OUTPUT_DIR / "phase4_production_flow_view.csv"

QUALITY_HISTORY_CLEAN_OUTPUT_FILE = OUTPUT_DIR / "phase4_quality_history_clean.csv"
QUALITY_TREND_OPERATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_quality_trend_by_operation.csv"
QUALITY_TREND_WORKSTATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_quality_trend_by_workstation.csv"
PROCESSING_TIME_TREND_OUTPUT_FILE = OUTPUT_DIR / "phase4_processing_time_trend_by_workstation.csv"
WORKSTATION_PERFORMANCE_SUMMARY_OUTPUT_FILE = OUTPUT_DIR / "phase4_workstation_performance_trend_summary.csv"
QUALITY_MANAGER_REVIEW_OUTPUT_FILE = OUTPUT_DIR / "phase4_quality_manager_review_queue.csv"
QUALITY_VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_quality_validation.csv"

CONFIRMATION_STATUS = "PLANNING_HISTORY_ONLY_NOT_SHOP_FLOOR_CONFIRMED"
SOURCE_PHASE = "PHASE4_STEP6A_QUALITY_TRENDS"
VALID_TRENDS = {"IMPROVING", "STABLE", "WORSENING", "INSUFFICIENT_DATA"}
VALID_DATA_SOURCES = {"SYNTHETIC_PLANNING_HISTORY", "PLANNING_ASSUMPTION_HISTORY"}


def build_quality_trend_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build quality history cleanup, trends, review queue, and validation outputs."""
    checks: list[dict] = []
    frames = {
        "quality_history": _load_csv(QUALITY_HISTORY_FILE, "quality_history", checks),
        "quality_rules": _load_csv(QUALITY_RULES_FILE, "quality_rules", checks),
        "rework_rules": _load_csv(REWORK_RULES_FILE, "rework_rules", checks),
        "product_routings": _load_csv(PRODUCT_ROUTINGS_FILE, "product_routings", checks),
        "workstations": _load_csv(WORKSTATIONS_FILE, "workstations", checks),
        "flow_validation": _load_csv(FLOW_VALIDATION_FILE, "flow_validation", checks),
        "capacity_validation": _load_csv(CAPACITY_VALIDATION_FILE, "capacity_validation", checks),
        "queue_validation": _load_csv(QUEUE_VALIDATION_FILE, "queue_validation", checks),
        "bottleneck_validation": _load_csv(BOTTLENECK_VALIDATION_FILE, "bottleneck_validation", checks),
    }
    clean = pd.DataFrame()
    operation_trend = pd.DataFrame()
    workstation_quality = pd.DataFrame()
    processing_trend = pd.DataFrame()
    performance_summary = pd.DataFrame()
    review_queue = pd.DataFrame()
    if all(frame is not None for frame in frames.values()):
        planning_run_id = _planning_run_id()
        clean = _clean_quality_history(frames["quality_history"], frames["product_routings"], frames["workstations"], planning_run_id)
        operation_trend = _build_operation_trends(clean)
        workstation_quality = _build_workstation_quality_trends(clean)
        processing_trend = _build_processing_time_trends(clean)
        performance_summary = _build_performance_summary(workstation_quality, processing_trend)
        review_queue = _build_manager_review_queue(operation_trend, processing_trend, performance_summary)
        _validate_quality_outputs(clean, operation_trend, workstation_quality, processing_trend, performance_summary, review_queue, frames, checks)
    _check_no_blocked_outputs(checks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    clean.to_csv(QUALITY_HISTORY_CLEAN_OUTPUT_FILE, index=False)
    operation_trend.to_csv(QUALITY_TREND_OPERATION_OUTPUT_FILE, index=False)
    workstation_quality.to_csv(QUALITY_TREND_WORKSTATION_OUTPUT_FILE, index=False)
    processing_trend.to_csv(PROCESSING_TIME_TREND_OUTPUT_FILE, index=False)
    performance_summary.to_csv(WORKSTATION_PERFORMANCE_SUMMARY_OUTPUT_FILE, index=False)
    review_queue.to_csv(QUALITY_MANAGER_REVIEW_OUTPUT_FILE, index=False)
    validation = pd.DataFrame(checks, columns=["check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"])
    validation.to_csv(QUALITY_VALIDATION_OUTPUT_FILE, index=False)
    return clean, operation_trend, workstation_quality, processing_trend, performance_summary, review_queue, validation


def _clean_quality_history(history: pd.DataFrame, routings: pd.DataFrame, workstations: pd.DataFrame, planning_run_id: str) -> pd.DataFrame:
    frame = history.copy()
    route_ref = routings[["operation_id", "operation_name", "finished_product_name"]].drop_duplicates("operation_id")
    ws_ref = workstations[["workstation_id", "workstation_name"]].drop_duplicates("workstation_id")
    frame = frame.merge(route_ref, on="operation_id", how="left", suffixes=("", "_routing"))
    frame = frame.merge(ws_ref, on="workstation_id", how="left")
    frame["planning_run_id"] = planning_run_id
    for column in ["units_processed", "defect_count", "rework_count", "scrap_count", "avg_processing_time_minutes", "standard_processing_time_minutes"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    frame["defect_rate"] = _safe_divide(frame["defect_count"], frame["units_processed"])
    frame["rework_rate"] = _safe_divide(frame["rework_count"], frame["units_processed"])
    frame["scrap_rate"] = _safe_divide(frame["scrap_count"], frame["units_processed"])
    frame["processing_time_variance_pct"] = _safe_divide(frame["avg_processing_time_minutes"], frame["standard_processing_time_minutes"]) - 1
    frame["data_source_type"] = frame["data_source_type"].fillna("SYNTHETIC_PLANNING_HISTORY")
    frame["advisory_only_flag"] = True
    return frame[
        [
            "planning_run_id",
            "period_start",
            "period_end",
            "finished_sku",
            "finished_product_name",
            "operation_id",
            "operation_name",
            "workstation_id",
            "workstation_name",
            "units_processed",
            "defect_count",
            "rework_count",
            "scrap_count",
            "avg_processing_time_minutes",
            "standard_processing_time_minutes",
            "defect_rate",
            "rework_rate",
            "scrap_rate",
            "processing_time_variance_pct",
            "data_source_type",
            "advisory_only_flag",
        ]
    ].copy()


def _build_operation_trends(clean: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in clean.groupby(["planning_run_id", "finished_sku", "operation_id", "operation_name", "workstation_id", "workstation_name"], dropna=False):
        rows.append(_operation_trend_row(keys, group.sort_values("period_start")))
    return pd.DataFrame(rows)


def _operation_trend_row(keys: tuple, group: pd.DataFrame) -> dict:
    defect_trend = _trend_for_series(group["defect_rate"], lower_is_better=True, threshold=0.01)
    rework_trend = _trend_for_series(group["rework_rate"], lower_is_better=True, threshold=0.008)
    scrap_trend = _trend_for_series(group["scrap_rate"], lower_is_better=True, threshold=0.004)
    overall = _worst_trend([defect_trend, rework_trend, scrap_trend])
    return {
        "planning_run_id": keys[0],
        "finished_sku": keys[1],
        "operation_id": keys[2],
        "operation_name": keys[3],
        "workstation_id": keys[4],
        "workstation_name": keys[5],
        "periods_observed": group["period_start"].nunique(),
        "total_units_processed": group["units_processed"].sum(),
        "avg_defect_rate": group["defect_rate"].mean(),
        "avg_rework_rate": group["rework_rate"].mean(),
        "avg_scrap_rate": group["scrap_rate"].mean(),
        "defect_rate_trend": defect_trend,
        "rework_rate_trend": rework_trend,
        "scrap_rate_trend": scrap_trend,
        "quality_trend_overall": overall,
        "trend_reason": _quality_reason(defect_trend, rework_trend, scrap_trend),
        "data_source_type": _source_type(group),
        "advisory_only_flag": True,
    }


def _build_workstation_quality_trends(clean: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in clean.groupby(["planning_run_id", "workstation_id", "workstation_name"], dropna=False):
        defect_trend = _trend_for_series(group.groupby("period_start")["defect_rate"].mean(), lower_is_better=True, threshold=0.008)
        rework_trend = _trend_for_series(group.groupby("period_start")["rework_rate"].mean(), lower_is_better=True, threshold=0.006)
        scrap_trend = _trend_for_series(group.groupby("period_start")["scrap_rate"].mean(), lower_is_better=True, threshold=0.003)
        overall = _worst_trend([defect_trend, rework_trend, scrap_trend])
        rows.append(
            {
                "planning_run_id": keys[0],
                "workstation_id": keys[1],
                "workstation_name": keys[2],
                "periods_observed": group["period_start"].nunique(),
                "operation_count": group["operation_id"].nunique(),
                "total_units_processed": group["units_processed"].sum(),
                "avg_defect_rate": group["defect_rate"].mean(),
                "avg_rework_rate": group["rework_rate"].mean(),
                "avg_scrap_rate": group["scrap_rate"].mean(),
                "defect_rate_trend": defect_trend,
                "rework_rate_trend": rework_trend,
                "scrap_rate_trend": scrap_trend,
                "quality_trend_overall": overall,
                "trend_reason": _quality_reason(defect_trend, rework_trend, scrap_trend),
                "data_source_type": _source_type(group),
                "advisory_only_flag": True,
            }
        )
    return pd.DataFrame(rows)


def _build_processing_time_trends(clean: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in clean.groupby(["planning_run_id", "workstation_id", "workstation_name"], dropna=False):
        by_period = group.groupby("period_start", as_index=False).agg(
            avg_processing_time_minutes=("avg_processing_time_minutes", "mean"),
            avg_standard_processing_time_minutes=("standard_processing_time_minutes", "mean"),
            avg_processing_time_variance_pct=("processing_time_variance_pct", "mean"),
        )
        processing_trend = _trend_for_series(by_period["avg_processing_time_variance_pct"], lower_is_better=True, threshold=0.03)
        speed_trend = processing_trend
        capacity_risk_trend = "WORSENING" if processing_trend == "WORSENING" else ("IMPROVING" if processing_trend == "IMPROVING" else processing_trend)
        rows.append(
            {
                "planning_run_id": keys[0],
                "workstation_id": keys[1],
                "workstation_name": keys[2],
                "periods_observed": group["period_start"].nunique(),
                "avg_processing_time_minutes": group["avg_processing_time_minutes"].mean(),
                "avg_standard_processing_time_minutes": group["standard_processing_time_minutes"].mean(),
                "avg_processing_time_variance_pct": group["processing_time_variance_pct"].mean(),
                "processing_time_trend": processing_trend,
                "speed_trend": speed_trend,
                "capacity_risk_trend": capacity_risk_trend,
                "trend_reason": _processing_reason(processing_trend),
                "data_source_type": _source_type(group),
                "advisory_only_flag": True,
            }
        )
    return pd.DataFrame(rows)


def _build_performance_summary(workstation_quality: pd.DataFrame, processing: pd.DataFrame) -> pd.DataFrame:
    summary = workstation_quality[
        ["planning_run_id", "workstation_id", "workstation_name", "quality_trend_overall"]
    ].merge(
        processing[["planning_run_id", "workstation_id", "processing_time_trend", "speed_trend", "capacity_risk_trend"]],
        on=["planning_run_id", "workstation_id"],
        how="left",
    )
    summary["combined_workstation_performance_trend"] = summary.apply(
        lambda row: _worst_trend([row["quality_trend_overall"], row["processing_time_trend"], row["capacity_risk_trend"]]),
        axis=1,
    )
    summary["performance_risk_level"] = summary["combined_workstation_performance_trend"].map(
        {"WORSENING": "HIGH", "STABLE": "MEDIUM", "IMPROVING": "LOW", "INSUFFICIENT_DATA": "MEDIUM"}
    )
    summary["recommended_review_focus"] = summary.apply(_review_focus, axis=1)
    summary["confirmation_status"] = CONFIRMATION_STATUS
    summary["source_phase"] = SOURCE_PHASE
    summary["advisory_only_flag"] = True
    return summary[
        [
            "planning_run_id",
            "workstation_id",
            "workstation_name",
            "quality_trend_overall",
            "processing_time_trend",
            "speed_trend",
            "capacity_risk_trend",
            "combined_workstation_performance_trend",
            "performance_risk_level",
            "recommended_review_focus",
            "confirmation_status",
            "source_phase",
            "advisory_only_flag",
        ]
    ].copy()


def _build_manager_review_queue(operation_trend: pd.DataFrame, processing: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    item = 1
    for _, row in operation_trend[operation_trend["quality_trend_overall"].eq("WORSENING")].iterrows():
        rows.append(
            _review_row(
                item,
                row["planning_run_id"],
                row["workstation_id"],
                row["workstation_name"],
                row["operation_id"],
                "QUALITY_TREND_WORSENING",
                "HIGH",
                row["trend_reason"],
                "REVIEW_DEFECT_REWORK_SCRAP_TRENDS",
            )
        )
        item += 1
    for _, row in processing[processing["processing_time_trend"].eq("WORSENING")].iterrows():
        rows.append(
            _review_row(
                item,
                row["planning_run_id"],
                row["workstation_id"],
                row["workstation_name"],
                "",
                "PROCESSING_TIME_WORSENING",
                "HIGH",
                row["trend_reason"],
                "REVIEW_WORKSTATION_METHOD_AND_STANDARD_TIME",
            )
        )
        item += 1
    for _, row in summary[summary["capacity_risk_trend"].eq("WORSENING")].iterrows():
        rows.append(
            _review_row(
                item,
                row["planning_run_id"],
                row["workstation_id"],
                row["workstation_name"],
                "",
                "CAPACITY_RISK_TREND_WORSENING",
                "HIGH",
                f"Capacity risk trend is worsening for {row['workstation_name']}.",
                "REVIEW_CAPACITY_RISK_AND_QUALITY_DRIVERS",
            )
        )
        item += 1
    return pd.DataFrame(
        rows,
        columns=[
            "planning_run_id",
            "review_item_id",
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


def _review_row(item: int, planning_run_id: str, workstation_id: str, workstation_name: str, operation_id: str, issue_type: str, severity: str, description: str, action: str) -> dict:
    return {
        "planning_run_id": planning_run_id,
        "review_item_id": f"QLT-REV-{item:04d}",
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


def _trend_for_series(values: pd.Series, lower_is_better: bool, threshold: float) -> str:
    series = pd.to_numeric(values, errors="coerce").dropna().reset_index(drop=True)
    if len(series) < 3:
        return "INSUFFICIENT_DATA"
    midpoint = len(series) // 2
    early = series.iloc[:midpoint].mean()
    recent = series.iloc[midpoint:].mean()
    delta = recent - early
    if abs(delta) <= threshold:
        return "STABLE"
    if lower_is_better:
        return "WORSENING" if delta > 0 else "IMPROVING"
    return "IMPROVING" if delta > 0 else "WORSENING"


def _worst_trend(trends: list[str]) -> str:
    if "WORSENING" in trends:
        return "WORSENING"
    if "STABLE" in trends:
        return "STABLE"
    if "IMPROVING" in trends:
        return "IMPROVING"
    return "INSUFFICIENT_DATA"


def _quality_reason(defect_trend: str, rework_trend: str, scrap_trend: str) -> str:
    return f"defect_rate_trend={defect_trend}; rework_rate_trend={rework_trend}; scrap_rate_trend={scrap_trend}"


def _processing_reason(processing_trend: str) -> str:
    if processing_trend == "WORSENING":
        return "Average processing time variance increased in recent planning-history periods."
    if processing_trend == "IMPROVING":
        return "Average processing time variance decreased in recent planning-history periods."
    if processing_trend == "STABLE":
        return "Average processing time variance stayed within the stability threshold."
    return "Insufficient planning-history periods for processing-time trend detection."


def _review_focus(row: pd.Series) -> str:
    if row["quality_trend_overall"] == "WORSENING" and row["processing_time_trend"] == "WORSENING":
        return "REVIEW_QUALITY_AND_SPEED_DRIVERS"
    if row["quality_trend_overall"] == "WORSENING":
        return "REVIEW_DEFECT_REWORK_SCRAP_TRENDS"
    if row["processing_time_trend"] == "WORSENING":
        return "REVIEW_WORKSTATION_METHOD_AND_STANDARD_TIME"
    return "MONITOR_PLANNING_HISTORY"


def _validate_quality_outputs(
    clean: pd.DataFrame,
    operation_trend: pd.DataFrame,
    workstation_quality: pd.DataFrame,
    processing: pd.DataFrame,
    summary: pd.DataFrame,
    review: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    checks: list[dict],
) -> None:
    required_clean = {"planning_run_id", "period_start", "operation_id", "workstation_id", "units_processed", "defect_rate", "rework_rate", "scrap_rate", "processing_time_variance_pct", "data_source_type", "advisory_only_flag"}
    required_operation = {"planning_run_id", "finished_sku", "operation_id", "operation_name", "workstation_id", "workstation_name", "periods_observed", "avg_defect_rate", "avg_rework_rate", "avg_scrap_rate", "defect_rate_trend", "rework_rate_trend", "scrap_rate_trend", "quality_trend_overall", "data_source_type", "advisory_only_flag"}
    required_processing = {"planning_run_id", "workstation_id", "workstation_name", "periods_observed", "avg_processing_time_minutes", "avg_standard_processing_time_minutes", "avg_processing_time_variance_pct", "processing_time_trend", "speed_trend", "capacity_risk_trend", "data_source_type", "advisory_only_flag"}
    required_summary = {"planning_run_id", "workstation_id", "workstation_name", "quality_trend_overall", "processing_time_trend", "speed_trend", "capacity_risk_trend", "combined_workstation_performance_trend", "performance_risk_level", "confirmation_status", "advisory_only_flag"}
    invalid = int(clean.empty) + int(operation_trend.empty) + int(workstation_quality.empty) + int(processing.empty) + int(summary.empty)
    for required, frame in [(required_clean, clean), (required_operation, operation_trend), (required_processing, processing), (required_summary, summary)]:
        invalid += len(required.difference(frame.columns))
    if not clean.empty:
        for column in ["defect_rate", "rework_rate", "scrap_rate", "processing_time_variance_pct"]:
            values = pd.to_numeric(clean[column], errors="coerce")
            invalid += int(values.isna().sum())
            if column != "processing_time_variance_pct":
                invalid += int((values < 0).sum())
        invalid += int((~clean["data_source_type"].astype(str).isin(VALID_DATA_SOURCES)).sum())
        invalid += int((~_to_bool(clean["advisory_only_flag"])).sum())
    for frame, columns in [
        (operation_trend, ["defect_rate_trend", "rework_rate_trend", "scrap_rate_trend", "quality_trend_overall"]),
        (processing, ["processing_time_trend", "speed_trend", "capacity_risk_trend"]),
        (summary, ["quality_trend_overall", "processing_time_trend", "speed_trend", "capacity_risk_trend", "combined_workstation_performance_trend"]),
    ]:
        for column in columns:
            invalid += int((~frame[column].astype(str).isin(VALID_TRENDS)).sum()) if column in frame.columns else 1
    if not summary.empty:
        invalid += int((summary["confirmation_status"].astype(str) != CONFIRMATION_STATUS).sum())
        invalid += int((~_to_bool(summary["advisory_only_flag"])).sum())
    if not review.empty:
        invalid += int(_to_bool(review["auto_action_allowed"]).sum())
        invalid += int((~_to_bool(review["advisory_only_flag"])).sum())
    for key in ["flow_validation", "capacity_validation", "queue_validation", "bottleneck_validation"]:
        validation = frames[key]
        if "status" in validation.columns:
            invalid += int((validation["status"].astype(str).str.upper() == "FAIL").sum())
    checks.append(_result("quality_step6a_outputs_valid", "Step 6A quality trend outputs valid", "FAIL" if invalid else "PASS", f"Step 6A missing/invalid values: {invalid}" if invalid else f"Quality trend outputs valid; history_rows={len(clean)}, operation_rows={len(operation_trend)}, workstation_rows={len(workstation_quality)}.", invalid))


def _check_no_blocked_outputs(checks: list[dict]) -> None:
    blocked_tokens = [
        "quality_adjusted_capacity",
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
    checks.append(_result("quality_no_blocked_outputs", "quality no blocked execution outputs", "FAIL" if bad_files else "PASS", f"Blocked quality-adjusted capacity/scheduling/simulation/execution outputs found: {bad_files}" if bad_files else "No quality-adjusted capacity, scheduling, simulation, or execution outputs found.", len(bad_files)))


def _planning_run_id() -> str:
    if os.environ.get("INTEGRATED_RUN_ID"):
        return os.environ["INTEGRATED_RUN_ID"]
    if PRODUCTION_FLOW_FILE.exists():
        flow = pd.read_csv(PRODUCTION_FLOW_FILE, usecols=["planning_run_id"])
        values = flow["planning_run_id"].dropna().astype(str).str.strip()
        if not values.empty:
            return values.iloc[0]
    return f"PHASE4-QUALITY-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


def _source_type(group: pd.DataFrame) -> str:
    values = group["data_source_type"].dropna().astype(str).unique().tolist()
    return values[0] if values else "SYNTHETIC_PLANNING_HISTORY"


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = pd.to_numeric(denominator, errors="coerce")
    numerator = pd.to_numeric(numerator, errors="coerce")
    return numerator.div(denominator.where(denominator != 0)).fillna(0)


def _load_csv(path: Path, name: str, checks: list[dict]) -> pd.DataFrame | None:
    if not path.exists():
        checks.append(_result(f"quality_{name}_exists", f"{name} exists", "FAIL", f"Missing file: {path}", 1))
        return None
    frame = pd.read_csv(path, keep_default_na=False)
    checks.append(_result(f"quality_{name}_exists", f"{name} exists", "PASS", f"Loaded {path}", 0))
    if frame.empty:
        checks.append(_result(f"quality_{name}_not_empty", f"{name} not empty", "WARNING", f"{name} has no rows.", 1))
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
    *_, validation = build_quality_trend_outputs()
    status_counts = validation["status"].value_counts().to_dict() if not validation.empty else {}
    print(f"Quality validation rows: {len(validation)}")
    print(f"Quality validation status counts: {status_counts}")
