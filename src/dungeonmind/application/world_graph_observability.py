"""Application-owned, vendor-neutral World Graph read observability (R.2a).

This module is the DungeonMind-native observation seam for the direct World
Graph read path (R.1 projection + R.2 retrieval). It is deliberately small:

``WorldGraphReadObservation`` — one immutable terminal fact emitted after one
public read method invocation, once its semantic result or error is known;
``WorldGraphReadPhaseDuration`` — one immutable ``(phase, seconds)`` entry;
``WorldGraphReadObserver`` — the injection port with a single ``observe`` call;
``WorldGraphReadClock`` — monotonic nanosecond timing port;
``PhaseRecorder`` — accumulates monotonic phase timings inside an operation;
``emit_read_observation`` — fail-open terminal dispatch;
``classify_read_failure`` — stable failure-class mapping.

Content safety is structural. Observation fields are closed vocabularies,
booleans, bounded policy/schema values, counts, and durations only. No graph,
user, or source identity or text can enter an observation value, because no
field exists that could carry it; nothing is redacted after the fact.

The observer is not graph authority. It receives terminal facts after a read
is evaluated; it cannot select revisions, admit evidence, broaden scope,
mutate repositories, or alter return values. Observer failure is fail-open,
is swallowed at the dispatch boundary, and is never persisted as graph or
retrieval state. No vendor SDK, exporter, or transport lives here; deployment
adapters may bridge this port to their own telemetry stack outside core.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypedDict

from ..domain.errors import (
    DungeonMindError,
    HeadNotFoundError,
    RevisionNotFoundError,
    ScopeResolutionError,
)


class RequestObservationFields(TypedDict):
    """Request policy fields shared by every observation. Values only."""

    pinned_read: bool
    scope_mode: str
    admissibility: str


class GraphObservationFields(TypedDict):
    """Admitted-graph and exclusion counts known after one projection."""

    graph_schema: str
    admitted_object_count: int
    admitted_relationship_count: int
    admitted_evidence_count: int
    excluded_object_count: int
    excluded_relationship_count: int
    excluded_assertion_count: int
    provenance_rejected_count: int
    scope_unknown_exclusion_count: int


class CoverageObservationFields(TypedDict):
    """Coverage/truncation facts as counts and stable field names only."""

    truncated_fields: tuple[str, ...]
    coverage_gap_count: int
    coverage_missing_count: int

WorldGraphReadOperation = Literal[
    "project",
    "get_object",
    "search",
    "get_neighborhood",
    "get_evidence",
    "resolve_source_anchor",
]
"""Closed vocabulary of instrumented direct-read operations."""

WorldGraphReadOutcome = Literal["success", "miss", "error"]
"""Closed terminal outcome vocabulary for one operation invocation."""

WorldGraphReadFailureCode = Literal[
    "head_not_found",
    "revision_not_found",
    "scope_resolution",
    "invalid_input",
    "graph_read_failed",
    "unexpected",
]
"""Stable failure classes. Never an exception class name or message string."""

WorldGraphReadPhase = Literal[
    "head_lookup",
    "revision_load",
    "parse",
    "scope_projection",
    "projection",
    "object_selection",
    "referent_and_lexical_scoring",
    "traversal",
    "evidence_revalidation",
    "anchor_derivation",
]
"""Closed semantic phase vocabulary. Phases are not helper names."""

READ_OPERATIONS: frozenset[str] = frozenset(WorldGraphReadOperation.__args__)
READ_OUTCOMES: frozenset[str] = frozenset(WorldGraphReadOutcome.__args__)
READ_FAILURE_CODES: frozenset[str] = frozenset(WorldGraphReadFailureCode.__args__)
READ_PHASES: frozenset[str] = frozenset(WorldGraphReadPhase.__args__)


class WorldGraphReadClock(Protocol):
    """Monotonic nanosecond timing port. Never wall clock or UTC stamps."""

    def now_ns(self) -> int: ...


class SystemMonotonicReadClock:
    """Default monotonic clock backed by ``time.perf_counter_ns``."""

    def now_ns(self) -> int:
        return time.perf_counter_ns()


@dataclass(frozen=True)
class WorldGraphReadPhaseDuration:
    """One reached phase and its monotonic elapsed seconds (>= 0)."""

    phase: WorldGraphReadPhase
    duration_seconds: float

    def __post_init__(self) -> None:
        if self.duration_seconds < 0:
            raise ValueError("phase duration_seconds must be non-negative")


@dataclass(frozen=True)
class WorldGraphReadObservation:
    """One privacy-safe terminal fact about one direct graph read.

    Required fields are always present. Optional count fields are ``None``
    when the operation failed before the information existed or the field is
    not applicable to that operation. Every value is a closed vocabulary
    member, boolean, bounded policy/schema string, integer count, or duration;
    no request, graph, user, or source identity or text is representable.
    """

    operation: WorldGraphReadOperation
    outcome: WorldGraphReadOutcome
    duration_seconds: float
    phase_durations: tuple[WorldGraphReadPhaseDuration, ...]
    pinned_read: bool
    scope_mode: str
    admissibility: str
    failure_code: WorldGraphReadFailureCode | None = None
    graph_schema: str | None = None
    parsed_object_count: int | None = None
    parsed_relationship_count: int | None = None
    parsed_evidence_count: int | None = None
    admitted_object_count: int | None = None
    admitted_relationship_count: int | None = None
    admitted_evidence_count: int | None = None
    excluded_object_count: int | None = None
    excluded_relationship_count: int | None = None
    excluded_assertion_count: int | None = None
    provenance_rejected_count: int | None = None
    scope_unknown_exclusion_count: int | None = None
    result_object_count: int | None = None
    result_relationship_count: int | None = None
    result_assertion_count: int | None = None
    result_anchor_count: int | None = None
    requested_seed_count: int | None = None
    present_seed_count: int | None = None
    missing_seed_count: int | None = None
    truncated_fields: tuple[str, ...] = ()
    neighborhood_depth: int | None = None
    coverage_gap_count: int | None = None
    coverage_missing_count: int | None = None

    def __post_init__(self) -> None:
        if self.duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")
        if self.operation not in READ_OPERATIONS:
            raise ValueError(f"unknown read operation {self.operation!r}")
        if self.outcome not in READ_OUTCOMES:
            raise ValueError(f"unknown read outcome {self.outcome!r}")
        if self.failure_code is not None and self.failure_code not in READ_FAILURE_CODES:
            raise ValueError(f"unknown read failure code {self.failure_code!r}")
        if (self.outcome == "error") != (self.failure_code is not None):
            raise ValueError("error outcome requires failure_code and vice versa")
        if self.neighborhood_depth is not None and self.neighborhood_depth not in (1, 2):
            raise ValueError("neighborhood_depth must be 1 or 2 when present")


class WorldGraphReadObserver(Protocol):
    """Terminal observation sink. Not graph authority; strictly fail-open."""

    def observe(self, observation: WorldGraphReadObservation) -> None: ...


class _NoOpWorldGraphReadObserver:
    def observe(self, observation: WorldGraphReadObservation) -> None:
        return None


NOOP_READ_OBSERVER: WorldGraphReadObserver = _NoOpWorldGraphReadObserver()
"""Default observer: receives terminal facts and does nothing."""


def classify_read_failure(exc: BaseException) -> WorldGraphReadFailureCode:
    """Map an exception onto the stable failure-class vocabulary.

    Only known authority/input classes are distinguished. Anything else maps
    to ``unexpected``; exception class names and message text never leave the
    process through an observation value.
    """

    if isinstance(exc, HeadNotFoundError):
        return "head_not_found"
    if isinstance(exc, RevisionNotFoundError):
        return "revision_not_found"
    if isinstance(exc, ScopeResolutionError):
        return "scope_resolution"
    if isinstance(exc, ValueError):
        return "invalid_input"
    if isinstance(exc, DungeonMindError):
        return "graph_read_failed"
    return "unexpected"


def emit_read_observation(
    observer: WorldGraphReadObserver,
    observation: WorldGraphReadObservation,
) -> None:
    """Fail-open terminal dispatch.

    An observer exception is swallowed at this boundary: it must never change
    a successful read result and never mask an original graph-read error. Core
    deliberately does not log the observer failure; a deployment adapter owns
    reporting its own sink failures.
    """

    with suppress(Exception):
        observer.observe(observation)



@dataclass
class PhaseRecorder:
    """Accumulates monotonic phase timings for one operation invocation.

    Phase timing never duplicates work: a phase wraps the real call exactly
    once. Phases are not required to sum to the total; result assembly and
    interpreter overhead legitimately remain in the difference.
    """

    _clock: WorldGraphReadClock
    _start_ns: int = field(init=False)
    _phases: list[WorldGraphReadPhaseDuration] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self._start_ns = self._clock.now_ns()

    @contextmanager
    def phase(self, name: WorldGraphReadPhase) -> Iterator[None]:
        start_ns = self._clock.now_ns()
        try:
            yield
        finally:
            elapsed_ns = self._clock.now_ns() - start_ns
            self._phases.append(
                WorldGraphReadPhaseDuration(
                    phase=name,
                    duration_seconds=elapsed_ns / 1_000_000_000,
                )
            )

    def total_seconds(self) -> float:
        return (self._clock.now_ns() - self._start_ns) / 1_000_000_000

    @property
    def phases(self) -> tuple[WorldGraphReadPhaseDuration, ...]:
        return tuple(self._phases)


__all__ = [
    "NOOP_READ_OBSERVER",
    "READ_FAILURE_CODES",
    "READ_OPERATIONS",
    "READ_OUTCOMES",
    "READ_PHASES",
    "CoverageObservationFields",
    "GraphObservationFields",
    "PhaseRecorder",
    "RequestObservationFields",
    "SystemMonotonicReadClock",
    "WorldGraphReadClock",
    "WorldGraphReadFailureCode",
    "WorldGraphReadObservation",
    "WorldGraphReadObserver",
    "WorldGraphReadOperation",
    "WorldGraphReadOutcome",
    "WorldGraphReadPhase",
    "WorldGraphReadPhaseDuration",
    "classify_read_failure",
    "emit_read_observation",
]
