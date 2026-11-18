"""Derived byte-exact native revision read artifacts."""

from alembic import op

revision = "0022_native_read_artifacts"
down_revision = "0021_native_source_withdrawal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE dungeonmind.knowledge_native_read_artifacts (
            space_id text NOT NULL,
            revision_id text NOT NULL,
            codec_version text NOT NULL,
            parsed_format text NOT NULL,
            envelope_sha256 text NOT NULL CHECK (envelope_sha256 ~ '^[0-9a-f]{64}$'),
            graph_sha256 text NOT NULL CHECK (graph_sha256 ~ '^[0-9a-f]{64}$'),
            artifact_sha256 text NOT NULL CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
            artifact_length bigint NOT NULL CHECK (artifact_length > 0),
            artifact_bytes bytea NOT NULL,
            PRIMARY KEY (space_id, revision_id, codec_version, parsed_format),
            FOREIGN KEY (space_id, revision_id)
                REFERENCES dungeonmind.knowledge_revisions (space_id, revision_id),
            CHECK (octet_length(artifact_bytes) = artifact_length)
        )
    """)


def downgrade() -> None:
    # Derived disposable data only. Immutable revision authority stays intact.
    op.execute("DROP TABLE dungeonmind.knowledge_native_read_artifacts")
