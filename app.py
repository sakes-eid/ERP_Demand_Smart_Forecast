"""Streamlit UI for Phase 1 Demand Intelligence."""

from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
except ModuleNotFoundError:
    px = None
    go = None


# Run with: streamlit run app.py

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_FILE_CANDIDATES = {
    "products": ["products_clean.csv", "products_cleaned.csv"],
    "demand": ["demand_history_clean.csv", "demand_history_cleaned.csv"],
    "event_features": ["demand_with_event_features.csv"],
    "features": ["demand_features.csv"],
    "profile": ["demand_profile.csv"],
    "anomalies": ["demand_anomalies.csv"],
    "forecasts": ["forecast_results.csv"],
    "performance": ["model_performance.csv"],
    "registry": ["model_registry.csv"],
    "missing_dates": ["missing_dates.csv"],
}

PAGES = [
    "Overview",
    "Data Quality",
    "Demand Profiles",
    "Forecasting Results",
    "Model Performance",
    "Champion Registry",
    "Event Analysis",
    "Pipeline Outputs",
]

FORECAST_TABLE_PRIORITY = [
    "sku_id",
    "target_date",
    "model_name",
    "actual_demand",
    "forecast_quantity",
    "p10",
    "p50",
    "p90",
    "lower_bound",
    "upper_bound",
    "forecast_confidence_score",
    "forecast_confidence_class",
    "forecast_risk_level",
    "confidence_reason",
    "error",
    "absolute_error",
]

MODEL_PERFORMANCE_PRIORITY = [
    "sku_id",
    "model_name",
    "is_champion",
    "selection_metric",
    "selection_score",
    "mae",
    "rmse",
    "wape",
    "smape",
    "mase",
    "bias",
    "metric_warning",
    "average_confidence_score",
    "average_interval_width",
    "observations_used",
    "selection_reason",
]

CHAMPION_REGISTRY_PRIORITY = [
    "sku_id",
    "champion_model",
    "champion_selection_metric",
    "champion_selection_score",
    "champion_wape",
    "champion_mae",
    "champion_bias",
    "champion_confidence_score",
    "champion_risk_level",
    "champion_metric_warning",
    "selection_reason",
]

DEMAND_PROFILE_PRIORITY = [
    "sku_id",
    "sku_name",
    "category",
    "demand_behavior_class",
    "data_sufficiency_class",
    "total_demand",
    "average_daily_demand",
    "coefficient_of_variation",
    "zero_demand_ratio",
    "event_affected_ratio",
    "seasonality_score",
    "trend_score",
]

ANOMALY_PRIORITY = [
    "date",
    "sku_id",
    "quantity_demanded",
    "anomaly_reason",
    "anomaly_score",
    "is_valid_for_training",
    "event_label",
    "notes",
]

EVENT_ANALYSIS_PRIORITY = [
    "date",
    "sku_id",
    "quantity_demanded",
    "event_names",
    "event_types",
    "has_event",
    "before_event_flag",
    "during_event_flag",
    "after_event_flag",
    "promotion_flag",
    "holiday_flag",
    "stockout_flag",
]


def load_csv_flexible(output_dir: Path, candidates: list[str]) -> tuple[pd.DataFrame, str | None, str | None]:
    """Load the first available CSV from a list of candidate filenames."""
    for filename in candidates:
        path = output_dir / filename
        if path.exists():
            return pd.read_csv(path), filename, None
    return pd.DataFrame(), None, f"Missing file. Expected one of: {', '.join(candidates)}"


@st.cache_data
def load_all_outputs() -> dict[str, dict[str, object]]:
    """Load all expected output CSVs with flexible filename support."""
    loaded = {}
    for key, candidates in OUTPUT_FILE_CANDIDATES.items():
        df, filename, warning = load_csv_flexible(OUTPUT_DIR, candidates)
        loaded[key] = {"df": df, "filename": filename, "warning": warning, "candidates": candidates}
    return loaded


