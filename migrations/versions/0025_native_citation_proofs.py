"""Add an atomic typed projection of immutable native citation proofs."""

from alembic import context, op
from psycopg.rows import dict_row

revision = "0025_native_citation_proofs"
down_revision = "0024_selective_read_projection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("native citation backfill requires a live database")
    # Serialize the verified backfill with native source publications.
    op.execute("""
        SELECT epoch FROM dungeonmind.knowledge_native_source_authority
        WHERE singleton_id = 1 FOR UPDATE
    """)
    op.execute("""
        CREATE TABLE dungeonmind.native_citation_manifests (
            space_id text NOT NULL,
            receipt_id text NOT NULL,
            kind text NOT NULL CHECK (kind IN ('admission', 'extension', 'publication')),
            admission_id text NOT NULL,
            source_artifact_id text NOT NULL,
            source_revision_id text NOT NULL,
            authority_epoch bigint NOT NULL CHECK (authority_epoch > 0),
            receipt_fingerprint text NOT NULL CHECK (receipt_fingerprint ~ '^[0-9a-f]{64}$'),
            publication_fingerprint text NOT NULL
                CHECK (publication_fingerprint ~ '^[0-9a-f]{64}$'),
            span_ids text[] NOT NULL,
            span_fingerprints text[] NOT NULL,
            intact boolean NOT NULL DEFAULT true,
            PRIMARY KEY (space_id, receipt_id),
            CHECK (cardinality(span_ids) = cardinality(span_fingerprints)),
            CHECK ((kind = 'admission') = (admission_id = receipt_id))
        )
    """)
    op.execute("""
        CREATE INDEX native_citation_manifests_source_idx
        ON dungeonmind.native_citation_manifests
            (space_id, source_artifact_id, source_revision_id, authority_epoch)
    """)
    op.execute("""
        CREATE TABLE dungeonmind.native_citation_proofs (
            space_id text NOT NULL,
            receipt_id text NOT NULL,
            span_id text NOT NULL,
            evidence_ref_id text NOT NULL,
            source_revision_id text NOT NULL,
            start_byte bigint NOT NULL CHECK (start_byte >= 0),
            end_byte bigint NOT NULL CHECK (end_byte > start_byte),
            slice_sha256 text NOT NULL CHECK (slice_sha256 ~ '^[0-9a-f]{64}$'),
            PRIMARY KEY (space_id, receipt_id, span_id),
            FOREIGN KEY (space_id, receipt_id)
                REFERENCES dungeonmind.native_citation_manifests(space_id, receipt_id)
        )
    """)

    op.execute("""
        CREATE FUNCTION dungeonmind.invalidate_native_citation_manifest()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_ARGV[1] = 'admission' THEN
                UPDATE dungeonmind.native_citation_manifests
                SET intact = false
                WHERE space_id = OLD.space_id AND admission_id = to_jsonb(OLD)->>TG_ARGV[0];
            ELSE
                UPDATE dungeonmind.native_citation_manifests
                SET intact = false
                WHERE space_id = OLD.space_id AND receipt_id = to_jsonb(OLD)->>TG_ARGV[0];
            END IF;
            RETURN NULL;
        END
        $$
    """)
    for table, key, scope in _INVALIDATION_SOURCES:
        op.execute(f"""
            CREATE TRIGGER invalidate_native_citation_manifest
            AFTER UPDATE OR DELETE ON dungeonmind.{table}
            FOR EACH ROW EXECUTE FUNCTION
                dungeonmind.invalidate_native_citation_manifest('{key}', '{scope}')
        """)

    op.execute("""
        CREATE FUNCTION dungeonmind.protect_native_citation_manifest()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' AND pg_trigger_depth() > 1 AND NOT NEW.intact THEN
                NEW.intact := OLD.intact;
                IF NEW IS NOT DISTINCT FROM OLD THEN
                    NEW.intact := false;
                    RETURN NEW;
                END IF;
            END IF;
            RAISE EXCEPTION 'native citation manifest is immutable'
                USING ERRCODE = 'integrity_constraint_violation';
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER protect_native_citation_manifest
        BEFORE UPDATE OR DELETE ON dungeonmind.native_citation_manifests
        FOR EACH ROW EXECUTE FUNCTION dungeonmind.protect_native_citation_manifest()
    """)

    from dungeonmind.infrastructure.postgres.vnext_sources import backfill_native_citation_proofs

    driver = op.get_bind().connection.driver_connection
    previous_factory = driver.row_factory
    try:
        driver.row_factory = dict_row
        backfill_native_citation_proofs(driver)
    finally:
        driver.row_factory = previous_factory


_INVALIDATION_SOURCES = (
    ("knowledge_native_source_admissions", "admission_id", "admission"),
    ("knowledge_native_source_spans", "admission_id", "admission"),
    ("knowledge_native_source_extensions", "extension_id", "receipt"),
    ("knowledge_native_source_publications", "publication_id", "receipt"),
    ("knowledge_publication_receipts", "publication_id", "receipt"),
)


def downgrade() -> None:
    for table, _, _ in _INVALIDATION_SOURCES:
        op.execute(f"DROP TRIGGER invalidate_native_citation_manifest ON dungeonmind.{table}")
    op.execute("DROP FUNCTION dungeonmind.invalidate_native_citation_manifest()")
    op.execute("DROP TABLE dungeonmind.native_citation_proofs")
    op.execute("DROP TABLE dungeonmind.native_citation_manifests")
    op.execute("DROP FUNCTION dungeonmind.protect_native_citation_manifest()")
