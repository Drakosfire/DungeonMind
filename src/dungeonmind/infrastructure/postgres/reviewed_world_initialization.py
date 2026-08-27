"""PostgreSQL atomic reviewed first-world initialization unit of work."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from psycopg import Connection, sql
from psycopg.errors import UniqueViolation

from ...application.graph_snapshot import GRAPH_SCHEMA_V6
from ...application.reviewed_world_initialization import (
    FirstWorldMaterialization,
    bind_reviewed_world_initialization_command,
    replay_conflict_if_present,
    reviewed_world_initialization_replay_identity,
    terminal_reviewed_world_initialization_receipt,
)
from ...contracts.contribution_review_v2 import contribution_v2_payload_sha256
from ...contracts.graph import PublishRevisionCommand
from ...contracts.reviewed_world_initialization import (
    ReviewedWorldInitializationCommandV1,
    ReviewedWorldInitializationReceiptV1,
)
from ...domain.canonical import canonical_sha256
from ...domain.errors import IdempotencyConflictError, PersistenceIntegrityError
from .database import SCHEMA, PostgresDatabase, jsonb, lock_world
from .graph import (
    _REVISION_SELECT,
    PostgresWorldGraphRepository,
    _reconstruct_stored_revision,
)
from .records import (
    _append_contribution_in_transaction,
    _put_artifact_in_transaction,
    _put_revision_in_transaction,
)
from .serialization import dump_payload, model_fingerprint, reconstruct

_INIT_SELECT = """
    world_id,
    initialization_id,
    source_plan_id,
    source_plan_sha256,
    command_sha256,
    reviewed_contribution_id,
    reviewed_contribution_sha256,
    published_revision_id,
    published_graph_schema,
    published_graph_payload_sha256,
    initialized_at,
    schema_version,
    record_fingerprint,
    payload
"""


def _init_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "world_id": row["world_id"],
        "initialization_id": row["initialization_id"],
        "source_plan_id": row["source_plan_id"],
        "source_plan_sha256": row["source_plan_sha256"],
        "command_sha256": row["command_sha256"],
        "reviewed_contribution_id": row["reviewed_contribution_id"],
        "reviewed_contribution_sha256": row["reviewed_contribution_sha256"],
        "published_revision_id": row["published_revision_id"],
        "published_graph_schema": row["published_graph_schema"],
        "published_graph_payload_sha256": row["published_graph_payload_sha256"],
        "initialized_at": row["initialized_at"],
        "schema_version": row["schema_version"],
    }


def _init_row(
    conn: Connection[Any],
    *,
    world_id: str,
    initialization_id: str | None = None,
) -> dict[str, Any] | None:
    if initialization_id is None:
        return conn.execute(
            sql.SQL(
                f"""
                SELECT {_INIT_SELECT}
                FROM {{}}.reviewed_world_initializations
                WHERE world_id = %s
                """
            ).format(sql.Identifier(SCHEMA)),
            (world_id,),
        ).fetchone()
    return conn.execute(
        sql.SQL(
            f"""
            SELECT {_INIT_SELECT}
            FROM {{}}.reviewed_world_initializations
            WHERE world_id = %s AND initialization_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (world_id, initialization_id),
    ).fetchone()


