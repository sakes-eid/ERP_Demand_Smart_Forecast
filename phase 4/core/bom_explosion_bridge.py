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
    output_file: Path = OUTPUT_FILE,
    planning_run_id: str | None = None,
) -> pd.DataFrame:
    """Explode finished-bike forecasts into advisory gross component requirements."""
    planning_run_id = planning_run_id or os.environ.get("INTEGRATED_RUN_ID") or _default_run_id()
    forecast = _load_forecast(forecast_file)
    bom = _load_bom(bom_file)

    bike_forecast = forecast[forecast["sku_id"].isin(FINISHED_BIKE_SKUS)].copy()
    if bike_forecast.empty:
        requirements = _empty_output()
    else:
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
        requirements = exploded[
            [
                "planning_run_id",
                "forecast_period",
                "finished_sku",
                "component_sku",
                "component_name",
                "finished_goods_forecast_qty",
                "quantity_per_finished_unit",
                "gross_component_requirement_qty",
                "source_phase",
                "advisory_only_flag",
            ]
        ].copy()

    output_file.parent.mkdir(parents=True, exist_ok=True)
    requirements.to_csv(output_file, index=False)
    return requirements


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


def _empty_output() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "planning_run_id",
            "forecast_period",
            "finished_sku",
            "component_sku",
            "component_name",
            "finished_goods_forecast_qty",
            "quantity_per_finished_unit",
            "gross_component_requirement_qty",
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
