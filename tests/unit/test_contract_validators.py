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
    IdentityDecisionKind,
    IdentityDecisionRecord,
    MindTurnRequest,
    ProjectionFocus,
    PublishRevisionCommand,
    ScopeMode,
    SemanticDocument,
    SemanticDocumentKind,
    SemanticQuery,
    SourceArtifact,
    SourceDomain,
    SourceRevision,
    WorldGraphProjectionRequest,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)


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


def test_visibility_required_on_semantic_query() -> None:
    with pytest.raises(ValidationError):
        SemanticQuery.model_validate({"world_id": "world:demo", "text": "x"})


def test_campaign_scope_mode_requires_campaign_id() -> None:
    with pytest.raises(ValidationError):
        WorldGraphProjectionRequest(
            world_id="world:demo",
            admissibility=Admissibility.GM,
            scope_mode=ScopeMode.CAMPAIGN,
        )


def test_session_focus_requires_session_id() -> None:
    with pytest.raises(ValidationError):
        ProjectionFocus(kind=FocusKind.SESSION)


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


def test_graph_object_doc_requires_object_id() -> None:
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


def test_source_chunk_requires_source_identity() -> None:
    with pytest.raises(ValidationError):
        SemanticDocument(
            semantic_document_id="sdoc:1",
            document_kind=SemanticDocumentKind.SOURCE_CHUNK,
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


def test_embedding_dimensions_must_match_vector() -> None:
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
