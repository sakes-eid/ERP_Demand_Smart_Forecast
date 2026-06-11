"""Build visual-ready warehouse map outputs from Step 9 slotting data."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from config import (
    WAREHOUSE_UTILIZATION_THRESHOLDS,
    WAREHOUSE_VISUAL_COLOR_GROUPS,
    WAREHOUSE_VISUAL_CONFIG,
    WAREHOUSE_VISUAL_WARNING_PRIORITY,
)

VISUAL_COLOR_NAME_TO_HEX = {
    "RED": "#d62728",
    "ORANGE": "#ff7f0e",
    "YELLOW": "#f1c40f",
    "GREEN": "#2ca02c",
    "BLUE": "#1f77b4",
    "PURPLE": "#9467bd",
    "GRAY": "#7f7f7f",
}


def build_warehouse_visualization(
    warehouse_slotting: pd.DataFrame,
    batch_slotting: pd.DataFrame,
    location_utilization: pd.DataFrame,
    space_utilization: pd.DataFrame,
    warehouse_travel_costs: pd.DataFrame,
    storage_locations_clean: pd.DataFrame,
    warehouse_layout_clean: pd.DataFrame,
    inventory_status: pd.DataFrame,
    inventory_costs: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Return CSV-ready visual outputs and optional HTML maps."""
    visual_locations = _build_visual_locations(location_utilization)
    visual_skus = _build_visual_skus(warehouse_slotting, inventory_status, inventory_costs)
    visual_batches = _build_visual_batches(batch_slotting)
    visual_grid = _build_visual_grid(visual_locations)
    visual_legend = _build_visual_legend()
    visual_summary = _build_visual_summary(
        visual_grid,
        visual_locations,
        visual_skus,
        visual_batches,
        visual_legend,
        warehouse_travel_costs,
    )
    html_outputs = _build_html_maps(visual_locations)
    return (
        visual_grid,
        visual_locations,
        visual_skus,
        visual_batches,
        visual_legend,
        visual_summary,
        html_outputs,
    )


def _build_visual_locations(location_utilization: pd.DataFrame) -> pd.DataFrame:
    """Create one visual row per warehouse location."""
    rows = []
    for _, row in location_utilization.iterrows():
        visual_row = row.to_dict()
        current_status = _resolve_location_status(
            visual_row,
            "current_location_status",
            "current_capacity_status",
            "current_utilization_pct",
            "current_over_capacity_flag",
            "current_capacity_pressure_flag",
        )
        projected_status = _resolve_location_status(
            visual_row,
            "projected_location_status",
            "projected_capacity_status",
            "projected_utilization_pct",
            "projected_over_capacity_flag",
            "projected_capacity_pressure_flag",
        )
        visual_row["current_location_status"] = current_status
        visual_row["projected_location_status"] = projected_status
        if _is_blank(visual_row.get("location_status")):
            visual_row["location_status"] = _worse_location_status(current_status, projected_status)
        group = _location_color_group(visual_row)
        warnings = _as_text(row.get("location_warning_flags"))
        role_warnings = _as_text(row.get("location_role_warning_flags"))
        info = _join_parts([row.get("location_role_info_flags"), row.get("map_color_group")])
        label = (
            f"{_as_text(row.get('location_id'))} | {_as_text(row.get('zone'))} | "
            f"Projected {_fmt_pct(row.get('projected_utilization_pct'))}"
        )
        problem = _problem_summary([warnings, role_warnings])
        hover = _hover_text(
            {
                "Location": row.get("location_id"),
                "Zone": row.get("zone"),
                "Current utilization": _fmt_pct(row.get("current_utilization_pct")),
                "Projected utilization": _fmt_pct(row.get("projected_utilization_pct")),
                "Current status": current_status,
                "Projected status": projected_status,
                "Primary SKUs": row.get("assigned_primary_skus"),
                "Replenishment SKUs": row.get("assigned_replenishment_skus"),
                "Quarantine batches": row.get("assigned_quarantine_skus"),
                "FEFO batches": row.get("assigned_fefo_skus"),
                "Trace-only batches": row.get("assigned_trace_only_batches"),
                "Warnings": _join_parts([warnings, role_warnings]),
                "Info": info,
            }
        )
        out = {column: visual_row.get(column, "") for column in _LOCATION_COLUMNS}
        out.update(
            {
                "visual_layer": "LOCATION_BASE",
                "visual_color_group": group,
                "visual_color_name": _color(group),
                "visual_priority": _visual_priority(group, _join_parts([warnings, role_warnings])),
                "visual_label": label,
                "visual_hover_text": hover,
                "visual_problem_summary": problem,
                "show_on_2d_map": True,
                "show_on_3d_map": True,
            }
        )
        rows.append(out)
    return pd.DataFrame(rows, columns=_LOCATION_OUTPUT_COLUMNS)


