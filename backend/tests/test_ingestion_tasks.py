from app.jobs import tasks


def test_refresh_conditions_returns_metrics_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        tasks,
        "run_ingestion_pipeline",
        lambda store: {
            "raw_count": 3,
            "normalized_count": 3,
            "hazard_count": 4,
            "scored_count": 4,
            "deduped_count": 3,
            "persisted_count": 3,
            "error_count": 0,
            "trail_ids": [1, 2],
        },
    )
    monkeypatch.setattr(tasks, "build_ingestion_repository", lambda: object())
    monkeypatch.setattr(tasks, "invalidate_trail_conditions_cache", lambda trail_ids: len(trail_ids))

    payload = tasks.refresh_conditions._orig_run()
    assert payload["raw_count"] == 3
    assert payload["persisted_count"] == 3
    assert payload["cache_keys_invalidated"] == 2
    assert "task_id" in payload
    assert isinstance(payload["run_duration_ms"], float)
