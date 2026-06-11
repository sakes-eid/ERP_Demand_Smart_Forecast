"""SKU-specific service level engine for Phase 3."""

from __future__ import annotations

import pandas as pd

from config import (
    SERVICE_LEVEL_ADJUSTMENTS,
    SERVICE_LEVEL_BOUNDS,
    SERVICE_LEVEL_DECISION_THRESHOLDS,
    SERVICE_LEVEL_GUARDRAILS,
    SERVICE_LEVEL_TARGETS,
    SERVICE_LEVEL_Z,
)


def build_inventory_service_levels(
    planning_context: pd.DataFrame,
    inventory_classification: pd.DataFrame,
) -> pd.DataFrame:
    """Assign service-level targets and safety factors without calculating policy quantities."""
    merged = _merge_context_and_classification(planning_context, inventory_classification)
    rows = []
    for _, row in merged.iterrows():
        result = row.to_dict()
        base_level, base_reason = _base_service_level(row)
        adjustment, flags, adjustment_reasons = _service_level_adjustments(row)
        pre_guardrail_target = _clamp(base_level + adjustment)
        target, guardrail_applied, guardrail_reason = _apply_service_level_guardrails(row, pre_guardrail_target)
        result.update(flags)
        result["base_service_level"] = round(base_level, 3)
        result["final_service_level_adjustment"] = round(adjustment, 3)
        result["pre_guardrail_service_level"] = round(pre_guardrail_target, 3)
        result["service_level_guardrail_applied"] = guardrail_applied
        result["service_level_guardrail_reason"] = guardrail_reason
        result["service_level_floor"] = SERVICE_LEVEL_BOUNDS["minimum"]
        result["service_level_ceiling"] = SERVICE_LEVEL_BOUNDS["maximum"]
        result["service_level_target"] = round(target, 3)
        result["safety_factor_z"] = round(_z_for_service_level(target), 3)
        result["service_level_review_required"] = _service_level_review_required(row, flags, guardrail_applied)
        signal, signal_reason = _re_evaluation_signal(row, result["service_level_review_required"], guardrail_applied)
        result["service_level_re_evaluation_signal"] = signal
        result["service_level_re_evaluation_reason"] = signal_reason
        result["service_level_reason"] = _service_level_reason(
            row,
            base_reason,
            adjustment_reasons,
            target,
            guardrail_applied,
            guardrail_reason,
        )
        rows.append(result)
    output = pd.DataFrame(rows)
    return output[_output_columns(output)]


def _merge_context_and_classification(
    planning_context: pd.DataFrame,
    inventory_classification: pd.DataFrame,
) -> pd.DataFrame:
    """Merge planning context with classification output."""
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
    available = [column for column in classification_columns if column in inventory_classification.columns]
    return planning_context.merge(inventory_classification[available], on="sku_id", how="left")


