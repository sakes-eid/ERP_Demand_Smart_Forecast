"""Essential procurement KPI calculations for Phase 2."""

from __future__ import annotations

import pandas as pd


FULL_RECEIPT_TOLERANCE = 0.01


def add_supplier_performance_kpis(
    supplier_performance: pd.DataFrame,
    purchase_orders: pd.DataFrame,
    receipts: pd.DataFrame,
) -> pd.DataFrame:
    """Add OTIF and fill-rate KPIs to supplier performance."""
    if supplier_performance.empty:
        return supplier_performance
    result = supplier_performance.copy()
    if purchase_orders.empty or receipts.empty or "po_id" not in purchase_orders.columns or "po_id" not in receipts.columns:
        result["otif_rate"] = pd.NA
        result["otif_eligible_delivery_count"] = 0
        result["otif_delivery_count"] = 0
        result["supplier_fill_rate"] = pd.NA
        result["supplier_fill_rate_basis"] = "UNAVAILABLE_PO_RECEIPT_HISTORY"
        return result
    receipt_summary = _po_level_receipt_summary(receipts)
    po_cols = ["po_id", "supplier_id", "ordered_quantity", "promised_delivery_date"]
    po_history = purchase_orders[po_cols].drop_duplicates("po_id").merge(receipt_summary, on="po_id", how="left")
    po_history["promised_delivery_date"] = pd.to_datetime(po_history.get("promised_delivery_date"), errors="coerce")
    po_history["latest_receipt_date"] = pd.to_datetime(po_history.get("latest_receipt_date"), errors="coerce")
    for column in ["ordered_quantity", "accepted_quantity", "received_quantity"]:
        po_history[column] = pd.to_numeric(po_history.get(column), errors="coerce").fillna(0)
    po_history["receipt_row_count"] = pd.to_numeric(po_history.get("receipt_row_count"), errors="coerce").fillna(0)
    eligible = po_history["receipt_row_count"] > 0
    po_history["on_time_flag"] = eligible & po_history["latest_receipt_date"].notna() & po_history["promised_delivery_date"].notna() & (po_history["latest_receipt_date"] <= po_history["promised_delivery_date"])
    po_history["in_full_flag"] = eligible & (po_history["accepted_quantity"] + FULL_RECEIPT_TOLERANCE >= po_history["ordered_quantity"])
    po_history["otif_flag"] = po_history["on_time_flag"] & po_history["in_full_flag"]
    grouped = po_history[eligible].groupby("supplier_id", dropna=False).agg(
        otif_eligible_delivery_count=("po_id", "nunique"),
        otif_delivery_count=("otif_flag", "sum"),
        accepted_quantity=("accepted_quantity", "sum"),
        ordered_quantity=("ordered_quantity", "sum"),
        po_receipt_duplicate_row_count=("receipt_row_count", lambda s: int((pd.to_numeric(s, errors="coerce").fillna(0) > 1).sum())),
    ).reset_index()
    grouped["otif_rate"] = _safe_divide(grouped["otif_delivery_count"], grouped["otif_eligible_delivery_count"])
    grouped["supplier_fill_rate"] = _safe_divide(grouped["accepted_quantity"], grouped["ordered_quantity"])
    grouped["supplier_fill_rate_basis"] = "ACCEPTED_QUANTITY_DIVIDED_BY_ORDERED_QUANTITY"
    result = result.merge(
        grouped[[
            "supplier_id",
            "otif_rate",
            "otif_eligible_delivery_count",
            "otif_delivery_count",
            "supplier_fill_rate",
            "supplier_fill_rate_basis",
            "po_receipt_duplicate_row_count",
        ]],
        on="supplier_id",
        how="left",
    )
    result["otif_eligible_delivery_count"] = result["otif_eligible_delivery_count"].fillna(0).astype(int)
    result["otif_delivery_count"] = result["otif_delivery_count"].fillna(0).astype(int)
    result["po_receipt_duplicate_row_count"] = result["po_receipt_duplicate_row_count"].fillna(0).astype(int)
    result["supplier_fill_rate_basis"] = result["supplier_fill_rate_basis"].fillna("UNAVAILABLE_PO_RECEIPT_HISTORY")
    return result