def _build_visual_skus(
    warehouse_slotting: pd.DataFrame,
    inventory_status: pd.DataFrame,
    inventory_costs: pd.DataFrame,
) -> pd.DataFrame:
    """Create one visual row per SKU."""
    status_lookup = _lookup_by_sku(inventory_status)
    cost_lookup = _lookup_by_sku(inventory_costs)
    rows = []
    for _, row in warehouse_slotting.iterrows():
        sku_id = _as_text(row.get("sku_id"))
        merged = row.to_dict()
        merged.update({k: v for k, v in status_lookup.get(sku_id, {}).items() if k not in merged or _is_blank(merged[k])})
        merged.update({k: v for k, v in cost_lookup.get(sku_id, {}).items() if k not in merged or _is_blank(merged[k])})
        group = _sku_color_group(merged)
        warnings = _join_parts([merged.get("visual_warning_flags"), merged.get("slotting_warning_flags")])
        info = _join_parts([merged.get("visual_info_flags"), merged.get("slotting_info_flags")])
        label = f"{sku_id} | {_as_text(merged.get('map_zone'))} | {_as_text(merged.get('main_inventory_status'))}"
        hover = _hover_text(
            {
                "SKU": sku_id,
                "Product": merged.get("product_name"),
                "Primary location": merged.get("primary_visual_location_id"),
                "Replenishment location": merged.get("replenishment_visual_location_id"),
                "Quarantine location": merged.get("quarantine_visual_location_id"),
                "FEFO location": merged.get("fefo_visual_location_id"),
                "Primary quantity": merged.get("primary_visual_quantity"),
                "Replenishment quantity": merged.get("replenishment_visual_quantity"),
                "Quarantine quantity": merged.get("quarantine_visual_quantity"),
                "FEFO quantity": merged.get("fefo_visual_quantity"),
                "Current inventory": merged.get("current_inventory"),
                "Recommended order": merged.get("recommended_order_quantity"),
                "Status": merged.get("main_inventory_status"),
                "Action": merged.get("primary_action"),
                "Warnings": warnings,
                "Info": info,
            }
        )
        out = {column: merged.get(column, "") for column in _SKU_COLUMNS}
        out.update(
            {
                "visual_layer": "PRIMARY_STORAGE",
                "visual_color_group_resolved": group,
                "visual_color_name": _color(group),
                "visual_priority": _visual_priority(group, warnings),
                "visual_label": label,
                "visual_hover_text": hover,
                "show_primary_on_map": _num(merged.get("primary_visual_quantity")) > 0,
                "show_replenishment_on_map": _num(merged.get("replenishment_visual_quantity")) > 0,
                "show_quarantine_on_map": _num(merged.get("quarantine_visual_quantity")) > 0,
                "show_fefo_on_map": _num(merged.get("fefo_visual_quantity")) > 0,
            }
        )
        rows.append(out)
    return pd.DataFrame(rows, columns=_SKU_OUTPUT_COLUMNS)


