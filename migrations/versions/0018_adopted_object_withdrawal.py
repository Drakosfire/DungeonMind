"""Admit explicit object-target withdrawal receipts without weakening old schemas."""

from collections.abc import Sequence

from alembic import op

revision = "0018_adopted_object_withdrawal"
down_revision = "0017_publication_admission"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None
TABLE = "dungeonmind.adopted_assertion_withdrawals"
VERSION = "adopted_assertion_withdrawals_schema_version_check"
LOCATOR = "adopted_assertion_withdrawals_version_locator_check"
TARGET = "adopted_assertion_withdrawals_version_target_check"
V1 = "dm_adopted_assertion_withdrawal_receipt_v1"
V2 = "dm_adopted_assertion_withdrawal_receipt_v2"
V3 = "dm_adopted_object_withdrawal_receipt_v3"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT {VERSION}")
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT {LOCATOR}")
    for field in ["relationship_id", "predicate", "object_object_id"]:
        op.execute(f"ALTER TABLE {TABLE} ALTER COLUMN {field} DROP NOT NULL")
    op.execute(
        f"ALTER TABLE {TABLE} ADD CONSTRAINT {VERSION} "
        f"CHECK (schema_version IN ('{V1}','{V2}','{V3}'))"
    )
    op.execute(f"""ALTER TABLE {TABLE} ADD CONSTRAINT {LOCATOR} CHECK (
        (schema_version='{V1}' AND source_locator IS NOT NULL) OR
        (schema_version='{V2}' AND source_locator IS NULL) OR schema_version='{V3}')""")
    op.execute(f"""ALTER TABLE {TABLE} ADD CONSTRAINT {TARGET} CHECK (
        (schema_version IN ('{V1}','{V2}') AND relationship_id IS NOT NULL
         AND predicate IS NOT NULL AND object_object_id IS NOT NULL) OR
        (schema_version='{V3}' AND relationship_id IS NULL
         AND predicate IS NULL AND object_object_id IS NULL))""")


def downgrade() -> None:
    op.execute(f"""DO $$ BEGIN IF EXISTS (SELECT 1 FROM {TABLE} WHERE schema_version='{V3}')
        THEN RAISE EXCEPTION 'cannot downgrade populated object withdrawal receipts';
        END IF; END $$""")
    for constraint in [TARGET, VERSION, LOCATOR]:
        op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT {constraint}")
    for field in ["relationship_id", "predicate", "object_object_id"]:
        op.execute(f"ALTER TABLE {TABLE} ALTER COLUMN {field} SET NOT NULL")
    op.execute(
        f"ALTER TABLE {TABLE} ADD CONSTRAINT {VERSION} CHECK (schema_version IN ('{V1}','{V2}'))"
    )
    op.execute(f"""ALTER TABLE {TABLE} ADD CONSTRAINT {LOCATOR} CHECK (
        (schema_version='{V1}' AND source_locator IS NOT NULL) OR
        (schema_version='{V2}' AND source_locator IS NULL))""")
