"""Inventory policy selection layer for Phase 3.

This module selects the policy/model type only. Quantity calculations such as
safety stock, ROP, EOQ, base stock, and order-up-to levels are intentionally
left blank for the next step.
"""

from __future__ import annotations

import pandas as pd

from config import (
    DEFAULT_REVIEW_PERIOD_DAYS,
    POLICY_SELECTION_THRESHOLDS,
)


def build_inventory_policy_selection(
    planning_context: pd.DataFrame,
    inventory_classification: pd.DataFrame,
    inventory_service_levels: pd.DataFrame,
) -> pd.DataFrame:
    """Select an inventory policy type for every SKU."""
    merged = _merge_policy_inputs(planning_context, inventory_classification, inventory_service_levels)
    rows = []
    for _, row in merged.iterrows():
        model_type, policy_reason = _select_inventory_model_type(row)
        review_policy = _select_review_policy(model_type, row)
        review_period, review_period_reason = _select_review_period(row)
        urgency = _select_policy_urgency(row)
        procurement_flag, procurement_reason = _procurement_constraint_context(row)
        review_required, review_reason, phase4_review_flag = _policy_review_context(
            row,
            model_type,
            procurement_flag,
        )
        confidence, confidence_reason = _policy_selection_confidence(
            row,
            model_type,
            review_required,
            procurement_flag,
            phase4_review_flag,
        )

        result = _copy_output_fields(row)
        result.update(
            {
                "inventory_model_type": model_type,
                "review_policy": review_policy,
                "policy_selection_confidence": confidence,
                "policy_confidence_reason": confidence_reason,
                "policy_urgency": urgency,
                "policy_review_required": review_required,
                "policy_review_reason": review_reason,
                "policy_reason": policy_reason,
                "review_period_R": review_period,
                "review_period_reason": review_period_reason,
                "procurement_constraint_flag": procurement_flag,
                "procurement_constraint_reason": procurement_reason,
                "phase4_review_flag": phase4_review_flag,
            }
        )
        result.update(_step6_placeholders())
        rows.append(result)
    output = pd.DataFrame(rows)
    return output[_output_columns(output)]


def _merge_policy_inputs(
    planning_context: pd.DataFrame,
    inventory_classification: pd.DataFrame,
    inventory_service_levels: pd.DataFrame,
) -> pd.DataFrame:
    """Merge planning context, classification, and service-level outputs."""
    classification_columns = [
        "sku_id",
        "abc_class",
        "xyz_class",
        "fsn_class",
        "vitality_class",
        "seasonality_class",
        "perishability_class",
        "movement_class",
        "supplier_risk_class",
        "inventory_priority_class",
        "classification_score",
    ]
    service_columns = [
        "sku_id",
        "service_level_target",
        "safety_factor_z",
        "service_level_review_required",
        "service_level_re_evaluation_signal",
    ]
    merged = planning_context.copy()
    merged = merged.merge(_available_columns(inventory_classification, classification_columns), on="sku_id", how="left")
    merged = merged.merge(_available_columns(inventory_service_levels, service_columns), on="sku_id", how="left")
    return merged


