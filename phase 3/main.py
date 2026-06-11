"""Run Phase 3 Inventory Control data foundation pipeline."""

import os
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import OUTPUT_DIR, WAREHOUSE_STAGING_RULES
from core.inventory_cleaner import (
    clean_inventory,
    clean_inventory_batches,
    clean_inventory_movements,
    clean_sku_storage_requirements,
    clean_storage_locations,
    clean_warehouse_layout,
    load_inventory_inputs,
)
from core.inventory_classification import build_inventory_classification
from core.inventory_consolidation import build_inventory_control_consolidation
from core.inventory_context import build_inventory_planning_context
from core.inventory_costs import build_inventory_costs
from core.inventory_generator import create_sample_inventory_files
from core.inventory_kpis import build_inventory_kpi_summary, merge_manager_dashboard_kpis
from core.employee_task_view import build_employee_task_view
from core.inventory_parameters import calculate_inventory_parameters
from core.inventory_policy import build_inventory_policy_selection
from core.inventory_re_evaluation import build_inventory_re_evaluation
from core.inventory_scenario_optimizer import build_inventory_scenario_optimization
from core.inventory_status import build_inventory_status
from core.phase1_integration import load_phase1_inventory_context
from core.phase2_integration import load_phase2_inventory_context
from core.procurement_requirement_bridge import (
    save_phase3_allocation_validation,
    save_procurement_requirement_bridge,
)
from core.service_level import build_inventory_service_levels
from core.warehouse_slotting import build_warehouse_slotting
from core.warehouse_visualization import build_warehouse_visualization


def run_pipeline() -> None:
    """Run Phase 3 Step 1 data foundation."""
    run_id = os.environ.get("INTEGRATED_RUN_ID") or f"PHASE3-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    planning_iteration = int(os.environ.get("PLANNING_ITERATION", "0"))
    create_sample_inventory_files()
    (
        inventory_raw,
        batches_raw,
        movements_raw,
        warehouse_layout_raw,
        storage_locations_raw,
        sku_storage_requirements_raw,
    ) = load_inventory_inputs()

    inventory = clean_inventory(inventory_raw)
    batches = clean_inventory_batches(batches_raw)
    movements = clean_inventory_movements(movements_raw)
    warehouse_layout = clean_warehouse_layout(warehouse_layout_raw)
    storage_locations = clean_storage_locations(storage_locations_raw)
    sku_storage_requirements = clean_sku_storage_requirements(sku_storage_requirements_raw)
    sku_ids = set(inventory["sku_id"].astype(str).str.strip())
    phase1_context, phase1_metadata = load_phase1_inventory_context(sku_ids)
    phase2_context, phase2_metadata = load_phase2_inventory_context(sku_ids)
    planning_context = build_inventory_planning_context(
        inventory,
        batches,
        movements,
        sku_storage_requirements,
        phase1_context,
        phase2_context,
    )
    inventory_classification = build_inventory_classification(planning_context)
    inventory_service_levels = build_inventory_service_levels(planning_context, inventory_classification)
    inventory_policy = build_inventory_policy_selection(
        planning_context,
        inventory_classification,
        inventory_service_levels,
    )
    inventory_policy, inventory_policy_parameters = calculate_inventory_parameters(inventory_policy)
    inventory_status, inventory_action_recommendations = build_inventory_status(
        inventory_policy,
        inventory_policy_parameters,
        planning_context,
        inventory_classification,
        inventory_service_levels,
    )
    inventory_costs, inventory_cost_summary = build_inventory_costs(
        inventory_policy,
        inventory_policy_parameters,
        inventory_status,
        inventory_action_recommendations,
        planning_context,
        inventory_classification,
        inventory_service_levels,
    )
    warehouse_slotting, batch_slotting, location_utilization, space_utilization, warehouse_travel_costs = build_warehouse_slotting(
        inventory,
        batches,
        movements,
        warehouse_layout,
        storage_locations,
        sku_storage_requirements,
        planning_context,
        inventory_classification,
        inventory_service_levels,
        inventory_policy,
        inventory_policy_parameters,
        inventory_status,
        inventory_action_recommendations,
        inventory_costs,
    )
    (
        warehouse_visual_grid,
        warehouse_visual_locations,
        warehouse_visual_skus,
        warehouse_visual_batches,
        warehouse_visual_legend,
        warehouse_visual_summary,
        warehouse_html_outputs,
    ) = build_warehouse_visualization(
        warehouse_slotting,
        batch_slotting,
        location_utilization,
        space_utilization,
        warehouse_travel_costs,
        storage_locations,
        warehouse_layout,
        inventory_status,
        inventory_costs,
    )
    (
        inventory_re_evaluation,
        inventory_parameter_adjustment_recommendations,
        re_evaluation_summary,
    ) = build_inventory_re_evaluation(
        inventory,
        batches,
        movements,
        planning_context,
        inventory_classification,
        inventory_service_levels,
        inventory_policy,
        inventory_policy_parameters,
        inventory_status,
        inventory_action_recommendations,
        inventory_costs,
        warehouse_slotting,
        batch_slotting,
        location_utilization,
        space_utilization,
        warehouse_travel_costs,
        warehouse_visual_skus,
        warehouse_visual_locations,
        warehouse_visual_batches,
        warehouse_visual_summary,
    )
    (
        inventory_scenarios,
        inventory_scenario_results,
        inventory_optimization_recommendations,
        inventory_optimization_summary,
    ) = build_inventory_scenario_optimization(
        inventory,
        batches,
        movements,
        planning_context,
        inventory_classification,
        inventory_service_levels,
        inventory_policy,
        inventory_policy_parameters,
        inventory_status,
        inventory_action_recommendations,
        inventory_costs,
        warehouse_slotting,
        batch_slotting,
        location_utilization,
        space_utilization,
        warehouse_travel_costs,
        warehouse_visual_skus,
        warehouse_visual_locations,
        warehouse_visual_batches,
        warehouse_visual_summary,
        inventory_re_evaluation,
        inventory_parameter_adjustment_recommendations,
        re_evaluation_summary,
    )
    (
        inventory_control_master_decisions,
        inventory_control_human_review_queue,
        inventory_control_advisory_review_queue,
        inventory_control_executive_summary,
        inventory_control_kpi_summary,
        inventory_control_action_plan,
        inventory_control_risk_register,
        inventory_control_manager_dashboard,
    ) = build_inventory_control_consolidation(
        inventory,
        batches,
        movements,
        planning_context,
        inventory_classification,
        inventory_service_levels,
        inventory_policy,
        inventory_policy_parameters,
        inventory_status,
        inventory_action_recommendations,
        inventory_costs,
        inventory_cost_summary,
        warehouse_slotting,
        batch_slotting,
        location_utilization,
        space_utilization,
        warehouse_travel_costs,
        warehouse_visual_grid,
        warehouse_visual_locations,
        warehouse_visual_skus,
        warehouse_visual_batches,
        warehouse_visual_summary,
        inventory_re_evaluation,
        inventory_parameter_adjustment_recommendations,
        re_evaluation_summary,
        inventory_scenarios,
        inventory_scenario_results,
        inventory_optimization_recommendations,
        inventory_optimization_summary,
    )
    inventory_kpi_summary = build_inventory_kpi_summary(
        inventory,
        batches,
        movements,
        planning_context,
        inventory_status,
        inventory_policy_parameters,
    )
    inventory_control_manager_dashboard = merge_manager_dashboard_kpis(
        inventory_control_manager_dashboard,
        inventory_kpi_summary,
    )

    save_output(inventory, "inventory_clean.csv")
    save_output(batches, "inventory_batches_clean.csv")
    save_output(movements, "inventory_movements_clean.csv")
    save_output(warehouse_layout, "warehouse_layout_clean.csv")
    save_output(storage_locations, "storage_locations_clean.csv")
    save_output(sku_storage_requirements, "sku_storage_requirements_clean.csv")
    save_output(planning_context, "inventory_planning_context.csv")
    save_output(inventory_classification, "inventory_classification.csv")
    save_output(inventory_service_levels, "inventory_service_levels.csv")
    save_output(inventory_policy, "inventory_policy.csv")
    save_output(inventory_policy_parameters, "inventory_policy_parameters.csv")
    save_output(inventory_status, "inventory_status.csv")
    save_output(inventory_action_recommendations, "inventory_action_recommendations.csv")
    save_output(inventory_costs, "inventory_costs.csv")
    save_output(inventory_cost_summary, "inventory_cost_summary.csv")
    save_output(warehouse_slotting, "warehouse_slotting.csv")
    save_output(batch_slotting, "batch_slotting.csv")
    save_output(location_utilization, "location_utilization.csv")
    save_output(space_utilization, "space_utilization.csv")
    save_output(warehouse_travel_costs, "warehouse_travel_costs.csv")
    save_output(warehouse_visual_grid, "warehouse_visual_grid.csv")
    save_output(warehouse_visual_locations, "warehouse_visual_locations.csv")
    save_output(warehouse_visual_skus, "warehouse_visual_skus.csv")
    save_output(warehouse_visual_batches, "warehouse_visual_batches.csv")
    save_output(warehouse_visual_legend, "warehouse_visual_legend.csv")
    save_output(warehouse_visual_summary, "warehouse_visual_summary.csv")
    save_output(inventory_re_evaluation, "inventory_re_evaluation.csv")
    save_output(inventory_parameter_adjustment_recommendations, "inventory_parameter_adjustment_recommendations.csv")
    save_output(re_evaluation_summary, "re_evaluation_summary.csv")
    save_output(inventory_scenarios, "inventory_scenarios.csv")
    save_output(inventory_scenario_results, "inventory_scenario_results.csv")
    save_output(inventory_optimization_recommendations, "inventory_optimization_recommendations.csv")
    save_output(inventory_optimization_summary, "inventory_optimization_summary.csv")
    save_output(inventory_control_master_decisions, "inventory_control_master_decisions.csv")
    save_output(inventory_control_human_review_queue, "inventory_control_human_review_queue.csv")
    save_output(inventory_control_advisory_review_queue, "inventory_control_advisory_review_queue.csv")
    save_output(inventory_control_executive_summary, "inventory_control_executive_summary.csv")
    save_output(inventory_control_kpi_summary, "inventory_control_kpi_summary.csv")
    save_output(inventory_kpi_summary, "inventory_kpi_summary.csv")
    save_output(inventory_control_action_plan, "inventory_control_action_plan.csv")
    save_output(inventory_control_risk_register, "inventory_control_risk_register.csv")
    save_output(inventory_control_manager_dashboard, "inventory_control_manager_dashboard.csv")
    for filename, html in warehouse_html_outputs.items():
        save_text_output(html, filename)

    shared_outputs = Path(__file__).resolve().parents[1] / "shared" / "outputs"
    inbound_summary_path = shared_outputs / "phase2_inbound_supply_summary.csv"
    allocation_summary_path = shared_outputs / "phase2_procurement_allocation_summary.csv"
    inbound_summary = pd.read_csv(inbound_summary_path) if inbound_summary_path.exists() else pd.DataFrame()
    planning_data_as_of_date = os.environ.get("PLANNING_DATA_AS_OF_DATE") or datetime.utcnow().date().isoformat()
    procurement_requirement_bridge = save_procurement_requirement_bridge(
        inventory=inventory,
        batches=batches,
        policy=inventory_policy,
        parameters=inventory_policy_parameters,
        status=inventory_status,
        classification=inventory_classification,
        service_levels=inventory_service_levels,
        action_recommendations=inventory_action_recommendations,
        phase1_context=phase1_context,
        inbound_summary=inbound_summary,
        run_id=run_id,
        planning_iteration=planning_iteration,
        data_as_of_date=planning_data_as_of_date,
    )
    if allocation_summary_path.exists():
        allocation_summary = pd.read_csv(allocation_summary_path)
        phase3_allocation_validation = save_phase3_allocation_validation(
            procurement_requirement_bridge,
            allocation_summary,
            run_id=run_id,
            planning_iteration=planning_iteration,
            data_as_of_date=planning_data_as_of_date,
        )
    else:
        allocation_summary = pd.DataFrame()
        phase3_allocation_validation = pd.DataFrame()
    inventory_employee_task_view = build_employee_task_view(
        inventory_control_manager_dashboard,
        inventory_control_master_decisions,
        warehouse_slotting,
        inventory_kpi_summary,
        procurement_requirement_bridge,
        allocation_summary,
    )
    save_output(inventory_employee_task_view, "inventory_employee_task_view.csv")

    print_summary(
        inventory,
        batches,
        movements,
        warehouse_layout,
        storage_locations,
        sku_storage_requirements,
        planning_context,
        inventory_classification,
        inventory_service_levels,
        inventory_policy,
        inventory_policy_parameters,
        inventory_status,
        inventory_action_recommendations,
        inventory_costs,
        inventory_cost_summary,
        warehouse_slotting,
        batch_slotting,
        location_utilization,
        space_utilization,
        warehouse_travel_costs,
        warehouse_visual_grid,
        warehouse_visual_locations,
        warehouse_visual_skus,
        warehouse_visual_batches,
        warehouse_visual_legend,
        warehouse_visual_summary,
        warehouse_html_outputs,
        inventory_re_evaluation,
        inventory_parameter_adjustment_recommendations,
        re_evaluation_summary,
        inventory_scenarios,
        inventory_scenario_results,
        inventory_optimization_recommendations,
        inventory_optimization_summary,
        inventory_control_master_decisions,
        inventory_control_human_review_queue,
        inventory_control_advisory_review_queue,
        inventory_control_executive_summary,
        inventory_control_kpi_summary,
        inventory_kpi_summary,
        inventory_control_action_plan,
        inventory_control_risk_register,
        inventory_control_manager_dashboard,
        phase1_metadata,
        phase2_metadata,
        procurement_requirement_bridge,
        phase3_allocation_validation,
        inventory_employee_task_view,
    )


