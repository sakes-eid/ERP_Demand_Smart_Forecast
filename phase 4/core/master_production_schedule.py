"""Advisory Master Production Schedule builder for Phase 4 Step 1B."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE4_DIR.parent
PHASE1_FUTURE_FORECAST_FILE = PROJECT_ROOT / "phase 1" / "outputs" / "future_forecast_results.csv"
PHASE3_INVENTORY_FILE = PROJECT_ROOT / "phase 3" / "data" / "inventory.csv"
OUTPUT_FILE = PHASE4_DIR / "outputs" / "phase4_master_production_schedule.csv"

FINISHED_PRODUCTS = {
    "SKU-BIKE-ROAD-001": "Road Bike",
    "SKU-BIKE-MT-001": "Mountain Bike",
}


def build_master_production_schedule(
    forecast_file: Path = PHASE1_FUTURE_FORECAST_FILE,
    inventory_file: Path = PHASE3_INVENTORY_FILE,
    output_file: Path = OUTPUT_FILE,
    planning_run_id: str | None = None,
) -> pd.DataFrame:
    """Build a weekly advisory MPS with projected finished-goods balance."""
    planning_run_id = planning_run_id or os.environ.get("INTEGRATED_RUN_ID") or _default_run_id()
    forecast = _load_forecast(forecast_file)
    inventory = _load_inventory(inventory_file)

    bike_forecast = forecast[forecast["sku_id"].isin(FINISHED_PRODUCTS)].copy()
    if bike_forecast.empty:
        mps = _empty_output()
    else:
        bike_forecast["forecast_date"] = pd.to_datetime(bike_forecast["forecast_date"], errors="coerce")
        bike_forecast = bike_forecast[bike_forecast["forecast_date"].notna()].copy()
        bike_forecast["forecast_quantity"] = pd.to_numeric(
            bike_forecast["forecast_quantity"],
            errors="coerce",
        ).fillna(0).clip(lower=0)
        bike_forecast["period_start"] = (
            bike_forecast["forecast_date"] - pd.to_timedelta(bike_forecast["forecast_date"].dt.weekday, unit="D")
        ).dt.normalize()
        bike_forecast["period_end"] = bike_forecast["period_start"] + pd.Timedelta(days=6)
        weekly = (
            bike_forecast.groupby(["period_start", "period_end", "sku_id"], as_index=False)["forecast_quantity"]
            .sum()
            .rename(columns={"sku_id": "finished_sku", "forecast_quantity": "forecast_demand_qty"})
        )
        inventory_positions = _finished_goods_inventory_positions(inventory)
        mps = weekly.merge(inventory_positions, on="finished_sku", how="left")
        missing_inventory = mps["inventory_record_found_flag"].isna()
        mps["finished_product_name"] = mps["finished_sku"].map(FINISHED_PRODUCTS)
        mps["finished_goods_on_hand_qty"] = mps["finished_goods_on_hand_qty"].fillna(0)
        mps["available_finished_goods_qty"] = mps["available_finished_goods_qty"].fillna(0)
        mps["inventory_record_missing_flag"] = missing_inventory
        mps = _apply_rolling_balance(mps)
        mps["planning_run_id"] = planning_run_id
        mps["source_phase"] = "PHASE1_FORECAST_PHASE3_FINISHED_GOODS_INVENTORY"
        mps["advisory_only_flag"] = True
        mps["period_start"] = mps["period_start"].dt.date.astype(str)
        mps["period_end"] = mps["period_end"].dt.date.astype(str)
        mps = mps[
            [
                "planning_run_id",
                "period_start",
                "period_end",
                "finished_sku",
                "finished_product_name",
                "forecast_demand_qty",
                "finished_goods_on_hand_qty",
                "available_finished_goods_qty",
                "period_sequence",
                "period_starting_inventory_qty",
                "net_finished_goods_requirement_qty",
                "planned_production_qty",
                "projected_ending_inventory_qty",
                "projected_shortage_qty",
                "rolling_balance_applied_flag",
                "mps_planning_basis",
                "mps_status",
                "mps_review_required_flag",
                "source_phase",
                "advisory_only_flag",
            ]
        ].copy()

    output_file.parent.mkdir(parents=True, exist_ok=True)
    mps.to_csv(output_file, index=False)
    return mps


def _apply_rolling_balance(mps: pd.DataFrame) -> pd.DataFrame:
    """Apply advisory rolling finished-goods inventory balance by SKU."""
    result = mps.sort_values(["finished_sku", "period_start"]).copy()
    for column in ["forecast_demand_qty", "finished_goods_on_hand_qty", "available_finished_goods_qty"]:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).clip(lower=0)

    output_groups = []
    for _, group in result.groupby("finished_sku", sort=False):
        group = group.sort_values("period_start").copy()
        missing_inventory = group["inventory_record_missing_flag"].fillna(True).astype(bool)
        if missing_inventory.all():
            rolling_inventory = 0.0
        else:
            rolling_inventory = float(group["available_finished_goods_qty"].iloc[0])

        period_sequences = []
        starts = []
        net_requirements = []
        planned = []
        ending = []
        shortages = []

        for sequence, (_, row) in enumerate(group.iterrows(), start=1):
            demand = max(float(row["forecast_demand_qty"]), 0.0)
            if bool(row["inventory_record_missing_flag"]):
                starting_inventory = 0.0
            else:
                starting_inventory = max(rolling_inventory, 0.0)
            net_requirement = max(demand - starting_inventory, 0.0)
            planned_production = net_requirement
            projected_ending = starting_inventory + planned_production - demand
            projected_shortage = max(demand - starting_inventory - planned_production, 0.0)

            period_sequences.append(sequence)
            starts.append(round(starting_inventory, 4))
            net_requirements.append(round(net_requirement, 4))
            planned.append(round(planned_production, 4))
            ending.append(round(max(projected_ending, 0.0), 4))
            shortages.append(round(projected_shortage, 4))
            rolling_inventory = max(projected_ending, 0.0)

        group["period_sequence"] = period_sequences
        group["period_starting_inventory_qty"] = starts
        group["net_finished_goods_requirement_qty"] = net_requirements
        group["planned_production_qty"] = planned
        group["projected_ending_inventory_qty"] = ending
        group["projected_shortage_qty"] = shortages
        group["rolling_balance_applied_flag"] = True
        group["mps_planning_basis"] = "ROLLING_PROJECTED_AVAILABLE_BALANCE"
        group["mps_status"] = "PRODUCTION_PLANNED"
        group.loc[
            (group["planned_production_qty"] == 0) & (group["forecast_demand_qty"] > 0),
            "mps_status",
        ] = "COVERED_BY_PROJECTED_INVENTORY"
        group.loc[group["forecast_demand_qty"] == 0, "mps_status"] = "NO_DEMAND"
        group.loc[group["projected_shortage_qty"] > 0, "mps_status"] = "REVIEW_REQUIRED"
        group.loc[group["inventory_record_missing_flag"], "mps_status"] = "MISSING_FINISHED_GOODS_INVENTORY_RECORD"
        group["mps_review_required_flag"] = (
            group["inventory_record_missing_flag"] | (group["projected_shortage_qty"] > 0)
        )
        output_groups.append(group)

    return pd.concat(output_groups, ignore_index=True) if output_groups else result


def _load_forecast(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Phase 1 future forecast output not found: {path}")
    forecast = pd.read_csv(path)
    missing = {"sku_id", "forecast_date", "forecast_quantity"}.difference(forecast.columns)
    if missing:
        raise ValueError(f"Phase 1 future forecast output is missing columns: {sorted(missing)}")
    return forecast


def _load_inventory(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Phase 3 inventory input not found: {path}")
    inventory = pd.read_csv(path)
    missing = {"sku_id", "current_inventory", "available_inventory"}.difference(inventory.columns)
    if missing:
        raise ValueError(f"Phase 3 inventory input is missing columns: {sorted(missing)}")
    return inventory


def _finished_goods_inventory_positions(inventory: pd.DataFrame) -> pd.DataFrame:
    positions = inventory.copy()
    positions["finished_sku"] = positions["sku_id"].astype(str).str.strip()
    positions = positions[positions["finished_sku"].isin(FINISHED_PRODUCTS)].copy()
    if positions.empty:
        return pd.DataFrame(
            columns=[
                "finished_sku",
                "finished_goods_on_hand_qty",
                "available_finished_goods_qty",
                "inventory_record_found_flag",
            ]
        )
    positions["finished_goods_on_hand_qty"] = pd.to_numeric(
        positions["current_inventory"],
        errors="coerce",
    ).fillna(0).clip(lower=0)
    positions["available_finished_goods_qty"] = pd.to_numeric(
        positions["available_inventory"],
        errors="coerce",
    ).fillna(0).clip(lower=0)
    positions["inventory_record_found_flag"] = True
    return positions[
        [
            "finished_sku",
            "finished_goods_on_hand_qty",
            "available_finished_goods_qty",
            "inventory_record_found_flag",
        ]
    ].drop_duplicates("finished_sku")


def _empty_output() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "planning_run_id",
            "period_start",
            "period_end",
            "finished_sku",
            "finished_product_name",
            "forecast_demand_qty",
            "finished_goods_on_hand_qty",
            "available_finished_goods_qty",
            "period_sequence",
            "period_starting_inventory_qty",
            "net_finished_goods_requirement_qty",
            "planned_production_qty",
            "projected_ending_inventory_qty",
            "projected_shortage_qty",
            "rolling_balance_applied_flag",
            "mps_planning_basis",
            "mps_status",
            "mps_review_required_flag",
            "source_phase",
            "advisory_only_flag",
        ]
    )


def _default_run_id() -> str:
    return f"PHASE4-MPS-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


if __name__ == "__main__":
    output = build_master_production_schedule()
    print(f"Phase 4 MPS rows: {len(output)}")
    print(f"Output written to: {OUTPUT_FILE}")