def _select_inventory_model_type(row: pd.Series) -> tuple[str, str]:
    """Select the main inventory model type and explain why."""
    if _continuous_review_candidate(row):
        return (
            "CONTINUOUS_REVIEW_sQ",
            "Selected CONTINUOUS_REVIEW_sQ because SKU is critical, high service, stockout-prone, or needs close threshold monitoring.",
        )
    if _phase4_item(row) and _phase4_one_to_one_candidate(row):
        return (
            "ONE_TO_ONE_REPLACEMENT",
            "Selected ONE_TO_ONE_REPLACEMENT because SKU is component-like or Phase 4-ready and each issue may need replacement logic.",
        )
    if _event_based_candidate(row):
        return (
            "EVENT_BASED_REPLENISHMENT",
            "Selected EVENT_BASED_REPLENISHMENT because SKU is intermittent, low-moving, or should avoid holding excessive stock.",
        )
    if _base_stock_candidate(row):
        return (
            "BASE_STOCK",
            "Selected BASE_STOCK because SKU is an important buffer with variable demand or supplier uncertainty and should maintain a target inventory position.",
        )
    if _newsvendor_candidate(row):
        return (
            "NEWSVENDOR_CANDIDATE",
            "Selected NEWSVENDOR_CANDIDATE because SKU is seasonal/perishable and excess inventory creates spoilage or obsolescence risk.",
        )
    if _eoq_candidate(row):
        return (
            "EOQ",
            "Selected EOQ candidate because SKU has smooth repeated demand, low expiry risk, feasible supplier, and manageable procurement constraints.",
        )
    return (
        "PERIODIC_REVIEW_RS",
        "Selected PERIODIC_REVIEW_RS because SKU has normal priority, repeated demand, and periodic checking is sufficient.",
    )


def _continuous_review_candidate(row: pd.Series) -> bool:
    """Return True when close continuous monitoring is justified."""
    service_level = _float(row.get("service_level_target"))
    return bool(
        _bool(row.get("stockout_signal"))
        or row.get("inventory_priority_class") in {"CRITICAL_PRIORITY", "HIGH_PRIORITY"}
        or (row.get("vitality_class") in {"VITAL", "IMPORTANT"} and service_level >= POLICY_SELECTION_THRESHOLDS["high_service_level"])
        or (row.get("abc_class") == "A" and row.get("movement_class") == "FAST_MOVING")
        or _float(row.get("stockout_penalty_per_unit")) >= POLICY_SELECTION_THRESHOLDS["high_stockout_penalty"]
        or _float(row.get("stockout_units")) >= POLICY_SELECTION_THRESHOLDS["high_stockout_units"]
        or (
            row.get("vitality_class") in {"VITAL", "IMPORTANT"}
            and _float(row.get("demand_adjusted_procurement_risk_score")) >= POLICY_SELECTION_THRESHOLDS["high_supplier_risk_score"]
        )
    )


def _newsvendor_candidate(row: pd.Series) -> bool:
    """Return True for seasonal, perishable, or spoilage-risk SKUs."""
    seasonal = row.get("seasonality_class") in {
        "PEAK_SEASON",
        "OFF_SEASON",
        "SEASONAL_BUILDUP",
        "SEASONAL_DRAWDOWN",
        "SEASONAL_UNKNOWN",
    }
    perishable = (
        row.get("perishability_class") in {"SPOILAGE_RISK", "EXPIRY_TRACKED", "PERISHABLE"}
        or _bool(row.get("perishable"))
        or _bool(row.get("expiry_tracking_required"))
        or _bool(row.get("fefo_required"))
    )
    expiry_signal = (
        _bool(row.get("expiry_risk_signal"))
        or _float(row.get("near_expiry_units")) >= POLICY_SELECTION_THRESHOLDS["near_expiry_units_threshold"]
        or _float(row.get("expired_units")) >= POLICY_SELECTION_THRESHOLDS["expired_units_threshold"]
    )
    return bool((seasonal or perishable or expiry_signal) and row.get("inventory_priority_class") != "CRITICAL_PRIORITY")


def _event_based_candidate(row: pd.Series) -> bool:
    """Return True when replenishment should be triggered by events rather than constant holding."""
    low_demand = _float(row.get("average_daily_demand")) <= POLICY_SELECTION_THRESHOLDS["low_average_daily_demand"]
    low_movement = _float(row.get("movement_count")) <= POLICY_SELECTION_THRESHOLDS["low_movement_count"]
    intermittent = str(row.get("demand_behavior_class", "")).lower() in {"intermittent", "erratic"}
    return bool(
        row.get("movement_class") == "NON_MOVING"
        or _bool(row.get("dead_stock_signal"))
        or (_bool(row.get("non_moving_signal")) and row.get("vitality_class") != "VITAL")
        or (intermittent and (low_demand or low_movement) and row.get("vitality_class") != "VITAL")
    )


