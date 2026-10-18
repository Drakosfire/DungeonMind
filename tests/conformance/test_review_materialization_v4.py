"""Property corrections/collisions fail before the local workspace is changed."""

import copy

import pytest

from dungeonmind.application.contribution_review_v4 import _build_review_state
from dungeonmind.application.review_materialization_v4 import (
    materialize_finalized_review_v4,
    validate_reviewed_property_delta_v4,
)
from dungeonmind.domain.errors import ContributionMaterializationError
from tests.unit.test_contribution_review_v2 import _reader, _stored_parent
from tests.unit.test_contribution_review_v3 import source_snapshot
from tests.unit.test_contribution_review_v4 import (
    PROPERTY_ID,
    candidate,
    materialize,
    submission,
    upgrade_intent,
)


def test_changed_post_review_property_payload_is_rejected():
    state = _build_review_state(submission())
    result = materialize(state)
    changed = copy.deepcopy(result.graph_payload)
    next(o for o in changed["objects"] if o["properties"])["properties"][0]["value"] = "changed"
    with pytest.raises(ContributionMaterializationError):
        validate_reviewed_property_delta_v4(
            state, parent=_stored_parent(), graph_payload=changed, source_snapshot=source_snapshot()
        )


def test_new_property_correction_is_refused_without_mutating_parent():
    item = candidate()
    from dungeonmind.contracts.contribution import GraphContributionAssertionCorrection

    item.assertion_corrections = [
        GraphContributionAssertionCorrection(
            **{
                "correction_kind": "contradicts",
                "target_contribution_id": "prior",
                "target_assertion_id": PROPERTY_ID,
            }
        )
    ]
    # Reparse the typed correction record, then obtain the real finalized state.
    from dungeonmind.contracts.contribution import GraphContributionV4

    item = GraphContributionV4.model_validate(item.model_dump(mode="json"))
    state = _build_review_state(submission(upgrade_intent(new_candidate=item)))
    parent = _stored_parent()
    before = parent.model_dump(mode="json")
    with pytest.raises(ContributionMaterializationError) as caught:
        materialize_finalized_review_v4(
            state, parent=parent, graph_reader=_reader(), source_snapshot=source_snapshot()
        )
    assert caught.value.details["reason"] == "property_correction_unsupported"
    assert parent.model_dump(mode="json") == before


def test_property_id_cannot_hijack_parent_or_generated_alias_facet():
    parent = _stored_parent()
    existing_id = parent.graph_payload["objects"][0]["assertion_metadata"]["assertion_id"]
    for conflict in [existing_id]:
        item = candidate()
        item.assertions[0].assertion_id = conflict
        old = upgrade_intent()
        from dungeonmind.contracts.contribution_review import ContributionAssertionVerdict

        fields = {
            k: getattr(old, k)
            for k in [
                "operation_id",
                "world_id",
                "campaign_id",
                "identity_proposals",
                "identity_verdicts",
                "reviewer_id",
                "reviewed_at",
            ]
        }
        from dungeonmind.contracts.contribution_review_v4 import (
            ContributionReviewIntentV4,
            contribution_v4_payload_sha256,
            derive_review_intent_sha256_v4,
        )

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
        with pytest.raises(ContributionMaterializationError) as caught:
            materialize(_build_review_state(submission(intent)))
        assert caught.value.details["reason"] == "cross_facet_assertion_collision"


@pytest.mark.parametrize("target_v4", [False, True])
def test_v4_withdraws_historical_v3_or_v4_description_with_original_proof(monkeypatch, target_v4):
    from dungeonmind.application.contribution_review_v4 import finalize_contribution_review_v4
    from dungeonmind.application.source_description_correction import (
        verify_source_description_corrections,
    )
    from tests.conformance import test_current_node_source_observations as n
    from tests.conformance import test_reviewed_source_observation_retrieval as f
    from tests.conformance import test_source_description_withdrawal as w
    from tests.unit.test_contribution_review_v4 import policy, version_intent

    if target_v4:
        monkeypatch.setattr(
            n,
            "_build_review_state",
            lambda sub: _build_review_state(submission(version_intent(sub.intent))),
        )
    service, graph, _sources, reviews, publications, prior, child = w.setup(monkeypatch)
    parent = graph.get_revision(f.WORLD_ID, child)
    intent = version_intent(w.withdrawal(prior, parent))
    state = finalize_contribution_review_v4(
        submission(intent),
        capability_policy=policy(intent),
        world_graph_repository=graph,
        review_repository=reviews,
    )
    proof = verify_source_description_corrections(
        state, parent=parent, world_graph=graph, reviews=reviews, publications=publications
    )
    assert proof.matches(state, parent)
    from dataclasses import replace

    from dungeonmind.application.review_materialization_v4 import materialize_finalized_review_v4

    for bad_proof in [
        None,
        replace(proof, _issuer=object()),
        replace(proof, contribution_sha256="f" * 64),
    ]:
        with pytest.raises(ContributionMaterializationError):
            materialize_finalized_review_v4(
                state,
                parent=parent,
                graph_reader=f._reader(),
                source_description_correction_proof=bad_proof,
            )
    forged_parent = parent.model_copy(
        update={"revision": parent.revision.model_copy(update={"revision_id": "wrong"})}
    )
    assert not proof.matches(state, forged_parent)
    receipt = w.publish(state, graph, reviews, publications)
    result = service.get_complete_object(f._request(receipt.published_revision_id), object_id=n.NEW)
    assert result.found and not result.reviewed_source_observations
    assert service.get_complete_object(
        f._request(child), object_id=n.NEW
    ).reviewed_source_observations
    assert w.publish(state, graph, reviews, publications) == receipt
    current = graph.get_revision(f.WORLD_ID, receipt.published_revision_id)
    again = version_intent(w.withdrawal(prior, current, suffix="b"))
    second = finalize_contribution_review_v4(
        submission(again),
        capability_policy=policy(again),
        world_graph_repository=graph,
        review_repository=reviews,
    )
    before = graph.get_head(f.WORLD_ID)
    with pytest.raises(ContributionMaterializationError) as caught:
        w.publish(second, graph, reviews, publications)
    assert caught.value.details["reason"] == "source_description_correction_already_withdrawn"
    assert graph.get_head(f.WORLD_ID) == before


