# Lookout

> Self-hosted infrastructure monitoring and alerting platform with anti-flapping protection, real-time dashboards, and graceful agent management.

Lookout is a production-ready monitoring platform designed for teams who need instant visibility into their infrastructure without complex configuration or vendor lock-in. Built with a clean hexagonal architecture and developed over 5 sprints, it provides HTTP/TCP blackbox probing, push-based agent metrics collection, intelligent alerting with anti-flapping, and a real-time WebSocket dashboard.

**Quick Links:**
- **Demo Dashboard:** http://localhost (after installation)
- **API Documentation:** http://localhost/api/v1 (OpenAPI spec at `/docs`)
- **Real-time Stream:** `ws://localhost/ws/v1/dashboard`

---

## Overview

### What Lookout Does

1. **Monitors Services** — Continuously probe HTTP/TCP endpoints on a schedule, track latency and availability
2. **Collects Agent Metrics** — Remote agents (Linux, Docker) push system/container metrics securely via Bearer tokens
3. **Detects Anomalies** — Anti-flapping state machine prevents alert fatigue: UNKNOWN → WARNING → CRITICAL → RESOLVED with sliding window thresholds
4. **Sends Alerts** — Discord webhooks, extensible notifier ports (email/Slack-ready)
5. **Streams Live Updates** — WebSocket dashboard auto-connects and shows state changes in real time
6. **Retains Historical Data** — TimescaleDB with 7-day hypertable retention for cost control
7. **Graceful Agent Shutdown** — Agents trap SIGTERM/SIGINT and finish in-flight collection before exit

### Why Lookout

- **Self-hosted** — Full control over data and deployment; no cloud dependencies
- **Clean Architecture** — Hexagonal design with ports & adapters; business logic is independent of frameworks
- **Production-Ready** — Bearer token auth with SHA-256 hashing, transaction-level concurrency (`SELECT FOR UPDATE`), graceful shutdown
- **Low Friction** — One-line installer for Docker Compose; pip install for agents
- **No Vendor Lock-in** — Portable schema; can migrate data using standard PostgreSQL/TimescaleDB tools

### Key Features Across 5 Sprints

| Sprint | Feature |
|--------|---------|
| **1** | FastAPI REST API, HTTP/TCP blackbox probing, TimescaleDB metrics storage |
| **2** | Remote push agent (psutil + docker-py collectors), Bearer token auth, metric ingestion |
| **3** | Anti-flapping FSM, sliding window counters, Discord webhook alerting |
| **4** | Atomic DB concurrency (`SELECT FOR UPDATE`), WebSocket real-time hub, Next.js 15 dashboard, Caddy reverse proxy |
| **5** | Graceful agent shutdown (SIGTERM/SIGINT), 7-day retention policy, one-line installer |

---

## Architecture

### System Design

Lookout follows **Hexagonal Architecture (Ports & Adapters)**, ensuring the domain business logic is independent of any framework, database, or HTTP library:

```mermaid
flowchart TD
    Client["Browser<br/>(Next.js Dashboard)"]
    WebClient["WebSocket Client"]
    Agent["Remote Agent<br/>(psutil + docker-py)"]
    Caddy["Caddy Reverse Proxy<br/>:80"]

    subgraph Backend["Backend (FastAPI)"]
        API["REST API Routers<br/>(services, metrics, ws)"]
        DomainLogic["Domain Layer<br/>(Service, State Machine,<br/>Event Publisher)"]
        Probes["Blackbox Prober<br/>(HTTP/TCP)"]
        Scheduler["Probe Scheduler"]
        Evaluator["Alert Evaluator"]
    end

    subgraph DB["Data Layer"]
        TimescaleDB["TimescaleDB<br/>(services, metrics,<br/>agent_keys, hypertable)"]
        AsyncPG["asyncpg Connection Pool<br/>(no ORM)"]
    end

    subgraph Infra["Notification & Streaming"]
        Discord["Discord Webhook<br/>Notifier"]
        WSHub["WebSocket Hub<br/>(EventPublisher Adapter)"]
    end

    subgraph Frontend["Frontend (Next.js 15)"]
        Dashboard["Dashboard<br/>(React + Tailwind +<br/>shadcn/ui)"]
    end

    Client -->|HTTP| Caddy
    WebClient -->|WebSocket| Caddy
    Agent -->|POST /metrics/push<br/>Bearer Token| Caddy
    Caddy -->|Reverse Proxy| API
    Caddy -->|Static Export| Dashboard
    Dashboard -->|WebSocket| WSHub

    API -->|Calls Use Cases| DomainLogic
    DomainLogic -->|Publishes Events| WSHub
    DomainLogic -->|Evaluates Alerts| Scheduler
    Scheduler -->|Runs Probes| Probes
    Scheduler -->|Calls Evaluator| Evaluator
    Evaluator -->|Sends Alerts| Discord
    Evaluator -->|Publishes Events| WSHub

    API -->|Queries/Mutations| AsyncPG
    Scheduler -->|Queries/Mutations| AsyncPG
    Evaluator -->|Queries/Mutations| AsyncPG
    AsyncPG -->|Rows| TimescaleDB
```

