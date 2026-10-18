"""V4 uses real finalization and independently materializes reviewed literals."""

import json

import pytest

from dungeonmind.application.contribution_review_v4 import _build_review_state
from dungeonmind.application.review_materialization_v4 import materialize_finalized_review_v4
from dungeonmind.contracts.contribution import GraphContributionV4
from dungeonmind.contracts.contribution_review import (
    ContributionAssertionVerdict,
    derive_confirmation_id,
)
from dungeonmind.contracts.contribution_review_v4 import (
    FINALIZE_REVIEW_V4_TOOL,
    CommitConfirmationReceiptV4,
    ContributionReviewIntentV4,
    ContributionReviewSubmissionV4,
    contribution_v4_payload_sha256,
    derive_review_intent_sha256_v4,
)
from tests.unit.test_contribution_review_v2 import _policy, _reader, _stored_parent
from tests.unit.test_contribution_review_v3 import source_snapshot
from tests.unit.test_contribution_review_v3_contract import typed_candidate, typed_intent

PROPERTY_ID = "assertion:reviewed:property"
VALUE = {"count": 2, "label": "source wording", "unknown": None, "flags": [True, False]}


def candidate(base=None, *, subject=None, kind="property"):
    base = base or typed_candidate()
    raw = base.model_dump(mode="json")
    raw["schema_version"] = "dm_graph_contribution_v4"
    node = next(a for a in raw["assertions"] if a["assertion_kind"] == "node")
    prop = dict(
        node,
        assertion_id=PROPERTY_ID,
        assertion_kind=kind,
        subject_object_id=subject or node["subject_object_id"],
        object_object_id=None,
        predicate=None,
        label=None,
        value=json.dumps(
            {
                "schema_version": "dm_reviewed_property_literal_v1",
                "property_term": "dnd5e:test_fact",
                "value": VALUE,
            }
        ),
    )
    raw["assertions"].insert(0, prop)
    return GraphContributionV4.model_validate(raw)


def upgrade_intent(old=None, *, new_candidate=None, reject_property=False):
    old = old or typed_intent()
    new_candidate = new_candidate or candidate(old.candidate_contribution)
    fields = {
        name: getattr(old, name)
        for name in [
            "operation_id",
            "world_id",
            "campaign_id",
            "identity_proposals",
            "identity_verdicts",
            "reviewer_id",
            "reviewed_at",
        ]
    }
    fields["plan_ref"] = old.plan_ref.model_copy(
        update={"candidate_contribution_sha256": contribution_v4_payload_sha256(new_candidate)}
    )
    fields["candidate_contribution"] = new_candidate
    verdicts = [
        *old.assertion_verdicts,
        ContributionAssertionVerdict(
            assertion_id=PROPERTY_ID, acceptance_state="rejected" if reject_property else "accepted"
        ),
    ]
    fields["assertion_verdicts"] = sorted(verdicts, key=lambda v: v.assertion_id)
    return ContributionReviewIntentV4(
        **fields, review_intent_sha256=derive_review_intent_sha256_v4(**fields)
    )


