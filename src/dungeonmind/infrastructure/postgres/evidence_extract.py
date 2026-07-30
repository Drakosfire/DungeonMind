"""Transactional evidence_ref extraction shared by parent-record adapters.

Bounded discovery helper: used by records.py and threads.py. Not a public port.
"""

from __future__ import annotations

from typing import Any

from psycopg import Connection, sql

from ...contracts.evidence import EvidenceRef
from ...domain.errors import IdempotencyConflictError, PersistenceIntegrityError
from .database import SCHEMA, jsonb
from .serialization import dump_payload, model_fingerprint, reconstruct


def upsert_evidence_refs(conn: Connection[Any], evidence: list[EvidenceRef]) -> None:
    """Persist evidence refs with atomic insert/reconcile idempotency."""
    for item in evidence:
        fingerprint = model_fingerprint(item)
        payload = dump_payload(item)
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
                ON CONFLICT (evidence_ref_id) DO NOTHING
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
        existing = conn.execute(
            sql.SQL(
                """
                SELECT
                    evidence_ref_id,
                    source_artifact_id,
                    source_revision_id,
                    source_domain,
                    evidence_role,
                    schema_version,
                    record_fingerprint,
                    payload
                FROM {}.evidence_refs
                WHERE evidence_ref_id = %s
                """
            ).format(sql.Identifier(SCHEMA)),
            (item.evidence_ref_id,),
        ).fetchone()
        if existing is None:
            raise PersistenceIntegrityError(
                f"evidence_ref {item.evidence_ref_id!r} missing after insert/reconcile"
            )
        if existing["record_fingerprint"] != fingerprint:
            raise IdempotencyConflictError(
                f"evidence_ref {item.evidence_ref_id!r} replayed with different payload"
            )
        reconstruct(
            EvidenceRef,
            dict(existing["payload"]),
            expected_fingerprint=existing["record_fingerprint"],
            identity={
                "evidence_ref_id": existing["evidence_ref_id"],
                "source_artifact_id": existing["source_artifact_id"],
                "source_revision_id": existing["source_revision_id"],
                "source_domain": existing["source_domain"],
                "evidence_role": existing["evidence_role"],
                "schema_version": existing["schema_version"],
            },
        )


def collect_evidence_from_contribution_payload(contribution: Any) -> list[EvidenceRef]:
    """Deduplicate evidence IDs across assertions; reject conflicting duplicates."""
    by_id: dict[str, EvidenceRef] = {}
    ordered: list[EvidenceRef] = []
    for assertion in getattr(contribution, "assertions", []) or []:
        for ref in getattr(assertion, "evidence_refs", []) or []:
            prior = by_id.get(ref.evidence_ref_id)
            if prior is not None:
                if model_fingerprint(prior) != model_fingerprint(ref):
                    raise IdempotencyConflictError(
                        f"contribution embeds conflicting evidence_ref "
                        f"{ref.evidence_ref_id!r}"
                    )
                continue
            by_id[ref.evidence_ref_id] = ref
            ordered.append(ref)
    return ordered
