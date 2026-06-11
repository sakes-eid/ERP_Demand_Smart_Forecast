# Phase 3 Inventory Control

## 1. Purpose Of Phase 3

Phase 3 is the inventory control module of the supply chain planning project. It combines inventory records, demand context, supplier context, warehouse constraints, batch expiry, costs, scenario scoring, and final manager-facing decision outputs.

Phase 3 is a validated decision-support module. It is not yet a production ERP system.

## 2. End-To-End Pipeline

The pipeline runs through `main.py` and follows this sequence:

1. Load or create local Phase 3 input files.
2. Clean inventory, batch, movement, warehouse, location, and SKU storage data.
3. Load Phase 1 demand context and Phase 2 procurement context.
4. Build inventory planning context.
5. Classify SKUs.
6. Build SKU-specific service levels.
7. Select inventory policies.
8. Calculate inventory policy parameters.
9. Build inventory status and action signals.
10. Estimate inventory costs.
11. Build warehouse slotting and batch slotting outputs.
12. Build warehouse visualization data.
13. Run re-evaluation logic.
14. Generate and score inventory scenarios.
15. Consolidate final manager-facing decisions.

## 3. Data Inputs

Phase 3 uses local data in `data/` and context files from earlier phases when available:

- Inventory master records.
- Inventory batches.
- Inventory movements.
- Warehouse layout.
- Storage locations.
- SKU storage requirements.
- Phase 1 demand and forecast context.
- Phase 2 supplier and procurement context.

## 4. Processing Steps

Each processing step writes its own output files. This keeps the module auditable because intermediate results can be reviewed without rerunning the full decision layer.

The pipeline does not overwrite Phase 1 or Phase 2 outputs. Phase 3 consumes those contexts as inputs.

## 5. Classification Logic

The classification step assigns operational classes to each SKU:

- ABC class for value contribution.
- XYZ class for demand variability.
- FSN class for movement speed.
- Vitality class for operational importance.
- Perishability class for expiry/spoilage risk.
- Seasonality class.
- Supplier risk class.
- Inventory priority class.

These classifications support service levels, policy selection, status logic, scenario generation, and final decision priority.

## 6. Service-Level Logic

The service-level layer sets SKU-specific targets and safety factors. Guardrails protect critical, vital, A-class, and fast-moving SKUs from inappropriate service-level reductions.

Service-level outputs are not automatically applied to external systems.

## 7. Policy And Parameter Logic

The policy layer selects the appropriate inventory model for each SKU, including:

- EOQ.
- Continuous review.
- Base stock.
- Newsvendor candidate.
- Event-based replenishment.
- One-to-one replacement.

The parameter layer calculates safety stock, reorder point, EOQ, recommended order quantity, and supporting warning codes. These are generated outputs and are not automatically executed.

## 8. Inventory Status And Action Logic

The status layer identifies current inventory conditions such as stockout, zero stock, critical low stock, reorder now, approaching reorder point, overstock, and healthy/unknown status.

Secondary flags capture expiry, supplier review, policy review, Phase 4 review, quantity constraints, no-order logic, and overstock risk.

## 9. Cost Logic

The cost layer estimates:

- Purchase cost.
- Ordering cost.
- Holding cost.
- Stockout cost.
- Overstock cost.
- Expiry and dead stock cost.
- Supplier risk cost.
- Warehouse space cost.
- Warehouse travel cost.

Some cost assumptions remain fallback-based and require future calibration.

## 10. Warehouse Slotting Logic

Warehouse slotting evaluates SKU and batch placement using:

- Current and projected location utilization.
- Batch-level expiry status.
- FEFO handling.
- Quarantine handling.
- Primary storage and replenishment staging.
- Temperature, security, forklift, fragile, heavy, and perishable constraints.
- Travel distance.
- z-level or shelf-level rules.

Zero-quantity historical batches are retained for traceability but excluded from physical map quantities.

## 11. Visualization Layer

The visualization layer creates CSV files for:

- Location visual data.
- SKU visual data.
- Batch visual data.
- Warehouse grid data.
- Legend and summary data.

It also creates optional 2D and 3D HTML maps when the plotting dependency is available. The visualization layer does not optimize or change warehouse assignments.

## 12. Re-Evaluation Engine

The re-evaluation engine creates recommendation-only review signals for service levels, safety stock, ROP, EOQ review, order model review, and order quantity review.

It is rule-based and does not automatically update policy files.

## 13. Scenario Optimizer

The scenario optimizer generates signal-gated scenarios rather than brute-force combinations. Scenario cost reporting is separated into:

- Operational cost.
- Risk penalty.
- Constraint penalty.
- Penalty-adjusted total cost.

The selected scenario remains a recommendation. It does not trigger automatic execution.

## 14. Final Consolidation Layer

The consolidation layer combines inventory status, costs, warehouse signals, re-evaluation results, and scenario recommendations into final manager-facing outputs.

It separates:

- Mandatory review.
- Advisory review.
- Blocking review action.
- Proposed operational action.
- Execution owner.
- Review owner.
- Final manager status.

## 15. Validation Layer

`validate_phase3.py` reads existing output files and generates validation reports. It checks file existence, row counts, required fields, non-negative values, auto-apply safety, review queue logic, scenario logic, cost reconciliation, warehouse/batch logic, and manager-output quality.

Latest validation result:

- PASS: `179`
- WARNING: `11`
- FAIL: `0`
- SKIPPED: `1`

## 16. Safety And Non-Auto-Apply Rules

Phase 3 does not:

- Create purchase orders.
- Mutate inventory quantities.
- Change suppliers.
- Overwrite service levels.
- Overwrite safety stock, ROP, EOQ, or policy parameters.
- Change warehouse assignments.
- Auto-apply recommendations.

## 17. Known Limitations

Current known limitations are tracked as validation warnings:

- No purchase order creation yet.
- No supplier return-policy integration yet.
- No backorder aging yet.
- No Phase 4 BOM/production logic yet.
- No stockout-censored demand correction yet.
- No automatic policy application yet.
- No UI yet.
- Cost assumptions are partly fallback-based.
- Supplier scenarios are strategy-level, not supplier-ID-level.
- Scenario optimizer is rule-based, not simulation-based.
- Re-evaluation engine is rule-based, not a historical learning loop.

## 18. Planned Improvements

Planned improvements include revisiting Phase 1 forecasting, improving Phase 2 supplier/procurement context, reconnecting richer cross-phase signals, calibrating cost assumptions, adding supplier-specific scenarios, building a UI/dashboard, and later adding Phase 4 production/BOM logic.