def save_output(df, filename: str) -> None:
    """Save a cleaned Phase 3 output dataframe."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_DIR / filename, index=False)


def save_text_output(text: str, filename: str) -> None:
    """Save a text output such as an HTML visual map."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / filename).write_text(text, encoding="utf-8")


def print_summary(
    inventory,
    batches,
    movements,
    warehouse_layout,
    storage_locations,
    sku_storage_requirements,
    planning_context,
    inventory_classification,
    inventory_service_levels,
    inventory_policy,
    inventory_policy_parameters,
    inventory_status,
    inventory_action_recommendations,
    inventory_costs,
    inventory_cost_summary,
    warehouse_slotting,
    batch_slotting,
    location_utilization,
    space_utilization,
    warehouse_travel_costs,
    warehouse_visual_grid,
    warehouse_visual_locations,
    warehouse_visual_skus,
    warehouse_visual_batches,
    warehouse_visual_legend,
    warehouse_visual_summary,
    warehouse_html_outputs,
    inventory_re_evaluation,
    inventory_parameter_adjustment_recommendations,
    re_evaluation_summary,
    inventory_scenarios,
    inventory_scenario_results,
    inventory_optimization_recommendations,
    inventory_optimization_summary,
    inventory_control_master_decisions,
    inventory_control_human_review_queue,
    inventory_control_advisory_review_queue,
    inventory_control_executive_summary,
    inventory_control_kpi_summary,
    inventory_kpi_summary,
    inventory_control_action_plan,
    inventory_control_risk_register,
    inventory_control_manager_dashboard,
    phase1_metadata,
    phase2_metadata,
    procurement_requirement_bridge=None,
    phase3_allocation_validation=None,
    inventory_employee_task_view=None,
) -> None:
    """Print the Phase 3 Step 2 run summary."""
    procurement_requirement_bridge = procurement_requirement_bridge if procurement_requirement_bridge is not None else pd.DataFrame()
    phase3_allocation_validation = phase3_allocation_validation if phase3_allocation_validation is not None else pd.DataFrame()
    inventory_employee_task_view = inventory_employee_task_view if inventory_employee_task_view is not None else pd.DataFrame()
    print("Phase 3 Inventory Control planning context completed.")
    print(f"Inventory rows: {len(inventory)}")
    print(f"Batch rows: {len(batches)}")
    print(f"Movement rows: {len(movements)}")
    print(f"Warehouse rows: {len(warehouse_layout)}")
    print(f"Storage location rows: {len(storage_locations)}")
    print(f"SKU storage requirement rows: {len(sku_storage_requirements)}")
    print(f"SKUs with negative inventory: {_count_true(inventory, 'negative_inventory_flag')}")
    print(f"SKUs with zero inventory: {_count_true(inventory, 'zero_inventory_flag')}")
    print(f"SKUs with positive inventory: {_count_true(inventory, 'positive_inventory_flag')}")
    print(f"Near-expiry batches: {_count_true(batches, 'near_expiry_flag')}")
    print(f"Expired batches: {_count_true(batches, 'expired_flag')}")
    print(f"Warehouse aisle width OK: {_all_true(warehouse_layout, 'aisle_width_ok')}")
    print(f"Storage locations over capacity: {_count_true(storage_locations, 'overcapacity_flag')}")
    print(f"Forklift-accessible locations: {_count_true(storage_locations, 'forklift_accessible')}")
    print(f"Temperature-controlled locations: {_count_true(storage_locations, 'temperature_controlled')}")
    print(f"Security-controlled locations: {_count_true(storage_locations, 'security_controlled')}")
    print(f"Phase 1 context loaded: {phase1_metadata['phase1_context_loaded']}")
    print(f"Phase 2 context loaded: {phase2_metadata['phase2_context_loaded']}")
    print(f"Phase 2 context source: {phase2_metadata.get('phase2_context_source', 'UNKNOWN')}")
    print(f"Phase 2 allocation bridge loaded: {phase2_metadata.get('phase2_allocation_loaded_flag', False)}")
    print(f"Planning context rows: {len(planning_context)}")
    print(f"Planning context complete rows: {_count_value(planning_context, 'planning_context_status', 'COMPLETE_CONTEXT')}")
    print(f"Planning context partial rows: {_count_value(planning_context, 'planning_context_status', 'PARTIAL_CONTEXT')}")
    print(f"Planning context fallback rows: {_count_value(planning_context, 'planning_context_status', 'FALLBACK_CONTEXT')}")
    print(f"SKUs with stockout signal: {_count_true(planning_context, 'stockout_signal')}")
    print(f"SKUs with expiry risk signal: {_count_true(planning_context, 'expiry_risk_signal')}")
    print(f"SKUs with non-moving signal: {_count_true(planning_context, 'non_moving_signal')}")
    print(f"SKUs with supplier review signal: {_count_true(planning_context, 'supplier_review_signal')}")
    print(f"SKUs with watchlist supplier signal: {_count_true(planning_context, 'watchlist_supplier_signal')}")
    print(f"Supplier option average count: {_numeric_mean(planning_context, 'supplier_option_count'):.2f}")
    print(f"Feasible supplier option average count: {_numeric_mean(planning_context, 'feasible_supplier_option_count'):.2f}")
    print(f"Inventory classification rows: {len(inventory_classification)}")
    print(f"ABC class counts: {_format_counts(inventory_classification, 'abc_class')}")
    print(f"XYZ class counts: {_format_counts(inventory_classification, 'xyz_class')}")
    print(f"FSN class counts: {_format_counts(inventory_classification, 'fsn_class')}")
    print(f"Vitality class counts: {_format_counts(inventory_classification, 'vitality_class')}")
    print(f"Seasonality class counts: {_format_counts(inventory_classification, 'seasonality_class')}")
    print(f"Perishability class counts: {_format_counts(inventory_classification, 'perishability_class')}")
    print(f"Inventory priority class counts: {_format_counts(inventory_classification, 'inventory_priority_class')}")
    print(
        "Critical priority SKU count: "
        f"{_count_value(inventory_classification, 'inventory_priority_class', 'CRITICAL_PRIORITY')}"
    )
    print(
        "Liquidation priority SKU count: "
        f"{_count_value(inventory_classification, 'inventory_priority_class', 'LIQUIDATION_PRIORITY')}"
    )
    print(f"Inventory service level rows: {len(inventory_service_levels)}")
    print(f"Average service level target: {_numeric_mean(inventory_service_levels, 'service_level_target'):.3f}")
    print(f"Minimum service level target: {_numeric_min(inventory_service_levels, 'service_level_target'):.3f}")
    print(f"Maximum service level target: {_numeric_max(inventory_service_levels, 'service_level_target'):.3f}")
    print(f"Average safety factor z: {_numeric_mean(inventory_service_levels, 'safety_factor_z'):.3f}")
    print(f"Service levels requiring review: {_count_true(inventory_service_levels, 'service_level_review_required')}")
    print(
        "Service level re-evaluation signals: "
        f"{_count_true(inventory_service_levels, 'service_level_re_evaluation_signal')}"
    )
    print(
        "Service level count by inventory priority class: "
        f"{_format_counts(inventory_service_levels, 'inventory_priority_class')}"
    )
    print(f"Service level count by vitality class: {_format_counts(inventory_service_levels, 'vitality_class')}")
    print(f"Service level band >=0.98: {_service_level_band_count(inventory_service_levels, 0.98, None)}")
    print(f"Service level band 0.95 to <0.98: {_service_level_band_count(inventory_service_levels, 0.95, 0.98)}")
    print(f"Service level band 0.90 to <0.95: {_service_level_band_count(inventory_service_levels, 0.90, 0.95)}")
    print(f"Service level band <0.90: {_service_level_band_count(inventory_service_levels, None, 0.90)}")
    print(
        "Service level guardrails applied count: "
        f"{_count_true(inventory_service_levels, 'service_level_guardrail_applied')}"
    )
    print(f"Service levels below 0.90 count: {_service_level_below_count(inventory_service_levels, 0.90)}")
    print(
        "IMPORTANT SKUs below 0.90 count: "
        f"{_class_service_level_below_count(inventory_service_levels, 'vitality_class', 'IMPORTANT', 0.90)}"
    )
    print(
        "VITAL SKUs below 0.95 count: "
        f"{_class_service_level_below_count(inventory_service_levels, 'vitality_class', 'VITAL', 0.95)}"
    )
    print(
        "CRITICAL_PRIORITY SKUs below 0.98 count: "
        f"{_class_service_level_below_count(inventory_service_levels, 'inventory_priority_class', 'CRITICAL_PRIORITY', 0.98)}"
    )
    print(f"Inventory policy rows: {len(inventory_policy)}")
    print(f"Inventory model type counts: {_format_counts(inventory_policy, 'inventory_model_type')}")
    print(f"Review policy counts: {_format_counts(inventory_policy, 'review_policy')}")
    print(f"Policy urgency counts: {_format_counts(inventory_policy, 'policy_urgency')}")
    print(f"Policy review required count: {_count_true(inventory_policy, 'policy_review_required')}")
    print(
        "Average policy selection confidence: "
        f"{_numeric_mean(inventory_policy, 'policy_selection_confidence'):.3f}"
    )
    print(f"Low policy confidence count: {_numeric_below_count(inventory_policy, 'policy_selection_confidence', 0.60)}")
    print(f"Procurement constraint flag count: {_count_true(inventory_policy, 'procurement_constraint_flag')}")
    print(f"Phase 4 review flag count: {_count_true(inventory_policy, 'phase4_review_flag')}")
    print(
        "CONTINUOUS_REVIEW_sQ policies: "
        f"{_count_value(inventory_policy, 'inventory_model_type', 'CONTINUOUS_REVIEW_sQ')}"
    )
    print(f"PERIODIC_REVIEW_RS policies: {_count_value(inventory_policy, 'inventory_model_type', 'PERIODIC_REVIEW_RS')}")
    print(f"EOQ policies: {_count_value(inventory_policy, 'inventory_model_type', 'EOQ')}")
    print(
        "NEWSVENDOR_CANDIDATE policies: "
        f"{_count_value(inventory_policy, 'inventory_model_type', 'NEWSVENDOR_CANDIDATE')}"
    )
    print(f"BASE_STOCK policies: {_count_value(inventory_policy, 'inventory_model_type', 'BASE_STOCK')}")
    print(
        "EVENT_BASED_REPLENISHMENT policies: "
        f"{_count_value(inventory_policy, 'inventory_model_type', 'EVENT_BASED_REPLENISHMENT')}"
    )
    print(
        "ONE_TO_ONE_REPLACEMENT policies: "
        f"{_count_value(inventory_policy, 'inventory_model_type', 'ONE_TO_ONE_REPLACEMENT')}"
    )
    print(
        "FINISHED_GOOD_BUFFER assigned to ONE_TO_ONE count: "
        f"{_two_column_count(inventory_policy, 'push_pull_boundary_role', 'FINISHED_GOOD_BUFFER', 'inventory_model_type', 'ONE_TO_ONE_REPLACEMENT')}"
    )
    print(f"Inventory parameter rows: {len(inventory_policy_parameters)}")
    print(f"Average safety stock: {_numeric_mean(inventory_policy_parameters, 'safety_stock'):.2f}")
    print(f"Average reorder point: {_numeric_mean(inventory_policy_parameters, 'reorder_point'):.2f}")
    print(f"Average EOQ: {_numeric_mean(inventory_policy_parameters, 'eoq'):.2f}")
    print(
        "Average recommended order quantity: "
        f"{_numeric_mean(inventory_policy_parameters, 'recommended_order_quantity'):.2f}"
    )
    print(
        "Total recommended order quantity: "
        f"{_numeric_sum(inventory_policy_parameters, 'recommended_order_quantity'):.2f}"
    )
    print(
        "SKUs with recommended order quantity > 0: "
        f"{_numeric_greater_count(inventory_policy_parameters, 'recommended_order_quantity', 0)}"
    )
    print(
        "SKUs with recommended order quantity = 0: "
        f"{_numeric_equal_count(inventory_policy_parameters, 'recommended_order_quantity', 0)}"
    )
    print(f"Quantity constraint flag count: {_count_true(inventory_policy_parameters, 'quantity_constraint_flag')}")
    print(f"MOQ adjustment count: {_count_true(inventory_policy_parameters, 'moq_adjustment_applied')}")
    print(f"Batch rounding adjustment count: {_count_true(inventory_policy_parameters, 'batch_rounding_applied')}")
    print(f"Yield adjustment count: {_count_true(inventory_policy_parameters, 'yield_adjustment_applied')}")
    print(f"Perishability cap applied count: {_count_true(inventory_policy_parameters, 'perishability_cap_applied')}")
    print(f"Stockout order boost count: {_count_true(inventory_policy_parameters, 'stockout_order_boost_applied')}")
    print(f"Supplier review before order count: {_count_true(inventory_policy_parameters, 'supplier_review_before_order')}")
    print(
        "Phase 4 review before final policy count: "
        f"{_count_true(inventory_policy_parameters, 'phase4_review_before_final_policy')}"
    )
    print(f"No-order event-based count: {_count_true(inventory_policy_parameters, 'no_order_event_based')}")
    print(f"No-order one-to-one count: {_count_true(inventory_policy_parameters, 'no_order_one_to_one')}")
    print(f"Existing-inventory cap count: {_count_true(inventory_policy_parameters, 'existing_inventory_cap_applied')}")
    print(
        "Event-based SKUs with order quantity > 0: "
        f"{_model_quantity_greater_count(inventory_policy_parameters, 'EVENT_BASED_REPLENISHMENT', 0)}"
    )
    print(
        "One-to-one SKUs with order quantity > 0: "
        f"{_model_quantity_greater_count(inventory_policy_parameters, 'ONE_TO_ONE_REPLACEMENT', 0)}"
    )
    print(f"Warning code counts: {_warning_code_counts(inventory_policy_parameters, 'warning_codes')}")
    print(f"Inventory status rows: {len(inventory_status)}")
    print(f"Inventory action recommendation rows: {len(inventory_action_recommendations)}")
    print(f"Main inventory status counts: {_format_counts(inventory_status, 'main_inventory_status')}")
    print(f"Action priority counts: {_format_counts(inventory_status, 'action_priority')}")
    print(f"Primary action counts: {_format_counts(inventory_status, 'primary_action')}")
    print(f"Secondary flag counts: {_secondary_flag_counts(inventory_status, 'secondary_status_flags')}")
    print(f"Stockout status count: {_count_value(inventory_status, 'main_inventory_status', 'STOCKOUT')}")
    print(f"Reorder now count: {_count_value(inventory_status, 'main_inventory_status', 'REORDER_NOW')}")
    print(
        "Approaching reorder point count: "
        f"{_count_value(inventory_status, 'main_inventory_status', 'APPROACHING_REORDER_POINT')}"
    )
    print(f"Healthy count: {_count_value(inventory_status, 'main_inventory_status', 'HEALTHY')}")
    print(f"Overstock count: {_count_value(inventory_status, 'main_inventory_status', 'OVERSTOCK')}")
    print(f"No-order recommended flag count: {_secondary_flag_count(inventory_status, 'NO_ORDER_RECOMMENDED')}")
    print(f"Parameter inconsistency count: {_secondary_flag_count(inventory_status, 'PARAMETER_INCONSISTENCY')}")
    print(f"Supplier review required flag count: {_secondary_flag_count(inventory_status, 'SUPPLIER_REVIEW_REQUIRED')}")
    print(f"Phase 4 review required flag count: {_secondary_flag_count(inventory_status, 'PHASE4_REVIEW_REQUIRED')}")
    print(f"Expired stock flag count: {_secondary_flag_count(inventory_status, 'EXPIRED_STOCK')}")
    print(f"Near-expiry flag count: {_secondary_flag_count(inventory_status, 'NEAR_EXPIRY')}")
    print(f"Inventory cost rows: {len(inventory_costs)}")
    print(f"Inventory cost summary rows: {len(inventory_cost_summary)}")
    print(f"Total current inventory cost: {_numeric_sum(inventory_costs, 'total_current_inventory_cost'):.2f}")
    print(f"Total recommended action cost: {_numeric_sum(inventory_costs, 'total_recommended_action_cost'):.2f}")
    print(
        "Total projected cost after action: "
        f"{_numeric_sum(inventory_costs, 'total_projected_cost_after_action'):.2f}"
    )
    print(f"Total relevant inventory cost: {_numeric_sum(inventory_costs, 'total_relevant_inventory_cost'):.2f}")
    print(f"Main cost driver counts: {_format_counts(inventory_costs, 'main_cost_driver')}")
    print(f"Cost risk level counts: {_format_counts(inventory_costs, 'cost_risk_level')}")
    print(f"Cost action recommendation counts: {_format_counts(inventory_costs, 'cost_action_recommendation')}")
    print(f"SKUs with stockout cost > 0: {_numeric_greater_count(inventory_costs, 'current_stockout_cost', 0)}")
    print(
        "SKUs with expiry cost > 0: "
        f"{_numeric_sum_greater_count(inventory_costs, ['expired_stock_cost', 'near_expiry_risk_cost'], 0)}"
    )
    print(
        "SKUs with overstock cost > 0: "
        f"{_numeric_sum_greater_count(inventory_costs, ['current_overstock_cost', 'projected_overstock_cost_after_order'], 0)}"
    )
    print(
        "SKUs with recommended order cost > 0: "
        f"{_numeric_greater_count(inventory_costs, 'recommended_total_order_cost', 0)}"
    )
    print(f"SKUs with return recovery > 0: {_numeric_greater_count(inventory_costs, 'return_recovery_estimate', 0)}")
    print(f"Cost fallback flag count: {_cost_warning_count(inventory_costs, 'COST_USES_FALLBACKS')}")
    print(f"Warehouse slotting rows: {len(warehouse_slotting)}")
    print(f"Batch slotting rows: {len(batch_slotting)}")
    print(
        "Active expired batches assigned to quarantine: "
        f"{_delimited_count(batch_slotting, 'batch_slotting_warning_flags', 'ACTIVE_EXPIRED_BATCH_ASSIGNED_TO_QUARANTINE')}"
    )
    print(
        "Active near-expiry batches assigned to FEFO: "
        f"{_delimited_count(batch_slotting, 'batch_slotting_warning_flags', 'ACTIVE_NEAR_EXPIRY_BATCH_ASSIGNED_TO_FEFO')}"
    )
    print(
        "Zero-quantity expired batch trace-only count: "
        f"{_delimited_count(batch_slotting, 'batch_slotting_warning_flags', 'ZERO_QUANTITY_EXPIRED_BATCH_TRACE_ONLY')}"
    )
    print(
        "Zero-quantity near-expiry batch trace-only count: "
        f"{_delimited_count(batch_slotting, 'batch_slotting_warning_flags', 'ZERO_QUANTITY_NEAR_EXPIRY_BATCH_TRACE_ONLY')}"
    )
    print(f"SKUs with operational batch split required: {_count_true(warehouse_slotting, 'batch_split_required')}")
    print(
        "SKUs with only historical expired/near-expiry trace: "
        f"{_historical_trace_only_count(warehouse_slotting)}"
    )
    print(
        "Whole-SKU quarantine avoided count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'WHOLE_SKU_QUARANTINE_AVOIDED_BY_BATCH_SPLIT')}"
    )
    print(f"Physical-map included batch count: {_count_true(batch_slotting, 'include_in_physical_map')}")
    print(f"Trace-only batch count: {_count_true(batch_slotting, 'batch_trace_only_flag')}")
    print(f"Traceability-layer batch count: {_count_true(batch_slotting, 'include_in_traceability_layer')}")
    print(f"Location utilization rows: {len(location_utilization)}")
    print(f"Space utilization summary rows: {len(space_utilization)}")
    print(f"Warehouse travel cost rows: {len(warehouse_travel_costs)}")
    print(f"Assigned SKUs count: {_nonblank_count(warehouse_slotting, 'recommended_location_id')}")
    print(
        "SKUs with no feasible location: "
        f"{_count_value(warehouse_slotting, 'location_assignment_status', 'NO_FEASIBLE_LOCATION')}"
    )
    print(
        "SKUs assigned with actual operational warnings: "
        f"{_nonblank_operational_warning_count(warehouse_slotting, 'recommended_location_id', 'slotting_warning_flags')}"
    )
    print(f"Current locations over capacity: {_count_true(location_utilization, 'current_over_capacity_flag')}")
    print(f"Projected locations over capacity: {_count_true(location_utilization, 'projected_over_capacity_flag')}")
    print(f"Current capacity pressure locations: {_count_true(location_utilization, 'current_capacity_pressure_flag')}")
    print(f"Projected capacity pressure locations: {_count_true(location_utilization, 'projected_capacity_pressure_flag')}")
    print(f"Receiving/staging locations projected over capacity: {_receiving_projected_overcapacity_count(location_utilization)}")
    print(f"SKUs causing projected staging pressure: {_count_true(warehouse_slotting, 'sku_causes_projected_staging_pressure')}")
    print(f"Locations with primary storage role: {_numeric_greater_count(location_utilization, 'assigned_primary_sku_count', 0)}")
    print(f"Locations with replenishment staging role: {_numeric_greater_count(location_utilization, 'assigned_replenishment_sku_count', 0)}")
    print(f"Locations with quarantine role: {_numeric_greater_count(location_utilization, 'assigned_quarantine_batch_count', 0)}")
    print(f"Locations with FEFO role: {_numeric_greater_count(location_utilization, 'assigned_fefo_batch_count', 0)}")
    print(f"Locations with mixed roles: {_mixed_role_count(location_utilization)}")
    print(f"Warehouse slotting rows with visual fields populated: {_nonblank_count(warehouse_slotting, 'visual_status_group')}")
    print(f"Batch slotting rows with visual fields populated: {_nonblank_count(batch_slotting, 'visual_status_group')}")
    print(f"Travel rows with visual risk group populated: {_nonblank_count(warehouse_travel_costs, 'visual_travel_risk_group')}")
    print(f"Warehouse visual grid rows: {len(warehouse_visual_grid)}")
    print(f"Warehouse visual location rows: {len(warehouse_visual_locations)}")
    print(f"Warehouse visual SKU rows: {len(warehouse_visual_skus)}")
    print(f"Warehouse visual batch rows: {len(warehouse_visual_batches)}")
    print(f"Warehouse visual legend rows: {len(warehouse_visual_legend)}")
    print(f"Warehouse visual summary rows: {len(warehouse_visual_summary)}")
    print(
        "Visual current location status counts: "
        f"{_format_counts(warehouse_visual_locations, 'current_location_status')}"
    )
    print(
        "Visual projected location status counts: "
        f"{_format_counts(warehouse_visual_locations, 'projected_location_status')}"
    )
    print(f"Visual physical-map batch count: {_count_true(warehouse_visual_batches, 'show_on_physical_map')}")
    print(f"Visual trace-only batch count: {_count_true(warehouse_visual_batches, 'batch_trace_only_flag')}")
    print(
        "Visual locations projected over capacity: "
        f"{_count_true(warehouse_visual_locations, 'projected_over_capacity_flag')}"
    )
    print(
        "Visual locations current over capacity: "
        f"{_count_true(warehouse_visual_locations, 'current_over_capacity_flag')}"
    )
    print(
        "Visual SKUs causing staging pressure: "
        f"{_count_true(warehouse_visual_skus, 'sku_causes_projected_staging_pressure')}"
    )
    print(f"Visual travel risk rows: {_visual_travel_risk_count(warehouse_travel_costs)}")
    print(f"Visual z-level warning rows: {_visual_z_warning_count(warehouse_visual_skus)}")
    print(f"HTML 2D map generated: {'warehouse_2d_map.html' in warehouse_html_outputs}")
    print(f"HTML 3D map generated: {'warehouse_3d_map.html' in warehouse_html_outputs}")
    print(f"Inventory re-evaluation rows: {len(inventory_re_evaluation)}")
    print(
        "Parameter adjustment recommendation rows: "
        f"{len(inventory_parameter_adjustment_recommendations)}"
    )
    print(f"Re-evaluation summary rows: {len(re_evaluation_summary)}")
    print(
        "Recommended adjustment direction counts: "
        f"{_format_counts(inventory_re_evaluation, 'recommended_adjustment_direction')}"
    )
    print(f"Recommendation strength counts: {_format_counts(inventory_re_evaluation, 'recommendation_strength')}")
    print(f"Auto-apply allowed count: {_count_true(inventory_re_evaluation, 'auto_apply_allowed')}")
    print(f"Buffer adjustment scope counts: {_format_counts(inventory_re_evaluation, 'buffer_adjustment_scope')}")
    print(f"Human review level counts: {_format_counts(inventory_re_evaluation, 'human_review_level')}")
    print(
        "Recommendation priority counts: "
        f"{_format_counts(inventory_parameter_adjustment_recommendations, 'recommendation_priority')}"
    )
    print(f"SKUs requiring human review: {_count_true(inventory_re_evaluation, 'requires_human_review')}")
    print(
        "Mandatory review count: "
        f"{_count_value(inventory_re_evaluation, 'human_review_level', 'MANDATORY_REVIEW')}"
    )
    print(
        "Increase buffer recommendations: "
        f"{_count_value(inventory_re_evaluation, 'recommended_adjustment_direction', 'INCREASE_BUFFER')}"
    )
    print(
        "Decrease buffer recommendations: "
        f"{_count_value(inventory_re_evaluation, 'recommended_adjustment_direction', 'DECREASE_BUFFER')}"
    )
    print(
        "Mixed signal recommendations: "
        f"{_count_value(inventory_re_evaluation, 'recommended_adjustment_direction', 'MIXED_SIGNALS')}"
    )
    print(
        "Review-only recommendations: "
        f"{_count_value(inventory_re_evaluation, 'recommended_adjustment_direction', 'REVIEW_ONLY')}"
    )
    print(f"Service level increase count: {_numeric_greater_count(inventory_re_evaluation, 'service_level_adjustment', 0)}")
    print(f"Service level decrease count: {_numeric_below_count(inventory_re_evaluation, 'service_level_adjustment', 0)}")
    print(
        "Safety stock increase count: "
        f"{_numeric_greater_count(inventory_re_evaluation, 'safety_stock_adjustment_units', 0)}"
    )
    print(
        "Safety stock decrease count: "
        f"{_numeric_below_count(inventory_re_evaluation, 'safety_stock_adjustment_units', 0)}"
    )
    print(
        "ROP increase count: "
        f"{_numeric_greater_count(inventory_re_evaluation, 'reorder_point_adjustment_units', 0)}"
    )
    print(
        "ROP decrease count: "
        f"{_numeric_below_count(inventory_re_evaluation, 'reorder_point_adjustment_units', 0)}"
    )
    print(
        "Service level guardrail protected count: "
        f"{_count_value(inventory_re_evaluation, 'service_level_guardrail_action', 'GUARDRAIL_PROTECTED_NO_REDUCTION')}"
    )
    print(
        "ROP lead-time guardrail applied count: "
        f"{_count_true(inventory_re_evaluation, 'rop_lead_time_guardrail_applied')}"
    )
    print(
        "ROP review required count: "
        f"{_count_value(inventory_re_evaluation, 'rop_guardrail_action', 'ROP_REVIEW_REQUIRED')}"
    )
    print(
        "Order quantity review flag count: "
        f"{_count_true(inventory_re_evaluation, 'recommended_order_quantity_review_flag')}"
    )
    print(f"Order review type counts: {_format_counts(inventory_re_evaluation, 'order_review_type')}")
    print(f"Order review severity counts: {_format_counts(inventory_re_evaluation, 'order_review_severity')}")
    print(f"Order review info type counts: {_format_counts(inventory_re_evaluation, 'order_review_info_type')}")
    print(
        "Order review false but non-NO_ORDER_REVIEW count: "
        f"{_order_review_consistency_violation_count(inventory_re_evaluation)}"
    )
    print(
        "Quantity constraint review-only count: "
        f"{_count_true(inventory_re_evaluation, 'quantity_constraint_review_only_flag')}"
    )
    print(f"EOQ review recommendation counts: {_format_counts(inventory_re_evaluation, 'eoq_review_recommendation')}")
    print(
        "Non-EOQ SKUs with EOQ review count: "
        f"{_non_eoq_with_eoq_review_count(inventory_re_evaluation)}"
    )
    print(
        "Order model review recommendation counts: "
        f"{_format_counts(inventory_re_evaluation, 'order_model_review_recommendation')}"
    )
    print(
        "Guarded partial buffer decrease count: "
        f"{_count_value(inventory_re_evaluation, 'buffer_adjustment_scope', 'PARTIAL_BUFFER_DECREASE_SERVICE_LEVEL_PROTECTED')}"
    )
    print(
        "Mixed signal mandatory review count: "
        f"{_two_column_count(inventory_re_evaluation, 'recommended_adjustment_direction', 'MIXED_SIGNALS', 'human_review_level', 'MANDATORY_REVIEW')}"
    )
    print(
        "Supplier review recommendation count: "
        f"{_non_default_count(inventory_re_evaluation, 'supplier_review_recommendation', 'NO_SUPPLIER_REVIEW')}"
    )
    print(
        "Warehouse review recommendation count: "
        f"{_non_default_count(inventory_re_evaluation, 'warehouse_review_recommendation', 'NO_WAREHOUSE_REVIEW')}"
    )
    print(
        "Policy review recommendation count: "
        f"{_non_default_count(inventory_re_evaluation, 'policy_review_recommendation', 'KEEP_POLICY')}"
    )
    print(f"Inventory scenario rows: {len(inventory_scenarios)}")
    print(f"Inventory scenario result rows: {len(inventory_scenario_results)}")
    print(f"Inventory optimization recommendation rows: {len(inventory_optimization_recommendations)}")
    print(f"Inventory optimization summary rows: {len(inventory_optimization_summary)}")
    print(f"Average scenarios per SKU: {_scenario_count_mean(inventory_scenarios):.2f}")
    print(f"Max scenarios per SKU: {_scenario_count_max(inventory_scenarios)}")
    print(f"Feasible scenario count: {_count_true(inventory_scenario_results, 'feasible_flag')}")
    print(
        "Infeasible scenario count: "
        f"{_count_value(inventory_scenario_results, 'feasibility_status', 'INFEASIBLE')}"
    )
    print(f"Human-review scenario count: {_count_true(inventory_scenario_results, 'requires_human_review')}")
    print(f"Scenario hard blocker count: {_numeric_sum(inventory_scenario_results, 'hard_blocker_count'):.0f}")
    print(f"Scenario major risk count: {_numeric_sum(inventory_scenario_results, 'major_risk_count'):.0f}")
    print(f"Scenario review required count: {_numeric_sum(inventory_scenario_results, 'review_required_count'):.0f}")
    print(f"Scenario soft warning count: {_numeric_sum(inventory_scenario_results, 'soft_warning_count'):.0f}")
    print(f"Scenario feasibility severity counts: {_format_counts(inventory_scenario_results, 'feasibility_severity')}")
    print(f"Legacy constraint penalty used count: {_count_true(inventory_scenario_results, 'legacy_constraint_penalty_used_flag')}")
    print(
        "Total severity-based constraint penalty: "
        f"{_numeric_sum(inventory_scenario_results, 'severity_based_constraint_penalty'):.2f}"
    )
    print(
        "Total severity-based review penalty: "
        f"{_numeric_sum(inventory_scenario_results, 'severity_based_review_penalty'):.2f}"
    )
    print(
        "Total severity-based soft warning penalty: "
        f"{_numeric_sum(inventory_scenario_results, 'severity_based_soft_warning_penalty'):.2f}"
    )
    print(f"Selected scenario status counts: {_format_counts(inventory_optimization_recommendations, 'selection_status')}")
    print(f"Selected hard blocker count: {_numeric_sum(inventory_optimization_recommendations, 'selected_hard_blocker_count'):.0f}")
    print(f"Selected major risk count: {_numeric_sum(inventory_optimization_recommendations, 'selected_major_risk_count'):.0f}")
    print(f"Selected review required count: {_numeric_sum(inventory_optimization_recommendations, 'selected_review_required_count'):.0f}")
    print(f"Selected soft warning count: {_numeric_sum(inventory_optimization_recommendations, 'selected_soft_warning_count'):.0f}")
    print(
        "Selected feasibility severity counts: "
        f"{_format_counts(inventory_optimization_recommendations, 'selected_feasibility_severity')}"
    )
    print(
        "Total selected severity-based constraint penalty: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'selected_severity_based_constraint_penalty'):.2f}"
    )
    print(
        "Total selected severity-based review penalty: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'selected_severity_based_review_penalty'):.2f}"
    )
    print(
        "Total selected severity-based soft warning penalty: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'selected_severity_based_soft_warning_penalty'):.2f}"
    )
    print(f"Selected buffer strategy counts: {_format_counts(inventory_optimization_recommendations, 'selected_buffer_strategy')}")
    print(f"Selected supplier strategy counts: {_format_counts(inventory_optimization_recommendations, 'selected_supplier_strategy')}")
    print(f"Selected delivery strategy counts: {_format_counts(inventory_optimization_recommendations, 'selected_delivery_strategy')}")
    print(f"Selected order cap strategy counts: {_format_counts(inventory_optimization_recommendations, 'selected_order_cap_strategy')}")
    print(f"Selected expiry strategy counts: {_format_counts(inventory_optimization_recommendations, 'selected_expiry_strategy')}")
    print(f"Selected warehouse strategy counts: {_format_counts(inventory_optimization_recommendations, 'selected_warehouse_strategy')}")
    print(
        "Total baseline penalty-adjusted cost: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'baseline_total_penalty_adjusted_cost'):.2f}"
    )
    print(
        "Total selected penalty-adjusted cost: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'selected_total_penalty_adjusted_cost'):.2f}"
    )
    print(
        "Total penalty-adjusted estimated saving vs baseline: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'penalty_adjusted_saving_vs_baseline'):.2f}"
    )
    print(
        "Total baseline operational cost: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'baseline_operational_cost'):.2f}"
    )
    print(
        "Total selected operational cost: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'selected_operational_cost'):.2f}"
    )
    print(
        "Total operational cost saving vs baseline: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'operational_cost_saving_vs_baseline'):.2f}"
    )
    print(
        "Total baseline risk penalty cost: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'baseline_risk_penalty_cost'):.2f}"
    )
    print(
        "Total selected risk penalty cost: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'selected_risk_penalty_cost'):.2f}"
    )
    print(
        "Total risk penalty avoided vs baseline: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'risk_penalty_avoidance_vs_baseline'):.2f}"
    )
    print(
        "Total baseline constraint penalty cost: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'baseline_constraint_penalty_cost'):.2f}"
    )
    print(
        "Total selected constraint penalty cost: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'selected_constraint_penalty_cost'):.2f}"
    )
    print(
        "Total constraint penalty avoided vs baseline: "
        f"{_numeric_sum(inventory_optimization_recommendations, 'constraint_penalty_avoidance_vs_baseline'):.2f}"
    )
    print(f"Penalty-driven saving count: {_count_true(inventory_optimization_recommendations, 'penalty_driven_saving_flag')}")
    print(
        "Operational saving count: "
        f"{_count_value(inventory_optimization_recommendations, 'saving_interpretation_type', 'OPERATIONAL_SAVING')}"
    )
    print(
        "Cost increase with risk reduction count: "
        f"{_count_value(inventory_optimization_recommendations, 'saving_interpretation_type', 'COST_INCREASE_WITH_RISK_REDUCTION')}"
    )
    print(
        "Selected for lowest operational cost count: "
        f"{_count_true(inventory_optimization_recommendations, 'selected_for_lowest_operational_cost_flag')}"
    )
    print(
        "Selected for lowest penalty-adjusted cost count: "
        f"{_count_true(inventory_optimization_recommendations, 'selected_for_lowest_penalty_adjusted_cost_flag')}"
    )
    print(f"Selection cost basis counts: {_format_counts(inventory_optimization_recommendations, 'selection_cost_basis')}")
    print(f"Saving interpretation type counts: {_format_counts(inventory_optimization_recommendations, 'saving_interpretation_type')}")
    print(
        "SKUs with positive estimated cost saving: "
        f"{_numeric_greater_count(inventory_optimization_recommendations, 'penalty_adjusted_saving_vs_baseline', 0)}"
    )
    print(
        "SKUs with no feasible scenario: "
        f"{_count_value(inventory_optimization_recommendations, 'selection_status', 'NO_FEASIBLE_SCENARIO_FOUND')}"
    )
    print(
        "SKUs selected with human review required: "
        f"{_count_true(inventory_optimization_recommendations, 'selected_requires_human_review')}"
    )
    print(f"Optimization auto-apply allowed count: {_count_true(inventory_optimization_recommendations, 'auto_apply_allowed')}")
    print(f"Inventory control master decision rows: {len(inventory_control_master_decisions)}")
    print(f"Mandatory human review queue rows: {len(inventory_control_human_review_queue)}")
    print(f"Advisory review queue rows: {len(inventory_control_advisory_review_queue)}")
    print(f"Executive summary rows: {len(inventory_control_executive_summary)}")
    print(f"KPI summary rows: {len(inventory_control_kpi_summary)}")
    print(f"Inventory KPI summary rows: {len(inventory_kpi_summary)}")
    print(
        "Average days inventory on hand: "
        f"{_numeric_mean(inventory_kpi_summary, 'days_inventory_on_hand'):.2f}"
    )
    print(
        "Unit fill-rate unavailable SKUs: "
        f"{_kpi_warning_count(inventory_kpi_summary, 'UNIT_FILL_RATE_UNAVAILABLE')}"
    )
    print(
        "Stockout-rate unavailable SKUs: "
        f"{_kpi_warning_count(inventory_kpi_summary, 'STOCKOUT_RATE_UNAVAILABLE')}"
    )
    print(
        "FEFO compliance unavailable SKUs: "
        f"{_kpi_warning_count(inventory_kpi_summary, 'FEFO_COMPLIANCE_UNAVAILABLE')}"
    )
    print(f"Action plan rows: {len(inventory_control_action_plan)}")
    print(f"Risk register rows: {len(inventory_control_risk_register)}")
    print(f"Manager dashboard rows: {len(inventory_control_manager_dashboard)}")
    print(f"Employee task view rows: {len(inventory_employee_task_view)}")
    print(
        "Final decision priority counts: "
        f"{_format_counts(inventory_control_master_decisions, 'final_decision_priority')}"
    )
    print(
        "Final manager status counts: "
        f"{_format_counts(inventory_control_master_decisions, 'final_manager_status')}"
    )
    print(
        "Final review severity counts: "
        f"{_format_counts(inventory_control_master_decisions, 'final_review_severity')}"
    )
    print(
        "Primary review type counts: "
        f"{_format_counts(inventory_control_master_decisions, 'primary_review_type')}"
    )
    print(
        "Action readiness counts: "
        f"{_format_counts(inventory_control_master_decisions, 'action_readiness')}"
    )
    print(
        "Final recommended action counts: "
        f"{_format_counts(inventory_control_master_decisions, 'final_recommended_action')}"
    )
    print(
        "Blocking review action counts: "
        f"{_format_counts(inventory_control_master_decisions, 'blocking_review_action')}"
    )
    print(
        "Proposed operational action counts: "
        f"{_format_counts(inventory_control_master_decisions, 'proposed_operational_action')}"
    )
    print(
        "Execution owner counts: "
        f"{_format_counts(inventory_control_master_decisions, 'execution_owner')}"
    )
    print(
        "Review owner counts: "
        f"{_format_counts(inventory_control_master_decisions, 'review_owner')}"
    )
    print(
        "Final review type counts: "
        f"{_format_counts(inventory_control_master_decisions, 'final_review_type')}"
    )
    print(
        "Final risk level counts: "
        f"{_format_counts(inventory_control_master_decisions, 'final_risk_level')}"
    )
    print(
        "Final action owner counts: "
        f"{_format_counts(inventory_control_master_decisions, 'final_action_owner')}"
    )
    print(f"Final auto-apply allowed count: {_count_true(inventory_control_master_decisions, 'auto_apply_allowed')}")
    print(
        "Final mandatory review required count: "
        f"{_count_true(inventory_control_master_decisions, 'final_mandatory_review_required')}"
    )
    print(
        "Final advisory review required count: "
        f"{_count_true(inventory_control_master_decisions, 'final_advisory_review_required')}"
    )
    print(
        "Final info warning only count: "
        f"{_count_true(inventory_control_master_decisions, 'final_info_warning_only')}"
    )
    print(
        "Mandatory review gate count: "
        f"{_numeric_sum(inventory_control_master_decisions, 'mandatory_review_gate_count'):.0f}"
    )
    print(
        "Advisory review gate count: "
        f"{_numeric_sum(inventory_control_master_decisions, 'advisory_review_gate_count'):.0f}"
    )
    print(
        "Rows with proposed_operational_action missing: "
        f"{_blank_count(inventory_control_master_decisions, 'proposed_operational_action')}"
    )
    print(
        "Rows with execution_owner missing: "
        f"{_blank_count(inventory_control_master_decisions, 'execution_owner')}"
    )
    print(
        "Multi-department owner without multi-department review count: "
        f"{_multi_owner_misuse_count(inventory_control_master_decisions)}"
    )
    print(
        "Phase 4 rows with proposed operational action populated: "
        f"{_phase4_proposed_action_count(inventory_control_master_decisions)}"
    )
    print(
        "Split delivery rows with procurement and warehouse execution owner: "
        f"{_split_delivery_owner_count(inventory_control_master_decisions)}"
    )
    print(
        "Total operational saving in master decisions: "
        f"{_numeric_sum(inventory_control_master_decisions, 'operational_cost_saving_vs_baseline'):.2f}"
    )
    print(
        "Total penalty-adjusted saving in master decisions: "
        f"{_numeric_sum(inventory_control_master_decisions, 'penalty_adjusted_saving_vs_baseline'):.2f}"
    )
    print(f"SKUs requiring final review: {_count_true(inventory_control_master_decisions, 'final_review_required')}")
    print(
        "MANDATORY_MULTI_DEPARTMENT_REVIEW count: "
        f"{_count_value(inventory_control_master_decisions, 'final_review_type', 'MANDATORY_MULTI_DEPARTMENT_REVIEW')}"
    )
    print(
        "SKUs with TAKE_ACTION_NOW: "
        f"{_count_value(inventory_control_master_decisions, 'final_manager_status', 'TAKE_ACTION_NOW')}"
    )
    print(
        "SKUs with REVIEW_BEFORE_ACTION: "
        f"{_count_value(inventory_control_master_decisions, 'final_manager_status', 'REVIEW_BEFORE_ACTION')}"
    )
    print(f"SKUs with MONITOR: {_count_value(inventory_control_master_decisions, 'final_manager_status', 'MONITOR')}")
    print(
        "SKUs with NO_ACTION_REQUIRED: "
        f"{_count_value(inventory_control_master_decisions, 'final_manager_status', 'NO_ACTION_REQUIRED')}"
    )
    print(
        "Warehouse current space utilization %: "
        f"{_space_summary_value(space_utilization, 'ALL_WAREHOUSE', 'current_utilization_pct'):.2f}"
    )
    print(f"Locations rebased count: {_count_true(location_utilization, 'rebased_utilization_applied')}")
    print(f"Known SKU volume rebased: {_numeric_sum(location_utilization, 'known_current_sku_volume_rebased'):.2f}")
    print(
        "Batch-level location utilization applied count: "
        f"{_count_true(location_utilization, 'batch_level_location_utilization_applied')}"
    )
    print(f"Active quarantine volume: {_numeric_sum(location_utilization, 'assigned_quarantine_volume_m3'):.2f}")
    print(f"Active FEFO volume: {_numeric_sum(location_utilization, 'assigned_fefo_volume_m3'):.2f}")
    print(f"Active primary volume: {_numeric_sum(location_utilization, 'assigned_primary_volume_m3'):.2f}")
    print(f"Active replenishment volume: {_numeric_sum(location_utilization, 'assigned_replenishment_volume_m3'):.2f}")
    print(
        "Warehouse current utilization before rebase %: "
        f"{_safe_pct(_space_summary_value(space_utilization, 'ALL_WAREHOUSE', 'base_used_volume_m3_original'), _space_summary_value(space_utilization, 'ALL_WAREHOUSE', 'total_capacity_m3')):.2f}"
    )
    print(
        "Warehouse current utilization after rebase %: "
        f"{_space_summary_value(space_utilization, 'ALL_WAREHOUSE', 'current_utilization_pct'):.2f}"
    )
    print(
        "Warehouse projected space utilization %: "
        f"{_space_summary_value(space_utilization, 'ALL_WAREHOUSE', 'projected_utilization_pct'):.2f}"
    )
    print(
        "Total current space utilization cost: "
        f"{_space_summary_value(space_utilization, 'ALL_WAREHOUSE', 'space_utilization_cost'):.2f}"
    )
    print(
        "Total projected space utilization cost: "
        f"{_space_summary_value(space_utilization, 'ALL_WAREHOUSE', 'projected_space_utilization_cost'):.2f}"
    )
    print(f"Total travel cost: {_numeric_sum(warehouse_travel_costs, 'travel_cost'):.2f}")
    print(
        "Total frequency-adjusted travel cost: "
        f"{_numeric_sum(warehouse_travel_costs, 'frequency_adjusted_travel_cost'):.2f}"
    )
    print(
        "Fast-moving items too far count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'FAST_MOVING_ITEM_TOO_FAR')}"
    )
    print(
        "Fast-moving one-way distance warning count: "
        f"{_warning_basis_count(warehouse_slotting, 'FAST_MOVING_ITEM_TOO_FAR', 'ONE_WAY')}"
    )
    print(
        "Fast-moving total-route distance warning count: "
        f"{_warning_basis_count(warehouse_slotting, 'FAST_MOVING_ITEM_TOO_FAR', 'TOTAL_ROUTE')}"
    )
    print(
        "Slow/non-moving item in fast-pick count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'SLOW_OR_NON_MOVING_ITEM_IN_FAST_PICK')}"
    )
    print(
        "Prime space used by slow item count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'PRIME_SPACE_USED_BY_SLOW_ITEM')}"
    )
    print(
        "Capability match zone mismatch count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'CAPABILITY_MATCH_ZONE_MISMATCH')}"
    )
    print(
        "Capability match non-exact zone info count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_info_flags', 'CAPABILITY_MATCH_NON_EXACT_ZONE')}"
    )
    print(
        "Replenishment staging over capacity warning count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'REPLENISHMENT_STAGING_OVER_CAPACITY')}"
    )
    print(
        "Receiving capacity review required count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'RECEIVING_CAPACITY_REVIEW_REQUIRED')}"
    )
    print(
        "Current location overcapacity warning count: "
        f"{_delimited_count(location_utilization, 'location_warning_flags', 'CURRENT_LOCATION_OVER_CAPACITY')}"
    )
    print(
        "Projected location overcapacity warning count: "
        f"{_delimited_count(location_utilization, 'location_warning_flags', 'PROJECTED_LOCATION_OVER_CAPACITY')}"
    )
    print(
        "Trace-only batch excluded from physical map count: "
        f"{_delimited_count(batch_slotting, 'visual_warning_flags', 'TRACE_ONLY_BATCH_EXCLUDED_FROM_PHYSICAL_MAP')}"
    )
    print(
        "SKU volume split by batch status count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'SKU_VOLUME_SPLIT_BY_BATCH_STATUS')}"
    )
    print(
        "Active FEFO warning count: "
        f"{_delimited_count(batch_slotting, 'batch_slotting_warning_flags', 'ACTIVE_NEAR_EXPIRY_BATCH_ASSIGNED_TO_FEFO')}"
    )
    print(
        "Zero-quantity FEFO trace-only count: "
        f"{_delimited_count(batch_slotting, 'batch_slotting_warning_flags', 'ZERO_QUANTITY_NEAR_EXPIRY_BATCH_TRACE_ONLY')}"
    )
    print(
        "Fast-moving z-level ergonomic warning count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'FAST_MOVING_ITEM_NOT_ERGONOMIC')}"
    )
    print(
        "A-class items too far count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'A_CLASS_ITEM_TOO_FAR')}"
    )
    print(
        "Fragile high-level warning count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'FRAGILE_ITEM_HIGH_LEVEL')}"
    )
    print(
        "Heavy item high-level warning count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'HEAVY_ITEM_NOT_LOW_LEVEL')}"
    )
    print(
        "Temperature-control mismatch count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'TEMPERATURE_CONTROL_REQUIRED_BUT_MISSING')}"
    )
    print(
        "Security-control mismatch count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'SECURITY_REQUIRED_BUT_MISSING')}"
    )
    print(
        "Forklift mismatch count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'FORKLIFT_ACCESS_REQUIRED_BUT_MISSING')}"
    )
    print(
        "FEFO warning count: "
        f"{_delimited_count(warehouse_slotting, 'slotting_warning_flags', 'FEFO_REQUIRED_BUT_NOT_SUPPORTED') + _delimited_count(warehouse_slotting, 'slotting_warning_flags', 'PERISHABLE_ITEM_NEEDS_FEFO_ACCESS')}"
    )
    print(f"Phase 3 requirement bridge rows: {len(procurement_requirement_bridge)}")
    print(
        "Authoritative requested quantity total: "
        f"{_numeric_sum(procurement_requirement_bridge, 'net_replenishment_requirement_units'):.2f}"
    )
    print(f"Phase 2 allocation validation rows: {len(phase3_allocation_validation)}")
    print(
        "Total allocated usable quantity: "
        f"{_numeric_sum(phase3_allocation_validation, 'allocated_usable_quantity_units'):.2f}"
    )
    print(
        "Total supplier purchase quantity: "
        f"{_numeric_sum(phase3_allocation_validation, 'accepted_allocated_quantity_units'):.2f}"
    )
    print(f"Allocation accepted count: {_count_true(phase3_allocation_validation, 'allocation_accepted_flag')}")
    print(f"Adjustment required count: {_count_true(phase3_allocation_validation, 'adjustment_required_flag')}")
    print(
        "Warehouse blocked count: "
        f"{len(phase3_allocation_validation) - _count_true(phase3_allocation_validation, 'warehouse_capacity_feasible_flag') if not phase3_allocation_validation.empty else 0}"
    )
    print(
        "Service-level blocked count: "
        f"{len(phase3_allocation_validation) - _count_true(phase3_allocation_validation, 'service_level_guardrail_feasible_flag') if not phase3_allocation_validation.empty else 0}"
    )
    print("Integrated convergence status: GENERATED_BY_ORCHESTRATOR" if not phase3_allocation_validation.empty else "STANDALONE_OR_WAITING_FOR_ALLOCATION")
    print(f"Outputs written to: {OUTPUT_DIR}")
    for warning in phase1_metadata.get("phase1_warnings", []):
        print(f"Warning: {warning}")
    for warning in phase2_metadata.get("phase2_warnings", []):
        print(f"Warning: {warning}")


