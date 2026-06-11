"""Baseline multi-model forecasting layer for demand planning."""

import json
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib

from config import MODEL_PERSISTENCE_CONFIG
from core.confidence import add_forecast_confidence
from core.evaluation import build_model_registry, evaluate_forecasts

TARGET_COLUMN = "quantity_demanded"
INTERNAL_TARGET_COLUMN = "__target_demand"
TEST_DAYS_PER_SKU = 30
VALIDATION_DAYS_PER_SKU = 30
MIN_ML_TRAIN_ROWS = 60

TARGET_AND_OUTPUT_COLUMNS = {
    "quantity_demanded",
    "quantity_demanded_clean",
    "actual_demand",
    "forecast_quantity",
    "error",
    "absolute_error",
    "p10",
    "p50",
    "p90",
    "lower_bound",
    "upper_bound",
    "date",
    "target_date",
    "sku_id",
    "event_names",
    "event_types",
    "demand_behavior_class",
    "data_sufficiency_class",
    "forecast_confidence_score",
    "forecast_confidence_class",
    "forecast_risk_level",
    "confidence_reason",
    "event_label",
    "notes",
    "is_invalid_quantity",
    "demand_change_1",
    "demand_change_7",
}

BASELINE_MODELS = {
    "naive": ["lag_1"],
    "seasonal_naive_lag_7": ["lag_7"],
    "moving_average_7": ["rolling_mean_7"],
    "moving_average_14": ["rolling_mean_14"],
    "moving_average_30": ["rolling_mean_30"],
}

LINEAR_REGRESSION_FEATURES = [
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_30",
    "rolling_mean_7",
    "rolling_mean_14",
    "rolling_mean_30",
    "rolling_std_7",
    "rolling_std_14",
    "rolling_std_30",
    "day_of_week",
    "week_of_year",
    "month",
    "quarter",
    "weekend_flag",
    "month_start_flag",
    "month_end_flag",
    "has_event",
    "promotion_flag",
    "holiday_flag",
    "before_event_flag",
    "during_event_flag",
    "after_event_flag",
    "event_count",
    "recent_event_count_7",
    "recent_event_count_30",
    "anomaly_recent_flag",
    "anomaly_count_30",
    "coefficient_of_variation",
    "zero_demand_ratio",
    "event_affected_ratio",
]


