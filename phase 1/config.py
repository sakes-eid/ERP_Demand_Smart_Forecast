from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

PRODUCTS_FILE = DATA_DIR / "products.csv"
DEMAND_FILE = DATA_DIR / "demand_history.csv"
EVENTS_FILE = DATA_DIR / "events.csv"

DATE_FORMAT = "%Y-%m-%d"

INTERMITTENT_SELECTION_WEIGHTS = {
    "wape_rank": 0.35,
    "mae_rank": 0.25,
    "mase_rank": 0.25,
    "absolute_bias_rank": 0.15,
}

DEMAND_PLANNING_CONTEXT_CONFIG = {
    "enabled": True,
    "forecast_horizons_days": [7, 14, 30, 60, 90],
    "default_planning_horizon_days": 30,
    "low_confidence_threshold": 0.50,
    "medium_confidence_threshold": 0.70,
    "high_uncertainty_ratio_threshold": 0.75,
    "underforecast_bias_threshold": -0.15,
    "overforecast_bias_threshold": 0.15,
    "stockout_censor_zero_window_days": 3,
    "stockout_censor_recent_window_days": 30,
    "stockout_censor_high_demand_quantile": 0.75,
    "minimum_history_days_for_context": 30,
    "event_lookahead_days": 60,
    "seasonality_min_strength": 0.20,
}

FUTURE_FORECAST_CONFIG = {
    "enabled": True,
    "future_horizon_days": 90,
    "forecast_frequency": "D",
    "use_champion_model_only": True,
    "fallback_model": "seasonal_naive_7",
    "min_training_days": 30,
    "clip_negative_forecasts": True,
    "prediction_interval_enabled": True,
    "prediction_interval_method": "backtest_residual_quantiles",
    "p10_quantile": 0.10,
    "p50_quantile": 0.50,
    "p90_quantile": 0.90,
    "default_interval_width_multiplier": 1.0,
}

MODEL_PERSISTENCE_CONFIG = {
    "enabled": True,
    "model_output_dir": OUTPUT_DIR / "models",
    "persist_champion_models_only": True,
    "persist_supported_models": [
        "linear_regression",
        "random_forest",
        "knn",
        "gradient_boosting",
    ],
    "persist_model_metadata": True,
}
