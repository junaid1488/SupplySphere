# SupplySphere — Phases 11–14

## Phase 11 — Geospatial Intelligence
- Leaflet map components in the React client.
- OpenStreetMap tile layer with attribution.
- Warehouse, customer, seller and route API layers.
- Haversine distance calculation and deterministic 12-city warehouse network.

## Phase 12 — FastAPI Backend
The API exposes health, dashboard, demand, inventory, stockout risk, suppliers, warehouses, delivery risk, geospatial, search, events, shipment detail and optimization contracts. List endpoints support `limit`/`offset`; risk/inventory filtering is supported where applicable.

## Phase 13 — React Control Tower
The React + TypeScript + Vite client provides navigation for dashboard, demand, inventory, warehouses, suppliers, logistics, geospatial, optimization, AI insights, reports and settings; it connects to the FastAPI contracts and includes loading/error states, responsive layout, tabular drill-down data and the network map.

## Phase 14 — Global Search & Shipment Tracking
Global search covers the operational entity identifiers exposed by the backend. Shipment detail is available through `/api/shipments/{shipment_id}` and returns risk/detail data plus the event timeline from the simulated shipment-event layer.

## Verification scope
Python compilation, API smoke tests and source-contract tests are run in the repository. A real browser build requires installing the frontend dependencies and running `npm run build`; that build is environment-dependent when package installation is unavailable.
