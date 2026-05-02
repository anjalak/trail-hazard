"""Run the hazard/review ingestion pipeline once (no Celery).

Loads ``data/external_hazards.json`` and ``data/external_reviews.json`` by default,
parses hazard keywords, and persists into Postgres when ``DATABASE_URL`` points at your DB.

Usage (from ``backend/`` with venv active):

    export DATABASE_URL='postgresql://…'
    python -m scripts.run_ingestion_once

Requires ``USE_IN_MEMORY_REPOSITORY=false`` for Postgres-backed ingestion repository.
"""

from __future__ import annotations

from app.runtime_check import ensure_supported_python

ensure_supported_python()

from app.services.ingestion import run_ingestion_pipeline
from app.services.repository_factory import build_ingestion_repository


def main() -> None:
    store = build_ingestion_repository()
    result = run_ingestion_pipeline(store=store)
    print(result)


if __name__ == "__main__":
    main()
