"""Durable V5.4 prospective publication result mappings."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010_vnext_prospective_publication_results"
down_revision: str | None = "0009_vnext_publication_receipts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {SCHEMA}.knowledge_prospective_publication_results (
            schema_version text NOT NULL,
            space_id text NOT NULL,
            publication_id text NOT NULL,
            prospective_request_sha256 text NOT NULL,
            published_revision_id text NOT NULL,
            result_bindings jsonb NOT NULL,
            status text NOT NULL,
            record_fingerprint text NOT NULL,
            PRIMARY KEY (space_id, publication_id),
            CHECK (status = 'published'),
            FOREIGN KEY (space_id, publication_id)
                REFERENCES {SCHEMA}.knowledge_publication_receipts
                    (space_id, publication_id),
            FOREIGN KEY (space_id, published_revision_id)
                REFERENCES {SCHEMA}.knowledge_revisions
                    (space_id, revision_id)
        )
    """)


def downgrade() -> None:
    op.execute(
        f"DROP TABLE IF EXISTS {SCHEMA}.knowledge_prospective_publication_results"
    )
