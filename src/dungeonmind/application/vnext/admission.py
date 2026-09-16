"""Generic kernel gates and domain admission policy for vNext candidate admission."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from dungeonmind.contracts.vnext.common import KnowledgeStanding
from dungeonmind.contracts.vnext.domain import DomainContractDescriptor, SemanticProfileDescriptorV2
from dungeonmind.contracts.vnext.projection import ProjectionRequest
from dungeonmind.contracts.vnext.source import SourceArtifactV3
from dungeonmind.domain.canonical import canonical_sha256

from .errors import KnowledgeReadContextIntegrityError
from .model import ParsedKnowledgeRevision
from .provenance import KnowledgeProvenanceSnapshot
from .records import (
    ParsedAssertion,
    ParsedDomainTemporalScope,
    ParsedLabelsAllVisibility,
    ParsedLabelsAnyVisibility,
    ParsedPublicVisibility,
    ParsedVisibility,
)


@dataclass(frozen=True, slots=True)
class AdmissionWorkCounts:
    candidate_count: int
    assertions_evaluated: int
    policy_evaluations: int
    evidence_ids_resolved: int
    artifact_ids_requested: int
    revision_ids_requested: int
    provenance_snapshot_calls: int


@dataclass(frozen=True, slots=True)
class CandidateExclusion:
    assertion_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class CandidateAdmissionResult:
    admitted_assertion_ids: tuple[str, ...]
    excluded: tuple[CandidateExclusion, ...]
    work: AdmissionWorkCounts
    result_digest: str


class DomainAdmissionPolicy(Protocol):
    @property
    def policy_id(self) -> str: ...

    def narrow(
        self,
        *,
        assertion: ParsedAssertion,
        request: ProjectionRequest,
        domain_contract: DomainContractDescriptor,
        semantic_profile: SemanticProfileDescriptorV2,
        provenance: KnowledgeProvenanceSnapshot,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class AlwaysAdmitPolicy:
    policy_id: str

    def narrow(
        self,
        *,
        assertion: ParsedAssertion,
        request: ProjectionRequest,
        domain_contract: DomainContractDescriptor,
        semantic_profile: SemanticProfileDescriptorV2,
        provenance: KnowledgeProvenanceSnapshot,
    ) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class ExcludeByAssertionIdPolicy:
    policy_id: str
    excluded_assertion_ids: frozenset[str]

    def narrow(
        self,
        *,
        assertion: ParsedAssertion,
        request: ProjectionRequest,
        domain_contract: DomainContractDescriptor,
        semantic_profile: SemanticProfileDescriptorV2,
        provenance: KnowledgeProvenanceSnapshot,
    ) -> bool:
        return assertion.assertion_id not in self.excluded_assertion_ids


@dataclass(frozen=True, slots=True)
class ClaimModeFilterPolicy:
    policy_id: str
    allowed_claim_modes: frozenset[str]

    def narrow(
        self,
        *,
        assertion: ParsedAssertion,
        request: ProjectionRequest,
        domain_contract: DomainContractDescriptor,
        semantic_profile: SemanticProfileDescriptorV2,
        provenance: KnowledgeProvenanceSnapshot,
    ) -> bool:
        return assertion.metadata.claim_mode in self.allowed_claim_modes


class DomainAdmissionPolicyRegistry:
    def __init__(self, policies: Mapping[str, DomainAdmissionPolicy]) -> None:
        self._policies = dict(policies)

    def resolve(self, policy_id: str) -> DomainAdmissionPolicy:
        policy = self._policies.get(policy_id)
        if policy is None:
            raise KnowledgeReadContextIntegrityError(f"unknown admission policy: {policy_id}")
        if policy.policy_id != policy_id:
            raise KnowledgeReadContextIntegrityError(
                f"admission policy identity mismatch: {policy.policy_id!r} != {policy_id!r}"
            )
        return policy


def compute_result_digest(
    *,
    admitted_assertion_ids: Sequence[str],
    excluded: Sequence[CandidateExclusion],
) -> str:
    return canonical_sha256(
        {
            "admitted_assertion_ids": list(admitted_assertion_ids),
            "excluded": [
                {"assertion_id": item.assertion_id, "reason": item.reason} for item in excluded
            ],
        }
    )


def visibility_visible(
    visibility: ParsedVisibility,
    *,
    audience: frozenset[str],
    declared_labels: frozenset[str],
) -> bool:
    if isinstance(visibility, ParsedPublicVisibility):
        return True
    if isinstance(visibility, ParsedLabelsAnyVisibility):
        if any(label not in declared_labels for label in visibility.labels):
            return False
        return bool(audience.intersection(visibility.labels))
    if isinstance(visibility, ParsedLabelsAllVisibility):
        if any(label not in declared_labels for label in visibility.labels):
            return False
        return set(visibility.labels).issubset(audience)
    return False


def _contract_visibility_visible(
    artifact: SourceArtifactV3,
    *,
    audience: frozenset[str],
    declared_labels: frozenset[str],
) -> bool:
    visibility = artifact.visibility
    if visibility.kind == "public":
        return True
    if visibility.kind == "labels_any":
        labels = tuple(visibility.labels)
        if any(label not in declared_labels for label in labels):
            return False
        return bool(audience.intersection(labels))
    if visibility.kind == "labels_all":
        labels = tuple(visibility.labels)
        if any(label not in declared_labels for label in labels):
            return False
        return set(labels).issubset(audience)
    return False


def standing_passes(
    assertion: ParsedAssertion,
    *,
    standing_selector: Sequence[KnowledgeStanding],
) -> str | None:
    if not standing_selector:
        return "empty_standing_selector"
    if assertion.metadata.standing not in standing_selector:
        return "standing"
    return None


def scope_passes(
    assertion: ParsedAssertion,
    *,
    request: ProjectionRequest,
    declared_axes: frozenset[str],
) -> str | None:
    bindings = assertion.metadata.scope
    if not bindings:
        if request.scope_selector.include_unscoped:
            return None
        return "scope"

    request_bindings = {
        (binding.axis, binding.value) for binding in request.scope_selector.bindings
    }
    wildcards = frozenset(request.scope_selector.wildcard_axes)

    for binding in bindings:
        if binding.axis not in declared_axes:
            return "domain_declaration"
        if (binding.axis, binding.value) in request_bindings:
            continue
        if binding.axis in wildcards:
            continue
        return "scope"
    return None


def assertion_visibility_passes(
    assertion: ParsedAssertion,
    *,
    audience: frozenset[str],
    declared_labels: frozenset[str],
) -> str | None:
    if not visibility_visible(
        assertion.metadata.visibility,
        audience=audience,
        declared_labels=declared_labels,
    ):
        return "visibility"
    return None


def domain_declaration_passes(
    assertion: ParsedAssertion,
    *,
    domain_contract: DomainContractDescriptor,
) -> str | None:
    scope_axes = frozenset(domain_contract.scope_axes)
    visibility_labels = frozenset(domain_contract.visibility_labels)
    claim_modes = frozenset(domain_contract.claim_modes)
    temporal_schemas = frozenset(domain_contract.temporal_extension_schemas)
    metadata_schemas = frozenset(domain_contract.domain_metadata_schemas)

    for binding in assertion.metadata.scope:
        if binding.axis not in scope_axes:
            return "domain_declaration"

    vis = assertion.metadata.visibility
    if isinstance(vis, (ParsedLabelsAnyVisibility, ParsedLabelsAllVisibility)) and any(
        label not in visibility_labels for label in vis.labels
    ):
        return "domain_declaration"

    if assertion.metadata.claim_mode not in claim_modes:
        return "domain_declaration"

    temporal = assertion.metadata.temporal_scope
    if isinstance(temporal, ParsedDomainTemporalScope) and (
        temporal.schema_term not in temporal_schemas
    ):
        return "domain_declaration"

    for entry in assertion.metadata.domain_metadata:
        if entry.schema_term not in metadata_schemas:
            return "domain_declaration"

    return None


def semantic_profile_passes(
    assertion: ParsedAssertion,
    *,
    semantic_profile: SemanticProfileDescriptorV2,
) -> str | None:
    if not semantic_profile.predicates:
        return None
    predicate_map = {item.term: item for item in semantic_profile.predicates}
    spec = predicate_map.get(assertion.predicate)
    if spec is None:
        return "semantic_profile"
    value_kind = assertion.value.kind
    if value_kind not in spec.allowed_value_kinds:
        return "semantic_profile"
    return None


def validate_request_vocabulary(
    request: ProjectionRequest,
    *,
    domain_contract: DomainContractDescriptor,
) -> None:
    scope_axes = frozenset(domain_contract.scope_axes)
    visibility_labels = frozenset(domain_contract.visibility_labels)

    for binding in request.scope_selector.bindings:
        if binding.axis not in scope_axes:
            raise KnowledgeReadContextIntegrityError(
                f"undeclared scope axis in request: {binding.axis}"
            )
    for axis in request.scope_selector.wildcard_axes:
        if axis not in scope_axes:
            raise KnowledgeReadContextIntegrityError(
                f"undeclared wildcard scope axis in request: {axis}"
            )
    for label in request.audience_labels:
        if label not in visibility_labels:
            raise KnowledgeReadContextIntegrityError(
                f"undeclared audience label in request: {label}"
            )


def evidence_chain_passes(
    assertion: ParsedAssertion,
    *,
    parsed: ParsedKnowledgeRevision,
    provenance: KnowledgeProvenanceSnapshot,
    audience: frozenset[str],
    declared_labels: frozenset[str],
    domain_contract: DomainContractDescriptor,
    memo: dict[str, str | None],
) -> str | None:
    source_schemas = frozenset(domain_contract.source_annotation_schemas)
    for evidence_ref_id in assertion.metadata.evidence_ref_ids:
        if evidence_ref_id in memo:
            cached = memo[evidence_ref_id]
            if cached is not None:
                return cached
            continue

        evidence = parsed.get_evidence(evidence_ref_id)
        if evidence is None:
            memo[evidence_ref_id] = "source_missing"
            return "source_missing"

        for entry in evidence.domain_metadata:
            if entry.schema_term not in source_schemas:
                memo[evidence_ref_id] = "domain_declaration"
                return "domain_declaration"

        artifact_id = evidence.source_artifact_id
        artifact = provenance.get_artifact(artifact_id)
        if artifact_id in provenance.missing_artifact_ids or artifact is None:
            memo[evidence_ref_id] = "source_missing"
            return "source_missing"

        if not _contract_visibility_visible(
            artifact,
            audience=audience,
            declared_labels=declared_labels,
        ):
            memo[evidence_ref_id] = "source_visibility"
            return "source_visibility"

        if artifact.status != "active":
            memo[evidence_ref_id] = "source_inactive"
            return "source_inactive"

        for entry in artifact.domain_metadata:
            if entry.schema_term not in source_schemas:
                memo[evidence_ref_id] = "domain_declaration"
                return "domain_declaration"

        if evidence.source_revision_id is not None:
            revision_id = evidence.source_revision_id
            revision = provenance.get_revision(revision_id)
            if revision_id in provenance.missing_revision_ids or revision is None:
                memo[evidence_ref_id] = "source_revision_invalid"
                return "source_revision_invalid"
            if revision.source_artifact_id != artifact_id:
                memo[evidence_ref_id] = "source_revision_invalid"
                return "source_revision_invalid"

        memo[evidence_ref_id] = None

    return None


def collect_evidence_dependencies(
    parsed: ParsedKnowledgeRevision,
    candidate_assertion_ids: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    evidence_ids: set[str] = set()
    artifact_ids: set[str] = set()
    revision_ids: set[str] = set()

    for assertion_id in candidate_assertion_ids:
        assertion = parsed.get_assertion(assertion_id)
        if assertion is None:
            continue
        for evidence_ref_id in assertion.metadata.evidence_ref_ids:
            evidence_ids.add(evidence_ref_id)
            evidence = parsed.get_evidence(evidence_ref_id)
            if evidence is None:
                continue
            artifact_ids.add(evidence.source_artifact_id)
            if evidence.source_revision_id:
                revision_ids.add(evidence.source_revision_id)

    return (
        tuple(sorted(evidence_ids)),
        tuple(sorted(artifact_ids)),
        tuple(sorted(revision_ids)),
    )
