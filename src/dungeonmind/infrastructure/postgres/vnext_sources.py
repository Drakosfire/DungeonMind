"""PostgreSQL atomic native text-source/evidence authority."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from typing import Any

from psycopg import Connection, sql

from dungeonmind.application.vnext.native_source_admission import (
    native_source_command_sha256,
    validate_native_source_write,
)
from dungeonmind.application.vnext.ports import (
    NativeTextSourceView,
    StoredNativeTextSource,
)
from dungeonmind.application.vnext.provenance import (
    KnowledgeProvenanceSnapshot,
    _build_snapshot_from_loaded,
)
from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    SemanticProfileDescriptorV2,
    SemanticProfileDescriptorV3,
)
from dungeonmind.contracts.vnext.knowledge import (
    PublishKnowledgeRevisionCommand,
)
from dungeonmind.contracts.vnext.native_source import (
    NativeSourceAdmissionReceiptV1,
    NativeTextSourceAdmissionBindingV1,
    NativeTextSourceAdmissionV1,
    NativeTextSourceOriginV1,
    NativeUtf8SpanProofV1,
)
from dungeonmind.contracts.vnext.publication import KnowledgePublicationReceipt
from dungeonmind.contracts.vnext.source import SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

from ...application.vnext.authority import commit_expected_parent
from ...application.vnext.errors import (
    KnowledgePublicationIdempotencyConflictError,
    NativeTextSourceAdmissionIntegrityError,
)
from ...application.vnext.records import StoredKnowledgeRevision
from .database import SCHEMA, PostgresDatabase, jsonb
from .vnext_knowledge import (
    PostgresKnowledgeRevisionRepository,
    _advance_head,
    _insert_receipt,
    _insert_revision,
    _lock_space,
    _read_head,
    _read_receipt,
    _read_revision,
)


def _record_fingerprint(
    *,
    artifact: SourceArtifactV3,
    revision: SourceRevisionV2,
    body: bytes,
    proofs: Sequence[NativeUtf8SpanProofV1],
    origin: NativeTextSourceOriginV1 | None,
    receipt: NativeSourceAdmissionReceiptV1,
) -> str:
    return canonical_sha256(
        {
            "artifact": artifact.model_dump(mode="json"),
            "revision": revision.model_dump(mode="json"),
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "proofs": [item.model_dump(mode="json") for item in proofs],
            "origin": None if origin is None else origin.model_dump(mode="json"),
            "receipt": receipt.model_dump(mode="json"),
        }
    )


def _lock_native_epoch(conn: Connection[Any]) -> None:
    row = conn.execute(
        sql.SQL(
            "SELECT epoch FROM {}.knowledge_native_source_authority "
            "WHERE singleton_id = 1 FOR UPDATE"
        ).format(sql.Identifier(SCHEMA))
    ).fetchone()
    if row is None:
        raise PersistenceIntegrityError("native source authority epoch row missing")


def _read_native_record(
    conn: Connection[Any], space_id: str, admission_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        sql.SQL(
            """
            SELECT space_id, admission_id, command_sha256, source_authority_epoch,
                   source_artifact_id, source_revision_id, published_revision_id,
                   source_artifact, source_revision, origin, body_bytes, span_proofs,
                   receipt_payload, record_fingerprint
            FROM {}.knowledge_native_source_admissions
            WHERE space_id = %s AND admission_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (space_id, admission_id),
    ).fetchone()
    if row is None:
        return None
    try:
        artifact = SourceArtifactV3.model_validate(row["source_artifact"])
        revision = SourceRevisionV2.model_validate(row["source_revision"])
        proofs = tuple(NativeUtf8SpanProofV1.model_validate(item) for item in row["span_proofs"])
        origin = (
            None
            if row["origin"] is None
            else NativeTextSourceOriginV1.model_validate(row["origin"])
        )
        receipt = NativeSourceAdmissionReceiptV1.model_validate(row["receipt_payload"])
        body = bytes(row["body_bytes"])
    except Exception as exc:
        raise PersistenceIntegrityError("native source record reconstruction failed") from exc
    expected = _record_fingerprint(
        artifact=artifact,
        revision=revision,
        body=body,
        proofs=proofs,
        origin=origin,
        receipt=receipt,
    )
    if expected != row["record_fingerprint"]:
        raise PersistenceIntegrityError("native source record fingerprint drift")
    if (
        receipt.space_id != space_id
        or receipt.admission_id != admission_id
        or receipt.command_sha256 != row["command_sha256"]
        or receipt.source_authority_epoch != row["source_authority_epoch"]
        or receipt.source_artifact_id != row["source_artifact_id"]
        or receipt.source_revision_id != row["source_revision_id"]
        or receipt.published_revision_id != row["published_revision_id"]
        or artifact.source_artifact_id != row["source_artifact_id"]
        or revision.source_revision_id != row["source_revision_id"]
        or revision.source_artifact_id != artifact.source_artifact_id
        or origin != receipt.origin
    ):
        raise PersistenceIntegrityError("native source row identity drift")
    span_rows = conn.execute(
        sql.SQL(
            """
            SELECT span_id, evidence_ref_id, proof
            FROM {}.knowledge_native_source_spans
            WHERE space_id = %s AND admission_id = %s
            """
        ).format(sql.Identifier(SCHEMA)),
        (space_id, admission_id),
    ).fetchall()
    expected_spans = {
        (proof.span_id, proof.evidence_ref_id, canonical_sha256(proof.model_dump(mode="json")))
        for proof in proofs
    }
    actual_spans = {
        (
            item["span_id"],
            item["evidence_ref_id"],
            canonical_sha256(item["proof"]),
        )
        for item in span_rows
    }
    if actual_spans != expected_spans:
        raise PersistenceIntegrityError("native source span index drift")
    return {
        "space_id": space_id,
        "artifact": artifact,
        "revision": revision,
        "body": body,
        "proofs": proofs,
        "origin": origin,
        "receipt": receipt,
        "epoch": row["source_authority_epoch"],
    }