def test_old_v3_withdrawal_authority_does_not_expand_to_v4_targets(monkeypatch):
    from tests.conformance import test_current_node_source_observations as n
    from tests.conformance import test_reviewed_source_observation_retrieval as f
    from tests.conformance import test_source_description_withdrawal as w
    from tests.unit.test_contribution_review_v4 import version_intent

    monkeypatch.setattr(
        n,
        "_build_review_state",
        lambda sub: _build_review_state(submission(version_intent(sub.intent))),
    )
    _, graph, _, reviews, publications, prior, child = w.setup(monkeypatch)
    parent = graph.get_revision(f.WORLD_ID, child)
    state = w.finalize(w.withdrawal(prior, parent), graph, reviews)
    before = graph.get_head(f.WORLD_ID)
    with pytest.raises(ContributionMaterializationError) as caught:
        w.publish(state, graph, reviews, publications)
    assert caught.value.details["reason"] == "source_description_correction_target_kind"
    assert graph.get_head(f.WORLD_ID) == before


def _complete_intent(item, parent):
    from dungeonmind.contracts.contribution_review import ContributionAssertionVerdict
    from dungeonmind.contracts.contribution_review_v4 import (
        ContributionReviewIntentV4,
        contribution_v4_payload_sha256,
        derive_review_intent_sha256_v4,
    )
    from tests.unit.test_contribution_review_v3_contract import typed_intent

    old = typed_intent()
    fields = {
        k: getattr(old, k)
        for k in [
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
            update={
                "candidate_contribution_sha256": contribution_v4_payload_sha256(item),
                "base_graph_payload_sha256": parent.revision.graph_payload_sha256,
            }
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
    return ContributionReviewIntentV4(
        **fields, review_intent_sha256=derive_review_intent_sha256_v4(**fields)
    )


def test_v4_nonproperty_correction_retains_historical_materialization_behavior():
    from dungeonmind.contracts.contribution import GraphContributionAssertionCorrection
    from dungeonmind.domain.canonical import canonical_sha256

    parent = _stored_parent().model_copy(deep=True)
    alias = parent.graph_payload["objects"][0]["aliases"][0]
    alias["assertion_metadata"]["assertion_id"] = "assertion:synthetic:parent:alias"
    parent.revision.graph_payload_sha256 = canonical_sha256(parent.graph_payload)
    item = candidate()
    item.assertion_corrections = [
        GraphContributionAssertionCorrection(
            correction_kind="contradicts",
            target_contribution_id="contrib:synthetic:parent",
            target_assertion_id="assertion:synthetic:parent:alias",
        )
    ]
    state = _build_review_state(submission(_complete_intent(item, parent)))
    result = materialize_finalized_review_v4(
        state, parent=parent, graph_reader=_reader(), source_snapshot=source_snapshot()
    )
    assert all(
        a["assertion_metadata"]["assertion_id"] != "assertion:synthetic:parent:alias"
        for a in result.graph_payload["objects"][0]["aliases"]
    )
    assert any(o["properties"] for o in result.graph_payload["objects"])


def test_parent_property_correction_and_generated_alias_collision_refused():
    from dungeonmind.contracts.contribution import GraphContributionAssertionCorrection
    from dungeonmind.domain.canonical import canonical_sha256

    parent = _stored_parent().model_copy(deep=True)
    parent.graph_payload = materialize(_build_review_state(submission())).graph_payload
    parent.revision.graph_payload_sha256 = canonical_sha256(parent.graph_payload)
    item = candidate()
    item.assertion_corrections = [
        GraphContributionAssertionCorrection(
            correction_kind="contradicts",
            target_contribution_id="contrib:synthetic:parent",
            target_assertion_id=PROPERTY_ID,
        )
    ]
    state = _build_review_state(submission(_complete_intent(item, parent)))
    with pytest.raises(ContributionMaterializationError) as caught:
        materialize_finalized_review_v4(
            state, parent=parent, graph_reader=_reader(), source_snapshot=source_snapshot()
        )
    assert caught.value.details["reason"] == "property_correction_unsupported"
    item = candidate()
    node = next(a for a in item.assertions if a.assertion_kind == "node")
    item.assertions[0].assertion_id = node.assertion_id + ":alias:" + node.label
    state = _build_review_state(submission(_complete_intent(item, _stored_parent())))
    with pytest.raises(ContributionMaterializationError) as caught:
        materialize(state)
    assert caught.value.details["reason"] == "cross_facet_assertion_collision"
