"""Streamlit manager UI for Phase 4 production planning.

Run with:
    streamlit run "phase 4/app.py"
"""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
SHARED_OUTPUT_DIR = BASE_DIR.parent / "shared" / "outputs"

FILES = {
    "alt_summary": OUTPUT_DIR / "phase4_step8g_alternative_summary.csv",
    "recommendation": OUTPUT_DIR / "phase4_step8g_recommendation.csv",
    "tradeoff_analysis": OUTPUT_DIR / "phase4_step8g_tradeoff_analysis.csv",
    "decision_risks": OUTPUT_DIR / "phase4_step8g_decision_risks.csv",
    "step8g_manager_review": OUTPUT_DIR / "phase4_step8g_manager_review_queue.csv",
    "release_readiness": OUTPUT_DIR / "phase4_step8g_release_readiness.csv",
    "material_readiness": OUTPUT_DIR / "integrated_phase234_material_readiness.csv",
    "shortage_timeline": OUTPUT_DIR / "integrated_phase234_shortage_timeline.csv",
    "schedule_impact": OUTPUT_DIR / "integrated_phase234_schedule_impact.csv",
    "integrated_recommendation_check": OUTPUT_DIR / "integrated_phase234_recommendation_check.csv",
    "operation_slack": OUTPUT_DIR / "phase4_operation_slack_analysis.csv",
    "capacity_impact": OUTPUT_DIR / "phase4_schedule_alternative_capacity_impact.csv",
    "schedule_validation": OUTPUT_DIR / "phase4_schedule_alternative_validation.csv",
    "bom": BASE_DIR / "data" / "phase4_bom.csv",
    "bom_requirements": OUTPUT_DIR / "phase4_bom_component_requirements.csv",
    "component_operation_map": BASE_DIR / "data" / "phase4_component_operation_consumption_map.csv",
    "phase2_supplier_check": BASE_DIR.parent / "phase 2" / "outputs" / "phase4_component_supplier_check.csv",
    "phase3_inventory_check": BASE_DIR.parent / "phase 3" / "outputs" / "phase4_component_inventory_check.csv",
    "graph_nodes": OUTPUT_DIR / "integrated_phase234_graph_nodes.csv",
    "graph_edges": OUTPUT_DIR / "integrated_phase234_graph_edges.csv",
    "operation_detail": OUTPUT_DIR / "phase4_schedule_alternative_operation_detail.csv",
    "operation_segments": OUTPUT_DIR / "phase4_schedule_alternative_operation_segments.csv",
    "wip_access": OUTPUT_DIR / "phase4_wip_buffer_access_rules.csv",
    "wip_buffer": OUTPUT_DIR / "phase4_wip_buffer_status.csv",
    "wip_impact": OUTPUT_DIR / "phase4_schedule_alternative_wip_impact.csv",
    "shadow_wip": OUTPUT_DIR / "phase4_schedule_alternative_shadow_wip_ledger.csv",
    "maintenance_impact": OUTPUT_DIR / "phase4_schedule_alternative_maintenance_impact.csv",
    "maintenance_window_check": OUTPUT_DIR / "phase4_schedule_alternative_maintenance_window_check.csv",
    "maintenance_readiness": OUTPUT_DIR / "phase4_maintenance_readiness_context.csv",
    "maintenance_feasibility": OUTPUT_DIR / "phase4_maintenance_schedule_feasibility_context.csv",
    "maintenance_production_impact": OUTPUT_DIR / "phase4_maintenance_production_impact_context.csv",
    "breakdown_risk": OUTPUT_DIR / "phase4_breakdown_risk_context.csv",
    "maintenance_crew_context": OUTPUT_DIR / "phase4_maintenance_crew_capacity_context.csv",
    "spare_part_context": OUTPUT_DIR / "phase4_spare_part_requirement_context.csv",
    "maintenance_windows": SHARED_OUTPUT_DIR / "maintenance_schedule_candidate_windows.csv",
    "maintenance_due_status": SHARED_OUTPUT_DIR / "maintenance_due_status_context.csv",
    "maintenance_backlog": SHARED_OUTPUT_DIR / "maintenance_backlog_risk_summary.csv",
    "maintenance_crew_summary": SHARED_OUTPUT_DIR / "maintenance_crew_capacity_summary.csv",
    "maintenance_workload_by_skill": SHARED_OUTPUT_DIR / "maintenance_workload_by_skill.csv",
    "maintenance_spare_parts": SHARED_OUTPUT_DIR / "maintenance_spare_part_requirement_context.csv",
    "spare_part_review": SHARED_OUTPUT_DIR / "spare_part_manager_review_queue.csv",
    "workforce_auth": SHARED_OUTPUT_DIR / "workforce_machine_authorization_context.csv",
    "phase2_spare_supplier": BASE_DIR.parent / "phase 2" / "outputs" / "phase4_spare_part_supplier_check.csv",
    "phase3_spare_inventory": BASE_DIR.parent / "phase 3" / "outputs" / "phase4_spare_part_inventory_check.csv",
    "workstations": BASE_DIR / "data" / "workstations.csv",
    "machines": BASE_DIR / "data" / "machines.csv",
    "labor_resources": BASE_DIR / "data" / "labor_resources.csv",
    "resource_calendar": BASE_DIR / "data" / "resource_calendar.csv",
    "ui_validation": OUTPUT_DIR / "phase4_ui_validation.csv",
}


def main() -> None:
    st.set_page_config(page_title="Phase 4 Production Planning", layout="wide")
    data = _load_all_data()
    _sidebar(data)
    _header()
    page_label = st.sidebar.selectbox("Open page", [
        "Planning | Manager Overview",
        "Planning | Production Flow Graph",
        "Planning | Production Timeline",
        "Materials & Resources | BOM & Materials",
        "Materials & Resources | Capacity & WIP",
        "Materials & Resources | Maintenance",
        "Decision | Decision & Release Readiness",
    ])
    page = page_label.split(" | ", 1)[1]
    if page == "Manager Overview":
        _manager_overview(data)
    elif page == "Production Flow Graph":
        _production_flow_graph(data)
    elif page == "BOM & Materials":
        _bom_materials_page(data)
    elif page == "Production Timeline":
        _production_timeline_page(data)
    elif page == "Capacity & WIP":
        _capacity_wip_page(data)
    elif page == "Maintenance":
        _maintenance_page(data)
    else:
        _decision_release_page(data)


def _sidebar(data: dict[str, pd.DataFrame]) -> None:
    with st.sidebar:
        st.title("Phase 4")
        st.caption("Production planning manager UI")
        st.markdown("### Planning")
        st.caption("Manager Overview | Production Flow Graph | Production Timeline")
        st.markdown("### Materials & Resources")
        st.caption("BOM & Materials | Capacity & WIP | Maintenance")
        st.markdown("### Decision")
        st.caption("Decision & Release Readiness")
        st.info("Read-only advisory interface. No production orders, releases, dispatches, reservations, consumption, or execution transactions are created.")
        validation = data["ui_validation"]
        if not validation.empty and "status" in validation.columns:
            counts = validation["status"].value_counts().to_dict()
            st.caption(f"UI validation: PASS {counts.get('PASS', 0)} | WARNING {counts.get('WARNING', 0)} | FAIL {counts.get('FAIL', 0)}")


def _header() -> None:
    st.title("Production Planning Manager")
    st.caption("Manager overview and arrow-on-node production flow from validated Phase 4, Step 8G, and Phase 2-3-4 integration outputs.")


def _manager_overview(data: dict[str, pd.DataFrame]) -> None:
    summary = data["alt_summary"]
    rec = _first_row(data["recommendation"])
    readiness = data["release_readiness"]
    material = data["material_readiness"]

    st.subheader("Manager Overview")
    if summary.empty or not rec:
        st.warning("Manager decision outputs are missing. Run the Phase 4 and integration refresh first.")
        return

    st.caption("Overall Planning Metric values come from Step 8G. SKU-specific evidence appears on the filtered pages.")
    recommended_id = str(rec.get("recommended_alternative_id", ""))
    recommended = summary[summary["alternative_id"].astype(str) == recommended_id]
    recommended_row = recommended.iloc[0].to_dict() if not recommended.empty else {}
    release_row = readiness[readiness.get("readiness_row_type", pd.Series(dtype=str)).astype(str) == "OVERALL"]
    release_status = _cell(release_row, "release_readiness_status") or str(rec.get("approval_status", ""))

    material_shortage = _sum(material, "remaining_shortage_qty")
    late_count = int((material.get("material_readiness_status", pd.Series(dtype=str)).astype(str) == "LATE_INBOUND_REVIEW").sum()) if not material.empty else 0
    ready_count = int((material.get("material_readiness_status", pd.Series(dtype=str)).astype(str) == "READY_ON_TIME").sum()) if not material.empty else 0

    st.markdown("#### Decision")
    with st.container(border=True):
        cols = st.columns(5)
        cols[0].metric("Recommended Alternative", recommended_id or "Unavailable")
        cols[1].write("Recommendation Status")
        cols[1].code(str(rec.get("recommendation_status", "Unavailable")))
        cols[2].metric("Demand Coverage", _pct(recommended_row.get("demand_coverage_pct")))
        cols[3].metric("Completed Qty", _fmt(recommended_row.get("completed_full_route_qty")))
        cols[4].metric("Unscheduled Qty", _fmt(recommended_row.get("unscheduled_qty")))

    st.markdown("#### Constraints / Readiness")
    with st.container(border=True):
        cols = st.columns(5)
        cols[0].metric("Main Bottleneck", recommended_row.get("main_bottleneck_workstation", "Unavailable"))
        cols[1].metric("Unresolved Shortage", _fmt(material_shortage))
        cols[2].metric("Late Inbound", late_count)
        cols[3].metric("Material Ready", ready_count)
        cols[4].write("Release Readiness")
        cols[4].code(str(release_status or "Unavailable"))

    if str(release_status) == "NOT_READY_FOR_RELEASE":
        st.error("NOT_READY_FOR_RELEASE")
    else:
        st.warning(release_status or "Release readiness unavailable")

    st.subheader("Alternative Comparison")
    priority = [
        "alternative_id",
        "alternative_name",
        "step8f_status",
        "planned_demand_qty",
        "completed_full_route_qty",
        "demand_coverage_pct",
        "unscheduled_qty",
        "scheduled_processing_minutes",
        "setup_minutes",
        "setup_switch_count",
        "main_bottleneck_workstation",
        "buffer_blocked_qty",
        "wip_blocked_qty",
        "maintenance_review_count",
        "validated_real_cost",
        "assumed_cost_or_penalty",
        "cost_confidence_level",
        "upstream_warning_count",
        "recommendation_rank",
    ]
    st.dataframe(_display_columns(summary, priority), width="stretch", hide_index=True)


def _production_flow_graph(data: dict[str, pd.DataFrame]) -> None:
    nodes = data["graph_nodes"]
    edges = data["graph_edges"]
    if nodes.empty or edges.empty:
        st.warning("Integrated graph outputs are missing. Run the integration refresh first.")
        return

    st.subheader("Interactive Arrow-on-Node Production Flow")
    control_cols = st.columns([1.3, 1.7, 1.1])
    sku = control_cols[0].selectbox("Finished SKU", sorted(nodes["finished_sku"].dropna().astype(str).unique()))
    sku_nodes = nodes[nodes["finished_sku"].astype(str) == sku]
    candidates = sorted(sku_nodes["schedule_candidate_id"].dropna().astype(str).unique())
    candidate = control_cols[1].selectbox("Schedule candidate / planning week", candidates)
    selected_alt = "ALT-BASELINE"
    control_cols[2].text_input("Graph basis", selected_alt, disabled=True)
    st.info("Production Flow Graph is locked to ALT-BASELINE because the integrated graph source is not alternative-specific. The six-alternative comparison remains available on Manager Overview.")

    toggle_cols = st.columns(5)
    show_critical = toggle_cols[0].checkbox("Critical path", value=True)
    show_utilization = toggle_cols[1].checkbox("Utilization", value=True)
    show_wip = toggle_cols[2].checkbox("WIP buffers", value=True)
    show_materials = toggle_cols[3].checkbox("Materials", value=True)
    show_maintenance = toggle_cols[4].checkbox("Maintenance", value=True)

    filtered_nodes = sku_nodes[sku_nodes["schedule_candidate_id"].astype(str) == candidate].copy()
    filtered_edges = edges[(edges["finished_sku"].astype(str) == sku) & (edges["schedule_candidate_id"].astype(str) == candidate)].copy()
    operation_rows = _operation_detail(data, selected_alt, candidate)
    material_rows = data["material_readiness"][data["material_readiness"].get("schedule_candidate_id", pd.Series(dtype=str)).astype(str) == candidate] if not data["material_readiness"].empty else pd.DataFrame()

    graph_html, counts = _build_graph_html(
        filtered_nodes,
        filtered_edges,
        operation_rows,
        data,
        selected_alt,
        candidate,
        show_critical,
        show_utilization,
        show_wip,
        show_materials,
        show_maintenance,
    )
    components.html(graph_html, height=max(520, counts["height"]), scrolling=True)

    st.caption(
        f"Rendered {counts['operation_nodes']} operation nodes, {counts['edge_count']} dependency edges, "
        f"{counts['wip_nodes']} WIP buffer nodes, {counts['critical_nodes']} critical-path nodes, "
        f"{counts['bottleneck_nodes']} bottleneck nodes, and {counts['maintenance_indicators']} maintenance indicators."
    )

    st.caption("Node click selection is not enabled in this lightweight HTML graph. Use the operation selector below; it is bound to the same candidate-specific node IDs shown in the graph.")
    op_options = [f"{row.operation_id} | {row.operation_name}" for row in filtered_nodes.sort_values("operation_id").itertuples()]
    selected = st.selectbox("Operation detail", op_options)
    selected_op = selected.split(" | ", 1)[0]
    _operation_detail_panel(filtered_nodes, operation_rows, material_rows, data, selected_alt, selected_op)


def _bom_materials_page(data: dict[str, pd.DataFrame]) -> None:
    material = data["material_readiness"]
    bom = data["bom"]
    mapping = data["component_operation_map"]
    impact = data["schedule_impact"]
    if material.empty:
        st.warning("Integrated material readiness output is missing. Run the Phase 2-3-4 integration refresh first.")
        return

    st.subheader("BOM & Materials")
    control_cols = st.columns([1.2, 1.8])
    sku = control_cols[0].selectbox("Finished SKU", sorted(material["finished_sku"].dropna().astype(str).unique()), key="bom_sku")
    sku_material = material[material["finished_sku"].astype(str) == sku]
    candidates = sorted(sku_material["schedule_candidate_id"].dropna().astype(str).unique())
    candidate = control_cols[1].selectbox("Schedule candidate / planning week", candidates, key="bom_candidate")
    selected_material = sku_material[sku_material["schedule_candidate_id"].astype(str) == candidate].copy()

    st.caption("Read-only cross-phase material view. Consuming operations come only from the explicit component-operation map and integrated readiness output.")
    _bom_structure_section(bom, mapping, sku)
    _material_kpis(selected_material)
    _integrated_material_table(selected_material, bom)
    _component_detail(selected_material, impact, bom, data)
    _shortage_focus(selected_material)


def _production_timeline_page(data: dict[str, pd.DataFrame]) -> None:
    segments = data["operation_segments"]
    detail = data["operation_detail"]
    if segments.empty or detail.empty:
        st.warning("Step 8F operation segment/detail outputs are missing. Run the validated planning pipeline first.")
        return

    st.subheader("Production Timeline")
    selected_alt = "ALT-BASELINE"
    st.info("Production Timeline is locked to ALT-BASELINE until alternative-specific integrated timeline evidence is available.")

    base_detail = detail[detail["alternative_id"].astype(str) == selected_alt].copy()
    base_segments = segments[segments["alternative_id"].astype(str) == selected_alt].copy()
    if base_detail.empty:
        st.warning("No ALT-BASELINE operation detail rows are available.")
        return

    controls = st.columns([1.2, 1.8, 1.1])
    sku = controls[0].selectbox("Finished SKU", sorted(base_detail["finished_sku"].dropna().astype(str).unique()), key="timeline_sku")
    sku_detail = base_detail[base_detail["finished_sku"].astype(str) == sku].copy()
    candidates = sorted(sku_detail["schedule_candidate_id"].dropna().astype(str).unique())
    candidate = controls[1].selectbox("Schedule candidate / planning week", candidates, key="timeline_candidate")
    view_mode = controls[2].selectbox("View mode", ["Product / Route", "Workstation"], key="timeline_view_mode")

    op_detail = sku_detail[sku_detail["schedule_candidate_id"].astype(str) == candidate].copy()
    op_segments = base_segments[
        (base_segments["finished_sku"].astype(str) == sku)
        & (base_segments["schedule_candidate_id"].astype(str) == candidate)
    ].copy()
    timeline = _timeline_rows(op_segments, op_detail, data, selected_alt, candidate)

    toggle_cols = st.columns(6)
    overlays = {
        "critical": toggle_cols[0].checkbox("Critical path", value=True, key="timeline_critical"),
        "bottleneck": toggle_cols[1].checkbox("Bottlenecks", value=True, key="timeline_bottleneck"),
        "material": toggle_cols[2].checkbox("Material readiness", value=True, key="timeline_material"),
        "buffer": toggle_cols[3].checkbox("Buffer delays", value=True, key="timeline_buffer"),
        "setup": toggle_cols[4].checkbox("Setup", value=True, key="timeline_setup"),
        "maintenance": toggle_cols[5].checkbox("Maintenance", value=True, key="timeline_maintenance"),
    }

    _timeline_kpis(timeline, op_detail)
    _timeline_chart(timeline, view_mode, overlays, data, selected_alt)
    _timeline_unscheduled_summary(op_detail, data, candidate)
    _timeline_operation_detail(timeline, op_detail, data, selected_alt, candidate)


