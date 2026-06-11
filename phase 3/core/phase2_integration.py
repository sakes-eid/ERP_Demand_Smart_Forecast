"""Read-only Phase 2 procurement intelligence integration for Phase 3."""

from __future__ import annotations

import pandas as pd

from config import (
    PHASE2_PROCUREMENT_ALLOCATION_CONTEXT_FILE,
    PHASE2_PROCUREMENT_ALLOCATION_SUMMARY_FILE,
    PHASE2_PROCUREMENT_RECOMMENDATIONS_FILE,
    PHASE2_SUPPLY_CAPABILITY_CONTEXT_FILE,
    PHASE2_SUPPLIER_PERFORMANCE_FILE,
    PHASE2_SUPPLIER_SKU_SCORES_FILE,
    PHASE2_SUPPLIER_TRENDS_FILE,
)

PHASE2_DEFAULTS = {
    "recommended_supplier_id": "UNKNOWN",
    "backup_supplier_id": "UNKNOWN",
    "expected_lead_time_days": 7,
    "expected_arrival_date": "",
    "unit_cost_procurement": 0,
    "moq": 1,
    "batch_size": 1,
    "expected_yield_rate": 0.95,
    "final_feasible_order_quantity": 0,
    "estimated_total_procurement_cost": 0,
    "estimated_product_cost": 0,
    "estimated_fixed_order_cost": 0,
    "estimated_delivery_cost": 0,
    "estimated_expected_delay_cost": 0,
    "estimated_expected_partial_delivery_cost": 0,
    "estimated_expected_quality_cost": 0,
    "demand_adjusted_procurement_risk_score": 0.50,
    "demand_adjusted_procurement_risk_class": "MEDIUM",
    "recommended_supplier_feasible": False,
    "recommended_supplier_requires_review": True,
    "recommended_supplier_evidence_status": "UNKNOWN",
    "recommended_supplier_evidence_warning": "UNKNOWN",
    "recommended_supplier_history_status": "UNKNOWN",
    "supplier_trend_status": "INSUFFICIENT_DATA",
    "supplier_watchlist_flag": False,
    "supplier_watchlist_reason": "UNKNOWN",
    "split_sourcing_recommendation": False,
    "recommended_primary_share": 1.0,
    "recommended_backup_share": 0.0,
    "selection_reason": "UNKNOWN",
    "lead_time_std_days": 2,
    "delay_probability": 0,
    "partial_delivery_rate": 0,
    "defect_rate": 0,
    "procurement_risk_score": 0.50,
    "procurement_risk_class": "MEDIUM",
    "supplier_score": 0,
    "adjusted_supplier_score": 0,
    "feasibility_warning": "UNKNOWN",
    "feasibility_reason": "UNKNOWN",
    "supplier_option_count": 0,
    "feasible_supplier_option_count": 0,
    "infeasible_supplier_option_count": 0,
    "lowest_supplier_total_cost": 0,
    "highest_supplier_total_cost": 0,
    "average_supplier_total_cost": 0,
    "best_adjusted_supplier_score": 0,
    "has_watchlist_supplier_option": False,
    "has_review_required_supplier_option": False,
    "supplier_accepts_returns": False,
    "return_window_days": 0,
    "return_deduction_rate": 1.0,
    "return_transport_cost": 0.0,
    "return_policy_status": "MISSING_SUPPLIER_RETURN_POLICY",
    "phase2_context_status": "MISSING_PHASE2_CONTEXT",
    "phase2_context_source": "LEGACY_PROCUREMENT_RECOMMENDATIONS",
    "phase2_schema_version": "",
    "phase2_allocation_loaded_flag": False,
    "phase2_legacy_fallback_used_flag": True,
    "phase2_context_warning_codes": "LEGACY_PHASE2_CONTEXT_USED",
    "selected_supplier_ids": "",
    "supplier_allocation_quantities": "",
    "total_allocated_usable_quantity": 0,
    "total_supplier_purchase_quantity": 0,
    "total_procurement_cost": 0,
}


