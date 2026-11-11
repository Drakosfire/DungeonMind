"""Retain immutable native PDF sources before Graph publication."""

from alembic import op

revision = "0019_native_pdf_sources"
down_revision = "0018_native_source_extensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE dungeonmind.knowledge_native_pdf_sources (
            space_id text NOT NULL
                REFERENCES dungeonmind.knowledge_spaces (space_id),
            admission_id text NOT NULL,
            source_revision_id text NOT NULL UNIQUE,
            source_artifact jsonb NOT NULL,
            source_revision jsonb NOT NULL,
            page_count integer NOT NULL CHECK (page_count > 0),
            body_bytes bytea NOT NULL CHECK (octet_length(body_bytes) > 0),
            PRIMARY KEY (space_id, admission_id)
        )
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            LOCK TABLE dungeonmind.knowledge_native_pdf_sources IN ACCESS EXCLUSIVE MODE;
            IF EXISTS (SELECT 1 FROM dungeonmind.knowledge_native_pdf_sources) THEN
                RAISE EXCEPTION 'cannot downgrade populated native PDF sources';
            END IF;
        END
        $$;
    """)
    op.execute("DROP TABLE dungeonmind.knowledge_native_pdf_sources")
