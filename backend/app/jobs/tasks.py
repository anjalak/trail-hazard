from __future__ import annotations

import logging
import time

from celery import Celery

from app.core.config import settings
from app.jobs.ingestion_dlq import record_ingestion_task_failure, should_record_ingestion_dlq
from app.services.ingestion import run_ingestion_pipeline
from app.services.repository_factory import build_ingestion_repository

celery_app = Celery("trailintel_jobs", broker=settings.redis_url, backend=settings.redis_url)
logger = logging.getLogger("trailintel.ingestion")

celery_app.conf.beat_schedule = {
    "refresh-source-payloads-every-hour": {
        "task": "app.jobs.tasks.refresh_conditions",
        "schedule": 3600.0,
    }
}

celery_app.conf.timezone = "UTC"

def invalidate_trail_conditions_cache(trail_ids: list[int]) -> int:
    # TODO: Wire Redis key pattern invalidation once cache key scheme is finalized.
    if trail_ids:
        logger.info("ingestion.cache_invalidation.stub", extra={"trail_ids": trail_ids})
    return 0


def _handle_ingestion_task_failure(  # type: ignore[no-untyped-def]
    task, exc, task_id, args, kwargs, einfo
) -> None:
    if not should_record_ingestion_dlq(task, exc):
        return
    try:
        record_ingestion_task_failure(
            task_name=task.name,
            task_id=task_id,
            task_args=tuple(args or ()),
            task_kwargs=dict(kwargs or {}),
            exc=exc,
        )
    except Exception:
        logger.exception("ingestion.dlq.hook_failed", extra={"task_id": task_id})


class IngestionCeleryTask(celery_app.Task):
    """Celery task base: persist a dead-letter record after the last failed attempt."""

    def on_failure(self, exc, task_id, args, kwargs, einfo) -> None:  # type: ignore[no-untyped-def]
        _handle_ingestion_task_failure(self, exc, task_id, args, kwargs, einfo)
        return super().on_failure(exc, task_id, args, kwargs, einfo)


@celery_app.task(
    base=IngestionCeleryTask,
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def refresh_conditions(self) -> dict:
    started = time.perf_counter()
    results = run_ingestion_pipeline(store=build_ingestion_repository())
    cache_keys_invalidated = invalidate_trail_conditions_cache(results["trail_ids"])
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    payload = {
        **results,
        "cache_keys_invalidated": cache_keys_invalidated,
        "run_duration_ms": duration_ms,
        "task_id": self.request.id,
    }
    logger.info("ingestion.run.completed", extra=payload)
    return payload
