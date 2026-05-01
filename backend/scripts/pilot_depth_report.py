from __future__ import annotations

from app.runtime_check import ensure_supported_python

ensure_supported_python()

import os
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row


@dataclass
class DepthRow:
    trail_id: int
    name: str
    has_core: bool
    has_weather: bool
    has_hazard: bool
    has_reviews: bool
    depth_ready: bool


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required.")

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH pilot AS (
                  SELECT t.id, t.name, t.region, t.difficulty, t.length_km, t.elevation_gain_m,
                         t.geom, tl.state_code, tl.city
                  FROM trails t
                  LEFT JOIN trail_locations tl ON tl.id = t.location_id
                  WHERE t.id BETWEEN 1 AND 50
                ),
                reviews AS (
                  SELECT trail_id, COUNT(*) AS review_count
                  FROM reviews
                  WHERE trail_id BETWEEN 1 AND 50
                  GROUP BY trail_id
                ),
                hazards AS (
                  SELECT trail_id, COUNT(*) AS hazard_count
                  FROM hazards
                  WHERE trail_id BETWEEN 1 AND 50
                  GROUP BY trail_id
                ),
                weather AS (
                  SELECT trail_id, COUNT(*) AS weather_count
                  FROM weather_cache
                  WHERE trail_id BETWEEN 1 AND 50
                  GROUP BY trail_id
                )
                SELECT
                  p.id AS trail_id,
                  p.name,
                  (p.name IS NOT NULL AND p.region IS NOT NULL AND p.difficulty IS NOT NULL
                    AND p.length_km IS NOT NULL AND p.elevation_gain_m IS NOT NULL
                    AND p.geom IS NOT NULL AND p.state_code IS NOT NULL) AS has_core,
                  COALESCE(w.weather_count, 0) > 0 AS has_weather,
                  COALESCE(h.hazard_count, 0) > 0 AS has_hazard,
                  COALESCE(r.review_count, 0) >= 2 AS has_reviews
                FROM pilot p
                LEFT JOIN reviews r ON r.trail_id = p.id
                LEFT JOIN hazards h ON h.trail_id = p.id
                LEFT JOIN weather w ON w.trail_id = p.id
                ORDER BY p.id;
                """
            )
            rows = cur.fetchall()

    parsed: list[DepthRow] = []
    for row in rows:
        depth_ready = bool(row["has_core"] and row["has_weather"] and row["has_hazard"] and row["has_reviews"])
        parsed.append(
            DepthRow(
                trail_id=row["trail_id"],
                name=row["name"],
                has_core=bool(row["has_core"]),
                has_weather=bool(row["has_weather"]),
                has_hazard=bool(row["has_hazard"]),
                has_reviews=bool(row["has_reviews"]),
                depth_ready=depth_ready,
            )
        )

    total = len(parsed)
    ready = sum(1 for row in parsed if row.depth_ready)
    pct = (ready / total * 100.0) if total else 0.0

    print(f"Pilot trails checked: {total}")
    print(f"Depth-ready trails: {ready} ({pct:.1f}%)")
    print("Target for expansion: >= 80.0%")
    print("")
    print("Trails failing depth criteria:")
    failed = [row for row in parsed if not row.depth_ready]
    if not failed:
        print("  none")
        return
    for row in failed:
        missing = []
        if not row.has_core:
            missing.append("core")
        if not row.has_weather:
            missing.append("weather")
        if not row.has_hazard:
            missing.append("hazard")
        if not row.has_reviews:
            missing.append("reviews>=2")
        print(f"  - {row.trail_id}: {row.name} (missing: {', '.join(missing)})")


if __name__ == "__main__":
    main()
