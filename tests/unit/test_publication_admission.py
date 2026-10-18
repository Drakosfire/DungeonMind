"""Owning memory admission and complete-set synthetic validator witnesses."""

import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from dungeonmind.application.contribution_review_v4 import _build_review_state
from dungeonmind.application.publication_admission import (
    InMemoryPublicationAdmissionRepository,
    PublicationAdmissionRegistry,
    source_projection,
)
from dungeonmind.application.review_materialization_v4 import materialize_finalized_review_v4
from dungeonmind.application.review_publication import publish_finalized_review
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.publication_admission import (
    PublicationAdmissionPolicyV1,
    PublicationAdmissionResultV1,
)
from dungeonmind.contracts.review_publication import (
    FinalizedReviewPublicationCommandV2,
    FinalizedReviewPublicationV2,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryContributionReviewRepository,
    InMemoryFinalizedReviewPublicationRepository,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from tests.unit.test_contribution_review_v2 import (
    REVIEWED_AT,
    WORLD_ID,
    _reader,
    _v6_parent_payload,
)
from tests.unit.test_contribution_review_v3 import source_snapshot
from tests.unit.test_contribution_review_v3_contract import typed_intent
from tests.unit.test_contribution_review_v4 import PROPERTY_ID, submission, upgrade_intent


def admission_policy(ref, *, validator_id="synthetic.complete-set", version="v1", catalogs=None):
    raw = dict(
        schema_version="dm_publication_admission_policy_v1",
        profile_ref=ref.model_dump(mode="json"),
        policy_id="policy:synthetic",
        validator_ref=dict(validator_id=validator_id, validator_version=version),
        catalog_refs=catalogs or [],
    )
    return PublicationAdmissionPolicyV1(**raw, policy_sha256=canonical_sha256(raw))


class SyntheticValidator:
    """Synthetic roles/lines/quantity/output checks; no D&D transfer certification."""

    def __init__(self, *, reason=None):
        self.calls = []
        self.reason = reason

    def validate(self, context, parent, child):
        assert type(context) is type(parent) is type(child) is bytes
        self.calls.append((context, parent, child))
        ctx, _before, after = map(json.loads, (context, parent, child))
        assert hashlib.sha256(parent).hexdigest() == ctx["parent_graph_payload_sha256"]
        assert hashlib.sha256(child).hexdigest() == ctx["child_graph_payload_sha256"]
        # All accepted facts, their exact role/line/evidence and catalog refs
        # remain available to one whole-set decision.
        prop = next(
            (a for a in ctx["accepted_assertions"] if a["assertion_id"] == PROPERTY_ID), None
        )
        reason = self.reason
        if reason is None and any(
            a["status"] != "active" for a in ctx["source_snapshot"]["artifacts"]
        ):
            reason = "domain_invalid"
        if reason is None and prop is None:
            reason = "domain_invalid"
        if reason is None:
            value = json.loads(prop["value"])["value"]
            if (
                type(value.get("count")) is not int
                or value["count"] != 2
                or prop["evidence_refs"][0]["source_span_ref_id"] != "paragraph:002"
            ):
                reason = "domain_invalid"
            elif ctx["catalog_refs"]:
                reason = "catalog_mismatch"
            else:
                properties = [
                    p
                    for o in after["objects"]
                    for p in o["properties"]
                    if p["assertion_metadata"]["assertion_id"] == PROPERTY_ID
                ]
                if len(properties) != 1 or properties[0]["value"] != value:
                    reason = "accepted_set_mismatch"
        return PublicationAdmissionResultV1(
            decision="reject" if reason else "accept", reason=reason or "accepted"
        )


def setup_memory(*, validator=None, protected=True, reject_property=False, new_candidate=None):
    authority = InMemoryPublicationAdmissionRepository()
    graph = InMemoryWorldGraphRepository(admission=authority)
    contributions = InMemoryContributionRepository(admission=authority)
    reviews = InMemoryContributionReviewRepository(contributions)
    sources = InMemorySourceRepository()
    snapshot = source_snapshot()
    for artifact in snapshot.artifacts.values():
        sources.put_artifact(artifact)
    for revision in snapshot.revisions.values():
        sources.put_revision(revision)
    payload = _v6_parent_payload()
    ref = SemanticProfileRef.model_validate(payload["semantic_profile"])
    policy = admission_policy(ref)
    if protected:
        authority.register(policy)
    graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["adoption:test"],
            graph_schema="dm_union_graph_v6",
            graph_payload=payload,
            created_at=REVIEWED_AT,
        )
    )
    parent = graph.get_revision(WORLD_ID, graph.get_head(WORLD_ID).head_revision_id)
    old = typed_intent()
    old.plan_ref = old.plan_ref.model_copy(
        update={
            "expected_parent_revision_id": parent.revision.revision_id,
            "base_graph_payload_sha256": parent.revision.graph_payload_sha256,
        }
    )
    intent = upgrade_intent(old, reject_property=reject_property, new_candidate=new_candidate)
    state = reviews.finalize(_build_review_state(submission(intent)))
    registry = (
        PublicationAdmissionRegistry((("synthetic.complete-set", "v1", validator),))
        if validator
        else None
    )
    publications = InMemoryFinalizedReviewPublicationRepository(
        reviews, graph, source_repository=sources, admission_registry=registry
    )
    materialization = materialize_finalized_review_v4(
        state, parent=parent, graph_reader=_reader(), source_snapshot=snapshot
    )
    body = materialization.graph_payload
    command = FinalizedReviewPublicationCommandV2(
        world_id=WORLD_ID,
        review_id=state.record.review_id,
        reviewed_contribution_id=state.record.reviewed_contribution_id,
        reviewed_contribution_sha256=state.record.reviewed_contribution_sha256,
        review_intent_sha256=state.record.review_intent_sha256,
        confirmation_id=state.record.confirmation_id,
        operation_id=state.record.operation_id,
        expected_parent_revision_id=parent.revision.revision_id,
        parent_graph_payload_sha256=parent.revision.graph_payload_sha256,
        expected_published_revision_id=compute_revision_id(
            world_id=WORLD_ID,
            parent_revision_id=parent.revision.revision_id,
            operation_ids=[state.record.operation_id],
            graph_schema="dm_union_graph_v6",
            graph_payload_sha256=canonical_sha256(body),
        ),
        graph_schema="dm_union_graph_v6",
        graph_payload=body,
        graph_payload_sha256=canonical_sha256(body),
        requested_published_at=REVIEWED_AT,
        admission_policy_ref=policy.reference,
        validator_ref=policy.validator_ref,
    )
    return SimpleNamespace(
        authority=authority,
        graph=graph,
        reviews=reviews,
        sources=sources,
        publications=publications,
        state=state,
        parent=parent,
        policy=policy,
        command=command,
        snapshot=snapshot,
    )


