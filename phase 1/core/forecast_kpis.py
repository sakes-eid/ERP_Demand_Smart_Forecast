"""Focused forecast KPI calculations for Phase 1 demand planning."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


BASELINE_MODEL_PRIORITY = ["seasonal_naive_7", "naive"]
HORIZON_WINDOWS = [7, 30, 90]


def build_forecast_kpis(
    forecast_results: pd.DataFrame,
    future_forecast_results: pd.DataFrame,
    model_performance: pd.DataFrame,
    model_registry: pd.DataFrame,
    output_dir: Path,
    run_started_at: datetime | None = None,
) -> pd.DataFrame:
    """Build one concise forecast KPI row per SKU."""
    if model_registry.empty or "sku_id" not in model_registry.columns:
        return pd.DataFrame()
    run_started_at = run_started_at or datetime.now()
    previous_future, previous_snapshot_id = _load_previous_future_forecasts(output_dir, run_started_at)
    current_snapshot_id = run_started_at.isoformat(timespec="seconds")
    rows = []
    for _, reg in model_registry.iterrows():
        sku_id = str(reg.get("sku_id", "")).strip()
        champion = str(reg.get("champion_model", "")).strip()
        perf = model_performance[model_performance["sku_id"].astype(str).str.strip().eq(sku_id)].copy() if not model_performance.empty else pd.DataFrame()
        forecasts = forecast_results[forecast_results["sku_id"].astype(str).str.strip().eq(sku_id)].copy() if not forecast_results.empty else pd.DataFrame()
        baseline_model = _select_baseline_model(perf, champion)
        champion_error = _metric_for_model(perf, champion, "wape")
        baseline_error = _metric_for_model(perf, baseline_model, "wape") if baseline_model else pd.NA
        fva, fva_pct, fva_status = _forecast_value_added(champion_error, baseline_error)
        horizon = _horizon_wape(forecasts, champion)
        coverage = _prediction_interval_coverage(forecasts, champion)
        future = (
            future_forecast_results[future_forecast_results["sku_id"].astype(str).str.strip().eq(sku_id)].copy()
            if not future_forecast_results.empty
            else pd.DataFrame()
        )
        stability = _forecast_stability(
            previous_future,
            previous_snapshot_id,
            future,
            sku_id,
            current_snapshot_id,
        )
        rows.append(
            {
                "sku_id": sku_id,
                "champion_model": champion,
                "baseline_model": baseline_model or "",
                "forecast_value_added": fva,
                "forecast_value_added_pct": fva_pct,
                "forecast_value_added_status": fva_status,
                "champion_wape": champion_error,
                "baseline_wape": baseline_error,
                "forecast_wape_7d": horizon["forecast_wape_7d"],
                "forecast_wape_30d": horizon["forecast_wape_30d"],
                "forecast_wape_90d": horizon["forecast_wape_90d"],
                "forecast_wape_7d_available_flag": horizon["forecast_wape_7d_available_flag"],
                "forecast_wape_30d_available_flag": horizon["forecast_wape_30d_available_flag"],
                "forecast_wape_90d_available_flag": horizon["forecast_wape_90d_available_flag"],
                "horizon_accuracy_method": horizon["horizon_accuracy_method"],
                "prediction_interval_coverage_rate": coverage["prediction_interval_coverage_rate"],
                "prediction_interval_eligible_observations": coverage["prediction_interval_eligible_observations"],
                "prediction_interval_calibration_status": coverage["prediction_interval_calibration_status"],
                "forecast_stability_pct": stability["forecast_stability_pct"],
                "forecast_stability_status": stability["forecast_stability_status"],
                "previous_forecast_available_flag": stability["previous_forecast_available_flag"],
                "forecast_stability_method": stability["forecast_stability_method"],
                "current_forecast_snapshot_id": stability["current_forecast_snapshot_id"],
                "previous_forecast_snapshot_id": stability["previous_forecast_snapshot_id"],
                "forecast_stability_comparable_row_count": stability["forecast_stability_comparable_row_count"],
                "forecast_kpi_warning_codes": _warning_codes(fva_status, horizon, coverage, stability),
            }
        )
    return pd.DataFrame(rows)


def _load_previous_future_forecasts(output_dir: Path, run_started_at: datetime) -> tuple[pd.DataFrame, str]:
    path = output_dir / "future_forecast_results.csv"
    if not path.exists():
        return pd.DataFrame(), ""
    modified_at = datetime.fromtimestamp(path.stat().st_mtime)
    if modified_at >= run_started_at:
        return pd.DataFrame(), ""
    try:
        return pd.read_csv(path), modified_at.isoformat(timespec="seconds")
    except Exception:
        return pd.DataFrame(), ""


def _select_baseline_model(perf: pd.DataFrame, champion: str) -> str:
    if perf.empty or "model_name" not in perf.columns:
        return ""
    models = set(perf["model_name"].dropna().astype(str))
    for model in BASELINE_MODEL_PRIORITY:
        if model in models and model != champion:
            return model
    for model in BASELINE_MODEL_PRIORITY:
        if model in models:
            return model
    non_champions = [model for model in sorted(models) if model != champion]
    return non_champions[0] if non_champions else ""


def _metric_for_model(perf: pd.DataFrame, model: str, metric: str):
    if perf.empty or not model or metric not in perf.columns or "model_name" not in perf.columns:
        return pd.NA
    rows = perf[perf["model_name"].astype(str).eq(str(model))]
    if rows.empty:
        return pd.NA
    value = pd.to_numeric(rows.iloc[0][metric], errors="coerce")
    return round(float(value), 6) if pd.notna(value) else pd.NA


def _forecast_value_added(champion_error, baseline_error):
    if pd.isna(champion_error) or pd.isna(baseline_error) or float(baseline_error) <= 0:
        return pd.NA, pd.NA, "UNAVAILABLE"
    value = float(baseline_error) - float(champion_error)
    pct = value / float(baseline_error)
    if abs(pct) <= 0.01:
        status = "NEUTRAL"
    elif pct > 0:
        status = "POSITIVE"
    else:
        status = "NEGATIVE"
    return round(value, 6), round(pct, 6), status


def _horizon_wape(forecasts: pd.DataFrame, champion: str) -> dict:
    result = {
        "horizon_accuracy_method": "BACKTEST_CHAMPION_ROWS",
    }
    if forecasts.empty or "target_date" not in forecasts.columns or "model_name" not in forecasts.columns:
        for window in HORIZON_WINDOWS:
            result[f"forecast_wape_{window}d"] = pd.NA
            result[f"forecast_wape_{window}d_available_flag"] = False
        result["horizon_accuracy_method"] = "UNAVAILABLE_NO_BACKTEST_ROWS"
        return result
    working = forecasts[forecasts["model_name"].astype(str).eq(champion)].copy()
    if working.empty:
        working = forecasts.copy()
        result["horizon_accuracy_method"] = "BACKTEST_ALL_MODELS_FALLBACK"
    working["target_date"] = pd.to_datetime(working["target_date"], errors="coerce")
    working = working.dropna(subset=["target_date"]).sort_values("target_date")
    for window in HORIZON_WINDOWS:
        if len(working) < window:
            result[f"forecast_wape_{window}d"] = pd.NA
            result[f"forecast_wape_{window}d_available_flag"] = False
            continue
        tail = working.tail(window)
        actual = pd.to_numeric(tail.get("actual_demand"), errors="coerce").fillna(0).abs().sum()
        error = pd.to_numeric(tail.get("absolute_error"), errors="coerce").fillna(0).sum()
        if actual <= 0:
            result[f"forecast_wape_{window}d"] = pd.NA
            result[f"forecast_wape_{window}d_available_flag"] = False
        else:
            result[f"forecast_wape_{window}d"] = round(float(error / actual), 6)
            result[f"forecast_wape_{window}d_available_flag"] = True
    return result


def _prediction_interval_coverage(forecasts: pd.DataFrame, champion: str) -> dict:
    if forecasts.empty or not {"actual_demand", "p10", "p90", "model_name"}.issubset(forecasts.columns):
        return {
            "prediction_interval_coverage_rate": pd.NA,
            "prediction_interval_eligible_observations": 0,
            "prediction_interval_calibration_status": "INSUFFICIENT_DATA",
        }
    working = forecasts[forecasts["model_name"].astype(str).eq(champion)].copy()
    actual = pd.to_numeric(working["actual_demand"], errors="coerce")
    p10 = pd.to_numeric(working["p10"], errors="coerce")
    p90 = pd.to_numeric(working["p90"], errors="coerce")
    eligible = actual.notna() & p10.notna() & p90.notna()
    count = int(eligible.sum())
    if count < 10:
        return {
            "prediction_interval_coverage_rate": pd.NA,
            "prediction_interval_eligible_observations": count,
            "prediction_interval_calibration_status": "INSUFFICIENT_DATA",
        }
    coverage = ((actual[eligible] >= p10[eligible]) & (actual[eligible] <= p90[eligible])).mean()
    if 0.70 <= coverage <= 0.90:
        status = "WELL_CALIBRATED"
    elif coverage < 0.70:
        status = "TOO_NARROW"
    else:
        status = "TOO_WIDE"
    return {
        "prediction_interval_coverage_rate": round(float(coverage), 6),
        "prediction_interval_eligible_observations": count,
        "prediction_interval_calibration_status": status,
    }


def _forecast_stability(
    previous_future: pd.DataFrame,
    previous_snapshot_id: str,
    current_future: pd.DataFrame,
    sku_id: str,
    current_snapshot_id: str,
) -> dict:
    unavailable = {
        "forecast_stability_pct": pd.NA,
        "forecast_stability_status": "UNAVAILABLE_NO_COMPARABLE_PRIOR_RUN",
        "previous_forecast_available_flag": False,
        "forecast_stability_method": "UNAVAILABLE_REQUIRES_DISTINCT_FUTURE_FORECAST_SNAPSHOTS",
        "current_forecast_snapshot_id": current_snapshot_id,
        "previous_forecast_snapshot_id": previous_snapshot_id,
        "forecast_stability_comparable_row_count": 0,
    }
    required = {"sku_id", "forecast_date"}
    if previous_future.empty or current_future.empty or not required.issubset(previous_future.columns) or not required.issubset(current_future.columns):
        return unavailable
    if not previous_snapshot_id or previous_snapshot_id == current_snapshot_id:
        return unavailable
    previous_qty_col = _forecast_quantity_column(previous_future)
    current_qty_col = _forecast_quantity_column(current_future)
    if not previous_qty_col or not current_qty_col:
        return unavailable
    previous = previous_future[previous_future["sku_id"].astype(str).str.strip().eq(sku_id)].copy()
    if previous.empty:
        return unavailable
    previous["forecast_date"] = pd.to_datetime(previous["forecast_date"], errors="coerce")
    current = current_future.copy()
    current["forecast_date"] = pd.to_datetime(current["forecast_date"], errors="coerce")
    previous["previous_forecast_quantity"] = pd.to_numeric(previous[previous_qty_col], errors="coerce")
    current["current_forecast_quantity"] = pd.to_numeric(current[current_qty_col], errors="coerce")
    comparable = previous[["forecast_date", "previous_forecast_quantity"]].merge(
        current[["forecast_date", "current_forecast_quantity"]],
        on="forecast_date",
        how="inner",
    ).dropna(subset=["forecast_date", "previous_forecast_quantity", "current_forecast_quantity"])
    if comparable.empty:
        return unavailable
    denominator = comparable["previous_forecast_quantity"].abs().sum()
    if denominator <= 1e-9:
        unavailable["previous_forecast_available_flag"] = True
        unavailable["forecast_stability_status"] = "UNAVAILABLE_ZERO_PRIOR_FORECAST_QUANTITY"
        unavailable["forecast_stability_comparable_row_count"] = int(len(comparable))
        return unavailable
    stability = (comparable["current_forecast_quantity"] - comparable["previous_forecast_quantity"]).abs().sum() / denominator
    status = "STABLE" if stability <= 0.10 else ("MODERATE_CHANGE" if stability <= 0.30 else "MATERIAL_CHANGE")
    return {
        "forecast_stability_pct": round(float(stability), 6),
        "forecast_stability_status": status,
        "previous_forecast_available_flag": True,
        "forecast_stability_method": "FORECAST_QUANTITY_VECTOR_CHANGE_BY_SKU_AND_TARGET_DATE",
        "current_forecast_snapshot_id": current_snapshot_id,
        "previous_forecast_snapshot_id": previous_snapshot_id,
        "forecast_stability_comparable_row_count": int(len(comparable)),
    }


def _forecast_quantity_column(df: pd.DataFrame) -> str:
    for column in ["p50", "forecast_quantity"]:
        if column in df.columns:
            return column
    return ""


def _warning_codes(fva_status: str, horizon: dict, coverage: dict, stability: dict) -> str:
    codes = []
    if fva_status == "UNAVAILABLE":
        codes.append("FORECAST_VALUE_ADDED_UNAVAILABLE")
    for window in HORIZON_WINDOWS:
        if not horizon.get(f"forecast_wape_{window}d_available_flag", False):
            codes.append(f"FORECAST_WAPE_{window}D_UNAVAILABLE")
    if coverage["prediction_interval_calibration_status"] == "INSUFFICIENT_DATA":
        codes.append("PREDICTION_INTERVAL_COVERAGE_INSUFFICIENT_DATA")
    if not stability["previous_forecast_available_flag"]:
        codes.append("FORECAST_STABILITY_UNAVAILABLE_NO_COMPARABLE_PRIOR_RUN")
    return ";".join(codes) if codes else "NONE"
