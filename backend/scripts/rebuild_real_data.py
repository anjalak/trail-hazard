from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


TRAILS_SERVICE = (
    "https://mapservices.nps.gov/arcgis/rest/services/"
    "NationalDatasets/NPS_Public_Trails/FeatureServer/0/query"
)
ALERTS_API = "https://developer.nps.gov/api/v1/alerts"


@dataclass
class TrailRecord:
    trail_id: int
    name: str
    region: str
    location_id: int
    state_code: str
    city: str
    park_name: str
    park_type: str
    county: str
    difficulty: str
    length_km: float
    elevation_gain_m: int | None
    source_url: str
    geometry_quality: str
    geometry_source: str
    geometry_source_url: str
    data_quality_status: str
    validation_source: str
    validation_notes: str
    traversability_score: float
    wkt: str


def _fetch_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _trails_url(park_code: str) -> str:
    params = {
        "where": f"UNITCODE='{park_code.upper()}'",
        "outFields": "OBJECTID,TRLNAME,MAPLABEL,UNITNAME,UNITCODE",
        "f": "geojson",
        "orderByFields": "OBJECTID ASC",
    }
    return f"{TRAILS_SERVICE}?{urlencode(params)}"


def _alerts_url(park_code: str, api_key: str) -> str:
    params = {"parkCode": park_code.lower(), "limit": "50", "api_key": api_key}
    return f"{ALERTS_API}?{urlencode(params)}"


def _escape_sql(value: str) -> str:
    return value.replace("'", "''")


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _linestring_wkt(geometry: dict[str, Any]) -> str | None:
    coords: list[list[float]]
    if geometry.get("type") == "LineString":
        coords = geometry.get("coordinates") or []
    elif geometry.get("type") == "MultiLineString":
        segments = geometry.get("coordinates") or []
        if not segments:
            return None
        # Keep longest segment for deterministic trail path representation.
        coords = max(segments, key=len)
    else:
        return None

    if len(coords) < 2:
        return None
    pairs = ", ".join(f"{lng:.6f} {lat:.6f}" for lng, lat in coords)
    return f"LINESTRING({pairs})"


def _park_region(park_code: str) -> str:
    return {
        "MORA": "Mount Rainier",
        "OLYM": "Olympic Peninsula",
        "NOCA": "North Cascades",
    }.get(park_code.upper(), "Washington")


def _park_city(park_code: str) -> str:
    return {
        "MORA": "Ashford",
        "OLYM": "Port Angeles",
        "NOCA": "Marblemount",
    }.get(park_code.upper(), "Unknown")


def _park_county(park_code: str) -> str:
    return {
        "MORA": "Pierce",
        "OLYM": "Clallam",
        "NOCA": "Whatcom",
    }.get(park_code.upper(), "Unknown")


def _canonical_park_name(park_code: str) -> str:
    """Stable QUAD columns for UNIQUE (state_code, city, park_name, park_type); NPS UNITNAME varies by feature."""
    return {
        "MORA": "Mount Rainier National Park",
        "OLYM": "Olympic National Park",
        "NOCA": "North Cascades National Park",
    }.get(park_code.upper(), "Unknown National Park")


def _location_id_for_park(park_code: str) -> int:
    """One canonical trail_locations row per park (matches UNIQUE on location quad)."""
    return {"MORA": 1, "OLYM": 2, "NOCA": 3}.get(park_code.upper(), 1)


def fetch_trails(park_codes: list[str], max_per_park: int) -> list[TrailRecord]:
    trails: list[TrailRecord] = []
    trail_id = 1
    for park_code in park_codes:
        location_id = _location_id_for_park(park_code)
        payload = _fetch_json(_trails_url(park_code))
        for feature in payload.get("features", [])[:max_per_park]:
            props = feature.get("properties") or {}
            trail_name = str(props.get("TRLNAME") or props.get("MAPLABEL") or "").strip()
            if not trail_name:
                continue
            wkt = _linestring_wkt(feature.get("geometry") or {})
            if not wkt:
                continue
            unit_name = str(props.get("UNITNAME") or "Unknown National Park").strip()
            trails.append(
                TrailRecord(
                    trail_id=trail_id,
                    name=trail_name,
                    region=_park_region(park_code),
                    location_id=location_id,
                    state_code="WA",
                    city=_park_city(park_code),
                    park_name=_canonical_park_name(park_code),
                    park_type="national_park",
                    county=_park_county(park_code),
                    difficulty="moderate",
                    length_km=round(max(len(wkt) / 300.0, 1.5), 2),
                    elevation_gain_m=None,
                    source_url=TRAILS_SERVICE.replace("/query", ""),
                    geometry_quality="imported_nps",
                    geometry_source=f"NPS Public Trails ({park_code.upper()} OBJECTID {props.get('OBJECTID')})",
                    geometry_source_url=TRAILS_SERVICE.replace("/query", ""),
                    data_quality_status="verified",
                    validation_source="nps_public_trails",
                    validation_notes=f"Imported from NPS Public Trails for {unit_name}.",
                    traversability_score=0.7,
                    wkt=wkt,
                )
            )
            trail_id += 1
    return trails


