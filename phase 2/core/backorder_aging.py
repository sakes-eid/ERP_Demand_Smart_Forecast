"""Backorder aging detail and SKU-level summary for Phase 2 procurement context."""

import pandas as pd

from config import BACKORDER_CONFIG


def build_backorder_aging(
    backorders_df: pd.DataFrame,
    allocation_df: pd.DataFrame | None = None,
    as_of_date: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build backorder detail and SKU summary without treating batches as backorders."""
    as_of = pd.Timestamp(as_of_date).normalize() if as_of_date is not None else pd.Timestamp.today().normalize()
    detail = _prepare_backorders(backorders_df)
    if detail.empty:
        return _empty_detail(), _empty_summary()

    allocation_totals = _allocation_totals(allocation_df)
    detail = detail.merge(allocation_totals, on="backorder_id", how="left")
    detail["allocated_fulfillment_units"] = detail["allocated_fulfillment_units"].fillna(0)
    detail["remaining_backorder_units"] = (
        detail["backorder_units"] - detail[["fulfilled_units", "allocated_fulfillment_units"]].max(axis=1)
    ).clip(lower=0)

    detail["backorder_age_days"] = (as_of - detail["backorder_start_date"]).dt.days.clip(lower=0)
    detail["overdue_days"] = (as_of - detail["original_due_date"]).dt.days.clip(lower=0)
    detail["promise_delay_days"] = (as_of - detail["promised_date"]).dt.days.clip(lower=0)
    detail["oldest_unfulfilled_flag"] = False
    open_mask = detail["remaining_backorder_units"] > 0
    if open_mask.any():
        oldest_idx = detail.loc[open_mask].groupby("sku_id")["backorder_age_days"].idxmax()
        detail.loc[oldest_idx, "oldest_unfulfilled_flag"] = True

    detail["long_backorder_flag"] = detail["backorder_age_days"] > BACKORDER_CONFIG["long_backorder_days"]
    detail["critical_backorder_flag"] = (
        detail["criticality_class"].isin(["VITAL", "CRITICAL"])
        & (detail["remaining_backorder_units"] > 0)
        & (
            (detail["overdue_days"] > 0)
            | (detail["backorder_age_days"] > BACKORDER_CONFIG["critical_backorder_days"])
        )
    )
    detail["stale_backorder_flag"] = (
        (as_of - detail["last_update_date"]).dt.days.fillna(0) > BACKORDER_CONFIG["stale_update_days"]
    ) & (detail["remaining_backorder_units"] > 0)
    detail["backorder_priority_score"] = detail.apply(_priority_score, axis=1)
    detail["backorder_risk_level"] = detail["backorder_priority_score"].apply(_risk_level)
    detail["backorder_action"] = detail.apply(_recommended_action, axis=1)
    detail["backorder_warning_codes"] = detail.apply(_warning_codes, axis=1)

    detail = detail[_detail_columns()]
    summary = _build_summary(detail)
    return detail.reset_index(drop=True), summary.reset_index(drop=True)


def _prepare_backorders(backorders_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize backorder inputs and required date/numeric fields."""
    if backorders_df is None or backorders_df.empty:
        return _empty_detail()
    prepared = backorders_df.copy()
    for column in ["backorder_id", "sku_id", "supplier_id", "backorder_type", "backorder_status"]:
        prepared[column] = prepared[column].astype(str).str.strip()
    for column in ["backorder_start_date", "original_due_date", "promised_date", "last_update_date"]:
        prepared[column] = pd.to_datetime(prepared[column], errors="coerce")
    for column in ["backorder_units", "fulfilled_units", "remaining_backorder_units", "service_level_target"]:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce").fillna(0)
    prepared["backorder_units"] = prepared["backorder_units"].clip(lower=0)
    prepared["fulfilled_units"] = prepared["fulfilled_units"].clip(lower=0)
    prepared["remaining_backorder_units"] = (
        prepared["backorder_units"] - prepared["fulfilled_units"]
    ).clip(lower=0)
    prepared["priority_class"] = prepared.get("priority_class", "C").astype(str).str.upper()
    prepared["criticality_class"] = prepared.get("criticality_class", "STANDARD").astype(str).str.upper()
    prepared["customer_priority"] = prepared.get("customer_priority", "NORMAL").astype(str).str.upper()
    prepared["cancellation_flag"] = _to_bool_series(prepared.get("cancellation_flag", pd.Series(False, index=prepared.index)))
    return prepared


def _allocation_totals(allocation_df: pd.DataFrame | None) -> pd.DataFrame:
    """Aggregate batch allocation traceability by backorder."""
    if allocation_df is None or allocation_df.empty:
        return pd.DataFrame(columns=["backorder_id", "allocated_fulfillment_units"])
    allocations = allocation_df.copy()
    allocations["allocated_quantity"] = pd.to_numeric(allocations["allocated_quantity"], errors="coerce").fillna(0)
    allocations["allocated_quantity"] = allocations["allocated_quantity"].clip(lower=0)
    return (
        allocations.groupby("backorder_id", dropna=False)["allocated_quantity"]
        .sum()
        .reset_index(name="allocated_fulfillment_units")
    )


def _priority_score(row: pd.Series) -> int:
    """Calculate a transparent 0-100 backorder priority score."""
    if str(row["backorder_status"]).upper() in {"FULFILLED", "CANCELLED"} or row["remaining_backorder_units"] <= 0:
        return 0
    score = 0.0
    score += min(float(row["backorder_age_days"]) / 30, 1) * 20
    score += min(float(row["overdue_days"]) / 20, 1) * 20
    score += min(float(row["remaining_backorder_units"]) / BACKORDER_CONFIG["high_backorder_units_threshold"], 1) * 15
    score += {"VITAL": 20, "CRITICAL": 25, "IMPORTANT": 10}.get(str(row["criticality_class"]).upper(), 0)
    score += {"CRITICAL": 15, "HIGH": 10, "NORMAL": 3}.get(str(row["customer_priority"]).upper(), 0)
    score += max(float(row["service_level_target"]) - 0.90, 0) * 80
    if row["stale_backorder_flag"]:
        score += 8
    if row["cancellation_flag"]:
        score += 10
    return int(round(min(score, 100)))


def _risk_level(score: int) -> str:
    if score >= 75:
        return "CRITICAL"
    if score >= 55:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "NONE"


def _recommended_action(row: pd.Series) -> str:
    """Recommend non-executing procurement action for a backorder."""
    if row["remaining_backorder_units"] <= 0 or str(row["backorder_status"]).upper() in {"FULFILLED", "CANCELLED"}:
        return "CLOSE_BACKORDER"
    if row["critical_backorder_flag"]:
        return "EXPEDITE_SUPPLY"
    if row["overdue_days"] > 10 and row["remaining_backorder_units"] >= BACKORDER_CONFIG["high_backorder_units_threshold"]:
        return "SPLIT_DELIVERY"
    if row["stale_backorder_flag"]:
        return "CUSTOMER_COMMUNICATION_REQUIRED"
    if row["long_backorder_flag"]:
        return "USE_BACKUP_SUPPLIER"
    if row["cancellation_flag"]:
        return "REVIEW_CANCELLATION_RISK"
    return "MONITOR"


def _warning_codes(row: pd.Series) -> str:
    warnings = []
    if row["remaining_backorder_units"] <= 0:
        warnings.append("NO_ACTIVE_BACKORDER_REMAINING")
    if row["allocated_fulfillment_units"] > row["backorder_units"]:
        warnings.append("ALLOCATED_UNITS_EXCEED_BACKORDER_UNITS")
    if row["fulfilled_units"] > row["backorder_units"]:
        warnings.append("FULFILLED_UNITS_EXCEED_BACKORDER_UNITS")
    if row["long_backorder_flag"]:
        warnings.append("LONG_BACKORDER")
    if row["critical_backorder_flag"]:
        warnings.append("CRITICAL_BACKORDER")
    if row["stale_backorder_flag"]:
        warnings.append("STALE_BACKORDER_UPDATE")
    return ";".join(warnings) if warnings else "NONE"


def _build_summary(detail: pd.DataFrame) -> pd.DataFrame:
    """Aggregate backorder pressure to SKU level for downstream planning."""
    open_detail = detail[detail["remaining_backorder_units"] > 0].copy()
    if open_detail.empty:
        skus = detail[["sku_id"]].drop_duplicates()
        for column in _summary_columns():
            if column != "sku_id":
                skus[column] = 0 if column.endswith(("count", "units", "days", "score")) else "NONE"
        skus["backorder_pressure_flag"] = False
        skus["recommended_backorder_strategy"] = "MONITOR"
        skus["backorder_warning_codes"] = "NO_ACTIVE_BACKORDERS"
        return skus[_summary_columns()]

    summary = open_detail.groupby("sku_id", dropna=False).agg(
        open_backorder_count=("backorder_id", "nunique"),
        total_backorder_units=("backorder_units", "sum"),
        total_fulfilled_units=("fulfilled_units", "sum"),
        total_remaining_backorder_units=("remaining_backorder_units", "sum"),
        oldest_backorder_age_days=("backorder_age_days", "max"),
        average_backorder_age_days=("backorder_age_days", "mean"),
        max_overdue_days=("overdue_days", "max"),
        critical_backorder_count=("critical_backorder_flag", "sum"),
        long_backorder_count=("long_backorder_flag", "sum"),
        stale_backorder_count=("stale_backorder_flag", "sum"),
        backorder_priority_score=("backorder_priority_score", "max"),
    ).reset_index()
    summary["average_backorder_age_days"] = summary["average_backorder_age_days"].round(2)
    summary["backorder_risk_level"] = summary["backorder_priority_score"].apply(_risk_level)
    summary["backorder_pressure_flag"] = (
        (summary["total_remaining_backorder_units"] > 0)
        & summary["backorder_risk_level"].isin(["CRITICAL", "HIGH", "MEDIUM"])
    )
    summary["recommended_backorder_strategy"] = summary.apply(_summary_strategy, axis=1)
    summary["backorder_warning_codes"] = summary.apply(_summary_warnings, axis=1)

    all_skus = detail[["sku_id"]].drop_duplicates()
    summary = all_skus.merge(summary, on="sku_id", how="left")
    fill_values = {
        "open_backorder_count": 0,
        "total_backorder_units": 0,
        "total_fulfilled_units": 0,
        "total_remaining_backorder_units": 0,
        "oldest_backorder_age_days": 0,
        "average_backorder_age_days": 0,
        "max_overdue_days": 0,
        "critical_backorder_count": 0,
        "long_backorder_count": 0,
        "stale_backorder_count": 0,
        "backorder_priority_score": 0,
        "backorder_risk_level": "NONE",
        "backorder_pressure_flag": False,
        "recommended_backorder_strategy": "MONITOR",
        "backorder_warning_codes": "NO_ACTIVE_BACKORDERS",
    }
    for column, default in fill_values.items():
        if column in summary.columns:
            missing = summary[column].isna()
            if missing.any():
                summary.loc[missing, column] = default
    return summary[_summary_columns()]


def _summary_strategy(row: pd.Series) -> str:
    if row["critical_backorder_count"] > 0:
        return "EXPEDITE_SUPPLY"
    if row["max_overdue_days"] > 10:
        return "SPLIT_DELIVERY"
    if row["long_backorder_count"] > 0:
        return "USE_BACKUP_SUPPLIER"
    if row["stale_backorder_count"] > 0:
        return "CUSTOMER_COMMUNICATION_REQUIRED"
    return "MONITOR"


def _summary_warnings(row: pd.Series) -> str:
    warnings = []
    if row["critical_backorder_count"] > 0:
        warnings.append("CRITICAL_BACKORDER")
    if row["long_backorder_count"] > 0:
        warnings.append("LONG_BACKORDER")
    if row["stale_backorder_count"] > 0:
        warnings.append("STALE_BACKORDER_UPDATE")
    if row["total_remaining_backorder_units"] <= 0:
        warnings.append("NO_ACTIVE_BACKORDERS")
    return ";".join(warnings) if warnings else "NONE"


def _to_bool_series(series: pd.Series) -> pd.Series:
    normalized = series.fillna(False)
    if normalized.dtype == bool:
        return normalized
    return normalized.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y", "t"})


def _detail_columns() -> list[str]:
    return [
        "backorder_id",
        "sku_id",
        "supplier_id",
        "backorder_type",
        "backorder_start_date",
        "original_due_date",
        "promised_date",
        "backorder_units",
        "fulfilled_units",
        "allocated_fulfillment_units",
        "remaining_backorder_units",
        "backorder_age_days",
        "overdue_days",
        "promise_delay_days",
        "oldest_unfulfilled_flag",
        "long_backorder_flag",
        "critical_backorder_flag",
        "stale_backorder_flag",
        "backorder_priority_score",
        "backorder_risk_level",
        "backorder_action",
        "backorder_warning_codes",
    ]


def _summary_columns() -> list[str]:
    return [
        "sku_id",
        "open_backorder_count",
        "total_backorder_units",
        "total_fulfilled_units",
        "total_remaining_backorder_units",
        "oldest_backorder_age_days",
        "average_backorder_age_days",
        "max_overdue_days",
        "critical_backorder_count",
        "long_backorder_count",
        "stale_backorder_count",
        "backorder_priority_score",
        "backorder_risk_level",
        "backorder_pressure_flag",
        "recommended_backorder_strategy",
        "backorder_warning_codes",
    ]


def _empty_detail() -> pd.DataFrame:
    return pd.DataFrame(columns=_detail_columns())


def _empty_summary() -> pd.DataFrame:
    return pd.DataFrame(columns=_summary_columns())
