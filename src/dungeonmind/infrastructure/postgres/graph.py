"""PostgreSQL World Graph repository — immutable revisions + atomic head CAS."""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from psycopg import Connection, sql

from ...contracts.graph import (
    GRAPH_HEAD_SCHEMA,
    PublishRevisionCommand,
    StoredGraphRevision,
    WorldGraphHead,
    WorldGraphRevision,
)
from ...domain.canonical import canonical_sha256
from ...domain.errors import (
    ImmutableRevisionConflictError,
    PersistenceIntegrityError,
    RevisionNotFoundError,
    StaleParentRevisionError,
)
from ...domain.revision_ids import compute_revision_id
from .database import SCHEMA, PostgresDatabase, jsonb, lock_world
from .serialization import _normalize, dump_payload, model_fingerprint, reconstruct

_REVISION_SELECT = """
    world_id,
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

_HEAD_SELECT = "world_id, head_revision_id, updated_at, schema_version"


class PostgresWorldGraphRepository:
    """Immutable revisions + one head per world, published by atomic CAS."""

    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def get_head(self, world_id: str) -> WorldGraphHead | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_HEAD_SELECT}
                    FROM {{}}.world_graph_heads
                    WHERE world_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id,),
            ).fetchone()
        if row is None:
            return None
        return _head_from_row(row).model_copy(deep=True)

    def get_revision(self, world_id: str, revision_id: str) -> StoredGraphRevision | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_REVISION_SELECT}
                    FROM {{}}.graph_revisions
                    WHERE world_id = %s AND revision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id, revision_id),
            ).fetchone()
        if row is None:
            return None
        return _reconstruct_stored_revision(row)

    def publish_revision(self, command: PublishRevisionCommand) -> WorldGraphRevision:
        payload_hash = canonical_sha256(command.graph_payload)
        revision_id = compute_revision_id(
            world_id=command.world_id,
            parent_revision_id=command.parent_revision_id,
            operation_ids=command.operation_ids,
            graph_schema=command.graph_schema,
            graph_payload_sha256=payload_hash,
        )
        with self._database.transaction() as conn:
            lock_world(conn, command.world_id, created_at=command.created_at)

            head_row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_HEAD_SELECT}
                    FROM {{}}.world_graph_heads
                    WHERE world_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (command.world_id,),
            ).fetchone()
            if head_row is None:
                current_head_id = None
            else:
                current_head_id = _head_from_row(head_row).head_revision_id

            if command.expected_parent_revision_id != current_head_id:
                raise StaleParentRevisionError(
                    world_id=command.world_id,
                    expected_parent_revision_id=command.expected_parent_revision_id,
                    actual_head_revision_id=current_head_id,
                )
            if command.parent_revision_id != current_head_id:
                raise StaleParentRevisionError(
                    world_id=command.world_id,
                    expected_parent_revision_id=command.parent_revision_id,
                    actual_head_revision_id=current_head_id,
                )

            existing_row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_REVISION_SELECT}
                    FROM {{}}.graph_revisions
                    WHERE world_id = %s AND revision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (command.world_id, revision_id),
            ).fetchone()

            if existing_row is not None:
                # Reconstruct first so column/payload corruption fails closed as
                # PersistenceIntegrityError, not ImmutableRevisionConflictError.
                stored = _reconstruct_stored_revision(existing_row)
                if stored.revision.graph_payload_sha256 != payload_hash:
                    raise ImmutableRevisionConflictError(
                        f"revision {revision_id!r} already exists with different payload"
                    )
                _upsert_head(
                    conn,
                    world_id=command.world_id,
                    head_revision_id=revision_id,
                    updated_at=command.created_at,
                    previous_revision_id=current_head_id,
                )
                return stored.revision.model_copy(deep=True)

            envelope = WorldGraphRevision(
                world_id=command.world_id,
                revision_id=revision_id,
                parent_revision_id=command.parent_revision_id,
                created_at=command.created_at,
                operation_ids=list(command.operation_ids),
                graph_schema=command.graph_schema,
                graph_payload_sha256=payload_hash,
            )
            frozen_payload = copy.deepcopy(command.graph_payload)
            stored = StoredGraphRevision(revision=envelope, graph_payload=frozen_payload)
            fingerprint = model_fingerprint(stored)

            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.graph_revisions (
                        world_id,
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
                    command.world_id,
                    revision_id,
                    command.parent_revision_id,
                    command.created_at,
                    command.graph_schema,
                    payload_hash,
                    envelope.schema_version,
                    fingerprint,
                    jsonb(dump_payload(envelope)),
                    jsonb(frozen_payload),
                ),
            )
            _upsert_head(
                conn,
                world_id=command.world_id,
                head_revision_id=revision_id,
                updated_at=command.created_at,
                previous_revision_id=current_head_id,
            )
            return envelope.model_copy(deep=True)

    def rollback_head(
        self, world_id: str, target_revision_id: str, *, updated_at: datetime
    ) -> WorldGraphHead:
        with self._database.transaction() as conn:
            lock_world(conn, world_id, created_at=updated_at)

            head_row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_HEAD_SELECT}
                    FROM {{}}.world_graph_heads
                    WHERE world_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id,),
            ).fetchone()
            previous_revision_id = (
                None if head_row is None else _head_from_row(head_row).head_revision_id
            )

            revision_row = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_REVISION_SELECT}
                    FROM {{}}.graph_revisions
                    WHERE world_id = %s AND revision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id, target_revision_id),
            ).fetchone()
            if revision_row is None:
                raise RevisionNotFoundError(
                    f"revision {target_revision_id!r} does not exist for world {world_id!r}"
                )
            _reconstruct_stored_revision(revision_row)

            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.world_graph_heads (
                        world_id, head_revision_id, updated_at, schema_version
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (world_id) DO UPDATE SET
                        head_revision_id = EXCLUDED.head_revision_id,
                        updated_at = EXCLUDED.updated_at,
                        schema_version = EXCLUDED.schema_version
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id, target_revision_id, updated_at, GRAPH_HEAD_SCHEMA),
            )
            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.world_graph_head_events (
                        world_id,
                        event_kind,
                        previous_revision_id,
                        target_revision_id,
                        occurred_at
                    ) VALUES (%s, %s, %s, %s, %s)
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id, "rollback", previous_revision_id, target_revision_id, updated_at),
            )

        head = WorldGraphHead(
            world_id=world_id,
            head_revision_id=target_revision_id,
            updated_at=updated_at,
        )
        return head.model_copy(deep=True)


def _head_from_row(row: dict[str, Any]) -> WorldGraphHead:
    head = WorldGraphHead(
        world_id=row["world_id"],
        head_revision_id=row["head_revision_id"],
        updated_at=row["updated_at"],
    )
    if row["schema_version"] != head.schema_version:
        raise PersistenceIntegrityError(
            f"world graph head {row['world_id']!r} schema_version drift "
            f"({row['schema_version']!r} != {head.schema_version!r})"
        )
    return head


def _upsert_head(
    conn: Connection[Any],
    *,
    world_id: str,
    head_revision_id: str,
    updated_at: datetime,
    previous_revision_id: str | None,
) -> None:
    conn.execute(
        sql.SQL(
            """
            INSERT INTO {}.world_graph_heads (
                world_id, head_revision_id, updated_at, schema_version
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (world_id) DO UPDATE SET
                head_revision_id = EXCLUDED.head_revision_id,
                updated_at = EXCLUDED.updated_at,
                schema_version = EXCLUDED.schema_version
            """
        ).format(sql.Identifier(SCHEMA)),
        (world_id, head_revision_id, updated_at, GRAPH_HEAD_SCHEMA),
    )
    conn.execute(
        sql.SQL(
            """
            INSERT INTO {}.world_graph_head_events (
                world_id,
                event_kind,
                previous_revision_id,
                target_revision_id,
                occurred_at
            ) VALUES (%s, %s, %s, %s, %s)
            """
        ).format(sql.Identifier(SCHEMA)),
        (world_id, "publish", previous_revision_id, head_revision_id, updated_at),
    )


def _reconstruct_stored_revision(row: dict[str, Any]) -> StoredGraphRevision:
    payload = {
        "revision": dict(row["revision_payload"]),
        "graph_payload": dict(row["graph_payload"]),
    }
    stored = reconstruct(
        StoredGraphRevision,
        payload,
        expected_fingerprint=row["record_fingerprint"],
        identity={},
    )
    rev = stored.revision
    if rev.world_id != row["world_id"]:
        raise PersistenceIntegrityError(
            f"StoredGraphRevision world_id drift for {row['revision_id']!r}"
        )
    if rev.revision_id != row["revision_id"]:
        raise PersistenceIntegrityError(
            f"StoredGraphRevision revision_id drift for {row['revision_id']!r}"
        )
    if rev.parent_revision_id != row["parent_revision_id"]:
        raise PersistenceIntegrityError(
            f"StoredGraphRevision parent_revision_id drift for {row['revision_id']!r}"
        )
    if rev.graph_schema != row["graph_schema"]:
        raise PersistenceIntegrityError(
            f"StoredGraphRevision graph_schema drift for {row['revision_id']!r}"
        )
    if rev.graph_payload_sha256 != row["graph_payload_sha256"]:
        raise PersistenceIntegrityError(
            f"StoredGraphRevision graph_payload_sha256 drift for {row['revision_id']!r}"
        )
    if rev.schema_version != row["schema_version"]:
        raise PersistenceIntegrityError(
            f"StoredGraphRevision schema_version drift for {row['revision_id']!r}"
        )
    if _normalize(rev.created_at) != _normalize(row["created_at"]):
        raise PersistenceIntegrityError(
            f"StoredGraphRevision created_at drift for {row['revision_id']!r}"
        )
    payload_hash = canonical_sha256(stored.graph_payload)
    if payload_hash != rev.graph_payload_sha256:
        raise PersistenceIntegrityError(
            f"StoredGraphRevision graph_payload hash mismatch for {row['revision_id']!r}"
        )
    return stored.model_copy(deep=True)
