"""Supplier performance trend detection for Phase 2 procurement."""

import pandas as pd

from config import SUPPLIER_TREND_THRESHOLDS, SUPPLIER_TREND_WINDOWS

TREND_FIELDS = [
    "lead_time_trend",
    "delay_trend",
    "on_time_delivery_trend",
    "partial_delivery_trend",
    "yield_trend",
    "defect_rate_trend",
    "cost_trend",
    "cost_per_usable_unit_trend",
    "reliability_trend",
]

CRITICAL_TREND_FIELDS = [
    "reliability_trend",
    "yield_trend",
    "delay_trend",
    "partial_delivery_trend",
    "cost_per_usable_unit_trend",
]


def build_supplier_trends(
    suppliers: pd.DataFrame,
    purchase_orders: pd.DataFrame,
    receipts: pd.DataFrame,
) -> pd.DataFrame:
    """Compare recent supplier behavior against a prior baseline window."""
    history = _build_trend_history(purchase_orders, receipts)
    if history.empty:
        return _empty_trends_for_suppliers(suppliers)

    latest_receipt_date = history["receipt_date"].max().normalize()
    recent_start = latest_receipt_date - pd.Timedelta(days=SUPPLIER_TREND_WINDOWS["recent_days"] - 1)
    baseline_end = recent_start - pd.Timedelta(days=1)
    baseline_start = baseline_end - pd.Timedelta(days=SUPPLIER_TREND_WINDOWS["baseline_days"] - 1)

    baseline = history[(history["receipt_date"] >= baseline_start) & (history["receipt_date"] <= baseline_end)]
    recent = history[(history["receipt_date"] >= recent_start) & (history["receipt_date"] <= latest_receipt_date)]

    rows = []
    for supplier_id in suppliers["supplier_id"].astype(str):
        baseline_metrics = _period_metrics(baseline[baseline["supplier_id"] == supplier_id])
        recent_metrics = _period_metrics(recent[recent["supplier_id"] == supplier_id])
        row = {
            "supplier_id": supplier_id,
            "baseline_period_start": baseline_start.date().isoformat(),
            "baseline_period_end": baseline_end.date().isoformat(),
            "recent_period_start": recent_start.date().isoformat(),
            "recent_period_end": latest_receipt_date.date().isoformat(),
            "baseline_order_count": baseline_metrics["order_count"],
            "recent_order_count": recent_metrics["order_count"],
        }
        _add_prefixed_metrics(row, "baseline", baseline_metrics)
        _add_prefixed_metrics(row, "recent", recent_metrics)
        row.update(_classify_supplier_trends(row))
        rows.append(row)

    return pd.DataFrame(rows)


def key_trend_columns() -> list[str]:
    """Return the trend columns merged into supplier performance and scoring."""
    return [
        "supplier_id",
        *TREND_FIELDS,
        "improving_trend_count",
        "worsening_trend_count",
        "stable_trend_count",
        "supplier_watchlist_flag",
        "supplier_trend_status",
        "supplier_watchlist_reason",
    ]


def _build_trend_history(purchase_orders: pd.DataFrame, receipts: pd.DataFrame) -> pd.DataFrame:
    """Join purchase orders and receipts into a trend-ready history table."""
    if purchase_orders.empty or receipts.empty:
        return pd.DataFrame()

    po_columns = [
        "po_id",
        "supplier_id",
        "order_date",
        "promised_delivery_date",
        "ordered_quantity",
        "expected_unit_cost",
    ]
    history = receipts.merge(purchase_orders[po_columns], on="po_id", how="left")
    history = history.dropna(subset=["supplier_id", "order_date", "receipt_date"])
    if history.empty:
        return history

    history["supplier_id"] = history["supplier_id"].astype(str)
    history["actual_lead_time_days"] = (history["receipt_date"] - history["order_date"]).dt.days
    history["late_flag"] = (history["receipt_date"] > history["promised_delivery_date"]).astype(int)
    history["on_time_flag"] = 1 - history["late_flag"]
    history["expected_total_cost"] = history["expected_unit_cost"] * history["ordered_quantity"]
    return history


