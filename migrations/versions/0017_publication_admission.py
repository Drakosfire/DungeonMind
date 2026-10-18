"""Immutable first-use-only publication admission authority.

Deployment must exclude pre-gate writers while this migration backfills history.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0017_publication_admission"
down_revision = "0016_operator_source_attestation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""CREATE TABLE dungeonmind.publication_admission_profiles (
        profile_id text NOT NULL CHECK (octet_length(profile_id) BETWEEN 1 AND 512
            AND profile_id=btrim(profile_id)),
        profile_revision text NOT NULL CHECK (octet_length(profile_revision) BETWEEN 1 AND 512
            AND profile_revision=btrim(profile_revision)),
        descriptor_sha256 text NOT NULL CHECK (descriptor_sha256 ~ '^[0-9a-f]{64}$'),
        policy_payload jsonb,
        protected_use boolean,
        PRIMARY KEY(profile_id,profile_revision),
        CHECK (protected_use IS DISTINCT FROM TRUE OR policy_payload IS NOT NULL)
    )""")
    conn = op.get_bind()
    # Historical profile uses become irrevocably unprotected; reject ambiguous
    # descriptor history. Do not infer a profile for old schemas without one.
    rows = conn.execute(
        sa.text("""
        SELECT graph_payload->'semantic_profile' AS profile FROM dungeonmind.graph_revisions
        UNION ALL
        SELECT payload->'plan_ref'->'semantic_profile' AS profile
        FROM dungeonmind.contribution_reviews
    """)
    )
    identities = {}
    from dungeonmind.application.publication_admission import profile_ref

    for row in rows:
        ref = profile_ref(row.profile)
        if ref is None:
            continue
        key = (ref.profile_id, ref.profile_revision)
        if key in identities and identities[key] != ref.descriptor_sha256:
            raise ValueError("ambiguous historical profile descriptor")
        identities[key] = ref.descriptor_sha256
    for (profile_id, profile_revision), descriptor in sorted(identities.items()):
        conn.execute(
            sa.text("""INSERT INTO dungeonmind.publication_admission_profiles
            (profile_id,profile_revision,descriptor_sha256,protected_use)
            VALUES (:profile_id,:profile_revision,:descriptor,FALSE)"""),
            dict(profile_id=profile_id, profile_revision=profile_revision, descriptor=descriptor),
        )
    # Database-level append-only protection, in addition to the repository port.
    op.execute("""CREATE FUNCTION dungeonmind.guard_publication_admission_profile()
        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'admission authority is irreversible'; END IF;
        IF OLD.profile_id IS DISTINCT FROM NEW.profile_id
           OR OLD.profile_revision IS DISTINCT FROM NEW.profile_revision
           OR OLD.descriptor_sha256 IS DISTINCT FROM NEW.descriptor_sha256
           OR OLD.policy_payload IS DISTINCT FROM NEW.policy_payload
           OR (OLD.protected_use IS NOT NULL
               AND OLD.protected_use IS DISTINCT FROM NEW.protected_use)
        THEN RAISE EXCEPTION 'admission authority is immutable'; END IF;
        RETURN NEW; END $$""")
    op.execute("""CREATE TRIGGER immutable_admission_profile BEFORE UPDATE OR DELETE
        ON dungeonmind.publication_admission_profiles FOR EACH ROW
        EXECUTE FUNCTION dungeonmind.guard_publication_admission_profile()""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS (
        SELECT 1 FROM dungeonmind.publication_admission_profiles
        WHERE policy_payload IS NOT NULL OR protected_use IS TRUE)
        OR EXISTS (SELECT 1 FROM dungeonmind.finalized_review_publications
                   WHERE schema_version='dm_finalized_review_publication_v2')
        THEN RAISE EXCEPTION 'cannot discard protected publication admission authority';
        END IF; END $$""")
    op.execute("DROP TABLE dungeonmind.publication_admission_profiles")
    op.execute("DROP FUNCTION dungeonmind.guard_publication_admission_profile()")
