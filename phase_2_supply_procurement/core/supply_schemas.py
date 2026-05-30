"""Schema definitions and validation helpers for Phase 2 supply data."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TableSchema:
    """Required and optional columns for a supply table."""

    name: str
    required_columns: list[str]
    optional_columns: list[str]


SUPPLIERS_SCHEMA = TableSchema(
    name="suppliers",
    required_columns=[
        "supplier_id",
        "supplier_name",
        "country",
        "status",
        "base_reliability_score",
        "payment_terms",
        "priority_class",
    ],
    optional_columns=[],
)

SUPPLIER_SKU_SCHEMA = TableSchema(
    name="supplier_sku",
    required_columns=[
        "sku_id",
        "supplier_id",
        "unit_cost",
        "moq",
        "batch_size",
        "lead_time_mean_days",
        "lead_time_std_days",
        "yield_rate",
        "defect_rate",
        "delay_probability",
        "partial_delivery_rate",
        "supplier_priority",
        "is_primary_supplier",
    ],
    optional_columns=[
        "fixed_order_cost",
        "delivery_cost",
        "cost_per_late_day",
        "partial_delivery_penalty",
        "quality_rejection_cost_per_unit",
    ],
)

PURCHASE_ORDERS_SCHEMA = TableSchema(
    name="purchase_orders",
    required_columns=[
        "po_id",
        "sku_id",
        "supplier_id",
        "order_date",
        "ordered_quantity",
        "promised_delivery_date",
        "expected_unit_cost",
    ],
    optional_columns=[],
)

RECEIPTS_SCHEMA = TableSchema(
    name="receipts",
    required_columns=[
        "receipt_id",
        "po_id",
        "receipt_date",
        "received_quantity",
        "accepted_quantity",
        "rejected_quantity",
        "delay_days",
        "partial_delivery_flag",
        "quality_issue_flag",
    ],
    optional_columns=[],
)


def validate_schema(df: pd.DataFrame, schema: TableSchema) -> None:
    """Raise ValueError if a dataframe is missing required columns."""
    missing = [column for column in schema.required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"{schema.name} is missing required columns: {', '.join(missing)}")
