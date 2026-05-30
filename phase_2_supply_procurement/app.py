"""Streamlit dashboard for Phase 2 Supply & Procurement."""

from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    px = None
    go = None


# Run with: streamlit run app.py

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
DATA_DIR = BASE_DIR / "data"

EXPECTED_OUTPUTS = {
    "supplier_trends": OUTPUT_DIR / "supplier_trends.csv",
    "supplier_performance": OUTPUT_DIR / "supplier_performance.csv",
    "supplier_sku_scores": OUTPUT_DIR / "supplier_sku_scores.csv",
    "procurement_recommendations": OUTPUT_DIR / "procurement_recommendations.csv",
}

HISTORY_INPUTS = {
    "purchase_orders": DATA_DIR / "purchase_orders.csv",
    "receipts": DATA_DIR / "receipts.csv",
}

TABLE_CAPTION = "Key columns are shown first. Scroll horizontally to view all columns."


st.set_page_config(page_title="Phase 2 Supply & Procurement", layout="wide")


@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV file with caching and graceful failure."""
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        st.warning(f"Could not load {path.name}: {exc}")
        return pd.DataFrame()


@st.cache_data
def load_all_outputs() -> dict[str, pd.DataFrame]:
    """Load all Phase 2 output CSVs."""
    return {name: load_csv(path) for name, path in EXPECTED_OUTPUTS.items()}


@st.cache_data
def load_history_data() -> dict[str, pd.DataFrame]:
    """Load purchase order and receipt history for UI-only trend charts."""
    return {name: load_csv(path) for name, path in HISTORY_INPUTS.items()}


@st.cache_data
def prepare_supplier_history(purchase_orders: pd.DataFrame, receipts: pd.DataFrame) -> pd.DataFrame:
    """Merge purchase orders and receipts into history for supplier trend plots."""
    if purchase_orders.empty or receipts.empty:
        return pd.DataFrame()
    if "po_id" not in purchase_orders.columns or "po_id" not in receipts.columns:
        return pd.DataFrame()

    po_columns = [
        column
        for column in [
            "po_id",
            "supplier_id",
            "sku_id",
            "order_date",
            "promised_delivery_date",
            "ordered_quantity",
            "expected_unit_cost",
        ]
        if column in purchase_orders.columns
    ]
    history = receipts.merge(purchase_orders[po_columns], on="po_id", how="left")
    for column in ["order_date", "promised_delivery_date", "receipt_date"]:
        if column in history.columns:
            history[column] = pd.to_datetime(history[column], errors="coerce")
    numeric_columns = [
        "ordered_quantity",
        "received_quantity",
        "accepted_quantity",
        "rejected_quantity",
        "delay_days",
        "partial_delivery_flag",
        "quality_issue_flag",
        "expected_unit_cost",
    ]
    for column in numeric_columns:
        if column in history.columns:
            history[column] = pd.to_numeric(history[column], errors="coerce")
    return history


def file_status(path: Path) -> dict[str, object]:
    """Return status details for an expected output file."""
    if not path.exists():
        return {
            "file": path.name,
            "exists": False,
            "rows": 0,
            "columns": 0,
            "last_modified": "",
        }
    df = load_csv(path)
    return {
        "file": path.name,
        "exists": True,
        "rows": len(df),
        "columns": len(df.columns),
        "last_modified": pd.Timestamp(path.stat().st_mtime, unit="s").strftime("%Y-%m-%d %H:%M:%S"),
    }


def reorder_columns(df: pd.DataFrame, priority_columns: list[str]) -> pd.DataFrame:
    """Show priority columns first while preserving every column."""
    if df.empty:
        return df
    first = [column for column in priority_columns if column in df.columns]
    rest = [column for column in df.columns if column not in first]
    return df[first + rest]


def show_table(df: pd.DataFrame, priority_columns: list[str]) -> None:
    """Render a dataframe with important columns first."""
    st.caption(TABLE_CAPTION)
    if df.empty:
        st.info("No rows available.")
        return
    st.dataframe(reorder_columns(df, priority_columns), use_container_width=True, hide_index=True)


def safe_metric(label: str, value) -> None:
    """Render a metric without crashing on missing values."""
    if pd.isna(value):
        value = "N/A"
    st.metric(label, value)


def make_bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str | None = None,
    title: str = "",
    color: str | None = None,
    sort_desc: bool = True,
) -> None:
    """Render a Plotly bar chart with a Streamlit fallback."""
    if df.empty or x not in df.columns:
        st.info("Not enough data for this chart.")
        return

    chart_df = df.copy()
    if y is None:
        chart_df = chart_df[x].value_counts(dropna=False).rename_axis(x).reset_index(name="count")
        y = "count"

    if y not in chart_df.columns:
        st.info("Not enough data for this chart.")
        return

    chart_df = chart_df.sort_values(y, ascending=not sort_desc)
    if PLOTLY_AVAILABLE:
        fig = px.bar(chart_df, x=x, y=y, color=color if color in chart_df.columns else None, title=title)
        fig.update_layout(xaxis_title=x.replace("_", " ").title(), yaxis_title=y.replace("_", " ").title())
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(chart_df.set_index(x)[y])


def make_grouped_bar_chart(df: pd.DataFrame, x: str, y_columns: list[str], title: str) -> None:
    """Render grouped metric bars for baseline/recent comparisons."""
    available = [column for column in y_columns if column in df.columns]
    if df.empty or x not in df.columns or not available:
        st.info("Not enough data for this chart.")
        return
    chart_df = df[[x, *available]].melt(id_vars=x, var_name="metric", value_name="value")
    chart_df = chart_df.dropna(subset=["value"])
    if chart_df.empty:
        st.info("Not enough data for this chart.")
        return
    if PLOTLY_AVAILABLE:
        fig = px.bar(chart_df, x=x, y="value", color="metric", barmode="group", title=title)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(chart_df.pivot(index=x, columns="metric", values="value"))


def aggregate_supplier_history(history: pd.DataFrame, frequency: str) -> pd.DataFrame:
    """Aggregate supplier history by week or month for trend-line charts."""
    if history.empty or "receipt_date" not in history.columns:
        return pd.DataFrame()

    freq = "W-MON" if frequency == "Weekly" else "MS"
    working = history.dropna(subset=["receipt_date"]).copy()
    if working.empty:
        return pd.DataFrame()

    working["time_bucket"] = working["receipt_date"].dt.to_period(freq).dt.start_time
    working["late_delivery_flag"] = (working["delay_days"].fillna(0) > 0).astype(int)
    working["on_time_flag"] = 1 - working["late_delivery_flag"]
    working["expected_total_cost"] = working["expected_unit_cost"] * working["ordered_quantity"]

    grouped = working.groupby("time_bucket", dropna=False).agg(
        record_count=("po_id", "count"),
        average_delay_days=("delay_days", "mean"),
        on_time_delivery_rate=("on_time_flag", "mean"),
        late_delivery_rate=("late_delivery_flag", "mean"),
        partial_delivery_rate=("partial_delivery_flag", "mean"),
        ordered_quantity=("ordered_quantity", "sum"),
        received_quantity=("received_quantity", "sum"),
        accepted_quantity=("accepted_quantity", "sum"),
        rejected_quantity=("rejected_quantity", "sum"),
        quality_issue_rate=("quality_issue_flag", "mean"),
        average_unit_cost=("expected_unit_cost", "mean"),
        total_expected_cost=("expected_total_cost", "sum"),
    ).reset_index()

    grouped["received_to_ordered_ratio"] = _safe_divide_series(
        grouped["received_quantity"],
        grouped["ordered_quantity"],
    )
    grouped["yield_rate"] = _safe_divide_series(grouped["accepted_quantity"], grouped["received_quantity"])
    grouped["defect_rate"] = _safe_divide_series(grouped["rejected_quantity"], grouped["received_quantity"])
    grouped["cost_per_usable_unit"] = _safe_divide_series(
        grouped["total_expected_cost"],
        grouped["accepted_quantity"],
    )
    grouped["reliability_score"] = (
        0.40 * grouped["on_time_delivery_rate"].fillna(0)
        + 0.30 * grouped["yield_rate"].fillna(0)
        + 0.20 * (1 - grouped["partial_delivery_rate"].fillna(1))
        + 0.10 * (1 - grouped["quality_issue_rate"].fillna(1))
    ).clip(0, 1)
    return grouped.sort_values("time_bucket")


def plot_line_chart(
    df: pd.DataFrame,
    y_columns: list[str],
    title: str,
    recent_start: pd.Timestamp | None = None,
    recent_end: pd.Timestamp | None = None,
) -> None:
    """Render one or more time-series lines with a Streamlit fallback."""
    available = [column for column in y_columns if column in df.columns]
    if df.empty or "time_bucket" not in df.columns or not available:
        st.info("Not enough data for this chart.")
        return

    chart_df = df[["time_bucket", *available]].copy()
    chart_df[available] = chart_df[available].apply(pd.to_numeric, errors="coerce")
    chart_df = chart_df.dropna(how="all", subset=available)
    if chart_df.empty:
        st.info("Not enough data for this chart.")
        return

    if PLOTLY_AVAILABLE:
        fig = go.Figure()
        for column in available:
            fig.add_trace(
                go.Scatter(
                    x=chart_df["time_bucket"],
                    y=chart_df[column],
                    mode="lines+markers",
                    name=column.replace("_", " ").title(),
                )
            )
        if recent_start is not None and recent_end is not None:
            fig.add_vrect(
                x0=recent_start,
                x1=recent_end,
                fillcolor="LightSalmon",
                opacity=0.18,
                layer="below",
                line_width=0,
                annotation_text="Recent period",
                annotation_position="top left",
            )
        fig.update_layout(title=title, xaxis_title="Receipt Period", yaxis_title="Metric Value")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart(chart_df.set_index("time_bucket")[available])


def show_supplier_trend_lines(trends: pd.DataFrame) -> None:
    """Render supplier-specific history trend line charts."""
    history_files = load_history_data()
    purchase_orders = history_files["purchase_orders"]
    receipts = history_files["receipts"]
    if purchase_orders.empty and not HISTORY_INPUTS["purchase_orders"].exists():
        st.warning("Missing data/purchase_orders.csv. Run python main.py first.")
    if receipts.empty and not HISTORY_INPUTS["receipts"].exists():
        st.warning("Missing data/receipts.csv. Run python main.py first.")

    history = prepare_supplier_history(purchase_orders, receipts)
    if history.empty:
        st.warning("Purchase order and receipt history is unavailable for trend-line charts.")
        return

    supplier_ids = _supplier_selector_options(trends, history)
    if not supplier_ids:
        st.warning("No supplier history is available for trend-line charts.")
        return

    default_supplier = _default_trend_supplier(trends, supplier_ids)
    supplier_id = st.selectbox(
        "Supplier for time-series analysis",
        supplier_ids,
        index=supplier_ids.index(default_supplier),
    )
    supplier_history = history[history["supplier_id"].astype(str) == supplier_id].copy()

    sku_options = ["All SKUs"]
    if "sku_id" in supplier_history.columns:
        sku_options.extend(sorted(supplier_history["sku_id"].dropna().astype(str).unique()))
    selected_sku = st.selectbox("SKU filter for time-series analysis", sku_options)
    if selected_sku != "All SKUs":
        supplier_history = supplier_history[supplier_history["sku_id"].astype(str) == selected_sku]

    frequency = st.radio("Aggregation", ["Weekly", "Monthly"], horizontal=True)
    recent_start, recent_end, baseline_start, baseline_end = _trend_windows(history)
    st.caption(
        "Recent period is the last 30 days from the latest receipt date. "
        "Baseline is the previous 90 days."
    )
    if pd.notna(recent_start):
        st.caption(
            f"Baseline: {baseline_start.date()} to {baseline_end.date()} | "
            f"Recent: {recent_start.date()} to {recent_end.date()}"
        )

    show_supplier_interpretation(trends, supplier_id)

    if len(supplier_history) < 3:
        st.warning("Not enough historical records to draw a reliable trend line.")

    aggregated = aggregate_supplier_history(supplier_history, frequency)
    if aggregated.empty or len(aggregated) < 2:
        st.warning("Not enough historical records to draw a reliable trend line.")
        show_table(supplier_history, _history_priority_columns())
        return

    col1, col2 = st.columns(2)
    with col1:
        plot_line_chart(aggregated, ["reliability_score"], "Reliability Over Time", recent_start, recent_end)
        plot_line_chart(aggregated, ["yield_rate", "defect_rate"], "Quality Over Time", recent_start, recent_end)
        plot_line_chart(aggregated, ["average_unit_cost", "cost_per_usable_unit"], "Cost Over Time", recent_start, recent_end)
    with col2:
        plot_line_chart(aggregated, ["average_delay_days"], "Delay Over Time", recent_start, recent_end)
        plot_line_chart(aggregated, ["partial_delivery_rate"], "Partial Delivery Over Time", recent_start, recent_end)

    with st.expander("Raw supplier receipt history"):
        show_table(supplier_history, _history_priority_columns())


def metric_row(metrics: list[tuple[str, object]]) -> None:
    """Render metrics in a responsive row."""
    columns = st.columns(min(len(metrics), 4))
    for index, (label, value) in enumerate(metrics):
        with columns[index % len(columns)]:
            safe_metric(label, value)


def warning_for_missing(data: dict[str, pd.DataFrame], required: list[str]) -> None:
    """Show warnings for missing required CSV outputs."""
    for name in required:
        if data.get(name, pd.DataFrame()).empty and not EXPECTED_OUTPUTS[name].exists():
            st.warning(f"Missing {EXPECTED_OUTPUTS[name].name}. Run python main.py first.")


def filter_by_multiselect(df: pd.DataFrame, column: str, label: str | None = None) -> pd.DataFrame:
    """Filter a dataframe using a sidebar multiselect when the column exists."""
    if df.empty or column not in df.columns:
        return df
    values = sorted(df[column].dropna().astype(str).unique())
    selected = st.multiselect(label or column.replace("_", " ").title(), values)
    if selected:
        return df[df[column].astype(str).isin(selected)]
    return df


def filter_by_bool(df: pd.DataFrame, column: str, label: str | None = None) -> pd.DataFrame:
    """Filter a dataframe by a boolean-like column."""
    if df.empty or column not in df.columns:
        return df
    choice = st.selectbox(label or column.replace("_", " ").title(), ["All", "True", "False"])
    if choice == "All":
        return df
    return df[df[column].astype(str).str.lower() == choice.lower()]


def count_true(df: pd.DataFrame, column: str) -> int:
    """Count truthy values in a dataframe column."""
    if df.empty or column not in df.columns:
        return 0
    return int(df[column].astype(str).str.lower().isin(["true", "1", "yes"]).sum())


def numeric_mean(df: pd.DataFrame, column: str) -> float:
    """Return a numeric mean or zero when unavailable."""
    if df.empty or column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").mean())


def numeric_count(df: pd.DataFrame, column: str, value: str) -> int:
    """Count a specific string value in a column."""
    if df.empty or column not in df.columns:
        return 0
    return int((df[column].astype(str) == value).sum())


def _safe_divide_series(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Safely divide two numeric series."""
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce").replace(0, pd.NA)
    return numerator / denominator