def _count_true(df, column: str) -> int:
    """Count true values in a dataframe column."""
    if df.empty or column not in df.columns:
        return 0
    return int(df[column].astype(bool).sum())


def _all_true(df, column: str) -> bool:
    """Return True if all rows are true for a column."""
    if df.empty or column not in df.columns:
        return False
    return bool(df[column].astype(bool).all())


def _count_value(df, column: str, value: str) -> int:
    """Count rows where a column equals a value."""
    if df.empty or column not in df.columns:
        return 0
    return int((df[column].astype(str) == value).sum())


def _numeric_mean(df, column: str) -> float:
    """Return a numeric column mean."""
    if df.empty or column not in df.columns:
        return 0.0
    return float(df[column].mean())


def _numeric_min(df, column: str) -> float:
    """Return a numeric column minimum."""
    if df.empty or column not in df.columns:
        return 0.0
    return float(df[column].min())


def _numeric_max(df, column: str) -> float:
    """Return a numeric column maximum."""
    if df.empty or column not in df.columns:
        return 0.0
    return float(df[column].max())


def _numeric_sum(df, column: str) -> float:
    """Return a numeric column sum."""
    if df.empty or column not in df.columns:
        return 0.0
    return float(df[column].sum())


def _kpi_warning_count(df, token: str) -> int:
    """Count inventory KPI warning-code occurrences."""
    if df.empty or "inventory_kpi_warning_codes" not in df.columns:
        return 0
    return int(df["inventory_kpi_warning_codes"].fillna("").astype(str).str.contains(token, regex=False).sum())


