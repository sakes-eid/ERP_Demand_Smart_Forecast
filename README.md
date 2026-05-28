# ERP-like Planning System - Phase 1 Demand Intelligence Module

## Objective

Phase 1 builds the demand intelligence foundation for a future ERP-like planning and simulation system. It prepares clean demand data, creates forecasting-ready features, benchmarks forecasting models, and exposes the results through a Streamlit dashboard.

## What Phase 1 Does

- Loads product, demand, and event data from CSV files.
- Cleans and validates product, demand, and event records.
- Detects demand anomalies and missing dates.
- Adds event-aware features for holidays, promotions, and event windows.
- Profiles demand behavior per SKU.
- Creates model-ready forecasting features.
- Trains multiple forecasting models per SKU.
- Evaluates models fairly using a shared final test window.
- Uses robust metrics for intermittent and low-demand SKUs.
- Selects a champion model per SKU.
- Estimates P10/P50/P90 prediction intervals.
- Creates forecast confidence and risk scores.
- Provides a Streamlit dashboard for Phase 1 demand intelligence.

## What Phase 1 Does Not Do Yet

- Inventory optimization
- Reorder point calculation
- Safety stock calculation
- Supplier selection
- Production planning
- Digital twin simulation
- Finance optimization
- Reinforcement learning

## Main Files

- `SC project/phase 1/main.py` runs the end-to-end Phase 1 pipeline.
- `app.py` runs the dashboard from the workspace root.
- `SC project/phase 1/app.py` contains the Streamlit dashboard implementation.
- `SC project/phase 1/config.py` stores paths and model selection weights.
- `SC project/phase 1/core/` contains the modular pipeline logic.
- `SC project/phase 1/data/` contains input CSV files.
- `SC project/phase 1/outputs/` contains generated pipeline outputs.

## Main Outputs

- `products_cleaned.csv` or `products_clean.csv`
- `demand_history_cleaned.csv` or `demand_history_clean.csv`
- `demand_anomalies.csv`
- `missing_dates.csv`
- `demand_with_event_features.csv`
- `demand_profile.csv`
- `demand_features.csv`
- `forecast_results.csv`
- `model_performance.csv`
- `model_registry.csv`

## How To Run

Run the pipeline:

```bash
cd "SC project/phase 1"
python main.py
```

Run the dashboard from the workspace root:

```bash
streamlit run app.py
```

## Phase 2 Integration

The future inventory module will consume:

- Champion forecasts
- P10/P50/P90 forecast values
- Forecast confidence scores
- Forecast risk levels
- SKU demand profiles
- Model registry outputs

## Notes

- Raw input data is preserved separately from cleaned outputs.
- Anomalies are flagged and surfaced; they are not blindly deleted.
- Model selection is performed per SKU rather than using one model for all demand patterns.

