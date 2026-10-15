"""Observation-only terms are discoverable without rewriting canonical facts."""
from __future__ import annotations

import hashlib

import pytest

from dungeonmind.application.world_graph_retrieval import RetrievalBounds
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.domain.canonical import canonical_sha256
from tests.conformance import test_reviewed_source_observation_retrieval as f
from tests.conformance.test_v3_reviewed_source_observation_retrieval import v3_fixture

TEXT = "Representative of Commerce; concerned about the cult disrupting the festival."


def test_observation_only_search_returns_provenance_and_openable_source():
    service, graph, _sources, parent, child = f._fixture(text=TEXT)
    before = canonical_sha256(graph.get_revision(f.WORLD_ID, child).graph_payload)
    result = service.search(f._request(child), query_text="representative")
    assert f.EXISTING_OBJECT_ID in result.matched_object_ids
    matches = result.reviewed_source_observation_matches
    assert len(matches) == 1
    match = matches[0]
    assert match.assertion_id == f.ASSERTION_ID
    assert match.subject_object_id == f.EXISTING_OBJECT_ID
    assert match.text_excerpt == TEXT
    assert match.excerpt_start == 0 and match.excerpt_end == len(TEXT)
    assert match.text_length == len(TEXT)
    assert match.text_sha256 == hashlib.sha256(TEXT.encode()).hexdigest()
    assert match.publication_revision_id == child
    assert match.source_artifact_id == f.SOURCE_ARTIFACT_ID
    assert match.source_revision_id == f.SOURCE_REVISION_ID
    assert match.review_id.startswith("review:")
    assert match.contribution_id.startswith("contrib:")
    assert match.epistemic_kind
    assert "reviewed_source_observation" in result.match_reasons[f.EXISTING_OBJECT_ID]
    anchors = [a for a in result.anchors if match.assertion_id in a.supporting_assertion_ids]
    assert anchors
    assert service.resolve_source_anchor(f._request(child), anchor_id=anchors[0].anchor_id).found
    assert all(a.assertion_id != match.assertion_id for a in result.property_assertions)
    obj = next(o for o in result.objects if o.object_id == f.EXISTING_OBJECT_ID)
    assert obj.summary is None
    assert before == canonical_sha256(graph.get_revision(f.WORLD_ID, child).graph_payload)
    assert not service.search(f._request(parent), query_text="representative").matched_object_ids


@pytest.mark.parametrize("kwargs", [
    {"publish": False}, {"accepted": False}, {"text": {"not": "text"}},
    {"subject_id": "npc:not-admitted"},
])
def test_ineligible_observation_cannot_create_search_hit(kwargs):
    service, _graph, _sources, _parent, child = f._fixture(**{"text": TEXT, **kwargs})
    result = service.search(f._request(child), query_text="representative")
    assert not result.matched_object_ids
    assert not result.reviewed_source_observation_matches


def test_visibility_scope_and_missing_evidence_do_not_influence_search():
    service, _graph, sources, _parent, child = f._fixture(text=TEXT)
    for request in [f._request(child, admissibility=Admissibility.PLAYER),
                    f._request(child, campaign_id=None)]:
        result = service.search(request, query_text="representative")
        assert not result.matched_object_ids
        assert not result.reviewed_source_observation_matches
    sources._revisions.pop(f.SOURCE_REVISION_ID)
    broken = service.search(f._request(child), query_text="representative")
    assert not broken.matched_object_ids
    assert "evidence_source_revision_missing" in broken.coverage.gap_codes


def test_bounded_excerpt_is_exact_and_deterministic_without_false_full_text():
    text = "An introduction. " * 100 + TEXT + " Further background." * 100
    service, _graph, _sources, _parent, child = f._fixture(text=text, count=33)
    request = f._request(child)
    result = service.search(request, query_text="representative",
                            bounds=RetrievalBounds(max_assertions=2))
    assert len(result.reviewed_source_observation_matches) == 2
    assert len(result.property_assertions) + len(result.reviewed_source_observation_matches) <= 2
    assert "reviewed_source_observations" in result.coverage.truncated_fields
    assert "reviewed_source_observation_text" in result.coverage.truncated_fields
    for match in result.reviewed_source_observation_matches:
        assert len(match.text_excerpt) <= 768
        assert match.text_excerpt == text[match.excerpt_start:match.excerpt_end]
        assert "Representative of Commerce" in match.text_excerpt
        assert match.text_sha256 == hashlib.sha256(text.encode()).hexdigest()
        assert match.text_length == len(text)
    again = service.search(request, query_text="representative",
                           bounds=RetrievalBounds(max_assertions=2))
    assert result.reviewed_source_observation_matches == again.reviewed_source_observation_matches
    assert result.anchors == again.anchors
    assert result.match_reasons == again.match_reasons
    assert result.coverage == again.coverage


