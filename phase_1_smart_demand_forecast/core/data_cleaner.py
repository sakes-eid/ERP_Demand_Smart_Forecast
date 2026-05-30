"""Data cleaning, anomaly detection, and date gap checks."""

import pandas as pd

from config import DATE_FORMAT


def clean_products(products: pd.DataFrame) -> pd.DataFrame:
    """Normalize product text fields and date columns."""
    cleaned = products.copy()
    cleaned["sku_id"] = cleaned["sku_id"].astype(str).str.strip()
    cleaned["sku_name"] = cleaned["sku_name"].astype(str).str.strip()
    cleaned["category"] = cleaned["category"].astype(str).str.strip()
    cleaned["unit"] = cleaned["unit"].astype(str).str.strip().str.lower()
    cleaned["status"] = cleaned["status"].astype(str).str.strip().str.lower()

    for column in ("launch_date", "end_date"):
        if column in cleaned.columns:
            cleaned[column] = pd.to_datetime(cleaned[column], errors="coerce").dt.strftime(DATE_FORMAT)

    return cleaned.drop_duplicates(subset=["sku_id"]).reset_index(drop=True)


def clean_demand_data(demand: pd.DataFrame) -> pd.DataFrame:
    """Clean demand records and flag invalid demand quantities."""
    cleaned = demand.copy()
    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce")
    cleaned["sku_id"] = cleaned["sku_id"].astype(str).str.strip()
    cleaned["quantity_demanded"] = pd.to_numeric(cleaned["quantity_demanded"], errors="coerce")
    cleaned["is_invalid_quantity"] = cleaned["quantity_demanded"].isna() | (cleaned["quantity_demanded"] < 0)

    if "sales_value" in cleaned.columns:
        cleaned["sales_value"] = pd.to_numeric(cleaned["sales_value"], errors="coerce")

    cleaned = cleaned.dropna(subset=["date", "sku_id"])
    cleaned = cleaned.sort_values(["sku_id", "date"]).reset_index(drop=True)
    cleaned["date"] = cleaned["date"].dt.strftime(DATE_FORMAT)
    return cleaned


def detect_anomalies(demand: pd.DataFrame) -> pd.DataFrame:
    """Detect simple demand anomalies without using forecasting models."""
    cleaned = demand.copy()
    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce")
    cleaned["quantity_demanded"] = pd.to_numeric(cleaned["quantity_demanded"], errors="coerce")

    stats = cleaned.groupby("sku_id")["quantity_demanded"].agg(["mean", "std"]).reset_index()
    flagged = cleaned.merge(stats, on="sku_id", how="left")
    flagged["std"] = flagged["std"].fillna(0)
    flagged["z_score"] = 0.0

    mask = flagged["std"] > 0
    flagged.loc[mask, "z_score"] = (
        (flagged.loc[mask, "quantity_demanded"] - flagged.loc[mask, "mean"]) / flagged.loc[mask, "std"]
    )
    flagged["anomaly_reason"] = ""
    flagged.loc[flagged["quantity_demanded"].isna(), "anomaly_reason"] = "missing_quantity"
    flagged.loc[flagged["quantity_demanded"] < 0, "anomaly_reason"] = "negative_quantity"
    flagged.loc[flagged["z_score"].abs() >= 3, "anomaly_reason"] = "statistical_outlier"

    anomalies = flagged[flagged["anomaly_reason"] != ""].copy()
    anomalies["date"] = anomalies["date"].dt.strftime(DATE_FORMAT)
    return anomalies[["date", "sku_id", "quantity_demanded", "anomaly_reason", "z_score"]].reset_index(drop=True)


def detect_missing_dates(demand: pd.DataFrame) -> pd.DataFrame:
    """Find missing daily dates for each SKU in the demand history."""
    working = demand.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working = working.dropna(subset=["date", "sku_id"])

    missing_records: list[dict[str, str]] = []
    for sku_id, sku_demand in working.groupby("sku_id"):
        observed_dates = set(sku_demand["date"])
        expected_dates = pd.date_range(sku_demand["date"].min(), sku_demand["date"].max(), freq="D")
        for missing_date in expected_dates:
            if missing_date not in observed_dates:
                missing_records.append({"sku_id": sku_id, "missing_date": missing_date.strftime(DATE_FORMAT)})

    return pd.DataFrame(missing_records, columns=["sku_id", "missing_date"])


def clean_events(events: pd.DataFrame) -> pd.DataFrame:
    """Normalize event calendar dates, numeric windows, and labels."""
    cleaned = events.copy()
    cleaned["event_name"] = cleaned["event_name"].astype(str).str.strip()
    cleaned["event_type"] = cleaned["event_type"].astype(str).str.strip().str.lower()
    cleaned["event_start_date"] = pd.to_datetime(cleaned["event_start_date"], errors="coerce")
    cleaned["event_end_date"] = pd.to_datetime(cleaned["event_end_date"], errors="coerce")

    for column in ("before_window_days", "after_window_days"):
        if column in cleaned.columns:
            cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce").fillna(0).astype(int)

    if "event_intensity" in cleaned.columns:
        cleaned["event_intensity"] = pd.to_numeric(cleaned["event_intensity"], errors="coerce")

    cleaned = cleaned.dropna(subset=["event_start_date", "event_end_date"])
    cleaned = cleaned[cleaned["event_end_date"] >= cleaned["event_start_date"]]
    cleaned["event_start_date"] = cleaned["event_start_date"].dt.strftime(DATE_FORMAT)
    cleaned["event_end_date"] = cleaned["event_end_date"].dt.strftime(DATE_FORMAT)
    return cleaned.reset_index(drop=True)

