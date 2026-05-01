from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from celery.exceptions import Ignore, Reject, Retry

logger = logging.getLogger("trailintel.ingestion.dlq")

_MAX_EXC_MSG = 2000
_MAX_EXC_REPR = 4000


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return str(value)


def _serialize_args(args: Tuple[Any, ...]) -> List[Any]:
    return _json_safe(list(args))  # type: ignore[return-value]


def _exception_fields(exc: BaseException) -> Tuple[str, str, str]:
    name = type(exc).__name__
    message = (str(exc) or "")[:_MAX_EXC_MSG]
    rep = repr(exc)[:_MAX_EXC_REPR]
    return name, message, rep


def should_record_ingestion_dlq(task: Any, exc: BaseException) -> bool:
    """True when a failure is terminal w.r.t. Celery's retry policy (and not a retry signal)."""
    if isinstance(exc, (Ignore, Reject, Retry)):
        return False
    max_r: Optional[int] = getattr(task, "max_retries", None)
    if max_r is None:
        return False
    retries: int = int(getattr(getattr(task, "request", object()), "retries", 0) or 0)
    if retries < int(max_r):
        return False
    return True


def record_ingestion_task_failure(
    *,
    task_name: str,
    task_id: Optional[str],
    task_args: Tuple[Any, ...],
    task_kwargs: Dict[str, Any],
    exc: BaseException,
) -> None:
    from app.jobs import tasks  # local import: tasks imports this module

    name, message, rep = _exception_fields(exc)
    body = {
        "task_name": task_name,
        "task_id": task_id,
        "task_args": _serialize_args(task_args),
        "task_kwargs": _json_safe(task_kwargs),
        "exc_type": name,
        "exc_message": message,
        "exc_repr": rep,
    }
    try:
        tasks.build_ingestion_repository().append_ingestion_task_failure(body)
    except Exception:
        logger.exception("ingestion.dlq.append_failed", extra={"task_id": task_id, "task_name": task_name})
        return
    line = {
        "task_name": task_name,
        "task_id": task_id,
        "exc_type": name,
    }
    logger.warning("ingestion.dlq.appended " + json.dumps(line, default=str, sort_keys=True))
