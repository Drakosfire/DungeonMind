"""Transactional evidence_ref extraction shared by parent-record adapters.

Bounded discovery helper: used by records.py and threads.py. Not a public port.
"""

from __future__ import annotations

from typing import Any

from psycopg import Connection, sql

from ...contracts.evidence import EvidenceRef
from ...domain.errors import IdempotencyConflictError
from .database import SCHEMA, jsonb
from .serialization import dump_payload, model_fingerprint, reconstruct


def upsert_evidence_refs(conn: Connection[Any], evidence: list[EvidenceRef]) -> None:
    """Persist evidence refs with exact-replay idempotency; commit with the parent."""
    for item in evidence:
        fingerprint = model_fingerprint(item)
        payload = dump_payload(item)
        existing = conn.execute(
            sql.SQL(
                """
                SELECT record_fingerprint, payload
                FROM {}.evidence_refs
                WHERE evidence_ref_id = %s
                FOR UPDATE
                """
            ).format(sql.Identifier(SCHEMA)),
            (item.evidence_ref_id,),
        ).fetchone()
        if existing is not None:
            if existing["record_fingerprint"] != fingerprint:
                raise IdempotencyConflictError(
                    f"evidence_ref {item.evidence_ref_id!r} replayed with different payload"
                )
            reconstruct(
                EvidenceRef,
                dict(existing["payload"]),
                expected_fingerprint=existing["record_fingerprint"],
                identity={"evidence_ref_id": item.evidence_ref_id},
            )
            continue
        conn.execute(
            sql.SQL(
                """
                INSERT INTO {}.evidence_refs (
                    evidence_ref_id,
                    source_artifact_id,
                    source_revision_id,
                    source_domain,
                    evidence_role,
                    schema_version,
                    record_fingerprint,
                    payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
            ).format(sql.Identifier(SCHEMA)),
            (
                item.evidence_ref_id,
                item.source_artifact_id,
                item.source_revision_id,
                item.source_domain.value,
                item.evidence_role.value,
                item.schema_version,
                fingerprint,
                jsonb(payload),
            ),
        )


def collect_evidence_from_contribution_payload(contribution: Any) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    seen: set[str] = set()
    for assertion in getattr(contribution, "assertions", []) or []:
        for ref in getattr(assertion, "evidence_refs", []) or []:
            if ref.evidence_ref_id in seen:
                continue
            seen.add(ref.evidence_ref_id)
            refs.append(ref)
    return refs
