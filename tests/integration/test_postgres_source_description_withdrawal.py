"""Correction-only reviews persist through the real PostgreSQL publication seam."""

from __future__ import annotations

import json

import pytest

from dungeonmind.application.contribution_review_v3 import finalize_contribution_review_v3
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import WorldGraphRetrievalService
from dungeonmind.contracts.contribution import GraphContributionV3
from dungeonmind.contracts.contribution_review_v3 import (
    ContributionReviewIntentV3,
    contribution_v3_payload_sha256,
    derive_review_intent_sha256_v3,
)
from dungeonmind.contracts.evidence import SourceDomain
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2, WorldGraphProjectionRequestV2
from dungeonmind.infrastructure.postgres import PostgresRepositoryBundle
from tests.conformance import test_reviewed_source_observation_retrieval as sources_fixture
from tests.integration import test_postgres_review_publication_v3 as f
from tests.integration.test_postgres_review_publication_v6 import NEW_OBJECT_ID

pytestmark = pytest.mark.integration
ARTIFACT = "artifact:worldbuilding:description-withdrawal"
REVISION = "source-revision:worldbuilding:description-withdrawal"
TARGET = "assertion:cutover:node:new"


def test_postgres_withdrawal_fresh_read_and_exact_replay(pg):
    parent = f._seed(pg)
    sources_fixture._source(
        pg.sources,
        artifact_id=ARTIFACT,
        revision_id=REVISION,
        source_domain=SourceDomain.WORLDBUILDING,
    )
    raw = f._typed_candidate().model_dump(mode="json")
    raw.update(source_kind="extraction", source_artifact_id=ARTIFACT, source_revision_id=REVISION)
    for assertion in raw["assertions"]:
        assertion.update(source_artifact_id=ARTIFACT, source_revision_id=REVISION)
        if assertion["assertion_id"] == TARGET:
            value = json.loads(assertion["value"])
            value["summary"] = "Some citizens believe this representative protects the festival."
            assertion["value"] = json.dumps(value)
        for ref in assertion["evidence_refs"]:
            ref.update(
                source_artifact_id=ARTIFACT,
                source_revision_id=REVISION,
                source_domain="worldbuilding",
                source_domain_key="worldbuilding",
                session_id=None,
            )
    target = f._finalize(
        pg, f._typed_intent(parent, candidate=GraphContributionV3.model_validate(raw))
    )
    first = f._publish(pg, target.record.review_id)
    before = pg.world_graph.get_revision(f.WORLD_ID, first.published_revision_id)
    candidate = GraphContributionV3(
        contribution_id="contrib:postgres-description-withdrawal",
        world_id=f.WORLD_ID,
        source_kind="graph_review",
        source_artifact_id=ARTIFACT,
        source_revision_id=REVISION,
        produced_at=f.REVIEWED_AT,
        campaign_scope=f.CAMPAIGN_ID,
        diagnostics={
            "source_description_withdrawal_reason": "Review withdraws the extracted interpretation."
        },
        assertion_corrections=[
            {
                "correction_kind": "contradicts_source_description",
                "target_contribution_id": target.reviewed_contribution.contribution_id,
                "target_assertion_id": TARGET,
            }
        ],
    )
    fields = dict(
        operation_id="reviewop:" + "d" * 32,
        world_id=f.WORLD_ID,
        campaign_id=f.CAMPAIGN_ID,
        plan_ref=target.record.plan_ref.model_copy(
            update={
                "source_plan_id": "plan:postgres-description-withdrawal",
                "candidate_contribution_sha256": contribution_v3_payload_sha256(candidate),
                "expected_parent_revision_id": before.revision.revision_id,
                "base_graph_payload_sha256": before.revision.graph_payload_sha256,
            }
        ),
        candidate_contribution=candidate,
        identity_proposals=[],
        identity_verdicts=[],
        assertion_verdicts=[],
        reviewer_id=target.record.reviewer_id,
        reviewed_at=f.REVIEWED_AT,
    )
    intent = ContributionReviewIntentV3(
        **fields, review_intent_sha256=derive_review_intent_sha256_v3(**fields)
    )
    state = finalize_contribution_review_v3(
        f._submission(intent),
        capability_policy=f._policy(intent),
        world_graph_repository=pg.world_graph,
        review_repository=pg.contribution_reviews,
    )
    receipt = f._publish(pg, state.record.review_id)
    fresh = PostgresRepositoryBundle(pg.database)
    stored_state = fresh.contribution_reviews.get(f.WORLD_ID, state.record.review_id)
    assert stored_state == state
    current = fresh.world_graph.get_revision(f.WORLD_ID, receipt.published_revision_id)
    assert current.graph_payload == before.graph_payload
    projection = WorldGraphProjectionService(
        world_graph=fresh.world_graph,
        sources=fresh.sources,
        graph_reader=f.eldyrwild_graph_reader(),
        reviewed_world_initializations=fresh.reviewed_world_initializations,
    )
    service = WorldGraphRetrievalService(
        projection=projection,
        sources=fresh.sources,
        world_graph=fresh.world_graph,
        contribution_reviews=fresh.contribution_reviews,
        finalized_review_publications=fresh.finalized_review_publications,
    )

    def request(revision):
        return WorldGraphProjectionRequestV2(
            world_id=f.WORLD_ID,
            campaign_id=f.CAMPAIGN_ID,
            scope_mode=ScopeModeV2.CAMPAIGN,
            admissibility=Admissibility.GM,
            revision_pin=revision,
        )

    old = service.get_complete_object(request(first.published_revision_id), object_id=NEW_OBJECT_ID)
    assert any(o.assertion_id == TARGET for o in old.reviewed_source_observations)
    now = service.get_complete_object(
        request(receipt.published_revision_id), object_id=NEW_OBJECT_ID
    )
    assert now.found and all(o.assertion_id != TARGET for o in now.reviewed_source_observations)
    assert f._publish(fresh, state.record.review_id) == receipt
