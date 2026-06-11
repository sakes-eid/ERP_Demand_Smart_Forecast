"""Procurement requirement calculations for Phase 2 capability planning."""

import pandas as pd

from config import PROCUREMENT_CAPABILITY_CONFIG


def build_procurement_requirements(
    sku_ids,
    demand_context: pd.DataFrame,
    backorder_summary: pd.DataFrame,
    purchase_orders: pd.DataFrame,
    receipts: pd.DataFrame,
    as_of_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Build provisional SKU-level procurement requirements without inventory mutation."""
    as_of = pd.Timestamp(as_of_date).normalize() if as_of_date is not None else pd.Timestamp.today().normalize()
    base = pd.DataFrame({"sku_id": sorted(set(pd.Series(list(sku_ids)).astype(str)))})
    demand = _demand_fields(demand_context)
    backorders = _backorder_fields(backorder_summary)
    inbound = _confirmed_inbound(purchase_orders, receipts, as_of)

    req = base.merge(demand, on="sku_id", how="left")
    req = req.merge(backorders, on="sku_id", how="left")
    req = req.merge(inbound, on="sku_id", how="left")
    req = _fill_defaults(req)

    req["gross_procurement_requirement_units"] = (
        req["gross_forecast_demand_30d"]
        + req["active_backorder_units"]
        + req["provisional_buffer_requirement_units"]
    )
    req["confirmed_inbound_units"] = req["open_po_confirmed_units_30d"]
    req["expected_receipts_within_horizon_units"] = req["open_po_confirmed_units_30d"]
    req["provisional_net_procurement_requirement_units"] = (
        req["gross_procurement_requirement_units"]
        - req["usable_on_hand_inventory_units"]
        - req["confirmed_inbound_units"]
    ).clip(lower=0)
    req["remaining_horizon_requirement_units"] = req["provisional_net_procurement_requirement_units"]
    req["inventory_deduction_available_flag"] = False
    req["inbound_deduction_available_flag"] = req["confirmed_inbound_units"] > 0
    req["net_requirement_is_provisional_flag"] = True
    req["procurement_requirement_method"] = "PROVISIONAL_NO_INVENTORY_CONTEXT"
    req["buffer_requirement_source"] = "NO_PHASE3_POLICY_CONTEXT"
    req["inventory_context_missing_warning"] = "PHASE3_INVENTORY_CONTEXT_NOT_CONNECTED"
    req["procurement_requirement_warning_codes"] = req.apply(_requirement_warnings, axis=1)
    req["inbound_data_quality_flag"] = req["inbound_warning_codes"].eq("NONE")
    return req


def add_option_immediate_requirements(requirements: pd.DataFrame, options: pd.DataFrame) -> pd.DataFrame:
    """Add lead-time and immediate requirement fields to each supplier option."""
    enriched = options.merge(requirements, on="sku_id", how="left")
    lead_time = pd.to_numeric(enriched["expected_lead_time_days"], errors="coerce").fillna(0).clip(lower=0)
    avg_daily = pd.to_numeric(enriched["average_daily_forecast_demand_30d"], errors="coerce").fillna(
        pd.to_numeric(enriched["gross_forecast_demand_30d"], errors="coerce").fillna(0) / 30
    )
    enriched["lead_time_demand_units"] = (avg_daily * lead_time).round(2)
    enriched["confirmed_inbound_before_expected_arrival_units"] = enriched.apply(
        _confirmed_before_arrival,
        axis=1,
    )
    enriched["immediate_procurement_requirement_units"] = (
        enriched["lead_time_demand_units"]
        + enriched["active_backorder_units"]
        - enriched["confirmed_inbound_before_expected_arrival_units"]
    ).clip(lower=0)
    enriched["remaining_horizon_requirement_units"] = (
        enriched["provisional_net_procurement_requirement_units"]
        - enriched["immediate_procurement_requirement_units"]
    ).clip(lower=0)
    enriched["immediate_requirement_basis"] = "LEAD_TIME_DEMAND_PLUS_BACKORDER_MINUS_CONFIRMED_INBOUND"
    enriched["immediate_requirement_warning_codes"] = enriched.apply(_immediate_warnings, axis=1)
    return enriched


def _demand_fields(demand_context: pd.DataFrame) -> pd.DataFrame:
    if demand_context is None or demand_context.empty:
        return pd.DataFrame(columns=["sku_id"])
    columns = [
        "sku_id",
        "forecast_demand_7d",
        "forecast_demand_30d",
        "forecast_demand_60d",
        "forecast_demand_90d",
        "average_daily_forecast_demand_30d",
    ]
    existing = [column for column in columns if column in demand_context.columns]
    demand = demand_context[existing].drop_duplicates("sku_id")
    rename = {
        "forecast_demand_7d": "gross_forecast_demand_7d",
        "forecast_demand_30d": "gross_forecast_demand_30d",
        "forecast_demand_60d": "gross_forecast_demand_60d",
        "forecast_demand_90d": "gross_forecast_demand_90d",
    }
    return demand.rename(columns=rename)


def _backorder_fields(backorder_summary: pd.DataFrame) -> pd.DataFrame:
    if backorder_summary is None or backorder_summary.empty:
        return pd.DataFrame(columns=["sku_id"])
    fields = backorder_summary[["sku_id", "total_remaining_backorder_units"]].copy()
    fields = fields.rename(
        columns={
            "total_remaining_backorder_units": "active_backorder_units",
        }
    )
    fields["backorder_requirement_units"] = fields["active_backorder_units"]
    return fields


def _confirmed_inbound(
    purchase_orders: pd.DataFrame,
    receipts: pd.DataFrame,
    as_of: pd.Timestamp,
) -> pd.DataFrame:
    if purchase_orders is None or purchase_orders.empty:
        return pd.DataFrame(columns=["sku_id"])
    orders = purchase_orders.copy()
    orders["promised_delivery_date"] = pd.to_datetime(orders["promised_delivery_date"], errors="coerce")
    orders["ordered_quantity"] = pd.to_numeric(orders["ordered_quantity"], errors="coerce").fillna(0)
    received = _received_by_po(receipts)
    orders = orders.merge(received, on="po_id", how="left")
    orders["received_quantity_total"] = orders["received_quantity_total"].fillna(0)
    orders["open_order_quantity"] = (orders["ordered_quantity"] - orders["received_quantity_total"]).clip(lower=0)
    future = orders[(orders["open_order_quantity"] > 0) & orders["promised_delivery_date"].notna()].copy()
    future["days_to_arrival"] = (future["promised_delivery_date"] - as_of).dt.days
    future = future[future["days_to_arrival"] >= 0]
    rows = []
    for sku_id, sku_orders in future.groupby("sku_id", sort=True):
        row = {"sku_id": sku_id}
        for horizon in [7, 30, 60, 90]:
            row[f"open_po_confirmed_units_{horizon}d"] = float(
                sku_orders.loc[sku_orders["days_to_arrival"] <= horizon, "open_order_quantity"].sum()
            )
        rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty:
        result = pd.DataFrame(columns=["sku_id"])
    uncertain = orders[(orders["open_order_quantity"] > 0) & orders["promised_delivery_date"].isna()]
    if not uncertain.empty:
        uncertain_by_sku = uncertain.groupby("sku_id")["open_order_quantity"].sum().reset_index()
        uncertain_by_sku = uncertain_by_sku.rename(columns={"open_order_quantity": "uncertain_inbound_units"})
        result = result.merge(uncertain_by_sku, on="sku_id", how="outer")
    return result


def _received_by_po(receipts: pd.DataFrame) -> pd.DataFrame:
    if receipts is None or receipts.empty:
        return pd.DataFrame(columns=["po_id", "received_quantity_total"])
    received = receipts.copy()
    received["received_quantity"] = pd.to_numeric(received["received_quantity"], errors="coerce").fillna(0)
    return received.groupby("po_id", as_index=False)["received_quantity"].sum().rename(
        columns={"received_quantity": "received_quantity_total"}
    )


def _fill_defaults(req: pd.DataFrame) -> pd.DataFrame:
    defaults = {
        "gross_forecast_demand_7d": 0.0,
        "gross_forecast_demand_30d": 0.0,
        "gross_forecast_demand_60d": 0.0,
        "gross_forecast_demand_90d": 0.0,
        "average_daily_forecast_demand_30d": 0.0,
        "active_backorder_units": 0.0,
        "backorder_requirement_units": 0.0,
        "usable_on_hand_inventory_units": 0.0,
        "confirmed_inbound_units": 0.0,
        "open_po_confirmed_units_7d": 0.0,
        "open_po_confirmed_units_30d": 0.0,
        "open_po_confirmed_units_60d": 0.0,
        "open_po_confirmed_units_90d": 0.0,
        "expected_receipts_within_horizon_units": 0.0,
        "uncertain_inbound_units": 0.0,
        "provisional_buffer_requirement_units": 0.0,
        "inbound_warning_codes": "NONE",
    }
    filled = req.copy()
    for column, default in defaults.items():
        if column not in filled.columns:
            filled[column] = default
        else:
            filled[column] = filled[column].fillna(default)
    return filled


def _confirmed_before_arrival(row: pd.Series) -> float:
    lead_time = float(row.get("expected_lead_time_days", 0) or 0)
    if lead_time <= 7:
        return float(row.get("open_po_confirmed_units_7d", 0) or 0)
    if lead_time <= 30:
        return float(row.get("open_po_confirmed_units_30d", 0) or 0)
    if lead_time <= 60:
        return float(row.get("open_po_confirmed_units_60d", 0) or 0)
    return float(row.get("open_po_confirmed_units_90d", 0) or 0)


def _requirement_warnings(row: pd.Series) -> str:
    warnings = ["PROVISIONAL_NO_INVENTORY_CONTEXT"]
    if float(row.get("uncertain_inbound_units", 0) or 0) > 0:
        warnings.append("UNCERTAIN_INBOUND_EXCLUDED")
    if float(row.get("provisional_buffer_requirement_units", 0) or 0) == 0:
        warnings.append("BUFFER_REQUIREMENT_NOT_CONNECTED")
    return ";".join(warnings)


def _immediate_warnings(row: pd.Series) -> str:
    warnings = []
    if float(row.get("immediate_procurement_requirement_units", 0) or 0) > float(
        row.get("provisional_net_procurement_requirement_units", 0) or 0
    ):
        warnings.append("IMMEDIATE_REQUIREMENT_EXCEEDS_NET_REQUIREMENT_DUE_TO_BACKORDER_URGENCY")
    return ";".join(warnings) if warnings else "NONE"
