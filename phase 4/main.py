"""Run Phase 4 initialization bridge logic only."""

from __future__ import annotations

from core.bom_explosion_bridge import OUTPUT_FILE, build_bom_component_requirements
from core.master_production_schedule import OUTPUT_FILE as MPS_OUTPUT_FILE
from core.master_production_schedule import build_master_production_schedule


def run_initialization() -> None:
    """Regenerate Phase 4 advisory MPS and BOM component requirements."""
    mps = build_master_production_schedule()
    planning_run_id = None
    if not mps.empty and "planning_run_id" in mps.columns:
        run_ids = mps["planning_run_id"].dropna().astype(str).str.strip()
        if not run_ids.empty:
            planning_run_id = run_ids.iloc[0]
    requirements = build_bom_component_requirements(planning_run_id=planning_run_id)
    print("Phase 4 initialization bridge completed.")
    print(f"MPS rows: {len(mps)}")
    print(f"MPS output written to: {MPS_OUTPUT_FILE}")
    print(f"BOM component requirement rows: {len(requirements)}")
    print(f"Output written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    run_initialization()
