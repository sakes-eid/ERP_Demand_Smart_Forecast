"""Procurement capability, contract, and supplier strategy context."""

import pandas as pd

from config import PROCUREMENT_CAPABILITY_CONFIG, RETURN_POLICY_CONFIG, SUPPLIER_STRATEGY_CONFIG
from core.procurement_requirement import add_option_immediate_requirements, build_procurement_requirements


def build_procurement_capability_context(
    suppliers_df: pd.DataFrame,
    supplier_sku_df: pd.DataFrame,
    supplier_performance_df: pd.DataFrame,
    supplier_sku_scores_df: pd.DataFrame,
    backorder_summary_df: pd.DataFrame,
    purchase_orders_df: pd.DataFrame | None = None,
    receipts_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build one row per SKU-supplier option with capability and cost context."""
    base = supplier_sku_df.copy()
    base = _normalize_supplier_sku_columns(base)
    suppliers = _normalize_supplier_columns(suppliers_df)

    context = base.merge(suppliers, on="supplier_id", how="left", suffixes=("", "_supplier"))
    context = _merge_performance(context, supplier_performance_df)
    context = _merge_scores(context, supplier_sku_scores_df)
    context = _merge_backorders(context, backorder_summary_df)
    context = _add_demand_capability_fields(context)
    requirements = build_procurement_requirements(
        context["sku_id"].dropna().astype(str).unique(),
        supplier_sku_scores_df,
        backorder_summary_df,
        purchase_orders_df if purchase_orders_df is not None else pd.DataFrame(),
        receipts_df if receipts_df is not None else pd.DataFrame(),
    )

    context["planning_reference_quantity"] = context["final_feasible_order_quantity"].fillna(
        PROCUREMENT_CAPABILITY_CONFIG["default_reference_order_quantity"]
    )
    context["effective_unit_price"] = context.apply(_effective_unit_price, axis=1)
    context["applicable_price_break_quantity"] = context.apply(_price_break_quantity, axis=1)
    context["estimated_freight_cost"] = context["effective_unit_price"] * context["freight_cost_rate"]
    context["estimated_handling_cost"] = context["effective_unit_price"] * context["handling_cost_rate"]
    context["estimated_insurance_cost"] = context["effective_unit_price"] * context["insurance_cost_rate"]
    context["estimated_customs_cost"] = context["effective_unit_price"] * context["customs_cost_rate"]
    context["landed_cost_per_unit"] = (
        context["effective_unit_price"]
        + context["estimated_freight_cost"]
        + context["estimated_handling_cost"]
        + context["estimated_insurance_cost"]
        + context["estimated_customs_cost"]
    ).round(4)

    context["expected_lead_time_days"] = context["standard_lead_time_days"]
    context["lead_time_std_days"] = context["lead_time_variability_days"]
    context["expected_defect_units"] = (
        context["planning_reference_quantity"] * context["defect_rate"].clip(lower=0)
    ).round(2)
    context["expected_quality_loss_cost"] = (
        context["expected_defect_units"]
        * context["effective_unit_price"]
        * PROCUREMENT_CAPABILITY_CONFIG["quality_loss_cost_multiplier"]
    ).round(2)
    context["quality_adjusted_unit_cost"] = (
        context["landed_cost_per_unit"] / context["yield_rate"].where(context["yield_rate"] > 0, 0.01)
    ).round(4)
    context = add_option_immediate_requirements(requirements, context)
    context["requirement_warning_codes"] = context["procurement_requirement_warning_codes"]
    context = _add_order_quantity_fields(context)
    context = _normalize_capacity_fields(context)
    context = _add_time_basis_cost_fields(context)
    context["capacity_shortfall_flag"] = ~context["horizon_capacity_feasible_flag"]
    context["expected_return_recovery_rate"] = context.apply(_return_recovery_rate, axis=1)
    context["expected_return_recovery_value"] = context.apply(_return_recovery_value, axis=1)
    context["near_expiry_return_possible"] = (
        context["accepts_returns"] & context["return_eligible"] & context["returns_allowed_for_near_expiry"]
    )
    context["expired_return_possible"] = (
        context["accepts_returns"] & context["return_eligible"] & context["returns_allowed_for_expired"]
    )
    context["expedite_total_cost_estimate"] = context.apply(_expedite_cost, axis=1)
    context["expedite_lead_time_reduction_days"] = (
        context["standard_lead_time_days"] - context["expedite_lead_time_days"]
    ).clip(lower=0)
    expedite_capacity_limit = pd.to_numeric(context["expedite_capacity_limit"], errors="coerce").fillna(0)
    context["expedite_capacity_feasible_flag"] = (
        context["expedite_available"]
        & context["expedite_eligible"]
        & (expedite_capacity_limit > 0)
        & (context["final_immediate_order_quantity"] <= expedite_capacity_limit)
    ).fillna(False)
    context["expedite_recommended_flag"] = (
        context["expedite_capacity_feasible_flag"]
        & context["backorder_pressure_flag"]
        & (context["expedite_lead_time_reduction_days"] >= PROCUREMENT_CAPABILITY_CONFIG["expedite_recommendation_min_days_saved"])
        & (context["supplier_reliability_score"] >= 0.60)
    )

    split = context.apply(_split_delivery_fields, axis=1, result_type="expand")
    context = pd.concat([context, split], axis=1)
    context["base_supplier_feasible_flag"] = context["is_feasible_supplier_option"]
    context["commercial_feasible_flag"] = (context["minimum_order_value"] <= (context["final_immediate_order_quantity"] * context["effective_unit_price"]))
    context["supplier_active_feasible_flag"] = context["is_feasible_supplier_option"]
    context["quality_feasible_flag"] = context["yield_rate"] > 0
    context["net_requirement_feasible_flag"] = context["provisional_net_procurement_requirement_units"] >= 0
    context["supplier_option_active_flag"] = context["supplier_active_feasible_flag"]
    context["final_executable_supplier_option_flag"] = (
        context["base_supplier_feasible_flag"]
        & context["commercial_feasible_flag"]
        & context["supplier_active_feasible_flag"]
        & context["quality_feasible_flag"]
        & context["immediate_requirement_feasible_flag"]
        & context["net_requirement_feasible_flag"]
        & (context["order_acceptance_probability"] >= PROCUREMENT_CAPABILITY_CONFIG["minimum_order_acceptance_probability"])
    )
    context["feasible_supplier_option_flag"] = context["final_executable_supplier_option_flag"]
    context = _add_aggregate_capacity_fields(context)
    context = _refine_demand_adjusted_risk(context)
    context = _add_balanced_supplier_scores(context)
    context = context.copy()
    reasons = context.apply(_infeasibility_reasons, axis=1)
    context["infeasibility_reasons"] = reasons.apply(lambda items: ";".join(items) if items else "NONE")
    warnings = context.apply(_warning_codes, axis=1)
    context["procurement_warning_codes"] = warnings.apply(lambda items: ";".join(items) if items else "NONE")
    context["downstream_planning_notes"] = context.apply(_downstream_notes, axis=1)

    return context[_capability_columns()].reset_index(drop=True)


def build_supplier_strategy_summary(
    capability_context_df: pd.DataFrame,
    procurement_recommendations_df: pd.DataFrame | None = None,
    purchase_orders_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build one strategy row per SKU without overwriting existing recommendations."""
    rows = []
    recommendations = procurement_recommendations_df if procurement_recommendations_df is not None else pd.DataFrame()
    latest_po_current = _latest_po_current_supplier(purchase_orders_df)
    for sku_id, options in capability_context_df.groupby("sku_id", sort=True):
        options = options.copy()
        eligible = _eligible_recommendation_pool(options)
        current, current_source, current_confidence, current_warnings = _current_supplier_for_sku(
            sku_id,
            options,
            latest_po_current,
            recommendations,
        )
        cheapest = _best_by(eligible, "landed_cost_per_unit", ascending=True)
        fastest = _best_by(eligible, "expected_lead_time_days", ascending=True)
        reliable = _best_by(eligible, "supplier_reliability_score", ascending=False)
        balanced = _best_by(eligible, "balanced_supplier_score", ascending=False)
        backup = _first_or_blank(options[options["backup_supplier_flag"]], "supplier_id")
        return_capable = _first_or_blank(eligible[eligible["return_eligible"] & eligible["accepts_returns"]], "supplier_id")
        expedite_capable = _first_or_blank(_expedite_pool(eligible), "supplier_id")
        split_capable = _first_or_blank(_split_pool(eligible), "supplier_id")

        rec = recommendations[recommendations["sku_id"] == sku_id] if not recommendations.empty else pd.DataFrame()
        current_recommended = str(rec.iloc[0]["recommended_supplier_id"]) if not rec.empty else balanced
        backorder_risk = str(options["backorder_risk_level"].dropna().iloc[0]) if not options.empty else "NONE"
        backorder_strategy = str(options["recommended_backorder_strategy"].dropna().iloc[0]) if not options.empty else "MONITOR"
        selection = _recommended_strategy(
            options,
            eligible,
            current,
            current_recommended,
            backorder_risk,
            backorder_strategy,
        )
        selected = _selected_option(options, selection["recommended_supplier_id"])
        evidence = _selected_option_evidence(selected)
        capacity_strategy = _capacity_strategy_fields(options, selection, selected)
        warning_scopes = _warning_scopes(options, selected, selection)
        consistency_flag, consistency_reason = _strategy_consistency(selection, current, selected)
        switch_flag = bool(selection["recommended_supplier_id"] and current and selection["recommended_supplier_id"] != current)
        expedite_switch = selection["recommended_supplier_strategy"].startswith("EXPEDITE_") and switch_flag
        split_switch = selection["recommended_supplier_strategy"].startswith("SPLIT_DELIVERY_") and switch_flag
        rows.append(
            {
                "sku_id": sku_id,
                "current_supplier_id": current,
                "current_supplier_source": current_source,
                "current_supplier_confidence": current_confidence,
                "current_supplier_warning_codes": current_warnings,
                "cheapest_supplier_id": cheapest,
                "fastest_supplier_id": fastest,
                "most_reliable_supplier_id": reliable,
                "balanced_supplier_id": balanced,
                "backup_supplier_id": backup,
                "return_capable_supplier_id": return_capable,
                "expedite_capable_supplier_id": expedite_capable,
                "split_delivery_capable_supplier_id": split_capable,
                "recommended_supplier_strategy": selection["recommended_supplier_strategy"],
                "recommended_supplier_id": selection["recommended_supplier_id"],
                "recommendation_reason": selection["recommendation_reason"],
                "supplier_review_required": selection["supplier_review_required"],
                "recommendation_execution_allowed": selection["recommendation_execution_allowed"] and consistency_flag,
                "recommended_option_feasible_flag": evidence["recommended_option_feasible_flag"],
                "recommended_option_infeasibility_reasons": evidence["recommended_option_infeasibility_reasons"],
                "recommendation_blocking_reason": (
                    selection["recommendation_blocking_reason"] if consistency_flag else consistency_reason
                ),
                "review_candidate_supplier_id": selection["review_candidate_supplier_id"],
                "review_candidate_reason": selection["review_candidate_reason"],
                "review_candidate_infeasibility_reasons": selection["review_candidate_infeasibility_reasons"],
                **evidence,
                "supplier_switch_flag": switch_flag,
                "supplier_switch_reason": _supplier_switch_reason(selection["recommended_supplier_strategy"], switch_flag),
                **capacity_strategy,
                "expedite_supplier_switch_flag": expedite_switch,
                "expedite_strategy_consistency_flag": _expedite_strategy_consistency(selection, current, selected),
                "expedite_strategy_reason": _expedite_strategy_reason(selection, current, selected),
                "split_delivery_supplier_switch_flag": split_switch,
                "split_delivery_strategy_consistency_flag": _split_strategy_consistency(selection, current, selected),
                "split_delivery_strategy_reason": _split_strategy_reason(selection, current, selected),
                "strategy_consistency_flag": consistency_flag,
                "strategy_consistency_reason": consistency_reason,
                "backorder_strategy": backorder_strategy,
                "backorder_risk_level": backorder_risk,
                "phase1_context_source": _first_value(options, "phase1_context_source", "INTERNAL_FALLBACK"),
                "demand_urgency_score": _first_value(options, "demand_urgency_score", 0.0),
                "forecast_demand_30d": _first_value(options, "forecast_demand_30d", 0.0),
                "forecast_uncertainty_level": _first_value(options, "forecast_uncertainty_level", "UNKNOWN"),
                "stockout_censored_demand_flag": _first_value(options, "stockout_censored_demand_flag", False),
                "underforecast_risk_flag": _first_value(options, "underforecast_risk_flag", False),
                "upcoming_event_flag": _first_value(options, "upcoming_event_flag", False),
                "demand_driven_strategy_flag": _demand_driven_strategy_flag(options, selection),
                "demand_driven_strategy_reason": _demand_driven_strategy_reason(options, selection),
                "demand_review_required": _demand_review_required(options),
                "demand_strategy_warning_codes": _first_value(options, "demand_strategy_warning_codes", "NONE"),
                "gross_forecast_demand_30d": _first_value(options, "gross_forecast_demand_30d", 0.0),
                "active_backorder_units": _first_value(options, "active_backorder_units", 0.0),
                "confirmed_inbound_units": _first_value(options, "confirmed_inbound_units", 0.0),
                "provisional_net_procurement_requirement_units": _first_value(options, "provisional_net_procurement_requirement_units", 0.0),
                "immediate_procurement_requirement_units": _first_value(options, "immediate_procurement_requirement_units", 0.0),
                "remaining_horizon_requirement_units": _first_value(options, "remaining_horizon_requirement_units", 0.0),
                "net_requirement_is_provisional_flag": _first_value(options, "net_requirement_is_provisional_flag", True),
                "aggregate_capacity_feasible_flag": _first_value(options, "aggregate_capacity_feasible_flag", False),
                "aggregate_capacity_shortfall_units": _first_value(options, "aggregate_capacity_shortfall_units", 0.0),
                "split_sourcing_capacity_feasible_flag": _first_value(options, "split_sourcing_capacity_feasible_flag", False),
                "split_sourcing_candidate_supplier_ids": _first_value(options, "split_sourcing_candidate_supplier_ids", ""),
                "split_sourcing_allocation_plan": _first_value(options, "split_sourcing_allocation_plan", ""),
                "minimum_supplier_count_required": _first_value(options, "minimum_supplier_count_required", 0),
                **warning_scopes,
                "warning_codes": warning_scopes["consolidated_manager_warning_codes"],
            }
        )
    return pd.DataFrame(rows)


def _normalize_supplier_columns(suppliers: pd.DataFrame) -> pd.DataFrame:
    normalized = suppliers.copy()
    defaults = {
        "supplier_name": "",
        "supplier_status": normalized.get("status", "active"),
        "supplier_country": normalized.get("country", ""),
        "supplier_region": "UNKNOWN",
        "supplier_currency": "USD",
        "accepts_returns": False,
        "return_window_days": 0,
        "return_deduction_rate": RETURN_POLICY_CONFIG["default_return_deduction_rate"],
        "return_shipping_cost": RETURN_POLICY_CONFIG["default_return_shipping_cost"],
        "return_handling_fee": RETURN_POLICY_CONFIG["default_return_handling_fee"],
        "return_minimum_quantity": 0,
        "returns_allowed_for_near_expiry": False,
        "returns_allowed_for_expired": False,
        "return_authorization_required": True,
        "return_policy_notes": "Return policy not provided.",
        "expedite_available": False,
        "expedite_lead_time_days": 0,
        "expedite_fixed_fee": 0,
        "expedite_cost_rate": 0,
        "expedite_capacity_limit": 0,
        "expedite_reliability": 0,
        "expedite_minimum_quantity": 0,
        "expedite_policy_notes": "Expedite policy not provided.",
        "split_delivery_available": False,
        "minimum_split_quantity": 0,
        "maximum_split_shipments": 1,
        "split_delivery_fixed_fee": 0,
        "split_delivery_variable_rate": 0,
        "first_shipment_lead_time_days": 0,
        "remaining_shipment_lead_time_days": 0,
        "partial_delivery_reliability": 0,
        "split_delivery_policy_notes": "Split delivery policy not provided.",
        "supplier_capacity_per_period": 0,
        "supplier_capacity_period_unit": PROCUREMENT_CAPABILITY_CONFIG["default_capacity_period_unit"],
        "supplier_capacity_period_days": PROCUREMENT_CAPABILITY_CONFIG["default_capacity_period_days"],
        "available_capacity": 0,
        "capacity_utilization": 0,
        "order_acceptance_probability": 0.75,
        "capacity_review_required": False,
        "capacity_notes": "Capacity not provided.",
        "freight_cost_rate": 0.05,
        "handling_cost_rate": 0.02,
        "insurance_cost_rate": 0.01,
        "customs_cost_rate": 0.02,
        "payment_terms_days": 30,
        "early_payment_discount_rate": 0,
        "late_payment_penalty_rate": 0,
        "minimum_order_value": 0,
    }
    for column, default in defaults.items():
        if column not in normalized.columns:
            normalized[column] = default
    for column in [
        "accepts_returns",
        "returns_allowed_for_near_expiry",
        "returns_allowed_for_expired",
        "return_authorization_required",
        "expedite_available",
        "split_delivery_available",
        "capacity_review_required",
    ]:
        normalized[column] = _to_bool_series(normalized[column])
    numeric_columns = [column for column in defaults if column not in {"supplier_name", "supplier_status", "supplier_country", "supplier_region", "supplier_currency", "return_policy_notes", "expedite_policy_notes", "split_delivery_policy_notes", "capacity_notes", "supplier_capacity_period_unit"}]
    for column in numeric_columns:
        if column not in {"accepts_returns", "returns_allowed_for_near_expiry", "returns_allowed_for_expired", "return_authorization_required", "expedite_available", "split_delivery_available", "capacity_review_required"}:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce").fillna(defaults[column])
    return normalized


def _normalize_supplier_sku_columns(supplier_sku: pd.DataFrame) -> pd.DataFrame:
    normalized = supplier_sku.copy()
    if "unit_price" not in normalized.columns:
        normalized["unit_price"] = normalized["unit_cost"]
    defaults = {
        "currency": "USD",
        "order_multiple": normalized.get("batch_size", 1),
        "standard_lead_time_days": normalized.get("lead_time_mean_days", 0),
        "minimum_lead_time_days": normalized.get("lead_time_mean_days", 0),
        "maximum_lead_time_days": normalized.get("lead_time_mean_days", 0),
        "lead_time_variability_days": normalized.get("lead_time_std_days", 0),
        "supplier_sku_capacity_per_period": 0,
        "supplier_sku_capacity_period_unit": PROCUREMENT_CAPABILITY_CONFIG["default_capacity_period_unit"],
        "supplier_sku_capacity_period_days": PROCUREMENT_CAPABILITY_CONFIG["default_capacity_period_days"],
        "supplier_sku_available_capacity": 0,
        "max_order_quantity": 0,
        "allocation_limit_by_sku": 0,
        "price_break_1_quantity": normalized.get("moq", 0),
        "price_break_1_unit_price": normalized.get("unit_price", normalized.get("unit_cost", 0)),
        "price_break_2_quantity": 0,
        "price_break_2_unit_price": normalized.get("unit_price", normalized.get("unit_cost", 0)),
        "price_break_3_quantity": 0,
        "price_break_3_unit_price": normalized.get("unit_price", normalized.get("unit_cost", 0)),
        "return_eligible": False,
        "expedite_eligible": False,
        "split_delivery_eligible": False,
        "preferred_supplier_flag": normalized.get("is_primary_supplier", False),
        "backup_supplier_flag": False,
    }
    for column, default in defaults.items():
        if column not in normalized.columns:
            normalized[column] = default
    for column in ["return_eligible", "expedite_eligible", "split_delivery_eligible", "preferred_supplier_flag", "backup_supplier_flag", "is_primary_supplier"]:
        if column in normalized.columns:
            normalized[column] = _to_bool_series(normalized[column])
    numeric_columns = [
        "unit_price",
        "unit_cost",
        "moq",
        "batch_size",
        "order_multiple",
        "standard_lead_time_days",
        "minimum_lead_time_days",
        "maximum_lead_time_days",
        "lead_time_variability_days",
        "yield_rate",
        "defect_rate",
        "supplier_sku_capacity_per_period",
        "supplier_sku_capacity_period_days",
        "supplier_sku_available_capacity",
        "max_order_quantity",
        "allocation_limit_by_sku",
        "price_break_1_quantity",
        "price_break_1_unit_price",
        "price_break_2_quantity",
        "price_break_2_unit_price",
        "price_break_3_quantity",
        "price_break_3_unit_price",
    ]
    for column in numeric_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce").fillna(0)
    return normalized


def _merge_performance(context: pd.DataFrame, performance: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "supplier_id",
        "calculated_reliability_score",
        "lead_time_std_days",
        "late_delivery_rate",
        "supplier_watchlist_flag",
        "supplier_trend_status",
    ]
    available = [column for column in columns if column in performance.columns]
    merged = context.merge(performance[available], on="supplier_id", how="left")
    merged["supplier_reliability_score"] = merged["calculated_reliability_score"].fillna(merged.get("base_reliability_score", 0.65))
    merged["delay_probability"] = merged["delay_probability"].fillna(merged.get("late_delivery_rate", 0.20))
    merged["supplier_risk_score"] = (1 - merged["supplier_reliability_score"].clip(0, 1)).round(4)
    merged["supplier_risk_class"] = merged["supplier_risk_score"].apply(_risk_class)
    merged["watchlist_flag"] = _to_bool_series(merged.get("supplier_watchlist_flag", pd.Series(False, index=merged.index)))
    return merged


def _merge_scores(context: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "sku_id",
        "supplier_id",
        "final_feasible_order_quantity",
        "is_feasible_supplier_option",
        "estimated_total_procurement_cost",
        "phase1_context_source",
        "demand_profile",
        "demand_variability_class",
        "forecast_demand_7d",
        "forecast_demand_30d",
        "forecast_demand_60d",
        "forecast_demand_90d",
        "demand_urgency_score",
        "demand_pressure_7d",
        "demand_pressure_30d",
        "forecast_confidence_band",
        "forecast_uncertainty_level",
        "high_uncertainty_flag",
        "underforecast_risk_flag",
        "overforecast_risk_flag",
        "stockout_censored_demand_flag",
        "lost_sales_estimate_30d",
        "adjusted_demand_30d",
        "upcoming_event_flag",
        "seasonal_phase",
        "demand_data_quality_score",
        "phase1_demand_warning_codes",
        "demand_integration_notes",
        "gross_forecast_demand_7d",
        "gross_forecast_demand_30d",
        "gross_forecast_demand_60d",
        "gross_forecast_demand_90d",
        "active_backorder_units",
        "backorder_requirement_units",
        "usable_on_hand_inventory_units",
        "confirmed_inbound_units",
        "open_po_confirmed_units_7d",
        "open_po_confirmed_units_30d",
        "open_po_confirmed_units_60d",
        "open_po_confirmed_units_90d",
        "expected_receipts_within_horizon_units",
        "uncertain_inbound_units",
        "provisional_buffer_requirement_units",
        "gross_procurement_requirement_units",
        "provisional_net_procurement_requirement_units",
        "immediate_procurement_requirement_units",
        "remaining_horizon_requirement_units",
        "inventory_deduction_available_flag",
        "inbound_deduction_available_flag",
        "net_requirement_is_provisional_flag",
        "procurement_requirement_method",
        "buffer_requirement_source",
        "inventory_context_missing_warning",
        "lead_time_demand_units",
        "confirmed_inbound_before_expected_arrival_units",
        "immediate_requirement_basis",
        "procurement_requirement_warning_codes",
        "immediate_requirement_warning_codes",
        "demand_risk_component",
        "supplier_risk_component",
        "backorder_risk_component",
        "capacity_risk_component",
        "event_risk_component",
        "total_demand_adjusted_risk_score",
        "demand_strategy_warning_codes",
        "demand_adjusted_procurement_risk_score",
        "demand_adjusted_procurement_risk_class",
    ]
    available = [column for column in columns if column in scores.columns]
    if not available:
        context["final_feasible_order_quantity"] = PROCUREMENT_CAPABILITY_CONFIG["default_reference_order_quantity"]
        context["is_feasible_supplier_option"] = True
        context["estimated_total_procurement_cost"] = 0
        return context
    merged = context.merge(scores[available], on=["sku_id", "supplier_id"], how="left")
    merged["final_feasible_order_quantity"] = merged["final_feasible_order_quantity"].fillna(
        merged["moq"].clip(lower=PROCUREMENT_CAPABILITY_CONFIG["default_reference_order_quantity"])
    )
    merged["is_feasible_supplier_option"] = _to_bool_series(merged["is_feasible_supplier_option"].fillna(True))
    return merged


def _add_demand_capability_fields(context: pd.DataFrame) -> pd.DataFrame:
    """Fill demand fields that repeat across options for a SKU."""
    filled = context.copy()
    defaults = {
        "phase1_context_source": "INTERNAL_FALLBACK",
        "demand_profile": "UNKNOWN",
        "demand_variability_class": "UNKNOWN",
        "forecast_demand_7d": 0.0,
        "forecast_demand_30d": 0.0,
        "forecast_demand_60d": 0.0,
        "forecast_demand_90d": 0.0,
        "demand_urgency_score": 0.0,
        "demand_pressure_7d": 0.0,
        "demand_pressure_30d": 0.0,
        "forecast_confidence_band": "UNKNOWN",
        "forecast_uncertainty_level": "UNKNOWN",
        "high_uncertainty_flag": False,
        "underforecast_risk_flag": False,
        "overforecast_risk_flag": False,
        "stockout_censored_demand_flag": False,
        "lost_sales_estimate_30d": 0.0,
        "adjusted_demand_30d": 0.0,
        "upcoming_event_flag": False,
        "seasonal_phase": "UNKNOWN",
        "demand_data_quality_score": 0.5,
        "phase1_demand_warning_codes": "NONE",
        "demand_integration_notes": "No Phase 1 demand planning context available.",
        "demand_strategy_warning_codes": "NONE",
    }
    for column, default in defaults.items():
        if column not in filled.columns:
            filled[column] = default
        else:
            filled[column] = filled[column].fillna(default)
    return filled


def _refine_demand_adjusted_risk(context: pd.DataFrame) -> pd.DataFrame:
    """Add backorder and capacity risk into the capability context risk view."""
    refined = context.copy()
    refined["backorder_risk_component"] = refined["backorder_risk_level"].map(
        {"CRITICAL": 1.0, "HIGH": 0.75, "MEDIUM": 0.45, "LOW": 0.20, "NONE": 0.0}
    ).fillna(0)
    refined["capacity_risk_component"] = (
        _to_bool_series(refined["capacity_shortfall_flag"]).astype(float) * 0.85
        + (pd.to_numeric(refined["capacity_utilization"], errors="coerce").fillna(0) >= 0.85).astype(float) * 0.35
    ).clip(0, 1)
    refined["event_risk_component"] = _to_bool_series(refined["upcoming_event_flag"]).astype(float) * 0.65
    refined["supplier_risk_component"] = pd.to_numeric(refined["supplier_risk_score"], errors="coerce").fillna(0)
    refined["demand_risk_component"] = pd.to_numeric(refined.get("demand_risk_component", 0), errors="coerce").fillna(0)
    refined["total_demand_adjusted_risk_score"] = (
        0.30 * refined["demand_risk_component"]
        + 0.25 * refined["supplier_risk_component"]
        + 0.18 * refined["backorder_risk_component"]
        + 0.15 * refined["capacity_risk_component"]
        + 0.12 * refined["event_risk_component"]
    ).clip(0, 1)
    refined["demand_adjusted_procurement_risk_score"] = refined["total_demand_adjusted_risk_score"]
    refined["demand_adjusted_procurement_risk_class"] = refined["demand_adjusted_procurement_risk_score"].apply(_risk_class)
    return refined


def _merge_backorders(context: pd.DataFrame, backorders: pd.DataFrame) -> pd.DataFrame:
    if backorders is None or backorders.empty:
        context["total_remaining_backorder_units"] = 0
        context["oldest_backorder_age_days"] = 0
        context["backorder_risk_level"] = "NONE"
        context["backorder_pressure_flag"] = False
        context["recommended_backorder_strategy"] = "MONITOR"
        return context
    columns = [
        "sku_id",
        "total_remaining_backorder_units",
        "oldest_backorder_age_days",
        "backorder_risk_level",
        "backorder_pressure_flag",
        "recommended_backorder_strategy",
    ]
    merged = context.merge(backorders[columns], on="sku_id", how="left")
    merged["total_remaining_backorder_units"] = merged["total_remaining_backorder_units"].fillna(0)
    merged["oldest_backorder_age_days"] = merged["oldest_backorder_age_days"].fillna(0)
    merged["backorder_risk_level"] = merged["backorder_risk_level"].fillna("NONE")
    backorder_pressure = merged["backorder_pressure_flag"].where(merged["backorder_pressure_flag"].notna(), False)
    merged["backorder_pressure_flag"] = _to_bool_series(backorder_pressure)
    merged["recommended_backorder_strategy"] = merged["recommended_backorder_strategy"].fillna("MONITOR")
    return merged


def _normalize_capacity_fields(context: pd.DataFrame) -> pd.DataFrame:
    """Convert supplier and SKU capacity to comparable period and horizon values."""
    enriched = context.copy()
    for prefix in ["supplier", "supplier_sku"]:
        unit_col = f"{prefix}_capacity_period_unit"
        days_col = f"{prefix}_capacity_period_days"
        if unit_col not in enriched.columns:
            enriched[unit_col] = PROCUREMENT_CAPABILITY_CONFIG["default_capacity_period_unit"]
        if days_col not in enriched.columns:
            enriched[days_col] = PROCUREMENT_CAPABILITY_CONFIG["default_capacity_period_days"]
        enriched[unit_col] = enriched[unit_col].fillna(PROCUREMENT_CAPABILITY_CONFIG["default_capacity_period_unit"]).astype(str).str.upper()
        enriched[days_col] = pd.to_numeric(enriched[days_col], errors="coerce").fillna(PROCUREMENT_CAPABILITY_CONFIG["default_capacity_period_days"])

    sku_capacity = pd.to_numeric(enriched["supplier_sku_available_capacity"], errors="coerce").fillna(0)
    supplier_capacity = pd.to_numeric(enriched["available_capacity"], errors="coerce").fillna(0)
    enriched["supplier_sku_capacity_per_day"] = enriched.apply(
        lambda row: _capacity_per_day(row["supplier_sku_available_capacity"], row["supplier_sku_capacity_period_unit"], row["supplier_sku_capacity_period_days"]),
        axis=1,
    )
    enriched["supplier_capacity_per_day"] = enriched.apply(
        lambda row: _capacity_per_day(row["available_capacity"], row["supplier_capacity_period_unit"], row["supplier_capacity_period_days"]),
        axis=1,
    )
    enriched["supplier_capacity_per_day"] = enriched[["supplier_sku_capacity_per_day", "supplier_capacity_per_day"]].replace(0, pd.NA).min(axis=1).fillna(0)
    for horizon in [7, 30, 60, 90]:
        enriched[f"supplier_capacity_{horizon}d"] = (enriched["supplier_capacity_per_day"] * horizon).round(2)
    enriched["supplier_horizon_capacity_units"] = enriched["supplier_capacity_30d"]
    enriched["supplier_per_order_capacity_units"] = pd.to_numeric(enriched["max_order_quantity"], errors="coerce").fillna(0)
    enriched.loc[enriched["supplier_per_order_capacity_units"] <= 0, "supplier_per_order_capacity_units"] = sku_capacity
    enriched["supplier_effective_horizon_capacity_units"] = enriched["supplier_horizon_capacity_units"]
    enriched["capacity_source"] = "MIN_SUPPLIER_AND_SUPPLIER_SKU_CAPACITY"
    enriched["capacity_normalization_method"] = "PER_DAY_NORMALIZED_TO_HORIZON"
    enriched["capacity_time_basis_warning_codes"] = enriched.apply(_capacity_time_basis_warning, axis=1)
    enriched["capacity_warning_codes"] = enriched["capacity_time_basis_warning_codes"]
    enriched["per_order_capacity_feasible_flag"] = (
        enriched["final_immediate_order_quantity"].fillna(0) <= enriched["supplier_per_order_capacity_units"].replace(0, pd.NA)
    ).fillna(False)
    enriched["immediate_requirement_feasible_flag"] = enriched["per_order_capacity_feasible_flag"]
    enriched["horizon_capacity_feasible_flag"] = (
        enriched["provisional_net_procurement_requirement_units"].fillna(0)
        <= enriched["supplier_horizon_capacity_units"].replace(0, pd.NA)
    ).fillna(False)
    return enriched


def _capacity_per_day(capacity, period_unit: str, period_days) -> float:
    capacity = float(pd.to_numeric(pd.Series([capacity]), errors="coerce").fillna(0).iloc[0])
    days = float(pd.to_numeric(pd.Series([period_days]), errors="coerce").fillna(0).iloc[0])
    unit = str(period_unit).upper()
    if unit == "DAILY":
        return capacity
    if unit == "WEEKLY":
        return capacity / 7
    if unit == "MONTHLY":
        return capacity / PROCUREMENT_CAPABILITY_CONFIG["default_month_days"]
    if unit == "CUSTOM_DAYS" and days > 0:
        return capacity / days
    if unit == "PER_ORDER":
        return 0.0
    return capacity / PROCUREMENT_CAPABILITY_CONFIG["default_capacity_period_days"]


def _capacity_time_basis_warning(row: pd.Series) -> str:
    warnings = []
    if row.get("supplier_capacity_period_unit", "") == PROCUREMENT_CAPABILITY_CONFIG["default_capacity_period_unit"]:
        warnings.append("CAPACITY_PERIOD_ASSUMED")
    if row.get("supplier_sku_capacity_period_unit", "") == "PER_ORDER":
        warnings.append("PER_ORDER_CAPACITY_NOT_HORIZON_CAPACITY")
    return ";".join(warnings) if warnings else "NONE"


def _add_order_quantity_fields(context: pd.DataFrame) -> pd.DataFrame:
    enriched = context.copy()
    enriched["raw_immediate_order_quantity"] = enriched["immediate_procurement_requirement_units"].clip(lower=0)
    enriched["yield_adjusted_immediate_order_quantity"] = (
        enriched["raw_immediate_order_quantity"] / enriched["yield_rate"].where(enriched["yield_rate"] > 0, 1)
    ).round(2)
    enriched["moq_adjusted_immediate_order_quantity"] = enriched[
        ["yield_adjusted_immediate_order_quantity", "moq"]
    ].max(axis=1)
    enriched["batch_rounded_immediate_order_quantity"] = enriched.apply(_round_immediate_to_batch, axis=1)
    enriched["final_immediate_order_quantity"] = enriched["batch_rounded_immediate_order_quantity"]
    lead_time = pd.to_numeric(enriched["expected_lead_time_days"], errors="coerce").fillna(0).clip(lower=0)
    enriched["planned_order_frequency_days"] = lead_time.clip(lower=PROCUREMENT_CAPABILITY_CONFIG["minimum_review_cycle_days"])
    enriched["estimated_order_cycle_count"] = (
        PROCUREMENT_CAPABILITY_CONFIG["default_planning_horizon_days"] / enriched["planned_order_frequency_days"].replace(0, 1)
    ).apply(lambda value: max(1, int(round(value + 0.499))))
    enriched["average_order_quantity_per_cycle"] = (
        enriched["provisional_net_procurement_requirement_units"] / enriched["estimated_order_cycle_count"].replace(0, 1)
    ).round(2)
    return enriched


def _round_immediate_to_batch(row: pd.Series) -> float:
    quantity = float(row.get("moq_adjusted_immediate_order_quantity", 0) or 0)
    batch_size = float(row.get("batch_size", 0) or 0)
    if batch_size <= 0:
        return quantity
    batches = int(-(-quantity // batch_size))
    return float(batches * batch_size)


def _add_time_basis_cost_fields(context: pd.DataFrame) -> pd.DataFrame:
    enriched = context.copy()
    enriched["estimated_total_fixed_order_cost_over_horizon"] = enriched["fixed_order_cost"] * enriched["estimated_order_cycle_count"]
    enriched["estimated_total_delivery_cost_over_horizon"] = enriched["delivery_cost"] * enriched["estimated_order_cycle_count"]
    enriched["estimated_immediate_procurement_cost"] = (
        enriched["final_immediate_order_quantity"] * enriched["landed_cost_per_unit"]
        + enriched["fixed_order_cost"]
        + enriched["delivery_cost"]
    ).round(2)
    enriched["estimated_order_cycle_cost"] = (
        enriched["average_order_quantity_per_cycle"] * enriched["landed_cost_per_unit"]
        + enriched["fixed_order_cost"]
        + enriched["delivery_cost"]
    ).round(2)
    enriched["estimated_horizon_procurement_cost"] = (
        enriched["provisional_net_procurement_requirement_units"] * enriched["landed_cost_per_unit"]
        + enriched["estimated_total_fixed_order_cost_over_horizon"]
        + enriched["estimated_total_delivery_cost_over_horizon"]
    ).round(2)
    return enriched


def _add_aggregate_capacity_fields(context: pd.DataFrame) -> pd.DataFrame:
    """Calculate SKU-level aggregate/split-sourcing horizon capacity."""
    rows = []
    for sku_id, options in context.groupby("sku_id", sort=False):
        viable = options[
            _to_bool_series(options["base_supplier_feasible_flag"])
            & _to_bool_series(options["supplier_active_feasible_flag"])
            & _to_bool_series(options["quality_feasible_flag"])
        ].copy()
        requirement = float(options["provisional_net_procurement_requirement_units"].iloc[0])
        total_capacity = float(viable["supplier_capacity_30d"].sum()) if not viable.empty else 0.0
        ranked = viable.sort_values(["supplier_risk_score", "landed_cost_per_unit"], ascending=[True, True])
        remaining = requirement
        allocation_parts = []
        candidate_ids = []
        candidate_caps = []
        for _, supplier in ranked.iterrows():
            capacity = max(float(supplier["supplier_capacity_30d"]), 0.0)
            if capacity <= 0 or remaining <= 0:
                continue
            allocated = min(capacity, remaining)
            allocation_parts.append(f"{supplier['supplier_id']}:{round(allocated, 2)}")
            candidate_ids.append(str(supplier["supplier_id"]))
            candidate_caps.append(f"{supplier['supplier_id']}:{round(capacity, 2)}")
            remaining -= allocated
        rows.append(
            {
                "sku_id": sku_id,
                "total_available_supplier_capacity_30d": round(total_capacity, 2),
                "total_available_supplier_capacity_horizon": round(total_capacity, 2),
                "aggregate_capacity_shortfall_units": round(max(requirement - total_capacity, 0), 2),
                "aggregate_capacity_feasible_flag": total_capacity >= requirement,
                "minimum_supplier_count_required": len(allocation_parts) if requirement > 0 else 0,
                "split_sourcing_capacity_feasible_flag": total_capacity >= requirement and len(allocation_parts) > 1,
                "split_sourcing_candidate_supplier_ids": ";".join(candidate_ids) if candidate_ids else "",
                "split_sourcing_candidate_capacities": ";".join(candidate_caps) if candidate_caps else "",
                "split_sourcing_allocation_plan": ";".join(allocation_parts) if allocation_parts else "",
                "split_sourcing_review_required": total_capacity >= requirement and len(allocation_parts) > 1,
            }
        )
    aggregate = pd.DataFrame(rows)
    return context.merge(aggregate, on="sku_id", how="left")


def _effective_unit_price(row: pd.Series) -> float:
    quantity = float(row["planning_reference_quantity"])
    price = float(row["unit_price"])
    for level in [3, 2, 1]:
        threshold = float(row.get(f"price_break_{level}_quantity", 0) or 0)
        break_price = float(row.get(f"price_break_{level}_unit_price", price) or price)
        if threshold > 0 and quantity >= threshold:
            price = break_price
            break
    return round(max(price, 0), 4)


def _price_break_quantity(row: pd.Series) -> float:
    quantity = float(row["planning_reference_quantity"])
    applied = 0.0
    for level in [1, 2, 3]:
        threshold = float(row.get(f"price_break_{level}_quantity", 0) or 0)
        if threshold > 0 and quantity >= threshold:
            applied = threshold
    return applied


def _return_recovery_rate(row: pd.Series) -> float:
    if not bool(row["accepts_returns"]) or not bool(row["return_eligible"]):
        return 0.0
    return round(max(1 - float(row["return_deduction_rate"]), 0), 4)


def _return_recovery_value(row: pd.Series) -> float:
    if _return_recovery_rate(row) <= 0:
        return 0.0
    quantity = max(float(row["planning_reference_quantity"]) - float(row["return_minimum_quantity"]), 0)
    value = quantity * float(row["effective_unit_price"]) * float(row["expected_return_recovery_rate"])
    value -= float(row["return_shipping_cost"]) + float(row["return_handling_fee"])
    return round(max(value, 0), 2)


def _expedite_cost(row: pd.Series) -> float:
    if not bool(row["expedite_available"]) or not bool(row["expedite_eligible"]):
        return 0.0
    return round(float(row["expedite_fixed_fee"]) + float(row["planning_reference_quantity"]) * float(row["effective_unit_price"]) * float(row["expedite_cost_rate"]), 2)


def _split_delivery_fields(row: pd.Series) -> pd.Series:
    feasible = (
        bool(row["split_delivery_available"])
        and bool(row["split_delivery_eligible"])
        and float(row["final_immediate_order_quantity"]) >= float(row["minimum_split_quantity"])
        and int(row["maximum_split_shipments"]) >= 2
    )
    first_qty = 0.0
    remaining_qty = 0.0
    if feasible:
        first_qty = round(float(row["final_immediate_order_quantity"]) * 0.50, 2)
        remaining_qty = round(float(row["final_immediate_order_quantity"]) - first_qty, 2)
    reference_date = pd.Timestamp.today().normalize()
    split_cost = 0.0
    if feasible:
        split_cost = float(row["split_delivery_fixed_fee"]) + float(row["final_immediate_order_quantity"]) * float(row["effective_unit_price"]) * float(row["split_delivery_variable_rate"])
    recommended = feasible and bool(row["backorder_pressure_flag"]) and row["backorder_risk_level"] in {"CRITICAL", "HIGH", "MEDIUM"}
    return pd.Series(
        {
            "split_delivery_feasible_flag": feasible,
            "first_shipment_quantity": first_qty,
            "remaining_shipment_quantity": remaining_qty,
            "expected_first_shipment_date": (reference_date + pd.Timedelta(days=int(row["first_shipment_lead_time_days"]))).strftime("%Y-%m-%d") if feasible else "",
            "expected_final_shipment_date": (reference_date + pd.Timedelta(days=int(row["remaining_shipment_lead_time_days"]))).strftime("%Y-%m-%d") if feasible else "",
            "split_delivery_cost_estimate": round(max(split_cost, 0), 2),
            "split_delivery_recommended_flag": recommended,
        }
    )


def _infeasibility_reasons(row: pd.Series) -> list[str]:
    reasons = []
    if not bool(row["is_feasible_supplier_option"]):
        reasons.append("BASE_SUPPLIER_OPTION_INFEASIBLE")
    if bool(row["capacity_shortfall_flag"]):
        reasons.append("CAPACITY_SHORTFALL")
    if float(row["order_acceptance_probability"]) < PROCUREMENT_CAPABILITY_CONFIG["minimum_order_acceptance_probability"]:
        reasons.append("LOW_ORDER_ACCEPTANCE_PROBABILITY")
    if float(row["yield_rate"]) <= 0:
        reasons.append("INVALID_YIELD")
    return reasons


def _warning_codes(row: pd.Series) -> list[str]:
    warnings = []
    if float(row["freight_cost_rate"]) == 0:
        warnings.append("FREIGHT_COST_FALLBACK_USED")
    if float(row["customs_cost_rate"]) == 0:
        warnings.append("CUSTOMS_COST_FALLBACK_USED")
    if float(row["quality_adjusted_unit_cost"]) == 0:
        warnings.append("QUALITY_COST_FALLBACK_USED")
    warnings.append("PAYMENT_TERMS_COST_NOT_MODELED")
    if bool(row["split_delivery_recommended_flag"]):
        warnings.append("WAREHOUSE_CAPACITY_REVIEW_REQUIRED_FOR_SPLIT_DELIVERY")
    if bool(row["capacity_shortfall_flag"]):
        warnings.append("CAPACITY_SHORTFALL")
    if bool(row["return_eligible"]) and not bool(row["accepts_returns"]):
        warnings.append("SUPPLIER_RETURN_POLICY_BLOCKS_SKU_RETURN")
    return warnings


def _downstream_notes(row: pd.Series) -> str:
    notes = []
    if bool(row["backorder_pressure_flag"]):
        notes.append("Backorder pressure should influence urgency and supplier strategy.")
    if bool(row["expedite_recommended_flag"]):
        notes.append("Expedite is available for review; do not auto-apply.")
    if bool(row["split_delivery_recommended_flag"]):
        notes.append("Split delivery is feasible but needs warehouse capacity review.")
    if bool(row["capacity_shortfall_flag"]):
        notes.append("Supplier capacity may constrain the planning quantity.")
    if not notes:
        notes.append("Supplier option is available for standard procurement planning.")
    return " ".join(notes)


def _add_balanced_supplier_scores(context: pd.DataFrame) -> pd.DataFrame:
    """Add transparent feasible-option balanced score and rank by SKU."""
    scored = context.copy()
    frames = []
    for _, options in scored.groupby("sku_id", sort=False):
        ranked = options.copy()
        ranked["balanced_supplier_score"] = (
            SUPPLIER_STRATEGY_CONFIG["balanced_cost_weight"]
            * _normalize_lower_is_better(ranked["quality_adjusted_unit_cost"])
            + SUPPLIER_STRATEGY_CONFIG["balanced_lead_time_weight"]
            * _normalize_lower_is_better(ranked["expected_lead_time_days"])
            + SUPPLIER_STRATEGY_CONFIG["balanced_reliability_weight"]
            * ranked["supplier_reliability_score"].clip(0, 1)
            + SUPPLIER_STRATEGY_CONFIG["balanced_risk_weight"]
            * (1 - ranked["supplier_risk_score"].clip(0, 1))
            + SUPPLIER_STRATEGY_CONFIG["balanced_quality_weight"]
            * ranked["yield_rate"].clip(0, 1)
            + SUPPLIER_STRATEGY_CONFIG["balanced_capacity_weight"]
            * ranked["order_acceptance_probability"].clip(0, 1)
            + SUPPLIER_STRATEGY_CONFIG["balanced_backorder_capability_weight"]
            * _backorder_capability_score(ranked)
        ).round(4)
        ranked.loc[~ranked["feasible_supplier_option_flag"], "balanced_supplier_score"] = -1
        ranked["balanced_supplier_score_rank"] = (
            ranked["balanced_supplier_score"].rank(ascending=False, method="dense").astype(int)
        )
        ranked["balanced_supplier_selection_reason"] = ranked.apply(_balanced_reason, axis=1)
        frames.append(ranked)
    return pd.concat(frames, ignore_index=True) if frames else scored


def _backorder_capability_score(df: pd.DataFrame) -> pd.Series:
    pressure = _to_bool_series(df["backorder_pressure_flag"]).astype(float)
    expedite = _to_bool_series(df["expedite_capacity_feasible_flag"]).astype(float)
    split = _to_bool_series(df["split_delivery_feasible_flag"]).astype(float)
    return (pressure * (0.65 * expedite + 0.35 * split)).clip(0, 1)


def _balanced_reason(row: pd.Series) -> str:
    if not bool(row["feasible_supplier_option_flag"]):
        return "Excluded from balanced selection because supplier option is not fully feasible."
    return "Balanced score combines landed cost, lead time, reliability, risk, quality, capacity, and backorder capability."


def _eligible_recommendation_pool(options: pd.DataFrame) -> pd.DataFrame:
    """Return supplier options that can be executable recommendations."""
    if options.empty:
        return options.copy()
    eligible = options[
        _to_bool_series(options["feasible_supplier_option_flag"])
        & _to_bool_series(options["supplier_option_active_flag"])
        & ~_to_bool_series(options["capacity_shortfall_flag"])
        & (
            pd.to_numeric(options["order_acceptance_probability"], errors="coerce").fillna(0)
            >= PROCUREMENT_CAPABILITY_CONFIG["minimum_order_acceptance_probability"]
        )
    ].copy()
    return eligible


def _expedite_pool(options: pd.DataFrame) -> pd.DataFrame:
    if options.empty:
        return options.copy()
    return options[
        _to_bool_series(options["expedite_available"])
        & _to_bool_series(options["expedite_eligible"])
        & _to_bool_series(options["expedite_capacity_feasible_flag"])
        & (
            pd.to_numeric(options["expedite_lead_time_days"], errors="coerce")
            < pd.to_numeric(options["standard_lead_time_days"], errors="coerce")
        )
    ].copy()


def _split_pool(options: pd.DataFrame) -> pd.DataFrame:
    if options.empty:
        return options.copy()
    return options[
        _to_bool_series(options["split_delivery_available"])
        & _to_bool_series(options["split_delivery_eligible"])
        & _to_bool_series(options["split_delivery_feasible_flag"])
    ].copy()


def _latest_po_current_supplier(purchase_orders_df: pd.DataFrame | None) -> dict[str, str]:
    """Find latest purchase-order supplier per SKU when purchase history is available."""
    if purchase_orders_df is None or purchase_orders_df.empty:
        return {}
    orders = purchase_orders_df.copy()
    if not {"sku_id", "supplier_id", "order_date"}.issubset(orders.columns):
        return {}
    orders["order_date"] = pd.to_datetime(orders["order_date"], errors="coerce")
    orders = orders.dropna(subset=["sku_id", "supplier_id", "order_date"])
    if orders.empty:
        return {}
    latest = orders.sort_values("order_date").groupby("sku_id", as_index=False).tail(1)
    return dict(zip(latest["sku_id"].astype(str), latest["supplier_id"].astype(str)))


def _current_supplier_for_sku(
    sku_id: str,
    options: pd.DataFrame,
    latest_po_current: dict[str, str],
    recommendations: pd.DataFrame,
) -> tuple[str, str, str, str]:
    """Identify current supplier using ordered evidence sources."""
    if sku_id in latest_po_current and latest_po_current[sku_id] in set(options["supplier_id"].astype(str)):
        return latest_po_current[sku_id], "LATEST_ACTIVE_PO", "HIGH", "NONE"
    preferred = options[_to_bool_series(options["preferred_supplier_flag"])]
    if not preferred.empty:
        return str(preferred.iloc[0]["supplier_id"]), "PREFERRED_SUPPLIER_FLAG", "MEDIUM", "NONE"
    rec = recommendations[recommendations["sku_id"] == sku_id] if not recommendations.empty else pd.DataFrame()
    if not rec.empty and str(rec.iloc[0].get("recommended_supplier_id", "")):
        return (
            str(rec.iloc[0]["recommended_supplier_id"]),
            "EXISTING_RECOMMENDATION_FALLBACK",
            "LOW",
            "CURRENT_SUPPLIER_FROM_RECOMMENDATION_FALLBACK",
        )
    return "", "UNKNOWN", "LOW", "CURRENT_SUPPLIER_UNKNOWN"


def _recommended_strategy(
    options: pd.DataFrame,
    eligible: pd.DataFrame,
    current_supplier_id: str,
    current_recommended: str,
    backorder_risk: str,
    backorder_strategy: str,
) -> dict[str, object]:
    """Select a logically consistent supplier strategy from feasible options only."""
    review_candidate = _review_candidate(options)
    if eligible.empty:
        if bool(options["aggregate_capacity_feasible_flag"].iloc[0]):
            review_candidate = _review_candidate(options)
            return _strategy_result(
                "REVIEW_SPLIT_SOURCING_PLAN",
                "",
                "Aggregate supplier capacity can cover the horizon, but no single supplier option is immediately executable.",
                True,
                False,
                "NO_IMMEDIATE_EXECUTABLE_SUPPLIER",
                review_candidate,
            )
        return _strategy_result(
            "REVIEW_AGGREGATE_CAPACITY_SHORTFALL",
            "",
            "No fully feasible supplier option is available for execution.",
            True,
            False,
            "AGGREGATE_CAPACITY_SHORTFALL" if not bool(options["aggregate_capacity_feasible_flag"].iloc[0]) else "No eligible recommendation pool; review supplier constraints.",
            review_candidate,
        )

    current_option = _selected_option(eligible, current_supplier_id)
    expedite_options = _expedite_pool(eligible).sort_values(
        ["expedite_lead_time_days", "balanced_supplier_score"], ascending=[True, False]
    )
    split_options = _split_pool(eligible).sort_values(
        ["first_shipment_lead_time_days", "balanced_supplier_score"], ascending=[True, False]
    )

    if backorder_strategy == "EXPEDITE_SUPPLY" and not expedite_options.empty:
        current_expedite = _selected_option(expedite_options, current_supplier_id)
        selected = current_expedite if current_expedite is not None else expedite_options.iloc[0]
        strategy = (
            "EXPEDITE_CURRENT_SUPPLIER"
            if current_supplier_id and selected["supplier_id"] == current_supplier_id
            else "EXPEDITE_ALTERNATIVE_SUPPLIER"
        )
        return _strategy_result(
            strategy,
            str(selected["supplier_id"]),
            _expedite_selection_reason(strategy, backorder_risk),
            True,
            True,
            "NONE",
            review_candidate,
        )

    if backorder_strategy == "SPLIT_DELIVERY" and not split_options.empty:
        current_split = _selected_option(split_options, current_supplier_id)
        selected = current_split if current_split is not None else split_options.iloc[0]
        strategy = (
            "SPLIT_DELIVERY_CURRENT_SUPPLIER"
            if current_supplier_id and selected["supplier_id"] == current_supplier_id
            else "SPLIT_DELIVERY_ALTERNATIVE_SUPPLIER"
        )
        return _strategy_result(
            strategy,
            str(selected["supplier_id"]),
            "Backorder pressure supports feasible split-delivery review.",
            True,
            True,
            "NONE",
            review_candidate,
        )

    if backorder_risk in {"CRITICAL", "HIGH", "MEDIUM"}:
        selected = eligible.sort_values("balanced_supplier_score", ascending=False).iloc[0]
        if not bool(selected["horizon_capacity_feasible_flag"]) and bool(selected["split_sourcing_capacity_feasible_flag"]):
            return _strategy_result(
                "SPLIT_SOURCING_CAPACITY_PLAN",
                str(selected["supplier_id"]),
                f"{backorder_risk.lower()} backorder risk is present; immediate supplier is feasible and aggregate capacity covers horizon through split sourcing.",
                True,
                True,
                "NONE",
                review_candidate,
            )
        if not bool(selected["horizon_capacity_feasible_flag"]):
            return _strategy_result(
                "IMMEDIATE_ORDER_WITH_HORIZON_REVIEW",
                str(selected["supplier_id"]),
                f"{backorder_risk.lower()} backorder risk is present; supplier can cover immediate requirement but horizon capacity needs review.",
                True,
                True,
                "HORIZON_CAPACITY_REVIEW_REQUIRED",
                review_candidate,
            )
        return _strategy_result(
            "BALANCED_SUPPLIER",
            str(selected["supplier_id"]),
            f"{backorder_risk.lower()} backorder risk is present; selected best feasible balanced supplier.",
            True,
            True,
            "NONE",
            review_candidate,
        )

    if current_supplier_id and current_option is not None:
        if not bool(current_option["horizon_capacity_feasible_flag"]) and bool(current_option["split_sourcing_capacity_feasible_flag"]):
            return _strategy_result(
                "SPLIT_SOURCING_CAPACITY_PLAN",
                current_supplier_id,
                "Current supplier can support immediate requirement; split sourcing covers the horizon.",
                True,
                True,
                "NONE",
                review_candidate,
            )
        if not bool(current_option["horizon_capacity_feasible_flag"]):
            return _strategy_result(
                "IMMEDIATE_ORDER_WITH_HORIZON_REVIEW",
                current_supplier_id,
                "Current supplier can support immediate requirement but not the full horizon alone.",
                True,
                True,
                "HORIZON_CAPACITY_REVIEW_REQUIRED",
                review_candidate,
            )
        return _strategy_result(
            "CURRENT_SUPPLIER",
            current_supplier_id,
            "Current supplier is identified and remains feasible; no supplier switch recommended.",
            False,
            True,
            "NONE",
            review_candidate,
        )

    if current_recommended:
        recommended_option = _selected_option(eligible, current_recommended)
        if recommended_option is not None:
            return _strategy_result(
                "EXISTING_RECOMMENDED_SUPPLIER",
                current_recommended,
                "Existing procurement recommendation is feasible, but it is not labeled as current supplier.",
                False,
                True,
                "NONE",
                review_candidate,
            )

    selected = eligible.sort_values("balanced_supplier_score", ascending=False).iloc[0]
    if not bool(selected["horizon_capacity_feasible_flag"]) and bool(selected["split_sourcing_capacity_feasible_flag"]):
        return _strategy_result(
            "SPLIT_SOURCING_CAPACITY_PLAN",
            str(selected["supplier_id"]),
            "Selected immediate supplier is feasible and aggregate capacity covers horizon through split sourcing.",
            True,
            True,
            "NONE",
            review_candidate,
        )
    if not bool(selected["horizon_capacity_feasible_flag"]):
        return _strategy_result(
            "IMMEDIATE_ORDER_WITH_HORIZON_REVIEW",
            str(selected["supplier_id"]),
            "Selected supplier can support immediate requirement but horizon capacity needs review.",
            True,
            True,
            "HORIZON_CAPACITY_REVIEW_REQUIRED",
            review_candidate,
        )
    return _strategy_result(
        "BALANCED_SUPPLIER",
        str(selected["supplier_id"]),
        "Current supplier is unavailable or infeasible; selected best feasible balanced supplier.",
        True,
        True,
        "NONE",
        review_candidate,
    )


def _strategy_result(
    strategy: str,
    supplier_id: str,
    reason: str,
    review_required: bool,
    execution_allowed: bool,
    blocking_reason: str,
    review_candidate: dict[str, str],
) -> dict[str, object]:
    return {
        "recommended_supplier_strategy": strategy,
        "recommended_supplier_id": supplier_id,
        "recommendation_reason": reason,
        "supplier_review_required": review_required,
        "recommendation_execution_allowed": execution_allowed,
        "recommendation_blocking_reason": blocking_reason,
        **review_candidate,
    }


def _review_candidate(options: pd.DataFrame) -> dict[str, str]:
    if options.empty:
        return {
            "review_candidate_supplier_id": "",
            "review_candidate_reason": "",
            "review_candidate_infeasibility_reasons": "",
        }
    infeasible = options[~_to_bool_series(options["feasible_supplier_option_flag"])].copy()
    if infeasible.empty:
        return {
            "review_candidate_supplier_id": "",
            "review_candidate_reason": "",
            "review_candidate_infeasibility_reasons": "",
        }
    candidate = infeasible.sort_values("balanced_supplier_score", ascending=False).iloc[0]
    return {
        "review_candidate_supplier_id": str(candidate["supplier_id"]),
        "review_candidate_reason": "Supplier may be useful for review but is not execution-approved.",
        "review_candidate_infeasibility_reasons": str(candidate.get("infeasibility_reasons", "NOT_FEASIBLE")),
    }


def _selected_option(options: pd.DataFrame, supplier_id: str) -> pd.Series | None:
    if not supplier_id or options.empty:
        return None
    matches = options[options["supplier_id"].astype(str) == str(supplier_id)]
    if matches.empty:
        return None
    return matches.iloc[0]


def _selected_option_evidence(selected: pd.Series | None) -> dict[str, object]:
    if selected is None:
        return {
            "recommended_option_feasible_flag": False,
            "recommended_option_infeasibility_reasons": "NO_SELECTED_SUPPLIER_OPTION",
            "recommended_supplier_unit_price": 0,
            "recommended_supplier_landed_cost_per_unit": 0,
            "recommended_supplier_quality_adjusted_unit_cost": 0,
            "recommended_supplier_expected_lead_time_days": 0,
            "recommended_supplier_reliability_score": 0,
            "recommended_supplier_risk_class": "",
            "recommended_supplier_capacity_shortfall_flag": False,
            "recommended_supplier_order_acceptance_probability": 0,
            "recommended_supplier_expedite_available": False,
            "recommended_supplier_split_delivery_available": False,
            "recommended_supplier_return_eligible": False,
            "selected_supplier_capacity_30d": 0,
            "selected_supplier_per_order_capacity": 0,
            "selected_supplier_immediate_requirement_feasible_flag": False,
            "selected_supplier_horizon_capacity_feasible_flag": False,
            "balanced_supplier_score": 0,
            "balanced_supplier_score_rank": 0,
            "balanced_supplier_selection_reason": "",
        }
    return {
        "recommended_option_feasible_flag": bool(selected["feasible_supplier_option_flag"]),
        "recommended_option_infeasibility_reasons": str(selected.get("infeasibility_reasons", "NONE")),
        "recommended_supplier_unit_price": selected["unit_price"],
        "recommended_supplier_landed_cost_per_unit": selected["landed_cost_per_unit"],
        "recommended_supplier_quality_adjusted_unit_cost": selected["quality_adjusted_unit_cost"],
        "recommended_supplier_expected_lead_time_days": selected["expected_lead_time_days"],
        "recommended_supplier_reliability_score": selected["supplier_reliability_score"],
        "recommended_supplier_risk_class": selected["supplier_risk_class"],
        "recommended_supplier_capacity_shortfall_flag": bool(selected["capacity_shortfall_flag"]),
        "recommended_supplier_order_acceptance_probability": selected["order_acceptance_probability"],
        "recommended_supplier_expedite_available": bool(selected["expedite_available"]),
        "recommended_supplier_split_delivery_available": bool(selected["split_delivery_available"]),
        "recommended_supplier_return_eligible": bool(selected["return_eligible"]),
        "selected_supplier_capacity_30d": selected["supplier_capacity_30d"],
        "selected_supplier_per_order_capacity": selected["supplier_per_order_capacity_units"],
        "selected_supplier_immediate_requirement_feasible_flag": bool(selected["immediate_requirement_feasible_flag"]),
        "selected_supplier_horizon_capacity_feasible_flag": bool(selected["horizon_capacity_feasible_flag"]),
        "balanced_supplier_score": selected["balanced_supplier_score"],
        "balanced_supplier_score_rank": selected["balanced_supplier_score_rank"],
        "balanced_supplier_selection_reason": selected["balanced_supplier_selection_reason"],
    }


def _strategy_consistency(
    selection: dict[str, object],
    current_supplier_id: str,
    selected: pd.Series | None,
) -> tuple[bool, str]:
    strategy = str(selection["recommended_supplier_strategy"])
    supplier_id = str(selection["recommended_supplier_id"])
    if strategy.startswith("REVIEW_"):
        return (not bool(selection["recommendation_execution_allowed"])), "Review-required strategy is non-executable."
    if selected is None:
        return False, "Recommended supplier does not exist in the SKU-supplier capability context."
    if bool(selection["recommendation_execution_allowed"]) and not bool(selected["feasible_supplier_option_flag"]):
        return False, "Executable recommendation selected an infeasible supplier option."
    if strategy in {"CURRENT_SUPPLIER", "EXPEDITE_CURRENT_SUPPLIER", "SPLIT_DELIVERY_CURRENT_SUPPLIER"}:
        if not current_supplier_id or supplier_id != current_supplier_id:
            return False, f"{strategy} requires recommended_supplier_id to equal current_supplier_id."
    if strategy == "EXPEDITE_CURRENT_SUPPLIER" or strategy == "EXPEDITE_ALTERNATIVE_SUPPLIER":
        if not _expedite_option_ok(selected):
            return False, "Expedite strategy requires available, eligible, capacity-feasible expedite with shorter lead time."
    if strategy == "SPLIT_DELIVERY_CURRENT_SUPPLIER" or strategy == "SPLIT_DELIVERY_ALTERNATIVE_SUPPLIER":
        if not _split_option_ok(selected):
            return False, "Split-delivery strategy requires available, eligible, feasible split delivery."
    return True, "Strategy label, supplier ID, and selected option are consistent."


def _expedite_option_ok(selected: pd.Series | None) -> bool:
    if selected is None:
        return False
    return bool(
        selected["expedite_available"]
        and selected["expedite_eligible"]
        and selected["expedite_capacity_feasible_flag"]
        and selected["expedite_lead_time_days"] < selected["standard_lead_time_days"]
        and selected["feasible_supplier_option_flag"]
    )


def _split_option_ok(selected: pd.Series | None) -> bool:
    if selected is None:
        return False
    return bool(
        selected["split_delivery_available"]
        and selected["split_delivery_eligible"]
        and selected["split_delivery_feasible_flag"]
        and selected["feasible_supplier_option_flag"]
    )


def _expedite_strategy_consistency(selection: dict[str, object], current_supplier_id: str, selected: pd.Series | None) -> bool:
    strategy = str(selection["recommended_supplier_strategy"])
    if not strategy.startswith("EXPEDITE_"):
        return True
    if strategy == "EXPEDITE_CURRENT_SUPPLIER" and selection["recommended_supplier_id"] != current_supplier_id:
        return False
    return _expedite_option_ok(selected)


def _split_strategy_consistency(selection: dict[str, object], current_supplier_id: str, selected: pd.Series | None) -> bool:
    strategy = str(selection["recommended_supplier_strategy"])
    if not strategy.startswith("SPLIT_DELIVERY_"):
        return True
    if strategy == "SPLIT_DELIVERY_CURRENT_SUPPLIER" and selection["recommended_supplier_id"] != current_supplier_id:
        return False
    return _split_option_ok(selected)


def _expedite_strategy_reason(selection: dict[str, object], current_supplier_id: str, selected: pd.Series | None) -> str:
    if not str(selection["recommended_supplier_strategy"]).startswith("EXPEDITE_"):
        return "No expedite strategy selected."
    if _expedite_strategy_consistency(selection, current_supplier_id, selected):
        return "Expedite strategy uses a feasible expedite-capable supplier option."
    return "Expedite strategy is inconsistent with current supplier or capability rules."


def _split_strategy_reason(selection: dict[str, object], current_supplier_id: str, selected: pd.Series | None) -> str:
    if not str(selection["recommended_supplier_strategy"]).startswith("SPLIT_DELIVERY_"):
        return "No split-delivery strategy selected."
    if _split_strategy_consistency(selection, current_supplier_id, selected):
        return "Split-delivery strategy uses a feasible split-capable supplier option."
    return "Split-delivery strategy is inconsistent with current supplier or capability rules."


def _supplier_switch_reason(strategy: str, switch_flag: bool) -> str:
    if not switch_flag:
        return "No supplier switch implied by strategy."
    if "ALTERNATIVE_SUPPLIER" in strategy:
        return "Strategy explicitly recommends an alternative feasible supplier."
    return "Supplier switch is implied by selected supplier and strategy label."


def _capacity_strategy_fields(
    options: pd.DataFrame,
    selection: dict[str, object],
    selected: pd.Series | None,
) -> dict[str, object]:
    strategy = str(selection["recommended_supplier_strategy"])
    selected_id = str(selection.get("recommended_supplier_id", ""))
    candidate_ids = str(_first_value(options, "split_sourcing_candidate_supplier_ids", ""))
    candidates = [value for value in candidate_ids.split(";") if value]
    return {
        "immediate_supplier_id": selected_id,
        "horizon_primary_supplier_id": candidates[0] if candidates else selected_id,
        "horizon_backup_supplier_id": candidates[1] if len(candidates) > 1 else "",
        "split_sourcing_required_flag": strategy == "SPLIT_SOURCING_CAPACITY_PLAN",
        "recurring_orders_required_flag": strategy in {"RECURRING_ORDER_PLAN", "IMMEDIATE_ORDER_WITH_HORIZON_REVIEW"},
        "capacity_strategy_reason": _capacity_strategy_reason(options, selection, selected),
        "capacity_review_required": strategy in {
            "SPLIT_SOURCING_CAPACITY_PLAN",
            "IMMEDIATE_ORDER_WITH_HORIZON_REVIEW",
            "REVIEW_SPLIT_SOURCING_PLAN",
            "REVIEW_AGGREGATE_CAPACITY_SHORTFALL",
        },
    }


def _capacity_strategy_reason(options: pd.DataFrame, selection: dict[str, object], selected: pd.Series | None) -> str:
    strategy = str(selection["recommended_supplier_strategy"])
    if strategy == "SPLIT_SOURCING_CAPACITY_PLAN":
        return "No single supplier needs to cover the full horizon; aggregate supplier capacity can cover the provisional requirement."
    if strategy == "IMMEDIATE_ORDER_WITH_HORIZON_REVIEW":
        return "Selected supplier can cover immediate lead-time demand, but full-horizon capacity requires review."
    if strategy == "REVIEW_SPLIT_SOURCING_PLAN":
        return "Aggregate capacity appears feasible but no immediate executable supplier was found."
    if strategy == "REVIEW_AGGREGATE_CAPACITY_SHORTFALL":
        return "Aggregate supplier capacity is below provisional net requirement."
    if selected is not None and bool(selected.get("horizon_capacity_feasible_flag", False)):
        return "Selected supplier can cover immediate and horizon requirement."
    return "Capacity strategy follows selected supplier feasibility."


def _expedite_selection_reason(strategy: str, backorder_risk: str) -> str:
    if strategy == "EXPEDITE_CURRENT_SUPPLIER":
        return f"{backorder_risk.lower()} backorder risk supports expediting with the current feasible supplier."
    return f"{backorder_risk.lower()} backorder risk supports expediting with an alternative feasible supplier."


def _strategy_warnings(options: pd.DataFrame) -> str:
    warnings = set()
    for value in options.get("procurement_warning_codes", pd.Series(dtype=str)).astype(str):
        warnings.update(code for code in value.split(";") if code and code != "NONE")
    return ";".join(sorted(warnings)) if warnings else "NONE"


def _warning_scopes(
    options: pd.DataFrame,
    selected: pd.Series | None,
    selection: dict[str, object],
) -> dict[str, object]:
    """Separate selected supplier warnings from pool and review-candidate warnings."""
    selected_warnings = _option_warnings(selected, selection["recommended_supplier_strategy"])
    pool_warnings = _strategy_warnings(options)
    review_candidate = _selected_option(options, selection.get("review_candidate_supplier_id", ""))
    review_warnings = _option_warnings(review_candidate, "REVIEW_CANDIDATE")
    demand_warnings = str(_first_value(options, "phase1_demand_warning_codes", "NONE"))
    strategy_warnings = str(selection.get("recommendation_blocking_reason", "NONE"))
    demand_strategy = str(_first_value(options, "demand_strategy_warning_codes", "NONE"))
    if strategy_warnings == "NONE" and demand_strategy != "NONE":
        strategy_warnings = demand_strategy
    consolidated = _join_codes(
        [
            _prefix_codes("SELECTED", selected_warnings),
            _prefix_codes("POOL_INFO", pool_warnings),
            _prefix_codes("REVIEW_CANDIDATE", review_warnings),
            _prefix_codes("DEMAND", demand_warnings),
            _prefix_codes("STRATEGY", strategy_warnings),
        ]
    )
    selected_capacity_shortfall = bool(selected is not None and selected.get("capacity_shortfall_flag", False))
    selected_split_feasible = bool(selected is not None and selected.get("split_delivery_feasible_flag", False))
    selected_expedite_feasible = bool(selected is not None and selected.get("expedite_capacity_feasible_flag", False))
    scope_ok, scope_reason = _selected_scope_consistency(
        selected_warnings,
        str(selection["recommended_supplier_strategy"]),
        selected_capacity_shortfall,
    )
    return {
        "selected_option_warning_codes": selected_warnings,
        "sku_option_pool_warning_codes": pool_warnings,
        "review_candidate_warning_codes": review_warnings,
        "demand_context_warning_codes": demand_warnings,
        "strategy_warning_codes": strategy_warnings,
        "consolidated_manager_warning_codes": consolidated,
        "selected_option_capacity_shortfall_flag": selected_capacity_shortfall,
        "selected_option_split_delivery_feasible_flag": selected_split_feasible,
        "selected_option_expedite_capacity_feasible_flag": selected_expedite_feasible,
        "selected_option_has_blocking_warning": _has_blocking_warning(selected_warnings),
        "selected_option_warning_scope_consistency_flag": scope_ok,
        "selected_option_warning_scope_reason": scope_reason,
    }


def _option_warnings(option: pd.Series | None, strategy: str) -> str:
    if option is None:
        return "NONE"
    warnings = set()
    for value in [
        str(option.get("procurement_warning_codes", "NONE")),
        str(option.get("infeasibility_reasons", "NONE")),
    ]:
        warnings.update(code for code in value.split(";") if code and code != "NONE")
    if "CAPACITY_SHORTFALL" in warnings and not bool(option.get("capacity_shortfall_flag", False)):
        warnings.discard("CAPACITY_SHORTFALL")
    if (
        "WAREHOUSE_CAPACITY_REVIEW_REQUIRED_FOR_SPLIT_DELIVERY" in warnings
        and not str(strategy).startswith("SPLIT_DELIVERY_")
    ):
        warnings.discard("WAREHOUSE_CAPACITY_REVIEW_REQUIRED_FOR_SPLIT_DELIVERY")
    return ";".join(sorted(warnings)) if warnings else "NONE"


def _selected_scope_consistency(warnings: str, strategy: str, capacity_shortfall: bool) -> tuple[bool, str]:
    codes = set(code for code in str(warnings).split(";") if code and code != "NONE")
    if "CAPACITY_SHORTFALL" in codes and not capacity_shortfall:
        return False, "Selected option warning includes capacity shortfall but selected option has no capacity shortfall."
    if "WAREHOUSE_CAPACITY_REVIEW_REQUIRED_FOR_SPLIT_DELIVERY" in codes and not strategy.startswith("SPLIT_DELIVERY_"):
        return False, "Selected option warning includes split-delivery warehouse warning but selected strategy is not split delivery."
    return True, "Selected option warnings match selected supplier and strategy scope."


def _has_blocking_warning(warnings: str) -> bool:
    blocking = {"CAPACITY_SHORTFALL", "BASE_SUPPLIER_OPTION_INFEASIBLE", "LOW_ORDER_ACCEPTANCE_PROBABILITY"}
    codes = set(code for code in str(warnings).split(";") if code)
    return bool(codes & blocking)


def _prefix_codes(prefix: str, codes: str) -> str:
    if not codes or codes == "NONE":
        return ""
    return ";".join(f"{prefix}:{code}" for code in str(codes).split(";") if code and code != "NONE")


def _join_codes(values: list[str]) -> str:
    codes = []
    for value in values:
        codes.extend(code for code in str(value).split(";") if code)
    return ";".join(dict.fromkeys(codes)) if codes else "NONE"


def _first_value(options: pd.DataFrame, column: str, default):
    if options.empty or column not in options.columns:
        return default
    values = options[column].dropna()
    return default if values.empty else values.iloc[0]


def _demand_driven_strategy_flag(options: pd.DataFrame, selection: dict[str, object]) -> bool:
    if _demand_review_required(options):
        return True
    return str(selection["recommended_supplier_strategy"]).startswith(("EXPEDITE_", "SPLIT_DELIVERY_"))


def _demand_review_required(options: pd.DataFrame) -> bool:
    return bool(
        _to_bool_series(pd.Series([_first_value(options, "stockout_censored_demand_flag", False)])).iloc[0]
        or _to_bool_series(pd.Series([_first_value(options, "underforecast_risk_flag", False)])).iloc[0]
        or _to_bool_series(pd.Series([_first_value(options, "high_uncertainty_flag", False)])).iloc[0]
        or _to_bool_series(pd.Series([_first_value(options, "upcoming_event_flag", False)])).iloc[0]
        or float(_first_value(options, "demand_urgency_score", 0.0)) >= 70
    )


def _demand_driven_strategy_reason(options: pd.DataFrame, selection: dict[str, object]) -> str:
    reasons = []
    if float(_first_value(options, "demand_urgency_score", 0.0)) >= 70:
        reasons.append("high demand urgency")
    if _first_value(options, "forecast_uncertainty_level", "UNKNOWN") == "HIGH":
        reasons.append("high forecast uncertainty")
    if _to_bool_series(pd.Series([_first_value(options, "stockout_censored_demand_flag", False)])).iloc[0]:
        reasons.append("possible stockout-censored demand")
    if _to_bool_series(pd.Series([_first_value(options, "underforecast_risk_flag", False)])).iloc[0]:
        reasons.append("underforecast risk")
    if _to_bool_series(pd.Series([_first_value(options, "upcoming_event_flag", False)])).iloc[0]:
        reasons.append("upcoming event demand pressure")
    if not reasons:
        return "No strong Phase 1 demand signal changed the supplier strategy."
    return "Demand context influenced strategy through " + ", ".join(reasons) + "."


def _best_by(options: pd.DataFrame, column: str, ascending: bool) -> str:
    if options.empty or column not in options.columns:
        return ""
    ranked = options.sort_values(column, ascending=ascending)
    return str(ranked.iloc[0]["supplier_id"]) if not ranked.empty else ""


def _normalize_lower_is_better(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0)
    minimum = values.min()
    maximum = values.max()
    if pd.isna(minimum) or pd.isna(maximum) or maximum == minimum:
        return pd.Series(1.0, index=series.index)
    return 1 - ((values - minimum) / (maximum - minimum))


def _first_or_blank(options: pd.DataFrame, column: str) -> str:
    return str(options.iloc[0][column]) if not options.empty and column in options.columns else ""


def _risk_class(score: float) -> str:
    if score < 0.25:
        return "LOW"
    if score < 0.50:
        return "MEDIUM"
    return "HIGH"


def _to_bool_series(series: pd.Series) -> pd.Series:
    normalized = series.where(series.notna(), False)
    if normalized.dtype == bool:
        return normalized
    return normalized.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y", "t"})


def _capability_columns() -> list[str]:
    return [
        "sku_id",
        "supplier_id",
        "supplier_name",
        "phase1_context_source",
        "demand_profile",
        "demand_variability_class",
        "forecast_demand_7d",
        "forecast_demand_30d",
        "forecast_demand_60d",
        "forecast_demand_90d",
        "demand_urgency_score",
        "demand_pressure_7d",
        "demand_pressure_30d",
        "forecast_confidence_band",
        "forecast_uncertainty_level",
        "high_uncertainty_flag",
        "underforecast_risk_flag",
        "overforecast_risk_flag",
        "stockout_censored_demand_flag",
        "lost_sales_estimate_30d",
        "adjusted_demand_30d",
        "upcoming_event_flag",
        "seasonal_phase",
        "demand_data_quality_score",
        "phase1_demand_warning_codes",
        "demand_integration_notes",
        "gross_forecast_demand_7d",
        "gross_forecast_demand_30d",
        "gross_forecast_demand_60d",
        "gross_forecast_demand_90d",
        "active_backorder_units",
        "backorder_requirement_units",
        "usable_on_hand_inventory_units",
        "confirmed_inbound_units",
        "open_po_confirmed_units_7d",
        "open_po_confirmed_units_30d",
        "open_po_confirmed_units_60d",
        "open_po_confirmed_units_90d",
        "expected_receipts_within_horizon_units",
        "uncertain_inbound_units",
        "provisional_buffer_requirement_units",
        "gross_procurement_requirement_units",
        "provisional_net_procurement_requirement_units",
        "immediate_procurement_requirement_units",
        "remaining_horizon_requirement_units",
        "inventory_deduction_available_flag",
        "inbound_deduction_available_flag",
        "net_requirement_is_provisional_flag",
        "procurement_requirement_method",
        "buffer_requirement_source",
        "inventory_context_missing_warning",
        "lead_time_demand_units",
        "confirmed_inbound_before_expected_arrival_units",
        "immediate_requirement_basis",
        "procurement_requirement_warning_codes",
        "immediate_requirement_warning_codes",
        "unit_price",
        "effective_unit_price",
        "applicable_price_break_quantity",
        "landed_cost_per_unit",
        "estimated_freight_cost",
        "estimated_handling_cost",
        "estimated_insurance_cost",
        "estimated_customs_cost",
        "minimum_order_value",
        "payment_terms_days",
        "standard_lead_time_days",
        "expected_lead_time_days",
        "lead_time_std_days",
        "delay_probability",
        "expedite_available",
        "expedite_eligible",
        "expedite_lead_time_days",
        "expedite_total_cost_estimate",
        "expedite_lead_time_reduction_days",
        "expedite_capacity_feasible_flag",
        "expedite_recommended_flag",
        "defect_rate",
        "yield_rate",
        "expected_defect_units",
        "expected_quality_loss_cost",
        "quality_adjusted_unit_cost",
        "supplier_sku_available_capacity",
        "supplier_capacity_period_unit",
        "supplier_capacity_period_days",
        "supplier_sku_capacity_period_unit",
        "supplier_sku_capacity_period_days",
        "supplier_capacity_per_day",
        "supplier_capacity_7d",
        "supplier_capacity_30d",
        "supplier_capacity_60d",
        "supplier_capacity_90d",
        "supplier_horizon_capacity_units",
        "supplier_per_order_capacity_units",
        "supplier_effective_horizon_capacity_units",
        "capacity_source",
        "capacity_normalization_method",
        "capacity_utilization",
        "capacity_shortfall_flag",
        "order_acceptance_probability",
        "return_eligible",
        "accepts_returns",
        "return_window_days",
        "return_deduction_rate",
        "return_shipping_cost",
        "expected_return_recovery_rate",
        "expected_return_recovery_value",
        "near_expiry_return_possible",
        "expired_return_possible",
        "split_delivery_eligible",
        "split_delivery_available",
        "minimum_split_quantity",
        "maximum_split_shipments",
        "first_shipment_lead_time_days",
        "remaining_shipment_lead_time_days",
        "split_delivery_feasible_flag",
        "first_shipment_quantity",
        "remaining_shipment_quantity",
        "expected_first_shipment_date",
        "expected_final_shipment_date",
        "split_delivery_cost_estimate",
        "split_delivery_recommended_flag",
        "partial_delivery_reliability",
        "total_remaining_backorder_units",
        "oldest_backorder_age_days",
        "backorder_risk_level",
        "backorder_pressure_flag",
        "recommended_backorder_strategy",
        "supplier_reliability_score",
        "supplier_risk_score",
        "supplier_risk_class",
        "demand_risk_component",
        "supplier_risk_component",
        "backorder_risk_component",
        "capacity_risk_component",
        "event_risk_component",
        "total_demand_adjusted_risk_score",
        "demand_adjusted_procurement_risk_score",
        "demand_adjusted_procurement_risk_class",
        "demand_strategy_warning_codes",
        "watchlist_flag",
        "preferred_supplier_flag",
        "backup_supplier_flag",
        "supplier_option_active_flag",
        "base_supplier_feasible_flag",
        "commercial_feasible_flag",
        "supplier_active_feasible_flag",
        "quality_feasible_flag",
        "per_order_capacity_feasible_flag",
        "immediate_requirement_feasible_flag",
        "horizon_capacity_feasible_flag",
        "net_requirement_feasible_flag",
        "final_executable_supplier_option_flag",
        "feasible_supplier_option_flag",
        "raw_immediate_order_quantity",
        "yield_adjusted_immediate_order_quantity",
        "moq_adjusted_immediate_order_quantity",
        "batch_rounded_immediate_order_quantity",
        "final_immediate_order_quantity",
        "estimated_order_cycle_count",
        "average_order_quantity_per_cycle",
        "planned_order_frequency_days",
        "estimated_immediate_procurement_cost",
        "estimated_horizon_procurement_cost",
        "estimated_order_cycle_cost",
        "estimated_total_fixed_order_cost_over_horizon",
        "estimated_total_delivery_cost_over_horizon",
        "total_available_supplier_capacity_30d",
        "total_available_supplier_capacity_horizon",
        "aggregate_capacity_shortfall_units",
        "aggregate_capacity_feasible_flag",
        "minimum_supplier_count_required",
        "split_sourcing_capacity_feasible_flag",
        "split_sourcing_candidate_supplier_ids",
        "split_sourcing_candidate_capacities",
        "split_sourcing_allocation_plan",
        "split_sourcing_review_required",
        "balanced_supplier_score",
        "balanced_supplier_score_rank",
        "balanced_supplier_selection_reason",
        "infeasibility_reasons",
        "procurement_warning_codes",
        "requirement_warning_codes",
        "capacity_warning_codes",
        "capacity_time_basis_warning_codes",
        "downstream_planning_notes",
    ]
