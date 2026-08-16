"""PostgreSQL atomic existing-world adoption unit of work."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from psycopg import Connection, sql

from ...contracts.existing_world_adoption import (
    ExistingWorldAdoptionCommandV1,
    ExistingWorldAdoptionReceiptV1,
)
from ...contracts.graph import PublishRevisionCommand
from ...domain.errors import IdempotencyConflictError, PersistenceIntegrityError
from .database import SCHEMA, PostgresDatabase, jsonb, lock_world
from .graph import (
    _REVISION_SELECT,
    PostgresWorldGraphRepository,
    _reconstruct_stored_revision,
)
from .records import (
    _append_contribution_in_transaction,
    _append_identity_in_transaction,
    _put_artifact_in_transaction,
    _put_revision_in_transaction,
)
from .serialization import dump_payload, model_fingerprint, reconstruct

_ADOPTION_SELECT = """
    world_id,
    adoption_id,
    bundle_sha256,
    published_revision_id,
    graph_schema,
    graph_payload_sha256,
    adopted_at,
    source_artifact_count,
    source_revision_count,
    contribution_count,
    identity_decision_count,
    schema_version,
    record_fingerprint,
    payload
"""


def _adoption_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "world_id": row["world_id"],
        "adoption_id": row["adoption_id"],
        "bundle_sha256": row["bundle_sha256"],
        "published_revision_id": row["published_revision_id"],
        "graph_schema": row["graph_schema"],
        "graph_payload_sha256": row["graph_payload_sha256"],
        "adopted_at": row["adopted_at"],
        "source_artifact_count": row["source_artifact_count"],
        "source_revision_count": row["source_revision_count"],
        "contribution_count": row["contribution_count"],
        "identity_decision_count": row["identity_decision_count"],
        "schema_version": row["schema_version"],
    }


def _adoption_row(
    conn: Connection[Any],
    *,
    world_id: str,
    adoption_id: str | None = None,
) -> dict[str, Any] | None:
    if adoption_id is None:
        return conn.execute(
            sql.SQL(
                f"""
                SELECT {_ADOPTION_SELECT}
                FROM {{}}.existing_world_adoptions
                WHERE world_id = %s
                """
            ).format(sql.Identifier(SCHEMA)),
            (world_id,),
        ).fetchone()
    return conn.execute(
        sql.SQL(
            f"""
            SELECT {_ADOPTION_SELECT}
            FROM {{}}.existing_world_adoptions
            WHERE world_id = %s AND adoption_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (world_id, adoption_id),
    ).fetchone()


def _exists(conn: Connection[Any], query: str, params: tuple[Any, ...]) -> bool:
    row = conn.execute(
        sql.SQL(query).format(sql.Identifier(SCHEMA)),
        params,
    ).fetchone()
    return row is not None


