from typing import Optional

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
import app.main as app_main
from app.services.repository import InMemoryRepository


def _post_graphql(
    client: TestClient,
    query: str,
    variables: Optional[dict] = None,
    headers: Optional[dict[str, str]] = None,
) -> dict:
    response = client.post(
        "/graphql",
        json={"query": query, "variables": variables},
        headers=headers or {},
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture(autouse=True)
def _reset_rate_limits_between_tests() -> None:
    from app.services.report_rate_limit import reset_rate_limit_state_for_tests

    reset_rate_limit_state_for_tests()


def test_trail_hazards_geojson_returns_json_object() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        query Geo($trailId: Int!) {
          trailHazardsGeojson(trailId: $trailId)
        }
        """,
        {"trailId": 1},
    )

    geojson = payload["data"]["trailHazardsGeojson"]
    assert geojson["type"] == "FeatureCollection"
    assert isinstance(geojson["features"], list)


def test_submit_report_rejects_invalid_tags() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        mutation Submit($input: SubmitReportInput!) {
          submitReport(input: $input) {
            id
          }
        }
        """,
        {
            "input": {
                "trailId": 1,
                "conditionTags": ["snow", "unknown_tag"],
                "notes": "Looks rough",
                "reporterName": "tester",
            }
        },
    )

    assert payload.get("errors")
    assert "unsupported tags" in payload["errors"][0]["message"]


def test_submit_report_rejects_overlong_notes() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        mutation Submit($input: SubmitReportInput!) {
          submitReport(input: $input) {
            id
          }
        }
        """,
        {
            "input": {
                "trailId": 1,
                "conditionTags": ["snow"],
                "notes": "a" * 501,
                "reporterName": "tester",
            }
        },
    )

    assert payload.get("errors")
    assert "at most 500 characters" in payload["errors"][0]["message"]


def test_submit_report_sanitizes_text_inputs() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        mutation Submit($input: SubmitReportInput!) {
          submitReport(input: $input) {
            notes
            reporterName
          }
        }
        """,
        {
            "input": {
                "trailId": 1,
                "conditionTags": ["snow"],
                "notes": "  icy\x00 section\t\tnear bridge  ",
                "reporterName": "  hiker\x07 one  ",
            }
        },
    )

    report = payload["data"]["submitReport"]
    assert report["notes"] == "icy section near bridge"
    assert report["reporterName"] == "hiker one"


def test_resolve_report_updates_moderation_status() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    submit_payload = _post_graphql(
        client,
        """
        mutation Submit($input: SubmitReportInput!) {
          submitReport(input: $input) {
            id
          }
        }
        """,
        {
            "input": {
                "trailId": 1,
                "conditionTags": ["snow"],
                "notes": "For resolve test",
                "reporterName": "resolver-qa",
            }
        },
    )
    report_id = submit_payload["data"]["submitReport"]["id"]

    resolve_payload = _post_graphql(
        client,
        """
        mutation Resolve($id: Int!) {
          resolveReport(reportId: $id)
        }
        """,
        {"id": report_id},
    )
    assert resolve_payload["data"]["resolveReport"] is True

    conditions_payload = _post_graphql(
        client,
        """
        query Conditions($trailId: Int!) {
          trailConditions(trailId: $trailId) {
            recentReports {
              id
              moderationStatus
              moderatedAt
            }
          }
        }
        """,
        {"trailId": 1},
    )

    recent = {row["id"]: row for row in conditions_payload["data"]["trailConditions"]["recentReports"]}
    assert recent[report_id]["moderationStatus"] == "resolved"
    assert recent[report_id]["moderatedAt"] is not None


def test_graphql_logs_operation_metadata(caplog) -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)
    caplog.set_level("INFO", logger="trailintel.graphql")

    payload = _post_graphql(
        client,
        """
        mutation Submit($input: SubmitReportInput!) {
          submitReport(input: $input) {
            id
          }
        }
        """,
        {
            "input": {
                "trailId": 1,
                "conditionTags": ["not_allowed"],
                "notes": "Bad tag",
                "reporterName": "tester",
            }
        },
    )
    assert payload.get("errors")

    matching = [record for record in caplog.records if record.name == "trailintel.graphql"]
    assert matching
    last = matching[-1]
    assert last.operation_name == "anonymous"
    assert last.has_errors is True
    assert last.duration_ms >= 0