### Data Flow: Alert Evaluation

When metrics arrive (either from blackbox probe or push agent), the system evaluates thresholds and manages state transitions:

```mermaid
sequenceDiagram
    participant Probe as Blackbox/Agent
    participant Evaluator as Alert Evaluator
    participant FSM as State Machine
    participant Notifier as Discord Notifier
    participant WSHub as WebSocket Hub
    participant Dashboard as Dashboard Client

    Probe->>Evaluator: New probe result (UP/DOWN) or agent metrics arrive
    Evaluator->>FSM: Check sliding window counters (consecutive failures/successes)
    
    alt Breach threshold (3 consecutive failures detected)
        FSM->>FSM: UNKNOWN → WARNING → CRITICAL
        FSM->>Notifier: trigger alert
        Notifier->>Discord: POST alert webhook
        Notifier-->>WSHub: StateChanged event
    else Recovered (2 consecutive successes)
        FSM->>FSM: CRITICAL → RESOLVED
        FSM->>Notifier: resolve alert
        Notifier->>Discord: POST resolve webhook
        Notifier-->>WSHub: StateChanged event
    else No state change
        FSM->>FSM: Stay in current state
    end

    WSHub->>Dashboard: Real-time state update (WebSocket)
    Dashboard->>Dashboard: Re-render service cards
```

### Database Schema

```mermaid
erDiagram
    SERVICES ||--o{ METRICS : logs
    SERVICES ||--o{ AGENT_KEYS : has

    SERVICES {
        uuid id PK
        text name
        text type "http|tcp"
        text target
        int interval_s
        int expected_status
        boolean enabled
        text current_state "UNKNOWN|UP|WARNING|CRITICAL|RESOLVED"
        timestamptz created_at
        text agent_id FK "null for blackbox"
        int consecutive_failures
        int consecutive_successes
        timestamptz failure_start
    }

    METRICS {
        timestamptz time PK
        uuid service_id FK
        text metric "latency_ms|up|cpu|memory"
        double_precision value
        jsonb labels
    }

    AGENT_KEYS {
        uuid id PK
        text agent_id UK
        text key_hash "sha256"
        timestamptz created_at
        timestamptz revoked_at
    }
```

**TimescaleDB Specifics:**
- `metrics` is a **hypertable** partitioned on `time`
- Automatic 7-day retention policy (`DROP chunks older than 7 days`)
- Index on `(service_id, metric, time DESC)` for efficient time-series lookups
- Dev seed includes `agent_id='dev-agent-01'` with key hash for `lookout-dev-key`

### Layer Responsibilities

| Layer | Location | Responsibility |
|-------|----------|-----------------|
| **Domain** | `backend/app/domain/` | Pure Python models, ports (ABCs), anti-flapping FSM, no I/O imports |
| **Application** | `backend/app/application/` | Use cases: `evaluate_alerts`, `run_blackbox_probe`, `ingest_push_metrics` |
| **Infrastructure** | `backend/app/infrastructure/` | asyncpg repositories, HTTP/TCP prober, Discord notifier, WebSocket hub |
| **API** | `backend/app/api/v1/` | FastAPI routers, dependency injection, request/response models |

---

## Tech Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Backend Runtime** | Python | 3.11+ | Async server with FastAPI |
| **Web Framework** | FastAPI | ≥0.111.0 | REST API + WebSocket endpoints |
| **App Server** | Uvicorn | ≥0.29.0 | ASGI server with async lifespan |
| **Database** | TimescaleDB | 16 | PostgreSQL + time-series extension |
| **DB Client** | asyncpg | ≥0.29.0 | Async PostgreSQL driver (no ORM) |
| **HTTP Client** | httpx | ≥0.27.0 | Async HTTP for blackbox probing |
| **Config** | Pydantic Settings | ≥2.2.0 | Type-safe environment variables |
| **Validation** | Pydantic | ≥2.7.0 | Data validation + serialization |
| **Frontend Runtime** | Node.js | 20-alpine | Build/runtime for Next.js |
| **Frontend Framework** | Next.js | 15 | React + SSG (output: "export") |
| **CSS** | Tailwind CSS | Latest | Utility-first styling |
| **UI Components** | shadcn/ui | Latest | Pre-built accessible components |
| **Agent Runtime** | Python | 3.11+ | Remote metric collection |
| **System Metrics** | psutil | ≥5.9 | CPU, memory, disk, network |
| **Container Metrics** | docker-py | ≥7.0 | Docker container stats |
| **Reverse Proxy** | Caddy | 2-alpine | Auto HTTPS + load balancing |
| **Container Orchestration** | Docker Compose | Plugin or Standalone | Multi-service coordination |

---

## Prerequisites