def _read_native_receipt(
    conn: Connection[Any], space_id: str, admission_id: str
) -> NativeSourceAdmissionReceiptV1 | None:
    record = _read_native_record(conn, space_id, admission_id)
    return None if record is None else record["receipt"]


class PostgresNativeSourceEvidenceRepository(PostgresKnowledgeRevisionRepository):
    """Atomic source bytes, proof, native child, receipts and head/event adapter."""

    def __init__(
        self,
        database: PostgresDatabase,
        *,
        after_revision_insert: Callable[[], None] | None = None,
        after_receipt_insert: Callable[[], None] | None = None,
        after_native_source_insert: Callable[[], None] | None = None,
        after_native_receipt_insert: Callable[[], None] | None = None,
        after_publication_commit: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            database,
            after_revision_insert=after_revision_insert,
            after_receipt_insert=after_receipt_insert,
        )
        self._after_native_source_insert = after_native_source_insert
        self._after_native_receipt_insert = after_native_receipt_insert
        self._after_native_publication_commit = after_publication_commit

    def get_native_source_admission_receipt(
        self, space_id: str, admission_id: str
    ) -> NativeSourceAdmissionReceiptV1 | None:
        with self._database.transaction() as conn:
            return _read_native_receipt(conn, space_id, admission_id)

    def publish_native_text_source_evidence(
        self,
        *,
        request: NativeTextSourceAdmissionV1,
        command: PublishKnowledgeRevisionCommand,
        command_sha256: str,
        domain_contract: DomainContractDescriptor,
        semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
        source_artifact: SourceArtifactV3,
        source_revision: SourceRevisionV2,
        body_bytes: bytes,
        span_proofs: Sequence[NativeUtf8SpanProofV1],
    ) -> NativeSourceAdmissionReceiptV1:
        recomputed_command_sha = native_source_command_sha256(
            request=request,
            command=command,
            domain_contract=domain_contract,
            semantic_profile=semantic_profile,
        )
        if recomputed_command_sha != command_sha256:
            raise NativeTextSourceAdmissionIntegrityError("command_fingerprint_mismatch")
        with self._database.transaction() as conn:
            # Global source epoch is always acquired before the per-space CAS lock.
            _lock_native_epoch(conn)
            _lock_space(conn, request.space_id, created_at=request.created_at)

            parent = _read_revision(conn, request.space_id, request.expected_parent_revision_id)
            if parent is None:
                raise PersistenceIntegrityError("native source expected parent is missing")
            parts = validate_native_source_write(
                request=request,
                command=command,
                command_sha256=command_sha256,
                domain_contract=domain_contract,
                semantic_profile=semantic_profile,
                source_artifact=source_artifact,
                source_revision=source_revision,
                body_bytes=body_bytes,
                span_proofs=span_proofs,
                parent=parent,
            )
            existing = _read_native_receipt(conn, request.space_id, request.admission_id)
            if existing is not None:
                if existing.command_sha256 != recomputed_command_sha:
                    raise KnowledgePublicationIdempotencyConflictError(
                        space_id=request.space_id, publication_id=request.admission_id
                    )
                return existing
            if _read_receipt(conn, request.space_id, request.admission_id) is not None:
                raise KnowledgePublicationIdempotencyConflictError(
                    space_id=request.space_id, publication_id=request.admission_id
                )

            def insert_child(value: StoredKnowledgeRevision) -> None:
                _insert_revision(conn, value)
                if self._after_revision_insert is not None:
                    self._after_revision_insert()

            stored = commit_expected_parent(
                command,
                read_head=lambda: _read_head(conn, request.space_id),
                read_revision=lambda revision_id: _read_revision(
                    conn, request.space_id, revision_id
                ),
                insert_revision=insert_child,
                advance_head=lambda head, event: _advance_head(conn, head, event),
            )
            publication_receipt = KnowledgePublicationReceipt(
                space_id=request.space_id,
                publication_id=request.admission_id,
                command_sha256=canonical_sha256(command.model_dump(mode="json")),
                expected_parent_revision_id=request.expected_parent_revision_id,
                published_revision_id=stored.revision.revision_id,
                graph_payload_sha256=stored.graph_payload_sha256,
            )
            _insert_receipt(conn, publication_receipt)
            if self._after_receipt_insert is not None:
                self._after_receipt_insert()

            epoch_row = conn.execute(
                sql.SQL(
                    "UPDATE {}.knowledge_native_source_authority "
                    "SET epoch = epoch + 1 WHERE singleton_id = 1 RETURNING epoch"
                ).format(sql.Identifier(SCHEMA))
            ).fetchone()
            if epoch_row is None:
                raise PersistenceIntegrityError("native source epoch update returned no row")
            epoch = epoch_row["epoch"]
            companion = NativeSourceAdmissionReceiptV1(
                space_id=request.space_id,
                admission_id=request.admission_id,
                command_sha256=command_sha256,
                source_authority_epoch=epoch,
                source_artifact_id=parts.artifact.source_artifact_id,
                source_revision_id=parts.revision.source_revision_id,
                origin=request.origin,
                published_revision_id=stored.revision.revision_id,
                bindings=[
                    NativeTextSourceAdmissionBindingV1(
                        client_ref=span.client_ref,
                        span_id=proof.span_id,
                        evidence_ref_id=proof.evidence_ref_id,
                    )
                    for span, proof in zip(request.spans, parts.span_proofs, strict=True)
                ],
                publication_receipt=publication_receipt,
            )
            fingerprint = _record_fingerprint(
                artifact=parts.artifact,
                revision=parts.revision,
                body=parts.body_bytes,
                proofs=parts.span_proofs,
                origin=request.origin,
                receipt=companion,
            )
            conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.knowledge_native_source_admissions (
                        space_id, admission_id, schema_version, command_sha256,
                        source_authority_epoch, source_artifact_id, source_revision_id,
                        published_revision_id, source_artifact, source_revision, origin,
                        body_bytes, span_proofs, receipt_payload, record_fingerprint
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                ).format(sql.Identifier(SCHEMA)),
                (
                    request.space_id,
                    request.admission_id,
                    companion.schema_version,
                    command_sha256,
                    epoch,
                    parts.artifact.source_artifact_id,
                    parts.revision.source_revision_id,
                    stored.revision.revision_id,
                    jsonb(parts.artifact.model_dump(mode="json")),
                    jsonb(parts.revision.model_dump(mode="json")),
                    (
                        None
                        if request.origin is None
                        else jsonb(request.origin.model_dump(mode="json"))
                    ),
                    parts.body_bytes,
                    jsonb([item.model_dump(mode="json") for item in parts.span_proofs]),
                    jsonb(companion.model_dump(mode="json")),
                    fingerprint,
                ),
            )
            if self._after_native_source_insert is not None:
                self._after_native_source_insert()
            for proof in parts.span_proofs:
                conn.execute(
                    sql.SQL(
                        """
                        INSERT INTO {}.knowledge_native_source_spans (
                            span_id, evidence_ref_id, space_id, admission_id, proof
                        ) VALUES (%s, %s, %s, %s, %s)
                        """
                    ).format(sql.Identifier(SCHEMA)),
                    (
                        proof.span_id,
                        proof.evidence_ref_id,
                        request.space_id,
                        request.admission_id,
                        jsonb(proof.model_dump(mode="json")),
                    ),
                )
            if self._after_native_receipt_insert is not None:
                self._after_native_receipt_insert()

        if self._after_native_publication_commit is not None:
            self._after_native_publication_commit()
        return companion

    def open_native_source_view(self, space_id: str) -> NativeTextSourceView:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    "SELECT epoch FROM {}.knowledge_native_source_authority WHERE singleton_id = 1"
                ).format(sql.Identifier(SCHEMA))
            ).fetchone()
            if row is None:
                raise PersistenceIntegrityError("native source authority epoch row missing")
            return _PostgresNativeTextSourceView(self._database, space_id, row["epoch"])


