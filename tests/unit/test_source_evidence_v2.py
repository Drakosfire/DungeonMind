"""Contract matrix for lossless source/evidence provenance v2."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dungeonmind.application.graph_scope import (
    EvidenceScopeVerdict,
    ProvenanceRejection,
    project_scoped_snapshot,
    public_coverage_gaps_for_exclusion,
    resolve_evidence_provenance,
)
from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V2,
    GraphEvidenceRecord,
    GraphEvidenceRecordV2,
    GraphObjectView,
    ParsedGraphSnapshot,
)
from dungeonmind.contracts.evidence import (
    EvidenceRefV2,
    EvidenceRole,
    SourceArtifact,
    SourceArtifactV2,
    SourceAuthority,
    SourceDomain,
    SourceReviewState,
    SourceRevision,
    SourceStatus,
    WorkspaceDocumentRefV1,
)
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.infrastructure.memory import InMemorySourceRepository

FIXED_NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
WORLD_ID = "world:provenance-v2"
CAMPAIGN_ID = "camp:alpha"


def _artifact_v2(
    *,
    source_artifact_id: str = "src:v2-notes",
    source_domain_key: str = "buddy.session_recap",
    source_domain: SourceDomain | None = SourceDomain.SESSION_RECAP,
    campaign_id: str | None = CAMPAIGN_ID,
    session_id: str | None = "ses:0011",
    visibility: Visibility | None = Visibility.GM,
    source_visibility_state: str | None = "producer_private",
    authority: SourceAuthority | None = None,
    review_state: SourceReviewState | None = SourceReviewState.CANONICAL,
    lineage: dict | None = None,
    created_at: datetime | None = FIXED_NOW,
    updated_at: datetime | None = FIXED_NOW,
) -> SourceArtifactV2:
    return SourceArtifactV2(
        source_artifact_id=source_artifact_id,
        source_domain_key=source_domain_key,
        source_domain=source_domain,
        world_id=WORLD_ID,
        campaign_id=campaign_id,
        session_id=session_id,
        uri=None,
        current_revision_id="srcrev:v2-notes-v1",
        authority=authority,
        visibility=visibility,
        artifact_kind=None,
        document_class=None,
        review_state=review_state,
        source_visibility_state=source_visibility_state,
        workspace_document_ref=WorkspaceDocumentRefV1(
            document_id="doc:buddy-42", revision=3
        ),
        lineage={"import_batch": "batch-7"} if lineage is None else lineage,
        status=SourceStatus.ACTIVE,
        created_at=created_at,
        updated_at=updated_at,
    )


def _evidence_record(
    *,
    evidence_ref_id: str = "ev:v2",
    source_artifact_id: str = "src:v2-notes",
    source_domain_key: str = "buddy.session_recap",
    source_domain: SourceDomain | None = SourceDomain.SESSION_RECAP,
) -> GraphEvidenceRecordV2:
    return GraphEvidenceRecordV2(
        evidence_ref_id=evidence_ref_id,
        source_artifact_id=source_artifact_id,
        source_revision_id="srcrev:v2-notes-v1",
        source_domain_key=source_domain_key,
        source_domain=source_domain,
        evidence_role=EvidenceRole.SUPPORT,
        can_open_source=True,
        can_highlight_span=False,
        session_id="ses:0011",
        source_span_ref_id=None,
        locator=None,
        uri=None,
        source_locator=None,
        line_ref=None,
    )


def _v1_evidence_record(
    *,
    evidence_ref_id: str = "ev:v1",
    source_artifact_id: str = "src:v1-hidden",
) -> GraphEvidenceRecord:
    return GraphEvidenceRecord(
        evidence_ref_id=evidence_ref_id,
        source_artifact_id=source_artifact_id,
        source_revision_id="srcrev:v1-hidden-v1",
        source_domain="worldbuilding",
        evidence_role="support",
        can_open_source=True,
        can_highlight_span=False,
        locator=None,
        uri=None,
    )


def _snapshot_with_evidence(
    record: GraphEvidenceRecord | GraphEvidenceRecordV2,
) -> ParsedGraphSnapshot:
    return ParsedGraphSnapshot(
        world_id=WORLD_ID,
        graph_schema=GRAPH_SCHEMA_V2,
        objects={
            "obj:gate": GraphObjectView(
                object_id="obj:gate",
                kind="place",
                label="Gate",
                evidence_ref_ids=[record.evidence_ref_id],
                core_evidence_ref_ids=[record.evidence_ref_id],
                object_field_schema="v2",
            )
        },
        relationships={},
        evidence={record.evidence_ref_id: record},
    )


def _seed_v2_sources(
    artifact: SourceArtifactV2 | None = None,
) -> InMemorySourceRepository:
    sources = InMemorySourceRepository()
    art = artifact or _artifact_v2()
    sources.put_artifact(art)
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:v2-notes-v1",
            source_artifact_id=art.source_artifact_id,
            content_sha256="aa" * 32,
            body_storage="external",
            locator="fixture://v2-notes",
            created_at=FIXED_NOW,
        )
    )
    return sources


def test_campaign_matching_domains_pass_provenance() -> None:
    artifact = _artifact_v2()
    record = _evidence_record()
    sources = _seed_v2_sources(artifact)
    snapshot = _snapshot_with_evidence(record)
    resolved = resolve_evidence_provenance(
        "ev:v2",
        snapshot=snapshot,
        sources=sources,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        admissibility=Admissibility.GM,
    )
    assert resolved is not None
    assert not isinstance(resolved, ProvenanceRejection)
    assert resolved is not EvidenceScopeVerdict.SCOPE_UNKNOWN
    assert isinstance(resolved.evidence, EvidenceRefV2)
    assert resolved.artifact == artifact


def test_domain_key_mismatch_fails_provenance() -> None:
    artifact = _artifact_v2(source_domain_key="buddy.session_recap")
    record = _evidence_record(source_domain_key="buddy.other_kind")
    sources = _seed_v2_sources(artifact)
    snapshot = _snapshot_with_evidence(record)
    resolved = resolve_evidence_provenance(
        "ev:v2",
        snapshot=snapshot,
        sources=sources,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        admissibility=Admissibility.GM,
    )
    assert isinstance(resolved, ProvenanceRejection)
    assert resolved.gap_code == "evidence_source_domain_mismatch"


def test_visibility_null_with_source_visibility_state_not_admitted() -> None:
    artifact = _artifact_v2(
        visibility=None,
        source_visibility_state="producer_public",
    )
    sources = _seed_v2_sources(artifact)
    snapshot = _snapshot_with_evidence(_evidence_record())
    assert (
        resolve_evidence_provenance(
            "ev:v2",
            snapshot=snapshot,
            sources=sources,
            world_id=WORLD_ID,
            campaign_id=CAMPAIGN_ID,
            admissibility=Admissibility.GM,
        )
        is EvidenceScopeVerdict.SCOPE_UNKNOWN
    )
    scoped = project_scoped_snapshot(
        snapshot,
        sources=sources,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        admissibility=Admissibility.GM,
    )
    assert "obj:gate" not in scoped.snapshot.objects


def test_v1_evidence_hidden_v2_artifact_is_silent() -> None:
    """Visible v1 evidence → hidden v2 artifact must not leak schema mismatch."""
    hidden = _artifact_v2(
        source_artifact_id="src:v2-hidden",
        visibility=Visibility.GM,
        source_domain_key="buddy.worldbuilding",
        source_domain=SourceDomain.WORLDBUILDING,
        campaign_id=CAMPAIGN_ID,
        session_id=None,
    )
    sources = InMemorySourceRepository()
    sources.put_artifact(hidden)
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:v1-hidden-v1",
            source_artifact_id=hidden.source_artifact_id,
            content_sha256="cc" * 32,
            body_storage="external",
            locator="fixture://hidden",
            created_at=FIXED_NOW,
        )
    )
    record = _v1_evidence_record(source_artifact_id=hidden.source_artifact_id)
    snapshot = _snapshot_with_evidence(record)
    resolved = resolve_evidence_provenance(
        record.evidence_ref_id,
        snapshot=snapshot,
        sources=sources,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        admissibility=Admissibility.PLAYER,
    )
    assert resolved is None
    scoped = project_scoped_snapshot(
        snapshot,
        sources=sources,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        admissibility=Admissibility.PLAYER,
    )
    assert "obj:gate" not in scoped.snapshot.objects
    exclusion = scoped.object_exclusions["obj:gate"]
    gap_codes, missing = public_coverage_gaps_for_exclusion(exclusion)
    assert gap_codes == []
    assert missing == []
    assert "evidence_source_schema_mismatch" not in str(exclusion)


def test_v2_evidence_hidden_v1_artifact_is_silent() -> None:
    """Visible v2 evidence → hidden v1 artifact must not leak schema mismatch."""
    hidden = SourceArtifact(
        source_artifact_id="src:v1-hidden",
        source_domain=SourceDomain.WORLDBUILDING,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        visibility=Visibility.GM,
        status=SourceStatus.ACTIVE,
        created_at=FIXED_NOW,
    )
    sources = InMemorySourceRepository()
    sources.put_artifact(hidden)
    sources.put_revision(
        SourceRevision(
            source_revision_id="srcrev:v2-notes-v1",
            source_artifact_id=hidden.source_artifact_id,
            content_sha256="dd" * 32,
            body_storage="external",
            locator="fixture://v1-hidden",
            created_at=FIXED_NOW,
        )
    )
    record = _evidence_record(
        source_artifact_id=hidden.source_artifact_id,
        source_domain_key="buddy.worldbuilding",
        source_domain=SourceDomain.WORLDBUILDING,
    )
    snapshot = _snapshot_with_evidence(record)
    resolved = resolve_evidence_provenance(
        record.evidence_ref_id,
        snapshot=snapshot,
        sources=sources,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        admissibility=Admissibility.PLAYER,
    )
    assert resolved is None
    scoped = project_scoped_snapshot(
        snapshot,
        sources=sources,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        admissibility=Admissibility.PLAYER,
    )
    assert "obj:gate" not in scoped.snapshot.objects
    exclusion = scoped.object_exclusions["obj:gate"]
    gap_codes, missing = public_coverage_gaps_for_exclusion(exclusion)
    assert gap_codes == []
    assert missing == []
    assert "evidence_source_schema_mismatch" not in str(exclusion)


def test_visible_cross_schema_mismatch_is_detailed() -> None:
    """Once an artifact is proven visible, schema mismatch may be detailed."""
    visible_v1 = SourceArtifact(
        source_artifact_id="src:v1-visible",
        source_domain=SourceDomain.WORLDBUILDING,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        visibility=Visibility.PLAYER,
        status=SourceStatus.ACTIVE,
        created_at=FIXED_NOW,
    )
    sources = InMemorySourceRepository()
    sources.put_artifact(visible_v1)
    record = _evidence_record(
        source_artifact_id=visible_v1.source_artifact_id,
        source_domain_key="buddy.worldbuilding",
        source_domain=SourceDomain.WORLDBUILDING,
    )
    snapshot = _snapshot_with_evidence(record)
    resolved = resolve_evidence_provenance(
        record.evidence_ref_id,
        snapshot=snapshot,
        sources=sources,
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        admissibility=Admissibility.PLAYER,
    )
    assert isinstance(resolved, ProvenanceRejection)
    assert resolved.gap_code == "evidence_source_schema_mismatch"


def test_memory_roundtrip_null_timestamps() -> None:
    artifact = _artifact_v2(created_at=None, updated_at=None)
    sources = InMemorySourceRepository()
    assert sources.put_artifact(artifact) == artifact
    got = sources.get_artifact(artifact.source_artifact_id)
    assert got is not None
    assert got.created_at is None
    assert got.updated_at is None


def test_review_state_canonical_with_authority_null_valid() -> None:
    artifact = SourceArtifactV2.model_validate(
        _artifact_v2(
            authority=None,
            review_state=SourceReviewState.CANONICAL,
        ).model_dump(mode="json")
    )
    assert artifact.authority is None
    assert artifact.review_state is SourceReviewState.CANONICAL


def test_source_domain_key_with_null_source_domain_survives() -> None:
    artifact = _artifact_v2(
        source_domain_key="producer.opaque",
        source_domain=None,
        campaign_id=None,
        session_id=None,
    )
    sources = InMemorySourceRepository()
    sources.put_artifact(artifact)
    got = sources.get_artifact(artifact.source_artifact_id)
    assert got is not None
    assert got.source_domain_key == "producer.opaque"
    assert got.source_domain is None


def test_workspace_document_ref_distinct_from_source_artifact_id() -> None:
    artifact = _artifact_v2(source_artifact_id="src:kernel-id")
    assert artifact.workspace_document_ref is not None
    assert artifact.workspace_document_ref.document_id != artifact.source_artifact_id


def test_lineage_json_accepts_nested_dict() -> None:
    artifact = _artifact_v2(lineage={"chain": [{"step": 1, "ok": True}]})
    assert artifact.lineage["chain"][0]["step"] == 1


def test_lineage_rejects_non_json_value() -> None:
    with pytest.raises(ValidationError):
        SourceArtifactV2.model_validate(
            {
                **_artifact_v2().model_dump(mode="json"),
                "lineage": {"when": datetime(2026, 1, 1, tzinfo=UTC)},
            }
        )
