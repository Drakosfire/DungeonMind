"""Legacy compatibility decoder and semantic parity codec for DungeonMind historical graphs.

Supports exact stored revisions across all six historical schema generations:
- ``dm_union_graph_v1``
- ``dm_union_graph_v2``
- ``dm_union_graph_v3``
- ``dm_union_graph_v4``
- ``dm_union_graph_v5``
- ``dm_union_graph_v6``

Delegates historical semantic interpretation to ``VersionedUnionGraphSnapshotReader``
and maps the resulting historical graphs into the immutable ``ParsedKnowledgeRevision``
serving model with deterministic, bidirectional semantic parity.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from importlib import resources
from pathlib import Path
from typing import Any

from ...contracts.graph import StoredGraphRevision, WorldGraphRevision
from ...contracts.knowledge_assertion import (
    CanonState,
    KnowledgeAssertionMetadataV1,
    TemporalScopeKind,
    Visibility,
)
from ...contracts.vnext.common import KnowledgeStanding
from ...domain.canonical import canonical_json, canonical_sha256
from ...domain.errors import PersistenceIntegrityError
from ..graph_snapshot import (
    GRAPH_SCHEMA_V1,
    GRAPH_SCHEMA_V2,
    GRAPH_SCHEMA_V3,
    GRAPH_SCHEMA_V4,
    GRAPH_SCHEMA_V5,
    GRAPH_SCHEMA_V6,
    GraphEvidenceRecord,
    ParsedGraphSnapshot,
    SemanticProfileRegistry,
    VersionedUnionGraphSnapshotReader,
    effective_endpoint_kind,
)
from .builder import build_parsed_knowledge_revision_from_records
from .errors import LegacyCompatibilityIntegrityError
from .frozen_json import (
    freeze_json_value,
    thaw_json_value,
)
from .model import PARSED_REVISION_FORMAT_VERSION, ParsedKnowledgeRevision
from .records import (
    ParsedAssertion,
    ParsedAssertionMetadata,
    ParsedDomainContractRef,
    ParsedDomainMetadataEntry,
    ParsedDomainTemporalScope,
    ParsedEntity,
    ParsedEntityRefValue,
    ParsedEvidenceRef,
    ParsedIdentityAlias,
    ParsedKnowledgeRevisionIdentity,
    ParsedLabelsAnyVisibility,
    ParsedLiteralValue,
    ParsedScopeBinding,
    ParsedSemanticProfileRef,
    ParsedTemporalScope,
    ParsedTimelessTemporalScope,
    ParsedUnknownTemporalScope,
    ParsedVisibility,
)

# Packaged resource (library-safe) + audit Docs copy path
_PACKAGED_MANIFEST_RESOURCE = "dm_legacy_world_compat_v1.json"
DOCS_MANIFEST_AUDIT_PATH = Path("Docs/Compatibility/dm_legacy_world_compat_v1.json")
COMPATIBILITY_MAPPING_REVISION = "dm_legacy_world_compat_v1"
COMPATIBILITY_MANIFEST_SHA256 = (
    "f408ce73b8efb32a36e4fb29eb68e9242cb358a76c0c0b60eafdce5046abbe4f"
)
COMPATIBILITY_DOMAIN_CONTRACT_ID = "dungeonmind.compat.legacy_world"
COMPATIBILITY_DOMAIN_CONTRACT_REVISION = "1"
UNPROFILED_SEMANTIC_PROFILE_ID = "legacy.unprofiled"
UNPROFILED_SEMANTIC_PROFILE_REVISION = "none"
UNPROFILED_DESCRIPTOR_SHA256 = "0" * 64
LEGACY_COMPATIBILITY_IDENTITY_KIND = "dm_legacy_world_compat_identity_v1"

SUPPORTED_HISTORICAL_SCHEMAS: frozenset[str] = frozenset([
    GRAPH_SCHEMA_V1,
    GRAPH_SCHEMA_V2,
    GRAPH_SCHEMA_V3,
    GRAPH_SCHEMA_V4,
    GRAPH_SCHEMA_V5,
    GRAPH_SCHEMA_V6,
])

_MANIFEST_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "manifest_schema",
    "compatibility_mapping_revision",
    "vnext_format_version",
    "parsed_format_version",
    "domain_contract_id",
    "domain_contract_revision",
    "unprofiled_semantic_profile_id",
    "unprofiled_semantic_profile_revision",
    "unprofiled_descriptor_sha256",
    "supported_historical_schemas",
    "synthetic_assertion_id_templates",
    "predicate_mappings",
    "scope_and_visibility_rules",
    "v1_v3_coarse_metadata_rules",
    "epistemic_translation_rules",
    "canon_state_translation_rules",
    "temporal_translation_rules",
    "evidence_translation_rules",
    "relationship_aspect_rules",
    "identity_alias_admission_rules",
)


@dataclass(frozen=True, slots=True)
class LegacyCompatibilityManifest:
    """Verified compatibility mapping identity + executable mapping semantics."""

    manifest_schema: str
    compatibility_mapping_revision: str
    vnext_format_version: str
    parsed_format_version: str
    domain_contract_id: str
    domain_contract_revision: str
    unprofiled_semantic_profile_id: str
    unprofiled_semantic_profile_revision: str
    unprofiled_descriptor_sha256: str
    supported_historical_schemas: tuple[str, ...]
    synthetic_assertion_id_templates: Mapping[str, str]
    predicate_mappings: Mapping[str, str]
    scope_and_visibility_rules: Mapping[str, Any]
    v1_v3_coarse_metadata_rules: Mapping[str, Any]
    epistemic_translation_rules: Mapping[str, Any]
    canon_state_translation_rules: Mapping[str, Any]
    temporal_translation_rules: Mapping[str, Any]
    evidence_translation_rules: Mapping[str, Any]
    relationship_aspect_rules: Mapping[str, Any]
    identity_alias_admission_rules: Mapping[str, Any]
    manifest_sha256: str

    def to_canonical_dict(self) -> dict[str, Any]:
        """Reconstruct the canonical manifest document for digest verification."""
        return {
            "manifest_schema": self.manifest_schema,
            "compatibility_mapping_revision": self.compatibility_mapping_revision,
            "vnext_format_version": self.vnext_format_version,
            "parsed_format_version": self.parsed_format_version,
            "domain_contract_id": self.domain_contract_id,
            "domain_contract_revision": self.domain_contract_revision,
            "unprofiled_semantic_profile_id": self.unprofiled_semantic_profile_id,
            "unprofiled_semantic_profile_revision": (
                self.unprofiled_semantic_profile_revision
            ),
            "unprofiled_descriptor_sha256": self.unprofiled_descriptor_sha256,
            "supported_historical_schemas": list(self.supported_historical_schemas),
            "synthetic_assertion_id_templates": dict(
                self.synthetic_assertion_id_templates
            ),
            "predicate_mappings": dict(self.predicate_mappings),
            "scope_and_visibility_rules": dict(self.scope_and_visibility_rules),
            "v1_v3_coarse_metadata_rules": dict(self.v1_v3_coarse_metadata_rules),
            "epistemic_translation_rules": dict(self.epistemic_translation_rules),
            "canon_state_translation_rules": dict(self.canon_state_translation_rules),
            "temporal_translation_rules": dict(self.temporal_translation_rules),
            "evidence_translation_rules": dict(self.evidence_translation_rules),
            "relationship_aspect_rules": dict(self.relationship_aspect_rules),
            "identity_alias_admission_rules": dict(
                self.identity_alias_admission_rules
            ),
        }


def _read_packaged_manifest_bytes() -> bytes:
    package = resources.files("dungeonmind.application.vnext.data")
    resource = package.joinpath(_PACKAGED_MANIFEST_RESOURCE)
    with resources.as_file(resource) as path:
        return path.read_bytes()


def _manifest_from_raw(raw_data: dict[str, Any]) -> LegacyCompatibilityManifest:
    missing = [k for k in _MANIFEST_TOP_LEVEL_KEYS if k not in raw_data]
    if missing:
        raise LegacyCompatibilityIntegrityError(
            f"compatibility manifest missing required keys: {missing}",
            details={"missing_keys": missing},
        )
    return LegacyCompatibilityManifest(
        manifest_schema=str(raw_data["manifest_schema"]),
        compatibility_mapping_revision=str(raw_data["compatibility_mapping_revision"]),
        vnext_format_version=str(raw_data["vnext_format_version"]),
        parsed_format_version=str(raw_data["parsed_format_version"]),
        domain_contract_id=str(raw_data["domain_contract_id"]),
        domain_contract_revision=str(raw_data["domain_contract_revision"]),
        unprofiled_semantic_profile_id=str(raw_data["unprofiled_semantic_profile_id"]),
        unprofiled_semantic_profile_revision=str(
            raw_data["unprofiled_semantic_profile_revision"]
        ),
        unprofiled_descriptor_sha256=str(raw_data["unprofiled_descriptor_sha256"]),
        supported_historical_schemas=tuple(raw_data["supported_historical_schemas"]),
        synthetic_assertion_id_templates=dict(
            raw_data["synthetic_assertion_id_templates"]
        ),
        predicate_mappings=dict(raw_data["predicate_mappings"]),
        scope_and_visibility_rules=dict(raw_data["scope_and_visibility_rules"]),
        v1_v3_coarse_metadata_rules=dict(raw_data["v1_v3_coarse_metadata_rules"]),
        epistemic_translation_rules=dict(raw_data["epistemic_translation_rules"]),
        canon_state_translation_rules=dict(raw_data["canon_state_translation_rules"]),
        temporal_translation_rules=dict(raw_data["temporal_translation_rules"]),
        evidence_translation_rules=dict(raw_data["evidence_translation_rules"]),
        relationship_aspect_rules=dict(raw_data["relationship_aspect_rules"]),
        identity_alias_admission_rules=dict(
            raw_data["identity_alias_admission_rules"]
        ),
        manifest_sha256=canonical_sha256(raw_data),
    )


def verify_legacy_compatibility_manifest(
    manifest: LegacyCompatibilityManifest,
) -> LegacyCompatibilityManifest:
    """Fail closed unless the manifest's declared digest matches its content."""
    computed = canonical_sha256(manifest.to_canonical_dict())
    if computed != manifest.manifest_sha256:
        raise LegacyCompatibilityIntegrityError(
            "injected compatibility manifest digest mismatch: "
            f"declared {manifest.manifest_sha256}, computed {computed}",
            details={
                "declared_sha256": manifest.manifest_sha256,
                "computed_sha256": computed,
            },
        )
    return manifest