def _base_stock_candidate(row: pd.Series) -> bool:
    """Return True for repeated demand with uncertainty or supplier risk."""
    if _bool(row.get("stockout_signal")) or _bool(row.get("expiry_risk_signal")):
        return False
    if row.get("perishability_class") == "SPOILAGE_RISK":
        return False
    repeated = row.get("movement_class") in {"FAST_MOVING", "MEDIUM_MOVING", "SLOW_MOVING"}
    important_or_buffer = (
        row.get("vitality_class") in {"VITAL", "IMPORTANT"}
        or row.get("abc_class") in {"A", "B"}
        or row.get("push_pull_boundary_role") == "FINISHED_GOOD_BUFFER"
        or row.get("item_planning_type") == "FINISHED_GOOD"
    )
    uncertainty = (
        row.get("xyz_class") in {"Y", "Z"}
        or str(row.get("demand_behavior_class", "")).lower() in {"variable", "erratic"}
        or _float(row.get("coefficient_of_variation")) >= POLICY_SELECTION_THRESHOLDS["medium_cv"]
        or _float(row.get("lead_time_std_days")) > 3
        or row.get("demand_adjusted_procurement_risk_class") in {"MEDIUM", "HIGH"}
        or _float(row.get("demand_adjusted_procurement_risk_score")) >= POLICY_SELECTION_THRESHOLDS["high_supplier_risk_score"]
        or row.get("push_pull_boundary_role") == "FINISHED_GOOD_BUFFER"
        or row.get("item_planning_type") == "FINISHED_GOOD"
        or _bool(row.get("supplier_review_signal"))
        or _bool(row.get("watchlist_supplier_signal"))
    )
    return bool(repeated and important_or_buffer and uncertainty)


def _eoq_candidate(row: pd.Series) -> bool:
    """Return True when EOQ is an appropriate candidate for Step 6."""
    smooth = str(row.get("demand_behavior_class", "")).lower() == "smooth" or row.get("xyz_class") == "X"
    non_perishable = row.get("perishability_class") == "NON_PERISHABLE" and not _bool(row.get("expiry_risk_signal"))
    low_or_medium_risk = _float(row.get("demand_adjusted_procurement_risk_score")) < POLICY_SELECTION_THRESHOLDS["high_supplier_risk_score"]
    repeated = row.get("movement_class") in {"FAST_MOVING", "MEDIUM_MOVING", "SLOW_MOVING"}
    return bool(
        smooth
        and non_perishable
        and not _bool(row.get("stockout_signal"))
        and row.get("inventory_priority_class") not in {"CRITICAL_PRIORITY", "HIGH_PRIORITY"}
        and _bool(row.get("recommended_supplier_feasible"), True)
        and low_or_medium_risk
        and not _bool(row.get("supplier_review_signal"))
        and not _bool(row.get("watchlist_supplier_signal"))
        and not _extreme_moq_to_demand(row)
        and not _extreme_batch_to_demand(row)
        and not _phase4_one_to_one_candidate(row)
        and _float(row.get("average_daily_demand")) > 0
        and repeated
        and _float(row.get("stockout_penalty_per_unit")) < POLICY_SELECTION_THRESHOLDS["high_stockout_penalty"]
    )


def _select_review_policy(model_type: str, row: pd.Series) -> str:
    """Map inventory model type to review policy."""
    if model_type == "NEWSVENDOR_CANDIDATE":
        return "SINGLE_PERIOD"
    if model_type == "EVENT_BASED_REPLENISHMENT":
        return "EVENT_BASED"
    if model_type == "ONE_TO_ONE_REPLACEMENT":
        return "ONE_TO_ONE"
    if model_type == "BASE_STOCK":
        return "CONTINUOUS_REVIEW"
    if model_type == "CONTINUOUS_REVIEW_sQ":
        return "CONTINUOUS_REVIEW"
    if model_type == "EOQ":
        if row.get("movement_class") in {"FAST_MOVING", "MEDIUM_MOVING"} or row.get("vitality_class") in {"VITAL", "IMPORTANT"}:
            return "CONTINUOUS_REVIEW"
        return "PERIODIC_REVIEW"
    return "PERIODIC_REVIEW"


