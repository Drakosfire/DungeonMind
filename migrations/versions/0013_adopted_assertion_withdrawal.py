"""Durable append-only receipts for adopted assertion withdrawal.

Revision ID: 0013_adopted_withdrawal_v1
Revises: 0012_vnext_space_provisioning
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013_adopted_withdrawal_v1"
down_revision: str | None = "0012_vnext_space_provisioning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {SCHEMA}.adopted_assertion_withdrawals (
            operation_id text PRIMARY KEY,
            world_id text NOT NULL,
            adoption_id text NOT NULL,
            request_sha256 text NOT NULL,
            adoption_receipt_fingerprint text NOT NULL,
            parent_revision_id text NOT NULL,
            parent_payload_sha256 text NOT NULL,
            published_revision_id text NOT NULL,
            relationship_id text NOT NULL,
            assertion_id text NOT NULL,
            subject_object_id text NOT NULL,
            predicate text NOT NULL,
            object_object_id text NOT NULL,
            evidence_ref_id text NOT NULL,
            source_artifact_id text NOT NULL,
            source_revision_id text NOT NULL,
            source_span_ref_id text NOT NULL,
            source_locator text NOT NULL,
            disposition text NOT NULL CHECK (
                disposition = 'unsupported_by_bound_source'
            ),
            actor text NOT NULL,
            completed_at timestamptz NOT NULL,
            schema_version text NOT NULL CHECK (
                schema_version = 'dm_adopted_assertion_withdrawal_receipt_v1'
            ),
            record_fingerprint text NOT NULL,
            payload jsonb NOT NULL,
            UNIQUE (world_id, operation_id),
            FOREIGN KEY (world_id) REFERENCES {SCHEMA}.worlds (world_id),
            FOREIGN KEY (adoption_id)
                REFERENCES {SCHEMA}.existing_world_adoptions (adoption_id),
            FOREIGN KEY (world_id, parent_revision_id)
                REFERENCES {SCHEMA}.graph_revisions (world_id, revision_id),
            FOREIGN KEY (world_id, published_revision_id)
                REFERENCES {SCHEMA}.graph_revisions (world_id, revision_id),
            FOREIGN KEY (source_artifact_id)
                REFERENCES {SCHEMA}.source_artifacts (source_artifact_id),
            FOREIGN KEY (source_revision_id)
                REFERENCES {SCHEMA}.source_revisions (source_revision_id)
        )
    """)
    op.execute(f"""
        CREATE FUNCTION {SCHEMA}.reject_adopted_assertion_withdrawal_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'adopted assertion withdrawal receipts are append-only';
        END;
        $$
    """)
    op.execute(f"""
        CREATE TRIGGER adopted_assertion_withdrawals_append_only
        BEFORE UPDATE OR DELETE ON {SCHEMA}.adopted_assertion_withdrawals
        FOR EACH ROW EXECUTE FUNCTION
            {SCHEMA}.reject_adopted_assertion_withdrawal_mutation()
    """)


def downgrade() -> None:
    op.execute(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM {SCHEMA}.adopted_assertion_withdrawals) THEN
                RAISE EXCEPTION 'cannot downgrade populated adopted assertion withdrawals';
            END IF;
        END $$
    """)
    op.execute(
        f"DROP TRIGGER IF EXISTS adopted_assertion_withdrawals_append_only "
        f"ON {SCHEMA}.adopted_assertion_withdrawals"
    )
    op.execute(
        f"DROP FUNCTION IF EXISTS {SCHEMA}.reject_adopted_assertion_withdrawal_mutation()"
    )
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.adopted_assertion_withdrawals")