def _base_service_level(row: pd.Series) -> tuple[float, str]:
    """Choose a base service level from priority, vitality, ABC, FSN, and demand behavior."""
    priority_key = str(row.get("inventory_priority_class", "")).lower()
    priority_key = priority_key.replace("_priority", "_priority").lower()
    priority_map = {
        "critical_priority": SERVICE_LEVEL_TARGETS["critical_priority"],
        "high_priority": SERVICE_LEVEL_TARGETS["high_priority"],
        "medium_priority": SERVICE_LEVEL_TARGETS["medium_priority"],
        "low_priority": SERVICE_LEVEL_TARGETS["low_priority"],
        "liquidation_priority": SERVICE_LEVEL_TARGETS["liquidation_priority"],
    }
    base = priority_map.get(priority_key, SERVICE_LEVEL_BOUNDS["default"])
    reasons = [f"Base level starts from {row.get('inventory_priority_class', 'UNKNOWN')}."]

    vitality = str(row.get("vitality_class", "")).upper()
    if vitality == "VITAL":
        base = max(base, SERVICE_LEVEL_TARGETS["vital"])
        reasons.append("Vitality sets a high minimum service level.")
    elif vitality == "IMPORTANT":
        base = max(base, SERVICE_LEVEL_TARGETS["important"])
    elif vitality == "NORMAL":
        base = max(min(base, SERVICE_LEVEL_TARGETS["normal"]), SERVICE_LEVEL_TARGETS["normal"])

    abc_targets = {"A": SERVICE_LEVEL_TARGETS["abc_a"], "B": SERVICE_LEVEL_TARGETS["abc_b"], "C": SERVICE_LEVEL_TARGETS["abc_c"]}
    abc_class = row.get("abc_class")
    if abc_class in abc_targets and vitality != "VITAL":
        base = max(base, abc_targets[abc_class]) if abc_class == "A" else min(base, max(abc_targets[abc_class], 0.88))

    movement = row.get("movement_class")
    movement_targets = {
        "FAST_MOVING": SERVICE_LEVEL_TARGETS["fast_moving"],
        "MEDIUM_MOVING": SERVICE_LEVEL_TARGETS["medium_moving"],
        "SLOW_MOVING": SERVICE_LEVEL_TARGETS["slow_moving"],
        "NON_MOVING": SERVICE_LEVEL_TARGETS["non_moving"],
    }
    if movement in movement_targets and vitality != "VITAL":
        base = (base + movement_targets[movement]) / 2

    behavior = str(row.get("demand_behavior_class", "")).lower()
    if behavior == "intermittent" and abc_class == "C" and vitality == "NORMAL":
        base = min(base, SERVICE_LEVEL_TARGETS["intermittent_low_value"])
        reasons.append("Intermittent low-value demand keeps the base level restrained.")
    if behavior == "erratic" and row.get("supplier_risk_class") in {"HIGH_SUPPLIER_RISK", "REVIEW_REQUIRED_SUPPLIER_RISK"}:
        base = max(base, SERVICE_LEVEL_TARGETS["erratic_high_risk"])
        reasons.append("Erratic demand with supplier risk increases the base level.")
    return _clamp(base), " ".join(reasons)


