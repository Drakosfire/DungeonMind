"""Transport-neutral direct World Graph projection service.

This module is the application-layer read seam for consumers that need one
exact, admissibility-scoped DungeonMind graph revision without invoking a Mind
Turn, semantic retrieval, or a product-specific adapter.

The service deliberately composes existing authorities rather than defining a
second graph model:

``WorldGraphProjectionRequest``
→ exact head / revision resolution through ``WorldGraphRepository``
→ versioned graph parsing through ``GraphSnapshotReader``
→ campaign / admissibility / provenance projection through ``graph_scope``
→ ``ProjectionSnapshot`` + ``ScopedGraphProjection``

``focus`` and ``query_text`` remain request context for successor retrieval and
salience layers; this foundational service does not invent focus filtering or
lexical/semantic query behavior. It also performs no durable writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from ..contracts.projection import ProjectionSnapshot, WorldGraphProjectionRequest
from ..domain.errors import HeadNotFoundError, RevisionNotFoundError, ScopeResolutionError
from .graph_scope import ScopedGraphProjection, project_scoped_snapshot
from .graph_snapshot import GraphSnapshotReader, ParsedGraphSnapshot
from .repositories import SourceRepository, WorldGraphRepository


class ProjectionClock(Protocol):
    """Clock port used only to stamp the resolved projection identity."""

    def now(self) -> datetime: ...


class _SystemProjectionClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class WorldGraphProjectionResult:
    """One exact resolved revision plus its safely scoped graph view."""

    snapshot: ProjectionSnapshot
    scoped_graph: ScopedGraphProjection

    @property
    def graph(self) -> ParsedGraphSnapshot:
        """Convenience access to the admitted graph snapshot."""

        return self.scoped_graph.snapshot


class WorldGraphProjectionService:
    """Resolve and safely project one exact DungeonMind World Graph revision.

    A graph reader is required instead of silently constructing a semantic
    profile registry. Deployments serving profile-pinned v3+ graphs must inject
    the reader configured for those exact profile revisions.
    """

    def __init__(
        self,
        *,
        world_graph: WorldGraphRepository,
        sources: SourceRepository,
        graph_reader: GraphSnapshotReader,
        clock: ProjectionClock | None = None,
    ) -> None:
        self._world_graph = world_graph
        self._sources = sources
        self._graph_reader = graph_reader
        self._clock = clock or _SystemProjectionClock()

    def project(self, request: WorldGraphProjectionRequest) -> WorldGraphProjectionResult:
        """Resolve, parse, scope, and identify one coherent graph revision.

        Unpinned reads resolve the current head exactly once and report the
        selected revision. Explicit pins read that immutable revision while
        still reporting the current head. Missing or cross-world state fails
        closed with the existing typed DungeonMind read errors.
        """

        head = self._world_graph.get_head(request.world_id)
        if head is None:
            raise HeadNotFoundError(f"no graph head for world {request.world_id!r}")
        if head.world_id != request.world_id:
            raise ScopeResolutionError(
                "resolved graph head belongs to a different world",
                details={
                    "requested_world_id": request.world_id,
                    "resolved_world_id": head.world_id,
                    "reason": "head_world_mismatch",
                },
            )

        head_revision_id = head.head_revision_id
        revision_id = request.revision_pin or head_revision_id
        stored = self._world_graph.get_revision(request.world_id, revision_id)
        if stored is None:
            raise RevisionNotFoundError(
                f"revision {revision_id!r} not found for world {request.world_id!r}"
            )
        if stored.revision.world_id != request.world_id:
            raise ScopeResolutionError(
                "resolved graph revision belongs to a different world",
                details={
                    "requested_world_id": request.world_id,
                    "resolved_world_id": stored.revision.world_id,
                    "revision_id": revision_id,
                    "reason": "revision_world_mismatch",
                },
            )
        if stored.revision.revision_id != revision_id:
            raise ScopeResolutionError(
                "graph repository returned a different revision than requested",
                details={
                    "world_id": request.world_id,
                    "requested_revision_id": revision_id,
                    "resolved_revision_id": stored.revision.revision_id,
                    "reason": "revision_identity_mismatch",
                },
            )

        parsed = self._graph_reader.parse(
            graph_schema=stored.revision.graph_schema,
            graph_payload=stored.graph_payload,
        )
        if parsed.world_id != request.world_id:
            raise ScopeResolutionError(
                "stored graph payload belongs to a different world",
                details={
                    "requested_world_id": request.world_id,
                    "payload_world_id": parsed.world_id,
                    "revision_id": revision_id,
                    "reason": "payload_world_mismatch",
                },
            )

        scoped = project_scoped_snapshot(
            parsed,
            sources=self._sources,
            world_id=request.world_id,
            campaign_id=request.campaign_id,
            admissibility=request.admissibility,
            scope_mode=request.scope_mode,
        )
        snapshot = ProjectionSnapshot(
            world_id=request.world_id,
            campaign_id=request.campaign_id,
            focus=request.focus,
            admissibility=request.admissibility,
            scope_mode=request.scope_mode,
            revision_id=revision_id,
            head_revision_id=head_revision_id,
            is_head=revision_id == head_revision_id,
            projected_at=self._clock.now(),
        )
        return WorldGraphProjectionResult(snapshot=snapshot, scoped_graph=scoped)


__all__ = [
    "ProjectionClock",
    "WorldGraphProjectionResult",
    "WorldGraphProjectionService",
]
