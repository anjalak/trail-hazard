"""Unit tests for trail list deduplication (NPS multi-segment imports)."""

from __future__ import annotations

from app.services.trail_dedupe import (
    dedupe_trails_for_list_api,
    dedupe_trails_preserve_order,
    trail_logical_key,
)


def test_trail_logical_key_uses_state_region_name_not_park_label() -> None:
    """Avoid keys that split segments when park_name vs region strings differ."""
    a = {
        "name": "Sample Trail",
        "region": "North Cascades",
        "location": {
            "state_code": "WA",
            "park_name": "North Cascades National Park",
            "city": "Marblemount",
            "park_type": "national_park",
        },
    }
    b = {**a, "id": 999}
    assert trail_logical_key(a) == trail_logical_key(b)


def test_trail_logical_key_same_for_full_location_vs_region_only() -> None:
    with_park = {
        "name": "Sourdough Mountain Trail",
        "region": "North Cascades",
        "location": {
            "state_code": "WA",
            "park_name": "North Cascades National Park",
            "park_type": "national_park",
        },
    }
    without_park_name = {
        "name": "Sourdough Mountain Trail",
        "region": "North Cascades",
        "location": {"state_code": "WA"},
    }
    assert trail_logical_key(with_park) == trail_logical_key(without_park_name)


def test_dedupe_keeps_closest_segment_to_pivot() -> None:
    park = {
        "state_code": "WA",
        "city": "Marblemount",
        "park_name": "North Cascades National Park",
        "park_type": "national_park",
        "county": "Whatcom",
    }
    far = {
        "id": 10,
        "name": "Sourdough Mountain Trail",
        "region": "North Cascades",
        "location": park,
        "difficulty": "moderate",
        "length_km": 5.0,
        "elevation_gain_m": 0,
        "traversability_score": 0.7,
        "lat": 48.75,
        "lng": -121.2,
        "geometry_quality": "imported_nps",
    }
    near = {
        **far,
        "id": 11,
        "lat": 48.7428,
        "lng": -121.1028,
    }
    out = dedupe_trails_for_list_api([far, near], pivot_lat=48.7428, pivot_lng=-121.1028)
    assert len(out) == 1
    assert out[0]["id"] == 11


def test_dedupe_without_pivot_keeps_lowest_id() -> None:
    park = {
        "state_code": "WA",
        "park_name": "North Cascades National Park",
        "park_type": "national_park",
    }
    first = {
        "id": 5,
        "name": "Dup Trail",
        "region": "North Cascades",
        "location": park,
        "lat": 48.0,
        "lng": -121.0,
    }
    second = {**first, "id": 9}
    out = dedupe_trails_for_list_api([second, first])
    assert out == [first]


def test_dedupe_trails_preserve_order_keeps_first() -> None:
    loc = {"state_code": "WA", "park_name": "North Cascades National Park", "park_type": "national_park"}
    first = {
        "id": 61,
        "name": "Sourdough Mountain Trail",
        "region": "North Cascades",
        "location": loc,
    }
    second = {**first, "id": 73}
    out = dedupe_trails_preserve_order([first, second])
    assert [r["id"] for r in out] == [61]


def test_dedupe_different_parks_same_name() -> None:
    a = {
        "id": 1,
        "name": "River Trail",
        "region": "A",
        "location": {"state_code": "WA", "park_name": "Park A", "park_type": "national_park"},
        "lat": 47.0,
        "lng": -122.0,
    }
    b = {
        "id": 2,
        "name": "River Trail",
        "region": "B",
        "location": {"state_code": "WA", "park_name": "Park B", "park_type": "state_park"},
        "lat": 47.1,
        "lng": -122.1,
    }
    out = dedupe_trails_for_list_api([a, b])
    assert len(out) == 2
