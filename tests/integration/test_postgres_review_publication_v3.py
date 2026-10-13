"""Disposable PostgreSQL proof of V3 typed evidence through governed child publication."""

from __future__ import annotations

import pytest

from dungeonmind.application.contribution_review_v3 import finalize_contribution_review_v3
from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.application.review_publication import publish_finalized_review
from dungeonmind.contracts import (
    Admissibility,
    CapabilityCategory,
    CapabilityEffect,
    CapabilityPolicy,
    GraphScope,
    ToolCapabilityRule,
)
from dungeonmind.contracts.contribution import GraphContributionV3
from dungeonmind.contracts.contribution_review import derive_confirmation_id
from dungeonmind.contracts.contribution_review_v3 import (
    FINALIZE_REVIEW_V3_TOOL,
    CommitConfirmationReceiptV3,
    ContributionReviewIntentV3,
    ContributionReviewSubmissionV3,
    contribution_v3_payload_sha256,
    derive_review_intent_sha256_v3,
)
from dungeonmind.contracts.evidence import SourceArtifactV2, SourceDomain, SourceRevision
from dungeonmind.domain.errors import IdempotencyConflictError, StaleParentRevisionError
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryContributionReviewRepository,
    InMemoryExistingWorldAdoptionRepository,
    InMemoryFinalizedReviewPublicationRepository,
    InMemoryIdentityDecisionRepository,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from dungeonmind.infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle
from tests.integration.test_postgres_review_publication_v6 import (
    CAMPAIGN_ID,
    NEW_EVIDENCE_ARTIFACT,
    PUBLISHED_AT,
    PUBLISHED_REVISION_ID,
    REVIEWED_AT,
    WORLD_ID,
    _adopt,
    _candidate,
    _intent,
    _table_counts,
    eldyrwild_graph_reader,
)
from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import NOW, raw_bundle

pytestmark = pytest.mark.integration
SOURCE_REVISION = "revision:typed-review-v3"
SPAN = "paragraph:099"


def _typed_candidate(*, span: str = SPAN) -> GraphContributionV3:
    payload = _candidate().model_dump(mode="json")
    payload["schema_version"] = "dm_graph_contribution_v3"
    payload["source_revision_id"] = SOURCE_REVISION
    for assertion in payload["assertions"]:
        assertion["source_artifact_id"] = NEW_EVIDENCE_ARTIFACT
        assertion["source_revision_id"] = SOURCE_REVISION
        for ref in assertion["evidence_refs"]:
            ref.update(
                schema_version="dm_evidence_ref_v2",
                source_revision_id=SOURCE_REVISION,
                source_domain_key="session_recap",
                session_id="session-99",
                source_span_ref_id=span,
                uri="repo://recap/session-99",
                source_locator=None,
                line_ref=None,
            )
    return GraphContributionV3.model_validate(payload)


def _typed_intent(parent, *, candidate=None, source_plan_id="plan:typed-v3", operation_id=None):
    candidate = candidate or _typed_candidate()
    old = _intent(parent)
    plan = old.plan_ref.model_copy(
        update={
            "source_plan_id": source_plan_id,
            "candidate_contribution_sha256": contribution_v3_payload_sha256(candidate),
        }
    )
    fields = dict(
        operation_id=operation_id or old.operation_id,
        world_id=old.world_id,
        campaign_id=old.campaign_id,
        plan_ref=plan,
        candidate_contribution=candidate,
        identity_proposals=old.identity_proposals,
        identity_verdicts=old.identity_verdicts,
        assertion_verdicts=old.assertion_verdicts,
        reviewer_id=old.reviewer_id,
        reviewed_at=old.reviewed_at,
    )
    return ContributionReviewIntentV3(
        **fields, review_intent_sha256=derive_review_intent_sha256_v3(**fields)
    )


def _submission(intent):
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


def _policy(intent):
    return CapabilityPolicy(
        policy_id="pol:typed-v3",
        graph_scope=GraphScope(
            world_id=intent.world_id,
            campaign_id=intent.campaign_id,
            admissibility=Admissibility.GM,
            revision_pin=intent.plan_ref.expected_parent_revision_id,
        ),
        enabled_tools=[FINALIZE_REVIEW_V3_TOOL],
        tool_rules=[
            ToolCapabilityRule(
                tool_name=FINALIZE_REVIEW_V3_TOOL,
                category=CapabilityCategory.CONFIRM_COMMIT,
                allowed_effects=[CapabilityEffect.COMMIT],
            )
        ],
    )


