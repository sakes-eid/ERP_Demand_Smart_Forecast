"""Advisory inventory availability checks for Phase 4 BOM components."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE4_DIR.parent
PHASE4_REQUIREMENTS_FILE = PHASE4_DIR / "outputs" / "phase4_bom_component_requirements.csv"
PHASE3_OUTPUT_FILE = PROJECT_ROOT / "phase 3" / "outputs" / "phase4_component_inventory_check.csv"


def build_phase4_component_inventory_check(
    inventory: pd.DataFrame,
    requirements_file: Path = PHASE4_REQUIREMENTS_FILE,
    output_file: Path = PHASE3_OUTPUT_FILE,
) -> pd.DataFrame:
    """Compare advisory BOM component requirements to current inventory availability."""
    if not requirements_file.exists():
        return _write_empty(output_file)

    requirements = pd.read_csv(requirements_file)
    if requirements.empty:
        return _write_empty(output_file)

    required_columns = {
        "planning_run_id",
        "component_sku",
        "component_name",
        "gross_component_requirement_qty",
    }
    missing = required_columns.difference(requirements.columns)
    if missing:
        raise ValueError(f"Phase 4 component requirements missing columns: {sorted(missing)}")

    component_requirements = (
        requirements.groupby(["planning_run_id", "component_sku", "component_name"], as_index=False)[
            "gross_component_requirement_qty"
        ]
        .sum()
        .copy()
    )
    inventory_positions = inventory.copy()
    inventory_positions["sku_id"] = inventory_positions["sku_id"].astype(str).str.strip()
    for column in ["current_inventory", "available_inventory"]:
        inventory_positions[column] = pd.to_numeric(inventory_positions[column], errors="coerce").fillna(0)
    inventory_positions["on_hand_qty"] = inventory_positions["current_inventory"].clip(lower=0)
    inventory_positions["available_qty"] = inventory_positions["available_inventory"].clip(lower=0)

    check = component_requirements.merge(
        inventory_positions[["sku_id", "on_hand_qty", "available_qty"]],
        left_on="component_sku",
        right_on="sku_id",
        how="left",
    )
    missing_inventory = check["sku_id"].isna()
    check["on_hand_qty"] = check["on_hand_qty"].fillna(0)
    check["available_qty"] = check["available_qty"].fillna(0)
    check["shortage_qty"] = (
        check["gross_component_requirement_qty"] - check["available_qty"]
    ).clip(lower=0).round(4)
    check["inventory_status"] = "AVAILABLE"
    check.loc[check["shortage_qty"] > 0, "inventory_status"] = "SHORTAGE"
    check.loc[missing_inventory, "inventory_status"] = "MISSING_INVENTORY_RECORD"
    check["phase3_review_required_flag"] = check["inventory_status"] != "AVAILABLE"
    check["advisory_only_flag"] = True

    check = check[
        [
            "planning_run_id",
            "component_sku",
            "component_name",
            "gross_component_requirement_qty",
            "on_hand_qty",
            "available_qty",
            "shortage_qty",
            "inventory_status",
            "phase3_review_required_flag",
            "advisory_only_flag",
        ]
    ]
    output_file.parent.mkdir(parents=True, exist_ok=True)
    check.to_csv(output_file, index=False)
    return check


def _write_empty(output_file: Path) -> pd.DataFrame:
    check = _empty_output()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    check.to_csv(output_file, index=False)
    return check


def _empty_output() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "planning_run_id",
            "component_sku",
            "component_name",
            "gross_component_requirement_qty",
            "on_hand_qty",
            "available_qty",
            "shortage_qty",
            "inventory_status",
            "phase3_review_required_flag",
            "advisory_only_flag",
        ]
    )
