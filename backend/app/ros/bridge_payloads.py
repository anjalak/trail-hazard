from __future__ import annotations

from typing import Any, Dict, List


ROBOTICS_TRAVERSABILITY_QUERY = """
query RoboticsBridge($trailId: Int!) {
  roboticsTraversability(trailId: $trailId) {
    trailId
    name
    riskScore
    traversabilityScore
    hazardLocationQuality
    planningNotes
    rosCompatibleRoute
    hazardSummary {
      activeCount
      highestSeverity
      types
    }
  }
}
"""


def graphql_body_for_trail(trail_id: int) -> Dict[str, Any]:
    return {
        "query": ROBOTICS_TRAVERSABILITY_QUERY,
        "variables": {"trailId": int(trail_id)},
        "operationName": "RoboticsBridge",
    }


def route_points_from_payload(payload: Dict[str, Any]) -> List[Dict[str, float]]:
    data = payload.get("data") or {}
    traversability = data.get("roboticsTraversability") or {}
    ros_route = traversability.get("rosCompatibleRoute") or {}
    poses = ros_route.get("poses") or []
    points: List[Dict[str, float]] = []
    for pose in poses:
        position = pose.get("position") or {}
        points.append(
            {
                "x": float(position.get("x", 0.0)),
                "y": float(position.get("y", 0.0)),
                "z": float(position.get("z", 0.0)),
            }
        )
    return points


def bridge_status_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload.get("data") or {}
    traversability = data.get("roboticsTraversability") or {}
    hazard_summary = traversability.get("hazardSummary") or {}
    return {
        "trail_id": traversability.get("trailId"),
        "trail_name": traversability.get("name"),
        "risk_score": float(traversability.get("riskScore", 0.0)),
        "traversability_score": float(traversability.get("traversabilityScore", 0.0)),
        "hazard_location_quality": traversability.get("hazardLocationQuality", "unknown"),
        "hazard_summary": {
            "active_count": int(hazard_summary.get("activeCount", 0)),
            "highest_severity": hazard_summary.get("highestSeverity", "low"),
            "types": list(hazard_summary.get("types") or []),
        },
        "planning_notes": list(traversability.get("planningNotes") or []),
    }
