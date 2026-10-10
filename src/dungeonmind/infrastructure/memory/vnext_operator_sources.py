"""In-memory atomic authority for prepared operator source attestations."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from dungeonmind.application.vnext.operator_approval import (
    OperatorApprovalAuthority,
    TrustedOperatorApproval,
)
from dungeonmind.application.vnext.operator_source_binding import (
    validate_operator_source_selection,
)
from dungeonmind.application.vnext.ports import NativeTextSourceView, StoredNativeTextSource
from dungeonmind.application.vnext.provenance import (
    KnowledgeProvenanceSnapshot,
    _build_snapshot_from_loaded,
)
from dungeonmind.contracts.evidence import SourceStatus
from dungeonmind.contracts.vnext.domain import DomainContractDescriptor
from dungeonmind.contracts.vnext.native_source import (
    NATIVE_TEXT_BODY_STORAGE,
    NativeUtf8SpanProofV1,
)
from dungeonmind.contracts.vnext.operator_source import (
    OperatorSourceAttestationReceiptV1,
    OperatorSourceSelectionV1,
    PreparedOperatorSourceV1,
)
from dungeonmind.contracts.vnext.source import SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

from .repositories import InMemorySourceRepository
from .vnext_sources import InMemoryNativeSourceEvidenceRepository


@dataclass(frozen=True, slots=True)
class _OperatorArtifact:
    source_revision: SourceRevisionV2
    body: bytes
    policy_sha256: str
    first_epoch: int


class InMemoryOperatorSourceRepository(InMemoryNativeSourceEvidenceRepository):
    """Shares the native source lock/epoch and keeps legacy rows immutable."""

    def __init__(
        self, *, legacy_sources: InMemorySourceRepository,
        approval_authority: OperatorApprovalAuthority,
        after_operator_artifact_insert: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._legacy_sources = legacy_sources
        self._approval_authority = approval_authority
        self._after_operator_artifact_insert = after_operator_artifact_insert
        self._operator_prepared: dict[tuple[str, str], PreparedOperatorSourceV1] = {}
        self._operator_artifacts: dict[tuple[str, str], _OperatorArtifact] = {}
        self._operator_by_revision: dict[tuple[str, str], _OperatorArtifact] = {}
        self._operator_artifact_receipts: dict[
            tuple[str, str], OperatorSourceAttestationReceiptV1
        ] = {}
        self._operator_spans: dict[
            tuple[str, str], tuple[NativeUtf8SpanProofV1, OperatorSourceAttestationReceiptV1]
        ] = {}
        self._operator_receipts: dict[tuple[str, str], OperatorSourceAttestationReceiptV1] = {}

    def prepare_operator_source_span(
        self, *, selection: OperatorSourceSelectionV1,
        domain_contract: DomainContractDescriptor,
    ) -> PreparedOperatorSourceV1:
        key = (selection.space_id, selection.operation_id)
        with self._legacy_sources._lock, self._lock:
            head = self._heads.get(selection.space_id)
            stored = self._revisions.get(
                (selection.space_id, selection.expected_head_revision_id)
            )
            if (
                head is None
                or head.head_revision_id != selection.expected_head_revision_id
                or stored is None
            ):
                raise PersistenceIntegrityError("operator source expected head changed")
            prepared = validate_operator_source_selection(
                selection=selection, domain_contract=domain_contract,
                authority=self._approval_authority, head_revision=stored,
                legacy_artifact=self._legacy_sources.get_artifact(selection.source_artifact_id),
                legacy_revision=self._legacy_sources.get_revision(selection.source_revision_id),
                source_epoch=self._native_epoch,
            )
            existing = self._operator_prepared.get(key)
            if existing is not None:
                if existing.command != prepared.command:
                    raise PersistenceIntegrityError("operator preparation ID conflict")
                return existing.model_copy(deep=True)
            if key in self._operator_receipts:
                raise PersistenceIntegrityError("operator operation ID already committed")
            self._operator_prepared[key] = prepared.model_copy(deep=True)
            return prepared.model_copy(deep=True)

    def get_operator_source_receipt(
        self, space_id: str, operation_id: str,
    ) -> OperatorSourceAttestationReceiptV1 | None:
        with self._lock:
            receipt = self._operator_receipts.get((space_id, operation_id))
            if receipt is None:
                return None
            self._verify_receipt(receipt)
            artifact = self._operator_artifacts.get(
                (space_id, receipt.command.source_artifact_id)
            )
            prepared = self._operator_prepared.get((space_id, operation_id))
            pair = self._operator_spans.get(
                (space_id, receipt.command.source_span_ref_id)
            )
            if (
                artifact is None or pair is None or prepared is None
                or prepared.command != receipt.command
                or prepared.preparation_sha256 != receipt.preparation_sha256
                or prepared.review_display_sha256 != receipt.review_display_sha256
                or pair[1] != receipt
                or pair[0].evidence_ref_id != receipt.command.evidence_ref_id
                or artifact.source_revision.content_sha256 != receipt.command.body_sha256
                or pair[0].end_byte > len(artifact.body)
                or hashlib.sha256(
                    artifact.body[pair[0].start_byte:pair[0].end_byte]
                ).hexdigest() != pair[0].slice_sha256
                or artifact.policy_sha256 != canonical_sha256(
                    receipt.command.native_policy.model_dump(mode="json")
                )
            ):
                raise PersistenceIntegrityError("operator receipt/source binding drift")
            return receipt.model_copy(deep=True)

    @staticmethod
    def _verify_receipt(receipt: OperatorSourceAttestationReceiptV1) -> None:
        payload = receipt.model_dump(mode="json", exclude={"record_fingerprint"})
        if canonical_sha256(payload) != receipt.record_fingerprint:
            raise PersistenceIntegrityError("operator attestation fingerprint drift")

    def commit_operator_source_span(
        self, *, space_id: str, operation_id: str,
        body_text: str, approval: TrustedOperatorApproval,
        domain_contract: DomainContractDescriptor,
    ) -> OperatorSourceAttestationReceiptV1:
        key = (space_id, operation_id)
        with self._legacy_sources._lock, self._lock:
            existing_receipt = self._operator_receipts.get(key)
            if existing_receipt is not None:
                self._verify_receipt(existing_receipt)
                if (
                    existing_receipt.preparation_sha256 != approval.preparation_sha256
                    or hashlib.sha256(body_text.encode("utf-8", "strict")).hexdigest()
                    != existing_receipt.command.body_sha256
                ):
                    raise PersistenceIntegrityError("operator attestation replay conflict")
                self._approval_authority.verify(
                    approval, space_id=space_id,
                    world_id=existing_receipt.command.legacy_world_id,
                    operation_id=operation_id,
                    preparation_sha256=existing_receipt.preparation_sha256,
                    source_vocabulary_sha256=existing_receipt.command.source_vocabulary_sha256,
                )
                return existing_receipt.model_copy(deep=True)
            prepared = self._operator_prepared.get(key)
            if prepared is None:
                raise PersistenceIntegrityError("operator preparation missing")
            command = prepared.command
            self._approval_authority.verify(
                approval, space_id=space_id, world_id=command.legacy_world_id,
                operation_id=operation_id,
                preparation_sha256=prepared.preparation_sha256,
                source_vocabulary_sha256=command.source_vocabulary_sha256,
            )
            if datetime.now(UTC) >= prepared.expires_at:
                raise PersistenceIntegrityError("operator preparation expired")
            if self._native_epoch != command.expected_source_epoch:
                raise PersistenceIntegrityError("source authority epoch changed")
            head = self._heads.get(space_id)
            stored = self._revisions.get((space_id, command.expected_head_revision_id))
            if (
                head is None
                or head.head_revision_id != command.expected_head_revision_id
                or stored is None
            ):
                raise PersistenceIntegrityError("native head changed")
            body = body_text.encode("utf-8", "strict")
            if (
                hashlib.sha256(body).hexdigest() != command.body_sha256
                or command.end_byte > len(body)
            ):
                raise PersistenceIntegrityError("body differs from prepared command")
            selected = body[command.start_byte:command.end_byte]
            selected.decode("utf-8", "strict")
            if hashlib.sha256(selected).hexdigest() != command.slice_sha256:
                raise PersistenceIntegrityError("passage differs from prepared command")
            selection = OperatorSourceSelectionV1(
                space_id=space_id, legacy_world_id=command.legacy_world_id,
                operation_id=operation_id,
                expected_head_revision_id=command.expected_head_revision_id,
                claim_kind=command.claim_kind, claim_id=command.claim_id,
                evidence_ref_id=command.evidence_ref_id,
                source_artifact_id=command.source_artifact_id,
                source_revision_id=command.source_revision_id,
                source_span_ref_id=command.source_span_ref_id,
                expected_body_sha256=command.body_sha256,
                body_text=body_text, passage_text=selected.decode("utf-8"),
                occurrence_index=self._occurrence_index(body, selected, command.start_byte),
                native_policy=command.native_policy,
                source_vocabulary=sorted(self._approval_authority.allowed_source_terms),
                gm_label=command.gm_label,
            )
            rechecked = validate_operator_source_selection(
                selection=selection, domain_contract=domain_contract,
                authority=self._approval_authority, head_revision=stored,
                legacy_artifact=self._legacy_sources.get_artifact(command.source_artifact_id),
                legacy_revision=self._legacy_sources.get_revision(command.source_revision_id),
                source_epoch=self._native_epoch,
                prepared_at=prepared.prepared_at,
            )
            if rechecked != prepared:
                raise PersistenceIntegrityError("prepared review or policy changed")
            artifact_key = (space_id, command.source_artifact_id)
            prior = self._operator_artifacts.get(artifact_key)
            policy_sha = canonical_sha256(command.native_policy.model_dump(mode="json"))
            if prior is not None and (
                prior.policy_sha256 != policy_sha
                or prior.source_revision.source_revision_id != command.source_revision_id
                or prior.body != body
            ):
                raise PersistenceIntegrityError("artifact-wide policy/body conflict")
            if (
                (space_id, command.source_span_ref_id) in self._operator_spans
                or (space_id, command.source_span_ref_id) in self._by_span
                or artifact_key in self._native_records
                or (space_id, command.source_revision_id) in self._by_revision
            ):
                raise PersistenceIntegrityError("source or span identity collision")
            identities = (
                command.source_artifact_id, command.source_revision_id,
                command.source_span_ref_id, command.evidence_ref_id,
            )
            if len(set(identities)) != len(identities):
                raise PersistenceIntegrityError("source identities overlap")
            for identity in identities:
                owner = self._global_identity_space.get(identity)
                if owner is not None and not (
                    prior is not None
                    and owner == space_id
                    and identity in {
                        command.source_artifact_id, command.source_revision_id,
                    }
                ):
                    raise PersistenceIntegrityError("global source identity collision")
            epoch = self._native_epoch + 1
            legacy_revision = self._legacy_sources.get_revision(command.source_revision_id)
            if legacy_revision is None:
                raise PersistenceIntegrityError("legacy revision disappeared")
            source_revision = SourceRevisionV2(
                source_revision_id=command.source_revision_id,
                source_artifact_id=command.source_artifact_id,
                content_sha256=command.body_sha256,
                body_storage=NATIVE_TEXT_BODY_STORAGE,
                created_at=legacy_revision.created_at,
            )
            proof = NativeUtf8SpanProofV1(
                span_id=command.source_span_ref_id,
                source_revision_id=command.source_revision_id,
                evidence_ref_id=command.evidence_ref_id,
                start_byte=command.start_byte, end_byte=command.end_byte,
                slice_sha256=command.slice_sha256,
            )
            unsigned = OperatorSourceAttestationReceiptV1(
                command=command,
                preparation_sha256=prepared.preparation_sha256,
                review_display_sha256=prepared.review_display_sha256,
                actor=approval.actor,
                role=approval.role,  # type: ignore[arg-type]
                auth_method=approval.auth_method,
                approved_at=approval.approved_at,
                source_authority_epoch=epoch,
                record_fingerprint="0" * 64,
            )
            receipt = unsigned.model_copy(update={
                "record_fingerprint": canonical_sha256(
                    unsigned.model_dump(mode="json", exclude={"record_fingerprint"})
                )
            })
            old_artifacts = dict(self._operator_artifacts)
            old_by_revision = dict(self._operator_by_revision)
            old_artifact_receipts = dict(self._operator_artifact_receipts)
            old_spans = dict(self._operator_spans)
            old_receipts = dict(self._operator_receipts)
            old_global = dict(self._global_identity_space)
            old_epoch = self._native_epoch
            try:
                if prior is None:
                    self._operator_artifacts[artifact_key] = _OperatorArtifact(
                        source_revision=source_revision, body=bytes(body),
                        policy_sha256=policy_sha, first_epoch=epoch,
                    )
                    self._operator_by_revision[(space_id, command.source_revision_id)] = (
                        self._operator_artifacts[artifact_key]
                    )
                    self._operator_artifact_receipts[artifact_key] = receipt
                if self._after_operator_artifact_insert is not None:
                    self._after_operator_artifact_insert()
                self._operator_spans[(space_id, proof.span_id)] = (proof, receipt)
                self._operator_receipts[key] = receipt
                self._global_identity_space.update({
                    identity: space_id for identity in identities
                })
                self._native_epoch = epoch
            except Exception:
                self._operator_artifacts = old_artifacts
                self._operator_by_revision = old_by_revision
                self._operator_artifact_receipts = old_artifact_receipts
                self._operator_spans = old_spans
                self._operator_receipts = old_receipts
                self._global_identity_space = old_global
                self._native_epoch = old_epoch
                raise
            return receipt.model_copy(deep=True)

    @staticmethod
    def _occurrence_index(body: bytes, selected: bytes, wanted: int) -> int:
        cursor = 0
        occurrence = 0
        while (index := body.find(selected, cursor)) != -1:
            if index == wanted:
                return occurrence
            occurrence += 1
            cursor = index + 1
        raise PersistenceIntegrityError("prepared passage occurrence disappeared")

    def open_native_source_view(self, space_id: str) -> NativeTextSourceView:
        base = super().open_native_source_view(space_id)
        return _OperatorSourceView(self, base, space_id)


class _OperatorSourceView:
    def __init__(
        self, repo: InMemoryOperatorSourceRepository,
        base: NativeTextSourceView, space_id: str,
    ) -> None:
        self._repo, self._base, self._space_id = repo, base, space_id

    @property
    def epoch(self) -> int:
        return self._base.epoch

    def open_coherent_view(self) -> _OperatorSourceView:
        return _OperatorSourceView(self._repo, self._base.open_coherent_view(), self._space_id)

    def get_provenance_snapshot(
        self, *, artifact_ids: Sequence[str], revision_ids: Sequence[str]
    ) -> KnowledgeProvenanceSnapshot:
        base = self._base.get_provenance_snapshot(
            artifact_ids=artifact_ids, revision_ids=revision_ids,
        )
        artifacts = dict(base.artifacts_by_id)
        revisions = dict(base.revisions_by_id)
        with self._repo._legacy_sources._lock, self._repo._lock:
            for artifact_id in artifact_ids:
                item = self._repo._operator_artifacts.get((self._space_id, artifact_id))
                if item is not None and item.first_epoch <= self.epoch:
                    receipt = self._repo._operator_artifact_receipts.get(
                        (self._space_id, artifact_id)
                    )
                    if receipt is not None:
                        self._repo.get_operator_source_receipt(
                            self._space_id, receipt.command.operation_id
                        )
                        legacy_artifact = self._repo._legacy_sources.get_artifact(artifact_id)
                        if (
                            legacy_artifact is not None
                            and legacy_artifact.status == SourceStatus.ACTIVE
                            and legacy_artifact.current_revision_id
                            == item.source_revision.source_revision_id
                        ):
                            artifacts[artifact_id] = receipt.command.native_policy
            for revision_id in revision_ids:
                if revision_id in revisions:
                    continue
                item = self._repo._operator_by_revision.get((self._space_id, revision_id))
                if item is not None and item.first_epoch <= self.epoch:
                    legacy_artifact = self._repo._legacy_sources.get_artifact(
                        item.source_revision.source_artifact_id
                    )
                    if (
                        legacy_artifact is not None
                        and legacy_artifact.status == SourceStatus.ACTIVE
                        and legacy_artifact.current_revision_id == revision_id
                    ):
                        revisions[revision_id] = item.source_revision
        return _build_snapshot_from_loaded(
            loaded_artifacts=artifacts, loaded_revisions=revisions,
            requested_artifacts=tuple(sorted(set(artifact_ids))),
            requested_revisions=tuple(sorted(set(revision_ids))),
            missing_artifacts=tuple(a for a in artifact_ids if a not in artifacts),
            missing_revisions=tuple(r for r in revision_ids if r not in revisions),
        )

    def get_native_text_source(
        self, *, source_artifact_id: str, source_revision_id: str, span_id: str,
    ) -> StoredNativeTextSource | None:
        base = self._base.get_native_text_source(
            source_artifact_id=source_artifact_id,
            source_revision_id=source_revision_id, span_id=span_id,
        )
        if base is not None:
            return base
        with self._repo._legacy_sources._lock, self._repo._lock:
            pair = self._repo._operator_spans.get((self._space_id, span_id))
            item = self._repo._operator_artifacts.get(
                (self._space_id, source_artifact_id)
            )
            if pair is None or item is None:
                return None
            proof, receipt = pair
            if (
                receipt.source_authority_epoch > self.epoch
                or receipt.command.source_artifact_id != source_artifact_id
                or receipt.command.source_revision_id != source_revision_id
                or item.source_revision.source_revision_id != source_revision_id
            ):
                return None
            self._repo.get_operator_source_receipt(
                self._space_id, receipt.command.operation_id
            )
            if hashlib.sha256(item.body).hexdigest() != item.source_revision.content_sha256:
                raise PersistenceIntegrityError("operator source body drift")
            legacy_artifact = self._repo._legacy_sources.get_artifact(source_artifact_id)
            legacy_revision = self._repo._legacy_sources.get_revision(source_revision_id)
            if legacy_revision is None or legacy_revision.content_sha256 != (
                item.source_revision.content_sha256
            ):
                raise PersistenceIntegrityError("legacy/native body digest drift")
            if (
                legacy_artifact is None or legacy_artifact.status != SourceStatus.ACTIVE
                or legacy_artifact.current_revision_id != source_revision_id
            ):
                return None
            return StoredNativeTextSource(
                source_artifact=receipt.command.native_policy.model_copy(deep=True),
                source_revision=item.source_revision.model_copy(deep=True),
                body_bytes=bytes(item.body), span_proof=proof.model_copy(deep=True),
                authority_epoch=receipt.source_authority_epoch,
            )
