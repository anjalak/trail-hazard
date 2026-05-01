"""Baseline schema matching app/models/schema.sql.

Revision ID: 20260427_0001
Revises:
Create Date: 2026-04-27 01:00:00.000000
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260427_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS postgis;

        CREATE TABLE IF NOT EXISTS trail_locations (
          id SERIAL PRIMARY KEY,
          state_code TEXT NOT NULL,
          city TEXT,
          park_name TEXT,
          park_type TEXT CHECK (park_type IN ('national_park', 'state_park', 'national_forest', 'state_forest', 'other')),
          county TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE (state_code, city, park_name, park_type)
        );

        CREATE INDEX IF NOT EXISTS idx_trail_locations_state_code ON trail_locations (state_code);
        CREATE INDEX IF NOT EXISTS idx_trail_locations_city_lower ON trail_locations ((LOWER(city)));
        CREATE INDEX IF NOT EXISTS idx_trail_locations_park_name_lower ON trail_locations ((LOWER(park_name)));

        CREATE TABLE IF NOT EXISTS trails (
          id SERIAL PRIMARY KEY,
          name TEXT NOT NULL,
          region TEXT NOT NULL,
          location_id INT REFERENCES trail_locations(id) ON DELETE SET NULL,
          difficulty TEXT NOT NULL,
          length_km NUMERIC(6,2) NOT NULL,
          elevation_gain_m INT NOT NULL,
          geom GEOMETRY(LineString, 4326),
          source_url TEXT,
          traversability_score NUMERIC(4,3) DEFAULT 0.0,
          last_scraped_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_trails_geom ON trails USING GIST (geom);
        CREATE INDEX IF NOT EXISTS idx_trails_name_lower ON trails ((LOWER(name)));

        CREATE TABLE IF NOT EXISTS hazards (
          id SERIAL PRIMARY KEY,
          trail_id INT NOT NULL REFERENCES trails(id) ON DELETE CASCADE,
          type TEXT NOT NULL,
          severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
          location GEOMETRY(Point, 4326),
          source TEXT NOT NULL CHECK (source IN ('user', 'scraped', 'cv_pipeline')),
          confidence NUMERIC(3,2) NOT NULL DEFAULT 0.75,
          reported_at TIMESTAMPTZ NOT NULL,
          resolved_at TIMESTAMPTZ,
          raw_text TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_hazards_trail_id ON hazards (trail_id);
        CREATE INDEX IF NOT EXISTS idx_hazards_active ON hazards (trail_id, resolved_at, reported_at DESC);
        CREATE INDEX IF NOT EXISTS idx_hazards_location ON hazards USING GIST (location);

        CREATE TABLE IF NOT EXISTS user_reports (
          id SERIAL PRIMARY KEY,
          trail_id INT NOT NULL REFERENCES trails(id) ON DELETE CASCADE,
          location GEOMETRY(Point, 4326),
          photo_url TEXT,
          condition_tags TEXT[] NOT NULL DEFAULT '{}',
          notes TEXT,
          reporter_name TEXT,
          reported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          upvotes INT NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_user_reports_trail_id ON user_reports (trail_id, reported_at DESC);
        CREATE INDEX IF NOT EXISTS idx_user_reports_location ON user_reports USING GIST (location);

        CREATE TABLE IF NOT EXISTS seasonal_intel (
          id SERIAL PRIMARY KEY,
          trail_id INT NOT NULL REFERENCES trails(id) ON DELETE CASCADE,
          month INT NOT NULL CHECK (month BETWEEN 1 AND 12),
          wildlife_alerts JSONB NOT NULL DEFAULT '[]'::jsonb,
          plant_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
          gear_recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
          avg_temp_c NUMERIC(5,2),
          avg_snowpack_cm NUMERIC(6,2),
          source TEXT NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE (trail_id, month)
        );

        CREATE TABLE IF NOT EXISTS reviews (
          id SERIAL PRIMARY KEY,
          trail_id INT NOT NULL REFERENCES trails(id) ON DELETE CASCADE,
          source_platform TEXT NOT NULL,
          rating NUMERIC(3,2),
          text TEXT,
          sentiment_score NUMERIC(4,3),
          scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          author_handle TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_reviews_trail_id ON reviews (trail_id, scraped_at DESC);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS reviews;
        DROP TABLE IF EXISTS seasonal_intel;
        DROP TABLE IF EXISTS user_reports;
        DROP TABLE IF EXISTS hazards;
        DROP TABLE IF EXISTS trails;
        DROP TABLE IF EXISTS trail_locations;
        """
    )