def render_overview(data: dict[str, dict[str, object]]) -> None:
    """Render high-level demand intelligence KPIs and distributions."""
    st.title("Demand Intelligence Overview")
    products = get_df(data, "products")
    demand = get_df(data, "demand")
    anomalies = get_df(data, "anomalies")
    missing_dates = get_df(data, "missing_dates")
    performance = get_df(data, "performance")
    registry = get_df(data, "registry")
    forecasts = get_df(data, "forecasts")
    profile = get_df(data, "profile")

    metric_columns = st.columns(4)
    metric_columns[0].metric("SKUs", count_skus(products, demand, profile))
    metric_columns[1].metric("Demand Rows", len(demand))
    metric_columns[2].metric("Anomalies", len(anomalies))
    metric_columns[3].metric("Missing Dates", len(missing_dates))

    metric_columns = st.columns(4)
    metric_columns[0].metric("Models Evaluated", unique_count(performance, "model_name"))
    metric_columns[1].metric("Champion Models", len(registry))
    metric_columns[2].metric("Avg Confidence", format_mean(forecasts, "forecast_confidence_score"))
    metric_columns[3].metric("Avg Interval Width", average_interval_width(forecasts))

    show_warnings(data)
    chart_columns = st.columns(2)
    with chart_columns[0]:
        render_count_chart(registry, "champion_model", "Champion Model Distribution")
        render_count_chart(forecasts, "forecast_confidence_class", "Confidence Class Distribution")
    with chart_columns[1]:
        render_count_chart(forecasts, "forecast_risk_level", "Risk Level Distribution")
        render_count_chart(profile, "demand_behavior_class", "Demand Behavior Distribution")


def render_data_quality(data: dict[str, dict[str, object]]) -> None:
    """Render anomalies, missing dates, and data quality summaries."""
    st.title("Data Quality")
    anomalies = get_df(data, "anomalies")
    missing_dates = get_df(data, "missing_dates")
    demand = get_df(data, "demand")

    metric_columns = st.columns(4)
    metric_columns[0].metric("Anomaly Rows", len(anomalies))
    metric_columns[1].metric("Missing Date Rows", len(missing_dates))
    metric_columns[2].metric("Invalid Quantity Rows", count_flagged(demand, "is_invalid_quantity"))
    metric_columns[3].metric("Demand Rows", len(demand))

    filtered_anomalies = anomalies.copy()
    if not filtered_anomalies.empty:
        selected_sku = select_filter("SKU", filtered_anomalies, "sku_id", "quality_sku")
        selected_type = select_filter("Anomaly Type", filtered_anomalies, "anomaly_reason", "quality_type")
        filtered_anomalies = apply_filter(filtered_anomalies, "sku_id", selected_sku)
        filtered_anomalies = apply_filter(filtered_anomalies, "anomaly_reason", selected_type)

    render_count_chart(anomalies, "anomaly_reason", "Anomaly Types")
    st.subheader("Anomalies")
    show_dataframe(filtered_anomalies, ANOMALY_PRIORITY)
    st.subheader("Missing Dates")
    show_dataframe(missing_dates)
    show_warnings(data, keys=["anomalies", "missing_dates", "demand"])


def render_demand_profiles(data: dict[str, dict[str, object]]) -> None:
    """Render SKU-level demand profiles."""
    st.title("Demand Profiles")
    profile = get_df(data, "profile")
    products = get_df(data, "products")
    if profile.empty:
        show_missing_or_empty(data, "profile")
        return

    profile = add_product_context(profile, products)
    selected_sku = select_filter("SKU", profile, "sku_id", "profile_sku")
    selected_category = select_filter("Category", profile, "category", "profile_category")
    selected_behavior = select_filter("Demand Behavior", profile, "demand_behavior_class", "profile_behavior")
    selected_sufficiency = select_filter("Data Sufficiency", profile, "data_sufficiency_class", "profile_sufficiency")

    filtered = apply_filter(profile, "sku_id", selected_sku)
    filtered = apply_filter(filtered, "category", selected_category)
    filtered = apply_filter(filtered, "demand_behavior_class", selected_behavior)
    filtered = apply_filter(filtered, "data_sufficiency_class", selected_sufficiency)

    chart_columns = st.columns(2)
    with chart_columns[0]:
        render_count_chart(filtered, "demand_behavior_class", "Demand Behavior Classes")
        render_bar_chart(filtered, "sku_id", "zero_demand_ratio", "Zero Demand Ratio by SKU")
    with chart_columns[1]:
        render_count_chart(filtered, "data_sufficiency_class", "Data Sufficiency Classes")
        render_bar_chart(filtered, "sku_id", "coefficient_of_variation", "Coefficient of Variation by SKU")

    st.subheader("Demand Profile Table")
    show_dataframe(filtered, DEMAND_PROFILE_PRIORITY)


