from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.services.hazard_scoring import hazard_score

MIN_ROUTE_POSES = 10


def _trail_scalar_float(trail: Dict[str, Any], key: str, default: float = 0.0) -> float:
    raw = trail.get(key, default)
    if raw is None:
        return default
    return float(raw)
MAX_ROUTE_POSES = 25
DEFAULT_DENSIFIED_POSES = 12


def build_robotics_traversability(repo: Any, trail_id: int) -> Optional[Dict[str, Any]]:
    trail = repo.get_trail(trail_id)
    if not trail:
        return None

    route_geojson = repo.get_trail_route_geojson(trail_id)
    metadata = geometry_metadata(route_geojson)
    hazards = repo.get_hazards(trail_id=trail_id, active_only=True)
    traversability_score = _trail_scalar_float(trail, "traversability_score")
    length_km = _trail_scalar_float(trail, "length_km")
    elevation_gain_m = _trail_scalar_float(trail, "elevation_gain_m")
    risk_score = compute_route_risk(
        hazards=hazards,
        traversability_score=traversability_score,
        length_km=length_km,
        elevation_gain_m=elevation_gain_m,
    )
    coordinates = _line_coordinates(route_geojson)
    route_points = _densify_coordinates(coordinates)
    effort_score = _effort_component(length_km=length_km, elevation_gain_m=elevation_gain_m)
    segment_model = _build_segment_cost_model(
        route_points=route_points,
        hazards=hazards,
        traversability_score=traversability_score,
        effort_score=effort_score,
        route_risk_score=risk_score,
        total_elevation_gain_m=elevation_gain_m,
    )
    ros_route = build_ros_compatible_route(
        route_points=route_points,
        route_cost=risk_score,
        segment_costs=segment_model["segment_costs"],
        elevation_profile=segment_model["elevation_profile"],
    )
    hazard_location_quality = _hazard_location_quality(hazards)
    generated_at = datetime.now(tz=timezone.utc)

    return {
        "trail_id": trail["id"],
        "name": trail["name"],
        "route_geojson": route_geojson,
        "hazards_geojson": build_robotics_hazards_geojson(hazards),
        "hazard_summary": _hazard_summary(hazards),
        "data_freshness": _data_freshness(hazards, generated_at),
        "geometry_quality": metadata["geometry_quality"],
        "geometry_source": metadata["geometry_source"],
        "vertex_count": metadata["vertex_count"],
        "ros_compatible_route": ros_route,
        "traversability_score": traversability_score,
        "risk_score": risk_score,
        "effort_score": round(effort_score, 3),
        "segment_costs": segment_model["segment_costs"],
        "elevation_profile": segment_model["elevation_profile"],
        "cost_model": segment_model["cost_model"],
        "hazard_location_quality": hazard_location_quality,
        "planning_notes": _planning_notes(
            metadata=metadata,
            hazards=hazards,
            hazard_location_quality=hazard_location_quality,
            segment_fallback=segment_model["fallback_mode"],
        ),
    }