def load_phase2_inventory_context(sku_ids: set[str]) -> tuple[pd.DataFrame, dict]:
    """Load Phase 2 context as one row per SKU with safe fallbacks."""
    warnings: list[str] = []
    context = pd.DataFrame({"sku_id": sorted(str(sku_id).strip() for sku_id in sku_ids)})

    allocation_summary = _load_optional(PHASE2_PROCUREMENT_ALLOCATION_SUMMARY_FILE, "procurement_allocation_summary", warnings)
    allocation_context = _load_optional(PHASE2_PROCUREMENT_ALLOCATION_CONTEXT_FILE, "procurement_allocation_context", warnings)
    supply_capability = _load_optional(PHASE2_SUPPLY_CAPABILITY_CONTEXT_FILE, "supply_capability_context", warnings)
    recommendations = _load_optional(PHASE2_PROCUREMENT_RECOMMENDATIONS_FILE, "procurement_recommendations", warnings)
    supplier_scores = _load_optional(PHASE2_SUPPLIER_SKU_SCORES_FILE, "supplier_sku_scores", warnings)
    _load_optional(PHASE2_SUPPLIER_PERFORMANCE_FILE, "supplier_performance", warnings)
    _load_optional(PHASE2_SUPPLIER_TRENDS_FILE, "supplier_trends", warnings)

    context = _merge_allocation_summary(context, allocation_summary, allocation_context)
    context = _merge_supply_capability_summary(context, supply_capability)
    context = _merge_recommendations(context, recommendations)
    context = _merge_recommended_supplier_score_context(context, supplier_scores)
    context = _merge_supplier_option_summary(context, supplier_scores)
    context = _add_return_policy_placeholders(context)
    context = _fill_defaults(context)

    if not recommendations.empty:
        context.loc[context["recommended_supplier_id"] != "UNKNOWN", "phase2_context_status"] = "LOADED_FROM_PHASE2"
    if not allocation_summary.empty:
        context.loc[:, "phase2_context_status"] = "LOADED_FROM_PHASE2"
        context.loc[:, "phase2_context_source"] = "PHASE2_PROCUREMENT_ALLOCATION_SUMMARY"
        context.loc[:, "phase2_allocation_loaded_flag"] = True
        context.loc[:, "phase2_legacy_fallback_used_flag"] = False
        context.loc[:, "phase2_context_warning_codes"] = "NONE"
    elif not supply_capability.empty:
        context.loc[:, "phase2_context_source"] = "PHASE2_SUPPLY_CAPABILITY_CONTEXT"
        context.loc[:, "phase2_legacy_fallback_used_flag"] = False

    metadata = {
        "phase2_context_loaded": bool((context["phase2_context_status"] == "LOADED_FROM_PHASE2").any()),
        "phase2_warnings": warnings,
        "phase2_recommendation_skus_loaded": int((context["phase2_context_status"] == "LOADED_FROM_PHASE2").sum()),
        "phase2_supplier_option_rows_loaded": int(len(supplier_scores)),
        "phase2_context_source": context["phase2_context_source"].mode().iloc[0] if "phase2_context_source" in context.columns and not context.empty else "UNKNOWN",
        "phase2_allocation_loaded_flag": bool(context.get("phase2_allocation_loaded_flag", pd.Series([False])).astype(str).str.lower().isin(["true", "1", "yes"]).any()),
        "phase2_legacy_fallback_used_flag": bool(context.get("phase2_legacy_fallback_used_flag", pd.Series([True])).astype(str).str.lower().isin(["true", "1", "yes"]).any()),
    }
    return context, metadata


