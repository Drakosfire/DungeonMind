"""Explicit confirmation and durable reconstruction across the V7 parent boundary."""

import copy
import json

import pytest
from pydantic import ValidationError

from dungeonmind.application.contribution_review_v5 import finalize_contribution_review_v5
from dungeonmind.application.review_publication import publish_finalized_review
from dungeonmind.contracts.contribution_review import derive_confirmation_id
from dungeonmind.contracts.contribution_review_v4 import ContributionReviewIntentV4
from dungeonmind.contracts.contribution_review_v5 import (
    FINALIZE_REVIEW_V5_TOOL,
    CommitConfirmationReceiptV5,
    ContributionReviewIntentV5,
    ContributionReviewStateV5,
    ContributionReviewSubmissionV5,
    derive_review_intent_sha256_v5,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.domain.errors import (
    CapabilityDeniedError,
    ContributionReviewValidationError,
    PersistenceIntegrityError,
    StaleParentRevisionError,
)
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryContributionReviewRepository,
    InMemoryFinalizedReviewPublicationRepository,
    InMemoryWorldGraphRepository,
)
from tests.unit.test_contribution_review_v2 import _reader, _stored_parent
from tests.unit.test_contribution_review_v4 import VALUE, upgrade_intent
from tests.unit.test_contribution_review_v4 import policy as old_policy


def setup_case(schema="dm_union_graph_v7", *, failure_hook=None, admission=None):
    template = _stored_parent()
    graph = InMemoryWorldGraphRepository(admission=admission)
    payload = copy.deepcopy(template.graph_payload)
    if schema == "dm_union_graph_v7":
        payload["object_existence_support_schema"] = "dm_independent_object_existence_support_v1"
    revision = graph.publish_revision(
        PublishRevisionCommand(
            world_id=template.revision.world_id,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["test:v5-parent"],
            graph_schema=schema,
            graph_payload=payload,
            created_at=template.revision.created_at,
        )
    )
    parent = graph.get_revision(revision.world_id, revision.revision_id)
    old = upgrade_intent()
    fields = {
        k: getattr(old, k)
        for k in type(old).model_fields
        if k not in {"schema_version", "review_intent_sha256"}
    }
    fields["plan_ref"] = old.plan_ref.model_copy(
        update={
            "base_graph_schema": schema,
            "expected_parent_revision_id": revision.revision_id,
            "base_graph_payload_sha256": revision.graph_payload_sha256,
        }
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
        world_id=intent.world_id,
        campaign_id=intent.campaign_id,
        expected_parent_revision_id=revision.revision_id,
        confirmed_at=intent.reviewed_at,
    )
    submission = ContributionReviewSubmissionV5(intent=intent, confirmation=confirmation)
    policy = old_policy(intent)
    policy = policy.model_copy(
        update={
            "enabled_tools": [FINALIZE_REVIEW_V5_TOOL],
            "tool_rules": [
                r.model_copy(update={"tool_name": FINALIZE_REVIEW_V5_TOOL})
                for r in policy.tool_rules
            ],
        }
    )
    contributions = InMemoryContributionRepository(admission=admission)
    reviews = InMemoryContributionReviewRepository(contributions, failure_hook=failure_hook)
    return graph, parent, contributions, reviews, submission, policy


def finalize(case, *, policy=None):
    graph, _, _, reviews, submission, selected_policy = case
    return finalize_contribution_review_v5(
        submission,
        capability_policy=policy or selected_policy,
        world_graph_repository=graph,
        review_repository=reviews,
    )


@pytest.mark.parametrize("schema", ["dm_union_graph_v6", "dm_union_graph_v7"])
def test_explicit_family_finalizes_reconstructs_and_replays_without_graph_mutation(schema):
    case = setup_case(schema)
    graph, parent, contributions, reviews, submission, _ = case
    state = finalize(case)
    assert isinstance(state, ContributionReviewStateV5)
    assert state.record.schema_version == "dm_contribution_review_record_v5"
    assert state.candidate_contribution.schema_version == "dm_graph_contribution_v4"
    assert json.loads(state.reviewed_contribution.assertions[0].value)["value"] == VALUE
    assert reviews.get(state.record.world_id, state.record.review_id) == state
    assert finalize(case) == state
    assert len(contributions._items) == 2
    assert graph.get_head(state.record.world_id).head_revision_id == parent.revision.revision_id
    assert state.record.review_intent_sha256 == submission.intent.review_intent_sha256