def test_search_trails_by_name_with_location_filters() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        query Search($query: String!, $stateCode: String, $parkType: String, $parkNameContains: String) {
          searchTrailsByName(
            query: $query
            stateCode: $stateCode
            parkType: $parkType
            parkNameContains: $parkNameContains
          ) {
            id
            name
            location {
              stateCode
              parkType
              parkName
            }
          }
        }
        """,
        {
            "query": "silver",
            "stateCode": "WA",
            "parkType": "national_park",
            "parkNameContains": "rainier",
        },
    )

    trails = payload["data"]["searchTrailsByName"]
    assert len(trails) == 1
    assert trails[0]["name"] == "Silver Forest"
    assert trails[0]["location"]["stateCode"] == "WA"
    assert trails[0]["location"]["parkType"] == "national_park"


def test_search_trails_by_name_prefers_prefix_matches_for_autocomplete() -> None:
    repo = InMemoryRepository(use_fallback_snapshot=False)
    repo.trails = [
        {
            "id": 101,
            "name": "Pine Ridge",
            "region": "WA Cascades",
            "location": {
                "state_code": "WA",
                "city": "Bellingham",
                "park_name": "Mount Baker",
                "park_type": "national_forest",
                "county": "Whatcom",
            },
            "difficulty": "moderate",
            "length_km": 8.0,
            "elevation_gain_m": 400,
            "traversability_score": 0.8,
            "lat": 48.86,
            "lng": -121.68,
        },
        {
            "id": 102,
            "name": "Deception Pass Trail",
            "region": "WA Islands",
            "location": {
                "state_code": "WA",
                "city": "Oak Harbor",
                "park_name": "Deception Pass State Park",
                "park_type": "state_park",
                "county": "Island",
            },
            "difficulty": "easy",
            "length_km": 6.2,
            "elevation_gain_m": 120,
            "traversability_score": 0.9,
            "lat": 48.4,
            "lng": -122.65,
        },
    ]
    app_main.repo = repo
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        query Search($query: String!) {
          searchTrailsByName(query: $query) {
            id
            name
          }
        }
        """,
        {"query": "d"},
    )

    trails = payload["data"]["searchTrailsByName"]
    assert [trail["id"] for trail in trails] == [102, 101]


def test_nearby_trails_query_returns_expected_hit() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        query Nearby($lat: Float!, $lng: Float!, $km: Float!, $city: String) {
          nearbyTrails(lat: $lat, lng: $lng, km: $km, city: $city) {
            id
            name
            location {
              city
            }
          }
        }
        """,
        {"lat": 46.912688, "lng": -121.642024, "km": 280.0, "city": "Ashford"},
    )

    trails = payload["data"]["nearbyTrails"]
    assert trails
    assert any(trail["id"] == 1 for trail in trails)
    assert all(trail["location"]["city"] == "Ashford" for trail in trails)


def test_nearby_trails_query_excludes_synthetic_geometry() -> None:
    repo = InMemoryRepository(use_fallback_snapshot=False)
    repo.trails = [
        {
            "id": 201,
            "name": "Synthetic Placeholder",
            "region": "WA",
            "location": {
                "state_code": "WA",
                "city": "Ashford",
                "park_name": "Demo Park",
                "park_type": "national_park",
                "county": "Pierce",
            },
            "difficulty": "easy",
            "length_km": 3.0,
            "elevation_gain_m": 120,
            "traversability_score": 0.6,
            "lat": 46.9127,
            "lng": -121.6420,
            "geometry_quality": "synthetic",
        },
        {
            "id": 202,
            "name": "Imported Trail",
            "region": "WA",
            "location": {
                "state_code": "WA",
                "city": "Ashford",
                "park_name": "Rainier",
                "park_type": "national_park",
                "county": "Pierce",
            },
            "difficulty": "moderate",
            "length_km": 9.2,
            "elevation_gain_m": 520,
            "traversability_score": 0.82,
            "lat": 46.9130,
            "lng": -121.6425,
            "geometry_quality": "imported_nps",
        },
    ]
    app_main.repo = repo
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        query Nearby($lat: Float!, $lng: Float!, $km: Float!) {
          nearbyTrails(lat: $lat, lng: $lng, km: $km) {
            id
            name
          }
        }
        """,
        {"lat": 46.9128, "lng": -121.6422, "km": 5.0},
    )

    trails = payload["data"]["nearbyTrails"]
    assert [trail["id"] for trail in trails] == [202]


