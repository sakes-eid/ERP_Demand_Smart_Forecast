"""Generate realistic Phase 2 supply input data when CSV files are missing."""

import pandas as pd

from config import (
    BACKORDER_ALLOCATIONS_FILE,
    BACKORDERS_FILE,
    DATA_DIR,
    PURCHASE_ORDERS_FILE,
    RECEIPTS_FILE,
    SUPPLIER_SKU_FILE,
    SUPPLIERS_FILE,
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

SUPPLIER_PROFILES = {
    "SUP-001": {
        "name": "Budget Global Export",
        "country": "India",
        "status": "active",
        "base_reliability_score": 0.58,
        "payment_terms": "Net 60",
        "priority_class": "C",
        "type": "cheap_unreliable",
        "cost_factor": 0.78,
        "moq_factor": 1.35,
        "batch_factor": 1.45,
        "lead_time_mean": 15,
        "lead_time_std": 6.2,
        "yield_rate": 0.86,
        "delay_probability": 0.43,
        "partial_delivery_rate": 0.28,
        "fixed_order_cost": 65,
        "delivery_cost": 180,
        "cost_per_late_day": 55,
        "partial_delivery_penalty": 260,
        "quality_rejection_cost_per_unit": 9,
    },
    "SUP-002": {
        "name": "EuroSource Precision",
        "country": "Germany",
        "status": "active",
        "base_reliability_score": 0.96,
        "payment_terms": "Net 30",
        "priority_class": "A",
        "type": "expensive_reliable",
        "cost_factor": 1.34,
        "moq_factor": 0.95,
        "batch_factor": 1.00,
        "lead_time_mean": 10,
        "lead_time_std": 1.4,
        "yield_rate": 0.985,
        "delay_probability": 0.045,
        "partial_delivery_rate": 0.025,
        "fixed_order_cost": 95,
        "delivery_cost": 130,
        "cost_per_late_day": 18,
        "partial_delivery_penalty": 65,
        "quality_rejection_cost_per_unit": 4,
    },
    "SUP-003": {
        "name": "Rapid Local Supply",
        "country": "Lebanon",
        "status": "active",
        "base_reliability_score": 0.74,
        "payment_terms": "Net 15",
        "priority_class": "B",
        "type": "fast_lower_quality",
        "cost_factor": 1.06,
        "moq_factor": 0.65,
        "batch_factor": 0.65,
        "lead_time_mean": 4,
        "lead_time_std": 1.1,
        "yield_rate": 0.88,
        "delay_probability": 0.12,
        "partial_delivery_rate": 0.08,
        "fixed_order_cost": 55,
        "delivery_cost": 90,
        "cost_per_late_day": 30,
        "partial_delivery_penalty": 120,
        "quality_rejection_cost_per_unit": 14,
    },
    "SUP-004": {
        "name": "Nordic Stable Logistics",
        "country": "Denmark",
        "status": "active",
        "base_reliability_score": 0.92,
        "payment_terms": "Net 45",
        "priority_class": "A",
        "type": "slow_stable",
        "cost_factor": 1.12,
        "moq_factor": 1.05,
        "batch_factor": 1.10,
        "lead_time_mean": 22,
        "lead_time_std": 2.0,
        "yield_rate": 0.965,
        "delay_probability": 0.07,
        "partial_delivery_rate": 0.04,
        "fixed_order_cost": 85,
        "delivery_cost": 75,
        "cost_per_late_day": 20,
        "partial_delivery_penalty": 80,
        "quality_rejection_cost_per_unit": 5,
    },
    "SUP-005": {
        "name": "Fallback Trade Partners",
        "country": "Turkey",
        "status": "probation",
        "base_reliability_score": 0.64,
        "payment_terms": "Net 45",
        "priority_class": "C",
        "type": "risky_backup",
        "cost_factor": 0.98,
        "moq_factor": 0.90,
        "batch_factor": 0.95,
        "lead_time_mean": 13,
        "lead_time_std": 7.8,
        "yield_rate": 0.91,
        "delay_probability": 0.36,
        "partial_delivery_rate": 0.22,
        "fixed_order_cost": 70,
        "delivery_cost": 150,
        "cost_per_late_day": 45,
        "partial_delivery_penalty": 220,
        "quality_rejection_cost_per_unit": 8,
    },
    "SUP-006": {
        "name": "MegaBulk Manufacturing",
        "country": "China",
        "status": "active",
        "base_reliability_score": 0.79,
        "payment_terms": "Net 75",
        "priority_class": "B",
        "type": "bulk_supplier",
        "cost_factor": 0.72,
        "moq_factor": 2.80,
        "batch_factor": 3.20,
        "lead_time_mean": 16,
        "lead_time_std": 4.2,
        "yield_rate": 0.935,
        "delay_probability": 0.24,
        "partial_delivery_rate": 0.10,
        "fixed_order_cost": 180,
        "delivery_cost": 70,
        "cost_per_late_day": 28,
        "partial_delivery_penalty": 140,
        "quality_rejection_cost_per_unit": 6,
    },
    "SUP-007": {
        "name": "FlexiSource Express",
        "country": "Italy",
        "status": "active",
        "base_reliability_score": 0.84,
        "payment_terms": "Net 30",
        "priority_class": "B",
        "type": "flexible_supplier",
        "cost_factor": 1.22,
        "moq_factor": 0.45,
        "batch_factor": 0.45,
        "lead_time_mean": 7,
        "lead_time_std": 2.4,
        "yield_rate": 0.945,
        "delay_probability": 0.14,
        "partial_delivery_rate": 0.06,
        "fixed_order_cost": 35,
        "delivery_cost": 110,
        "cost_per_late_day": 24,
        "partial_delivery_penalty": 95,
        "quality_rejection_cost_per_unit": 6,
    },
}

SKU_SUPPLIER_MIX = [
    ["SUP-001", "SUP-002", "SUP-003", "SUP-006"],
    ["SUP-001", "SUP-002", "SUP-005", "SUP-007"],
    ["SUP-002", "SUP-003", "SUP-004", "SUP-005"],
    ["SUP-001", "SUP-004", "SUP-006", "SUP-007"],
    ["SUP-002", "SUP-003", "SUP-005", "SUP-006"],
    ["SUP-001", "SUP-004", "SUP-005", "SUP-006"],
    ["SUP-002", "SUP-003", "SUP-004", "SUP-007"],
    ["SUP-001", "SUP-005", "SUP-006", "SUP-007"],
    ["SUP-002", "SUP-004", "SUP-005", "SUP-006"],
    ["SUP-001", "SUP-003", "SUP-006", "SUP-007"],
]

PREVIOUS_SAMPLE_SUPPLIERS = {
    "Cedar Trading Co.",
    "Levant Components",
    "EuroSource GmbH",
    "Asia Pacific Supply",
    "MedPack Distribution",
    "Budget Global Export",
}

CURRENT_SAMPLE_SUPPLIERS = {profile["name"] for profile in SUPPLIER_PROFILES.values()}

COST_COLUMNS = {
    "fixed_order_cost",
    "delivery_cost",
    "cost_per_late_day",
    "partial_delivery_penalty",
    "quality_rejection_cost_per_unit",
}

SUPPLIER_CAPABILITY_COLUMNS = {
    "supplier_region",
    "supplier_currency",
    "accepts_returns",
    "return_window_days",
    "expedite_available",
    "split_delivery_available",
    "supplier_capacity_per_period",
    "freight_cost_rate",
    "payment_terms_days",
}

SUPPLIER_SKU_CAPABILITY_COLUMNS = {
    "unit_price",
    "currency",
    "order_multiple",
    "standard_lead_time_days",
    "supplier_sku_available_capacity",
    "price_break_1_quantity",
    "return_eligible",
    "expedite_eligible",
    "split_delivery_eligible",
    "preferred_supplier_flag",
    "backup_supplier_flag",
}

SUPPLIER_TREND_DEMO_PLAN = {
    "SUP-001": {"trend": "improving", "baseline_orders": 18, "recent_orders": 8},
    "SUP-002": {"trend": "healthy", "baseline_orders": 18, "recent_orders": 8},
    "SUP-003": {"trend": "mixed", "baseline_orders": 16, "recent_orders": 7},
    "SUP-004": {"trend": "healthy", "baseline_orders": 16, "recent_orders": 8},
    "SUP-005": {"trend": "watchlist", "baseline_orders": 18, "recent_orders": 8},
    "SUP-006": {"trend": "watchlist", "baseline_orders": 16, "recent_orders": 7},
    "SUP-007": {"trend": "insufficient", "baseline_orders": 2, "recent_orders": 1},
}

BASELINE_PROMISED_START = pd.Timestamp("2026-03-07")
BASELINE_PROMISED_END = pd.Timestamp("2026-05-19")
RECENT_PROMISED_START = pd.Timestamp("2026-06-02")
RECENT_PROMISED_END = pd.Timestamp("2026-06-20")


def create_sample_supply_files() -> None:
    """Create sample supply CSVs when missing or old bundled samples are present."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    files_existed_before = _all_input_files_exist()
    refresh_samples = _should_refresh_sample_files()

    suppliers = _sample_suppliers()
    supplier_sku = _sample_supplier_sku()
    purchase_orders = _sample_purchase_orders(supplier_sku)
    receipts = _sample_receipts(purchase_orders, supplier_sku)
    backorders = _sample_backorders(supplier_sku)
    allocations = _sample_backorder_allocations(backorders)

    wrote_any_file = any(
        [
            _write_if_missing_or_refresh(SUPPLIERS_FILE, suppliers, refresh_samples),
            _write_if_missing_or_refresh(SUPPLIER_SKU_FILE, supplier_sku, refresh_samples),
            _write_if_missing_or_refresh(PURCHASE_ORDERS_FILE, purchase_orders, refresh_samples),
            _write_if_missing_or_refresh(RECEIPTS_FILE, receipts, refresh_samples),
            _write_if_missing_or_refresh(BACKORDERS_FILE, backorders, refresh_samples),
            _write_if_missing_or_refresh(BACKORDER_ALLOCATIONS_FILE, allocations, refresh_samples),
        ]
    )
    _print_generator_status(files_existed_before, refresh_samples, wrote_any_file)


def _should_refresh_sample_files() -> bool:
    """Return True only for generated demo supplier files that need a safe refresh."""
    if not SUPPLIERS_FILE.exists():
        return False
    try:
        suppliers = pd.read_csv(SUPPLIERS_FILE)
    except Exception:
        return False
    if "supplier_name" not in suppliers.columns:
        return False
    supplier_names = set(suppliers["supplier_name"].astype(str))
    is_known_sample = supplier_names.issubset(PREVIOUS_SAMPLE_SUPPLIERS | CURRENT_SAMPLE_SUPPLIERS)
    return is_known_sample and (
        _suppliers_missing_capability_columns()
        or _supplier_sku_missing_cost_columns()
        or _supplier_sku_missing_capability_columns()
        or _purchase_orders_need_trend_refresh()
        or not BACKORDERS_FILE.exists()
        or not BACKORDER_ALLOCATIONS_FILE.exists()
    )


def _suppliers_missing_capability_columns() -> bool:
    """Return True when the supplier sample lacks capability fields."""
    if not SUPPLIERS_FILE.exists():
        return True
    try:
        suppliers = pd.read_csv(SUPPLIERS_FILE, nrows=1)
    except Exception:
        return False
    return not SUPPLIER_CAPABILITY_COLUMNS.issubset(set(suppliers.columns))


def _supplier_sku_missing_cost_columns() -> bool:
    """Return True when the generated supplier-SKU sample lacks new cost fields."""
    if not SUPPLIER_SKU_FILE.exists():
        return True
    try:
        supplier_sku = pd.read_csv(SUPPLIER_SKU_FILE, nrows=1)
    except Exception:
        return False
    return not COST_COLUMNS.issubset(set(supplier_sku.columns))


def _supplier_sku_missing_capability_columns() -> bool:
    """Return True when the generated supplier-SKU sample lacks capability fields."""
    if not SUPPLIER_SKU_FILE.exists():
        return True
    try:
        supplier_sku = pd.read_csv(SUPPLIER_SKU_FILE, nrows=1)
    except Exception:
        return False
    return not SUPPLIER_SKU_CAPABILITY_COLUMNS.issubset(set(supplier_sku.columns))


def _purchase_orders_need_trend_refresh() -> bool:
    """Return True when known demo purchase history is too shallow for trend demos."""
    if not PURCHASE_ORDERS_FILE.exists() or not RECEIPTS_FILE.exists():
        return True
    try:
        purchase_orders = pd.read_csv(PURCHASE_ORDERS_FILE, nrows=200)
    except Exception:
        return False
    return len(purchase_orders) != _expected_demo_purchase_order_count()


def _expected_demo_purchase_order_count() -> int:
    """Return the planned number of demo purchase orders."""
    return sum(
        plan["baseline_orders"] + plan["recent_orders"]
        for plan in SUPPLIER_TREND_DEMO_PLAN.values()
    )


def _all_input_files_exist() -> bool:
    """Return True when all supply input files are present."""
    return all(
        path.exists()
        for path in [
            SUPPLIERS_FILE,
            SUPPLIER_SKU_FILE,
            PURCHASE_ORDERS_FILE,
            RECEIPTS_FILE,
            BACKORDERS_FILE,
            BACKORDER_ALLOCATIONS_FILE,
        ]
    )


def _write_if_missing_or_refresh(path, df: pd.DataFrame, refresh: bool) -> bool:
    """Persist sample data when missing or refreshing old generated samples."""
    if refresh or not path.exists():
        try:
            df.to_csv(path, index=False)
            return True
        except PermissionError:
            print(f"Warning: could not refresh sample file because it is open or locked: {path}")
    return False


def _print_generator_status(files_existed_before: bool, refresh_samples: bool, wrote_any_file: bool) -> None:
    """Print a clear, non-destructive generator status message."""
    if refresh_samples and wrote_any_file:
        print("Detected shallow demo data and regenerated richer demo history.")
        return
    if not files_existed_before and wrote_any_file:
        print("Generated realistic Phase 2 supplier, supplier-SKU, PO, and receipt demo data.")
        return
    print("Sample supply input files already exist. Using existing files.")
    print("To regenerate demo data manually, close open CSV files, delete the files in data/, and rerun python main.py.")


def _sample_suppliers() -> pd.DataFrame:
    """Return a supplier master dataset with distinct behavior profiles."""
    rows = []
    for supplier_id, profile in SUPPLIER_PROFILES.items():
        rows.append(
            {
                "supplier_id": supplier_id,
                "supplier_name": profile["name"],
                "country": profile["country"],
                "status": profile["status"],
                "supplier_status": profile["status"].upper(),
                "supplier_country": profile["country"],
                "supplier_region": _supplier_region(profile["country"]),
                "supplier_currency": _supplier_currency(profile["country"]),
                "base_reliability_score": profile["base_reliability_score"],
                "payment_terms": profile["payment_terms"],
                "priority_class": profile["priority_class"],
                "accepts_returns": supplier_id in {"SUP-002", "SUP-003", "SUP-004", "SUP-007"},
                "return_window_days": _supplier_return_window(supplier_id),
                "return_deduction_rate": _supplier_return_deduction(supplier_id),
                "return_shipping_cost": _supplier_return_shipping(supplier_id),
                "return_handling_fee": _supplier_return_handling(supplier_id),
                "return_minimum_quantity": _supplier_return_minimum(supplier_id),
                "returns_allowed_for_near_expiry": supplier_id in {"SUP-002", "SUP-004", "SUP-007"},
                "returns_allowed_for_expired": supplier_id == "SUP-002",
                "return_authorization_required": supplier_id != "SUP-003",
                "return_policy_notes": _supplier_return_notes(supplier_id),
                "expedite_available": supplier_id in {"SUP-002", "SUP-003", "SUP-007"},
                "expedite_lead_time_days": max(2, int(profile["lead_time_mean"] * 0.45)),
                "expedite_fixed_fee": _expedite_fixed_fee(supplier_id),
                "expedite_cost_rate": _expedite_cost_rate(supplier_id),
                "expedite_capacity_limit": _expedite_capacity_limit(supplier_id),
                "expedite_reliability": min(0.98, profile["base_reliability_score"] + 0.08),
                "expedite_minimum_quantity": _expedite_min_qty(supplier_id),
                "expedite_policy_notes": _expedite_notes(supplier_id),
                "split_delivery_available": supplier_id in {"SUP-003", "SUP-004", "SUP-006", "SUP-007"},
                "minimum_split_quantity": _minimum_split_quantity(supplier_id),
                "maximum_split_shipments": _max_split_shipments(supplier_id),
                "split_delivery_fixed_fee": _split_fixed_fee(supplier_id),
                "split_delivery_variable_rate": _split_variable_rate(supplier_id),
                "first_shipment_lead_time_days": max(1, int(profile["lead_time_mean"] * 0.55)),
                "remaining_shipment_lead_time_days": int(profile["lead_time_mean"]),
                "partial_delivery_reliability": min(0.97, 1 - profile["partial_delivery_rate"]),
                "split_delivery_policy_notes": _split_notes(supplier_id),
                "supplier_capacity_per_period": _supplier_capacity(supplier_id),
                "available_capacity": _supplier_available_capacity(supplier_id),
                "capacity_utilization": _supplier_capacity_utilization(supplier_id),
                "order_acceptance_probability": _supplier_acceptance_probability(supplier_id),
                "capacity_review_required": _supplier_capacity_utilization(supplier_id) >= 0.85,
                "capacity_notes": _capacity_notes(supplier_id),
                "freight_cost_rate": _freight_rate(supplier_id),
                "handling_cost_rate": _handling_rate(supplier_id),
                "insurance_cost_rate": _insurance_rate(supplier_id),
                "customs_cost_rate": _customs_rate(supplier_id),
                "payment_terms_days": _payment_terms_days(profile["payment_terms"]),
                "early_payment_discount_rate": _early_discount_rate(supplier_id),
                "late_payment_penalty_rate": _late_penalty_rate(supplier_id),
                "minimum_order_value": _minimum_order_value(supplier_id),
            }
        )
    return pd.DataFrame(rows)


def _sample_supplier_sku() -> pd.DataFrame:
    """Return competing suppliers for each SKU with real trade-offs."""
    rows = []
    for sku_index, sku_id in enumerate(SKU_IDS):
        base_cost = 2.8 + sku_index * 1.45
        base_moq = 60 + 10 * (sku_index % 4)
        for supplier_rank, supplier_id in enumerate(SKU_SUPPLIER_MIX[sku_index], start=1):
            profile = SUPPLIER_PROFILES[supplier_id]
            sku_complexity = 1 + 0.025 * (sku_index % 5)
            unit_cost = round(base_cost * profile["cost_factor"] * sku_complexity, 2)
            moq = int(round(base_moq * profile["moq_factor"] / 5) * 5)
            batch_size = int(round((base_moq * 0.70) * profile["batch_factor"] / 5) * 5)
            lead_time = int(round(profile["lead_time_mean"] + (sku_index % 3) * 1.5))
            yield_rate = round(max(0.65, min(0.995, profile["yield_rate"] - 0.006 * (sku_index % 3))), 3)
            available_capacity = max(moq, int(_supplier_available_capacity(supplier_id) / (3 + supplier_rank)))
            rows.append(
                {
                    "sku_id": sku_id,
                    "supplier_id": supplier_id,
                    "unit_cost": unit_cost,
                    "unit_price": unit_cost,
                    "currency": _supplier_currency(profile["country"]),
                    "moq": moq,
                    "batch_size": batch_size,
                    "order_multiple": max(5, int(batch_size / 2)),
                    "lead_time_mean_days": lead_time,
                    "standard_lead_time_days": lead_time,
                    "minimum_lead_time_days": max(1, lead_time - int(profile["lead_time_std"])),
                    "maximum_lead_time_days": lead_time + int(profile["lead_time_std"] * 2),
                    "lead_time_std_days": round(profile["lead_time_std"] + 0.25 * (sku_index % 2), 1),
                    "lead_time_variability_days": round(profile["lead_time_std"] + 0.25 * (sku_index % 2), 1),
                    "yield_rate": yield_rate,
                    "defect_rate": round(1 - yield_rate, 3),
                    "supplier_sku_capacity_per_period": available_capacity + 150 + 20 * sku_index,
                    "supplier_sku_available_capacity": available_capacity,
                    "max_order_quantity": available_capacity + 80,
                    "allocation_limit_by_sku": max(moq, int(available_capacity * 0.85)),
                    "price_break_1_quantity": moq,
                    "price_break_1_unit_price": unit_cost,
                    "price_break_2_quantity": max(moq * 2, moq + 50),
                    "price_break_2_unit_price": round(unit_cost * 0.96, 2),
                    "price_break_3_quantity": max(moq * 4, moq + 160),
                    "price_break_3_unit_price": round(unit_cost * 0.92, 2),
                    "return_eligible": supplier_id in {"SUP-002", "SUP-003", "SUP-004", "SUP-007"} and sku_index % 4 != 1,
                    "expedite_eligible": supplier_id in {"SUP-002", "SUP-003", "SUP-007"} and sku_index % 5 != 3,
                    "split_delivery_eligible": supplier_id in {"SUP-003", "SUP-004", "SUP-006", "SUP-007"} and sku_index % 3 != 2,
                    "preferred_supplier_flag": supplier_rank == 1,
                    "backup_supplier_flag": supplier_rank == 2,
                    "delay_probability": round(min(0.85, profile["delay_probability"] + 0.015 * (sku_index % 4)), 3),
                    "partial_delivery_rate": round(min(0.70, profile["partial_delivery_rate"] + 0.012 * (sku_index % 3)), 3),
                    "fixed_order_cost": round(profile["fixed_order_cost"] * (1 + 0.02 * (sku_index % 3)), 2),
                    "delivery_cost": round(profile["delivery_cost"] * (1 + 0.015 * (sku_index % 4)), 2),
                    "cost_per_late_day": round(profile["cost_per_late_day"] * (1 + 0.03 * (sku_index % 2)), 2),
                    "partial_delivery_penalty": round(profile["partial_delivery_penalty"] * (1 + 0.02 * (sku_index % 5)), 2),
                    "quality_rejection_cost_per_unit": round(
                        profile["quality_rejection_cost_per_unit"] * (1 + 0.025 * (sku_index % 4)),
                        2,
                    ),
                    "supplier_priority": supplier_rank,
                    "is_primary_supplier": supplier_rank == 1,
                }
            )
    return pd.DataFrame(rows)


def _sample_backorders(supplier_sku: pd.DataFrame) -> pd.DataFrame:
    """Return order-line-level backorders for aging and planning context."""
    base_date = pd.Timestamp("2026-06-07")
    selected_skus = SKU_IDS[:8]
    rows = []
    for index, sku_id in enumerate(selected_skus, start=1):
        primary = supplier_sku[(supplier_sku["sku_id"] == sku_id) & (supplier_sku["preferred_supplier_flag"])]
        if primary.empty:
            primary = supplier_sku[supplier_sku["sku_id"] == sku_id].head(1)
        supplier_id = str(primary.iloc[0]["supplier_id"])
        units = 35 + index * 12
        fulfilled = 0 if index in {1, 3, 6} else int(units * (0.25 + 0.05 * (index % 3)))
        status = "OPEN" if fulfilled == 0 else "PARTIALLY_FULFILLED"
        if index == 8:
            fulfilled = units
            status = "FULFILLED"
        start_date = base_date - pd.Timedelta(days=4 + index * 4)
        due_date = start_date + pd.Timedelta(days=6 + index % 5)
        promised_date = due_date + pd.Timedelta(days=index % 4)
        rows.append(
            {
                "backorder_id": f"BO-{index:05d}",
                "backorder_type": _backorder_type(index),
                "sku_id": sku_id,
                "customer_order_id": f"CO-{2000 + index}",
                "customer_order_line_id": f"COL-{2000 + index}-1",
                "supplier_id": supplier_id,
                "purchase_order_id": f"PO-{index:05d}",
                "demand_reference": f"DEMAND-{sku_id}-{index}",
                "backorder_start_date": start_date.strftime("%Y-%m-%d"),
                "original_due_date": due_date.strftime("%Y-%m-%d"),
                "promised_date": promised_date.strftime("%Y-%m-%d"),
                "backorder_units": units,
                "fulfilled_units": fulfilled,
                "remaining_backorder_units": max(units - fulfilled, 0),
                "backorder_status": status,
                "priority_class": _priority_class(index),
                "criticality_class": _criticality_class(index),
                "customer_priority": _customer_priority(index),
                "service_level_target": _service_level_target(index),
                "last_update_date": (base_date - pd.Timedelta(days=index % 12)).strftime("%Y-%m-%d"),
                "cancellation_flag": False,
                "cancellation_date": "",
                "notes": "Demo order-line backorder for procurement planning context.",
            }
        )
    return pd.DataFrame(rows)


def _sample_backorder_allocations(backorders: pd.DataFrame) -> pd.DataFrame:
    """Return batch allocation traceability records for partially fulfilled backorders."""
    rows = []
    allocation_number = 1
    for _, backorder in backorders.iterrows():
        fulfilled = int(backorder["fulfilled_units"])
        if fulfilled <= 0:
            continue
        first_qty = int(round(fulfilled * 0.65))
        quantities = [first_qty, fulfilled - first_qty] if fulfilled - first_qty > 0 else [fulfilled]
        for split_index, quantity in enumerate(quantities, start=1):
            rows.append(
                {
                    "allocation_id": f"BOA-{allocation_number:05d}",
                    "backorder_id": backorder["backorder_id"],
                    "sku_id": backorder["sku_id"],
                    "batch_id": f"DEMO-BATCH-{backorder['sku_id']}-{split_index}",
                    "allocated_quantity": quantity,
                    "allocation_date": (
                        pd.to_datetime(backorder["last_update_date"]) - pd.Timedelta(days=split_index)
                    ).strftime("%Y-%m-%d"),
                    "warehouse_id": "WH-DEMO-01",
                    "location_id": f"DEMO-LOC-{split_index:02d}",
                    "allocation_method": "FEFO" if split_index == 1 else "PRIORITY_ALLOCATION",
                    "fefo_compliant_flag": split_index == 1,
                    "fifo_compliant_flag": True,
                    "allocation_status": "ALLOCATED",
                    "notes": "Demo batch allocation for backorder fulfillment traceability.",
                }
            )
            allocation_number += 1
    return pd.DataFrame(rows)


def _supplier_region(country: str) -> str:
    """Map demo supplier country to a broad procurement region."""
    return {
        "India": "APAC",
        "Germany": "EUROPE",
        "Lebanon": "LOCAL",
        "Denmark": "EUROPE",
        "Turkey": "MENA",
        "China": "APAC",
        "Italy": "EUROPE",
    }.get(country, "UNKNOWN")


def _supplier_currency(country: str) -> str:
    """Return supplier transaction currency for demo data."""
    return {
        "India": "USD",
        "Germany": "EUR",
        "Lebanon": "USD",
        "Denmark": "EUR",
        "Turkey": "USD",
        "China": "USD",
        "Italy": "EUR",
    }.get(country, "USD")


def _payment_terms_days(payment_terms: str) -> int:
    """Parse simple Net N terms into days."""
    parts = str(payment_terms).split()
    for part in parts:
        if part.isdigit():
            return int(part)
    return 30


def _supplier_return_window(supplier_id: str) -> int:
    return {"SUP-002": 45, "SUP-003": 21, "SUP-004": 30, "SUP-007": 25}.get(supplier_id, 0)


def _supplier_return_deduction(supplier_id: str) -> float:
    return {"SUP-002": 0.08, "SUP-003": 0.15, "SUP-004": 0.12, "SUP-007": 0.18}.get(supplier_id, 0.25)


def _supplier_return_shipping(supplier_id: str) -> float:
    return {"SUP-002": 70, "SUP-003": 35, "SUP-004": 55, "SUP-007": 45}.get(supplier_id, 0)


def _supplier_return_handling(supplier_id: str) -> float:
    return {"SUP-002": 25, "SUP-003": 15, "SUP-004": 20, "SUP-007": 18}.get(supplier_id, 0)


def _supplier_return_minimum(supplier_id: str) -> int:
    return {"SUP-002": 20, "SUP-003": 10, "SUP-004": 25, "SUP-007": 15}.get(supplier_id, 0)


def _supplier_return_notes(supplier_id: str) -> str:
    if supplier_id in {"SUP-002", "SUP-004"}:
        return "Returns accepted with authorization and inspection."
    if supplier_id in {"SUP-003", "SUP-007"}:
        return "Returns accepted for selected SKUs within window."
    return "Returns generally not accepted in demo terms."


def _expedite_fixed_fee(supplier_id: str) -> float:
    return {"SUP-002": 180, "SUP-003": 75, "SUP-007": 110}.get(supplier_id, 0)


def _expedite_cost_rate(supplier_id: str) -> float:
    return {"SUP-002": 0.10, "SUP-003": 0.08, "SUP-007": 0.12}.get(supplier_id, 0)


def _expedite_capacity_limit(supplier_id: str) -> int:
    return {"SUP-002": 180, "SUP-003": 120, "SUP-007": 150}.get(supplier_id, 0)


def _expedite_min_qty(supplier_id: str) -> int:
    return {"SUP-002": 25, "SUP-003": 10, "SUP-007": 15}.get(supplier_id, 0)


def _expedite_notes(supplier_id: str) -> str:
    return "Expedite option available for eligible SKUs." if supplier_id in {"SUP-002", "SUP-003", "SUP-007"} else "No expedite option."


def _minimum_split_quantity(supplier_id: str) -> int:
    return {"SUP-003": 40, "SUP-004": 80, "SUP-006": 160, "SUP-007": 50}.get(supplier_id, 0)


def _max_split_shipments(supplier_id: str) -> int:
    return {"SUP-003": 2, "SUP-004": 3, "SUP-006": 4, "SUP-007": 2}.get(supplier_id, 1)


def _split_fixed_fee(supplier_id: str) -> float:
    return {"SUP-003": 45, "SUP-004": 95, "SUP-006": 140, "SUP-007": 65}.get(supplier_id, 0)


def _split_variable_rate(supplier_id: str) -> float:
    return {"SUP-003": 0.035, "SUP-004": 0.045, "SUP-006": 0.03, "SUP-007": 0.04}.get(supplier_id, 0)


def _split_notes(supplier_id: str) -> str:
    return "Split delivery available for eligible quantities." if supplier_id in {"SUP-003", "SUP-004", "SUP-006", "SUP-007"} else "Split delivery not offered."


def _supplier_capacity(supplier_id: str) -> int:
    return {"SUP-001": 900, "SUP-002": 700, "SUP-003": 420, "SUP-004": 760, "SUP-005": 500, "SUP-006": 1400, "SUP-007": 360}[supplier_id]


def _supplier_available_capacity(supplier_id: str) -> int:
    return {"SUP-001": 330, "SUP-002": 280, "SUP-003": 115, "SUP-004": 260, "SUP-005": 95, "SUP-006": 520, "SUP-007": 160}[supplier_id]


def _supplier_capacity_utilization(supplier_id: str) -> float:
    return round(1 - (_supplier_available_capacity(supplier_id) / _supplier_capacity(supplier_id)), 3)


def _supplier_acceptance_probability(supplier_id: str) -> float:
    return round(max(0.50, 1 - _supplier_capacity_utilization(supplier_id) * 0.45), 3)


def _capacity_notes(supplier_id: str) -> str:
    if _supplier_capacity_utilization(supplier_id) >= 0.85:
        return "Supplier capacity is tight; review large orders."
    return "Supplier capacity available for normal planning quantities."


def _freight_rate(supplier_id: str) -> float:
    return {"SUP-001": 0.09, "SUP-002": 0.055, "SUP-003": 0.035, "SUP-004": 0.05, "SUP-005": 0.075, "SUP-006": 0.08, "SUP-007": 0.06}[supplier_id]


def _handling_rate(supplier_id: str) -> float:
    return {"SUP-001": 0.025, "SUP-002": 0.018, "SUP-003": 0.02, "SUP-004": 0.016, "SUP-005": 0.022, "SUP-006": 0.02, "SUP-007": 0.018}[supplier_id]


def _insurance_rate(supplier_id: str) -> float:
    return {"SUP-001": 0.012, "SUP-002": 0.01, "SUP-003": 0.006, "SUP-004": 0.009, "SUP-005": 0.011, "SUP-006": 0.014, "SUP-007": 0.01}[supplier_id]


def _customs_rate(supplier_id: str) -> float:
    return {"SUP-001": 0.045, "SUP-002": 0.02, "SUP-003": 0.0, "SUP-004": 0.02, "SUP-005": 0.035, "SUP-006": 0.05, "SUP-007": 0.02}[supplier_id]


def _early_discount_rate(supplier_id: str) -> float:
    return {"SUP-002": 0.01, "SUP-003": 0.005, "SUP-007": 0.008}.get(supplier_id, 0.0)


def _late_penalty_rate(supplier_id: str) -> float:
    return {"SUP-001": 0.025, "SUP-005": 0.03, "SUP-006": 0.02}.get(supplier_id, 0.015)


def _minimum_order_value(supplier_id: str) -> float:
    return {"SUP-001": 400, "SUP-002": 600, "SUP-003": 180, "SUP-004": 650, "SUP-005": 300, "SUP-006": 1000, "SUP-007": 250}[supplier_id]


def _backorder_type(index: int) -> str:
    return ["CUSTOMER_DEMAND_BACKORDER", "PROCUREMENT_SHORTFALL", "INTERNAL_REPLENISHMENT_BACKORDER"][index % 3]


def _priority_class(index: int) -> str:
    return ["A", "B", "C", "A"][index % 4]


def _criticality_class(index: int) -> str:
    return ["STANDARD", "VITAL", "IMPORTANT", "CRITICAL"][index % 4]


def _customer_priority(index: int) -> str:
    return ["NORMAL", "HIGH", "CRITICAL"][index % 3]


def _service_level_target(index: int) -> float:
    return [0.90, 0.95, 0.97, 0.92][index % 4]


def _sample_purchase_orders(supplier_sku: pd.DataFrame) -> pd.DataFrame:
    """Return purchase orders with enough baseline/recent history for trend demos."""
    rows = []
    po_number = 1
    for supplier_id, plan in SUPPLIER_TREND_DEMO_PLAN.items():
        links = supplier_sku[supplier_sku["supplier_id"] == supplier_id].reset_index(drop=True)
        period_specs = [
            ("baseline", plan["baseline_orders"], BASELINE_PROMISED_START, BASELINE_PROMISED_END),
            ("recent", plan["recent_orders"], RECENT_PROMISED_START, RECENT_PROMISED_END),
        ]
        for period_name, order_count, start_date, end_date in period_specs:
            promised_dates = _evenly_spaced_dates(start_date, end_date, order_count)
            for order_index, promised in enumerate(promised_dates):
                link = links.iloc[order_index % len(links)]
                planned_lead = _planned_lead_days(
                    supplier_id,
                    period_name,
                    int(link["lead_time_mean_days"]),
                    order_index,
                )
                order_date = promised - pd.Timedelta(days=planned_lead)
                quantity_multiplier = 1 + ((order_index + len(rows)) % 4)
                rows.append(
                    {
                        "po_id": f"PO-{po_number:05d}",
                        "sku_id": link["sku_id"],
                        "supplier_id": supplier_id,
                        "order_date": order_date.strftime("%Y-%m-%d"),
                        "ordered_quantity": int(link["moq"] * quantity_multiplier),
                        "promised_delivery_date": promised.strftime("%Y-%m-%d"),
                        "expected_unit_cost": round(
                            link["unit_cost"] * _unit_cost_multiplier(supplier_id, period_name),
                            2,
                        ),
                    }
                )
                po_number += 1
    return pd.DataFrame(rows)


def _sample_receipts(purchase_orders: pd.DataFrame, supplier_sku: pd.DataFrame) -> pd.DataFrame:
    """Return receipts whose recent/baseline behavior demonstrates supplier trends."""
    supply_terms = supplier_sku[
        [
            "sku_id",
            "supplier_id",
            "yield_rate",
            "delay_probability",
            "partial_delivery_rate",
            "lead_time_std_days",
        ]
    ].copy()
    orders = purchase_orders.merge(supply_terms, on=["sku_id", "supplier_id"], how="left")

    rows = []
    for index, po in orders.reset_index(drop=True).iterrows():
        ordered = int(po["ordered_quantity"])
        supplier_id = po["supplier_id"]
        period_name = _period_name(pd.to_datetime(po["promised_delivery_date"]))
        receipt_profile = _receipt_behavior(supplier_id, period_name, index)

        delay_days = receipt_profile["delay_days"]
        partial_event = receipt_profile["partial_delivery_flag"]
        quality_event = receipt_profile["quality_issue_flag"]
        yield_rate = receipt_profile["yield_rate"]

        received_ratio = 1.0 if not partial_event else receipt_profile["received_ratio"]
        received = int(round(ordered * received_ratio))

        defect_rate = max(0.002, 1 - yield_rate)
        rejected = int(round(received * defect_rate))
        accepted = max(0, received - rejected)

        promised_date = pd.to_datetime(po["promised_delivery_date"])
        receipt_date = promised_date + pd.Timedelta(days=delay_days)
        rows.append(
            {
                "receipt_id": f"REC-{index + 1:05d}",
                "po_id": po["po_id"],
                "receipt_date": receipt_date.strftime("%Y-%m-%d"),
                "received_quantity": received,
                "accepted_quantity": accepted,
                "rejected_quantity": rejected,
                "delay_days": delay_days,
                "partial_delivery_flag": int(partial_event),
                "quality_issue_flag": int(quality_event),
            }
        )
    return pd.DataFrame(rows)


def _deterministic_probability(index: int, offset: float) -> float:
    """Return a deterministic pseudo-random value between 0 and 1."""
    return float((index * 0.61803398875 + offset) % 1)


def _evenly_spaced_dates(start_date: pd.Timestamp, end_date: pd.Timestamp, count: int) -> list[pd.Timestamp]:
    """Return deterministic dates spread across a period."""
    if count <= 0:
        return []
    if count == 1:
        return [start_date]
    total_days = (end_date - start_date).days
    return [
        start_date + pd.Timedelta(days=round(index * total_days / (count - 1)))
        for index in range(count)
    ]


def _planned_lead_days(supplier_id: str, period_name: str, base_lead_days: int, order_index: int) -> int:
    """Return planned lead time used to create actual lead-time trend differences."""
    trend = SUPPLIER_TREND_DEMO_PLAN[supplier_id]["trend"]
    if trend == "improving" and period_name == "baseline":
        return base_lead_days + 2
    if trend == "mixed" and period_name == "recent":
        return base_lead_days + 2
    return base_lead_days + (order_index % 2)


def _unit_cost_multiplier(supplier_id: str, period_name: str) -> float:
    """Return expected unit cost multiplier for trend demonstration."""
    trend = SUPPLIER_TREND_DEMO_PLAN[supplier_id]["trend"]
    if trend == "improving":
        return 1.08 if period_name == "baseline" else 0.94
    if trend == "healthy":
        return 1.00 if period_name == "baseline" else 1.02
    if trend == "watchlist":
        return 0.96 if period_name == "baseline" else 1.22
    if trend == "mixed":
        return 1.12 if period_name == "baseline" else 0.88
    return 1.00


def _period_name(promised_delivery_date: pd.Timestamp) -> str:
    """Map promised delivery date to baseline or recent demo period."""
    if promised_delivery_date >= RECENT_PROMISED_START:
        return "recent"
    return "baseline"


def _receipt_behavior(supplier_id: str, period_name: str, index: int) -> dict[str, float | int]:
    """Return deterministic receipt behavior for a supplier trend archetype."""
    trend = SUPPLIER_TREND_DEMO_PLAN[supplier_id]["trend"]
    if trend == "improving":
        if period_name == "baseline":
            return _behavior(delay_days=3 + index % 3, partial_every=3, yield_rate=0.86, quality_every=2, index=index)
        return _behavior(delay_days=0 if index % 5 else 1, partial_every=99, yield_rate=0.96, quality_every=99, index=index)
    if trend == "healthy":
        return _behavior(delay_days=0 if index % 7 else 1, partial_every=99, yield_rate=0.975, quality_every=99, index=index)
    if trend == "watchlist":
        if period_name == "baseline":
            return _behavior(delay_days=0 if index % 5 else 1, partial_every=10, yield_rate=0.955, quality_every=12, index=index)
        return _behavior(delay_days=4 + index % 4, partial_every=2, yield_rate=0.83, quality_every=2, index=index)
    if trend == "mixed":
        if period_name == "baseline":
            return _behavior(delay_days=0, partial_every=99, yield_rate=0.90, quality_every=7, index=index)
        return _behavior(delay_days=0, partial_every=99, yield_rate=0.885, quality_every=6, index=index)
    return _behavior(delay_days=1, partial_every=4, yield_rate=0.93, quality_every=6, index=index)


def _behavior(
    delay_days: int,
    partial_every: int,
    yield_rate: float,
    quality_every: int,
    index: int,
) -> dict[str, float | int]:
    """Build one deterministic receipt behavior row."""
    partial_delivery_flag = int(partial_every < 99 and index % partial_every == 0)
    quality_issue_flag = int(quality_every < 99 and index % quality_every == 0)
    received_ratio = 0.72 if partial_delivery_flag else 1.0
    return {
        "delay_days": delay_days,
        "partial_delivery_flag": partial_delivery_flag,
        "quality_issue_flag": quality_issue_flag,
        "yield_rate": yield_rate,
        "received_ratio": received_ratio,
    }
