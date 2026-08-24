"""R.3a read-context, parsed-revision reuse, source freshness, and coherence."""

from __future__ import annotations

import threading

import pytest

from dungeonmind.application.graph_snapshot import VersionedUnionGraphSnapshotReader
from dungeonmind.application.parsed_revision_cache import ParsedImmutableRevisionCache
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import (
    EvidenceTarget,
    WorldGraphRetrievalService,
)
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.memory import InMemoryWorldGraphRepository
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from tests.unit.test_world_graph_retrieval_service import (
    CAMPAIGN_A,
    WORLD_ID,
    _FixedClock,
    _publish,
    _request,
    _seed_sources,
    _v6_descriptor,
)


class _CountingSources:
    def __init__(self, inner):
        self._inner = inner
        self.artifact_gets = 0
        self.revision_gets = 0
        self.snapshot_gets = 0

    def get_artifact(self, *args, **kwargs):
        self.artifact_gets += 1
        return self._inner.get_artifact(*args, **kwargs)

    def get_revision(self, *args, **kwargs):
        self.revision_gets += 1
        return self._inner.get_revision(*args, **kwargs)

    def get_provenance_snapshot(self, *args, **kwargs):
        self.snapshot_gets += 1
        return self._inner.get_provenance_snapshot(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _OnceFailingReader:
    def __init__(self, inner):
        self._inner = inner
        self.fail_next = False
        self.parse_calls = 0

    def parse(self, **kwargs):
        self.parse_calls += 1
        if self.fail_next:
            self.fail_next = False
            raise PersistenceIntegrityError("intentional parse failure")
        return self._inner.parse(**kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _replace_artifact(sources, artifact) -> None:
    with sources._lock:
        sources._artifacts[artifact.source_artifact_id] = artifact.model_copy(deep=True)


def _projection(world_graph, sources, *, reader=None, cache=None):
    return WorldGraphProjectionService(
        world_graph=world_graph,
        sources=sources,
        graph_reader=reader
        or VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([_v6_descriptor()])
        ),
        clock=_FixedClock(),
        parsed_revision_cache=cache,
    )


def _cross_gm(**kwargs):
    return _request(scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN, **kwargs)


def test_same_revision_reuses_parsed_immutable_snapshot():
    world_graph = InMemoryWorldGraphRepository()
    published = _publish(world_graph)
    projection = _projection(world_graph, _seed_sources())

    first = projection.open_read_context(_cross_gm())
    second = projection.open_read_context(_cross_gm(revision_pin=published.revision_id))

    assert first.parsed_revision_cache_hit is False
    assert second.parsed_revision_cache_hit is True
    assert first.parsed is second.parsed
    assert projection.parsed_revision_cache.hits == 1
    assert projection.parsed_revision_cache.misses == 1


def test_head_change_does_not_mutate_cached_historical_snapshot():
    world_graph = InMemoryWorldGraphRepository()
    first_rev = _publish(world_graph)
    projection = _projection(world_graph, _seed_sources())
    historical = projection.open_read_context(_cross_gm(revision_pin=first_rev.revision_id))

    second_rev = _publish(
        world_graph,
        parent_revision_id=first_rev.revision_id,
        operation_id="op:second",
    )
    pinned_after_move = projection.open_read_context(
        _cross_gm(revision_pin=first_rev.revision_id)
    )
    new_head = projection.open_read_context(_cross_gm())

    assert pinned_after_move.parsed is historical.parsed
    assert pinned_after_move.identity.revision_id == first_rev.revision_id
    assert pinned_after_move.identity.head_revision_id == second_rev.revision_id
    assert pinned_after_move.identity.is_head is False
    assert new_head.identity.revision_id == second_rev.revision_id
    assert new_head.identity.is_head is True
    assert new_head.parsed is not historical.parsed


def test_parse_failure_does_not_poison_unrelated_or_retry_reads():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    reader = _OnceFailingReader(
        VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([_v6_descriptor()])
        )
    )
    projection = _projection(world_graph, _seed_sources(), reader=reader)
    reader.fail_next = True

    with pytest.raises(PersistenceIntegrityError):
        projection.open_read_context(_cross_gm())
    recovered = projection.open_read_context(_cross_gm())

    assert recovered.parsed_revision_cache_hit is False
    assert reader.parse_calls == 2
    assert "obj:world-tavern" in recovered.graph.objects


