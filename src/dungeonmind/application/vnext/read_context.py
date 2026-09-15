"""Immutable KnowledgeReadContext and candidate admission orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from dungeonmind.contracts.vnext.domain import DomainContractDescriptor, SemanticProfileDescriptorV2
from dungeonmind.contracts.vnext.projection import ProjectionRequest
from dungeonmind.domain.canonical import canonical_sha256

from .admission import (
    AdmissionWorkCounts,
    CandidateAdmissionResult,
    CandidateExclusion,
    DomainAdmissionPolicy,
    assertion_visibility_passes,
    collect_evidence_dependencies,
    compute_result_digest,
    domain_declaration_passes,
    evidence_chain_passes,
    scope_passes,
    semantic_profile_passes,
    standing_passes,
    validate_request_vocabulary,
)
from .errors import CandidateAdmissionIntegrityError, KnowledgeReadContextIntegrityError
from .model import ParsedKnowledgeRevision
from .ports import KnowledgeSourceReader


def _verify_descriptor_pin(
    *,
    parsed: ParsedKnowledgeRevision,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2,
) -> None:
    contract_ref = parsed.domain_contract_ref
    if domain_contract.domain_id != contract_ref.domain_id:
        raise KnowledgeReadContextIntegrityError("domain contract id mismatch")
    if domain_contract.domain_revision != contract_ref.domain_revision:
        raise KnowledgeReadContextIntegrityError("domain contract revision mismatch")
    expected_contract_digest = canonical_sha256(domain_contract.model_dump(mode="json"))
    if expected_contract_digest != contract_ref.descriptor_sha256:
        raise KnowledgeReadContextIntegrityError("domain contract descriptor digest mismatch")

    profile_ref = parsed.semantic_profile_ref
    if semantic_profile.profile_id != profile_ref.profile_id:
        raise KnowledgeReadContextIntegrityError("semantic profile id mismatch")
    if semantic_profile.profile_revision != profile_ref.profile_revision:
        raise KnowledgeReadContextIntegrityError("semantic profile revision mismatch")
    expected_profile_digest = canonical_sha256(semantic_profile.model_dump(mode="json"))
    if expected_profile_digest != profile_ref.descriptor_sha256:
        raise KnowledgeReadContextIntegrityError("semantic profile descriptor digest mismatch")


@dataclass
class KnowledgeReadContext:
    """One exact immutable revision + request + pinned descriptors for admission."""

    parsed: ParsedKnowledgeRevision
    request: ProjectionRequest
    domain_contract: DomainContractDescriptor
    semantic_profile: SemanticProfileDescriptorV2
    domain_policy: DomainAdmissionPolicy
    source_reader: KnowledgeSourceReader
    _evidence_memo: dict[str, str | None] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.request.space_id != self.parsed.space_id:
            raise KnowledgeReadContextIntegrityError("request space_id mismatch")
        if (
            self.request.revision_id is not None
            and self.request.revision_id != self.parsed.revision_id
        ):
            raise KnowledgeReadContextIntegrityError("request revision_id mismatch")

        _verify_descriptor_pin(
            parsed=self.parsed,
            domain_contract=self.domain_contract,
            semantic_profile=self.semantic_profile,
        )

        if self.domain_policy.policy_id != self.domain_contract.admission_policy_id:
            raise KnowledgeReadContextIntegrityError("domain admission policy identity mismatch")

        validate_request_vocabulary(self.request, domain_contract=self.domain_contract)

    def admit_candidates(self, candidate_assertion_ids: Sequence[str]) -> CandidateAdmissionResult:
        self._evidence_memo.clear()
        normalized_ids = tuple(dict.fromkeys(candidate_assertion_ids))
        for assertion_id in normalized_ids:
            if self.parsed.get_assertion(assertion_id) is None:
                raise CandidateAdmissionIntegrityError(
                    f"unknown candidate assertion id: {assertion_id}"
                )

        evaluation_order = tuple(sorted(normalized_ids))
        (
            evidence_ids,
            artifact_ids,
            revision_ids,
        ) = collect_evidence_dependencies(self.parsed, evaluation_order)

        snapshot_calls_before = getattr(self.source_reader, "snapshot_call_count", None)
        provenance = self.source_reader.get_provenance_snapshot(
            artifact_ids=artifact_ids,
            revision_ids=revision_ids,
        )
        snapshot_calls = 1
        if snapshot_calls_before is not None:
            snapshot_calls_after = getattr(self.source_reader, "snapshot_call_count", 0)
            snapshot_calls = snapshot_calls_after - snapshot_calls_before

        audience = frozenset(self.request.audience_labels)
        declared_labels = frozenset(self.domain_contract.visibility_labels)
        declared_axes = frozenset(self.domain_contract.scope_axes)
        standing_selector = tuple(self.request.standing_selector)

        admitted: list[str] = []
        excluded: list[CandidateExclusion] = []

        for assertion_id in evaluation_order:
            assertion = self.parsed.get_assertion(assertion_id)
            assert assertion is not None

            reason = standing_passes(assertion, standing_selector=standing_selector)
            if reason is None:
                reason = scope_passes(
                    assertion,
                    request=self.request,
                    declared_axes=declared_axes,
                )
            if reason is None:
                reason = domain_declaration_passes(
                    assertion,
                    domain_contract=self.domain_contract,
                )
            if reason is None:
                reason = assertion_visibility_passes(
                    assertion,
                    audience=audience,
                    declared_labels=declared_labels,
                )
            if reason is None:
                reason = semantic_profile_passes(
                    assertion,
                    semantic_profile=self.semantic_profile,
                )
            if reason is None:
                reason = evidence_chain_passes(
                    assertion,
                    parsed=self.parsed,
                    provenance=provenance,
                    audience=audience,
                    declared_labels=declared_labels,
                    domain_contract=self.domain_contract,
                    memo=self._evidence_memo,
                )
            if reason is None and not self.domain_policy.narrow(
                assertion=assertion,
                request=self.request,
                domain_contract=self.domain_contract,
                semantic_profile=self.semantic_profile,
                provenance=provenance,
            ):
                reason = "domain_policy"

            if reason is None:
                admitted.append(assertion_id)
            else:
                excluded.append(CandidateExclusion(assertion_id=assertion_id, reason=reason))

        admitted_sorted = tuple(sorted(admitted))
        excluded_sorted = tuple(sorted(excluded, key=lambda item: (item.assertion_id, item.reason)))
        work = AdmissionWorkCounts(
            candidate_count=len(evaluation_order),
            evidence_ids_resolved=len(evidence_ids),
            artifact_ids_requested=len(artifact_ids),
            revision_ids_requested=len(revision_ids),
            provenance_snapshot_calls=snapshot_calls,
        )
        digest = compute_result_digest(
            admitted_assertion_ids=admitted_sorted,
            excluded=excluded_sorted,
        )
        return CandidateAdmissionResult(
            admitted_assertion_ids=admitted_sorted,
            excluded=excluded_sorted,
            work=work,
            result_digest=digest,
        )
