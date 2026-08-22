"""Observability seam tests for the direct World Graph read path (R.2a).

Proves the R.2a observation contract over the synthetic v6 authority fixture:

* exactly one terminal event per invoked public method, plus the intentional
  nested ``project`` event when projection and retrieval share an observer;
* closed operation/outcome/failure/phase vocabularies and monotonic,
  non-negative durations;
* count-only, privacy-safe observation values (structural token scan);
* stable failure classification without exception text;
* fail-open observer behavior on both success and error paths;
* no double execution of graph work for telemetry.
"""

from dataclasses import fields, is_dataclass
from pathlib import Path

import pytest

from dungeonmind.application.graph_snapshot import VersionedUnionGraphSnapshotReader
from dungeonmind.application.world_graph_observability import (
    NOOP_READ_OBSERVER,
    PhaseRecorder,
    WorldGraphReadObservation,
    classify_read_failure,
    emit_read_observation,
)
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import (
    EvidenceTarget,
    RetrievalBounds,
    WorldGraphRetrievalService,
)
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2
from dungeonmind.domain.errors import (
    DungeonMindError,
    HeadNotFoundError,
    RevisionNotFoundError,
    ScopeResolutionError,
)
from dungeonmind.infrastructure.memory import (
    InMemoryWorldGraphRepository,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from tests.unit.test_world_graph_retrieval_service import (
    _FixedClock,
    _publish,
    _request,
    _seed_sources,
    _v6_descriptor,
)

FORBIDDEN_VALUE_TOKENS = (
    "world:",
    "camp:",
    "obj:",
    "rel:",
    "asrt:",
    "ev:",
    "src:",
    "srcrev:",
    "span:",
    "dm-source-anchor:",
    "rev:",
    "tavern",
    "keep",
    "crypt",
    "vault",
    "pony",
    "traitor",
)

OBSERVABILITY_SOURCE = (
    Path(__file__).parents[2]
    / "src"
    / "dungeonmind"
    / "application"
    / "world_graph_observability.py"
)

FORBIDDEN_SOURCE_TOKENS = (
    "world_id",
    "campaign_id",
    "revision_id",
    "object_id",
    "relationship_id",
    "assertion_id",
    "evidence_ref_id",
    "source_artifact_id",
    "anchor_id",
    "query_text",
    "label",
    "alias",
    "summary",
    "locator",
    "uri",
)


class _RecordingObserver:
    def __init__(self) -> None:
        self.observations: list[WorldGraphReadObservation] = []

    def observe(self, observation: WorldGraphReadObservation) -> None:
        self.observations.append(observation)


class _ThrowingObserver:
    def observe(self, observation: WorldGraphReadObservation) -> None:
        raise RuntimeError("observer sink exploded")


class _FakeMonotonicClock:
    def __init__(self) -> None:
        self.ticks = 0

    def now_ns(self) -> int:
        self.ticks += 1
        return self.ticks * 1_000_000


class _CountingProjectionService(WorldGraphProjectionService):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.project_calls = 0

    def project(self, request):
        self.project_calls += 1
        return super().project(request)


def _services(
    world_graph: InMemoryWorldGraphRepository,
    *,
    observer=None,
    projection_observer=None,
    read_clock=None,
):
    sources = _seed_sources()
    projection = _CountingProjectionService(
        world_graph=world_graph,
        sources=sources,
        graph_reader=VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([_v6_descriptor()])
        ),
        clock=_FixedClock(),
        read_observer=projection_observer if projection_observer is not None else observer,
        read_clock=read_clock,
    )
    retrieval = WorldGraphRetrievalService(
        projection=projection,
        sources=sources,
        read_observer=observer,
        read_clock=read_clock,
    )
    return retrieval, projection


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_strings(key)
            yield from _walk_strings(item)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _walk_strings(item)
    elif is_dataclass(value) and not isinstance(value, type):
        for f in fields(value):
            yield from _walk_strings(getattr(value, f.name))


def _assert_no_forbidden_tokens(observation: WorldGraphReadObservation) -> None:
    for text in _walk_strings(observation):
        lowered = text.casefold()
        for token in FORBIDDEN_VALUE_TOKENS:
            assert token not in lowered, f"forbidden token {token!r} in {text!r}"


