"""Add ingestion_task_failures table for Celery dead-letter.

Revision ID: 20260427_0002
Revises: 20260427_0001
Create Date: 2026-04-27
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260427_0002"
down_revision = "20260427_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ingestion_task_failures (
          id BIGSERIAL PRIMARY KEY,
          task_name TEXT NOT NULL,
          task_id TEXT,
          task_args JSONB NOT NULL DEFAULT '[]',
          task_kwargs JSONB NOT NULL DEFAULT '{}',
          exc_type TEXT NOT NULL,
          exc_message TEXT,
          exc_repr TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_ingestion_task_failures_created_at
          ON ingestion_task_failures (created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_ingestion_task_failures_task_name
          ON ingestion_task_failures (task_name);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ingestion_task_failures;")