def _safe_pct(numerator: float, denominator: float) -> float:
    """Return percentage with zero-safe denominator."""
    if denominator == 0:
        return 0.0
    return (numerator / denominator) * 100


def _format_counts(df, column: str) -> str:
    """Format value counts for summary output."""
    if df.empty or column not in df.columns:
        return "none"
    counts = df[column].value_counts().sort_index()
    return ", ".join(f"{key}: {value}" for key, value in counts.items())


def _service_level_band_count(df, lower, upper) -> int:
    """Count service level rows within a band."""
    if df.empty or "service_level_target" not in df.columns:
        return 0
    values = df["service_level_target"]
    mask = values.notna()
    if lower is not None:
        mask &= values >= lower
    if upper is not None:
        mask &= values < upper
    return int(mask.sum())


def _service_level_below_count(df, threshold: float) -> int:
    """Count service level rows below a threshold."""
    if df.empty or "service_level_target" not in df.columns:
        return 0
    return int((df["service_level_target"] < threshold).sum())


def _class_service_level_below_count(df, class_column: str, class_value: str, threshold: float) -> int:
    """Count service level rows in a class that are below a threshold."""
    if df.empty or class_column not in df.columns or "service_level_target" not in df.columns:
        return 0
    mask = (df[class_column].astype(str) == class_value) & (df["service_level_target"] < threshold)
    return int(mask.sum())