def load_legacy_world_compat_manifest(
    path: Path | str | None = None,
) -> LegacyCompatibilityManifest:
    """Load and verify the packaged (or explicit audit-path) compatibility manifest."""
    if path is None:
        try:
            raw_bytes = _read_packaged_manifest_bytes()
            raw_data = json.loads(raw_bytes.decode("utf-8"))
        except Exception as exc:
            raise LegacyCompatibilityIntegrityError(
                f"failed to load packaged compatibility manifest: {exc}",
                details={"resource": _PACKAGED_MANIFEST_RESOURCE},
            ) from exc
    else:
        manifest_file = Path(path)
        if not manifest_file.exists():
            raise LegacyCompatibilityIntegrityError(
                f"compatibility manifest not found at {manifest_file}",
                details={"path": str(manifest_file)},
            )
        try:
            raw_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise LegacyCompatibilityIntegrityError(
                f"failed to parse compatibility manifest {manifest_file}: {exc}",
                details={"path": str(manifest_file)},
            ) from exc

    if not isinstance(raw_data, dict):
        raise LegacyCompatibilityIntegrityError(
            "compatibility manifest must be a JSON object",
            details={"type": type(raw_data).__name__},
        )

    manifest = _manifest_from_raw(raw_data)
    if path is None and manifest.manifest_sha256 != COMPATIBILITY_MANIFEST_SHA256:
        raise LegacyCompatibilityIntegrityError(
            "compatibility manifest digest mismatch: "
            f"expected {COMPATIBILITY_MANIFEST_SHA256}, got {manifest.manifest_sha256}",
            details={
                "expected_sha256": COMPATIBILITY_MANIFEST_SHA256,
                "computed_sha256": manifest.manifest_sha256,
            },
        )
    return verify_legacy_compatibility_manifest(manifest)


