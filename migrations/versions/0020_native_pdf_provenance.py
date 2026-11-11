"""Pin retained PDFs to DungeonMind's source authority epoch."""

from alembic import op

revision = "0020_native_pdf_provenance"
down_revision = "0019_native_pdf_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE dungeonmind.knowledge_native_pdf_sources
            ADD COLUMN source_authority_epoch bigint;
        WITH epoch AS (
            UPDATE dungeonmind.knowledge_native_source_authority
            SET epoch = epoch + 1 WHERE singleton_id = 1
            RETURNING epoch
        )
        UPDATE dungeonmind.knowledge_native_pdf_sources
            SET source_authority_epoch = epoch.epoch FROM epoch;
        ALTER TABLE dungeonmind.knowledge_native_pdf_sources
            ALTER COLUMN source_authority_epoch SET NOT NULL;
        CREATE INDEX knowledge_native_pdf_sources_artifact_idx
            ON dungeonmind.knowledge_native_pdf_sources
            (space_id, (source_artifact ->> 'source_artifact_id'));
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX dungeonmind.knowledge_native_pdf_sources_artifact_idx;
        ALTER TABLE dungeonmind.knowledge_native_pdf_sources
            DROP COLUMN source_authority_epoch;
    """)