def _timeline_rows(segments: pd.DataFrame, detail: pd.DataFrame, data: dict[str, pd.DataFrame], alternative_id: str, candidate_id: str) -> pd.DataFrame:
    if segments.empty:
        return pd.DataFrame()
    rows = segments.copy()
    rows["_start"] = pd.to_datetime(rows.get("proposed_start_datetime", ""), errors="coerce")
    rows["_end"] = pd.to_datetime(rows.get("proposed_end_datetime", ""), errors="coerce")
    rows = rows[rows["_start"].notna() & rows["_end"].notna() & (rows["_end"] > rows["_start"]) & (pd.to_numeric(rows.get("segment_scheduled_qty", 0), errors="coerce").fillna(0) > 0)].copy()
    if rows.empty:
        return rows

    detail_cols = [
        "operation_id",
        "operation_sequence",
        "critical_path_flag",
        "operation_schedule_status",
        "schedule_blocker_reason",
        "schedulable_production_qty",
        "requested_production_qty",
        "buffer_capacity_status",
        "buffer_capacity_blocker_reason",
        "wip_buffer_id",
        "slack_time_minutes",
    ]
    available_detail_cols = [c for c in detail_cols if c in detail.columns]
    if available_detail_cols:
        rows = rows.merge(detail[available_detail_cols].drop_duplicates("operation_id"), on="operation_id", how="left", suffixes=("", "_detail"))

    graph_nodes = data["graph_nodes"]
    if not graph_nodes.empty:
        node_cols = ["operation_id", "utilization_pct", "bottleneck_status", "material_readiness_status", "wip_readiness_status", "buffer_status", "slack_time_minutes"]
        node_subset = graph_nodes[
            (graph_nodes["schedule_candidate_id"].astype(str) == candidate_id)
            & (graph_nodes["finished_sku"].astype(str) == str(rows["finished_sku"].iloc[0]))
        ][[c for c in node_cols if c in graph_nodes.columns]].drop_duplicates("operation_id")
        rows = rows.merge(node_subset, on="operation_id", how="left", suffixes=("", "_node"))

    schedule_impact = data["schedule_impact"]
    if not schedule_impact.empty:
        impact_cols = ["operation_id", "schedule_impact_status", "blocker_reason", "remaining_shortage_qty", "late_component_count"]
        impact_subset = schedule_impact[schedule_impact["schedule_candidate_id"].astype(str) == candidate_id][[c for c in impact_cols if c in schedule_impact.columns]].drop_duplicates("operation_id")
        rows = rows.merge(impact_subset, on="operation_id", how="left", suffixes=("", "_impact"))

    wip_impact = data["wip_impact"]
    if not wip_impact.empty:
        wip_subset = wip_impact[
            (wip_impact["alternative_id"].astype(str) == alternative_id)
            & (wip_impact["finished_sku"].astype(str) == str(rows["finished_sku"].iloc[0]))
        ]
        wip_cols = ["operation_id", "wip_impact_status", "wip_shortage_qty", "buffer_delay_minutes", "buffer_capacity_status"]
        rows = rows.merge(wip_subset[[c for c in wip_cols if c in wip_subset.columns]].drop_duplicates("operation_id"), on="operation_id", how="left", suffixes=("", "_wip"))

    rows["operation_sequence"] = pd.to_numeric(rows.get("operation_sequence", rows.get("operation_sequence_detail", 0)), errors="coerce").fillna(0)
    rows["critical_path_flag_display"] = rows.get("critical_path_flag", False).map(_truthy) if "critical_path_flag" in rows.columns else False
    rows["bottleneck_flag_display"] = rows.get("bottleneck_status", pd.Series("", index=rows.index)).astype(str).str.upper().isin({"HIGH", "CRITICAL"})
    rows["partial_flag_display"] = rows.get("operation_schedule_status", pd.Series("", index=rows.index)).astype(str).str.contains("PARTIAL|UNSCHEDULED|BLOCK", case=False, regex=True)
    rows["buffer_delayed_flag_display"] = pd.to_numeric(rows.get("buffer_delay_minutes", 0), errors="coerce").fillna(0) > 0
    rows["material_constrained_flag_display"] = rows.get("schedule_impact_status", pd.Series("", index=rows.index)).astype(str).str.contains("LATE|SHORT|UNAVAILABLE|REVIEW", case=False, regex=True)
    rows["timeline_status"] = rows.apply(lambda row: _timeline_status(row, {
        "critical": True,
        "bottleneck": True,
        "material": True,
        "buffer": True,
        "setup": True,
    }), axis=1)
    rows["operation_axis"] = rows["operation_sequence"].astype(int).astype(str).str.zfill(3) + " | " + rows["operation_name"].astype(str)
    rows["workstation_axis"] = rows["workstation_id"].astype(str)
    rows["machine_units_display"] = rows.get("assigned_machine_unit_ids", pd.Series("", index=rows.index)).fillna("").astype(str)
    rows["labor_units_display"] = rows.get("assigned_labor_unit_ids", pd.Series("", index=rows.index)).fillna("").astype(str)
    rows["segment_label"] = rows["operation_id"].astype(str) + " segment " + rows["segment_sequence"].astype(str)
    return rows.sort_values(["operation_sequence", "_start", "segment_sequence"])


def _timeline_status(row: pd.Series, overlays: dict[str, bool]) -> str:
    if overlays.get("critical", True) and _truthy(row.get("critical_path_flag")):
        return "Critical Path"
    if overlays.get("bottleneck", True) and str(row.get("bottleneck_status", "")).upper() in {"HIGH", "CRITICAL"}:
        return "Bottleneck"
    if overlays.get("material", True) and any(token in str(row.get("schedule_impact_status", "")).upper() for token in ["LATE", "SHORT", "UNAVAILABLE", "REVIEW"]):
        return "Material Constrained"
    if overlays.get("buffer", True) and (_num(row.get("buffer_delay_minutes")) > 0 or "BLOCK" in str(row.get("buffer_capacity_status", "")).upper()):
        return "Buffer Delayed"
    if overlays.get("setup", True) and _num(row.get("segment_setup_minutes")) > 0:
        return "Setup Included"
    return "Scheduled"


def _timeline_kpis(timeline: pd.DataFrame, detail: pd.DataFrame) -> None:
    scheduled_ops = timeline["operation_id"].nunique() if not timeline.empty else 0
    scheduled_segments = len(timeline)
    partial_ops = int(detail.get("operation_schedule_status", pd.Series(dtype=str)).astype(str).str.contains("PARTIAL|UNSCHEDULED", case=False, regex=True).sum()) if not detail.empty else 0
    blocked_ops = int(detail.get("operation_schedule_status", pd.Series(dtype=str)).astype(str).str.contains("BLOCK|UNSCHEDULED", case=False, regex=True).sum()) if not detail.empty else 0
    total_processing = _sum(timeline, "segment_processing_minutes")
    total_setup = _sum(timeline, "segment_setup_minutes")
    critical_count = int(detail.get("critical_path_flag", pd.Series(dtype=str)).map(_truthy).sum()) if not detail.empty and "critical_path_flag" in detail.columns else 0
    bottleneck = _main_bottleneck_from_timeline(timeline)
    earliest = _clean_datetime(timeline["_start"].min()) if not timeline.empty else ""
    latest = _clean_datetime(timeline["_end"].max()) if not timeline.empty else ""

    cols = st.columns(5)
    cols[0].metric("Scheduled Operations", scheduled_ops)
    cols[1].metric("Scheduled Segments", scheduled_segments)
    cols[2].metric("Partial Ops", partial_ops)
    cols[3].metric("Blocked Ops", blocked_ops)
    cols[4].metric("Critical-Path Ops", critical_count)
    cols = st.columns(5)
    cols[0].metric("Processing Minutes", _fmt(total_processing))
    cols[1].metric("Setup Minutes", _fmt(total_setup))
    cols[2].metric("Bottleneck Workstation", bottleneck or "Unavailable")
    cols[3].metric("Earliest Start", earliest or "Unavailable")
    cols[4].metric("Latest Finish", latest or "Unavailable")


def _timeline_chart(timeline: pd.DataFrame, view_mode: str, overlays: dict[str, bool], data: dict[str, pd.DataFrame], alternative_id: str) -> None:
    st.subheader("Scheduled Segments")
    if timeline.empty:
        st.info("No scheduled dated segments are available for this selection.")
        return
    hover_cols = [
        "operation_id",
        "operation_name",
        "workstation_id",
        "machine_units_display",
        "labor_units_display",
        "segment_sequence",
        "segment_scheduled_qty",
        "segment_processing_minutes",
        "segment_setup_minutes",
        "segment_total_minutes",
        "operation_schedule_status",
        "schedule_impact_status",
        "buffer_capacity_status",
        "wip_impact_status",
        "slack_time_minutes",
    ]
    color_col = "timeline_status"
    timeline = timeline.copy()
    timeline[color_col] = timeline.apply(lambda row: _timeline_status(row, overlays), axis=1)
    fig = px.timeline(
        timeline,
        x_start="_start",
        x_end="_end",
        y="operation_axis" if view_mode == "Product / Route" else "workstation_axis",
        color=color_col,
        hover_data=[c for c in hover_cols if c in timeline.columns],
        text="segment_sequence",
    )
    if view_mode == "Product / Route":
        order = timeline.sort_values(["operation_sequence", "_start"])["operation_axis"].drop_duplicates().tolist()
        fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(order)))
    else:
        order = timeline.sort_values(["workstation_id", "_start"])["workstation_axis"].drop_duplicates().tolist()
        fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(order)))
    fig.update_layout(
        height=max(460, min(900, 70 * max(1, timeline["operation_axis" if view_mode == "Product / Route" else "workstation_axis"].nunique()))),
        xaxis_title="Scheduled time",
        yaxis_title="Operation" if view_mode == "Product / Route" else "Workstation",
        legend_title="Status",
        margin=dict(l=10, r=10, t=30, b=10),
    )
    fig.update_traces(textposition="inside", insidetextanchor="middle")
    if overlays.get("maintenance", True):
        _add_maintenance_windows(fig, data, alternative_id, timeline)
    st.plotly_chart(fig, width="stretch")
    if view_mode == "Workstation":
        st.caption("Workstation view uses actual segment timestamps and machine/labor unit IDs in hover. Parallel work is not collapsed into fake sequential work.")


def _add_maintenance_windows(fig, data: dict[str, pd.DataFrame], alternative_id: str, timeline: pd.DataFrame) -> None:
    maint = data["maintenance_window_check"]
    if maint.empty:
        return
    segment_ids = set(timeline.get("operation_segment_id", pd.Series(dtype=str)).astype(str))
    subset = maint[
        (maint["alternative_id"].astype(str) == alternative_id)
        & (maint["production_operation_segment_id"].astype(str).isin(segment_ids))
    ].copy()
    subset["_m_start"] = pd.to_datetime(subset.get("maintenance_start_datetime", ""), errors="coerce")
    subset["_m_end"] = pd.to_datetime(subset.get("maintenance_end_datetime", ""), errors="coerce")
    subset = subset[subset["_m_start"].notna() & subset["_m_end"].notna() & (subset["_m_end"] > subset["_m_start"])]
    for _, row in subset.drop_duplicates(["_m_start", "_m_end", "machine_id"]).iterrows():
        fig.add_vrect(
            x0=row["_m_start"],
            x1=row["_m_end"],
            fillcolor="#b42318",
            opacity=0.14,
            line_width=0,
            annotation_text="maintenance",
            annotation_position="top left",
        )


def _timeline_unscheduled_summary(detail: pd.DataFrame, data: dict[str, pd.DataFrame], candidate_id: str) -> None:
    st.subheader("Unscheduled / Partial Work")
    if detail.empty:
        st.info("No operation detail rows are available.")
        return
    rows = detail.copy()
    rows["unscheduled_qty"] = pd.to_numeric(rows.get("requested_production_qty", 0), errors="coerce").fillna(0) - pd.to_numeric(rows.get("schedulable_production_qty", 0), errors="coerce").fillna(0)
    rows = rows[(rows["unscheduled_qty"] > 0.0001) | rows.get("operation_schedule_status", pd.Series("", index=rows.index)).astype(str).str.contains("PARTIAL|BLOCK|UNSCHEDULED", case=False, regex=True)].copy()
    if rows.empty:
        st.success("No partial or blocked operation rows for this candidate.")
        return
    impact = data["schedule_impact"]
    if not impact.empty:
        impact_subset = impact[impact["schedule_candidate_id"].astype(str) == candidate_id][["operation_id", "schedule_impact_status", "blocker_reason"]].drop_duplicates("operation_id")
        rows = rows.merge(impact_subset, on="operation_id", how="left", suffixes=("", "_material"))
    cols = [
        "operation_id",
        "operation_name",
        "workstation_id",
        "requested_production_qty",
        "schedulable_production_qty",
        "unscheduled_qty",
        "operation_schedule_status",
        "schedule_blocker_reason",
        "schedule_impact_status",
        "buffer_capacity_status",
        "quantity_support_blocker_reason",
    ]
    st.dataframe(_display_columns(rows, cols), hide_index=True, width="stretch")


def _timeline_operation_detail(timeline: pd.DataFrame, detail: pd.DataFrame, data: dict[str, pd.DataFrame], alternative_id: str, candidate_id: str) -> None:
    st.subheader("Operation / Segment Detail")
    if detail.empty:
        st.info("No operation detail rows are available.")
        return
    scheduled_options = []
    if not timeline.empty:
        scheduled_options = [f"SEGMENT | {r.operation_segment_id} | {r.operation_name}" for r in timeline.sort_values(["_start", "operation_id", "segment_sequence"]).itertuples()]
    op_options = [f"OPERATION | {r.operation_id} | {r.operation_name}" for r in detail.sort_values("operation_sequence").itertuples()]
    selected = st.selectbox("Operation or segment", scheduled_options + op_options, key="timeline_detail_selector")
    parts = selected.split(" | ", 2)
    selected_type, selected_id = parts[0], parts[1]
    if selected_type == "SEGMENT" and not timeline.empty:
        seg = timeline[timeline["operation_segment_id"].astype(str) == selected_id].iloc[0].to_dict()
        op = detail[detail["operation_id"].astype(str) == str(seg.get("operation_id"))].iloc[0].to_dict()
        maint = _maintenance_status(data, alternative_id, str(seg.get("operation_id", "")), op)
        material_status = _operation_material_status(data, candidate_id, str(seg.get("operation_id", "")))
        st.dataframe(pd.DataFrame([{
            "operation": seg.get("operation_name", ""),
            "workstation": seg.get("workstation_id", ""),
            "segment_sequence": seg.get("segment_sequence", ""),
            "start": _clean_datetime(seg.get("_start")),
            "end": _clean_datetime(seg.get("_end")),
            "scheduled_qty": seg.get("segment_scheduled_qty", ""),
            "utilization_pct": seg.get("utilization_pct", ""),
            "slack_minutes": seg.get("slack_time_minutes", ""),
            "critical_path": seg.get("critical_path_flag", ""),
            "setup_minutes": seg.get("segment_setup_minutes", ""),
            "material_readiness": material_status.get("status", ""),
            "wip_buffer_status": seg.get("buffer_capacity_status", ""),
            "blocker_reason": op.get("schedule_blocker_reason", "") or material_status.get("blocker", ""),
            "maintenance_status": maint.get("maintenance_status", ""),
        }]), hide_index=True, width="stretch")
    else:
        op = detail[detail["operation_id"].astype(str) == selected_id].iloc[0].to_dict()
        maint = _maintenance_status(data, alternative_id, selected_id, op)
        material_status = _operation_material_status(data, candidate_id, selected_id)
        st.dataframe(pd.DataFrame([{
            "operation": op.get("operation_name", ""),
            "workstation": op.get("workstation_id", ""),
            "start": op.get("proposed_start_datetime", ""),
            "end": op.get("proposed_end_datetime", ""),
            "scheduled_qty": op.get("schedulable_production_qty", ""),
            "requested_qty": op.get("requested_production_qty", ""),
            "slack_minutes": op.get("slack_time_minutes", ""),
            "critical_path": op.get("critical_path_flag", ""),
            "setup_minutes": op.get("actual_sequence_setup_minutes", ""),
            "material_readiness": material_status.get("status", ""),
            "wip_buffer_status": op.get("buffer_capacity_status", ""),
            "blocker_reason": op.get("schedule_blocker_reason", "") or material_status.get("blocker", ""),
            "maintenance_status": maint.get("maintenance_status", ""),
        }]), hide_index=True, width="stretch")


