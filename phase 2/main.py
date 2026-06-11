"""Run Phase 2 Supply & Procurement data foundation and scoring."""

import os
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import BACKORDER_ALLOCATIONS_FILE, BACKORDERS_FILE, OUTPUT_DIR, SUPPLIER_TREND_WINDOWS
from core.backorder_aging import build_backorder_aging
from core.phase3_supply_bridge import save_phase2_supply_bridge
from core.procurement_allocation import build_and_save_procurement_allocation
from core.procurement_capability_context import (
    build_procurement_capability_context,
    build_supplier_strategy_summary,
)
from core.procurement_kpis import (
    add_allocation_kpis,
    add_procurement_cost_kpis,
    add_supplier_performance_kpis,
)
from core.procurement_scoring import build_procurement_recommendations, build_supplier_sku_scores
from core.phase1_integration import load_phase1_demand_context
from core.supplier_performance import build_supplier_performance
from core.supplier_trends import build_supplier_trends
from core.supply_cleaner import (
    clean_purchase_orders,
    clean_receipts,
    clean_supplier_sku,
    clean_suppliers,
    get_known_skus_from_phase1,
    load_supply_inputs,
)
from core.supply_generator import create_sample_supply_files


def run_pipeline() -> None:
    """Run the Phase 2 supply data foundation and procurement scoring pipeline."""
    run_id = os.environ.get("INTEGRATED_RUN_ID") or f"PHASE2-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    planning_iteration = int(os.environ.get("PLANNING_ITERATION", "0"))
    planning_data_as_of_date = os.environ.get("PLANNING_DATA_AS_OF_DATE") or datetime.utcnow().date().isoformat()
    create_sample_supply_files()
    suppliers_raw, supplier_sku_raw, purchase_orders_raw, receipts_raw = load_supply_inputs()
    known_skus = get_known_skus_from_phase1() or set(supplier_sku_raw["sku_id"].astype(str).str.strip())

    suppliers = clean_suppliers(suppliers_raw)
    supplier_sku = clean_supplier_sku(supplier_sku_raw, suppliers, known_skus)
    purchase_orders = clean_purchase_orders(purchase_orders_raw, suppliers, known_skus)
    receipts = clean_receipts(receipts_raw, purchase_orders)
    demand_context, phase1_metadata = load_phase1_demand_context(set(supplier_sku["sku_id"]))

    supplier_trends = build_supplier_trends(suppliers, purchase_orders, receipts)
    supplier_performance = build_supplier_performance(suppliers, purchase_orders, receipts, supplier_trends)
    supplier_performance = add_supplier_performance_kpis(supplier_performance, purchase_orders, receipts)
    supplier_sku_scores = build_supplier_sku_scores(supplier_sku, supplier_performance, demand_context, suppliers)
    supplier_sku_scores = add_procurement_cost_kpis(supplier_sku_scores)
    procurement_recommendations = build_procurement_recommendations(supplier_sku_scores, purchase_orders)
    procurement_recommendations = add_procurement_cost_kpis(procurement_recommendations)
    backorders = pd.read_csv(BACKORDERS_FILE)
    backorder_allocations = pd.read_csv(BACKORDER_ALLOCATIONS_FILE)
    backorder_aging_detail, backorder_aging_summary = build_backorder_aging(backorders, backorder_allocations)
    backorder_aging_summary = _complete_backorder_summary(backorder_aging_summary, supplier_sku["sku_id"])
    procurement_capability_context = build_procurement_capability_context(
        suppliers,
        supplier_sku,
        supplier_performance,
        supplier_sku_scores,
        backorder_aging_summary,
        purchase_orders,
        receipts,
    )
    procurement_capability_context = add_procurement_cost_kpis(procurement_capability_context)
    supplier_strategy_summary = build_supplier_strategy_summary(
        procurement_capability_context,
        procurement_recommendations,
        purchase_orders,
    )

    save_output(supplier_trends, "supplier_trends.csv")
    save_output(supplier_performance, "supplier_performance.csv")
    save_output(supplier_sku_scores, "supplier_sku_scores.csv")
    save_output(procurement_recommendations, "procurement_recommendations.csv")
    save_output(backorder_aging_detail, "backorder_aging_detail.csv")
    save_output(backorder_aging_summary, "backorder_aging_summary.csv")
    save_output(procurement_capability_context, "phase2_procurement_capability_context.csv")
    save_output(supplier_strategy_summary, "phase2_supplier_strategy_summary.csv")
    phase2_supply_bridge, phase2_inbound_summary = save_phase2_supply_bridge(
        procurement_capability_context,
        run_id=run_id,
        planning_iteration=planning_iteration,
        data_as_of_date=planning_data_as_of_date,
    )
    procurement_allocation_context, procurement_allocation_summary, allocation_metadata = (
        build_and_save_procurement_allocation(
            phase2_supply_bridge,
            run_id=run_id,
            planning_iteration=planning_iteration,
            data_as_of_date=planning_data_as_of_date,
        )
    )
    procurement_allocation_context, procurement_allocation_summary, procurement_kpi_summary = add_allocation_kpis(
        procurement_allocation_context,
        procurement_allocation_summary,
    )
    if not supplier_strategy_summary.empty and not procurement_allocation_summary.empty:
        allocation_kpi_cols = [
            "sku_id",
            "requirement_coverage_rate",
            "unallocated_requirement_rate",
            "top_supplier_allocation_share",
            "supplier_concentration_risk_status",
        ]
        available_allocation_kpi_cols = [
            col for col in allocation_kpi_cols if col in procurement_allocation_summary.columns
        ]
        if len(available_allocation_kpi_cols) > 1:
            merge_cols = [col for col in available_allocation_kpi_cols if col != "sku_id"]
            supplier_strategy_summary = supplier_strategy_summary.drop(
                columns=[col for col in merge_cols if col in supplier_strategy_summary.columns],
                errors="ignore",
            ).merge(
                procurement_allocation_summary[available_allocation_kpi_cols],
                on="sku_id",
                how="left",
            )
            save_output(supplier_strategy_summary, "phase2_supplier_strategy_summary.csv")
    if not procurement_allocation_context.empty:
        procurement_allocation_context.to_csv(
            Path(__file__).resolve().parents[1] / "shared" / "outputs" / "phase2_procurement_allocation_context.csv",
            index=False,
        )
    if not procurement_allocation_summary.empty:
        procurement_allocation_summary.to_csv(
            Path(__file__).resolve().parents[1] / "shared" / "outputs" / "phase2_procurement_allocation_summary.csv",
            index=False,
        )
    save_output(procurement_kpi_summary, "phase2_procurement_kpi_summary.csv")

    print_summary(
        suppliers,
        supplier_sku,
        purchase_orders,
        receipts,
        supplier_trends,
        supplier_performance,
        supplier_sku_scores,
        procurement_recommendations,
        backorder_aging_detail,
        backorder_aging_summary,
        procurement_capability_context,
        supplier_strategy_summary,
        phase1_metadata,
        phase2_supply_bridge,
        phase2_inbound_summary,
        procurement_allocation_context,
        procurement_allocation_summary,
        allocation_metadata,
        procurement_kpi_summary,
    )