# ---------------------------------------------------------------------------
# Observation value shape and vocabulary
# ---------------------------------------------------------------------------


def test_observation_vocabulary_is_closed_and_validated():
    with pytest.raises(ValueError, match="unknown read operation"):
        WorldGraphReadObservation(
            operation="delete_everything",
            outcome="success",
            duration_seconds=0.0,
            phase_durations=(),
            pinned_read=False,
            scope_mode="world",
            admissibility="gm",
        )
    with pytest.raises(ValueError, match="unknown read outcome"):
        WorldGraphReadObservation(
            operation="project",
            outcome="maybe",
            duration_seconds=0.0,
            phase_durations=(),
            pinned_read=False,
            scope_mode="world",
            admissibility="gm",
        )
    with pytest.raises(ValueError, match="unknown read failure code"):
        WorldGraphReadObservation(
            operation="project",
            outcome="error",
            duration_seconds=0.0,
            phase_durations=(),
            failure_code="boom",
            pinned_read=False,
            scope_mode="world",
            admissibility="gm",
        )
    with pytest.raises(ValueError, match="requires failure_code"):
        WorldGraphReadObservation(
            operation="project",
            outcome="error",
            duration_seconds=0.0,
            phase_durations=(),
            pinned_read=False,
            scope_mode="world",
            admissibility="gm",
        )
    with pytest.raises(ValueError, match="non-negative"):
        WorldGraphReadObservation(
            operation="project",
            outcome="success",
            duration_seconds=-0.1,
            phase_durations=(),
            pinned_read=False,
            scope_mode="world",
            admissibility="gm",
        )


def test_phase_recorder_uses_monotonic_clock_and_preserves_order():
    clock = _FakeMonotonicClock()
    recorder = PhaseRecorder(clock)
    with recorder.phase("head_lookup"):
        pass
    with recorder.phase("parse"):
        pass
    total = recorder.total_seconds()
    assert [p.phase for p in recorder.phases] == ["head_lookup", "parse"]
    assert all(p.duration_seconds > 0 for p in recorder.phases)
    assert total >= recorder.phases[-1].duration_seconds


def test_classify_read_failure_maps_known_classes_only():
    assert classify_read_failure(HeadNotFoundError("x")) == "head_not_found"
    assert classify_read_failure(RevisionNotFoundError("x")) == "revision_not_found"
    assert classify_read_failure(ScopeResolutionError("x")) == "scope_resolution"
    assert classify_read_failure(ValueError("x")) == "invalid_input"
    assert classify_read_failure(DungeonMindError("x")) == "graph_read_failed"
    assert classify_read_failure(RuntimeError("x")) == "unexpected"
    assert classify_read_failure(KeyboardInterrupt("x")) == "unexpected"


def test_observability_module_source_carries_no_identity_fields():
    text = OBSERVABILITY_SOURCE.read_text(encoding="utf-8")
    for token in FORBIDDEN_SOURCE_TOKENS:
        assert token not in text, f"forbidden token {token!r} in observability module"


# ---------------------------------------------------------------------------
# Projection observations
# ---------------------------------------------------------------------------


def test_project_success_observation_counts_and_phases():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    observer = _RecordingObserver()
    _, projection = _services(world_graph, observer=observer)

    result = projection.project(_request(scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN))

    assert len(observer.observations) == 1
    obs = observer.observations[0]
    assert obs.operation == "project"
    assert obs.outcome == "success"
    assert obs.failure_code is None
    assert [p.phase for p in obs.phase_durations] == [
        "head_lookup",
        "revision_load",
        "parse",
        "scope_projection",
    ]
    assert all(p.duration_seconds >= 0 for p in obs.phase_durations)
    assert obs.duration_seconds >= 0
    assert obs.graph_schema == result.graph.graph_schema
    assert obs.parsed_object_count == 6
    # GM cross-campaign admits everything except the broken-provenance row,
    # which fails closed at projection time with named in-scope rejections.
    assert obs.admitted_object_count == len(result.graph.objects) == 5
    assert obs.admitted_relationship_count == len(result.graph.relationships)
    assert obs.excluded_object_count == 1
    assert obs.provenance_rejected_count is not None
    assert obs.provenance_rejected_count >= 1
    assert obs.scope_unknown_exclusion_count is not None
    assert obs.pinned_read is False
    assert obs.scope_mode == "world_cross_campaign"
    assert obs.admissibility == "gm"
    _assert_no_forbidden_tokens(obs)


