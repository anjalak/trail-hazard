"""Regression: nested GeoJSON coordinate arrays must flatten to [lng,lat] pairs, not mixed vertex dimensions."""

from app.graphql.schema import _sanitize_route_coordinates


def test_flat_linestring_keeps_pairs() -> None:
    raw = [[-121.5, 46.9], [-121.51, 46.91]]
    out = _sanitize_route_coordinates(raw)
    assert out == [[-121.5, 46.9], [-121.51, 46.91]]


def test_multiline_nested_does_not_take_sublist_as_lng() -> None:
    """Old bug: iterating top-level segments used float([lng,lat]) or wrong pair construction."""
    nested = [
        [[-121.0, 46.0], [-121.02, 46.02]],
        [[-122.0, 47.0], [-122.03, 47.04]],
    ]
    out = _sanitize_route_coordinates(nested)
    assert out and all(isinstance(pair, list) and len(pair) == 2 for pair in out)
    assert out[0] == [-121.0, 46.0]
    assert len(out) >= 3