def _build_visual_batches(batch_slotting: pd.DataFrame) -> pd.DataFrame:
    """Create one visual row per batch."""
    rows = []
    for _, row in batch_slotting.iterrows():
        trace_only = _bool(row.get("batch_trace_only_flag"))
        active = _bool(row.get("active_batch_quantity_flag"))
        group = _batch_color_group(row, trace_only, active)
        warnings = _as_text(row.get("visual_warning_flags"))
        info = _as_text(row.get("visual_info_flags"))
        show_physical = _bool(row.get("include_in_physical_map")) and not trace_only
        show_trace = _bool(row.get("include_in_traceability_layer"))
        label = f"{_as_text(row.get('batch_id'))} | {_as_text(row.get('batch_status'))}"
        hover = _hover_text(
            {
                "Batch": row.get("batch_id"),
                "SKU": row.get("sku_id"),
                "Product": row.get("product_name"),
                "Quantity": row.get("batch_quantity"),
                "Expiry": row.get("expiry_date"),
                "Status": row.get("batch_status"),
                "Location": row.get("recommended_batch_location_id"),
                "Zone": row.get("recommended_batch_zone"),
                "Physical map": show_physical,
                "Traceability layer": show_trace,
                "Warnings": warnings,
                "Info": info,
            }
        )
        out = _preserve(row, _BATCH_COLUMNS)
        out.update(
            {
                "visual_color_group_resolved": group,
                "visual_color_name": _color(group),
                "visual_priority": _visual_priority(group, warnings),
                "visual_label": label,
                "visual_hover_text": hover,
                "show_on_physical_map": show_physical,
                "show_on_traceability_layer": show_trace,
            }
        )
        rows.append(out)
    return pd.DataFrame(rows, columns=_BATCH_OUTPUT_COLUMNS)


def _build_visual_grid(visual_locations: pd.DataFrame) -> pd.DataFrame:
    """Create compact location-grid rows for spreadsheet-friendly mapping."""
    rows = []
    for index, row in visual_locations.iterrows():
        grid_col = _grid_coord(row, ["map_x", "x"], index)
        grid_row = _grid_coord(row, ["map_y", "y"], index)
        grid_z = _grid_coord(row, ["map_z", "z", "shelf"], 0)
        warning_count = _flag_count(_join_parts([row.get("location_warning_flags"), row.get("location_role_warning_flags")]))
        info_count = _flag_count(row.get("location_role_info_flags"))
        rows.append(
            {
                "grid_row": grid_row,
                "grid_col": grid_col,
                "grid_z": grid_z,
                "location_id": row.get("location_id"),
                "zone": row.get("zone"),
                "visual_cell_label": _grid_label(row),
                "visual_color_group": row.get("visual_color_group"),
                "visual_color_name": row.get("visual_color_name"),
                "current_utilization_pct": row.get("current_utilization_pct"),
                "projected_utilization_pct": row.get("projected_utilization_pct"),
                "current_location_status": row.get("current_location_status"),
                "projected_location_status": row.get("projected_location_status"),
                "primary_skus": row.get("assigned_primary_skus"),
                "replenishment_skus": row.get("assigned_replenishment_skus"),
                "quarantine_batches": row.get("assigned_quarantine_skus"),
                "fefo_batches": row.get("assigned_fefo_skus"),
                "trace_only_batches": row.get("assigned_trace_only_batches"),
                "warning_count": warning_count,
                "info_count": info_count,
                "visual_problem_summary": row.get("visual_problem_summary"),
            }
        )
    return pd.DataFrame(rows)