def _supplier_selector_options(trends: pd.DataFrame, history: pd.DataFrame) -> list[str]:
    """Return supplier options from trends and history."""
    supplier_values = set()
    if "supplier_id" in trends.columns:
        supplier_values.update(trends["supplier_id"].dropna().astype(str).tolist())
    if "supplier_id" in history.columns:
        supplier_values.update(history["supplier_id"].dropna().astype(str).tolist())
    return sorted(supplier_values)


def _default_trend_supplier(trends: pd.DataFrame, supplier_ids: list[str]) -> str:
    """Default to a watchlist supplier when one is available."""
    if not trends.empty and {"supplier_id", "supplier_trend_status"}.issubset(trends.columns):
        watchlist = trends[trends["supplier_trend_status"].astype(str) == "WATCHLIST"]
        if not watchlist.empty:
            supplier_id = str(watchlist.iloc[0]["supplier_id"])
            if supplier_id in supplier_ids:
                return supplier_id
    return supplier_ids[0]


def _trend_windows(history: pd.DataFrame) -> tuple[pd.Timestamp | None, pd.Timestamp | None, pd.Timestamp | None, pd.Timestamp | None]:
    """Return baseline and recent windows used by the backend trend logic."""
    if history.empty or "receipt_date" not in history.columns:
        return None, None, None, None
    latest = history["receipt_date"].dropna().max()
    if pd.isna(latest):
        return None, None, None, None
    recent_end = latest.normalize()
    recent_start = recent_end - pd.Timedelta(days=29)
    baseline_end = recent_start - pd.Timedelta(days=1)
    baseline_start = baseline_end - pd.Timedelta(days=89)
    return recent_start, recent_end, baseline_start, baseline_end


