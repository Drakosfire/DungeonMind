"""Source admission through publication and authorized reads, with opaque producer keys."""

from __future__ import annotations

import copy
from hashlib import sha256

import pytest

from dungeonmind.application.contribution_review_v2 import finalize_contribution_review_v2
from dungeonmind.application.review_materialization_v6 import materialize_finalized_review_v6
from dungeonmind.application.review_publication import publish_finalized_review
from dungeonmind.application.source_admission import admit_source_revision
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import EvidenceTarget, WorldGraphRetrievalService
from dungeonmind.contracts.evidence import SourceArtifactV2, SourceRevision
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.projection_v2 import WorldGraphProjectionRequestV2
from dungeonmind.contracts.review_publication import FinalizedReviewPublicationCommand
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import ContributionMaterializationError
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.postgres.database import jsonb
from dungeonmind.infrastructure.postgres.review_publication import (
    PostgresFinalizedReviewPublicationRepository,
)
from dungeonmind.infrastructure.postgres.serialization import dump_payload, model_fingerprint
from tests.unit.test_contribution_review_v2 import (
    CAMPAIGN_ID,
    NEW_OBJECT_ID,
    REVIEWED_AT,
    WORLD_ID,
    _candidate,
    _intent,
    _policy,
    _reader,
    _stored_parent,
    _submission,
)

pytestmark = pytest.mark.integration
BODY = b"A synthetic traveler arrived at the gate.\n"


def _artifact(artifact_id, session, revision_id=None, uri=None):
    return SourceArtifactV2(
        source_artifact_id=artifact_id,
        source_domain_key="producer.custom-recap",
        source_domain="session_recap",
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        session_id=session,
        uri=uri,
        current_revision_id=revision_id,
        authority="primary",
        visibility="gm",
        artifact_kind="document",
        document_class=None,
        review_state=None,
        source_visibility_state="private",
        workspace_document_ref=None,
        status="active",
        created_at=REVIEWED_AT,
        updated_at=REVIEWED_AT,
    )


def _setup(pg, tmp_path):
    parent = _stored_parent()
    root = pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=parent.revision.operation_ids,
            graph_schema=parent.revision.graph_schema,
            graph_payload=parent.graph_payload,
            created_at=REVIEWED_AT,
        )
    )
    assert root.revision_id == parent.revision.revision_id
    old = parent.graph_payload["evidence_refs"][0]
    pg.sources.put_artifact(
        _artifact(old["source_artifact_id"], "session-1").model_copy(
            update={"source_domain_key": old["source_domain_key"]},
        )
    )
    path = tmp_path / "synthetic-recap.txt"
    path.write_bytes(BODY)
    candidate = _candidate()
    artifact_id = candidate.source_artifact_id
    revision_id = "sha256:" + sha256(BODY).hexdigest()
    artifact = _artifact(artifact_id, "session-2", revision_id, str(path))
    revision = SourceRevision(
        source_revision_id=revision_id,
        source_artifact_id=artifact_id,
        content_sha256=sha256(BODY).hexdigest(),
        body_storage="external",
        locator=str(path),
        created_at=REVIEWED_AT,
    )
    admit_source_revision(
        world_id=WORLD_ID,
        admission_id="admission:synthetic-producer-key",
        expected_head_revision_id=root.revision_id,
        artifact=artifact,
        revision=revision,
        source_body=BODY,
        admitted_at=REVIEWED_AT,
        world_graph_repository=pg.world_graph,
        source_repository=pg.sources,
    )
    candidate.source_revision_id = revision_id
    for assertion in candidate.assertions:
        assertion.evidence_refs = [
            ref.model_copy(
                update={
                    "source_revision_id": revision_id,
                    "uri": str(path),
                }
            )
            for ref in assertion.evidence_refs
        ]
    intent = _intent(candidate=candidate, parent=parent)
    state = finalize_contribution_review_v2(
        _submission(intent),
        capability_policy=_policy(intent),
        world_graph_repository=pg.world_graph,
        review_repository=pg.contribution_reviews,
    )
    return parent, state, artifact, revision


def _publish(pg, state, repository=None):
    return publish_finalized_review(
        WORLD_ID,
        state.record.review_id,
        published_at=REVIEWED_AT,
        review_repository=pg.contribution_reviews,
        world_graph_repository=pg.world_graph,
        publication_repository=repository or pg.finalized_review_publications,
        graph_reader=_reader(),
    )


def _counts(pg):
    with pg.database.transaction() as conn:
        return tuple(
            conn.execute(
                "SELECT (SELECT count(*) FROM dungeonmind.graph_revisions), "
                "(SELECT count(*) FROM dungeonmind.world_graph_head_events), "
                "(SELECT count(*) FROM dungeonmind.finalized_review_publications)"
            )
            .fetchone()
            .values()
        )


