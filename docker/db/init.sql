-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Services table
CREATE TABLE IF NOT EXISTS services (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             TEXT NOT NULL,
    type             TEXT NOT NULL,          -- 'http' or 'tcp'
    target           TEXT,
    interval_s       INT NOT NULL DEFAULT 60,
    expected_status  INT,
    enabled          BOOLEAN NOT NULL DEFAULT TRUE,
    current_state    TEXT NOT NULL DEFAULT 'UNKNOWN',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_id         TEXT UNIQUE   -- null for blackbox services; set for push/agent services
);

-- Metrics hypertable
CREATE TABLE IF NOT EXISTS metrics (
    time             TIMESTAMPTZ NOT NULL,
    service_id       UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    metric           TEXT NOT NULL,
    value            DOUBLE PRECISION NOT NULL,
    labels           JSONB
);

SELECT create_hypertable('metrics', 'time', if_not_exists => TRUE);

-- Helpful indexes for time-series lookups by service
CREATE INDEX IF NOT EXISTS idx_metrics_service_time
    ON metrics (service_id, metric, time DESC);

-- Agent API keys (hashed for security)
CREATE TABLE IF NOT EXISTS agent_keys (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id    TEXT        NOT NULL UNIQUE,
    key_hash    TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at  TIMESTAMPTZ
);

-- Development seed: plaintext key = "lookout-dev-key"
-- key_hash = sha256("lookout-dev-key")
INSERT INTO agent_keys (agent_id, key_hash) VALUES (
    'dev-agent-01',
    encode(sha256('lookout-dev-key'::bytea), 'hex')
) ON CONFLICT (agent_id) DO NOTHING;
