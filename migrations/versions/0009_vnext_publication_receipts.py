"""Durable vNext publication replay receipts."""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009_vnext_publication_receipts"
down_revision: str | None = "0008_vnext_knowledge_authority"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
SCHEMA = "dungeonmind"

def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {SCHEMA}.knowledge_publication_receipts (
            schema_version text NOT NULL,
            space_id text NOT NULL,
            publication_id text NOT NULL,
            command_sha256 text NOT NULL,
            expected_parent_revision_id text NULL,
            published_revision_id text NOT NULL,
            graph_payload_sha256 text NOT NULL,
            status text NOT NULL,
            record_fingerprint text NOT NULL,
            PRIMARY KEY (space_id, publication_id),
            CHECK (status = 'published'),
            FOREIGN KEY (space_id, published_revision_id)
                REFERENCES {SCHEMA}.knowledge_revisions (space_id, revision_id)
        )
    """)

def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.knowledge_publication_receipts")