def _capacity_wip_page(data: dict[str, pd.DataFrame]) -> None:
    alternative_id = "ALT-BASELINE"
    detail = data["operation_detail"]
    segments = data["operation_segments"]
    capacity = data["capacity_impact"]
    if detail.empty or segments.empty or capacity.empty:
        st.warning("Step 8F capacity, operation detail, or segment evidence is missing. Run the validated planning pipeline first.")
        return

    st.subheader("Capacity & WIP")
    st.info("Capacity & WIP is locked to ALT-BASELINE because it is the current integrated reference schedule.")

    base_detail = detail[detail["alternative_id"].astype(str) == alternative_id].copy()
    controls = st.columns([1.2, 1.8])
    sku = controls[0].selectbox("Finished SKU", sorted(base_detail["finished_sku"].dropna().astype(str).unique()), key="capwip_sku")
    sku_detail = base_detail[base_detail["finished_sku"].astype(str) == sku]
    candidate = controls[1].selectbox("Schedule candidate / planning week", sorted(sku_detail["schedule_candidate_id"].dropna().astype(str).unique()), key="capwip_candidate")

    op_detail = sku_detail[sku_detail["schedule_candidate_id"].astype(str) == candidate].copy()
    op_segments = segments[
        (segments["alternative_id"].astype(str) == alternative_id)
        & (segments["finished_sku"].astype(str) == sku)
        & (segments["schedule_candidate_id"].astype(str) == candidate)
    ].copy()
    cap_rows = capacity[
        (capacity["alternative_id"].astype(str) == alternative_id)
        & (capacity["schedule_candidate_id"].astype(str) == candidate)
    ].copy()
    graph_nodes = data["graph_nodes"][
        (data["graph_nodes"].get("finished_sku", pd.Series(dtype=str)).astype(str) == sku)
        & (data["graph_nodes"].get("schedule_candidate_id", pd.Series(dtype=str)).astype(str) == candidate)
    ].copy() if not data["graph_nodes"].empty else pd.DataFrame()

    workstation_summary = _capacity_workstation_summary(cap_rows, op_detail, op_segments, graph_nodes)
    wip_summary = _wip_buffer_summary(data, alternative_id, sku, candidate)

    _capacity_kpis(workstation_summary, op_detail, op_segments)
    _workstation_utilization_chart(workstation_summary)
    selected_ws = _capacity_detail_table(workstation_summary)
    _workstation_detail(selected_ws, op_segments, op_detail, data, alternative_id)
    _wip_kpis(wip_summary, data, alternative_id)
    _wip_buffer_occupancy_chart(wip_summary)
    selected_buffer = _wip_buffer_table(wip_summary)
    _wip_buffer_detail(selected_buffer, data, alternative_id, sku, candidate)


def _capacity_workstation_summary(capacity: pd.DataFrame, detail: pd.DataFrame, segments: pd.DataFrame, graph_nodes: pd.DataFrame) -> pd.DataFrame:
    if capacity.empty:
        return pd.DataFrame()
    cap = capacity.copy()
    numeric_cols = [
        "total_scheduled_workload_minutes",
        "aggregate_workstation_capacity_minutes",
        "remaining_aggregate_capacity_minutes",
        "workstation_utilization_pct",
        "machine_utilization_pct",
        "labor_utilization_pct",
        "effective_parallel_lane_count",
        "newly_allocated_minutes",
        "available_minutes",
    ]
    for col in numeric_cols:
        if col in cap.columns:
            cap[col] = pd.to_numeric(cap[col], errors="coerce").fillna(0)
    agg = cap.groupby("workstation_id", dropna=False).agg(
        scheduled_workload_minutes=("total_scheduled_workload_minutes", "sum"),
        available_capacity_minutes=("aggregate_workstation_capacity_minutes", "sum"),
        remaining_capacity_minutes=("remaining_aggregate_capacity_minutes", "sum"),
        effective_parallel_lane_count=("effective_parallel_lane_count", "max"),
        machine_utilization_pct=("machine_utilization_pct", "max"),
        labor_utilization_pct=("labor_utilization_pct", "max"),
        binding_resource_type=("binding_resource_type", _join_unique),
        capacity_status=("capacity_feasibility_status", _highest_capacity_status),
    ).reset_index()
    agg["utilization_pct"] = agg.apply(lambda r: (r["scheduled_workload_minutes"] / r["available_capacity_minutes"] * 100) if r["available_capacity_minutes"] else 0.0, axis=1)

    if not detail.empty:
        d = detail.copy()
        d["unscheduled_qty"] = pd.to_numeric(d.get("requested_production_qty", 0), errors="coerce").fillna(0) - pd.to_numeric(d.get("schedulable_production_qty", 0), errors="coerce").fillna(0)
        d["buffer_blocked_qty"] = pd.to_numeric(d.get("buffer_blocked_output_qty", 0), errors="coerce").fillna(0)
        detail_agg = d.groupby("workstation_id", dropna=False).agg(
            blocked_quantity=("unscheduled_qty", "sum"),
            buffer_blocked_quantity=("buffer_blocked_qty", "sum"),
            critical_operation_count=("critical_path_flag", lambda s: int(s.astype(str).str.lower().isin({"true", "1", "yes"}).sum())),
        ).reset_index()
        agg = agg.merge(detail_agg, on="workstation_id", how="left")
    for col in ["blocked_quantity", "buffer_blocked_quantity", "critical_operation_count"]:
        if col not in agg.columns:
            agg[col] = 0.0
        agg[col] = pd.to_numeric(agg[col], errors="coerce").fillna(0)

    if not graph_nodes.empty and "bottleneck_status" in graph_nodes.columns:
        bottle = graph_nodes.groupby("workstation_id", dropna=False)["bottleneck_status"].apply(_highest_bottleneck_status).reset_index()
        agg = agg.merge(bottle, on="workstation_id", how="left")
    if "bottleneck_status" not in agg.columns:
        agg["bottleneck_status"] = ""
    agg["load_band"] = agg["utilization_pct"].apply(_load_band)
    return agg.sort_values(["utilization_pct", "scheduled_workload_minutes"], ascending=[False, False])


def _capacity_kpis(ws: pd.DataFrame, detail: pd.DataFrame, segments: pd.DataFrame) -> None:
    main_bottleneck = _main_bottleneck_from_capacity(ws)
    highest_util = float(ws["utilization_pct"].max()) if not ws.empty else 0.0
    processing = _sum(segments, "segment_processing_minutes")
    available = _sum(ws, "available_capacity_minutes")
    blocked_qty = 0.0
    if not detail.empty:
        blocked_qty = _sum(detail.assign(_blocked_qty=pd.to_numeric(detail.get("requested_production_qty", 0), errors="coerce").fillna(0) - pd.to_numeric(detail.get("schedulable_production_qty", 0), errors="coerce").fillna(0)), "_blocked_qty")
    parallel_count = int((pd.to_numeric(ws.get("effective_parallel_lane_count", pd.Series(dtype=float)), errors="coerce").fillna(0) > 1).sum()) if not ws.empty else 0
    critical_ws = int((pd.to_numeric(ws.get("critical_operation_count", pd.Series(dtype=float)), errors="coerce").fillna(0) > 0).sum()) if not ws.empty else 0
    cols = st.columns(7)
    cols[0].metric("Selected Candidate Bottleneck", main_bottleneck or "Unavailable")
    cols[1].metric("Highest Utilization", _pct(highest_util))
    cols[2].metric("Processing Minutes", _fmt(processing))
    cols[3].metric("Available Capacity Minutes", _fmt(available))
    cols[4].metric("Capacity-Blocked Qty", _fmt(blocked_qty))
    cols[5].metric("Parallel-Capable Stations", parallel_count)
    cols[6].metric("Critical Workstations", critical_ws)


def _workstation_utilization_chart(ws: pd.DataFrame) -> None:
    st.subheader("Workstation Utilization")
    if ws.empty:
        st.info("No workstation capacity evidence is available for this selection.")
        return
    chart = ws.copy()
    chart["workstation_label"] = chart["workstation_id"].astype(str)
    fig = px.bar(
        chart.sort_values("utilization_pct"),
        x="utilization_pct",
        y="workstation_label",
        orientation="h",
        color="load_band",
        hover_data=["scheduled_workload_minutes", "available_capacity_minutes", "remaining_capacity_minutes", "effective_parallel_lane_count", "bottleneck_status", "capacity_status"],
        text=chart.sort_values("utilization_pct")["utilization_pct"].map(lambda v: f"{v:.1f}%"),
        color_discrete_map={"Bottleneck": "#b42318", "Heavy Load": "#b7791f", "Normal Load": "#3568a8", "Underused": "#5b6270"},
    )
    fig.update_layout(xaxis_title="Utilization %", yaxis_title="Workstation", height=max(360, 42 * len(chart)), margin=dict(l=10, r=10, t=30, b=10), legend_title="Load")
    st.plotly_chart(fig, width="stretch")


def _capacity_detail_table(ws: pd.DataFrame) -> str:
    st.subheader("Capacity Detail")
    if ws.empty:
        st.info("No capacity rows are available.")
        return ""
    display = ws.rename(columns={
        "workstation_id": "Workstation",
        "scheduled_workload_minutes": "Scheduled Workload Minutes",
        "available_capacity_minutes": "Available Capacity Minutes",
        "remaining_capacity_minutes": "Remaining Capacity Minutes",
        "utilization_pct": "Utilization %",
        "effective_parallel_lane_count": "Effective Parallel Lanes",
        "machine_utilization_pct": "Machine Utilization %",
        "labor_utilization_pct": "Labor Utilization %",
        "binding_resource_type": "Binding Resource",
        "capacity_status": "Capacity Status",
        "blocked_quantity": "Blocked Quantity",
        "bottleneck_status": "Bottleneck Status",
    })
    cols = ["Workstation", "Scheduled Workload Minutes", "Available Capacity Minutes", "Remaining Capacity Minutes", "Utilization %", "Effective Parallel Lanes", "Machine Utilization %", "Labor Utilization %", "Binding Resource", "Capacity Status", "Blocked Quantity", "Bottleneck Status"]
    st.dataframe(_display_columns(display, cols), hide_index=True, width="stretch")
    return st.selectbox("Workstation detail", ws["workstation_id"].astype(str).tolist(), key="capwip_ws_detail")


def _workstation_detail(workstation_id: str, segments: pd.DataFrame, detail: pd.DataFrame, data: dict[str, pd.DataFrame], alternative_id: str) -> None:
    st.subheader("Workstation Detail")
    if not workstation_id:
        return
    seg = segments[segments.get("workstation_id", pd.Series(dtype=str)).astype(str) == workstation_id].copy()
    det = detail[detail.get("workstation_id", pd.Series(dtype=str)).astype(str) == workstation_id].copy()
    seg["_start"] = pd.to_datetime(seg.get("proposed_start_datetime", ""), errors="coerce")
    seg["_end"] = pd.to_datetime(seg.get("proposed_end_datetime", ""), errors="coerce")
    scheduled = seg[pd.to_numeric(seg.get("segment_scheduled_qty", 0), errors="coerce").fillna(0) > 0].copy()
    peak = _peak_concurrency(scheduled)
    maint_statuses = []
    for op_id in det.get("operation_id", pd.Series(dtype=str)).dropna().astype(str).unique():
        maint_statuses.append(_maintenance_status(data, alternative_id, op_id, _row_dict(det, "operation_id", op_id)).get("maintenance_status", ""))
    summary = pd.DataFrame([{
        "workstation": workstation_id,
        "operations_scheduled": scheduled["operation_id"].nunique() if not scheduled.empty else 0,
        "peak_concurrency": peak,
        "setup_minutes": _sum(scheduled, "segment_setup_minutes"),
        "processing_minutes": _sum(scheduled, "segment_processing_minutes"),
        "blocked_or_unscheduled_qty": _sum(det.assign(_blocked_qty=pd.to_numeric(det.get("requested_production_qty", 0), errors="coerce").fillna(0) - pd.to_numeric(det.get("schedulable_production_qty", 0), errors="coerce").fillna(0)), "_blocked_qty") if not det.empty else 0.0,
        "bottleneck_status": _highest_bottleneck_status(det.get("bottleneck_status", pd.Series(dtype=str))) if "bottleneck_status" in det.columns else "",
        "maintenance_review_status": _join_unique(pd.Series([s for s in maint_statuses if s])),
    }])
    st.dataframe(summary, hide_index=True, width="stretch")
    cols = ["operation_id", "operation_name", "segment_sequence", "proposed_start_datetime", "proposed_end_datetime", "segment_scheduled_qty", "assigned_machine_unit_ids", "assigned_labor_unit_ids", "segment_processing_minutes", "segment_setup_minutes", "segment_capacity_status", "segment_maintenance_status"]
    st.dataframe(_display_columns(scheduled.sort_values(["_start", "operation_id", "segment_sequence"]), cols), hide_index=True, width="stretch")


def _wip_buffer_summary(data: dict[str, pd.DataFrame], alternative_id: str, sku: str, candidate_id: str) -> pd.DataFrame:
    access = data["wip_access"]
    shadow = data["shadow_wip"]
    wip_status = data["wip_buffer"]
    wip_impact = data["wip_impact"]
    if access.empty:
        return pd.DataFrame()
    related = access[access.get("finished_sku", pd.Series(dtype=str)).astype(str) == sku].copy()
    buffer_rows = []
    seen = set()
    for _, row in related.iterrows():
        for item_col, buffer_col, relation in [
            ("allowed_input_wip_item_id", "allowed_input_wip_buffer_id", "INPUT"),
            ("allowed_output_wip_item_id", "allowed_output_wip_buffer_id", "OUTPUT"),
        ]:
            buffer_id = str(row.get(buffer_col, "") or "")
            wip_item_id = str(row.get(item_col, "") or "")
            if not buffer_id or buffer_id.lower() == "nan" or (buffer_id, wip_item_id) in seen:
                continue
            seen.add((buffer_id, wip_item_id))
            generic = _row_dict(wip_status, "wip_buffer_id", buffer_id)
            events = _candidate_shadow_events(shadow, alternative_id, sku, candidate_id, buffer_id)
            latest = _latest_shadow_event(events)
            impact = wip_impact[
                (wip_impact.get("alternative_id", pd.Series(dtype=str)).astype(str) == alternative_id)
                & (wip_impact.get("finished_sku", pd.Series(dtype=str)).astype(str) == sku)
                & (wip_impact.get("wip_buffer_id", pd.Series(dtype=str)).astype(str) == buffer_id)
            ] if not wip_impact.empty else pd.DataFrame()
            projected = _num(latest.get("shadow_ending_qty")) if latest else _num(generic.get("current_wip_qty"))
            capacity = _num(latest.get("buffer_max_qty")) if latest else _num(generic.get("max_buffer_qty"))
            blocked = _sum(impact, "buffer_blocked_output_qty") if not impact.empty else _num(generic.get("blocked_wip_qty"))
            occupancy = projected / capacity * 100 if capacity else 0.0
            buffer_rows.append({
                "wip_buffer_id": buffer_id,
                "wip_item_id": wip_item_id,
                "projected_balance": projected,
                "max_buffer_qty": capacity,
                "occupancy_pct": occupancy,
                "blocked_qty": blocked,
                "fifo_status": _fifo_status(shadow, alternative_id, buffer_id, candidate_id),
                "constraint_status": _first_nonblank(impact, "buffer_capacity_status") or str(generic.get("buffer_status", "")),
                "upstream_operation_id": row.get("operation_id", ""),
                "downstream_operation_id": row.get("successor_operation_id", ""),
                "evidence_basis": "SELECTED_CANDIDATE_TIME_CAUSAL_SHADOW_WIP_LEDGER" if latest else "GENERIC_BUFFER_STATUS_FALLBACK",
                "latest_event_datetime": latest.get("event_datetime", "") if latest else "",
            })
    return pd.DataFrame(buffer_rows).sort_values(["occupancy_pct", "wip_buffer_id"], ascending=[False, True]) if buffer_rows else pd.DataFrame()


