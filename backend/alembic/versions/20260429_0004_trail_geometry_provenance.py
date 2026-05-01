"""Trail geometry provenance metadata.

Revision ID: 20260429_0004
Revises: 20260428_0003
Create Date: 2026-04-29
"""
from __future__ import annotations

from alembic import op

revision = "20260429_0004"
down_revision = "20260428_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE trails
          ADD COLUMN IF NOT EXISTS geometry_quality TEXT NOT NULL DEFAULT 'synthetic',
          ADD COLUMN IF NOT EXISTS geometry_source TEXT NOT NULL DEFAULT 'seed.sql',
          ADD COLUMN IF NOT EXISTS geometry_source_url TEXT;

        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'trails_geometry_quality_check'
          ) THEN
            ALTER TABLE trails
              ADD CONSTRAINT trails_geometry_quality_check
              CHECK (geometry_quality IN ('synthetic', 'curated', 'imported_usgs', 'imported_nps', 'imported_osm', 'unknown'));
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE trails DROP CONSTRAINT IF EXISTS trails_geometry_quality_check;
        ALTER TABLE trails
          DROP COLUMN IF EXISTS geometry_source_url,
          DROP COLUMN IF EXISTS geometry_source,
          DROP COLUMN IF EXISTS geometry_quality;
        """
    )
