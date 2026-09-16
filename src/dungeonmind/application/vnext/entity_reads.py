"""Exact and complete entity reads over one pinned KnowledgeReadContext."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from dungeonmind.domain.canonical import canonical_sha256

from .errors import EntityReadIntegrityError
from .provenance import KnowledgeProvenanceSnapshot
from .read_context import KnowledgeReadContext
from .records import ParsedAssertion, ParsedEntity, ParsedEntityRefValue, ParsedEvidenceRef

ENTITY_READ_PARTIAL_REASONS = frozenset({"support_unavailable", "result_truncated"})


def _dedupe_sorted(ids: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(ids)))


@dataclass(frozen=True, slots=True)
class EntityReadIdentity:
    space_id: str
    revision_id: str
    entity_id: str
    domain_contract_id: str
    domain_contract_revision: str
    semantic_profile_id: str
    semantic_profile_revision: str


@dataclass(frozen=True, slots=True)
class EntityReadCompleteness:
    status: Literal["complete", "partial"]
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status == "complete":
            if self.reason is not None:
                raise EntityReadIntegrityError(
                    "complete entity read cannot carry a partial reason"
                )
            return
        if self.reason is None:
            raise EntityReadIntegrityError("partial entity read requires an explicit reason")
        if self.reason not in ENTITY_READ_PARTIAL_REASONS:
            raise EntityReadIntegrityError(
                f"unknown partial completeness reason: {self.reason}"
            )


@dataclass(frozen=True, slots=True)
class EntityReadWorkCounts:
    entity_lookups: int
    subject_assertion_candidates: int
    incoming_entity_ref_candidates: int
    outgoing_entity_ref_candidates: int
    deduped_candidate_assertions: int
    assertions_evaluated: int
    policy_evaluations: int
    endpoint_entity_lookups: int
    evidence_ids_returned: int
    artifact_ids_requested: int
    revision_ids_requested: int
    provenance_snapshot_calls: int


@dataclass(frozen=True, slots=True)
class EntityReadSourceArtifact:
    source_artifact_id: str
    status: str
    current_revision_id: str | None
    source_classification: str
    authority: str


@dataclass(frozen=True, slots=True)
class EntityReadSourceRevision:
    source_revision_id: str
    source_artifact_id: str
    content_sha256: str


@dataclass(frozen=True, slots=True)
class EntityLookupResult:
    identity: EntityReadIdentity
    found: bool
    entity: ParsedEntity | None
    assertions: tuple[ParsedAssertion, ...]
    evidence: tuple[ParsedEvidenceRef, ...]
    source_artifacts: tuple[EntityReadSourceArtifact, ...]
    source_revisions: tuple[EntityReadSourceRevision, ...]
    completeness: EntityReadCompleteness
    work: EntityReadWorkCounts
    result_digest: str


@dataclass(frozen=True, slots=True)
class CompleteEntityLookupResult(EntityLookupResult):
    related_entities: tuple[ParsedEntity, ...]


def _identity(context: KnowledgeReadContext, entity_id: str) -> EntityReadIdentity:
    parsed = context.parsed
    return EntityReadIdentity(
        space_id=parsed.space_id,
        revision_id=parsed.revision_id,
        entity_id=entity_id,
        domain_contract_id=parsed.domain_contract_ref.domain_id,
        domain_contract_revision=parsed.domain_contract_ref.domain_revision,
        semantic_profile_id=parsed.semantic_profile_ref.profile_id,
        semantic_profile_revision=parsed.semantic_profile_ref.profile_revision,
    )


def _empty_work(*, entity_lookups: int) -> EntityReadWorkCounts:
    return EntityReadWorkCounts(
        entity_lookups=entity_lookups,
        subject_assertion_candidates=0,
        incoming_entity_ref_candidates=0,
        outgoing_entity_ref_candidates=0,
        deduped_candidate_assertions=0,
        assertions_evaluated=0,
        policy_evaluations=0,
        endpoint_entity_lookups=0,
        evidence_ids_returned=0,
        artifact_ids_requested=0,
        revision_ids_requested=0,
        provenance_snapshot_calls=0,
    )


def _compute_result_digest(
    *,
    identity: EntityReadIdentity,
    found: bool,
    assertion_ids: tuple[str, ...],
    related_entity_ids: tuple[str, ...],
    evidence: tuple[ParsedEvidenceRef, ...],
    source_artifacts: tuple[EntityReadSourceArtifact, ...],
    source_revisions: tuple[EntityReadSourceRevision, ...],
    completeness: EntityReadCompleteness,
) -> str:
    return canonical_sha256(
        {
            "space_id": identity.space_id,
            "revision_id": identity.revision_id,
            "entity_id": identity.entity_id,
            "found": found,
            "assertion_ids": list(assertion_ids),
            "related_entity_ids": list(related_entity_ids),
            "evidence": [
                {
                    "evidence_ref_id": item.evidence_ref_id,
                    "source_artifact_id": item.source_artifact_id,
                    "source_revision_id": item.source_revision_id,
                    "evidence_role": item.evidence_role,
                    "locator": item.locator,
                    "uri": item.uri,
                    "source_locator": item.source_locator,
                    "line_ref": item.line_ref,
                    "source_span_ref_id": item.source_span_ref_id,
                }
                for item in evidence
            ],
            "source_artifacts": [
                {
                    "source_artifact_id": item.source_artifact_id,
                    "status": item.status,
                    "current_revision_id": item.current_revision_id,
                }
                for item in source_artifacts
            ],
            "source_revisions": [
                {
                    "source_revision_id": item.source_revision_id,
                    "source_artifact_id": item.source_artifact_id,
                    "content_sha256": item.content_sha256,
                }
                for item in source_revisions
            ],
            "completeness": {"status": completeness.status, "reason": completeness.reason},
        }
    )


def _support_for_admitted(
    *,
    context: KnowledgeReadContext,
    admitted_ids: tuple[str, ...],
    provenance: KnowledgeProvenanceSnapshot | None,
) -> tuple[
    tuple[ParsedEvidenceRef, ...],
    tuple[EntityReadSourceArtifact, ...],
    tuple[EntityReadSourceRevision, ...],
]:
    parsed = context.parsed
    evidence_ids: list[str] = []
    for assertion_id in admitted_ids:
        evidence_ids.extend(parsed.assertion_evidence.get(assertion_id, ()))
    unique_evidence_ids = _dedupe_sorted(evidence_ids)
    evidence: list[ParsedEvidenceRef] = []
    artifact_ids: list[str] = []
    revision_ids: list[str] = []
    for evidence_id in unique_evidence_ids:
        record = parsed.get_evidence(evidence_id)
        if record is None:
            raise EntityReadIntegrityError(
                f"admitted assertion evidence missing from parsed revision: {evidence_id}"
            )
        evidence.append(record)
        artifact_ids.append(record.source_artifact_id)
        if record.source_revision_id is not None:
            revision_ids.append(record.source_revision_id)

    artifacts: list[EntityReadSourceArtifact] = []
    revisions: list[EntityReadSourceRevision] = []
    if provenance is not None:
        for artifact_id in _dedupe_sorted(artifact_ids):
            artifact = provenance.get_artifact(artifact_id)
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
        for revision_id in _dedupe_sorted(revision_ids):
            revision = provenance.get_revision(revision_id)
            if revision is None:
                continue
            revisions.append(
                EntityReadSourceRevision(
                    source_revision_id=revision.source_revision_id,
                    source_artifact_id=revision.source_artifact_id,
                    content_sha256=revision.content_sha256,
                )
            )
    return tuple(evidence), tuple(artifacts), tuple(revisions)


def _opposite_endpoint_id(assertion: ParsedAssertion, selected_entity_id: str) -> str | None:
    if not isinstance(assertion.value, ParsedEntityRefValue):
        return None
    if assertion.subject_entity_id == selected_entity_id:
        other = assertion.value.entity_id
        return None if other == selected_entity_id else other
    if assertion.value.entity_id == selected_entity_id:
        other = assertion.subject_entity_id
        return None if other == selected_entity_id else other
    return None


def _assemble(
    *,
    context: KnowledgeReadContext,
    entity_id: str,
    include_touching: bool,
) -> EntityLookupResult | CompleteEntityLookupResult:
    parsed = context.parsed
    identity = _identity(context, entity_id)
    entity = parsed.get_entity(entity_id)
    if entity is None:
        completeness = EntityReadCompleteness(status="complete", reason=None)
        work = _empty_work(entity_lookups=1)
        digest = _compute_result_digest(
            identity=identity,
            found=False,
            assertion_ids=(),
            related_entity_ids=(),
            evidence=(),
            source_artifacts=(),
            source_revisions=(),
            completeness=completeness,
        )
        miss = EntityLookupResult(
            identity=identity,
            found=False,
            entity=None,
            assertions=(),
            evidence=(),
            source_artifacts=(),
            source_revisions=(),
            completeness=completeness,
            work=work,
            result_digest=digest,
        )
        if include_touching:
            return CompleteEntityLookupResult(
                identity=miss.identity,
                found=miss.found,
                entity=miss.entity,
                assertions=miss.assertions,
                evidence=miss.evidence,
                source_artifacts=miss.source_artifacts,
                source_revisions=miss.source_revisions,
                completeness=miss.completeness,
                work=miss.work,
                result_digest=miss.result_digest,
                related_entities=(),
            )
        return miss

    subject_ids = tuple(parsed.get_subject_assertion_ids(entity_id))
    outgoing_assertion_ids = tuple(parsed.get_outgoing_entity_ref_assertion_ids(entity_id))
    incoming_assertion_ids = (
        tuple(parsed.get_incoming_entity_ref_assertion_ids(entity_id))
        if include_touching
        else ()
    )
    if include_touching:
        candidate_ids = _dedupe_sorted((*subject_ids, *incoming_assertion_ids))
    else:
        candidate_ids = _dedupe_sorted(subject_ids)
        outgoing_assertion_ids = ()

    admission, provenance = context.evaluate_candidates(candidate_ids)
    admitted_ids = admission.admitted_assertion_ids
    assertions: list[ParsedAssertion] = []
    for assertion_id in admitted_ids:
        assertion = parsed.get_assertion(assertion_id)
        if assertion is None:
            raise EntityReadIntegrityError(
                f"admitted assertion missing from parsed revision: {assertion_id}"
            )
        assertions.append(assertion)
    assertions_tuple = tuple(assertions)

    related: list[ParsedEntity] = []
    endpoint_lookups = 0
    if include_touching:
        related_ids: list[str] = []
        for assertion in assertions_tuple:
            endpoint_id = _opposite_endpoint_id(assertion, entity_id)
            if endpoint_id is None:
                continue
            endpoint_lookups += 1
            endpoint = parsed.get_entity(endpoint_id)
            if endpoint is None:
                raise EntityReadIntegrityError(
                    f"admitted touching assertion {assertion.assertion_id} has dangling "
                    f"endpoint {endpoint_id}"
                )
            related_ids.append(endpoint_id)
        for related_id in _dedupe_sorted(related_ids):
            related_entity = parsed.get_entity(related_id)
            if related_entity is None:
                raise EntityReadIntegrityError(
                    f"related endpoint missing from parsed revision: {related_id}"
                )
            related.append(related_entity)

    evidence, artifacts, revisions = _support_for_admitted(
        context=context,
        admitted_ids=admitted_ids,
        provenance=provenance,
    )
    completeness = EntityReadCompleteness(status="complete", reason=None)
    work = EntityReadWorkCounts(
        entity_lookups=1,
        subject_assertion_candidates=len(subject_ids),
        incoming_entity_ref_candidates=len(incoming_assertion_ids),
        outgoing_entity_ref_candidates=len(outgoing_assertion_ids),
        deduped_candidate_assertions=len(candidate_ids),
        assertions_evaluated=admission.work.assertions_evaluated,
        policy_evaluations=admission.work.policy_evaluations,
        endpoint_entity_lookups=endpoint_lookups,
        evidence_ids_returned=len(evidence),
        artifact_ids_requested=admission.work.artifact_ids_requested,
        revision_ids_requested=admission.work.revision_ids_requested,
        provenance_snapshot_calls=admission.work.provenance_snapshot_calls,
    )
    related_tuple = tuple(related)
    digest = _compute_result_digest(
        identity=identity,
        found=True,
        assertion_ids=admitted_ids,
        related_entity_ids=tuple(item.entity_id for item in related_tuple),
        evidence=evidence,
        source_artifacts=artifacts,
        source_revisions=revisions,
        completeness=completeness,
    )
    if include_touching:
        return CompleteEntityLookupResult(
            identity=identity,
            found=True,
            entity=entity,
            assertions=assertions_tuple,
            evidence=evidence,
            source_artifacts=artifacts,
            source_revisions=revisions,
            completeness=completeness,
            work=work,
            result_digest=digest,
            related_entities=related_tuple,
        )
    return EntityLookupResult(
        identity=identity,
        found=True,
        entity=entity,
        assertions=assertions_tuple,
        evidence=evidence,
        source_artifacts=artifacts,
        source_revisions=revisions,
        completeness=completeness,
        work=work,
        result_digest=digest,
    )


class EntityReadService:
    """Exact-ID entity reads using revision-local indexes and the V2 admission seam."""

    def get_entity(self, context: KnowledgeReadContext, entity_id: str) -> EntityLookupResult:
        result = _assemble(context=context, entity_id=entity_id, include_touching=False)
        if isinstance(result, CompleteEntityLookupResult):
            raise EntityReadIntegrityError("get_entity assembled a complete-entity result")
        return result

    def get_complete_entity(
        self, context: KnowledgeReadContext, entity_id: str
    ) -> CompleteEntityLookupResult:
        result = _assemble(context=context, entity_id=entity_id, include_touching=True)
        if not isinstance(result, CompleteEntityLookupResult):
            raise EntityReadIntegrityError("get_complete_entity assembled a non-complete result")
        return result
