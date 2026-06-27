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

### Light Agent and Whitebox Monitoring

- **agent:** Implementation of the remote agent ([`0ba19e2a`](https://github.com/ncharles11/lookout/commit/ba19e2aec488a0d1e4112731ee925eb95ef15785))
  - Addition of Bearer token authentication (agent_keys) on the backend side.
  - Creation of the ingestion use case and the POST endpoint /metrics/push.
  - Fix to the scheduler for asynchronous hot-reloading of new target services.

## [1.2.0] - 2026-06-27

### Brain and Anti-Flapping

- **alerting:** Implementation of the anti-flapping engine and notifications ([`0f93f6c0`](https://github.com/ncharles11/lookout/commit/f93f6c0343e44d2d9328e1ac9c676b7b81ee1d55))
  - Creation of a 100% pure domain for alerting (FSM, sliding window, hysteresis).
  - Addition of domain events (AlertFired, AlertResolved, StateChanged).
  - Implemented the DiscordWebhookNotifier for sending enriched alerts.
  - Wired the evaluate_alerts use case to the blackbox (prober) and whitebox (agent) streams.
  - Added 12 synchronous unit tests to validate the anti-flapping logic.

## [1.3.0] - 2026-06-27

### Dashboard, HUD, and Real-Time
- **ui:** Real-time HUD dashboard, WebSockets, and reverse proxy ([`0c740338`](https://github.com/ncharles11/lookout/commit/c740338eae9ee4c44e85cbb77a545e0db39e2d93))
  - Creation of the WebSocket backend hub (snapshot + state_change).
  - Initialization of the Vite + React + shadcn/ui frontend (dark cyberpunk theme).
  - Reactive dashboard component connected to the WebSocket stream.
  - Implementation of Caddy as a global reverse proxy.