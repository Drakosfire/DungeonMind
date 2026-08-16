"""Negative tests: contracts encode closed invariants, not only extra=forbid."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dungeonmind.contracts import (
    AcceptanceState,
    Admissibility,
    Claim,
    ClaimAuthority,
    ContributionEpistemicKind,
    FocusKind,
    GraphContributionAssertion,
    GraphContributionAssertionCorrection,
    GraphContributionAssertionCorrectionKind,
    GraphContributionAssertionV2,
    GraphScope,
    IdentityAliasMapRewrite,
    IdentityDecisionKind,
    IdentityDecisionRecord,
    IdentityDecisionRecordV2,
    IdentityMergeSideEffects,
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
from dungeonmind.contracts.vocabulary import EpistemicKind

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


def test_unknown_correction_kind_rejected() -> None:
    with pytest.raises(ValidationError):
        GraphContributionAssertionCorrection.model_validate(
            {
                "correction_kind": "soft_retract",
                "target_contribution_id": "ctr:1",
                "target_assertion_id": "a:1",
            }
        )


def test_blank_correction_targets_rejected() -> None:
    with pytest.raises(ValidationError):
        GraphContributionAssertionCorrection(
            correction_kind=GraphContributionAssertionCorrectionKind.CONTRADICTS,
            target_contribution_id="  ",
            target_assertion_id="a:1",
        )
    with pytest.raises(ValidationError):
        GraphContributionAssertionCorrection(
            correction_kind=GraphContributionAssertionCorrectionKind.CONTRADICTS,
            target_contribution_id="ctr:1",
            target_assertion_id="",
        )


def test_contradicts_rejects_replacement() -> None:
    with pytest.raises(ValidationError):
        GraphContributionAssertionCorrection(
            correction_kind=GraphContributionAssertionCorrectionKind.CONTRADICTS,
            target_contribution_id="ctr:1",
            target_assertion_id="a:1",
            replacement_assertion_id="a:2",
        )


def test_contradicts_and_replaces_requires_replacement() -> None:
    with pytest.raises(ValidationError):
        GraphContributionAssertionCorrection(
            correction_kind=GraphContributionAssertionCorrectionKind.CONTRADICTS_AND_REPLACES,
            target_contribution_id="ctr:1",
            target_assertion_id="a:1",
        )


def test_merge_v2_requires_side_effects() -> None:
    with pytest.raises(ValidationError):
        IdentityDecisionRecordV2(
            decision_id="dec:1",
            world_id="world:demo",
            decision_kind=IdentityDecisionKind.MERGE,
            subject_object_ids=["obj:1", "obj:2"],
            target_object_ids=["obj:1"],
            created_at=NOW,
        )


def test_non_merge_v2_rejects_side_effects() -> None:
    with pytest.raises(ValidationError):
        IdentityDecisionRecordV2(
            decision_id="dec:1",
            world_id="world:demo",
            decision_kind=IdentityDecisionKind.ALIAS_ADD,
            subject_object_ids=["obj:1"],
            alias="Name",
            created_at=NOW,
            merge_side_effects=IdentityMergeSideEffects(),
        )


def test_alias_rewrite_blank_key_or_owner_rejected() -> None:
    with pytest.raises(ValidationError):
        IdentityAliasMapRewrite(
            alias_key="  ",
            prior_owner_node_id=None,
            new_owner_node_id="obj:1",
        )
    with pytest.raises(ValidationError):
        IdentityAliasMapRewrite(
            alias_key="alias",
            prior_owner_node_id=None,
            new_owner_node_id="",
        )


def test_alias_rewrite_new_owner_must_match_merge_target() -> None:
    with pytest.raises(ValidationError):
        IdentityDecisionRecordV2(
            decision_id="dec:1",
            world_id="world:demo",
            decision_kind=IdentityDecisionKind.MERGE,
            subject_object_ids=["obj:1", "obj:2"],
            target_object_ids=["obj:1"],
            created_at=NOW,
            merge_side_effects=IdentityMergeSideEffects(
                alias_map_rewrites=[
                    IdentityAliasMapRewrite(
                        alias_key="alias",
                        prior_owner_node_id="obj:2",
                        new_owner_node_id="obj:other",
                    )
                ]
            ),
        )


@pytest.mark.parametrize(
    "kind",
    [
        ContributionEpistemicKind.ASSERTED,
        ContributionEpistemicKind.INFERRED,
        ContributionEpistemicKind.SPECULATIVE,
        ContributionEpistemicKind.SOURCE_DERIVED_CANDIDATE,
    ],
)
def test_contribution_v2_epistemic_kinds_round_trip(kind: ContributionEpistemicKind) -> None:
    assertion = GraphContributionAssertionV2(
        assertion_id="a:1",
        assertion_kind="attribute",
        epistemic_kind=kind,
    )
    restored = GraphContributionAssertionV2.model_validate(assertion.model_dump(mode="json"))
    assert restored.epistemic_kind is kind


def test_unknown_contribution_epistemic_kind_rejected() -> None:
    with pytest.raises(ValidationError):
        GraphContributionAssertionV2.model_validate(
            {
                "assertion_id": "a:1",
                "assertion_kind": "attribute",
                "epistemic_kind": "fact",
            }
        )


def test_v1_assertion_still_rejects_source_derived_candidate() -> None:
    with pytest.raises(ValidationError):
        GraphContributionAssertion.model_validate(
            {
                "assertion_id": "a:1",
                "assertion_kind": "attribute",
                "epistemic_kind": "source_derived_candidate",
            }
        )
    assert [member.value for member in EpistemicKind] == [
        "asserted",
        "inferred",
        "speculative",
    ]
