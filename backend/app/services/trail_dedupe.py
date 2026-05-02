"""Collapse duplicate trail rows from multi-segment imports (e.g. NPS OBJECTID per segment)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


def _normalized_trail_name(trail: Dict[str, Any]) -> str:
    raw = str(trail.get("name") or "").strip().lower()
    return re.sub(r"\s+", " ", raw)


def trail_logical_key(trail: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Segments share the same trails.region and location.state_code; do not use park_name here —
    GraphQL sometimes omits location when state_code is missing, which produced a different key
    than rows with a full location (e.g. 'north cascades national park' vs 'north cascades').
    """
    loc = trail.get("location") or {}
    state = str(loc.get("state_code") or "").strip().lower()
    region = str(trail.get("region") or "").strip().lower()
    return (state, region, _normalized_trail_name(trail))


def dedupe_trails_preserve_order(trails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep the first row per logical trail (preserves search relevance ordering)."""
    if len(trails) <= 1:
        return trails
    seen: set[Tuple[str, str, str]] = set()
    out: List[Dict[str, Any]] = []
    for t in trails:
        k = trail_logical_key(t)
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def dedupe_trails_for_list_api(
    trails: List[Dict[str, Any]],
    *,
    pivot_lat: Optional[float] = None,
    pivot_lng: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    One list entry per trail name per park. When a pivot is given, keep the segment
    whose pin is closest (Manhattan on lat/lng, matching the in-memory nearby heuristic).
    Otherwise keep the lowest trail id (canonical import order).
    """
    if len(trails) <= 1:
        return trails
    groups: dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for t in trails:
        groups.setdefault(trail_logical_key(t), []).append(t)
    out: List[Dict[str, Any]] = []
    use_pivot = pivot_lat is not None and pivot_lng is not None
    plat, plng = (pivot_lat, pivot_lng) if use_pivot else (0.0, 0.0)

    for items in groups.values():
        if use_pivot:

            def distance_key(tr: Dict[str, Any]) -> float:
                tlat, tlng = tr.get("lat"), tr.get("lng")
                if tlat is None or tlng is None:
                    return float("inf")
                return abs(float(tlat) - plat) + abs(float(tlng) - plng)

            out.append(min(items, key=distance_key))
        else:
            out.append(min(items, key=lambda tr: tr.get("id", 0)))
    return out
