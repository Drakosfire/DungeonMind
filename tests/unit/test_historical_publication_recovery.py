"""Original terminal history is coherent, detached and incapable of publication."""

import ast
import copy
from collections import Counter
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from dungeonmind.application.compatibility import read_historical_finalized_publication
from dungeonmind.application.repositories import VerifiedPublicationHistoryEntry
from dungeonmind.application.review_publication import publish_finalized_review
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.domain.errors import (
    CapabilityDeniedError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
)
from dungeonmind.infrastructure.memory import (
    InMemoryFinalizedReviewPublicationRepository,
    InMemoryWorldGraphRepository,
)
from tests.conformance.test_review_publication import (
    PUBLISHED_AT,
    _seed_graph,
    _seed_review,
)
from tests.unit.test_publication_admission import SyntheticValidator, setup_memory


@pytest.fixture(params=["v1", "v2"])
def lane(request):
    if request.param == "v2":
        value = setup_memory(validator=SyntheticValidator())
        value.receipt = value.publications.publish(value.command)
        return value
    graph = InMemoryWorldGraphRepository()
    parent, reader = _seed_graph(graph)
    reviews, state = _seed_review()
    publications = InMemoryFinalizedReviewPublicationRepository(reviews, graph)
    receipt = publish_finalized_review(
        state.record.world_id,
        state.record.review_id,
        published_at=PUBLISHED_AT,
        review_repository=reviews,
        world_graph_repository=graph,
        publication_repository=publications,
        graph_reader=reader,
    )
    return SimpleNamespace(
        graph=graph,
        parent=parent,
        reviews=reviews,
        state=state,
        publications=publications,
        receipt=receipt,
    )


def read(lane):
    return read_historical_finalized_publication(
        lane.receipt.world_id, lane.receipt.operation_id, reader=lane.publications
    )


def snapshot(lane):
    repo = lane.publications
    return copy.deepcopy(
        (
            repo._records_by_operation,
            repo._records_by_review,
            repo._records_by_revision,
            lane.graph._heads,
            lane.graph._revisions,
            lane.reviews._records,
            lane.reviews._contributions._items,
            lane.graph._admission._uses,
            lane.graph._admission._policies,
        )
    )


def forbidden(*args, **kwargs):
    raise AssertionError("historical read attempted current authority or mutation")


def test_terminal_read_preserves_family_without_current_authority_or_writes(lane, monkeypatch):
    for obj, method in [
        (lane.graph, "get_head"),
        (lane.graph, "publish_revision"),
        (lane.publications, "publish"),
        (lane.reviews, "finalize"),
        (lane.publications, "get_provenance_snapshot"),
        (lane.publications._admission_registry, "validate"),
    ]:
        monkeypatch.setattr(obj, method, forbidden)
    if hasattr(lane, "sources"):
        for method in ["get_artifact", "get_provenance_snapshot"]:
            monkeypatch.setattr(lane.sources, method, forbidden)
    before = snapshot(lane)
    entry = read(lane)
    assert entry.publication == lane.receipt
    assert entry.review == lane.state
    assert entry.revision.revision_id == lane.receipt.published_revision_id
    assert entry.publication.schema_version == lane.receipt.schema_version
    assert snapshot(lane) == before


def test_absent_terminal_never_completes_an_existing_finalized_review(lane, monkeypatch):
    for index in ["_records_by_operation", "_records_by_review", "_records_by_revision"]:
        getattr(lane.publications, index).clear()
    before = snapshot(lane)
    monkeypatch.setattr(lane.publications, "publish", forbidden)
    monkeypatch.setattr(lane.reviews, "finalize", forbidden)
    monkeypatch.setattr(lane.graph, "get_head", forbidden)
    assert read(lane) is None
    assert snapshot(lane) == before


@pytest.mark.parametrize("index", ["operation", "review", "revision"])
def test_partial_terminal_index_loss_is_integrity_not_absence(lane, index):
    getattr(lane.publications, "_records_by_" + index).clear()
    before = snapshot(lane)
    with pytest.raises(PersistenceIntegrityError):
        read(lane)
    assert snapshot(lane) == before


