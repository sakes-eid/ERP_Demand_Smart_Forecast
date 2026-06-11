# Phase 2 - Supply Capability and Procurement Intelligence

Phase 2 provides the supply-side planning layer for the project. It evaluates suppliers, supplier-SKU options, inbound purchase order context, capacity, cost, lead time, yield, MOQ, order multiples, backorders, and supplier-constrained allocation.

All Phase 2 outputs remain advisory. The module does not create purchase orders, change suppliers, or execute allocations.

## Current Capabilities

- Supplier performance and trend analysis.
- Supplier-SKU scoring and procurement recommendations.
- Landed cost and quality-adjusted cost.
- Lead time, MOQ, order multiple, batch size, and yield handling.
- Explicit per-order and horizon capacity checks.
- Confirmed inbound PO context.
- Return, expedite, and split-delivery capability fields.
- Order-line/SKU-level backorder aging.
- Supplier strategy summaries.
- Phase 1 demand planning context integration.
- Phase 3 authoritative requirement consumption in integrated mode.
- Supplier-constrained allocation against requested usable quantity.
- Expected first and final arrival dates for allocation rows.
- Meaningful allocation warning semantics for infeasible or partial allocations.
- Essential procurement KPIs for supplier performance, cost, coverage, capacity utilization, and concentration risk.

## Standalone and Integrated Modes

### Standalone Mode

When Phase 3 bridge files are not available, Phase 2 may use provisional requirement logic for supplier capability analysis. This mode is useful for supply-side review, supplier scoring, and capability preparation.

### Integrated Mode

When the Phase 3 requirement bridge exists, Phase 2 uses:

```text
net_replenishment_requirement_units
```

as the authoritative requested usable quantity. Integrated allocation is supplier-constrained and may leave shortages visible when aggregate supplier capacity is insufficient.

## Main Outputs

| Output | Purpose |
| --- | --- |
| `outputs/supplier_performance.csv` | Supplier KPI and performance output |
| `outputs/supplier_trends.csv` | Supplier trend analysis |
| `outputs/supplier_sku_scores.csv` | SKU-supplier score table |
| `outputs/procurement_recommendations.csv` | Advisory procurement recommendation output |
| `outputs/backorder_aging_detail.csv` | One row per backorder/order-line record |
| `outputs/backorder_aging_summary.csv` | One row per SKU backorder summary |
| `outputs/phase2_procurement_capability_context.csv` | One row per SKU-supplier option |
| `outputs/phase2_supplier_strategy_summary.csv` | One row per SKU supplier strategy summary |
| `outputs/phase2_procurement_kpi_summary.csv` | Compact procurement KPI summary |
| `shared/outputs/phase2_supply_capability_context.csv` | Shared SKU-supplier capability bridge |
| `shared/outputs/phase2_inbound_supply_summary.csv` | Shared SKU inbound supply bridge |
| `shared/outputs/phase2_procurement_allocation_context.csv` | Shared allocation detail bridge |
| `shared/outputs/phase2_procurement_allocation_summary.csv` | Shared allocation summary bridge |

## Allocation Semantics

- `allocation_feasible_flag` means the allocation is technically feasible under supplier and capacity constraints.
- `allocation_execution_allowed` remains `False`.
- Technical feasibility does not imply execution permission.
- `purchase_order_creation_allowed` remains `False`.
- Supplier switches and purchase orders are never auto-applied.

Current integrated capacity review cases:

| SKU | Requested | Allocated | Unallocated | Reason |
| --- | ---: | ---: | ---: | --- |
| `SKU-COF-001` | `1880.00` | `1491.43` | `388.57` | Genuine aggregate supplier-capacity shortfall |
| `SKU-TEA-002` | `880.00` | `814.28` | `65.72` | Genuine aggregate supplier-capacity shortfall |

These shortages are intentionally preserved for review.

## Procurement KPIs

Phase 2 now publishes the following non-executing KPIs:

- Supplier OTIF rate and eligible delivery counts in `supplier_performance.csv`, calculated after aggregating receipts to one PO-level record.
- Supplier fill rate using PO-level accepted quantity divided by ordered quantity, so multiple receipt rows do not repeat the ordered quantity.
- Weighted total procurement cost per usable unit: total procurement cost across active allocations divided by total usable allocated quantity.
- Requirement coverage and unallocated requirement rates on allocation summaries.
- Supplier capacity utilization at allocation-row level, plus weighted aggregate utilization: total allocated usable quantity divided by total relevant supplier horizon capacity.
- Top supplier allocation share and concise concentration-risk status.

The Streamlit dashboard surfaces these KPIs in Overview, Supplier Performance, Procurement Recommendations, Risk & Cost Analysis, and Feasibility Review. Feasibility still does not mean execution permission: `allocation_execution_allowed` remains `False`.

## Phase 1 Demand Integration

Phase 2 first consumes:

```text
phase 1/outputs/phase1_demand_planning_context.csv
```

This bridge provides future demand horizons, demand urgency, uncertainty, bias, stockout-censored demand signals, seasonality, event context, and demand warning codes. These fields affect procurement risk, strategy review, and supplier capability interpretation, but they do not automatically change suppliers or create orders.

## Phase 3 Requirement Integration

In integrated mode, Phase 3 owns the authoritative replenishment requirement. Phase 2 allocates supplier capacity against Phase 3's requested usable quantity and publishes allocation bridges back to Phase 3 for inventory, warehouse, service-level, and policy validation.

## Local Validation Result

Latest Phase 2 validation:

- Overall: `WARNING`
- PASS: `87`
- WARNING: `10`
- FAIL: `0`

The warnings reflect advisory limitations and review conditions, not failed validation checks.

## Remaining Limitations

- Payment terms are recorded but not yet financially modeled.
- Some suppliers lack returns, expedite, or split-delivery capabilities.
- Demo batch references remain placeholders for deeper traceability.
- Supplier selection remains advisory.
- No automatic purchase order creation or supplier switching occurs.

## How To Run

From the Phase 2 folder:

```bash
python main.py
python validate_phase2_procurement_context.py
python -m compileall .
```

From the project root:

```powershell
python "phase 2/main.py"
python "phase 2/validate_phase2_procurement_context.py"
```
