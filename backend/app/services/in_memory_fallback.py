"""Committed real-source snapshot for Postgres-offline API fallback."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

logger = logging.getLogger(__name__)

FALLBACK_JSON = "in_memory_fallback_snapshot.json"


def fallback_snapshot_default_path() -> Path:
    custom = os.getenv("IN_MEMORY_FALLBACK_SNAPSHOT_PATH", "").strip()
    if custom:
        return Path(custom).expanduser().resolve()
    # backend/app/services -> parents[2] == backend
    return Path(__file__).resolve().parents[2] / "data" / FALLBACK_JSON


def parse_snapshot_datetime(raw: Any) -> datetime:
    """Parse timestamps written by rebuild_snapshot (ISO-ish or Postgres-style)."""
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, str):
        text = raw.strip().replace("Z", "+00:00")
        parsed: Optional[datetime] = None
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            for fmt in (
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    parsed = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue
        if parsed is None:
            parsed = datetime.now(tz=timezone.utc)
        dt = parsed
    else:
        dt = datetime.now(tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def wkt_linestring_to_coordinates(wkt: str) -> list[list[float]]:
    """Return [[lng, lat], ...] from LINESTRING(lng lat, ...) WKT."""
    inner = wkt.strip()
    if not inner.upper().startswith("LINESTRING("):
        return []
    inner = inner[inner.index("(") + 1 : inner.rindex(")")]
    out: list[list[float]] = []
    for pair in inner.split(","):
        parts = pair.strip().split()
        if len(parts) >= 2:
            out.append([float(parts[0]), float(parts[1])])
    return out


def load_fallback_snapshot_document(path: Path) -> Dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("fallback snapshot root must be an object")
    return raw


def trails_from_snapshot_rows(rows: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    normalized: list[Dict[str, Any]] = []
    for row in rows:
        route_coordinates = row.get("route_coordinates")
        lat, lng = row.get("lat"), row.get("lng")
        if (lat is None or lng is None) and isinstance(route_coordinates, list) and len(route_coordinates) > 0:
            trailhead = route_coordinates[0]
            lng, lat = float(trailhead[0]), float(trailhead[1])
        normalized.append(
            {
                **row,
                "lat": float(lat) if lat is not None else None,
                "lng": float(lng) if lng is not None else None,
            }
        )
    return normalized


def hazards_from_snapshot_rows(rows: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    hazards: list[Dict[str, Any]] = []
    for row in rows:
        hazards.append(
            {
                **row,
                "reported_at": parse_snapshot_datetime(row.get("reported_at")),
                "resolved_at": None,
                "confidence": float(row.get("confidence", 0.75)),
            }
        )
    return hazards


def reports_from_snapshot_rows(rows: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    out: list[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                **row,
                "reported_at": parse_snapshot_datetime(row.get("reported_at")),
                "moderated_at": parse_snapshot_datetime(row["moderated_at"])
                if row.get("moderated_at")
                else None,
            }
        )
    return out


def reviews_from_snapshot_rows(rows: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    out: list[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                **row,
                "scraped_at": parse_snapshot_datetime(row.get("scraped_at")),
                "rating": row.get("rating"),
                "sentiment_score": float(row["sentiment_score"]) if row.get("sentiment_score") is not None else None,
            }
        )
    return out


def seasonal_from_snapshot(raw: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for key, value in raw.items():
        try:
            tid = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            out[tid] = dict(value)
    return out


def weather_cache_from_snapshot(entries: Iterable[Dict[str, Any]]) -> Dict[tuple[int, str], Dict[str, Any]]:
    out: Dict[tuple[int, str], Dict[str, Any]] = {}
    for row in entries:
        tid = int(row["trail_id"])
        provider = str(row["provider"])
        out[(tid, provider)] = {
            "trail_id": tid,
            "provider": provider,
            "summary": row.get("summary"),
            "temperature_c": row.get("temperature_c"),
            "wind_kph": row.get("wind_kph"),
            "fetched_at": parse_snapshot_datetime(row.get("fetched_at")),
            "expires_at": parse_snapshot_datetime(row.get("expires_at")),
        }
    return out


def try_load_fallback_state(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Returns keyword args / state blobs for InMemoryRepository, or None."""
    snapshot_path = path or fallback_snapshot_default_path()
    if not snapshot_path.is_file():
        logger.warning(
            "Missing fallback snapshot at %s. Run backend/scripts/rebuild_real_data.py.",
            snapshot_path,
        )
        return None
    try:
        doc = load_fallback_snapshot_document(snapshot_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.error("Cannot read fallback snapshot %s: %s", snapshot_path, exc)
        return None

    trails = trails_from_snapshot_rows(doc.get("trails") or [])
    return {
        "snapshot_meta": {k: doc.get(k) for k in ("snapshot_version", "captured_at", "sources", "notes") if k in doc},
        "trails": trails,
        "hazards": hazards_from_snapshot_rows(doc.get("hazards") or []),
        "reviews": reviews_from_snapshot_rows(doc.get("reviews") or []),
        "reports": reports_from_snapshot_rows(doc.get("reports") or []),
        "seasonal": seasonal_from_snapshot(doc.get("seasonal") or {}),
        "weather_cache": weather_cache_from_snapshot(doc.get("weather_cache") or []),
    }

