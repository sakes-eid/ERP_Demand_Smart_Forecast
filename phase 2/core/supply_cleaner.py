"""Load, clean, and validate Phase 2 supply input data."""

import pandas as pd

from config import PURCHASE_ORDERS_FILE, RECEIPTS_FILE, SUPPLIER_SKU_FILE, SUPPLIERS_FILE
from core.supply_schemas import (
    PURCHASE_ORDERS_SCHEMA,
    RECEIPTS_SCHEMA,
    SUPPLIER_SKU_SCHEMA,
    SUPPLIERS_SCHEMA,
    validate_schema,
)

SUPPLIER_SKU_COST_DEFAULTS = {
    "fixed_order_cost": 50,
    "delivery_cost": 100,
    "cost_per_late_day": 25,
    "partial_delivery_penalty": 100,
    "quality_rejection_cost_per_unit": 5,
}


def load_supply_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all Phase 2 supply CSV inputs and validate required columns."""
    suppliers = pd.read_csv(SUPPLIERS_FILE)
    supplier_sku = pd.read_csv(SUPPLIER_SKU_FILE)
    purchase_orders = pd.read_csv(PURCHASE_ORDERS_FILE)
    receipts = pd.read_csv(RECEIPTS_FILE)

    validate_schema(suppliers, SUPPLIERS_SCHEMA)
    validate_schema(supplier_sku, SUPPLIER_SKU_SCHEMA)
    validate_schema(purchase_orders, PURCHASE_ORDERS_SCHEMA)
    validate_schema(receipts, RECEIPTS_SCHEMA)

    return suppliers, supplier_sku, purchase_orders, receipts


def clean_suppliers(suppliers: pd.DataFrame) -> pd.DataFrame:
    """Clean supplier master records."""
    cleaned = suppliers.copy()
    cleaned["supplier_id"] = cleaned["supplier_id"].astype(str).str.strip()
    cleaned["supplier_name"] = cleaned["supplier_name"].astype(str).str.strip()
    cleaned["country"] = cleaned["country"].astype(str).str.strip()
    cleaned["status"] = cleaned["status"].astype(str).str.strip().str.lower()
    cleaned["payment_terms"] = cleaned["payment_terms"].astype(str).str.strip()
    cleaned["priority_class"] = cleaned["priority_class"].astype(str).str.strip().str.upper()
    cleaned["base_reliability_score"] = pd.to_numeric(cleaned["base_reliability_score"], errors="coerce")
    cleaned["invalid_reliability_flag"] = ~cleaned["base_reliability_score"].between(0, 1)
    return cleaned.drop_duplicates("supplier_id").reset_index(drop=True)


def clean_supplier_sku(supplier_sku: pd.DataFrame, suppliers: pd.DataFrame, known_skus: set[str]) -> pd.DataFrame:
    """Clean supplier-SKU links and flag invalid references/ranges."""
    cleaned = supplier_sku.copy()
    cleaned["sku_id"] = cleaned["sku_id"].astype(str).str.strip()
    cleaned["supplier_id"] = cleaned["supplier_id"].astype(str).str.strip()

    numeric_columns = [
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
        "fixed_order_cost",
        "delivery_cost",
        "cost_per_late_day",
        "partial_delivery_penalty",
        "quality_rejection_cost_per_unit",
    ]
    for column, default_value in SUPPLIER_SKU_COST_DEFAULTS.items():
        if column not in cleaned.columns:
            cleaned[column] = default_value

    for column in numeric_columns:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
        if column in SUPPLIER_SKU_COST_DEFAULTS:
            cleaned[column] = cleaned[column].fillna(SUPPLIER_SKU_COST_DEFAULTS[column])

    cleaned["is_primary_supplier"] = cleaned["is_primary_supplier"].astype(str).str.lower().isin(["true", "1", "yes"])
    supplier_ids = set(suppliers["supplier_id"])
    cleaned["unknown_supplier_flag"] = ~cleaned["supplier_id"].isin(supplier_ids)
    cleaned["unknown_sku_flag"] = ~cleaned["sku_id"].isin(known_skus) if known_skus else False
    cleaned["negative_cost_flag"] = cleaned["unit_cost"] < 0
    cleaned["negative_procurement_cost_flag"] = (
        (cleaned["fixed_order_cost"] < 0)
        | (cleaned["delivery_cost"] < 0)
        | (cleaned["cost_per_late_day"] < 0)
        | (cleaned["partial_delivery_penalty"] < 0)
        | (cleaned["quality_rejection_cost_per_unit"] < 0)
    )
    cleaned["invalid_quantity_flag"] = (cleaned["moq"] <= 0) | (cleaned["batch_size"] <= 0)
    cleaned["invalid_yield_rate_flag"] = ~cleaned["yield_rate"].between(0, 1) | (cleaned["yield_rate"] <= 0)
    cleaned["invalid_defect_rate_flag"] = ~cleaned["defect_rate"].between(0, 1)
    cleaned["invalid_delay_probability_flag"] = ~cleaned["delay_probability"].between(0, 1)
    cleaned["invalid_partial_delivery_rate_flag"] = ~cleaned["partial_delivery_rate"].between(0, 1)
    return cleaned.reset_index(drop=True)


def clean_purchase_orders(
    purchase_orders: pd.DataFrame,
    suppliers: pd.DataFrame,
    known_skus: set[str],
) -> pd.DataFrame:
    """Clean purchase orders and flag invalid references/values."""
    cleaned = purchase_orders.copy()
    cleaned["po_id"] = cleaned["po_id"].astype(str).str.strip()
    cleaned["sku_id"] = cleaned["sku_id"].astype(str).str.strip()
    cleaned["supplier_id"] = cleaned["supplier_id"].astype(str).str.strip()
    cleaned["order_date"] = pd.to_datetime(cleaned["order_date"], errors="coerce")
    cleaned["promised_delivery_date"] = pd.to_datetime(cleaned["promised_delivery_date"], errors="coerce")
    cleaned["ordered_quantity"] = pd.to_numeric(cleaned["ordered_quantity"], errors="coerce")
    cleaned["expected_unit_cost"] = pd.to_numeric(cleaned["expected_unit_cost"], errors="coerce")

    supplier_ids = set(suppliers["supplier_id"])
    cleaned["unknown_supplier_flag"] = ~cleaned["supplier_id"].isin(supplier_ids)
    cleaned["unknown_sku_flag"] = ~cleaned["sku_id"].isin(known_skus) if known_skus else False
    cleaned["negative_quantity_flag"] = cleaned["ordered_quantity"] < 0
    cleaned["negative_cost_flag"] = cleaned["expected_unit_cost"] < 0
    return cleaned.reset_index(drop=True)


def clean_receipts(receipts: pd.DataFrame, purchase_orders: pd.DataFrame) -> pd.DataFrame:
    """Clean receipts and flag invalid purchase-order links/quantities."""
    cleaned = receipts.copy()
    cleaned["receipt_id"] = cleaned["receipt_id"].astype(str).str.strip()
    cleaned["po_id"] = cleaned["po_id"].astype(str).str.strip()
    cleaned["receipt_date"] = pd.to_datetime(cleaned["receipt_date"], errors="coerce")

    numeric_columns = [
        "received_quantity",
        "accepted_quantity",
        "rejected_quantity",
        "delay_days",
        "partial_delivery_flag",
        "quality_issue_flag",
    ]
    for column in numeric_columns:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    po_ids = set(purchase_orders["po_id"])
    cleaned["unknown_po_flag"] = ~cleaned["po_id"].isin(po_ids)
    cleaned["negative_quantity_flag"] = (
        (cleaned["received_quantity"] < 0)
        | (cleaned["accepted_quantity"] < 0)
        | (cleaned["rejected_quantity"] < 0)
    )
    return cleaned.reset_index(drop=True)


def get_known_skus_from_phase1() -> set[str]:
    """Load known SKUs from Phase 1 outputs or return an empty set."""
    from config import PHASE_1_OUTPUT_DIR

    for filename in ("products_cleaned.csv", "products_clean.csv"):
        path = PHASE_1_OUTPUT_DIR / filename
        if path.exists():
            products = pd.read_csv(path)
            if "sku_id" in products.columns:
                return set(products["sku_id"].astype(str).str.strip())
    return set()
