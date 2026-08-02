"""Pure, non-mutating D&D Threat create-or-connect contribution planning.

Repository-blind graph awareness: the caller supplies one exact
``StoredGraphRevision`` (fetched through DungeonMind repositories by the
caller, never by this package) and a configured ``GraphSnapshotReader``.
This planner verifies envelope/payload/world/schema/profile integrity,
performs deterministic exact label/alias identity blocking, verifies every
explicit existing-object endpoint by ID, plans relationship endpoints with
duplicate-triple detection, and emits a ``DndThreatContributionPlan`` whose
candidate-only ``GraphContribution`` preview exists only when the entire
packet is safe for review.

Nothing here appends a contribution, records a durable identity decision,
advances a graph head, or publishes a revision. There is no fuzzy, semantic,
embedding, LLM, or confidence-based matching anywhere in this module. All
failures raise ``DndContributionPlanningError`` sanitized per the package
failure model: IDs, qualified terms, and digests only — never labels,
aliases, summaries, source or graph prose, evidence locators, raw payloads,
filesystem paths, Pydantic ``errors()`` records, or chained parser
exceptions.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V3,
    GraphSnapshotReader,
    ParsedGraphSnapshot,
)
from dungeonmind.contracts.contribution import (
    AcceptanceState,
    ContributionSourceKind,
    ContributionStatus,
    GraphContribution,
    GraphContributionAssertion,
)
from dungeonmind.contracts.evidence import EvidenceRef
from dungeonmind.contracts.graph import StoredGraphRevision
from dungeonmind.contracts.identity import IdentityOutcome
from dungeonmind.contracts.vocabulary import EpistemicKind, Visibility
from dungeonmind.domain.canonical import canonical_sha256

from ..contracts.candidates import (
    DndCandidateEndpointRef,
    DndThreatCandidatePacket,
)
from ..contracts.contribution_planning import (
    DndCandidateResolution,
    DndExistingObjectVerification,
    DndExistingObjectVerificationState,
    DndMatchChannel,
    DndPlanBlocker,
    DndPlanBlockerCode,
    DndRelationshipPlan,
    DndRelationshipPlanState,
    DndThreatContributionPlan,
    DndThreatPlanStatus,
    derive_assertion_id,
    derive_contribution_id,
    derive_plan_id,
    derive_preview_content_sha256,
    derive_proposed_object_id,
    format_extraction_profile,
)
from ..domain.errors import (
    DndCandidateValidationError,
    DndContributionPlanningError,
    DndVocabularyIntegrityError,
)
from .threat_candidates import (
    parse_threat_candidate_packet,
    validate_threat_candidate_packet,
)


def _norm(term: str) -> str:
    """Identity-term normalization, identical to the graph index rule."""
    return term.casefold().strip()


def _error_messages(exc: ValidationError) -> list[str]:
    """Validator message strings only — never rejected input values."""
    messages = [str(err.get("msg", "invalid")) for err in exc.errors()]
    return list(dict.fromkeys(messages))


def _candidate_terms(packet: DndThreatCandidatePacket) -> dict[str, list[str]]:
    """Normalized exact-match material per candidate: label first, then
    ordered surface forms, deduplicated after normalization."""
    terms: dict[str, list[str]] = {}
    for node in packet.nodes:
        ordered = [_norm(node.label), *(_norm(form) for form in node.surface_forms)]
        terms[node.candidate_id] = list(dict.fromkeys(ordered))
    return terms


def _parse_and_validate_packet(
    payload: Mapping[str, Any] | DndThreatCandidatePacket,
) -> DndThreatCandidatePacket:
    """Steps 1-2: sanitizing parse plus authoritative-catalog validation."""
    try:
        packet = parse_threat_candidate_packet(payload)
        return validate_threat_candidate_packet(packet)
    except DndCandidateValidationError as exc:
        messages = exc.details.get("messages", [str(exc)])
        raise DndContributionPlanningError(
            "candidate packet failed validation",
            details={"reason": "candidate_validation", "messages": list(messages)},
        ) from None
    except DndVocabularyIntegrityError as exc:
        raise DndContributionPlanningError(
            "candidate vocabulary integrity failure",
            details={"reason": type(exc).__name__},
        ) from None


def _verify_revision_integrity(
    packet: DndThreatCandidatePacket,
    stored_revision: StoredGraphRevision,
) -> None:
    """Steps 3-5: envelope digest, world agreement, exact schema."""
    revision = stored_revision.revision
    actual_digest = canonical_sha256(stored_revision.graph_payload)
    if actual_digest != revision.graph_payload_sha256:
        raise DndContributionPlanningError(
            "graph payload digest does not match the revision envelope",
            details={
                "revision_id": revision.revision_id,
                "envelope_sha256": revision.graph_payload_sha256,
                "actual_sha256": actual_digest,
            },
        )
    payload_world = stored_revision.graph_payload.get("world_id")
    if not isinstance(payload_world, str) or not payload_world:
        raise DndContributionPlanningError(
            "stored graph payload is missing its world identity",
            details={"revision_id": revision.revision_id},
        )
    if payload_world != revision.world_id:
        raise DndContributionPlanningError(
            "stored graph payload world differs from the revision envelope world",
            details={
                "revision_id": revision.revision_id,
                "envelope_world_id": revision.world_id,
                "payload_world_id": payload_world,
            },
        )
    if packet.world_id != revision.world_id:
        raise DndContributionPlanningError(
            "candidate packet world differs from the stored revision world",
            details={
                "packet_id": packet.packet_id,
                "revision_id": revision.revision_id,
                "packet_world_id": packet.world_id,
                "revision_world_id": revision.world_id,
            },
        )
    if revision.graph_schema != GRAPH_SCHEMA_V3:
        raise DndContributionPlanningError(
            "stored graph schema is not plannable",
            details={
                "revision_id": revision.revision_id,
                "graph_schema": revision.graph_schema,
                "expected_graph_schema": GRAPH_SCHEMA_V3,
            },
        )


def _parse_full_snapshot(
    stored_revision: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
) -> ParsedGraphSnapshot:
    """Step 6: parse the complete stored payload through the supplied reader.

    A caller-scoped snapshot is structurally impossible here: the raw stored
    payload is parsed in full so no existing object can be hidden behind a
    scope. Reader failures are wrapped and unchained — kernel parser errors
    may embed rejected graph records (labels, summaries, locators).
    """
    try:
        return graph_reader.parse(
            graph_schema=stored_revision.revision.graph_schema,
            graph_payload=stored_revision.graph_payload,
        )
    except Exception as exc:
        raise DndContributionPlanningError(
            "stored graph payload could not be parsed",
            details={"reason": type(exc).__name__},
        ) from None


def _require_profile_match(
    packet: DndThreatCandidatePacket,
    snapshot: ParsedGraphSnapshot,
) -> None:
    """Step 7: the graph and the packet pin the exact same profile revision."""
    graph_ref = snapshot.semantic_profile_ref
    if graph_ref is None:
        raise DndContributionPlanningError(
            "stored graph carries no semantic profile ref",
            details={"packet_id": packet.packet_id},
        )
    if graph_ref != packet.semantic_profile:
        raise DndContributionPlanningError(
            "graph profile ref differs from the candidate packet profile ref",
            details={
                "packet_id": packet.packet_id,
                "profile_id": packet.semantic_profile.profile_id,
                "packet_profile_revision": packet.semantic_profile.profile_revision,
                "graph_profile_revision": graph_ref.profile_revision,
            },
        )


def _resolve_candidates(
    packet: DndThreatCandidatePacket,
    snapshot: ParsedGraphSnapshot,
    packet_digest: str,
) -> list[DndCandidateResolution]:
    """Step 8: exact label/alias blocking with the conservative outcome matrix.

    Candidate-to-candidate identity-term collisions are detected before any
    graph matching and make every colliding candidate ambiguous.
    """
    terms = _candidate_terms(packet)
    candidate_ids = [node.candidate_id for node in packet.nodes]
    colliding: set[str] = set()
    for index, first in enumerate(candidate_ids):
        for second in candidate_ids[index + 1 :]:
            if set(terms[first]) & set(terms[second]):
                colliding.add(first)
                colliding.add(second)

    resolutions: list[DndCandidateResolution] = []
    for node in packet.nodes:
        if node.candidate_id in colliding:
            resolutions.append(
                DndCandidateResolution(
                    candidate_id=node.candidate_id,
                    candidate_kind=node.kind,
                    outcome=IdentityOutcome.AMBIGUOUS,
                )
            )
            continue

        channels_by_object: dict[str, set[DndMatchChannel]] = {}
        for term in terms[node.candidate_id]:
            for object_id in snapshot.label_index.get(term, []):
                channels_by_object.setdefault(object_id, set()).add(DndMatchChannel.LABEL)
            for object_id in snapshot.alias_index.get(term, []):
                channels_by_object.setdefault(object_id, set()).add(DndMatchChannel.ALIAS)
        matched_ids = sorted(channels_by_object)
        channels = sorted(
            {channel for hits in channels_by_object.values() for channel in hits}
        )

        if not matched_ids:
            resolutions.append(
                DndCandidateResolution(
                    candidate_id=node.candidate_id,
                    candidate_kind=node.kind,
                    outcome=IdentityOutcome.PROVISIONAL_NEW,
                    target_object_id=derive_proposed_object_id(
                        world_id=packet.world_id,
                        packet_digest=packet_digest,
                        candidate_id=node.candidate_id,
                    ),
                )
            )
            continue
        matched_kinds = {snapshot.objects[oid].kind for oid in matched_ids}
        if any(kind != node.kind for kind in matched_kinds):
            # Conservative: any cross-kind exact match blocks; never "pick
            # the likely one", even with exactly one same-kind match present.
            resolutions.append(
                DndCandidateResolution(
                    candidate_id=node.candidate_id,
                    candidate_kind=node.kind,
                    outcome=IdentityOutcome.BLOCKED_COLLISION,
                    matched_object_ids=matched_ids,
                    match_channels=channels,
                )
            )
        elif len(matched_ids) == 1:
            resolutions.append(
                DndCandidateResolution(
                    candidate_id=node.candidate_id,
                    candidate_kind=node.kind,
                    outcome=IdentityOutcome.RESOLVED_EXISTING,
                    target_object_id=matched_ids[0],
                    matched_object_ids=matched_ids,
                    match_channels=channels,
                )
            )
        else:
            resolutions.append(
                DndCandidateResolution(
                    candidate_id=node.candidate_id,
                    candidate_kind=node.kind,
                    outcome=IdentityOutcome.AMBIGUOUS,
                    matched_object_ids=matched_ids,
                    match_channels=channels,
                )
            )

    proposed = [
        resolution
        for resolution in resolutions
        if resolution.outcome is IdentityOutcome.PROVISIONAL_NEW
    ]
    proposed_ids = [resolution.target_object_id for resolution in proposed]
    if len(set(proposed_ids)) != len(proposed_ids):
        raise DndContributionPlanningError(
            "two candidates produced the same proposed object identity",
            details={"packet_id": packet.packet_id},
        )
    existing_ids = set(snapshot.objects)
    for resolution in proposed:
        if resolution.target_object_id in existing_ids:
            raise DndContributionPlanningError(
                "proposed object identity collides with an existing graph object",
                details={
                    "packet_id": packet.packet_id,
                    "candidate_id": resolution.candidate_id,
                    "object_id": resolution.target_object_id,
                },
            )
    return resolutions


def _verify_existing_endpoints(
    packet: DndThreatCandidatePacket,
    snapshot: ParsedGraphSnapshot,
) -> list[DndExistingObjectVerification]:
    """Step 9: explicit existing-object references are checked by exact ID
    and exact kind only — never substituted, never label-matched."""
    endpoints: list[tuple[str, str]] = []
    relationship_ids: dict[tuple[str, str], list[str]] = {}
    for relationship in packet.relationships:
        for endpoint in (relationship.subject, relationship.object):
            if endpoint.existing_object_id is None:
                continue
            key = (endpoint.existing_object_id, endpoint.expected_kind or "")
            if key not in relationship_ids:
                endpoints.append(key)
                relationship_ids[key] = []
            relationship_ids[key].append(relationship.candidate_id)

    verifications: list[DndExistingObjectVerification] = []
    for object_id, expected_kind in endpoints:
        graph_object = snapshot.objects.get(object_id)
        if graph_object is None:
            state = DndExistingObjectVerificationState.MISSING
            actual_kind = None
        elif graph_object.kind != expected_kind:
            state = DndExistingObjectVerificationState.KIND_MISMATCH
            actual_kind = graph_object.kind
        else:
            state = DndExistingObjectVerificationState.VERIFIED
            actual_kind = graph_object.kind
        verifications.append(
            DndExistingObjectVerification(
                existing_object_id=object_id,
                expected_kind=expected_kind,
                actual_kind=actual_kind,
                state=state,
                relationship_candidate_ids=sorted(relationship_ids[(object_id, expected_kind)]),
            )
        )
    return verifications


def _plan_relationships(
    packet: DndThreatCandidatePacket,
    resolutions: list[DndCandidateResolution],
    verifications: list[DndExistingObjectVerification],
    snapshot: ParsedGraphSnapshot,
) -> list[DndRelationshipPlan]:
    """Step 10: resolve endpoints, then detect duplicate packet triples and
    pre-existing graph triples. Direction comes only from the packet."""
    target_by_candidate = {
        resolution.candidate_id: resolution.target_object_id
        for resolution in resolutions
    }
    verified = {
        (verification.existing_object_id, verification.expected_kind)
        for verification in verifications
        if verification.state is DndExistingObjectVerificationState.VERIFIED
    }

    def _endpoint_object_id(endpoint: DndCandidateEndpointRef) -> str | None:
        if endpoint.candidate_id is not None:
            return target_by_candidate[endpoint.candidate_id]
        key = (endpoint.existing_object_id or "", endpoint.expected_kind or "")
        if key not in verified:
            return None
        return endpoint.existing_object_id

    resolved: dict[str, tuple[str | None, str | None]] = {}
    for relationship in packet.relationships:
        resolved[relationship.candidate_id] = (
            _endpoint_object_id(relationship.subject),
            _endpoint_object_id(relationship.object),
        )

    graph_triples: dict[tuple[str, str, str], list[str]] = {}
    for graph_relationship in snapshot.relationships.values():
        key = (
            graph_relationship.subject_object_id,
            graph_relationship.predicate,
            graph_relationship.object_object_id,
        )
        graph_triples.setdefault(key, []).append(graph_relationship.relationship_id)
    for relationship_ids in graph_triples.values():
        relationship_ids.sort()

    packet_triples: Counter[tuple[str, str, str]] = Counter()
    for relationship in packet.relationships:
        subject_id, object_id = resolved[relationship.candidate_id]
        if subject_id is None or object_id is None:
            continue
        packet_triples[(subject_id, relationship.predicate, object_id)] += 1

    plans: list[DndRelationshipPlan] = []
    for relationship in packet.relationships:
        subject_id, object_id = resolved[relationship.candidate_id]
        if subject_id is None or object_id is None:
            state = DndRelationshipPlanState.ENDPOINT_BLOCKED
            existing: list[str] = []
        else:
            triple = (subject_id, relationship.predicate, object_id)
            if packet_triples[triple] > 1:
                state = DndRelationshipPlanState.DUPLICATE_IN_PACKET
                existing = []
            elif triple in graph_triples:
                state = DndRelationshipPlanState.ALREADY_EXISTS_IN_GRAPH
                existing = graph_triples[triple]
            else:
                state = DndRelationshipPlanState.READY
                existing = []
        plans.append(
            DndRelationshipPlan(
                relationship_candidate_id=relationship.candidate_id,
                predicate=relationship.predicate,
                subject_object_id=subject_id,
                object_object_id=object_id,
                state=state,
                existing_relationship_ids=existing,
            )
        )
    return plans


def _collect_blockers(
    resolutions: list[DndCandidateResolution],
    verifications: list[DndExistingObjectVerification],
    relationship_plans: list[DndRelationshipPlan],
) -> list[DndPlanBlocker]:
    """Step 11: one blocker per non-reviewable record, deterministically
    sorted. Blockers carry IDs only."""
    blockers: list[DndPlanBlocker] = []
    for resolution in resolutions:
        if resolution.outcome is IdentityOutcome.AMBIGUOUS:
            blockers.append(
                DndPlanBlocker(
                    code=DndPlanBlockerCode.AMBIGUOUS_IDENTITY,
                    candidate_id=resolution.candidate_id,
                    related_object_ids=list(resolution.matched_object_ids),
                )
            )
        elif resolution.outcome is IdentityOutcome.BLOCKED_COLLISION:
            blockers.append(
                DndPlanBlocker(
                    code=DndPlanBlockerCode.CROSS_KIND_COLLISION,
                    candidate_id=resolution.candidate_id,
                    related_object_ids=list(resolution.matched_object_ids),
                )
            )
    for verification in verifications:
        if verification.state is DndExistingObjectVerificationState.MISSING:
            blockers.append(
                DndPlanBlocker(
                    code=DndPlanBlockerCode.EXISTING_OBJECT_MISSING,
                    object_id=verification.existing_object_id,
                    expected_kind=verification.expected_kind,
                )
            )
        elif verification.state is DndExistingObjectVerificationState.KIND_MISMATCH:
            blockers.append(
                DndPlanBlocker(
                    code=DndPlanBlockerCode.EXISTING_OBJECT_KIND_MISMATCH,
                    object_id=verification.existing_object_id,
                    expected_kind=verification.expected_kind,
                )
            )
    for plan in relationship_plans:
        if plan.state is DndRelationshipPlanState.ENDPOINT_BLOCKED:
            blockers.append(
                DndPlanBlocker(
                    code=DndPlanBlockerCode.RELATIONSHIP_ENDPOINT_BLOCKED,
                    relationship_candidate_id=plan.relationship_candidate_id,
                )
            )
        elif plan.state is DndRelationshipPlanState.DUPLICATE_IN_PACKET:
            blockers.append(
                DndPlanBlocker(
                    code=DndPlanBlockerCode.DUPLICATE_PACKET_RELATIONSHIP,
                    relationship_candidate_id=plan.relationship_candidate_id,
                )
            )
        elif plan.state is DndRelationshipPlanState.ALREADY_EXISTS_IN_GRAPH:
            blockers.append(
                DndPlanBlocker(
                    code=DndPlanBlockerCode.RELATIONSHIP_ALREADY_EXISTS,
                    relationship_candidate_id=plan.relationship_candidate_id,
                    related_object_ids=list(plan.existing_relationship_ids),
                )
            )
    blockers.sort(
        key=lambda blocker: (
            blocker.code.value,
            blocker.candidate_id or "",
            blocker.relationship_candidate_id or "",
            blocker.object_id or "",
            blocker.expected_kind or "",
        )
    )
    return blockers


def _node_field_assertion(
    packet: DndThreatCandidatePacket,
    *,
    contribution_id: str,
    candidate_id: str,
    target_object_id: str,
    outcome: IdentityOutcome,
    evidence_refs: list[EvidenceRef],
    assertion_kind: str,
    discriminator: str,
    label: str | None = None,
    value: str | None = None,
) -> GraphContributionAssertion:
    return GraphContributionAssertion(
        assertion_id=derive_assertion_id(
            contribution_id=contribution_id,
            candidate_id=candidate_id,
            assertion_kind=assertion_kind,
            discriminator=discriminator,
        ),
        assertion_kind=assertion_kind,
        subject_object_id=target_object_id,
        label=label,
        value=value,
        evidence_refs=evidence_refs,
        source_artifact_id=packet.source_artifact_id,
        source_revision_id=packet.source_revision_id,
        campaign_scope=packet.campaign_id,
        visibility=Visibility.GM,
        epistemic_kind=EpistemicKind.ASSERTED,
        acceptance_state=AcceptanceState.CANDIDATE,
        identity_resolution_outcome=outcome,
    )


def _node_assertions(
    packet: DndThreatCandidatePacket,
    resolution_by_candidate: dict[str, DndCandidateResolution],
    evidence_by_id: dict[str, EvidenceRef],
    contribution_id: str,
) -> list[GraphContributionAssertion]:
    """Label, then aliases in packet order (excluding label-equivalent
    forms), then summary — per node in packet order. Every assertion is
    candidate, GM-visible, asserted, and carries the node's exact evidence."""
    assertions: list[GraphContributionAssertion] = []
    for node in packet.nodes:
        resolution = resolution_by_candidate[node.candidate_id]
        target = resolution.target_object_id
        if target is None:  # pragma: no cover — preview is built only when ready
            raise DndContributionPlanningError(
                "contribution preview requires resolved node targets",
                details={"candidate_id": node.candidate_id},
            )
        evidence = [evidence_by_id[ref_id] for ref_id in node.evidence_ref_ids]
        assertions.append(
            _node_field_assertion(
                packet,
                contribution_id=contribution_id,
                candidate_id=node.candidate_id,
                target_object_id=target,
                outcome=resolution.outcome,
                evidence_refs=list(evidence),
                assertion_kind="label",
                discriminator="",
                label=node.label,
            )
        )
        label_norm = _norm(node.label)
        for form in node.surface_forms:
            if _norm(form) == label_norm:
                continue
            assertions.append(
                _node_field_assertion(
                    packet,
                    contribution_id=contribution_id,
                    candidate_id=node.candidate_id,
                    target_object_id=target,
                    outcome=resolution.outcome,
                    evidence_refs=list(evidence),
                    assertion_kind="alias",
                    discriminator=form,
                    value=form,
                )
            )
        if node.summary is not None:
            assertions.append(
                _node_field_assertion(
                    packet,
                    contribution_id=contribution_id,
                    candidate_id=node.candidate_id,
                    target_object_id=target,
                    outcome=resolution.outcome,
                    evidence_refs=list(evidence),
                    assertion_kind="summary",
                    discriminator="",
                    value=node.summary,
                )
            )
    return assertions


