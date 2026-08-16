"""Scoped projection proofs for ``dm_union_graph_v6`` aspect assertions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dungeonmind.application.graph_scope import (
    project_scoped_snapshot,
    public_coverage_gaps_for_exclusion,
)
from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V6,
    RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
)
from dungeonmind.application.graph_snapshot_v6 import UnionGraphV6SnapshotReader
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
from dungeonmind.infrastructure.memory import InMemorySourceRepository
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry

FIXED_NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
WORLD_ID = "world:union-graph-v6-scope"
CAMPAIGN_ID = "camp:union-graph-v6-scope"
OTHER_CAMPAIGN_ID = "camp:other-v6-scope"
DESCRIPTOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "semantic_profiles"
    / "test-kernel-v1.json"
)
HIDDEN_ASPECT_ID = "asrt:college-org"


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


def _meta(
    assertion_id: str,
    *,
    evidence: tuple[str, ...] = ("ev:v6",),
    visibility: str = "player",
    campaign_scope: str | None = CAMPAIGN_ID,
) -> dict[str, Any]:
    return {
        "schema_version": "dm_knowledge_assertion_metadata_v1",
        "assertion_id": assertion_id,
        "campaign_scope": campaign_scope,
        "visibility": visibility,
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


def _payload(
    *,
    aspect_visibility: str = "player",
    aspect_campaign: str | None = CAMPAIGN_ID,
    existence_visibility: str = "player",
    relationship_visibility: str = "player",
    extra_hidden_aspect: bool = False,
) -> dict[str, Any]:
    aspects = [
        {
            "aspect_key": "organization",
            "kind": "test:faction",
            "assertion_metadata": _meta(
                HIDDEN_ASPECT_ID,
                visibility=aspect_visibility,
                campaign_scope=aspect_campaign,
            ),
        }
    ]
    if extra_hidden_aspect:
        aspects.append(
            {
                "aspect_key": "secret-hall",
                "kind": "test:location",
                "assertion_metadata": _meta(
                    "asrt:college-secret",
                    visibility="gm",
                ),
            }
        )
    return {
        "world_id": WORLD_ID,
        "semantic_profile": _profile_ref(),
        "relationship_endpoint_aspect_schema": RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
        "objects": [
            {
                "object_id": "obj:college",
                "kind": "test:location",
                "label": "Wizard College",
                "assertion_metadata": _meta(
                    "asrt:college-exists",
                    visibility=existence_visibility,
                ),
                "aliases": [],
                "summary": None,
                "properties": [],
                "aspects": aspects,
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
        ],
        "relationships": [
            {
                "relationship_id": "rel:leads",
                "source_object_id": "obj:headmaster",
                "target_object_id": "obj:college",
                "predicate": "test:leads",
                "assertion_metadata": _meta(
                    "asrt:leads",
                    visibility=relationship_visibility,
                ),
                "source_aspect_assertion_id": None,
                "target_aspect_assertion_id": HIDDEN_ASPECT_ID,
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


def _seed_sources() -> InMemorySourceRepository:
    sources = InMemorySourceRepository()
    sources.put_artifact(
        SourceArtifactV2(
            source_artifact_id="src:v6-notes",
            source_domain_key="buddy.worldbuilding",
            source_domain=SourceDomain.WORLDBUILDING,
            world_id=WORLD_ID,
            campaign_id=CAMPAIGN_ID,
            session_id=None,
            uri=None,
            current_revision_id="srcrev:v6-notes-v1",
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
            source_revision_id="srcrev:v6-notes-v1",
            source_artifact_id="src:v6-notes",
            content_sha256="cc" * 32,
            body_storage="external",
            locator="fixture://v6-notes",
            created_at=FIXED_NOW,
        )
    )
    return sources


def _project(payload: dict[str, Any], *, admissibility: Admissibility = Admissibility.PLAYER):
    snapshot = UnionGraphV6SnapshotReader(_registry()).parse(
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload=payload,
    )
    return project_scoped_snapshot(
        snapshot,
        sources=_seed_sources(),
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        admissibility=admissibility,
    )


def _public_text(projection) -> str:
    dumped = []
    for obj in projection.snapshot.objects.values():
        dumped.append(obj.model_dump(mode="json"))
    for rel in projection.snapshot.relationships.values():
        dumped.append(rel.model_dump(mode="json"))
    for exclusion in (
        *projection.object_exclusions.values(),
        *projection.relationship_exclusions.values(),
    ):
        dumped.append(list(public_coverage_gaps_for_exclusion(exclusion)))
    return json.dumps(dumped)


def test_visible_relationship_and_aspect_traverse() -> None:
    scoped = _project(_payload())
    assert "rel:leads" in scoped.snapshot.relationships
    assert "rel:travels" in scoped.snapshot.relationships
    college = scoped.snapshot.objects["obj:college"]
    assert [item.assertion_id for item in college.admitted_aspect_assertions] == [
        HIDDEN_ASPECT_ID
    ]


def test_hidden_relationship_stays_hidden() -> None:
    scoped = _project(_payload(relationship_visibility="gm"))
    assert "rel:leads" not in scoped.snapshot.relationships
    assert "rel:travels" in scoped.snapshot.relationships
    college = scoped.snapshot.objects["obj:college"]
    assert any(item.assertion_id == HIDDEN_ASPECT_ID for item in college.admitted_aspect_assertions)


def test_hidden_referenced_aspect_hides_that_relationship() -> None:
    scoped = _project(_payload(aspect_visibility="gm"))
    assert "rel:leads" not in scoped.snapshot.relationships
    assert scoped.relationship_exclusions["rel:leads"].out_of_scope is True
    assert "rel:travels" in scoped.snapshot.relationships
    college = scoped.snapshot.objects["obj:college"]
    assert college.admitted_aspect_assertions == []


def test_hidden_object_existence_hides_object_aspects_and_relationships() -> None:
    scoped = _project(_payload(existence_visibility="gm"))
    assert "obj:college" not in scoped.snapshot.objects
    assert "rel:leads" not in scoped.snapshot.relationships
    assert "rel:travels" not in scoped.snapshot.relationships


def test_unrelated_hidden_aspect_does_not_hide_primary_sense_relationship() -> None:
    scoped = _project(_payload(extra_hidden_aspect=True))
    assert "rel:travels" in scoped.snapshot.relationships
    assert "rel:leads" in scoped.snapshot.relationships
    college = scoped.snapshot.objects["obj:college"]
    assert [item.assertion_id for item in college.admitted_aspect_assertions] == [
        HIDDEN_ASPECT_ID
    ]
    public = _public_text(scoped)
    assert "asrt:college-secret" not in public


def test_campaign_specific_aspect_is_omitted_from_other_campaign_read() -> None:
    scoped = _project(_payload(aspect_campaign=OTHER_CAMPAIGN_ID))
    assert "rel:leads" not in scoped.snapshot.relationships
    assert "rel:travels" in scoped.snapshot.relationships
    assert scoped.snapshot.objects["obj:college"].admitted_aspect_assertions == []


def test_visibility_specific_aspect_is_gm_only() -> None:
    player = _project(_payload(aspect_visibility="gm"), admissibility=Admissibility.PLAYER)
    gm = _project(_payload(aspect_visibility="gm"), admissibility=Admissibility.GM)
    assert "rel:leads" not in player.snapshot.relationships
    assert "rel:leads" in gm.snapshot.relationships
    assert player.snapshot.objects["obj:college"].admitted_aspect_assertions == []
    assert gm.snapshot.objects["obj:college"].admitted_aspect_assertions


def test_public_dumps_do_not_leak_hidden_aspect_assertion_ids() -> None:
    scoped = _project(_payload(aspect_visibility="gm"))
    public = _public_text(scoped)
    assert HIDDEN_ASPECT_ID not in public
    codes, missing = public_coverage_gaps_for_exclusion(
        scoped.relationship_exclusions["rel:leads"]
    )
    assert codes == []
    assert missing == []
    for obj in scoped.snapshot.objects.values():
        dumped = obj.model_dump()
        assert "admitted_aspect_assertions" not in dumped
    for rel in scoped.snapshot.relationships.values():
        dumped = rel.model_dump()
        assert "target_aspect_assertion_id" not in dumped
        assert "source_aspect_assertion_id" not in dumped