def test_legacy_confirmation_authority_does_not_enable_new_review_family():
    case = setup_case()
    with pytest.raises(CapabilityDeniedError):
        finalize(case, policy=old_policy(case[4].intent))
    assert case[2]._items == {} and case[3]._records == {}


@pytest.mark.parametrize(
    "field,value",
    [
        ("actor", "another-reviewer"),
        ("world_id", "another-world"),
        ("campaign_id", "another-campaign"),
        ("expected_parent_revision_id", "rev:other"),
    ],
)
def test_confirmation_binds_actor_world_campaign_and_exact_parent(field, value):
    case = setup_case()
    receipt = case[4].confirmation
    receipt = receipt.model_copy(update={field: value})
    receipt.confirmation_id = derive_confirmation_id(
        operation_id=receipt.operation_id,
        review_intent_sha256=receipt.review_intent_sha256,
        actor=receipt.actor,
        confirmed_at=receipt.confirmed_at,
    )
    case[4].confirmation = receipt
    with pytest.raises(ContributionReviewValidationError):
        finalize(case)
    assert case[2]._items == {} and case[3]._records == {}


def test_review_failure_rolls_back_both_typed_children_and_record():
    def fail():
        raise RuntimeError("deliberate review persistence failure")

    case = setup_case(failure_hook=fail)
    with pytest.raises(RuntimeError, match="deliberate"):
        finalize(case)
    assert case[2]._items == {} and case[3]._records == {}


def test_stale_head_does_not_persist_confirmation():
    case = setup_case()
    graph, parent = case[:2]
    graph.publish_revision(
        PublishRevisionCommand(
            world_id=parent.revision.world_id,
            parent_revision_id=parent.revision.revision_id,
            expected_parent_revision_id=parent.revision.revision_id,
            operation_ids=["test:advance"],
            graph_schema=parent.revision.graph_schema,
            graph_payload=parent.graph_payload,
            created_at=parent.revision.created_at,
        )
    )
    with pytest.raises(StaleParentRevisionError):
        finalize(case)
    assert case[2]._items == {} and case[3]._records == {}


def test_new_family_does_not_expand_old_v4_parent_or_digest_contract():
    case = setup_case()
    raw = case[4].intent.model_dump(mode="json")
    raw["schema_version"] = "dm_contribution_review_intent_v4"
    with pytest.raises(ValidationError):
        ContributionReviewIntentV4.model_validate(raw)
    raw = case[4].intent.model_dump(mode="json")
    raw["review_intent_sha256"] = upgrade_intent().review_intent_sha256
    with pytest.raises(ValidationError):
        ContributionReviewIntentV5.model_validate(raw)


def test_legacy_publication_rejects_v5_before_any_graph_or_receipt_write():
    case = setup_case()
    state = finalize(case)
    publications = InMemoryFinalizedReviewPublicationRepository(case[3], case[0])
    with pytest.raises(PersistenceIntegrityError):
        publish_finalized_review(
            state.record.world_id,
            state.record.review_id,
            published_at=state.record.reviewed_at,
            review_repository=case[3],
            world_graph_repository=case[0],
            publication_repository=publications,
            graph_reader=_reader(),
        )
    assert publications._records_by_review == {}
    assert case[0].get_head(state.record.world_id).head_revision_id == case[1].revision.revision_id


@pytest.mark.parametrize("schema", ["dm_graph_v1", "dm_union_graph_v8"])
def test_unknown_parent_families_do_not_gain_review_authority(schema):
    with pytest.raises(ValidationError, match="v5 review intents require"):
        setup_case(schema)


def test_mutated_typed_literal_is_rejected_before_coercive_serialization():
    case = setup_case()
    case[4].intent.candidate_contribution.assertions[0].value = b"{}"
    with pytest.raises(ContributionReviewValidationError):
        finalize(case)
    assert case[2]._items == {} and case[3]._records == {}


def test_reconstruction_rejects_tampered_reviewed_property_content():
    case = setup_case()
    state = finalize(case)
    key = (state.record.world_id, state.record.reviewed_contribution_id)
    child = case[2]._items[key].model_copy(deep=True)
    child.assertions[0].value = '{"forged": true}'
    case[2]._items[key] = child
    with pytest.raises(PersistenceIntegrityError):
        case[3].get(state.record.world_id, state.record.review_id)
