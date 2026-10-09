"""Atomic legacy source artifact/revision admission receipts."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015_legacy_source_admission_receipts"
down_revision: str | None = "0014_adopted_withdrawal_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None

SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE {SCHEMA}.source_artifacts
        ADD CONSTRAINT source_artifacts_world_binding_uq
        UNIQUE (world_id, source_artifact_id)
        """
    )
    op.execute(
        f"""
        ALTER TABLE {SCHEMA}.source_revisions
        ADD CONSTRAINT source_revisions_artifact_binding_uq
        UNIQUE (source_revision_id, source_artifact_id)
        """
    )
    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.source_admission_receipts (
            admission_id text PRIMARY KEY,
            world_id text NOT NULL,
            expected_head_revision_id text NOT NULL,
            source_artifact_id text NOT NULL,
            source_revision_id text NOT NULL,
            content_sha256 text NOT NULL,
            command_sha256 text NOT NULL,
            admitted_at timestamptz NOT NULL,
            schema_version text NOT NULL,
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL,
            CONSTRAINT source_admission_receipt_schema
                CHECK (schema_version = 'dm_source_admission_receipt_v1'),
            FOREIGN KEY (world_id)
                REFERENCES {SCHEMA}.worlds (world_id),
            FOREIGN KEY (world_id, expected_head_revision_id)
                REFERENCES {SCHEMA}.graph_revisions (world_id, revision_id),
            FOREIGN KEY (world_id, source_artifact_id)
                REFERENCES {SCHEMA}.source_artifacts (world_id, source_artifact_id),
            FOREIGN KEY (source_revision_id, source_artifact_id)
                REFERENCES {SCHEMA}.source_revisions
                    (source_revision_id, source_artifact_id)
        )
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM {SCHEMA}.source_admission_receipts) THEN
                RAISE EXCEPTION 'cannot downgrade populated source admission authority';
            END IF;
        END $$
        """
    )
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.source_admission_receipts")
    op.execute(
        f"ALTER TABLE {SCHEMA}.source_revisions "
        "DROP CONSTRAINT IF EXISTS source_revisions_artifact_binding_uq"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA}.source_artifacts "
        "DROP CONSTRAINT IF EXISTS source_artifacts_world_binding_uq"
    )
