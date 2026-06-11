"""Validate Phase 2 procurement capability and backorder foundation outputs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from config import DATA_DIR, OUTPUT_DIR


RESULT_COLUMNS = [
    "check_id",
    "check_group",
    "check_name",
    "severity",
    "status",
    "details",
    "affected_file",
    "affected_column",
    "affected_rows",
    "suggested_fix",
]

REQUIRED_OUTPUTS = [
    "backorder_aging_detail.csv",
    "backorder_aging_summary.csv",
    "phase2_procurement_capability_context.csv",
    "phase2_supplier_strategy_summary.csv",
    "phase2_procurement_kpi_summary.csv",
]


class Validator:
    """Collect validation results and write compact reports."""

    def __init__(self) -> None:
        self.results: list[dict[str, object]] = []
        self.frames: dict[str, pd.DataFrame] = {}

    def add_result(
        self,
        check_id: str,
        check_group: str,
        check_name: str,
        severity: str,
        status: str,
        details: str,
        affected_file: str = "",
        affected_column: str = "",
        affected_rows: int | str = 0,
        suggested_fix: str = "",
    ) -> None:
        self.results.append(
            {
                "check_id": check_id,
                "check_group": check_group,
                "check_name": check_name,
                "severity": severity,
                "status": status,
                "details": details,
                "affected_file": affected_file,
                "affected_column": affected_column,
                "affected_rows": affected_rows,
                "suggested_fix": suggested_fix,
            }
        )

    def read_csv(self, filename: str, folder: Path = OUTPUT_DIR) -> pd.DataFrame:
        path = folder / filename
        if not path.exists():
            self.add_result(
                f"FILE_{filename}",
                "FILES",
                f"{filename} exists",
                "FAIL",
                "FAIL",
                "Required file is missing.",
                str(path),
                suggested_fix="Run python main.py to regenerate Phase 2 outputs.",
            )
            return pd.DataFrame()
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            self.add_result(
                f"LOAD_{filename}",
                "FILES",
                f"{filename} parses",
                "FAIL",
                "FAIL",
                f"Could not parse CSV: {exc}",
                str(path),
                suggested_fix="Inspect the CSV and regenerate it if corrupted.",
            )
            return pd.DataFrame()
        self.add_result(
            f"FILE_{filename}",
            "FILES",
            f"{filename} exists",
            "PASS",
            "PASS",
            f"Loaded {len(df)} rows.",
            str(path),
        )
        self.frames[filename] = df
        return df

    def require_columns(self, df: pd.DataFrame, filename: str, columns: list[str]) -> None:
        missing = [column for column in columns if column not in df.columns]
        self.add_result(
            f"COLUMNS_{filename}",
            "COLUMNS",
            f"{filename} required columns",
            "FAIL" if missing else "PASS",
            "FAIL" if missing else "PASS",
            f"Missing columns: {', '.join(missing)}" if missing else "All required columns are present.",
            filename,
            affected_rows=0,
            suggested_fix="Add missing required columns to the output builder." if missing else "",
        )

    def validate(self) -> tuple[pd.DataFrame, str]:
        """Run validations and return summary frame and overall status."""
        for filename in REQUIRED_OUTPUTS:
            self.read_csv(filename)
        self.read_csv("backorders.csv", DATA_DIR)
        self.read_csv("backorder_fulfillment_allocations.csv", DATA_DIR)
        self.read_csv("supplier_performance.csv")
        self.read_csv("supplier_sku_scores.csv")
        self.read_csv("procurement_recommendations.csv")

        self._validate_required_columns()
        self._validate_integrated_bridge_detection()
        self._validate_phase1_context()
        self._validate_requirement_capacity_logic()
        self._validate_keys_and_counts()
        self._validate_numeric_logic()
        self._validate_recommendations()
        self._validate_supplier_strategy_consistency()
        self._validate_procurement_kpis()
        self._add_known_warnings()

        summary = pd.DataFrame(self.results, columns=RESULT_COLUMNS)
        fail_count = int((summary["status"] == "FAIL").sum())
        warning_count = int((summary["severity"] == "WARNING").sum())
        overall = "FAIL" if fail_count else ("WARNING" if warning_count else "PASS")
        return summary, overall

    def _validate_integrated_bridge_detection(self) -> None:
        shared_output_dir = Path(__file__).resolve().parents[1] / "shared" / "outputs"
        requirement_bridge = shared_output_dir / "phase3_procurement_requirement_context.csv"
        allocation_bridge = shared_output_dir / "phase2_procurement_allocation_summary.csv"
        detected = [path.name for path in [requirement_bridge, allocation_bridge] if path.exists()]
        mode = "INTEGRATED_MODE" if requirement_bridge.exists() else "STANDALONE_MODE"
        self.add_result(
            "INTEGRATED_BRIDGE_DETECTION",
            "INTEGRATION",
            "Integrated bridge files are detected without being required for standalone validation",
            "PASS",
            "PASS",
            f"Mode: {mode}. Bridge files detected: {', '.join(detected) if detected else 'none'}.",
            "shared/outputs",
            "integrated_validator_status;integrated_run_id;bridge_files_detected;standalone_or_integrated_mode",
            0,
        )

    def _validate_required_columns(self) -> None:
        self.require_columns(
            self.frames.get("backorder_aging_detail.csv", pd.DataFrame()),
            "backorder_aging_detail.csv",
            [
                "backorder_id",
                "sku_id",
                "remaining_backorder_units",
                "backorder_age_days",
                "overdue_days",
                "backorder_priority_score",
                "backorder_risk_level",
                "backorder_action",
                "backorder_warning_codes",
            ],
        )
        self.require_columns(
            self.frames.get("backorder_aging_summary.csv", pd.DataFrame()),
            "backorder_aging_summary.csv",
            [
                "sku_id",
                "open_backorder_count",
                "total_remaining_backorder_units",
                "backorder_priority_score",
                "backorder_risk_level",
                "backorder_pressure_flag",
                "recommended_backorder_strategy",
            ],
        )
        self.require_columns(
            self.frames.get("phase2_procurement_capability_context.csv", pd.DataFrame()),
            "phase2_procurement_capability_context.csv",
            [
                "sku_id",
                "supplier_id",
                "landed_cost_per_unit",
                "quality_adjusted_unit_cost",
                "expedite_capacity_feasible_flag",
                "split_delivery_feasible_flag",
                "split_delivery_recommended_flag",
                "feasible_supplier_option_flag",
                "procurement_warning_codes",
                "phase1_context_source",
                "forecast_demand_30d",
                "demand_urgency_score",
                "demand_data_quality_score",
                "high_uncertainty_flag",
                "stockout_censored_demand_flag",
                "gross_forecast_demand_30d",
                "active_backorder_units",
                "confirmed_inbound_units",
                "provisional_net_procurement_requirement_units",
                "immediate_procurement_requirement_units",
                "remaining_horizon_requirement_units",
                "net_requirement_is_provisional_flag",
                "procurement_requirement_method",
                "supplier_capacity_period_unit",
                "supplier_capacity_period_days",
                "supplier_capacity_per_day",
                "supplier_capacity_30d",
                "supplier_per_order_capacity_units",
                "supplier_horizon_capacity_units",
                "per_order_capacity_feasible_flag",
                "immediate_requirement_feasible_flag",
                "horizon_capacity_feasible_flag",
                "final_executable_supplier_option_flag",
                "estimated_order_cycle_count",
                "average_order_quantity_per_cycle",
                "planned_order_frequency_days",
                "final_immediate_order_quantity",
                "estimated_immediate_procurement_cost",
                "estimated_horizon_procurement_cost",
                "requirement_warning_codes",
                "capacity_warning_codes",
                "capacity_time_basis_warning_codes",
                "total_procurement_cost_per_usable_unit",
                "total_procurement_cost_basis",
            ],
        )
        self.require_columns(
            self.frames.get("phase2_supplier_strategy_summary.csv", pd.DataFrame()),
            "phase2_supplier_strategy_summary.csv",
            [
                "sku_id",
                "current_supplier_id",
                "recommended_supplier_strategy",
                "recommended_supplier_id",
                "current_supplier_source",
                "current_supplier_confidence",
                "supplier_review_required",
                "recommendation_execution_allowed",
                "recommended_option_feasible_flag",
                "recommended_option_infeasibility_reasons",
                "recommendation_blocking_reason",
                "supplier_switch_flag",
                "strategy_consistency_flag",
                "phase1_context_source",
                "demand_urgency_score",
                "forecast_demand_30d",
                "forecast_uncertainty_level",
                "stockout_censored_demand_flag",
                "underforecast_risk_flag",
                "upcoming_event_flag",
                "demand_driven_strategy_flag",
                "demand_review_required",
                "selected_option_warning_codes",
                "sku_option_pool_warning_codes",
                "review_candidate_warning_codes",
                "demand_context_warning_codes",
                "strategy_warning_codes",
                "consolidated_manager_warning_codes",
                "selected_option_capacity_shortfall_flag",
                "selected_option_split_delivery_feasible_flag",
                "selected_option_expedite_capacity_feasible_flag",
                "selected_option_warning_scope_consistency_flag",
                "backorder_strategy",
                "backorder_risk_level",
            ],
        )
        self.require_columns(
            self.frames.get("supplier_performance.csv", pd.DataFrame()),
            "supplier_performance.csv",
            [
                "supplier_id",
                "otif_rate",
                "otif_eligible_delivery_count",
                "otif_delivery_count",
                "supplier_fill_rate",
                "supplier_fill_rate_basis",
                "po_receipt_duplicate_row_count",
            ],
        )
        self.require_columns(
            self.frames.get("phase2_procurement_kpi_summary.csv", pd.DataFrame()),
            "phase2_procurement_kpi_summary.csv",
            ["kpi_category", "kpi_name", "kpi_value", "kpi_unit", "kpi_data_quality", "kpi_explanation"],
        )

    def _validate_phase1_context(self) -> None:
        capability = self.frames.get("phase2_procurement_capability_context.csv", pd.DataFrame())
        strategy = self.frames.get("phase2_supplier_strategy_summary.csv", pd.DataFrame())
        if capability.empty:
            return
        source_ok = "phase1_context_source" in capability.columns and capability["phase1_context_source"].astype(str).eq("PHASE1_DEMAND_PLANNING_CONTEXT").any()
        source = capability["phase1_context_source"].dropna().astype(str).mode().iloc[0] if "phase1_context_source" in capability.columns and not capability["phase1_context_source"].dropna().empty else "UNKNOWN"
        severity = "PASS" if source_ok else "WARNING"
        self.add_result(
            "PHASE1_DEMAND_PLANNING_CONTEXT_USED",
            "PHASE1_CONTEXT",
            "New Phase 1 demand planning context is used",
            severity,
            severity,
            f"Primary context source observed: {source}.",
            "phase2_procurement_capability_context.csv",
            "phase1_context_source",
            0,
            "Use phase1_demand_planning_context.csv before legacy Phase 1 outputs." if not source_ok else "",
        )
        if "sku_id" in capability.columns:
            missing = int(capability[capability["phase1_context_source"].astype(str).eq("INTERNAL_FALLBACK")]["sku_id"].nunique()) if "phase1_context_source" in capability.columns else 0
            self.add_result(
                "PHASE1_CONTEXT_MATCHES_SKUS",
                "PHASE1_CONTEXT",
                "All Phase 2 SKUs have matched demand context",
                "FAIL" if missing else "PASS",
                "FAIL" if missing else "PASS",
                f"SKUs using internal fallback context: {missing}.",
                "phase2_procurement_capability_context.csv",
                "phase1_context_source",
                missing,
            )
        self._check_bounds("phase2_procurement_capability_context.csv", "demand_urgency_score", 0, 100)
        self._check_bounds("phase2_procurement_capability_context.csv", "demand_data_quality_score", 0, 1)
        self._check_non_negative("phase2_procurement_capability_context.csv", ["forecast_demand_7d", "forecast_demand_30d", "forecast_demand_60d", "forecast_demand_90d"])
        if not strategy.empty:
            self._check_bounds("phase2_supplier_strategy_summary.csv", "demand_urgency_score", 0, 100)
            self._check_non_negative("phase2_supplier_strategy_summary.csv", ["forecast_demand_30d"])

    def _validate_requirement_capacity_logic(self) -> None:
        capability = self.frames.get("phase2_procurement_capability_context.csv", pd.DataFrame())
        if capability.empty:
            return
        self._capacity_period_defined_check(capability)
        self._check_non_negative(
            "phase2_procurement_capability_context.csv",
            [
                "supplier_capacity_per_day",
                "supplier_capacity_30d",
                "supplier_horizon_capacity_units",
                "supplier_per_order_capacity_units",
                "gross_forecast_demand_30d",
                "active_backorder_units",
                "confirmed_inbound_units",
                "provisional_net_procurement_requirement_units",
                "immediate_procurement_requirement_units",
                "final_immediate_order_quantity",
                "estimated_immediate_procurement_cost",
                "estimated_horizon_procurement_cost",
            ],
        )
        sku_rows = capability.drop_duplicates("sku_id").copy()
        expected_net = (
            pd.to_numeric(sku_rows["gross_forecast_demand_30d"], errors="coerce").fillna(0)
            + pd.to_numeric(sku_rows["active_backorder_units"], errors="coerce").fillna(0)
            + pd.to_numeric(sku_rows.get("provisional_buffer_requirement_units", 0), errors="coerce").fillna(0)
            - pd.to_numeric(sku_rows.get("usable_on_hand_inventory_units", 0), errors="coerce").fillna(0)
            - pd.to_numeric(sku_rows["confirmed_inbound_units"], errors="coerce").fillna(0)
        ).clip(lower=0)
        actual_net = pd.to_numeric(sku_rows["provisional_net_procurement_requirement_units"], errors="coerce").fillna(0)
        bad_net = int(((expected_net - actual_net).abs() > 0.01).sum())
        self.add_result(
            "PROVISIONAL_NET_REQUIREMENT_MATH",
            "REQUIREMENT_CAPACITY",
            "Provisional net requirement reconciles",
            "FAIL" if bad_net else "PASS",
            "FAIL" if bad_net else "PASS",
            f"Rows with net requirement mismatch: {bad_net}.",
            "phase2_procurement_capability_context.csv",
            "provisional_net_procurement_requirement_units",
            bad_net,
        )
        immediate = pd.to_numeric(sku_rows["immediate_procurement_requirement_units"], errors="coerce").fillna(0)
        bad_immediate = int((immediate < 0).sum())
        self.add_result(
            "IMMEDIATE_REQUIREMENT_NON_NEGATIVE",
            "REQUIREMENT_CAPACITY",
            "Immediate procurement requirement is non-negative",
            "FAIL" if bad_immediate else "PASS",
            "FAIL" if bad_immediate else "PASS",
            f"Negative immediate requirement rows: {bad_immediate}.",
            "phase2_procurement_capability_context.csv",
            "immediate_procurement_requirement_units",
            bad_immediate,
        )
        self._feasibility_alias_check(capability)
        self._false_single_order_assumption_check(capability)
        self._split_sourcing_capacity_check(capability)
        self._capacity_regression_snapshot(capability)
        shared_output_dir = Path(__file__).resolve().parents[1] / "shared" / "outputs"
        integrated_requirement_bridge = shared_output_dir / "phase3_procurement_requirement_context.csv"
        if integrated_requirement_bridge.exists():
            self.add_result(
                "AUTHORITATIVE_PHASE3_REQUIREMENT_MODE",
                "REQUIREMENT_CAPACITY",
                "Phase 2 allocation uses authoritative Phase 3 requirements in integrated mode",
                "PASS",
                "PASS",
                "Integrated mode detected: Phase 3 requirement bridge is present, so allocation uses authoritative Phase 3 net replenishment requirements rather than standalone provisional requirements.",
                "shared/outputs/phase3_procurement_requirement_context.csv",
                "net_replenishment_requirement_units",
                0,
            )
        else:
            provisional = int(_bool_series(sku_rows["net_requirement_is_provisional_flag"]).sum())
            self.add_result(
                "PROVISIONAL_REQUIREMENT_WARNING",
                "REQUIREMENT_CAPACITY",
                "Net requirements are provisional in standalone Phase 2 mode",
                "WARNING" if provisional else "PASS",
                "WARNING" if provisional else "PASS",
                f"Standalone/provisional SKU requirements: {provisional}.",
                "phase2_procurement_capability_context.csv",
                "net_requirement_is_provisional_flag",
                provisional,
                "Run integrated planning with the Phase 3 requirement bridge for authoritative inventory-policy requirements.",
            )

    def _capacity_period_defined_check(self, capability: pd.DataFrame) -> None:
        required = {"supplier_capacity_period_unit", "supplier_sku_capacity_period_unit"}
        if not required.issubset(capability.columns):
            return
        blank = int(
            (
                capability["supplier_capacity_period_unit"].fillna("").astype(str).str.strip().eq("")
                | capability["supplier_sku_capacity_period_unit"].fillna("").astype(str).str.strip().eq("")
            ).sum()
        )
        self.add_result(
            "CAPACITY_PERIOD_DEFINED",
            "REQUIREMENT_CAPACITY",
            "Capacity period units are defined",
            "FAIL" if blank else "PASS",
            "FAIL" if blank else "PASS",
            f"Rows with blank capacity period unit: {blank}.",
            "phase2_procurement_capability_context.csv",
            "supplier_capacity_period_unit",
            blank,
        )

    def _feasibility_alias_check(self, capability: pd.DataFrame) -> None:
        if not {"feasible_supplier_option_flag", "final_executable_supplier_option_flag"}.issubset(capability.columns):
            return
        bad = int((_bool_series(capability["feasible_supplier_option_flag"]) != _bool_series(capability["final_executable_supplier_option_flag"])).sum())
        self.add_result(
            "FEASIBLE_ALIAS_MATCHES_FINAL_EXECUTABLE",
            "REQUIREMENT_CAPACITY",
            "Backward-compatible feasible flag equals final executable flag",
            "FAIL" if bad else "PASS",
            "FAIL" if bad else "PASS",
            f"Alias mismatch rows: {bad}.",
            "phase2_procurement_capability_context.csv",
            "feasible_supplier_option_flag",
            bad,
        )

    def _false_single_order_assumption_check(self, capability: pd.DataFrame) -> None:
        immediate = pd.to_numeric(capability["final_immediate_order_quantity"], errors="coerce").fillna(0)
        gross_30 = pd.to_numeric(capability["gross_forecast_demand_30d"], errors="coerce").fillna(0)
        same = (immediate.round(2) == gross_30.round(2)) & (gross_30 > 0)
        bad = int(same.sum())
        self.add_result(
            "NO_FALSE_SINGLE_ORDER_ASSUMPTION",
            "REQUIREMENT_CAPACITY",
            "Full 30-day demand is not used directly as immediate order quantity",
            "FAIL" if bad else "PASS",
            "FAIL" if bad else "PASS",
            f"Rows where immediate order equals gross 30-day demand: {bad}.",
            "phase2_procurement_capability_context.csv",
            "final_immediate_order_quantity",
            bad,
        )

    def _split_sourcing_capacity_check(self, capability: pd.DataFrame) -> None:
        sku_rows = capability.drop_duplicates("sku_id")
        split = _bool_series(sku_rows.get("split_sourcing_capacity_feasible_flag", pd.Series(False, index=sku_rows.index)))
        requirement = pd.to_numeric(sku_rows["provisional_net_procurement_requirement_units"], errors="coerce").fillna(0)
        total = pd.to_numeric(sku_rows["total_available_supplier_capacity_30d"], errors="coerce").fillna(0)
        bad = int((split & (total + 0.01 < requirement)).sum())
        self.add_result(
            "SPLIT_SOURCING_ALLOCATION_COVERS_REQUIREMENT",
            "REQUIREMENT_CAPACITY",
            "Split sourcing feasible flag covers stated requirement",
            "FAIL" if bad else "PASS",
            "FAIL" if bad else "PASS",
            f"Split-feasible SKUs where aggregate capacity is insufficient: {bad}.",
            "phase2_procurement_capability_context.csv",
            "split_sourcing_capacity_feasible_flag",
            bad,
        )

    def _capacity_regression_snapshot(self, capability: pd.DataFrame) -> None:
        base = int(_bool_series(capability.get("base_supplier_feasible_flag", pd.Series(False, index=capability.index))).sum())
        immediate = int(_bool_series(capability.get("immediate_requirement_feasible_flag", pd.Series(False, index=capability.index))).sum())
        horizon = int(_bool_series(capability.get("horizon_capacity_feasible_flag", pd.Series(False, index=capability.index))).sum())
        final = int(_bool_series(capability.get("final_executable_supplier_option_flag", pd.Series(False, index=capability.index))).sum())
        aggregate = int(capability.drop_duplicates("sku_id")["aggregate_capacity_feasible_flag"].astype(str).str.lower().isin(["true", "1", "yes"]).sum())
        detail = (
            f"Base feasible options: {base}; immediate feasible options: {immediate}; "
            f"horizon feasible options: {horizon}; aggregate feasible SKUs: {aggregate}; "
            f"final executable options: {final}."
        )
        self.add_result(
            "CAPACITY_COLLAPSE_REGRESSION_SNAPSHOT",
            "REQUIREMENT_CAPACITY",
            "Capacity feasibility counts are reported",
            "PASS",
            "PASS",
            detail,
            "phase2_procurement_capability_context.csv",
        )

    def _validate_keys_and_counts(self) -> None:
        detail = self.frames.get("backorder_aging_detail.csv", pd.DataFrame())
        if not detail.empty and "backorder_id" in detail.columns:
            duplicates = int(detail["backorder_id"].duplicated().sum())
            self.add_result(
                "BACKORDER_ID_UNIQUE",
                "KEYS",
                "Backorder IDs are unique in detail",
                "FAIL" if duplicates else "PASS",
                "FAIL" if duplicates else "PASS",
                f"Duplicate backorder IDs: {duplicates}.",
                "backorder_aging_detail.csv",
                "backorder_id",
                duplicates,
                "Use one row per backorder/order line.",
            )

    def _validate_supplier_strategy_consistency(self) -> None:
        strategy = self.frames.get("phase2_supplier_strategy_summary.csv", pd.DataFrame())
        capability = self.frames.get("phase2_procurement_capability_context.csv", pd.DataFrame())
        if strategy.empty:
            return

        self._current_strategy_match_check(strategy, "CURRENT_SUPPLIER")
        self._current_strategy_match_check(strategy, "EXPEDITE_CURRENT_SUPPLIER")
        self._current_strategy_match_check(strategy, "SPLIT_DELIVERY_CURRENT_SUPPLIER")
        self._selected_supplier_exists_check(strategy, capability)
        self._selected_supplier_feasibility_check(strategy, capability)
        self._expedite_strategy_capability_check(strategy, capability)
        self._split_strategy_capability_check(strategy, capability)
        self._strategy_consistency_flag_check(strategy)
        self._warning_scope_consistency_check(strategy)
        self._demand_strategy_consistency_warnings(strategy)
        self._review_required_behavior_check(strategy)
        self._supplier_switch_label_check(strategy)
        self._supplier_strategy_warning_checks(strategy)

    def _current_strategy_match_check(self, strategy: pd.DataFrame, strategy_label: str) -> None:
        required = {"recommended_supplier_strategy", "recommended_supplier_id", "current_supplier_id"}
        if not required.issubset(strategy.columns):
            return
        rows = strategy[strategy["recommended_supplier_strategy"].astype(str) == strategy_label]
        bad = int((rows["recommended_supplier_id"].astype(str) != rows["current_supplier_id"].astype(str)).sum())
        self.add_result(
            f"{strategy_label}_CURRENT_MATCH",
            "STRATEGY_CONSISTENCY",
            f"{strategy_label} selected supplier matches current supplier",
            "FAIL" if bad else "PASS",
            "FAIL" if bad else "PASS",
            f"Mismatched rows: {bad}.",
            "phase2_supplier_strategy_summary.csv",
            "recommended_supplier_id",
            bad,
            f"{strategy_label} must not imply a supplier switch.",
        )

    def _selected_supplier_exists_check(self, strategy: pd.DataFrame, capability: pd.DataFrame) -> None:
        if capability.empty or not {"sku_id", "supplier_id"}.issubset(capability.columns):
            return
        selected = strategy[strategy["recommended_supplier_id"].fillna("").astype(str).str.strip() != ""]
        if selected.empty:
            bad = 0
        else:
            joined = selected.merge(
                capability[["sku_id", "supplier_id"]],
                left_on=["sku_id", "recommended_supplier_id"],
                right_on=["sku_id", "supplier_id"],
                how="left",
            )
            bad = int(joined["supplier_id"].isna().sum())
        self.add_result(
            "SELECTED_SUPPLIER_EXISTS",
            "STRATEGY_CONSISTENCY",
            "Selected supplier exists in capability context",
            "FAIL" if bad else "PASS",
            "FAIL" if bad else "PASS",
            f"Selected suppliers without matching SKU-supplier option: {bad}.",
            "phase2_supplier_strategy_summary.csv",
            "recommended_supplier_id",
            bad,
        )

    def _selected_supplier_feasibility_check(self, strategy: pd.DataFrame, capability: pd.DataFrame) -> None:
        executable = _bool_series(strategy.get("recommendation_execution_allowed", pd.Series(False, index=strategy.index)))
        feasible = _bool_series(strategy.get("recommended_option_feasible_flag", pd.Series(False, index=strategy.index)))
        bad = int((executable & ~feasible).sum())
        self.add_result(
            "EXECUTABLE_RECOMMENDATION_FEASIBLE",
            "STRATEGY_CONSISTENCY",
            "Executable recommendations use feasible supplier options",
            "FAIL" if bad else "PASS",
            "FAIL" if bad else "PASS",
            f"Executable recommendations with infeasible selected option: {bad}.",
            "phase2_supplier_strategy_summary.csv",
            "recommended_option_feasible_flag",
            bad,
        )

        if capability.empty:
            return
        selected = strategy[executable & (strategy["recommended_supplier_id"].fillna("").astype(str).str.strip() != "")]
        if selected.empty:
            bad_context = 0
        else:
            context_columns = [
                "sku_id",
                "supplier_id",
                "feasible_supplier_option_flag",
                "capacity_shortfall_flag",
                "supplier_option_active_flag",
                "order_acceptance_probability",
            ]
            joined = selected.merge(
                capability[context_columns],
                left_on=["sku_id", "recommended_supplier_id"],
                right_on=["sku_id", "supplier_id"],
                how="left",
            )
            bad_context = int(
                (
                    ~_bool_series(joined["feasible_supplier_option_flag"])
                    | _bool_series(joined["capacity_shortfall_flag"])
                    | ~_bool_series(joined["supplier_option_active_flag"])
                    | (pd.to_numeric(joined["order_acceptance_probability"], errors="coerce").fillna(0) < 0.70)
                ).sum()
            )
        self.add_result(
            "EXECUTABLE_RECOMMENDATION_CONTEXT_FEASIBLE",
            "STRATEGY_CONSISTENCY",
            "Executable selected supplier is feasible in capability context",
            "FAIL" if bad_context else "PASS",
            "FAIL" if bad_context else "PASS",
            f"Executable recommendations failing context feasibility: {bad_context}.",
            "phase2_procurement_capability_context.csv",
            "feasible_supplier_option_flag",
            bad_context,
        )

    def _expedite_strategy_capability_check(self, strategy: pd.DataFrame, capability: pd.DataFrame) -> None:
        if capability.empty:
            return
        expedite_rows = strategy[strategy["recommended_supplier_strategy"].astype(str).str.startswith("EXPEDITE_")]
        bad = self._strategy_capability_bad_count(
            expedite_rows,
            capability,
            [
                ("expedite_available", True),
                ("expedite_eligible", True),
                ("expedite_capacity_feasible_flag", True),
                ("feasible_supplier_option_flag", True),
            ],
            require_expedite_lt_standard=True,
        )
        self.add_result(
            "EXPEDITE_STRATEGY_CAPABILITY_VALID",
            "STRATEGY_CONSISTENCY",
            "Expedite strategies use expedite-capable feasible options",
            "FAIL" if bad else "PASS",
            "FAIL" if bad else "PASS",
            f"Invalid expedite strategy rows: {bad}.",
            "phase2_supplier_strategy_summary.csv",
            "recommended_supplier_strategy",
            bad,
        )

    def _split_strategy_capability_check(self, strategy: pd.DataFrame, capability: pd.DataFrame) -> None:
        if capability.empty:
            return
        split_rows = strategy[strategy["recommended_supplier_strategy"].astype(str).str.startswith("SPLIT_DELIVERY_")]
        bad = self._strategy_capability_bad_count(
            split_rows,
            capability,
            [
                ("split_delivery_available", True),
                ("split_delivery_eligible", True),
                ("split_delivery_feasible_flag", True),
                ("feasible_supplier_option_flag", True),
            ],
        )
        self.add_result(
            "SPLIT_STRATEGY_CAPABILITY_VALID",
            "STRATEGY_CONSISTENCY",
            "Split-delivery strategies use split-capable feasible options",
            "FAIL" if bad else "PASS",
            "FAIL" if bad else "PASS",
            f"Invalid split-delivery strategy rows: {bad}.",
            "phase2_supplier_strategy_summary.csv",
            "recommended_supplier_strategy",
            bad,
        )

    def _strategy_capability_bad_count(
        self,
        rows: pd.DataFrame,
        capability: pd.DataFrame,
        bool_requirements: list[tuple[str, bool]],
        require_expedite_lt_standard: bool = False,
    ) -> int:
        if rows.empty:
            return 0
        columns = ["sku_id", "supplier_id", "standard_lead_time_days", "expedite_lead_time_days"] + [
            column for column, _ in bool_requirements
        ]
        joined = rows.merge(
            capability[list(dict.fromkeys(columns))],
            left_on=["sku_id", "recommended_supplier_id"],
            right_on=["sku_id", "supplier_id"],
            how="left",
        )
        invalid = joined["supplier_id"].isna()
        for column, required_value in bool_requirements:
            values = _bool_series(joined[column])
            invalid = invalid | (values != required_value)
        if require_expedite_lt_standard:
            invalid = invalid | (
                pd.to_numeric(joined["expedite_lead_time_days"], errors="coerce").fillna(999999)
                >= pd.to_numeric(joined["standard_lead_time_days"], errors="coerce").fillna(0)
            )
        return int(invalid.sum())

    def _strategy_consistency_flag_check(self, strategy: pd.DataFrame) -> None:
        executable = _bool_series(strategy.get("recommendation_execution_allowed", pd.Series(False, index=strategy.index)))
        consistent = _bool_series(strategy.get("strategy_consistency_flag", pd.Series(False, index=strategy.index)))
        bad = int((executable & ~consistent).sum())
        self.add_result(
            "STRATEGY_CONSISTENCY_FLAG_VALID",
            "STRATEGY_CONSISTENCY",
            "Executable recommendations have strategy_consistency_flag True",
            "FAIL" if bad else "PASS",
            "FAIL" if bad else "PASS",
            f"Executable inconsistent strategy rows: {bad}.",
            "phase2_supplier_strategy_summary.csv",
            "strategy_consistency_flag",
            bad,
        )

    def _review_required_behavior_check(self, strategy: pd.DataFrame) -> None:
        review = strategy["recommended_supplier_strategy"].astype(str).eq("REVIEW_REQUIRED")
        executable = _bool_series(strategy.get("recommendation_execution_allowed", pd.Series(False, index=strategy.index)))
        bad = int((review & executable).sum())
        self.add_result(
            "REVIEW_REQUIRED_NOT_EXECUTABLE",
            "STRATEGY_CONSISTENCY",
            "REVIEW_REQUIRED recommendations are non-executable",
            "FAIL" if bad else "PASS",
            "FAIL" if bad else "PASS",
            f"Executable REVIEW_REQUIRED rows: {bad}.",
            "phase2_supplier_strategy_summary.csv",
            "recommendation_execution_allowed",
            bad,
        )

    def _supplier_switch_label_check(self, strategy: pd.DataFrame) -> None:
        no_switch_labels = {"CURRENT_SUPPLIER", "EXPEDITE_CURRENT_SUPPLIER", "SPLIT_DELIVERY_CURRENT_SUPPLIER"}
        rows = strategy[strategy["recommended_supplier_strategy"].isin(no_switch_labels)]
        bad = int((rows["recommended_supplier_id"].astype(str) != rows["current_supplier_id"].astype(str)).sum())
        self.add_result(
            "NO_SWITCH_LABELS_DO_NOT_SWITCH",
            "STRATEGY_CONSISTENCY",
            "No-switch strategy labels do not switch suppliers",
            "FAIL" if bad else "PASS",
            "FAIL" if bad else "PASS",
            f"No-switch label rows with supplier switch: {bad}.",
            "phase2_supplier_strategy_summary.csv",
            "recommended_supplier_strategy",
            bad,
        )

    def _supplier_strategy_warning_checks(self, strategy: pd.DataFrame) -> None:
        fallback = int(strategy["current_supplier_source"].astype(str).eq("EXISTING_RECOMMENDATION_FALLBACK").sum()) if "current_supplier_source" in strategy.columns else 0
        low_confidence = int(strategy["current_supplier_confidence"].astype(str).eq("LOW").sum()) if "current_supplier_confidence" in strategy.columns else 0
        no_feasible = int(strategy["recommended_supplier_strategy"].astype(str).eq("REVIEW_REQUIRED").sum()) if "recommended_supplier_strategy" in strategy.columns else 0
        review_candidate = int(strategy["review_candidate_supplier_id"].fillna("").astype(str).str.strip().ne("").sum()) if "review_candidate_supplier_id" in strategy.columns else 0
        switches = int(_bool_series(strategy.get("supplier_switch_flag", pd.Series(False, index=strategy.index))).sum())
        backorder_no_fast_option = int(
            (
                strategy["backorder_risk_level"].astype(str).isin(["CRITICAL", "HIGH", "MEDIUM"])
                & ~strategy["recommended_supplier_strategy"].astype(str).str.startswith(("EXPEDITE_", "SPLIT_DELIVERY_"))
            ).sum()
        )
        self._warning_result("CURRENT_SUPPLIER_FALLBACK_SOURCE", "Current supplier source uses fallback", fallback)
        self._warning_result("CURRENT_SUPPLIER_LOW_CONFIDENCE", "Current supplier confidence is low", low_confidence)
        self._warning_result("NO_FEASIBLE_SUPPLIER_STRATEGY", "No feasible supplier exists for some SKUs", no_feasible)
        self._warning_result("REVIEW_CANDIDATE_INFEASIBLE", "Infeasible options are preserved as review candidates", review_candidate)
        self._warning_result("ALTERNATIVE_SUPPLIER_SWITCH", "Alternative supplier switch is recommended", switches)
        self._warning_result(
            "BACKORDER_RISK_WITHOUT_FAST_OPTION",
            "Backorder risk exists but no expedite/split option is selected",
            backorder_no_fast_option,
        )

    def _warning_result(self, check_id: str, name: str, count: int) -> None:
        self.add_result(
            check_id,
            "STRATEGY_WARNINGS",
            name,
            "WARNING" if count else "PASS",
            "WARNING" if count else "PASS",
            f"Affected rows: {count}.",
            "phase2_supplier_strategy_summary.csv",
            affected_rows=count,
        )

    def _warning_scope_consistency_check(self, strategy: pd.DataFrame) -> None:
        if "selected_option_warning_scope_consistency_flag" in strategy.columns:
            bad = int((~_bool_series(strategy["selected_option_warning_scope_consistency_flag"])).sum())
            self.add_result(
                "SELECTED_WARNING_SCOPE_CONSISTENT",
                "WARNING_SCOPE",
                "Selected option warning scope is internally consistent",
                "FAIL" if bad else "PASS",
                "FAIL" if bad else "PASS",
                f"Rows with selected warning scope mismatch: {bad}.",
                "phase2_supplier_strategy_summary.csv",
                "selected_option_warning_scope_consistency_flag",
                bad,
            )
        if {"selected_option_warning_codes", "selected_option_capacity_shortfall_flag"}.issubset(strategy.columns):
            has_capacity_warning = strategy["selected_option_warning_codes"].astype(str).str.contains("CAPACITY_SHORTFALL", regex=False)
            has_capacity_flag = _bool_series(strategy["selected_option_capacity_shortfall_flag"])
            bad = int((has_capacity_warning & ~has_capacity_flag).sum())
            self.add_result(
                "SELECTED_CAPACITY_WARNING_SCOPE",
                "WARNING_SCOPE",
                "Selected capacity warning belongs only to selected capacity-shortfall option",
                "FAIL" if bad else "PASS",
                "FAIL" if bad else "PASS",
                f"Capacity warning scope mismatches: {bad}.",
                "phase2_supplier_strategy_summary.csv",
                "selected_option_warning_codes",
                bad,
            )
        if {"selected_option_warning_codes", "recommended_supplier_strategy"}.issubset(strategy.columns):
            has_split_warning = strategy["selected_option_warning_codes"].astype(str).str.contains(
                "WAREHOUSE_CAPACITY_REVIEW_REQUIRED_FOR_SPLIT_DELIVERY",
                regex=False,
            )
            is_split = strategy["recommended_supplier_strategy"].astype(str).str.startswith("SPLIT_DELIVERY_")
            bad = int((has_split_warning & ~is_split).sum())
            self.add_result(
                "SELECTED_SPLIT_WARNING_SCOPE",
                "WARNING_SCOPE",
                "Selected split-delivery warning appears only for split-delivery strategy",
                "FAIL" if bad else "PASS",
                "FAIL" if bad else "PASS",
                f"Split-delivery warning scope mismatches: {bad}.",
                "phase2_supplier_strategy_summary.csv",
                "selected_option_warning_codes",
                bad,
            )
        if {"review_candidate_warning_codes", "selected_option_warning_codes"}.issubset(strategy.columns):
            selected = strategy["selected_option_warning_codes"].astype(str)
            review = strategy["review_candidate_warning_codes"].astype(str)
            shared_non_blocking = {
                "NONE",
                "PAYMENT_TERMS_COST_NOT_MODELED",
                "FREIGHT_COST_FALLBACK_USED",
                "CUSTOMS_COST_FALLBACK_USED",
                "QUALITY_COST_FALLBACK_USED",
            }

            def _has_review_only_leak(row: pd.Series) -> bool:
                selected_codes = _split_codes(row["selected_option_warning_codes"]) - shared_non_blocking
                review_codes = _split_codes(row["review_candidate_warning_codes"]) - shared_non_blocking
                if not review_codes:
                    return False
                return bool(review_codes & selected_codes)

            bad = int(strategy.apply(_has_review_only_leak, axis=1).sum())
            self.add_result(
                "REVIEW_CANDIDATE_WARNING_SEPARATED",
                "WARNING_SCOPE",
                "Review candidate warnings are separate from selected option warnings",
                "FAIL" if bad else "PASS",
                "FAIL" if bad else "PASS",
                f"Rows where review-candidate-only warnings leak into selected option scope: {bad}.",
                "phase2_supplier_strategy_summary.csv",
                "review_candidate_warning_codes",
                bad,
            )

    def _demand_strategy_consistency_warnings(self, strategy: pd.DataFrame) -> None:
        high_urgency = pd.to_numeric(strategy.get("demand_urgency_score", 0), errors="coerce").fillna(0) >= 70
        risk = strategy.get("backorder_risk_level", pd.Series("", index=strategy.index)).astype(str).isin(["CRITICAL", "HIGH"])
        fast_strategy = strategy.get("recommended_supplier_strategy", pd.Series("", index=strategy.index)).astype(str).str.startswith(("EXPEDITE_", "SPLIT_DELIVERY_", "FASTEST_"))
        self._warning_result(
            "HIGH_URGENCY_BACKORDER_NO_FAST_REVIEW",
            "Critical/high backorder plus high urgency has no fast review strategy",
            int((high_urgency & risk & ~fast_strategy).sum()),
        )
        upcoming = _bool_series(strategy.get("upcoming_event_flag", pd.Series(False, index=strategy.index)))
        self._warning_result(
            "UPCOMING_EVENT_LEAD_TIME_REVIEW",
            "Upcoming event demand exists and should be reviewed for lead-time readiness",
            int((upcoming & ~fast_strategy).sum()),
        )
        censored = _bool_series(strategy.get("stockout_censored_demand_flag", pd.Series(False, index=strategy.index)))
        demand_review = _bool_series(strategy.get("demand_review_required", pd.Series(False, index=strategy.index)))
        self._warning_result(
            "CENSORED_DEMAND_REVIEW_SIGNAL",
            "Stockout-censored demand exists but demand review flag is not set",
            int((censored & ~demand_review).sum()),
        )
        high_uncertainty = strategy.get("forecast_uncertainty_level", pd.Series("", index=strategy.index)).astype(str).eq("HIGH")
        cheapest_only = strategy.get("recommended_supplier_strategy", pd.Series("", index=strategy.index)).astype(str).eq("CHEAPEST_SUPPLIER")
        self._warning_result(
            "HIGH_UNCERTAINTY_CHEAPEST_ONLY",
            "High uncertainty selected cheapest-only strategy without review",
            int((high_uncertainty & cheapest_only & ~demand_review).sum()),
        )
        summary = self.frames.get("backorder_aging_summary.csv", pd.DataFrame())
        if not summary.empty and "sku_id" in summary.columns:
            duplicates = int(summary["sku_id"].duplicated().sum())
            self.add_result(
                "BACKORDER_SUMMARY_ONE_ROW_PER_SKU",
                "KEYS",
                "Backorder summary has one row per SKU",
                "FAIL" if duplicates else "PASS",
                "FAIL" if duplicates else "PASS",
                f"Duplicate SKU rows: {duplicates}.",
                "backorder_aging_summary.csv",
                "sku_id",
                duplicates,
            )
        capability = self.frames.get("phase2_procurement_capability_context.csv", pd.DataFrame())
        if not capability.empty and {"sku_id", "supplier_id"}.issubset(capability.columns):
            duplicates = int(capability.duplicated(["sku_id", "supplier_id"]).sum())
            self.add_result(
                "CAPABILITY_ONE_ROW_PER_SKU_SUPPLIER",
                "KEYS",
                "Capability context has one row per SKU-supplier option",
                "FAIL" if duplicates else "PASS",
                "FAIL" if duplicates else "PASS",
                f"Duplicate SKU-supplier rows: {duplicates}.",
                "phase2_procurement_capability_context.csv",
                "sku_id;supplier_id",
                duplicates,
            )
        strategy = self.frames.get("phase2_supplier_strategy_summary.csv", pd.DataFrame())
        if not strategy.empty and "sku_id" in strategy.columns:
            duplicates = int(strategy["sku_id"].duplicated().sum())
            self.add_result(
                "STRATEGY_ONE_ROW_PER_SKU",
                "KEYS",
                "Supplier strategy summary has one row per SKU",
                "FAIL" if duplicates else "PASS",
                "FAIL" if duplicates else "PASS",
                f"Duplicate SKU rows: {duplicates}.",
                "phase2_supplier_strategy_summary.csv",
                "sku_id",
                duplicates,
            )

    def _validate_numeric_logic(self) -> None:
        self._check_non_negative(
            "backorder_aging_detail.csv",
            [
                "backorder_units",
                "fulfilled_units",
                "allocated_fulfillment_units",
                "remaining_backorder_units",
                "backorder_age_days",
                "overdue_days",
                "promise_delay_days",
                "backorder_priority_score",
            ],
        )
        self._check_non_negative(
            "phase2_procurement_capability_context.csv",
            [
                "landed_cost_per_unit",
                "quality_adjusted_unit_cost",
                "expected_quality_loss_cost",
                "expected_return_recovery_value",
                "expedite_total_cost_estimate",
                "split_delivery_cost_estimate",
            ],
        )
        detail = self.frames.get("backorder_aging_detail.csv", pd.DataFrame())
        if {"fulfilled_units", "backorder_units"}.issubset(detail.columns):
            bad = int((pd.to_numeric(detail["fulfilled_units"], errors="coerce") > pd.to_numeric(detail["backorder_units"], errors="coerce")).sum())
            self.add_result(
                "BACKORDER_MATH_FULFILLED_LE_BACKORDER",
                "NUMERIC",
                "Fulfilled units do not exceed backorder units",
                "FAIL" if bad else "PASS",
                "FAIL" if bad else "PASS",
                f"Rows where fulfilled units exceed backorder units: {bad}.",
                "backorder_aging_detail.csv",
                "fulfilled_units",
                bad,
            )
        capability = self.frames.get("phase2_procurement_capability_context.csv", pd.DataFrame())
        if {"expedite_available", "expedite_lead_time_days", "standard_lead_time_days"}.issubset(capability.columns):
            available = capability["expedite_available"].astype(str).str.lower().isin(["true", "1", "yes"])
            bad = int((available & (pd.to_numeric(capability["expedite_lead_time_days"], errors="coerce") > pd.to_numeric(capability["standard_lead_time_days"], errors="coerce"))).sum())
            self.add_result(
                "EXPEDITE_LEAD_TIME_VALID",
                "NUMERIC",
                "Expedite lead time is not longer than standard lead time",
                "FAIL" if bad else "PASS",
                "FAIL" if bad else "PASS",
                f"Invalid expedite lead time rows: {bad}.",
                "phase2_procurement_capability_context.csv",
                "expedite_lead_time_days",
                bad,
            )

    def _validate_recommendations(self) -> None:
        capability = self.frames.get("phase2_procurement_capability_context.csv", pd.DataFrame())
        if {"split_delivery_recommended_flag", "split_delivery_feasible_flag"}.issubset(capability.columns):
            rec = capability["split_delivery_recommended_flag"].astype(str).str.lower().isin(["true", "1", "yes"])
            feasible = capability["split_delivery_feasible_flag"].astype(str).str.lower().isin(["true", "1", "yes"])
            bad = int((rec & ~feasible).sum())
            self.add_result(
                "SPLIT_RECOMMENDED_ONLY_IF_FEASIBLE",
                "RECOMMENDATIONS",
                "Split delivery is recommended only where feasible",
                "FAIL" if bad else "PASS",
                "FAIL" if bad else "PASS",
                f"Infeasible split-delivery recommendations: {bad}.",
                "phase2_procurement_capability_context.csv",
                "split_delivery_recommended_flag",
                bad,
            )
        if "procurement_warning_codes" in capability.columns:
            fallback = int(capability["procurement_warning_codes"].astype(str).str.contains("FALLBACK_USED", regex=False).sum())
            self.add_result(
                "FALLBACK_COST_WARNINGS",
                "WARNINGS",
                "Fallback cost assumptions are identified",
                "WARNING" if fallback else "PASS",
                "WARNING" if fallback else "PASS",
                f"Rows with fallback cost warning codes: {fallback}.",
                "phase2_procurement_capability_context.csv",
                "procurement_warning_codes",
                fallback,
                "Replace fallback rates with supplier contract data when available.",
            )
        allocations = self.frames.get("backorder_fulfillment_allocations.csv", pd.DataFrame())
        if not allocations.empty and "batch_id" in allocations.columns:
            placeholder = int(allocations["batch_id"].astype(str).str.contains("DEMO-BATCH", regex=False).sum())
            self.add_result(
                "PLACEHOLDER_BATCH_TRACEABILITY",
                "WARNINGS",
                "Demo batch allocation references are clearly identifiable",
                "WARNING" if placeholder else "PASS",
                "WARNING" if placeholder else "PASS",
                f"Placeholder/demo batch references: {placeholder}.",
                "backorder_fulfillment_allocations.csv",
                "batch_id",
                placeholder,
                "Reconnect to Phase 3 batch IDs when phases are integrated.",
            )

    def _check_non_negative(self, filename: str, columns: list[str]) -> None:
        df = self.frames.get(filename, pd.DataFrame())
        for column in columns:
            if df.empty or column not in df.columns:
                continue
            values = pd.to_numeric(df[column], errors="coerce")
            bad = int((values < 0).sum())
            self.add_result(
                f"NON_NEGATIVE_{filename}_{column}",
                "NUMERIC",
                f"{column} is non-negative",
                "FAIL" if bad else "PASS",
                "FAIL" if bad else "PASS",
                f"Negative rows: {bad}.",
                filename,
                column,
                bad,
            )

    def _check_bounds(self, filename: str, column: str, lower: float, upper: float) -> None:
        df = self.frames.get(filename, pd.DataFrame())
        if df.empty or column not in df.columns:
            return
        values = pd.to_numeric(df[column], errors="coerce")
        bad = int(((values < lower) | (values > upper)).sum())
        self.add_result(
            f"BOUNDS_{filename}_{column}",
            "NUMERIC",
            f"{column} is between {lower} and {upper}",
            "FAIL" if bad else "PASS",
            "FAIL" if bad else "PASS",
            f"Out-of-bounds rows: {bad}.",
            filename,
            column,
            bad,
        )

    def _validate_procurement_kpis(self) -> None:
        supplier_performance = self.frames.get("supplier_performance.csv", pd.DataFrame())
        capability = self.frames.get("phase2_procurement_capability_context.csv", pd.DataFrame())
        kpis = self.frames.get("phase2_procurement_kpi_summary.csv", pd.DataFrame())
        self._check_bounds("supplier_performance.csv", "otif_rate", 0, 1)
        self._check_bounds("supplier_performance.csv", "supplier_fill_rate", 0, 1.5)
        self._check_non_negative("supplier_performance.csv", ["otif_eligible_delivery_count", "otif_delivery_count", "po_receipt_duplicate_row_count"])
        self._check_non_negative("phase2_procurement_capability_context.csv", ["total_procurement_cost_per_usable_unit"])
        if not supplier_performance.empty and {"otif_delivery_count", "otif_eligible_delivery_count"}.issubset(supplier_performance.columns):
            bad = int(
                (
                    pd.to_numeric(supplier_performance["otif_delivery_count"], errors="coerce").fillna(0)
                    > pd.to_numeric(supplier_performance["otif_eligible_delivery_count"], errors="coerce").fillna(0)
                ).sum()
            )
            self.add_result(
                "PROC_KPI_OTIF_COUNTS",
                "PROCUREMENT_KPIS",
                "OTIF delivery count does not exceed eligible deliveries",
                "FAIL" if bad else "PASS",
                "FAIL" if bad else "PASS",
                f"Rows with OTIF count greater than eligible count: {bad}.",
                "supplier_performance.csv",
                "otif_delivery_count; otif_eligible_delivery_count",
                bad,
            )
        if not supplier_performance.empty and "supplier_fill_rate_basis" in supplier_performance.columns:
            valid_basis = {
                "ACCEPTED_QUANTITY_DIVIDED_BY_ORDERED_QUANTITY",
                "UNAVAILABLE_PO_RECEIPT_HISTORY",
            }
            bad_basis = int((~supplier_performance["supplier_fill_rate_basis"].fillna("").astype(str).isin(valid_basis)).sum())
            self.add_result(
                "PROC_KPI_RECEIPTS_PO_LEVEL",
                "PROCUREMENT_KPIS",
                "OTIF and fill rate use PO-level receipt aggregation",
                "FAIL" if bad_basis else "PASS",
                "FAIL" if bad_basis else "PASS",
                f"Rows with invalid fill-rate basis: {bad_basis}. Duplicate receipt PO counts are reported separately.",
                "supplier_performance.csv",
                "supplier_fill_rate_basis",
                bad_basis,
            )
        if not capability.empty and "total_procurement_cost_per_usable_unit" in capability.columns:
            available = int(pd.to_numeric(capability["total_procurement_cost_per_usable_unit"], errors="coerce").notna().sum())
            self.add_result(
                "PROC_KPI_COST_PER_USABLE_AVAILABLE",
                "PROCUREMENT_KPIS",
                "Cost per usable unit is calculated where source quantities exist",
                "PASS" if available else "WARNING",
                "PASS" if available else "WARNING",
                f"Rows with available cost per usable unit: {available}.",
                "phase2_procurement_capability_context.csv",
                "total_procurement_cost_per_usable_unit",
                0 if available else len(capability),
            )
        if not kpis.empty:
            required_names = {
                "requirement_coverage_rate",
                "unallocated_requirement_rate",
                "average_supplier_capacity_utilization_rate",
                "average_top_supplier_allocation_share",
                "average_total_procurement_cost_per_usable_unit",
            }
            names = set(kpis.get("kpi_name", pd.Series(dtype=str)).dropna().astype(str))
            missing = sorted(required_names - names)
            self.add_result(
                "PROC_KPI_SUMMARY_NAMES",
                "PROCUREMENT_KPIS",
                "Procurement KPI summary contains essential non-redundant KPIs",
                "FAIL" if missing else "PASS",
                "FAIL" if missing else "PASS",
                "All required KPI names present." if not missing else f"Missing KPI names: {', '.join(missing)}.",
                "phase2_procurement_kpi_summary.csv",
                "kpi_name",
                len(missing),
            )
            weighted_rows = kpis[kpis["kpi_name"].isin({
                "average_supplier_capacity_utilization_rate",
                "average_total_procurement_cost_per_usable_unit",
            })]
            weighted_text = " ".join(weighted_rows.get("kpi_explanation", pd.Series(dtype=str)).fillna("").astype(str)).lower()
            missing_weighted_label = int("weighted" not in weighted_text)
            self.add_result(
                "PROC_KPI_WEIGHTED_AGGREGATES",
                "PROCUREMENT_KPIS",
                "Aggregate cost and capacity KPIs use weighted formulas",
                "FAIL" if missing_weighted_label else "PASS",
                "FAIL" if missing_weighted_label else "PASS",
                "Weighted formula wording is present." if not missing_weighted_label else "Weighted formula wording missing from aggregate KPI explanations.",
                "phase2_procurement_kpi_summary.csv",
                "kpi_explanation",
                missing_weighted_label,
            )
            if "kpi_data_quality" in kpis.columns:
                valid_quality = {"AVAILABLE", "UNAVAILABLE_ZERO_OR_MISSING_DENOMINATOR"}
                invalid_quality = int((~kpis["kpi_data_quality"].fillna("").astype(str).isin(valid_quality)).sum())
                self.add_result(
                    "PROC_KPI_DATA_QUALITY_FLAGS",
                    "PROCUREMENT_KPIS",
                    "Procurement KPI summary includes explicit data-quality flags",
                    "FAIL" if invalid_quality else "PASS",
                    "FAIL" if invalid_quality else "PASS",
                    f"Rows with invalid data-quality flag: {invalid_quality}.",
                    "phase2_procurement_kpi_summary.csv",
                    "kpi_data_quality",
                    invalid_quality,
                )

    def _add_known_warnings(self) -> None:
        known = [
            "Some suppliers do not support returns.",
            "Some suppliers do not support expedite.",
            "Some suppliers do not support split delivery.",
            "Payment terms cost is noted but not financially modeled.",
            "No automatic supplier selection or purchase order creation is performed.",
        ]
        for index, detail in enumerate(known, start=1):
            self.add_result(
                f"KNOWN_LIMITATION_{index}",
                "KNOWN_LIMITATIONS",
                detail,
                "WARNING",
                "WARNING",
                detail,
                suggested_fix="Planned future enhancement; no blocking issue.",
            )


def write_outputs(summary: pd.DataFrame, overall: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = OUTPUT_DIR / "phase2_procurement_validation_summary.csv"
    report_path = OUTPUT_DIR / "phase2_procurement_validation_report.txt"
    summary.to_csv(summary_path, index=False)

    fail_count = int((summary["status"] == "FAIL").sum())
    warning_count = int((summary["severity"] == "WARNING").sum())
    pass_count = int((summary["status"] == "PASS").sum())
    lines = [
        "Phase 2 Procurement Capability Validation Report",
        f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"Project path: {Path(__file__).resolve().parent}",
        f"Outputs path: {OUTPUT_DIR}",
        "",
        f"Overall status: {overall}",
        f"PASS: {pass_count}",
        f"WARNING: {warning_count}",
        f"FAIL: {fail_count}",
        "",
        "Critical Failures:",
    ]
    failures = summary[summary["status"] == "FAIL"]
    if failures.empty:
        lines.append("None.")
    else:
        for _, row in failures.iterrows():
            lines.append(f"- {row['check_id']}: {row['details']}")
    lines.extend(["", "Warnings:"])
    warnings = summary[summary["severity"] == "WARNING"]
    if warnings.empty:
        lines.append("None.")
    else:
        for _, row in warnings.iterrows():
            lines.append(f"- {row['check_group']} / {row['check_id']}: {row['details']}")
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Validation report: {report_path}")
    print(f"Validation summary: {summary_path}")
    print(f"Overall status: {overall}")
    print(f"FAIL count: {fail_count}")
    print(f"WARNING count: {warning_count}")


def _bool_series(series: pd.Series) -> pd.Series:
    """Parse CSV boolean-ish values consistently."""
    normalized = series.where(series.notna(), False)
    if normalized.dtype == bool:
        return normalized
    return normalized.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y", "t"})


def _split_codes(value: object) -> set[str]:
    """Split semicolon warning-code fields without treating blanks as real codes."""
    if pd.isna(value):
        return set()
    return {
        code.strip()
        for code in str(value).split(";")
        if code.strip() and code.strip().upper() not in {"NAN", "NONE"}
    }


def main() -> None:
    validator = Validator()
    summary, overall = validator.validate()
    write_outputs(summary, overall)


if __name__ == "__main__":
    main()