def _merge_allocation_summary(context: pd.DataFrame, allocation_summary: pd.DataFrame, allocation_context: pd.DataFrame) -> pd.DataFrame:
    if allocation_summary.empty or "sku_id" not in allocation_summary.columns:
        return context
    source = allocation_summary.copy()
    source["recommended_supplier_id"] = source.get("primary_supplier_id", "UNKNOWN")
    source["backup_supplier_id"] = source.get("backup_supplier_id", "UNKNOWN")
    source["final_feasible_order_quantity"] = source.get("total_supplier_purchase_quantity", 0)
    source["estimated_total_procurement_cost"] = source.get("total_procurement_cost", 0)
    source["recommended_supplier_feasible"] = source.get("allocation_feasible_flag", False)
    source["recommended_supplier_requires_review"] = source.get("human_review_required", True)
    source["split_sourcing_recommendation"] = source.get("split_sourcing_used_flag", False)
    source["selected_supplier_ids"] = source.get("primary_supplier_id", "").astype(str)
    if not allocation_context.empty and {"sku_id", "supplier_id", "allocated_usable_quantity_units"}.issubset(allocation_context.columns):
        plans = allocation_context.groupby("sku_id").apply(
            lambda group: ";".join(
                f"{row.supplier_id}:{float(row.allocated_usable_quantity_units):.2f}"
                for row in group.itertuples()
                if str(row.supplier_id) != "NO_SUPPLIER_REQUIRED"
            )
        )
        supplier_ids = allocation_context.groupby("sku_id")["supplier_id"].apply(
            lambda values: ";".join(sorted(set(str(value) for value in values if str(value) != "NO_SUPPLIER_REQUIRED")))
        )
        source = source.merge(plans.rename("supplier_allocation_quantities"), on="sku_id", how="left")
        source = source.merge(supplier_ids.rename("selected_supplier_ids"), on="sku_id", how="left", suffixes=("", "_from_context"))
        if "selected_supplier_ids_from_context" in source.columns:
            source["selected_supplier_ids"] = source["selected_supplier_ids_from_context"].fillna(source["selected_supplier_ids"])
            source = source.drop(columns=["selected_supplier_ids_from_context"])
    columns = [
        "sku_id",
        "recommended_supplier_id",
        "backup_supplier_id",
        "final_feasible_order_quantity",
        "estimated_total_procurement_cost",
        "recommended_supplier_feasible",
        "recommended_supplier_requires_review",
        "split_sourcing_recommendation",
        "selected_supplier_ids",
        "supplier_allocation_quantities",
        "total_allocated_usable_quantity",
        "total_supplier_purchase_quantity",
        "total_procurement_cost",
        "schema_version",
    ]
    merged = _merge_available(context, source, columns)
    if "schema_version" in merged.columns:
        merged["phase2_schema_version"] = merged["schema_version"].fillna("")
        merged = merged.drop(columns=["schema_version"], errors="ignore")
    return merged


def _merge_supply_capability_summary(context: pd.DataFrame, supply_capability: pd.DataFrame) -> pd.DataFrame:
    if supply_capability.empty or "sku_id" not in supply_capability.columns:
        return context
    working = supply_capability.copy()
    working["base_supplier_feasible_flag"] = _to_bool(working.get("base_supplier_feasible_flag", False))
    summary = working.groupby("sku_id", dropna=False).agg(
        supplier_option_count=("supplier_id", "nunique"),
        feasible_supplier_option_count=("base_supplier_feasible_flag", "sum"),
        lowest_supplier_total_cost=("quality_adjusted_unit_cost", "min"),
        highest_supplier_total_cost=("quality_adjusted_unit_cost", "max"),
        average_supplier_total_cost=("quality_adjusted_unit_cost", "mean"),
    ).reset_index()
    summary["infeasible_supplier_option_count"] = summary["supplier_option_count"] - summary["feasible_supplier_option_count"]
    return context.merge(summary, on="sku_id", how="left", suffixes=("", "_supply_bridge"))


def _load_optional(path, label: str, warnings: list[str]) -> pd.DataFrame:
    """Load a Phase 2 CSV if present."""
    if not path.exists():
        warnings.append(f"Phase 2 {label} file missing: {path.name}")
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        warnings.append(f"Could not read Phase 2 {label}: {exc}")
        return pd.DataFrame()


def _merge_recommendations(context: pd.DataFrame, recommendations: pd.DataFrame) -> pd.DataFrame:
    """Merge recommendation fields."""
    if recommendations.empty or "sku_id" not in recommendations.columns:
        return context
    source = recommendations.copy()
    if "unit_cost" in source.columns:
        source = source.rename(columns={"unit_cost": "unit_cost_procurement"})
    columns = [
        "sku_id",
        "recommended_supplier_id",
        "backup_supplier_id",
        "expected_lead_time_days",
        "expected_arrival_date",
        "unit_cost_procurement",
        "moq",
        "batch_size",
        "expected_yield_rate",
        "final_feasible_order_quantity",
        "estimated_total_procurement_cost",
        "estimated_product_cost",
        "estimated_fixed_order_cost",
        "estimated_delivery_cost",
        "estimated_expected_delay_cost",
        "estimated_expected_partial_delivery_cost",
        "estimated_expected_quality_cost",
        "demand_adjusted_procurement_risk_score",
        "demand_adjusted_procurement_risk_class",
        "recommended_supplier_feasible",
        "recommended_supplier_requires_review",
        "recommended_supplier_evidence_status",
        "recommended_supplier_evidence_warning",
        "recommended_supplier_history_status",
        "supplier_trend_status",
        "supplier_watchlist_flag",
        "supplier_watchlist_reason",
        "split_sourcing_recommendation",
        "recommended_primary_share",
        "recommended_backup_share",
        "selection_reason",
    ]
    return _merge_available(context, source, columns)


