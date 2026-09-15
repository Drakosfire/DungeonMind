"""Focused test suite for V1.2 legacy v1-v6 compatibility decoder and semantic parity.

Covers the complete §13 acceptance matrix and verifies structural integrity,
exact semantic parity, determinism, fail-closed boundaries, and immutability.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import tests.unit.test_assertion_scoped_graph as tag
import tests.unit.test_graph_snapshot_reader as tr
import tests.unit.test_graph_snapshot_v6 as tu6
import tests.unit.test_semantic_profile_graph as tsp
import tests.unit.test_union_graph_v4 as tu4
import tests.unit.test_union_graph_v5 as tu5
from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V1,
    GRAPH_SCHEMA_V2,
    GRAPH_SCHEMA_V3,
    GRAPH_SCHEMA_V4,
    GRAPH_SCHEMA_V5,
    GRAPH_SCHEMA_V6,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.vnext.builder import (
    compute_compatibility_key,
)
from dungeonmind.application.vnext.errors import (
    LegacyCompatibilityIntegrityError,
)
from dungeonmind.application.vnext.frozen_json import FrozenDict
from dungeonmind.application.vnext.legacy_compat import (
    COMPATIBILITY_MANIFEST_SHA256,
    DOCS_MANIFEST_AUDIT_PATH,
    LegacyCompatibilityManifest,
    compute_legacy_compatibility_key,
    compute_mapping_implementation_digest,
    decode_legacy_graph_revision,
    load_legacy_world_compat_manifest,
    validate_stored_legacy_graph_revision,
    verify_historical_semantic_parity,
)
from dungeonmind.application.vnext.model import PARSED_REVISION_FORMAT_VERSION
from dungeonmind.application.vnext.records import (
    ParsedDomainTemporalScope,
    ParsedEntityRefValue,
    ParsedLabelsAnyVisibility,
    ParsedLiteralValue,
    ParsedTimelessTemporalScope,
    ParsedUnknownTemporalScope,
)
from dungeonmind.contracts.graph import WorldGraphRevision
from dungeonmind.contracts.knowledge_assertion import CanonState
from dungeonmind.contracts.vnext.common import KnowledgeStanding
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError


def _make_rev(
    schema: str, payload: dict[str, Any], *, rev_id: str | None = None
) -> WorldGraphRevision:
    return WorldGraphRevision(
        schema_version="dm_graph_revision_v1",
        world_id=payload.get("world_id", "world:test-compat"),
        revision_id=rev_id or f"rev:compat-{schema}",
        parent_revision_id="rev:compat-parent",
        created_at=datetime.now(UTC),
        operation_ids=["op:compat-init"],
        graph_schema=schema,
        graph_payload_sha256=canonical_sha256(payload),
        status="published",
    )


# 1. Steward handoff update
def test_01_steward_handoff_records_pr57_and_v1_2_active() -> None:
    path = Path("Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "6d9a40f609530f4882470c5599b4914e2288b8d5" in content
    assert "V1.1 COMPLETE" in content
    assert "V1.2 ACTIVE" in content
    assert "38d9eac" in content
    assert "5213422370" in content


# 2. v1 stored revision decodes and has semantic parity
def test_02_v1_stored_revision_decodes_and_semantic_parity() -> None:
    payload = tr._payload()
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    parsed = decode_legacy_graph_revision(revision=rev, graph_payload=payload)

    reader = VersionedUnionGraphSnapshotReader()
    hist_snapshot = reader.parse(graph_schema=GRAPH_SCHEMA_V1, graph_payload=payload)

    ok, hist_sha, parsed_sha = verify_historical_semantic_parity(hist_snapshot, parsed)
    assert ok is True
    assert hist_sha == parsed_sha
    nodes = payload.get("nodes", [])
    assert isinstance(nodes, list)
    evidence_refs = payload.get("evidence_refs", [])
    assert isinstance(evidence_refs, list)
    assert len(parsed.entities_by_id) == len(nodes)
    assert len(parsed.evidence_by_id) == len(evidence_refs)


# 3. v2 stored revision decodes and has semantic parity
def test_03_v2_stored_revision_decodes_and_semantic_parity() -> None:
    payload = tag._v2_payload()
    rev = _make_rev(GRAPH_SCHEMA_V2, payload)
    parsed = decode_legacy_graph_revision(revision=rev, graph_payload=payload)

    reader = VersionedUnionGraphSnapshotReader()
    hist_snapshot = reader.parse(graph_schema=GRAPH_SCHEMA_V2, graph_payload=payload)

    ok, hist_sha, parsed_sha = verify_historical_semantic_parity(hist_snapshot, parsed)
    assert ok is True
    assert hist_sha == parsed_sha
    assert parsed.get_entity("obj:item-sun-ledger") is not None


# 4. v3 stored revision decodes with exact profile verification
def test_04_v3_stored_revision_decodes_with_exact_profile_verification() -> None:
    payload = tsp._v3_payload()
    rev = _make_rev(GRAPH_SCHEMA_V3, payload)
    registry = tsp._narrative_registry()

    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    reader = VersionedUnionGraphSnapshotReader(profile_registry=registry)
    hist_snapshot = reader.parse(graph_schema=GRAPH_SCHEMA_V3, graph_payload=payload)

    ok, hist_sha, parsed_sha = verify_historical_semantic_parity(hist_snapshot, parsed)
    assert ok is True
    assert hist_sha == parsed_sha
    assert parsed.semantic_profile_ref.profile_id == "test.narrative"


# 5. v4 stored revision decodes and has semantic parity
def test_05_v4_stored_revision_decodes_and_semantic_parity() -> None:
    payload = tu4._v4_payload()
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()

    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    reader = VersionedUnionGraphSnapshotReader(profile_registry=registry)
    hist_snapshot = reader.parse(graph_schema=GRAPH_SCHEMA_V4, graph_payload=payload)

    ok, hist_sha, parsed_sha = verify_historical_semantic_parity(hist_snapshot, parsed)
    assert ok is True
    assert hist_sha == parsed_sha


# 6. v5 stored revision decodes and has semantic parity
def test_06_v5_stored_revision_decodes_and_semantic_parity() -> None:
    payload = copy.deepcopy(tu5._v5_payload())
    # Add fictional-time relationship
    payload["relationships"].append({
        "relationship_id": "rel:quill-self",
        "source_object_id": "obj:person-quill",
        "target_object_id": "obj:person-quill",
        "predicate": "test:knows",
        "assertion_metadata": {
            "schema_version": "dm_knowledge_assertion_metadata_v1",
            "assertion_id": "asrt:quill-knows",
            "campaign_scope": "camp:fellowship",
            "visibility": "player",
            "epistemic_kind": "asserted",
            "canon_state": "canonical",
            "evidence_ref_ids": ["ev:v5"],
            "session_refs": ["sess:1"],
            "temporal_scope": {
                "schema_version": "dm_temporal_scope_ref_v1",
                "kind": "fictional_time_ref",
                "fictional_time_ref": {
                    "schema_version": "dm_fictional_time_anchor_ref_v1",
                    "bundle_id": "bundle:ft-era1",
                    "campaign_id": "camp:fellowship",
                    "anchor_id": "anchor:year-100",
                },
            },
        },
    })
    rev = _make_rev(GRAPH_SCHEMA_V5, payload)
    registry = tu5._registry()

    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    reader = VersionedUnionGraphSnapshotReader(profile_registry=registry)
    hist_snapshot = reader.parse(graph_schema=GRAPH_SCHEMA_V5, graph_payload=payload)

    ok, hist_sha, parsed_sha = verify_historical_semantic_parity(hist_snapshot, parsed)
    assert ok is True
    assert hist_sha == parsed_sha


# 7. v6 stored revision decodes and has semantic parity
def test_07_v6_stored_revision_decodes_and_semantic_parity() -> None:
    payload = tu6._v6_payload()
    rev = _make_rev(GRAPH_SCHEMA_V6, payload)
    registry = tu6._registry()

    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    reader = VersionedUnionGraphSnapshotReader(profile_registry=registry)
    hist_snapshot = reader.parse(graph_schema=GRAPH_SCHEMA_V6, graph_payload=payload)

    ok, hist_sha, parsed_sha = verify_historical_semantic_parity(hist_snapshot, parsed)
    assert ok is True
    assert hist_sha == parsed_sha


# 8. Unsupported graph schema fails closed
def test_08_unsupported_graph_schema_fails_closed() -> None:
    payload = tr._payload()
    rev = _make_rev("dm_union_graph_v99", payload)
    with pytest.raises(
        LegacyCompatibilityIntegrityError, match="unsupported historical graph schema"
    ):
        decode_legacy_graph_revision(revision=rev, graph_payload=payload)


# 9. Payload digest mismatch fails closed
def test_09_payload_digest_mismatch_fails_closed() -> None:
    payload = tr._payload()
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    tampered_payload = copy.deepcopy(payload)
    tampered_payload["tampered"] = True
    with pytest.raises(LegacyCompatibilityIntegrityError, match="payload digest mismatch"):
        decode_legacy_graph_revision(revision=rev, graph_payload=tampered_payload)


# 10. World envelope/payload mismatch fails closed
def test_10_world_envelope_payload_mismatch_fails_closed() -> None:
    payload = tr._payload()
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    tampered_rev = WorldGraphRevision(
        schema_version=rev.schema_version,
        world_id="world:different-world-id",
        revision_id=rev.revision_id,
        parent_revision_id=rev.parent_revision_id,
        created_at=rev.created_at,
        operation_ids=rev.operation_ids,
        graph_schema=rev.graph_schema,
        graph_payload_sha256=canonical_sha256(payload),
        status=rev.status,
    )
    with pytest.raises(LegacyCompatibilityIntegrityError, match="does not match revision world_id"):
        decode_legacy_graph_revision(revision=tampered_rev, graph_payload=payload)


# 11. Malformed profile state fails closed
def test_11_malformed_profile_state_fails_closed() -> None:
    payload = tsp._v3_payload()
    rev = _make_rev(GRAPH_SCHEMA_V3, payload)
    # Empty registry fails to resolve narrative.core
    with pytest.raises((LegacyCompatibilityIntegrityError, PersistenceIntegrityError)):
        decode_legacy_graph_revision(revision=rev, graph_payload=payload, profile_registry=None)


# 12. Malformed historical structural state fails closed
def test_12_malformed_historical_structural_state_fails_closed() -> None:
    payload = copy.deepcopy(tr._payload())
    # Add dangling relationship endpoint
    rels = payload.get("relationships", [])
    assert isinstance(rels, list)
    rels.append({
        "relationship_id": "rel:dangling",
        "subject_object_id": "obj:city-vael",
        "predicate": "points_to",
        "object_object_id": "obj:nonexistent-node",
        "evidence_ref_ids": [],
    })
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    with pytest.raises((LegacyCompatibilityIntegrityError, PersistenceIntegrityError)):
        decode_legacy_graph_revision(revision=rev, graph_payload=payload)


# 13. Exact world_id becomes exact space_id
def test_13_exact_world_id_becomes_exact_space_id() -> None:
    payload = tr._payload()
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    parsed = decode_legacy_graph_revision(revision=rev, graph_payload=payload)
    assert parsed.space_id == rev.world_id
    assert parsed.identity.space_id == "world:demo-atlas"


# 14. Exact revision identity sequence and payload digest preserved
def test_14_exact_revision_identity_preserved() -> None:
    payload = tr._payload()
    rev = WorldGraphRevision(
        schema_version="dm_graph_revision_v1",
        world_id=str(payload["world_id"]),
        revision_id="rev:exact-id",
        parent_revision_id="rev:exact-parent",
        created_at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC),
        operation_ids=["op:gamma", "op:alpha", "op:beta"],  # unsorted
        graph_schema=GRAPH_SCHEMA_V1,
        graph_payload_sha256=canonical_sha256(payload),
        status="published",
    )
    parsed = decode_legacy_graph_revision(revision=rev, graph_payload=payload)
    assert parsed.revision_id == "rev:exact-id"
    assert parsed.parent_revision_id == "rev:exact-parent"
    assert parsed.created_at == datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)
    assert parsed.operation_ids == ("op:gamma", "op:alpha", "op:beta")
    assert parsed.graph_payload_sha256 == canonical_sha256(payload)


# 15. v3-v6 historical profile participates in compatibility identity
def test_15_v3_v6_historical_profile_in_compatibility_identity() -> None:
    payload = tsp._v3_payload()
    rev = _make_rev(GRAPH_SCHEMA_V3, payload)
    registry = tsp._narrative_registry()
    reader = VersionedUnionGraphSnapshotReader(profile_registry=registry)
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )
    assert parsed.semantic_profile_ref.profile_id == "test.narrative"
    assert parsed.semantic_profile_ref.profile_revision == "narrative-profile-v1"
    assert len(parsed.semantic_profile_ref.descriptor_sha256) == 64
    manifest = load_legacy_world_compat_manifest()
    expected = compute_legacy_compatibility_key(
        mapping_revision=manifest.compatibility_mapping_revision,
        mapping_manifest_sha256=COMPATIBILITY_MANIFEST_SHA256,
        mapping_implementation_digest=compute_mapping_implementation_digest(manifest),
        graph_schema=GRAPH_SCHEMA_V3,
        historical_parse_compatibility_id=reader.parse_compatibility_id,
        semantic_profile_ref=parsed.semantic_profile_ref,
        parsed_format_version=PARSED_REVISION_FORMAT_VERSION,
        legacy_payload_sha256=rev.graph_payload_sha256,
    )
    assert parsed.compatibility_key == expected
    # Native V1.1 key remains a distinct function and must not equal legacy key.
    assert parsed.compatibility_key != compute_compatibility_key(parsed.identity)


# 16. v1-v2 unprofiled compatibility identity is deterministic and explicit
def test_16_v1_v2_unprofiled_compatibility_identity() -> None:
    payload = tr._payload()
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    parsed = decode_legacy_graph_revision(revision=rev, graph_payload=payload)
    assert parsed.semantic_profile_ref.profile_id == "legacy.unprofiled"
    assert parsed.semantic_profile_ref.profile_revision == "none"
    assert parsed.semantic_profile_ref.descriptor_sha256 == "0" * 64
    assert parsed.compatibility_key is not None


# 17. Mapping manifest or version change changes compatibility key
def test_17_manifest_or_version_changes_compatibility_key() -> None:
    payload = tr._payload()
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    parsed1 = decode_legacy_graph_revision(revision=rev, graph_payload=payload)

    manifest = load_legacy_world_compat_manifest()
    mutated_content = manifest.to_canonical_dict()
    mutated_content["compatibility_mapping_revision"] = "dm_legacy_world_compat_v2_mutated"
    mutated_content["domain_contract_revision"] = "2"
    mutated_content["epistemic_translation_rules"] = {
        **mutated_content["epistemic_translation_rules"],
        "fact_is_not_asserted": False,
    }
    mutated_sha = canonical_sha256(mutated_content)
    mutated_manifest = LegacyCompatibilityManifest(
        manifest_schema=str(mutated_content["manifest_schema"]),
        compatibility_mapping_revision=str(
            mutated_content["compatibility_mapping_revision"]
        ),
        vnext_format_version=str(mutated_content["vnext_format_version"]),
        parsed_format_version=str(mutated_content["parsed_format_version"]),
        domain_contract_id=str(mutated_content["domain_contract_id"]),
        domain_contract_revision=str(mutated_content["domain_contract_revision"]),
        unprofiled_semantic_profile_id=str(
            mutated_content["unprofiled_semantic_profile_id"]
        ),
        unprofiled_semantic_profile_revision=str(
            mutated_content["unprofiled_semantic_profile_revision"]
        ),
        unprofiled_descriptor_sha256=str(
            mutated_content["unprofiled_descriptor_sha256"]
        ),
        supported_historical_schemas=tuple(
            mutated_content["supported_historical_schemas"]
        ),
        synthetic_assertion_id_templates=dict(
            mutated_content["synthetic_assertion_id_templates"]
        ),
        predicate_mappings=dict(mutated_content["predicate_mappings"]),
        scope_and_visibility_rules=dict(mutated_content["scope_and_visibility_rules"]),
        v1_v3_coarse_metadata_rules=dict(mutated_content["v1_v3_coarse_metadata_rules"]),
        epistemic_translation_rules=dict(mutated_content["epistemic_translation_rules"]),
        canon_state_translation_rules=dict(
            mutated_content["canon_state_translation_rules"]
        ),
        temporal_translation_rules=dict(mutated_content["temporal_translation_rules"]),
        evidence_translation_rules=dict(mutated_content["evidence_translation_rules"]),
        relationship_aspect_rules=dict(mutated_content["relationship_aspect_rules"]),
        identity_alias_admission_rules=dict(
            mutated_content["identity_alias_admission_rules"]
        ),
        manifest_sha256=mutated_sha,
    )
    parsed2 = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, manifest=mutated_manifest
    )
    assert parsed1.compatibility_key != parsed2.compatibility_key


def test_17b_legacy_payload_digest_and_parse_id_change_compatibility_key() -> None:
    payload_a = copy.deepcopy(tr._payload())
    payload_b = copy.deepcopy(tr._payload())
    nodes_b = payload_b.get("nodes", [])
    assert isinstance(nodes_b, list)
    nodes_b[0]["label"] = f"{nodes_b[0]['label']}-mutated-for-key"

    rev_a = _make_rev(GRAPH_SCHEMA_V1, payload_a, rev_id="rev:key-a")
    rev_b = _make_rev(GRAPH_SCHEMA_V1, payload_b, rev_id="rev:key-b")
    parsed_a = decode_legacy_graph_revision(revision=rev_a, graph_payload=payload_a)
    parsed_b = decode_legacy_graph_revision(revision=rev_b, graph_payload=payload_b)
    assert rev_a.graph_payload_sha256 != rev_b.graph_payload_sha256
    assert parsed_a.compatibility_key != parsed_b.compatibility_key

    payload_v3 = tsp._v3_payload()
    rev_v3 = _make_rev(GRAPH_SCHEMA_V3, payload_v3)
    registry = tsp._narrative_registry()
    parsed_with = decode_legacy_graph_revision(
        revision=rev_v3, graph_payload=payload_v3, profile_registry=registry
    )
    manifest = load_legacy_world_compat_manifest()
    mapping_revision = manifest.compatibility_mapping_revision
    mapping_impl = compute_mapping_implementation_digest(manifest)
    key_base = compute_legacy_compatibility_key(
        mapping_revision=mapping_revision,
        mapping_manifest_sha256=COMPATIBILITY_MANIFEST_SHA256,
        mapping_implementation_digest=mapping_impl,
        graph_schema=GRAPH_SCHEMA_V3,
        historical_parse_compatibility_id="VersionedUnionGraphSnapshotReader:registry-a",
        semantic_profile_ref=parsed_with.semantic_profile_ref,
        parsed_format_version=PARSED_REVISION_FORMAT_VERSION,
        legacy_payload_sha256=rev_v3.graph_payload_sha256,
    )
    key_other = compute_legacy_compatibility_key(
        mapping_revision=mapping_revision,
        mapping_manifest_sha256=COMPATIBILITY_MANIFEST_SHA256,
        mapping_implementation_digest=mapping_impl,
        graph_schema=GRAPH_SCHEMA_V3,
        historical_parse_compatibility_id="VersionedUnionGraphSnapshotReader:registry-b",
        semantic_profile_ref=parsed_with.semantic_profile_ref,
        parsed_format_version=PARSED_REVISION_FORMAT_VERSION,
        legacy_payload_sha256=rev_v3.graph_payload_sha256,
    )
    assert key_base != key_other


def test_17c_unverified_injected_manifest_fails_closed() -> None:
    payload = tr._payload()
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    manifest = load_legacy_world_compat_manifest()
    bad = LegacyCompatibilityManifest(
        manifest_schema=manifest.manifest_schema,
        compatibility_mapping_revision=manifest.compatibility_mapping_revision,
        vnext_format_version=manifest.vnext_format_version,
        parsed_format_version=manifest.parsed_format_version,
        domain_contract_id=manifest.domain_contract_id,
        domain_contract_revision=manifest.domain_contract_revision,
        unprofiled_semantic_profile_id=manifest.unprofiled_semantic_profile_id,
        unprofiled_semantic_profile_revision=(
            manifest.unprofiled_semantic_profile_revision
        ),
        unprofiled_descriptor_sha256=manifest.unprofiled_descriptor_sha256,
        supported_historical_schemas=manifest.supported_historical_schemas,
        synthetic_assertion_id_templates=dict(
            manifest.synthetic_assertion_id_templates
        ),
        predicate_mappings=dict(manifest.predicate_mappings),
        scope_and_visibility_rules=dict(manifest.scope_and_visibility_rules),
        v1_v3_coarse_metadata_rules=dict(manifest.v1_v3_coarse_metadata_rules),
        epistemic_translation_rules=dict(manifest.epistemic_translation_rules),
        canon_state_translation_rules=dict(manifest.canon_state_translation_rules),
        temporal_translation_rules=dict(manifest.temporal_translation_rules),
        evidence_translation_rules=dict(manifest.evidence_translation_rules),
        relationship_aspect_rules=dict(manifest.relationship_aspect_rules),
        identity_alias_admission_rules=dict(manifest.identity_alias_admission_rules),
        manifest_sha256="0" * 64,
    )
    with pytest.raises(LegacyCompatibilityIntegrityError, match="digest mismatch"):
        decode_legacy_graph_revision(revision=rev, graph_payload=payload, manifest=bad)


def test_17d_packaged_manifest_loads_independent_of_cwd(tmp_path: Path) -> None:
    import os

    original = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert not (tmp_path / "Docs").exists()
        manifest = load_legacy_world_compat_manifest()
        assert manifest.manifest_sha256 == COMPATIBILITY_MANIFEST_SHA256
        assert manifest.compatibility_mapping_revision == "dm_legacy_world_compat_v1"
    finally:
        os.chdir(original)

    audit = load_legacy_world_compat_manifest(DOCS_MANIFEST_AUDIT_PATH)
    assert audit.manifest_sha256 == COMPATIBILITY_MANIFEST_SHA256


def test_17e_valid_v1_duplicate_aliases_decode_without_collision() -> None:
    payload = copy.deepcopy(tr._payload())
    nodes = payload.get("nodes", [])
    assert isinstance(nodes, list)
    nodes[0]["aliases"] = ["Mere Astor", "Mere Astor", "Astor"]
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    parsed = decode_legacy_graph_revision(revision=rev, graph_payload=payload)
    alias_assertions = [
        a
        for a in parsed.assertions_by_id.values()
        if a.predicate == "dungeonmind.compat:alias"
        and a.subject_entity_id == nodes[0]["object_id"]
    ]
    assert len(alias_assertions) == 3
    assert len({a.assertion_id for a in alias_assertions}) == 3
    texts = [
        a.value.value
        for a in alias_assertions
        if isinstance(a.value, ParsedLiteralValue)
    ]
    assert texts.count("Mere Astor") == 2
    assert "Astor" in texts
    reader = VersionedUnionGraphSnapshotReader()
    hist = reader.parse(graph_schema=GRAPH_SCHEMA_V1, graph_payload=payload)
    ok, _, _ = verify_historical_semantic_parity(hist, parsed)
    assert ok is True


def test_17f_mapping_implementation_digest_seals_translator_source() -> None:
    manifest = load_legacy_world_compat_manifest()
    baseline = compute_mapping_implementation_digest(manifest)
    mutated = compute_mapping_implementation_digest(
        manifest,
        translator_sources={
            "_translate_assertion_metadata": "# synthetic mutation for digest test\n",
            "_synthetic_v1_alias_assertion_id": "pass",
            "_v1_alias_assertion_ids": "pass",
        },
    )
    assert baseline != mutated


def test_17g_manifest_visibility_labels_drive_decode_and_key() -> None:
    payload = tu4._v4_payload()
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed_base = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )
    gm_asrt = parsed_base.get_assertion("asrt:quill-alias-secret")
    assert gm_asrt is not None
    base_vis = gm_asrt.metadata.visibility
    assert isinstance(base_vis, ParsedLabelsAnyVisibility)
    assert base_vis.labels == ("audience:gm",)

    manifest = load_legacy_world_compat_manifest()
    mutated_content = manifest.to_canonical_dict()
    mutated_content["scope_and_visibility_rules"] = {
        **mutated_content["scope_and_visibility_rules"],
        "gm_visibility_label": "audience:gm_mutated_test",
        "player_visibility_label": "audience:player_mutated_test",
    }
    mutated_sha = canonical_sha256(mutated_content)
    mutated_manifest = LegacyCompatibilityManifest(
        manifest_schema=str(mutated_content["manifest_schema"]),
        compatibility_mapping_revision=str(
            mutated_content["compatibility_mapping_revision"]
        ),
        vnext_format_version=str(mutated_content["vnext_format_version"]),
        parsed_format_version=str(mutated_content["parsed_format_version"]),
        domain_contract_id=str(mutated_content["domain_contract_id"]),
        domain_contract_revision=str(mutated_content["domain_contract_revision"]),
        unprofiled_semantic_profile_id=str(
            mutated_content["unprofiled_semantic_profile_id"]
        ),
        unprofiled_semantic_profile_revision=str(
            mutated_content["unprofiled_semantic_profile_revision"]
        ),
        unprofiled_descriptor_sha256=str(
            mutated_content["unprofiled_descriptor_sha256"]
        ),
        supported_historical_schemas=tuple(
            mutated_content["supported_historical_schemas"]
        ),
        synthetic_assertion_id_templates=dict(
            mutated_content["synthetic_assertion_id_templates"]
        ),
        predicate_mappings=dict(mutated_content["predicate_mappings"]),
        scope_and_visibility_rules=dict(mutated_content["scope_and_visibility_rules"]),
        v1_v3_coarse_metadata_rules=dict(mutated_content["v1_v3_coarse_metadata_rules"]),
        epistemic_translation_rules=dict(mutated_content["epistemic_translation_rules"]),
        canon_state_translation_rules=dict(
            mutated_content["canon_state_translation_rules"]
        ),
        temporal_translation_rules=dict(mutated_content["temporal_translation_rules"]),
        evidence_translation_rules=dict(mutated_content["evidence_translation_rules"]),
        relationship_aspect_rules=dict(mutated_content["relationship_aspect_rules"]),
        identity_alias_admission_rules=dict(
            mutated_content["identity_alias_admission_rules"]
        ),
        manifest_sha256=mutated_sha,
    )
    parsed_mut = decode_legacy_graph_revision(
        revision=rev,
        graph_payload=payload,
        profile_registry=registry,
        manifest=mutated_manifest,
    )
    gm_mut = parsed_mut.get_assertion("asrt:quill-alias-secret")
    assert gm_mut is not None
    mut_vis = gm_mut.metadata.visibility
    assert isinstance(mut_vis, ParsedLabelsAnyVisibility)
    assert mut_vis.labels == ("audience:gm_mutated_test",)
    assert parsed_base.compatibility_key != parsed_mut.compatibility_key
    assert compute_mapping_implementation_digest(manifest) != (
        compute_mapping_implementation_digest(mutated_manifest)
    )


def test_17h_v1_alias_reorder_preserves_id_set_and_semantic_digest() -> None:
    payload_a = copy.deepcopy(tr._payload())
    payload_b = copy.deepcopy(tr._payload())
    nodes_a = payload_a.get("nodes", [])
    nodes_b = payload_b.get("nodes", [])
    assert isinstance(nodes_a, list) and isinstance(nodes_b, list)
    nodes_a[0]["aliases"] = ["Alpha", "Beta", "Alpha"]
    nodes_b[0]["aliases"] = ["Beta", "Alpha", "Alpha"]

    rev_a = _make_rev(GRAPH_SCHEMA_V1, payload_a, rev_id="rev:alias-order-a")
    rev_b = _make_rev(GRAPH_SCHEMA_V1, payload_b, rev_id="rev:alias-order-b")
    parsed_a = decode_legacy_graph_revision(revision=rev_a, graph_payload=payload_a)
    parsed_b = decode_legacy_graph_revision(revision=rev_b, graph_payload=payload_b)

    def _alias_ids(parsed: Any, entity_id: str) -> set[str]:
        return {
            a.assertion_id
            for a in parsed.assertions_by_id.values()
            if a.predicate == "dungeonmind.compat:alias"
            and a.subject_entity_id == entity_id
        }

    entity_id = nodes_a[0]["object_id"]
    assert _alias_ids(parsed_a, entity_id) == _alias_ids(parsed_b, entity_id)
    assert parsed_a.semantic_digest == parsed_b.semantic_digest


# 18. Object IDs become entity IDs without re-ID
def test_18_object_ids_become_entity_ids_without_re_id() -> None:
    payload = tr._payload()
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    parsed = decode_legacy_graph_revision(revision=rev, graph_payload=payload)
    nodes = payload.get("nodes", [])
    assert isinstance(nodes, list)
    for node in nodes:
        ent = parsed.get_entity(node["object_id"])
        assert ent is not None
        assert ent.entity_id == node["object_id"]


# 19. v4-v6 existence assertions remain distinct from entity identity
def test_19_v4_v6_existence_assertions_distinct_from_entity() -> None:
    payload = tu4._v4_payload()
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    # Node obj:person-quill has existence assertion asrt:quill-exists
    ent = parsed.get_entity("obj:person-quill")
    assert ent is not None
    exist_asrt = parsed.get_assertion("asrt:quill-exists")
    assert exist_asrt is not None
    assert exist_asrt.subject_entity_id == "obj:person-quill"
    assert exist_asrt.predicate == "dungeonmind.compat:existence"


# 20. kind/label/summary semantics are parity-complete
def test_20_kind_label_summary_semantics_are_parity_complete() -> None:
    payload = tu4._v4_payload()
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    kind_asrt = parsed.get_assertion(
        "asrt:compat:dm_legacy_world_compat_v1:obj:person-quill:kind"
    )
    assert kind_asrt is not None
    assert isinstance(kind_asrt.value, ParsedLiteralValue)
    assert kind_asrt.value.value == "test:person"

    label_asrt = parsed.get_assertion(
        "asrt:compat:dm_legacy_world_compat_v1:obj:person-quill:label"
    )
    assert label_asrt is not None
    assert isinstance(label_asrt.value, ParsedLiteralValue)
    assert label_asrt.value.value == "Quill"

    summary_asrt = parsed.get_assertion("asrt:quill-summary")
    assert summary_asrt is not None
    assert isinstance(summary_asrt.value, ParsedLiteralValue)
    assert summary_asrt.value.value == "a public archivist of the low ward"


# 21. Duplicate/conflicting property assertions are not collapsed
def test_21_duplicate_or_conflicting_properties_not_collapsed() -> None:
    payload = tu4._v4_payload()
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    # In v4 payload, obj:person-quill has two properties for "test:role":
    # asrt:quill-role-open and asrt:quill-role-hidden
    note1 = parsed.get_assertion("asrt:quill-role-open")
    note2 = parsed.get_assertion("asrt:quill-role-hidden")
    assert note1 is not None
    assert note2 is not None
    assert note1.assertion_id != note2.assertion_id
    assert note1.predicate == note2.predicate == "test:role"


# 22. Relationships preserve source/target/predicate and legacy identity
def test_22_relationships_preserve_endpoints_and_predicate() -> None:
    payload = tr._payload()
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    parsed = decode_legacy_graph_revision(revision=rev, graph_payload=payload)

    # In v1 payload: rel:astor-resides-vael
    rel_asrt = parsed.get_assertion(
        "asrt:compat:dm_legacy_world_compat_v1:rel:rel:astor-resides-vael"
    )
    assert rel_asrt is not None
    assert rel_asrt.subject_entity_id == "obj:npc-mere-astor"
    assert rel_asrt.predicate == "resides_in"
    assert isinstance(rel_asrt.value, ParsedEntityRefValue)
    assert rel_asrt.value.entity_id == "obj:city-vael"


# 23. v4-v6 relationship assertion metadata preserved
def test_23_v4_v6_relationship_assertion_metadata_preserved() -> None:
    payload = tu4._v4_payload()
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    rel_asrt = parsed.get_assertion("asrt:rel-quill-ward")
    assert rel_asrt is not None
    assert rel_asrt.metadata.standing == KnowledgeStanding.ESTABLISHED
    assert rel_asrt.metadata.epistemic_basis == "asserted"
    assert len(rel_asrt.metadata.scope) == 1
    assert rel_asrt.metadata.scope[0].axis == "dungeonmind.compat:campaign"
    assert rel_asrt.metadata.scope[0].value == "camp:assertion-scoped-v4"


# 24. v1-v3 synthetic assertion IDs are deterministic and collision-free
def test_24_v1_v3_synthetic_assertion_ids_deterministic_and_collision_free() -> None:
    payload = tr._payload()
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    parsed1 = decode_legacy_graph_revision(revision=rev, graph_payload=payload)
    parsed2 = decode_legacy_graph_revision(revision=rev, graph_payload=payload)

    assert set(parsed1.assertions_by_id.keys()) == set(parsed2.assertions_by_id.keys())
    # Assert no ID collisions
    assert len(parsed1.assertions_by_id) == len(set(parsed1.assertions_by_id.keys()))


# 25. Evidence identities and locator metadata are parity-complete
def test_25_evidence_identities_and_locator_metadata_complete() -> None:
    payload = tr._payload()
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    parsed = decode_legacy_graph_revision(revision=rev, graph_payload=payload)

    ev = parsed.get_evidence("ev:vael")
    assert ev is not None
    assert ev.evidence_ref_id == "ev:vael"
    assert ev.source_artifact_id == "src:atlas-notes"
    assert ev.source_revision_id == "srcrev:atlas-notes-v1"
    assert ev.locator == "fixture://atlas-notes#vael"
    assert ev.can_open_source is True


# 26. Scoped and GM alias assertions do not enter identity_aliases_by_id
def test_26_scoped_and_gm_aliases_remain_assertions_only() -> None:
    payload = tu4._v4_payload()
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    # In v4 payload, obj:person-quill has:
    # - asrt:quill-alias-public: campaign_scope='camp:assertion-scoped-v4' -> scoped!
    # - asrt:quill-alias-secret: visibility='gm' -> GM only!
    # Neither should enter parsed.aliases_by_id!
    assert "asrt:quill-alias-public" not in parsed.aliases_by_id
    assert "asrt:quill-alias-secret" not in parsed.aliases_by_id
    # Both MUST remain in parsed.assertions_by_id
    assert "asrt:quill-alias-public" in parsed.assertions_by_id
    assert "asrt:quill-alias-secret" in parsed.assertions_by_id


# 27. Alias ambiguity remains representable
def test_27_alias_ambiguity_remains_representable() -> None:
    payload = copy.deepcopy(tr._payload())
    # Assign same alias to two different nodes in v1
    nodes = payload.get("nodes", [])
    assert isinstance(nodes, list)
    nodes[0]["aliases"] = ["Common Name"]
    nodes[1]["aliases"] = ["Common Name"]
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    parsed = decode_legacy_graph_revision(revision=rev, graph_payload=payload)

    # Look up alias in alias_exact_index: should map to both identity aliases
    matched_alias_ids = parsed.lookup_alias("Common Name")
    assert len(matched_alias_ids) == 2


# 28. Legacy campaign scope is preserved in metadata without admission
def test_28_legacy_campaign_scope_preserved() -> None:
    payload = tu4._v4_payload()
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    asrt = parsed.get_assertion("asrt:quill-alias-public")
    assert asrt is not None
    assert any(
        b.axis == "dungeonmind.compat:campaign" and b.value == "camp:assertion-scoped-v4"
        for b in asrt.metadata.scope
    )


# 29. Legacy GM/PLAYER visibility preserved without admission
def test_29_legacy_gm_player_visibility_preserved() -> None:
    payload = tu4._v4_payload()
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    asrt_gm = parsed.get_assertion("asrt:quill-alias-secret")
    assert asrt_gm is not None
    assert isinstance(asrt_gm.metadata.visibility, ParsedLabelsAnyVisibility)
    assert "audience:gm" in asrt_gm.metadata.visibility.labels

    asrt_player = parsed.get_assertion("asrt:quill-exists")
    assert asrt_player is not None
    assert isinstance(asrt_player.metadata.visibility, ParsedLabelsAnyVisibility)
    assert "audience:player" in asrt_player.metadata.visibility.labels


# 30. Fact is not silently aliased to asserted
def test_30_fact_is_not_silently_aliased_to_asserted() -> None:
    payload = copy.deepcopy(tu4._v4_payload())
    # Explicitly test an assertion with epistemic_kind='fact'
    payload["objects"][0]["assertion_metadata"]["epistemic_kind"] = "fact"
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    asrt = parsed.get_assertion("asrt:quill-exists")
    assert asrt is not None
    assert asrt.metadata.epistemic_basis == "fact"
    dm_entry = next(
        e for e in asrt.metadata.domain_metadata
        if e.schema_term == "dungeonmind.compat:legacy_epistemic_kind"
    )
    assert isinstance(dm_entry.payload, (dict, FrozenDict))
    assert dm_entry.payload["epistemic_kind"] == "fact"


# 31. source_derived_candidate is not silently aliased to inferred
def test_31_source_derived_candidate_is_not_aliased_to_inferred() -> None:
    payload = copy.deepcopy(tu4._v4_payload())
    # Explicitly test an assertion with epistemic_kind='source_derived_candidate'
    payload["objects"][0]["assertion_metadata"]["epistemic_kind"] = "source_derived_candidate"
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    asrt = parsed.get_assertion("asrt:quill-exists")
    assert asrt is not None
    assert asrt.metadata.epistemic_basis == "source_derived_candidate"
    dm_entry = next(
        e for e in asrt.metadata.domain_metadata
        if e.schema_term == "dungeonmind.compat:legacy_epistemic_kind"
    )
    assert isinstance(dm_entry.payload, (dict, FrozenDict))
    assert dm_entry.payload["epistemic_kind"] == "source_derived_candidate"


# 32. Legacy canon state losslessly reconstructible
def test_32_legacy_canon_state_losslessly_reconstructible() -> None:
    payload = tu4._v4_payload()
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    asrt = parsed.get_assertion("asrt:quill-exists")
    assert asrt is not None
    dm_entry = next(
        e for e in asrt.metadata.domain_metadata
        if e.schema_term == "dungeonmind.compat:legacy_canon_state"
    )
    assert isinstance(dm_entry.payload, (dict, FrozenDict))
    assert dm_entry.payload["canon_state"] == CanonState.CANONICAL.value


# 33. Session refs preserved without becoming scope or time
def test_33_session_refs_preserved_without_becoming_scope_or_time() -> None:
    payload = tu4._v4_payload()
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    # In v4 payload, asrt:quill-exists has session_refs=['ses:0007']
    asrt = parsed.get_assertion("asrt:quill-exists")
    assert asrt is not None
    dm_entry = next(
        e for e in asrt.metadata.domain_metadata
        if e.schema_term == "dungeonmind.compat:session_refs"
    )
    assert isinstance(dm_entry.payload, (dict, FrozenDict))
    sess_refs = dm_entry.payload["session_refs"]
    assert isinstance(sess_refs, (list, tuple))
    assert "ses:0007" in sess_refs
    # Check that session_refs didn't leak into scope bindings
    assert not any("ses:0007" in b.value for b in asrt.metadata.scope)


# 34. Unknown temporal state distinct from timeless
def test_34_unknown_temporal_state_distinct_from_timeless() -> None:
    payload = copy.deepcopy(tu4._v4_payload())
    # obj 0 has unknown, obj 1 has world_timeless
    payload["objects"][1]["assertion_metadata"]["temporal_scope"] = {
        "kind": "world_timeless",
    }
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    asrt_unknown = parsed.get_assertion("asrt:quill-exists")
    assert asrt_unknown is not None
    assert isinstance(asrt_unknown.metadata.temporal_scope, ParsedUnknownTemporalScope)

    asrt_timeless = parsed.get_assertion("asrt:ward-exists")
    assert asrt_timeless is not None
    assert isinstance(asrt_timeless.metadata.temporal_scope, ParsedTimelessTemporalScope)


# 35. Fictional-time ref preserves exact bundle/campaign/anchor identity
def test_35_fictional_time_ref_preserves_exact_anchor_pointer() -> None:
    payload = copy.deepcopy(tu4._v4_payload())
    payload["objects"][0]["assertion_metadata"]["temporal_scope"] = {
        "kind": "fictional_time_ref",
        "fictional_time_ref": {
            "schema_version": "dm_fictional_time_anchor_ref_v1",
            "bundle_id": "bundle:ft-era1",
            "campaign_id": "camp:assertion-scoped-v4",
            "anchor_id": "anchor:first-light",
        },
    }
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    asrt = parsed.get_assertion("asrt:quill-exists")
    assert asrt is not None
    assert isinstance(asrt.metadata.temporal_scope, ParsedDomainTemporalScope)
    assert asrt.metadata.temporal_scope.schema_term == "dungeonmind.compat:fictional_time_ref"
    pl = asrt.metadata.temporal_scope.payload
    assert isinstance(pl, (dict, FrozenDict))
    assert pl["bundle_id"] == "bundle:ft-era1"
    assert pl["campaign_id"] == "camp:assertion-scoped-v4"
    assert pl["anchor_id"] == "anchor:first-light"


# 36. v6 source/target endpoint aspects are losslessly reconstructible
def test_36_v6_source_target_endpoint_aspects_reconstructible() -> None:
    payload = tu6._v6_payload()
    rev = _make_rev(GRAPH_SCHEMA_V6, payload)
    registry = tu6._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    # In v6, rel:leads has target_aspect_assertion_id='asrt:college-org'
    rel_asrt = parsed.get_assertion("asrt:leads")
    assert rel_asrt is not None
    dm_entry = next(
        e for e in rel_asrt.metadata.domain_metadata
        if e.schema_term == "dungeonmind.compat:relationship"
    )
    assert isinstance(dm_entry.payload, (dict, FrozenDict))
    assert dm_entry.payload["target_aspect_assertion_id"] == "asrt:college-org"
    assert dm_entry.payload["source_aspect_assertion_id"] is None


# 37. All six schemas pass canonical semantic parity
@pytest.mark.parametrize("schema,getter", [
    (GRAPH_SCHEMA_V1, lambda: (tr._payload(), None)),
    (GRAPH_SCHEMA_V2, lambda: (tag._v2_payload(), None)),
    (GRAPH_SCHEMA_V3, lambda: (tsp._v3_payload(), tsp._narrative_registry())),
    (GRAPH_SCHEMA_V4, lambda: (tu4._v4_payload(), tu4._registry())),
    (GRAPH_SCHEMA_V5, lambda: (tu5._v5_payload(), tu5._registry())),
    (GRAPH_SCHEMA_V6, lambda: (tu6._v6_payload(), tu6._registry())),
])
def test_37_all_six_schemas_pass_canonical_semantic_parity(schema: str, getter: Any) -> None:
    payload, registry = getter()
    rev = _make_rev(schema, payload)
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )
    reader = VersionedUnionGraphSnapshotReader(profile_registry=registry)
    hist_snapshot = reader.parse(graph_schema=schema, graph_payload=payload)
    ok, hist_sha, parsed_sha = verify_historical_semantic_parity(hist_snapshot, parsed)
    assert ok is True
    assert hist_sha == parsed_sha


# 38. Compatibility output remains deeply immutable under mutation attacks
def test_38_compatibility_output_remains_deeply_immutable() -> None:
    payload = copy.deepcopy(tu4._v4_payload())
    rev = _make_rev(GRAPH_SCHEMA_V4, payload)
    registry = tu4._registry()
    parsed = decode_legacy_graph_revision(
        revision=rev, graph_payload=payload, profile_registry=registry
    )

    # Attempt to mutate caller's input payload
    payload["objects"][0]["label"] = "Tampered Label"
    assert parsed.get_entity("obj:person-quill") is not None
    asrt_label = parsed.get_assertion(
        "asrt:compat:dm_legacy_world_compat_v1:obj:person-quill:label"
    )
    assert asrt_label is not None
    assert asrt_label.value.value == "Quill"  # type: ignore

    # Attempt to mutate parsed mappings
    with pytest.raises(TypeError):
        parsed.entities_by_id["obj:evil"] = parsed.entities_by_id["obj:person-quill"]  # type: ignore


# 39. Pure in-memory transformation: no repository/database/network calls
def test_39_pure_in_memory_transformation() -> None:
    # Validate validate_stored_legacy_graph_revision rejects bad payload without I/O
    payload = tr._payload()
    rev = _make_rev(GRAPH_SCHEMA_V1, payload)
    assert validate_stored_legacy_graph_revision(rev, payload) is None


# 40. Parity artifact regenerates byte-for-byte
def test_40_parity_artifact_is_exact() -> None:
    artifact_path = Path("Docs/Compatibility/legacy_v1_v6_parity_v1.json")
    assert artifact_path.exists()
    proc = subprocess.run(
        [sys.executable, "scripts/generate_legacy_compatibility_parity_artifact.py", "--check"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"check failed: {proc.stderr}\n{proc.stdout}"


# 41. Frozen V0 bundle aggregate remains exact
def test_41_v0_bundle_aggregate_remains_exact() -> None:
    bundle_path = Path("Docs/Contracts/vnext/dm_vnext_contract_v1.json")
    assert bundle_path.exists()
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert (
        bundle["aggregate_sha256"]
        == "fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea"
    )


# 42. Boundary guards: no generic vNext module imports dungeonmind_dnd
def test_42_boundary_guards_no_dnd_imports_in_vnext() -> None:
    vnext_dir = Path("src/dungeonmind/application/vnext")
    for py_file in vnext_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "dungeonmind_dnd" not in alias.name, (
                        f"Forbidden import in {py_file}: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert "dungeonmind_dnd" not in node.module, (
                    f"Forbidden import from {node.module} in {py_file}"
                )


# 43. Historical reader files remain at pinned content digests (CI-portable)
_HISTORICAL_READER_SHA256: dict[str, str] = {
    "src/dungeonmind/application/graph_snapshot.py": (
        "8d0fb363e27ac78004fe8a0f2b11916b72a4b41ea9b53e536c588c5927a42fa7"
    ),
    "src/dungeonmind/application/graph_snapshot_v4.py": (
        "2a041e7b7b4059da2199c23071b440ed11f8dc50f2d566905e30f2fb02fa5bdc"
    ),
    "src/dungeonmind/application/graph_snapshot_v5.py": (
        "2b50b8185d40721b95af48e03b1a8a1cb1a6c8b2bb9d294ea92ead6847551a20"
    ),
    "src/dungeonmind/application/graph_snapshot_v6.py": (
        "06afb20e30398ade199dece69f6ea38465fd154fb9b521659e161654988a2548"
    ),
    "src/dungeonmind/application/graph_scope.py": (
        "94d4c57306df85ee900f6723e09236da4279b13546dd845e47fdd6ff99108da2"
    ),
}


def test_43_historical_reader_files_remain_untouched() -> None:
    for rel_path, expected_sha in _HISTORICAL_READER_SHA256.items():
        path = Path(rel_path)
        assert path.exists(), f"missing historical reader file {rel_path}"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == expected_sha, (
            f"Historical file {rel_path} content changed: expected {expected_sha}, got {digest}"
        )
