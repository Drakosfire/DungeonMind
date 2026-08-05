"""Fictional-time claim bundles and revision-pinned queries (FT1a)."""

from __future__ import annotations

from collections import defaultdict, deque
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import DungeonMindModel
from .evidence import EvidenceRef

FICTIONAL_TIME_CLAIM_BUNDLE_SCHEMA = "dm_fictional_time_claim_bundle_v1"
FICTIONAL_TIME_QUERY_SCHEMA = "dm_fictional_time_query_v1"
FICTIONAL_TIME_QUERY_RESULT_SCHEMA = "dm_fictional_time_query_result_v1"


class FictionalTimeAuthorityMode(StrEnum):
    SHADOW = "shadow"


class FictionalTimeQueryKind(StrEnum):
    STRICT_BEFORE = "strict_before"
    STATE_AT_BOUNDARY = "state_at_boundary"
    ABSOLUTE_FICTIONAL_TIME = "absolute_fictional_time"


class FictionalTimeBoundaryPosition(StrEnum):
    IMMEDIATELY_BEFORE = "immediately_before"
    IMMEDIATELY_AFTER = "immediately_after"


class FictionalTimeResultStatus(StrEnum):
    ENTAILED = "entailed"
    CONTRADICTED = "contradicted"
    UNRESOLVED = "unresolved"


class FictionalTimeUnresolvedReason(StrEnum):
    SAME_ANCHOR_IRREFLEXIVE = "same_anchor_irreflexive"
    UNKNOWN_ANCHOR = "unknown_anchor"
    NO_ORDERING_PATH = "no_ordering_path"
    NO_MATCHING_STATE_BOUNDARY = "no_matching_state_boundary"
    NO_EXPLICIT_ABSOLUTE_ANCHOR = "no_explicit_absolute_anchor"


