"""Native vNext knowledge authority tables.

Revision ID: 0008_vnext_knowledge_authority
Revises: 0007_reviewed_world_init
Create Date: 2026-09-21
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_vnext_knowledge_authority"
down_revision: str | None = "0007_reviewed_world_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.knowledge_spaces (
            space_id text PRIMARY KEY,
            created_at timestamptz NOT NULL
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.knowledge_revisions (
            space_id text NOT NULL,
            revision_id text NOT NULL,
            parent_revision_id text NULL,
            created_at timestamptz NOT NULL,
            graph_schema text NOT NULL,
            graph_payload_sha256 text NOT NULL,
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            revision_payload jsonb NOT NULL,
            graph_payload jsonb NOT NULL,
            PRIMARY KEY (space_id, revision_id),
            FOREIGN KEY (space_id)
                REFERENCES {SCHEMA}.knowledge_spaces (space_id),
            FOREIGN KEY (space_id, parent_revision_id)
                REFERENCES {SCHEMA}.knowledge_revisions (space_id, revision_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.knowledge_heads (
            space_id text PRIMARY KEY,
            head_revision_id text NOT NULL,
            updated_at timestamptz NOT NULL,
            schema_version text NOT NULL,
            FOREIGN KEY (space_id)
                REFERENCES {SCHEMA}.knowledge_spaces (space_id),
            FOREIGN KEY (space_id, head_revision_id)
                REFERENCES {SCHEMA}.knowledge_revisions (space_id, revision_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.knowledge_head_events (
            event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            space_id text NOT NULL,
            event_kind text NOT NULL,
            previous_revision_id text NULL,
            target_revision_id text NOT NULL,
            occurred_at timestamptz NOT NULL,
            CONSTRAINT knowledge_head_events_kind
                CHECK (event_kind IN ('publish', 'rollback')),
            FOREIGN KEY (space_id)
                REFERENCES {SCHEMA}.knowledge_spaces (space_id),
            FOREIGN KEY (space_id, target_revision_id)
                REFERENCES {SCHEMA}.knowledge_revisions (space_id, revision_id)
        )
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.knowledge_head_events")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.knowledge_heads")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.knowledge_revisions")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.knowledge_spaces")
