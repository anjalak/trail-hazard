from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import re
from typing import Any, List, Optional, Union

import strawberry
from strawberry.scalars import JSON
from strawberry.fastapi import BaseContext
from strawberry.types import Info

from app.services.hazard_scoring import build_conditions
from app.services.postgres_repository import PostgresRepository
from app.services.trail_dedupe import dedupe_trails_preserve_order
from app.services.report_rate_limit import check_report_mutation
from app.services.repository import InMemoryRepository
from app.services.robotics import build_robotics_area, build_robotics_traversability


@strawberry.type
class TrailLocation:
    state_code: str
    city: Optional[str]
    park_name: Optional[str]
    park_type: Optional[str]
    county: Optional[str]


@strawberry.type
class Trail:
    id: int
    name: str
    region: str
    location: Optional[TrailLocation]
    lat: Optional[float]
    lng: Optional[float]
    difficulty: str
    length_km: float
    elevation_gain_m: int
    traversability_score: float
    route_coordinates: Optional[JSON] = None  # GeoJSON [[lng, lat], …] from trail.geom when available


@strawberry.type
class Hazard:
    id: int
    type: str
    severity: str
    source: str
    confidence: float
    reported_at: datetime
    raw_text: Optional[str]


@strawberry.type
class Report:
    id: int
    trail_id: int
    condition_tags: List[str]
    notes: Optional[str]
    reporter_name: Optional[str]
    reported_at: datetime
    upvotes: int
    moderation_status: str = "pending"
    moderated_at: Optional[datetime] = None


@strawberry.type
class Review:
    id: int
    trail_id: int
    source_platform: str
    external_review_id: Optional[str]
    source_url: Optional[str]
    rating: Optional[float]
    text: Optional[str]
    sentiment_score: Optional[float]
    scraped_at: datetime
    author_handle: Optional[str]


@strawberry.type
class WeatherSnapshot:
    provider: str
    summary: str
    temperature_c: Optional[float]
    wind_kph: Optional[float]
    fetched_at: datetime
    expires_at: datetime


@strawberry.type
class HazardSummary:
    active_count: int
    highest_severity: str
    types: List[str]


@strawberry.type
class SeasonalIntel:
    month: int
    wildlife_alerts: str
    plant_warnings: str
    gear_recommendations: List[str]
    avg_temp_c: float
    avg_snowpack_cm: float


@strawberry.type
class TrailConditions:
    trail_id: int
    name: str
    region: str
    location: Optional[TrailLocation]
    lat: Optional[float]
    lng: Optional[float]
    overall_score: int
    hazard_summary: HazardSummary
    active_hazards: List[Hazard]
    recent_hazard_count: int
    has_recent_info: bool
    seasonal_intel: Optional[SeasonalIntel]
    recent_reports: List[Report]
    weather_snapshot: Optional[WeatherSnapshot]
    last_updated: datetime


@strawberry.type
class RoboticsDataFreshness:
    generated_at: datetime
    latest_hazard_at: Optional[datetime]
    source_count: int
    stale: bool


@strawberry.type
class RoboticsTraversability:
    trail_id: int
    name: str
    route_geojson: JSON
    hazards_geojson: JSON
    hazard_summary: HazardSummary
    data_freshness: RoboticsDataFreshness
    geometry_quality: str
    geometry_source: str
    vertex_count: int
    ros_compatible_route: JSON
    traversability_score: float
    risk_score: float
    effort_score: float
    segment_costs: JSON
    elevation_profile: JSON
    cost_model: JSON
    hazard_location_quality: str
    planning_notes: List[str]


@strawberry.type
class RoboticsAreaCenter:
    lat: float
    lng: float


@strawberry.type
class RoboticsAreaTrail:
    trail_id: int
    name: str
    traversability_score: float
    risk_score: float
    effort_score: float
    active_hazard_count: int
    hazard_location_quality: str


@strawberry.type
class RoboticsArea:
    center: RoboticsAreaCenter
    radius_m: float
    active_hazard_count: int
    hazard_density: float
    area_risk_score: float
    highest_risk_trail: Optional[RoboticsAreaTrail]
    recommended_trail_ids: List[int]
    trails: List[RoboticsAreaTrail]
    generated_at: datetime


@strawberry.input
class SubmitReportInput:
    trail_id: int
    condition_tags: List[str]
    notes: Optional[str] = None
    reporter_name: Optional[str] = None


