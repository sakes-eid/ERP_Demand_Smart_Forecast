# Phase 4 UI Part 4 Summary

## Page Added

- `Capacity & WIP` was added to the Phase 4 Streamlit manager UI.

## Sample Context

- Page basis: `ALT-BASELINE`
- Sample finished SKU: `SKU-BIKE-MT-001`
- Sample schedule candidate: `PSC-SKU-BIKE-MT-001-20260629`

## Workstation Utilization Results

- Workstations rendered: 7
- Main bottleneck workstation: `WS-PACK`
- Highest workstation utilization: 82.6166%
- Parallel-capable workstations rendered from Step 8F evidence: 4

## WIP Buffer Results

- WIP buffers rendered: 8
- Candidate-specific ledger buffers: 8
- Generic fallback buffers: 0
- Maximum selected-candidate buffer occupancy: 37.5%
- Total blocked WIP/buffer quantity: 153.9482
- FIFO violation count from Step 8F validation FAIL rows: 0
- Projected balances are filtered by `ALT-BASELINE`, finished SKU, selected schedule candidate, and buffer before selecting the latest chronological shadow-WIP event. Candidate-independent opening WIP is included only when explicitly marked as `STARTING_ACCEPTED_WIP`.

## Validation Results

- PASS: 61
- WARNING: 0
- FAIL: 0

## Known Limitations

- Capacity & WIP is locked to `ALT-BASELINE` because that is the current integrated reference schedule.
- The page is a read-only management view and does not recalculate scheduling, resource capacity, WIP policy, FIFO logic, or buffer capacity.
- WIP buffer balances use selected-candidate time-causal shadow-ledger events where available; generic buffer status is shown only as a labeled fallback.
- Maintenance information is displayed as review evidence; detailed maintenance pages are not part of UI Part 4.

## Advisory-Only Confirmation

All UI Part 4 outputs are advisory-only. The UI reads validated planning outputs only and does not create production orders, confirmed schedules, dispatch instructions, inventory reservations, inventory consumption, WIP transactions, purchase orders, maintenance work orders, capacity reductions, or simulation outputs.