def _relationship_assertions(
    packet: DndThreatCandidatePacket,
    plan_by_relationship: dict[str, DndRelationshipPlan],
    evidence_by_id: dict[str, EvidenceRef],
    contribution_id: str,
) -> list[GraphContributionAssertion]:
    """One relationship assertion per ready relationship, in packet order,
    with resolved endpoint IDs and the exact relationship evidence."""
    assertions: list[GraphContributionAssertion] = []
    for relationship in packet.relationships:
        plan = plan_by_relationship[relationship.candidate_id]
        if plan.subject_object_id is None or plan.object_object_id is None:
            # pragma: no cover — preview is built only when every plan is ready
            raise DndContributionPlanningError(
                "contribution preview requires resolved relationship endpoints",
                details={"relationship_candidate_id": relationship.candidate_id},
            )
        assertions.append(
            GraphContributionAssertion(
                assertion_id=derive_assertion_id(
                    contribution_id=contribution_id,
                    candidate_id=relationship.candidate_id,
                    assertion_kind="relationship",
                    discriminator="",
                ),
                assertion_kind="relationship",
                subject_object_id=plan.subject_object_id,
                predicate=relationship.predicate,
                object_object_id=plan.object_object_id,
                evidence_refs=[
                    evidence_by_id[ref_id] for ref_id in relationship.evidence_ref_ids
                ],
                source_artifact_id=packet.source_artifact_id,
                source_revision_id=packet.source_revision_id,
                campaign_scope=packet.campaign_id,
                visibility=Visibility.GM,
                epistemic_kind=EpistemicKind.ASSERTED,
                acceptance_state=AcceptanceState.CANDIDATE,
                identity_resolution_outcome=None,
            )
        )
    return assertions