def _select_review_period(row: pd.Series) -> tuple[int, str]:
    """Select a planned monitoring/review cycle without calculating R,S quantities."""
    if row.get("inventory_priority_class") == "CRITICAL_PRIORITY" or _bool(row.get("stockout_signal")):
        return 1, "Critical or stockout SKU should be checked daily."
    if row.get("seasonality_class") in {"PEAK_SEASON", "SEASONAL_BUILDUP"}:
        return DEFAULT_REVIEW_PERIOD_DAYS["seasonal"], "Seasonal demand needs weekly review."
    if row.get("perishability_class") in {"SPOILAGE_RISK", "EXPIRY_TRACKED", "PERISHABLE"}:
        return DEFAULT_REVIEW_PERIOD_DAYS["perishable"], "Perishable or expiry-tracked SKU needs weekly review."
    movement_periods = {
        "FAST_MOVING": ("fast_moving", "Fast-moving SKU should be reviewed weekly."),
        "MEDIUM_MOVING": ("medium_moving", "Medium-moving SKU should be reviewed every two weeks."),
        "SLOW_MOVING": ("slow_moving", "Slow-moving SKU can use monthly review."),
        "NON_MOVING": ("non_moving", "Non-moving SKU can use longer review cadence."),
    }
    if row.get("movement_class") in movement_periods:
        key, reason = movement_periods[row.get("movement_class")]
        return DEFAULT_REVIEW_PERIOD_DAYS[key], reason
    return DEFAULT_REVIEW_PERIOD_DAYS["default"], "Default review period selected."


def _select_policy_urgency(row: pd.Series) -> str:
    """Classify urgency for policy review and later calculation."""
    low_inventory = _float(row.get("current_inventory")) <= max(_float(row.get("average_p90_forecast")), 0)
    if (
        _bool(row.get("stockout_signal"))
        or row.get("inventory_priority_class") == "CRITICAL_PRIORITY"
        or (row.get("vitality_class") == "VITAL" and _float(row.get("current_inventory")) <= 0)
        or _float(row.get("stockout_units")) >= POLICY_SELECTION_THRESHOLDS["high_stockout_units"]
        or (_bool(row.get("watchlist_supplier_signal")) and low_inventory)
    ):
        return "URGENT"
    if (
        low_inventory
        or _float(row.get("service_level_target")) >= 0.98
        or _bool(row.get("supplier_review_signal"))
        or _bool(row.get("watchlist_supplier_signal"))
        or (row.get("seasonality_class") == "SEASONAL_BUILDUP" and low_inventory)
        or _float(row.get("demand_adjusted_procurement_risk_score")) >= POLICY_SELECTION_THRESHOLDS["high_supplier_risk_score"]
    ):
        return "HIGH"
    if (
        row.get("movement_class") == "NON_MOVING"
        or row.get("inventory_priority_class") == "LOW_PRIORITY"
        or (_float(row.get("service_level_target")) < POLICY_SELECTION_THRESHOLDS["low_service_level"] and not _bool(row.get("stockout_signal")))
    ):
        return "LOW"
    return "MEDIUM"


