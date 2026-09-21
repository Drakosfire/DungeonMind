"""Content-addressed identity for native vNext knowledge revisions.

``created_at`` is durable history and is intentionally absent. Pinned
DomainContract, SemanticProfile, and MigrationOrigin refs are part of identity
so identical graph bytes with different authority pins cannot share an id.
"""

from __future__ import annotations

from collections.abc import Sequence

from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.domain import DomainContractRef
from dungeonmind.contracts.vnext.knowledge import MigrationOriginRef
from dungeonmind.domain.canonical import canonical_sha256

REVISION_ID_PREFIX = "rev"
REVISION_ID_HEX_LENGTH = 32
IDENTITY_SCHEMA = "dm_knowledge_revision_identity_v1"


def compute_knowledge_revision_id(
    *,
    space_id: str,
    parent_revision_id: str | None,
    operation_ids: Sequence[str],
    graph_schema: str,
    graph_payload_sha256: str,
    domain_contract_ref: DomainContractRef,
    semantic_profile_ref: SemanticProfileRef,
    migration_origin_ref: MigrationOriginRef | None,
) -> str:
    """Return ``rev:<sha256-32>`` over the canonical native identity material."""
    material = {
        "schema": IDENTITY_SCHEMA,
        "space_id": space_id,
        "parent_revision_id": parent_revision_id,
        "operation_ids": list(operation_ids),
        "graph_schema": graph_schema,
        "graph_payload_sha256": graph_payload_sha256,
        "domain_contract_ref": {
            "domain_id": domain_contract_ref.domain_id,
            "domain_revision": domain_contract_ref.domain_revision,
            "descriptor_sha256": domain_contract_ref.descriptor_sha256,
        },
        "semantic_profile_ref": {
            "profile_id": semantic_profile_ref.profile_id,
            "profile_revision": semantic_profile_ref.profile_revision,
            "descriptor_sha256": semantic_profile_ref.descriptor_sha256,
        },
        "migration_origin_ref": (
            None if migration_origin_ref is None else migration_origin_ref.model_dump(mode="json")
        ),
    }
    digest = canonical_sha256(material)
    return f"{REVISION_ID_PREFIX}:{digest[:REVISION_ID_HEX_LENGTH]}"
