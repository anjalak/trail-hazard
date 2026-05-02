from datetime import datetime, timedelta, timezone

from app.services.hazard_scoring import hazard_score


def test_recent_high_severity_scores_higher_than_old_low_severity() -> None:
    now = datetime.now(tz=timezone.utc)
    recent_high = {
        "reported_at": now - timedelta(days=1),
        "confidence": 0.9,
        "severity": "high",
        "source": "scraped",
    }
    old_low = {
        "reported_at": now - timedelta(days=10),
        "confidence": 0.7,
        "severity": "low",
        "source": "user",
    }
    assert hazard_score(recent_high) > hazard_score(old_low)


def test_hazard_score_accepts_naive_reported_at_as_utc() -> None:
    """NPS JSON exports often omit timezone; scoring must not mix naive and aware datetimes."""
    naive = datetime(2026, 4, 17, 0, 0, 0)
    assert naive.tzinfo is None
    score = hazard_score(
        {
            "reported_at": naive,
            "confidence": 0.86,
            "severity": "medium",
            "source": "scraped",
        }
    )
    assert isinstance(score, float)
    assert score > 0
