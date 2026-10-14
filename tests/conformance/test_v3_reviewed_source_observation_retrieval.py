"""Current typed review evidence stays visible in the source-observation facet."""

import hashlib
import json

import pytest

from dungeonmind.application.contribution_review_v3 import _build_review_state
from dungeonmind.contracts.contribution import GraphContributionV2, GraphContributionV3
from dungeonmind.contracts.contribution_review import derive_confirmation_id
from dungeonmind.contracts.contribution_review_v2 import (
    ContributionReviewStateV2,
    contribution_v2_payload_sha256,
)
from dungeonmind.contracts.contribution_review_v3 import (
    CommitConfirmationReceiptV3,
    ContributionReviewIntentV3,
    ContributionReviewStateV3,
    ContributionReviewSubmissionV3,
    contribution_v3_payload_sha256,
    derive_review_intent_sha256_v3,
)
from dungeonmind.contracts.evidence import SourceDomain
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.domain.errors import PersistenceIntegrityError
from tests.conformance import test_reviewed_source_observation_retrieval as f

CANDIDATE = f._candidate_with_observation
SOURCE = f._source
INTENT = f._intent
SOURCES = f.InMemorySourceRepository
PUBLICATIONS = f.InMemoryFinalizedReviewPublicationRepository


def v3_fixture(monkeypatch, *, kind="worldbuilding_observation", publish=True, accepted=True):
    declarations = {}
    shared = {}
    values = tuple(
        (kind, f"Section {i}: some communities believe goats float; Example: cloak {i}.")
        for i in range(6)
    )

    def candidate(**kwargs):
        raw, verdicts = CANDIDATE(**kwargs)
        raw = raw.model_dump(mode="json")
        raw.update(schema_version="dm_graph_contribution_v3", source_kind="extraction")
        raw["assertions"] = [a for a in raw["assertions"] if a["assertion_kind"] == "attribute"]
        ids = {a["assertion_id"] for a in raw["assertions"]}
        verdicts = [v for v in verdicts if v.assertion_id in ids]
        for assertion in raw["assertions"]:
            for ref in assertion["evidence_refs"]:
                # Explicit synthetic source declarations, never locator/ID inference.
                span = "fixture:declared-span:" + assertion["assertion_id"]
                binding = {
                    "artifact": ref["source_artifact_id"],
                    "revision": ref["source_revision_id"],
                    "span": span,
                }
                ref.update(
                    schema_version="dm_evidence_ref_v2",
                    source_domain_key="worldbuilding",
                    source_domain="worldbuilding",
                    source_span_ref_id=span,
                    session_id=None,
                    locator=None,
                    uri=None,
                    source_locator=None,
                    line_ref=None,
                )
                ref["evidence_ref_id"] += (
                    ":fixture-v3:"
                    + hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
                )
                declarations[ref["evidence_ref_id"]] = span
        return GraphContributionV3.model_validate(raw), verdicts

    def source(sources, **kwargs):
        if kwargs["artifact_id"] == f.SOURCE_ARTIFACT_ID:
            kwargs["source_domain"] = SourceDomain.WORLDBUILDING
        return SOURCE(sources, **kwargs)

    def intent(**kwargs):
        old = INTENT(**kwargs, identity_proposals=[], identity_verdicts=[])
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
                )
            }
        )
        return ContributionReviewIntentV3(
            **fields, review_intent_sha256=derive_review_intent_sha256_v3(**fields)
        )

    def submission(intent):
        confirmation = CommitConfirmationReceiptV3(
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
        )
        return ContributionReviewSubmissionV3(intent=intent, confirmation=confirmation)

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
    service, graph, repository, parent, child = f._fixture(
        observation_values=values,
        authored_summary="Original authored prose.",
        publish=publish,
        accepted=accepted,
    )
    return service, graph, repository, parent, child, declarations, values


