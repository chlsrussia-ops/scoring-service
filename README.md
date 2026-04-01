# scoring-service v3.1 — Production Hardened

Scoring pipeline with idempotency, job queue, outbox pattern, circuit breakers,
source protection, dead-letter handling, admin API, and full observability.

## Quick start

```bash
cp .env.example .env
pip install -e ".[dev]"
# Start PostgreSQL (or use docker-compose)
docker compose up db -d
# Run migrations
alembic upgrade head
# Start API
make api
# Start worker (in another terminal)
python -m scoring_service.worker
```

## Docker

```bash
docker compose up --build
docker compose exec scoring-service alembic upgrade head
```

## API Endpoints

### Public
- `GET  /health` — liveness
- `GET  /ready` — readiness with subsystem checks
- `GET  /metrics` — Prometheus metrics
- `POST /v1/score` — score a payload (auth required, idempotent with Idempotency-Key header)
- `GET  /v1/scores` — list recent scores

### Admin (requires X-Admin-Key header)
- `GET  /v1/admin/jobs` — list jobs
- `GET  /v1/admin/jobs/{id}` — job details + attempts
- `POST /v1/admin/jobs/{id}/retry` — retry a dead job
- `POST /v1/admin/jobs/requeue-failed` — requeue all dead jobs
- `GET  /v1/admin/failures` — dead-letter + failure records
- `POST /v1/admin/failures/{id}/replay` — replay a dead-letter item
- `GET  /v1/admin/outbox` — outbox events
- `POST /v1/admin/outbox/{id}/dispatch` — re-dispatch an outbox event
- `GET  /v1/admin/sources/health` — source health summary
- `POST /v1/admin/sources/{id}/quarantine` — quarantine a source
- `POST /v1/admin/sources/{id}/resume` — resume a source
- `GET  /v1/admin/diagnostics/summary` — full system diagnostics

## Architecture

- **Idempotency**: Duplicate requests with same Idempotency-Key return cached result
- **Transactional Outbox**: Score events written in same DB transaction, dispatched by worker
- **Job Queue**: DB-backed with exponential backoff, lease/lock, stale recovery
- **Dead Letter**: Failed jobs/dispatches parked with payload snapshot and retry history
- **Circuit Breaker**: Protects webhook delivery from cascading failures
- **Source Protection**: Auto-quarantine noisy sources, manual quarantine/resume via admin API
- **Audit Trail**: All admin actions logged with actor, correlation ID, IP

## Runbook

### Replay failed items
```bash
# List failures
curl -H "X-Admin-Key: admin-secret-key" http://localhost:8020/v1/admin/failures
# Replay specific item
curl -X POST -H "X-Admin-Key: admin-secret-key" http://localhost:8020/v1/admin/failures/1/replay
```

### Requeue dead jobs
```bash
curl -X POST -H "X-Admin-Key: admin-secret-key" http://localhost:8020/v1/admin/jobs/requeue-failed
```

### Quarantine/Resume a source
```bash
curl -X POST -H "X-Admin-Key: admin-secret-key" "http://localhost:8020/v1/admin/sources/noisy-src/quarantine?reason=too+many+errors"
curl -X POST -H "X-Admin-Key: admin-secret-key" http://localhost:8020/v1/admin/sources/noisy-src/resume
```

### Check system health
```bash
curl -H "X-Admin-Key: admin-secret-key" http://localhost:8020/v1/admin/diagnostics/summary
```

## Tests
```bash
pytest
pytest tests/test_production_hardening.py -v
```
