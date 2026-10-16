"""Batch resolution exercises the real projection/admission boundary."""

from dataclasses import asdict
from unittest.mock import Mock

import pytest

from dungeonmind.application import SourceAnchorBatchRequest, derive_source_anchor_id
from dungeonmind.contracts.projection import Admissibility, ProjectionFocus
from dungeonmind.contracts.projection_v2 import ScopeModeV2
from dungeonmind.domain.errors import PersistenceUnavailableError
from dungeonmind.infrastructure.memory import InMemoryWorldGraphRepository
from tests.unit.test_world_graph_retrieval_service import (
    _campaign_a,
    _payload,
    _publish,
    _request,
    _services,
)


def _fixture():
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph)
    service, projection = _services(graph)
    request = _request(scope_mode=ScopeModeV2.WORLD, revision_pin=revision.revision_id)
    anchor = service.get_object(request, object_id="obj:world-tavern").anchors[0]
    return graph, revision, service, projection, request, anchor


def test_batch_matches_single_results_with_one_context_and_derivation(monkeypatch):
    _, _, service, projection, request, anchor = _fixture()
    ids = ("unknown-anchor", anchor.anchor_id)
    expected = tuple(service.resolve_source_anchor(request, anchor_id=i) for i in ids)
    derive = Mock(wraps=service._anchors_for)
    monkeypatch.setattr(service, "_anchors_for", derive)
    before = projection.project_calls
    batch = service.resolve_source_anchors(SourceAnchorBatchRequest(request, ids))
    assert projection.project_calls == before + 1
    assert derive.call_count == 1
    assert asdict(batch)["resolutions"] == tuple(asdict(item) for item in expected)
    assert [item.anchor_id for item in batch.resolutions] == list(ids)
    assert [item.found for item in batch.resolutions] == [False, True]
    assert all(item.snapshot == batch.snapshot for item in batch.resolutions)
    assert not hasattr(batch.resolutions[1].anchor, "content")


@pytest.mark.parametrize("ids", [(), ("same", "same"), ("",), (" padded",),
    ("line\nbreak",), ("nul\x00id",), ("x" * 513,), (None,), ["mutable"],
    tuple(str(i) for i in range(129))])
def test_batch_rejects_invalid_selectors_before_projection(ids):
    _, _, _, projection, request, _ = _fixture()
    before = projection.project_calls
    with pytest.raises(ValueError):
        SourceAnchorBatchRequest(request, ids)
    assert projection.project_calls == before


def test_batch_requires_explicit_pin_and_accepts_maximum_distinct_selectors():
    _, _, service, _, request, _ = _fixture()
    with pytest.raises(ValueError, match="exact revision pin"):
        SourceAnchorBatchRequest(request.model_copy(update={"revision_pin": None}), ("a",))
    ids = tuple(str(i) for i in range(128))
    batch = service.resolve_source_anchors(SourceAnchorBatchRequest(request, ids))
    assert tuple(item.anchor_id for item in batch.resolutions) == ids
    assert all(not item.found and item.anchor is None for item in batch.resolutions)


@pytest.mark.parametrize("change", ["visibility", "scope", "campaign", "focus"])
def test_batch_does_not_reuse_foreign_context_anchors(change):
    _, revision, service, _, request, anchor = _fixture()
    if change == "visibility":
        changed = request.model_copy(update={"admissibility": Admissibility.PLAYER})
    elif change == "scope":
        changed = request.model_copy(update={"scope_mode": ScopeModeV2.WORLD_CROSS_CAMPAIGN})
    else:
        request = _campaign_a(revision_pin=revision.revision_id)
        anchor = service.get_object(request, object_id="obj:world-tavern").anchors[0]
        if change == "campaign":
            changed = request.model_copy(update={"campaign_id": "camp:beta"})
        else:
            changed = request.model_copy(
                update={"focus": ProjectionFocus(kind="session", session_id="session:one")}
            )
    batch = service.resolve_source_anchors(SourceAnchorBatchRequest(changed, (anchor.anchor_id,)))
    single = service.resolve_source_anchor(changed, anchor_id=anchor.anchor_id)
    assert not batch.resolutions[0].found
    assert asdict(batch.resolutions[0]) == asdict(single)


def test_historical_anchor_remains_resolvable_only_under_its_exact_revision():
    graph, first, service, _, request, anchor = _fixture()
    child = _publish(graph, _payload(), parent_revision_id=first.revision_id,
                     operation_id="op:batch-child")
    historical = service.resolve_source_anchors(
        SourceAnchorBatchRequest(request, (anchor.anchor_id,))
    )
    assert historical.resolutions[0].found
    assert historical.snapshot.head_revision_id == child.revision_id
    changed = request.model_copy(update={"revision_pin": child.revision_id})
    current = service.resolve_source_anchors(SourceAnchorBatchRequest(changed, (anchor.anchor_id,)))
    assert not current.resolutions[0].found


@pytest.mark.parametrize("failure_point", ["_establish", "_anchors_for"])
def test_batch_propagates_failure_without_successful_prefix(monkeypatch, failure_point):
    _, _, service, _, request, anchor = _fixture()
    observer = Mock()
    service._read_observer = observer
    failure = PersistenceUnavailableError("synthetic unavailable")
    monkeypatch.setattr(service, failure_point, Mock(side_effect=failure))
    with pytest.raises(PersistenceUnavailableError):
        service.resolve_source_anchors(
            SourceAnchorBatchRequest(request, (anchor.anchor_id, "missing"))
        )
    observer.observe.assert_called_once()
    observation = observer.observe.call_args.args[0]
    assert observation.operation == "resolve_source_anchors"
    assert observation.outcome == "error"


def test_batch_emits_one_terminal_observation_counting_only_found_anchors():
    _, _, service, _, request, anchor = _fixture()
    observer = Mock()
    service._read_observer = observer
    service.resolve_source_anchors(SourceAnchorBatchRequest(request, (anchor.anchor_id, "missing")))
    observer.observe.assert_called_once()
    observation = observer.observe.call_args.args[0]
    assert observation.operation == "resolve_source_anchors"
    assert observation.result_anchor_count == 1
    assert observation.outcome == "success"


@pytest.mark.parametrize("field", ["evidence_ref_id", "source_artifact_id",
                                  "source_revision_id", "locator_identity"])
def test_batch_rejects_anchor_bound_to_foreign_source_identity(field):
    _, _, service, _, request, anchor = _fixture()
    snapshot = service.resolve_source_anchor(request, anchor_id=anchor.anchor_id).snapshot
    identity = {
        "evidence_ref_id": "ev:world",
        "source_artifact_id": "src:world-lore",
        "source_revision_id": "srcrev:world-lore-v1",
        "locator_identity": "span:tavern-1",
    }
    identity[field] = "foreign"
    foreign = derive_source_anchor_id(snapshot=snapshot, **identity)
    batch = service.resolve_source_anchors(SourceAnchorBatchRequest(request, (foreign,)))
    assert not batch.resolutions[0].found
