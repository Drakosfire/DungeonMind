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

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from ..contracts.projection_v2 import ProjectionSnapshotV2, WorldGraphProjectionRequestV2
from ..domain.errors import HeadNotFoundError, RevisionNotFoundError, ScopeResolutionError
from .graph_scope import EvidenceResolution, ScopedGraphProjection, project_scoped_snapshot
from .graph_snapshot import GraphSnapshotReader, ParsedGraphSnapshot
from .parsed_revision_cache import (
    DEFAULT_PARSED_REVISION_CACHE_MAX_ENTRIES,
    ParsedImmutableRevisionCache,
)
from .repositories import SourceRepository, WorldGraphRepository
from .source_provenance_snapshot import provenance_refs_from_parsed_graph
from .world_graph_observability import (
    NOOP_READ_OBSERVER,
    GraphObservationFields,
    PhaseRecorder,
    RequestObservationFields,
    SystemMonotonicReadClock,
    WorldGraphReadClock,
    WorldGraphReadObservation,
    WorldGraphReadObserver,
    classify_read_failure,
    emit_read_observation,
)
from .world_graph_read_context import WorldGraphReadContext


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

    @classmethod
    def from_read_context(cls, context: WorldGraphReadContext) -> WorldGraphProjectionResult:
        return cls(snapshot=context.identity, scoped_graph=context.scoped_graph)


def _scoped_count_fields(scoped: ScopedGraphProjection) -> GraphObservationFields:
    """Admitted/excluded counts for one completed scope projection."""

    admitted = scoped.snapshot
    scope_unknown = sum(
        1
        for exclusion in (
            *scoped.object_exclusions.values(),
            *scoped.relationship_exclusions.values(),
            *scoped.assertion_exclusions.values(),
        )
        if exclusion.scope_unknown
    )
    return {
        "graph_schema": admitted.graph_schema,
        "admitted_object_count": len(admitted.objects),
        "admitted_relationship_count": len(admitted.relationships),
        "admitted_evidence_count": len(admitted.evidence),
        "excluded_object_count": len(scoped.object_exclusions),
        "excluded_relationship_count": len(scoped.relationship_exclusions),
        "excluded_assertion_count": len(scoped.assertion_exclusions),
        "provenance_rejected_count": len(scoped.rejections),
        "scope_unknown_exclusion_count": scope_unknown,
    }


