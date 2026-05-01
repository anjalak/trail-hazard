# TrailIntel

TrailIntel is a full-stack trail intelligence app that helps hikers quickly find trails and evaluate current conditions using recency-weighted hazard scoring, community reports, and seasonal guidance.

## Stack

- Frontend: Next.js + TypeScript + Tailwind CSS + shadcn/ui
- Backend: FastAPI + Strawberry GraphQL (Python **3.11+**; not supported on 3.9)
- Data: PostgreSQL + PostGIS
- Jobs: Celery + Redis

**Interpreter:** The repo includes [`.python-version`](.python-version) for pyenv and similar tools. Use Python 3.11 locally to match [Docker](docker-compose.yml) and CI. Typing in backend code uses modern union syntax (PEP 604), which requires 3.10+.

## MVP Features

- Exact trail name search
- Trail detail conditions card
- Danger badges with "how to handle" guidance
- Nearby hikes using geolocation or manual ZIP/city entry
- Map explore with hazard overlays
- Background ingestion pipeline scaffold

## Repository Layout

```text
backend/    FastAPI GraphQL API, scoring, jobs, schema SQL
frontend/   Next.js app routes and UI components
docs/       Architecture, observability, and demo script
```

## Project Tracking

- Changelog: `CHANGELOG.md`
- ROS 2 live demo guide: [`docs/ros-demo.md`](docs/ros-demo.md)

## Documentation Index

- Architecture: [`docs/architecture.md`](docs/architecture.md)
- Running and debugging runbook: [`docs/running-and-debugging.md`](docs/running-and-debugging.md)
- Observability notes: [`docs/observability.md`](docs/observability.md)
- External data strategy: [`docs/external-data-strategy.md`](docs/external-data-strategy.md)
- Robotics reference (canonical): [`docs/robotics.md`](docs/robotics.md)
- Robotics implementation backlog: [`docs/todo-by-area.md`](docs/todo-by-area.md)
- ROS 2 live demo: [`docs/ros-demo.md`](docs/ros-demo.md)

## Local Development

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) with Compose v2, **Node.js 18+** (CI uses 20; see `frontend/package.json`), and **Python 3.11+** for running the backend or tests outside Docker (use repo [`.python-version`](.python-version) with pyenv/asdf). Do not reuse a `backend/.venv` created with Python 3.9 or 3.10—remove it and run `python3.11 -m venv backend/.venv` if imports or tests fail mysteriously.

### One command (full stack)

From the repository root:

```bash
make dev
# or: ./scripts/dev.sh
```

This starts **Postgres, Redis, API, Celery worker, and Celery beat** in the background, waits until `GET /health` succeeds, then runs the **Next.js dev server** in the foreground. Use `make dev-no-worker` or `./scripts/dev.sh --no-worker` to skip the worker and beat. Stop the terminal with Ctrl+C (containers keep running); shut down services with `docker compose down`.

### Manual / partial setup

1. **Python 3.11** when working on the API outside Docker: `cd backend && python3.11 -m venv .venv`.
2. Start infrastructure and backend services:
   - `docker compose up` (or `docker compose up postgres redis backend` without workers)
   - Note: backend defaults to `USE_IN_MEMORY_REPOSITORY=true` unless you provide environment overrides.
   - Important: do not run Docker backend and local `uvicorn` on port `8000` at the same time.
3. Run frontend:
   - `cd frontend`
   - `npm install`
   - `npm run dev`
4. Open:
   - Frontend: `http://localhost:3000`
   - GraphQL API: `http://localhost:8000/graphql`

### Local backend + Docker infra (recommended when debugging repository mode)

From repo root, run infra/services except Docker backend:

```bash
docker compose up -d postgres redis worker beat
docker compose stop backend
```

Then run backend locally with explicit Postgres mode:

