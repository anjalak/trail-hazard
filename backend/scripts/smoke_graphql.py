#!/usr/bin/env python3
from __future__ import annotations

from app.runtime_check import ensure_supported_python

ensure_supported_python()

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_graphql(graphql_url: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        graphql_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _assert_graphql_ok(payload: dict[str, Any], operation_name: str) -> dict[str, Any]:
    if payload.get("errors"):
        raise RuntimeError(f"{operation_name} returned GraphQL errors: {payload['errors']}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"{operation_name} response did not include data object")
    return data


def run(base_url: str) -> None:
    health_url = f"{base_url}/health"
    graphql_url = f"{base_url}/graphql"

    health = _get_json(health_url)
    if health.get("status") != "ok":
        raise RuntimeError(f"Health check failed: {health}")
    print("PASS health endpoint")

    search_data = _assert_graphql_ok(
        _post_graphql(
            graphql_url,
            """
            query Search($query: String!, $stateCode: String) {
              searchTrailsByName(query: $query, stateCode: $stateCode) {
                id
                name
              }
            }
            """,
            {"query": "Trail", "stateCode": "WA"},
        ),
        "searchTrailsByName",
    )
    if not search_data.get("searchTrailsByName"):
        raise RuntimeError("searchTrailsByName returned no rows")
    print("PASS searchTrailsByName query")

    nearby_data = _assert_graphql_ok(
        _post_graphql(
            graphql_url,
            """
            query Nearby($lat: Float!, $lng: Float!, $km: Float!) {
              nearbyTrails(lat: $lat, lng: $lng, km: $km) {
                id
                name
              }
            }
            """,
            {"lat": 47.414, "lng": -121.428, "km": 10.0},
        ),
        "nearbyTrails",
    )
    if not nearby_data.get("nearbyTrails"):
        raise RuntimeError("nearbyTrails returned no rows")
    print("PASS nearbyTrails query")

    conditions_data = _assert_graphql_ok(
        _post_graphql(
            graphql_url,
            """
            query Conditions($trailId: Int!) {
              trailConditions(trailId: $trailId) {
                trailId
                hazardSummary {
                  activeCount
                  highestSeverity
                }
                recentReports {
                  id
                }
              }
            }
            """,
            {"trailId": 1},
        ),
        "trailConditions",
    )
    if not conditions_data.get("trailConditions"):
        raise RuntimeError("trailConditions returned null")
    print("PASS trailConditions query")

    robotics_traversability_data = _assert_graphql_ok(
        _post_graphql(
            graphql_url,
            """
            query RoboticsTraversability($trailId: Int!) {
              roboticsTraversability(trailId: $trailId) {
                trailId
                geometryQuality
                geometrySource
                vertexCount
                hazardLocationQuality
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
                rosCompatibleRoute
                planningNotes
              }
            }
            """,
            {"trailId": 1},
        ),
        "roboticsTraversability",
    )
    robotics_payload = robotics_traversability_data.get("roboticsTraversability")
    if not robotics_payload:
        raise RuntimeError("roboticsTraversability returned null")
    route = robotics_payload.get("rosCompatibleRoute") or {}
    if route.get("header", {}).get("frame_id") != "map" or not route.get("poses"):
        raise RuntimeError("roboticsTraversability returned an invalid ROS-compatible message format")
    if robotics_payload.get("hazardsGeojson", {}).get("type") != "FeatureCollection":
        raise RuntimeError("roboticsTraversability returned invalid hazardsGeojson")
    print("PASS roboticsTraversability query")

    robotics_area_data = _assert_graphql_ok(
        _post_graphql(
            graphql_url,
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
                recommendedTrailIds
                trails {
                  trailId
                  riskScore
                }
                generatedAt
              }
            }
            """,
            {"lat": 47.414, "lng": -121.428, "radiusM": 40000.0},
        ),
        "roboticsArea",
    )
    robotics_area = robotics_area_data.get("roboticsArea")
    if not robotics_area or not robotics_area.get("trails"):
        raise RuntimeError("roboticsArea returned no trail summaries")
    print("PASS roboticsArea query")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check API health and key GraphQL queries.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base API URL, e.g. http://localhost:8000")
    args = parser.parse_args()

    try:
        run(args.base_url.rstrip("/"))
        print("Smoke checks passed.")
        return 0
    except (urllib.error.URLError, TimeoutError) as error:
        print(f"Smoke checks failed due to network error: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Smoke checks failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
