"""Every durable/wire contract must round-trip exactly and reject unknown fields."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dungeonmind.contracts import (
    CapabilityCategory,
    CapabilityEffect,
    CapabilityPolicy,
    ContributionSourceKind,
    EvidenceRef,
    GraphContribution,
    GraphContributionAssertion,
    GraphRetrievalSession,
    GraphScope,
    IdentityDecisionKind,
    IdentityDecisionRecord,
    MindTurnRequest,
    MindTurnResponse,
    ProjectionSnapshot,
    PublishRevisionCommand,
    SemanticDocument,
    SemanticDocumentKind,
    SemanticQuery,
    SourceArtifact,
    SourceDomain,
    SourceRevision,
    StoredGraphRevision,
    ToolCapabilityRule,
    Visibility,
    WorldGraphHead,
    WorldGraphProjectionRequest,
    WorldGraphRevision,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)


def _instances() -> list[object]:
    revision = WorldGraphRevision(
        world_id="world:demo",
        revision_id="rev:" + "ab" * 16,
        parent_revision_id=None,
        created_at=NOW,
        operation_ids=["op:1"],
        graph_schema="dm_union_graph_v1",
        graph_payload_sha256="cd" * 32,
    )
    snapshot = ProjectionSnapshot(
        world_id="world:demo",
        revision_id=revision.revision_id,
        head_revision_id=revision.revision_id,
        is_head=True,
        projected_at=NOW,
    )
    return [
        revision,
        WorldGraphHead(
            world_id="world:demo", head_revision_id=revision.revision_id, updated_at=NOW
        ),
        PublishRevisionCommand(
            world_id="world:demo",
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["op:1"],
            graph_schema="dm_union_graph_v1",
            graph_payload={"world_id": "world:demo"},
            created_at=NOW,
        ),
        StoredGraphRevision(revision=revision, graph_payload={"world_id": "world:demo"}),
        GraphContribution(
            contribution_id="ctr:1",
            world_id="world:demo",
            source_kind=ContributionSourceKind.EXTRACTION,
            produced_at=NOW,
            assertions=[
                GraphContributionAssertion(
                    assertion_id="a:1",
                    assertion_kind="relationship",
                    subject_object_id="obj:1",
                    predicate="resides_in",
                    object_object_id="obj:2",
                    evidence_refs=[
                        EvidenceRef(
                            evidence_ref_id="evd:1",
                            source_artifact_id="src:1",
                            source_domain=SourceDomain.WORLDBUILDING,
                        )
                    ],
                )
            ],
        ),
        EvidenceRef(
            evidence_ref_id="evd:1",
            source_artifact_id="src:1",
            source_domain=SourceDomain.SESSION_RECAP,
        ),
        SourceArtifact(
            source_artifact_id="src:1",
            source_domain=SourceDomain.SESSION_RECAP,
            world_id="world:demo",
            campaign_id="camp:1",
            session_id="ses-recap:1",
            content_sha256="ef" * 32,
            created_at=NOW,
        ),
        SourceRevision(
            source_revision_id="srev:1",
            source_artifact_id="src:1",
            content_sha256="ef" * 32,
            locator="r2://bucket/key",
            created_at=NOW,
        ),
        IdentityDecisionRecord(
            decision_id="dec:1",
            world_id="world:demo",
            decision_kind=IdentityDecisionKind.MERGE,
            subject_object_ids=["obj:1", "obj:2"],
            target_object_ids=["obj:1"],
            created_at=NOW,
        ),
        WorldGraphProjectionRequest(world_id="world:demo", campaign_id="camp:1"),
        snapshot,
        GraphRetrievalSession(
            session_id="ses:1",
            snapshot=snapshot,
            question="Where does Mere Astor live?",
            created_at=NOW,
            updated_at=NOW,
        ),
        SemanticDocument(
            semantic_document_id="sdoc:1",
            document_kind=SemanticDocumentKind.GRAPH_OBJECT,
            world_id="world:demo",
            graph_object_id="obj:1",
            visibility=Visibility.GM,
            content="Mere Astor, factor of Vael",
            content_sha256="12" * 32,
            embedding_model="test-model",
            embedding_model_revision="rev-1",
            embedding_dimensions=8,
            embedding_recipe="raw-v1",
            materialization_run_id="erun:1",
            created_at=NOW,
            embedding=[0.0] * 8,
        ),
        SemanticQuery(world_id="world:demo", text="Mere Astor", top_k=5),
        CapabilityPolicy(
            policy_id="pol:1",
            graph_scope=GraphScope(world_id="world:demo"),
            enabled_tools=["graph.search"],
            tool_rules=[
                ToolCapabilityRule(
                    tool_name="graph.search",
                    category=CapabilityCategory.READ_ONLY,
                    allowed_effects=[CapabilityEffect.READ],
                )
            ],
        ),
        MindTurnRequest(
            request_id="req:1",
            thread_id="thr:1",
            caller_scope={"caller_id": "user:1"},
            world_id="world:demo",
            surface_context={"surface_id": "surface:test"},
            message="Where does Mere Astor live?",
        ),
        MindTurnResponse(
            request_id="req:1",
            turn_id="turn:1",
            thread_id="thr:1",
            world_id="world:demo",
            revision_id=revision.revision_id,
            answer="In Vael.",
        ),
    ]


@pytest.mark.parametrize("instance", _instances(), ids=lambda i: type(i).__name__)
def test_round_trip_exact(instance: object) -> None:
    model_type = type(instance)
    payload = instance.model_dump_json()  # type: ignore[attr-defined]
    restored = model_type.model_validate_json(payload)
    assert restored == instance
    assert restored.model_dump_json() == payload


@pytest.mark.parametrize("instance", _instances(), ids=lambda i: type(i).__name__)
def test_unknown_fields_rejected(instance: object) -> None:
    model_type = type(instance)
    payload = instance.model_dump(mode="json")  # type: ignore[attr-defined]
    payload["unexpected_field"] = "drift"
    with pytest.raises(ValidationError):
        model_type.model_validate(payload)


def test_campaign_scope_blank_forbidden() -> None:
    with pytest.raises(ValidationError):
        GraphContribution(
            contribution_id="ctr:1",
            world_id="world:demo",
            source_kind=ContributionSourceKind.MANUAL_IMPORT,
            produced_at=NOW,
            campaign_scope="",
        )