### System Requirements

- **Docker & Docker Compose** — For containerized installation
  - Docker 20.10+ (or newer)
  - Docker Compose plugin v2+ or standalone docker-compose
  - Install: https://docs.docker.com/get-docker/ and https://docs.docker.com/compose/install/

- **Python 3.11+** — For local/development installations or agent deployments
  - Install: https://www.python.org/downloads/

- **Network Access**
  - Service can bind to `localhost:80` (Caddy reverse proxy)
  - Agents need network access to the backend URL (e.g., `http://monitoring.example.com`)

### Optional

- **Discord Webhook URL** — For alert notifications (set `DISCORD_WEBHOOK_URL` in `.env`)
- **Git** — To clone the repository
- **Make** — Not required; all commands use `docker compose` directly

---

## Installation

### Option 1: One-Line Installer (Recommended for Production)

The fastest way to get Lookout running on any Unix-like system (Linux, macOS):

```bash
git clone https://github.com/ncharles11/lookout.git
cd lookout
./install.sh
```

The installer will:
1. Check for Docker and Docker Compose
2. Copy `.env.example` to `.env` (review it before production)
3. Build and start all 4 services (db, backend, frontend, proxy)
4. Wait for health checks to pass
5. Print success banner with dashboard URL

**Expected output:**
```
  ✔  docker found (25.0.3)
  ✔  docker compose found
  ✔  backend/.env created from .env.example
  
  → Building images and starting the stack (this may take a few minutes)...
  
  → Waiting for the backend to become healthy...
  
  🚀  Lookout is up and running!
  
  Dashboard  →  http://localhost
  API        →  http://localhost/api/v1/services
  WebSocket  →  ws://localhost/ws/v1/dashboard
```

### Option 2: Manual Docker Compose Setup

For fine-grained control over configuration:

```bash
git clone https://github.com/ncharles11/lookout.git
cd lookout

# Copy and edit the environment file
cp backend/.env.example backend/.env
# Edit backend/.env to add your Discord webhook, database settings, etc.
nano backend/.env

# Build and start the stack
docker compose up -d --build

# Verify all services are healthy
docker compose ps
# Output should show all services with status "Up"

# Check the health endpoint
curl -s http://localhost/api/v1/services/status | jq .

# View logs
docker compose logs -f backend
```

**Ports used:**
- `80` — Caddy reverse proxy (dashboard + API)
- `8000` — Backend FastAPI (internal only, proxied through Caddy)
- `5432` — PostgreSQL/TimescaleDB (internal only, not exposed)

### Option 3: Local Development Setup

Run the backend and frontend locally on your machine (requires Python 3.11+ and Node.js 20+):

**Backend:**
```bash
cd backend

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # or on Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start TimescaleDB separately (Docker or local PostgreSQL)
docker run -d \
  --name timescaledb \
  -p 5432:5432 \
  -e POSTGRES_DB=lookout \
  -e POSTGRES_USER=lookout \
  -e POSTGRES_PASSWORD=lookout \
  timescale/timescaledb:latest-pg16

# Run database initialization
psql postgresql://lookout:lookout@localhost:5432/lookout < ../docker/db/init.sql

# Start the backend dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at `http://localhost:8000` with auto-reload on code changes.

**Frontend:**
```bash
cd frontend

# Install dependencies
npm install

# Start the Next.js dev server
npm run dev
```

Frontend will be available at `http://localhost:3000`.

**Note:** The dev setup requires you to manually point frontend WebSocket to the backend. Edit `src/components/Dashboard.tsx` and set `wsUrl` appropriately.

---

## Configuration

### Backend Configuration (`backend/.env`)

Create or edit `backend/.env` with the following variables:

```bash
# ──────────────────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://lookout:lookout@localhost:5432/lookout

# ──────────────────────────────────────────────────────────────────────
# Probing
# ──────────────────────────────────────────────────────────────────────
# Maximum number of blackbox probes to run concurrently
PROBE_CONCURRENCY=10

# ──────────────────────────────────────────────────────────────────────
# Alerting & Notifications
# ──────────────────────────────────────────────────────────────────────
# Discord webhook URL for alert notifications (optional)
# Leave blank to disable Discord alerts (NoOpNotifier will be used)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN

# Anti-flapping configuration
# Number of consecutive failures before entering WARNING state
ALERT_CONSECUTIVE_FAILURES=3

# Duration window for consecutive failure detection (seconds)
ALERT_FAILURE_DURATION_S=60.0

# Number of consecutive successes before resolving alert
ALERT_CONSECUTIVE_SUCCESSES=2
```