def add_procurement_cost_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Add total procurement cost per usable unit where cost and quantity exist."""
    if df.empty:
        return df
    result = df.copy()
    quantity = _first_available_numeric(result, ["reference_usable_quantity", "allocated_usable_quantity_units", "final_immediate_order_quantity"])
    total_cost = _first_available_numeric(result, ["estimated_total_procurement_cost", "estimated_horizon_procurement_cost", "total_procurement_cost"])
    result["total_procurement_cost_kpi_numerator"] = total_cost
    result["total_procurement_cost_kpi_denominator_units"] = quantity
    result["total_procurement_cost_per_usable_unit"] = _safe_divide(total_cost, quantity)
    warning_source = result.get("procurement_warning_codes", result.get("allocation_warning_codes", pd.Series("NONE", index=result.index))).fillna("NONE").astype(str)
    result["total_procurement_cost_basis"] = "TOTAL_RELEVANT_PROCUREMENT_COST_DIVIDED_BY_USABLE_QUANTITY"
    result["total_procurement_cost_warning_codes"] = warning_source.where(warning_source.ne(""), "NONE")
    return result


def add_allocation_kpis(allocation_context: pd.DataFrame, allocation_summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Add coverage, utilization, and concentration KPIs to allocation bridges."""
    context = allocation_context.copy()
    summary = allocation_summary.copy()
    if not context.empty:
        context["supplier_capacity_utilization_rate"] = _safe_divide(
            _num(context, "allocated_usable_quantity_units"),
            _num(context, "supplier_horizon_capacity_units"),
        )
        context["supplier_capacity_utilization_status"] = context["supplier_capacity_utilization_rate"].apply(_capacity_status)
        context["capacity_utilization_availability"] = context["supplier_capacity_utilization_rate"].apply(lambda v: "UNAVAILABLE" if pd.isna(v) else "AVAILABLE")
        context = add_procurement_cost_kpis(context)
    if not summary.empty:
        requested = _num(summary, "requested_requirement_units")
        allocated = _num(summary, "total_allocated_usable_quantity")
        unallocated = _num(summary, "unallocated_requirement_units")
        summary["requirement_coverage_rate"] = _safe_divide(allocated, requested).fillna(1.0)
        summary["unallocated_requirement_rate"] = _safe_divide(unallocated, requested).fillna(0.0)
        concentration = _supplier_concentration(context)
        summary = summary.merge(concentration, on="sku_id", how="left")
    aggregate = _aggregate_kpi_summary(context, summary)
    return context, summary, aggregate


def _supplier_concentration(context: pd.DataFrame) -> pd.DataFrame:
    if context.empty or "sku_id" not in context.columns:
        return pd.DataFrame(columns=["sku_id", "top_supplier_allocation_share", "supplier_concentration_risk_status"])
    rows = []
    for sku_id, group in context.groupby("sku_id", dropna=False):
        allocated = _num(group, "allocated_usable_quantity_units")
        total = allocated.sum()
        if total <= 0:
            share = pd.NA
            status = "NO_ALLOCATION"
        else:
            share = float(allocated.max() / total)
            supplier_count = group.loc[allocated > 0, "supplier_id"].nunique() if "supplier_id" in group.columns else 0
            if supplier_count <= 1:
                status = "SINGLE_SOURCE"
            elif share >= 0.80:
                status = "HIGH"
            elif share >= 0.60:
                status = "MEDIUM"
            else:
                status = "LOW"
        rows.append({"sku_id": sku_id, "top_supplier_allocation_share": share, "supplier_concentration_risk_status": status})
    return pd.DataFrame(rows)


