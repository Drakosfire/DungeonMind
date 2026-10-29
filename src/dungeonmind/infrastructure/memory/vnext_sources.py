"""Atomic in-memory adapter for native text-source admission and access."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass

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
    KnowledgeHead,
    PublishKnowledgeRevisionCommand,
)
from dungeonmind.contracts.vnext.native_source import (
    NativeSourceAdmissionReceiptV1,
    NativeSourceEvidenceExtensionReceiptV1,
    NativeSourceEvidenceExtensionV1,
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
from ...application.vnext.records import KnowledgeHeadEvent, StoredKnowledgeRevision
from .vnext_knowledge import InMemoryKnowledgeRevisionRepository


@dataclass(frozen=True, slots=True)
class _NativeSourceRecord:
    space_id: str
    artifact: SourceArtifactV3
    revision: SourceRevisionV2
    body: bytes
    proofs: tuple[NativeUtf8SpanProofV1, ...]
    origin: NativeTextSourceOriginV1 | None
    epoch: int
    fingerprint: str


def _native_fingerprint(
    *,
    artifact: SourceArtifactV3,
    revision: SourceRevisionV2,
    body: bytes,
    proofs: Sequence[NativeUtf8SpanProofV1],
    origin: NativeTextSourceOriginV1 | None,
    epoch: int,
) -> str:
    return canonical_sha256(
        {
            "artifact": artifact.model_dump(mode="json"),
            "revision": revision.model_dump(mode="json"),
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "proofs": [item.model_dump(mode="json") for item in proofs],
            "origin": None if origin is None else origin.model_dump(mode="json"),
            "epoch": epoch,
        }
    )


class InMemoryNativeSourceEvidenceRepository(InMemoryKnowledgeRevisionRepository):
    """One lock and rollback boundary for graph, receipts, source bytes and spans."""

    def __init__(
        self,
        *,
        after_revision_insert: Callable[[], None] | None = None,
        after_receipt_insert: Callable[[], None] | None = None,
        after_publication_commit: Callable[[], None] | None = None,
        after_prospective_result_insert: Callable[[], None] | None = None,
        after_native_source_insert: Callable[[], None] | None = None,
        after_native_receipt_insert: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            after_revision_insert=after_revision_insert,
            after_publication_commit=after_publication_commit,
            after_prospective_result_insert=after_prospective_result_insert,
        )
        self._after_native_publication_receipt_insert = after_receipt_insert
        self._native_epoch = 0
        self._extension_receipts = {}
        self._extension_by_span = {}
        self._native_receipts: dict[tuple[str, str], NativeSourceAdmissionReceiptV1] = {}
        self._native_records: dict[tuple[str, str], _NativeSourceRecord] = {}
        self._by_revision: dict[tuple[str, str], _NativeSourceRecord] = {}
        self._by_span: dict[tuple[str, str], tuple[_NativeSourceRecord, NativeUtf8SpanProofV1]] = {}
        self._global_identity_space: dict[str, str] = {}
        self._after_native_source_insert = after_native_source_insert
        self._after_native_receipt_insert = after_native_receipt_insert

    def get_native_source_admission_receipt(
        self, space_id: str, admission_id: str
    ) -> NativeSourceAdmissionReceiptV1 | None:
        with self._lock:
            receipt = self._native_receipts.get((space_id, admission_id))
            return None if receipt is None else receipt.model_copy(deep=True)

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
        key = (request.space_id, request.admission_id)
        recomputed_command_sha = native_source_command_sha256(
            request=request,
            command=command,
            domain_contract=domain_contract,
            semantic_profile=semantic_profile,
        )
        if recomputed_command_sha != command_sha256:
            raise NativeTextSourceAdmissionIntegrityError("command_fingerprint_mismatch")
        with self._lock:
            parent = self._revisions.get((request.space_id, request.expected_parent_revision_id))
            if parent is None:
                raise PersistenceIntegrityError("native source parent is missing")
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
            existing = self._native_receipts.get(key)
            if existing is not None:
                if existing.command_sha256 != recomputed_command_sha:
                    raise KnowledgePublicationIdempotencyConflictError(
                        space_id=request.space_id, publication_id=request.admission_id
                    )
                return existing.model_copy(deep=True)
            if key in self._receipts:
                raise KnowledgePublicationIdempotencyConflictError(
                    space_id=request.space_id, publication_id=request.admission_id
                )
            all_ids = [
                parts.artifact.source_artifact_id,
                parts.revision.source_revision_id,
                *(proof.span_id for proof in parts.span_proofs),
                *(proof.evidence_ref_id for proof in parts.span_proofs),
            ]
            if len(all_ids) != len(set(all_ids)):
                raise PersistenceIntegrityError("native source identity collision")
            if any(identity in self._global_identity_space for identity in all_ids):
                raise PersistenceIntegrityError("native source identity collision")

            old_revisions = dict(self._revisions)
            old_heads = dict(self._heads)
            old_events = list(self._events)
            old_receipts = dict(self._receipts)
            old_epoch = self._native_epoch
            old_native_receipts = dict(self._native_receipts)
            old_records = dict(self._native_records)
            old_by_revision = dict(self._by_revision)
            old_by_span = dict(self._by_span)
            old_global = dict(self._global_identity_space)
            try:
                stored = commit_expected_parent(
                    command,
                    read_head=lambda: self._heads.get(request.space_id),
                    read_revision=lambda revision_id: self._revisions.get(
                        (request.space_id, revision_id)
                    ),
                    insert_revision=lambda value: self._insert_native_child(value),
                    advance_head=lambda head, event: self._advance_native_head(head, event),
                )
                publication_receipt = KnowledgePublicationReceipt(
                    space_id=request.space_id,
                    publication_id=request.admission_id,
                    command_sha256=canonical_sha256(command.model_dump(mode="json")),
                    expected_parent_revision_id=request.expected_parent_revision_id,
                    published_revision_id=stored.revision.revision_id,
                    graph_payload_sha256=stored.graph_payload_sha256,
                )
                self._receipts[key] = publication_receipt
                if self._after_native_publication_receipt_insert is not None:
                    self._after_native_publication_receipt_insert()
                epoch = self._native_epoch + 1
                record = _NativeSourceRecord(
                    space_id=request.space_id,
                    artifact=parts.artifact.model_copy(deep=True),
                    revision=parts.revision.model_copy(deep=True),
                    body=bytes(parts.body_bytes),
                    proofs=tuple(item.model_copy(deep=True) for item in parts.span_proofs),
                    origin=None if request.origin is None else request.origin.model_copy(deep=True),
                    epoch=epoch,
                    fingerprint=_native_fingerprint(
                        artifact=parts.artifact,
                        revision=parts.revision,
                        body=parts.body_bytes,
                        proofs=parts.span_proofs,
                        origin=request.origin,
                        epoch=epoch,
                    ),
                )
                self._native_epoch = epoch
                self._native_records[(request.space_id, parts.artifact.source_artifact_id)] = record
                self._by_revision[(request.space_id, parts.revision.source_revision_id)] = record
                self._global_identity_space.update(
                    {identity: request.space_id for identity in all_ids}
                )
                for proof in parts.span_proofs:
                    self._by_span[(request.space_id, proof.span_id)] = (record, proof)
                if self._after_native_source_insert is not None:
                    self._after_native_source_insert()
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
                self._native_receipts[key] = companion
                if self._after_native_receipt_insert is not None:
                    self._after_native_receipt_insert()
            except Exception:
                self._revisions = old_revisions
                self._heads = old_heads
                self._events = old_events
                self._receipts = old_receipts
                self._native_epoch = old_epoch
                self._native_receipts = old_native_receipts
                self._native_records = old_records
                self._by_revision = old_by_revision
                self._by_span = old_by_span
                self._global_identity_space = old_global
                raise
        if self._after_publication_commit is not None:
            self._after_publication_commit()
        return companion.model_copy(deep=True)

    def get_native_source_evidence_extension_receipt(
        self, space_id: str, extension_id: str
    ) -> NativeSourceEvidenceExtensionReceiptV1 | None:
        with self._lock:
            value = self._extension_receipts.get((space_id, extension_id))
            if value is None:
                return None
            receipt, fingerprint = value
            if canonical_sha256(receipt.model_dump(mode="json")) != fingerprint:
                raise PersistenceIntegrityError("extension receipt fingerprint drift")
            return NativeSourceEvidenceExtensionReceiptV1.model_validate(
                receipt.model_dump(mode="json")
            )

    def publish_native_source_evidence_extension(
        self,
        *,
        request: NativeSourceEvidenceExtensionV1,
        domain_contract: DomainContractDescriptor,
        semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
        audience_labels: Sequence[str],
    ) -> NativeSourceEvidenceExtensionReceiptV1:
        from ...application.vnext.errors import KnowledgePublicationOutcomeUnknownError
        from ...application.vnext.native_source_extension import (
            extension_plan,
            make_extension_receipt,
            snapshot_extension_inputs,
        )

        request, domain_contract, semantic_profile = snapshot_extension_inputs(
            request, domain_contract, semantic_profile
        )
        audience_labels = tuple(audience_labels)

        with self._lock:
            record = self._by_revision.get((request.space_id, request.source_revision_id))
            intervals = (
                set() if record is None else {(p.start_byte, p.end_byte) for p in record.proofs}
            )
            root = self.get_native_source_admission_receipt(
                request.space_id, request.original_admission_id
            )
            if (
                root is not None
                and record is not None
                and (
                    root.source_artifact_id != record.artifact.source_artifact_id
                    or root.source_revision_id != record.revision.source_revision_id
                    or root.origin != record.origin
                    or {b.span_id for b in root.bindings} != {p.span_id for p in record.proofs}
                )
            ):
                raise PersistenceIntegrityError("extension original source receipt drift")

            for key in self._extension_receipts:
                receipt = self.get_native_source_evidence_extension_receipt(*key)
                if (
                    receipt.space_id == request.space_id
                    and receipt.source_revision_id == request.source_revision_id
                ):
                    intervals.update((p.start_byte, p.end_byte) for p in receipt.proofs)
            plan = extension_plan(
                repository=self,
                request=request,
                domain_contract=domain_contract,
                semantic_profile=semantic_profile,
                audience_labels=audience_labels,
                registered_intervals=intervals,
            )
            if isinstance(plan, NativeSourceEvidenceExtensionReceiptV1):
                return plan
            ids = [i for p in plan.proofs for i in (p.span_id, p.evidence_ref_id)]
            if any(i in self._global_identity_space for i in ids):
                raise PersistenceIntegrityError("extension identity collision")
            snapshot = (
                dict(self._revisions),
                dict(self._heads),
                list(self._events),
                dict(self._receipts),
                self._native_epoch,
                dict(self._extension_receipts),
                dict(self._extension_by_span),
                dict(self._global_identity_space),
            )
            try:
                command = plan.command
                stored = commit_expected_parent(
                    command,
                    read_head=lambda: self._heads.get(request.space_id),
                    read_revision=lambda rid: self._revisions.get((request.space_id, rid)),
                    insert_revision=self._insert_native_child,
                    advance_head=self._advance_native_head,
                )
                publication = KnowledgePublicationReceipt(
                    space_id=request.space_id,
                    publication_id=request.extension_id,
                    command_sha256=canonical_sha256(command.model_dump(mode="json")),
                    expected_parent_revision_id=request.expected_parent_revision_id,
                    published_revision_id=stored.revision.revision_id,
                    graph_payload_sha256=stored.graph_payload_sha256,
                )
                self._receipts[(request.space_id, request.extension_id)] = publication
                if self._after_native_publication_receipt_insert:
                    self._after_native_publication_receipt_insert()
                self._native_epoch += 1
                receipt = make_extension_receipt(plan, self._native_epoch, publication)
                self._extension_receipts[(request.space_id, request.extension_id)] = (
                    receipt,
                    canonical_sha256(receipt.model_dump(mode="json")),
                )
                for proof in plan.proofs:
                    self._extension_by_span[(request.space_id, proof.span_id)] = (
                        request.extension_id
                    )
                self._global_identity_space.update({i: request.space_id for i in ids})
                if self._after_native_source_insert:
                    self._after_native_source_insert()
                if self._after_native_receipt_insert:
                    self._after_native_receipt_insert()
            except Exception:
                (
                    self._revisions,
                    self._heads,
                    self._events,
                    self._receipts,
                    self._native_epoch,
                    self._extension_receipts,
                    self._extension_by_span,
                    self._global_identity_space,
                ) = snapshot
                raise
        if self._after_publication_commit:
            try:
                self._after_publication_commit()
            except Exception as exc:
                raise KnowledgePublicationOutcomeUnknownError(
                    space_id=request.space_id,
                    publication_id=request.extension_id,
                    expected_published_revision_id=receipt.publication_receipt.published_revision_id,
                    reason="extension_commit_acknowledgement_lost",
                ) from exc
        return receipt.model_copy(deep=True)

    def _insert_native_child(self, stored: StoredKnowledgeRevision) -> None:
        key = (stored.revision.space_id, stored.revision.revision_id)
        self._revisions[key] = stored
        if self._after_revision_insert is not None:
            self._after_revision_insert()

    def _advance_native_head(self, head: KnowledgeHead, event: KnowledgeHeadEvent) -> None:
        self._heads[head.space_id] = head
        self._events.append(event)

    def open_native_source_view(self, space_id: str) -> NativeTextSourceView:
        with self._lock:
            return _InMemoryNativeTextSourceView(self, space_id, self._native_epoch)


class _InMemoryNativeTextSourceView:
    __slots__ = ("_epoch", "_repository", "_space_id")

    def __init__(
        self,
        repository: InMemoryNativeSourceEvidenceRepository,
        space_id: str,
        epoch: int,
    ) -> None:
        self._repository = repository
        self._space_id = space_id
        self._epoch = epoch

    @property
    def epoch(self) -> int:
        return self._epoch

    def open_coherent_view(self) -> NativeTextSourceView:
        return _InMemoryNativeTextSourceView(self._repository, self._space_id, self._epoch)

    def get_provenance_snapshot(
        self, *, artifact_ids: Sequence[str], revision_ids: Sequence[str]
    ) -> KnowledgeProvenanceSnapshot:
        requested_artifacts = tuple(sorted(set(artifact_ids)))
        requested_revisions = tuple(sorted(set(revision_ids)))
        artifacts: dict[str, SourceArtifactV3] = {}
        revisions: dict[str, SourceRevisionV2] = {}
        with self._repository._lock:
            for artifact_id in requested_artifacts:
                record = self._repository._native_records.get((self._space_id, artifact_id))
                if record is not None and record.epoch <= self._epoch:
                    artifacts[artifact_id] = record.artifact
            for revision_id in requested_revisions:
                record = self._repository._by_revision.get((self._space_id, revision_id))
                if record is not None and record.epoch <= self._epoch:
                    revisions[revision_id] = record.revision
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
        with self._repository._lock:
            record = self._repository._native_records.get((self._space_id, source_artifact_id))
            indexed_revision = self._repository._by_revision.get(
                (self._space_id, source_revision_id)
            )
            indexed_span = self._repository._by_span.get((self._space_id, span_id))
            if record is None or record.epoch > self._epoch:
                return None
            proof_epoch = record.epoch
            if indexed_span is None:
                extension_id = self._repository._extension_by_span.get((self._space_id, span_id))
                if extension_id is not None:
                    receipt = self._repository.get_native_source_evidence_extension_receipt(
                        self._space_id, extension_id
                    )
                    root = self._repository.get_native_source_admission_receipt(
                        self._space_id, receipt.original_admission_id
                    )
                    if (
                        root is None
                        or canonical_sha256(root.model_dump(mode="json"))
                        != receipt.original_admission_sha256
                        or (receipt.source_artifact_id, receipt.source_revision_id, receipt.origin)
                        != (source_artifact_id, source_revision_id, root.origin)
                    ):
                        raise PersistenceIntegrityError("extension source lineage drift")
                    if receipt.source_authority_epoch > self._epoch:
                        return None
                    proof = next((p for p in receipt.proofs if p.span_id == span_id), None)
                    if proof is None:
                        raise PersistenceIntegrityError("extension span index drift")
                    indexed_span = (record, proof)
                    proof_epoch = receipt.source_authority_epoch
            if (
                indexed_revision is not record
                or indexed_span is None
                or indexed_span[0] is not record
            ):
                return None
            expected = _native_fingerprint(
                artifact=record.artifact,
                revision=record.revision,
                body=record.body,
                proofs=record.proofs,
                origin=record.origin,
                epoch=record.epoch,
            )
            if expected != record.fingerprint:
                raise PersistenceIntegrityError("native source record fingerprint drift")
            proof = indexed_span[1]
            return StoredNativeTextSource(
                source_artifact=record.artifact.model_copy(deep=True),
                source_revision=record.revision.model_copy(deep=True),
                body_bytes=bytes(record.body),
                span_proof=proof.model_copy(deep=True),
                authority_epoch=proof_epoch,
            )
