# Phase 4 Initialization Through Production Flow Visibility

Phase 4 production planning preparation has started. It now includes a simple advisory Master Production Schedule (MPS), MRP net component requirements, component-period MRP summary, pegging detail, production resource master data, shared workforce/crew master data, routing/workflow master data, CRP feasibility for workstations, machine types, and labor skills, capacity feasibility summary, bottleneck candidates, estimated queue pressure / WIP risk visibility, bottleneck visibility summaries, a production flow view, planning-based quality/workstation performance trends, and quality-adjusted capacity impact estimates. This is still not the full production planning engine.

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
- Step 7A adds a shared workforce, crew, skill, and machine authorization layer.
- The workforce layer sits under `shared/` because production, maintenance, warehouse, delivery, and decision-support logic may all need it later.
- Active crews are separated into `PRODUCTION` and `MAINTENANCE`.
- Future crew types such as `WAREHOUSE` and `DELIVERY` are schema-supported but inactive for now.
- Crew skills and machine authorizations define who can operate, set up, maintain, or repair machines.
- Step 7A now supports limited light autonomous maintenance by production crews.
- Production crews can perform light tasks such as cleaning, inspection, lubrication/oil change, tightening, basic adjustment, and abnormality reporting.
- Production crews cannot perform medium or heavy maintenance, corrective repair, breakdown repair, overhaul, electrical repair, or complex mechanical repair.
- Maintenance crews own medium/heavy maintenance, troubleshooting, repair, breakdown recovery, and overhaul.
- Crew role separation is explicit in the Phase 4 workforce context output.
- `phase 4/outputs/phase4_workforce_resource_context.csv` gives Phase 4 a clean advisory view of production and maintenance crews.
- Step 7A does not schedule workers, does not change production capacity calculations, and does not create maintenance work orders.
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
- `core/bottleneck_visibility.py` combines CRP capacity evidence with estimated queue/WIP pressure evidence.
- Bottleneck visibility outputs are bottleneck candidates, not final measured bottlenecks.
- Confirmation status is `PLANNING_EVIDENCE_ONLY_NOT_SIMULATION_CONFIRMED`.
- Final Assembly may appear as the top bottleneck candidate because it combines high load, queue pressure, and parallel branch merge pressure.
- `core/production_flow_view.py` creates UI-ready production flow data, but no UI is built yet.
- The production flow view combines routing order, parallel branches, queue-pressure evidence, and bottleneck-visibility evidence.
- Flow risks are planning-based and not simulation-confirmed.
- Final Assembly may appear as a high-risk flow step because parallel branches merge there and capacity/queue evidence is high.
- `core/quality_trends.py` analyzes synthetic/planning-based quality history for defects, rework, scrap, and processing-time trends.
- Quality history uses `SYNTHETIC_PLANNING_HISTORY` or `PLANNING_ASSUMPTION_HISTORY`; it is not claimed as shop-floor-confirmed measurement.
- Workstation performance trend summaries classify quality trend, processing-time trend, speed trend, and capacity-risk trend as `IMPROVING`, `STABLE`, `WORSENING`, or `INSUFFICIENT_DATA`.
- Step 6A does not adjust MPS, BOM, MRP, or capacity math.
- `core/quality_adjusted_capacity.py` estimates how defects, rework, scrap, and worsening processing-time trends affect required capacity and bottleneck pressure.
- Step 6B outputs are planning estimates only with confirmation status `PLANNING_ESTIMATE_ONLY_NOT_EXECUTION_CONFIRMED`.
- Step 6B includes explicit defect disposition reconciliation.
- Defects are split into reworkable defects, direct scrap, discount/review units, and other defect disposition units.
- Rework can succeed or fail, and final expected good units plus total expected loss units are reconciled back to planned production.
- Quality-adjusted capacity compares original workstation load to estimated rework and processing-time trend impacts.
- Quality material loss exposure is advisory-only, uses total expected loss units, and explicitly flags that MRP is not changed.
- Step 6B does not change MPS quantities, BOM quantities, MRP quantities, inventory, or execution orders.
- Step 6B does not create MPS, BOM, MRP, procurement, inventory, scheduling, simulation, or execution actions.
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
6. Validate shared workforce, crew, skill, and machine authorization master data.
7. Validate Phase 4 routing/workflow master data.
8. Build Phase 4 workstation, machine-type, and labor-skill capacity load / CRP feasibility.
9. Build Phase 4 capacity feasibility summary and bottleneck candidates.
10. Build Phase 4 estimated queue pressure and WIP risk visibility.
11. Build Phase 4 bottleneck visibility summary.
12. Build Phase 4 production flow and queue-bottleneck flow view.
13. Build Phase 4 quality and workstation performance trend detection.
14. Build Phase 4 quality-adjusted capacity impact estimates.
15. Run Phase 3 component inventory checks.
16. Run Phase 2 component supplier checks.

The Phase 4 bridges are optional-safe. If a bridge file is missing or fails, Phase 2 and Phase 3 print a warning and continue their existing core pipelines.

Guardrails:

- Outputs are advisory only.
- No purchase orders are created.
- No production orders are created.
- No maintenance work orders are created.
- No inventory is consumed or auto-reserved.
- No workforce, maintenance, production, or delivery scheduling is created.
- Simulation is a separate future phase.
- Future production release flags should default to `production_order_release_allowed = False`.

Not implemented yet:

- Full MPS governance beyond the advisory rolling-balance calculation.
- Full MRP execution, order release, and procurement execution.
- Detailed capacity scheduling and utilization dashboards.
- Step 5B provides bottleneck visibility from CRP and estimated queue evidence; final measured bottleneck confirmation remains future work.
- Step 5C provides production-flow and queue-bottleneck flow-view data; Streamlit/UI screens remain future work.
- Step 6B provides planning-based quality-adjusted capacity impact; quality-adjusted MRP remains future work.
- Step 7A provides shared workforce master data and authorizations; crew scheduling and maintenance planning remain future work.
- Confirmed bottlenecks from real queue behavior.
- Real queue measurement, exact wait-time tracking, queue logic, or queue simulation.
- Shop-floor-confirmed quality measurement, quality-adjusted MRP, maintenance work orders, crew scheduling, layout, or simulation.
- Production order release.

Next likely Phase 4 feature:

- The next real feature after this workforce master-data step is likely maintenance master data or crew-aware capacity planning, but neither is implemented here.

Review bundle:

- `create_phase4_review_bundle.py` generates `phase4_step7a_workforce_review_bundle.zip` at the project root for external review.
- The bundle preserves project-relative folder structure and excludes cache, bytecode, virtual environment, and zip artifacts.
