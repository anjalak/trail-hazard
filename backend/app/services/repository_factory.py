from __future__ import annotations

from app.core.config import settings
from app.services.postgres_repository import PostgresRepository
from app.services.repository import InMemoryRepository


def build_api_repository():
    if settings.use_in_memory_repository:
        return InMemoryRepository()

    db_repo = PostgresRepository(settings.database_url)
    try:
        if db_repo.ping():
            return db_repo
    except Exception:
        pass
    return InMemoryRepository()


def build_ingestion_repository():
    if settings.use_in_memory_repository:
        return InMemoryRepository()
    return PostgresRepository(settings.database_url)