def counts(lane):
    return (
        len(lane.graph._revisions),
        len(lane.publications._records_by_review),
        lane.graph.get_head(WORLD_ID).head_revision_id,
    )


def test_memory_complete_set_atomic_admission_and_replay_without_validator():
    validator = SyntheticValidator()
    lane = setup_memory(validator=validator)
    receipt = lane.publications.publish(lane.command)
    assert isinstance(receipt, FinalizedReviewPublicationV2) and len(validator.calls) == 1
    assert len(receipt.admission_context.accepted_assertions) == sum(
        a.acceptance_state == "accepted" for a in lane.state.reviewed_contribution.assertions
    )
    assert lane.publications.publish(lane.command) == receipt and len(validator.calls) == 1
    restarted = InMemoryFinalizedReviewPublicationRepository(
        lane.reviews, lane.graph, source_repository=lane.sources
    )
    restarted._records_by_review = copy.deepcopy(lane.publications._records_by_review)
    restarted._records_by_operation = copy.deepcopy(lane.publications._records_by_operation)
    restarted._records_by_revision = copy.deepcopy(lane.publications._records_by_revision)
    assert restarted.get_for_review(WORLD_ID, lane.state.record.review_id) == receipt
    assert restarted.publish(lane.command) == receipt
    assert len(validator.calls) == 1


