# Phase 4 Initialization Through Resource Master Data

Phase 4 production planning preparation has started. It now includes a simple advisory Master Production Schedule (MPS), MRP net component requirements, component-period MRP summary, pegging detail, and production resource master data. This is still not the full production planning engine.

Current initialization scope:

- Road Bike and Mountain Bike were added as future finished products in Phase 1 demand planning.
- BOM seed data lives in `data/phase4_bom.csv`.
- `core/master_production_schedule.py` plans Road Bike and Mountain Bike finished production by weekly period.
- The MPS uses Phase 1 finished-goods forecasts and Phase 3 finished-goods inventory.
- The MPS now rolls projected finished-goods inventory forward by SKU and period, so the same opening inventory is not repeatedly subtracted every week.
- Planned production is based on weekly net finished-goods requirements from that rolling projected balance.
- `core/bom_explosion_bridge.py` converts MPS planned production into advisory component requirements when MPS output is available.
- `core/mrp_net_requirements.py` nets gross BOM component requirements against component inventory.
- MRP produces advisory net component requirements before procurement review.
- Component-period MRP summary prevents shared component inventory from being allocated based only on finished-SKU row order.
- MRP pegging detail shows which finished product demand caused each component requirement.
- Resource master data now defines workstations, machines, labor resources, and a simple resource calendar.
- The resource data will later support routing/workflow, capacity feasibility, queues, bottlenecks, quality, and maintenance.
- If MPS output is missing or empty, BOM explosion falls back to the original forecast-based initialization bridge.
- Phase 3 can produce an advisory inventory availability check using component-period MRP summary when available.
- Phase 2 preserves the component-period basis in advisory supplier coverage checks.
- Phase 4 validation writes JSON evidence and a text report under `outputs/`.

Run order:

1. Run Phase 1 forecasts.
2. Run Phase 4 MPS.
3. Run Phase 4 BOM explosion from MPS planned production.
4. Run Phase 4 MRP net component requirements, component-period summary, and pegging detail.
5. Validate Phase 4 resource master data.
6. Run Phase 3 component inventory checks.
7. Run Phase 2 component supplier checks.

The Phase 4 bridges are optional-safe. If a bridge file is missing or fails, Phase 2 and Phase 3 print a warning and continue their existing core pipelines.

Guardrails:

- Outputs are advisory only.
- No purchase orders are created.
- No production orders are created.
- No inventory is consumed or auto-reserved.
- Simulation is a separate future phase.
- Future production release flags should default to `production_order_release_allowed = False`.

Not implemented yet:

- Full MPS governance beyond the advisory rolling-balance calculation.
- Full MRP execution, order release, and procurement execution.
- Routing/workflow.
- Capacity feasibility, utilization, and bottleneck analysis.
- Queues, quality, maintenance, scheduling, layout, or simulation.
- Production order release.

Next likely Phase 4 feature:

- The next real feature after this resource master data step is routing/workflow, but it is not implemented here.

Review bundle:

- `create_phase4_review_bundle.py` generates `phase4_step3a_resources_review_bundle.zip` at the project root for external review.
- The bundle preserves project-relative folder structure and excludes cache, bytecode, virtual environment, and zip artifacts.
