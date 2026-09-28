"""Transport-neutral read ports for vNext knowledge admission."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    SemanticProfileDescriptorV2,
    SemanticProfileDescriptorV3,
)
from dungeonmind.contracts.vnext.knowledge import KnowledgeHead, PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.native_source import (
    NativeSourceAdmissionReceiptV1,
    NativeTextSourceAdmissionV1,
    NativeUtf8SpanProofV1,
)
from dungeonmind.contracts.vnext.prospective import (
    KnowledgeProspectivePublication,
    ProspectiveResultBinding,
)
from dungeonmind.contracts.vnext.publication import KnowledgePublicationReceipt
from dungeonmind.contracts.vnext.source import SourceArtifactV3, SourceRevisionV2

from .provenance import KnowledgeProvenanceSnapshot
from .records import KnowledgeHeadEvent, StoredKnowledgeRevision


class KnowledgeSourceReader(Protocol):
    """Read-only source/provenance access for one coherent admission operation."""

    def open_coherent_view(self) -> KnowledgeSourceReader:
        """Pin the current source authority epoch/generation for context construction.

        Implementations must be O(1): pin an epoch only, without preloading or deep-copying
        the full source store. Candidate-local materialization happens in
        ``get_provenance_snapshot`` for the requested ids only.
        """
        ...

    def get_provenance_snapshot(
        self,
        *,
        artifact_ids: Sequence[str],
        revision_ids: Sequence[str],
    ) -> KnowledgeProvenanceSnapshot: ...


class KnowledgeRevisionRepository(Protocol):
    """Native vNext revision/head authority. Not a product write API."""

    def get_head(self, space_id: str) -> KnowledgeHead | None: ...

    def get_revision(self, space_id: str, revision_id: str) -> StoredKnowledgeRevision | None: ...

    def publish_revision(
        self, command: PublishKnowledgeRevisionCommand
    ) -> StoredKnowledgeRevision: ...

    def publish_publication(
        self, command: PublishKnowledgeRevisionCommand, publication_id: str
    ) -> KnowledgePublicationReceipt: ...

    def get_publication_receipt(
        self, space_id: str, publication_id: str
    ) -> KnowledgePublicationReceipt | None: ...

    def publish_prospective_publication(
        self,
        command: PublishKnowledgeRevisionCommand,
        publication_id: str,
        prospective_request_sha256: str,
        result_bindings: Sequence[ProspectiveResultBinding],
    ) -> KnowledgeProspectivePublication: ...

    def get_prospective_publication(
        self, space_id: str, publication_id: str
    ) -> KnowledgeProspectivePublication | None: ...

    def head_events(self, space_id: str) -> tuple[KnowledgeHeadEvent, ...]: ...


@dataclass(frozen=True, slots=True)
class StoredNativeTextSource:
    """One exact-space native source record returned from a pinned source epoch."""

    source_artifact: SourceArtifactV3
    source_revision: SourceRevisionV2
    body_bytes: bytes
    span_proof: NativeUtf8SpanProofV1
    authority_epoch: int


class NativeTextSourceView(Protocol):
    """O(1) epoch-pinned native provenance and body reader."""

    @property
    def epoch(self) -> int: ...

    def open_coherent_view(self) -> NativeTextSourceView: ...

    def get_provenance_snapshot(
        self,
        *,
        artifact_ids: Sequence[str],
        revision_ids: Sequence[str],
    ) -> KnowledgeProvenanceSnapshot: ...

    def get_native_text_source(
        self,
        *,
        source_artifact_id: str,
        source_revision_id: str,
        span_id: str,
    ) -> StoredNativeTextSource | None: ...


class NativeSourceEvidenceRepository(KnowledgeRevisionRepository, Protocol):
    """Atomic text-source admission plus exact-space native source reading."""

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
    ) -> NativeSourceAdmissionReceiptV1: ...

    def get_native_source_admission_receipt(
        self,
        space_id: str,
        admission_id: str,
    ) -> NativeSourceAdmissionReceiptV1 | None: ...

    def open_native_source_view(self, space_id: str) -> NativeTextSourceView: ...