def test_parsed_revision_cache_is_bounded():
    cache = ParsedImmutableRevisionCache(max_entries=2)
    world_graph = InMemoryWorldGraphRepository()
    first = _publish(world_graph)
    second = _publish(world_graph, parent_revision_id=first.revision_id, operation_id="op:2")
    third = _publish(world_graph, parent_revision_id=second.revision_id, operation_id="op:3")
    projection = _projection(world_graph, _seed_sources(), cache=cache)

    projection.open_read_context(_cross_gm(revision_pin=first.revision_id))
    projection.open_read_context(_cross_gm(revision_pin=second.revision_id))
    projection.open_read_context(_cross_gm(revision_pin=third.revision_id))

    assert cache.size == 2
    evicted = projection.open_read_context(_cross_gm(revision_pin=first.revision_id))
    assert evicted.parsed_revision_cache_hit is False


def test_source_change_is_visible_without_graph_publication():
    """Cached parsed graph must not imply a cached admissibility decision."""

    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    sources = _seed_sources()
    projection = _projection(world_graph, sources)
    player = _request(
        scope_mode=ScopeModeV2.WORLD,
        admissibility=Admissibility.PLAYER,
    )

    first = projection.open_read_context(player)
    assert "obj:world-tavern" in first.graph.objects

    world_lore = sources.get_artifact("src:world-lore")
    assert world_lore is not None
    _replace_artifact(sources, world_lore.model_copy(update={"visibility": Visibility.GM}))

    second = projection.open_read_context(player)
    assert first.parsed is second.parsed
    assert first.source_snapshot.fingerprint != second.source_snapshot.fingerprint
    assert "obj:world-tavern" not in second.graph.objects
    assert first.graph.objects.keys() != second.graph.objects.keys()


def test_projection_uses_one_coherent_source_snapshot_not_n_plus_one():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    counted = _CountingSources(_seed_sources())
    projection = _projection(world_graph, counted)
    retrieval = WorldGraphRetrievalService(projection=projection, sources=counted)

    request = _cross_gm()
    projection.open_read_context(request)
    assert counted.snapshot_gets == 1
    assert counted.artifact_gets == 0
    assert counted.revision_gets == 0

    hit = retrieval.get_object(request, object_id="obj:world-tavern")
    retrieval.get_evidence(
        request, target=EvidenceTarget(kind="object", target_id="obj:world-tavern")
    )
    retrieval.resolve_source_anchor(request, anchor_id=hit.anchors[0].anchor_id)

    assert counted.snapshot_gets == 4  # one snapshot per public operation
    assert counted.artifact_gets == 0
    assert counted.revision_gets == 0


def test_campaign_and_admissibility_axes_remain_independent():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    projection = _projection(world_graph, _seed_sources())

    campaign_gm = projection.open_read_context(
        _request(scope_mode=ScopeModeV2.CAMPAIGN, campaign_id=CAMPAIGN_A)
    )
    cross_gm = projection.open_read_context(_cross_gm())
    campaign_player = projection.open_read_context(
        _request(
            scope_mode=ScopeModeV2.CAMPAIGN,
            campaign_id=CAMPAIGN_A,
            admissibility=Admissibility.PLAYER,
        )
    )
    cross_player = projection.open_read_context(
        _request(
            scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
            admissibility=Admissibility.PLAYER,
        )
    )

    assert "obj:world-tavern" in campaign_gm.graph.objects
    assert "obj:alpha-keep" in campaign_gm.graph.objects
    assert "obj:alpha-secret" in campaign_gm.graph.objects
    assert "obj:beta-crypt" not in campaign_gm.graph.objects

    assert "obj:beta-crypt" in cross_gm.graph.objects
    assert "obj:alpha-secret" in cross_gm.graph.objects

    assert "obj:world-tavern" in campaign_player.graph.objects
    assert "obj:alpha-keep" in campaign_player.graph.objects
    assert "obj:alpha-secret" not in campaign_player.graph.objects
    assert "obj:world-tavern" in cross_player.graph.objects
    assert "obj:alpha-secret" not in cross_player.graph.objects


