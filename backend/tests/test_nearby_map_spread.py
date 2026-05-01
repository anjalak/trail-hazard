from app.graphql.schema import map_trail


def test_map_trail_keeps_exact_coordinates() -> None:
    row = {
        "id": 42,
        "name": "Alpine Loop",
        "region": "Cascades",
        "location": None,
        "lat": 47.466,
        "lng": -121.661,
        "difficulty": "moderate",
        "length_km": 11.2,
        "elevation_gain_m": 480,
        "traversability_score": 74.5,
        "route_coordinates": [[-121.67, 47.46], [-121.65, 47.47]],
    }
    trail = map_trail(row)
    assert trail.lat == row["lat"]
    assert trail.lng == row["lng"]
