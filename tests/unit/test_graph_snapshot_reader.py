"""Unit tests for the ``dm_union_graph_v1`` snapshot reader."""

import pytest

from dungeonmind.application.graph_snapshot import (
    UnionGraphV1SnapshotReader,
    collect_one_hop_object_ids,
)
from dungeonmind.contracts.identity import IdentityOutcome
from dungeonmind.domain.errors import PersistenceIntegrityError

READER = UnionGraphV1SnapshotReader()


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "world_id": "world:demo-atlas",
        "nodes": [
            {
                "object_id": "obj:city-vael",
                "kind": "location",
                "label": "Vael",
                "aliases": ["Vael City"],
                "evidence_ref_ids": ["ev:vael"],
            },
            {
                "object_id": "obj:npc-mere-astor",
                "kind": "npc",
                "label": "Mere Astor",
                "aliases": ["Astor"],
                "evidence_ref_ids": ["ev:astor"],
            },
            {
                "object_id": "obj:item-sun-ledger",
                "kind": "artifact",
                "label": "The Sun Ledger",
                "aliases": [],
                "evidence_ref_ids": ["ev:ledger"],
            },
        ],
        "relationships": [
            {
                "relationship_id": "rel:astor-resides-vael",
                "subject_object_id": "obj:npc-mere-astor",
                "predicate": "resides_in",
                "object_object_id": "obj:city-vael",
                "evidence_ref_ids": ["ev:astor-vael"],
            },
            {
                "relationship_id": "rel:astor-safeguards-ledger",
                "subject_object_id": "obj:npc-mere-astor",
                "predicate": "safeguards",
                "object_object_id": "obj:item-sun-ledger",
                "evidence_ref_ids": ["ev:astor-ledger"],
            },
        ],
        "evidence_refs": [
            {
                "evidence_ref_id": "ev:vael",
                "source_artifact_id": "src:atlas-notes",
                "source_revision_id": "srcrev:atlas-notes-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
                "can_open_source": True,
                "locator": "fixture://atlas-notes#vael",
            },
            {
                "evidence_ref_id": "ev:astor",
                "source_artifact_id": "src:atlas-notes",
                "source_revision_id": "srcrev:atlas-notes-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
                "can_open_source": True,
                "locator": "fixture://atlas-notes#astor",
            },
            {
                "evidence_ref_id": "ev:ledger",
                "source_artifact_id": "src:atlas-notes",
                "source_revision_id": "srcrev:atlas-notes-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
                "can_open_source": True,
                "locator": "fixture://atlas-notes#sun-ledger",
            },
            {
                "evidence_ref_id": "ev:astor-vael",
                "source_artifact_id": "src:atlas-notes",
                "source_revision_id": "srcrev:atlas-notes-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
                "can_open_source": True,
                "locator": "fixture://atlas-notes#astor-vael",
            },
            {
                "evidence_ref_id": "ev:astor-ledger",
                "source_artifact_id": "src:atlas-notes",
                "source_revision_id": "srcrev:atlas-notes-v1",
                "source_domain": "worldbuilding",
                "evidence_role": "support",
                "can_open_source": True,
                "locator": "fixture://atlas-notes#astor-ledger",
            },
        ],
    }
    base.update(overrides)
    return base


def test_supported_schema_parses() -> None:
    snapshot = READER.parse(graph_schema="dm_union_graph_v1", graph_payload=_payload())
    assert snapshot.world_id == "world:demo-atlas"
    assert "obj:npc-mere-astor" in snapshot.objects
    assert "rel:astor-safeguards-ledger" in snapshot.relationships
    assert "ev:astor-ledger" in snapshot.evidence


def test_unsupported_schema_rejects() -> None:
    with pytest.raises(PersistenceIntegrityError, match="unsupported graph schema"):
        READER.parse(graph_schema="dm_other_v1", graph_payload=_payload())


def test_duplicate_object_rejects() -> None:
    payload = _payload()
    nodes = list(payload["nodes"])  # type: ignore[arg-type]
    nodes.append(dict(nodes[0]))
    payload["nodes"] = nodes
    with pytest.raises(PersistenceIntegrityError, match="duplicate object_id"):
        READER.parse(graph_schema="dm_union_graph_v1", graph_payload=payload)