def _numeric_below_count(df, column: str, threshold: float) -> int:
    """Count numeric rows below a threshold."""
    if df.empty or column not in df.columns:
        return 0
    return int((df[column] < threshold).sum())


def _numeric_greater_count(df, column: str, threshold: float) -> int:
    """Count numeric rows greater than a threshold."""
    if df.empty or column not in df.columns:
        return 0
    return int((df[column] > threshold).sum())


def _numeric_sum_greater_count(df, columns: list[str], threshold: float) -> int:
    """Count rows where the sum of available numeric columns is greater than a threshold."""
    if df.empty:
        return 0
    available = [column for column in columns if column in df.columns]
    if not available:
        return 0
    return int((df[available].sum(axis=1) > threshold).sum())


def _numeric_equal_count(df, column: str, value: float) -> int:
    """Count numeric rows equal to a value."""
    if df.empty or column not in df.columns:
        return 0
    return int((df[column] == value).sum())


def _two_column_count(df, first_column: str, first_value: str, second_column: str, second_value: str) -> int:
    """Count rows matching two exact string conditions."""
    if df.empty or first_column not in df.columns or second_column not in df.columns:
        return 0
    mask = (df[first_column].astype(str) == first_value) & (df[second_column].astype(str) == second_value)
    return int(mask.sum())


