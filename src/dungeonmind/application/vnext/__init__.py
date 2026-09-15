"""Application-layer vNext normalized immutable revision serving substrate.

Provides ``ParsedKnowledgeRevision``, pure builders, frozen data structures,
and deterministic structural graph indexes over already-decoded vNext knowledge primitives.
"""

from __future__ import annotations

from .builder import DecodedKnowledgeContent, build_parsed_knowledge_revision
from .errors import RevisionStructuralIntegrityError
from .frozen_json import (
    FrozenDict,
    FrozenJsonValue,
    canonical_json_bytes,
    canonical_json_text,
    freeze_json_value,
    thaw_json_value,
)
from .model import (
    PARSED_REVISION_FORMAT_VERSION,
    ParsedKnowledgeRevision,
    compute_compatibility_key,
    compute_semantic_digest,
)
from .records import (
    ParsedAssertion,
    ParsedAssertionMetadata,
    ParsedAssertionValue,
    ParsedDomainContractRef,
    ParsedDomainMetadataEntry,
    ParsedDomainTemporalScope,
    ParsedEntity,
    ParsedEntityRefValue,
    ParsedEvidenceRef,
    ParsedIdentityAlias,
    ParsedKnowledgeRevisionIdentity,
    ParsedLabelsAllVisibility,
    ParsedLabelsAnyVisibility,
    ParsedLiteralValue,
    ParsedMigrationOriginRef,
    ParsedPublicVisibility,
    ParsedScopeBinding,
    ParsedSemanticProfileRef,
    ParsedTemporalScope,
    ParsedTermRefValue,
    ParsedTimelessTemporalScope,
    ParsedUnknownTemporalScope,
    ParsedUtcIntervalTemporalScope,
    ParsedVisibility,
)

__all__ = [
    "PARSED_REVISION_FORMAT_VERSION",
    "DecodedKnowledgeContent",
    "FrozenDict",
    "FrozenJsonValue",
    "ParsedAssertion",
    "ParsedAssertionMetadata",
    "ParsedAssertionValue",
    "ParsedDomainContractRef",
    "ParsedDomainMetadataEntry",
    "ParsedDomainTemporalScope",
    "ParsedEntity",
    "ParsedEntityRefValue",
    "ParsedEvidenceRef",
    "ParsedIdentityAlias",
    "ParsedKnowledgeRevision",
    "ParsedKnowledgeRevisionIdentity",
    "ParsedLabelsAllVisibility",
    "ParsedLabelsAnyVisibility",
    "ParsedLiteralValue",
    "ParsedMigrationOriginRef",
    "ParsedPublicVisibility",
    "ParsedScopeBinding",
    "ParsedSemanticProfileRef",
    "ParsedTemporalScope",
    "ParsedTermRefValue",
    "ParsedTimelessTemporalScope",
    "ParsedUnknownTemporalScope",
    "ParsedUtcIntervalTemporalScope",
    "ParsedVisibility",
    "RevisionStructuralIntegrityError",
    "build_parsed_knowledge_revision",
    "canonical_json_bytes",
    "canonical_json_text",
    "compute_compatibility_key",
    "compute_semantic_digest",
    "freeze_json_value",
    "thaw_json_value",
]
