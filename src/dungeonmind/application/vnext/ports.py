"""Transport-neutral read ports for vNext knowledge admission."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .provenance import KnowledgeProvenanceSnapshot


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