def test_nearby_trails_collapses_same_name_same_park() -> None:
    """NPS imports one row per segment; list APIs should show one row per trail name per park."""
    park_loc = {
        "state_code": "WA",
        "city": "Marblemount",
        "park_name": "North Cascades National Park",
        "park_type": "national_park",
        "county": "Whatcom",
    }
    repo = InMemoryRepository(use_fallback_snapshot=False)
    repo.trails = [
        {
            "id": 61,
            "name": "Sourdough Mountain Trail",
            "region": "North Cascades",
            "location": park_loc,
            "difficulty": "moderate",
            "length_km": 5.0,
            "elevation_gain_m": 0,
            "traversability_score": 0.7,
            "lat": 48.80,
            "lng": -121.50,
            "geometry_quality": "imported_nps",
        },
        {
            "id": 73,
            "name": "Sourdough Mountain Trail",
            "region": "North Cascades",
            "location": park_loc,
            "difficulty": "moderate",
            "length_km": 2.0,
            "elevation_gain_m": 0,
            "traversability_score": 0.7,
            "lat": 48.743,
            "lng": -121.103,
            "geometry_quality": "imported_nps",
        },
    ]
    app_main.repo = repo
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        query Nearby($lat: Float!, $lng: Float!, $km: Float!) {
          nearbyTrails(lat: $lat, lng: $lng, km: $km) {
            id
            name
          }
        }
        """,
        {"lat": 48.743, "lng": -121.103, "km": 50.0},
    )

    trails = payload["data"]["nearbyTrails"]
    assert len(trails) == 1
    assert trails[0]["id"] == 73
    assert trails[0]["name"] == "Sourdough Mountain Trail"


def test_trail_conditions_response_shape() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        query Conditions($trailId: Int!) {
          trailConditions(trailId: $trailId) {
            trailId
            name
            region
            location {
              parkName
              city
              stateCode
            }
            lat
            lng
            overallScore
            hazardSummary {
              activeCount
              highestSeverity
              types
            }
            activeHazards {
              id
              type
              reportedAt
            }
            recentHazardCount
            hasRecentInfo
            seasonalIntel {
              month
              gearRecommendations
            }
            recentReports {
              id
              conditionTags
              notes
              reporterName
              upvotes
            }
            lastUpdated
          }
        }
        """,
        {"trailId": 1},
    )

    conditions = payload["data"]["trailConditions"]
    assert conditions["trailId"] == 1
    assert conditions["region"] == "Mount Rainier"
    assert conditions["location"]["stateCode"] == "WA"
    assert conditions["lat"] is not None
    assert conditions["lng"] is not None
    assert isinstance(conditions["hazardSummary"]["types"], list)
    assert "highestSeverity" in conditions["hazardSummary"]
    assert isinstance(conditions["activeHazards"], list)
    assert isinstance(conditions["recentHazardCount"], int)
    assert isinstance(conditions["hasRecentInfo"], bool)
    assert conditions["seasonalIntel"] is None
    assert isinstance(conditions["recentReports"], list)
    assert conditions["lastUpdated"] is not None


