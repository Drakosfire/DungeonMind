"""PostgreSQL roundtrip for ``dm_union_graph_v5`` payloads."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V5
from dungeonmind.application.graph_snapshot_v5 import UnionGraphV5SnapshotReader
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts import PublishRevisionCommand
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from tests.conftest import FIXED_NOW

WORLD_ID = "world:v5-roundtrip"
CAMPAIGN_ID = "camp:v5-roundtrip"
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
        "evidence_ref_ids": ["ev:roundtrip-v5"],
        "session_refs": [],
        "temporal_scope": {
            "schema_version": "dm_temporal_scope_ref_v1",
            "kind": "unknown",
        },
    }


def _v5_payload() -> dict[str, Any]:
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
                    "aliases": [],
                    "summary": None,
                    "properties": [],
                }
            ],
            "relationships": [],
            "evidence_refs": [
                {
                    "schema_version": "dm_evidence_ref_v2",
                    "evidence_ref_id": "ev:roundtrip-v5",
                    "source_artifact_id": "src:roundtrip-v5",
                    "source_revision_id": "srcrev:roundtrip-v5-v1",
                    "source_domain_key": "buddy.worldbuilding",
                    "source_domain": "worldbuilding",
                    "evidence_role": "support",
                    "can_open_source": True,
                    "can_highlight_span": False,
                    "session_id": None,
                    "source_span_ref_id": None,
                    "locator": "fixture://v5-roundtrip/notes",
                    "uri": None,
                    "source_locator": None,
                    "line_ref": None,
                }
            ],
        }
    )


@pytest.mark.integration
def test_v5_payload_survives_publish_and_read_unchanged(pg) -> None:
    payload = _v5_payload()
    published = pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["op:v5-roundtrip"],
            graph_schema=GRAPH_SCHEMA_V5,
            graph_payload=payload,
            created_at=FIXED_NOW,
        )
    )
    stored = pg.world_graph.get_revision(WORLD_ID, published.revision_id)
    assert stored is not None
    assert stored.graph_payload == payload

    registry = StaticSemanticProfileRegistry([_descriptor()])
    snapshot = UnionGraphV5SnapshotReader(registry).parse(
        graph_schema=GRAPH_SCHEMA_V5,
        graph_payload=stored.graph_payload,
    )
    assert snapshot.objects["obj:person-quill"].label == "Quill"
    assert "ev:roundtrip-v5" in snapshot.evidence
