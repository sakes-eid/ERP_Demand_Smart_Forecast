# Phase 3 - Inventory Control Engine

Phase 3 provides inventory control and manager decision support for the integrated planning system. It combines physical inventory, usable inventory, batch expiry, warehouse constraints, inventory policy, scenario optimization, and final manager-facing decisions.

Phase 3 is a validated advisory backend module. It does not create purchase orders, mutate inventory quantities, change suppliers, overwrite policy parameters, or execute warehouse changes.

## Current Capabilities

- Physical and usable inventory calculation.
- Batch expiry and traceability handling.
- Quarantine and near-expiry treatment.
- ABC, XYZ, FSN, vitality, perishability, and seasonality classification.
- SKU-specific service levels.
- Safety stock, reorder point, EOQ, and inventory policy outputs.
- Warehouse slotting and capacity analysis.
- FEFO and space-utilization logic.
- Scenario optimization with operational, risk, and constraint cost layers.
- Manager decision outputs with mandatory and advisory review separation.
- Authoritative replenishment requirement bridge for integrated planning.
- Validation of Phase 2 allocations against inventory, warehouse, service, and policy constraints.
- Essential inventory KPI output for future UI use.
- Polished role-based Streamlit dashboard for manager and employee/warehouse-staff views.

## Local Validation Result

Latest Phase 3 validation:

- Overall: `WARNING`
- PASS: `208`
- WARNING: `11`
- FAIL: `0`
- SKIPPED: `1`

The `WARNING` status reflects known limitations and planned improvements. There are no failed Phase 3 validation checks.

## Key Outputs

| Output | Purpose |
| --- | --- |
| `outputs/inventory_control_master_decisions.csv` | Main final SKU decision output |
| `outputs/inventory_control_manager_dashboard.csv` | Flat manager dashboard data |
| `outputs/inventory_control_human_review_queue.csv` | Mandatory review queue |
| `outputs/inventory_control_advisory_review_queue.csv` | Non-blocking advisory review queue |
| `outputs/inventory_control_action_plan.csv` | Action-oriented advisory planning output |
| `outputs/inventory_control_risk_register.csv` | One row per SKU-risk pair |
| `outputs/inventory_control_executive_summary.csv` | Management summary metrics |
| `outputs/inventory_control_kpi_summary.csv` | KPI table |
| `outputs/inventory_kpi_summary.csv` | One row per SKU inventory KPI summary |
| `outputs/inventory_employee_task_view.csv` | Shared operational task dataset for manager and employee UI views |
| `outputs/phase3_validation_report.txt` | Local validation report |
| `outputs/phase3_wrap_up_summary.txt` | Concise Phase 3 closure note |
| `shared/outputs/phase3_procurement_requirement_context.csv` | Authoritative replenishment requirement bridge |
| `shared/outputs/phase3_allocation_validation.csv` | Validation of Phase 2 supplier allocations |

## Integrated Role

Phase 3 owns the authoritative inventory-side requirement:

- physical inventory
- usable inventory
- expired, quarantined, near-expiry, and trace-only inventory treatment
- safety stock, reorder point, policy, and service constraints
- warehouse receiving and capacity validation
- net replenishment requirement

Phase 2 owns supplier capability and allocation. In integrated mode, Phase 3 sends its requested usable replenishment requirement to Phase 2, then validates Phase 2 allocation outputs before the orchestrator produces consolidated advisory decisions.

## Manager Decision Support

The final manager-facing layer separates:

- blocking review actions
- proposed operational actions
- review owners
- execution owners
- advisory warnings
- action readiness

Outputs remain advisory. `auto_apply_allowed` remains `False`.

## Role-Based Streamlit UI

Run the dashboard from the Phase 3 folder:

```bash
streamlit run app.py
```

Or from the project root:

```powershell
streamlit run "phase 3/app.py"
```

The first screen is a simple role selector. It does not implement authentication, passwords, or user accounts. The dashboard header shows the selected role, latest integrated run status where available, last generated timestamp where available, and read-only advisory mode.

