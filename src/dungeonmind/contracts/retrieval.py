"""Retrieval session contracts (schema ``dm_retrieval_session_v1``).

A retrieval session is turn-scoped and read-only: it records resolved
referents, the append-only operation log, the claim ledger, admitted source
anchors and reads, coverage, and diagnostics — all pinned to one coherent
graph revision. A graph miss produces coverage/abstention, never a silent
fallback to arbitrary file search. Vector similarity is never evidence.

Admitted evidence, anchors, reads, and claims form one closed ledger.
Reference integrity is validated against that envelope — not by repository
lookup from Pydantic validators.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from .base import DungeonMindModel
from .evidence import EvidenceRef
from .identity import IdentityOutcome
from .projection import ProjectionSnapshot

RETRIEVAL_SESSION_SCHEMA = "dm_retrieval_session_v1"


class ClaimAuthority(StrEnum):
    GRAPH_FACT = "graph_fact"  # supported by admitted evidence at the pinned revision
    INFERENCE = "inference"  # derived; must be labeled, never stated as fact
    UNGROUNDED = "ungrounded"  # asserted without admitted support; rejected by validation


class ClaimStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Claim(DungeonMindModel):
    claim_id: str
    text: str
    authority: ClaimAuthority = ClaimAuthority.UNGROUNDED
    status: ClaimStatus = ClaimStatus.PENDING
    evidence_ref_ids: list[str] = []
    source_anchor_ids: list[str] = []

    @model_validator(mode="after")
    def _graph_fact_requires_evidence(self) -> Self:
        if self.authority is ClaimAuthority.GRAPH_FACT and not self.evidence_ref_ids:
            raise ValueError("graph_fact claims require at least one evidence_ref_id")
        return self


class ResolvedReferent(DungeonMindModel):
    """How a mention in the user message resolved against the graph."""

    mention_text: str
    outcome: IdentityOutcome
    object_id: str | None = None  # set only for resolved_existing / created identities
    diagnostics: dict[str, Any] = {}


class RetrievalOperationKind(StrEnum):
    SEARCH_OBJECTS = "search_objects"
    GET_OBJECT = "get_object"
    LIST_RELATIONSHIPS = "list_relationships"
    EXPAND = "expand"
    READ_SOURCE = "read_source"
    SEMANTIC_CANDIDATES = "semantic_candidates"


class OperationOutcome(StrEnum):
    OK = "ok"
    MISS = "miss"
    DENIED = "denied"


class RetrievalOperation(DungeonMindModel):
    """Append-only record of one retrieval step at the pinned revision."""

    operation_id: str
    kind: RetrievalOperationKind
    outcome: OperationOutcome
    revision_id: str
    arguments: dict[str, Any] = {}
    result_count: int = 0
    diagnostics: dict[str, Any] = {}


class SourceAnchor(DungeonMindModel):
    """A graph-admitted pointer to openable source material."""

    anchor_id: str
    revision_id: str
    evidence_ref_id: str | None = None
    source_artifact_id: str
    source_domain: str
    session_id: str | None = None
    supporting_object_ids: list[str] = []
    readable: bool = True
    locator_kind: str | None = None
    display_label: str | None = None


class SourceRead(DungeonMindModel):
    """Record of an opened anchor. Content is referenced by digest, not copied."""

    source_anchor_id: str
    read_at: datetime
    content_sha256: str


class Coverage(DungeonMindModel):
    """What the graph could and could not answer. Misses are explicit."""

    known: list[str] = []
    missing: list[str] = []
    gap_codes: list[str] = []


class DiagnosticEntry(DungeonMindModel):
    code: str
    severity: Literal["info", "warning", "error"] = "info"
    message: str | None = None
    data: dict[str, Any] = {}


def validate_admitted_evidence_ledger(
    *,
    evidence: list[EvidenceRef],
    source_anchors: list[SourceAnchor],
    source_reads: list[SourceRead],
    claims: list[Claim],
) -> None:
    """Validate closed-envelope referential integrity for an admitted ledger."""
    evidence_ids = [item.evidence_ref_id for item in evidence]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("duplicate evidence_ref_id in admitted evidence ledger")
    evidence_set = set(evidence_ids)

    anchor_ids = [item.anchor_id for item in source_anchors]
    if len(anchor_ids) != len(set(anchor_ids)):
        raise ValueError("duplicate anchor_id in admitted anchor ledger")
    anchor_set = set(anchor_ids)

    claim_ids = [item.claim_id for item in claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("duplicate claim_id in claim ledger")

    for anchor in source_anchors:
        if anchor.evidence_ref_id is not None and anchor.evidence_ref_id not in evidence_set:
            raise ValueError(
                f"source anchor {anchor.anchor_id!r} references unknown "
                f"evidence_ref_id {anchor.evidence_ref_id!r}"
            )

    for read in source_reads:
        if read.source_anchor_id not in anchor_set:
            raise ValueError(
                f"source read references unknown source_anchor_id "
                f"{read.source_anchor_id!r}"
            )

    for claim in claims:
        if (
            claim.authority is ClaimAuthority.UNGROUNDED
            and claim.status is ClaimStatus.ACCEPTED
        ):
            raise ValueError("ungrounded claim must not be accepted")
        for evidence_ref_id in claim.evidence_ref_ids:
            if evidence_ref_id not in evidence_set:
                raise ValueError(
                    f"claim {claim.claim_id!r} references unknown "
                    f"evidence_ref_id {evidence_ref_id!r}"
                )
        for source_anchor_id in claim.source_anchor_ids:
            if source_anchor_id not in anchor_set:
                raise ValueError(
                    f"claim {claim.claim_id!r} references unknown "
                    f"source_anchor_id {source_anchor_id!r}"
                )
        if claim.authority is ClaimAuthority.GRAPH_FACT and not claim.evidence_ref_ids:
            raise ValueError(
                f"graph_fact claim {claim.claim_id!r} requires admitted evidence"
            )


class GraphRetrievalSession(DungeonMindModel):
    schema_version: Literal["dm_retrieval_session_v1"] = RETRIEVAL_SESSION_SCHEMA
    session_id: str
    thread_id: str | None = None
    snapshot: ProjectionSnapshot
    question: str
    intent_hint: str | None = None
    referents: list[ResolvedReferent] = []
    operations: list[RetrievalOperation] = []
    evidence: list[EvidenceRef] = []
    claims: list[Claim] = []
    source_anchors: list[SourceAnchor] = []
    source_reads: list[SourceRead] = []
    coverage: Coverage = Field(default_factory=Coverage)
    diagnostics: list[DiagnosticEntry] = []
    preflight_candidate_ids: list[str] = []
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _admitted_ledger_integrity(self) -> Self:
        validate_admitted_evidence_ledger(
            evidence=self.evidence,
            source_anchors=self.source_anchors,
            source_reads=self.source_reads,
            claims=self.claims,
        )
        return self
