#!/usr/bin/env bash
# One-command local stack: Docker (Postgres, Redis, API, optional Celery) + Next.js dev server.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WITH_WORKER=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-worker)
      WITH_WORKER=0
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./scripts/dev.sh [--no-worker]

  Starts docker compose services in detached mode, waits for the API /health
  endpoint, then runs the frontend dev server (foreground).

  --no-worker   Only postgres, redis, and backend (skip Celery worker + beat).

Prerequisites: Docker with Compose, Node.js 18+ (npm). Python 3.11+ is required
for local backend/scripts outside Docker — see docs/running-and-debugging.md
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1 (try --help)" >&2
      exit 1
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found. Install Docker Desktop or Docker Engine." >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: 'docker compose' not available. Install Docker Compose v2." >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm not found. Install Node.js 18+ (see docs/running-and-debugging.md)." >&2
  exit 1
fi

if [[ "$WITH_WORKER" -eq 1 ]]; then
  echo "Starting postgres, redis, backend, worker, beat..."
  docker compose up -d postgres redis backend worker beat
else
  echo "Starting postgres, redis, backend (no worker/beat)..."
  docker compose up -d postgres redis backend
fi

echo "Waiting for http://localhost:8000/health (first start may take a few minutes while the API image installs deps)..."
ok=0
for i in $(seq 1 150); do
  if curl -sf "http://localhost:8000/health" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done
if [[ "$ok" -ne 1 ]]; then
  echo "ERROR: Timed out waiting for backend. Check: docker compose logs backend" >&2
  exit 1
fi
echo "Backend is healthy."

cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  echo "Running npm install in frontend/..."
  npm install
fi
echo "Starting Next.js (Ctrl+C stops the dev server; containers keep running). Use: docker compose down"
exec npm run dev