def _build_visual_legend() -> pd.DataFrame:
    """Create a stable legend for downstream maps and dashboards."""
    meanings = {
        "STOCKOUT": ("SKU has negative or unavailable stock.", "Expedite or review order signal."),
        "ZERO_STOCK": ("SKU has zero stock.", "Review replenishment trigger."),
        "CRITICAL_LOW_STOCK": (
            "Inventory is at or below safety stock / critical low level.",
            "Replenish, expedite, or monitor urgently.",
        ),
        "REORDER_NOW": ("Inventory position is at or below reorder point.", "Order recommended quantity."),
        "APPROACHING_REORDER_POINT": ("Inventory is close to reorder point.", "Monitor closely."),
        "OVERSTOCK": ("Inventory exceeds policy or days-of-supply limits.", "Reduce future orders."),
        "PRIMARY_STORAGE": ("Normal sellable inventory storage.", "Maintain assigned location."),
        "REPLENISHMENT_STAGING": ("Recommended order is staged through receiving.", "Review staging capacity."),
        "QUARANTINE_EXPIRED": ("Expired active batches are isolated.", "Scrap or quarantine."),
        "FEFO_NEAR_EXPIRY": ("Near-expiry active batches need FEFO attention.", "Prioritize FEFO picking."),
        "TRACE_ONLY_BATCH": ("Zero-quantity batch retained for history.", "Show only on traceability layer."),
        "CURRENT_OVER_CAPACITY": ("Location is currently over capacity.", "Review capacity immediately."),
        "PROJECTED_OVER_CAPACITY": ("Location becomes over capacity after planned replenishment.", "Review before order."),
        "CAPACITY_PRESSURE": ("Location is near capacity.", "Monitor capacity."),
        "TRAVEL_RISK": ("SKU has travel-distance risk.", "Review travel or pick-face placement."),
        "Z_LEVEL_WARNING": ("SKU has shelf-height or ergonomic risk.", "Review vertical slotting."),
        "NO_FEASIBLE_LOCATION": ("No compatible warehouse location was found.", "Manual slotting review."),
        "NORMAL": ("No major visual issue.", "No visual action."),
        "UNKNOWN": ("Missing or unclear visual status.", "Review source data."),
    }
    rows = []
    for rank, group in enumerate(meanings, start=1):
        meaning, action = meanings[group]
        rows.append(
            {
                "visual_color_group": group,
                "visual_color_name": _color(group),
                "meaning": meaning,
                "typical_action": action,
                "priority_rank": rank,
            }
        )
    return pd.DataFrame(rows)


def _build_visual_summary(
    visual_grid: pd.DataFrame,
    visual_locations: pd.DataFrame,
    visual_skus: pd.DataFrame,
    visual_batches: pd.DataFrame,
    visual_legend: pd.DataFrame,
    warehouse_travel_costs: pd.DataFrame,
) -> pd.DataFrame:
    """Create grouped visual summary counts."""
    rows = []
    rows.append(_summary_row("ALL_VISUALS", "ALL", visual_grid, visual_locations, visual_skus, visual_batches))
    rows.extend(_group_summary("BY_VISUAL_COLOR_GROUP", visual_locations, "visual_color_group", "location", visual_batches))
    rows.extend(_group_summary("BY_LOCATION_STATUS", visual_locations, "location_status", "location", visual_batches))
    rows.extend(_group_summary("BY_PROJECTED_LOCATION_STATUS", visual_locations, "projected_location_status", "location", visual_batches))
    rows.extend(_group_summary("BY_ZONE", visual_locations, "zone", "location", visual_batches))
    rows.extend(_group_summary("BY_VISUAL_LAYER", visual_batches, "visual_layer", "batch", visual_batches))
    rows.extend(_group_summary("BY_BATCH_STATUS", visual_batches, "batch_status", "batch", visual_batches))
    rows.extend(_group_summary("BY_SKU_STATUS", visual_skus, "main_inventory_status", "sku", visual_batches))
    rows.extend(_group_summary("BY_TRAVEL_RISK_GROUP", warehouse_travel_costs, "visual_travel_risk_group", "row", visual_batches))
    return pd.DataFrame(rows)


def _build_html_maps(visual_locations: pd.DataFrame) -> dict:
    """Return optional Plotly HTML map strings."""
    html_outputs = {}
    if not WAREHOUSE_VISUAL_CONFIG.get("generate_html_maps", True):
        return html_outputs
    try:
        import plotly.express as px
    except ImportError:
        print("Plotly not available; HTML map skipped.")
        return html_outputs

    plot_df = visual_locations.copy()
    if plot_df.empty:
        return html_outputs
    for column in ["map_x", "map_y", "map_z", "projected_utilization_pct"]:
        if column not in plot_df.columns:
            plot_df[column] = 0
        plot_df[column] = pd.to_numeric(plot_df[column], errors="coerce").fillna(0)
    plot_df["marker_size"] = plot_df["projected_utilization_pct"].clip(lower=5, upper=140)

    if WAREHOUSE_VISUAL_CONFIG.get("generate_2d_map", True):
        fig2d = px.scatter(
            plot_df,
            x="map_x",
            y="map_y",
            color="visual_color_group",
            text="visual_label",
            size="marker_size",
            hover_name="location_id",
            hover_data={"visual_hover_text": True, "marker_size": False},
            color_discrete_map=_plotly_color_discrete_map(),
            title="Phase 3 Warehouse 2D Visual Map",
        )
        fig2d.update_traces(textposition="top center")
        fig2d.update_yaxes(scaleanchor="x", scaleratio=1)
        html_outputs["warehouse_2d_map.html"] = _append_palette_comment(
            fig2d.to_html(include_plotlyjs="cdn", full_html=True)
        )

    if WAREHOUSE_VISUAL_CONFIG.get("generate_3d_map", True):
        fig3d = px.scatter_3d(
            plot_df,
            x="map_x",
            y="map_y",
            z="map_z",
            color="visual_color_group",
            text="visual_label",
            size="marker_size",
            hover_name="location_id",
            hover_data={"visual_hover_text": True, "marker_size": False},
            color_discrete_map=_plotly_color_discrete_map(),
            title="Phase 3 Warehouse 3D Visual Map",
        )
        html_outputs["warehouse_3d_map.html"] = _append_palette_comment(
            fig3d.to_html(include_plotlyjs="cdn", full_html=True)
        )
    return html_outputs