def _model_quantity_greater_count(df, model_type: str, threshold: float) -> int:
    """Count policy rows for one model where recommended quantity is greater than threshold."""
    required = {"inventory_model_type", "recommended_order_quantity"}
    if df.empty or not required.issubset(df.columns):
        return 0
    mask = (df["inventory_model_type"].astype(str) == model_type) & (df["recommended_order_quantity"] > threshold)
    return int(mask.sum())


def _warning_code_counts(df, column: str) -> str:
    """Format semicolon-delimited warning code counts."""
    if df.empty or column not in df.columns:
        return "none"
    counts = {}
    for value in df[column].dropna().astype(str):
        for code in value.split(";"):
            code = code.strip()
            if not code:
                continue
            counts[code] = counts.get(code, 0) + 1
    if not counts:
        return "none"
    return ", ".join(f"{key}: {counts[key]}" for key in sorted(counts))


def _secondary_flag_counts(df, column: str) -> str:
    """Format semicolon-delimited secondary flag counts."""
    if df.empty or column not in df.columns:
        return "none"
    counts = _split_value_counts(df[column])
    if not counts:
        return "none"
    return ", ".join(f"{key}: {counts[key]}" for key in sorted(counts))


def _secondary_flag_count(df, flag: str) -> int:
    """Count rows where a secondary flag is present."""
    if df.empty or "secondary_status_flags" not in df.columns:
        return 0
    return _split_value_counts(df["secondary_status_flags"]).get(flag, 0)


