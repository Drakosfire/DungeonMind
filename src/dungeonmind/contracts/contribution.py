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

from pydantic import ConfigDict, Field, field_validator, model_validator

from .base import DungeonMindModel
from .evidence import EvidenceRef, EvidenceRefV2
from .identity import IdentityOutcome
from .vocabulary import ContributionEpistemicKind, EpistemicKind, Visibility

GRAPH_CONTRIBUTION_SCHEMA = "dm_graph_contribution_v1"
GRAPH_CONTRIBUTION_V2_SCHEMA = "dm_graph_contribution_v2"
GRAPH_CONTRIBUTION_V3_SCHEMA = "dm_graph_contribution_v3"


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

    def partition_assertions(self, state: AcceptanceState) -> list[GraphContributionAssertion]:
        return [a for a in self.assertions if a.acceptance_state is state]


def _require_nonblank_id(value: str, *, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must be a non-blank string")
    return value


class GraphContributionAssertionCorrectionKind(StrEnum):
    CONTRADICTS_SOURCE_DESCRIPTION = "contradicts_source_description"
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
        if kind in {
            GraphContributionAssertionCorrectionKind.CONTRADICTS,
            GraphContributionAssertionCorrectionKind.CONTRADICTS_SOURCE_DESCRIPTION,
        } and replacement is not None:
            raise ValueError(f"{kind.value} requires replacement_assertion_id to be null")
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

    @model_validator(mode="after")
    def _source_description_withdrawal_contract(self) -> Self:
        if any(
            item.correction_kind
            is GraphContributionAssertionCorrectionKind.CONTRADICTS_SOURCE_DESCRIPTION
            for item in self.assertion_corrections
        ):
            reason = self.diagnostics.get("source_description_withdrawal_reason")
            if (
                self.schema_version != GRAPH_CONTRIBUTION_V3_SCHEMA
                or self.source_kind is not ContributionSourceKind.GRAPH_REVIEW
                or not isinstance(reason, str)
                or not reason.strip()
            ):
                raise ValueError(
                    "source-description withdrawal requires V3 Graph review and reason"
                )
        return self

    def partition_assertions(self, state: AcceptanceState) -> list[GraphContributionAssertionV2]:
        return [a for a in self.assertions if a.acceptance_state is state]


class GraphContributionAssertionV3(GraphContributionAssertionV2):
    """Versioned governed assertion with first-class typed evidence."""

    evidence_refs: list[EvidenceRefV2] = []

    @model_validator(mode="after")
    def _typed_evidence_source_identity(self) -> Self:
        for ref in self.evidence_refs:
            if not ref.source_revision_id:
                raise ValueError("typed evidence requires an immutable source revision")
            if self.source_artifact_id and ref.source_artifact_id != self.source_artifact_id:
                raise ValueError("typed evidence source artifact differs from assertion")
            if self.source_revision_id and ref.source_revision_id != self.source_revision_id:
                raise ValueError("typed evidence source revision differs from assertion")
        return self


class GraphContributionV3(GraphContributionV2):
    """Durable governed contribution carrying typed evidence refs."""

    schema_version: Literal["dm_graph_contribution_v3"] = GRAPH_CONTRIBUTION_V3_SCHEMA
    assertions: list[GraphContributionAssertionV3] = []

    @model_validator(mode="after")
    def _assertion_scope(self) -> Self:
        for assertion in self.assertions:
            if assertion.campaign_scope != self.campaign_scope:
                raise ValueError("candidate assertion campaign differs from review intent")
        return self

    def partition_assertions(self, state: AcceptanceState) -> list[GraphContributionAssertionV3]:
        return [a for a in self.assertions if a.acceptance_state is state]


GRAPH_CONTRIBUTION_V4_SCHEMA = "dm_graph_contribution_v4"


def _strict_property_json(value: Any, *, depth: int = 0, budget: list[int] | None = None) -> None:
    """Check raw values before serialization can coerce Python objects."""
    import math

    if budget is None:
        budget = [0]
    budget[0] += 1
    if budget[0] > 4096 or depth > 32:
        raise ValueError("property JSON node/depth bound exceeded")
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if value.bit_length() > 4096:
            raise ValueError("property integer exceeds 4096 bits")
    elif type(value) is float:
        if not math.isfinite(value):
            raise ValueError("property numbers must be finite")
    elif type(value) is str:
        if len(value.encode("utf-8")) > 16384:
            raise ValueError("property string exceeds UTF-8 bound")
    elif type(value) is list:
        if len(value) > 1024:
            raise ValueError("property array exceeds element bound")
        for item in value:
            _strict_property_json(item, depth=depth + 1, budget=budget)
    elif type(value) is dict:
        if len(value) > 256:
            raise ValueError("property object exceeds member bound")
        for key, item in value.items():
            if type(key) is not str or len(key.encode("utf-8")) > 1024:
                raise ValueError("property object key must be a bounded string")
            budget[0] += 1
            if budget[0] > 4096:
                raise ValueError("property JSON node bound exceeded")
            _strict_property_json(item, depth=depth + 1, budget=budget)
    else:
        raise ValueError("property literal requires strict JSON types")


class ReviewedPropertyLiteralV1(DungeonMindModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always")
    schema_version: Literal["dm_reviewed_property_literal_v1"]
    property_term: str
    value: Any = Field(...)

    @model_validator(mode="before")
    @classmethod
    def _strict_input(cls, raw: Any) -> Any:
        if isinstance(raw, cls):
            if getattr(raw, "__pydantic_extra__", None):
                raise ValueError("property literal model has extra state")
            raw = vars(raw)
        if type(raw) is not dict or set(raw) != {"schema_version", "property_term", "value"}:
            raise ValueError("property requires the closed literal envelope")
        _strict_property_json(raw)
        term = raw["property_term"]
        if type(term) is not str or not term.strip() or len(term.encode("utf-8")) > 512:
            raise ValueError("property term must be nonblank and at most 512 UTF-8 bytes")
        import json

        canonical = json.dumps(
            raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        if len(canonical.encode("utf-8")) > 65536:
            raise ValueError("property envelope exceeds 65536 UTF-8 bytes")
        return raw


def parse_reviewed_property_literal(raw: Any) -> ReviewedPropertyLiteralV1:
    import json

    if type(raw) is not str:
        raise ValueError("property value must be a JSON envelope string")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate property JSON key")
            result[key] = value
        return result

    def nonfinite(token: str) -> Any:
        raise ValueError("nonfinite JSON number")

    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
        return ReviewedPropertyLiteralV1.model_validate(value)
    except (RecursionError, OverflowError) as exc:
        raise ValueError("property parser bounds exceeded") from exc


class GraphContributionAssertionV4(GraphContributionAssertionV3):
    """V4 alone authorizes literal properties, retaining typed evidence."""

    model_config = ConfigDict(extra="forbid", revalidate_instances="always")

    @model_validator(mode="before")
    @classmethod
    def _strict_property_input(cls, raw: Any) -> Any:
        if isinstance(raw, cls):
            if getattr(raw, "__pydantic_extra__", None):
                raise ValueError("property assertion has extra state")
            raw = vars(raw)
        if isinstance(raw, dict):
            if type(raw.get("assertion_kind")) is not str:
                raise ValueError("V4 assertion kind must be an actual string")
            if raw["assertion_kind"] == "property":
                parse_reviewed_property_literal(raw.get("value"))
        return raw

    @model_validator(mode="after")
    def _property_contract(self) -> Self:
        if self.assertion_kind == "property":
            parse_reviewed_property_literal(self.value)
            if not self.subject_object_id or not self.subject_object_id.strip():
                raise ValueError("property requires a subject")
            if (
                self.object_object_id is not None
                or self.predicate is not None
                or self.label is not None
            ):
                raise ValueError("property references must be explicit outside the literal")
            if not self.evidence_refs:
                raise ValueError("property requires independently bound evidence refs")
        return self


class GraphContributionV4(GraphContributionV2):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always")
    schema_version: Literal["dm_graph_contribution_v4"] = GRAPH_CONTRIBUTION_V4_SCHEMA
    assertions: list[GraphContributionAssertionV4] = []

    @model_validator(mode="after")
    def _source_description_withdrawal_contract(self) -> Self:
        if any(
            c.correction_kind
            is GraphContributionAssertionCorrectionKind.CONTRADICTS_SOURCE_DESCRIPTION
            for c in self.assertion_corrections
        ):
            reason = self.diagnostics.get("source_description_withdrawal_reason")
            if (
                self.source_kind is not ContributionSourceKind.GRAPH_REVIEW
                or not isinstance(reason, str)
                or not reason.strip()
            ):
                raise ValueError(
                    "V4 source-description withdrawal requires Graph review and reason"
                )
        return self

    @model_validator(mode="after")
    def _assertion_scope(self) -> Self:
        for assertion in self.assertions:
            GraphContributionAssertionV4.model_validate(assertion)
            if assertion.campaign_scope != self.campaign_scope:
                raise ValueError("candidate assertion campaign differs from review intent")
        return self

    def partition_assertions(self, state: AcceptanceState) -> list[GraphContributionAssertionV4]:
        return [a for a in self.assertions if a.acceptance_state is state]
