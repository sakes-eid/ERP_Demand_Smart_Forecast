# Phase 4 Initialization Through Estimated Queue Pressure

Phase 4 production planning preparation has started. It now includes a simple advisory Master Production Schedule (MPS), MRP net component requirements, component-period MRP summary, pegging detail, production resource master data, routing/workflow master data, CRP feasibility for workstations, machine types, and labor skills, capacity feasibility summary, bottleneck candidates, and estimated queue pressure / WIP risk visibility. This is still not the full production planning engine.

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
- Routing is the ERP version of the production flowchart.
- Road Bike and Mountain Bike now have different advisory routings.
- Parallel subassembly branches are included for both products.
- Final assembly acts as the join point for the parallel branches.
- Mountain Bike routing includes fork and suspension prep; Road Bike routing does not.
- Routing operation resources reference the workstations, machine types, and labor skills from Step 3A.
- `core/routing_master_data.py` validates routing structure, resource references, fork/join groups, and circular dependencies.
- `outputs/phase4_routing_flow_summary.csv` provides a human-readable review summary of each routing.
- `core/capacity_load.py` calculates advisory workstation-level capacity load from MPS planned production and routing operation times.
- Available workstation capacity is based on the workstation rows in the resource calendar.
- Machine-type capacity checks machine/tool constraints from routing operation resources and `machines.csv`.
- Labor-skill capacity checks worker skill constraints from routing operation resources and `labor_resources.csv`.
- The capacity constraint bridge links workstation overloads to machine and labor causes.
- Step 4C summarizes CRP evidence across workstation, machine, and labor layers.
- `outputs/phase4_capacity_feasibility_summary.csv` answers whether each weekly plan is capacity-feasible.
- `outputs/phase4_bottleneck_candidate_summary.csv` identifies likely bottleneck candidates using capacity evidence only.
- Bottleneck candidates are not final queue-confirmed bottlenecks.
- `outputs/phase4_capacity_manager_review_queue.csv` is an advisory-only manager review list and does not trigger automatic actions.
- `core/queue_pressure.py` estimates planned queue pressure and WIP risk by workstation and period.
- Queue pressure is derived from capacity overload, utilization, capacity gaps, labor warnings, machine/labor constraints, and routing join pressure.
- These queue outputs are planning estimates, not actual measured queue lengths or real wait times.
- Actual queue measurement would require shop-floor execution timestamps or simulation, which are not implemented here.
- Final Assembly may appear as a high queue-risk workstation because Road Bike and Mountain Bike parallel branches merge there.
- Bottleneck candidates are supported by estimated queue-pressure evidence, but they are still not simulation-confirmed bottlenecks.
- Labor capacity uses stricter labor-specific thresholds because workers need operating buffer for breaks, fatigue, variability, quality checks, coordination, and disruptions.
- Labor utilization above 80% is marked `HIGH_UTILIZATION_WARNING`.
- Labor utilization above 95% is treated as a hard `OVERLOADED` condition.
- Workstation capacity output now states its capacity basis explicitly.
- Current workstation capacity is based on `SINGLE_STATION_CALENDAR`.
- `WORKSTATION_ONLY` overload means the workstation calendar layer is overloaded; it does not necessarily mean the machine-type or labor-skill layers are overloaded.
- Parallel operations add load to their own workstations in the same period, but they are not sequenced or scheduled yet.
- Capacity statuses include `FEASIBLE`, `NEAR_CAPACITY`, `HIGH_UTILIZATION_WARNING`, `OVERLOADED`, `NO_CAPACITY_RECORD`, `NO_LOAD`, and `REVIEW_REQUIRED`.
- `outputs/phase4_capacity_operation_load_detail.csv` provides operation-level load detail for validation and review only.
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
6. Validate Phase 4 routing/workflow master data.
7. Build Phase 4 workstation, machine-type, and labor-skill capacity load / CRP feasibility.
8. Build Phase 4 capacity feasibility summary and bottleneck candidates.
9. Build Phase 4 estimated queue pressure and WIP risk visibility.
10. Run Phase 3 component inventory checks.
11. Run Phase 2 component supplier checks.

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
- Detailed capacity scheduling, utilization dashboards, and bottleneck ranking analysis.
- Step 4C provides bottleneck candidates from CRP evidence; detailed bottleneck ranking remains future work.
- Confirmed bottlenecks from queue behavior.
- Real queue measurement, exact wait-time tracking, queue logic, or queue simulation.
- Quality, maintenance, scheduling, layout, or simulation.
- Production order release.

Next likely Phase 4 feature:

- The next real feature after this estimated queue-pressure step is likely capacity relief recommendations or queue-aware bottleneck confirmation, but it is not implemented here.

Review bundle:

- `create_phase4_review_bundle.py` generates `phase4_step5a_queue_pressure_review_bundle.zip` at the project root for external review.
- The bundle preserves project-relative folder structure and excludes cache, bytecode, virtual environment, and zip artifacts.
