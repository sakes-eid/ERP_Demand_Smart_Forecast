"""Advisory BOM explosion bridge for Phase 4 initialization."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE4_DIR.parent
PHASE1_FUTURE_FORECAST_FILE = PROJECT_ROOT / "phase 1" / "outputs" / "future_forecast_results.csv"
BOM_FILE = PHASE4_DIR / "data" / "phase4_bom.csv"
MPS_FILE = PHASE4_DIR / "outputs" / "phase4_master_production_schedule.csv"
OUTPUT_FILE = PHASE4_DIR / "outputs" / "phase4_bom_component_requirements.csv"

FINISHED_BIKE_SKUS = {"SKU-BIKE-ROAD-001", "SKU-BIKE-MT-001"}
REQUIRED_BOM_COLUMNS = {
    "finished_sku",
    "finished_product_name",
    "component_sku",
    "component_name",
    "quantity_per_finished_unit",
    "component_type",
    "critical_component_flag",
    "phase4_active_flag",
}


def build_bom_component_requirements(
    forecast_file: Path = PHASE1_FUTURE_FORECAST_FILE,
    bom_file: Path = BOM_FILE,
    mps_file: Path = MPS_FILE,
    output_file: Path = OUTPUT_FILE,
    planning_run_id: str | None = None,
) -> pd.DataFrame:
    """Explode finished-bike MPS planned production, falling back to forecast demand."""
    planning_run_id = planning_run_id or os.environ.get("INTEGRATED_RUN_ID") or _default_run_id()
    bom = _load_bom(bom_file)
    mps = _load_valid_mps(mps_file)
    if not mps.empty:
        requirements = _build_from_mps(mps, bom, planning_run_id)
    else:
        forecast = _load_forecast(forecast_file)
        requirements = _build_from_forecast(forecast, bom, planning_run_id)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    requirements.to_csv(output_file, index=False)
    return requirements


def _build_from_mps(mps: pd.DataFrame, bom: pd.DataFrame, planning_run_id: str) -> pd.DataFrame:
    """Explode MPS planned production quantities into gross component requirements."""
    active_bom = bom[_to_bool(bom["phase4_active_flag"])].copy()
    mps_rows = mps[mps["finished_sku"].isin(FINISHED_BIKE_SKUS)].copy()
    if mps_rows.empty:
        return _empty_output()
    mps_rows["mps_planned_production_qty"] = pd.to_numeric(
        mps_rows["planned_production_qty"],
        errors="coerce",
    ).fillna(0).clip(lower=0)
    mps_rows["forecast_demand_qty"] = pd.to_numeric(
        mps_rows.get("forecast_demand_qty", 0),
        errors="coerce",
    ).fillna(0).clip(lower=0)
    mps_rows["forecast_period"] = mps_rows["period_start"].astype(str)
    exploded = mps_rows.merge(active_bom, on="finished_sku", how="inner")
    exploded["quantity_per_finished_unit"] = pd.to_numeric(
        exploded["quantity_per_finished_unit"],
        errors="coerce",
    ).fillna(0)
    exploded["finished_goods_forecast_qty"] = exploded["forecast_demand_qty"]
    exploded["gross_component_requirement_qty"] = (
        exploded["mps_planned_production_qty"] * exploded["quantity_per_finished_unit"]
    ).round(4)
    exploded["planning_run_id"] = planning_run_id
    exploded["source_phase"] = "PHASE4_MPS_BOM_BRIDGE"
    exploded["advisory_only_flag"] = True
    exploded["bom_explosion_basis"] = "MPS_PLANNED_PRODUCTION"
    return _select_output_columns(exploded)


def _build_from_forecast(forecast: pd.DataFrame, bom: pd.DataFrame, planning_run_id: str) -> pd.DataFrame:
    """Explode finished-bike forecast quantities into gross component requirements."""
    bike_forecast = forecast[forecast["sku_id"].isin(FINISHED_BIKE_SKUS)].copy()
    if bike_forecast.empty:
        return _empty_output()
    bike_forecast["forecast_period"] = bike_forecast["forecast_date"].astype(str)
    bike_forecast["finished_goods_forecast_qty"] = pd.to_numeric(
        bike_forecast["forecast_quantity"],
        errors="coerce",
    ).fillna(0).clip(lower=0)
    active_bom = bom[_to_bool(bom["phase4_active_flag"])].copy()
    exploded = bike_forecast.merge(active_bom, left_on="sku_id", right_on="finished_sku", how="inner")
    exploded["quantity_per_finished_unit"] = pd.to_numeric(
        exploded["quantity_per_finished_unit"],
        errors="coerce",
    ).fillna(0)
    exploded["gross_component_requirement_qty"] = (
        exploded["finished_goods_forecast_qty"] * exploded["quantity_per_finished_unit"]
    ).round(4)
    exploded["planning_run_id"] = planning_run_id
    exploded["source_phase"] = "PHASE1_FORECAST_PHASE4_BOM_BRIDGE"
    exploded["advisory_only_flag"] = True
    exploded["period_start"] = ""
    exploded["period_end"] = ""
    exploded["mps_planned_production_qty"] = 0.0
    exploded["bom_explosion_basis"] = "FORECAST_FALLBACK"
    return _select_output_columns(exploded)


def _load_valid_mps(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    mps = pd.read_csv(path)
    required = {"planning_run_id", "period_start", "period_end", "finished_sku", "planned_production_qty"}
    if mps.empty or not required.issubset(mps.columns):
        return pd.DataFrame()
    return mps


def _load_forecast(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Phase 1 future forecast output not found: {path}")
    forecast = pd.read_csv(path)
    required = {"sku_id", "forecast_date", "forecast_quantity"}
    missing = required.difference(forecast.columns)
    if missing:
        raise ValueError(f"Phase 1 future forecast output is missing columns: {sorted(missing)}")
    return forecast


def _load_bom(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Phase 4 BOM file not found: {path}")
    bom = pd.read_csv(path)
    missing = REQUIRED_BOM_COLUMNS.difference(bom.columns)
    if missing:
        raise ValueError(f"Phase 4 BOM file is missing columns: {sorted(missing)}")
    return bom


def _select_output_columns(exploded: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "planning_run_id",
        "forecast_period",
        "planning_period",
        "period_start",
        "period_end",
        "finished_sku",
        "component_sku",
        "component_name",
        "finished_goods_forecast_qty",
        "mps_planned_production_qty",
        "quantity_per_finished_unit",
        "gross_component_requirement_qty",
        "bom_explosion_basis",
        "source_phase",
        "advisory_only_flag",
    ]
    result = exploded.copy()
    if "planning_period" not in result.columns:
        result["planning_period"] = result.get("period_start", result.get("forecast_period", ""))
    for column in columns:
        if column not in result.columns:
            result[column] = ""
    return result[columns].copy()


def _empty_output() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "planning_run_id",
            "forecast_period",
            "planning_period",
            "period_start",
            "period_end",
            "finished_sku",
            "component_sku",
            "component_name",
            "finished_goods_forecast_qty",
            "mps_planned_production_qty",
            "quantity_per_finished_unit",
            "gross_component_requirement_qty",
            "bom_explosion_basis",
            "source_phase",
            "advisory_only_flag",
        ]
    )


def _to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _default_run_id() -> str:
    return f"PHASE4-INIT-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


if __name__ == "__main__":
    output = build_bom_component_requirements()
    print(f"Phase 4 BOM component requirement rows: {len(output)}")
    print(f"Output written to: {OUTPUT_FILE}")