def test_unknown_admissibility_fails_closed():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _request(scope_mode=ScopeModeV2.WORLD, admissibility="audience")  # type: ignore[arg-type]


def test_in_memory_snapshot_does_not_mix_source_generations():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    sources = _seed_sources()
    started = threading.Event()
    release = threading.Event()
    mutation_ran = threading.Event()

    class _GatedSources(type(sources)):
        def get_provenance_snapshot(self, **kwargs):
            with self._lock:
                started.set()
                assert release.wait(timeout=2)
                return super().get_provenance_snapshot(**kwargs)

    gated = _GatedSources()
    for artifact in sources.list_artifacts_for_world(WORLD_ID):
        gated.put_artifact(artifact)
    for artifact in sources.list_artifacts_for_world(WORLD_ID):
        for revision in sources.list_revisions(artifact.source_artifact_id):
            gated.put_revision(revision)

    projection = _projection(world_graph, gated)
    captured = {}

    def reader() -> None:
        captured["context"] = projection.open_read_context(_cross_gm())

    def mutator() -> None:
        assert started.wait(timeout=2)
        world_lore = gated.get_artifact("src:world-lore")
        assert world_lore is not None
        _replace_artifact(
            gated, world_lore.model_copy(update={"visibility": Visibility.GM})
        )
        mutation_ran.set()

    reader_thread = threading.Thread(target=reader)
    mutator_thread = threading.Thread(target=mutator)
    reader_thread.start()
    assert started.wait(timeout=2)
    mutator_thread.start()
    # Mutator must still be blocked on the snapshot lock.
    assert not mutation_ran.wait(timeout=0.2)
    release.set()
    reader_thread.join(timeout=2)
    mutator_thread.join(timeout=2)

    context = captured["context"]
    world_lore = context.source_snapshot.get_artifact("src:world-lore")
    assert world_lore is not None
    assert world_lore.visibility is Visibility.PLAYER
    later = projection.open_read_context(_cross_gm())
    later_lore = later.source_snapshot.get_artifact("src:world-lore")
    assert later_lore is not None
    assert later_lore.visibility is Visibility.GM


def test_retrieval_hit_miss_search_neighborhood_evidence_and_anchor():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    projection = _projection(world_graph, _seed_sources())
    retrieval = WorldGraphRetrievalService(projection=projection, sources=_seed_sources())
    request = _cross_gm()

    hit = retrieval.get_object(request, object_id="obj:world-tavern")
    miss = retrieval.get_object(request, object_id="obj:absent")
    search = retrieval.search(request, query_text="tavern", seed_object_ids=["obj:world-gate"])
    depth1 = retrieval.get_neighborhood(
        request, seed_object_ids=["obj:world-tavern"], depth=1
    )
    depth2 = retrieval.get_neighborhood(
        request, seed_object_ids=["obj:world-tavern"], depth=2
    )
    evidence = retrieval.get_evidence(
        request, target=EvidenceTarget(kind="object", target_id="obj:world-tavern")
    )
    resolved = retrieval.resolve_source_anchor(request, anchor_id=hit.anchors[0].anchor_id)

    assert hit.found is True
    assert miss.found is False
    assert "obj:world-tavern" in search.matched_object_ids
    assert "obj:world-gate" in search.matched_object_ids  # explicit seed preserved
    assert depth1.seed_object_ids == ("obj:world-tavern",)
    assert set(depth2.object_depths) >= set(depth1.object_depths)
    assert evidence.found is True
    assert resolved.found is True
    assert resolved.anchor is not None
    assert resolved.anchor.anchor_id == hit.anchors[0].anchor_id
