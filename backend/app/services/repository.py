from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from app.services.in_memory_fallback import try_load_fallback_state


def _empty_in_memory_fallback() -> Dict[str, Any]:
    return {
        "snapshot_meta": {},
        "trails": [],
        "hazards": [],
        "reviews": [],
        "reports": [],
        "seasonal": {},
        "weather_cache": {},
    }


class InMemoryRepository:
    """Backed by Postgres for production runtime; fallback uses committed real-source snapshot."""

    snapshot_meta: Dict[str, Any]

    def __init__(self, use_fallback_snapshot: bool = True) -> None:
        self.ingestion_task_failures = []
        self.source_fetch_log: set[tuple[str, str, Optional[date], Optional[date], str]] = set()
        self.snapshot_meta = {}
        if use_fallback_snapshot:
            state = try_load_fallback_state()
            if state is not None:
                self._hydrate(state)
                return
        self._hydrate(_empty_in_memory_fallback())

    def _hydrate(self, state: Dict[str, Any]) -> None:
        meta = state.get("snapshot_meta")
        self.snapshot_meta = meta if isinstance(meta, dict) else {}
        self.trails = list(state.get("trails") or [])
        self.hazards = list(state.get("hazards") or [])
        self.reports = list(state.get("reports") or [])
        self.reviews = list(state.get("reviews") or [])
        self.seasonal = dict(state.get("seasonal") or {})
        wc_raw = state.get("weather_cache")
        self.weather_cache: Dict[tuple[int, str], Dict[str, Any]] = dict(wc_raw or {})

    def _matches_location_filters(
        self,
        trail: Dict,
        state_code: Optional[str] = None,
        city: Optional[str] = None,
        park_type: Optional[str] = None,
        park_name_contains: Optional[str] = None,
    ) -> bool:
        location = trail.get("location") or {}

        if state_code and location.get("state_code", "").lower() != state_code.lower():
            return False
        if city and location.get("city", "").lower() != city.lower():
            return False
        if park_type and location.get("park_type", "").lower() != park_type.lower():
            return False
        if park_name_contains and park_name_contains.lower() not in location.get("park_name", "").lower():
            return False
        return True

    def _has_non_synthetic_geometry(self, trail: Dict) -> bool:
        geometry_quality = str(trail.get("geometry_quality") or "").strip().lower()
        if geometry_quality == "synthetic":
            return False
        data_quality_status = str(trail.get("data_quality_status") or "").strip().lower()
        if data_quality_status == "demo_synthetic":
            return False
        return True

    def search_trails(
        self,
        query: str,
        limit: int = 10,
        state_code: Optional[str] = None,
        city: Optional[str] = None,
        park_type: Optional[str] = None,
        park_name_contains: Optional[str] = None,
    ) -> List[Dict]:
        q = query.strip().lower()
        matches = [
            t
            for t in self.trails
            if q in t["name"].lower()
            and self._matches_location_filters(
                t,
                state_code=state_code,
                city=city,
                park_type=park_type,
                park_name_contains=park_name_contains,
            )
        ]
        ranked = sorted(
            matches,
            key=lambda trail: self._search_rank(trail["name"], q),
        )
        return ranked[:limit]

    def _search_rank(self, trail_name: str, normalized_query: str) -> tuple[int, int, int, str]:
        lowered_name = trail_name.lower()
        if lowered_name == normalized_query:
            priority = 0
        elif lowered_name.startswith(normalized_query):
            priority = 1
        elif f" {normalized_query}" in lowered_name:
            priority = 2
        else:
            priority = 3
        return (priority, lowered_name.find(normalized_query), len(trail_name), lowered_name)

    def get_trail(self, trail_id: int) -> Optional[Dict]:
        return next((t for t in self.trails if t["id"] == trail_id), None)

    def nearby_trails(
        self,
        lat: float,
        lng: float,
        km: float,
        state_code: Optional[str] = None,
        city: Optional[str] = None,
        park_type: Optional[str] = None,
        park_name_contains: Optional[str] = None,
    ) -> List[Dict]:
        max_distance = km / 111.0
        hits = []
        for trail in self.trails:
            if not self._has_non_synthetic_geometry(trail):
                continue
            lat_delta = abs(trail["lat"] - lat)
            lng_delta = abs(trail["lng"] - lng)
            if (
                lat_delta <= max_distance
                and lng_delta <= max_distance
                and self._matches_location_filters(
                    trail,
                    state_code=state_code,
                    city=city,
                    park_type=park_type,
                    park_name_contains=park_name_contains,
                )
            ):
                hits.append(trail)
        return hits

    def get_hazards(self, trail_id: int, active_only: bool = True) -> List[Dict]:
        rows = [h for h in self.hazards if h["trail_id"] == trail_id]
        if active_only:
            rows = [h for h in rows if h["resolved_at"] is None]
        enriched_rows = []
        for row in rows:
            location = row.get("location")
            enriched = {**row, "has_location": bool(location)}
            if isinstance(location, dict):
                enriched["lat"] = location.get("lat")
                enriched["lng"] = location.get("lng")
            enriched_rows.append(enriched)
        return enriched_rows

    def get_trail_route_geojson(self, trail_id: int) -> Optional[Dict]:
        trail = self.get_trail(trail_id)
        if not trail:
            return None

        coords = trail.get("route_coordinates")
        if isinstance(coords, list) and len(coords) >= 2:
            return {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "trailId": trail["id"],
                    "name": trail["name"],
                    "geometryQuality": trail.get("geometry_quality") or "imported_snapshot",
                    "geometrySource": trail.get("geometry_source") or "in_memory_fallback_snapshot.json",
                    "geometrySourceUrl": trail.get("geometry_source_url"),
                },
            }

        if trail.get("lat") is None or trail.get("lng") is None:
            return None

        lng = float(trail["lng"])
        lat = float(trail["lat"])
        return {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[lng, lat], [lng + 0.002, lat + 0.002]]},
            "properties": {
                "trailId": trail["id"],
                "name": trail["name"],
                "geometryQuality": "stale_point_stub",
                "geometrySource": "snapshot trail centroid stub (missing route_coordinates)",
                "geometrySourceUrl": trail.get("geometry_source_url"),
            },
        }

    def get_hazards_geojson(self, trail_id: int) -> Dict:
        hazards = self.get_hazards(trail_id=trail_id, active_only=True)
        features = []
        for hazard in hazards:
            trail = self.get_trail(hazard["trail_id"])
            if not trail:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [trail["lng"], trail["lat"]]},
                    "properties": {
                        "hazard_id": hazard["id"],
                        "type": hazard["type"],
                        "severity": hazard["severity"],
                    },
                }
            )
        return {"type": "FeatureCollection", "features": features}

    def get_recent_reports(self, trail_id: int, limit: int = 5) -> List[Dict]:
        rows = [r for r in self.reports if r["trail_id"] == trail_id]
        rows.sort(key=lambda r: r["reported_at"], reverse=True)
        return rows[:limit]

    def get_seasonal(self, trail_id: int) -> Optional[Dict]:
        return self.seasonal.get(trail_id)

    def get_recent_reviews(self, trail_id: int, limit: int = 10) -> List[Dict]:
        rows = [r for r in self.reviews if r["trail_id"] == trail_id]
        rows.sort(key=lambda r: r["scraped_at"], reverse=True)
        return rows[:limit]

    def persist_reviews(self, reviews: Sequence[Dict]) -> int:
        if not reviews:
            return 0
        existing_ids = {
            (row["source_platform"], row.get("external_review_id"))
            for row in self.reviews
            if row.get("external_review_id")
        }
        next_id = max([r["id"] for r in self.reviews], default=0) + 1
        inserted = 0
        for review in reviews:
            dedupe_key = (review["source_platform"], review.get("external_review_id"))
            if review.get("external_review_id") and dedupe_key in existing_ids:
                continue
            self.reviews.append(
                {
                    "id": next_id,
                    "trail_id": review["trail_id"],
                    "source_platform": review["source_platform"],
                    "external_review_id": review.get("external_review_id"),
                    "source_url": review.get("source_url"),
                    "rating": review.get("rating"),
                    "text": review.get("text"),
                    "sentiment_score": review.get("sentiment_score"),
                    "scraped_at": review.get("scraped_at", datetime.now(tz=timezone.utc)),
                    "author_handle": review.get("author_handle"),
                }
            )
            if review.get("external_review_id"):
                existing_ids.add(dedupe_key)
            next_id += 1
            inserted += 1
        return inserted

    def get_weather_cache(self, trail_id: int, provider: str) -> Optional[Dict]:
        row = self.weather_cache.get((trail_id, provider))
        if not row:
            return None
        if row["expires_at"] <= datetime.now(tz=timezone.utc):
            return None
        return dict(row)

    def upsert_weather_cache(
        self,
        trail_id: int,
        provider: str,
        summary: str,
        temperature_c: Optional[float],
        wind_kph: Optional[float],
        fetched_at: datetime,
        expires_at: datetime,
    ) -> Dict:
        row = {
            "trail_id": trail_id,
            "provider": provider,
            "summary": summary,
            "temperature_c": temperature_c,
            "wind_kph": wind_kph,
            "fetched_at": fetched_at,
            "expires_at": expires_at,
        }
        self.weather_cache[(trail_id, provider)] = row
        return dict(row)

    def has_fetch_log(
        self,
        source_name: str,
        fetch_scope: str,
        period_start: Optional[date],
        period_end: Optional[date],
        content_hash: str,
    ) -> bool:
        return (source_name, fetch_scope, period_start, period_end, content_hash) in self.source_fetch_log

    def record_fetch_log(
        self,
        source_name: str,
        fetch_scope: str,
        period_start: Optional[date],
        period_end: Optional[date],
        content_hash: str,
    ) -> None:
        self.source_fetch_log.add((source_name, fetch_scope, period_start, period_end, content_hash))

    def add_report(
        self, trail_id: int, condition_tags: List[str], notes: Optional[str], reporter_name: Optional[str]
    ) -> Dict:
        next_id = max([r["id"] for r in self.reports], default=0) + 1
        row = {
            "id": next_id,
            "trail_id": trail_id,
            "condition_tags": condition_tags,
            "notes": notes,
            "reporter_name": reporter_name,
            "reported_at": datetime.now(tz=timezone.utc),
            "upvotes": 0,
            "moderation_status": "pending",
            "moderated_at": None,
        }
        self.reports.append(row)
        return row

    def upvote_report(self, report_id: int) -> Optional[Dict]:
        row = next((r for r in self.reports if r["id"] == report_id), None)
        if not row:
            return None
        row["upvotes"] += 1
        return row

    def resolve_report(self, report_id: int) -> bool:
        row = next((r for r in self.reports if r["id"] == report_id), None)
        if not row:
            return False
        row["moderation_status"] = "resolved"
        row["moderated_at"] = datetime.now(tz=timezone.utc)
        return True

    def get_hazards_for_dedupe(self, trail_ids: Sequence[int], since: datetime) -> List[Dict]:
        if not trail_ids:
            return []
        return [
            hazard
            for hazard in self.hazards
            if hazard["trail_id"] in trail_ids and hazard["reported_at"] >= since and hazard["resolved_at"] is None
        ]

    def persist_hazards(self, hazards: Sequence[Dict]) -> int:
        if not hazards:
            return 0
        next_id = max([hazard["id"] for hazard in self.hazards], default=0) + 1
        for hazard in hazards:
            self.hazards.append(
                {
                    "id": next_id,
                    "trail_id": hazard["trail_id"],
                    "type": hazard["type"],
                    "severity": hazard["severity"],
                    "source": hazard["source"],
                    "confidence": hazard["confidence"],
                    "reported_at": hazard["reported_at"],
                    "raw_text": hazard.get("raw_text"),
                    "resolved_at": None,
                }
            )
            next_id += 1
        return len(hazards)

    def append_ingestion_task_failure(self, record: Dict[str, Any]) -> Dict[str, Any]:
        next_id = max((row["id"] for row in self.ingestion_task_failures), default=0) + 1
        row: Dict[str, Any] = {
            "id": next_id,
            "task_name": record["task_name"],
            "task_id": record.get("task_id"),
            "task_args": record.get("task_args", []),
            "task_kwargs": record.get("task_kwargs", {}),
            "exc_type": record.get("exc_type", "Exception"),
            "exc_message": record.get("exc_message", ""),
            "exc_repr": record.get("exc_repr", ""),
            "created_at": datetime.now(tz=timezone.utc),
        }
        self.ingestion_task_failures.append(row)
        return row

    def list_ingestion_task_failures(self, limit: int = 20) -> List[Dict[str, Any]]:
        return sorted(
            (dict(row) for row in self.ingestion_task_failures),
            key=lambda r: r["id"],
            reverse=True,
        )[: max(0, int(limit))]