def _aggregate_kpi_summary(context: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if not summary.empty:
        requested = _num(summary, "requested_requirement_units").sum()
        allocated = _num(summary, "total_allocated_usable_quantity").sum()
        unallocated = _num(summary, "unallocated_requirement_units").sum()
        rows.extend(
            [
                _row("REQUIREMENT", "requirement_coverage_rate", _scalar_divide(allocated, requested), "ratio", "Allocated usable quantity divided by requested usable requirement.", requested),
                _row("REQUIREMENT", "unallocated_requirement_rate", _scalar_divide(unallocated, requested), "ratio", "Unallocated requirement divided by requested requirement.", requested),
                _row("CONCENTRATION", "average_top_supplier_allocation_share", _num(summary, "top_supplier_allocation_share").mean(), "ratio", "Average largest-supplier allocation share across allocated SKUs.", _num(summary, "top_supplier_allocation_share").notna().sum()),
            ]
        )
    if not context.empty:
        active = _active_allocation_rows(context)
        total_allocated = _num(active, "allocated_usable_quantity_units").sum()
        total_capacity = _num(active, "supplier_horizon_capacity_units").sum()
        total_cost = _num(active, "total_procurement_cost_kpi_numerator").sum()
        total_cost_units = _num(active, "total_procurement_cost_kpi_denominator_units").sum()
        rows.append(_row("CAPACITY", "average_supplier_capacity_utilization_rate", _scalar_divide(total_allocated, total_capacity), "ratio", "Weighted allocation utilization: total allocated usable quantity divided by total relevant supplier horizon capacity.", total_capacity))
        rows.append(_row("COST", "average_total_procurement_cost_per_usable_unit", _scalar_divide(total_cost, total_cost_units), "currency/unit", "Weighted procurement cost: total procurement cost across active allocations divided by total usable allocated quantity.", total_cost_units))
    return pd.DataFrame(rows, columns=["kpi_category", "kpi_name", "kpi_value", "kpi_unit", "kpi_data_quality", "kpi_explanation"])


def _po_level_receipt_summary(receipts: pd.DataFrame) -> pd.DataFrame:
    working = receipts.copy()
    working["receipt_date"] = pd.to_datetime(working.get("receipt_date"), errors="coerce")
    for column in ["accepted_quantity", "received_quantity", "rejected_quantity", "defective_quantity"]:
        if column not in working.columns:
            working[column] = 0
        working[column] = pd.to_numeric(working[column], errors="coerce").fillna(0)
    return working.groupby("po_id", dropna=False).agg(
        received_quantity=("received_quantity", "sum"),
        accepted_quantity=("accepted_quantity", "sum"),
        rejected_quantity=("rejected_quantity", "sum"),
        defective_quantity=("defective_quantity", "sum"),
        earliest_receipt_date=("receipt_date", "min"),
        latest_receipt_date=("receipt_date", "max"),
        receipt_row_count=("po_id", "count"),
    ).reset_index()


def _active_allocation_rows(context: pd.DataFrame) -> pd.DataFrame:
    if context.empty:
        return context
    active = context.copy()
    if "allocation_status" in active.columns:
        status = active["allocation_status"].fillna("").astype(str).str.upper()
        active = active[~status.isin({"REJECTED", "CANCELLED", "INACTIVE"})]
    if "allocated_usable_quantity_units" in active.columns:
        active = active[_num(active, "allocated_usable_quantity_units") > 0]
    return active


def _row(category: str, name: str, value, unit: str, explanation: str, denominator=None) -> dict:
    denominator_value = pd.to_numeric(pd.Series([denominator]), errors="coerce").iloc[0] if denominator is not None else 1
    return {
        "kpi_category": category,
        "kpi_name": name,
        "kpi_value": round(float(value), 6) if pd.notna(value) else pd.NA,
        "kpi_unit": unit,
        "kpi_data_quality": "AVAILABLE" if pd.notna(value) and float(denominator_value) > 0 else "UNAVAILABLE_ZERO_OR_MISSING_DENOMINATOR",
        "kpi_explanation": explanation,
    }


def _capacity_status(value) -> str:
    if pd.isna(value):
        return "UNAVAILABLE"
    value = float(value)
    if value >= 1:
        return "FULLY_USED"
    if value >= 0.85:
        return "HIGH"
    if value >= 0.50:
        return "MEDIUM"
    return "LOW"


def _first_available_numeric(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    result = pd.Series(0.0, index=df.index)
    for column in columns:
        if column in df.columns:
            values = _num(df, column)
            result = result.mask(result.eq(0), values)
    return result


def _num(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[column], errors="coerce")


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = pd.to_numeric(denominator, errors="coerce").replace(0, pd.NA)
    return pd.to_numeric(numerator, errors="coerce") / denominator


def _scalar_divide(numerator: float, denominator: float):
    return float(numerator / denominator) if denominator else pd.NA
