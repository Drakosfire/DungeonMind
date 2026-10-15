"""Current V3 created descriptions stay readable as reviewed source evidence."""

from __future__ import annotations

import json

import pytest

from dungeonmind.application.contribution_review_v3 import _build_review_state
from dungeonmind.contracts.contribution import AcceptanceState, GraphContributionV3
from dungeonmind.contracts.contribution_review import derive_confirmation_id
from dungeonmind.contracts.contribution_review_v3 import (
    CommitConfirmationReceiptV3,
    ContributionReviewIntentV3,
    ContributionReviewSubmissionV3,
    contribution_v3_payload_sha256,
    derive_review_intent_sha256_v3,
)
from dungeonmind.contracts.evidence import SourceDomain
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.domain.canonical import canonical_sha256
from tests.conformance import test_reviewed_source_observation_retrieval as f
from tests.unit import test_contribution_review_v2 as review_fixture

NEW = "npc:new_npc"
NODE_ASSERTION = "assertion:test:node:new"
TEXT = "Representative of Commerce; some citizens believe she protects the festival."
BASE_CANDIDATE = f._candidate_with_observation
BASE_SOURCE = f._source
BASE_INTENT = f._intent
SOURCES = f.InMemorySourceRepository
PUBLICATIONS = f.InMemoryFinalizedReviewPublicationRepository


def current_fixture(
    monkeypatch,
    *,
    publish=True,
    source_kind="extraction",
    text=TEXT,
    typed=True,
    domain="worldbuilding",
    accepted=True,
):
    shared = {}

    def candidate(**kwargs):
        value, verdicts = BASE_CANDIDATE(**kwargs)
        raw = value.model_dump(mode="json")
        raw.update(schema_version="dm_graph_contribution_v3", source_kind=source_kind)
        raw["assertions"] = [
            a for a in raw["assertions"] if a["assertion_kind"] in {"node", "attribute", "alias"}
        ]
        ids = {a["assertion_id"] for a in raw["assertions"]}
        verdicts = [
            v.model_copy(
                update={
                    "acceptance_state": (
                        (
                            AcceptanceState.CANDIDATE
                            if accepted == "candidate"
                            else AcceptanceState.REJECTED
                        )
                        if v.assertion_id == NODE_ASSERTION and accepted is not True
                        else v.acceptance_state
                    )
                }
            )
            for v in verdicts
            if v.assertion_id in ids
        ]
        for assertion in raw["assertions"]:
            assertion.update(
                source_artifact_id=f.SOURCE_ARTIFACT_ID, source_revision_id=f.SOURCE_REVISION_ID
            )
            if assertion["assertion_kind"] == "node":
                payload = json.loads(assertion["value"])
                payload["summary"] = text
                assertion["value"] = json.dumps(payload)
            for ref in assertion["evidence_refs"]:
                ref["source_revision_id"] = f.SOURCE_REVISION_ID
                if typed:
                    ref.update(
                        schema_version="dm_evidence_ref_v2",
                        source_domain_key=domain,
                        source_domain=domain,
                        source_span_ref_id="span:" + assertion["assertion_id"],
                        session_id=None,
                        locator=None,
                        uri=None,
                        source_locator=None,
                        line_ref=None,
                    )
        return GraphContributionV3.model_validate(raw), verdicts

    def source(sources, **kwargs):
        if kwargs["artifact_id"] == f.SOURCE_ARTIFACT_ID:
            kwargs["source_domain"] = SourceDomain(domain)
        return BASE_SOURCE(sources, **kwargs)

    def intent(**kwargs):
        accepted_ids = {
            v.assertion_id
            for v in kwargs["assertion_verdicts"]
            if v.acceptance_state is AcceptanceState.ACCEPTED
        }
        targets = {
            a.subject_object_id
            for a in kwargs["candidate"].assertions
            if a.assertion_id in accepted_ids and a.assertion_kind in {"node", "alias"}
        }
        old = BASE_INTENT(
            **kwargs,
            identity_proposals=[
                p for p in review_fixture._proposals() if p.target_object_id in targets
            ],
            identity_verdicts=[
                v for v in review_fixture._identity_verdicts() if v.target_object_id in targets
            ],
        )
        fields = {
            key: getattr(old, key)
            for key in (
                "operation_id",
                "world_id",
                "campaign_id",
                "plan_ref",
                "candidate_contribution",
                "identity_proposals",
                "identity_verdicts",
                "assertion_verdicts",
                "reviewer_id",
                "reviewed_at",
            )
        }
        fields["plan_ref"] = old.plan_ref.model_copy(
            update={
                "candidate_contribution_sha256": contribution_v3_payload_sha256(
                    old.candidate_contribution
                ),
            }
        )
        return ContributionReviewIntentV3(
            **fields, review_intent_sha256=derive_review_intent_sha256_v3(**fields)
        )

    def submission(intent):
        return ContributionReviewSubmissionV3(
            intent=intent,
            confirmation=CommitConfirmationReceiptV3(
                confirmation_id=derive_confirmation_id(
                    operation_id=intent.operation_id,
                    review_intent_sha256=intent.review_intent_sha256,
                    actor=intent.reviewer_id,
                    confirmed_at=intent.reviewed_at,
                ),
                operation_id=intent.operation_id,
                review_intent_sha256=intent.review_intent_sha256,
                actor=intent.reviewer_id,
                world_id=intent.world_id,
                campaign_id=intent.campaign_id,
                expected_parent_revision_id=intent.plan_ref.expected_parent_revision_id,
                confirmed_at=intent.reviewed_at,
            ),
        )

    def sources():
        shared["sources"] = SOURCES()
        return shared["sources"]

    for name, value in {
        "_candidate_with_observation": candidate,
        "_source": source,
        "_intent": intent,
        "_submission": submission,
        "_build_review_state": _build_review_state,
        "InMemorySourceRepository": sources,
        "InMemoryFinalizedReviewPublicationRepository": lambda reviews, graph: PUBLICATIONS(
            reviews, graph, source_repository=shared["sources"]
        ),
    }.items():
        monkeypatch.setattr(f, name, value)
    return f._fixture(text="Existing keeper remembers the festival.", publish=publish)