class PostgresExistingWorldAdoptionRepository:
    """Atomic PostgreSQL existing-world adoption unit of work."""

    def __init__(
        self,
        database: PostgresDatabase,
        *,
        failure_hook: Callable[[str], None] | None = None,
    ) -> None:
        self._database = database
        self._graph = PostgresWorldGraphRepository(database)
        self._failure_hook = failure_hook

    @staticmethod
    def _reload_command(
        command: ExistingWorldAdoptionCommandV1,
    ) -> ExistingWorldAdoptionCommandV1:
        try:
            return ExistingWorldAdoptionCommandV1.model_validate(command.model_dump(mode="json"))
        except Exception:
            raise PersistenceIntegrityError(
                "existing-world adoption command failed validation"
            ) from None

    def _return_receipt(self, row: dict[str, Any]) -> ExistingWorldAdoptionReceiptV1:
        identity = _adoption_identity(row)
        try:
            receipt = reconstruct(
                ExistingWorldAdoptionReceiptV1,
                dict(row["payload"]),
                expected_fingerprint=row["record_fingerprint"],
                identity=identity,
            )
        except Exception:
            raise PersistenceIntegrityError(
                "existing-world adoption receipt failed reconstruction"
            ) from None
        return receipt.model_copy(deep=True)

    def _load_verified(
        self,
        conn: Connection[Any],
        row: dict[str, Any],
    ) -> ExistingWorldAdoptionReceiptV1:
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
                "existing-world adoption receipt references a missing revision"
            )
        stored = _reconstruct_stored_revision(revision_row)
        if (
            stored.revision.graph_payload_sha256 != receipt.graph_payload_sha256
            or stored.revision.graph_schema != receipt.graph_schema
            or stored.revision.world_id != receipt.world_id
        ):
            raise PersistenceIntegrityError(
                "existing-world adoption receipt disagrees with its published revision"
            )
        return receipt

    def _assert_pristine(self, conn: Connection[Any], world_id: str) -> None:
        checks = (
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
                    "existing-world adoption target is not pristine",
                    details={"reason": "non_pristine_target", "family": family},
                )

    def _insert_receipt(
        self,
        conn: Connection[Any],
        receipt: ExistingWorldAdoptionReceiptV1,
    ) -> dict[str, Any]:
        fingerprint = model_fingerprint(receipt)
        conn.execute(
            sql.SQL(
                """
                INSERT INTO {}.existing_world_adoptions (
                    world_id,
                    adoption_id,
                    bundle_sha256,
                    published_revision_id,
                    graph_schema,
                    graph_payload_sha256,
                    adopted_at,
                    source_artifact_count,
                    source_revision_count,
                    contribution_count,
                    identity_decision_count,
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
                receipt.adoption_id,
                receipt.bundle_sha256,
                receipt.published_revision_id,
                receipt.graph_schema,
                receipt.graph_payload_sha256,
                receipt.adopted_at,
                receipt.source_artifact_count,
                receipt.source_revision_count,
                receipt.contribution_count,
                receipt.identity_decision_count,
                receipt.schema_version,
                fingerprint,
                jsonb(dump_payload(receipt)),
            ),
        )
        row = _adoption_row(conn, world_id=receipt.world_id, adoption_id=receipt.adoption_id)
        if row is None:
            raise PersistenceIntegrityError("existing-world adoption receipt missing after insert")
        return row

    def get(self, world_id: str, adoption_id: str) -> ExistingWorldAdoptionReceiptV1 | None:
        with self._database.transaction() as conn:
            row = _adoption_row(conn, world_id=world_id, adoption_id=adoption_id)
            return None if row is None else self._load_verified(conn, row)

    def get_for_world(self, world_id: str) -> ExistingWorldAdoptionReceiptV1 | None:
        with self._database.transaction() as conn:
            row = _adoption_row(conn, world_id=world_id)
            return None if row is None else self._load_verified(conn, row)

    def adopt(self, command: ExistingWorldAdoptionCommandV1) -> ExistingWorldAdoptionReceiptV1:
        validated = self._reload_command(command)
        bundle = validated.bundle
        world_id = bundle.world_id
        with self._database.transaction() as conn:
            lock_world(conn, world_id, created_at=validated.requested_adopted_at)
            existing_row = _adoption_row(conn, world_id=world_id)
            if existing_row is not None:
                existing = self._load_verified(conn, existing_row)
                if existing.bundle_sha256 == validated.bundle_sha256:
                    return existing
                raise IdempotencyConflictError(
                    "existing-world adoption identity conflicts with the requested bundle"
                )
            self._assert_pristine(conn, world_id)
            for artifact in bundle.source_artifacts:
                _put_artifact_in_transaction(conn, artifact)
            for revision in bundle.source_revisions:
                _put_revision_in_transaction(conn, revision)
            for contribution in bundle.contributions:
                _append_contribution_in_transaction(conn, contribution)
            for decision in bundle.identity_decisions:
                _append_identity_in_transaction(conn, decision)
            if self._failure_hook is not None:
                self._failure_hook("source_history")
            graph_command = PublishRevisionCommand(
                world_id=world_id,
                parent_revision_id=None,
                expected_parent_revision_id=None,
                operation_ids=[bundle.adoption_id],
                graph_schema=bundle.graph_schema,
                graph_payload=bundle.graph_payload,
                created_at=validated.requested_adopted_at,
            )
            revision = self._graph._publish_revision_in_transaction(
                conn,
                graph_command,
                world_locked=True,
            )
            if revision.revision_id != validated.expected_published_revision_id:
                raise PersistenceIntegrityError(
                    "published adoption revision id disagrees with the command"
                )
            if revision.graph_payload_sha256 != validated.graph_payload_sha256:
                raise PersistenceIntegrityError(
                    "published adoption payload digest disagrees with the command"
                )
            if self._failure_hook is not None:
                self._failure_hook("graph")
            receipt = ExistingWorldAdoptionReceiptV1(
                adoption_id=bundle.adoption_id,
                world_id=world_id,
                bundle_sha256=validated.bundle_sha256,
                source_provenance=bundle.source_provenance,
                published_revision_id=revision.revision_id,
                graph_schema=bundle.graph_schema,
                graph_payload_sha256=validated.graph_payload_sha256,
                adopted_at=validated.requested_adopted_at,
                source_artifact_count=len(bundle.source_artifacts),
                source_revision_count=len(bundle.source_revisions),
                contribution_count=len(bundle.contributions),
                identity_decision_count=len(bundle.identity_decisions),
            )
            row = self._insert_receipt(conn, receipt)
            if self._failure_hook is not None:
                self._failure_hook("receipt")
            return self._load_verified(conn, row)
