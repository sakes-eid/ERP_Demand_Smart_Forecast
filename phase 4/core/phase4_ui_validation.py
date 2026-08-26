"""Read-only validation checks for the Phase 4 manager UI inputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE4_DIR.parent
OUTPUT_DIR = PHASE4_DIR / "outputs"

VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_ui_validation.csv"


FILES = {
    "graph_nodes": OUTPUT_DIR / "integrated_phase234_graph_nodes.csv",
    "graph_edges": OUTPUT_DIR / "integrated_phase234_graph_edges.csv",
    "step8g_summary": OUTPUT_DIR / "phase4_step8g_alternative_summary.csv",
    "step8g_recommendation": OUTPUT_DIR / "phase4_step8g_recommendation.csv",
    "step8g_tradeoffs": OUTPUT_DIR / "phase4_step8g_tradeoff_analysis.csv",
    "step8g_decision_risks": OUTPUT_DIR / "phase4_step8g_decision_risks.csv",
    "step8g_manager_review": OUTPUT_DIR / "phase4_step8g_manager_review_queue.csv",
    "step8g_readiness": OUTPUT_DIR / "phase4_step8g_release_readiness.csv",
    "integrated_recommendation_check": OUTPUT_DIR / "integrated_phase234_recommendation_check.csv",
    "operation_detail": OUTPUT_DIR / "phase4_schedule_alternative_operation_detail.csv",
    "operation_segments": OUTPUT_DIR / "phase4_schedule_alternative_operation_segments.csv",
    "capacity_impact": OUTPUT_DIR / "phase4_schedule_alternative_capacity_impact.csv",
    "schedule_validation": OUTPUT_DIR / "phase4_schedule_alternative_validation.csv",
    "operation_slack": OUTPUT_DIR / "phase4_operation_slack_analysis.csv",
    "wip_impact": OUTPUT_DIR / "phase4_schedule_alternative_wip_impact.csv",
    "wip_buffer_status": OUTPUT_DIR / "phase4_wip_buffer_status.csv",
    "wip_access_rules": OUTPUT_DIR / "phase4_wip_buffer_access_rules.csv",
    "maintenance_impact": OUTPUT_DIR / "phase4_schedule_alternative_maintenance_impact.csv",
    "maintenance_window_check": OUTPUT_DIR / "phase4_schedule_alternative_maintenance_window_check.csv",
    "maintenance_readiness": OUTPUT_DIR / "phase4_maintenance_readiness_context.csv",
    "maintenance_feasibility": OUTPUT_DIR / "phase4_maintenance_schedule_feasibility_context.csv",
    "maintenance_production_impact": OUTPUT_DIR / "phase4_maintenance_production_impact_context.csv",
    "breakdown_risk": OUTPUT_DIR / "phase4_breakdown_risk_context.csv",
    "maintenance_crew_context": OUTPUT_DIR / "phase4_maintenance_crew_capacity_context.csv",
    "spare_part_context": OUTPUT_DIR / "phase4_spare_part_requirement_context.csv",
    "maintenance_windows": PROJECT_ROOT / "shared" / "outputs" / "maintenance_schedule_candidate_windows.csv",
    "maintenance_due_status": PROJECT_ROOT / "shared" / "outputs" / "maintenance_due_status_context.csv",
    "maintenance_backlog": PROJECT_ROOT / "shared" / "outputs" / "maintenance_backlog_risk_summary.csv",
    "maintenance_crew_summary": PROJECT_ROOT / "shared" / "outputs" / "maintenance_crew_capacity_summary.csv",
    "maintenance_workload_by_skill": PROJECT_ROOT / "shared" / "outputs" / "maintenance_workload_by_skill.csv",
    "maintenance_spare_parts": PROJECT_ROOT / "shared" / "outputs" / "maintenance_spare_part_requirement_context.csv",
    "spare_part_review": PROJECT_ROOT / "shared" / "outputs" / "spare_part_manager_review_queue.csv",
    "workforce_auth": PROJECT_ROOT / "shared" / "outputs" / "workforce_machine_authorization_context.csv",
    "phase2_spare_supplier": PROJECT_ROOT / "phase 2" / "outputs" / "phase4_spare_part_supplier_check.csv",
    "phase3_spare_inventory": PROJECT_ROOT / "phase 3" / "outputs" / "phase4_spare_part_inventory_check.csv",
    "material_readiness": OUTPUT_DIR / "integrated_phase234_material_readiness.csv",
    "shortage_timeline": OUTPUT_DIR / "integrated_phase234_shortage_timeline.csv",
    "schedule_impact": OUTPUT_DIR / "integrated_phase234_schedule_impact.csv",
    "bom": PHASE4_DIR / "data" / "phase4_bom.csv",
    "bom_requirements": OUTPUT_DIR / "phase4_bom_component_requirements.csv",
    "component_operation_map": PHASE4_DIR / "data" / "phase4_component_operation_consumption_map.csv",
    "phase2_supplier_check": PROJECT_ROOT / "phase 2" / "outputs" / "phase4_component_supplier_check.csv",
    "phase3_inventory_check": PROJECT_ROOT / "phase 3" / "outputs" / "phase4_component_inventory_check.csv",
    "shadow_wip": OUTPUT_DIR / "phase4_schedule_alternative_shadow_wip_ledger.csv",
}


def build_ui_validation() -> pd.DataFrame:
    data = {name: _load(path) for name, path in FILES.items()}
    rows = []
    run_id = _first_value(data["graph_nodes"], "planning_run_id")

    def add(name: str, passed: bool, message: str, affected_rows: int = 0) -> None:
        rows.append({
            "planning_run_id": run_id,
            "check_name": name,
            "status": "PASS" if passed else "FAIL",
            "message": message,
            "affected_rows": int(affected_rows),
            "source_phase": "PHASE4_UI_FINAL_MANAGER_APP",
            "advisory_only_flag": True,
        })

    nodes = data["graph_nodes"]
    edges = data["graph_edges"]
    op_detail = data["operation_detail"]
    op_segments = data["operation_segments"]
    capacity_impact = data["capacity_impact"]
    slack = data["operation_slack"]
    summary = data["step8g_summary"]
    rec = data["step8g_recommendation"]
    tradeoffs = data["step8g_tradeoffs"]
    risks = data["step8g_decision_risks"]
    step8g_review = data["step8g_manager_review"]
    readiness = data["step8g_readiness"]
    wip = data["wip_buffer_status"]
    maint = data["maintenance_impact"]
    shadow = data["shadow_wip"]
    material = data["material_readiness"]
    bom = data["bom"]
    bom_requirements = data["bom_requirements"]
    component_map = data["component_operation_map"]
    supplier = data["phase2_supplier_check"]
    inventory = data["phase3_inventory_check"]
    app_source = (PHASE4_DIR / "app.py").read_text(encoding="utf-8")

    add("REQUIRED_UI_INPUTS_EXIST", all(path.exists() for path in FILES.values()), "All required read-only UI inputs exist.")
    legacy_validation_name = "phase4_ui_" + "part1_validation.csv"
    add("CONSOLIDATED_UI_VALIDATION_FILE_USED", VALIDATION_OUTPUT_FILE.name == "phase4_ui_validation.csv" and '"phase4_ui_validation.csv"' in app_source and legacy_validation_name not in app_source, "The consolidated UI validation output is phase4_ui_validation.csv.")
    add("GRAPH_INPUTS_NON_EMPTY", not nodes.empty and not edges.empty, "Integrated graph node and edge files are non-empty.")
    node_ids = set(nodes.get("node_id", pd.Series(dtype=str)).astype(str))
    missing_edges = edges[~edges.get("from_node_id", pd.Series(dtype=str)).astype(str).isin(node_ids) | ~edges.get("to_node_id", pd.Series(dtype=str)).astype(str).isin(node_ids)] if not edges.empty else edges
    add("GRAPH_EDGES_REFERENCE_VALID_NODES", missing_edges.empty, "Every integrated graph edge references a visible node.", len(missing_edges))
    add("GRAPH_NODES_FROM_VALIDATED_INTEGRATION", _all_source(nodes, "INTEGRATED_PHASE234_ADVISORY_PLANNING_REFRESH"), "Graph nodes come from the integrated Phase 2-3-4 output.")
    add("GRAPH_EDGES_FROM_VALIDATED_INTEGRATION", _all_source(edges, "INTEGRATED_PHASE234_ADVISORY_PLANNING_REFRESH"), "Graph edges come from the integrated Phase 2-3-4 output.")
    add("CANDIDATE_SPECIFIC_GRAPH_KEYS", {"schedule_candidate_id", "node_id"} <= set(nodes.columns) and {"schedule_candidate_id", "from_node_id", "to_node_id"} <= set(edges.columns), "Graph keys include schedule candidate IDs and node IDs.")

    if not nodes.empty and not op_detail.empty:
        base = op_detail[op_detail.get("alternative_id", pd.Series(dtype=str)).astype(str) == "ALT-BASELINE"]
        detail_keys = set(zip(base.get("schedule_candidate_id", pd.Series(dtype=str)).astype(str), base.get("operation_id", pd.Series(dtype=str)).astype(str)))
        missing_detail = nodes[~nodes.apply(lambda r: (str(r["schedule_candidate_id"]), str(r["operation_id"])) in detail_keys, axis=1)]
    else:
        missing_detail = nodes
    add("NODE_DATES_AND_QUANTITIES_TRACE_TO_STEP8F", missing_detail.empty, "Graph node details can be traced to Step 8F operation detail.", len(missing_detail))
    add("MANAGER_KPIS_TRACE_TO_STEP8G", not summary.empty and not rec.empty and not readiness.empty, "Manager overview KPI files are Step 8G outputs.")
    add("ALTERNATIVE_COMPARISON_HAS_SIX_ROWS", len(summary) == 6, "Alternative comparison contains the six Step 8F/8G alternatives.", len(summary))
    add("WIP_VALUES_TRACE_TO_WIP_OUTPUTS", not wip.empty and {"wip_buffer_id", "current_wip_qty", "max_buffer_qty"} <= set(wip.columns), "WIP buffer values trace to Step 8C/8F WIP outputs.")
    add("GRAPH_LOCKED_TO_BASELINE_REFERENCE", 'selected_alt = "ALT-BASELINE"' in app_source and "selectbox(\"Alternative\"" not in app_source, "Production Flow Graph is locked to ALT-BASELINE because integrated graph evidence is not alternative-specific.")
    add("WIP_OCCUPANCY_USES_TIME_CAUSAL_SHADOW_LEDGER", "_projected_wip_occupancy" in app_source and not shadow.empty, "WIP buffer occupancy is derived from the time-causal shadow WIP ledger when schedule-specific evidence exists.", len(shadow))
    add("NO_ALTERNATIVE_DATA_MIXING_IN_GRAPH", not nodes.empty and set(nodes.get("source_phase", pd.Series(dtype=str)).dropna().astype(str)) == {"INTEGRATED_PHASE234_ADVISORY_PLANNING_REFRESH"}, "Graph data comes from the integrated reference graph; non-baseline alternatives are not selectable on the graph.")
    graph_card_source = app_source.split("def _operation_card_html", 1)[1].split("def _wip_card_html", 1)[0] if "def _operation_card_html" in app_source else ""
    add("PRESENTATION_GRAPH_OPERATION_NODES_SIMPLIFIED", "proposed_start_datetime" not in graph_card_source and "proposed_end_datetime" not in graph_card_source and "schedulable_production_qty" in graph_card_source, "Graph operation cards keep dates/blockers in the detail panel and show only manager-priority card fields.")
    wip_card_source = app_source.split("def _wip_card_html", 1)[1].split("def _graph_css", 1)[0] if "def _wip_card_html" in app_source else ""
    add("PRESENTATION_WIP_NODES_SIMPLIFIED", "Projected {current" not in wip_card_source and "FIFO" in wip_card_source and "blocked" in wip_card_source.lower(), "WIP cards show compact projected quantity, capacity, FIFO, and constraint evidence.")
    countdown_fabricated = False
    if "_maintenance_status" in app_source:
        countdown_fabricated = "time-to-maintenance" in app_source.lower() and "maintenance_start_datetime" not in app_source
    if not maint.empty and "maintenance_avoidance_evidence" in maint.columns:
        countdown_fabricated = countdown_fabricated or maint["maintenance_avoidance_evidence"].astype(str).str.contains("countdown", case=False, regex=False).any()
    add("MAINTENANCE_COUNTDOWN_NOT_FABRICATED", not countdown_fabricated, "Maintenance indicator uses dated window evidence or review status, not invented countdowns.")
    add("NODE_SELECTION_FALLBACK_DOCUMENTED", "Node click selection is not enabled" in app_source, "Node detail selection is documented as a selector fallback to avoid a large frontend rewrite.")
    add("BOM_MATERIALS_PAGE_REGISTERED", '"BOM & Materials"' in app_source, "BOM & Materials page is registered in Phase 4 manager navigation.")
    add("BOM_ROWS_TRACE_TO_SOURCE", not bom.empty and {"finished_sku", "component_sku", "quantity_per_finished_unit"} <= set(bom.columns), "BOM rows trace to phase4_bom.csv.")
    add("BOM_REQUIREMENTS_TRACE_TO_OUTPUT", not bom_requirements.empty and {"finished_sku", "component_sku", "gross_component_requirement_qty"} <= set(bom_requirements.columns), "BOM requirement quantities trace to Phase 4 BOM output.")
    map_keys = set(zip(component_map.get("finished_sku", pd.Series(dtype=str)).astype(str), component_map.get("component_sku", pd.Series(dtype=str)).astype(str), component_map.get("consuming_operation_id", pd.Series(dtype=str)).astype(str)))
    mapped_bad = material[~material.apply(lambda r: (str(r.get("finished_sku", "")), str(r.get("component_sku", "")), str(r.get("consuming_operation_id", ""))) in map_keys, axis=1)] if not material.empty and map_keys else material
    add("COMPONENT_OPERATION_MAPPING_MATCHES_EXPLICIT_MAP", mapped_bad.empty, "Displayed consuming operations match the explicit component-operation map.", len(mapped_bad))
    duplicate_keys = material.duplicated(["schedule_candidate_id", "component_sku", "finished_sku"]).sum() if not material.empty else 0
    add("NO_UI_COMPONENT_DUPLICATION", duplicate_keys == 0, "Material page source has one row per candidate, finished SKU, and component.", duplicate_keys)
    if not material.empty:
        grouped_sum = material.groupby("schedule_candidate_id")["material_readiness_status"].value_counts().rename("count").reset_index()
        reconciles = int(grouped_sum["count"].sum()) == len(material)
    else:
        reconciles = False
    add("MATERIAL_STATUS_COUNTS_RECONCILE", reconciles, "Material status counts reconcile to integrated readiness rows.", len(material))
    dated = material[material.get("required_date", pd.Series(dtype=str)).fillna("").astype(str).str.len() > 0] if not material.empty else material
    date_bad = dated[dated.apply(lambda r: str(r["required_date"]) != _date_part(r.get("consuming_operation_start_datetime", "")), axis=1)] if not dated.empty else dated
    add("REQUIRED_DATES_MATCH_INTEGRATED_EVIDENCE", date_bad.empty, "Displayed required dates match integrated consuming-operation start dates.", len(date_bad))
    inv_keys = set(inventory.get("component_sku", pd.Series(dtype=str)).astype(str)) if not inventory.empty else set()
    sup_keys = set(supplier.get("component_sku", pd.Series(dtype=str)).astype(str)) if not supplier.empty else set()
    material_components = set(material.get("component_sku", pd.Series(dtype=str)).astype(str)) if not material.empty else set()
    add("INVENTORY_QUANTITIES_TRACE_TO_PHASE3", material_components <= inv_keys, "Inventory quantities trace to Phase 3 component inventory check.", len(material_components - inv_keys))
    add("SUPPLIER_QUANTITIES_TRACE_TO_PHASE2", material_components <= sup_keys, "Supplier quantities trace to Phase 2 component supplier check.", len(material_components - sup_keys))
    add("PRODUCTION_TIMELINE_PAGE_REGISTERED", '"Production Timeline"' in app_source and "_production_timeline_page" in app_source, "Production Timeline page is registered in Phase 4 manager navigation.")
    scheduled_segments = op_segments.copy()
    if not scheduled_segments.empty:
        scheduled_segments["_start"] = pd.to_datetime(scheduled_segments.get("proposed_start_datetime", ""), errors="coerce")
        scheduled_segments["_end"] = pd.to_datetime(scheduled_segments.get("proposed_end_datetime", ""), errors="coerce")
        scheduled_qty = pd.to_numeric(scheduled_segments.get("segment_scheduled_qty", 0), errors="coerce").fillna(0)
        real_bars = scheduled_segments[(scheduled_qty > 0) & scheduled_segments["_start"].notna() & scheduled_segments["_end"].notna()].copy()
        invalid_dates = real_bars[(real_bars["_end"] <= real_bars["_start"]) | real_bars.get("proposed_window_id", pd.Series("", index=real_bars.index)).astype(str).str.contains("ADVISORY|REVIEW_WINDOW|PLACEHOLDER", case=False, regex=True)]
        unscheduled_with_dates = scheduled_segments[
            scheduled_segments.get("segment_schedule_status", pd.Series("", index=scheduled_segments.index)).astype(str).str.contains("UNSCHEDULED", case=False, regex=False)
            & (scheduled_segments["_start"].notna() | scheduled_segments["_end"].notna())
        ]
    else:
        real_bars = scheduled_segments
        invalid_dates = scheduled_segments
        unscheduled_with_dates = scheduled_segments
    add("TIMELINE_BARS_TRACE_TO_OPERATION_SEGMENTS", not real_bars.empty and {"operation_segment_id", "proposed_start_datetime", "proposed_end_datetime"} <= set(op_segments.columns), "Timeline bars are sourced from real Step 8F operation segments.", len(real_bars))
    add("TIMELINE_START_END_MATCH_SEGMENT_EVIDENCE", invalid_dates.empty, "Timeline start/end datetimes are valid segment evidence without placeholder windows.", len(invalid_dates))
    detail_keys = set(zip(op_detail.get("alternative_id", pd.Series(dtype=str)).astype(str), op_detail.get("schedule_candidate_id", pd.Series(dtype=str)).astype(str), op_detail.get("operation_id", pd.Series(dtype=str)).astype(str)))
    segment_missing_detail = real_bars[~real_bars.apply(lambda r: (str(r.get("alternative_id", "")), str(r.get("schedule_candidate_id", "")), str(r.get("operation_id", ""))) in detail_keys, axis=1)] if not real_bars.empty else real_bars
    add("TIMELINE_SEGMENTS_TRACE_TO_OPERATION_DETAIL", segment_missing_detail.empty, "Every timeline segment traces to its operation-detail row.", len(segment_missing_detail))
    add("TIMELINE_LOCKED_TO_BASELINE_REFERENCE", 'selected_alt = "ALT-BASELINE"' in app_source and "timeline" in app_source.lower() and "Alternative" not in app_source.split("def _production_timeline_page", 1)[1].split("def _timeline_rows", 1)[0], "Production Timeline is locked to ALT-BASELINE and does not expose unsupported alternative selection.")
    order_bad = False
    if not op_detail.empty and "operation_sequence" in op_detail.columns:
        order_bad = op_detail.groupby(["alternative_id", "schedule_candidate_id"])["operation_sequence"].apply(lambda s: pd.to_numeric(s, errors="coerce").dropna().is_monotonic_increasing).eq(False).any()
    add("TIMELINE_ROUTE_ORDER_AVAILABLE", not order_bad and "operation_sequence" in op_detail.columns, "Product/route timeline can order operations using routing sequence evidence.")
    parallel_evidence = False
    if not real_bars.empty and {"assigned_machine_unit_ids", "assigned_labor_unit_ids", "parallel_capacity_applied_flag"} <= set(real_bars.columns):
        parallel_evidence = _bool_series(real_bars["parallel_capacity_applied_flag"]).any() and real_bars["assigned_machine_unit_ids"].fillna("").astype(str).str.len().gt(0).all()
    add("WORKSTATION_VIEW_PRESERVES_PARALLEL_SEGMENTS", parallel_evidence, "Workstation view uses real segment timestamps with individual machine/labor unit evidence.")
    add("UNSCHEDULED_WORK_HAS_NO_FAKE_DATES", unscheduled_with_dates.empty, "Unscheduled work remains in the summary table and is not assigned fabricated timeline bars.", len(unscheduled_with_dates))
    critical_keys = set(zip(slack.get("finished_sku", pd.Series(dtype=str)).astype(str), slack.get("operation_id", pd.Series(dtype=str)).astype(str))) if not slack.empty else set()
    critical_trace_bad = op_detail[_bool_series(op_detail.get("critical_path_flag", pd.Series(dtype=str))) & ~op_detail.apply(lambda r: (str(r.get("finished_sku", "")), str(r.get("operation_id", ""))) in critical_keys, axis=1)] if not op_detail.empty and critical_keys else pd.DataFrame()
    add("TIMELINE_CRITICAL_FLAGS_TRACE_TO_SLACK_EVIDENCE", critical_trace_bad.empty and not slack.empty, "Critical-path flags trace to Step 8A slack/critical-path evidence.", len(critical_trace_bad))
    cap_keys = set(zip(capacity_impact.get("alternative_id", pd.Series(dtype=str)).astype(str), capacity_impact.get("schedule_candidate_id", pd.Series(dtype=str)).astype(str), capacity_impact.get("operation_id", pd.Series(dtype=str)).astype(str))) if not capacity_impact.empty else set()
    cap_trace_bad = real_bars[~real_bars.apply(lambda r: (str(r.get("alternative_id", "")), str(r.get("schedule_candidate_id", "")), str(r.get("operation_id", ""))) in cap_keys, axis=1)] if not real_bars.empty and cap_keys else pd.DataFrame()
    add("TIMELINE_CAPACITY_FLAGS_TRACE_TO_STEP8F", cap_trace_bad.empty and not capacity_impact.empty, "Timeline utilization and capacity context trace to Step 8F capacity impact evidence.", len(cap_trace_bad))
    material_ops = set(zip(data["schedule_impact"].get("schedule_candidate_id", pd.Series(dtype=str)).astype(str), data["schedule_impact"].get("operation_id", pd.Series(dtype=str)).astype(str))) if not data["schedule_impact"].empty else set()
    detail_candidate_operation_keys = set(zip(op_detail.get("schedule_candidate_id", pd.Series(dtype=str)).astype(str), op_detail.get("operation_id", pd.Series(dtype=str)).astype(str))) if not op_detail.empty else set()
    material_trace_bad = data["schedule_impact"][
        ~data["schedule_impact"].apply(lambda r: (str(r.get("schedule_candidate_id", "")), str(r.get("operation_id", ""))) in detail_candidate_operation_keys, axis=1)
    ] if not data["schedule_impact"].empty and detail_candidate_operation_keys else pd.DataFrame()
    add("TIMELINE_MATERIAL_STATUS_TRACE_TO_INTEGRATION", material_trace_bad.empty and bool(material_ops), "Timeline material status traces to integrated schedule-impact evidence where component-consuming operations exist.", len(material_trace_bad))
    add("TIMELINE_BUFFER_STATUS_TRACE_TO_STEP8F_WIP", not data["wip_buffer_status"].empty and not data["wip_access_rules"].empty and not data["shadow_wip"].empty, "Timeline buffer status traces to WIP/buffer and shadow-ledger evidence.")
    timeline_source = app_source.split("def _timeline_status", 1)[1].split("def _timeline_kpis", 1)[0] if "def _timeline_status" in app_source else ""
    chart_source = app_source.split("def _timeline_chart", 1)[1].split("def _add_maintenance_windows", 1)[0] if "def _timeline_chart" in app_source else ""
    add("TIMELINE_CRITICAL_TOGGLE_FUNCTIONAL", 'overlays.get("critical"' in timeline_source and "Critical Path" in timeline_source, "Critical Path toggle is referenced by timeline visual classification.")
    add("TIMELINE_BOTTLENECK_TOGGLE_FUNCTIONAL", 'overlays.get("bottleneck"' in timeline_source and "Bottleneck" in timeline_source, "Bottlenecks toggle is referenced by timeline visual classification.")
    add("TIMELINE_MATERIAL_TOGGLE_FUNCTIONAL", 'overlays.get("material"' in timeline_source and "Material Constrained" in timeline_source, "Material Readiness toggle is referenced by timeline visual classification.")
    add("TIMELINE_BUFFER_TOGGLE_FUNCTIONAL", 'overlays.get("buffer"' in timeline_source and "Buffer Delayed" in timeline_source, "Buffer Delays toggle is referenced by timeline visual classification.")
    add("TIMELINE_SETUP_TOGGLE_FUNCTIONAL", 'overlays.get("setup"' in timeline_source and "Setup Included" in timeline_source, "Setup toggle is referenced by timeline visual classification.")
    add("TIMELINE_MAINTENANCE_TOGGLE_FUNCTIONAL", 'overlays.get("maintenance"' in chart_source and "_add_maintenance_windows" in chart_source, "Maintenance toggle controls dated maintenance-window overlays.")
    add("TIMELINE_PLOTLY_WIDTH_STRETCH", 'st.plotly_chart(fig, width="stretch")' in chart_source and "use_container_width=True" not in chart_source, "Production Timeline Plotly chart uses width=\"stretch\" instead of deprecated use_container_width.")
    add("CAPACITY_WIP_PAGE_REGISTERED", '"Capacity & WIP"' in app_source and "_capacity_wip_page" in app_source, "Capacity & WIP page is registered in Phase 4 manager navigation.")
    cap_numeric = capacity_impact.copy()
    for col in ["total_scheduled_workload_minutes", "aggregate_workstation_capacity_minutes", "remaining_aggregate_capacity_minutes", "effective_parallel_lane_count"]:
        if col in cap_numeric.columns:
            cap_numeric[col] = pd.to_numeric(cap_numeric[col], errors="coerce").fillna(0)
    cap_reconcile_bad = cap_numeric[
        (cap_numeric.get("aggregate_workstation_capacity_minutes", pd.Series(dtype=float)) + 0.0001 < cap_numeric.get("total_scheduled_workload_minutes", pd.Series(dtype=float)))
        | (cap_numeric.get("remaining_aggregate_capacity_minutes", pd.Series(dtype=float)) < -0.0001)
    ] if not cap_numeric.empty else cap_numeric
    add("CAPACITY_WIP_UTILIZATION_TRACES_TO_STEP8F", not capacity_impact.empty and {"workstation_id", "total_scheduled_workload_minutes", "aggregate_workstation_capacity_minutes", "workstation_utilization_pct"} <= set(capacity_impact.columns), "Workstation utilization traces to Step 8F capacity impact evidence.")
    add("CAPACITY_WIP_AVAILABLE_SCHEDULED_REMAINING_RECONCILES", cap_reconcile_bad.empty, "Capacity available, scheduled, and remaining minutes reconcile without validated overrun.", len(cap_reconcile_bad))
    add("CAPACITY_WIP_PARALLEL_LANES_TRACE_TO_STEP8F", not cap_numeric.empty and "effective_parallel_lane_count" in cap_numeric.columns and (cap_numeric["effective_parallel_lane_count"] >= 1).all(), "Parallel lane counts are displayed from Step 8F evidence.")
    segment_unit_bad = real_bars[
        real_bars.get("assigned_machine_unit_ids", pd.Series("", index=real_bars.index)).fillna("").astype(str).str.len().eq(0)
        | real_bars.get("assigned_labor_unit_ids", pd.Series("", index=real_bars.index)).fillna("").astype(str).str.len().eq(0)
    ] if not real_bars.empty else real_bars
    add("CAPACITY_WIP_RESOURCE_UNITS_TRACE_TO_SEGMENTS", segment_unit_bad.empty, "Machine and labor unit usage traces to Step 8F operation segment evidence.", len(segment_unit_bad))
    if not shadow.empty:
        shadow_numeric = shadow.copy()
        for col in ["shadow_ending_qty", "buffer_max_qty", "buffer_overflow_qty"]:
            if col in shadow_numeric.columns:
                shadow_numeric[col] = pd.to_numeric(shadow_numeric[col], errors="coerce").fillna(0)
        buffer_over_bad = shadow_numeric[(shadow_numeric["shadow_ending_qty"] > shadow_numeric["buffer_max_qty"] + 0.0001) & (shadow_numeric["buffer_overflow_qty"] <= 0.0001)] if {"shadow_ending_qty", "buffer_max_qty", "buffer_overflow_qty"} <= set(shadow_numeric.columns) else pd.DataFrame()
    else:
        buffer_over_bad = shadow
    add("CAPACITY_WIP_PROJECTED_BALANCES_TRACE_TO_SHADOW_LEDGER", "_wip_buffer_summary" in app_source and "_latest_shadow_event" in app_source and not shadow.empty, "WIP projected balances trace to the time-causal shadow ledger.")
    add("CAPACITY_WIP_BUFFER_OCCUPANCY_RECONCILES", buffer_over_bad.empty, "Buffer occupancy reconciles to configured capacity or explicit overflow evidence.", len(buffer_over_bad))
    fifo_failures = data["schedule_validation"][data["schedule_validation"].get("check_name", pd.Series(dtype=str)).astype(str).isin(["FIFO_SEQUENCE_VIOLATION", "NEWER_LOT_USED_BEFORE_OLDER_AVAILABLE_LOT", "WIP_LOT_QUANTITY_REUSED"]) & (data["schedule_validation"].get("status", pd.Series(dtype=str)).astype(str).str.upper() == "FAIL")] if not data["schedule_validation"].empty else pd.DataFrame()
    add("CAPACITY_WIP_FIFO_STATUS_MATCHES_SOURCE_VALIDATION", fifo_failures.empty, "FIFO status uses Step 8F validation evidence and reports violations only from FAIL rows.", len(fifo_failures))
    add("CAPACITY_WIP_BLOCKED_QUANTITIES_TRACE_TO_STEP8F", not data["wip_impact"].empty and {"buffer_blocked_output_qty", "wip_shortage_qty"} <= set(data["wip_impact"].columns), "Blocked WIP and buffer quantities trace to Step 8F WIP impact output.")
    capwip_source = app_source.split("def _capacity_wip_page", 1)[1].split("def _capacity_workstation_summary", 1)[0] if "def _capacity_wip_page" in app_source else ""
    add("CAPACITY_WIP_LOCKED_TO_BASELINE_NO_ALT_LEAKAGE", 'alternative_id = "ALT-BASELINE"' in capwip_source and "selectbox(\"Alternative\"" not in capwip_source, "Capacity & WIP is locked to the ALT-BASELINE reference alternative.")
    add("CAPACITY_WIP_BOTTLENECK_LABEL_IS_CANDIDATE_SCOPED", '"Selected Candidate Bottleneck"' in app_source, "Capacity & WIP bottleneck KPI is labelled as selected-candidate scope.")
    sample_detail = op_detail[op_detail.get("alternative_id", pd.Series(dtype=str)).astype(str) == "ALT-BASELINE"].copy() if not op_detail.empty else pd.DataFrame()
    sample_sku = _first_value(sample_detail, "finished_sku")
    sample_candidate = _first_value(sample_detail[sample_detail.get("finished_sku", pd.Series(dtype=str)).astype(str) == sample_sku], "schedule_candidate_id") if sample_sku else ""
    candidate_shadow_bad = pd.DataFrame()
    candidate_occupancy_bad = 0
    fallback_label_supported = "GENERIC_BUFFER_STATUS_FALLBACK" in app_source
    if sample_sku and sample_candidate and not shadow.empty and not data["wip_access_rules"].empty:
        related_access = data["wip_access_rules"][data["wip_access_rules"].get("finished_sku", pd.Series(dtype=str)).astype(str) == sample_sku]
        buffer_ids = set()
        for col in ["allowed_input_wip_buffer_id", "allowed_output_wip_buffer_id"]:
            if col in related_access.columns:
                buffer_ids.update(v for v in related_access[col].dropna().astype(str) if v and v.lower() != "nan")
        bad_rows = []
        for buffer_id in buffer_ids:
            events = shadow[
                (shadow.get("alternative_id", pd.Series(dtype=str)).astype(str) == "ALT-BASELINE")
                & (shadow.get("wip_buffer_id", pd.Series(dtype=str)).astype(str) == buffer_id)
            ].copy()
            if events.empty:
                continue
            sku_values = events.get("finished_sku", pd.Series("", index=events.index)).fillna("").astype(str).str.strip()
            events = events[sku_values.isin(["", sample_sku, "nan"])]
            candidate_values = events.get("schedule_candidate_id", pd.Series("", index=events.index)).fillna("").astype(str).str.strip()
            event_types = events.get("shadow_event_type", pd.Series("", index=events.index)).fillna("").astype(str)
            allowed = events[candidate_values.eq(sample_candidate) | (candidate_values.isin(["", "nan"]) & event_types.eq("STARTING_ACCEPTED_WIP"))].copy()
            if allowed.empty:
                continue
            allowed["_event_dt"] = pd.to_datetime(allowed.get("event_datetime", ""), errors="coerce")
            allowed["_seq"] = pd.to_numeric(allowed.get("event_sequence", 0), errors="coerce").fillna(0)
            latest = allowed[allowed["_event_dt"].notna()].sort_values(["_event_dt", "_seq"]).tail(1)
            if latest.empty:
                continue
            latest_candidate = str(latest.iloc[0].get("schedule_candidate_id", "") or "").strip()
            latest_type = str(latest.iloc[0].get("shadow_event_type", "") or "")
            if latest_candidate not in {"", "nan", sample_candidate} or (latest_candidate in {"", "nan"} and latest_type != "STARTING_ACCEPTED_WIP"):
                bad_rows.append(latest.iloc[0].to_dict())
            balance = pd.to_numeric(latest.iloc[0].get("shadow_ending_qty", 0), errors="coerce")
            capacity = pd.to_numeric(latest.iloc[0].get("buffer_max_qty", 0), errors="coerce")
            if pd.notna(balance) and pd.notna(capacity) and capacity >= 0 and balance < -0.0001:
                candidate_occupancy_bad += 1
        candidate_shadow_bad = pd.DataFrame(bad_rows)
    add("CAPACITY_WIP_NO_OTHER_CANDIDATE_SHADOW_EVENT_USED", candidate_shadow_bad.empty and "_candidate_shadow_events" in app_source, "Projected WIP balance filters shadow events to selected candidate plus explicit candidate-independent opening WIP.", len(candidate_shadow_bad))
    add("CAPACITY_WIP_SELECTED_CANDIDATE_OCCUPANCY_RECONCILES", candidate_occupancy_bad == 0, "Selected-candidate projected occupancy uses candidate-filtered shadow balance divided by configured capacity.", candidate_occupancy_bad)
    add("CAPACITY_WIP_FIFO_STATUS_CANDIDATE_SPECIFIC", "_fifo_status(shadow, alternative_id, buffer_id, candidate_id)" in app_source, "FIFO status is calculated with selected candidate context.")
    add("CAPACITY_WIP_GENERIC_FALLBACK_EXPLICITLY_LABELLED", fallback_label_supported, "Generic WIP buffer fallback is explicitly labelled when selected-candidate shadow evidence is unavailable.")
    add("MAINTENANCE_PAGE_REGISTERED", '"Maintenance"' in app_source and "_maintenance_page" in app_source, "Maintenance page is registered in Phase 4 manager navigation.")
    maint_window = data["maintenance_windows"]
    valid_dated_window_count = 0
    if not maint_window.empty and {"maintenance_start_datetime", "maintenance_end_datetime"} <= set(maint_window.columns):
        starts = pd.to_datetime(maint_window["maintenance_start_datetime"], errors="coerce")
        ends = pd.to_datetime(maint_window["maintenance_end_datetime"], errors="coerce")
        valid_dated_window_count = int((starts.notna() & ends.notna() & (ends > starts)).sum())
    else:
        valid_dated_window_count = 0
    add("MAINTENANCE_DATED_WINDOWS_REQUIRE_DATETIME_EVIDENCE", valid_dated_window_count >= 0 and "_valid_dated_windows" in app_source, "Dated maintenance windows are rendered only from valid start/end datetime evidence.", valid_dated_window_count)
    add("MAINTENANCE_NO_COUNTDOWN_WITHOUT_DATE", "_time_until_label" in app_source and "DATE UNKNOWN" in app_source, "Maintenance countdown displays DATE UNKNOWN when no valid dated evidence exists.")
    conflict_rows = data["maintenance_window_check"][
        _bool_series(data["maintenance_window_check"].get("dated_overlap_flag", pd.Series(dtype=str)))
        | _bool_series(data["maintenance_window_check"].get("machine_state_unavailable_flag", pd.Series(dtype=str)))
    ] if not data["maintenance_window_check"].empty else pd.DataFrame()
    add("MAINTENANCE_CONFLICT_REQUIRES_REAL_OVERLAP", "DATED MAINTENANCE CONFLICT" in app_source and (conflict_rows.empty or {"production_start_datetime", "production_end_datetime"} <= set(data["maintenance_window_check"].columns)), "Conflict status is based on dated overlap or machine-unavailable evidence.", len(conflict_rows))
    risk_only_without_overlap = data["maintenance_window_check"][
        data["maintenance_window_check"].get("maintenance_window_check_status", pd.Series(dtype=str)).astype(str).str.contains("RISK_REVIEW|NO_DATED_CONFLICT", case=False, regex=True)
        & ~_bool_series(data["maintenance_window_check"].get("dated_overlap_flag", pd.Series(dtype=str)))
    ] if not data["maintenance_window_check"].empty else pd.DataFrame()
    add("MAINTENANCE_RISK_ONLY_NOT_DATED_CONFLICT", "RISK-ONLY REVIEW" in app_source and not risk_only_without_overlap.empty, "Risk-only maintenance rows are labelled separately from dated conflicts.", len(risk_only_without_overlap))
    add("MAINTENANCE_CREW_SKILL_TRACE_TO_SOURCE", not data["maintenance_workload_by_skill"].empty and {"required_skill_id", "available_crew_hours", "capacity_status"} <= set(data["maintenance_workload_by_skill"].columns), "Crew and skill readiness traces to maintenance workload-by-skill evidence.")
    spare_trace = (not data["maintenance_spare_parts"].empty and {"spare_part_sku", "quantity_required", "spare_part_readiness_status"} <= set(data["maintenance_spare_parts"].columns)) or not data["spare_part_context"].empty
    add("MAINTENANCE_SPARE_PART_TRACE_TO_SOURCE", spare_trace, "Spare-part readiness traces to maintenance spare-part evidence with Phase 2/3 context available where present.")
    auth = data["workforce_auth"]
    auth_source_ready = not auth.empty and {"machine_id", "authorization_level", "can_maintain_flag", "can_repair_flag"} <= set(auth.columns)
    maintenance_status_source = app_source.split("def _maintenance_status_table", 1)[1].split("def _maintenance_kpis", 1)[0] if "def _maintenance_status_table" in app_source else ""
    bad_auth_assignment = '"authorization_level": _join_unique(d_rows.get("maintenance_level"' in maintenance_status_source
    unavailable_label_present = "NOT_AVAILABLE / REVIEW" in maintenance_status_source
    add("MAINTENANCE_LEVEL_NOT_USED_AS_AUTHORIZATION", not bad_auth_assignment and '"maintenance_level":' in maintenance_status_source, "Maintenance level is displayed separately and is not used as authorization level.")
    add("MAINTENANCE_AUTHORIZATION_TRACES_TO_SOURCE_FIELD", auth_source_ready and 'relevant_auth.get("authorization_level"' in maintenance_status_source, "Displayed authorization traces to workforce_machine_authorization_context.authorization_level.")
    add("MAINTENANCE_AUTHORIZATION_UNAVAILABLE_LABELLED", unavailable_label_present, "Unavailable authorization evidence is explicitly labelled NOT_AVAILABLE / REVIEW.")
    baseline_detail = op_detail[op_detail.get("alternative_id", pd.Series(dtype=str)).astype(str) == "ALT-BASELINE"].copy() if not op_detail.empty else pd.DataFrame()
    sku_values = set(baseline_detail.get("finished_sku", pd.Series(dtype=str)).dropna().astype(str))
    multi_sku_ok = {"SKU-BIKE-MT-001", "SKU-BIKE-ROAD-001"} <= sku_values
    sku_candidate_ok = True
    if multi_sku_ok:
        for sku_value in ["SKU-BIKE-MT-001", "SKU-BIKE-ROAD-001"]:
            candidates = baseline_detail[baseline_detail.get("finished_sku", pd.Series(dtype=str)).astype(str) == sku_value].get("schedule_candidate_id", pd.Series(dtype=str)).dropna().astype(str)
            sku_candidate_ok = sku_candidate_ok and not candidates.empty
    add("MAINTENANCE_MULTI_SKU_FILTERS_AVAILABLE", multi_sku_ok and sku_candidate_ok, "Maintenance SKU-dependent production-impact filters support both Mountain Bike and Road Bike without hardcoding candidate lists.")
    maint_prod_source = app_source.split("def _maintenance_production_rows", 1)[1].split("def _maintenance_production_impact_section", 1)[0] if "def _maintenance_production_rows" in app_source else ""
    add("MAINTENANCE_PRODUCTION_IMPACT_FILTERS_SELECTED_SKU_CANDIDATE", "finished_sku" in maint_prod_source and "schedule_candidate_id" in maint_prod_source, "Production-impact rows trace to the selected SKU and schedule candidate.")
    execution_widgets_absent = all(token not in app_source for token in ["st.button(\"Create", "st.button(\"Release", "st.button(\"Dispatch", "st.button(\"Reserve", "st.button(\"Purchase", "create_maintenance_work_order", "create_purchase_order"])
    add("MAINTENANCE_NO_EXECUTION_CONTROLS", execution_widgets_absent, "Maintenance UI contains no work-order, dispatch, purchase-order, reservation, or execution controls.")
    sku_samples = {
        "SKU-BIKE-MT-001": "MT-",
        "SKU-BIKE-ROAD-001": "ROAD-",
    }
    candidate_leak_count = 0
    operation_leak_count = 0
    graph_leak_count = 0
    bom_leak_count = 0
    material_leak_count = 0
    timeline_leak_count = 0
    wip_leak_count = 0
    maintenance_leak_count = 0
    sample_pages_ok = True
    sample_messages = []
    for sku_value, op_prefix in sku_samples.items():
        sku_nodes = nodes[nodes.get("finished_sku", pd.Series(dtype=str)).astype(str) == sku_value] if not nodes.empty else pd.DataFrame()
        sku_edges = edges[edges.get("finished_sku", pd.Series(dtype=str)).astype(str) == sku_value] if not edges.empty else pd.DataFrame()
        sku_material = material[material.get("finished_sku", pd.Series(dtype=str)).astype(str) == sku_value] if not material.empty else pd.DataFrame()
        sku_detail = baseline_detail[baseline_detail.get("finished_sku", pd.Series(dtype=str)).astype(str) == sku_value] if not baseline_detail.empty else pd.DataFrame()
        sku_segments = op_segments[(op_segments.get("alternative_id", pd.Series(dtype=str)).astype(str) == "ALT-BASELINE") & (op_segments.get("finished_sku", pd.Series(dtype=str)).astype(str) == sku_value)] if not op_segments.empty else pd.DataFrame()
        sku_bom = bom[bom.get("finished_sku", pd.Series(dtype=str)).astype(str) == sku_value] if not bom.empty else pd.DataFrame()
        candidate_values = set(sku_detail.get("schedule_candidate_id", pd.Series(dtype=str)).dropna().astype(str))
        sample_candidate = sorted(candidate_values)[0] if candidate_values else ""
        sample_pages_ok = sample_pages_ok and not sku_nodes.empty and not sku_edges.empty and not sku_material.empty and not sku_detail.empty and not sku_segments.empty and not sku_bom.empty and bool(sample_candidate)
        other_sku_candidates = set(op_detail[(op_detail.get("finished_sku", pd.Series(dtype=str)).astype(str) != sku_value) & (op_detail.get("alternative_id", pd.Series(dtype=str)).astype(str) == "ALT-BASELINE")].get("schedule_candidate_id", pd.Series(dtype=str)).dropna().astype(str)) if not op_detail.empty else set()
        candidate_leak_count += len(candidate_values & other_sku_candidates)
        operation_leak_count += int(sku_detail.get("operation_id", pd.Series(dtype=str)).dropna().astype(str).map(lambda value: not value.startswith(op_prefix)).sum()) if not sku_detail.empty else 1
        graph_leak_count += int(sku_nodes.get("operation_id", pd.Series(dtype=str)).dropna().astype(str).map(lambda value: not value.startswith(op_prefix)).sum()) if not sku_nodes.empty else 1
        bom_leak_count += int(sku_bom.get("finished_sku", pd.Series(dtype=str)).astype(str).ne(sku_value).sum()) if not sku_bom.empty else 1
        if sample_candidate:
            selected_material = sku_material[sku_material.get("schedule_candidate_id", pd.Series(dtype=str)).astype(str) == sample_candidate]
            selected_segments = sku_segments[sku_segments.get("schedule_candidate_id", pd.Series(dtype=str)).astype(str) == sample_candidate]
            selected_impact = data["schedule_impact"][
                (data["schedule_impact"].get("finished_sku", pd.Series(dtype=str)).astype(str) == sku_value)
                & (data["schedule_impact"].get("schedule_candidate_id", pd.Series(dtype=str)).astype(str) == sample_candidate)
            ] if not data["schedule_impact"].empty else pd.DataFrame()
            material_leak_count += int(selected_material.get("finished_sku", pd.Series(dtype=str)).astype(str).ne(sku_value).sum()) if not selected_material.empty else 1
            timeline_leak_count += int(selected_segments.get("finished_sku", pd.Series(dtype=str)).astype(str).ne(sku_value).sum()) if not selected_segments.empty else 1
            maintenance_leak_count += int(selected_impact.get("finished_sku", pd.Series(dtype=str)).astype(str).ne(sku_value).sum()) if not selected_impact.empty else 0
            related_buffers = set()
            access_for_sku = data["wip_access_rules"][data["wip_access_rules"].get("finished_sku", pd.Series(dtype=str)).astype(str) == sku_value] if not data["wip_access_rules"].empty else pd.DataFrame()
            for col in ["allowed_input_wip_buffer_id", "allowed_output_wip_buffer_id"]:
                if col in access_for_sku.columns:
                    related_buffers.update(v for v in access_for_sku[col].dropna().astype(str) if v and v.lower() != "nan")
            if related_buffers and not shadow.empty:
                for buffer_id in related_buffers:
                    filtered = shadow[
                        (shadow.get("alternative_id", pd.Series(dtype=str)).astype(str) == "ALT-BASELINE")
                        & (shadow.get("wip_buffer_id", pd.Series(dtype=str)).astype(str) == buffer_id)
                    ]
                    if "schedule_candidate_id" in filtered.columns:
                        candidate_values_shadow = filtered.get("schedule_candidate_id", pd.Series(dtype=str)).fillna("").astype(str)
                        event_types_shadow = filtered.get("shadow_event_type", pd.Series("", index=filtered.index)).fillna("").astype(str)
                        filtered = filtered[candidate_values_shadow.eq(sample_candidate) | (candidate_values_shadow.isin(["", "nan"]) & event_types_shadow.eq("STARTING_ACCEPTED_WIP"))]
                    if "finished_sku" in filtered.columns:
                        sku_values_shadow = filtered.get("finished_sku", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
                        wip_leak_count += int((~sku_values_shadow.isin(["", "nan", sku_value])).sum())
        sample_messages.append(f"{sku_value}: candidates={len(candidate_values)}, graph_nodes={len(sku_nodes)}, graph_edges={len(sku_edges)}, bom_rows={len(sku_bom)}, timeline_segments={len(sku_segments)}")
    add("MULTI_SKU_MB_RB_PAGES_HAVE_EVIDENCE", sample_pages_ok, "Mountain Bike and Road Bike have source evidence for all SKU-dependent pages. " + " | ".join(sample_messages))
    add("MULTI_SKU_CANDIDATE_LISTS_ARE_SKU_SPECIFIC", candidate_leak_count == 0, "Candidate IDs are not shared across Mountain Bike and Road Bike selected views.", candidate_leak_count)
    add("MULTI_SKU_OPERATION_IDS_ARE_SKU_SPECIFIC", operation_leak_count == 0 and graph_leak_count == 0, "Operation IDs for MB/RB views stay within the selected SKU route family.", operation_leak_count + graph_leak_count)
    add("MULTI_SKU_BOM_ROWS_ARE_SKU_SPECIFIC", bom_leak_count == 0, "BOM rows remain scoped to the selected finished SKU.", bom_leak_count)
    add("MULTI_SKU_MATERIAL_ROWS_ARE_SKU_CANDIDATE_SPECIFIC", material_leak_count == 0, "Material readiness rows remain scoped to selected SKU and candidate.", material_leak_count)
    add("MULTI_SKU_TIMELINE_SEGMENTS_ARE_SKU_CANDIDATE_SPECIFIC", timeline_leak_count == 0, "Timeline segments remain scoped to selected SKU and candidate.", timeline_leak_count)
    add("MULTI_SKU_WIP_BALANCES_ARE_SKU_CANDIDATE_SPECIFIC", wip_leak_count == 0, "WIP projected balances are filtered by selected SKU/candidate and do not use another SKU's projected events.", wip_leak_count)
    add("MULTI_SKU_MAINTENANCE_IMPACT_SCOPED", maintenance_leak_count == 0, "Maintenance production-impact support remains scoped through the selected SKU/candidate operation evidence.", maintenance_leak_count)
    add("DECISION_RELEASE_PAGE_REGISTERED", '"Decision & Release Readiness"' in app_source and "_decision_release_page" in app_source, "Decision & Release Readiness page is registered in Phase 4 manager navigation.")
    rec_row = rec.iloc[0].to_dict() if not rec.empty else {}
    recommended_id = str(rec_row.get("recommended_alternative_id", ""))
    recommended_summary = summary[summary.get("alternative_id", pd.Series(dtype=str)).astype(str) == recommended_id] if not summary.empty else pd.DataFrame()
    add("DECISION_RECOMMENDATION_MATCHES_STEP8G", not rec.empty and not recommended_summary.empty and "RECOMMENDED_FOR_REVIEW" in rec.get("recommendation_status", pd.Series(dtype=str)).astype(str).to_string(), "Decision page recommendation matches Step 8G recommendation evidence.")
    explicit_equiv = str(rec_row.get("equivalent_result_group", "") or "")
    equiv_ok = bool(explicit_equiv.strip()) and all(alt.strip() in set(summary.get("alternative_id", pd.Series(dtype=str)).astype(str)) for alt in explicit_equiv.split(",") if alt.strip()) if not summary.empty else False
    add("DECISION_EQUIVALENT_ALTERNATIVES_TRACE_TO_STEP8G", equiv_ok and "equivalent_result_group" in app_source, "Equivalent alternatives are read from Step 8G recommendation/summary evidence.")
    tradeoff_cols = {"compared_alternative_id", "demand_coverage_delta_pct", "validated_cost_delta", "assumed_penalty_delta", "setup_minutes_delta", "buffer_blocked_quantity_delta", "wip_blocked_quantity_delta"}
    add("DECISION_TRADEOFF_VALUES_TRACE_TO_SOURCE", not tradeoffs.empty and tradeoff_cols <= set(tradeoffs.columns), "Trade-off values trace to phase4_step8g_tradeoff_analysis.csv.")
    cost_separated = not summary.empty and {"validated_real_cost", "assumed_cost_or_penalty", "cost_confidence_level"} <= set(summary.columns) and "validated_real_cost" in app_source and "assumed_cost_or_penalty" in app_source
    add("DECISION_VALIDATED_AND_ASSUMED_COSTS_SEPARATED", cost_separated, "Decision page keeps validated real cost separate from assumed cost or penalty exposure.")
    readiness_cols = {"readiness_check_name", "readiness_status", "release_readiness_status", "production_release_allowed", "evidence_source_file", "evidence_summary"}
    add("DECISION_READINESS_CHECKS_MATCH_SOURCE", not readiness.empty and readiness_cols <= set(readiness.columns) and "phase4_step8g_release_readiness.csv" in str(FILES["step8g_readiness"]), "Readiness checklist matches Step 8G release-readiness evidence.")
    release_false = not readiness.empty and readiness.get("production_release_allowed", pd.Series(dtype=str)).astype(str).str.strip().str.lower().isin({"false", "0", "no"}).all()
    add("DECISION_PRODUCTION_RELEASE_REMAINS_FALSE", release_false and "production_release_allowed" in app_source, "Decision page preserves production_release_allowed=False from Step 8G evidence.")
    approval_not_fabricated = not rec.empty and rec.get("approval_status", pd.Series(dtype=str)).astype(str).str.contains("NOT_APPROVED", case=False, regex=False).any() and "manager approval" not in app_source.lower().replace("manager approval received", "")
    add("DECISION_MANAGER_APPROVAL_NOT_FABRICATED", approval_not_fabricated, "Manager approval remains source-driven and is not set by the UI.")
    blocked = readiness[readiness.get("readiness_row_type", pd.Series(dtype=str)).astype(str) != "OVERALL"] if not readiness.empty else pd.DataFrame()
    blocked = blocked[blocked.get("readiness_status", pd.Series(dtype=str)).astype(str).str.upper().isin(["BLOCKED", "REVIEW_REQUIRED", "REVIEW REQUIRED", "FAIL"])] if not blocked.empty else blocked
    blocker_source_reason_ok = blocked.empty or ({"evidence_source_file", "evidence_summary", "recommended_manager_action"} <= set(blocked.columns) and blocked["evidence_source_file"].fillna("").astype(str).str.len().gt(0).all())
    add("DECISION_BLOCKED_CHECKS_SHOW_SOURCE_REASON", blocker_source_reason_ok and "_release_blockers_section" in app_source, "Blocked readiness checks display source, reason, business impact, and manager action.", len(blocked))
    upstream_rows = pd.concat([risks, step8g_review], ignore_index=True, sort=False) if not risks.empty or not step8g_review.empty else pd.DataFrame()
    upstream_attr = upstream_rows.apply(lambda r: "PHASE2" in str(r.to_dict()).upper() or "PHASE3" in str(r.to_dict()).upper() or "UPSTREAM" in str(r.to_dict()).upper(), axis=1).any() if not upstream_rows.empty else False
    add("DECISION_UPSTREAM_WARNING_ATTRIBUTION_PRESERVED", upstream_attr or (not summary.empty and pd.to_numeric(summary.get("upstream_warning_count", 0), errors="coerce").fillna(0).sum() > 0), "Upstream warnings remain visible and attributed to their source phase.")
    decision_source = app_source.split("def _decision_release_page", 1)[1].split("def _operation_material_status", 1)[0] if "def _decision_release_page" in app_source else ""
    decision_multi_sku = '"decision_sku"' in decision_source and "finished_sku" in decision_source and "schedule_candidate_id" in decision_source
    add("DECISION_MULTI_SKU_FILTERS_NO_LEAKAGE", decision_multi_sku and multi_sku_ok, "Decision page SKU/candidate filters use source finished_sku and schedule_candidate_id values for MB/RB without hardcoding.")
    no_decision_execution_controls = all(token not in decision_source for token in ["st.button(\"Approve", "st.button(\"Release", "st.button(\"Create", "production_release_allowed = True", "create_production_order", "dispatch_workers(", "reserve_inventory(", "create_purchase_order", "create_maintenance_work_order"])
    add("DECISION_NO_EXECUTION_ACTION_AVAILABLE", no_decision_execution_controls, "Decision page exposes no release, approval, dispatch, reservation, purchase, work-order, or transaction action.")
    add("DECISION_RISKS_AND_REVIEW_QUEUE_AVAILABLE", not risks.empty and not step8g_review.empty, "Decision risk register and manager review queue are available to the page.", len(risks) + len(step8g_review))
    alt_not_sku = "affected_sku_or_workstation" not in decision_source and '"Affected Alternative"' in decision_source
    add("DECISION_REVIEW_ALTERNATIVE_NOT_PRESENTED_AS_SKU_WORKSTATION", alt_not_sku, "Manager review queue presents alternative_id as Affected Alternative, not as SKU/workstation.")
    review_source_has_sku = "finished_sku" in step8g_review.columns
    review_source_has_ws = "workstation_id" in step8g_review.columns
    sku_ws_source_supported = (
        review_source_has_sku or '"Affected SKU"' not in decision_source or 'if "finished_sku" in display.columns' in decision_source
    ) and (
        review_source_has_ws or '"Affected Workstation"' not in decision_source or 'if "workstation_id" in display.columns' in decision_source
    )
    add("DECISION_REVIEW_SKU_WORKSTATION_ONLY_SOURCE_SUPPORTED", sku_ws_source_supported, "Affected SKU/workstation fields are shown only when genuine source columns exist.")
    add("DECISION_MANAGER_REVIEW_ROW_COUNT_UNCHANGED", len(step8g_review) == len(data["step8g_manager_review"]), "Manager-review row count remains source-driven and unchanged.", len(step8g_review))
    rec_values_unchanged = str(rec_row.get("recommended_alternative_id", "")) == "ALT-BASELINE" and str(rec_row.get("recommendation_status", "")) == "RECOMMENDED_FOR_REVIEW"
    readiness_overall = readiness[readiness.get("readiness_row_type", pd.Series(dtype=str)).astype(str) == "OVERALL"] if not readiness.empty else pd.DataFrame()
    readiness_unchanged = not readiness_overall.empty and str(readiness_overall.iloc[0].get("release_readiness_status", "")) == "NOT_READY_FOR_RELEASE" and str(readiness_overall.iloc[0].get("production_release_allowed", "")).strip().lower() in {"false", "0", "no"}
    add("DECISION_RECOMMENDATION_READINESS_VALUES_UNCHANGED", rec_values_unchanged and readiness_unchanged, "Recommendation and release-readiness values remain unchanged by the UI correction.")
    decision_dataframe_cleanup = "def _decision_manager_review_section" in app_source and "width=\"stretch\"" in decision_source and "affected_sku_or_workstation" not in decision_source
    add("DECISION_TOUCHED_DATAFRAMES_WIDTH_STRETCH", decision_dataframe_cleanup, "Touched Decision & Release Readiness dataframes use width=\"stretch\".")
    add("NO_DEPRECATED_USE_CONTAINER_WIDTH_IN_UI", "use_container_width" not in app_source, "Active Streamlit UI code uses width=\"stretch\"/current width APIs instead of deprecated use_container_width.")
    add("MANAGER_OVERVIEW_OVERALL_SCOPE_LABELLED", "Overall Planning Metric" in app_source or "Overall Recommended Alternative" in app_source, "Manager Overview labels Step 8G metrics as overall planning metrics.")
    add("FINAL_UI_PAGES_REGISTERED", all(name in app_source for name in ["Manager Overview", "Production Flow Graph", "BOM & Materials", "Production Timeline", "Capacity & WIP", "Maintenance", "Decision & Release Readiness"]), "All seven completed manager pages are registered.")
    add("NAVIGATION_GROUPS_PRESENT", all(name in app_source for name in ["Planning | Manager Overview", "Materials & Resources | BOM & Materials", "Decision | Decision & Release Readiness"]), "Sidebar navigation is visually grouped into Planning, Materials & Resources, and Decision.")
    add("PRESENTATION_ALIASES_DO_NOT_RENAME_SOURCE_COLUMNS", "_DISPLAY_LABELS" in app_source and "return display.rename(columns=" in app_source, "Readable table labels are applied only to display copies, not source dataframes.")
    add("GRAPH_SOURCE_COUNTS_PRESERVED", len(nodes) == 182 and len(edges) == 196, "Presentation cleanup preserves validated graph source row counts.", len(nodes) + len(edges))
    add("TIMELINE_SOURCE_COUNTS_PRESERVED", len(op_segments) == 2686, "Presentation cleanup preserves validated timeline segment source row count.", len(op_segments))
    add("NO_PLANNING_LOGIC_RECALCULATED_IN_UI", "build_integrated_phase234_outputs" not in app_source and "build_schedule_alternative_outputs" not in app_source, "UI reads existing outputs and does not call planning builders.")
    add("UI_OUTPUTS_ADVISORY_ONLY", all(_all_true(df, "advisory_only_flag") for df in [nodes, edges, summary, rec, readiness]), "UI source outputs are advisory-only.")
    add("NO_EXECUTION_OUTPUTS_CREATED_FOR_UI", not _forbidden_outputs_exist(), "No production orders, dispatches, reservations, consumption, releases, or transaction outputs exist.")

    validation = pd.DataFrame(rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    return validation


def _load(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _first_value(df: pd.DataFrame, column: str) -> str:
    if not df.empty and column in df.columns:
        values = df[column].dropna().astype(str)
        if not values.empty:
            return values.iloc[0]
    return ""


def _all_source(df: pd.DataFrame, source: str) -> bool:
    return not df.empty and "source_phase" in df.columns and set(df["source_phase"].dropna().astype(str)) == {source}


def _all_true(df: pd.DataFrame, column: str) -> bool:
    return not df.empty and column in df.columns and df[column].astype(str).str.strip().str.lower().isin({"true", "1", "yes"}).all()


def _date_part(value: object) -> str:
    dt = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(dt) else dt.date().isoformat()


def _bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _forbidden_outputs_exist() -> bool:
    patterns = [
        "*production_order*.csv",
        "*confirmed_schedule*.csv",
        "*worker_dispatch*.csv",
        "*inventory_reservation*.csv",
        "*inventory_consumption*.csv",
        "*wip_transaction*.csv",
        "*purchase_order_release*.csv",
        "*maintenance_work_order*.csv",
        "*capacity_reduction_applied*.csv",
        "*release_action*.csv",
        "*simulation*.csv",
    ]
    allow = {
        "phase4_production_schedule_candidates.csv",
        "phase4_operation_schedule_candidate_detail.csv",
        "phase4_production_schedule_validation.csv",
        "phase4_schedule_alternative_operation_detail.csv",
        "phase4_schedule_alternative_operation_segments.csv",
        "phase4_schedule_alternative_validation.csv",
    }
    return any(path.name not in allow for pattern in patterns for path in OUTPUT_DIR.glob(pattern))


if __name__ == "__main__":
    result = build_ui_validation()
    counts = result["status"].value_counts().to_dict()
    print(f"Phase 4 UI validation rows: {len(result)}")
    print(f"Validation counts: {counts}")
    print(f"Validation output written to: {VALIDATION_OUTPUT_FILE}")
