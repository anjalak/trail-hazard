"""Trail data-quality and validation columns (align with app/models/schema.sql).

Revision ID: 20260430_0005
Revises: 20260429_0004
Create Date: 2026-04-30
"""
from __future__ import annotations

from alembic import op

revision = "20260430_0005"
down_revision = "20260429_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE trails
          ADD COLUMN IF NOT EXISTS data_quality_status TEXT NOT NULL DEFAULT 'demo_synthetic',
          ADD COLUMN IF NOT EXISTS validation_source TEXT,
          ADD COLUMN IF NOT EXISTS validated_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS validation_notes TEXT;

        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'trails_data_quality_status_check'
          ) THEN
            ALTER TABLE trails
              ADD CONSTRAINT trails_data_quality_status_check
              CHECK (data_quality_status IN ('verified', 'demo_synthetic'));
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE trails DROP CONSTRAINT IF EXISTS trails_data_quality_status_check;
        ALTER TABLE trails
          DROP COLUMN IF EXISTS validation_notes,
          DROP COLUMN IF EXISTS validated_at,
          DROP COLUMN IF EXISTS validation_source,
          DROP COLUMN IF EXISTS data_quality_status;
        """
    )
