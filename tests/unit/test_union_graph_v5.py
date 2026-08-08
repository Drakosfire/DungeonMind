"""Parse and admission proofs for ``dm_union_graph_v5``."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dungeonmind.application.graph_scope import project_scoped_snapshot
from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V4,
    GRAPH_SCHEMA_V5,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.graph_snapshot_v4 import UnionGraphV4SnapshotReader
from dungeonmind.application.graph_snapshot_v5 import UnionGraphV5SnapshotReader
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts.evidence import (
    SourceArtifactV2,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.memory import InMemorySourceRepository
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry

FIXED_NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
WORLD_ID = "world:union-graph-v5"
CAMPAIGN_ID = "camp:union-graph-v5"

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


def _meta(assertion_id: str, *, evidence: tuple[str, ...] = ("ev:v5",)) -> dict[str, Any]:
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


def _evidence_v2_row(
    evidence_ref_id: str = "ev:v5",
    source_artifact_id: str = "src:v5-notes",
) -> dict[str, Any]:
    return {
        "schema_version": "dm_evidence_ref_v2",
        "evidence_ref_id": evidence_ref_id,
        "source_artifact_id": source_artifact_id,
        "source_revision_id": "srcrev:v5-notes-v1",
        "source_domain_key": "buddy.worldbuilding",
        "source_domain": "worldbuilding",
        "evidence_role": "support",
        "can_open_source": True,
        "can_highlight_span": False,
        "session_id": None,
        "source_span_ref_id": None,
        "locator": "fixture://v5-notes#quill",
        "uri": None,
        "source_locator": None,
        "line_ref": None,
    }


def _v5_payload() -> dict[str, Any]:
    return {
        "world_id": WORLD_ID,
        "semantic_profile": _profile_ref(),
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
                    "value": "a public archivist",
                    "assertion_metadata": _meta("asrt:quill-summary"),
                },
                "properties": [],
            }
        ],
        "relationships": [],
        "evidence_refs": [_evidence_v2_row()],
    }


def _seed_v5_sources() -> InMemorySourceRepository:
    sources = InMemorySourceRepository()
    sources.put_artifact(
        SourceArtifactV2(
            source_artifact_id="src:v5-notes",
            source_domain_key="buddy.worldbuilding",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id=WORLD_ID,
            campaign_id=CAMPAIGN_ID,
            session_id=None,
            uri=None,
            current_revision_id="srcrev:v5-notes-v1",
            authority=None,
            visibility=Visibility.PLAYER,
            artifact_kind=None,
            document_class=None,
            review_state=None,
            source_visibility_state=None,
            workspace_document_ref=None,
            lineage={},
            status=SourceStatus.ACTIVE,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:v5-notes-v1",
            source_artifact_id="src:v5-notes",
            content_sha256="bb" * 32,
            body_storage="external",
            locator="fixture://v5-notes",
            created_at=FIXED_NOW,
        )
    )
    return sources


def test_v4_rejects_v2_evidence() -> None:
    payload = copy.deepcopy(_v5_payload())
    payload["evidence_refs"] = [_evidence_v2_row()]
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV4SnapshotReader(_registry()).parse(
            graph_schema=GRAPH_SCHEMA_V4,
            graph_payload=payload,
        )


def test_v5_rejects_v1_evidence() -> None:
    payload = copy.deepcopy(_v5_payload())
    payload["evidence_refs"] = [
        {
            "schema_version": "dm_evidence_ref_v1",
            "evidence_ref_id": "ev:v1",
            "source_artifact_id": "src:v5-notes",
            "source_revision_id": "srcrev:v5-notes-v1",
            "source_domain": "worldbuilding",
            "evidence_role": "support",
        }
    ]
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV5SnapshotReader(_registry()).parse(
            graph_schema=GRAPH_SCHEMA_V5,
            graph_payload=payload,
        )


def test_versioned_reader_dispatches_v5() -> None:
    reader = VersionedUnionGraphSnapshotReader(_registry())
    snapshot = reader.parse(graph_schema=GRAPH_SCHEMA_V5, graph_payload=_v5_payload())
    assert snapshot.graph_schema == GRAPH_SCHEMA_V5
    assert "obj:person-quill" in snapshot.objects


def test_v5_assertion_grain_admits_object_independently() -> None:
    payload = copy.deepcopy(_v5_payload())
    payload["objects"][0]["aliases"][0]["assertion_metadata"] = {
        **_meta("asrt:quill-alias-hidden"),
        "visibility": "gm",
    }
    snapshot = UnionGraphV5SnapshotReader(_registry()).parse(
        graph_schema=GRAPH_SCHEMA_V5,
        graph_payload=payload,
    )
    sources = _seed_v5_sources()
    scoped = project_scoped_snapshot(
        snapshot,
        sources=sources,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        admissibility=Admissibility.PLAYER,
    )
    obj = scoped.snapshot.objects["obj:person-quill"]
    assert obj.label == "Quill"
    assert obj.aliases == []
    assert obj.summary == "a public archivist"


@pytest.mark.parametrize(
    "omitted_key",
    [
        "source_revision_id",
        "source_domain",
        "evidence_role",
        "can_open_source",
        "can_highlight_span",
        "session_id",
        "source_span_ref_id",
        "locator",
        "uri",
        "source_locator",
        "line_ref",
        "source_domain_key",
        "source_artifact_id",
        "evidence_ref_id",
    ],
)
def test_v5_evidence_row_rejects_omitted_required_v2_keys(omitted_key: str) -> None:
    """Every required EvidenceRefV2 serialized key omitted from v5 fails closed."""
    row = _evidence_v2_row()
    del row[omitted_key]
    payload = copy.deepcopy(_v5_payload())
    payload["evidence_refs"] = [row]
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV5SnapshotReader(_registry()).parse(
            graph_schema=GRAPH_SCHEMA_V5,
            graph_payload=payload,
        )


def test_v5_minimal_three_field_evidence_row_rejected() -> None:
    payload = copy.deepcopy(_v5_payload())
    payload["evidence_refs"] = [
        {
            "evidence_ref_id": "ev:x",
            "source_artifact_id": "src:x",
            "source_domain_key": "producer:x",
        }
    ]
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV5SnapshotReader(_registry()).parse(
            graph_schema=GRAPH_SCHEMA_V5,
            graph_payload=payload,
        )
