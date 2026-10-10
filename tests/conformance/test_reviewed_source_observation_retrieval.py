"""Published V6 source observations stay separate from authored graph fields."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from dungeonmind.application.contribution_review_v2 import _build_review_state
from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V6
from dungeonmind.application.review_publication import publish_finalized_review
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import WorldGraphRetrievalService
from dungeonmind.contracts.contribution import AcceptanceState, GraphContributionV2
from dungeonmind.contracts.contribution_review import ContributionAssertionVerdict
from dungeonmind.contracts.contribution_review_v2 import contribution_v2_payload_sha256
from dungeonmind.contracts.evidence import (
    SourceArtifactV2,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2, WorldGraphProjectionRequestV2
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryContributionReviewRepository,
    InMemoryFinalizedReviewPublicationRepository,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from tests.unit.null_reviewed_world_initialization import (
    NullReviewedWorldInitializationRepository,
)
from tests.unit.test_contribution_review_v2 import (
    CAMPAIGN_ID,
    EXISTING_OBJECT_ID,
    REVIEWED_AT,
    WORLD_ID,
    _candidate,
    _intent,
    _reader,
    _stored_parent,
    _submission,
    _v6_parent_payload,
)

SOURCE_ARTIFACT_ID = "artifact:recap:longmont-c2:session-2"
SOURCE_REVISION_ID = "source-revision:observation-v1"
ASSERTION_ID = "assertion:test:attribute:existing"
OBSERVATION_TEXT = "The keeper saw a blue lantern by the gate."


def _source(
    sources: InMemorySourceRepository,
    *,
    artifact_id: str,
    revision_id: str | None,
    visibility: Visibility = Visibility.PLAYER,
) -> None:
    sources.put_artifact(
        SourceArtifactV2(
            source_artifact_id=artifact_id,
            source_domain_key="session_recap",
            source_domain=SourceDomain.SESSION_RECAP,
            world_id=WORLD_ID,
            campaign_id=CAMPAIGN_ID,
            session_id="session-2",
            uri=None,
            current_revision_id=revision_id,
            authority=None,
            visibility=visibility,
            artifact_kind=None,
            document_class=None,
            review_state=None,
            source_visibility_state=None,
            workspace_document_ref=None,
            lineage={},
            status=SourceStatus.ACTIVE,
            created_at=REVIEWED_AT,
            updated_at=REVIEWED_AT,
        )
    )
    if revision_id is not None:
        sources.put_revision(
            SourceRevision(
                source_revision_id=revision_id,
                source_artifact_id=artifact_id,
                content_sha256="ab" * 32,
                body_storage="external",
                locator="test://reviewed-observation",
                created_at=REVIEWED_AT,
            )
        )


def _candidate_with_observation(
    *,
    subject_id: str = EXISTING_OBJECT_ID,
    text: object = OBSERVATION_TEXT,
    accepted: bool = True,
    count: int = 1,
) -> tuple[GraphContributionV2, list[ContributionAssertionVerdict]]:
    raw = _candidate().model_dump(mode="json")
    raw["source_revision_id"] = SOURCE_REVISION_ID
    template = next(row for row in raw["assertions"] if row["assertion_id"] == ASSERTION_ID)
    raw["assertions"] = [row for row in raw["assertions"] if row is not template]
    for index in range(count):
        assertion = dict(template)
        assertion["assertion_id"] = ASSERTION_ID if count == 1 else f"{ASSERTION_ID}:{index:02d}"
        assertion["subject_object_id"] = subject_id
        assertion["value"] = json.dumps(
            {"property_term": "session_observation", "summary": text, "kind": "npc"}
        )
        assertion["source_artifact_id"] = SOURCE_ARTIFACT_ID
        assertion["source_revision_id"] = SOURCE_REVISION_ID
        assertion["evidence_refs"] = [
            {**template["evidence_refs"][0], "source_revision_id": SOURCE_REVISION_ID}
        ]
        raw["assertions"].append(assertion)
    candidate = GraphContributionV2.model_validate(raw)
    verdicts = [
        ContributionAssertionVerdict(
            assertion_id=row.assertion_id,
            acceptance_state=(
                AcceptanceState.REJECTED
                if not accepted and row.assertion_kind == "attribute"
                else AcceptanceState.ACCEPTED
            ),
        )
        for row in sorted(candidate.assertions, key=lambda item: item.assertion_id)
    ]
    return candidate, verdicts


def _fixture(
    *,
    subject_id: str = EXISTING_OBJECT_ID,
    text: object = OBSERVATION_TEXT,
    accepted: bool = True,
    count: int = 1,
    publish: bool = True,
) -> tuple[
    WorldGraphRetrievalService,
    InMemoryWorldGraphRepository,
    InMemorySourceRepository,
    str,
    str,
]:
    payload = _v6_parent_payload()
    for obj in payload["objects"]:
        obj["assertion_metadata"]["visibility"] = "player"
        for alias in obj["aliases"]:
            alias["assertion_metadata"]["visibility"] = "player"
    parent = _stored_parent(payload)
    graph = InMemoryWorldGraphRepository()
    root = graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["adoption:test"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=parent.graph_payload,
            created_at=REVIEWED_AT,
        )
    )
    assert root.revision_id == parent.revision.revision_id
    sources = InMemorySourceRepository()
    _source(
        sources,
        artifact_id="artifact:recap:longmont-c2:session-1",
        revision_id=None,
    )
    _source(
        sources,
        artifact_id=SOURCE_ARTIFACT_ID,
        revision_id=SOURCE_REVISION_ID,
    )
    reviews = InMemoryContributionReviewRepository(InMemoryContributionRepository())
    publications = InMemoryFinalizedReviewPublicationRepository(reviews, graph)
    candidate, verdicts = _candidate_with_observation(
        subject_id=subject_id, text=text, accepted=accepted, count=count
    )
    intent = _intent(candidate=candidate, parent=parent, assertion_verdicts=verdicts)
    state = _build_review_state(_submission(intent))
    reviews.finalize(state)
    projection = WorldGraphProjectionService(
        world_graph=graph,
        sources=sources,
        graph_reader=_reader(),
        reviewed_world_initializations=NullReviewedWorldInitializationRepository(),
    )
    service = WorldGraphRetrievalService(
        projection=projection,
        sources=sources,
        world_graph=graph,
        contribution_reviews=reviews,
        finalized_review_publications=publications,
    )
    if not publish:
        return service, graph, sources, root.revision_id, root.revision_id
    publication = publish_finalized_review(
        WORLD_ID,
        state.record.review_id,
        published_at=REVIEWED_AT + timedelta(minutes=1),
        review_repository=reviews,
        world_graph_repository=graph,
        publication_repository=publications,
        graph_reader=_reader(),
    )
    return service, graph, sources, root.revision_id, publication.published_revision_id


def _request(
    revision_id: str,
    *,
    campaign_id: str | None = CAMPAIGN_ID,
    admissibility: Admissibility = Admissibility.GM,
) -> WorldGraphProjectionRequestV2:
    return WorldGraphProjectionRequestV2(
        world_id=WORLD_ID,
        campaign_id=campaign_id,
        scope_mode=(
            ScopeModeV2.CAMPAIGN if campaign_id is not None else ScopeModeV2.WORLD
        ),
        admissibility=admissibility,
        revision_pin=revision_id,
    )


def test_published_observation_is_typed_and_separate_from_authored_graph() -> None:
    service, graph, _sources, parent_id, child_id = _fixture()
    before = graph.get_revision(WORLD_ID, child_id)
    assert before is not None
    result = service.get_complete_object(_request(child_id), object_id=EXISTING_OBJECT_ID)
    assert result.found
    assert len(result.reviewed_source_observations) == 1
    observation = result.reviewed_source_observations[0]
    assert observation.assertion_id == ASSERTION_ID
    assert observation.text == OBSERVATION_TEXT
    assert observation.observation_kind == "session_observation"
    assert observation.entity_kind == "npc"
    assert observation.publication_revision_id == child_id
    assert observation.source_artifact_id == SOURCE_ARTIFACT_ID
    assert observation.source_revision_id == SOURCE_REVISION_ID
    assert observation.review_id.startswith("review:")
    assert observation.contribution_id.startswith("contrib:")
    assert observation.evidence_ref_ids == ("evidence:new:attribute",)
    anchors = [
        anchor for anchor in result.anchors
        if ASSERTION_ID in anchor.supporting_assertion_ids
    ]
    assert len(anchors) == 1
    assert anchors[0].source_revision_id == SOURCE_REVISION_ID
    assert service.resolve_source_anchor(
        _request(child_id), anchor_id=anchors[0].anchor_id
    ).found
    assert all(row.assertion_id != ASSERTION_ID for row in result.property_assertions)
    after = graph.get_revision(WORLD_ID, child_id)
    assert after is not None
    assert canonical_sha256(after.graph_payload) == canonical_sha256(before.graph_payload)
    assert after.graph_payload == before.graph_payload
    old = service.get_complete_object(_request(parent_id), object_id=EXISTING_OBJECT_ID)
    assert old.reviewed_source_observations == ()


def test_finalized_but_unpublished_review_is_not_a_read_authority() -> None:
    service, _graph, _sources, _parent, pin = _fixture(publish=False)
    result = service.get_complete_object(_request(pin), object_id=EXISTING_OBJECT_ID)
    assert result.found
    assert result.reviewed_source_observations == ()


def test_published_observation_survives_descendant_without_leaking_to_parent() -> None:
    service, graph, _sources, parent_id, child_id = _fixture()
    child = graph.get_revision(WORLD_ID, child_id)
    assert child is not None
    descendant = graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=child_id,
            expected_parent_revision_id=child_id,
            operation_ids=["read:test:descendant"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=child.graph_payload,
            created_at=REVIEWED_AT + timedelta(minutes=2),
        )
    )
    later = service.get_complete_object(
        _request(descendant.revision_id), object_id=EXISTING_OBJECT_ID
    )
    earlier = service.get_complete_object(_request(parent_id), object_id=EXISTING_OBJECT_ID)
    assert len(later.reviewed_source_observations) == 1
    assert later.reviewed_source_observations[0].publication_revision_id == child_id
    assert earlier.reviewed_source_observations == ()


def test_later_published_correction_marks_observation_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, graph, _sources, _parent_id, child_id = _fixture()
    child = graph.get_revision(WORLD_ID, child_id)
    assert child is not None
    descendant = graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=child_id,
            expected_parent_revision_id=child_id,
            operation_ids=["read:test:correction"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=child.graph_payload,
            created_at=REVIEWED_AT + timedelta(minutes=2),
        )
    )
    publications = service._finalized_review_publications
    reviews = service._contribution_reviews
    assert publications is not None and reviews is not None
    prior_publication = publications.get_for_published_revision(WORLD_ID, child_id)
    assert prior_publication is not None
    prior_state = reviews.get(WORLD_ID, prior_publication.review_id)
    assert prior_state is not None
    corrected_payload = prior_state.reviewed_contribution.model_dump(mode="json")
    corrected_payload["contribution_id"] = "contrib:" + "c" * 32
    corrected_payload["assertions"] = []
    corrected_payload["assertion_corrections"] = [{
        "target_contribution_id": prior_state.reviewed_contribution.contribution_id,
        "target_assertion_id": ASSERTION_ID,
        "correction_kind": "contradicts",
        "replacement_assertion_id": None,
    }]
    corrected_contribution = GraphContributionV2.model_validate(corrected_payload)
    corrected_sha = contribution_v2_payload_sha256(corrected_contribution)
    correction_review_id = "review:" + "c" * 32
    corrected_record = prior_state.record.model_copy(update={
        "review_id": correction_review_id,
        "reviewed_contribution_id": corrected_contribution.contribution_id,
        "reviewed_contribution_sha256": corrected_sha,
    })
    corrected_state = prior_state.model_copy(update={
        "record": corrected_record,
        "reviewed_contribution": corrected_contribution,
    })
    corrected_publication = prior_publication.model_copy(update={
        "review_id": correction_review_id,
        "reviewed_contribution_id": corrected_contribution.contribution_id,
        "reviewed_contribution_sha256": corrected_sha,
        "expected_parent_revision_id": child_id,
        "published_revision_id": descendant.revision_id,
    })
    original_publication_lookup = publications.get_for_published_revision
    original_review_lookup = reviews.get
    monkeypatch.setattr(
        publications,
        "get_for_published_revision",
        lambda world_id, revision_id: (
            corrected_publication if revision_id == descendant.revision_id
            else original_publication_lookup(world_id, revision_id)
        ),
    )
    monkeypatch.setattr(
        reviews,
        "get",
        lambda world_id, review_id: (
            corrected_state if review_id == correction_review_id
            else original_review_lookup(world_id, review_id)
        ),
    )
    corrected = service.get_complete_object(
        _request(descendant.revision_id), object_id=EXISTING_OBJECT_ID
    )
    assert corrected.reviewed_source_observations == ()
    assert "reviewed_source_observation_correction_unresolved" in corrected.coverage.gap_codes
    prior = service.get_complete_object(_request(child_id), object_id=EXISTING_OBJECT_ID)
    assert len(prior.reviewed_source_observations) == 1


def test_observation_filters_and_coverage_are_independent_of_object() -> None:
    service, _graph, sources, _parent_id, child_id = _fixture()
    assert service.get_complete_object(
        _request(child_id, admissibility=Admissibility.PLAYER),
        object_id=EXISTING_OBJECT_ID,
    ).reviewed_source_observations == ()
    assert not service.get_complete_object(
        _request(child_id, campaign_id=None), object_id=EXISTING_OBJECT_ID
    ).reviewed_source_observations
    sources._revisions.pop(SOURCE_REVISION_ID)
    broken = service.get_complete_object(_request(child_id), object_id=EXISTING_OBJECT_ID)
    assert broken.found
    assert broken.reviewed_source_observations == ()
    assert "evidence_source_revision_missing" in broken.coverage.gap_codes


def test_rejected_and_wrong_subject_observations_do_not_appear() -> None:
    rejected, _graph, _sources, _parent, child = _fixture(accepted=False)
    assert rejected.get_complete_object(
        _request(child), object_id=EXISTING_OBJECT_ID
    ).reviewed_source_observations == ()
    other, _graph, _sources, _parent, child = _fixture(subject_id="npc:other")
    result = other.get_complete_object(_request(child), object_id=EXISTING_OBJECT_ID)
    assert result.reviewed_source_observations == ()


def test_unsupported_observation_has_coverage_without_false_value() -> None:
    service, _graph, _sources, _parent, child = _fixture(text={"not": "text"})
    result = service.get_complete_object(_request(child), object_id=EXISTING_OBJECT_ID)
    assert result.reviewed_source_observations == ()
    assert "reviewed_source_observation_unsupported_shape" in result.coverage.gap_codes


def test_complete_object_observations_are_not_bounded_by_retrieval_caps() -> None:
    service, _graph, _sources, _parent, child = _fixture(count=33)
    result = service.get_complete_object(_request(child), object_id=EXISTING_OBJECT_ID)
    assert len(result.reviewed_source_observations) == 33
    assert result.completeness.status == "complete"
    assert not result.coverage.truncated_fields
