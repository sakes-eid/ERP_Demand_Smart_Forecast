# Phase 4 UI Part 1 Graph Corrections Summary

## Fixes Implemented

- Maintenance badges now use dated maintenance-window evidence where available and show `DATE UNKNOWN / REVIEW` only when evidence is risk-only or undated.
- WIP buffer nodes now use the time-causal shadow-WIP ledger to show projected balance at the relevant transfer timestamp when schedule-specific evidence exists.
- Generic WIP buffer status remains available only as a clearly labeled fallback.
- The Production Flow Graph is locked to `ALT-BASELINE` because integrated graph nodes and edges are not alternative-specific.
- The Manager Overview still shows the six-alternative comparison.
- Node-click selection was not added to avoid a larger frontend rewrite; the operation detail selector remains the Part 1 fallback.

## Sample Graph Evidence

- Sample SKU: `SKU-BIKE-MT-001`
- Sample candidate: `PSC-SKU-BIKE-MT-001-20260629`
- Operation nodes: 7
- Dependency edges: 8
- WIP buffer nodes: 8
- Critical-path nodes: 5
- Bottleneck nodes: 7
- Dated maintenance indicators: 0
- Unknown/review maintenance indicators: 7
- WIP nodes using time-causal shadow ledger: 7
- WIP nodes using generic fallback: 1

## Validation

- UI validation PASS: 17
- UI validation WARNING: 0
- UI validation FAIL: 0

## Known UI Limitations

- The HTML graph is read-only. Operation detail selection is handled by a Streamlit selector rather than direct node clicks.
- Integrated graph evidence is currently reference-graph data, so graph filtering is locked to `ALT-BASELINE`.
- Detailed BOM, timeline/Gantt, capacity/WIP, maintenance, and release pages are intentionally not included in Part 1.

## Advisory-Only Confirmation

The UI reads existing outputs only. It does not rerun scheduling, change Step 8F or Step 8G logic, create production orders, authorize release, dispatch workers, reserve inventory, consume inventory or WIP, create purchase orders, create maintenance work orders, apply capacity reductions, or run simulation.
