"""PostgreSQL adapter for MindThreadRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from psycopg import sql

from ...contracts.mind_turn import MindTurnRequest, MindTurnResponse
from ...domain.canonical import canonical_sha256
from ...domain.errors import (
    DocumentNotFoundError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
    ThreadContextMismatchError,
)
from .database import SCHEMA, PostgresDatabase, jsonb
from .evidence_extract import upsert_evidence_refs
from .serialization import dump_payload, model_fingerprint, reconstruct


def _binding_fingerprint(
    *,
    world_id: str,
    campaign_id: str | None,
    caller_id: str,
    tenant_id: str | None,
    created_at: datetime,
) -> str:
    binding = {
        "world_id": world_id,
        "campaign_id": campaign_id,
        "caller_id": caller_id,
        "tenant_id": tenant_id,
        "created_at": created_at.astimezone(UTC).isoformat(),
    }
    return canonical_sha256(binding)


_BINDING_SELECT = """
    world_id, campaign_id, caller_id, tenant_id, created_at, binding_fingerprint
"""


def _verify_binding_row(row: dict[str, Any], *, thread_id: str) -> dict[str, Any]:
    """Fail closed if extracted binding columns disagree with binding_fingerprint."""
    recomputed = _binding_fingerprint(
        world_id=row["world_id"],
        campaign_id=row["campaign_id"],
        caller_id=row["caller_id"],
        tenant_id=row["tenant_id"],
        created_at=row["created_at"],
    )
    if recomputed != row["binding_fingerprint"]:
        raise PersistenceIntegrityError(
            f"thread {thread_id!r} binding columns disagree with binding_fingerprint"
        )
    return row


class PostgresMindThreadRepository:
    """Caller-private, cross-surface threads with the same invariants as memory."""

    def __init__(self, database: PostgresDatabase) -> None:
        self._db = database

    def create_thread(
        self,
        thread_id: str,
        *,
        world_id: str,
        campaign_id: str | None,
        caller_id: str,
        tenant_id: str | None,
        created_at: datetime,
    ) -> str:
        fingerprint = _binding_fingerprint(
            world_id=world_id,
            campaign_id=campaign_id,
            caller_id=caller_id,
            tenant_id=tenant_id,
            created_at=created_at,
        )
        with self._db.transaction() as conn:
            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.mind_threads (
                        thread_id,
                        world_id,
                        campaign_id,
                        caller_id,
                        tenant_id,
                        created_at,
                        binding_fingerprint
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (thread_id) DO NOTHING
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    thread_id,
                    world_id,
                    campaign_id,
                    caller_id,
                    tenant_id,
                    created_at,
                    fingerprint,
                ),
            )
            existing = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_BINDING_SELECT}
                    FROM {{}}.mind_threads
                    WHERE thread_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (thread_id,),
            ).fetchone()
            if existing is None:
                raise PersistenceIntegrityError(
                    f"thread {thread_id!r} missing after insert/reconcile"
                )
            verified = _verify_binding_row(existing, thread_id=thread_id)
            if verified["binding_fingerprint"] != fingerprint:
                raise IdempotencyConflictError(
                    f"thread {thread_id!r} already bound with different context"
                )
            return thread_id

    def append_turn(self, request: MindTurnRequest, response: MindTurnResponse) -> None:
        request_fp = model_fingerprint(request)
        response_fp = model_fingerprint(response)
        with self._db.transaction() as conn:
            binding = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_BINDING_SELECT}
                    FROM {{}}.mind_threads
                    WHERE thread_id = %s
                    FOR UPDATE
                    """
                ).format(sql.Identifier(SCHEMA)),
                (request.thread_id,),
            ).fetchone()
            if binding is None:
                raise DocumentNotFoundError(f"thread {request.thread_id!r} not found")
            binding = _verify_binding_row(binding, thread_id=request.thread_id)
            if request.world_id != binding["world_id"]:
                raise ThreadContextMismatchError(
                    f"request world_id {request.world_id!r} != thread world "
                    f"{binding['world_id']!r}"
                )
            if request.campaign_id != binding["campaign_id"]:
                raise ThreadContextMismatchError(
                    f"request campaign_id {request.campaign_id!r} != thread campaign "
                    f"{binding['campaign_id']!r}"
                )
            if request.caller_scope.tenant_id != binding["tenant_id"]:
                raise ThreadContextMismatchError(
                    f"request tenant_id {request.caller_scope.tenant_id!r} != thread tenant "
                    f"{binding['tenant_id']!r}"
                )
            if request.caller_scope.caller_id != binding["caller_id"]:
                raise ThreadContextMismatchError(
                    f"request caller_id {request.caller_scope.caller_id!r} != thread caller "
                    f"{binding['caller_id']!r}"
                )
            if response.request_id != request.request_id:
                raise ThreadContextMismatchError(
                    f"response.request_id {response.request_id!r} != "
                    f"request.request_id {request.request_id!r}"
                )
            if response.thread_id != request.thread_id:
                raise ThreadContextMismatchError(
                    f"response.thread_id {response.thread_id!r} != "
                    f"request.thread_id {request.thread_id!r}"
                )
            if response.world_id != request.world_id:
                raise ThreadContextMismatchError(
                    f"response.world_id {response.world_id!r} != "
                    f"request.world_id {request.world_id!r}"
                )
            if response.campaign_id != request.campaign_id:
                raise ThreadContextMismatchError(
                    f"response.campaign_id {response.campaign_id!r} != "
                    f"request.campaign_id {request.campaign_id!r}"
                )

            conflicts = conn.execute(
                sql.SQL(
                    """
                    SELECT
                        turn_id,
                        request_id,
                        request_fingerprint,
                        response_fingerprint,
                        request_payload,
                        response_payload
                    FROM {}.mind_turns
                    WHERE thread_id = %s
                      AND (turn_id = %s OR request_id = %s)
                    """
                ).format(sql.Identifier(SCHEMA)),
                (request.thread_id, response.turn_id, request.request_id),
            ).fetchall()
            for row in conflicts:
                if row["turn_id"] == response.turn_id:
                    if (
                        row["request_fingerprint"] == request_fp
                        and row["response_fingerprint"] == response_fp
                    ):
                        # Reconstruct before accepting exact replay so corrupted
                        # JSONB cannot be silently blessed by fingerprint match.
                        _row_to_turn_pair(row, thread_id=request.thread_id)
                        upsert_evidence_refs(conn, response.evidence)
                        return
                    raise IdempotencyConflictError(
                        f"turn_id {response.turn_id!r} replayed with different payload"
                    )
                if row["request_id"] == request.request_id:
                    raise IdempotencyConflictError(
                        f"request_id {request.request_id!r} already bound to a different turn"
                    )

            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.mind_turns (
                        thread_id,
                        turn_id,
                        request_id,
                        request_fingerprint,
                        response_fingerprint,
                        request_payload,
                        response_payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    request.thread_id,
                    response.turn_id,
                    request.request_id,
                    request_fp,
                    response_fp,
                    jsonb(dump_payload(request)),
                    jsonb(dump_payload(response)),
                ),
            )
            upsert_evidence_refs(conn, response.evidence)

    def list_turns(
        self, thread_id: str
    ) -> list[tuple[MindTurnRequest, MindTurnResponse]]:
        with self._db.transaction() as conn:
            thread = conn.execute(
                sql.SQL(
                    f"""
                    SELECT {_BINDING_SELECT}
                    FROM {{}}.mind_threads
                    WHERE thread_id = %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (thread_id,),
            ).fetchone()
            if thread is None:
                return []
            _verify_binding_row(thread, thread_id=thread_id)
            rows = conn.execute(
                sql.SQL(
                    """
                    SELECT
                        turn_id,
                        request_id,
                        request_fingerprint,
                        response_fingerprint,
                        request_payload,
                        response_payload
                    FROM {}.mind_turns
                    WHERE thread_id = %s
                    ORDER BY ordinal ASC
                    """
                ).format(sql.Identifier(SCHEMA)),
                (thread_id,),
            ).fetchall()
            return [_row_to_turn_pair(row, thread_id=thread_id) for row in rows]


def _row_to_turn_pair(
    row: dict[str, Any], *, thread_id: str
) -> tuple[MindTurnRequest, MindTurnResponse]:
    request = reconstruct(
        MindTurnRequest,
        dict(row["request_payload"]),
        expected_fingerprint=row["request_fingerprint"],
        identity={"request_id": row["request_id"], "thread_id": thread_id},
    )
    response = reconstruct(
        MindTurnResponse,
        dict(row["response_payload"]),
        expected_fingerprint=row["response_fingerprint"],
        identity={"turn_id": row["turn_id"], "thread_id": thread_id},
    )
    return request, response
