"""Advisory inventory availability checks for Phase 4 BOM components."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE4_DIR.parent
PHASE4_REQUIREMENTS_FILE = PHASE4_DIR / "outputs" / "phase4_bom_component_requirements.csv"
PHASE4_MRP_REQUIREMENTS_FILE = PHASE4_DIR / "outputs" / "phase4_mrp_net_component_requirements.csv"
PHASE4_MRP_COMPONENT_PERIOD_SUMMARY_FILE = PHASE4_DIR / "outputs" / "phase4_mrp_component_period_summary.csv"
PHASE3_OUTPUT_FILE = PROJECT_ROOT / "phase 3" / "outputs" / "phase4_component_inventory_check.csv"


def build_phase4_component_inventory_check(
    inventory: pd.DataFrame,
    requirements_file: Path = PHASE4_REQUIREMENTS_FILE,
    mrp_requirements_file: Path = PHASE4_MRP_REQUIREMENTS_FILE,
    component_period_summary_file: Path = PHASE4_MRP_COMPONENT_PERIOD_SUMMARY_FILE,
    output_file: Path = PHASE3_OUTPUT_FILE,
) -> pd.DataFrame:
    """Compare advisory component requirements to current inventory availability."""
    requirements, basis = _load_preferred_requirements(
        component_period_summary_file,
        mrp_requirements_file,
        requirements_file,
    )
    if requirements.empty:
        return _write_empty(output_file)

    requirement_qty_column = (
        "net_component_requirement_qty"
        if basis in {"MRP_COMPONENT_PERIOD_SUMMARY", "MRP_NET_REQUIREMENT"}
        else "gross_component_requirement_qty"
    )

    required_columns = {
        "planning_run_id",
        "component_sku",
        "component_name",
        "gross_component_requirement_qty",
        requirement_qty_column,
    }
    missing = required_columns.difference(requirements.columns)
    if missing:
        raise ValueError(f"Phase 4 component requirements missing columns: {sorted(missing)}")

    optional_group_columns = [
        column
        for column in ["mrp_recommendation_status", "mrp_planning_basis"]
        if column in requirements.columns
    ]
    component_requirements = (
        requirements.groupby(["planning_run_id", "component_sku", "component_name"], as_index=False)
        .agg(
            {
                "gross_component_requirement_qty": "sum",
                requirement_qty_column: "sum",
                **{column: _combine_values for column in optional_group_columns},
            }
        )
        .copy()
    )
    if "net_component_requirement_qty" not in component_requirements.columns:
        component_requirements["net_component_requirement_qty"] = component_requirements["gross_component_requirement_qty"]
    for column in ["mrp_recommendation_status", "mrp_planning_basis"]:
        if column not in component_requirements.columns:
            component_requirements[column] = ""
    component_requirements["component_requirement_basis"] = basis
    component_requirements["component_period_summary_used_flag"] = basis == "MRP_COMPONENT_PERIOD_SUMMARY"
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
    if basis in {"MRP_COMPONENT_PERIOD_SUMMARY", "MRP_NET_REQUIREMENT"}:
        check["shortage_qty"] = pd.to_numeric(check["net_component_requirement_qty"], errors="coerce").fillna(0).clip(lower=0).round(4)
    else:
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
            "net_component_requirement_qty",
            "on_hand_qty",
            "available_qty",
            "shortage_qty",
            "inventory_status",
            "mrp_recommendation_status",
            "mrp_planning_basis",
            "component_requirement_basis",
            "component_period_summary_used_flag",
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
            "net_component_requirement_qty",
            "on_hand_qty",
            "available_qty",
            "shortage_qty",
            "inventory_status",
            "mrp_recommendation_status",
            "mrp_planning_basis",
            "component_requirement_basis",
            "component_period_summary_used_flag",
            "phase3_review_required_flag",
            "advisory_only_flag",
        ]
    )


def _load_preferred_requirements(summary_file: Path, mrp_file: Path, bom_file: Path) -> tuple[pd.DataFrame, str]:
    if summary_file.exists():
        summary = pd.read_csv(summary_file)
        required = {
            "planning_run_id",
            "component_sku",
            "component_name",
            "gross_component_requirement_qty",
            "net_component_requirement_qty",
        }
        if not summary.empty and required.issubset(summary.columns):
            return summary, "MRP_COMPONENT_PERIOD_SUMMARY"
    if mrp_file.exists():
        mrp = pd.read_csv(mrp_file)
        required = {"planning_run_id", "component_sku", "component_name", "gross_component_requirement_qty", "net_component_requirement_qty"}
        if not mrp.empty and required.issubset(mrp.columns):
            return mrp, "MRP_NET_REQUIREMENT"
    if not bom_file.exists():
        return pd.DataFrame(), "BOM_GROSS_REQUIREMENT_FALLBACK"
    bom = pd.read_csv(bom_file)
    return bom, "BOM_GROSS_REQUIREMENT_FALLBACK"


def _combine_values(series: pd.Series) -> str:
    values = sorted(set(series.dropna().astype(str).str.strip()) - {""})
    return ";".join(values)