def test_exact_label_and_seed_still_outrank_observation_matches():
    service, _graph, _sources, _parent, child = f._fixture(
        text="Existing Location " * 100, count=33,
    )
    exact = service.search(f._request(child), query_text="Existing Location")
    assert exact.matched_object_ids[0] == "location:existing_location"
    seed = service.search(f._request(child), query_text="Existing Location",
                          seed_object_ids=["npc:new_npc"], bounds=RetrievalBounds(max_objects=1))
    assert seed.matched_object_ids == ("npc:new_npc",)
    assert not seed.reviewed_source_observation_matches


def test_alias_exclusions_apply_after_observation_scoring(monkeypatch):
    import dungeonmind.application.world_graph_retrieval as retrieval
    service, _graph, _sources, _parent, child = f._fixture(text=TEXT)
    for function in ["objects_blocked_by_omitted_aliases", "objects_blocked_by_ambiguous_aliases"]:
        with monkeypatch.context() as m:
            m.setattr(retrieval, function, lambda *_: {f.EXISTING_OBJECT_ID})
            result = service.search(f._request(child), query_text="representative")
            assert not result.matched_object_ids
            assert not result.reviewed_source_observation_matches


def test_empty_and_noise_only_queries_do_not_scan_review_history(monkeypatch):
    service, _graph, _sources, _parent, child = f._fixture(text=TEXT)
    def forbidden(*args, **kwargs):
        raise AssertionError("Empty discovery must not scan publications")
    monkeypatch.setattr(service, "_reviewed_source_observations", forbidden)
    for query in ["", "the", "and of the"]:
        result = service.search(f._request(child), query_text=query)
        assert not result.reviewed_source_observation_matches


def test_v3_worldbuilding_search_preserves_qualified_text_and_spans(monkeypatch):
    service, _graph, _sources, parent, child, _declarations, _values = v3_fixture(monkeypatch)
    request = f._request(child)
    result = service.search(request, query_text="goats")
    assert len(result.reviewed_source_observation_matches) == 6
    for match in result.reviewed_source_observation_matches:
        assert match.observation_kind == "worldbuilding_observation"
        assert "some communities believe" in match.text_excerpt
        anchors = [a for a in result.anchors if match.assertion_id in a.supporting_assertion_ids]
        assert anchors and anchors[0].source_span_ref_id
        assert service.resolve_source_anchor(request, anchor_id=anchors[0].anchor_id).found
    assert not service.search(f._request(parent), query_text="goats").matched_object_ids
    assert not service.search(
        f._request(child, campaign_id=None), query_text="goats",
    ).matched_object_ids



def test_corrected_observation_is_not_discovered_at_descendant(monkeypatch):
    from datetime import timedelta

    from dungeonmind.contracts.contribution import GraphContributionV2
    from dungeonmind.contracts.contribution_review_v2 import contribution_v2_payload_sha256
    from dungeonmind.contracts.graph import PublishRevisionCommand

    service, graph, _sources, _, child = f._fixture(text=TEXT)
    stored = graph.get_revision(f.WORLD_ID, child)
    descendant = graph.publish_revision(PublishRevisionCommand(
        world_id=f.WORLD_ID, parent_revision_id=child, expected_parent_revision_id=child,
        operation_ids=["search:correction"], graph_schema=f.GRAPH_SCHEMA_V6,
        graph_payload=stored.graph_payload, created_at=f.REVIEWED_AT + timedelta(minutes=2),
    ))
    publications = service._finalized_review_publications
    reviews = service._contribution_reviews
    prior = publications.get_for_published_revision(f.WORLD_ID, child)
    state = reviews.get(f.WORLD_ID, prior.review_id)
    raw = state.reviewed_contribution.model_dump(mode="json")
    raw.update(contribution_id="contrib:" + "c" * 32, assertions=[], assertion_corrections=[{
        "target_contribution_id": state.reviewed_contribution.contribution_id,
        "target_assertion_id": f.ASSERTION_ID, "correction_kind": "contradicts",
        "replacement_assertion_id": None,
    }])
    contribution = GraphContributionV2.model_validate(raw)
    digest = contribution_v2_payload_sha256(contribution)
    review_id = "review:" + "c" * 32
    corrected = state.model_copy(update={
        "record": state.record.model_copy(update={"review_id": review_id,
            "reviewed_contribution_id": contribution.contribution_id,
            "reviewed_contribution_sha256": digest}),
        "reviewed_contribution": contribution,
    })
    publication = prior.model_copy(update={
        "review_id": review_id, "reviewed_contribution_id": contribution.contribution_id,
        "reviewed_contribution_sha256": digest, "expected_parent_revision_id": child,
        "published_revision_id": descendant.revision_id,
    })
    original_publication = publications.get_for_published_revision
    original_review = reviews.get
    monkeypatch.setattr(publications, "get_for_published_revision", lambda w, r: (
        publication if r == descendant.revision_id else original_publication(w, r)))
    monkeypatch.setattr(reviews, "get", lambda w, r: (
        corrected if r == review_id else original_review(w, r)))
    assert service.search(f._request(child), query_text="representative").matched_object_ids
    result = service.search(f._request(descendant.revision_id), query_text="representative")
    assert not result.matched_object_ids
    assert not result.reviewed_source_observation_matches
    assert "reviewed_source_observation_correction_unresolved" in result.coverage.gap_codes