def _wip_kpis(wip: pd.DataFrame, data: dict[str, pd.DataFrame], alternative_id: str) -> None:
    validation = data["schedule_validation"]
    fifo_violations = _validation_affected(validation, ["FIFO_SEQUENCE_VIOLATION", "NEWER_LOT_USED_BEFORE_OLDER_AVAILABLE_LOT", "WIP_LOT_QUANTITY_REUSED"])
    buffer_delay_count = int((pd.to_numeric(data["wip_impact"].get("buffer_delay_minutes", pd.Series(dtype=float)), errors="coerce").fillna(0) > 0).sum()) if not data["wip_impact"].empty else 0
    cols = st.columns(6)
    cols[0].metric("WIP Buffers Used", len(wip))
    cols[1].metric("Average Occupancy", _pct(wip["occupancy_pct"].mean() if not wip.empty else 0))
    cols[2].metric("Maximum Occupancy", _pct(wip["occupancy_pct"].max() if not wip.empty else 0))
    cols[3].metric("Full / Constrained Buffers", int(wip.get("constraint_status", pd.Series(dtype=str)).astype(str).str.contains("FULL|BLOCK|OVERFLOW|CONSTRAIN", case=False, regex=True).sum()) if not wip.empty else 0)
    cols[4].metric("Blocked WIP Qty", _fmt(_sum(wip, "blocked_qty")))
    cols[5].metric("FIFO Violations", fifo_violations)
    st.caption(f"Buffer-delay operation rows: {buffer_delay_count}")


def _wip_buffer_occupancy_chart(wip: pd.DataFrame) -> None:
    st.subheader("WIP Buffer Occupancy")
    if wip.empty:
        st.info("No related WIP buffer evidence is available.")
        return
    chart = wip.copy().sort_values("occupancy_pct")
    fig = px.bar(
        chart,
        x="occupancy_pct",
        y="wip_buffer_id",
        orientation="h",
        color="constraint_status",
        hover_data=["wip_item_id", "projected_balance", "max_buffer_qty", "blocked_qty", "fifo_status", "evidence_basis", "latest_event_datetime"],
        text=chart["occupancy_pct"].map(lambda v: f"{v:.1f}%"),
    )
    fig.update_layout(xaxis_title="Occupancy %", yaxis_title="WIP buffer", height=max(360, 38 * len(chart)), margin=dict(l=10, r=10, t=30, b=10), legend_title="Constraint")
    st.plotly_chart(fig, width="stretch")


def _wip_buffer_table(wip: pd.DataFrame) -> str:
    st.subheader("WIP Buffer Table")
    if wip.empty:
        return ""
    display = wip.rename(columns={
        "wip_buffer_id": "Buffer ID",
        "wip_item_id": "WIP Item",
        "projected_balance": "Projected Balance",
        "max_buffer_qty": "Maximum Capacity",
        "occupancy_pct": "Occupancy %",
        "blocked_qty": "Blocked Quantity",
        "fifo_status": "FIFO Status",
        "constraint_status": "Constraint Status",
        "upstream_operation_id": "Upstream Operation",
        "downstream_operation_id": "Downstream Operation",
        "evidence_basis": "Evidence Basis",
    })
    cols = ["Buffer ID", "WIP Item", "Projected Balance", "Maximum Capacity", "Occupancy %", "Blocked Quantity", "FIFO Status", "Constraint Status", "Upstream Operation", "Downstream Operation", "Evidence Basis"]
    st.dataframe(_display_columns(display, cols), hide_index=True, width="stretch")
    return st.selectbox("Buffer detail", wip["wip_buffer_id"].astype(str).tolist(), key="capwip_buffer_detail")


def _wip_buffer_detail(buffer_id: str, data: dict[str, pd.DataFrame], alternative_id: str, sku: str, candidate_id: str) -> None:
    st.subheader("Buffer Detail")
    if not buffer_id:
        return
    shadow = data["shadow_wip"]
    events = _candidate_shadow_events(shadow, alternative_id, sku, candidate_id, buffer_id)
    events["_event_dt"] = pd.to_datetime(events.get("event_datetime", ""), errors="coerce") if not events.empty else pd.Series(dtype="datetime64[ns]")
    events = events.sort_values(["_event_dt", "event_sequence"]) if not events.empty and "event_sequence" in events.columns else events
    cols = [
        "event_sequence",
        "event_datetime",
        "lot_id",
        "lot_availability_datetime",
        "lot_selection_method",
        "schedule_candidate_id",
        "operation_segment_id",
        "producer_operation_id",
        "consumer_operation_id",
        "shadow_event_type",
        "advisory_produced_qty",
        "advisory_drawn_qty",
        "advisory_blocked_qty",
        "shadow_ending_qty",
        "buffer_max_qty",
        "shadow_balance_status",
    ]
    st.dataframe(_display_columns(events, cols), hide_index=True, width="stretch")


def _maintenance_page(data: dict[str, pd.DataFrame]) -> None:
    alternative_id = "ALT-BASELINE"
    detail = data["operation_detail"]
    if detail.empty:
        st.warning("Step 8F operation evidence is missing. Run the validated planning pipeline first.")
        return
    st.subheader("Maintenance")
    st.caption("Read-only maintenance planning and production-risk view. No maintenance work orders, crew assignments, spare-part reservations, or capacity reductions are created.")

    base_detail = detail[detail["alternative_id"].astype(str) == alternative_id].copy()
    controls = st.columns([1.1, 1.7, 1.4, 1.2])
    sku = controls[0].selectbox("Finished SKU", sorted(base_detail["finished_sku"].dropna().astype(str).unique()), key="maint_sku")
    sku_detail = base_detail[base_detail["finished_sku"].astype(str) == sku]
    candidate = controls[1].selectbox("Schedule candidate / planning week", sorted(sku_detail["schedule_candidate_id"].dropna().astype(str).unique()), key="maint_candidate")
    impact = _maintenance_production_rows(data, alternative_id, sku, candidate)
    machine_options = ["All"] + sorted(set(_nonblank(data["maintenance_readiness"].get("machine_id", pd.Series(dtype=str))) + _nonblank(impact.get("machine_id", pd.Series(dtype=str)))))
    selected_machine = controls[2].selectbox("Workstation or machine", machine_options, key="maint_machine")
    risk_options = ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW", "REVIEW REQUIRED", "DATE UNKNOWN"]
    selected_risk = controls[3].selectbox("Maintenance status/risk", risk_options, key="maint_risk")

    status_table = _maintenance_status_table(data)
    if selected_machine != "All":
        status_table = status_table[(status_table["machine_id"].astype(str) == selected_machine) | (status_table["workstation_id"].astype(str) == selected_machine)]
        impact = impact[(impact.get("machine_id", pd.Series(dtype=str)).astype(str) == selected_machine) | (impact.get("workstation_id", pd.Series(dtype=str)).astype(str) == selected_machine)]
    if selected_risk != "All":
        status_table = status_table[status_table.apply(lambda r: selected_risk in str(r.to_dict()).upper(), axis=1)]

    _maintenance_kpis(data, status_table, impact)
    _maintenance_status_section(status_table)
    _maintenance_production_impact_section(impact)
    _maintenance_calendar_section(data)
    _breakdown_risk_section(data)
    _crew_skill_section(data)
    _spare_part_section(data)
    _maintenance_review_queue(status_table, impact, data)


