"""E1 contract pins for the sealed Eldyrwild existing-world adoption bundle v2.

These tests consume the exact Buddy Git blob and the unchanged #33 parser.
They must not recanonicalize fixture bytes or patch DungeonMind runtime.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from dungeonmind.application.existing_world_adoption import (
    parse_existing_world_adoption_bundle,
)
from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V6,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts.contribution import GraphContributionV2
from dungeonmind.contracts.existing_world_adoption import (
    EXISTING_WORLD_ADOPTION_BUNDLE_V2_SCHEMA,
    sha256_bytes,
)
from dungeonmind.contracts.identity import IdentityDecisionRecordV2
from dungeonmind.contracts.vocabulary import ContributionEpistemicKind
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.world_object_vocabulary import load_builtin_v3_descriptor

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = (
    REPO_ROOT
    / "tests/fixtures/dungeonmind_dnd/eldyrwild_existing_world_adoption_bundle_v2.json"
)

GIT_BLOB_SHA = "274cdd9e6d38d5a00aa43d780779e95a7919d975"
BUNDLE_SHA256 = "90574dfc4101e4198c7fd96478d6f49e65aa534d0aa91fa41a9a17da9d49695f"
GRAPH_PAYLOAD_SHA256 = "047214f19e3a2d22b1cf3e0596283844ef34853dd2e4f38d341c6b212ae320ef"
PUBLISHED_REVISION_ID = "rev:34b1f8e2625d5ba693fc726a2a1a4720"
WORLD_ID = "eldyrwild"
ADOPTION_ID = "adoption:eldyrwild:dungeonmind-v6:rev:0c644e56b45bcaac709012206e3e41c2"
PRODUCER_REVISION = "4446b6d207921a4be121ebb756d68b6078b8eee0"
PROFILE_V3_DIGEST = "2199e8fb96e917c22718e6aec59cbbf55a37ee81575e1bcf16ce13fae0393496"
SOURCE_WORLD_REVISION_ID = "rev:0c644e56b45bcaac709012206e3e41c2"
SOURCE_GRAPH_PAYLOAD_SHA256 = (
    "0640d7ef8ce152ee4f656959e0e9a6c9c2fdf5ecc8bd721729b3019170d677f2"
)
NOW = datetime(2026, 8, 16, 21, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)

EXPECTED_SOURCE_ARTIFACTS = 83
EXPECTED_SOURCE_REVISIONS = 83
EXPECTED_CONTRIBUTIONS = 93
EXPECTED_IDENTITY_DECISIONS = 13
EXPECTED_OBJECTS = 469
EXPECTED_RELATIONSHIPS = 323
EXPECTED_GRAPH_EVIDENCE_REFS = 184
EXPECTED_SECONDARY_ASPECTS = 3
EXPECTED_ASPECT_SELECTED_RELATIONSHIPS = 5
EXPECTED_ASPECT_OBJECTS = {
    "loc:wizard_college": ("dnd5e:location", "dnd5e:faction"),
    "node:hempholm_folk_revelry": ("dnd5e:group", "dnd5e:event"),
    "node:meat_distribution_network_session9": ("dnd5e:party", "dnd5e:location"),
}

WITNESS_RAW_EVIDENCE_ID = (
    "evidence:artifact:recap:longmont-c1:session-10:session-10:recap:paragraph:002"
)
WITNESS_CONTRIBUTION_ID = "contribution:2807888820d76c78"
WITNESS_SOURCE_REVISIONS = frozenset(
    {
        "sha256:04e6b145f64e4c2788f1afbb8a820b9be1222039471e343419bf247fbc6b96bf",
        "sha256:f0f49045df06f7baf61aa9c43f3739d16483eeb20ac8ed1bbf29f8209474af25",
    }
)
CONTRIBUTION_EVIDENCE_ID_MARK = ":dmv1:"

PRECOMMIT_FAILURE_STAGES = (
    "source_records",
    "contributions",
    "identity_decisions",
    "source_history",
    "graph",
    "receipt",
)


def raw_bundle() -> bytes:
    return BUNDLE_PATH.read_bytes()


def git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def eldyrwild_graph_reader() -> VersionedUnionGraphSnapshotReader:
    descriptor = load_builtin_v3_descriptor()
    assert descriptor_sha256(descriptor) == PROFILE_V3_DIGEST
    return VersionedUnionGraphSnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )


def parse_sealed_bundle():
    return parse_existing_world_adoption_bundle(
        raw_bundle(),
        graph_reader=eldyrwild_graph_reader(),
    )


def aspect_selected(relationships: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        relationship
        for relationship in relationships
        if relationship.get("source_aspect_assertion_id")
        or relationship.get("target_aspect_assertion_id")
    ]


def contribution_evidence_bindings(bundle) -> dict[str, dict[str, object]]:
    bindings: dict[str, dict[str, object]] = {}
    for contribution in bundle.contributions:
        for assertion in contribution.assertions:
            for ref in assertion.evidence_refs:
                payload = ref.model_dump(mode="json")
                prior = bindings.get(ref.evidence_ref_id)
                if prior is None:
                    bindings[ref.evidence_ref_id] = payload
                    continue
                if prior != payload:
                    raise AssertionError(
                        "conflicting immutable evidence payload for "
                        f"{ref.evidence_ref_id} in {contribution.contribution_id}"
                    )
    return bindings


def test_fixture_bytes_are_the_sealed_buddy_blob() -> None:
    raw = raw_bundle()
    assert git_blob_sha1(raw) == GIT_BLOB_SHA
    assert sha256_bytes(raw) == BUNDLE_SHA256


def test_one_byte_drift_fails_the_sealed_blob_oid_pin() -> None:
    raw = raw_bundle()
    drifted = raw[:-1] + bytes([raw[-1] ^ 0x01])
    assert git_blob_sha1(raw) == GIT_BLOB_SHA
    assert git_blob_sha1(drifted) != GIT_BLOB_SHA


def test_parse_accepts_the_exact_v2_bundle() -> None:
    bundle = parse_sealed_bundle()
    assert bundle.schema_version == EXISTING_WORLD_ADOPTION_BUNDLE_V2_SCHEMA
    assert bundle.world_id == WORLD_ID
    assert bundle.adoption_id == ADOPTION_ID
    assert bundle.graph_schema == GRAPH_SCHEMA_V6
    assert bundle.source_provenance.producer_revision == PRODUCER_REVISION
    assert bundle.source_provenance.source_world_revision_id == SOURCE_WORLD_REVISION_ID
    assert bundle.source_provenance.source_graph_payload_sha256 == SOURCE_GRAPH_PAYLOAD_SHA256
    assert len(bundle.source_artifacts) == EXPECTED_SOURCE_ARTIFACTS
    assert len(bundle.source_revisions) == EXPECTED_SOURCE_REVISIONS
    assert len(bundle.contributions) == EXPECTED_CONTRIBUTIONS
    assert len(bundle.identity_decisions) == EXPECTED_IDENTITY_DECISIONS
    assert all(isinstance(item, GraphContributionV2) for item in bundle.contributions)
    assert all(isinstance(item, IdentityDecisionRecordV2) for item in bundle.identity_decisions)
    payload = bundle.graph_payload
    assert payload["semantic_profile"]["descriptor_sha256"] == PROFILE_V3_DIGEST
    assert payload["relationship_endpoint_aspect_schema"] == "dm_relationship_endpoint_aspect_v1"
    assert len(payload["objects"]) == EXPECTED_OBJECTS
    assert len(payload["relationships"]) == EXPECTED_RELATIONSHIPS
    assert len(payload["evidence_refs"]) == EXPECTED_GRAPH_EVIDENCE_REFS
    assert canonical_sha256(payload) == GRAPH_PAYLOAD_SHA256
    expected_revision = compute_revision_id(
        world_id=WORLD_ID,
        parent_revision_id=None,
        operation_ids=[ADOPTION_ID],
        graph_schema=bundle.graph_schema,
        graph_payload_sha256=GRAPH_PAYLOAD_SHA256,
    )
    assert expected_revision == PUBLISHED_REVISION_ID


def test_current_graph_keeps_three_aspects_and_five_aspect_selected_relationships() -> None:
    bundle = parse_sealed_bundle()
    objects = bundle.graph_payload["objects"]
    aspects = [aspect for obj in objects for aspect in obj.get("aspects") or []]
    assert len(aspects) == EXPECTED_SECONDARY_ASPECTS
    aspect_objects = {
        obj["object_id"]: (obj["kind"], aspect["kind"])
        for obj in objects
        for aspect in obj.get("aspects") or []
    }
    assert aspect_objects == EXPECTED_ASPECT_OBJECTS
    selected = aspect_selected(bundle.graph_payload["relationships"])
    assert len(selected) == EXPECTED_ASPECT_SELECTED_RELATIONSHIPS


def test_v2_history_preserves_corrections_candidates_and_merge_side_effects() -> None:
    bundle = parse_sealed_bundle()
    corrections = [
        correction
        for contribution in bundle.contributions
        for correction in contribution.assertion_corrections
    ]
    source_derived = [
        assertion
        for contribution in bundle.contributions
        for assertion in contribution.assertions
        if assertion.epistemic_kind is ContributionEpistemicKind.SOURCE_DERIVED_CANDIDATE
    ]
    merge_effects = [
        decision.merge_side_effects
        for decision in bundle.identity_decisions
        if decision.merge_side_effects is not None
    ]
    assert corrections
    assert source_derived
    assert merge_effects
    assert all(
        correction.correction_kind.value in {"contradicts", "contradicts_and_replaces"}
        and correction.target_contribution_id
        and correction.target_assertion_id
        for correction in corrections
    )
    assert all(
        effect.aliases_added_to_target is not None
        and effect.evidence_ref_ids_added_to_target is not None
        and effect.source_domains_added_to_target is not None
        and effect.alias_map_rewrites is not None
        for effect in merge_effects
    )


def test_contribution_evidence_ids_have_no_conflicting_immutable_bindings() -> None:
    bundle = parse_sealed_bundle()
    bindings = contribution_evidence_bindings(bundle)
    assert bindings
    graph_bindings: dict[str, dict[str, object]] = {}
    for ref in bundle.graph_payload["evidence_refs"]:
        evidence_id = ref["evidence_ref_id"]
        prior = graph_bindings.get(evidence_id)
        if prior is None:
            graph_bindings[evidence_id] = ref
            continue
        assert prior == ref
    contribution = next(
        item for item in bundle.contributions if item.contribution_id == WITNESS_CONTRIBUTION_ID
    )
    by_revision: dict[str, set[str]] = {}
    for assertion in contribution.assertions:
        for ref in assertion.evidence_refs:
            marker = WITNESS_RAW_EVIDENCE_ID + CONTRIBUTION_EVIDENCE_ID_MARK
            if not ref.evidence_ref_id.startswith(marker):
                continue
            assert ref.source_revision_id in WITNESS_SOURCE_REVISIONS
            by_revision.setdefault(ref.source_revision_id, set()).add(ref.evidence_ref_id)
    assert set(by_revision) == WITNESS_SOURCE_REVISIONS
    exported = {next(iter(ids)) for ids in by_revision.values()}
    assert len(exported) == 2
    assert all(CONTRIBUTION_EVIDENCE_ID_MARK in evidence_id for evidence_id in exported)