def _service_level_adjustments(row: pd.Series) -> tuple[float, dict[str, bool], list[str]]:
    """Calculate service-level adjustments and diagnostics."""
    flags = {
        "stockout_service_boost_applied": False,
        "vital_service_boost_applied": False,
        "supplier_risk_service_boost_applied": False,
        "low_forecast_confidence_boost_applied": False,
        "seasonal_service_adjustment_applied": False,
        "perishability_service_reduction_applied": False,
        "slow_or_non_moving_reduction_applied": False,
        "expiry_risk_reduction_applied": False,
        "liquidation_reduction_applied": False,
    }
    reasons = []
    adjustment = 0.0
    penalty = _float(row.get("stockout_penalty_per_unit"))
    stockout_units = _float(row.get("stockout_units"))
    avg_demand = _float(row.get("average_daily_demand"))
    procurement_risk = _float(row.get("demand_adjusted_procurement_risk_score"))
    forecast_confidence = min(
        _float(row.get("average_forecast_confidence_score"), 0.5),
        _float(row.get("champion_confidence_score"), 0.5),
    )

    if _bool(row.get("stockout_signal")):
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["stockout_signal_boost"]
        flags["stockout_service_boost_applied"] = True
        reasons.append("stockout signal boosted service level")
    if stockout_units >= SERVICE_LEVEL_DECISION_THRESHOLDS["high_stockout_units"]:
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["high_stockout_units_boost"]
        flags["stockout_service_boost_applied"] = True
    if penalty >= SERVICE_LEVEL_DECISION_THRESHOLDS["high_stockout_penalty"]:
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["high_stockout_cost_boost"]
        flags["stockout_service_boost_applied"] = True
    if row.get("vitality_class") == "VITAL":
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["vital_boost"]
        flags["vital_service_boost_applied"] = True
    if row.get("inventory_priority_class") == "CRITICAL_PRIORITY":
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["critical_priority_boost"]
        flags["vital_service_boost_applied"] = True

    supplier_risky = (
        _bool(row.get("supplier_review_signal"))
        or _bool(row.get("watchlist_supplier_signal"))
        or _bool(row.get("recommended_supplier_requires_review"))
        or str(row.get("supplier_trend_status", "")).upper() == "WATCHLIST"
        or str(row.get("supplier_evidence_status", "")).upper() in {"NO_HISTORY", "LIMITED_HISTORY"}
        or procurement_risk >= SERVICE_LEVEL_DECISION_THRESHOLDS["high_procurement_risk_score"]
        or str(row.get("demand_adjusted_procurement_risk_class", "")).upper() == "HIGH"
    )
    if supplier_risky and row.get("vitality_class") in {"VITAL", "IMPORTANT"}:
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["supplier_review_boost"]
        flags["supplier_risk_service_boost_applied"] = True
        reasons.append("supplier risk increased protection for important SKU")
    if _bool(row.get("watchlist_supplier_signal")):
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["watchlist_supplier_boost"]
        flags["supplier_risk_service_boost_applied"] = True
    if str(row.get("demand_adjusted_procurement_risk_class", "")).upper() == "HIGH":
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["high_procurement_risk_boost"]
        flags["supplier_risk_service_boost_applied"] = True

    if forecast_confidence < SERVICE_LEVEL_DECISION_THRESHOLDS["low_forecast_confidence"] and row.get("vitality_class") in {"VITAL", "IMPORTANT"}:
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["low_forecast_confidence_boost_for_vital"]
        flags["low_forecast_confidence_boost_applied"] = True
        reasons.append("low forecast confidence boosted vital or important SKU")

    seasonality = row.get("seasonality_class")
    if seasonality in {"SEASONAL_BUILDUP", "PEAK_SEASON"}:
        adjustment += 0.02
        flags["seasonal_service_adjustment_applied"] = True
    elif seasonality == "SEASONAL_DRAWDOWN":
        reduction = SERVICE_LEVEL_ADJUSTMENTS["off_season_reduction"] / 2 if row.get("vitality_class") == "VITAL" else SERVICE_LEVEL_ADJUSTMENTS["off_season_reduction"]
        adjustment += reduction
        flags["seasonal_service_adjustment_applied"] = True
        reasons.append("seasonal drawdown reduced service level")
    elif seasonality == "OFF_SEASON":
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["off_season_reduction"]
        flags["seasonal_service_adjustment_applied"] = True

    if row.get("movement_class") == "SLOW_MOVING" and row.get("vitality_class") != "VITAL":
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["slow_moving_reduction"]
        flags["slow_or_non_moving_reduction_applied"] = True
        reasons.append("slow movement reduced service level")
    if row.get("movement_class") == "NON_MOVING" and row.get("vitality_class") != "VITAL":
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["non_moving_reduction"]
        flags["slow_or_non_moving_reduction_applied"] = True
        reasons.append("non-moving SKU reduced service level")
    if row.get("perishability_class") == "SPOILAGE_RISK":
        reduction = SERVICE_LEVEL_ADJUSTMENTS["spoilage_risk_reduction"] / 2 if row.get("vitality_class") == "VITAL" else SERVICE_LEVEL_ADJUSTMENTS["spoilage_risk_reduction"]
        adjustment += reduction
        flags["perishability_service_reduction_applied"] = True
        reasons.append("spoilage or expiry risk reduced service level")
    if _float(row.get("near_expiry_units")) > 0 or _float(row.get("expired_units")) > 0 or _bool(row.get("expiry_risk_signal")):
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["near_expiry_reduction"]
        flags["expiry_risk_reduction_applied"] = True
    if _bool(row.get("dead_stock_signal")):
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["dead_stock_reduction"]
        flags["slow_or_non_moving_reduction_applied"] = True
    if row.get("inventory_priority_class") == "LIQUIDATION_PRIORITY":
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["liquidation_priority_reduction"]
        flags["liquidation_reduction_applied"] = True
        reasons.append("liquidation priority reduced service level")
    if avg_demand < SERVICE_LEVEL_DECISION_THRESHOLDS["high_average_daily_demand"] and _float(row.get("current_inventory")) > max(_float(row.get("average_p90_forecast")), 1) * 2:
        adjustment += SERVICE_LEVEL_ADJUSTMENTS["overstock_like_reduction"]
        reasons.append("high inventory relative to forecast reduced service level")

    return adjustment, flags, reasons


