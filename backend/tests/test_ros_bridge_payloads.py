from app.ros.bridge_payloads import bridge_status_from_payload, graphql_body_for_trail, route_points_from_payload


def test_graphql_body_for_trail_sets_query_and_variables() -> None:
    body = graphql_body_for_trail(7)
    assert body["operationName"] == "RoboticsBridge"
    assert body["variables"] == {"trailId": 7}
    assert "roboticsTraversability" in body["query"]


def test_route_points_from_payload_maps_ros_positions() -> None:
    payload = {
        "data": {
            "roboticsTraversability": {
                "rosCompatibleRoute": {
                    "poses": [
                        {"position": {"x": -121.5, "y": 47.4, "z": 0.0}},
                        {"position": {"x": -121.4, "y": 47.5, "z": 1.2}},
                    ]
                }
            }
        }
    }
    points = route_points_from_payload(payload)
    assert points == [
        {"x": -121.5, "y": 47.4, "z": 0.0},
        {"x": -121.4, "y": 47.5, "z": 1.2},
    ]


def test_bridge_status_from_payload_extracts_demo_metadata() -> None:
    payload = {
        "data": {
            "roboticsTraversability": {
                "trailId": 1,
                "name": "Silver Forest",
                "riskScore": 0.42,
                "traversabilityScore": 0.73,
                "hazardLocationQuality": "trail_level",
                "planningNotes": ["demo note"],
                "hazardSummary": {
                    "activeCount": 2,
                    "highestSeverity": "medium",
                    "types": ["snow", "wildlife"],
                },
            }
        }
    }
    status = bridge_status_from_payload(payload)
    assert status["trail_id"] == 1
    assert status["trail_name"] == "Silver Forest"
    assert status["risk_score"] == 0.42
    assert status["hazard_summary"]["active_count"] == 2
    assert status["hazard_summary"]["types"] == ["snow", "wildlife"]