def _merge_recommended_supplier_score_context(context: pd.DataFrame, supplier_scores: pd.DataFrame) -> pd.DataFrame:
    """Enrich recommendation with the chosen supplier option fields."""
    if supplier_scores.empty or "sku_id" not in supplier_scores.columns or "recommended_supplier_id" not in context.columns:
        return context
    source = supplier_scores.copy()
    columns = [
        "sku_id",
        "supplier_id",
        "lead_time_std_days",
        "delay_probability",
        "partial_delivery_rate",
        "defect_rate",
        "procurement_risk_score",
        "procurement_risk_class",
        "supplier_score",
        "adjusted_supplier_score",
        "feasibility_warning",
        "feasibility_reason",
    ]
    available = [column for column in columns if column in source.columns]
    if "supplier_id" not in available:
        return context
    source = source[available]
    merged = context.merge(
        source,
        left_on=["sku_id", "recommended_supplier_id"],
        right_on=["sku_id", "supplier_id"],
        how="left",
    )
    return merged.drop(columns=["supplier_id"], errors="ignore")


def _merge_supplier_option_summary(context: pd.DataFrame, supplier_scores: pd.DataFrame) -> pd.DataFrame:
    """Summarize all supplier options per SKU."""
    if supplier_scores.empty or "sku_id" not in supplier_scores.columns:
        return context
    working = supplier_scores.copy()
    working["is_feasible_supplier_option"] = _to_bool(working.get("is_feasible_supplier_option", False))
    working["supplier_watchlist_flag"] = _to_bool(working.get("supplier_watchlist_flag", False))
    working["supplier_requires_review"] = _to_bool(working.get("supplier_requires_review", False))
    summary = working.groupby("sku_id", dropna=False).agg(
        supplier_option_count=("supplier_id", "nunique") if "supplier_id" in working.columns else ("sku_id", "size"),
        feasible_supplier_option_count=("is_feasible_supplier_option", "sum"),
        lowest_supplier_total_cost=("estimated_total_procurement_cost", "min"),
        highest_supplier_total_cost=("estimated_total_procurement_cost", "max"),
        average_supplier_total_cost=("estimated_total_procurement_cost", "mean"),
        best_adjusted_supplier_score=("adjusted_supplier_score", "max"),
        has_watchlist_supplier_option=("supplier_watchlist_flag", "max"),
        has_review_required_supplier_option=("supplier_requires_review", "max"),
    ).reset_index()
    summary["infeasible_supplier_option_count"] = (
        summary["supplier_option_count"] - summary["feasible_supplier_option_count"]
    )
    return context.merge(summary, on="sku_id", how="left")


def _add_return_policy_placeholders(context: pd.DataFrame) -> pd.DataFrame:
    """Add future supplier return-policy placeholders."""
    enriched = context.copy()
    enriched["supplier_accepts_returns"] = False
    enriched["return_window_days"] = 0
    enriched["return_deduction_rate"] = 1.0
    enriched["return_transport_cost"] = 0.0
    enriched["return_policy_status"] = "MISSING_SUPPLIER_RETURN_POLICY"
    return enriched


def _merge_available(context: pd.DataFrame, source: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Merge columns present in source."""
    available = [column for column in columns if column in source.columns]
    if available == ["sku_id"]:
        return context
    return context.merge(source[available].drop_duplicates("sku_id"), on="sku_id", how="left")


def _fill_defaults(context: pd.DataFrame) -> pd.DataFrame:
    """Fill missing Phase 2 context columns."""
    filled = context.copy()
    for column, default in PHASE2_DEFAULTS.items():
        if column not in filled.columns:
            filled[column] = default
        else:
            filled[column] = filled[column].fillna(default)
    return filled[["sku_id", *PHASE2_DEFAULTS.keys()]]


def _to_bool(value) -> pd.Series:
    """Convert a series-like value to booleans."""
    if isinstance(value, pd.Series):
        return value.fillna(False).astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
    return pd.Series([bool(value)])
