"""PostgreSQL native vNext revision and head authority."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from psycopg import Connection, sql

from ...application.vnext.authority import (
    commit_expected_parent,
    revision_from_command,
    verify_stored_revision,
)
from ...application.vnext.errors import KnowledgePublicationIdempotencyConflictError
from ...application.vnext.records import KnowledgeHeadEvent, StoredKnowledgeRevision
from ...contracts.vnext.knowledge import (
    KnowledgeHead,
    KnowledgeRevision,
    PublishKnowledgeRevisionCommand,
)
from ...contracts.vnext.publication import KnowledgePublicationReceipt
from ...domain.canonical import canonical_json, canonical_sha256
from ...domain.errors import PersistenceIntegrityError
from .database import SCHEMA, PostgresDatabase, jsonb
from .serialization import _normalize

_REVISION_SELECT = """
    space_id,
    revision_id,
    parent_revision_id,
    created_at,
    graph_schema,
    graph_payload_sha256,
    schema_version,
    record_fingerprint,
    revision_payload,
    graph_payload
"""


class PostgresKnowledgeRevisionRepository:
    """Durable expected-parent CAS. One transaction owns revision, head, and event."""

    def __init__(
        self,
        database: PostgresDatabase,
        *,
        after_revision_insert: Callable[[], None] | None = None,
    ) -> None:
        self._database = database
        self._after_revision_insert = after_revision_insert

    def get_head(self, space_id: str) -> KnowledgeHead | None:
        with self._database.transaction() as conn:
            return _read_head(conn, space_id)

    def get_revision(self, space_id: str, revision_id: str) -> StoredKnowledgeRevision | None:
        with self._database.transaction() as conn:
            return _read_revision(conn, space_id, revision_id)

    def head_events(self, space_id: str) -> tuple[KnowledgeHeadEvent, ...]:
        with self._database.transaction() as conn:
            rows = conn.execute(
                sql.SQL(
                    """
                    SELECT event_kind, previous_revision_id, target_revision_id, occurred_at
                    FROM {}.knowledge_head_events
                    WHERE space_id = %s
                    ORDER BY event_id
                    """
                ).format(sql.Identifier(SCHEMA)),
                (space_id,),
            ).fetchall()
        return tuple(
            KnowledgeHeadEvent(
                space_id=space_id,
                event_kind=row["event_kind"],
                previous_revision_id=row["previous_revision_id"],
                target_revision_id=row["target_revision_id"],
                occurred_at=row["occurred_at"],
            )
            for row in rows
        )

    def publish_revision(self, command: PublishKnowledgeRevisionCommand) -> StoredKnowledgeRevision:
        with self._database.transaction() as conn:
            _lock_space(conn, command.space_id, created_at=command.created_at)

            def insert_revision(stored: StoredKnowledgeRevision) -> None:
                _insert_revision(conn, stored)
                if self._after_revision_insert is not None:
                    self._after_revision_insert()

            def advance_head(head: KnowledgeHead, event: KnowledgeHeadEvent) -> None:
                _advance_head(conn, head, event)

            return commit_expected_parent(
                command,
                read_head=lambda: _read_head(conn, command.space_id),
                read_revision=lambda revision_id: _read_revision(
                    conn, command.space_id, revision_id
                ),
                insert_revision=insert_revision,
                advance_head=advance_head,
            )

    def get_publication_receipt(
        self, space_id: str, publication_id: str
    ) -> KnowledgePublicationReceipt | None:
        with self._database.transaction() as conn:
            return _read_receipt(conn, space_id, publication_id)

    def publish_publication(
        self, command: PublishKnowledgeRevisionCommand, publication_id: str
    ) -> KnowledgePublicationReceipt:
        with self._database.transaction() as conn:
            _lock_space(conn, command.space_id, created_at=command.created_at)
            existing = _read_receipt(conn, command.space_id, publication_id)
            command_sha = canonical_sha256(command.model_dump(mode="json"))
            if existing is not None:
                if existing.command_sha256 != command_sha:
                    raise KnowledgePublicationIdempotencyConflictError(
                        space_id=command.space_id, publication_id=publication_id
                    )
                return existing
            stored = commit_expected_parent(
                command,
                read_head=lambda: _read_head(conn, command.space_id),
                read_revision=lambda revision_id: _read_revision(
                    conn, command.space_id, revision_id
                ),
                insert_revision=lambda value: _insert_revision(conn, value),
                advance_head=lambda head, event: _advance_head(conn, head, event),
            )
            receipt = KnowledgePublicationReceipt(
                space_id=command.space_id,
                publication_id=publication_id,
                command_sha256=command_sha,
                expected_parent_revision_id=command.expected_parent_revision_id,
                published_revision_id=stored.revision.revision_id,
                graph_payload_sha256=stored.graph_payload_sha256,
            )
            _insert_receipt(conn, receipt)
            return receipt


def _lock_space(conn: Connection[Any], space_id: str, *, created_at: Any) -> None:
    conn.execute(
        sql.SQL(
            """
            INSERT INTO {}.knowledge_spaces (space_id, created_at)
            VALUES (%s, %s)
            ON CONFLICT (space_id) DO NOTHING
            """
        ).format(sql.Identifier(SCHEMA)),
        (space_id, created_at),
    )
    row = conn.execute(
        sql.SQL(
            """
            SELECT space_id
            FROM {}.knowledge_spaces
            WHERE space_id = %s
            FOR UPDATE
            """
        ).format(sql.Identifier(SCHEMA)),
        (space_id,),
    ).fetchone()
    if row is None:
        raise PersistenceIntegrityError(f"knowledge space {space_id!r} missing after lock")


def _read_head(conn: Connection[Any], space_id: str) -> KnowledgeHead | None:
    row = conn.execute(
        sql.SQL(
            """
            SELECT space_id, head_revision_id, updated_at, schema_version
            FROM {}.knowledge_heads
            WHERE space_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (space_id,),
    ).fetchone()
    if row is None:
        return None
    head = KnowledgeHead(
        space_id=row["space_id"],
        head_revision_id=row["head_revision_id"],
        updated_at=row["updated_at"],
    )
    if row["schema_version"] != head.schema_version:
        raise PersistenceIntegrityError("knowledge head schema_version drift")
    return head


