"""V2 finalized contribution-review contracts, finalize service, and v6 materialization.

These tests pin the ``dm_contribution_review_intent_v2`` family and the
``dm_union_graph_v6`` materializer that Buddy's whole-world authority transfer
drives (ADR-0020).  Fixtures are self-contained: a minimal synthetic v6 parent
payload under the builtin dnd semantic profile.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dungeonmind.application.contribution_review_v2 import (
    _build_review_state,
    finalize_contribution_review_v2,
)
from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V6,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.review_materialization_v6 import (
    materialize_finalized_review_v6,
)
from dungeonmind.application.semantic_profiles import descriptor_sha256
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
    GraphContributionAssertionCorrection,
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
from dungeonmind.contracts.graph import StoredGraphRevision, WorldGraphHead
from dungeonmind.contracts.identity import IdentityOutcome
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    CapabilityDeniedError,
    ContributionMaterializationError,
    ContributionReviewValidationError,
    IdempotencyConflictError,
    StaleParentRevisionError,
)
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryContributionReviewRepository,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.world_object_vocabulary import (
    load_builtin_v3_descriptor,
)

WORLD_ID = "eldyrwild"
CAMPAIGN_ID = "longmont-c2"
REVIEWER_ID = "gm:test"
REVIEWED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
OPERATION_ID = "reviewop:" + "0" * 32

PROFILE = SemanticProfileRef(
    profile_id="dungeonmind.dnd5e",
    profile_revision="dnd5e-profile-v3",
    descriptor_sha256="2199e8fb96e917c22718e6aec59cbbf55a37ee81575e1bcf16ce13fae0393496",
)

EXISTING_OBJECT_ID = "npc:existing_npc"
SECOND_OBJECT_ID = "location:existing_location"
NEW_OBJECT_ID = "npc:new_npc"
EXISTING_EVIDENCE_ID = "evidence:artifact:recap:longmont-c2:session-1:paragraph:001"


def _reader() -> VersionedUnionGraphSnapshotReader:
    descriptor = load_builtin_v3_descriptor()
    assert descriptor_sha256(descriptor) == PROFILE.descriptor_sha256
    return VersionedUnionGraphSnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )


def _existence_metadata(assertion_id: str, evidence_ids: list[str]) -> dict[str, object]:
    return {
        "assertion_id": assertion_id,
        "campaign_scope": CAMPAIGN_ID,
        "visibility": "gm",
        "epistemic_kind": "fact",
        "canon_state": "canonical",
        "evidence_ref_ids": evidence_ids,
        "session_refs": [],
        "temporal_scope": {"kind": "unknown", "fictional_time_ref": None},
    }


def _v6_parent_payload() -> dict[str, object]:
    from dungeonmind.application.graph_snapshot_v6 import UnionGraphV6Payload

    raw = {
        "world_id": WORLD_ID,
        "semantic_profile": PROFILE.model_dump(mode="json"),
        "relationship_endpoint_aspect_schema": "dm_relationship_endpoint_aspect_v1",
        "objects": [
            {
                "object_id": EXISTING_OBJECT_ID,
                "kind": "dnd5e:npc",
                "label": "Existing NPC",
                "assertion_metadata": _existence_metadata(
                    "ka:object:npc:existing_npc", [EXISTING_EVIDENCE_ID]
                ),
                "aliases": [
                    {
                        "value": "The Existing One",
                        "assertion_metadata": _existence_metadata(
                            "ka:alias:npc:existing_npc:0", [EXISTING_EVIDENCE_ID]
                        ),
                    }
                ],
                "summary": None,
                "properties": [],
                "aspects": [],
            },
            {
                "object_id": SECOND_OBJECT_ID,
                "kind": "dnd5e:location",
                "label": "Existing Location",
                "assertion_metadata": _existence_metadata(
                    "ka:object:location:existing_location", [EXISTING_EVIDENCE_ID]
                ),
                "aliases": [],
                "summary": None,
                "properties": [],
                "aspects": [],
            },
        ],
        "relationships": [],
        "evidence_refs": [
            {
                "evidence_ref_id": EXISTING_EVIDENCE_ID,
                "source_artifact_id": "artifact:recap:longmont-c2:session-1",
                "source_revision_id": None,
                "source_domain_key": "session_recap",
                "source_domain": "session_recap",
                "evidence_role": "support",
                "can_open_source": True,
                "can_highlight_span": True,
                "session_id": None,
                "source_span_ref_id": None,
                "locator": "paragraph:001",
                "uri": None,
                "source_locator": None,
                "line_ref": None,
            }
        ],
    }
    # Normalize through the payload model so the fixture is exactly the
    # materialized shape (all schema_version defaults present), matching what
    # the adoption path stores and what the materializer round-trip requires.
    return UnionGraphV6Payload.model_validate(raw).model_dump(mode="json")


def _stored_parent() -> StoredGraphRevision:
    payload = _v6_parent_payload()
    digest = canonical_sha256(payload)
    revision_id = compute_revision_id(
        world_id=WORLD_ID,
        parent_revision_id=None,
        operation_ids=["adoption:test"],
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload_sha256=digest,
    )
    from dungeonmind.contracts.graph import WorldGraphRevision

    return StoredGraphRevision(
        revision=WorldGraphRevision(
            world_id=WORLD_ID,
            revision_id=revision_id,
            parent_revision_id=None,
            created_at=REVIEWED_AT,
            operation_ids=["adoption:test"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload_sha256=digest,
        ),
        graph_payload=payload,
    )


def _evidence(evidence_ref_id: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_ref_id=evidence_ref_id,
        source_artifact_id="artifact:recap:longmont-c2:session-2",
        source_domain=SourceDomain.SESSION_RECAP,
        evidence_role=EvidenceRole.SUPPORT,
        can_open_source=True,
        can_highlight_span=True,
        locator="paragraph:002",
    )


def _candidate() -> GraphContributionV2:
    return GraphContributionV2(
        contribution_id="contrib:" + "a" * 32,
        world_id=WORLD_ID,
        source_kind=ContributionSourceKind.GRAPH_REVIEW,
        produced_at=REVIEWED_AT,
        authored_by="buddy:test",
        campaign_scope=CAMPAIGN_ID,
        source_artifact_id="artifact:recap:longmont-c2:session-2",
        assertions=[
            GraphContributionAssertionV2(
                assertion_id="assertion:test:node:new",
                assertion_kind="node",
                subject_object_id=NEW_OBJECT_ID,
                label="New NPC",
                value=(
                    '{"dm_kind": "dnd5e:npc", "kind": "npc",'
                    ' "aliases": ["New NPC", "The Newcomer"]}'
                ),
                evidence_refs=[_evidence("evidence:new:node")],
                campaign_scope=CAMPAIGN_ID,
            ),
            GraphContributionAssertionV2(
                assertion_id="assertion:test:alias:existing",
                assertion_kind="alias",
                subject_object_id=EXISTING_OBJECT_ID,
                label="The Familiar",
                evidence_refs=[_evidence("evidence:new:alias")],
                campaign_scope=CAMPAIGN_ID,
            ),
            GraphContributionAssertionV2(
                assertion_id="assertion:test:edge:new",
                assertion_kind="edge",
                subject_object_id=NEW_OBJECT_ID,
                object_object_id=EXISTING_OBJECT_ID,
                predicate="knows_about",
                value='{"dm_predicate": "dnd5e:knows_about"}',
                evidence_refs=[_evidence("evidence:new:edge")],
                campaign_scope=CAMPAIGN_ID,
            ),
            GraphContributionAssertionV2(
                assertion_id="assertion:test:attribute:existing",
                assertion_kind="attribute",
                subject_object_id=EXISTING_OBJECT_ID,
                value='{"attribute": "disposition", "detail": "wary"}',
                evidence_refs=[_evidence("evidence:new:attribute")],
                campaign_scope=CAMPAIGN_ID,
            ),
        ],
    )


def _proposals() -> list[ContributionIdentityProposal]:
    return [
        ContributionIdentityProposal(
            candidate_id="cand:existing",
            candidate_kind="dnd5e:npc",
            planned_outcome=IdentityOutcome.RESOLVED_EXISTING,
            target_object_id=EXISTING_OBJECT_ID,
            matched_object_ids=[EXISTING_OBJECT_ID],
        ),
        ContributionIdentityProposal(
            candidate_id="cand:new",
            candidate_kind="dnd5e:npc",
            planned_outcome=IdentityOutcome.PROVISIONAL_NEW,
            target_object_id=NEW_OBJECT_ID,
        ),
    ]


def _identity_verdicts() -> list[ContributionIdentityVerdict]:
    return [
        ContributionIdentityVerdict(
            candidate_id="cand:existing",
            verdict=ContributionIdentityVerdictKind.CONFIRM_EXISTING,
            target_object_id=EXISTING_OBJECT_ID,
        ),
        ContributionIdentityVerdict(
            candidate_id="cand:new",
            verdict=ContributionIdentityVerdictKind.CREATE_NEW,
            target_object_id=NEW_OBJECT_ID,
        ),
    ]


def _assertion_verdicts(
    candidate: GraphContributionV2,
) -> list[ContributionAssertionVerdict]:
    return [
        ContributionAssertionVerdict(
            assertion_id=assertion.assertion_id,
            acceptance_state=AcceptanceState.ACCEPTED,
        )
        for assertion in sorted(candidate.assertions, key=lambda assertion: assertion.assertion_id)
    ]


def _plan_ref(candidate: GraphContributionV2, parent: StoredGraphRevision) -> ContributionPlanRef:
    return ContributionPlanRef(
        source_plan_schema="dmb_extract_promote_review_package_v1",
        source_plan_id="plan:test",
        source_plan_sha256="1" * 64,
        source_input_sha256="2" * 64,
        preview_content_sha256="3" * 64,
        candidate_contribution_sha256=contribution_v2_payload_sha256(candidate),
        expected_parent_revision_id=parent.revision.revision_id,
        base_graph_schema=GRAPH_SCHEMA_V6,
        base_graph_payload_sha256=parent.revision.graph_payload_sha256,
        semantic_profile=PROFILE,
    )


def _intent(
    *,
    candidate: GraphContributionV2 | None = None,
    parent: StoredGraphRevision | None = None,
    identity_proposals: list[ContributionIdentityProposal] | None = None,
    identity_verdicts: list[ContributionIdentityVerdict] | None = None,
    assertion_verdicts: list[ContributionAssertionVerdict] | None = None,
    operation_id: str = OPERATION_ID,
) -> ContributionReviewIntentV2:
    candidate = candidate or _candidate()
    parent = parent or _stored_parent()
    plan_ref = _plan_ref(candidate, parent)
    identity_proposals = _proposals() if identity_proposals is None else identity_proposals
    identity_verdicts = _identity_verdicts() if identity_verdicts is None else identity_verdicts
    assertion_verdicts = (
        _assertion_verdicts(candidate) if assertion_verdicts is None else assertion_verdicts
    )
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


def _submission(intent: ContributionReviewIntentV2 | None = None) -> ContributionReviewSubmissionV2:
    intent = intent or _intent()
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


def _policy(
    intent: ContributionReviewIntentV2, *, revision_pin: str | None = None
) -> CapabilityPolicy:
    return CapabilityPolicy(
        policy_id="pol:v2-review",
        graph_scope=GraphScope(
            world_id=intent.world_id,
            campaign_id=intent.campaign_id,
            admissibility=Admissibility.GM,
            revision_pin=(
                revision_pin
                if revision_pin is not None
                else intent.plan_ref.expected_parent_revision_id
            ),
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


class _GraphRepository:
    def __init__(self, parent: StoredGraphRevision, *, head_revision_id: str | None = None) -> None:
        self.parent = parent
        self.head_revision_id = head_revision_id or parent.revision.revision_id

    def get_head(self, world_id: str) -> WorldGraphHead:
        return WorldGraphHead(
            world_id=world_id,
            head_revision_id=self.head_revision_id,
            updated_at=REVIEWED_AT,
        )

    def get_revision(self, world_id: str, revision_id: str):
        return self.parent if revision_id == self.parent.revision.revision_id else None


def _repositories() -> tuple[InMemoryContributionReviewRepository, InMemoryContributionRepository]:
    contributions = InMemoryContributionRepository()
    return InMemoryContributionReviewRepository(contributions), contributions


def _finalize(
    intent: ContributionReviewIntentV2 | None = None,
    *,
    parent: StoredGraphRevision | None = None,
    reviews: InMemoryContributionReviewRepository | None = None,
) -> ContributionReviewStateV2:
    intent = intent or _intent()
    parent = parent or _stored_parent()
    if reviews is None:
        reviews, _ = _repositories()
    return finalize_contribution_review_v2(
        _submission(intent),
        capability_policy=_policy(intent),
        world_graph_repository=_GraphRepository(parent),
        review_repository=reviews,
    )


# ---------------------------------------------------------------------------
# Contract invariants
# ---------------------------------------------------------------------------


def test_v2_intent_digest_binds_complete_content() -> None:
    payload = _intent().model_dump(mode="json")
    payload["candidate_contribution"]["assertions"][0]["label"] = "tampered"
    with pytest.raises(ValidationError):
        ContributionReviewIntentV2.model_validate(payload)


def test_v2_intent_rejects_non_v6_base_schema() -> None:
    candidate = _candidate()
    parent = _stored_parent()
    plan_ref = _plan_ref(candidate, parent).model_copy(
        update={"base_graph_schema": "dm_union_graph_v3"}
    )
    digest = derive_review_intent_sha256_v2(
        operation_id=OPERATION_ID,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        plan_ref=plan_ref,
        candidate_contribution=candidate,
        identity_proposals=_proposals(),
        identity_verdicts=_identity_verdicts(),
        assertion_verdicts=_assertion_verdicts(candidate),
        reviewer_id=REVIEWER_ID,
        reviewed_at=REVIEWED_AT,
    )
    with pytest.raises(ValidationError):
        ContributionReviewIntentV2(
            operation_id=OPERATION_ID,
            world_id=WORLD_ID,
            campaign_id=CAMPAIGN_ID,
            plan_ref=plan_ref,
            candidate_contribution=candidate,
            identity_proposals=_proposals(),
            identity_verdicts=_identity_verdicts(),
            assertion_verdicts=_assertion_verdicts(candidate),
            reviewer_id=REVIEWER_ID,
            reviewed_at=REVIEWED_AT,
            review_intent_sha256=digest,
        )


def test_v2_intent_rejects_unknown_kind_with_accepted_verdict() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][0]["assertion_kind"] = "statblock_binding"
    candidate = GraphContributionV2.model_validate(candidate_payload)
    with pytest.raises(ValidationError):
        _intent(candidate=candidate)


def test_v2_intent_allows_unknown_kind_with_rejected_verdict() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][0]["assertion_kind"] = "statblock_binding"
    candidate_payload["assertions"][0]["subject_object_id"] = None
    candidate = GraphContributionV2.model_validate(candidate_payload)
    verdicts = [
        ContributionAssertionVerdict(
            assertion_id=verdict.assertion_id,
            acceptance_state=(
                AcceptanceState.REJECTED
                if verdict.assertion_id == candidate.assertions[0].assertion_id
                else AcceptanceState.ACCEPTED
            ),
        )
        for verdict in _assertion_verdicts(candidate)
    ]
    # The rejected unknown-kind assertion's node target no longer exists, so
    # the create_new proposal for it must be dropped as well.
    intent = _intent(
        candidate=candidate,
        assertion_verdicts=verdicts,
        identity_proposals=[_proposals()[0]],
        identity_verdicts=[_identity_verdicts()[0]],
    )
    rejected = {verdict.assertion_id: verdict for verdict in intent.assertion_verdicts}
    assert (
        rejected[candidate.assertions[0].assertion_id].acceptance_state is AcceptanceState.REJECTED
    )


def test_v2_intent_rejects_identity_proposal_coverage_drift() -> None:
    candidate = _candidate()
    with pytest.raises(ValidationError):
        _intent(candidate=candidate, identity_proposals=[_proposals()[0]])


def test_v2_intent_rejects_candidate_without_evidence_or_source() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][3]["evidence_refs"] = []
    candidate_payload["assertions"][3]["source_artifact_id"] = None
    candidate_payload["assertions"][3]["source_revision_id"] = None
    candidate = GraphContributionV2.model_validate(candidate_payload)
    with pytest.raises(ValidationError):
        _intent(candidate=candidate)


def test_v2_submission_receipt_binds_intent() -> None:
    payload = _submission().model_dump(mode="json")
    payload["confirmation"]["review_intent_sha256"] = "f" * 64
    with pytest.raises(ValidationError):
        ContributionReviewSubmissionV2.model_validate(payload)


def test_v2_state_rejects_assertion_content_drift() -> None:
    state = _build_review_state(_submission())
    payload = copy.deepcopy(state.model_dump(mode="json"))
    payload["reviewed_contribution"]["assertions"][0]["label"] = "tampered"
    with pytest.raises(ValidationError):
        ContributionReviewStateV2.model_validate(payload)


def test_v2_state_rejects_reviewed_source_kind_drift() -> None:
    state = _build_review_state(_submission())
    payload = copy.deepcopy(state.model_dump(mode="json"))
    payload["reviewed_contribution"]["source_kind"] = "extraction"
    with pytest.raises(ValidationError):
        ContributionReviewStateV2.model_validate(payload)


def test_v2_state_preserves_candidate_provenance_fields() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["unresolved_mentions"] = ["the brewer"]
    candidate_payload["diagnostics"] = {"review_surface": "test"}
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    assert state.reviewed_contribution.unresolved_mentions == candidate.unresolved_mentions
    assert state.reviewed_contribution.diagnostics == candidate.diagnostics
    assert state.reviewed_contribution.source_kind is candidate.source_kind


def test_v2_state_rejects_correction_drift() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertion_corrections"] = [
        {
            "target_contribution_id": "contrib:" + "b" * 32,
            "target_assertion_id": "assertion:old:alias",
            "correction_kind": "contradicts_and_replaces",
            "replacement_assertion_id": "assertion:test:alias:existing",
        }
    ]
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    assert state.reviewed_contribution.assertion_corrections == [
        GraphContributionAssertionCorrection.model_validate(
            candidate_payload["assertion_corrections"][0]
        )
    ]
    payload = copy.deepcopy(state.model_dump(mode="json"))
    payload["reviewed_contribution"]["assertion_corrections"][0]["target_assertion_id"] = (
        "assertion:tampered"
    )
    with pytest.raises(ValidationError):
        ContributionReviewStateV2.model_validate(payload)


# ---------------------------------------------------------------------------
# Finalize service
# ---------------------------------------------------------------------------


def test_finalize_v2_persists_candidate_and_reviewed_successor() -> None:
    intent = _intent()
    reviews, contributions = _repositories()
    state = finalize_contribution_review_v2(
        _submission(intent),
        capability_policy=_policy(intent),
        world_graph_repository=_GraphRepository(_stored_parent()),
        review_repository=reviews,
    )
    assert state.record.status == "finalized"
    assert state.candidate_contribution.status.value == "superseded"
    assert state.reviewed_contribution.status.value == "active"
    assert state.reviewed_contribution.source_kind is ContributionSourceKind.GRAPH_REVIEW
    assert state.reviewed_contribution.supersedes_contribution_id == (
        state.candidate_contribution.contribution_id
    )
    node = state.reviewed_contribution.assertions[0]
    assert node.identity_resolution_outcome is IdentityOutcome.CREATED_NEW
    alias = state.reviewed_contribution.assertions[1]
    assert alias.identity_resolution_outcome is IdentityOutcome.RESOLVED_EXISTING
    edge = state.reviewed_contribution.assertions[2]
    assert edge.identity_resolution_outcome is None
    assert len(contributions.list_for_world(intent.world_id)) == 2
    reloaded = reviews.get(intent.world_id, state.record.review_id)
    assert reloaded == state


def test_finalize_v2_exact_replay_returns_same_state() -> None:
    intent = _intent()
    reviews, contributions = _repositories()
    parent = _stored_parent()
    first = _finalize(intent, parent=parent, reviews=reviews)
    second = _finalize(intent, parent=parent, reviews=reviews)
    assert second == first
    assert len(contributions.list_for_world(intent.world_id)) == 2


def test_finalize_v2_same_operation_changed_payload_conflicts() -> None:
    intent = _intent()
    reviews, _ = _repositories()
    parent = _stored_parent()
    _finalize(intent, parent=parent, reviews=reviews)
    changed_verdicts = _assertion_verdicts(_candidate())
    changed_verdicts[2] = ContributionAssertionVerdict(
        assertion_id=changed_verdicts[2].assertion_id,
        acceptance_state=AcceptanceState.REJECTED,
    )
    changed = _intent(assertion_verdicts=changed_verdicts)
    with pytest.raises(IdempotencyConflictError):
        _finalize(changed, parent=parent, reviews=reviews)


def test_finalize_v2_stale_head_is_rejected_before_persistence() -> None:
    intent = _intent()
    reviews, contributions = _repositories()
    parent = _stored_parent()
    with pytest.raises(StaleParentRevisionError):
        finalize_contribution_review_v2(
            _submission(intent),
            capability_policy=_policy(intent),
            world_graph_repository=_GraphRepository(parent, head_revision_id="rev:stale"),
            review_repository=reviews,
        )
    assert contributions.list_for_world(intent.world_id) == []


def test_finalize_v2_missing_revision_pin_is_denied() -> None:
    intent = _intent()
    reviews, _ = _repositories()
    with pytest.raises(CapabilityDeniedError):
        finalize_contribution_review_v2(
            _submission(intent),
            capability_policy=_policy(intent, revision_pin="rev:other"),
            world_graph_repository=_GraphRepository(_stored_parent()),
            review_repository=reviews,
        )


def test_finalize_v2_rejected_candidate_must_close_dependent_assertions() -> None:
    candidate = _candidate()
    # reject the new node's identity but leave its node assertion accepted
    intent = _intent(
        candidate=candidate,
        identity_verdicts=[
            _identity_verdicts()[0],
            ContributionIdentityVerdict(
                candidate_id="cand:new",
                verdict=ContributionIdentityVerdictKind.REJECT_CANDIDATE,
                target_object_id=NEW_OBJECT_ID,
            ),
        ],
    )
    reviews, _ = _repositories()
    with pytest.raises(ContributionReviewValidationError):
        finalize_contribution_review_v2(
            _submission(intent),
            capability_policy=_policy(intent),
            world_graph_repository=_GraphRepository(_stored_parent()),
            review_repository=reviews,
        )


# ---------------------------------------------------------------------------
# V6 materialization
# ---------------------------------------------------------------------------


def _materialize(state: ContributionReviewStateV2 | None = None):
    parent = _stored_parent()
    return parent, materialize_finalized_review_v6(
        state or _build_review_state(_submission(_intent(parent=parent))),
        parent=parent,
        graph_reader=_reader(),
    )


def test_v6_materialization_creates_updates_and_derives_ids() -> None:
    parent, result = _materialize()
    assert result.graph_schema == GRAPH_SCHEMA_V6
    assert result.expected_parent_revision_id == parent.revision.revision_id
    payload = result.graph_payload
    assert canonical_sha256(payload) == result.graph_payload_sha256

    objects = {obj["object_id"]: obj for obj in payload["objects"]}
    assert set(objects) == {EXISTING_OBJECT_ID, SECOND_OBJECT_ID, NEW_OBJECT_ID}
    created = objects[NEW_OBJECT_ID]
    assert created["kind"] == "dnd5e:npc"
    assert created["label"] == "New NPC"
    assert created["assertion_metadata"]["assertion_id"] == "assertion:test:node:new"
    assert created["assertion_metadata"]["evidence_ref_ids"] == ["evidence:new:node"]
    assert [alias["value"] for alias in created["aliases"]] == ["New NPC", "The Newcomer"]

    existing = objects[EXISTING_OBJECT_ID]
    assert existing["kind"] == "dnd5e:npc"
    assert existing["label"] == "Existing NPC"
    assert [alias["value"] for alias in existing["aliases"]] == [
        "The Existing One",
        "The Familiar",
    ]
    assert existing["aliases"][1]["assertion_metadata"]["assertion_id"] == (
        "assertion:test:alias:existing"
    )
    assert EXISTING_EVIDENCE_ID in existing["assertion_metadata"]["evidence_ref_ids"]
    assert "evidence:new:alias" in existing["assertion_metadata"]["evidence_ref_ids"]

    relationships = {rel["relationship_id"]: rel for rel in payload["relationships"]}
    edge_id = f"edge:{NEW_OBJECT_ID}:knows_about:{EXISTING_OBJECT_ID}"
    assert edge_id in relationships
    edge = relationships[edge_id]
    assert edge["predicate"] == "dnd5e:knows_about"
    assert edge["source_object_id"] == NEW_OBJECT_ID
    assert edge["target_object_id"] == EXISTING_OBJECT_ID
    assert edge["assertion_metadata"]["assertion_id"] == "assertion:test:edge:new"

    evidence_ids = {record["evidence_ref_id"] for record in payload["evidence_refs"]}
    assert evidence_ids == {
        EXISTING_EVIDENCE_ID,
        "evidence:new:node",
        "evidence:new:alias",
        "evidence:new:edge",
        "evidence:new:attribute",
    }
    lifted = {record["evidence_ref_id"]: record for record in payload["evidence_refs"]}
    assert lifted["evidence:new:node"]["source_domain_key"] == "session_recap"
    assert lifted["evidence:new:node"]["locator"] == "paragraph:002"

    # The output payload reparses under the pinned profile.
    snapshot = _reader().parse(graph_schema=GRAPH_SCHEMA_V6, graph_payload=payload)
    assert NEW_OBJECT_ID in snapshot.objects


def test_v6_materialization_explicit_edge_id_is_preserved() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][2]["value"] = (
        '{"dm_predicate": "dnd5e:knows_about", "edge_id": "edge:custom:1"}'
    )
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    _, result = _materialize(state)
    relationship_ids = {rel["relationship_id"] for rel in result.graph_payload["relationships"]}
    assert relationship_ids == {"edge:custom:1"}


def test_v6_materialization_missing_qualified_kind_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][0]["value"] = '{"kind": "npc"}'
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "missing_qualified_kind"


def test_v6_materialization_missing_qualified_predicate_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][2]["value"] = "{}"
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "missing_qualified_predicate"


def test_v6_materialization_unqualified_terms_fail_output_validation() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][0]["value"] = '{"dm_kind": "notaprofile:npc", "kind": "npc"}'
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "output_graph_validation"


def test_v6_materialization_edge_id_collision_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    # A second edge assertion reusing the same derived id with a different
    # qualified predicate must fail closed, not silently merge.
    second_edge = copy.deepcopy(candidate_payload["assertions"][2])
    second_edge["assertion_id"] = "assertion:test:edge:second"
    second_edge["value"] = '{"dm_predicate": "dnd5e:allied_with"}'
    candidate_payload["assertions"].append(second_edge)
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "relationship_id_collision"


def test_v6_materialization_exact_duplicate_edge_is_replay_safe() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    duplicate = copy.deepcopy(candidate_payload["assertions"][2])
    duplicate["assertion_id"] = "assertion:test:edge:duplicate"
    candidate_payload["assertions"].append(duplicate)
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    _, result = _materialize(state)
    assert len(result.graph_payload["relationships"]) == 1


def test_v6_materialization_correction_removes_alias_record() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertion_corrections"] = [
        {
            "target_contribution_id": "contrib:" + "b" * 32,
            "target_assertion_id": "ka:alias:npc:existing_npc:0",
            "correction_kind": "contradicts_and_replaces",
            "replacement_assertion_id": "assertion:test:alias:existing",
        }
    ]
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    _, result = _materialize(state)
    objects = {obj["object_id"]: obj for obj in result.graph_payload["objects"]}
    assert [alias["value"] for alias in objects[EXISTING_OBJECT_ID]["aliases"]] == ["The Familiar"]


def test_v6_materialization_correction_on_existence_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertion_corrections"] = [
        {
            "target_contribution_id": "contrib:" + "b" * 32,
            "target_assertion_id": "ka:object:npc:existing_npc",
            "correction_kind": "contradicts_and_replaces",
            "replacement_assertion_id": "assertion:test:node:new",
        }
    ]
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "correction_target_existence"


def test_v6_materialization_unresolvable_correction_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertion_corrections"] = [
        {
            "target_contribution_id": "contrib:" + "b" * 32,
            "target_assertion_id": "assertion:does:not:exist",
            "correction_kind": "contradicts_and_replaces",
            "replacement_assertion_id": "assertion:test:node:new",
        }
    ]
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "correction_target_unresolvable"


def test_v6_materialization_non_mutating_outcome_is_skipped() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][3]["identity_resolution_outcome"] = "ambiguous"
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    _, result = _materialize(state)
    evidence_ids = {record["evidence_ref_id"] for record in result.graph_payload["evidence_refs"]}
    assert "evidence:new:attribute" not in evidence_ids


def test_v6_materialization_evidence_fallback_synthesis() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    # Source-identity-only node assertion: valid for the contract, and the
    # materializer synthesizes the contribution-scoped fallback evidence.
    candidate_payload["assertions"][0]["evidence_refs"] = []
    candidate_payload["assertions"][0]["source_artifact_id"] = (
        "artifact:recap:longmont-c2:session-2"
    )
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    _, result = _materialize(state)
    objects = {obj["object_id"]: obj for obj in result.graph_payload["objects"]}
    reviewed_id = state.reviewed_contribution.contribution_id
    fallback_id = f"evidence:{reviewed_id}:{NEW_OBJECT_ID}"
    assert objects[NEW_OBJECT_ID]["assertion_metadata"]["evidence_ref_ids"] == [fallback_id]
    evidence = {
        record["evidence_ref_id"]: record for record in result.graph_payload["evidence_refs"]
    }
    assert evidence[fallback_id]["source_artifact_id"] == ("artifact:recap:longmont-c2:session-2")
    assert evidence[fallback_id]["source_domain_key"] == "manual_seed"


def test_v6_materialization_alias_without_evidence_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][1]["evidence_refs"] = []
    candidate_payload["assertions"][1]["source_artifact_id"] = None
    candidate_payload["assertions"][1]["source_revision_id"] = None
    candidate = GraphContributionV2.model_validate(candidate_payload)
    with pytest.raises(ValidationError):
        _intent(candidate=candidate)


def test_v6_materialization_reuses_identical_parent_evidence() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][1]["evidence_refs"] = [
        {
            "evidence_ref_id": EXISTING_EVIDENCE_ID,
            "source_artifact_id": "artifact:recap:longmont-c2:session-1",
            "source_domain": "session_recap",
            "evidence_role": "support",
            "can_open_source": True,
            "can_highlight_span": True,
            "locator": "paragraph:001",
            "uri": None,
        }
    ]
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    _, result = _materialize(state)
    evidence_ids = [record["evidence_ref_id"] for record in result.graph_payload["evidence_refs"]]
    assert evidence_ids.count(EXISTING_EVIDENCE_ID) == 1


def test_v6_materialization_conflicting_parent_evidence_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][1]["evidence_refs"] = [
        {
            "evidence_ref_id": EXISTING_EVIDENCE_ID,
            "source_artifact_id": "artifact:recap:longmont-c2:session-1",
            "source_domain": "session_recap",
            "evidence_role": "contradiction",
            "can_open_source": True,
            "can_highlight_span": True,
            "locator": "paragraph:001",
            "uri": None,
        }
    ]
    candidate = GraphContributionV2.model_validate(candidate_payload)
    state = _build_review_state(_submission(_intent(candidate=candidate)))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "accepted_evidence_conflict"


def test_v6_materialization_create_new_on_existing_object_fails_closed() -> None:
    candidate_payload = _candidate().model_dump(mode="json")
    candidate_payload["assertions"][0]["subject_object_id"] = EXISTING_OBJECT_ID
    candidate = GraphContributionV2.model_validate(candidate_payload)
    # Node and alias assertions now both target the existing object, so the
    # single identity proposal covers it — but with a create_new verdict,
    # which the materializer must refuse against the existing parent object.
    proposals = [
        ContributionIdentityProposal(
            candidate_id="cand:clash",
            candidate_kind="dnd5e:npc",
            planned_outcome=IdentityOutcome.PROVISIONAL_NEW,
            target_object_id=EXISTING_OBJECT_ID,
        )
    ]
    verdicts = [
        ContributionIdentityVerdict(
            candidate_id="cand:clash",
            verdict=ContributionIdentityVerdictKind.CREATE_NEW,
            target_object_id=EXISTING_OBJECT_ID,
        )
    ]
    intent = _intent(
        candidate=candidate,
        identity_proposals=proposals,
        identity_verdicts=verdicts,
    )
    state = _build_review_state(_submission(intent))
    with pytest.raises(ContributionMaterializationError) as excinfo:
        _materialize(state)
    assert excinfo.value.details["reason"] == "parent_binding_mismatch"