def _policy_review_context(row: pd.Series, model_type: str, procurement_flag: bool) -> tuple[bool, str, bool]:
    """Return review requirement, reason, and Phase 4 review flag."""
    reasons = []
    phase4_review = _phase4_item(row)
    if _bool(row.get("service_level_review_required")):
        reasons.append("Service-level engine marked this SKU for review.")
    if _bool(row.get("service_level_re_evaluation_signal")):
        reasons.append("Service-level re-evaluation signal is active.")
    if _bool(row.get("supplier_review_signal")) or _bool(row.get("recommended_supplier_requires_review")):
        reasons.append("Recommended supplier requires review.")
    if _bool(row.get("watchlist_supplier_signal")):
        reasons.append("Supplier watchlist signal requires policy review.")
    if not _bool(row.get("recommended_supplier_feasible"), True):
        reasons.append("Recommended supplier is not feasible.")
    if phase4_review:
        reasons.append("Phase 4 production, BOM, or MRP logic may override this policy.")
    if _bool(row.get("expiry_risk_signal")):
        reasons.append("Expiry risk requires review before final order quantity.")
    if _bool(row.get("dead_stock_signal")) or _bool(row.get("non_moving_signal")):
        reasons.append("Non-moving or dead-stock signal requires policy review.")
    if row.get("seasonality_class") == "SEASONAL_UNKNOWN":
        reasons.append("Seasonal context is unclear.")
    if row.get("phase1_context_status") != "LOADED_FROM_PHASE1":
        reasons.append("Demand context is missing or fallback.")
    if row.get("phase2_context_status") != "LOADED_FROM_PHASE2":
        reasons.append("Procurement context is missing or fallback.")
    if procurement_flag:
        reasons.append("Procurement constraints should be reviewed before Step 6 calculations.")
    if model_type in {"NEWSVENDOR_CANDIDATE", "ONE_TO_ONE_REPLACEMENT", "EVENT_BASED_REPLENISHMENT"}:
        if _float(row.get("average_forecast_confidence_score"), 0.5) < 0.60:
            reasons.append("Selected policy is sensitive to low forecast confidence.")
    if not reasons:
        return False, "No immediate policy review required.", phase4_review
    return True, " ".join(reasons), phase4_review


def _policy_selection_confidence(
    row: pd.Series,
    model_type: str,
    review_required: bool,
    procurement_flag: bool,
    phase4_review_flag: bool,
) -> tuple[float, str]:
    """Calculate an interpretable policy-selection confidence score."""
    score = 0.70
    reasons = []
    if row.get("phase1_context_status") == "LOADED_FROM_PHASE1":
        score += 0.05
        reasons.append("Phase 1 demand context loaded")
    else:
        score -= 0.15
        reasons.append("missing Phase 1 demand context")
    if row.get("phase2_context_status") == "LOADED_FROM_PHASE2":
        score += 0.05
        reasons.append("Phase 2 procurement context loaded")
    else:
        score -= 0.15
        reasons.append("missing Phase 2 procurement context")
    if not pd.isna(row.get("classification_score")):
        score += 0.05
    if not pd.isna(row.get("service_level_target")):
        score += 0.05
    if _bool(row.get("recommended_supplier_feasible"), True):
        score += 0.05
    else:
        score -= 0.08
        reasons.append("recommended supplier is not feasible")
    forecast_confidence = _float(row.get("average_forecast_confidence_score"), 0.5)
    if forecast_confidence >= 0.80:
        score += 0.05
        reasons.append("forecast confidence is high")
    elif forecast_confidence < 0.60:
        score -= 0.10
        reasons.append("forecast confidence is low")
    if str(row.get("demand_behavior_class", "")).upper() in {"UNKNOWN", ""}:
        score -= 0.10
        reasons.append("demand behavior is unknown")
    else:
        score += 0.03
    evidence = str(row.get("supplier_evidence_status", row.get("recommended_supplier_evidence_status", ""))).upper()
    if evidence == "STRONG_HISTORY":
        score += 0.03
    elif evidence == "LIMITED_HISTORY":
        score -= 0.05
        reasons.append("supplier trend data is limited")
    elif evidence == "NO_HISTORY":
        score -= 0.08
        reasons.append("supplier has no history")
    if review_required:
        score -= 0.08
        reasons.append("policy review is required")
    if _bool(row.get("watchlist_supplier_signal")):
        score -= 0.08
        reasons.append("supplier is on watchlist")
    if phase4_review_flag:
        score -= 0.08
        reasons.append("Phase 4 production logic may override")
    if row.get("perishability_class") == "SPOILAGE_RISK":
        score -= 0.05
        reasons.append("spoilage risk adds uncertainty")
    if procurement_flag:
        score -= 0.05
        reasons.append("procurement constraints exist")
    if model_type in {"NEWSVENDOR_CANDIDATE", "EVENT_BASED_REPLENISHMENT", "ONE_TO_ONE_REPLACEMENT"}:
        score -= 0.03
    confidence = round(_clamp(score), 3)
    if not reasons:
        reasons.append("standard context supports policy selection")
    return confidence, "; ".join(reasons)