def test_robotics_traversability_payload_shape() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        query Robotics($trailId: Int!) {
          roboticsTraversability(trailId: $trailId) {
            trailId
            name
            routeGeojson
            hazardsGeojson
            hazardSummary {
              activeCount
              highestSeverity
              types
            }
            dataFreshness {
              generatedAt
              latestHazardAt
              sourceCount
              stale
            }
            geometryQuality
            geometrySource
            vertexCount
            rosCompatibleRoute
            traversabilityScore
            riskScore
            effortScore
            segmentCosts
            elevationProfile
            costModel
            hazardLocationQuality
            planningNotes
          }
        }
        """,
        {"trailId": 1},
    )

    robotics = payload["data"]["roboticsTraversability"]
    assert robotics["trailId"] == 1
    assert robotics["name"] == "Silver Forest"
    assert robotics["routeGeojson"]["type"] == "Feature"
    assert robotics["routeGeojson"]["geometry"]["type"] == "LineString"
    assert robotics["hazardsGeojson"]["type"] == "FeatureCollection"
    assert robotics["hazardsGeojson"]["features"] == []
    assert robotics["hazardSummary"]["activeCount"] == 1
    assert robotics["hazardSummary"]["highestSeverity"] == "medium"
    assert robotics["hazardSummary"]["types"] == ["washout"]
    assert robotics["dataFreshness"]["generatedAt"] is not None
    assert robotics["dataFreshness"]["latestHazardAt"] is not None
    assert robotics["dataFreshness"]["sourceCount"] == 1
    assert robotics["dataFreshness"]["stale"] is True
    assert robotics["geometryQuality"] == "imported_nps"
    assert robotics["geometrySource"].startswith("NPS Public Trails")
    assert robotics["vertexCount"] == 3
    assert isinstance(robotics["traversabilityScore"], float)
    assert 0 <= robotics["riskScore"] <= 1
    assert 0 <= robotics["effortScore"] <= 1
    assert isinstance(robotics["segmentCosts"], list)
    assert isinstance(robotics["elevationProfile"], list)
    assert robotics["costModel"]["version"] == "v2-segment-aware"
    assert robotics["planningNotes"]


def test_robotics_traversability_ros_compatible_route_shape() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        query Robotics($trailId: Int!) {
          roboticsTraversability(trailId: $trailId) {
            rosCompatibleRoute
          }
        }
        """,
        {"trailId": 1},
    )

    route = payload["data"]["roboticsTraversability"]["rosCompatibleRoute"]
    assert route["header"]["frame_id"] == "map"
    assert route["header"]["coordinate_system"] == "WGS84"
    assert route["header"]["axes"] == {
        "x": "longitude_degrees",
        "y": "latitude_degrees",
        "z": "elevation_meters",
    }
    assert len(route["poses"]) == 12
    assert len(route["costs"]) == len(route["poses"])
    first_pose = route["poses"][0]
    assert set(first_pose["position"].keys()) == {"x", "y", "z"}
    assert first_pose["position"]["z"] == 0.0
    assert first_pose["orientation"] == {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
    # Fallback segment mode can normalize all pose costs equal when elevation gain data is unavailable.


def test_robotics_traversability_returns_segment_cost_details() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        query Robotics($trailId: Int!) {
          roboticsTraversability(trailId: $trailId) {
            riskScore
            segmentCosts
            elevationProfile
            costModel
          }
        }
        """,
        {"trailId": 1},
    )

    robotics = payload["data"]["roboticsTraversability"]
    segment_costs = robotics["segmentCosts"]
    assert segment_costs
    assert len(segment_costs) == len(robotics["elevationProfile"]) - 1
    assert all("estimated_grade" in segment for segment in segment_costs)
    assert all("cost" in segment for segment in segment_costs)
    average_segment_cost = sum(segment["cost"] for segment in segment_costs) / len(segment_costs)
    assert abs(average_segment_cost - robotics["riskScore"]) <= 0.08
    assert robotics["costModel"]["fallback_mode"] is True


def test_robotics_traversability_handles_missing_hazard_coordinates() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        query Robotics($trailId: Int!) {
          roboticsTraversability(trailId: $trailId) {
            hazardLocationQuality
            hazardsGeojson
            planningNotes
            rosCompatibleRoute
          }
        }
        """,
        {"trailId": 1},
    )

    robotics = payload["data"]["roboticsTraversability"]
    assert robotics["hazardLocationQuality"] == "trail_level"
    assert robotics["hazardsGeojson"]["features"] == []
    assert any("route-level risk" in note for note in robotics["planningNotes"])
    assert robotics["rosCompatibleRoute"]["poses"]


