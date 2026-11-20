"""Atomic source-fenced governed publications, separate from extension V1."""

from alembic import op

revision = "0023_native_source_publications"
down_revision = "0022_native_read_artifacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE dungeonmind.knowledge_native_source_publications (
        space_id text NOT NULL,
        publication_id text NOT NULL,
        original_admission_id text NOT NULL,
        source_artifact_id text NOT NULL,
        source_revision_id text NOT NULL,
        mode text NOT NULL CHECK(mode IN ('new_intervals','existing_support')),
        source_authority_epoch_before bigint NOT NULL CHECK(source_authority_epoch_before>0),
        source_authority_epoch_after bigint NOT NULL,
        receipt_payload jsonb NOT NULL,
        record_fingerprint text NOT NULL,
        PRIMARY KEY(space_id,publication_id),
        FOREIGN KEY(space_id,original_admission_id)
            REFERENCES dungeonmind.knowledge_native_source_admissions(space_id,admission_id),
        FOREIGN KEY(space_id,publication_id)
            REFERENCES dungeonmind.knowledge_publication_receipts(space_id,publication_id),
        CHECK(source_authority_epoch_after=source_authority_epoch_before
              +CASE WHEN mode='new_intervals' THEN 1 ELSE 0 END)
    )""")
    op.execute("""CREATE INDEX native_source_publications_lookup_idx
        ON dungeonmind.knowledge_native_source_publications
        (space_id,source_revision_id,source_authority_epoch_after)""")
    op.execute("""CREATE INDEX native_source_publications_proofs_idx
        ON dungeonmind.knowledge_native_source_publications
        USING gin ((receipt_payload->'proofs') jsonb_path_ops)""")
    op.execute("""CREATE INDEX native_source_extensions_proofs_idx
        ON dungeonmind.knowledge_native_source_extensions
        USING gin ((receipt_payload->'proofs') jsonb_path_ops)""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM dungeonmind.knowledge_native_source_publications) THEN
            RAISE EXCEPTION 'cannot downgrade populated native source publications';
        END IF;
    END $$""")
    op.execute("DROP INDEX dungeonmind.native_source_extensions_proofs_idx")
    op.execute("DROP TABLE dungeonmind.knowledge_native_source_publications")
