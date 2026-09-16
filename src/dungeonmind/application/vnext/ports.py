"""Transport-neutral read ports for vNext knowledge admission."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .provenance import KnowledgeProvenanceSnapshot


class KnowledgeSourceReader(Protocol):
    """Read-only source/provenance access for one coherent admission operation."""

    def open_coherent_view(self) -> KnowledgeSourceReader:
        """Return a frozen view of current source authority for pinning at context construction."""
        ...

    def get_provenance_snapshot(
        self,
        *,
        artifact_ids: Sequence[str],
        revision_ids: Sequence[str],
    ) -> KnowledgeProvenanceSnapshot: ...
