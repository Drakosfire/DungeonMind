"""Historical reconstruction only; not current knowledge publication or policy.

Use this explicit boundary for exact stored v1-v6 graphs. Current consumers use
``dungeonmind.application.vnext``. No legacy current-write API is exported here.
"""

from ..vnext.errors import LegacyCompatibilityIntegrityError
from .legacy_graph import (
    COMPATIBILITY_DOMAIN_CONTRACT_ID,
    COMPATIBILITY_DOMAIN_CONTRACT_REVISION,
    COMPATIBILITY_MANIFEST_SHA256,
    COMPATIBILITY_MAPPING_REVISION,
    LegacyCompatibilityManifest,
    build_historical_semantic_witness,
    build_parsed_revision_semantic_witness,
    compute_legacy_compatibility_key,
    compute_mapping_implementation_digest,
    decode_legacy_graph_revision,
    decode_legacy_stored_graph_revision,
    load_legacy_world_compat_manifest,
    validate_stored_legacy_graph_revision,
    verify_historical_semantic_parity,
    verify_legacy_compatibility_manifest,
)

__all__ = [
    "COMPATIBILITY_DOMAIN_CONTRACT_ID",
    "COMPATIBILITY_DOMAIN_CONTRACT_REVISION",
    "COMPATIBILITY_MANIFEST_SHA256",
    "COMPATIBILITY_MAPPING_REVISION",
    "LegacyCompatibilityIntegrityError",
    "LegacyCompatibilityManifest",
    "build_historical_semantic_witness",
    "build_parsed_revision_semantic_witness",
    "compute_legacy_compatibility_key",
    "compute_mapping_implementation_digest",
    "decode_legacy_graph_revision",
    "decode_legacy_stored_graph_revision",
    "load_legacy_world_compat_manifest",
    "validate_stored_legacy_graph_revision",
    "verify_historical_semantic_parity",
    "verify_legacy_compatibility_manifest",
]
