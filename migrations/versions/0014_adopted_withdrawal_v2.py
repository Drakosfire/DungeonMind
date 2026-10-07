"""Extend withdrawal receipts for explicit locator-null V2 evidence.

Revision ID: 0014_adopted_withdrawal_v2
Revises: 0013_adopted_withdrawal_v1
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014_adopted_withdrawal_v2"
down_revision: str | None = "0013_adopted_withdrawal_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
TABLE = "dungeonmind.adopted_assertion_withdrawals"
VERSION_CHECK = "adopted_assertion_withdrawals_schema_version_check"
LOCATOR_CHECK = "adopted_assertion_withdrawals_version_locator_check"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT {VERSION_CHECK}")
    op.execute(f"ALTER TABLE {TABLE} ALTER COLUMN source_locator DROP NOT NULL")
    op.execute(f"""
        ALTER TABLE {TABLE} ADD CONSTRAINT {VERSION_CHECK} CHECK (
            schema_version IN ('dm_adopted_assertion_withdrawal_receipt_v1',
                               'dm_adopted_assertion_withdrawal_receipt_v2')
        )
    """)
    op.execute(f"""
        ALTER TABLE {TABLE} ADD CONSTRAINT {LOCATOR_CHECK} CHECK (
            (schema_version = 'dm_adopted_assertion_withdrawal_receipt_v1'
             AND source_locator IS NOT NULL) OR
            (schema_version = 'dm_adopted_assertion_withdrawal_receipt_v2'
             AND source_locator IS NULL)
        )
    """)


def downgrade() -> None:
    op.execute(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM {TABLE}
                       WHERE schema_version = 'dm_adopted_assertion_withdrawal_receipt_v2')
            THEN
                RAISE EXCEPTION 'cannot downgrade while V2 withdrawal receipts exist';
            END IF;
        END $$
    """)
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT {LOCATOR_CHECK}")
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT {VERSION_CHECK}")
    op.execute(f"ALTER TABLE {TABLE} ALTER COLUMN source_locator SET NOT NULL")
    op.execute(f"""
        ALTER TABLE {TABLE} ADD CONSTRAINT {VERSION_CHECK} CHECK (
            schema_version = 'dm_adopted_assertion_withdrawal_receipt_v1'
        )
    """)
