"""Build the shared operational task view for Phase 3 role-based UI."""

from __future__ import annotations

import pandas as pd


EMPLOYEE_TASK_COLUMNS = [
    "sku_id",
    "product_name",
    "category",
    "warehouse_zone",
    "storage_location",
    "available_quantity",
    "usable_quantity",
    "net_replenishment_requirement",
    "recommended_action",
    "action_priority",
    "next_delivery_date",
    "expiry_status",
    "handling_warning",
    "manager_review_required",
    "employee_instruction",
]


def build_employee_task_view(
    manager_dashboard: pd.DataFrame,
    master_decisions: pd.DataFrame,
    warehouse_slotting: pd.DataFrame,
    inventory_kpis: pd.DataFrame,
    procurement_requirement_bridge: pd.DataFrame,
    allocation_summary: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Create one concise operational row per SKU for employee and manager views."""
    base = _base_sku_frame(manager_dashboard, master_decisions, procurement_requirement_bridge)
    if base.empty:
        return pd.DataFrame(columns=EMPLOYEE_TASK_COLUMNS)

    result = base.copy()
    result = _merge_optional(result, manager_dashboard, ["sku_id", "available_inventory", "current_inventory", "main_inventory_status", "final_review_required", "final_mandatory_review_required"])
    result = _merge_optional(result, master_decisions, ["sku_id", "proposed_operational_action", "final_recommended_action", "final_decision_priority", "final_review_required", "final_mandatory_review_required"])
    result = _merge_optional(result, warehouse_slotting, ["sku_id", "assigned_zone", "recommended_zone", "recommended_storage_zone", "zone", "assigned_location_id", "storage_location_id", "recommended_location_id", "current_location_id", "slotting_warning_flags"])
    result = _merge_optional(result, inventory_kpis, ["sku_id", "expiry_exposure_rate_30d", "dead_stock_rate", "excess_inventory_rate", "days_inventory_on_hand_status"])
    result = _merge_optional(result, procurement_requirement_bridge, ["sku_id", "net_replenishment_requirement_units", "usable_inventory_units", "available_inventory_units"])
    if allocation_summary is not None and not allocation_summary.empty:
        result = _merge_optional(
            result,
            allocation_summary,
            [
                "sku_id",
                "earliest_arrival_date",
                "final_arrival_date",
                "unallocated_requirement_units",
                "total_allocated_usable_quantity",
                "human_review_required",
                "allocation_warning_codes",
            ],
        )

    result["warehouse_zone"] = _first_text(result, ["assigned_zone", "recommended_zone", "recommended_storage_zone", "zone"], "UNASSIGNED")
    result["storage_location"] = _first_text(result, ["assigned_location_id", "storage_location_id", "recommended_location_id", "current_location_id"], "UNASSIGNED")
    source_available_quantity = _first_number(result, ["available_inventory_units", "available_inventory", "current_inventory"])
    source_usable_quantity = _first_number(result, ["usable_inventory_units"]).fillna(source_available_quantity)
    result["_negative_employee_stock_flag"] = (source_available_quantity.fillna(0) < 0) | (source_usable_quantity.fillna(0) < 0)
    result["available_quantity"] = source_available_quantity.clip(lower=0)
    result["usable_quantity"] = source_usable_quantity.clip(lower=0)
    result["net_replenishment_requirement"] = _first_number(result, ["net_replenishment_requirement_units"])
    result["recommended_action"] = _first_text(result, ["proposed_operational_action", "final_recommended_action"], "NO_ACTION")
    result["action_priority"] = _first_text(result, ["final_decision_priority"], "NO_ACTION")
    result["next_delivery_date"] = _first_text(result, ["earliest_arrival_date", "final_arrival_date"], "")
    result["expiry_status"] = result.apply(_expiry_status, axis=1)
    allocation_warnings = result.get("allocation_warning_codes", pd.Series("", index=result.index)).fillna("").astype(str).str.upper()
    result["_allocation_shortage_review_flag"] = (
        (pd.to_numeric(result.get("unallocated_requirement_units", 0), errors="coerce").fillna(0) > 0)
        | allocation_warnings.str.contains("UNALLOCATED_REQUIREMENT_REMAINS|ALLOCATION_ADJUSTMENT_REQUIRED|REQUIREMENT_NOT_FULLY_ALLOCATED|AGGREGATE_CAPACITY_SHORTFALL", na=False)
    )
    review_required = (
        _bool_any(result, ["final_mandatory_review_required", "final_review_required"])
        | result["_negative_employee_stock_flag"]
        | result["_allocation_shortage_review_flag"]
    )
    result["manager_review_required"] = review_required
    result["handling_warning"] = result.apply(_handling_warning, axis=1)
    result["employee_instruction"] = result.apply(_employee_instruction, axis=1)

    result = result[EMPLOYEE_TASK_COLUMNS].drop_duplicates("sku_id").sort_values("sku_id")
    return result


def _base_sku_frame(*frames: pd.DataFrame) -> pd.DataFrame:
    for frame in frames:
        if frame is not None and not frame.empty and "sku_id" in frame.columns:
            cols = ["sku_id"]
            for column in ["product_name", "category"]:
                if column in frame.columns:
                    cols.append(column)
            return frame[cols].drop_duplicates("sku_id").copy()
    return pd.DataFrame(columns=["sku_id", "product_name", "category"])


def _merge_optional(base: pd.DataFrame, source: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if source is None or source.empty or "sku_id" not in source.columns:
        return base
    keep = [column for column in columns if column in source.columns]
    if len(keep) <= 1:
        return base
    prepared = source[keep].drop_duplicates("sku_id")
    overlapping = [column for column in keep if column != "sku_id" and column in base.columns]
    base = base.drop(columns=overlapping, errors="ignore")
    return base.merge(prepared, on="sku_id", how="left")


def _first_text(df: pd.DataFrame, columns: list[str], default: str) -> pd.Series:
    result = pd.Series(default, index=df.index, dtype="object")
    for column in columns:
        if column in df.columns:
            values = df[column].fillna("").astype(str).str.strip()
            result = result.where(result.astype(str).str.strip().ne(default), values.where(values.ne(""), result))
    return result.fillna(default).replace("", default)


def _first_number(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    result = pd.Series(pd.NA, index=df.index, dtype="Float64")
    for column in columns:
        if column in df.columns:
            values = pd.to_numeric(df[column], errors="coerce")
            result = result.where(result.notna(), values)
    return result


def _bool_any(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    result = pd.Series(False, index=df.index)
    for column in columns:
        if column in df.columns:
            result = result | df[column].fillna(False).astype(str).str.lower().isin({"true", "1", "yes", "y", "t"})
    return result


def _expiry_status(row: pd.Series) -> str:
    exposure = _safe_float(row.get("expiry_exposure_rate_30d"))
    status = str(row.get("main_inventory_status", "")).upper()
    if "EXPIRED" in status:
        return "EXPIRED_REVIEW"
    if exposure > 0:
        return "NEAR_EXPIRY"
    return "NO_EXPIRY_ALERT"


def _handling_warning(row: pd.Series) -> str:
    warnings = []
    if bool(row.get("_negative_employee_stock_flag")):
        warnings.append("STOCKOUT_OR_NEGATIVE_INVENTORY_REVIEW")
    if bool(row.get("_allocation_shortage_review_flag")):
        warnings.append("PARTIAL ALLOCATION REVIEW")
        warnings.append("SUPPLIER SHORTAGE")
    if bool(row.get("manager_review_required")):
        warnings.append("MANAGER REVIEW REQUIRED")
    if _safe_float(row.get("net_replenishment_requirement")) > 0 and not str(row.get("next_delivery_date", "")).strip():
        warnings.append("WAITING DELIVERY")
    if str(row.get("expiry_status", "")) == "NEAR_EXPIRY":
        warnings.append("NEAR EXPIRY")
    slotting_warnings = str(row.get("slotting_warning_flags", "")).upper()
    if slotting_warnings and slotting_warnings != "NONE":
        warnings.append("WAREHOUSE CHECK REQUIRED")
    if warnings:
        return "; ".join(dict.fromkeys(warnings))
    return "NO ACTION REQUIRED"


def _employee_instruction(row: pd.Series) -> str:
    if bool(row.get("_allocation_shortage_review_flag")):
        if str(row.get("next_delivery_date", "")).strip():
            return "Wait for partial delivery; manager review required"
        return "Manager review required before full replenishment"
    if bool(row.get("_negative_employee_stock_flag")):
        return "Manager review required"
    if bool(row.get("manager_review_required")):
        return "Manager review required"
    if str(row.get("expiry_status", "")) == "NEAR_EXPIRY":
        return "Move near-expiry stock to front"
    if _safe_float(row.get("net_replenishment_requirement")) > 0:
        if str(row.get("next_delivery_date", "")).strip():
            return "Wait for delivery"
        return "Prepare replenishment"
    action = str(row.get("recommended_action", "")).upper()
    if action in {"NO_ACTION", "NO_ACTION_REQUIRED", "MONITOR_ONLY"}:
        return "No action required"
    return "Check task details"


def _safe_float(value) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
