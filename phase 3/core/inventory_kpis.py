"""Essential inventory KPI calculations for Phase 3."""

from __future__ import annotations

import pandas as pd


def build_inventory_kpi_summary(
    inventory: pd.DataFrame,
    batches: pd.DataFrame,
    movements: pd.DataFrame,
    planning_context: pd.DataFrame,
    inventory_status: pd.DataFrame,
    policy_parameters: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build one operational inventory KPI row per SKU."""
    base = planning_context.copy()
    if base.empty or "sku_id" not in base.columns:
        return pd.DataFrame()
    movement_metrics = _movement_metrics(movements)
    expiry_metrics = _expiry_metrics(batches)
    reconciliation = _reconciliation_metrics(inventory, batches)
    result = base.merge(movement_metrics, on="sku_id", how="left")
    result = result.merge(expiry_metrics, on="sku_id", how="left")
    result = result.merge(reconciliation, on="sku_id", how="left")
    result = result.merge(_policy_thresholds(policy_parameters), on="sku_id", how="left")
    if not inventory_status.empty and "sku_id" in inventory_status.columns:
        keep = ["sku_id"] + [c for c in ["main_inventory_status", "fsn_class", "dead_stock_signal", "non_moving_signal", "stockout_signal"] if c in inventory_status.columns]
        result = result.merge(inventory_status[keep].drop_duplicates("sku_id"), on="sku_id", how="left", suffixes=("", "_status"))

    usable = _num(result, "available_inventory").where(_num(result, "available_inventory") > 0, _num(result, "quantity_available"))
    avg_daily_forecast = _num(result, "average_daily_forecast_demand_30d").where(_num(result, "average_daily_forecast_demand_30d") > 0, _num(result, "average_daily_demand"))
    outbound_90d = _num(result, "outbound_units_90d")
    current_inventory = _num(result, "current_inventory")
    batch_available = _num(result, "quantity_available")
    average_inventory_proxy = pd.concat([usable, current_inventory, batch_available], axis=1).where(lambda frame: frame > 0).max(axis=1)
    result["outbound_to_current_inventory_ratio_90d"] = _safe_divide(outbound_90d, average_inventory_proxy)
    result["outbound_to_current_inventory_ratio_90d_method"] = "OUTBOUND_UNITS_90D_DIVIDED_BY_CURRENT_USABLE_INVENTORY_PROXY"
    result["outbound_to_current_inventory_ratio_90d_data_quality"] = result["outbound_to_current_inventory_ratio_90d"].apply(lambda value: "AVAILABLE_PROXY" if pd.notna(value) else "UNAVAILABLE")
    result["inventory_turnover_units_90d"] = result["outbound_to_current_inventory_ratio_90d"]
    result["inventory_turnover_method"] = "PROXY_NOT_FORMAL_TURNOVER"
    result["inventory_turnover_data_quality"] = result["outbound_to_current_inventory_ratio_90d_data_quality"]

    result["days_inventory_on_hand"] = _safe_divide(usable, avg_daily_forecast)
    result["days_inventory_on_hand_status"] = result.apply(_days_inventory_status, axis=1)

    result["unit_fill_rate_proxy"] = pd.NA
    result["unit_fill_rate_method"] = "UNAVAILABLE_NO_IMMEDIATE_FULFILLMENT_RECORDS"
    result["unit_fill_rate_data_quality"] = "UNAVAILABLE"

    result["stockout_rate"] = pd.NA
    result["stockout_rate_method"] = "UNAVAILABLE_NO_HISTORICAL_STOCKOUT_EVENT_SERIES"
    result["stockout_rate_data_quality"] = "UNAVAILABLE"

    excess_units = _excess_units(result, usable)
    result["excess_inventory_units"] = excess_units
    result["excess_inventory_data_quality"] = result["max_stock_threshold_units"].apply(
        lambda value: "AVAILABLE_POLICY_THRESHOLD" if pd.notna(value) and float(value) > 0 else "UNAVAILABLE_POLICY_THRESHOLD"
    )
    dead_stock_units = usable.where(_bool(result.get("dead_stock_signal", pd.Series(False, index=result.index))) | _bool(result.get("non_moving_signal", pd.Series(False, index=result.index))), 0)
    result["excess_inventory_rate"] = _safe_divide(excess_units, usable)
    result["dead_stock_rate"] = _safe_divide(dead_stock_units, usable)
    result["expiry_exposure_rate_30d"] = _safe_divide(_num(result, "expiry_exposure_units_30d"), usable)
    result["inventory_reconciliation_accuracy_rate"] = (1 - _safe_divide(_num(result, "absolute_reconciliation_difference"), _num(result, "reconciliation_basis_units"))).clip(lower=0, upper=1)

    result["fefo_compliance_rate"] = pd.NA
    result["fefo_compliance_method"] = "UNAVAILABLE_NO_EXPIRY_CONTROLLED_ISSUE_TRACE"
    result["fefo_compliance_data_quality"] = "UNAVAILABLE"
    result["inventory_kpi_warning_codes"] = result.apply(_warning_codes, axis=1)
    columns = [
        "sku_id",
        "product_name",
        "category",
        "outbound_to_current_inventory_ratio_90d",
        "outbound_to_current_inventory_ratio_90d_method",
        "outbound_to_current_inventory_ratio_90d_data_quality",
        "inventory_turnover_units_90d",
        "inventory_turnover_method",
        "inventory_turnover_data_quality",
        "days_inventory_on_hand",
        "days_inventory_on_hand_status",
        "unit_fill_rate_proxy",
        "unit_fill_rate_method",
        "unit_fill_rate_data_quality",
        "stockout_rate",
        "stockout_rate_method",
        "stockout_rate_data_quality",
        "max_stock_threshold_units",
        "excess_inventory_units",
        "excess_inventory_rate",
        "excess_inventory_data_quality",
        "dead_stock_rate",
        "expiry_exposure_rate_30d",
        "inventory_reconciliation_accuracy_rate",
        "fefo_compliance_rate",
        "fefo_compliance_method",
        "fefo_compliance_data_quality",
        "inventory_kpi_warning_codes",
    ]
    return _ensure_columns(result, columns)[columns]


def merge_manager_dashboard_kpis(dashboard: pd.DataFrame, inventory_kpis: pd.DataFrame) -> pd.DataFrame:
    """Merge the most manager-relevant inventory KPIs into the dashboard file."""
    if dashboard.empty or inventory_kpis.empty or "sku_id" not in dashboard.columns:
        return dashboard
    fields = [
        "sku_id",
        "outbound_to_current_inventory_ratio_90d",
        "outbound_to_current_inventory_ratio_90d_data_quality",
        "days_inventory_on_hand",
        "days_inventory_on_hand_status",
        "excess_inventory_units",
        "excess_inventory_rate",
        "excess_inventory_data_quality",
        "dead_stock_rate",
        "expiry_exposure_rate_30d",
        "inventory_reconciliation_accuracy_rate",
    ]
    keep = [column for column in fields if column in inventory_kpis.columns]
    return dashboard.merge(inventory_kpis[keep], on="sku_id", how="left")


def _movement_metrics(movements: pd.DataFrame) -> pd.DataFrame:
    if movements.empty or "sku_id" not in movements.columns:
        return pd.DataFrame(columns=["sku_id", "outbound_units_90d"])
    working = movements.copy()
    working["movement_date"] = pd.to_datetime(working.get("movement_date"), errors="coerce")
    latest = working["movement_date"].max()
    if pd.isna(latest):
        return pd.DataFrame({"sku_id": sorted(working["sku_id"].dropna().astype(str).unique()), "outbound_units_90d": 0})
    recent = working[working["movement_date"] >= latest - pd.Timedelta(days=89)].copy()
    qty = pd.to_numeric(recent.get("quantity"), errors="coerce").fillna(0)
    outbound = recent[qty < 0].copy()
    outbound["outbound_units_90d"] = qty[qty < 0].abs()
    return outbound.groupby("sku_id", dropna=False)["outbound_units_90d"].sum().reset_index()


def _expiry_metrics(batches: pd.DataFrame) -> pd.DataFrame:
    if batches.empty or "sku_id" not in batches.columns:
        return pd.DataFrame(columns=["sku_id", "quantity_available", "expiry_exposure_units_30d"])
    working = batches.copy()
    available = pd.to_numeric(working.get("quantity_available"), errors="coerce").fillna(0)
    days = pd.to_numeric(working.get("days_until_expiry"), errors="coerce")
    exposure = available.where(days.notna() & (days >= 0) & (days <= 30), 0)
    working["quantity_available"] = available
    working["expiry_exposure_units_30d"] = exposure
    return working.groupby("sku_id", dropna=False).agg(
        quantity_available=("quantity_available", "sum"),
        expiry_exposure_units_30d=("expiry_exposure_units_30d", "sum"),
    ).reset_index()


def _reconciliation_metrics(inventory: pd.DataFrame, batches: pd.DataFrame) -> pd.DataFrame:
    inv = inventory[["sku_id", "current_inventory"]].copy() if {"sku_id", "current_inventory"}.issubset(inventory.columns) else pd.DataFrame(columns=["sku_id", "current_inventory"])
    if not batches.empty and {"sku_id", "quantity_on_hand"}.issubset(batches.columns):
        batch = batches.copy()
        batch["batch_on_hand_units"] = pd.to_numeric(batch["quantity_on_hand"], errors="coerce").fillna(0)
        batch = batch.groupby("sku_id", dropna=False)["batch_on_hand_units"].sum().reset_index()
    else:
        batch = pd.DataFrame(columns=["sku_id", "batch_on_hand_units"])
    merged = inv.merge(batch, on="sku_id", how="outer").fillna(0)
    merged["absolute_reconciliation_difference"] = (pd.to_numeric(merged["current_inventory"], errors="coerce").fillna(0) - pd.to_numeric(merged["batch_on_hand_units"], errors="coerce").fillna(0)).abs()
    merged["reconciliation_basis_units"] = pd.concat([
        pd.to_numeric(merged["current_inventory"], errors="coerce").fillna(0),
        pd.to_numeric(merged["batch_on_hand_units"], errors="coerce").fillna(0),
    ], axis=1).max(axis=1)
    return merged[["sku_id", "absolute_reconciliation_difference", "reconciliation_basis_units"]]


def _policy_thresholds(policy_parameters: pd.DataFrame | None) -> pd.DataFrame:
    if policy_parameters is None or policy_parameters.empty or "sku_id" not in policy_parameters.columns:
        return pd.DataFrame(columns=["sku_id", "max_stock_threshold_units"])
    working = policy_parameters.copy()
    threshold = pd.Series(pd.NA, index=working.index, dtype="Float64")
    for column in ["max_stock_level", "max_stock_level_units"]:
        if column in working.columns:
            values = pd.to_numeric(working[column], errors="coerce")
            threshold = threshold.where(threshold.notna(), values.where(values > 0))
    working["max_stock_threshold_units"] = threshold
    return working[["sku_id", "max_stock_threshold_units"]].drop_duplicates("sku_id")


def _days_inventory_status(row) -> str:
    demand = _safe_num(row.get("average_daily_forecast_demand_30d")) or _safe_num(row.get("average_daily_demand"))
    days = _safe_num(row.get("days_inventory_on_hand"))
    if demand <= 0:
        return "NO_DEMAND"
    if days < 3:
        return "CRITICAL_LOW"
    if days < 7:
        return "LOW"
    if days <= 45:
        return "BALANCED"
    if days <= 90:
        return "HIGH"
    return "EXCESSIVE"


def _excess_units(df: pd.DataFrame, usable: pd.Series) -> pd.Series:
    max_stock = _num(df, "max_stock_threshold_units")
    return (usable - max_stock).clip(lower=0).where(max_stock.notna() & (max_stock > 0), pd.NA)


def _warning_codes(row) -> str:
    codes = []
    if str(row.get("unit_fill_rate_data_quality", "")).upper() == "UNAVAILABLE":
        codes.append("UNIT_FILL_RATE_UNAVAILABLE")
    if str(row.get("stockout_rate_data_quality", "")).upper() == "UNAVAILABLE":
        codes.append("STOCKOUT_RATE_UNAVAILABLE")
    if str(row.get("fefo_compliance_data_quality", "")).upper() == "UNAVAILABLE":
        codes.append("FEFO_COMPLIANCE_UNAVAILABLE")
    if pd.isna(row.get("days_inventory_on_hand")):
        codes.append("DAYS_INVENTORY_ON_HAND_UNAVAILABLE")
    if str(row.get("excess_inventory_data_quality", "")).upper() == "UNAVAILABLE_POLICY_THRESHOLD":
        codes.append("EXCESS_INVENTORY_UNAVAILABLE_POLICY_THRESHOLD")
    return ";".join(codes) if codes else "NONE"


def _num(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[column], errors="coerce")


def _bool(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.lower().isin({"true", "1", "yes", "y"})


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = pd.to_numeric(denominator, errors="coerce").replace(0, pd.NA)
    return pd.to_numeric(numerator, errors="coerce") / denominator


def _safe_num(value) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = df.copy()
    for column in columns:
        if column not in result.columns:
            result[column] = pd.NA
    return result