**Environment Variables Reference:**

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DATABASE_URL` | string | `postgresql://lookout:lookout@localhost:5432/lookout` | TimescaleDB connection string (user:pass@host:port/db) |
| `PROBE_CONCURRENCY` | int | `10` | Max concurrent blackbox HTTP/TCP probes (tune based on resource limits) |
| `DISCORD_WEBHOOK_URL` | string (optional) | unset | Full Discord webhook URL; if omitted, alerts go to a no-op notifier |
| `ALERT_CONSECUTIVE_FAILURES` | int | `3` | Failures in window before WARNING state |
| `ALERT_FAILURE_DURATION_S` | float | `60.0` | Time window for counting consecutive failures |
| `ALERT_CONSECUTIVE_SUCCESSES` | int | `2` | Successes needed to transition from CRITICAL → RESOLVED |

### Agent Configuration

Agents read from a `.env` file or environment variables:

```bash
# ──────────────────────────────────────────────────────────────────────
# Backend Connection
# ──────────────────────────────────────────────────────────────────────
BACKEND_URL=http://localhost:8000
# For remote deployments: http://monitoring.example.com:8000

# ──────────────────────────────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────────────────────────────
# Your agent ID (must be registered in backend database)
AGENT_ID=my-server-01

# Bearer token for authentication (matches key_hash in database)
AGENT_API_KEY=your-secure-api-key-here

# ──────────────────────────────────────────────────────────────────────
# Collection
# ──────────────────────────────────────────────────────────────────────
# Interval between metric collection (seconds)
COLLECT_INTERVAL_S=15

# Enable Docker container metrics collection
ENABLE_DOCKER=true
```

**Environment Variables Reference:**

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `BACKEND_URL` | string | `http://localhost:8000` | Backend API URL (must be reachable from agent) |
| `AGENT_ID` | string | `dev-agent-01` | Unique identifier for this agent (registered in `agent_keys` table) |
| `AGENT_API_KEY` | string | `lookout-dev-key` | Bearer token (must match SHA-256 hash in database) |
| `COLLECT_INTERVAL_S` | int | `15` | Seconds between metric collection batches |
| `ENABLE_DOCKER` | bool | `true` | Collect Docker container metrics (requires docker socket access) |

### Alerting

Alerts transition through states based on the anti-flapping state machine:

```
UNKNOWN
  ↓
(3 consecutive failures within 60s window)
  ↓
WARNING
  ↓
(3 consecutive failures within 60s window)
  ↓
CRITICAL
  ↓
(2 consecutive successes within 60s window)
  ↓
RESOLVED
```

Each state transition (if it changes) triggers:
1. A notification via the configured notifier (Discord webhook)
2. A WebSocket event broadcast to all dashboard clients
3. A database row update with the new state

You can tune the thresholds in `backend/.env`:
- Increase `ALERT_CONSECUTIVE_FAILURES` to reduce false positives (e.g., set to 5)
- Increase `ALERT_FAILURE_DURATION_S` to expand the window for counting (e.g., set to 120.0)
- Decrease `ALERT_CONSECUTIVE_SUCCESSES` to resolve faster (e.g., set to 1)

---

## Usage

### Quick Start: Create a Service and Probe It

After installation, the dashboard is available at `http://localhost`.

**Via API (curl):**
```bash
# Create an HTTP service
curl -X POST http://localhost/api/v1/config/services \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "example-api",
    "type": "http",
    "target": "https://api.example.com/health",
    "expected_status": 200,
    "interval_s": 30
  }'

# Response:
# {
#   "id": "550e8400-e29b-41d4-a716-446655440000",
#   "name": "example-api",
#   "type": "http",
#   "target": "https://api.example.com/health",
#   "expected_status": 200,
#   "interval_s": 30,
#   "enabled": true,
#   "current_state": "UNKNOWN",
#   "created_at": "2025-06-27T10:15:00Z"
# }

# Fetch all services and their current state
curl http://localhost/api/v1/services/status

# Response:
# [
#   {
#     "id": "550e8400-e29b-41d4-a716-446655440000",
#     "name": "example-api",
#     "type": "http",
#     "current_state": "UP",
#     "created_at": "2025-06-27T10:15:00Z"
#   }
# ]

# Delete a service
curl -X DELETE http://localhost/api/v1/services/550e8400-e29b-41d4-a716-446655440000
```

**Via Dashboard:**
1. Open http://localhost
2. Click "+ Add Service"
3. Fill in name, type (HTTP/TCP), target, probe interval
4. Click "Save"
5. Observe real-time status updates on the dashboard

### Push Agent Metrics

If you have a remote agent running (see Agent Deployment below), it will continuously push metrics:

```bash
# Example metric batch from agent
POST http://localhost/api/v1/metrics/push
Authorization: Bearer lookout-dev-key
Content-Type: application/json

{
  "agent_id": "dev-agent-01",
  "timestamp": "2025-06-27T10:15:00Z",
  "metrics": [
    {
      "service_id": "550e8400-e29b-41d4-a716-446655440000",
      "metric": "cpu_percent",
      "value": 35.2,
      "labels": {"host": "web-server-01"}
    },
    {
      "service_id": "550e8400-e29b-41d4-a716-446655440000",
      "metric": "memory_mb",
      "value": 2048.5,
      "labels": {"host": "web-server-01"}
    }
  ]
}

# Response: 204 No Content (success)
```