def _build_contribution_preview(
    packet: DndThreatCandidatePacket,
    resolutions: list[DndCandidateResolution],
    relationship_plans: list[DndRelationshipPlan],
    *,
    plan_id: str,
    actor: str,
    planned_at: datetime,
) -> GraphContribution:
    """Step 12: the candidate-only, GM-only review preview. Built only for a
    blocker-free packet; never appended anywhere."""
    contribution_id = derive_contribution_id(plan_id=plan_id)
    evidence_by_id = {ref.evidence_ref_id: ref for ref in packet.evidence_refs}
    resolution_by_candidate = {r.candidate_id: r for r in resolutions}
    plan_by_relationship = {p.relationship_candidate_id: p for p in relationship_plans}
    assertions = _node_assertions(
        packet, resolution_by_candidate, evidence_by_id, contribution_id
    )
    assertions.extend(
        _relationship_assertions(
            packet, plan_by_relationship, evidence_by_id, contribution_id
        )
    )
    try:
        return GraphContribution(
            contribution_id=contribution_id,
            world_id=packet.world_id,
            source_kind=ContributionSourceKind.EXTRACTION,
            source_artifact_id=packet.source_artifact_id,
            source_revision_id=packet.source_revision_id,
            extraction_profile=format_extraction_profile(
                packet.semantic_profile, packet.vocabulary
            ),
            produced_at=planned_at,
            campaign_scope=packet.campaign_id,
            status=ContributionStatus.ACTIVE,
            assertions=assertions,
            unresolved_mentions=[],
            identity_decision_ids=[],
            authored_by=actor,
            diagnostics={},
        )
    except ValidationError as exc:
        # Kernel contribution models do not hide rejected inputs; forward
        # validator message strings only, and never chain the raw error.
        raise DndContributionPlanningError(
            "contribution preview construction violated a contract invariant",
            details={"reason": "ValidationError", "messages": _error_messages(exc)},
        ) from None


