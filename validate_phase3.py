"""Run read-only validation checks for Phase 3 Inventory Control outputs."""

from __future__ import annotations

from pathlib import Path

from core.phase3_validation import run_phase3_validation


if __name__ == "__main__":
    result = run_phase3_validation()
    shared_output_dir = Path(__file__).resolve().parents[1] / "shared" / "outputs"
    allocation_summary = shared_output_dir / "phase2_procurement_allocation_summary.csv"
    requirement_bridge = shared_output_dir / "phase3_procurement_requirement_context.csv"
    bridge_files = [path.name for path in [requirement_bridge, allocation_summary] if path.exists()]
    mode = "INTEGRATED_MODE" if allocation_summary.exists() else "STANDALONE_MODE"
    print(f"Validation report: {result['report_path']}")
    print(f"Summary CSV: {result['summary_path']}")
    print(f"Issues CSV: {result['issues_path']}")
    print(f"Overall status: {result['overall_status']}")
    print(f"Fail count: {result['fail_count']}")
    print(f"Warning count: {result['warning_count']}")
    print(f"Standalone or integrated mode: {mode}")
    print(f"Bridge files detected: {', '.join(bridge_files) if bridge_files else 'none'}")
