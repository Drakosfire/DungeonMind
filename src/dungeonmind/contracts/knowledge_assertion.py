"""Shared knowledge-assertion metadata for assertion-scoped world graphs.

``dm_union_graph_v4`` attaches one of these records to every independently
durable assertion (object existence, alias, summary, property, relationship)
so campaign scope, audience visibility, epistemic standing, canon standing,
evidence, session references, and *explicit* temporal knowledge state travel
together instead of being inferred from position or order.

Three deliberate separations are encoded here:

* **Session references are not fictional time.** ``session_refs`` records the
  real-world sessions an assertion surfaced in. It never implies when the
  asserted content happened in the fiction, and nothing derives
  ``temporal_scope`` from it.
* **``unknown`` temporal scope is not ``world_timeless``.** "We have not
  established when this holds" and "this holds independent of fictional time"
  are different claims and must stay distinguishable.
* **The versioned epistemic vocabulary is not the historical enum.**
  :class:`EpistemicKindV2` is a superset *vocabulary*, not a remapping:
  ``fact`` is not an alias for ``asserted`` and ``source_derived_candidate``
  is not an alias for ``inferred``. The historical
  :class:`~dungeonmind.contracts.vocabulary.EpistemicKind` keeps its own
  meaning for v1-v3 records and is never narrowed or mutated.

``campaign_scope`` is required-but-nullable: the key must always be present,
``None`` means world-universal, and a blank string fails closed. It scopes
*knowledge*, never identity — an object's ``object_id`` never changes because
an assertion about it is campaign-scoped.

When ``temporal_scope.kind`` is ``fictional_time_ref``, the target is an exact
:class:`~dungeonmind.contracts.fictional_time.FictionalTimeAnchorRefV1` into the
existing fictional-time authority (``bundle_id`` + ``campaign_id`` +
``anchor_id``). Opaque strings are not accepted.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import DungeonMindModel
from .fictional_time import FictionalTimeAnchorRefV1
from .vocabulary import CanonState, Visibility

TEMPORAL_SCOPE_REF_SCHEMA = "dm_temporal_scope_ref_v1"
KNOWLEDGE_ASSERTION_METADATA_SCHEMA = "dm_knowledge_assertion_metadata_v1"


class TemporalScopeKind(StrEnum):
    """Explicit temporal knowledge state of an assertion. Never inferred."""

    # We have not established when (or whether) this holds in fictional time.
    UNKNOWN = "unknown"
    # Holds independent of fictional time; distinct from UNKNOWN.
    WORLD_TIMELESS = "world_timeless"
    # Anchored to an exact FictionalTimeAnchor inside a named claim bundle.
    FICTIONAL_TIME_REF = "fictional_time_ref"


class EpistemicKindV2(StrEnum):
    """Versioned epistemic vocabulary for assertion-scoped graphs.

    A superset vocabulary, not a remapping of the historical enum: ``fact``
    and ``asserted`` are distinct members, as are ``source_derived_candidate``
    and ``inferred``. Producers choose one; the kernel never equates them.
    """

    ASSERTED = "asserted"
    INFERRED = "inferred"
    SPECULATIVE = "speculative"
    FACT = "fact"
    SOURCE_DERIVED_CANDIDATE = "source_derived_candidate"


def _reject_blank(value: str, label: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{label} must be a non-blank string")


def _reject_blank_or_duplicate(values: list[str], label: str) -> None:
    seen: set[str] = set()
    for value in values:
        _reject_blank(value, label)
        if value in seen:
            raise ValueError(f"duplicate {label}: {value}")
        seen.add(value)


class TemporalScopeRefV1(DungeonMindModel):
    """Explicit temporal knowledge state for one assertion.

    ``fictional_time_ref`` is an exact typed pointer into
    ``dm_fictional_time_claim_bundle_v1`` (one anchor inside one bundle). This
    model carries no chronology logic and never competes with fictional-time
    query evaluation.
    """

    schema_version: Literal["dm_temporal_scope_ref_v1"] = TEMPORAL_SCOPE_REF_SCHEMA
    kind: TemporalScopeKind
    fictional_time_ref: FictionalTimeAnchorRefV1 | None = None

    @model_validator(mode="after")
    def _ref_required_iff_fictional_time(self) -> Self:
        if self.kind is TemporalScopeKind.FICTIONAL_TIME_REF:
            if self.fictional_time_ref is None:
                raise ValueError(
                    "temporal_scope kind 'fictional_time_ref' requires fictional_time_ref"
                )
        elif self.fictional_time_ref is not None:
            raise ValueError(
                f"temporal_scope kind {self.kind.value!r} must not carry "
                "fictional_time_ref"
            )
        return self


class KnowledgeAssertionMetadataV1(DungeonMindModel):
    """Metadata every independently durable assertion must carry.

    Every field below is required (``campaign_scope`` required-but-nullable).
    There are no defaults for visibility, epistemic kind, or canon state:
    omitted audience or standing fails closed rather than silently becoming
    the most permissive value.

    ``evidence_ref_ids`` must be non-empty at the contract boundary. Graph
    readers retain a separate check that each listed id resolves inside the
    payload evidence ledger.
    """

    schema_version: Literal["dm_knowledge_assertion_metadata_v1"] = (
        KNOWLEDGE_ASSERTION_METADATA_SCHEMA
    )
    assertion_id: str
    # Required key. ``None`` = world-universal knowledge; blank string fails.
    campaign_scope: str | None
    visibility: Visibility
    epistemic_kind: EpistemicKindV2
    canon_state: CanonState
    evidence_ref_ids: list[str] = Field(min_length=1)
    # Real-world sessions this assertion surfaced in. Never fictional time.
    session_refs: list[str]
    temporal_scope: TemporalScopeRefV1

    @model_validator(mode="after")
    def _validate_metadata(self) -> Self:
        _reject_blank(self.assertion_id, "assertion_id")
        if self.campaign_scope is not None:
            _reject_blank(self.campaign_scope, "campaign_scope")
        _reject_blank_or_duplicate(self.evidence_ref_ids, "evidence_ref_id")
        _reject_blank_or_duplicate(self.session_refs, "session_ref")
        if (
            self.temporal_scope.kind is TemporalScopeKind.FICTIONAL_TIME_REF
            and self.temporal_scope.fictional_time_ref is not None
            and self.campaign_scope is not None
            and self.campaign_scope
            != self.temporal_scope.fictional_time_ref.campaign_id
        ):
            raise ValueError(
                "campaign_scope must be null (world-universal) or equal "
                "fictional_time_ref.campaign_id"
            )
        return self
