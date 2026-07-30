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
from .serialization import dump_payload, model_fingerprint, reconstruct


class PostgresWorldGraphRepository:
    """Immutable revisions + one head per world, published by atomic CAS."""

    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database

    def get_head(self, world_id: str) -> WorldGraphHead | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    """
                    SELECT world_id, head_revision_id, updated_at, schema_version
                    FROM {}.world_graph_heads
                    WHERE world_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id,),
            ).fetchone()
        if row is None:
            return None
        head = WorldGraphHead(
            world_id=row["world_id"],
            head_revision_id=row["head_revision_id"],
            updated_at=row["updated_at"],
        )
        return head.model_copy(deep=True)

    def get_revision(self, world_id: str, revision_id: str) -> StoredGraphRevision | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    """
                    SELECT
                        world_id,
                        revision_id,
                        parent_revision_id,
                        graph_schema,
                        record_fingerprint,
                        revision_payload,
                        graph_payload
                    FROM {}.graph_revisions
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
                    """
                    SELECT head_revision_id
                    FROM {}.world_graph_heads
                    WHERE world_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (command.world_id,),
            ).fetchone()
            current_head_id = head_row["head_revision_id"] if head_row else None

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
                    """
                    SELECT
                        graph_payload_sha256,
                        record_fingerprint,
                        revision_payload,
                        graph_payload
                    FROM {}.graph_revisions
                    WHERE world_id = %s AND revision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (command.world_id, revision_id),
            ).fetchone()

            if existing_row is not None:
                if existing_row["graph_payload_sha256"] != payload_hash:
                    raise ImmutableRevisionConflictError(
                        f"revision {revision_id!r} already exists with different payload"
                    )
                stored = _reconstruct_stored_revision(
                    {
                        **existing_row,
                        "world_id": command.world_id,
                        "revision_id": revision_id,
                        "parent_revision_id": command.parent_revision_id,
                        "graph_schema": command.graph_schema,
                    }
                )
                if model_fingerprint(stored) != existing_row["record_fingerprint"]:
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

            revision_row = conn.execute(
                sql.SQL(
                    """
                    SELECT revision_id
                    FROM {}.graph_revisions
                    WHERE world_id = %s AND revision_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id, target_revision_id),
            ).fetchone()
            if revision_row is None:
                raise RevisionNotFoundError(
                    f"revision {target_revision_id!r} does not exist for world {world_id!r}"
                )

            head_row = conn.execute(
                sql.SQL(
                    """
                    SELECT head_revision_id
                    FROM {}.world_graph_heads
                    WHERE world_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (world_id,),
            ).fetchone()
            previous_revision_id = head_row["head_revision_id"] if head_row else None

            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.world_graph_heads (
                        world_id, head_revision_id, updated_at, schema_version
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (world_id) DO UPDATE SET
                        head_revision_id = EXCLUDED.head_revision_id,
                        updated_at = EXCLUDED.updated_at
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
                updated_at = EXCLUDED.updated_at
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
    return stored.model_copy(deep=True)
