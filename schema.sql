-- DataPulse PostgreSQL Database Schema & DDL Script
-- Target Database: PostgreSQL 16+ (Supabase / Managed PostgreSQL)

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Operational Metrics Relational Table
CREATE TABLE IF NOT EXISTS operational_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_service VARCHAR(100) NOT NULL,       -- e.g., 'auth-service', 'payment-gateway', 'order-router', 'search-indexer', 'database-pool'
    metric_name VARCHAR(100) NOT NULL,          -- e.g., 'p99_latency_ms', 'cpu_utilization_pct', 'error_rate', 'memory_usage_mb'
    metric_value DOUBLE PRECISION NOT NULL,
    threshold_limit DOUBLE PRECISION NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'HEALTHY', -- 'HEALTHY', 'WARNING', 'CRITICAL'
    payload JSONB DEFAULT '{}'::jsonb,          -- Context metadata: { region, host_id, trace_id }
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Composite & Filtered Time-Series Index Layout
CREATE INDEX IF NOT EXISTS idx_metrics_lookup 
    ON operational_metrics (source_service, metric_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_metrics_status 
    ON operational_metrics (status) 
    WHERE status IN ('WARNING', 'CRITICAL');

-- 4. Initial Seed Data (Optional for manual database verification)
INSERT INTO operational_metrics (source_service, metric_name, metric_value, threshold_limit, status, payload)
VALUES 
    ('auth-service', 'p99_latency_ms', 125.4, 200.0, 'HEALTHY', '{"region": "us-east-1", "host_id": "node-101"}'),
    ('payment-gateway', 'p99_latency_ms', 450.8, 300.0, 'CRITICAL', '{"region": "us-west-2", "host_id": "node-102"}'),
    ('order-router', 'cpu_utilization_pct', 82.5, 80.0, 'WARNING', '{"region": "eu-central-1", "host_id": "node-103"}'),
    ('search-indexer', 'memory_usage_mb', 1150.0, 2048.0, 'HEALTHY', '{"region": "us-east-1", "host_id": "node-104"}'),
    ('database-pool', 'error_rate', 0.2, 5.0, 'HEALTHY', '{"region": "us-east-1", "host_id": "node-105"}');
