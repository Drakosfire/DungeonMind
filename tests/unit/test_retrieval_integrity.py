"""Closed-envelope evidence ledger integrity for sessions and Mind Turn responses."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dungeonmind.contracts import (
    Admissibility,
    Claim,
    ClaimAuthority,
    ClaimStatus,
    EvidenceRef,
    GraphRetrievalSession,
    MindTurnResponse,
    ProjectionSnapshot,
    SourceAnchor,
    SourceDomain,
    SourceRead,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)
REV = "rev:" + "ab" * 16


def _snapshot() -> ProjectionSnapshot:
    return ProjectionSnapshot(
        world_id="world:demo",
        revision_id=REV,
        head_revision_id=REV,
        is_head=True,
        projected_at=NOW,
        admissibility=Admissibility.GM,
    )


def _evidence(evidence_ref_id: str = "evd:1") -> EvidenceRef:
    return EvidenceRef(
        evidence_ref_id=evidence_ref_id,
        source_artifact_id="src:1",
        source_domain=SourceDomain.WORLDBUILDING,
    )


def _anchor(
    *,
    anchor_id: str = "anc:1",
    evidence_ref_id: str | None = "evd:1",
) -> SourceAnchor:
    return SourceAnchor(
        anchor_id=anchor_id,
        revision_id=REV,
        evidence_ref_id=evidence_ref_id,
        source_artifact_id="src:1",
        source_domain="worldbuilding",
    )


def _valid_session(**overrides: object) -> GraphRetrievalSession:
    base: dict[str, object] = {
        "session_id": "ses:1",
        "snapshot": _snapshot(),
        "question": "Where?",
        "evidence": [_evidence()],
        "source_anchors": [_anchor()],
        "source_reads": [
            SourceRead(source_anchor_id="anc:1", read_at=NOW, content_sha256="ab" * 32)
        ],
        "claims": [
            Claim(
                claim_id="claim:1",
                text="Mere Astor lives in Vael.",
                authority=ClaimAuthority.GRAPH_FACT,
                status=ClaimStatus.ACCEPTED,
                evidence_ref_ids=["evd:1"],
                source_anchor_ids=["anc:1"],
            )
        ],
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return GraphRetrievalSession(**base)  # type: ignore[arg-type]


def test_valid_complete_ledger_round_trips() -> None:
    session = _valid_session()
    restored = GraphRetrievalSession.model_validate_json(session.model_dump_json())
    assert restored == session

    response = MindTurnResponse(
        request_id="req:1",
        turn_id="turn:1",
        thread_id="thr:1",
        world_id="world:demo",
        revision_id=REV,
        answer="In Vael.",
        evidence=session.evidence,
        source_anchors=session.source_anchors,
        source_reads=session.source_reads,
        claims=session.claims,
    )
    assert MindTurnResponse.model_validate_json(response.model_dump_json()) == response


def test_graph_fact_with_invented_evidence_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid_session(
            claims=[
                Claim(
                    claim_id="claim:1",
                    text="unsupported",
                    authority=ClaimAuthority.GRAPH_FACT,
                    evidence_ref_ids=["evidence:not-admitted"],
                )
            ]
        )


def test_claim_with_invented_anchor_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid_session(
            claims=[
                Claim(
                    claim_id="claim:1",
                    text="fact",
                    authority=ClaimAuthority.GRAPH_FACT,
                    evidence_ref_ids=["evd:1"],
                    source_anchor_ids=["anc:missing"],
                )
            ]
        )


def test_anchor_with_invented_evidence_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid_session(source_anchors=[_anchor(evidence_ref_id="evd:missing")])


def test_source_read_with_invented_anchor_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid_session(
            source_reads=[
                SourceRead(
                    source_anchor_id="anc:missing",
                    read_at=NOW,
                    content_sha256="ab" * 32,
                )
            ]
        )


def test_duplicate_evidence_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid_session(evidence=[_evidence(), _evidence()])


def test_duplicate_anchor_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid_session(source_anchors=[_anchor(), _anchor()])


def test_duplicate_claim_ids_rejected() -> None:
    claim = Claim(
        claim_id="claim:1",
        text="fact",
        authority=ClaimAuthority.GRAPH_FACT,
        evidence_ref_ids=["evd:1"],
    )
    with pytest.raises(ValidationError):
        _valid_session(claims=[claim, claim])


def test_accepted_ungrounded_claim_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid_session(
            claims=[
                Claim(
                    claim_id="claim:1",
                    text="rumor",
                    authority=ClaimAuthority.UNGROUNDED,
                    status=ClaimStatus.ACCEPTED,
                )
            ]
        )


def test_rejected_claim_may_retain_resolvable_refs() -> None:
    session = _valid_session(
        claims=[
            Claim(
                claim_id="claim:1",
                text="was wrong",
                authority=ClaimAuthority.GRAPH_FACT,
                status=ClaimStatus.REJECTED,
                evidence_ref_ids=["evd:1"],
                source_anchor_ids=["anc:1"],
            )
        ]
    )
    assert session.claims[0].status is ClaimStatus.REJECTED