def render_forecasting_results(data: dict[str, dict[str, object]]) -> None:
    """Render forecast results for a selected SKU and champion model."""
    st.title("Forecasting Results")
    forecasts = get_df(data, "forecasts")
    registry = get_df(data, "registry")
    if forecasts.empty:
        show_missing_or_empty(data, "forecasts")
        return

    selected_sku = select_filter("SKU", forecasts, "sku_id", "forecast_sku", default_first=True)
    sku_forecasts = apply_filter(forecasts, "sku_id", selected_sku)
    champion_model = champion_for_sku(registry, selected_sku)
    if champion_model:
        st.caption(f"Showing champion model for {selected_sku}: {champion_model}")
        sku_forecasts = sku_forecasts[sku_forecasts["model_name"] == champion_model]
    else:
        selected_model = select_filter("Model", sku_forecasts, "model_name", "forecast_model", default_first=True)
        sku_forecasts = apply_filter(sku_forecasts, "model_name", selected_model)

    metric_columns = st.columns(3)
    metric_columns[0].metric("Rows", len(sku_forecasts))
    metric_columns[1].metric("Avg Confidence", format_mean(sku_forecasts, "forecast_confidence_score"))
    metric_columns[2].metric("Avg Interval Width", average_interval_width(sku_forecasts))

    render_forecast_chart(sku_forecasts)
    chart_columns = st.columns(2)
    with chart_columns[0]:
        render_count_chart(sku_forecasts, "forecast_confidence_class", "Confidence Classes")
    with chart_columns[1]:
        render_count_chart(sku_forecasts, "forecast_risk_level", "Risk Levels")

    st.subheader("Forecast Table")
    show_dataframe(sku_forecasts, FORECAST_TABLE_PRIORITY)


def render_model_performance(data: dict[str, dict[str, object]]) -> None:
    """Render model performance comparison for one SKU."""
    st.title("Model Performance")
    performance = get_df(data, "performance")
    registry = get_df(data, "registry")
    if performance.empty:
        show_missing_or_empty(data, "performance")
        return

    selected_sku = select_filter("SKU", performance, "sku_id", "performance_sku", default_first=True)
    filtered = apply_filter(performance, "sku_id", selected_sku)
    champion_model = champion_for_sku(registry, selected_sku)
    if champion_model and "model_name" in filtered.columns:
        filtered = filtered.copy()
        filtered["is_champion"] = filtered["model_name"].eq(champion_model)
        st.success(f"Champion model: {champion_model}")

    st.caption("Lower error metrics and lower selection score are better.")
    metric_choice = st.radio("Compare models by", ["selection_score", "wape"], horizontal=True)
    render_bar_chart(filtered, "model_name", metric_choice, f"Models by {metric_choice}", sort_descending=False)
    show_dataframe(filtered, MODEL_PERFORMANCE_PRIORITY)


def render_champion_registry(data: dict[str, dict[str, object]]) -> None:
    """Render champion model registry."""
    st.title("Champion Registry")
    registry = get_df(data, "registry")
    if registry.empty:
        show_missing_or_empty(data, "registry")
        return

    selected_model = select_filter("Champion Model", registry, "champion_model", "registry_model")
    selected_risk = select_filter("Champion Risk", registry, "champion_risk_level", "registry_risk")
    filtered = apply_filter(registry, "champion_model", selected_model)
    filtered = apply_filter(filtered, "champion_risk_level", selected_risk)

    chart_columns = st.columns(2)
    with chart_columns[0]:
        render_count_chart(filtered, "champion_model", "Champion Model Counts")
    with chart_columns[1]:
        render_count_chart(filtered, "champion_risk_level", "Champion Risk Levels")

    show_dataframe(filtered, CHAMPION_REGISTRY_PRIORITY)


