"""Supplier performance metrics for Phase 2 procurement scoring."""

import pandas as pd


def build_supplier_performance(
    suppliers: pd.DataFrame,
    purchase_orders: pd.DataFrame,
    receipts: pd.DataFrame,
    supplier_trends: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Calculate supplier-level performance from PO and receipt history."""
    history = _build_receipt_history(purchase_orders, receipts)
    if history.empty:
        return _merge_supplier_trend_columns(_build_no_history_performance(suppliers), supplier_trends)

    grouped = history.groupby("supplier_id", dropna=False)
    performance = grouped.agg(
        total_pos=("po_id", "nunique"),
        performance_observation_count=("receipt_id", "count"),
        average_lead_time_days=("actual_lead_time_days", "mean"),
        lead_time_std_days=("actual_lead_time_days", "std"),
        on_time_delivery_rate=("on_time_flag", "mean"),
        late_delivery_rate=("late_flag", "mean"),
        average_delay_days=("delay_days", "mean"),
        partial_delivery_rate=("partial_delivery_flag", "mean"),
        average_yield_rate=("receipt_yield_rate", "mean"),
        defect_rate=("receipt_defect_rate", "mean"),
    ).reset_index()

    performance["lead_time_std_days"] = performance["lead_time_std_days"].fillna(0)
    performance["performance_data_status"] = "HISTORICAL"

    performance = suppliers[["supplier_id", "base_reliability_score"]].merge(
        performance,
        on="supplier_id",
        how="left",
    )
    performance = _fill_no_history_supplier_rows(performance)
    performance["calculated_reliability_score"] = _calculate_reliability_score(performance)
    no_history_mask = performance["performance_data_status"] == "NO_HISTORY"
    performance.loc[no_history_mask, "calculated_reliability_score"] = performance.loc[
        no_history_mask, "base_reliability_score"
    ]
    performance = performance[
        [
            "supplier_id",
            "total_pos",
            "performance_data_status",
            "performance_observation_count",
            "average_lead_time_days",
            "lead_time_std_days",
            "on_time_delivery_rate",
            "late_delivery_rate",
            "average_delay_days",
            "partial_delivery_rate",
            "average_yield_rate",
            "defect_rate",
            "calculated_reliability_score",
        ]
    ]
    return _merge_supplier_trend_columns(performance, supplier_trends)


def _build_receipt_history(purchase_orders: pd.DataFrame, receipts: pd.DataFrame) -> pd.DataFrame:
    """Join purchase orders and receipts into receipt-level history."""
    history = receipts.merge(
        purchase_orders[["po_id", "supplier_id", "sku_id", "order_date", "promised_delivery_date", "ordered_quantity"]],
        on="po_id",
        how="left",
    )
    history = history.dropna(subset=["supplier_id", "order_date", "receipt_date"])
    if history.empty:
        return history

    history["actual_lead_time_days"] = (history["receipt_date"] - history["order_date"]).dt.days
    history["late_flag"] = (history["receipt_date"] > history["promised_delivery_date"]).astype(int)
    history["on_time_flag"] = 1 - history["late_flag"]
    history["receipt_yield_rate"] = history["accepted_quantity"] / history["received_quantity"].replace(0, pd.NA)
    history["receipt_defect_rate"] = history["rejected_quantity"] / history["received_quantity"].replace(0, pd.NA)
    history["receipt_yield_rate"] = history["receipt_yield_rate"].fillna(0)
    history["receipt_defect_rate"] = history["receipt_defect_rate"].fillna(0)
    return history


def _calculate_reliability_score(performance: pd.DataFrame) -> pd.Series:
    """Calculate an interpretable reliability score between 0 and 1."""
    delay_penalty = (performance["average_delay_days"] / 10).clip(0, 1)
    reliability = (
        0.35 * performance["on_time_delivery_rate"]
        + 0.25 * performance["average_yield_rate"]
        + 0.15 * (1 - performance["partial_delivery_rate"].clip(0, 1))
        + 0.15 * (1 - delay_penalty)
        + 0.10 * performance["base_reliability_score"].fillna(0.7)
    )
    return reliability.clip(0, 1)


def _fill_no_history_supplier_rows(performance: pd.DataFrame) -> pd.DataFrame:
    """Fill fallback values for suppliers with no PO/receipt history."""
    filled = performance.copy()
    no_history_mask = filled["total_pos"].isna()
    filled.loc[no_history_mask, "total_pos"] = 0
    filled.loc[no_history_mask, "performance_observation_count"] = 0
    filled.loc[no_history_mask, "performance_data_status"] = "NO_HISTORY"
    filled.loc[no_history_mask, "on_time_delivery_rate"] = filled.loc[no_history_mask, "base_reliability_score"]
    filled.loc[no_history_mask, "late_delivery_rate"] = 1 - filled.loc[no_history_mask, "base_reliability_score"]
    filled.loc[no_history_mask, "partial_delivery_rate"] = 0.10
    filled.loc[no_history_mask, "average_yield_rate"] = 0.95
    filled.loc[no_history_mask, "defect_rate"] = 1 - filled.loc[no_history_mask, "average_yield_rate"]
    filled.loc[~no_history_mask, "performance_data_status"] = filled.loc[
        ~no_history_mask, "performance_data_status"
    ].fillna("HISTORICAL")
    filled["total_pos"] = filled["total_pos"].astype(int)
    filled["performance_observation_count"] = filled["performance_observation_count"].astype(int)
    return filled


def _build_no_history_performance(suppliers: pd.DataFrame) -> pd.DataFrame:
    """Return fallback performance rows for all suppliers when no history exists."""
    performance = suppliers[["supplier_id", "base_reliability_score"]].copy()
    performance["total_pos"] = 0
    performance["performance_data_status"] = "NO_HISTORY"
    performance["performance_observation_count"] = 0
    performance["average_lead_time_days"] = pd.NA
    performance["lead_time_std_days"] = pd.NA
    performance["on_time_delivery_rate"] = performance["base_reliability_score"]
    performance["late_delivery_rate"] = 1 - performance["base_reliability_score"]
    performance["average_delay_days"] = pd.NA
    performance["partial_delivery_rate"] = 0.10
    performance["average_yield_rate"] = 0.95
    performance["defect_rate"] = 0.05
    performance["calculated_reliability_score"] = performance["base_reliability_score"]
    return performance[
        [
            "supplier_id",
            "total_pos",
            "performance_data_status",
            "performance_observation_count",
            "average_lead_time_days",
            "lead_time_std_days",
            "on_time_delivery_rate",
            "late_delivery_rate",
            "average_delay_days",
            "partial_delivery_rate",
            "average_yield_rate",
            "defect_rate",
            "calculated_reliability_score",
        ]
    ]


def _merge_supplier_trend_columns(
    performance: pd.DataFrame,
    supplier_trends: pd.DataFrame | None,
) -> pd.DataFrame:
    """Append supplier trend columns to performance output."""
    if supplier_trends is None or supplier_trends.empty:
        return _add_default_trend_columns(performance)

    trend_columns = [
        "supplier_id",
        "lead_time_trend",
        "delay_trend",
        "on_time_delivery_trend",
        "partial_delivery_trend",
        "yield_trend",
        "defect_rate_trend",
        "cost_trend",
        "cost_per_usable_unit_trend",
        "reliability_trend",
        "improving_trend_count",
        "worsening_trend_count",
        "stable_trend_count",
        "supplier_watchlist_flag",
        "supplier_trend_status",
        "supplier_watchlist_reason",
    ]
    available_columns = [column for column in trend_columns if column in supplier_trends.columns]
    merged = performance.merge(supplier_trends[available_columns], on="supplier_id", how="left")
    return _add_default_trend_columns(merged)


def _add_default_trend_columns(performance: pd.DataFrame) -> pd.DataFrame:
    """Fill trend columns when trend detection is unavailable."""
    filled = performance.copy()
    trend_defaults = {
        "lead_time_trend": "INSUFFICIENT_DATA",
        "delay_trend": "INSUFFICIENT_DATA",
        "on_time_delivery_trend": "INSUFFICIENT_DATA",
        "partial_delivery_trend": "INSUFFICIENT_DATA",
        "yield_trend": "INSUFFICIENT_DATA",
        "defect_rate_trend": "INSUFFICIENT_DATA",
        "cost_trend": "INSUFFICIENT_DATA",
        "cost_per_usable_unit_trend": "INSUFFICIENT_DATA",
        "reliability_trend": "INSUFFICIENT_DATA",
        "improving_trend_count": 0,
        "worsening_trend_count": 0,
        "stable_trend_count": 0,
        "supplier_watchlist_flag": False,
        "supplier_trend_status": "INSUFFICIENT_DATA",
        "supplier_watchlist_reason": "Insufficient recent or baseline data for trend detection.",
    }
    for column, default_value in trend_defaults.items():
        if column not in filled.columns:
            filled[column] = default_value
        else:
            filled[column] = filled[column].fillna(default_value)
    return filled


def _empty_supplier_performance() -> pd.DataFrame:
    """Return an empty supplier performance frame with expected columns."""
    return pd.DataFrame(
        columns=[
            "supplier_id",
            "total_pos",
            "performance_data_status",
            "performance_observation_count",
            "average_lead_time_days",
            "lead_time_std_days",
            "on_time_delivery_rate",
            "late_delivery_rate",
            "average_delay_days",
            "partial_delivery_rate",
            "average_yield_rate",
            "defect_rate",
            "calculated_reliability_score",
        ]
    )
