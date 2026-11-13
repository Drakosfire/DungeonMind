"""Store native source withdrawals independently of immutable admissions."""

from alembic import op

revision = "0021_native_source_withdrawal"
down_revision = "0020_native_pdf_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE dungeonmind.knowledge_native_source_withdrawals (
            space_id text NOT NULL,
            source_artifact_id text NOT NULL,
            source_revision_id text NOT NULL,
            source_authority_epoch bigint NOT NULL CHECK (source_authority_epoch > 0),
            PRIMARY KEY (space_id, source_artifact_id, source_revision_id),
            UNIQUE (source_authority_epoch)
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE dungeonmind.knowledge_native_source_withdrawals")
