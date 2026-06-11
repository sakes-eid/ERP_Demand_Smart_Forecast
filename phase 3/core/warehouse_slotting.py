"""Warehouse slotting, space utilization, and travel impact for Phase 3 Step 9."""

from __future__ import annotations

import math

import pandas as pd

from config import (
    WAREHOUSE_BATCH_QUANTITY_RULES,
    WAREHOUSE_BATCH_ZONE_RULES,
    WAREHOUSE_HANDLING_RULES,
    WAREHOUSE_SLOT_CONFIG,
    WAREHOUSE_STAGING_RULES,
    WAREHOUSE_TRAVEL_THRESHOLDS,
    WAREHOUSE_UTILIZATION_THRESHOLDS,
    WAREHOUSE_Z_LEVEL_RULES,
    WAREHOUSE_ZONE_COST_MULTIPLIERS,
)


def build_warehouse_slotting(
    inventory_clean: pd.DataFrame,
    inventory_batches_clean: pd.DataFrame,
    inventory_movements_clean: pd.DataFrame,
    warehouse_layout_clean: pd.DataFrame,
    storage_locations_clean: pd.DataFrame,
    sku_storage_requirements_clean: pd.DataFrame,
    planning_context: pd.DataFrame,
    inventory_classification: pd.DataFrame,
    inventory_service_levels: pd.DataFrame,
    inventory_policy: pd.DataFrame,
    inventory_policy_parameters: pd.DataFrame,
    inventory_status: pd.DataFrame,
    inventory_action_recommendations: pd.DataFrame,
    inventory_costs: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create slotting, utilization, and travel outputs."""
    batch_summary = _build_batch_summary(inventory_batches_clean)
    slotting_input = _build_slotting_input(
        inventory_clean,
        sku_storage_requirements_clean,
        planning_context,
        inventory_classification,
        inventory_service_levels,
        inventory_policy,
        inventory_policy_parameters,
        inventory_status,
        inventory_action_recommendations,
        inventory_costs,
    )
    slotting_input = _merge_missing_columns(slotting_input, batch_summary)
    layout_context = _layout_context(warehouse_layout_clean)
    locations = _normalize_locations(storage_locations_clean)
    prepared_skus = _prepared_skus(slotting_input)
    known_usage = _known_current_usage_by_location(prepared_skus)
    location_state = _initial_location_state(locations, known_usage)

    slotting_rows = []
    for _, row in prepared_skus.iterrows():
        slotting_rows.append(_assign_sku(row, locations, location_state, layout_context))

    warehouse_slotting = pd.DataFrame(slotting_rows)
    warehouse_slotting = _add_batch_split_location_fields(warehouse_slotting, locations)
    location_state = _rebuild_location_state_from_slotting(location_state, warehouse_slotting)
    location_utilization = _build_location_utilization(locations, location_state)
    warehouse_slotting = _add_replenishment_pressure_fields(warehouse_slotting, location_utilization)
    warehouse_slotting = _add_warehouse_visual_fields(warehouse_slotting)
    warehouse_slotting = _ensure_columns(warehouse_slotting, _slotting_output_columns())
    warehouse_slotting = warehouse_slotting[_slotting_output_columns()]
    batch_slotting = build_batch_slotting_rows(
        inventory_batches_clean,
        warehouse_slotting,
        locations,
        location_state,
        layout_context,
    )
    location_utilization = _add_trace_only_batches_to_location_utilization(location_utilization, batch_slotting)
    space_utilization = _build_space_utilization(location_utilization, batch_slotting)
    warehouse_travel_costs = _build_travel_costs(warehouse_slotting)
    return warehouse_slotting, batch_slotting, location_utilization, space_utilization, warehouse_travel_costs


def _build_slotting_input(
    inventory_clean: pd.DataFrame,
    sku_storage_requirements_clean: pd.DataFrame,
    planning_context: pd.DataFrame,
    inventory_classification: pd.DataFrame,
    inventory_service_levels: pd.DataFrame,
    inventory_policy: pd.DataFrame,
    inventory_policy_parameters: pd.DataFrame,
    inventory_status: pd.DataFrame,
    inventory_action_recommendations: pd.DataFrame,
    inventory_costs: pd.DataFrame,
) -> pd.DataFrame:
    """Start from inventory rows and merge missing SKU context."""
    merged = inventory_clean.copy()
    if "unit_cost" in merged.columns and "unit_cost_inventory" not in merged.columns:
        merged = merged.rename(columns={"unit_cost": "unit_cost_inventory"})
    if "storage_location_id" in merged.columns and "current_location_id" not in merged.columns:
        merged["current_location_id"] = merged["storage_location_id"]
    for supplement in [
        sku_storage_requirements_clean,
        planning_context,
        inventory_classification,
        inventory_service_levels,
        inventory_policy,
        inventory_policy_parameters,
        inventory_status,
        inventory_action_recommendations,
        inventory_costs,
    ]:
        merged = _merge_missing_columns(merged, supplement)
    return merged


def _merge_missing_columns(base: pd.DataFrame, supplement: pd.DataFrame) -> pd.DataFrame:
    """Merge columns that are missing from base, keyed by sku_id."""
    if base.empty or supplement.empty or "sku_id" not in base.columns or "sku_id" not in supplement.columns:
        return base
    missing_columns = [column for column in supplement.columns if column not in base.columns]
    if not missing_columns:
        return base
    return base.merge(supplement[["sku_id", *missing_columns]], on="sku_id", how="left")


def _build_batch_summary(inventory_batches_clean: pd.DataFrame) -> pd.DataFrame:
    """Summarize expired, near-expiry, and healthy batches per SKU for split slotting."""
    if inventory_batches_clean.empty or "sku_id" not in inventory_batches_clean.columns:
        return pd.DataFrame(columns=["sku_id"])
    rows = []
    batches = inventory_batches_clean.copy()
    batches["_batch_quantity"] = batches.apply(_batch_quantity, axis=1)
    batches["_active_batch_quantity_flag"] = batches["_batch_quantity"] > WAREHOUSE_BATCH_QUANTITY_RULES["active_batch_quantity_min"]
    for sku_id, group in inventory_batches_clean.groupby("sku_id", dropna=False):
        group = batches.loc[group.index]
        expired = group[group["expired_flag"].apply(_bool)] if "expired_flag" in group.columns else group.iloc[0:0]
        near = group[group["near_expiry_flag"].apply(_bool) & ~group["expired_flag"].apply(_bool)] if {"near_expiry_flag", "expired_flag"}.issubset(group.columns) else group.iloc[0:0]
        healthy = group.drop(expired.index.union(near.index))
        active_expired = expired[expired["_active_batch_quantity_flag"]]
        active_near = near[near["_active_batch_quantity_flag"]]
        active_healthy = healthy[healthy["_active_batch_quantity_flag"]]
        empty_expired = expired[~expired["_active_batch_quantity_flag"]]
        empty_near = near[~near["_active_batch_quantity_flag"]]
        empty_healthy = healthy[~healthy["_active_batch_quantity_flag"]]
        rows.append(
            {
                "sku_id": sku_id,
                "expired_batch_ids": _join_ids(expired, "batch_id"),
                "near_expiry_batch_ids": _join_ids(near, "batch_id"),
                "healthy_batch_ids": _join_ids(healthy, "batch_id"),
                "expired_batch_count": int(len(expired)),
                "near_expiry_batch_count": int(len(near)),
                "healthy_batch_count": int(len(healthy)),
                "active_expired_batch_count": int(len(active_expired)),
                "active_near_expiry_batch_count": int(len(active_near)),
                "active_healthy_batch_count": int(len(active_healthy)),
                "expired_empty_batch_count": int(len(empty_expired)),
                "near_expiry_empty_batch_count": int(len(empty_near)),
                "healthy_empty_batch_count": int(len(empty_healthy)),
                "quarantine_units": _quantity_sum(active_expired),
                "near_expiry_units_for_fefo": _quantity_sum(active_near),
                "normal_storage_units": _quantity_sum(active_healthy),
            }
        )
    return pd.DataFrame(rows)


def _join_ids(df: pd.DataFrame, column: str) -> str:
    """Join IDs from a dataframe group."""
    if df.empty or column not in df.columns:
        return ""
    return ";".join(df[column].dropna().astype(str))


def _quantity_sum(df: pd.DataFrame) -> float:
    """Sum batch on-hand quantity with safe fallback."""
    if df.empty:
        return 0.0
    if "quantity_on_hand" in df.columns:
        return float(pd.to_numeric(df["quantity_on_hand"], errors="coerce").fillna(0).clip(lower=0).sum())
    if "quantity_available" in df.columns:
        return float(pd.to_numeric(df["quantity_available"], errors="coerce").fillna(0).clip(lower=0).sum())
    return 0.0


def _prepared_skus(slotting_input: pd.DataFrame) -> pd.DataFrame:
    """Add priority and deterministic sort keys before greedy assignment."""
    prepared_rows = []
    for _, row in slotting_input.iterrows():
        result = row.to_dict()
        requirements, warnings = _sku_requirements(row)
        result.update(requirements)
        result["slotting_priority_score"] = _slotting_priority(row)
        result["recommended_storage_zone"] = _recommended_zone(row, requirements)
        result["_initial_warnings"] = warnings
        prepared_rows.append(result)
    prepared = pd.DataFrame(prepared_rows)
    return prepared.sort_values(
        by=["slotting_priority_score", "projected_required_volume_m3", "sku_id"],
        ascending=[False, False, True],
    )


def _sku_requirements(row: pd.Series) -> tuple[dict, list[str]]:
    """Calculate unit, volume, and weight requirements for a SKU."""
    warnings = []
    current_units = max(_float(row.get("current_inventory")), 0.0)
    recommended_quantity = max(_float(row.get("recommended_order_quantity")), 0.0)
    projected_units = max(_float(row.get("inventory_position")), _float(row.get("current_inventory")), 0.0) + recommended_quantity
    unit_volume = _float(row.get("unit_volume_m3"), default=-1.0)
    unit_weight = _float(row.get("unit_weight_kg"), default=-1.0)
    if unit_volume <= 0:
        unit_volume = WAREHOUSE_SLOT_CONFIG["default_unit_volume_m3"]
        warnings.append("MISSING_SKU_STORAGE_REQUIREMENTS")
    if unit_weight <= 0:
        unit_weight = WAREHOUSE_SLOT_CONFIG["default_unit_weight_kg"]
        warnings.append("MISSING_SKU_STORAGE_REQUIREMENTS")
    if current_units > 0 and not str(row.get("current_location_id", "")).strip():
        warnings.append("MISSING_CURRENT_LOCATION_FOR_REBASE")
    quarantine_units = max(_float(row.get("quarantine_units")), 0.0)
    fefo_units = max(_float(row.get("near_expiry_units_for_fefo")), 0.0)
    normal_storage_units = max(_float(row.get("normal_storage_units")), 0.0)
    active_batch_units = quarantine_units + fefo_units + normal_storage_units
    if current_units > 0 and active_batch_units > 0 and abs(active_batch_units - current_units) > 0.01:
        warnings.append("BATCH_QUANTITY_RECONCILIATION_REVIEW")
    if current_units > 0 and active_batch_units <= 0:
        normal_storage_units = current_units
    elif active_batch_units > 0 and active_batch_units < current_units and current_units - active_batch_units > 0.01:
        normal_storage_units += current_units - active_batch_units
    primary_storage_units = max(normal_storage_units, 0.0)
    replenishment_units = recommended_quantity
    primary_projected_units = primary_storage_units + replenishment_units

    temperature_required = _bool(row.get("temperature_required")) or _bool(row.get("temperature_control_required"))
    security_required = _bool(row.get("security_required")) or _bool(row.get("security_control_required"))
    handling_unit = str(row.get("handling_unit", "")).upper()
    ergonomic_level_required = (
        WAREHOUSE_HANDLING_RULES["fast_moving_prefers_ergonomic_level"]
        and row.get("movement_class") == "FAST_MOVING"
    )
    fragile_low_level = WAREHOUSE_HANDLING_RULES["fragile_prefers_low_level"] and _bool(row.get("fragile"))
    heavy_low_level = _bool(row.get("heavy_low_storage_required")) or unit_weight >= WAREHOUSE_HANDLING_RULES["heavy_item_weight_kg_threshold"]
    low_level_required = heavy_low_level or fragile_low_level or ergonomic_level_required
    forklift_reasons = []
    if _bool(row.get("forklift_required")):
        forklift_reasons.append("EXPLICIT_FORKLIFT_REQUIRED")
    if WAREHOUSE_HANDLING_RULES["pallet_requires_forklift"] and handling_unit == "PALLET":
        forklift_reasons.append("PALLET_HANDLING_UNIT")
    if unit_weight >= WAREHOUSE_HANDLING_RULES["forklift_weight_kg_threshold"]:
        forklift_reasons.append("WEIGHT_ABOVE_FORKLIFT_THRESHOLD")
    forklift_required = bool(forklift_reasons)
    low_level_reasons = []
    if heavy_low_level:
        low_level_reasons.append("HEAVY_OR_LOW_STORAGE_REQUIRED")
    if fragile_low_level:
        low_level_reasons.append("FRAGILE_PREFERS_LOW_LEVEL")
    if ergonomic_level_required:
        low_level_reasons.append("FAST_MOVING_PREFERS_ERGONOMIC_LEVEL")
    max_stack_height = _float(row.get("max_stack_height_m"), default=_float(row.get("max_stack_height")))
    if max_stack_height <= 0:
        max_stack_height = WAREHOUSE_SLOT_CONFIG["default_max_stack_height_m"]

    return {
        "current_units_for_space": current_units,
        "projected_units_after_order": projected_units,
        "primary_storage_units": primary_storage_units,
        "quarantine_storage_units": quarantine_units,
        "fefo_storage_units": fefo_units,
        "replenishment_storage_units": replenishment_units,
        "replenishment_units": replenishment_units,
        "unit_volume_m3": unit_volume,
        "unit_weight_kg": unit_weight,
        "total_current_inventory_volume_m3": current_units * unit_volume,
        "total_current_inventory_weight_kg": current_units * unit_weight,
        "primary_storage_volume_m3": primary_storage_units * unit_volume,
        "quarantine_storage_volume_m3": quarantine_units * unit_volume,
        "fefo_storage_volume_m3": fefo_units * unit_volume,
        "replenishment_storage_volume_m3": replenishment_units * unit_volume,
        "primary_projected_volume_m3": primary_projected_units * unit_volume,
        "primary_storage_weight_kg": primary_storage_units * unit_weight,
        "quarantine_storage_weight_kg": quarantine_units * unit_weight,
        "fefo_storage_weight_kg": fefo_units * unit_weight,
        "replenishment_storage_weight_kg": replenishment_units * unit_weight,
        "primary_projected_weight_kg": primary_projected_units * unit_weight,
        "current_required_volume_m3": primary_storage_units * unit_volume,
        "projected_required_volume_m3": primary_projected_units * unit_volume,
        "current_required_weight_kg": primary_storage_units * unit_weight,
        "projected_required_weight_kg": primary_projected_units * unit_weight,
        "current_cube_utilization_need_m3": current_units * unit_volume,
        "projected_cube_utilization_need_m3": projected_units * unit_volume,
        "current_weight_need_kg": current_units * unit_weight,
        "projected_weight_need_kg": projected_units * unit_weight,
        "temperature_control_required": temperature_required,
        "security_control_required": security_required,
        "forklift_required": forklift_required,
        "low_level_required": low_level_required,
        "ergonomic_level_required": ergonomic_level_required,
        "forklift_required_reason": ";".join(forklift_reasons) if forklift_reasons else "NOT_REQUIRED",
        "low_level_required_reason": ";".join(low_level_reasons) if low_level_reasons else "NOT_REQUIRED",
        "hazardous": _bool(row.get("hazardous")),
        "max_stack_height_m": max_stack_height,
    }, warnings


def _slotting_priority(row: pd.Series) -> float:
    """Return slotting priority from classification, movement, status, and storage needs."""
    score = 0.0
    if row.get("abc_class") == "A":
        score += 0.20
    elif row.get("abc_class") == "B":
        score += 0.10
    if row.get("fsn_class") == "F":
        score += 0.20
    elif row.get("fsn_class") == "S":
        score += 0.10
    if row.get("movement_class") == "FAST_MOVING":
        score += 0.15
    elif row.get("movement_class") == "MEDIUM_MOVING":
        score += 0.10
    elif row.get("movement_class") == "SLOW_MOVING":
        score += 0.05
    if row.get("inventory_priority_class") == "CRITICAL_PRIORITY":
        score += 0.10
    elif row.get("inventory_priority_class") == "HIGH_PRIORITY":
        score += 0.07
    if row.get("vitality_class") == "VITAL":
        score += 0.07
    elif row.get("vitality_class") == "IMPORTANT":
        score += 0.04
    if row.get("main_inventory_status") in {"STOCKOUT", "ZERO_STOCK", "REORDER_NOW", "CRITICAL_LOW_STOCK"}:
        score += 0.05
    if row.get("perishability_class") in {"SPOILAGE_RISK", "EXPIRY_TRACKED", "PERISHABLE"} or _bool(row.get("fefo_required")):
        score += 0.05
    if _bool(row.get("temperature_required")) or _bool(row.get("temperature_control_required")):
        score += 0.05
    if _bool(row.get("security_required")) or _bool(row.get("security_control_required")):
        score += 0.05
    return round(min(max(score, 0.0), 1.0), 3)


def _recommended_zone(row: pd.Series, requirements: dict) -> str:
    """Choose a recommended storage zone or specialized area label."""
    quarantine_units = _float(row.get("quarantine_units"))
    normal_storage_units = _float(row.get("normal_storage_units"))
    replenishment_units = _float(requirements.get("replenishment_units"))
    current_units = _float(requirements.get("current_units_for_space"))
    if quarantine_units > 0 and normal_storage_units <= 0 and replenishment_units <= 0 and quarantine_units >= max(current_units, 0):
        return "QUARANTINE"
    if row.get("primary_action") in {"MARKDOWN_NEAR_EXPIRY", "RETURN_TO_SUPPLIER_IF_ALLOWED"}:
        return "RETURNS"
    if requirements["temperature_control_required"]:
        return "TEMPERATURE_CONTROLLED"
    if requirements["security_control_required"]:
        return "SECURITY_CONTROLLED"
    handling = str(row.get("handling_unit", "")).upper()
    if row.get("abc_class") == "A" or row.get("movement_class") == "FAST_MOVING":
        if handling == "PALLET":
            return "PALLET_STORAGE"
        if handling == "EACH":
            return "EACH_PICKING"
        return "FAST_PICK"
    if row.get("movement_class") == "NON_MOVING" or row.get("abc_class") == "C":
        return "BULK_STORAGE" if handling == "PALLET" else "SLOW_PICK"
    if handling == "PALLET":
        return "PALLET_STORAGE"
    if handling == "EACH":
        return "EACH_PICKING"
    if handling == "CASE":
        return "CASE_PICKING"
    preferred = str(row.get("preferred_zone", "")).strip().upper()
    return preferred if preferred else "SLOW_PICK"


def _normalize_locations(locations: pd.DataFrame) -> pd.DataFrame:
    """Normalize location columns to names expected by the slotting layer."""
    if locations.empty:
        return pd.DataFrame(columns=_location_base_columns())
    normalized = locations.copy()
    normalized["x"] = normalized.apply(lambda row: _first_value(row, ["x", "x_coord"], WAREHOUSE_SLOT_CONFIG["default_location_x"]), axis=1)
    normalized["y"] = normalized.apply(lambda row: _first_value(row, ["y", "y_coord"], WAREHOUSE_SLOT_CONFIG["default_location_y"]), axis=1)
    normalized["z"] = normalized.apply(lambda row: _first_value(row, ["z", "shelf_level"], WAREHOUSE_SLOT_CONFIG["default_location_z"]), axis=1)
    normalized["shelf"] = normalized.apply(lambda row: _first_value(row, ["shelf", "shelf_level"], ""), axis=1)
    normalized["bin"] = normalized.apply(lambda row: _first_value(row, ["bin"], ""), axis=1)
    normalized["distance_to_dock"] = normalized.apply(lambda row: _first_value(row, ["distance_to_dock"], pd.NA), axis=1)
    normalized["distance_to_exit"] = normalized.apply(lambda row: _first_value(row, ["distance_to_exit"], pd.NA), axis=1)
    normalized["distance_to_entrance"] = normalized.apply(lambda row: _first_value(row, ["distance_to_entrance"], pd.NA), axis=1)
    normalized["distance_to_pick_face"] = normalized.apply(
        lambda row: _first_value(row, ["distance_to_pick_face"], pd.NA),
        axis=1,
    )
    normalized["capacity_m3"] = normalized.apply(
        lambda row: _first_value(row, ["capacity_m3", "capacity_volume_m3"], WAREHOUSE_SLOT_CONFIG["default_location_capacity_m3"]),
        axis=1,
    )
    normalized["capacity_kg"] = normalized.apply(
        lambda row: _first_value(row, ["capacity_kg", "capacity_weight_kg"], WAREHOUSE_SLOT_CONFIG["default_location_capacity_kg"]),
        axis=1,
    )
    normalized["base_used_volume_m3"] = normalized.apply(
        lambda row: _first_value(row, ["current_used_volume_m3", "used_volume_m3"], 0),
        axis=1,
    )
    normalized["base_used_weight_kg"] = normalized.apply(
        lambda row: _first_value(row, ["current_used_weight_kg", "used_weight_kg"], 0),
        axis=1,
    )
    normalized["active"] = normalized.apply(lambda row: _bool(_first_value(row, ["active"], True)), axis=1)
    for column in [
        "forklift_accessible",
        "temperature_controlled",
        "security_controlled",
        "heavy_item_allowed",
        "fragile_item_allowed",
        "perishable_item_allowed",
    ]:
        if column not in normalized.columns:
            normalized[column] = False
        normalized[column] = normalized[column].apply(_bool)
    return normalized


def _location_base_columns() -> list[str]:
    """Return minimum normalized location columns."""
    return [
        "location_id",
        "zone",
        "aisle",
        "rack",
        "shelf",
        "bin",
        "x",
        "y",
        "z",
        "capacity_m3",
        "capacity_kg",
        "base_used_volume_m3",
        "base_used_weight_kg",
    ]


def _known_current_usage_by_location(prepared_skus: pd.DataFrame) -> dict:
    """Calculate known SKU volume/weight at current locations for utilization rebasing."""
    usage = {}
    for _, row in prepared_skus.iterrows():
        location_id = str(row.get("current_location_id", "")).strip()
        if not location_id:
            continue
        entry = usage.setdefault(location_id, {"volume": 0.0, "weight": 0.0, "sku_count": 0})
        entry["volume"] += _float(row.get("total_current_inventory_volume_m3"))
        entry["weight"] += _float(row.get("total_current_inventory_weight_kg"))
        entry["sku_count"] += 1
    return usage


def _initial_location_state(locations: pd.DataFrame, known_usage: dict) -> dict:
    """Create mutable location capacity state."""
    state = {}
    for _, row in locations.iterrows():
        location_id = str(row.get("location_id", "")).strip()
        base_volume = max(_float(row.get("base_used_volume_m3")), 0.0)
        base_weight = max(_float(row.get("base_used_weight_kg")), 0.0)
        known_volume = max(_float(known_usage.get(location_id, {}).get("volume")), 0.0)
        known_weight = max(_float(known_usage.get(location_id, {}).get("weight")), 0.0)
        background_volume = max(base_volume - known_volume, 0.0)
        background_weight = max(base_weight - known_weight, 0.0)
        state[location_id] = {
            "assigned_skus": [],
            "assigned_primary_skus": [],
            "assigned_replenishment_skus": [],
            "assigned_quarantine_skus": [],
            "assigned_fefo_skus": [],
            "assigned_trace_only_batches": [],
            "base_used_volume_m3_original": base_volume,
            "base_used_weight_kg_original": base_weight,
            "known_current_sku_volume_rebased": known_volume,
            "known_current_sku_weight_rebased": known_weight,
            "background_used_volume_m3": background_volume,
            "background_used_weight_kg": background_weight,
            "rebased_utilization_applied": known_volume > 0 or known_weight > 0,
            "batch_level_location_utilization_applied": False,
            "assigned_primary_volume_m3": 0.0,
            "assigned_quarantine_volume_m3": 0.0,
            "assigned_fefo_volume_m3": 0.0,
            "assigned_replenishment_volume_m3": 0.0,
            "assigned_primary_weight_kg": 0.0,
            "assigned_quarantine_weight_kg": 0.0,
            "assigned_fefo_weight_kg": 0.0,
            "assigned_replenishment_weight_kg": 0.0,
            "current_used_volume_m3": background_volume,
            "projected_used_volume_m3": background_volume,
            "current_used_weight_kg": background_weight,
            "projected_used_weight_kg": background_weight,
        }
    return state


def _assign_sku(row: pd.Series, locations: pd.DataFrame, location_state: dict, layout_context: dict) -> dict:
    """Assign a SKU to the best feasible location using greedy remaining capacity."""
    warnings = list(row.get("_initial_warnings", []))
    scored = []
    for _, location in locations.iterrows():
        scored.append(_score_location(row, location, location_state, layout_context))
    nonprime_feasible = any(
        candidate["constraint_ok"]
        and candidate["current_fit"]
        and str(candidate["location"].get("zone", "")).upper() in {"SLOW_PICK", "BULK_STORAGE", "PALLET_STORAGE"}
        for candidate in scored
    )
    projected = [candidate for candidate in scored if candidate["constraint_ok"] and candidate["projected_fit"]]
    current = [candidate for candidate in scored if candidate["constraint_ok"] and candidate["current_fit"]]

    if projected:
        assignment = max(projected, key=lambda candidate: candidate["score"])
        status = "ASSIGNED"
    elif current:
        assignment = max(current, key=lambda candidate: candidate["score"])
        status = "REVIEW_REQUIRED"
        warnings.append("INSUFFICIENT_SPACE_AFTER_ORDER")
    else:
        assignment = max(scored, key=lambda candidate: candidate["score"]) if scored else _blank_assignment(layout_context)
        status = "NO_FEASIBLE_LOCATION"
        warnings.append("NO_FEASIBLE_LOCATION_FOUND")

    if not scored:
        warnings.append("MISSING_LOCATION_DATA")
    if status != "NO_FEASIBLE_LOCATION":
        assignment = _assignment_with_after_metrics(row, assignment, location_state)
    assignment["nonprime_feasible"] = nonprime_feasible

    result = _slotting_result(row, assignment, status, warnings, layout_context)
    if result["recommended_location_id"]:
        _update_location_state(row, result, location_state)
    return result


def _assignment_with_after_metrics(row: pd.Series, assignment: dict, location_state: dict) -> dict:
    """Attach current/projected after-assignment metrics to the chosen location series."""
    location = assignment.get("location", pd.Series(dtype=object)).copy()
    location_id = str(location.get("location_id", "")).strip()
    state = location_state.get(location_id, {})
    location["_current_after_assignment_volume_m3"] = _float(state.get("current_used_volume_m3")) + _float(row.get("current_required_volume_m3"))
    location["_projected_after_assignment_volume_m3"] = _float(state.get("projected_used_volume_m3")) + _float(row.get("projected_required_volume_m3"))
    location["_current_after_assignment_weight_kg"] = _float(state.get("current_used_weight_kg")) + _float(row.get("current_required_weight_kg"))
    location["_projected_after_assignment_weight_kg"] = _float(state.get("projected_used_weight_kg")) + _float(row.get("projected_required_weight_kg"))
    updated = dict(assignment)
    updated["location"] = location
    return updated


def _score_location(row: pd.Series, location: pd.Series, location_state: dict, layout_context: dict) -> dict:
    """Score one SKU-location candidate."""
    location_id = str(location.get("location_id", "")).strip()
    state = location_state.get(location_id, {})
    capacity_m3 = _float(location.get("capacity_m3"), WAREHOUSE_SLOT_CONFIG["default_location_capacity_m3"])
    capacity_kg = _float(location.get("capacity_kg"), WAREHOUSE_SLOT_CONFIG["default_location_capacity_kg"])
    current_remaining_m3 = capacity_m3 - _float(state.get("current_used_volume_m3"))
    projected_remaining_m3 = capacity_m3 - _float(state.get("projected_used_volume_m3"))
    current_remaining_kg = capacity_kg - _float(state.get("current_used_weight_kg"))
    projected_remaining_kg = capacity_kg - _float(state.get("projected_used_weight_kg"))

    constraint_ok = _location_constraints_ok(row, location)
    current_fit = (
        current_remaining_m3 >= _float(row.get("current_required_volume_m3"))
        and current_remaining_kg >= _float(row.get("current_required_weight_kg"))
    )
    projected_fit = (
        projected_remaining_m3 >= _float(row.get("projected_required_volume_m3"))
        and projected_remaining_kg >= _float(row.get("projected_required_weight_kg"))
    )
    distance = _travel_metrics(location, layout_context)
    score = _location_score(row, location, projected_remaining_m3, capacity_m3, distance)
    if not constraint_ok:
        score -= 1.0
    if not current_fit:
        score -= 0.6
    elif not projected_fit:
        score -= 0.2
    return {
        "location": location,
        "score": score,
        "constraint_ok": constraint_ok,
        "current_fit": current_fit,
        "projected_fit": projected_fit,
        **distance,
    }


def _location_constraints_ok(row: pd.Series, location: pd.Series) -> bool:
    """Return True when location capabilities satisfy SKU requirements."""
    if not _bool(location.get("active"), default=True):
        return False
    if _bool(row.get("forklift_required")) and not _bool(location.get("forklift_accessible")):
        return False
    if _bool(row.get("temperature_control_required")) and not _bool(location.get("temperature_controlled")):
        return False
    if _bool(row.get("security_control_required")) and not _bool(location.get("security_controlled")):
        return False
    if _bool(row.get("fragile")) and not _bool(location.get("fragile_item_allowed")):
        return False
    if (_bool(row.get("perishable")) or _bool(row.get("fefo_required"))) and not _bool(location.get("perishable_item_allowed")):
        return False
    if _is_heavy_sku(row) and not _bool(location.get("heavy_item_allowed")):
        return False
    return True


def _location_score(row: pd.Series, location: pd.Series, projected_remaining_m3: float, capacity_m3: float, distance: dict) -> float:
    """Calculate candidate score from zone fit, distance, and capability matches."""
    score = 0.0
    zone = str(location.get("zone", "")).upper()
    recommended_zone = str(row.get("recommended_storage_zone", "")).upper()
    handling = str(row.get("handling_unit", "")).upper()
    if recommended_zone == zone:
        score += 0.35
    elif recommended_zone == "TEMPERATURE_CONTROLLED" and _bool(location.get("temperature_controlled")):
        score += 0.35
    elif recommended_zone == "SECURITY_CONTROLLED" and _bool(location.get("security_controlled")):
        score += 0.35
    elif recommended_zone == "FAST_PICK" and zone in {"FAST_PICK", "CASE_PICKING", "EACH_PICKING"}:
        score += 0.25
    elif recommended_zone == "BULK_STORAGE" and zone in {"BULK_STORAGE", "SLOW_PICK", "PALLET_STORAGE"}:
        score += 0.25

    if handling == "PALLET" and zone in {"PALLET_STORAGE", "BULK_STORAGE", "FAST_PICK"}:
        score += 0.12
    elif handling == "CASE" and zone in {"CASE_PICKING", "FAST_PICK"}:
        score += 0.12
    elif handling == "EACH" and zone in {"EACH_PICKING", "FAST_PICK"}:
        score += 0.12

    if _bool(row.get("temperature_control_required")) and _bool(location.get("temperature_controlled")):
        score += 0.08
    if _bool(row.get("security_control_required")) and _bool(location.get("security_controlled")):
        score += 0.08
    if _bool(row.get("forklift_required")) and _bool(location.get("forklift_accessible")):
        score += 0.05
    if _bool(row.get("low_level_required")) and _float(location.get("z")) <= WAREHOUSE_Z_LEVEL_RULES["low_level_max_z"]:
        score += 0.05
    score += _z_level_score(row, location) * 0.15

    distance_score = 1 - min(distance["total_travel_distance_m"] / max(WAREHOUSE_TRAVEL_THRESHOLDS["high_distance_m"], 1), 1)
    if row.get("movement_class") in {"FAST_MOVING", "MEDIUM_MOVING"} or row.get("abc_class") == "A":
        score += distance_score * 0.20
    elif recommended_zone in {"SLOW_PICK", "BULK_STORAGE"}:
        score += (1 - distance_score) * 0.08
    else:
        score += distance_score * 0.10

    if capacity_m3 > 0:
        remaining_ratio = max(projected_remaining_m3, 0) / capacity_m3
        score += min(remaining_ratio, 0.5) * 0.12
    if str(row.get("current_location_id", "")).strip() == str(location.get("location_id", "")).strip():
        score += 0.05
    return score


def _slotting_result(row: pd.Series, assignment: dict, status: str, warnings: list[str], layout_context: dict) -> dict:
    """Build one warehouse_slotting row."""
    location = assignment.get("location", pd.Series(dtype=object))
    location_id = str(location.get("location_id", "")).strip()
    distance = {
        "distance_from_receiving_m": assignment.get("distance_from_receiving_m", 0.0),
        "distance_to_shipping_m": assignment.get("distance_to_shipping_m", 0.0),
        "distance_to_pick_face_m": assignment.get("distance_to_pick_face_m", WAREHOUSE_SLOT_CONFIG["default_pick_face_distance_m"]),
        "one_way_operational_distance_m": assignment.get("one_way_operational_distance_m", 0.0),
        "total_travel_distance_m": assignment.get("total_travel_distance_m", 0.0),
        "travel_time_min": assignment.get("travel_time_min", 0.0),
        "travel_cost": assignment.get("travel_cost", 0.0),
        "travel_distance_basis": assignment.get("travel_distance_basis", "FALLBACK_DISTANCE"),
        "travel_threshold_basis": assignment.get("travel_threshold_basis", "TOTAL_ROUTE"),
    }
    capacity = _capacity_metrics(row, location, status)
    zone_match_type = _zone_match_type(row, location, status)
    info_flags = []
    warnings.extend(_capability_warnings(row, location, status, assignment.get("nonprime_feasible", False)))
    warnings.extend(_travel_warnings(row, distance))
    warnings.extend(_utilization_warnings(row, location, capacity))
    if zone_match_type == "CAPABILITY_MATCH":
        info_flags.append("CAPABILITY_MATCH_NON_EXACT_ZONE")
    if "TRAVEL_THRESHOLD_USES_ONE_WAY" in warnings:
        info_flags.append("TRAVEL_THRESHOLD_USES_ONE_WAY")
    if "TRAVEL_THRESHOLD_USES_TOTAL_ROUTE" in warnings:
        info_flags.append("TRAVEL_THRESHOLD_USES_TOTAL_ROUTE")
    if _float(row.get("quarantine_units")) > 0 and str(row.get("recommended_storage_zone", "")).upper() != "QUARANTINE":
        warnings.append("WHOLE_SKU_QUARANTINE_AVOIDED_BY_BATCH_SPLIT")
    if _float(row.get("quarantine_units")) > 0 or _float(row.get("near_expiry_units_for_fefo")) > 0:
        warnings.append("SKU_VOLUME_SPLIT_BY_BATCH_STATUS")
    if _float(row.get("expired_empty_batch_count")) > 0:
        warnings.append("ZERO_QUANTITY_EXPIRED_BATCH_TRACE_ONLY")
    if _float(row.get("near_expiry_empty_batch_count")) > 0:
        warnings.append("ZERO_QUANTITY_NEAR_EXPIRY_BATCH_TRACE_ONLY")
    warnings = _unique(warnings)
    warnings = [warning for warning in warnings if warning not in {"TRAVEL_THRESHOLD_USES_ONE_WAY", "TRAVEL_THRESHOLD_USES_TOTAL_ROUTE", "CAPABILITY_MATCH_ZONE_MISMATCH"}]
    info_flags = _unique(info_flags)

    frequency = max(_float(row.get("movement_count")), 1.0)
    action = _slotting_action(row, location, status, warnings)
    map_color_group = _map_color_group(row, status)
    reason = _slotting_reason(row, status, action, warnings)
    return {
        "sku_id": row.get("sku_id"),
        "product_name": row.get("product_name"),
        "category": row.get("category"),
        "current_inventory": _float(row.get("current_inventory")),
        "inventory_position": _float(row.get("inventory_position")),
        "recommended_order_quantity": _float(row.get("recommended_order_quantity")),
        "projected_units_after_order": _float(row.get("projected_units_after_order")),
        "abc_class": row.get("abc_class"),
        "fsn_class": row.get("fsn_class"),
        "movement_class": row.get("movement_class"),
        "vitality_class": row.get("vitality_class"),
        "perishability_class": row.get("perishability_class"),
        "seasonality_class": row.get("seasonality_class"),
        "inventory_priority_class": row.get("inventory_priority_class"),
        "main_inventory_status": row.get("main_inventory_status"),
        "primary_action": row.get("primary_action"),
        "action_priority": row.get("action_priority"),
        "main_cost_driver": row.get("main_cost_driver"),
        "cost_risk_level": row.get("cost_risk_level"),
        "movement_count": _float(row.get("movement_count")),
        "handling_unit": row.get("handling_unit"),
        "unit_volume_m3": _float(row.get("unit_volume_m3")),
        "unit_weight_kg": _float(row.get("unit_weight_kg")),
        "temperature_control_required": _bool(row.get("temperature_control_required")),
        "security_control_required": _bool(row.get("security_control_required")),
        "forklift_required": _bool(row.get("forklift_required")),
        "low_level_required": _bool(row.get("low_level_required")),
        "ergonomic_level_required": _bool(row.get("ergonomic_level_required")),
        "forklift_required_reason": row.get("forklift_required_reason"),
        "low_level_required_reason": row.get("low_level_required_reason"),
        "fefo_required": _bool(row.get("fefo_required")),
        "expiry_tracking_required": _bool(row.get("expiry_tracking_required")),
        "fragile": _bool(row.get("fragile")),
        "hazardous": _bool(row.get("hazardous")),
        "stackable": _bool(row.get("stackable")),
        "max_stack_height_m": _float(row.get("max_stack_height_m")),
        "slotting_priority_score": _float(row.get("slotting_priority_score")),
        "z_level_score": _round(_z_level_score(row, location)) if not location.empty else 0.0,
        "recommended_storage_zone": row.get("recommended_storage_zone"),
        "recommended_location_id": location_id if status != "NO_FEASIBLE_LOCATION" else "",
        "location_assignment_status": _assignment_status(status, warnings),
        "current_location_id": row.get("current_location_id"),
        "zone": location.get("zone", ""),
        "aisle": location.get("aisle", ""),
        "rack": location.get("rack", ""),
        "shelf": location.get("shelf", ""),
        "bin": location.get("bin", ""),
        "assigned_temperature_controlled": _bool(location.get("temperature_controlled")),
        "assigned_security_controlled": _bool(location.get("security_controlled")),
        "assigned_forklift_accessible": _bool(location.get("forklift_accessible")),
        "assigned_perishable_allowed": _bool(location.get("perishable_item_allowed")),
        "assigned_fragile_allowed": _bool(location.get("fragile_item_allowed")),
        "assigned_heavy_allowed": _bool(location.get("heavy_item_allowed")),
        "zone_match_type": zone_match_type,
        "expired_batch_ids": row.get("expired_batch_ids", ""),
        "near_expiry_batch_ids": row.get("near_expiry_batch_ids", ""),
        "healthy_batch_ids": row.get("healthy_batch_ids", ""),
        "expired_batch_count": int(_float(row.get("expired_batch_count"))),
        "near_expiry_batch_count": int(_float(row.get("near_expiry_batch_count"))),
        "healthy_batch_count": int(_float(row.get("healthy_batch_count"))),
        "active_expired_batch_count": int(_float(row.get("active_expired_batch_count"))),
        "active_near_expiry_batch_count": int(_float(row.get("active_near_expiry_batch_count"))),
        "active_healthy_batch_count": int(_float(row.get("active_healthy_batch_count"))),
        "expired_empty_batch_count": int(_float(row.get("expired_empty_batch_count"))),
        "near_expiry_empty_batch_count": int(_float(row.get("near_expiry_empty_batch_count"))),
        "healthy_empty_batch_count": int(_float(row.get("healthy_empty_batch_count"))),
        "quarantine_units": _round(row.get("quarantine_units")),
        "near_expiry_units_for_fefo": _round(row.get("near_expiry_units_for_fefo")),
        "normal_storage_units": _round(row.get("normal_storage_units")),
        "replenishment_units": _round(row.get("replenishment_units")),
        "historical_expired_or_near_expiry_batch_exists": _float(row.get("expired_batch_count")) > 0 or _float(row.get("near_expiry_batch_count")) > 0,
        "quarantine_location_id": "",
        "fefo_location_id": "",
        "primary_storage_location_id": location_id if status != "NO_FEASIBLE_LOCATION" else "",
        "replenishment_receiving_location_id": "",
        "batch_split_required": _float(row.get("quarantine_units")) > 0 or _float(row.get("near_expiry_units_for_fefo")) > 0,
        "batch_split_reason": _batch_split_reason(row),
        "active_batch_split_reason": _active_batch_split_reason(row),
        "historical_batch_trace_reason": _historical_batch_trace_reason(row),
        "primary_storage_units": _round(row.get("primary_storage_units")),
        "quarantine_storage_units": _round(row.get("quarantine_storage_units")),
        "fefo_storage_units": _round(row.get("fefo_storage_units")),
        "replenishment_storage_units": _round(row.get("replenishment_storage_units")),
        "primary_storage_volume_m3": _round(row.get("primary_storage_volume_m3")),
        "quarantine_storage_volume_m3": _round(row.get("quarantine_storage_volume_m3")),
        "fefo_storage_volume_m3": _round(row.get("fefo_storage_volume_m3")),
        "replenishment_storage_volume_m3": _round(row.get("replenishment_storage_volume_m3")),
        "primary_projected_volume_m3": _round(row.get("primary_projected_volume_m3")),
        "primary_storage_weight_kg": _round(row.get("primary_storage_weight_kg")),
        "quarantine_storage_weight_kg": _round(row.get("quarantine_storage_weight_kg")),
        "fefo_storage_weight_kg": _round(row.get("fefo_storage_weight_kg")),
        "replenishment_storage_weight_kg": _round(row.get("replenishment_storage_weight_kg")),
        "primary_projected_weight_kg": _round(row.get("primary_projected_weight_kg")),
        "current_required_volume_m3": _round(row.get("current_required_volume_m3")),
        "projected_required_volume_m3": _round(row.get("projected_required_volume_m3")),
        "current_required_weight_kg": _round(row.get("current_required_weight_kg")),
        "projected_required_weight_kg": _round(row.get("projected_required_weight_kg")),
        **capacity,
        **distance,
        "frequency_adjusted_travel_distance_m": _round(distance["total_travel_distance_m"] * frequency),
        "frequency_adjusted_travel_cost": _round(distance["travel_cost"] * frequency),
        "slotting_warning_flags": ";".join(warnings),
        "slotting_info_flags": ";".join(info_flags),
        "slotting_action_recommendation": action,
        "slotting_reason": reason,
        "map_x": _float(location.get("x"), WAREHOUSE_SLOT_CONFIG["default_location_x"]),
        "map_y": _float(location.get("y"), WAREHOUSE_SLOT_CONFIG["default_location_y"]),
        "map_z": _float(location.get("z"), WAREHOUSE_SLOT_CONFIG["default_location_z"]),
        "map_zone": location.get("zone", ""),
        "map_label": f"{row.get('sku_id')} -> {location_id}" if location_id else str(row.get("sku_id")),
        "map_color_group": map_color_group,
        "_assigned_location_id": location_id if status != "NO_FEASIBLE_LOCATION" else "",
    }


def _capacity_metrics(row: pd.Series, location: pd.Series, status: str) -> dict:
    """Calculate SKU-level location capacity and space cost metrics."""
    if status == "NO_FEASIBLE_LOCATION" or location.empty:
        capacity_m3 = WAREHOUSE_SLOT_CONFIG["default_location_capacity_m3"]
        capacity_kg = WAREHOUSE_SLOT_CONFIG["default_location_capacity_kg"]
        current_used_volume = 0.0
        projected_used_volume = _float(row.get("projected_required_volume_m3"))
        current_used_weight = 0.0
        projected_used_weight = _float(row.get("projected_required_weight_kg"))
        zone = "DEFAULT"
    else:
        capacity_m3 = _float(location.get("capacity_m3"), WAREHOUSE_SLOT_CONFIG["default_location_capacity_m3"])
        capacity_kg = _float(location.get("capacity_kg"), WAREHOUSE_SLOT_CONFIG["default_location_capacity_kg"])
        current_used_volume = _float(location.get("_current_after_assignment_volume_m3"))
        projected_used_volume = _float(location.get("_projected_after_assignment_volume_m3"))
        current_used_weight = _float(location.get("_current_after_assignment_weight_kg"))
        projected_used_weight = _float(location.get("_projected_after_assignment_weight_kg"))
        zone = str(location.get("zone", "DEFAULT")).upper()

    current_util = _pct(current_used_volume, capacity_m3)
    projected_util = _pct(projected_used_volume, capacity_m3)
    current_weight_util = _pct(current_used_weight, capacity_kg)
    projected_weight_util = _pct(projected_used_weight, capacity_kg)
    shortage_m3 = max(projected_used_volume - capacity_m3, 0.0)
    shortage_kg = max(projected_used_weight - capacity_kg, 0.0)
    multiplier = _zone_multiplier(zone, location)
    storage_cost_per_m3 = WAREHOUSE_SLOT_CONFIG["default_storage_cost_per_m3"]
    current_space_cost = _float(row.get("current_required_volume_m3")) * storage_cost_per_m3 * multiplier
    projected_space_cost = _float(row.get("projected_required_volume_m3")) * storage_cost_per_m3 * multiplier
    if _float(row.get("recommended_order_quantity")) <= 0:
        incremental_space_cost = 0.0
    else:
        incremental_space_cost = max(projected_space_cost - current_space_cost, 0.0)
    current_units = max(_float(row.get("current_units_for_space")), 1.0)
    projected_units = max(_float(row.get("projected_units_after_order")), 1.0)
    return {
        "location_capacity_m3": _round(capacity_m3),
        "location_capacity_kg": _round(capacity_kg),
        "location_current_utilization_pct": _round(current_util),
        "location_projected_utilization_pct": _round(projected_util),
        "location_current_weight_utilization_pct": _round(current_weight_util),
        "location_projected_weight_utilization_pct": _round(projected_weight_util),
        "projected_space_shortage_m3": _round(shortage_m3),
        "projected_weight_shortage_kg": _round(shortage_kg),
        "current_space_utilization_cost": _round(current_space_cost),
        "projected_space_utilization_cost": _round(projected_space_cost),
        "incremental_space_cost_after_order": _round(incremental_space_cost),
        "current_storage_cost_per_unit": _round(current_space_cost / current_units),
        "projected_storage_cost_per_unit": _round(projected_space_cost / projected_units),
    }


def _update_location_state(row: pd.Series, result: dict, location_state: dict) -> None:
    """Update mutable location state after one SKU assignment."""
    location_id = result.get("_assigned_location_id")
    if not location_id or location_id not in location_state:
        return
    state = location_state[location_id]
    state["assigned_skus"].append(str(row.get("sku_id")))
    state["current_used_volume_m3"] += _float(row.get("current_required_volume_m3"))
    state["projected_used_volume_m3"] += _float(row.get("projected_required_volume_m3"))
    state["current_used_weight_kg"] += _float(row.get("current_required_weight_kg"))
    state["projected_used_weight_kg"] += _float(row.get("projected_required_weight_kg"))


def _zone_match_type(row: pd.Series, location: pd.Series, status: str) -> str:
    """Return how the assigned location matches the recommended zone."""
    if status == "NO_FEASIBLE_LOCATION" or location.empty:
        return "NO_FEASIBLE_LOCATION"
    recommended_zone = str(row.get("recommended_storage_zone", "")).upper()
    actual_zone = str(location.get("zone", "")).upper()
    if recommended_zone and recommended_zone == actual_zone:
        return "EXACT_ZONE_MATCH"
    if recommended_zone == "TEMPERATURE_CONTROLLED" and _bool(location.get("temperature_controlled")):
        return "CAPABILITY_MATCH"
    if recommended_zone == "SECURITY_CONTROLLED" and _bool(location.get("security_controlled")):
        return "CAPABILITY_MATCH"
    compatible = {
        "FAST_PICK": {"CASE_PICKING", "EACH_PICKING"},
        "CASE_PICKING": {"FAST_PICK", "EACH_PICKING"},
        "EACH_PICKING": {"FAST_PICK", "CASE_PICKING"},
        "BULK_STORAGE": {"SLOW_PICK", "PALLET_STORAGE"},
        "SLOW_PICK": {"BULK_STORAGE", "PALLET_STORAGE"},
        "PALLET_STORAGE": {"BULK_STORAGE"},
        "RECEIVING": {"PUTAWAY", "CROSSDOCKING"},
        "QUARANTINE": {"RETURNS"},
    }
    if actual_zone in compatible.get(recommended_zone, set()):
        return "COMPATIBLE_ZONE_MATCH"
    return "FALLBACK_ZONE"


def _batch_split_reason(row: pd.Series) -> str:
    """Return a SKU-level reason for batch split handling."""
    expired_count = int(_float(row.get("active_expired_batch_count")))
    near_count = int(_float(row.get("active_near_expiry_batch_count")))
    if expired_count and near_count:
        return "Expired batches are assigned separately to quarantine and near-expiry batches are assigned for FEFO picking; primary SKU location remains normal storage."
    if expired_count:
        return "Expired batches are assigned separately to quarantine; primary SKU location remains normal storage for sellable or replenishment inventory."
    if near_count:
        return "Near-expiry batches are assigned separately to FEFO-accessible picking; primary SKU location remains normal storage."
    return "No batch split required."


def _active_batch_split_reason(row: pd.Series) -> str:
    """Return operational active batch split reason."""
    if _float(row.get("quarantine_units")) > 0 and _float(row.get("near_expiry_units_for_fefo")) > 0:
        return "Active expired units require quarantine and active near-expiry units require FEFO-accessible storage."
    if _float(row.get("quarantine_units")) > 0:
        return "Active expired units require quarantine; healthy/replenishment units remain in normal storage."
    if _float(row.get("near_expiry_units_for_fefo")) > 0:
        return "Active near-expiry units require FEFO-accessible storage; healthy/replenishment units remain in normal storage."
    return "No active expired or near-expiry quantity requires operational batch split."


def _historical_batch_trace_reason(row: pd.Series) -> str:
    """Return trace-only reason for historical zero-quantity batches."""
    expired_empty = int(_float(row.get("expired_empty_batch_count")))
    near_empty = int(_float(row.get("near_expiry_empty_batch_count")))
    if expired_empty and near_empty:
        return "Expired and near-expiry batch IDs exist with zero active quantity; retained for traceability only."
    if expired_empty:
        return "Expired batch IDs exist with zero active quantity; retained for traceability only."
    if near_empty:
        return "Near-expiry batch IDs exist with zero active quantity; retained for traceability only."
    if _float(row.get("expired_batch_count")) > 0 or _float(row.get("near_expiry_batch_count")) > 0:
        return "Historical expired or near-expiry batch records exist and active quantities are handled separately."
    return "No historical expired or near-expiry batch trace issue."


def _capability_warnings(row: pd.Series, location: pd.Series, status: str, nonprime_feasible: bool = False) -> list[str]:
    """Return capability and handling warnings for an assignment."""
    if status == "NO_FEASIBLE_LOCATION" or location.empty:
        return ["NO_FEASIBLE_LOCATION_FOUND", "MISSING_LOCATION_DATA"]
    warnings = []
    if _bool(row.get("forklift_required")) and not _bool(location.get("forklift_accessible")):
        warnings.append("FORKLIFT_ACCESS_REQUIRED_BUT_MISSING")
    if _bool(row.get("temperature_control_required")) and not _bool(location.get("temperature_controlled")):
        warnings.append("TEMPERATURE_CONTROL_REQUIRED_BUT_MISSING")
    if _bool(row.get("security_control_required")) and not _bool(location.get("security_controlled")):
        warnings.append("SECURITY_REQUIRED_BUT_MISSING")
    z_level = _float(location.get("z"))
    if _is_heavy_sku(row) and z_level > WAREHOUSE_Z_LEVEL_RULES["low_level_max_z"]:
        warnings.append("HEAVY_ITEM_NOT_LOW_LEVEL")
    if row.get("movement_class") == "FAST_MOVING" and z_level > WAREHOUSE_Z_LEVEL_RULES["fast_moving_max_preferred_z"]:
        warnings.append("FAST_MOVING_ITEM_NOT_ERGONOMIC")
    if _bool(row.get("fragile")) and z_level > WAREHOUSE_Z_LEVEL_RULES["fragile_max_preferred_z"]:
        warnings.append("FRAGILE_ITEM_HIGH_LEVEL")
    active_fefo_units = _float(row.get("near_expiry_units_for_fefo")) > 0
    if active_fefo_units and _bool(row.get("fefo_required")) and str(location.get("zone", "")).upper() in {"BULK_STORAGE", "SLOW_PICK"}:
        warnings.append("FEFO_REQUIRED_BUT_NOT_SUPPORTED")
    if active_fefo_units and _bool(row.get("fefo_required")) and str(location.get("zone", "")).upper() not in {"FAST_PICK", "CASE_PICKING", "EACH_PICKING", "RECEIVING", "QUARANTINE"}:
        warnings.append("PERISHABLE_ITEM_NEEDS_FEFO_ACCESS")
    if _slow_item_in_prime_space(row, location, nonprime_feasible):
        warnings.extend(["SLOW_OR_NON_MOVING_ITEM_IN_FAST_PICK", "PRIME_SPACE_USED_BY_SLOW_ITEM"])
    return warnings


def _slow_item_in_prime_space(row: pd.Series, location: pd.Series, nonprime_feasible: bool) -> bool:
    """Return True when a slow/non-moving SKU occupies prime pick space without a strong reason."""
    zone = str(location.get("zone", "")).upper()
    slow_profile = row.get("movement_class") in {"SLOW_MOVING", "NON_MOVING"} or row.get("fsn_class") == "N"
    if not slow_profile or zone not in {"FAST_PICK", "EACH_PICKING", "CASE_PICKING"}:
        return False
    if _float(row.get("near_expiry_units_for_fefo")) > 0 or _float(row.get("near_expiry_units")) > 0:
        return False
    if row.get("main_inventory_status") in {"STOCKOUT", "ZERO_STOCK"} and row.get("inventory_priority_class") == "CRITICAL_PRIORITY":
        return False
    if _bool(row.get("temperature_control_required")) or _bool(row.get("security_control_required")):
        return False
    return bool(nonprime_feasible)


def _travel_warnings(row: pd.Series, distance: dict) -> list[str]:
    """Return distance-related slotting warnings."""
    warnings = []
    total_distance = _float(distance.get("total_travel_distance_m"))
    one_way = _float(distance.get("one_way_operational_distance_m"))
    if distance.get("travel_threshold_basis") == "ONE_WAY":
        if row.get("movement_class") == "FAST_MOVING" and one_way > WAREHOUSE_TRAVEL_THRESHOLDS["fast_moving_max_one_way_distance_m"]:
            warnings.extend(["FAST_MOVING_ITEM_TOO_FAR", "TRAVEL_THRESHOLD_USES_ONE_WAY"])
        if row.get("abc_class") == "A" and one_way > WAREHOUSE_TRAVEL_THRESHOLDS["a_class_max_one_way_distance_m"]:
            warnings.extend(["A_CLASS_ITEM_TOO_FAR", "TRAVEL_THRESHOLD_USES_ONE_WAY"])
    else:
        if row.get("movement_class") == "FAST_MOVING" and total_distance > WAREHOUSE_TRAVEL_THRESHOLDS["fast_moving_max_total_route_distance_m"]:
            warnings.extend(["FAST_MOVING_ITEM_TOO_FAR", "TRAVEL_THRESHOLD_USES_TOTAL_ROUTE"])
        if row.get("abc_class") == "A" and total_distance > WAREHOUSE_TRAVEL_THRESHOLDS["a_class_max_total_route_distance_m"]:
            warnings.extend(["A_CLASS_ITEM_TOO_FAR", "TRAVEL_THRESHOLD_USES_TOTAL_ROUTE"])
    if total_distance > WAREHOUSE_TRAVEL_THRESHOLDS["high_distance_m"]:
        warnings.append("HIGH_TRAVEL_DISTANCE")
    return warnings


def _utilization_warnings(row: pd.Series, location: pd.Series, capacity: dict) -> list[str]:
    """Return capacity and utilization warnings."""
    warnings = []
    if capacity["location_current_utilization_pct"] > WAREHOUSE_UTILIZATION_THRESHOLDS["over_capacity_pct"]:
        warnings.append("LOCATION_OVER_CAPACITY")
    if (
        capacity["location_projected_utilization_pct"] > WAREHOUSE_UTILIZATION_THRESHOLDS["projected_over_capacity_pct"]
        or capacity["location_projected_weight_utilization_pct"] > WAREHOUSE_UTILIZATION_THRESHOLDS["projected_over_capacity_pct"]
    ):
        warnings.append("INSUFFICIENT_SPACE_AFTER_ORDER")
    elif capacity["location_projected_utilization_pct"] > WAREHOUSE_UTILIZATION_THRESHOLDS["target_location_utilization_max_pct"]:
        warnings.append("PROJECTED_CAPACITY_PRESSURE")
    prime_zone = str(location.get("zone", "")).upper() in {"FAST_PICK", "CASE_PICKING", "EACH_PICKING"}
    if prime_zone and capacity["location_projected_utilization_pct"] < WAREHOUSE_UTILIZATION_THRESHOLDS["target_location_utilization_min_pct"]:
        warnings.append("LOW_LOCATION_UTILIZATION")
    return warnings


def _travel_metrics(location: pd.Series, layout_context: dict) -> dict:
    """Calculate Manhattan travel metrics for a location."""
    if WAREHOUSE_TRAVEL_THRESHOLDS.get("prefer_existing_location_distance_fields", False):
        dock = _float(location.get("distance_to_dock"), default=float("nan"))
        exit_distance = _float(location.get("distance_to_exit"), default=float("nan"))
        entrance = _float(location.get("distance_to_entrance"), default=float("nan"))
        pick_face = _float(location.get("distance_to_pick_face"), default=float("nan"))
        available = [value for value in [dock, exit_distance, entrance, pick_face] if not pd.isna(value) and value > 0]
        if available:
            receiving_distance = entrance if not pd.isna(entrance) and entrance > 0 else dock
            shipping_distance = exit_distance if not pd.isna(exit_distance) and exit_distance > 0 else dock
            pick_face_distance = pick_face if not pd.isna(pick_face) and pick_face > 0 else min(available)
            total_distance = _float(receiving_distance) + _float(shipping_distance)
            one_way = min(available)
            travel_time = total_distance / max(WAREHOUSE_SLOT_CONFIG["default_travel_speed_m_per_min"], 1.0)
            travel_cost = total_distance * WAREHOUSE_SLOT_CONFIG["default_travel_cost_per_meter"]
            return {
                "distance_from_receiving_m": _round(receiving_distance),
                "distance_to_shipping_m": _round(shipping_distance),
                "distance_to_pick_face_m": _round(pick_face_distance),
                "one_way_operational_distance_m": _round(one_way),
                "total_travel_distance_m": _round(total_distance),
                "travel_time_min": _round(travel_time),
                "travel_cost": _round(travel_cost),
                "travel_distance_basis": "LOCATION_DISTANCE_FIELDS",
                "travel_threshold_basis": "ONE_WAY",
            }
    x = _float(location.get("x"), WAREHOUSE_SLOT_CONFIG["default_location_x"])
    y = _float(location.get("y"), WAREHOUSE_SLOT_CONFIG["default_location_y"])
    receiving_distance = abs(x - layout_context["receiving_x"]) + abs(y - layout_context["receiving_y"])
    shipping_distance = abs(x - layout_context["shipping_x"]) + abs(y - layout_context["shipping_y"])
    total_distance = receiving_distance + shipping_distance
    travel_time = total_distance / max(WAREHOUSE_SLOT_CONFIG["default_travel_speed_m_per_min"], 1.0)
    travel_cost = total_distance * WAREHOUSE_SLOT_CONFIG["default_travel_cost_per_meter"]
    return {
        "distance_from_receiving_m": _round(receiving_distance),
        "distance_to_shipping_m": _round(shipping_distance),
        "distance_to_pick_face_m": _round(_float(location.get("distance_to_exit"), WAREHOUSE_SLOT_CONFIG["default_pick_face_distance_m"])),
        "one_way_operational_distance_m": _round(min(receiving_distance, shipping_distance)),
        "total_travel_distance_m": _round(total_distance),
        "travel_time_min": _round(travel_time),
        "travel_cost": _round(travel_cost),
        "travel_distance_basis": "COORDINATE_CALCULATION",
        "travel_threshold_basis": "TOTAL_ROUTE",
    }


def _layout_context(warehouse_layout: pd.DataFrame) -> dict:
    """Return receiving/shipping coordinates from layout or config fallbacks."""
    if warehouse_layout.empty:
        return {
            "receiving_x": WAREHOUSE_SLOT_CONFIG["receiving_x"],
            "receiving_y": WAREHOUSE_SLOT_CONFIG["receiving_y"],
            "shipping_x": WAREHOUSE_SLOT_CONFIG["shipping_x"],
            "shipping_y": WAREHOUSE_SLOT_CONFIG["shipping_y"],
        }
    row = warehouse_layout.iloc[0]
    return {
        "receiving_x": _float(row.get("dock_x"), WAREHOUSE_SLOT_CONFIG["receiving_x"]),
        "receiving_y": _float(row.get("dock_y"), WAREHOUSE_SLOT_CONFIG["receiving_y"]),
        "shipping_x": _float(row.get("exit_x"), WAREHOUSE_SLOT_CONFIG["shipping_x"]),
        "shipping_y": _float(row.get("exit_y"), WAREHOUSE_SLOT_CONFIG["shipping_y"]),
    }


def _blank_assignment(layout_context: dict) -> dict:
    """Return blank assignment when no locations exist."""
    return {
        "location": pd.Series(dtype=object),
        "score": 0.0,
        "constraint_ok": False,
        "current_fit": False,
        "projected_fit": False,
        "distance_from_receiving_m": 0.0,
        "distance_to_shipping_m": 0.0,
        "distance_to_pick_face_m": WAREHOUSE_SLOT_CONFIG["default_pick_face_distance_m"],
        "one_way_operational_distance_m": 0.0,
        "total_travel_distance_m": 0.0,
        "travel_time_min": 0.0,
        "travel_cost": 0.0,
        "travel_distance_basis": "FALLBACK_DISTANCE",
        "travel_threshold_basis": "TOTAL_ROUTE",
        "nonprime_feasible": False,
    }


def _assignment_status(status: str, warnings: list[str]) -> str:
    """Return final assignment status."""
    if status == "NO_FEASIBLE_LOCATION":
        return "NO_FEASIBLE_LOCATION"
    severe = {"INSUFFICIENT_SPACE_AFTER_ORDER", "NO_FEASIBLE_LOCATION_FOUND"}
    if status == "REVIEW_REQUIRED" or severe.intersection(warnings):
        return "REVIEW_REQUIRED"
    return "ASSIGNED_WITH_WARNINGS" if warnings else "ASSIGNED"


def _slotting_action(row: pd.Series, location: pd.Series, status: str, warnings: list[str]) -> str:
    """Recommend a warehouse slotting action."""
    actual_zone = str(location.get("zone", "")).upper()
    recommended_zone = str(row.get("recommended_storage_zone", "")).upper()
    if status == "NO_FEASIBLE_LOCATION" or "NO_FEASIBLE_LOCATION_FOUND" in warnings:
        return "REVIEW_MANUALLY"
    if "SLOW_OR_NON_MOVING_ITEM_IN_FAST_PICK" in warnings or "PRIME_SPACE_USED_BY_SLOW_ITEM" in warnings:
        return "MOVE_SLOW_ITEM_OUT_OF_FAST_PICK"
    if "WHOLE_SKU_QUARANTINE_AVOIDED_BY_BATCH_SPLIT" in warnings and _float(row.get("quarantine_units")) > 0:
        return "QUARANTINE_EXPIRED_BATCHES_ONLY"
    if "WHOLE_SKU_QUARANTINE_AVOIDED_BY_BATCH_SPLIT" in warnings or _float(row.get("near_expiry_units_for_fefo")) > 0:
        return "SPLIT_BATCH_STORAGE"
    if "INSUFFICIENT_SPACE_AFTER_ORDER" in warnings or "PROJECTED_CAPACITY_PRESSURE" in warnings:
        return "REVIEW_CAPACITY_BEFORE_ORDER"
    if "TEMPERATURE_CONTROL_REQUIRED_BUT_MISSING" in warnings or (
        recommended_zone == "TEMPERATURE_CONTROLLED" and _bool(location.get("temperature_controlled"))
    ):
        return "MOVE_TO_TEMPERATURE_CONTROLLED"
    if "SECURITY_REQUIRED_BUT_MISSING" in warnings or (
        recommended_zone == "SECURITY_CONTROLLED" and _bool(location.get("security_controlled"))
    ):
        return "MOVE_TO_SECURITY_CONTROLLED"
    if "HEAVY_ITEM_NOT_LOW_LEVEL" in warnings:
        return "MOVE_TO_LOWER_LEVEL"
    if "FAST_MOVING_ITEM_NOT_ERGONOMIC" in warnings:
        return "MOVE_TO_FAST_PICK"
    if "FRAGILE_ITEM_HIGH_LEVEL" in warnings:
        return "MOVE_TO_LOWER_LEVEL"
    if "FEFO_REQUIRED_BUT_NOT_SUPPORTED" in warnings or "PERISHABLE_ITEM_NEEDS_FEFO_ACCESS" in warnings:
        return "REVIEW_FEFO_ROTATION"
    if recommended_zone == "FAST_PICK" and actual_zone == "FAST_PICK":
        return "MOVE_TO_FAST_PICK"
    if "FAST_MOVING_ITEM_TOO_FAR" in warnings:
        return "MOVE_TO_FAST_PICK"
    if recommended_zone == "BULK_STORAGE" and actual_zone == "BULK_STORAGE":
        return "MOVE_TO_BULK_STORAGE"
    if recommended_zone == "SLOW_PICK" and actual_zone == "SLOW_PICK":
        return "MOVE_TO_SLOW_PICK"
    current_location = str(row.get("current_location_id", "")).strip()
    if current_location and current_location == str(location.get("location_id", "")).strip():
        return "KEEP_CURRENT_LOCATION"
    if recommended_zone and recommended_zone != actual_zone and recommended_zone not in {"TEMPERATURE_CONTROLLED", "SECURITY_CONTROLLED"}:
        return "REVIEW_MANUALLY"
    return "REVIEW_MANUALLY" if warnings else "KEEP_CURRENT_LOCATION"


def _slotting_reason(row: pd.Series, status: str, action: str, warnings: list[str]) -> str:
    """Create readable slotting reason."""
    if status == "NO_FEASIBLE_LOCATION":
        return "No feasible location found that satisfies capacity and handling constraints."
    if action == "MOVE_SLOW_ITEM_OUT_OF_FAST_PICK":
        return "Slow/non-moving SKU is occupying prime pick space; review relocation to slow-pick or bulk storage to free fast-pick capacity."
    if action == "QUARANTINE_EXPIRED_BATCHES_ONLY":
        return "Expired batches are assigned to quarantine separately, while sellable and replenishment inventory remains in normal storage."
    if action == "SPLIT_BATCH_STORAGE":
        return _batch_split_reason(row)
    if "INSUFFICIENT_SPACE_AFTER_ORDER" in warnings:
        return "Projected inventory after recommended order exceeds assigned location capacity; review capacity before ordering."
    if "FAST_MOVING_ITEM_NOT_ERGONOMIC" in warnings:
        return "Fast-moving SKU is assigned above the preferred ergonomic pick level; review a lower pick face."
    if action == "MOVE_TO_FAST_PICK":
        return "A-class or fast-moving SKU should be placed close to shipping/receiving to reduce travel distance."
    if action == "MOVE_TO_TEMPERATURE_CONTROLLED":
        return "Temperature-controlled storage is required or preferred for this SKU."
    if action == "MOVE_TO_SECURITY_CONTROLLED":
        return "Security-controlled storage is required or preferred for this SKU."
    if action == "MOVE_TO_BULK_STORAGE":
        return "Slow, bulky, or overstocked SKU can use bulk storage to free prime pick space."
    if action == "MOVE_TO_SLOW_PICK":
        return "Slow or non-moving SKU can be placed in slow-pick space to protect prime locations."
    if action == "REVIEW_FEFO_ROTATION":
        return "Perishable FEFO SKU should be assigned to accessible location for rotation."
    if action == "MOVE_TO_LOWER_LEVEL":
        return "Heavy or palletized SKU should be stored at a lower accessible level."
    if "FRAGILE_ITEM_HIGH_LEVEL" in warnings:
        return "Fragile SKU is assigned to a high level; review a lower shelf to reduce handling damage risk."
    if action == "REVIEW_MANUALLY" and not warnings:
        return "Recommended location satisfies constraints but differs from the preferred zone; review manually before moving."
    if warnings:
        return "Location is assigned with warehouse handling, capacity, or travel warnings."
    return "Current or recommended location satisfies capacity, travel, and handling constraints."


def _add_batch_split_location_fields(warehouse_slotting: pd.DataFrame, locations: pd.DataFrame) -> pd.DataFrame:
    """Attach SKU-level location ids used by batch split slotting."""
    if warehouse_slotting.empty:
        return warehouse_slotting
    rows = []
    for _, row in warehouse_slotting.iterrows():
        updated = row.to_dict()
        sku_row = pd.Series(updated)
        primary_location_id = str(updated.get("recommended_location_id", "")).strip()
        if str(updated.get("zone", "")).upper() == "QUARANTINE" and (
            _float(updated.get("normal_storage_units")) > 0 or _float(updated.get("replenishment_units")) > 0
        ):
            primary_location_id = _best_normal_location_id(locations, sku_row) or primary_location_id
        updated["primary_storage_location_id"] = primary_location_id
        updated["quarantine_location_id"] = (
            _best_location_id(locations, "QUARANTINE", sku_row)
            if _float(updated.get("quarantine_units")) > 0
            else ""
        )
        updated["fefo_location_id"] = (
            _best_fefo_location_id(locations, sku_row)
            if _float(updated.get("near_expiry_units_for_fefo")) > 0
            else ""
        )
        replenishment_location_id = ""
        if _float(updated.get("replenishment_units")) > 0:
            replenishment_location_id = _best_location_id(
                locations,
                WAREHOUSE_BATCH_ZONE_RULES["replenishment_zone_fallback"],
                sku_row,
            ) or primary_location_id
        updated["replenishment_receiving_location_id"] = replenishment_location_id
        rows.append(updated)
    return pd.DataFrame(rows)


def _rebuild_location_state_from_slotting(location_state: dict, warehouse_slotting: pd.DataFrame) -> dict:
    """Rebuild proposed location utilization from split SKU/batch volume buckets."""
    rebuilt = {}
    for location_id, state in location_state.items():
        base = dict(state)
        background_volume = _float(base.get("background_used_volume_m3"))
        background_weight = _float(base.get("background_used_weight_kg"))
        base.update(
            {
                "assigned_skus": [],
                "assigned_primary_skus": [],
                "assigned_replenishment_skus": [],
                "assigned_quarantine_skus": [],
                "assigned_fefo_skus": [],
                "assigned_trace_only_batches": [],
                "batch_level_location_utilization_applied": False,
                "assigned_primary_volume_m3": 0.0,
                "assigned_quarantine_volume_m3": 0.0,
                "assigned_fefo_volume_m3": 0.0,
                "assigned_replenishment_volume_m3": 0.0,
                "assigned_primary_weight_kg": 0.0,
                "assigned_quarantine_weight_kg": 0.0,
                "assigned_fefo_weight_kg": 0.0,
                "assigned_replenishment_weight_kg": 0.0,
                "current_used_volume_m3": background_volume,
                "projected_used_volume_m3": background_volume,
                "current_used_weight_kg": background_weight,
                "projected_used_weight_kg": background_weight,
            }
        )
        rebuilt[location_id] = base

    for _, row in warehouse_slotting.iterrows():
        sku_id = str(row.get("sku_id", "")).strip()
        _apply_location_bucket(
            rebuilt,
            row.get("primary_storage_location_id") or row.get("recommended_location_id"),
            sku_id,
            "primary",
            _float(row.get("primary_storage_volume_m3")),
            _float(row.get("primary_storage_weight_kg")),
            current=True,
            projected=True,
        )
        _apply_location_bucket(
            rebuilt,
            row.get("quarantine_location_id"),
            sku_id,
            "quarantine",
            _float(row.get("quarantine_storage_volume_m3")),
            _float(row.get("quarantine_storage_weight_kg")),
            current=True,
            projected=True,
        )
        _apply_location_bucket(
            rebuilt,
            row.get("fefo_location_id"),
            sku_id,
            "fefo",
            _float(row.get("fefo_storage_volume_m3")),
            _float(row.get("fefo_storage_weight_kg")),
            current=True,
            projected=True,
        )
        _apply_location_bucket(
            rebuilt,
            row.get("replenishment_receiving_location_id") or row.get("primary_storage_location_id") or row.get("recommended_location_id"),
            sku_id,
            "replenishment",
            _float(row.get("replenishment_storage_volume_m3")),
            _float(row.get("replenishment_storage_weight_kg")),
            current=False,
            projected=True,
        )
    return rebuilt


def _apply_location_bucket(
    location_state: dict,
    location_id,
    sku_id: str,
    bucket: str,
    volume: float,
    weight: float,
    current: bool,
    projected: bool,
) -> None:
    """Apply one volume/weight bucket to a location state entry."""
    location_id = str(location_id or "").strip()
    if not location_id or location_id not in location_state or volume <= 0 and weight <= 0:
        return
    state = location_state[location_id]
    if sku_id and sku_id not in state["assigned_skus"]:
        state["assigned_skus"].append(sku_id)
    role_list = f"assigned_{bucket}_skus"
    if role_list in state and sku_id and sku_id not in state[role_list]:
        state[role_list].append(sku_id)
    state["batch_level_location_utilization_applied"] = True
    state[f"assigned_{bucket}_volume_m3"] += volume
    state[f"assigned_{bucket}_weight_kg"] += weight
    if current:
        state["current_used_volume_m3"] += volume
        state["current_used_weight_kg"] += weight
    if projected:
        state["projected_used_volume_m3"] += volume
        state["projected_used_weight_kg"] += weight


def build_batch_slotting_rows(
    inventory_batches_clean: pd.DataFrame,
    warehouse_slotting_df: pd.DataFrame,
    locations: pd.DataFrame,
    location_state: dict,
    layout_context: dict,
) -> pd.DataFrame:
    """Build one batch-level slotting row per inventory batch."""
    _ = location_state, layout_context
    if inventory_batches_clean.empty:
        return pd.DataFrame(columns=_batch_slotting_columns())
    sku_lookup = {
        str(row.get("sku_id", "")).strip(): row
        for _, row in warehouse_slotting_df.iterrows()
    }
    location_lookup = {
        str(row.get("location_id", "")).strip(): row
        for _, row in locations.iterrows()
    }
    rows = []
    for _, batch in inventory_batches_clean.iterrows():
        sku_id = str(batch.get("sku_id", "")).strip()
        sku_row = sku_lookup.get(sku_id, pd.Series(dtype=object))
        batch_status = _batch_slot_status(batch)
        batch_quantity = _batch_quantity(batch)
        active_batch_quantity = _active_batch_quantity(batch_quantity)
        recommended_zone = _recommended_batch_zone(batch_status, sku_row, active_batch_quantity)
        location_id = _recommended_batch_location_id(batch_status, sku_row, locations, active_batch_quantity, batch)
        location = location_lookup.get(location_id, pd.Series(dtype=object))
        warnings = _batch_warning_flags(batch_status, location_id, active_batch_quantity)
        visual = _batch_visual_fields(batch_status, batch_quantity, active_batch_quantity, warnings)
        assigned_zone = str(location.get("zone", "")).upper()
        rows.append(
            {
                "batch_id": batch.get("batch_id"),
                "sku_id": sku_id,
                "product_name": sku_row.get("product_name", "UNKNOWN") if not sku_row.empty else "UNKNOWN",
                "category": sku_row.get("category", "UNKNOWN") if not sku_row.empty else "UNKNOWN",
                "batch_quantity": _round(batch_quantity),
                "active_batch_quantity_flag": active_batch_quantity,
                "active_batch_action_required": active_batch_quantity and batch_status in {"EXPIRED_BATCH", "NEAR_EXPIRY_BATCH", "HEALTHY_BATCH"},
                "batch_trace_only_flag": not active_batch_quantity,
                "expiry_date": batch.get("expiry_date"),
                "batch_status": batch_status,
                "expired_flag": _bool(batch.get("expired_flag")),
                "near_expiry_flag": _bool(batch.get("near_expiry_flag")) and not _bool(batch.get("expired_flag")),
                "recommended_batch_zone": recommended_zone,
                "recommended_batch_location_id": location_id,
                "primary_sku_location_id": sku_row.get("primary_storage_location_id", "") if not sku_row.empty else "",
                "quarantine_location_id": sku_row.get("quarantine_location_id", "") if not sku_row.empty else "",
                "fefo_location_id": sku_row.get("fefo_location_id", "") if not sku_row.empty else "",
                "normal_storage_location_id": sku_row.get("primary_storage_location_id", "") if not sku_row.empty else "",
                "batch_slotting_action": _batch_slotting_action(batch_status, location_id, active_batch_quantity),
                "batch_slotting_reason": _batch_slotting_reason(batch_status, location_id, active_batch_quantity),
                "batch_slotting_warning_flags": ";".join(warnings),
                **visual,
                "assigned_temperature_controlled": _bool(location.get("temperature_controlled")),
                "assigned_security_controlled": _bool(location.get("security_controlled")),
                "assigned_forklift_accessible": _bool(location.get("forklift_accessible")),
                "assigned_perishable_allowed": _bool(location.get("perishable_item_allowed")),
                "assigned_fragile_allowed": _bool(location.get("fragile_item_allowed")),
                "assigned_heavy_allowed": _bool(location.get("heavy_item_allowed")),
                "zone_match_type": _batch_zone_match_type(recommended_zone, assigned_zone, location),
                "map_x": _float(location.get("x"), WAREHOUSE_SLOT_CONFIG["default_location_x"]),
                "map_y": _float(location.get("y"), WAREHOUSE_SLOT_CONFIG["default_location_y"]),
                "map_z": _float(location.get("z"), WAREHOUSE_SLOT_CONFIG["default_location_z"]),
                "map_zone": assigned_zone,
                "map_label": f"{batch.get('batch_id')} -> {location_id}" if location_id else str(batch.get("batch_id")),
                "map_color_group": batch_status,
            }
        )
    batch_slotting = pd.DataFrame(rows)
    batch_slotting = _ensure_columns(batch_slotting, _batch_slotting_columns())
    return batch_slotting[_batch_slotting_columns()]


def _batch_slot_status(batch: pd.Series) -> str:
    """Classify a batch for slotting."""
    if _bool(batch.get("expired_flag")):
        return "EXPIRED_BATCH"
    if _bool(batch.get("near_expiry_flag")):
        return "NEAR_EXPIRY_BATCH"
    if str(batch.get("batch_id", "")).strip():
        return "HEALTHY_BATCH"
    return "UNKNOWN_BATCH_STATUS"


def _recommended_batch_zone(batch_status: str, sku_row: pd.Series, active_batch_quantity: bool) -> str:
    """Return the preferred zone for one batch."""
    if not active_batch_quantity:
        return "TRACE_ONLY"
    if batch_status == "EXPIRED_BATCH":
        return WAREHOUSE_BATCH_ZONE_RULES["expired_batch_zone"]
    if batch_status == "NEAR_EXPIRY_BATCH":
        return WAREHOUSE_BATCH_ZONE_RULES["near_expiry_batch_zone"]
    if batch_status == "HEALTHY_BATCH" and not sku_row.empty:
        zone = str(sku_row.get("zone", "") or sku_row.get("recommended_storage_zone", "")).upper()
        return zone if zone and zone != "QUARANTINE" else WAREHOUSE_BATCH_ZONE_RULES["healthy_batch_zone_fallback"]
    return WAREHOUSE_BATCH_ZONE_RULES["healthy_batch_zone_fallback"]


def _recommended_batch_location_id(
    batch_status: str,
    sku_row: pd.Series,
    locations: pd.DataFrame,
    active_batch_quantity: bool,
    batch: pd.Series,
) -> str:
    """Return the assigned location id for one batch."""
    if not active_batch_quantity:
        return str(batch.get("location_id", "")).strip()
    if batch_status == "EXPIRED_BATCH":
        return str(sku_row.get("quarantine_location_id", "")).strip() or _best_location_id(locations, "QUARANTINE", sku_row)
    if batch_status == "NEAR_EXPIRY_BATCH":
        return str(sku_row.get("fefo_location_id", "")).strip() or _best_fefo_location_id(locations, sku_row)
    if batch_status == "HEALTHY_BATCH":
        return str(sku_row.get("primary_storage_location_id", "")).strip() or str(sku_row.get("recommended_location_id", "")).strip()
    return str(sku_row.get("primary_storage_location_id", "")).strip() or str(sku_row.get("recommended_location_id", "")).strip()


def _best_location_id(locations: pd.DataFrame, preferred_zone: str, sku_row: pd.Series | None = None) -> str:
    """Return best location id for a preferred zone and SKU capability needs."""
    if locations.empty:
        return ""
    preferred_zone = str(preferred_zone).upper()
    candidates = locations[locations["zone"].astype(str).str.upper() == preferred_zone]
    if candidates.empty and preferred_zone == "FAST_PICK":
        candidates = locations[locations["zone"].astype(str).str.upper().isin(["FAST_PICK", "CASE_PICKING", "EACH_PICKING"])]
    if candidates.empty:
        candidates = locations
    candidates = _filter_location_capabilities(candidates, sku_row)
    if candidates.empty:
        return ""
    ranked = candidates.copy()
    ranked["_distance"] = ranked.apply(
        lambda location: min(
            _positive_float(location.get("distance_to_dock"), WAREHOUSE_TRAVEL_THRESHOLDS["high_distance_m"]),
            _positive_float(location.get("distance_to_exit"), WAREHOUSE_TRAVEL_THRESHOLDS["high_distance_m"]),
            _positive_float(location.get("distance_to_entrance"), WAREHOUSE_TRAVEL_THRESHOLDS["high_distance_m"]),
        ),
        axis=1,
    )
    ranked["_z"] = ranked["z"].apply(_float)
    ranked = ranked.sort_values(by=["_distance", "_z", "location_id"], ascending=[True, True, True])
    return str(ranked.iloc[0].get("location_id", "")).strip()


def _best_fefo_location_id(locations: pd.DataFrame, sku_row: pd.Series) -> str:
    """Return a FEFO-friendly pick location id."""
    if locations.empty:
        return ""
    pick_zones = ["FAST_PICK", "CASE_PICKING", "EACH_PICKING", "RECEIVING"]
    candidates = locations[locations["zone"].astype(str).str.upper().isin(pick_zones)]
    candidates = _filter_location_capabilities(candidates, sku_row)
    if candidates.empty:
        return _best_location_id(locations, WAREHOUSE_BATCH_ZONE_RULES["near_expiry_batch_zone"], sku_row)
    ranked = candidates.copy()
    ranked["_distance"] = ranked.apply(
        lambda location: min(
            _positive_float(location.get("distance_to_exit"), WAREHOUSE_TRAVEL_THRESHOLDS["high_distance_m"]),
            _positive_float(location.get("distance_to_dock"), WAREHOUSE_TRAVEL_THRESHOLDS["high_distance_m"]),
        ),
        axis=1,
    )
    ranked["_zone_rank"] = ranked["zone"].astype(str).str.upper().map({"FAST_PICK": 0, "CASE_PICKING": 1, "EACH_PICKING": 1, "RECEIVING": 2}).fillna(3)
    ranked = ranked.sort_values(by=["_zone_rank", "_distance", "location_id"], ascending=[True, True, True])
    return str(ranked.iloc[0].get("location_id", "")).strip()


def _best_normal_location_id(locations: pd.DataFrame, sku_row: pd.Series) -> str:
    """Return a normal sellable storage location when quarantine should not hold the whole SKU."""
    preferred_zone = str(sku_row.get("recommended_storage_zone", "")).upper()
    if preferred_zone and preferred_zone != "QUARANTINE":
        return _best_location_id(locations, preferred_zone, sku_row)
    for zone in ["SLOW_PICK", "BULK_STORAGE", "PALLET_STORAGE", "CASE_PICKING", "EACH_PICKING"]:
        location_id = _best_location_id(locations, zone, sku_row)
        if location_id:
            return location_id
    return ""


def _filter_location_capabilities(candidates: pd.DataFrame, sku_row: pd.Series | None) -> pd.DataFrame:
    """Filter candidate locations by mandatory SKU capabilities."""
    if sku_row is None or sku_row.empty or candidates.empty:
        return candidates
    filtered = candidates.copy()
    if _bool(sku_row.get("temperature_control_required")):
        filtered = filtered[filtered["temperature_controlled"].apply(_bool)]
    if _bool(sku_row.get("security_control_required")):
        filtered = filtered[filtered["security_controlled"].apply(_bool)]
    if _bool(sku_row.get("forklift_required")):
        filtered = filtered[filtered["forklift_accessible"].apply(_bool)]
    if _bool(sku_row.get("fragile")):
        filtered = filtered[filtered["fragile_item_allowed"].apply(_bool)]
    if _bool(sku_row.get("perishable")) or _bool(sku_row.get("fefo_required")):
        filtered = filtered[filtered["perishable_item_allowed"].apply(_bool)]
    if _is_heavy_sku(sku_row):
        filtered = filtered[filtered["heavy_item_allowed"].apply(_bool)]
    return filtered


def _positive_float(value, default: float) -> float:
    """Return a positive float or fallback."""
    numeric = _float(value, default)
    return numeric if numeric > 0 else default


def _batch_quantity(batch: pd.Series) -> float:
    """Return quantity stored for one batch."""
    if "quantity_on_hand" in batch.index:
        return max(_float(batch.get("quantity_on_hand")), 0.0)
    if "quantity_available" in batch.index:
        return max(_float(batch.get("quantity_available")), 0.0)
    if "batch_quantity" in batch.index:
        return max(_float(batch.get("batch_quantity")), 0.0)
    return 0.0


def _active_batch_quantity(quantity: float) -> bool:
    """Return True when batch quantity is operationally active."""
    return _float(quantity) > WAREHOUSE_BATCH_QUANTITY_RULES["active_batch_quantity_min"]


def _batch_warning_flags(batch_status: str, location_id: str, active_batch_quantity: bool) -> list[str]:
    """Return batch slotting warning flags."""
    warnings = []
    if batch_status == "EXPIRED_BATCH" and active_batch_quantity:
        warnings.append("ACTIVE_EXPIRED_BATCH_ASSIGNED_TO_QUARANTINE")
    elif batch_status == "EXPIRED_BATCH":
        warnings.append("ZERO_QUANTITY_EXPIRED_BATCH_TRACE_ONLY")
    elif batch_status == "NEAR_EXPIRY_BATCH" and active_batch_quantity:
        warnings.append("ACTIVE_NEAR_EXPIRY_BATCH_ASSIGNED_TO_FEFO")
    elif batch_status == "NEAR_EXPIRY_BATCH":
        warnings.append("ZERO_QUANTITY_NEAR_EXPIRY_BATCH_TRACE_ONLY")
    elif batch_status == "HEALTHY_BATCH" and active_batch_quantity:
        warnings.append("ACTIVE_HEALTHY_BATCH_ASSIGNED_TO_NORMAL_STORAGE")
    elif batch_status == "HEALTHY_BATCH":
        warnings.append("NO_ACTIVE_BATCH_QUANTITY")
    else:
        warnings.append("UNKNOWN_BATCH_STATUS")
    if active_batch_quantity and not location_id:
        warnings.append("NO_FEASIBLE_LOCATION_FOUND")
    return _unique(warnings)


def _batch_slotting_action(batch_status: str, location_id: str, active_batch_quantity: bool) -> str:
    """Return batch-level slotting action."""
    if not active_batch_quantity:
        return "NO_ACTIVE_BATCH_QUANTITY"
    if not location_id:
        return "REVIEW_MANUALLY"
    if batch_status == "EXPIRED_BATCH":
        return "QUARANTINE_EXPIRED_BATCH"
    if batch_status == "NEAR_EXPIRY_BATCH":
        return "PRIORITIZE_NEAR_EXPIRY_FEFO"
    return "KEEP_CURRENT_LOCATION"


def _batch_slotting_reason(batch_status: str, location_id: str, active_batch_quantity: bool) -> str:
    """Return batch-level slotting reason."""
    if not active_batch_quantity:
        return "Batch has zero active quantity; retained in batch slotting for traceability only."
    if not location_id:
        return "No feasible batch location found; review batch placement manually."
    if batch_status == "EXPIRED_BATCH":
        return "Expired batch is assigned to quarantine without quarantining the entire SKU."
    if batch_status == "NEAR_EXPIRY_BATCH":
        return "Near-expiry batch is assigned to FEFO-accessible picking so it can be used before healthy stock."
    if batch_status == "HEALTHY_BATCH":
        return "Healthy batch follows the SKU primary normal storage location."
    return "Unknown batch status follows the SKU primary location and should be reviewed."


def _batch_zone_match_type(recommended_zone: str, assigned_zone: str, location: pd.Series) -> str:
    """Return batch zone match type."""
    if not assigned_zone:
        return "NO_FEASIBLE_LOCATION"
    if str(recommended_zone).upper() == assigned_zone:
        return "EXACT_ZONE_MATCH"
    if _bool(location.get("temperature_controlled")) or _bool(location.get("security_controlled")):
        return "CAPABILITY_MATCH"
    compatible = {
        "FAST_PICK": {"CASE_PICKING", "EACH_PICKING", "RECEIVING"},
        "SLOW_PICK": {"BULK_STORAGE", "PALLET_STORAGE"},
        "QUARANTINE": {"RETURNS"},
    }
    if assigned_zone in compatible.get(str(recommended_zone).upper(), set()):
        return "COMPATIBLE_ZONE_MATCH"
    return "FALLBACK_ZONE"


def _batch_visual_fields(batch_status: str, batch_quantity: float, active_batch_quantity: bool, warnings: list[str]) -> dict:
    """Return Step 10 visual controls for one batch row."""
    if not active_batch_quantity:
        return {
            "include_in_physical_map": False,
            "include_in_traceability_layer": True,
            "visual_quantity": 0.0,
            "visual_layer": "TRACE_ONLY_BATCH",
            "visual_status_group": "TRACE_ONLY_BATCH",
            "visual_warning_flags": "TRACE_ONLY_BATCH_EXCLUDED_FROM_PHYSICAL_MAP",
            "visual_info_flags": "TRACE_ONLY_BATCH_RETAINED_FOR_HISTORY;BATCH_VISUAL_EXCLUDED_ZERO_QUANTITY",
        }
    if batch_status == "EXPIRED_BATCH":
        layer = "QUARANTINE_EXPIRED"
    elif batch_status == "NEAR_EXPIRY_BATCH":
        layer = "FEFO_NEAR_EXPIRY"
    else:
        layer = "PRIMARY_STORAGE"
    return {
        "include_in_physical_map": True,
        "include_in_traceability_layer": True,
        "visual_quantity": _round(batch_quantity),
        "visual_layer": layer,
        "visual_status_group": layer,
        "visual_warning_flags": ";".join(code for code in warnings if code in {"NO_FEASIBLE_LOCATION_FOUND"}),
        "visual_info_flags": "",
    }


def _add_trace_only_batches_to_location_utilization(location_utilization: pd.DataFrame, batch_slotting: pd.DataFrame) -> pd.DataFrame:
    """Attach trace-only and active batch role counts to location utilization."""
    if location_utilization.empty or batch_slotting.empty:
        return location_utilization
    updated = location_utilization.copy()
    for column in ["assigned_trace_only_batches", "assigned_trace_only_batch_count", "assigned_quarantine_batch_count", "assigned_fefo_batch_count"]:
        if column not in updated.columns:
            updated[column] = "" if column == "assigned_trace_only_batches" else 0
    for idx, row in updated.iterrows():
        location_id = str(row.get("location_id", "")).strip()
        location_batches = batch_slotting[batch_slotting["recommended_batch_location_id"].fillna("").astype(str).str.strip() == location_id]
        trace_batches = location_batches[location_batches["batch_trace_only_flag"].apply(_bool)]
        quarantine_batches = location_batches[
            location_batches["active_batch_quantity_flag"].apply(_bool)
            & (location_batches["batch_status"].astype(str) == "EXPIRED_BATCH")
        ]
        fefo_batches = location_batches[
            location_batches["active_batch_quantity_flag"].apply(_bool)
            & (location_batches["batch_status"].astype(str) == "NEAR_EXPIRY_BATCH")
        ]
        updated.at[idx, "assigned_trace_only_batches"] = ";".join(trace_batches["batch_id"].dropna().astype(str))
        updated.at[idx, "assigned_trace_only_batch_count"] = int(len(trace_batches))
        updated.at[idx, "assigned_quarantine_batch_count"] = int(len(quarantine_batches))
        updated.at[idx, "assigned_fefo_batch_count"] = int(len(fefo_batches))
        role_info_flags = _split_flags(updated.at[idx, "location_role_info_flags"])
        if len(trace_batches) > 0:
            info = _unique(role_info_flags + ["TRACE_ONLY_BATCH_RETAINED_FOR_HISTORY"])
            updated.at[idx, "location_role_info_flags"] = ";".join(info)
    return updated[_location_utilization_columns()]


def _add_replenishment_pressure_fields(warehouse_slotting: pd.DataFrame, location_utilization: pd.DataFrame) -> pd.DataFrame:
    """Add SKU-level staging capacity fields using final location utilization."""
    if warehouse_slotting.empty:
        return warehouse_slotting
    location_lookup = {
        str(row.get("location_id", "")).strip(): row
        for _, row in location_utilization.iterrows()
    }
    rows = []
    receiving_zones = {str(zone).upper() for zone in WAREHOUSE_STAGING_RULES["receiving_zones"]}
    for _, row in warehouse_slotting.iterrows():
        updated = row.to_dict()
        location_id = str(updated.get("replenishment_receiving_location_id", "")).strip()
        location = location_lookup.get(location_id, pd.Series(dtype=object))
        projected_util = _float(location.get("projected_utilization_pct"))
        projected_weight_util = _float(location.get("projected_weight_utilization_pct"))
        projected_over = _bool(location.get("projected_over_capacity_flag"))
        projected_pressure = _bool(location.get("projected_capacity_pressure_flag"))
        replenishment_quantity = _float(updated.get("replenishment_storage_units"))
        warning_flags = _split_flags(updated.get("slotting_warning_flags", ""))
        info_flags = _split_flags(updated.get("slotting_info_flags", ""))
        if location_id and replenishment_quantity > 0:
            if location_id != str(updated.get("primary_storage_location_id", "")).strip():
                info_flags.append("PRIMARY_REPLENISHMENT_LOCATION_ROLE_SPLIT")
            if str(location.get("zone", "")).upper() in receiving_zones:
                info_flags.append("REPLENISHMENT_STAGED_IN_RECEIVING")
            if projected_over and WAREHOUSE_STAGING_RULES["flag_sku_if_replenishment_location_over_capacity"]:
                warning_flags.extend([
                    "REPLENISHMENT_STAGING_OVER_CAPACITY",
                    "SKU_CAUSES_PROJECTED_STAGING_PRESSURE",
                ])
                if str(location.get("zone", "")).upper() in receiving_zones:
                    warning_flags.append("RECEIVING_CAPACITY_REVIEW_REQUIRED")
            elif projected_pressure:
                warning_flags.extend(["PROJECTED_CAPACITY_PRESSURE", "SKU_CAUSES_PROJECTED_STAGING_PRESSURE"])
            info_flags.append("CURRENT_VS_PROJECTED_CAPACITY_SPLIT")
        sku_pressure = (
            replenishment_quantity > 0
            and location_id
            and (projected_over or projected_pressure)
        )
        if location_id and replenishment_quantity > 0 and projected_over:
            reason = (
                f"Recommended replenishment quantity is staged through {location_id}, whose projected utilization exceeds capacity. "
                "Review receiving/staging capacity before ordering."
            )
        elif location_id and replenishment_quantity > 0 and projected_pressure:
            reason = (
                f"Recommended replenishment quantity is staged through {location_id}, whose projected utilization is under pressure. "
                "Review staging capacity before ordering."
            )
        elif location_id and replenishment_quantity > 0:
            reason = f"Recommended replenishment quantity can be staged through {location_id} within current configured capacity."
        else:
            reason = "No replenishment staging quantity is assigned for this SKU."
        updated.update(
            {
                "replenishment_location_projected_utilization_pct": _round(projected_util),
                "replenishment_location_projected_weight_utilization_pct": _round(projected_weight_util),
                "replenishment_location_projected_over_capacity_flag": projected_over,
                "replenishment_location_projected_capacity_pressure_flag": projected_pressure,
                "sku_replenishment_volume_m3": _round(updated.get("replenishment_storage_volume_m3")),
                "sku_replenishment_weight_kg": _round(updated.get("replenishment_storage_weight_kg")),
                "sku_causes_projected_staging_pressure": sku_pressure,
                "sku_replenishment_staging_warning": ";".join(
                    code for code in _unique(warning_flags)
                    if code in {"REPLENISHMENT_STAGING_OVER_CAPACITY", "RECEIVING_CAPACITY_REVIEW_REQUIRED", "SKU_CAUSES_PROJECTED_STAGING_PRESSURE", "PROJECTED_CAPACITY_PRESSURE"}
                ),
                "sku_replenishment_staging_reason": reason,
                "slotting_warning_flags": ";".join(_unique(warning_flags)),
                "slotting_info_flags": ";".join(_unique(info_flags)),
            }
        )
        rows.append(updated)
    return pd.DataFrame(rows)


def _add_warehouse_visual_fields(warehouse_slotting: pd.DataFrame) -> pd.DataFrame:
    """Add Step 10 visual-ready fields to SKU-level slotting rows."""
    if warehouse_slotting.empty:
        return warehouse_slotting
    rows = []
    for _, row in warehouse_slotting.iterrows():
        updated = row.to_dict()
        warning_flags = _split_flags(updated.get("slotting_warning_flags", ""))
        info_flags = _split_flags(updated.get("slotting_info_flags", ""))
        visual_warning_flags = [
            code for code in warning_flags
            if code in {
                "REPLENISHMENT_STAGING_OVER_CAPACITY",
                "RECEIVING_CAPACITY_REVIEW_REQUIRED",
                "CURRENT_LOCATION_OVER_CAPACITY",
                "PROJECTED_LOCATION_OVER_CAPACITY",
                "NO_FEASIBLE_LOCATION_FOUND",
            }
        ]
        visual_info_flags = [
            code for code in info_flags
            if code in {
                "CAPABILITY_MATCH_NON_EXACT_ZONE",
                "REPLENISHMENT_STAGED_IN_RECEIVING",
                "CURRENT_VS_PROJECTED_CAPACITY_SPLIT",
            }
        ]
        updated.update(
            {
                "primary_visual_location_id": updated.get("primary_storage_location_id", ""),
                "replenishment_visual_location_id": updated.get("replenishment_receiving_location_id", ""),
                "quarantine_visual_location_id": updated.get("quarantine_location_id", ""),
                "fefo_visual_location_id": updated.get("fefo_location_id", ""),
                "primary_visual_quantity": _round(updated.get("primary_storage_units")),
                "replenishment_visual_quantity": _round(updated.get("replenishment_storage_units")),
                "quarantine_visual_quantity": _round(updated.get("quarantine_storage_units")),
                "fefo_visual_quantity": _round(updated.get("fefo_storage_units")),
                "primary_visual_volume_m3": _round(updated.get("primary_storage_volume_m3")),
                "replenishment_visual_volume_m3": _round(updated.get("replenishment_storage_volume_m3")),
                "quarantine_visual_volume_m3": _round(updated.get("quarantine_storage_volume_m3")),
                "fefo_visual_volume_m3": _round(updated.get("fefo_storage_volume_m3")),
                "visual_status_group": _warehouse_visual_status_group(updated, warning_flags),
                "visual_warning_flags": ";".join(_unique(visual_warning_flags)),
                "visual_info_flags": ";".join(_unique(visual_info_flags)),
            }
        )
        rows.append(updated)
    return pd.DataFrame(rows)


def _warehouse_visual_status_group(row: dict, warning_flags: list[str]) -> str:
    """Return Step 10 visual group for one SKU-level slotting row."""
    if row.get("location_assignment_status") == "NO_FEASIBLE_LOCATION":
        return "NO_FEASIBLE_LOCATION"
    if row.get("main_inventory_status") == "STOCKOUT":
        return "STOCKOUT"
    if row.get("main_inventory_status") in {"REORDER_NOW", "CRITICAL_LOW_STOCK", "ZERO_STOCK"}:
        return "REORDER_NOW"
    if "PROJECTED_LOCATION_OVER_CAPACITY" in warning_flags or _bool(row.get("replenishment_location_projected_over_capacity_flag")):
        return "PROJECTED_OVER_CAPACITY"
    if "CURRENT_LOCATION_OVER_CAPACITY" in warning_flags:
        return "OVER_CAPACITY"
    if row.get("main_inventory_status") == "OVERSTOCK":
        return "OVERSTOCK"
    if _float(row.get("fefo_storage_units")) > 0:
        return "FEFO_NEAR_EXPIRY"
    if _float(row.get("quarantine_storage_units")) > 0:
        return "QUARANTINE_EXPIRED"
    if row.get("movement_class") == "FAST_MOVING":
        return "FAST_MOVING"
    return "NORMAL"


def _build_location_utilization(locations: pd.DataFrame, location_state: dict) -> pd.DataFrame:
    """Build one utilization row per storage location."""
    rows = []
    for _, location in locations.iterrows():
        location_id = str(location.get("location_id", "")).strip()
        state = location_state.get(location_id, {})
        capacity_m3 = _float(location.get("capacity_m3"), WAREHOUSE_SLOT_CONFIG["default_location_capacity_m3"])
        capacity_kg = _float(location.get("capacity_kg"), WAREHOUSE_SLOT_CONFIG["default_location_capacity_kg"])
        current_used_volume = _float(state.get("current_used_volume_m3"))
        projected_used_volume = _float(state.get("projected_used_volume_m3"))
        current_used_weight = _float(state.get("current_used_weight_kg"))
        projected_used_weight = _float(state.get("projected_used_weight_kg"))
        assigned_primary_volume = _float(state.get("assigned_primary_volume_m3"))
        assigned_quarantine_volume = _float(state.get("assigned_quarantine_volume_m3"))
        assigned_fefo_volume = _float(state.get("assigned_fefo_volume_m3"))
        assigned_replenishment_volume = _float(state.get("assigned_replenishment_volume_m3"))
        assigned_primary_weight = _float(state.get("assigned_primary_weight_kg"))
        assigned_quarantine_weight = _float(state.get("assigned_quarantine_weight_kg"))
        assigned_fefo_weight = _float(state.get("assigned_fefo_weight_kg"))
        assigned_replenishment_weight = _float(state.get("assigned_replenishment_weight_kg"))
        base_used_volume_original = _float(state.get("base_used_volume_m3_original"))
        base_used_weight_original = _float(state.get("base_used_weight_kg_original"))
        known_current_volume = _float(state.get("known_current_sku_volume_rebased"))
        known_current_weight = _float(state.get("known_current_sku_weight_rebased"))
        background_volume = _float(state.get("background_used_volume_m3"))
        background_weight = _float(state.get("background_used_weight_kg"))
        rebased_applied = _bool(state.get("rebased_utilization_applied"))
        current_util = _pct(current_used_volume, capacity_m3)
        projected_util = _pct(projected_used_volume, capacity_m3)
        current_weight_util = _pct(current_used_weight, capacity_kg)
        projected_weight_util = _pct(projected_used_weight, capacity_kg)
        warnings = _location_warning_flags(current_util, projected_util, current_weight_util, projected_weight_util)
        if rebased_applied:
            warnings.append("CURRENT_LOCATION_UTILIZATION_REBASED")
        if _bool(state.get("batch_level_location_utilization_applied")):
            warnings.append("BATCH_LEVEL_LOCATION_UTILIZATION_APPLIED")
        else:
            warnings.append("BATCH_LEVEL_LOCATION_UTILIZATION_NOT_APPLIED")
        current_over_capacity = current_util > 100 or current_weight_util > 100
        projected_over_capacity = projected_util > 100 or projected_weight_util > 100
        current_capacity_pressure = (
            not current_over_capacity
            and (
                current_util > WAREHOUSE_UTILIZATION_THRESHOLDS["target_location_utilization_max_pct"]
                or current_weight_util > WAREHOUSE_UTILIZATION_THRESHOLDS["target_location_utilization_max_pct"]
            )
        )
        projected_capacity_pressure = (
            not projected_over_capacity
            and (
                projected_util > WAREHOUSE_UTILIZATION_THRESHOLDS["target_location_utilization_max_pct"]
                or projected_weight_util > WAREHOUSE_UTILIZATION_THRESHOLDS["target_location_utilization_max_pct"]
            )
        )
        current_status = _capacity_status(current_util, current_weight_util)
        projected_status = _capacity_status(projected_util, projected_weight_util)
        status = _worse_capacity_status(current_status, projected_status)
        assigned_skus = state.get("assigned_skus", [])
        role_summary, role_warnings, role_info = _location_role_flags(state)
        warnings.extend(role_warnings)
        rows.append(
            {
                "location_id": location_id,
                "zone": location.get("zone", ""),
                "aisle": location.get("aisle", ""),
                "rack": location.get("rack", ""),
                "shelf": location.get("shelf", ""),
                "bin": location.get("bin", ""),
                "x": _float(location.get("x")),
                "y": _float(location.get("y")),
                "z": _float(location.get("z")),
                "capacity_m3": _round(capacity_m3),
                "capacity_kg": _round(capacity_kg),
                "assigned_sku_count": len(assigned_skus),
                "assigned_skus": ";".join(assigned_skus),
                "assigned_primary_skus": ";".join(state.get("assigned_primary_skus", [])),
                "assigned_replenishment_skus": ";".join(state.get("assigned_replenishment_skus", [])),
                "assigned_quarantine_skus": ";".join(state.get("assigned_quarantine_skus", [])),
                "assigned_fefo_skus": ";".join(state.get("assigned_fefo_skus", [])),
                "assigned_trace_only_batches": ";".join(state.get("assigned_trace_only_batches", [])),
                "assigned_primary_sku_count": len(state.get("assigned_primary_skus", [])),
                "assigned_replenishment_sku_count": len(state.get("assigned_replenishment_skus", [])),
                "assigned_quarantine_batch_count": 0,
                "assigned_fefo_batch_count": 0,
                "assigned_trace_only_batch_count": len(state.get("assigned_trace_only_batches", [])),
                "location_role_summary": role_summary,
                "location_role_warning_flags": ";".join(role_warnings),
                "location_role_info_flags": ";".join(role_info),
                "base_used_volume_m3_original": _round(base_used_volume_original),
                "base_used_weight_kg_original": _round(base_used_weight_original),
                "known_current_sku_volume_rebased": _round(known_current_volume),
                "known_current_sku_weight_rebased": _round(known_current_weight),
                "background_used_volume_m3": _round(background_volume),
                "background_used_weight_kg": _round(background_weight),
                "assigned_primary_volume_m3": _round(assigned_primary_volume),
                "assigned_quarantine_volume_m3": _round(assigned_quarantine_volume),
                "assigned_fefo_volume_m3": _round(assigned_fefo_volume),
                "assigned_replenishment_volume_m3": _round(assigned_replenishment_volume),
                "assigned_primary_weight_kg": _round(assigned_primary_weight),
                "assigned_quarantine_weight_kg": _round(assigned_quarantine_weight),
                "assigned_fefo_weight_kg": _round(assigned_fefo_weight),
                "assigned_replenishment_weight_kg": _round(assigned_replenishment_weight),
                "current_used_volume_m3": _round(current_used_volume),
                "projected_used_volume_m3": _round(projected_used_volume),
                "current_utilization_pct": _round(current_util),
                "projected_utilization_pct": _round(projected_util),
                "current_used_weight_kg": _round(current_used_weight),
                "projected_used_weight_kg": _round(projected_used_weight),
                "current_weight_utilization_pct": _round(current_weight_util),
                "projected_weight_utilization_pct": _round(projected_weight_util),
                "remaining_volume_m3": _round(capacity_m3 - current_used_volume),
                "projected_remaining_volume_m3": _round(capacity_m3 - projected_used_volume),
                "remaining_weight_kg": _round(capacity_kg - current_used_weight),
                "projected_remaining_weight_kg": _round(capacity_kg - projected_used_weight),
                "rebased_utilization_applied": rebased_applied,
                "batch_level_location_utilization_applied": _bool(state.get("batch_level_location_utilization_applied")),
                "current_over_capacity_flag": current_over_capacity,
                "projected_over_capacity_flag": projected_over_capacity,
                "current_capacity_pressure_flag": current_capacity_pressure,
                "projected_capacity_pressure_flag": projected_capacity_pressure,
                "current_capacity_status": current_status,
                "projected_capacity_status": projected_status,
                "location_status": status,
                "location_warning_flags": ";".join(_unique(warnings)),
                "map_x": _float(location.get("x")),
                "map_y": _float(location.get("y")),
                "map_z": _float(location.get("z")),
                "map_zone": location.get("zone", ""),
                "map_label": location_id,
                "map_color_group": status,
            }
        )
    utilization = pd.DataFrame(rows)
    return utilization[_location_utilization_columns()]


def _location_warning_flags(current_util: float, projected_util: float, current_weight_util: float, projected_weight_util: float) -> list[str]:
    """Return location capacity warnings."""
    warnings = []
    if current_util > 100 or current_weight_util > 100:
        warnings.extend(["LOCATION_OVER_CAPACITY", "CURRENT_LOCATION_OVER_CAPACITY"])
    if projected_util > 100 or projected_weight_util > 100:
        warnings.extend(["INSUFFICIENT_SPACE_AFTER_ORDER", "PROJECTED_LOCATION_OVER_CAPACITY"])
    elif projected_util > WAREHOUSE_UTILIZATION_THRESHOLDS["target_location_utilization_max_pct"]:
        warnings.append("PROJECTED_CAPACITY_PRESSURE")
    if projected_util < WAREHOUSE_UTILIZATION_THRESHOLDS["target_location_utilization_min_pct"]:
        warnings.append("LOW_LOCATION_UTILIZATION")
    return warnings


def _location_role_flags(state: dict) -> tuple[str, list[str], list[str]]:
    """Return role summary plus role warning/info flags for one location."""
    roles = []
    if state.get("assigned_primary_skus"):
        roles.append("PRIMARY")
    if state.get("assigned_replenishment_skus"):
        roles.append("REPLENISHMENT")
    if state.get("assigned_quarantine_skus"):
        roles.append("QUARANTINE")
    if state.get("assigned_fefo_skus"):
        roles.append("FEFO")
    if not roles:
        return "EMPTY", [], []

    warnings = []
    info = []
    if roles == ["PRIMARY"]:
        summary = "PRIMARY_ONLY"
    elif roles == ["REPLENISHMENT"]:
        summary = "REPLENISHMENT_STAGING_ONLY"
    elif roles == ["QUARANTINE"]:
        summary = "QUARANTINE_ONLY"
    elif roles == ["FEFO"]:
        summary = "FEFO_ONLY"
    elif set(roles) == {"PRIMARY", "REPLENISHMENT"}:
        summary = "PRIMARY_AND_REPLENISHMENT"
        info.append("LOCATION_HAS_PRIMARY_AND_STAGING_ROLES")
    else:
        summary = "MIXED_" + "_".join(roles)
        if "QUARANTINE" in roles or "FEFO" in roles:
            info.append("LOCATION_HAS_QUARANTINE_OR_FEFO_ROLE")
        if len(roles) > 1:
            warnings.append("LOCATION_ROLE_MIXED_USAGE_REVIEW")
    return summary, warnings, info


def _capacity_status(utilization_pct: float, weight_utilization_pct: float) -> str:
    """Return capacity status for current or projected utilization."""
    if utilization_pct <= 0 and weight_utilization_pct <= 0:
        return "EMPTY"
    if utilization_pct > 100 or weight_utilization_pct > 100:
        return "OVER_CAPACITY"
    if (
        utilization_pct > WAREHOUSE_UTILIZATION_THRESHOLDS["target_location_utilization_max_pct"]
        or weight_utilization_pct > WAREHOUSE_UTILIZATION_THRESHOLDS["target_location_utilization_max_pct"]
    ):
        return "CAPACITY_PRESSURE"
    if utilization_pct < WAREHOUSE_UTILIZATION_THRESHOLDS["target_location_utilization_min_pct"]:
        return "UNDERUTILIZED"
    return "HEALTHY"


def _worse_capacity_status(current_status: str, projected_status: str) -> str:
    """Return worse of current/projected capacity statuses."""
    rank = {
        "OVER_CAPACITY": 5,
        "CAPACITY_PRESSURE": 4,
        "HEALTHY": 3,
        "UNDERUTILIZED": 2,
        "EMPTY": 1,
    }
    return projected_status if rank.get(projected_status, 0) >= rank.get(current_status, 0) else current_status


def _location_status(projected_util: float, projected_weight_util: float) -> str:
    """Return location status."""
    if projected_util <= 0 and projected_weight_util <= 0:
        return "EMPTY"
    if projected_util > 100 or projected_weight_util > 100:
        return "OVER_CAPACITY"
    if projected_util > WAREHOUSE_UTILIZATION_THRESHOLDS["target_location_utilization_max_pct"]:
        return "CAPACITY_PRESSURE"
    if projected_util < WAREHOUSE_UTILIZATION_THRESHOLDS["target_location_utilization_min_pct"]:
        return "UNDERUTILIZED"
    return "HEALTHY"


def _build_space_utilization(location_utilization: pd.DataFrame, batch_slotting: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build warehouse-level and zone-level utilization summary."""
    rows = []
    rows.append(_space_summary_row(location_utilization, "ALL_WAREHOUSE", "ALL_WAREHOUSE", batch_slotting))
    for zone, group in location_utilization.groupby("zone", dropna=False):
        zone_batches = _batch_group_for_space(batch_slotting, str(zone), "zone")
        rows.append(_space_summary_row(group, "BY_ZONE", str(zone), zone_batches))
    if "projected_location_status" in location_utilization.columns:
        for status, group in location_utilization.groupby("projected_location_status", dropna=False):
            rows.append(_space_summary_row(group, "BY_PROJECTED_LOCATION_STATUS", str(status), batch_slotting))
    return pd.DataFrame(rows)


def _space_summary_row(df: pd.DataFrame, summary_type: str, group_name: str, batch_slotting: pd.DataFrame | None = None) -> dict:
    """Return one space utilization summary row."""
    total_capacity_m3 = df["capacity_m3"].sum()
    total_current_used_volume = df["current_used_volume_m3"].sum()
    total_projected_used_volume = df["projected_used_volume_m3"].sum()
    base_used_volume_original = df["base_used_volume_m3_original"].sum() if "base_used_volume_m3_original" in df.columns else 0.0
    known_sku_volume_rebased = df["known_current_sku_volume_rebased"].sum() if "known_current_sku_volume_rebased" in df.columns else 0.0
    background_used_volume = df["background_used_volume_m3"].sum() if "background_used_volume_m3" in df.columns else 0.0
    rebased_count = int(df["rebased_utilization_applied"].astype(bool).sum()) if "rebased_utilization_applied" in df.columns else 0
    batch_level_count = int(df["batch_level_location_utilization_applied"].astype(bool).sum()) if "batch_level_location_utilization_applied" in df.columns else 0
    active_primary_volume = df["assigned_primary_volume_m3"].sum() if "assigned_primary_volume_m3" in df.columns else 0.0
    active_quarantine_volume = df["assigned_quarantine_volume_m3"].sum() if "assigned_quarantine_volume_m3" in df.columns else 0.0
    active_fefo_volume = df["assigned_fefo_volume_m3"].sum() if "assigned_fefo_volume_m3" in df.columns else 0.0
    active_replenishment_volume = df["assigned_replenishment_volume_m3"].sum() if "assigned_replenishment_volume_m3" in df.columns else 0.0
    current_over_capacity_count = int(df["current_over_capacity_flag"].astype(bool).sum()) if "current_over_capacity_flag" in df.columns else 0
    projected_over_capacity_count = int(df["projected_over_capacity_flag"].astype(bool).sum()) if "projected_over_capacity_flag" in df.columns else 0
    current_pressure_count = int(df["current_capacity_pressure_flag"].astype(bool).sum()) if "current_capacity_pressure_flag" in df.columns else 0
    projected_pressure_count = int(df["projected_capacity_pressure_flag"].astype(bool).sum()) if "projected_capacity_pressure_flag" in df.columns else 0
    trace_only_batch_count = _batch_count(batch_slotting, "batch_trace_only_flag", True)
    physical_map_batch_count = _batch_count(batch_slotting, "include_in_physical_map", True)
    traceability_batch_count = _batch_count(batch_slotting, "include_in_traceability_layer", True)
    total_capacity_kg = df["capacity_kg"].sum()
    total_current_used_weight = df["current_used_weight_kg"].sum()
    total_projected_used_weight = df["projected_used_weight_kg"].sum()
    if summary_type == "ALL_WAREHOUSE":
        current_cost = sum(_space_cost(row, "current_used_volume_m3") for _, row in df.iterrows())
        projected_cost = sum(_space_cost(row, "projected_used_volume_m3") for _, row in df.iterrows())
    else:
        zone = group_name if summary_type == "BY_ZONE" else "DEFAULT"
        multiplier = WAREHOUSE_ZONE_COST_MULTIPLIERS.get(zone, WAREHOUSE_ZONE_COST_MULTIPLIERS["DEFAULT"])
        current_cost = total_current_used_volume * WAREHOUSE_SLOT_CONFIG["default_storage_cost_per_m3"] * multiplier
        projected_cost = total_projected_used_volume * WAREHOUSE_SLOT_CONFIG["default_storage_cost_per_m3"] * multiplier
    current_util = _pct(total_current_used_volume, total_capacity_m3)
    projected_util = _pct(total_projected_used_volume, total_capacity_m3)
    warning = _space_warning(projected_util)
    return {
        "summary_type": summary_type,
        "group_name": group_name,
        "location_count": int(len(df)),
        "total_capacity_m3": _round(total_capacity_m3),
        "base_used_volume_m3_original": _round(base_used_volume_original),
        "known_sku_volume_rebased": _round(known_sku_volume_rebased),
        "background_used_volume_m3": _round(background_used_volume),
        "rebased_utilization_applied_count": rebased_count,
        "batch_level_location_utilization_applied_count": batch_level_count,
        "active_primary_volume_m3": _round(active_primary_volume),
        "active_quarantine_volume_m3": _round(active_quarantine_volume),
        "active_fefo_volume_m3": _round(active_fefo_volume),
        "active_replenishment_volume_m3": _round(active_replenishment_volume),
        "primary_volume_m3": _round(active_primary_volume),
        "replenishment_volume_m3": _round(active_replenishment_volume),
        "quarantine_volume_m3": _round(active_quarantine_volume),
        "fefo_volume_m3": _round(active_fefo_volume),
        "current_over_capacity_location_count": current_over_capacity_count,
        "projected_over_capacity_location_count": projected_over_capacity_count,
        "current_capacity_pressure_location_count": current_pressure_count,
        "projected_capacity_pressure_location_count": projected_pressure_count,
        "trace_only_batch_count": trace_only_batch_count,
        "physical_map_included_batch_count": physical_map_batch_count,
        "traceability_layer_batch_count": traceability_batch_count,
        "total_current_used_volume_m3": _round(total_current_used_volume),
        "total_projected_used_volume_m3": _round(total_projected_used_volume),
        "current_utilization_pct": _round(current_util),
        "projected_utilization_pct": _round(projected_util),
        "total_capacity_kg": _round(total_capacity_kg),
        "total_current_used_weight_kg": _round(total_current_used_weight),
        "total_projected_used_weight_kg": _round(total_projected_used_weight),
        "current_weight_utilization_pct": _round(_pct(total_current_used_weight, total_capacity_kg)),
        "projected_weight_utilization_pct": _round(_pct(total_projected_used_weight, total_capacity_kg)),
        "space_utilization_cost": _round(current_cost),
        "projected_space_utilization_cost": _round(projected_cost),
        "utilization_warning": warning,
    }


def _space_cost(row: pd.Series, volume_column: str) -> float:
    """Calculate space cost for one location row."""
    multiplier = WAREHOUSE_ZONE_COST_MULTIPLIERS.get(str(row.get("zone", "")).upper(), WAREHOUSE_ZONE_COST_MULTIPLIERS["DEFAULT"])
    return _float(row.get(volume_column)) * WAREHOUSE_SLOT_CONFIG["default_storage_cost_per_m3"] * multiplier


def _batch_group_for_space(batch_slotting: pd.DataFrame | None, group_name: str, group_type: str) -> pd.DataFrame | None:
    """Return batch rows relevant to a space utilization group."""
    if batch_slotting is None or batch_slotting.empty or group_type != "zone" or "map_zone" not in batch_slotting.columns:
        return batch_slotting
    return batch_slotting[batch_slotting["map_zone"].fillna("").astype(str) == group_name]


def _batch_count(batch_slotting: pd.DataFrame | None, column: str, expected: bool) -> int:
    """Count batch rows with a boolean flag."""
    if batch_slotting is None or batch_slotting.empty or column not in batch_slotting.columns:
        return 0
    return int((batch_slotting[column].apply(_bool) == expected).sum())


def _space_warning(projected_util: float) -> str:
    """Return warehouse utilization warning text."""
    if projected_util >= WAREHOUSE_UTILIZATION_THRESHOLDS["warehouse_over_capacity_pct"]:
        return "WAREHOUSE_OVER_CAPACITY"
    if projected_util >= WAREHOUSE_UTILIZATION_THRESHOLDS["warehouse_high_utilization_pct"]:
        return "WAREHOUSE_HIGH_UTILIZATION"
    return "OK"


def _build_travel_costs(warehouse_slotting: pd.DataFrame) -> pd.DataFrame:
    """Build focused travel cost output."""
    travel = warehouse_slotting.copy()
    travel["movement_count"] = travel.apply(lambda row: _float(row.get("movement_count")), axis=1) if "movement_count" in travel.columns else 0
    travel["travel_warning_flags"] = travel["slotting_warning_flags"].apply(_travel_warning_subset)
    travel["travel_info_flags"] = travel.apply(_travel_info_subset, axis=1)
    travel["travel_reason"] = travel.apply(_travel_reason, axis=1)
    travel["visual_travel_risk_group"] = travel.apply(_visual_travel_risk_group, axis=1)
    return _ensure_columns(travel, _travel_output_columns())[_travel_output_columns()]


def _travel_warning_subset(value) -> str:
    """Return only travel-related warnings."""
    travel_codes = {"FAST_MOVING_ITEM_TOO_FAR", "A_CLASS_ITEM_TOO_FAR", "HIGH_TRAVEL_DISTANCE"}
    return ";".join(code for code in str(value).split(";") if code in travel_codes)


def _travel_info_subset(row: pd.Series) -> str:
    """Return travel informational flags."""
    flags = []
    for value in [row.get("slotting_info_flags", ""), row.get("slotting_warning_flags", "")]:
        for code in str(value).split(";"):
            if code in {"TRAVEL_THRESHOLD_USES_ONE_WAY", "TRAVEL_THRESHOLD_USES_TOTAL_ROUTE"}:
                flags.append(code)
    return ";".join(_unique(flags))


def _travel_reason(row: pd.Series) -> str:
    """Create travel reason text."""
    if row.get("travel_warning_flags"):
        return "Assigned location creates elevated travel distance for SKU movement profile."
    return "Travel distance and cost are within configured thresholds for this SKU."


def _visual_travel_risk_group(row: pd.Series) -> str:
    """Return Step 10 travel visual risk group."""
    warnings = set(_split_flags(row.get("travel_warning_flags", "")))
    if not str(row.get("recommended_location_id", "")).strip():
        return "NO_LOCATION"
    if "FAST_MOVING_ITEM_TOO_FAR" in warnings:
        return "FAST_MOVING_TOO_FAR"
    if "A_CLASS_ITEM_TOO_FAR" in warnings:
        return "A_CLASS_TOO_FAR"
    if "HIGH_TRAVEL_DISTANCE" in warnings:
        return "HIGH_TRAVEL_DISTANCE"
    return "NORMAL_TRAVEL"


def _map_color_group(row: pd.Series, status: str) -> str:
    """Return visualization color group for Step 10."""
    if status == "NO_FEASIBLE_LOCATION":
        return "NO_FEASIBLE_LOCATION"
    current_units = max(_float(row.get("current_inventory")), 0.0)
    if _float(row.get("quarantine_units")) > 0 and _float(row.get("quarantine_units")) >= current_units and _float(row.get("replenishment_units")) <= 0:
        return "EXPIRED"
    if row.get("main_inventory_status") == "STOCKOUT":
        return "STOCKOUT"
    if row.get("main_inventory_status") in {"REORDER_NOW", "CRITICAL_LOW_STOCK", "ZERO_STOCK"}:
        return "REORDER_NOW"
    if row.get("main_inventory_status") == "OVERSTOCK":
        return "OVERSTOCK"
    if row.get("movement_class") == "FAST_MOVING":
        return "FAST_MOVING"
    if row.get("perishability_class") in {"SPOILAGE_RISK", "EXPIRY_TRACKED", "PERISHABLE"}:
        return "PERISHABLE"
    return "NORMAL"


def _zone_multiplier(zone: str, location: pd.Series) -> float:
    """Return zone or special-control cost multiplier."""
    if _bool(location.get("temperature_controlled")):
        return WAREHOUSE_ZONE_COST_MULTIPLIERS["TEMPERATURE_CONTROLLED"]
    if _bool(location.get("security_controlled")):
        return WAREHOUSE_ZONE_COST_MULTIPLIERS["SECURITY_CONTROLLED"]
    return WAREHOUSE_ZONE_COST_MULTIPLIERS.get(zone, WAREHOUSE_ZONE_COST_MULTIPLIERS["DEFAULT"])


def _z_level_score(row: pd.Series, location: pd.Series) -> float:
    """Score vertical rack/shelf suitability for a SKU-location pair."""
    z_level = _float(location.get("z"))
    low_max = WAREHOUSE_Z_LEVEL_RULES["low_level_max_z"]
    medium_max = WAREHOUSE_Z_LEVEL_RULES["medium_level_max_z"]
    high_min = WAREHOUSE_Z_LEVEL_RULES["high_level_min_z"]

    if _is_heavy_sku(row):
        if z_level <= low_max:
            return 1.0
        if z_level <= medium_max:
            return 0.35
        return 0.0
    if row.get("movement_class") == "FAST_MOVING":
        if z_level <= WAREHOUSE_Z_LEVEL_RULES["fast_moving_max_preferred_z"]:
            return 1.0
        if z_level <= medium_max:
            return 0.45
        return 0.1
    if _bool(row.get("fragile")):
        if z_level <= WAREHOUSE_Z_LEVEL_RULES["fragile_max_preferred_z"]:
            return 1.0
        if z_level <= medium_max:
            return 0.35
        return 0.05
    if row.get("abc_class") == "C" or row.get("movement_class") in {"SLOW_MOVING", "NON_MOVING"}:
        if z_level >= high_min:
            return 1.0
        if z_level > low_max:
            return 0.75
        return 0.45
    if _float(row.get("quarantine_units")) > 0 and row.get("recommended_storage_zone") == "QUARANTINE":
        if z_level <= medium_max:
            return 0.8
        return 0.5
    if z_level <= medium_max:
        return 0.75
    return 0.45


def _is_heavy_sku(row: pd.Series) -> bool:
    """Return True when SKU should prefer low vertical levels."""
    return bool(
        _bool(row.get("heavy_low_storage_required"))
        or str(row.get("handling_unit", "")).upper() == "PALLET"
        or _float(row.get("unit_weight_kg")) >= WAREHOUSE_Z_LEVEL_RULES["heavy_item_weight_kg_threshold"]
    )


def _first_value(row: pd.Series, columns: list[str], default):
    """Return first existing non-null value."""
    for column in columns:
        if column in row.index and not pd.isna(row.get(column)):
            return row.get(column)
    return default


def _pct(value: float, denominator: float) -> float:
    """Return percentage with zero-safe denominator."""
    denominator = _float(denominator)
    if denominator <= 0:
        return 0.0
    return (_float(value) / denominator) * 100


def _round(value) -> float:
    """Round numeric values for CSV readability."""
    return round(_float(value), 2)


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


def _unique(values: list[str]) -> list[str]:
    """Return unique values preserving order."""
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _split_flags(value) -> list[str]:
    """Split semicolon-delimited flags into a clean list."""
    if pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(";") if item.strip()]


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Ensure dataframe has requested columns."""
    for column in columns:
        if column not in df.columns:
            df[column] = pd.NA
    return df


def _slotting_output_columns() -> list[str]:
    """Return warehouse_slotting.csv columns."""
    return [
        "sku_id",
        "product_name",
        "category",
        "current_inventory",
        "inventory_position",
        "recommended_order_quantity",
        "projected_units_after_order",
        "abc_class",
        "fsn_class",
        "movement_class",
        "vitality_class",
        "perishability_class",
        "seasonality_class",
        "inventory_priority_class",
        "main_inventory_status",
        "primary_action",
        "action_priority",
        "main_cost_driver",
        "cost_risk_level",
        "movement_count",
        "handling_unit",
        "unit_volume_m3",
        "unit_weight_kg",
        "temperature_control_required",
        "security_control_required",
        "forklift_required",
        "low_level_required",
        "ergonomic_level_required",
        "forklift_required_reason",
        "low_level_required_reason",
        "fefo_required",
        "expiry_tracking_required",
        "fragile",
        "hazardous",
        "stackable",
        "max_stack_height_m",
        "slotting_priority_score",
        "z_level_score",
        "recommended_storage_zone",
        "recommended_location_id",
        "location_assignment_status",
        "current_location_id",
        "zone",
        "aisle",
        "rack",
        "shelf",
        "bin",
        "assigned_temperature_controlled",
        "assigned_security_controlled",
        "assigned_forklift_accessible",
        "assigned_perishable_allowed",
        "assigned_fragile_allowed",
        "assigned_heavy_allowed",
        "zone_match_type",
        "expired_batch_ids",
        "near_expiry_batch_ids",
        "healthy_batch_ids",
        "expired_batch_count",
        "near_expiry_batch_count",
        "healthy_batch_count",
        "active_expired_batch_count",
        "active_near_expiry_batch_count",
        "active_healthy_batch_count",
        "expired_empty_batch_count",
        "near_expiry_empty_batch_count",
        "healthy_empty_batch_count",
        "quarantine_units",
        "near_expiry_units_for_fefo",
        "normal_storage_units",
        "replenishment_units",
        "historical_expired_or_near_expiry_batch_exists",
        "quarantine_location_id",
        "fefo_location_id",
        "primary_storage_location_id",
        "replenishment_receiving_location_id",
        "batch_split_required",
        "batch_split_reason",
        "active_batch_split_reason",
        "historical_batch_trace_reason",
        "primary_storage_units",
        "quarantine_storage_units",
        "fefo_storage_units",
        "replenishment_storage_units",
        "primary_storage_volume_m3",
        "quarantine_storage_volume_m3",
        "fefo_storage_volume_m3",
        "replenishment_storage_volume_m3",
        "primary_projected_volume_m3",
        "primary_storage_weight_kg",
        "quarantine_storage_weight_kg",
        "fefo_storage_weight_kg",
        "replenishment_storage_weight_kg",
        "primary_projected_weight_kg",
        "current_required_volume_m3",
        "projected_required_volume_m3",
        "current_required_weight_kg",
        "projected_required_weight_kg",
        "location_capacity_m3",
        "location_capacity_kg",
        "location_current_utilization_pct",
        "location_projected_utilization_pct",
        "location_current_weight_utilization_pct",
        "location_projected_weight_utilization_pct",
        "projected_space_shortage_m3",
        "projected_weight_shortage_kg",
        "current_space_utilization_cost",
        "projected_space_utilization_cost",
        "incremental_space_cost_after_order",
        "replenishment_location_projected_utilization_pct",
        "replenishment_location_projected_weight_utilization_pct",
        "replenishment_location_projected_over_capacity_flag",
        "replenishment_location_projected_capacity_pressure_flag",
        "sku_replenishment_volume_m3",
        "sku_replenishment_weight_kg",
        "sku_causes_projected_staging_pressure",
        "sku_replenishment_staging_warning",
        "sku_replenishment_staging_reason",
        "distance_from_receiving_m",
        "distance_to_shipping_m",
        "distance_to_pick_face_m",
        "one_way_operational_distance_m",
        "total_travel_distance_m",
        "travel_distance_basis",
        "travel_threshold_basis",
        "travel_time_min",
        "travel_cost",
        "frequency_adjusted_travel_distance_m",
        "frequency_adjusted_travel_cost",
        "slotting_warning_flags",
        "slotting_info_flags",
        "slotting_action_recommendation",
        "slotting_reason",
        "map_x",
        "map_y",
        "map_z",
        "map_zone",
        "map_label",
        "map_color_group",
        "primary_visual_location_id",
        "replenishment_visual_location_id",
        "quarantine_visual_location_id",
        "fefo_visual_location_id",
        "primary_visual_quantity",
        "replenishment_visual_quantity",
        "quarantine_visual_quantity",
        "fefo_visual_quantity",
        "primary_visual_volume_m3",
        "replenishment_visual_volume_m3",
        "quarantine_visual_volume_m3",
        "fefo_visual_volume_m3",
        "visual_status_group",
        "visual_warning_flags",
        "visual_info_flags",
    ]


def _location_utilization_columns() -> list[str]:
    """Return location_utilization.csv columns."""
    return [
        "location_id",
        "zone",
        "aisle",
        "rack",
        "shelf",
        "bin",
        "x",
        "y",
        "z",
        "capacity_m3",
        "capacity_kg",
        "assigned_sku_count",
        "assigned_skus",
        "assigned_primary_skus",
        "assigned_replenishment_skus",
        "assigned_quarantine_skus",
        "assigned_fefo_skus",
        "assigned_trace_only_batches",
        "assigned_primary_sku_count",
        "assigned_replenishment_sku_count",
        "assigned_quarantine_batch_count",
        "assigned_fefo_batch_count",
        "assigned_trace_only_batch_count",
        "location_role_summary",
        "location_role_warning_flags",
        "location_role_info_flags",
        "base_used_volume_m3_original",
        "base_used_weight_kg_original",
        "known_current_sku_volume_rebased",
        "known_current_sku_weight_rebased",
        "background_used_volume_m3",
        "background_used_weight_kg",
        "assigned_primary_volume_m3",
        "assigned_quarantine_volume_m3",
        "assigned_fefo_volume_m3",
        "assigned_replenishment_volume_m3",
        "assigned_primary_weight_kg",
        "assigned_quarantine_weight_kg",
        "assigned_fefo_weight_kg",
        "assigned_replenishment_weight_kg",
        "current_used_volume_m3",
        "projected_used_volume_m3",
        "current_utilization_pct",
        "projected_utilization_pct",
        "current_used_weight_kg",
        "projected_used_weight_kg",
        "current_weight_utilization_pct",
        "projected_weight_utilization_pct",
        "remaining_volume_m3",
        "projected_remaining_volume_m3",
        "remaining_weight_kg",
        "projected_remaining_weight_kg",
        "rebased_utilization_applied",
        "batch_level_location_utilization_applied",
        "current_over_capacity_flag",
        "projected_over_capacity_flag",
        "current_capacity_pressure_flag",
        "projected_capacity_pressure_flag",
        "current_capacity_status",
        "projected_capacity_status",
        "location_status",
        "location_warning_flags",
        "map_x",
        "map_y",
        "map_z",
        "map_zone",
        "map_label",
        "map_color_group",
    ]


def _travel_output_columns() -> list[str]:
    """Return warehouse_travel_costs.csv columns."""
    return [
        "sku_id",
        "product_name",
        "category",
        "recommended_location_id",
        "recommended_storage_zone",
        "abc_class",
        "fsn_class",
        "movement_class",
        "distance_from_receiving_m",
        "distance_to_shipping_m",
        "distance_to_pick_face_m",
        "one_way_operational_distance_m",
        "total_travel_distance_m",
        "travel_distance_basis",
        "travel_threshold_basis",
        "travel_time_min",
        "travel_cost",
        "movement_count",
        "frequency_adjusted_travel_distance_m",
        "frequency_adjusted_travel_cost",
        "travel_warning_flags",
        "travel_info_flags",
        "travel_reason",
        "visual_travel_risk_group",
        "map_x",
        "map_y",
        "map_z",
    ]


def _batch_slotting_columns() -> list[str]:
    """Return batch_slotting.csv columns."""
    return [
        "batch_id",
        "sku_id",
        "product_name",
        "category",
        "batch_quantity",
        "active_batch_quantity_flag",
        "active_batch_action_required",
        "batch_trace_only_flag",
        "expiry_date",
        "batch_status",
        "expired_flag",
        "near_expiry_flag",
        "recommended_batch_zone",
        "recommended_batch_location_id",
        "primary_sku_location_id",
        "quarantine_location_id",
        "fefo_location_id",
        "normal_storage_location_id",
        "batch_slotting_action",
        "batch_slotting_reason",
        "batch_slotting_warning_flags",
        "include_in_physical_map",
        "include_in_traceability_layer",
        "visual_quantity",
        "visual_layer",
        "visual_status_group",
        "visual_warning_flags",
        "visual_info_flags",
        "assigned_temperature_controlled",
        "assigned_security_controlled",
        "assigned_forklift_accessible",
        "assigned_perishable_allowed",
        "assigned_fragile_allowed",
        "assigned_heavy_allowed",
        "zone_match_type",
        "map_x",
        "map_y",
        "map_z",
        "map_zone",
        "map_label",
        "map_color_group",
    ]
