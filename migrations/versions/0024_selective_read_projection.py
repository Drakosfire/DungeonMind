"""Publish immutable exact-revision derived read projections."""

from alembic import op

revision = "0024_selective_read_projection"
down_revision = "0023_native_source_publications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE dungeonmind.selective_read_activations (
            space_id text NOT NULL,
            revision_id text NOT NULL,
            proof_sha256 text NOT NULL CHECK(proof_sha256 ~ '^[0-9a-f]{64}$'),
            PRIMARY KEY (space_id, revision_id),
            FOREIGN KEY (space_id, revision_id)
                REFERENCES dungeonmind.knowledge_revisions(space_id, revision_id)
        )
    """)
    op.execute("""
        CREATE TABLE dungeonmind.selective_read_proofs (
            space_id text NOT NULL,
            revision_id text NOT NULL,
            content bytea NOT NULL,
            PRIMARY KEY (space_id, revision_id),
            FOREIGN KEY (space_id, revision_id)
                REFERENCES dungeonmind.selective_read_activations(space_id, revision_id)
        )
    """)
    for table in ("selective_read_records", "selective_read_buckets"):
        op.execute(f"""
            CREATE TABLE dungeonmind.{table} (
                space_id text NOT NULL,
                revision_id text NOT NULL,
                family text NOT NULL,
                key text NOT NULL,
                value jsonb NOT NULL,
                PRIMARY KEY (space_id, revision_id, family, key),
                FOREIGN KEY (space_id, revision_id)
                    REFERENCES dungeonmind.selective_read_activations(space_id, revision_id)
            )
        """)


def downgrade() -> None:
    for table in (
        "selective_read_buckets", "selective_read_records", "selective_read_proofs",
        "selective_read_activations",
    ):
        op.execute(f"DROP TABLE dungeonmind.{table}")