def test_project_pinned_read_is_boolean_only():
    world_graph = InMemoryWorldGraphRepository()
    published = _publish(world_graph)
    observer = _RecordingObserver()
    _, projection = _services(world_graph, observer=observer)

    projection.project(_request(scope_mode=ScopeModeV2.WORLD))
    projection.project(
        _request(
            scope_mode=ScopeModeV2.WORLD,
            revision_pin=published.revision_id,
        )
    )

    assert [obs.pinned_read for obs in observer.observations] == [False, True]
    for obs in observer.observations:
        _assert_no_forbidden_tokens(obs)


def test_project_error_observations_classify_without_exception_text():
    observer = _RecordingObserver()
    empty_graph = InMemoryWorldGraphRepository()
    _, projection = _services(empty_graph, observer=observer)

    with pytest.raises(HeadNotFoundError):
        projection.project(_request(scope_mode=ScopeModeV2.WORLD))
    assert len(observer.observations) == 1
    obs = observer.observations[0]
    assert obs.operation == "project"
    assert obs.outcome == "error"
    assert obs.failure_code == "head_not_found"
    assert [p.phase for p in obs.phase_durations] == ["head_lookup"]
    assert obs.parsed_object_count is None
    _assert_no_forbidden_tokens(obs)

    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    observer2 = _RecordingObserver()
    _, projection2 = _services(world_graph, observer=observer2)
    with pytest.raises(RevisionNotFoundError):
        projection2.project(
            _request(scope_mode=ScopeModeV2.WORLD, revision_pin="rev:missing")
        )
    assert observer2.observations[0].failure_code == "revision_not_found"
    _assert_no_forbidden_tokens(observer2.observations[0])


def test_project_player_campaign_counts_without_identity():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    observer = _RecordingObserver()
    _, projection = _services(world_graph, observer=observer)

    result = projection.project(
        _request(
            scope_mode=ScopeModeV2.CAMPAIGN,
            campaign_id="camp:alpha",
            admissibility=Admissibility.PLAYER,
        )
    )

    obs = observer.observations[0]
    assert obs.scope_mode == "campaign"
    assert obs.admissibility == "player"
    assert obs.admitted_object_count == len(result.graph.objects)
    assert obs.excluded_object_count == len(result.scoped_graph.object_exclusions)
    assert obs.excluded_object_count > 0  # GM-only and other-campaign rows excluded
    _assert_no_forbidden_tokens(obs)


# ---------------------------------------------------------------------------
# Retrieval observations
# ---------------------------------------------------------------------------


def test_retrieval_emits_nested_project_plus_outer_event():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    observer = _RecordingObserver()
    retrieval, projection = _services(world_graph, observer=observer)

    result = retrieval.get_object(
        _request(scope_mode=ScopeModeV2.WORLD), object_id="obj:world-tavern"
    )

    assert result.found is True
    assert [obs.operation for obs in observer.observations] == ["project", "get_object"]
    assert projection.project_calls == 1
    outer = observer.observations[1]
    assert outer.outcome == "success"
    assert [p.phase for p in outer.phase_durations] == [
        "projection",
        "object_selection",
        "anchor_derivation",
    ]
    assert outer.result_object_count == 1
    assert outer.result_anchor_count == len(result.anchors)
    assert outer.admitted_object_count is not None
    _assert_no_forbidden_tokens(outer)


def test_retrieval_observer_without_projection_observer_emits_one_event():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    observer = _RecordingObserver()
    retrieval, _ = _services(world_graph, observer=observer, projection_observer=None)
    # Rewire: projection gets the default no-op observer explicitly.
    sources = _seed_sources()
    projection = WorldGraphProjectionService(
        world_graph=world_graph,
        sources=sources,
        graph_reader=VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([_v6_descriptor()])
        ),
        clock=_FixedClock(),
    )
    retrieval = WorldGraphRetrievalService(
        projection=projection, sources=sources, read_observer=observer
    )

    retrieval.get_object(_request(scope_mode=ScopeModeV2.WORLD), object_id="obj:world-tavern")

    assert [obs.operation for obs in observer.observations] == ["get_object"]


