.PHONY: dev dev-no-worker
# Start Postgres, Redis, API, worker+beat (optional via script flag), and the Next.js dev server.
dev:
	./scripts/dev.sh

# Same as dev but without Celery worker and beat (faster / less memory).
dev-no-worker:
	./scripts/dev.sh --no-worker