def render_event_analysis(data: dict[str, dict[str, object]]) -> None:
    """Render event feature analysis."""
    st.title("Event Analysis")
    event_features = get_df(data, "event_features")
    if event_features.empty:
        show_missing_or_empty(data, "event_features")
        return

    selected_sku = select_filter("SKU", event_features, "sku_id", "event_sku")
    selected_event_type = select_event_type_filter(event_features)
    filtered = apply_filter(event_features, "sku_id", selected_sku)
    filtered = apply_event_type_filter(filtered, selected_event_type)

    metric_columns = st.columns(4)
    metric_columns[0].metric("Rows With Events", count_flagged(filtered, "has_event"))
    metric_columns[1].metric("Before Event", count_flagged(filtered, "before_event_flag"))
    metric_columns[2].metric("During Event", count_flagged(filtered, "during_event_flag"))
    metric_columns[3].metric("After Event", count_flagged(filtered, "after_event_flag"))

    render_event_type_counts(filtered)
    st.subheader("Event-Affected Demand")
    if has_columns(filtered, ["has_event"]):
        show_dataframe(filtered[filtered["has_event"] > 0], EVENT_ANALYSIS_PRIORITY)
    else:
        show_dataframe(filtered, EVENT_ANALYSIS_PRIORITY)


def render_pipeline_outputs(data: dict[str, dict[str, object]]) -> None:
    """Render compact status of expected pipeline output files."""
    st.title("Pipeline Outputs")
    rows = []
    for key, item in data.items():
        df = item["df"]
        rows.append(
            {
                "output_key": key,
                "status": "FOUND" if item["filename"] else "MISSING",
                "filename_used": item["filename"] or "",
                "rows": len(df),
                "columns": len(df.columns),
                "expected_names": ", ".join(item["candidates"]),
            }
        )
    show_dataframe(pd.DataFrame(rows))


def render_forecast_chart(df: pd.DataFrame) -> None:
    """Render actual vs forecast with optional prediction interval bands."""
    if df.empty or not has_columns(df, ["target_date", "actual_demand"]):
        st.info("No forecast rows available for the selected filters.")
        return

    chart_df = df.copy()
    chart_df["target_date"] = pd.to_datetime(chart_df["target_date"], errors="coerce")
    y_forecast = "p50" if "p50" in chart_df.columns else "forecast_quantity"

    if px and go:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=chart_df["target_date"],
                y=chart_df["actual_demand"],
                name="Actual Demand",
                mode="lines+markers",
                line={"color": "#2563eb", "width": 3},
            )
        )
        if has_columns(chart_df, ["p10", "p90"]):
            fig.add_trace(
                go.Scatter(
                    x=chart_df["target_date"],
                    y=chart_df["p90"],
                    name="P10-P90 Uncertainty Band",
                    mode="lines",
                    line={"width": 0},
                    showlegend=False,
                    hovertemplate="P90: %{y}<extra></extra>",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=chart_df["target_date"],
                    y=chart_df["p10"],
                    name="P10-P90 Uncertainty Band",
                    fill="tonexty",
                    fillcolor="rgba(245, 158, 11, 0.22)",
                    mode="lines",
                    line={"width": 0},
                    hovertemplate="P10: %{y}<extra></extra>",
                )
            )
        fig.add_trace(
            go.Scatter(
                x=chart_df["target_date"],
                y=chart_df[y_forecast],
                name="P50 Forecast" if y_forecast == "p50" else "Forecast Quantity",
                mode="lines+markers",
                line={"color": "#dc2626", "width": 3, "dash": "dash"},
            )
        )
        fig.update_layout(
            title="Actual Demand vs Champion Forecast",
            xaxis_title="Target Date",
            yaxis_title="Demand",
            hovermode="x unified",
            legend_title_text="Series",
            margin={"l": 20, "r": 20, "t": 60, "b": 20},
        )
        st.plotly_chart(fig, width="stretch")
        return

    st.line_chart(chart_df.set_index("target_date")[["actual_demand", y_forecast]])
    if has_columns(chart_df, ["p10", "p90"]):
        st.caption("P10/P90 interval columns are available in the table below.")


def render_count_chart(df: pd.DataFrame, column: str, title: str) -> None:
    """Render a count chart for a categorical column."""
    st.subheader(title)
    if df.empty or column not in df.columns:
        st.info("No data available.")
        return
    counts = df[column].fillna("Unknown").astype(str).value_counts().reset_index()
    counts.columns = [column, "count"]
    counts = counts.sort_values("count", ascending=False)
    if px:
        fig = px.bar(counts, x=column, y="count", title=title, labels={column: column.replace("_", " ").title(), "count": "Count"})
        if counts[column].astype(str).str.len().max() > 14 or len(counts) > 6:
            fig.update_xaxes(tickangle=-35)
        fig.update_layout(showlegend=False, margin={"l": 20, "r": 20, "t": 50, "b": 40})
        st.plotly_chart(fig, width="stretch")
    else:
        st.bar_chart(counts.set_index(column))


