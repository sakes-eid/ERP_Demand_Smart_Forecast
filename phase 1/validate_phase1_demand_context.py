"""Validate the Phase 1 downstream demand planning context output."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from config import MODEL_PERSISTENCE_CONFIG, OUTPUT_DIR
from core.demand_planning_context import REQUIRED_OUTPUT_COLUMNS


OUTPUT_FILE = OUTPUT_DIR / "phase1_demand_planning_context.csv"
FUTURE_FORECAST_FILE = OUTPUT_DIR / "future_forecast_results.csv"
FORECAST_KPI_FILE = OUTPUT_DIR / "phase1_forecast_kpis.csv"
PRODUCTS_FILE = OUTPUT_DIR / "products_cleaned.csv"
MODEL_REGISTRY_FILE = OUTPUT_DIR / "model_registry.csv"
MODEL_OUTPUT_DIR = MODEL_PERSISTENCE_CONFIG["model_output_dir"]
REPORT_FILE = OUTPUT_DIR / "phase1_demand_context_validation_report.txt"
SUMMARY_FILE = OUTPUT_DIR / "phase1_demand_context_validation_summary.csv"

VALID_CENSOR_CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "NONE"}


class Validator:
    """Collect validation checks for the Phase 1 demand context output."""

    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []
        self.index = 1

    def add(self, group: str, name: str, severity: str, details: str, file_name: str = "", column: str = "", rows: int | str = "") -> None:
        self.results.append(
            {
                "check_id": f"P1CTX-{self.index:03d}",
                "check_group": group,
                "check_name": name,
                "severity": severity,
                "details": details,
                "affected_file": file_name,
                "affected_column": column,
                "affected_rows": rows,
            }
        )
        self.index += 1

    def run(self) -> dict[str, Any]:
        context = self._load_context()
        future = self._load_future_forecasts()
        forecast_kpis = self._load_forecast_kpis()
        products = self._load_products()
        registry = self._load_model_registry()
        self._check_model_persistence(registry)
        if future is not None:
            self._check_future_forecast_columns(future)
            self._check_future_forecast_rows(future, products)
            self._check_future_horizon_coverage(future)
            self._check_future_dates(future)
            self._check_future_numeric_values(future)
            self._check_future_intervals(future)
            self._known_future_warnings(future)
        if context is not None:
            self._check_columns(context)
            self._check_one_row_per_sku(context, products)
            self._check_missing_sku(context)
            self._check_non_negative(context)
            self._check_ranges(context)
            self._check_censor_confidence(context)
            self._check_warning_codes(context)
            self._check_context_uses_future_forecasts(context, future)
            self._check_context_forecast_kpis(context)
            self._known_warnings(context)
        if forecast_kpis is not None:
            self._check_forecast_kpi_columns(forecast_kpis)
            self._check_forecast_kpi_bounds(forecast_kpis)
            self._check_forecast_stability_snapshot_integrity(forecast_kpis)
            self._known_forecast_kpi_warnings(forecast_kpis)
        return self._write_outputs()

    def _load_context(self) -> pd.DataFrame | None:
        if not OUTPUT_FILE.exists():
            self.add("FILE", "Demand planning context exists", "FAIL", "phase1_demand_planning_context.csv is missing.", OUTPUT_FILE.name)
            return None
        try:
            df = pd.read_csv(OUTPUT_FILE)
        except Exception as exc:  # pragma: no cover - defensive file handling
            self.add("FILE", "Demand planning context loads", "FAIL", f"CSV could not be parsed: {exc}", OUTPUT_FILE.name)
            return None
        self.add("FILE", "Demand planning context loads", "PASS", f"Loaded {len(df)} rows.", OUTPUT_FILE.name)
        return df

    def _load_future_forecasts(self) -> pd.DataFrame | None:
        if not FUTURE_FORECAST_FILE.exists():
            self.add("FILE", "Future forecast output exists", "FAIL", "future_forecast_results.csv is missing.", FUTURE_FORECAST_FILE.name)
            return None
        try:
            df = pd.read_csv(FUTURE_FORECAST_FILE)
        except Exception as exc:  # pragma: no cover - defensive file handling
            self.add("FILE", "Future forecast output loads", "FAIL", f"CSV could not be parsed: {exc}", FUTURE_FORECAST_FILE.name)
            return None
        self.add("FILE", "Future forecast output loads", "PASS", f"Loaded {len(df)} rows.", FUTURE_FORECAST_FILE.name)
        return df

    def _load_forecast_kpis(self) -> pd.DataFrame | None:
        if not FORECAST_KPI_FILE.exists():
            self.add("FILE", "Forecast KPI output exists", "FAIL", "phase1_forecast_kpis.csv is missing.", FORECAST_KPI_FILE.name)
            return None
        try:
            df = pd.read_csv(FORECAST_KPI_FILE)
        except Exception as exc:
            self.add("FILE", "Forecast KPI output loads", "FAIL", f"CSV could not be parsed: {exc}", FORECAST_KPI_FILE.name)
            return None
        self.add("FILE", "Forecast KPI output loads", "PASS", f"Loaded {len(df)} rows.", FORECAST_KPI_FILE.name)
        return df

    def _load_products(self) -> pd.DataFrame | None:
        if not PRODUCTS_FILE.exists():
            self.add("FILE", "Products output exists", "WARNING", "products_cleaned.csv missing; row count comparison skipped.", PRODUCTS_FILE.name)
            return None
        return pd.read_csv(PRODUCTS_FILE)

    def _load_model_registry(self) -> pd.DataFrame | None:
        if not MODEL_REGISTRY_FILE.exists():
            self.add("FILE", "Model registry exists", "FAIL", "model_registry.csv is missing.", MODEL_REGISTRY_FILE.name)
            return None
        return pd.read_csv(MODEL_REGISTRY_FILE)

    def _check_model_persistence(self, registry: pd.DataFrame | None) -> None:
        if not MODEL_PERSISTENCE_CONFIG["enabled"]:
            self.add("MODEL_PERSISTENCE", "Model persistence enabled", "WARNING", "Model persistence is disabled in config.")
            return
        self.add(
            "MODEL_PERSISTENCE",
            "Model output folder exists",
            "PASS" if MODEL_OUTPUT_DIR.exists() else "FAIL",
            f"Folder: {MODEL_OUTPUT_DIR}",
            str(MODEL_OUTPUT_DIR),
        )
        if registry is None:
            return
        required = [
            "model_persisted_flag",
            "model_artifact_path",
            "model_metadata_path",
            "future_forecast_reusable_flag",
            "future_forecast_reuse_reason",
        ]
        missing = [column for column in required if column not in registry.columns]
        self.add(
            "MODEL_PERSISTENCE",
            "Model registry persistence columns exist",
            "PASS" if not missing else "FAIL",
            "All persistence columns present." if not missing else f"Missing columns: {'; '.join(missing)}",
            MODEL_REGISTRY_FILE.name,
            "; ".join(missing),
            len(missing),
        )
        if missing:
            return
        persisted = registry["model_persisted_flag"].astype(str).str.lower().isin({"true", "1", "yes"})
        missing_artifacts = 0
        for row in registry.loc[persisted].to_dict("records"):
            if not Path(str(row.get("model_artifact_path", ""))).exists():
                missing_artifacts += 1
            if not Path(str(row.get("model_metadata_path", ""))).exists():
                missing_artifacts += 1
        self.add(
            "MODEL_PERSISTENCE",
            "Persisted model artifacts exist",
            "PASS" if missing_artifacts == 0 else "FAIL",
            f"Persisted models={int(persisted.sum())}; missing artifact/metadata paths={missing_artifacts}.",
            MODEL_REGISTRY_FILE.name,
            "model_artifact_path; model_metadata_path",
            missing_artifacts,
        )

    def _check_columns(self, context: pd.DataFrame) -> None:
        missing = [column for column in REQUIRED_OUTPUT_COLUMNS if column not in context.columns]
        if missing:
            self.add("SCHEMA", "Required columns exist", "FAIL", f"Missing columns: {'; '.join(missing)}", OUTPUT_FILE.name, "; ".join(missing), len(missing))
        else:
            self.add("SCHEMA", "Required columns exist", "PASS", "All required columns are present.", OUTPUT_FILE.name)

    def _check_future_forecast_columns(self, future: pd.DataFrame) -> None:
        required = [
            "sku_id",
            "forecast_date",
            "horizon_day",
            "champion_model",
            "forecast_quantity",
            "p10",
            "p50",
            "p90",
            "forecast_generation_method",
            "interval_generation_method",
            "future_forecast_warning_codes",
        ]
        missing = [column for column in required if column not in future.columns]
        self.add(
            "FUTURE_FORECAST",
            "Future forecast required columns exist",
            "PASS" if not missing else "FAIL",
            "All required columns are present." if not missing else f"Missing columns: {'; '.join(missing)}",
            FUTURE_FORECAST_FILE.name,
            "; ".join(missing),
            len(missing),
        )

    def _check_future_forecast_rows(self, future: pd.DataFrame, products: pd.DataFrame | None) -> None:
        if products is None or "sku_id" not in products.columns or "sku_id" not in future.columns:
            self.add("FUTURE_FORECAST", "Future forecast expected row count", "WARNING", "Products or sku_id unavailable; exact row count skipped.", FUTURE_FORECAST_FILE.name)
            return
        sku_count = products["sku_id"].nunique()
        expected = sku_count * 90
        status = "PASS" if len(future) == expected else "FAIL"
        self.add("FUTURE_FORECAST", "Future forecast expected row count", status, f"Rows={len(future)}, expected={expected}.", FUTURE_FORECAST_FILE.name, rows=abs(len(future) - expected))

    def _check_future_horizon_coverage(self, future: pd.DataFrame) -> None:
        if "sku_id" not in future.columns or "horizon_day" not in future.columns:
            self.add("FUTURE_FORECAST", "Each SKU has horizon days 1 to 90", "FAIL", "sku_id or horizon_day missing.", FUTURE_FORECAST_FILE.name)
            return
        bad_skus = 0
        expected = set(range(1, 91))
        for _, sku_rows in future.groupby("sku_id"):
            horizons = set(pd.to_numeric(sku_rows["horizon_day"], errors="coerce").dropna().astype(int))
            if horizons != expected:
                bad_skus += 1
        self.add("FUTURE_FORECAST", "Each SKU has horizon days 1 to 90", "PASS" if bad_skus == 0 else "FAIL", f"SKUs with incomplete horizon coverage: {bad_skus}.", FUTURE_FORECAST_FILE.name, "horizon_day", bad_skus)

    def _check_future_dates(self, future: pd.DataFrame) -> None:
        if "forecast_date" not in future.columns or "horizon_day" not in future.columns:
            self.add("FUTURE_FORECAST", "Future forecast dates are future-only", "FAIL", "forecast_date or horizon_day missing.", FUTURE_FORECAST_FILE.name)
            return
        dates = pd.to_datetime(future["forecast_date"], errors="coerce")
        horizons = pd.to_numeric(future["horizon_day"], errors="coerce")
        invalid = int((dates.isna() | horizons.isna() | (horizons < 1)).sum())
        self.add("FUTURE_FORECAST", "Future forecast dates are future-only", "PASS" if invalid == 0 else "FAIL", f"Invalid date/horizon rows: {invalid}.", FUTURE_FORECAST_FILE.name, "forecast_date; horizon_day", invalid)

    def _check_future_numeric_values(self, future: pd.DataFrame) -> None:
        columns = ["forecast_quantity", "p10", "p50", "p90"]
        bad = 0
        for column in columns:
            if column not in future.columns:
                bad += len(future)
                continue
            values = pd.to_numeric(future[column], errors="coerce")
            bad += int((values.isna() | (values < 0)).sum())
        self.add("FUTURE_FORECAST", "Future forecast numeric values are non-negative", "PASS" if bad == 0 else "FAIL", f"Invalid numeric rows: {bad}.", FUTURE_FORECAST_FILE.name, "; ".join(columns), bad)

    def _check_future_intervals(self, future: pd.DataFrame) -> None:
        required = ["forecast_quantity", "p10", "p50", "p90"]
        if not all(column in future.columns for column in required):
            self.add("FUTURE_FORECAST", "Future forecast intervals are ordered", "FAIL", "Interval columns missing.", FUTURE_FORECAST_FILE.name, "; ".join(required))
            return
        p10 = pd.to_numeric(future["p10"], errors="coerce")
        p50 = pd.to_numeric(future["p50"], errors="coerce")
        p90 = pd.to_numeric(future["p90"], errors="coerce")
        forecast = pd.to_numeric(future["forecast_quantity"], errors="coerce")
        bad_order = int(((p10 > p50) | (p50 > p90)).sum())
        bad_p50 = int(((p50 - forecast).abs() > 0.01).sum())
        severity = "PASS" if bad_order == 0 and bad_p50 == 0 else "FAIL"
        self.add("FUTURE_FORECAST", "Future forecast intervals are ordered", severity, f"Bad interval rows={bad_order}; p50 mismatch rows={bad_p50}.", FUTURE_FORECAST_FILE.name, "; ".join(required), bad_order + bad_p50)

    def _check_one_row_per_sku(self, context: pd.DataFrame, products: pd.DataFrame | None) -> None:
        if "sku_id" not in context.columns:
            self.add("ROW_COUNT", "One row per SKU", "FAIL", "sku_id column is missing.", OUTPUT_FILE.name, "sku_id")
            return
        duplicate_count = int(context["sku_id"].astype(str).duplicated().sum())
        if products is not None and "sku_id" in products.columns:
            product_count = products["sku_id"].nunique()
            context_count = context["sku_id"].nunique()
            if len(context) == product_count and context_count == product_count and duplicate_count == 0:
                self.add("ROW_COUNT", "One row per SKU", "PASS", f"Rows and unique SKU count match products: {product_count}.", OUTPUT_FILE.name, "sku_id")
            else:
                self.add("ROW_COUNT", "One row per SKU", "FAIL", f"Rows={len(context)}, unique_skus={context_count}, product_skus={product_count}, duplicates={duplicate_count}.", OUTPUT_FILE.name, "sku_id")
        elif duplicate_count:
            self.add("ROW_COUNT", "One row per SKU", "FAIL", f"Duplicate SKU rows: {duplicate_count}.", OUTPUT_FILE.name, "sku_id", duplicate_count)
        else:
            self.add("ROW_COUNT", "One row per SKU", "WARNING", "Products file unavailable; duplicate SKU check passed only.", OUTPUT_FILE.name, "sku_id")

    def _check_missing_sku(self, context: pd.DataFrame) -> None:
        missing = int(context["sku_id"].isna().sum() + context["sku_id"].astype(str).str.strip().eq("").sum()) if "sku_id" in context.columns else len(context)
        self.add("QUALITY", "No missing sku_id", "PASS" if missing == 0 else "FAIL", f"Missing sku_id rows: {missing}.", OUTPUT_FILE.name, "sku_id", missing)

    def _check_non_negative(self, context: pd.DataFrame) -> None:
        columns = [
            "forecast_demand_7d",
            "forecast_demand_14d",
            "forecast_demand_30d",
            "forecast_demand_60d",
            "forecast_demand_90d",
            "forecast_uncertainty_ratio_30d",
        ]
        bad = 0
        checked = []
        for column in columns:
            if column not in context.columns:
                continue
            values = pd.to_numeric(context[column], errors="coerce")
            bad += int((values < 0).sum())
            checked.append(column)
        self.add("NUMERIC", "Forecast horizon and uncertainty fields are non-negative", "PASS" if bad == 0 else "FAIL", f"Checked columns: {'; '.join(checked)}. Invalid rows: {bad}.", OUTPUT_FILE.name, "; ".join(checked), bad)

    def _check_ranges(self, context: pd.DataFrame) -> None:
        range_columns = ["model_confidence_score", "demand_data_quality_score"]
        for column in range_columns:
            if column not in context.columns:
                self.add("NUMERIC", f"{column} range", "FAIL", "Column is missing.", OUTPUT_FILE.name, column)
                continue
            values = pd.to_numeric(context[column], errors="coerce")
            bad = int((values.isna() | (values < 0) | (values > 1)).sum())
            self.add("NUMERIC", f"{column} range", "PASS" if bad == 0 else "FAIL", f"Values outside [0, 1] or missing: {bad}.", OUTPUT_FILE.name, column, bad)

    def _check_censor_confidence(self, context: pd.DataFrame) -> None:
        column = "stockout_censor_confidence"
        if column not in context.columns:
            self.add("CENSORING", "Stockout censor confidence values", "FAIL", "Column is missing.", OUTPUT_FILE.name, column)
            return
        invalid = int((~context[column].astype(str).isin(VALID_CENSOR_CONFIDENCE)).sum())
        self.add("CENSORING", "Stockout censor confidence values", "PASS" if invalid == 0 else "FAIL", f"Invalid rows: {invalid}.", OUTPUT_FILE.name, column, invalid)

    def _check_warning_codes(self, context: pd.DataFrame) -> None:
        column = "demand_planning_warning_codes"
        if column not in context.columns:
            self.add("WARNINGS", "Warning code field exists", "FAIL", "Warning code field is missing.", OUTPUT_FILE.name, column)
            return
        missing = int(context[column].isna().sum())
        self.add("WARNINGS", "Warning code field is safe", "PASS" if missing == 0 else "WARNING", f"Null warning-code cells: {missing}. Blank strings are acceptable.", OUTPUT_FILE.name, column, missing)

    def _check_context_uses_future_forecasts(self, context: pd.DataFrame, future: pd.DataFrame | None) -> None:
        warning_text = ";".join(context.get("demand_planning_warning_codes", pd.Series(dtype=str)).fillna("").astype(str))
        approximated_count = warning_text.count("FORECAST_HORIZON_APPROXIMATED")
        true_future_count = warning_text.count("FORECAST_HORIZON_FROM_TRUE_FUTURE_FORECAST")
        future_complete = future is not None and len(future) >= max(context["sku_id"].nunique() * 90, 1)
        if future_complete and approximated_count:
            self.add("CONTEXT", "Demand context uses true future forecasts", "FAIL", f"FORECAST_HORIZON_APPROXIMATED still appears {approximated_count} times.", OUTPUT_FILE.name, "demand_planning_warning_codes", approximated_count)
        elif future_complete and true_future_count < context["sku_id"].nunique():
            self.add("CONTEXT", "Demand context uses true future forecasts", "FAIL", f"True future forecast marker appears {true_future_count} times for {context['sku_id'].nunique()} SKUs.", OUTPUT_FILE.name, "demand_planning_warning_codes", context["sku_id"].nunique() - true_future_count)
        else:
            self.add("CONTEXT", "Demand context uses true future forecasts", "PASS", f"True future marker count={true_future_count}; old approximation count={approximated_count}.", OUTPUT_FILE.name, "demand_planning_warning_codes")

    def _check_context_forecast_kpis(self, context: pd.DataFrame) -> None:
        required = [
            "forecast_value_added_status",
            "forecast_wape_7d",
            "forecast_wape_30d",
            "forecast_wape_90d",
            "prediction_interval_coverage_rate",
            "forecast_stability_status",
        ]
        missing = [column for column in required if column not in context.columns]
        self.add(
            "FORECAST_KPIS",
            "Demand context includes concise forecast KPI fields",
            "PASS" if not missing else "FAIL",
            "Forecast KPI fields are present." if not missing else f"Missing fields: {'; '.join(missing)}",
            OUTPUT_FILE.name,
            "; ".join(missing),
            len(missing),
        )

    def _check_forecast_kpi_columns(self, forecast_kpis: pd.DataFrame) -> None:
        required = [
            "sku_id",
            "forecast_value_added",
            "forecast_value_added_pct",
            "forecast_value_added_status",
            "forecast_wape_7d",
            "forecast_wape_30d",
            "forecast_wape_90d",
            "prediction_interval_coverage_rate",
            "prediction_interval_eligible_observations",
            "prediction_interval_calibration_status",
            "forecast_stability_pct",
            "forecast_stability_status",
            "previous_forecast_available_flag",
            "forecast_stability_method",
            "current_forecast_snapshot_id",
            "previous_forecast_snapshot_id",
            "forecast_stability_comparable_row_count",
        ]
        missing = [column for column in required if column not in forecast_kpis.columns]
        self.add(
            "FORECAST_KPIS",
            "Forecast KPI required columns exist",
            "PASS" if not missing else "FAIL",
            "All required KPI columns are present." if not missing else f"Missing columns: {'; '.join(missing)}",
            FORECAST_KPI_FILE.name,
            "; ".join(missing),
            len(missing),
        )

    def _check_forecast_kpi_bounds(self, forecast_kpis: pd.DataFrame) -> None:
        bounded = [
            "forecast_value_added_pct",
            "forecast_wape_7d",
            "forecast_wape_30d",
            "forecast_wape_90d",
            "prediction_interval_coverage_rate",
            "forecast_stability_pct",
        ]
        bad = 0
        for column in bounded:
            if column not in forecast_kpis.columns:
                continue
            values = pd.to_numeric(forecast_kpis[column], errors="coerce")
            if column == "forecast_value_added_pct":
                bad += int((values.dropna() < -10).sum())
            else:
                bad += int((values.dropna() < 0).sum())
        valid_statuses = {"POSITIVE", "NEUTRAL", "NEGATIVE", "UNAVAILABLE"}
        invalid_status = 0
        if "forecast_value_added_status" in forecast_kpis.columns:
            invalid_status = int((~forecast_kpis["forecast_value_added_status"].astype(str).isin(valid_statuses)).sum())
        self.add(
            "FORECAST_KPIS",
            "Forecast KPI bounds and statuses",
            "PASS" if bad == 0 and invalid_status == 0 else "FAIL",
            f"Negative/out-of-range KPI values={bad}; invalid FVA statuses={invalid_status}.",
            FORECAST_KPI_FILE.name,
            "; ".join(bounded),
            bad + invalid_status,
        )

    def _check_forecast_stability_snapshot_integrity(self, forecast_kpis: pd.DataFrame) -> None:
        required = {
            "forecast_stability_status",
            "forecast_stability_method",
            "current_forecast_snapshot_id",
            "previous_forecast_snapshot_id",
            "forecast_stability_comparable_row_count",
        }
        if not required.issubset(forecast_kpis.columns):
            self.add(
                "FORECAST_KPIS",
                "Forecast stability uses distinct forecast snapshots",
                "FAIL",
                f"Missing stability integrity fields: {'; '.join(sorted(required - set(forecast_kpis.columns)))}",
                FORECAST_KPI_FILE.name,
                affected_rows=len(forecast_kpis),
            )
            return
        status = forecast_kpis["forecast_stability_status"].fillna("").astype(str)
        available = status.isin({"STABLE", "MODERATE_CHANGE", "MATERIAL_CHANGE"})
        current = forecast_kpis["current_forecast_snapshot_id"].fillna("").astype(str)
        previous = forecast_kpis["previous_forecast_snapshot_id"].fillna("").astype(str)
        method = forecast_kpis["forecast_stability_method"].fillna("").astype(str)
        comparable_rows = pd.to_numeric(forecast_kpis["forecast_stability_comparable_row_count"], errors="coerce").fillna(0)
        bad_available = available & (
            current.eq("")
            | previous.eq("")
            | current.eq(previous)
            | method.ne("FORECAST_QUANTITY_VECTOR_CHANGE_BY_SKU_AND_TARGET_DATE")
            | (comparable_rows <= 0)
        )
        unavailable_with_fake_stable = status.eq("STABLE") & comparable_rows.eq(0)
        failures = int((bad_available | unavailable_with_fake_stable).sum())
        self.add(
            "FORECAST_KPIS",
            "Forecast stability uses distinct forecast quantity vectors",
            "PASS" if failures == 0 else "FAIL",
            f"Available stability rows with missing/distinctness/method issues={failures}.",
            FORECAST_KPI_FILE.name,
            "forecast_stability_*",
            failures,
        )

    def _known_forecast_kpi_warnings(self, forecast_kpis: pd.DataFrame) -> None:
        warning_text = ";".join(forecast_kpis.get("forecast_kpi_warning_codes", pd.Series(dtype=str)).fillna("").astype(str))
        for code, message in {
            "FORECAST_WAPE_90D_UNAVAILABLE": "90-day backtest WAPE is unavailable because the current comparable backtest window is shorter than 90 days.",
            "FORECAST_STABILITY_UNAVAILABLE_NO_COMPARABLE_PRIOR_RUN": "Forecast stability requires a distinct prior future-forecast snapshot and compares forecast quantities, not error metrics.",
            "PREDICTION_INTERVAL_COVERAGE_INSUFFICIENT_DATA": "Prediction interval coverage has insufficient eligible observations for some SKUs.",
        }.items():
            if code in warning_text:
                self.add("KNOWN_WARNINGS", code, "WARNING", message, FORECAST_KPI_FILE.name, "forecast_kpi_warning_codes")

    def _known_warnings(self, context: pd.DataFrame) -> None:
        warning_text = ";".join(context.get("demand_planning_warning_codes", pd.Series(dtype=str)).fillna("").astype(str))
        for code, message in {
            "FORECAST_BIAS_UNAVAILABLE": "Forecast bias unavailable for some SKUs.",
            "EVENT_UPLIFT_UNKNOWN": "Event uplift is unknown for some future events.",
            "INSUFFICIENT_HISTORY_FOR_SEASONALITY": "Seasonality unavailable for some SKUs due to insufficient history.",
            "FORECAST_HORIZON_APPROXIMATED": "Forecast horizons are approximated from current Phase 1 forecast outputs.",
        }.items():
            if code in warning_text:
                self.add("KNOWN_WARNINGS", code, "WARNING", message, OUTPUT_FILE.name, "demand_planning_warning_codes")

    def _known_future_warnings(self, future: pd.DataFrame) -> None:
        warning_text = ";".join(future.get("future_forecast_warning_codes", pd.Series(dtype=str)).fillna("").astype(str))
        for code, message in {
            "CHAMPION_MODEL_NOT_REUSABLE_FOR_FUTURE": "Advanced champion model objects are not persisted; fallback forecast generation was used.",
            "FUTURE_MODEL_FALLBACK_USED": "Transparent statistical fallback was used for some future forecasts.",
            "FUTURE_INTERVAL_APPROXIMATED": "Future interval was approximated because champion residuals were unavailable.",
            "FUTURE_EVENT_UPLIFT_UNKNOWN": "Future event uplift was unavailable and left neutral.",
        }.items():
            if code in warning_text:
                self.add("KNOWN_WARNINGS", code, "WARNING", message, FUTURE_FORECAST_FILE.name, "future_forecast_warning_codes")

    def _write_outputs(self) -> dict[str, Any]:
        summary = pd.DataFrame(self.results)
        SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
        summary.to_csv(SUMMARY_FILE, index=False)
        fail_count = int((summary["severity"] == "FAIL").sum()) if not summary.empty else 0
        warning_count = int((summary["severity"] == "WARNING").sum()) if not summary.empty else 0
        pass_count = int((summary["severity"] == "PASS").sum()) if not summary.empty else 0
        overall = "FAIL" if fail_count else ("WARNING" if warning_count else "PASS")
        lines = [
            "Phase 1 Demand Planning Context Validation",
            "=" * 43,
            f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
            f"Output file: {OUTPUT_FILE}",
            f"Overall status: {overall}",
            f"PASS: {pass_count}",
            f"WARNING: {warning_count}",
            f"FAIL: {fail_count}",
            "",
            "Issues:",
        ]
        issues = summary[summary["severity"].isin(["WARNING", "FAIL"])]
        if issues.empty:
            lines.append("- None")
        else:
            for row in issues.to_dict("records"):
                lines.append(f"- {row['severity']} [{row['check_id']}] {row['check_name']}: {row['details']}")
        REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {
            "overall_status": overall,
            "pass_count": pass_count,
            "warning_count": warning_count,
            "fail_count": fail_count,
            "report_path": REPORT_FILE,
            "summary_path": SUMMARY_FILE,
        }


if __name__ == "__main__":
    result = Validator().run()
    print(f"Validation report: {result['report_path']}")
    print(f"Validation summary: {result['summary_path']}")
    print(f"Overall status: {result['overall_status']}")
    print(f"PASS: {result['pass_count']}")
    print(f"WARNING: {result['warning_count']}")
    print(f"FAIL: {result['fail_count']}")
