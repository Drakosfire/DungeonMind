"""The Mind Turn contract (schema ``mind_turn_v1``) — DungeonMind's primary
interaction envelope.

A surface submits surface context + a user message; DungeonMind resolves scope
and revision, retrieves and admits evidence, assembles context, runs an agent
adapter under a capability policy, and returns an answer plus semantic
projections and diagnostics. Surfaces never assemble graph queries or prompts,
and response types are never named after surface layouts (panes, drawers,
cards, rails) or agent tool traces.

Deviations from the handoff's conceptual target, recorded deliberately:
- ``caller_scope`` carries the authenticated caller identity explicitly so that
  authorization is never conflated with ``world_id`` (a world id is not an
  authentication boundary).
- ``focus``/``admissibility`` reuse the projection contracts so a Mind Turn and
  a graph projection share one scope vocabulary.
- Sub-records (claims, evidence, source reads, coverage) reuse the retrieval
  session contracts so the session ledger and the wire response cannot drift.
- ``admissibility`` is required with no default (PR A.1): absence never means GM.
- Response ledgers validate closed-envelope referential integrity.
"""

from typing import Any, Literal, Self

from pydantic import Field, model_validator

from .base import DungeonMindModel
from .evidence import EvidenceRef
from .projection import Admissibility, FocusKind, ProjectionFocus
from .retrieval import (
    Claim,
    Coverage,
    DiagnosticEntry,
    ResolvedReferent,
    SourceAnchor,
    SourceRead,
    validate_admitted_evidence_ledger,
)

MIND_TURN_SCHEMA = "mind_turn_v1"


class CallerScope(DungeonMindModel):
    """Who is calling. Authentication/authorization live outside DungeonMind core."""

    caller_id: str
    tenant_id: str | None = None
    roles: list[str] = []


class SurfaceContext(DungeonMindModel):
    """Everything a surface may provide. Surfaces own nothing else."""

    surface_id: str
    mode: str | None = None
    selected_object_ids: list[str] = []
    selected_document_ref: str | None = None
    active_artifact_refs: list[str] = []


class MindTurnRequest(DungeonMindModel):
    schema_version: Literal["mind_turn_v1"] = MIND_TURN_SCHEMA
    request_id: str
    thread_id: str
    caller_scope: CallerScope
    world_id: str
    campaign_id: str | None = Field(default=None, min_length=1)
    # None resolves to the head at read time; the response reports the winner.
    requested_revision_id: str | None = None
    # Required. No default — absence must never mean GM.
    admissibility: Admissibility
    focus: ProjectionFocus = Field(default_factory=ProjectionFocus)
    surface_context: SurfaceContext
    message: str

    @model_validator(mode="after")
    def _session_focus_requires_campaign(self) -> Self:
        if self.focus.kind is FocusKind.SESSION and not self.campaign_id:
            raise ValueError("session focus requires campaign_id on MindTurnRequest")
        return self

    @classmethod
    def for_authorized(
        cls,
        *,
        request_id: str,
        thread_id: str,
        caller_scope: CallerScope,
        world_id: str,
        admissibility: Admissibility,
        surface_context: SurfaceContext,
        message: str,
        campaign_id: str | None = None,
        requested_revision_id: str | None = None,
        focus: ProjectionFocus | None = None,
    ) -> Self:
        """Trusted constructor for orchestration after caller authorization."""
        return cls(
            request_id=request_id,
            thread_id=thread_id,
            caller_scope=caller_scope,
            world_id=world_id,
            campaign_id=campaign_id,
            requested_revision_id=requested_revision_id,
            admissibility=admissibility,
            focus=focus or ProjectionFocus(),
            surface_context=surface_context,
            message=message,
        )


class SemanticProjection(DungeonMindModel):
    """A semantic (surface-agnostic) view derived from the turn's results."""

    projection_id: str
    kind: str  # e.g. entity_brief | relationship_list | chronology_excerpt (vocabulary v1)
    payload: dict[str, Any] = {}


class SuggestedAction(DungeonMindModel):
    """An action the surface may offer. Never a silent side effect."""

    action_id: str
    kind: str  # e.g. open_source | pin_revision | propose_contribution (vocabulary v1)
    label: str
    arguments: dict[str, Any] = {}


class ContextChange(DungeonMindModel):
    """A proposed change to the surface's context for the next turn."""

    change_id: str
    kind: str  # e.g. focus_updated | selection_merged | thread_continued (vocabulary v1)
    payload: dict[str, Any] = {}


class MindTurnResponse(DungeonMindModel):
    schema_version: Literal["mind_turn_v1"] = MIND_TURN_SCHEMA
    request_id: str
    turn_id: str
    thread_id: str
    world_id: str
    campaign_id: str | None = None
    revision_id: str
    answer: str
    resolved_referents: list[ResolvedReferent] = []
    claims: list[Claim] = []
    evidence: list[EvidenceRef] = []
    source_anchors: list[SourceAnchor] = []
    source_reads: list[SourceRead] = []
    semantic_projections: list[SemanticProjection] = []
    suggested_actions: list[SuggestedAction] = []
    context_changes: list[ContextChange] = []
    coverage: Coverage = Field(default_factory=Coverage)
    diagnostics: list[DiagnosticEntry] = []

    @model_validator(mode="after")
    def _admitted_ledger_integrity(self) -> Self:
        validate_admitted_evidence_ledger(
            evidence=self.evidence,
            source_anchors=self.source_anchors,
            source_reads=self.source_reads,
            claims=self.claims,
            pinned_revision_id=self.revision_id,
        )
        return self
