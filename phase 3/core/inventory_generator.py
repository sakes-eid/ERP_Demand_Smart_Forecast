"""Generate realistic Phase 3 inventory and warehouse demo data."""

from __future__ import annotations

import math
from datetime import date

import pandas as pd

from config import (
    DATA_DIR,
    DEFAULT_OVERSTOCK_PENALTY_PER_UNIT,
    DEFAULT_STOCKOUT_PENALTY_PER_UNIT,
    DEFAULT_WAREHOUSE_LENGTH_M,
    DEFAULT_WAREHOUSE_WIDTH_M,
    HANDLING_UNIT_COSTS,
    INVENTORY_BATCHES_FILE,
    INVENTORY_FILE,
    INVENTORY_MOVEMENTS_FILE,
    MIN_FORKLIFT_AISLE_WIDTH_M,
    SKU_STORAGE_REQUIREMENTS_FILE,
    STORAGE_LOCATIONS_FILE,
    WAREHOUSE_LAYOUT_FILE,
)

SKU_IDS = [
    "SKU-COF-001",
    "SKU-TEA-002",
    "SKU-SUN-003",
    "SKU-SUP-004",
    "SKU-CHC-005",
    "SKU-BBQ-006",
    "SKU-UMR-007",
    "SKU-BAT-008",
    "SKU-FIL-009",
    "SKU-GFT-010",
]

REFERENCE_DATE = pd.Timestamp("2026-06-04")

SKU_PROFILES = {
    "SKU-COF-001": {"cost": 6.5, "inventory": 420, "penalty": 35, "overstock": 4, "loc": "LOC-FP-001"},
    "SKU-TEA-002": {"cost": 4.2, "inventory": 0, "penalty": 30, "overstock": 7, "loc": "LOC-CP-001"},
    "SKU-SUN-003": {"cost": 9.8, "inventory": 160, "penalty": 22, "overstock": 9, "loc": "LOC-TC-001"},
    "SKU-SUP-004": {"cost": 5.4, "inventory": -18, "penalty": 28, "overstock": 6, "loc": "LOC-TC-002"},
    "SKU-CHC-005": {"cost": 3.8, "inventory": 35, "penalty": 24, "overstock": 8, "loc": "LOC-TC-003"},
    "SKU-BBQ-006": {"cost": 12.5, "inventory": 720, "penalty": 18, "overstock": 12, "loc": "LOC-BK-001"},
    "SKU-UMR-007": {"cost": 14.0, "inventory": 8, "penalty": 26, "overstock": 10, "loc": "LOC-SP-001"},
    "SKU-BAT-008": {"cost": 7.2, "inventory": -6, "penalty": 40, "overstock": 4, "loc": "LOC-SC-001"},
    "SKU-FIL-009": {"cost": 11.3, "inventory": 96, "penalty": 20, "overstock": 5, "loc": "LOC-EP-001"},
    "SKU-GFT-010": {"cost": 16.5, "inventory": 310, "penalty": 32, "overstock": 14, "loc": "LOC-SC-002"},
}

SUPPLIER_IDS = ["SUP-001", "SUP-002", "SUP-003", "SUP-004", "SUP-005", "SUP-006", "SUP-007"]


