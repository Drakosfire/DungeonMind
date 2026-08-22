"""Transport-neutral direct World Graph projection service.

This module is the application-layer read seam for consumers that need one
exact, admissibility-scoped DungeonMind graph revision without invoking a Mind
Turn, semantic retrieval, or a product-specific adapter.

The service deliberately composes existing authorities rather than defining a
second graph model:

``WorldGraphProjectionRequestV2``
→ exact head / revision resolution through ``WorldGraphRepository``
→ versioned graph parsing through ``GraphSnapshotReader``
→ campaign / admissibility / provenance projection through ``graph_scope``
→ ``ProjectionSnapshotV2`` + ``ScopedGraphProjection``

``focus`` and ``query_text`` remain request context for successor retrieval and
salience layers; this foundational service does not invent focus filtering or
lexical/semantic query behavior. It also performs no durable writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from ..contracts.projection_v2 import ProjectionSnapshotV2, WorldGraphProjectionRequestV2
from ..domain.errors import HeadNotFoundError, RevisionNotFoundError, ScopeResolutionError
from .graph_scope import ScopedGraphProjection, project_scoped_snapshot
from .graph_snapshot import GraphSnapshotReader, ParsedGraphSnapshot
from .repositories import SourceRepository, WorldGraphRepository
from .world_graph_observability import (
    NOOP_READ_OBSERVER,
    PhaseRecorder,
    RequestObservationFields,
    SystemMonotonicReadClock,
    WorldGraphReadClock,
    WorldGraphReadObservation,
    WorldGraphReadObserver,
    classify_read_failure,
    emit_read_observation,
)


class ProjectionClock(Protocol):
    """Clock port used only to stamp the resolved projection identity."""

    def now(self) -> datetime: ...


class _SystemProjectionClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class WorldGraphProjectionResult:
    """One exact resolved revision plus its safely scoped graph view."""

    snapshot: ProjectionSnapshotV2
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
        read_observer: WorldGraphReadObserver | None = None,
        read_clock: WorldGraphReadClock | None = None,
    ) -> None:
        self._world_graph = world_graph
        self._sources = sources
        self._graph_reader = graph_reader
        self._clock = clock or _SystemProjectionClock()
        self._read_observer = (
            read_observer if read_observer is not None else NOOP_READ_OBSERVER
        )
        self._read_clock = read_clock or SystemMonotonicReadClock()

    def project(self, request: WorldGraphProjectionRequestV2) -> WorldGraphProjectionResult:
        """Resolve, parse, scope, and identify one coherent graph revision.

        Unpinned reads resolve the current head exactly once and report the
        selected revision. Explicit pins read that immutable revision while
        still reporting the current head. Missing or cross-world state fails
        closed with the existing typed DungeonMind read errors.

        Emits exactly one terminal ``project`` observation per invocation
        (success or error) through the optional read observer; observation
        never changes projection semantics.
        """

        recorder = PhaseRecorder(self._read_clock)
        try:
            result, parsed = self._project_observed(request, recorder)
        except Exception as exc:
            self._emit(
                self._error_observation(recorder, request, exc),
            )
            raise
        self._emit(self._success_observation(recorder, request, result, parsed))
        return result

    def _project_observed(
        self,
        request: WorldGraphProjectionRequestV2,
        recorder: PhaseRecorder,
    ) -> tuple[WorldGraphProjectionResult, ParsedGraphSnapshot]:
        with recorder.phase("head_lookup"):
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
        with recorder.phase("revision_load"):
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

        with recorder.phase("parse"):
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

        with recorder.phase("scope_projection"):
            scoped = project_scoped_snapshot(
                parsed,
                sources=self._sources,
                world_id=request.world_id,
                campaign_id=request.campaign_id,
                admissibility=request.admissibility,
                scope_mode=request.scope_mode,
            )
        snapshot = ProjectionSnapshotV2(
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
        return WorldGraphProjectionResult(snapshot=snapshot, scoped_graph=scoped), parsed

    def _emit(self, observation: WorldGraphReadObservation) -> None:
        emit_read_observation(self._read_observer, observation)

    @staticmethod
    def _request_fields(
        request: WorldGraphProjectionRequestV2,
    ) -> RequestObservationFields:
        return {
            "pinned_read": request.revision_pin is not None,
            "scope_mode": str(request.scope_mode),
            "admissibility": str(request.admissibility),
        }

    def _error_observation(
        self,
        recorder: PhaseRecorder,
        request: WorldGraphProjectionRequestV2,
        exc: Exception,
    ) -> WorldGraphReadObservation:
        return WorldGraphReadObservation(
            operation="project",
            outcome="error",
            duration_seconds=recorder.total_seconds(),
            phase_durations=recorder.phases,
            failure_code=classify_read_failure(exc),
            **self._request_fields(request),
        )

    def _success_observation(
        self,
        recorder: PhaseRecorder,
        request: WorldGraphProjectionRequestV2,
        result: WorldGraphProjectionResult,
        parsed: ParsedGraphSnapshot,
    ) -> WorldGraphReadObservation:
        admitted = result.scoped_graph.snapshot
        scoped = result.scoped_graph
        scope_unknown = sum(
            1
            for exclusion in (
                *scoped.object_exclusions.values(),
                *scoped.relationship_exclusions.values(),
                *scoped.assertion_exclusions.values(),
            )
            if exclusion.scope_unknown
        )
        return WorldGraphReadObservation(
            operation="project",
            outcome="success",
            duration_seconds=recorder.total_seconds(),
            phase_durations=recorder.phases,
            graph_schema=parsed.graph_schema,
            parsed_object_count=len(parsed.objects),
            parsed_relationship_count=len(parsed.relationships),
            parsed_evidence_count=len(parsed.evidence),
            admitted_object_count=len(admitted.objects),
            admitted_relationship_count=len(admitted.relationships),
            admitted_evidence_count=len(admitted.evidence),
            excluded_object_count=len(scoped.object_exclusions),
            excluded_relationship_count=len(scoped.relationship_exclusions),
            excluded_assertion_count=len(scoped.assertion_exclusions),
            provenance_rejected_count=len(scoped.rejections),
            scope_unknown_exclusion_count=scope_unknown,
            **self._request_fields(request),
        )


__all__ = [
    "ProjectionClock",
    "WorldGraphProjectionResult",
    "WorldGraphProjectionService",
]
