"""Atomic native text-source/evidence admission.

Revision ID: 0011_vnext_native_source_admission
Revises: 0010_vnext_prospective_results
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011_native_source_v1"
down_revision: str | None = "0010_vnext_prospective_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
SCHEMA = "dungeonmind"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE {SCHEMA}.knowledge_native_source_authority (
            singleton_id smallint PRIMARY KEY CHECK (singleton_id = 1),
            epoch bigint NOT NULL CHECK (epoch >= 0)
        )
    """)
    op.execute(f"""
        INSERT INTO {SCHEMA}.knowledge_native_source_authority(singleton_id, epoch)
        VALUES (1, 0)
    """)
    op.execute(f"""
        CREATE TABLE {SCHEMA}.knowledge_native_source_admissions (
            space_id text NOT NULL,
            admission_id text NOT NULL,
            schema_version text NOT NULL,
            command_sha256 text NOT NULL,
            source_authority_epoch bigint NOT NULL CHECK (source_authority_epoch > 0),
            source_artifact_id text NOT NULL UNIQUE,
            source_revision_id text NOT NULL UNIQUE,
            published_revision_id text NOT NULL,
            source_artifact jsonb NOT NULL,
            source_revision jsonb NOT NULL,
            origin jsonb NULL,
            body_bytes bytea NOT NULL,
            span_proofs jsonb NOT NULL,
            receipt_payload jsonb NOT NULL,
            record_fingerprint text NOT NULL,
            PRIMARY KEY (space_id, admission_id),
            FOREIGN KEY (space_id, admission_id)
                REFERENCES {SCHEMA}.knowledge_publication_receipts(space_id, publication_id),
            FOREIGN KEY (space_id, published_revision_id)
                REFERENCES {SCHEMA}.knowledge_revisions(space_id, revision_id),
            CHECK (schema_version = 'dm_native_source_admission_receipt_v1')
        )
    """)
    op.execute(f"""
        CREATE TABLE {SCHEMA}.knowledge_native_source_spans (
            span_id text PRIMARY KEY,
            evidence_ref_id text NOT NULL UNIQUE,
            space_id text NOT NULL,
            admission_id text NOT NULL,
            proof jsonb NOT NULL,
            FOREIGN KEY (space_id, admission_id)
                REFERENCES {SCHEMA}.knowledge_native_source_admissions(space_id, admission_id)
        )
    """)
    op.execute(f"""
        CREATE INDEX knowledge_native_source_admissions_epoch_idx
        ON {SCHEMA}.knowledge_native_source_admissions(space_id, source_authority_epoch)
    """)


def downgrade() -> None:
    op.execute(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM {SCHEMA}.knowledge_native_source_admissions)
               OR EXISTS (SELECT 1 FROM {SCHEMA}.knowledge_native_source_spans) THEN
                RAISE EXCEPTION 'cannot downgrade populated native source admission authority';
            END IF;
        END $$
    """)
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.knowledge_native_source_spans")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.knowledge_native_source_admissions")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.knowledge_native_source_authority")
