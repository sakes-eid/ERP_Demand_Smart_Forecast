"""Phase 2 bridge outputs for Phase 3 inventory planning."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.contracts.cross_phase_contracts import (  # noqa: E402
    PHASE2_INBOUND_SUMMARY_COLUMNS,
    PHASE2_SUPPLY_CAPABILITY_COLUMNS,
    PHASE2_SUPPLY_CONTEXT_SCHEMA_VERSION,
    PHASE_2,
    PHASE_3,
    SHARED_OUTPUT_DIR,
    ensure_columns,
    metadata_frame,
)


def build_phase2_supply_bridge(
    procurement_capability_context: pd.DataFrame,
    *,
    run_id: str,
    planning_iteration: int = 0,
    data_as_of_date: str = "",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build Phase 2 supply capability and inbound bridge files."""
    capability = procurement_capability_context.copy()
    if "supplier_status" not in capability.columns:
        capability["supplier_status"] = capability.get("supplier_option_active_flag", True).map(
            lambda value: "ACTIVE" if _to_bool(value) else "INACTIVE"
        )
    capability["supplier_active_flag"] = capability.get("supplier_option_active_flag", capability.get("supplier_active_feasible_flag", True))
    capability["supplier_history_status"] = capability.get("supplier_history_status", capability.get("supplier_evidence_status", "UNKNOWN"))
    capability["supplier_evidence_status"] = capability.get("supplier_evidence_status", capability.get("supplier_history_status", "UNKNOWN"))
    capability["supplier_requires_review"] = capability.get("supplier_requires_review", False)
    capability["supplier_watchlist_flag"] = capability.get("watchlist_flag", False)
    capability["unit_cost"] = capability.get("unit_price", capability.get("effective_unit_price", 0))
    capability["order_multiple"] = capability.get("order_multiple", capability.get("batch_size", 1))
    capability["batch_size"] = capability.get("batch_size", capability.get("order_multiple", 1))
    capability["fixed_order_cost"] = capability.get("fixed_order_cost", 0)
    capability["delivery_cost"] = capability.get("delivery_cost", capability.get("estimated_freight_cost", 0))
    capability["expected_quality_loss_rate"] = pd.to_numeric(capability.get("defect_rate", 0), errors="coerce").fillna(0)
    capability["expedite_capacity_limit"] = capability.get("expedite_capacity_limit", capability.get("supplier_per_order_capacity_units", 0))
    capability["expedite_reliability"] = capability.get("expedite_reliability", capability.get("supplier_reliability_score", 0))
    capability["next_confirmed_receipt_date"] = capability.get("next_confirmed_receipt_date", "")
    capability["inbound_data_quality_flag"] = capability.get("inbound_data_quality_flag", "CONFIRMED_OR_NONE")
    capability["inbound_warning_codes"] = capability.get("inbound_warning_codes", capability.get("procurement_requirement_warning_codes", "NONE"))

    capability = metadata_frame(
        capability,
        schema_version=PHASE2_SUPPLY_CONTEXT_SCHEMA_VERSION,
        run_id=run_id,
        planning_iteration=planning_iteration,
        source_phase=PHASE_2,
        target_phase=PHASE_3,
        data_as_of_date=data_as_of_date,
    )
    capability = ensure_columns(capability, PHASE2_SUPPLY_CAPABILITY_COLUMNS)

    inbound = _build_inbound_summary(procurement_capability_context)
    inbound = metadata_frame(
        inbound,
        schema_version=PHASE2_SUPPLY_CONTEXT_SCHEMA_VERSION,
        run_id=run_id,
        planning_iteration=planning_iteration,
        source_phase=PHASE_2,
        target_phase=PHASE_3,
        data_as_of_date=data_as_of_date,
    )
    inbound = ensure_columns(inbound, PHASE2_INBOUND_SUMMARY_COLUMNS)
    return capability, inbound


def save_phase2_supply_bridge(
    procurement_capability_context: pd.DataFrame,
    *,
    run_id: str,
    planning_iteration: int = 0,
    data_as_of_date: str = "",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build and save Phase 2 supply bridge files under shared/outputs."""
    SHARED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    capability, inbound = build_phase2_supply_bridge(
        procurement_capability_context,
        run_id=run_id,
        planning_iteration=planning_iteration,
        data_as_of_date=data_as_of_date,
    )
    capability.to_csv(SHARED_OUTPUT_DIR / "phase2_supply_capability_context.csv", index=False)
    inbound.to_csv(SHARED_OUTPUT_DIR / "phase2_inbound_supply_summary.csv", index=False)
    return capability, inbound


def _build_inbound_summary(capability: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sku_id, group in capability.groupby("sku_id", dropna=False):
        first = group.iloc[0]
        confirmed_7 = _num(first, "open_po_confirmed_units_7d")
        confirmed_30 = _num(first, "open_po_confirmed_units_30d")
        confirmed_60 = _num(first, "open_po_confirmed_units_60d")
        confirmed_90 = _num(first, "open_po_confirmed_units_90d")
        uncertain = _num(first, "uncertain_inbound_units")
        rows.append(
            {
                "sku_id": sku_id,
                "confirmed_inbound_units_7d": confirmed_7,
                "confirmed_inbound_units_30d": confirmed_30,
                "confirmed_inbound_units_60d": confirmed_60,
                "confirmed_inbound_units_90d": confirmed_90,
                "confirmed_inbound_before_need_date_units": confirmed_7,
                "uncertain_inbound_units": uncertain,
                "next_confirmed_receipt_date": first.get("next_confirmed_receipt_date", ""),
                "inbound_confidence": "MEDIUM" if uncertain else "HIGH",
                "inbound_warning_codes": first.get("inbound_warning_codes", first.get("procurement_requirement_warning_codes", "NONE")),
            }
        )
    return pd.DataFrame(rows)


def _num(row: pd.Series, column: str) -> float:
    if column not in row:
        return 0.0
    return float(pd.to_numeric(pd.Series([row[column]]), errors="coerce").fillna(0).iloc[0])


def _to_bool(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t", "active"}
