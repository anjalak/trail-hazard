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


def _post_graphql(graphql_url: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        graphql_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _robotics_traversability(graphql_url: str, trail_id: int) -> dict[str, Any] | None:
    payload = _post_graphql(
        graphql_url,
        """
        query RoboticsSmoke($trailId: Int!) {
          roboticsTraversability(trailId: $trailId) {
            trailId
            name
            geometryQuality
            vertexCount
            riskScore
            effortScore
            segmentCosts
            elevationProfile
            costModel
            rosCompatibleRoute
          }
        }
        """,
        {"trailId": trail_id},
    )
    if payload.get("errors"):
        raise RuntimeError(f"roboticsTraversability(trailId={trail_id}) errors: {payload['errors']}")
    rt = (payload.get("data") or {}).get("roboticsTraversability")
    return rt


def _find_candidate_trail_id(graphql_url: str, scan_max: int) -> tuple[int, dict[str, Any]]:
    for tid in range(1, scan_max + 1):
        rt = _robotics_traversability(graphql_url, tid)
        if not rt:
            continue
        segs = rt.get("segmentCosts") or []
        prof = rt.get("elevationProfile") or []
        if len(segs) >= 2 and len(prof) == len(segs) + 1:
            return tid, rt
    raise RuntimeError(
        f"No trail with segmentCosts aligned to elevationProfile found in ids 1..{scan_max}. "
        "Pass --trail-id explicitly (e.g. an imported_nps trail id from your seed)."
    )


def _validate_robotics(trail_id: int, rt: dict[str, Any]) -> None:
    segs = rt.get("segmentCosts") or []
    prof = rt.get("elevationProfile") or []
    if not segs:
        raise RuntimeError(f"trail {trail_id}: segmentCosts is empty")
    if len(prof) != len(segs) + 1:
        raise RuntimeError(
            f"trail {trail_id}: expected len(elevationProfile) == len(segmentCosts)+1, "
            f"got {len(prof)} vs {len(segs)}+1"
        )
    for s in segs:
        if "estimated_grade" not in s or "cost" not in s:
            raise RuntimeError(f"trail {trail_id}: segment missing estimated_grade or cost: {s!r}")

    cm = rt.get("costModel") or {}
    if cm.get("version") != "v2-segment-aware":
        raise RuntimeError(f"trail {trail_id}: unexpected costModel.version: {cm.get('version')}")
    if "fallback_mode" not in cm:
        raise RuntimeError(f"trail {trail_id}: costModel missing fallback_mode")

    route = rt.get("rosCompatibleRoute") or {}
    hdr = route.get("header") or {}
    if hdr.get("frame_id") != "map":
        raise RuntimeError(f"trail {trail_id}: ros header.frame_id != map")
    if hdr.get("coordinate_system") != "WGS84":
        raise RuntimeError(f"trail {trail_id}: ros header missing WGS84")
    if hdr.get("cost_model_version") != "v2-segment-aware":
        raise RuntimeError(f"trail {trail_id}: ros header.cost_model_version mismatch")

    poses = route.get("poses") or []
    costs = route.get("costs") or []
    if not poses:
        raise RuntimeError(f"trail {trail_id}: ros poses empty")
    if len(costs) != len(poses):
        raise RuntimeError(
            f"trail {trail_id}: len(costs) != len(poses): {len(costs)} vs {len(poses)}"
        )
    if len(costs) > 1 and len(set(costs)) == 1:
        raise RuntimeError(f"trail {trail_id}: ros costs are all equal (expected varying segment costs)")


def run(base_url: str, trail_id: int | None, scan_max: int) -> None:
    graphql_url = f"{base_url.rstrip('/')}/graphql"
    if trail_id is not None:
        rt = _robotics_traversability(graphql_url, trail_id)
        if not rt:
            raise RuntimeError(f"roboticsTraversability returned null for trailId={trail_id}")
        used_id = trail_id
    else:
        used_id, rt = _find_candidate_trail_id(graphql_url, scan_max)

    _validate_robotics(used_id, rt)
    name = rt.get("name", "?")
    vcount = rt.get("vertexCount")
    gq = rt.get("geometryQuality")
    print(f"PASS robotics segment smoke (trailId={used_id} name={name!r} vertexCount={vcount} geometryQuality={gq!r})")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke check segment-aware roboticsTraversability (segmentCosts, elevationProfile, ros costs)."
    )
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument(
        "--trail-id",
        type=int,
        default=None,
        help="Specific trail id (e.g. imported NPS row). If omitted, scans ids 1..scan-max.",
    )
    parser.add_argument(
        "--scan-max",
        type=int,
        default=400,
        help="Max trail id to scan when --trail-id is omitted (default 400).",
    )
    args = parser.parse_args()

    try:
        run(args.base_url, args.trail_id, args.scan_max)
        print("Robotics segment smoke passed.")
        return 0
    except (urllib.error.URLError, TimeoutError) as error:
        print(f"Robotics segment smoke failed (network): {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Robotics segment smoke failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
