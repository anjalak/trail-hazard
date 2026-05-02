from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from app.services.weather import get_trail_weather

SEVERITY_WEIGHT = {"low": 0.5, "medium": 0.75, "high": 1.0}
SOURCE_WEIGHT = {"user": 0.8, "scraped": 0.7, "cv_pipeline": 0.95}
FRESHNESS_WINDOW_HOURS = 168


def ensure_utc_datetime(dt: datetime) -> datetime:
    """Normalize for comparisons; naive values are treated as UTC (NPS exports often omit offsets)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def hazard_score(report: Dict) -> float:
    now = datetime.now(tz=timezone.utc)
    raw_ra = report["reported_at"]
    reported_at = ensure_utc_datetime(raw_ra) if isinstance(raw_ra, datetime) else now
    days_old = (now - reported_at).days
    recency_weight = 1 / (1 + days_old * 0.3)
    # Postgres NUMERIC values can arrive as Decimal; normalize before float math.
    confidence = float(report.get("confidence", 0.75))
    severity_weight = SEVERITY_WEIGHT.get(report.get("severity", "low"), 0.5)
    source_weight = SOURCE_WEIGHT.get(report.get("source", "user"), 0.8)
    return confidence * recency_weight * severity_weight * source_weight


def build_conditions(repo, trail_id: int) -> Optional[Dict]:
    trail = repo.get_trail(trail_id)
    if not trail:
        return None

    hazards = repo.get_hazards(trail_id=trail_id, active_only=True)
    reports = repo.get_recent_reports(trail_id=trail_id, limit=5)
    seasonal = repo.get_seasonal(trail_id)
    weather = get_trail_weather(repo=repo, trail_id=trail_id)
    now = datetime.now(tz=timezone.utc)

    if hazards:
        highest = max(hazards, key=lambda h: SEVERITY_WEIGHT.get(h["severity"], 0.5))
        overall = sum(hazard_score(h) for h in hazards)
        overall_score = max(1, min(100, int(overall * 100)))
    else:
        highest = {"severity": "low"}
        overall_score = 5

    recent_hazard_count = sum(
        1
        for hazard in hazards
        if (now - hazard["reported_at"]).total_seconds() <= FRESHNESS_WINDOW_HOURS * 3600
    )

    return {
        "trail_id": trail["id"],
        "name": trail["name"],
        "region": trail["region"],
        "location": trail.get("location"),
        "lat": trail.get("lat"),
        "lng": trail.get("lng"),
        "overall_score": overall_score,
        "hazard_summary": {
            "active_count": len(hazards),
            "highest_severity": highest["severity"],
            "types": sorted(list({h["type"] for h in hazards})),
        },
        "active_hazards": hazards[:8],
        "recent_hazard_count": recent_hazard_count,
        "has_recent_info": recent_hazard_count > 0,
        "seasonal_intel": seasonal,
        "recent_reports": reports,
        "weather_snapshot": weather,
        "last_updated": now,
    }