@pytest.mark.parametrize("kind", ["worldbuilding_observation", "session_observation"])
def test_v3_six_observations_keep_typed_spans_and_authored_prose(monkeypatch, kind):
    service, graph, _, parent, child, spans, values = v3_fixture(monkeypatch, kind=kind)
    before = graph.get_revision(f.WORLD_ID, child).graph_payload
    result = service.get_complete_object(f._request(child), object_id=f.EXISTING_OBJECT_ID)
    assert len(result.reviewed_source_observations) == 6
    assert len({r.assertion_id for r in result.reviewed_source_observations}) == 6
    assert sorted(
        (r.observation_kind, r.text) for r in result.reviewed_source_observations
    ) == sorted(values)
    assert result.object.summary == "Original authored prose."
    for observation in result.reviewed_source_observations:
        anchors = [
            a for a in result.anchors if observation.assertion_id in a.supporting_assertion_ids
        ]
        assert anchors
        assert all(a.source_span_ref_id == spans[a.evidence_ref_id] for a in anchors)
        assert all(a.evidence.source_domain is SourceDomain.WORLDBUILDING for a in anchors)
        assert all(
            service.resolve_source_anchor(f._request(child), anchor_id=a.anchor_id).found
            for a in anchors
        )
    assert graph.get_revision(f.WORLD_ID, child).graph_payload == before
    assert (
        service.get_complete_object(
            f._request(parent), object_id=f.EXISTING_OBJECT_ID
        ).reviewed_source_observations
        == ()
    )


@pytest.mark.parametrize(
    "kwargs", [{"publish": False}, {"accepted": False}, {"kind": "unknown_observation"}]
)
def test_v3_does_not_bypass_review_publication_or_supported_kind(monkeypatch, kwargs):
    service, _, _, _, child, _, _ = v3_fixture(monkeypatch, **kwargs)
    assert (
        service.get_complete_object(
            f._request(child), object_id=f.EXISTING_OBJECT_ID
        ).reviewed_source_observations
        == ()
    )


def test_v3_visibility_scope_and_missing_source_still_exclude(monkeypatch):
    service, _, sources, _, child, _, _ = v3_fixture(monkeypatch)
    assert (
        service.get_complete_object(
            f._request(child, admissibility=Admissibility.PLAYER), object_id=f.EXISTING_OBJECT_ID
        ).reviewed_source_observations
        == ()
    )
    assert (
        service.get_complete_object(
            f._request(child, campaign_id=None), object_id=f.EXISTING_OBJECT_ID
        ).reviewed_source_observations
        == ()
    )
    sources._revisions.pop(f.SOURCE_REVISION_ID)
    result = service.get_complete_object(f._request(child), object_id=f.EXISTING_OBJECT_ID)
    assert result.reviewed_source_observations == ()
    assert "evidence_source_revision_missing" in result.coverage.gap_codes


def test_v3_reviewed_contribution_digest_tamper_is_rejected(monkeypatch):
    service, _, _, _, child, _, _ = v3_fixture(monkeypatch)
    reviews = service._contribution_reviews
    original = reviews.get

    def tampered(*args):
        state = original(*args)
        if state is None:
            return None
        changed = state.model_copy(deep=True)
        changed.reviewed_contribution.assertions[0].value = '{"summary":"tampered"}'
        return changed

    monkeypatch.setattr(reviews, "get", tampered)
    with pytest.raises(PersistenceIntegrityError):
        service.get_complete_object(f._request(child), object_id=f.EXISTING_OBJECT_ID)


