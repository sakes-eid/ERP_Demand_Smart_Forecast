"""CSV loading and example data creation utilities."""

from pathlib import Path

import pandas as pd

from config import DEMAND_FILE, EVENTS_FILE, OUTPUT_DIR, PRODUCTS_FILE
from core.schemas import DEMAND_SCHEMA, EVENTS_SCHEMA, PRODUCTS_SCHEMA, validate_schema


def ensure_directories() -> None:
    """Create input and output directories used by the Phase 1 pipeline."""
    PRODUCTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_example_csv_files() -> None:
    """Create minimal example CSV files when input files are missing."""
    ensure_directories()
    _write_if_missing(PRODUCTS_FILE, _example_products())
    _write_if_missing(DEMAND_FILE, _example_demand())
    _write_if_missing(EVENTS_FILE, _example_events())


def load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV file into a dataframe."""
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    return pd.read_csv(path)


def load_input_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and validate products, demand history, and events."""
    products = load_csv(PRODUCTS_FILE)
    demand = load_csv(DEMAND_FILE)
    events = load_csv(EVENTS_FILE)

    validate_schema(products, PRODUCTS_SCHEMA)
    validate_schema(demand, DEMAND_SCHEMA)
    validate_schema(events, EVENTS_SCHEMA)

    return products, demand, events


def export_csv(df: pd.DataFrame, path: Path) -> None:
    """Export a dataframe to CSV without an index column."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _write_if_missing(path: Path, df: pd.DataFrame) -> None:
    """Write an example dataframe only when the target path does not exist."""
    if not path.exists():
        df.to_csv(path, index=False)


def _example_products() -> pd.DataFrame:
    """Return a small product catalog for local smoke runs."""
    return pd.DataFrame(
        [
            {
                "sku_id": "SKU-001",
                "sku_name": "Basic Widget",
                "category": "Hardware",
                "unit": "each",
                "status": "active",
                "subcategory": "Widgets",
                "launch_date": "2026-01-01",
                "end_date": "",
                "is_perishable": False,
                "shelf_life_days": "",
            },
            {
                "sku_id": "SKU-002",
                "sku_name": "Premium Widget",
                "category": "Hardware",
                "unit": "each",
                "status": "active",
                "subcategory": "Widgets",
                "launch_date": "2026-01-01",
                "end_date": "",
                "is_perishable": False,
                "shelf_life_days": "",
            },
            {
                "sku_id": "SKU-BIKE-ROAD-001",
                "sku_name": "Road Bike",
                "category": "Bicycles",
                "unit": "each",
                "status": "active",
                "subcategory": "Road Bikes",
                "launch_date": "2026-01-01",
                "end_date": "",
                "is_perishable": False,
                "shelf_life_days": "",
            },
            {
                "sku_id": "SKU-BIKE-MT-001",
                "sku_name": "Mountain Bike",
                "category": "Bicycles",
                "unit": "each",
                "status": "active",
                "subcategory": "Mountain Bikes",
                "launch_date": "2026-01-01",
                "end_date": "",
                "is_perishable": False,
                "shelf_life_days": "",
            },
        ]
    )


def _example_demand() -> pd.DataFrame:
    """Return demand history with one gap and one anomaly for validation."""
    rows = [
        {"date": "2026-01-01", "sku_id": "SKU-001", "quantity_demanded": 12},
        {"date": "2026-01-02", "sku_id": "SKU-001", "quantity_demanded": 14},
        {"date": "2026-01-04", "sku_id": "SKU-001", "quantity_demanded": 75},
        {"date": "2026-01-01", "sku_id": "SKU-002", "quantity_demanded": 7},
        {"date": "2026-01-02", "sku_id": "SKU-002", "quantity_demanded": -2},
        {"date": "2026-01-03", "sku_id": "SKU-002", "quantity_demanded": 8},
    ]
    for index, date in enumerate(pd.date_range("2026-01-01", periods=60, freq="D")):
        rows.extend(
            [
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "sku_id": "SKU-BIKE-ROAD-001",
                    "quantity_demanded": 8 + (index % 7) + (2 if date.dayofweek >= 5 else 0),
                },
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "sku_id": "SKU-BIKE-MT-001",
                    "quantity_demanded": 6 + (index % 6) + (3 if date.dayofweek >= 5 else 0),
                },
            ]
        )
    return pd.DataFrame(rows)


def _example_events() -> pd.DataFrame:
    """Return a small calendar of business events."""
    return pd.DataFrame(
        [
            {
                "event_name": "New Year Promo",
                "event_type": "promotion",
                "event_start_date": "2026-01-01",
                "event_end_date": "2026-01-03",
                "sku_id": "SKU-001",
                "location_id": "",
                "before_window_days": 2,
                "after_window_days": 2,
                "event_intensity": 0.8,
                "description": "Introductory promotion",
            }
        ]
    )
