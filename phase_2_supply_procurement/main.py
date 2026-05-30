"""Run Phase 2 Supply & Procurement data foundation and scoring."""

from config import OUTPUT_DIR, SUPPLIER_TREND_WINDOWS
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
    supplier_sku_scores = build_supplier_sku_scores(supplier_sku, supplier_performance, demand_context, suppliers)
    procurement_recommendations = build_procurement_recommendations(supplier_sku_scores, purchase_orders)

    save_output(supplier_trends, "supplier_trends.csv")
    save_output(supplier_performance, "supplier_performance.csv")
    save_output(supplier_sku_scores, "supplier_sku_scores.csv")
    save_output(procurement_recommendations, "procurement_recommendations.csv")

    print_summary(
        suppliers,
        supplier_sku,
        purchase_orders,
        receipts,
        supplier_trends,
        supplier_performance,
        supplier_sku_scores,
        procurement_recommendations,
        phase1_metadata,
    )


def save_output(df, filename: str) -> None:
    """Save a Phase 2 output dataframe."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / filename, index=False)


def print_summary(
    suppliers,
    supplier_sku,
    purchase_orders,
    receipts,
    supplier_trends,
    supplier_performance,
    supplier_sku_scores,
    procurement_recommendations,
    phase1_metadata,
) -> None:
    """Print the required Phase 2 run summary."""
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
    return 0.0


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


if __name__ == "__main__":
    run_pipeline()