def _procurement_constraint_context(row: pd.Series) -> tuple[bool, str]:
    """Flag procurement constraints that Step 6 must respect."""
    reasons = []
    if _high_moq_to_demand(row):
        reasons.append("High MOQ may force overstock; Step 6 should cap order quantity using capacity and demand.")
    if _high_batch_to_demand(row):
        reasons.append("Large batch size may force order rounding above expected demand.")
    if _float(row.get("expected_yield_rate"), 1.0) < 0.90:
        reasons.append("Low expected yield requires yield-adjusted order quantity later.")
    if not _bool(row.get("recommended_supplier_feasible"), True):
        reasons.append("Recommended supplier is not feasible before finalization.")
    if _float(row.get("feasible_supplier_option_count")) <= 1:
        reasons.append("Few feasible supplier options limit procurement flexibility.")
    if _bool(row.get("supplier_review_signal")) or _bool(row.get("watchlist_supplier_signal")):
        reasons.append("Supplier review or watchlist signal affects policy finalization.")
    if not reasons:
        return False, "No major procurement constraints flagged for Step 6."
    return True, " ".join(reasons)


def _phase4_item(row: pd.Series) -> bool:
    """Return True when Phase 4 production logic may later override policy."""
    owner = str(row.get("inventory_owner_type", "")).upper()
    planning_type = str(row.get("item_planning_type", "")).upper()
    role = str(row.get("push_pull_boundary_role", "")).upper()
    return bool(
        owner in {"PRODUCED", "SEMI_PRODUCED"}
        or planning_type in {"COMPONENT", "RAW_MATERIAL", "WIP", "SEMI_FINISHED", "FINISHED_GOOD"}
        or role in {"MAKE_TO_ORDER_ITEM", "ASSEMBLE_TO_ORDER_COMPONENT", "RAW_MATERIAL_BUFFER", "FINISHED_GOOD_BUFFER"}
    )


def _phase4_one_to_one_candidate(row: pd.Series) -> bool:
    """Return True when a Phase 4 item resembles replacement/spare logic."""
    planning_type = str(row.get("item_planning_type", "")).upper()
    role = str(row.get("push_pull_boundary_role", "")).upper()
    owner = str(row.get("inventory_owner_type", "")).upper()
    behavior = str(row.get("demand_behavior_class", "")).lower()
    slow_or_intermittent = row.get("movement_class") in {"SLOW_MOVING", "NON_MOVING"} or behavior in {
        "intermittent",
        "erratic",
    }
    return bool(
        planning_type in {"COMPONENT", "RAW_MATERIAL", "WIP", "SEMI_FINISHED"}
        or role in {"ASSEMBLE_TO_ORDER_COMPONENT", "RAW_MATERIAL_BUFFER"}
        or (owner == "SEMI_PRODUCED" and slow_or_intermittent)
    )


def _high_moq_to_demand(row: pd.Series) -> bool:
    """Return True when MOQ is high relative to demand reference."""
    demand_reference = _demand_reference(row)
    return (_float(row.get("moq")) / demand_reference) >= POLICY_SELECTION_THRESHOLDS["high_moq_to_demand_ratio"]


def _high_batch_to_demand(row: pd.Series) -> bool:
    """Return True when batch size is high relative to demand reference."""
    demand_reference = _demand_reference(row)
    return (_float(row.get("batch_size")) / demand_reference) >= POLICY_SELECTION_THRESHOLDS["high_moq_to_demand_ratio"]