def _build_plan(
    packet: DndThreatCandidatePacket,
    stored_revision: StoredGraphRevision,
    *,
    plan_id: str,
    packet_digest: str,
    status: DndThreatPlanStatus,
    resolutions: list[DndCandidateResolution],
    verifications: list[DndExistingObjectVerification],
    relationship_plans: list[DndRelationshipPlan],
    blockers: list[DndPlanBlocker],
    actor: str,
    planned_at: datetime,
    preview_content_sha256: str | None,
    proposed_contribution: GraphContribution | None,
) -> DndThreatContributionPlan:
    """Step 13: deterministic record ordering and plan assembly."""
    revision = stored_revision.revision
    try:
        return DndThreatContributionPlan(
            plan_id=plan_id,
            world_id=packet.world_id,
            campaign_id=packet.campaign_id,
            packet_id=packet.packet_id,
            candidate_packet_sha256=packet_digest,
            base_revision_id=revision.revision_id,
            base_graph_schema=revision.graph_schema,
            base_graph_payload_sha256=revision.graph_payload_sha256,
            preview_content_sha256=preview_content_sha256,
            expected_parent_revision_id=revision.revision_id,
            semantic_profile=packet.semantic_profile,
            vocabulary=packet.vocabulary,
            actor=actor,
            planned_at=planned_at,
            status=status,
            candidate_resolutions=sorted(resolutions, key=lambda r: r.candidate_id),
            existing_object_verifications=sorted(
                verifications,
                key=lambda v: (v.existing_object_id, v.expected_kind),
            ),
            relationship_plans=sorted(
                relationship_plans, key=lambda p: p.relationship_candidate_id
            ),
            blockers=blockers,
            confirmation_required=True,
            proposed_contribution=proposed_contribution,
        )
    except ValidationError as exc:
        raise DndContributionPlanningError(
            "plan construction violated a plan invariant",
            details={"reason": "ValidationError", "messages": _error_messages(exc)},
        ) from None