def _period_metrics(period: pd.DataFrame) -> dict[str, float]:
    """Calculate supplier metrics for one time period."""
    if period.empty:
        return _blank_period_metrics()

    received_quantity = period["received_quantity"].sum()
    ordered_quantity = period["ordered_quantity"].sum()
    accepted_quantity = period["accepted_quantity"].sum()
    rejected_quantity = period["rejected_quantity"].sum()
    expected_total_cost = period["expected_total_cost"].sum()

    yield_rate = _safe_divide(accepted_quantity, received_quantity)
    partial_delivery_rate = period["partial_delivery_flag"].mean()
    quality_issue_rate = period["quality_issue_flag"].mean()

    metrics = {
        "order_count": period["po_id"].nunique(),
        "average_lead_time_days": period["actual_lead_time_days"].mean(),
        "lead_time_std_days": period["actual_lead_time_days"].std(),
        "late_delivery_rate": period["late_flag"].mean(),
        "average_delay_days": period["delay_days"].mean(),
        "on_time_delivery_rate": period["on_time_flag"].mean(),
        "partial_delivery_rate": partial_delivery_rate,
        "received_to_ordered_ratio": _safe_divide(received_quantity, ordered_quantity),
        "yield_rate": yield_rate,
        "defect_rate": _safe_divide(rejected_quantity, received_quantity),
        "quality_issue_rate": quality_issue_rate,
        "average_unit_cost": period["expected_unit_cost"].mean(),
        "cost_per_usable_unit": _safe_divide(expected_total_cost, accepted_quantity),
    }
    metrics["lead_time_std_days"] = 0.0 if pd.isna(metrics["lead_time_std_days"]) else metrics["lead_time_std_days"]
    metrics["reliability_score"] = _reliability_score(
        metrics["on_time_delivery_rate"],
        yield_rate,
        partial_delivery_rate,
        quality_issue_rate,
    )
    return metrics


def _blank_period_metrics() -> dict[str, float]:
    """Return blank metrics for a supplier with no orders in a period."""
    return {
        "order_count": 0,
        "average_lead_time_days": pd.NA,
        "lead_time_std_days": pd.NA,
        "late_delivery_rate": pd.NA,
        "average_delay_days": pd.NA,
        "on_time_delivery_rate": pd.NA,
        "partial_delivery_rate": pd.NA,
        "received_to_ordered_ratio": pd.NA,
        "yield_rate": pd.NA,
        "defect_rate": pd.NA,
        "quality_issue_rate": pd.NA,
        "average_unit_cost": pd.NA,
        "cost_per_usable_unit": pd.NA,
        "reliability_score": pd.NA,
    }


def _add_prefixed_metrics(row: dict, prefix: str, metrics: dict[str, float]) -> None:
    """Add period metrics to a trend output row with baseline/recent prefixes."""
    for key, value in metrics.items():
        if key != "order_count":
            row[f"{prefix}_{key}"] = value


