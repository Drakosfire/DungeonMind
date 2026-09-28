"""Public construction of one canonical empty native KnowledgeSpace genesis."""

from __future__ import annotations

from datetime import datetime

from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    DomainContractRef,
    SemanticProfileDescriptorV2,
    SemanticProfileDescriptorV3,
)
from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.publication import KnowledgePublicationReceipt
from dungeonmind.domain.canonical import canonical_sha256

from .authority import revision_from_command
from .builder import build_parsed_knowledge_revision
from .errors import KnowledgePublicationIntegrityError
from .materialization import (
    NATIVE_VNEXT_GRAPH_SCHEMA,
    decode_native_graph_payload,
    encode_native_graph_payload,
)
from .ports import KnowledgeRevisionRepository
from .publication import _publish_validated_command


def initialize_empty_knowledge_space(
    *,
    repository: KnowledgeRevisionRepository,
    space_id: str,
    initialization_id: str,
    created_at: datetime,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
) -> KnowledgePublicationReceipt:
    """Initialize a previously absent namespace with one canonical empty genesis.

    ``initialization_id`` is both the sole revision operation identity and the
    durable publication identity. Exact retries therefore recover the original
    receipt without consulting or moving the current head.
    """
    if not isinstance(space_id, str) or not space_id.strip():
        raise KnowledgePublicationIntegrityError("space_id_blank")
    if not isinstance(initialization_id, str) or not initialization_id.strip():
        raise KnowledgePublicationIntegrityError("initialization_id_blank")
    if not isinstance(created_at, datetime) or created_at.utcoffset() is None:
        raise KnowledgePublicationIntegrityError("created_at_not_timezone_aware")
    if not isinstance(domain_contract, DomainContractDescriptor):
        raise KnowledgePublicationIntegrityError("domain_contract_type_invalid")
    if not isinstance(
        semantic_profile, (SemanticProfileDescriptorV2, SemanticProfileDescriptorV3)
    ):
        raise KnowledgePublicationIntegrityError("semantic_profile_type_invalid")

    # Snapshot caller-owned mutable models before deriving any sealed identity.
    domain_snapshot = DomainContractDescriptor.model_validate(
        domain_contract.model_dump(mode="json")
    )
    profile_type = type(semantic_profile)
    profile_snapshot = profile_type.model_validate(semantic_profile.model_dump(mode="json"))

    payload = encode_native_graph_payload(
        entities={},
        assertions={},
        aliases={},
        evidence={},
    )
    command = PublishKnowledgeRevisionCommand(
        space_id=space_id,
        parent_revision_id=None,
        expected_parent_revision_id=None,
        operation_ids=[initialization_id],
        graph_schema=NATIVE_VNEXT_GRAPH_SCHEMA,
        graph_payload=payload,
        domain_contract_ref=DomainContractRef(
            domain_id=domain_snapshot.domain_id,
            domain_revision=domain_snapshot.domain_revision,
            descriptor_sha256=canonical_sha256(domain_snapshot.model_dump(mode="json")),
        ),
        semantic_profile_ref=SemanticProfileRef(
            profile_id=profile_snapshot.profile_id,
            profile_revision=profile_snapshot.profile_revision,
            descriptor_sha256=canonical_sha256(profile_snapshot.model_dump(mode="json")),
        ),
        migration_origin_ref=None,
        created_at=created_at,
    )
    expected = revision_from_command(command)
    decoded = decode_native_graph_payload(payload)
    build_parsed_knowledge_revision(revision=expected, decoded_content=decoded)
    return _publish_validated_command(
        command,
        publication_id=initialization_id,
        repository=repository,
    )