def create_sample_inventory_files() -> None:
    """Create Phase 3 demo files only when one or more input files are missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    files = [
        INVENTORY_FILE,
        INVENTORY_BATCHES_FILE,
        INVENTORY_MOVEMENTS_FILE,
        WAREHOUSE_LAYOUT_FILE,
        STORAGE_LOCATIONS_FILE,
        SKU_STORAGE_REQUIREMENTS_FILE,
    ]
    if all(path.exists() for path in files):
        print("Phase 3 input files already exist. Using existing files.")
        print("To regenerate demo data manually, close open CSV files, delete the files in data/, and rerun python main.py.")
        return

    storage_requirements = _sample_sku_storage_requirements()
    storage_locations = _sample_storage_locations()
    inventory = _sample_inventory(storage_requirements)
    batches = _sample_inventory_batches(inventory, storage_requirements)
    movements = _sample_inventory_movements(batches)
    warehouse_layout = _sample_warehouse_layout()

    _write_if_missing(INVENTORY_FILE, inventory)
    _write_if_missing(INVENTORY_BATCHES_FILE, batches)
    _write_if_missing(INVENTORY_MOVEMENTS_FILE, movements)
    _write_if_missing(WAREHOUSE_LAYOUT_FILE, warehouse_layout)
    _write_if_missing(STORAGE_LOCATIONS_FILE, storage_locations)
    _write_if_missing(SKU_STORAGE_REQUIREMENTS_FILE, storage_requirements)
    print("Generated realistic Phase 3 inventory and warehouse demo data.")


def _write_if_missing(path, df: pd.DataFrame) -> None:
    """Write a CSV only if it does not already exist."""
    if not path.exists():
        df.to_csv(path, index=False)


def _sample_inventory(storage_requirements: pd.DataFrame) -> pd.DataFrame:
    """Create realistic inventory position data."""
    rows = []
    for index, sku_id in enumerate(SKU_IDS):
        profile = SKU_PROFILES[sku_id]
        current_inventory = profile["inventory"]
        reserved_inventory = max(0, int(abs(current_inventory) * (0.08 + 0.02 * (index % 3))))
        available_inventory = current_inventory - reserved_inventory
        unit_cost = profile["cost"]
        unit_holding_cost = round(unit_cost * 0.19 / 365, 4)
        last_restock = REFERENCE_DATE - pd.Timedelta(days=7 + index * 6)
        last_movement = REFERENCE_DATE - pd.Timedelta(days=[2, 4, 12, 1, 28, 45, 18, 3, 75, 10][index])
        planning_type = "PURCHASED_FINISHED_GOOD"
        owner_type = "PURCHASED"
        if sku_id in {"SKU-FIL-009"}:
            planning_type = "COMPONENT"
        if sku_id in {"SKU-SUP-004"}:
            planning_type = "SEMI_FINISHED"
            owner_type = "SEMI_PRODUCED"
        rows.append(
            {
                "sku_id": sku_id,
                "warehouse_id": "WH-001",
                "current_inventory": current_inventory,
                "reserved_inventory": reserved_inventory,
                "available_inventory": available_inventory,
                "inventory_value": round(current_inventory * unit_cost, 2),
                "inventory_position": current_inventory,
                "unit_cost": unit_cost,
                "unit_holding_cost": unit_holding_cost,
                "stockout_penalty_per_unit": profile.get("penalty", DEFAULT_STOCKOUT_PENALTY_PER_UNIT),
                "overstock_penalty_per_unit": profile.get("overstock", DEFAULT_OVERSTOCK_PENALTY_PER_UNIT),
                "storage_location_id": profile["loc"],
                "last_restock_date": last_restock.strftime("%Y-%m-%d"),
                "last_movement_date": last_movement.strftime("%Y-%m-%d"),
                "inventory_owner_type": owner_type,
                "item_planning_type": planning_type,
                "push_pull_boundary_role": _push_pull_role(sku_id),
            }
        )
    return pd.DataFrame(rows)


def _sample_inventory_batches(inventory: pd.DataFrame, storage_requirements: pd.DataFrame) -> pd.DataFrame:
    """Create inventory batches with fresh, near-expiry, expired, and hold examples."""
    rows = []
    perishable = set(storage_requirements[storage_requirements["perishable"]]["sku_id"])
    for sku_index, inventory_row in inventory.reset_index(drop=True).iterrows():
        sku_id = inventory_row["sku_id"]
        current_inventory = max(0, int(inventory_row["current_inventory"]))
        batch_count = 1 + (sku_index % 4)
        remaining = current_inventory
        for batch_index in range(batch_count):
            quantity = int(max(0, remaining // (batch_count - batch_index))) if batch_count - batch_index else 0
            remaining -= quantity
            if current_inventory == 0:
                quantity = 0
            received_date = REFERENCE_DATE - pd.Timedelta(days=20 + sku_index * 5 + batch_index * 35)
            expiry_date, status, shelf_life = _expiry_details(sku_id, batch_index, sku_id in perishable)
            reserved = int(quantity * (0.06 + 0.02 * (batch_index % 2)))
            available = quantity - reserved
            unit_cost = float(inventory_row["unit_cost"])
            rows.append(
                {
                    "batch_id": f"BATCH-{sku_id[-3:]}-{batch_index + 1:02d}",
                    "sku_id": sku_id,
                    "supplier_id": SUPPLIER_IDS[(sku_index + batch_index) % len(SUPPLIER_IDS)],
                    "warehouse_id": "WH-001",
                    "location_id": inventory_row["storage_location_id"],
                    "received_date": received_date.strftime("%Y-%m-%d"),
                    "expiry_date": "" if expiry_date is None else expiry_date.strftime("%Y-%m-%d"),
                    "quantity_received": quantity + int(quantity * 0.05),
                    "quantity_on_hand": quantity,
                    "quantity_reserved": reserved,
                    "quantity_available": available,
                    "unit_cost": unit_cost,
                    "batch_value": round(quantity * unit_cost, 2),
                    "batch_status": status,
                    "shelf_life_days": shelf_life,
                }
            )
    return pd.DataFrame(rows)


def _sample_inventory_movements(batches: pd.DataFrame) -> pd.DataFrame:
    """Create recent movement history with fast, slow, and non-moving examples."""
    rows = []
    movement_id = 1
    movement_plan = {
        "SKU-COF-001": [2, 5, 9, 13, 17, 21, 25],
        "SKU-TEA-002": [4, 9, 16],
        "SKU-SUN-003": [8, 14, 35],
        "SKU-SUP-004": [1, 3, 7, 12, 18],
        "SKU-CHC-005": [28, 46],
        "SKU-BBQ-006": [45, 76, 105],
        "SKU-UMR-007": [18, 34],
        "SKU-BAT-008": [3, 5, 11, 19, 27],
        "SKU-FIL-009": [75, 140],
        "SKU-GFT-010": [10, 20, 32, 55],
    }
    movement_types = ["RECEIPT", "PUTAWAY", "PICK", "SHIP", "DEMAND", "TRANSFER", "ADJUSTMENT"]
    for sku_id, day_offsets in movement_plan.items():
        sku_batches = batches[batches["sku_id"] == sku_id]
        batch_id = sku_batches.iloc[0]["batch_id"] if not sku_batches.empty else ""
        location_id = sku_batches.iloc[0]["location_id"] if not sku_batches.empty else ""
        for offset_index, days_ago in enumerate(day_offsets):
            movement_type = movement_types[offset_index % len(movement_types)]
            quantity = _movement_quantity(movement_type, offset_index)
            rows.append(
                {
                    "movement_id": f"MOV-{movement_id:05d}",
                    "sku_id": sku_id,
                    "batch_id": batch_id,
                    "warehouse_id": "WH-001",
                    "location_id": location_id,
                    "movement_date": (REFERENCE_DATE - pd.Timedelta(days=days_ago)).strftime("%Y-%m-%d"),
                    "movement_type": movement_type,
                    "quantity": quantity,
                    "source_location_id": location_id if movement_type not in {"RECEIPT", "CUSTOMER_RETURN"} else "",
                    "destination_location_id": location_id if movement_type in {"RECEIPT", "PUTAWAY", "TRANSFER", "CUSTOMER_RETURN"} else "",
                    "reason_code": _reason_code(movement_type),
                    "related_po_id": f"PO-{1000 + movement_id}" if movement_type in {"RECEIPT", "PUTAWAY"} else "",
                    "related_order_id": f"ORD-{2000 + movement_id}" if movement_type in {"PICK", "SHIP", "DEMAND"} else "",
                }
            )
            movement_id += 1
    extra_rows = [
        ("CUSTOMER_RETURN", "SKU-GFT-010", 9),
        ("SUPPLIER_RETURN", "SKU-CHC-005", -6),
        ("SCRAP", "SKU-SUP-004", -12),
        ("EXPIRED", "SKU-SUN-003", -5),
    ]
    for movement_type, sku_id, quantity in extra_rows:
        sku_batches = batches[batches["sku_id"] == sku_id]
        batch_id = sku_batches.iloc[-1]["batch_id"] if not sku_batches.empty else ""
        location_id = sku_batches.iloc[-1]["location_id"] if not sku_batches.empty else ""
        rows.append(
            {
                "movement_id": f"MOV-{movement_id:05d}",
                "sku_id": sku_id,
                "batch_id": batch_id,
                "warehouse_id": "WH-001",
                "location_id": location_id,
                "movement_date": (REFERENCE_DATE - pd.Timedelta(days=6 + movement_id % 20)).strftime("%Y-%m-%d"),
                "movement_type": movement_type,
                "quantity": quantity,
                "source_location_id": location_id,
                "destination_location_id": "LOC-RT-001" if movement_type == "CUSTOMER_RETURN" else "LOC-QA-001",
                "reason_code": _reason_code(movement_type),
                "related_po_id": "",
                "related_order_id": "",
            }
        )
        movement_id += 1
    return pd.DataFrame(rows)


def _sample_warehouse_layout() -> pd.DataFrame:
    """Create one warehouse layout row with dock and aisle details."""
    length = DEFAULT_WAREHOUSE_LENGTH_M
    width = DEFAULT_WAREHOUSE_WIDTH_M
    aisle_width = 3.4
    return pd.DataFrame(
        [
            {
                "warehouse_id": "WH-001",
                "warehouse_name": "Main Inventory Control Warehouse",
                "warehouse_length_m": length,
                "warehouse_width_m": width,
                "total_floor_area_m2": length * width,
                "storage_area_m2": 1380,
                "receiving_area_m2": 180,
                "shipping_area_m2": 170,
                "crossdock_area_m2": 120,
                "returns_area_m2": 65,
                "aisle_width_m": aisle_width,
                "minimum_required_aisle_width_m": MIN_FORKLIFT_AISLE_WIDTH_M,
                "forklift_accessible": aisle_width >= MIN_FORKLIFT_AISLE_WIDTH_M,
                "dock_x": 4,
                "dock_y": 3,
                "entrance_x": 2,
                "entrance_y": 2,
                "exit_x": 58,
                "exit_y": 3,
            }
        ]
    )


def _sample_storage_locations() -> pd.DataFrame:
    """Create realistic warehouse storage locations across zones."""
    location_specs = [
        ("LOC-RC-001", "RECEIVING", "R1", "A", 1, 6, 5, 250, 35, 2400, "STAGING", True, False, False, True, True, True),
        ("LOC-PL-001", "PALLET_STORAGE", "P1", "A", 1, 14, 12, 500, 90, 9000, "PALLET_RACK", True, False, False, True, False, False),
        ("LOC-PL-002", "PALLET_STORAGE", "P2", "B", 2, 24, 16, 480, 84, 8500, "PALLET_RACK", True, False, False, True, False, False),
        ("LOC-CP-001", "CASE_PICKING", "C1", "A", 2, 10, 24, 360, 45, 3500, "CASE_FLOW", True, False, False, False, True, True),
        ("LOC-EP-001", "EACH_PICKING", "E1", "A", 3, 8, 30, 220, 20, 1200, "SHELVING", False, False, True, False, True, False),
        ("LOC-FP-001", "FAST_PICK", "F1", "A", 1, 12, 8, 420, 40, 2800, "FAST_PICK", True, False, False, False, True, False),
        ("LOC-SP-001", "SLOW_PICK", "S1", "C", 4, 42, 28, 180, 30, 1800, "SHELVING", False, False, False, False, True, False),
        ("LOC-BK-001", "BULK_STORAGE", "B1", "A", 1, 48, 20, 1000, 160, 15000, "BULK_FLOOR", True, False, False, True, False, False),
        ("LOC-RT-001", "RETURNS", "R2", "A", 1, 50, 6, 130, 18, 1300, "RETURNS_STAGING", True, False, False, False, True, True),
        ("LOC-QA-001", "QUARANTINE", "Q1", "A", 1, 54, 12, 90, 15, 900, "CAGE", False, True, True, False, True, True),
        ("LOC-SH-001", "SHIPPING", "S2", "A", 1, 56, 4, 260, 32, 2400, "STAGING", True, False, False, True, True, False),
        ("LOC-TC-001", "CASE_PICKING", "T1", "A", 1, 18, 30, 260, 28, 1800, "TEMP_CASE", True, True, False, False, True, True),
        ("LOC-TC-002", "PALLET_STORAGE", "T2", "B", 1, 30, 30, 340, 65, 5400, "TEMP_PALLET", True, True, False, True, True, True),
        ("LOC-TC-003", "EACH_PICKING", "T3", "C", 2, 20, 32, 190, 18, 1000, "TEMP_SHELF", False, True, False, False, True, True),
        ("LOC-SC-001", "EACH_PICKING", "SEC1", "A", 2, 34, 8, 160, 14, 900, "SECURE_SHELF", False, False, True, False, True, False),
        ("LOC-SC-002", "SLOW_PICK", "SEC2", "B", 3, 46, 32, 140, 16, 850, "SECURE_SHELF", False, False, True, False, True, False),
    ]
    rows = []
    for index, spec in enumerate(location_specs):
        (
            location_id,
            zone,
            aisle,
            rack,
            shelf_level,
            x_coord,
            y_coord,
            capacity_units,
            capacity_volume,
            capacity_weight,
            location_type,
            forklift,
            temp,
            secure,
            heavy,
            fragile,
            perishable,
        ) = spec
        used_ratio = 0.45 + (index % 5) * 0.11
        used_units = int(capacity_units * used_ratio)
        used_volume = round(capacity_volume * used_ratio, 2)
        used_weight = round(capacity_weight * used_ratio, 2)
        if location_id == "LOC-BK-001":
            used_units = capacity_units + 45
        rows.append(
            {
                "location_id": location_id,
                "warehouse_id": "WH-001",
                "zone": zone,
                "aisle": aisle,
                "rack": rack,
                "shelf_level": shelf_level,
                "x_coord": x_coord,
                "y_coord": y_coord,
                "distance_to_dock": _distance(x_coord, y_coord, 4, 3),
                "distance_to_exit": _distance(x_coord, y_coord, 58, 3),
                "distance_to_entrance": _distance(x_coord, y_coord, 2, 2),
                "capacity_units": capacity_units,
                "capacity_volume_m3": capacity_volume,
                "capacity_weight_kg": capacity_weight,
                "used_units": used_units,
                "used_volume_m3": used_volume,
                "used_weight_kg": used_weight,
                "free_units": capacity_units - used_units,
                "free_volume_m3": round(capacity_volume - used_volume, 2),
                "free_weight_kg": round(capacity_weight - used_weight, 2),
                "location_type": location_type,
                "forklift_accessible": forklift,
                "temperature_controlled": temp,
                "security_controlled": secure,
                "heavy_item_allowed": heavy,
                "fragile_item_allowed": fragile,
                "perishable_item_allowed": perishable,
            }
        )
    return pd.DataFrame(rows)


def _sample_sku_storage_requirements() -> pd.DataFrame:
    """Create SKU handling and storage requirements."""
    rows = [
        ("SKU-COF-001", 0.004, 0.35, True, False, False, False, False, "CASE", 12, 80, "FAST_PICK", 5),
        ("SKU-TEA-002", 0.003, 0.25, True, True, True, True, False, "CASE", 24, 60, "CASE_PICKING", 4),
        ("SKU-SUN-003", 0.002, 0.18, True, False, True, True, False, "EACH", 12, 80, "CASE_PICKING", 4),
        ("SKU-SUP-004", 0.006, 0.55, True, False, True, True, False, "CASE", 10, 50, "PALLET_STORAGE", 4),
        ("SKU-CHC-005", 0.0015, 0.09, False, True, True, True, False, "EACH", 24, 70, "EACH_PICKING", 3),
        ("SKU-BBQ-006", 0.025, 2.4, True, False, False, False, False, "PALLET", 6, 40, "BULK_STORAGE", 3),
        ("SKU-UMR-007", 0.03, 1.1, True, False, False, False, False, "EACH", 4, 30, "SLOW_PICK", 3),
        ("SKU-BAT-008", 0.002, 0.22, True, False, False, False, True, "EACH", 20, 100, "EACH_PICKING", 4),
        ("SKU-FIL-009", 0.018, 1.8, True, False, False, False, False, "CASE", 8, 36, "EACH_PICKING", 3),
        ("SKU-GFT-010", 0.015, 0.65, False, True, False, False, True, "EACH", 6, 48, "SLOW_PICK", 2),
    ]
    output = []
    for row in rows:
        (
            sku_id,
            volume,
            weight,
            stackable,
            fragile,
            perishable,
            temperature_required,
            security_required,
            handling_unit,
            units_per_case,
            cases_per_pallet,
            preferred_zone,
            max_stack_height,
        ) = row
        output.append(
            {
                "sku_id": sku_id,
                "unit_volume_m3": volume,
                "unit_weight_kg": weight,
                "stackable": stackable,
                "fragile": fragile,
                "perishable": perishable,
                "temperature_required": temperature_required,
                "security_required": security_required,
                "handling_unit": handling_unit,
                "units_per_case": units_per_case,
                "cases_per_pallet": cases_per_pallet,
                "handling_cost_per_unit": HANDLING_UNIT_COSTS["EACH"],
                "handling_cost_per_case": HANDLING_UNIT_COSTS["CASE"],
                "handling_cost_per_pallet": HANDLING_UNIT_COSTS["PALLET"],
                "preferred_zone": preferred_zone,
                "max_stack_height": max_stack_height,
                "heavy_low_storage_required": weight > 1.5,
                "expiry_tracking_required": perishable,
                "fefo_required": perishable,
            }
        )
    return pd.DataFrame(output)


def _expiry_details(sku_id: str, batch_index: int, perishable: bool):
    """Return expiry date, status, and shelf life for a batch."""
    if not perishable:
        return None, "FRESH", 0
    offsets = [-6, 12, 46, 140]
    expiry_date = REFERENCE_DATE + pd.Timedelta(days=offsets[batch_index % len(offsets)])
    days_until_expiry = (expiry_date - REFERENCE_DATE).days
    if days_until_expiry < 0:
        status = "EXPIRED"
    elif days_until_expiry <= 30:
        status = "NEAR_EXPIRY"
    else:
        status = "FRESH"
    if sku_id == "SKU-CHC-005" and batch_index == 1:
        status = "HOLD"
    if sku_id == "SKU-SUP-004" and batch_index == 2:
        status = "QUARANTINE"
    return expiry_date, status, 180


def _push_pull_role(sku_id: str) -> str:
    """Return a future planning role for a SKU."""
    roles = {
        "SKU-FIL-009": "ASSEMBLE_TO_ORDER_COMPONENT",
        "SKU-SUP-004": "MAKE_TO_STOCK_ITEM",
        "SKU-BBQ-006": "FINISHED_GOOD_BUFFER",
        "SKU-BAT-008": "RAW_MATERIAL_BUFFER",
    }
    return roles.get(sku_id, "MAKE_TO_STOCK_ITEM")


def _movement_quantity(movement_type: str, index: int) -> int:
    """Return realistic positive or negative movement quantity."""
    base = 12 + index * 4
    if movement_type in {"RECEIPT", "PUTAWAY", "CUSTOMER_RETURN"}:
        return base
    if movement_type == "ADJUSTMENT":
        return -3 if index % 2 else 4
    return -base


def _reason_code(movement_type: str) -> str:
    """Return a reason code for a movement type."""
    reasons = {
        "RECEIPT": "PO_RECEIPT",
        "PUTAWAY": "STANDARD_PUTAWAY",
        "PICK": "CUSTOMER_PICK",
        "SHIP": "CUSTOMER_SHIPMENT",
        "DEMAND": "DEMAND_CONSUMPTION",
        "TRANSFER": "ZONE_TRANSFER",
        "ADJUSTMENT": "CYCLE_COUNT",
        "CUSTOMER_RETURN": "CUSTOMER_RETURN",
        "SUPPLIER_RETURN": "SUPPLIER_RETURN",
        "SCRAP": "DAMAGED_STOCK",
        "EXPIRED": "EXPIRED_STOCK",
    }
    return reasons.get(movement_type, "UNKNOWN")


def _distance(x1, y1, x2, y2) -> float:
    """Return Euclidean travel distance rounded to two decimals."""
    return round(math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2), 2)
