"""Durable allocation identity for MIND-minted empty vNext spaces."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012_vnext_space_provisioning"
down_revision: str | None = "0011_native_source_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {SCHEMA}.knowledge_space_provisioning_receipts (
            schema_version text NOT NULL,
            allocation_id text PRIMARY KEY,
            request_sha256 text NOT NULL,
            space_id text NOT NULL UNIQUE,
            publication_id text NOT NULL,
            receipt_payload jsonb NOT NULL,
            record_fingerprint text NOT NULL,
            CHECK (schema_version = 'dm_knowledge_space_provisioning_receipt_v1'),
            FOREIGN KEY (space_id)
                REFERENCES {SCHEMA}.knowledge_spaces (space_id),
            FOREIGN KEY (space_id, publication_id)
                REFERENCES {SCHEMA}.knowledge_publication_receipts
                    (space_id, publication_id)
        )
    """)


def downgrade() -> None:
    op.execute(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM {SCHEMA}.knowledge_space_provisioning_receipts) THEN
                RAISE EXCEPTION 'cannot downgrade populated space provisioning authority';
            END IF;
        END $$
    """)
    op.execute(
        f"DROP TABLE IF EXISTS {SCHEMA}.knowledge_space_provisioning_receipts"
    )
