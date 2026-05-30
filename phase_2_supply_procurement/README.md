# ERP-like Planning System - Phase 2 Supply & Procurement Module

## Objective

Phase 2 builds the supply and procurement intelligence layer for the ERP-like planning system. It connects supplier performance, supplier-SKU options, cost, risk, feasibility, trend status, and Phase 1 demand intelligence so later phases can make inventory and planning decisions from a richer procurement foundation.

## What Phase 2 Does

- Generates or loads supplier data.
- Generates or loads supplier-SKU options.
- Generates or loads purchase orders and receipts.
- Cleans and validates supply data.
- Calculates supplier performance KPIs.
- Handles suppliers with no or limited history.
- Calculates procurement risk.
- Integrates Phase 1 demand context when available.
- Calculates demand-adjusted procurement risk.
- Estimates procurement cost breakdowns.
- Checks supplier feasibility using MOQ, batch size, yield, supplier status, and a forecast reference quantity.
- Calculates a temporary final feasible order quantity.
- Detects supplier trends using recent vs baseline windows.
- Flags improving, healthy, mixed, watchlist, and insufficient-data suppliers.
- Selects recommended and backup suppliers.
- Flags supplier review requirements.
- Outputs procurement recommendations.
- Provides a Streamlit dashboard for Phase 2 supply and procurement analysis.
- Shows supplier trend time-series charts from purchase order and receipt history.

## What Phase 2 Does Not Do Yet

- Reorder point.
- Safety stock.
- EOQ.
- Final inventory policy.
- Production planning.
- Digital twin simulation.
- Financial optimization decision engine.

## Main Files

- `main.py` runs the Phase 2 pipeline.
- `app.py` runs the Phase 2 Streamlit dashboard.
- `config.py` stores paths, thresholds, weights, trend windows, and evidence penalties.
- `core/supply_generator.py` creates realistic demo data.
- `core/supply_cleaner.py` validates supply data.
- `core/supplier_performance.py` calculates supplier KPIs.
- `core/supplier_trends.py` detects supplier performance trends.
- `core/phase1_integration.py` loads Phase 1 demand intelligence.
- `core/procurement_scoring.py` scores suppliers and creates recommendations.

## Input Files

- `data/suppliers.csv`
- `data/supplier_sku.csv`
- `data/purchase_orders.csv`
- `data/receipts.csv`

## Output Files

- `outputs/supplier_trends.csv`
- `outputs/supplier_performance.csv`
- `outputs/supplier_sku_scores.csv`
- `outputs/procurement_recommendations.csv`

## Phase 1 Integration

Phase 2 reads Phase 1 demand intelligence outputs when available from:

```text
C:\Users\iTECH\OneDrive - Beirut Arab University\Desktop\apps i made\SC project\phase 1\outputs
```

Phase 2 can still run if Phase 1 outputs are missing. In that case, it uses fallback values for demand behavior, forecast confidence, forecast risk, and forecast quantities.

## How To Run

Run the backend pipeline:

```powershell
cd "C:\Users\iTECH\OneDrive - Beirut Arab University\Desktop\apps i made\SC project\phase 2"
python main.py
```

Run the dashboard:

```powershell
streamlit run app.py
```

## Dashboard

The Phase 2 dashboard reads existing CSV files from `outputs/` and purchase/receipt history from `data/`. It does not modify backend calculations.

Dashboard pages:

- Overview
- Supplier Performance
- Supplier Trends
- Supplier-SKU Options
- Procurement Recommendations
- Risk & Cost Analysis
- Feasibility Review
- Pipeline Outputs

The Supplier Trends page includes weekly or monthly time-series charts for:

- reliability score
- average delay days
- yield rate and defect rate
- partial delivery rate
- average unit cost and cost per usable unit

If required files are missing, the dashboard shows warnings and asks the user to run `python main.py`.

## How To Regenerate Demo Data

The generator does not blindly overwrite real or user-edited CSV files.

To force a fresh demo dataset:

1. Close any CSV files open in Excel, preview panes, or other tools.
2. Delete the CSV files inside `data/`.
3. Run `python main.py` again.

## Output Contract For Later Phases

Phase 3 Inventory Planning should consume these fields from `procurement_recommendations.csv`:

- `sku_id`
- `recommended_supplier_id`
- `backup_supplier_id`
- `expected_lead_time_days`
- `expected_arrival_date`
- `unit_cost`
- `moq`
- `batch_size`
- `expected_yield_rate`
- `final_feasible_order_quantity`
- `estimated_total_procurement_cost`
- `demand_adjusted_procurement_risk_score`
- `demand_adjusted_procurement_risk_class`
- `recommended_supplier_feasible`
- `recommended_supplier_requires_review`
- `split_sourcing_recommendation`
- `recommended_primary_share`
- `recommended_backup_share`

Phase 3 should also consume `supplier_sku_scores.csv` for:

- all supplier options per SKU
- total cost breakdown
- feasibility warnings
- trend status
- supplier evidence and review fields

## Important Design Notes

- Thresholds are configurable so future UI controls can expose them safely.
- Supplier scoring is not based on unit cost alone.
- Supplier recommendations balance cost, reliability, lead time, quality, feasibility, trend status, and demand-adjusted risk.
- The Streamlit app is read-only and modular so it can later be merged into one unified ERP-like dashboard.
- The final decision engine in later phases should minimize total cost per SKU across supply, inventory, production, delay, quality, and other cost factors.

## Requirements

Phase 2 uses:

- `pandas`
- `numpy`
- `streamlit`
- `plotly`
