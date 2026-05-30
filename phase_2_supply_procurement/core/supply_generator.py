"""Generate realistic Phase 2 supply input data when CSV files are missing."""

import pandas as pd

from config import DATA_DIR, PURCHASE_ORDERS_FILE, RECEIPTS_FILE, SUPPLIER_SKU_FILE, SUPPLIERS_FILE


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

    wrote_any_file = any(
        [
            _write_if_missing_or_refresh(SUPPLIERS_FILE, suppliers, refresh_samples),
            _write_if_missing_or_refresh(SUPPLIER_SKU_FILE, supplier_sku, refresh_samples),
            _write_if_missing_or_refresh(PURCHASE_ORDERS_FILE, purchase_orders, refresh_samples),
            _write_if_missing_or_refresh(RECEIPTS_FILE, receipts, refresh_samples),
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
    return is_known_sample and (_supplier_sku_missing_cost_columns() or _purchase_orders_need_trend_refresh())


def _supplier_sku_missing_cost_columns() -> bool:
    """Return True when the generated supplier-SKU sample lacks new cost fields."""
    if not SUPPLIER_SKU_FILE.exists():
        return True
    try:
        supplier_sku = pd.read_csv(SUPPLIER_SKU_FILE, nrows=1)
    except Exception:
        return False
    return not COST_COLUMNS.issubset(set(supplier_sku.columns))


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
        for path in [SUPPLIERS_FILE, SUPPLIER_SKU_FILE, PURCHASE_ORDERS_FILE, RECEIPTS_FILE]
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
                "base_reliability_score": profile["base_reliability_score"],
                "payment_terms": profile["payment_terms"],
                "priority_class": profile["priority_class"],
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
            rows.append(
                {
                    "sku_id": sku_id,
                    "supplier_id": supplier_id,
                    "unit_cost": round(base_cost * profile["cost_factor"] * sku_complexity, 2),
                    "moq": int(round(base_moq * profile["moq_factor"] / 5) * 5),
                    "batch_size": int(round((base_moq * 0.70) * profile["batch_factor"] / 5) * 5),
                    "lead_time_mean_days": int(round(profile["lead_time_mean"] + (sku_index % 3) * 1.5)),
                    "lead_time_std_days": round(profile["lead_time_std"] + 0.25 * (sku_index % 2), 1),
                    "yield_rate": round(max(0.65, min(0.995, profile["yield_rate"] - 0.006 * (sku_index % 3))), 3),
                    "defect_rate": round(1 - max(0.65, min(0.995, profile["yield_rate"] - 0.006 * (sku_index % 3))), 3),
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