def _init_row_for_id(conn: Connection[Any], initialization_id: str) -> dict[str, Any] | None:
    return conn.execute(
        sql.SQL(
            f"""
            SELECT {_INIT_SELECT}
            FROM {{}}.reviewed_world_initializations
            WHERE initialization_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (initialization_id,),
    ).fetchone()


def _exists(conn: Connection[Any], query: str, params: tuple[Any, ...]) -> bool:
    row = conn.execute(
        sql.SQL(query).format(sql.Identifier(SCHEMA)),
        params,
    ).fetchone()
    return row is not None


class PostgresReviewedWorldInitializationRepository:
    """Atomic PostgreSQL reviewed first-world initialization unit of work."""

    def __init__(
        self,
        database: PostgresDatabase,
        *,
        failure_hook: Callable[[str], None] | None = None,
    ) -> None:
        self._database = database
        self._graph = PostgresWorldGraphRepository(database)
        self._failure_hook = failure_hook

    def _return_receipt(self, row: dict[str, Any]) -> ReviewedWorldInitializationReceiptV1:
        identity = _init_identity(row)
        try:
            receipt = reconstruct(
                ReviewedWorldInitializationReceiptV1,
                dict(row["payload"]),
                expected_fingerprint=row["record_fingerprint"],
                identity=identity,
            )
        except Exception:
            raise PersistenceIntegrityError(
                "reviewed-world initialization receipt failed reconstruction"
            ) from None
        return receipt.model_copy(deep=True)

    def _load_verified(
        self,
        conn: Connection[Any],
        row: dict[str, Any],
    ) -> ReviewedWorldInitializationReceiptV1:
        receipt = self._return_receipt(row)
        revision_row = conn.execute(
            sql.SQL(
                f"""
                SELECT {_REVISION_SELECT}
                FROM {{}}.graph_revisions
                WHERE world_id = %s AND revision_id = %s
                """
            ).format(sql.Identifier(SCHEMA)),
            (receipt.world_id, receipt.published_revision_id),
        ).fetchone()
        if revision_row is None:
            raise PersistenceIntegrityError(
                "reviewed-world initialization receipt references a missing revision"
            )
        stored = _reconstruct_stored_revision(revision_row)
        if (
            stored.revision.graph_payload_sha256 != receipt.published_graph_payload_sha256
            or stored.revision.graph_schema != receipt.published_graph_schema
            or stored.revision.world_id != receipt.world_id
            or stored.revision.parent_revision_id is not None
        ):
            raise PersistenceIntegrityError(
                "reviewed-world initialization receipt disagrees with its published revision"
            )
        return receipt

    def _assert_pristine(self, conn: Connection[Any], world_id: str) -> None:
        checks = (
            (
                "SELECT 1 FROM {}.existing_world_adoptions WHERE world_id = %s LIMIT 1",
                "existing_world_adoption",
            ),
            (
                "SELECT 1 FROM {}.reviewed_world_initializations WHERE world_id = %s LIMIT 1",
                "reviewed_world_initialization",
            ),
            (
                "SELECT 1 FROM {}.world_graph_heads WHERE world_id = %s",
                "graph_head",
            ),
            (
                "SELECT 1 FROM {}.graph_revisions WHERE world_id = %s LIMIT 1",
                "graph_revision",
            ),
            (
                "SELECT 1 FROM {}.graph_contributions WHERE world_id = %s LIMIT 1",
                "contribution",
            ),
            (
                "SELECT 1 FROM {}.identity_decisions WHERE world_id = %s LIMIT 1",
                "identity_decision",
            ),
            (
                "SELECT 1 FROM {}.source_artifacts WHERE world_id = %s LIMIT 1",
                "source_artifact",
            ),
        )
        for query, family in checks:
            if _exists(conn, query, (world_id,)):
                raise PersistenceIntegrityError(
                    "reviewed-world initialization target is not pristine",
                    details={"reason": "non_pristine_target", "family": family},
                )

    def _insert_receipt(
        self,
        conn: Connection[Any],
        receipt: ReviewedWorldInitializationReceiptV1,
    ) -> dict[str, Any]:
        fingerprint = model_fingerprint(receipt)
        conn.execute(
            sql.SQL(
                """
                INSERT INTO {}.reviewed_world_initializations (
                    world_id,
                    initialization_id,
                    source_plan_id,
                    source_plan_sha256,
                    command_sha256,
                    reviewed_contribution_id,
                    reviewed_contribution_sha256,
                    published_revision_id,
                    published_graph_schema,
                    published_graph_payload_sha256,
                    initialized_at,
                    schema_version,
                    record_fingerprint,
                    payload
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """
            ).format(sql.Identifier(SCHEMA)),
            (
                receipt.world_id,
                receipt.initialization_id,
                receipt.source_plan_id,
                receipt.source_plan_sha256,
                receipt.command_sha256,
                receipt.reviewed_contribution_id,
                receipt.reviewed_contribution_sha256,
                receipt.published_revision_id,
                receipt.published_graph_schema,
                receipt.published_graph_payload_sha256,
                receipt.initialized_at,
                receipt.schema_version,
                fingerprint,
                jsonb(dump_payload(receipt)),
            ),
        )
        row = _init_row(
            conn, world_id=receipt.world_id, initialization_id=receipt.initialization_id
        )
        if row is None:
            raise PersistenceIntegrityError(
                "reviewed-world initialization receipt missing after insert"
            )
        return row

    def get(
        self, world_id: str, initialization_id: str
    ) -> ReviewedWorldInitializationReceiptV1 | None:
        with self._database.transaction() as conn:
            row = _init_row(conn, world_id=world_id, initialization_id=initialization_id)
            return None if row is None else self._load_verified(conn, row)

    def get_for_world(self, world_id: str) -> ReviewedWorldInitializationReceiptV1 | None:
        with self._database.transaction() as conn:
            row = _init_row(conn, world_id=world_id)
            return None if row is None else self._load_verified(conn, row)

    def initialize(
        self,
        command: ReviewedWorldInitializationCommandV1,
        *,
        graph_payload: dict[str, Any],
        graph_payload_sha256: str,
        accepted_assertion_ids: Sequence[str],
    ) -> ReviewedWorldInitializationReceiptV1:
        validated = bind_reviewed_world_initialization_command(command)
        identity = reviewed_world_initialization_replay_identity(validated)
        command_sha256 = identity.current_command_sha256
        world_id = validated.world_id
        if canonical_sha256(graph_payload) != graph_payload_sha256:
            raise PersistenceIntegrityError(
                "reviewed-world initialization graph payload digest disagrees with the command"
            )
        with self._database.transaction() as conn:
            lock_world(conn, world_id, created_at=validated.requested_initialized_at)
            existing_row = _init_row(conn, world_id=world_id)
            verified_existing = (
                self._load_verified(conn, existing_row) if existing_row is not None else None
            )
            matched = replay_conflict_if_present(
                verified_existing,
                initialization_id=validated.initialization_id,
                identity=identity,
                world_id=world_id,
                other_world_receipt=lambda: (
                    self._load_verified(conn, other)
                    if (other := _init_row_for_id(conn, validated.initialization_id))
                    is not None
                    else None
                ),
            )
            if matched is not None:
                return matched
            self._assert_pristine(conn, world_id)
            for artifact in validated.source_artifacts:
                _put_artifact_in_transaction(conn, artifact)
            for revision in validated.source_revisions:
                _put_revision_in_transaction(conn, revision)
            if self._failure_hook is not None:
                self._failure_hook("source_records")
            _append_contribution_in_transaction(conn, validated.reviewed_contribution)
            if self._failure_hook is not None:
                self._failure_hook("contributions")
            graph_command = PublishRevisionCommand(
                world_id=world_id,
                parent_revision_id=None,
                expected_parent_revision_id=None,
                operation_ids=[validated.initialization_id],
                graph_schema=GRAPH_SCHEMA_V6,
                graph_payload=graph_payload,
                created_at=validated.requested_initialized_at,
            )
            revision = self._graph._publish_revision_in_transaction(
                conn,
                graph_command,
                world_locked=True,
            )
            if revision.graph_payload_sha256 != graph_payload_sha256:
                raise PersistenceIntegrityError(
                    "published initialization payload digest disagrees with the command"
                )
            if revision.parent_revision_id is not None:
                raise PersistenceIntegrityError(
                    "published initialization revision must have a null parent"
                )
            if self._failure_hook is not None:
                self._failure_hook("graph")
            try:
                materialization = FirstWorldMaterialization(
                    world_id=validated.world_id,
                    initialization_id=validated.initialization_id,
                    reviewed_contribution_id=validated.reviewed_contribution.contribution_id,
                    reviewed_contribution_sha256=contribution_v2_payload_sha256(
                        validated.reviewed_contribution
                    ),
                    graph_schema=GRAPH_SCHEMA_V6,
                    graph_payload=graph_payload,
                    graph_payload_sha256=graph_payload_sha256,
                    accepted_assertion_ids=tuple(accepted_assertion_ids),
                )
            except Exception:
                raise PersistenceIntegrityError(
                    "reviewed-world initialization materialization binding failed"
                ) from None
            receipt = terminal_reviewed_world_initialization_receipt(
                validated,
                command_sha256=command_sha256,
                materialization=materialization,
                published_revision_id=revision.revision_id,
            )
            try:
                row = self._insert_receipt(conn, receipt)
            except UniqueViolation:
                raise IdempotencyConflictError(
                    f"initialization {validated.initialization_id!r} already exists "
                    "for another world"
                ) from None
            if self._failure_hook is not None:
                self._failure_hook("receipt")
            return self._load_verified(conn, row)