### Real-Time Dashboard

The dashboard connects to the WebSocket endpoint and receives state change events:

```javascript
// Client-side (handled by Next.js Dashboard automatically)
const ws = new WebSocket("ws://localhost/ws/v1/dashboard");

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === "snapshot") {
    // Initial state of all services
    console.log("Services:", message.services);
  } else if (message.type === "state_change") {
    // Real-time update: a service's state changed
    console.log("Service state changed:", message.service_id, message.new_state);
  } else if (message.type === "ping") {
    // Keep-alive signal
  }
};
```

The dashboard auto-reconnects on disconnect with exponential backoff.

---

## API Reference

All endpoints are prefixed with `/api/v1`. The base URL is `http://localhost` (or your server address).

### Health Check

```
GET /health
```

Returns platform health status (always succeeds).

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

---

### Services

#### Create Service

```
POST /api/v1/config/services
Content-Type: application/json
```

Register a new service to be monitored.

**Request Body:**
```json
{
  "name": "string",
  "type": "http" | "tcp",
  "target": "string (URL or host:port)",
  "expected_status": "integer (optional, for HTTP only)",
  "interval_s": "integer (default 60)"
}
```

**Request Example:**
```bash
curl -X POST http://localhost/api/v1/config/services \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "db-primary",
    "type": "tcp",
    "target": "db.example.com:5432",
    "interval_s": 30
  }'
```

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "db-primary",
  "type": "tcp",
  "target": "db.example.com:5432",
  "expected_status": null,
  "interval_s": 30,
  "enabled": true,
  "current_state": "UNKNOWN",
  "created_at": "2025-06-27T10:15:00Z",
  "agent_id": null
}
```

---

#### Get All Services

```
GET /api/v1/services/status
```

Fetch all services and their current health state.

**Response (200 OK):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "db-primary",
    "type": "tcp",
    "target": "db.example.com:5432",
    "interval_s": 30,
    "enabled": true,
    "current_state": "UP",
    "created_at": "2025-06-27T10:15:00Z",
    "agent_id": null
  },
  {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "name": "web-api",
    "type": "http",
    "target": "https://api.example.com/health",
    "expected_status": 200,
    "interval_s": 60,
    "enabled": true,
    "current_state": "CRITICAL",
    "created_at": "2025-06-27T10:20:00Z",
    "agent_id": null
  }
]
```

---

#### Get Service by ID

```
GET /api/v1/services/{id}
```

Fetch a single service by UUID.

**Path Parameters:**
- `id` (string, UUID) — Service ID

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "db-primary",
  "type": "tcp",
  "target": "db.example.com:5432",
  "interval_s": 30,
  "enabled": true,
  "current_state": "UP",
  "created_at": "2025-06-27T10:15:00Z",
  "agent_id": null
}
```

**Response (404 Not Found):** Service does not exist.

---

#### Delete Service

```
DELETE /api/v1/services/{id}
```

Remove a service and its associated metrics from monitoring.

**Path Parameters:**
- `id` (string, UUID) — Service ID

**Response (204 No Content):** Success; service deleted.

**Response (404 Not Found):** Service does not exist.

---

### Metrics

#### Push Agent Metrics

```
POST /api/v1/metrics/push
Authorization: Bearer {AGENT_API_KEY}
Content-Type: application/json
```

Agents submit metric batches. Each batch is ingested, evaluated against thresholds, and may trigger alerts.

**Headers:**
- `Authorization: Bearer {AGENT_API_KEY}` — Required. Bearer token must match a key in the `agent_keys` table.

**Request Body:**
```json
{
  "agent_id": "string",
  "timestamp": "string (ISO 8601)",
  "metrics": [
    {
      "service_id": "string (UUID of the service)",
      "metric": "string (metric name)",
      "value": "number",
      "labels": "object (optional, arbitrary JSON)"
    }
  ]
}
```

**Request Example:**
```bash
curl -X POST http://localhost/api/v1/metrics/push \
  -H 'Authorization: Bearer lookout-dev-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "agent_id": "web-server-01",
    "timestamp": "2025-06-27T10:15:00Z",
    "metrics": [
      {
        "service_id": "550e8400-e29b-41d4-a716-446655440000",
        "metric": "cpu_percent",
        "value": 45.2,
        "labels": {"host": "web-server-01", "cores": "4"}
      },
      {
        "service_id": "550e8400-e29b-41d4-a716-446655440000",
        "metric": "memory_mb",
        "value": 3072.5,
        "labels": {"host": "web-server-01"}
      }
    ]
  }'
