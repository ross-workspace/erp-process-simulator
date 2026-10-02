# ERP Process Analyzer

A local-first process-mining application for prepared Order-to-Cash event logs. Load a synthetic demo or a CSV to see observed order paths, investigate elapsed time between events, inspect rework, and explore a transparent timing scenario.

This is a portfolio MVP with useful diagnostic behaviour. It does not connect to an ERP, infer queue time from a single timestamp, or predict money or staffing savings.

## Try it locally

Python 3.12 or newer is required.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/streamlit run app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`. The app starts with a synthetic 10,000-order demo. No account, API key, database, or network connection is needed after installation.

To run the tests:

```bash
.venv/bin/python -m pytest
```

To regenerate the committed demos from the fixed seed:

```bash
.venv/bin/python -m erp_process_analyzer.generator --cases 10000 --seed 42 --profile messy --output data/demo_messy.csv
.venv/bin/python -m erp_process_analyzer.generator --cases 2000 --seed 42 --profile clean --output data/demo_clean.csv
.venv/bin/python -m erp_process_analyzer.generator --cases 3000 --seed 42 --profile warehouse --output data/demo_warehouse.csv
```

## Docker

```bash
docker build -t erp-process-analyzer .
docker run --rm -p 8501:8501 erp-process-analyzer
```

## Use your own event log

Upload a UTF-8 CSV with one row per event and these required columns:

```csv
case_id,activity,timestamp,resource
ORD-001,Order Created,2026-01-03T08:12:00Z,sales_01
ORD-001,Order Approved,2026-01-03T09:42:00Z,manager_01
ORD-001,Payment Received,2026-01-19T12:00:00Z,system
```

Optional columns are `resource`, `department`, `cost`, `order_value`, and `event_order`. A case is one order. The app accepts ISO 8601 timestamps with offsets; for timestamps without offsets, select their timezone in the sidebar. See [the data dictionary](docs/DATA_DICTIONARY.md) for validation and calculation rules. The initial version expects these column names; it does not map arbitrary ERP exports automatically.

## How the numbers are made

- Events are ordered within each case by timestamp, optional `event_order`, then source CSV row. Tied timestamps without a unique order are flagged.
- The map is a directly-follows graph: `A → B` means an A event was followed immediately by B in the same case. Edge hover shows distinct cases and total occurrences separately.
- A completed order reaches its first `Payment Received`. Completed cycle time runs from its first event to that payment. Open cases stay visible but are excluded from completed cycle-time and scenario aggregates.
- An edge gap is elapsed calendar time between the two events. Median, P90, and total elapsed case-hours come from observed gap values. Long gaps are investigation candidates, not proven staff bottlenecks.
- A variant is a full event sequence. Approval rework means `Order Approved`, then `Order Edited`, then another `Order Approved` in the same case.
- The scenario subtracts a chosen percentage of every matching edge gap from each completed case's observed cycle time, then recomputes aggregate mean and median. It assumes later events shift earlier by the same amount. It does not model capacity, queues, concurrent branches, payment terms, or behaviour changes. Case-hours are elapsed time across orders, not labour hours or financial savings.

Events after the first payment are flagged, visible in case details, and excluded from process and scenario calculations. Demo data is synthetic throughout. Uploaded CSV data is analyzed in the local Streamlit session; if you host this app on a server, uploaded data will be processed there.

## Project layout

```text
app.py                         Streamlit views and interactions
src/erp_process_analyzer/
  importer.py                  CSV validation and normalization
  analyzer.py                  case, edge, variant, and rework metrics
  scenario.py                  historical timing calculation
  generator.py                 deterministic synthetic demo data
  visuals.py                   interactive process map
tests/                         golden fixture and core checks
data/                          synthetic demo CSVs
docs/                          data contract and dashboard preview
```

## Deliberate limits

V1 is for a single order case ID and a prepared event log. Real Order-to-Cash systems can have multiple deliveries, invoices, payments, and parallel paths per order. Mapping these correctly requires an explicit data model and is future work. There is no SAP or Dynamics connector, authentication, database, AI ranking, BPMN editor, or claim of causal impact.