@dataclass
class _ProjectionObservationFacts:
    """Graph facts that become known progressively during one projection.

    Populated as phases complete so a late failure still reports everything
    already determined; the error path reads this holder. Counts and bounded
    schema strings only — never identity or content.
    """

    graph_schema: str | None = None
    parsed_object_count: int | None = None
    parsed_relationship_count: int | None = None
    parsed_evidence_count: int | None = None
    scoped_counts: GraphObservationFields | None = None
    parsed_revision_cache_hit: bool | None = None
    source_artifact_count: int | None = None
    source_revision_count: int | None = None


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
        parsed_revision_cache: ParsedImmutableRevisionCache | None = None,
        parsed_revision_cache_max_entries: int = DEFAULT_PARSED_REVISION_CACHE_MAX_ENTRIES,
    ) -> None:
        self._world_graph = world_graph
        self._sources = sources
        self._graph_reader = graph_reader
        self._clock = clock or _SystemProjectionClock()
        self._read_observer = (
            read_observer if read_observer is not None else NOOP_READ_OBSERVER
        )
        self._read_clock = read_clock or SystemMonotonicReadClock()
        self._parsed_revisions = parsed_revision_cache or ParsedImmutableRevisionCache(
            max_entries=parsed_revision_cache_max_entries
        )

    @property
    def parsed_revision_cache(self) -> ParsedImmutableRevisionCache:
        return self._parsed_revisions

    def open_read_context(
        self, request: WorldGraphProjectionRequestV2
    ) -> WorldGraphReadContext:
        """Establish one coherent native read: revision, parse, source snapshot, scope.

        Public ``project`` remains the compatibility wrapper over this seam.
        """

        recorder = PhaseRecorder(self._read_clock)
        facts = _ProjectionObservationFacts()
        try:
            context = self._open_observed(request, recorder, facts)
        except Exception as exc:
            self._emit(self._error_observation(recorder, request, exc, facts))
            raise
        result = WorldGraphProjectionResult.from_read_context(context)
        self._emit(self._success_observation(recorder, request, result, context.parsed, facts))
        return context

    def project(self, request: WorldGraphProjectionRequestV2) -> WorldGraphProjectionResult:
        """Resolve, parse, scope, and identify one coherent graph revision.

        Unpinned reads resolve the current head exactly once and report the
        selected revision. Explicit pins read that immutable revision while
        still reporting the current head. Missing or cross-world state fails
        closed with the existing typed DungeonMind read errors.

        Emits exactly one terminal ``project`` observation per invocation
        (success or error) through the optional read observer; observation
        never changes projection semantics. On a late failure the error
        observation still carries every graph fact that was already
        determined (parsed counts after parse, admitted counts after scope
        projection); fields are absent only when the failure preceded them.
        """

        return WorldGraphProjectionResult.from_read_context(self.open_read_context(request))

    def _open_observed(
        self,
        request: WorldGraphProjectionRequestV2,
        recorder: PhaseRecorder,
        facts: _ProjectionObservationFacts,
    ) -> WorldGraphReadContext:
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
            parsed, cache_hit = self._parsed_revisions.get_or_load(
                request.world_id,
                revision_id,
                lambda: self._graph_reader.parse(
                    graph_schema=stored.revision.graph_schema,
                    graph_payload=stored.graph_payload,
                ),
            )
        facts.parsed_revision_cache_hit = cache_hit
        facts.graph_schema = parsed.graph_schema
        facts.parsed_object_count = len(parsed.objects)
        facts.parsed_relationship_count = len(parsed.relationships)
        facts.parsed_evidence_count = len(parsed.evidence)
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

        artifact_ids, revision_ids = provenance_refs_from_parsed_graph(parsed)
        with recorder.phase("source_snapshot_load"):
            source_snapshot = self._sources.get_provenance_snapshot(
                artifact_ids=artifact_ids,
                revision_ids=revision_ids,
            )
        facts.source_artifact_count = source_snapshot.artifact_count
        facts.source_revision_count = source_snapshot.revision_count

        evidence_memo: dict[str, EvidenceResolution] = {}
        with recorder.phase("scope_projection"):
            scoped = project_scoped_snapshot(
                parsed,
                sources=source_snapshot,
                world_id=request.world_id,
                campaign_id=request.campaign_id,
                admissibility=request.admissibility,
                scope_mode=request.scope_mode,
                evidence_cache=evidence_memo,
            )
        facts.scoped_counts = _scoped_count_fields(scoped)
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
        return WorldGraphReadContext(
            identity=snapshot,
            parsed=parsed,
            scoped_graph=scoped,
            source_snapshot=source_snapshot,
            parsed_revision_cache_hit=cache_hit,
            _evidence_memo=evidence_memo,
        )

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
        facts: _ProjectionObservationFacts,
    ) -> WorldGraphReadObservation:
        observation = WorldGraphReadObservation(
            operation="project",
            outcome="error",
            duration_seconds=recorder.total_seconds(),
            phase_durations=recorder.phases,
            failure_code=classify_read_failure(exc),
            graph_schema=facts.graph_schema,
            parsed_object_count=facts.parsed_object_count,
            parsed_relationship_count=facts.parsed_relationship_count,
            parsed_evidence_count=facts.parsed_evidence_count,
            parsed_revision_cache_hit=facts.parsed_revision_cache_hit,
            source_artifact_count=facts.source_artifact_count,
            source_revision_count=facts.source_revision_count,
            **self._request_fields(request),
        )
        if facts.scoped_counts is not None:
            observation = replace(observation, **facts.scoped_counts)
        return observation

    def _success_observation(
        self,
        recorder: PhaseRecorder,
        request: WorldGraphProjectionRequestV2,
        result: WorldGraphProjectionResult,
        parsed: ParsedGraphSnapshot,
        facts: _ProjectionObservationFacts,
    ) -> WorldGraphReadObservation:
        # Reuse the counts computed when scope projection completed; a second
        # graph-sized exclusion scan here would change the cost profile this
        # seam exists to characterize.
        scoped_counts = facts.scoped_counts
        if scoped_counts is None:
            # Unreachable on the success path (scope projection completed);
            # observation construction must never break the read.
            scoped_counts = _scoped_count_fields(result.scoped_graph)
        return WorldGraphReadObservation(
            operation="project",
            outcome="success",
            duration_seconds=recorder.total_seconds(),
            phase_durations=recorder.phases,
            parsed_object_count=len(parsed.objects),
            parsed_relationship_count=len(parsed.relationships),
            parsed_evidence_count=len(parsed.evidence),
            parsed_revision_cache_hit=facts.parsed_revision_cache_hit,
            source_artifact_count=facts.source_artifact_count,
            source_revision_count=facts.source_revision_count,
            **self._request_fields(request),
            **scoped_counts,
        )


__all__ = [
    "ProjectionClock",
    "WorldGraphProjectionResult",
    "WorldGraphProjectionService",
    "WorldGraphReadContext",
]