@pytest.mark.parametrize("companion", ["review", "candidate", "contribution", "parent", "child"])
def test_missing_companions_are_integrity_without_mutation(lane, companion):
    receipt = lane.receipt
    if companion == "review":
        lane.reviews._records.clear()
    elif companion in {"candidate", "contribution"}:
        state = lane.state
        value = (
            state.candidate_contribution
            if companion == "candidate"
            else state.reviewed_contribution
        )
        lane.reviews._contributions._items.pop((receipt.world_id, value.contribution_id))
    else:
        key = (
            receipt.expected_parent_revision_id
            if companion == "parent"
            else receipt.published_revision_id
        )
        lane.graph._revisions.pop((receipt.world_id, key))
    before = snapshot(lane)
    with pytest.raises(PersistenceIntegrityError):
        read(lane)
    assert snapshot(lane) == before


@pytest.mark.parametrize("damage", ["payload", "timestamp", "index", "family"])
def test_corrupt_companions_fail_closed(lane, damage):
    receipt = lane.receipt
    stored = lane.graph._revisions[(receipt.world_id, receipt.published_revision_id)]
    if damage == "payload":
        stored.graph_payload["corrupt"] = True
    elif damage == "timestamp":
        stored.revision.created_at += timedelta(seconds=1)
    elif damage == "family":
        wrong = receipt.model_copy(update={"schema_version": "unknown"})
        lane.publications._records_by_operation[(receipt.world_id, receipt.operation_id)] = wrong
        lane.publications._records_by_review[(receipt.world_id, receipt.review_id)] = wrong
        lane.publications._records_by_revision[
            (receipt.world_id, receipt.published_revision_id)
        ] = wrong
    else:
        wrong = receipt.model_copy(update={"confirmation_id": "confirmation:wrong"})
        lane.publications._records_by_review[(receipt.world_id, receipt.review_id)] = wrong
    before = snapshot(lane)
    with pytest.raises(PersistenceIntegrityError):
        read(lane)
    assert snapshot(lane) == before


@pytest.mark.parametrize("selector", ["world", "operation"])
def test_valid_receipt_under_a_foreign_selector_is_rejected(lane, selector):
    receipt = lane.receipt
    world = "world:wrong" if selector == "world" else receipt.world_id
    operation = "operation:wrong" if selector == "operation" else receipt.operation_id
    lane.publications._records_by_operation[(world, operation)] = receipt.model_copy(deep=True)
    with pytest.raises(PersistenceIntegrityError):
        lane.publications.read_verified_publication(world, operation)


def test_valid_parent_substituted_for_child_fails_selector_before_caching(lane):
    receipt = lane.receipt
    lane.graph._revisions[(receipt.world_id, receipt.published_revision_id)] = lane.parent
    with pytest.raises(PersistenceIntegrityError):
        read(lane)


def test_valid_foreign_review_is_rejected_before_caching(lane, monkeypatch):
    foreign = (
        setup_memory().state if lane.receipt.schema_version.endswith("v1") else _seed_review()[1]
    )
    # A fully valid state from the other fixture family, not a malformed copy.
    type(foreign).model_validate(foreign.model_dump(mode="json"))
    assert (foreign.record.world_id, foreign.record.review_id) != (
        lane.state.record.world_id,
        lane.state.record.review_id,
    )
    monkeypatch.setattr(lane.reviews, "get", lambda *args: foreign)
    with pytest.raises(PersistenceIntegrityError):
        read(lane)


def test_returned_models_are_detached_from_storage(lane):
    entry = read(lane)
    entry.revision.operation_ids.clear()
    entry.review.reviewed_contribution.assertions.clear()
    entry.publication.confirmation_id = "confirmation:caller-only"
    again = read(lane)
    assert again.publication == lane.receipt
    assert again.review == lane.state
    assert again.revision.operation_ids == [lane.receipt.operation_id]


def test_immutable_history_ignores_current_source_withdrawal(monkeypatch):
    lane = setup_memory(validator=SyntheticValidator())
    lane.receipt = lane.publications.publish(lane.command)
    for artifact in lane.sources._artifacts.values():
        artifact.status = "retracted"
    monkeypatch.setattr(lane.sources, "get_artifact", forbidden)
    monkeypatch.setattr(lane.sources, "get_provenance_snapshot", forbidden)
    assert read(lane).publication == lane.receipt
    key = next(iter(lane.sources._revisions))
    lane.sources._revisions[key].content_sha256 = "0" * 64
    with pytest.raises(PersistenceIntegrityError):
        read(lane)