def _location_color_group(row: pd.Series) -> str:
    current_status = _as_text(row.get("current_location_status")).upper()
    projected_status = _as_text(row.get("projected_location_status")).upper()
    if current_status == "OVER_CAPACITY":
        return "CURRENT_OVER_CAPACITY"
    if projected_status == "OVER_CAPACITY":
        return "PROJECTED_OVER_CAPACITY"
    if current_status == "CAPACITY_PRESSURE" or projected_status == "CAPACITY_PRESSURE":
        return "CAPACITY_PRESSURE"
    role = _as_text(row.get("location_role_summary")).upper()
    if "REPLENISHMENT" in role:
        return "REPLENISHMENT_STAGING"
    if "QUARANTINE" in role:
        return "QUARANTINE_EXPIRED"
    if "FEFO" in role:
        return "FEFO_NEAR_EXPIRY"
    if _num(row.get("assigned_primary_sku_count")) > 0 or _as_text(row.get("assigned_primary_skus")):
        return "PRIMARY_STORAGE"
    return "NORMAL"


def _sku_color_group(row: dict[str, Any]) -> str:
    status = _as_text(row.get("main_inventory_status")).upper()
    warnings = _join_parts([row.get("visual_warning_flags"), row.get("slotting_warning_flags")]).upper()
    if status in {"STOCKOUT", "ZERO_STOCK", "CRITICAL_LOW_STOCK"}:
        return status
    if _bool(row.get("sku_causes_projected_staging_pressure")) or "PROJECTED_LOCATION_OVER_CAPACITY" in warnings:
        return "PROJECTED_OVER_CAPACITY"
    if status == "REORDER_NOW":
        return "REORDER_NOW"
    if status == "OVERSTOCK":
        return "OVERSTOCK"
    if _num(row.get("quarantine_visual_quantity")) > 0:
        return "QUARANTINE_EXPIRED"
    if _num(row.get("fefo_visual_quantity")) > 0:
        return "FEFO_NEAR_EXPIRY"
    if any(code in warnings for code in ["FAST_MOVING_ITEM_TOO_FAR", "A_CLASS_ITEM_TOO_FAR", "HIGH_TRAVEL_DISTANCE"]):
        return "TRAVEL_RISK"
    if any(code in warnings for code in ["FAST_MOVING_ITEM_NOT_ERGONOMIC", "FRAGILE_ITEM_HIGH_LEVEL", "HEAVY_ITEM_NOT_LOW_LEVEL"]):
        return "Z_LEVEL_WARNING"
    if _as_text(row.get("visual_status_group")) in WAREHOUSE_VISUAL_COLOR_GROUPS:
        return _as_text(row.get("visual_status_group"))
    return "NORMAL"


def _batch_color_group(row: pd.Series, trace_only: bool, active: bool) -> str:
    if trace_only:
        return "TRACE_ONLY_BATCH"
    status = _as_text(row.get("batch_status")).upper()
    if active and status == "EXPIRED_BATCH":
        return "QUARANTINE_EXPIRED"
    if active and status == "NEAR_EXPIRY_BATCH":
        return "FEFO_NEAR_EXPIRY"
    if active and status == "HEALTHY_BATCH":
        return "PRIMARY_STORAGE"
    return _as_text(row.get("visual_status_group")) or "UNKNOWN"