def test_get_object_miss_is_miss_outcome_not_error():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    observer = _RecordingObserver()
    retrieval, _ = _services(world_graph, observer=observer)

    result = retrieval.get_object(
        _request(scope_mode=ScopeModeV2.WORLD), object_id="obj:absent"
    )

    assert result.found is False
    outer = observer.observations[-1]
    assert outer.operation == "get_object"
    assert outer.outcome == "miss"
    assert outer.result_object_count == 0
    _assert_no_forbidden_tokens(outer)


def test_search_observation_success_miss_and_truncation():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    observer = _RecordingObserver()
    retrieval, _ = _services(world_graph, observer=observer)

    hit = retrieval.search(
        _request(scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN),
        query_text="dnd5e:location",
        bounds=RetrievalBounds(max_objects=2),
    )
    assert hit.matched_object_ids
    outer = observer.observations[-1]
    assert outer.operation == "search"
    assert outer.outcome == "success"
    assert [p.phase for p in outer.phase_durations] == [
        "projection",
        "referent_and_lexical_scoring",
        "anchor_derivation",
    ]
    assert outer.result_object_count == 2
    assert "objects" in outer.truncated_fields
    _assert_no_forbidden_tokens(outer)

    miss = retrieval.search(_request(scope_mode=ScopeModeV2.WORLD), query_text="")
    assert miss.matched_object_ids == ()
    outer = observer.observations[-1]
    assert outer.outcome == "miss"
    assert outer.result_object_count == 0


def test_neighborhood_observation_records_depth_and_seed_counts_only():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    observer = _RecordingObserver()
    retrieval, _ = _services(world_graph, observer=observer)

    result = retrieval.get_neighborhood(
        _request(scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN),
        seed_object_ids=["obj:alpha-keep", "obj:gone"],
        depth=2,
    )

    outer = observer.observations[-1]
    assert outer.operation == "get_neighborhood"
    assert outer.outcome == "success"
    assert outer.neighborhood_depth == 2
    assert outer.requested_seed_count == 2
    assert outer.present_seed_count == 1
    assert outer.missing_seed_count == 1
    assert [p.phase for p in outer.phase_durations] == [
        "projection",
        "traversal",
        "anchor_derivation",
    ]
    assert outer.result_object_count == len(result.objects)
    _assert_no_forbidden_tokens(outer)


def test_neighborhood_all_seeds_missing_is_miss():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    observer = _RecordingObserver()
    retrieval, _ = _services(world_graph, observer=observer)

    result = retrieval.get_neighborhood(
        _request(scope_mode=ScopeModeV2.WORLD),
        seed_object_ids=["obj:gone"],
        depth=1,
    )

    assert result.seed_object_ids == ()
    outer = observer.observations[-1]
    assert outer.outcome == "miss"
    assert outer.missing_seed_count == 1


def test_get_evidence_observation_counts_broken_provenance_safely():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    observer = _RecordingObserver()
    retrieval, _ = _services(world_graph, observer=observer)

    result = retrieval.get_evidence(
        _request(scope_mode=ScopeModeV2.WORLD),
        target=EvidenceTarget(kind="object", target_id="obj:broken-lore"),
    )

    # Broken in-scope provenance: explicit safe coverage, outcome is a miss
    # (the projection excluded the row fail-closed), counts only.
    assert result.found is False
    outer = observer.observations[-1]
    assert outer.operation == "get_evidence"
    assert outer.outcome == "miss"
    assert [p.phase for p in outer.phase_durations] == ["projection"]
    assert outer.coverage_gap_count is not None and outer.coverage_gap_count >= 1
    assert outer.coverage_missing_count is not None and outer.coverage_missing_count >= 1
    _assert_no_forbidden_tokens(outer)


def test_get_evidence_hidden_target_miss_never_echoes_identity():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    observer = _RecordingObserver()
    retrieval, _ = _services(world_graph, observer=observer)

    result = retrieval.get_evidence(
        _request(scope_mode=ScopeModeV2.CAMPAIGN, campaign_id="camp:alpha",
                 admissibility=Admissibility.PLAYER),
        target=EvidenceTarget(kind="object", target_id="obj:alpha-secret"),
    )

    assert result.found is False
    outer = observer.observations[-1]
    assert outer.outcome == "miss"
    _assert_no_forbidden_tokens(outer)


