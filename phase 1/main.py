"""Run the Phase 1 data foundation and forecasting pipeline end to end."""

from datetime import datetime

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
from core.demand_planning_context import build_demand_planning_context, demand_planning_warning_counts
from core.event_features import add_event_features
from core.feature_engineering import (
    build_demand_features,
    count_generated_feature_columns,
    count_nan_lag_rows,
)
from core.forecast_kpis import build_forecast_kpis
from core.forecasting import run_baseline_forecasting
from core.future_forecasting import build_future_forecasts, future_forecast_warning_counts


def run_pipeline() -> None:
    """Load, validate, clean, feature-engineer, forecast, and export outputs."""
    run_started_at = datetime.now()
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
    future_forecast_results = build_future_forecasts(
        cleaned_demand,
        demand_features,
        model_registry,
        model_performance,
        forecast_results,
        cleaned_events,
    )
    forecast_kpis = build_forecast_kpis(
        forecast_results,
        future_forecast_results,
        model_performance,
        model_registry,
        OUTPUT_DIR,
        run_started_at,
    )
    demand_planning_context = build_demand_planning_context(
        cleaned_products,
        cleaned_demand,
        cleaned_events,
        forecast_results,
        demand_profile,
        model_registry,
        model_performance,
        future_forecast_results,
    )
    demand_planning_context = _merge_forecast_kpis_into_context(demand_planning_context, forecast_kpis)

    export_csv(cleaned_products, OUTPUT_DIR / "products_cleaned.csv")
    export_csv(cleaned_demand, OUTPUT_DIR / "demand_history_cleaned.csv")
    export_csv(cleaned_events, OUTPUT_DIR / "events_cleaned.csv")
    export_csv(anomalies, OUTPUT_DIR / "demand_anomalies.csv")
    export_csv(missing_dates, OUTPUT_DIR / "missing_dates.csv")
    export_csv(demand_with_event_features, OUTPUT_DIR / "demand_with_event_features.csv")
    export_csv(demand_profile, OUTPUT_DIR / "demand_profile.csv")
    export_csv(demand_features, OUTPUT_DIR / "demand_features.csv")
    export_csv(forecast_results, OUTPUT_DIR / "forecast_results.csv")
    export_csv(future_forecast_results, OUTPUT_DIR / "future_forecast_results.csv")
    export_csv(model_performance, OUTPUT_DIR / "model_performance.csv")
    export_csv(model_registry, OUTPUT_DIR / "model_registry.csv")
    export_csv(forecast_kpis, OUTPUT_DIR / "phase1_forecast_kpis.csv")
    export_csv(demand_planning_context, OUTPUT_DIR / "phase1_demand_planning_context.csv")

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
    print_forecast_kpi_summary(forecast_kpis)
    print_model_persistence_summary(model_registry)
    print_future_forecast_summary(future_forecast_results)
    print_demand_planning_context_summary(demand_planning_context)
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


def print_future_forecast_summary(future_forecast_results) -> None:
    """Print a compact summary of generated true future forecasts."""
    print("Future forecast summary:")
    print(f"Future forecast rows: {len(future_forecast_results)}")
    print(f"Future forecast SKUs: {future_forecast_results['sku_id'].nunique() if not future_forecast_results.empty else 0}")
    print(f"Future forecast horizon max: {int(future_forecast_results['horizon_day'].max()) if not future_forecast_results.empty else 0}")
    warning_counts = future_forecast_warning_counts(future_forecast_results)
    persisted_rows = int((future_forecast_results["forecast_generation_method"] == "PERSISTED_CHAMPION_MODEL").sum()) if "forecast_generation_method" in future_forecast_results.columns else 0
    fallback_count = warning_counts.get("FUTURE_MODEL_FALLBACK_USED", 0)
    interval_approx_count = warning_counts.get("FUTURE_INTERVAL_APPROXIMATED", 0)
    negative_clipped_count = warning_counts.get("NEGATIVE_FUTURE_FORECAST_CLIPPED", 0)
    event_adjust_count = int(future_forecast_results["event_flag"].sum()) if "event_flag" in future_forecast_results.columns else 0
    print(f"Future forecast rows using persisted champion model: {persisted_rows}")
    print(f"Future forecasts using fallback count: {fallback_count}")
    print(f"Fallback reduction vs previous baseline 720: {720 - fallback_count}")
    print(f"Future interval approximated count: {interval_approx_count}")
    print(f"Future negative forecast clipped count: {negative_clipped_count}")
    print(f"Future event adjustment count: {event_adjust_count}")
    if warning_counts:
        print("Future forecast warning code counts:")
        print(", ".join(f"{code}: {count}" for code, count in warning_counts.items()))
    else:
        print("Future forecast warning code counts: none")