def _summary_row(summary_type: str, group_name: str, row_df: pd.DataFrame, locations: pd.DataFrame, skus: pd.DataFrame, batches: pd.DataFrame) -> dict:
    return {
        "summary_type": summary_type,
        "group_name": group_name,
        "row_count": len(row_df),
        "location_count": len(locations),
        "sku_count": len(skus),
        "batch_count": len(batches),
        "physical_map_batch_count": _count_true(batches, "show_on_physical_map"),
        "trace_only_batch_count": _count_true(batches, "batch_trace_only_flag"),
        "warning_count": _dataframe_warning_count(row_df),
        "info_count": _dataframe_info_count(row_df),
    }


def _group_summary(summary_type: str, df: pd.DataFrame, column: str, kind: str, batches: pd.DataFrame) -> list[dict]:
    if df.empty or column not in df.columns:
        return []
    rows = []
    for value, group in df.groupby(df[column].fillna("UNKNOWN").astype(str), dropna=False):
        rows.append(
            {
                "summary_type": summary_type,
                "group_name": value or "UNKNOWN",
                "row_count": len(group),
                "location_count": len(group) if kind == "location" else 0,
                "sku_count": len(group) if kind == "sku" else 0,
                "batch_count": len(group) if kind == "batch" else 0,
                "physical_map_batch_count": _count_true(group, "show_on_physical_map") if kind == "batch" else 0,
                "trace_only_batch_count": _count_true(group, "batch_trace_only_flag") if kind == "batch" else 0,
                "warning_count": _dataframe_warning_count(group),
                "info_count": _dataframe_info_count(group),
            }
        )
    return rows


def _lookup_by_sku(df: pd.DataFrame) -> dict[str, dict]:
    if df.empty or "sku_id" not in df.columns:
        return {}
    return {
        _as_text(row.get("sku_id")): row.to_dict()
        for _, row in df.iterrows()
        if _as_text(row.get("sku_id"))
    }


def _preserve(row: pd.Series, columns: list[str]) -> dict:
    return {column: row.get(column, "") for column in columns}


def _color(group: str) -> str:
    return WAREHOUSE_VISUAL_COLOR_GROUPS.get(_as_text(group), WAREHOUSE_VISUAL_COLOR_GROUPS.get("UNKNOWN", "GRAY"))


def _plotly_color_discrete_map() -> dict:
    return {
        group: VISUAL_COLOR_NAME_TO_HEX.get(color_name, VISUAL_COLOR_NAME_TO_HEX["GRAY"])
        for group, color_name in WAREHOUSE_VISUAL_COLOR_GROUPS.items()
    }


def _append_palette_comment(html: str) -> str:
    palette = ", ".join(f"{group}={hex_code}" for group, hex_code in _plotly_color_discrete_map().items())
    return f"{html}\n<!-- warehouse_visual_semantic_palette: {palette} -->\n"


def _resolve_location_status(
    row: dict[str, Any],
    preferred_status_column: str,
    fallback_status_column: str,
    utilization_column: str,
    over_capacity_column: str,
    capacity_pressure_column: str,
) -> str:
    """Preserve a status when present, otherwise derive it from utilization and flags."""
    existing = _as_text(row.get(preferred_status_column)) or _as_text(row.get(fallback_status_column))
    if existing:
        return existing
    utilization = _num(row.get(utilization_column))
    over_capacity = _bool(row.get(over_capacity_column)) or utilization > _num(
        WAREHOUSE_UTILIZATION_THRESHOLDS.get("over_capacity_pct"),
        100.0,
    )
    pressure = _bool(row.get(capacity_pressure_column)) or (
        utilization > _num(WAREHOUSE_UTILIZATION_THRESHOLDS.get("target_location_utilization_max_pct"), 90.0)
        and utilization <= _num(WAREHOUSE_UTILIZATION_THRESHOLDS.get("over_capacity_pct"), 100.0)
    )
    return _derive_capacity_status(utilization, over_capacity, pressure)


