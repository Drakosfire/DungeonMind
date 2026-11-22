"""Typed exact citation proofs derived from verified native publication records."""

from collections.abc import Sequence
from hashlib import sha256
from struct import pack
from typing import Any, Literal

from psycopg import Connection

from dungeonmind.contracts.vnext.native_source import NativeUtf8SpanProofV1
from dungeonmind.contracts.vnext.publication import KnowledgePublicationReceipt
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

ReceiptKind = Literal["admission", "extension", "publication"]


def proof_fingerprint(proof: NativeUtf8SpanProofV1) -> str:
    """Seal the typed fields with a versioned, length-delimited encoding."""
    digest = sha256(b"dungeonmind/native-citation-proof/v1\x00")
    for value in (
        proof.span_id, proof.source_revision_id, proof.evidence_ref_id, proof.slice_sha256,
    ):
        encoded = value.encode("utf-8")
        digest.update(pack(">I", len(encoded)))
        digest.update(encoded)
    digest.update(pack(">QQ", proof.start_byte, proof.end_byte))
    return digest.hexdigest()


def insert_citation_manifest(
    conn: Connection[Any],
    *,
    kind: ReceiptKind,
    admission_id: str,
    source_artifact_id: str,
    source_revision_id: str,
    authority_epoch: int,
    receipt_fingerprint: str,
    publication: KnowledgePublicationReceipt,
    proofs: Sequence[NativeUtf8SpanProofV1],
) -> None:
    span_ids = [proof.span_id for proof in proofs]
    if len(set(span_ids)) != len(span_ids) or any(
        proof.source_revision_id != source_revision_id for proof in proofs
    ):
        raise PersistenceIntegrityError("native citation manifest proof identity drift")
    # An independent membership list lets the reader distinguish a missing proof
    # row from a key that never belonged to this publication.
    conn.execute(
        """
        INSERT INTO dungeonmind.native_citation_manifests (
            space_id, receipt_id, kind, admission_id, source_artifact_id,
            source_revision_id, authority_epoch, receipt_fingerprint,
            publication_fingerprint, span_ids, span_fingerprints
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            publication.space_id, publication.publication_id, kind, admission_id,
            source_artifact_id, source_revision_id, authority_epoch, receipt_fingerprint,
            canonical_sha256(publication.model_dump(mode="json")), span_ids,
            [proof_fingerprint(proof) for proof in proofs],
        ),
    )
    if proofs:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO dungeonmind.native_citation_proofs (
                    space_id, receipt_id, span_id, evidence_ref_id, source_revision_id,
                    start_byte, end_byte, slice_sha256
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        publication.space_id, publication.publication_id, proof.span_id,
                        proof.evidence_ref_id, source_revision_id, proof.start_byte,
                        proof.end_byte, proof.slice_sha256,
                    )
                    for proof in proofs
                ],
            )


def read_citation_proofs(
    conn: Connection[Any],
    space_id: str,
    epoch: int,
    keys: Sequence[tuple[str, str, str]],
) -> dict[tuple[str, str, str], tuple[NativeUtf8SpanProofV1, int]]:
    artifacts, revisions, spans = map(list, zip(*keys, strict=True))
    # Reconcile the scoped manifest set with the canonical receipt identities.
    # Neither branch selects the canonical JSON, even for an unresolved key.
    rows = conn.execute(
        """
        WITH requested AS (
            SELECT * FROM unnest(%s::text[], %s::text[], %s::text[])
                AS keys(artifact_id, revision_id, span_id)
        ), pairs AS (
            SELECT DISTINCT artifact_id, revision_id FROM requested
        ), scope AS (
            SELECT %s::text AS space_id, %s::bigint AS epoch
        ), authority AS (
            SELECT a.admission_id AS receipt_id, 'admission' AS kind, a.admission_id,
                   a.source_artifact_id, a.source_revision_id, a.source_authority_epoch AS epoch,
                   a.record_fingerprint
            FROM dungeonmind.knowledge_native_source_admissions a
            JOIN pairs p ON (a.source_artifact_id, a.source_revision_id) =
                            (p.artifact_id, p.revision_id)
            JOIN scope s ON s.space_id = a.space_id AND a.source_authority_epoch <= s.epoch
            UNION ALL
            SELECT e.extension_id, 'extension', e.original_admission_id,
                   e.source_artifact_id, e.source_revision_id, e.source_authority_epoch,
                   e.record_fingerprint
            FROM dungeonmind.knowledge_native_source_extensions e
            JOIN pairs p ON (e.source_artifact_id, e.source_revision_id) =
                            (p.artifact_id, p.revision_id)
            JOIN scope s ON s.space_id = e.space_id AND e.source_authority_epoch <= s.epoch
            UNION ALL
            SELECT r.publication_id, 'publication', r.original_admission_id,
                   r.source_artifact_id, r.source_revision_id, r.source_authority_epoch_after,
                   r.record_fingerprint
            FROM dungeonmind.knowledge_native_source_publications r
            JOIN pairs p ON (r.source_artifact_id, r.source_revision_id) =
                            (p.artifact_id, p.revision_id)
            JOIN scope s ON s.space_id = r.space_id AND r.source_authority_epoch_after <= s.epoch
            WHERE r.mode = 'new_intervals'
        ), manifests AS (
            SELECT m.*
            FROM dungeonmind.native_citation_manifests m
            JOIN pairs p ON (m.source_artifact_id, m.source_revision_id) =
                            (p.artifact_id, p.revision_id)
            JOIN scope s ON s.space_id = m.space_id AND m.authority_epoch <= s.epoch
            WHERE cardinality(m.span_ids) > 0
        ), checked AS (
            SELECT m.space_id, m.receipt_id, m.authority_epoch, m.span_ids, m.span_fingerprints,
                   COALESCE(m.source_artifact_id, a.source_artifact_id) AS artifact_id,
                   COALESCE(m.source_revision_id, a.source_revision_id) AS revision_id,
                   (
                       m.intact AND
                       (m.kind, m.admission_id, m.source_artifact_id, m.source_revision_id,
                        m.authority_epoch, m.receipt_fingerprint, m.publication_fingerprint)
                       = (a.kind, a.admission_id, a.source_artifact_id, a.source_revision_id,
                          a.epoch, a.record_fingerprint, p.record_fingerprint)
                   ) IS TRUE AS valid
            FROM authority a FULL JOIN manifests m USING (receipt_id)
            LEFT JOIN dungeonmind.knowledge_publication_receipts p
                ON (p.space_id, p.publication_id) = (m.space_id, m.receipt_id)
        )
        SELECT c.valid, c.authority_epoch, k.artifact_id, k.revision_id, k.span_id,
               c.span_fingerprints[array_position(c.span_ids, k.span_id)] AS fingerprint,
               p.source_revision_id, p.evidence_ref_id, p.start_byte, p.end_byte, p.slice_sha256
        FROM checked c
        JOIN requested k USING (artifact_id, revision_id)
        LEFT JOIN dungeonmind.native_citation_proofs p
            ON (p.space_id, p.receipt_id, p.span_id) = (c.space_id, c.receipt_id, k.span_id)
        WHERE NOT c.valid OR k.span_id = ANY(c.span_ids) OR p.span_id IS NOT NULL
        """,
        (artifacts, revisions, spans, space_id, epoch),
    ).fetchall()
    resolved: dict[tuple[str, str, str], tuple[NativeUtf8SpanProofV1, int]] = {}
    for row in rows:
        if not row["valid"]:
            raise PersistenceIntegrityError("native source span index drift: unverified manifest")
        key = row["artifact_id"], row["revision_id"], row["span_id"]
        try:
            proof = NativeUtf8SpanProofV1(
                span_id=row["span_id"],
                source_revision_id=row["source_revision_id"],
                evidence_ref_id=row["evidence_ref_id"],
                start_byte=row["start_byte"],
                end_byte=row["end_byte"],
                slice_sha256=row["slice_sha256"],
            )
        except (ValueError, TypeError) as exc:
            raise PersistenceIntegrityError(
                "native source span index drift: invalid proof row"
            ) from exc
        if (
            proof.source_revision_id != row["revision_id"]
            or proof_fingerprint(proof) != row["fingerprint"]
            or key in resolved
        ):
            raise PersistenceIntegrityError(
                "native source span index drift: proof identity mismatch"
            )
        resolved[key] = proof, row["authority_epoch"]
    return resolved
