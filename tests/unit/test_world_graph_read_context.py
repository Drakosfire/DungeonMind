"""R.3a read-context, parsed-revision reuse, source freshness, and coherence."""

from __future__ import annotations

import threading

import pytest

from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V1,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.parsed_revision_cache import ParsedImmutableRevisionCache
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import (
    EvidenceTarget,
    WorldGraphRetrievalService,
)
from dungeonmind.contracts.evidence import (
    SourceArtifact,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import PersistenceIntegrityError, SemanticProfileNotFoundError
from dungeonmind.infrastructure.memory import (
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from tests.unit.test_world_graph_retrieval_service import (
    CAMPAIGN_A,
    NOW,
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


def _assert_isolated_same_revision(left, right) -> None:
    assert left is not right
    assert left.world_id == right.world_id
    assert left.graph_schema == right.graph_schema
    assert set(left.objects) == set(right.objects)
    for object_id, obj in left.objects.items():
        other = right.objects[object_id]
        assert obj is not other
        assert obj.label == other.label
        assert list(obj.aliases) == list(other.aliases)
    assert set(left.relationships) == set(right.relationships)
    for relationship_id, rel in left.relationships.items():
        other = right.relationships[relationship_id]
        assert rel is not other
        assert rel.predicate == other.predicate
    assert set(left.evidence) == set(right.evidence)
    for evidence_id, record in left.evidence.items():
        other = right.evidence[evidence_id]
        assert record is not other
        assert record.locator == other.locator


def _publish_v1(world_graph: InMemoryWorldGraphRepository):
    return world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["op:v1-fixture"],
            graph_schema=GRAPH_SCHEMA_V1,
            graph_payload={
                "world_id": WORLD_ID,
                "nodes": [
                    {
                        "object_id": "obj:world-tavern",
                        "kind": "location",
                        "label": "World Tavern",
                        "aliases": ["The Local Spot"],
                        "evidence_ref_ids": ["ev:world"],
                        "summary": "A bustling tavern at the crossroads.",
                    },
                    {
                        "object_id": "obj:world-gate",
                        "kind": "location",
                        "label": "North Gate",
                        "aliases": [],
                        "evidence_ref_ids": ["ev:world"],
                        "summary": None,
                    },
                ],
                "relationships": [
                    {
                        "relationship_id": "rel:tavern-gate",
                        "subject_object_id": "obj:world-tavern",
                        "predicate": "connected_to",
                        "object_object_id": "obj:world-gate",
                        "evidence_ref_ids": ["ev:world"],
                    }
                ],
                "evidence_refs": [
                    {
                        "evidence_ref_id": "ev:world",
                        "source_artifact_id": "src:world-lore",
                        "source_revision_id": "srcrev:world-lore-v1",
                        "source_domain": "worldbuilding",
                        "evidence_role": "support",
                        "locator": "fixture://src:world-lore",
                    }
                ],
            },
            created_at=NOW,
        )
    )


def _seed_v1_sources() -> InMemorySourceRepository:
    sources = InMemorySourceRepository()
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:world-lore",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id=WORLD_ID,
            visibility=Visibility.PLAYER,
            status=SourceStatus.ACTIVE,
            current_revision_id="srcrev:world-lore-v1",
            created_at=NOW,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:world-lore-v1",
            source_artifact_id="src:world-lore",
            content_sha256="dd" * 32,
            body_storage="external",
            locator="fixture://src:world-lore",
            created_at=NOW,
        )
    )
    return sources


def test_same_revision_reuses_parsed_immutable_snapshot():
    world_graph = InMemoryWorldGraphRepository()
    published = _publish(world_graph)
    projection = _projection(world_graph, _seed_sources())

    first = projection.open_read_context(_cross_gm())
    second = projection.open_read_context(_cross_gm(revision_pin=published.revision_id))

    assert first.parsed_revision_cache_hit is False
    assert second.parsed_revision_cache_hit is True
    _assert_isolated_same_revision(first.parsed, second.parsed)
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

    assert pinned_after_move.parsed is not historical.parsed
    _assert_isolated_same_revision(pinned_after_move.parsed, historical.parsed)
    assert pinned_after_move.parsed_revision_cache_hit is True
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