def test_resolve_source_anchor_observation_success_and_miss():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    observer = _RecordingObserver()
    retrieval, _ = _services(world_graph, observer=observer)
    request = _request(scope_mode=ScopeModeV2.WORLD)

    anchor_id = retrieval.get_object(request, object_id="obj:world-tavern").anchors[0].anchor_id
    observer.observations.clear()

    resolved = retrieval.resolve_source_anchor(request, anchor_id=anchor_id)
    assert resolved.found is True
    outer = observer.observations[-1]
    assert outer.operation == "resolve_source_anchor"
    assert outer.outcome == "success"
    assert outer.result_anchor_count == 1
    assert [p.phase for p in outer.phase_durations] == ["projection", "anchor_derivation"]
    _assert_no_forbidden_tokens(outer)

    miss = retrieval.resolve_source_anchor(request, anchor_id="dm-source-anchor:v1:bogus")
    assert miss.found is False
    outer = observer.observations[-1]
    assert outer.outcome == "miss"
    assert outer.result_anchor_count == 0
    _assert_no_forbidden_tokens(outer)


# ---------------------------------------------------------------------------
# Fail-open behavior
# ---------------------------------------------------------------------------


def test_observer_exception_on_success_preserves_result():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    throwing, projection = _services(world_graph, observer=_ThrowingObserver())
    quiet, _ = _services(world_graph, observer=None)

    request = _request(scope_mode=ScopeModeV2.WORLD)
    expected = quiet.get_object(request, object_id="obj:world-tavern")
    actual = throwing.get_object(request, object_id="obj:world-tavern")

    assert actual == expected
    assert projection.project_calls == 1


def test_observer_exception_on_error_preserves_original_error():
    empty_graph = InMemoryWorldGraphRepository()
    _, projection = _services(empty_graph, observer=_ThrowingObserver())

    with pytest.raises(HeadNotFoundError):
        projection.project(_request(scope_mode=ScopeModeV2.WORLD))


def test_observer_exception_during_retrieval_error_preserves_original_error():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    retrieval, _ = _services(world_graph, observer=_ThrowingObserver())

    with pytest.raises(ValueError, match="non-blank"):
        retrieval.get_object(_request(scope_mode=ScopeModeV2.WORLD), object_id="  ")


def test_unexpected_exception_maps_to_unexpected_without_text():
    class _ExplodingRepository(InMemoryWorldGraphRepository):
        def get_head(self, world_id):
            raise RuntimeError("database connection to world:test leaked")

    world_graph = _ExplodingRepository()
    observer = _RecordingObserver()
    _, projection = _services(world_graph, observer=observer)

    with pytest.raises(RuntimeError, match="leaked"):
        projection.project(_request(scope_mode=ScopeModeV2.WORLD))

    obs = observer.observations[0]
    assert obs.outcome == "error"
    assert obs.failure_code == "unexpected"
    _assert_no_forbidden_tokens(obs)


def test_emit_read_observation_swallows_observer_failure():
    observation = WorldGraphReadObservation(
        operation="project",
        outcome="success",
        duration_seconds=0.0,
        phase_durations=(),
        pinned_read=False,
        scope_mode="world",
        admissibility="gm",
    )
    emit_read_observation(_ThrowingObserver(), observation)  # must not raise
    emit_read_observation(NOOP_READ_OBSERVER, observation)


def test_invalid_input_error_is_observed_once():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    observer = _RecordingObserver()
    retrieval, projection = _services(world_graph, observer=observer)

    with pytest.raises(ValueError, match="depth must be 1 or 2"):
        retrieval.get_neighborhood(
            _request(scope_mode=ScopeModeV2.WORLD),
            seed_object_ids=["obj:world-tavern"],
            depth=3,
        )

    # Input validation fails before projection: only the outer event exists.
    assert [obs.operation for obs in observer.observations] == ["get_neighborhood"]
    assert observer.observations[0].failure_code == "invalid_input"
    assert projection.project_calls == 0
