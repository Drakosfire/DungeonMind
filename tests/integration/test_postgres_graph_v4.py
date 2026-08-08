"""PostgreSQL roundtrip for ``dm_union_graph_v4`` payloads.

The store is schema-agnostic (payloads are canonical JSON), so the proof here
is that a v4 payload survives publish → read byte-for-byte *and* that the read
payload still parses under the v4 reader with its assertion metadata intact.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V4
from dungeonmind.application.graph_snapshot_v4 import UnionGraphV4SnapshotReader
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts import PublishRevisionCommand
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from tests.conftest import FIXED_NOW

WORLD_ID = "world:v4-roundtrip"
CAMPAIGN_ID = "camp:v4-roundtrip"
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


def _meta(assertion_id: str, *, campaign_scope: str | None = CAMPAIGN_ID) -> dict[str, Any]:
    return {
        "schema_version": "dm_knowledge_assertion_metadata_v1",
        "assertion_id": assertion_id,
        "campaign_scope": campaign_scope,
        "visibility": "player",
        "epistemic_kind": "source_derived_candidate",
        "canon_state": "provisional",
        "evidence_ref_ids": ["ev:roundtrip"],
        "session_refs": ["ses:0011"],
        "temporal_scope": {
            "schema_version": "dm_temporal_scope_ref_v1",
            "kind": "fictional_time_ref",
            "fictional_time_ref": "ftime:anchor-roundtrip",
        },
    }


def _v4_payload() -> dict[str, Any]:
    descriptor = _descriptor()
    return copy.deepcopy(
        {
            "world_id": WORLD_ID,
            "semantic_profile": {
                "schema_version": "dm_semantic_profile_ref_v1",
                "profile_id": descriptor.profile_id,
                "profile_revision": descriptor.profile_revision,
                "descriptor_sha256": descriptor_sha256(descriptor),
            },
            "objects": [
                {
                    "object_id": "obj:person-quill",
                    "kind": "test:person",
                    "label": "Quill",
                    "assertion_metadata": _meta("asrt:quill-exists"),
                    "aliases": [
                        {
                            "value": "Quill the Scribe",
                            "assertion_metadata": _meta("asrt:quill-alias"),
                        }
                    ],
                    "summary": {
                        "value": "a public archivist of the low ward",
                        "assertion_metadata": _meta("asrt:quill-summary"),
                    },
                    "properties": [
                        {
                            "property_term": "test:role",
                            "value": {"name": "archivist", "tenure": 4, "active": True},
                            "assertion_metadata": _meta("asrt:quill-role"),
                        }
                    ],
                },
                {
                    "object_id": "obj:place-low-ward",
                    "kind": "test:place",
                    "label": "Low Ward",
                    "assertion_metadata": _meta(
                        "asrt:ward-exists", campaign_scope=None
                    ),
                    "aliases": [],
                    "summary": None,
                    "properties": [],
                },
            ],
            "relationships": [
                {
                    "relationship_id": "rel:quill-in-ward",
                    "source_object_id": "obj:person-quill",
                    "target_object_id": "obj:place-low-ward",
                    "predicate": "test:located_in",
                    "assertion_metadata": _meta("asrt:rel-quill-ward"),
                }
            ],
            "evidence_refs": [
                {
                    "schema_version": "dm_evidence_ref_v1",
                    "evidence_ref_id": "ev:roundtrip",
                    "source_artifact_id": "src:roundtrip-notes",
                    "source_revision_id": "srcrev:roundtrip-notes-v1",
                    "source_domain": "worldbuilding",
                    "evidence_role": "support",
                    "can_open_source": True,
                    "locator": "fixture://v4-roundtrip/notes",
                }
            ],
        }
    )


@pytest.mark.integration
def test_v4_payload_survives_publish_and_read_unchanged(pg) -> None:
    payload = _v4_payload()
    published = pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["op:v4-roundtrip"],
            graph_schema=GRAPH_SCHEMA_V4,
            graph_payload=payload,
            created_at=FIXED_NOW,
        )
    )

    stored = pg.world_graph.get_revision(WORLD_ID, published.revision_id)
    assert stored is not None
    assert stored.revision.graph_schema == GRAPH_SCHEMA_V4
    assert stored.graph_payload == payload

    reader = UnionGraphV4SnapshotReader(StaticSemanticProfileRegistry([_descriptor()]))
    snapshot = reader.parse(
        graph_schema=stored.revision.graph_schema,
        graph_payload=stored.graph_payload,
    )
    quill = snapshot.objects["obj:person-quill"]
    assert quill.existence_assertion_metadata is not None
    assert quill.existence_assertion_metadata.assertion_id == "asrt:quill-exists"
    assert quill.aliases == ["Quill the Scribe"]
    assert quill.admitted_property_assertions[0].value == {
        "name": "archivist",
        "tenure": 4,
        "active": True,
    }
    edge = snapshot.relationships["rel:quill-in-ward"]
    assert edge.assertion_metadata is not None
    assert (
        edge.assertion_metadata.temporal_scope.fictional_time_ref
        == "ftime:anchor-roundtrip"
    )