```

**Response (204 No Content):** Metrics ingested successfully.

**Response (401 Unauthorized):** Invalid or missing Bearer token.

**Response (422 Unprocessable Entity):** Invalid request body.

---

### WebSocket

#### Real-Time Dashboard Stream

```
GET /ws/v1/dashboard
Upgrade: websocket
```

Upgrade to WebSocket to receive real-time service state change events.

**Initial Message (on connect):**
```json
{
  "type": "snapshot",
  "services": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "db-primary",
      "type": "tcp",
      "target": "db.example.com:5432",
      "current_state": "UP",
      "interval_s": 30,
      "enabled": true
    }
  ]
}
```

**State Change Event:**
```json
{
  "type": "state_change",
  "service_id": "550e8400-e29b-41d4-a716-446655440000",
  "new_state": "CRITICAL",
  "timestamp": "2025-06-27T10:15:30Z"
}
```

**Keep-Alive (every 30s):**
```json
{
  "type": "ping"
}
```

**JavaScript Client Example:**
```javascript
const ws = new WebSocket("ws://localhost/ws/v1/dashboard");

ws.onopen = () => console.log("Connected to dashboard stream");

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  
  if (msg.type === "snapshot") {
    console.log("Initial state:", msg.services);
  } else if (msg.type === "state_change") {
    console.log(`Service ${msg.service_id} is now ${msg.new_state}`);
  }
};

ws.onerror = (err) => console.error("WebSocket error:", err);
ws.onclose = () => console.log("Disconnected; dashboard will auto-reconnect");
```

---

## Agent Deployment

The Lookout Agent is a lightweight, stateless process that runs on each monitored host and periodically collects metrics (CPU, memory, disk, Docker containers) and pushes them to the backend.

### Option 1: Docker Container (Recommended)

Deploy the agent as a container on your host:

```bash
# Pull the Lookout agent image (or build locally)
docker run -d \
  --name lookout-agent \
  --restart unless-stopped \
  -e BACKEND_URL=http://monitoring.example.com:8000 \
  -e AGENT_ID=web-server-01 \
  -e AGENT_API_KEY=your-secure-key \
  -e COLLECT_INTERVAL_S=15 \
  -e ENABLE_DOCKER=true \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  lookout-agent:latest

# Check logs
docker logs -f lookout-agent

# Stop gracefully
docker stop lookout-agent
# Agent will trap SIGTERM and finish in-flight collection before exiting
```

**Key Notes:**
- Mount `/var/run/docker.sock` if `ENABLE_DOCKER=true` to access container metrics
- Set `--restart unless-stopped` for production (auto-restart on crash, but respects manual stops)
- Agent gracefully shuts down on `SIGTERM`/`SIGINT` (container will wait for graceful period)

### Option 2: System Package (pip)

Install and run the agent as a system service on Linux:

```bash
# Install the agent package
pip install lookout-agent

# Create a .env file with configuration
cat > /etc/lookout-agent/.env << EOF
BACKEND_URL=http://monitoring.example.com:8000
AGENT_ID=web-server-01
AGENT_API_KEY=your-secure-key
COLLECT_INTERVAL_S=15
ENABLE_DOCKER=true
EOF

# Run the agent in the foreground (or use systemd service below)
lookout-agent

# For production, create a systemd service
sudo tee /etc/systemd/system/lookout-agent.service > /dev/null << EOF
[Unit]
Description=Lookout Monitoring Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/lookout-agent
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=lookout-agent

# For graceful shutdown (recommended)
KillSignal=SIGTERM
TimeoutStopSec=30

# If running with Docker container access
# SupplementaryGroups=docker

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable lookout-agent
sudo systemctl start lookout-agent

# Check status
sudo systemctl status lookout-agent
sudo journalctl -u lookout-agent -f
```

### Option 3: Source Code (Development)

Clone and run the agent directly from source:

```bash
# Clone the repository
git clone https://github.com/ncharles11/lookout.git
cd lookout/agent

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .

# Create .env file
cat > .env << EOF
BACKEND_URL=http://localhost:8000
AGENT_ID=dev-agent-01
AGENT_API_KEY=lookout-dev-key
COLLECT_INTERVAL_S=15
ENABLE_DOCKER=true
EOF

# Run the agent
lookout-agent

# Ctrl+C will gracefully shut down
```

### Registering an Agent

Before an agent can push metrics, you must register its API key in the backend:

```bash
# SSH into the backend container (or DB container)
docker compose exec backend bash

# Or connect to TimescaleDB directly
psql postgresql://lookout:lookout@db:5432/lookout

# Insert the agent's API key (hashed with SHA-256)
INSERT INTO agent_keys (agent_id, key_hash)
VALUES (
  'web-server-01',
  encode(sha256('your-secure-key'::bytea), 'hex')
);

