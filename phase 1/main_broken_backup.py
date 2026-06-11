"""Run the Phase 1 data foundation and forecasting pipeline end to end."""

from config import OUTPUT_DIR
from core.data_cleaner import (
    clean_demand_data,
    clean_events,
    clean_products,
    detect_anomalies,
    detect_missing_dates,
)
from core.data_loader import create_example_csv_files, export_csv, load_input_tables
from core.demand_profile import build_demand_profile
from core.event_features import add_event_features
from core.feature_engineering import (
    build_demand_features,
    count_generated_feature_columns,
    count_nan_lag_rows,
)
from core.forecasting import run_baseline_forecasting


def run_pipeline() -> None:
    """Load, validate, clean, feature-engineer, forecast, and export outputs."""
    create_example_csv_files()
    products, demand, events = load_input_tables()

    cleaned_products = clean_products(products)
    cleaned_demand = clean_demand_data(demand)
    cleaned_events = clean_events(events)
    anomalies = detect_anomalies(cleaned_demand)
    missing_dates = detect_missing_dates(cleaned_demand)
    demand_with_event_features = add_event_features(cleaned_demand, cleaned_events)
    demand_profile = build_demand_profile(demand_with_event_features)
    demand_features = build_demand_features(demand_with_event_features, demand_profile)
    forecast_results, model_performance, model_registry, forecasting_diagnostics = run_baseline_forecasting(
        demand_features
    )

    export_csv(cleaned_products, OUTPUT_DIR / "products_cleaned.csv")
    export_csv(cleaned_demand, OUTPUT_DIR / "demand_history_cleaned.csv")
    export_csv(cleaned_events, OUTPUT_DIR / "events_cleaned.csv")
    export_csv(anomalies, OUTPUT_DIR / "demand_anomalies.csv")
    export_csv(missing_dates, OUTPUT_DIR / "missing_dates.csv")
    export_csv(demand_with_event_features, OUTPUT_DIR / "demand_with_event_features.csv")
    export_csv(demand_profile, OUTPUT_DIR / "demand_profile.csv")
    export_csv(demand_features, OUTPUT_DIR / "demand_features.csv")
    export_csv(forecast_results, OUTPUT_DIR / "forecast_results.csv")
    export_csv(model_performance, OUTPUT_DIR / "model_performance.csv")
    export_csv(model_registry, OUTPUT_DIR / "model_registry.csv")

    print("Phase 1 data foundation completed.")
    print(f"Cleaned products: {len(cleaned_products)}")
    print(f"Cleaned demand rows: {len(cleaned_demand)}")
    print(f"Cleaned events: {len(cleaned_events)}")
    print(f"Anomalies detected: {len(anomalies)}")
    print(f"Missing dates detected: {len(missing_dates)}")
    print(f"Demand rows with event features: {len(demand_with_event_features)}")
    print_event_feature_summary(demand_with_event_features)
    print_demand_profile_summary(demand_profile)
    print_feature_engineering_summary(demand_features)
    print_forecasting_summary(forecast_results, model_performance, model_registry, forecasting_diagnostics)
    print(f"Outputs written to: {OUTPUT_DIR}")


def print_event_feature_summary(demand_with_event_features) -> None:
    """Print a compact summary of generated event features."""
    event_types = _detected_event_types(demand_with_event_features["event_types"])

    print("Event feature summary:")
    print(f"Total rows with events: {int(demand_with_event_features['has_event'].sum())}")
    print(f"Rows during events: {int(demand_with_event_features['during_event_flag'].sum())}")
    print(f"Rows before events: {int(demand_with_event_features['before_event_flag'].sum())}")
    print(f"Rows after events: {int(demand_with_event_features['after_event_flag'].sum())}")
    print(f"Event types detected: {event_types}")


def _detected_event_types(event_type_series) -> str:
    """Return sorted unique event types from semicolon-separated event type cells."""
    event_types: set[str] = set()
    for value in event_type_series.dropna():
        for event_type in str(value).split(";"):
            event_type = event_type.strip()
            if event_type:
                event_types.add(event_type)
    return ", ".join(sorted(event_types)) if event_types else "none"


def print_demand_profile_summary(demand_profile) -> None:
    """Print demand behavior and data sufficiency class counts."""
    print("Demand profile summary:")
    print("Demand behavior classes:")
    print(_format_class_counts(demand_profile["demand_behavior_class"]))
    print("Data sufficiency classes:")
    print(_format_class_counts(demand_profile["data_sufficiency_class"]))


def _format_class_counts(series) -> str:
    """Format class counts as a compact comma-separated string."""
    counts = series.value_counts().sort_index()
    return ", ".join(f"{class_name}: {count}" for class_name, count in counts.items())


def print_feature_engineering_summary(demand_features) -> None:
    """Print a compact summary of the model-ready feature dataset."""
    print("Feature engineering summary:")
    print(f"Total feature rows: {len(demand_features)}")
    print(f"Generated feature columns: {count_generated_feature_columns(demand_features)}")
    print(f"Rows containing NaN lag values: {count_nan_lag_rows(demand_features)}")
    print("Feature generation completed successfully.")


def print_forecasting_summary(forecast_results, model_performance, model_registry, forecasting_diagnostics) -> None:
    """Print a compact summary of forecasting outputs."""
    print("Forecasting summary:")
    print(f"Forecast result rows: {len(forecast_results)}")
    print(f"Model performance rows: {len(model_performance)}")
    print(f"Total models evaluated: {model_performance['model_name'].nunique() if not model_performance.empty else 0}")
    print(f"Champion models selected: {len(model_registry)}")
    if not model_registry.empty:
        print("Champion model counts:")
        print(_format_class_counts(model_registry["champion_model"]))
    print(f"Skipped ML models count: {forecasting_diagnostics['skipped_ml_models']}")
    print(f"ML model failures count: {forecasting_diagnostics['ml_model_failures']}")
    print("Advanced ML models added successfully.")
    if not forecast_results.empty:
        print("Confidence class counts:")
        print(_format_class_counts(forecast_results["forecast_confidence_class"]))
        print(f"Average confidence score: {forecast_results['forecast_confidence_score'].mean():.4f}")
        average_interval_width = (forecast_results["upper_bound"] - forecast_results["lower_bound"]).mean()
        print(f"Average interval width: {average_interval_width:.4f}")
        print("Risk level counts:")
        print(_format_class_counts(forecast_results["forecast_risk_level"]))


if __name__ == "__main__":
    run_pipeline()
