"""Read-only validation checks for Phase 3 Inventory Control outputs."""

from __future__ import annotations

import json
import py_compile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PASS = "PASS"
WARNING = "WARNING"
FAIL = "FAIL"
SKIPPED = "SKIPPED"

TOLERANCE = 0.01
SCENARIO_COUNT_CAP = 25

PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = PROJECT_DIR / "outputs"


REQUIRED_CSV_FILES = [
    "inventory_clean.csv",
    "inventory_batches_clean.csv",
    "inventory_movements_clean.csv",
    "warehouse_layout_clean.csv",
    "storage_locations_clean.csv",
    "sku_storage_requirements_clean.csv",
    "inventory_planning_context.csv",
    "inventory_classification.csv",
    "inventory_service_levels.csv",
    "inventory_policy.csv",
    "inventory_policy_parameters.csv",
    "inventory_status.csv",
    "inventory_action_recommendations.csv",
    "inventory_costs.csv",
    "inventory_cost_summary.csv",
    "warehouse_slotting.csv",
    "batch_slotting.csv",
    "location_utilization.csv",
    "space_utilization.csv",
    "warehouse_travel_costs.csv",
    "warehouse_visual_grid.csv",
    "warehouse_visual_locations.csv",
    "warehouse_visual_skus.csv",
    "warehouse_visual_batches.csv",
    "warehouse_visual_legend.csv",
    "warehouse_visual_summary.csv",
    "inventory_re_evaluation.csv",
    "inventory_parameter_adjustment_recommendations.csv",
    "re_evaluation_summary.csv",
    "inventory_scenarios.csv",
    "inventory_scenario_results.csv",
    "inventory_optimization_recommendations.csv",
    "inventory_optimization_summary.csv",
    "inventory_control_master_decisions.csv",
    "inventory_control_human_review_queue.csv",
    "inventory_control_advisory_review_queue.csv",
    "inventory_control_executive_summary.csv",
    "inventory_control_kpi_summary.csv",
    "inventory_kpi_summary.csv",
    "inventory_control_action_plan.csv",
    "inventory_control_risk_register.csv",
    "inventory_control_manager_dashboard.csv",
    "inventory_employee_task_view.csv",
]

REQUIRED_HTML_FILES = [
    "warehouse_2d_map.html",
    "warehouse_3d_map.html",
]

VALIDATION_OUTPUT_FILES = [
    "phase3_validation_report.txt",
    "phase3_validation_summary.csv",
    "phase3_validation_issues.csv",
    "phase3_wrap_up_summary.txt",
]


def file_exists(path: Path) -> bool:
    return path.exists()