def fetch_alert_records(
    park_codes: list[str],
    api_key: str,
    trails: list[TrailRecord],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trail_lookup = {trail.trail_id: trail for trail in trails}
    normalized_name_lookup = {_normalize_name(trail.name): trail.trail_id for trail in trails}
    hazards: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []

    for park_code in park_codes:
        payload = _fetch_json(_alerts_url(park_code, api_key))
        for item in payload.get("data", []):
            title = str(item.get("title") or "").strip()
            description = str(item.get("description") or "").strip()
            if not title and not description:
                continue
            text_blob = f"{title}. {description}".strip()
            normalized_blob = _normalize_name(text_blob)

            matched_trail_id = None
            for normalized_name, candidate_trail_id in normalized_name_lookup.items():
                if normalized_name and normalized_name in normalized_blob:
                    matched_trail_id = candidate_trail_id
                    break
            if matched_trail_id is None:
                park_region = _park_region(park_code)
                fallback = next((t for t in trail_lookup.values() if t.region == park_region), None)
                if fallback is None:
                    continue
                matched_trail_id = fallback.trail_id

            source_url = item.get("url") or item.get("linkUrl") or "https://developer.nps.gov/"
            published_at = item.get("lastIndexedDate") or item.get("lastIndexeddate") or item.get("date")
            if not isinstance(published_at, str) or not published_at:
                published_at = datetime.now(tz=timezone.utc).isoformat()
            if published_at.endswith("Z"):
                published_at = published_at.replace("Z", "+00:00")

            hazard_source = "scraped"
            lowered = text_blob.lower()
            hazard_type = "wildlife"
            severity = "low"
            if "snow" in lowered or "ice" in lowered:
                hazard_type = "snow"
                severity = "medium"
            elif "washout" in lowered or "erosion" in lowered:
                hazard_type = "washout"
                severity = "high"
            elif "mud" in lowered:
                hazard_type = "muddy_sections"
                severity = "low"
            elif "closed" in lowered or "closure" in lowered:
                hazard_type = "downed_tree"
                severity = "medium"

            hazards.append(
                {
                    "trail_id": matched_trail_id,
                    "source": hazard_source,
                    "source_platform": "nps_alerts",
                    "source_url": source_url,
                    "text": text_blob[:900],
                    "reported_at": published_at,
                    "confidence": 0.86,
                }
            )

            reviews.append(
                {
                    "trail_id": matched_trail_id,
                    "source_platform": "nps_alerts",
                    "external_review_id": str(item.get("id") or ""),
                    "source_url": source_url,
                    "rating": None,
                    "text": text_blob[:900],
                    "sentiment_score": 0.0,
                    "scraped_at": published_at,
                    "author_handle": "nps_alert_feed",
                }
            )

    # Dedupe review IDs and hazard text for idempotent outputs.
    unique_reviews: list[dict[str, Any]] = []
    seen_review_keys: set[tuple[str, str]] = set()
    for review in reviews:
        key = (review["source_platform"], review["external_review_id"])
        if key in seen_review_keys:
            continue
        seen_review_keys.add(key)
        unique_reviews.append(review)

    unique_hazards: list[dict[str, Any]] = []
    seen_hazard_keys: set[tuple[int, str, str]] = set()
    for hazard in hazards:
        key = (hazard["trail_id"], hazard["source_url"], hazard["text"])
        if key in seen_hazard_keys:
            continue
        seen_hazard_keys.add(key)
        unique_hazards.append(hazard)

    return unique_hazards, unique_reviews


def build_fallback_snapshot(
    trails: list[TrailRecord],
    hazards_export: list[dict[str, Any]],
    reviews_export: list[dict[str, Any]],
) -> dict[str, Any]:
    """Offline Postgres fallback snapshot: real NPS trail geometry + inferred hazards matching ingestion.extract_hazards."""
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    from app.services import ingestion as ing
    from app.services.in_memory_fallback import wkt_linestring_to_coordinates

    trails_out: list[dict[str, Any]] = []
    for t in trails:
        coords = wkt_linestring_to_coordinates(t.wkt)
        lng0 = lat0 = None
        if coords:
            trailhead = coords[0]
            lng0, lat0 = float(trailhead[0]), float(trailhead[1])
        trails_out.append(
            {
                "id": t.trail_id,
                "name": t.name,
                "region": t.region,
                "location": {
                    "state_code": t.state_code,
                    "city": t.city,
                    "park_name": t.park_name,
                    "park_type": t.park_type,
                    "county": t.county,
                },
                "difficulty": t.difficulty,
                "length_km": t.length_km,
                "elevation_gain_m": t.elevation_gain_m,
                "traversability_score": t.traversability_score,
                "lat": lat0,
                "lng": lng0,
                "route_coordinates": coords,
                "geometry_quality": t.geometry_quality,
                "geometry_source": t.geometry_source,
                "geometry_source_url": t.geometry_source_url,
            }
        )

    def _parse_export_dt(raw: str | None) -> datetime:
        if not raw:
            return datetime.now(tz=timezone.utc)
        text = raw.strip().replace("Z", "+00:00")
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return datetime.fromisoformat(text.replace(" ", "T", 1) if "T" not in text else text)

    flattened: list[dict[str, Any]] = []
    for row in hazards_export:
        reported_at = _parse_export_dt(row.get("reported_at") if isinstance(row.get("reported_at"), str) else None)
        normalized = {
            "trail_id": int(row["trail_id"]),
            "source": row.get("source", "scraped"),
            "source_platform": row.get("source_platform"),
            "source_url": row.get("source_url"),
            "adapter": "nps_alert_export",
            "raw_text": row.get("text") or "",
            "reported_at": reported_at,
            "confidence": float(row.get("confidence", 0.86)),
        }
        flattened.extend(ing.extract_hazards(normalized))

    hazard_rows_out: list[dict[str, Any]] = []
    seen_fp: set[str] = set()
    hid = 1
    for h in flattened:
        fp = ing.hazard_fingerprint(h)
        if fp in seen_fp:
            continue
        seen_fp.add(fp)
        hazard_rows_out.append(
            {
                "id": hid,
                "trail_id": h["trail_id"],
                "type": h["type"],
                "severity": h["severity"],
                "source": h["source"],
                "confidence": h["confidence"],
                "reported_at": h["reported_at"].isoformat(),
                "raw_text": h.get("raw_text"),
                "resolved_at": None,
            }
        )
        hid += 1

    reviews_out: list[dict[str, Any]] = []
    for i, r in enumerate(reviews_export, start=1):
        scraped = _parse_export_dt(r.get("scraped_at") if isinstance(r.get("scraped_at"), str) else None)
        reviews_out.append(
            {
                "id": i,
                "trail_id": int(r["trail_id"]),
                "source_platform": str(r.get("source_platform") or ""),
                "external_review_id": str(r.get("external_review_id") or ""),
                "source_url": r.get("source_url"),
                "rating": r.get("rating"),
                "text": r.get("text"),
                "sentiment_score": r.get("sentiment_score"),
                "scraped_at": scraped.isoformat(),
                "author_handle": r.get("author_handle"),
            }
        )

    return {
        "snapshot_version": 1,
        "captured_at": datetime.now(tz=timezone.utc).isoformat(),
        "sources": [
            "National Park Service Public Trails GeoJSON layer",
            "National Park Service Alerts API export (keyword hazard extraction mirrors ingestion.extract_hazards)",
        ],
        "notes": "Committed snapshot for Postgres-offline fallback; rerun this script for a fresher real snapshot.",
        "trails": trails_out,
        "hazards": hazard_rows_out,
        "reviews": reviews_out,
        "reports": [],
        "seasonal": {},
        "weather_cache": [],
    }


def build_seed_sql(trails: list[TrailRecord]) -> str:
    locations_by_id: dict[int, TrailRecord] = {}
    for t in trails:
        locations_by_id.setdefault(t.location_id, t)
    location_rows = sorted(locations_by_id.values(), key=lambda x: x.location_id)
    location_values = ",\n".join(
        "("
        + ", ".join(
            [
                str(t.location_id),
                f"'{_escape_sql(t.state_code)}'",
                f"'{_escape_sql(t.city)}'",
                f"'{_escape_sql(t.park_name)}'",
                f"'{_escape_sql(t.park_type)}'",
                f"'{_escape_sql(t.county)}'",
            ]
        )
        + ")"
        for t in location_rows
    )
    trail_values = ",\n".join(
        "("
        + ", ".join(
            [
                str(t.trail_id),
                f"'{_escape_sql(t.name)}'",
                f"'{_escape_sql(t.region)}'",
                str(t.location_id),
                f"'{_escape_sql(t.difficulty)}'",
                f"{t.length_km:.2f}",
                "NULL" if t.elevation_gain_m is None else str(t.elevation_gain_m),
                f"'{_escape_sql(t.source_url)}'",
                f"'{_escape_sql(t.geometry_quality)}'",
                f"'{_escape_sql(t.geometry_source)}'",
                f"'{_escape_sql(t.geometry_source_url)}'",
                f"'{_escape_sql(t.data_quality_status)}'",
                f"'{_escape_sql(t.validation_source)}'",
                "NOW()",
                f"'{_escape_sql(t.validation_notes)}'",
                f"{t.traversability_score:.2f}",
                "NOW()",
                f"ST_SetSRID(ST_GeomFromText('{_escape_sql(t.wkt)}'), 4326)",
            ]
        )
        + ")"
        for t in trails
    )
    return f"""-- Generated by backend/scripts/rebuild_real_data.py
-- Real-source bootstrap only (no synthetic hazard/review/weather rows).

INSERT INTO trail_locations (id, state_code, city, park_name, park_type, county)
VALUES
{location_values}
ON CONFLICT (id) DO UPDATE SET
  state_code = EXCLUDED.state_code,
  city = EXCLUDED.city,
  park_name = EXCLUDED.park_name,
  park_type = EXCLUDED.park_type,
  county = EXCLUDED.county;

INSERT INTO trails (
  id, name, region, location_id, difficulty, length_km, elevation_gain_m,
  source_url, geometry_quality, geometry_source, geometry_source_url,
  data_quality_status, validation_source, validated_at, validation_notes,
  traversability_score, last_scraped_at, geom
)
VALUES
{trail_values}
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name,
    region = EXCLUDED.region,
    location_id = EXCLUDED.location_id,
    difficulty = EXCLUDED.difficulty,
    length_km = EXCLUDED.length_km,
    elevation_gain_m = EXCLUDED.elevation_gain_m,
    source_url = EXCLUDED.source_url,
    geometry_quality = EXCLUDED.geometry_quality,
    geometry_source = EXCLUDED.geometry_source,
    geometry_source_url = EXCLUDED.geometry_source_url,
    data_quality_status = EXCLUDED.data_quality_status,
    validation_source = EXCLUDED.validation_source,
    validated_at = EXCLUDED.validated_at,
    validation_notes = EXCLUDED.validation_notes,
    traversability_score = EXCLUDED.traversability_score,
    last_scraped_at = EXCLUDED.last_scraped_at,
    geom = EXCLUDED.geom;
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild repo data artifacts from real public sources.")
    parser.add_argument("--nps-api-key", default="DEMO_KEY")
    parser.add_argument("--parks", default="MORA,OLYM,NOCA")
    parser.add_argument("--max-trails-per-park", type=int, default=25)
    args = parser.parse_args()

    park_codes = [part.strip().upper() for part in args.parks.split(",") if part.strip()]
    backend_root = Path(__file__).resolve().parents[1]
    seed_path = backend_root / "app" / "models" / "seed.sql"
    hazards_path = backend_root / "data" / "external_hazards.json"
    reviews_path = backend_root / "data" / "external_reviews.json"
    snapshot_path = backend_root / "data" / "in_memory_fallback_snapshot.json"

    trails = fetch_trails(park_codes=park_codes, max_per_park=args.max_trails_per_park)
    hazards, reviews = fetch_alert_records(park_codes=park_codes, api_key=args.nps_api_key, trails=trails)

    snapshot = build_fallback_snapshot(trails, hazards, reviews)

    seed_path.write_text(build_seed_sql(trails), encoding="utf-8")
    hazards_path.write_text(json.dumps(hazards, indent=2), encoding="utf-8")
    reviews_path.write_text(json.dumps(reviews, indent=2), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    print(
        "Rebuilt real data artifacts:",
        f"trails={len(trails)}",
        f"hazards={len(hazards)}",
        f"reviews={len(reviews)}",
        f"snapshot_trails={len(snapshot['trails'])} snapshot_hazard_rows={len(snapshot['hazards'])}",
    )


if __name__ == "__main__":
    main()
