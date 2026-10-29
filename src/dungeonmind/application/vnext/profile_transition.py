"""Govern an additive profile change without changing native graph content."""

from typing import NoReturn

from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    DomainContractRef,
    SemanticProfileDescriptorV2,
    SemanticProfileDescriptorV3,
    parse_semantic_profile_descriptor,
)
from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.profile_transition import KnowledgeProfileTransitionV1
from dungeonmind.contracts.vnext.publication import KnowledgePublicationReceipt
from dungeonmind.domain.canonical import canonical_sha256

from .admission import domain_declaration_passes, semantic_profile_passes
from .authority import revision_from_command, verify_stored_revision
from .builder import build_parsed_knowledge_revision
from .errors import KnowledgeProfileTransitionIntegrityError
from .materialization import NATIVE_VNEXT_GRAPH_SCHEMA, decode_native_graph_payload
from .ports import KnowledgeRevisionRepository
from .publication import _publish_validated_command

Profile = SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3


def _fail(reason: str) -> NoReturn:
    raise KnowledgeProfileTransitionIntegrityError(reason)


def _profile_ref(profile: Profile) -> SemanticProfileRef:
    return SemanticProfileRef(
        profile_id=profile.profile_id,
        profile_revision=profile.profile_revision,
        descriptor_sha256=canonical_sha256(profile.model_dump(mode="json")),
    )


def _additive(current: Profile, target: Profile) -> None:
    if (
        current.profile_id != target.profile_id
        or current.profile_revision == target.profile_revision
    ):
        _fail("profile_identity_not_extension")
    if not isinstance(current, SemanticProfileDescriptorV3) and not current.predicates:
        _fail("unrestricted_v2_transition_unsupported")
    for field in ("term_namespaces", "classification_terms"):
        if not set(getattr(current, field)).issubset(getattr(target, field)):
            _fail("profile_permission_removed")
    old_fixed = {p.term: p.model_dump(mode="json") for p in current.predicates}
    new_fixed = {p.term: p.model_dump(mode="json") for p in target.predicates}
    if len(old_fixed) != len(current.predicates) or len(new_fixed) != len(target.predicates):
        _fail("duplicate_fixed_predicate")
    if any(new_fixed.get(term) != spec for term, spec in old_fixed.items()):
        _fail("fixed_predicate_changed")
    old_open = {
        r.namespace: set(r.allowed_value_kinds)
        for r in getattr(current, "open_predicate_namespaces", [])
    }
    new_open = {
        r.namespace: set(r.allowed_value_kinds)
        for r in getattr(target, "open_predicate_namespaces", [])
    }
    if any(
        not kinds.issubset(new_open.get(namespace, set())) for namespace, kinds in old_open.items()
    ):
        _fail("open_permission_removed")
    # Set order does not grant a new permission. Fixed specs were compared above.
    extended = (
        set(target.term_namespaces) != set(current.term_namespaces)
        or set(target.classification_terms) != set(current.classification_terms)
        or new_fixed != old_fixed
        or new_open != old_open
    )
    if not extended:
        _fail("profile_has_no_policy_extension")


def transition_knowledge_semantic_profile(
    *,
    repository: KnowledgeRevisionRepository,
    request: KnowledgeProfileTransitionV1,
    domain_contract: DomainContractDescriptor,
    current_profile: Profile,
    target_profile: Profile,
) -> KnowledgePublicationReceipt:
    """Publish one unchanged graph under an explicitly additive profile revision.

    The immutable parent reconstructs the same command on every retry. Existing
    publication machinery resolves receipts before CAS and recovers lost acks;
    no current-head read, alternate operation, or new receipt authority is added.
    """
    request = KnowledgeProfileTransitionV1.model_validate(request.model_dump(mode="json"))
    domain = DomainContractDescriptor.model_validate(domain_contract.model_dump(mode="json"))
    current = parse_semantic_profile_descriptor(current_profile.model_dump(mode="json"))
    target = parse_semantic_profile_descriptor(target_profile.model_dump(mode="json"))
    domain_ref = DomainContractRef(
        domain_id=domain.domain_id,
        domain_revision=domain.domain_revision,
        descriptor_sha256=canonical_sha256(domain.model_dump(mode="json")),
    )
    if (
        request.domain_contract_ref != domain_ref
        or request.from_profile_ref != _profile_ref(current)
        or request.to_profile_ref != _profile_ref(target)
    ):
        _fail("descriptor_reference_mismatch")
    _additive(current, target)
    parent = repository.get_revision(request.space_id, request.expected_parent_revision_id)
    if parent is None:
        _fail("parent_unavailable")
    verify_stored_revision(parent)
    if (
        parent.revision.space_id != request.space_id
        or parent.revision.revision_id != request.expected_parent_revision_id
        or parent.revision.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA
        or parent.revision.domain_contract_ref != domain_ref
        or parent.revision.semantic_profile_ref != request.from_profile_ref
    ):
        _fail("parent_authority_mismatch")
    command = PublishKnowledgeRevisionCommand(
        space_id=request.space_id,
        parent_revision_id=request.expected_parent_revision_id,
        expected_parent_revision_id=request.expected_parent_revision_id,
        operation_ids=[request.publication_id],
        graph_schema=parent.revision.graph_schema,
        graph_payload=parent.graph_payload,
        domain_contract_ref=domain_ref,
        semantic_profile_ref=request.to_profile_ref,
        migration_origin_ref=parent.revision.migration_origin_ref,
        created_at=request.created_at,
    )
    child = build_parsed_knowledge_revision(
        revision=revision_from_command(command),
        decoded_content=decode_native_graph_payload(command.graph_payload),
    )
    for assertion in child.assertions_by_id.values():
        if (
            domain_declaration_passes(assertion, domain_contract=domain) is not None
            or semantic_profile_passes(assertion, semantic_profile=target) is not None
        ):
            _fail("target_rejects_existing_assertion")
    return _publish_validated_command(
        command, repository=repository, publication_id=request.publication_id
    )