@dataclass
class Context(BaseContext):
    repo: Union[InMemoryRepository, PostgresRepository]


def _seasonal_json_field_as_str(value: Any) -> str:
    """Postgres JSONB may deserialize to list/dict; GraphQL exposes these as strings."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _seasonal_numeric(value: Any) -> float:
    return float(value) if value is not None else 0.0


def _seasonal_gear_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


ALLOWED_REPORT_TAGS = {
    "snow",
    "windy",
    "muddy",
    "washout",
    "wildlife",
    "ice",
    "flooded",
    "fallen_trees",
    "clear",
    "rockfall",
}
MAX_REPORT_NOTE_LENGTH = 500
_TEXT_SANITIZE_PATTERN = re.compile(r"[^\x20-\x7E\n\t]")
_MULTI_SPACE_PATTERN = re.compile(r"[ \t]{2,}")


def _client_id_from_info(info: Info[Context, Any]) -> str:
    req = getattr(info.context, "request", None)
    if req is None:
        return "unknown"
    headers = getattr(req, "headers", None)
    if headers:
        forwarded = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()[:256]
    client = getattr(req, "client", None)
    host = getattr(client, "host", None) if client else None
    return str(host) if host else "unknown"


def _sanitize_text(value: Optional[str], max_length: int) -> Optional[str]:
    if value is None:
        return None

    sanitized = _TEXT_SANITIZE_PATTERN.sub("", value).strip()
    sanitized = _MULTI_SPACE_PATTERN.sub(" ", sanitized)
    if len(sanitized) > max_length:
        raise ValueError(f"notes must be at most {max_length} characters")
    return sanitized or None


def _validate_condition_tags(tags: List[str]) -> List[str]:
    normalized_tags = [tag.strip().lower() for tag in tags if tag.strip()]
    if not normalized_tags:
        raise ValueError("condition_tags must include at least one non-empty tag")

    disallowed = sorted({tag for tag in normalized_tags if tag not in ALLOWED_REPORT_TAGS})
    if disallowed:
        raise ValueError(f"condition_tags include unsupported tags: {', '.join(disallowed)}")
    return normalized_tags


def _geojson_coordinate_visit(coords: Any, out: List[tuple[float, float]], *, max_pts: int) -> None:
    """Collect [lng, lat] tuples from GeoJSON CoordinateArrays (LineString vs nested Multi-/Polygon shells)."""

    def maybe_pair(a: Any, b: Any) -> None:
        if len(out) >= max_pts:
            return
        try:
            xf, yf = float(a), float(b)
        except (TypeError, ValueError):
            return
        if _looks_like_lng_lat(xf, yf):
            out.append((xf, yf))
        elif _looks_like_lng_lat(yf, xf):
            out.append((yf, xf))
        elif -180.0 <= xf <= 180.0 and -90.0 <= yf <= 90.0:
            out.append((xf, yf))

    if coords is None or not isinstance(coords, list) or not coords:
        return
    head = coords[0]
    if isinstance(head, (int, float)) and len(coords) >= 2 and isinstance(coords[1], (int, float)):
        maybe_pair(coords[0], coords[1])
        return
    for child in coords:
        if len(out) >= max_pts:
            break
        if isinstance(child, (list, tuple)):
            _geojson_coordinate_visit(child, out, max_pts=max_pts)


_WA_ROUGH_LNG = (-130.5, -115.8)
_WA_ROUGH_LAT = (41.5, 52.5)


def _looks_like_lng_lat(lng_f: float, lat_f: float) -> bool:
    return (
        _WA_ROUGH_LNG[0] <= lng_f <= _WA_ROUGH_LNG[1]
        and _WA_ROUGH_LAT[0] <= lat_f <= _WA_ROUGH_LAT[1]
    )


def _sanitize_route_coordinates(raw: Any) -> Any:
    """Flatten nested GeoJSON coordinates to [[lng, lat], …] for LineString payloads; avoids bogus vertex chains."""
    if raw is None:
        return None

    if isinstance(raw, str):
        try:
            pts = json.loads(raw)
        except json.JSONDecodeError:
            return None
    else:
        pts = raw
    if not isinstance(pts, list) or not pts:
        return None

    max_pts = 500
    coords_list: List[tuple[float, float]] = []
    _geojson_coordinate_visit(pts, coords_list, max_pts=max_pts)
    cleaned: List[List[float]] = [[lng, lat] for lng, lat in coords_list]
    if not cleaned:
        return None

    if len(cleaned) > max_pts:
        step = math.ceil(len(cleaned) / max_pts)
        cleaned = cleaned[::step]
    return cleaned


def map_trail(row: dict) -> Trail:
    location = row.get("location")
    location_obj = TrailLocation(**location) if location else None
    route_coords_raw = row.get("route_coordinates")
    lat = row.get("lat")
    lng = row.get("lng")
    return Trail(
        id=row["id"],
        name=row["name"],
        region=row["region"],
        location=location_obj,
        lat=lat,
        lng=lng,
        difficulty=row["difficulty"],
        length_km=row["length_km"],
        elevation_gain_m=row["elevation_gain_m"],
        traversability_score=row["traversability_score"],
        route_coordinates=_sanitize_route_coordinates(route_coords_raw),
    )


def map_hazard(row: dict) -> Hazard:
    return Hazard(
        id=row["id"],
        type=row["type"],
        severity=row["severity"],
        source=row["source"],
        confidence=float(row["confidence"]),
        reported_at=row["reported_at"],
        raw_text=row.get("raw_text"),
    )


@strawberry.type
class Query:
    @strawberry.field
    def search_trails_by_name(
        self,
        info: Info[Context, Any],
        query: str,
        limit: int = 10,
        state_code: Optional[str] = None,
        city: Optional[str] = None,
        park_type: Optional[str] = None,
        park_name_contains: Optional[str] = None,
    ) -> List[Trail]:
        rows = info.context.repo.search_trails(
            query=query,
            limit=limit,
            state_code=state_code,
            city=city,
            park_type=park_type,
            park_name_contains=park_name_contains,
        )
        rows = dedupe_trails_preserve_order(rows)
        return [map_trail(row) for row in rows]

    @strawberry.field
    def trail(self, info: Info[Context, Any], id: int) -> Optional[Trail]:
        row = info.context.repo.get_trail(id)
        return map_trail(row) if row else None

    @strawberry.field
    def nearby_trails(
        self,
        info: Info[Context, Any],
        lat: float,
        lng: float,
        km: float,
        state_code: Optional[str] = None,
        city: Optional[str] = None,
        park_type: Optional[str] = None,
        park_name_contains: Optional[str] = None,
    ) -> List[Trail]:
        rows = info.context.repo.nearby_trails(
            lat=lat,
            lng=lng,
            km=km,
            state_code=state_code,
            city=city,
            park_type=park_type,
            park_name_contains=park_name_contains,
        )
        return [map_trail(row) for row in rows]

    @strawberry.field
    def trail_hazards(
        self, info: Info[Context, Any], trail_id: int, active_only: bool = True
    ) -> List[Hazard]:
        rows = info.context.repo.get_hazards(trail_id=trail_id, active_only=active_only)
        return [map_hazard(row) for row in rows]

    @strawberry.field
    def trail_hazards_geojson(self, info: Info[Context, Any], trail_id: int) -> JSON:
        return info.context.repo.get_hazards_geojson(trail_id=trail_id)

    @strawberry.field
    def trail_conditions(self, info: Info[Context, Any], trail_id: int) -> Optional[TrailConditions]:
        payload = build_conditions(info.context.repo, trail_id)
        if not payload:
            return None

        seasonal = payload["seasonal_intel"]
        seasonal_obj = None
        if seasonal:
            seasonal_obj = SeasonalIntel(
                month=int(seasonal["month"]),
                wildlife_alerts=_seasonal_json_field_as_str(seasonal.get("wildlife_alerts")),
                plant_warnings=_seasonal_json_field_as_str(seasonal.get("plant_warnings")),
                gear_recommendations=_seasonal_gear_list(seasonal.get("gear_recommendations")),
                avg_temp_c=_seasonal_numeric(seasonal.get("avg_temp_c")),
                avg_snowpack_cm=_seasonal_numeric(seasonal.get("avg_snowpack_cm")),
            )

        reports = [Report(**r) for r in payload["recent_reports"]]
        hazards = [map_hazard(row) for row in payload.get("active_hazards", [])]
        weather = payload.get("weather_snapshot")
        weather_obj = None
        if weather:
            weather_obj = WeatherSnapshot(
                provider=weather["provider"],
                summary=weather["summary"],
                temperature_c=weather.get("temperature_c"),
                wind_kph=weather.get("wind_kph"),
                fetched_at=weather["fetched_at"],
                expires_at=weather["expires_at"],
            )
        summary = HazardSummary(**payload["hazard_summary"])

        return TrailConditions(
            trail_id=payload["trail_id"],
            name=payload["name"],
            region=payload["region"],
            location=TrailLocation(**payload["location"]) if payload.get("location") else None,
            lat=payload.get("lat"),
            lng=payload.get("lng"),
            overall_score=payload["overall_score"],
            hazard_summary=summary,
            active_hazards=hazards,
            recent_hazard_count=payload.get("recent_hazard_count", 0),
            has_recent_info=payload.get("has_recent_info", False),
            seasonal_intel=seasonal_obj,
            recent_reports=reports,
            weather_snapshot=weather_obj,
            last_updated=payload.get("last_updated", datetime.now(tz=timezone.utc)),
        )

    @strawberry.field
    def robotics_traversability(
        self, info: Info[Context, Any], trail_id: int
    ) -> Optional[RoboticsTraversability]:
        payload = build_robotics_traversability(info.context.repo, trail_id)
        if not payload:
            return None
        return RoboticsTraversability(
            trail_id=payload["trail_id"],
            name=payload["name"],
            route_geojson=payload["route_geojson"],
            hazards_geojson=payload["hazards_geojson"],
            hazard_summary=HazardSummary(**payload["hazard_summary"]),
            data_freshness=RoboticsDataFreshness(**payload["data_freshness"]),
            geometry_quality=payload["geometry_quality"],
            geometry_source=payload["geometry_source"],
            vertex_count=payload["vertex_count"],
            ros_compatible_route=payload["ros_compatible_route"],
            traversability_score=payload["traversability_score"],
            risk_score=payload["risk_score"],
            effort_score=payload["effort_score"],
            segment_costs=payload["segment_costs"],
            elevation_profile=payload["elevation_profile"],
            cost_model=payload["cost_model"],
            hazard_location_quality=payload["hazard_location_quality"],
            planning_notes=payload["planning_notes"],
        )

    @strawberry.field
    def robotics_area(self, info: Info[Context, Any], lat: float, lng: float, radius_m: float) -> RoboticsArea:
        payload = build_robotics_area(info.context.repo, lat=lat, lng=lng, radius_m=radius_m)
        highest = payload["highest_risk_trail"]
        return RoboticsArea(
            center=RoboticsAreaCenter(**payload["center"]),
            radius_m=payload["radius_m"],
            active_hazard_count=payload["active_hazard_count"],
            hazard_density=payload["hazard_density"],
            area_risk_score=payload["area_risk_score"],
            highest_risk_trail=RoboticsAreaTrail(**highest) if highest else None,
            recommended_trail_ids=payload["recommended_trail_ids"],
            trails=[RoboticsAreaTrail(**trail) for trail in payload["trails"]],
            generated_at=payload["generated_at"],
        )

    @strawberry.field
    def trail_reviews(self, info: Info[Context, Any], trail_id: int, limit: int = 10) -> List[Review]:
        rows = info.context.repo.get_recent_reviews(trail_id=trail_id, limit=limit)
        return [Review(**row) for row in rows]


@strawberry.type
class Mutation:
    @strawberry.mutation
    def submit_report(self, info: Info[Context, Any], input: SubmitReportInput) -> Report:
        check_report_mutation("submit", _client_id_from_info(info))
        condition_tags = _validate_condition_tags(input.condition_tags)
        notes = _sanitize_text(input.notes, max_length=MAX_REPORT_NOTE_LENGTH)
        reporter_name = _sanitize_text(input.reporter_name, max_length=80)
        row = info.context.repo.add_report(
            trail_id=input.trail_id,
            condition_tags=condition_tags,
            notes=notes,
            reporter_name=reporter_name,
        )
        return Report(**row)

    @strawberry.mutation
    def upvote_report(self, info: Info[Context, Any], report_id: int) -> Optional[Report]:
        check_report_mutation("upvote", _client_id_from_info(info))
        row = info.context.repo.upvote_report(report_id)
        return Report(**row) if row else None

    @strawberry.mutation
    def resolve_report(self, info: Info[Context, Any], report_id: int) -> bool:
        return info.context.repo.resolve_report(report_id)


schema = strawberry.Schema(query=Query, mutation=Mutation)