# Verify the key was created
SELECT agent_id, created_at FROM agent_keys WHERE agent_id='web-server-01';
```

Once registered, the agent can push metrics using that key as a Bearer token.

### Agent Metrics

The agent automatically collects and pushes these metrics every `COLLECT_INTERVAL_S` seconds:

**System Metrics (via psutil):**
- `cpu_percent` — CPU usage (0–100%)
- `memory_mb` — Memory used (MB)
- `memory_percent` — Memory usage (0–100%)
- `disk_mb_used` — Disk used (MB)
- `disk_percent` — Disk usage (0–100%)
- `network_bytes_sent` — Network sent (bytes)
- `network_bytes_recv` — Network received (bytes)

**Container Metrics (via docker-py, if `ENABLE_DOCKER=true`):**
- `container_cpu_percent` — Container CPU usage (%)
- `container_memory_mb` — Container memory usage (MB)
- `container_count` — Number of running containers

Each metric is tagged with labels (hostname, container name, etc.) for context in queries.

---

## Development

### Running Tests

**Backend unit tests:**
```bash
cd backend

# Install dev dependencies
pip install -r requirements-dev.txt

# Run unit tests (12 anti-flapping FSM tests)
pytest tests/unit/test_state_machine.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test
pytest tests/unit/test_state_machine.py::test_transition_unknown_to_warning -v
```

**Frontend tests (if available):**
```bash
cd frontend

npm test
```

### Development Workflow

**Backend with auto-reload:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
export DATABASE_URL=postgresql://lookout:lookout@localhost:5432/lookout
uvicorn app.main:app --reload --log-level debug
```

Open http://localhost:8000/docs for interactive API documentation.

**Frontend with hot reload:**
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

### Project Layout

```
lookout/
├── backend/
│   ├── app/
│   │   ├── domain/              # Pure business logic
│   │   │   ├── models.py
│   │   │   ├── alerting/
│   │   │   │   ├── state_machine.py
│   │   │   │   ├── sliding_window.py
│   │   │   │   └── events.py
│   │   │   └── ports/            # Abstract interfaces
│   │   ├── application/          # Use cases
│   │   ├── infrastructure/       # Concrete adapters
│   │   ├── api/v1/               # FastAPI routers
│   │   ├── main.py               # App factory + lifespan
│   │   └── config.py             # Settings
│   ├── tests/unit/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── requirements-dev.txt
│
├── agent/
│   ├── lookout_agent/
│   │   ├── __main__.py           # Entry point
│   │   ├── config.py             # Agent settings
│   │   ├── models.py             # Data models
│   │   ├── transport.py          # HTTP client
│   │   └── collectors/           # psutil, docker metrics
│   ├── pyproject.toml
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── app/                  # Next.js routes
│   │   ├── components/           # React components
│   │   │   ├── Dashboard.tsx     # Main UI + WebSocket
│   │   │   └── ui/               # shadcn/ui components
│   │   └── lib/                  # Utilities
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── nginx.conf                # Static file server
│   ├── Dockerfile
│   └── package.json
│
├── docker/
│   ├── db/init.sql               # Database schema + seed
│   └── caddy/Caddyfile           # Reverse proxy config
│
├── docker-compose.yml            # Multi-service orchestration
├── install.sh                    # One-line installer
├── README.md                     # This file
├── architecture.md               # Detailed architecture docs
├── requirements.md               # Sprint requirements
└── CHANGELOG.md                  # Version history
```

### Adding a New Notifier

To add a new notification channel (e.g., Slack, PagerDuty):

1. **Define the port** — Add a new method to `domain/ports/notifier.py`:
   ```python
   @abstractmethod
   async def slack_notify(self, service: Service, state: ServiceState) -> None:
       pass
   ```

2. **Implement the adapter** — Create `infrastructure/notifiers/slack_notifier.py`:
   ```python
   from app.domain.ports.notifier import Notifier
   
   class SlackNotifier(Notifier):
       async def slack_notify(self, service: Service, state: ServiceState) -> None:
           # POST to Slack API
           pass
   ```

3. **Wire in main.py** — Add to the lifespan function:
   ```python
   notifier = SlackNotifier(settings.SLACK_WEBHOOK_URL)
   ```

4. **Update config.py** — Add `SLACK_WEBHOOK_URL` setting.

The domain logic remains unchanged; you've simply added a new adapter. All notifiers are called in `ProbeScheduler.evaluate_service`.

### Adding a New Metric Collector (Agent)

To add a new system metric collection (e.g., network latency, GPU usage):

1. **Create a collector module** — `agent/lookout_agent/collectors/network_latency.py`:
   ```python
   async def collect_latency_metrics() -> list[MetricPoint]:
       # Ping or HTTP latency checks
       return [...]
   ```

2. **Register in `__main__.py`** — Add to the metric collection loop.

3. **Test locally** — Run the agent with `COLLECT_INTERVAL_S=5` and verify metrics appear.

---

## Troubleshooting

### Backend won't start: "Database connection refused"

**Cause:** TimescaleDB is not running or misconfigured.

**Fix:**
```bash
# Check if db container is running
docker compose ps db

# If not running, start it
docker compose up db -d

# Check logs
docker compose logs db

# Verify connection manually
docker compose exec db psql -U lookout -d lookout -c "SELECT 1"
```

