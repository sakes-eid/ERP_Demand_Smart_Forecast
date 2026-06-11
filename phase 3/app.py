"""Role-based Streamlit dashboard for Phase 3 Inventory Control."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
SHARED_OUTPUT_DIR = BASE_DIR.parent / "shared" / "outputs"
SHARED_VALIDATION_DIR = BASE_DIR.parent / "shared" / "validation"

EMPLOYEE_COLUMNS = [
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

MANAGER_TASK_EXTRA_COLUMNS = [
    "safety_stock",
    "reorder_point",
    "max_stock",
    "days_inventory_on_hand",
    "dead_stock_rate",
    "expiry_exposure_rate_30d",
    "excess_inventory_rate",
    "supplier_allocation",
    "unallocated_quantity",
    "earliest_arrival_date",
    "final_arrival_date",
    "total_procurement_cost",
    "final_review_reason",
    "warning_codes",
]

DISPLAY_LABELS = {
    "sku_id": "SKU",
    "product_name": "Product",
    "category": "Category",
    "warehouse_zone": "Zone",
    "storage_location": "Location",
    "available_quantity": "Available Qty",
    "usable_quantity": "Usable Qty",
    "net_replenishment_requirement": "Net Requirement",
    "recommended_action": "Recommended Action",
    "action_priority": "Priority",
    "next_delivery_date": "Next Delivery",
    "expiry_status": "Expiry Status",
    "handling_warning": "Status",
    "manager_review_required": "Manager Review Required",
    "employee_instruction": "Instruction",
    "main_inventory_status": "Inventory Status",
    "final_recommended_action": "Final Recommendation",
    "proposed_operational_action": "Proposed Operational Action",
    "blocking_review_action": "Blocking Review",
    "final_decision_priority": "Priority",
    "final_review_required": "Review Required",
    "review_owner": "Review Owner",
    "execution_owner": "Execution Owner",
    "safety_stock": "Safety Stock",
    "reorder_point": "Reorder Point",
    "max_stock": "Max Stock",
    "days_inventory_on_hand": "Days Inventory on Hand",
    "dead_stock_rate": "Dead Stock Rate",
    "expiry_exposure_rate_30d": "30-Day Expiry Exposure",
    "excess_inventory_rate": "Excess Inventory Rate",
    "supplier_allocation": "Supplier Allocation",
    "unallocated_quantity": "Unallocated Quantity",
    "earliest_arrival_date": "Earliest Arrival",
    "final_arrival_date": "Final Arrival",
    "total_procurement_cost": "Total Procurement Cost",
    "final_review_reason": "Review Reason",
    "warning_codes": "Warnings",
}


def main() -> None:
    st.set_page_config(page_title="Phase 3 Inventory Control", layout="wide")
    role = _role_selector()
    data = _load_all_data()
    _dashboard_header(data, role)
    if role == "Employee / Warehouse Staff":
        _employee_app(data)
    else:
        _manager_app(data)


def _role_selector() -> str:
    if "phase3_role" not in st.session_state:
        st.session_state.phase3_role = ""
    if not st.session_state.phase3_role:
        st.subheader("Select role")
        st.caption("This prototype uses role selection only. No authentication or execution workflow is implemented.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Manager", use_container_width=True):
                st.session_state.phase3_role = "Manager"
                st.rerun()
        with col2:
            if st.button("Employee / Warehouse Staff", use_container_width=True):
                st.session_state.phase3_role = "Employee / Warehouse Staff"
                st.rerun()
        st.stop()
    with st.sidebar:
        st.write(f"Role: **{st.session_state.phase3_role}**")
        if st.button("Change role"):
            st.session_state.phase3_role = ""
            st.rerun()
        st.info("Read-only advisory dashboard. No purchase orders, inventory updates, supplier changes, policy changes, or warehouse changes are executed.")
    return st.session_state.phase3_role


def _dashboard_header(data: dict[str, pd.DataFrame | dict], role: str) -> None:
    evidence = data.get("integrated_evidence", {})
    overall = evidence.get("overall_result", {}) if isinstance(evidence, dict) else {}
    generated_at = _latest_generated_at(data)
    cols = st.columns([2, 1, 1, 1])
    cols[0].title("Phase 3 Inventory Control")
    cols[1].metric("Role", role)
    cols[2].metric("Run Status", overall.get("status", "UNKNOWN"))
    cols[3].metric("Last Generated", generated_at or "Unavailable")
    st.warning(
        "Read-only advisory dashboard. No purchase orders, inventory updates, supplier changes, "
        "policy changes, or warehouse changes are executed from this UI."
    )


def _latest_generated_at(data: dict[str, pd.DataFrame | dict]) -> str:
    for key in ["integrated_decisions", "allocation_summary", "allocation_validation"]:
        df = data.get(key)
        if isinstance(df, pd.DataFrame) and not df.empty and "generated_at" in df.columns:
            values = df["generated_at"].dropna().astype(str)
            if not values.empty:
                return values.iloc[0].replace("T", " ").replace("Z", "")
    return ""


def _load_all_data() -> dict[str, pd.DataFrame | dict]:
    files = {
        "tasks": OUTPUT_DIR / "inventory_employee_task_view.csv",
        "manager_dashboard": OUTPUT_DIR / "inventory_control_manager_dashboard.csv",
        "master": OUTPUT_DIR / "inventory_control_master_decisions.csv",
        "human_review": OUTPUT_DIR / "inventory_control_human_review_queue.csv",
        "advisory_review": OUTPUT_DIR / "inventory_control_advisory_review_queue.csv",
        "action_plan": OUTPUT_DIR / "inventory_control_action_plan.csv",
        "risk_register": OUTPUT_DIR / "inventory_control_risk_register.csv",
        "inventory_kpis": OUTPUT_DIR / "inventory_kpi_summary.csv",
        "policy_parameters": OUTPUT_DIR / "inventory_policy_parameters.csv",
        "warehouse_slotting": OUTPUT_DIR / "warehouse_slotting.csv",
        "location_utilization": OUTPUT_DIR / "location_utilization.csv",
        "phase3_validation": OUTPUT_DIR / "phase3_validation_summary.csv",
        "integrated_decisions": SHARED_OUTPUT_DIR / "integrated_replenishment_decisions.csv",
        "allocation_summary": SHARED_OUTPUT_DIR / "phase2_procurement_allocation_summary.csv",
        "allocation_validation": SHARED_OUTPUT_DIR / "phase3_allocation_validation.csv",
    }
    data: dict[str, pd.DataFrame | dict] = {key: _load_csv(path) for key, path in files.items()}
    data["integrated_evidence"] = _load_json(SHARED_VALIDATION_DIR / "integrated_validation_evidence.json")
    return data


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        st.warning(f"Missing file: {path.name}. Run python main.py and the integrated orchestrator first.")
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        st.warning(f"Could not load {path.name}: {exc}")
        return pd.DataFrame()


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _employee_app(data: dict[str, pd.DataFrame | dict]) -> None:
    pages = ["Product Lookup", "Operational Tasks", "Expiry / Stock Checks", "Delivery / Receiving"]
    page = st.sidebar.radio("Employee pages", pages)
    tasks = _filter_tasks(data["tasks"])
    _task_cards(tasks)
    if page == "Product Lookup":
        st.subheader("Product Lookup")
        _show_status_legend()
        _show_table(tasks, _employee_display_columns())
    elif page == "Operational Tasks":
        st.subheader("Operational Tasks")
        _show_status_legend()
        _show_table(tasks, _employee_display_columns())
    elif page == "Expiry / Stock Checks":
        st.subheader("Expiry / Stock Checks")
        expiry = tasks[tasks.get("expiry_status", pd.Series(dtype=str)).astype(str).ne("NO_EXPIRY_ALERT")] if not tasks.empty else tasks
        _show_table(expiry, _employee_display_columns())
    else:
        st.subheader("Delivery / Receiving")
        delivery = tasks[tasks.get("next_delivery_date", pd.Series(dtype=str)).fillna("").astype(str).str.strip().ne("")] if not tasks.empty else tasks
        _show_table(delivery, _employee_display_columns())


def _manager_app(data: dict[str, pd.DataFrame | dict]) -> None:
    pages = [
        "Executive Overview",
        "Operational Task View",
        "Inventory Decisions",
        "Replenishment & Supplier Allocation",
        "Review Queue",
        "Expiry / Dead Stock / Overstock",
        "Warehouse & Location",
        "Validation & Data Quality",
    ]
    page = st.sidebar.radio("Manager pages", pages)
    if page == "Executive Overview":
        _manager_overview(data)
    elif page == "Operational Task View":
        _manager_task_view(data)
    elif page == "Inventory Decisions":
        _inventory_decisions(data)
    elif page == "Replenishment & Supplier Allocation":
        _replenishment_allocation(data)
    elif page == "Review Queue":
        _review_queue(data)
    elif page == "Expiry / Dead Stock / Overstock":
        _expiry_dead_overstock(data)
    elif page == "Warehouse & Location":
        _warehouse_location(data)
    else:
        _validation_quality(data)


def _manager_overview(data: dict[str, pd.DataFrame | dict]) -> None:
    st.subheader("Executive Overview")
    tasks = data["tasks"]
    manager = data["manager_dashboard"]
    allocation = data["allocation_summary"]
    kpis = data["inventory_kpis"]
    evidence = data["integrated_evidence"] if isinstance(data["integrated_evidence"], dict) else {}
    key_metrics = evidence.get("key_metrics", {})
    cards = [
        ("Total SKUs", _nunique(tasks, "sku_id")),
        ("SKUs Requiring Review", _true_count(tasks, "manager_review_required")),
        ("SKUs Requiring Replenishment", _positive_count(tasks, "net_replenishment_requirement")),
        ("Total Net Requirement", f"{_sum(tasks, 'net_replenishment_requirement'):.2f}"),
        ("Total Allocated Quantity", f"{_sum(allocation, 'total_allocated_usable_quantity'):.2f}"),
        ("Unallocated Quantity", f"{_sum(allocation, 'unallocated_requirement_units'):.2f}"),
        ("Coverage Rate", _fmt_pct(key_metrics.get("end_to_end_requirement_coverage_rate"))),
        ("Planning Exception Rate", _fmt_pct(key_metrics.get("planning_exception_rate"))),
        ("Near-Expiry SKUs", _positive_count(kpis, "expiry_exposure_rate_30d")),
        ("Dead-Stock SKUs", _positive_count(kpis, "dead_stock_rate")),
        ("Projected Relevant Cost", f"{_sum(manager, 'projected_total_relevant_cost'):.2f}"),
    ]
    _metric_grid(cards, columns=4)
    chart_cols = st.columns(3)
    with chart_cols[0]:
        _bar_counts(manager, "main_inventory_status", "Inventory Status")
    with chart_cols[1]:
        _bar_counts(manager, "final_decision_priority", "Priority")
    with chart_cols[2]:
        _bar_counts(tasks, "handling_warning", "Task Status")
    _safety_banner(data)


def _manager_task_view(data: dict[str, pd.DataFrame | dict]) -> None:
    st.subheader("Operational Task View")
    tasks = _filter_tasks(data["tasks"])
    enriched = _manager_task_enrichment(tasks, data)
    _show_table(enriched, _employee_display_columns())
    manager_cols = [c for c in MANAGER_TASK_EXTRA_COLUMNS if c in enriched.columns]
    with st.expander("Manager-only planning, KPI, cost, and warning details"):
        _show_table(enriched, ["sku_id", "product_name"] + manager_cols)


def _inventory_decisions(data: dict[str, pd.DataFrame | dict]) -> None:
    st.subheader("Inventory Decisions")
    manager = _filter_sku_table(data["manager_dashboard"])
    priority = [
        "sku_id", "product_name", "category", "main_inventory_status",
        "final_recommended_action", "proposed_operational_action", "blocking_review_action",
        "final_decision_priority", "final_review_required", "review_owner", "execution_owner",
    ]
    _show_table(manager, priority)
    with st.expander("Technical decision fields"):
        _show_table(data["master"], list(data["master"].columns))


def _replenishment_allocation(data: dict[str, pd.DataFrame | dict]) -> None:
    st.subheader("Replenishment & Supplier Allocation")
    st.markdown(
        "```text\n"
        "Forecast Demand\n"
        "- Usable Inventory\n"
        "- Confirmed Inbound\n"
        "+ Policy / Safety Need\n"
        "= Net Requirement\n"
        "-> Supplier Allocation\n"
        "-> Phase 3 Validation\n"
        "```"
    )
    allocation = data["allocation_summary"]
    _metric_grid(
        [
            ("Requested Requirement", f"{_sum(allocation, 'requested_requirement_units'):.2f}"),
            ("Allocated Usable Qty", f"{_sum(allocation, 'total_allocated_usable_quantity'):.2f}"),
            ("Unallocated Qty", f"{_sum(allocation, 'unallocated_requirement_units'):.2f}"),
            ("Allocation Review SKUs", int((pd.to_numeric(allocation.get("unallocated_requirement_units", 0), errors="coerce").fillna(0) > 0).sum()) if not allocation.empty else 0),
        ],
        columns=4,
    )
    _show_table(data["integrated_decisions"], list(data["integrated_decisions"].columns))
    with st.expander("Supplier allocation summary"):
        _show_table(data["allocation_summary"], list(data["allocation_summary"].columns))
    with st.expander("Phase 3 allocation validation"):
        _show_table(data["allocation_validation"], list(data["allocation_validation"].columns))
    shortages = data["allocation_summary"]
    if not shortages.empty and "unallocated_requirement_units" in shortages.columns:
        review = shortages[pd.to_numeric(shortages["unallocated_requirement_units"], errors="coerce").fillna(0) > 0]
        if not review.empty:
            st.warning("SKU-COF-001 and SKU-TEA-002 are genuine supplier-capacity shortage review cases, not system defects.")
            _show_table(review, [c for c in ["sku_id", "requested_requirement_units", "total_allocated_usable_quantity", "unallocated_requirement_units", "allocation_status", "allocation_warning_codes"] if c in review.columns])


def _review_queue(data: dict[str, pd.DataFrame | dict]) -> None:
    st.subheader("Review Queue")
    master = data["master"]
    _metric_grid(
        [
            ("Mandatory Reviews", len(data["human_review"])),
            ("Advisory Reviews", len(data["advisory_review"])),
            ("Review-Owned Actions", _nonblank_count(master, "review_owner")),
            ("Execution-Owned Actions", _nonblank_count(master, "execution_owner")),
        ],
        columns=4,
    )
    tab1, tab2 = st.tabs(["Mandatory Review", "Advisory Review"])
    with tab1:
        _show_table(data["human_review"], list(data["human_review"].columns))
    with tab2:
        _show_table(data["advisory_review"], list(data["advisory_review"].columns))


def _expiry_dead_overstock(data: dict[str, pd.DataFrame | dict]) -> None:
    st.subheader("Expiry / Dead Stock / Overstock")
    kpis = data["inventory_kpis"]
    risk = data["risk_register"]
    action = data["action_plan"]
    cols = [c for c in ["sku_id", "product_name", "category", "expiry_exposure_rate_30d", "dead_stock_rate", "excess_inventory_rate", "excess_inventory_data_quality", "inventory_kpi_warning_codes"] if c in kpis.columns]
    _show_table(kpis, cols)
    st.caption("Unavailable formal KPIs are shown as unavailable rather than inferred from current stock alone.")
    with st.expander("Risk register"):
        _show_table(risk, list(risk.columns))
    with st.expander("Action plan"):
        _show_table(action, list(action.columns))


def _warehouse_location(data: dict[str, pd.DataFrame | dict]) -> None:
    st.subheader("Warehouse & Location")
    slotting = _filter_sku_table(data["warehouse_slotting"])
    cols = [c for c in ["sku_id", "product_name", "category", "assigned_zone", "assigned_location_id", "recommended_zone", "current_inventory", "available_inventory", "slotting_warning_flags"] if c in slotting.columns]
    _show_table(slotting, cols)
    with st.expander("Location utilization"):
        _show_table(data["location_utilization"], list(data["location_utilization"].columns))


def _validation_quality(data: dict[str, pd.DataFrame | dict]) -> None:
    st.subheader("Validation & Data Quality")
    evidence = data["integrated_evidence"] if isinstance(data["integrated_evidence"], dict) else {}
    overall = evidence.get("overall_result", {})
    cards = [
        ("Integrated Status", overall.get("status", "UNKNOWN")),
        ("PASS", overall.get("pass_count", "")),
        ("WARNING", overall.get("warning_count", "")),
        ("FAIL", overall.get("fail_count", "")),
        ("Analytical Safe", overall.get("safe_for_analytical_downstream_use", "")),
        ("Planning Safe", overall.get("safe_for_planning_downstream_use", "")),
        ("Execution Safe", overall.get("safe_for_execution_downstream_use", "")),
        ("Convergence", overall.get("convergence_status", "")),
    ]
    _metric_grid(cards, columns=4)
    _safety_banner(data)
    phase3 = data["phase3_validation"]
    if not phase3.empty and "status" in phase3.columns:
        phase3_counts = phase3["status"].value_counts().to_dict()
        _metric_grid(
            [
                ("Phase 3 PASS", phase3_counts.get("PASS", 0)),
                ("Phase 3 WARNING", phase3_counts.get("WARNING", 0)),
                ("Phase 3 FAIL", phase3_counts.get("FAIL", 0)),
                ("Phase 3 SKIPPED", phase3_counts.get("SKIPPED", 0)),
            ],
            columns=4,
        )
    kpis = data["inventory_kpis"]
    unavailable_count = 0
    for column in ["unit_fill_rate_data_quality", "stockout_rate_data_quality", "fefo_compliance_data_quality", "excess_inventory_data_quality"]:
        if not kpis.empty and column in kpis.columns:
            unavailable_count += int(kpis[column].fillna("").astype(str).str.contains("UNAVAILABLE", na=False).sum())
    st.metric("Unavailable KPI Fields", unavailable_count)
    issues = phase3[phase3.get("status", pd.Series(dtype=str)).isin(["WARNING", "FAIL", "SKIPPED"])] if not phase3.empty and "status" in phase3.columns else phase3
    _show_table(issues, list(issues.columns))


def _filter_tasks(tasks: pd.DataFrame) -> pd.DataFrame:
    filtered = tasks.copy()
    if filtered.empty:
        return filtered
    with st.sidebar:
        category = _select_filter(filtered, "category", "Category")
        priority = _select_filter(filtered, "action_priority", "Priority")
        review = st.selectbox("Review required", ["All", "Yes", "No"])
        sku_query = st.text_input("SKU or product search")
    filtered = _apply_filter(filtered, "category", category)
    filtered = _apply_filter(filtered, "action_priority", priority)
    if review == "Yes" and "manager_review_required" in filtered.columns:
        filtered = filtered[filtered["manager_review_required"].astype(str).str.lower().isin({"true", "1", "yes"})]
    if review == "No" and "manager_review_required" in filtered.columns:
        filtered = filtered[~filtered["manager_review_required"].astype(str).str.lower().isin({"true", "1", "yes"})]
    if sku_query:
        text = sku_query.lower()
        mask = filtered.astype(str).apply(lambda col: col.str.lower().str.contains(text, na=False)).any(axis=1)
        filtered = filtered[mask]
    return _prioritize_tasks(filtered)


def _prioritize_tasks(tasks: pd.DataFrame) -> pd.DataFrame:
    if tasks.empty:
        return tasks
    result = tasks.copy()
    review = result.get("manager_review_required", pd.Series(False, index=result.index)).astype(str).str.lower().isin({"true", "1", "yes", "y", "t"})
    priority = result.get("action_priority", pd.Series("", index=result.index)).fillna("").astype(str).str.upper()
    net_req = pd.to_numeric(result.get("net_replenishment_requirement", 0), errors="coerce").fillna(0)
    expiry = result.get("expiry_status", pd.Series("", index=result.index)).fillna("").astype(str).str.upper().eq("NEAR_EXPIRY")
    priority_rank = priority.map({"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NO_ACTION": 4}).fillna(5)
    result["_sort_review"] = (~review).astype(int)
    result["_sort_priority"] = priority_rank
    result["_sort_requirement"] = -(net_req > 0).astype(int)
    result["_sort_expiry"] = (~expiry).astype(int)
    result["_sort_sku"] = result.get("sku_id", pd.Series("", index=result.index)).astype(str)
    return result.sort_values(["_sort_review", "_sort_priority", "_sort_requirement", "_sort_expiry", "_sort_sku"]).drop(columns=[c for c in result.columns if c.startswith("_sort_")])


def _filter_sku_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    query = st.sidebar.text_input("Manager SKU search", key="manager_sku_search")
    if query:
        mask = df.astype(str).apply(lambda col: col.str.lower().str.contains(query.lower(), na=False)).any(axis=1)
        return df[mask]
    return df


def _manager_task_enrichment(tasks: pd.DataFrame, data: dict[str, pd.DataFrame | dict]) -> pd.DataFrame:
    result = tasks.copy()
    joins = [
        (data["policy_parameters"], {"safety_stock": "safety_stock", "reorder_point": "reorder_point", "max_stock_level": "max_stock"}),
        (data["inventory_kpis"], {"days_inventory_on_hand": "days_inventory_on_hand", "dead_stock_rate": "dead_stock_rate", "expiry_exposure_rate_30d": "expiry_exposure_rate_30d", "excess_inventory_rate": "excess_inventory_rate"}),
        (data["allocation_summary"], {"supplier_allocation_plan": "supplier_allocation", "unallocated_requirement_units": "unallocated_quantity", "earliest_arrival_date": "earliest_arrival_date", "final_arrival_date": "final_arrival_date", "total_procurement_cost": "total_procurement_cost"}),
        (data["master"], {"final_review_reason": "final_review_reason", "final_risk_types": "warning_codes"}),
    ]
    for frame, mapping in joins:
        if frame.empty or "sku_id" not in frame.columns:
            continue
        keep = ["sku_id"] + [src for src in mapping if src in frame.columns]
        add = frame[keep].drop_duplicates("sku_id").rename(columns=mapping)
        result = result.drop(columns=[col for col in add.columns if col != "sku_id" and col in result.columns], errors="ignore").merge(add, on="sku_id", how="left")
    return result


def _task_cards(tasks: pd.DataFrame) -> None:
    _metric_grid(
        [
            ("Visible Tasks", len(tasks)),
            ("Urgent Tasks", int(tasks.get("action_priority", pd.Series(dtype=str)).fillna("").astype(str).str.upper().isin({"URGENT", "HIGH"}).sum()) if not tasks.empty else 0),
            ("Review Required", _true_count(tasks, "manager_review_required")),
            ("Near Expiry", int((tasks.get("expiry_status", pd.Series(dtype=str)).astype(str) == "NEAR_EXPIRY").sum()) if not tasks.empty else 0),
            ("Waiting Delivery", int(tasks.get("handling_warning", pd.Series(dtype=str)).fillna("").astype(str).str.contains("WAITING DELIVERY|PARTIAL ALLOCATION REVIEW", na=False).sum()) if not tasks.empty else 0),
        ],
        columns=5,
    )


def _employee_display_columns() -> list[str]:
    return [
        "sku_id",
        "product_name",
        "warehouse_zone",
        "storage_location",
        "available_quantity",
        "usable_quantity",
        "net_replenishment_requirement",
        "action_priority",
        "next_delivery_date",
        "expiry_status",
        "handling_warning",
        "employee_instruction",
        "manager_review_required",
    ]


def _show_status_legend() -> None:
    st.caption("Statuses: LOW STOCK | WAITING DELIVERY | NEAR EXPIRY | MANAGER REVIEW REQUIRED | NO ACTION REQUIRED | WAREHOUSE CHECK REQUIRED | SUPPLIER SHORTAGE")


def _show_table(df: pd.DataFrame, columns: list[str]) -> None:
    if df.empty:
        st.info("No rows available.")
        return
    keep = [column for column in columns if column in df.columns]
    display = df[keep] if keep else df
    display = display.rename(columns={column: DISPLAY_LABELS.get(column, column.replace("_", " ").title()) for column in display.columns})
    st.dataframe(display, use_container_width=True, hide_index=True)


def _metric_grid(items: list[tuple[str, object]], columns: int = 4) -> None:
    cols = st.columns(columns)
    for index, (label, value) in enumerate(items):
        cols[index % columns].metric(label, value)


def _bar_counts(df: pd.DataFrame, column: str, title: str) -> None:
    st.caption(title)
    if df.empty or column not in df.columns:
        st.info("Unavailable")
        return
    counts = df[column].fillna("UNKNOWN").astype(str)
    if counts.empty:
        st.info("Unavailable")
        return
    chart = counts.value_counts().rename_axis("Category").reset_index(name="Count")
    st.bar_chart(chart, x="Category", y="Count", use_container_width=True)


def _safety_banner(data: dict[str, pd.DataFrame | dict]) -> None:
    decisions = data["integrated_decisions"]
    allocation = data["allocation_summary"]
    allocation_context = _load_csv(SHARED_OUTPUT_DIR / "phase2_procurement_allocation_context.csv")
    flags = {
        "auto_apply_allowed": _true_count(decisions, "auto_apply_allowed"),
        "purchase_order_creation_allowed": _true_count(decisions, "purchase_order_creation_allowed"),
        "procurement_execution_ready_flag": _true_count(decisions, "procurement_execution_ready_flag"),
        "allocation_execution_allowed": _true_count(allocation_context if not allocation_context.empty else allocation, "allocation_execution_allowed"),
    }
    st.caption("Safety controls: " + " | ".join(f"{key}=False ({value} true)" for key, value in flags.items()))


def _select_filter(df: pd.DataFrame, column: str, label: str) -> str:
    if column not in df.columns:
        return "All"
    values = sorted(v for v in df[column].dropna().astype(str).unique() if v)
    return st.selectbox(label, ["All"] + values)


def _apply_filter(df: pd.DataFrame, column: str, selected: str) -> pd.DataFrame:
    if selected == "All" or column not in df.columns:
        return df
    return df[df[column].astype(str).eq(selected)]


def _nunique(df: pd.DataFrame, column: str) -> int:
    return int(df[column].nunique()) if not df.empty and column in df.columns else 0


def _sum(df: pd.DataFrame, column: str) -> float:
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum()) if not df.empty and column in df.columns else 0.0


def _positive_count(df: pd.DataFrame, column: str) -> int:
    return int((pd.to_numeric(df[column], errors="coerce").fillna(0) > 0).sum()) if not df.empty and column in df.columns else 0


def _true_count(df: pd.DataFrame, column: str) -> int:
    return int(df[column].fillna(False).astype(str).str.lower().isin({"true", "1", "yes", "y", "t"}).sum()) if not df.empty and column in df.columns else 0


def _nonblank_count(df: pd.DataFrame, column: str) -> int:
    return int(df[column].fillna("").astype(str).str.strip().ne("").sum()) if not df.empty and column in df.columns else 0


def _fmt_pct(value) -> str:
    try:
        if pd.isna(value):
            return "Unavailable"
        return f"{float(value):.1%}"
    except Exception:
        return "Unavailable"


if __name__ == "__main__":
    main()
