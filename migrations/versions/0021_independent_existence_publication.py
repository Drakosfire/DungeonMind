"""Make explicit independent-existence publication receipts append-only."""

from collections.abc import Sequence

from alembic import op

revision = "0021_independent_existence"
down_revision = "0020_adopted_relation_correction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""CREATE FUNCTION dungeonmind.reject_v7_publication_mutation()
    RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF OLD.schema_version = 'dm_finalized_review_publication_v3' OR
           OLD.payload->>'schema_version' = 'dm_finalized_review_publication_v3' THEN
            RAISE EXCEPTION 'independent existence publication is immutable';
        END IF;
        IF TG_OP = 'UPDATE' AND (NEW.schema_version = 'dm_finalized_review_publication_v3' OR
           NEW.payload->>'schema_version' = 'dm_finalized_review_publication_v3') THEN
            RAISE EXCEPTION 'cannot convert legacy publication to V3';
        END IF;
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER independent_existence_publication_append_only
        BEFORE UPDATE OR DELETE ON dungeonmind.finalized_review_publications
        FOR EACH ROW EXECUTE FUNCTION dungeonmind.reject_v7_publication_mutation()""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM dungeonmind.finalized_review_publications
          WHERE schema_version='dm_finalized_review_publication_v3' OR
                payload->>'schema_version'='dm_finalized_review_publication_v3') THEN
            RAISE EXCEPTION 'cannot downgrade populated independent existence publications';
        END IF;
    END $$""")
    op.execute(
        "DROP TRIGGER independent_existence_publication_append_only "
        "ON dungeonmind.finalized_review_publications"
    )
    op.execute("DROP FUNCTION dungeonmind.reject_v7_publication_mutation()")