def _extreme_moq_to_demand(row: pd.Series) -> bool:
    """Return True when MOQ is too large for EOQ candidacy."""
    demand_reference = _demand_reference(row)
    return (
        _float(row.get("moq")) / demand_reference
    ) >= POLICY_SELECTION_THRESHOLDS["eoq_extreme_moq_to_demand_ratio"]


def _extreme_batch_to_demand(row: pd.Series) -> bool:
    """Return True when batch size is too large for EOQ candidacy."""
    demand_reference = _demand_reference(row)
    return (
        _float(row.get("batch_size")) / demand_reference
    ) >= POLICY_SELECTION_THRESHOLDS["eoq_extreme_batch_to_demand_ratio"]


def _demand_reference(row: pd.Series) -> float:
    """Return the demand reference used for constraint comparisons."""
    return max(
        _float(row.get("average_p90_forecast")),
        _float(row.get("average_p50_forecast")),
        _float(row.get("average_daily_demand")),
        1.0,
    )


def _copy_output_fields(row: pd.Series) -> dict:
    """Copy required context fields into the policy output."""
    fields = [
        "sku_id",
        "product_name",
        "category",
        "service_level_target",
        "safety_factor_z",
        "service_level_review_required",
        "service_level_re_evaluation_signal",
        "abc_class",
        "xyz_class",
        "fsn_class",
        "vitality_class",
        "seasonality_class",
        "perishability_class",
        "movement_class",
        "supplier_risk_class",
        "inventory_priority_class",
        "classification_score",
        "current_inventory",
        "available_inventory",
        "inventory_position",
        "stockout_signal",
        "stockout_units",
        "zero_inventory_signal",
        "expiry_risk_signal",
        "non_moving_signal",
        "dead_stock_signal",
        "near_expiry_units",
        "expired_units",
        "stockout_penalty_per_unit",
        "overstock_penalty_per_unit",
        "unit_cost_inventory",
        "inventory_value",
        "average_daily_demand",
        "coefficient_of_variation",
        "demand_behavior_class",
        "average_p50_forecast",
        "average_p90_forecast",
        "average_forecast_confidence_score",
        "dominant_forecast_risk_level",
        "recommended_supplier_id",
        "backup_supplier_id",
        "expected_lead_time_days",
        "lead_time_std_days",
        "unit_cost_procurement",
        "moq",
        "batch_size",
        "expected_yield_rate",
        "final_feasible_order_quantity",
        "demand_adjusted_procurement_risk_score",
        "demand_adjusted_procurement_risk_class",
        "recommended_supplier_feasible",
        "recommended_supplier_requires_review",
        "split_sourcing_recommendation",
        "recommended_primary_share",
        "recommended_backup_share",
        "supplier_option_count",
        "feasible_supplier_option_count",
        "supplier_review_signal",
        "watchlist_supplier_signal",
        "supplier_trend_status",
        "supplier_evidence_status",
        "recommended_supplier_evidence_status",
        "perishable",
        "expiry_tracking_required",
        "fefo_required",
        "handling_unit",
        "inventory_owner_type",
        "item_planning_type",
        "push_pull_boundary_role",
        "supplier_accepts_returns",
        "return_window_days",
        "return_deduction_rate",
        "return_transport_cost",
        "return_policy_status",
        "phase1_context_status",
        "phase2_context_status",
    ]
    result = {field: row.get(field, pd.NA) for field in fields}
    if pd.isna(result.get("supplier_evidence_status")):
        result["supplier_evidence_status"] = row.get("recommended_supplier_evidence_status", pd.NA)
    return result


