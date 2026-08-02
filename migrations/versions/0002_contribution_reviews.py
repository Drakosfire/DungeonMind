"""Add atomic finalized contribution-review bundles.

Revision ID: 0002_contribution_reviews
Revises: 0001_postgres_substrate
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_contribution_reviews"
down_revision: str | None = "0001_postgres_substrate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.contribution_reviews (
            world_id text NOT NULL,
            review_id text NOT NULL,
            operation_id text NOT NULL,
            source_plan_id text NOT NULL,
            candidate_contribution_id text NOT NULL,
            reviewed_contribution_id text NOT NULL,
            expected_parent_revision_id text NOT NULL,
            reviewer_id text NOT NULL,
            reviewed_at timestamptz NOT NULL,
            status text NOT NULL CHECK (status = 'finalized'),
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL,
            PRIMARY KEY (world_id, review_id),
            UNIQUE (world_id, operation_id),
            UNIQUE (world_id, source_plan_id),
            FOREIGN KEY (world_id, candidate_contribution_id)
                REFERENCES {SCHEMA}.graph_contributions (world_id, contribution_id),
            FOREIGN KEY (world_id, reviewed_contribution_id)
                REFERENCES {SCHEMA}.graph_contributions (world_id, contribution_id),
            FOREIGN KEY (world_id, expected_parent_revision_id)
                REFERENCES {SCHEMA}.graph_revisions (world_id, revision_id)
        )
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.contribution_reviews")