def submission(intent=None):
    intent = intent or upgrade_intent()
    return ContributionReviewSubmissionV4(
        intent=intent,
        confirmation=CommitConfirmationReceiptV4(
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


def policy(intent):
    old = _policy(intent)
    return old.model_copy(
        update={
            "enabled_tools": [FINALIZE_REVIEW_V4_TOOL],
            "tool_rules": [
                r.model_copy(update={"tool_name": FINALIZE_REVIEW_V4_TOOL}) for r in old.tool_rules
            ],
        }
    )


def materialize(state):
    return materialize_finalized_review_v4(
        state, parent=_stored_parent(), graph_reader=_reader(), source_snapshot=source_snapshot()
    )


def test_property_before_node_preserves_exact_value_and_host_metadata():
    state = _build_review_state(submission())
    result = materialize(state)
    obj = next(o for o in result.graph_payload["objects"] if o["properties"])
    row = obj["properties"][0]
    assert row["value"] == VALUE and row["property_term"] == "dnd5e:test_fact"
    assert row["assertion_metadata"]["assertion_id"] == PROPERTY_ID
    assert row["assertion_metadata"]["evidence_ref_ids"]
    assert row["assertion_metadata"]["visibility"] == "gm"


def test_rejected_property_and_historical_attribute_do_not_write_properties():
    for intent in [
        upgrade_intent(reject_property=True),
        upgrade_intent(new_candidate=candidate(kind="attribute")),
    ]:
        result = materialize(_build_review_state(submission(intent)))
        assert all(not o["properties"] for o in result.graph_payload["objects"])


def test_orphan_property_and_unadmitted_namespace_fail():
    from dungeonmind.domain.errors import ContributionMaterializationError

    for changes in [
        {"subject_object_id": "object:absent"},
        {
            "value": json.dumps(
                {
                    "schema_version": "dm_reviewed_property_literal_v1",
                    "property_term": "foreign:fact",
                    "value": 2,
                }
            )
        },
    ]:
        item = candidate()
        item.assertions[0] = item.assertions[0].model_copy(update=changes)
        with pytest.raises(ContributionMaterializationError):
            materialize(_build_review_state(submission(upgrade_intent(new_candidate=item))))


def test_finalizer_rejects_mutation_before_a_coercive_dump():
    from dungeonmind.application.contribution_review_v4 import finalize_contribution_review_v4
    from dungeonmind.domain.errors import ContributionReviewValidationError

    item = submission()
    item.intent.candidate_contribution.assertions[0].value = b"{}"
    with pytest.raises(ContributionReviewValidationError):
        finalize_contribution_review_v4(
            item,
            capability_policy=policy(item.intent),
            world_graph_repository=None,
            review_repository=None,
        )


def version_intent(old):
    """Upgrade only the explicit test input family, preserving approved content."""
    raw = old.candidate_contribution.model_dump(mode="json")
    raw["schema_version"] = "dm_graph_contribution_v4"
    item = GraphContributionV4.model_validate(raw)
    fields = {
        name: getattr(old, name)
        for name in [
            "operation_id",
            "world_id",
            "campaign_id",
            "identity_proposals",
            "identity_verdicts",
            "assertion_verdicts",
            "reviewer_id",
            "reviewed_at",
        ]
    }
    fields.update(
        candidate_contribution=item,
        plan_ref=old.plan_ref.model_copy(
            update={"candidate_contribution_sha256": contribution_v4_payload_sha256(item)}
        ),
    )
    return ContributionReviewIntentV4(
        **fields, review_intent_sha256=derive_review_intent_sha256_v4(**fields)
    )


def test_same_term_appends_independent_assertions_without_scalar_normalization():
    from dungeonmind.contracts.contribution_review import ContributionAssertionVerdict

    item = candidate()
    item.assertions.insert(
        0, item.assertions[0].model_copy(update={"assertion_id": "assertion:property:second"})
    )
    old = typed_intent()
    fields = {
        name: getattr(old, name)
        for name in [
            "operation_id",
            "world_id",
            "campaign_id",
            "identity_proposals",
            "identity_verdicts",
            "reviewer_id",
            "reviewed_at",
        ]
    }
    fields.update(
        candidate_contribution=item,
        plan_ref=old.plan_ref.model_copy(
            update={"candidate_contribution_sha256": contribution_v4_payload_sha256(item)}
        ),
        assertion_verdicts=sorted(
            [
                ContributionAssertionVerdict(
                    assertion_id=a.assertion_id, acceptance_state="accepted"
                )
                for a in item.assertions
            ],
            key=lambda a: a.assertion_id,
        ),
    )
    intent = ContributionReviewIntentV4(
        **fields, review_intent_sha256=derive_review_intent_sha256_v4(**fields)
    )
    result = materialize(_build_review_state(submission(intent)))
    props = next(o["properties"] for o in result.graph_payload["objects"] if o["properties"])
    assert len(props) == 2 and props[0]["property_term"] == props[1]["property_term"]
    assert (
        props[0]["assertion_metadata"]["assertion_id"]
        != props[1]["assertion_metadata"]["assertion_id"]
    )


def test_memory_finalizer_reconstructs_v4_and_rejects_stale_or_changed_review():
    from dungeonmind.application.contribution_review_v4 import finalize_contribution_review_v4
    from dungeonmind.contracts.contribution_review_v4 import ContributionReviewStateV4
    from dungeonmind.domain.errors import IdempotencyConflictError, StaleParentRevisionError
    from tests.unit.test_contribution_review_v2 import _GraphRepository, _repositories

    reviews, contributions = _repositories()
    intent = upgrade_intent()
    graph = _GraphRepository(_stored_parent())
    state = finalize_contribution_review_v4(
        submission(intent),
        capability_policy=policy(intent),
        world_graph_repository=graph,
        review_repository=reviews,
    )
    reopened = reviews.get(intent.world_id, state.record.review_id)
    assert isinstance(reopened, ContributionReviewStateV4) and reopened == state
    assert (
        contributions.get(intent.world_id, state.reviewed_contribution.contribution_id)
        == state.reviewed_contribution
    )
    assert (
        finalize_contribution_review_v4(
            submission(intent),
            capability_policy=policy(intent),
            world_graph_repository=graph,
            review_repository=reviews,
        )
        == state
    )
    changed = candidate()
    value = json.loads(changed.assertions[0].value)
    value["value"] = "a different reviewed literal"
    changed.assertions[0].value = json.dumps(value)
    changed_intent = upgrade_intent(new_candidate=changed)
    with pytest.raises(IdempotencyConflictError):
        finalize_contribution_review_v4(
            submission(changed_intent),
            capability_policy=policy(changed_intent),
            world_graph_repository=graph,
            review_repository=reviews,
        )
    graph.head_revision_id = "revision:advanced"
    with pytest.raises(StaleParentRevisionError):
        finalize_contribution_review_v4(
            submission(intent),
            capability_policy=policy(intent),
            world_graph_repository=graph,
            review_repository=reviews,
        )
    assert reviews.get(intent.world_id, state.record.review_id) == state


@pytest.mark.parametrize("version", [2, 3])
def test_historical_attribute_literal_tag_never_authorizes_property_materialization(version):
    from dungeonmind.application.review_materialization_v6 import materialize_finalized_review_v6
    from dungeonmind.contracts.contribution import (
        GraphContributionAssertionV2,
        GraphContributionAssertionV3,
    )
    from dungeonmind.contracts.contribution_review import ContributionAssertionVerdict
    from tests.unit import test_contribution_review_v2 as v2

    if version == 2:
        item = v2._candidate()
        raw = item.assertions[0].model_dump(mode="json")
        raw.update(
            assertion_id=PROPERTY_ID,
            assertion_kind="attribute",
            object_object_id=None,
            predicate=None,
            label=None,
            value=json.dumps(
                {
                    "schema_version": "dm_reviewed_property_literal_v1",
                    "property_term": "dnd5e:test_fact",
                    "value": VALUE,
                }
            ),
        )
        item.assertions.append(GraphContributionAssertionV2.model_validate(raw))
        from dungeonmind.application.contribution_review_v2 import _build_review_state as build

        state = build(v2._submission(v2._intent(candidate=item)))
        result = materialize_finalized_review_v6(
            state, parent=_stored_parent(), graph_reader=_reader()
        )
    else:
        from dungeonmind.application.contribution_review_v3 import _build_review_state as build
        from dungeonmind.contracts.contribution_review_v3 import (
            ContributionReviewIntentV3,
            contribution_v3_payload_sha256,
            derive_review_intent_sha256_v3,
        )

        item = typed_candidate()
        raw = item.assertions[0].model_dump(mode="json")
        raw.update(
            assertion_id=PROPERTY_ID,
            assertion_kind="attribute",
            object_object_id=None,
            predicate=None,
            label=None,
            value=json.dumps(
                {
                    "schema_version": "dm_reviewed_property_literal_v1",
                    "property_term": "dnd5e:test_fact",
                    "value": VALUE,
                }
            ),
        )
        item.assertions.append(GraphContributionAssertionV3.model_validate(raw))
        old = typed_intent()
        fields = {
            name: getattr(old, name)
            for name in [
                "operation_id",
                "world_id",
                "campaign_id",
                "identity_proposals",
                "identity_verdicts",
                "reviewer_id",
                "reviewed_at",
            ]
        }
        fields.update(
            candidate_contribution=item,
            plan_ref=old.plan_ref.model_copy(
                update={"candidate_contribution_sha256": contribution_v3_payload_sha256(item)}
            ),
            assertion_verdicts=sorted(
                [
                    ContributionAssertionVerdict(
                        assertion_id=a.assertion_id, acceptance_state="accepted"
                    )
                    for a in item.assertions
                ],
                key=lambda a: a.assertion_id,
            ),
        )
        intent = ContributionReviewIntentV3(
            **fields, review_intent_sha256=derive_review_intent_sha256_v3(**fields)
        )
        # Existing V3 fixture accepts an intent only through its local receipt constructor.
        from dungeonmind.contracts.contribution_review_v3 import (
            CommitConfirmationReceiptV3,
            ContributionReviewSubmissionV3,
        )

        receipt = dict(
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
        state = build(
            ContributionReviewSubmissionV3(
                intent=intent, confirmation=CommitConfirmationReceiptV3.model_validate(receipt)
            )
        )
        result = materialize_finalized_review_v6(
            state,
            parent=_stored_parent(),
            graph_reader=_reader(),
            source_snapshot=source_snapshot(),
        )
    assert all(not obj["properties"] for obj in result.graph_payload["objects"])
