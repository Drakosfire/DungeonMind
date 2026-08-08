"""Allow nullable source_domain and visibility for v2 source artifacts.

Revision ID: 0004_source_artifact_v2_nullable
Revises: 0003_finalized_review_pubs
Create Date: 2026-08-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_source_artifact_v2_nullable"
down_revision: str | None = "0003_finalized_review_pubs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {SCHEMA}.source_artifacts "
        f"ALTER COLUMN source_domain DROP NOT NULL"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA}.source_artifacts "
        f"ALTER COLUMN visibility DROP NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE {SCHEMA}.source_artifacts "
        f"ALTER COLUMN visibility SET NOT NULL"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA}.source_artifacts "
        f"ALTER COLUMN source_domain SET NOT NULL"
    )