def show_supplier_interpretation(trends: pd.DataFrame, supplier_id: str) -> None:
    """Render a deterministic interpretation from supplier trend fields."""
    if trends.empty or "supplier_id" not in trends.columns:
        return
    row_df = trends[trends["supplier_id"].astype(str) == supplier_id]
    if row_df.empty:
        return
    row = row_df.iloc[0]
    status = row.get("supplier_trend_status", "UNKNOWN")
    reason = row.get("supplier_watchlist_reason", "")
    trend_fields = [
        "lead_time_trend",
        "delay_trend",
        "yield_trend",
        "partial_delivery_trend",
        "reliability_trend",
        "cost_per_usable_unit_trend",
    ]
    worsening = [
        column.replace("_trend", "").replace("_", " ")
        for column in trend_fields
        if row.get(column) == "WORSENING"
    ]
    improving = [
        column.replace("_trend", "").replace("_", " ")
        for column in trend_fields
        if row.get(column) == "IMPROVING"
    ]

    if status == "WATCHLIST" and worsening:
        message = f"Supplier {supplier_id} is on WATCHLIST because {', '.join(worsening)} trend is worsening."
    elif status == "IMPROVING":
        message = f"Supplier {supplier_id} is IMPROVING because most metrics improved and no critical trend worsened."
    elif status == "HEALTHY":
        message = f"Supplier {supplier_id} is HEALTHY because recent performance is stable with no critical worsening trend."
    elif status == "MIXED":
        detail = f" Improving: {', '.join(improving)}." if improving else ""
        message = f"Supplier {supplier_id} is MIXED because some metrics improved while others worsened.{detail}"
    elif status == "INSUFFICIENT_DATA":
        message = f"Supplier {supplier_id} has INSUFFICIENT_DATA for reliable trend detection."
    else:
        message = f"Supplier {supplier_id} trend status is {status}."

    st.info(f"{message} {reason}".strip())
    metric_row(
        [
            ("Improving Metrics", row.get("improving_trend_count", 0)),
            ("Worsening Metrics", row.get("worsening_trend_count", 0)),
            ("Stable Metrics", row.get("stable_trend_count", 0)),
            ("Watchlist", row.get("supplier_watchlist_flag", False)),
        ]
    )


