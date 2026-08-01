"""V3 graph parse/scope/terms plus v1/v2 regression for profile fields."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dungeonmind.application.graph_scope import project_scoped_snapshot
from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V1,
    GRAPH_SCHEMA_V2,
    GRAPH_SCHEMA_V3,
    UnionGraphV1SnapshotReader,
    UnionGraphV2SnapshotReader,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts.evidence import (
    SourceArtifact,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import (
    PersistenceIntegrityError,
    SemanticProfileNotFoundError,
    SemanticTermValidationError,
)
from dungeonmind.infrastructure.memory import InMemorySourceRepository
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "curated_semantic_profile_v1.json"
)
NARRATIVE_DESCRIPTOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "semantic_profiles"
    / "test-narrative-v1.json"
)
FIXED_NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _narrative_registry() -> StaticSemanticProfileRegistry:
    descriptor = SemanticProfileDescriptor.model_validate(
        json.loads(NARRATIVE_DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    )
    return StaticSemanticProfileRegistry([descriptor])


def _v3_payload() -> dict:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return copy.deepcopy(raw["graph_payload"])


def _seed_sources() -> InMemorySourceRepository:
    sources = InMemorySourceRepository()
    sources.put_artifact(
        SourceArtifact(
            source_artifact_id="src:narrative-player-notes",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id="world:semantic-profile-demo",
            campaign_id="camp:semantic-profile",
            current_revision_id="srcrev:narrative-player-notes-v1",
            authority="primary",
            visibility=Visibility.PLAYER,
            status=SourceStatus.ACTIVE,
            created_at=FIXED_NOW,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:narrative-player-notes-v1",
            source_artifact_id="src:narrative-player-notes",
            content_sha256="c" * 64,
            body_storage="external",
            locator="fixture://curated-semantic-profile-v1/player-notes",
            created_at=FIXED_NOW,
        )
    )
    return sources


def test_v3_parse_resolves_profile_and_admits_terms() -> None:
    reader = VersionedUnionGraphSnapshotReader(profile_registry=_narrative_registry())
    snapshot = reader.parse(graph_schema=GRAPH_SCHEMA_V3, graph_payload=_v3_payload())
    assert snapshot.semantic_profile_ref is not None
    assert snapshot.semantic_profile_descriptor is not None
    assert snapshot.semantic_profile_ref.profile_id == "test.narrative"
    assert snapshot.objects["obj:clock-buried-sun"].kind == "narrative:clock"
    assert (
        snapshot.relationships["rel:clock-advances-outcome"].predicate
        == "narrative:advances_toward"
    )


def test_v3_scope_preserves_profile_fields() -> None:
    reader = VersionedUnionGraphSnapshotReader(profile_registry=_narrative_registry())
    snapshot = reader.parse(graph_schema=GRAPH_SCHEMA_V3, graph_payload=_v3_payload())
    scoped = project_scoped_snapshot(
        snapshot,
        sources=_seed_sources(),
        world_id="world:semantic-profile-demo",
        campaign_id="camp:semantic-profile",
        admissibility=Admissibility.PLAYER,
    )
    assert scoped.snapshot.semantic_profile_ref == snapshot.semantic_profile_ref
    assert (
        scoped.snapshot.semantic_profile_descriptor
        == snapshot.semantic_profile_descriptor
    )
    assert "obj:clock-buried-sun" in scoped.snapshot.objects


def test_v3_rejects_unadmitted_namespace() -> None:
    payload = _v3_payload()
    payload["nodes"][0]["kind"] = "dnd5e:creature"
    reader = VersionedUnionGraphSnapshotReader(profile_registry=_narrative_registry())
    with pytest.raises(SemanticTermValidationError):
        reader.parse(graph_schema=GRAPH_SCHEMA_V3, graph_payload=payload)


def test_v3_fails_closed_without_registry() -> None:
    reader = VersionedUnionGraphSnapshotReader()
    with pytest.raises(SemanticProfileNotFoundError):
        reader.parse(graph_schema=GRAPH_SCHEMA_V3, graph_payload=_v3_payload())


def test_v1_and_v2_reject_semantic_profile_field() -> None:
    v1_payload = {
        "world_id": "world:demo",
        "semantic_profile": {
            "schema_version": "dm_semantic_profile_ref_v1",
            "profile_id": "test.narrative",
            "profile_revision": "narrative-profile-v1",
            "descriptor_sha256": "0" * 64,
        },
        "nodes": [],
        "relationships": [],
        "evidence_refs": [],
    }
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV1SnapshotReader().parse(
            graph_schema=GRAPH_SCHEMA_V1, graph_payload=v1_payload
        )
    with pytest.raises(PersistenceIntegrityError):
        UnionGraphV2SnapshotReader().parse(
            graph_schema=GRAPH_SCHEMA_V2, graph_payload=v1_payload
        )


def test_v1_v2_parsed_snapshots_have_null_profile_fields() -> None:
    v1 = UnionGraphV1SnapshotReader().parse(
        graph_schema=GRAPH_SCHEMA_V1,
        graph_payload={
            "world_id": "world:demo",
            "nodes": [
                {
                    "object_id": "obj:a",
                    "kind": "location",
                    "label": "A",
                    "aliases": [],
                    "evidence_ref_ids": ["ev:a"],
                }
            ],
            "relationships": [],
            "evidence_refs": [
                {
                    "evidence_ref_id": "ev:a",
                    "source_artifact_id": "src:a",
                    "source_domain": "worldbuilding",
                    "evidence_role": "support",
                }
            ],
        },
    )
    assert v1.semantic_profile_ref is None
    assert v1.semantic_profile_descriptor is None

    v2 = UnionGraphV2SnapshotReader().parse(
        graph_schema=GRAPH_SCHEMA_V2,
        graph_payload={
            "world_id": "world:demo",
            "nodes": [
                {
                    "object_id": "obj:a",
                    "kind": "location",
                    "label": "A",
                    "evidence_ref_ids": ["ev:a"],
                    "alias_assertions": [],
                    "summary_assertion": None,
                }
            ],
            "relationships": [],
            "evidence_refs": [
                {
                    "evidence_ref_id": "ev:a",
                    "source_artifact_id": "src:a",
                    "source_domain": "worldbuilding",
                    "evidence_role": "support",
                }
            ],
        },
    )
    assert v2.semantic_profile_ref is None
    assert v2.semantic_profile_descriptor is None


def test_curated_fixture_digest_matches_descriptor() -> None:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    descriptor = SemanticProfileDescriptor.model_validate(
        json.loads(NARRATIVE_DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    )
    assert (
        raw["graph_payload"]["semantic_profile"]["descriptor_sha256"]
        == descriptor_sha256(descriptor)
    )
