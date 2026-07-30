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
from typing import Any, Literal

from pydantic import Field

from .base import DungeonMindModel
from .evidence import EvidenceRef
from .identity import IdentityOutcome
from .vocabulary import EpistemicKind, Visibility

GRAPH_CONTRIBUTION_SCHEMA = "dm_graph_contribution_v1"


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