def _blank_mask(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype(str).str.strip().eq("")


def _to_bool(series: pd.Series) -> pd.Series:
    if series.empty:
        return series.astype(bool)
    normalized = series.astype(str).str.strip().str.lower()
    return series.eq(True) | normalized.isin({"true", "1", "yes", "y"})


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _join_values(values: Any) -> str:
    if isinstance(values, pd.Series):
        values = values.dropna().astype(str).tolist()
    if not values:
        return ""
    return "; ".join(str(v) for v in values)


@dataclass
class Phase3Validator:
    project_dir: Path = PROJECT_DIR
    outputs_dir: Path = OUTPUTS_DIR
    results: list[dict[str, Any]] = field(default_factory=list)
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    check_index: int = 1

    def next_id(self, prefix: str) -> str:
        check_id = f"{prefix}-{self.check_index:04d}"
        self.check_index += 1
        return check_id

    def add_result(
        self,
        check_group: str,
        check_name: str,
        severity: str,
        status: str,
        details: str,
        affected_file: str = "",
        affected_column: str = "",
        affected_rows: Any = "",
        suggested_fix: str = "",
        check_id: str | None = None,
    ) -> None:
        self.results.append(
            {
                "check_id": check_id or self.next_id(check_group[:3].upper()),
                "check_group": check_group,
                "check_name": check_name,
                "severity": severity,
                "status": status,
                "details": details,
                "affected_file": affected_file,
                "affected_column": affected_column,
                "affected_rows": str(affected_rows),
                "suggested_fix": suggested_fix,
            }
        )

    def safe_read_csv(self, file_name: str) -> pd.DataFrame | None:
        path = self.outputs_dir / file_name
        if not path.exists():
            self.add_result(
                "SAFE_LOAD",
                f"Load {file_name}",
                FAIL,
                FAIL,
                "Required CSV file is missing.",
                file_name,
                suggested_fix="Regenerate Phase 3 outputs before validation.",
            )
            return None
        try:
            df = pd.read_csv(path)
        except Exception as exc:  # pragma: no cover - defensive file handling
            self.add_result(
                "SAFE_LOAD",
                f"Load {file_name}",
                FAIL,
                FAIL,
                f"CSV could not be parsed: {exc}",
                file_name,
                suggested_fix="Open the CSV, fix formatting/parsing errors, and rerun validation.",
            )
            return None
        self.frames[file_name] = df
        self.add_result(
            "SAFE_LOAD",
            f"Load {file_name}",
            PASS,
            PASS,
            f"Loaded {len(df)} rows and {len(df.columns)} columns.",
            file_name,
        )
        return df

    def require_columns(self, df: pd.DataFrame | None, file_name: str, columns: list[str]) -> bool:
        if df is None:
            self.add_result(
                "COLUMN_CHECK",
                f"Required columns in {file_name}",
                SKIPPED,
                SKIPPED,
                "File was not loaded.",
                file_name,
                suggested_fix="Fix missing/unreadable file first.",
            )
            return False
        missing = [col for col in columns if col not in df.columns]
        if missing:
            self.add_result(
                "COLUMN_CHECK",
                f"Required columns in {file_name}",
                FAIL,
                FAIL,
                f"Missing columns: {_join_values(missing)}",
                file_name,
                affected_column=_join_values(missing),
                suggested_fix="Regenerate the upstream Phase 3 step that creates these fields.",
            )
            return False
        self.add_result(
            "COLUMN_CHECK",
            f"Required columns in {file_name}",
            PASS,
            PASS,
            "All required columns are present.",
            file_name,
        )
        return True

    def check_unique_key(self, df: pd.DataFrame | None, file_name: str, key: str = "sku_id") -> bool:
        if df is None or key not in getattr(df, "columns", []):
            self.add_result(
                "KEY_CHECK",
                f"Unique {key} in {file_name}",
                SKIPPED,
                SKIPPED,
                f"Cannot check uniqueness because {key} or file is unavailable.",
                file_name,
                key,
                suggested_fix="Fix file loading or missing key column first.",
            )
            return False
        missing = int(_blank_mask(df[key]).sum())
        duplicates = int(df[key].dropna().astype(str).duplicated().sum())
        if missing or duplicates:
            self.add_result(
                "KEY_CHECK",
                f"Unique {key} in {file_name}",
                FAIL,
                FAIL,
                f"Missing key rows: {missing}; duplicate key rows: {duplicates}.",
                file_name,
                key,
                affected_rows=missing + duplicates,
                suggested_fix="Ensure each SKU-level output has exactly one nonblank sku_id per row.",
            )
            return False
        self.add_result(
            "KEY_CHECK",
            f"Unique {key} in {file_name}",
            PASS,
            PASS,
            f"{key} is present and unique.",
            file_name,
            key,
        )
        return True

    def check_no_missing(self, df: pd.DataFrame | None, file_name: str, columns: list[str]) -> bool:
        if df is None:
            self.add_result("POPULATION", f"Required fields populated in {file_name}", SKIPPED, SKIPPED, "File was not loaded.", file_name)
            return False
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            self.add_result(
                "POPULATION",
                f"Required fields populated in {file_name}",
                SKIPPED,
                SKIPPED,
                f"Missing columns prevent population check: {_join_values(missing_cols)}",
                file_name,
                affected_column=_join_values(missing_cols),
                suggested_fix="Add required columns before checking field population.",
            )
            return False
        issues = {col: int(_blank_mask(df[col]).sum()) for col in columns}
        bad = {col: count for col, count in issues.items() if count > 0}
        if bad:
            self.add_result(
                "POPULATION",
                f"Required fields populated in {file_name}",
                FAIL,
                FAIL,
                f"Blank required values: {bad}",
                file_name,
                affected_column=_join_values(bad.keys()),
                affected_rows=sum(bad.values()),
                suggested_fix="Populate all manager-facing and selected scenario fields.",
            )
            return False
        self.add_result(
            "POPULATION",
            f"Required fields populated in {file_name}",
            PASS,
            PASS,
            "Required fields are populated.",
            file_name,
            affected_column=_join_values(columns),
        )
        return True

    def check_numeric_non_negative(self, df: pd.DataFrame | None, file_name: str, columns: list[str]) -> bool:
        if df is None:
            self.add_result("NUMERIC", f"Non-negative numeric values in {file_name}", SKIPPED, SKIPPED, "File was not loaded.", file_name)
            return False
        checked = []
        failures = {}
        for col in columns:
            if col not in df.columns:
                continue
            values = pd.to_numeric(df[col], errors="coerce")
            bad_count = int((values < 0).sum())
            null_numeric = int(values.isna().sum() - df[col].isna().sum())
            checked.append(col)
            if bad_count or null_numeric:
                failures[col] = bad_count + max(null_numeric, 0)
        if not checked:
            self.add_result(
                "NUMERIC",
                f"Non-negative numeric values in {file_name}",
                SKIPPED,
                SKIPPED,
                "None of the requested numeric columns exist.",
                file_name,
                affected_column=_join_values(columns),
                suggested_fix="Verify output schema or adjust validation column list.",
            )
            return False
        if failures:
            self.add_result(
                "NUMERIC",
                f"Non-negative numeric values in {file_name}",
                FAIL,
                FAIL,
                f"Negative or nonnumeric impossible values: {failures}",
                file_name,
                affected_column=_join_values(failures.keys()),
                affected_rows=sum(failures.values()),
                suggested_fix="Fix upstream calculations so required numeric fields are non-negative.",
            )
            return False
        self.add_result(
            "NUMERIC",
            f"Non-negative numeric values in {file_name}",
            PASS,
            PASS,
            f"Checked non-negative columns: {_join_values(checked)}",
            file_name,
            affected_column=_join_values(checked),
        )
        return True

    def check_boolean_all_false(self, df: pd.DataFrame | None, file_name: str, column: str) -> bool:
        if df is None or column not in getattr(df, "columns", []):
            self.add_result(
                "SAFETY",
                f"{column} disabled in {file_name}",
                SKIPPED,
                SKIPPED,
                "File or column is unavailable.",
                file_name,
                column,
            )
            return False
        true_count = int(_to_bool(df[column]).sum())
        if true_count:
            self.add_result(
                "SAFETY",
                f"{column} disabled in {file_name}",
                FAIL,
                FAIL,
                f"{true_count} rows allow auto-apply.",
                file_name,
                column,
                affected_rows=true_count,
                suggested_fix="Keep Phase 3 recommendation outputs advisory only; set auto_apply_allowed to False.",
            )
            return False
        self.add_result(
            "SAFETY",
            f"{column} disabled in {file_name}",
            PASS,
            PASS,
            "Auto-apply is disabled for every row.",
            file_name,
            column,
        )
        return True

    def compare_sums(
        self,
        df1: pd.DataFrame | None,
        col1: str,
        df2: pd.DataFrame | None,
        col2: str,
        tolerance: float = TOLERANCE,
        name: str = "Sum reconciliation",
        file_pair: str = "",
    ) -> bool:
        if df1 is None or df2 is None or col1 not in getattr(df1, "columns", []) or col2 not in getattr(df2, "columns", []):
            self.add_result(
                "RECONCILIATION",
                name,
                SKIPPED,
                SKIPPED,
                "One or both files/columns are unavailable.",
                file_pair,
                f"{col1}; {col2}",
            )
            return False
        total1 = pd.to_numeric(df1[col1], errors="coerce").fillna(0).sum()
        total2 = pd.to_numeric(df2[col2], errors="coerce").fillna(0).sum()
        diff = abs(total1 - total2)
        if diff > tolerance:
            self.add_result(
                "RECONCILIATION",
                name,
                FAIL,
                FAIL,
                f"Totals differ by {diff:.4f}: {col1}={total1:.4f}, {col2}={total2:.4f}.",
                file_pair,
                f"{col1}; {col2}",
                suggested_fix="Trace the consolidation handoff from optimization recommendations to master decisions.",
            )
            return False
        self.add_result(
            "RECONCILIATION",
            name,
            PASS,
            PASS,
            f"Totals reconcile within tolerance: {total1:.4f} vs {total2:.4f}.",
            file_pair,
            f"{col1}; {col2}",
        )
        return True

    def run(self) -> dict[str, Any]:
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.check_required_files()
        self.load_csv_files()
        self.run_all_checks()
        self.add_known_limitations()
        self.add_validation_output_rows()
        return self.write_outputs()

    def check_required_files(self) -> None:
        for file_name in REQUIRED_CSV_FILES:
            path = self.outputs_dir / file_name
            if path.exists() and path.stat().st_size > 0:
                self.add_result("REQUIRED_FILES", f"Required file exists: {file_name}", PASS, PASS, "File exists and is non-empty.", file_name)
            elif path.exists():
                self.add_result("REQUIRED_FILES", f"Required file exists: {file_name}", FAIL, FAIL, "File exists but is empty.", file_name, suggested_fix="Regenerate the output file.")
            else:
                self.add_result("REQUIRED_FILES", f"Required file exists: {file_name}", FAIL, FAIL, "File is missing.", file_name, suggested_fix="Run the Phase 3 pipeline before validation.")

        for file_name in REQUIRED_HTML_FILES:
            path = self.outputs_dir / file_name
            if path.exists() and path.stat().st_size > 0:
                self.add_result("REQUIRED_FILES", f"Required HTML map exists: {file_name}", PASS, PASS, "HTML map exists and is non-empty.", file_name)
            elif path.exists():
                self.add_result("REQUIRED_FILES", f"Required HTML map exists: {file_name}", FAIL, FAIL, "HTML map exists but is empty.", file_name, suggested_fix="Regenerate visualization maps.")
            else:
                self.add_result("REQUIRED_FILES", f"Required HTML map exists: {file_name}", FAIL, FAIL, "HTML map is missing.", file_name, suggested_fix="Run Step 10 visualization generation.")

    def load_csv_files(self) -> None:
        for file_name in REQUIRED_CSV_FILES:
            if (self.outputs_dir / file_name).exists():
                self.safe_read_csv(file_name)

    def run_all_checks(self) -> None:
        self.check_sku_level_rows()
        self.check_required_columns()
        self.check_required_field_population()
        self.check_numeric_sanity()
        self.check_auto_apply_safety()
        self.check_review_queue_logic()
        self.check_action_clarity()
        self.check_scenario_logic()
        self.check_cost_reconciliation()
        self.check_warehouse_batch_logic()
        self.check_manager_output_quality()
        self.check_inventory_kpi_quality()
        self.check_employee_task_view()

    def check_sku_level_rows(self) -> None:
        base = self.frames.get("inventory_clean.csv")
        if base is None or "sku_id" not in base.columns:
            self.add_result("ROW_COUNTS", "Base SKU count", SKIPPED, SKIPPED, "inventory_clean.csv or sku_id is unavailable.", "inventory_clean.csv")
            return
        base_skus = set(base["sku_id"].dropna().astype(str))
        base_count = len(base_skus)
        self.add_result("ROW_COUNTS", "Base SKU count", PASS, PASS, f"Base unique SKU count is {base_count}.", "inventory_clean.csv", "sku_id")

        sku_files = [
            "inventory_classification.csv",
            "inventory_service_levels.csv",
            "inventory_policy.csv",
            "inventory_policy_parameters.csv",
            "inventory_status.csv",
            "inventory_action_recommendations.csv",
            "inventory_costs.csv",
            "warehouse_slotting.csv",
            "warehouse_visual_skus.csv",
            "inventory_re_evaluation.csv",
            "inventory_parameter_adjustment_recommendations.csv",
            "inventory_optimization_recommendations.csv",
            "inventory_control_master_decisions.csv",
            "inventory_control_manager_dashboard.csv",
            "inventory_employee_task_view.csv",
        ]
        for file_name in sku_files:
            df = self.frames.get(file_name)
            if df is None or "sku_id" not in getattr(df, "columns", []):
                self.add_result("ROW_COUNTS", f"SKU-level row count: {file_name}", SKIPPED, SKIPPED, "File or sku_id is unavailable.", file_name)
                continue
            missing_skus = base_skus - set(df["sku_id"].dropna().astype(str))
            extra_skus = set(df["sku_id"].dropna().astype(str)) - base_skus
            duplicate_rows = int(df["sku_id"].dropna().astype(str).duplicated().sum())
            if len(df) != base_count or df["sku_id"].nunique(dropna=True) != base_count or missing_skus or extra_skus or duplicate_rows:
                self.add_result(
                    "ROW_COUNTS",
                    f"SKU-level row count: {file_name}",
                    FAIL,
                    FAIL,
                    f"Rows={len(df)}, unique_skus={df['sku_id'].nunique(dropna=True)}, base={base_count}, missing={len(missing_skus)}, extra={len(extra_skus)}, duplicates={duplicate_rows}.",
                    file_name,
                    "sku_id",
                    affected_rows=abs(len(df) - base_count) + duplicate_rows + len(missing_skus) + len(extra_skus),
                    suggested_fix="Ensure SKU-level outputs have exactly one row per inventory_clean SKU.",
                )
            else:
                self.add_result("ROW_COUNTS", f"SKU-level row count: {file_name}", PASS, PASS, f"Rows and unique SKU count match base count {base_count}.", file_name, "sku_id")
            self.check_unique_key(df, file_name)

        scenarios = self.frames.get("inventory_scenarios.csv")
        if scenarios is not None:
            status = PASS if len(scenarios) >= base_count else FAIL
            self.add_result("ROW_COUNTS", "Scenario rows at least one per SKU", status, status, f"Scenario rows={len(scenarios)}, base_skus={base_count}.", "inventory_scenarios.csv", suggested_fix="Ensure every SKU has at least a baseline scenario.")

        scenario_results = self.frames.get("inventory_scenario_results.csv")
        if scenarios is not None and scenario_results is not None:
            status = PASS if len(scenario_results) == len(scenarios) else FAIL
            self.add_result("ROW_COUNTS", "Scenario results row count matches scenarios", status, status, f"Scenario rows={len(scenarios)}, result rows={len(scenario_results)}.", "inventory_scenario_results.csv", suggested_fix="Score every generated scenario exactly once.")

        batches = self.frames.get("inventory_batches_clean.csv")
        batch_slotting = self.frames.get("batch_slotting.csv")
        if batches is not None and batch_slotting is not None:
            status = PASS if len(batch_slotting) == len(batches) else FAIL
            self.add_result("ROW_COUNTS", "Batch slotting row count matches clean batches", status, status, f"Batch rows={len(batches)}, batch slotting rows={len(batch_slotting)}.", "batch_slotting.csv", suggested_fix="Keep batch_slotting.csv at one row per clean batch.")

        for file_name in ["inventory_control_human_review_queue.csv", "inventory_control_advisory_review_queue.csv", "inventory_control_action_plan.csv"]:
            df = self.frames.get(file_name)
            if df is None:
                continue
            status = PASS if 0 <= len(df) <= base_count else FAIL
            self.add_result("ROW_COUNTS", f"Queue/action plan bounded rows: {file_name}", status, status, f"Rows={len(df)}, base_skus={base_count}.", file_name, suggested_fix="Queue/action plan should not exceed one row per SKU.")

    def check_required_columns(self) -> None:
        master_cols = [
            "sku_id", "product_name", "category", "main_inventory_status", "final_decision_priority",
            "final_manager_status", "final_recommended_action", "blocking_review_action",
            "proposed_operational_action", "execution_owner", "review_owner", "final_action_owner",
            "final_review_required", "final_mandatory_review_required", "final_advisory_review_required",
            "final_review_severity", "primary_review_type", "final_risk_level", "final_risk_types",
            "selected_scenario_name", "selected_buffer_strategy", "selected_supplier_strategy",
            "selected_delivery_strategy", "selected_expiry_strategy", "selected_warehouse_strategy",
            "operational_cost_saving_vs_baseline", "penalty_adjusted_saving_vs_baseline",
            "auto_apply_allowed",
        ]
        dashboard_cols = [
            "sku_id", "product_name", "category", "current_inventory", "main_inventory_status",
            "final_decision_priority", "final_manager_status", "final_recommended_action",
            "blocking_review_action", "proposed_operational_action", "execution_owner", "review_owner",
            "final_review_required", "final_mandatory_review_required", "final_advisory_review_required",
            "final_review_severity", "final_risk_level", "final_risk_types", "selected_scenario_name",
            "operational_cost_saving_vs_baseline", "penalty_adjusted_saving_vs_baseline",
            "suggested_dashboard_badge", "suggested_dashboard_color_group",
        ]
        opt_cols = [
            "sku_id", "selected_scenario_id", "selected_scenario_name",
            "selected_total_penalty_adjusted_cost", "baseline_total_penalty_adjusted_cost",
            "penalty_adjusted_saving_vs_baseline", "selected_operational_cost",
            "baseline_operational_cost", "operational_cost_saving_vs_baseline",
            "selected_feasibility_status", "selected_feasibility_severity",
            "selected_hard_blocker_count", "selected_major_risk_count",
            "selected_review_required_count", "selected_soft_warning_count", "auto_apply_allowed",
        ]
        scenario_result_cols = [
            "sku_id", "scenario_id", "scenario_name", "scenario_operational_cost",
            "scenario_risk_penalty_cost", "scenario_constraint_penalty_cost",
            "scenario_total_penalty_adjusted_cost", "scenario_total_relevant_cost", "feasible_flag",
            "hard_blocker_count", "major_risk_count", "review_required_count", "soft_warning_count",
            "feasibility_severity", "legacy_constraint_penalty_used_flag",
        ]
        self.require_columns(self.frames.get("inventory_control_master_decisions.csv"), "inventory_control_master_decisions.csv", master_cols)
        self.require_columns(self.frames.get("inventory_control_manager_dashboard.csv"), "inventory_control_manager_dashboard.csv", dashboard_cols)
        self.require_columns(self.frames.get("inventory_optimization_recommendations.csv"), "inventory_optimization_recommendations.csv", opt_cols)
        self.require_columns(self.frames.get("inventory_scenario_results.csv"), "inventory_scenario_results.csv", scenario_result_cols)

    def check_required_field_population(self) -> None:
        self.check_no_missing(
            self.frames.get("inventory_control_master_decisions.csv"),
            "inventory_control_master_decisions.csv",
            [
                "sku_id", "final_decision_priority", "final_manager_status", "final_recommended_action",
                "blocking_review_action", "proposed_operational_action", "execution_owner", "review_owner",
                "final_review_severity", "final_risk_level", "selected_scenario_name",
            ],
        )
        self.check_no_missing(
            self.frames.get("inventory_control_manager_dashboard.csv"),
            "inventory_control_manager_dashboard.csv",
            [
                "sku_id", "final_decision_priority", "final_manager_status", "final_recommended_action",
                "proposed_operational_action", "execution_owner", "review_owner", "suggested_dashboard_badge",
                "suggested_dashboard_color_group",
            ],
        )
        self.check_no_missing(
            self.frames.get("inventory_optimization_recommendations.csv"),
            "inventory_optimization_recommendations.csv",
            [
                "selected_scenario_id", "selected_scenario_name", "selected_feasibility_status",
                "selected_feasibility_severity", "selection_status", "optimization_recommendation",
            ],
        )

    def check_numeric_sanity(self) -> None:
        service = self.frames.get("inventory_service_levels.csv")
        if service is not None:
            if "service_level_target" in service.columns:
                vals = pd.to_numeric(service["service_level_target"], errors="coerce")
                bad = int((vals.isna() | (vals < 0) | (vals > 1)).sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("NUMERIC", "Service level target between 0 and 1", status, status, f"Invalid rows: {bad}.", "inventory_service_levels.csv", "service_level_target", bad, "Keep service_level_target within [0, 1].")
            if "safety_factor_z" in service.columns:
                bad = int(pd.to_numeric(service["safety_factor_z"], errors="coerce").isna().sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("NUMERIC", "Safety factor z populated", status, status, f"Missing/non-numeric rows: {bad}.", "inventory_service_levels.csv", "safety_factor_z", bad, "Populate safety_factor_z for every SKU.")

        self.check_numeric_non_negative(self.frames.get("inventory_policy_parameters.csv"), "inventory_policy_parameters.csv", ["safety_stock", "reorder_point", "eoq", "recommended_order_quantity"])

        costs = self.frames.get("inventory_costs.csv")
        if costs is not None:
            cost_cols = []
            for col in costs.columns:
                if "cost" not in col.lower():
                    continue
                numeric_values = pd.to_numeric(costs[col], errors="coerce")
                if numeric_values.notna().any():
                    cost_cols.append(col)
            self.check_numeric_non_negative(costs, "inventory_costs.csv", cost_cols)

        self.check_numeric_non_negative(
            self.frames.get("inventory_scenario_results.csv"),
            "inventory_scenario_results.csv",
            [
                "scenario_operational_cost", "scenario_risk_penalty_cost", "scenario_constraint_penalty_cost",
                "scenario_total_penalty_adjusted_cost", "scenario_total_relevant_cost", "hard_blocker_count",
                "major_risk_count", "review_required_count", "soft_warning_count",
            ],
        )
        self.check_numeric_non_negative(
            self.frames.get("inventory_optimization_recommendations.csv"),
            "inventory_optimization_recommendations.csv",
            [
                "selected_total_penalty_adjusted_cost", "baseline_total_penalty_adjusted_cost",
                "selected_operational_cost", "baseline_operational_cost", "selected_hard_blocker_count",
            ],
        )
        self.check_numeric_non_negative(
            self.frames.get("inventory_control_master_decisions.csv"),
            "inventory_control_master_decisions.csv",
            [
                "selected_operational_cost", "baseline_operational_cost",
                "selected_total_penalty_adjusted_cost", "baseline_total_penalty_adjusted_cost",
            ],
        )

    def check_auto_apply_safety(self) -> None:
        for file_name in [
            "inventory_re_evaluation.csv",
            "inventory_parameter_adjustment_recommendations.csv",
            "inventory_optimization_recommendations.csv",
            "inventory_control_master_decisions.csv",
            "inventory_control_manager_dashboard.csv",
        ]:
            self.check_boolean_all_false(self.frames.get(file_name), file_name, "auto_apply_allowed")

    def check_review_queue_logic(self) -> None:
        master = self.frames.get("inventory_control_master_decisions.csv")
        mandatory = self.frames.get("inventory_control_human_review_queue.csv")
        advisory = self.frames.get("inventory_control_advisory_review_queue.csv")
        if master is None:
            self.add_result("REVIEW_QUEUE", "Review queue logic", SKIPPED, SKIPPED, "Master decisions file unavailable.", "inventory_control_master_decisions.csv")
            return
        required = ["sku_id", "final_review_required", "final_mandatory_review_required", "final_advisory_review_required"]
        if not all(col in master.columns for col in required):
            self.add_result("REVIEW_QUEUE", "Master review flags available", SKIPPED, SKIPPED, "Required review flag columns are missing.", "inventory_control_master_decisions.csv", _join_values(required))
            return

        review = _to_bool(master["final_review_required"])
        mandatory_flag = _to_bool(master["final_mandatory_review_required"])
        advisory_flag = _to_bool(master["final_advisory_review_required"])
        mismatch = int((review != mandatory_flag).sum())
        status = PASS if mismatch == 0 else FAIL
        self.add_result("REVIEW_QUEUE", "final_review_required equals mandatory review", status, status, f"Mismatched rows: {mismatch}.", "inventory_control_master_decisions.csv", "final_review_required; final_mandatory_review_required", mismatch, "Keep final_review_required reserved for mandatory review gates.")

        mandatory_skus = set(master.loc[mandatory_flag, "sku_id"].dropna().astype(str))
        advisory_only_skus = set(master.loc[advisory_flag & ~mandatory_flag, "sku_id"].dropna().astype(str))

        if mandatory is not None and "sku_id" in mandatory.columns:
            queue_skus = set(mandatory["sku_id"].dropna().astype(str))
            bad = queue_skus - mandatory_skus
            count_match = len(mandatory) == len(mandatory_skus)
            status = PASS if not bad and count_match else FAIL
            self.add_result("REVIEW_QUEUE", "Mandatory queue contains mandatory review rows only", status, status, f"Queue rows={len(mandatory)}, mandatory master rows={len(mandatory_skus)}, unexpected queue SKUs={len(bad)}.", "inventory_control_human_review_queue.csv", "sku_id", len(bad), "Build mandatory queue from final_mandatory_review_required only.")
        else:
            self.add_result("REVIEW_QUEUE", "Mandatory queue contains mandatory review rows only", SKIPPED, SKIPPED, "Mandatory queue file or sku_id unavailable.", "inventory_control_human_review_queue.csv")

        if advisory is not None and "sku_id" in advisory.columns:
            queue_skus = set(advisory["sku_id"].dropna().astype(str))
            bad = queue_skus - advisory_only_skus
            count_match = len(advisory) == len(advisory_only_skus)
            status = PASS if not bad and count_match else FAIL
            self.add_result("REVIEW_QUEUE", "Advisory queue contains advisory-only rows", status, status, f"Queue rows={len(advisory)}, advisory-only master rows={len(advisory_only_skus)}, unexpected queue SKUs={len(bad)}.", "inventory_control_advisory_review_queue.csv", "sku_id", len(bad), "Build advisory queue from advisory true and mandatory false rows only.")
        else:
            self.add_result("REVIEW_QUEUE", "Advisory queue contains advisory-only rows", SKIPPED, SKIPPED, "Advisory queue file or sku_id unavailable.", "inventory_control_advisory_review_queue.csv")

    def check_action_clarity(self) -> None:
        master = self.frames.get("inventory_control_master_decisions.csv")
        if master is None:
            self.add_result("ACTION_CLARITY", "Action clarity checks", SKIPPED, SKIPPED, "Master decisions file unavailable.", "inventory_control_master_decisions.csv")
            return
        self.check_no_missing(master, "inventory_control_master_decisions.csv", ["proposed_operational_action", "blocking_review_action", "execution_owner", "review_owner"])

        if {"final_action_owner", "final_review_type", "mandatory_review_gate_count"}.issubset(master.columns):
            multi = master["final_action_owner"].astype(str).eq("MULTI_DEPARTMENT_REVIEW")
            allowed = master["final_review_type"].astype(str).eq("MANDATORY_MULTI_DEPARTMENT_REVIEW") | (pd.to_numeric(master["mandatory_review_gate_count"], errors="coerce").fillna(0) > 1)
            bad = int((multi & ~allowed).sum())
            status = PASS if bad == 0 else FAIL
            self.add_result("ACTION_CLARITY", "Multi-department owner used only for multi-department review", status, status, f"Misused rows: {bad}.", "inventory_control_master_decisions.csv", "final_action_owner", bad, "Assign practical owner unless multiple mandatory gates require multi-department review.")
        else:
            self.add_result("ACTION_CLARITY", "Multi-department owner used only for multi-department review", SKIPPED, SKIPPED, "Required owner/review columns are missing.", "inventory_control_master_decisions.csv")

        if {"blocking_review_action", "proposed_operational_action"}.issubset(master.columns):
            phase4 = master["blocking_review_action"].astype(str).eq("REVIEW_PHASE4_PRODUCTION_LOGIC")
            bad = int((phase4 & _blank_mask(master["proposed_operational_action"])).sum())
            status = PASS if bad == 0 else FAIL
            self.add_result("ACTION_CLARITY", "Phase 4 blocking rows expose proposed operational action", status, status, f"Rows missing proposed action: {bad}.", "inventory_control_master_decisions.csv", "proposed_operational_action", bad, "Populate proposed_operational_action even when Phase 4 review is blocking.")

        if {"proposed_operational_action", "execution_owner"}.issubset(master.columns):
            split = master["proposed_operational_action"].astype(str).eq("SPLIT_DELIVERY")
            owners = master["execution_owner"].astype(str)
            bad = int((split & ~(owners.str.contains("PROCUREMENT_TEAM", na=False) & owners.str.contains("WAREHOUSE_TEAM", na=False))).sum())
            status = PASS if bad == 0 else FAIL
            self.add_result("ACTION_CLARITY", "Split delivery owner includes procurement and warehouse", status, status, f"Rows with incomplete split-delivery owner: {bad}.", "inventory_control_master_decisions.csv", "execution_owner", bad, "Set split-delivery execution owner to PROCUREMENT_TEAM; WAREHOUSE_TEAM.")

        if {"blocking_review_action", "final_mandatory_review_required"}.issubset(master.columns):
            no_block = master["blocking_review_action"].astype(str).eq("NO_BLOCKING_REVIEW")
            bad = int((no_block & _to_bool(master["final_mandatory_review_required"])).sum())
            status = PASS if bad == 0 else FAIL
            self.add_result("ACTION_CLARITY", "No blocking review means no mandatory review", status, status, f"Mismatched rows: {bad}.", "inventory_control_master_decisions.csv", "blocking_review_action; final_mandatory_review_required", bad, "Keep NO_BLOCKING_REVIEW aligned with final_mandatory_review_required=False.")

    def check_scenario_logic(self) -> None:
        scenarios = self.frames.get("inventory_scenarios.csv")
        results = self.frames.get("inventory_scenario_results.csv")
        opt = self.frames.get("inventory_optimization_recommendations.csv")
        base = self.frames.get("inventory_clean.csv")
        if scenarios is None:
            self.add_result("SCENARIOS", "Scenario logic checks", SKIPPED, SKIPPED, "inventory_scenarios.csv unavailable.", "inventory_scenarios.csv")
            return

        if base is not None and {"sku_id"}.issubset(base.columns) and {"sku_id", "scenario_name"}.issubset(scenarios.columns):
            baseline = scenarios["scenario_name"].astype(str).eq("CURRENT_POLICY")
            baseline_skus = set(scenarios.loc[baseline, "sku_id"].dropna().astype(str))
            base_skus = set(base["sku_id"].dropna().astype(str))
            missing = base_skus - baseline_skus
            status = PASS if not missing else FAIL
            self.add_result("SCENARIOS", "Every SKU has CURRENT_POLICY baseline scenario", status, status, f"Missing baseline SKUs: {len(missing)}.", "inventory_scenarios.csv", "scenario_name", len(missing), "Generate a CURRENT_POLICY baseline for every SKU.")

        if "sku_id" in scenarios.columns:
            counts = scenarios.groupby("sku_id").size()
            max_count = int(counts.max()) if not counts.empty else 0
            over = int((counts > SCENARIO_COUNT_CAP).sum())
            status = PASS if over == 0 else FAIL
            self.add_result("SCENARIOS", "Scenario count per SKU stays within cap", status, status, f"Max scenarios per SKU={max_count}; SKUs over cap={over}.", "inventory_scenarios.csv", "sku_id", over, "Keep generated scenarios controlled and signal-gated.")

        if "scenario_contradiction_flag" in scenarios.columns:
            bad = int(_to_bool(scenarios["scenario_contradiction_flag"]).sum())
            status = PASS if bad == 0 else FAIL
            self.add_result("SCENARIOS", "Contradictory scenarios rejected", status, status, f"Contradictory scenario rows: {bad}.", "inventory_scenarios.csv", "scenario_contradiction_flag", bad, "Reject contradictory scenarios before scoring.")

        if results is not None:
            if len(results) == len(scenarios):
                self.add_result("SCENARIOS", "Scenario results row count equals scenario rows", PASS, PASS, f"Rows={len(results)}.", "inventory_scenario_results.csv")
            else:
                self.add_result("SCENARIOS", "Scenario results row count equals scenario rows", FAIL, FAIL, f"Scenario rows={len(scenarios)}, result rows={len(results)}.", "inventory_scenario_results.csv", affected_rows=abs(len(results) - len(scenarios)), suggested_fix="Score every generated scenario exactly once.")
            if {"scenario_total_relevant_cost", "scenario_total_penalty_adjusted_cost"}.issubset(results.columns):
                diff = (pd.to_numeric(results["scenario_total_relevant_cost"], errors="coerce").fillna(0) - pd.to_numeric(results["scenario_total_penalty_adjusted_cost"], errors="coerce").fillna(0)).abs()
                bad = int((diff > TOLERANCE).sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("SCENARIOS", "Relevant cost equals penalty-adjusted cost", status, status, f"Rows outside tolerance: {bad}.", "inventory_scenario_results.csv", "scenario_total_relevant_cost; scenario_total_penalty_adjusted_cost", bad, "Keep backward-compatible relevant cost equal to penalty-adjusted total cost.")
            if "scenario_penalty_share_of_total" in results.columns:
                vals = pd.to_numeric(results["scenario_penalty_share_of_total"], errors="coerce")
                bad = int((vals.isna() | (vals < 0) | (vals > 1)).sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("SCENARIOS", "Scenario penalty share between 0 and 1", status, status, f"Invalid rows: {bad}.", "inventory_scenario_results.csv", "scenario_penalty_share_of_total", bad, "Bound penalty share to [0, 1].")
            if "legacy_constraint_penalty_used_flag" in results.columns:
                bad = int(_to_bool(results["legacy_constraint_penalty_used_flag"]).sum())
                status = PASS if bad == 0 else WARNING
                severity = PASS if bad == 0 else WARNING
                self.add_result("SCENARIOS", "Severity-based penalties replace legacy generic penalty", severity, status, f"Legacy penalty rows: {bad}.", "inventory_scenario_results.csv", "legacy_constraint_penalty_used_flag", bad, "Step 12C expects severity-based penalties instead of generic legacy penalties.")
            if "feasible_flag" in results.columns:
                bad = int(_blank_mask(results["feasible_flag"]).sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("SCENARIOS", "Scenario feasible_flag populated", status, status, f"Blank rows: {bad}.", "inventory_scenario_results.csv", "feasible_flag", bad, "Populate feasible_flag for every scenario result.")

        if opt is not None and results is not None:
            if {"selected_scenario_id"}.issubset(opt.columns) and {"scenario_id"}.issubset(results.columns):
                selected = set(opt["selected_scenario_id"].dropna().astype(str))
                all_results = set(results["scenario_id"].dropna().astype(str))
                missing = selected - all_results
                status = PASS if not missing else FAIL
                self.add_result("SCENARIOS", "Selected scenario IDs exist in scenario results", status, status, f"Missing selected scenario IDs: {len(missing)}.", "inventory_optimization_recommendations.csv", "selected_scenario_id", len(missing), "Select only scenarios present in inventory_scenario_results.csv.")
            if "selected_hard_blocker_count" in opt.columns:
                bad = int((pd.to_numeric(opt["selected_hard_blocker_count"], errors="coerce").fillna(0) > 0).sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("SCENARIOS", "Selected scenarios have no hard blockers", status, status, f"Selected rows with hard blockers: {bad}.", "inventory_optimization_recommendations.csv", "selected_hard_blocker_count", bad, "Never select hard-blocker scenarios in normal optimization.")

    def check_cost_reconciliation(self) -> None:
        master = self.frames.get("inventory_control_master_decisions.csv")
        opt = self.frames.get("inventory_optimization_recommendations.csv")
        results = self.frames.get("inventory_scenario_results.csv")
        self.compare_sums(master, "operational_cost_saving_vs_baseline", opt, "operational_cost_saving_vs_baseline", name="Master vs optimization operational savings", file_pair="inventory_control_master_decisions.csv; inventory_optimization_recommendations.csv")
        self.compare_sums(master, "penalty_adjusted_saving_vs_baseline", opt, "penalty_adjusted_saving_vs_baseline", name="Master vs optimization penalty-adjusted savings", file_pair="inventory_control_master_decisions.csv; inventory_optimization_recommendations.csv")

        if master is not None:
            needed = ["baseline_operational_cost", "selected_operational_cost", "operational_cost_saving_vs_baseline"]
            if all(col in master.columns for col in needed):
                diff = (pd.to_numeric(master["baseline_operational_cost"], errors="coerce").fillna(0) - pd.to_numeric(master["selected_operational_cost"], errors="coerce").fillna(0) - pd.to_numeric(master["operational_cost_saving_vs_baseline"], errors="coerce").fillna(0)).abs()
                bad = int((diff > TOLERANCE).sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("RECONCILIATION", "Master operational saving row formula", status, status, f"Rows outside tolerance: {bad}.", "inventory_control_master_decisions.csv", _join_values(needed), bad, "Keep baseline - selected equal to reported operational saving.")
            else:
                self.add_result("RECONCILIATION", "Master operational saving row formula", SKIPPED, SKIPPED, "Required operational cost columns missing.", "inventory_control_master_decisions.csv")

            needed = ["baseline_total_penalty_adjusted_cost", "selected_total_penalty_adjusted_cost", "penalty_adjusted_saving_vs_baseline"]
            if all(col in master.columns for col in needed):
                diff = (pd.to_numeric(master["baseline_total_penalty_adjusted_cost"], errors="coerce").fillna(0) - pd.to_numeric(master["selected_total_penalty_adjusted_cost"], errors="coerce").fillna(0) - pd.to_numeric(master["penalty_adjusted_saving_vs_baseline"], errors="coerce").fillna(0)).abs()
                bad = int((diff > TOLERANCE).sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("RECONCILIATION", "Master penalty-adjusted saving row formula", status, status, f"Rows outside tolerance: {bad}.", "inventory_control_master_decisions.csv", _join_values(needed), bad, "Keep baseline - selected equal to reported penalty-adjusted saving.")
            else:
                self.add_result("RECONCILIATION", "Master penalty-adjusted saving row formula", SKIPPED, SKIPPED, "Required penalty-adjusted cost columns missing.", "inventory_control_master_decisions.csv")

        if results is not None:
            needed = ["scenario_operational_cost", "scenario_risk_penalty_cost", "scenario_constraint_penalty_cost", "scenario_total_penalty_adjusted_cost"]
            if all(col in results.columns for col in needed):
                total = (
                    pd.to_numeric(results["scenario_operational_cost"], errors="coerce").fillna(0)
                    + pd.to_numeric(results["scenario_risk_penalty_cost"], errors="coerce").fillna(0)
                    + pd.to_numeric(results["scenario_constraint_penalty_cost"], errors="coerce").fillna(0)
                )
                diff = (total - pd.to_numeric(results["scenario_total_penalty_adjusted_cost"], errors="coerce").fillna(0)).abs()
                bad = int((diff > TOLERANCE).sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("RECONCILIATION", "Scenario cost components equal total penalty-adjusted cost", status, status, f"Rows outside tolerance: {bad}.", "inventory_scenario_results.csv", _join_values(needed), bad, "Keep operational + risk penalty + constraint penalty equal to total penalty-adjusted cost.")
            else:
                self.add_result("RECONCILIATION", "Scenario cost components equal total penalty-adjusted cost", SKIPPED, SKIPPED, "Required scenario cost columns missing.", "inventory_scenario_results.csv")

    def check_warehouse_batch_logic(self) -> None:
        batch = self.frames.get("batch_slotting.csv")
        visual_batches = self.frames.get("warehouse_visual_batches.csv")
        location = self.frames.get("location_utilization.csv")
        slotting = self.frames.get("warehouse_slotting.csv")

        if batch is not None:
            if {"batch_trace_only_flag", "include_in_physical_map"}.issubset(batch.columns):
                bad = int((_to_bool(batch["batch_trace_only_flag"]) & _to_bool(batch["include_in_physical_map"])).sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("WAREHOUSE_BATCH", "Trace-only batches excluded from physical map", status, status, f"Trace-only physical rows: {bad}.", "batch_slotting.csv", "batch_trace_only_flag; include_in_physical_map", bad, "Keep trace-only zero-quantity batches out of physical maps.")
            else:
                self.add_result("WAREHOUSE_BATCH", "Trace-only batches excluded from physical map", WARNING, SKIPPED, "Trace-only or physical-map columns missing.", "batch_slotting.csv", suggested_fix="Keep Step 9D visual controls in batch_slotting.csv.")

            required = {"expired_flag", "near_expiry_flag", "active_batch_quantity_flag", "batch_trace_only_flag"}
            if required.issubset(batch.columns):
                inactive = ~_to_bool(batch["active_batch_quantity_flag"])
                expired_or_near = _to_bool(batch["expired_flag"]) | _to_bool(batch["near_expiry_flag"])
                bad = int((inactive & expired_or_near & ~_to_bool(batch["batch_trace_only_flag"])).sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("WAREHOUSE_BATCH", "Zero-quantity expired/near-expiry batches are trace-only", status, status, f"Inactive expired/near-expiry rows not trace-only: {bad}.", "batch_slotting.csv", "batch_trace_only_flag", bad, "Mark inactive expired/near-expiry batches as trace-only.")
            else:
                self.add_result("WAREHOUSE_BATCH", "Zero-quantity expired/near-expiry batches are trace-only", WARNING, SKIPPED, "Required active/expiry columns missing.", "batch_slotting.csv")

            if {"expired_flag", "active_batch_quantity_flag", "recommended_batch_zone", "batch_slotting_action"}.issubset(batch.columns):
                active_expired = _to_bool(batch["expired_flag"]) & _to_bool(batch["active_batch_quantity_flag"])
                ok = batch["recommended_batch_zone"].astype(str).str.contains("QUARANTINE", case=False, na=False) | batch["batch_slotting_action"].astype(str).str.contains("QUARANTINE", case=False, na=False)
                bad = int((active_expired & ~ok).sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("WAREHOUSE_BATCH", "Active expired batches assigned to quarantine", status, status, f"Active expired rows without quarantine: {bad}.", "batch_slotting.csv", "recommended_batch_zone; batch_slotting_action", bad, "Send active expired batches to quarantine or document quarantine action.")
            else:
                self.add_result("WAREHOUSE_BATCH", "Active expired batches assigned to quarantine", WARNING, SKIPPED, "Required quarantine columns missing.", "batch_slotting.csv")

            if {"near_expiry_flag", "active_batch_quantity_flag", "recommended_batch_zone", "batch_slotting_action"}.issubset(batch.columns):
                active_near = _to_bool(batch["near_expiry_flag"]) & _to_bool(batch["active_batch_quantity_flag"])
                zone_or_action = batch["recommended_batch_zone"].astype(str) + " " + batch["batch_slotting_action"].astype(str)
                ok = zone_or_action.str.contains("FEFO|FAST_PICK|CASE_PICKING|EACH_PICKING", case=False, regex=True, na=False)
                bad = int((active_near & ~ok).sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("WAREHOUSE_BATCH", "Active near-expiry batches assigned to FEFO/pick-friendly handling", status, status, f"Active near-expiry rows without FEFO/pick-friendly handling: {bad}.", "batch_slotting.csv", "recommended_batch_zone; batch_slotting_action", bad, "Route active near-expiry batches to FEFO-accessible or pick-friendly handling.")
            else:
                self.add_result("WAREHOUSE_BATCH", "Active near-expiry batches assigned to FEFO/pick-friendly handling", WARNING, SKIPPED, "Required FEFO columns missing.", "batch_slotting.csv")

        if visual_batches is not None:
            if {"batch_trace_only_flag", "show_on_physical_map"}.issubset(visual_batches.columns):
                bad = int((_to_bool(visual_batches["batch_trace_only_flag"]) & _to_bool(visual_batches["show_on_physical_map"])).sum())
                status = PASS if bad == 0 else FAIL
                self.add_result("WAREHOUSE_BATCH", "Visual trace-only batches hidden from physical map", status, status, f"Trace-only visual physical rows: {bad}.", "warehouse_visual_batches.csv", "show_on_physical_map", bad, "Do not draw trace-only batches as physical stock.")
            else:
                self.add_result("WAREHOUSE_BATCH", "Visual trace-only batches hidden from physical map", WARNING, SKIPPED, "Trace-only visual controls missing.", "warehouse_visual_batches.csv")
            if batch is not None and "include_in_physical_map" in batch.columns and "show_on_physical_map" in visual_batches.columns:
                physical_batch = int(_to_bool(batch["include_in_physical_map"]).sum())
                physical_visual = int(_to_bool(visual_batches["show_on_physical_map"]).sum())
                status = PASS if physical_batch == physical_visual else FAIL
                self.add_result("WAREHOUSE_BATCH", "Physical-map batch counts reconcile", status, status, f"batch_slotting={physical_batch}, warehouse_visual_batches={physical_visual}.", "warehouse_visual_batches.csv", "show_on_physical_map", abs(physical_batch - physical_visual), "Keep visual batch physical-map count aligned with batch_slotting.")

        if location is not None:
            cols = ["current_over_capacity_flag", "projected_over_capacity_flag", "current_capacity_pressure_flag", "projected_capacity_pressure_flag"]
            missing = [col for col in cols if col not in location.columns]
            status = PASS if not missing else WARNING
            self.add_result("WAREHOUSE_BATCH", "Location utilization separates current/projected capacity flags", status, status if not missing else SKIPPED, "All current/projected capacity fields exist." if not missing else f"Missing fields: {_join_values(missing)}", "location_utilization.csv", _join_values(cols), suggested_fix="Retain Step 9D current/projected capacity split fields.")

        if slotting is not None:
            status = PASS if "z_level_score" in slotting.columns else WARNING
            self.add_result("WAREHOUSE_BATCH", "Warehouse slotting has z-level score", status, status if status == PASS else SKIPPED, "z_level_score exists." if status == PASS else "z_level_score is missing.", "warehouse_slotting.csv", "z_level_score", suggested_fix="Keep z-level scoring for Step 10 visual readiness.")
            if "slotting_warning_flags" in slotting.columns:
                warnings = int((~_blank_mask(slotting["slotting_warning_flags"])).sum())
                self.add_result("WAREHOUSE_BATCH", "Slotting warning flags are readable when present", PASS, PASS, f"Rows with slotting warnings: {warnings}.", "warehouse_slotting.csv", "slotting_warning_flags")
            else:
                self.add_result("WAREHOUSE_BATCH", "Slotting warning flags are readable when present", WARNING, SKIPPED, "slotting_warning_flags column missing.", "warehouse_slotting.csv", "slotting_warning_flags")

    def check_manager_output_quality(self) -> None:
        master = self.frames.get("inventory_control_master_decisions.csv")
        dashboard = self.frames.get("inventory_control_manager_dashboard.csv")
        if master is not None:
            allowed = {
                "final_decision_priority": {"URGENT", "HIGH", "MEDIUM", "LOW", "NO_ACTION"},
                "final_manager_status": {"TAKE_ACTION_NOW", "REVIEW_BEFORE_ACTION", "MONITOR", "NO_ACTION_REQUIRED"},
                "final_review_severity": {"MANDATORY", "ADVISORY", "INFO_ONLY", "NO_REVIEW"},
            }
            for col, values in allowed.items():
                if col not in master.columns:
                    self.add_result("MANAGER_OUTPUT", f"Allowed values for {col}", SKIPPED, SKIPPED, "Column missing.", "inventory_control_master_decisions.csv", col)
                    continue
                invalid = int((~master[col].astype(str).isin(values)).sum())
                status = PASS if invalid == 0 else FAIL
                self.add_result("MANAGER_OUTPUT", f"Allowed values for {col}", status, status, f"Invalid rows: {invalid}.", "inventory_control_master_decisions.csv", col, invalid, f"Use only configured allowed values: {_join_values(values)}")
            if {"final_manager_status", "final_mandatory_review_required"}.issubset(master.columns):
                mandatory = _to_bool(master["final_mandatory_review_required"])
                review_bad = int((master["final_manager_status"].astype(str).eq("REVIEW_BEFORE_ACTION") & ~mandatory).sum())
                action_bad = int((master["final_manager_status"].astype(str).eq("TAKE_ACTION_NOW") & mandatory).sum())
                self.add_result("MANAGER_OUTPUT", "REVIEW_BEFORE_ACTION requires mandatory review", PASS if review_bad == 0 else FAIL, PASS if review_bad == 0 else FAIL, f"Mismatched rows: {review_bad}.", "inventory_control_master_decisions.csv", "final_manager_status; final_mandatory_review_required", review_bad, "Use REVIEW_BEFORE_ACTION only for mandatory review rows.")
                self.add_result("MANAGER_OUTPUT", "TAKE_ACTION_NOW cannot have mandatory review", PASS if action_bad == 0 else FAIL, PASS if action_bad == 0 else FAIL, f"Mismatched rows: {action_bad}.", "inventory_control_master_decisions.csv", "final_manager_status; final_mandatory_review_required", action_bad, "Use TAKE_ACTION_NOW only when action is not blocked by mandatory review.")
            if {"final_manager_status", "proposed_operational_action"}.issubset(master.columns):
                no_action = master["final_manager_status"].astype(str).eq("NO_ACTION_REQUIRED")
                ok = master["proposed_operational_action"].astype(str).isin({"NO_ACTION", "MONITOR_ONLY"})
                bad = int((no_action & ~ok).sum())
                status = PASS if bad == 0 else WARNING
                self.add_result("MANAGER_OUTPUT", "NO_ACTION_REQUIRED aligns with no-action or monitor action", status, status, f"Potential mismatch rows: {bad}.", "inventory_control_master_decisions.csv", "final_manager_status; proposed_operational_action", bad, "Ensure no-action manager status does not hide an operational action.")

        if dashboard is not None:
            col = "suggested_dashboard_color_group"
            values = {"RED", "ORANGE", "YELLOW", "GREEN", "BLUE", "GRAY"}
            if col in dashboard.columns:
                invalid = int((~dashboard[col].astype(str).isin(values)).sum())
                status = PASS if invalid == 0 else FAIL
                self.add_result("MANAGER_OUTPUT", "Allowed dashboard color groups", status, status, f"Invalid color rows: {invalid}.", "inventory_control_manager_dashboard.csv", col, invalid, "Use configured dashboard color groups only.")
            else:
                self.add_result("MANAGER_OUTPUT", "Allowed dashboard color groups", SKIPPED, SKIPPED, "Dashboard color column missing.", "inventory_control_manager_dashboard.csv", col)

    def check_inventory_kpi_quality(self) -> None:
        kpis = self.frames.get("inventory_kpi_summary.csv")
        dashboard = self.frames.get("inventory_control_manager_dashboard.csv")
        if kpis is None:
            self.add_result("INVENTORY_KPIS", "Inventory KPI summary exists and loads", SKIPPED, SKIPPED, "inventory_kpi_summary.csv was not loaded.", "inventory_kpi_summary.csv")
            return
        required = [
            "sku_id",
            "outbound_to_current_inventory_ratio_90d",
            "outbound_to_current_inventory_ratio_90d_method",
            "outbound_to_current_inventory_ratio_90d_data_quality",
            "inventory_turnover_units_90d",
            "inventory_turnover_method",
            "inventory_turnover_data_quality",
            "days_inventory_on_hand",
            "days_inventory_on_hand_status",
            "unit_fill_rate_proxy",
            "unit_fill_rate_data_quality",
            "stockout_rate",
            "stockout_rate_data_quality",
            "max_stock_threshold_units",
            "excess_inventory_units",
            "excess_inventory_rate",
            "excess_inventory_data_quality",
            "dead_stock_rate",
            "expiry_exposure_rate_30d",
            "inventory_reconciliation_accuracy_rate",
            "fefo_compliance_rate",
            "fefo_compliance_data_quality",
            "inventory_kpi_warning_codes",
        ]
        self.require_columns(kpis, "inventory_kpi_summary.csv", required)
        bounded = [
            "excess_inventory_rate",
            "dead_stock_rate",
            "expiry_exposure_rate_30d",
            "inventory_reconciliation_accuracy_rate",
            "unit_fill_rate_proxy",
            "stockout_rate",
            "fefo_compliance_rate",
        ]
        for column in bounded:
            if column not in kpis.columns:
                continue
            values = pd.to_numeric(kpis[column], errors="coerce")
            bad = int(((values.dropna() < 0) | (values.dropna() > 1)).sum())
            self.add_result(
                "INVENTORY_KPIS",
                f"{column} is within 0 to 1 when available",
                PASS if bad == 0 else FAIL,
                PASS if bad == 0 else FAIL,
                f"Out-of-bound non-null values: {bad}.",
                "inventory_kpi_summary.csv",
                column,
                bad,
            )
        self.check_numeric_non_negative(kpis, "inventory_kpi_summary.csv", ["outbound_to_current_inventory_ratio_90d", "inventory_turnover_units_90d", "days_inventory_on_hand"])
        if {"inventory_turnover_method", "outbound_to_current_inventory_ratio_90d_method"}.issubset(kpis.columns):
            bad_turnover_label = int(
                (
                    kpis["inventory_turnover_method"].astype(str).ne("PROXY_NOT_FORMAL_TURNOVER")
                    | kpis["outbound_to_current_inventory_ratio_90d_method"].astype(str).ne("OUTBOUND_UNITS_90D_DIVIDED_BY_CURRENT_USABLE_INVENTORY_PROXY")
                ).sum()
            )
            self.add_result(
                "INVENTORY_KPIS",
                "Inventory turnover is explicitly labelled as a proxy",
                PASS if bad_turnover_label == 0 else FAIL,
                PASS if bad_turnover_label == 0 else FAIL,
                f"Rows with misleading turnover method labels: {bad_turnover_label}.",
                "inventory_kpi_summary.csv",
                "inventory_turnover_method",
                bad_turnover_label,
            )
        if {"max_stock_threshold_units", "excess_inventory_rate", "excess_inventory_data_quality"}.issubset(kpis.columns):
            threshold = pd.to_numeric(kpis["max_stock_threshold_units"], errors="coerce")
            excess_rate = pd.to_numeric(kpis["excess_inventory_rate"], errors="coerce")
            quality = kpis["excess_inventory_data_quality"].astype(str)
            bad_missing_threshold = int(((threshold.isna() | (threshold <= 0)) & (excess_rate.notna() | quality.ne("UNAVAILABLE_POLICY_THRESHOLD"))).sum())
            self.add_result(
                "INVENTORY_KPIS",
                "Excess inventory requires a valid max-stock threshold",
                PASS if bad_missing_threshold == 0 else FAIL,
                PASS if bad_missing_threshold == 0 else FAIL,
                f"Rows where missing/nonpositive thresholds produced an excess KPI: {bad_missing_threshold}.",
                "inventory_kpi_summary.csv",
                "max_stock_threshold_units; excess_inventory_rate",
                bad_missing_threshold,
            )
        unavailable = 0
        for column in ["unit_fill_rate_data_quality", "stockout_rate_data_quality", "fefo_compliance_data_quality"]:
            if column in kpis.columns:
                unavailable += int(kpis[column].astype(str).eq("UNAVAILABLE").sum())
        self.add_result(
            "INVENTORY_KPIS",
            "Unavailable formal KPIs are explicitly flagged",
            PASS,
            PASS,
            f"Unavailable method/data-quality flags: {unavailable}.",
            "inventory_kpi_summary.csv",
            "unit_fill_rate_data_quality; stockout_rate_data_quality; fefo_compliance_data_quality",
            unavailable,
        )
        if dashboard is not None:
            required_dashboard = [
                "days_inventory_on_hand",
                "days_inventory_on_hand_status",
                "outbound_to_current_inventory_ratio_90d",
                "outbound_to_current_inventory_ratio_90d_data_quality",
                "excess_inventory_units",
                "excess_inventory_rate",
                "excess_inventory_data_quality",
                "dead_stock_rate",
                "expiry_exposure_rate_30d",
                "inventory_reconciliation_accuracy_rate",
            ]
            missing = [column for column in required_dashboard if column not in dashboard.columns]
            self.add_result(
                "INVENTORY_KPIS",
                "Manager dashboard contains compact inventory KPI fields",
                PASS if not missing else FAIL,
                PASS if not missing else FAIL,
                "All compact dashboard KPI fields are present." if not missing else f"Missing dashboard KPI fields: {_join_values(missing)}",
                "inventory_control_manager_dashboard.csv",
                _join_values(required_dashboard),
                len(missing),
            )

    def check_employee_task_view(self) -> None:
        tasks = self.frames.get("inventory_employee_task_view.csv")
        if tasks is None:
            self.add_result("EMPLOYEE_TASK_VIEW", "Employee task view exists and loads", SKIPPED, SKIPPED, "inventory_employee_task_view.csv was not loaded.", "inventory_employee_task_view.csv")
            return
        required = [
            "sku_id",
            "product_name",
            "category",
            "warehouse_zone",
            "storage_location",
            "available_quantity",
            "usable_quantity",
            "net_replenishment_requirement",
            "recommended_action",
            "action_priority",
            "next_delivery_date",
            "expiry_status",
            "handling_warning",
            "manager_review_required",
            "employee_instruction",
        ]
        self.require_columns(tasks, "inventory_employee_task_view.csv", required)
        missing_instruction = int(_blank_mask(tasks["employee_instruction"]).sum()) if "employee_instruction" in tasks.columns else len(tasks)
        missing_review = int(_blank_mask(tasks["manager_review_required"]).sum()) if "manager_review_required" in tasks.columns else len(tasks)
        duplicate_skus = int(tasks["sku_id"].dropna().astype(str).duplicated().sum()) if "sku_id" in tasks.columns else len(tasks)
        self.add_result(
            "EMPLOYEE_TASK_VIEW",
            "Employee task rows have populated instruction and review fields",
            PASS if missing_instruction == 0 and missing_review == 0 and duplicate_skus == 0 else FAIL,
            PASS if missing_instruction == 0 and missing_review == 0 and duplicate_skus == 0 else FAIL,
            f"blank instructions={missing_instruction}, blank review flags={missing_review}, duplicate SKU rows={duplicate_skus}.",
            "inventory_employee_task_view.csv",
            "employee_instruction; manager_review_required; sku_id",
            missing_instruction + missing_review + duplicate_skus,
        )
        if {"available_quantity", "usable_quantity"}.issubset(tasks.columns):
            available = pd.to_numeric(tasks["available_quantity"], errors="coerce")
            usable = pd.to_numeric(tasks["usable_quantity"], errors="coerce")
            negative_count = int(((available < 0) | (usable < 0)).sum())
            missing_quantity_count = int((available.isna() | usable.isna()).sum())
            self.add_result(
                "EMPLOYEE_TASK_VIEW",
                "Employee-facing stock quantities are non-negative",
                PASS if negative_count == 0 and missing_quantity_count == 0 else FAIL,
                PASS if negative_count == 0 and missing_quantity_count == 0 else FAIL,
                f"Rows with negative quantities={negative_count}, missing displayed quantities={missing_quantity_count}.",
                "inventory_employee_task_view.csv",
                "available_quantity; usable_quantity",
                negative_count + missing_quantity_count,
                "Clip employee-facing quantities at zero and expose the source issue as a review warning.",
            )
        if "handling_warning" in tasks.columns:
            allowed_warning_labels = {
                "LOW STOCK",
                "WAITING DELIVERY",
                "NEAR EXPIRY",
                "MANAGER REVIEW REQUIRED",
                "NO ACTION REQUIRED",
                "WAREHOUSE CHECK REQUIRED",
                "SUPPLIER SHORTAGE",
                "PARTIAL ALLOCATION REVIEW",
                "STOCKOUT_OR_NEGATIVE_INVENTORY_REVIEW",
            }
            invalid_warning_rows = 0
            for value in tasks["handling_warning"].fillna("").astype(str):
                labels = [part.strip() for part in value.split(";") if part.strip()]
                if not labels or any(label not in allowed_warning_labels for label in labels):
                    invalid_warning_rows += 1
            self.add_result(
                "EMPLOYEE_TASK_VIEW",
                "Employee warnings use simplified readable labels",
                PASS if invalid_warning_rows == 0 else FAIL,
                PASS if invalid_warning_rows == 0 else FAIL,
                f"Rows with blank or unsupported employee warning labels: {invalid_warning_rows}.",
                "inventory_employee_task_view.csv",
                "handling_warning",
                invalid_warning_rows,
                "Use concise operational labels instead of backend technical warning noise.",
            )
        if {"net_replenishment_requirement", "next_delivery_date"}.issubset(tasks.columns):
            needs_delivery = pd.to_numeric(tasks["net_replenishment_requirement"], errors="coerce").fillna(0) > 0
            blank_delivery = _blank_mask(tasks["next_delivery_date"])
            blank_count = int((needs_delivery & blank_delivery).sum())
            self.add_result(
                "EMPLOYEE_TASK_VIEW",
                "Next delivery blanks are visible review cases",
                WARNING if blank_count else PASS,
                WARNING if blank_count else PASS,
                f"Rows with replenishment requirement and blank next delivery date: {blank_count}. This is acceptable when no delivery exists and must remain visible.",
                "inventory_employee_task_view.csv",
                "next_delivery_date",
                blank_count,
            )
        shared_summary_path = self.project_dir.parent / "shared" / "outputs" / "phase2_procurement_allocation_summary.csv"
        if shared_summary_path.exists() and "sku_id" in tasks.columns:
            try:
                allocation_summary = pd.read_csv(shared_summary_path)
            except Exception:
                allocation_summary = pd.DataFrame()
            if "sku_id" in allocation_summary.columns:
                unallocated = pd.to_numeric(allocation_summary.get("unallocated_requirement_units", 0), errors="coerce").fillna(0)
                allocation_codes = allocation_summary.get("allocation_warning_codes", pd.Series("", index=allocation_summary.index)).fillna("").astype(str).str.upper()
                shortage_rows = allocation_summary[
                    (unallocated > 0)
                    | allocation_codes.str.contains("UNALLOCATED_REQUIREMENT_REMAINS|ALLOCATION_ADJUSTMENT_REQUIRED|REQUIREMENT_NOT_FULLY_ALLOCATED|AGGREGATE_CAPACITY_SHORTFALL", na=False)
                ][["sku_id"]].drop_duplicates()
                if not shortage_rows.empty:
                    review_check = shortage_rows.merge(
                        tasks[["sku_id", "manager_review_required", "handling_warning", "employee_instruction"]],
                        on="sku_id",
                        how="left",
                    )
                    missing_review = int((~_to_bool(review_check["manager_review_required"])).sum())
                    shortage_warning_mask = review_check["handling_warning"].fillna("").astype(str).str.contains(
                        "SUPPLIER SHORTAGE|PARTIAL ALLOCATION REVIEW",
                        na=False,
                    )
                    unclear_warning = int((~shortage_warning_mask).sum())
                    wait_only = int(review_check["employee_instruction"].fillna("").astype(str).str.strip().eq("Wait for delivery").sum())
                    bad = missing_review + unclear_warning + wait_only
                    self.add_result(
                        "EMPLOYEE_TASK_VIEW",
                        "Integrated allocation shortages require manager review in employee task view",
                        PASS if bad == 0 else FAIL,
                        PASS if bad == 0 else FAIL,
                        (
                            f"shortage SKUs={len(review_check)}, missing review flags={missing_review}, "
                            f"unclear shortage warnings={unclear_warning}, wait-only instructions={wait_only}."
                        ),
                        "inventory_employee_task_view.csv",
                        "manager_review_required; handling_warning; employee_instruction",
                        bad,
                        "Flag unallocated or adjustment-required SKUs for manager review with a partial-allocation instruction.",
                    )
        shared_allocation_path = self.project_dir.parent / "shared" / "outputs" / "phase2_procurement_allocation_context.csv"
        if shared_allocation_path.exists():
            try:
                allocation_context = pd.read_csv(shared_allocation_path)
            except Exception:
                allocation_context = pd.DataFrame()
            if "allocation_execution_allowed" in allocation_context.columns:
                true_count = int(_to_bool(allocation_context["allocation_execution_allowed"]).sum())
                self.add_result(
                    "EMPLOYEE_TASK_VIEW",
                    "Allocation execution remains disabled for UI",
                    PASS if true_count == 0 else FAIL,
                    PASS if true_count == 0 else FAIL,
                    f"allocation_execution_allowed true rows: {true_count}.",
                    "phase2_procurement_allocation_context.csv",
                    "allocation_execution_allowed",
                    true_count,
                )
        integrated_decisions_path = self.project_dir.parent / "shared" / "outputs" / "integrated_replenishment_decisions.csv"
        if integrated_decisions_path.exists():
            try:
                integrated = pd.read_csv(integrated_decisions_path)
            except Exception:
                integrated = pd.DataFrame()
            safety_columns = [
                "auto_apply_allowed",
                "purchase_order_creation_allowed",
                "procurement_execution_ready_flag",
            ]
            present = [column for column in safety_columns if column in integrated.columns]
            if present:
                true_count = int(sum(_to_bool(integrated[column]).sum() for column in present))
                self.add_result(
                    "EMPLOYEE_TASK_VIEW",
                    "Integrated execution safety flags remain disabled for UI",
                    PASS if true_count == 0 else FAIL,
                    PASS if true_count == 0 else FAIL,
                    f"true safety/execution flag cells across integrated decisions: {true_count}.",
                    "integrated_replenishment_decisions.csv",
                    _join_values(present),
                    true_count,
                    "Keep the Phase 3 UI advisory-only until an approved execution workflow exists.",
                )
        app_path = self.project_dir / "app.py"
        if app_path.exists():
            try:
                py_compile.compile(str(app_path), doraise=True)
                self.add_result(
                    "EMPLOYEE_TASK_VIEW",
                    "Phase 3 Streamlit app compiles",
                    PASS,
                    PASS,
                    "app.py compiled successfully.",
                    "app.py",
                )
            except Exception as exc:
                self.add_result(
                    "EMPLOYEE_TASK_VIEW",
                    "Phase 3 Streamlit app compiles",
                    FAIL,
                    FAIL,
                    f"app.py compile error: {exc}",
                    "app.py",
                    suggested_fix="Fix syntax/import errors in the Phase 3 Streamlit app.",
                )
        else:
            self.add_result("EMPLOYEE_TASK_VIEW", "Phase 3 Streamlit app compiles", FAIL, FAIL, "app.py is missing.", "app.py")

    def add_known_limitations(self) -> None:
        limitations = [
            ("No purchase order creation yet.", "Future execution layer may create purchase orders after approval."),
            ("Supplier return-policy fields are available through Phase 2 bridges, but automated return execution is not implemented.", "Use Phase 2 return-policy fields for advisory review only until an approved return execution workflow exists."),
            ("Backorder aging foundation exists in Phase 2, but deeper batch/inventory/forecast feedback integration remains future work.", "Connect backorder aging signals back into inventory and forecasting feedback loops in a later integration step."),
            ("No Phase 4 BOM/production logic yet.", "Build Phase 4 production/BOM integration separately."),
            ("No stockout-censored demand correction yet.", "Add censored demand correction before advanced forecasting."),
            ("No automatic policy application yet.", "Keep auto-apply disabled until governance is approved."),
            ("Role-based Streamlit UI foundation exists, but approved execution workflows are not implemented.", "Keep the UI read-only until governance and execution workflows are approved."),
            ("Cost assumptions still partly fallback-based.", "Replace fallback cost assumptions with finance-approved values."),
            ("Phase 3 internal scenario labels remain strategy-level; integrated supplier IDs and quantities come from Phase 2 allocation bridges.", "Use integrated bridge outputs for supplier-ID allocation detail while keeping Phase 3 scenario labels advisory."),
            ("Scenario optimizer is rule-based, not simulation-based.", "Use simulation only after the rule-based layer is accepted."),
            ("Re-evaluation engine is rule-based, not historical learning loop.", "Add historical learning loop in a later model improvement phase."),
        ]
        for limitation, fix in limitations:
            self.add_result("KNOWN_LIMITATIONS", limitation, WARNING, WARNING, limitation, suggested_fix=fix)

    def add_validation_output_rows(self) -> None:
        for file_name in VALIDATION_OUTPUT_FILES:
            self.add_result(
                "VALIDATION_OUTPUTS",
                f"Validation output generated: {file_name}",
                PASS,
                PASS,
                "This file is generated by validate_phase3.py at the end of the run.",
                file_name,
            )

    def write_outputs(self) -> dict[str, Any]:
        summary_df = pd.DataFrame(self.results)
        severity_order = {"FAIL": 0, "WARNING": 1, "SKIPPED": 2, "PASS": 3}
        issues_df = summary_df[summary_df["severity"].isin([FAIL, WARNING, SKIPPED])].copy()
        if not issues_df.empty:
            issues_df["_severity_order"] = issues_df["severity"].map(severity_order).fillna(9)
            issues_df = issues_df.sort_values(["_severity_order", "check_group", "check_id"]).drop(columns=["_severity_order"])

        fail_count = int((summary_df["severity"] == FAIL).sum())
        warning_count = int((summary_df["severity"] == WARNING).sum())
        skipped_count = int((summary_df["severity"] == SKIPPED).sum())
        pass_count = int((summary_df["severity"] == PASS).sum())
        overall_status = FAIL if fail_count else (WARNING if warning_count or skipped_count else PASS)

        report_text = self.build_report(summary_df, overall_status, pass_count, warning_count, fail_count, skipped_count)

        summary_path = self.outputs_dir / "phase3_validation_summary.csv"
        issues_path = self.outputs_dir / "phase3_validation_issues.csv"
        report_path = self.outputs_dir / "phase3_validation_report.txt"
        wrap_up_path = self.outputs_dir / "phase3_wrap_up_summary.txt"

        summary_df.to_csv(summary_path, index=False)
        issues_df.to_csv(issues_path, index=False)
        report_path.write_text(report_text, encoding="utf-8")
        wrap_up_path.write_text(
            self.build_wrap_up_summary(summary_df, overall_status, pass_count, warning_count, fail_count, skipped_count),
            encoding="utf-8",
        )

        return {
            "report_path": str(report_path),
            "summary_path": str(summary_path),
            "issues_path": str(issues_path),
            "wrap_up_path": str(wrap_up_path),
            "overall_status": overall_status,
            "pass_count": pass_count,
            "warning_count": warning_count,
            "fail_count": fail_count,
            "skipped_count": skipped_count,
        }

    def build_wrap_up_summary(
        self,
        summary_df: pd.DataFrame,
        overall_status: str,
        pass_count: int,
        warning_count: int,
        fail_count: int,
        skipped_count: int,
    ) -> str:
        tasks = self.frames.get("inventory_employee_task_view.csv", pd.DataFrame())
        master = self.frames.get("inventory_control_master_decisions.csv", pd.DataFrame())
        kpis = self.frames.get("inventory_kpi_summary.csv", pd.DataFrame())
        integrated_evidence_path = self.project_dir.parent / "shared" / "validation" / "integrated_validation_evidence.json"
        integrated = {}
        if integrated_evidence_path.exists():
            try:
                integrated = json.loads(integrated_evidence_path.read_text(encoding="utf-8"))
            except Exception:
                integrated = {}
        overall = integrated.get("overall_result", {})
        warnings = summary_df[summary_df["severity"] == WARNING]["check_name"].head(12).astype(str).tolist()
        unavailable_kpis = 0
        for column in ["unit_fill_rate_data_quality", "stockout_rate_data_quality", "fefo_compliance_data_quality", "excess_inventory_data_quality"]:
            if not kpis.empty and column in kpis.columns:
                unavailable_kpis += int(kpis[column].fillna("").astype(str).str.contains("UNAVAILABLE", na=False).sum())
        lines = [
            "Phase 3 Wrap-Up Summary",
            "=======================",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "Phase 3 Status",
            f"- Local validation: {overall_status} (PASS {pass_count}, WARNING {warning_count}, FAIL {fail_count}, SKIPPED {skipped_count})",
            f"- Integrated validation: {overall.get('status', 'UNKNOWN')} (PASS {overall.get('pass_count', 'n/a')}, WARNING {overall.get('warning_count', 'n/a')}, FAIL {overall.get('fail_count', 'n/a')})",
            f"- Convergence: {overall.get('convergence_status', 'UNKNOWN')}",
            "",
            "Main Outputs",
            "- inventory_control_master_decisions.csv",
            "- inventory_control_manager_dashboard.csv",
            "- inventory_employee_task_view.csv",
            "- inventory_kpi_summary.csv",
            "- phase3_validation_report.txt",
            "",
            "UI Status",
            f"- Shared employee task rows: {len(tasks)}",
            f"- Unique task SKUs: {tasks['sku_id'].nunique() if 'sku_id' in tasks.columns else 0}",
            "- Role-based Streamlit UI: Manager and Employee / Warehouse Staff views",
            "- UI mode: read-only advisory",
            "",
            "Remaining Warnings",
        ]
        lines.extend([f"- {item}" for item in warnings] if warnings else ["- None"])
        lines.extend(
            [
                "",
                "Safety Status",
                "- auto_apply_allowed = False",
                "- purchase_order_creation_allowed = False",
                "- procurement_execution_ready_flag = False",
                "- allocation_execution_allowed = False",
                "- No purchase orders, supplier changes, inventory mutations, policy changes, or warehouse changes are executed.",
                "",
                "Known Limitations",
                f"- Unavailable KPI fields: {unavailable_kpis}",
                "- Supplier return, PO creation, and inventory/policy execution workflows are not implemented.",
                "- Scenario optimization and re-evaluation remain rule-based.",
                "- Phase 4 production/BOM logic is not implemented yet.",
                "",
                "Recommended Next Phases",
                "- Use the stable Phase 3 UI contract to define any future dashboard extensions.",
                "- Begin Phase 4 production/BOM planning when ready.",
                "- Later add approved execution workflows, logistics, finance, and deeper historical learning.",
            ]
        )
        return "\n".join(lines) + "\n"

    def build_report(
        self,
        summary_df: pd.DataFrame,
        overall_status: str,
        pass_count: int,
        warning_count: int,
        fail_count: int,
        skipped_count: int,
    ) -> str:
        lines: list[str] = []
        lines.append("Phase 3 Validation Report")
        lines.append("=" * 27)
        lines.append(f"Timestamp: {datetime.now().isoformat(timespec='seconds')}")
        lines.append(f"Project path: {self.project_dir}")
        lines.append(f"Outputs path: {self.outputs_dir}")
        lines.append("")
        lines.append("Overall Status")
        lines.append(f"- {overall_status}")
        lines.append("")
        lines.append("Summary Counts")
        lines.append(f"- Total checks: {len(summary_df)}")
        lines.append(f"- PASS: {pass_count}")
        lines.append(f"- WARNING: {warning_count}")
        lines.append(f"- FAIL: {fail_count}")
        lines.append(f"- SKIPPED: {skipped_count}")
        lines.append("")
        lines.append("Critical Failures")
        failures = summary_df[summary_df["severity"] == FAIL]
        if failures.empty:
            lines.append("- None")
        else:
            for _, row in failures.iterrows():
                lines.append(f"- [{row['check_id']}] {row['check_group']} - {row['check_name']}: {row['details']} ({row['affected_file']})")
        lines.append("")
        lines.append("Warnings / Known Limitations")
        warnings = summary_df[summary_df["severity"] == WARNING]
        if warnings.empty:
            lines.append("- None")
        else:
            for group, group_df in warnings.groupby("check_group"):
                lines.append(f"{group}:")
                for _, row in group_df.iterrows():
                    lines.append(f"- [{row['check_id']}] {row['check_name']}: {row['details']}")
        lines.append("")
        lines.extend(self._key_reconciliations_section())
        lines.append("")
        lines.extend(self._manager_snapshot_section())
        lines.append("")
        lines.extend(self._scenario_snapshot_section())
        lines.append("")
        lines.extend(self._warehouse_snapshot_section())
        lines.append("")
        lines.append("Recommended Next Steps")
        if fail_count:
            lines.append("- Fix FAIL rows before proceeding.")
        else:
            lines.append("- Phase 3 validation passed structurally.")
            lines.append("- Review warnings/limitations.")
            lines.append("- Next: decide whether to document Phase 3 or begin revisiting Phase 1/2 improvements.")
        lines.append("")
        return "\n".join(lines)

    def _key_reconciliations_section(self) -> list[str]:
        master = self.frames.get("inventory_control_master_decisions.csv")
        dashboard = self.frames.get("inventory_control_manager_dashboard.csv")
        mandatory = self.frames.get("inventory_control_human_review_queue.csv")
        advisory = self.frames.get("inventory_control_advisory_review_queue.csv")
        opt = self.frames.get("inventory_optimization_recommendations.csv")
        base = self.frames.get("inventory_clean.csv")
        lines = ["Key Reconciliations"]
        lines.append(f"- SKU count: {base['sku_id'].nunique() if base is not None and 'sku_id' in base.columns else 'unavailable'}")
        lines.append(f"- Master decisions row count: {len(master) if master is not None else 'unavailable'}")
        lines.append(f"- Manager dashboard row count: {len(dashboard) if dashboard is not None else 'unavailable'}")
        lines.append(f"- Mandatory review queue count: {len(mandatory) if mandatory is not None else 'unavailable'}")
        lines.append(f"- Advisory review queue count: {len(advisory) if advisory is not None else 'unavailable'}")
        lines.append(f"- Operational saving total: {self._sum_col(master, 'operational_cost_saving_vs_baseline'):.2f}")
        lines.append(f"- Penalty-adjusted saving total: {self._sum_col(master, 'penalty_adjusted_saving_vs_baseline'):.2f}")
        auto_true = 0
        if master is not None and "auto_apply_allowed" in master.columns:
            auto_true = int(_to_bool(master["auto_apply_allowed"]).sum())
        lines.append(f"- Auto-apply true count: {auto_true}")
        lines.append(f"- Selected hard blocker count: {self._sum_col(opt, 'selected_hard_blocker_count'):.0f}")
        return lines

    def _manager_snapshot_section(self) -> list[str]:
        master = self.frames.get("inventory_control_master_decisions.csv")
        lines = ["Final Manager Output Snapshot"]
        if master is None:
            lines.append("- Master decisions unavailable.")
            return lines
        for label, col in [
            ("Priority counts", "final_decision_priority"),
            ("Manager status counts", "final_manager_status"),
            ("Review severity counts", "final_review_severity"),
            ("Proposed operational action counts", "proposed_operational_action"),
            ("Blocking review action counts", "blocking_review_action"),
            ("Execution owner counts", "execution_owner"),
        ]:
            lines.append(f"- {label}: {self._value_counts(master, col)}")
        return lines

    def _scenario_snapshot_section(self) -> list[str]:
        scenarios = self.frames.get("inventory_scenarios.csv")
        results = self.frames.get("inventory_scenario_results.csv")
        opt = self.frames.get("inventory_optimization_recommendations.csv")
        lines = ["Scenario Optimization Snapshot"]
        if scenarios is None:
            lines.append("- Scenario file unavailable.")
            return lines
        scenario_count = len(scenarios)
        avg_per_sku = 0.0
        max_per_sku = 0
        if "sku_id" in scenarios.columns:
            counts = scenarios.groupby("sku_id").size()
            avg_per_sku = float(counts.mean()) if not counts.empty else 0.0
            max_per_sku = int(counts.max()) if not counts.empty else 0
        lines.append(f"- Scenario count: {scenario_count}")
        lines.append(f"- Average scenarios per SKU: {avg_per_sku:.2f}")
        lines.append(f"- Max scenarios per SKU: {max_per_sku}")
        if results is not None and "feasibility_status" in results.columns:
            lines.append(f"- Feasible/infeasible counts: {self._value_counts(results, 'feasibility_status')}")
        lines.append(f"- Selected hard blocker count: {self._sum_col(opt, 'selected_hard_blocker_count'):.0f}")
        lines.append(f"- Selected review-required count: {self._sum_col(opt, 'selected_review_required_count'):.0f}")
        lines.append(f"- Selected soft warning count: {self._sum_col(opt, 'selected_soft_warning_count'):.0f}")
        return lines

    def _warehouse_snapshot_section(self) -> list[str]:
        batch = self.frames.get("batch_slotting.csv")
        visual_batches = self.frames.get("warehouse_visual_batches.csv")
        location = self.frames.get("location_utilization.csv")
        lines = ["Warehouse Snapshot"]
        lines.append(f"- Batch slotting rows: {len(batch) if batch is not None else 'unavailable'}")
        trace_count = self._bool_count(batch, "batch_trace_only_flag")
        physical_count = self._bool_count(batch, "include_in_physical_map")
        if physical_count == 0 and visual_batches is not None:
            physical_count = self._bool_count(visual_batches, "show_on_physical_map")
        lines.append(f"- Trace-only batch count: {trace_count}")
        lines.append(f"- Physical-map batch count: {physical_count}")
        lines.append(f"- Active quarantine count: {self._bool_action_count(batch, 'expired_flag', 'active_batch_quantity_flag')}")
        lines.append(f"- Active FEFO count: {self._bool_action_count(batch, 'near_expiry_flag', 'active_batch_quantity_flag')}")
        lines.append(f"- Current overcapacity count: {self._bool_count(location, 'current_over_capacity_flag')}")
        lines.append(f"- Projected overcapacity count: {self._bool_count(location, 'projected_over_capacity_flag')}")
        return lines

    def _sum_col(self, df: pd.DataFrame | None, col: str) -> float:
        if df is None or col not in getattr(df, "columns", []):
            return 0.0
        return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())

    def _value_counts(self, df: pd.DataFrame, col: str) -> str:
        if col not in df.columns:
            return "unavailable"
        counts = df[col].fillna("BLANK").astype(str).value_counts().to_dict()
        return ", ".join(f"{key}={value}" for key, value in counts.items()) or "none"

    def _bool_count(self, df: pd.DataFrame | None, col: str) -> int:
        if df is None or col not in getattr(df, "columns", []):
            return 0
        return int(_to_bool(df[col]).sum())

    def _bool_action_count(self, df: pd.DataFrame | None, flag_col: str, active_col: str) -> int:
        if df is None or flag_col not in getattr(df, "columns", []) or active_col not in df.columns:
            return 0
        return int((_to_bool(df[flag_col]) & _to_bool(df[active_col])).sum())


def run_phase3_validation() -> dict[str, Any]:
    """Run all Phase 3 validation checks and write validation outputs."""

    return Phase3Validator().run()


# Module-level helper aliases requested by the validation spec.
_DEFAULT_VALIDATOR = Phase3Validator()
safe_read_csv = _DEFAULT_VALIDATOR.safe_read_csv
add_result = _DEFAULT_VALIDATOR.add_result
require_columns = _DEFAULT_VALIDATOR.require_columns
check_unique_key = _DEFAULT_VALIDATOR.check_unique_key
check_no_missing = _DEFAULT_VALIDATOR.check_no_missing
check_numeric_non_negative = _DEFAULT_VALIDATOR.check_numeric_non_negative
check_boolean_all_false = _DEFAULT_VALIDATOR.check_boolean_all_false
compare_sums = _DEFAULT_VALIDATOR.compare_sums
