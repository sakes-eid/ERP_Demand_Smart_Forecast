# Phase 4 Initialization and MPS Step 1B

Phase 4 production planning preparation has started, and Step 1B now includes a simple advisory Master Production Schedule (MPS) with a rolling finished-goods inventory balance. This is still not the full production planning engine.

Current initialization scope:

- Road Bike and Mountain Bike were added as future finished products in Phase 1 demand planning.
- BOM seed data lives in `data/phase4_bom.csv`.
- `core/master_production_schedule.py` plans Road Bike and Mountain Bike finished production by weekly period.
- The MPS uses Phase 1 finished-goods forecasts and Phase 3 finished-goods inventory.
- The MPS now rolls projected finished-goods inventory forward by SKU and period, so the same opening inventory is not repeatedly subtracted every week.
- Planned production is based on weekly net finished-goods requirements from that rolling projected balance.
- `core/bom_explosion_bridge.py` converts MPS planned production into advisory component requirements when MPS output is available.
- If MPS output is missing or empty, BOM explosion falls back to the original forecast-based initialization bridge.
- Phase 3 can produce an advisory inventory availability check for BOM components.
- Phase 2 can produce an advisory supplier coverage check for BOM component shortages.
- Phase 4 validation writes JSON evidence and a text report under `outputs/`.

Run order:

1. Run Phase 1 forecasts.
2. Run Phase 4 MPS.
3. Run Phase 4 BOM explosion from MPS planned production.
4. Run Phase 3 component inventory checks.
5. Run Phase 2 component supplier checks.

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
- MRP/netting.
- Routing, machines, queues, quality, maintenance, scheduling, layout, or simulation.
- Production order release.

Next likely Phase 4 feature:

- The next real feature after this rolling-balance hardening step is a richer MPS layer, but it is not implemented here.

Review bundle:

- `create_phase4_review_bundle.py` generates `phase4_mps_step1b_review_bundle.zip` at the project root for external review.
- The bundle preserves project-relative folder structure and excludes cache, bytecode, virtual environment, and zip artifacts.