def test_terminal_lookup_loads_one_review_and_only_original_parent_child(lane, monkeypatch):
    calls = Counter()
    original = lane.reviews.get

    def get_review(world, key):
        calls["review"] += 1
        return original(world, key)

    class CountedRevisions(dict):
        def get(self, key, default=None):
            calls[key[1]] += 1
            return super().get(key, default)

    monkeypatch.setattr(lane.reviews, "get", get_review)
    monkeypatch.setattr(lane.graph, "_revisions", CountedRevisions(lane.graph._revisions))
    monkeypatch.setattr(lane.graph, "get_head", forbidden)
    assert read(lane).review == lane.state
    assert calls == Counter(
        {
            "review": 1,
            lane.receipt.expected_parent_revision_id: 1,
            lane.receipt.published_revision_id: 1,
        }
    )


@pytest.mark.parametrize("mode", ["descendant", "rollback"])
def test_original_terminal_after_head_movement(lane, monkeypatch, mode):
    receipt = lane.receipt
    # Raw graph persistence is only setup, before the read tripwire.
    child = lane.graph._revisions[(receipt.world_id, receipt.published_revision_id)]
    if mode == "descendant":
        lane.graph.publish_revision(
            PublishRevisionCommand(
                world_id=receipt.world_id,
                parent_revision_id=receipt.published_revision_id,
                expected_parent_revision_id=receipt.published_revision_id,
                operation_ids=["later:operation"],
                graph_schema=receipt.graph_schema,
                graph_payload=child.graph_payload,
                created_at=receipt.published_at + timedelta(seconds=1),
            )
        )
    else:
        lane.graph.rollback_head(
            receipt.world_id,
            receipt.expected_parent_revision_id,
            updated_at=receipt.published_at + timedelta(seconds=1),
        )
    monkeypatch.setattr(lane.graph, "get_head", forbidden)
    assert read(lane).publication == receipt


@pytest.mark.parametrize(
    "ceiling", [frozenset(), {"dm_finalized_review_publication_v1"}, frozenset({"unknown"})]
)
def test_invalid_receipt_ceiling_refuses_before_io(ceiling):
    with pytest.raises(CapabilityDeniedError):
        read_historical_finalized_publication(
            "world",
            "op",
            reader=SimpleNamespace(
                read_verified_publication=forbidden,
            ),
            allowed_receipt_schemas=ceiling,
        )


def test_disallowed_receipt_family_is_not_downgraded_or_absence(lane):
    if lane.receipt.schema_version.endswith("v1"):
        assert (
            read_historical_finalized_publication(
                lane.receipt.world_id,
                lane.receipt.operation_id,
                reader=lane.publications,
                allowed_receipt_schemas=frozenset({"dm_finalized_review_publication_v1"}),
            ).publication
            == lane.receipt
        )
    else:
        with pytest.raises(CapabilityDeniedError):
            read_historical_finalized_publication(
                lane.receipt.world_id,
                lane.receipt.operation_id,
                reader=lane.publications,
                allowed_receipt_schemas=frozenset({"dm_finalized_review_publication_v1"}),
            )


def test_unavailability_never_becomes_absence():
    def unavailable(*args):
        raise PersistenceUnavailableError("offline")

    with pytest.raises(PersistenceUnavailableError):
        read_historical_finalized_publication(
            "world",
            "op",
            reader=SimpleNamespace(
                read_verified_publication=unavailable,
            ),
        )


def test_incomplete_aggregate_cannot_masquerade_as_absence(lane):
    entry = read(lane)
    broken = VerifiedPublicationHistoryEntry(entry.revision, entry.publication, None)
    with pytest.raises(PersistenceIntegrityError):
        read_historical_finalized_publication(
            lane.receipt.world_id,
            lane.receipt.operation_id,
            reader=SimpleNamespace(read_verified_publication=lambda *args: broken),
        )


def test_helper_has_no_direct_fresh_publisher_or_materializer_import():
    from dungeonmind.application.compatibility import publication_recovery

    source = ast.parse(Path(publication_recovery.__file__).read_text())
    imports = [node.module for node in ast.walk(source) if isinstance(node, ast.ImportFrom)]
    assert all(module is not None and "materializ" not in module for module in imports)
    assert "review_publication" not in imports
    # Core's existing eager parent initializer is a separate retirement gate.


def test_retained_v2_policy_is_required_even_without_current_validator():
    lane = setup_memory(validator=SyntheticValidator())
    lane.receipt = lane.publications.publish(lane.command)
    lane.publications._admission._policies.clear()
    with pytest.raises(PersistenceIntegrityError):
        read(lane)
