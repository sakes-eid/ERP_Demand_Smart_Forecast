"""Table schema definitions and validation helpers."""

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class TableSchema:
    """Describes required and optional columns for an input table."""

    name: str
    required_columns: list[str]
    optional_columns: list[str]

    @property
    def allowed_columns(self) -> list[str]:
        """Return every column recognized by this schema."""
        return self.required_columns + self.optional_columns


PRODUCTS_SCHEMA = TableSchema(
    name="products",
    required_columns=["sku_id", "sku_name", "category", "unit", "status"],
    optional_columns=["subcategory", "launch_date", "end_date", "is_perishable", "shelf_life_days"],
)

DEMAND_SCHEMA = TableSchema(
    name="demand_history_raw",
    required_columns=["date", "sku_id", "quantity_demanded"],
    optional_columns=["location_id", "channel", "sales_value", "event_label", "notes"],
)

EVENTS_SCHEMA = TableSchema(
    name="events",
    required_columns=["event_name", "event_type", "event_start_date", "event_end_date"],
    optional_columns=[
        "sku_id",
        "location_id",
        "before_window_days",
        "after_window_days",
        "event_intensity",
        "description",
    ],
)


def missing_required_columns(df: pd.DataFrame, schema: TableSchema) -> list[str]:
    """Return required schema columns that are absent from a dataframe."""
    return [column for column in schema.required_columns if column not in df.columns]


def validate_schema(df: pd.DataFrame, schema: TableSchema) -> None:
    """Raise ValueError when a dataframe is missing required columns."""
    missing = missing_required_columns(df, schema)
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"{schema.name} is missing required columns: {missing_text}")


def validate_schemas(tables: Iterable[tuple[pd.DataFrame, TableSchema]]) -> None:
    """Validate multiple dataframe/schema pairs."""
    for df, schema in tables:
        validate_schema(df, schema)