def plan_threat_candidate_contribution(
    payload: Mapping[str, Any] | DndThreatCandidatePacket,
    *,
    stored_revision: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
    actor: str,
    planned_at: datetime,
) -> DndThreatContributionPlan:
    """Plan one Threat candidate packet against one exact stored graph revision.

    Deterministic and non-mutating: the same packet, stored revision, actor,
    and ``planned_at`` produce a byte-identical plan. ``planned_at`` is
    caller-supplied operation identity — exact retries must reuse it.

    Raises ``DndContributionPlanningError`` on any integrity failure
    (malformed packet, digest/world/schema/profile mismatch, unparseable
    stored payload, deterministic-ID collision, or invariant violation);
    valid-but-unresolvable states yield a ``blocked`` plan instead.
    """
    if not actor.strip():
        raise DndContributionPlanningError(
            "actor must be non-blank",
            details={"reason": "blank_actor"},
        )
    packet = _parse_and_validate_packet(payload)
    _verify_revision_integrity(packet, stored_revision)
    snapshot = _parse_full_snapshot(stored_revision, graph_reader)
    _require_profile_match(packet, snapshot)

    packet_digest = canonical_sha256(packet.model_dump(mode="json"))
    resolutions = _resolve_candidates(packet, snapshot, packet_digest)
    verifications = _verify_existing_endpoints(packet, snapshot)
    relationship_plans = _plan_relationships(
        packet, resolutions, verifications, snapshot
    )
    blockers = _collect_blockers(resolutions, verifications, relationship_plans)

    plan_id = derive_plan_id(
        packet_digest=packet_digest,
        base_revision_id=stored_revision.revision.revision_id,
        base_graph_payload_sha256=stored_revision.revision.graph_payload_sha256,
        actor=actor,
        planned_at=planned_at,
    )
    common: dict[str, Any] = {
        "plan_id": plan_id,
        "packet_digest": packet_digest,
        "resolutions": resolutions,
        "verifications": verifications,
        "relationship_plans": relationship_plans,
        "blockers": blockers,
        "actor": actor,
        "planned_at": planned_at,
    }
    if blockers:
        return _build_plan(
            packet,
            stored_revision,
            status=DndThreatPlanStatus.BLOCKED,
            preview_content_sha256=None,
            proposed_contribution=None,
            **common,
        )
    contribution = _build_contribution_preview(
        packet,
        resolutions,
        relationship_plans,
        plan_id=plan_id,
        actor=actor,
        planned_at=planned_at,
    )
    preview_content_sha256 = derive_preview_content_sha256(
        candidate_resolutions=resolutions,
        existing_object_verifications=verifications,
        relationship_plans=relationship_plans,
        contribution=contribution,
    )
    plan_id = derive_plan_id(
        packet_digest=packet_digest,
        base_revision_id=stored_revision.revision.revision_id,
        base_graph_payload_sha256=stored_revision.revision.graph_payload_sha256,
        actor=actor,
        planned_at=planned_at,
        preview_content_sha256=preview_content_sha256,
    )
    common["plan_id"] = plan_id
    contribution = _build_contribution_preview(
        packet,
        resolutions,
        relationship_plans,
        plan_id=plan_id,
        actor=actor,
        planned_at=planned_at,
    )
    return _build_plan(
        packet,
        stored_revision,
        status=DndThreatPlanStatus.READY_FOR_REVIEW,
        preview_content_sha256=preview_content_sha256,
        proposed_contribution=contribution,
        **common,
    )
