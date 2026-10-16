"""Published extraction descriptions can be withdrawn without deleting objects."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from pydantic import ValidationError

from dungeonmind.application.contribution_review_v3 import finalize_contribution_review_v3
from dungeonmind.application.review_materialization_v6 import materialize_finalized_review_v6
from dungeonmind.application.review_publication import publish_finalized_review
from dungeonmind.application.source_description_correction import (
    verify_source_description_corrections,
)
from dungeonmind.contracts.contribution import (
    GraphContributionAssertionCorrection,
    GraphContributionV3,
)
from dungeonmind.contracts.contribution_review_v3 import (
    FINALIZE_REVIEW_V3_TOOL,
    ContributionReviewIntentV3,
    contribution_v3_payload_sha256,
    derive_review_intent_sha256_v3,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.domain.errors import ContributionMaterializationError
from tests.conformance import test_current_node_source_observations as n
from tests.conformance import test_reviewed_source_observation_retrieval as f
from tests.unit import test_contribution_review_v2 as v2

KIND = "contradicts_source_description"


def setup(monkeypatch, **options):
    service, graph, sources, _root, child = n.current_fixture(monkeypatch, **options)
    publications = service._finalized_review_publications
    reviews = service._contribution_reviews
    publication = publications.get_for_published_revision(f.WORLD_ID, child)
    prior = reviews.get(f.WORLD_ID, publication.review_id)
    return service, graph, sources, reviews, publications, prior, child


def withdrawal(prior, parent, *, suffix="a", target=None, target_contribution=None, **updates):
    candidate = GraphContributionV3(
        contribution_id="contrib:withdrawal:" + suffix,
        world_id=f.WORLD_ID,
        source_kind="graph_review",
        source_artifact_id=f.SOURCE_ARTIFACT_ID,
        source_revision_id=f.SOURCE_REVISION_ID,
        produced_at=f.REVIEWED_AT,
        campaign_scope=f.CAMPAIGN_ID,
        diagnostics={
            "source_description_withdrawal_reason": "Source does not support this interpretation."
        },
        assertion_corrections=[
            GraphContributionAssertionCorrection(
                correction_kind=KIND,
                target_contribution_id=target_contribution
                or prior.reviewed_contribution.contribution_id,
                target_assertion_id=target or n.NODE_ASSERTION,
            )
        ],
    )
    if updates:
        raw = candidate.model_dump(mode="json")
        raw.update(updates)
        candidate = GraphContributionV3.model_validate(raw)
    plan = v2._plan_ref(candidate, parent).model_copy(
        update={
            "candidate_contribution_sha256": contribution_v3_payload_sha256(candidate),
            "source_plan_id": "plan:withdrawal:" + suffix,
        }
    )
    fields = dict(
        operation_id="reviewop:" + suffix * 32,
        world_id=f.WORLD_ID,
        campaign_id=f.CAMPAIGN_ID,
        plan_ref=plan,
        candidate_contribution=candidate,
        identity_proposals=[],
        identity_verdicts=[],
        assertion_verdicts=[],
        reviewer_id=prior.record.reviewer_id,
        reviewed_at=f.REVIEWED_AT,
    )
    return ContributionReviewIntentV3(
        **fields, review_intent_sha256=derive_review_intent_sha256_v3(**fields)
    )


def finalize(intent, graph, reviews):
    policy = v2._policy(intent)
    rule = policy.tool_rules[0].model_copy(update={"tool_name": FINALIZE_REVIEW_V3_TOOL})
    policy = policy.model_copy(
        update={"enabled_tools": [FINALIZE_REVIEW_V3_TOOL], "tool_rules": [rule]}
    )
    return finalize_contribution_review_v3(
        f._submission(intent),
        capability_policy=policy,
        world_graph_repository=graph,
        review_repository=reviews,
    )


def publish(state, graph, reviews, publications):
    return publish_finalized_review(
        f.WORLD_ID,
        state.record.review_id,
        published_at=f.REVIEWED_AT + timedelta(minutes=2),
        review_repository=reviews,
        world_graph_repository=graph,
        publication_repository=publications,
        graph_reader=f._reader(),
    )


def test_finalize_publish_fresh_read_and_historical_citation(monkeypatch):
    service, graph, sources, reviews, publications, prior, child = setup(monkeypatch)
    parent = graph.get_revision(f.WORLD_ID, child)
    old = service.get_complete_object(f._request(child), object_id=n.NEW)
    anchor = next(a for a in old.anchors if n.NODE_ASSERTION in a.supporting_assertion_ids)
    state = finalize(withdrawal(prior, parent), graph, reviews)
    receipt = publish(state, graph, reviews, publications)
    current = graph.get_revision(f.WORLD_ID, receipt.published_revision_id)
    assert current.graph_payload == parent.graph_payload
    assert state.record.reviewer_id
    assert state.reviewed_contribution.diagnostics["source_description_withdrawal_reason"]
    # Fresh service instance, not a mutated/cached earlier result.
    fresh = type(service)(
        projection=service._projection,
        sources=sources,
        world_graph=graph,
        contribution_reviews=reviews,
        finalized_review_publications=publications,
    )
    result = fresh.get_complete_object(f._request(receipt.published_revision_id), object_id=n.NEW)
    assert result.found and result.reviewed_source_observations == ()
    search = fresh.search(f._request(receipt.published_revision_id), query_text="Representative")
    assert all(
        m.assertion_id != n.NODE_ASSERTION for m in search.reviewed_source_observation_matches
    )
    assert fresh.get_complete_object(
        f._request(child), object_id=n.NEW
    ).reviewed_source_observations
    assert fresh.resolve_source_anchor(f._request(child), anchor_id=anchor.anchor_id).found
    assert publish(state, graph, reviews, publications) == receipt
    descendant = graph.publish_revision(
        PublishRevisionCommand(
            world_id=f.WORLD_ID,
            parent_revision_id=receipt.published_revision_id,
            expected_parent_revision_id=receipt.published_revision_id,
            operation_ids=["test:description-withdrawal:descendant"],
            graph_schema=parent.revision.graph_schema,
            graph_payload=current.graph_payload,
            created_at=f.REVIEWED_AT + timedelta(minutes=3),
        )
    )
    assert (
        fresh.get_complete_object(
            f._request(descendant.revision_id), object_id=n.NEW
        ).reviewed_source_observations
        == ()
    )


def test_missing_forged_and_stale_proof_fail_closed(monkeypatch):
    _service, graph, _sources, reviews, publications, prior, child = setup(monkeypatch)
    parent = graph.get_revision(f.WORLD_ID, child)
    state = finalize(withdrawal(prior, parent), graph, reviews)
    with pytest.raises(ContributionMaterializationError) as exc:
        materialize_finalized_review_v6(state, parent=parent, graph_reader=f._reader())
    assert exc.value.reason == "source_description_correction_proof_required"
    proof = verify_source_description_corrections(
        state, parent=parent, world_graph=graph, reviews=reviews, publications=publications
    )
    for invalid in [
        replace(proof, _issuer=None),
        replace(proof, parent_revision_id="other"),
        replace(proof, contribution_sha256="0" * 64),
        replace(proof, targets=frozenset()),
    ]:
        with pytest.raises(ContributionMaterializationError) as exc:
            materialize_finalized_review_v6(
                state,
                parent=parent,
                graph_reader=f._reader(),
                source_description_correction_proof=invalid,
            )
        assert exc.value.reason == "source_description_correction_proof_mismatch"


@pytest.mark.parametrize("target", [f.ASSERTION_ID, "ka:adopted", "assertion:missing"])
def test_non_description_and_missing_targets_reject(monkeypatch, target):
    _s, graph, _sources, reviews, publications, prior, child = setup(monkeypatch)
    parent = graph.get_revision(f.WORLD_ID, child)
    state = finalize(withdrawal(prior, parent, target=target), graph, reviews)
    with pytest.raises(ContributionMaterializationError):
        publish(state, graph, reviews, publications)
    assert graph.get_head(f.WORLD_ID).head_revision_id == child


def test_unpublished_foreign_contribution_target_rejects(monkeypatch):
    _s, graph, _sources, reviews, publications, prior, child = setup(monkeypatch)
    state = finalize(
        withdrawal(
            prior,
            graph.get_revision(f.WORLD_ID, child),
            target_contribution="contrib:foreign-or-unpublished",
        ),
        graph,
        reviews,
    )
    with pytest.raises(ContributionMaterializationError) as exc:
        publish(state, graph, reviews, publications)
    assert exc.value.reason == "source_description_correction_target_unresolvable"


def test_repeated_withdrawal_rejected_but_exact_replay_preserved(monkeypatch):
    _s, graph, _sources, reviews, publications, prior, child = setup(monkeypatch)
    first = finalize(withdrawal(prior, graph.get_revision(f.WORLD_ID, child)), graph, reviews)
    receipt = publish(first, graph, reviews, publications)
    parent = graph.get_revision(f.WORLD_ID, receipt.published_revision_id)
    second = finalize(withdrawal(prior, parent, suffix="b"), graph, reviews)
    with pytest.raises(ContributionMaterializationError) as exc:
        publish(second, graph, reviews, publications)
    assert exc.value.reason == "source_description_correction_already_withdrawn"
    assert publish(first, graph, reviews, publications) == receipt


def test_withdrawal_kind_requires_no_replacement_and_old_serialization_stays_exact():
    with pytest.raises(ValidationError):
        GraphContributionAssertionCorrection(
            correction_kind=KIND,
            target_contribution_id="c",
            target_assertion_id="a",
            replacement_assertion_id="r",
        )
    for kind, replacement in [("contradicts", None), ("contradicts_and_replaces", "r")]:
        raw = {
            "correction_kind": kind,
            "target_contribution_id": "c",
            "target_assertion_id": "a",
            "replacement_assertion_id": replacement,
        }
        assert (
            GraphContributionAssertionCorrection.model_validate(raw).model_dump(mode="json") == raw
        )


@pytest.mark.parametrize(
    "options",
    [
        {"source_kind": "manual_import"},
        {"text": ""},
        {"accepted": False},
    ],
)
def test_only_supported_current_extraction_descriptions_are_withdrawable(monkeypatch, options):
    _s, graph, _sources, reviews, publications, prior, child = setup(monkeypatch, **options)
    state = finalize(withdrawal(prior, graph.get_revision(f.WORLD_ID, child)), graph, reviews)
    with pytest.raises(ContributionMaterializationError):
        publish(state, graph, reviews, publications)
    assert graph.get_head(f.WORLD_ID).head_revision_id == child


def test_unrelated_same_subject_observation_is_preserved(monkeypatch):
    original = n.BASE_CANDIDATE

    def candidate(**kwargs):
        value, verdicts = original(**kwargs)
        for assertion in value.assertions:
            if assertion.assertion_kind == "attribute":
                assertion.subject_object_id = n.NEW
        return value, verdicts

    monkeypatch.setattr(n, "BASE_CANDIDATE", candidate)
    service, graph, _sources, reviews, publications, prior, child = setup(monkeypatch)
    before = service.get_complete_object(f._request(child), object_id=n.NEW)
    assert len(before.reviewed_source_observations) == 2
    state = finalize(withdrawal(prior, graph.get_revision(f.WORLD_ID, child)), graph, reviews)
    receipt = publish(state, graph, reviews, publications)
    after = service.get_complete_object(f._request(receipt.published_revision_id), object_id=n.NEW)
    assert [o.assertion_id for o in after.reviewed_source_observations] == [f.ASSERTION_ID]
    assert after.object == before.object
    assert after.relationships == before.relationships


def test_duplicate_targets_reject(monkeypatch):
    _s, graph, _sources, reviews, publications, prior, child = setup(monkeypatch)
    intent = withdrawal(prior, graph.get_revision(f.WORLD_ID, child))
    row = intent.candidate_contribution.assertion_corrections[0].model_dump(mode="json")
    intent = withdrawal(
        prior, graph.get_revision(f.WORLD_ID, child), assertion_corrections=[row, row]
    )
    state = finalize(intent, graph, reviews)
    with pytest.raises(ContributionMaterializationError) as exc:
        publish(state, graph, reviews, publications)
    assert exc.value.reason == "source_description_correction_duplicate"


def test_competing_withdrawals_preserve_writer_compare_and_swap(monkeypatch):
    from dungeonmind.domain.errors import StaleParentRevisionError

    _s, graph, _sources, reviews, publications, prior, child = setup(monkeypatch)
    parent = graph.get_revision(f.WORLD_ID, child)
    first = finalize(withdrawal(prior, parent), graph, reviews)
    second = finalize(withdrawal(prior, parent, suffix="b"), graph, reviews)
    receipt = publish(first, graph, reviews, publications)
    with pytest.raises(StaleParentRevisionError):
        publish(second, graph, reviews, publications)
    assert graph.get_head(f.WORLD_ID).head_revision_id == receipt.published_revision_id


@pytest.mark.parametrize(
    "updates",
    [
        {"source_artifact_id": "artifact:foreign"},
        {"source_revision_id": "revision:foreign"},
    ],
)
def test_withdrawal_source_identity_must_match_target(monkeypatch, updates):
    _s, graph, _sources, reviews, publications, prior, child = setup(monkeypatch)
    state = finalize(
        withdrawal(prior, graph.get_revision(f.WORLD_ID, child), **updates), graph, reviews
    )
    with pytest.raises(ContributionMaterializationError) as exc:
        publish(state, graph, reviews, publications)
    assert exc.value.reason == "source_description_correction_source_mismatch"


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reason_is_required_and_empty_ordinary_reviews_still_reject(monkeypatch, reason):
    _s, graph, _sources, _reviews, _publications, prior, child = setup(monkeypatch)
    parent = graph.get_revision(f.WORLD_ID, child)
    with pytest.raises(ValidationError):
        withdrawal(prior, parent, diagnostics={"source_description_withdrawal_reason": reason})
    with pytest.raises(ValidationError, match="empty review"):
        withdrawal(prior, parent, assertion_corrections=[])


def test_new_kind_cannot_enter_v2_contributions(monkeypatch):
    from dungeonmind.contracts.contribution import GraphContributionV2

    _s, graph, _sources, _reviews, _publications, prior, child = setup(monkeypatch)
    raw = withdrawal(
        prior, graph.get_revision(f.WORLD_ID, child)
    ).candidate_contribution.model_dump(mode="json")
    raw["schema_version"] = "dm_graph_contribution_v2"
    with pytest.raises(ValidationError):
        GraphContributionV2.model_validate(raw)


def test_withdrawal_does_not_bypass_review_capability(monkeypatch):
    from dungeonmind.domain.errors import CapabilityDeniedError

    _s, graph, _sources, reviews, _publications, prior, child = setup(monkeypatch)
    intent = withdrawal(prior, graph.get_revision(f.WORLD_ID, child))
    with pytest.raises(CapabilityDeniedError):
        finalize_contribution_review_v3(
            f._submission(intent),
            capability_policy=v2._policy(intent),
            world_graph_repository=graph,
            review_repository=reviews,
        )
    assert graph.get_head(f.WORLD_ID).head_revision_id == child


def test_published_node_without_complete_evidence_cannot_be_withdrawn_as_description(monkeypatch):
    original = n.BASE_CANDIDATE

    def candidate(**kwargs):
        value, verdicts = original(**kwargs)
        for assertion in value.assertions:
            if assertion.assertion_kind == "node":
                assertion.evidence_refs = []
        return value, verdicts

    monkeypatch.setattr(n, "BASE_CANDIDATE", candidate)
    _s, graph, _sources, reviews, publications, prior, child = setup(monkeypatch)
    state = finalize(withdrawal(prior, graph.get_revision(f.WORLD_ID, child)), graph, reviews)
    with pytest.raises(ContributionMaterializationError) as exc:
        publish(state, graph, reviews, publications)
    assert exc.value.reason == "source_description_correction_source_mismatch"


def test_corrupt_ancestry_fails_integrity_before_publication(monkeypatch):
    from dungeonmind.domain.errors import PersistenceIntegrityError

    _s, graph, _sources, reviews, publications, prior, child = setup(monkeypatch)
    parent = graph.get_revision(f.WORLD_ID, child)
    state = finalize(withdrawal(prior, parent), graph, reviews)
    original = graph.get_revision
    broken = parent.model_copy(
        update={"revision": parent.revision.model_copy(update={"parent_revision_id": child})}
    )
    monkeypatch.setattr(
        graph, "get_revision", lambda w, r: broken if r == child else original(w, r)
    )
    with pytest.raises(PersistenceIntegrityError):
        publish(state, graph, reviews, publications)
    assert graph.get_head(f.WORLD_ID).head_revision_id == child
