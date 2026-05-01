from datetime import datetime, timezone

from app.services.ingestion import (
    StaticHazardSourceAdapter,
    dedupe_hazards,
    extract_hazards,
    normalize_payload,
    run_ingestion_pipeline,
)
from app.services.repository import InMemoryRepository


def test_extract_hazards_maps_keywords() -> None:
    repo = InMemoryRepository()
    normalized = normalize_payload(
        store=repo,
        raw={
            "trail_id": 1,
            "source": "scraped",
            "text": "Snow above 3000ft and muddy sections below tree line",
            "confidence": 0.8,
        },
    )
    hazards = extract_hazards(normalized)
    types = {hazard["type"] for hazard in hazards}
    assert {"snow", "muddy_sections"} <= types


def test_source_adapter_returns_seeded_payloads() -> None:
    seeded = [{"trail_id": 2, "source": "scraped", "text": "Washout reported", "confidence": 0.88}]
    adapter = StaticHazardSourceAdapter(seeded_payloads=seeded)
    assert adapter.fetch() == seeded


def test_dedupe_hazards_filters_existing_and_same_run_duplicates() -> None:
    reported_at = datetime(2026, 4, 27, tzinfo=timezone.utc)
    existing = [
        {
            "trail_id": 1,
            "type": "snow",
            "reported_at": reported_at,
            "raw_text": "Fresh snow near ridge",
        }
    ]
    candidates = [
        {
            "trail_id": 1,
            "type": "snow",
            "reported_at": reported_at,
            "raw_text": "Fresh snow near ridge",
            "source": "scraped",
            "severity": "medium",
            "confidence": 0.9,
        },
        {
            "trail_id": 1,
            "type": "snow",
            "reported_at": reported_at,
            "raw_text": "Fresh snow near ridge",
            "source": "scraped",
            "severity": "medium",
            "confidence": 0.9,
        },
        {
            "trail_id": 1,
            "type": "wildlife",
            "reported_at": reported_at,
            "raw_text": "Bear seen near lake",
            "source": "scraped",
            "severity": "low",
            "confidence": 0.7,
        },
    ]
    deduped = dedupe_hazards(candidates=candidates, existing=existing)
    assert len(deduped) == 1
    assert deduped[0]["type"] == "wildlife"


def test_run_ingestion_pipeline_persists_deduped_hazards() -> None:
    baseline_time = datetime(2026, 4, 27, tzinfo=timezone.utc)
    repo = InMemoryRepository(use_fallback_snapshot=False)
    existing_count = len(repo.hazards)
    adapters = [
        StaticHazardSourceAdapter(
            seeded_payloads=[
                {
                    "trail_id": 1,
                    "source": "scraped",
                    "text": "Patchy snow near upper switchbacks",
                    "reported_at": baseline_time,
                    "confidence": 0.82,
                },
                {
                    "trail_id": 2,
                    "source": "scraped",
                    "text": "Muddy sections and tree debris on lower trail",
                    "confidence": 0.79,
                },
            ]
        )
    ]
    results = run_ingestion_pipeline(store=repo, adapters=adapters)
    assert results["raw_count"] == 2
    assert results["deduped_count"] == 3
    assert results["persisted_count"] == 3
    assert len(repo.hazards) == existing_count + 3
