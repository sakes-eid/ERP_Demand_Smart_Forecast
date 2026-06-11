"""Load, clean, and validate Phase 3 inventory input data."""

from __future__ import annotations

import pandas as pd

from config import (
    INVENTORY_BATCHES_FILE,
    INVENTORY_FILE,
    INVENTORY_MOVEMENTS_FILE,
    NEAR_EXPIRY_DAYS,
    SKU_STORAGE_REQUIREMENTS_FILE,
    STORAGE_LOCATIONS_FILE,
    WAREHOUSE_LAYOUT_FILE,
)
from core.inventory_schemas import (
    INVENTORY_BATCHES_SCHEMA,
    INVENTORY_MOVEMENTS_SCHEMA,
    INVENTORY_SCHEMA,
    SKU_STORAGE_REQUIREMENTS_SCHEMA,
    STORAGE_LOCATIONS_SCHEMA,
    WAREHOUSE_LAYOUT_SCHEMA,
    validate_schema,
)

ALLOWED_MOVEMENT_TYPES = {
    "RECEIPT",
    "PUTAWAY",
    "PICK",
    "SHIP",
    "DEMAND",
    "TRANSFER",
    "ADJUSTMENT",
    "CUSTOMER_RETURN",
    "SUPPLIER_RETURN",
    "SCRAP",
    "EXPIRED",
}

BOOLEAN_TRUE_VALUES = {"true", "1", "yes", "y", "t"}
HANDLING_UNITS = {"PALLET", "CASE", "EACH"}


