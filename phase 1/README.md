# Phase 1 - Demand Planning

Phase 1 provides demand intelligence for the integrated planning system. It prepares demand and event data, benchmarks forecasting models per SKU, generates future forecast horizons, and publishes a downstream planning context for Phase 2 and Phase 3.

Phase 1 outputs are advisory planning inputs. They do not create orders, change inventory policies, select suppliers, or execute procurement actions.

## Current Capabilities

- Cleans product, demand, and event data.
- Builds demand profiles by SKU.
- Benchmarks forecasting models and selects a champion model per SKU.
- Generates true future 7, 14, 30, 60, and 90 day forecast horizons.
- Produces P10/P50/P90 uncertainty intervals.
- Calculates forecast confidence, bias, urgency, seasonality, and event context.
- Detects heuristic stockout-censored demand signals.
- Persists supported champion model artifacts where safe.
- Provides a Streamlit dashboard through `app.py`.
- Publishes the downstream demand planning bridge:

```text
phase 1/outputs/phase1_demand_planning_context.csv
```

## Main Outputs

| Output | Purpose |
| --- | --- |
| `outputs/products_cleaned.csv` | Cleaned product master data |
| `outputs/demand_history_cleaned.csv` | Cleaned historical demand |
| `outputs/demand_profile.csv` | SKU-level demand profile |
| `outputs/demand_features.csv` | Forecasting feature table |
| `outputs/forecast_results.csv` | Backtest-style forecast results |
| `outputs/future_forecast_results.csv` | One future forecast row per SKU per future date |
| `outputs/model_performance.csv` | Model evaluation metrics |
| `outputs/model_registry.csv` | Champion model registry |
| `outputs/phase1_forecast_kpis.csv` | Essential forecast KPI summary by SKU |
| `outputs/phase1_demand_planning_context.csv` | Official Phase 1 bridge for downstream planning |
| `outputs/models/` | Persisted supported champion model artifacts |

## Forecast KPIs

Phase 1 now calculates a compact KPI output in `outputs/phase1_forecast_kpis.csv` and merges the manager-useful fields into `outputs/phase1_demand_planning_context.csv`.

Added KPIs:

- Forecast value added against a simple comparable baseline.
- 7-day and 30-day backtest WAPE where actual historical test data exists.
- 90-day horizon accuracy availability flag; the current comparable backtest window is shorter than 90 days, so 90-day WAPE is not fabricated.
- Prediction interval coverage for P10/P90 calibration.
- Forecast stability status, calculated from forecast quantity vectors across distinct future-forecast snapshots aligned by SKU and target date.

Forecast stability does not use WAPE, MAE, MASE, or any other error metric. If no distinct comparable prior future-forecast snapshot exists, the KPI is marked `UNAVAILABLE_NO_COMPARABLE_PRIOR_RUN`.

The Streamlit dashboard shows these KPIs in the Overview, Forecasting Results, Model Performance, and Demand Planning Context sections.

## Demand Planning Context

`phase1_demand_planning_context.csv` is the official Phase 1 bridge consumed by Phase 2 and Phase 3. It includes:

- SKU identifiers and category context.
- Demand profile, variability, intermittency, and spikiness fields.
- 7, 14, 30, 60, and 90 day future demand totals.
- 30-day P10/P50/P90 uncertainty fields.
- Champion model, confidence, bias direction, and risk flags.
- Seasonality, upcoming events, and event uplift context.
- Heuristic stockout-censored demand indicators.
- Demand urgency, pressure, data quality, warning codes, and downstream notes.

## Known Limitations

- Advanced champion models may use transparent statistical fallback for future forecasts when trained model objects or future features cannot be reused safely.
- Stockout-censored demand detection is heuristic.
- Confirmed lost-sales correction using Phase 2 and Phase 3 operational evidence is future work.
- Short histories may limit seasonality quality.
- Forecast stability requires a prior comparable future-forecast snapshot from a distinct planning run.
- 90-day backtest WAPE is unavailable when the historical test window is shorter than 90 days.
- Phase 1 does not own inventory, supplier, production, policy, warehouse, or execution decisions.

## How To Run

From the Phase 1 folder:

```bash
python main.py
python validate_phase1_demand_context.py
python -m compileall .
```

Launch the dashboard:

```bash
streamlit run app.py
```

From outside the Phase 1 folder:

```bash
streamlit run "C:\Users\iTECH\OneDrive - Beirut Arab University\Desktop\apps i made\SC project\phase 1\app.py"
```

Do not launch Streamlit from `C:\Users\iTECH\OneDrive\streamlit_app.py`; that is not the Phase 1 app path.

## Integration Role

Phase 1 feeds Phase 2 and Phase 3 with demand intelligence. Phase 2 uses the demand context for procurement risk and supplier planning. Phase 3 uses demand context as part of inventory planning and manager-facing decision support. Phase 1 remains an advisory context provider and does not trigger orders or policy changes.
