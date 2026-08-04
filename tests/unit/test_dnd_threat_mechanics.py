"""B.3a pinned Threat mechanics-resource contract and hash gates."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dungeonmind.application.graph_snapshot import UnionGraphV3SnapshotReader
from dungeonmind.contracts.graph import StoredGraphRevision, WorldGraphRevision
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor, SemanticProfileRef
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.threat_mechanics import (
    derive_threat_mechanics_binding,
    derive_threat_mechanics_binding_id,
    hydrate_threat_mechanics,
)
from dungeonmind_dnd.contracts.mechanics_resources import (
    DndMechanicsResourceEnvelope,
    DndMechanicsResourceRef,
    DndThreatMechanicsBinding,
    DndThreatMechanicsHydration,
)
from dungeonmind_dnd.contracts.vocabulary import DndVocabularyRef

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dungeonmind_dnd"
PROFILE_DESCRIPTOR = (
    Path(__file__).resolve().parents[2] / "src/dungeonmind_dnd/profiles/dnd5e-v2.json"
)
RESOURCE_FIXTURE = FIXTURES / "tripod-null-calf-mechanics-resource-v1.json"
BINDING_FIXTURE = FIXTURES / "tripod-null-calf-threat-mechanics-binding-v1.json"
HYDRATION_FIXTURE = FIXTURES / "tripod-null-calf-threat-mechanics-hydration-v1.json"
MATERIALIZED_GRAPH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "contribution_reviews/tripod-null-calf-materialized-world-graph-v3.json"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _profile() -> SemanticProfileRef:
    return SemanticProfileRef(
        profile_id="dungeonmind.dnd5e",
        profile_revision="dnd5e-profile-v2",
        descriptor_sha256=(
            "57de5bc922503571d781f0de00d0a26b7aabcb3c363518e269f6c7a52a6c0086"
        ),
    )


def _vocabulary() -> DndVocabularyRef:
    return DndVocabularyRef(
        vocabulary_id="dungeonmind.dnd5e.threat",
        vocabulary_revision="threat-v1",
        catalog_sha256=(
            "0edaeee9dc6ccb0c507e79339ce74cbea7e3734bb42ae00b4833d02ac8ea6047"
        ),
    )


def _stored_revision() -> StoredGraphRevision:
    graph = _json(MATERIALIZED_GRAPH)
    return StoredGraphRevision(
        revision=WorldGraphRevision(
            world_id="world:synthetic-gatewatch",
            revision_id="rev:6e02bd224f6b5616534f10026c8b9679",
            parent_revision_id=None,
            created_at=datetime(2026, 8, 1, 18, 0, tzinfo=UTC),
            operation_ids=["op:materialize-tripod-null-calf-v1"],
            graph_schema="dm_union_graph_v3",
            graph_payload_sha256=(
                "75dd4d9f3425e6646d9141fde1ceea48d4574057bc0b5aada32b165de978adc5"
            ),
        ),
        graph_payload=graph,
    )


def _reader() -> UnionGraphV3SnapshotReader:
    descriptor = SemanticProfileDescriptor.model_validate(
        json.loads(PROFILE_DESCRIPTOR.read_text(encoding="utf-8"))
    )
    return UnionGraphV3SnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )


def _resource_ref() -> DndMechanicsResourceRef:
    return DndMechanicsResourceRef.model_validate(_json(RESOURCE_FIXTURE)["resource_ref"])


class _Resolver:
    def __init__(self, envelope: DndMechanicsResourceEnvelope) -> None:
        self.envelope = envelope
        self.calls: list[DndMechanicsResourceRef] = []

    def resolve(
        self, resource_ref: DndMechanicsResourceRef
    ) -> DndMechanicsResourceEnvelope:
        self.calls.append(resource_ref)
        return self.envelope


def test_complete_fixture_hashes_and_nested_defaults_are_canonical() -> None:
    resource = _json(RESOURCE_FIXTURE)
    binding = _json(BINDING_FIXTURE)
    hydration = _json(HYDRATION_FIXTURE)

    assert canonical_sha256(resource["mechanics_payload"]) == (
        "11e6e581606ffdd1091cf6d515c1fd4288772451a74ec14a979660acdeffd932"
    )
    assert canonical_sha256(resource) == (
        "e5a36d1e74deecf7c256bffa0934911ee665c0d2d3d6a4b6bafa9d5bd95411ae"
    )
    assert canonical_sha256(binding) == (
        "82a6cc1b5df140013ff24cc6dc63721d5c421ee7d6e0c185b22d48d15879dddb"
    )
    assert canonical_sha256(hydration) == (
        "166dfe01ad0e2f4b57de3c74cfd50160e34a29591957f85b4a786c9f2edd6e16"
    )
    assert "schema_version" in binding["semantic_profile"]
    assert "schema_version" in binding["threat_vocabulary"]
    assert "schema_version" in binding["resource_ref"]


def test_binding_derivation_matches_complete_fixture() -> None:
    expected = DndThreatMechanicsBinding.model_validate(_json(BINDING_FIXTURE))

    actual = derive_threat_mechanics_binding(
        expected.object_id,
        _resource_ref(),
        graph_revision=_stored_revision(),
        graph_reader=_reader(),
    )

    assert actual.model_dump(mode="json") == expected.model_dump(mode="json")
    assert actual.binding_id == "mechbind:872167afbc6e6a6b242c6d93036767ab"
    assert canonical_sha256(actual.model_dump(mode="json")) == (
        "82a6cc1b5df140013ff24cc6dc63721d5c421ee7d6e0c185b22d48d15879dddb"
    )


def test_binding_id_helper_uses_complete_nested_contract_dumps() -> None:
    binding = DndThreatMechanicsBinding.model_validate(_json(BINDING_FIXTURE))

    assert derive_threat_mechanics_binding_id(
        world_id=binding.world_id,
        graph_revision_id=binding.graph_revision_id,
        graph_payload_sha256=binding.graph_payload_sha256,
        semantic_profile=binding.semantic_profile,
        threat_vocabulary=binding.threat_vocabulary,
        object_id=binding.object_id,
        object_kind=binding.object_kind,
        threat_relationship_ids=copy.deepcopy(binding.threat_relationship_ids),
        resource_ref=binding.resource_ref,
        visibility=binding.visibility,
    ) == binding.binding_id


def test_hydration_matches_fixture_and_resolves_once_with_isolated_payload() -> None:
    resource = DndMechanicsResourceEnvelope.model_validate(_json(RESOURCE_FIXTURE))
    binding = DndThreatMechanicsBinding.model_validate(_json(BINDING_FIXTURE))
    expected = DndThreatMechanicsHydration.model_validate(_json(HYDRATION_FIXTURE))
    resolver = _Resolver(resource)

    actual = hydrate_threat_mechanics(
        binding,
        admissibility=Admissibility.GM,
        graph_revision=_stored_revision(),
        graph_reader=_reader(),
        resource_resolver=resolver,
    )

    assert len(resolver.calls) == 1
    assert actual.model_dump(mode="json") == expected.model_dump(mode="json")
    assert canonical_sha256(actual.model_dump(mode="json")) == (
        "166dfe01ad0e2f4b57de3c74cfd50160e34a29591957f85b4a786c9f2edd6e16"
    )
    assert actual.mechanics_payload is not resource.mechanics_payload