def load_inventory_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and validate all Phase 3 inventory inputs."""
    inventory = pd.read_csv(INVENTORY_FILE)
    batches = pd.read_csv(INVENTORY_BATCHES_FILE)
    movements = pd.read_csv(INVENTORY_MOVEMENTS_FILE)
    warehouse_layout = pd.read_csv(WAREHOUSE_LAYOUT_FILE)
    storage_locations = pd.read_csv(STORAGE_LOCATIONS_FILE)
    sku_storage_requirements = pd.read_csv(SKU_STORAGE_REQUIREMENTS_FILE)

    validate_schema(inventory, "inventory.csv", INVENTORY_SCHEMA)
    validate_schema(batches, "inventory_batches.csv", INVENTORY_BATCHES_SCHEMA)
    validate_schema(movements, "inventory_movements.csv", INVENTORY_MOVEMENTS_SCHEMA)
    validate_schema(warehouse_layout, "warehouse_layout.csv", WAREHOUSE_LAYOUT_SCHEMA)
    validate_schema(storage_locations, "storage_locations.csv", STORAGE_LOCATIONS_SCHEMA)
    validate_schema(sku_storage_requirements, "sku_storage_requirements.csv", SKU_STORAGE_REQUIREMENTS_SCHEMA)

    return inventory, batches, movements, warehouse_layout, storage_locations, sku_storage_requirements


def clean_inventory(inventory: pd.DataFrame) -> pd.DataFrame:
    """Clean inventory position records and add validation flags."""
    cleaned = inventory.copy()
    _strip_id_columns(cleaned)
    _parse_dates(cleaned, ["last_restock_date", "last_movement_date"])
    _to_numeric(
        cleaned,
        [
            "current_inventory",
            "reserved_inventory",
            "available_inventory",
            "inventory_value",
            "inventory_position",
            "unit_cost",
            "unit_holding_cost",
            "stockout_penalty_per_unit",
            "overstock_penalty_per_unit",
        ],
    )
    expected_value = cleaned["current_inventory"] * cleaned["unit_cost"]
    cleaned["inventory_value_expected"] = expected_value.round(2)
    cleaned["inventory_value_variance"] = (cleaned["inventory_value"] - expected_value).round(2)
    cleaned["inventory_value_recalculated_flag"] = cleaned["inventory_value"].isna()
    cleaned.loc[cleaned["inventory_value"].isna(), "inventory_value"] = expected_value
    cleaned["negative_inventory_flag"] = cleaned["current_inventory"] < 0
    cleaned["zero_inventory_flag"] = cleaned["current_inventory"] == 0
    cleaned["positive_inventory_flag"] = cleaned["current_inventory"] > 0
    cleaned["negative_reserved_inventory_flag"] = cleaned["reserved_inventory"] < 0
    cleaned["negative_unit_cost_flag"] = cleaned["unit_cost"] < 0
    cleaned["negative_stockout_penalty_flag"] = cleaned["stockout_penalty_per_unit"] < 0
    cleaned["negative_overstock_penalty_flag"] = cleaned["overstock_penalty_per_unit"] < 0
    return cleaned


def clean_inventory_batches(batches: pd.DataFrame) -> pd.DataFrame:
    """Clean batch records and add expiry/quantity flags."""
    cleaned = batches.copy()
    _strip_id_columns(cleaned)
    _parse_dates(cleaned, ["received_date", "expiry_date"])
    _to_numeric(
        cleaned,
        [
            "quantity_received",
            "quantity_on_hand",
            "quantity_reserved",
            "quantity_available",
            "unit_cost",
            "batch_value",
            "shelf_life_days",
        ],
    )
    reference_date = pd.Timestamp.today().normalize()
    cleaned["days_until_expiry"] = (cleaned["expiry_date"] - reference_date).dt.days
    cleaned["batch_value"] = (cleaned["quantity_on_hand"] * cleaned["unit_cost"]).round(2)
    cleaned["expired_flag"] = cleaned["days_until_expiry"].notna() & (cleaned["days_until_expiry"] < 0)
    cleaned["near_expiry_flag"] = (
        cleaned["days_until_expiry"].notna()
        & (cleaned["days_until_expiry"] >= 0)
        & (cleaned["days_until_expiry"] <= NEAR_EXPIRY_DAYS)
    )
    cleaned["negative_batch_quantity_flag"] = (
        (cleaned["quantity_received"] < 0)
        | (cleaned["quantity_on_hand"] < 0)
        | (cleaned["quantity_reserved"] < 0)
        | (cleaned["quantity_available"] < 0)
    )
    cleaned["negative_unit_cost_flag"] = cleaned["unit_cost"] < 0
    return cleaned


def clean_inventory_movements(movements: pd.DataFrame) -> pd.DataFrame:
    """Clean movement history and flag unknown movement types."""
    cleaned = movements.copy()
    _strip_id_columns(cleaned)
    _parse_dates(cleaned, ["movement_date"])
    _to_numeric(cleaned, ["quantity"])
    cleaned["movement_type"] = cleaned["movement_type"].astype(str).str.strip().str.upper()
    cleaned["unknown_movement_type_flag"] = ~cleaned["movement_type"].isin(ALLOWED_MOVEMENT_TYPES)
    return cleaned


def clean_warehouse_layout(warehouse_layout: pd.DataFrame) -> pd.DataFrame:
    """Clean warehouse layout and forklift access flags."""
    cleaned = warehouse_layout.copy()
    _strip_id_columns(cleaned)
    _to_numeric(
        cleaned,
        [
            "warehouse_length_m",
            "warehouse_width_m",
            "total_floor_area_m2",
            "storage_area_m2",
            "receiving_area_m2",
            "shipping_area_m2",
            "crossdock_area_m2",
            "returns_area_m2",
            "aisle_width_m",
            "minimum_required_aisle_width_m",
            "dock_x",
            "dock_y",
            "entrance_x",
            "entrance_y",
            "exit_x",
            "exit_y",
        ],
    )
    _to_bool(cleaned, ["forklift_accessible"])
    calculated_area = cleaned["warehouse_length_m"] * cleaned["warehouse_width_m"]
    cleaned["total_floor_area_m2"] = cleaned["total_floor_area_m2"].fillna(calculated_area)
    cleaned["aisle_width_ok"] = cleaned["aisle_width_m"] >= cleaned["minimum_required_aisle_width_m"]
    cleaned.loc[~cleaned["aisle_width_ok"], "forklift_accessible"] = False
    return cleaned


def clean_storage_locations(storage_locations: pd.DataFrame) -> pd.DataFrame:
    """Clean storage locations and add capacity flags."""
    cleaned = storage_locations.copy()
    _strip_id_columns(cleaned)
    _to_numeric(
        cleaned,
        [
            "shelf_level",
            "x_coord",
            "y_coord",
            "distance_to_dock",
            "distance_to_exit",
            "distance_to_entrance",
            "capacity_units",
            "capacity_volume_m3",
            "capacity_weight_kg",
            "used_units",
            "used_volume_m3",
            "used_weight_kg",
            "free_units",
            "free_volume_m3",
            "free_weight_kg",
        ],
    )
    _to_bool(
        cleaned,
        [
            "forklift_accessible",
            "temperature_controlled",
            "security_controlled",
            "heavy_item_allowed",
            "fragile_item_allowed",
            "perishable_item_allowed",
        ],
    )
    cleaned["free_units"] = cleaned["capacity_units"] - cleaned["used_units"]
    cleaned["free_volume_m3"] = cleaned["capacity_volume_m3"] - cleaned["used_volume_m3"]
    cleaned["free_weight_kg"] = cleaned["capacity_weight_kg"] - cleaned["used_weight_kg"]
    cleaned["overcapacity_units_flag"] = cleaned["used_units"] > cleaned["capacity_units"]
    cleaned["overcapacity_volume_flag"] = cleaned["used_volume_m3"] > cleaned["capacity_volume_m3"]
    cleaned["overcapacity_weight_flag"] = cleaned["used_weight_kg"] > cleaned["capacity_weight_kg"]
    cleaned["overcapacity_flag"] = (
        cleaned["overcapacity_units_flag"]
        | cleaned["overcapacity_volume_flag"]
        | cleaned["overcapacity_weight_flag"]
    )
    return cleaned


def clean_sku_storage_requirements(sku_storage_requirements: pd.DataFrame) -> pd.DataFrame:
    """Clean SKU storage requirements and add validation flags."""
    cleaned = sku_storage_requirements.copy()
    _strip_id_columns(cleaned)
    _to_numeric(
        cleaned,
        [
            "unit_volume_m3",
            "unit_weight_kg",
            "units_per_case",
            "cases_per_pallet",
            "handling_cost_per_unit",
            "handling_cost_per_case",
            "handling_cost_per_pallet",
            "max_stack_height",
        ],
    )
    _to_bool(
        cleaned,
        [
            "stackable",
            "fragile",
            "perishable",
            "temperature_required",
            "security_required",
            "heavy_low_storage_required",
            "expiry_tracking_required",
            "fefo_required",
        ],
    )
    cleaned["handling_unit"] = cleaned["handling_unit"].astype(str).str.strip().str.upper()
    cleaned["invalid_unit_volume_flag"] = cleaned["unit_volume_m3"] <= 0
    cleaned["invalid_unit_weight_flag"] = cleaned["unit_weight_kg"] <= 0
    cleaned["invalid_handling_unit_flag"] = ~cleaned["handling_unit"].isin(HANDLING_UNITS)
    cleaned["fefo_required"] = cleaned["fefo_required"] | cleaned["expiry_tracking_required"] | cleaned["perishable"]
    return cleaned


def _strip_id_columns(df: pd.DataFrame) -> None:
    """Strip whitespace from ID and code columns in-place."""
    for column in df.columns:
        if column.endswith("_id") or column in {
            "sku_id",
            "batch_id",
            "warehouse_id",
            "location_id",
            "movement_id",
            "zone",
            "aisle",
            "rack",
            "movement_type",
            "reason_code",
            "inventory_owner_type",
            "item_planning_type",
            "push_pull_boundary_role",
        }:
            df[column] = df[column].astype(str).str.strip()


def _parse_dates(df: pd.DataFrame, columns: list[str]) -> None:
    """Parse date columns in-place."""
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce")


def _to_numeric(df: pd.DataFrame, columns: list[str]) -> None:
    """Convert numeric columns in-place."""
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")


def _to_bool(df: pd.DataFrame, columns: list[str]) -> None:
    """Convert boolean-like columns in-place."""
    for column in columns:
        if column in df.columns:
            df[column] = df[column].fillna(False).astype(str).str.strip().str.lower().isin(BOOLEAN_TRUE_VALUES)


def _latest_or_today(df: pd.DataFrame, date_columns: list[str]) -> pd.Timestamp:
    """Use the latest available date or today's date as fallback."""
    dates = []
    for column in date_columns:
        if column in df.columns:
            dates.append(df[column])
    if not dates:
        return pd.Timestamp.today().normalize()
    all_dates = pd.concat(dates).dropna()
    if all_dates.empty:
        return pd.Timestamp.today().normalize()
    return all_dates.max().normalize()