@pytest.mark.parametrize("initial_version,correction_version", [(3, 3), (3, 2), (2, 3)])
def test_v3_correction_excludes_only_target_and_preserves_prior_revision(
    monkeypatch: pytest.MonkeyPatch,
    initial_version,
    correction_version,
) -> None:
    if initial_version == 3:
        service, graph, _sources, _parent_id, child_id, _spans, _values = v3_fixture(monkeypatch)
        initial_count = 6
    else:
        service, graph, _sources, _parent_id, child_id = f._fixture()
        initial_count = 1
    child = graph.get_revision(f.WORLD_ID, child_id)
    assert child is not None
    descendant = graph.publish_revision(
        f.PublishRevisionCommand(
            world_id=f.WORLD_ID,
            parent_revision_id=child_id,
            expected_parent_revision_id=child_id,
            operation_ids=["read:test:correction"],
            graph_schema=f.GRAPH_SCHEMA_V6,
            graph_payload=child.graph_payload,
            created_at=f.REVIEWED_AT + f.timedelta(minutes=2),
        )
    )
    publications = service._finalized_review_publications
    reviews = service._contribution_reviews
    assert publications is not None and reviews is not None
    prior_publication = publications.get_for_published_revision(f.WORLD_ID, child_id)
    assert prior_publication is not None
    prior_state = reviews.get(f.WORLD_ID, prior_publication.review_id)
    assert prior_state is not None
    target_id = next(
        a.assertion_id
        for a in prior_state.reviewed_contribution.assertions
        if a.assertion_kind == "attribute"
    )
    corrected_payload = prior_state.reviewed_contribution.model_dump(mode="json")
    corrected_payload["contribution_id"] = "contrib:" + "c" * 32
    corrected_payload["assertions"] = []
    corrected_payload["assertion_corrections"] = [
        {
            "target_contribution_id": prior_state.reviewed_contribution.contribution_id,
            "target_assertion_id": target_id,
            "correction_kind": "contradicts",
            "replacement_assertion_id": None,
        }
    ]
    corrected_payload["schema_version"] = f"dm_graph_contribution_v{correction_version}"
    contribution_model = GraphContributionV3 if correction_version == 3 else GraphContributionV2
    corrected_contribution = contribution_model.model_validate(corrected_payload)
    digest = (
        contribution_v3_payload_sha256
        if correction_version == 3
        else contribution_v2_payload_sha256
    )
    corrected_sha = digest(corrected_contribution)
    correction_review_id = "review:" + "c" * 32
    corrected_record = prior_state.record.model_copy(
        update={
            "review_id": correction_review_id,
            "reviewed_contribution_id": corrected_contribution.contribution_id,
            "reviewed_contribution_sha256": corrected_sha,
        }
    )
    corrected_state = prior_state.model_copy(
        update={
            "record": corrected_record,
            "reviewed_contribution": corrected_contribution,
        }
    )
    # Synthetic stored-descendant record isolates reader ancestry semantics;
    # the positive fixture above separately exercises real finalization/publication.
    state_model = (
        ContributionReviewStateV3 if correction_version == 3 else ContributionReviewStateV2
    )
    corrected_state = state_model.model_construct(**corrected_state.model_dump())
    corrected_state.record = corrected_record
    corrected_state.reviewed_contribution = corrected_contribution
    corrected_publication = prior_publication.model_copy(
        update={
            "review_id": correction_review_id,
            "reviewed_contribution_id": corrected_contribution.contribution_id,
            "reviewed_contribution_sha256": corrected_sha,
            "expected_parent_revision_id": child_id,
            "published_revision_id": descendant.revision_id,
        }
    )
    original_publication_lookup = publications.get_for_published_revision
    original_review_lookup = reviews.get
    monkeypatch.setattr(
        publications,
        "get_for_published_revision",
        lambda world_id, revision_id: (
            corrected_publication
            if revision_id == descendant.revision_id
            else original_publication_lookup(world_id, revision_id)
        ),
    )
    monkeypatch.setattr(
        reviews,
        "get",
        lambda world_id, review_id: (
            corrected_state
            if review_id == correction_review_id
            else original_review_lookup(world_id, review_id)
        ),
    )
    corrected = service.get_complete_object(
        f._request(descendant.revision_id), object_id=f.EXISTING_OBJECT_ID
    )
    assert len(corrected.reviewed_source_observations) == initial_count - 1
    assert all(row.assertion_id != target_id for row in corrected.reviewed_source_observations)
    assert "reviewed_source_observation_correction_unresolved" in corrected.coverage.gap_codes
    prior = service.get_complete_object(f._request(child_id), object_id=f.EXISTING_OBJECT_ID)
    assert len(prior.reviewed_source_observations) == initial_count