def render_bar_chart(
    df: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str,
    sort_descending: bool = True,
) -> None:
    """Render a bar chart when both columns are available."""
    st.subheader(title)
    if df.empty or not has_columns(df, [x_column, y_column]):
        st.info("No data available.")
        return
    chart_df = df[[x_column, y_column]].dropna().copy()
    chart_df[y_column] = pd.to_numeric(chart_df[y_column], errors="coerce")
    chart_df = chart_df.dropna(subset=[y_column]).sort_values(y_column, ascending=not sort_descending)
    if px:
        fig = px.bar(
            chart_df,
            x=x_column,
            y=y_column,
            title=title,
            labels={x_column: x_column.replace("_", " ").title(), y_column: y_column.replace("_", " ").title()},
        )
        if chart_df[x_column].astype(str).str.len().max() > 14 or len(chart_df) > 6:
            fig.update_xaxes(tickangle=-35)
        fig.update_layout(showlegend=False, margin={"l": 20, "r": 20, "t": 50, "b": 40})
        st.plotly_chart(fig, width="stretch")
    else:
        st.bar_chart(chart_df.set_index(x_column))


def render_event_type_counts(df: pd.DataFrame) -> None:
    """Render counts of semicolon-separated event types."""
    st.subheader("Event Type Counts")
    counts = event_type_counts(df)
    if counts.empty:
        st.info("No event types available.")
        return
    if px:
        st.plotly_chart(px.bar(counts, x="event_type", y="count"), width="stretch")
    else:
        st.bar_chart(counts.set_index("event_type"))


