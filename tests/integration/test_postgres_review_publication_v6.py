"""PostgreSQL owning-boundary proof for v6 governed review publication.

ADR-0020: the sealed Eldyrwild adoption (head D_A, V3 receipt) accepts a
GM-confirmed v2 contribution review and publishes a real child revision D_B
through the existing finalized-review publication boundary, with replay and
CAS-loser proofs at the same boundary.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from dungeonmind.application import FinalizedReviewPublication, publish_finalized_review
from dungeonmind.application.contribution_review_v2 import finalize_contribution_review_v2
from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V6
from dungeonmind.contracts import (
    Admissibility,
    CapabilityCategory,
    CapabilityEffect,
    CapabilityPolicy,
    GraphScope,
    ToolCapabilityRule,
)
from dungeonmind.contracts.contribution import (
    AcceptanceState,
    ContributionSourceKind,
    GraphContributionAssertionV2,
    GraphContributionV2,
)
from dungeonmind.contracts.contribution_review import (
    ContributionAssertionVerdict,
    ContributionIdentityProposal,
    ContributionIdentityVerdict,
    ContributionIdentityVerdictKind,
    ContributionPlanRef,
    derive_confirmation_id,
)
from dungeonmind.contracts.contribution_review_v2 import (
    FINALIZE_REVIEW_V2_TOOL,
    CommitConfirmationReceiptV2,
    ContributionReviewIntentV2,
    ContributionReviewStateV2,
    ContributionReviewSubmissionV2,
    contribution_v2_payload_sha256,
    derive_review_intent_sha256_v2,
)
from dungeonmind.contracts.evidence import EvidenceRef, EvidenceRole, SourceDomain
from dungeonmind.contracts.graph import StoredGraphRevision
from dungeonmind.contracts.identity import IdentityOutcome
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    ContributionMaterializationError,
    StaleParentRevisionError,
)
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryContributionReviewRepository,
    InMemoryExistingWorldAdoptionRepository,
    InMemoryFinalizedReviewPublicationRepository,
    InMemoryIdentityDecisionRepository,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
    NOW,
    PROFILE_V3_DIGEST,
    PUBLISHED_REVISION_ID,
    WORLD_ID,
    eldyrwild_graph_reader,
    raw_bundle,
)

if TYPE_CHECKING:
    from dungeonmind.infrastructure.postgres import PostgresRepositoryBundle

pytestmark = pytest.mark.integration

CAMPAIGN_ID = "longmont-c2"
REVIEWER_ID = "gm:cutover-proof"
REVIEWED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
PUBLISHED_AT = datetime(2026, 8, 18, 13, 0, tzinfo=UTC)
PROFILE = SemanticProfileRef(
    profile_id="dungeonmind.dnd5e",
    profile_revision="dnd5e-profile-v3",
    descriptor_sha256=PROFILE_V3_DIGEST,
)

ADOPTED_OBJECT_ID = "node:barin_coppergleam"
NEW_OBJECT_ID = "node:cutover_integration_npc"
EDGE_ID = "edge:cutover:integration:aware"
NEW_EVIDENCE_ARTIFACT = "artifact:recap:longmont-c2:session-99"


def _adopt(pg) -> None:
    receipt = adopt_existing_world(
        raw_bundle(),
        adopted_at=NOW,
        adoption_repository=pg.existing_world_adoptions,
        graph_reader=eldyrwild_graph_reader(),
    )
    assert receipt.published_revision_id == PUBLISHED_REVISION_ID


def _evidence(evidence_ref_id: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_ref_id=evidence_ref_id,
        source_artifact_id=NEW_EVIDENCE_ARTIFACT,
        source_domain=SourceDomain.SESSION_RECAP,
        evidence_role=EvidenceRole.SUPPORT,
        can_open_source=True,
        can_highlight_span=True,
        locator="paragraph:099",
    )


def _candidate(
    *,
    contribution_id: str = "contrib:" + "c" * 32,
    new_object_id: str = NEW_OBJECT_ID,
    edge_id: str = EDGE_ID,
    alias_label: str = "Barin the Cutover Witness",
    node_value: str | None = None,
) -> GraphContributionV2:
    return GraphContributionV2(
        contribution_id=contribution_id,
        world_id=WORLD_ID,
        source_kind=ContributionSourceKind.GRAPH_REVIEW,
        produced_at=REVIEWED_AT,
        authored_by="buddy:cutover-proof",
        campaign_scope=CAMPAIGN_ID,
        source_artifact_id=NEW_EVIDENCE_ARTIFACT,
        assertions=[
            GraphContributionAssertionV2(
                assertion_id="assertion:cutover:node:new",
                assertion_kind="node",
                subject_object_id=new_object_id,
                label="Cutover Integration NPC",
                value=(
                    node_value
                    if node_value is not None
                    else (
                        '{"dm_kind": "dnd5e:npc", "kind": "npc",'
                        ' "aliases": ["Cutover Integration NPC"]}'
                    )
                ),
                evidence_refs=[_evidence("evidence:cutover:node")],
                campaign_scope=CAMPAIGN_ID,
            ),
            GraphContributionAssertionV2(
                assertion_id="assertion:cutover:alias:adopted",
                assertion_kind="alias",
                subject_object_id=ADOPTED_OBJECT_ID,
                label=alias_label,
                evidence_refs=[_evidence("evidence:cutover:alias")],
                campaign_scope=CAMPAIGN_ID,
            ),
            GraphContributionAssertionV2(
                assertion_id="assertion:cutover:edge:new",
                assertion_kind="edge",
                subject_object_id=new_object_id,
                object_object_id=ADOPTED_OBJECT_ID,
                predicate="aware_of",
                value=('{"dm_predicate": "dnd5e:aware_of", "edge_id": "' + edge_id + '"}'),
                evidence_refs=[_evidence("evidence:cutover:edge")],
                campaign_scope=CAMPAIGN_ID,
            ),
            GraphContributionAssertionV2(
                assertion_id="assertion:cutover:attribute:adopted",
                assertion_kind="attribute",
                subject_object_id=ADOPTED_OBJECT_ID,
                value='{"attribute": "disposition", "detail": "alert"}',
                evidence_refs=[_evidence("evidence:cutover:attribute")],
                campaign_scope=CAMPAIGN_ID,
            ),
        ],
    )


def _intent(
    parent: StoredGraphRevision,
    *,
    candidate: GraphContributionV2 | None = None,
    operation_id: str = "reviewop:" + "c" * 32,
    source_plan_id: str = "plan:cutover-proof",
) -> ContributionReviewIntentV2:
    candidate = candidate or _candidate()
    new_object_id = candidate.assertions[0].subject_object_id
    plan_ref = ContributionPlanRef(
        source_plan_schema="dmb_extract_promote_review_package_v1",
        source_plan_id=source_plan_id,
        source_plan_sha256="1" * 64,
        source_input_sha256="2" * 64,
        preview_content_sha256="3" * 64,
        candidate_contribution_sha256=contribution_v2_payload_sha256(candidate),
        expected_parent_revision_id=parent.revision.revision_id,
        base_graph_schema=GRAPH_SCHEMA_V6,
        base_graph_payload_sha256=parent.revision.graph_payload_sha256,
        semantic_profile=PROFILE,
    )
    identity_proposals = [
        ContributionIdentityProposal(
            candidate_id="cand:adopted",
            candidate_kind="dnd5e:npc",
            planned_outcome=IdentityOutcome.RESOLVED_EXISTING,
            target_object_id=ADOPTED_OBJECT_ID,
            matched_object_ids=[ADOPTED_OBJECT_ID],
        ),
        ContributionIdentityProposal(
            candidate_id="cand:new",
            candidate_kind="dnd5e:npc",
            planned_outcome=IdentityOutcome.PROVISIONAL_NEW,
            target_object_id=new_object_id,
        ),
    ]
    identity_verdicts = [
        ContributionIdentityVerdict(
            candidate_id="cand:adopted",
            verdict=ContributionIdentityVerdictKind.CONFIRM_EXISTING,
            target_object_id=ADOPTED_OBJECT_ID,
        ),
        ContributionIdentityVerdict(
            candidate_id="cand:new",
            verdict=ContributionIdentityVerdictKind.CREATE_NEW,
            target_object_id=new_object_id,
        ),
    ]
    assertion_verdicts = [
        ContributionAssertionVerdict(
            assertion_id=assertion.assertion_id,
            acceptance_state=AcceptanceState.ACCEPTED,
        )
        for assertion in sorted(candidate.assertions, key=lambda assertion: assertion.assertion_id)
    ]
    digest = derive_review_intent_sha256_v2(
        operation_id=operation_id,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        plan_ref=plan_ref,
        candidate_contribution=candidate,
        identity_proposals=identity_proposals,
        identity_verdicts=identity_verdicts,
        assertion_verdicts=assertion_verdicts,
        reviewer_id=REVIEWER_ID,
        reviewed_at=REVIEWED_AT,
    )
    return ContributionReviewIntentV2(
        operation_id=operation_id,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        plan_ref=plan_ref,
        candidate_contribution=candidate,
        identity_proposals=identity_proposals,
        identity_verdicts=identity_verdicts,
        assertion_verdicts=assertion_verdicts,
        reviewer_id=REVIEWER_ID,
        reviewed_at=REVIEWED_AT,
        review_intent_sha256=digest,
    )


def _submission(
    intent: ContributionReviewIntentV2,
) -> ContributionReviewSubmissionV2:
    return ContributionReviewSubmissionV2(
        intent=intent,
        confirmation=CommitConfirmationReceiptV2(
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


def _policy(intent: ContributionReviewIntentV2) -> CapabilityPolicy:
    return CapabilityPolicy(
        policy_id="pol:cutover-proof",
        graph_scope=GraphScope(
            world_id=intent.world_id,
            campaign_id=intent.campaign_id,
            admissibility=Admissibility.GM,
            revision_pin=intent.plan_ref.expected_parent_revision_id,
        ),
        enabled_tools=[FINALIZE_REVIEW_V2_TOOL],
        tool_rules=[
            ToolCapabilityRule(
                tool_name=FINALIZE_REVIEW_V2_TOOL,
                category=CapabilityCategory.CONFIRM_COMMIT,
                allowed_effects=[CapabilityEffect.COMMIT],
            )
        ],
    )


def _finalize(pg, intent: ContributionReviewIntentV2) -> ContributionReviewStateV2:
    return finalize_contribution_review_v2(
        _submission(intent),
        capability_policy=_policy(intent),
        world_graph_repository=pg.world_graph,
        review_repository=pg.contribution_reviews,
    )


def _publish(pg, review_id: str) -> FinalizedReviewPublication:
    return publish_finalized_review(
        WORLD_ID,
        review_id,
        published_at=PUBLISHED_AT,
        review_repository=pg.contribution_reviews,
        world_graph_repository=pg.world_graph,
        publication_repository=pg.finalized_review_publications,
        graph_reader=eldyrwild_graph_reader(),
    )


def _table_counts(pg) -> dict[str, int]:
    tables = {
        "revisions": "graph_revisions",
        "head_events": "world_graph_head_events",
        "contributions": "graph_contributions",
        "reviews": "contribution_reviews",
        "publications": "finalized_review_publications",
    }
    queries = {
        name: f"SELECT COUNT(*) AS count FROM dungeonmind.{table} WHERE world_id = %s"
        for name, table in tables.items()
    }
    counts: dict[str, int] = {}
    with pg.database.connect() as conn:
        for name, query in queries.items():
            row = conn.execute(query, (WORLD_ID,)).fetchone()
            counts[name] = int(row["count"])
    return counts


@pytest.mark.integration
def test_postgres_v6_governed_publication_commits_child_revision(pg) -> None:
    _adopt(pg)
    parent = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert parent is not None
    before = _table_counts(pg)

    state = _finalize(pg, _intent(parent))
    result = _publish(pg, state.record.review_id)

    child = pg.world_graph.get_revision(WORLD_ID, result.published_revision_id)
    assert child is not None
    assert child.revision.parent_revision_id == PUBLISHED_REVISION_ID
    assert child.revision.graph_schema == GRAPH_SCHEMA_V6
    assert child.revision.operation_ids == [state.record.operation_id]
    assert canonical_sha256(child.graph_payload) == result.graph_payload_sha256
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == (  # type: ignore[union-attr]
        result.published_revision_id
    )

    # The child payload reparses under the pinned profile and carries the new
    # material with Buddy-convention identities.
    snapshot = eldyrwild_graph_reader().parse(
        graph_schema=GRAPH_SCHEMA_V6, graph_payload=child.graph_payload
    )
    created = snapshot.objects[NEW_OBJECT_ID]
    assert created.kind == "dnd5e:npc"
    assert created.label == "Cutover Integration NPC"
    assert EDGE_ID in snapshot.relationships
    edge = snapshot.relationships[EDGE_ID]
    assert edge.subject_object_id == NEW_OBJECT_ID
    assert edge.object_object_id == ADOPTED_OBJECT_ID
    assert edge.predicate == "dnd5e:aware_of"
    adopted = snapshot.objects[ADOPTED_OBJECT_ID]
    assert "Barin the Cutover Witness" in adopted.aliases

    # The reviewed contribution is durable in the ledger through the existing
    # finalize append.
    ledger_ids = {
        contribution.contribution_id for contribution in pg.contributions.list_for_world(WORLD_ID)
    }
    assert state.reviewed_contribution.contribution_id in ledger_ids
    assert state.candidate_contribution.contribution_id in ledger_ids

    after = _table_counts(pg)
    print(
        "D_A->D_B proof:",
        f"parent={PUBLISHED_REVISION_ID}",
        f"child={result.published_revision_id}",
        f"child.parent={child.revision.parent_revision_id}",
        f"payload_sha256={result.graph_payload_sha256}",
        f"counts_before={before}",
        f"counts_after={after}",
        f"reviewed_contribution={state.reviewed_contribution.contribution_id}",
    )
    assert after["revisions"] == before["revisions"] + 1
    assert after["contributions"] == before["contributions"] + 2
    assert after["reviews"] == before["reviews"] + 1
    assert after["publications"] == before["publications"] + 1


@pytest.mark.integration
def test_postgres_v6_publication_exact_replay_returns_same_receipt(pg) -> None:
    _adopt(pg)
    parent = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert parent is not None
    state = _finalize(pg, _intent(parent))
    first = _publish(pg, state.record.review_id)
    before = _table_counts(pg)

    replay = _publish(pg, state.record.review_id)

    assert replay == first
    assert _table_counts(pg) == before


@pytest.mark.integration
def test_postgres_v6_two_reviews_race_one_cas_winner(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresRepositoryBundle,
    )

    _adopt(pg)
    parent = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert parent is not None
    first_state = _finalize(pg, _intent(parent))
    second_state = _finalize(
        pg,
        _intent(
            parent,
            candidate=_candidate(
                contribution_id="contrib:" + "d" * 32,
                new_object_id="node:cutover_integration_npc_second",
                edge_id="edge:cutover:integration:aware:second",
                alias_label="Barin the Second Witness",
            ),
            operation_id="reviewop:" + "d" * 32,
            source_plan_id="plan:cutover-proof-second",
        ),
    )

    bundle_a = PostgresRepositoryBundle(PostgresDatabase(migrated_database))
    bundle_b = PostgresRepositoryBundle(PostgresDatabase(migrated_database))
    barrier = threading.Barrier(2)
    successes: list[FinalizedReviewPublication] = []
    errors: list[BaseException] = []

    def call(bundle: PostgresRepositoryBundle, review_id: str) -> None:
        try:
            barrier.wait(timeout=5)
            successes.append(_publish(bundle, review_id))
        except BaseException as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=call, args=(bundle_a, first_state.record.review_id)),
        threading.Thread(target=call, args=(bundle_b, second_state.record.review_id)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert not any(thread.is_alive() for thread in threads)
    assert len(successes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], StaleParentRevisionError)
    winner = successes[0]
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == (  # type: ignore[union-attr]
        winner.published_revision_id
    )
    loser_review_id = (
        second_state.record.review_id
        if winner.review_id == first_state.record.review_id
        else first_state.record.review_id
    )
    assert pg.finalized_review_publications.get_for_review(WORLD_ID, loser_review_id) is None
    counts = _table_counts(pg)
    assert counts["publications"] == 1
    assert counts["revisions"] == 2  # D_A plus exactly one child


@pytest.mark.integration
def test_postgres_v6_materialization_failure_leaves_zero_mutation(pg) -> None:
    _adopt(pg)
    parent = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert parent is not None
    state = _finalize(
        pg,
        _intent(parent, candidate=_candidate(node_value='{"kind": "npc"}')),
    )
    before = _table_counts(pg)

    with pytest.raises(ContributionMaterializationError) as excinfo:
        _publish(pg, state.record.review_id)

    assert excinfo.value.details["reason"] == "missing_qualified_kind"
    assert _table_counts(pg) == before
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID  # type: ignore[union-attr]


@pytest.mark.integration
def test_postgres_v6_adopted_era_correction_fails_closed(pg) -> None:
    # Adopted-era ka:* records predate contribution receipts; a correction
    # targeting one fails closed with correction_target_unresolvable and zero
    # mutation, even though the record exists in the parent (dispatch §5).
    _adopt(pg)
    parent = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert parent is not None
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertion_corrections"] = [
        {
            "target_contribution_id": "contrib:" + "b" * 32,
            "target_assertion_id": "ka:object:node:barin_coppergleam",
            "correction_kind": "contradicts_and_replaces",
            "replacement_assertion_id": "assertion:cutover:node:new",
        }
    ]
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _finalize(pg, _intent(parent, candidate=candidate))
    before = _table_counts(pg)

    with pytest.raises(ContributionMaterializationError) as excinfo:
        _publish(pg, state.record.review_id)

    assert excinfo.value.details["reason"] == "correction_target_unresolvable"
    assert _table_counts(pg) == before
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID  # type: ignore[union-attr]


@pytest.mark.integration
def test_postgres_v6_mechanics_binding_fails_closed(pg) -> None:
    # Mechanics/statblock bindings are excluded from the World Graph
    # publication seam (dispatch §4): an otherwise valid edge carrying
    # statblock binding material fails closed with zero mutation.
    _adopt(pg)
    parent = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert parent is not None
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][2]["value"] = (
        '{"dm_predicate": "dnd5e:aware_of", "edge_id": "' + EDGE_ID + '",'
        ' "statblock_binding": {"statblock_id": "mm:goblin"}}'
    )
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _finalize(pg, _intent(parent, candidate=candidate))
    before = _table_counts(pg)

    with pytest.raises(ContributionMaterializationError) as excinfo:
        _publish(pg, state.record.review_id)

    assert excinfo.value.details["reason"] == "unsupported_assertion_kind"
    assert excinfo.value.details["binding"] == "statblock_binding"
    assert _table_counts(pg) == before
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == PUBLISHED_REVISION_ID  # type: ignore[union-attr]


@pytest.mark.integration
def test_postgres_v6_alias_fallback_evidence_synthesized(pg) -> None:
    # A source-identity-only alias assertion receives deterministic fallback
    # evidence in the durable published head (dispatch §5).
    _adopt(pg)
    parent = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert parent is not None
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][1]["evidence_refs"] = []
    candidate_payload["assertions"][1]["source_artifact_id"] = NEW_EVIDENCE_ARTIFACT
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _finalize(pg, _intent(parent, candidate=candidate))
    result = _publish(pg, state.record.review_id)

    child = pg.world_graph.get_revision(WORLD_ID, result.published_revision_id)
    assert child is not None
    reviewed_id = state.reviewed_contribution.contribution_id
    fallback_id = f"evidence:{reviewed_id}:{ADOPTED_OBJECT_ID}"
    evidence = {
        record["evidence_ref_id"]: record for record in child.graph_payload["evidence_refs"]
    }
    assert evidence[fallback_id]["source_artifact_id"] == NEW_EVIDENCE_ARTIFACT
    assert evidence[fallback_id]["source_domain_key"] == "manual_seed"
    objects = {obj["object_id"]: obj for obj in child.graph_payload["objects"]}
    alias = objects[ADOPTED_OBJECT_ID]["aliases"][-1]
    assert alias["value"] == "Barin the Cutover Witness"
    assert alias["assertion_metadata"]["evidence_ref_ids"] == [fallback_id]


@pytest.mark.integration
def test_postgres_v6_session_ids_round_trip(pg) -> None:
    # value["session_ids"] materializes into session_refs on the records the
    # assertion creates, durable in the published head (dispatch §5).
    _adopt(pg)
    parent = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert parent is not None
    candidate = _candidate(
        node_value=(
            '{"dm_kind": "dnd5e:npc", "kind": "npc",'
            ' "aliases": ["Cutover Integration NPC"],'
            ' "session_ids": ["session-21", "session-22"]}'
        )
    )
    candidate_payload = candidate.model_dump(mode="json")
    candidate_payload["assertions"][2]["value"] = (
        '{"dm_predicate": "dnd5e:aware_of", "edge_id": "' + EDGE_ID + '",'
        ' "session_ids": ["session-22"]}'
    )
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _finalize(pg, _intent(parent, candidate=candidate))
    result = _publish(pg, state.record.review_id)

    child = pg.world_graph.get_revision(WORLD_ID, result.published_revision_id)
    assert child is not None
    snapshot = eldyrwild_graph_reader().parse(
        graph_schema=GRAPH_SCHEMA_V6, graph_payload=child.graph_payload
    )
    created = snapshot.objects[NEW_OBJECT_ID]
    assert created.existence_assertion_metadata is not None
    assert created.existence_assertion_metadata.session_refs == ["session-21", "session-22"]
    edge = snapshot.relationships[EDGE_ID]
    assert edge.assertion_metadata is not None
    assert edge.assertion_metadata.session_refs == ["session-22"]


@pytest.mark.integration
def test_in_memory_v6_finalize_publish_matches_postgres(pg) -> None:
    _adopt(pg)
    parent = pg.world_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert parent is not None
    pg_state = _finalize(pg, _intent(parent))
    pg_result = _publish(pg, pg_state.record.review_id)

    memory_graph = InMemoryWorldGraphRepository()
    memory_contributions = InMemoryContributionRepository()
    memory_reviews = InMemoryContributionReviewRepository(memory_contributions)
    memory_publications = InMemoryFinalizedReviewPublicationRepository(memory_reviews, memory_graph)
    memory_adoptions = InMemoryExistingWorldAdoptionRepository(
        memory_graph,
        InMemorySourceRepository(),
        memory_contributions,
        InMemoryIdentityDecisionRepository(),
    )
    adopt_existing_world(
        raw_bundle(),
        adopted_at=NOW,
        adoption_repository=memory_adoptions,
        graph_reader=eldyrwild_graph_reader(),
    )
    memory_parent = memory_graph.get_revision(WORLD_ID, PUBLISHED_REVISION_ID)
    assert memory_parent is not None

    memory_state = finalize_contribution_review_v2(
        _submission(_intent(memory_parent)),
        capability_policy=_policy(_intent(memory_parent)),
        world_graph_repository=memory_graph,
        review_repository=memory_reviews,
    )
    memory_result = publish_finalized_review(
        WORLD_ID,
        memory_state.record.review_id,
        published_at=PUBLISHED_AT,
        review_repository=memory_reviews,
        world_graph_repository=memory_graph,
        publication_repository=memory_publications,
        graph_reader=eldyrwild_graph_reader(),
    )

    assert memory_result == pg_result
    assert memory_result.graph_payload_sha256 == pg_result.graph_payload_sha256
    assert memory_result.published_revision_id == pg_result.published_revision_id