def _reject_blank(value: str, label: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{label} must be a non-blank string")


def _uniq_nonempty(ids: list[str], label: str) -> None:
    if not ids:
        raise ValueError(f"{label} must be non-empty")
    seen: set[str] = set()
    for item in ids:
        _reject_blank(item, label)
        if item in seen:
            raise ValueError(f"duplicate {label}: {item}")
        seen.add(item)


class FictionalTimeAnchor(DungeonMindModel):
    anchor_id: str
    label: str
    related_object_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_anchor(self) -> Self:
        _reject_blank(self.anchor_id, "anchor_id")
        _reject_blank(self.label, "label")
        _uniq_nonempty(self.related_object_ids, "related_object_id")
        return self


class FictionalTimeStrictBeforeClaim(DungeonMindModel):
    claim_id: str
    before_anchor_id: str
    after_anchor_id: str
    evidence_ref_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_claim(self) -> Self:
        _reject_blank(self.claim_id, "claim_id")
        _reject_blank(self.before_anchor_id, "before_anchor_id")
        _reject_blank(self.after_anchor_id, "after_anchor_id")
        _uniq_nonempty(self.evidence_ref_ids, "evidence_ref_id")
        return self


class FictionalTimeStateBoundaryClaim(DungeonMindModel):
    claim_id: str
    state_id: str
    boundary_anchor_id: str
    before_value: bool
    after_value: bool
    before_evidence_ref_ids: list[str] = Field(min_length=1)
    after_evidence_ref_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_boundary(self) -> Self:
        _reject_blank(self.claim_id, "claim_id")
        _reject_blank(self.state_id, "state_id")
        _reject_blank(self.boundary_anchor_id, "boundary_anchor_id")
        if self.before_value == self.after_value:
            raise ValueError("state boundary before_value and after_value must differ")
        _uniq_nonempty(self.before_evidence_ref_ids, "before_evidence_ref_id")
        _uniq_nonempty(self.after_evidence_ref_ids, "after_evidence_ref_id")
        return self


def _detect_cycle(adj: dict[str, list[str]], nodes: set[str]) -> None:
    indeg = dict.fromkeys(nodes, 0)
    for _src, outs in adj.items():
        for dst in outs:
            indeg[dst] += 1
    queue = deque([n for n, d in indeg.items() if d == 0])
    seen = 0
    while queue:
        node = queue.popleft()
        seen += 1
        for dst in adj.get(node, []):
            indeg[dst] -= 1
            if indeg[dst] == 0:
                queue.append(dst)
    if seen != len(nodes):
        raise ValueError("strict_before_claims contain a directed cycle")


class FictionalTimeClaimBundle(DungeonMindModel):
    schema_version: Literal["dm_fictional_time_claim_bundle_v1"] = (
        FICTIONAL_TIME_CLAIM_BUNDLE_SCHEMA
    )
    bundle_id: str
    world_id: str
    campaign_id: str
    authority_mode: FictionalTimeAuthorityMode = FictionalTimeAuthorityMode.SHADOW
    graph_schema: str
    graph_revision_id: str
    graph_payload_sha256: str
    anchors: list[FictionalTimeAnchor] = Field(min_length=1)
    strict_before_claims: list[FictionalTimeStrictBeforeClaim] = Field(default_factory=list)
    state_boundaries: list[FictionalTimeStateBoundaryClaim] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_bundle(self) -> Self:
        for field in (self.bundle_id, self.world_id, self.campaign_id, self.graph_schema,
                      self.graph_revision_id, self.graph_payload_sha256):
            _reject_blank(field, "bundle field")
        if len(self.graph_payload_sha256) != 64 or any(
            c not in "0123456789abcdef" for c in self.graph_payload_sha256
        ):
            raise ValueError("graph_payload_sha256 must be 64 lowercase hex chars")
        if self.authority_mode is not FictionalTimeAuthorityMode.SHADOW:
            raise ValueError("authority_mode must be shadow")
        if not self.strict_before_claims and not self.state_boundaries:
            raise ValueError("bundle must contain at least one claim")

        _uniq_nonempty([a.anchor_id for a in self.anchors], "anchor_id")
        anchor_ids = {a.anchor_id for a in self.anchors}
        _uniq_nonempty(
            [e.evidence_ref_id for e in self.evidence_refs], "evidence_ref_id"
        )
        evidence_ids = {e.evidence_ref_id for e in self.evidence_refs}

        claim_ids: list[str] = []
        for claim in self.strict_before_claims:
            claim_ids.append(claim.claim_id)
        for boundary in self.state_boundaries:
            claim_ids.append(boundary.claim_id)
        _uniq_nonempty(claim_ids, "claim_id")

        pairs: set[tuple[str, str]] = set()
        adj: dict[str, list[str]] = defaultdict(list)
        used_evidence: set[str] = set()
        for claim in self.strict_before_claims:
            if claim.before_anchor_id not in anchor_ids or claim.after_anchor_id not in anchor_ids:
                raise ValueError(f"dangling anchor ref in claim {claim.claim_id}")
            if claim.before_anchor_id == claim.after_anchor_id:
                raise ValueError(f"self-edge in claim {claim.claim_id}")
            pair = (claim.before_anchor_id, claim.after_anchor_id)
            if pair in pairs:
                raise ValueError(f"duplicate strict_before pair {pair}")
            pairs.add(pair)
            adj[claim.before_anchor_id].append(claim.after_anchor_id)
            for eid in claim.evidence_ref_ids:
                if eid not in evidence_ids:
                    raise ValueError(f"dangling evidence in claim {claim.claim_id}")
                used_evidence.add(eid)

        boundary_keys: set[tuple[str, str]] = set()
        for boundary in self.state_boundaries:
            if boundary.boundary_anchor_id not in anchor_ids:
                raise ValueError(f"dangling boundary anchor in {boundary.claim_id}")
            key = (boundary.state_id, boundary.boundary_anchor_id)
            if key in boundary_keys:
                raise ValueError(f"duplicate state boundary key {key}")
            boundary_keys.add(key)
            for eid in (*boundary.before_evidence_ref_ids, *boundary.after_evidence_ref_ids):
                if eid not in evidence_ids:
                    raise ValueError(f"dangling evidence in boundary {boundary.claim_id}")
                used_evidence.add(eid)

        unused = evidence_ids - used_evidence
        if unused:
            raise ValueError(f"unused evidence refs: {sorted(unused)}")
        _detect_cycle(adj, anchor_ids)
        return self


class FictionalTimeQuery(DungeonMindModel):
    schema_version: Literal["dm_fictional_time_query_v1"] = FICTIONAL_TIME_QUERY_SCHEMA
    query_id: str
    query_kind: FictionalTimeQueryKind
    before_anchor_id: str | None = None
    after_anchor_id: str | None = None
    state_id: str | None = None
    boundary_anchor_id: str | None = None
    position: FictionalTimeBoundaryPosition | None = None
    anchor_id: str | None = None

    @model_validator(mode="after")
    def _validate_query_shape(self) -> Self:
        _reject_blank(self.query_id, "query_id")
        kind = self.query_kind
        fields = {
            "before_anchor_id": self.before_anchor_id,
            "after_anchor_id": self.after_anchor_id,
            "state_id": self.state_id,
            "boundary_anchor_id": self.boundary_anchor_id,
            "position": self.position,
            "anchor_id": self.anchor_id,
        }
        if kind is FictionalTimeQueryKind.STRICT_BEFORE:
            required = ("before_anchor_id", "after_anchor_id")
            forbidden = ("state_id", "boundary_anchor_id", "position", "anchor_id")
        elif kind is FictionalTimeQueryKind.STATE_AT_BOUNDARY:
            required = ("state_id", "boundary_anchor_id", "position")
            forbidden = ("before_anchor_id", "after_anchor_id", "anchor_id")
        else:
            required = ("anchor_id",)
            forbidden = (
                "before_anchor_id", "after_anchor_id", "state_id",
                "boundary_anchor_id", "position",
            )
        for name in required:
            if fields[name] is None:
                raise ValueError(f"{name} required for query_kind {kind.value}")
            if isinstance(fields[name], str):
                _reject_blank(fields[name], name)
        for name in forbidden:
            if name in self.model_fields_set:
                raise ValueError(f"{name} must be absent for query_kind {kind.value}")
        return self


class FictionalTimeQueryResult(DungeonMindModel):
    schema_version: Literal["dm_fictional_time_query_result_v1"] = (
        FICTIONAL_TIME_QUERY_RESULT_SCHEMA
    )
    query_id: str
    query_kind: FictionalTimeQueryKind
    status: FictionalTimeResultStatus
    value: bool | None
    proof_claim_ids: list[str]
    evidence_ref_ids: list[str]
    reason: FictionalTimeUnresolvedReason | None = None
    authority_mode: FictionalTimeAuthorityMode = FictionalTimeAuthorityMode.SHADOW
    bundle_id: str
    world_id: str
    campaign_id: str
    graph_schema: str
    graph_revision_id: str
    graph_payload_sha256: str

    @model_validator(mode="after")
    def _validate_result(self) -> Self:
        if self.status is FictionalTimeResultStatus.UNRESOLVED:
            if self.value is not None:
                raise ValueError("unresolved result must have null value")
            if self.proof_claim_ids or self.evidence_ref_ids:
                raise ValueError("unresolved result must have empty proof and evidence")
            if self.reason is None:
                raise ValueError("unresolved result requires reason")
        else:
            if self.value is None:
                raise ValueError("entailed/contradicted result requires bool value")
            if not self.proof_claim_ids:
                raise ValueError("entailed/contradicted result requires nonempty proof")
            if self.reason is not None:
                raise ValueError("entailed/contradicted result must have null reason")
        if self.authority_mode is not FictionalTimeAuthorityMode.SHADOW:
            raise ValueError("authority_mode must be shadow")
        return self