def _history_priority_columns() -> list[str]:
    """Return priority columns for raw PO/receipt history."""
    return [
        "supplier_id",
        "sku_id",
        "po_id",
        "order_date",
        "promised_delivery_date",
        "receipt_date",
        "ordered_quantity",
        "received_quantity",
        "accepted_quantity",
        "rejected_quantity",
        "delay_days",
        "partial_delivery_flag",
        "quality_issue_flag",
        "expected_unit_cost",
    ]


def render_overview(data: dict[str, pd.DataFrame]) -> None:
    """Render the Phase 2 overview page."""
    st.title("Supply & Procurement Overview")
    st.write("High-level procurement health, supplier trends, risk, feasibility, and recommendation coverage.")
    warning_for_missing(data, list(EXPECTED_OUTPUTS))

    trends = data["supplier_trends"]
    scores = data["supplier_sku_scores"]
    recs = data["procurement_recommendations"]

    supplier_count = trends["supplier_id"].nunique() if "supplier_id" in trends.columns else 0
    metric_row(
        [
            ("Suppliers", supplier_count),
            ("Supplier-SKU Options", len(scores)),
            ("Recommendations", len(recs)),
            ("Feasible Options", count_true(scores, "is_feasible_supplier_option")),
        ]
    )
    metric_row(
        [
            ("Infeasible Options", len(scores) - count_true(scores, "is_feasible_supplier_option")),
            ("Watchlist Suppliers", numeric_count(trends, "supplier_trend_status", "WATCHLIST")),
            ("Improving Suppliers", numeric_count(trends, "supplier_trend_status", "IMPROVING")),
            ("Insufficient Data", numeric_count(trends, "supplier_trend_status", "INSUFFICIENT_DATA")),
        ]
    )
    metric_row(
        [
            ("Recommendations Requiring Review", count_true(recs, "recommended_supplier_requires_review")),
            ("Using Watchlist Suppliers", count_true(recs, "supplier_watchlist_flag")),
            ("Avg Recommended Cost", f"{numeric_mean(recs, 'estimated_total_procurement_cost'):.2f}"),
            ("Avg Feasible Order Qty", f"{numeric_mean(recs, 'final_feasible_order_quantity'):.2f}"),
        ]
    )

    col1, col2 = st.columns(2)
    with col1:
        make_bar_chart(trends, "supplier_trend_status", title="Supplier Trend Status Counts")
        make_bar_chart(scores, "is_feasible_supplier_option", title="Feasible vs Infeasible Supplier Options")
    with col2:
        make_bar_chart(scores, "demand_adjusted_procurement_risk_class", title="Demand-Adjusted Risk Class Counts")
        make_bar_chart(recs, "recommended_supplier_requires_review", title="Recommendations Requiring Review")