def _cost_warning_count(df, warning: str) -> int:
    """Count rows where a cost warning is present."""
    if df.empty or "cost_warning_flags" not in df.columns:
        return 0
    return _split_value_counts(df["cost_warning_flags"]).get(warning, 0)


def _nonblank_count(df, column: str) -> int:
    """Count rows with a nonblank value."""
    if df.empty or column not in df.columns:
        return 0
    values = df[column].dropna().astype(str).str.strip()
    return int((values != "").sum())


def _blank_count(df, column: str) -> int:
    """Count rows with a blank value."""
    if df.empty or column not in df.columns:
        return 0
    return int(df[column].fillna("").astype(str).str.strip().eq("").sum())


def _multi_owner_misuse_count(df) -> int:
    """Count multi-department owners used without multi-department review or multiple gates."""
    required = {"final_action_owner", "final_review_type", "mandatory_review_gate_count"}
    if df.empty or required.difference(df.columns):
        return 0
    owner = df["final_action_owner"].fillna("").astype(str).str.upper()
    review = df["final_review_type"].fillna("").astype(str).str.upper()
    gate_count = pd.to_numeric(df["mandatory_review_gate_count"], errors="coerce").fillna(0)
    return int(((owner == "MULTI_DEPARTMENT_REVIEW") & (review != "MANDATORY_MULTI_DEPARTMENT_REVIEW") & (gate_count <= 1)).sum())