def _step6_placeholders() -> dict:
    """Return Step 6 quantity fields that are intentionally not calculated yet."""
    return {
        "safety_stock": pd.NA,
        "reorder_point": pd.NA,
        "eoq": pd.NA,
        "eoq_rounded": pd.NA,
        "recommended_order_quantity": pd.NA,
        "min_stock_level": pd.NA,
        "max_stock_level": pd.NA,
        "reorder_point_s": pd.NA,
        "order_quantity_Q": pd.NA,
        "order_up_to_level_S": pd.NA,
        "base_stock_level": pd.NA,
        "newsvendor_critical_ratio": pd.NA,
    }


def _available_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Return available columns from a dataframe, preserving sku_id."""
    available = [column for column in columns if column in df.columns]
    return df[available].copy()


def _float(value, default: float = 0.0) -> float:
    """Safely convert scalar values to float."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value, default: bool = False) -> bool:
    """Safely convert scalar values to boolean."""
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return default
    return str(value).strip().lower() in {"true", "1", "yes"}


def _clamp(value: float) -> float:
    """Clamp confidence score between zero and one."""
    return max(0.0, min(1.0, value))


def _output_columns(df: pd.DataFrame) -> list[str]:
    """Return ordered policy output columns."""
    priority = [
        "sku_id",
        "product_name",
        "category",
        "inventory_model_type",
        "review_policy",
        "policy_selection_confidence",
        "policy_confidence_reason",
        "policy_urgency",
        "policy_review_required",
        "policy_review_reason",
        "policy_reason",
        "service_level_target",
        "safety_factor_z",
        "service_level_review_required",
        "service_level_re_evaluation_signal",
        "abc_class",
        "xyz_class",
        "fsn_class",
        "vitality_class",
        "seasonality_class",
        "perishability_class",
        "movement_class",
        "supplier_risk_class",
        "inventory_priority_class",
        "classification_score",
        "current_inventory",
        "available_inventory",
        "inventory_position",
        "stockout_signal",
        "stockout_units",
        "zero_inventory_signal",
        "expiry_risk_signal",
        "non_moving_signal",
        "dead_stock_signal",
        "near_expiry_units",
        "expired_units",
        "stockout_penalty_per_unit",
        "overstock_penalty_per_unit",
        "unit_cost_inventory",
        "inventory_value",
        "average_daily_demand",
        "coefficient_of_variation",
        "demand_behavior_class",
        "average_p50_forecast",
        "average_p90_forecast",
        "average_forecast_confidence_score",
        "dominant_forecast_risk_level",
        "recommended_supplier_id",
        "backup_supplier_id",
        "expected_lead_time_days",
        "lead_time_std_days",
        "unit_cost_procurement",
        "moq",
        "batch_size",
        "expected_yield_rate",
        "final_feasible_order_quantity",
        "demand_adjusted_procurement_risk_score",
        "demand_adjusted_procurement_risk_class",
        "recommended_supplier_feasible",
        "recommended_supplier_requires_review",
        "split_sourcing_recommendation",
        "recommended_primary_share",
        "recommended_backup_share",
        "supplier_option_count",
        "feasible_supplier_option_count",
        "supplier_review_signal",
        "watchlist_supplier_signal",
        "supplier_trend_status",
        "supplier_evidence_status",
        "perishable",
        "expiry_tracking_required",
        "fefo_required",
        "handling_unit",
        "inventory_owner_type",
        "item_planning_type",
        "push_pull_boundary_role",
        "supplier_accepts_returns",
        "return_window_days",
        "return_deduction_rate",
        "return_transport_cost",
        "return_policy_status",
        "safety_stock",
        "reorder_point",
        "eoq",
        "eoq_rounded",
        "recommended_order_quantity",
        "min_stock_level",
        "max_stock_level",
        "reorder_point_s",
        "order_quantity_Q",
        "review_period_R",
        "review_period_reason",
        "order_up_to_level_S",
        "base_stock_level",
        "newsvendor_critical_ratio",
        "procurement_constraint_flag",
        "procurement_constraint_reason",
        "phase4_review_flag",
        "phase1_context_status",
        "phase2_context_status",
    ]
    return [column for column in priority if column in df.columns]
