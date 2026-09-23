"""Transport-neutral read ports for vNext knowledge admission."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from dungeonmind.contracts.vnext.knowledge import KnowledgeHead, PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.prospective import (
    KnowledgeProspectivePublication,
    ProspectiveResultBinding,
)
from dungeonmind.contracts.vnext.publication import KnowledgePublicationReceipt

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