### Agent can't reach backend: "Connection refused"

**Cause:** Agent is using the wrong `BACKEND_URL` or backend is not accessible.

**Fix:**
```bash
# From the agent container, verify backend is reachable
docker exec lookout-agent curl http://backend:8000/health

# If agent is not containerized, check your BACKEND_URL
# For Docker Compose internal DNS: http://backend:8000
# For remote: http://monitoring.example.com:8000
```

### No metrics appearing in dashboard after agent push

**Cause:** Agent API key is not registered or doesn't match.

**Fix:**
```bash
# Verify the key is in the database
docker compose exec db psql -U lookout -d lookout \
  -c "SELECT agent_id, created_at FROM agent_keys"

# If missing, insert it
docker compose exec db psql -U lookout -d lookout << EOF
INSERT INTO agent_keys (agent_id, key_hash)
VALUES ('my-agent', encode(sha256('my-secret-key'::bytea), 'hex'));
EOF

# Check agent logs for auth errors
docker logs lookout-agent
```

### WebSocket connection dropped or not updating

**Cause:** Network issue, frontend/backend version mismatch, or Caddy misconfiguration.

**Fix:**
```bash
# Verify Caddy is proxying WebSocket correctly
docker compose logs proxy | grep -i websocket

# Check if backend receives WebSocket upgrade
docker compose logs backend | grep -i websocket

# Reload frontend (hard refresh in browser)
# or restart the dashboard container
docker compose restart frontend
```

---

## Production Deployment

### Pre-Flight Checklist

- [ ] Set `DISCORD_WEBHOOK_URL` in `backend/.env` for alerts
- [ ] Tune `ALERT_CONSECUTIVE_FAILURES`, `ALERT_FAILURE_DURATION_S`, `ALERT_CONSECUTIVE_SUCCESSES` to your thresholds
- [ ] Configure agents with secure `AGENT_API_KEY` values (use cryptographically random strings)
- [ ] Test at least one probe and one agent push to confirm end-to-end alerting
- [ ] Verify Caddy reverse proxy is behind a firewall or requires authentication
- [ ] Review database backup strategy (TimescaleDB 7-day retention means no long-term history)
- [ ] Set up monitoring/observability for the monitoring platform itself (meta-monitoring)
- [ ] Test graceful shutdown: `docker compose down --timeout 30`

### Scaling

- **Increase `PROBE_CONCURRENCY`** if you have many blackbox services (watch CPU/memory usage)
- **Add more agents** if you need to monitor many hosts (agents are stateless)
- **Use a dedicated TimescaleDB instance** for higher availability (not containerized)
- **Run multiple backend replicas** behind Caddy or a load balancer (stateless)
- **Archive metrics** if you need history beyond 7 days (set up external store before retention cutoff)

### Backup & Restore

```bash
# Dump the database (including schema and data)
docker compose exec db pg_dump -U lookout lookout > lookout-backup.sql

# Restore from backup
docker compose exec db psql -U lookout lookout < lookout-backup.sql

# For automated backups, use pg_dump in a cron job or Kubernetes CronJob
```

---

## Contributing

### Bug Reports & Feature Requests

Please open an issue on GitHub with:
- Reproduction steps
- Expected vs. actual behavior
- Logs (use `docker compose logs` for debugging)
- System info (OS, Docker version, Python version)

### Code Contributions

1. **Fork and clone** the repository
2. **Create a feature branch** (`git checkout -b feature/your-feature`)
3. **Follow hexagonal architecture** — business logic stays in `domain/`, adapters in `infrastructure/`, API in `api/`
4. **Write tests** for new domain logic (use `pytest` for backend, `jest` for frontend)
5. **Run tests locally** before submitting PR
6. **Update README** if adding new configuration or API endpoints
7. **Submit a pull request** with a clear description

### Code Style

- **Python:** PEP 8, type hints required, use `black` for formatting
- **TypeScript/React:** ESLint + Prettier, functional components preferred
- **Git:** Conventional commits (e.g., `feat: add Slack notifier`, `fix: handle null agent_id`)

---

## License

Lookout is released under the **MIT License**. See the LICENSE file for details.

---

## Support & Community

- **Documentation:** https://github.com/ncharles11/lookout/blob/main/README.md
- **Issues:** https://github.com/ncharles11/lookout/issues
- **Architecture Deep-Dive:** See `architecture.md`
- **Changelog:** See `CHANGELOG.md`

---

## Acknowledgments

Lookout was built incrementally over 5 sprints with the following technologies:

- **FastAPI** — Modern, async-first Python web framework
- **TimescaleDB** — PostgreSQL extension for time-series data
- **Next.js 15** — React framework with static export
- **Caddy** — Modern reverse proxy with automatic HTTPS
- **Docker & Compose** — Containerization and orchestration
- **asyncpg** — Async PostgreSQL driver with zero ORM overhead

---

**Lookout — Monitor what matters. Stay in control.**

