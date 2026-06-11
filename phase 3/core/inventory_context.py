"""Build SKU-level inventory planning context for later Phase 3 logic."""

from __future__ import annotations

import pandas as pd

from config import DEAD_STOCK_DAYS, NON_MOVING_DAYS


def build_inventory_planning_context(
    inventory: pd.DataFrame,
    batches: pd.DataFrame,
    movements: pd.DataFrame,
    storage_requirements: pd.DataFrame,
    phase1_context: pd.DataFrame,
    phase2_context: pd.DataFrame,
) -> pd.DataFrame:
    """Build one planning-context row per SKU without calculating policies."""
    context = _inventory_base(inventory)
    context = context.merge(_storage_requirements(storage_requirements), on="sku_id", how="left")
    context = context.merge(_batch_summary(batches), on="sku_id", how="left")
    context = context.merge(_movement_summary(movements), on="sku_id", how="left")
    context = context.merge(phase1_context, on="sku_id", how="left")
    context = context.merge(phase2_context, on="sku_id", how="left")
    context = _fill_summary_defaults(context)
    context = _add_derived_context_fields(context)
    return context


def _inventory_base(inventory: pd.DataFrame) -> pd.DataFrame:
    """Select and rename inventory fields for the context."""
    base_columns = [
        "sku_id",
        "warehouse_id",
        "current_inventory",
        "reserved_inventory",
        "available_inventory",
        "inventory_value",
        "inventory_position",
        "unit_cost",
        "unit_holding_cost",
        "stockout_penalty_per_unit",
        "overstock_penalty_per_unit",
        "storage_location_id",
        "last_restock_date",
        "last_movement_date",
        "inventory_owner_type",
        "item_planning_type",
        "push_pull_boundary_role",
    ]
    available = [column for column in base_columns if column in inventory.columns]
    base = inventory[available].copy()
    if "unit_cost" in base.columns:
        base = base.rename(columns={"unit_cost": "unit_cost_inventory"})
    return base


def _storage_requirements(storage_requirements: pd.DataFrame) -> pd.DataFrame:
    """Select storage requirement fields."""
    columns = [
        "sku_id",
        "unit_volume_m3",
        "unit_weight_kg",
        "stackable",
        "fragile",
        "perishable",
        "temperature_required",
        "security_required",
        "handling_unit",
        "units_per_case",
        "cases_per_pallet",
        "handling_cost_per_unit",
        "handling_cost_per_case",
        "handling_cost_per_pallet",
        "preferred_zone",
        "max_stack_height",
        "heavy_low_storage_required",
        "expiry_tracking_required",
        "fefo_required",
    ]
    available = [column for column in columns if column in storage_requirements.columns]
    return storage_requirements[available].drop_duplicates("sku_id") if available else pd.DataFrame(columns=["sku_id"])


def _batch_summary(batches: pd.DataFrame) -> pd.DataFrame:
    """Summarize batch-level inventory by SKU."""
    if batches.empty or "sku_id" not in batches.columns:
        return pd.DataFrame(columns=["sku_id"])
    working = batches.copy()
    for column in ["quantity_on_hand", "days_until_expiry"]:
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")
    if "expiry_date" in working.columns:
        working["expiry_date"] = pd.to_datetime(working["expiry_date"], errors="coerce")
    working["near_expiry_units_calc"] = working["quantity_on_hand"].where(_bool_column(working, "near_expiry_flag"), 0)
    working["expired_units_calc"] = working["quantity_on_hand"].where(_bool_column(working, "expired_flag"), 0)
    summary = working.groupby("sku_id", dropna=False).agg(
        batch_count=("batch_id", "nunique") if "batch_id" in working.columns else ("sku_id", "size"),
        total_batch_quantity_on_hand=("quantity_on_hand", "sum"),
        near_expiry_batch_count=("near_expiry_flag", lambda series: _bool_series(series).sum())
        if "near_expiry_flag" in working.columns
        else ("sku_id", "size"),
        near_expiry_units=("near_expiry_units_calc", "sum"),
        expired_batch_count=("expired_flag", lambda series: _bool_series(series).sum())
        if "expired_flag" in working.columns
        else ("sku_id", "size"),
        expired_units=("expired_units_calc", "sum"),
        earliest_expiry_date=("expiry_date", "min") if "expiry_date" in working.columns else ("sku_id", "first"),
        minimum_days_until_expiry=("days_until_expiry", "min") if "days_until_expiry" in working.columns else ("sku_id", "first"),
    ).reset_index()
    summary["expiry_tracking_present"] = summary["earliest_expiry_date"].notna()
    return summary


