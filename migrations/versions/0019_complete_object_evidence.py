"""Retain complete evidence tuples in versioned adopted object withdrawals."""

from collections.abc import Sequence

from alembic import op

revision = "0019_complete_object_evidence"
down_revision = "0018_adopted_object_withdrawal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
TABLE = "dungeonmind.adopted_assertion_withdrawals"
PREFIX = "adopted_assertion_withdrawals_"
V1 = "dm_adopted_assertion_withdrawal_receipt_v1"
V2 = "dm_adopted_assertion_withdrawal_receipt_v2"
V3 = "dm_adopted_object_withdrawal_receipt_v3"
V4 = "dm_adopted_object_withdrawal_receipt_v4"


def _target_constraints(*, complete: bool) -> None:
    object_versions = f"'{V3}','{V4}'" if complete else f"'{V3}'"
    versions = f"'{V1}','{V2}',{object_versions}"
    op.execute(
        f"ALTER TABLE {TABLE} ADD CONSTRAINT {PREFIX}schema_version_check "
        f"CHECK (schema_version IN ({versions}))"
    )
    op.execute(f"""ALTER TABLE {TABLE} ADD CONSTRAINT {PREFIX}version_locator_check CHECK (
        (schema_version='{V1}' AND source_locator IS NOT NULL) OR
        (schema_version='{V2}' AND source_locator IS NULL) OR
        schema_version IN ({object_versions}))""")
    op.execute(f"""ALTER TABLE {TABLE} ADD CONSTRAINT {PREFIX}version_target_check CHECK (
        (schema_version IN ('{V1}','{V2}') AND relationship_id IS NOT NULL
         AND predicate IS NOT NULL AND object_object_id IS NOT NULL) OR
        (schema_version IN ({object_versions}) AND relationship_id IS NULL
         AND predicate IS NULL AND object_object_id IS NULL))""")


def _drop_target_constraints() -> None:
    for suffix in ("schema_version_check", "version_locator_check", "version_target_check"):
        op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT {PREFIX}{suffix}")


def upgrade() -> None:
    _drop_target_constraints()
    _target_constraints(complete=True)
    op.execute(f"""ALTER TABLE {TABLE} ADD CONSTRAINT {PREFIX}complete_evidence_check CHECK (
        schema_version <> '{V4}' OR (
            payload ? 'evidence_bindings' AND
            jsonb_typeof(payload->'evidence_bindings') = 'array' AND
            jsonb_array_length(payload->'evidence_bindings') >= 2))""")


def downgrade() -> None:
    op.execute(f"""DO $$ BEGIN IF EXISTS (SELECT 1 FROM {TABLE} WHERE schema_version='{V4}')
        THEN RAISE EXCEPTION 'cannot downgrade populated complete-evidence withdrawal receipts';
        END IF; END $$""")
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT {PREFIX}complete_evidence_check")
    _drop_target_constraints()
    _target_constraints(complete=False)