def test_incompatible_profile_registry_does_not_reuse_cached_parse():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    sources = _seed_sources()
    cache = ParsedImmutableRevisionCache()
    good = _projection(
        world_graph,
        sources,
        reader=VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([_v6_descriptor()])
        ),
        cache=cache,
    )
    bad = _projection(
        world_graph,
        sources,
        reader=VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry()
        ),
        cache=cache,
    )

    first = good.open_read_context(_cross_gm())
    assert first.parsed_revision_cache_hit is False
    with pytest.raises(SemanticProfileNotFoundError):
        bad.open_read_context(_cross_gm())
    second = good.open_read_context(_cross_gm())
    assert second.parsed_revision_cache_hit is True
    assert cache.hits == 1


def test_returned_result_mutation_cannot_poison_parsed_revision_cache():
    world_graph = InMemoryWorldGraphRepository()
    _publish_v1(world_graph)
    projection = _projection(world_graph, _seed_v1_sources())

    first = projection.open_read_context(_cross_gm())
    parsed_object = first.parsed.objects["obj:world-tavern"]
    scoped_object = first.graph.objects["obj:world-tavern"]
    parsed_rel = first.parsed.relationships["rel:tavern-gate"]
    scoped_rel = first.graph.relationships["rel:tavern-gate"]
    parsed_evidence = first.parsed.evidence["ev:world"]
    scoped_evidence = first.graph.evidence["ev:world"]

    parsed_object.label = "poisoned parsed"
    parsed_object.aliases.append("poison-alias")
    scoped_object.label = "poisoned scoped"
    scoped_object.aliases.append("poison-scoped-alias")
    parsed_rel.predicate = "poisoned_predicate"
    scoped_rel.predicate = "poisoned_scoped_predicate"
    parsed_evidence.locator = "poisoned-parsed-locator"
    scoped_evidence.locator = "poisoned-scoped-locator"

    second = projection.open_read_context(_cross_gm())
    assert second.parsed_revision_cache_hit is True
    assert second.parsed.objects["obj:world-tavern"].label == "World Tavern"
    assert second.parsed.objects["obj:world-tavern"].aliases == ["The Local Spot"]
    assert second.graph.objects["obj:world-tavern"].label == "World Tavern"
    assert second.graph.objects["obj:world-tavern"].aliases == ["The Local Spot"]
    assert second.parsed.relationships["rel:tavern-gate"].predicate == "connected_to"
    assert second.graph.relationships["rel:tavern-gate"].predicate == "connected_to"
    assert second.parsed.evidence["ev:world"].locator == "fixture://src:world-lore"
    assert second.graph.evidence["ev:world"].locator == "fixture://src:world-lore"


def test_source_provenance_snapshot_mutation_cannot_contaminate_snapshot_or_later_read():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    projection = _projection(world_graph, _seed_sources())

    first = projection.open_read_context(_cross_gm())
    artifact = first.source_snapshot.get_artifact("src:world-lore")
    revision = first.source_snapshot.get_revision("srcrev:world-lore-v1")
    assert artifact is not None
    assert revision is not None
    artifact.visibility = Visibility.GM
    revision.locator = "poisoned-locator"

    same_artifact = first.source_snapshot.get_artifact("src:world-lore")
    same_revision = first.source_snapshot.get_revision("srcrev:world-lore-v1")
    assert same_artifact is not None
    assert same_revision is not None
    assert same_artifact.visibility is Visibility.PLAYER
    assert same_revision.locator == "fixture://src:world-lore"

    second = projection.open_read_context(_cross_gm())
    later_artifact = second.source_snapshot.get_artifact("src:world-lore")
    later_revision = second.source_snapshot.get_revision("srcrev:world-lore-v1")
    assert later_artifact is not None
    assert later_revision is not None
    assert later_artifact.visibility is Visibility.PLAYER
    assert later_revision.locator == "fixture://src:world-lore"
    with pytest.raises(TypeError):
        first.source_snapshot.artifacts["src:world-lore"] = artifact  # type: ignore[index]


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
    assert first.parsed is not second.parsed
    _assert_isolated_same_revision(first.parsed, second.parsed)
    assert second.parsed_revision_cache_hit is True
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
