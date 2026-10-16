"""Read-only historical discovery over real publication repository boundaries."""

from datetime import timedelta
from types import SimpleNamespace

import pytest

from dungeonmind.application import discover_review_publications
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError
from dungeonmind.infrastructure.memory import (
    InMemoryFinalizedReviewPublicationRepository,
    InMemoryWorldGraphRepository,
)
from tests.conformance.test_review_publication import (
    WORLD_ID,
    _publish,
    _seed_graph,
    _seed_review,
)


def _published():
    graph = InMemoryWorldGraphRepository()
    parent, reader = _seed_graph(graph)
    reviews, state = _seed_review()
    publications = InMemoryFinalizedReviewPublicationRepository(reviews, graph)
    receipt = _publish(reviews, graph, reader, publication_repository=publications)
    return SimpleNamespace(
        world_graph=graph, contribution_reviews=reviews,
        finalized_review_publications=publications,
    ), parent, state, receipt


def _discover(bundle, state, pin, **overrides):
    arguments = dict(
        world_id=state.record.world_id, revision_id=pin,
        reviewer_id=state.record.reviewer_id,
        source_plan_schema=state.record.plan_ref.source_plan_schema,
        world_graph_repository=bundle.world_graph,
        publication_repository=bundle.finalized_review_publications,
        review_repository=bundle.contribution_reviews,
    )
    arguments.update(overrides)
    return discover_review_publications(**arguments)


def _descendant(graph, parent_id, suffix):
    parent = graph.get_revision(WORLD_ID, parent_id)
    return graph.publish_revision(PublishRevisionCommand(
        world_id=WORLD_ID, parent_revision_id=parent_id,
        expected_parent_revision_id=parent_id, operation_ids=[f"op:ordinary:{suffix}"],
        graph_schema=parent.revision.graph_schema,
        graph_payload=parent.graph_payload,
        created_at=parent.revision.created_at + timedelta(seconds=1),
    ))


def test_real_publication_discovered_without_plan_or_write(monkeypatch):
    bundle, parent, state, receipt = _published()
    descendant = _descendant(bundle.world_graph, receipt.published_revision_id, "one")

    def forbidden(*args, **kwargs):
        raise AssertionError("history must not read mutable head or mutate")

    for owner, method in (
        (bundle.world_graph, "get_head"), (bundle.world_graph, "publish_revision"),
        (bundle.finalized_review_publications, "publish"),
        (bundle.contribution_reviews, "finalize"),
    ):
        monkeypatch.setattr(owner, method, forbidden)
    result = _discover(bundle, state, descendant.revision_id)
    assert result.scanned_revision_count == 3
    assert len(result.publications) == 1
    found = result.publications[0]
    assert found.publication == receipt
    assert found.review == state
    assert found.review.reviewed_contribution.assertions
    # Earlier pins cannot see later publications, even though mutable head moved.
    assert _discover(bundle, state, parent.revision.revision_id).publications == ()


@pytest.mark.parametrize("override", [
    {"reviewer_id": "another-run"}, {"source_plan_schema": "another-family"},
])
def test_exact_selectors_return_complete_zero(override):
    bundle, _parent, state, receipt = _published()
    result = _discover(bundle, state, receipt.published_revision_id, **override)
    assert result.publications == ()
    assert result.scanned_revision_count == 2


@pytest.mark.parametrize("change", ["missing", "world", "revision", "payload", "cycle"])
def test_broken_ancestry_never_returns_partial_result(monkeypatch, change):
    bundle, parent, state, receipt = _published()
    actual = bundle.world_graph.get_revision

    def changed(world_id, revision_id):
        stored = actual(world_id, revision_id)
        if revision_id != parent.revision.revision_id:
            return stored
        if change == "missing":
            return None
        if change == "payload":
            return stored.model_copy(update={"graph_payload": {"changed": True}})
        revision = stored.revision.model_copy(update={
            "world_id": "another-world" if change == "world" else WORLD_ID,
            "revision_id": "another-revision" if change == "revision" else revision_id,
            "parent_revision_id": receipt.published_revision_id if change == "cycle" else None,
        })
        return stored.model_copy(update={"revision": revision})

    monkeypatch.setattr(bundle.world_graph, "get_revision", changed)
    with pytest.raises(PersistenceIntegrityError):
        _discover(bundle, state, receipt.published_revision_id)