class _PostgresNativeTextSourceView:
    __slots__ = ("_database", "_epoch", "_space_id")

    def __init__(self, database: PostgresDatabase, space_id: str, epoch: int) -> None:
        self._database = database
        self._space_id = space_id
        self._epoch = epoch

    @property
    def epoch(self) -> int:
        return self._epoch

    def open_coherent_view(self) -> NativeTextSourceView:
        return _PostgresNativeTextSourceView(self._database, self._space_id, self._epoch)

    def get_provenance_snapshot(
        self, *, artifact_ids: Sequence[str], revision_ids: Sequence[str]
    ) -> KnowledgeProvenanceSnapshot:
        requested_artifacts = tuple(sorted(set(artifact_ids)))
        requested_revisions = tuple(sorted(set(revision_ids)))
        artifacts: dict[str, SourceArtifactV3] = {}
        revisions: dict[str, SourceRevisionV2] = {}
        if requested_artifacts or requested_revisions:
            with self._database.transaction() as conn:
                rows = conn.execute(
                    sql.SQL(
                        """
                        SELECT admission_id, source_artifact_id, source_revision_id
                        FROM {}.knowledge_native_source_admissions
                        WHERE space_id = %s AND source_authority_epoch <= %s
                          AND (source_artifact_id = ANY(%s) OR source_revision_id = ANY(%s))
                        """
                    ).format(sql.Identifier(SCHEMA)),
                    (
                        self._space_id,
                        self._epoch,
                        list(requested_artifacts),
                        list(requested_revisions),
                    ),
                ).fetchall()
                for row in rows:
                    record = _read_native_record(conn, self._space_id, row["admission_id"])
                    if record is None:
                        raise PersistenceIntegrityError("native source record disappeared")
                    if row["source_artifact_id"] in requested_artifacts:
                        artifacts[row["source_artifact_id"]] = record["artifact"]
                    if row["source_revision_id"] in requested_revisions:
                        revisions[row["source_revision_id"]] = record["revision"]
        return _build_snapshot_from_loaded(
            loaded_artifacts=artifacts,
            loaded_revisions=revisions,
            requested_artifacts=requested_artifacts,
            requested_revisions=requested_revisions,
            missing_artifacts=tuple(item for item in requested_artifacts if item not in artifacts),
            missing_revisions=tuple(item for item in requested_revisions if item not in revisions),
        )

    def get_native_text_source(
        self, *, source_artifact_id: str, source_revision_id: str, span_id: str
    ) -> StoredNativeTextSource | None:
        with self._database.transaction() as conn:
            row = conn.execute(
                sql.SQL(
                    """
                    SELECT admission_id
                    FROM {}.knowledge_native_source_admissions
                    WHERE space_id = %s AND source_artifact_id = %s
                      AND source_revision_id = %s AND source_authority_epoch <= %s
                    """
                ).format(sql.Identifier(SCHEMA)),
                (self._space_id, source_artifact_id, source_revision_id, self._epoch),
            ).fetchone()
            if row is None:
                return None
            record = _read_native_record(conn, self._space_id, row["admission_id"])
            if record is None:
                raise PersistenceIntegrityError("native source record disappeared")
            span = next((proof for proof in record["proofs"] if proof.span_id == span_id), None)
            if span is None:
                return None
            return StoredNativeTextSource(
                source_artifact=record["artifact"],
                source_revision=record["revision"],
                body_bytes=record["body"],
                span_proof=span,
                authority_epoch=record["epoch"],
            )