def _derive_capacity_status(utilization_pct: Any, over_capacity_flag: Any, capacity_pressure_flag: Any) -> str:
    """Derive a readable current/projected capacity status."""
    utilization = _num(utilization_pct)
    if _bool(over_capacity_flag):
        return "OVER_CAPACITY"
    if _bool(capacity_pressure_flag):
        return "CAPACITY_PRESSURE"
    if utilization <= 0:
        return "EMPTY"
    if utilization < _num(WAREHOUSE_UTILIZATION_THRESHOLDS.get("target_location_utilization_min_pct"), 50.0):
        return "UNDERUTILIZED"
    return "HEALTHY"


def _worse_location_status(current_status: str, projected_status: str) -> str:
    rank = {
        "OVER_CAPACITY": 5,
        "CAPACITY_PRESSURE": 4,
        "HEALTHY": 3,
        "UNDERUTILIZED": 2,
        "EMPTY": 1,
    }
    return current_status if rank.get(current_status, 0) >= rank.get(projected_status, 0) else projected_status


def _visual_priority(group: str, warning_flags: Any) -> int:
    flags = _flag_set(warning_flags)
    for idx, code in enumerate(WAREHOUSE_VISUAL_WARNING_PRIORITY, start=1):
        if code in flags or code == group:
            return idx
    fallback = {
        "STOCKOUT": 20,
        "ZERO_STOCK": 21,
        "CURRENT_OVER_CAPACITY": 22,
        "PROJECTED_OVER_CAPACITY": 23,
        "REORDER_NOW": 30,
        "CAPACITY_PRESSURE": 40,
        "QUARANTINE_EXPIRED": 50,
        "FEFO_NEAR_EXPIRY": 60,
        "TRAVEL_RISK": 70,
        "Z_LEVEL_WARNING": 75,
        "PRIMARY_STORAGE": 90,
        "REPLENISHMENT_STAGING": 95,
        "NORMAL": 100,
    }
    return fallback.get(group, 999)


def _hover_text(values: dict[str, Any]) -> str:
    parts = []
    for key, value in values.items():
        text = _as_text(value)
        if text:
            parts.append(f"{key}: {text}")
    return " | ".join(parts)


def _problem_summary(parts: list[Any]) -> str:
    flags = []
    for part in parts:
        flags.extend(_split_flags(part))
    return "; ".join(flags) if flags else "No major visual problem."


def _grid_label(row: pd.Series) -> str:
    location = _as_text(row.get("location_id")).replace("LOC-", "")
    projected = _fmt_pct(row.get("projected_utilization_pct")).replace(" ", "")
    role = _as_text(row.get("location_role_summary")).replace("_", " ")
    role_short = "EMPTY"
    if "REPLENISHMENT" in role:
        role_short = "REPL"
    elif "QUARANTINE" in role:
        role_short = "QUAR"
    elif "FEFO" in role:
        role_short = "FEFO"
    elif "PRIMARY" in role:
        role_short = "PRIM"
    return f"{location}\\n{projected} proj\\n{role_short}"


def _grid_coord(row: pd.Series, columns: list[str], fallback: int) -> int:
    for column in columns:
        value = _num(row.get(column), None)
        if value is not None and math.isfinite(value):
            return int(round(value))
    return int(fallback)


def _fmt_pct(value: Any) -> str:
    return f"{_num(value):.0f}%"


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = _as_text(value).strip().lower()
    return text in {"true", "1", "yes", "y"}


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _split_flags(value: Any) -> list[str]:
    text = _as_text(value)
    if not text:
        return []
    return [part.strip() for part in text.replace(",", ";").split(";") if part.strip()]


def _flag_set(value: Any) -> set[str]:
    return set(_split_flags(value))


def _flag_count(value: Any) -> int:
    return len(_split_flags(value))


def _join_parts(parts: list[Any]) -> str:
    flags = []
    for part in parts:
        flags.extend(_split_flags(part))
    seen = []
    for flag in flags:
        if flag not in seen:
            seen.append(flag)
    return "; ".join(seen)


def _dataframe_warning_count(df: pd.DataFrame) -> int:
    columns = [column for column in df.columns if "warning" in column.lower()]
    return int(sum(df[column].apply(_flag_count).sum() for column in columns))