def _classify_supplier_trends(row: dict) -> dict[str, object]:
    """Classify individual trends and the overall supplier trend status."""
    has_enough_data = (
        row["recent_order_count"] >= SUPPLIER_TREND_WINDOWS["minimum_recent_orders"]
        and row["baseline_order_count"] >= SUPPLIER_TREND_WINDOWS["minimum_baseline_orders"]
    )
    if not has_enough_data:
        trends = {field: "INSUFFICIENT_DATA" for field in TREND_FIELDS}
        trends.update(_trend_counts_and_status(trends))
        return trends

    trends = {
        "lead_time_trend": _classify_lower_is_better(
            row["baseline_average_lead_time_days"],
            row["recent_average_lead_time_days"],
            SUPPLIER_TREND_THRESHOLDS["lead_time_worsening_pct"],
            SUPPLIER_TREND_THRESHOLDS["lead_time_improving_pct"],
        ),
        "delay_trend": _classify_lower_is_better(
            row["baseline_average_delay_days"],
            row["recent_average_delay_days"],
            SUPPLIER_TREND_THRESHOLDS["delay_worsening_pct"],
            SUPPLIER_TREND_THRESHOLDS["delay_improving_pct"],
        ),
        "on_time_delivery_trend": _classify_higher_is_better(
            row["baseline_on_time_delivery_rate"],
            row["recent_on_time_delivery_rate"],
            SUPPLIER_TREND_THRESHOLDS["on_time_rate_drop_pct"],
            SUPPLIER_TREND_THRESHOLDS["on_time_rate_improve_pct"],
        ),
        "partial_delivery_trend": _classify_lower_is_better(
            row["baseline_partial_delivery_rate"],
            row["recent_partial_delivery_rate"],
            SUPPLIER_TREND_THRESHOLDS["partial_delivery_worsening_pct"],
            SUPPLIER_TREND_THRESHOLDS["partial_delivery_improving_pct"],
        ),
        "yield_trend": _classify_higher_is_better(
            row["baseline_yield_rate"],
            row["recent_yield_rate"],
            SUPPLIER_TREND_THRESHOLDS["yield_drop_pct"],
            SUPPLIER_TREND_THRESHOLDS["yield_improve_pct"],
        ),
        "defect_rate_trend": _classify_lower_is_better(
            row["baseline_defect_rate"],
            row["recent_defect_rate"],
            SUPPLIER_TREND_THRESHOLDS["defect_rate_worsening_pct"],
            SUPPLIER_TREND_THRESHOLDS["defect_rate_improving_pct"],
        ),
        "cost_trend": _classify_lower_is_better(
            row["baseline_average_unit_cost"],
            row["recent_average_unit_cost"],
            SUPPLIER_TREND_THRESHOLDS["cost_worsening_pct"],
            SUPPLIER_TREND_THRESHOLDS["cost_improving_pct"],
        ),
        "cost_per_usable_unit_trend": _classify_lower_is_better(
            row["baseline_cost_per_usable_unit"],
            row["recent_cost_per_usable_unit"],
            SUPPLIER_TREND_THRESHOLDS["cost_worsening_pct"],
            SUPPLIER_TREND_THRESHOLDS["cost_improving_pct"],
        ),
        "reliability_trend": _classify_higher_is_better(
            row["baseline_reliability_score"],
            row["recent_reliability_score"],
            SUPPLIER_TREND_THRESHOLDS["reliability_drop_pct"],
            SUPPLIER_TREND_THRESHOLDS["reliability_improve_pct"],
        ),
    }
    trends.update(_trend_counts_and_status(trends))
    return trends


def _trend_counts_and_status(trends: dict[str, str]) -> dict[str, object]:
    """Count trends and classify overall supplier trend status."""
    improving_count = sum(trends[field] == "IMPROVING" for field in TREND_FIELDS)
    worsening_count = sum(trends[field] == "WORSENING" for field in TREND_FIELDS)
    stable_count = sum(trends[field] == "STABLE" for field in TREND_FIELDS)

    has_insufficient = any(trends[field] == "INSUFFICIENT_DATA" for field in TREND_FIELDS)
    critical_worsening = [field for field in CRITICAL_TREND_FIELDS if trends[field] == "WORSENING"]

    if has_insufficient:
        status = "INSUFFICIENT_DATA"
    elif critical_worsening:
        status = "WATCHLIST"
    elif improving_count >= 5 and worsening_count == 0:
        status = "IMPROVING"
    elif improving_count > 0 and worsening_count > 0:
        status = "MIXED"
    else:
        status = "HEALTHY"

    return {
        "improving_trend_count": improving_count,
        "worsening_trend_count": worsening_count,
        "stable_trend_count": stable_count,
        "supplier_trend_status": status,
        "supplier_watchlist_flag": status == "WATCHLIST",
        "supplier_watchlist_reason": _watchlist_reason(status, critical_worsening),
    }


