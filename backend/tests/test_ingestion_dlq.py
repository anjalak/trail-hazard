from __future__ import annotations

from types import SimpleNamespace

from celery.exceptions import Retry

from app.jobs import tasks
from app.jobs.ingestion_dlq import record_ingestion_task_failure, should_record_ingestion_dlq
from app.services.repository import InMemoryRepository


def test_should_record_ingestion_dlq_terminal_vs_nonterminal() -> None:
    class _Task:
        def __init__(self, max_retries, retries) -> None:
            self.max_retries = max_retries
            self.request = type("R", (), {"retries": retries})()

    assert not should_record_ingestion_dlq(_Task(5, 0), ValueError("x"))
    assert not should_record_ingestion_dlq(_Task(5, 4), ValueError("x"))
    assert should_record_ingestion_dlq(_Task(5, 5), ValueError("x"))


def test_should_record_ingestion_dlq_ignores_retry_control_exceptions() -> None:
    class _Task:
        max_retries = 5
        request = type("R", (), {"retries": 5})()

    assert not should_record_ingestion_dlq(_Task(), Retry("retry"))  # type: ignore[call-arg]


def test_handle_ingestion_task_failure_persists_terminal_run(monkeypatch) -> None:
    store = InMemoryRepository()
    monkeypatch.setattr(tasks, "build_ingestion_repository", lambda: store)
    task = SimpleNamespace(
        name="app.jobs.tasks.refresh_conditions",
        max_retries=5,
        request=SimpleNamespace(retries=5),
    )
    tasks._handle_ingestion_task_failure(
        task, ValueError("store persist failed"), "tid-9", (1, 2), {"k": 1}, None
    )
    assert len(store.ingestion_task_failures) == 1
    row = store.ingestion_task_failures[0]
    assert row["task_id"] == "tid-9"
    assert row["task_args"] == [1, 2]
    assert row["task_kwargs"] == {"k": 1}
    assert row["exc_type"] == "ValueError"


def test_record_ingestion_task_failure_does_not_raise_when_append_fails(caplog, monkeypatch) -> None:
    class _Bad:
        def append_ingestion_task_failure(self, record) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("db unavailable")

    monkeypatch.setattr(tasks, "build_ingestion_repository", lambda: _Bad())
    with caplog.at_level("ERROR", logger="trailintel.ingestion.dlq"):
        record_ingestion_task_failure(
            task_name="t",
            task_id="t1",
            task_args=(),
            task_kwargs={},
            exc=ValueError("ingestion run failed after retries"),
        )
    assert "ingestion.dlq.append_failed" in caplog.text or "db unavailable" in caplog.text