def _apply_service_level_guardrails(row: pd.Series, target: float) -> tuple[float, bool, str]:
    """Apply configurable service-level floors for protected SKU classes."""
    floors: list[tuple[float, str]] = []
    priority = row.get("inventory_priority_class")
    vitality = row.get("vitality_class")
    important_exception_reason = ""

    if priority == "CRITICAL_PRIORITY":
        floors.append((SERVICE_LEVEL_GUARDRAILS["critical_priority_min"], "Critical priority guardrail raised service level to 0.98."))
    if priority == "HIGH_PRIORITY":
        floors.append((SERVICE_LEVEL_GUARDRAILS["high_priority_min"], "High priority guardrail raised service level to 0.95."))
    if vitality == "VITAL" and not _vital_guardrail_exception(row):
        floors.append((SERVICE_LEVEL_GUARDRAILS["vital_min"], "Vital SKU guardrail raised service level to 0.95."))
    if vitality == "IMPORTANT":
        if _important_guardrail_exception(row):
            important_exception_reason = _important_exception_reason(row)
        else:
            floors.append((SERVICE_LEVEL_GUARDRAILS["important_min"], "Important SKU guardrail raised service level to 0.90."))
    if row.get("abc_class") == "A" and not _reduction_floor_exception(row):
        floors.append((SERVICE_LEVEL_GUARDRAILS["abc_a_min"], "A-class guardrail raised service level to 0.90."))
    if row.get("movement_class") == "FAST_MOVING" and not _reduction_floor_exception(row):
        floors.append((SERVICE_LEVEL_GUARDRAILS["fast_moving_min"], "Fast-moving guardrail raised service level to 0.90."))

    if not floors:
        if important_exception_reason and target < SERVICE_LEVEL_GUARDRAILS["important_min"]:
            return target, False, important_exception_reason
        return target, False, "No guardrail applied."

    floor, reason = max(floors, key=lambda item: item[0])
    if target < floor:
        return _clamp(floor), True, reason
    if important_exception_reason and target < SERVICE_LEVEL_GUARDRAILS["important_min"]:
        return target, False, important_exception_reason
    return target, False, "No guardrail applied."


def _important_guardrail_exception(row: pd.Series) -> bool:
    """Return True when an important SKU is allowed below the normal minimum."""
    if row.get("inventory_priority_class") == "LIQUIDATION_PRIORITY":
        return SERVICE_LEVEL_GUARDRAILS["allow_below_important_min_if_liquidation"]
    if _float(row.get("expired_units")) > 0 and row.get("vitality_class") != "VITAL":
        return SERVICE_LEVEL_GUARDRAILS["allow_below_important_min_if_expired_and_not_vital"]
    if _bool(row.get("dead_stock_signal")) and row.get("vitality_class") != "VITAL":
        return SERVICE_LEVEL_GUARDRAILS["allow_below_important_min_if_dead_stock_and_not_vital"]
    if (
        row.get("movement_class") == "NON_MOVING"
        and row.get("abc_class") == "C"
        and row.get("vitality_class") == "NORMAL"
    ):
        return SERVICE_LEVEL_GUARDRAILS["allow_below_important_min_if_non_moving_c_class_normal"]
    return False


def _vital_guardrail_exception(row: pd.Series) -> bool:
    """Return True only for explicit liquidation/non-stockout exceptions."""
    return row.get("inventory_priority_class") == "LIQUIDATION_PRIORITY" and not _bool(row.get("stockout_signal"))


def _reduction_floor_exception(row: pd.Series) -> bool:
    """Return True when A/fast-moving floors can be relaxed."""
    return (
        row.get("inventory_priority_class") == "LIQUIDATION_PRIORITY"
        or _bool(row.get("dead_stock_signal"))
        or _float(row.get("expired_units")) > 0
        or row.get("perishability_class") == "SPOILAGE_RISK"
    )


def _important_exception_reason(row: pd.Series) -> str:
    """Explain why an important SKU was allowed below the guardrail."""
    if row.get("inventory_priority_class") == "LIQUIDATION_PRIORITY":
        return "Allowed below important minimum because SKU is liquidation priority."
    if _float(row.get("expired_units")) > 0:
        return "Allowed below important minimum because SKU has expired units and is not vital."
    if _bool(row.get("dead_stock_signal")):
        return "Allowed below important minimum because SKU is dead stock and is not vital."
    if row.get("movement_class") == "NON_MOVING" and row.get("abc_class") == "C" and row.get("vitality_class") == "NORMAL":
        return "Allowed below important minimum because SKU is non-moving C-class normal inventory."
    return "No guardrail applied."


