"""Retrieval session contracts (schema ``dm_retrieval_session_v1``).

A retrieval session is turn-scoped and read-only: it records resolved
referents, the append-only operation log, the claim ledger, admitted source
anchors and reads, coverage, and diagnostics — all pinned to one coherent
graph revision. A graph miss produces coverage/abstention, never a silent
fallback to arbitrary file search. Vector similarity is never evidence.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from .base import DungeonMindModel
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


class GraphRetrievalSession(DungeonMindModel):
    schema_version: Literal["dm_retrieval_session_v1"] = RETRIEVAL_SESSION_SCHEMA
    session_id: str
    thread_id: str | None = None
    snapshot: ProjectionSnapshot
    question: str
    intent_hint: str | None = None
    referents: list[ResolvedReferent] = []
    operations: list[RetrievalOperation] = []
    claims: list[Claim] = []
    source_anchors: list[SourceAnchor] = []
    source_reads: list[SourceRead] = []
    coverage: Coverage = Coverage()
    diagnostics: list[DiagnosticEntry] = []
    preflight_candidate_ids: list[str] = []
    created_at: datetime
    updated_at: datetime
