from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from urllib.error import URLError
from urllib.request import urlopen

PROVIDER = "open_meteo"
WEATHER_TTL_MINUTES = 5


def _build_summary(temperature_c: Optional[float], wind_kph: Optional[float]) -> str:
    if temperature_c is None and wind_kph is None:
        return "Current weather unavailable."
    if temperature_c is None:
        return f"Wind near {wind_kph:.1f} kph."
    if wind_kph is None:
        return f"Temperature near {temperature_c:.1f} C."
    return f"Around {temperature_c:.1f} C with winds near {wind_kph:.1f} kph."


def _fetch_open_meteo(lat: float, lng: float) -> Dict[str, Optional[float]]:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lng}&current=temperature_2m,wind_speed_10m"
    )
    with urlopen(url, timeout=8) as response:  # nosec: B310
        payload = json.loads(response.read().decode("utf-8"))
    current = payload.get("current", {})
    return {
        "temperature_c": current.get("temperature_2m"),
        "wind_kph": current.get("wind_speed_10m"),
    }


def get_trail_weather(repo, trail_id: int) -> Optional[Dict]:
    cached = repo.get_weather_cache(trail_id=trail_id, provider=PROVIDER)
    trail = repo.get_trail(trail_id)
    if not trail:
        return None
    lat = trail.get("lat")
    lng = trail.get("lng")
    if cached:
        # If a prior cached fallback was written because coordinates were missing,
        # refresh immediately once real coordinates become available.
        summary = str(cached.get("summary", ""))
        if not (
            summary.startswith("Current weather unavailable: trail coordinates are missing.")
            and lat is not None
            and lng is not None
        ):
            return cached

    now = datetime.now(tz=timezone.utc)
    if lat is None or lng is None:
        # Keep UI contract stable for all hikes even when trail geometry/coords are missing.
        return repo.upsert_weather_cache(
            trail_id=trail_id,
            provider=PROVIDER,
            summary="Current weather unavailable: trail coordinates are missing.",
            temperature_c=None,
            wind_kph=None,
            fetched_at=now,
            expires_at=now + timedelta(minutes=WEATHER_TTL_MINUTES),
        )

    try:
        latest = _fetch_open_meteo(lat=lat, lng=lng)
        summary = _build_summary(latest.get("temperature_c"), latest.get("wind_kph"))
    except (TimeoutError, URLError, ValueError):
        # Persist brief fallback so repeated failures do not repeatedly hit provider.
        latest = {"temperature_c": None, "wind_kph": None}
        summary = "Current weather unavailable from provider."

    return repo.upsert_weather_cache(
        trail_id=trail_id,
        provider=PROVIDER,
        summary=summary,
        temperature_c=latest.get("temperature_c"),
        wind_kph=latest.get("wind_kph"),
        fetched_at=now,
        expires_at=now + timedelta(minutes=WEATHER_TTL_MINUTES),
    )