def test_robotics_traversability_enriches_exact_hazard_geojson() -> None:
    repo = InMemoryRepository()
    repo.hazards[0]["location"] = {"lat": 47.415, "lng": -121.429}
    app_main.repo = repo
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        query Robotics($trailId: Int!) {
          roboticsTraversability(trailId: $trailId) {
            hazardLocationQuality
            hazardsGeojson
            planningNotes
          }
        }
        """,
        {"trailId": 1},
    )

    robotics = payload["data"]["roboticsTraversability"]
    features = robotics["hazardsGeojson"]["features"]
    assert robotics["hazardLocationQuality"] == "exact"
    assert len(features) == 1
    assert features[0]["geometry"]["coordinates"] == [-121.429, 47.415]
    assert features[0]["properties"]["hazardId"] == 1
    assert features[0]["properties"]["confidence"] == pytest.approx(0.86, rel=0, abs=0.02)
    assert features[0]["properties"]["source"] == "scraped"
    assert features[0]["properties"]["reportedAt"] is not None
    assert 0 <= features[0]["properties"]["riskCost"] <= 1
    assert any("explicit point location" in note for note in robotics["planningNotes"])


def test_robotics_area_returns_mission_summary() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    payload = _post_graphql(
        client,
        """
        query RoboticsArea($lat: Float!, $lng: Float!, $radiusM: Float!) {
          roboticsArea(lat: $lat, lng: $lng, radiusM: $radiusM) {
            center {
              lat
              lng
            }
            radiusM
            activeHazardCount
            hazardDensity
            areaRiskScore
            highestRiskTrail {
              trailId
              name
              riskScore
              activeHazardCount
              hazardLocationQuality
            }
            recommendedTrailIds
            trails {
              trailId
              name
              traversabilityScore
              riskScore
              effortScore
              activeHazardCount
              hazardLocationQuality
            }
            generatedAt
          }
        }
        """,
        {"lat": 46.913, "lng": -121.642, "radiusM": 40000.0},
    )

    area = payload["data"]["roboticsArea"]
    assert area["center"] == {"lat": 46.913, "lng": -121.642}
    assert area["radiusM"] == 40000.0
    assert area["activeHazardCount"] >= 1
    assert area["hazardDensity"] >= 0
    assert 0 <= area["areaRiskScore"] <= 1
    assert area["highestRiskTrail"]["trailId"] is not None
    assert isinstance(area["recommendedTrailIds"], list)
    assert len(area["trails"]) >= 1
    assert all(0 <= trail["effortScore"] <= 1 for trail in area["trails"])
    assert area["generatedAt"] is not None


def test_report_mutations_submit_upvote_and_resolve() -> None:
    app_main.repo = InMemoryRepository()
    client = TestClient(app)

    submit_payload = _post_graphql(
        client,
        """
        mutation Submit($input: SubmitReportInput!) {
          submitReport(input: $input) {
            id
            trailId
            conditionTags
            upvotes
            moderationStatus
          }
        }
        """,
        {
            "input": {
                "trailId": 1,
                "conditionTags": ["snow"],
                "notes": "Test report",
                "reporterName": "qa-run",
            }
        },
    )
    report_id = submit_payload["data"]["submitReport"]["id"]
    assert submit_payload["data"]["submitReport"]["trailId"] == 1
    assert submit_payload["data"]["submitReport"]["upvotes"] == 0

    upvote_payload = _post_graphql(
        client,
        """
        mutation Upvote($reportId: Int!) {
          upvoteReport(reportId: $reportId) {
            id
            upvotes
          }
        }
        """,
        {"reportId": report_id},
    )
    assert upvote_payload["data"]["upvoteReport"]["id"] == report_id
    assert upvote_payload["data"]["upvoteReport"]["upvotes"] == 1

    resolve_payload = _post_graphql(
        client,
        """
        mutation Resolve($reportId: Int!) {
          resolveReport(reportId: $reportId)
        }
        """,
        {"reportId": report_id},
    )
    assert resolve_payload["data"]["resolveReport"] is True


def test_submit_report_graphql_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_submit_max_per_window", 2)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 3600)
    monkeypatch.setattr(settings, "rate_limit_reports_enabled", True)

    app_main.repo = InMemoryRepository()
    client = TestClient(app)
    hdr = {"X-Forwarded-For": "203.0.113.120"}

    mutation = """
        mutation Submit($input: SubmitReportInput!) {
          submitReport(input: $input) {
            id
          }
        }
    """
    variables = {
        "input": {
            "trailId": 1,
            "conditionTags": ["snow"],
            "notes": "one",
            "reporterName": "rl-test",
        }
    }

    assert _post_graphql(client, mutation, variables, headers=hdr)["data"]["submitReport"]["id"]
    assert _post_graphql(client, mutation, variables, headers=hdr)["data"]["submitReport"]["id"]

    payload = _post_graphql(client, mutation, variables, headers=hdr)
    assert payload.get("errors")
    assert payload["errors"][0].get("extensions", {}).get("code") == "RATE_LIMITED"


def test_upvote_report_graphql_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_upvote_max_per_window", 2)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 3600)
    monkeypatch.setattr(settings, "rate_limit_reports_enabled", True)

    app_main.repo = InMemoryRepository()
    client = TestClient(app)
    hdr = {"X-Forwarded-For": "203.0.113.121"}

    created = _post_graphql(
        client,
        """
        mutation Submit($input: SubmitReportInput!) {
          submitReport(input: $input) { id }
        }
        """,
        {
            "input": {
                "trailId": 1,
                "conditionTags": ["snow"],
                "notes": "upvote rl",
                "reporterName": "rl-submit",
            }
        },
    )
    report_id = created["data"]["submitReport"]["id"]

    mutation = """
        mutation Upvote($reportId: Int!) {
          upvoteReport(reportId: $reportId) {
            id
          }
        }
    """

    assert _post_graphql(client, mutation, {"reportId": report_id}, headers=hdr)["data"]["upvoteReport"]["id"]
    assert _post_graphql(client, mutation, {"reportId": report_id}, headers=hdr)["data"]["upvoteReport"]["id"]

    payload = _post_graphql(client, mutation, {"reportId": report_id}, headers=hdr)
    assert payload.get("errors")
    assert payload["errors"][0].get("extensions", {}).get("code") == "RATE_LIMITED"
