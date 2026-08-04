"""Add terminal finalized-review publication identities.

Revision ID: 0003_finalized_review_pubs
Revises: 0002_contribution_reviews
Create Date: 2026-08-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_finalized_review_pubs"
down_revision: str | None = "0002_contribution_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.finalized_review_publications (
            world_id text NOT NULL,
            review_id text NOT NULL,
            reviewed_contribution_id text NOT NULL,
            reviewed_contribution_sha256 text NOT NULL,
            review_intent_sha256 text NOT NULL,
            confirmation_id text NOT NULL,
            operation_id text NOT NULL,
            expected_parent_revision_id text NOT NULL,
            parent_graph_payload_sha256 text NOT NULL,
            published_revision_id text NOT NULL,
            graph_schema text NOT NULL,
            graph_payload_sha256 text NOT NULL,
            published_at timestamptz NOT NULL,
            status text NOT NULL CHECK (status = 'published'),
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL,
            PRIMARY KEY (world_id, operation_id),
            UNIQUE (world_id, review_id),
            UNIQUE (world_id, published_revision_id),
            FOREIGN KEY (world_id, review_id)
                REFERENCES {SCHEMA}.contribution_reviews (world_id, review_id),
            FOREIGN KEY (world_id, reviewed_contribution_id)
                REFERENCES {SCHEMA}.graph_contributions (world_id, contribution_id),
            FOREIGN KEY (world_id, expected_parent_revision_id)
                REFERENCES {SCHEMA}.graph_revisions (world_id, revision_id),
            FOREIGN KEY (world_id, published_revision_id)
                REFERENCES {SCHEMA}.graph_revisions (world_id, revision_id)
        )
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.finalized_review_publications")
