"""Immutable KnowledgeReadContext and candidate admission orchestration."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

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
from .frozen_json import FrozenJsonValue, freeze_json_value, thaw_json_value
from .model import ParsedKnowledgeRevision
from .ports import KnowledgeSourceReader
from .provenance import KnowledgeProvenanceSnapshot, validate_provenance_snapshot_integrity


class _EvidenceMemoBox:
    __slots__ = ("store",)

    def __init__(self) -> None:
        self.store: dict[str, str | None] = {}


def _seal_model_dump(model: Any) -> FrozenJsonValue:
    return freeze_json_value(model.model_dump(mode="json"))


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


@dataclass(frozen=True, slots=True)
class KnowledgeReadContext:
    """One exact immutable revision + request + pinned descriptors for admission.

    Authorization/profile models are sealed as JSON dumps at construction. Public
    ``request`` / ``domain_contract`` / ``semantic_profile`` accessors always
    rehydrate fresh copies, so callers cannot mutate pinned authority in place.
    """

    parsed: ParsedKnowledgeRevision
    domain_policy: DomainAdmissionPolicy
    source_reader: KnowledgeSourceReader
    _request_dump: FrozenJsonValue
    _domain_contract_dump: FrozenJsonValue
    _semantic_profile_dump: FrozenJsonValue
    _evidence_memo: _EvidenceMemoBox = field(
        default_factory=_EvidenceMemoBox,
        repr=False,
        compare=False,
    )

    def __init__(
        self,
        *,
        parsed: ParsedKnowledgeRevision,
        request: ProjectionRequest,
        domain_contract: DomainContractDescriptor,
        semantic_profile: SemanticProfileDescriptorV2,
        domain_policy: DomainAdmissionPolicy,
        source_reader: KnowledgeSourceReader,
    ) -> None:
        if request.space_id != parsed.space_id:
            raise KnowledgeReadContextIntegrityError("request space_id mismatch")
        if request.revision_id is not None and request.revision_id != parsed.revision_id:
            raise KnowledgeReadContextIntegrityError("request revision_id mismatch")

        request_sealed = request.model_copy(deep=True)
        contract_sealed = domain_contract.model_copy(deep=True)
        profile_sealed = semantic_profile.model_copy(deep=True)

        _verify_descriptor_pin(
            parsed=parsed,
            domain_contract=contract_sealed,
            semantic_profile=profile_sealed,
        )

        if domain_policy.policy_id != contract_sealed.admission_policy_id:
            raise KnowledgeReadContextIntegrityError("domain admission policy identity mismatch")

        validate_request_vocabulary(request_sealed, domain_contract=contract_sealed)

        object.__setattr__(self, "parsed", parsed)
        object.__setattr__(self, "domain_policy", domain_policy)
        object.__setattr__(self, "source_reader", source_reader.open_coherent_view())
        object.__setattr__(self, "_request_dump", _seal_model_dump(request_sealed))
        object.__setattr__(self, "_domain_contract_dump", _seal_model_dump(contract_sealed))
        object.__setattr__(self, "_semantic_profile_dump", _seal_model_dump(profile_sealed))
        object.__setattr__(self, "_evidence_memo", _EvidenceMemoBox())

    @property
    def request(self) -> ProjectionRequest:
        return ProjectionRequest.model_validate(thaw_json_value(self._request_dump))

    @property
    def domain_contract(self) -> DomainContractDescriptor:
        return DomainContractDescriptor.model_validate(
            thaw_json_value(self._domain_contract_dump)
        )

    @property
    def semantic_profile(self) -> SemanticProfileDescriptorV2:
        return SemanticProfileDescriptorV2.model_validate(
            thaw_json_value(self._semantic_profile_dump)
        )

    def admit_candidates(self, candidate_assertion_ids: Sequence[str]) -> CandidateAdmissionResult:
        result, _provenance = self.evaluate_candidates(candidate_assertion_ids)
        return result

    def evaluate_candidates(
        self, candidate_assertion_ids: Sequence[str]
    ) -> tuple[CandidateAdmissionResult, KnowledgeProvenanceSnapshot]:
        """Admit candidates and retain the sealed provenance snapshot for V3 assembly.

        Public ``admit_candidates`` remains the V2 contract and ignores the snapshot.
        """

        self._evidence_memo.store.clear()
        request = self.request
        domain_contract = self.domain_contract
        semantic_profile = self.semantic_profile

        normalized_ids = tuple(dict.fromkeys(candidate_assertion_ids))
        for assertion_id in normalized_ids:
            if self.parsed.get_assertion(assertion_id) is None:
                raise CandidateAdmissionIntegrityError(
                    f"unknown candidate assertion id: {assertion_id}"
                )

        evaluation_order = tuple(sorted(normalized_ids))
        assertions_evaluated = len(evaluation_order)
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
        validate_provenance_snapshot_integrity(
            provenance,
            expected_artifact_ids=artifact_ids,
            expected_revision_ids=revision_ids,
        )
        snapshot_calls = 1
        if snapshot_calls_before is not None:
            snapshot_calls_after = getattr(self.source_reader, "snapshot_call_count", 0)
            snapshot_calls = snapshot_calls_after - snapshot_calls_before

        audience = frozenset(request.audience_labels)
        declared_labels = frozenset(domain_contract.visibility_labels)
        declared_axes = frozenset(domain_contract.scope_axes)
        standing_selector = tuple(request.standing_selector)

        admitted: list[str] = []
        excluded: list[CandidateExclusion] = []
        policy_evaluations = 0

        for assertion_id in evaluation_order:
            assertion = self.parsed.get_assertion(assertion_id)
            assert assertion is not None

            reason = standing_passes(assertion, standing_selector=standing_selector)
            if reason is None:
                reason = scope_passes(
                    assertion,
                    request=request,
                    declared_axes=declared_axes,
                )
            if reason is None:
                reason = domain_declaration_passes(
                    assertion,
                    domain_contract=domain_contract,
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
                    semantic_profile=semantic_profile,
                )
            if reason is None:
                reason = evidence_chain_passes(
                    assertion,
                    parsed=self.parsed,
                    provenance=provenance,
                    audience=audience,
                    declared_labels=declared_labels,
                    domain_contract=domain_contract,
                    memo=self._evidence_memo.store,
                )
            if reason is None:
                policy_evaluations += 1
                if not self.domain_policy.narrow(
                    assertion=copy.deepcopy(assertion),
                    request=request.model_copy(deep=True),
                    domain_contract=domain_contract.model_copy(deep=True),
                    semantic_profile=semantic_profile.model_copy(deep=True),
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
            assertions_evaluated=assertions_evaluated,
            policy_evaluations=policy_evaluations,
            evidence_ids_resolved=len(evidence_ids),
            artifact_ids_requested=len(artifact_ids),
            revision_ids_requested=len(revision_ids),
            provenance_snapshot_calls=snapshot_calls,
        )
        digest = compute_result_digest(
            admitted_assertion_ids=admitted_sorted,
            excluded=excluded_sorted,
        )
        return (
            CandidateAdmissionResult(
                admitted_assertion_ids=admitted_sorted,
                excluded=excluded_sorted,
                work=work,
                result_digest=digest,
            ),
            provenance,
        )