def render_supplier_performance(data: dict[str, pd.DataFrame]) -> None:
    """Render supplier performance KPIs."""
    st.title("Supplier Performance")
    st.write("Supplier-level historical performance KPIs and evidence status.")
    warning_for_missing(data, ["supplier_performance"])

    df = data["supplier_performance"].copy()
    df = filter_by_multiselect(df, "supplier_id")
    df = filter_by_multiselect(df, "performance_data_status")
    df = filter_by_multiselect(df, "supplier_trend_status")
    df = filter_by_bool(df, "supplier_watchlist_flag")

    metric_row(
        [
            ("Avg Lead Time", f"{numeric_mean(df, 'average_lead_time_days'):.2f}"),
            ("Avg Yield", f"{numeric_mean(df, 'average_yield_rate'):.3f}"),
            ("On-Time Rate", f"{numeric_mean(df, 'on_time_delivery_rate'):.3f}"),
            ("Late Delivery Rate", f"{numeric_mean(df, 'late_delivery_rate'):.3f}"),
        ]
    )
    metric_row(
        [
            ("Partial Delivery Rate", f"{numeric_mean(df, 'partial_delivery_rate'):.3f}"),
            ("Reliability Score", f"{numeric_mean(df, 'calculated_reliability_score'):.3f}"),
        ]
    )

    col1, col2 = st.columns(2)
    with col1:
        make_bar_chart(df, "supplier_id", "calculated_reliability_score", "Reliability Score by Supplier")
        make_bar_chart(df, "supplier_id", "average_delay_days", "Average Delay Days by Supplier", sort_desc=False)
    with col2:
        make_bar_chart(df, "supplier_id", "on_time_delivery_rate", "On-Time Delivery Rate by Supplier")
        make_bar_chart(df, "supplier_id", "average_yield_rate", "Average Yield Rate by Supplier")

    priority = [
        "supplier_id",
        "supplier_name",
        "performance_data_status",
        "performance_observation_count",
        "calculated_reliability_score",
        "average_lead_time_days",
        "lead_time_std_days",
        "on_time_delivery_rate",
        "late_delivery_rate",
        "average_yield_rate",
        "defect_rate",
        "supplier_trend_status",
        "supplier_watchlist_flag",
        "supplier_watchlist_reason",
    ]
    show_table(df, priority)