def _service_level_review_required(row: pd.Series, flags: dict[str, bool], guardrail_applied: bool) -> bool:
    """Return True when service-level choice should be reviewed later."""
    production_item = str(row.get("item_planning_type", "")).upper() in {"COMPONENT", "RAW_MATERIAL", "WIP", "SEMI_FINISHED"}
    low_confidence_non_vital = (
        min(_float(row.get("average_forecast_confidence_score"), 0.5), _float(row.get("champion_confidence_score"), 0.5))
        < SERVICE_LEVEL_DECISION_THRESHOLDS["low_forecast_confidence"]
        and row.get("vitality_class") != "VITAL"
    )
    return bool(
        _bool(row.get("supplier_review_signal"))
        or _bool(row.get("watchlist_supplier_signal"))
        or str(row.get("supplier_evidence_status", "")).upper() in {"NO_HISTORY", "LIMITED_HISTORY"}
        or (low_confidence_non_vital and row.get("perishability_class") in {"SPOILAGE_RISK", "EXPIRY_TRACKED"})
        or production_item
        or flags["liquidation_reduction_applied"]
        or row.get("seasonality_class") == "SEASONAL_UNKNOWN"
        or guardrail_applied
    )


def _re_evaluation_signal(row: pd.Series, review_required: bool, guardrail_applied: bool) -> tuple[bool, str]:
    """Add early signals for the future re-evaluation engine."""
    reasons = []
    if _bool(row.get("stockout_signal")):
        reasons.append("Stockout signal requires review of service level.")
    if _bool(row.get("expiry_risk_signal")):
        reasons.append("Expiry risk suggests lowering future service level or order quantity.")
    if _bool(row.get("dead_stock_signal")) or _bool(row.get("non_moving_signal")):
        reasons.append("Non-moving or dead-stock signal requires service level review.")
    if _bool(row.get("supplier_review_signal")) or _bool(row.get("watchlist_supplier_signal")):
        reasons.append("Watchlist supplier may require higher protection or supplier review.")
    if min(_float(row.get("average_forecast_confidence_score"), 0.5), _float(row.get("champion_confidence_score"), 0.5)) < SERVICE_LEVEL_DECISION_THRESHOLDS["low_forecast_confidence"] and row.get("vitality_class") in {"VITAL", "IMPORTANT"}:
        reasons.append("Low forecast confidence for important SKU requires review.")
    if row.get("seasonality_class") == "SEASONAL_DRAWDOWN" and (_bool(row.get("expiry_risk_signal")) or _float(row.get("current_inventory")) > 0):
        reasons.append("Seasonal drawdown with inventory or expiry risk requires review.")
    if str(row.get("item_planning_type", "")).upper() in {"COMPONENT", "RAW_MATERIAL", "WIP", "SEMI_FINISHED"}:
        reasons.append("Component/semi-finished item should be revisited when Phase 4 production planning is added.")
    if guardrail_applied:
        reasons.append("Service-level guardrail was applied and should be reviewed later.")
    if review_required and not reasons:
        reasons.append("Service level review required by supplier or planning context.")
    return bool(reasons), " ".join(reasons) if reasons else "No immediate service level re-evaluation signal."


def _service_level_reason(
    row: pd.Series,
    base_reason: str,
    adjustment_reasons: list[str],
    target: float,
    guardrail_applied: bool,
    guardrail_reason: str,
) -> str:
    """Create readable service-level reason text."""
    if row.get("inventory_priority_class") == "CRITICAL_PRIORITY" and _bool(row.get("stockout_signal")):
        return "Critical stockout SKU; service level kept high to reduce shortage risk."
    if guardrail_applied:
        if row.get("seasonality_class") == "SEASONAL_DRAWDOWN" and row.get("movement_class") == "SLOW_MOVING":
            return f"Seasonal drawdown and slow movement reduced the target, but {_lower_first(guardrail_reason)}"
        if row.get("seasonality_class") == "SEASONAL_DRAWDOWN":
            return f"Seasonal drawdown reduced the target, but {_lower_first(guardrail_reason)}"
        if row.get("perishability_class") == "SPOILAGE_RISK":
            return f"Spoilage risk reduced the target, but {_lower_first(guardrail_reason)}"
        if adjustment_reasons:
            return f"{', '.join(adjustment_reasons).capitalize()}, but {_lower_first(guardrail_reason)}"
        return f"{base_reason} {guardrail_reason}"
    if guardrail_reason.startswith("Allowed below"):
        if row.get("movement_class") == "NON_MOVING" and row.get("abc_class") == "C" and row.get("vitality_class") == "NORMAL":
            return f"Non-moving C-class normal SKU; low service level allowed to reduce frozen capital. {guardrail_reason}"
        if adjustment_reasons:
            return f"{base_reason} Adjustments applied: {', '.join(adjustment_reasons)}. {guardrail_reason}"
        return f"{base_reason} {guardrail_reason}"
    if row.get("seasonality_class") == "SEASONAL_BUILDUP":
        return "Seasonal buildup SKU; service level increased for expected demand."
    if row.get("seasonality_class") == "SEASONAL_DRAWDOWN" and row.get("perishability_class") == "SPOILAGE_RISK":
        return "Off-season/perishable SKU with expiry risk; service level reduced to avoid waste."
    if row.get("movement_class") == "NON_MOVING":
        return "Non-moving SKU; service level kept low to reduce frozen capital."
    if row.get("vitality_class") == "VITAL" and row.get("supplier_risk_class") in {"HIGH_SUPPLIER_RISK", "REVIEW_REQUIRED_SUPPLIER_RISK"}:
        return "Vital SKU with high stockout penalty and supplier risk; service level increased."
    if str(row.get("item_planning_type", "")).upper() in {"COMPONENT", "RAW_MATERIAL", "WIP", "SEMI_FINISHED"}:
        return "Component/semi-finished item preserved for Phase 4 production planning review."
    if row.get("abc_class") == "A" and row.get("movement_class") == "FAST_MOVING":
        return "Stable A-class fast-moving SKU; high service level maintained."
    if adjustment_reasons:
        return f"{base_reason} Adjustments applied: {', '.join(adjustment_reasons)}. Final target {target:.3f}."
    return f"{base_reason} Final service level target {target:.3f}."


