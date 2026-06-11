"""Event-aware feature engineering for cleaned demand history."""

import pandas as pd

from config import DATE_FORMAT

EVENT_FEATURE_COLUMNS = [
    "event_count",
    "has_event",
    "before_event_flag",
    "during_event_flag",
    "after_event_flag",
    "promotion_flag",
    "holiday_flag",
    "stockout_flag",
    "breakdown_flag",
    "marketing_flag",
    "event_names",
    "event_types",
]


def add_event_features(demand: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Add event-window features to each cleaned demand row."""
    demand_working = _prepare_demand(demand)
    event_records = _prepare_event_records(events)

    feature_rows = [
        _build_features_for_row(row, event_records)
        for row in demand_working[["date", "sku_id"]].itertuples(index=False)
    ]
    features = pd.DataFrame(feature_rows, columns=EVENT_FEATURE_COLUMNS)

    enriched = pd.concat([demand_working.reset_index(drop=True), features], axis=1)
    enriched["date"] = enriched["date"].dt.strftime(DATE_FORMAT)
    return enriched


def _prepare_demand(demand: pd.DataFrame) -> pd.DataFrame:
    """Return demand with parsed dates and normalized SKU values."""
    prepared = demand.copy()
    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce")
    prepared["sku_id"] = prepared["sku_id"].astype(str).str.strip()
    return prepared


def _prepare_event_records(events: pd.DataFrame) -> list[dict[str, object]]:
    """Convert cleaned event rows into feature-ready dictionaries."""
    prepared = events.copy()
    prepared["event_start_date"] = pd.to_datetime(prepared["event_start_date"], errors="coerce")
    prepared["event_end_date"] = pd.to_datetime(prepared["event_end_date"], errors="coerce")

    if "before_window_days" not in prepared.columns:
        prepared["before_window_days"] = 0
    if "after_window_days" not in prepared.columns:
        prepared["after_window_days"] = 0

    prepared["before_window_days"] = pd.to_numeric(prepared["before_window_days"], errors="coerce").fillna(0)
    prepared["after_window_days"] = pd.to_numeric(prepared["after_window_days"], errors="coerce").fillna(0)

    records: list[dict[str, object]] = []
    for event in prepared.dropna(subset=["event_start_date", "event_end_date"]).itertuples(index=False):
        event_dict = event._asdict()
        start_date = event_dict["event_start_date"]
        end_date = event_dict["event_end_date"]
        before_days = int(event_dict["before_window_days"])
        after_days = int(event_dict["after_window_days"])

        event_dict["before_start_date"] = start_date - pd.Timedelta(days=before_days)
        event_dict["after_end_date"] = end_date + pd.Timedelta(days=after_days)
        event_dict["normalized_sku_id"] = _normalize_optional_sku(event_dict.get("sku_id"))
        event_dict["event_type"] = _normalize_event_type(event_dict.get("event_type"))
        event_dict["event_name"] = str(event_dict.get("event_name", "")).strip()
        records.append(event_dict)

    return records


def _build_features_for_row(row: object, event_records: list[dict[str, object]]) -> dict[str, object]:
    """Build all event features for one demand row."""
    matching_events = [
        event
        for event in event_records
        if _event_matches_row(row.date, row.sku_id, event)
    ]

    event_names = _unique_join(event["event_name"] for event in matching_events)
    event_types = _unique_join(event["event_type"] for event in matching_events)
    event_type_values = [str(event["event_type"]) for event in matching_events]

    return {
        "event_count": len(matching_events),
        "has_event": int(bool(matching_events)),
        "before_event_flag": int(any(_is_before_event(row.date, event) for event in matching_events)),
        "during_event_flag": int(any(_is_during_event(row.date, event) for event in matching_events)),
        "after_event_flag": int(any(_is_after_event(row.date, event) for event in matching_events)),
        "promotion_flag": int(_has_event_type(event_type_values, "promotion")),
        "holiday_flag": int(_has_event_type(event_type_values, "holiday")),
        "stockout_flag": int(_has_event_type(event_type_values, "stockout")),
        "breakdown_flag": int(_has_event_type(event_type_values, "breakdown")),
        "marketing_flag": int(_has_event_type(event_type_values, "marketing")),
        "event_names": event_names,
        "event_types": event_types,
    }


def _event_matches_row(row_date: pd.Timestamp, sku_id: str, event: dict[str, object]) -> bool:
    """Return True when an event applies to a demand row."""
    if pd.isna(row_date):
        return False
    if not _sku_matches(sku_id, event["normalized_sku_id"]):
        return False
    return event["before_start_date"] <= row_date <= event["after_end_date"]


def _sku_matches(sku_id: str, event_sku_id: str) -> bool:
    """Return True for global events or exact SKU-specific matches."""
    return event_sku_id == "" or sku_id == event_sku_id


def _is_before_event(row_date: pd.Timestamp, event: dict[str, object]) -> bool:
    """Return True when row date is in the pre-event window."""
    return event["before_start_date"] <= row_date < event["event_start_date"]


def _is_during_event(row_date: pd.Timestamp, event: dict[str, object]) -> bool:
    """Return True when row date is inside the event window."""
    return event["event_start_date"] <= row_date <= event["event_end_date"]


def _is_after_event(row_date: pd.Timestamp, event: dict[str, object]) -> bool:
    """Return True when row date is in the post-event window."""
    return event["event_end_date"] < row_date <= event["after_end_date"]


def _has_event_type(event_types: list[str], expected_type: str) -> bool:
    """Return True when any matched event type equals the expected type."""
    return any(event_type == expected_type for event_type in event_types)


def _normalize_optional_sku(value: object) -> str:
    """Normalize nullable SKU values without changing their case."""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_event_type(value: object) -> str:
    """Normalize nullable event type values for flag matching."""
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def _unique_join(values: object) -> str:
    """Join unique non-empty values while preserving first-seen order."""
    seen: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.append(text)
    return "; ".join(seen)
