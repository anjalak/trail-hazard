# Changelog

All notable project updates are tracked here for handoff and portfolio context.

## 2026-05-01

- Added production hosting runbook [`docs/hosting.md`](docs/hosting.md), Render Blueprint [`render.yaml`](render.yaml) (free-tier API only; Alembic at container startup), optional paid Celery [`render.workers.yaml`](render.workers.yaml), and [`frontend/vercel.json`](frontend/vercel.json). Production Docker image includes `backend/data` for ingestion paths.
- Fixed default ingestion export paths so Docker resolves `data/external_hazards.json` under `/app` (was incorrectly `backend/data/…`). Added [`backend/scripts/run_ingestion_once.py`](backend/scripts/run_ingestion_once.py) for one-off ingestion without Celery.
- Normalized naive `reported_at` datetimes to UTC in ingestion and [`hazard_score`](backend/app/services/hazard_scoring.py) so NPS-style exports without offsets do not crash ingestion.

## 2026-04-28

- Explore page map now supports manual location entry by ZIP code or city as a fallback to browser geolocation; the app geocodes the input and reloads nearby trails from that center.
- Added Redis-backed fixed-window rate limiting for GraphQL `submitReport` and `upvoteReport` (per client IP; in-process fallback when Redis is unavailable), with `RATE_LIMIT_*` env configuration and `RATE_LIMITED` GraphQL error extension.
- Added Postgres btree indexes for common trail location filters (`LOWER(state_code)`, `LOWER(park_type)`) and `trails(location_id)` join alignment with `PostgresRepository` search/nearby queries (Alembic `20260428_0003`; `schema.sql` kept in sync).
- Added integration tests for `PostgresRepository` location filters and `nearby_trails` PostGIS distance behavior (`tests/test_postgres_repository.py`); CI runs them against a PostGIS service via `TEST_DATABASE_URL`. Seed trails include `geom` LineStrings for deterministic distance assertions.
- Fixed optional filter parameters in Postgres search/nearby SQL with `::text` casts so psycopg 3 does not raise `AmbiguousParameter` when bind values are NULL (behavior unchanged for callers).

## 2026-04-27

- Added one-command local development entrypoint (`make dev` / `scripts/dev.sh`) to start the Docker Compose stack and the Next.js dev server, with optional `--no-worker` to skip Celery.
- Enforced Python 3.11+ at import time for the API, pytest, and the GraphQL smoke script, with an explicit error if a 3.9/3.10 venv is used by mistake.
- Added location-aware GraphQL filters for trail search and nearby queries (`stateCode`, `city`, `parkType`, `parkNameContains`).
- Added Postgres-backed repository mode with API fallback to in-memory when DB ping fails.
- Added DB bootstrap flow (`python -m scripts.bootstrap_db`) and Alembic baseline migration setup.
- Replaced `trailHazardsGeojson` string output with JSON object response.
- Added report input validation and moderation metadata fields.
- Added ingestion improvements: source adapters, hazard dedupe, Postgres persistence, and run metrics.
- Added GraphQL integration tests and smoke test script for core queries.
- Expanded run/debug docs and demo guidance for local handoff.
