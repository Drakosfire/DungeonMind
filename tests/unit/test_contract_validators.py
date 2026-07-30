"""Negative tests: contracts encode closed invariants, not only extra=forbid."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dungeonmind.contracts import (
    AcceptanceState,
    Admissibility,
    Claim,
    ClaimAuthority,
    FocusKind,
    GraphContributionAssertion,
    GraphScope,
    IdentityDecisionKind,
    IdentityDecisionRecord,
    MindTurnRequest,
    ProjectionFocus,
    ProjectionSnapshot,
    PublishRevisionCommand,
    ScopeMode,
    SemanticDocument,
    SemanticDocumentKind,
    SemanticQuery,
    SourceArtifact,
    SourceDomain,
    SourceRevision,
    SurfaceContext,
    WorldGraphProjectionRequest,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)
REV = "rev:" + "ab" * 16


def test_admissibility_required_on_projection_request() -> None:
    with pytest.raises(ValidationError):
        WorldGraphProjectionRequest.model_validate({"world_id": "world:demo"})


def test_admissibility_required_on_mind_turn() -> None:
    with pytest.raises(ValidationError):
        MindTurnRequest.model_validate(
            {
                "request_id": "req:1",
                "thread_id": "thr:1",
                "caller_scope": {"caller_id": "user:1"},
                "world_id": "world:demo",
                "surface_context": {"surface_id": "surface:test"},
                "message": "hello",
            }
        )


def test_admissibility_required_on_graph_scope() -> None:
    with pytest.raises(ValidationError):
        GraphScope.model_validate({"world_id": "world:demo"})


def test_visibility_required_on_semantic_query() -> None:
    with pytest.raises(ValidationError):
        SemanticQuery.model_validate({"world_id": "world:demo", "text": "x"})


def test_world_scope_without_campaign_ok() -> None:
    req = WorldGraphProjectionRequest(
        world_id="world:demo",
        admissibility=Admissibility.GM,
        scope_mode=ScopeMode.WORLD,
    )
    assert req.campaign_id is None


def test_world_scope_with_campaign_rejected() -> None:
    with pytest.raises(ValidationError):
        WorldGraphProjectionRequest(
            world_id="world:demo",
            campaign_id="camp:1",
            admissibility=Admissibility.GM,
            scope_mode=ScopeMode.WORLD,
        )


def test_campaign_scope_mode_requires_campaign_id() -> None:
    with pytest.raises(ValidationError):
        WorldGraphProjectionRequest(
            world_id="world:demo",
            admissibility=Admissibility.GM,
            scope_mode=ScopeMode.CAMPAIGN,
        )


def test_campaign_scope_with_campaign_ok() -> None:
    req = WorldGraphProjectionRequest(
        world_id="world:demo",
        campaign_id="camp:1",
        admissibility=Admissibility.GM,
        scope_mode=ScopeMode.CAMPAIGN,
    )
    assert req.campaign_id == "camp:1"


def test_session_focus_requires_session_id() -> None:
    with pytest.raises(ValidationError):
        ProjectionFocus(kind=FocusKind.SESSION)


def test_none_focus_with_session_id_rejected() -> None:
    with pytest.raises(ValidationError):
        ProjectionFocus(kind=FocusKind.NONE, session_id="ses:1")


def test_session_focus_requires_campaign_on_request() -> None:
    with pytest.raises(ValidationError):
        WorldGraphProjectionRequest(
            world_id="world:demo",
            admissibility=Admissibility.GM,
            scope_mode=ScopeMode.WORLD,
            focus=ProjectionFocus(kind=FocusKind.SESSION, session_id="ses:1"),
        )


def test_session_focus_with_campaign_accepted() -> None:
    req = WorldGraphProjectionRequest(
        world_id="world:demo",
        campaign_id="camp:1",
        admissibility=Admissibility.GM,
        scope_mode=ScopeMode.CAMPAIGN,
        focus=ProjectionFocus(kind=FocusKind.SESSION, session_id="ses:1"),
    )
    assert req.focus.session_id == "ses:1"
    assert "campaign_id" not in ProjectionFocus.model_fields


def test_projection_snapshot_rejects_contradictory_scope() -> None:
    with pytest.raises(ValidationError):
        ProjectionSnapshot(
            world_id="world:demo",
            campaign_id="camp:1",
            scope_mode=ScopeMode.WORLD,
            admissibility=Admissibility.GM,
            revision_id=REV,
            head_revision_id=REV,
            is_head=True,
            projected_at=NOW,
        )


def test_projection_snapshot_is_head_must_match_revision_ids() -> None:
    with pytest.raises(ValidationError):
        ProjectionSnapshot(
            world_id="world:demo",
            revision_id="rev:old" + "a" * 25,
            head_revision_id="rev:new" + "b" * 25,
            is_head=True,
            projected_at=NOW,
            admissibility=Admissibility.GM,
        )
    snap = ProjectionSnapshot(
        world_id="world:demo",
        revision_id=REV,
        head_revision_id="rev:other" + "c" * 23,
        is_head=False,
        projected_at=NOW,
        admissibility=Admissibility.GM,
    )
    assert snap.is_head is False


def test_mind_turn_session_focus_requires_campaign() -> None:
    with pytest.raises(ValidationError):
        MindTurnRequest(
            request_id="req:1",
            thread_id="thr:1",
            caller_scope={"caller_id": "user:1"},
            world_id="world:demo",
            admissibility=Admissibility.GM,
            focus=ProjectionFocus(kind=FocusKind.SESSION, session_id="ses:1"),
            surface_context=SurfaceContext(surface_id="surface:test"),
            message="hello",
        )


def test_graph_scope_session_focus_requires_campaign() -> None:
    with pytest.raises(ValidationError):
        GraphScope(
            world_id="world:demo",
            admissibility=Admissibility.GM,
            focus=ProjectionFocus(kind=FocusKind.SESSION, session_id="ses:1"),
        )


def test_focus_has_no_independent_campaign_authority() -> None:
    assert "campaign_id" not in ProjectionFocus.model_fields


def test_publish_parent_must_equal_expected() -> None:
    with pytest.raises(ValidationError):
        PublishRevisionCommand(
            world_id="world:demo",
            parent_revision_id="rev:a",
            expected_parent_revision_id="rev:b",
            operation_ids=["op:1"],
            graph_schema="dm_union_graph_v1",
            graph_payload={"v": 1},
            created_at=NOW,
        )


def test_accepted_assertion_requires_evidence_or_source() -> None:
    with pytest.raises(ValidationError):
        GraphContributionAssertion(
            assertion_id="a:1",
            assertion_kind="relationship",
            acceptance_state=AcceptanceState.ACCEPTED,
        )


def test_session_recap_requires_campaign_and_session() -> None:
    with pytest.raises(ValidationError):
        SourceArtifact(
            source_artifact_id="src:1",
            source_domain=SourceDomain.SESSION_RECAP,
            world_id="world:demo",
            created_at=NOW,
        )


def test_source_revision_locator_required_unless_postgres() -> None:
    with pytest.raises(ValidationError):
        SourceRevision(
            source_revision_id="srev:1",
            source_artifact_id="src:1",
            content_sha256="ab" * 32,
            body_storage="object_store",
            created_at=NOW,
        )
    ok = SourceRevision(
        source_revision_id="srev:2",
        source_artifact_id="src:1",
        content_sha256="ab" * 32,
        body_storage="postgres",
        created_at=NOW,
    )
    assert ok.locator is None


def test_graph_object_doc_requires_object_and_revision() -> None:
    with pytest.raises(ValidationError):
        SemanticDocument(
            semantic_document_id="sdoc:1",
            document_kind=SemanticDocumentKind.GRAPH_OBJECT,
            world_id="world:demo",
            content="x",
            content_sha256="ab" * 32,
            embedding_model="m",
            embedding_model_revision="r",
            embedding_dimensions=8,
            embedding_recipe="raw",
            materialization_run_id="erun:1",
            created_at=NOW,
        )
    with pytest.raises(ValidationError):
        SemanticDocument(
            semantic_document_id="sdoc:1",
            document_kind=SemanticDocumentKind.GRAPH_OBJECT,
            world_id="world:demo",
            graph_object_id="obj:1",
            content="x",
            content_sha256="ab" * 32,
            embedding_model="m",
            embedding_model_revision="r",
            embedding_dimensions=8,
            embedding_recipe="raw",
            materialization_run_id="erun:1",
            created_at=NOW,
        )


def test_source_chunk_requires_source_revision() -> None:
    with pytest.raises(ValidationError):
        SemanticDocument(
            semantic_document_id="sdoc:1",
            document_kind=SemanticDocumentKind.SOURCE_CHUNK,
            world_id="world:demo",
            source_artifact_id="src:1",
            content="x",
            content_sha256="ab" * 32,
            embedding_model="m",
            embedding_model_revision="r",
            embedding_dimensions=8,
            embedding_recipe="raw",
            materialization_run_id="erun:1",
            created_at=NOW,
        )


def test_embedding_dimensions_must_match_vector() -> None:
    with pytest.raises(ValidationError):
        SemanticDocument(
            semantic_document_id="sdoc:1",
            document_kind=SemanticDocumentKind.GRAPH_OBJECT,
            world_id="world:demo",
            graph_object_id="obj:1",
            graph_revision_id=REV,
            content="x",
            content_sha256="ab" * 32,
            embedding_model="m",
            embedding_model_revision="r",
            embedding_dimensions=8,
            embedding_recipe="raw",
            materialization_run_id="erun:1",
            created_at=NOW,
            embedding=[0.0, 1.0],
        )


def test_merge_requires_subjects_and_single_target() -> None:
    with pytest.raises(ValidationError):
        IdentityDecisionRecord(
            decision_id="dec:1",
            world_id="world:demo",
            decision_kind=IdentityDecisionKind.MERGE,
            subject_object_ids=["obj:1"],
            target_object_ids=["obj:1"],
            created_at=NOW,
        )


def test_alias_requires_alias_field() -> None:
    with pytest.raises(ValidationError):
        IdentityDecisionRecord(
            decision_id="dec:1",
            world_id="world:demo",
            decision_kind=IdentityDecisionKind.ALIAS_ADD,
            subject_object_ids=["obj:1"],
            created_at=NOW,
        )


def test_graph_fact_claim_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        Claim(claim_id="c:1", text="fact", authority=ClaimAuthority.GRAPH_FACT)
