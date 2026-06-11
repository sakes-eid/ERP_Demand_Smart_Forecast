"""Configuration for Phase 2 Supply & Procurement."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
PROJECT_ROOT = BASE_DIR.parent
SHARED_OUTPUT_DIR = PROJECT_ROOT / "shared" / "outputs"

PHASE_1_DIR = BASE_DIR.parent / "phase 1"
PHASE_1_OUTPUT_DIR = PHASE_1_DIR / "outputs"
PHASE1_OUTPUT_DIR = PHASE_1_OUTPUT_DIR

PHASE1_PRODUCTS_CLEAN_FILES = [
    PHASE1_OUTPUT_DIR / "products_clean.csv",
    PHASE1_OUTPUT_DIR / "products_cleaned.csv",
]
PHASE1_DEMAND_PROFILE_FILE = PHASE1_OUTPUT_DIR / "demand_profile.csv"
PHASE1_DEMAND_PLANNING_CONTEXT_FILE = PHASE1_OUTPUT_DIR / "phase1_demand_planning_context.csv"
PHASE1_FORECAST_RESULTS_FILE = PHASE1_OUTPUT_DIR / "forecast_results.csv"
PHASE1_MODEL_REGISTRY_FILE = PHASE1_OUTPUT_DIR / "model_registry.csv"

SUPPLIERS_FILE = DATA_DIR / "suppliers.csv"
SUPPLIER_SKU_FILE = DATA_DIR / "supplier_sku.csv"
PURCHASE_ORDERS_FILE = DATA_DIR / "purchase_orders.csv"
RECEIPTS_FILE = DATA_DIR / "receipts.csv"
BACKORDERS_FILE = DATA_DIR / "backorders.csv"
BACKORDER_ALLOCATIONS_FILE = DATA_DIR / "backorder_fulfillment_allocations.csv"

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

BACKORDER_CONFIG = {
    "long_backorder_days": 14,
    "critical_backorder_days": 7,
    "stale_update_days": 10,
    "high_backorder_units_threshold": 100,
}

PROCUREMENT_CAPABILITY_CONFIG = {
    "default_reference_order_quantity": 100,
    "default_planning_horizon_days": 30,
    "minimum_review_cycle_days": 7,
    "default_capacity_period_unit": "WEEKLY",
    "default_capacity_period_days": 7,
    "default_month_days": 30,
    "capacity_pressure_threshold": 0.85,
    "minimum_order_acceptance_probability": 0.70,
    "expedite_recommendation_min_days_saved": 3,
    "split_delivery_minimum_service_benefit": 0.10,
    "cost_fallbacks_enabled": True,
    "quality_loss_cost_multiplier": 1.0,
}

CAPACITY_PERIOD_UNITS = [
    "DAILY",
    "WEEKLY",
    "MONTHLY",
    "PER_ORDER",
    "CUSTOM_DAYS",
]

PROCUREMENT_REQUIREMENT_METHODS = [
    "GROSS_DEMAND_PLUS_BACKORDER_MINUS_CONFIRMED_INBOUND",
    "GROSS_DEMAND_ONLY",
    "PROVISIONAL_NO_INVENTORY_CONTEXT",
    "LEGACY_REFERENCE_QUANTITY_FALLBACK",
]

SUPPLIER_STRATEGY_CONFIG = {
    "balanced_cost_weight": 0.25,
    "balanced_lead_time_weight": 0.18,
    "balanced_reliability_weight": 0.22,
    "balanced_risk_weight": 0.12,
    "balanced_quality_weight": 0.12,
    "balanced_capacity_weight": 0.07,
    "balanced_backorder_capability_weight": 0.04,
}

DEMAND_ADJUSTED_RISK_WEIGHTS = {
    "demand_risk_component": 0.30,
    "supplier_risk_component": 0.25,
    "backorder_risk_component": 0.18,
    "capacity_risk_component": 0.15,
    "event_risk_component": 0.12,
}

RETURN_POLICY_CONFIG = {
    "default_return_deduction_rate": 0.20,
    "default_return_shipping_cost": 0.0,
    "default_return_handling_fee": 0.0,
}

PROCUREMENT_SCORING_INPUT_MODES = [
    "CAPABILITY_ONLY",
    "PROVISIONAL_NO_PHASE3_CONTEXT",
    "AUTHORITATIVE_PHASE3_REQUIREMENT",
]
