"""Bounded graph search allocates by source authority, not context-token hashes."""

from copy import deepcopy

import pytest

from dungeonmind.application.world_graph_retrieval import (
    EvidenceTarget,
    RetrievalBounds,
    SelectedSourceAnchorIndexRequest,
)
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2
from dungeonmind.infrastructure.memory import (
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from tests.unit.test_world_graph_retrieval_service import (
    CAMPAIGN_A,
    CAMPAIGN_B,
    _evidence_row,
    _object,
    _payload,
    _publish,
    _put_source,
    _request,
    _services,
)


def _fixture(*, distinct_revision=False):
    payload = _payload()
    payload.update(objects=[], relationships=[], evidence_refs=[])
    sources = InMemorySourceRepository()
    broad = []
    focused = []
    pairs = set()
    for index in range(70):
        artifact = "src:a-broad" if index < 65 else f"src:focused-{index - 65}"
        revision = "srcrev:a-broad" if index < 65 else f"srcrev:focused-{index - 65}"
        if distinct_revision and index == 66:
            artifact = "src:focused-0"
        if (artifact, revision) not in pairs:
            if sources.get_artifact(artifact) is None:
                _put_source(sources, artifact_id=artifact, revision_id=revision, campaign_id=None)
            else:
                prior = sources.get_revision("srcrev:focused-0")
                assert prior is not None
                sources.put_revision(prior.model_copy(update={"source_revision_id": revision}))
            pairs.add((artifact, revision))
        evidence = f"ev:witness-{index:02d}"
        (broad if index < 65 else focused).append(evidence)
        payload["evidence_refs"].append(
            _evidence_row(evidence, artifact, revision, span=f"span:{index:02d}")
        )
    for object_id, evidence in (("obj:broad", broad), ("obj:focused", focused + broad[:1])):
        obj = _object(
            object_id,
            "Keeper " + object_id,
            assertion_id="asrt:" + object_id,
            evidence=evidence[0],
            campaign_scope=None,
        )
        obj["assertion_metadata"]["evidence_ref_ids"] = evidence
        payload["objects"].append(obj)
    return payload, sources, pairs


def _search(service, revision, limit=24, **scope):
    request = _request(
        scope_mode=scope.pop("scope_mode", ScopeModeV2.WORLD),
        revision_pin=revision.revision_id,
        **scope,
    )
    return service.search(request, query_text="Keeper", bounds=RetrievalBounds(max_anchors=limit))


def _identities(anchors):
    return [(a.evidence_ref_id, a.source_artifact_id, a.source_revision_id) for a in anchors]


def test_public_search_keeps_small_source_witnesses_within_existing_allowance():
    payload, sources, pairs = _fixture()
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph, payload)
    service, projection = _services(graph, sources)
    result = _search(service, revision)
    assert projection.project_calls == 1
    assert set(result.matched_object_ids) == {"obj:broad", "obj:focused"}
    assert len(result.anchors) == 24
    assert "anchors" in result.coverage.truncated_fields
    assert {(a.source_artifact_id, a.source_revision_id) for a in result.anchors} == pairs
    assert {a.evidence_ref_id for a in result.anchors} >= {f"ev:witness-{n}" for n in range(65, 70)}
    shared = next(a for a in result.anchors if a.evidence_ref_id == "ev:witness-00")
    assert shared.supporting_object_ids == ("obj:broad", "obj:focused")
    assert shared.supporting_assertion_ids == ()  # Search exposes existence via object support.
    assert len({a.anchor_id for a in result.anchors}) == 24


