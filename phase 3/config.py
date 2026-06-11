"""Configuration for Phase 3 Inventory Control."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
PROJECT_ROOT = BASE_DIR.parent
SHARED_OUTPUT_DIR = PROJECT_ROOT / "shared" / "outputs"

INVENTORY_FILE = DATA_DIR / "inventory.csv"
INVENTORY_BATCHES_FILE = DATA_DIR / "inventory_batches.csv"
INVENTORY_MOVEMENTS_FILE = DATA_DIR / "inventory_movements.csv"
WAREHOUSE_LAYOUT_FILE = DATA_DIR / "warehouse_layout.csv"
STORAGE_LOCATIONS_FILE = DATA_DIR / "storage_locations.csv"
SKU_STORAGE_REQUIREMENTS_FILE = DATA_DIR / "sku_storage_requirements.csv"

PHASE1_OUTPUT_DIR = BASE_DIR.parent / "phase 1" / "outputs"
PHASE2_OUTPUT_DIR = BASE_DIR.parent / "phase 2" / "outputs"

PHASE1_PRODUCTS_CLEAN_FILES = [
    PHASE1_OUTPUT_DIR / "products_clean.csv",
    PHASE1_OUTPUT_DIR / "products_cleaned.csv",
]
PHASE1_DEMAND_PROFILE_FILE = PHASE1_OUTPUT_DIR / "demand_profile.csv"
PHASE1_DEMAND_PLANNING_CONTEXT_FILE = PHASE1_OUTPUT_DIR / "phase1_demand_planning_context.csv"
PHASE1_FORECAST_RESULTS_FILE = PHASE1_OUTPUT_DIR / "forecast_results.csv"
PHASE1_MODEL_REGISTRY_FILE = PHASE1_OUTPUT_DIR / "model_registry.csv"
PHASE1_DEMAND_EVENT_FEATURES_FILE = PHASE1_OUTPUT_DIR / "demand_with_event_features.csv"

PHASE2_PROCUREMENT_RECOMMENDATIONS_FILE = PHASE2_OUTPUT_DIR / "procurement_recommendations.csv"
PHASE2_SUPPLIER_SKU_SCORES_FILE = PHASE2_OUTPUT_DIR / "supplier_sku_scores.csv"
PHASE2_SUPPLIER_PERFORMANCE_FILE = PHASE2_OUTPUT_DIR / "supplier_performance.csv"
PHASE2_SUPPLIER_TRENDS_FILE = PHASE2_OUTPUT_DIR / "supplier_trends.csv"
PHASE2_PROCUREMENT_ALLOCATION_SUMMARY_FILE = SHARED_OUTPUT_DIR / "phase2_procurement_allocation_summary.csv"
PHASE2_PROCUREMENT_ALLOCATION_CONTEXT_FILE = SHARED_OUTPUT_DIR / "phase2_procurement_allocation_context.csv"
PHASE2_SUPPLY_CAPABILITY_CONTEXT_FILE = SHARED_OUTPUT_DIR / "phase2_supply_capability_context.csv"

MIN_FORKLIFT_AISLE_WIDTH_M = 3.0
DEFAULT_WAREHOUSE_LENGTH_M = 60
DEFAULT_WAREHOUSE_WIDTH_M = 35
DEFAULT_TRAVEL_SPEED_M_PER_MIN = 60
DEFAULT_TRAVEL_COST_PER_METER = 0.02
DEFAULT_STORAGE_COST_PER_M3 = 4.0

NEAR_EXPIRY_DAYS = 30
EXPIRED_GRACE_DAYS = 0
NON_MOVING_DAYS = 60
DEAD_STOCK_DAYS = 120
SLOW_MOVING_DAYS = 30

SERVICE_LEVEL_Z = {
    0.80: 0.84,
    0.85: 1.04,
    0.90: 1.28,
    0.95: 1.65,
    0.975: 1.96,
    0.98: 2.05,
    0.99: 2.33,
}

HOLDING_COST_COMPONENTS = {
    "capital_cost_rate": 0.10,
    "facility_cost_rate": 0.03,
    "insurance_cost_rate": 0.01,
    "handling_cost_rate": 0.01,
    "obsolescence_cost_rate": 0.02,
    "spoilage_cost_rate": 0.02,
}

DEFAULT_STOCKOUT_PENALTY_PER_UNIT = 25
DEFAULT_OVERSTOCK_PENALTY_PER_UNIT = 5

HANDLING_UNIT_COSTS = {
    "PALLET": 1.0,
    "CASE": 2.5,
    "EACH": 5.0,
}

WAREHOUSE_ZONES = [
    "RECEIVING",
    "PUTAWAY",
    "PALLET_STORAGE",
    "CASE_PICKING",
    "EACH_PICKING",
    "SORTATION",
    "CROSSDOCKING",
    "PACKING",
    "SHIPPING",
    "RETURNS",
    "VALUE_ADDED_SERVICES",
    "QUARANTINE",
    "BULK_STORAGE",
    "FAST_PICK",
    "SLOW_PICK",
]

ABC_CLASS_THRESHOLDS = {
    "A_cumulative_share": 0.80,
    "B_cumulative_share": 0.95,
}

XYZ_CLASS_THRESHOLDS = {
    "X_cv_max": 0.50,
    "Y_cv_max": 1.00,
}

FSN_CLASS_THRESHOLDS = {
    "fast_movement_count_min": 5,
    "slow_movement_count_min": 2,
    "non_moving_days": 60,
}

VITALITY_THRESHOLDS = {
    "vital_stockout_penalty": 35,
    "important_stockout_penalty": 25,
    "high_stockout_units": 10,
    "high_average_daily_demand": 20,
}

SEASONALITY_THRESHOLDS = {
    "high_event_affected_ratio": 0.20,
    "seasonal_categories": ["outdoor", "seasonal", "beverages"],
}

CLASSIFICATION_SCORE_WEIGHTS = {
    "abc": 0.25,
    "xyz": 0.15,
    "fsn": 0.20,
    "vitality": 0.20,
    "perishability": 0.10,
    "supplier_risk": 0.10,
}

SERVICE_LEVEL_TARGETS = {
    "critical_priority": 0.99,
    "high_priority": 0.98,
    "medium_priority": 0.95,
    "low_priority": 0.90,
    "liquidation_priority": 0.80,
    "vital": 0.98,
    "important": 0.95,
    "normal": 0.90,
    "abc_a": 0.97,
    "abc_b": 0.94,
    "abc_c": 0.90,
    "fast_moving": 0.97,
    "medium_moving": 0.94,
    "slow_moving": 0.88,
    "non_moving": 0.80,
    "seasonal_peak": 0.98,
    "seasonal_buildup": 0.97,
    "seasonal_drawdown": 0.85,
    "seasonal_off_season": 0.80,
    "non_seasonal": 0.93,
    "perishable_normal": 0.90,
    "expiry_tracked": 0.88,
    "spoilage_risk": 0.80,
    "intermittent_low_value": 0.85,
    "erratic_high_risk": 0.95,
}

SERVICE_LEVEL_BOUNDS = {
    "minimum": 0.70,
    "maximum": 0.99,
    "default": 0.95,
}

SERVICE_LEVEL_ADJUSTMENTS = {
    "stockout_signal_boost": 0.03,
    "high_stockout_units_boost": 0.02,
    "high_stockout_cost_boost": 0.03,
    "vital_boost": 0.02,
    "critical_priority_boost": 0.02,
    "watchlist_supplier_boost": 0.02,
    "supplier_review_boost": 0.01,
    "high_procurement_risk_boost": 0.02,
    "low_forecast_confidence_boost_for_vital": 0.02,
    "off_season_reduction": -0.08,
    "slow_moving_reduction": -0.04,
    "non_moving_reduction": -0.08,
    "spoilage_risk_reduction": -0.08,
    "near_expiry_reduction": -0.05,
    "dead_stock_reduction": -0.10,
    "liquidation_priority_reduction": -0.10,
    "overstock_like_reduction": -0.04,
}

SERVICE_LEVEL_DECISION_THRESHOLDS = {
    "high_stockout_penalty": 35,
    "medium_stockout_penalty": 25,
    "high_stockout_units": 10,
    "low_forecast_confidence": 0.60,
    "high_forecast_confidence": 0.80,
    "high_average_daily_demand": 20,
    "high_procurement_risk_score": 0.50,
    "low_procurement_risk_score": 0.25,
}

SERVICE_LEVEL_GUARDRAILS = {
    "critical_priority_min": 0.98,
    "high_priority_min": 0.95,
    "vital_min": 0.95,
    "important_min": 0.90,
    "abc_a_min": 0.90,
    "fast_moving_min": 0.90,
    "allow_below_important_min_if_liquidation": True,
    "allow_below_important_min_if_expired_and_not_vital": True,
    "allow_below_important_min_if_dead_stock_and_not_vital": True,
    "allow_below_important_min_if_non_moving_c_class_normal": True,
}

INVENTORY_POLICY_TYPES = [
    "EOQ",
    "NEWSVENDOR_CANDIDATE",
    "BASE_STOCK",
    "CONTINUOUS_REVIEW_sQ",
    "PERIODIC_REVIEW_RS",
    "EVENT_BASED_REPLENISHMENT",
    "ONE_TO_ONE_REPLACEMENT",
]

REVIEW_POLICY_TYPES = [
    "CONTINUOUS_REVIEW",
    "PERIODIC_REVIEW",
    "EVENT_BASED",
    "ONE_TO_ONE",
    "SINGLE_PERIOD",
]

POLICY_SELECTION_THRESHOLDS = {
    "high_service_level": 0.97,
    "medium_service_level": 0.95,
    "low_service_level": 0.90,
    "high_cv": 1.00,
    "medium_cv": 0.50,
    "high_average_daily_demand": 20,
    "low_average_daily_demand": 3,
    "high_stockout_penalty": 35,
    "medium_stockout_penalty": 25,
    "high_stockout_units": 10,
    "high_supplier_risk_score": 0.50,
    "high_moq_to_demand_ratio": 2.0,
    "eoq_extreme_moq_to_demand_ratio": 8.0,
    "eoq_extreme_batch_to_demand_ratio": 6.0,
    "low_movement_count": 2,
    "non_moving_days": 60,
    "near_expiry_units_threshold": 1,
    "expired_units_threshold": 1,
}

DEFAULT_REVIEW_PERIOD_DAYS = {
    "fast_moving": 7,
    "medium_moving": 14,
    "slow_moving": 30,
    "non_moving": 60,
    "seasonal": 7,
    "perishable": 7,
    "default": 14,
}

POLICY_URGENCY_LEVELS = [
    "LOW",
    "MEDIUM",
    "HIGH",
    "URGENT",
]

POLICY_REVIEW_FLAGS = {
    "phase4_item_review": True,
    "supplier_review": True,
    "stockout_review": True,
    "expiry_review": True,
    "seasonal_review": True,
}

INVENTORY_PARAMETER_DEFAULTS = {
    "fallback_lead_time_days": 7,
    "fallback_lead_time_std_days": 2,
    "fallback_average_daily_demand": 1,
    "fallback_coefficient_of_variation": 0.50,
    "fallback_order_setup_cost": 75,
    "fallback_holding_cost_rate": 0.19,
    "minimum_order_quantity": 1,
    "minimum_batch_size": 1,
    "minimum_yield_rate": 0.50,
    "default_yield_rate": 0.95,
}

DEMAND_VARIABILITY_FALLBACKS = {
    "smooth": 0.25,
    "variable": 0.75,
    "erratic": 1.25,
    "intermittent": 1.50,
    "unknown": 0.75,
}

INVENTORY_PARAMETER_ADJUSTMENTS = {
    "critical_safety_stock_multiplier": 1.20,
    "high_priority_safety_stock_multiplier": 1.10,
    "supplier_high_risk_safety_stock_multiplier": 1.15,
    "supplier_medium_risk_safety_stock_multiplier": 1.05,
    "low_forecast_confidence_safety_stock_multiplier": 1.10,
    "perishable_cap_multiplier": 1.50,
    "spoilage_risk_cap_multiplier": 1.00,
    "seasonal_drawdown_cap_multiplier": 1.00,
    "non_moving_cap_multiplier": 0.50,
    "stockout_order_boost_multiplier": 1.25,
}

INVENTORY_PARAMETER_LIMITS = {
    "minimum_safety_stock": 0,
    "minimum_reorder_point": 0,
    "minimum_eoq": 1,
    "maximum_order_days_of_supply_default": 90,
    "maximum_order_days_of_supply_perishable": 30,
    "maximum_order_days_of_supply_spoilage_risk": 14,
    "maximum_order_days_of_supply_non_moving": 7,
    "maximum_order_days_of_supply_seasonal_drawdown": 21,
}

QUANTITY_WARNING_CODES = [
    "HIGH_MOQ_MAY_CAUSE_OVERSTOCK",
    "BATCH_ROUNDING_INCREASED_ORDER",
    "LOW_YIELD_REQUIRES_EXTRA_ORDERING",
    "PERISHABLE_ORDER_CAPPED",
    "STOCKOUT_ORDER_BOOSTED",
    "SUPPLIER_REVIEW_BEFORE_ORDER",
    "PHASE4_REVIEW_BEFORE_FINAL_POLICY",
    "NO_ORDER_RECOMMENDED_FOR_EVENT_BASED",
    "NO_ORDER_RECOMMENDED_FOR_ONE_TO_ONE",
    "ORDER_QUANTITY_CAPPED_BY_EXPIRY_OR_MOVEMENT",
    "ORDER_QUANTITY_CAPPED_BY_EXISTING_INVENTORY",
]

EVENT_BASED_REPLENISHMENT_RULES = {
    "trigger_when_stockout": True,
    "trigger_when_inventory_position_lte_zero": True,
    "trigger_when_inventory_below_days_of_supply": 7,
    "important_review_only_without_trigger": True,
    "default_no_order_quantity": 0,
}

ONE_TO_ONE_REPLACEMENT_RULES = {
    "trigger_when_stockout": True,
    "trigger_when_inventory_position_lte_zero": True,
    "trigger_when_recent_outbound_exists": True,
    "recent_outbound_lookback_days": 30,
    "default_no_order_quantity": 0,
}

INVENTORY_POSITION_CAP_RULES = {
    "event_based_max_days_of_supply": 14,
    "one_to_one_max_days_of_supply": 30,
    "non_moving_max_days_of_supply": 14,
    "low_priority_max_days_of_supply": 30,
    "apply_position_aware_cap": True,
}

INVENTORY_STATUS_TYPES = [
    "STOCKOUT",
    "ZERO_STOCK",
    "CRITICAL_LOW_STOCK",
    "REORDER_NOW",
    "APPROACHING_REORDER_POINT",
    "HEALTHY",
    "OVERSTOCK",
    "UNKNOWN_STATUS",
]

SECONDARY_STATUS_FLAGS = [
    "NEAR_EXPIRY",
    "EXPIRED_STOCK",
    "SPOILAGE_RISK",
    "NON_MOVING",
    "DEAD_STOCK",
    "SUPPLIER_REVIEW_REQUIRED",
    "WATCHLIST_SUPPLIER",
    "PHASE4_REVIEW_REQUIRED",
    "POLICY_REVIEW_REQUIRED",
    "QUANTITY_CONSTRAINT_ACTIVE",
    "NO_ORDER_RECOMMENDED",
    "EXISTING_INVENTORY_CAP_ACTIVE",
    "HIGH_MOQ_OVERSTOCK_RISK",
    "OVERSTOCK_RISK_BY_DAYS_OF_SUPPLY",
    "PARAMETER_INCONSISTENCY",
]

INVENTORY_ACTION_TYPES = [
    "NO_ACTION",
    "ORDER_RECOMMENDED_QUANTITY",
    "EXPEDITE_ORDER",
    "USE_FAST_RELIABLE_SUPPLIER",
    "REVIEW_SUPPLIER_BEFORE_ORDER",
    "WAIT_FOR_TRIGGER",
    "MONITOR_CLOSELY",
    "PRIORITIZE_FEFO_PICKING",
    "MARKDOWN_NEAR_EXPIRY",
    "SCRAP_OR_QUARANTINE_EXPIRED",
    "REDUCE_FUTURE_ORDERS",
    "RETURN_TO_SUPPLIER_IF_ALLOWED",
    "LIQUIDATE_DEAD_STOCK",
    "REVIEW_PHASE4_PRODUCTION_LOGIC",
    "REVIEW_POLICY_PARAMETERS",
]

ACTION_PRIORITY_LEVELS = [
    "URGENT",
    "HIGH",
    "MEDIUM",
    "LOW",
    "NO_ACTION",
]

INVENTORY_STATUS_THRESHOLDS = {
    "approaching_reorder_warning_days": 3,
    "approaching_reorder_warning_pct": 0.10,
    "near_max_stock_warning_pct": 0.90,
    "default_overstock_days_of_supply": 90,
    "perishable_overstock_days_of_supply": 30,
    "spoilage_risk_overstock_days_of_supply": 14,
    "seasonal_drawdown_overstock_days_of_supply": 21,
    "non_moving_overstock_days_of_supply": 14,
    "low_priority_overstock_days_of_supply": 30,
}

INVENTORY_COST_DEFAULTS = {
    "fallback_unit_cost": 1.0,
    "fallback_fixed_order_cost": 75.0,
    "fallback_delivery_cost": 25.0,
    "fallback_stockout_duration_days": 3,
    "fallback_delay_cost_per_day": 10.0,
    "fallback_quality_cost_per_unit": 2.0,
    "fallback_storage_cost_per_m3": 4.0,
    "fallback_handling_cost_per_unit": 0.25,
    "fallback_unit_volume_m3": 0.01,
    "fallback_markdown_loss_rate": 0.30,
    "fallback_scrap_loss_rate": 1.00,
    "fallback_dead_stock_markdown_loss_rate": 0.50,
    "fallback_expedite_cost_rate": 0.15,
    "fallback_supplier_risk_cost_rate": 0.05,
    "fallback_stockout_probability": 0.20,
}

INVENTORY_COST_RISK_THRESHOLDS = {
    "low_total_cost": 250,
    "medium_total_cost": 1000,
    "high_total_cost": 3000,
    "critical_total_cost": 7500,
    "high_stockout_cost": 1000,
    "high_expiry_cost": 500,
    "high_overstock_cost": 750,
    "high_recommended_order_cost": 2500,
    "high_projected_holding_cost": 750,
}

INVENTORY_COST_DRIVER_TYPES = [
    "HOLDING_COST",
    "ORDERING_COST",
    "PURCHASE_COST",
    "STOCKOUT_COST",
    "OVERSTOCK_COST",
    "EXPIRY_COST",
    "DEAD_STOCK_COST",
    "SUPPLIER_RISK_COST",
    "STORAGE_SPACE_COST",
    "HANDLING_COST",
    "PHASE4_REVIEW_COST_RISK",
    "LOW_COST_NORMAL",
]

INVENTORY_COST_ACTIONS = [
    "NO_COST_ACTION_REQUIRED",
    "EXPEDITE_REPLENISHMENT",
    "REDUCE_FUTURE_ORDERS",
    "MARKDOWN_OR_RETURN_STOCK",
    "SCRAP_OR_QUARANTINE_EXPIRED",
    "LIQUIDATE_DEAD_STOCK",
    "REVIEW_SUPPLIER_COST_RISK",
    "REVIEW_POLICY_PARAMETERS",
    "JUSTIFY_HIGHER_HOLDING_COST",
    "WAIT_FOR_TRIGGER",
]

INVENTORY_COST_RISK_LEVELS = [
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
]

WAREHOUSE_SLOT_CONFIG = {
    "receiving_x": 0,
    "receiving_y": 0,
    "shipping_x": 0,
    "shipping_y": 0,
    "default_location_x": 0,
    "default_location_y": 0,
    "default_location_z": 0,
    "default_pick_face_distance_m": 10,
    "default_unit_volume_m3": 0.01,
    "default_unit_weight_kg": 1.0,
    "default_max_stack_height_m": 1.8,
    "default_location_capacity_m3": 10.0,
    "default_location_capacity_kg": 1000.0,
    "default_storage_cost_per_m3": 4.0,
    "default_travel_speed_m_per_min": 60.0,
    "default_travel_cost_per_meter": 0.02,
    "default_handling_time_min_per_unit": 0.05,
    "default_handling_cost_per_min": 0.30,
}

WAREHOUSE_ZONE_COST_MULTIPLIERS = {
    "FAST_PICK": 1.30,
    "CASE_PICKING": 1.15,
    "EACH_PICKING": 1.20,
    "PALLET_STORAGE": 1.00,
    "BULK_STORAGE": 0.80,
    "SLOW_PICK": 0.70,
    "TEMPERATURE_CONTROLLED": 1.50,
    "SECURITY_CONTROLLED": 1.40,
    "QUARANTINE": 1.10,
    "RETURNS": 1.00,
    "CROSSDOCKING": 1.25,
    "DEFAULT": 1.00,
}

WAREHOUSE_SLOT_PRIORITY_WEIGHTS = {
    "abc": 0.20,
    "fsn": 0.20,
    "movement": 0.15,
    "vitality": 0.10,
    "perishability": 0.10,
    "temperature": 0.10,
    "security": 0.05,
    "travel_distance": 0.10,
}

WAREHOUSE_TRAVEL_THRESHOLDS = {
    "fast_moving_max_distance_m": 30,
    "a_class_max_distance_m": 40,
    "medium_distance_m": 75,
    "high_distance_m": 120,
    "fast_moving_max_one_way_distance_m": 30,
    "fast_moving_max_total_route_distance_m": 60,
    "a_class_max_one_way_distance_m": 40,
    "a_class_max_total_route_distance_m": 80,
    "prefer_existing_location_distance_fields": True,
}

WAREHOUSE_UTILIZATION_THRESHOLDS = {
    "target_location_utilization_min_pct": 50,
    "target_location_utilization_max_pct": 90,
    "over_capacity_pct": 100,
    "projected_over_capacity_pct": 100,
    "warehouse_high_utilization_pct": 85,
    "warehouse_over_capacity_pct": 100,
}

WAREHOUSE_Z_LEVEL_RULES = {
    "low_level_max_z": 1,
    "medium_level_max_z": 3,
    "high_level_min_z": 4,
    "heavy_item_weight_kg_threshold": 15,
    "fast_moving_max_preferred_z": 2,
    "fragile_max_preferred_z": 2,
}

WAREHOUSE_BATCH_STATUS_TYPES = [
    "EXPIRED_BATCH",
    "NEAR_EXPIRY_BATCH",
    "HEALTHY_BATCH",
    "UNKNOWN_BATCH_STATUS",
]

WAREHOUSE_BATCH_ZONE_RULES = {
    "expired_batch_zone": "QUARANTINE",
    "near_expiry_batch_zone": "FAST_PICK",
    "healthy_batch_zone_fallback": "SLOW_PICK",
    "replenishment_zone_fallback": "RECEIVING",
    "near_expiry_requires_fefo": True,
    "expired_requires_quarantine": True,
}

WAREHOUSE_BATCH_QUANTITY_RULES = {
    "active_batch_quantity_min": 0.0001,
    "ignore_zero_quantity_batches_for_actions": True,
    "keep_zero_quantity_batches_for_traceability": True,
}

WAREHOUSE_STAGING_RULES = {
    "receiving_zones": ["RECEIVING", "PUTAWAY", "CROSSDOCKING"],
    "staging_location_role": "REPLENISHMENT_STAGING",
    "flag_projected_staging_over_capacity": True,
    "flag_sku_if_replenishment_location_over_capacity": True,
    "allow_projected_receiving_over_capacity_as_warning_only": True,
}

WAREHOUSE_VISUAL_STATUS_GROUPS = [
    "PRIMARY_STORAGE",
    "REPLENISHMENT_STAGING",
    "QUARANTINE_EXPIRED",
    "FEFO_NEAR_EXPIRY",
    "TRACE_ONLY_BATCH",
    "OVER_CAPACITY",
    "PROJECTED_OVER_CAPACITY",
    "CAPACITY_PRESSURE",
    "NO_FEASIBLE_LOCATION",
    "NORMAL",
]

WAREHOUSE_VISUAL_CONFIG = {
    "generate_html_maps": True,
    "generate_2d_map": True,
    "generate_3d_map": True,
    "default_cell_width": 1,
    "default_cell_height": 1,
    "default_zone": "UNKNOWN_ZONE",
    "default_visual_color_group": "NORMAL",
    "hide_trace_only_batches_from_physical_map": True,
    "include_traceability_layer": True,
    "include_replenishment_layer": True,
    "include_batch_layer": True,
    "include_capacity_layer": True,
    "include_travel_layer": True,
    "include_z_level_layer": True,
}

WAREHOUSE_VISUAL_COLOR_GROUPS = {
    "STOCKOUT": "RED",
    "ZERO_STOCK": "RED",
    "REORDER_NOW": "ORANGE",
    "CRITICAL_LOW_STOCK": "ORANGE",
    "APPROACHING_REORDER_POINT": "YELLOW",
    "OVERSTOCK": "ORANGE",
    "PRIMARY_STORAGE": "GREEN",
    "REPLENISHMENT_STAGING": "BLUE",
    "QUARANTINE_EXPIRED": "PURPLE",
    "FEFO_NEAR_EXPIRY": "YELLOW",
    "TRACE_ONLY_BATCH": "GRAY",
    "CURRENT_OVER_CAPACITY": "RED",
    "PROJECTED_OVER_CAPACITY": "ORANGE",
    "CAPACITY_PRESSURE": "YELLOW",
    "TRAVEL_RISK": "ORANGE",
    "Z_LEVEL_WARNING": "YELLOW",
    "NO_FEASIBLE_LOCATION": "RED",
    "NORMAL": "GREEN",
    "UNKNOWN": "GRAY",
}

WAREHOUSE_VISUAL_LAYER_TYPES = [
    "LOCATION_BASE",
    "PRIMARY_STORAGE",
    "REPLENISHMENT_STAGING",
    "QUARANTINE_EXPIRED",
    "FEFO_NEAR_EXPIRY",
    "TRACEABILITY_ONLY",
    "CAPACITY_STATUS",
    "TRAVEL_RISK",
    "Z_LEVEL_RISK",
]

WAREHOUSE_VISUAL_WARNING_PRIORITY = [
    "NO_FEASIBLE_LOCATION_FOUND",
    "CURRENT_LOCATION_OVER_CAPACITY",
    "PROJECTED_LOCATION_OVER_CAPACITY",
    "REPLENISHMENT_STAGING_OVER_CAPACITY",
    "RECEIVING_CAPACITY_REVIEW_REQUIRED",
    "STOCKOUT",
    "EXPIRED_BATCH_ASSIGNED_TO_QUARANTINE",
    "ACTIVE_EXPIRED_BATCH_ASSIGNED_TO_QUARANTINE",
    "FAST_MOVING_ITEM_TOO_FAR",
    "FAST_MOVING_ITEM_NOT_ERGONOMIC",
    "FRAGILE_ITEM_HIGH_LEVEL",
    "HEAVY_ITEM_NOT_LOW_LEVEL",
    "PROJECTED_CAPACITY_PRESSURE",
    "NEAR_EXPIRY_BATCH_ASSIGNED_TO_FEFO",
    "ACTIVE_NEAR_EXPIRY_BATCH_ASSIGNED_TO_FEFO",
]

WAREHOUSE_HANDLING_RULES = {
    "heavy_item_weight_kg_threshold": 15,
    "forklift_weight_kg_threshold": 30,
    "pallet_requires_forklift": True,
    "heavy_low_storage_does_not_always_require_forklift": True,
    "fragile_prefers_low_level": True,
    "fast_moving_prefers_ergonomic_level": True,
}

WAREHOUSE_SLOT_WARNING_CODES = [
    "LOCATION_OVER_CAPACITY",
    "INSUFFICIENT_SPACE_AFTER_ORDER",
    "FORKLIFT_ACCESS_REQUIRED_BUT_MISSING",
    "TEMPERATURE_CONTROL_REQUIRED_BUT_MISSING",
    "SECURITY_REQUIRED_BUT_MISSING",
    "HEAVY_ITEM_NOT_LOW_LEVEL",
    "FAST_MOVING_ITEM_NOT_ERGONOMIC",
    "FRAGILE_ITEM_HIGH_LEVEL",
    "FAST_MOVING_ITEM_TOO_FAR",
    "A_CLASS_ITEM_TOO_FAR",
    "PERISHABLE_ITEM_NEEDS_FEFO_ACCESS",
    "FEFO_REQUIRED_BUT_NOT_SUPPORTED",
    "HIGH_TRAVEL_DISTANCE",
    "LOW_LOCATION_UTILIZATION",
    "MISSING_LOCATION_DATA",
    "MISSING_SKU_STORAGE_REQUIREMENTS",
    "MISSING_CURRENT_LOCATION_FOR_REBASE",
    "PROJECTED_CAPACITY_PRESSURE",
    "NO_FEASIBLE_LOCATION_FOUND",
    "SLOW_OR_NON_MOVING_ITEM_IN_FAST_PICK",
    "PRIME_SPACE_USED_BY_SLOW_ITEM",
    "WHOLE_SKU_QUARANTINE_AVOIDED_BY_BATCH_SPLIT",
    "EXPIRED_BATCH_ASSIGNED_TO_QUARANTINE",
    "NEAR_EXPIRY_BATCH_ASSIGNED_TO_FEFO",
    "HEALTHY_BATCH_ASSIGNED_TO_NORMAL_STORAGE",
    "REPLENISHMENT_ASSIGNED_TO_NORMAL_STORAGE",
    "CURRENT_LOCATION_UTILIZATION_REBASED",
    "TRAVEL_THRESHOLD_USES_TOTAL_ROUTE",
    "TRAVEL_THRESHOLD_USES_ONE_WAY",
    "CAPABILITY_MATCH_ZONE_MISMATCH",
    "ZERO_QUANTITY_EXPIRED_BATCH_TRACE_ONLY",
    "ZERO_QUANTITY_NEAR_EXPIRY_BATCH_TRACE_ONLY",
    "ACTIVE_EXPIRED_BATCH_ASSIGNED_TO_QUARANTINE",
    "ACTIVE_NEAR_EXPIRY_BATCH_ASSIGNED_TO_FEFO",
    "ACTIVE_HEALTHY_BATCH_ASSIGNED_TO_NORMAL_STORAGE",
    "BATCH_LEVEL_LOCATION_UTILIZATION_APPLIED",
    "BATCH_LEVEL_LOCATION_UTILIZATION_NOT_APPLIED",
    "SKU_VOLUME_SPLIT_BY_BATCH_STATUS",
    "CAPABILITY_MATCH_NON_EXACT_ZONE",
    "BATCH_QUANTITY_RECONCILIATION_REVIEW",
    "NO_ACTIVE_BATCH_QUANTITY",
    "REPLENISHMENT_STAGING_OVER_CAPACITY",
    "RECEIVING_CAPACITY_REVIEW_REQUIRED",
    "SKU_CAUSES_PROJECTED_STAGING_PRESSURE",
    "PROJECTED_LOCATION_OVER_CAPACITY",
    "CURRENT_LOCATION_OVER_CAPACITY",
    "TRACE_ONLY_BATCH_EXCLUDED_FROM_PHYSICAL_MAP",
    "PRIMARY_REPLENISHMENT_LOCATION_ROLE_SPLIT",
    "LOCATION_ROLE_MIXED_USAGE_REVIEW",
    "REPLENISHMENT_STAGED_IN_RECEIVING",
    "TRACE_ONLY_BATCH_RETAINED_FOR_HISTORY",
    "BATCH_VISUAL_EXCLUDED_ZERO_QUANTITY",
    "LOCATION_HAS_PRIMARY_AND_STAGING_ROLES",
    "LOCATION_HAS_QUARANTINE_OR_FEFO_ROLE",
    "CURRENT_VS_PROJECTED_CAPACITY_SPLIT",
]

WAREHOUSE_SLOT_STATUS_TYPES = [
    "ASSIGNED",
    "ASSIGNED_WITH_WARNINGS",
    "NO_FEASIBLE_LOCATION",
    "REVIEW_REQUIRED",
]

WAREHOUSE_SLOT_ACTION_TYPES = [
    "KEEP_CURRENT_LOCATION",
    "MOVE_TO_FAST_PICK",
    "MOVE_TO_SLOW_PICK",
    "MOVE_TO_BULK_STORAGE",
    "MOVE_TO_TEMPERATURE_CONTROLLED",
    "MOVE_TO_SECURITY_CONTROLLED",
    "MOVE_TO_LOWER_LEVEL",
    "REVIEW_CAPACITY_BEFORE_ORDER",
    "REVIEW_FEFO_ROTATION",
    "REVIEW_MANUALLY",
    "SPLIT_BATCH_STORAGE",
    "QUARANTINE_EXPIRED_BATCHES_ONLY",
    "QUARANTINE_EXPIRED_BATCH",
    "PRIORITIZE_NEAR_EXPIRY_FEFO",
    "NO_ACTIVE_BATCH_QUANTITY",
    "MOVE_SLOW_ITEM_OUT_OF_FAST_PICK",
]

RE_EVALUATION_CONFIG = {
    "enabled": True,
    "default_review_period_days": 30,
    "minimum_confidence_for_auto_suggestion": 0.60,
    "human_review_confidence_threshold": 0.75,
    "max_service_level_adjustment_per_cycle": 0.03,
    "max_safety_stock_adjustment_pct_per_cycle": 0.20,
    "max_reorder_point_adjustment_pct_per_cycle": 0.20,
    "max_order_cap_adjustment_pct_per_cycle": 0.25,
    "min_service_level": 0.70,
    "max_service_level": 0.99,
    "protect_vital_skus": True,
    "protect_critical_priority_skus": True,
    "do_not_reduce_vital_below": 0.95,
    "do_not_reduce_critical_below": 0.98,
    "do_not_reduce_fast_moving_below": 0.90,
    "do_not_reduce_abc_a_below": 0.90,
    "recommend_only": True,
}

RE_EVALUATION_SIGNAL_WEIGHTS = {
    "stockout": 0.25,
    "zero_stock": 0.12,
    "critical_low_stock": 0.15,
    "reorder_now": 0.10,
    "overstock": 0.18,
    "expiry": 0.15,
    "non_moving": 0.12,
    "dead_stock": 0.15,
    "supplier_risk": 0.10,
    "warehouse_capacity": 0.12,
    "travel_or_z_warning": 0.06,
    "forecast_uncertainty": 0.10,
    "high_cost": 0.15,
}

RE_EVALUATION_THRESHOLDS = {
    "high_total_relevant_cost": 3000,
    "critical_total_relevant_cost": 7500,
    "high_stockout_cost": 1000,
    "high_holding_or_overstock_cost": 750,
    "high_expiry_cost": 500,
    "high_order_cost": 2500,
    "high_days_of_supply": 90,
    "perishable_high_days_of_supply": 30,
    "non_moving_high_days_of_supply": 14,
    "projected_capacity_pressure_pct": 85,
    "projected_over_capacity_pct": 100,
    "low_forecast_confidence": 0.60,
    "high_procurement_risk_score": 0.50,
    "high_travel_risk_count": 1,
}

RE_EVALUATION_ACTION_TYPES = [
    "INCREASE_SERVICE_LEVEL",
    "DECREASE_SERVICE_LEVEL",
    "KEEP_SERVICE_LEVEL",
    "INCREASE_SAFETY_STOCK",
    "DECREASE_SAFETY_STOCK",
    "KEEP_SAFETY_STOCK",
    "INCREASE_REORDER_POINT",
    "DECREASE_REORDER_POINT",
    "KEEP_REORDER_POINT",
    "INCREASE_ORDER_CAP",
    "DECREASE_ORDER_CAP",
    "KEEP_ORDER_CAP",
    "REVIEW_INVENTORY_POLICY",
    "REVIEW_SUPPLIER_RISK",
    "REVIEW_WAREHOUSE_SLOT",
    "REVIEW_RECEIVING_CAPACITY",
    "REVIEW_EXPIRY_MARKDOWN_OR_RETURN",
    "REVIEW_PHASE4_PRODUCTION_LOGIC",
    "NO_PARAMETER_CHANGE",
]

RE_EVALUATION_REVIEW_LEVELS = [
    "NO_REVIEW",
    "LOW_REVIEW",
    "MEDIUM_REVIEW",
    "HIGH_REVIEW",
    "MANDATORY_REVIEW",
]

RE_EVALUATION_DIRECTION_TYPES = [
    "INCREASE_BUFFER",
    "DECREASE_BUFFER",
    "KEEP_STABLE",
    "MIXED_SIGNALS",
    "REVIEW_ONLY",
]

RE_EVALUATION_RECOMMENDATION_STRENGTH = [
    "DO_NOT_CHANGE",
    "REVIEW_ONLY",
    "SUGGESTED_CHANGE",
    "STRONGLY_SUGGESTED_CHANGE",
]

RE_EVALUATION_AUTO_APPLY = {
    "auto_apply_allowed_default": False,
    "allow_auto_apply_in_step_11": False,
}

RE_EVALUATION_GUARDRAIL_ACTIONS = [
    "NO_GUARDRAIL_APPLIED",
    "GUARDRAIL_PROTECTED_NO_REDUCTION",
    "GUARDRAIL_LIMITED_INCREASE",
    "GUARDRAIL_LIMITED_DECREASE",
    "ROP_LEAD_TIME_GUARDRAIL_APPLIED",
    "ROP_REVIEW_REQUIRED",
]

RE_EVALUATION_ORDER_REVIEW_TYPES = [
    "NO_ORDER_REVIEW",
    "RECEIVING_CAPACITY_ORDER_REVIEW",
    "MOQ_OVERSTOCK_REVIEW",
    "BATCH_ROUNDING_REVIEW",
    "YIELD_REVIEW",
    "PERISHABILITY_CAP_REVIEW",
    "PHASE4_ORDER_REVIEW",
    "SUPPLIER_REVIEW_BEFORE_ORDER",
    "QUANTITY_CONSTRAINT_REVIEW_ONLY",
]

RE_EVALUATION_EOQ_REVIEW_TYPES = [
    "NO_EOQ_REVIEW",
    "REVIEW_EOQ_INPUTS",
    "REVIEW_ORDER_COST",
    "REVIEW_HOLDING_COST",
    "REVIEW_DEMAND_INPUT",
    "REVIEW_EOQ_CONSTRAINTS",
]

SCENARIO_OPTIMIZATION_CONFIG = {
    "enabled": True,
    "recommend_only": True,
    "auto_apply_allowed": False,
    "max_scenarios_per_sku": 25,
    "max_combined_levers_per_scenario": 3,
    "include_baseline_scenario": True,
    "include_single_lever_scenarios": True,
    "include_combined_scenarios": True,
    "use_signal_gated_generation": True,
    "reject_contradictory_scenarios": True,
    "select_lowest_feasible_cost": True,
    "allow_infeasible_recommendation_only_if_no_feasible_exists": False,
    "human_review_required_for_mixed_signals": True,
    "human_review_required_for_phase4_items": True,
    "human_review_required_for_supplier_review": True,
    "human_review_required_for_projected_receiving_overcapacity": True,
}

SCENARIO_LEVER_TYPES = {
    "buffer_strategy": ["CURRENT_BUFFER", "INCREASE_BUFFER", "DECREASE_BUFFER", "MINIMUM_SAFE_BUFFER", "SERVICE_LEVEL_GUARDED_BUFFER"],
    "supplier_strategy": ["CURRENT_SUPPLIER", "CHEAPEST_SUPPLIER", "FAST_RELIABLE_SUPPLIER", "MOST_RELIABLE_SUPPLIER", "BALANCED_SUPPLIER", "SUPPLIER_REVIEW_ONLY"],
    "delivery_strategy": ["NORMAL_DELIVERY", "SPLIT_DELIVERY", "EXPEDITE_DELIVERY", "DELAY_NONURGENT_ORDER", "NO_ORDER_WAIT_FOR_TRIGGER"],
    "order_cap_strategy": ["CURRENT_ORDER_CAP", "TIGHTEN_ORDER_CAP", "LOOSEN_ORDER_CAP", "CAP_BY_EXPIRY_OR_MOVEMENT"],
    "expiry_strategy": ["NO_EXPIRY_ACTION", "MARKDOWN_NEAR_EXPIRY", "RETURN_TO_SUPPLIER_IF_ALLOWED", "QUARANTINE_OR_SCRAP_EXPIRED", "LIQUIDATE_DEAD_STOCK"],
    "warehouse_strategy": ["CURRENT_WAREHOUSE_PLAN", "REVIEW_RECEIVING_CAPACITY", "REVIEW_SLOT_LOCATION", "REVIEW_TRAVEL_DISTANCE", "REVIEW_Z_LEVEL_ERGONOMICS", "REVIEW_QUARANTINE_OR_FEFO"],
}

SCENARIO_GENERATION_RULES = {
    "stockout_generates_buffer_scenarios": True,
    "stockout_generates_fast_supplier_scenarios": True,
    "supplier_risk_generates_supplier_scenarios": True,
    "receiving_pressure_generates_split_delivery_scenarios": True,
    "overstock_generates_decrease_buffer_scenarios": True,
    "expiry_generates_expiry_action_scenarios": True,
    "non_moving_generates_order_cap_scenarios": True,
    "travel_warning_generates_slot_review_scenarios": True,
    "z_warning_generates_z_review_scenarios": True,
    "phase4_generates_review_only_scenarios": True,
}

SCENARIO_CONTRADICTION_RULES = [
    ["INCREASE_BUFFER", "DECREASE_BUFFER"],
    ["INCREASE_BUFFER", "MINIMUM_SAFE_BUFFER"],
    ["EXPEDITE_DELIVERY", "DELAY_NONURGENT_ORDER"],
    ["EXPEDITE_DELIVERY", "NO_ORDER_WAIT_FOR_TRIGGER"],
    ["SPLIT_DELIVERY", "NO_ORDER_WAIT_FOR_TRIGGER"],
    ["LOOSEN_ORDER_CAP", "TIGHTEN_ORDER_CAP"],
    ["MARKDOWN_NEAR_EXPIRY", "INCREASE_BUFFER"],
    ["LIQUIDATE_DEAD_STOCK", "INCREASE_BUFFER"],
    ["RETURN_TO_SUPPLIER_IF_ALLOWED", "INCREASE_BUFFER"],
    ["NO_EXPIRY_ACTION", "MARKDOWN_NEAR_EXPIRY"],
    ["NO_EXPIRY_ACTION", "QUARANTINE_OR_SCRAP_EXPIRED"],
]

SCENARIO_COST_WEIGHTS = {
    "purchase_cost": 1.00,
    "ordering_cost": 1.00,
    "holding_cost": 1.00,
    "stockout_cost": 1.00,
    "overstock_cost": 1.00,
    "expiry_cost": 1.00,
    "dead_stock_cost": 1.00,
    "supplier_risk_cost": 1.00,
    "warehouse_space_cost": 1.00,
    "warehouse_travel_cost": 1.00,
    "receiving_capacity_penalty": 1.00,
    "manual_review_penalty": 0.25,
    "constraint_violation_penalty": 10.00,
}

SCENARIO_COST_DEFAULTS = {
    "fallback_purchase_unit_cost": 1.0,
    "fallback_ordering_cost": 75.0,
    "fallback_holding_cost_per_unit": 0.20,
    "fallback_stockout_cost_per_unit": 25.0,
    "fallback_overstock_cost_per_unit": 5.0,
    "fallback_expiry_cost_per_unit": 10.0,
    "fallback_supplier_risk_cost_rate": 0.05,
    "fallback_receiving_capacity_penalty": 500.0,
    "fallback_manual_review_penalty": 100.0,
    "fallback_constraint_violation_penalty": 10000.0,
}

SCENARIO_FEASIBILITY_RULES = {
    "vital_min_service_level": 0.95,
    "critical_priority_min_service_level": 0.98,
    "abc_a_min_service_level": 0.90,
    "fast_moving_min_service_level": 0.90,
    "max_projected_warehouse_utilization_pct": 100,
    "max_projected_receiving_utilization_pct": 100,
    "expired_units_not_sellable": True,
    "trace_only_batches_not_physical_stock": True,
    "supplier_review_blocks_auto_selection": True,
    "phase4_blocks_final_policy_selection": True,
    "allow_review_required_scenario_as_feasible_with_human_review": True,
}

SCENARIO_IMPACT_FACTORS = {
    "increase_buffer_service_level_delta": 0.02,
    "decrease_buffer_service_level_delta": -0.02,
    "increase_buffer_safety_stock_multiplier": 1.15,
    "decrease_buffer_safety_stock_multiplier": 0.85,
    "minimum_safe_buffer_safety_stock_multiplier": 0.75,
    "increase_buffer_rop_multiplier": 1.15,
    "decrease_buffer_rop_multiplier": 0.85,
    "tighten_order_cap_multiplier": 0.75,
    "loosen_order_cap_multiplier": 1.25,
    "split_delivery_receiving_penalty_multiplier": 0.50,
    "split_delivery_ordering_cost_multiplier": 1.20,
    "expedite_delivery_cost_multiplier": 1.25,
    "fast_supplier_purchase_cost_multiplier": 1.10,
    "fast_supplier_stockout_risk_multiplier": 0.60,
    "reliable_supplier_risk_multiplier": 0.50,
    "cheapest_supplier_purchase_cost_multiplier": 0.90,
    "cheapest_supplier_risk_multiplier": 1.25,
    "markdown_expiry_cost_multiplier": 0.60,
    "return_supplier_expiry_cost_multiplier": 0.40,
    "liquidation_dead_stock_cost_multiplier": 0.50,
}

SCENARIO_SELECTION_STATUS = [
    "SELECTED_LOWEST_FEASIBLE_COST",
    "SELECTED_LOWEST_COST_WITH_HUMAN_REVIEW",
    "NO_FEASIBLE_SCENARIO_FOUND",
    "BASELINE_SELECTED",
    "REVIEW_ONLY_SELECTED",
]

SCENARIO_COST_REPORTING = {
    "separate_operational_and_penalty_costs": True,
    "selection_cost_basis": "PENALTY_ADJUSTED_TOTAL_COST",
    "report_operational_savings_separately": True,
    "report_penalty_avoidance_separately": True,
    "warn_when_savings_are_penalty_driven": True,
    "penalty_driven_saving_share_threshold": 0.50,
}

SCENARIO_COST_COMPONENT_GROUPS = {
    "operational_cost_components": [
        "scenario_purchase_cost",
        "scenario_ordering_cost",
        "scenario_holding_cost",
        "scenario_stockout_cost",
        "scenario_overstock_cost",
        "scenario_expiry_cost",
        "scenario_dead_stock_cost",
        "scenario_supplier_risk_cost",
        "scenario_warehouse_space_cost",
        "scenario_warehouse_travel_cost",
    ],
    "penalty_cost_components": [
        "scenario_receiving_capacity_penalty",
        "scenario_manual_review_penalty",
        "scenario_constraint_violation_penalty",
    ],
}

SCENARIO_SAVING_INTERPRETATION_TYPES = [
    "OPERATIONAL_SAVING",
    "PENALTY_AVOIDANCE",
    "MIXED_OPERATIONAL_AND_PENALTY_SAVING",
    "NO_SAVING",
    "COST_INCREASE_WITH_RISK_REDUCTION",
    "REVIEW_REQUIRED",
]

SCENARIO_FEASIBILITY_SEVERITY_TYPES = [
    "NO_ISSUE",
    "HARD_BLOCKER",
    "MAJOR_RISK",
    "REVIEW_REQUIRED",
    "SOFT_WARNING",
]

SCENARIO_CONSTRAINT_SEVERITY = {
    "VITAL_SERVICE_LEVEL_BELOW_MIN": "HARD_BLOCKER",
    "CRITICAL_PRIORITY_SERVICE_LEVEL_BELOW_MIN": "HARD_BLOCKER",
    "ABC_A_SERVICE_LEVEL_BELOW_MIN": "MAJOR_RISK",
    "FAST_MOVING_SERVICE_LEVEL_BELOW_MIN": "MAJOR_RISK",
    "EXPIRED_UNITS_COUNTED_AS_SELLABLE": "HARD_BLOCKER",
    "TRACE_ONLY_BATCHES_COUNTED_AS_PHYSICAL": "HARD_BLOCKER",
    "NEGATIVE_SCENARIO_ORDER_QUANTITY": "HARD_BLOCKER",
    "ROP_BELOW_SAFETY_STOCK": "HARD_BLOCKER",
    "ROP_BELOW_SAFETY_STOCK_PLUS_LEAD_TIME_DEMAND": "HARD_BLOCKER",
    "PROJECTED_WAREHOUSE_OVER_CAPACITY_WITHOUT_REVIEW": "MAJOR_RISK",
    "PROJECTED_RECEIVING_OVER_CAPACITY_WITHOUT_SPLIT_OR_REVIEW": "MAJOR_RISK",
    "SUPPLIER_REVIEW_REQUIRED_WITH_SUPPLIER_CHANGE": "REVIEW_REQUIRED",
    "PHASE4_FINAL_POLICY_WITHOUT_REVIEW": "REVIEW_REQUIRED",
    "FORECAST_CONFIDENCE_LOW": "SOFT_WARNING",
    "SUPPLIER_RISK_REMAINS": "SOFT_WARNING",
    "TRAVEL_WARNING_REMAINS": "SOFT_WARNING",
    "Z_LEVEL_WARNING_REMAINS": "SOFT_WARNING",
}

SCENARIO_SEVERITY_PENALTIES = {
    "HARD_BLOCKER": 100000,
    "MAJOR_RISK": 3000,
    "REVIEW_REQUIRED": 500,
    "SOFT_WARNING": 100,
    "NO_ISSUE": 0,
}

SCENARIO_PENALTY_CAPS = {
    "max_constraint_penalty_per_scenario": 100000,
    "max_major_risk_penalty_per_scenario": 10000,
    "max_review_penalty_per_scenario": 2000,
    "max_soft_warning_penalty_per_scenario": 1000,
}

SCENARIO_RECEIVING_CAPACITY_PENALTY = {
    "base_penalty": 1500,
    "over_capacity_multiplier": 1.00,
    "capacity_pressure_multiplier": 0.50,
    "split_delivery_penalty_multiplier": 0.25,
    "review_receiving_penalty_multiplier": 0.50,
    "split_and_review_penalty_multiplier": 0.10,
}

SCENARIO_SELECTION_MODES = [
    "LOWEST_PENALTY_ADJUSTED_COST",
    "LOWEST_OPERATIONAL_COST_WITH_ACCEPTABLE_RISK",
    "LOWEST_COST_NO_MANDATORY_REVIEW",
]

SCENARIO_SELECTION_CONFIG = {
    "selection_mode": "LOWEST_PENALTY_ADJUSTED_COST",
    "acceptable_major_risk_count": 0,
    "acceptable_hard_blocker_count": 0,
    "allow_review_required_selection": True,
    "prefer_no_review_if_cost_difference_pct_below": 0.05,
}

INVENTORY_CONSOLIDATION_CONFIG = {
    "enabled": True,
    "recommend_only": True,
    "auto_apply_allowed": False,
    "manager_outputs_enabled": True,
    "include_debug_references": True,
    "include_cost_explanations": True,
    "include_human_review_queue": True,
    "include_action_plan": True,
    "include_risk_register": True,
    "include_dashboard_flat_file": True,
    "max_reason_length": 500,
}

FINAL_DECISION_PRIORITY_LEVELS = [
    "URGENT",
    "HIGH",
    "MEDIUM",
    "LOW",
    "NO_ACTION",
]

FINAL_DECISION_ACTION_TYPES = [
    "EXPEDITE_REPLENISHMENT",
    "ORDER_RECOMMENDED_QUANTITY",
    "USE_SELECTED_OPTIMIZED_SCENARIO",
    "SPLIT_DELIVERY",
    "USE_FAST_RELIABLE_SUPPLIER",
    "REDUCE_BUFFER",
    "INCREASE_BUFFER",
    "TIGHTEN_ORDER_CAP",
    "LOOSEN_ORDER_CAP",
    "MARKDOWN_NEAR_EXPIRY",
    "RETURN_TO_SUPPLIER_REVIEW",
    "QUARANTINE_OR_SCRAP_EXPIRED",
    "LIQUIDATE_DEAD_STOCK",
    "WAIT_FOR_TRIGGER",
    "MONITOR_ONLY",
    "REVIEW_PHASE4_PRODUCTION_LOGIC",
    "REVIEW_SUPPLIER_BEFORE_ORDER",
    "REVIEW_WAREHOUSE_CAPACITY",
    "REVIEW_WAREHOUSE_SLOT",
    "REVIEW_POLICY_PARAMETERS",
    "NO_ACTION",
]

FINAL_REVIEW_TYPES = [
    "NO_REVIEW_REQUIRED",
    "PROCUREMENT_REVIEW",
    "SUPPLIER_REVIEW",
    "WAREHOUSE_REVIEW",
    "EXPIRY_REVIEW",
    "POLICY_REVIEW",
    "PHASE4_REVIEW",
    "FINANCE_COST_REVIEW",
    "MANDATORY_MULTI_DEPARTMENT_REVIEW",
]

FINAL_RISK_TYPES = [
    "STOCKOUT_RISK",
    "OVERSTOCK_RISK",
    "EXPIRY_RISK",
    "DEAD_STOCK_RISK",
    "SUPPLIER_RISK",
    "WAREHOUSE_CAPACITY_RISK",
    "RECEIVING_STAGING_RISK",
    "TRAVEL_OR_SLOT_RISK",
    "POLICY_RISK",
    "PHASE4_PRODUCTION_RISK",
    "COST_RISK",
    "DATA_QUALITY_RISK",
]

FINAL_MANAGER_STATUS_TYPES = [
    "TAKE_ACTION_NOW",
    "REVIEW_BEFORE_ACTION",
    "MONITOR",
    "NO_ACTION_REQUIRED",
]

FINAL_DECISION_WEIGHTS = {
    "inventory_status": 0.25,
    "action_priority": 0.20,
    "cost_risk": 0.20,
    "optimization_status": 0.15,
    "human_review": 0.10,
    "warehouse_risk": 0.05,
    "supplier_risk": 0.05,
}

FINAL_REVIEW_SEVERITY_LEVELS = [
    "MANDATORY",
    "ADVISORY",
    "INFO_ONLY",
    "NO_REVIEW",
]

FINAL_REVIEW_GATE_TYPES = [
    "HARD_BLOCKER_GATE",
    "SELECTED_SCENARIO_REVIEW_GATE",
    "PHASE4_GATE",
    "SUPPLIER_CHANGE_GATE",
    "RECEIVING_CAPACITY_GATE",
    "EXPIRY_DISPOSITION_GATE",
    "FINANCE_COST_GATE",
    "POLICY_PARAMETER_GATE",
    "ADVISORY_WAREHOUSE_SIGNAL",
    "ADVISORY_SUPPLIER_SIGNAL",
    "ADVISORY_POLICY_SIGNAL",
    "ADVISORY_COST_SIGNAL",
    "INFO_WARNING_ONLY",
]

FINAL_REVIEW_SEVERITY_RULES = {
    "hard_blocker_is_mandatory": True,
    "selected_scenario_review_is_mandatory": True,
    "phase4_selected_policy_change_is_mandatory": True,
    "supplier_change_with_supplier_review_is_mandatory": True,
    "split_delivery_with_receiving_pressure_is_mandatory": True,
    "expiry_disposition_action_is_mandatory": True,
    "high_penalty_driven_saving_is_advisory": True,
    "warehouse_review_without_selected_warehouse_action_is_advisory": True,
    "supplier_review_without_supplier_change_is_advisory": True,
    "policy_review_without_parameter_change_is_advisory": True,
    "soft_warning_only_is_info": True,
}

FINAL_PRIORITY_TUNING = {
    "urgent_score_threshold": 70,
    "high_score_threshold": 45,
    "medium_score_threshold": 20,
    "low_score_threshold": 1,
    "mandatory_review_score_add": 10,
    "advisory_review_score_add": 3,
    "info_warning_score_add": 1,
    "soft_warning_score_add": 2,
    "major_risk_score_add": 10,
    "review_required_score_add": 5,
    "cost_high_score_add": 10,
    "cost_critical_score_add": 20,
    "stockout_score_add": 35,
    "zero_stock_score_add": 30,
    "critical_low_score_add": 25,
    "reorder_now_score_add": 20,
    "overstock_score_add": 12,
    "approaching_rop_score_add": 8,
    "vital_critical_stockout_override": True,
}

FINAL_MANAGER_STATUS_RULES = {
    "mandatory_review_goes_to_review_before_action": True,
    "advisory_review_only_can_be_take_action_or_monitor": True,
    "urgent_action_without_mandatory_review_goes_to_take_action_now": True,
    "high_action_without_mandatory_review_goes_to_take_action_now": True,
    "medium_or_low_with_advisory_review_goes_to_monitor": True,
    "no_action_goes_to_no_action_required": True,
}

FINAL_HUMAN_REVIEW_QUEUE_RULES = {
    "include_mandatory_reviews_only": True,
    "exclude_advisory_only_reviews": True,
    "exclude_info_only_reviews": True,
}
