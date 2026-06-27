# Lookout

Self-hosted monitoring & alerting platform. Sprint 1 delivers the black-box
probing core: register HTTP/TCP services, probe them on a schedule, store
latency and up/down metrics in TimescaleDB, and expose service status via a
REST API.

## Architecture

Ports & Adapters (Hexagonal). Dependencies point inward toward the domain.

```
backend/app/
├── domain/            # Pure models + repository ports (zero infra/framework imports)
│   ├── models.py
│   └── ports/         # MetricRepository, ServiceRepository (ABCs)
├── application/       # Use cases orchestrating ports
│   └── run_blackbox_probe.py
├── infrastructure/    # Adapters: asyncpg repos, httpx/tcp prober, scheduler
│   ├── db/
│   └── prober/
└── api/               # FastAPI delivery layer (no business logic)
    └── v1/services.py
```

Rule of thumb: the scheduler calls the `run_blackbox_probe` use case, which
talks to ports only. Concrete adapters are wired together in `main.py`.

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env   # optional; compose injects DATABASE_URL
docker compose up --build
```

- API: http://localhost:8000
- Health: http://localhost:8000/health
- OpenAPI docs: http://localhost:8000/docs

## Quick start (local)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Start TimescaleDB separately, then:
export DATABASE_URL=postgresql://lookout:lookout@localhost:5432/lookout
uvicorn app.main:app --reload
```

## API

| Method | Path                       | Body            | Returns          |
|--------|----------------------------|-----------------|------------------|
| POST   | `/api/v1/config/services`  | `ServiceCreate` | `Service` (201)  |
| GET    | `/api/v1/services/status`  | —               | `[Service]`(200) |
| GET    | `/health`                  | —               | `{"status":"ok"}`|

### Register a service

```bash
curl -X POST http://localhost:8000/api/v1/config/services \
  -H 'Content-Type: application/json' \
  -d '{"name":"example","type":"http","target":"https://example.com","expected_status":200,"interval_s":30}'
```

> Newly registered services are picked up by the scheduler on the next backend
> restart (Sprint 1 loads the probe set at startup).

## Configuration

| Variable            | Default                                               | Description                  |
|---------------------|-------------------------------------------------------|------------------------------|
| `DATABASE_URL`      | `postgresql://lookout:lookout@localhost:5432/lookout` | TimescaleDB connection       |
| `PROBE_CONCURRENCY` | `10`                                                  | Max simultaneous probes      |

## Next steps

- Hot-reload the scheduler when a service is created (no restart required).
- Add alerting rules and notification adapters (email/Slack/webhook ports).
- Expose metric query endpoints backed by TimescaleDB continuous aggregates.
- Add unit tests for `run_blackbox_probe` and integration tests for the repos.