def test_current_created_description_read_search_and_open_without_graph_rewrite(monkeypatch):
    service, graph, _sources, parent, child = current_fixture(monkeypatch)
    before = canonical_sha256(graph.get_revision(f.WORLD_ID, child).graph_payload)
    result = service.get_complete_object(f._request(child), object_id=NEW)
    assert result.found and result.object.summary is None
    assert len(result.reviewed_source_observations) == 1
    observation = result.reviewed_source_observations[0]
    assert observation.text == TEXT
    assert observation.assertion_id == NODE_ASSERTION
    assert observation.observation_kind == "worldbuilding_observation"
    assert observation.subject_object_id == NEW
    assert observation.publication_revision_id == child
    assert observation.source_revision_id == f.SOURCE_REVISION_ID
    assert "some citizens believe" in observation.text
    anchors = [a for a in result.anchors if NODE_ASSERTION in a.supporting_assertion_ids]
    assert anchors and anchors[0].source_span_ref_id
    assert service.resolve_source_anchor(f._request(child), anchor_id=anchors[0].anchor_id).found
    search = service.search(f._request(child), query_text="representative")
    assert NEW in search.matched_object_ids
    assert any(m.assertion_id == NODE_ASSERTION for m in search.reviewed_source_observation_matches)
    assert not service.get_complete_object(f._request(parent), object_id=NEW).found
    existing = service.get_complete_object(f._request(child), object_id=f.EXISTING_OBJECT_ID)
    assert (
        existing.reviewed_source_observations[0].text == "Existing keeper remembers the festival."
    )
    assert before == canonical_sha256(graph.get_revision(f.WORLD_ID, child).graph_payload)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"publish": False},
        {"accepted": False},
        {"source_kind": "graph_review"},
        {"source_kind": "manual_import"},
        {"domain": "session_recap"},
        {"text": None},
        {"text": ""},
        {"text": 12},
        {"text": {"bad": "shape"}},
    ],
)
def test_other_node_values_never_become_worldbuilding_observations(monkeypatch, kwargs):
    service, _graph, _sources, _parent, child = current_fixture(monkeypatch, **kwargs)
    result = service.get_complete_object(f._request(child), object_id=NEW)
    assert not result.reviewed_source_observations
    assert (
        NEW not in service.search(f._request(child), query_text="representative").matched_object_ids
    )


def test_untyped_evidence_is_rejected_by_current_v3_contract(monkeypatch):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        current_fixture(monkeypatch, typed=False)


def test_visibility_scope_and_missing_source_still_exclude_created_description(monkeypatch):
    service, _graph, sources, _parent, child = current_fixture(monkeypatch)
    for request in [
        f._request(child, admissibility=Admissibility.PLAYER),
        f._request(child, campaign_id=None),
    ]:
        assert not service.get_complete_object(request, object_id=NEW).reviewed_source_observations
        assert NEW not in service.search(request, query_text="representative").matched_object_ids
    sources._revisions.pop(f.SOURCE_REVISION_ID)
    result = service.get_complete_object(f._request(child), object_id=NEW)
    assert not result.reviewed_source_observations
    assert "evidence_source_revision_missing" in result.coverage.gap_codes


def test_v2_node_summary_is_not_promoted_to_current_description_facet():
    # A historical node-shaped value is not evidence of current typed admission.
    from dungeonmind.application.world_graph_retrieval import WorldGraphRetrievalService
    from dungeonmind.contracts.contribution import GraphContributionAssertionV2

    assertion = GraphContributionAssertionV2(
        assertion_id="legacy:node",
        assertion_kind="node",
        subject_object_id=NEW,
        value=json.dumps({"summary": TEXT, "kind": "npc"}),
    )
    assert WorldGraphRetrievalService._observation_value(assertion, node_description=True) is None


def test_unfinalizable_candidate_node_is_not_a_read_authority(monkeypatch):
    from dungeonmind.domain.errors import ContributionReviewValidationError

    with pytest.raises(ContributionReviewValidationError):
        current_fixture(monkeypatch, accepted="candidate")