def build_robotics_area(repo: Any, lat: float, lng: float, radius_m: float) -> Dict[str, Any]:
    radius_km = max(0.0, float(radius_m)) / 1000.0
    nearby_trails = repo.nearby_trails(lat=lat, lng=lng, km=radius_km)
    trail_summaries = []
    active_hazard_count = 0

    for trail in nearby_trails:
        hazards = repo.get_hazards(trail_id=trail["id"], active_only=True)
        risk_score = compute_route_risk(
            hazards=hazards,
            traversability_score=_trail_scalar_float(trail, "traversability_score"),
            length_km=_trail_scalar_float(trail, "length_km"),
            elevation_gain_m=_trail_scalar_float(trail, "elevation_gain_m"),
        )
        effort_score = _effort_component(
            length_km=_trail_scalar_float(trail, "length_km"),
            elevation_gain_m=_trail_scalar_float(trail, "elevation_gain_m"),
        )
        active_hazard_count += len(hazards)
        trail_summaries.append(
            {
                "trail_id": trail["id"],
                "name": trail["name"],
                "traversability_score": float(trail.get("traversability_score", 0.0)),
                "risk_score": risk_score,
                "effort_score": round(effort_score, 3),
                "active_hazard_count": len(hazards),
                "hazard_location_quality": _hazard_location_quality(hazards),
            }
        )

    trail_summaries.sort(key=lambda row: (row["risk_score"], -row["traversability_score"], row["name"]))
    area_km2 = math.pi * (radius_km**2) if radius_km > 0 else 0.0
    highest_risk_trail = max(trail_summaries, key=lambda row: row["risk_score"], default=None)
    recommended_trail_ids = [
        row["trail_id"]
        for row in trail_summaries
        if row["risk_score"] <= 0.45
    ][:5]

    return {
        "center": {"lat": float(lat), "lng": float(lng)},
        "radius_m": float(radius_m),
        "active_hazard_count": active_hazard_count,
        "hazard_density": round(active_hazard_count / area_km2, 3) if area_km2 else 0.0,
        "area_risk_score": round(
            sum(row["risk_score"] for row in trail_summaries) / len(trail_summaries),
            3,
        )
        if trail_summaries
        else 0.0,
        "highest_risk_trail": highest_risk_trail,
        "recommended_trail_ids": recommended_trail_ids,
        "trails": trail_summaries,
        "generated_at": datetime.now(tz=timezone.utc),
    }


