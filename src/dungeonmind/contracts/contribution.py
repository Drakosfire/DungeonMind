"""Governed contribution contracts (schema ``dm_graph_contribution_v1``).

A contribution is the durable write unit for knowledge entering the graph:
propose → validate → merge → atomic head publication. Lifecycle is explicit
(active | superseded | retracted | failed); supersession and retraction are
recorded, replayable facts, and reprocessing a contribution is idempotent.

Deviation from DungeonMindBuddy: Buddy stores assertions pre-partitioned into
candidate/accepted/rejected lists. DungeonMind stores one assertion list with
per-assertion ``acceptance_state`` and derives partitions. This removes a
whole class of partition/drift bugs; conformance fixtures (Roadmap PR B+)
pin equivalence against Buddy behavior.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from .base import DungeonMindModel
from .evidence import EvidenceRef
from .identity import IdentityOutcome
from .vocabulary import ContributionEpistemicKind, EpistemicKind, Visibility

GRAPH_CONTRIBUTION_SCHEMA = "dm_graph_contribution_v1"
GRAPH_CONTRIBUTION_V2_SCHEMA = "dm_graph_contribution_v2"


class ContributionSourceKind(StrEnum):
    EXTRACTION = "extraction"
    STANDING_CONTEXT = "standing_context"
    GRAPH_REVIEW = "graph_review"
    IDENTITY_DECISION = "identity_decision"
    MANUAL_IMPORT = "manual_import"


class ContributionStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"
    FAILED = "failed"


class AcceptanceState(StrEnum):
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class GraphContributionAssertion(DungeonMindModel):
    """One proposed or accepted fact. Metadata is mandatory, not advisory."""

    assertion_id: str
    assertion_kind: str  # relationship | attribute | ... (domain-owned vocabulary)
    subject_object_id: str | None = None
    object_object_id: str | None = None
    predicate: str | None = None
    label: str | None = None
    value: str | None = None
    evidence_refs: list[EvidenceRef] = []
    source_artifact_id: str | None = None
    source_revision_id: str | None = None
    # None means world-universal; blank strings are forbidden by construction.
    campaign_scope: str | None = Field(default=None, min_length=1)
    temporal_scope: dict[str, Any] | None = None
    visibility: Visibility = Visibility.GM
    epistemic_kind: EpistemicKind = EpistemicKind.ASSERTED
    acceptance_state: AcceptanceState = AcceptanceState.CANDIDATE
    identity_resolution_outcome: IdentityOutcome | None = None

    @model_validator(mode="after")
    def _accepted_requires_evidentiary_basis(self) -> Self:
        if self.acceptance_state is AcceptanceState.ACCEPTED:
            has_evidence = bool(self.evidence_refs)
            has_source = bool(self.source_artifact_id or self.source_revision_id)
            if not has_evidence and not has_source:
                raise ValueError(
                    "accepted assertions require evidence_refs or a source "
                    "artifact/revision identity"
                )
        return self


class GraphContribution(DungeonMindModel):
    """The durable, idempotent, replayable write unit."""

    schema_version: Literal["dm_graph_contribution_v1"] = GRAPH_CONTRIBUTION_SCHEMA
    contribution_id: str
    world_id: str
    source_kind: ContributionSourceKind
    source_artifact_id: str | None = None
    source_revision_id: str | None = None
    extraction_profile: str | None = None
    produced_at: datetime
    campaign_scope: str | None = Field(default=None, min_length=1)
    status: ContributionStatus = ContributionStatus.ACTIVE
    supersedes_contribution_id: str | None = None
    assertions: list[GraphContributionAssertion] = []
    unresolved_mentions: list[str] = []
    identity_decision_ids: list[str] = []
    authored_by: str | None = None
    diagnostics: dict[str, Any] = {}

    def partition_assertions(
        self, state: AcceptanceState
    ) -> list[GraphContributionAssertion]:
        return [a for a in self.assertions if a.acceptance_state is state]


def _require_nonblank_id(value: str, *, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must be a non-blank string")
    return value


class GraphContributionAssertionCorrectionKind(StrEnum):
    CONTRADICTS = "contradicts"
    CONTRADICTS_AND_REPLACES = "contradicts_and_replaces"


class GraphContributionAssertionCorrection(DungeonMindModel):
    """Typed contradiction history for one contribution assertion."""

    correction_kind: GraphContributionAssertionCorrectionKind
    target_contribution_id: str
    target_assertion_id: str
    replacement_assertion_id: str | None = None

    @field_validator("target_contribution_id", "target_assertion_id")
    @classmethod
    def _target_ids(cls, value: str) -> str:
        return _require_nonblank_id(value, field_name="correction target id")

    @field_validator("replacement_assertion_id")
    @classmethod
    def _replacement_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_nonblank_id(value, field_name="replacement_assertion_id")

    @model_validator(mode="after")
    def _kind_nullability(self) -> Self:
        kind = self.correction_kind
        replacement = self.replacement_assertion_id
        if kind is GraphContributionAssertionCorrectionKind.CONTRADICTS and replacement is not None:
            raise ValueError("contradicts requires replacement_assertion_id to be null")
        if (
            kind is GraphContributionAssertionCorrectionKind.CONTRADICTS_AND_REPLACES
            and replacement is None
        ):
            raise ValueError(
                "contradicts_and_replaces requires a non-blank replacement_assertion_id"
            )
        return self


class GraphContributionAssertionV2(DungeonMindModel):
    """v2 contribution assertion. Admits ``source_derived_candidate`` exactly."""

    assertion_id: str
    assertion_kind: str
    subject_object_id: str | None = None
    object_object_id: str | None = None
    predicate: str | None = None
    label: str | None = None
    value: str | None = None
    evidence_refs: list[EvidenceRef] = []
    source_artifact_id: str | None = None
    source_revision_id: str | None = None
    campaign_scope: str | None = Field(default=None, min_length=1)
    temporal_scope: dict[str, Any] | None = None
    visibility: Visibility = Visibility.GM
    epistemic_kind: ContributionEpistemicKind = ContributionEpistemicKind.ASSERTED
    acceptance_state: AcceptanceState = AcceptanceState.CANDIDATE
    identity_resolution_outcome: IdentityOutcome | None = None

    @model_validator(mode="after")
    def _accepted_requires_evidentiary_basis(self) -> Self:
        if self.acceptance_state is AcceptanceState.ACCEPTED:
            has_evidence = bool(self.evidence_refs)
            has_source = bool(self.source_artifact_id or self.source_revision_id)
            if not has_evidence and not has_source:
                raise ValueError(
                    "accepted assertions require evidence_refs or a source "
                    "artifact/revision identity"
                )
        return self


class GraphContributionV2(DungeonMindModel):
    """v2 durable write unit. Preserves v1 fields and typed correction history."""

    schema_version: Literal["dm_graph_contribution_v2"] = GRAPH_CONTRIBUTION_V2_SCHEMA
    contribution_id: str
    world_id: str
    source_kind: ContributionSourceKind
    source_artifact_id: str | None = None
    source_revision_id: str | None = None
    extraction_profile: str | None = None
    produced_at: datetime
    campaign_scope: str | None = Field(default=None, min_length=1)
    status: ContributionStatus = ContributionStatus.ACTIVE
    supersedes_contribution_id: str | None = None
    assertions: list[GraphContributionAssertionV2] = []
    unresolved_mentions: list[str] = []
    identity_decision_ids: list[str] = []
    authored_by: str | None = None
    diagnostics: dict[str, Any] = {}
    assertion_corrections: list[GraphContributionAssertionCorrection] = []

    def partition_assertions(
        self, state: AcceptanceState
    ) -> list[GraphContributionAssertionV2]:
        return [a for a in self.assertions if a.acceptance_state is state]