def run_baseline_forecasting(
    demand_features: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Generate baseline and challenger forecasts, then evaluate champions."""
    prepared = _prepare_features(demand_features)
    forecast_results, diagnostics = _forecast_all_skus(prepared)
    forecast_results = add_forecast_confidence(forecast_results, prepared)
    model_performance = evaluate_forecasts(forecast_results)
    model_registry = build_model_registry(model_performance)
    model_registry = persist_champion_models(prepared, model_registry)
    return forecast_results, model_performance, model_registry, diagnostics


def persist_champion_models(demand_features: pd.DataFrame, model_registry: pd.DataFrame) -> pd.DataFrame:
    """Persist supported champion model artifacts for future forecast reuse."""
    enriched = model_registry.copy()
    persistence_columns = {
        "model_persisted_flag": False,
        "model_artifact_path": "",
        "model_metadata_path": "",
        "future_forecast_reusable_flag": False,
        "future_forecast_reuse_reason": "",
    }
    for column, default in persistence_columns.items():
        enriched[column] = default

    if not MODEL_PERSISTENCE_CONFIG["enabled"] or enriched.empty:
        enriched["future_forecast_reuse_reason"] = "Model persistence disabled."
        return enriched

    output_dir = Path(MODEL_PERSISTENCE_CONFIG["model_output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    supported = set(MODEL_PERSISTENCE_CONFIG["persist_supported_models"])

    for index, row in enriched.iterrows():
        sku_id = str(row["sku_id"]).strip()
        model_name = str(row["champion_model"]).strip()
        normalized_model = _normalized_persist_model_name(model_name)
        if normalized_model not in supported:
            enriched.at[index, "future_forecast_reuse_reason"] = (
                "Champion is rule-based or not configured for model persistence; future forecast uses native rule/fallback logic."
            )
            continue

        sku_features = demand_features[demand_features["sku_id"].astype(str) == sku_id].copy()
        artifact, metadata, reason = _train_persistable_champion(sku_id, model_name, sku_features)
        if artifact is None:
            enriched.at[index, "future_forecast_reuse_reason"] = reason
            continue

        safe_sku = _safe_filename(sku_id)
        safe_model = _safe_filename(model_name)
        artifact_path = output_dir / f"{safe_sku}__{safe_model}.joblib"
        metadata_path = output_dir / f"{safe_sku}__{safe_model}__metadata.json"
        joblib.dump(artifact, artifact_path)
        if MODEL_PERSISTENCE_CONFIG["persist_model_metadata"]:
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        enriched.at[index, "model_persisted_flag"] = True
        enriched.at[index, "model_artifact_path"] = str(artifact_path)
        enriched.at[index, "model_metadata_path"] = str(metadata_path)
        enriched.at[index, "future_forecast_reusable_flag"] = True
        enriched.at[index, "future_forecast_reuse_reason"] = "Persisted champion model can be reused for future forecasting."

    return enriched


def _normalized_persist_model_name(model_name: str) -> str:
    if model_name == "knn_regressor":
        return "knn"
    return model_name


def _train_persistable_champion(sku_id: str, model_name: str, sku_features: pd.DataFrame) -> tuple[object | None, dict[str, object], str]:
    if sku_features.empty:
        return None, {}, "No training rows available for champion persistence."
    if model_name == "linear_regression":
        required_columns = LINEAR_REGRESSION_FEATURES + [INTERNAL_TARGET_COLUMN]
        valid = sku_features.dropna(subset=required_columns)
        if len(valid) < len(LINEAR_REGRESSION_FEATURES) + 1:
            return None, {}, "Insufficient rows/features to persist linear regression champion."
        coefficients = _fit_linear_regression(valid[LINEAR_REGRESSION_FEATURES], valid[INTERNAL_TARGET_COLUMN])
        artifact = {
            "model_type": "linear_regression",
            "coefficients": coefficients,
            "feature_columns": LINEAR_REGRESSION_FEATURES,
        }
        metadata = _metadata(sku_id, model_name, LINEAR_REGRESSION_FEATURES, len(valid), "Persisted linear regression coefficients.")
        return artifact, metadata, ""

    predictor_columns = _select_numeric_predictors(sku_features)
    required_columns = predictor_columns + [INTERNAL_TARGET_COLUMN]
    valid = sku_features.dropna(subset=required_columns)
    if len(valid) < MIN_ML_TRAIN_ROWS or not predictor_columns:
        return None, {}, "Insufficient valid training rows or predictors for persisted ML champion."
    tuning_train, validation_rows = _split_tuning_validation(valid)
    if len(tuning_train) < MIN_ML_TRAIN_ROWS or validation_rows.empty:
        return None, {}, "Insufficient internal validation rows for persisted ML champion."
    candidates = _ml_model_candidates(len(tuning_train)).get(model_name)
    if not candidates:
        return None, {}, "Champion model family is not available for persistence."
    model = _select_best_ml_model(candidates, tuning_train, validation_rows, predictor_columns)
    model.fit(valid[predictor_columns], valid[INTERNAL_TARGET_COLUMN])
    metadata = _metadata(sku_id, model_name, predictor_columns, len(valid), "Persisted retrained champion model family on available training rows.")
    return model, metadata, ""


def _metadata(sku_id: str, model_name: str, feature_columns: list[str], training_rows: int, notes: str) -> dict[str, object]:
    return {
        "sku_id": sku_id,
        "model_name": model_name,
        "feature_columns": feature_columns,
        "target_column": TARGET_COLUMN,
        "internal_target_column": INTERNAL_TARGET_COLUMN,
        "training_rows": training_rows,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "notes": notes,
    }


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)


def _prepare_features(demand_features: pd.DataFrame) -> pd.DataFrame:
    """Normalize feature types and ordering before model evaluation."""
    prepared = demand_features.copy()
    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce")
    prepared["sku_id"] = prepared["sku_id"].astype(str).str.strip()
    source_target = "quantity_demanded_clean" if "quantity_demanded_clean" in prepared.columns else TARGET_COLUMN
    prepared[INTERNAL_TARGET_COLUMN] = pd.to_numeric(prepared[source_target], errors="coerce")
    return prepared.dropna(subset=["date", "sku_id", INTERNAL_TARGET_COLUMN]).sort_values(["sku_id", "date"]).reset_index(drop=True)


def _forecast_all_skus(demand_features: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Run all baseline and challenger models independently for every SKU."""
    forecast_frames = []
    diagnostics = {"skipped_ml_models": 0, "ml_model_failures": 0}

    for sku_id, sku_features in demand_features.groupby("sku_id", sort=True):
        train_rows, test_rows = _split_train_test(sku_features)
        if train_rows.empty or test_rows.empty:
            continue

        forecast_frames.extend(_forecast_baseline_models(sku_id, test_rows))
        linear_results = _forecast_linear_regression(sku_id, train_rows, test_rows)
        if not linear_results.empty:
            forecast_frames.append(linear_results)
        ml_results, sku_diagnostics = _forecast_ml_challengers(sku_id, train_rows, test_rows)
        forecast_frames.extend(ml_results)
        diagnostics["skipped_ml_models"] += sku_diagnostics["skipped_ml_models"]
        diagnostics["ml_model_failures"] += sku_diagnostics["ml_model_failures"]

    if not forecast_frames:
        return _empty_forecast_frame(), diagnostics

    return pd.concat(forecast_frames, ignore_index=True), diagnostics


def _split_train_test(sku_features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use the last 30 rows for testing and all earlier rows for training."""
    ordered = sku_features.sort_values("date").reset_index(drop=True)
    test_rows = ordered.tail(TEST_DAYS_PER_SKU)
    train_rows = ordered.iloc[: -len(test_rows)]
    return train_rows, test_rows


def _forecast_baseline_models(sku_id: str, test_rows: pd.DataFrame) -> list[pd.DataFrame]:
    """Generate direct forecasts from lag and moving-average columns."""
    forecasts = []
    forecast_column_map = {
        "naive": "lag_1",
        "seasonal_naive_lag_7": "lag_7",
        "moving_average_7": "rolling_mean_7",
        "moving_average_14": "rolling_mean_14",
        "moving_average_30": "rolling_mean_30",
    }

    for model_name, forecast_column in forecast_column_map.items():
        valid_rows = test_rows.dropna(subset=[forecast_column, INTERNAL_TARGET_COLUMN])
        if valid_rows.empty:
            continue
        forecasts.append(_format_forecast_results(sku_id, model_name, valid_rows, valid_rows[forecast_column]))

    return forecasts


def _forecast_linear_regression(sku_id: str, train_rows: pd.DataFrame, test_rows: pd.DataFrame) -> pd.DataFrame:
    """Fit a simple per-SKU linear regression and forecast the test period."""
    required_columns = LINEAR_REGRESSION_FEATURES + [INTERNAL_TARGET_COLUMN]
    valid_train = train_rows.dropna(subset=required_columns)
    valid_test = test_rows.dropna(subset=LINEAR_REGRESSION_FEATURES + [INTERNAL_TARGET_COLUMN])

    if len(valid_train) < len(LINEAR_REGRESSION_FEATURES) + 1 or valid_test.empty:
        return pd.DataFrame()

    coefficients = _fit_linear_regression(valid_train[LINEAR_REGRESSION_FEATURES], valid_train[INTERNAL_TARGET_COLUMN])
    predictions = _predict_linear_regression(valid_test[LINEAR_REGRESSION_FEATURES], coefficients)
    predictions = pd.Series(np.maximum(predictions, 0), index=valid_test.index)
    return _format_forecast_results(sku_id, "linear_regression", valid_test, predictions)


def _forecast_ml_challengers(
    sku_id: str,
    train_rows: pd.DataFrame,
    test_rows: pd.DataFrame,
) -> tuple[list[pd.DataFrame], dict[str, int]]:
    """Tune and evaluate advanced ML challengers using only pre-test data."""
    diagnostics = {"skipped_ml_models": 0, "ml_model_failures": 0}
    predictor_columns = _select_numeric_predictors(train_rows)
    required_columns = predictor_columns + [INTERNAL_TARGET_COLUMN]
    valid_train = train_rows.dropna(subset=required_columns)
    valid_test = test_rows.dropna(subset=predictor_columns + [INTERNAL_TARGET_COLUMN])

    if len(valid_train) < MIN_ML_TRAIN_ROWS or valid_test.empty or not predictor_columns:
        diagnostics["skipped_ml_models"] += 3
        print(f"Skipped ML challengers for {sku_id}: insufficient valid training or test rows.")
        return [], diagnostics

    tuning_train, validation_rows = _split_tuning_validation(valid_train)
    if len(tuning_train) < MIN_ML_TRAIN_ROWS or validation_rows.empty:
        diagnostics["skipped_ml_models"] += 3
        print(f"Skipped ML challengers for {sku_id}: insufficient internal validation rows.")
        return [], diagnostics

    forecast_frames = []
    for model_name, candidate_models in _ml_model_candidates(len(tuning_train)).items():
        try:
            tuned_model = _select_best_ml_model(candidate_models, tuning_train, validation_rows, predictor_columns)
            tuned_model.fit(valid_train[predictor_columns], valid_train[INTERNAL_TARGET_COLUMN])
            predictions = tuned_model.predict(valid_test[predictor_columns])
            forecast_frames.append(_format_forecast_results(sku_id, model_name, valid_test, predictions))
        except Exception as exc:
            diagnostics["ml_model_failures"] += 1
            print(f"ML model failure for {sku_id} / {model_name}: {exc}")

    return forecast_frames, diagnostics


def _select_numeric_predictors(rows: pd.DataFrame) -> list[str]:
    """Select numeric, non-target predictor columns for ML challengers."""
    numeric_columns = rows.select_dtypes(include=["number", "bool"]).columns.tolist()
    return [
        column
        for column in numeric_columns
        if column not in TARGET_AND_OUTPUT_COLUMNS and not column.startswith("__")
    ]


def _split_tuning_validation(train_rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create an internal rolling-style validation split inside training data only."""
    ordered = train_rows.sort_values("date").reset_index(drop=True)
    validation_size = min(VALIDATION_DAYS_PER_SKU, max(14, len(ordered) // 5))
    validation_rows = ordered.tail(validation_size)
    tuning_train = ordered.iloc[: -len(validation_rows)]
    return tuning_train, validation_rows


def _ml_model_candidates(training_row_count: int) -> dict[str, list[object]]:
    """Return compact hyperparameter grids for advanced challenger models."""
    max_neighbors = max(1, min(14, training_row_count - 1))
    k_values = [k for k in (3, 5, 7, 14) if k <= max_neighbors]

    return {
        "random_forest": [
            RandomForestRegressor(n_estimators=n, max_depth=depth, min_samples_leaf=leaf, random_state=42)
            for n in (50, 100)
            for depth in (3, 6, None)
            for leaf in (1, 3)
        ],
        "knn_regressor": [
            Pipeline([("scaler", StandardScaler()), ("model", KNeighborsRegressor(n_neighbors=k))])
            for k in k_values
        ],
        "gradient_boosting": [
            GradientBoostingRegressor(n_estimators=n, learning_rate=rate, max_depth=depth, random_state=42)
            for n in (50, 100)
            for rate in (0.03, 0.05, 0.1)
            for depth in (2, 3)
        ],
    }


def _select_best_ml_model(
    candidate_models: list[object],
    tuning_train: pd.DataFrame,
    validation_rows: pd.DataFrame,
    predictor_columns: list[str],
) -> object:
    """Tune a model family on internal validation WAPE."""
    best_model = None
    best_wape = float("inf")

    for candidate in candidate_models:
        candidate.fit(tuning_train[predictor_columns], tuning_train[INTERNAL_TARGET_COLUMN])
        predictions = np.maximum(candidate.predict(validation_rows[predictor_columns]), 0)
        wape = _validation_wape(validation_rows[INTERNAL_TARGET_COLUMN], predictions)
        if wape < best_wape:
            best_wape = wape
            best_model = candidate

    return best_model


def _validation_wape(actuals: pd.Series, predictions: np.ndarray) -> float:
    """Return WAPE for internal model tuning."""
    denominator = actuals.abs().sum()
    absolute_error = np.abs(predictions - actuals.to_numpy(dtype=float)).sum()
    if denominator == 0:
        return 0.0 if absolute_error == 0 else float("inf")
    return float(absolute_error / denominator)


def _fit_linear_regression(features: pd.DataFrame, target: pd.Series) -> np.ndarray:
    """Fit ordinary least squares with an intercept term."""
    design_matrix = _with_intercept(features)
    coefficients, *_ = np.linalg.lstsq(design_matrix, target.to_numpy(dtype=float), rcond=None)
    return coefficients


def _predict_linear_regression(features: pd.DataFrame, coefficients: np.ndarray) -> np.ndarray:
    """Predict demand from linear regression coefficients."""
    return _with_intercept(features) @ coefficients


def _with_intercept(features: pd.DataFrame) -> np.ndarray:
    """Return a numeric design matrix with a leading intercept column."""
    feature_matrix = features.to_numpy(dtype=float)
    intercept = np.ones((len(features), 1))
    return np.hstack([intercept, feature_matrix])


def _format_forecast_results(
    sku_id: str,
    model_name: str,
    rows: pd.DataFrame,
    forecast_values: pd.Series | np.ndarray,
) -> pd.DataFrame:
    """Create the standard forecast results dataframe for one model."""
    forecasts = pd.Series(forecast_values, index=rows.index).astype(float).clip(lower=0)
    actuals = rows[INTERNAL_TARGET_COLUMN].astype(float)
    errors = forecasts - actuals

    return pd.DataFrame(
        {
            "sku_id": sku_id,
            "target_date": rows["date"].dt.strftime("%Y-%m-%d"),
            "model_name": model_name,
            "actual_demand": actuals,
            "forecast_quantity": forecasts,
            "error": errors,
            "absolute_error": errors.abs(),
        }
    )


def _empty_forecast_frame() -> pd.DataFrame:
    """Return an empty forecast results dataframe with expected columns."""
    return pd.DataFrame(
        columns=[
            "sku_id",
            "target_date",
            "model_name",
            "actual_demand",
            "forecast_quantity",
            "error",
            "absolute_error",
            "p10",
            "p50",
            "p90",
            "lower_bound",
            "upper_bound",
            "forecast_confidence_score",
            "forecast_confidence_class",
            "forecast_risk_level",
            "confidence_reason",
        ]
    )