def render_supplier_trends(data: dict[str, pd.DataFrame]) -> None:
    """Render supplier trend analysis."""
    st.title("Supplier Trends")
    st.write("Recent supplier performance compared with the prior baseline window.")
    warning_for_missing(data, ["supplier_trends"])

    df = data["supplier_trends"].copy()
    df = filter_by_multiselect(df, "supplier_id")
    df = filter_by_multiselect(df, "supplier_trend_status")

    metric_row(
        [
            ("Improving", numeric_count(df, "supplier_trend_status", "IMPROVING")),
            ("Healthy", numeric_count(df, "supplier_trend_status", "HEALTHY")),
            ("Watchlist", numeric_count(df, "supplier_trend_status", "WATCHLIST")),
            ("Mixed", numeric_count(df, "supplier_trend_status", "MIXED")),
        ]
    )
    metric_row(
        [
            ("Insufficient Data", numeric_count(df, "supplier_trend_status", "INSUFFICIENT_DATA")),
            ("Worsening Delay", numeric_count(df, "delay_trend", "WORSENING")),
            ("Worsening Yield", numeric_count(df, "yield_trend", "WORSENING")),
            ("Worsening Reliability", numeric_count(df, "reliability_trend", "WORSENING")),
        ]
    )
    metric_row([("Worsening Cost/Usable Unit", numeric_count(df, "cost_per_usable_unit_trend", "WORSENING"))])

    st.subheader("Supplier Trend Over Time")
    show_supplier_trend_lines(data["supplier_trends"])

    col1, col2 = st.columns(2)
    with col1:
        make_bar_chart(df, "supplier_trend_status", title="Supplier Trend Status Counts")
        make_grouped_bar_chart(
            df,
            "supplier_id",
            ["improving_trend_count", "worsening_trend_count", "stable_trend_count"],
            "Trend Counts by Supplier",
        )
    with col2:
        make_grouped_bar_chart(
            df,
            "supplier_id",
            ["baseline_reliability_score", "recent_reliability_score"],
            "Recent vs Baseline Reliability",
        )
        make_grouped_bar_chart(
            df,
            "supplier_id",
            ["baseline_cost_per_usable_unit", "recent_cost_per_usable_unit"],
            "Recent vs Baseline Cost per Usable Unit",
        )

    priority = [
        "supplier_id",
        "supplier_trend_status",
        "supplier_watchlist_flag",
        "supplier_watchlist_reason",
        "improving_trend_count",
        "worsening_trend_count",
        "stable_trend_count",
        "lead_time_trend",
        "delay_trend",
        "on_time_delivery_trend",
        "partial_delivery_trend",
        "yield_trend",
        "defect_rate_trend",
        "cost_trend",
        "cost_per_usable_unit_trend",
        "reliability_trend",
    ]
    show_table(df, priority)


def render_supplier_sku_options(data: dict[str, pd.DataFrame]) -> None:
    """Render all supplier-SKU options."""
    st.title("Supplier-SKU Options")
    st.write("Compare all available supplier options per SKU.")
    warning_for_missing(data, ["supplier_sku_scores"])

    df = data["supplier_sku_scores"].copy()
    df = filter_by_multiselect(df, "sku_id")
    df = filter_by_multiselect(df, "supplier_id")
    df = filter_by_bool(df, "is_feasible_supplier_option", "Feasible Supplier Option")
    df = filter_by_multiselect(df, "demand_adjusted_procurement_risk_class", "Demand-Adjusted Risk Class")
    df = filter_by_bool(df, "supplier_requires_review", "Supplier Requires Review")
    df = filter_by_multiselect(df, "supplier_trend_status")

    metric_row(
        [
            ("Options", len(df)),
            ("Feasible", count_true(df, "is_feasible_supplier_option")),
            ("Infeasible", len(df) - count_true(df, "is_feasible_supplier_option")),
            ("Requires Review", count_true(df, "supplier_requires_review")),
        ]
    )
    metric_row(
        [
            ("Low Risk", numeric_count(df, "demand_adjusted_procurement_risk_class", "LOW")),
            ("Medium Risk", numeric_count(df, "demand_adjusted_procurement_risk_class", "MEDIUM")),
            ("High Risk", numeric_count(df, "demand_adjusted_procurement_risk_class", "HIGH")),
            ("Avg Adjusted Score", f"{numeric_mean(df, 'adjusted_supplier_score'):.3f}"),
        ]
    )

    selected_sku_df = _selected_sku_subset(df)
    col1, col2, col3 = st.columns(3)
    with col1:
        make_bar_chart(selected_sku_df, "supplier_id", "adjusted_supplier_score", "Adjusted Supplier Score")
    with col2:
        make_bar_chart(selected_sku_df, "supplier_id", "estimated_total_procurement_cost", "Estimated Total Cost", sort_desc=False)
    with col3:
        make_bar_chart(selected_sku_df, "supplier_id", "demand_adjusted_procurement_risk_score", "Demand-Adjusted Risk", sort_desc=False)

    priority = [
        "sku_id",
        "supplier_id",
        "adjusted_supplier_score",
        "supplier_score",
        "normalized_total_cost_score",
        "cost_score_basis",
        "estimated_total_procurement_cost",
        "procurement_risk_class",
        "demand_adjusted_procurement_risk_class",
        "is_feasible_supplier_option",
        "feasibility_warning",
        "supplier_evidence_status",
        "supplier_requires_review",
        "supplier_trend_status",
        "supplier_watchlist_flag",
        "unit_cost",
        "moq",
        "batch_size",
        "final_feasible_order_quantity",
        "expected_yield_rate",
        "yield_rate",
        "lead_time_mean_days",
        "lead_time_std_days",
    ]
    show_table(df, priority)