def test_application_selects_v2_using_durable_profile_policy():
    lane = setup_memory(validator=SyntheticValidator())
    receipt = publish_finalized_review(
        WORLD_ID,
        lane.state.record.review_id,
        published_at=REVIEWED_AT,
        review_repository=lane.reviews,
        world_graph_repository=lane.graph,
        publication_repository=lane.publications,
        graph_reader=_reader(),
    )
    assert isinstance(receipt, FinalizedReviewPublicationV2)


@pytest.mark.parametrize(
    "case",
    [
        "empty_registry",
        "wrong_version",
        "legacy",
        "exception",
        "unknown_result",
        "reject_role",
        "changed_profile",
        "raw_adoption",
        "failure_hook",
    ],
)
def test_protected_direct_failures_leave_zero_graph_head_receipt_writes(case):
    validator = SyntheticValidator()
    lane = setup_memory(validator=validator, reject_property=case == "reject_role")
    if case == "empty_registry":
        lane.publications._admission_registry = PublicationAdmissionRegistry()
    elif case == "wrong_version":
        lane.publications._admission_registry = PublicationAdmissionRegistry(
            (("synthetic.complete-set", "v2", validator),)
        )
    elif case == "legacy":
        from dungeonmind.contracts.review_publication import FinalizedReviewPublicationCommand

        raw = lane.command.model_dump(
            mode="python", exclude={"schema_version", "validator_ref", "admission_policy_ref"}
        )
        lane.command = FinalizedReviewPublicationCommand(**raw)
    elif case in ("exception", "unknown_result"):

        class Broken:
            def validate(self, *_):
                if case == "exception":
                    raise RuntimeError("secret campaign text")
                return {"decision": "accept", "reason": "accepted", "secret": "forbidden"}

        lane.publications._admission_registry = PublicationAdmissionRegistry(
            (("synthetic.complete-set", "v1", Broken()),)
        )
    elif case == "changed_profile":
        lane.command.graph_payload["semantic_profile"]["descriptor_sha256"] = "0" * 64
        lane.command.graph_payload_sha256 = canonical_sha256(lane.command.graph_payload)
        lane.command.expected_published_revision_id = compute_revision_id(
            world_id=WORLD_ID,
            parent_revision_id=lane.command.expected_parent_revision_id,
            operation_ids=[lane.command.operation_id],
            graph_schema=lane.command.graph_schema,
            graph_payload_sha256=lane.command.graph_payload_sha256,
        )
    elif case == "raw_adoption":
        lane.graph.publish_revision(
            PublishRevisionCommand(
                world_id=WORLD_ID,
                parent_revision_id=lane.command.expected_parent_revision_id,
                expected_parent_revision_id=lane.command.expected_parent_revision_id,
                operation_ids=[lane.command.operation_id],
                graph_schema=lane.command.graph_schema,
                graph_payload=lane.command.graph_payload,
                created_at=REVIEWED_AT,
            )
        )
    elif case == "failure_hook":
        lane.publications._failure_hook = lambda: (_ for _ in ()).throw(RuntimeError("after write"))
    before = counts(lane)
    with pytest.raises((PersistenceIntegrityError, RuntimeError)) as exc:
        lane.publications.publish(lane.command)
    assert counts(lane) == before
    assert "secret campaign text" not in str(exc.value)