- Manager view: executive overview, operational task view, inventory decisions, replenishment and allocation, review queues, expiry/dead-stock/overstock, warehouse/location, and validation/data-quality pages. Manager pages include planning, cost, risk, allocation, and validation detail in tables and expanders.
- Employee / Warehouse Staff view: product lookup, operational tasks, expiry/stock checks, and delivery/receiving pages. Employee pages show task cards, simplified status labels, operational instructions, location, stock, next delivery, and review flags.

Both roles use `outputs/inventory_employee_task_view.csv` as the shared operational task base. Manager pages expose additional planning, cost, risk, validation, and decision details. Employee pages hide supplier scoring, cost, validation internals, scenario optimizer details, and policy formulas.

The UI is read-only and advisory. It does not include Create PO, Apply Policy, Change Supplier, Update Inventory, Change Warehouse Assignment, or similar execution controls.

## Inventory KPIs

Phase 3 now publishes `outputs/inventory_kpi_summary.csv`, one row per SKU. The most manager-relevant fields are also merged into `inventory_control_manager_dashboard.csv` for the future UI contract.

Added KPIs:

- 90-day outbound-to-current-inventory proxy, exposed as `outbound_to_current_inventory_ratio_90d`.
- Days inventory on hand and status.
- Excess inventory rate only when a valid positive policy max-stock threshold exists.
- Dead-stock rate.
- 30-day expiry exposure rate.
- Inventory reconciliation accuracy rate.
- Unit fill-rate, stockout-rate, and FEFO-compliance availability fields.

The outbound/current-inventory ratio is not formal financial inventory turnover because average inventory and COGS history are not yet available. The compatibility turnover field is marked `PROXY_NOT_FORMAL_TURNOVER`.

Formal unit fill rate, historical stockout rate, and FEFO compliance are marked unavailable where event-level fulfillment, stockout, or expiry-controlled issue evidence is not present. Excess inventory is also unavailable when no valid max-stock policy threshold exists. The system does not infer these KPIs from current stock alone.

## Current Integrated Context

The integrated project currently validates with:

- Overall status: `WARNING`
- Convergence: `CONVERGED_WITH_REVIEW`
- Integrated FAIL count: `0`
- Analytical downstream safe: `True`
- Planning downstream safe: `False`
- Execution downstream safe: `False`

The remaining integrated unallocated requirements for `SKU-COF-001` and `SKU-TEA-002` are genuine aggregate supplier-capacity shortfalls from Phase 2, not Phase 3 allocator defects. Phase 3 preserves them as review conditions.

## Updated Limitations

- Supplier return-policy fields are available through Phase 2 bridges, but automated return execution is not implemented.
- Backorder aging exists in Phase 2, but deeper batch, inventory, and forecast feedback integration remains future work.
- Phase 3 internal scenario labels may remain strategy-level, while supplier IDs and quantities come from Phase 2 allocation bridges.
- Stockout-censored demand correction using operational evidence is not yet implemented.
- Scenario optimization is rule-based, not simulation-based.
- Re-evaluation is rule-based, not yet a historical learning loop.
- Formal fill-rate, stockout-rate, and FEFO-compliance KPIs require deeper operational event history.
- No Phase 4 BOM or production logic exists yet.
- Phase 3 UI is a read-only Streamlit advisory dashboard; execution workflows are not implemented.
- No automatic policy, inventory, warehouse, supplier, or purchase-order mutation occurs.

Phase 3 is wrapped as a stable advisory backend plus role-based UI foundation. Remaining warnings and deferred features stay visible in the UI, validation report, and `outputs/phase3_wrap_up_summary.txt`.

## How To Run

From the Phase 3 folder:

```bash
python main.py
python validate_phase3.py
python -m compileall .
```

From the project root:

```powershell
python "phase 3/main.py"
python "phase 3/validate_phase3.py"
python validate_integrated_planning.py
streamlit run "phase 3/app.py"
```

## Safety Rules

- No automatic purchase order creation.
- No inventory quantity mutation.
- No automatic supplier changes.
- No automatic service-level or policy overwrite.
- No automatic warehouse assignment mutation.
- Mandatory and advisory review logic remains explicit.
- `auto_apply_allowed` remains `False`.