def save_output(df, filename: str) -> None:
    """Save a Phase 2 output dataframe."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / filename, index=False)


def _complete_backorder_summary(backorder_summary, sku_ids) -> pd.DataFrame:
    """Ensure the SKU-level backorder summary includes SKUs with no active backorders."""
    all_skus = pd.DataFrame({"sku_id": sorted(set(sku_ids.astype(str)))})
    summary = all_skus.merge(backorder_summary, on="sku_id", how="left")
    defaults = {
        "open_backorder_count": 0,
        "total_backorder_units": 0,
        "total_fulfilled_units": 0,
        "total_remaining_backorder_units": 0,
        "oldest_backorder_age_days": 0,
        "average_backorder_age_days": 0,
        "max_overdue_days": 0,
        "critical_backorder_count": 0,
        "long_backorder_count": 0,
        "stale_backorder_count": 0,
        "backorder_priority_score": 0,
        "backorder_risk_level": "NONE",
        "backorder_pressure_flag": False,
        "recommended_backorder_strategy": "MONITOR",
        "backorder_warning_codes": "NO_ACTIVE_BACKORDERS",
    }
    for column, default in defaults.items():
        if column in summary.columns:
            missing = summary[column].isna()
            if missing.any():
                summary.loc[missing, column] = default
    return summary


def print_summary(
    suppliers,
    supplier_sku,
    purchase_orders,
    receipts,
    supplier_trends,
    supplier_performance,
    supplier_sku_scores,
    procurement_recommendations,
    backorder_aging_detail,
    backorder_aging_summary,
    procurement_capability_context,
    supplier_strategy_summary,
    phase1_metadata,
    phase2_supply_bridge=None,
    phase2_inbound_summary=None,
    procurement_allocation_context=None,
    procurement_allocation_summary=None,
    allocation_metadata=None,
    procurement_kpi_summary=None,
) -> None:
    """Print the required Phase 2 run summary."""
    phase2_supply_bridge = phase2_supply_bridge if phase2_supply_bridge is not None else pd.DataFrame()
    phase2_inbound_summary = phase2_inbound_summary if phase2_inbound_summary is not None else pd.DataFrame()
    procurement_allocation_context = procurement_allocation_context if procurement_allocation_context is not None else pd.DataFrame()
    procurement_allocation_summary = procurement_allocation_summary if procurement_allocation_summary is not None else pd.DataFrame()
    allocation_metadata = allocation_metadata or {}
    procurement_kpi_summary = procurement_kpi_summary if procurement_kpi_summary is not None else pd.DataFrame()
    print("Phase 2 Supply & Procurement completed.")
    print(f"Suppliers count: {len(suppliers)}")
    print(f"Supplier-SKU links count: {len(supplier_sku)}")
    print(f"Purchase orders count: {len(purchase_orders)}")
    print(f"Receipts count: {len(receipts)}")
    print(f"Supplier trend rows: {len(supplier_trends)}")
    print(f"Suppliers with IMPROVING trend status: {_supplier_trend_status_count(supplier_trends, 'IMPROVING')}")
    print(f"Suppliers with HEALTHY trend status: {_supplier_trend_status_count(supplier_trends, 'HEALTHY')}")
    print(f"Suppliers on WATCHLIST: {_supplier_trend_status_count(supplier_trends, 'WATCHLIST')}")
    print(f"Suppliers with MIXED trend status: {_supplier_trend_status_count(supplier_trends, 'MIXED')}")
    print(
        "Suppliers with INSUFFICIENT_DATA trend status: "
        f"{_supplier_trend_status_count(supplier_trends, 'INSUFFICIENT_DATA')}"
    )
    print(f"Suppliers with enough recent and baseline data: {_suppliers_with_enough_trend_data(supplier_trends)}")
    print(f"Worsening lead time trends: {_trend_value_count(supplier_trends, 'lead_time_trend', 'WORSENING')}")
    print(f"Worsening delay trends: {_trend_value_count(supplier_trends, 'delay_trend', 'WORSENING')}")
    print(f"Worsening yield trends: {_trend_value_count(supplier_trends, 'yield_trend', 'WORSENING')}")
    print(f"Worsening reliability trends: {_trend_value_count(supplier_trends, 'reliability_trend', 'WORSENING')}")
    print(
        "Worsening cost per usable unit trends: "
        f"{_trend_value_count(supplier_trends, 'cost_per_usable_unit_trend', 'WORSENING')}"
    )
    print(f"Phase 1 context loaded: {phase1_metadata['phase1_context_loaded']}")
    print(
        "Phase 1 demand planning context loaded: "
        f"{phase1_metadata.get('phase1_context_source') == 'PHASE1_DEMAND_PLANNING_CONTEXT'}"
    )
    print(f"Phase 1 context source: {phase1_metadata.get('phase1_context_source', 'UNKNOWN')}")
    print(f"SKUs loaded from new context: {_count_context_source(supplier_sku_scores, 'PHASE1_DEMAND_PLANNING_CONTEXT')}")
    print(f"SKUs using legacy fallback: {_count_context_source(supplier_sku_scores, 'LEGACY_PHASE1_OUTPUTS')}")
    print(f"SKUs missing context: {phase1_metadata.get('phase1_context_missing_sku_count', 0)}")
    print(f"SKUs with Phase 1 demand context: {_count_demand_context_status(supplier_sku_scores, 'LOADED_FROM_PHASE1')}")
    print(f"SKUs missing Phase 1 demand context: {_count_demand_context_status(supplier_sku_scores, 'MISSING_PHASE1_CONTEXT')}")
    print(f"Supplier performance rows: {len(supplier_performance)}")
    print(f"Suppliers with historical performance: {_count_performance_status(supplier_performance, 'HISTORICAL')}")
    print(f"Suppliers with no history: {_count_performance_status(supplier_performance, 'NO_HISTORY')}")
    print(f"Supplier-SKU score rows: {len(supplier_sku_scores)}")
    print(f"Procurement recommendation rows: {len(procurement_recommendations)}")
    print(f"Supplier-SKU options with STRONG_HISTORY: {_supplier_evidence_status_count(supplier_sku_scores, 'STRONG_HISTORY')}")
    print(f"Supplier-SKU options with LIMITED_HISTORY: {_supplier_evidence_status_count(supplier_sku_scores, 'LIMITED_HISTORY')}")
    print(f"Supplier-SKU options with NO_HISTORY: {_supplier_evidence_status_count(supplier_sku_scores, 'NO_HISTORY')}")
    print(f"Supplier-SKU options requiring review: {_supplier_review_count(supplier_sku_scores)}")
    print(
        "Procurement recommendations requiring supplier review: "
        f"{_recommendation_review_count(procurement_recommendations)}"
    )
    print(
        "Recommendations using NO_HISTORY suppliers: "
        f"{_recommendation_evidence_status_count(procurement_recommendations, 'NO_HISTORY')}"
    )
    print(f"Recommendations using WATCHLIST suppliers: {_recommendation_watchlist_count(procurement_recommendations)}")
    print(f"Feasible supplier-SKU options count: {_feasible_option_count(supplier_sku_scores, True)}")
    print(f"Infeasible supplier-SKU options count: {_feasible_option_count(supplier_sku_scores, False)}")
    print(f"SKUs with at least one feasible supplier: {_skus_with_feasible_supplier(supplier_sku_scores)}")
    print(f"SKUs with no feasible supplier: {_skus_without_feasible_supplier(supplier_sku_scores)}")
    print(
        "HIGH_MOQ_VS_DEMAND warning count: "
        f"{_feasibility_warning_count(supplier_sku_scores, 'HIGH_MOQ_VS_DEMAND')}"
    )
    print(
        "LOW_YIELD_REQUIRES_EXTRA_ORDERING warning count: "
        f"{_feasibility_warning_count(supplier_sku_scores, 'LOW_YIELD_REQUIRES_EXTRA_ORDERING')}"
    )
    print(
        "Inactive supplier option count: "
        f"{_feasibility_warning_count(supplier_sku_scores, 'INACTIVE_SUPPLIER')}"
    )
    print("Procurement risk class counts:")
    print(_format_counts(supplier_sku_scores, "procurement_risk_class"))
    print("Demand-adjusted procurement risk class counts:")
    print(_format_counts(supplier_sku_scores, "demand_adjusted_procurement_risk_class"))
    print(
        "Average demand-adjusted procurement risk score: "
        f"{_numeric_summary(supplier_sku_scores, 'demand_adjusted_procurement_risk_score', 'mean'):.4f}"
    )
    print("Split sourcing recommendation counts:")
    print(_format_counts(procurement_recommendations, "split_sourcing_recommendation"))
    print(f"LOW risk SKUs with split sourcing: {_split_count_by_risk(procurement_recommendations, 'LOW')}")
    print(f"MEDIUM risk SKUs with split sourcing: {_split_count_by_risk(procurement_recommendations, 'MEDIUM')}")
    print(f"HIGH risk SKUs with split sourcing: {_split_count_by_risk(procurement_recommendations, 'HIGH')}")
    print(
        "LOW demand-adjusted risk SKUs with split sourcing: "
        f"{_split_count_by_adjusted_risk(procurement_recommendations, 'LOW')}"
    )
    print(
        "MEDIUM demand-adjusted risk SKUs with split sourcing: "
        f"{_split_count_by_adjusted_risk(procurement_recommendations, 'MEDIUM')}"
    )
    print(
        "HIGH demand-adjusted risk SKUs with split sourcing: "
        f"{_split_count_by_adjusted_risk(procurement_recommendations, 'HIGH')}"
    )
    print(
        "Average estimated total procurement cost: "
        f"{_numeric_summary(supplier_sku_scores, 'estimated_total_procurement_cost', 'mean'):.2f}"
    )
    print(
        "Lowest estimated total procurement cost: "
        f"{_numeric_summary(supplier_sku_scores, 'estimated_total_procurement_cost', 'min'):.2f}"
    )
    print(
        "Highest estimated total procurement cost: "
        f"{_numeric_summary(supplier_sku_scores, 'estimated_total_procurement_cost', 'max'):.2f}"
    )
    print(
        "Average estimated delay cost: "
        f"{_numeric_summary(supplier_sku_scores, 'estimated_expected_delay_cost', 'mean'):.2f}"
    )
    print(
        "Average estimated quality cost: "
        f"{_numeric_summary(supplier_sku_scores, 'estimated_expected_quality_cost', 'mean'):.2f}"
    )
    print(
        "Average estimated total procurement cost for recommended suppliers: "
        f"{_numeric_summary(procurement_recommendations, 'estimated_total_procurement_cost', 'mean'):.2f}"
    )
    print(
        "Average final feasible order quantity for recommended suppliers: "
        f"{_numeric_summary(procurement_recommendations, 'final_feasible_order_quantity', 'mean'):.2f}"
    )
    print(
        "Lowest recommended supplier estimated total procurement cost: "
        f"{_numeric_summary(procurement_recommendations, 'estimated_total_procurement_cost', 'min'):.2f}"
    )
    print(
        "Highest recommended supplier estimated total procurement cost: "
        f"{_numeric_summary(procurement_recommendations, 'estimated_total_procurement_cost', 'max'):.2f}"
    )
    print(
        "SKUs where recommended supplier is also lowest total cost supplier: "
        f"{_recommended_lowest_cost_count(supplier_sku_scores, procurement_recommendations)}"
    )
    print(
        "SKUs where higher-cost supplier was selected due to reliability/risk: "
        f"{_higher_cost_selection_count(supplier_sku_scores, procurement_recommendations)}"
    )
    print(f"Backorder aging detail rows: {len(backorder_aging_detail)}")
    print(f"Backorder aging summary rows: {len(backorder_aging_summary)}")
    print(f"Open backorder count: {_open_backorder_count(backorder_aging_detail)}")
    print(f"Critical backorder count: {_numeric_column_sum(backorder_aging_detail, 'critical_backorder_flag')}")
    print(f"Long backorder count: {_numeric_column_sum(backorder_aging_detail, 'long_backorder_flag')}")
    print(f"Stale backorder count: {_numeric_column_sum(backorder_aging_detail, 'stale_backorder_flag')}")
    print(f"Procurement capability context rows: {len(procurement_capability_context)}")
    print(
        "Gross 30-day demand total: "
        f"{_numeric_summary(procurement_capability_context.drop_duplicates('sku_id'), 'gross_forecast_demand_30d', 'sum'):.2f}"
    )
    print(
        "Active backorder units total: "
        f"{_numeric_summary(procurement_capability_context.drop_duplicates('sku_id'), 'active_backorder_units', 'sum'):.2f}"
    )
    print(
        "Confirmed inbound units total: "
        f"{_numeric_summary(procurement_capability_context.drop_duplicates('sku_id'), 'confirmed_inbound_units', 'sum'):.2f}"
    )
    print(
        "Provisional net requirement total: "
        f"{_numeric_summary(procurement_capability_context.drop_duplicates('sku_id'), 'provisional_net_procurement_requirement_units', 'sum'):.2f}"
    )
    print(
        "Immediate requirement total: "
        f"{_numeric_summary(procurement_capability_context.drop_duplicates('sku_id'), 'immediate_procurement_requirement_units', 'sum'):.2f}"
    )
    print(f"SKUs with provisional requirement: {_bool_sku_count(procurement_capability_context, 'net_requirement_is_provisional_flag')}")
    print(f"SKUs missing inventory deduction context: {_warning_sku_count(procurement_capability_context, 'PHASE3_INVENTORY_CONTEXT_NOT_CONNECTED')}")
    print(
        "Feasible supplier option count in capability context: "
        f"{_numeric_column_sum(procurement_capability_context, 'feasible_supplier_option_flag')}"
    )
    print(
        "Base feasible supplier option count: "
        f"{_numeric_column_sum(procurement_capability_context, 'base_supplier_feasible_flag')}"
    )
    print(
        "Immediate requirement feasible option count: "
        f"{_numeric_column_sum(procurement_capability_context, 'immediate_requirement_feasible_flag')}"
    )
    print(
        "Horizon capacity feasible option count: "
        f"{_numeric_column_sum(procurement_capability_context, 'horizon_capacity_feasible_flag')}"
    )
    print(
        "Final executable supplier option count: "
        f"{_numeric_column_sum(procurement_capability_context, 'final_executable_supplier_option_flag')}"
    )
    print(f"SKUs with one supplier covering horizon: {_horizon_single_supplier_sku_count(procurement_capability_context)}")
    print(f"SKUs with aggregate capacity covering horizon: {_bool_sku_count(procurement_capability_context, 'aggregate_capacity_feasible_flag')}")
    print(f"SKUs requiring split sourcing: {_bool_sku_count(procurement_capability_context, 'split_sourcing_capacity_feasible_flag')}")
    print(f"SKUs with true aggregate capacity shortfall: {_aggregate_shortfall_sku_count(procurement_capability_context)}")
    print(
        "Return-capable supplier option count: "
        f"{_return_capable_option_count(procurement_capability_context)}"
    )
    print(
        "Expedite-capable supplier option count: "
        f"{_numeric_column_sum(procurement_capability_context, 'expedite_capacity_feasible_flag')}"
    )
    print(
        "Split-delivery-capable supplier option count: "
        f"{_numeric_column_sum(procurement_capability_context, 'split_delivery_feasible_flag')}"
    )
    print(
        "Capacity shortfall option count: "
        f"{_numeric_column_sum(procurement_capability_context, 'capacity_shortfall_flag')}"
    )
    print(
        "Fallback cost warning count: "
        f"{_warning_code_count(procurement_capability_context, 'FALLBACK_USED')}"
    )
    print(
        "Weighted procurement cost per usable allocated unit: "
        f"{_kpi_summary_value(procurement_kpi_summary, 'average_total_procurement_cost_per_usable_unit'):.2f}"
    )
    print("Supplier strategy counts:")
    print(_format_counts(supplier_strategy_summary, "recommended_supplier_strategy"))
    print("Current supplier source counts:")
    print(_format_counts(supplier_strategy_summary, "current_supplier_source"))
    print(f"Current supplier unknown count: {_strategy_value_count(supplier_strategy_summary, 'current_supplier_source', 'UNKNOWN')}")
    print(
        "Executable supplier strategy recommendations: "
        f"{_numeric_column_sum(supplier_strategy_summary, 'recommendation_execution_allowed')}"
    )
    print(
        "Blocked supplier strategy recommendations: "
        f"{len(supplier_strategy_summary) - _numeric_column_sum(supplier_strategy_summary, 'recommendation_execution_allowed')}"
    )
    print(
        "Recommended infeasible supplier count: "
        f"{_recommended_infeasible_supplier_count(supplier_strategy_summary)}"
    )
    print(
        "CURRENT_SUPPLIER mismatch count: "
        f"{_strategy_current_mismatch_count(supplier_strategy_summary, 'CURRENT_SUPPLIER')}"
    )
    print(
        "EXPEDITE_CURRENT_SUPPLIER mismatch count: "
        f"{_strategy_current_mismatch_count(supplier_strategy_summary, 'EXPEDITE_CURRENT_SUPPLIER')}"
    )
    print(
        "SPLIT_DELIVERY_CURRENT_SUPPLIER mismatch count: "
        f"{_strategy_current_mismatch_count(supplier_strategy_summary, 'SPLIT_DELIVERY_CURRENT_SUPPLIER')}"
    )
    print(
        "Alternative supplier switch count: "
        f"{_numeric_column_sum(supplier_strategy_summary, 'supplier_switch_flag')}"
    )
    print(
        "Review-required strategy count: "
        f"{_review_strategy_count(supplier_strategy_summary)}"
    )
    print(
        "Executable immediate recommendations: "
        f"{_numeric_column_sum(supplier_strategy_summary, 'recommendation_execution_allowed')}"
    )
    print(
        "Horizon review recommendations: "
        f"{_numeric_column_sum(supplier_strategy_summary, 'capacity_review_required')}"
    )
    print(
        "Split-sourcing capacity plans: "
        f"{_strategy_value_count(supplier_strategy_summary, 'recommended_supplier_strategy', 'SPLIT_SOURCING_CAPACITY_PLAN')}"
    )
    print(
        "Recurring-order plans: "
        f"{_numeric_column_sum(supplier_strategy_summary, 'recurring_orders_required_flag')}"
    )
    print(
        "Aggregate-capacity review count: "
        f"{_strategy_value_count(supplier_strategy_summary, 'recommended_supplier_strategy', 'REVIEW_AGGREGATE_CAPACITY_SHORTFALL')}"
    )
    print(f"Phase 2A supply bridge rows: {len(phase2_supply_bridge)}")
    print(f"Phase 2A inbound summary rows: {len(phase2_inbound_summary)}")
    print(f"Phase 3 requirement bridge loaded: {allocation_metadata.get('phase3_requirement_loaded', False)}")
    print(f"Authoritative requirement SKU count: {allocation_metadata.get('authoritative_requirement_sku_count', 0)}")
    print(f"Fallback requirement SKU count: {allocation_metadata.get('fallback_requirement_sku_count', 0)}")
    print(
        "Total requested usable quantity: "
        f"{allocation_metadata.get('total_requested_usable_quantity', 0.0):.2f}"
    )
    print(
        "Total supplier purchase quantity: "
        f"{allocation_metadata.get('total_supplier_purchase_quantity', 0.0):.2f}"
    )
    print(f"Phase 2B allocation rows: {len(procurement_allocation_context)}")
    print(f"Phase 2B allocation summary rows: {len(procurement_allocation_summary)}")
    print(f"Split-sourcing allocation count: {allocation_metadata.get('split_sourcing_allocation_count', 0)}")
    print(
        "Average requirement coverage rate: "
        f"{_numeric_summary(procurement_allocation_summary, 'requirement_coverage_rate', 'mean'):.4f}"
    )
    print(
        "Weighted supplier capacity utilization rate: "
        f"{_kpi_summary_value(procurement_kpi_summary, 'average_supplier_capacity_utilization_rate'):.4f}"
    )
    print("Supplier concentration risk counts:")
    print(_format_counts(procurement_allocation_summary, "supplier_concentration_risk_status"))
    print(
        "Immediate-with-horizon-review count: "
        f"{_strategy_value_count(supplier_strategy_summary, 'recommended_supplier_strategy', 'IMMEDIATE_ORDER_WITH_HORIZON_REVIEW')}"
    )
    print(
        "Unallocated requirement total: "
        f"{allocation_metadata.get('unallocated_requirement_total', 0.0):.2f}"
    )
    print(
        "Strategy consistency failure count: "
        f"{_strategy_consistency_failure_count(supplier_strategy_summary)}"
    )
    print(f"High urgency SKU count: {_high_urgency_sku_count(procurement_capability_context)}")
    print(f"High uncertainty SKU count: {_bool_sku_count(procurement_capability_context, 'high_uncertainty_flag')}")
    print(f"Stockout-censored demand SKU count: {_bool_sku_count(procurement_capability_context, 'stockout_censored_demand_flag')}")
    print(f"Underforecast risk SKU count: {_bool_sku_count(procurement_capability_context, 'underforecast_risk_flag')}")
    print(f"Upcoming event SKU count: {_bool_sku_count(procurement_capability_context, 'upcoming_event_flag')}")
    print(f"Low data quality SKU count: {_low_quality_sku_count(procurement_capability_context)}")
    print(f"Demand-driven strategy count: {_numeric_column_sum(supplier_strategy_summary, 'demand_driven_strategy_flag')}")
    print(f"Demand review required count: {_numeric_column_sum(supplier_strategy_summary, 'demand_review_required')}")
    print(
        "Selected option warning scope mismatch count: "
        f"{_selected_warning_scope_mismatch_count(supplier_strategy_summary)}"
    )
    print(
        "Selected option capacity warning mismatch count: "
        f"{_selected_warning_token_mismatch_count(supplier_strategy_summary, 'CAPACITY_SHORTFALL')}"
    )
    print(
        "Selected option split-warning mismatch count: "
        f"{_selected_split_warning_mismatch_count(supplier_strategy_summary)}"
    )
    print(f"Outputs written to: {OUTPUT_DIR}")
    for warning in phase1_metadata.get("phase1_warnings", []):
        print(f"Warning: {warning}")


def _format_counts(df, column: str) -> str:
    """Format value counts for summary output."""
    if df.empty or column not in df.columns:
        return "none"
    counts = df[column].value_counts().sort_index()
    return ", ".join(f"{key}: {value}" for key, value in counts.items())


def _split_count_by_risk(df, risk_class: str) -> int:
    """Count recommendations using split sourcing for a risk class."""
    if df.empty:
        return 0
    matching_rows = df[
        (df["procurement_risk_class"] == risk_class)
        & (df["split_sourcing_recommendation"].astype(bool))
    ]
    return int(len(matching_rows))


def _split_count_by_adjusted_risk(df, risk_class: str) -> int:
    """Count split sourcing recommendations by demand-adjusted risk class."""
    if df.empty or "demand_adjusted_procurement_risk_class" not in df.columns:
        return 0
    matching_rows = df[
        (df["demand_adjusted_procurement_risk_class"] == risk_class)
        & (df["split_sourcing_recommendation"].astype(bool))
    ]
    return int(len(matching_rows))


def _numeric_summary(df, column: str, operation: str) -> float:
    """Return a numeric summary value for a dataframe column."""
    if df.empty or column not in df.columns:
        return 0.0
    values = df[column]
    if operation == "mean":
        return float(values.mean())
    if operation == "min":
        return float(values.min())
    if operation == "max":
        return float(values.max())
    if operation == "sum":
        return float(values.sum())
    return 0.0


def _kpi_summary_value(df, kpi_name: str) -> float:
    """Return a numeric value from the compact KPI summary."""
    if df.empty or "kpi_name" not in df.columns or "kpi_value" not in df.columns:
        return 0.0
    rows = df[df["kpi_name"].astype(str).eq(kpi_name)]
    if rows.empty:
        return 0.0
    value = pd.to_numeric(rows.iloc[0]["kpi_value"], errors="coerce")
    return float(value) if pd.notna(value) else 0.0


def _count_demand_context_status(df, status: str) -> int:
    """Count unique SKUs by demand context status."""
    if df.empty or "demand_context_status" not in df.columns:
        return 0
    return int(df[df["demand_context_status"] == status]["sku_id"].nunique())


def _supplier_trend_status_count(df, status: str) -> int:
    """Count suppliers by overall trend status."""
    if df.empty or "supplier_trend_status" not in df.columns:
        return 0
    return int((df["supplier_trend_status"] == status).sum())


def _trend_value_count(df, column: str, value: str) -> int:
    """Count suppliers by a specific trend field value."""
    if df.empty or column not in df.columns:
        return 0
    return int((df[column] == value).sum())


def _suppliers_with_enough_trend_data(df) -> int:
    """Count suppliers meeting minimum trend data requirements."""
    required_columns = {"baseline_order_count", "recent_order_count"}
    if df.empty or not required_columns.issubset(df.columns):
        return 0
    enough_data = (
        (df["baseline_order_count"] >= SUPPLIER_TREND_WINDOWS["minimum_baseline_orders"])
        & (df["recent_order_count"] >= SUPPLIER_TREND_WINDOWS["minimum_recent_orders"])
    )
    return int(enough_data.sum())


def _feasible_option_count(df, feasible: bool) -> int:
    """Count supplier-SKU options by feasibility status."""
    if df.empty or "is_feasible_supplier_option" not in df.columns:
        return 0
    return int((df["is_feasible_supplier_option"].astype(bool) == feasible).sum())


def _supplier_evidence_status_count(df, status: str) -> int:
    """Count supplier-SKU options by evidence status."""
    if df.empty or "supplier_evidence_status" not in df.columns:
        return 0
    return int((df["supplier_evidence_status"] == status).sum())


def _supplier_review_count(df) -> int:
    """Count supplier-SKU options requiring supplier review."""
    if df.empty or "supplier_requires_review" not in df.columns:
        return 0
    return int(df["supplier_requires_review"].astype(bool).sum())


def _recommendation_review_count(df) -> int:
    """Count procurement recommendations requiring supplier review."""
    if df.empty or "recommended_supplier_requires_review" not in df.columns:
        return 0
    return int(df["recommended_supplier_requires_review"].astype(bool).sum())


def _recommendation_evidence_status_count(df, status: str) -> int:
    """Count recommendations by recommended supplier evidence status."""
    if df.empty or "recommended_supplier_evidence_status" not in df.columns:
        return 0
    return int((df["recommended_supplier_evidence_status"] == status).sum())


def _recommendation_watchlist_count(df) -> int:
    """Count recommendations using watchlist suppliers."""
    if df.empty or "supplier_watchlist_flag" not in df.columns:
        return 0
    return int(df["supplier_watchlist_flag"].astype(bool).sum())


def _skus_with_feasible_supplier(df) -> int:
    """Count SKUs that have at least one feasible supplier option."""
    if df.empty or "is_feasible_supplier_option" not in df.columns:
        return 0
    feasible_by_sku = df.groupby("sku_id")["is_feasible_supplier_option"].any()
    return int(feasible_by_sku.sum())


def _skus_without_feasible_supplier(df) -> int:
    """Count SKUs that have no feasible supplier option."""
    if df.empty or "is_feasible_supplier_option" not in df.columns:
        return 0
    feasible_by_sku = df.groupby("sku_id")["is_feasible_supplier_option"].any()
    return int((~feasible_by_sku).sum())


def _feasibility_warning_count(df, warning: str) -> int:
    """Count supplier-SKU options containing a feasibility warning code."""
    if df.empty or "feasibility_warning" not in df.columns:
        return 0
    return int(df["feasibility_warning"].astype(str).str.contains(warning, regex=False).sum())


def _recommended_lowest_cost_count(supplier_sku_scores, procurement_recommendations) -> int:
    """Count SKUs where the recommended supplier has the lowest estimated total cost."""
    comparison = _recommendation_cost_comparison(supplier_sku_scores, procurement_recommendations)
    if comparison.empty:
        return 0
    return int(comparison["is_lowest_total_cost"].sum())


def _higher_cost_selection_count(supplier_sku_scores, procurement_recommendations) -> int:
    """Count SKUs where recommendation selected a higher-cost supplier."""
    comparison = _recommendation_cost_comparison(supplier_sku_scores, procurement_recommendations)
    if comparison.empty:
        return 0
    return int((~comparison["is_lowest_total_cost"]).sum())


def _recommendation_cost_comparison(supplier_sku_scores, procurement_recommendations):
    """Compare recommended supplier cost to each SKU's lowest total cost option."""
    if supplier_sku_scores.empty or procurement_recommendations.empty:
        return supplier_sku_scores.iloc[0:0].copy()
    min_cost = supplier_sku_scores.groupby("sku_id")["estimated_total_procurement_cost"].min().reset_index()
    min_cost = min_cost.rename(columns={"estimated_total_procurement_cost": "lowest_total_procurement_cost"})
    comparison = procurement_recommendations[["sku_id", "estimated_total_procurement_cost"]].merge(
        min_cost,
        on="sku_id",
        how="left",
    )
    comparison["is_lowest_total_cost"] = (
        comparison["estimated_total_procurement_cost"].round(6)
        <= comparison["lowest_total_procurement_cost"].round(6)
    )
    return comparison