def _lower_first(text: str) -> str:
    """Lowercase the first letter of a short reason clause."""
    if not text:
        return text
    return text[0].lower() + text[1:]


def _z_for_service_level(service_level: float) -> float:
    """Return z factor using simple linear interpolation across configured points."""
    points = sorted(SERVICE_LEVEL_Z.items())
    if service_level <= points[0][0]:
        return points[0][1]
    if service_level >= points[-1][0]:
        return points[-1][1]
    for (lower_level, lower_z), (upper_level, upper_z) in zip(points, points[1:]):
        if lower_level <= service_level <= upper_level:
            share = (service_level - lower_level) / (upper_level - lower_level)
            return lower_z + share * (upper_z - lower_z)
    return SERVICE_LEVEL_Z[0.95]


def _clamp(value: float) -> float:
    """Clamp service level to configured bounds."""
    return max(SERVICE_LEVEL_BOUNDS["minimum"], min(SERVICE_LEVEL_BOUNDS["maximum"], value))


def _float(value, default: float = 0.0) -> float:
    """Safely convert scalar to float."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value) -> bool:
    """Safely convert scalar to bool."""
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def _output_columns(df: pd.DataFrame) -> list[str]:
    """Return ordered output columns."""
    priority = [
        "sku_id",
        "product_name",
        "category",
        "service_level_target",
        "safety_factor_z",
        "base_service_level",
        "final_service_level_adjustment",
        "pre_guardrail_service_level",
        "service_level_guardrail_applied",
        "service_level_guardrail_reason",
        "service_level_floor",
        "service_level_ceiling",
        "service_level_reason",
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
        "stockout_signal",
        "stockout_units",
        "zero_inventory_signal",
        "expiry_risk_signal",
        "non_moving_signal",
        "dead_stock_signal",
        "near_expiry_units",
        "expired_units",
        "stockout_penalty_per_unit",
        "average_daily_demand",
        "coefficient_of_variation",
        "demand_behavior_class",
        "average_forecast_confidence_score",
        "champion_confidence_score",
        "dominant_forecast_risk_level",
        "demand_adjusted_procurement_risk_score",
        "demand_adjusted_procurement_risk_class",
        "recommended_supplier_requires_review",
        "supplier_review_signal",
        "supplier_watchlist_flag",
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
        "stockout_service_boost_applied",
        "vital_service_boost_applied",
        "supplier_risk_service_boost_applied",
        "low_forecast_confidence_boost_applied",
        "seasonal_service_adjustment_applied",
        "perishability_service_reduction_applied",
        "slow_or_non_moving_reduction_applied",
        "expiry_risk_reduction_applied",
        "liquidation_reduction_applied",
        "service_level_review_required",
        "service_level_re_evaluation_signal",
        "service_level_re_evaluation_reason",
    ]
    return [column for column in priority if column in df.columns]
