# SupplySphere — Supply Chain Intelligence Platform

Schema-Aware Dataset Analyzer + Ask Your Dataset, integrated alongside the Olist Supply Chain Control Tower.

## Architecture Overview

SupplySphere contains two independent systems:

### 1. Olist Control Tower (Phases 0–17)

PostgreSQL-backed supply chain intelligence platform with:
- **Phases 0–5:** Data ingestion, PostgreSQL schemas, analytics, synthetic operational layer, demand forecasting
- **Phases 6–10:** Stockout prediction, supplier intelligence, warehouse optimization, delivery risk, procurement optimization
- **Phases 11–14:** Geospatial intelligence, FastAPI APIs, React control-tower UI, global search, shipment tracking
- **Phases 15–17:** Real-time simulation, MLOps & monitoring, production hardening

### 2. Dataset Analyzer (Phases 18–20)

Schema-aware, generic dataset analysis system:
- Secure upload of CSV/XLSX files
- Deterministic profiling and schema intelligence
- Dynamic capability detection based on uploaded data
- KPI, analytics, trends, domain, geospatial, route, anomaly analysis
- Ask Your Dataset (deterministic query engine)
- Evidence-based insights and comprehensive reports
- Temporary filesystem storage with TTL expiration

**Dataset Analyzer is NOT Olist.** It is a separate, generic system that analyzes any uploaded dataset. It does not assume Olist data, Brazilian geography, or fixed product/supplier/warehouse names.

## Quick Start

### Backend

```bash
cd supply-sphere-phase11/supply-sphere
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows
# source .venv/bin/activate       # Linux/Mac
pip install -r requirements.txt
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # Development server on http://localhost:5173
npm run build        # Production build to dist/
```

### Tests

```bash
python -m pytest -v
```

## API Endpoints

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | System health check |

### Dataset Analyzer

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/dataset-analyzer/sessions` | Upload dataset (CSV/XLSX) |
| GET | `/api/dataset-analyzer/sessions` | List all sessions |
| GET | `/api/dataset-analyzer/sessions/{id}` | Get session metadata |
| DELETE | `/api/dataset-analyzer/sessions/{id}` | Delete dataset |
| GET | `/api/dataset-analyzer/sessions/{id}/profile` | Dataset profiling |
| GET | `/api/dataset-analyzer/sessions/{id}/schema` | Schema intelligence |
| GET | `/api/dataset-analyzer/sessions/{id}/capabilities` | Capability detection |
| GET | `/api/dataset-analyzer/sessions/{id}/kpis` | Key performance indicators |
| GET | `/api/dataset-analyzer/sessions/{id}/analytics` | Generic analytics |
| GET | `/api/dataset-analyzer/sessions/{id}/trends` | Trend analysis |
| GET | `/api/dataset-analyzer/sessions/{id}/domain` | Domain analysis |
| GET | `/api/dataset-analyzer/sessions/{id}/geospatial` | Geospatial analysis |
| GET | `/api/dataset-analyzer/sessions/{id}/routes` | Route analysis |
| GET | `/api/dataset-analyzer/sessions/{id}/anomalies` | Anomaly detection |
| POST | `/api/dataset-analyzer/sessions/{id}/ask` | Ask Your Dataset |
| GET | `/api/dataset-analyzer/sessions/{id}/insights` | Evidence-based insights |
| GET | `/api/dataset-analyzer/sessions/{id}/report` | Comprehensive report |

### Olist Control Tower

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/summary` | Dashboard summary |
| GET | `/api/inventory` | Inventory data |
| GET | `/api/suppliers` | Supplier data |
| GET | `/api/warehouses` | Warehouse data |
| GET | `/api/geospatial/warehouses` | Geospatial warehouse data |
| GET | `/api/geospatial/routes` | Geospatial route data |
| GET | `/api/logistics/delivery-risk` | Delivery risk data |
| GET | `/api/demand/forecast` | Demand forecast |
| POST | `/api/optimization/run` | Supply optimization |
| POST | `/api/realtime/start` | Start real-time simulation |
| POST | `/api/realtime/tick` | Tick simulation |
| GET | `/api/realtime/status` | Simulation status |
| GET | `/api/mlops/health` | MLOps health |

## Dataset

The Olist Brazilian E-Commerce Public Dataset is used for the Control Tower system. Expected raw files in `data/raw/`:

1. `olist_customers_dataset.csv`
2. `olist_geolocation_dataset.csv`
3. `olist_order_items_dataset.csv`
4. `olist_order_payments_dataset.csv`
5. `olist_order_reviews_dataset.csv`
6. `olist_orders_dataset.csv`
7. `olist_products_dataset.csv`
8. `olist_sellers_dataset.csv`
9. `product_category_name_translation.csv`

## Project Structure

```
supply-sphere/
├── api/                    # FastAPI application and routes
├── configs/                # Application settings
├── data/                   # Dataset storage (raw, staging, processed)
├── docs/                   # Project documentation
├── frontend/               # React + TypeScript + Vite frontend
├── geospatial/             # Geospatial services
├── ml/                     # Machine learning models and training
├── mlops/                  # MLOps registry, monitoring, hardening
├── notebooks/              # Jupyter notebooks
├── realtime/               # Real-time simulation
├── scripts/                # Pipeline and utility scripts
├── sql/                    # PostgreSQL schemas and views
├── src/                    # Source code
│   ├── dataset_analyzer/   # Dataset Analyzer module
│   ├── ingestion/          # Data ingestion
│   ├── analytics/          # Analytics metrics
│   ├── data_quality/       # Data quality validators
│   └── synthetic/          # Synthetic data generation
└── tests/                  # Test suite
```

## Environment

See `.env.example` for configuration. Key variables:

- `DATABASE_URL` — PostgreSQL connection string (for Olist Control Tower)
- `APP_ENV` — Application environment
- `LOG_LEVEL` — Logging level

## Verification

```bash
python -m pytest -v          # Run full test suite
cd frontend && npm run build # Frontend production build
```

## Known Limitations

1. **XLS format:** Not supported (xlwt deprecated). Use XLSX.
2. **Browser E2E:** Not verified in automated testing environment.
3. **OR-Tools solver:** Optimization test may stall in Python 3.14.5 environment.
4. **Ask Your Dataset:** Uses deterministic regex-based pattern matching. Not a general-purpose NL reasoning engine.
5. **Dataset Analyzer reads:** Individual compute engines may independently read uploaded files.
6. **Deprecation warnings:** `datetime.utcnow()` and `numpy.timedelta` warnings present (cosmetic).

## Documentation

- `docs/ARCHITECTURE.md` — Phase 0–5 architecture
- `docs/PHASE11_14.md` — Geospatial, APIs, React UI, search, tracking
- `docs/PHASE15_17.md` — Real-time simulation, MLOps, hardening
- `docs/DATASET_ANALYZER.md` — Dataset Analyzer complete documentation
- `FINAL_AUDIT.md` — Final audit results (STEP 21/22)
