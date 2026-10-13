"""Governed V3 review retains typed evidence through V6 child materialization."""

from __future__ import annotations

import pytest

from dungeonmind.application.contribution_review_v3 import _build_review_state
from dungeonmind.application.review_materialization_v6 import materialize_finalized_review_v6
from dungeonmind.application.source_provenance_snapshot import SourceProvenanceSnapshot
from dungeonmind.contracts.contribution_review import derive_confirmation_id
from dungeonmind.contracts.contribution_review_v3 import (
    CommitConfirmationReceiptV3,
    ContributionReviewSubmissionV3,
)
from dungeonmind.contracts.evidence import SourceArtifactV2, SourceDomain, SourceRevision
from dungeonmind.domain.errors import ContributionMaterializationError
from tests.unit.test_contribution_review_v2 import (
    CAMPAIGN_ID,
    REVIEWED_AT,
    WORLD_ID,
    _reader,
    _stored_parent,
)
from tests.unit.test_contribution_review_v3_contract import typed_candidate, typed_intent


def submission(candidate=None) -> ContributionReviewSubmissionV3:
    intent = typed_intent(candidate)
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


def source_snapshot() -> SourceProvenanceSnapshot:
    artifact_id = "artifact:recap:longmont-c2:session-2"
    revision_id = "revision:typed-span"
    artifact = SourceArtifactV2(
        source_artifact_id=artifact_id,
        source_domain_key="session_recap",
        source_domain=SourceDomain.SESSION_RECAP,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        session_id="session-2",
        uri="repo://recap/session-2",
        current_revision_id=revision_id,
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
    revision = SourceRevision(
        source_revision_id=revision_id,
        source_artifact_id=artifact_id,
        content_sha256="a" * 64,
        body_storage="object_store",
        locator="repo://recap/session-2",
        created_at=REVIEWED_AT,
    )
    return SourceProvenanceSnapshot.from_loaded(
        requested_artifact_ids=frozenset({artifact_id}),
        requested_revision_ids=frozenset({revision_id}),
        artifacts={artifact_id: artifact},
        revisions={revision_id: revision},
    )


def test_reviewed_child_retains_exact_typed_span_and_identity() -> None:
    state = _build_review_state(submission())
    assert (
        state.reviewed_contribution.assertions[0].evidence_refs[0].source_span_ref_id
        == "paragraph:002"
    )
    child = materialize_finalized_review_v6(
        state,
        parent=_stored_parent(),
        graph_reader=_reader(),
        source_snapshot=source_snapshot(),
    )
    row = next(
        e
        for e in child.graph_payload["evidence_refs"]
        if e["evidence_ref_id"] == "evidence:new:node"
    )
    assert row["source_span_ref_id"] == "paragraph:002"
    assert row["locator"] == "paragraph:002"
    assert row["uri"] == "repo://recap/session-2"


def test_same_evidence_id_with_conflicting_typed_content_fails_closed() -> None:
    candidate = typed_candidate()
    first = candidate.assertions[0].evidence_refs[0]
    second = candidate.assertions[1].evidence_refs[0]
    candidate.assertions[1].evidence_refs[0] = second.model_copy(
        update={
            "evidence_ref_id": first.evidence_ref_id,
            "source_span_ref_id": "paragraph:other",
        }
    )
    state = _build_review_state(submission(candidate))
    with pytest.raises(ContributionMaterializationError) as exc:
        materialize_finalized_review_v6(
            state,
            parent=_stored_parent(),
            graph_reader=_reader(),
            source_snapshot=source_snapshot(),
        )
    assert exc.value.details["reason"] == "accepted_evidence_conflict"


@pytest.mark.parametrize("field", ["campaign_id", "world_id"])
def test_registered_source_wrong_scope_blocks_child_materialization(field: str) -> None:
    state = _build_review_state(submission())
    snapshot = source_snapshot()
    artifact_id = "artifact:recap:longmont-c2:session-2"
    artifact = snapshot.get_artifact(artifact_id)
    assert artifact is not None
    changed = artifact.model_copy(update={field: "wrong-scope"})
    bad = SourceProvenanceSnapshot.from_loaded(
        requested_artifact_ids=snapshot.requested_artifact_ids,
        requested_revision_ids=snapshot.requested_revision_ids,
        artifacts={artifact_id: changed},
        revisions={"revision:typed-span": snapshot.get_revision("revision:typed-span")},
    )
    with pytest.raises(ContributionMaterializationError) as exc:
        materialize_finalized_review_v6(
            state,
            parent=_stored_parent(),
            graph_reader=_reader(),
            source_snapshot=bad,
        )
    assert exc.value.details["reason"] in {"source_world_mismatch", "evidence_source_mismatch"}
