"""D&D Threat create-or-connect contribution plan contracts.

A ``DndThreatContributionPlan`` is a non-mutating, candidate-only review
artifact: it reconciles one validated Threat candidate packet against one
exact immutable ``dm_union_graph_v3`` revision and records deterministic
exact-match create-or-connect identity outcomes, explicit existing-object
verifications, relationship plans, and — only when the entire packet is safe
for review — a candidate-only ``GraphContribution`` preview pinned to that
expected parent revision.

Plans are never canonical, never persisted, and never published: no durable
``IdentityDecisionRecord`` is created, no assertion is accepted or rejected,
and nothing appends a contribution, advances a graph head, or publishes a
revision. Records carry IDs, qualified terms, and digests only — never
labels, aliases, summaries, evidence locators, or source prose. Planning
failures raise ``DndContributionPlanningError``; valid-but-unresolvable
states surface as machine-readable blockers.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V3
from dungeonmind.contracts.contribution import (
    AcceptanceState,
    ContributionSourceKind,
    ContributionStatus,
    GraphContribution,
)
from dungeonmind.contracts.identity import IdentityOutcome
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vocabulary import EpistemicKind, Visibility

from .candidates import DndCandidateContractModel
from .vocabulary import DndVocabularyRef

THREAT_CONTRIBUTION_PLAN_SCHEMA = "dmdnd_threat_contribution_plan_v1"
CANDIDATE_RESOLUTION_SCHEMA = "dmdnd_candidate_resolution_v1"
EXISTING_OBJECT_VERIFICATION_SCHEMA = "dmdnd_existing_object_verification_v1"
RELATIONSHIP_PLAN_SCHEMA = "dmdnd_relationship_plan_v1"
PLAN_BLOCKER_SCHEMA = "dmdnd_plan_blocker_v1"

_PLAN_ID = re.compile(r"^plan:[0-9a-f]{32}$")
_PROPOSED_OBJECT_ID = re.compile(r"^obj:[0-9a-f]{32}$")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
# namespace:local — mirrors the kernel term shape; duplicated deliberately
# because the profile package owns its contract surface.
_QUALIFIED_TERM = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*:[a-z0-9]+(?:[._-][a-z0-9]+)*$")

# B.2d plans propose; durable/final outcomes belong to a confirmed successor.
_ALLOWED_OUTCOMES = frozenset(
    {
        IdentityOutcome.RESOLVED_EXISTING,
        IdentityOutcome.PROVISIONAL_NEW,
        IdentityOutcome.AMBIGUOUS,
        IdentityOutcome.BLOCKED_COLLISION,
    }
)


def _validate_term(value: str, *, field_name: str) -> str:
    if not _QUALIFIED_TERM.fullmatch(value):
        raise ValueError(
            f"{field_name} must be a qualified namespace:local term "
            "(lowercase letters, digits, '.', '_', '-')"
        )
    return value


def _require_unique_sorted(values: list[str], *, field_name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must be unique")
    if values != sorted(values):
        raise ValueError(f"{field_name} must be sorted deterministically")


class DndThreatPlanStatus(StrEnum):
    """Lifecycle of one plan: reviewable only when completely blocker-free."""

    READY_FOR_REVIEW = "ready_for_review"
    BLOCKED = "blocked"


class DndExistingObjectVerificationState(StrEnum):
    """Outcome of verifying one explicit existing-object reference."""

    VERIFIED = "verified"
    MISSING = "missing"
    KIND_MISMATCH = "kind_mismatch"


class DndRelationshipPlanState(StrEnum):
    """Planning state of one candidate relationship."""

    READY = "ready"
    ENDPOINT_BLOCKED = "endpoint_blocked"
    DUPLICATE_IN_PACKET = "duplicate_in_packet"
    ALREADY_EXISTS_IN_GRAPH = "already_exists_in_graph"


class DndPlanBlockerCode(StrEnum):
    """Machine-readable reasons a plan cannot be reviewed."""

    AMBIGUOUS_IDENTITY = "ambiguous_identity"
    CROSS_KIND_COLLISION = "cross_kind_collision"
    EXISTING_OBJECT_MISSING = "existing_object_missing"
    EXISTING_OBJECT_KIND_MISMATCH = "existing_object_kind_mismatch"
    RELATIONSHIP_ENDPOINT_BLOCKED = "relationship_endpoint_blocked"
    DUPLICATE_PACKET_RELATIONSHIP = "duplicate_packet_relationship"
    RELATIONSHIP_ALREADY_EXISTS = "relationship_already_exists"


class DndMatchChannel(StrEnum):
    """Exact-match channel through which a graph identity was found."""

    LABEL = "label"
    ALIAS = "alias"


class DndCandidateResolution(DndCandidateContractModel):
    """Identity outcome for one packet node candidate.

    Exact label/alias blocking only. ``resolved_existing`` and
    ``provisional_new`` are proposals; ``ambiguous`` and
    ``blocked_collision`` block the whole plan. No label, alias, or summary
    text is copied into this record.
    """

    schema_version: Literal["dmdnd_candidate_resolution_v1"] = CANDIDATE_RESOLUTION_SCHEMA
    candidate_id: str = Field(min_length=1)
    candidate_kind: str = Field(min_length=1)
    outcome: IdentityOutcome
    target_object_id: str | None = None
    matched_object_ids: list[str] = []
    match_channels: list[DndMatchChannel] = []
    confirmation_required: bool = True

    @field_validator("candidate_kind")
    @classmethod
    def _validate_kind(cls, value: str) -> str:
        return _validate_term(value, field_name="candidate_kind")

    @model_validator(mode="after")
    def _outcome_shape(self) -> Self:
        if self.outcome not in _ALLOWED_OUTCOMES:
            raise ValueError(
                "outcome must be one of resolved_existing, provisional_new, "
                "ambiguous, blocked_collision; durable outcomes are forbidden"
            )
        if not self.confirmation_required:
            raise ValueError("confirmation_required is always true in a plan")
        _require_unique_sorted(self.matched_object_ids, field_name="matched_object_ids")
        if len(set(self.match_channels)) != len(self.match_channels):
            raise ValueError("match_channels must be unique")
        matched = self.matched_object_ids
        channels = self.match_channels
        if matched and not channels:
            raise ValueError("matched objects require at least one match channel")
        if not matched and channels:
            raise ValueError("match channels require at least one matched object")
        if self.outcome is IdentityOutcome.RESOLVED_EXISTING:
            if self.target_object_id is None:
                raise ValueError("resolved_existing requires a target_object_id")
            if matched != [self.target_object_id]:
                raise ValueError(
                    "resolved_existing requires exactly one matched object, "
                    "equal to the target"
                )
        elif self.outcome is IdentityOutcome.PROVISIONAL_NEW:
            if self.target_object_id is None or not _PROPOSED_OBJECT_ID.fullmatch(
                self.target_object_id
            ):
                raise ValueError(
                    "provisional_new requires a deterministic proposed "
                    "target_object_id (obj:<32 lowercase hex>)"
                )
            if matched:
                raise ValueError("provisional_new requires no matched objects")
        elif self.outcome is IdentityOutcome.AMBIGUOUS:
            if self.target_object_id is not None:
                raise ValueError("ambiguous must not carry a target_object_id")
            if len(matched) == 1:
                raise ValueError(
                    "ambiguous requires zero (packet collision) or at least "
                    "two matched objects"
                )
        elif self.outcome is IdentityOutcome.BLOCKED_COLLISION:
            if self.target_object_id is not None:
                raise ValueError("blocked_collision must not carry a target_object_id")
            if not matched:
                raise ValueError(
                    "blocked_collision requires at least one cross-kind match"
                )
        return self


class DndExistingObjectVerification(DndCandidateContractModel):
    """Verification of one explicit ``existing_object_id`` + ``expected_kind``
    endpoint reference against the pinned base revision. Checked by ID only;
    never substituted, never fuzzy-matched."""

    schema_version: Literal["dmdnd_existing_object_verification_v1"] = (
        EXISTING_OBJECT_VERIFICATION_SCHEMA
    )
    existing_object_id: str = Field(min_length=1)
    expected_kind: str = Field(min_length=1)
    actual_kind: str | None = None
    state: DndExistingObjectVerificationState
    relationship_candidate_ids: list[str] = Field(min_length=1)

    @field_validator("expected_kind")
    @classmethod
    def _validate_expected(cls, value: str) -> str:
        return _validate_term(value, field_name="expected_kind")

    @field_validator("actual_kind")
    @classmethod
    def _validate_actual(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_term(value, field_name="actual_kind")

    @model_validator(mode="after")
    def _state_shape(self) -> Self:
        _require_unique_sorted(
            self.relationship_candidate_ids,
            field_name="relationship_candidate_ids",
        )
        if self.state is DndExistingObjectVerificationState.VERIFIED:
            if self.actual_kind != self.expected_kind:
                raise ValueError(
                    "verified requires the actual kind to equal the expected kind"
                )
        elif self.state is DndExistingObjectVerificationState.MISSING:
            if self.actual_kind is not None:
                raise ValueError("missing requires actual_kind to be null")
        elif self.state is DndExistingObjectVerificationState.KIND_MISMATCH and (
            self.actual_kind is None or self.actual_kind == self.expected_kind
        ):
            raise ValueError("kind_mismatch requires a differing actual qualified kind")
        return self


class DndRelationshipPlan(DndCandidateContractModel):
    """Resolved-endpoint plan for one candidate relationship.

    The semantic triple is ``(subject_object_id, predicate,
    object_object_id)``; direction comes entirely from the validated packet
    and is never inverted. Existing graph triples block because evidence
    augmentation semantics are not designed.
    """

    schema_version: Literal["dmdnd_relationship_plan_v1"] = RELATIONSHIP_PLAN_SCHEMA
    relationship_candidate_id: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    subject_object_id: str | None = None
    object_object_id: str | None = None
    state: DndRelationshipPlanState
    existing_relationship_ids: list[str] = []

    @field_validator("predicate")
    @classmethod
    def _validate_predicate(cls, value: str) -> str:
        return _validate_term(value, field_name="predicate")

    @model_validator(mode="after")
    def _state_shape(self) -> Self:
        _require_unique_sorted(
            self.existing_relationship_ids,
            field_name="existing_relationship_ids",
        )
        both = self.subject_object_id is not None and self.object_object_id is not None
        either_missing = self.subject_object_id is None or self.object_object_id is None
        if self.state is DndRelationshipPlanState.READY:
            if not both:
                raise ValueError("ready requires both resolved endpoint object IDs")
            if self.existing_relationship_ids:
                raise ValueError("ready records no existing graph relationship IDs")
        elif self.state is DndRelationshipPlanState.ENDPOINT_BLOCKED:
            if not either_missing:
                raise ValueError(
                    "endpoint_blocked requires at least one missing endpoint ID"
                )
            if self.existing_relationship_ids:
                raise ValueError(
                    "endpoint_blocked records no existing graph relationship IDs"
                )
        elif self.state is DndRelationshipPlanState.DUPLICATE_IN_PACKET:
            if not both:
                raise ValueError(
                    "duplicate_in_packet requires both resolved endpoint IDs"
                )
            if self.existing_relationship_ids:
                raise ValueError(
                    "duplicate_in_packet records no existing graph relationship IDs"
                )
        elif self.state is DndRelationshipPlanState.ALREADY_EXISTS_IN_GRAPH:
            if not both:
                raise ValueError(
                    "already_exists_in_graph requires both resolved endpoint IDs"
                )
            if not self.existing_relationship_ids:
                raise ValueError(
                    "already_exists_in_graph records the exact existing "
                    "relationship IDs"
                )
        return self


class DndPlanBlocker(DndCandidateContractModel):
    """One machine-readable reason a plan cannot be reviewed.

    Fields not relevant to a code remain null/empty; no free-form prose and
    no labels, summaries, aliases, evidence locators, filesystem paths, or
    raw payloads.
    """

    schema_version: Literal["dmdnd_plan_blocker_v1"] = PLAN_BLOCKER_SCHEMA
    code: DndPlanBlockerCode
    candidate_id: str | None = None
    relationship_candidate_id: str | None = None
    object_id: str | None = None
    related_object_ids: list[str] = []

    @model_validator(mode="after")
    def _code_shape(self) -> Self:
        _require_unique_sorted(
            self.related_object_ids, field_name="related_object_ids"
        )
        identity = {
            DndPlanBlockerCode.AMBIGUOUS_IDENTITY,
            DndPlanBlockerCode.CROSS_KIND_COLLISION,
        }
        existing = {
            DndPlanBlockerCode.EXISTING_OBJECT_MISSING,
            DndPlanBlockerCode.EXISTING_OBJECT_KIND_MISMATCH,
        }
        relationship = {
            DndPlanBlockerCode.RELATIONSHIP_ENDPOINT_BLOCKED,
            DndPlanBlockerCode.DUPLICATE_PACKET_RELATIONSHIP,
            DndPlanBlockerCode.RELATIONSHIP_ALREADY_EXISTS,
        }
        if self.code in identity:
            if not self.candidate_id:
                raise ValueError(f"{self.code.value} requires candidate_id")
            if self.relationship_candidate_id is not None or self.object_id is not None:
                raise ValueError(
                    f"{self.code.value} carries no relationship or object fields"
                )
            if (
                self.code is DndPlanBlockerCode.CROSS_KIND_COLLISION
                and not self.related_object_ids
            ):
                raise ValueError(
                    "cross_kind_collision records the cross-kind matched object IDs"
                )
        elif self.code in existing:
            if not self.object_id:
                raise ValueError(f"{self.code.value} requires object_id")
            if self.candidate_id is not None or self.relationship_candidate_id is not None:
                raise ValueError(
                    f"{self.code.value} carries no candidate or relationship fields"
                )
            if self.related_object_ids:
                raise ValueError(f"{self.code.value} records no related object IDs")
        elif self.code in relationship:
            if not self.relationship_candidate_id:
                raise ValueError(f"{self.code.value} requires relationship_candidate_id")
            if self.candidate_id is not None or self.object_id is not None:
                raise ValueError(
                    f"{self.code.value} carries no candidate or object fields"
                )
            if (
                self.code is DndPlanBlockerCode.RELATIONSHIP_ALREADY_EXISTS
                and not self.related_object_ids
            ):
                raise ValueError(
                    "relationship_already_exists records the existing "
                    "relationship IDs"
                )
            if (
                self.code is not DndPlanBlockerCode.RELATIONSHIP_ALREADY_EXISTS
                and self.related_object_ids
            ):
                raise ValueError(f"{self.code.value} records no related object IDs")
        return self


def _blocker_sort_key(blocker: DndPlanBlocker) -> tuple[str, str, str, str]:
    return (
        blocker.code.value,
        blocker.candidate_id or "",
        blocker.relationship_candidate_id or "",
        blocker.object_id or "",
    )


class DndThreatContributionPlan(DndCandidateContractModel):
    """One pinned, deterministic create-or-connect review plan.

    Pins the exact base revision used for planning (``expected_parent``),
    the exact candidate packet digest, and the exact profile/vocabulary
    pins. Contains no graph payload bytes, no current-head metadata, no
    durable identity decisions, and no accepted or rejected assertions.
    """

    schema_version: Literal["dmdnd_threat_contribution_plan_v1"] = (
        THREAT_CONTRIBUTION_PLAN_SCHEMA
    )
    plan_id: str
    world_id: str = Field(min_length=1)
    campaign_id: str | None = Field(default=None, min_length=1)
    packet_id: str = Field(min_length=1)
    candidate_packet_sha256: str
    base_revision_id: str = Field(min_length=1)
    base_graph_schema: str
    base_graph_payload_sha256: str
    expected_parent_revision_id: str = Field(min_length=1)
    semantic_profile: SemanticProfileRef
    vocabulary: DndVocabularyRef
    actor: str = Field(min_length=1)
    planned_at: datetime
    status: DndThreatPlanStatus
    candidate_resolutions: list[DndCandidateResolution] = Field(min_length=1)
    existing_object_verifications: list[DndExistingObjectVerification] = []
    relationship_plans: list[DndRelationshipPlan] = Field(min_length=1)
    blockers: list[DndPlanBlocker] = []
    confirmation_required: bool = True
    proposed_contribution: GraphContribution | None = None

    @field_validator("plan_id")
    @classmethod
    def _validate_plan_id(cls, value: str) -> str:
        if not _PLAN_ID.fullmatch(value):
            raise ValueError("plan_id must be plan:<32 lowercase hex>")
        return value

    @field_validator("candidate_packet_sha256", "base_graph_payload_sha256")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        if not _SHA256_HEX.fullmatch(value):
            raise ValueError("digest fields must be exactly 64 lowercase hex")
        return value

    @field_validator("base_graph_schema")
    @classmethod
    def _validate_base_graph_schema(cls, value: str) -> str:
        if value != GRAPH_SCHEMA_V3:
            raise ValueError(
                f"base_graph_schema must be {GRAPH_SCHEMA_V3!r}; other stored "
                "schemas are not plannable"
            )
        return value

    @field_validator("actor")
    @classmethod
    def _validate_actor(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("actor must be non-blank")
        return value

    @model_validator(mode="after")
    def _plan_invariants(self) -> Self:
        if self.expected_parent_revision_id != self.base_revision_id:
            raise ValueError("expected_parent_revision_id must equal base_revision_id")
        if not self.confirmation_required:
            raise ValueError("confirmation_required is always true")

        resolution_ids = [r.candidate_id for r in self.candidate_resolutions]
        _require_unique_sorted(resolution_ids, field_name="candidate_resolutions")
        verification_keys = [
            (v.existing_object_id, v.expected_kind)
            for v in self.existing_object_verifications
        ]
        if len(set(verification_keys)) != len(verification_keys):
            raise ValueError(
                "existing_object_verifications must be unique per "
                "(existing_object_id, expected_kind)"
            )
        if verification_keys != sorted(verification_keys):
            raise ValueError(
                "existing_object_verifications must be sorted deterministically"
            )
        relationship_ids = [p.relationship_candidate_id for p in self.relationship_plans]
        _require_unique_sorted(relationship_ids, field_name="relationship_plans")
        if self.blockers != sorted(self.blockers, key=_blocker_sort_key):
            raise ValueError("blockers must be sorted deterministically")

        self._require_blocker_correspondence()
        self._require_status_shape()
        self._require_candidate_only_preview()
        return self

    def _require_blocker_correspondence(self) -> None:
        """Every blocked/bad record has exactly its blocker, and every
        blocker names a real bad record (no orphans)."""
        blocker_keys = {
            (b.code, b.candidate_id, b.relationship_candidate_id, b.object_id)
            for b in self.blockers
        }

        def _need(key: tuple[DndPlanBlockerCode, str | None, str | None, str | None]) -> None:
            if key not in blocker_keys:
                raise ValueError(f"missing blocker for {key[0].value}: {key[1:]}")

        for resolution in self.candidate_resolutions:
            if resolution.outcome is IdentityOutcome.AMBIGUOUS:
                _need(
                    (
                        DndPlanBlockerCode.AMBIGUOUS_IDENTITY,
                        resolution.candidate_id,
                        None,
                        None,
                    )
                )
            elif resolution.outcome is IdentityOutcome.BLOCKED_COLLISION:
                _need(
                    (
                        DndPlanBlockerCode.CROSS_KIND_COLLISION,
                        resolution.candidate_id,
                        None,
                        None,
                    )
                )
        for verification in self.existing_object_verifications:
            if verification.state is DndExistingObjectVerificationState.MISSING:
                _need(
                    (
                        DndPlanBlockerCode.EXISTING_OBJECT_MISSING,
                        None,
                        None,
                        verification.existing_object_id,
                    )
                )
            elif verification.state is DndExistingObjectVerificationState.KIND_MISMATCH:
                _need(
                    (
                        DndPlanBlockerCode.EXISTING_OBJECT_KIND_MISMATCH,
                        None,
                        None,
                        verification.existing_object_id,
                    )
                )
        for plan in self.relationship_plans:
            if plan.state is DndRelationshipPlanState.ENDPOINT_BLOCKED:
                _need(
                    (
                        DndPlanBlockerCode.RELATIONSHIP_ENDPOINT_BLOCKED,
                        None,
                        plan.relationship_candidate_id,
                        None,
                    )
                )
            elif plan.state is DndRelationshipPlanState.DUPLICATE_IN_PACKET:
                _need(
                    (
                        DndPlanBlockerCode.DUPLICATE_PACKET_RELATIONSHIP,
                        None,
                        plan.relationship_candidate_id,
                        None,
                    )
                )
            elif plan.state is DndRelationshipPlanState.ALREADY_EXISTS_IN_GRAPH:
                _need(
                    (
                        DndPlanBlockerCode.RELATIONSHIP_ALREADY_EXISTS,
                        None,
                        plan.relationship_candidate_id,
                        None,
                    )
                )

        resolutions = {r.candidate_id: r for r in self.candidate_resolutions}
        verifications = {
            v.existing_object_id: v for v in self.existing_object_verifications
        }
        plans = {p.relationship_candidate_id: p for p in self.relationship_plans}
        for blocker in self.blockers:
            code = blocker.code
            if code is DndPlanBlockerCode.AMBIGUOUS_IDENTITY:
                target = resolutions.get(blocker.candidate_id or "")
                if target is None or target.outcome is not IdentityOutcome.AMBIGUOUS:
                    raise ValueError("orphan ambiguous_identity blocker")
            elif code is DndPlanBlockerCode.CROSS_KIND_COLLISION:
                target = resolutions.get(blocker.candidate_id or "")
                if target is None or target.outcome is not IdentityOutcome.BLOCKED_COLLISION:
                    raise ValueError("orphan cross_kind_collision blocker")
            elif code is DndPlanBlockerCode.EXISTING_OBJECT_MISSING:
                target = verifications.get(blocker.object_id or "")
                if target is None or target.state is not (
                    DndExistingObjectVerificationState.MISSING
                ):
                    raise ValueError("orphan existing_object_missing blocker")
            elif code is DndPlanBlockerCode.EXISTING_OBJECT_KIND_MISMATCH:
                target = verifications.get(blocker.object_id or "")
                if target is None or target.state is not (
                    DndExistingObjectVerificationState.KIND_MISMATCH
                ):
                    raise ValueError("orphan existing_object_kind_mismatch blocker")
            else:
                target = plans.get(blocker.relationship_candidate_id or "")
                expected = {
                    DndPlanBlockerCode.RELATIONSHIP_ENDPOINT_BLOCKED: (
                        DndRelationshipPlanState.ENDPOINT_BLOCKED
                    ),
                    DndPlanBlockerCode.DUPLICATE_PACKET_RELATIONSHIP: (
                        DndRelationshipPlanState.DUPLICATE_IN_PACKET
                    ),
                    DndPlanBlockerCode.RELATIONSHIP_ALREADY_EXISTS: (
                        DndRelationshipPlanState.ALREADY_EXISTS_IN_GRAPH
                    ),
                }[code]
                if target is None or target.state is not expected:
                    raise ValueError(f"orphan {code.value} blocker")

    def _require_status_shape(self) -> None:
        if self.status is DndThreatPlanStatus.READY_FOR_REVIEW:
            if self.blockers:
                raise ValueError("ready_for_review requires zero blockers")
            if self.proposed_contribution is None:
                raise ValueError(
                    "ready_for_review requires a proposed_contribution preview"
                )
            for resolution in self.candidate_resolutions:
                if resolution.outcome not in (
                    IdentityOutcome.RESOLVED_EXISTING,
                    IdentityOutcome.PROVISIONAL_NEW,
                ):
                    raise ValueError(
                        "ready_for_review requires every node outcome to be "
                        "resolved_existing or provisional_new"
                    )
            for verification in self.existing_object_verifications:
                if verification.state is not DndExistingObjectVerificationState.VERIFIED:
                    raise ValueError(
                        "ready_for_review requires every explicit endpoint "
                        "to be verified"
                    )
            for plan in self.relationship_plans:
                if plan.state is not DndRelationshipPlanState.READY:
                    raise ValueError(
                        "ready_for_review requires every relationship to be ready"
                    )
        elif self.status is DndThreatPlanStatus.BLOCKED:
            if not self.blockers:
                raise ValueError("blocked requires at least one blocker")
            if self.proposed_contribution is not None:
                raise ValueError("blocked plans contain no contribution preview")

    def _require_candidate_only_preview(self) -> None:
        contribution = self.proposed_contribution
        if contribution is None:
            return
        if contribution.world_id != self.world_id:
            raise ValueError("contribution world must equal the plan world")
        if contribution.campaign_scope != self.campaign_id:
            raise ValueError("contribution campaign scope must equal the plan campaign")
        if contribution.source_kind is not ContributionSourceKind.EXTRACTION:
            raise ValueError("planned contributions are extraction-sourced")
        if contribution.status is not ContributionStatus.ACTIVE:
            raise ValueError("planned contributions are active-if-appended")
        if contribution.supersedes_contribution_id is not None:
            raise ValueError("planned contributions supersede nothing")
        if contribution.identity_decision_ids:
            raise ValueError("planned contributions contain no identity decisions")
        if contribution.unresolved_mentions:
            raise ValueError("planned contributions contain no unresolved mentions")
        if contribution.diagnostics:
            raise ValueError("planned contributions contain no diagnostics")
        for assertion in contribution.assertions:
            if assertion.acceptance_state is not AcceptanceState.CANDIDATE:
                raise ValueError(
                    "every planned assertion remains candidate; accepted or "
                    "rejected assertions are forbidden"
                )
            if assertion.visibility is not Visibility.GM:
                raise ValueError("every planned assertion is GM-visible only")
            if assertion.epistemic_kind is not EpistemicKind.ASSERTED:
                raise ValueError("every planned assertion is asserted")
   