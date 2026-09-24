-- Phase 6-10 analytical contracts. Runtime loading is performed by the phase runner.
CREATE TABLE IF NOT EXISTS analytics.stockout_predictions (
    warehouse_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    stockout_probability DOUBLE PRECISION NOT NULL CHECK (stockout_probability BETWEEN 0 AND 1),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('Low','Medium','High','Critical')),
    expected_stockout_date DATE
);
CREATE INDEX IF NOT EXISTS ix_stockout_predictions_risk ON analytics.stockout_predictions (risk_level, stockout_probability DESC);

CREATE TABLE IF NOT EXISTS analytics.supplier_intelligence (
    supplier_id TEXT PRIMARY KEY,
    supplier_score DOUBLE PRECISION NOT NULL CHECK (supplier_score BETWEEN 0 AND 100),
    risk_score DOUBLE PRECISION NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    risk_level TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics.warehouse_metrics (
    warehouse_id TEXT PRIMARY KEY,
    inventory_units BIGINT NOT NULL,
    reserved_units BIGINT NOT NULL,
    utilization DOUBLE PRECISION NOT NULL CHECK (utilization BETWEEN 0 AND 1),
    operating_cost DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics.delivery_risk_predictions (
    order_id TEXT PRIMARY KEY,
    late_delivery_probability DOUBLE PRECISION NOT NULL CHECK (late_delivery_probability BETWEEN 0 AND 1),
    risk_level TEXT NOT NULL,
    expected_delivery_date TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics.optimization_runs (
    run_id BIGSERIAL PRIMARY KEY,
    solver TEXT NOT NULL,
    current_cost DOUBLE PRECISION NOT NULL,
    optimized_cost DOUBLE PRECISION NOT NULL,
    estimated_savings DOUBLE PRECISION NOT NULL,
    service_level DOUBLE PRECISION NOT NULL CHECK (service_level BETWEEN 0 AND 1),
    stockout_risk DOUBLE PRECISION NOT NULL CHECK (stockout_risk BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
