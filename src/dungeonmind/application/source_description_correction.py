"""Host-derived authority for a published extraction description withdrawal.

The proof is an internal, non-wire value. It does not replace finalized review
or writer compare-and-swap. No object or source record is changed here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, NoReturn, cast

from ..contracts.contribution import (
    AcceptanceState,
    ContributionSourceKind,
    GraphContributionAssertionCorrection,
    GraphContributionAssertionCorrectionKind,
    GraphContributionAssertionV3,
    GraphContributionV3,
)
from ..contracts.contribution_review_v2 import (
    NON_MUTATING_IDENTITY_OUTCOMES,
    ContributionReviewRecordV2,
    ContributionReviewStateV2,
)
from ..contracts.contribution_review_v3 import ContributionReviewRecordV3, ContributionReviewStateV3
from ..contracts.evidence import EvidenceRole, SourceDomain
from ..contracts.graph import StoredGraphRevision
from ..domain.canonical import canonical_sha256
from ..domain.errors import ContributionMaterializationError, PersistenceIntegrityError
from .repositories import (
    ContributionReviewRepository,
    FinalizedReviewPublicationRepository,
    WorldGraphRepository,
)

_KIND = GraphContributionAssertionCorrectionKind.CONTRADICTS_SOURCE_DESCRIPTION
_ISSUER = object()


def _fail(reason: str) -> NoReturn:
    raise ContributionMaterializationError(reason)


@dataclass(frozen=True)
class SourceDescriptionCorrectionProof:
    world_id: str
    review_id: str
    contribution_sha256: str
    parent_revision_id: str
    parent_sha256: str
    targets: frozenset[tuple[str, str]]
    _issuer: object = field(repr=False, default=None)

    def matches(
        self,
        state: ContributionReviewStateV2 | ContributionReviewStateV3,
        parent: StoredGraphRevision,
    ) -> bool:
        return (
            self._issuer is _ISSUER
            and self.world_id == state.record.world_id == parent.revision.world_id
            and self.review_id == state.record.review_id
            and self.contribution_sha256 == state.record.reviewed_contribution_sha256
            and self.parent_revision_id == parent.revision.revision_id
            and self.parent_sha256 == canonical_sha256(parent.graph_payload)
            and self.targets
            == frozenset(
                (c.target_contribution_id, c.target_assertion_id)
                for c in state.reviewed_contribution.assertion_corrections
                if c.correction_kind is _KIND
            )
        )

    def admits(
        self,
        record: ContributionReviewRecordV2 | ContributionReviewRecordV3,
        correction: GraphContributionAssertionCorrection,
    ) -> bool:
        return (
            self._issuer is _ISSUER
            and self.review_id == record.review_id
            and self.world_id == record.world_id
            and (correction.target_contribution_id, correction.target_assertion_id) in self.targets
        )


def verify_source_description_corrections(
    state: ContributionReviewStateV2 | ContributionReviewStateV3,
    *,
    parent: StoredGraphRevision,
    world_graph: WorldGraphRepository,
    reviews: ContributionReviewRepository,
    publications: FinalizedReviewPublicationRepository,
) -> SourceDescriptionCorrectionProof | None:
    corrections = [
        c for c in state.reviewed_contribution.assertion_corrections if c.correction_kind is _KIND
    ]
    if not corrections:
        return None
    if not isinstance(state, ContributionReviewStateV3):
        _fail("source_description_correction_requires_v3")
    targets = [(c.target_contribution_id, c.target_assertion_id) for c in corrections]
    if len(set(targets)) != len(targets):
        _fail("source_description_correction_duplicate")
    pending = set(targets)
    found = set()
    suppressed = set()
    world = state.record.world_id
    current_objects = {o["object_id"]: o for o in parent.graph_payload["objects"]}
    current_evidence = {e["evidence_ref_id"]: e for e in parent.graph_payload["evidence_refs"]}
    visited = set()
    revision_id = parent.revision.revision_id
    while revision_id is not None:
        if revision_id in visited:
            raise PersistenceIntegrityError("description correction ancestry cycle")
        visited.add(revision_id)
        stored = world_graph.get_revision(world, revision_id)
        if (
            stored is None
            or stored.revision.world_id != world
            or stored.revision.revision_id != revision_id
            or canonical_sha256(stored.graph_payload) != stored.revision.graph_payload_sha256
        ):
            raise PersistenceIntegrityError("description correction ancestry is incomplete")
        publication = publications.get_for_published_revision(world, revision_id)
        if publication is not None:
            prior = reviews.get(world, publication.review_id)
            if prior is not None:
                try:
                    prior = type(prior).model_validate(prior.model_dump(mode="json"))
                except (TypeError, ValueError):
                    raise PersistenceIntegrityError(
                        "description correction durable review failed reload"
                    ) from None
            if (
                prior is None
                or publication.world_id != world
                or publication.published_revision_id != revision_id
                or publication.expected_parent_revision_id != stored.revision.parent_revision_id
                or publication.graph_payload_sha256 != stored.revision.graph_payload_sha256
                or prior.record.world_id != world
                or prior.record.review_id != publication.review_id
                or prior.record.review_intent_sha256 != publication.review_intent_sha256
                or prior.record.reviewed_contribution_id != publication.reviewed_contribution_id
                or prior.record.reviewed_contribution_sha256
                != publication.reviewed_contribution_sha256
                or canonical_sha256(prior.reviewed_contribution.model_dump(mode="json"))
                != publication.reviewed_contribution_sha256
            ):
                raise PersistenceIntegrityError(
                    "description correction publication binding mismatch"
                )
            contribution = prior.reviewed_contribution
            suppressed.update(
                (c.target_contribution_id, c.target_assertion_id)
                for c in getattr(contribution, "assertion_corrections", ())
            )
            for assertion in contribution.assertions:
                pair = (contribution.contribution_id, assertion.assertion_id)
                if pair not in pending:
                    continue
                if pair in suppressed:
                    _fail("source_description_correction_already_withdrawn")
                if not isinstance(prior, ContributionReviewStateV3):
                    _fail("source_description_correction_target_kind")
                _validate_target(
                    state,
                    cast(GraphContributionV3, contribution),
                    cast(GraphContributionAssertionV3, assertion),
                    current_objects,
                    current_evidence,
                    publications,
                )
                found.add(pair)
        revision_id = stored.revision.parent_revision_id
    if found != pending:
        _fail("source_description_correction_target_unresolvable")
    return SourceDescriptionCorrectionProof(
        world,
        state.record.review_id,
        state.record.reviewed_contribution_sha256,
        parent.revision.revision_id,
        canonical_sha256(parent.graph_payload),
        frozenset(found),
        _ISSUER,
    )


def _validate_target(
    state: ContributionReviewStateV3,
    contribution: GraphContributionV3,
    assertion: GraphContributionAssertionV3,
    objects: dict[str, Any],
    evidence: dict[str, Any],
    publications: FinalizedReviewPublicationRepository,
) -> None:
    if (
        contribution.source_kind is not ContributionSourceKind.EXTRACTION
        or assertion.assertion_kind != "node"
        or assertion.assertion_id.startswith("ka:")
        or assertion.acceptance_state is not AcceptanceState.ACCEPTED
        or assertion.identity_resolution_outcome in NON_MUTATING_IDENTITY_OUTCOMES
        or assertion.subject_object_id not in objects
    ):
        _fail("source_description_correction_target_kind")
    try:
        value = json.loads(assertion.value or "")
    except (TypeError, ValueError):
        _fail("source_description_correction_target_shape")
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("summary"), str)
        or not value["summary"].strip()
        or not isinstance(value.get("kind"), str)
        or not value["kind"].strip()
        or value.get("property_term") is not None
        or value.get("dm_kind") != objects[assertion.subject_object_id]["kind"]
    ):
        _fail("source_description_correction_target_shape")
    artifact = assertion.source_artifact_id or contribution.source_artifact_id
    revision = assertion.source_revision_id or contribution.source_revision_id
    withdrawal = state.reviewed_contribution
    if (
        not artifact
        or not revision
        or not assertion.evidence_refs
        or withdrawal.source_artifact_id != artifact
        or withdrawal.source_revision_id != revision
        or withdrawal.campaign_scope != assertion.campaign_scope
    ):
        _fail("source_description_correction_source_mismatch")
    if any(
        ref.evidence_role is not EvidenceRole.SUPPORT
        or ref.source_domain is not SourceDomain.WORLDBUILDING
        or not ref.source_span_ref_id
        or ref.source_artifact_id != artifact
        or ref.source_revision_id != revision
        or evidence.get(ref.evidence_ref_id) != ref.model_dump(mode="json")
        for ref in assertion.evidence_refs
    ):
        _fail("source_description_correction_evidence_invalid")
    sources = publications.get_provenance_snapshot(
        artifact_ids=(artifact,), revision_ids=(revision,)
    )
    # Reuse the materializer's exact typed source/provenance validation. Local
    # import avoids a module cycle with the proof type consumed by materialization.
    from .review_materialization_v6 import _lift_evidence

    _lift_evidence(assertion, world_id=state.record.world_id, sources=sources)
