"""Source discovery shares actual published-observation authority and corrections."""
from dataclasses import replace

import pytest

from dungeonmind.application.world_graph_retrieval import ReviewedSourceDiscoveryRequest
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.domain.errors import HeadNotFoundError
from tests.conformance import test_reviewed_source_observation_retrieval as f
from tests.conformance import test_source_description_withdrawal as w


def request(pin, **updates):
    fields = dict(projection=f._request(pin), source_artifact_id=f.SOURCE_ARTIFACT_ID,
                  source_revision_id=f.SOURCE_REVISION_ID)
    fields.update(updates)
    return ReviewedSourceDiscoveryRequest(**fields)


def test_paged_discovery_is_complete_deterministic_qualified_and_non_mutating(monkeypatch):
    service, graph, _sources, parent, pin = f._fixture(count=3, text='A qualified belief. ' * 30)
    before = graph.get_revision(f.WORLD_ID, pin)
    open_context = service._projection.open_read_context
    calls = []

    def counted(projection):
        calls.append(projection)
        return open_context(projection)

    monkeypatch.setattr(service._projection, 'open_read_context', counted)
    first = service.discover_reviewed_source_observations(request(pin, max_entries=1))
    assert len(calls) == 1
    assert first.offset == 0 and first.eligible_count == 3 and len(first.entries) == 1
    assert first.next_page_token and first.discovery_only
    assert first == replace(service.discover_reviewed_source_observations(
        request(pin, max_entries=1)), snapshot=first.snapshot)
    entries = list(first.entries)
    token = first.next_page_token
    offsets = [first.offset]
    while token:
        page = service.discover_reviewed_source_observations(
            request(pin, max_entries=1, page_token=token))
        assert page.eligible_count == 3 and page.snapshot.revision_id == pin
        entries.extend(page.entries)
        offsets.append(page.offset)
        token = page.next_page_token
    assert offsets == [0, 1, 2]
    assert len({entry.assertion_id for entry in entries}) == 3
    assert {entry.subject_object_id for entry in entries} == {f.EXISTING_OBJECT_ID}
    for entry in entries:
        assert entry.discovery_only and entry.excerpt_truncated and len(entry.excerpt) == 240
        assert entry.epistemic_kind and entry.observation_kind == 'session_observation'
        assert entry.source_anchors
        for anchor in entry.source_anchors:
            assert anchor.source_artifact_id == f.SOURCE_ARTIFACT_ID
            assert anchor.source_revision_id == f.SOURCE_REVISION_ID
            assert service.resolve_source_anchor(f._request(pin), anchor_id=anchor.anchor_id).found
    assert graph.get_revision(f.WORLD_ID, pin) == before
    assert not service.discover_reviewed_source_observations(request(parent)).entries


@pytest.mark.parametrize('update', [
    {'source_artifact_id': 'foreign-source'}, {'source_revision_id': 'another-source-revision'},
])
def test_exact_source_pair_never_substitutes_another_revision_or_artifact(update):
    service, _, _, _, pin = f._fixture()
    result = service.discover_reviewed_source_observations(request(pin, **update))
    assert result.entries == () and result.eligible_count == 0 and result.next_page_token is None


def test_foreign_world_player_visibility_and_unpublished_review_cannot_leak():
    service, _, _, _, pin = f._fixture()
    with pytest.raises(HeadNotFoundError):
        service.discover_reviewed_source_observations(request(pin,
            projection=f._request(pin).model_copy(update={'world_id': 'foreign-world'})))
    assert not service.discover_reviewed_source_observations(request(pin,
        projection=f._request(pin, admissibility=Admissibility.PLAYER))).entries
    unpublished, _, _, _, parent = f._fixture(publish=False)
    assert not unpublished.discover_reviewed_source_observations(request(parent)).entries


@pytest.mark.parametrize('change', ['source', 'revision', 'admissibility', 'page-size', 'offset'])
def test_cursor_cannot_cross_source_scope_revision_or_bounds(change):
    service, _, _, parent, pin = f._fixture(count=3)
    first = service.discover_reviewed_source_observations(request(pin, max_entries=1))
    next_request = request(pin, max_entries=1, page_token=first.next_page_token)
    if change == 'source':
        next_request = replace(next_request, source_artifact_id='foreign-source')
    elif change == 'revision':
        next_request = replace(next_request, projection=f._request(parent))
    elif change == 'admissibility':
        next_request = replace(next_request,
            projection=f._request(pin, admissibility=Admissibility.PLAYER))
    elif change == 'page-size':
        next_request = replace(next_request, max_entries=2)
    else:
        next_request = replace(next_request,
            page_token=first.next_page_token.rsplit(':', 1)[0] + ':999')
    with pytest.raises(ValueError, match='cursor'):
        service.discover_reviewed_source_observations(next_request)


def test_published_withdrawal_is_excluded_but_historical_source_discovery_survives(monkeypatch):
    service, graph, _, reviews, publications, prior, child = w.setup(monkeypatch)
    old = service.discover_reviewed_source_observations(request(child))
    assert w.n.NODE_ASSERTION in {entry.assertion_id for entry in old.entries}
    parent = graph.get_revision(f.WORLD_ID, child)
    state = w.finalize(w.withdrawal(prior, parent), graph, reviews)
    receipt = w.publish(state, graph, reviews, publications)
    current = service.discover_reviewed_source_observations(request(receipt.published_revision_id))
    assert w.n.NODE_ASSERTION not in {entry.assertion_id for entry in current.entries}
    historical = service.discover_reviewed_source_observations(request(child))
    assert historical.entries == old.entries


