"""Exact assertion/evidence support reads over one pinned KnowledgeReadContext."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from dungeonmind.domain.canonical import canonical_sha256

from .entity_reads import (
    EntityReadCompleteness,
    EntityReadSourceArtifact,
    EntityReadSourceRevision,
)
from .errors import EvidenceReadIntegrityError
from .provenance import KnowledgeProvenanceSnapshot
from .read_context import KnowledgeReadContext
from .records import ParsedAssertion, ParsedEvidenceRef
from .source_anchors import (
    SourceAnchor,
    build_source_anchor,
    compute_anchor_identity_digest,
    decode_anchor_token,
    evidence_location_payload,
    visible_source_payload,
)

EvidenceReadCompleteness = EntityReadCompleteness


@dataclass(frozen=True, slots=True)
class EvidenceReadIdentity:
    space_id: str
    revision_id: str
    domain_contract_id: str
    domain_contract_revision: str
    semantic_profile_id: str
    semantic_profile_revision: str


@dataclass(frozen=True, slots=True)
class EvidenceReadTrace:
    assertion_lookups: int
    evidence_lookups: int
    supporter_candidates: int
    assertions_evaluated: int
    policy_evaluations: int
    evidence_ids_consulted: int
    unique_artifact_ids_requested: int
    unique_revision_ids_requested: int
    provenance_snapshot_calls: int
    anchors_constructed: int
    anchors_revalidated: int


@dataclass(frozen=True, slots=True)
class AssertionEvidenceResult:
    identity: EvidenceReadIdentity
    requested_assertion_id: str
    available: bool
    assertion: ParsedAssertion | None
    evidence: tuple[ParsedEvidenceRef, ...]
    source_artifacts: tuple[EntityReadSourceArtifact, ...]
    source_revisions: tuple[EntityReadSourceRevision, ...]
    anchors: tuple[SourceAnchor, ...]
    completeness: EntityReadCompleteness
    result_digest: str


@dataclass(frozen=True, slots=True)
class EvidenceLookupResult:
    identity: EvidenceReadIdentity
    requested_evidence_ref_id: str
    available: bool
    evidence: ParsedEvidenceRef | None
    admitted_supporter_assertions: tuple[ParsedAssertion, ...]
    source_artifacts: tuple[EntityReadSourceArtifact, ...]
    source_revisions: tuple[EntityReadSourceRevision, ...]
    anchors: tuple[SourceAnchor, ...]
    completeness: EntityReadCompleteness
    result_digest: str


@dataclass(frozen=True, slots=True)
class SourceAnchorResolution:
    identity: EvidenceReadIdentity
    requested_anchor_id: str
    resolved: bool
    anchor: SourceAnchor | None
    evidence: ParsedEvidenceRef | None
    admitted_supporter_assertions: tuple[ParsedAssertion, ...]
    source_artifacts: tuple[EntityReadSourceArtifact, ...]
    source_revisions: tuple[EntityReadSourceRevision, ...]
    completeness: EntityReadCompleteness
    result_digest: str


def _empty_trace() -> EvidenceReadTrace:
    return EvidenceReadTrace(
        assertion_lookups=0,
        evidence_lookups=0,
        supporter_candidates=0,
        assertions_evaluated=0,
        policy_evaluations=0,
        evidence_ids_consulted=0,
        unique_artifact_ids_requested=0,
        unique_revision_ids_requested=0,
        provenance_snapshot_calls=0,
        anchors_constructed=0,
        anchors_revalidated=0,
    )


def _require_id(value: object, *, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise EvidenceReadIntegrityError(f"{label} must be a non-empty string")
    return value


def _identity(context: KnowledgeReadContext) -> EvidenceReadIdentity:
    parsed = context.parsed
    return EvidenceReadIdentity(
        space_id=parsed.space_id,
        revision_id=parsed.revision_id,
        domain_contract_id=parsed.domain_contract_ref.domain_id,
        domain_contract_revision=parsed.domain_contract_ref.domain_revision,
        semantic_profile_id=parsed.semantic_profile_ref.profile_id,
        semantic_profile_revision=parsed.semantic_profile_ref.profile_revision,
    )


def _identity_payload(identity: EvidenceReadIdentity) -> dict[str, str]:
    return {
        "space_id": identity.space_id,
        "revision_id": identity.revision_id,
        "domain_contract_id": identity.domain_contract_id,
        "domain_contract_revision": identity.domain_contract_revision,
        "semantic_profile_id": identity.semantic_profile_id,
        "semantic_profile_revision": identity.semantic_profile_revision,
    }


def _anchor_payload(anchor: SourceAnchor) -> dict[str, object]:
    return {
        "anchor_id": anchor.anchor_id,
        "evidence_ref_id": anchor.evidence_ref_id,
        "source_artifact_id": anchor.source_artifact_id,
        "source_revision_id": anchor.source_revision_id,
        "evidence_role": anchor.evidence_role,
        "can_open_source": anchor.can_open_source,
        "can_highlight_span": anchor.can_highlight_span,
        "locator": anchor.locator,
        "uri": anchor.uri,
        "source_locator": anchor.source_locator,
        "line_ref": anchor.line_ref,
        "source_span_ref_id": anchor.source_span_ref_id,
    }


def _unavailable_digest(
    *,
    identity: EvidenceReadIdentity,
    requested_key: str,
    requested_value: str,
    available_key: str,
    available_value: bool,
) -> str:
    return canonical_sha256(
        {
            **_identity_payload(identity),
            requested_key: requested_value,
            available_key: available_value,
        }
    )


def _available_support_digest(
    *,
    identity: EvidenceReadIdentity,
    requested_key: str,
    requested_value: str,
    available: bool,
    assertion_id: str | None,
    evidence: tuple[ParsedEvidenceRef, ...],
    admitted_supporter_ids: tuple[str, ...],
    source_artifacts: tuple[EntityReadSourceArtifact, ...],
    source_revisions: tuple[EntityReadSourceRevision, ...],
    anchors: tuple[SourceAnchor, ...],
    completeness: EntityReadCompleteness,
) -> str:
    return canonical_sha256(
        {
            **_identity_payload(identity),
            requested_key: requested_value,
            "available": available,
            "assertion_id": assertion_id,
            "evidence": [evidence_location_payload(item) for item in evidence],
            "admitted_supporter_assertion_ids": list(admitted_supporter_ids),
            **visible_source_payload(source_artifacts, source_revisions),
            "anchors": [_anchor_payload(item) for item in anchors],
            "completeness": {"status": completeness.status, "reason": completeness.reason},
        }
    )


def _merge_trace(
    *,
    base: EvidenceReadTrace,
    snapshot: KnowledgeProvenanceSnapshot | None,
    assertions_evaluated: int,
    policy_evaluations: int,
    evidence_ids_consulted: int,
    provenance_snapshot_calls: int,
    supporter_candidates: int | None = None,
    anchors_constructed: int = 0,
    anchors_revalidated: int = 0,
) -> EvidenceReadTrace:
    requested_artifacts: set[str] = set()
    requested_revisions: set[str] = set()
    if snapshot is not None:
        requested_artifacts.update(snapshot.requested_artifact_ids)
        requested_revisions.update(snapshot.requested_revision_ids)
    return EvidenceReadTrace(
        assertion_lookups=base.assertion_lookups,
        evidence_lookups=base.evidence_lookups,
        supporter_candidates=(
            base.supporter_candidates if supporter_candidates is None else supporter_candidates
        ),
        assertions_evaluated=base.assertions_evaluated + assertions_evaluated,
        policy_evaluations=base.policy_evaluations + policy_evaluations,
        evidence_ids_consulted=base.evidence_ids_consulted + evidence_ids_consulted,
        unique_artifact_ids_requested=len(requested_artifacts),
        unique_revision_ids_requested=len(requested_revisions),
        provenance_snapshot_calls=base.provenance_snapshot_calls + provenance_snapshot_calls,
        anchors_constructed=base.anchors_constructed + anchors_constructed,
        anchors_revalidated=base.anchors_revalidated + anchors_revalidated,
    )


def _source_support_for_evidence(
    *,
    evidence: Sequence[ParsedEvidenceRef],
    snapshot: KnowledgeProvenanceSnapshot | None,
) -> tuple[tuple[EntityReadSourceArtifact, ...], tuple[EntityReadSourceRevision, ...]]:
    if snapshot is None:
        return (), ()
    artifact_ids = [record.source_artifact_id for record in evidence]
    revision_ids = [
        record.source_revision_id for record in evidence if record.source_revision_id is not None
    ]
    artifacts: list[EntityReadSourceArtifact] = []
    for artifact_id in sorted(set(artifact_ids)):
        artifact = snapshot.get_artifact(artifact_id)
        if artifact is None:
            continue
        artifacts.append(
            EntityReadSourceArtifact(
                source_artifact_id=artifact.source_artifact_id,
                status=artifact.status,
                current_revision_id=artifact.current_revision_id,
                source_classification=artifact.source_classification,
                authority=artifact.authority,
            )
        )
    revisions: list[EntityReadSourceRevision] = []
    for revision_id in sorted(set(revision_ids)):
        revision = snapshot.get_revision(revision_id)
        if revision is None:
            continue
        revisions.append(
            EntityReadSourceRevision(
                source_revision_id=revision.source_revision_id,
                source_artifact_id=revision.source_artifact_id,
                content_sha256=revision.content_sha256,
            )
        )
    return tuple(artifacts), tuple(revisions)


def _complete() -> EntityReadCompleteness:
    return EntityReadCompleteness(status="complete", reason=None)


def _with_anchors(
    trace: EvidenceReadTrace, *, constructed: int, revalidated: int
) -> EvidenceReadTrace:
    return EvidenceReadTrace(
        assertion_lookups=trace.assertion_lookups,
        evidence_lookups=trace.evidence_lookups,
        supporter_candidates=trace.supporter_candidates,
        assertions_evaluated=trace.assertions_evaluated,
        policy_evaluations=trace.policy_evaluations,
        evidence_ids_consulted=trace.evidence_ids_consulted,
        unique_artifact_ids_requested=trace.unique_artifact_ids_requested,
        unique_revision_ids_requested=trace.unique_revision_ids_requested,
        provenance_snapshot_calls=trace.provenance_snapshot_calls,
        anchors_constructed=constructed,
        anchors_revalidated=revalidated,
    )


class EvidenceReadService:
    """Exact assertion/evidence support and source-anchor revalidation."""

    def __init__(self) -> None:
        self.last_trace: EvidenceReadTrace = _empty_trace()

    def get_assertion_evidence(
        self,
        context: KnowledgeReadContext,
        assertion_id: str,
    ) -> AssertionEvidenceResult:
        requested = _require_id(assertion_id, label="assertion ID")
        identity = _identity(context)
        parsed = context.parsed
        trace = EvidenceReadTrace(
            assertion_lookups=1,
            evidence_lookups=0,
            supporter_candidates=0,
            assertions_evaluated=0,
            policy_evaluations=0,
            evidence_ids_consulted=0,
            unique_artifact_ids_requested=0,
            unique_revision_ids_requested=0,
            provenance_snapshot_calls=0,
            anchors_constructed=0,
            anchors_revalidated=0,
        )
        assertion = parsed.get_assertion(requested)
        if assertion is None:
            return self._unavailable_assertion(identity=identity, requested=requested, trace=trace)

        admission, snapshot = context.evaluate_candidates((requested,))
        evidence_ids = parsed.assertion_evidence.get(requested, ())
        trace = _merge_trace(
            base=trace,
            snapshot=snapshot,
            assertions_evaluated=admission.work.assertions_evaluated,
            policy_evaluations=admission.work.policy_evaluations,
            evidence_ids_consulted=len(evidence_ids),
            provenance_snapshot_calls=admission.work.provenance_snapshot_calls,
        )
        if requested not in admission.admitted_assertion_ids:
            return self._unavailable_assertion(identity=identity, requested=requested, trace=trace)

        evidence_records: list[ParsedEvidenceRef] = []
        for evidence_id in evidence_ids:
            record = parsed.get_evidence(evidence_id)
            if record is None:
                raise EvidenceReadIntegrityError(
                    f"admitted assertion evidence missing from parsed revision: {evidence_id}"
                )
            evidence_records.append(record)
        evidence_tuple = tuple(sorted(evidence_records, key=lambda item: item.evidence_ref_id))
        artifacts, revisions = _source_support_for_evidence(
            evidence=evidence_tuple, snapshot=snapshot
        )
        anchors = tuple(
            build_source_anchor(
                context=context,
                evidence=item,
                source_artifacts=artifacts,
                source_revisions=revisions,
                admitted_supporter_assertion_ids=(requested,),
            )
            for item in evidence_tuple
        )
        self.last_trace = _with_anchors(trace, constructed=len(anchors), revalidated=0)
        completeness = _complete()
        return AssertionEvidenceResult(
            identity=identity,
            requested_assertion_id=requested,
            available=True,
            assertion=assertion,
            evidence=evidence_tuple,
            source_artifacts=artifacts,
            source_revisions=revisions,
            anchors=anchors,
            completeness=completeness,
            result_digest=_available_support_digest(
                identity=identity,
                requested_key="requested_assertion_id",
                requested_value=requested,
                available=True,
                assertion_id=assertion.assertion_id,
                evidence=evidence_tuple,
                admitted_supporter_ids=(requested,),
                source_artifacts=artifacts,
                source_revisions=revisions,
                anchors=anchors,
                completeness=completeness,
            ),
        )

    def get_evidence(
        self,
        context: KnowledgeReadContext,
        evidence_ref_id: str,
    ) -> EvidenceLookupResult:
        requested = _require_id(evidence_ref_id, label="evidence ref ID")
        identity = _identity(context)
        parsed = context.parsed
        trace = EvidenceReadTrace(
            assertion_lookups=0,
            evidence_lookups=1,
            supporter_candidates=0,
            assertions_evaluated=0,
            policy_evaluations=0,
            evidence_ids_consulted=0,
            unique_artifact_ids_requested=0,
            unique_revision_ids_requested=0,
            provenance_snapshot_calls=0,
            anchors_constructed=0,
            anchors_revalidated=0,
        )
        record = parsed.get_evidence(requested)
        if record is None:
            return self._unavailable_evidence(identity=identity, requested=requested, trace=trace)

        supporter_ids = parsed.evidence_supporters.get(requested, ())
        trace = EvidenceReadTrace(
            assertion_lookups=0,
            evidence_lookups=1,
            supporter_candidates=len(supporter_ids),
            assertions_evaluated=0,
            policy_evaluations=0,
            evidence_ids_consulted=1,
            unique_artifact_ids_requested=0,
            unique_revision_ids_requested=0,
            provenance_snapshot_calls=0,
            anchors_constructed=0,
            anchors_revalidated=0,
        )
        if not supporter_ids:
            return self._unavailable_evidence(identity=identity, requested=requested, trace=trace)

        admission, snapshot = context.evaluate_candidates(supporter_ids)
        trace = _merge_trace(
            base=trace,
            snapshot=snapshot,
            assertions_evaluated=admission.work.assertions_evaluated,
            policy_evaluations=admission.work.policy_evaluations,
            evidence_ids_consulted=0,
            provenance_snapshot_calls=admission.work.provenance_snapshot_calls,
        )
        admitted_ids = tuple(
            sorted(
                assertion_id
                for assertion_id in supporter_ids
                if assertion_id in set(admission.admitted_assertion_ids)
            )
        )
        if not admitted_ids:
            return self._unavailable_evidence(identity=identity, requested=requested, trace=trace)

        supporters: list[ParsedAssertion] = []
        for assertion_id in admitted_ids:
            assertion = parsed.get_assertion(assertion_id)
            if assertion is None:
                raise EvidenceReadIntegrityError(
                    f"admitted supporter missing from parsed revision: {assertion_id}"
                )
            supporters.append(assertion)
        artifacts, revisions = _source_support_for_evidence(evidence=(record,), snapshot=snapshot)
        anchors = (
            build_source_anchor(
                context=context,
                evidence=record,
                source_artifacts=artifacts,
                source_revisions=revisions,
                admitted_supporter_assertion_ids=admitted_ids,
            ),
        )
        self.last_trace = _with_anchors(trace, constructed=1, revalidated=0)
        completeness = _complete()
        return EvidenceLookupResult(
            identity=identity,
            requested_evidence_ref_id=requested,
            available=True,
            evidence=record,
            admitted_supporter_assertions=tuple(supporters),
            source_artifacts=artifacts,
            source_revisions=revisions,
            anchors=anchors,
            completeness=completeness,
            result_digest=_available_support_digest(
                identity=identity,
                requested_key="requested_evidence_ref_id",
                requested_value=requested,
                available=True,
                assertion_id=None,
                evidence=(record,),
                admitted_supporter_ids=admitted_ids,
                source_artifacts=artifacts,
                source_revisions=revisions,
                anchors=anchors,
                completeness=completeness,
            ),
        )

    def resolve_source_anchor(
        self,
        context: KnowledgeReadContext,
        anchor_id: str,
    ) -> SourceAnchorResolution:
        requested = _require_id(anchor_id, label="anchor ID")
        identity = _identity(context)
        parsed_token = decode_anchor_token(requested)
        if parsed_token is None:
            self.last_trace = _empty_trace()
            return self._unresolved_anchor(identity=identity, requested=requested)
        evidence_ref_id, identity_digest = parsed_token
        lookup = self.get_evidence(context, evidence_ref_id)
        trace = self.last_trace
        self.last_trace = _with_anchors(trace, constructed=trace.anchors_constructed, revalidated=1)
        if not lookup.available or lookup.evidence is None or not lookup.anchors:
            return self._unresolved_anchor(identity=identity, requested=requested)
        current_digest = compute_anchor_identity_digest(
            context=context,
            evidence=lookup.evidence,
            source_artifacts=lookup.source_artifacts,
            source_revisions=lookup.source_revisions,
        )
        if current_digest != identity_digest:
            return self._unresolved_anchor(identity=identity, requested=requested)
        completeness = _complete()
        current_anchor = lookup.anchors[0]
        return SourceAnchorResolution(
            identity=identity,
            requested_anchor_id=requested,
            resolved=True,
            anchor=current_anchor,
            evidence=lookup.evidence,
            admitted_supporter_assertions=lookup.admitted_supporter_assertions,
            source_artifacts=lookup.source_artifacts,
            source_revisions=lookup.source_revisions,
            completeness=completeness,
            result_digest=_available_support_digest(
                identity=identity,
                requested_key="requested_anchor_id",
                requested_value=requested,
                available=True,
                assertion_id=None,
                evidence=(lookup.evidence,),
                admitted_supporter_ids=tuple(
                    item.assertion_id for item in lookup.admitted_supporter_assertions
                ),
                source_artifacts=lookup.source_artifacts,
                source_revisions=lookup.source_revisions,
                anchors=(current_anchor,),
                completeness=completeness,
            ),
        )

    def _unavailable_assertion(
        self,
        *,
        identity: EvidenceReadIdentity,
        requested: str,
        trace: EvidenceReadTrace,
    ) -> AssertionEvidenceResult:
        self.last_trace = trace
        completeness = _complete()
        return AssertionEvidenceResult(
            identity=identity,
            requested_assertion_id=requested,
            available=False,
            assertion=None,
            evidence=(),
            source_artifacts=(),
            source_revisions=(),
            anchors=(),
            completeness=completeness,
            result_digest=_unavailable_digest(
                identity=identity,
                requested_key="requested_assertion_id",
                requested_value=requested,
                available_key="available",
                available_value=False,
            ),
        )

    def _unavailable_evidence(
        self,
        *,
        identity: EvidenceReadIdentity,
        requested: str,
        trace: EvidenceReadTrace,
    ) -> EvidenceLookupResult:
        self.last_trace = trace
        completeness = _complete()
        return EvidenceLookupResult(
            identity=identity,
            requested_evidence_ref_id=requested,
            available=False,
            evidence=None,
            admitted_supporter_assertions=(),
            source_artifacts=(),
            source_revisions=(),
            anchors=(),
            completeness=completeness,
            result_digest=_unavailable_digest(
                identity=identity,
                requested_key="requested_evidence_ref_id",
                requested_value=requested,
                available_key="available",
                available_value=False,
            ),
        )

    def _unresolved_anchor(
        self,
        *,
        identity: EvidenceReadIdentity,
        requested: str,
    ) -> SourceAnchorResolution:
        completeness = _complete()
        return SourceAnchorResolution(
            identity=identity,
            requested_anchor_id=requested,
            resolved=False,
            anchor=None,
            evidence=None,
            admitted_supporter_assertions=(),
            source_artifacts=(),
            source_revisions=(),
            completeness=completeness,
            result_digest=_unavailable_digest(
                identity=identity,
                requested_key="requested_anchor_id",
                requested_value=requested,
                available_key="resolved",
                available_value=False,
            ),
        )