def compute_legacy_compatibility_key(
    *,
    mapping_revision: str,
    mapping_manifest_sha256: str,
    mapping_implementation_digest: str,
    graph_schema: str,
    historical_parse_compatibility_id: str,
    semantic_profile_ref: ParsedSemanticProfileRef,
    parsed_format_version: str,
    legacy_payload_sha256: str,
) -> str:
    """Legacy-specific compatibility identity (does not alter native V1.1 keys)."""
    payload = {
        "kind": LEGACY_COMPATIBILITY_IDENTITY_KIND,
        "mapping_revision": mapping_revision,
        "mapping_manifest_sha256": mapping_manifest_sha256,
        "mapping_implementation_digest": mapping_implementation_digest,
        "graph_schema": graph_schema,
        "historical_parse_compatibility_id": historical_parse_compatibility_id,
        "semantic_profile_ref": {
            "profile_id": semantic_profile_ref.profile_id,
            "profile_revision": semantic_profile_ref.profile_revision,
            "descriptor_sha256": semantic_profile_ref.descriptor_sha256,
        },
        "parsed_format_version": parsed_format_version,
        "legacy_payload_sha256": legacy_payload_sha256,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


_SEALED_COMPATIBILITY_SOURCE_NAMES: tuple[str, ...] = (
    "_identity_alias_admitted_from_metadata",
    "_synthetic_v1_alias_assertion_id",
    "_translate_assertion_metadata",
    "_v1_alias_assertion_ids",
    "decode_legacy_graph_revision",
)


def compute_mapping_implementation_digest(
    manifest: LegacyCompatibilityManifest,
    *,
    translator_sources: Mapping[str, str] | None = None,
) -> str:
    """Hash manifest semantics plus the full sealed compatibility-codec surface.

    The sealed set must include every function that can change normalized
    compatibility meaning: metadata translation, synthetic alias identity,
    identity-alias admission, and the decode entrypoint that performs
    evidence/relationship/object mapping.
    """
    if translator_sources is None:
        sealed_sources: dict[str, str] = {
            name: inspect.getsource(globals()[name])
            for name in _SEALED_COMPATIBILITY_SOURCE_NAMES
        }
    else:
        sealed_sources = dict(translator_sources)

    payload = {
        "manifest_canonical": manifest.to_canonical_dict(),
        "manifest_sha256": manifest.manifest_sha256,
        "translator_sources": dict(sorted(sealed_sources.items())),
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()



def _synthetic_v1_alias_assertion_id(
    object_id: str,
    *,
    occurrence: int,
    alias_text: str,
    template: str,
) -> str:
    alias_sha256 = hashlib.sha256(alias_text.encode("utf-8")).hexdigest()
    return (
        template.replace("{object_id}", object_id)
        .replace("{occurrence}", str(occurrence))
        .replace("{alias_sha256}", alias_sha256)
    )


def _v1_alias_assertion_ids(
    object_id: str,
    aliases: Sequence[str],
    *,
    template: str,
) -> list[tuple[str, str]]:
    """Assign alias assertion IDs with per-value occurrence ordinals (multiset-safe)."""
    value_occurrence: dict[str, int] = {}
    pairs: list[tuple[str, str]] = []
    for alias_text in aliases:
        occurrence = value_occurrence.get(alias_text, 0)
        value_occurrence[alias_text] = occurrence + 1
        assertion_id = _synthetic_v1_alias_assertion_id(
            object_id,
            occurrence=occurrence,
            alias_text=alias_text,
            template=template,
        )
        pairs.append((alias_text, assertion_id))
    return pairs


def _identity_alias_admitted_from_metadata(
    meta: KnowledgeAssertionMetadataV1 | None,
    *,
    manifest: LegacyCompatibilityManifest,
    coarse: bool,
) -> bool:
    rules = manifest.identity_alias_admission_rules
    if coarse:
        return bool(rules.get("v2_v3_coarse_aliases_enter_identity_aliases", True))
    if meta is None:
        return False
    if (
        bool(rules.get("require_no_campaign_scope", True))
        and meta.campaign_scope is not None
    ):
        return False
    if (
        bool(rules.get("require_player_visibility", True))
        and meta.visibility != Visibility.PLAYER
    ):
        return False
    return not (
        bool(rules.get("require_canonical_standing", True))
        and meta.canon_state != CanonState.CANONICAL
    )


def validate_stored_legacy_graph_revision(
    revision: WorldGraphRevision,
    graph_payload: dict[str, Any],
) -> None:
    """Verify stored envelope and payload identity before compatibility decoding."""
    if revision.schema_version != "dm_graph_revision_v1":
        raise LegacyCompatibilityIntegrityError(
            f"unsupported graph revision schema_version {revision.schema_version!r}",
            details={"schema_version": revision.schema_version},
        )

    if revision.graph_schema not in SUPPORTED_HISTORICAL_SCHEMAS:
        raise LegacyCompatibilityIntegrityError(
            f"unsupported historical graph schema {revision.graph_schema!r}",
            details={"graph_schema": revision.graph_schema},
        )

    if not isinstance(graph_payload, dict):
        raise LegacyCompatibilityIntegrityError(
            "graph_payload must be a JSON object",
            details={"type": type(graph_payload).__name__},
        )

    payload_world_id = graph_payload.get("world_id")
    if payload_world_id != revision.world_id:
        raise LegacyCompatibilityIntegrityError(
            f"payload world_id {payload_world_id!r} does not match revision world_id "
            f"{revision.world_id!r}",
            details={
                "revision_world_id": revision.world_id,
                "payload_world_id": payload_world_id,
            },
        )

    computed_digest = canonical_sha256(graph_payload)
    if computed_digest != revision.graph_payload_sha256:
        raise LegacyCompatibilityIntegrityError(
            f"payload digest mismatch for revision {revision.revision_id}",
            details={
                "expected_sha256": revision.graph_payload_sha256,
                "computed_sha256": computed_digest,
            },
        )

    if not revision.operation_ids:
        raise LegacyCompatibilityIntegrityError(
            f"revision {revision.revision_id} has empty operation_ids",
            details={"revision_id": revision.revision_id},
        )


def _translate_assertion_metadata(
    meta: KnowledgeAssertionMetadataV1 | None,
    *,
    manifest: LegacyCompatibilityManifest,
    default_evidence_ids: Sequence[str],
    graph_schema: str,
    claim_mode: str,
) -> ParsedAssertionMetadata:
    """Translate legacy KnowledgeAssertionMetadataV1 or synthesize coarse metadata."""
    scope_rules = manifest.scope_and_visibility_rules
    campaign_axis = str(scope_rules["campaign_scope_axis"])
    gm_label = str(scope_rules["gm_visibility_label"])
    player_label = str(scope_rules["player_visibility_label"])

    temporal_rules = manifest.temporal_translation_rules
    fictional_time_schema = str(temporal_rules["fictional_time_ref_schema"])
    session_refs_schema = str(temporal_rules["session_refs_schema"])

    epistemic_rules = manifest.epistemic_translation_rules
    epistemic_domain_schema = str(epistemic_rules["domain_metadata_schema"])

    canon_rules = manifest.canon_state_translation_rules
    canon_domain_schema = str(canon_rules["domain_metadata_schema"])

    coarse_rules = manifest.v1_v3_coarse_metadata_rules
    coarse_epistemic_basis = str(coarse_rules["epistemic_basis"])
    coarse_standing = KnowledgeStanding(str(coarse_rules["standing"]))
    coarse_visibility_labels = tuple(str(x) for x in coarse_rules["visibility_labels"])
    coarse_domain_schema = str(coarse_rules["domain_metadata_schema"])

    if meta is not None:
        scope = (
            (ParsedScopeBinding(axis=campaign_axis, value=meta.campaign_scope),)
            if meta.campaign_scope is not None
            else ()
        )

        vis: ParsedVisibility
        if meta.visibility == Visibility.GM:
            vis = ParsedLabelsAnyVisibility(labels=(gm_label,))
        else:
            vis = ParsedLabelsAnyVisibility(labels=(player_label,))

        temp_scope: ParsedTemporalScope
        if meta.temporal_scope.kind == TemporalScopeKind.UNKNOWN:
            temp_scope = ParsedUnknownTemporalScope()
        elif meta.temporal_scope.kind == TemporalScopeKind.WORLD_TIMELESS:
            temp_scope = ParsedTimelessTemporalScope()
        elif meta.temporal_scope.kind == TemporalScopeKind.FICTIONAL_TIME_REF:
            ref = meta.temporal_scope.fictional_time_ref
            if ref is None:
                raise LegacyCompatibilityIntegrityError(
                    "fictional_time_ref temporal scope missing anchor ref"
                )
            temp_scope = ParsedDomainTemporalScope(
                schema_term=fictional_time_schema,
                payload=freeze_json_value({
                    "bundle_id": ref.bundle_id,
                    "campaign_id": ref.campaign_id,
                    "anchor_id": ref.anchor_id,
                }),
            )
        else:
            raise LegacyCompatibilityIntegrityError(
                f"unrecognized legacy temporal scope kind {meta.temporal_scope.kind!r}"
            )

        standing_val = KnowledgeStanding(str(canon_rules[meta.canon_state.value]))

        domain_meta: list[ParsedDomainMetadataEntry] = [
            ParsedDomainMetadataEntry(
                schema_term=epistemic_domain_schema,
                payload=freeze_json_value({"epistemic_kind": meta.epistemic_kind.value}),
            ),
            ParsedDomainMetadataEntry(
                schema_term=canon_domain_schema,
                payload=freeze_json_value({"canon_state": meta.canon_state.value}),
            ),
        ]
        if meta.session_refs:
            domain_meta.append(
                ParsedDomainMetadataEntry(
                    schema_term=session_refs_schema,
                    payload=freeze_json_value({"session_refs": list(meta.session_refs)}),
                )
            )

        return ParsedAssertionMetadata(
            scope=scope,
            visibility=vis,
            epistemic_basis=meta.epistemic_kind.value,
            claim_mode=claim_mode,
            standing=standing_val,
            evidence_ref_ids=tuple(meta.evidence_ref_ids),
            temporal_scope=temp_scope,
            domain_metadata=tuple(domain_meta),
        )

    # v1-v3 coarse semantics: neutral, truth-preserving compatibility metadata
    return ParsedAssertionMetadata(
        scope=(),
        visibility=ParsedLabelsAnyVisibility(labels=coarse_visibility_labels),
        epistemic_basis=coarse_epistemic_basis,
        claim_mode=claim_mode,
        standing=coarse_standing,
        evidence_ref_ids=tuple(default_evidence_ids),
        temporal_scope=ParsedUnknownTemporalScope(),
        domain_metadata=(
            ParsedDomainMetadataEntry(
                schema_term=coarse_domain_schema,
                payload=freeze_json_value({"schema_generation": graph_schema}),
            ),
        ),
    )


def decode_legacy_graph_revision(
    *,
    revision: WorldGraphRevision,
    graph_payload: dict[str, Any],
    profile_registry: SemanticProfileRegistry | None = None,
    manifest: LegacyCompatibilityManifest | None = None,
) -> ParsedKnowledgeRevision:
    """Decode a legacy stored revision into an immutable ParsedKnowledgeRevision."""
    validate_stored_legacy_graph_revision(revision, graph_payload)

    if manifest is None:
        manifest_obj = load_legacy_world_compat_manifest()
    else:
        manifest_obj = verify_legacy_compatibility_manifest(manifest)

    reader = VersionedUnionGraphSnapshotReader(profile_registry=profile_registry)
    try:
        snapshot = reader.parse(
            graph_schema=revision.graph_schema,
            graph_payload=graph_payload,
        )
    except PersistenceIntegrityError as exc:
        raise LegacyCompatibilityIntegrityError(
            f"historical reader failed to parse legacy payload: {exc}",
            details={"revision_id": revision.revision_id, "graph_schema": revision.graph_schema},
        ) from exc

    # Pinned compatibility revision identity
    domain_contract_ref = ParsedDomainContractRef(
        domain_id=manifest_obj.domain_contract_id,
        domain_revision=manifest_obj.domain_contract_revision,
        descriptor_sha256=manifest_obj.manifest_sha256,
    )

    if snapshot.semantic_profile_ref is not None:
        semantic_profile_ref = ParsedSemanticProfileRef(
            profile_id=snapshot.semantic_profile_ref.profile_id,
            profile_revision=snapshot.semantic_profile_ref.profile_revision,
            descriptor_sha256=snapshot.semantic_profile_ref.descriptor_sha256,
        )
    else:
        semantic_profile_ref = ParsedSemanticProfileRef(
            profile_id=manifest_obj.unprofiled_semantic_profile_id,
            profile_revision=manifest_obj.unprofiled_semantic_profile_revision,
            descriptor_sha256=manifest_obj.unprofiled_descriptor_sha256,
        )

    identity = ParsedKnowledgeRevisionIdentity(
        space_id=revision.world_id,
        revision_id=revision.revision_id,
        parent_revision_id=revision.parent_revision_id,
        created_at=revision.created_at,
        operation_ids=tuple(revision.operation_ids),
        graph_schema=revision.graph_schema,
        graph_payload_sha256=revision.graph_payload_sha256,
        domain_contract_ref=domain_contract_ref,
        semantic_profile_ref=semantic_profile_ref,
        migration_origin_ref=None,
    )

    evidence_rules = manifest_obj.evidence_translation_rules
    v1_source_domain_schema = str(evidence_rules["v1_source_domain_schema"])
    v2_extra_schema = str(evidence_rules["v2_extra_schema"])
    rel_aspect_rules = manifest_obj.relationship_aspect_rules
    relationship_domain_schema = str(
        rel_aspect_rules["relationship_domain_metadata_schema"]
    )
    pred_map = manifest_obj.predicate_mappings
    id_templates = manifest_obj.synthetic_assertion_id_templates
    mapping_revision = manifest_obj.compatibility_mapping_revision
    mapping_impl_digest = compute_mapping_implementation_digest(manifest_obj)

    # 1. Translate Evidence Ledger
    evidence_dict: dict[str, ParsedEvidenceRef] = {}
    for ev_id, rec in snapshot.evidence.items():
        ev_role_str = str(getattr(rec.evidence_role, "value", rec.evidence_role))
        domain_meta: list[ParsedDomainMetadataEntry] = []
        if isinstance(rec, GraphEvidenceRecord):
            domain_meta.append(
                ParsedDomainMetadataEntry(
                    schema_term=v1_source_domain_schema,
                    payload=freeze_json_value({"source_domain": rec.source_domain}),
                )
            )
        else:  # EvidenceRefV2
            domain_meta.append(
                ParsedDomainMetadataEntry(
                    schema_term=v2_extra_schema,
                    payload=freeze_json_value({
                        "source_domain_key": rec.source_domain_key,
                        "source_domain": rec.source_domain.value if rec.source_domain else None,
                        "session_id": rec.session_id,
                    }),
                )
            )

        evidence_dict[ev_id] = ParsedEvidenceRef(
            evidence_ref_id=rec.evidence_ref_id,
            source_artifact_id=rec.source_artifact_id,
            source_revision_id=rec.source_revision_id,
            evidence_role=ev_role_str,
            can_open_source=rec.can_open_source,
            can_highlight_span=rec.can_highlight_span,
            locator=rec.locator,
            uri=rec.uri,
            source_locator=getattr(rec, "source_locator", None),
            line_ref=getattr(rec, "line_ref", None),
            source_span_ref_id=getattr(rec, "source_span_ref_id", None),
            domain_metadata=tuple(domain_meta),
        )

    # 2. Translate Entities, Assertions, Aliases
    entities_dict: dict[str, ParsedEntity] = {}
    assertions_dict: dict[str, ParsedAssertion] = {}
    aliases_dict: dict[str, ParsedIdentityAlias] = {}

    for obj_id, obj in snapshot.objects.items():
        entities_dict[obj_id] = ParsedEntity(entity_id=obj_id)

        default_ev_ids = obj.core_evidence_ref_ids or obj.evidence_ref_ids

        existence_predicate = pred_map["existence"]
        kind_predicate = pred_map["kind"]
        label_predicate = pred_map["label"]
        summary_predicate = pred_map["summary"]
        alias_predicate = pred_map["alias"]
        aspect_predicate = pred_map["aspect"]
        existence_claim_mode = existence_predicate
        kind_claim_mode = kind_predicate
        label_claim_mode = label_predicate
        summary_claim_mode = summary_predicate
        alias_claim_mode = alias_predicate
        aspect_claim_mode = aspect_predicate

        # Existence assertion
        if obj.existence_assertion_metadata is not None:
            exist_id = obj.existence_assertion_metadata.assertion_id
            exist_meta = _translate_assertion_metadata(
                obj.existence_assertion_metadata,
                manifest=manifest_obj,
                default_evidence_ids=default_ev_ids,
                graph_schema=snapshot.graph_schema,
                claim_mode=existence_claim_mode,
            )
        else:
            exist_id = id_templates["existence"].replace("{object_id}", obj_id)
            exist_meta = _translate_assertion_metadata(
                None,
                manifest=manifest_obj,
                default_evidence_ids=default_ev_ids,
                graph_schema=snapshot.graph_schema,
                claim_mode=existence_claim_mode,
            )

        if exist_id in assertions_dict:
            raise LegacyCompatibilityIntegrityError(
                f"duplicate assertion ID {exist_id!r}",
                details={"assertion_id": exist_id, "object_id": obj_id},
            )
        assertions_dict[exist_id] = ParsedAssertion(
            assertion_id=exist_id,
            subject_entity_id=obj_id,
            predicate=existence_predicate,
            value=ParsedLiteralValue(
                value=freeze_json_value(True),
                canonical_json_text="true",
            ),
            metadata=exist_meta,
        )

        # Kind assertion
        kind_id = id_templates["kind"].replace("{object_id}", obj_id)
        if kind_id in assertions_dict:
            raise LegacyCompatibilityIntegrityError(
                f"duplicate assertion ID {kind_id!r}",
                details={"assertion_id": kind_id, "object_id": obj_id},
            )
        assertions_dict[kind_id] = ParsedAssertion(
            assertion_id=kind_id,
            subject_entity_id=obj_id,
            predicate=kind_predicate,
            value=ParsedLiteralValue(
                value=freeze_json_value(obj.kind),
                canonical_json_text=canonical_json(obj.kind),
            ),
            metadata=_translate_assertion_metadata(
                obj.existence_assertion_metadata,
                manifest=manifest_obj,
                default_evidence_ids=default_ev_ids,
                graph_schema=snapshot.graph_schema,
                claim_mode=kind_claim_mode,
            ),
        )

        # Label assertion
        label_id = id_templates["label"].replace("{object_id}", obj_id)
        if label_id in assertions_dict:
            raise LegacyCompatibilityIntegrityError(
                f"duplicate assertion ID {label_id!r}",
                details={"assertion_id": label_id, "object_id": obj_id},
            )
        assertions_dict[label_id] = ParsedAssertion(
            assertion_id=label_id,
            subject_entity_id=obj_id,
            predicate=label_predicate,
            value=ParsedLiteralValue(
                value=freeze_json_value(obj.label),
                canonical_json_text=canonical_json(obj.label),
            ),
            metadata=_translate_assertion_metadata(
                obj.existence_assertion_metadata,
                manifest=manifest_obj,
                default_evidence_ids=default_ev_ids,
                graph_schema=snapshot.graph_schema,
                claim_mode=label_claim_mode,
            ),
        )

        # Summary assertion
        if obj.summary is not None:
            if obj.admitted_summary_assertion is not None:
                sum_id = obj.admitted_summary_assertion.assertion_id
                sum_ev_ids = obj.admitted_summary_assertion.evidence_ref_ids
                sum_meta = _translate_assertion_metadata(
                    obj.admitted_summary_assertion.assertion_metadata,
                    manifest=manifest_obj,
                    default_evidence_ids=sum_ev_ids,
                    graph_schema=snapshot.graph_schema,
                    claim_mode=summary_claim_mode,
                )
            else:
                sum_id = id_templates["summary"].replace("{object_id}", obj_id)
                sum_ev_ids = obj.evidence_ref_ids
                sum_meta = _translate_assertion_metadata(
                    None,
                    manifest=manifest_obj,
                    default_evidence_ids=sum_ev_ids,
                    graph_schema=snapshot.graph_schema,
                    claim_mode=summary_claim_mode,
                )

            if sum_id in assertions_dict:
                raise LegacyCompatibilityIntegrityError(
                    f"duplicate assertion ID {sum_id!r}",
                    details={"assertion_id": sum_id, "object_id": obj_id},
                )
            assertions_dict[sum_id] = ParsedAssertion(
                assertion_id=sum_id,
                subject_entity_id=obj_id,
                predicate=summary_predicate,
                value=ParsedLiteralValue(
                    value=freeze_json_value(obj.summary),
                    canonical_json_text=canonical_json(obj.summary),
                ),
                metadata=sum_meta,
            )

        # Alias assertions and safe identity aliases
        if obj.admitted_alias_assertions:
            for al in obj.admitted_alias_assertions:
                if al.assertion_id in assertions_dict:
                    raise LegacyCompatibilityIntegrityError(
                        f"duplicate assertion ID {al.assertion_id!r}",
                        details={"assertion_id": al.assertion_id, "object_id": obj_id},
                    )
                al_meta = _translate_assertion_metadata(
                    al.assertion_metadata,
                    manifest=manifest_obj,
                    default_evidence_ids=al.evidence_ref_ids,
                    graph_schema=snapshot.graph_schema,
                    claim_mode=alias_claim_mode,
                )
                assertions_dict[al.assertion_id] = ParsedAssertion(
                    assertion_id=al.assertion_id,
                    subject_entity_id=obj_id,
                    predicate=alias_predicate,
                    value=ParsedLiteralValue(
                        value=freeze_json_value(al.alias),
                        canonical_json_text=canonical_json(al.alias),
                    ),
                    metadata=al_meta,
                )

                if _identity_alias_admitted_from_metadata(
                    al.assertion_metadata,
                    manifest=manifest_obj,
                    coarse=al.assertion_metadata is None,
                ):
                    aliases_dict[al.assertion_id] = ParsedIdentityAlias(
                        alias_id=al.assertion_id,
                        entity_id=obj_id,
                        alias_text=al.alias,
                        evidence_ref_ids=tuple(al.evidence_ref_ids),
                        standing=KnowledgeStanding.ESTABLISHED,
                    )
        else:
            # v1 plain aliases — value-group occurrence + full sha256 (multiset-safe)
            alias_template = id_templates["alias"]
            v1_alias_pairs = _v1_alias_assertion_ids(
                obj_id,
                obj.aliases,
                template=alias_template,
            )
            v1_enter_identity = bool(
                manifest_obj.identity_alias_admission_rules.get(
                    "v1_plain_aliases_enter_identity_aliases",
                    True,
                )
            )
            for alias_text, al_id in v1_alias_pairs:
                if al_id in assertions_dict:
                    raise LegacyCompatibilityIntegrityError(
                        f"duplicate alias assertion ID {al_id!r}",
                        details={"assertion_id": al_id, "object_id": obj_id},
                    )
                al_meta = _translate_assertion_metadata(
                    None,
                    manifest=manifest_obj,
                    default_evidence_ids=obj.evidence_ref_ids,
                    graph_schema=snapshot.graph_schema,
                    claim_mode=alias_claim_mode,
                )
                assertions_dict[al_id] = ParsedAssertion(
                    assertion_id=al_id,
                    subject_entity_id=obj_id,
                    predicate=alias_predicate,
                    value=ParsedLiteralValue(
                        value=freeze_json_value(alias_text),
                        canonical_json_text=canonical_json(alias_text),
                    ),
                    metadata=al_meta,
                )
                if v1_enter_identity:
                    aliases_dict[al_id] = ParsedIdentityAlias(
                        alias_id=al_id,
                        entity_id=obj_id,
                        alias_text=alias_text,
                        evidence_ref_ids=tuple(obj.evidence_ref_ids),
                        standing=KnowledgeStanding.ESTABLISHED,
                    )

        # Property assertions (v4-v6)
        for prop in obj.admitted_property_assertions:
            if prop.assertion_id in assertions_dict:
                raise LegacyCompatibilityIntegrityError(
                    f"duplicate property assertion ID {prop.assertion_id!r}",
                    details={"assertion_id": prop.assertion_id, "object_id": obj_id},
                )
            prop_meta = _translate_assertion_metadata(
                prop.assertion_metadata,
                manifest=manifest_obj,
                default_evidence_ids=prop.evidence_ref_ids,
                graph_schema=snapshot.graph_schema,
                claim_mode="dungeonmind.compat:property",
            )
            assertions_dict[prop.assertion_id] = ParsedAssertion(
                assertion_id=prop.assertion_id,
                subject_entity_id=obj_id,
                predicate=prop.property_term,
                value=ParsedLiteralValue(
                    value=freeze_json_value(prop.value),
                    canonical_json_text=canonical_json(prop.value),
                ),
                metadata=prop_meta,
            )

        # Aspect assertions (v6)
        for aspect in obj.admitted_aspect_assertions:
            if aspect.assertion_id in assertions_dict:
                raise LegacyCompatibilityIntegrityError(
                    f"duplicate aspect assertion ID {aspect.assertion_id!r}",
                    details={"assertion_id": aspect.assertion_id, "object_id": obj_id},
                )
            aspect_meta = _translate_assertion_metadata(
                aspect.assertion_metadata,
                manifest=manifest_obj,
                default_evidence_ids=aspect.evidence_ref_ids,
                graph_schema=snapshot.graph_schema,
                claim_mode=aspect_claim_mode,
            )
            aspect_val = {"aspect_key": aspect.aspect_key, "kind": aspect.kind}
            assertions_dict[aspect.assertion_id] = ParsedAssertion(
                assertion_id=aspect.assertion_id,
                subject_entity_id=obj_id,
                predicate=aspect_predicate,
                value=ParsedLiteralValue(
                    value=freeze_json_value(aspect_val),
                    canonical_json_text=canonical_json(aspect_val),
                ),
                metadata=aspect_meta,
            )

    # 3. Translate Relationships
    for rel_id, rel in snapshot.relationships.items():
        if rel.subject_object_id not in entities_dict:
            raise LegacyCompatibilityIntegrityError(
                f"relationship {rel_id} references missing subject entity {rel.subject_object_id}",
                details={"relationship_id": rel_id, "subject_entity_id": rel.subject_object_id},
            )
        if rel.object_object_id not in entities_dict:
            raise LegacyCompatibilityIntegrityError(
                f"relationship {rel_id} references missing object entity {rel.object_object_id}",
                details={"relationship_id": rel_id, "object_entity_id": rel.object_object_id},
            )

        # Verify v6 endpoint aspect integrity
        if rel.source_aspect_assertion_id:
            src_obj = snapshot.objects[rel.subject_object_id]
            if not any(
                a.assertion_id == rel.source_aspect_assertion_id
                for a in src_obj.admitted_aspect_assertions
            ):
                raise LegacyCompatibilityIntegrityError(
                    f"relationship {rel_id} source aspect {rel.source_aspect_assertion_id} "
                    f"is not admitted on {rel.subject_object_id}",
                    details={
                        "relationship_id": rel_id,
                        "source_aspect_assertion_id": rel.source_aspect_assertion_id,
                    },
                )
        if rel.target_aspect_assertion_id:
            tgt_obj = snapshot.objects[rel.object_object_id]
            if not any(
                a.assertion_id == rel.target_aspect_assertion_id
                for a in tgt_obj.admitted_aspect_assertions
            ):
                raise LegacyCompatibilityIntegrityError(
                    f"relationship {rel_id} target aspect {rel.target_aspect_assertion_id} "
                    f"is not admitted on {rel.object_object_id}",
                    details={
                        "relationship_id": rel_id,
                        "target_aspect_assertion_id": rel.target_aspect_assertion_id,
                    },
                )

        rel_asrt_id = (
            rel.assertion_metadata.assertion_id
            if rel.assertion_metadata is not None
            else id_templates["relationship"].replace("{relationship_id}", rel_id)
        )

        if rel_asrt_id in assertions_dict:
            raise LegacyCompatibilityIntegrityError(
                f"duplicate relationship assertion ID {rel_asrt_id!r}",
                details={"assertion_id": rel_asrt_id, "relationship_id": rel_id},
            )

        base_meta = _translate_assertion_metadata(
            rel.assertion_metadata,
            manifest=manifest_obj,
            default_evidence_ids=rel.evidence_ref_ids,
            graph_schema=snapshot.graph_schema,
            claim_mode="dungeonmind.compat:relationship",
        )

        # Record relationship metadata for lossless reconstruction
        rel_extra_entry = ParsedDomainMetadataEntry(
            schema_term=relationship_domain_schema,
            payload=freeze_json_value({
                "relationship_id": rel_id,
                "source_aspect_assertion_id": rel.source_aspect_assertion_id,
                "target_aspect_assertion_id": rel.target_aspect_assertion_id,
            }),
        )
        combined_meta = ParsedAssertionMetadata(
            scope=base_meta.scope,
            visibility=base_meta.visibility,
            epistemic_basis=base_meta.epistemic_basis,
            claim_mode=base_meta.claim_mode,
            standing=base_meta.standing,
            evidence_ref_ids=base_meta.evidence_ref_ids,
            temporal_scope=base_meta.temporal_scope,
            domain_metadata=(*base_meta.domain_metadata, rel_extra_entry),
        )

        assertions_dict[rel_asrt_id] = ParsedAssertion(
            assertion_id=rel_asrt_id,
            subject_entity_id=rel.subject_object_id,
            predicate=rel.predicate,
            value=ParsedEntityRefValue(entity_id=rel.object_object_id),
            metadata=combined_meta,
        )

    parsed = build_parsed_knowledge_revision_from_records(
        identity=identity,
        entities=entities_dict,
        assertions=assertions_dict,
        aliases=aliases_dict,
        evidence=evidence_dict,
    )
    legacy_key = compute_legacy_compatibility_key(
        mapping_revision=mapping_revision,
        mapping_manifest_sha256=manifest_obj.manifest_sha256,
        mapping_implementation_digest=mapping_impl_digest,
        graph_schema=revision.graph_schema,
        historical_parse_compatibility_id=reader.parse_compatibility_id,
        semantic_profile_ref=semantic_profile_ref,
        parsed_format_version=PARSED_REVISION_FORMAT_VERSION,
        legacy_payload_sha256=revision.graph_payload_sha256,
    )
    return replace(parsed, compatibility_key=legacy_key)


def decode_legacy_stored_graph_revision(
    stored_revision: StoredGraphRevision,
    *,
    profile_registry: SemanticProfileRegistry | None = None,
    manifest: LegacyCompatibilityManifest | None = None,
) -> ParsedKnowledgeRevision:
    """Decode a StoredGraphRevision through the historical compatibility decoder."""
    return decode_legacy_graph_revision(
        revision=stored_revision.revision,
        graph_payload=stored_revision.graph_payload,
        profile_registry=profile_registry,
        manifest=manifest,
    )


# --- Canonical Semantic Witness Generators (§8) ---

def _serialize_witness_metadata(
    meta: KnowledgeAssertionMetadataV1 | None,
) -> dict[str, Any] | None:
    if meta is None:
        return None

    temp_dict: dict[str, Any]
    if meta.temporal_scope.kind == TemporalScopeKind.UNKNOWN:
        temp_dict = {"kind": "unknown"}
    elif meta.temporal_scope.kind == TemporalScopeKind.WORLD_TIMELESS:
        temp_dict = {"kind": "world_timeless"}
    elif meta.temporal_scope.kind == TemporalScopeKind.FICTIONAL_TIME_REF:
        ref = meta.temporal_scope.fictional_time_ref
        temp_dict = {
            "anchor_id": ref.anchor_id if ref else None,
            "bundle_id": ref.bundle_id if ref else None,
            "campaign_id": ref.campaign_id if ref else None,
            "kind": "fictional_time_ref",
        }
    else:
        temp_dict = {"kind": meta.temporal_scope.kind.value}

    c_state = meta.canon_state
    c_state_str = c_state.value if hasattr(c_state, "value") else str(c_state)
    e_kind = meta.epistemic_kind
    e_kind_str = e_kind.value if hasattr(e_kind, "value") else str(e_kind)
    vis = meta.visibility
    vis_str = vis.value if hasattr(vis, "value") else str(vis)

    return {
        "campaign_scope": meta.campaign_scope,
        "canon_state": c_state_str,
        "epistemic_kind": e_kind_str,
        "evidence_ref_ids": sorted(meta.evidence_ref_ids),
        "session_refs": sorted(meta.session_refs),
        "temporal_scope": temp_dict,
        "visibility": vis_str,
    }


def _reconstruct_witness_metadata_from_parsed(
    meta: ParsedAssertionMetadata,
) -> dict[str, Any] | None:
    if meta.epistemic_basis == "dungeonmind.compat:legacy_unspecified":
        return None

    campaign_scope: str | None = None
    for b in meta.scope:
        if b.axis == "dungeonmind.compat:campaign":
            campaign_scope = b.value
            break

    # Visibility
    vis_str = "player"
    if (
        isinstance(meta.visibility, ParsedLabelsAnyVisibility)
        and "audience:gm" in meta.visibility.labels
    ):
        vis_str = "gm"

    # Epistemic kind
    epistemic_kind = meta.epistemic_basis
    for dm in meta.domain_metadata:
        if dm.schema_term == "dungeonmind.compat:legacy_epistemic_kind":
            thawed = thaw_json_value(dm.payload)
            if isinstance(thawed, dict) and "epistemic_kind" in thawed:
                epistemic_kind = thawed["epistemic_kind"]

    # Canon state
    canon_state = (
        "canonical"
        if meta.standing == "established"
        else "provisional"
        if meta.standing == "provisional"
        else "retracted"
    )
    for dm in meta.domain_metadata:
        if dm.schema_term == "dungeonmind.compat:legacy_canon_state":
            thawed = thaw_json_value(dm.payload)
            if isinstance(thawed, dict) and "canon_state" in thawed:
                canon_state = thawed["canon_state"]

    # Session refs
    session_refs: list[str] = []
    for dm in meta.domain_metadata:
        if dm.schema_term == "dungeonmind.compat:session_refs":
            thawed = thaw_json_value(dm.payload)
            if isinstance(thawed, dict) and "session_refs" in thawed:
                session_refs = list(thawed["session_refs"])

    # Temporal scope
    temp_dict: dict[str, Any]
    if isinstance(meta.temporal_scope, ParsedUnknownTemporalScope):
        temp_dict = {"kind": "unknown"}
    elif isinstance(meta.temporal_scope, ParsedTimelessTemporalScope):
        temp_dict = {"kind": "world_timeless"}
    elif isinstance(meta.temporal_scope, ParsedDomainTemporalScope):
        thawed_t = thaw_json_value(meta.temporal_scope.payload)
        temp_dict = {
            "anchor_id": thawed_t.get("anchor_id"),
            "bundle_id": thawed_t.get("bundle_id"),
            "campaign_id": thawed_t.get("campaign_id"),
            "kind": "fictional_time_ref",
        }
    else:
        temp_dict = {"kind": meta.temporal_scope.kind}

    return {
        "campaign_scope": campaign_scope,
        "canon_state": canon_state,
        "epistemic_kind": epistemic_kind,
        "evidence_ref_ids": sorted(meta.evidence_ref_ids),
        "session_refs": sorted(session_refs),
        "temporal_scope": temp_dict,
        "visibility": vis_str,
    }


def build_historical_semantic_witness(snapshot: ParsedGraphSnapshot) -> dict[str, Any]:
    """Extract canonical semantic witness directly from historical ParsedGraphSnapshot."""
    manifest = load_legacy_world_compat_manifest()
    id_templates = manifest.synthetic_assertion_id_templates

    # Semantic profile
    prof_dict = None
    if snapshot.semantic_profile_ref is not None:
        prof_dict = {
            "descriptor_sha256": snapshot.semantic_profile_ref.descriptor_sha256,
            "profile_id": snapshot.semantic_profile_ref.profile_id,
            "profile_revision": snapshot.semantic_profile_ref.profile_revision,
        }

    # Objects
    witness_objects = []
    for obj_id in sorted(snapshot.objects.keys()):
        obj = snapshot.objects[obj_id]

        # Existence
        if obj.existence_assertion_metadata is not None:
            exist_id = obj.existence_assertion_metadata.assertion_id
            exist_meta = _serialize_witness_metadata(obj.existence_assertion_metadata)
        else:
            exist_id = id_templates["existence"].replace("{object_id}", obj_id)
            exist_meta = None

        # Summary
        sum_dict = None
        if obj.summary is not None:
            if obj.admitted_summary_assertion is not None:
                sum_meta = _serialize_witness_metadata(
                    obj.admitted_summary_assertion.assertion_metadata
                )
                sum_dict = {
                    "assertion_id": obj.admitted_summary_assertion.assertion_id,
                    "evidence_ref_ids": sorted(obj.admitted_summary_assertion.evidence_ref_ids),
                    "metadata": sum_meta,
                    "summary": obj.summary,
                }
            else:
                sum_dict = {
                    "assertion_id": id_templates["summary"].replace("{object_id}", obj_id),
                    "evidence_ref_ids": sorted(obj.evidence_ref_ids),
                    "metadata": None,
                    "summary": obj.summary,
                }

        # Aliases
        alias_list = []
        if obj.admitted_alias_assertions:
            for al in sorted(obj.admitted_alias_assertions, key=lambda x: x.assertion_id):
                alias_list.append({
                    "alias": al.alias,
                    "assertion_id": al.assertion_id,
                    "evidence_ref_ids": sorted(al.evidence_ref_ids),
                    "metadata": _serialize_witness_metadata(al.assertion_metadata),
                })
        else:
            alias_template = id_templates["alias"]
            for al_text, syn_al_id in _v1_alias_assertion_ids(
                obj_id,
                obj.aliases,
                template=alias_template,
            ):
                alias_list.append({
                    "alias": al_text,
                    "assertion_id": syn_al_id,
                    "evidence_ref_ids": sorted(obj.evidence_ref_ids),
                    "metadata": None,
                })
            alias_list.sort(key=lambda item: item["assertion_id"])

        # Properties
        prop_list = []
        for prop in sorted(obj.admitted_property_assertions, key=lambda x: x.assertion_id):
            prop_list.append({
                "assertion_id": prop.assertion_id,
                "evidence_ref_ids": sorted(prop.evidence_ref_ids),
                "metadata": _serialize_witness_metadata(prop.assertion_metadata),
                "property_term": prop.property_term,
                "value": prop.value,
            })

        # Aspects
        aspect_list = []
        for aspect in sorted(obj.admitted_aspect_assertions, key=lambda x: x.assertion_id):
            aspect_list.append({
                "aspect_key": aspect.aspect_key,
                "assertion_id": aspect.assertion_id,
                "evidence_ref_ids": sorted(aspect.evidence_ref_ids),
                "kind": aspect.kind,
                "metadata": _serialize_witness_metadata(aspect.assertion_metadata),
            })

        witness_objects.append({
            "alias_assertions": alias_list,
            "aspect_assertions": aspect_list,
            "existence_assertion": {
                "assertion_id": exist_id,
                "metadata": exist_meta,
            },
            "kind": obj.kind,
            "label": obj.label,
            "object_id": obj_id,
            "property_assertions": prop_list,
            "summary_assertion": sum_dict,
        })

    # Relationships
    witness_relationships = []
    for rel_id in sorted(snapshot.relationships.keys()):
        rel = snapshot.relationships[rel_id]
        asrt_id = (
            rel.assertion_metadata.assertion_id
            if rel.assertion_metadata is not None
            else id_templates["relationship"].replace("{relationship_id}", rel_id)
        )
        eff_src = effective_endpoint_kind(rel, endpoint="source", snapshot=snapshot)
        eff_tgt = effective_endpoint_kind(rel, endpoint="target", snapshot=snapshot)
        witness_relationships.append({
            "assertion_id": asrt_id,
            "effective_source_kind": eff_src,
            "effective_target_kind": eff_tgt,
            "evidence_ref_ids": sorted(rel.evidence_ref_ids),
            "metadata": _serialize_witness_metadata(rel.assertion_metadata),
            "object_object_id": rel.object_object_id,
            "predicate": rel.predicate,
            "relationship_id": rel.relationship_id,
            "source_aspect_assertion_id": rel.source_aspect_assertion_id,
            "subject_object_id": rel.subject_object_id,
            "target_aspect_assertion_id": rel.target_aspect_assertion_id,
        })

    # Evidence
    witness_evidence = []
    for ev_id in sorted(snapshot.evidence.keys()):
        ev = snapshot.evidence[ev_id]
        ev_role_str = str(getattr(ev.evidence_role, "value", ev.evidence_role))
        src_domain = None
        sd = getattr(ev, "source_domain", None)
        if sd is not None:
            src_domain = str(getattr(sd, "value", sd))
        witness_evidence.append({
            "can_highlight_span": ev.can_highlight_span,
            "can_open_source": ev.can_open_source,
            "evidence_ref_id": ev.evidence_ref_id,
            "evidence_role": ev_role_str,
            "line_ref": getattr(ev, "line_ref", None),
            "locator": ev.locator,
            "session_id": getattr(ev, "session_id", None),
            "source_artifact_id": ev.source_artifact_id,
            "source_domain": src_domain,
            "source_locator": getattr(ev, "source_locator", None),
            "source_revision_id": ev.source_revision_id,
            "source_span_ref_id": getattr(ev, "source_span_ref_id", None),
            "uri": ev.uri,
        })

    return {
        "evidence": witness_evidence,
        "graph_schema": snapshot.graph_schema,
        "objects": witness_objects,
        "relationships": witness_relationships,
        "semantic_profile": prof_dict,
        "world_id": snapshot.world_id,
    }


def build_parsed_revision_semantic_witness(
    parsed: ParsedKnowledgeRevision,
) -> dict[str, Any]:
    """Reconstruct canonical semantic witness from compatibility-normalized revision."""
    # Semantic profile
    prof_dict = None
    if parsed.semantic_profile_ref.profile_id != UNPROFILED_SEMANTIC_PROFILE_ID:
        prof_dict = {
            "descriptor_sha256": parsed.semantic_profile_ref.descriptor_sha256,
            "profile_id": parsed.semantic_profile_ref.profile_id,
            "profile_revision": parsed.semantic_profile_ref.profile_revision,
        }

    # Group assertions by subject and predicate/role
    objects_dict: dict[str, dict[str, Any]] = {}
    relationship_assertions: list[ParsedAssertion] = []

    for ent_id in sorted(parsed.entities_by_id.keys()):
        objects_dict[ent_id] = {
            "alias_assertions": [],
            "aspect_assertions": [],
            "existence_assertion": None,
            "kind": "",
            "label": "",
            "object_id": ent_id,
            "property_assertions": [],
            "summary_assertion": None,
        }

    for asrt_id in sorted(parsed.assertions_by_id.keys()):
        asrt = parsed.assertions_by_id[asrt_id]
        subj = asrt.subject_entity_id

        if isinstance(asrt.value, ParsedEntityRefValue):
            relationship_assertions.append(asrt)
            continue

        obj_record = objects_dict.get(subj)
        if obj_record is None:
            continue

        pred = asrt.predicate
        if isinstance(asrt.value, ParsedLiteralValue):
            val_payload = thaw_json_value(asrt.value.value)
        else:
            val_payload = None

        if pred == "dungeonmind.compat:existence":
            obj_record["existence_assertion"] = {
                "assertion_id": asrt.assertion_id,
                "metadata": _reconstruct_witness_metadata_from_parsed(asrt.metadata),
            }
        elif pred == "dungeonmind.compat:kind":
            obj_record["kind"] = val_payload or ""
        elif pred == "dungeonmind.compat:label":
            obj_record["label"] = val_payload or ""
        elif pred == "dungeonmind.compat:summary":
            obj_record["summary_assertion"] = {
                "assertion_id": asrt.assertion_id,
                "evidence_ref_ids": sorted(asrt.metadata.evidence_ref_ids),
                "metadata": _reconstruct_witness_metadata_from_parsed(asrt.metadata),
                "summary": val_payload,
            }
        elif pred == "dungeonmind.compat:alias":
            obj_record["alias_assertions"].append({
                "alias": val_payload,
                "assertion_id": asrt.assertion_id,
                "evidence_ref_ids": sorted(asrt.metadata.evidence_ref_ids),
                "metadata": _reconstruct_witness_metadata_from_parsed(asrt.metadata),
            })
        elif pred == "dungeonmind.compat:aspect":
            aspect_dict = val_payload if isinstance(val_payload, dict) else {}
            obj_record["aspect_assertions"].append({
                "aspect_key": aspect_dict.get("aspect_key", ""),
                "assertion_id": asrt.assertion_id,
                "evidence_ref_ids": sorted(asrt.metadata.evidence_ref_ids),
                "kind": aspect_dict.get("kind", ""),
                "metadata": _reconstruct_witness_metadata_from_parsed(asrt.metadata),
            })
        else:  # Custom property assertion
            obj_record["property_assertions"].append({
                "assertion_id": asrt.assertion_id,
                "evidence_ref_ids": sorted(asrt.metadata.evidence_ref_ids),
                "metadata": _reconstruct_witness_metadata_from_parsed(asrt.metadata),
                "property_term": pred,
                "value": val_payload,
            })

    # Sort inner assertion collections
    witness_objects = []
    for ent_id in sorted(objects_dict.keys()):
        rec = objects_dict[ent_id]
        rec["alias_assertions"].sort(key=lambda x: x["assertion_id"])
        rec["aspect_assertions"].sort(key=lambda x: x["assertion_id"])
        rec["property_assertions"].sort(key=lambda x: x["assertion_id"])
        witness_objects.append(rec)

    # Reconstruct Relationships
    witness_relationships = []
    for asrt in relationship_assertions:
        rel_id = asrt.assertion_id
        src_aspect_id = None
        tgt_aspect_id = None
        for dm in asrt.metadata.domain_metadata:
            if dm.schema_term == "dungeonmind.compat:relationship":
                thawed_r = thaw_json_value(dm.payload)
                if isinstance(thawed_r, dict):
                    rel_id = thawed_r.get("relationship_id", rel_id)
                    src_aspect_id = thawed_r.get("source_aspect_assertion_id")
                    tgt_aspect_id = thawed_r.get("target_aspect_assertion_id")

        subj_obj_id = asrt.subject_entity_id
        if isinstance(asrt.value, ParsedEntityRefValue):
            target_entity_id = asrt.value.entity_id
        else:
            target_entity_id = ""

        # Compute effective endpoint kinds
        eff_src = objects_dict[subj_obj_id]["kind"]
        if src_aspect_id:
            for asp in objects_dict[subj_obj_id]["aspect_assertions"]:
                if asp["assertion_id"] == src_aspect_id:
                    eff_src = asp["kind"]
                    break

        eff_tgt = objects_dict[target_entity_id]["kind"]
        if tgt_aspect_id:
            for asp in objects_dict[target_entity_id]["aspect_assertions"]:
                if asp["assertion_id"] == tgt_aspect_id:
                    eff_tgt = asp["kind"]
                    break

        witness_relationships.append({
            "assertion_id": asrt.assertion_id,
            "effective_source_kind": eff_src,
            "effective_target_kind": eff_tgt,
            "evidence_ref_ids": sorted(asrt.metadata.evidence_ref_ids),
            "metadata": _reconstruct_witness_metadata_from_parsed(asrt.metadata),
            "object_object_id": target_entity_id,
            "predicate": asrt.predicate,
            "relationship_id": rel_id,
            "source_aspect_assertion_id": src_aspect_id,
            "subject_object_id": subj_obj_id,
            "target_aspect_assertion_id": tgt_aspect_id,
        })

    witness_relationships.sort(key=lambda x: x["relationship_id"])

    # Reconstruct Evidence
    witness_evidence = []
    for ev_id in sorted(parsed.evidence_by_id.keys()):
        ev = parsed.evidence_by_id[ev_id]
        src_domain = None
        session_id = None
        for dm in ev.domain_metadata:
            if dm.schema_term == "dungeonmind.compat:evidence_source_domain":
                thawed_d = thaw_json_value(dm.payload)
                if isinstance(thawed_d, dict):
                    src_domain = thawed_d.get("source_domain")
            elif dm.schema_term == "dungeonmind.compat:evidence_v2_extra":
                thawed_d = thaw_json_value(dm.payload)
                if isinstance(thawed_d, dict):
                    src_domain = thawed_d.get("source_domain")
                    session_id = thawed_d.get("session_id")

        witness_evidence.append({
            "can_highlight_span": ev.can_highlight_span,
            "can_open_source": ev.can_open_source,
            "evidence_ref_id": ev.evidence_ref_id,
            "evidence_role": ev.evidence_role,
            "line_ref": ev.line_ref,
            "locator": ev.locator,
            "session_id": session_id,
            "source_artifact_id": ev.source_artifact_id,
            "source_domain": src_domain,
            "source_locator": ev.source_locator,
            "source_revision_id": ev.source_revision_id,
            "source_span_ref_id": ev.source_span_ref_id,
            "uri": ev.uri,
        })

    return {
        "evidence": witness_evidence,
        "graph_schema": parsed.graph_schema,
        "objects": witness_objects,
        "relationships": witness_relationships,
        "semantic_profile": prof_dict,
        "world_id": parsed.space_id,
    }


def verify_historical_semantic_parity(
    snapshot: ParsedGraphSnapshot,
    parsed: ParsedKnowledgeRevision,
) -> tuple[bool, str, str]:
    """Verify exact canonical semantic parity between historical snapshot and parsed revision."""
    hist_witness = build_historical_semantic_witness(snapshot)
    parsed_witness = build_parsed_revision_semantic_witness(parsed)

    hist_sha = canonical_sha256(hist_witness)
    parsed_sha = canonical_sha256(parsed_witness)

    return hist_sha == parsed_sha, hist_sha, parsed_sha