def render_procurement_recommendations(data: dict[str, pd.DataFrame]) -> None:
    """Render recommended and backup supplier decisions."""
    st.title("Procurement Recommendations")
    st.write("Recommended supplier, backup supplier, split sourcing, review status, and rationale.")
    warning_for_missing(data, ["procurement_recommendations"])

    df = data["procurement_recommendations"].copy()
    df = filter_by_multiselect(df, "sku_id")
    df = filter_by_multiselect(df, "recommended_supplier_id")
    df = filter_by_multiselect(df, "demand_adjusted_procurement_risk_class", "Demand-Adjusted Risk Class")
    df = filter_by_bool(df, "recommended_supplier_requires_review", "Recommended Supplier Requires Review")
    df = filter_by_bool(df, "split_sourcing_recommendation", "Split Sourcing Recommendation")

    metric_row(
        [
            ("Recommended SKUs", len(df)),
            ("Requires Review", count_true(df, "recommended_supplier_requires_review")),
            ("Using Watchlist Suppliers", count_true(df, "supplier_watchlist_flag")),
            ("Split Sourcing", count_true(df, "split_sourcing_recommendation")),
        ]
    )
    metric_row(
        [
            ("Avg Total Cost", f"{numeric_mean(df, 'estimated_total_procurement_cost'):.2f}"),
            ("Avg Feasible Order Qty", f"{numeric_mean(df, 'final_feasible_order_quantity'):.2f}"),
        ]
    )

    col1, col2 = st.columns(2)
    with col1:
        make_bar_chart(df, "recommended_supplier_id", title="Recommended Supplier Count")
        make_bar_chart(df, "demand_adjusted_procurement_risk_class", title="Recommendation Risk Class")
    with col2:
        make_bar_chart(df, "sku_id", "estimated_total_procurement_cost", "Recommended Supplier Total Cost by SKU", sort_desc=False)
        make_bar_chart(df, "recommended_supplier_requires_review", title="Review Required Count")

    priority = [
        "sku_id",
        "recommended_supplier_id",
        "backup_supplier_id",
        "adjusted_supplier_score",
        "estimated_total_procurement_cost",
        "final_feasible_order_quantity",
        "demand_adjusted_procurement_risk_class",
        "recommended_supplier_feasible",
        "recommended_supplier_requires_review",
        "recommended_supplier_evidence_status",
        "recommended_supplier_evidence_warning",
        "recommended_supplier_history_status",
        "recommended_supplier_trend_status",
        "supplier_trend_status",
        "split_sourcing_recommendation",
        "recommended_primary_share",
        "recommended_backup_share",
        "expected_lead_time_days",
        "expected_arrival_date",
        "selection_reason",
    ]
    show_table(df, priority)


def render_risk_cost_analysis(data: dict[str, pd.DataFrame]) -> None:
    """Render procurement risk and cost analysis."""
    st.title("Risk & Cost Analysis")
    st.write("Analyze procurement risk classes, demand-adjusted risk, and cost breakdowns.")
    warning_for_missing(data, ["supplier_sku_scores", "procurement_recommendations"])

    scores = data["supplier_sku_scores"].copy()
    recs = data["procurement_recommendations"].copy()

    col1, col2 = st.columns(2)
    with col1:
        make_bar_chart(scores, "procurement_risk_class", title="Procurement Risk Class Counts")
        make_bar_chart(scores, "demand_adjusted_procurement_risk_class", title="Demand-Adjusted Risk Class Counts")
    with col2:
        _histogram(scores, "estimated_total_procurement_cost", "Estimated Total Procurement Cost Distribution")
        make_bar_chart(recs, "demand_adjusted_procurement_risk_class", title="Recommendation Risk Class Counts")

    selected = _selected_sku_subset(scores)
    st.subheader("Selected SKU Supplier Comparison")
    col3, col4 = st.columns(2)
    with col3:
        make_bar_chart(selected, "supplier_id", "estimated_total_procurement_cost", "Total Procurement Cost", sort_desc=False)
        make_bar_chart(selected, "supplier_id", "adjusted_supplier_score", "Adjusted Supplier Score")
    with col4:
        make_bar_chart(selected, "supplier_id", "demand_adjusted_procurement_risk_score", "Demand-Adjusted Risk Score", sort_desc=False)
        make_bar_chart(selected, "supplier_id", "is_feasible_supplier_option", "Feasibility Status")

    cost_columns = [
        "estimated_product_cost",
        "estimated_fixed_order_cost",
        "estimated_delivery_cost",
        "estimated_expected_delay_cost",
        "estimated_expected_partial_delivery_cost",
        "estimated_expected_quality_cost",
    ]
    _cost_breakdown_chart(selected, cost_columns)


def render_feasibility_review(data: dict[str, pd.DataFrame]) -> None:
    """Render operational feasibility review."""
    st.title("Feasibility Review")
    st.write("Review supplier options constrained by MOQ, batch size, yield, status, and forecast reference quantity.")
    warning_for_missing(data, ["supplier_sku_scores", "procurement_recommendations"])

    df = data["supplier_sku_scores"].copy()
    df = filter_by_multiselect(df, "feasibility_warning")
    df = filter_by_multiselect(df, "sku_id")
    df = filter_by_multiselect(df, "supplier_id")

    metric_row(
        [
            ("Infeasible Options", len(df) - count_true(df, "is_feasible_supplier_option")),
            ("High MOQ Warnings", _warning_contains(df, "HIGH_MOQ_VS_DEMAND")),
            ("Low Yield Warnings", _warning_contains(df, "LOW_YIELD_REQUIRES_EXTRA_ORDERING")),
            ("Inactive Options", _warning_contains(df, "INACTIVE_SUPPLIER")),
        ]
    )

    col1, col2 = st.columns(2)
    with col1:
        _feasibility_warning_chart(df)
        make_bar_chart(df, "sku_id", "final_feasible_order_quantity", "Final Feasible Order Quantity by SKU")
    with col2:
        make_grouped_bar_chart(df, "supplier_id", ["moq", "reference_usable_quantity"], "MOQ vs Reference Usable Quantity")
        make_grouped_bar_chart(
            df,
            "supplier_id",
            ["yield_adjusted_order_quantity", "final_feasible_order_quantity"],
            "Yield-Adjusted vs Final Feasible Quantity",
        )

    priority = [
        "sku_id",
        "supplier_id",
        "is_feasible_supplier_option",
        "feasibility_warning",
        "feasibility_reason",
        "reference_usable_quantity",
        "reference_quantity_source",
        "yield_adjusted_order_quantity",
        "batch_rounded_order_quantity",
        "moq_adjusted_order_quantity",
        "final_feasible_order_quantity",
        "moq",
        "batch_size",
        "yield_rate",
        "is_supplier_active",
    ]
    show_table(df, priority)


