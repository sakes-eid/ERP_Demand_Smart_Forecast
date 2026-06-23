"""Advisory supplier coverage checks for Phase 4 BOM component shortages."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE4_DIR.parent
PHASE3_SHORTAGE_FILE = PROJECT_ROOT / "phase 3" / "outputs" / "phase4_component_inventory_check.csv"
PHASE2_OUTPUT_FILE = PROJECT_ROOT / "phase 2" / "outputs" / "phase4_component_supplier_check.csv"


def build_phase4_component_supplier_check(
    supplier_sku_scores: pd.DataFrame,
    shortages_file: Path = PHASE3_SHORTAGE_FILE,
    output_file: Path = PHASE2_OUTPUT_FILE,
) -> pd.DataFrame:
    """Check whether component shortage SKUs have eligible supplier coverage."""
    if not shortages_file.exists():
        return _write_empty(output_file)

    shortages = pd.read_csv(shortages_file)
    if shortages.empty:
        return _write_empty(output_file)

    required_columns = {"planning_run_id", "component_sku", "component_name", "shortage_qty", "inventory_status"}
    missing = required_columns.difference(shortages.columns)
    if missing:
        raise ValueError(f"Phase 4 inventory shortage file missing columns: {sorted(missing)}")

    shortage_rows = shortages[
        (pd.to_numeric(shortages["shortage_qty"], errors="coerce").fillna(0) > 0)
        | (shortages["inventory_status"].astype(str) == "MISSING_INVENTORY_RECORD")
    ].copy()
    if shortage_rows.empty:
        return _write_empty(output_file)

    scores = supplier_sku_scores.copy()
    scores["sku_id"] = scores["sku_id"].astype(str).str.strip()
    rows = []
    for _, shortage in shortage_rows.iterrows():
        component_sku = str(shortage["component_sku"]).strip()
        options = scores[scores["sku_id"] == component_sku].copy()
        eligible = _eligible_options(options)
        if eligible.empty:
            rows.append(_missing_supplier_row(shortage))
            continue

        sort_column = "adjusted_supplier_score" if "adjusted_supplier_score" in eligible.columns else "supplier_score"
        eligible[sort_column] = pd.to_numeric(eligible[sort_column], errors="coerce").fillna(0)
        selected = eligible.sort_values(sort_column, ascending=False).iloc[0]
        rows.append(
            {
                "planning_run_id": shortage["planning_run_id"],
                "component_sku": component_sku,
                "component_name": shortage["component_name"],
                "shortage_qty": shortage["shortage_qty"],
                "supplier_available_flag": True,
                "eligible_supplier_count": int(len(eligible)),
                "recommended_supplier_id": selected.get("supplier_id", ""),
                "supplier_risk_class": selected.get("procurement_risk_class", "UNKNOWN"),
                "expected_lead_time": selected.get("lead_time_mean_days", ""),
                "expected_unit_cost": selected.get("unit_cost", ""),
                "supplier_review_required_flag": bool(selected.get("supplier_requires_review", False)),
                "advisory_only_flag": True,
            }
        )

    check = pd.DataFrame(rows, columns=_output_columns())
    output_file.parent.mkdir(parents=True, exist_ok=True)
    check.to_csv(output_file, index=False)
    return check


def _eligible_options(options: pd.DataFrame) -> pd.DataFrame:
    if options.empty:
        return options
    eligible = options.copy()
    if "is_supplier_active" in eligible.columns:
        eligible = eligible[eligible["is_supplier_active"].astype(str).str.lower().isin({"true", "1", "yes"})]
    if "is_feasible_supplier_option" in eligible.columns:
        eligible = eligible[eligible["is_feasible_supplier_option"].astype(str).str.lower().isin({"true", "1", "yes"})]
    return eligible


def _missing_supplier_row(shortage: pd.Series) -> dict:
    return {
        "planning_run_id": shortage["planning_run_id"],
        "component_sku": shortage["component_sku"],
        "component_name": shortage["component_name"],
        "shortage_qty": shortage["shortage_qty"],
        "supplier_available_flag": False,
        "eligible_supplier_count": 0,
        "recommended_supplier_id": "",
        "supplier_risk_class": "MISSING_SUPPLIER_COVERAGE",
        "expected_lead_time": "",
        "expected_unit_cost": "",
        "supplier_review_required_flag": True,
        "advisory_only_flag": True,
    }


def _write_empty(output_file: Path) -> pd.DataFrame:
    check = _empty_output()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    check.to_csv(output_file, index=False)
    return check


def _empty_output() -> pd.DataFrame:
    return pd.DataFrame(columns=_output_columns())


def _output_columns() -> list[str]:
    return [
        "planning_run_id",
        "component_sku",
        "component_name",
        "shortage_qty",
        "supplier_available_flag",
        "eligible_supplier_count",
        "recommended_supplier_id",
        "supplier_risk_class",
        "expected_lead_time",
        "expected_unit_cost",
        "supplier_review_required_flag",
        "advisory_only_flag",
    ]
