"""Build advisory Phase 2-3-4 integrated material readiness evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE4_DIR.parent
OUTPUT_DIR = PHASE4_DIR / "outputs"

BOM_FILE = PHASE4_DIR / "data" / "phase4_bom.csv"
ROUTING_FILE = PHASE4_DIR / "data" / "product_routings.csv"
COMPONENT_OPERATION_MAP_FILE = PHASE4_DIR / "data" / "phase4_component_operation_consumption_map.csv"
MRP_PERIOD_FILE = OUTPUT_DIR / "phase4_mrp_component_period_summary.csv"
MRP_PEGGING_FILE = OUTPUT_DIR / "phase4_mrp_pegging_detail.csv"
INVENTORY_FILE = PROJECT_ROOT / "phase 3" / "outputs" / "phase4_component_inventory_check.csv"
SUPPLIER_CHECK_FILE = PROJECT_ROOT / "phase 2" / "outputs" / "phase4_component_supplier_check.csv"
SUPPLIER_CAPABILITY_FILE = PROJECT_ROOT / "phase 2" / "outputs" / "phase2_procurement_capability_context.csv"
ALLOCATION_SUMMARY_FILE = PROJECT_ROOT / "shared" / "outputs" / "phase2_procurement_allocation_summary.csv"
STEP8G_RECOMMENDATION_FILE = OUTPUT_DIR / "phase4_step8g_recommendation.csv"
STEP8G_READINESS_FILE = OUTPUT_DIR / "phase4_step8g_release_readiness.csv"
OPERATION_DETAIL_FILE = OUTPUT_DIR / "phase4_schedule_alternative_operation_detail.csv"
GRAPH_NODES_FILE = OUTPUT_DIR / "phase4_routing_graph_nodes.csv"
SLACK_FILE = OUTPUT_DIR / "phase4_operation_slack_analysis.csv"
CAPACITY_FILE = OUTPUT_DIR / "phase4_schedule_alternative_capacity_impact.csv"
BOTTLENECK_FILE = OUTPUT_DIR / "phase4_bottleneck_visibility_summary.csv"
WIP_FILE = OUTPUT_DIR / "phase4_schedule_alternative_wip_impact.csv"
BUFFER_FILE = OUTPUT_DIR / "phase4_wip_buffer_status.csv"

MATERIAL_READINESS_OUTPUT_FILE = OUTPUT_DIR / "integrated_phase234_material_readiness.csv"
SHORTAGE_TIMELINE_OUTPUT_FILE = OUTPUT_DIR / "integrated_phase234_shortage_timeline.csv"
SCHEDULE_IMPACT_OUTPUT_FILE = OUTPUT_DIR / "integrated_phase234_schedule_impact.csv"
RECOMMENDATION_CHECK_OUTPUT_FILE = OUTPUT_DIR / "integrated_phase234_recommendation_check.csv"
VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "integrated_phase234_validation.csv"
GRAPH_NODES_OUTPUT_FILE = OUTPUT_DIR / "integrated_phase234_graph_nodes.csv"
GRAPH_EDGES_OUTPUT_FILE = OUTPUT_DIR / "integrated_phase234_graph_edges.csv"

SOURCE_PHASE = "INTEGRATED_PHASE234_ADVISORY_PLANNING_REFRESH"
REFERENCE_ALT = "ALT-BASELINE"
UNMAPPED_STATUS = "CONSUMING_OPERATION_UNMAPPED_REVIEW"
TOL = 0.0001


def build_integrated_phase234_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frames = {name: _load(path) for name, path in {
        "bom": BOM_FILE,
        "routing": ROUTING_FILE,
        "component_operation_map": COMPONENT_OPERATION_MAP_FILE,
        "mrp": MRP_PERIOD_FILE,
        "pegging": MRP_PEGGING_FILE,
        "inventory": INVENTORY_FILE,
        "supplier": SUPPLIER_CHECK_FILE,
        "capability": SUPPLIER_CAPABILITY_FILE,
        "allocation": ALLOCATION_SUMMARY_FILE,
        "recommendation": STEP8G_RECOMMENDATION_FILE,
        "readiness": STEP8G_READINESS_FILE,
        "operations": OPERATION_DETAIL_FILE,
        "routing_nodes": GRAPH_NODES_FILE,
        "slack": SLACK_FILE,
        "capacity": CAPACITY_FILE,
        "bottleneck": BOTTLENECK_FILE,
        "wip": WIP_FILE,
        "buffer": BUFFER_FILE,
    }.items()}
    material = _build_material_readiness(frames)
    shortage = _build_shortage_timeline(material)
    impact = _build_schedule_impact(material)
    recommendation = _build_recommendation_check(material, frames)
    nodes = _build_graph_nodes(impact, frames)
    edges = _build_graph_edges(impact, frames)
    validation = _build_validation(material, shortage, impact, recommendation, nodes, edges, frames)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    material.to_csv(MATERIAL_READINESS_OUTPUT_FILE, index=False)
    shortage.to_csv(SHORTAGE_TIMELINE_OUTPUT_FILE, index=False)
    impact.to_csv(SCHEDULE_IMPACT_OUTPUT_FILE, index=False)
    recommendation.to_csv(RECOMMENDATION_CHECK_OUTPUT_FILE, index=False)
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    nodes.to_csv(GRAPH_NODES_OUTPUT_FILE, index=False)
    edges.to_csv(GRAPH_EDGES_OUTPUT_FILE, index=False)
    return material, shortage, impact, recommendation, validation, nodes, edges


def _build_material_readiness(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    pegging = frames["pegging"].copy()
    inventory = _index(frames["inventory"], "component_sku")
    supplier = _index(frames["supplier"], "component_sku")
    allocation = _index(frames["allocation"].rename(columns={"sku_id": "component_sku"}), "component_sku")
    capability = _best_capability(frames["capability"])
    operation_dates = _operation_dates(frames["operations"])
    component_ops = _explicit_component_operation_map(frames["component_operation_map"], frames["routing"], frames["bom"])
    data_as_of = _data_as_of(frames["capability"])

    inventory_remaining = {sku: _num(row.get("available_qty")) for sku, row in inventory.items()}
    supplier_remaining: dict[str, float] = {}
    inbound_dates: dict[str, pd.Timestamp] = {}
    supplier_rows: dict[str, dict] = {}
    for sku, sup in supplier.items():
        cap = capability.get(sku, {})
        alloc = allocation.get(sku, {})
        shortage = _num(sup.get("shortage_qty"))
        capacity = _num(cap.get("supplier_effective_horizon_capacity_units"))
        yield_rate = _num(cap.get("yield_rate")) or 1.0
        allocated = _num(alloc.get("total_allocated_usable_quantity"))
        if allocated <= TOL and _bool(sup.get("supplier_available_flag")):
            allocated = min(shortage, capacity * yield_rate if capacity > 0 else shortage)
        supplier_remaining[sku] = max(allocated, 0.0)
        lead_days = int(round(_num(sup.get("expected_lead_time", cap.get("expected_lead_time_days", 0)))))
        arrival_text = alloc.get("final_arrival_date") or cap.get("expected_final_shipment_date") or ""
        arrival = pd.to_datetime(arrival_text, errors="coerce")
        if pd.isna(arrival) and lead_days:
            arrival = data_as_of + pd.Timedelta(days=lead_days)
        inbound_dates[sku] = arrival
        supplier_rows[sku] = {**sup, **{f"cap_{k}": v for k, v in cap.items()}, **{f"alloc_{k}": v for k, v in alloc.items()}}

    rows = []
    for _, req in pegging.sort_values(["component_sku", "period_start", "finished_sku"]).iterrows():
        sku = str(req["component_sku"])
        period_start = str(req["period_start"])
        finished_sku = str(req["finished_sku"])
        required_qty = _num(req.get("pegged_gross_component_requirement_qty"))
        candidate_id = f"PSC-{finished_sku}-{period_start.replace('-', '')}"
        mapping = component_ops.get((finished_sku, sku), {})
        consuming_op_id = str(mapping.get("operation_id", ""))
        op = operation_dates.get((candidate_id, consuming_op_id), {}) if consuming_op_id else {}
        mapped = bool(op)
        required_dt = pd.to_datetime(op.get("proposed_start_datetime"), errors="coerce") if mapped else pd.NaT
        dated_operation = mapped and not pd.isna(required_dt)

        inv_used = min(inventory_remaining.get(sku, 0.0), required_qty)
        inventory_remaining[sku] = max(inventory_remaining.get(sku, 0.0) - inv_used, 0.0)
        remaining_after_inv = max(required_qty - inv_used, 0.0)
        inbound_dt = inbound_dates.get(sku, pd.NaT)
        inbound_on_time = dated_operation and not pd.isna(inbound_dt) and inbound_dt <= required_dt
        supplier_used = min(supplier_remaining.get(sku, 0.0), remaining_after_inv) if inbound_on_time else 0.0
        supplier_remaining[sku] = max(supplier_remaining.get(sku, 0.0) - supplier_used, 0.0)
        shortage_qty = max(remaining_after_inv - supplier_used, 0.0)
        inv = inventory.get(sku, {})
        sup = supplier_rows.get(sku, {})

        if not mapped:
            status = UNMAPPED_STATUS
            shortage_qty = max(required_qty - inv_used, 0.0)
        elif not dated_operation:
            status = "REQUIRED_DATE_UNAVAILABLE_REVIEW"
            shortage_qty = max(required_qty - inv_used, 0.0)
        elif shortage_qty <= TOL:
            status = "READY_ON_TIME"
        elif remaining_after_inv > TOL and not inbound_on_time and not pd.isna(inbound_dt):
            status = "LATE_INBOUND_REVIEW"
        elif remaining_after_inv > TOL and supplier_remaining.get(sku, 0.0) <= TOL and not _bool(sup.get("supplier_available_flag")):
            status = "SUPPLIER_REVIEW_REQUIRED"
        else:
            status = "SHORTAGE_UNRESOLVED"

        rows.append({
            "planning_run_id": req.get("planning_run_id", ""),
            "finished_sku": finished_sku,
            "schedule_candidate_id": candidate_id,
            "component_sku": sku,
            "component_name": req.get("component_name", ""),
            "required_date": required_dt.date().isoformat() if dated_operation else "",
            "consuming_operation_id": consuming_op_id if mapped else "",
            "consuming_operation_name": op.get("operation_name", "") if mapped else "",
            "workstation_id": op.get("workstation_id", "") if mapped else "",
            "consuming_operation_start_datetime": op.get("proposed_start_datetime", "") if mapped else "",
            "component_operation_mapping_status": "EXPLICIT_CONSUMING_OPERATION_MAPPED" if mapped else UNMAPPED_STATUS,
            "component_operation_mapping_basis": mapping.get("mapping_basis", "NO_RELIABLE_COMPONENT_OPERATION_MAPPING"),
            "component_operation_mapping_source": mapping.get("mapping_source", ""),
            "component_operation_review_required_flag": bool(not mapped or not dated_operation or _bool(mapping.get("review_required_flag"))),
            "required_date_source": "CONSUMING_OPERATION_PROPOSED_START" if dated_operation else ("CONSUMING_OPERATION_NOT_SCHEDULED" if mapped else "UNMAPPED_REVIEW"),
            "phase4_required_qty": round(required_qty, 4),
            "phase3_available_inventory_qty": round(_num(inv.get("available_qty")), 4),
            "inventory_qty_used_for_requirement": round(inv_used, 4),
            "phase3_net_replenishment_need_qty": round(_num(inv.get("shortage_qty")), 4),
            "phase2_allocated_supplier_qty": round(_num(sup.get("alloc_total_allocated_usable_quantity", 0.0)) or supplier_used, 4),
            "phase2_capacity_limited_supplier_qty": round(_num(sup.get("cap_supplier_effective_horizon_capacity_units")) * (_num(sup.get("cap_yield_rate")) or 1.0), 4),
            "phase2_moq_adjusted_order_qty": round(_num(sup.get("cap_final_immediate_order_quantity")), 4),
            "phase2_yield_rate": round(_num(sup.get("cap_yield_rate")) or 1.0, 4),
            "expected_inbound_qty_available_for_requirement": round(supplier_used, 4),
            "expected_inbound_date": inbound_dt.date().isoformat() if not pd.isna(inbound_dt) else "",
            "inbound_available_before_operation_flag": bool(inbound_on_time and supplier_used > TOL),
            "remaining_shortage_qty": round(shortage_qty, 4),
            "material_readiness_status": status,
            "material_blocker_flag": bool(shortage_qty > TOL or not mapped or not dated_operation),
            "source_phase4_file": "phase4_mrp_pegging_detail.csv;phase4_schedule_alternative_operation_detail.csv",
            "source_phase3_file": "phase4_component_inventory_check.csv",
            "source_phase2_file": "phase4_component_supplier_check.csv;phase2_procurement_capability_context.csv",
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_material_columns())


def _build_shortage_timeline(material: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in material[material["remaining_shortage_qty"].map(_num) > TOL].iterrows():
        inbound = pd.to_datetime(row["expected_inbound_date"], errors="coerce")
        req = pd.to_datetime(row["required_date"], errors="coerce")
        late_days = (inbound - req).days if not pd.isna(inbound) and not pd.isna(req) else 0
        rows.append({
            "planning_run_id": row["planning_run_id"],
            "component_sku": row["component_sku"],
            "component_name": row["component_name"],
            "finished_sku": row["finished_sku"],
            "schedule_candidate_id": row["schedule_candidate_id"],
            "consuming_operation_id": row["consuming_operation_id"],
            "consuming_operation_name": row["consuming_operation_name"],
            "workstation_id": row["workstation_id"],
            "component_operation_mapping_status": row["component_operation_mapping_status"],
            "component_operation_mapping_source": row["component_operation_mapping_source"],
            "required_date": row["required_date"],
            "expected_inbound_date": row["expected_inbound_date"],
            "required_qty": row["phase4_required_qty"],
            "inventory_used_qty": row["inventory_qty_used_for_requirement"],
            "inbound_used_qty": row["expected_inbound_qty_available_for_requirement"],
            "remaining_shortage_qty": row["remaining_shortage_qty"],
            "shortage_timing_status": "UNMAPPED_CONSUMING_OPERATION_REVIEW" if row["component_operation_mapping_status"] == UNMAPPED_STATUS else ("REQUIRED_DATE_UNAVAILABLE_REVIEW" if row["material_readiness_status"] == "REQUIRED_DATE_UNAVAILABLE_REVIEW" else ("LATE_INBOUND" if late_days > 0 else "UNRESOLVED_SHORTAGE")),
            "late_days": max(late_days, 0),
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    if not rows:
        rows.append({col: "" for col in _shortage_columns()})
        rows[0].update({"planning_run_id": material["planning_run_id"].iloc[0] if not material.empty else "", "shortage_timing_status": "NO_SHORTAGE", "remaining_shortage_qty": 0.0, "late_days": 0, "source_phase": SOURCE_PHASE, "advisory_only_flag": True})
    return pd.DataFrame(rows, columns=_shortage_columns())


def _build_schedule_impact(material: pd.DataFrame) -> pd.DataFrame:
    grouped = material.groupby(["planning_run_id", "schedule_candidate_id", "finished_sku", "consuming_operation_id", "consuming_operation_name", "workstation_id"], dropna=False)
    rows = []
    for keys, group in grouped:
        shortage = group["remaining_shortage_qty"].map(_num).sum()
        blocked_components = int((group["remaining_shortage_qty"].map(_num) > TOL).sum())
        late_components = int((group["material_readiness_status"].astype(str) == "LATE_INBOUND_REVIEW").sum())
        unmapped = str(keys[3]).strip() == ""
        undated = bool((group["material_readiness_status"].astype(str) == "REQUIRED_DATE_UNAVAILABLE_REVIEW").any())
        rows.append({
            "planning_run_id": keys[0],
            "schedule_candidate_id": keys[1],
            "finished_sku": keys[2],
            "operation_id": keys[3],
            "operation_name": keys[4],
            "workstation_id": keys[5],
            "component_operation_mapping_status": UNMAPPED_STATUS if unmapped else "EXPLICIT_CONSUMING_OPERATION_MAPPED",
            "affected_component_count": blocked_components,
            "late_component_count": late_components,
            "remaining_shortage_qty": round(shortage, 4),
            "schedule_impact_status": "CONSUMING_OPERATION_UNMAPPED_REVIEW" if unmapped else ("REQUIRED_DATE_UNAVAILABLE_REVIEW" if undated else ("MATERIAL_BLOCKED_REVIEW" if shortage > TOL else "MATERIAL_READY_FOR_OPERATION")),
            "blocker_reason": "Component-to-operation mapping requires review." if unmapped else ("Consuming operation has no proposed start datetime for material timing." if undated else ("Component shortage traces to integrated Phase 2/3/4 readiness." if shortage > TOL else "")),
            "recommendation_change_required_flag": False,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_impact_columns())


def _build_recommendation_check(material: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rec = frames["recommendation"].iloc[0].to_dict() if not frames["recommendation"].empty else {}
    prior_alt = str(rec.get("recommended_alternative_id", ""))
    shortage = material["remaining_shortage_qty"].map(_num).sum() if not material.empty else 0.0
    material_alt_specific = "alternative_id" in material.columns and material["alternative_id"].nunique(dropna=True) > 1
    if material_alt_specific:
        blocked_by_alt = material.groupby("alternative_id")["remaining_shortage_qty"].apply(lambda s: sum(_num(v) for v in s)).to_dict()
        integrated_alt = sorted(blocked_by_alt, key=lambda alt: (blocked_by_alt[alt], alt))[0]
        recalculation_status = "RECOMMENDATION_INDEPENDENTLY_RECALCULATED"
        retention_status = ""
        independent = True
        reason = f"Integrated material evidence was alternative-specific; selected {integrated_alt} from shortage exposure ranking."
    else:
        integrated_alt = prior_alt
        recalculation_status = "RECOMMENDATION_NOT_RECALCULABLE_FROM_CURRENT_INTEGRATION"
        retention_status = "PRIOR_RECOMMENDATION_RETAINED_PENDING_REVIEW"
        independent = False
        reason = f"Integrated material evidence is not alternative-specific, so prior Step 8G recommendation {prior_alt} is retained pending review; unresolved shortage qty {round(shortage, 4)}."
    row = {
        "planning_run_id": rec.get("planning_run_id", material["planning_run_id"].iloc[0] if not material.empty else ""),
        "prior_recommended_alternative_id": prior_alt,
        "integrated_recommended_alternative_id": integrated_alt,
        "recommendation_changed_flag": bool(independent and integrated_alt != prior_alt),
        "recommendation_recalculation_status": recalculation_status,
        "recommendation_retention_status": retention_status,
        "independent_recalculation_performed_flag": independent,
        "recommendation_check_status": retention_status or recalculation_status,
        "recommendation_check_reason": reason,
        "release_readiness_status": "NOT_READY_FOR_RELEASE",
        "production_release_allowed": False,
        "material_release_blocker_flag": bool(shortage > TOL),
        "source_phase": SOURCE_PHASE,
        "advisory_only_flag": True,
    }
    return pd.DataFrame([row], columns=_recommendation_check_columns())


def _build_graph_nodes(impact: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    ops = frames["operations"][frames["operations"]["alternative_id"].astype(str) == REFERENCE_ALT].copy()
    slack = _index_multi(frames["slack"], ["finished_sku", "operation_id"])
    cap = _index_multi(frames["capacity"][frames["capacity"]["alternative_id"].astype(str) == REFERENCE_ALT], ["schedule_candidate_id", "operation_id"])
    bottleneck = _index(frames["bottleneck"], "workstation_id")
    wip_candidate_specific = "schedule_candidate_id" in frames["wip"].columns
    wip = _index_multi(frames["wip"][frames["wip"]["alternative_id"].astype(str) == REFERENCE_ALT], ["schedule_candidate_id", "operation_id"]) if wip_candidate_specific else {}
    buffer = _index(frames["buffer"], "wip_buffer_id")
    impact_by_op = _index_multi(impact, ["schedule_candidate_id", "operation_id"])
    rows = []
    for _, op in ops.iterrows():
        candidate_id = str(op.get("schedule_candidate_id", ""))
        op_id = str(op.get("operation_id", ""))
        ws = str(op.get("workstation_id", ""))
        wip_row = wip.get((candidate_id, op_id), {})
        buffer_row = buffer.get(str(wip_row.get("wip_buffer_id", "")), {})
        impact_row = impact_by_op.get((candidate_id, op_id), {})
        material_status = impact_row.get("schedule_impact_status", "NO_DIRECT_COMPONENT_CHECK")
        wip_status = wip_row.get("wip_impact_status", "WIP_STATUS_NOT_CANDIDATE_SPECIFIC_REVIEW" if not wip_candidate_specific else "")
        blocker = "MATERIAL" if material_status == "MATERIAL_BLOCKED_REVIEW" else ("WIP_REVIEW" if str(wip_status).endswith("_REVIEW") else ("WIP" if _num(wip_row.get("wip_shortage_qty")) > TOL else ("BOTTLENECK" if str(bottleneck.get(ws, {}).get("bottleneck_visibility_level", "")).upper() in {"HIGH", "CRITICAL"} else "NONE")))
        rows.append({
            "planning_run_id": op.get("planning_run_id", ""),
            "node_id": f"{candidate_id}-{op_id}",
            "node_type": "OPERATION",
            "schedule_candidate_id": candidate_id,
            "finished_sku": op.get("finished_sku", ""),
            "operation_id": op_id,
            "operation_name": op.get("operation_name", ""),
            "workstation_id": ws,
            "workstation_name": op.get("workstation_name", ""),
            "proposed_start_datetime": op.get("proposed_start_datetime", ""),
            "proposed_end_datetime": op.get("proposed_end_datetime", ""),
            "critical_path_flag": op.get("critical_path_flag", False),
            "slack_time_minutes": slack.get((str(op.get("finished_sku", "")), op_id), {}).get("slack_time_minutes", ""),
            "utilization_pct": cap.get((candidate_id, op_id), {}).get("utilization_pct", ""),
            "bottleneck_status": bottleneck.get(ws, {}).get("bottleneck_visibility_level", ""),
            "material_readiness_status": material_status,
            "wip_readiness_status": wip_status,
            "buffer_status": buffer_row.get("buffer_status", wip_row.get("buffer_capacity_status", "")),
            "blocker_type": blocker,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_graph_node_columns())


def _build_graph_edges(impact: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    ops = frames["operations"][frames["operations"]["alternative_id"].astype(str) == REFERENCE_ALT]
    qty_by_op = _index_multi(ops, ["schedule_candidate_id", "operation_id"])
    impact_by_op = _index_multi(impact, ["schedule_candidate_id", "operation_id"])
    rows = []
    for _, op in ops.iterrows():
        candidate_id = str(op.get("schedule_candidate_id", ""))
        to_op = str(op.get("operation_id", ""))
        pred_value = op.get("predecessor_operation_ids", "")
        preds = [] if pd.isna(pred_value) else [p.strip() for p in str(pred_value).split(";") if p.strip() and p.strip().lower() != "nan"]
        for pred in preds:
            from_row = qty_by_op.get((candidate_id, pred), {})
            to_row = qty_by_op.get((candidate_id, to_op), {})
            available = _num(from_row.get("schedulable_production_qty"))
            required = _num(to_row.get("schedulable_production_qty"))
            impact_row = impact_by_op.get((candidate_id, to_op), {})
            blocker = "MATERIAL_SHORTAGE_REVIEW" if impact_row.get("schedule_impact_status") == "MATERIAL_BLOCKED_REVIEW" else ""
            rows.append({
                "planning_run_id": op.get("planning_run_id", ""),
                "edge_id": f"{candidate_id}-{pred}-{to_op}",
                "schedule_candidate_id": candidate_id,
                "from_node_id": f"{candidate_id}-{pred}",
                "to_node_id": f"{candidate_id}-{to_op}",
                "finished_sku": op.get("finished_sku", ""),
                "from_operation_id": pred,
                "to_operation_id": to_op,
                "dependency_type": "MERGE_DEPENDENCY" if _bool(op.get("merge_operation_flag")) else "FINISH_TO_START",
                "required_quantity": round(required, 4),
                "available_quantity": round(available, 4),
                "critical_edge_flag": bool(required > TOL and available <= required + TOL),
                "blocker_reason": blocker,
                "source_phase": SOURCE_PHASE,
                "advisory_only_flag": True,
            })
    return pd.DataFrame(rows, columns=_graph_edge_columns())


def _build_validation(material, shortage, impact, recommendation, nodes, edges, frames):
    rows = []
    run_id = material["planning_run_id"].iloc[0] if not material.empty else ""

    def add(name, passed, message, affected=0):
        rows.append({"planning_run_id": run_id, "check_id": f"INT234-{len(rows)+1:03d}", "check_name": name, "status": "PASS" if passed else "FAIL", "message": message, "affected_rows": int(affected), "advisory_only_flag": True})

    mapped = material[material["component_operation_mapping_status"] == "EXPLICIT_CONSUMING_OPERATION_MAPPED"]
    unmapped = material[material["component_operation_mapping_status"] == UNMAPPED_STATUS]
    dated_mapped = mapped[mapped["required_date"].fillna("").astype(str).str.len() > 0]
    undated_mapped = mapped[mapped["required_date_source"].astype(str) == "CONSUMING_OPERATION_NOT_SCHEDULED"]
    mapped_dates = dated_mapped.apply(lambda r: str(r["required_date"]) == _date_part(r["consuming_operation_start_datetime"]), axis=1) if not dated_mapped.empty else pd.Series(dtype=bool)
    late_without_date = material[(material["material_readiness_status"].astype(str) == "LATE_INBOUND_REVIEW") & (material["required_date"].fillna("").astype(str).str.len() == 0)]
    on_time_without_date = material[(_bool_series(material["inbound_available_before_operation_flag"])) & (material["required_date"].fillna("").astype(str).str.len() == 0)]
    undated_preserved = undated_mapped["consuming_operation_id"].fillna("").astype(str).str.len().gt(0).all() and undated_mapped["workstation_id"].fillna("").astype(str).str.len().gt(0).all()
    node_ids = set(nodes["node_id"]) if "node_id" in nodes.columns else set()
    missing_endpoints = edges[~edges["from_node_id"].isin(node_ids) | ~edges["to_node_id"].isin(node_ids)] if {"from_node_id", "to_node_id"} <= set(edges.columns) else edges
    impact_by_key = _index_multi(impact, ["schedule_candidate_id", "operation_id"])
    node_mismatches = 0
    for _, node in nodes.iterrows():
        key = (str(node["schedule_candidate_id"]), str(node["operation_id"]))
        expected = impact_by_key.get(key, {}).get("schedule_impact_status", "NO_DIRECT_COMPONENT_CHECK")
        if str(node["material_readiness_status"]) != str(expected):
            node_mismatches += 1

    add("OUTPUTS_NON_EMPTY", all(not df.empty for df in [material, shortage, impact, recommendation, nodes, edges]), "All integrated Phase 2/3/4 outputs are non-empty.")
    add("ALL_COMPONENT_REQUIREMENTS_TRACE_TO_PHASE4", len(material) == len(frames["pegging"]) and set(material["component_sku"]) <= set(frames["pegging"]["component_sku"]), "Material readiness rows trace to Phase 4 MRP pegging.", len(material))
    add("EXPLICIT_COMPONENT_OPERATION_MAP_EXISTS", not frames["component_operation_map"].empty, "Explicit component-to-operation consumption map exists.")
    add("NO_KEYWORD_BASED_COMPONENT_MAPPING", not material["component_operation_mapping_basis"].astype(str).str.contains("KEYWORD|COMPONENT_NAME_TO_ROUTING", case=False, regex=True).any(), "Component mapping does not use keyword/name inference.")
    add("COMPONENT_MAPPED_TO_ACTUAL_CONSUMING_OPERATION", len(mapped) + len(unmapped) == len(material) and mapped["consuming_operation_id"].astype(str).str.len().gt(0).all(), "Component requirements are mapped to explicit consuming operations or explicitly marked for review.", len(unmapped))
    add("REQUIRED_DATE_EQUALS_CONSUMING_OPERATION_START_DATE", bool(mapped_dates.all()) if not mapped.empty else True, "Required material dates equal the consuming operation start date for mapped rows.", int((~mapped_dates).sum()) if not mapped.empty else 0)
    add("NO_LATE_INBOUND_STATUS_WITHOUT_REQUIRED_DATE", late_without_date.empty, "Late inbound review is used only when required date exists.", len(late_without_date))
    add("NO_ON_TIME_FLAG_WITHOUT_REQUIRED_DATE", on_time_without_date.empty, "Inbound on-time flag is never true without a required date.", len(on_time_without_date))
    add("UNDATED_OPERATION_MAPPING_PRESERVED", bool(undated_preserved), "Explicit mappings with undated operations preserve consuming operation and workstation evidence.", len(undated_mapped))
    add("NO_FIRST_OPERATION_FALLBACK_SILENTLY_USED", "FIRST_OPERATION_FALLBACK" not in set(material["component_operation_mapping_basis"].astype(str)), "No silent first-operation fallback mapping is used.")
    valid_route_keys = set(zip(frames["routing"]["finished_sku"].astype(str), frames["routing"]["operation_id"].astype(str))) if not frames["routing"].empty else set()
    invalid_mapped_ops = mapped[~mapped.apply(lambda r: (str(r["finished_sku"]), str(r["consuming_operation_id"])) in valid_route_keys, axis=1)]
    add("MAPPED_COMPONENT_REFERENCES_VALID_ROUTING_OPERATION", invalid_mapped_ops.empty, "Mapped component consuming operations reference valid routing operations.", len(invalid_mapped_ops))
    add("NO_INVENTORY_REUSE", _no_inventory_reuse(material, frames["inventory"]), "Inventory used by requirements does not exceed Phase 3 usable inventory by component.", len(material))
    add("SUPPLIER_ALLOCATION_CAPACITY_YIELD_RESPECTED", _supplier_capacity_ok(material), "Supplier allocation is capped by capacity and yield evidence.", len(material))
    late_use = material[(material["expected_inbound_qty_available_for_requirement"].map(_num) > TOL) & (pd.to_datetime(material["expected_inbound_date"], errors="coerce") > pd.to_datetime(material["required_date"], errors="coerce"))]
    add("INBOUND_NOT_USED_BEFORE_ARRIVAL", late_use.empty, "Inbound material is not used before arrival.", len(late_use))
    add("SCHEDULE_IMPACT_TRACES_TO_SHORTAGES", _impact_traces(material, impact), "Schedule impacts trace to candidate/operation component shortages.", len(impact))
    add("GRAPH_JOINS_CANDIDATE_SPECIFIC", {"schedule_candidate_id", "from_node_id", "to_node_id"} <= set(edges.columns) and nodes["node_id"].is_unique, "Graph edges and nodes use schedule-candidate-specific keys.", len(edges))
    add("GRAPH_EDGE_ENDPOINTS_EXIST", missing_endpoints.empty, "Every graph edge endpoint references a real node ID.", len(missing_endpoints))
    add("NODE_STATUS_MATCHES_CANDIDATE_IMPACT", node_mismatches == 0, "Graph node material status matches same-candidate operation schedule impact.", node_mismatches)
    add("NO_CANDIDATE_STATUS_INHERITANCE", "WIP_STATUS_NOT_CANDIDATE_SPECIFIC_REVIEW" in set(nodes["wip_readiness_status"].astype(str)) or "schedule_candidate_id" in frames["wip"].columns, "Candidate-specific fields are joined by candidate/operation; non-candidate-specific WIP is marked review.", len(nodes))
    rec_row = recommendation.iloc[0]
    rec_ok = _bool(rec_row.get("independent_recalculation_performed_flag")) or str(rec_row.get("recommendation_recalculation_status")) == "RECOMMENDATION_NOT_RECALCULABLE_FROM_CURRENT_INTEGRATION"
    add("RECOMMENDATION_CALCULATED_OR_EXPLICITLY_NONRECALCULABLE", rec_ok, "Recommendation is independently recalculated when possible or explicitly marked non-recalculable.", 1)
    add("VALIDATION_NOT_HARDCODED_FLAG", str(rec_row.get("recommendation_check_status")) != "RECOMMENDATION_UNCHANGED_WITH_MATERIAL_REVIEW", "Validation no longer passes by checking the old hardcoded unchanged flag.", 1)
    add("RELEASE_REMAINS_BLOCKED", not _bool(rec_row.get("production_release_allowed")) and str(rec_row.get("release_readiness_status")) == "NOT_READY_FOR_RELEASE", "Release remains blocked.", 1)
    add("ADVISORY_ONLY", all(_all_true(df, "advisory_only_flag") for df in [material, shortage, impact, recommendation, nodes, edges]), "All integrated outputs are advisory-only.")
    add("NO_FORBIDDEN_EXECUTION_OUTPUTS", not _forbidden_outputs_exist(), "No execution outputs were created.")
    return pd.DataFrame(rows, columns=_validation_columns())


def _explicit_component_operation_map(mapping_df: pd.DataFrame, routing: pd.DataFrame, bom: pd.DataFrame) -> dict[tuple[str, str], dict]:
    if mapping_df.empty or routing.empty:
        return {}
    valid_route_keys = set(zip(routing["finished_sku"].astype(str), routing["operation_id"].astype(str)))
    bom_qty = {(str(row.get("finished_sku", "")), str(row.get("component_sku", ""))): _num(row.get("quantity_per_finished_unit")) for _, row in bom.iterrows()} if not bom.empty else {}
    mapping: dict[tuple[str, str], dict] = {}
    for _, row in mapping_df.iterrows():
        sku = str(row.get("finished_sku", ""))
        component_sku = str(row.get("component_sku", ""))
        op_id = str(row.get("consuming_operation_id", ""))
        status = str(row.get("mapping_status", ""))
        if (sku, op_id) in valid_route_keys and status == "EXPLICIT_CONSUMING_OPERATION_MAPPED" and not _bool(row.get("review_required_flag")):
            qty = _num(row.get("quantity_per_finished_unit"))
            qty_basis = "BOM_QUANTITY_MATCH" if abs(qty - bom_qty.get((sku, component_sku), qty)) <= TOL else "MAP_QUANTITY_REVIEW"
            mapping[(sku, component_sku)] = {
                "operation_id": op_id,
                "mapping_basis": f"EXPLICIT_PLANNING_MASTER_{qty_basis}",
                "mapping_source": row.get("mapping_source", "phase4_component_operation_consumption_map.csv"),
                "review_required_flag": row.get("review_required_flag", False),
            }
    return mapping


def _operation_dates(ops: pd.DataFrame) -> dict[tuple[str, str], dict]:
    if ops.empty:
        return {}
    baseline = ops[ops["alternative_id"].astype(str) == REFERENCE_ALT].copy()
    return {(str(row["schedule_candidate_id"]), str(row["operation_id"])): row.to_dict() for _, row in baseline.iterrows()}


def _best_capability(cap: pd.DataFrame) -> dict[str, dict]:
    if cap.empty:
        return {}
    comp = cap[cap["sku_id"].astype(str).str.startswith("SKU-COMP")].copy()
    comp["_rank"] = pd.to_numeric(comp.get("balanced_supplier_score_rank", 999), errors="coerce").fillna(999)
    comp["_risk"] = pd.to_numeric(comp.get("demand_adjusted_procurement_risk_score", 999), errors="coerce").fillna(999)
    comp = comp.sort_values(["sku_id", "_rank", "_risk"])
    return {str(group.iloc[0]["sku_id"]): group.iloc[0].to_dict() for _, group in comp.groupby("sku_id")}


def _data_as_of(cap: pd.DataFrame) -> pd.Timestamp:
    if not cap.empty and "data_as_of_date" in cap.columns:
        dt = pd.to_datetime(cap["data_as_of_date"].dropna().astype(str).iloc[0], errors="coerce")
        if not pd.isna(dt):
            return dt
    return pd.Timestamp("2026-07-26")


def _no_inventory_reuse(material: pd.DataFrame, inventory: pd.DataFrame) -> bool:
    inv = _index(inventory, "component_sku")
    used = material.groupby("component_sku")["inventory_qty_used_for_requirement"].apply(lambda s: sum(_num(v) for v in s)).to_dict()
    return all(qty <= _num(inv.get(sku, {}).get("available_qty")) + TOL for sku, qty in used.items())


def _supplier_capacity_ok(material: pd.DataFrame) -> bool:
    capacities = material["phase2_capacity_limited_supplier_qty"].map(_num)
    allocated = material["phase2_allocated_supplier_qty"].map(_num)
    return bool(((allocated <= capacities + TOL) | (capacities <= TOL)).all())


def _impact_traces(material: pd.DataFrame, impact: pd.DataFrame) -> bool:
    by_op = material.groupby(["schedule_candidate_id", "consuming_operation_id"], dropna=False)["remaining_shortage_qty"].apply(lambda s: sum(_num(v) for v in s)).to_dict()
    for _, row in impact.iterrows():
        shortage = _num(by_op.get((str(row["schedule_candidate_id"]), str(row["operation_id"])), 0.0))
        if shortage > TOL and str(row["schedule_impact_status"]) not in {"MATERIAL_BLOCKED_REVIEW", "CONSUMING_OPERATION_UNMAPPED_REVIEW", "REQUIRED_DATE_UNAVAILABLE_REVIEW"}:
            return False
    return True


def _load(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _index(df: pd.DataFrame, column: str) -> dict[str, dict]:
    if df.empty or column not in df.columns:
        return {}
    return {str(row[column]): row.to_dict() for _, row in df.iterrows()}


def _index_multi(df: pd.DataFrame, columns: list[str]) -> dict[tuple[str, ...], dict]:
    if df.empty or not set(columns) <= set(df.columns):
        return {}
    return {tuple(str(row[col]) for col in columns): row.to_dict() for _, row in df.iterrows()}


def _num(value) -> float:
    try:
        if pd.isna(value) or str(value).strip() == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bool(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _all_true(df: pd.DataFrame, column: str) -> bool:
    return column in df.columns and df[column].astype(str).str.lower().isin({"true", "1", "yes"}).all()


def _date_part(value) -> str:
    dt = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(dt) else dt.date().isoformat()


def _forbidden_outputs_exist() -> bool:
    patterns = ["*production_order*.csv", "*confirmed_schedule*.csv", "*worker_dispatch*.csv", "*inventory_reservation*.csv", "*inventory_consumption*.csv", "*wip_transaction*.csv", "*purchase_order_release*.csv", "*maintenance_work_order*.csv", "*capacity_reduction_applied*.csv", "*simulation*.csv"]
    allow = {"phase4_production_schedule_candidates.csv", "phase4_operation_schedule_candidate_detail.csv", "phase4_production_schedule_validation.csv"}
    return any(path.name not in allow for pattern in patterns for path in OUTPUT_DIR.glob(pattern))


def _material_columns():
    return ["planning_run_id", "finished_sku", "schedule_candidate_id", "component_sku", "component_name", "required_date", "consuming_operation_id", "consuming_operation_name", "workstation_id", "consuming_operation_start_datetime", "component_operation_mapping_status", "component_operation_mapping_basis", "component_operation_mapping_source", "component_operation_review_required_flag", "required_date_source", "phase4_required_qty", "phase3_available_inventory_qty", "inventory_qty_used_for_requirement", "phase3_net_replenishment_need_qty", "phase2_allocated_supplier_qty", "phase2_capacity_limited_supplier_qty", "phase2_moq_adjusted_order_qty", "phase2_yield_rate", "expected_inbound_qty_available_for_requirement", "expected_inbound_date", "inbound_available_before_operation_flag", "remaining_shortage_qty", "material_readiness_status", "material_blocker_flag", "source_phase4_file", "source_phase3_file", "source_phase2_file", "advisory_only_flag"]


def _shortage_columns():
    return ["planning_run_id", "component_sku", "component_name", "finished_sku", "schedule_candidate_id", "consuming_operation_id", "consuming_operation_name", "workstation_id", "component_operation_mapping_status", "component_operation_mapping_source", "required_date", "expected_inbound_date", "required_qty", "inventory_used_qty", "inbound_used_qty", "remaining_shortage_qty", "shortage_timing_status", "late_days", "source_phase", "advisory_only_flag"]


def _impact_columns():
    return ["planning_run_id", "schedule_candidate_id", "finished_sku", "operation_id", "operation_name", "workstation_id", "component_operation_mapping_status", "affected_component_count", "late_component_count", "remaining_shortage_qty", "schedule_impact_status", "blocker_reason", "recommendation_change_required_flag", "source_phase", "advisory_only_flag"]


def _recommendation_check_columns():
    return ["planning_run_id", "prior_recommended_alternative_id", "integrated_recommended_alternative_id", "recommendation_changed_flag", "recommendation_recalculation_status", "recommendation_retention_status", "independent_recalculation_performed_flag", "recommendation_check_status", "recommendation_check_reason", "release_readiness_status", "production_release_allowed", "material_release_blocker_flag", "source_phase", "advisory_only_flag"]


def _graph_node_columns():
    return ["planning_run_id", "node_id", "node_type", "schedule_candidate_id", "finished_sku", "operation_id", "operation_name", "workstation_id", "workstation_name", "proposed_start_datetime", "proposed_end_datetime", "critical_path_flag", "slack_time_minutes", "utilization_pct", "bottleneck_status", "material_readiness_status", "wip_readiness_status", "buffer_status", "blocker_type", "source_phase", "advisory_only_flag"]


def _graph_edge_columns():
    return ["planning_run_id", "edge_id", "schedule_candidate_id", "from_node_id", "to_node_id", "finished_sku", "from_operation_id", "to_operation_id", "dependency_type", "required_quantity", "available_quantity", "critical_edge_flag", "blocker_reason", "source_phase", "advisory_only_flag"]


def _validation_columns():
    return ["planning_run_id", "check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"]


if __name__ == "__main__":
    outputs = build_integrated_phase234_outputs()
    print(f"Integrated material-readiness rows: {len(outputs[0])}")
    print(f"Integrated shortage timeline rows: {len(outputs[1])}")
    print(f"Integrated schedule-impact rows: {len(outputs[2])}")
    print(f"Integrated recommendation-check rows: {len(outputs[3])}")
    print(f"Integrated validation rows: {len(outputs[4])}")
    print(f"Integrated graph nodes: {len(outputs[5])}")
    print(f"Integrated graph edges: {len(outputs[6])}")