def _movement_summary(movements: pd.DataFrame) -> pd.DataFrame:
    """Summarize movement history by SKU."""
    if movements.empty or "sku_id" not in movements.columns:
        return pd.DataFrame(columns=["sku_id"])
    working = movements.copy()
    working["movement_date"] = pd.to_datetime(working["movement_date"], errors="coerce")
    working["quantity"] = pd.to_numeric(working["quantity"], errors="coerce").fillna(0)
    working["movement_type"] = working["movement_type"].astype(str).str.upper()
    working["outbound_quantity_calc"] = working["quantity"].where(working["quantity"] < 0, 0).abs()
    working["inbound_quantity_calc"] = working["quantity"].where(working["quantity"] > 0, 0)
    summary = working.groupby("sku_id", dropna=False).agg(
        movement_count=("movement_id", "nunique") if "movement_id" in working.columns else ("sku_id", "size"),
        last_movement_date_from_movements=("movement_date", "max"),
        receipt_movement_count=("movement_type", lambda series: series.isin(["RECEIPT", "PUTAWAY"]).sum()),
        demand_movement_count=("movement_type", lambda series: series.isin(["DEMAND"]).sum()),
        pick_ship_movement_count=("movement_type", lambda series: series.isin(["PICK", "SHIP"]).sum()),
        return_movement_count=("movement_type", lambda series: series.isin(["CUSTOMER_RETURN", "SUPPLIER_RETURN"]).sum()),
        adjustment_movement_count=("movement_type", lambda series: series.isin(["ADJUSTMENT"]).sum()),
        total_movement_quantity=("quantity", "sum"),
        total_outbound_quantity=("outbound_quantity_calc", "sum"),
        total_inbound_quantity=("inbound_quantity_calc", "sum"),
    ).reset_index()
    today = pd.Timestamp.today().normalize()
    summary["days_since_last_movement"] = (today - summary["last_movement_date_from_movements"]).dt.days
    return summary


def _fill_summary_defaults(context: pd.DataFrame) -> pd.DataFrame:
    """Fill missing summary values after context merges."""
    defaults = {
        "batch_count": 0,
        "total_batch_quantity_on_hand": 0,
        "near_expiry_batch_count": 0,
        "near_expiry_units": 0,
        "expired_batch_count": 0,
        "expired_units": 0,
        "minimum_days_until_expiry": pd.NA,
        "expiry_tracking_present": False,
        "movement_count": 0,
        "days_since_last_movement": pd.NA,
        "receipt_movement_count": 0,
        "demand_movement_count": 0,
        "pick_ship_movement_count": 0,
        "return_movement_count": 0,
        "adjustment_movement_count": 0,
        "total_movement_quantity": 0,
        "total_outbound_quantity": 0,
        "total_inbound_quantity": 0,
    }
    filled = context.copy()
    for column, default in defaults.items():
        if column not in filled.columns:
            filled[column] = default
        else:
            filled[column] = filled[column].fillna(default)
    return filled


def _add_derived_context_fields(context: pd.DataFrame) -> pd.DataFrame:
    """Add lightweight signals for later inventory logic."""
    enriched = context.copy()
    current_inventory = pd.to_numeric(enriched["current_inventory"], errors="coerce").fillna(0)
    enriched["stockout_signal"] = current_inventory < 0
    enriched["stockout_units"] = current_inventory.where(current_inventory < 0, 0).abs()
    enriched["zero_inventory_signal"] = current_inventory == 0
    enriched["positive_inventory_signal"] = current_inventory > 0
    enriched["expiry_risk_signal"] = (
        pd.to_numeric(enriched["near_expiry_units"], errors="coerce").fillna(0) > 0
    ) | (
        pd.to_numeric(enriched["expired_units"], errors="coerce").fillna(0) > 0
    )
    days_since = pd.to_numeric(enriched["days_since_last_movement"], errors="coerce")
    enriched["non_moving_signal"] = days_since >= NON_MOVING_DAYS
    enriched["dead_stock_signal"] = days_since >= DEAD_STOCK_DAYS
    enriched["supplier_review_signal"] = _bool_column(enriched, "recommended_supplier_requires_review")
    enriched["watchlist_supplier_signal"] = _bool_column(enriched, "supplier_watchlist_flag")
    phase1_loaded = enriched["phase1_context_status"].astype(str).eq("LOADED_FROM_PHASE1")
    phase2_loaded = enriched["phase2_context_status"].astype(str).eq("LOADED_FROM_PHASE2")
    enriched["planning_context_status"] = "FALLBACK_CONTEXT"
    enriched.loc[phase1_loaded ^ phase2_loaded, "planning_context_status"] = "PARTIAL_CONTEXT"
    enriched.loc[phase1_loaded & phase2_loaded, "planning_context_status"] = "COMPLETE_CONTEXT"
    return enriched


def _bool_column(df: pd.DataFrame, column: str) -> pd.Series:
    """Return a boolean series for a column that may contain strings."""
    if column not in df.columns:
        return pd.Series(False, index=df.index)
    return _bool_series(df[column])


def _bool_series(series: pd.Series) -> pd.Series:
    """Convert a series to booleans safely."""
    return series.fillna(False).astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
