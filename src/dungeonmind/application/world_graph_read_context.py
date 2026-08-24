"""Application-layer World Graph read context (R.3a).

One coherent read establishes:

* the exact selected graph revision and current head;
* a parsed immutable graph snapshot (safe to reuse across reads);
* one coherent current source/provenance snapshot;
* the scoped/admitted projection for this request;
* memoized evidence-chain resolution for this context only.

The context is not durable authority, agent memory, or a product session. It
is a reusable application computation. Public R.1/R.2 result contracts stay
unchanged; retrieval consumes the context instead of recomputing projection
and provenance facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts.projection_v2 import ProjectionSnapshotV2
from .graph_scope import (
    EvidenceResolution,
    ScopedGraphProjection,
    resolve_evidence_provenance,
)
from .graph_snapshot import ParsedGraphSnapshot
from .source_provenance_snapshot import SourceProvenanceSnapshot


@dataclass
class WorldGraphReadContext:
    """Facts established for one coherent native World Graph read."""

    identity: ProjectionSnapshotV2
    parsed: ParsedGraphSnapshot
    scoped_graph: ScopedGraphProjection
    source_snapshot: SourceProvenanceSnapshot
    parsed_revision_cache_hit: bool
    _evidence_memo: dict[str, EvidenceResolution] = field(default_factory=dict)

    @property
    def graph(self) -> ParsedGraphSnapshot:
        """Admitted graph snapshot (same convenience as the projection result)."""

        return self.scoped_graph.snapshot

    @property
    def evidence_memo_size(self) -> int:
        return len(self._evidence_memo)

    def resolve_evidence(self, evidence_ref_id: str) -> EvidenceResolution:
        """Resolve one evidence chain, once, against this context's snapshot."""

        if evidence_ref_id in self._evidence_memo:
            return self._evidence_memo[evidence_ref_id]
        resolved = resolve_evidence_provenance(
            evidence_ref_id,
            snapshot=self.parsed,
            sources=self.source_snapshot,
            world_id=self.identity.world_id,
            campaign_id=self.identity.campaign_id,
            admissibility=self.identity.admissibility,
            scope_mode=self.identity.scope_mode,
            evidence_cache=self._evidence_memo,
        )
        return resolved


__all__ = [
    "EvidenceResolution",
    "WorldGraphReadContext",
]
