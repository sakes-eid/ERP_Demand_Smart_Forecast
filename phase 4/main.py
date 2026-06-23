"""Run Phase 4 initialization bridge logic only."""

from __future__ import annotations

from core.bom_explosion_bridge import OUTPUT_FILE, build_bom_component_requirements


def run_initialization() -> None:
    """Regenerate Phase 4 advisory BOM component requirements."""
    requirements = build_bom_component_requirements()
    print("Phase 4 initialization bridge completed.")
    print(f"BOM component requirement rows: {len(requirements)}")
    print(f"Output written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    run_initialization()
