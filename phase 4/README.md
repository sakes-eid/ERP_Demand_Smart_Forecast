# Phase 4 Initialization

Phase 4 production planning preparation has started, but this is initialization only. The full production planning engine is not implemented yet.

Current initialization scope:

- Road Bike and Mountain Bike were added as future finished products in Phase 1 demand planning.
- BOM seed data lives in `data/phase4_bom.csv`.
- `core/bom_explosion_bridge.py` converts finished-bike forecasts into advisory component requirements.
- Phase 3 can produce an advisory inventory availability check for BOM components.
- Phase 2 can produce an advisory supplier coverage check for BOM component shortages.
- Phase 4 validation writes JSON evidence and a text report under `outputs/`.

Run order:

1. Run Phase 1 forecasts.
2. Run Phase 4 BOM explosion.
3. Run Phase 3 component inventory checks.
4. Run Phase 2 component supplier checks.

The Phase 4 bridges are optional-safe. If a bridge file is missing or fails, Phase 2 and Phase 3 print a warning and continue their existing core pipelines.

Guardrails:

- Outputs are advisory only.
- No purchase orders are created.
- No production orders are created.
- No inventory is auto-reserved.
- Simulation is a separate future phase.
- Future production release flags should default to `production_order_release_allowed = False`.

Next likely Phase 4 feature:

- The next real production-planning feature will be MPS, but MPS is not implemented in this initialization hardening step.

Review bundle:

- `create_phase4_review_bundle.py` generates `phase4_init_review_bundle.zip` at the project root for external review.
- The bundle preserves project-relative folder structure and excludes cache, bytecode, virtual environment, and zip artifacts.
