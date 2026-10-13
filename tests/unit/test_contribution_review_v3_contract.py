"""Typed evidence remains first-class in the versioned governed wire."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dungeonmind.contracts.contribution import GraphContributionV3
from dungeonmind.contracts.contribution_review_v3 import (
    ContributionReviewIntentV3,
    contribution_v3_payload_sha256,
    derive_review_intent_sha256_v3,
)
from dungeonmind.contracts.evidence import EvidenceRefV2
from tests.unit.test_contribution_review_v2 import _candidate, _intent, _stored_parent


def typed_candidate() -> GraphContributionV3:
    payload = _candidate().model_dump(mode="json")
    payload["schema_version"] = "dm_graph_contribution_v3"
    payload["source_revision_id"] = "revision:typed-span"
    for assertion in payload["assertions"]:
        for ref in assertion["evidence_refs"]:
            ref.update(
                schema_version="dm_evidence_ref_v2",
                source_revision_id="revision:typed-span",
                source_domain_key="session_recap",
                session_id="session-2",
                source_span_ref_id="paragraph:002",
                uri="repo://recap/session-2",
                source_locator=None,
                line_ref=None,
            )
    return GraphContributionV3.model_validate(payload)


def typed_intent(candidate: GraphContributionV3 | None = None) -> ContributionReviewIntentV3:
    candidate = candidate or typed_candidate()
    old = _intent(parent=_stored_parent())
    plan = old.plan_ref.model_copy(
        update={"candidate_contribution_sha256": contribution_v3_payload_sha256(candidate)}
    )
    fields = dict(
        operation_id=old.operation_id,
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


def test_typed_evidence_roundtrip_and_digest_binds_span_and_source() -> None:
    candidate = typed_candidate()
    restored = GraphContributionV3.model_validate(candidate.model_dump(mode="json"))
    assert restored == candidate
    ref = restored.assertions[0].evidence_refs[0]
    assert isinstance(ref, EvidenceRefV2)
    assert ref.source_span_ref_id == "paragraph:002"
    assert ref.evidence_ref_id == candidate.assertions[0].evidence_refs[0].evidence_ref_id
    for change in (
        {"source_span_ref_id": "paragraph:003"},
        {"source_revision_id": "revision:other"},
    ):
        changed = candidate.model_copy(deep=True)
        changed.assertions[0].evidence_refs[0] = ref.model_copy(update=change)
        assert contribution_v3_payload_sha256(changed) != contribution_v3_payload_sha256(candidate)
    assert typed_intent(candidate).candidate_contribution == candidate


def test_typed_evidence_wrong_assertion_source_or_scope_rejected() -> None:
    candidate = typed_candidate()
    candidate.assertions[0].source_artifact_id = "artifact:wrong"
    with pytest.raises(ValidationError, match="source artifact differs"):
        typed_intent(candidate)
    candidate = typed_candidate()
    candidate.assertions[0].campaign_scope = "wrong-campaign"
    with pytest.raises(ValidationError, match="campaign differs"):
        typed_intent(candidate)
