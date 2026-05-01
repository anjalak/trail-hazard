from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Dict, Generator, List, Optional, Sequence

import psycopg
from psycopg.rows import dict_row

from app.services.trail_geom_sql import TRAIL_MAP_PIN_POINT

class PostgresRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def _conn(self) -> Generator[psycopg.Connection, None, None]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            yield conn

    def ping(self) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return cur.fetchone() is not None

    def search_trails(
        self,
        query: str,
        limit: int = 10,
        state_code: Optional[str] = None,
        city: Optional[str] = None,
        park_type: Optional[str] = None,
        park_name_contains: Optional[str] = None,
    ) -> List[Dict]:
        normalized_query = query.strip().lower()
        sql = """
            SELECT
              t.id,
              t.name,
              t.region,
              t.difficulty,
              t.length_km,
              t.elevation_gain_m,
              t.traversability_score,
              (ST_AsGeoJSON(ST_SimplifyPreserveTopology(t.geom::geometry, 0.00004))::jsonb -> 'coordinates') AS route_coordinates,
              COALESCE(
                ST_Y({pin}),
                (
                  SELECT ST_Y(ST_Centroid(ST_Collect(h.location)))
                  FROM hazards h
                  WHERE h.trail_id = t.id
                    AND h.location IS NOT NULL
                ),
                (
                  SELECT ST_Y(ST_Centroid(ST_Collect(ur.location)))
                  FROM user_reports ur
                  WHERE ur.trail_id = t.id
                    AND ur.location IS NOT NULL
                )
              ) AS lat,
              COALESCE(
                ST_X({pin}),
                (
                  SELECT ST_X(ST_Centroid(ST_Collect(h.location)))
                  FROM hazards h
                  WHERE h.trail_id = t.id
                    AND h.location IS NOT NULL
                ),
                (
                  SELECT ST_X(ST_Centroid(ST_Collect(ur.location)))
                  FROM user_reports ur
                  WHERE ur.trail_id = t.id
                    AND ur.location IS NOT NULL
                )
              ) AS lng,
              tl.state_code,
              tl.city,
              tl.park_name,
              tl.park_type,
              tl.county
            FROM trails t
            LEFT JOIN trail_locations tl ON tl.id = t.location_id
            WHERE LOWER(t.name) LIKE %(query)s
              AND (%(state_code)s::text IS NULL OR LOWER(tl.state_code) = LOWER(%(state_code)s::text))
              AND (%(city)s::text IS NULL OR LOWER(tl.city) = LOWER(%(city)s::text))
              AND (%(park_type)s::text IS NULL OR LOWER(tl.park_type) = LOWER(%(park_type)s::text))
              AND (
                %(park_name_contains)s::text IS NULL
                OR LOWER(tl.park_name) LIKE %(park_name_like)s
              )
            ORDER BY
              CASE
                WHEN LOWER(t.name) = %(normalized_query)s THEN 0
                WHEN LOWER(t.name) LIKE %(prefix_query)s THEN 1
                WHEN LOWER(t.name) LIKE %(word_prefix_query)s THEN 2
                WHEN LOWER(t.name) LIKE %(query)s THEN 3
                ELSE 4
              END,
              POSITION(%(normalized_query)s IN LOWER(t.name)),
              LENGTH(t.name),
              t.name
            LIMIT %(limit)s;
        """.replace("{pin}", TRAIL_MAP_PIN_POINT)
        params = {
            "query": f"%{normalized_query}%",
            "normalized_query": normalized_query,
            "prefix_query": f"{normalized_query}%",
            "word_prefix_query": f"% {normalized_query}%",
            "state_code": state_code,
            "city": city,
            "park_type": park_type,
            "park_name_contains": park_name_contains,
            "park_name_like": f"%{(park_name_contains or '').lower()}%",
            "limit": limit,
        }
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [self._map_trail_row(row) for row in rows]

    def get_trail(self, trail_id: int) -> Optional[Dict]:
        sql = """
            SELECT
              t.id,
              t.name,
              t.region,
              t.difficulty,
              t.length_km,
              t.elevation_gain_m,
              t.traversability_score,
              (ST_AsGeoJSON(ST_SimplifyPreserveTopology(t.geom::geometry, 0.00004))::jsonb -> 'coordinates') AS route_coordinates,
              COALESCE(
                ST_Y({pin}),
                (
                  SELECT ST_Y(ST_Centroid(ST_Collect(h.location)))
                  FROM hazards h
                  WHERE h.trail_id = t.id
                    AND h.location IS NOT NULL
                ),
                (
                  SELECT ST_Y(ST_Centroid(ST_Collect(ur.location)))
                  FROM user_reports ur
                  WHERE ur.trail_id = t.id
                    AND ur.location IS NOT NULL
                )
              ) AS lat,
              COALESCE(
                ST_X({pin}),
                (
                  SELECT ST_X(ST_Centroid(ST_Collect(h.location)))
                  FROM hazards h
                  WHERE h.trail_id = t.id
                    AND h.location IS NOT NULL
                ),
                (
                  SELECT ST_X(ST_Centroid(ST_Collect(ur.location)))
                  FROM user_reports ur
                  WHERE ur.trail_id = t.id
                    AND ur.location IS NOT NULL
                )
              ) AS lng,
              tl.state_code,
              tl.city,
              tl.park_name,
              tl.park_type,
              tl.county
            FROM trails t
            LEFT JOIN trail_locations tl ON tl.id = t.location_id
            WHERE t.id = %(trail_id)s;
        """.replace("{pin}", TRAIL_MAP_PIN_POINT)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"trail_id": trail_id})
                row = cur.fetchone()
        return self._map_trail_row(row) if row else None

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
        trails_columns = self._get_table_columns("trails")
        quality_filters: list[str] = []
        if "geometry_quality" in trails_columns:
            quality_filters.append("(t.geometry_quality IS NULL OR t.geometry_quality <> 'synthetic')")
        if "data_quality_status" in trails_columns:
            quality_filters.append("(t.data_quality_status IS NULL OR t.data_quality_status <> 'demo_synthetic')")
        quality_clause = f"\n              AND {' AND '.join(quality_filters)}" if quality_filters else ""

        sql = f"""
            SELECT
              t.id,
              t.name,
              t.region,
              t.difficulty,
              t.length_km,
              t.elevation_gain_m,
              t.traversability_score,
              ST_Y({{pin}}) AS lat,
              ST_X({{pin}}) AS lng,
              tl.state_code,
              tl.city,
              tl.park_name,
              tl.park_type,
              tl.county
            FROM trails t
            LEFT JOIN trail_locations tl ON tl.id = t.location_id
            WHERE t.geom IS NOT NULL
              {quality_clause}
              AND ST_DWithin(
                  t.geom::geography,
                  ST_SetSRID(ST_Point(%(lng)s, %(lat)s), 4326)::geography,
                  %(radius_m)s
                )
              AND (%(state_code)s::text IS NULL OR LOWER(tl.state_code) = LOWER(%(state_code)s::text))
              AND (%(city)s::text IS NULL OR LOWER(tl.city) = LOWER(%(city)s::text))
              AND (%(park_type)s::text IS NULL OR LOWER(tl.park_type) = LOWER(%(park_type)s::text))
              AND (
                %(park_name_contains)s::text IS NULL
                OR LOWER(tl.park_name) LIKE %(park_name_like)s
              )
            ORDER BY t.name;
        """.replace("{pin}", TRAIL_MAP_PIN_POINT)
        params = {
            "lat": lat,
            "lng": lng,
            "radius_m": km * 1000,
            "state_code": state_code,
            "city": city,
            "park_type": park_type,
            "park_name_contains": park_name_contains,
            "park_name_like": f"%{(park_name_contains or '').lower()}%",
        }
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [self._map_trail_row(row) for row in rows]

    def get_hazards(self, trail_id: int, active_only: bool = True) -> List[Dict]:
        sql = """
            SELECT
              id,
              trail_id,
              type,
              severity,
              source,
              confidence,
              reported_at,
              raw_text,
              resolved_at,
              location IS NOT NULL AS has_location,
              ST_X(location) AS lng,
              ST_Y(location) AS lat
            FROM hazards
            WHERE trail_id = %(trail_id)s
              AND (%(active_only)s = FALSE OR resolved_at IS NULL)
            ORDER BY reported_at DESC;
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"trail_id": trail_id, "active_only": active_only})
                return cur.fetchall()

    def get_trail_route_geojson(self, trail_id: int) -> Optional[Dict]:
        sql = """
            SELECT
              t.id,
              t.name,
              t.source_url,
              t.geometry_quality,
              t.geometry_source,
              t.geometry_source_url,
              ST_AsGeoJSON(t.geom) AS geometry
            FROM trails t
            WHERE t.id = %(trail_id)s
              AND t.geom IS NOT NULL;
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"trail_id": trail_id})
                row = cur.fetchone()
        if not row:
            return None

        geometry = json.loads(row["geometry"])
        return {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "trailId": row["id"],
                "name": row["name"],
                "sourceUrl": row.get("source_url"),
                "geometryQuality": row.get("geometry_quality") or "synthetic",
                "geometrySource": row.get("geometry_source") or "seed.sql",
                "geometrySourceUrl": row.get("geometry_source_url"),
            },
        }

    def get_hazards_geojson(self, trail_id: int) -> Dict:
        sql = """
            SELECT
              id AS hazard_id,
              type,
              severity,
              ST_X(location) AS lng,
              ST_Y(location) AS lat
            FROM hazards
            WHERE trail_id = %(trail_id)s
              AND resolved_at IS NULL
              AND location IS NOT NULL;
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"trail_id": trail_id})
                rows = cur.fetchall()
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [row["lng"], row["lat"]]},
                    "properties": {
                        "hazard_id": row["hazard_id"],
                        "type": row["type"],
                        "severity": row["severity"],
                    },
                }
                for row in rows
            ],
        }

    def get_recent_reports(self, trail_id: int, limit: int = 5) -> List[Dict]:
        sql = """
            SELECT id, trail_id, condition_tags, notes, reporter_name, reported_at, upvotes
            FROM user_reports
            WHERE trail_id = %(trail_id)s
            ORDER BY reported_at DESC
            LIMIT %(limit)s;
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"trail_id": trail_id, "limit": limit})
                return cur.fetchall()

    def get_seasonal(self, trail_id: int) -> Optional[Dict]:
        month = datetime.utcnow().month
        sql = """
            SELECT month, wildlife_alerts, plant_warnings, gear_recommendations, avg_temp_c, avg_snowpack_cm
            FROM seasonal_intel
            WHERE trail_id = %(trail_id)s AND month = %(month)s;
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"trail_id": trail_id, "month": month})
                row = cur.fetchone()
        return row

    def get_recent_reviews(self, trail_id: int, limit: int = 10) -> List[Dict]:
        sql = """
            SELECT
              id, trail_id, source_platform, external_review_id, source_url,
              rating, text, sentiment_score, scraped_at, author_handle
            FROM reviews
            WHERE trail_id = %(trail_id)s
            ORDER BY scraped_at DESC
            LIMIT %(limit)s;
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"trail_id": trail_id, "limit": limit})
                return cur.fetchall()

    def persist_reviews(self, reviews: Sequence[Dict]) -> int:
        if not reviews:
            return 0
        sql = """
            INSERT INTO reviews (
              trail_id, source_platform, external_review_id, source_url,
              rating, text, sentiment_score, scraped_at, author_handle
            )
            VALUES (
              %(trail_id)s, %(source_platform)s, %(external_review_id)s, %(source_url)s,
              %(rating)s, %(text)s, %(sentiment_score)s, %(scraped_at)s, %(author_handle)s
            )
            ON CONFLICT (source_platform, external_review_id) DO NOTHING;
        """
        inserted = 0
        with self._conn() as conn:
            with conn.cursor() as cur:
                for review in reviews:
                    cur.execute(
                        sql,
                        {
                            "trail_id": review["trail_id"],
                            "source_platform": review["source_platform"],
                            "external_review_id": review.get("external_review_id"),
                            "source_url": review.get("source_url"),
                            "rating": review.get("rating"),
                            "text": review.get("text"),
                            "sentiment_score": review.get("sentiment_score"),
                            "scraped_at": review.get("scraped_at", datetime.now(tz=timezone.utc)),
                            "author_handle": review.get("author_handle"),
                        },
                    )
                    inserted += cur.rowcount
            conn.commit()
        return inserted

    def get_weather_cache(self, trail_id: int, provider: str) -> Optional[Dict]:
        sql = """
            SELECT trail_id, provider, summary, temperature_c, wind_kph, fetched_at, expires_at
            FROM weather_cache
            WHERE trail_id = %(trail_id)s
              AND provider = %(provider)s
              AND expires_at > NOW();
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"trail_id": trail_id, "provider": provider})
                return cur.fetchone()

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
        sql = """
            INSERT INTO weather_cache (trail_id, provider, summary, temperature_c, wind_kph, fetched_at, expires_at)
            VALUES (%(trail_id)s, %(provider)s, %(summary)s, %(temperature_c)s, %(wind_kph)s, %(fetched_at)s, %(expires_at)s)
            ON CONFLICT (trail_id, provider) DO UPDATE
            SET summary = EXCLUDED.summary,
                temperature_c = EXCLUDED.temperature_c,
                wind_kph = EXCLUDED.wind_kph,
                fetched_at = EXCLUDED.fetched_at,
                expires_at = EXCLUDED.expires_at
            RETURNING trail_id, provider, summary, temperature_c, wind_kph, fetched_at, expires_at;
        """
        payload = {
            "trail_id": trail_id,
            "provider": provider,
            "summary": summary,
            "temperature_c": temperature_c,
            "wind_kph": wind_kph,
            "fetched_at": fetched_at,
            "expires_at": expires_at,
        }
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, payload)
                row = cur.fetchone()
            conn.commit()
        return row or payload

    def has_fetch_log(
        self,
        source_name: str,
        fetch_scope: str,
        period_start: Optional[date],
        period_end: Optional[date],
        content_hash: str,
    ) -> bool:
        sql = """
            SELECT 1
            FROM source_fetch_log
            WHERE source_name = %(source_name)s
              AND fetch_scope = %(fetch_scope)s
              AND period_start IS NOT DISTINCT FROM %(period_start)s
              AND period_end IS NOT DISTINCT FROM %(period_end)s
              AND content_hash = %(content_hash)s
            LIMIT 1;
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    {
                        "source_name": source_name,
                        "fetch_scope": fetch_scope,
                        "period_start": period_start,
                        "period_end": period_end,
                        "content_hash": content_hash,
                    },
                )
                return cur.fetchone() is not None

    def record_fetch_log(
        self,
        source_name: str,
        fetch_scope: str,
        period_start: Optional[date],
        period_end: Optional[date],
        content_hash: str,
    ) -> None:
        sql = """
            INSERT INTO source_fetch_log (source_name, fetch_scope, period_start, period_end, content_hash)
            VALUES (%(source_name)s, %(fetch_scope)s, %(period_start)s, %(period_end)s, %(content_hash)s)
            ON CONFLICT DO NOTHING;
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    {
                        "source_name": source_name,
                        "fetch_scope": fetch_scope,
                        "period_start": period_start,
                        "period_end": period_end,
                        "content_hash": content_hash,
                    },
                )
            conn.commit()

    def add_report(
        self, trail_id: int, condition_tags: List[str], notes: Optional[str], reporter_name: Optional[str]
    ) -> Dict:
        moderation_status_select = self._optional_column_sql(
            table_name="user_reports",
            preferred_column="moderation_status",
            fallback_sql="'pending'",
        )
        moderated_at_select = self._optional_column_sql(
            table_name="user_reports",
            preferred_column="moderated_at",
            fallback_sql="NULL",
        )
        sql = """
            INSERT INTO user_reports (trail_id, condition_tags, notes, reporter_name)
            VALUES (%(trail_id)s, %(condition_tags)s, %(notes)s, %(reporter_name)s)
            RETURNING id, trail_id, condition_tags, notes, reporter_name, reported_at, upvotes,
                      {moderation_status_select} AS moderation_status,
                      {moderated_at_select} AS moderated_at;
        """
        sql = sql.format(
            moderation_status_select=moderation_status_select,
            moderated_at_select=moderated_at_select,
        )
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    {
                        "trail_id": trail_id,
                        "condition_tags": condition_tags,
                        "notes": notes,
                        "reporter_name": reporter_name,
                    },
                )
                row = cur.fetchone()
            conn.commit()
        return row

    def upvote_report(self, report_id: int) -> Optional[Dict]:
        moderation_status_select = self._optional_column_sql(
            table_name="user_reports",
            preferred_column="moderation_status",
            fallback_sql="'pending'",
        )
        moderated_at_select = self._optional_column_sql(
            table_name="user_reports",
            preferred_column="moderated_at",
            fallback_sql="NULL",
        )
        sql = """
            UPDATE user_reports
            SET upvotes = upvotes + 1
            WHERE id = %(report_id)s
            RETURNING id, trail_id, condition_tags, notes, reporter_name, reported_at, upvotes,
                      {moderation_status_select} AS moderation_status,
                      {moderated_at_select} AS moderated_at;
        """
        sql = sql.format(
            moderation_status_select=moderation_status_select,
            moderated_at_select=moderated_at_select,
        )
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"report_id": report_id})
                row = cur.fetchone()
            conn.commit()
        return row

    def resolve_report(self, report_id: int) -> bool:
        columns = self._get_table_columns("user_reports")
        if "moderation_status" in columns:
            sql = """
                UPDATE user_reports
                SET moderation_status = 'resolved',
                    moderated_at = NOW()
                WHERE id = %(report_id)s;
            """
        elif "resolved_at" in columns:
            sql = """
                UPDATE user_reports
                SET resolved_at = NOW()
                WHERE id = %(report_id)s;
            """
        else:
            return False

        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"report_id": report_id})
                changed = cur.rowcount > 0
            conn.commit()
        return changed

    def _get_table_columns(self, table_name: str) -> set[str]:
        sql = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %(table_name)s;
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"table_name": table_name})
                rows = cur.fetchall()
        return {row["column_name"] for row in rows}

    def _optional_column_sql(self, table_name: str, preferred_column: str, fallback_sql: str) -> str:
        columns = self._get_table_columns(table_name)
        if preferred_column in columns:
            return preferred_column
        return fallback_sql

    def _map_trail_row(self, row: Dict) -> Dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "region": row["region"],
            "difficulty": row["difficulty"],
            "length_km": float(row["length_km"]),
            "elevation_gain_m": int(row["elevation_gain_m"]),
            "traversability_score": float(row["traversability_score"]),
            "location": {
                "state_code": row.get("state_code"),
                "city": row.get("city"),
                "park_name": row.get("park_name"),
                "park_type": row.get("park_type"),
                "county": row.get("county"),
            }
            if row.get("state_code")
            else None,
            "lat": float(row["lat"]) if row.get("lat") is not None else None,
            "lng": float(row["lng"]) if row.get("lng") is not None else None,
            "route_coordinates": row.get("route_coordinates"),
        }

    def get_hazards_for_dedupe(self, trail_ids: Sequence[int], since: datetime) -> List[Dict]:
        if not trail_ids:
            return []
        sql = """
            SELECT id, trail_id, type, severity, source, confidence, reported_at, raw_text, resolved_at
            FROM hazards
            WHERE trail_id = ANY(%(trail_ids)s)
              AND reported_at >= %(since)s
              AND resolved_at IS NULL;
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"trail_ids": list(trail_ids), "since": since})
                return cur.fetchall()

    def persist_hazards(self, hazards: Sequence[Dict]) -> int:
        if not hazards:
            return 0
        sql = """
            INSERT INTO hazards (trail_id, type, severity, source, confidence, reported_at, raw_text)
            VALUES (
              %(trail_id)s, %(type)s, %(severity)s, %(source)s, %(confidence)s, %(reported_at)s, %(raw_text)s
            );
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                for hazard in hazards:
                    cur.execute(
                        sql,
                        {
                            "trail_id": hazard["trail_id"],
                            "type": hazard["type"],
                            "severity": hazard["severity"],
                            "source": hazard["source"],
                            "confidence": hazard["confidence"],
                            "reported_at": hazard["reported_at"],
                            "raw_text": hazard.get("raw_text"),
                        },
                    )
            conn.commit()
        return len(hazards)

    def append_ingestion_task_failure(self, record: Dict[str, Any]) -> Dict[str, Any]:
        sql = """
            INSERT INTO ingestion_task_failures (
              task_name, task_id, task_args, task_kwargs, exc_type, exc_message, exc_repr
            )
            VALUES (
              %(task_name)s, %(task_id)s, %(task_args)s::jsonb, %(task_kwargs)s::jsonb,
              %(exc_type)s, %(exc_message)s, %(exc_repr)s
            )
            RETURNING id, task_name, task_id, task_args, task_kwargs, exc_type, exc_message, exc_repr, created_at;
        """
        payload = {
            "task_name": record["task_name"],
            "task_id": record.get("task_id"),
            "task_args": json.dumps(record.get("task_args", [])),
            "task_kwargs": json.dumps(record.get("task_kwargs", {})),
            "exc_type": record.get("exc_type", "Exception"),
            "exc_message": record.get("exc_message", ""),
            "exc_repr": record.get("exc_repr", ""),
        }
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, payload)
                row = cur.fetchone()
            conn.commit()
        return dict(row) if row else {}

    def list_ingestion_task_failures(self, limit: int = 20) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, task_name, task_id, task_args, task_kwargs, exc_type, exc_message, exc_repr, created_at
            FROM ingestion_task_failures
            ORDER BY id DESC
            LIMIT %(limit)s;
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"limit": max(0, int(limit))})
                return list(cur.fetchall())
