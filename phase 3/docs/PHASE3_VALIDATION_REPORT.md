# Phase 3 Validation Report

## Current Result

- Overall status: `WARNING`
- PASS: `179`
- WARNING: `11`
- FAIL: `0`
- SKIPPED: `1`

The module passed structural validation. The warnings are known roadmap limitations, not failed validation checks.

## Key Reconciliations

- SKU count: `10`
- Master decision rows: `10`
- Manager dashboard rows: `10`
- Mandatory review queue: `7`
- Advisory review queue: `3`
- Operational saving: `7,796.05`
- Penalty-adjusted saving: `20,077.30`
- Auto-apply true count: `0`
- Selected hard blocker count: `0`

## Validation Categories

The validation script checks:

- File existence.
- Row counts.
- One row per SKU in SKU-level outputs.
- Required fields.
- Non-negative costs.
- Auto-apply safety.
- Review queue logic.
- Scenario logic.
- Cost reconciliation.
- Warehouse and batch logic.
- Manager-output quality.

## Interpretation

The `WARNING` status is caused by planned limitations such as missing purchase order creation, missing supplier return-policy integration, missing UI, fallback-based cost assumptions, and rule-based scenario/re-evaluation logic.

There are no failed validation checks in the current output set.