def _read_revision(
    conn: Connection[Any], space_id: str, revision_id: str
) -> StoredKnowledgeRevision | None:
    row = conn.execute(
        sql.SQL(
            f"""
            SELECT {_REVISION_SELECT}
            FROM {{}}.knowledge_revisions
            WHERE space_id = %s AND revision_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (space_id, revision_id),
    ).fetchone()
    if row is None:
        return None
    return _reconstruct(row)


def _insert_revision(conn: Connection[Any], stored: StoredKnowledgeRevision) -> None:
    revision = stored.revision
    payload = stored.graph_payload
    envelope = revision.model_dump(mode="json")
    fingerprint = canonical_sha256({"graph_payload": payload, "revision": envelope})
    conn.execute(
        sql.SQL(
            """
            INSERT INTO {}.knowledge_revisions (
                space_id,
                revision_id,
                parent_revision_id,
                created_at,
                graph_schema,
                graph_payload_sha256,
                schema_version,
                record_fingerprint,
                revision_payload,
                graph_payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
        ).format(sql.Identifier(SCHEMA)),
        (
            revision.space_id,
            revision.revision_id,
            revision.parent_revision_id,
            revision.created_at,
            revision.graph_schema,
            revision.graph_payload_sha256,
            revision.schema_version,
            fingerprint,
            jsonb(envelope),
            jsonb(payload),
        ),
    )


def _advance_head(conn: Connection[Any], head: KnowledgeHead, event: KnowledgeHeadEvent) -> None:
    conn.execute(
        sql.SQL(
            """
            INSERT INTO {}.knowledge_heads (
                space_id, head_revision_id, updated_at, schema_version
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (space_id) DO UPDATE SET
                head_revision_id = EXCLUDED.head_revision_id,
                updated_at = EXCLUDED.updated_at,
                schema_version = EXCLUDED.schema_version
            """
        ).format(sql.Identifier(SCHEMA)),
        (head.space_id, head.head_revision_id, head.updated_at, head.schema_version),
    )
    if event.event_kind != "publish":
        raise PersistenceIntegrityError("V5.2 head events are publish only")
    conn.execute(
        sql.SQL(
            """
            INSERT INTO {}.knowledge_head_events (
                space_id, event_kind, previous_revision_id,
                target_revision_id, occurred_at
            ) VALUES (%s, %s, %s, %s, %s)
            """
        ).format(sql.Identifier(SCHEMA)),
        (
            event.space_id, event.event_kind, event.previous_revision_id,
            event.target_revision_id, event.occurred_at,
        ),
    )


def _read_receipt(
    conn: Connection[Any], space_id: str, publication_id: str
) -> KnowledgePublicationReceipt | None:
    row = conn.execute(
        sql.SQL(
            """
            SELECT schema_version, space_id, publication_id, command_sha256,
                   expected_parent_revision_id, published_revision_id,
                   graph_payload_sha256, status, record_fingerprint
            FROM {}.knowledge_publication_receipts
            WHERE space_id = %s AND publication_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (space_id, publication_id),
    ).fetchone()
    if row is None:
        return None
    fingerprint = row["record_fingerprint"]
    receipt_data = dict(row)
    receipt_data.pop("record_fingerprint", None)
    try:
        receipt = KnowledgePublicationReceipt.model_validate(receipt_data)
    except Exception as exc:
        raise PersistenceIntegrityError(
            f"failed to reconstruct publication receipt: {exc}"
        ) from exc
    expected_fingerprint = canonical_sha256(receipt.model_dump(mode="json"))
    if expected_fingerprint != fingerprint:
        raise PersistenceIntegrityError("publication receipt fingerprint drift")
    return receipt


def _insert_receipt(conn: Connection[Any], receipt: KnowledgePublicationReceipt) -> None:
    payload = receipt.model_dump(mode="json")
    fingerprint = canonical_sha256(payload)
    conn.execute(
        sql.SQL(
            """
            INSERT INTO {}.knowledge_publication_receipts (
                schema_version, space_id, publication_id, command_sha256,
                expected_parent_revision_id, published_revision_id,
                graph_payload_sha256, status, record_fingerprint
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
        ).format(sql.Identifier(SCHEMA)),
        (
            receipt.schema_version, receipt.space_id, receipt.publication_id,
            receipt.command_sha256, receipt.expected_parent_revision_id,
            receipt.published_revision_id, receipt.graph_payload_sha256,
            receipt.status, fingerprint,
        ),
    )
def _reconstruct(row: dict[str, Any]) -> StoredKnowledgeRevision:
    try:
        revision = KnowledgeRevision.model_validate(row["revision_payload"])
    except Exception as exc:
        raise PersistenceIntegrityError(f"failed to reconstruct KnowledgeRevision: {exc}") from exc
    payload = row["graph_payload"]
    if not isinstance(payload, dict):
        raise PersistenceIntegrityError("knowledge revision graph_payload is not an object")
    fingerprint = canonical_sha256(
        {"graph_payload": payload, "revision": revision.model_dump(mode="json")}
    )
    if fingerprint != row["record_fingerprint"]:
        raise PersistenceIntegrityError("knowledge revision record_fingerprint drift")
    if revision.space_id != row["space_id"] or revision.revision_id != row["revision_id"]:
        raise PersistenceIntegrityError("knowledge revision identity column drift")
    if revision.parent_revision_id != row["parent_revision_id"]:
        raise PersistenceIntegrityError("knowledge revision parent column drift")
    if revision.graph_schema != row["graph_schema"]:
        raise PersistenceIntegrityError("knowledge revision graph_schema column drift")
    if revision.graph_payload_sha256 != row["graph_payload_sha256"]:
        raise PersistenceIntegrityError("knowledge revision payload hash column drift")
    if revision.schema_version != row["schema_version"]:
        raise PersistenceIntegrityError("knowledge revision schema_version column drift")
    if _normalize(revision.created_at) != _normalize(row["created_at"]):
        raise PersistenceIntegrityError("knowledge revision created_at column drift")
    if canonical_sha256(payload) != revision.graph_payload_sha256:
        raise PersistenceIntegrityError("stored graph payload hash mismatch")
    stored = StoredKnowledgeRevision(
        revision=revision,
        graph_payload_sha256=revision.graph_payload_sha256,
        _payload_json=canonical_json(payload),
    )
    verify_stored_revision(stored)
    expected = revision_from_command(
        PublishKnowledgeRevisionCommand(
            space_id=revision.space_id,
            parent_revision_id=revision.parent_revision_id,
            expected_parent_revision_id=revision.parent_revision_id,
            operation_ids=list(revision.operation_ids),
            graph_schema=revision.graph_schema,
            graph_payload=payload,
            domain_contract_ref=revision.domain_contract_ref,
            semantic_profile_ref=revision.semantic_profile_ref,
            migration_origin_ref=revision.migration_origin_ref,
            created_at=revision.created_at,
        )
    )
    if expected.revision_id != revision.revision_id:
        raise PersistenceIntegrityError("recomputed native revision id disagrees with stored id")
    return stored