def _maintenance_status_table(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    readiness = data["maintenance_readiness"].copy()
    prod = data["maintenance_production_impact"].copy()
    feas = data["maintenance_feasibility"].copy()
    breakdown = data["breakdown_risk"].copy()
    crew = data["maintenance_crew_context"].copy()
    due = data["maintenance_due_status"].copy()
    windows = data["maintenance_windows"].copy()
    auth = data["workforce_auth"].copy()
    machines = sorted(set(_nonblank(readiness.get("machine_id", pd.Series(dtype=str))) + _nonblank(prod.get("machine_id", pd.Series(dtype=str))) + _nonblank(breakdown.get("machine_id", pd.Series(dtype=str)))))
    rows = []
    for machine_id in machines:
        r = _row_dict(readiness, "machine_id", machine_id)
        p = _row_dict(prod, "machine_id", machine_id)
        f = _row_dict(feas, "machine_id", machine_id)
        b = _row_dict(breakdown, "machine_id", machine_id)
        c = _row_dict(crew, "machine_id", machine_id)
        d_rows = due[due.get("machine_id", pd.Series(dtype=str)).astype(str) == machine_id] if not due.empty else pd.DataFrame()
        w_rows = windows[windows.get("machine_id", pd.Series(dtype=str)).astype(str) == machine_id] if not windows.empty else pd.DataFrame()
        a_rows = auth[auth.get("machine_id", pd.Series(dtype=str)).astype(str) == machine_id] if not auth.empty else pd.DataFrame()
        relevant_auth = a_rows[_bool_series(a_rows.get("can_maintain_flag", pd.Series(dtype=str))) | _bool_series(a_rows.get("can_repair_flag", pd.Series(dtype=str)))] if not a_rows.empty else pd.DataFrame()
        authorization_level = _join_unique(relevant_auth.get("authorization_level", pd.Series(dtype=str))) if not relevant_auth.empty and "authorization_level" in relevant_auth.columns else "NOT_AVAILABLE / REVIEW"
        due_status = _highest_due_status(d_rows.get("due_status", pd.Series(dtype=str))) if not d_rows.empty else _maintenance_due_label(r)
        status_label = _maintenance_status_label(due_status, f, p)
        rows.append({
            "machine_id": machine_id,
            "machine_name": r.get("machine_name") or p.get("machine_name") or b.get("machine_name") or "",
            "workstation_id": p.get("workstation_id", ""),
            "maintenance_type": _join_unique(d_rows.get("maintenance_category", pd.Series(dtype=str))) if not d_rows.empty else "",
            "maintenance_level": _join_unique(d_rows.get("maintenance_level", pd.Series(dtype=str))) if not d_rows.empty else "",
            "due_status": due_status,
            "status_label": status_label,
            "planned_or_next_maintenance_date": _dated_window_value(w_rows, "maintenance_start_datetime"),
            "time_until_maintenance": _time_until_label(_dated_window_value(w_rows, "maintenance_start_datetime")),
            "breakdown_risk": b.get("breakdown_risk_level", ""),
            "backlog_status": c.get("backlog_risk_level", ""),
            "required_skill": c.get("required_skill_id") or _first_nonblank(w_rows, "required_skill_id"),
            "required_crew_type": _first_nonblank(w_rows, "required_crew_type"),
            "required_worker_count": _first_nonblank(w_rows, "required_worker_count"),
            "authorization_level": authorization_level,
            "authorization_source": "workforce_machine_authorization_context.csv" if authorization_level != "NOT_AVAILABLE / REVIEW" else "NOT_AVAILABLE / REVIEW",
            "maintenance_feasibility_status": f.get("best_schedule_feasibility_status", ""),
            "production_impact_status": p.get("scheduling_blocker_status", ""),
            "source_phase": _join_unique(pd.Series([r.get("source_phase", ""), p.get("source_phase", ""), f.get("source_phase", ""), b.get("source_phase", ""), c.get("source_phase", "")])),
        })
    return pd.DataFrame(rows)


def _maintenance_kpis(data: dict[str, pd.DataFrame], status_table: pd.DataFrame, impact: pd.DataFrame) -> None:
    dated_windows = _valid_dated_windows(data["maintenance_windows"])
    window_check = data["maintenance_window_check"]
    conflicts = 0
    if not window_check.empty:
        conflicts = int((_bool_series(window_check.get("dated_overlap_flag", pd.Series(dtype=str))) | _bool_series(window_check.get("machine_state_unavailable_flag", pd.Series(dtype=str)))).sum())
    spare_reviews = int(_bool_series(data["maintenance_spare_parts"].get("spare_part_review_required_flag", pd.Series(dtype=str))).sum()) if not data["maintenance_spare_parts"].empty else len(data["spare_part_review"])
    crew_risk = int(data["maintenance_workload_by_skill"].get("capacity_status", pd.Series(dtype=str)).astype(str).str.contains("OVERLOAD|NO_COVERAGE|REVIEW", case=False, regex=True).sum()) if not data["maintenance_workload_by_skill"].empty else 0
    cols = st.columns(5)
    cols[0].metric("Machines / Workstations Reviewed", len(status_table))
    cols[1].metric("Maintenance Due", int(status_table["due_status"].astype(str).str.contains("DUE|OVERDUE", case=False, regex=True).sum()) if not status_table.empty else 0)
    cols[2].metric("Overdue", int(status_table["due_status"].astype(str).str.contains("OVERDUE", case=False, regex=False).sum()) if not status_table.empty else 0)
    cols[3].metric("Dated Maintenance Windows", len(dated_windows))
    cols[4].metric("Production Conflicts", conflicts)
    cols = st.columns(5)
    cols[0].metric("High Breakdown Risk", int(status_table["breakdown_risk"].astype(str).str.upper().isin({"HIGH", "CRITICAL"}).sum()) if not status_table.empty else 0)
    cols[1].metric("Backlog / Review Required", int(status_table.apply(lambda r: "REVIEW" in str(r.to_dict()).upper() or "CRITICAL" in str(r.get("backlog_status", "")).upper(), axis=1).sum()) if not status_table.empty else 0)
    cols[2].metric("Affected Operations", impact["operation_id"].nunique() if not impact.empty else 0)
    cols[3].metric("Spare-Part Shortage / Review", spare_reviews)
    cols[4].metric("Crew-Capacity Risk", crew_risk)
    if len(dated_windows) == 0:
        st.info("DATED MAINTENANCE WINDOWS: 0. Current maintenance calendar evidence is risk/review-based only.")


def _maintenance_status_section(status_table: pd.DataFrame) -> None:
    st.subheader("Maintenance Status")
    if status_table.empty:
        st.info("No maintenance status evidence is available.")
        return
    cols = ["machine_id", "machine_name", "workstation_id", "maintenance_type", "maintenance_level", "status_label", "due_status", "planned_or_next_maintenance_date", "time_until_maintenance", "breakdown_risk", "backlog_status", "required_skill", "required_crew_type", "required_worker_count", "authorization_level", "authorization_source", "maintenance_feasibility_status", "production_impact_status"]
    st.dataframe(_display_columns(status_table, cols), hide_index=True, width="stretch")


def _maintenance_production_rows(data: dict[str, pd.DataFrame], alternative_id: str, sku: str, candidate_id: str) -> pd.DataFrame:
    maint = data["maintenance_impact"]
    detail = data["operation_detail"]
    if maint.empty or detail.empty:
        return pd.DataFrame()
    ops = detail[(detail["alternative_id"].astype(str) == alternative_id) & (detail["finished_sku"].astype(str) == sku) & (detail["schedule_candidate_id"].astype(str) == candidate_id)]
    rows = maint[(maint["alternative_id"].astype(str) == alternative_id) & (maint["operation_id"].astype(str).isin(ops["operation_id"].astype(str)))].copy()
    rows = rows.merge(ops[["schedule_candidate_id", "finished_sku", "operation_id", "operation_name", "workstation_id", "proposed_start_datetime", "proposed_end_datetime"]], on=["operation_id", "workstation_id"], how="left", suffixes=("", "_op"))
    if "finished_sku_op" in rows.columns:
        rows["finished_sku"] = rows["finished_sku_op"]
    rows["impact_type"] = rows.apply(lambda r: "DATED MAINTENANCE CONFLICT" if _truthy(r.get("maintenance_conflict_flag")) or _truthy(r.get("selected_window_maintenance_conflict_flag")) else "RISK-ONLY REVIEW", axis=1)
    rows["recommended_manager_review_action"] = rows["impact_type"].map({"DATED MAINTENANCE CONFLICT": "Review dated maintenance conflict before release.", "RISK-ONLY REVIEW": "Review maintenance and breakdown risk; do not treat as dated downtime."})
    return rows.drop_duplicates(["finished_sku", "schedule_candidate_id", "operation_id", "machine_id", "workstation_id"]).copy()


def _maintenance_production_impact_section(impact: pd.DataFrame) -> None:
    st.subheader("Production Impact")
    if impact.empty:
        st.info("No selected SKU/candidate production operations have maintenance-impact evidence.")
        return
    cols = ["finished_sku", "schedule_candidate_id", "operation_id", "operation_name", "workstation_id", "proposed_start_datetime", "proposed_end_datetime", "maintenance_feasibility_status", "impact_type", "maintenance_conflict_flag", "breakdown_risk_level", "maintenance_conflict_penalty", "recommended_manager_review_action"]
    st.dataframe(_display_columns(impact, cols), hide_index=True, width="stretch")


def _maintenance_calendar_section(data: dict[str, pd.DataFrame]) -> None:
    st.subheader("Maintenance Timeline / Calendar")
    windows = _valid_dated_windows(data["maintenance_windows"])
    if windows.empty:
        st.info("No valid dated maintenance windows are present. Current maintenance evidence is risk/review-based only; no fake maintenance bars are shown.")
        return
    fig = px.timeline(windows, x_start="_start", x_end="_end", y="machine_id", color="schedule_feasibility_status", hover_data=[c for c in ["maintenance_plan_id", "required_skill_id", "required_crew_type", "required_worker_count", "schedule_feasibility_reason"] if c in windows.columns])
    fig.update_layout(xaxis_title="Maintenance window", yaxis_title="Machine", height=max(360, 42 * windows["machine_id"].nunique()), margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, width="stretch")


def _breakdown_risk_section(data: dict[str, pd.DataFrame]) -> None:
    st.subheader("Breakdown Risk")
    risk = data["breakdown_risk"].copy()
    if risk.empty:
        st.info("No breakdown-risk evidence is available.")
        return
    risk["risk_score"] = pd.to_numeric(risk.get("breakdown_risk_score", 0), errors="coerce").fillna(0)
    cols = ["machine_id", "machine_name", "breakdown_risk_level", "risk_score", "expected_breakdown_count_next_period", "expected_downtime_hours_next_period", "breakdown_trend_overall", "maintenance_due_status_signal", "highest_failure_mode_severity"]
    st.dataframe(_display_columns(risk.sort_values("risk_score", ascending=False), cols), hide_index=True, width="stretch")


def _crew_skill_section(data: dict[str, pd.DataFrame]) -> None:
    st.subheader("Crew & Skill Readiness")
    workload = data["maintenance_workload_by_skill"]
    if workload.empty:
        st.info("No maintenance crew/skill workload evidence is available.")
        return
    cols = ["required_skill_id", "required_skill_name", "maintenance_level", "total_required_hours", "active_maintenance_crew_count", "light_authorized_production_crew_count", "available_crew_hours", "utilization_pct", "capacity_status", "backlog_hours", "skill_coverage_status"]
    st.dataframe(_display_columns(workload, cols), hide_index=True, width="stretch")


def _spare_part_section(data: dict[str, pd.DataFrame]) -> None:
    st.subheader("Spare-Part Readiness")
    spare = data["maintenance_spare_parts"].copy()
    if spare.empty:
        spare = data["spare_part_context"].copy()
    if spare.empty:
        st.info("No maintenance spare-part readiness evidence is available.")
        return
    cols = ["maintenance_plan_id", "machine_id", "machine_name", "spare_part_sku", "spare_part_name", "quantity_required", "inventory_status", "supplier_coverage_status", "spare_part_readiness_status", "spare_part_review_required_flag", "source_phase"]
    st.dataframe(_display_columns(spare, cols), hide_index=True, width="stretch")


def _maintenance_review_queue(status_table: pd.DataFrame, impact: pd.DataFrame, data: dict[str, pd.DataFrame]) -> None:
    st.subheader("Maintenance Review Queue")
    rows = []
    for _, row in status_table.iterrows():
        text = str(row.to_dict()).upper()
        if any(token in text for token in ["OVERDUE", "CRITICAL", "HIGH", "REVIEW", "BLOCKED", "DATE UNKNOWN"]):
            rows.append({
                "severity": _maintenance_review_severity(row),
                "machine_or_workstation": row.get("machine_id", "") or row.get("workstation_id", ""),
                "issue": row.get("status_label", "") or row.get("due_status", ""),
                "production_impact": row.get("production_impact_status", ""),
                "source_evidence": row.get("source_phase", ""),
                "recommended_review_action": "Review maintenance readiness, crew/spare constraints, and production impact before release.",
            })
    if not impact.empty:
        for _, row in impact.drop_duplicates(["operation_id", "workstation_id"]).iterrows():
            if str(row.get("impact_type", "")).upper() != "RISK-ONLY REVIEW" or str(row.get("breakdown_risk_level", "")).upper() in {"HIGH", "CRITICAL"}:
                rows.append({
                    "severity": "HIGH" if str(row.get("breakdown_risk_level", "")).upper() in {"HIGH", "CRITICAL"} else "MEDIUM",
                    "machine_or_workstation": row.get("machine_id", "") or row.get("workstation_id", ""),
                    "issue": row.get("impact_type", ""),
                    "production_impact": f"{row.get('operation_id', '')} {row.get('operation_name', '')}",
                    "source_evidence": row.get("source_phase", ""),
                    "recommended_review_action": row.get("recommended_manager_review_action", "Review production impact."),
                })
    spare_reviews = data["spare_part_review"]
    if not spare_reviews.empty:
        for _, row in spare_reviews.head(20).iterrows():
            rows.append({
                "severity": row.get("issue_severity", "MEDIUM"),
                "machine_or_workstation": row.get("spare_part_sku", ""),
                "issue": row.get("issue_type", "SPARE_PART_REVIEW"),
                "production_impact": row.get("issue_description", ""),
                "source_evidence": "SHARED_SPARE_PART_MANAGER_REVIEW_QUEUE",
                "recommended_review_action": row.get("recommended_review_action", "Review spare-part readiness."),
            })
    queue = pd.DataFrame(rows).drop_duplicates() if rows else pd.DataFrame()
    if queue.empty:
        st.success("No concise maintenance review items for the current filters.")
    else:
        st.dataframe(queue, hide_index=True, width="stretch")


def _decision_release_page(data: dict[str, pd.DataFrame]) -> None:
    summary = data["alt_summary"].copy()
    rec = _first_row(data["recommendation"])
    readiness = data["release_readiness"].copy()
    tradeoffs = data["tradeoff_analysis"].copy()
    risks = data["decision_risks"].copy()
    review = data["step8g_manager_review"].copy()
    material = data["material_readiness"].copy()
    schedule_impact = data["schedule_impact"].copy()

    st.subheader("Decision & Release Readiness")
    st.caption("Read-only decision-support view. It does not approve, release, reserve, consume, dispatch, or create execution transactions.")
    if summary.empty or not rec or readiness.empty:
        st.warning("Step 8G decision outputs are missing. Run the validated Step 8G decision layer first.")
        return

    selected_alt = "ALT-BASELINE"
    controls = st.columns([1.2, 1.8])
    sku_options = sorted(material.get("finished_sku", pd.Series(dtype=str)).dropna().astype(str).unique()) if not material.empty else sorted(summary.get("alternative_id", pd.Series(dtype=str)).dropna().astype(str).unique())
    sku = controls[0].selectbox("Finished SKU", sku_options, key="decision_sku")
    sku_material = material[material.get("finished_sku", pd.Series(dtype=str)).astype(str) == sku].copy() if not material.empty and "finished_sku" in material.columns else pd.DataFrame()
    candidate_options = sorted(sku_material.get("schedule_candidate_id", pd.Series(dtype=str)).dropna().astype(str).unique()) if not sku_material.empty else []
    candidate = controls[1].selectbox("Schedule candidate / planning week", candidate_options or ["Overall"], key="decision_candidate")
    selected_material = sku_material[sku_material.get("schedule_candidate_id", pd.Series(dtype=str)).astype(str) == candidate].copy() if candidate_options else sku_material
    selected_impact = schedule_impact[
        (schedule_impact.get("finished_sku", pd.Series(dtype=str)).astype(str) == sku)
        & (schedule_impact.get("schedule_candidate_id", pd.Series(dtype=str)).astype(str) == candidate)
    ].copy() if not schedule_impact.empty and candidate_options else pd.DataFrame()

    _decision_summary_section(summary, rec, readiness)
    _decision_alternative_comparison(summary, rec)
    _decision_tradeoff_section(tradeoffs, rec)
    _release_readiness_section(readiness)
    _release_blockers_section(readiness)
    _decision_risks_section(risks)
    _decision_manager_review_section(review)
    _cross_phase_readiness_section(data, selected_alt, sku, candidate, selected_material, selected_impact)


def _decision_summary_section(summary: pd.DataFrame, rec: dict, readiness: pd.DataFrame) -> None:
    st.subheader("Decision Summary")
    recommended_id = str(rec.get("recommended_alternative_id", ""))
    row = _row_dict(summary, "alternative_id", recommended_id)
    release_row = readiness[readiness.get("readiness_row_type", pd.Series(dtype=str)).astype(str) == "OVERALL"]
    release_status = _cell(release_row, "release_readiness_status") or _first_nonblank(readiness, "release_readiness_status")
    release_allowed = _cell(release_row, "production_release_allowed") or _first_nonblank(readiness, "production_release_allowed")

    cols = st.columns(5)
    cols[0].metric("Recommended Alternative", recommended_id or "Unavailable")
    cols[1].metric("Recommendation Status", rec.get("recommendation_status", "Unavailable"))
    cols[2].metric("Demand Coverage", _pct(row.get("demand_coverage_pct")))
    cols[3].metric("Completed Qty", _fmt(row.get("completed_full_route_qty")))
    cols[4].metric("Unscheduled Qty", _fmt(row.get("unscheduled_qty")))

    cols = st.columns(5)
    cols[0].metric("Overall Bottleneck", row.get("main_bottleneck_workstation", "Unavailable"))
    cols[1].metric("Cost Confidence", row.get("cost_confidence_level", "Unavailable"))
    cols[2].metric("Step 8G Final Status", rec.get("step8g_final_status", "Unavailable"))
    cols[3].metric("Release Readiness", release_status or "Unavailable")
    cols[4].metric("Release Allowed", str(release_allowed))

    equivalents = _equivalent_group(rec, summary)
    st.info(f"Equivalent alternatives: {equivalents or 'None identified'}")
    if str(rec.get("step8g_final_status", "")) == "CLOSED_WITH_REVIEW":
        st.warning("CLOSED_WITH_REVIEW")
    if str(release_status) == "NOT_READY_FOR_RELEASE" or not _truthy(release_allowed):
        st.error("NOT_READY_FOR_RELEASE")


def _decision_alternative_comparison(summary: pd.DataFrame, rec: dict) -> None:
    st.subheader("Alternative Comparison")
    if summary.empty:
        st.info("No alternative summary rows are available.")
        return
    display = summary.copy()
    display["equivalent_result_group"] = display["alternative_id"].astype(str).map(lambda alt: _equivalent_label_for_alt(alt, rec, summary))
    cols = [
        "alternative_id",
        "alternative_name",
        "step8f_status",
        "demand_coverage_pct",
        "completed_full_route_qty",
        "unscheduled_qty",
        "validated_real_cost",
        "assumed_cost_or_penalty",
        "setup_minutes",
        "setup_switch_count",
        "buffer_blocked_qty",
        "wip_blocked_qty",
        "main_bottleneck_workstation",
        "recommendation_rank",
        "equivalent_result_group",
    ]
    st.dataframe(_display_columns(display.sort_values("recommendation_rank"), cols), hide_index=True, width="stretch")


def _decision_tradeoff_section(tradeoffs: pd.DataFrame, rec: dict) -> None:
    st.subheader("Trade-offs")
    if tradeoffs.empty:
        st.info("No Step 8G trade-off output is available.")
        return
    recommended_id = str(rec.get("recommended_alternative_id", "ALT-BASELINE"))
    st.caption(f"Compared against Step 8G baseline/reference. Recommended reference: {recommended_id}.")
    cols = [
        "compared_alternative_id",
        "compared_alternative_name",
        "equivalent_to_baseline_flag",
        "meaningful_difference_flag",
        "demand_coverage_delta_pct",
        "completed_quantity_delta",
        "unscheduled_quantity_delta",
        "validated_cost_delta",
        "assumed_penalty_delta",
        "setup_minutes_delta",
        "setup_switch_delta",
        "buffer_blocked_quantity_delta",
        "wip_blocked_quantity_delta",
        "bottleneck_exposure_change",
        "maintenance_review_count_delta",
        "tradeoff_summary",
    ]
    st.dataframe(_display_columns(tradeoffs, cols), hide_index=True, width="stretch")


def _release_readiness_section(readiness: pd.DataFrame) -> None:
    st.subheader("Release Readiness Checklist")
    st.caption("Overall release readiness from Step 8G. This is not a product-specific approval state.")
    checks = readiness[readiness.get("readiness_row_type", pd.Series(dtype=str)).astype(str) != "OVERALL"].copy()
    if checks.empty:
        checks = readiness.copy()
    display = checks.rename(columns={
        "readiness_check_name": "Check",
        "readiness_status": "Status",
        "evidence_source_file": "Source",
        "evidence_summary": "Reason",
        "recommended_manager_action": "Manager Action",
    })
    cols = ["Check", "Status", "release_readiness_status", "production_release_allowed", "Source", "Reason", "Manager Action"]
    st.dataframe(_display_columns(display, cols), hide_index=True, width="stretch")


def _release_blockers_section(readiness: pd.DataFrame) -> None:
    st.subheader("Blockers to Release")
    blocked = readiness[
        readiness.get("readiness_row_type", pd.Series(dtype=str)).astype(str) != "OVERALL"
    ].copy()
    if not blocked.empty:
        blocked = blocked[blocked.get("readiness_status", pd.Series(dtype=str)).astype(str).str.upper().isin(["BLOCKED", "REVIEW_REQUIRED", "REVIEW REQUIRED", "FAIL"])]
    if blocked.empty:
        st.success("No blocked readiness checks in the Step 8G readiness evidence.")
        return
    rows = blocked.rename(columns={
        "readiness_check_name": "check",
        "readiness_status": "status",
        "evidence_source_file": "source_phase_or_file",
        "evidence_summary": "reason",
        "recommended_manager_action": "recommended_manager_action",
    }).copy()
    rows["business_impact"] = rows["status"].astype(str).map(lambda s: "Production release remains blocked until this check is resolved." if "BLOCK" in s.upper() else "Manager review is required before release.")
    cols = ["check", "status", "source_phase_or_file", "reason", "business_impact", "recommended_manager_action"]
    st.dataframe(_display_columns(rows, cols), hide_index=True, width="stretch")


def _decision_risks_section(risks: pd.DataFrame) -> None:
    st.subheader("Decision Risks")
    if risks.empty:
        st.info("No Step 8G decision-risk register is available.")
        return
    rows = risks.copy()
    rows["_severity_rank"] = rows.get("severity", pd.Series("", index=rows.index)).astype(str).str.upper().map({"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}).fillna(0)
    rows = rows.sort_values(["_severity_rank", "risk_type"], ascending=[False, True]).drop_duplicates(["risk_type", "affected_alternative_or_resource", "source_file"])
    cols = ["severity", "risk_type", "affected_alternative_or_resource", "business_impact", "source_phase_reference", "source_file", "recommended_manager_action"]
    st.dataframe(_display_columns(rows, cols), hide_index=True, width="stretch")


def _decision_manager_review_section(review: pd.DataFrame) -> None:
    st.subheader("Manager Review Queue")
    if review.empty:
        st.info("No Step 8G manager review queue is available.")
        return
    rows = review.copy()
    rows["approval_or_review_status"] = "MANAGER_REVIEW_REQUIRED"
    display = rows.rename(columns={
        "alternative_id": "Affected Alternative",
        "issue_type": "issue",
        "issue_severity": "severity",
        "source_file": "source",
        "recommended_manager_action": "manager_action_required",
    })
    if "finished_sku" in display.columns:
        display = display.rename(columns={"finished_sku": "Affected SKU"})
    if "workstation_id" in display.columns:
        display = display.rename(columns={"workstation_id": "Affected Workstation"})
    cols = ["issue", "severity", "Affected Alternative", "Affected SKU", "Affected Workstation", "source", "manager_action_required", "approval_or_review_status", "business_impact"]
    st.dataframe(_display_columns(display, cols), hide_index=True, width="stretch")


def _cross_phase_readiness_section(data: dict[str, pd.DataFrame], alternative_id: str, sku: str, candidate: str, material: pd.DataFrame, impact: pd.DataFrame) -> None:
    st.subheader("Cross-Phase Readiness Summary")
    st.caption(f"SKU/candidate scope: {sku} / {candidate}. Release-readiness status above is overall unless the source says otherwise.")
    rec_check = _first_row(data["integrated_recommendation_check"])
    summary_row = _row_dict(data["alt_summary"], "alternative_id", alternative_id)
    maint = _maintenance_production_rows(data, alternative_id, sku, candidate) if candidate != "Overall" else pd.DataFrame()

    mat_status = material.get("material_readiness_status", pd.Series(dtype=str)).astype(str) if not material.empty else pd.Series(dtype=str)
    shortage_qty = _sum(material, "remaining_shortage_qty")
    supplier_warning_count = int(mat_status.str.contains("LATE|SHORT|REVIEW|UNAVAILABLE", case=False, regex=True).sum()) if not mat_status.empty else 0
    material_affected_ops = impact[impact.get("schedule_impact_status", pd.Series(dtype=str)).astype(str) != "MATERIAL_READY_FOR_OPERATION"]["operation_id"].nunique() if not impact.empty else 0
    dated_conflict_count = int(_bool_series(maint.get("overlap_or_conflict_flag", pd.Series(dtype=str))).sum()) if not maint.empty else 0
    maint_review_count = int(maint.apply(lambda r: "REVIEW" in str(r.to_dict()).upper() or "OVERDUE" in str(r.to_dict()).upper(), axis=1).sum()) if not maint.empty else 0

    cols = st.columns(4)
    with cols[0]:
        st.write("Procurement")
        st.metric("Supplier / Inbound Warnings", supplier_warning_count)
        st.metric("Unresolved Supply Exposure", _fmt(shortage_qty))
    with cols[1]:
        st.write("Inventory")
        inventory_ready = "REVIEW REQUIRED" if shortage_qty > 0 or supplier_warning_count > 0 else "READY"
        st.metric("Inventory Readiness", inventory_ready)
        st.metric("Shortage Exposure", _fmt(shortage_qty))
    with cols[2]:
        st.write("Production")
        st.metric("Finite Schedule Status", summary_row.get("step8f_status", "Unavailable"))
        st.metric("Demand Coverage", _pct(summary_row.get("demand_coverage_pct")))
        st.metric("Bottleneck", summary_row.get("main_bottleneck_workstation", "Unavailable"))
        st.metric("Material-Affected Ops", material_affected_ops)
    with cols[3]:
        st.write("Maintenance")
        st.metric("Overdue / Review Rows", maint_review_count)
        st.metric("Dated Conflict Count", dated_conflict_count)

    if rec_check:
        st.caption(
            f"Integrated recommendation check: {rec_check.get('recommendation_check_status', '')}; "
            f"release readiness {rec_check.get('release_readiness_status', '')}; "
            f"release allowed {rec_check.get('production_release_allowed', '')}."
        )


def _operation_material_status(data: dict[str, pd.DataFrame], candidate_id: str, operation_id: str) -> dict:
    impact = data["schedule_impact"]
    if impact.empty:
        return {"status": "", "blocker": ""}
    subset = impact[
        (impact["schedule_candidate_id"].astype(str) == candidate_id)
        & (impact["operation_id"].astype(str) == operation_id)
    ]
    if subset.empty:
        return {"status": "", "blocker": ""}
    row = subset.iloc[0]
    return {"status": row.get("schedule_impact_status", ""), "blocker": row.get("blocker_reason", "")}


def _main_bottleneck_from_timeline(timeline: pd.DataFrame) -> str:
    if timeline.empty:
        return ""
    flagged = timeline[timeline.get("bottleneck_status", pd.Series("", index=timeline.index)).astype(str).str.upper().isin({"HIGH", "CRITICAL"})]
    source = flagged if not flagged.empty else timeline
    if source.empty:
        return ""
    minutes = source.groupby("workstation_id")["segment_total_minutes"].sum().sort_values(ascending=False)
    return str(minutes.index[0]) if not minutes.empty else ""


def _bom_structure_section(bom: pd.DataFrame, mapping: pd.DataFrame, sku: str) -> None:
    st.subheader("BOM Structure")
    if bom.empty:
        st.info("BOM source file is unavailable.")
        return
    rows = bom[bom["finished_sku"].astype(str) == sku].copy()
    if not mapping.empty:
        rows = rows.merge(
            mapping[["finished_sku", "component_sku", "consuming_operation_id", "quantity_per_finished_unit", "mapping_source", "mapping_status", "review_required_flag"]],
            on=["finished_sku", "component_sku"],
            how="left",
            suffixes=("", "_mapped"),
        )
    display = rows.rename(columns={
        "component_sku": "Component SKU",
        "component_name": "Component Name",
        "quantity_per_finished_unit": "Qty per Finished Unit",
        "consuming_operation_id": "Consuming Operation",
        "mapping_status": "Mapping Status",
        "review_required_flag": "Review Required",
    })
    st.dataframe(
        _display_columns(display, ["Component SKU", "Component Name", "Qty per Finished Unit", "Consuming Operation", "Mapping Status", "Review Required"]),
        hide_index=True,
        width="stretch",
    )


def _material_kpis(rows: pd.DataFrame) -> None:
    status = rows.get("material_readiness_status", pd.Series(dtype=str)).astype(str)
    cols = st.columns(5)
    cols[0].metric("Requirement Rows", len(rows))
    cols[1].metric("Ready On Time", int((status == "READY_ON_TIME").sum()))
    cols[2].metric("Late Inbound", int((status == "LATE_INBOUND_REVIEW").sum()))
    cols[3].metric("Unresolved Shortage", int(status.isin(["SHORTAGE_UNRESOLVED", "SUPPLIER_REVIEW_REQUIRED"]).sum()))
    cols[4].metric("Required Date Unavailable", int((status == "REQUIRED_DATE_UNAVAILABLE_REVIEW").sum()))
    st.metric("Total Unresolved Shortage Quantity", _fmt(_sum(rows, "remaining_shortage_qty")))


def _integrated_material_table(rows: pd.DataFrame, bom: pd.DataFrame) -> None:
    st.subheader("Integrated Material Table")
    if rows.empty:
        st.info("No material rows for the selected candidate.")
        return
    display = rows.copy()
    qty_per = {}
    if not bom.empty:
        qty_per = {
            (str(r["finished_sku"]), str(r["component_sku"])): r.get("quantity_per_finished_unit", "")
            for _, r in bom.iterrows()
        }
    display["Qty per Bike"] = display.apply(lambda r: qty_per.get((str(r["finished_sku"]), str(r["component_sku"])), ""), axis=1)
    display["Component"] = display["component_sku"].astype(str) + " | " + display["component_name"].astype(str)
    display["Status"] = display["material_readiness_status"].map(_material_label)
    display = display.rename(columns={
        "phase4_required_qty": "Total Required",
        "phase3_available_inventory_qty": "Inventory Available",
        "phase3_net_replenishment_need_qty": "Net Replenishment Need",
        "phase2_allocated_supplier_qty": "Supplier Allocated Qty",
        "expected_inbound_qty_available_for_requirement": "Expected Inbound Qty",
        "expected_inbound_date": "Expected Inbound Date",
        "remaining_shortage_qty": "Remaining Shortage",
        "consuming_operation_name": "Consuming Operation",
        "workstation_id": "Workstation",
        "required_date": "Required Date",
        "material_readiness_status": "Material Readiness Status",
    })
    cols = [
        "Component",
        "Qty per Bike",
        "Total Required",
        "Inventory Available",
        "Net Replenishment Need",
        "Supplier Allocated Qty",
        "Expected Inbound Qty",
        "Expected Inbound Date",
        "Remaining Shortage",
        "Consuming Operation",
        "Workstation",
        "Required Date",
        "Status",
        "Material Readiness Status",
    ]
    styled = _display_columns(display, cols).style.apply(_material_row_style, axis=1)
    st.dataframe(styled, width="stretch", hide_index=True)


def _component_detail(rows: pd.DataFrame, impact: pd.DataFrame, bom: pd.DataFrame, data: dict[str, pd.DataFrame]) -> None:
    st.subheader("Component Detail")
    if rows.empty:
        st.info("No components are available for detail.")
        return
    options = [f"{r.component_sku} | {r.component_name}" for r in rows.sort_values("component_sku").itertuples()]
    selected = st.selectbox("Component", options)
    component_sku = selected.split(" | ", 1)[0]
    row = rows[rows["component_sku"].astype(str) == component_sku].iloc[0].to_dict()
    bom_row = bom[(bom.get("finished_sku", pd.Series(dtype=str)).astype(str) == str(row.get("finished_sku"))) & (bom.get("component_sku", pd.Series(dtype=str)).astype(str) == component_sku)]
    qty_per = _cell(bom_row, "quantity_per_finished_unit")
    impact_row = pd.DataFrame()
    if not impact.empty:
        impact_row = impact[
            (impact["schedule_candidate_id"].astype(str) == str(row.get("schedule_candidate_id")))
            & (impact["operation_id"].astype(str) == str(row.get("consuming_operation_id")))
        ]
    blocker = _cell(impact_row, "blocker_reason")
    detail_cols = st.columns(4)
    with detail_cols[0]:
        st.write("BOM / Production")
        st.dataframe(pd.DataFrame([{
            "qty_per_finished_unit": qty_per,
            "total_requirement": row.get("phase4_required_qty", ""),
            "consuming_operation": row.get("consuming_operation_name", ""),
            "workstation": row.get("workstation_id", ""),
            "operation_required_date": row.get("required_date", ""),
        }]), hide_index=True, width="stretch")
    with detail_cols[1]:
        st.write("Inventory")
        st.dataframe(pd.DataFrame([{
            "available_inventory": row.get("phase3_available_inventory_qty", ""),
            "inventory_readiness_status": _inventory_status(row),
            "replenishment_requirement": row.get("phase3_net_replenishment_need_qty", ""),
        }]), hide_index=True, width="stretch")
    with detail_cols[2]:
        st.write("Procurement")
        st.dataframe(pd.DataFrame([{
            "supplier_allocation": row.get("phase2_allocated_supplier_qty", ""),
            "expected_inbound_qty": row.get("expected_inbound_qty_available_for_requirement", ""),
            "expected_inbound_date": row.get("expected_inbound_date", ""),
            "remaining_shortage": row.get("remaining_shortage_qty", ""),
        }]), hide_index=True, width="stretch")
    with detail_cols[3]:
        st.write("Planning Impact")
        st.dataframe(pd.DataFrame([{
            "readiness_status": row.get("material_readiness_status", ""),
            "affected_operation": row.get("consuming_operation_id", ""),
            "blocker_reason": blocker,
            "expected_before_operation_start": row.get("inbound_available_before_operation_flag", ""),
        }]), hide_index=True, width="stretch")


def _shortage_focus(rows: pd.DataFrame) -> None:
    st.subheader("Shortage Focus")
    if rows.empty:
        st.info("No material rows for the selected candidate.")
        return
    severity = {
        "SHORTAGE_UNRESOLVED": 1,
        "SUPPLIER_REVIEW_REQUIRED": 1,
        "REQUIRED_DATE_UNAVAILABLE_REVIEW": 2,
        "LATE_INBOUND_REVIEW": 3,
    }
    focus = rows[rows["material_readiness_status"].astype(str).isin(severity)].copy()
    if focus.empty:
        st.success("No late inbound, unresolved shortage, or undated material requirements for this candidate.")
        return
    focus["_severity_rank"] = focus["material_readiness_status"].map(severity).fillna(9)
    focus = focus.sort_values(["_severity_rank", "remaining_shortage_qty"], ascending=[True, False])
    cols = ["component_sku", "component_name", "consuming_operation_name", "workstation_id", "required_date", "expected_inbound_date", "remaining_shortage_qty", "material_readiness_status"]
    st.dataframe(_display_columns(focus, cols), hide_index=True, width="stretch")


def _operation_detail_panel(nodes: pd.DataFrame, operation_rows: pd.DataFrame, material_rows: pd.DataFrame, data: dict[str, pd.DataFrame], alternative_id: str, operation_id: str) -> None:
    node = nodes[nodes["operation_id"].astype(str) == operation_id]
    detail = operation_rows[operation_rows["operation_id"].astype(str) == operation_id]
    node_row = node.iloc[0].to_dict() if not node.empty else {}
    detail_row = detail.iloc[0].to_dict() if not detail.empty else {}
    op_material = material_rows[material_rows.get("consuming_operation_id", pd.Series(dtype=str)).astype(str) == operation_id]
    maint = _maintenance_status(data, alternative_id, operation_id, detail_row)

    st.subheader("Operation Detail")
    cols = st.columns(4)
    cols[0].metric("Operation", node_row.get("operation_name", operation_id))
    cols[1].metric("Workstation", node_row.get("workstation_id", ""))
    cols[2].metric("Scheduled Qty", _fmt(detail_row.get("schedulable_production_qty")))
    cols[3].metric("Utilization", _pct(node_row.get("utilization_pct")))

    detail_cols = st.columns(3)
    with detail_cols[0]:
        st.write("Dates")
        st.dataframe(pd.DataFrame([{
            "start": node_row.get("proposed_start_datetime", ""),
            "end": node_row.get("proposed_end_datetime", ""),
            "predecessor_ready": detail_row.get("predecessor_ready_datetime", ""),
        }]), hide_index=True, width="stretch")
    with detail_cols[1]:
        st.write("Capacity and Slack")
        st.dataframe(pd.DataFrame([{
            "slack_minutes": node_row.get("slack_time_minutes", ""),
            "critical_path": node_row.get("critical_path_flag", ""),
            "bottleneck": node_row.get("bottleneck_status", ""),
            "operation_status": detail_row.get("operation_schedule_status", ""),
        }]), hide_index=True, width="stretch")
    with detail_cols[2]:
        st.write("Maintenance")
        st.dataframe(pd.DataFrame([maint]), hide_index=True, width="stretch")

    st.write("Material Status")
    if op_material.empty:
        st.info("No direct component rows mapped to this operation.")
    else:
        cols = ["component_sku", "component_name", "required_date", "remaining_shortage_qty", "material_readiness_status", "expected_inbound_date"]
        st.dataframe(_display_columns(op_material, cols), hide_index=True, width="stretch")

    st.write("Blocker Evidence")
    st.dataframe(pd.DataFrame([{
        "material_status": node_row.get("material_readiness_status", ""),
        "wip_status": node_row.get("wip_readiness_status", ""),
        "buffer_status": node_row.get("buffer_status", ""),
        "blocker_type": node_row.get("blocker_type", ""),
        "blocker_reason": detail_row.get("schedule_blocker_reason", ""),
    }]), hide_index=True, width="stretch")


def _build_graph_html(nodes: pd.DataFrame, edges: pd.DataFrame, op_detail: pd.DataFrame, data: dict[str, pd.DataFrame], alternative_id: str, candidate_id: str, show_critical: bool, show_utilization: bool, show_wip: bool, show_materials: bool, show_maintenance: bool) -> tuple[str, dict[str, int]]:
    nodes = nodes.copy()
    sequence_map = _operation_sequence_map(op_detail)
    nodes["_sequence"] = nodes["operation_id"].map(sequence_map)
    nodes["_sequence"] = pd.to_numeric(nodes["_sequence"], errors="coerce")
    nodes["_sequence"] = nodes["_sequence"].fillna(pd.Series(range(1, len(nodes) + 1), index=nodes.index))
    nodes = nodes.sort_values(["_sequence", "operation_id"])
    node_by_id = {str(row["node_id"]): row.to_dict() for _, row in nodes.iterrows()}
    detail_by_op = _index(op_detail, "operation_id")
    access = data["wip_access"]
    buffer = _index(data["wip_buffer"], "wip_buffer_id")
    wip_impact = data["wip_impact"]
    shadow = data["shadow_wip"]

    positions: dict[str, tuple[int, int]] = {}
    grouped = nodes.groupby("_sequence", sort=True)
    x_gap = 300
    y_gap = 180
    for col, (_, group) in enumerate(grouped):
        start_y = 35 + max(0, 2 - len(group)) * 35
        for row_idx, (_, row) in enumerate(group.sort_values("operation_id").iterrows()):
            positions[str(row["node_id"])] = (30 + col * x_gap, start_y + row_idx * y_gap)

    wip_nodes: dict[str, dict] = {}
    display_edges = []
    for _, edge in edges.iterrows():
        from_id = str(edge["from_node_id"])
        to_id = str(edge["to_node_id"])
        if from_id not in positions or to_id not in positions:
            continue
        from_op = str(edge["from_operation_id"])
        to_op = str(edge["to_operation_id"])
        sku = str(edge["finished_sku"])
        rule = _find_access_rule(access, sku, from_op, to_op)
        if show_wip and rule:
            buffer_id = str(rule.get("allowed_output_wip_buffer_id") or rule.get("allowed_input_wip_buffer_id") or "")
            wip_item_id = str(rule.get("allowed_output_wip_item_id") or rule.get("allowed_input_wip_item_id") or "")
            wx = (positions[from_id][0] + positions[to_id][0]) // 2
            wy = (positions[from_id][1] + positions[to_id][1]) // 2 + 82
            wip_node_id = f"WIP-{from_id}-{to_id}"
            wip_nodes[wip_node_id] = {
                "id": wip_node_id,
                "x": wx,
                "y": wy,
                "buffer_id": buffer_id,
                "wip_item_id": wip_item_id,
                "buffer": buffer.get(buffer_id, {}),
                "impact": _wip_impact_for(wip_impact, alternative_id, sku, from_op, buffer_id),
                "occupancy": _projected_wip_occupancy(shadow, buffer.get(buffer_id, {}), wip_impact, alternative_id, candidate_id, sku, from_op, buffer_id, detail_by_op.get(from_op, {})),
                "fifo": _fifo_status(shadow, alternative_id, buffer_id, candidate_id),
            }
            display_edges.append((from_id, wip_node_id, edge.to_dict()))
            display_edges.append((wip_node_id, to_id, edge.to_dict()))
        else:
            display_edges.append((from_id, to_id, edge.to_dict()))

    width = max([x for x, _ in positions.values()] + [v["x"] for v in wip_nodes.values()] + [640]) + 270
    height = max([y for _, y in positions.values()] + [v["y"] for v in wip_nodes.values()] + [380]) + 190
    arrows = [_svg_arrow(_center(source, positions, wip_nodes), _center(target, positions, wip_nodes), meta.get("critical_edge_flag", False)) for source, target, meta in display_edges]
    cards = []
    for node_id, row in node_by_id.items():
        x, y = positions[node_id]
        cards.append(_operation_card_html(row, detail_by_op.get(str(row["operation_id"]), {}), data, alternative_id, x, y, show_critical, show_utilization, show_materials, show_maintenance))
    for wip_node in wip_nodes.values():
        cards.append(_wip_card_html(wip_node))

    legend = """
    <div class="legend">
      <span><b class="critical-dot"></b> Critical path outline</span>
      <span><b class="bottleneck-dot"></b> Bottleneck badge</span>
      <span><b class="material-dot"></b> Material status</span>
      <span><b class="wip-dot"></b> WIP buffer</span>
    </div>
    """
    doc = f"""
    <html>
    <head>{_graph_css()}</head>
    <body>
      {legend}
      <div class="graph" style="width:{width}px;height:{height}px;">
        <svg class="arrows" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
          <defs>
            <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L0,6 L9,3 z" fill="#52616b"></path>
            </marker>
            <marker id="arrowCritical" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L0,6 L9,3 z" fill="#a83246"></path>
            </marker>
          </defs>
          {''.join(arrows)}
        </svg>
        {''.join(cards)}
      </div>
    </body>
    </html>
    """
    counts = {
        "operation_nodes": len(nodes),
        "edge_count": len(edges),
        "wip_nodes": len(wip_nodes),
        "critical_nodes": int(nodes["critical_path_flag"].astype(str).str.lower().isin({"true", "1", "yes"}).sum()),
        "bottleneck_nodes": int(nodes["bottleneck_status"].astype(str).str.upper().isin({"HIGH", "CRITICAL"}).sum()),
        "maintenance_indicators": len(nodes) if show_maintenance else 0,
        "height": height + 40,
    }
    return doc, counts


def _operation_card_html(row: dict, detail: dict, data: dict[str, pd.DataFrame], alternative_id: str, x: int, y: int, show_critical: bool, show_utilization: bool, show_materials: bool, show_maintenance: bool) -> str:
    critical = _truthy(row.get("critical_path_flag"))
    bottleneck = str(row.get("bottleneck_status", "")).upper()
    material = str(row.get("material_readiness_status", ""))
    util = _num(row.get("utilization_pct"))
    scheduled_qty = _fmt(detail.get("schedulable_production_qty"))
    cls = "op-card critical" if show_critical and critical else "op-card"
    bottleneck_badge = f"<span class='badge danger'>BOTTLENECK</span>" if bottleneck in {"HIGH", "CRITICAL"} else ""
    critical_badge = "<span class='badge critical-badge'>CRITICAL PATH</span>" if critical else ""
    material_badge = f"<span class='badge { _material_class(material) }'>{html.escape(_material_label(material))}</span>" if show_materials else ""
    maint_row = _maintenance_status(data, alternative_id, str(row.get("operation_id", "")), detail)
    maint_class = "danger" if maint_row["maintenance_status"] == "CONFLICT" else ("warning" if maint_row["maintenance_status"] in {"DUE SOON", "OVERDUE", "DATE UNKNOWN / REVIEW"} else "ok")
    maint = f"<span class='badge {maint_class}'>{html.escape(str(maint_row['maintenance_status']))}</span>" if show_maintenance else ""
    util_html = f"<div class='bar'><span style='width:{min(max(util,0),100):.1f}%'></span></div><small>{util:.1f}% utilization</small>" if show_utilization else ""
    return f"""
    <div class="{cls}" style="left:{x}px;top:{y}px;">
      <div class="title">{html.escape(str(row.get('operation_name', '')))}</div>
      <div class="sub">{html.escape(str(row.get('workstation_id', '')))}</div>
      <div class="line">Qty {html.escape(scheduled_qty)} | Slack {html.escape(_fmt(row.get('slack_time_minutes')))}m</div>
      {util_html}
      <div class="badges">{critical_badge}{bottleneck_badge}{material_badge}{maint}</div>
    </div>
    """


def _wip_card_html(node: dict) -> str:
    buf = node["buffer"]
    impact = node["impact"]
    occ = node["occupancy"]
    x, y = node["x"], node["y"]
    current = _num(occ.get("projected_balance"))
    max_qty = _num(occ.get("capacity"))
    blocked = _num(occ.get("blocked_qty"))
    occupancy = (current / max_qty * 100) if max_qty else 0.0
    capacity_status = str(impact.get("buffer_capacity_status") or buf.get("buffer_status") or "")
    constrained = "danger" if any(token in capacity_status.upper() for token in ["BLOCK", "FULL", "OVERFLOW"]) else "ok"
    basis = str(occ.get("basis", "GENERIC_BUFFER_STATUS_FALLBACK"))
    timestamp = str(occ.get("timestamp", ""))
    return f"""
    <div class="wip-card {constrained}" style="left:{x}px;top:{y}px;">
      <div class="title">{html.escape(str(node['buffer_id']))}</div>
      <div class="sub">{html.escape(str(node['wip_item_id']))}</div>
      <div class="bar"><span style="width:{min(max(occupancy,0),100):.1f}%"></span></div>
      <small>{current:.1f} / {max_qty:.1f} | {occupancy:.1f}%</small>
      <div class="line">FIFO {html.escape(node['fifo'])}</div>
      <div class="line">{html.escape('Blocked ' + _fmt(blocked) if blocked else 'No blocked qty')}</div>
      <span class="badge {constrained}">{html.escape(capacity_status or 'BUFFER STATUS')}</span>
    </div>
    """


def _graph_css() -> str:
    return """
    <style>
    body { margin:0; font-family: Inter, Segoe UI, Arial, sans-serif; color:#172026; background:#f7f9fb; }
    .legend { display:flex; gap:14px; align-items:center; padding:10px 12px; font-size:12px; color:#52616b; }
    .legend b { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:5px; vertical-align:-1px; }
    .critical-dot { border:2px solid #a83246; } .bottleneck-dot { background:#d83b01; } .material-dot { background:#2e7d32; } .wip-dot { background:#3568a8; }
    .graph { position:relative; overflow:auto; background:linear-gradient(#ffffff, #f7f9fb); border:1px solid #d9e1e8; border-radius:8px; }
    .arrows { position:absolute; left:0; top:0; pointer-events:none; }
    .op-card, .wip-card { position:absolute; width:218px; min-height:112px; border:1px solid #b9c6d2; background:#fff; border-radius:8px; padding:10px; box-shadow:0 2px 8px rgba(24,38,52,.08); }
    .op-card.critical { border:3px solid #a83246; padding:8px; }
    .wip-card { width:164px; min-height:74px; border-style:dashed; background:#f9fcff; padding:8px; }
    .wip-card.danger { border-color:#b42318; background:#fff7f5; }
    .title { font-weight:700; font-size:13px; color:#172026; line-height:1.25; }
    .sub, .line, small { color:#52616b; font-size:11px; line-height:1.35; }
    .bar { height:6px; background:#e6edf3; border-radius:6px; overflow:hidden; margin:7px 0 3px; }
    .bar span { display:block; height:100%; background:#3a7ca5; }
    .badges { display:flex; flex-wrap:wrap; gap:4px; margin-top:6px; }
    .badge { display:inline-block; border-radius:5px; padding:2px 5px; font-size:10px; font-weight:700; color:#fff; margin:2px 3px 0 0; }
    .badge.danger { background:#b42318; } .badge.warning { background:#b7791f; } .badge.ok { background:#2e7d32; }
    .badge.review { background:#5b6270; } .badge.info { background:#3568a8; }
    .badge.critical-badge { background:#a83246; }
    </style>
    """


def _svg_arrow(start: tuple[int, int], end: tuple[int, int], critical: object) -> str:
    x1, y1 = start
    x2, y2 = end
    color = "#a83246" if _truthy(critical) else "#52616b"
    marker = "arrowCritical" if _truthy(critical) else "arrow"
    mid = (x1 + x2) / 2
    return f"<path d='M{x1},{y1} C{mid},{y1} {mid},{y2} {x2},{y2}' stroke='{color}' stroke-width='2' fill='none' marker-end='url(#{marker})'></path>"


def _center(node_id: str, positions: dict[str, tuple[int, int]], wip_nodes: dict[str, dict]) -> tuple[int, int]:
    if node_id in positions:
        x, y = positions[node_id]
        return x + 109, y + 56
    node = wip_nodes[node_id]
    return node["x"] + 82, node["y"] + 41


@st.cache_data
def _load_all_data() -> dict[str, pd.DataFrame]:
    return {name: _load_csv(path) for name, path in FILES.items()}


def _load_csv(path: Path) -> pd.DataFrame:
    try:
        if path.exists():
            return pd.read_csv(path)
    except Exception as exc:
        st.warning(f"Could not load {path.name}: {exc}")
    return pd.DataFrame()


def _operation_detail(data: dict[str, pd.DataFrame], alternative_id: str, candidate_id: str) -> pd.DataFrame:
    df = data["operation_detail"]
    if df.empty:
        return df
    return df[(df["alternative_id"].astype(str) == alternative_id) & (df["schedule_candidate_id"].astype(str) == candidate_id)].copy()


def _operation_sequence_map(op_detail: pd.DataFrame) -> dict[str, float]:
    if op_detail.empty or "operation_sequence" not in op_detail.columns:
        return {}
    return {str(row["operation_id"]): _num(row["operation_sequence"]) for _, row in op_detail.iterrows()}


def _find_access_rule(access: pd.DataFrame, sku: str, from_op: str, to_op: str) -> dict:
    if access.empty:
        return {}
    subset = access[
        (access["finished_sku"].astype(str) == sku)
        & (access["operation_id"].astype(str) == from_op)
        & (access["successor_operation_id"].astype(str) == to_op)
    ]
    return subset.iloc[0].to_dict() if not subset.empty else {}


def _wip_impact_for(wip: pd.DataFrame, alternative_id: str, sku: str, from_op: str, buffer_id: str) -> dict:
    if wip.empty:
        return {}
    subset = wip[
        (wip["alternative_id"].astype(str) == alternative_id)
        & (wip["finished_sku"].astype(str) == sku)
        & (wip["operation_id"].astype(str) == from_op)
    ]
    if buffer_id and "wip_buffer_id" in subset.columns:
        exact = subset[subset["wip_buffer_id"].astype(str) == buffer_id]
        if not exact.empty:
            return exact.iloc[0].to_dict()
    return subset.iloc[0].to_dict() if not subset.empty else {}


def _projected_wip_occupancy(shadow: pd.DataFrame, generic_buffer: dict, wip_impact: pd.DataFrame, alternative_id: str, candidate_id: str, sku: str, producer_operation_id: str, buffer_id: str, producer_detail: dict) -> dict:
    timestamp = _timestamp_for_buffer_check(wip_impact, alternative_id, sku, producer_operation_id, buffer_id) or str(producer_detail.get("proposed_end_datetime", "") or "")
    capacity = _num(generic_buffer.get("max_buffer_qty"))
    blocked = _num(generic_buffer.get("blocked_wip_qty"))
    if not shadow.empty and buffer_id and timestamp:
        subset = shadow[
            (shadow["alternative_id"].astype(str) == alternative_id)
            & (shadow["wip_buffer_id"].astype(str) == buffer_id)
            & (pd.to_datetime(shadow["event_datetime"], errors="coerce") <= pd.to_datetime(timestamp, errors="coerce"))
        ].copy()
        if not subset.empty:
            subset["_event_dt"] = pd.to_datetime(subset["event_datetime"], errors="coerce")
            subset["_seq"] = pd.to_numeric(subset.get("event_sequence", 0), errors="coerce").fillna(0)
            last = subset.sort_values(["_event_dt", "_seq"]).iloc[-1]
            return {
                "projected_balance": _num(last.get("shadow_ending_qty")),
                "capacity": _num(last.get("buffer_max_qty")) or capacity,
                "blocked_qty": blocked,
                "timestamp": _clean_datetime(timestamp),
                "basis": "TIME_CAUSAL_SHADOW_WIP_LEDGER",
            }
    return {
        "projected_balance": _num(generic_buffer.get("current_wip_qty")),
        "capacity": capacity,
        "blocked_qty": blocked,
        "timestamp": "",
        "basis": "GENERIC_BUFFER_STATUS_FALLBACK",
    }


def _timestamp_for_buffer_check(wip_impact: pd.DataFrame, alternative_id: str, sku: str, producer_operation_id: str, buffer_id: str) -> str:
    if wip_impact.empty:
        return ""
    subset = wip_impact[
        (wip_impact["alternative_id"].astype(str) == alternative_id)
        & (wip_impact["finished_sku"].astype(str) == sku)
        & (wip_impact["operation_id"].astype(str) == producer_operation_id)
        & (wip_impact["wip_buffer_id"].astype(str) == buffer_id)
    ]
    if subset.empty:
        return ""
    return str(subset.iloc[0].get("buffer_check_datetime", "") or "")


def _fifo_status(shadow: pd.DataFrame, alternative_id: str, buffer_id: str, candidate_id: str = "") -> str:
    if shadow.empty or not buffer_id:
        return "UNAVAILABLE"
    subset = shadow[(shadow["alternative_id"].astype(str) == alternative_id) & (shadow["wip_buffer_id"].astype(str) == buffer_id)]
    if subset.empty:
        return "NO EVENTS"
    if candidate_id and "schedule_candidate_id" in subset.columns:
        candidate_subset = subset[(subset["schedule_candidate_id"].fillna("").astype(str).isin(["", candidate_id]))]
        if not candidate_subset.empty:
            subset = candidate_subset
    methods = set(subset.get("lot_selection_method", pd.Series(dtype=str)).dropna().astype(str))
    return "FIFO" if "FIFO" in methods else "REVIEW"


def _maintenance_status(data: dict[str, pd.DataFrame], alternative_id: str, operation_id: str, detail_row: dict | None = None) -> dict:
    maintenance = data["maintenance_impact"]
    window_check = data.get("maintenance_window_check", pd.DataFrame())
    detail_row = detail_row or {}
    segment_ids = [part.strip() for part in str(detail_row.get("final_operation_segment_ids", "")).split(";") if part.strip()]
    if not segment_ids and not data.get("operation_segments", pd.DataFrame()).empty:
        segments = data["operation_segments"]
        candidate_id = str(detail_row.get("schedule_candidate_id", ""))
        segment_subset = segments[
            (segments["alternative_id"].astype(str) == alternative_id)
            & (segments["operation_id"].astype(str) == operation_id)
        ]
        if candidate_id:
            segment_subset = segment_subset[segment_subset["schedule_candidate_id"].astype(str) == candidate_id]
        segment_ids = segment_subset.get("operation_segment_id", pd.Series(dtype=str)).dropna().astype(str).tolist()
    if segment_ids and not window_check.empty and "production_operation_segment_id" in window_check.columns:
        subset = window_check[
            (window_check["alternative_id"].astype(str) == alternative_id)
            & (window_check["production_operation_segment_id"].astype(str).isin(segment_ids))
        ].copy()
        if not subset.empty:
            if _bool_series(subset.get("dated_overlap_flag", pd.Series(dtype=str))).any() or _bool_series(subset.get("machine_state_unavailable_flag", pd.Series(dtype=str))).any():
                return {"maintenance_status": "CONFLICT", "next_maintenance_datetime": _first_nonblank(subset, "maintenance_start_datetime"), "maintenance_source": "DATED_WINDOW_CHECK", "evidence": "Production segment overlaps dated maintenance or machine-unavailable evidence."}
            selected = subset[_bool_series(subset.get("maintenance_window_selected_flag", pd.Series(dtype=str)))]
            selected_date = _first_nonblank(selected, "maintenance_start_datetime")
            if selected_date:
                return {"maintenance_status": "OK", "next_maintenance_datetime": selected_date, "maintenance_source": "DATED_WINDOW_CHECK", "evidence": "Dated maintenance window evidence exists; no production overlap in selected graph operation."}
            status = _first_nonblank(subset, "maintenance_window_check_status")
            risk = _first_nonblank(subset, "maintenance_risk_level")
            if status == "MAINTENANCE_RISK_REVIEW" or risk:
                return {"maintenance_status": "DATE UNKNOWN / REVIEW", "next_maintenance_datetime": "", "maintenance_source": "RISK_ONLY_NO_DATED_DOWNTIME", "evidence": f"{status or 'Maintenance risk review'}; risk={risk or 'UNKNOWN'}."}
    if maintenance.empty:
        return {"maintenance_status": "DATE UNKNOWN / REVIEW", "evidence": "No maintenance impact rows loaded."}
    subset = maintenance[(maintenance["alternative_id"].astype(str) == alternative_id) & (maintenance["operation_id"].astype(str) == operation_id)]
    if subset.empty:
        return {"maintenance_status": "DATE UNKNOWN / REVIEW", "evidence": "No candidate-specific dated maintenance evidence."}
    row = subset.iloc[0].to_dict()
    if _truthy(row.get("selected_window_maintenance_conflict_flag")) or _truthy(row.get("maintenance_conflict_flag")):
        status = "CONFLICT"
    else:
        status = row.get("selected_window_maintenance_status") or row.get("maintenance_feasibility_status") or "DATE UNKNOWN / REVIEW"
    if not str(row.get("maintenance_avoidance_evidence", "")).strip() and status != "CONFLICT":
        status = "DATE UNKNOWN / REVIEW"
    return {
        "maintenance_status": status,
        "next_maintenance_datetime": "",
        "maintenance_source": "MAINTENANCE_IMPACT_SUMMARY",
        "breakdown_risk_level": row.get("breakdown_risk_level", ""),
        "maintenance_conflict_flag": row.get("maintenance_conflict_flag", ""),
        "evidence": row.get("maintenance_avoidance_evidence", "Risk/review evidence only."),
    }


def _join_unique(series: pd.Series) -> str:
    values = [str(value) for value in series.dropna().astype(str) if str(value).strip() and str(value).strip().lower() != "nan"]
    return "; ".join(sorted(set(values)))


def _highest_capacity_status(series: pd.Series) -> str:
    rank = {
        "FINITE_CAPACITY_BLOCKED": 4,
        "CAPACITY_BLOCKED": 4,
        "REVIEW_REQUIRED": 3,
        "FINITE_CAPACITY_HIGH_UTILIZATION": 2,
        "HIGH_UTILIZATION_WARNING": 2,
        "FINITE_CAPACITY_PARTIAL_QUANTITY": 2,
        "FINITE_CAPACITY_FEASIBLE": 1,
        "FEASIBLE": 1,
    }
    values = [str(value).strip() for value in series.dropna() if str(value).strip()]
    if not values:
        return ""
    return max(values, key=lambda value: rank.get(value.upper(), 0))


def _highest_bottleneck_status(series: pd.Series) -> str:
    rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    values = [str(value).strip() for value in series.dropna() if str(value).strip() and str(value).strip().lower() != "nan"]
    if not values:
        return ""
    return max(values, key=lambda value: rank.get(value.upper(), 0))


def _load_band(utilization_pct: float) -> str:
    if utilization_pct >= 85:
        return "Bottleneck"
    if utilization_pct >= 70:
        return "Heavy Load"
    if utilization_pct <= 30:
        return "Underused"
    return "Normal Load"


def _main_bottleneck_from_capacity(ws: pd.DataFrame) -> str:
    if ws.empty:
        return ""
    flagged = ws[ws.get("bottleneck_status", pd.Series("", index=ws.index)).astype(str).str.upper().isin({"CRITICAL", "HIGH"})]
    source = flagged if not flagged.empty else ws
    source = source.sort_values(["utilization_pct", "scheduled_workload_minutes"], ascending=[False, False])
    return str(source.iloc[0].get("workstation_id", "")) if not source.empty else ""


def _row_dict(df: pd.DataFrame, key_column: str, key_value: str) -> dict:
    if df.empty or key_column not in df.columns:
        return {}
    subset = df[df[key_column].astype(str) == str(key_value)]
    return subset.iloc[0].to_dict() if not subset.empty else {}


def _latest_shadow_event(events: pd.DataFrame) -> dict:
    if events.empty:
        return {}
    rows = events.copy()
    rows["_event_dt"] = pd.to_datetime(rows.get("event_datetime", ""), errors="coerce")
    rows["_seq"] = pd.to_numeric(rows.get("event_sequence", 0), errors="coerce").fillna(0)
    rows = rows[rows["_event_dt"].notna()].sort_values(["_event_dt", "_seq"])
    return rows.iloc[-1].to_dict() if not rows.empty else {}


def _candidate_shadow_events(shadow: pd.DataFrame, alternative_id: str, sku: str, candidate_id: str, buffer_id: str) -> pd.DataFrame:
    if shadow.empty:
        return pd.DataFrame()
    events = shadow[
        (shadow.get("alternative_id", pd.Series(dtype=str)).astype(str) == alternative_id)
        & (shadow.get("wip_buffer_id", pd.Series(dtype=str)).astype(str) == buffer_id)
    ].copy()
    if events.empty:
        return events
    if "finished_sku" in events.columns:
        sku_values = events["finished_sku"].fillna("").astype(str).str.strip()
        events = events[sku_values.isin(["", sku, "nan"])]
    if events.empty:
        return events
    if "schedule_candidate_id" in events.columns:
        candidate_values = events["schedule_candidate_id"].fillna("").astype(str).str.strip()
        event_types = events.get("shadow_event_type", pd.Series("", index=events.index)).fillna("").astype(str)
        candidate_independent = candidate_values.isin(["", "nan"]) & event_types.eq("STARTING_ACCEPTED_WIP")
        events = events[candidate_values.eq(candidate_id) | candidate_independent]
    return events.copy()


def _nonblank(series: pd.Series) -> list[str]:
    return [str(value).strip() for value in series.dropna().astype(str) if str(value).strip() and str(value).strip().lower() != "nan"]


def _highest_due_status(series: pd.Series) -> str:
    rank = {"OVERDUE": 4, "DUE_NOW": 3, "DUE_SOON": 2, "NOT_DUE": 1, "OK": 1}
    values = _nonblank(series)
    if not values:
        return "DATE UNKNOWN"
    return max(values, key=lambda value: rank.get(value.upper(), 0))


def _maintenance_due_label(row: dict) -> str:
    if _num(row.get("overdue_count")) > 0:
        return "OVERDUE"
    if _num(row.get("due_now_count")) > 0:
        return "DUE_NOW"
    if _num(row.get("due_soon_count")) > 0:
        return "DUE_SOON"
    return "OK" if row else "DATE UNKNOWN"


def _maintenance_status_label(due_status: str, feasibility: dict, production_impact: dict) -> str:
    blocker = str(production_impact.get("scheduling_blocker_status", "")).upper()
    feasible = str(feasibility.get("best_schedule_feasibility_status", "")).upper()
    if blocker in {"MULTI_BLOCKED", "CREW_BLOCKED", "SPARE_PART_BLOCKED"} or feasible in {"MULTI_BLOCKED", "REVIEW_REQUIRED"}:
        return "REVIEW REQUIRED"
    if "OVERDUE" in str(due_status).upper():
        return "OVERDUE"
    if "DUE" in str(due_status).upper():
        return "DUE SOON"
    return "OK"


def _dated_window_value(df: pd.DataFrame, column: str) -> str:
    if df.empty or column not in df.columns:
        return ""
    dated = pd.to_datetime(df[column], errors="coerce")
    if dated.notna().any():
        return dated.dropna().min().strftime("%Y-%m-%dT%H:%M")
    return ""


def _time_until_label(value: str) -> str:
    if not value:
        return "DATE UNKNOWN"
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return "DATE UNKNOWN"
    delta_days = (dt - pd.Timestamp.now(tz=None)).total_seconds() / 86400
    if delta_days < 0:
        return "OVERDUE"
    if delta_days <= 7:
        return "DUE SOON"
    return f"{delta_days:.0f} days"


def _valid_dated_windows(windows: pd.DataFrame) -> pd.DataFrame:
    if windows.empty or "maintenance_start_datetime" not in windows.columns or "maintenance_end_datetime" not in windows.columns:
        return pd.DataFrame()
    rows = windows.copy()
    rows["_start"] = pd.to_datetime(rows["maintenance_start_datetime"], errors="coerce")
    rows["_end"] = pd.to_datetime(rows["maintenance_end_datetime"], errors="coerce")
    return rows[rows["_start"].notna() & rows["_end"].notna() & (rows["_end"] > rows["_start"])].copy()


def _maintenance_review_severity(row: pd.Series) -> str:
    text = str(row.to_dict()).upper()
    if any(token in text for token in ["CRITICAL", "OVERDUE", "CONFLICT"]):
        return "CRITICAL"
    if "HIGH" in text or "BLOCKED" in text:
        return "HIGH"
    if "REVIEW" in text or "DATE UNKNOWN" in text:
        return "MEDIUM"
    return "LOW"


def _validation_affected(validation: pd.DataFrame, check_names: list[str]) -> int:
    if validation.empty or "check_name" not in validation.columns:
        return 0
    subset = validation[validation["check_name"].astype(str).isin(check_names)]
    if "status" in subset.columns:
        subset = subset[subset["status"].astype(str).str.upper() == "FAIL"]
    return int(pd.to_numeric(subset.get("affected_rows", 0), errors="coerce").fillna(0).sum())


def _peak_concurrency(segments: pd.DataFrame) -> int:
    if segments.empty:
        return 0
    rows = segments.copy()
    rows["_start"] = pd.to_datetime(rows.get("proposed_start_datetime", ""), errors="coerce")
    rows["_end"] = pd.to_datetime(rows.get("proposed_end_datetime", ""), errors="coerce")
    rows = rows[rows["_start"].notna() & rows["_end"].notna() & (rows["_end"] > rows["_start"])]
    events = []
    for _, row in rows.iterrows():
        events.append((row["_start"], 1))
        events.append((row["_end"], -1))
    current = 0
    peak = 0
    for _, delta in sorted(events, key=lambda item: (item[0], item[1])):
        current += delta
        peak = max(peak, current)
    return peak


def _index(df: pd.DataFrame, column: str) -> dict[str, dict]:
    if df.empty or column not in df.columns:
        return {}
    return {str(row[column]): row.to_dict() for _, row in df.iterrows()}


def _first_row(df: pd.DataFrame) -> dict:
    return df.iloc[0].to_dict() if not df.empty else {}


def _cell(df: pd.DataFrame, column: str) -> str:
    if not df.empty and column in df.columns:
        return str(df.iloc[0][column])
    return ""


def _display_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    display = df[[col for col in columns if col in df.columns]].copy()
    return display.rename(columns={col: _DISPLAY_LABELS.get(col, col) for col in display.columns})


_DISPLAY_LABELS = {
    "alternative_id": "Alternative",
    "alternative_name": "Alternative Name",
    "alternative_type": "Alternative Type",
    "step8f_status": "Finite Schedule Status",
    "schedule_candidate_id": "Schedule Candidate",
    "finished_sku": "Finished SKU",
    "operation_id": "Operation ID",
    "operation_name": "Operation",
    "workstation_id": "Workstation",
    "machine_id": "Machine",
    "labor_skill_id": "Labor Skill",
    "candidate_schedule_period": "Planning Period",
    "candidate_schedule_day": "Planning Day",
    "candidate_schedule_shift": "Planning Shift",
    "proposed_start_datetime": "Start",
    "proposed_end_datetime": "Finish",
    "proposed_schedule_date": "Schedule Date",
    "proposed_shift_id": "Shift",
    "proposed_window_id": "Calendar Window",
    "segment_sequence": "Segment",
    "segment_scheduled_qty": "Scheduled Qty",
    "requested_production_qty": "Requested Qty",
    "schedulable_production_qty": "Scheduled Qty",
    "unscheduled_qty": "Unscheduled Qty",
    "completed_full_route_qty": "Completed Full-Route Qty",
    "demand_coverage_pct": "Demand Coverage %",
    "planned_demand_qty": "Planned Demand Qty",
    "scheduled_processing_minutes": "Processing Minutes",
    "setup_minutes": "Setup Minutes",
    "setup_switch_count": "Setup Switches",
    "main_bottleneck_workstation": "Main Bottleneck",
    "buffer_blocked_qty": "Buffer-Blocked Qty",
    "wip_blocked_qty": "WIP-Blocked Qty",
    "validated_real_cost": "Validated Real Cost",
    "assumed_cost_or_penalty": "Assumed Cost / Penalty",
    "cost_confidence_level": "Cost Confidence",
    "recommendation_rank": "Rank",
    "material_readiness_status": "Material Status",
    "expected_inbound_date": "Expected Inbound",
    "remaining_shortage_qty": "Remaining Shortage",
    "critical_path_flag": "Critical Path",
    "slack_time_minutes": "Slack Minutes",
    "utilization_pct": "Utilization %",
    "bottleneck_status": "Bottleneck",
    "component_sku": "Component SKU",
    "component_name": "Component",
    "consuming_operation_name": "Consuming Operation",
    "required_date": "Required Date",
    "source_phase": "Source Phase",
    "source_file": "Source File",
    "recommended_manager_action": "Recommended Manager Action",
    "business_impact": "Business Impact",
    "issue_type": "Issue",
    "issue_severity": "Severity",
    "risk_type": "Risk",
    "severity": "Severity",
    "readiness_status": "Readiness Status",
    "release_readiness_status": "Release Readiness",
    "production_release_allowed": "Release Allowed",
}


def _sum(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    return round(pd.to_numeric(df[column], errors="coerce").fillna(0).sum(), 4)


def _num(value: object) -> float:
    try:
        if pd.isna(value) or str(value).strip() == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt(value: object) -> str:
    number = _num(value)
    if abs(number) >= 1000:
        return f"{number:,.1f}"
    return f"{number:.1f}"


def _pct(value: object) -> str:
    return f"{_num(value):.1f}%"


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _first_nonblank(df: pd.DataFrame, column: str) -> str:
    if df.empty or column not in df.columns:
        return ""
    values = df[column].dropna().astype(str)
    values = values[values.str.strip().ne("")]
    return values.iloc[0] if not values.empty else ""


def _equivalent_group(rec: dict, summary: pd.DataFrame) -> str:
    explicit = str(rec.get("equivalent_result_group", "") or "").strip()
    if explicit and explicit.lower() != "nan":
        return explicit.replace(",", " / ")
    if summary.empty:
        return ""
    metrics = [
        "demand_coverage_pct",
        "completed_full_route_qty",
        "unscheduled_qty",
        "validated_real_cost",
        "assumed_cost_or_penalty",
        "setup_minutes",
        "setup_switch_count",
        "buffer_blocked_qty",
        "wip_blocked_qty",
        "main_bottleneck_workstation",
    ]
    available = [col for col in metrics if col in summary.columns]
    groups = []
    for _, rows in summary.groupby(available, dropna=False):
        if len(rows) > 1:
            groups.append(" / ".join(rows["alternative_id"].astype(str).sort_values()))
    return "; ".join(groups)


def _equivalent_label_for_alt(alternative_id: str, rec: dict, summary: pd.DataFrame) -> str:
    groups = _equivalent_group(rec, summary)
    for group in groups.split("; "):
        members = [member.strip() for member in group.replace(",", " / ").split(" / ") if member.strip()]
        if alternative_id in members:
            return group
    return ""


def _clean_datetime(value: object) -> str:
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return str(value or "")
    return dt.strftime("%Y-%m-%dT%H:%M")


def _material_label(status: str) -> str:
    text = status.upper()
    if "READY" in text:
        return "READY"
    if "LATE" in text:
        return "LATE INBOUND"
    if "SHORT" in text or "BLOCK" in text:
        return "SHORT"
    if "UNAVAILABLE" in text:
        return "REQUIRED DATE UNAVAILABLE"
    return "REVIEW REQUIRED"


def _material_class(status: str) -> str:
    label = _material_label(status)
    if label == "READY":
        return "ok"
    if label in {"LATE INBOUND", "REQUIRED DATE UNAVAILABLE"}:
        return "warning"
    if label == "SHORT":
        return "danger"
    return "review"


def _material_row_style(row: pd.Series) -> list[str]:
    status = str(row.get("Material Readiness Status", row.get("Status", ""))).upper()
    if "READY_ON_TIME" in status:
        color = "background-color: #eef7ee"
    elif "LATE" in status:
        color = "background-color: #fff7df"
    elif "UNAVAILABLE" in status:
        color = "background-color: #f4f1ff"
    elif "SHORT" in status or "SUPPLIER_REVIEW" in status:
        color = "background-color: #fff0ed"
    else:
        color = "background-color: #f3f5f7"
    return [color for _ in row]


def _inventory_status(row: dict) -> str:
    required = _num(row.get("phase4_required_qty"))
    available = _num(row.get("phase3_available_inventory_qty"))
    if available >= required and required > 0:
        return "INVENTORY_COVERS_REQUIREMENT"
    if available > 0:
        return "PARTIAL_INVENTORY_COVERAGE"
    return "INVENTORY_REPLENISHMENT_REVIEW"


if __name__ == "__main__":
    main()