def render_pipeline_outputs(data: dict[str, pd.DataFrame]) -> None:
    """Render expected output file status."""
    st.title("Pipeline Outputs")
    st.write("Expected Phase 2 output files and load status.")
    st.info("To refresh outputs, close any open CSV files and run python main.py.")

    rows = [file_status(path) for path in EXPECTED_OUTPUTS.values()]
    status_df = pd.DataFrame(rows)
    show_table(status_df, ["file", "exists", "rows", "columns", "last_modified"])

    for name, df in data.items():
        if not df.empty:
            with st.expander(f"Preview {EXPECTED_OUTPUTS[name].name}"):
                show_table(df.head(20), [])
        elif not EXPECTED_OUTPUTS[name].exists():
            st.warning(f"{EXPECTED_OUTPUTS[name].name} is missing. Run python main.py first.")


def _selected_sku_subset(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows for one SKU selected from the current dataframe."""
    if df.empty or "sku_id" not in df.columns:
        return df
    skus = sorted(df["sku_id"].dropna().astype(str).unique())
    if not skus:
        return df
    selected_sku = st.selectbox("SKU for comparison", skus)
    return df[df["sku_id"].astype(str) == selected_sku]


def _histogram(df: pd.DataFrame, column: str, title: str) -> None:
    """Render a histogram for numeric values."""
    if df.empty or column not in df.columns:
        st.info("Not enough data for this chart.")
        return
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    if values.empty:
        st.info("Not enough data for this chart.")
        return
    if PLOTLY_AVAILABLE:
        fig = px.histogram(values.to_frame(column), x=column, title=title)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(values.value_counts().sort_index())


def _cost_breakdown_chart(df: pd.DataFrame, cost_columns: list[str]) -> None:
    """Render stacked cost breakdown by supplier."""
    available = [column for column in cost_columns if column in df.columns]
    if df.empty or "supplier_id" not in df.columns or not available:
        st.info("Cost breakdown columns are unavailable.")
        return
    chart_df = df[["supplier_id", *available]].melt(id_vars="supplier_id", var_name="cost_component", value_name="cost")
    if PLOTLY_AVAILABLE:
        fig = px.bar(chart_df, x="supplier_id", y="cost", color="cost_component", title="Cost Breakdown by Supplier")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(chart_df.pivot_table(index="supplier_id", columns="cost_component", values="cost", aggfunc="sum"))


def _warning_contains(df: pd.DataFrame, warning: str) -> int:
    """Count feasibility warning occurrences."""
    if df.empty or "feasibility_warning" not in df.columns:
        return 0
    return int(df["feasibility_warning"].astype(str).str.contains(warning, regex=False).sum())


def _feasibility_warning_chart(df: pd.DataFrame) -> None:
    """Render counts for semicolon-separated feasibility warning codes."""
    if df.empty or "feasibility_warning" not in df.columns:
        st.info("No feasibility warning data available.")
        return
    warnings = (
        df["feasibility_warning"]
        .fillna("NONE")
        .astype(str)
        .str.split(";")
        .explode()
        .str.strip()
    )
    chart_df = warnings.value_counts().rename_axis("feasibility_warning").reset_index(name="count")
    make_bar_chart(chart_df, "feasibility_warning", "count", "Feasibility Warning Counts")


def main() -> None:
    """Run the Streamlit app."""
    data = load_all_outputs()

    st.sidebar.title("Phase 2 Module")
    # Future unified ERP navigation can mount this page router as one module.
    page = st.sidebar.radio(
        "Navigation",
        [
            "Overview",
            "Supplier Performance",
            "Supplier Trends",
            "Supplier-SKU Options",
            "Procurement Recommendations",
            "Risk & Cost Analysis",
            "Feasibility Review",
            "Pipeline Outputs",
        ],
    )

    if page == "Overview":
        render_overview(data)
    elif page == "Supplier Performance":
        render_supplier_performance(data)
    elif page == "Supplier Trends":
        render_supplier_trends(data)
    elif page == "Supplier-SKU Options":
        render_supplier_sku_options(data)
    elif page == "Procurement Recommendations":
        render_procurement_recommendations(data)
    elif page == "Risk & Cost Analysis":
        render_risk_cost_analysis(data)
    elif page == "Feasibility Review":
        render_feasibility_review(data)
    else:
        render_pipeline_outputs(data)


if __name__ == "__main__":
    main()
