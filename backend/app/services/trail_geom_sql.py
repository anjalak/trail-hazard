"""Shared PostGIS snippets for a representative map anchor from trails.geom."""

# Project centroid onto merged linework so the pin lies on the trail (never "between" disjoint parts).
# Fallbacks cover degenerate / collection geometries.
TRAIL_MAP_PIN_POINT = """(COALESCE(
  ST_ClosestPoint(
    ST_LineMerge(ST_MakeValid(t.geom::geometry))::geometry,
    ST_Centroid(ST_LineMerge(ST_MakeValid(t.geom::geometry))::geometry)::geometry
  ),
  ST_StartPoint(ST_MakeValid(t.geom::geometry)::geometry),
  ST_PointOnSurface(ST_MakeValid(t.geom::geometry)::geometry)
))"""