def _command(parent, state, payload):
    record = state.record
    digest = canonical_sha256(payload)
    return FinalizedReviewPublicationCommand(
        world_id=WORLD_ID,
        review_id=record.review_id,
        reviewed_contribution_id=record.reviewed_contribution_id,
        reviewed_contribution_sha256=record.reviewed_contribution_sha256,
        review_intent_sha256=record.review_intent_sha256,
        confirmation_id=record.confirmation_id,
        operation_id=record.operation_id,
        expected_parent_revision_id=parent.revision.revision_id,
        parent_graph_payload_sha256=parent.revision.graph_payload_sha256,
        expected_published_revision_id=compute_revision_id(
            world_id=WORLD_ID,
            parent_revision_id=parent.revision.revision_id,
            operation_ids=[record.operation_id],
            graph_schema=parent.revision.graph_schema,
            graph_payload_sha256=digest,
        ),
        graph_schema=parent.revision.graph_schema,
        graph_payload=payload,
        graph_payload_sha256=digest,
        requested_published_at=REVIEWED_AT,
    )


def test_source_admission_publication_world_reads_and_exact_source_open(pg, tmp_path, monkeypatch):
    parent, state, artifact, revision = _setup(pg, tmp_path)
    receipt = _publish(pg, state)
    child = pg.world_graph.get_revision(WORLD_ID, receipt.published_revision_id)
    introduced = [
        r
        for r in child.graph_payload["evidence_refs"]
        if r["source_artifact_id"] == artifact.source_artifact_id
    ]
    assert introduced and all(r["source_domain_key"] == "producer.custom-recap" for r in introduced)
    assert all(r["source_domain"] == "session_recap" for r in introduced)
    assert pg.sources.get_artifact(artifact.source_artifact_id) == artifact
    assert pg.sources.get_revision(revision.source_revision_id) == revision
    assert child.graph_payload["evidence_refs"][0] == parent.graph_payload["evidence_refs"][0]
    projection = WorldGraphProjectionService(
        world_graph=pg.world_graph,
        sources=pg.sources,
        graph_reader=_reader(),
        reviewed_world_initializations=pg.reviewed_world_initializations,
    )
    reads = WorldGraphRetrievalService(projection=projection, sources=pg.sources)
    request = WorldGraphProjectionRequestV2(
        world_id=WORLD_ID,
        scope_mode="world_cross_campaign",
        admissibility="gm",
        revision_pin=receipt.published_revision_id,
    )
    assert NEW_OBJECT_ID in reads.search(request, query_text="New NPC").matched_object_ids
    assert reads.get_object(request, object_id=NEW_OBJECT_ID).found
    evidence = reads.get_evidence(
        request, target=EvidenceTarget(kind="object", target_id=NEW_OBJECT_ID)
    )
    assert evidence.anchors
    anchor = evidence.anchors[0]
    resolved = reads.resolve_source_anchor(request, anchor_id=anchor.anchor_id)
    assert resolved.found and resolved.anchor.source_revision_id == revision.source_revision_id
    from pathlib import Path

    admitted = pg.sources.get_revision(resolved.anchor.source_revision_id)
    assert sha256(Path(admitted.locator).read_bytes()).hexdigest() == admitted.content_sha256
    before = _counts(pg)
    monkeypatch.setattr(
        pg.finalized_review_publications,
        "get_provenance_snapshot",
        lambda **kwargs: pytest.fail("durable replay must not reload source authority"),
    )
    assert _publish(pg, state) == receipt
    assert _counts(pg) == before


def test_publication_writer_rejects_forged_producer_key_with_zero_mutation(pg, tmp_path):
    parent, state, artifact, revision = _setup(pg, tmp_path)
    snapshot = pg.sources.get_provenance_snapshot(
        artifact_ids=[artifact.source_artifact_id],
        revision_ids=[revision.source_revision_id],
    )
    material = materialize_finalized_review_v6(
        state,
        parent=parent,
        graph_reader=_reader(),
        source_snapshot=snapshot,
    )
    payload = copy.deepcopy(material.graph_payload)
    for ref in payload["evidence_refs"]:
        if ref["source_artifact_id"] == artifact.source_artifact_id:
            ref["source_domain_key"] = "producer.forged"
    before = _counts(pg)
    with pytest.raises(ContributionMaterializationError, match="materialization") as caught:
        pg.finalized_review_publications.publish(_command(parent, state, payload))
    assert caught.value.reason == "evidence_source_domain_mismatch"
    assert _counts(pg) == before
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == parent.revision.revision_id
    assert pg.sources.get_artifact(artifact.source_artifact_id) == artifact


def test_source_producer_drift_between_preparation_and_writer_fence_fails_closed(pg, tmp_path):
    parent, state, artifact, _revision = _setup(pg, tmp_path)

    class DriftRepository(PostgresFinalizedReviewPublicationRepository):
        def get_provenance_snapshot(self, **kwargs):
            snapshot = super().get_provenance_snapshot(**kwargs)
            changed = artifact.model_copy(update={"source_domain_key": "producer.changed"})
            # Synthetic authority drift with a valid storage fingerprint; never production data.
            with pg.database.transaction() as conn:
                conn.execute(
                    "UPDATE dungeonmind.source_artifacts SET payload=%s, "
                    "record_fingerprint=%s WHERE source_artifact_id=%s",
                    (
                        jsonb(dump_payload(changed)),
                        model_fingerprint(changed),
                        artifact.source_artifact_id,
                    ),
                )
            return snapshot

    before = _counts(pg)
    with pytest.raises(ContributionMaterializationError) as caught:
        _publish(pg, state, DriftRepository(pg.database))
    assert caught.value.reason == "evidence_source_domain_mismatch"
    assert _counts(pg) == before
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == parent.revision.revision_id