def event_type_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Return event type counts from semicolon-separated event type cells."""
    if df.empty or "event_types" not in df.columns:
        return pd.DataFrame(columns=["event_type", "count"])
    values = []
    for value in df["event_types"].dropna():
        values.extend([part.strip() for part in str(value).split(";") if part.strip()])
    if not values:
        return pd.DataFrame(columns=["event_type", "count"])
    return pd.Series(values).value_counts().reset_index(name="count").rename(columns={"index": "event_type"})


def select_filter(label: str, df: pd.DataFrame, column: str, key: str, default_first: bool = False) -> str:
    """Render a selectbox filter for a dataframe column."""
    if df.empty or column not in df.columns:
        return "All"
    options = sorted(df[column].dropna().astype(str).unique().tolist())
    if not options:
        return "All"
    options = options if default_first else ["All"] + options
    return st.selectbox(label, options, key=key)


def select_event_type_filter(df: pd.DataFrame) -> str:
    """Render an event type filter from semicolon-separated event types."""
    counts = event_type_counts(df)
    if counts.empty:
        return "All"
    options = ["All"] + sorted(counts["event_type"].astype(str).tolist())
    return st.selectbox("Event Type", options, key="event_type_filter")


def apply_filter(df: pd.DataFrame, column: str, value: str) -> pd.DataFrame:
    """Apply a simple equality filter when a concrete value is selected."""
    if value == "All" or df.empty or column not in df.columns:
        return df
    return df[df[column].astype(str) == value]


def apply_event_type_filter(df: pd.DataFrame, event_type: str) -> pd.DataFrame:
    """Filter rows containing an event type token."""
    if event_type == "All" or df.empty or "event_types" not in df.columns:
        return df
    return df[df["event_types"].fillna("").astype(str).str.split(";").apply(lambda parts: event_type in [p.strip() for p in parts])]


def show_dataframe(df: pd.DataFrame, priority_columns: list[str] | None = None) -> None:
    """Display a dataframe or a graceful empty state."""
    if df.empty:
        st.info("No rows available.")
    else:
        st.caption("Key columns are shown first. Scroll horizontally to view all columns.")
        st.dataframe(reorder_columns(df, priority_columns or []), width="stretch", hide_index=True)


def reorder_columns(df: pd.DataFrame, priority_columns: list[str]) -> pd.DataFrame:
    """Show priority columns first while preserving all other columns."""
    if df.empty or not priority_columns:
        return df
    first_columns = [column for column in priority_columns if column in df.columns]
    remaining_columns = [column for column in df.columns if column not in first_columns]
    return df[first_columns + remaining_columns]


def show_warnings(data: dict[str, dict[str, object]], keys: list[str] | None = None) -> None:
    """Show missing file warnings."""
    keys = keys or list(data.keys())
    for key in keys:
        warning = data[key]["warning"]
        if warning:
            st.warning(f"{key}: {warning}")


def show_missing_or_empty(data: dict[str, dict[str, object]], key: str) -> None:
    """Show a clear message for missing or empty data."""
    warning = data[key]["warning"]
    if warning:
        st.warning(warning)
    else:
        st.info("The file was loaded but contains no rows.")


def get_df(data: dict[str, dict[str, object]], key: str) -> pd.DataFrame:
    """Return a loaded dataframe by output key."""
    return data[key]["df"]


def has_columns(df: pd.DataFrame, columns: list[str]) -> bool:
    """Return True when all columns are present."""
    return all(column in df.columns for column in columns)


def unique_count(df: pd.DataFrame, column: str) -> int:
    """Return unique count for a column if present."""
    if df.empty or column not in df.columns:
        return 0
    return int(df[column].nunique())


def count_skus(products: pd.DataFrame, demand: pd.DataFrame, profile: pd.DataFrame) -> int:
    """Return the best available SKU count."""
    for df in (products, profile, demand):
        if not df.empty and "sku_id" in df.columns:
            return int(df["sku_id"].nunique())
    return 0


def count_flagged(df: pd.DataFrame, column: str) -> int:
    """Count positive values in a flag column."""
    if df.empty or column not in df.columns:
        return 0
    return int(pd.to_numeric(df[column], errors="coerce").fillna(0).gt(0).sum())


def format_mean(df: pd.DataFrame, column: str) -> str:
    """Format a numeric mean when available."""
    if df.empty or column not in df.columns:
        return "N/A"
    return f"{pd.to_numeric(df[column], errors='coerce').mean():.3f}"


def average_interval_width(df: pd.DataFrame) -> str:
    """Format average interval width if interval columns exist."""
    if df.empty or not has_columns(df, ["lower_bound", "upper_bound"]):
        return "N/A"
    width = pd.to_numeric(df["upper_bound"], errors="coerce") - pd.to_numeric(df["lower_bound"], errors="coerce")
    return f"{width.mean():.3f}"


def champion_for_sku(registry: pd.DataFrame, sku_id: str) -> str | None:
    """Return champion model for a SKU if available."""
    if registry.empty or not has_columns(registry, ["sku_id", "champion_model"]):
        return None
    matches = registry[registry["sku_id"].astype(str) == str(sku_id)]
    if matches.empty:
        return None
    return str(matches.iloc[0]["champion_model"])


def add_product_context(df: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Add product category fields when product output data is available."""
    if df.empty or products.empty or "sku_id" not in df.columns or "sku_id" not in products.columns:
        return df
    context_columns = ["sku_id"] + [column for column in ["category", "subcategory", "sku_name"] if column in products.columns]
    if len(context_columns) == 1:
        return df
    return df.merge(products[context_columns].drop_duplicates("sku_id"), on="sku_id", how="left")


def main() -> None:
    """Run the Streamlit application."""
    st.set_page_config(page_title="Demand Intelligence", layout="wide")
    st.sidebar.title("Planning System")
    st.sidebar.caption("Phase 1: Demand Intelligence")
    page = st.sidebar.radio("Navigation", PAGES)
    data = load_all_outputs()

    if page == "Overview":
        render_overview(data)
    elif page == "Data Quality":
        render_data_quality(data)
    elif page == "Demand Profiles":
        render_demand_profiles(data)
    elif page == "Forecasting Results":
        render_forecasting_results(data)
    elif page == "Model Performance":
        render_model_performance(data)
    elif page == "Champion Registry":
        render_champion_registry(data)
    elif page == "Event Analysis":
        render_event_analysis(data)
    elif page == "Pipeline Outputs":
        render_pipeline_outputs(data)


if __name__ == "__main__":
    main()

