"""Atomic PostgreSQL publication for current-World identity reconciliation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from psycopg import Connection, sql

from ...application.world_identity_reconciliation import (
    IdentityReconciliationPublicationCommand,
    IdentityReconciliationPublicationResult,
)
from ...contracts.graph import PublishRevisionCommand
from ...contracts.identity import (
    IDENTITY_RECONCILIATION_DECISION_SCHEMA,
    IdentityReconciliationDecision,
)
from ...domain.errors import (
    IdempotencyConflictError,
    PersistenceIntegrityError,
    RevisionNotFoundError,
    StaleParentRevisionError,
)
from .database import SCHEMA, PostgresDatabase, jsonb, lock_world
from .graph import (
    _REVISION_SELECT,
    PostgresWorldGraphRepository,
    _reconstruct_stored_revision,
)
from .records import (
    _IDENTITY_SELECT,
    _append_identity_in_transaction,
    _return_identity,
)


class PostgresWorldIdentityReconciliationRepository:
    """One transaction for decisions, graph child, and World-head CAS."""

    def __init__(
        self,
        database: PostgresDatabase,
        *,
        failure_hook: Callable[[str], None] | None = None,
    ) -> None:
        self._database = database
        self._graph_repository = PostgresWorldGraphRepository(database)
        self._failure_hook = failure_hook

    def _fail(self, phase: str) -> None:
        if self._failure_hook is not None:
            self._failure_hook(phase)

    def _find_revision_for_operation(
        self,
        conn: Connection[Any],
        *,
        world_id: str,
        operation_token: str,
    ) -> Any | None:
        rows = conn.execute(
            sql.SQL(
                f"""
                SELECT {_REVISION_SELECT}
                FROM {{}}.graph_revisions
                WHERE world_id = %s
                  AND (revision_payload -> 'operation_ids') @> %s
                ORDER BY created_at, revision_id
                LIMIT 2
                """
            ).format(sql.Identifier(SCHEMA)),
            (world_id, jsonb([operation_token])),
        ).fetchall()
        if len(rows) > 1:
            raise PersistenceIntegrityError(
                f"operation token {operation_token!r} has multiple graph revisions"
            )
        return None if not rows else _reconstruct_stored_revision(rows[0])

    def _load_existing_result(
        self,
        conn: Connection[Any],
        command: IdentityReconciliationPublicationCommand,
        *,
        stored: Any,
    ) -> IdentityReconciliationPublicationResult:
        operation_ids = tuple(stored.revision.operation_ids)
        if tuple(command.operation_ids) != operation_ids:
            raise IdempotencyConflictError(
                f"operation {command.operation_id!r} was replayed with different material"
            )
        if stored.revision.revision_id != command.expected_published_revision_id:
            raise IdempotencyConflictError(
                f"operation {command.operation_id!r} was replayed with a different revision"
            )
        for decision in command.decisions:
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_IDENTITY_SELECT}
                    FROM {{}}.identity_decisions
                    WHERE world_id = %s AND decision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (command.world_id, decision.decision_id),
            ).fetchone()
            if row is None:
                raise PersistenceIntegrityError(
                    f"reconciliation decision {decision.decision_id!r} is missing"
                )
            stored_decision = _return_identity(row)
            if not isinstance(stored_decision, IdentityReconciliationDecision):
                raise PersistenceIntegrityError(
                    f"decision {decision.decision_id!r} has the wrong identity schema"
                )
            stored_material = stored_decision.model_dump(mode="json")
            expected_material = decision.model_dump(mode="json")
            stored_material.pop("created_at", None)
            expected_material.pop("created_at", None)
            if stored_material != expected_material:
                raise IdempotencyConflictError(
                    f"decision {decision.decision_id!r} was replayed with different material"
                )
        return IdentityReconciliationPublicationResult(
            world_id=command.world_id,
            operation_id=command.operation_id,
            parent_revision_id=command.expected_parent_revision_id,
            published_revision_id=stored.revision.revision_id,
            decision_ids=tuple(decision.decision_id for decision in command.decisions),
            already_applied=True,
        )

    def publish(
        self, command: IdentityReconciliationPublicationCommand
    ) -> IdentityReconciliationPublicationResult:
        operation_token = command.operation_ids[0]
        with self._database.transaction() as conn:
            existing = self._find_revision_for_operation(
                conn,
                world_id=command.world_id,
                operation_token=operation_token,
            )
            if existing is not None:
                return self._load_existing_result(conn, command, stored=existing)

            request_existing = self._find_revision_for_operation(
                conn,
                world_id=command.world_id,
                operation_token=command.operation_ids[1],
            )
            if request_existing is not None:
                raise IdempotencyConflictError(
                    f"request digest for operation {command.operation_id!r} is already committed"
                )

            lock_world(
                conn,
                command.world_id,
                created_at=command.requested_published_at,
            )
            parent_row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_REVISION_SELECT}
                    FROM {{}}.graph_revisions
                    WHERE world_id = %s AND revision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (command.world_id, command.expected_parent_revision_id),
            ).fetchone()
            if parent_row is None:
                raise RevisionNotFoundError(
                    f"revision {command.expected_parent_revision_id!r} not found for world "
                    f"{command.world_id!r}"
                )
            parent = _reconstruct_stored_revision(parent_row)
            if parent.revision.graph_payload_sha256 != command.parent_graph_payload_sha256:
                raise PersistenceIntegrityError(
                    "identity reconciliation parent payload hash does not match command"
                )

            head_row = conn.execute(
                sql.SQL(
                    """
                    SELECT head_revision_id
                    FROM {}.world_graph_heads
                    WHERE world_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (command.world_id,),
            ).fetchone()
            actual_head = None if head_row is None else head_row["head_revision_id"]
            if actual_head != command.expected_parent_revision_id:
                raise StaleParentRevisionError(
                    world_id=command.world_id,
                    expected_parent_revision_id=command.expected_parent_revision_id,
                    actual_head_revision_id=actual_head,
                )

            for index, decision in enumerate(command.decisions, start=1):
                self._fail(f"identity_decision_{index}")
                _append_identity_in_transaction(conn, decision)
            self._fail("after_identity_decisions")
            self._fail("before_graph_revision")

            revision = self._graph_repository._publish_revision_in_transaction(
                conn,
                PublishRevisionCommand(
                    world_id=command.world_id,
                    parent_revision_id=command.expected_parent_revision_id,
                    expected_parent_revision_id=command.expected_parent_revision_id,
                    operation_ids=list(command.operation_ids),
                    graph_schema=command.graph_schema,
                    graph_payload=command.graph_payload,
                    created_at=command.requested_published_at,
                ),
                world_locked=True,
            )
            if revision.revision_id != command.expected_published_revision_id:
                raise PersistenceIntegrityError(
                    "identity reconciliation published an unexpected revision id"
                )
            return IdentityReconciliationPublicationResult(
                world_id=command.world_id,
                operation_id=command.operation_id,
                parent_revision_id=command.expected_parent_revision_id,
                published_revision_id=revision.revision_id,
                decision_ids=tuple(decision.decision_id for decision in command.decisions),
            )

    def list_for_world(self, world_id: str) -> list[IdentityReconciliationDecision]:
        with self._database.transaction() as conn:
            rows = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_IDENTITY_SELECT}
                    FROM {{}}.identity_decisions
                    WHERE world_id = %s AND schema_version = %s
                    ORDER BY decision_id
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id, IDENTITY_RECONCILIATION_DECISION_SCHEMA),
            ).fetchall()
        records = [_return_identity(row) for row in rows]
        reconciliation_records: list[IdentityReconciliationDecision] = []
        for record in records:
            if not isinstance(record, IdentityReconciliationDecision):
                raise PersistenceIntegrityError(
                    "reconciliation history contains a non-reconciliation decision"
                )
            reconciliation_records.append(record)
        return reconciliation_records
