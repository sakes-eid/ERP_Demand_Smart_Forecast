"""Configuration for Phase 2 Supply & Procurement."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

PHASE_1_DIR = BASE_DIR.parent / "phase 1"
PHASE_1_OUTPUT_DIR = PHASE_1_DIR / "outputs"
PHASE1_OUTPUT_DIR = PHASE_1_OUTPUT_DIR

PHASE1_PRODUCTS_CLEAN_FILES = [
    PHASE1_OUTPUT_DIR / "products_clean.csv",
    PHASE1_OUTPUT_DIR / "products_cleaned.csv",
]
PHASE1_DEMAND_PROFILE_FILE = PHASE1_OUTPUT_DIR / "demand_profile.csv"
PHASE1_FORECAST_RESULTS_FILE = PHASE1_OUTPUT_DIR / "forecast_results.csv"
PHASE1_MODEL_REGISTRY_FILE = PHASE1_OUTPUT_DIR / "model_registry.csv"

SUPPLIERS_FILE = DATA_DIR / "suppliers.csv"
SUPPLIER_SKU_FILE = DATA_DIR / "supplier_sku.csv"
PURCHASE_ORDERS_FILE = DATA_DIR / "purchase_orders.csv"
RECEIPTS_FILE = DATA_DIR / "receipts.csv"

DATE_FORMAT = "%Y-%m-%d"

SUPPLIER_SELECTION_WEIGHTS = {
    "cost": 0.35,
    "reliability": 0.25,
    "lead_time": 0.20,
    "quality": 0.15,
    "risk": 0.05,
}

PROCUREMENT_RISK_THRESHOLDS = {
    "low": 0.25,
    "medium": 0.50,
}

SUPPLIER_SCORE_CLOSE_THRESHOLD = 0.03

SPLIT_SOURCING_THRESHOLDS = {
    "high_delay_probability": 0.30,
    "high_lead_time_std_days": 5.0,
}

SUPPLIER_TREND_WINDOWS = {
    "recent_days": 30,
    "baseline_days": 90,
    "minimum_recent_orders": 3,
    "minimum_baseline_orders": 5,
}

SUPPLIER_TREND_THRESHOLDS = {
    "lead_time_worsening_pct": 0.20,
    "lead_time_improving_pct": 0.20,
    "delay_worsening_pct": 0.20,
    "delay_improving_pct": 0.20,
    "on_time_rate_drop_pct": 0.10,
    "on_time_rate_improve_pct": 0.10,
    "partial_delivery_worsening_pct": 0.10,
    "partial_delivery_improving_pct": 0.10,
    "yield_drop_pct": 0.05,
    "yield_improve_pct": 0.05,
    "defect_rate_worsening_pct": 0.10,
    "defect_rate_improving_pct": 0.10,
    "cost_worsening_pct": 0.15,
    "cost_improving_pct": 0.15,
    "reliability_drop_pct": 0.08,
    "reliability_improve_pct": 0.08,
}

SUPPLIER_EVIDENCE_ADJUSTMENTS = {
    "no_history_penalty": 0.05,
    "insufficient_trend_data_penalty": 0.03,
    "watchlist_penalty": 0.05,
    "improving_bonus": 0.02,
}
