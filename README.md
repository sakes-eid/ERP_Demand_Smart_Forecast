[README.md](https://github.com/user-attachments/files/28854138/README.md)
# ERP-Like Supply Chain Planning Project

This project is an advisory supply chain planning prototype organized into independently runnable phases. The current implementation connects demand planning, supplier capability, inventory requirements, supplier-constrained allocation, warehouse validation, and integrated replenishment decisions through explicit bridge files.

## Current Integrated Architecture

```text
Phase 1 Demand Planning
-> Phase 2 Supply Capability and Inbound Bridge
-> Phase 3 Authoritative Inventory Requirement
-> Phase 2 Supplier-Constrained Allocation
-> Phase 3 Inventory and Warehouse Validation
-> Integrated Advisory Replenishment Decisions
```

The phases do not directly execute each other. Integration is coordinated by `planning_orchestrator.py`, shared CSV bridge files in `shared/outputs/`, and validation evidence in `shared/validation/`.

## Phase Ownership

| Component | Owns |
| --- | --- |
| Phase 1 Demand Planning | Forecasts, uncertainty, bias, urgency, seasonality, events, and stockout-censored demand signals |
| Phase 2 Supply Capability | Supplier capability, inbound POs, MOQ, yield, capacity, cost, lead time, and supplier allocation |
| Phase 3 Inventory Control | Physical inventory, usable inventory, expiry, inventory policies, safety stock, reorder point, warehouse constraints, and net replenishment requirement |
| Orchestrator | Cross-phase sequencing and consolidated advisory replenishment decisions |

## Key Bridge Outputs

| File | Purpose |
| --- | --- |
| `shared/outputs/phase2_supply_capability_context.csv` | SKU-supplier capability, cost, lead time, capacity, and inbound context |
| `shared/outputs/phase2_inbound_supply_summary.csv` | SKU-level confirmed and uncertain inbound supply |
| `shared/outputs/phase3_procurement_requirement_context.csv` | Phase 3 authoritative net replenishment requirement |
| `shared/outputs/phase2_procurement_allocation_context.csv` | Supplier-constrained allocation detail |
| `shared/outputs/phase2_procurement_allocation_summary.csv` | SKU-level allocation summary |
| `shared/outputs/phase3_allocation_validation.csv` | Inventory, warehouse, policy, and service validation of allocations |
| `shared/outputs/integrated_replenishment_decisions.csv` | Consolidated advisory replenishment decisions |

The main external validation artifact is:

```text
shared/validation/integrated_validation_evidence.json
```

## Phase 3 Role-Based UI

Phase 3 includes a polished Streamlit advisory dashboard with simple role selection, a run-status header, role-aware column visibility, task cards, manager overview metrics, validation summaries, and persistent safety messaging:

- `Manager`: operational task view plus planning, cost, risk, review queue, allocation, warehouse, and validation details.
- `Employee / Warehouse Staff`: simplified operational views for product lookup, tasks, expiry checks, and delivery/receiving.

Both roles use the same shared task dataset, `phase 3/outputs/inventory_employee_task_view.csv`; the UI changes column visibility by role rather than creating contradictory datasets. The dashboard is advisory only and does not execute purchase orders, supplier changes, inventory updates, policy changes, or warehouse changes.

## Essential KPI Additions

The current KPI layer adds decision-useful metrics without changing planning decisions:

| Area | Added KPIs | Main outputs |
| --- | --- | --- |
| Phase 1 | Forecast value added, 7/30/90-day backtest WAPE, prediction interval coverage, forecast stability from distinct future-forecast quantity snapshots | `phase 1/outputs/phase1_forecast_kpis.csv`, `phase 1/outputs/phase1_demand_planning_context.csv` |
| Phase 2 | PO-level OTIF, PO-level fill rate, weighted procurement cost per usable unit, requirement coverage, weighted capacity utilization, supplier concentration risk | `phase 2/outputs/supplier_performance.csv`, `phase 2/outputs/phase2_procurement_kpi_summary.csv`, shared allocation outputs |
| Phase 3 | 90-day outbound-to-current-inventory proxy, days inventory on hand, policy-threshold excess/dead-stock/expiry exposure rates, reconciliation accuracy, unavailable formal fill-rate/stockout/FEFO flags | `phase 3/outputs/inventory_kpi_summary.csv`, `phase 3/outputs/inventory_control_manager_dashboard.csv` |
| Integrated | End-to-end requirement coverage rate and planning exception rate | `shared/validation/integrated_validation_evidence.json` |

The KPI layer is reporting-only. It does not alter forecasts, supplier choices, allocation logic, inventory policy, or execution safety flags. Unavailable KPI values are marked with explicit method or data-quality fields instead of silent fallback values.

## Latest Integrated Validation

| Metric | Value |
| --- | --- |
| Overall status | `WARNING` |
| PASS | `58` |
| WARNING | `3` |
| FAIL | `0` |
| SKIPPED | `0` |
| Convergence | `CONVERGED_WITH_REVIEW` |
| Analytical downstream safe | `True` |
| Planning downstream safe | `False` |
| Execution downstream safe | `False` |

The remaining integrated warnings are intentional review conditions, not hidden allocator defects:

| Warning | Affected SKUs | Meaning |
| --- | --- | --- |
| `UNALLOCATED_REQUIREMENT_REMAINS` | `SKU-COF-001`, `SKU-TEA-002` | Supplier capacity cannot cover the full requested quantity |
| `ALLOCATION_ADJUSTMENT_REQUIRED` | `SKU-COF-001`, `SKU-TEA-002` | Phase 3 keeps the shortage visible for review |
| `FALLBACK_COST_OR_TIMING_ASSUMPTIONS` | all 10 SKUs | Some cost or timing assumptions remain fallback-based |

Current genuine aggregate supplier-capacity shortfalls:

| SKU | Requested | Allocated | Unallocated |
| --- | ---: | ---: | ---: |
| `SKU-COF-001` | `1880.00` | `1491.43` | `388.57` |
| `SKU-TEA-002` | `880.00` | `814.28` | `65.72` |

These shortages are preserved as review conditions. The system does not force allocation by hiding capacity limits.

## Safety Rules

- `auto_apply_allowed = False`
- `purchase_order_creation_allowed = False`
- `procurement_execution_ready_flag = False`
- `allocation_execution_allowed = False`
- Allocation outputs are advisory only.
- No supplier, inventory, policy, warehouse, or purchase-order mutation occurs.
- Feasibility fields describe technical feasibility, not execution permission.

## How To Run

From the project root:

```powershell
python "phase 1/main.py"
python "phase 2/main.py"
python "phase 3/main.py"
python planning_orchestrator.py
python validate_integrated_planning.py
python "phase 2/validate_phase2_procurement_context.py"
python "phase 3/validate_phase3.py"
python -m compileall .
```

## Current Roadmap

1. Treat Phase 3 as wrapped as an advisory backend plus role-based UI foundation.
2. Revisit remaining Phase 1, Phase 2, and Phase 3 improvements.
3. Begin Phase 4 production/BOM planning.
4. Later add logistics, finance, approved execution workflow, and the final total-cost engine.