@pytest.mark.parametrize('update', [
    {'max_entries': 0}, {'max_entries': 65}, {'max_entries': True},
    {'source_revision_id': ' x'}, {'source_artifact_id': ''}, {'page_token': 12},
    {'page_token': ''}, {'page_token': 'invented'},
])
def test_malformed_request_refuses_before_any_read(update):
    with pytest.raises(ValueError):
        request('revision:test', **update)


def test_two_published_source_revisions_are_not_combined(monkeypatch):
    base_candidate = f._candidate_with_observation
    base_source = f._source
    second = 'source-revision:observation-v2'

    def candidate(**kwargs):
        value, verdicts = base_candidate(**kwargs)
        raw = value.model_dump(mode='json')
        row = next(a for a in raw['assertions'] if a['assertion_id'].endswith(':01'))
        row['source_revision_id'] = second
        for evidence in row['evidence_refs']:
            evidence['source_revision_id'] = second
            evidence['evidence_ref_id'] += ':revision-two'
        return f.GraphContributionV2.model_validate(raw), verdicts

    def source(sources, **kwargs):
        base_source(sources, **kwargs)
        if kwargs.get('revision_id') == f.SOURCE_REVISION_ID:
            sources.put_revision(f.SourceRevision(
                source_revision_id=second, source_artifact_id=f.SOURCE_ARTIFACT_ID,
                content_sha256='cd' * 32, body_storage='external', locator='test://second',
                created_at=f.REVIEWED_AT))

    monkeypatch.setattr(f, '_candidate_with_observation', candidate)
    monkeypatch.setattr(f, '_source', source)
    service, _, _, _, pin = f._fixture(count=2)
    first = service.discover_reviewed_source_observations(request(pin))
    later = service.discover_reviewed_source_observations(request(pin, source_revision_id=second))
    assert len(first.entries) == len(later.entries) == 1
    assert first.entries[0].assertion_id.endswith(':00')
    assert later.entries[0].assertion_id.endswith(':01')
    assert all(a.source_revision_id == second for a in later.entries[0].source_anchors)


def test_same_label_does_not_merge_distinct_published_subjects(monkeypatch):
    base_candidate = f._candidate_with_observation
    base_parent = f._v6_parent_payload

    def candidate(**kwargs):
        value, verdicts = base_candidate(**kwargs)
        raw = value.model_dump(mode='json')
        next(a for a in raw['assertions'] if a['assertion_id'].endswith(':01'))[
            'subject_object_id'] = 'npc:new_npc'
        return f.GraphContributionV2.model_validate(raw), verdicts

    def payload():
        raw = base_parent()
        next(o for o in raw['objects'] if o['object_id'] == f.EXISTING_OBJECT_ID)[
            'label'] = 'New NPC'
        return raw

    monkeypatch.setattr(f, '_candidate_with_observation', candidate)
    monkeypatch.setattr(f, '_v6_parent_payload', payload)
    service, _, _, _, pin = f._fixture(count=2)
    result = service.discover_reviewed_source_observations(request(pin))
    assert len(result.entries) == 2
    assert {entry.subject_object_id for entry in result.entries} == {
        f.EXISTING_OBJECT_ID, 'npc:new_npc'}
    assert len({entry.subject_label for entry in result.entries}) == 1


def test_historical_cursor_remains_valid_when_head_advances():
    service, graph, _, _, pin = f._fixture(count=3)
    first = service.discover_reviewed_source_observations(request(pin, max_entries=1))
    parent = graph.get_revision(f.WORLD_ID, pin)
    graph.publish_revision(f.PublishRevisionCommand(
        world_id=f.WORLD_ID, parent_revision_id=pin, expected_parent_revision_id=pin,
        operation_ids=['source-discovery:head-advance'], graph_schema=f.GRAPH_SCHEMA_V6,
        graph_payload=parent.graph_payload, created_at=f.REVIEWED_AT + f.timedelta(minutes=3)))
    second = service.discover_reviewed_source_observations(
        request(pin, max_entries=1, page_token=first.next_page_token))
    assert second.offset == 1 and second.eligible_count == 3
    assert second.snapshot.revision_id == pin and not second.snapshot.is_head


def test_unresolved_correction_has_same_exclusion_as_complete_object(monkeypatch):
    fixture = f._fixture
    checked = []

    def instrumented_fixture(**kwargs):
        service, *rest = fixture(**kwargs)
        complete = service.get_complete_object

        def checked_complete(projection, **options):
            result = complete(projection, **options)
            discovery = service.discover_reviewed_source_observations(
                request(projection.revision_pin, projection=projection))
            assert {entry.assertion_id for entry in discovery.entries} == {
                observation.assertion_id for observation in result.reviewed_source_observations}
            checked.append(len(discovery.entries))
            return result

        monkeypatch.setattr(service, 'get_complete_object', checked_complete)
        return service, *rest

    monkeypatch.setattr(f, '_fixture', instrumented_fixture)
    f.test_later_published_correction_marks_observation_unresolved(monkeypatch)
    assert checked == [0, 1]


def test_missing_publication_authority_is_not_reported_as_an_empty_source():
    service, _, sources, _, pin = f._fixture()
    legacy = f.WorldGraphRetrievalService(projection=service._projection, sources=sources)
    with pytest.raises(ValueError, match='publication authority ports'):
        legacy.discover_reviewed_source_observations(request(pin))
