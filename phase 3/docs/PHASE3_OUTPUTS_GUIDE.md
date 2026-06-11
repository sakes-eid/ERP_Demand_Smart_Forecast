# Phase 3 Outputs Guide

This guide explains the main Phase 3 output files and how to interpret them.

## 1. Cleaned Data Outputs

- `inventory_clean.csv`: Clean SKU-level inventory data.
- `inventory_batches_clean.csv`: Clean batch-level inventory and expiry data.
- `inventory_movements_clean.csv`: Clean inventory movement history.
- `warehouse_layout_clean.csv`: Clean warehouse layout context.
- `storage_locations_clean.csv`: Clean storage location data.
- `sku_storage_requirements_clean.csv`: Clean SKU storage requirements.

## 2. Planning Context Outputs

- `inventory_planning_context.csv`: Combined planning context from inventory, batch, movement, Phase 1 demand, Phase 2 supplier/procurement, and storage data.

Use this file to inspect the input signals that feed most later Phase 3 decisions.

## 3. Classification, Service, And Policy Outputs

- `inventory_classification.csv`: ABC, XYZ, FSN, vitality, seasonality, perishability, supplier risk, and inventory priority classes.
- `inventory_service_levels.csv`: SKU-specific service-level targets and guardrails.
- `inventory_policy.csv`: Selected inventory policy and review policy per SKU.
- `inventory_policy_parameters.csv`: Safety stock, reorder point, EOQ, recommended order quantity, and related policy parameters.

## 4. Parameter, Status, And Action Outputs

- `inventory_status.csv`: Main inventory status, secondary flags, supporting status metrics, and action fields.
- `inventory_action_recommendations.csv`: Compact action-focused output for easier review.

These outputs answer whether a SKU is stocked out, low, approaching reorder point, overstocked, healthy, or blocked by review signals.

## 5. Cost Outputs

- `inventory_costs.csv`: SKU-level cost estimates and cost drivers.
- `inventory_cost_summary.csv`: Summary views of cost metrics.

Costs are estimated for decision support. Some assumptions remain fallback-based and should be calibrated before production use.

## 6. Warehouse Outputs

- `warehouse_slotting.csv`: SKU-level warehouse slotting recommendations and warning/info flags.
- `batch_slotting.csv`: One row per batch, including active vs trace-only batch handling.
- `location_utilization.csv`: Current and projected capacity by location.
- `space_utilization.csv`: Space utilization summaries.
- `warehouse_travel_costs.csv`: Travel distance, travel risk, and travel cost estimates.

The warehouse layer separates primary storage, replenishment staging, quarantine, FEFO, and trace-only batches.

## 7. Visualization Outputs

- `warehouse_visual_grid.csv`: Grid-ready location view.
- `warehouse_visual_locations.csv`: One row per location with visual color groups and hover text.
- `warehouse_visual_skus.csv`: One row per SKU with visual role quantities.
- `warehouse_visual_batches.csv`: One row per batch with physical-map and traceability-layer controls.
- `warehouse_visual_legend.csv`: Color group meanings.
- `warehouse_visual_summary.csv`: Summary rows by visual group, status, zone, layer, batch status, SKU status, and travel risk.
- `warehouse_2d_map.html`: Optional 2D warehouse map.
- `warehouse_3d_map.html`: Optional 3D warehouse map using z/shelf level.

## 8. Re-Evaluation Outputs

- `inventory_re_evaluation.csv`: Detailed recommendation-only re-evaluation output.
- `inventory_parameter_adjustment_recommendations.csv`: More focused parameter review recommendation file.
- `re_evaluation_summary.csv`: Summary of re-evaluation directions, guardrails, order review types, and model review types.

These files recommend review. They do not overwrite policy parameters.

## 9. Scenario Optimization Outputs

- `inventory_scenarios.csv`: Generated scenario candidates.
- `inventory_scenario_results.csv`: Scored scenario rows with operational, risk penalty, constraint penalty, and penalty-adjusted cost fields.
- `inventory_optimization_recommendations.csv`: Selected scenario per SKU and savings interpretation.
- `inventory_optimization_summary.csv`: Scenario optimization summary.

Important scenario fields:

- `scenario_operational_cost`: Direct operating-cost estimate.
- `scenario_risk_penalty_cost`: Risk/review penalty estimate.
- `scenario_constraint_penalty_cost`: Constraint penalty estimate.
- `scenario_total_penalty_adjusted_cost`: Sum of the three buckets.
- `scenario_cost_reconciliation_ok`: Internal cost bucket check.
- `selected_hard_blocker_count`: Should remain zero for selected scenarios.

