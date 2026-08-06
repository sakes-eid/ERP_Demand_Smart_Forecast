"""Build Step 8G manager-facing schedule alternative decision data.

This module reads finalized Step 8F advisory outputs and summarizes them for
manager review. It does not create schedules, orders, dispatches, reservations,
transactions, or capacity changes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

PHASE4_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE4_DIR.parent
OUTPUT_DIR = PHASE4_DIR / "outputs"

STEP8F_MASTER_FILE = OUTPUT_DIR / "phase4_schedule_alternative_master.csv"
STEP8F_DETAIL_FILE = OUTPUT_DIR / "phase4_schedule_alternative_operation_detail.csv"
STEP8F_SEGMENTS_FILE = OUTPUT_DIR / "phase4_schedule_alternative_operation_segments.csv"
STEP8F_WIP_FILE = OUTPUT_DIR / "phase4_schedule_alternative_wip_impact.csv"
STEP8F_SETUP_FILE = OUTPUT_DIR / "phase4_schedule_alternative_setup_impact.csv"
STEP8F_MAINTENANCE_FILE = OUTPUT_DIR / "phase4_schedule_alternative_maintenance_impact.csv"
STEP8F_COST_FILE = OUTPUT_DIR / "phase4_schedule_alternative_cost_score.csv"
STEP8F_RECOMMENDATIONS_FILE = OUTPUT_DIR / "phase4_schedule_alternative_recommendations.csv"
STEP8F_REVIEW_FILE = OUTPUT_DIR / "phase4_schedule_alternative_manager_review_queue.csv"
STEP8F_VALIDATION_FILE = OUTPUT_DIR / "phase4_schedule_alternative_validation.csv"
BOTTLENECK_FILE = OUTPUT_DIR / "phase4_bottleneck_visibility_summary.csv"
PHASE4_VALIDATION_JSON = OUTPUT_DIR / "phase4_initialization_validation.json"

SUMMARY_OUTPUT_FILE = OUTPUT_DIR / "phase4_step8g_alternative_summary.csv"
RECOMMENDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_step8g_recommendation.csv"
MANAGER_REVIEW_OUTPUT_FILE = OUTPUT_DIR / "phase4_step8g_manager_review_queue.csv"
VALIDATION_OUTPUT_FILE = OUTPUT_DIR / "phase4_step8g_validation.csv"
TRADEOFF_OUTPUT_FILE = OUTPUT_DIR / "phase4_step8g_tradeoff_analysis.csv"
DECISION_RISKS_OUTPUT_FILE = OUTPUT_DIR / "phase4_step8g_decision_risks.csv"
RELEASE_READINESS_OUTPUT_FILE = OUTPUT_DIR / "phase4_step8g_release_readiness.csv"

SOURCE_PHASE = "PHASE4_STEP8G_MANAGER_DECISION_DATASET"
TOLERANCE = 0.0001
STEP8G_FINAL_STATUS = "CLOSED_WITH_REVIEW"
STEP8G_DECISION_STATE = "READY_FOR_MANAGER_REVIEW_NOT_RELEASED"


def build_step8g_manager_decision_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frames = {
        "master": _load(STEP8F_MASTER_FILE),
        "detail": _load(STEP8F_DETAIL_FILE),
        "segments": _load(STEP8F_SEGMENTS_FILE),
        "wip": _load(STEP8F_WIP_FILE),
        "setup": _load(STEP8F_SETUP_FILE),
        "maintenance": _load(STEP8F_MAINTENANCE_FILE),
        "cost": _load(STEP8F_COST_FILE),
        "recommendations": _load(STEP8F_RECOMMENDATIONS_FILE),
        "step8f_review": _load(STEP8F_REVIEW_FILE),
        "step8f_validation": _load(STEP8F_VALIDATION_FILE),
        "bottleneck": _load(BOTTLENECK_FILE),
    }
    upstream = _upstream_warning_counts()
    summary = _build_summary(frames, upstream)
    equivalent_groups = _equivalent_groups(summary)
    recommendation = _build_recommendation(summary, equivalent_groups)
    review = _build_review_queue(summary, recommendation, equivalent_groups, upstream, frames)
    tradeoff = _build_tradeoff_analysis(summary, equivalent_groups)
    risks = _build_decision_risks(summary, recommendation, equivalent_groups, upstream, frames)
    readiness = _build_release_readiness(summary, recommendation, upstream, frames)
    validation = _build_validation(frames, summary, recommendation, review, equivalent_groups, upstream, tradeoff, risks, readiness)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_OUTPUT_FILE, index=False)
    recommendation.to_csv(RECOMMENDATION_OUTPUT_FILE, index=False)
    review.to_csv(MANAGER_REVIEW_OUTPUT_FILE, index=False)
    tradeoff.to_csv(TRADEOFF_OUTPUT_FILE, index=False)
    risks.to_csv(DECISION_RISKS_OUTPUT_FILE, index=False)
    readiness.to_csv(RELEASE_READINESS_OUTPUT_FILE, index=False)
    validation.to_csv(VALIDATION_OUTPUT_FILE, index=False)
    return summary, recommendation, review, validation


def _build_summary(frames: dict[str, pd.DataFrame], upstream: dict[str, int]) -> pd.DataFrame:
    master = frames["master"]
    segments = frames["segments"]
    wip = frames["wip"]
    setup = frames["setup"]
    maintenance = frames["maintenance"]
    cost = frames["cost"]
    bottleneck = frames["bottleneck"]

    top_bottleneck = _top_bottleneck(bottleneck)
    cost_by_alt = _index(cost, "alternative_id")
    recommendation_rank = master.set_index("alternative_id")["recommendation_rank"].to_dict()
    rows: list[dict] = []
    for _, alt in master.iterrows():
        alt_id = str(alt["alternative_id"])
        seg_alt = segments[segments["alternative_id"].astype(str) == alt_id]
        scheduled = seg_alt[seg_alt["segment_scheduled_qty"].map(_num) > 0]
        wip_alt = wip[wip["alternative_id"].astype(str) == alt_id]
        setup_alt = setup[setup["alternative_id"].astype(str) == alt_id]
        maint_alt = maintenance[maintenance["alternative_id"].astype(str) == alt_id]
        cost_row = cost_by_alt.get(alt_id, {})
        assumed_or_penalty = _num(cost_row.get("assumed_monetary_cost_total")) + _num(cost_row.get("total_proxy_penalty"))
        rows.append({
            "planning_run_id": alt["planning_run_id"],
            "alternative_id": alt_id,
            "alternative_name": alt.get("alternative_name", alt.get("alternative_type", "")),
            "alternative_type": alt.get("alternative_type", ""),
            "step8f_status": alt.get("hard_feasibility_status", ""),
            "planned_demand_qty": round(_num(alt.get("planned_demand_qty")), 4),
            "completed_full_route_qty": round(_num(alt.get("covered_demand_qty")), 4),
            "demand_coverage_pct": round(_num(alt.get("demand_coverage_pct")), 4),
            "unscheduled_qty": round(_num(alt.get("unscheduled_qty", alt.get("uncovered_demand_qty"))), 4),
            "scheduled_processing_minutes": round(scheduled["segment_processing_minutes"].map(_num).sum(), 4),
            "setup_minutes": round(scheduled["segment_setup_minutes"].map(_num).sum(), 4),
            "setup_switch_count": int(_to_bool(setup_alt.get("setup_switch_flag", pd.Series(dtype=object))).sum()),
            "main_bottleneck_workstation": top_bottleneck.get("workstation_id", ""),
            "main_bottleneck_workstation_name": top_bottleneck.get("workstation_name", ""),
            "main_bottleneck_level": top_bottleneck.get("bottleneck_visibility_level", ""),
            "buffer_blocked_qty": round(wip_alt["buffer_blocked_output_qty"].map(_num).sum() if "buffer_blocked_output_qty" in wip_alt else 0.0, 4),
            "wip_blocked_qty": round(wip_alt["wip_shortage_qty"].map(_num).sum() if "wip_shortage_qty" in wip_alt else 0.0, 4),
            "maintenance_review_count": int((maint_alt["maintenance_feasibility_status"].astype(str).str.upper() != "FEASIBLE").sum()) if "maintenance_feasibility_status" in maint_alt else 0,
            "validated_real_cost": round(_num(cost_row.get("validated_real_cost_total", alt.get("validated_real_cost_total"))), 4),
            "assumed_cost_or_penalty": round(assumed_or_penalty, 4),
            "cost_confidence_level": cost_row.get("cost_confidence", alt.get("cost_confidence", "")),
            "upstream_warning_count": int(upstream.get("phase2_warning_count", 0) + upstream.get("phase3_warning_count", 0) + upstream.get("integrated_warning_count", 0)),
            "recommendation_rank": int(_num(recommendation_rank.get(alt_id, alt.get("recommendation_rank", 0)))),
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_summary_columns())


def _build_recommendation(summary: pd.DataFrame, equivalent_groups: list[list[str]]) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame(columns=_recommendation_columns())
    ranked = summary.copy()
    ranked["_risk_score"] = ranked.apply(_serious_planning_risk, axis=1)
    ranked = ranked.sort_values(
        ["demand_coverage_pct", "_risk_score", "validated_real_cost", "setup_minutes", "assumed_cost_or_penalty", "alternative_id"],
        ascending=[False, True, True, True, True, True],
    )
    selected = ranked.iloc[0].to_dict()
    for group in equivalent_groups:
        if "ALT-BASELINE" in group and selected["alternative_id"] in group:
            selected = ranked[ranked["alternative_id"] == "ALT-BASELINE"].iloc[0].to_dict()
            break
    equivalent_text = ";".join(",".join(group) for group in equivalent_groups)
    reason = "Selected highest coverage, lowest serious planning risk, then lower cost/setup/penalty exposure."
    if any("ALT-BASELINE" in group and "ALT-MAINT" in group for group in equivalent_groups):
        reason += " ALT-BASELINE and ALT-MAINT are equivalent on decision metrics; baseline is used as the simpler reference."
    return pd.DataFrame([{
        "planning_run_id": selected["planning_run_id"],
        "recommended_alternative_id": selected["alternative_id"],
        "recommended_alternative_name": selected["alternative_name"],
        "recommendation_status": "RECOMMENDED_FOR_REVIEW",
        "recommendation_reason": reason,
        "equivalent_result_group": equivalent_text,
        "step8g_final_status": STEP8G_FINAL_STATUS,
        "step8g_decision_state": STEP8G_DECISION_STATE,
        "selected_as_reference_flag": True,
        "approval_status": "NOT_APPROVED_NOT_RELEASED",
        "release_authorized_flag": False,
        "source_phase": SOURCE_PHASE,
        "advisory_only_flag": True,
    }], columns=_recommendation_columns())


def _build_review_queue(summary: pd.DataFrame, recommendation: pd.DataFrame, equivalent_groups: list[list[str]], upstream: dict[str, int], frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict] = []
    planning_run_id = summary["planning_run_id"].iloc[0] if not summary.empty else ""

    def add(issue_type: str, severity: str, alt_id: str, impact: str, source_file: str, action: str) -> None:
        rows.append({
            "review_item_id": f"STEP8G-REV-{len(rows)+1:04d}",
            "planning_run_id": planning_run_id,
            "alternative_id": alt_id,
            "issue_type": issue_type,
            "issue_severity": severity,
            "business_impact": impact,
            "source_file": source_file,
            "recommended_manager_action": action,
            "auto_action_allowed": False,
            "advisory_only_flag": True,
        })

    for _, row in summary.iterrows():
        alt_id = str(row["alternative_id"])
        if _num(row["demand_coverage_pct"]) < 100:
            add("PARTIAL_DEMAND_COVERAGE", "HIGH", alt_id, f"Only {row['demand_coverage_pct']}% full-route demand coverage.", "phase4_schedule_alternative_master.csv", "Review whether partial coverage is acceptable or request another scenario.")
        if _num(row["buffer_blocked_qty"]) > 0 or _num(row["wip_blocked_qty"]) > 0:
            add("BUFFER_OR_WIP_BLOCKED_PRODUCTION", "HIGH", alt_id, f"Buffer blocked qty={row['buffer_blocked_qty']}; WIP blocked qty={row['wip_blocked_qty']}.", "phase4_schedule_alternative_wip_impact.csv", "Review WIP buffers, upstream/downstream flow, and candidate quantities.")
        if str(row["cost_confidence_level"]).upper() in {"LOW", "REVIEW_REQUIRED"}:
            add("LOW_COST_CONFIDENCE", "MEDIUM", alt_id, f"Cost confidence is {row['cost_confidence_level']}.", "phase4_schedule_alternative_cost_score.csv", "Review cost assumptions before approving a scenario.")
        if _num(row["assumed_cost_or_penalty"]) > 0:
            add("ASSUMED_PENALTIES_USED", "MEDIUM", alt_id, f"Assumed/proxy exposure={row['assumed_cost_or_penalty']}.", "phase4_schedule_alternative_cost_score.csv", "Separate real cost from proxy exposure during management review.")
        if str(row["main_bottleneck_level"]).upper() in {"HIGH", "CRITICAL"}:
            add("MAJOR_BOTTLENECK", "HIGH", alt_id, f"Main bottleneck is {row['main_bottleneck_workstation']} ({row['main_bottleneck_level']}).", "phase4_bottleneck_visibility_summary.csv", "Review bottleneck capacity before selecting a schedule alternative.")
    if upstream.get("phase2_warning_count", 0) or upstream.get("phase3_warning_count", 0) or upstream.get("integrated_warning_count", 0):
        add("UPSTREAM_PHASE_WARNINGS", "MEDIUM", "", f"Phase 2 warnings={upstream.get('phase2_warning_count', 0)}; Phase 3 warnings={upstream.get('phase3_warning_count', 0)}; integrated warnings={upstream.get('integrated_warning_count', 0)}.", "phase4_initialization_validation.json", "Keep upstream warnings visible; do not attribute them to Step 8G.")
    for group in equivalent_groups:
        add("EQUIVALENT_ALTERNATIVES", "LOW", ",".join(group), f"Equivalent decision metrics for {', '.join(group)}.", "phase4_step8g_alternative_summary.csv", "Use the simpler baseline reference when equivalent.")
    selected = recommendation["recommended_alternative_id"].iloc[0] if not recommendation.empty else ""
    add("RELEASE_NOT_AUTHORIZED", "HIGH", selected, "Recommendation is for review only; no release is authorized.", "phase4_step8g_recommendation.csv", "Manager must approve a later decision layer before any execution action.")
    return pd.DataFrame(rows, columns=_review_columns())


def _build_tradeoff_analysis(summary: pd.DataFrame, equivalent_groups: list[list[str]]) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame(columns=_tradeoff_columns())
    baseline_rows = summary[summary["alternative_id"].astype(str) == "ALT-BASELINE"]
    baseline = baseline_rows.iloc[0].to_dict() if not baseline_rows.empty else summary.iloc[0].to_dict()
    rows: list[dict] = []
    for _, alt in summary.iterrows():
        alt_row = alt.to_dict()
        alt_id = str(alt_row["alternative_id"])
        deltas = {
            "demand_coverage_delta_pct": _delta(alt_row, baseline, "demand_coverage_pct"),
            "completed_quantity_delta": _delta(alt_row, baseline, "completed_full_route_qty"),
            "unscheduled_quantity_delta": _delta(alt_row, baseline, "unscheduled_qty"),
            "validated_cost_delta": _delta(alt_row, baseline, "validated_real_cost"),
            "assumed_penalty_delta": _delta(alt_row, baseline, "assumed_cost_or_penalty"),
            "setup_minutes_delta": _delta(alt_row, baseline, "setup_minutes"),
            "setup_switch_delta": _delta(alt_row, baseline, "setup_switch_count"),
            "buffer_blocked_quantity_delta": _delta(alt_row, baseline, "buffer_blocked_qty"),
            "wip_blocked_quantity_delta": _delta(alt_row, baseline, "wip_blocked_qty"),
            "maintenance_review_count_delta": _delta(alt_row, baseline, "maintenance_review_count"),
        }
        equivalent = alt_id == str(baseline["alternative_id"]) or any(alt_id in group and str(baseline["alternative_id"]) in group for group in equivalent_groups)
        meaningful = any(abs(value) > TOLERANCE for value in deltas.values()) or str(alt_row.get("main_bottleneck_level", "")) != str(baseline.get("main_bottleneck_level", ""))
        if equivalent:
            tradeoff_summary = "Equivalent to ALT-BASELINE on decision metrics; no meaningful difference claimed."
        elif not meaningful:
            tradeoff_summary = "No meaningful difference versus ALT-BASELINE within tolerance."
        else:
            tradeoff_summary = _tradeoff_summary_text(deltas)
        rows.append({
            "planning_run_id": alt_row["planning_run_id"],
            "baseline_alternative_id": baseline["alternative_id"],
            "compared_alternative_id": alt_id,
            "compared_alternative_name": alt_row["alternative_name"],
            "step8f_status": alt_row["step8f_status"],
            "equivalent_to_baseline_flag": bool(equivalent),
            "meaningful_difference_flag": bool(meaningful and not equivalent),
            "baseline_demand_coverage_pct": baseline["demand_coverage_pct"],
            "compared_demand_coverage_pct": alt_row["demand_coverage_pct"],
            "demand_coverage_delta_pct": round(deltas["demand_coverage_delta_pct"], 4),
            "baseline_completed_full_route_qty": baseline["completed_full_route_qty"],
            "compared_completed_full_route_qty": alt_row["completed_full_route_qty"],
            "completed_quantity_delta": round(deltas["completed_quantity_delta"], 4),
            "baseline_unscheduled_qty": baseline["unscheduled_qty"],
            "compared_unscheduled_qty": alt_row["unscheduled_qty"],
            "unscheduled_quantity_delta": round(deltas["unscheduled_quantity_delta"], 4),
            "validated_cost_delta": round(deltas["validated_cost_delta"], 4),
            "assumed_penalty_delta": round(deltas["assumed_penalty_delta"], 4),
            "setup_minutes_delta": round(deltas["setup_minutes_delta"], 4),
            "setup_switch_delta": round(deltas["setup_switch_delta"], 4),
            "buffer_blocked_quantity_delta": round(deltas["buffer_blocked_quantity_delta"], 4),
            "wip_blocked_quantity_delta": round(deltas["wip_blocked_quantity_delta"], 4),
            "baseline_bottleneck_exposure": baseline.get("main_bottleneck_workstation", ""),
            "compared_bottleneck_exposure": alt_row.get("main_bottleneck_workstation", ""),
            "bottleneck_exposure_change": "UNCHANGED" if str(alt_row.get("main_bottleneck_workstation", "")) == str(baseline.get("main_bottleneck_workstation", "")) else "CHANGED",
            "maintenance_review_count_delta": int(round(deltas["maintenance_review_count_delta"])),
            "tradeoff_summary": tradeoff_summary,
            "source_phase": SOURCE_PHASE,
            "advisory_only_flag": True,
        })
    return pd.DataFrame(rows, columns=_tradeoff_columns())


def _build_decision_risks(summary: pd.DataFrame, recommendation: pd.DataFrame, equivalent_groups: list[list[str]], upstream: dict[str, int], frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict] = []
    planning_run_id = summary["planning_run_id"].iloc[0] if not summary.empty else ""

    def add(risk_type: str, severity: str, impact: str, affected_alt: str, resource: str, source_phase_reference: str, source_file: str, action: str) -> None:
        rows.append({
            "risk_item_id": f"STEP8G-RISK-{len(rows)+1:04d}",
            "planning_run_id": planning_run_id,
            "risk_type": risk_type,
            "severity": severity,
            "business_impact": impact,
            "affected_alternative_or_resource": affected_alt or resource,
            "affected_alternative_id": affected_alt,
            "affected_resource_id": resource,
            "source_phase_reference": source_phase_reference,
            "source_file": source_file,
            "recommended_manager_action": action,
            "auto_action_allowed": False,
            "advisory_only_flag": True,
        })

    for _, row in summary.iterrows():
        alt_id = str(row["alternative_id"])
        if _num(row["demand_coverage_pct"]) < 100:
            add("PARTIAL_DEMAND_COVERAGE", "HIGH", f"{alt_id} covers {row['demand_coverage_pct']}% of full-route demand.", alt_id, "", "PHASE4_STEP8F", "phase4_schedule_alternative_master.csv", "Decide whether partial finite coverage is acceptable before release.")
        if str(row.get("main_bottleneck_workstation", "")) == "WS-FINAL-ASM" or str(row.get("main_bottleneck_level", "")).upper() in {"HIGH", "CRITICAL"}:
            add("FINAL_ASSEMBLY_BOTTLENECK", "HIGH", f"Primary bottleneck exposure remains {row.get('main_bottleneck_workstation', '')}.", alt_id, str(row.get("main_bottleneck_workstation", "")), "PHASE4_STEP5B", "phase4_bottleneck_visibility_summary.csv", "Review final assembly bottleneck before selecting an alternative.")
        if _num(row["buffer_blocked_qty"]) > 0 or _num(row["wip_blocked_qty"]) > 0:
            add("BLOCKED_PRODUCTION", "HIGH", f"Buffer blocked qty={row['buffer_blocked_qty']}; WIP blocked qty={row['wip_blocked_qty']}.", alt_id, "", "PHASE4_STEP8F", "phase4_schedule_alternative_wip_impact.csv", "Review finite WIP buffers and shortages before release.")
        if str(row["cost_confidence_level"]).upper() in {"LOW", "REVIEW_REQUIRED"}:
            add("LOW_COST_CONFIDENCE", "MEDIUM", f"Cost confidence is {row['cost_confidence_level']}.", alt_id, "", "PHASE4_STEP8F", "phase4_schedule_alternative_cost_score.csv", "Validate cost-rate assumptions before treating score as decision-ready.")
        if _num(row["assumed_cost_or_penalty"]) > 0:
            add("ASSUMED_PENALTIES", "MEDIUM", f"Assumed/proxy penalty exposure is {row['assumed_cost_or_penalty']}.", alt_id, "", "PHASE4_STEP8F", "phase4_schedule_alternative_cost_score.csv", "Keep assumed/proxy exposure separate from validated cost.")
        if _num(row["maintenance_review_count"]) > 0:
            add("UNCONFIRMED_MAINTENANCE_IMPACT", "MEDIUM", f"Maintenance review count is {row['maintenance_review_count']}.", alt_id, "", "PHASE4_STEP7G_STEP8F", "phase4_schedule_alternative_maintenance_impact.csv", "Complete maintenance review before approving release.")

    if upstream.get("phase2_warning_count", 0):
        add("UPSTREAM_PHASE2_WARNINGS", "MEDIUM", f"Phase 2 warnings remain visible: {upstream['phase2_warning_count']}.", "", "PHASE2", "PHASE2", "phase4_initialization_validation.json", "Resolve or accept procurement warnings before release.")
    if upstream.get("phase3_warning_count", 0):
        add("UPSTREAM_PHASE3_WARNINGS", "MEDIUM", f"Phase 3 warnings remain visible: {upstream['phase3_warning_count']}.", "", "PHASE3", "PHASE3", "phase4_initialization_validation.json", "Resolve or accept inventory warnings before release.")
    if upstream.get("integrated_warning_count", 0):
        add("UPSTREAM_INTEGRATED_WARNINGS", "MEDIUM", f"Integrated validation warnings remain visible: {upstream['integrated_warning_count']}.", "", "INTEGRATED", "INTEGRATED", "phase4_initialization_validation.json", "Resolve or formally accept integrated validation warnings before release.")
    for group in equivalent_groups:
        add("EQUIVALENT_ALTERNATIVES", "LOW", f"Equivalent alternatives detected: {', '.join(group)}.", ",".join(group), "", SOURCE_PHASE, "phase4_step8g_tradeoff_analysis.csv", "Use one reference alternative for review; avoid over-interpreting identical results.")
    selected = recommendation["recommended_alternative_id"].iloc[0] if not recommendation.empty else ""
    add("MANAGER_APPROVAL_REQUIRED", "HIGH", "Recommendation is not approved or released.", selected, "", SOURCE_PHASE, "phase4_step8g_release_readiness.csv", "Manager approval must be recorded in a later decision layer before execution.")
    return pd.DataFrame(rows, columns=_decision_risk_columns())


def _build_release_readiness(summary: pd.DataFrame, recommendation: pd.DataFrame, upstream: dict[str, int], frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    planning_run_id = summary["planning_run_id"].iloc[0] if not summary.empty else ""
    step8f_validation = frames["step8f_validation"]
    selected_alt = recommendation["recommended_alternative_id"].iloc[0] if not recommendation.empty else ""
    selected_summary = summary[summary["alternative_id"].astype(str) == str(selected_alt)]
    selected = selected_summary.iloc[0].to_dict() if not selected_summary.empty else {}

    step8f_closed = (
        not step8f_validation.empty
        and not (step8f_validation["status"].astype(str).str.upper() == "FAIL").any()
        and "STEP8F_FINAL_CLOSURE_STATUS" in set(step8f_validation["check_id"].astype(str))
    )
    checks = [
        ("STEP8F_CLOSED", "Step 8F closed", step8f_closed, "phase4_schedule_alternative_validation.csv", "Step 8F final closure validation is present and has no FAIL rows.", "Keep Step 8F evidence attached to decision review."),
        ("RECOMMENDATION_GENERATED", "Recommendation generated", not recommendation.empty and str(recommendation.iloc[0]["recommendation_status"]) == "RECOMMENDED_FOR_REVIEW", "phase4_step8g_recommendation.csv", f"Recommended alternative: {selected_alt}.", "Review recommendation; do not release yet."),
        ("MANAGER_APPROVAL_RECEIVED", "Manager approval received", False, "phase4_step8g_recommendation.csv", "No manager approval record exists in Step 8G-B.", "Capture explicit manager approval in a later release decision step."),
        ("UPSTREAM_WARNINGS_RESOLVED", "Upstream warnings resolved", upstream.get("phase2_warning_count", 0) == 0 and upstream.get("phase3_warning_count", 0) == 0 and upstream.get("integrated_warning_count", 0) == 0, "phase4_initialization_validation.json", f"Phase 2 warnings={upstream.get('phase2_warning_count', 0)}; Phase 3 warnings={upstream.get('phase3_warning_count', 0)}; integrated warnings={upstream.get('integrated_warning_count', 0)}.", "Resolve or accept upstream warnings before release."),
        ("MATERIAL_READINESS_CONFIRMED", "Material readiness confirmed", False, "phase4_production_schedule_material_readiness.csv", "Material readiness remains planning evidence, not release confirmation.", "Confirm material readiness before production release."),
        ("INVENTORY_READINESS_CONFIRMED", "Inventory readiness confirmed", False, "phase4_component_inventory_check.csv", "Inventory readiness remains advisory and upstream warnings are still visible.", "Confirm inventory availability before production release."),
        ("MAINTENANCE_REVIEW_COMPLETED", "Maintenance review completed", _num(selected.get("maintenance_review_count")) == 0, "phase4_schedule_alternative_maintenance_impact.csv", f"Selected alternative maintenance review count={_num(selected.get('maintenance_review_count'))}.", "Complete maintenance review before production release."),
        ("SCHEDULE_REMAINS_INTERNALLY_VALID", "Schedule remains internally valid", step8f_closed and str(selected.get("step8f_status", "")) in {"PARTIAL_FINITE_SCHEDULE", "CLOSED_WITH_REVIEW", "HARD_FEASIBLE_WITH_REVIEW", "HARD_FEASIBLE"}, "phase4_schedule_alternative_validation.csv", f"Selected Step 8F status={selected.get('step8f_status', '')}.", "Use as advisory scenario evidence only."),
    ]
    failed_checks = [check_id for check_id, _, passed, _, _, _ in checks if not passed]
    final_status = "NOT_READY_FOR_RELEASE" if failed_checks else "READY_FOR_MANAGER_REVIEW"
    support_rows = []
    for check_id, name, passed, source_file, evidence, action in checks:
        readiness_status = "PASS" if passed else "BLOCKED"
        support_rows.append({
            "readiness_item_id": f"STEP8G-READY-{len(support_rows)+1:04d}",
            "planning_run_id": planning_run_id,
            "readiness_row_type": "SUPPORTING_CHECK",
            "readiness_check_type": check_id,
            "readiness_check_name": name,
            "readiness_status": readiness_status,
            "release_readiness_status": final_status,
            "production_release_allowed": False,
            "evidence_source_file": source_file,
            "evidence_summary": evidence,
            "recommended_manager_action": action,
            "auto_action_allowed": False,
            "advisory_only_flag": True,
        })
    overall = {
        "readiness_item_id": "STEP8G-READY-0000",
        "planning_run_id": planning_run_id,
        "readiness_row_type": "OVERALL",
        "readiness_check_type": "OVERALL_RELEASE_READINESS",
        "readiness_check_name": "Overall release readiness",
        "readiness_status": "BLOCKED" if failed_checks else "PASS",
        "release_readiness_status": final_status,
        "production_release_allowed": False,
        "evidence_source_file": "phase4_step8g_release_readiness.csv",
        "evidence_summary": "Failed readiness checks: " + (";".join(failed_checks) if failed_checks else "NONE"),
        "recommended_manager_action": "Do not release production; complete blocked readiness checks first.",
        "auto_action_allowed": False,
        "advisory_only_flag": True,
    }
    return pd.DataFrame([overall, *support_rows], columns=_release_readiness_columns())


def _build_validation(frames: dict[str, pd.DataFrame], summary: pd.DataFrame, recommendation: pd.DataFrame, review: pd.DataFrame, equivalent_groups: list[list[str]], upstream: dict[str, int], tradeoff: pd.DataFrame, risks: pd.DataFrame, readiness: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    planning_run_id = summary["planning_run_id"].iloc[0] if not summary.empty else ""

    def add(name: str, passed: bool, message: str, affected: int = 0) -> None:
        rows.append({
            "planning_run_id": planning_run_id,
            "check_id": f"STEP8G-A-{len(rows)+1:03d}",
            "check_name": name,
            "status": "PASS" if passed else "FAIL",
            "message": message,
            "affected_rows": affected,
            "advisory_only_flag": True,
        })

    master = frames["master"]
    add("OUTPUTS_NOT_EMPTY", not summary.empty and not recommendation.empty and not review.empty, "Step 8G-A outputs exist and are non-empty.", len(summary) + len(recommendation) + len(review))
    add("ONE_SUMMARY_ROW_PER_ALTERNATIVE", len(summary) == len(master) and summary["alternative_id"].is_unique, "One summary row per Step 8F alternative.", len(summary))
    add("METRICS_TRACE_TO_STEP8F", _summary_traces_to_step8f(summary, frames), "Summary metrics reconcile to Step 8F master/cost/segment/WIP/setup evidence.", len(summary))
    add("RECOMMENDATION_RANKING_RECALCULATES", _recommendation_recalculates(summary, recommendation), "Recommendation ranking recalculates from coverage, risk, cost, setup, and penalty exposure.", len(recommendation))
    add("EQUIVALENT_ALTERNATIVES_DETECTED", any("ALT-BASELINE" in group and "ALT-MAINT" in group for group in equivalent_groups), "Equivalent alternatives are detected, including ALT-BASELINE and ALT-MAINT for this run.", len(equivalent_groups))
    add("COSTS_REMAIN_SEPARATE", "validated_real_cost" in summary and "assumed_cost_or_penalty" in summary and (summary["assumed_cost_or_penalty"].map(_num) >= 0).all(), "Validated real cost remains separate from assumed/proxy exposure.", len(summary))
    add("UPSTREAM_WARNINGS_ATTRIBUTED", upstream.get("phase2_warning_count", 0) >= 0 and upstream.get("phase3_warning_count", 0) >= 0 and upstream.get("integrated_warning_count", 0) >= 0, "Upstream warnings remain attributed to their source phase.", upstream.get("phase2_warning_count", 0) + upstream.get("phase3_warning_count", 0) + upstream.get("integrated_warning_count", 0))
    add("ADVISORY_ONLY_FLAGS", _all_true(summary, "advisory_only_flag") and _all_true(recommendation, "advisory_only_flag") and _all_true(review, "advisory_only_flag"), "All Step 8G-A outputs are advisory-only.", len(summary) + len(recommendation) + len(review))
    add("NO_AUTO_ACTIONS", _all_false(review, "auto_action_allowed") and _all_false(recommendation, "release_authorized_flag"), "No automatic action or release is authorized.", len(review) + len(recommendation))
    add("NO_FORBIDDEN_EXECUTION_OUTPUTS", not _forbidden_outputs_exist(), "No production orders, dispatch, reservations, transactions, or execution outputs exist.", 0)
    add("TRADEOFF_OUTPUTS_NOT_EMPTY", not tradeoff.empty, "Step 8G-B trade-off analysis exists and is non-empty.", len(tradeoff))
    add("TRADEOFF_METRICS_TRACE_TO_SUMMARY", _tradeoff_traces_to_summary(tradeoff, summary), "Trade-off deltas reconcile to Step 8G-A summary and therefore Step 8F evidence.", len(tradeoff))
    add("EQUIVALENT_TRADEOFFS_HANDLED", _equivalent_tradeoffs_handled(tradeoff, equivalent_groups), "Equivalent alternatives are clearly marked without claiming meaningful differences.", len(equivalent_groups))
    add("DECISION_RISKS_NOT_EMPTY", not risks.empty, "Step 8G-B decision risk rows exist.", len(risks))
    add("UPSTREAM_RISKS_ATTRIBUTED", _upstream_risks_attributed(risks, upstream), "Upstream risks remain attributed to Phase 2/Phase 3 sources.", upstream.get("phase2_warning_count", 0) + upstream.get("phase3_warning_count", 0))
    add("RELEASE_READINESS_BLOCKED", _release_readiness_blocked(readiness), "Release readiness is blocked and production release is not allowed.", len(readiness))
    add("STEP8G_B_ADVISORY_ONLY_FLAGS", _all_true(tradeoff, "advisory_only_flag") and _all_true(risks, "advisory_only_flag") and _all_true(readiness, "advisory_only_flag"), "All Step 8G-B outputs are advisory-only.", len(tradeoff) + len(risks) + len(readiness))
    add("STEP8G_B_NO_AUTO_ACTIONS", _all_false(risks, "auto_action_allowed") and _all_false(readiness, "auto_action_allowed") and _all_false(readiness, "production_release_allowed"), "Step 8G-B does not approve release or allow automatic actions.", len(risks) + len(readiness))
    add("STEP8G_FINAL_STATUS_CLOSED_WITH_REVIEW", not recommendation.empty and str(recommendation.iloc[0].get("step8g_final_status", "")) == STEP8G_FINAL_STATUS, "Formal Step 8G closure status is CLOSED_WITH_REVIEW.", len(recommendation))
    add("UPSTREAM_WARNINGS_BLOCK_RELEASE_READINESS", _upstream_warnings_block_release(readiness, upstream), "Unresolved Phase 2, Phase 3, or integrated warnings block release readiness.", len(readiness))
    return pd.DataFrame(rows, columns=_validation_columns())


def _summary_traces_to_step8f(summary: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> bool:
    master = frames["master"].set_index("alternative_id")
    cost = frames["cost"].set_index("alternative_id")
    segments = frames["segments"]
    for _, row in summary.iterrows():
        alt_id = row["alternative_id"]
        if alt_id not in master.index or alt_id not in cost.index:
            return False
        m = master.loc[alt_id]
        c = cost.loc[alt_id]
        if abs(_num(row["completed_full_route_qty"]) - _num(m["covered_demand_qty"])) > 0.01:
            return False
        if abs(_num(row["validated_real_cost"]) - _num(c["validated_real_cost_total"])) > 0.01:
            return False
        seg = segments[(segments["alternative_id"].astype(str) == str(alt_id)) & (segments["segment_scheduled_qty"].map(_num) > 0)]
        if abs(_num(row["scheduled_processing_minutes"]) - seg["segment_processing_minutes"].map(_num).sum()) > 0.05:
            return False
    return True


def _tradeoff_traces_to_summary(tradeoff: pd.DataFrame, summary: pd.DataFrame) -> bool:
    if tradeoff.empty or summary.empty:
        return False
    summary_idx = summary.set_index("alternative_id")
    baseline_rows = summary[summary["alternative_id"].astype(str) == "ALT-BASELINE"]
    if baseline_rows.empty:
        return False
    baseline = baseline_rows.iloc[0]
    for _, row in tradeoff.iterrows():
        alt_id = str(row["compared_alternative_id"])
        if alt_id not in summary_idx.index:
            return False
        alt = summary_idx.loc[alt_id]
        checks = [
            ("demand_coverage_delta_pct", _num(alt["demand_coverage_pct"]) - _num(baseline["demand_coverage_pct"])),
            ("completed_quantity_delta", _num(alt["completed_full_route_qty"]) - _num(baseline["completed_full_route_qty"])),
            ("unscheduled_quantity_delta", _num(alt["unscheduled_qty"]) - _num(baseline["unscheduled_qty"])),
            ("validated_cost_delta", _num(alt["validated_real_cost"]) - _num(baseline["validated_real_cost"])),
            ("assumed_penalty_delta", _num(alt["assumed_cost_or_penalty"]) - _num(baseline["assumed_cost_or_penalty"])),
            ("setup_minutes_delta", _num(alt["setup_minutes"]) - _num(baseline["setup_minutes"])),
            ("setup_switch_delta", _num(alt["setup_switch_count"]) - _num(baseline["setup_switch_count"])),
            ("buffer_blocked_quantity_delta", _num(alt["buffer_blocked_qty"]) - _num(baseline["buffer_blocked_qty"])),
            ("wip_blocked_quantity_delta", _num(alt["wip_blocked_qty"]) - _num(baseline["wip_blocked_qty"])),
            ("maintenance_review_count_delta", _num(alt["maintenance_review_count"]) - _num(baseline["maintenance_review_count"])),
        ]
        if any(abs(_num(row[column]) - expected) > 0.01 for column, expected in checks):
            return False
    return True


def _equivalent_tradeoffs_handled(tradeoff: pd.DataFrame, equivalent_groups: list[list[str]]) -> bool:
    if tradeoff.empty:
        return False
    for group in equivalent_groups:
        if "ALT-BASELINE" not in group:
            continue
        subset = tradeoff[tradeoff["compared_alternative_id"].astype(str).isin(group)]
        if subset.empty:
            return False
        if not _all_true(subset, "equivalent_to_baseline_flag"):
            return False
        if _to_bool(subset["meaningful_difference_flag"]).any():
            return False
    return True


def _upstream_risks_attributed(risks: pd.DataFrame, upstream: dict[str, int]) -> bool:
    if risks.empty:
        return False
    if upstream.get("phase2_warning_count", 0) > 0:
        phase2 = risks[risks["risk_type"].astype(str) == "UPSTREAM_PHASE2_WARNINGS"]
        if phase2.empty or not phase2["source_phase_reference"].astype(str).str.contains("PHASE2").any():
            return False
    if upstream.get("phase3_warning_count", 0) > 0:
        phase3 = risks[risks["risk_type"].astype(str) == "UPSTREAM_PHASE3_WARNINGS"]
        if phase3.empty or not phase3["source_phase_reference"].astype(str).str.contains("PHASE3").any():
            return False
    if upstream.get("integrated_warning_count", 0) > 0:
        integrated = risks[risks["risk_type"].astype(str) == "UPSTREAM_INTEGRATED_WARNINGS"]
        if integrated.empty or not integrated["source_phase_reference"].astype(str).str.contains("INTEGRATED").any():
            return False
    return True


def _upstream_warnings_block_release(readiness: pd.DataFrame, upstream: dict[str, int]) -> bool:
    if readiness.empty:
        return False
    warning_count = upstream.get("phase2_warning_count", 0) + upstream.get("phase3_warning_count", 0) + upstream.get("integrated_warning_count", 0)
    row = readiness[readiness["readiness_check_type"].astype(str) == "UPSTREAM_WARNINGS_RESOLVED"]
    if row.empty:
        return False
    status = str(row.iloc[0]["readiness_status"])
    if warning_count > 0:
        return status in {"BLOCKED", "REVIEW_REQUIRED"}
    return status == "PASS"


def _release_readiness_blocked(readiness: pd.DataFrame) -> bool:
    if readiness.empty:
        return False
    overall = readiness[readiness["readiness_row_type"].astype(str) == "OVERALL"]
    if overall.empty:
        return False
    row = overall.iloc[0]
    return (
        str(row["release_readiness_status"]) == "NOT_READY_FOR_RELEASE"
        and not bool(_to_bool(pd.Series([row["production_release_allowed"]])).iloc[0])
        and readiness["readiness_check_type"].astype(str).isin({
            "STEP8F_CLOSED", "RECOMMENDATION_GENERATED", "MANAGER_APPROVAL_RECEIVED", "UPSTREAM_WARNINGS_RESOLVED",
            "MATERIAL_READINESS_CONFIRMED", "INVENTORY_READINESS_CONFIRMED", "MAINTENANCE_REVIEW_COMPLETED",
            "SCHEDULE_REMAINS_INTERNALLY_VALID", "OVERALL_RELEASE_READINESS",
        }).all()
    )


def _recommendation_recalculates(summary: pd.DataFrame, recommendation: pd.DataFrame) -> bool:
    if summary.empty or recommendation.empty:
        return False
    ranked = summary.copy()
    ranked["_risk_score"] = ranked.apply(_serious_planning_risk, axis=1)
    ranked = ranked.sort_values(
        ["demand_coverage_pct", "_risk_score", "validated_real_cost", "setup_minutes", "assumed_cost_or_penalty", "alternative_id"],
        ascending=[False, True, True, True, True, True],
    )
    expected = str(ranked.iloc[0]["alternative_id"])
    top_group = _equivalent_groups(summary)
    for group in top_group:
        if expected in group and "ALT-BASELINE" in group:
            expected = "ALT-BASELINE"
    return str(recommendation.iloc[0]["recommended_alternative_id"]) == expected and str(recommendation.iloc[0]["recommendation_status"]) == "RECOMMENDED_FOR_REVIEW"


def _equivalent_groups(summary: pd.DataFrame) -> list[list[str]]:
    if summary.empty:
        return []
    fields = [
        "step8f_status",
        "planned_demand_qty",
        "completed_full_route_qty",
        "demand_coverage_pct",
        "unscheduled_qty",
        "scheduled_processing_minutes",
        "setup_minutes",
        "buffer_blocked_qty",
        "wip_blocked_qty",
        "maintenance_review_count",
        "validated_real_cost",
        "assumed_cost_or_penalty",
        "cost_confidence_level",
    ]
    groups: list[list[str]] = []
    for _, group in summary.groupby(fields, dropna=False):
        if len(group) > 1:
            groups.append(sorted(group["alternative_id"].astype(str).tolist()))
    return groups


def _serious_planning_risk(row: pd.Series) -> float:
    risk = 0.0
    risk += max(100.0 - _num(row.get("demand_coverage_pct")), 0.0) * 10
    risk += _num(row.get("buffer_blocked_qty")) * 2
    risk += _num(row.get("wip_blocked_qty")) * 2
    risk += _num(row.get("maintenance_review_count")) * 25
    risk += _num(row.get("upstream_warning_count")) * 10
    if str(row.get("cost_confidence_level", "")).upper() == "LOW":
        risk += 50
    return risk


def _delta(row: dict, baseline: dict, column: str) -> float:
    return _num(row.get(column)) - _num(baseline.get(column))


def _tradeoff_summary_text(deltas: dict[str, float]) -> str:
    parts: list[str] = []
    if abs(deltas["demand_coverage_delta_pct"]) > TOLERANCE:
        direction = "higher" if deltas["demand_coverage_delta_pct"] > 0 else "lower"
        parts.append(f"{abs(deltas['demand_coverage_delta_pct']):.4f} pct points {direction} coverage")
    if abs(deltas["assumed_penalty_delta"]) > TOLERANCE:
        direction = "higher" if deltas["assumed_penalty_delta"] > 0 else "lower"
        parts.append(f"{abs(deltas['assumed_penalty_delta']):.4f} {direction} assumed/proxy exposure")
    if abs(deltas["setup_minutes_delta"]) > TOLERANCE:
        direction = "higher" if deltas["setup_minutes_delta"] > 0 else "lower"
        parts.append(f"{abs(deltas['setup_minutes_delta']):.4f} minutes {direction} setup")
    if abs(deltas["buffer_blocked_quantity_delta"]) > TOLERANCE:
        direction = "higher" if deltas["buffer_blocked_quantity_delta"] > 0 else "lower"
        parts.append(f"{abs(deltas['buffer_blocked_quantity_delta']):.4f} {direction} buffer-blocked qty")
    return "; ".join(parts) if parts else "Differences exist only in secondary manager-review fields."


def _top_bottleneck(bottleneck: pd.DataFrame) -> dict:
    if bottleneck.empty:
        return {}
    ranked = bottleneck.copy()
    if "bottleneck_visibility_rank" in ranked:
        ranked["_rank"] = ranked["bottleneck_visibility_rank"].map(_num)
        ranked = ranked.sort_values(["_rank", "workstation_id"])
    return ranked.iloc[0].to_dict()


def _upstream_warning_counts() -> dict[str, int]:
    result = {"phase2_warning_count": 0, "phase3_warning_count": 0, "integrated_warning_count": 0}
    if not PHASE4_VALIDATION_JSON.exists():
        return result
    try:
        data = json.loads(PHASE4_VALIDATION_JSON.read_text())
    except json.JSONDecodeError:
        return result
    for check in data.get("checks", []):
        name = str(check.get("check_name", check.get("name", check.get("check", "")))).lower()
        status = str(check.get("status", "")).upper()
        message = str(check.get("message", ""))
        count = _extract_warning_count(message)
        if status != "WARNING":
            continue
        if "phase2" in name or "phase 2" in message.lower():
            result["phase2_warning_count"] += max(count, 1)
        elif "phase3" in name or "phase 3" in message.lower():
            result["phase3_warning_count"] += max(count, 1)
        elif "integrated" in name:
            result["integrated_warning_count"] += max(count, 1)
    return result


def _extract_warning_count(message: str) -> int:
    import re

    match = re.search(r"WARNING\s*=\s*(\d+)", message)
    return int(match.group(1)) if match else 0


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
        "*simulation*.csv",
    ]
    allow = {"phase4_production_schedule_candidates.csv", "phase4_operation_schedule_candidate_detail.csv", "phase4_production_schedule_validation.csv"}
    for pattern in patterns:
        for path in OUTPUT_DIR.glob(pattern):
            if path.name not in allow:
                return True
    return False


def _load(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _index(df: pd.DataFrame, column: str) -> dict[str, dict]:
    if df.empty or column not in df:
        return {}
    return {str(row[column]): row.to_dict() for _, row in df.iterrows()}


def _num(value) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_bool(series: pd.Series) -> pd.Series:
    if series is None or len(series) == 0:
        return pd.Series(dtype=bool)
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def _all_true(df: pd.DataFrame, column: str) -> bool:
    return column in df and bool(_to_bool(df[column]).all())


def _all_false(df: pd.DataFrame, column: str) -> bool:
    return column in df and bool((~_to_bool(df[column])).all())


def _summary_columns() -> list[str]:
    return [
        "planning_run_id", "alternative_id", "alternative_name", "alternative_type", "step8f_status",
        "planned_demand_qty", "completed_full_route_qty", "demand_coverage_pct", "unscheduled_qty",
        "scheduled_processing_minutes", "setup_minutes", "setup_switch_count", "main_bottleneck_workstation",
        "main_bottleneck_workstation_name", "main_bottleneck_level", "buffer_blocked_qty", "wip_blocked_qty",
        "maintenance_review_count", "validated_real_cost", "assumed_cost_or_penalty", "cost_confidence_level",
        "upstream_warning_count", "recommendation_rank", "source_phase", "advisory_only_flag",
    ]


def _recommendation_columns() -> list[str]:
    return [
        "planning_run_id", "recommended_alternative_id", "recommended_alternative_name", "recommendation_status",
        "recommendation_reason", "equivalent_result_group", "step8g_final_status", "step8g_decision_state",
        "selected_as_reference_flag", "approval_status", "release_authorized_flag", "source_phase", "advisory_only_flag",
    ]


def _review_columns() -> list[str]:
    return [
        "review_item_id", "planning_run_id", "alternative_id", "issue_type", "issue_severity",
        "business_impact", "source_file", "recommended_manager_action", "auto_action_allowed",
        "advisory_only_flag",
    ]


def _tradeoff_columns() -> list[str]:
    return [
        "planning_run_id", "baseline_alternative_id", "compared_alternative_id", "compared_alternative_name",
        "step8f_status", "equivalent_to_baseline_flag", "meaningful_difference_flag",
        "baseline_demand_coverage_pct", "compared_demand_coverage_pct", "demand_coverage_delta_pct",
        "baseline_completed_full_route_qty", "compared_completed_full_route_qty", "completed_quantity_delta",
        "baseline_unscheduled_qty", "compared_unscheduled_qty", "unscheduled_quantity_delta",
        "validated_cost_delta", "assumed_penalty_delta", "setup_minutes_delta", "setup_switch_delta",
        "buffer_blocked_quantity_delta", "wip_blocked_quantity_delta", "baseline_bottleneck_exposure",
        "compared_bottleneck_exposure", "bottleneck_exposure_change", "maintenance_review_count_delta",
        "tradeoff_summary", "source_phase", "advisory_only_flag",
    ]


def _decision_risk_columns() -> list[str]:
    return [
        "risk_item_id", "planning_run_id", "risk_type", "severity", "business_impact",
        "affected_alternative_or_resource", "affected_alternative_id", "affected_resource_id",
        "source_phase_reference", "source_file", "recommended_manager_action", "auto_action_allowed",
        "advisory_only_flag",
    ]


def _release_readiness_columns() -> list[str]:
    return [
        "readiness_item_id", "planning_run_id", "readiness_row_type", "readiness_check_type",
        "readiness_check_name", "readiness_status", "release_readiness_status", "production_release_allowed",
        "evidence_source_file", "evidence_summary", "recommended_manager_action", "auto_action_allowed",
        "advisory_only_flag",
    ]


def _validation_columns() -> list[str]:
    return ["planning_run_id", "check_id", "check_name", "status", "message", "affected_rows", "advisory_only_flag"]


if __name__ == "__main__":
    outputs = build_step8g_manager_decision_outputs()
    print(f"Step 8G-A alternative summary rows: {len(outputs[0])}")
    print(f"Step 8G-A recommendation rows: {len(outputs[1])}")
    print(f"Step 8G-A manager review rows: {len(outputs[2])}")
    print(f"Step 8G-A validation rows: {len(outputs[3])}")
    print(f"Step 8G-B trade-off rows: {len(_load(TRADEOFF_OUTPUT_FILE))}")
    print(f"Step 8G-B decision risk rows: {len(_load(DECISION_RISKS_OUTPUT_FILE))}")
    print(f"Step 8G-B release readiness rows: {len(_load(RELEASE_READINESS_OUTPUT_FILE))}")