def _phase4_proposed_action_count(df) -> int:
    """Count Phase 4 blocking review rows with proposed operational action populated."""
    required = {"blocking_review_action", "proposed_operational_action"}
    if df.empty or required.difference(df.columns):
        return 0
    phase4 = df["blocking_review_action"].fillna("").astype(str).str.upper().eq("REVIEW_PHASE4_PRODUCTION_LOGIC")
    proposed = df["proposed_operational_action"].fillna("").astype(str).str.strip().ne("")
    return int((phase4 & proposed).sum())


def _split_delivery_owner_count(df) -> int:
    """Count split-delivery rows with both procurement and warehouse execution owners."""
    required = {"proposed_operational_action", "execution_owner"}
    if df.empty or required.difference(df.columns):
        return 0
    split = df["proposed_operational_action"].fillna("").astype(str).str.upper().eq("SPLIT_DELIVERY")
    owner = df["execution_owner"].fillna("").astype(str).str.upper()
    return int((split & owner.str.contains("PROCUREMENT_TEAM", regex=False) & owner.str.contains("WAREHOUSE_TEAM", regex=False)).sum())


def _nonblank_warning_count(df, id_column: str, warning_column: str) -> int:
    """Count rows with an assigned id and at least one warning."""
    if df.empty or id_column not in df.columns or warning_column not in df.columns:
        return 0
    assigned = df[id_column].fillna("").astype(str).str.strip() != ""
    warned = df[warning_column].fillna("").astype(str).str.strip() != ""
    return int((assigned & warned).sum())


def _nonblank_operational_warning_count(df, id_column: str, warning_column: str) -> int:
    """Count assigned rows with non-trace operational warnings."""
    if df.empty or id_column not in df.columns or warning_column not in df.columns:
        return 0
    trace_or_info = {
        "ZERO_QUANTITY_EXPIRED_BATCH_TRACE_ONLY",
        "ZERO_QUANTITY_NEAR_EXPIRY_BATCH_TRACE_ONLY",
        "TRAVEL_THRESHOLD_USES_ONE_WAY",
        "TRAVEL_THRESHOLD_USES_TOTAL_ROUTE",
        "CAPABILITY_MATCH_ZONE_MISMATCH",
    }
    count = 0
    for _, row in df.iterrows():
        assigned = str(row.get(id_column, "")).strip() != ""
        if not assigned:
            continue
        warnings = {
            item.strip()
            for item in str(row.get(warning_column, "")).split(";")
            if item.strip()
        }
        if warnings - trace_or_info:
            count += 1
    return count


def _historical_trace_only_count(df) -> int:
    """Count SKUs with historical expired/near-expiry batches but no active split."""
    required = {"historical_expired_or_near_expiry_batch_exists", "batch_split_required"}
    if df.empty or not required.issubset(df.columns):
        return 0
    historical = df["historical_expired_or_near_expiry_batch_exists"].astype(bool)
    active = df["batch_split_required"].astype(bool)
    return int((historical & ~active).sum())


def _receiving_projected_overcapacity_count(df) -> int:
    """Count receiving/staging locations projected over capacity."""
    required = {"zone", "projected_over_capacity_flag"}
    if df.empty or not required.issubset(df.columns):
        return 0
    receiving_zones = {str(zone).upper() for zone in WAREHOUSE_STAGING_RULES["receiving_zones"]}
    mask = df["zone"].fillna("").astype(str).str.upper().isin(receiving_zones) & df["projected_over_capacity_flag"].astype(bool)
    return int(mask.sum())


def _mixed_role_count(df) -> int:
    """Count locations with multiple active operational roles."""
    if df.empty or "location_role_summary" not in df.columns:
        return 0
    summaries = df["location_role_summary"].fillna("").astype(str)
    return int(summaries.str.startswith("MIXED").sum() + (summaries == "PRIMARY_AND_REPLENISHMENT").sum())


def _delimited_count(df, column: str, flag: str) -> int:
    """Count rows where a semicolon-delimited flag is present."""
    if df.empty or column not in df.columns:
        return 0
    return _split_value_counts(df[column]).get(flag, 0)


def _warning_basis_count(df, warning: str, threshold_basis: str) -> int:
    """Count warning rows with a specific travel threshold basis."""
    required = {"slotting_warning_flags", "travel_threshold_basis"}
    if df.empty or not required.issubset(df.columns):
        return 0
    warning_present = df["slotting_warning_flags"].fillna("").astype(str).str.contains(warning, regex=False)
    basis_match = df["travel_threshold_basis"].fillna("").astype(str) == threshold_basis
    return int((warning_present & basis_match).sum())


def _space_summary_value(df, group_name: str, column: str) -> float:
    """Return a value from a space utilization summary row."""
    if df.empty or "group_name" not in df.columns or column not in df.columns:
        return 0.0
    rows = df[df["group_name"].astype(str) == group_name]
    if rows.empty:
        return 0.0
    return float(rows.iloc[0][column])


def _split_value_counts(values) -> dict:
    """Count semicolon-delimited values."""
    counts = {}
    for value in values.dropna().astype(str):
        for item in value.split(";"):
            item = item.strip()
            if not item:
                continue
            counts[item] = counts.get(item, 0) + 1
    return counts


def _visual_travel_risk_count(df) -> int:
    """Count travel visual rows with a non-normal travel risk group."""
    if df.empty or "visual_travel_risk_group" not in df.columns:
        return 0
    values = df["visual_travel_risk_group"].fillna("").astype(str)
    return int(((values != "") & (values != "NORMAL_TRAVEL")).sum())


def _visual_z_warning_count(df) -> int:
    """Count SKU visual rows with shelf-height or ergonomic warnings."""
    if df.empty:
        return 0
    z_codes = [
        "FAST_MOVING_ITEM_NOT_ERGONOMIC",
        "FRAGILE_ITEM_HIGH_LEVEL",
        "HEAVY_ITEM_NOT_LOW_LEVEL",
    ]
    columns = [column for column in ["visual_warning_flags", "slotting_warning_flags"] if column in df.columns]
    count = 0
    for _, row in df.iterrows():
        flags = " ".join(str(row.get(column, "")) for column in columns)
        if any(code in flags for code in z_codes):
            count += 1
    return count


def _non_default_count(df, column: str, default_value: str) -> int:
    """Count rows where a recommendation column is not the default value."""
    if df.empty or column not in df.columns:
        return 0
    values = df[column].fillna("").astype(str)
    return int(((values != "") & (values != default_value)).sum())


def _order_review_consistency_violation_count(df) -> int:
    """Count rows with no order review flag but an active order review type."""
    required = {"recommended_order_quantity_review_flag", "order_review_type"}
    if df.empty or not required.issubset(df.columns):
        return 0
    no_review = ~df["recommended_order_quantity_review_flag"].astype(bool)
    non_default = df["order_review_type"].fillna("").astype(str) != "NO_ORDER_REVIEW"
    return int((no_review & non_default).sum())


def _non_eoq_with_eoq_review_count(df) -> int:
    """Count non-EOQ SKUs with EOQ-specific review recommendations."""
    required = {"inventory_model_type", "eoq_review_recommendation"}
    if df.empty or not required.issubset(df.columns):
        return 0
    non_eoq = df["inventory_model_type"].fillna("").astype(str) != "EOQ"
    has_eoq_review = df["eoq_review_recommendation"].fillna("").astype(str) != "NO_EOQ_REVIEW"
    return int((non_eoq & has_eoq_review).sum())


def _scenario_count_mean(df) -> float:
    """Return average generated scenario count per SKU."""
    if df.empty or "sku_id" not in df.columns:
        return 0.0
    return float(df.groupby("sku_id").size().mean())


def _scenario_count_max(df) -> int:
    """Return max generated scenario count per SKU."""
    if df.empty or "sku_id" not in df.columns:
        return 0
    return int(df.groupby("sku_id").size().max())


if __name__ == "__main__":
    run_pipeline()
