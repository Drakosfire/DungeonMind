from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dungeonmind.application.eldyrwild_party_registry_provenance_repair import (
    ELDYRWILD_WORLD_ID,
    PARTY_REGISTRY_ARTIFACT_ID,
    PC_OBJECT_IDS,
    materialize_party_registry_provenance_repair,
    publish_party_registry_provenance_repair,
)
from dungeonmind.application.graph_snapshot import GRAPH_SCHEMA_V6
from dungeonmind.contracts.evidence import (
    SourceArtifactV2,
    SourceAuthority,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.graph import (
    PublishRevisionCommand,
    StoredGraphRevision,
    WorldGraphRevision,
)
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.memory import InMemorySourceRepository, InMemoryWorldGraphRepository

NOW = datetime(2026, 9, 22, tzinfo=UTC)
REVISION = "sha256:" + "a" * 64


def _metadata(evidence_id: str) -> dict[str, object]:
    return {
        "schema_version": "dm_knowledge_assertion_metadata_v1",
        "assertion_id": f"asrt:{evidence_id}",
        "campaign_scope": "longmont-c1",
        "visibility": "gm",
        "epistemic_kind": "asserted",
        "canon_state": "canonical",
        "evidence_ref_ids": [evidence_id],
        "session_refs": [],
        "temporal_scope": {"schema_version": "dm_temporal_scope_ref_v1", "kind": "unknown"},
    }


def _payload() -> dict[str, object]:
    evidence = []
    objects = []
    for object_id in PC_OBJECT_IDS:
        evidence_id = f"ev:{object_id}"
        objects.append(
            {
                "object_id": object_id,
                "kind": "dnd5e:player_character",
                "label": object_id,
                "assertion_metadata": _metadata(evidence_id),
                "aliases": [],
                "summary": None,
                "properties": [],
                "aspects": [],
            }
        )
        evidence.append(
            {
                "schema_version": "dm_evidence_ref_v2",
                "evidence_ref_id": evidence_id,
                "source_artifact_id": PARTY_REGISTRY_ARTIFACT_ID,
                "source_revision_id": REVISION,
                "source_domain_key": "other",
                "source_domain": "other",
                "evidence_role": "support",
                "can_open_source": False,
                "can_highlight_span": False,
                "session_id": None,
                "source_span_ref_id": None,
                "locator": None,
                "uri": None,
                "source_locator": None,
                "line_ref": None,
            }
        )
    return {
        "world_id": ELDYRWILD_WORLD_ID,
        "semantic_profile": {
            "schema_version": "dm_semantic_profile_ref_v1",
            "profile_id": "test.profile",
            "profile_revision": "v1",
            "descriptor_sha256": "0" * 64,
        },
        "relationship_endpoint_aspect_schema": "dm_relationship_endpoint_aspect_v1",
        "objects": objects,
        "relationships": [],
        "evidence_refs": evidence,
    }


def _sources() -> InMemorySourceRepository:
    sources = InMemorySourceRepository()
    sources.put_artifact(
        SourceArtifactV2(
            source_artifact_id=PARTY_REGISTRY_ARTIFACT_ID,
            source_domain_key="party_registry",
            source_domain=SourceDomain.OTHER,
            world_id=ELDYRWILD_WORLD_ID,
            campaign_id="longmont-c1",
            session_id=None,
            uri=None,
            current_revision_id=REVISION,
            authority=SourceAuthority.PRIMARY,
            visibility=Visibility.GM,
            artifact_kind="party_registry",
            document_class=None,
            review_state=None,
            source_visibility_state=None,
            workspace_document_ref=None,
            lineage={},
            status=SourceStatus.ACTIVE,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    sources.put_revision(
        SourceRevision(
            source_revision_id=REVISION,
            source_artifact_id=PARTY_REGISTRY_ARTIFACT_ID,
            content_sha256="b" * 64,
            body_storage="external",
            locator="fixture://party",
            created_at=NOW,
        )
    )
    return sources


def _parent(payload: dict[str, object] | None = None) -> StoredGraphRevision:
    body = payload or _payload()
    return StoredGraphRevision(
        revision=WorldGraphRevision(
            world_id=ELDYRWILD_WORLD_ID,
            revision_id="rev:parent",
            parent_revision_id=None,
            created_at=NOW,
            operation_ids=["seed"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload_sha256=canonical_sha256(body),
        ),
        graph_payload=body,
    )


def test_repairs_only_the_six_party_registry_evidence_keys() -> None:
    parent = _parent()
    result = materialize_party_registry_provenance_repair(parent, sources=_sources())
    assert len(result.corrected_evidence_ref_ids) == 6
    assert {item["source_domain_key"] for item in result.graph_payload["evidence_refs"]} == {
        "party_registry"
    }  # type: ignore[index]
    assert result.graph_payload["objects"] == parent.graph_payload["objects"]
    assert result.graph_payload["relationships"] == parent.graph_payload["relationships"]


def test_fails_closed_for_a_non_historical_evidence_key() -> None:
    payload = _payload()
    payload["evidence_refs"][0]["source_domain_key"] = "wrong"  # type: ignore[index]
    with pytest.raises(PersistenceIntegrityError, match="failed validation"):
        materialize_party_registry_provenance_repair(_parent(payload), sources=_sources())


def test_publish_is_exact_retry_noop_and_stale_parent_fails_closed() -> None:
    graph = InMemoryWorldGraphRepository()
    parent = _payload()
    seeded = graph.publish_revision(
        PublishRevisionCommand(
            world_id=ELDYRWILD_WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["seed"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=parent,
            created_at=NOW,
        )
    )
    first = publish_party_registry_provenance_repair(
        graph,
        sources=_sources(),
        created_at=NOW,
        expected_parent_revision_id=seeded.revision_id,
    )
    retry = publish_party_registry_provenance_repair(
        graph,
        sources=_sources(),
        created_at=NOW,
        expected_parent_revision_id=seeded.revision_id,
    )
    assert first.already_applied is False
    assert retry.already_applied is True
    assert retry.child_revision_id == first.child_revision_id
    with pytest.raises(PersistenceIntegrityError) as error:
        publish_party_registry_provenance_repair(
            graph,
            sources=_sources(),
            created_at=NOW,
            expected_parent_revision_id="rev:wrong",
        )
    assert error.value.details["reason"] == "expected_parent_missing"
