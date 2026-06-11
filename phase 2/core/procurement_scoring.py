"""Supplier-SKU scoring and procurement recommendations."""

from pathlib import Path

import pandas as pd

from config import (
    DATE_FORMAT,
    DEMAND_ADJUSTED_RISK_WEIGHTS,
    PROCUREMENT_RISK_THRESHOLDS,
    SPLIT_SOURCING_THRESHOLDS,
    SUPPLIER_EVIDENCE_ADJUSTMENTS,
    SUPPLIER_SCORE_CLOSE_THRESHOLD,
    SUPPLIER_SELECTION_WEIGHTS,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PHASE3_REQUIREMENT_BRIDGE_FILE = PROJECT_ROOT / "shared" / "outputs" / "phase3_procurement_requirement_context.csv"


def build_supplier_sku_scores(
    supplier_sku: pd.DataFrame,
    supplier_performance: pd.DataFrame,
    demand_context: pd.DataFrame | None = None,
    suppliers: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Create normalized supplier scores for each SKU."""
    scored = supplier_sku.merge(
        supplier_performance[
            [
                "supplier_id",
                "calculated_reliability_score",
                "performance_data_status",
                "supplier_trend_status",
                "supplier_watchlist_flag",
                "supplier_watchlist_reason",
            ]
        ],
        on="supplier_id",
        how="left",
    )
    scored = _merge_supplier_status(scored, suppliers)
    phase3_requirement = _load_phase3_requirement_context()
    scored = _merge_phase3_requirement_context(scored, phase3_requirement)
    scored["calculated_reliability_score"] = scored["calculated_reliability_score"].fillna(0.65)
    scored["supplier_history_status"] = scored["performance_data_status"].fillna("NO_HISTORY")
    scored["supplier_trend_status"] = scored["supplier_trend_status"].fillna("INSUFFICIENT_DATA")
    scored["supplier_watchlist_flag"] = _to_bool_series(scored["supplier_watchlist_flag"])
    scored["supplier_watchlist_reason"] = scored["supplier_watchlist_reason"].fillna(
        "Insufficient recent or baseline data for trend detection."
    )
    scored = _add_supplier_evidence_fields(scored)
    scored["procurement_risk_score"] = _calculate_procurement_risk(scored)
    scored = _merge_demand_context(scored, demand_context)
    scored = _add_demand_adjusted_risk(scored)
    scored = _add_feasibility_fields(scored)
    scored = _add_procurement_cost_estimates(scored)

    scored_frames = []
    for _, sku_options in scored.groupby("sku_id", sort=True):
        normalized = sku_options.copy()
        normalized["normalized_total_cost_score"] = _normalize_lower_is_better(
            normalized["estimated_total_procurement_cost"]
        )
        normalized["cost_score_basis"] = "estimated_total_procurement_cost"
        normalized["cost_score"] = normalized["normalized_total_cost_score"]
        normalized["reliability_score"] = normalized["calculated_reliability_score"].clip(0, 1)
        normalized["lead_time_score"] = _normalize_lower_is_better(normalized["lead_time_mean_days"])
        normalized["quality_score"] = (0.70 * normalized["yield_rate"] + 0.30 * (1 - normalized["defect_rate"])).clip(0, 1)
        normalized["risk_score"] = (1 - normalized["procurement_risk_score"]).clip(0, 1)
        normalized["supplier_score"] = (
            SUPPLIER_SELECTION_WEIGHTS["cost"] * normalized["cost_score"]
            + SUPPLIER_SELECTION_WEIGHTS["reliability"] * normalized["reliability_score"]
            + SUPPLIER_SELECTION_WEIGHTS["lead_time"] * normalized["lead_time_score"]
            + SUPPLIER_SELECTION_WEIGHTS["quality"] * normalized["quality_score"]
            + SUPPLIER_SELECTION_WEIGHTS["risk"] * normalized["risk_score"]
        )
        normalized["demand_context_adjustment"] = _demand_context_adjustment(normalized)
        normalized["supplier_trend_adjustment"] = _supplier_trend_adjustment(normalized)
        normalized["adjusted_supplier_score"] = (
            normalized["supplier_score"]
            + normalized["demand_context_adjustment"]
            + normalized["supplier_trend_adjustment"]
        ).clip(0, 1)
        scored_frames.append(normalized)

    result = pd.concat(scored_frames, ignore_index=True) if scored_frames else pd.DataFrame()
    result["procurement_risk_class"] = result["procurement_risk_score"].apply(_risk_class)
    return result[
        [
            "sku_id",
            "supplier_id",
            "unit_cost",
            "moq",
            "batch_size",
            "lead_time_mean_days",
            "lead_time_std_days",
            "yield_rate",
            "defect_rate",
            "delay_probability",
            "partial_delivery_rate",
            "fixed_order_cost",
            "delivery_cost",
            "cost_per_late_day",
            "partial_delivery_penalty",
            "quality_rejection_cost_per_unit",
            "supplier_history_status",
            "supplier_trend_status",
            "supplier_watchlist_flag",
            "supplier_watchlist_reason",
            "supplier_evidence_status",
            "supplier_evidence_warning",
            "supplier_requires_review",
            "reference_order_quantity",
            "estimated_product_cost",
            "estimated_fixed_order_cost",
            "estimated_delivery_cost",
            "estimated_expected_delay_cost",
            "estimated_expected_partial_delivery_cost",
            "estimated_expected_quality_cost",
            "estimated_total_procurement_cost",
            "cost_score_basis",
            "normalized_total_cost_score",
            "demand_behavior_class",
            "zero_demand_ratio",
            "coefficient_of_variation",
            "event_affected_ratio",
            "data_sufficiency_class",
            "champion_model",
            "champion_confidence_score",
            "champion_risk_level",
            "average_p50_forecast",
            "average_p90_forecast",
            "average_forecast_confidence_score",
            "dominant_forecast_risk_level",
            "demand_context_status",
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
            "demand_risk_component",
            "supplier_risk_component",
            "backorder_risk_component",
            "capacity_risk_component",
            "event_risk_component",
            "total_demand_adjusted_risk_score",
            "demand_strategy_warning_codes",
            "demand_adjusted_procurement_risk_score",
            "demand_adjusted_procurement_risk_class",
            "demand_context_adjustment",
            "supplier_trend_adjustment",
            "reference_usable_quantity",
            "reference_quantity_source",
            "requirement_input_mode",
            "phase3_requirement_loaded_flag",
            "phase3_requirement_schema_version",
            "authoritative_requested_quantity_units",
            "fallback_quantity_used_flag",
            "fallback_quantity_reason",
            "yield_adjusted_order_quantity",
            "batch_rounded_order_quantity",
            "moq_adjusted_order_quantity",
            "final_feasible_order_quantity",
            "is_supplier_active",
            "is_feasible_supplier_option",
            "feasibility_warning",
            "feasibility_reason",
            "supplier_score",
            "adjusted_supplier_score",
            "procurement_risk_score",
            "procurement_risk_class",
        ]
    ]


def build_procurement_recommendations(
    supplier_sku_scores: pd.DataFrame,
    purchase_orders: pd.DataFrame,
) -> pd.DataFrame:
    """Select primary and backup suppliers with split-sourcing guidance."""
    reference_date = _reference_date(purchase_orders)
    rows = []
    for sku_id, sku_scores in supplier_sku_scores.groupby("sku_id", sort=True):
        candidate_scores, all_options_infeasible = _recommendation_candidates(sku_scores)
        ranked = _rank_recommendation_candidates(candidate_scores, all_options_infeasible)
        primary = ranked.iloc[0]
        backup = ranked.iloc[1] if len(ranked) > 1 else None
        split_recommended, primary_share, backup_share, reason = _split_sourcing_decision(primary, backup)
        selection_reason = _selection_reason_with_demand_context(primary, reason, all_options_infeasible)
        expected_arrival = reference_date + pd.Timedelta(days=int(round(primary["lead_time_mean_days"])))
        rows.append(
            {
                "sku_id": sku_id,
                "recommended_supplier_id": primary["supplier_id"],
                "backup_supplier_id": backup["supplier_id"] if backup is not None else "",
                "recommended_supplier_feasible": primary["is_feasible_supplier_option"],
                "backup_supplier_feasible": backup["is_feasible_supplier_option"] if backup is not None else False,
                "recommended_supplier_history_status": primary["supplier_history_status"],
                "backup_supplier_history_status": backup["supplier_history_status"] if backup is not None else "",
                "supplier_trend_status": primary["supplier_trend_status"],
                "supplier_watchlist_flag": _to_bool_value(primary["supplier_watchlist_flag"]),
                "supplier_watchlist_reason": primary["supplier_watchlist_reason"],
                "recommended_supplier_evidence_status": primary["supplier_evidence_status"],
                "recommended_supplier_evidence_warning": primary["supplier_evidence_warning"],
                "recommended_supplier_requires_review": _to_bool_value(primary["supplier_requires_review"]),
                "backup_supplier_evidence_status": backup["supplier_evidence_status"] if backup is not None else "",
                "backup_supplier_evidence_warning": backup["supplier_evidence_warning"] if backup is not None else "",
                "backup_supplier_requires_review": (
                    _to_bool_value(backup["supplier_requires_review"]) if backup is not None else False
                ),
                "expected_lead_time_days": primary["lead_time_mean_days"],
                "expected_arrival_date": expected_arrival.strftime(DATE_FORMAT),
                "unit_cost": primary["unit_cost"],
                "moq": primary["moq"],
                "batch_size": primary["batch_size"],
                "expected_yield_rate": primary["yield_rate"],
                "final_feasible_order_quantity": primary["final_feasible_order_quantity"],
                "feasibility_warning": primary["feasibility_warning"],
                "feasibility_reason": primary["feasibility_reason"],
                "cost_score_basis": primary["cost_score_basis"],
                "normalized_total_cost_score": primary["normalized_total_cost_score"],
                "demand_behavior_class": primary["demand_behavior_class"],
                "champion_confidence_score": primary["champion_confidence_score"],
                "champion_risk_level": primary["champion_risk_level"],
                "average_p50_forecast": primary["average_p50_forecast"],
                "average_p90_forecast": primary["average_p90_forecast"],
                "demand_adjusted_procurement_risk_score": primary["demand_adjusted_procurement_risk_score"],
                "demand_adjusted_procurement_risk_class": primary["demand_adjusted_procurement_risk_class"],
                "demand_context_status": primary["demand_context_status"],
                "adjusted_supplier_score": primary["adjusted_supplier_score"],
                "estimated_total_procurement_cost": primary["estimated_total_procurement_cost"],
                "estimated_product_cost": primary["estimated_product_cost"],
                "estimated_fixed_order_cost": primary["estimated_fixed_order_cost"],
                "estimated_delivery_cost": primary["estimated_delivery_cost"],
                "estimated_expected_delay_cost": primary["estimated_expected_delay_cost"],
                "estimated_expected_partial_delivery_cost": primary["estimated_expected_partial_delivery_cost"],
                "estimated_expected_quality_cost": primary["estimated_expected_quality_cost"],
                "reference_order_quantity": primary["reference_order_quantity"],
                "procurement_risk_score": primary["procurement_risk_score"],
                "procurement_risk_class": primary["procurement_risk_class"],
                "split_sourcing_recommendation": split_recommended,
                "recommended_primary_share": primary_share,
                "recommended_backup_share": backup_share,
                "selection_reason": selection_reason,
            }
        )
    return pd.DataFrame(rows)


def _calculate_procurement_risk(df: pd.DataFrame) -> pd.Series:
    """Calculate procurement risk from lead time, delay, quality, and reliability."""
    lead_time_std_risk = (df["lead_time_std_days"] / 10).clip(0, 1)
    defect_risk = df["defect_rate"].clip(0, 1)
    low_yield_risk = (1 - df["yield_rate"].clip(0, 1))
    reliability_risk = (1 - df["calculated_reliability_score"].clip(0, 1))
    return (
        0.22 * lead_time_std_risk
        + 0.22 * df["delay_probability"].clip(0, 1)
        + 0.16 * df["partial_delivery_rate"].clip(0, 1)
        + 0.15 * defect_risk
        + 0.10 * low_yield_risk
        + 0.15 * reliability_risk
    ).clip(0, 1)


def _add_procurement_cost_estimates(df: pd.DataFrame) -> pd.DataFrame:
    """Add preliminary MOQ-based procurement cost estimates."""
    enriched = df.copy()
    enriched["reference_order_quantity"] = enriched["final_feasible_order_quantity"]
    enriched["estimated_product_cost"] = enriched["unit_cost"] * enriched["reference_order_quantity"]
    enriched["estimated_fixed_order_cost"] = enriched["fixed_order_cost"]
    enriched["estimated_delivery_cost"] = enriched["delivery_cost"]
    enriched["estimated_expected_delay_cost"] = (
        enriched["delay_probability"] * enriched["lead_time_std_days"] * enriched["cost_per_late_day"]
    )
    enriched["estimated_expected_partial_delivery_cost"] = (
        enriched["partial_delivery_rate"] * enriched["partial_delivery_penalty"]
    )
    enriched["estimated_expected_quality_cost"] = (
        enriched["reference_order_quantity"] * enriched["defect_rate"] * enriched["quality_rejection_cost_per_unit"]
    )
    enriched["estimated_total_procurement_cost"] = (
        enriched["estimated_product_cost"]
        + enriched["estimated_fixed_order_cost"]
        + enriched["estimated_delivery_cost"]
        + enriched["estimated_expected_delay_cost"]
        + enriched["estimated_expected_partial_delivery_cost"]
        + enriched["estimated_expected_quality_cost"]
    )
    return enriched


def _load_phase3_requirement_context() -> pd.DataFrame:
    """Load the authoritative Phase 3 requirement bridge when present."""
    if not PHASE3_REQUIREMENT_BRIDGE_FILE.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(PHASE3_REQUIREMENT_BRIDGE_FILE)
    except Exception:
        return pd.DataFrame()


def _merge_phase3_requirement_context(scored: pd.DataFrame, requirement: pd.DataFrame) -> pd.DataFrame:
    """Attach Phase 3 net requirement fields without making them mandatory."""
    if requirement.empty or "sku_id" not in requirement.columns:
        scored = scored.copy()
        scored["authoritative_requested_quantity_units"] = 0.0
        scored["phase3_requirement_schema_version"] = ""
        return scored
    columns = ["sku_id", "schema_version", "net_replenishment_requirement_units"]
    available = [column for column in columns if column in requirement.columns]
    source = requirement[available].drop_duplicates("sku_id").rename(
        columns={
            "schema_version": "phase3_requirement_schema_version",
            "net_replenishment_requirement_units": "authoritative_requested_quantity_units",
        }
    )
    merged = scored.merge(source, on="sku_id", how="left")
    merged["authoritative_requested_quantity_units"] = pd.to_numeric(
        merged.get("authoritative_requested_quantity_units", 0),
        errors="coerce",
    ).fillna(0)
    if "phase3_requirement_schema_version" not in merged.columns:
        merged["phase3_requirement_schema_version"] = ""
    merged["phase3_requirement_schema_version"] = merged["phase3_requirement_schema_version"].fillna("")
    return merged


def _merge_supplier_status(df: pd.DataFrame, suppliers: pd.DataFrame | None) -> pd.DataFrame:
    """Merge supplier active/inactive status when supplier master data is available."""
    enriched = df.copy()
    if suppliers is not None and not suppliers.empty and {"supplier_id", "status"}.issubset(suppliers.columns):
        supplier_status = suppliers[["supplier_id", "status"]].drop_duplicates("supplier_id")
        enriched = enriched.merge(supplier_status, on="supplier_id", how="left")
    if "status" not in enriched.columns:
        enriched["status"] = "active"
    enriched["status"] = enriched["status"].fillna("inactive").astype(str).str.lower()
    return enriched


def _merge_demand_context(df: pd.DataFrame, demand_context: pd.DataFrame | None) -> pd.DataFrame:
    """Merge Phase 1 SKU demand context or fill fallback values."""
    enriched = df.copy()
    if demand_context is not None and not demand_context.empty:
        enriched = enriched.merge(demand_context, on="sku_id", how="left")

    defaults = {
        "demand_behavior_class": "UNKNOWN",
        "demand_profile": "UNKNOWN",
        "demand_variability_class": "UNKNOWN",
        "zero_demand_ratio": 0.0,
        "coefficient_of_variation": 0.0,
        "event_affected_ratio": 0.0,
        "data_sufficiency_class": "UNKNOWN",
        "phase1_context_source": "INTERNAL_FALLBACK",
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
        "demand_integration_notes": "",
        "champion_model": "UNKNOWN",
        "champion_confidence_score": 0.50,
        "champion_risk_level": "MEDIUM_RISK",
        "average_p50_forecast": pd.NA,
        "average_p90_forecast": pd.NA,
        "average_forecast_confidence_score": 0.50,
        "dominant_forecast_risk_level": "MEDIUM_RISK",
        "demand_context_status": "MISSING_PHASE1_CONTEXT",
    }
    for column, default_value in defaults.items():
        if column not in enriched.columns:
            enriched[column] = default_value
        else:
            enriched[column] = enriched[column].fillna(default_value)

    return enriched


def _add_supplier_evidence_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Add evidence status and review flags for supplier history/trend confidence."""
    enriched = df.copy()
    no_history = enriched["supplier_history_status"].astype(str).eq("NO_HISTORY")
    insufficient_trend = enriched["supplier_trend_status"].astype(str).eq("INSUFFICIENT_DATA")
    watchlist = _to_bool_series(enriched["supplier_watchlist_flag"])
    enriched["supplier_watchlist_flag"] = watchlist

    enriched["supplier_evidence_status"] = "STRONG_HISTORY"
    enriched.loc[insufficient_trend & ~no_history, "supplier_evidence_status"] = "LIMITED_HISTORY"
    enriched.loc[no_history, "supplier_evidence_status"] = "NO_HISTORY"

    enriched["supplier_evidence_warning"] = "NONE"
    enriched.loc[insufficient_trend & ~no_history, "supplier_evidence_warning"] = "LIMITED_TREND_DATA"
    enriched.loc[no_history & ~insufficient_trend, "supplier_evidence_warning"] = "NO_SUPPLIER_HISTORY"
    enriched.loc[watchlist, "supplier_evidence_warning"] = "WATCHLIST_SUPPLIER"
    enriched.loc[no_history & insufficient_trend, "supplier_evidence_warning"] = (
        "NO_HISTORY_AND_INSUFFICIENT_TREND_DATA"
    )
    enriched["supplier_requires_review"] = enriched["supplier_evidence_status"].eq("NO_HISTORY") | watchlist
    return enriched


def _add_feasibility_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate supplier feasibility and constraint-aware temporary quantities."""
    enriched = df.copy()
    reference = enriched.apply(_reference_quantity, axis=1, result_type="expand")
    for column in [
        "reference_usable_quantity",
        "reference_quantity_source",
        "requirement_input_mode",
        "phase3_requirement_loaded_flag",
        "phase3_requirement_schema_version",
        "authoritative_requested_quantity_units",
        "fallback_quantity_used_flag",
        "fallback_quantity_reason",
    ]:
        enriched[column] = reference[column]
    enriched["yield_adjusted_order_quantity"] = enriched["reference_usable_quantity"] / enriched["yield_rate"].where(
        enriched["yield_rate"] > 0
    )
    enriched["batch_rounded_order_quantity"] = enriched.apply(_round_up_to_batch, axis=1)
    enriched["moq_adjusted_order_quantity"] = enriched[["batch_rounded_order_quantity", "moq"]].max(axis=1)
    enriched["final_feasible_order_quantity"] = enriched["moq_adjusted_order_quantity"]
    enriched["is_supplier_active"] = enriched["status"].eq("active")
    enriched["is_feasible_supplier_option"] = enriched.apply(_is_feasible_supplier_option, axis=1)
    warnings = enriched.apply(_feasibility_warnings, axis=1)
    enriched["feasibility_warning"] = warnings.apply(lambda values: ";".join(values) if values else "NONE")
    enriched["feasibility_reason"] = warnings.apply(_feasibility_reason)
    return enriched


def _reference_quantity(row: pd.Series) -> pd.Series:
    """Choose temporary usable quantity from Phase 1 forecast context or MOQ fallback."""
    authoritative = pd.to_numeric(pd.Series([row.get("authoritative_requested_quantity_units")]), errors="coerce").iloc[0]
    schema_version = str(row.get("phase3_requirement_schema_version", "") or "")
    if pd.notna(authoritative) and authoritative > 0:
        return pd.Series(
            {
                "reference_usable_quantity": float(authoritative),
                "reference_quantity_source": "PHASE3_NET_REPLENISHMENT_REQUIREMENT",
                "requirement_input_mode": "AUTHORITATIVE_PHASE3_REQUIREMENT",
                "phase3_requirement_loaded_flag": True,
                "phase3_requirement_schema_version": schema_version,
                "authoritative_requested_quantity_units": float(authoritative),
                "fallback_quantity_used_flag": False,
                "fallback_quantity_reason": "NONE",
            }
        )
    avg_daily = pd.to_numeric(pd.Series([row.get("average_daily_forecast_demand_30d")]), errors="coerce").iloc[0]
    lead_time = pd.to_numeric(pd.Series([row.get("lead_time_mean_days")]), errors="coerce").iloc[0]
    adjusted_30d = pd.to_numeric(pd.Series([row.get("adjusted_demand_30d")]), errors="coerce").iloc[0]
    if pd.notna(avg_daily) and avg_daily > 0 and pd.notna(lead_time) and lead_time > 0:
        reference = float(avg_daily * lead_time)
        if _to_bool_value(row.get("stockout_censored_demand_flag", False)) and pd.notna(adjusted_30d) and adjusted_30d > 0:
            reference = max(reference, float(adjusted_30d / 30 * lead_time))
            return _reference_series(reference, "LEAD_TIME_ADJUSTED_DEMAND_CENSORED")
        return _reference_series(reference, "LEAD_TIME_FORECAST_DEMAND")
    p90 = pd.to_numeric(pd.Series([row.get("average_p90_forecast")]), errors="coerce").iloc[0]
    p50 = pd.to_numeric(pd.Series([row.get("average_p50_forecast")]), errors="coerce").iloc[0]
    if pd.notna(p90) and p90 > 0:
        return _reference_series(float(p90), "AVERAGE_P90_FORECAST")
    if pd.notna(p50) and p50 > 0:
        return _reference_series(float(p50), "AVERAGE_P50_FORECAST")
    return _reference_series(float(row["moq"]), "MOQ_FALLBACK")


def _reference_series(quantity: float, source: str) -> pd.Series:
    return pd.Series(
        {
            "reference_usable_quantity": quantity,
            "reference_quantity_source": source,
            "requirement_input_mode": "PROVISIONAL_NO_PHASE3_CONTEXT",
            "phase3_requirement_loaded_flag": False,
            "phase3_requirement_schema_version": "",
            "authoritative_requested_quantity_units": 0.0,
            "fallback_quantity_used_flag": True,
            "fallback_quantity_reason": "PHASE3_REQUIREMENT_BRIDGE_NOT_AVAILABLE",
        }
    )


def _round_up_to_batch(row: pd.Series) -> float:
    """Round yield-adjusted quantity up to the nearest batch size."""
    quantity = row["yield_adjusted_order_quantity"]
    batch_size = row["batch_size"]
    if pd.isna(quantity) or pd.isna(batch_size) or batch_size <= 0:
        return pd.NA
    batches = int(-(-float(quantity) // float(batch_size)))
    return float(batches * batch_size)


def _is_feasible_supplier_option(row: pd.Series) -> bool:
    """Return True when supplier option passes basic feasibility checks."""
    return bool(
        row["is_supplier_active"]
        and row["unit_cost"] >= 0
        and 0 < row["yield_rate"] <= 1
        and row["moq"] > 0
        and row["batch_size"] > 0
        and pd.notna(row["final_feasible_order_quantity"])
        and row["final_feasible_order_quantity"] > 0
    )


def _feasibility_warnings(row: pd.Series) -> list[str]:
    """Return supplier feasibility warnings."""
    warnings = []
    if not row["is_supplier_active"]:
        warnings.append("INACTIVE_SUPPLIER")
    if not (0 < row["yield_rate"] <= 1):
        warnings.append("INVALID_YIELD")
    if row["moq"] <= 0:
        warnings.append("INVALID_MOQ")
    if row["batch_size"] <= 0:
        warnings.append("INVALID_BATCH_SIZE")
    if row["unit_cost"] < 0:
        warnings.append("INVALID_COST")
    if row["moq"] > 3 * row["reference_usable_quantity"]:
        warnings.append("HIGH_MOQ_VS_DEMAND")
    if row["yield_rate"] < 0.90:
        warnings.append("LOW_YIELD_REQUIRES_EXTRA_ORDERING")
    if _to_bool_value(row.get("stockout_censored_demand_flag", False)):
        warnings.append("DEMAND_MAY_BE_CENSORED")
    if _to_bool_value(row.get("underforecast_risk_flag", False)):
        warnings.append("UNDERFORECAST_RISK_AFFECTS_PROCUREMENT")
    if _to_bool_value(row.get("high_uncertainty_flag", False)):
        warnings.append("HIGH_FORECAST_UNCERTAINTY")
    if _to_bool_value(row.get("upcoming_event_flag", False)):
        warnings.append("UPCOMING_EVENT_DEMAND_PRESSURE")
    return warnings


def _feasibility_reason(warnings: list[str]) -> str:
    """Create a readable feasibility reason from warning codes."""
    if not warnings:
        return "Supplier option is feasible."
    if "INACTIVE_SUPPLIER" in warnings:
        return "Supplier is inactive."
    if "INVALID_MOQ" in warnings or "INVALID_BATCH_SIZE" in warnings:
        return "Supplier option has invalid MOQ or batch size."
    if "INVALID_YIELD" in warnings:
        return "Supplier option has invalid yield."
    if "INVALID_COST" in warnings:
        return "Supplier option has invalid cost."
    if "HIGH_MOQ_VS_DEMAND" in warnings:
        return "MOQ is high compared to expected demand."
    if "LOW_YIELD_REQUIRES_EXTRA_ORDERING" in warnings:
        return "Low yield requires ordering extra quantity."
    return "Supplier option requires procurement review."


def _add_demand_adjusted_risk(df: pd.DataFrame) -> pd.DataFrame:
    """Add demand-context risk adjustment without replacing original risk."""
    enriched = df.copy()
    enriched["demand_risk_component"] = _demand_risk_component(enriched)
    enriched["supplier_risk_component"] = enriched["procurement_risk_score"].clip(0, 1)
    enriched["backorder_risk_component"] = 0.0
    enriched["capacity_risk_component"] = 0.0
    enriched["event_risk_component"] = _to_bool_series(enriched["upcoming_event_flag"]).astype(float) * 0.65
    total = sum(DEMAND_ADJUSTED_RISK_WEIGHTS.values())
    enriched["total_demand_adjusted_risk_score"] = (
        DEMAND_ADJUSTED_RISK_WEIGHTS["demand_risk_component"] * enriched["demand_risk_component"]
        + DEMAND_ADJUSTED_RISK_WEIGHTS["supplier_risk_component"] * enriched["supplier_risk_component"]
        + DEMAND_ADJUSTED_RISK_WEIGHTS["backorder_risk_component"] * enriched["backorder_risk_component"]
        + DEMAND_ADJUSTED_RISK_WEIGHTS["capacity_risk_component"] * enriched["capacity_risk_component"]
        + DEMAND_ADJUSTED_RISK_WEIGHTS["event_risk_component"] * enriched["event_risk_component"]
    ) / total
    enriched["demand_adjusted_procurement_risk_score"] = enriched["total_demand_adjusted_risk_score"].clip(0, 1)
    enriched["demand_adjusted_procurement_risk_class"] = enriched[
        "demand_adjusted_procurement_risk_score"
    ].apply(_risk_class)
    enriched["demand_strategy_warning_codes"] = enriched.apply(_demand_warning_codes, axis=1)
    return enriched


def _demand_risk_component(df: pd.DataFrame) -> pd.Series:
    """Return a normalized demand risk component from new Phase 1 planning signals."""
    urgency = (pd.to_numeric(df["demand_urgency_score"], errors="coerce").fillna(0) / 100).clip(0, 1)
    uncertainty = _to_bool_series(df["high_uncertainty_flag"]).astype(float) * 0.75
    underforecast = _to_bool_series(df["underforecast_risk_flag"]).astype(float) * 0.75
    censored = _to_bool_series(df["stockout_censored_demand_flag"]).astype(float) * 0.85
    low_quality = (1 - pd.to_numeric(df["demand_data_quality_score"], errors="coerce").fillna(0.5)).clip(0, 1)
    pressure = (pd.to_numeric(df["demand_pressure_30d"], errors="coerce").fillna(1) - 1).clip(0, 1)
    seasonal = df["seasonal_phase"].astype(str).str.upper().isin(["BUILDUP", "PEAK"]).astype(float) * 0.35
    return (
        0.25 * urgency
        + 0.18 * uncertainty
        + 0.18 * underforecast
        + 0.16 * censored
        + 0.10 * low_quality
        + 0.08 * pressure
        + 0.05 * seasonal
    ).clip(0, 1)


def _demand_warning_codes(row: pd.Series) -> str:
    warnings = []
    if _to_bool_value(row.get("stockout_censored_demand_flag", False)):
        warnings.append("DEMAND_MAY_BE_CENSORED")
    if _to_bool_value(row.get("underforecast_risk_flag", False)):
        warnings.append("UNDERFORECAST_RISK_AFFECTS_PROCUREMENT")
    if _to_bool_value(row.get("high_uncertainty_flag", False)):
        warnings.append("HIGH_FORECAST_UNCERTAINTY")
    if _to_bool_value(row.get("upcoming_event_flag", False)):
        warnings.append("UPCOMING_EVENT_DEMAND_PRESSURE")
    if float(row.get("demand_data_quality_score", 0.5)) < 0.5:
        warnings.append("LOW_DEMAND_DATA_QUALITY")
    return ";".join(warnings) if warnings else "NONE"


def _demand_context_adjustment(df: pd.DataFrame) -> pd.Series:
    """Return small demand-context score adjustments."""
    adjustment = pd.Series(0.0, index=df.index)
    high_adjusted_risk = df["demand_adjusted_procurement_risk_class"].astype(str).eq("HIGH")
    low_confidence = pd.to_numeric(df["champion_confidence_score"], errors="coerce").fillna(0.5) < 0.45
    intermittent = df["demand_behavior_class"].astype(str).str.lower().eq("intermittent")
    smooth = df["demand_behavior_class"].astype(str).str.lower().eq("smooth")

    adjustment -= high_adjusted_risk.astype(float) * df["procurement_risk_score"].clip(0, 1) * 0.04
    adjustment += low_confidence.astype(float) * df["reliability_score"].clip(0, 1) * 0.03
    adjustment += intermittent.astype(float) * (_normalize_lower_is_better(df["moq"]) + _normalize_lower_is_better(df["batch_size"])) * 0.015
    adjustment += smooth.astype(float) * _normalize_lower_is_better(df["unit_cost"]) * 0.015
    return adjustment.clip(-0.08, 0.08)


def _supplier_trend_adjustment(df: pd.DataFrame) -> pd.Series:
    """Return a small evidence and trend adjustment for challenger scoring."""
    adjustment = pd.Series(0.0, index=df.index)
    no_history = df["supplier_history_status"].astype(str).eq("NO_HISTORY")
    insufficient_trend = df["supplier_trend_status"].astype(str).eq("INSUFFICIENT_DATA")
    watchlist = _to_bool_series(df["supplier_watchlist_flag"])
    improving = df["supplier_trend_status"].astype(str).eq("IMPROVING")
    adjustment -= no_history.astype(float) * SUPPLIER_EVIDENCE_ADJUSTMENTS["no_history_penalty"]
    adjustment -= insufficient_trend.astype(float) * SUPPLIER_EVIDENCE_ADJUSTMENTS["insufficient_trend_data_penalty"]
    adjustment -= watchlist.astype(float) * SUPPLIER_EVIDENCE_ADJUSTMENTS["watchlist_penalty"]
    adjustment += improving.astype(float) * SUPPLIER_EVIDENCE_ADJUSTMENTS["improving_bonus"]
    return adjustment


def _normalize_lower_is_better(series: pd.Series) -> pd.Series:
    """Normalize a numeric series so the lowest value receives the best score."""
    minimum = series.min()
    maximum = series.max()
    if pd.isna(minimum) or pd.isna(maximum) or maximum == minimum:
        return pd.Series(1.0, index=series.index)
    return 1 - ((series - minimum) / (maximum - minimum))


def _to_bool_series(series: pd.Series) -> pd.Series:
    """Convert mixed boolean/string/number values to real booleans."""
    normalized = series.fillna(False)
    if normalized.dtype == bool:
        return normalized
    true_values = {"true", "1", "yes", "y", "t"}
    return normalized.astype(str).str.strip().str.lower().isin(true_values)


def _to_bool_value(value) -> bool:
    """Convert a scalar mixed boolean/string/number value to a real boolean."""
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def _risk_class(score: float) -> str:
    """Map risk score to readable class."""
    if score < PROCUREMENT_RISK_THRESHOLDS["low"]:
        return "LOW"
    if score < PROCUREMENT_RISK_THRESHOLDS["medium"]:
        return "MEDIUM"
    return "HIGH"


def _reference_date(purchase_orders: pd.DataFrame) -> pd.Timestamp:
    """Use latest order date as the procurement reference date when available."""
    if purchase_orders.empty or "order_date" not in purchase_orders.columns:
        return pd.Timestamp.today().normalize()
    latest_order_date = purchase_orders["order_date"].max()
    if pd.isna(latest_order_date):
        return pd.Timestamp.today().normalize()
    return latest_order_date.normalize()


def _split_sourcing_decision(primary: pd.Series, backup: pd.Series | None) -> tuple[bool, float, float, str]:
    """Recommend sourcing shares using simple risk and dominance rules."""
    if backup is None:
        return False, 1.0, 0.0, "Single supplier available for SKU."

    score_gap = primary["adjusted_supplier_score"] - backup["adjusted_supplier_score"]
    is_close_score = score_gap <= SUPPLIER_SCORE_CLOSE_THRESHOLD
    risk_class = primary["demand_adjusted_procurement_risk_class"]
    high_delay_probability = primary["delay_probability"] >= SPLIT_SOURCING_THRESHOLDS["high_delay_probability"]
    high_lead_time_std = primary["lead_time_std_days"] >= SPLIT_SOURCING_THRESHOLDS["high_lead_time_std_days"]

    if risk_class == "HIGH":
        return True, 0.60, 0.40, "Split sourcing recommended because demand-adjusted procurement risk is HIGH."
    if risk_class == "MEDIUM" and is_close_score:
        return True, 0.70, 0.30, "Split sourcing recommended because demand-adjusted risk is MEDIUM and backup score is close."
    if high_delay_probability:
        return True, 0.70, 0.30, "Split sourcing recommended because delay probability is high."
    if high_lead_time_std:
        return True, 0.70, 0.30, "Split sourcing recommended because lead time variability is high."
    if is_close_score and risk_class != "LOW":
        return True, 0.70, 0.30, "Split sourcing recommended because supplier scores are close and risk is not LOW."
    return False, 1.0, 0.0, "Single sourcing recommended because supplier has LOW demand-adjusted risk and clearly highest adjusted score."


def _recommendation_candidates(sku_scores: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Prefer feasible suppliers, but keep a review row if all options are infeasible."""
    feasible = sku_scores[sku_scores["is_feasible_supplier_option"]]
    if not feasible.empty:
        return feasible, False
    return sku_scores, True


def _rank_recommendation_candidates(candidates: pd.DataFrame, all_options_infeasible: bool) -> pd.DataFrame:
    """Rank feasible candidates by score, or all-infeasible candidates by risk for review."""
    if all_options_infeasible:
        return candidates.sort_values(
            ["demand_adjusted_procurement_risk_score", "adjusted_supplier_score"],
            ascending=[True, False],
        ).reset_index(drop=True)
    return candidates.sort_values("adjusted_supplier_score", ascending=False).reset_index(drop=True)


def _selection_reason_with_demand_context(
    primary: pd.Series,
    split_reason: str,
    all_options_infeasible: bool,
) -> str:
    """Add readable demand-context rationale to a recommendation."""
    if all_options_infeasible or not primary["is_feasible_supplier_option"]:
        return "All supplier options are infeasible; lowest-risk option selected for review."
    if primary["supplier_evidence_status"] == "NO_HISTORY":
        return (
            f"{split_reason} Supplier selected despite no historical performance because it has strong cost and "
            "feasibility advantages. Review recommended."
        )
    if primary["supplier_evidence_status"] == "LIMITED_HISTORY":
        return (
            f"{split_reason} Supplier selected despite limited trend data because it has the best adjusted score "
            "and is feasible. Limited trend data is noted for procurement monitoring."
        )
    if _to_bool_value(primary["supplier_watchlist_flag"]):
        return f"{split_reason} Supplier selected with caution because supplier is on the watchlist. Review recommended."
    if primary["supplier_trend_status"] == "IMPROVING":
        return f"{split_reason} Supplier trend is improving, supporting the adjusted supplier score."
    if "HIGH_MOQ_VS_DEMAND" in str(primary["feasibility_warning"]):
        return f"{split_reason} Cheapest supplier was not selected because MOQ is too high relative to expected demand."
    if primary["demand_context_status"] != "LOADED_FROM_PHASE1":
        return f"{split_reason} Phase 1 demand context was unavailable, so fallback demand assumptions were used."
    if primary["demand_adjusted_procurement_risk_class"] == "HIGH":
        return f"{split_reason} Reliability prioritized over lowest cost because forecast risk is high."
    if primary["champion_confidence_score"] < 0.45:
        return f"{split_reason} Reliability prioritized because forecast confidence is low."
    if str(primary["demand_behavior_class"]).lower() == "intermittent":
        return f"{split_reason} Flexible supplier preferred because SKU has intermittent demand."
    if primary["champion_risk_level"] == "LOW_RISK" and str(primary["demand_behavior_class"]).lower() == "smooth":
        return f"{split_reason} Supplier selected due to lowest estimated total procurement cost and acceptable reliability."
    return (
        f"{split_reason} Supplier selected because it is feasible, has strong total cost performance, "
        "and has sufficient historical evidence."
    )