def build_ros_compatible_route(
    route_points: List[List[float]],
    route_cost: float,
    segment_costs: Optional[List[Dict[str, Any]]] = None,
    elevation_profile: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    elevation_by_pose = _elevation_values_for_poses(route_points, elevation_profile or [])
    poses = [
        {
            "position": {"x": float(lng), "y": float(lat), "z": float(elevation_by_pose[index])},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        }
        for index, (lng, lat) in enumerate(route_points)
    ]
    pose_costs = _pose_costs_from_segment_costs(route_points, segment_costs or [])
    if not pose_costs:
        pose_costs = [round(route_cost, 3) for _ in poses]
    return {
        "header": {
            "frame_id": "map",
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "coordinate_system": "WGS84",
            "axes": {
                "x": "longitude_degrees",
                "y": "latitude_degrees",
                "z": "elevation_meters",
            },
            "cost_model_version": "v2-segment-aware",
        },
        "poses": poses,
        "costs": pose_costs,
    }


def compute_route_risk(
    hazards: List[Dict[str, Any]],
    traversability_score: float,
    length_km: float,
    elevation_gain_m: float,
) -> float:
    traversability_risk = 1.0 - _clamp(traversability_score)
    if hazards:
        hazard_component = _clamp(sum(hazard_score(hazard) for hazard in hazards) / max(len(hazards), 1))
    else:
        hazard_component = 0.0
    effort_component = _effort_component(length_km=length_km, elevation_gain_m=elevation_gain_m)
    return round(
        _clamp((0.35 * traversability_risk) + (0.45 * hazard_component) + (0.20 * effort_component)),
        3,
    )


def _effort_component(length_km: float, elevation_gain_m: float) -> float:
    # Normalize mileage/elevation into a 0..1 effort signal for route cost.
    distance_component = _clamp(length_km / 20.0)
    elevation_component = _clamp(elevation_gain_m / 1500.0)
    return _clamp((0.6 * distance_component) + (0.4 * elevation_component))


def _build_segment_cost_model(
    route_points: List[List[float]],
    hazards: List[Dict[str, Any]],
    traversability_score: float,
    effort_score: float,
    route_risk_score: float,
    total_elevation_gain_m: float,
) -> Dict[str, Any]:
    if len(route_points) < 2:
        return {
            "segment_costs": [],
            "elevation_profile": _build_elevation_profile(route_points, total_elevation_gain_m),
            "cost_model": {
                "version": "v2-segment-aware",
                "fallback_mode": True,
                "reason": "insufficient_route_points",
            },
            "fallback_mode": True,
        }

    elevation_profile = _build_elevation_profile(route_points, total_elevation_gain_m)
    elevations = _elevation_values_for_poses(route_points, elevation_profile)
    traversability_risk = 1.0 - _clamp(traversability_score)
    global_hazard_component = _hazard_component(hazards)
    segment_lengths = _segment_lengths(route_points)
    max_segment_length = max(segment_lengths, default=1.0)
    exact_hazards = [
        (float(h.get("lng")), float(h.get("lat")), hazard_score(h))
        for h in hazards
        if _hazard_has_exact_location(h) and h.get("lng") is not None and h.get("lat") is not None
    ]
    segment_costs: List[Dict[str, Any]] = []
    fallback_mode = len(exact_hazards) == 0 or total_elevation_gain_m <= 0

    for index, segment_length in enumerate(segment_lengths):
        elevation_delta = max(0.0, elevations[index + 1] - elevations[index])
        grade = elevation_delta / max(segment_length * 111000.0, 1.0)
        grade_component = _clamp(grade / 0.25)
        distance_component = _clamp(segment_length / max_segment_length)
        segment_effort = _clamp((0.5 * effort_score) + (0.25 * grade_component) + (0.25 * distance_component))
        hazard_local = _local_hazard_component(
            point_a=route_points[index],
            point_b=route_points[index + 1],
            exact_hazards=exact_hazards,
            fallback_hazard=global_hazard_component,
        )
        segment_costs.append(
            {
                "index": index,
                "start": {"lng": float(route_points[index][0]), "lat": float(route_points[index][1])},
                "end": {"lng": float(route_points[index + 1][0]), "lat": float(route_points[index + 1][1])},
                "estimated_gain_m": round(elevation_delta, 2),
                "estimated_grade": round(grade, 4),
                "hazard_component": round(hazard_local, 3),
                "cost": round(
                    _clamp((0.35 * traversability_risk) + (0.40 * hazard_local) + (0.25 * segment_effort)),
                    3,
                ),
            }
        )

    normalized_costs = _normalize_segment_costs(segment_costs, route_risk_score)
    return {
        "segment_costs": normalized_costs,
        "elevation_profile": elevation_profile,
        "cost_model": {
            "version": "v2-segment-aware",
            "fallback_mode": fallback_mode,
            "weights": {
                "traversability": 0.35,
                "hazard": 0.40,
                "segment_effort": 0.25,
            },
        },
        "fallback_mode": fallback_mode,
    }


def _normalize_segment_costs(segment_costs: List[Dict[str, Any]], target_mean_cost: float) -> List[Dict[str, Any]]:
    if not segment_costs:
        return segment_costs
    mean_cost = sum(segment["cost"] for segment in segment_costs) / len(segment_costs)
    if mean_cost <= 0:
        return segment_costs
    scale = target_mean_cost / mean_cost
    for segment in segment_costs:
        segment["cost"] = round(_clamp(segment["cost"] * scale), 3)
    return segment_costs


def _build_elevation_profile(route_points: List[List[float]], total_gain_m: float) -> List[Dict[str, float]]:
    if not route_points:
        return []
    if len(route_points) == 1:
        return [{"index": 0, "distance_ratio": 0.0, "elevation_m": 0.0}]

    segment_count = len(route_points) - 1
    weights = _gain_distribution_weights(segment_count)
    cumulative = 0.0
    profile = [{"index": 0, "distance_ratio": 0.0, "elevation_m": 0.0}]
    for index, weight in enumerate(weights, start=1):
        cumulative += max(0.0, total_gain_m) * weight
        profile.append(
            {
                "index": index,
                "distance_ratio": round(index / segment_count, 4),
                "elevation_m": round(cumulative, 2),
            }
        )
    return profile


def _gain_distribution_weights(segment_count: int) -> List[float]:
    if segment_count <= 0:
        return []
    raw = []
    for step in range(segment_count):
        ratio = (step + 0.5) / segment_count
        raw.append(0.15 + math.sin(math.pi * ratio))
    total = sum(raw)
    if total <= 0:
        return [1.0 / segment_count for _ in range(segment_count)]
    return [value / total for value in raw]


def _elevation_values_for_poses(route_points: List[List[float]], elevation_profile: List[Dict[str, float]]) -> List[float]:
    if not route_points:
        return []
    if not elevation_profile:
        return [0.0 for _ in route_points]
    values = [0.0 for _ in route_points]
    for row in elevation_profile:
        index = int(row.get("index", -1))
        if 0 <= index < len(values):
            values[index] = float(row.get("elevation_m", 0.0))
    return values


def _pose_costs_from_segment_costs(
    route_points: List[List[float]], segment_costs: List[Dict[str, Any]]
) -> List[float]:
    if len(route_points) == 0:
        return []
    if not segment_costs:
        return []
    segment_values = [float(segment.get("cost", 0.0)) for segment in segment_costs]
    if not segment_values:
        return []
    pose_costs = [round(segment_values[0], 3)]
    for index in range(1, len(route_points)):
        segment_index = min(index - 1, len(segment_values) - 1)
        pose_costs.append(round(segment_values[segment_index], 3))
    return pose_costs


def _segment_lengths(route_points: List[List[float]]) -> List[float]:
    return [math.dist(route_points[index], route_points[index + 1]) for index in range(len(route_points) - 1)]


def _hazard_component(hazards: List[Dict[str, Any]]) -> float:
    if not hazards:
        return 0.0
    return _clamp(sum(hazard_score(hazard) for hazard in hazards) / max(len(hazards), 1))


def _local_hazard_component(
    point_a: List[float], point_b: List[float], exact_hazards: List[Any], fallback_hazard: float
) -> float:
    if not exact_hazards:
        return fallback_hazard
    midpoint_lng = (point_a[0] + point_b[0]) / 2.0
    midpoint_lat = (point_a[1] + point_b[1]) / 2.0
    weighted_scores: List[float] = []
    for hazard_lng, hazard_lat, hazard_risk in exact_hazards:
        distance_deg = math.dist([midpoint_lng, midpoint_lat], [hazard_lng, hazard_lat])
        distance_km = distance_deg * 111.0
        proximity = 1.0 / (1.0 + (distance_km * 4.0))
        weighted_scores.append(hazard_risk * proximity)
    return _clamp(max(weighted_scores, default=fallback_hazard))


def build_robotics_hazards_geojson(hazards: List[Dict[str, Any]]) -> Dict[str, Any]:
    features = []
    for hazard in hazards:
        if not _hazard_has_exact_location(hazard):
            continue
        lng = hazard.get("lng")
        lat = hazard.get("lat")
        if lng is None or lat is None:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
                "properties": {
                    "hazardId": hazard["id"],
                    "type": hazard["type"],
                    "severity": hazard["severity"],
                    "confidence": float(hazard.get("confidence", 0.75)),
                    "source": hazard["source"],
                    "reportedAt": _datetime_iso(hazard["reported_at"]),
                    "riskCost": round(hazard_score(hazard), 3),
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def geometry_metadata(route_geojson: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    properties = (route_geojson or {}).get("properties") or {}
    coordinates = _line_coordinates(route_geojson)
    return {
        "geometry_quality": properties.get("geometryQuality") or "synthetic",
        "geometry_source": properties.get("geometrySource") or "seed.sql",
        "vertex_count": len(coordinates),
    }


def _hazard_summary(hazards: List[Dict[str, Any]]) -> Dict[str, Any]:
    highest = max(hazards, key=lambda hazard: hazard_score(hazard), default=None)
    return {
        "active_count": len(hazards),
        "highest_severity": highest["severity"] if highest else "low",
        "types": sorted({hazard["type"] for hazard in hazards}),
    }


def _data_freshness(hazards: List[Dict[str, Any]], generated_at: datetime) -> Dict[str, Any]:
    latest_hazard_at = max(
        (_ensure_aware_datetime(hazard["reported_at"]) for hazard in hazards),
        default=None,
    )
    return {
        "generated_at": generated_at,
        "latest_hazard_at": latest_hazard_at,
        "source_count": len({hazard["source"] for hazard in hazards}),
        "stale": bool(latest_hazard_at and generated_at - latest_hazard_at > timedelta(days=14)),
    }


def _line_coordinates(route_geojson: Optional[Dict[str, Any]]) -> List[List[float]]:
    if not route_geojson:
        return []
    geometry = route_geojson.get("geometry") or {}
    if geometry.get("type") != "LineString":
        return []
    coordinates = geometry.get("coordinates") or []
    return [
        [float(point[0]), float(point[1])]
        for point in coordinates
        if isinstance(point, (list, tuple)) and len(point) >= 2
    ]


def _densify_coordinates(coordinates: List[List[float]]) -> List[List[float]]:
    if not coordinates:
        return []
    if len(coordinates) == 1:
        lng, lat = coordinates[0]
        coordinates = [[lng, lat], [lng + 0.001, lat + 0.001]]
    if MIN_ROUTE_POSES <= len(coordinates) <= MAX_ROUTE_POSES:
        return coordinates

    target_count = DEFAULT_DENSIFIED_POSES if len(coordinates) < MIN_ROUTE_POSES else MAX_ROUTE_POSES
    segment_lengths = [
        math.dist(coordinates[index], coordinates[index + 1])
        for index in range(len(coordinates) - 1)
    ]
    total_length = sum(segment_lengths)
    if total_length <= 0:
        return [coordinates[0] for _ in range(target_count)]

    densified: List[List[float]] = []
    for step in range(target_count):
        distance_along = (total_length * step) / (target_count - 1)
        densified.append(_interpolate_at_distance(coordinates, segment_lengths, distance_along))
    return densified


def _interpolate_at_distance(
    coordinates: List[List[float]], segment_lengths: List[float], distance_along: float
) -> List[float]:
    traversed = 0.0
    for index, segment_length in enumerate(segment_lengths):
        if traversed + segment_length >= distance_along:
            ratio = 0.0 if segment_length == 0 else (distance_along - traversed) / segment_length
            start = coordinates[index]
            end = coordinates[index + 1]
            return [
                start[0] + ((end[0] - start[0]) * ratio),
                start[1] + ((end[1] - start[1]) * ratio),
            ]
        traversed += segment_length
    return coordinates[-1]


def _hazard_location_quality(hazards: List[Dict[str, Any]]) -> str:
    if any(_hazard_has_exact_location(hazard) for hazard in hazards):
        return "exact"
    if hazards:
        return "trail_level"
    return "unknown"


def _hazard_has_exact_location(hazard: Dict[str, Any]) -> bool:
    if hazard.get("has_location") is True:
        return True
    location = hazard.get("location")
    return bool(location)


def _ensure_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _datetime_iso(value: datetime) -> str:
    return _ensure_aware_datetime(value).isoformat()


def _planning_notes(
    metadata: Dict[str, Any], hazards: List[Dict[str, Any]], hazard_location_quality: str, segment_fallback: bool
) -> List[str]:
    notes = [
        "ROS-compatible message format generated from route geometry for pre-mission planning.",
        "Route pose coordinates are geographic (WGS84 lon/lat), not local ENU map meters.",
        "Route cost blends hazards, traversability, mileage, and elevation gain.",
    ]
    if metadata["geometry_quality"] == "synthetic":
        notes.append("Route geometry is simplified demo data and should not be treated as survey-grade.")
    if segment_fallback:
        notes.append("Segment costs use fallback mode because exact hazard points or elevation profile detail is limited.")
    else:
        notes.append("Segment costs include local slope and nearby hazard influence along the route.")
    if hazard_location_quality == "trail_level":
        notes.append("Active hazards are treated as route-level risk because exact hazard GPS points are not available.")
    elif hazard_location_quality == "exact":
        notes.append("At least one active hazard includes an explicit point location.")
    elif not hazards:
        notes.append("No active hazards are currently attached to this trail.")
    return notes


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
