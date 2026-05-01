"""B-tree indexes for trail search/nearby location filters and join key.

Revision ID: 20260428_0003
Revises: 20260427_0002
Create Date: 2026-04-28

Supports WHERE clauses in PostgresRepository.search_trails and nearby_trails:
- idx_trail_locations_state_code_lower: LOWER(tl.state_code) = LOWER(%(state_code)s)
- idx_trail_locations_park_type_lower: LOWER(tl.park_type) = LOWER(%(park_type)s)
  (city / park_name ILIKE-style filters already use idx_trail_locations_city_lower /
   idx_trail_locations_park_name_lower from baseline.)
- idx_trails_location_id: JOIN trail_locations tl ON tl.id = t.location_id

Nearby still uses ST_DWithin on computed trail center (geography); spatial side uses
existing idx_trails_geom (GiST on trails.geom). Further nearby CTE/tuning is deferred.

"""
from __future__ import annotations

from alembic import op

revision = "20260428_0003"
down_revision = "20260427_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_trail_locations_state_code_lower
          ON trail_locations ((LOWER(state_code)));
        CREATE INDEX IF NOT EXISTS idx_trail_locations_park_type_lower
          ON trail_locations ((LOWER(park_type)));
        CREATE INDEX IF NOT EXISTS idx_trails_location_id
          ON trails (location_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_trails_location_id;
        DROP INDEX IF EXISTS idx_trail_locations_park_type_lower;
        DROP INDEX IF EXISTS idx_trail_locations_state_code_lower;
        """
    )
