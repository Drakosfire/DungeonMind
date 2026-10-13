"""Transactional evidence_ref extraction shared by parent-record adapters.

Bounded discovery helper: used by records.py and threads.py. Not a public port.
"""

from __future__ import annotations

from typing import Any

from psycopg import Connection, sql

from ...contracts.evidence import (
    EVIDENCE_REF_SCHEMA,
    EVIDENCE_REF_V2_SCHEMA,
    EvidenceRef,
    EvidenceRefV2,
)
from ...domain.errors import IdempotencyConflictError, PersistenceIntegrityError
from .database import SCHEMA, jsonb
from .serialization import dump_payload, model_fingerprint, reconstruct


def _evidence_model(schema_version: str) -> type[EvidenceRef] | type[EvidenceRefV2]:
    if schema_version == EVIDENCE_REF_SCHEMA:
        return EvidenceRef
    if schema_version == EVIDENCE_REF_V2_SCHEMA:
        return EvidenceRefV2
    raise PersistenceIntegrityError(f"unsupported evidence_ref schema {schema_version!r}")


def upsert_evidence_refs(
    conn: Connection[Any], evidence: list[EvidenceRef | EvidenceRefV2]
) -> None:
    """Persist evidence refs with atomic insert/reconcile idempotency."""
    for item in evidence:
        if item.source_domain is None:
            # The existing extraction table requires a classified source domain.
            # Do not coerce a typed V2 domain to OTHER or alter historical schema.
            raise PersistenceIntegrityError(
                f"evidence_ref {item.evidence_ref_id!r} has no extracted source domain"
            )
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
            _evidence_model(existing["schema_version"]),
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


def collect_evidence_from_contribution_payload(
    contribution: Any,
) -> list[EvidenceRef | EvidenceRefV2]:
    """Deduplicate evidence IDs across assertions; reject conflicting duplicates."""
    by_id: dict[str, EvidenceRef | EvidenceRefV2] = {}
    ordered: list[EvidenceRef | EvidenceRefV2] = []
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
