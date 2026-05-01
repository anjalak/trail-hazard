"""PostgresRepository integration tests (PostGIS + filter SQL).

Requires PostGIS and TEST_DATABASE_URL (see docs/running-and-debugging.md).
CI sets TEST_DATABASE_URL automatically; locally export it to run these tests.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest

from app.services.postgres_repository import PostgresRepository

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = BACKEND_ROOT / "app" / "models" / "seed.sql"

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to run Postgres/PostGIS tests (see docs/running-and-debugging.md).",
)


def _apply_migrations_and_seed(url: str) -> None:
    env = {**os.environ, "DATABASE_URL": url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        check=True,
    )
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(SEED_PATH.read_text(encoding="utf-8"))
        conn.commit()


@pytest.fixture(scope="session", name="pg_repo")
def postgres_repository_session() -> PostgresRepository:
    url = os.environ["TEST_DATABASE_URL"]
    assert url
    _apply_migrations_and_seed(url)
    return PostgresRepository(url)


def test_search_filters_state_and_park_type(pg_repo: PostgresRepository) -> None:
    rows = pg_repo.search_trails(
        "silver",
        limit=20,
        state_code="WA",
        park_type="national_park",
        park_name_contains="rainier",
    )
    assert {r["id"] for r in rows} == {1}


def test_search_filters_city_and_park_name_contains(pg_repo: PostgresRepository) -> None:
    rows = pg_repo.search_trails(
        "tipsoo",
        limit=10,
        city="ashford",
        park_name_contains="rainier",
    )
    assert len(rows) == 1
    assert rows[0]["id"] == 10
    assert rows[0]["location"]["park_name"] == "Mount Rainier National Park"


def test_search_case_insensitive_state_and_combined_filters(pg_repo: PostgresRepository) -> None:
    rows = pg_repo.search_trails(
        "emmons moraine",
        limit=10,
        state_code="wa",
        park_type="national_park",
        park_name_contains="rainier",
    )
    assert {r["id"] for r in rows} == {11}


def test_search_no_false_positive_when_filters_exclude(pg_repo: PostgresRepository) -> None:
    rows = pg_repo.search_trails(
        "silver",
        limit=20,
        state_code="WA",
        city="north bend",
        park_type="national_park",
    )
    assert rows == []


def test_nearby_tight_radius_only_closest_trail(pg_repo: PostgresRepository) -> None:
    pivot = pg_repo.get_trail(1)
    assert pivot is not None
    rows = pg_repo.nearby_trails(pivot["lat"], pivot["lng"], 0.08)
    assert {r["id"] for r in rows} == {1}


def test_nearby_medium_radius_includes_additional_mount_rainier_trails(pg_repo: PostgresRepository) -> None:
    pivot = pg_repo.get_trail(1)
    assert pivot is not None
    rows = pg_repo.nearby_trails(pivot["lat"], pivot["lng"], 35.0, state_code="WA")
    ids = {r["id"] for r in rows}
    assert ids.issuperset({1, 2})
    assert all(r["location"]["park_name"] == "Mount Rainier National Park" for r in rows)


def test_nearby_wide_radius_crosses_regions(pg_repo: PostgresRepository) -> None:
    pivot = pg_repo.get_trail(1)
    assert pivot is not None
    rows = pg_repo.nearby_trails(pivot["lat"], pivot["lng"], 250.0, state_code="WA")
    location_names = {r["location"]["park_name"] for r in rows}
    assert location_names > {"Mount Rainier National Park"}


def test_nearby_filters_park_type(pg_repo: PostgresRepository) -> None:
    pivot = pg_repo.get_trail(1)
    assert pivot is not None
    rows = pg_repo.nearby_trails(
        pivot["lat"],
        pivot["lng"],
        120.0,
        park_type="national_forest",
    )
    assert rows == []


def test_nearby_filters_city(pg_repo: PostgresRepository) -> None:
    pivot = pg_repo.get_trail(1)
    assert pivot is not None
    rows = pg_repo.nearby_trails(
        pivot["lat"],
        pivot["lng"],
        250.0,
        city="ashford",
    )
    ids = {r["id"] for r in rows}
    assert ids.issuperset({1, 10})


def test_nearby_filters_state_code(pg_repo: PostgresRepository) -> None:
    pivot = pg_repo.get_trail(1)
    assert pivot is not None
    rows = pg_repo.nearby_trails(pivot["lat"], pivot["lng"], 350.0, state_code="wa")
    ids = {r["id"] for r in rows}
    assert ids.issuperset({1, 51})


def test_get_trail_round_trip(pg_repo: PostgresRepository) -> None:
    row = pg_repo.get_trail(1)
    assert row is not None
    assert row["id"] == 1
    assert row["location"]["state_code"] == "WA"


def test_get_trail_route_geojson_exports_linestring(pg_repo: PostgresRepository) -> None:
    route = pg_repo.get_trail_route_geojson(1)
    assert route is not None
    assert route["type"] == "Feature"
    assert route["geometry"]["type"] == "LineString"
    assert route["geometry"]["coordinates"] == [
        [-121.642036, 46.912687],
        [-121.642009, 46.912676],
        [-121.642007, 46.912675],
    ]
    assert route["properties"]["trailId"] == 1
    assert route["properties"]["geometryQuality"] == "imported_nps"
    assert route["properties"]["geometrySource"].startswith("NPS Public Trails")


def test_get_trail_route_geojson_exposes_imported_nps_metadata(pg_repo: PostgresRepository) -> None:
    route = pg_repo.get_trail_route_geojson(51)
    assert route is not None
    assert route["geometry"]["type"] == "LineString"
    assert len(route["geometry"]["coordinates"]) == 165
    assert route["properties"]["trailId"] == 51
    assert route["properties"]["geometryQuality"] == "imported_nps"
    assert route["properties"]["geometrySource"].startswith("NPS Public Trails")
    assert route["properties"]["geometrySourceUrl"] == (
        "https://mapservices.nps.gov/arcgis/rest/services/"
        "NationalDatasets/NPS_Public_Trails/FeatureServer/0"
    )
