"""Owning explicit V7 publication: reviewed delta, replay, rollback and family isolation."""

import copy

import pytest

from dungeonmind.application.graph_snapshot_v7 import VersionedUnionGraphSnapshotReaderV7
from dungeonmind.application.review_materialization_v6 import review_source_refs_v6
from dungeonmind.application.review_materialization_v7 import materialize_finalized_review_v7
from dungeonmind.application.review_publication_v7 import publish_finalized_review_v7
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.review_publication import (
    FinalizedReviewPublicationCommandV3,
    FinalizedReviewPublicationV3,
)
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.memory import (
    InMemoryFinalizedReviewPublicationRepository,
    InMemoryIdentityDecisionRepository,
    InMemorySourceRepository,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.world_object_vocabulary import load_builtin_v3_descriptor
from tests.unit.test_contribution_review_v3 import source_snapshot
from tests.unit.test_contribution_review_v5 import finalize, setup_case


def prepared(schema="dm_union_graph_v6", *, failure_hook=None, enabled=True, admission=None):
    case = setup_case(schema, admission=admission)
    state = finalize(case)
    sources = InMemorySourceRepository()
    snapshot = source_snapshot()
    for source in snapshot.artifacts.values():
        sources.put_artifact(source)
    for revision in snapshot.revisions.values():
        sources.put_revision(revision)
    reader = VersionedUnionGraphSnapshotReaderV7(
        StaticSemanticProfileRegistry([load_builtin_v3_descriptor()])
    )
    publications = InMemoryFinalizedReviewPublicationRepository(
        case[3],
        case[0],
        source_repository=sources,
        identity_repository=InMemoryIdentityDecisionRepository(),
        v7_graph_reader=reader if enabled else None,
        failure_hook=failure_hook,
    )
    return case, state, sources, reader, publications


def command_for(preparation, *, alter=None):
    case, state, sources, reader, _ = preparation
    parent = case[1]
    artifacts, revisions = review_source_refs_v6(state)
    snapshot = sources.get_provenance_snapshot(artifact_ids=artifacts, revision_ids=revisions)
    result = materialize_finalized_review_v7(
        state,
        parent=parent,
        graph_reader=reader,
        source_snapshot=snapshot,
    )
    payload = copy.deepcopy(result.graph_payload)
    if alter:
        alter(payload)
    digest = canonical_sha256(payload)
    record = state.record
    return FinalizedReviewPublicationCommandV3(
        world_id=record.world_id,
        review_id=record.review_id,
        reviewed_contribution_id=record.reviewed_contribution_id,
        reviewed_contribution_sha256=record.reviewed_contribution_sha256,
        review_intent_sha256=record.review_intent_sha256,
        confirmation_id=record.confirmation_id,
        operation_id=record.operation_id,
        expected_parent_revision_id=parent.revision.revision_id,
        parent_graph_payload_sha256=parent.revision.graph_payload_sha256,
        parent_graph_schema=parent.revision.graph_schema,
        expected_published_revision_id=compute_revision_id(
            world_id=record.world_id,
            parent_revision_id=parent.revision.revision_id,
            operation_ids=[record.operation_id],
            graph_schema="dm_union_graph_v7",
            graph_payload_sha256=digest,
        ),
        graph_payload=payload,
        graph_payload_sha256=digest,
        requested_published_at=record.reviewed_at,
    )


def publish(preparation):
    case, state, _, reader, publications = preparation
    return publish_finalized_review_v7(
        state.record.world_id,
        state.record.review_id,
        published_at=state.record.reviewed_at,
        review_repository=case[3],
        world_graph_repository=case[0],
        publication_repository=publications,
        graph_reader=reader,
    )


@pytest.mark.parametrize("schema", ["dm_union_graph_v6", "dm_union_graph_v7"])
def test_exact_confirmed_v5_delta_publishes_as_v3_receipt_and_replays(schema):
    preparation = prepared(schema)
    case, state, _, _, publications = preparation
    receipt = publish(preparation)
    assert isinstance(receipt, FinalizedReviewPublicationV3)
    assert receipt.parent_graph_schema == schema
    assert receipt.graph_schema == "dm_union_graph_v7"
    assert publish(preparation) == receipt
    assert publications.get_for_review(state.record.world_id, state.record.review_id) == receipt
    assert len(case[0]._revisions) == 2
    assert case[0].get_revision(case[1].revision.world_id, case[1].revision.revision_id) == case[1]


def test_self_consistent_forged_child_is_rejected_at_owning_transaction_boundary():
    preparation = prepared()

    def forge(payload):
        obj = next(o for o in payload["objects"] if o["properties"])
        obj["properties"][0]["value"]["count"] = 999

    command = command_for(preparation, alter=forge)
    with pytest.raises(PersistenceIntegrityError, match="reviewed semantic delta"):
        preparation[4].publish(command)
    assert len(preparation[0][0]._revisions) == 1
    assert preparation[4]._records_by_review == {}


@pytest.mark.parametrize("fail_at", [1, 2])
def test_failure_rolls_back_graph_head_and_every_receipt_index(fail_at):
    calls = []

    def fail():
        calls.append(1)
        if len(calls) == fail_at:
            raise RuntimeError("deliberate V7 transaction failure")

    preparation = prepared(failure_hook=fail)
    case = preparation[0]
    with pytest.raises(RuntimeError, match="deliberate"):
        publish(preparation)
    assert len(case[0]._revisions) == 1
    assert (
        case[0].get_head(case[1].revision.world_id).head_revision_id == case[1].revision.revision_id
    )
    assert preparation[4]._records_by_review == preparation[4]._records_by_operation == {}
    assert preparation[4]._records_by_revision == {}


def test_missing_trusted_v7_reader_cannot_activate_write_via_command_payload():
    preparation = prepared(enabled=False)
    with pytest.raises(PersistenceIntegrityError, match="authority unavailable"):
        preparation[4].publish(command_for(preparation))
    assert len(preparation[0][0]._revisions) == 1


def test_raw_revision_cannot_be_adopted_as_governed_v7_publication():
    preparation = prepared()
    command = command_for(preparation)
    graph = preparation[0][0]
    graph.publish_revision(
        PublishRevisionCommand(
            world_id=command.world_id,
            parent_revision_id=command.expected_parent_revision_id,
            expected_parent_revision_id=command.expected_parent_revision_id,
            operation_ids=[command.operation_id],
            graph_schema=command.graph_schema,
            graph_payload=command.graph_payload,
            created_at=command.requested_published_at,
        )
    )
    graph.rollback_head(
        command.world_id,
        command.expected_parent_revision_id,
        updated_at=command.requested_published_at,
    )
    with pytest.raises(PersistenceIntegrityError) as failure:
        preparation[4].publish(command)
    assert failure.value.details["reason"] == "admission_raw_revision_adoption_forbidden"
    assert preparation[4]._records_by_review == {}


def test_second_confirmed_ingestion_adds_c1_support_without_hiding_original_c2_identity():
    assert_two_campaign_ingestions(prepared())


def assert_two_campaign_ingestions(preparation):
    from datetime import timedelta

    from dungeonmind.application.contribution_review_v5 import finalize_contribution_review_v5
    from dungeonmind.application.graph_scope_v7 import project_scoped_snapshot_v7
    from dungeonmind.contracts.contribution import GraphContributionV4
    from dungeonmind.contracts.contribution_review import (
        ContributionAssertionVerdict,
        ContributionIdentityProposal,
        ContributionIdentityVerdict,
        derive_confirmation_id,
    )
    from dungeonmind.contracts.contribution_review_v5 import (
        CommitConfirmationReceiptV5,
        ContributionReviewIntentV5,
        ContributionReviewSubmissionV5,
        contribution_v4_payload_sha256,
        derive_review_intent_sha256_v5,
    )
    from dungeonmind.contracts.projection import Admissibility
    from dungeonmind.contracts.projection_v2 import ScopeModeV2

    case, first_state, sources, reader, publications = preparation
    first = publish(preparation)
    parent = case[0].get_revision(first.world_id, first.published_revision_id)
    old_node = next(
        a for a in first_state.candidate_contribution.assertions if a.assertion_kind == "node"
    )
    target = old_node.subject_object_id
    original_object = copy.deepcopy(
        next(o for o in parent.graph_payload["objects"] if o["object_id"] == target)
    )
    artifact = next(iter(source_snapshot().artifacts.values())).model_copy(
        update={
            "source_artifact_id": "artifact:c1-independent-proof",
            "campaign_id": "longmont-c1",
            "current_revision_id": "revision:c1-independent-proof",
            "session_id": "session-1",
            "source_domain_key": "session_recap",
        }
    )
    source_revision = next(iter(source_snapshot().revisions.values())).model_copy(
        update={
            "source_artifact_id": artifact.source_artifact_id,
            "source_revision_id": artifact.current_revision_id,
        }
    )
    sources.put_artifact(artifact)
    sources.put_revision(source_revision)
    raw = first_state.candidate_contribution.model_dump(mode="json")
    node = old_node.model_dump(mode="json")
    node.update(
        assertion_id="assertion:c1-independent-proof",
        campaign_scope="longmont-c1",
        label="First-campaign witnessed NPC",
        source_artifact_id=artifact.source_artifact_id,
        source_revision_id=source_revision.source_revision_id,
    )
    for evidence in node["evidence_refs"]:
        evidence.update(
            evidence_ref_id="evidence:c1-independent-proof",
            source_artifact_id=artifact.source_artifact_id,
            source_revision_id=source_revision.source_revision_id,
            source_domain_key="session_recap",
            session_id="session-1",
        )
    raw.update(
        contribution_id="contrib:" + "d" * 32,
        status="active",
        assertions=[node],
        campaign_scope="longmont-c1",
        source_artifact_id=artifact.source_artifact_id,
        source_revision_id=source_revision.source_revision_id,
    )
    candidate = GraphContributionV4.model_validate(raw)
    plan = first_state.record.plan_ref.model_copy(
        update={
            "source_plan_id": "plan:c1-second-ingestion",
            "candidate_contribution_sha256": contribution_v4_payload_sha256(candidate),
            "expected_parent_revision_id": parent.revision.revision_id,
            "base_graph_payload_sha256": parent.revision.graph_payload_sha256,
            "base_graph_schema": "dm_union_graph_v7",
        }
    )
    fields = dict(
        operation_id="reviewop:" + "d" * 32,
        world_id=first.world_id,
        campaign_id="longmont-c1",
        plan_ref=plan,
        candidate_contribution=candidate,
        reviewer_id=first_state.record.reviewer_id,
        reviewed_at=first_state.record.reviewed_at + timedelta(minutes=1),
        identity_proposals=[
            ContributionIdentityProposal(
                candidate_id="candidate:c1",
                candidate_kind="dnd5e:npc",
                planned_outcome="resolved_existing",
                target_object_id=target,
                matched_object_ids=[target],
            )
        ],
        identity_verdicts=[
            ContributionIdentityVerdict(
                candidate_id="candidate:c1", verdict="confirm_existing", target_object_id=target
            )
        ],
        assertion_verdicts=[
            ContributionAssertionVerdict(
                assertion_id=node["assertion_id"], acceptance_state="accepted"
            )
        ],
    )
    intent = ContributionReviewIntentV5(
        **fields, review_intent_sha256=derive_review_intent_sha256_v5(**fields)
    )
    confirmation = CommitConfirmationReceiptV5(
        confirmation_id=derive_confirmation_id(
            operation_id=intent.operation_id,
            review_intent_sha256=intent.review_intent_sha256,
            actor=intent.reviewer_id,
            confirmed_at=intent.reviewed_at,
        ),
        operation_id=intent.operation_id,
        review_intent_sha256=intent.review_intent_sha256,
        actor=intent.reviewer_id,
        confirmed_at=intent.reviewed_at,
        world_id=intent.world_id,
        campaign_id=intent.campaign_id,
        expected_parent_revision_id=parent.revision.revision_id,
    )
    scope = case[5].graph_scope.model_copy(
        update={"campaign_id": "longmont-c1", "revision_pin": parent.revision.revision_id}
    )
    second_state = finalize_contribution_review_v5(
        ContributionReviewSubmissionV5(intent=intent, confirmation=confirmation),
        capability_policy=case[5].model_copy(update={"graph_scope": scope}),
        world_graph_repository=case[0],
        review_repository=case[3],
    )
    second = publish_finalized_review_v7(
        second_state.record.world_id,
        second_state.record.review_id,
        published_at=second_state.record.reviewed_at,
        review_repository=case[3],
        world_graph_repository=case[0],
        publication_repository=publications,
        graph_reader=reader,
    )
    child = case[0].get_revision(second.world_id, second.published_revision_id)
    obj = next(o for o in child.graph_payload["objects"] if o["object_id"] == target)
    assert obj["assertion_metadata"] == original_object["assertion_metadata"]
    assert len(obj["independent_existence_assertions"]) == 1
    parsed = reader.parse(graph_schema="dm_union_graph_v7", graph_payload=child.graph_payload)
    refs = child.graph_payload["evidence_refs"]
    snapshot = sources.get_provenance_snapshot(
        artifact_ids=sorted({e["source_artifact_id"] for e in refs}),
        revision_ids=sorted({e["source_revision_id"] for e in refs if e["source_revision_id"]}),
    )
    for campaign in ["longmont-c1", "longmont-c2"]:
        scoped = project_scoped_snapshot_v7(
            parsed,
            sources=snapshot,
            world_id=second.world_id,
            campaign_id=campaign,
            admissibility=Admissibility.GM,
            scope_mode=ScopeModeV2.CAMPAIGN,
        ).snapshot
        assert target in scoped.objects
    assert publish(preparation) == first
    assert publications.get_for_review(second.world_id, second.review_id) == second


@pytest.mark.parametrize("validator_available", [False, True])
def test_v7_protected_profile_keeps_mandatory_validator_boundary(validator_available):
    from dungeonmind.application.publication_admission import (
        InMemoryPublicationAdmissionRepository,
        PublicationAdmissionRegistry,
    )
    from tests.unit.test_publication_admission import SyntheticValidator, admission_policy

    authority = InMemoryPublicationAdmissionRepository()
    policy = admission_policy(setup_case()[4].intent.plan_ref.semantic_profile)
    authority.register(policy)
    preparation = prepared(admission=authority)
    case, _, _, _, publications = preparation
    validator = SyntheticValidator()
    if validator_available:
        publications._admission_registry = PublicationAdmissionRegistry(
            (
                (
                    policy.validator_ref.validator_id,
                    policy.validator_ref.validator_version,
                    validator,
                ),
            )
        )
        receipt = publish(preparation)
        assert receipt.admission_policy_ref == policy.reference
        assert receipt.admission_context is not None
        assert len(validator.calls) == 1
        assert publications.get_for_review(receipt.world_id, receipt.review_id) == receipt
    else:
        with pytest.raises(PersistenceIntegrityError) as failure:
            publish(preparation)
        assert failure.value.details["reason"] == "validator_unavailable"
        assert len(case[0]._revisions) == 1
        assert publications._records_by_review == {}


def test_replay_rejects_missing_immutable_source_revision():
    preparation = prepared()
    receipt = publish(preparation)
    sources = preparation[2]
    sources._revisions.pop(receipt.retained_sources.revisions[0].source_revision_id)
    with pytest.raises(PersistenceIntegrityError, match="historical source revision changed"):
        preparation[4].get_for_review(receipt.world_id, receipt.review_id)
    # Detection does not erase the published graph or advance its head.
    assert (
        preparation[0][0].get_head(receipt.world_id).head_revision_id
        == receipt.published_revision_id
    )


def test_missing_source_closure_cannot_publish():
    preparation = prepared()
    command = command_for(preparation)
    preparation[2]._revisions.clear()
    from dungeonmind.domain.errors import ContributionMaterializationError

    with pytest.raises(ContributionMaterializationError) as failure:
        preparation[4].publish(command)
    assert failure.value.details["reason"] == "source_revision_missing"
    assert len(preparation[0][0]._revisions) == 1
    assert preparation[4]._records_by_review == {}


def test_published_v7_is_readable_through_ordinary_native_complete_object_service():
    from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
    from dungeonmind.application.world_graph_retrieval import WorldGraphRetrievalService
    from dungeonmind.contracts.projection import Admissibility
    from dungeonmind.contracts.projection_v2 import ScopeModeV2, WorldGraphProjectionRequestV2
    from dungeonmind.infrastructure.memory import InMemoryReviewedWorldInitializationRepository

    preparation = prepared()
    case, state, sources, reader, _ = preparation
    receipt = publish(preparation)
    projection = WorldGraphProjectionService(
        world_graph=case[0],
        sources=sources,
        graph_reader=reader,
        reviewed_world_initializations=InMemoryReviewedWorldInitializationRepository(
            case[0], sources, case[2]
        ),
    )
    service = WorldGraphRetrievalService(projection=projection, sources=sources)
    target = next(
        a.subject_object_id
        for a in state.reviewed_contribution.assertions
        if a.assertion_kind == "node"
    )
    result = service.get_complete_object(
        WorldGraphProjectionRequestV2(
            world_id=receipt.world_id,
            campaign_id=state.record.campaign_id,
            scope_mode=ScopeModeV2.CAMPAIGN,
            admissibility=Admissibility.GM,
            revision_pin=receipt.published_revision_id,
        ),
        object_id=target,
    )
    assert result.found
    assert result.object.object_id == target
    assert result.snapshot.revision_id == receipt.published_revision_id
    assert result.anchors
    assert result.completeness.status == "complete"
