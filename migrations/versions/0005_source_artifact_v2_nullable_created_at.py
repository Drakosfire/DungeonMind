"""Allow nullable source-artifact created_at for unknown producer timestamps.

Revision ID: 0005_source_created_at_null
Revises: 0004_source_artifact_v2_nullable
Create Date: 2026-08-08

``SourceArtifactV2.created_at`` is required-but-nullable. The relational column
must round-trip ``None`` without inventing a producer timestamp. World/campaign
registry rows still need a substrate ``created_at``; that value is chosen at
put time and is never written back into the artifact payload.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005_source_created_at_null"
down_revision: str | None = "0004_source_artifact_v2_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {SCHEMA}.source_artifacts "
        f"ALTER COLUMN created_at DROP NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE {SCHEMA}.source_artifacts "
        f"ALTER COLUMN created_at SET NOT NULL"
    )
