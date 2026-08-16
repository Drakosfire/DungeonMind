"""Add terminal existing-world adoption identities.

Revision ID: 0006_existing_world_adoptions
Revises: 0005_source_artifact_v2_nullable_created_at
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_existing_world_adoptions"
down_revision: str | None = "0005_source_created_at_null"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.existing_world_adoptions (
            world_id text NOT NULL,
            adoption_id text NOT NULL,
            bundle_sha256 text NOT NULL,
            published_revision_id text NOT NULL,
            graph_schema text NOT NULL,
            graph_payload_sha256 text NOT NULL,
            adopted_at timestamptz NOT NULL,
            source_artifact_count integer NOT NULL CHECK (source_artifact_count >= 0),
            source_revision_count integer NOT NULL CHECK (source_revision_count >= 0),
            contribution_count integer NOT NULL CHECK (contribution_count >= 0),
            identity_decision_count integer NOT NULL CHECK (identity_decision_count >= 0),
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL,
            PRIMARY KEY (world_id),
            UNIQUE (adoption_id),
            UNIQUE (world_id, published_revision_id),
            FOREIGN KEY (world_id)
                REFERENCES {SCHEMA}.worlds (world_id),
            FOREIGN KEY (world_id, published_revision_id)
                REFERENCES {SCHEMA}.graph_revisions (world_id, revision_id)
        )
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.existing_world_adoptions")
