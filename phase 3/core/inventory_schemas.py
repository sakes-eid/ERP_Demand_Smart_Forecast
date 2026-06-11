"""Schema definitions for Phase 3 inventory input files."""

INVENTORY_SCHEMA = [
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

INVENTORY_BATCHES_SCHEMA = [
    "batch_id",
    "sku_id",
    "supplier_id",
    "warehouse_id",
    "location_id",
    "received_date",
    "expiry_date",
    "quantity_received",
    "quantity_on_hand",
    "quantity_reserved",
    "quantity_available",
    "unit_cost",
    "batch_value",
    "batch_status",
    "shelf_life_days",
]

INVENTORY_MOVEMENTS_SCHEMA = [
    "movement_id",
    "sku_id",
    "batch_id",
    "warehouse_id",
    "location_id",
    "movement_date",
    "movement_type",
    "quantity",
    "source_location_id",
    "destination_location_id",
    "reason_code",
    "related_po_id",
    "related_order_id",
]

WAREHOUSE_LAYOUT_SCHEMA = [
    "warehouse_id",
    "warehouse_name",
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
    "forklift_accessible",
    "dock_x",
    "dock_y",
    "entrance_x",
    "entrance_y",
    "exit_x",
    "exit_y",
]

STORAGE_LOCATIONS_SCHEMA = [
    "location_id",
    "warehouse_id",
    "zone",
    "aisle",
    "rack",
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
    "location_type",
    "forklift_accessible",
    "temperature_controlled",
    "security_controlled",
    "heavy_item_allowed",
    "fragile_item_allowed",
    "perishable_item_allowed",
]

SKU_STORAGE_REQUIREMENTS_SCHEMA = [
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


def validate_schema(df, schema_name: str, required_columns: list[str]) -> None:
    """Validate that required columns exist in a dataframe."""
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"{schema_name} is missing required columns: {missing}")
