"""World-object vocabulary, hostility-independent mechanics, and B.3a compatibility."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from dungeonmind.application.graph_snapshot import UnionGraphV3SnapshotReader
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts.graph import StoredGraphRevision, WorldGraphRevision
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.canonical import canonical_sha256, sha256_text
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.threat_candidates import load_builtin_threat_vocabulary
from dungeonmind_dnd.application.threat_mechanics import (
    derive_threat_mechanics_binding,
    hydrate_threat_mechanics,
)
from dungeonmind_dnd.application.world_object_mechanics import (
    derive_world_object_mechanics_binding,
    hydrate_world_object_mechanics,
)
from dungeonmind_dnd.application.world_object_vocabulary import (
    builtin_world_object_vocabulary_ref,
    load_builtin_v3_descriptor,
    load_builtin_world_object_vocabulary,
    vocabulary_sha256,
)
from dungeonmind_dnd.contracts.mechanics_resources import (
    DndMechanicsResourceEnvelope,
    DndMechanicsResourceRef,
    DndThreatMechanicsBinding,
)
from dungeonmind_dnd.contracts.world_object_mechanics import (
    DndStatblockMechanicsAttachment,
    DndWorldObjectMechanicsBinding,
    derive_world_object_mechanics_binding_id,
    enumerate_statblock_mechanics_attachments,
)
from dungeonmind_dnd.domain.errors import DndWorldObjectMechanicsHydrationError

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dungeonmind_dnd"
V1_PATH = REPO_ROOT / "src/dungeonmind_dnd/profiles/dnd5e-v1.json"
V2_PATH = REPO_ROOT / "src/dungeonmind_dnd/profiles/dnd5e-v2.json"
V3_PATH = REPO_ROOT / "src/dungeonmind_dnd/profiles/dnd5e-v3.json"
THREAT_VOCAB_PATH = REPO_ROOT / "src/dungeonmind_dnd/vocabularies/threat-v1.json"
WORLD_OBJECT_VOCAB_PATH = (
    REPO_ROOT / "src/dungeonmind_dnd/vocabularies/world-object-v1.json"
)
BINDING_FIXTURE = FIXTURES / "tripod-null-calf-threat-mechanics-binding-v1.json"
RESOURCE_FIXTURE = FIXTURES / "tripod-null-calf-mechanics-resource-v1.json"
MATERIALIZED_GRAPH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "contribution_reviews/tripod-null-calf-materialized-world-graph-v3.json"
)

V1_DIGEST = "582851c0fc41897fff5a57a4fd6dd7fb7078b865315a30bc21552c82e7596967"
V2_DIGEST = "57de5bc922503571d781f0de00d0a26b7aabcb3c363518e269f6c7a52a6c0086"
V3_DIGEST = "2199e8fb96e917c22718e6aec59cbbf55a37ee81575e1bcf16ce13fae0393496"
THREAT_VOCAB_DIGEST = (
    "0edaeee9dc6ccb0c507e79339ce74cbea7e3734bb42ae00b4833d02ac8ea6047"
)
WORLD_OBJECT_VOCAB_DIGEST = (
    "7cc3b285611ed13eb01e0cdc8a963cfa0bea3130abe0ce816204ab67186cb880"
)


def _evidence(evidence_ref_id: str) -> dict[str, Any]:
    return {
        "schema_version": "dm_evidence_ref_v1",
        "evidence_ref_id": evidence_ref_id,
        "source_artifact_id": "src:synthetic-world-object",
        "source_revision_id": "srcrev:synthetic-world-object-v1",
        "source_domain": "prep",
        "evidence_role": "support",
        "can_open_source": True,
        "can_highlight_span": True,
        "locator": f"fixture://synthetic-world-object#{evidence_ref_id}",
        "uri": None,
    }


def _node(
    object_id: str,
    kind: str,
    *,
    label: str,
    evidence_ref_id: str,
) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "kind": kind,
        "label": label,
        "evidence_ref_ids": [evidence_ref_id],
        "alias_assertions": [],
        "summary_assertion": None,
    }


def _rel(
    relationship_id: str,
    subject: str,
    predicate: str,
    obj: str,
    *,
    evidence_ref_id: str,
) -> dict[str, Any]:
    return {
        "relationship_id": relationship_id,
        "subject_object_id": subject,
        "predicate": predicate,
        "object_object_id": obj,
        "evidence_ref_ids": [evidence_ref_id],
    }


def _graph_payload(
    *,
    nodes: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    evidence_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "world_id": "world:synthetic-world-object",
        "semantic_profile": {
            "schema_version": "dm_semantic_profile_ref_v1",
            "profile_id": "dungeonmind.dnd5e",
            "profile_revision": "dnd5e-profile-v3",
            "descriptor_sha256": V3_DIGEST,
        },
        "nodes": nodes,
        "relationships": relationships,
        "evidence_refs": evidence_refs,
    }


def _stored_revision(graph_payload: dict[str, Any]) -> StoredGraphRevision:
    payload_sha = canonical_sha256(graph_payload)
    revision_id = compute_revision_id(
        world_id="world:synthetic-world-object",
        parent_revision_id=None,
        operation_ids=["op:synthetic-world-object-v1"],
        graph_schema="dm_union_graph_v3",
        graph_payload_sha256=payload_sha,
    )
    return StoredGraphRevision(
        revision=WorldGraphRevision(
            world_id="world:synthetic-world-object",
            revision_id=revision_id,
            parent_revision_id=None,
            created_at=datetime(2026, 8, 7, 16, 0, tzinfo=UTC),
            operation_ids=["op:synthetic-world-object-v1"],
            graph_schema="dm_union_graph_v3",
            graph_payload_sha256=payload_sha,
        ),
        graph_payload=graph_payload,
    )


def _reader() -> UnionGraphV3SnapshotReader:
    descriptor = load_builtin_v3_descriptor()
    return UnionGraphV3SnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )


def _resource_for(resource_id: str, payload: dict[str, Any]) -> DndMechanicsResourceEnvelope:
    digest = canonical_sha256(payload)
    ref = DndMechanicsResourceRef(
        ruleset_id="dnd5e",
        provider_id="fixture.dungeonmind.statblocks",
        resource_id=resource_id,
        resource_revision=f"{resource_id}-v1",
        resource_schema="fixture_dnd5e_statblock_v1",
        media_type="application/json",
        payload_sha256=digest,
    )
    return DndMechanicsResourceEnvelope(
        resource_ref=ref,
        mechanics_payload=payload,
    )


class _Resolver:
    def __init__(self, envelopes: dict[str, DndMechanicsResourceEnvelope]) -> None:
        self.envelopes = envelopes
        self.calls: list[DndMechanicsResourceRef] = []

    def resolve(
        self, resource_ref: DndMechanicsResourceRef
    ) -> DndMechanicsResourceEnvelope | None:
        self.calls.append(resource_ref)
        return self.envelopes.get(resource_ref.resource_id)


def _fixture_a_graph() -> dict[str, Any]:
    """Threat + mechanics + zero threatens."""
    ev = [_evidence("ev:threat-a"), _evidence("ev:loc-a")]
    nodes = [
        _node("obj:loc-a", "dnd5e:location", label="Keep", evidence_ref_id="ev:loc-a"),
        _node(
            "obj:threat-a",
            "dnd5e:threat",
            label="Synthetic Threat A",
            evidence_ref_id="ev:threat-a",
        ),
    ]
    return _graph_payload(nodes=nodes, relationships=[], evidence_refs=ev)


def _fixture_b_graph() -> dict[str, Any]:
    """NPC + mechanics + zero threatens."""
    ev = [_evidence("ev:npc-b"), _evidence("ev:loc-b")]
    nodes = [
        _node("obj:loc-b", "dnd5e:location", label="Hall", evidence_ref_id="ev:loc-b"),
        _node(
            "obj:npc-b",
            "dnd5e:npc",
            label="Synthetic NPC B",
            evidence_ref_id="ev:npc-b",
        ),
    ]
    return _graph_payload(nodes=nodes, relationships=[], evidence_refs=ev)


def _fixture_c_graph() -> dict[str, Any]:
    """Threat + threatens + zero mechanics attachments (graph only)."""
    ev = [
        _evidence("ev:threat-c"),
        _evidence("ev:loc-c"),
        _evidence("ev:threatens-c"),
    ]
    nodes = [
        _node("obj:loc-c", "dnd5e:location", label="Gate", evidence_ref_id="ev:loc-c"),
        _node(
            "obj:threat-c",
            "dnd5e:threat",
            label="Synthetic Threat C",
            evidence_ref_id="ev:threat-c",
        ),
    ]
    relationships = [
        _rel(
            "rel:threat-c-threatens-loc-c",
            "obj:threat-c",
            "dnd5e:threatens",
            "obj:loc-c",
            evidence_ref_id="ev:threatens-c",
        )
    ]
    return _graph_payload(nodes=nodes, relationships=relationships, evidence_refs=ev)


def _fixture_d_graph() -> dict[str, Any]:
    """NPC that contextually threatens remains NPC."""
    ev = [
        _evidence("ev:npc-d"),
        _evidence("ev:loc-d"),
        _evidence("ev:threatens-d"),
    ]
    nodes = [
        _node("obj:loc-d", "dnd5e:location", label="Ward", evidence_ref_id="ev:loc-d"),
        _node(
            "obj:npc-d",
            "dnd5e:npc",
            label="Synthetic NPC D",
            evidence_ref_id="ev:npc-d",
        ),
    ]
    relationships = [
        _rel(
            "rel:npc-d-threatens-loc-d",
            "obj:npc-d",
            "dnd5e:threatens",
            "obj:loc-d",
            evidence_ref_id="ev:threatens-d",
        )
    ]
    return _graph_payload(nodes=nodes, relationships=relationships, evidence_refs=ev)


def _fixture_e_graph() -> dict[str, Any]:
    """Threat with multiple attachments (roles proven in test, not graph)."""
    return _fixture_a_graph()


def _fixture_f_graph() -> dict[str, Any]:
    """PlayerCharacter identity only."""
    ev = [_evidence("ev:pc-f"), _evidence("ev:loc-f")]
    nodes = [
        _node("obj:loc-f", "dnd5e:location", label="Camp", evidence_ref_id="ev:loc-f"),
        _node(
            "obj:pc-f",
            "dnd5e:player_character",
            label="Synthetic PC F",
            evidence_ref_id="ev:pc-f",
        ),
    ]
    return _graph_payload(nodes=nodes, relationships=[], evidence_refs=ev)


def test_published_profile_and_threat_vocabulary_bytes_unchanged() -> None:
    assert descriptor_sha256(
        SemanticProfileDescriptor.model_validate_json(V1_PATH.read_text())
    ) == V1_DIGEST
    assert descriptor_sha256(
        SemanticProfileDescriptor.model_validate_json(V2_PATH.read_text())
    ) == V2_DIGEST
    assert sha256_text(THREAT_VOCAB_PATH.read_text(encoding="utf-8")) == sha256_text(
        THREAT_VOCAB_PATH.read_text(encoding="utf-8")
    )
    catalog = load_builtin_threat_vocabulary()
    assert vocabulary_sha256(catalog) == THREAT_VOCAB_DIGEST
    assert json.loads(BINDING_FIXTURE.read_text())["binding_id"] == (
        "mechbind:872167afbc6e6a6b242c6d93036767ab"
    )


def test_world_object_profile_and_vocabulary_pins() -> None:
    descriptor = load_builtin_v3_descriptor()
    assert descriptor.profile_revision == "dnd5e-profile-v3"
    assert descriptor_sha256(descriptor) == V3_DIGEST
    catalog = load_builtin_world_object_vocabulary()
    assert vocabulary_sha256(catalog) == WORLD_OBJECT_VOCAB_DIGEST
    assert catalog.vocabulary_revision == "world-object-v1"
    kinds = {kind.term for kind in catalog.object_kinds}
    assert kinds == {
        "dnd5e:creature",
        "dnd5e:threat",
        "dnd5e:npc",
        "dnd5e:player_character",
        "dnd5e:location",
        "dnd5e:faction",
        "dnd5e:encounter",
    }
    threatens = next(p for p in catalog.predicates if p.term == "dnd5e:threatens")
    assert "dnd5e:threat" in threatens.subject_kinds
    assert "dnd5e:npc" in threatens.subject_kinds
    assert "dnd5e:player_character" in threatens.subject_kinds
    ref = builtin_world_object_vocabulary_ref()
    assert ref.catalog_sha256 == WORLD_OBJECT_VOCAB_DIGEST


def test_fixture_a_threat_mechanics_without_hostility() -> None:
    stored = _stored_revision(_fixture_a_graph())
    envelope = _resource_for("statblock:threat-a", {"name": "Threat A", "ac": 15})
    binding = derive_world_object_mechanics_binding(
        "obj:threat-a",
        envelope.resource_ref,
        graph_revision=stored,
        graph_reader=_reader(),
    )
    assert binding.object_kind == "dnd5e:threat"
    assert "threat_relationship_ids" not in binding.model_dump()
    hydration = hydrate_world_object_mechanics(
        binding,
        admissibility=Admissibility.GM,
        graph_revision=stored,
        graph_reader=_reader(),
        resource_resolver=_Resolver({envelope.resource_ref.resource_id: envelope}),
    )
    assert hydration.mechanics_payload == envelope.mechanics_payload


def test_fixture_b_npc_mechanics_without_hostility() -> None:
    stored = _stored_revision(_fixture_b_graph())
    envelope = _resource_for("statblock:npc-b", {"name": "NPC B", "ac": 12})
    binding = derive_world_object_mechanics_binding(
        "obj:npc-b",
        envelope.resource_ref,
        graph_revision=stored,
        graph_reader=_reader(),
    )
    assert binding.object_kind == "dnd5e:npc"
    hydration = hydrate_world_object_mechanics(
        binding,
        admissibility=Admissibility.GM,
        graph_revision=stored,
        graph_reader=_reader(),
        resource_resolver=_Resolver({envelope.resource_ref.resource_id: envelope}),
    )
    assert hydration.binding.binding_id == binding.binding_id


def test_fixture_c_threat_with_threatens_and_no_mechanics() -> None:
    stored = _stored_revision(_fixture_c_graph())
    snapshot = _reader().parse(
        graph_schema=stored.revision.graph_schema,
        graph_payload=copy.deepcopy(stored.graph_payload),
    )
    assert snapshot.objects["obj:threat-c"].kind == "dnd5e:threat"
    threatens = [
        rel
        for rel in snapshot.relationships.values()
        if rel.predicate == "dnd5e:threatens"
        and rel.subject_object_id == "obj:threat-c"
    ]
    assert len(threatens) == 1
    # No synthetic mechanics binding is created merely because threatens exists.


def test_fixture_d_npc_that_threatens_remains_npc() -> None:
    stored = _stored_revision(_fixture_d_graph())
    snapshot = _reader().parse(
        graph_schema=stored.revision.graph_schema,
        graph_payload=copy.deepcopy(stored.graph_payload),
    )
    assert snapshot.objects["obj:npc-d"].kind == "dnd5e:npc"
    envelope = _resource_for("statblock:npc-d", {"name": "NPC D"})
    binding = derive_world_object_mechanics_binding(
        "obj:npc-d",
        envelope.resource_ref,
        graph_revision=stored,
        graph_reader=_reader(),
    )
    assert binding.object_kind == "dnd5e:npc"


def test_fixture_e_multiple_statblock_attachments_no_first_winner() -> None:
    stored = _stored_revision(_fixture_e_graph())
    primary = _resource_for("statblock:threat-a-primary", {"name": "Primary", "hp": 40})
    phase = _resource_for("statblock:threat-a-phase", {"name": "Phase", "hp": 80})
    alternate = _resource_for(
        "statblock:threat-a-alternate", {"name": "Alternate", "hp": 30}
    )
    bindings = []
    for envelope in (alternate, phase, primary):
        bindings.append(
            derive_world_object_mechanics_binding(
                "obj:threat-a",
                envelope.resource_ref,
                graph_revision=stored,
                graph_reader=_reader(),
            )
        )
    attachments = [
        DndStatblockMechanicsAttachment(binding=bindings[0], role="alternate"),
        DndStatblockMechanicsAttachment(
            binding=bindings[1], role="phase", phase_key="enraged"
        ),
        DndStatblockMechanicsAttachment(binding=bindings[2], role="primary"),
    ]
    enumerated = enumerate_statblock_mechanics_attachments(attachments)
    assert len(enumerated) == 3
    assert {item.role for item in enumerated} == {"primary", "phase", "alternate"}
    assert [item.role for item in enumerated] != ["primary"]  # not first-winner collapse
    # Deterministic order by binding_id then role then phase_key.
    assert enumerated == sorted(
        attachments,
        key=lambda item: (
            item.binding.binding_id,
            item.role,
            item.phase_key or "",
        ),
    )


def test_fixture_f_player_character_identity_without_invented_mechanics() -> None:
    stored = _stored_revision(_fixture_f_graph())
    snapshot = _reader().parse(
        graph_schema=stored.revision.graph_schema,
        graph_payload=copy.deepcopy(stored.graph_payload),
    )
    assert snapshot.objects["obj:pc-f"].kind == "dnd5e:player_character"
    envelope = _resource_for("statblock:fake-pc", {"name": "Fake"})
    with pytest.raises(DndWorldObjectMechanicsHydrationError) as exc:
        derive_world_object_mechanics_binding(
            "obj:pc-f",
            envelope.resource_ref,
            graph_revision=stored,
            graph_reader=_reader(),
        )
    assert exc.value.details["reason"] == "object_kind_not_eligible"


def test_creature_is_not_eligible_for_world_object_mechanics() -> None:
    """Peer kinds: legacy creature remains on B.3a path, not the new binding."""
    ev = [_evidence("ev:creature"), _evidence("ev:loc")]
    nodes = [
        _node("obj:loc", "dnd5e:location", label="Yard", evidence_ref_id="ev:loc"),
        _node(
            "obj:creature",
            "dnd5e:creature",
            label="Creature",
            evidence_ref_id="ev:creature",
        ),
    ]
    stored = _stored_revision(
        _graph_payload(nodes=nodes, relationships=[], evidence_refs=ev)
    )
    envelope = _resource_for("statblock:creature", {"name": "Creature"})
    with pytest.raises(DndWorldObjectMechanicsHydrationError) as exc:
        derive_world_object_mechanics_binding(
            "obj:creature",
            envelope.resource_ref,
            graph_revision=stored,
            graph_reader=_reader(),
        )
    assert exc.value.details["reason"] == "object_kind_not_eligible"


def test_forged_binding_id_rejected() -> None:
    stored = _stored_revision(_fixture_a_graph())
    envelope = _resource_for("statblock:threat-a", {"name": "Threat A"})
    binding = derive_world_object_mechanics_binding(
        "obj:threat-a",
        envelope.resource_ref,
        graph_revision=stored,
        graph_reader=_reader(),
    )
    forged = binding.model_dump(mode="json")
    forged["binding_id"] = "mechbind:" + ("a" * 32)
    with pytest.raises(ValidationError):
        DndWorldObjectMechanicsBinding.model_validate(forged)


def test_graph_payload_digest_mismatch_rejects() -> None:
    stored = _stored_revision(_fixture_a_graph())
    envelope = _resource_for("statblock:threat-a", {"name": "Threat A"})
    mutated = StoredGraphRevision.model_validate(stored.model_dump(mode="json"))
    mutated.revision.graph_payload_sha256 = "0" * 64
    with pytest.raises(DndWorldObjectMechanicsHydrationError) as exc:
        derive_world_object_mechanics_binding(
            "obj:threat-a",
            envelope.resource_ref,
            graph_revision=mutated,
            graph_reader=_reader(),
        )
    assert exc.value.details["reason"] == "graph_payload_digest_mismatch"


def test_historical_b3a_path_unchanged() -> None:
    graph = json.loads(MATERIALIZED_GRAPH.read_text(encoding="utf-8"))
    resource = DndMechanicsResourceEnvelope.model_validate(
        json.loads(RESOURCE_FIXTURE.read_text(encoding="utf-8"))
    )
    expected = DndThreatMechanicsBinding.model_validate(
        json.loads(BINDING_FIXTURE.read_text(encoding="utf-8"))
    )
    stored = StoredGraphRevision(
        revision=WorldGraphRevision(
            world_id="world:synthetic-gatewatch",
            revision_id="rev:6e02bd224f6b5616534f10026c8b9679",
            parent_revision_id="rev:f2d5164c176289c5f3df7e68b4f0e46d",
            created_at=datetime(2026, 8, 1, 18, 0, tzinfo=UTC),
            operation_ids=["reviewop:11111111111111111111111111111111"],
            graph_schema="dm_union_graph_v3",
            graph_payload_sha256=(
                "75dd4d9f3425e6646d9141fde1ceea48d4574057bc0b5aada32b165de978adc5"
            ),
        ),
        graph_payload=graph,
    )
    descriptor = SemanticProfileDescriptor.model_validate_json(V2_PATH.read_text())
    reader = UnionGraphV3SnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([descriptor])
    )
    binding = derive_threat_mechanics_binding(
        "obj:48e170969a2bb3980e437f7430b7b1c1",
        resource.resource_ref,
        graph_revision=stored,
        graph_reader=reader,
    )
    assert binding.model_dump(mode="json") == expected.model_dump(mode="json")
    hydration = hydrate_threat_mechanics(
        binding,
        admissibility=Admissibility.GM,
        graph_revision=stored,
        graph_reader=reader,
        resource_resolver=_Resolver({resource.resource_ref.resource_id: resource}),
    )
    assert hydration.mechanics_payload_sha256 == resource.resource_ref.payload_sha256


def test_binding_id_derivation_is_stable() -> None:
    stored = _stored_revision(_fixture_a_graph())
    envelope = _resource_for("statblock:threat-a", {"name": "Threat A"})
    binding = derive_world_object_mechanics_binding(
        "obj:threat-a",
        envelope.resource_ref,
        graph_revision=stored,
        graph_reader=_reader(),
    )
    recomputed = derive_world_object_mechanics_binding_id(
        world_id=binding.world_id,
        graph_revision_id=binding.graph_revision_id,
        graph_payload_sha256=binding.graph_payload_sha256,
        semantic_profile=binding.semantic_profile,
        world_object_vocabulary=binding.world_object_vocabulary,
        object_id=binding.object_id,
        object_kind=binding.object_kind,
        visibility=binding.visibility,
        resource_ref=binding.resource_ref,
    )
    assert recomputed == binding.binding_id


def test_world_object_vocabulary_file_digest_pin() -> None:
    catalog = load_builtin_world_object_vocabulary()
    from_disk = json.loads(WORLD_OBJECT_VOCAB_PATH.read_text(encoding="utf-8"))
    assert from_disk["vocabulary_revision"] == "world-object-v1"
    assert vocabulary_sha256(catalog) == WORLD_OBJECT_VOCAB_DIGEST
