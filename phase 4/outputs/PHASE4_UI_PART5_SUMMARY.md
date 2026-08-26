# Phase 4 UI Part 5 Summary

## Page Added

- `Maintenance` was added to the Phase 4 Streamlit manager UI.

## Maintenance Status Counts

- Machines/workstations rendered: 7
- Maintenance due count: 7
- Overdue count: 6
- Backlog/review-required count: 6
- High/critical breakdown-risk rows: 7
- Maintenance levels displayed separately: `BREAKDOWN_REPAIR_PLACEHOLDER`, `HEAVY`, `LIGHT`, `MEDIUM`
- Explicit authorization rows found: 7
- Authorization unavailable/review rows: 0
- Authorization levels are sourced only from `shared/outputs/workforce_machine_authorization_context.csv`.

## Dated Versus Risk-Only Evidence

- Valid dated maintenance windows: 0
- Production dated conflict rows in sample views: 0
- Current maintenance calendar evidence is risk/review-based only, so the UI shows `DATED MAINTENANCE WINDOWS: 0` and does not draw fake maintenance bars.

## Production Impact

- Mountain Bike sample candidate: `PSC-SKU-BIKE-MT-001-20260629`
- Mountain Bike affected operations: 7
- Mountain Bike risk-only review rows: 7
- Mountain Bike dated conflict rows: 0
- Road Bike sample candidate: `PSC-SKU-BIKE-ROAD-001-20260629`
- Road Bike affected operations: 6
- Road Bike risk-only review rows: 6
- Road Bike dated conflict rows: 0

## Crew And Skill Findings

- Crew/skill review rows from workload capacity evidence: 0
- Crew and skill readiness is displayed from maintenance workload-by-skill and crew-capacity source outputs only.

## Spare-Part Findings

- Spare-part review rows: 5
- Spare-part readiness is displayed from maintenance spare-part source outputs and shared spare-part review evidence.

## Validation Results

- PASS: 74
- WARNING: 0
- FAIL: 0

## Known Limitations

- The Maintenance page is read-only and does not create maintenance work orders, schedule crews, reserve spare parts, create purchase orders, or apply capacity reductions.
- No dated maintenance timeline bars are shown because no valid dated maintenance start/end evidence exists in the current source files.
- Risk-only maintenance evidence remains separate from dated production conflicts.

## Advisory-Only Confirmation

All UI Part 5 outputs are advisory-only. The UI reads validated planning outputs only and does not create production orders, confirmed schedules, dispatch instructions, inventory reservations, inventory consumption, WIP transactions, purchase orders, maintenance work orders, capacity reductions, or simulation outputs.