def _count_performance_status(df, status: str) -> int:
    """Count suppliers by performance data status."""
    if df.empty or "performance_data_status" not in df.columns:
        return 0
    return int((df["performance_data_status"] == status).sum())


def _open_backorder_count(df) -> int:
    """Count active backorder rows with remaining quantity."""
    if df.empty or "remaining_backorder_units" not in df.columns:
        return 0
    return int((pd.to_numeric(df["remaining_backorder_units"], errors="coerce").fillna(0) > 0).sum())


def _numeric_column_sum(df, column: str) -> int:
    """Count truthy boolean rows or sum a numeric column."""
    if df.empty or column not in df.columns:
        return 0
    series = df[column]
    if series.dtype == bool:
        return int(series.sum())
    normalized = series.astype(str).str.strip().str.lower()
    if normalized.isin(["true", "false", "1", "0", "yes", "no"]).any():
        return int(normalized.isin(["true", "1", "yes"]).sum())
    return int(pd.to_numeric(series, errors="coerce").fillna(0).sum())


def _return_capable_option_count(df) -> int:
    """Count SKU-supplier options with both supplier and SKU return eligibility."""
    required = {"accepts_returns", "return_eligible"}
    if df.empty or not required.issubset(df.columns):
        return 0
    accepts = df["accepts_returns"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
    eligible = df["return_eligible"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
    return int((accepts & eligible).sum())


def _warning_code_count(df, token: str) -> int:
    """Count rows where procurement warning codes contain a token."""
    if df.empty or "procurement_warning_codes" not in df.columns:
        return 0
    return int(df["procurement_warning_codes"].astype(str).str.contains(token, regex=False).sum())


def _strategy_value_count(df, column: str, value: str) -> int:
    """Count strategy rows by a specific value."""
    if df.empty or column not in df.columns:
        return 0
    return int((df[column].astype(str) == value).sum())


def _review_strategy_count(df) -> int:
    """Count all review strategy labels, not only exact REVIEW_REQUIRED."""
    if df.empty or "recommended_supplier_strategy" not in df.columns:
        return 0
    return int(df["recommended_supplier_strategy"].astype(str).str.startswith("REVIEW_").sum())


def _strategy_current_mismatch_count(df, strategy: str) -> int:
    """Count rows where a current-supplier strategy switches suppliers."""
    required = {"recommended_supplier_strategy", "recommended_supplier_id", "current_supplier_id"}
    if df.empty or not required.issubset(df.columns):
        return 0
    rows = df[df["recommended_supplier_strategy"].astype(str) == strategy]
    return int((rows["recommended_supplier_id"].astype(str) != rows["current_supplier_id"].astype(str)).sum())


def _recommended_infeasible_supplier_count(df) -> int:
    """Count executable recommendations whose selected option is not feasible."""
    required = {"recommendation_execution_allowed", "recommended_option_feasible_flag"}
    if df.empty or not required.issubset(df.columns):
        return 0
    executable = df["recommendation_execution_allowed"].astype(str).str.lower().isin(["true", "1", "yes"])
    feasible = df["recommended_option_feasible_flag"].astype(str).str.lower().isin(["true", "1", "yes"])
    return int((executable & ~feasible).sum())


def _strategy_consistency_failure_count(df) -> int:
    """Count executable strategy consistency failures."""
    if df.empty or "strategy_consistency_flag" not in df.columns:
        return 0
    return int((~df["strategy_consistency_flag"].astype(str).str.lower().isin(["true", "1", "yes"])).sum())


def _count_context_source(df, source: str) -> int:
    if df.empty or "phase1_context_source" not in df.columns:
        return 0
    return int(df[df["phase1_context_source"].astype(str) == source]["sku_id"].nunique())


def _bool_sku_count(df, column: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    values = df[column].astype(str).str.lower().isin(["true", "1", "yes"])
    return int(df.loc[values, "sku_id"].nunique())


def _high_urgency_sku_count(df) -> int:
    if df.empty or "demand_urgency_score" not in df.columns:
        return 0
    values = pd.to_numeric(df["demand_urgency_score"], errors="coerce").fillna(0) >= 70
    return int(df.loc[values, "sku_id"].nunique())


def _low_quality_sku_count(df) -> int:
    if df.empty or "demand_data_quality_score" not in df.columns:
        return 0
    values = pd.to_numeric(df["demand_data_quality_score"], errors="coerce").fillna(1) < 0.5
    return int(df.loc[values, "sku_id"].nunique())


def _selected_warning_scope_mismatch_count(df) -> int:
    if df.empty or "selected_option_warning_scope_consistency_flag" not in df.columns:
        return 0
    return int((~df["selected_option_warning_scope_consistency_flag"].astype(str).str.lower().isin(["true", "1", "yes"])).sum())


def _selected_warning_token_mismatch_count(df, token: str) -> int:
    required = {"selected_option_warning_codes", "selected_option_capacity_shortfall_flag"}
    if df.empty or not required.issubset(df.columns):
        return 0
    has_token = df["selected_option_warning_codes"].astype(str).str.contains(token, regex=False)
    capacity = df["selected_option_capacity_shortfall_flag"].astype(str).str.lower().isin(["true", "1", "yes"])
    return int((has_token & ~capacity).sum())


def _selected_split_warning_mismatch_count(df) -> int:
    if df.empty or not {"selected_option_warning_codes", "recommended_supplier_strategy"}.issubset(df.columns):
        return 0
    has_warning = df["selected_option_warning_codes"].astype(str).str.contains(
        "WAREHOUSE_CAPACITY_REVIEW_REQUIRED_FOR_SPLIT_DELIVERY",
        regex=False,
    )
    is_split = df["recommended_supplier_strategy"].astype(str).str.startswith("SPLIT_DELIVERY_")
    return int((has_warning & ~is_split).sum())


def _warning_sku_count(df, token: str) -> int:
    if df.empty:
        return 0
    warning_columns = [column for column in df.columns if "warning" in column.lower()]
    if not warning_columns:
        return 0
    mask = pd.Series(False, index=df.index)
    for column in warning_columns:
        mask = mask | df[column].astype(str).str.contains(token, regex=False)
    return int(df.loc[mask, "sku_id"].nunique())


def _horizon_single_supplier_sku_count(df) -> int:
    if df.empty or "horizon_capacity_feasible_flag" not in df.columns:
        return 0
    mask = df["horizon_capacity_feasible_flag"].astype(str).str.lower().isin(["true", "1", "yes"])
    return int(df.loc[mask, "sku_id"].nunique())


def _aggregate_shortfall_sku_count(df) -> int:
    if df.empty or "aggregate_capacity_shortfall_units" not in df.columns:
        return 0
    mask = pd.to_numeric(df["aggregate_capacity_shortfall_units"], errors="coerce").fillna(0) > 0
    return int(df.loc[mask, "sku_id"].nunique())


if __name__ == "__main__":
    run_pipeline()
