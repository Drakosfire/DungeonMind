"""Additional evidence without rewriting immutable native source admissions."""

from alembic import op

revision = "0018_native_source_extensions"
down_revision = "0017_publication_admission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE dungeonmind.knowledge_native_source_extensions (
        space_id text NOT NULL,
        extension_id text NOT NULL,
        original_admission_id text NOT NULL,
        source_artifact_id text NOT NULL,
        source_revision_id text NOT NULL,
        source_authority_epoch bigint NOT NULL CHECK (source_authority_epoch>0),
        receipt_payload jsonb NOT NULL,
        record_fingerprint text NOT NULL,
        PRIMARY KEY(space_id, extension_id),
        FOREIGN KEY(space_id, original_admission_id)
            REFERENCES dungeonmind.knowledge_native_source_admissions(space_id, admission_id),
        FOREIGN KEY(space_id, extension_id)
            REFERENCES dungeonmind.knowledge_publication_receipts(space_id, publication_id)
    )""")
    op.execute("""CREATE INDEX native_source_extensions_lookup_idx
        ON dungeonmind.knowledge_native_source_extensions
        (space_id,source_revision_id,source_authority_epoch)""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM dungeonmind.knowledge_native_source_extensions) THEN
            RAISE EXCEPTION 'cannot downgrade populated native source extensions';
        END IF;
    END $$""")
    op.execute("DROP TABLE dungeonmind.knowledge_native_source_extensions")
