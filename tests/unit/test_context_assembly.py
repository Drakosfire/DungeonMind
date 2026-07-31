"""Unit tests for deterministic agent context assembly."""

import json

from dungeonmind.application.context_assembly import assemble_agent_context
from dungeonmind.application.graph_snapshot import GraphObjectView, GraphRelationshipView
from dungeonmind.contracts.evidence import EvidenceRef, EvidenceRole, SourceDomain
from dungeonmind.contracts.projection import Admissibility, ProjectionFocus
from dungeonmind.contracts.retrieval import Coverage, SourceAnchor
from dungeonmind.domain.canonical import canonical_json


def _object(oid: str, label: str) -> GraphObjectView:
    return GraphObjectView(
        object_id=oid,
        kind="npc",
        label=label,
        aliases=[],
        evidence_ref_ids=[f"ev:{oid}"],
    )


def _relationship(rid: str, subject: str, obj: str) -> GraphRelationshipView:
    return GraphRelationshipView(
        relationship_id=rid,
        subject_object_id=subject,
        predicate="related_to",
        object_object_id=obj,
        evidence_ref_ids=[f"ev:{rid}"],
    )


def _evidence(eid: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_ref_id=eid,
        source_artifact_id="src:atlas-notes",
        source_revision_id="srcrev:atlas-notes-v1",
        source_domain=SourceDomain.WORLDBUILDING,
        evidence_role=EvidenceRole.SUPPORT,
        can_open_source=True,
        locator=f"fixture://{eid}",
    )


def _anchor(aid: str, eid: str) -> SourceAnchor:
    return SourceAnchor(
        anchor_id=aid,
        revision_id="rev:" + "ab" * 16,
        evidence_ref_id=eid,
        source_artifact_id="src:atlas-notes",
        source_domain=SourceDomain.WORLDBUILDING.value,
        supporting_object_ids=["obj:a"],
        readable=True,
    )


def test_assembled_context_is_canonical_json() -> None:
    objects = [_object("obj:a", "A"), _object("obj:b", "B")]
    relationships = [
        _relationship("rel:b-a", "obj:b", "obj:a"),
        _relationship("rel:a-b", "obj:a", "obj:b"),
    ]
    evidence = [_evidence("ev:obj:a"), _evidence("ev:rel:a-b")]
    anchors = [_anchor("anchor:1", "ev:obj:a")]

    rendered = assemble_agent_context(
        revision_id="rev:" + "ab" * 16,
        world_id="world:demo-atlas",
        campaign_id="camp:demo",
        admissibility=Admissibility.GM,
        focus=ProjectionFocus(),
        objects=objects,
        relationships=relationships,
        evidence=evidence,
        source_anchors=anchors,
        coverage=Coverage(known=["obj:a"], missing=[], gap_codes=[]),
    )

    parsed = json.loads(rendered)
    assert rendered == canonical_json(parsed)
    # Re-assembly is byte-identical (sorted keys, tight separators).
    again = assemble_agent_context(
        revision_id="rev:" + "ab" * 16,
        world_id="world:demo-atlas",
        campaign_id="camp:demo",
        admissibility=Admissibility.GM,
        focus=ProjectionFocus(),
        objects=objects,
        relationships=relationships,
        evidence=evidence,
        source_anchors=anchors,
        coverage=Coverage(known=["obj:a"], missing=[], gap_codes=[]),
    )
    assert again == rendered


def test_truncation_drops_lower_ranked_relationships_before_corrupting_evidence() -> None:
    objects = [_object("obj:keep", "Keep"), _object("obj:drop", "Drop")]
    # Ranked last → truncated first.
    relationships = [
        _relationship(f"rel:high-{i}", "obj:keep", "obj:drop")
        for i in range(3)
    ] + [
        _relationship(f"rel:low-{i}", "obj:drop", "obj:keep")
        for i in range(20)
    ]
    evidence = [
        _evidence("ev:obj:keep"),
        _evidence("ev:obj:drop"),
        *[_evidence(f"ev:rel:high-{i}") for i in range(3)],
        *[_evidence(f"ev:rel:low-{i}") for i in range(20)],
    ]
    anchors = [_anchor("anchor:keep", "ev:obj:keep")]

    full = assemble_agent_context(
        revision_id="rev:" + "ab" * 16,
        world_id="world:demo-atlas",
        campaign_id=None,
        admissibility=Admissibility.GM,
        focus=ProjectionFocus(),
        objects=objects,
        relationships=relationships,
        evidence=evidence,
        source_anchors=anchors,
        coverage=Coverage(),
        char_limit=10_000_000,
    )
    full_doc = json.loads(full)
    assert len(full_doc["relationships"]) == 23
    full_bytes = len(full.encode("utf-8"))
    # Limit tight enough to force relationship drops, loose enough to keep evidence.
    char_limit = full_bytes - 800
    assert char_limit > 0

    truncated = assemble_agent_context(
        revision_id="rev:" + "ab" * 16,
        world_id="world:demo-atlas",
        campaign_id=None,
        admissibility=Admissibility.GM,
        focus=ProjectionFocus(),
        objects=objects,
        relationships=relationships,
        evidence=evidence,
        source_anchors=anchors,
        coverage=Coverage(),
        char_limit=char_limit,
    )
    assert len(truncated.encode("utf-8")) <= char_limit
    doc = json.loads(truncated)
    # Still valid JSON with intact evidence entries (not sliced mid-object).
    assert isinstance(doc["evidence"], list)
    assert all(isinstance(item, dict) for item in doc["evidence"])
    assert {item["evidence_ref_id"] for item in doc["evidence"]} == {
        item["evidence_ref_id"] for item in full_doc["evidence"]
    }
    assert len(doc["relationships"]) < len(full_doc["relationships"])
    # Lower-ranked (later) relationships drop first.
    kept_ids = [rel["relationship_id"] for rel in doc["relationships"]]
    assert kept_ids == [
        rel["relationship_id"] for rel in full_doc["relationships"][: len(kept_ids)]
    ]


def test_assembled_context_omits_auth_metadata_keys() -> None:
    rendered = assemble_agent_context(
        revision_id="rev:" + "ab" * 16,
        world_id="world:demo-atlas",
        campaign_id="camp:demo",
        admissibility=Admissibility.GM,
        focus=ProjectionFocus(),
        objects=[_object("obj:a", "A")],
        relationships=[],
        evidence=[_evidence("ev:obj:a")],
        source_anchors=[],
        coverage=Coverage(),
    )
    doc = json.loads(rendered)
    assert "caller_id" not in doc
    assert "tenant_id" not in doc
    assert "roles" not in doc