@pytest.mark.parametrize("limit", [1, 2, 6, 24, 32])
def test_revision_only_change_and_input_permutation_preserve_selected_evidence(limit):
    payload, sources, _ = _fixture()
    graph = InMemoryWorldGraphRepository()
    before = _publish(graph, payload)
    reordered = deepcopy(payload)
    reordered["objects"].reverse()
    reordered["evidence_refs"].reverse()
    for obj in reordered["objects"]:
        obj["assertion_metadata"]["evidence_ref_ids"].reverse()
    after = _publish(
        graph, reordered, parent_revision_id=before.revision_id, operation_id="op:reorder"
    )
    service, _ = _services(graph, sources)
    first, second = _search(service, before, limit), _search(service, after, limit)
    assert _identities(first.anchors) == _identities(second.anchors)
    assert len(first.anchors) == limit
    assert "anchors" in first.coverage.truncated_fields
    assert set(a.anchor_id for a in first.anchors).isdisjoint(a.anchor_id for a in second.anchors)
    # Anchor capabilities remain bound to each exact context; ordering never rebinds them.
    for result in (first, second):
        request = _request(scope_mode=ScopeModeV2.WORLD, revision_pin=result.snapshot.revision_id)
        foreign = second if result is first else first
        for anchor in result.anchors:
            opened = service.resolve_source_anchor(request, anchor_id=anchor.anchor_id)
            assert opened.found and opened.anchor is not None
            assert _identities((opened.anchor,)) == _identities((anchor,))
            assert opened.anchor.locator_identity == anchor.locator_identity
            assert opened.anchor.evidence == anchor.evidence
            assert opened.anchor.artifact == anchor.artifact
            # Whole-graph resolution can enrich supporter sets, never change source authority.
            assert set(anchor.supporting_object_ids) <= set(opened.anchor.supporting_object_ids)
        assert not service.resolve_source_anchor(
            request, anchor_id=foreign.anchors[0].anchor_id
        ).found


def test_complete_index_keeps_every_anchor_and_distinct_source_revision():
    payload, sources, pairs = _fixture(distinct_revision=True)
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph, payload)
    service, _ = _services(graph, sources)
    bounded = _search(service, revision, 6)
    assert {(a.source_artifact_id, a.source_revision_id) for a in bounded.anchors} == pairs
    request = _request(scope_mode=ScopeModeV2.WORLD, revision_pin=revision.revision_id)
    full = service.list_selected_source_anchor_index(
        SelectedSourceAnchorIndexRequest(
            projection=request,
            targets=(
                EvidenceTarget("object", "obj:broad"),
                EvidenceTarget("object", "obj:focused"),
            ),
        )
    )
    assert full.eligible_count == len(full.entries) == 70
    assert len({a.anchor_id for a in full.entries}) == 70
    broad = service.get_complete_object(request, object_id="obj:broad")
    assert len(broad.anchors) == 65 and not broad.coverage.truncated_fields
    assert [a.anchor_id for a in broad.anchors] == sorted(a.anchor_id for a in broad.anchors)


@pytest.mark.parametrize("visibility", ["campaign", "player"])
def test_budget_does_not_recover_scope_or_player_hidden_support(visibility):
    payload, sources, _ = _fixture()
    artifact, revision_id = "src:hidden", "srcrev:hidden"
    _put_source(
        sources,
        artifact_id=artifact,
        revision_id=revision_id,
        campaign_id=CAMPAIGN_B if visibility == "campaign" else None,
    )
    payload["evidence_refs"].append(_evidence_row("ev:hidden", artifact, revision_id))
    payload["objects"].append(
        _object(
            "obj:hidden",
            "Keeper hidden",
            assertion_id="asrt:hidden",
            evidence="ev:hidden",
            campaign_scope=CAMPAIGN_B if visibility == "campaign" else None,
            visibility="gm" if visibility == "player" else "player",
        )
    )
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph, payload)
    service, _ = _services(graph, sources)
    result = _search(
        service,
        revision,
        scope_mode=ScopeModeV2.CAMPAIGN,
        campaign_id=CAMPAIGN_A,
        admissibility=Admissibility.PLAYER if visibility == "player" else Admissibility.GM,
    )
    assert "obj:hidden" not in result.matched_object_ids
    assert all(a.evidence_ref_id != "ev:hidden" for a in result.anchors)
    assert all("obj:hidden" not in a.supporting_object_ids for a in result.anchors)


def test_fewer_anchors_than_allowance_are_complete_without_false_truncation():
    payload, sources, _ = _fixture()
    wanted = {"ev:witness-00", "ev:witness-65"}
    payload["evidence_refs"] = [
        e for e in payload["evidence_refs"] if e["evidence_ref_id"] in wanted
    ]
    for obj in payload["objects"]:
        metadata = obj["assertion_metadata"]
        metadata["evidence_ref_ids"] = [e for e in metadata["evidence_ref_ids"] if e in wanted]
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph, payload)
    service, _ = _services(graph, sources)
    result = _search(service, revision)
    assert len(result.anchors) == 2
    assert not result.coverage.truncated_fields
    assert {a.evidence_ref_id for a in result.anchors} == wanted
