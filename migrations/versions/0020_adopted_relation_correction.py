"""Append-only receipts for atomic adopted relationship replacement."""

from collections.abc import Sequence

from alembic import op

revision = "0020_adopted_relation_correction"
down_revision = "0019_complete_object_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""CREATE TABLE dungeonmind.adopted_relationship_corrections (
        operation_id text PRIMARY KEY,
        world_id text NOT NULL REFERENCES dungeonmind.worlds(world_id),
        adoption_id text NOT NULL REFERENCES dungeonmind.existing_world_adoptions(adoption_id),
        parent_revision_id text NOT NULL,
        published_revision_id text NOT NULL,
        request_sha256 text NOT NULL,
        record_fingerprint text NOT NULL,
        payload jsonb NOT NULL,
        FOREIGN KEY (world_id,parent_revision_id)
            REFERENCES dungeonmind.graph_revisions(world_id,revision_id),
        FOREIGN KEY (world_id,published_revision_id)
            REFERENCES dungeonmind.graph_revisions(world_id,revision_id),
        CHECK (payload ? 'schema_version' AND
            payload->>'schema_version' = 'dm_adopted_relationship_correction_receipt_v1'),
        CHECK (payload ? 'command' AND payload ? 'identity_history' AND payload ? 'rules_sha256')
    )""")
    op.execute("""CREATE TRIGGER adopted_relationship_corrections_append_only
        BEFORE UPDATE OR DELETE ON dungeonmind.adopted_relationship_corrections
        FOR EACH ROW EXECUTE FUNCTION dungeonmind.reject_adopted_assertion_withdrawal_mutation()""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM dungeonmind.adopted_relationship_corrections) THEN
            RAISE EXCEPTION 'cannot downgrade populated adopted relationship corrections';
        END IF; END $$""")
    op.execute("DROP TABLE dungeonmind.adopted_relationship_corrections")