@pytest.mark.parametrize("change", ["missing", "wrong-review", "corrupt-review"])
def test_required_review_proof_cannot_be_skipped_by_selector(monkeypatch, change):
    bundle, _parent, state, receipt = _published()

    def changed(*args):
        if change == "missing":
            return None
        record = state.record.model_copy(update={
            "review_id": "another-review" if change == "wrong-review" else state.record.review_id,
            "reviewer_id": "tampered-reviewer",
        })
        return state.model_copy(update={"record": record})

    monkeypatch.setattr(bundle.contribution_reviews, "get", changed)
    with pytest.raises(PersistenceIntegrityError):
        _discover(bundle, state, receipt.published_revision_id, reviewer_id="no-match")


@pytest.mark.parametrize("field,value", [
    ("world_id", "another-world"), ("published_revision_id", "another-revision"),
    ("reviewed_contribution_sha256", "a" * 64),
    ("parent_graph_payload_sha256", "a" * 64),
])
def test_publication_cross_record_mismatch_refuses(monkeypatch, field, value):
    bundle, _parent, state, receipt = _published()
    monkeypatch.setattr(
        bundle.finalized_review_publications, "get_for_published_revision",
        lambda *args: receipt.model_copy(update={field: value}),
    )
    with pytest.raises((PersistenceIntegrityError, ValueError)):
        _discover(bundle, state, receipt.published_revision_id)


def test_authority_unavailable_is_not_empty(monkeypatch):
    bundle, _parent, state, receipt = _published()

    def unavailable(*args):
        raise PersistenceUnavailableError("synthetic unavailable authority")

    monkeypatch.setattr(
        bundle.finalized_review_publications, "get_for_published_revision", unavailable,
    )
    with pytest.raises(PersistenceUnavailableError):
        _discover(bundle, state, receipt.published_revision_id)


def test_long_complete_history_has_no_silent_cap():
    bundle, _parent, state, receipt = _published()
    pin = receipt.published_revision_id
    for index in range(130):
        pin = _descendant(bundle.world_graph, pin, str(index)).revision_id
    result = _discover(bundle, state, pin)
    assert result.scanned_revision_count == 132
    assert [item.publication for item in result.publications] == [receipt]


def test_multiple_publications_preserve_history_after_description_withdrawal(monkeypatch):
    from dungeonmind.application.review_publication import publish_finalized_review
    from tests.conformance import test_source_description_withdrawal as f

    _service, graph, _sources, reviews, publications, prior, first_child = f.setup(monkeypatch)
    world_id = prior.record.world_id
    parent = graph.get_revision(world_id, first_child)
    intent = f.withdrawal(prior, parent)
    correction = f.finalize(intent, graph, reviews)
    latest = publish_finalized_review(
        world_id, correction.record.review_id, published_at=intent.reviewed_at,
        review_repository=reviews, world_graph_repository=graph,
        publication_repository=publications, graph_reader=f.v2._reader(),
    )
    bundle = SimpleNamespace(
        world_graph=graph, contribution_reviews=reviews,
        finalized_review_publications=publications,
    )
    # Each exact family query sees its historical successes; withdrawal does not
    # erase the original publication or turn it into never-published coverage.
    historical = _discover(bundle, prior, latest.published_revision_id)
    assert prior.record.review_id in [
        item.review.record.review_id for item in historical.publications
    ]
    corrected = _discover(bundle, correction, latest.published_revision_id)
    assert prior.record.plan_ref.source_plan_schema == correction.record.plan_ref.source_plan_schema
    assert len(corrected.publications) == 2
    assert corrected.publications[0].publication == latest
    assert corrected.publications[0].review.reviewed_contribution.assertion_corrections
    earlier = _discover(bundle, correction, first_child)
    assert latest not in [item.publication for item in earlier.publications]


@pytest.mark.parametrize("field", ["world_id", "revision_id", "reviewer_id", "source_plan_schema"])
def test_blank_selectors_refused(field):
    bundle, _parent, state, receipt = _published()
    with pytest.raises(ValueError, match="nonblank"):
        _discover(bundle, state, receipt.published_revision_id, **{field: " "})
