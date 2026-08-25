"""Add terminal reviewed first-world initialization identities.

Revision ID: 0007_reviewed_world_init
Revises: 0006_existing_world_adoptions
Create Date: 2026-08-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007_reviewed_world_init"
down_revision: str | None = "0006_existing_world_adoptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.reviewed_world_initializations (
            world_id text NOT NULL,
            initialization_id text NOT NULL,
            source_plan_id text NOT NULL,
            source_plan_sha256 text NOT NULL,
            command_sha256 text NOT NULL,
            reviewed_contribution_id text NOT NULL,
            reviewed_contribution_sha256 text NOT NULL,
            published_revision_id text NOT NULL,
            published_graph_schema text NOT NULL,
            published_graph_payload_sha256 text NOT NULL,
            initialized_at timestamptz NOT NULL,
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL,
            PRIMARY KEY (world_id),
            UNIQUE (initialization_id),
            UNIQUE (world_id, published_revision_id),
            FOREIGN KEY (world_id)
                REFERENCES {SCHEMA}.worlds (world_id),
            FOREIGN KEY (world_id, published_revision_id)
                REFERENCES {SCHEMA}.graph_revisions (world_id, revision_id)
        )
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.reviewed_world_initializations")
