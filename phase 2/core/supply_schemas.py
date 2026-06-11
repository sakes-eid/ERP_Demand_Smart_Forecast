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
    optional_columns=[
        "supplier_status",
        "supplier_country",
        "supplier_region",
        "supplier_currency",
        "accepts_returns",
        "return_window_days",
        "return_deduction_rate",
        "return_shipping_cost",
        "return_handling_fee",
        "return_minimum_quantity",
        "returns_allowed_for_near_expiry",
        "returns_allowed_for_expired",
        "return_authorization_required",
        "return_policy_notes",
        "expedite_available",
        "expedite_lead_time_days",
        "expedite_fixed_fee",
        "expedite_cost_rate",
        "expedite_capacity_limit",
        "expedite_reliability",
        "expedite_minimum_quantity",
        "expedite_policy_notes",
        "split_delivery_available",
        "minimum_split_quantity",
        "maximum_split_shipments",
        "split_delivery_fixed_fee",
        "split_delivery_variable_rate",
        "first_shipment_lead_time_days",
        "remaining_shipment_lead_time_days",
        "partial_delivery_reliability",
        "split_delivery_policy_notes",
        "supplier_capacity_per_period",
        "available_capacity",
        "capacity_utilization",
        "order_acceptance_probability",
        "capacity_review_required",
        "capacity_notes",
        "freight_cost_rate",
        "handling_cost_rate",
        "insurance_cost_rate",
        "customs_cost_rate",
        "payment_terms_days",
        "early_payment_discount_rate",
        "late_payment_penalty_rate",
        "minimum_order_value",
    ],
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
        "unit_price",
        "currency",
        "order_multiple",
        "standard_lead_time_days",
        "minimum_lead_time_days",
        "maximum_lead_time_days",
        "lead_time_variability_days",
        "supplier_sku_capacity_per_period",
        "supplier_sku_available_capacity",
        "max_order_quantity",
        "allocation_limit_by_sku",
        "price_break_1_quantity",
        "price_break_1_unit_price",
        "price_break_2_quantity",
        "price_break_2_unit_price",
        "price_break_3_quantity",
        "price_break_3_unit_price",
        "return_eligible",
        "expedite_eligible",
        "split_delivery_eligible",
        "preferred_supplier_flag",
        "backup_supplier_flag",
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