def _finalize(pg, intent):
    return finalize_contribution_review_v3(
        _submission(intent),
        capability_policy=_policy(intent),
        world_graph_repository=pg.world_graph,
        review_repository=pg.contribution_reviews,
    )


def _publish(pg, review_id):
    return publish_finalized_review(
        WORLD_ID,
        review_id,
        published_at=PUBLISHED_AT,
        review_repository=pg.contribution_reviews,
        world_graph_repository=pg.world_graph,
        publication_repository=pg.finalized_review_publications,
        graph_reader=eldyrwild_graph_reader(),
    )


def _seed(pg):
    _adopt(pg)
    pg.sources.put_revision(
        SourceRevision(
            source_revision_id=SOURCE_REVISION,
            source_artifact_id=NEW_EVIDENCE_ARTIFACT,
            content_sha256="a" * 64,
            body_storage="object_store",
            locator="repo://recap/session-99",
            created_at=REVIEWED_AT,
        )
    )
    parent = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert parent is not None
    return parent


def test_disposable_memory_v3_governed_child_before_postgres():
    graph = InMemoryWorldGraphRepository()
    contributions = InMemoryContributionRepository()
    reviews = InMemoryContributionReviewRepository(contributions)
    sources = InMemorySourceRepository()
    identities = InMemoryIdentityDecisionRepository()
    publications = InMemoryFinalizedReviewPublicationRepository(
        reviews,
        graph,
        source_repository=sources,
    )
    adoptions = InMemoryExistingWorldAdoptionRepository(
        graph,
        sources,
        contributions,
        identities,
    )
    adopt_existing_world(
        raw_bundle(),
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=eldyrwild_graph_reader(),
    )
    sources.put_artifact(
        SourceArtifactV2(
            source_artifact_id=NEW_EVIDENCE_ARTIFACT,
            source_domain_key="session_recap",
            source_domain=SourceDomain.SESSION_RECAP,
            world_id=WORLD_ID,
            campaign_id=CAMPAIGN_ID,
            session_id="session-99",
            uri="repo://recap/session-99",
            current_revision_id=SOURCE_REVISION,
            authority="primary",
            visibility="gm",
            artifact_kind=None,
            document_class=None,
            review_state=None,
            source_visibility_state=None,
            workspace_document_ref=None,
            status="active",
            created_at=REVIEWED_AT,
            updated_at=REVIEWED_AT,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id=SOURCE_REVISION,
            source_artifact_id=NEW_EVIDENCE_ARTIFACT,
            content_sha256="a" * 64,
            body_storage="object_store",
            locator="repo://recap/session-99",
            created_at=REVIEWED_AT,
        )
    )
    parent = graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert parent is not None
    intent = _typed_intent(parent)
    state = finalize_contribution_review_v3(
        _submission(intent),
        capability_policy=_policy(intent),
        world_graph_repository=graph,
        review_repository=reviews,
    )
    receipt = publish_finalized_review(
        WORLD_ID,
        state.record.review_id,
        published_at=PUBLISHED_AT,
        review_repository=reviews,
        world_graph_repository=graph,
        publication_repository=publications,
        graph_reader=eldyrwild_graph_reader(),
    )
    child = graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert child is not None
    evidence_id = intent.candidate_contribution.assertions[0].evidence_refs[0].evidence_ref_id
    record = next(
        row for row in child.graph_payload["evidence_refs"] if row["evidence_ref_id"] == evidence_id
    )
    assert record["source_span_ref_id"] == SPAN