```bash
cd backend
source .venv/bin/activate
USE_IN_MEMORY_REPOSITORY=false DATABASE_URL=postgresql://postgres:postgres@localhost:5432/trailintel uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Backend Repository Mode

- `USE_IN_MEMORY_REPOSITORY=false` (default): API uses Postgres-backed repository and real-source bootstrap data.
- `USE_IN_MEMORY_REPOSITORY=true`: test/debug mode only; deterministic in-memory records remain for unit tests and API-contract checks.
- Ingestion uses `PostgresRepository` directly when `USE_IN_MEMORY_REPOSITORY=false` (no API-style fallback).

### GraphQL report rate limits

`submitReport` and `upvoteReport` are **fixed-window** rate limited per client, using the first `X-Forwarded-For` address (if present) or the direct socket IP. Counters are stored in **Redis** when `REDIS_URL` is reachable (shared across API workers). If Redis is down, the API falls back to an **in-process** counter (not safe for multiple processes; set up Redis in production). Tune with `RATE_LIMIT_REPORTS_ENABLED`, `RATE_LIMIT_SUBMIT_MAX_PER_WINDOW`, `RATE_LIMIT_UPVOTE_MAX_PER_WINDOW`, and `RATE_LIMIT_WINDOW_SECONDS` (see `backend/.env.example`). Excess requests return a GraphQL error with `extensions.code: RATE_LIMITED`.

### Postgres bootstrap and migrations

In `backend/`:

- `python -m scripts.bootstrap_db` applies `app/models/schema.sql` then `app/models/seed.sql` using `DATABASE_URL`.
- `python -m scripts.bootstrap_db --skip-seed` applies schema only.
- `alembic upgrade head` applies migrations (baseline included at `20260427_0001`).

### Data Sources and Provenance

Runtime data is generated from real public sources. The canonical rebuild entrypoint is:

- `python backend/scripts/rebuild_real_data.py`

That command rewrites:

- `backend/app/models/seed.sql` with real NPS Public Trails geometry (currently WA parks `MORA`, `OLYM`, `NOCA`)
- `backend/data/external_hazards.json` from live NPS Alerts API content
- `backend/data/external_reviews.json` from the same NPS alerts feed, normalized to the reviews ingestion contract

Key rules:

- `seed.sql` contains real-source trail/location bootstrap rows only (no synthetic hazard/review/weather seed rows).
- Hazard/review exports are regenerated from live APIs, not hand-authored placeholders.
- `trails.geometry_quality` is `imported_nps` and `trails.data_quality_status` is `verified` for generated rows.
- Weather remains runtime data from Open-Meteo cache refresh.

For planning/operations detail, see `docs/external-data-strategy.md`.

## Core GraphQL Operations

- `searchTrailsByName(query, limit, stateCode, city, parkType, parkNameContains)`
- `trail(id)`
- `trailConditions(trailId)`
- `nearbyTrails(lat, lng, km, stateCode, city, parkType, parkNameContains)`
- `roboticsTraversability(trailId)`
- `roboticsArea(lat, lng, radiusM)`
- `submitReport(input)`

The robotics-facing queries expose route-level pre-mission planning context, including GeoJSON route geometry,
traversability/risk scoring, quality metadata, and a ROS-compatible message format. They are not a robot controller,
SLAM stack, or real-time autonomy integration.

TrailIntel also includes a real ROS 2 bridge node (`backend/scripts/ros_bridge.py`) that polls GraphQL and publishes
`Path`, `PoseArray`, and status/risk topics for live demos.

## GraphQL Examples (location filters)

### Search trails by name + location

```graphql
query SearchTrails(
  $query: String!
  $stateCode: String
  $city: String
  $parkType: String
  $parkNameContains: String
) {
  searchTrailsByName(
    query: $query
    stateCode: $stateCode
    city: $city
    parkType: $parkType
    parkNameContains: $parkNameContains
    limit: 10
  ) {
    id
    name
    location {
      stateCode
      city
      parkName
      parkType
    }
  }
}
```

Variables:

```json
{
  "query": "trail",
  "stateCode": "WA",
  "city": "North Bend",
  "parkType": "national_forest",
  "parkNameContains": "alpine"
}
```

### Nearby trails + location filters

```graphql
query NearbyTrails(
  $lat: Float!
  $lng: Float!
  $km: Float!
  $stateCode: String
  $city: String
) {
  nearbyTrails(
    lat: $lat
    lng: $lng
    km: $km
    stateCode: $stateCode
    city: $city
  ) {
    id
    name
    location {
      stateCode
      city
    }
  }
}
```

Variables:

```json
{
  "lat": 47.414,
  "lng": -121.428,
  "km": 10,
  "stateCode": "WA",
  "city": "North Bend"
}
```

### API Contract Notes

- `trailHazardsGeojson(trailId)` now returns a JSON object (`FeatureCollection`) instead of a stringified payload.
- `Report` includes moderation metadata: `moderationStatus` (default `pending`) and `moderatedAt`.
- `submitReport` validates `conditionTags` against an allowlist:
  - `snow`, `windy`, `muddy`, `washout`, `wildlife`, `ice`, `flooded`, `fallen_trees`, `clear`, `rockfall`
- `submitReport.notes` max length is 500 chars and text inputs are sanitized (trimmed and stripped of control chars).

## Deployment Targets

- Frontend: Vercel
- Backend + workers: Render or Railway
- Database: managed Postgres with PostGIS
- Redis: managed Redis provider

## Interview Highlight

The project demonstrates geospatial queries, ETL design, algorithmic hazard scoring, background job orchestration, and end-to-end ownership from UI to deployment.