def _classify_lower_is_better(baseline: float, recent: float, worsening_pct: float, improving_pct: float) -> str:
    """Classify a lower-is-better metric trend."""
    if _missing_comparison_values(baseline, recent):
        return "INSUFFICIENT_DATA"
    change = _relative_change(baseline, recent)
    if change >= worsening_pct:
        return "WORSENING"
    if change <= -improving_pct:
        return "IMPROVING"
    return "STABLE"


def _classify_higher_is_better(baseline: float, recent: float, worsening_pct: float, improving_pct: float) -> str:
    """Classify a higher-is-better metric trend."""
    if _missing_comparison_values(baseline, recent):
        return "INSUFFICIENT_DATA"
    change = _relative_change(baseline, recent)
    if change <= -worsening_pct:
        return "WORSENING"
    if change >= improving_pct:
        return "IMPROVING"
    return "STABLE"


def _relative_change(baseline: float, recent: float) -> float:
    """Calculate relative change with a small denominator guard."""
    denominator = max(abs(float(baseline)), 1e-9)
    return (float(recent) - float(baseline)) / denominator


def _missing_comparison_values(baseline: float, recent: float) -> bool:
    """Return True when a metric cannot be compared safely."""
    return pd.isna(baseline) or pd.isna(recent)


def _safe_divide(numerator: float, denominator: float) -> float:
    """Divide while avoiding zero denominators."""
    if pd.isna(denominator) or denominator == 0:
        return pd.NA
    return numerator / denominator


def _reliability_score(
    on_time_delivery_rate: float,
    yield_rate: float,
    partial_delivery_rate: float,
    quality_issue_rate: float,
) -> float:
    """Calculate a compact period reliability score."""
    if any(pd.isna(value) for value in [on_time_delivery_rate, yield_rate, partial_delivery_rate, quality_issue_rate]):
        return pd.NA
    reliability = (
        0.35 * on_time_delivery_rate
        + 0.30 * yield_rate
        + 0.20 * (1 - partial_delivery_rate)
        + 0.15 * (1 - quality_issue_rate)
    )
    return max(0.0, min(1.0, reliability))


def _watchlist_reason(status: str, critical_worsening: list[str]) -> str:
    """Create a readable reason for the supplier trend status."""
    if status == "INSUFFICIENT_DATA":
        return "Insufficient recent or baseline data for trend detection."
    if status == "IMPROVING":
        return "Supplier performance is improving across most metrics."
    if status != "WATCHLIST":
        return "Supplier performance trend is acceptable for current review."
    if len(critical_worsening) > 1:
        return "Multiple supplier performance metrics are worsening."
    reason_map = {
        "delay_trend": "Delay trend is worsening.",
        "yield_trend": "Yield trend is worsening.",
        "partial_delivery_trend": "Partial delivery trend is worsening.",
        "cost_per_usable_unit_trend": "Cost per usable unit is worsening.",
        "reliability_trend": "Reliability trend is worsening.",
    }
    return reason_map.get(critical_worsening[0], "Supplier performance is worsening.")


def _empty_trends_for_suppliers(suppliers: pd.DataFrame) -> pd.DataFrame:
    """Return insufficient-data trend rows when no receipt history exists."""
    rows = []
    for supplier_id in suppliers["supplier_id"].astype(str):
        trends = {field: "INSUFFICIENT_DATA" for field in TREND_FIELDS}
        trends.update(_trend_counts_and_status(trends))
        rows.append(
            {
                "supplier_id": supplier_id,
                "baseline_period_start": pd.NA,
                "baseline_period_end": pd.NA,
                "recent_period_start": pd.NA,
                "recent_period_end": pd.NA,
                "baseline_order_count": 0,
                "recent_order_count": 0,
                **_blank_prefixed_metrics("baseline"),
                **_blank_prefixed_metrics("recent"),
                **trends,
            }
        )
    return pd.DataFrame(rows)


def _blank_prefixed_metrics(prefix: str) -> dict[str, object]:
    """Create blank baseline/recent metric columns."""
    metrics = _blank_period_metrics()
    return {f"{prefix}_{key}": value for key, value in metrics.items() if key != "order_count"}