def test_registration_first_use_exact_replay_conflicts_and_source_projection():
    lane = setup_memory()
    assert lane.authority.register(lane.policy) == lane.policy
    changed = admission_policy(lane.policy.profile_ref, version="v2")
    with pytest.raises(PersistenceIntegrityError):
        lane.authority.register(changed)
    legacy = setup_memory(protected=False)
    with pytest.raises(PersistenceIntegrityError):
        legacy.authority.register(legacy.policy)
    snapshot = source_projection(lane.snapshot).model_dump(mode="json")
    assert all(
        "locator" not in row and "uri" not in row
        for row in snapshot["artifacts"] + snapshot["revisions"]
    )
    assert snapshot["artifacts"][0]["workspace_document_ref"] is None


def test_source_withdrawal_does_not_recompute_historical_snapshot():
    lane = setup_memory(validator=SyntheticValidator())
    receipt = lane.publications.publish(lane.command)
    # Mutate today's authority only; receipt verification must keep its historical scope.
    key = next(iter(lane.sources._artifacts))
    lane.sources._artifacts[key].status = "retracted"
    assert lane.publications.get_for_review(WORLD_ID, lane.state.record.review_id) == receipt


def test_actual_graph_budget_refusal_has_exact_reason_and_zero_writes():
    from dungeonmind.contracts.publication_admission import GRAPH_BYTES

    lane = setup_memory(validator=SyntheticValidator())
    before = counts(lane)
    lane.command.graph_payload["limit-witness"] = "x" * GRAPH_BYTES
    with pytest.raises(PersistenceIntegrityError) as exc:
        lane.publications.publish(lane.command)
    assert exc.value.details["reason"] == "admission_context_limit_exceeded"
    assert counts(lane) == before


def test_complete_accepted_budget_one_over_refuses_at_owner_without_truncation():
    from dungeonmind.application.publication_admission import accepted_assertions
    from dungeonmind.contracts.publication_admission import ACCEPTED_BYTES, bounded_canonical
    from tests.unit.test_contribution_review_v4 import candidate

    value = candidate(
        kind="attribute"
    )  # historical provenance-only value has no property-literal cap
    value.assertions[0].value = json.dumps({"opaque": ""})
    baseline = setup_memory(validator=SyntheticValidator(), new_candidate=value)
    rows = accepted_assertions(baseline.state)
    remaining = ACCEPTED_BYTES - len(bounded_canonical(rows, max_bytes=ACCEPTED_BYTES))
    value.assertions[0].value = json.dumps({"opaque": "x" * (remaining + 1)})
    lane = setup_memory(validator=SyntheticValidator(), new_candidate=value)
    before = counts(lane)
    with pytest.raises(PersistenceIntegrityError) as exc:
        lane.publications.publish(lane.command)
    assert exc.value.details["reason"] == "admission_context_limit_exceeded"
    assert counts(lane) == before


def test_v1_source_projection_retains_decoded_defaults_and_explicit_absent_axes():
    from dungeonmind.application.source_provenance_snapshot import SourceProvenanceSnapshot
    from dungeonmind.contracts.evidence import SourceArtifact

    artifact = SourceArtifact(
        source_artifact_id="a:v1",
        world_id=WORLD_ID,
        source_domain="worldbuilding",
        created_at=REVIEWED_AT,
    )
    snapshot = SourceProvenanceSnapshot.from_loaded(
        requested_artifact_ids=frozenset({"a:v1"}),
        requested_revision_ids=frozenset(),
        artifacts={"a:v1": artifact},
        revisions={},
    )
    projected = source_projection(snapshot).artifacts[0]
    assert projected.authority == "primary" and projected.visibility == "gm"
    assert projected.source_schema_version == "dm_source_artifact_v1"
    for name in (
        "source_domain_key",
        "artifact_kind",
        "document_class",
        "review_state",
        "source_visibility_state",
        "workspace_document_ref",
    ):
        assert getattr(projected, name) is None
    # V2 nullable values remain null rather than receiving V1 defaults.
    snapshot = source_snapshot()
    record = next(iter(snapshot._artifacts.values()))
    record.authority = None
    record.visibility = None
    projected = source_projection(snapshot).artifacts[0]
    assert projected.authority is None and projected.visibility is None