def _dataframe_info_count(df: pd.DataFrame) -> int:
    columns = [column for column in df.columns if "info" in column.lower()]
    return int(sum(df[column].apply(_flag_count).sum() for column in columns))


def _count_true(df: pd.DataFrame, column: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    return int(df[column].apply(_bool).sum())


_LOCATION_COLUMNS = [
    "location_id",
    "zone",
    "aisle",
    "rack",
    "shelf",
    "bin",
    "x",
    "y",
    "z",
    "map_x",
    "map_y",
    "map_z",
    "map_zone",
    "map_label",
    "capacity_m3",
    "capacity_kg",
    "current_utilization_pct",
    "projected_utilization_pct",
    "current_weight_utilization_pct",
    "projected_weight_utilization_pct",
    "current_location_status",
    "projected_location_status",
    "location_status",
    "current_over_capacity_flag",
    "projected_over_capacity_flag",
    "current_capacity_pressure_flag",
    "projected_capacity_pressure_flag",
    "assigned_primary_skus",
    "assigned_replenishment_skus",
    "assigned_quarantine_skus",
    "assigned_fefo_skus",
    "assigned_trace_only_batches",
    "location_role_summary",
    "location_role_warning_flags",
    "location_role_info_flags",
    "location_warning_flags",
]
_LOCATION_OUTPUT_COLUMNS = _LOCATION_COLUMNS + [
    "visual_layer",
    "visual_color_group",
    "visual_color_name",
    "visual_priority",
    "visual_label",
    "visual_hover_text",
    "visual_problem_summary",
    "show_on_2d_map",
    "show_on_3d_map",
]

_SKU_COLUMNS = [
    "sku_id",
    "product_name",
    "category",
    "main_inventory_status",
    "primary_action",
    "action_priority",
    "main_cost_driver",
    "cost_risk_level",
    "current_inventory",
    "inventory_position",
    "recommended_order_quantity",
    "primary_visual_location_id",
    "replenishment_visual_location_id",
    "quarantine_visual_location_id",
    "fefo_visual_location_id",
    "primary_visual_quantity",
    "replenishment_visual_quantity",
    "quarantine_visual_quantity",
    "fefo_visual_quantity",
    "primary_visual_volume_m3",
    "replenishment_visual_volume_m3",
    "quarantine_visual_volume_m3",
    "fefo_visual_volume_m3",
    "visual_status_group",
    "visual_warning_flags",
    "visual_info_flags",
    "slotting_warning_flags",
    "slotting_info_flags",
    "sku_causes_projected_staging_pressure",
    "sku_replenishment_staging_warning",
    "sku_replenishment_staging_reason",
    "map_x",
    "map_y",
    "map_z",
    "map_zone",
    "map_label",
    "map_color_group",
]
_SKU_OUTPUT_COLUMNS = _SKU_COLUMNS + [
    "visual_layer",
    "visual_color_group_resolved",
    "visual_color_name",
    "visual_priority",
    "visual_label",
    "visual_hover_text",
    "show_primary_on_map",
    "show_replenishment_on_map",
    "show_quarantine_on_map",
    "show_fefo_on_map",
]

_BATCH_COLUMNS = [
    "batch_id",
    "sku_id",
    "product_name",
    "category",
    "batch_quantity",
    "expiry_date",
    "batch_status",
    "active_batch_quantity_flag",
    "active_batch_action_required",
    "batch_trace_only_flag",
    "include_in_physical_map",
    "include_in_traceability_layer",
    "visual_quantity",
    "visual_layer",
    "visual_status_group",
    "visual_warning_flags",
    "visual_info_flags",
    "recommended_batch_location_id",
    "recommended_batch_zone",
    "map_x",
    "map_y",
    "map_z",
    "map_zone",
    "map_label",
    "map_color_group",
]
_BATCH_OUTPUT_COLUMNS = _BATCH_COLUMNS + [
    "visual_color_group_resolved",
    "visual_color_name",
    "visual_priority",
    "visual_label",
    "visual_hover_text",
    "show_on_physical_map",
    "show_on_traceability_layer",
]