## 10. Final Manager-Facing Outputs

### `inventory_control_master_decisions.csv`

What it is: the main final SKU decision file.

Who uses it: inventory planners, operations managers, project reviewers, and future dashboard logic.

Key columns:

- `sku_id`, `product_name`, `category`
- `main_inventory_status`
- `selected_scenario_name`
- `final_decision_priority`
- `final_manager_status`
- `final_recommended_action`
- `blocking_review_action`
- `proposed_operational_action`
- `execution_owner`
- `review_owner`
- `final_review_severity`
- `operational_cost_saving_vs_baseline`
- `penalty_adjusted_saving_vs_baseline`
- `auto_apply_allowed`

How to interpret it: use this as the single best manager-facing summary for each SKU. It shows what the system recommends, whether review blocks execution, who owns review/execution, and what cost impact is estimated.

### `inventory_control_manager_dashboard.csv`

What it is: a flat file shaped for a future dashboard.

Who uses it: dashboard builders, managers, and reviewers who need fewer columns than the master file.

Key columns:

- `final_decision_priority`
- `final_manager_status`
- `final_recommended_action`
- `blocking_review_action`
- `proposed_operational_action`
- `execution_owner`
- `review_owner`
- `suggested_dashboard_badge`
- `suggested_dashboard_color_group`

How to interpret it: use this as the future UI source. It keeps the operational action visible even when a review gate blocks execution.

### `inventory_control_human_review_queue.csv`

What it is: mandatory review queue.

Who uses it: managers or reviewers who must approve an action before execution.

Key columns:

- `review_rank`
- `final_review_type`
- `final_review_severity`
- `mandatory_review_gates`
- `blocking_review_action`
- `proposed_operational_action`
- `next_review_step`

How to interpret it: every row here blocks execution until review is completed.

### `inventory_control_advisory_review_queue.csv`

What it is: non-blocking advisory review queue.

Who uses it: planners and managers who want to review warnings without stopping execution.

Key columns:

- `advisory_rank`
- `primary_review_type`
- `advisory_review_gates`
- `proposed_operational_action`
- `suggested_advisory_step`

How to interpret it: these rows are review-worthy but do not block action.

### `inventory_control_action_plan.csv`

What it is: action-oriented execution file.

Who uses it: planners, warehouse teams, procurement teams, and operations managers.

Key columns:

- `action_rank`
- `action_readiness`
- `final_recommended_action`
- `blocking_review_action`
- `proposed_operational_action`
- `execution_owner`
- `review_owner`
- `suggested_next_step`

How to interpret it: use `action_readiness` to separate ready-to-act rows from review-required, advisory, monitor-only, and no-action rows.

### `inventory_control_risk_register.csv`

What it is: one row per SKU-risk pair.

Who uses it: managers and analysts reviewing risk drivers.

Key columns:

- `risk_type`
- `risk_level`
- `risk_source`
- `risk_description`
- `mitigation_action`
- `risk_owner`
- `review_severity`
- `action_readiness`

How to interpret it: use this file to understand why a SKU was flagged and what mitigation is attached.

### `inventory_control_executive_summary.csv`

What it is: a management-level summary file.

Intended user: project reviewers, managers, and anyone who needs a compact summary rather than SKU-level detail.

Key columns:

- `summary_section`
- `metric_name`
- `metric_value`
- `metric_unit`
- `interpretation`
- `manager_note`

How to interpret it: use this file to review high-level counts, decision totals, review queue counts, savings totals, and management notes. It is not intended to replace SKU-level review when action is required.

### `inventory_control_kpi_summary.csv`

What it is: KPI-style summary of Phase 3 output quality and decision state.

Intended user: project reviewers, managers, and future dashboard/KPI pages.

Key columns:

- `kpi_category`
- `kpi_name`
- `kpi_value`
- `kpi_unit`
- `target_or_reference`
- `status`
- `explanation`

How to interpret it: use this file to track review rates, action readiness, validation-relevant indicators, and decision-support performance measures. KPI values are descriptive outputs, not automatic policy changes.

## 11. Validation Outputs

- `phase3_validation_report.txt`: readable validation report.
- `phase3_validation_summary.csv`: one row per validation check.
- `phase3_validation_issues.csv`: warnings, failures, and skipped checks only.

Current validation has zero failures. Warnings are known roadmap limitations.
