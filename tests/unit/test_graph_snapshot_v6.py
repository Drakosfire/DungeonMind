"""Parse and admission proofs for ``dm_union_graph_v6``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V5,
    GRAPH_SCHEMA_V6,
    RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
    VersionedUnionGraphSnapshotReader,
    effective_endpoint_kind,
)
from dungeonmind.application.graph_snapshot_v5 import UnionGraphV5SnapshotReader
from dungeonmind.application.graph_snapshot_v6 import UnionGraphV6SnapshotReader
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry

WORLD_ID = "world:union-graph-v6"
CAMPAIGN_ID = "camp:union-graph-v6"
DESCRIPTOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "semantic_profiles"
    / "test-kernel-v1.json"
)


def _descriptor() -> SemanticProfileDescriptor:
    return SemanticProfileDescriptor.model_validate(
        json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    )


def _registry() -> StaticSemanticProfileRegistry:
    return StaticSemanticProfileRegistry([_descriptor()])


def _profile_ref() -> dict[str, Any]:
    descriptor = _descriptor()
    return {
        "schema_version": "dm_semantic_profile_ref_v1",
        "profile_id": descriptor.profile_id,
        "profile_revision": descriptor.profile_revision,
        "descriptor_sha256": descriptor_sha256(descriptor),
    }


def _meta(assertion_id: str, *, evidence: tuple[str, ...] = ("ev:v6",)) -> dict[str, Any]:
    return {
        "schema_version": "dm_knowledge_assertion_metadata_v1",
        "assertion_id": assertion_id,
        "campaign_scope": CAMPAIGN_ID,
        "visibility": "player",
        "epistemic_kind": "asserted",
        "canon_state": "canonical",
        "evidence_ref_ids": list(evidence),
        "session_refs": [],
        "temporal_scope": {"schema_version": "dm_temporal_scope_ref_v1", "kind": "unknown"},
    }


def _evidence_v2_row() -> dict[str, Any]:
    return {
        "schema_version": "dm_evidence_ref_v2",
        "evidence_ref_id": "ev:v6",
        "source_artifact_id": "src:v6-notes",
        "source_revision_id": "srcrev:v6-notes-v1",
        "source_domain_key": "buddy.worldbuilding",
        "source_domain": "worldbuilding",
        "evidence_role": "support",
        "can_open_source": True,
        "can_highlight_span": False,
        "session_id": None,
        "source_span_ref_id": None,
        "locator": "fixture://v6-notes#college",
        "uri": None,
        "source_locator": None,
        "line_ref": None,
    }


def _v6_payload() -> dict[str, Any]:
    return {
        "world_id": WORLD_ID,
        "semantic_profile": _profile_ref(),
        "relationship_endpoint_aspect_schema": RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
        "objects": [
            {
                "object_id": "obj:college",
                "kind": "test:location",
                "label": "Wizard College",
                "assertion_metadata": _meta("asrt:college-exists"),
                "aliases": [],
                "summary": None,
                "properties": [],
                "aspects": [
                    {
                        "aspect_key": "organization",
                        "kind": "test:faction",
                        "assertion_metadata": _meta("asrt:college-org"),
                    }
                ],
            },
            {
                "object_id": "obj:headmaster",
                "kind": "test:person",
                "label": "Headmaster",
                "assertion_metadata": _meta("asrt:headmaster-exists"),
                "aliases": [],
                "summary": None,
                "properties": [],
                "aspects": [],
            },
            {
                "object_id": "obj:other",
                "kind": "test:person",
                "label": "Other",
                "assertion_metadata": _meta("asrt:other-exists"),
                "aliases": [],
                "summary": None,
                "properties": [],
                "aspects": [
                    {
                        "aspect_key": "site",
                        "kind": "test:location",
                        "assertion_metadata": _meta("asrt:other-site"),
                    }
                ],
            },
        ],
        "relationships": [
            {
                "relationship_id": "rel:leads",
                "source_object_id": "obj:headmaster",
                "target_object_id": "obj:college",
                "predicate": "test:leads",
                "assertion_metadata": _meta("asrt:leads"),
                "source_aspect_assertion_id": None,
                "target_aspect_assertion_id": "asrt:college-org",
            },
            {
                "relationship_id": "rel:travels",
                "source_object_id": "obj:headmaster",
                "target_object_id": "obj:college",
                "predicate": "test:travels_to",
                "assertion_metadata": _meta("asrt:travels"),
            },
        ],
        "evidence_refs": [_evidence_v2_row()],
    }


def _parse(payload: dict[str, Any] | None = None):
    return UnionGraphV6SnapshotReader(_registry()).parse(
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload=payload or _v6_payload(),
    )


def test_valid_aspect_assertion_parses() -> None:
    snapshot = _parse()
    obj = snapshot.objects["obj:college"]
    assert obj.kind == "test:location"
    assert len(obj.admitted_aspect_assertions) == 1
    aspect = obj.admitted_aspect_assertions[0]
    assert aspect.aspect_key == "organization"
    assert aspect.kind == "test:faction"
    assert aspect.assertion_id == "asrt:college-org"
    dumped = obj.model_dump()
    assert "admitted_aspect_assertions" not in dumped
    assert "aspects" not in dumped


def test_exact_endpoint_selection_resolves_aspect_kind() -> None:
    snapshot = _parse()
    leads = snapshot.relationships["rel:leads"]
    assert effective_endpoint_kind(leads, endpoint="source", snapshot=snapshot) == "test:person"
    assert effective_endpoint_kind(leads, endpoint="target", snapshot=snapshot) == "test:faction"


def test_missing_aspect_assertion_refuses() -> None:
    payload = _v6_payload()
    payload["relationships"][0]["target_aspect_assertion_id"] = "asrt:missing"
    with pytest.raises(PersistenceIntegrityError, match="does not exist") as exc:
        _parse(payload)
    rendered = str(exc.value) + str(exc.value.details)
    assert "asrt:missing" not in rendered
    assert "asrt:college-org" not in rendered


def test_wrong_owner_aspect_refuses() -> None:
    payload = _v6_payload()
    payload["relationships"][0]["target_aspect_assertion_id"] = "asrt:other-site"
    with pytest.raises(PersistenceIntegrityError, match="does not belong"):
        _parse(payload)


def test_aspect_assertion_id_collision_refuses() -> None:
    payload = _v6_payload()
    payload["objects"][0]["aspects"][0]["assertion_metadata"] = _meta("asrt:leads")
    with pytest.raises(PersistenceIntegrityError, match="duplicate assertion_id"):
        _parse(payload)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda p: p["objects"][0]["aspects"][0].__setitem__("aspect_key", ""),
        lambda p: p["objects"][0]["aspects"][0].__setitem__("kind", ""),
        lambda p: p["objects"][0]["aspects"][0].__setitem__("kind", "faction"),
    ],
)
def test_malformed_aspect_refuses(mutator) -> None:
    payload = _v6_payload()
    mutator(payload)
    with pytest.raises(PersistenceIntegrityError):
        _parse(payload)


def test_v6_discriminator_required() -> None:
    payload = _v6_payload()
    del payload["relationship_endpoint_aspect_schema"]
    with pytest.raises(PersistenceIntegrityError, match="relationship_endpoint_aspect_schema"):
        _parse(payload)
    payload = _v6_payload()
    payload["relationship_endpoint_aspect_schema"] = "dm_relationship_endpoint_aspect_v0"
    with pytest.raises(PersistenceIntegrityError):
        _parse(payload)


def test_v5_relabel_without_discriminator_refuses() -> None:
    payload = {
        "world_id": WORLD_ID,
        "semantic_profile": _profile_ref(),
        "objects": [
            {
                "object_id": "obj:college",
                "kind": "test:location",
                "label": "Wizard College",
                "assertion_metadata": _meta("asrt:college-exists"),
                "aliases": [],
                "summary": None,
                "properties": [],
            }
        ],
        "relationships": [],
        "evidence_refs": [_evidence_v2_row()],
    }
    with pytest.raises(PersistenceIntegrityError, match="relationship_endpoint_aspect_schema"):
        UnionGraphV6SnapshotReader(_registry()).parse(
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=payload,
        )


def test_v5_reader_rejects_v6_only_shape() -> None:
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV5SnapshotReader(_registry()).parse(
            graph_schema=GRAPH_SCHEMA_V5,
            graph_payload=_v6_payload(),
        )


def test_primary_kind_fallback_without_aspect_ref() -> None:
    snapshot = _parse()
    travels = snapshot.relationships["rel:travels"]
    assert travels.target_aspect_assertion_id is None
    assert effective_endpoint_kind(travels, endpoint="target", snapshot=snapshot) == "test:location"
    dumped = travels.model_dump()
    assert "source_aspect_assertion_id" not in dumped
    assert "target_aspect_assertion_id" not in dumped


def test_versioned_reader_dispatches_v6() -> None:
    snapshot = VersionedUnionGraphSnapshotReader(_registry()).parse(
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload=_v6_payload(),
    )
    assert snapshot.graph_schema == GRAPH_SCHEMA_V6
    assert snapshot.objects["obj:college"].object_field_schema == "v6"
