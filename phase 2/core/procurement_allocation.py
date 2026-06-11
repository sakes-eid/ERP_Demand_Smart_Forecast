"""Supplier-constrained allocation from Phase 3 replenishment requirements."""

from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.contracts.cross_phase_contracts import (  # noqa: E402
    PHASE2_ALLOCATION_COLUMNS,
    PHASE2_ALLOCATION_SCHEMA_VERSION,
    PHASE2_ALLOCATION_SUMMARY_COLUMNS,
    PHASE_2,
    PHASE_3,
    SHARED_OUTPUT_DIR,
    ensure_columns,
    metadata_frame,
)


REQUIREMENT_FILE = SHARED_OUTPUT_DIR / "phase3_procurement_requirement_context.csv"


def build_procurement_allocation(
    requirement_context: pd.DataFrame,
    supply_capability_context: pd.DataFrame,
    *,
    run_id: str,
    planning_iteration: int = 0,
    data_as_of_date: str = "",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Allocate Phase 3 requested usable quantities to feasible Phase 2 suppliers."""
    allocation_rows: list[dict] = []
    summary_rows: list[dict] = []
    supply = supply_capability_context.copy()
    supply["base_supplier_feasible_flag"] = _bool_series(supply.get("base_supplier_feasible_flag", True))
    supply["supplier_active_flag"] = _bool_series(supply.get("supplier_active_flag", True))
    supply["supplier_capacity_30d"] = _num_series(supply.get("supplier_capacity_30d", 0))
    supply["supplier_per_order_capacity_units"] = _num_series(supply.get("supplier_per_order_capacity_units", 0))
    supply["supplier_reliability_score"] = _num_series(supply.get("supplier_reliability_score", 0))
    supply["supplier_risk_score"] = _num_series(supply.get("supplier_risk_score", 0.5))
    supply["landed_cost_per_unit"] = _num_series(supply.get("landed_cost_per_unit", supply.get("unit_cost", 0)))
    supply["quality_adjusted_unit_cost"] = _num_series(supply.get("quality_adjusted_unit_cost", supply["landed_cost_per_unit"]))

    for _, req in requirement_context.iterrows():
        sku_id = str(req.get("sku_id", "")).strip()
        requested = max(_num(req, "net_replenishment_requirement_units"), 0.0)
        options = supply[supply["sku_id"].astype(str).str.strip().eq(sku_id)].copy()
        options = options[options["base_supplier_feasible_flag"] & options["supplier_active_flag"]]
        options = options.sort_values(
            ["quality_adjusted_unit_cost", "supplier_reliability_score"],
            ascending=[True, False],
        )
        remaining = requested
        sku_allocations: list[dict] = []
        for _, option in options.iterrows():
            if remaining <= 0.01:
                break
            supplier_capacity = max(_num(option, "supplier_capacity_30d"), 0.0)
            if supplier_capacity <= 0:
                continue
            allocated = min(remaining, supplier_capacity)
            if allocated <= 0:
                continue
            role = "PRIMARY" if not sku_allocations else "SPLIT_SOURCE"
            row = _allocation_row(
                req=req,
                option=option,
                allocated_usable=allocated,
                requested=requested,
                remaining_after=max(remaining - allocated, 0.0),
                role=role,
                sequence=len(sku_allocations) + 1,
            )
            sku_allocations.append(row)
            remaining -= allocated

        if requested <= 0:
            sku_allocations.append(_no_order_allocation(req, sequence=1))
            remaining = 0.0
        elif not sku_allocations:
            sku_allocations.append(_review_candidate_allocation(req, options, requested))

        allocation_rows.extend(sku_allocations)
        summary_rows.append(_summary_row(req, sku_allocations, requested, max(remaining, 0.0)))

    allocation = pd.DataFrame(allocation_rows)
    summary = pd.DataFrame(summary_rows)
    allocation = metadata_frame(
        allocation,
        schema_version=PHASE2_ALLOCATION_SCHEMA_VERSION,
        run_id=run_id,
        planning_iteration=planning_iteration,
        source_phase=PHASE_2,
        target_phase=PHASE_3,
        data_as_of_date=data_as_of_date,
    )
    summary = metadata_frame(
        summary,
        schema_version=PHASE2_ALLOCATION_SCHEMA_VERSION,
        run_id=run_id,
        planning_iteration=planning_iteration,
        source_phase=PHASE_2,
        target_phase=PHASE_3,
        data_as_of_date=data_as_of_date,
    )
    return ensure_columns(allocation, PHASE2_ALLOCATION_COLUMNS), ensure_columns(summary, PHASE2_ALLOCATION_SUMMARY_COLUMNS)


def build_and_save_procurement_allocation(
    supply_capability_context: pd.DataFrame,
    *,
    run_id: str,
    planning_iteration: int = 0,
    data_as_of_date: str = "",
    requirement_path: Path = REQUIREMENT_FILE,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Build allocation bridge if the Phase 3 requirement bridge is available."""
    metadata = {
        "phase3_requirement_loaded": False,
        "authoritative_requirement_sku_count": 0,
        "fallback_requirement_sku_count": 0,
        "allocation_rows": 0,
    }
    if not requirement_path.exists():
        return pd.DataFrame(), pd.DataFrame(), metadata
    requirement_context = pd.read_csv(requirement_path)
    metadata["phase3_requirement_loaded"] = True
    metadata["authoritative_requirement_sku_count"] = int(requirement_context["sku_id"].nunique()) if "sku_id" in requirement_context.columns else 0
    allocation, summary = build_procurement_allocation(
        requirement_context,
        supply_capability_context,
        run_id=run_id,
        planning_iteration=planning_iteration,
        data_as_of_date=data_as_of_date,
    )
    SHARED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    allocation.to_csv(SHARED_OUTPUT_DIR / "phase2_procurement_allocation_context.csv", index=False)
    summary.to_csv(SHARED_OUTPUT_DIR / "phase2_procurement_allocation_summary.csv", index=False)
    metadata["allocation_rows"] = len(allocation)
    metadata["total_requested_usable_quantity"] = float(_num_series(summary.get("requested_requirement_units", 0)).sum())
    metadata["total_allocated_usable_quantity"] = float(_num_series(summary.get("total_allocated_usable_quantity", 0)).sum())
    metadata["total_supplier_purchase_quantity"] = float(_num_series(summary.get("total_supplier_purchase_quantity", 0)).sum())
    metadata["split_sourcing_allocation_count"] = int(_bool_series(summary.get("split_sourcing_used_flag", False)).sum())
    metadata["unallocated_requirement_total"] = float(_num_series(summary.get("unallocated_requirement_units", 0)).sum())
    return allocation, summary, metadata


def _allocation_row(req: pd.Series, option: pd.Series, allocated_usable: float, requested: float, remaining_after: float, role: str, sequence: int) -> dict:
    yield_rate = max(_num(option, "yield_rate"), 0.01)
    purchase = allocated_usable / yield_rate
    moq = max(_num(option, "moq"), 0.0)
    batch = max(_num(option, "batch_size"), _num(option, "order_multiple"), 1.0)
    moq_adjusted = max(purchase, moq)
    rounded = math.ceil(moq_adjusted / batch) * batch if batch > 0 else moq_adjusted
    capacity = max(_num(option, "supplier_capacity_30d"), 0.0)
    per_order = max(_num(option, "supplier_per_order_capacity_units"), capacity)
    landed = _num(option, "landed_cost_per_unit")
    quality = _num(option, "quality_adjusted_unit_cost") or landed
    fixed = _num(option, "fixed_order_cost")
    delivery = _num(option, "delivery_cost")
    product_cost = rounded * landed
    quality_cost = max(quality - landed, 0) * rounded
    total_cost = product_cost + fixed + delivery + quality_cost
    per_order_ok = allocated_usable <= per_order + 0.01 if per_order > 0 else True
    horizon_ok = allocated_usable <= capacity + 0.01 if capacity > 0 else False
    feasible = per_order_ok and horizon_ok
    supplier_id = str(option.get("supplier_id", "UNKNOWN"))
    first_arrival, final_arrival, arrival_warnings = _arrival_dates(req, option, role)
    warning_codes = []
    if not per_order_ok:
        warning_codes.append("PER_ORDER_CAPACITY_EXCEEDED")
    if not horizon_ok:
        warning_codes.append("HORIZON_CAPACITY_EXCEEDED")
    if role == "SPLIT_SOURCE":
        warning_codes.append("SPLIT_SOURCE_REVIEW_REQUIRED")
    warning_codes.extend(arrival_warnings)
    moq_increased = moq > 0 and moq_adjusted > purchase + 0.01
    batch_increased = batch > 1 and rounded > moq_adjusted + 0.01
    if moq_increased or batch_increased:
        warning_codes.append("MOQ_OR_BATCH_CONSTRAINT_REVIEW")
    return {
        "allocation_id": f"ALLOC-{req.get('sku_id')}-{sequence}-{supplier_id}",
        "sku_id": req.get("sku_id"),
        "supplier_id": supplier_id,
        "supplier_role": role,
        "requested_usable_quantity_units": round(requested, 2),
        "allocated_usable_quantity_units": round(allocated_usable, 2),
        "unallocated_requirement_units": round(remaining_after, 2),
        "yield_adjusted_purchase_quantity": round(purchase, 2),
        "moq_adjusted_purchase_quantity": round(moq_adjusted, 2),
        "batch_rounded_purchase_quantity": round(rounded, 2),
        "final_supplier_purchase_quantity": round(rounded, 2),
        "normal_delivery_quantity": round(allocated_usable, 2),
        "expedite_quantity": 0.0,
        "split_delivery_quantity": round(allocated_usable, 2) if role == "SPLIT_SOURCE" else 0.0,
        "first_shipment_quantity": round(allocated_usable, 2),
        "remaining_shipment_quantity": 0.0,
        "expected_first_arrival_date": first_arrival,
        "expected_final_arrival_date": final_arrival,
        "supplier_per_order_capacity_units": per_order,
        "supplier_horizon_capacity_units": capacity,
        "capacity_used_units": round(allocated_usable, 2),
        "capacity_remaining_units": round(max(capacity - allocated_usable, 0), 2),
        "per_order_capacity_feasible_flag": per_order_ok,
        "horizon_capacity_feasible_flag": horizon_ok,
        "allocation_capacity_feasible_flag": feasible,
        "unit_cost": _num(option, "unit_cost"),
        "landed_cost_per_unit": landed,
        "quality_adjusted_unit_cost": quality,
        "estimated_product_cost": round(product_cost, 2),
        "estimated_fixed_order_cost": fixed,
        "estimated_delivery_cost": delivery,
        "estimated_expedite_cost": 0.0,
        "estimated_delay_cost": 0.0,
        "estimated_quality_cost": round(quality_cost, 2),
        "estimated_total_procurement_cost": round(total_cost, 2),
        "supplier_reliability_score": _num(option, "supplier_reliability_score"),
        "supplier_risk_score": _num(option, "supplier_risk_score"),
        "supplier_risk_class": option.get("supplier_risk_class", "UNKNOWN"),
        "return_eligible": option.get("return_eligible", False),
        "expedite_used_flag": False,
        "split_delivery_used_flag": role == "SPLIT_SOURCE",
        "allocation_feasible_flag": feasible,
        "allocation_execution_allowed": False,
        "human_review_required": bool(role == "SPLIT_SOURCE"),
        "allocation_warning_codes": _join_codes(warning_codes),
        "allocation_reason": _allocation_reason(feasible, remaining_after, role, warning_codes),
    }


def _no_order_allocation(req: pd.Series, sequence: int) -> dict:
    return {
        "allocation_id": f"ALLOC-{req.get('sku_id')}-{sequence}-NO_ORDER",
        "sku_id": req.get("sku_id"),
        "supplier_id": "NO_SUPPLIER_REQUIRED",
        "supplier_role": "PRIMARY",
        "requested_usable_quantity_units": 0.0,
        "allocated_usable_quantity_units": 0.0,
        "unallocated_requirement_units": 0.0,
        "allocation_feasible_flag": True,
        "allocation_execution_allowed": False,
        "human_review_required": False,
        "allocation_warning_codes": "NO_REPLENISHMENT_REQUIREMENT",
        "allocation_reason": "Phase 3 net replenishment requirement is zero.",
    }


def _review_candidate_allocation(req: pd.Series, options: pd.DataFrame, requested: float) -> dict:
    supplier_id = str(options.iloc[0]["supplier_id"]) if not options.empty and "supplier_id" in options.columns else "NO_FEASIBLE_SUPPLIER"
    return {
        "allocation_id": f"ALLOC-{req.get('sku_id')}-1-REVIEW",
        "sku_id": req.get("sku_id"),
        "supplier_id": supplier_id,
        "supplier_role": "REVIEW_CANDIDATE",
        "requested_usable_quantity_units": round(requested, 2),
        "allocated_usable_quantity_units": 0.0,
        "unallocated_requirement_units": round(requested, 2),
        "allocation_feasible_flag": False,
        "allocation_execution_allowed": False,
        "human_review_required": True,
        "allocation_warning_codes": "NO_FEASIBLE_SUPPLIER_CAPACITY",
        "allocation_reason": "No executable supplier capacity could cover the requirement.",
    }


def _summary_row(req: pd.Series, allocations: list[dict], requested: float, remaining: float) -> dict:
    allocated = sum(_num_dict(row, "allocated_usable_quantity_units") for row in allocations)
    purchase = sum(_num_dict(row, "final_supplier_purchase_quantity") for row in allocations)
    cost = sum(_num_dict(row, "estimated_total_procurement_cost") for row in allocations)
    supplier_ids = [row.get("supplier_id", "") for row in allocations if row.get("supplier_id") not in {"", "NO_SUPPLIER_REQUIRED"}]
    feasible = remaining <= 0.01 and all(_to_bool(row.get("allocation_feasible_flag", False)) for row in allocations)
    split = len([supplier for supplier in supplier_ids if supplier != "NO_FEASIBLE_SUPPLIER"]) > 1
    arrival_values = [
        str(row.get(column, "")).strip()
        for row in allocations
        for column in ["expected_first_arrival_date", "expected_final_arrival_date"]
        if str(row.get(column, "")).strip()
    ]
    warnings = [row.get("allocation_warning_codes", "NONE") for row in allocations]
    if remaining > 0.01:
        warnings.append("REQUIREMENT_NOT_FULLY_ALLOCATED")
        warnings.append("AGGREGATE_CAPACITY_SHORTFALL")
    return {
        "sku_id": req.get("sku_id"),
        "requested_requirement_units": round(requested, 2),
        "total_allocated_usable_quantity": round(allocated, 2),
        "total_supplier_purchase_quantity": round(purchase, 2),
        "allocation_coverage_rate": round(allocated / requested, 4) if requested > 0 else 1.0,
        "primary_supplier_id": supplier_ids[0] if supplier_ids else "NO_SUPPLIER_REQUIRED",
        "backup_supplier_id": supplier_ids[1] if len(supplier_ids) > 1 else "",
        "supplier_count": len(set(supplier_ids)),
        "split_sourcing_used_flag": split,
        "expedite_used_flag": any(_to_bool(row.get("expedite_used_flag", False)) for row in allocations),
        "earliest_arrival_date": min(arrival_values) if arrival_values else "",
        "final_arrival_date": max(arrival_values) if arrival_values else "",
        "total_procurement_cost": round(cost, 2),
        "total_risk_adjusted_procurement_cost": round(cost * 1.05, 2),
        "allocation_feasible_flag": feasible,
        "unallocated_requirement_units": round(max(remaining, 0), 2),
        "human_review_required": any(_to_bool(row.get("human_review_required", False)) for row in allocations) or not feasible,
        "allocation_warning_codes": _join_codes(warnings),
    }


def _arrival_dates(req: pd.Series, option: pd.Series, role: str) -> tuple[str, str, list[str]]:
    warnings = []
    as_of = _parse_date(req.get("data_as_of_date", "")) or _parse_date(option.get("data_as_of_date", ""))
    if as_of is None:
        return "", "", ["ARRIVAL_DATE_UNAVAILABLE"]
    if _to_bool(option.get("expedite_available", False)) and str(req.get("replenishment_urgency", "")).upper() == "URGENT":
        first_lead = _num(option, "expedite_lead_time_days") or _num(option, "expected_lead_time_days")
        final_lead = first_lead
    elif role == "SPLIT_SOURCE":
        first_lead = _num(option, "first_shipment_lead_time_days") or _num(option, "expected_lead_time_days")
        final_lead = _num(option, "remaining_shipment_lead_time_days") or _num(option, "expected_lead_time_days") or first_lead
    else:
        first_lead = _num(option, "expected_lead_time_days")
        final_lead = first_lead
    if first_lead <= 0 or final_lead <= 0:
        return "", "", ["ARRIVAL_DATE_UNAVAILABLE"]
    first_date = as_of + timedelta(days=int(math.ceil(first_lead)))
    final_date = as_of + timedelta(days=int(math.ceil(final_lead)))
    return first_date.isoformat(), final_date.isoformat(), warnings


def _parse_date(value) -> datetime.date | None:
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None
    try:
        return pd.to_datetime(text).date()
    except Exception:
        return None


def _allocation_reason(feasible: bool, remaining_after: float, role: str, warning_codes: list[str]) -> str:
    if not feasible:
        return f"Allocation requires review: {_join_codes(warning_codes)}."
    if role == "SPLIT_SOURCE":
        return "Allocated through split sourcing; manager review is required before execution."
    return "Allocated from feasible supplier capacity."


def _num(row: pd.Series, column: str) -> float:
    if column not in row:
        return 0.0
    return float(pd.to_numeric(pd.Series([row[column]]), errors="coerce").fillna(0).iloc[0])


def _num_dict(row: dict, column: str) -> float:
    return float(pd.to_numeric(pd.Series([row.get(column, 0)]), errors="coerce").fillna(0).iloc[0])


def _num_series(series) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce").fillna(0)
    return pd.Series([series]).pipe(pd.to_numeric, errors="coerce").fillna(0)


def _bool_series(series) -> pd.Series:
    if isinstance(series, pd.Series):
        return series.fillna(False).astype(str).str.lower().isin({"true", "1", "yes", "y", "t"})
    return pd.Series([series]).astype(str).str.lower().isin({"true", "1", "yes", "y", "t"})


def _to_bool(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def _join_codes(values) -> str:
    codes = []
    for value in values:
        for code in str(value).split(";"):
            code = code.strip()
            if code and code != "NONE" and code not in codes:
                codes.append(code)
    return ";".join(codes) if codes else "NONE"