def test_postgres_v3_persisted_reopened_child_typed_span_and_replay(pg, migrated_database):
    parent = _seed(pg)
    intent = _typed_intent(parent)
    state = _finalize(pg, intent)
    assert _finalize(pg, intent) == state
    fresh = PostgresRepositoryBundle(PostgresDatabase(migrated_database))
    reopened = fresh.contribution_reviews.get(WORLD_ID, state.record.review_id)
    assert reopened is not None
    assert reopened.reviewed_contribution.assertions[0].evidence_refs[0].source_span_ref_id == SPAN
    receipt = _publish(pg, state.record.review_id)
    child = fresh.world_graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert child is not None
    evidence_id = intent.candidate_contribution.assertions[0].evidence_refs[0].evidence_ref_id
    with pg.database.connect() as conn:
        extracted = conn.execute(
            "SELECT schema_version, payload FROM dungeonmind.evidence_refs "
            "WHERE evidence_ref_id = %s",
            (evidence_id,),
        ).fetchone()
    assert extracted["schema_version"] == "dm_evidence_ref_v2"
    assert extracted["payload"]["source_span_ref_id"] == SPAN
    record = next(
        row for row in child.graph_payload["evidence_refs"] if row["evidence_ref_id"] == evidence_id
    )
    assert record["source_span_ref_id"] == SPAN
    assert record["source_revision_id"] == SOURCE_REVISION
    assert record["locator"] == SPAN
    assert record["uri"] == "repo://recap/session-99"
    before = _table_counts(pg)
    assert _publish(pg, state.record.review_id) == receipt
    assert _table_counts(pg) == before


def test_postgres_v3_conflicting_operation_and_stale_parent_leave_zero_mutation(pg):
    parent = _seed(pg)
    state = _finalize(pg, _typed_intent(parent))
    before = _table_counts(pg)
    conflicting = _typed_intent(
        parent,
        candidate=_typed_candidate(span="paragraph:other"),
        source_plan_id="plan:typed-v3-conflict",
    )
    with pytest.raises(IdempotencyConflictError):
        _finalize(pg, conflicting)
    assert _table_counts(pg) == before
    _publish(pg, state.record.review_id)
    after_publish = _table_counts(pg)
    with pytest.raises(StaleParentRevisionError):
        _finalize(pg, conflicting)
    assert _table_counts(pg) == after_publish


def test_postgres_v3_same_evidence_id_different_span_rolls_back_review_bundle(pg):
    parent = _seed(pg)
    _finalize(pg, _typed_intent(parent))
    before = _table_counts(pg)
    candidate = _typed_candidate(span="paragraph:other").model_copy(
        update={"contribution_id": "contrib:" + "d" * 32}
    )
    conflicting = _typed_intent(
        parent,
        candidate=candidate,
        source_plan_id="plan:typed-v3-second",
        operation_id="reviewop:" + "d" * 32,
    )
    with pytest.raises(IdempotencyConflictError):
        _finalize(pg, conflicting)
    assert _table_counts(pg) == before


def test_postgres_v3_wrong_registered_source_scope_blocks_publication(pg):
    parent = _seed(pg)
    wrong_artifact_id = "artifact:recap:wrong-campaign:v3"
    wrong_revision_id = "revision:wrong-campaign:v3"
    base_artifact = pg.sources.get_artifact(NEW_EVIDENCE_ARTIFACT)
    assert base_artifact is not None
    pg.sources.put_artifact(
        base_artifact.model_copy(
            update={
                "source_artifact_id": wrong_artifact_id,
                "campaign_id": "wrong-campaign",
                "current_revision_id": wrong_revision_id,
            }
        )
    )
    pg.sources.put_revision(
        SourceRevision(
            source_revision_id=wrong_revision_id,
            source_artifact_id=wrong_artifact_id,
            content_sha256="b" * 64,
            body_storage="object_store",
            locator="repo://recap/wrong-campaign",
            created_at=REVIEWED_AT,
        )
    )
    payload = _typed_candidate().model_dump(mode="json")
    payload["source_artifact_id"] = wrong_artifact_id
    payload["source_revision_id"] = wrong_revision_id
    for assertion in payload["assertions"]:
        assertion["source_artifact_id"] = wrong_artifact_id
        assertion["source_revision_id"] = wrong_revision_id
        for ref in assertion["evidence_refs"]:
            ref["source_artifact_id"] = wrong_artifact_id
            ref["source_revision_id"] = wrong_revision_id
    candidate = GraphContributionV3.model_validate(payload)
    state = _finalize(pg, _typed_intent(parent, candidate=candidate))
    before = _table_counts(pg)
    from dungeonmind.domain.errors import ContributionMaterializationError

    with pytest.raises(ContributionMaterializationError):
        _publish(pg, state.record.review_id)
    assert _table_counts(pg) == before
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID
