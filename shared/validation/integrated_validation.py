"""Integrated planning validation evidence builder."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import pandas as pd

from shared.contracts.cross_phase_contracts import (
    INTEGRATED_DECISION_COLUMNS,
    PHASE2_ALLOCATION_COLUMNS,
    PHASE2_ALLOCATION_SUMMARY_COLUMNS,
    PHASE2_INBOUND_SUMMARY_COLUMNS,
    PHASE2_SUPPLY_CAPABILITY_COLUMNS,
    PHASE3_ALLOCATION_VALIDATION_COLUMNS,
    PHASE3_REQUIREMENT_COLUMNS,
    PROJECT_ROOT,
    SHARED_OUTPUT_DIR,
    SHARED_VALIDATION_DIR,
    SUPPORTED_SCHEMA_VERSIONS,
    schema_status,
)


FILES = {
    "phase1_demand_context": PROJECT_ROOT / "phase 1" / "outputs" / "phase1_demand_planning_context.csv",
    "phase2_supply_capability_context": SHARED_OUTPUT_DIR / "phase2_supply_capability_context.csv",
    "phase2_inbound_supply_summary": SHARED_OUTPUT_DIR / "phase2_inbound_supply_summary.csv",
    "phase3_procurement_requirement_context": SHARED_OUTPUT_DIR / "phase3_procurement_requirement_context.csv",
    "phase2_procurement_allocation_context": SHARED_OUTPUT_DIR / "phase2_procurement_allocation_context.csv",
    "phase2_procurement_allocation_summary": SHARED_OUTPUT_DIR / "phase2_procurement_allocation_summary.csv",
    "phase3_allocation_validation": SHARED_OUTPUT_DIR / "phase3_allocation_validation.csv",
    "integrated_replenishment_decisions": SHARED_OUTPUT_DIR / "integrated_replenishment_decisions.csv",
    "phase2_strategy_summary": PROJECT_ROOT / "phase 2" / "outputs" / "phase2_supplier_strategy_summary.csv",
    "phase3_master_decisions": PROJECT_ROOT / "phase 3" / "outputs" / "inventory_control_master_decisions.csv",
}

SCHEMAS = {
    "phase2_supply_capability_context": PHASE2_SUPPLY_CAPABILITY_COLUMNS,
    "phase2_inbound_supply_summary": PHASE2_INBOUND_SUMMARY_COLUMNS,
    "phase3_procurement_requirement_context": PHASE3_REQUIREMENT_COLUMNS,
    "phase2_procurement_allocation_context": PHASE2_ALLOCATION_COLUMNS,
    "phase2_procurement_allocation_summary": PHASE2_ALLOCATION_SUMMARY_COLUMNS,
    "phase3_allocation_validation": PHASE3_ALLOCATION_VALIDATION_COLUMNS,
    "integrated_replenishment_decisions": INTEGRATED_DECISION_COLUMNS,
}


class IntegratedValidator:
    """Build self-contained integrated validation evidence."""

    def __init__(self) -> None:
        self.frames: dict[str, pd.DataFrame] = {}
        self.checks: list[dict] = []

    def build(self) -> dict:
        self._load_files()
        self._schema_checks()
        self._identity_checks()
        self._numeric_checks()
        self._active_issue_checks()
        self._reconciliation_checks()
        self._safety_checks()
        self._evidence_integrity_checks()
        pass_count = sum(1 for check in self.checks if check["status"] == "PASS")
        warning_count = sum(1 for check in self.checks if check["status"] == "WARNING")
        fail_count = sum(1 for check in self.checks if check["status"] == "FAIL")
        skipped_count = sum(1 for check in self.checks if check["status"] == "SKIPPED")
        status = "FAIL" if fail_count else ("WARNING" if warning_count else "PASS")
        decisions = self.frames.get("integrated_replenishment_decisions", pd.DataFrame())
        run_id = _mode_value(decisions, "run_id", "UNKNOWN")
        final_iteration = int(_num(decisions.iloc[0], "final_iteration")) if not decisions.empty else 0
        convergence = _mode_value(decisions, "convergence_status", "UNKNOWN")
        safety = self._safety_flags(fail_count)
        evidence = {
            "validation_metadata": {
                "validation_version": "1.0",
                "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                "run_id": run_id,
                "final_iteration": final_iteration,
                "validator_git_or_code_version": "LOCAL",
                "project_root": str(PROJECT_ROOT),
                "operating_mode": "INTEGRATED_BRIDGE_VALIDATION",
            },
            "overall_result": {
                "status": status,
                "pass_count": pass_count,
                "warning_count": warning_count,
                "fail_count": fail_count,
                "skipped_count": skipped_count,
                "convergence_status": convergence,
                "safe_for_analytical_downstream_use": safety["analytical"],
                "safe_for_planning_downstream_use": safety["planning"],
                "safe_for_execution_downstream_use": safety["execution"],
                "auto_apply_allowed": False,
                "purchase_order_creation_allowed": False,
            },
            "pipeline_snapshot": self._pipeline_snapshot(),
            "schema_contracts": self._schema_contracts(),
            "file_manifest": self._file_manifest(),
            "phase_summaries": self._phase_summaries(),
            "cross_phase_reconciliations": self._cross_phase_reconciliations(),
            "validation_checks": self.checks,
            "issues": [check for check in self.checks if check["status"] in {"FAIL", "WARNING", "SKIPPED"}],
            "warning_catalog": self._warning_catalog(),
            "key_metrics": self._key_metrics(),
            "strategy_counts": self._strategy_counts(),
            "representative_rows": self._representative_rows(),
            "configuration_snapshot": self._configuration_snapshot(),
            "future_phase_readiness": self._future_phase_readiness(),
            "known_limitations": self._known_limitations(),
        }
        return evidence

    def write(self) -> tuple[Path, Path, dict]:
        evidence = self.build()
        SHARED_VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
        json_path = SHARED_VALIDATION_DIR / "integrated_validation_evidence.json"
        txt_path = SHARED_VALIDATION_DIR / "integrated_validation_report.txt"
        clean_evidence = _json_safe(evidence)
        json_path.write_text(json.dumps(clean_evidence, indent=2, allow_nan=False), encoding="utf-8")
        txt_path.write_text(_human_report(clean_evidence), encoding="utf-8")
        return json_path, txt_path, clean_evidence

    def _load_files(self) -> None:
        for logical_name, path in FILES.items():
            if path.exists() and path.suffix.lower() == ".csv":
                try:
                    self.frames[logical_name] = pd.read_csv(path)
                except Exception:
                    self.frames[logical_name] = pd.DataFrame()
            else:
                self.frames[logical_name] = pd.DataFrame()

    def _add_check(self, check_id: str, category: str, severity: str, status: str, description: str, expected: object, actual: object, affected_keys=None, suggested_fix: str = "") -> None:
        deduped_keys = _dedupe_keys(affected_keys or [])
        affected_row_count = _affected_row_count(actual, affected_keys or [])
        self.checks.append(
            {
                "check_id": check_id,
                "category": category,
                "severity": severity,
                "status": status,
                "description": description,
                "expected": expected,
                "actual": actual,
                "affected_row_count": affected_row_count,
                "affected_unique_key_count": len(deduped_keys),
                "affected_keys": deduped_keys,
                "evidence": {"actual": actual},
                "suggested_fix": suggested_fix,
            }
        )

    def _schema_checks(self) -> None:
        for logical_name, columns in SCHEMAS.items():
            df = self.frames.get(logical_name, pd.DataFrame())
            missing = [column for column in columns if column not in df.columns]
            self._add_check(
                f"SCHEMA_{logical_name}",
                "SCHEMA",
                "FAIL" if missing else "PASS",
                "FAIL" if missing else "PASS",
                f"{logical_name} required columns are present",
                "no missing columns",
                {"missing_columns": missing},
                missing,
            )
            if "schema_version" in df.columns and logical_name in SUPPORTED_SCHEMA_VERSIONS:
                expected_version = SUPPORTED_SCHEMA_VERSIONS[logical_name]
                actual_versions = sorted(df["schema_version"].dropna().astype(str).unique().tolist())
                bad = df[~df["schema_version"].astype(str).eq(expected_version)]
                self._add_check(
                    f"SCHEMA_VERSION_{logical_name}",
                    "SCHEMA",
                    "FAIL" if len(bad) else "PASS",
                    "FAIL" if len(bad) else "PASS",
                    f"{logical_name} schema version is supported",
                    expected_version,
                    {"actual_versions": actual_versions, "mismatch_count": int(len(bad))},
                    _keys(bad),
                )

    def _identity_checks(self) -> None:
        key_map = {
            "phase2_supply_capability_context": ["sku_id", "supplier_id"],
            "phase2_inbound_supply_summary": ["sku_id"],
            "phase3_procurement_requirement_context": ["sku_id"],
            "phase2_procurement_allocation_context": ["allocation_id"],
            "phase2_procurement_allocation_summary": ["sku_id"],
            "phase3_allocation_validation": ["sku_id"],
            "integrated_replenishment_decisions": ["sku_id"],
        }
        for name, keys in key_map.items():
            df = self.frames.get(name, pd.DataFrame())
            missing = [key for key in keys if key not in df.columns]
            dup = len(df) if missing else int(df.duplicated(keys).sum())
            self._add_check(
                f"PRIMARY_KEY_{name}",
                "IDENTITY",
                "FAIL" if dup else "PASS",
                "FAIL" if dup else "PASS",
                f"{name} primary key is unique",
                0,
                {"primary_key": keys, "duplicate_count": dup, "missing_key_columns": missing},
                _keys(df[df.duplicated(keys, keep=False)]) if not missing else missing,
            )

    def _numeric_checks(self) -> None:
        checks = [
            ("phase3_procurement_requirement_context", ["gross_forecast_demand_30d", "usable_on_hand_inventory_units", "net_replenishment_requirement_units"]),
            ("phase2_procurement_allocation_context", ["allocated_usable_quantity_units", "final_supplier_purchase_quantity", "estimated_total_procurement_cost"]),
            ("phase2_procurement_allocation_summary", ["requested_requirement_units", "total_allocated_usable_quantity", "unallocated_requirement_units"]),
        ]
        for name, columns in checks:
            df = self.frames.get(name, pd.DataFrame())
            for column in columns:
                if column not in df.columns:
                    continue
                bad = df[pd.to_numeric(df[column], errors="coerce").fillna(0) < 0]
                self._add_check(f"NON_NEGATIVE_{name}_{column}", "NUMERIC", "FAIL" if len(bad) else "PASS", "FAIL" if len(bad) else "PASS", f"{column} is non-negative", 0, int(len(bad)), _keys(bad))

    def _warning_if_positive(self, check_id: str, category: str, df: pd.DataFrame, column: str, description: str) -> None:
        if df.empty or column not in df.columns:
            self._add_check(check_id, category, "SKIPPED", "SKIPPED", description, "column present", "missing column", [])
            return
        rows = df[pd.to_numeric(df[column], errors="coerce").fillna(0) > 0.01]
        self._add_check(
            check_id,
            category,
            "WARNING" if len(rows) else "PASS",
            "WARNING" if len(rows) else "PASS",
            description,
            "0 affected rows",
            _records(rows, ["sku_id", column]),
            _keys(rows),
        )

    def _warning_if_true(self, check_id: str, category: str, df: pd.DataFrame, column: str, description: str) -> None:
        if df.empty or column not in df.columns:
            self._add_check(check_id, category, "SKIPPED", "SKIPPED", description, "column present", "missing column", [])
            return
        rows = df[_bool_series(df[column])]
        self._add_check(
            check_id,
            category,
            "WARNING" if len(rows) else "PASS",
            "WARNING" if len(rows) else "PASS",
            description,
            "0 affected rows",
            _records(rows, ["sku_id", column, "validation_warning_codes"]),
            _keys(rows),
        )

    def _active_issue_checks(self) -> None:
        req = self.frames.get("phase3_procurement_requirement_context", pd.DataFrame())
        alloc = self.frames.get("phase2_procurement_allocation_context", pd.DataFrame())
        alloc_summary = self.frames.get("phase2_procurement_allocation_summary", pd.DataFrame())
        validation = self.frames.get("phase3_allocation_validation", pd.DataFrame())
        decisions = self.frames.get("integrated_replenishment_decisions", pd.DataFrame())

        self._warning_if_positive(
            "UNALLOCATED_REQUIREMENT_REMAINS",
            "ACTIVE_ISSUES",
            alloc_summary,
            "unallocated_requirement_units",
            "Unallocated requirement remains and must be reviewed.",
        )
        self._warning_if_true(
            "ALLOCATION_ADJUSTMENT_REQUIRED",
            "ACTIVE_ISSUES",
            validation,
            "adjustment_required_flag",
            "Phase 3 requested allocation adjustment.",
        )
        if not req.empty and "requirement_warning_codes" in req.columns:
            batch_rows = req[req["requirement_warning_codes"].astype(str).str.contains("BATCH_INVENTORY_RECONCILIATION_REVIEW", regex=False)]
            self._add_check(
                "BATCH_INVENTORY_RECONCILIATION_REVIEW",
                "ACTIVE_ISSUES",
                "WARNING" if len(batch_rows) else "PASS",
                "WARNING" if len(batch_rows) else "PASS",
                "Batch inventory reconciliation review is surfaced.",
                "0 active reconciliation warnings",
                _records(batch_rows, ["sku_id", "batch_inventory_reconciliation_difference", "batch_inventory_reconciliation_flag"]),
                _keys(batch_rows),
            )
        missing_arrival = pd.DataFrame()
        if not alloc.empty:
            arrival_cols = [column for column in ["expected_first_arrival_date", "expected_final_arrival_date"] if column in alloc.columns]
            if arrival_cols:
                mask = pd.Series(False, index=alloc.index)
                for column in arrival_cols:
                    mask = mask | alloc[column].fillna("").astype(str).str.strip().eq("")
                active = pd.to_numeric(alloc.get("allocated_usable_quantity_units", 0), errors="coerce").fillna(0) > 0
                missing_arrival = alloc[mask & active]
        self._add_check(
            "ARRIVAL_DATE_MISSING",
            "ACTIVE_ISSUES",
            "WARNING" if len(missing_arrival) else "PASS",
            "WARNING" if len(missing_arrival) else "PASS",
            "Active allocation rows have populated arrival dates for logistics readiness.",
            "arrival dates populated for active allocations",
            {
                "affected_rows": int(len(missing_arrival)),
                "missing_date_columns": arrival_cols if not alloc.empty else [],
                "missing_cells": int(sum(missing_arrival[column].fillna("").astype(str).str.strip().eq("").sum() for column in arrival_cols)) if not missing_arrival.empty else 0,
                "rows": _records(missing_arrival, ["allocation_id", "sku_id", "supplier_id", "expected_first_arrival_date", "expected_final_arrival_date"]),
            },
            _unique_keys(missing_arrival),
            "Populate expected arrival dates before using accepted allocations for logistics or committed planning.",
        )
        data_as_records = []
        for name in SCHEMAS:
            df = self.frames.get(name, pd.DataFrame())
            if "data_as_of_date" in df.columns:
                bad = df[df["data_as_of_date"].fillna("").astype(str).str.strip().eq("")]
                for idx, row in bad.head(100).iterrows():
                    data_as_records.append(
                        {
                            "file": name,
                            "row_index": int(idx),
                            "sku_id": str(row.get("sku_id", "")) if "sku_id" in row else "",
                            "affected_column": "data_as_of_date",
                        }
                    )
        data_as_keys = sorted({record["sku_id"] for record in data_as_records if record["sku_id"]})
        self._add_check(
            "DATA_AS_OF_DATE_MISSING",
            "ACTIVE_ISSUES",
            "WARNING" if data_as_records else "PASS",
            "WARNING" if data_as_records else "PASS",
            "Bridge rows identify the source data_as_of_date used for planning evidence.",
            "all bridge rows have data_as_of_date",
            {
                "affected_rows": int(len(data_as_records)),
                "unique_sku_count": int(len(data_as_keys)),
                "affected_files": sorted({record["file"] for record in data_as_records}),
                "affected_columns": ["data_as_of_date"],
                "affected_cells": int(len(data_as_records)),
                "sample_rows": data_as_records[:25],
            },
            data_as_keys[:25],
            "Populate data_as_of_date in bridge outputs so managers can distinguish stale and current planning evidence.",
        )
        fallback_records = self._fallback_assumption_records()
        self._add_check(
            "FALLBACK_COST_OR_TIMING_ASSUMPTIONS",
            "ACTIVE_ISSUES",
            "WARNING" if fallback_records else "PASS",
            "WARNING" if fallback_records else "PASS",
            "Fallback cost or timing assumptions are surfaced with affected fields.",
            "no active fallback assumptions",
            {
                "affected_rows": int(len(fallback_records)),
                "affected_files": sorted({record["file"] for record in fallback_records}),
                "affected_columns": sorted({record["affected_column"] for record in fallback_records}),
                "sample_rows": fallback_records[:25],
            },
            sorted({record["sku_id"] for record in fallback_records if record.get("sku_id")})[:25],
            "Replace fallback assumptions with explicit cost, timing, or policy source fields when available.",
        )
        infeasible = alloc[~_bool_series(alloc.get("allocation_feasible_flag", pd.Series(True, index=alloc.index)))] if not alloc.empty else pd.DataFrame()
        self._add_check(
            "ALLOCATION_INFEASIBLE",
            "ACTIVE_ISSUES",
            "WARNING" if len(infeasible) else "PASS",
            "WARNING" if len(infeasible) else "PASS",
            "Infeasible allocations are blocked/reviewed.",
            "0 infeasible allocation rows",
            _records(infeasible, ["allocation_id", "sku_id", "supplier_id", "allocation_warning_codes"]),
            _unique_keys(infeasible),
        )
        if not infeasible.empty and "allocation_warning_codes" in infeasible.columns:
            missing_reason = infeasible[infeasible["allocation_warning_codes"].fillna("").astype(str).str.strip().str.upper().isin(["", "NONE", "NAN"])]
        else:
            missing_reason = pd.DataFrame()
        self._add_check(
            "INFEASIBLE_ALLOCATION_WARNING_MEANINGFUL",
            "ACTIVE_ISSUES",
            "WARNING" if len(missing_reason) else "PASS",
            "WARNING" if len(missing_reason) else "PASS",
            "Every infeasible allocation row carries a meaningful warning code.",
            "allocation_warning_codes is not NONE/blank for infeasible rows",
            _records(missing_reason, ["allocation_id", "sku_id", "supplier_id", "allocation_feasible_flag", "allocation_warning_codes", "allocation_reason"]),
            _unique_keys(missing_reason),
            "Assign a specific infeasibility warning, such as CAPACITY_SHORTFALL, SPLIT_SOURCE_REVIEW_REQUIRED, or ALLOCATION_REQUIRES_REVIEW.",
        )
        incomplete = req[~_bool_series(req.get("inventory_context_complete_flag", pd.Series(True, index=req.index)))] if not req.empty else pd.DataFrame()
        self._add_check(
            "INVENTORY_CONTEXT_INCOMPLETE",
            "ACTIVE_ISSUES",
            "WARNING" if len(incomplete) else "PASS",
            "WARNING" if len(incomplete) else "PASS",
            "Inventory context completeness is explicit.",
            "all inventory context rows complete",
            _records(incomplete, ["sku_id", "inventory_context_complete_flag", "requirement_warning_codes"]),
            _keys(incomplete),
        )
        if not decisions.empty:
            zero_bad = decisions[
                (pd.to_numeric(decisions.get("net_replenishment_requirement_units", 0), errors="coerce").fillna(0) <= 0)
                & (pd.to_numeric(decisions.get("total_allocated_usable_quantity", 0), errors="coerce").fillna(0) <= 0)
                & ~decisions.get("final_recommendation", "").astype(str).eq("NO_PROCUREMENT_ACTION_REQUIRED")
            ]
            self._add_check(
                "ZERO_REQUIREMENT_RECOMMENDATION_SEMANTICS",
                "DECISION_QUALITY",
                "FAIL" if len(zero_bad) else "PASS",
                "FAIL" if len(zero_bad) else "PASS",
                "Zero requirement rows use no-action recommendation.",
                "NO_PROCUREMENT_ACTION_REQUIRED",
                _records(zero_bad, ["sku_id", "final_recommendation", "final_action_owner"]),
                _keys(zero_bad),
            )

    def _reconciliation_checks(self) -> None:
        req = self.frames.get("phase3_procurement_requirement_context", pd.DataFrame())
        phase1 = self.frames.get("phase1_demand_context", pd.DataFrame())
        inbound = self.frames.get("phase2_inbound_supply_summary", pd.DataFrame())
        alloc = self.frames.get("phase2_procurement_allocation_context", pd.DataFrame())
        alloc_summary = self.frames.get("phase2_procurement_allocation_summary", pd.DataFrame())
        validation = self.frames.get("phase3_allocation_validation", pd.DataFrame())
        if not req.empty and not phase1.empty:
            merged = req[["sku_id", "gross_forecast_demand_30d"]].merge(phase1[["sku_id", "forecast_demand_30d"]], on="sku_id", how="left")
            diff = (pd.to_numeric(merged["gross_forecast_demand_30d"], errors="coerce").fillna(0) - pd.to_numeric(merged["forecast_demand_30d"], errors="coerce").fillna(0)).abs()
            bad = merged[diff > 0.01]
            self._add_check("DEMAND_RECONCILIATION_PHASE1_TO_PHASE3", "RECONCILIATION", "FAIL" if len(bad) else "PASS", "FAIL" if len(bad) else "PASS", "Phase 1 30-day demand reconciles to Phase 3 gross demand", "<= 0.01 difference", int(len(bad)), _keys(bad))
        if not req.empty and not inbound.empty:
            merged = req[["sku_id", "confirmed_inbound_units_30d"]].merge(inbound[["sku_id", "confirmed_inbound_units_30d"]], on="sku_id", how="left", suffixes=("_phase3", "_phase2"))
            diff = (pd.to_numeric(merged["confirmed_inbound_units_30d_phase3"], errors="coerce").fillna(0) - pd.to_numeric(merged["confirmed_inbound_units_30d_phase2"], errors="coerce").fillna(0)).abs()
            bad = merged[diff > 0.01]
            self._add_check("INBOUND_RECONCILIATION_PHASE2_TO_PHASE3", "RECONCILIATION", "FAIL" if len(bad) else "PASS", "FAIL" if len(bad) else "PASS", "Phase 2 inbound reconciles to Phase 3 inbound use", "<= 0.01 difference", int(len(bad)), _keys(bad))
        if not alloc.empty and not alloc_summary.empty:
            grouped = alloc.groupby("sku_id")["allocated_usable_quantity_units"].sum().reset_index()
            merged = alloc_summary[["sku_id", "total_allocated_usable_quantity"]].merge(grouped, on="sku_id", how="left")
            diff = (pd.to_numeric(merged["total_allocated_usable_quantity"], errors="coerce").fillna(0) - pd.to_numeric(merged["allocated_usable_quantity_units"], errors="coerce").fillna(0)).abs()
            bad = merged[diff > 0.01]
            self._add_check("ALLOCATION_DETAIL_SUMMARY_RECONCILIATION", "RECONCILIATION", "FAIL" if len(bad) else "PASS", "FAIL" if len(bad) else "PASS", "Allocation detail sums reconcile to allocation summary", "<= 0.01 difference", int(len(bad)), _keys(bad))
        if not alloc_summary.empty and not validation.empty:
            merged = validation[["sku_id", "allocated_usable_quantity_units"]].merge(alloc_summary[["sku_id", "total_allocated_usable_quantity"]], on="sku_id", how="left")
            diff = (pd.to_numeric(merged["allocated_usable_quantity_units"], errors="coerce").fillna(0) - pd.to_numeric(merged["total_allocated_usable_quantity"], errors="coerce").fillna(0)).abs()
            bad = merged[diff > 0.01]
            self._add_check("PHASE3_VALIDATION_ALLOCATION_RECONCILIATION", "RECONCILIATION", "FAIL" if len(bad) else "PASS", "FAIL" if len(bad) else "PASS", "Phase 3 validation uses Phase 2 allocated quantity", "<= 0.01 difference", int(len(bad)), _keys(bad))
        self._critical_reconciliation_checks(req, alloc, alloc_summary, validation)

    def _critical_reconciliation_checks(self, req: pd.DataFrame, alloc: pd.DataFrame, alloc_summary: pd.DataFrame, validation: pd.DataFrame) -> None:
        if not req.empty:
            preclip = (
                pd.to_numeric(req.get("usable_on_hand_inventory_units", 0), errors="coerce").fillna(0)
                + pd.to_numeric(req.get("confirmed_inbound_before_need_date_units", 0), errors="coerce").fillna(0)
                - pd.to_numeric(req.get("reserved_or_committed_demand_units", 0), errors="coerce").fillna(0)
                - pd.to_numeric(req.get("active_backorder_units", 0), errors="coerce").fillna(0)
            )
            actual = pd.to_numeric(req.get("integrated_inventory_position_units", 0), errors="coerce").fillna(0)
            expected = preclip.clip(lower=0)
            bad = req[(expected - actual).abs() > 0.01]
            clipped = req[preclip < 0]
            self._add_check(
                "INTEGRATED_INVENTORY_POSITION_FORMULA",
                "RECONCILIATION",
                "FAIL" if len(bad) else "PASS",
                "FAIL" if len(bad) else "PASS",
                "Integrated inventory position formula reconciles.",
                "usable + inbound - reserved - backorders, clipped at zero",
                _records(bad.assign(pre_clipped_inventory_position_units=preclip.loc[bad.index]), ["sku_id", "pre_clipped_inventory_position_units", "integrated_inventory_position_units"]),
                _keys(bad),
            )
            clipping_transparent = (
                "pre_clipped_inventory_position_units" in req.columns
                and "inventory_position_clipped_flag" in req.columns
            )
            clipped_without_transparency = clipped if not clipping_transparent else pd.DataFrame()
            self._add_check(
                "INVENTORY_POSITION_CLIPPING_TRANSPARENCY",
                "RECONCILIATION",
                "WARNING" if len(clipped_without_transparency) else "PASS",
                "WARNING" if len(clipped_without_transparency) else "PASS",
                "Inventory position clipping is visible when pre-clipped value is negative.",
                "clipping flag/pre-clipped value present or no clipping required",
                {
                    "affected_rows": int(len(clipped_without_transparency)),
                    "clipped_rows": int(len(clipped)),
                    "transparency_fields_present": clipping_transparent,
                    "rows": _records(clipped.assign(pre_clipped_inventory_position_units=preclip.loc[clipped.index]), ["sku_id", "pre_clipped_inventory_position_units", "inventory_position_clipped_flag", "integrated_inventory_position_units", "inventory_position_method"]),
                },
                _keys(clipped_without_transparency),
            )
            double_bad = req[
                _bool_series(req.get("backorder_in_inventory_position_flag", pd.Series(False, index=req.index)))
                & ~_bool_series(req.get("double_count_prevention_flag", pd.Series(False, index=req.index)))
            ]
            self._add_check(
                "NO_DOUBLE_SUBTRACTION_BACKORDERS",
                "RECONCILIATION",
                "FAIL" if len(double_bad) else "PASS",
                "FAIL" if len(double_bad) else "PASS",
                "Backorders are not double-subtracted from inventory position.",
                "double_count_prevention_flag true when backorders are included",
                _records(double_bad, ["sku_id", "backorder_in_inventory_position_flag", "double_count_prevention_flag"]),
                _keys(double_bad),
            )
            unusable_bad = req[
                (pd.to_numeric(req.get("expired_inventory_units", 0), errors="coerce").fillna(0) + pd.to_numeric(req.get("quarantined_inventory_units", 0), errors="coerce").fillna(0) > 0)
                & (pd.to_numeric(req.get("usable_on_hand_inventory_units", 0), errors="coerce").fillna(0) > pd.to_numeric(req.get("current_inventory_units", 0), errors="coerce").fillna(0))
            ]
            self._add_check(
                "EXPIRED_QUARANTINED_EXCLUDED_FROM_USABLE",
                "INVENTORY",
                "FAIL" if len(unusable_bad) else "PASS",
                "FAIL" if len(unusable_bad) else "PASS",
                "Expired and quarantined stock are excluded from usable inventory.",
                "usable inventory <= current inventory when unusable stock exists",
                _records(unusable_bad, ["sku_id", "usable_on_hand_inventory_units", "expired_inventory_units", "quarantined_inventory_units"]),
                _keys(unusable_bad),
            )
        if not alloc_summary.empty:
            requested = pd.to_numeric(alloc_summary.get("requested_requirement_units", 0), errors="coerce").fillna(0)
            allocated = pd.to_numeric(alloc_summary.get("total_allocated_usable_quantity", 0), errors="coerce").fillna(0)
            unallocated = pd.to_numeric(alloc_summary.get("unallocated_requirement_units", 0), errors="coerce").fillna(0)
            bad = alloc_summary[(requested - allocated - unallocated).abs() > 0.01]
            self._add_check(
                "REQUESTED_EQUALS_ALLOCATED_PLUS_UNALLOCATED",
                "RECONCILIATION",
                "FAIL" if len(bad) else "PASS",
                "FAIL" if len(bad) else "PASS",
                "Requested requirement reconciles to allocated plus unallocated quantity.",
                "requested = allocated + unallocated",
                _records(bad, ["sku_id", "requested_requirement_units", "total_allocated_usable_quantity", "unallocated_requirement_units"]),
                _keys(bad),
            )
        if not alloc.empty:
            yield_rate = pd.to_numeric(alloc.get("allocated_usable_quantity_units", 0), errors="coerce").fillna(0) / pd.to_numeric(alloc.get("yield_adjusted_purchase_quantity", 0), errors="coerce").replace(0, pd.NA)
            yield_bad = alloc[(pd.to_numeric(alloc.get("allocated_usable_quantity_units", 0), errors="coerce").fillna(0) > 0) & yield_rate.isna()]
            self._add_check(
                "PURCHASE_QUANTITY_RECONCILES_WITH_YIELD",
                "RECONCILIATION",
                "FAIL" if len(yield_bad) else "PASS",
                "FAIL" if len(yield_bad) else "PASS",
                "Purchase quantity has valid yield basis.",
                "yield-adjusted purchase quantity populated for positive allocations",
                _records(yield_bad, ["allocation_id", "sku_id", "allocated_usable_quantity_units", "yield_adjusted_purchase_quantity"]),
                _keys(yield_bad),
            )
            moq_bad = alloc[pd.to_numeric(alloc.get("moq_adjusted_purchase_quantity", 0), errors="coerce").fillna(0) + 0.01 < pd.to_numeric(alloc.get("yield_adjusted_purchase_quantity", 0), errors="coerce").fillna(0)]
            batch_bad = alloc[pd.to_numeric(alloc.get("batch_rounded_purchase_quantity", 0), errors="coerce").fillna(0) + 0.01 < pd.to_numeric(alloc.get("moq_adjusted_purchase_quantity", 0), errors="coerce").fillna(0)]
            self._add_check("MOQ_ROUNDING_VALID", "RECONCILIATION", "FAIL" if len(moq_bad) else "PASS", "FAIL" if len(moq_bad) else "PASS", "MOQ-adjusted quantity is not below yield-adjusted quantity.", "moq_adjusted >= yield_adjusted", _records(moq_bad, ["allocation_id", "sku_id"]), _keys(moq_bad))
            self._add_check("BATCH_ROUNDING_VALID", "RECONCILIATION", "FAIL" if len(batch_bad) else "PASS", "FAIL" if len(batch_bad) else "PASS", "Batch-rounded quantity is not below MOQ-adjusted quantity.", "batch_rounded >= moq_adjusted", _records(batch_bad, ["allocation_id", "sku_id"]), _keys(batch_bad))
            cap_bad = alloc[pd.to_numeric(alloc.get("capacity_used_units", 0), errors="coerce").fillna(0) > pd.to_numeric(alloc.get("supplier_horizon_capacity_units", 0), errors="coerce").fillna(0) + 0.01]
            self._add_check("ALLOCATION_DOES_NOT_EXCEED_SUPPLIER_CAPACITY", "CAPACITY", "FAIL" if len(cap_bad) else "PASS", "FAIL" if len(cap_bad) else "PASS", "Allocation does not exceed supplier capacity.", "capacity_used <= supplier_horizon_capacity", _records(cap_bad, ["allocation_id", "sku_id", "supplier_id", "capacity_used_units", "supplier_horizon_capacity_units"]), _keys(cap_bad))
            split = alloc[_bool_series(alloc.get("split_delivery_used_flag", pd.Series(False, index=alloc.index)))]
            split_bad = split[pd.to_numeric(split.get("allocated_usable_quantity_units", 0), errors="coerce").fillna(0) < 0]
            self._add_check("SPLIT_QUANTITIES_NON_NEGATIVE", "CAPACITY", "FAIL" if len(split_bad) else "PASS", "FAIL" if len(split_bad) else "PASS", "Split allocation quantities are non-negative.", ">= 0", _records(split_bad, ["allocation_id", "sku_id", "supplier_id"]), _keys(split_bad))
            cost_sum = (
                pd.to_numeric(alloc.get("estimated_product_cost", 0), errors="coerce").fillna(0)
                + pd.to_numeric(alloc.get("estimated_fixed_order_cost", 0), errors="coerce").fillna(0)
                + pd.to_numeric(alloc.get("estimated_delivery_cost", 0), errors="coerce").fillna(0)
                + pd.to_numeric(alloc.get("estimated_expedite_cost", 0), errors="coerce").fillna(0)
                + pd.to_numeric(alloc.get("estimated_delay_cost", 0), errors="coerce").fillna(0)
                + pd.to_numeric(alloc.get("estimated_quality_cost", 0), errors="coerce").fillna(0)
            )
            total_cost = pd.to_numeric(alloc.get("estimated_total_procurement_cost", 0), errors="coerce").fillna(0)
            cost_bad = alloc[(cost_sum - total_cost).abs() > 0.01]
            self._add_check("PROCUREMENT_COST_COMPONENTS_RECONCILE", "COST", "FAIL" if len(cost_bad) else "PASS", "FAIL" if len(cost_bad) else "PASS", "Allocation cost components reconcile to total procurement cost.", "component sum = total cost", _records(cost_bad, ["allocation_id", "sku_id", "estimated_total_procurement_cost"]), _keys(cost_bad))
        if not validation.empty:
            cap_bad = validation[
                _bool_series(validation.get("allocation_accepted_flag", pd.Series(False, index=validation.index)))
                & (pd.to_numeric(validation.get("accepted_allocated_quantity_units", 0), errors="coerce").fillna(0) + 0.01 < pd.to_numeric(validation.get("allocated_usable_quantity_units", 0), errors="coerce").fillna(0))
            ]
            self._add_check("ACCEPTED_ALLOCATIONS_RESPECT_PHASE3_CAPS", "PHASE3_VALIDATION", "FAIL" if len(cap_bad) else "PASS", "FAIL" if len(cap_bad) else "PASS", "Accepted allocations respect Phase 3 caps.", "accepted quantity equals allocated quantity for accepted rows", _records(cap_bad, ["sku_id", "allocated_usable_quantity_units", "accepted_allocated_quantity_units"]), _keys(cap_bad))

    def _safety_checks(self) -> None:
        decisions = self.frames.get("integrated_replenishment_decisions", pd.DataFrame())
        if not decisions.empty:
            auto_true = int(decisions.get("auto_apply_allowed", pd.Series(False, index=decisions.index)).astype(str).str.lower().isin(["true", "1", "yes"]).sum())
            po_true = int(decisions.get("purchase_order_creation_allowed", pd.Series(False, index=decisions.index)).astype(str).str.lower().isin(["true", "1", "yes"]).sum())
            self._add_check("AUTO_APPLY_ALWAYS_FALSE", "SAFETY", "FAIL" if auto_true else "PASS", "FAIL" if auto_true else "PASS", "auto_apply_allowed is False everywhere", 0, auto_true)
            self._add_check("PO_CREATION_ALWAYS_FALSE", "SAFETY", "FAIL" if po_true else "PASS", "FAIL" if po_true else "PASS", "purchase_order_creation_allowed is False everywhere", 0, po_true)
            blocked = decisions[
                _bool_series(decisions.get("final_review_required", pd.Series(False, index=decisions.index)))
                | ~_bool_series(decisions.get("allocation_accepted_flag", pd.Series(True, index=decisions.index)))
                | (pd.to_numeric(decisions.get("total_allocated_usable_quantity", 0), errors="coerce").fillna(0) + 0.01 < pd.to_numeric(decisions.get("net_replenishment_requirement_units", 0), errors="coerce").fillna(0))
            ]
            execution_ready_blocked = blocked[_bool_series(blocked.get("procurement_execution_ready_flag", pd.Series(False, index=blocked.index)))]
            self._add_check(
                "BLOCKED_ROWS_NOT_EXECUTION_READY",
                "SAFETY",
                "FAIL" if len(execution_ready_blocked) else "PASS",
                "FAIL" if len(execution_ready_blocked) else "PASS",
                "Rows requiring review or adjustment are not execution-ready.",
                "procurement_execution_ready_flag false for blocked rows",
                _records(execution_ready_blocked, ["sku_id", "final_review_required", "allocation_accepted_flag", "procurement_execution_ready_flag"]),
                _keys(execution_ready_blocked),
            )
            planning_blockers = self._planning_blockers()
            safety = self._safety_flags(0)
            inconsistent = []
            if planning_blockers and safety["planning"]:
                inconsistent.append("safe_for_planning_downstream_use is True while planning blockers exist")
            if (review_required := _bool_count(decisions, "final_review_required") > 0) and safety["execution"]:
                inconsistent.append("safe_for_execution_downstream_use is True while review-required rows exist")
            row_ready_bad = decisions[
                _bool_series(decisions.get("procurement_execution_ready_flag", pd.Series(False, index=decisions.index)))
                & _bool_series(decisions.get("final_review_required", pd.Series(False, index=decisions.index)))
            ]
            if len(row_ready_bad):
                inconsistent.append("row-level execution-ready flag is True on review-required rows")
            self._add_check(
                "DOWNSTREAM_SAFETY_FLAGS_CONSISTENT",
                "SAFETY",
                "FAIL" if inconsistent else "PASS",
                "FAIL" if inconsistent else "PASS",
                "Overall downstream safety flags align with active warnings and row-level review/execution state.",
                "planning/execution safety false when blockers are active",
                {"inconsistencies": inconsistent, "planning_blockers": planning_blockers, "review_required": review_required},
                _keys(row_ready_bad),
            )

    def _evidence_integrity_checks(self) -> None:
        mismatches = []
        for check in self.checks:
            actual = check.get("actual")
            if not _actual_has_row_count(actual):
                continue
            actual_count = _affected_row_count(actual, check.get("affected_keys", []))
            if int(check.get("affected_row_count", 0)) != int(actual_count):
                mismatches.append(
                    {
                        "check_id": check.get("check_id"),
                        "affected_row_count": int(check.get("affected_row_count", 0)),
                        "actual_evidence_row_count": int(actual_count),
                    }
                )
        self._add_check(
            "AFFECTED_ROW_COUNT_EVIDENCE_CONSISTENCY",
            "EVIDENCE_INTEGRITY",
            "FAIL" if mismatches else "PASS",
            "FAIL" if mismatches else "PASS",
            "Each check's affected_row_count matches the row count stated in its actual evidence where applicable.",
            "affected_row_count equals actual.affected_rows or actual list length",
            {"affected_rows": len(mismatches), "mismatches": mismatches[:25]},
            [item["check_id"] for item in mismatches],
            "Fix validator evidence construction so affected row counts are not inferred from deduplicated keys.",
        )

    def _file_manifest(self) -> list[dict]:
        manifest = []
        for logical_name, path in FILES.items():
            df = self.frames.get(logical_name, pd.DataFrame())
            manifest.append(
                {
                    "logical_name": logical_name,
                    "path": str(path),
                    "exists": path.exists(),
                    "row_count": int(len(df)) if path.exists() else 0,
                    "column_count": int(len(df.columns)) if path.exists() else 0,
                    "sha256": _sha256(path) if path.exists() else "",
                    "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if path.exists() else "",
                    "schema_version": _mode_value(df, "schema_version", ""),
                    "source_phase": _mode_value(df, "source_phase", ""),
                    "required_or_optional": "required" if logical_name in SCHEMAS else "optional",
                }
            )
        return manifest

    def _schema_contracts(self) -> dict:
        key_map = {
            "phase2_supply_capability_context": ["sku_id", "supplier_id"],
            "phase2_inbound_supply_summary": ["sku_id"],
            "phase3_procurement_requirement_context": ["sku_id"],
            "phase2_procurement_allocation_context": ["allocation_id"],
            "phase2_procurement_allocation_summary": ["sku_id"],
            "phase3_allocation_validation": ["sku_id"],
            "integrated_replenishment_decisions": ["sku_id"],
        }
        return {
            name: {
                **schema_status(self.frames.get(name, pd.DataFrame()), columns),
                "primary_key": key_map.get(name, ["sku_id"]),
                "duplicate_count": _duplicate_count(self.frames.get(name, pd.DataFrame()), key_map.get(name, ["sku_id"])),
            }
            for name, columns in SCHEMAS.items()
        }

    def _pipeline_snapshot(self) -> dict:
        return {
            "phase1_rows": len(self.frames.get("phase1_demand_context", pd.DataFrame())),
            "phase2_supply_rows": len(self.frames.get("phase2_supply_capability_context", pd.DataFrame())),
            "phase3_requirement_rows": len(self.frames.get("phase3_procurement_requirement_context", pd.DataFrame())),
            "phase2_allocation_rows": len(self.frames.get("phase2_procurement_allocation_context", pd.DataFrame())),
            "phase3_validation_rows": len(self.frames.get("phase3_allocation_validation", pd.DataFrame())),
            "integrated_decision_rows": len(self.frames.get("integrated_replenishment_decisions", pd.DataFrame())),
        }

    def _phase_summaries(self) -> dict:
        return {
            "phase1": {"sku_count": _nunique(self.frames.get("phase1_demand_context", pd.DataFrame()), "sku_id")},
            "phase2": {"supplier_option_rows": len(self.frames.get("phase2_supply_capability_context", pd.DataFrame()))},
            "phase3": {"requirement_sku_count": _nunique(self.frames.get("phase3_procurement_requirement_context", pd.DataFrame()), "sku_id")},
        }

    def _cross_phase_reconciliations(self) -> dict:
        req = self.frames.get("phase3_procurement_requirement_context", pd.DataFrame())
        alloc_summary = self.frames.get("phase2_procurement_allocation_summary", pd.DataFrame())
        decisions = self.frames.get("integrated_replenishment_decisions", pd.DataFrame())
        return {
            "demand_reconciliation": {"phase3_gross_30d_total": _sum(req, "gross_forecast_demand_30d")},
            "inbound_reconciliation": {"phase3_confirmed_inbound_30d_total": _sum(req, "confirmed_inbound_units_30d")},
            "inventory_reconciliation": {"usable_on_hand_total": _sum(req, "usable_on_hand_inventory_units")},
            "requirement_reconciliation": {"net_requirement_total": _sum(req, "net_replenishment_requirement_units")},
            "allocation_reconciliation": {"allocated_usable_total": _sum(alloc_summary, "total_allocated_usable_quantity")},
            "yield_reconciliation": {"supplier_purchase_total": _sum(alloc_summary, "total_supplier_purchase_quantity")},
            "capacity_reconciliation": {"unallocated_requirement_total": _sum(alloc_summary, "unallocated_requirement_units")},
            "final_inventory_reconciliation": {"accepted_allocation_total": _sum(self.frames.get("phase3_allocation_validation", pd.DataFrame()), "accepted_allocated_quantity_units")},
            "cost_reconciliation": {"integrated_procurement_cost_total": _sum(decisions, "total_procurement_cost")},
            "review_execution_reconciliation": {"review_required_count": _bool_count(decisions, "final_review_required")},
        }

    def _key_metrics(self) -> dict:
        decisions = self.frames.get("integrated_replenishment_decisions", pd.DataFrame())
        req = self.frames.get("phase3_procurement_requirement_context", pd.DataFrame())
        alloc_summary = self.frames.get("phase2_procurement_allocation_summary", pd.DataFrame())
        return {
            "sku_count": _nunique(req, "sku_id"),
            "net_requirement_total": _sum(req, "net_replenishment_requirement_units"),
            "allocated_usable_total": _sum(alloc_summary, "total_allocated_usable_quantity"),
            "end_to_end_requirement_coverage_rate": _safe_ratio(
                _sum(self.frames.get("phase3_allocation_validation", pd.DataFrame()), "accepted_allocated_quantity_units"),
                _sum(req, "net_replenishment_requirement_units"),
            ),
            "planning_exception_rate": _safe_ratio(
                _bool_count(decisions, "final_review_required"),
                max(_nunique(decisions, "sku_id"), 1),
            ),
            "split_sourcing_count": _bool_count(alloc_summary, "split_sourcing_used_flag"),
            "auto_apply_true_count": _bool_count(decisions, "auto_apply_allowed"),
        }

    def _strategy_counts(self) -> dict:
        strategy = self.frames.get("phase2_strategy_summary", pd.DataFrame())
        decisions = self.frames.get("integrated_replenishment_decisions", pd.DataFrame())
        return {
            "phase2_supplier_strategy_counts": _counts(strategy, "recommended_supplier_strategy"),
            "integrated_recommendation_counts": _counts(decisions, "final_recommendation"),
            "integrated_priority_counts": _counts(decisions, "final_priority"),
        }

    def _representative_rows(self) -> dict:
        decisions = self.frames.get("integrated_replenishment_decisions", pd.DataFrame())
        req = self.frames.get("phase3_procurement_requirement_context", pd.DataFrame())
        alloc = self.frames.get("phase2_procurement_allocation_summary", pd.DataFrame())
        return {
            "healthy_or_no_order_sku": _sample(decisions, decisions.get("net_replenishment_requirement_units", pd.Series(dtype=float)).fillna(0).eq(0)),
            "stockout_sku": _sample(req, req.get("main_inventory_status", pd.Series(dtype=str)).astype(str).str.contains("STOCKOUT", regex=False)),
            "split_sourcing_sku": _sample(alloc, alloc.get("split_sourcing_used_flag", pd.Series(dtype=str)).astype(str).str.lower().isin(["true", "1", "yes"])),
            "aggregate_capacity_shortfall_sku": _sample(alloc, pd.to_numeric(alloc.get("unallocated_requirement_units", pd.Series(dtype=float)), errors="coerce").fillna(0).gt(0)),
            "phase4_review_sku": _sample(self.frames.get("phase3_master_decisions", pd.DataFrame()), self.frames.get("phase3_master_decisions", pd.DataFrame()).get("mandatory_review_gates", pd.Series(dtype=str)).astype(str).str.contains("PHASE4", regex=False)),
        }

    def _configuration_snapshot(self) -> dict:
        return {
            "max_iterations": 3,
            "quantity_tolerance_units": 1.0,
            "auto_apply_allowed": False,
            "purchase_order_creation_allowed": False,
        }

    def _future_phase_readiness(self) -> dict:
        return {
            "phase4_production_planning": {"status": "PARTIAL", "available_fields": ["phase4 review flags", "net requirement"], "missing_fields": ["BOM", "production capacity"], "blockers": ["No Phase 4 model yet"], "suggested_next_step": "Add BOM and make/buy contracts."},
            "logistics_planning": {"status": "PARTIAL", "available_fields": ["arrival-date schema fields", "shipment placeholders"], "missing_fields": ["populated active-allocation arrival dates", "lanes", "carrier costs"], "blockers": ["Active allocation arrival-date fields are present but currently blank", "No logistics optimizer"], "suggested_next_step": "Populate expected arrival dates before committed logistics planning."},
            "finance_planning": {"status": "PARTIAL", "available_fields": ["procurement cost", "payment terms"], "missing_fields": ["cash constraints"], "blockers": ["No cash-flow engine"], "suggested_next_step": "Add finance constraints."},
            "execution_po_generation": {"status": "BLOCKED_BY_DESIGN", "available_fields": ["allocation plan"], "missing_fields": ["approval workflow"], "blockers": ["PO creation disabled"], "suggested_next_step": "Build approval and execution workflow later."},
            "manager_ui": {"status": "READY_FOR_PROTOTYPE", "available_fields": ["final decisions", "validation evidence"], "missing_fields": ["UI screens"], "blockers": ["No UI in this step"], "suggested_next_step": "Build dashboard later."},
            "total_cost_engine": {"status": "PARTIAL", "available_fields": ["procurement cost"], "missing_fields": ["logistics, finance, production costs"], "blockers": ["Later phases missing"], "suggested_next_step": "Extend cost contracts by phase."},
        }

    def _warning_catalog(self) -> list[dict]:
        return [{"warning_code": warning, "scope": "KNOWN_LIMITATION"} for warning in self._known_limitations()]

    def _known_limitations(self) -> list[str]:
        limitations = [
            "No automatic purchase order creation.",
            "No automatic supplier mutation.",
            "No automatic inventory mutation.",
            "No execution workflow.",
            "No production integration yet.",
            "No logistics optimization yet.",
            "No finance/cash-flow constraint yet.",
            "No simulation.",
            "No final UI.",
        ]
        if self._fallback_assumption_records():
            limitations.append("Some cost and timing assumptions remain fallback-based.")
        return limitations

    def _safety_flags(self, fail_count: int) -> dict[str, bool]:
        decisions = self.frames.get("integrated_replenishment_decisions", pd.DataFrame())
        review_required = _bool_count(decisions, "final_review_required") > 0
        po_disabled = _bool_count(decisions, "purchase_order_creation_allowed") == 0
        auto_disabled = _bool_count(decisions, "auto_apply_allowed") == 0
        planning_blocked = bool(self._planning_blockers())
        return {
            "analytical": fail_count == 0,
            "planning": fail_count == 0 and not planning_blocked,
            "execution": (
                fail_count == 0
                and not review_required
                and not planning_blocked
                and po_disabled is False
                and auto_disabled is False
            ),
        }

    def _planning_blockers(self) -> list[str]:
        alloc = self.frames.get("phase2_procurement_allocation_context", pd.DataFrame())
        alloc_summary = self.frames.get("phase2_procurement_allocation_summary", pd.DataFrame())
        validation = self.frames.get("phase3_allocation_validation", pd.DataFrame())
        blockers = []
        if _sum(alloc_summary, "unallocated_requirement_units") > 0.01:
            blockers.append("UNALLOCATED_REQUIREMENT_REMAINS")
        if not alloc_summary.empty and _bool_count(alloc_summary, "allocation_feasible_flag") < len(alloc_summary):
            blockers.append("ALLOCATION_INFEASIBLE_SUMMARY_ROWS")
        if not alloc.empty and _bool_count(alloc, "allocation_feasible_flag") < len(alloc):
            blockers.append("ALLOCATION_INFEASIBLE_DETAIL_ROWS")
        if _bool_count(validation, "adjustment_required_flag") > 0:
            blockers.append("ALLOCATION_ADJUSTMENT_REQUIRED")
        if not alloc.empty:
            arrival_cols = [column for column in ["expected_first_arrival_date", "expected_final_arrival_date"] if column in alloc.columns]
            if arrival_cols:
                active = pd.to_numeric(alloc.get("allocated_usable_quantity_units", 0), errors="coerce").fillna(0) > 0
                missing = pd.Series(False, index=alloc.index)
                for column in arrival_cols:
                    missing = missing | alloc[column].fillna("").astype(str).str.strip().eq("")
                if int((active & missing).sum()):
                    blockers.append("ARRIVAL_DATE_MISSING_FOR_ACTIVE_ALLOCATIONS")
        return sorted(set(blockers))

    def _fallback_assumption_records(self) -> list[dict]:
        records = []
        needles = ("FALLBACK", "ASSUMPTION", "PAYMENT_TERMS_COST_NOT_MODELED")
        for name, df in self.frames.items():
            if df.empty:
                continue
            text_columns = [
                column
                for column in df.columns
                if any(token in column.lower() for token in ["warning", "reason", "note", "method", "source", "assumption"])
            ]
            for column in text_columns:
                values = df[column].fillna("").astype(str)
                mask = values.str.upper().apply(lambda value: any(needle in value for needle in needles))
                for idx, row in df[mask].head(25).iterrows():
                    records.append(
                        {
                            "file": name,
                            "row_index": int(idx),
                            "sku_id": str(row.get("sku_id", "")) if "sku_id" in row else "",
                            "affected_column": column,
                            "value": str(row.get(column, ""))[:300],
                        }
                    )
        return records[:100]


def write_integrated_validation() -> tuple[Path, Path, dict]:
    return IntegratedValidator().write()


def _keys(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return []
    if "sku_id" in df.columns:
        return df["sku_id"].astype(str).head(25).tolist()
    return df.index.astype(str).head(25).tolist()


def _unique_keys(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return []
    if "sku_id" in df.columns:
        return sorted({str(value) for value in df["sku_id"].dropna().tolist()})[:25]
    return sorted({str(value) for value in df.index.tolist()})[:25]


def _dedupe_keys(keys) -> list[str]:
    deduped = []
    seen = set()
    for key in keys or []:
        text = str(key)
        if text not in seen:
            seen.add(text)
            deduped.append(text)
    return deduped


def _actual_has_row_count(actual: object) -> bool:
    if isinstance(actual, list):
        return True
    if isinstance(actual, dict) and "affected_rows" in actual:
        return True
    return False


def _affected_row_count(actual: object, affected_keys=None) -> int:
    if isinstance(actual, dict) and "affected_rows" in actual:
        try:
            return int(actual.get("affected_rows") or 0)
        except Exception:
            return 0
    if isinstance(actual, list):
        return len(actual)
    if isinstance(actual, int):
        return int(actual)
    return len(affected_keys or [])


def _records(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    if df.empty:
        return []
    available = [column for column in columns if column in df.columns]
    if not available:
        return []
    return df[available].head(25).to_dict(orient="records")


def _sum(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    return round(float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum()), 2)


def _safe_ratio(numerator: float, denominator: float):
    if denominator is None or float(denominator) == 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def _num(row: pd.Series, column: str) -> float:
    if row is None or column not in row:
        return 0.0
    return float(pd.to_numeric(pd.Series([row[column]]), errors="coerce").fillna(0).iloc[0])


def _mode_value(df: pd.DataFrame, column: str, default: str) -> str:
    if df.empty or column not in df.columns or df[column].dropna().empty:
        return default
    return str(df[column].dropna().astype(str).mode().iloc[0])


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _duplicate_count(df: pd.DataFrame, columns) -> int:
    if isinstance(columns, str):
        columns = [columns]
    if df.empty or not set(columns).issubset(df.columns):
        return 0
    return int(df.duplicated(columns).sum())


def _nunique(df: pd.DataFrame, column: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    return int(df[column].nunique())


def _bool_count(df: pd.DataFrame, column: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    return int(df[column].astype(str).str.lower().isin(["true", "1", "yes"]).sum())


def _bool_series(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y", "t"])


def _counts(df: pd.DataFrame, column: str) -> dict:
    if df.empty or column not in df.columns:
        return {}
    return df[column].fillna("UNKNOWN").astype(str).value_counts().to_dict()


def _sample(df: pd.DataFrame, mask: pd.Series) -> dict:
    if df.empty or mask.empty:
        return {}
    rows = df[mask]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


def _json_safe(value):
    if isinstance(value, dict):
        return {str(_json_safe(key)): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if pd.isna(value) if not isinstance(value, (list, dict, tuple)) else False:
        return None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _human_report(evidence: dict) -> str:
    result = evidence["overall_result"]
    lines = [
        "Integrated Planning Validation Report",
        f"Generated at: {evidence['validation_metadata']['generated_at']}",
        f"Run ID: {evidence['validation_metadata']['run_id']}",
        f"Overall status: {result['status']}",
        f"PASS: {result['pass_count']}",
        f"WARNING: {result['warning_count']}",
        f"FAIL: {result['fail_count']}",
        f"SKIPPED: {result['skipped_count']}",
        "",
        "Critical failures:",
    ]
    failures = [check for check in evidence["validation_checks"] if check["status"] == "FAIL"]
    if not failures:
        lines.append("None.")
    else:
        for check in failures:
            lines.append(f"- {check['check_id']}: {check['actual']}")
    lines.extend(["", "Key metrics:"])
    for key, value in evidence["key_metrics"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "Downstream safety:",
            f"- analytical: {result['safe_for_analytical_downstream_use']}",
            f"- planning: {result['safe_for_planning_downstream_use']}",
            f"- execution: {result['safe_for_execution_downstream_use']}",
            f"- auto_apply_allowed: {result['auto_apply_allowed']}",
            f"- purchase_order_creation_allowed: {result['purchase_order_creation_allowed']}",
            "",
            "Warnings:",
        ]
    )
    warnings = [check for check in evidence["validation_checks"] if check["status"] == "WARNING"]
    if not warnings:
        lines.append("None.")
    else:
        for check in warnings:
            lines.append(f"- {check['check_id']}: {check['actual']}")
    return "\n".join(lines)
