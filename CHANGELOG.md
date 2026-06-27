# Changelog

All notable changes to **Lookout** are documented here.Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-06-27

### 📡 Monitoring & Probers

- **core:** Implementation of the foundations and the blackbox prober ([`0db783a`](https://github.com/ncharles11/lookout/commit/0db783a9264757f480100eb14f2bd69c057561ba))
  - Initialization of the stack via Docker Compose (FastAPI + TimescaleDB).
  - Strict implementation of the hexagonal architecture (Domain, Ports, Adapters).
  - Configured the asynchronous database (asyncpg) and created the `metrics` hypertable.
  - Developed the asynchronous HTTP/TCP probing engine using `httpx`.
  - Added a task scheduler integrated with FastAPI’s lifespan.
  - Creation of the initial REST endpoints (`/config/services`, `/services/status`).
  - Implementation of dependency injection for repositories.

## [1.1.0] - 2026-06-27

- **agent:** Implementation of the remote agent ([`0ba19e2a`](https://github.com/ncharles11/lookout/commit/ba19e2aec488a0d1e4112731ee925eb95ef15785))
  - Addition of Bearer token authentication (agent_keys) on the backend side.
  - Creation of the ingestion use case and the POST endpoint /metrics/push.
  - Fix to the scheduler for asynchronous hot-reloading of new target services.