def test_duplicate_alias_reports_ambiguity() -> None:
    payload = _payload()
    nodes = list(payload["nodes"])  # type: ignore[arg-type]
    nodes[0] = {**nodes[0], "aliases": ["Shared"]}
    nodes[1] = {**nodes[1], "aliases": ["Shared"]}
    payload["nodes"] = nodes
    snapshot = READER.parse(graph_schema="dm_union_graph_v1", graph_payload=payload)
    referents = READER.resolve_mentions(
        snapshot,
        message="Tell me about Shared",
        selected_object_ids=[],
    )
    ambiguous = [r for r in referents if r.outcome is IdentityOutcome.AMBIGUOUS]
    assert ambiguous
    assert ambiguous[0].object_id is None


def test_dangling_relationship_rejects() -> None:
    payload = _payload()
    relationships = list(payload["relationships"])  # type: ignore[arg-type]
    relationships[0] = {
        **relationships[0],
        "object_object_id": "obj:missing",
    }
    payload["relationships"] = relationships
    with pytest.raises(PersistenceIntegrityError, match="dangling relationship object"):
        READER.parse(graph_schema="dm_union_graph_v1", graph_payload=payload)


def test_dangling_evidence_rejects() -> None:
    payload = _payload()
    nodes = list(payload["nodes"])  # type: ignore[arg-type]
    nodes[0] = {**nodes[0], "evidence_ref_ids": ["ev:missing"]}
    payload["nodes"] = nodes
    with pytest.raises(PersistenceIntegrityError, match="dangling node evidence"):
        READER.parse(graph_schema="dm_union_graph_v1", graph_payload=payload)


def test_exact_object_id_resolves() -> None:
    snapshot = READER.parse(graph_schema="dm_union_graph_v1", graph_payload=_payload())
    referents = READER.resolve_mentions(
        snapshot,
        message="Describe obj:npc-mere-astor please",
        selected_object_ids=[],
    )
    assert any(
        r.object_id == "obj:npc-mere-astor" and r.outcome is IdentityOutcome.RESOLVED_EXISTING
        for r in referents
    )


def test_label_resolves_case_insensitively() -> None:
    snapshot = READER.parse(graph_schema="dm_union_graph_v1", graph_payload=_payload())
    referents = READER.resolve_mentions(
        snapshot,
        message="where does mere astor live?",
        selected_object_ids=[],
    )
    assert any(
        r.object_id == "obj:npc-mere-astor" and r.outcome is IdentityOutcome.RESOLVED_EXISTING
        for r in referents
    )


def test_alias_resolves_case_insensitively() -> None:
    snapshot = READER.parse(graph_schema="dm_union_graph_v1", graph_payload=_payload())
    referents = READER.resolve_mentions(
        snapshot,
        message="Who is ASTOR?",
        selected_object_ids=[],
    )
    assert any(
        r.object_id == "obj:npc-mere-astor" and r.outcome is IdentityOutcome.RESOLVED_EXISTING
        for r in referents
    )


def test_one_hop_traversal_is_deterministic() -> None:
    snapshot = READER.parse(graph_schema="dm_union_graph_v1", graph_payload=_payload())
    first = READER.list_relationships(snapshot, ["obj:npc-mere-astor"])
    second = READER.list_relationships(snapshot, ["obj:npc-mere-astor"])
    assert [r.relationship_id for r in first] == [r.relationship_id for r in second]
    assert [r.relationship_id for r in first] == sorted(r.relationship_id for r in first)


def test_traversal_never_exceeds_one_hop() -> None:
    snapshot = READER.parse(graph_schema="dm_union_graph_v1", graph_payload=_payload())
    expanded = collect_one_hop_object_ids(snapshot, ["obj:item-sun-ledger"])
    # Ledger ↔ Astor is one hop; Vael is two hops from the ledger and must stay out.
    assert expanded == ["obj:item-sun-ledger", "obj:npc-mere-astor"]