def print_forecast_kpi_summary(forecast_kpis) -> None:
    """Print a compact summary of added forecast KPIs."""
    print("Forecast KPI summary:")
    print(f"Forecast KPI rows: {len(forecast_kpis)}")
    if forecast_kpis.empty:
        return
    print("Forecast value added status counts:")
    print(_format_class_counts(forecast_kpis["forecast_value_added_status"]))
    print(
        "Average forecast value added pct: "
        f"{_mean_numeric(forecast_kpis, 'forecast_value_added_pct'):.4f}"
    )
    print(
        "Average 7d/30d/90d WAPE: "
        f"{_mean_numeric(forecast_kpis, 'forecast_wape_7d'):.4f}, "
        f"{_mean_numeric(forecast_kpis, 'forecast_wape_30d'):.4f}, "
        f"{_mean_numeric(forecast_kpis, 'forecast_wape_90d'):.4f}"
    )
    print(
        "Average prediction interval coverage: "
        f"{_mean_numeric(forecast_kpis, 'prediction_interval_coverage_rate'):.4f}"
    )
    unavailable_stability = int(
        forecast_kpis["forecast_stability_status"].fillna("").astype(str).str.startswith("UNAVAILABLE").sum()
    )
    print(f"Forecast stability unavailable count: {unavailable_stability}")


def print_model_persistence_summary(model_registry) -> None:
    """Print compact model persistence summary counters."""
    print("Model persistence summary:")
    if model_registry.empty or "model_persisted_flag" not in model_registry.columns:
        print("Persisted model count: 0")
        print("Reusable persisted model count: 0")
        return
    persisted = model_registry["model_persisted_flag"].astype(str).str.lower().isin({"true", "1", "yes"})
    reusable = model_registry["future_forecast_reusable_flag"].astype(str).str.lower().isin({"true", "1", "yes"})
    print(f"Persisted model count: {int(persisted.sum())}")
    print(f"Reusable persisted model count: {int(reusable.sum())}")


def print_demand_planning_context_summary(demand_planning_context) -> None:
    """Print a compact summary of the downstream planning context output."""
    print("Demand planning context summary:")
    print(f"Rows: {len(demand_planning_context)}")
    print(f"High uncertainty count: {int(demand_planning_context['high_uncertainty_flag'].sum())}")
    print(f"Low confidence count: {int((demand_planning_context['forecast_confidence_band'] == 'LOW').sum())}")
    print(f"Stockout-censored demand flag count: {int(demand_planning_context['stockout_censored_demand_flag'].sum())}")
    print(f"Underforecast risk count: {int(demand_planning_context['underforecast_risk_flag'].sum())}")
    print(f"Overforecast risk count: {int(demand_planning_context['overforecast_risk_flag'].sum())}")
    print(f"Upcoming event flag count: {int(demand_planning_context['upcoming_event_flag'].sum())}")
    print(f"Average demand data quality score: {demand_planning_context['demand_data_quality_score'].mean():.4f}")
    warning_counts = demand_planning_warning_counts(demand_planning_context)
    true_future_count = int(
        demand_planning_context["demand_planning_warning_codes"]
        .fillna("")
        .astype(str)
        .str.contains("FORECAST_HORIZON_FROM_TRUE_FUTURE_FORECAST")
        .sum()
    )
    approximated_count = int(
        demand_planning_context["demand_planning_warning_codes"]
        .fillna("")
        .astype(str)
        .str.contains("FORECAST_HORIZON_APPROXIMATED")
        .sum()
    )
    print(f"Forecast horizons from true future forecasts: {true_future_count}")
    print(f"Forecast horizons approximated: {approximated_count}")
    if warning_counts:
        print("Demand planning warning code counts:")
        print(", ".join(f"{code}: {count}" for code, count in warning_counts.items()))
    else:
        print("Demand planning warning code counts: none")


def _merge_forecast_kpis_into_context(demand_planning_context, forecast_kpis):
    """Attach concise forecast KPI fields to the downstream planning context."""
    if demand_planning_context.empty or forecast_kpis.empty or "sku_id" not in demand_planning_context.columns:
        return demand_planning_context
    keep = [
        "sku_id",
        "forecast_value_added",
        "forecast_value_added_pct",
        "forecast_value_added_status",
        "baseline_model",
        "forecast_wape_7d",
        "forecast_wape_30d",
        "forecast_wape_90d",
        "forecast_wape_7d_available_flag",
        "forecast_wape_30d_available_flag",
        "forecast_wape_90d_available_flag",
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
        "forecast_kpi_warning_codes",
    ]
    return demand_planning_context.merge(forecast_kpis[keep], on="sku_id", how="left")


def _mean_numeric(df, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    value = df[column].pipe(lambda s: __import__("pandas").to_numeric(s, errors="coerce")).mean()
    return float(value) if value == value else 0.0


if __name__ == "__main__":
    run_pipeline()
