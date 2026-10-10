"""Prepared GM source review and append-only native span attestation."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0016_operator_source_attestation"
down_revision: str | None = "0015_source_admission"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None

SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.knowledge_operator_source_preparations (
            space_id text NOT NULL,
            operation_id text NOT NULL,
            preparation_sha256 text NOT NULL,
            expires_at timestamptz NOT NULL,
            payload jsonb NOT NULL,
            record_fingerprint text NOT NULL,
            PRIMARY KEY (space_id, operation_id),
            FOREIGN KEY (space_id) REFERENCES {SCHEMA}.knowledge_spaces (space_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.knowledge_operator_source_artifacts (
            space_id text NOT NULL,
            source_artifact_id text NOT NULL,
            source_revision_id text NOT NULL,
            legacy_world_id text NOT NULL,
            body_sha256 text NOT NULL,
            body_bytes bytea NOT NULL,
            policy jsonb NOT NULL,
            source_revision jsonb NOT NULL,
            policy_sha256 text NOT NULL,
            source_authority_epoch bigint NOT NULL,
            record_fingerprint text NOT NULL,
            PRIMARY KEY (space_id, source_artifact_id),
            UNIQUE (source_artifact_id),
            UNIQUE (source_revision_id),
            UNIQUE (space_id, source_revision_id),
            FOREIGN KEY (space_id) REFERENCES {SCHEMA}.knowledge_spaces (space_id),
            FOREIGN KEY (legacy_world_id, source_artifact_id)
                REFERENCES {SCHEMA}.source_artifacts (world_id, source_artifact_id),
            FOREIGN KEY (source_revision_id, source_artifact_id)
                REFERENCES {SCHEMA}.source_revisions (source_revision_id, source_artifact_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.knowledge_operator_source_attestations (
            space_id text NOT NULL,
            operation_id text NOT NULL,
            source_artifact_id text NOT NULL,
            source_span_ref_id text NOT NULL,
            evidence_ref_id text NOT NULL,
            source_authority_epoch bigint NOT NULL,
            proof jsonb NOT NULL,
            receipt jsonb NOT NULL,
            record_fingerprint text NOT NULL,
            PRIMARY KEY (space_id, operation_id),
            UNIQUE (source_span_ref_id),
            UNIQUE (evidence_ref_id),
            UNIQUE (space_id, source_span_ref_id),
            UNIQUE (space_id, evidence_ref_id),
            FOREIGN KEY (space_id, operation_id)
                REFERENCES {SCHEMA}.knowledge_operator_source_preparations
                    (space_id, operation_id),
            FOREIGN KEY (space_id, source_artifact_id)
                REFERENCES {SCHEMA}.knowledge_operator_source_artifacts
                    (space_id, source_artifact_id)
        )
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM {SCHEMA}.knowledge_operator_source_preparations)
               OR EXISTS (SELECT 1 FROM {SCHEMA}.knowledge_operator_source_artifacts)
               OR EXISTS (SELECT 1 FROM {SCHEMA}.knowledge_operator_source_attestations)
            THEN
                RAISE EXCEPTION 'cannot downgrade populated operator source authority';
            END IF;
        END $$
        """
    )
    op.execute(f"DROP TABLE {SCHEMA}.knowledge_operator_source_attestations")
    op.execute(f"DROP TABLE {SCHEMA}.knowledge_operator_source_artifacts")
    op.execute(f"DROP TABLE {SCHEMA}.knowledge_operator_source_preparations")
