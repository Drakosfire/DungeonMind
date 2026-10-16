"""Complete caller-owned ancestry facts; no cross-operation admitted cache."""
from dataclasses import replace

import pytest

from dungeonmind.application.world_graph_retrieval import ReviewedSourceDiscoveryRequest
from dungeonmind.domain.errors import PersistenceIntegrityError
from tests.conformance import test_reviewed_source_observation_retrieval as f


def test_memory_history_preserves_point_read_facts_and_caller_isolation():
    service, graph, _, root, pin = f._fixture()
    publications = service._finalized_review_publications
    rows = publications.read_verified_ancestry(f.WORLD_ID, pin)
    assert [row.revision.revision_id for row in rows] == [pin, root]
    assert rows[0].publication == publications.get_for_published_revision(f.WORLD_ID, pin)
    assert rows[0].review is not None
    before = graph.get_revision(f.WORLD_ID, pin)
    rows[0].revision.operation_ids.append('caller:only')
    rows[0].review.reviewed_contribution.assertions.clear()
    again = publications.read_verified_ancestry(f.WORLD_ID, pin)
    assert again[0].revision == before.revision
    assert again[0].review.reviewed_contribution.assertions
    assert again[1].publication is None and again[1].review is None


def test_memory_unknown_or_foreign_ancestry_is_integrity_error():
    service, _, _, _, pin = f._fixture()
    publications = service._finalized_review_publications
    for world, revision in [(f.WORLD_ID, 'missing'), ('other', pin)]:
        with pytest.raises(PersistenceIntegrityError):
            publications.read_verified_ancestry(world, revision)


def test_memory_cycle_is_rejected(monkeypatch):
    service, graph, _, root, pin = f._fixture()
    original = graph.get_revision
    def cyclic(world, revision):
        stored = original(world, revision)
        if stored is not None and revision == root:
            stored.revision.parent_revision_id = pin
        return stored
    monkeypatch.setattr(graph, 'get_revision', cyclic)
    with pytest.raises(PersistenceIntegrityError, match='cycle'):
        service._finalized_review_publications.read_verified_ancestry(f.WORLD_ID, pin)


@pytest.mark.parametrize('damage', ['truncated', 'reversed', 'foreign'])
def test_service_rejects_invalid_history_contract(monkeypatch, damage):
    service, _, _, _, pin = f._fixture()
    publications = service._finalized_review_publications
    rows = publications.read_verified_ancestry(f.WORLD_ID, pin)
    if damage == 'truncated':
        rows = rows[:1]
    elif damage == 'reversed':
        rows = tuple(reversed(rows))
    else:
        revision = rows[0].revision.model_copy(deep=True)
        revision.world_id = 'other'
        rows = (replace(rows[0], revision=revision), *rows[1:])
    monkeypatch.setattr(publications, 'read_verified_ancestry', lambda *args: rows)
    with pytest.raises(PersistenceIntegrityError):
        service.discover_reviewed_source_observations(ReviewedSourceDiscoveryRequest(
            f._request(pin), f.SOURCE_ARTIFACT_ID, f.SOURCE_REVISION_ID))
