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
