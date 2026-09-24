# SupplySphere Phases 15–17

## Phase 15 — Real-Time Simulation
Redis Streams is the production broker contract, with a deterministic in-memory stream for local development/tests. Events: new order, inventory update, shipment dispatch, shipment delay, supplier delay, warehouse capacity change, and stockout warning. The simulator exposes start/pause/stop/tick and state metrics.

## Phase 16 — MLOps & Monitoring
The model registry records model/version/dataset/features/parameters/metrics/artifact/timestamp and supports candidate/production/archive stages. MLflow and Evidently adapters are optional runtime integrations so local tests remain deterministic when those services/packages are unavailable. Monitoring includes feature and prediction drift.

## Phase 17 — Production Hardening & Final Audit
The hardening audit checks required Phase 15–17 files and Python compilation. The complete test suite is the release gate. Runtime PostgreSQL, Redis, MLflow and Evidently service checks remain environment-dependent and are reported rather than fabricated as passing.
