"""Advisory MRP component-period netting and pegging for Phase 4 Step 2B."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE4_DIR.parent
BOM_REQUIREMENTS_FILE = PHASE4_DIR / "outputs" / "phase4_bom_component_requirements.csv"
PHASE3_INVENTORY_FILE = PROJECT_ROOT / "phase 3" / "data" / "inventory.csv"
OUTPUT_FILE = PHASE4_DIR / "outputs" / "phase4_mrp_net_component_requirements.csv"
SUMMARY_OUTPUT_FILE = PHASE4_DIR / "outputs" / "phase4_mrp_component_period_summary.csv"
PEGGING_OUTPUT_FILE = PHASE4_DIR / "outputs" / "phase4_mrp_pegging_detail.csv"

LEGACY_MRP_PLANNING_BASIS = "MPS_BOM_COMPONENT_NETTING"
COMPONENT_PERIOD_MRP_PLANNING_BASIS = "MPS_BOM_COMPONENT_NETTING_COMPONENT_PERIOD"
PEGGING_TYPE = "SOFT_PEGGING_FINISHED_GOODS_DEMAND"
FINISHED_PRODUCT_NAMES = {
    "SKU-BIKE-ROAD-001": "Road Bike",
    "SKU-BIKE-MT-001": "Mountain Bike",
}


def build_mrp_net_component_requirements(
    bom_requirements_file: Path = BOM_REQUIREMENTS_FILE,
    inventory_file: Path = PHASE3_INVENTORY_FILE,
    output_file: Path = OUTPUT_FILE,
    summary_output_file: Path = SUMMARY_OUTPUT_FILE,
    pegging_output_file: Path = PEGGING_OUTPUT_FILE,
    planning_run_id: str | None = None,
) -> pd.DataFrame:
    """Build advisory component-period MRP and soft pegging outputs."""
    planning_run_id = planning_run_id or os.environ.get("INTEGRATED_RUN_ID") or _default_run_id()
    requirements = _load_requirements(bom_requirements_file)
    inventory = _load_inventory(inventory_file)

    if requirements.empty:
        summary = _empty_summary_output()
        legacy = _empty_legacy_output()
        pegging = _empty_pegging_output()
    else:
        normalized = _normalize_requirements(requirements)
        summary = _build_component_period_summary(normalized, inventory, planning_run_id)
        pegging = _build_pegging_detail(normalized, summary)
        legacy = _build_legacy_detail(normalized, pegging, summary)

    for path, frame in [
        (output_file, legacy),
        (summary_output_file, summary),
        (pegging_output_file, pegging),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    return legacy


def _normalize_requirements(requirements: pd.DataFrame) -> pd.DataFrame:
    rows = requirements.copy()
    if "period_start" not in rows.columns or rows["period_start"].fillna("").astype(str).str.strip().eq("").all():
        rows["period_start"] = rows.get("forecast_period", "")
    if "period_end" not in rows.columns:
        rows["period_end"] = ""
    rows["period_start"] = pd.to_datetime(rows["period_start"], errors="coerce")
    rows["period_end"] = pd.to_datetime(rows["period_end"], errors="coerce")
    rows = rows[rows["period_start"].notna()].copy()
    if rows.empty:
        return rows
    rows["period_end"] = rows["period_end"].fillna(rows["period_start"] + pd.Timedelta(days=6))
    rows["gross_component_requirement_qty"] = pd.to_numeric(
        rows["gross_component_requirement_qty"],
        errors="coerce",
    ).fillna(0).clip(lower=0)
    rows["mps_planned_production_qty"] = pd.to_numeric(
        rows.get("mps_planned_production_qty", 0),
        errors="coerce",
    ).fillna(0).clip(lower=0)
    rows["quantity_per_finished_unit"] = pd.to_numeric(
        rows.get("quantity_per_finished_unit", 0),
        errors="coerce",
    ).fillna(0).clip(lower=0)
    for column in ["planning_run_id", "finished_sku", "component_sku", "component_name"]:
        rows[column] = rows[column].astype(str).str.strip()
    if "finished_product_name" not in rows.columns:
        rows["finished_product_name"] = ""
    rows["finished_product_name"] = rows["finished_product_name"].fillna("").astype(str).str.strip()
    missing_names = rows["finished_product_name"].eq("")
    rows.loc[missing_names, "finished_product_name"] = rows.loc[missing_names, "finished_sku"].map(FINISHED_PRODUCT_NAMES).fillna("")
    return rows


def _build_component_period_summary(
    requirements: pd.DataFrame,
    inventory: pd.DataFrame,
    planning_run_id: str,
) -> pd.DataFrame:
    if requirements.empty:
        return _empty_summary_output()
    summary = (
        requirements.groupby(
            ["planning_run_id", "period_start", "period_end", "component_sku", "component_name"],
            as_index=False,
        )["gross_component_requirement_qty"]
        .sum()
        .copy()
    )
    inventory_positions = _component_inventory_positions(inventory)
    summary = summary.merge(inventory_positions, on="component_sku", how="left")
    summary["component_on_hand_qty"] = summary["component_on_hand_qty"].fillna(0)
    summary["component_available_qty"] = summary["component_available_qty"].fillna(0)
    summary["inventory_record_missing_flag"] = summary["inventory_record_found_flag"].isna()
    summary = summary.sort_values(["component_sku", "period_start", "period_end"]).copy()

    output_groups = []
    for _, group in summary.groupby("component_sku", sort=False):
        group = group.sort_values(["period_start", "period_end"]).copy()
        rolling_inventory = 0.0 if group["inventory_record_missing_flag"].all() else float(group["component_available_qty"].iloc[0])
        sequences = []
        starts = []
        net_requirements = []
        endings = []
        shortages = []

        for sequence, (_, row) in enumerate(group.iterrows(), start=1):
            gross_requirement = max(float(row["gross_component_requirement_qty"]), 0.0)
            starting_inventory = 0.0 if bool(row["inventory_record_missing_flag"]) else max(rolling_inventory, 0.0)
            net_requirement = max(gross_requirement - starting_inventory, 0.0)
            projected_ending = starting_inventory - gross_requirement + net_requirement
            projected_shortage = max(gross_requirement - starting_inventory - net_requirement, 0.0)

            sequences.append(sequence)
            starts.append(round(starting_inventory, 4))
            net_requirements.append(round(net_requirement, 4))
            endings.append(round(max(projected_ending, 0.0), 4))
            shortages.append(round(projected_shortage, 4))
            rolling_inventory = max(projected_ending, 0.0)

        group["period_sequence"] = sequences
        group["period_starting_component_inventory_qty"] = starts
        group["net_component_requirement_qty"] = net_requirements
        group["projected_component_ending_inventory_qty"] = endings
        group["projected_component_shortage_qty"] = shortages
        group["mrp_recommendation_status"] = "NET_REQUIREMENT_IDENTIFIED"
        group.loc[
            (group["net_component_requirement_qty"] == 0) & (group["gross_component_requirement_qty"] > 0),
            "mrp_recommendation_status",
        ] = "COVERED_BY_COMPONENT_INVENTORY"
        group.loc[group["gross_component_requirement_qty"] == 0, "mrp_recommendation_status"] = "NO_COMPONENT_REQUIREMENT"
        group.loc[group["projected_component_shortage_qty"] > 0, "mrp_recommendation_status"] = "REVIEW_REQUIRED"
        group.loc[group["inventory_record_missing_flag"], "mrp_recommendation_status"] = "MISSING_COMPONENT_INVENTORY_RECORD"
        group["mrp_review_required_flag"] = (
            group["inventory_record_missing_flag"] | (group["projected_component_shortage_qty"] > 0)
        )
        output_groups.append(group)

    result = pd.concat(output_groups, ignore_index=True)
    result["planning_run_id"] = planning_run_id
    result["mrp_planning_basis"] = COMPONENT_PERIOD_MRP_PLANNING_BASIS
    result["component_period_summary_flag"] = True
    result["source_phase"] = "PHASE4_MPS_BOM_MRP_COMPONENT_PERIOD_NETTING"
    result["advisory_only_flag"] = True
    result["period_start"] = result["period_start"].dt.date.astype(str)
    result["period_end"] = result["period_end"].dt.date.astype(str)
    return result[_summary_columns()].copy()


def _build_pegging_detail(requirements: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    if requirements.empty or summary.empty:
        return _empty_pegging_output()
    detail = (
        requirements.groupby(
            [
                "planning_run_id",
                "period_start",
                "period_end",
                "component_sku",
                "component_name",
                "finished_sku",
                "finished_product_name",
            ],
            as_index=False,
        )
        .agg(
            {
                "mps_planned_production_qty": "sum",
                "quantity_per_finished_unit": "max",
                "gross_component_requirement_qty": "sum",
            }
        )
        .rename(columns={"gross_component_requirement_qty": "pegged_gross_component_requirement_qty"})
    )
    detail["period_start"] = detail["period_start"].dt.date.astype(str)
    detail["period_end"] = detail["period_end"].dt.date.astype(str)
    keys = ["planning_run_id", "period_start", "period_end", "component_sku", "component_name"]
    summary_subset = summary[
        keys
        + [
            "gross_component_requirement_qty",
            "net_component_requirement_qty",
        ]
    ].rename(
        columns={
            "gross_component_requirement_qty": "component_period_gross_requirement_qty",
            "net_component_requirement_qty": "component_period_net_requirement_qty",
        }
    )
    detail = detail.merge(summary_subset, on=keys, how="left")
    gross = pd.to_numeric(detail["component_period_gross_requirement_qty"], errors="coerce").fillna(0)
    pegged_gross = pd.to_numeric(detail["pegged_gross_component_requirement_qty"], errors="coerce").fillna(0)
    net = pd.to_numeric(detail["component_period_net_requirement_qty"], errors="coerce").fillna(0)
    detail["pegged_requirement_share_pct"] = _safe_divide(pegged_gross, gross).round(8)
    detail["pegged_net_requirement_qty"] = (net * detail["pegged_requirement_share_pct"]).clip(lower=0).round(4)
    detail["pegging_type"] = PEGGING_TYPE
    detail["source_phase"] = "PHASE4_MRP_COMPONENT_PERIOD_SOFT_PEGGING"
    detail["advisory_only_flag"] = True
    return detail[_pegging_columns()].copy()


def _build_legacy_detail(requirements: pd.DataFrame, pegging: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    if requirements.empty or pegging.empty:
        return _empty_legacy_output()
    keys = ["planning_run_id", "period_start", "period_end", "component_sku", "component_name", "finished_sku"]
    req = requirements.copy()
    req["period_start"] = req["period_start"].dt.date.astype(str)
    req["period_end"] = req["period_end"].dt.date.astype(str)
    legacy = req.merge(
        pegging[
            keys
            + [
                "component_period_net_requirement_qty",
                "pegged_net_requirement_qty",
            ]
        ],
        on=keys,
        how="left",
    )
    summary_keys = ["planning_run_id", "period_start", "period_end", "component_sku", "component_name"]
    summary_subset = summary[
        summary_keys
        + [
            "component_on_hand_qty",
            "component_available_qty",
            "period_starting_component_inventory_qty",
            "projected_component_ending_inventory_qty",
            "projected_component_shortage_qty",
            "mrp_recommendation_status",
            "mrp_review_required_flag",
        ]
    ]
    legacy = legacy.merge(summary_subset, on=summary_keys, how="left")
    legacy["net_component_requirement_qty"] = pd.to_numeric(
        legacy["pegged_net_requirement_qty"],
        errors="coerce",
    ).fillna(0).clip(lower=0)
    legacy["mrp_planning_basis"] = LEGACY_MRP_PLANNING_BASIS
    legacy["component_period_mrp_planning_basis"] = COMPONENT_PERIOD_MRP_PLANNING_BASIS
    legacy["source_phase"] = "PHASE4_MPS_BOM_MRP_NETTING_COMPATIBILITY_DETAIL"
    legacy["advisory_only_flag"] = True
    return legacy[_legacy_columns()].copy()


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    safe_denominator = denominator.where(denominator != 0)
    return (numerator / safe_denominator).fillna(0).clip(lower=0, upper=1)


def _load_requirements(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Phase 4 BOM component requirements not found: {path}")
    requirements = pd.read_csv(path)
    required = {
        "planning_run_id",
        "period_start",
        "period_end",
        "finished_sku",
        "component_sku",
        "component_name",
        "gross_component_requirement_qty",
    }
    missing = required.difference(requirements.columns)
    if missing:
        raise ValueError(f"Phase 4 BOM component requirements missing columns: {sorted(missing)}")
    return requirements


def _load_inventory(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Phase 3 inventory input not found: {path}")
    inventory = pd.read_csv(path)
    missing = {"sku_id", "current_inventory", "available_inventory"}.difference(inventory.columns)
    if missing:
        raise ValueError(f"Phase 3 inventory input missing columns: {sorted(missing)}")
    return inventory


def _component_inventory_positions(inventory: pd.DataFrame) -> pd.DataFrame:
    positions = inventory.copy()
    positions["component_sku"] = positions["sku_id"].astype(str).str.strip()
    positions["component_on_hand_qty"] = pd.to_numeric(
        positions["current_inventory"],
        errors="coerce",
    ).fillna(0).clip(lower=0)
    positions["component_available_qty"] = pd.to_numeric(
        positions["available_inventory"],
        errors="coerce",
    ).fillna(0).clip(lower=0)
    positions["inventory_record_found_flag"] = True
    return positions[
        [
            "component_sku",
            "component_on_hand_qty",
            "component_available_qty",
            "inventory_record_found_flag",
        ]
    ].drop_duplicates("component_sku")


def _empty_legacy_output() -> pd.DataFrame:
    return pd.DataFrame(columns=_legacy_columns())


def _empty_summary_output() -> pd.DataFrame:
    return pd.DataFrame(columns=_summary_columns())


def _empty_pegging_output() -> pd.DataFrame:
    return pd.DataFrame(columns=_pegging_columns())


def _legacy_columns() -> list[str]:
    return [
        "planning_run_id",
        "period_start",
        "period_end",
        "finished_sku",
        "component_sku",
        "component_name",
        "gross_component_requirement_qty",
        "component_on_hand_qty",
        "component_available_qty",
        "period_starting_component_inventory_qty",
        "net_component_requirement_qty",
        "projected_component_ending_inventory_qty",
        "projected_component_shortage_qty",
        "mrp_recommendation_status",
        "mrp_review_required_flag",
        "mrp_planning_basis",
        "component_period_mrp_planning_basis",
        "source_phase",
        "advisory_only_flag",
    ]


def _summary_columns() -> list[str]:
    return [
        "planning_run_id",
        "period_start",
        "period_end",
        "component_sku",
        "component_name",
        "gross_component_requirement_qty",
        "component_on_hand_qty",
        "component_available_qty",
        "period_sequence",
        "period_starting_component_inventory_qty",
        "net_component_requirement_qty",
        "projected_component_ending_inventory_qty",
        "projected_component_shortage_qty",
        "mrp_recommendation_status",
        "mrp_review_required_flag",
        "mrp_planning_basis",
        "component_period_summary_flag",
        "source_phase",
        "advisory_only_flag",
    ]


def _pegging_columns() -> list[str]:
    return [
        "planning_run_id",
        "period_start",
        "period_end",
        "component_sku",
        "component_name",
        "finished_sku",
        "finished_product_name",
        "mps_planned_production_qty",
        "quantity_per_finished_unit",
        "pegged_gross_component_requirement_qty",
        "component_period_gross_requirement_qty",
        "pegged_requirement_share_pct",
        "component_period_net_requirement_qty",
        "pegged_net_requirement_qty",
        "pegging_type",
        "source_phase",
        "advisory_only_flag",
    ]


def _default_run_id() -> str:
    return f"PHASE4-MRP-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


if __name__ == "__main__":
    output = build_mrp_net_component_requirements()
    print(f"Phase 4 MRP compatibility detail rows: {len(output)}")
    print(f"Output written to: {OUTPUT_FILE}")
    print(f"Component-period summary written to: {SUMMARY_OUTPUT_FILE}")
    print(f"Pegging detail written to: {PEGGING_OUTPUT_FILE}")
