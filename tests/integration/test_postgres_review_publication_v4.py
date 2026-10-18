"""Actual installed-schema V4 finalize/publication and new-process admitted read.

The caller must select a uniquely owned disposable Core database. Shared fixture
TRUNCATE is used only within that unique database by integration/conftest.py.
"""

import copy
import os
import subprocess
import sys

import pytest

from dungeonmind.application.contribution_review_v4 import finalize_contribution_review_v4
from dungeonmind.application.review_materialization_v4 import materialize_finalized_review_v4
from dungeonmind.contracts.review_publication import FinalizedReviewPublicationCommand
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import ContributionMaterializationError
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle
from tests.integration import test_postgres_review_publication_v3 as f
from tests.integration.test_postgres_review_publication_v6 import NEW_OBJECT_ID
from tests.unit.test_contribution_review_v4 import (
    policy,
    submission,
    upgrade_intent,
)

pytestmark = pytest.mark.integration


def finalize(pg, parent, *, independent_property_source=False, public_subject=False):
    intent = upgrade_intent(f._typed_intent(parent))
    if independent_property_source:
        from dungeonmind.contracts.contribution import GraphContributionV4

        artifact = pg.sources.get_artifact(f.NEW_EVIDENCE_ARTIFACT)
        pg.sources.put_artifact(
            artifact.model_copy(
                update={
                    "source_artifact_id": "artifact:property:v4",
                    "current_revision_id": "revision:property:v4",
                }
            )
        )
        from dungeonmind.contracts.evidence import SourceRevision

        pg.sources.put_revision(
            SourceRevision(
                source_revision_id="revision:property:v4",
                source_artifact_id="artifact:property:v4",
                content_sha256="c" * 64,
                body_storage="object_store",
                locator="repo://property-evidence",
                created_at=f.REVIEWED_AT,
            )
        )
        raw = intent.candidate_contribution.model_dump(mode="json")
        prop = raw["assertions"][0]
        prop.update(
            source_artifact_id="artifact:property:v4", source_revision_id="revision:property:v4"
        )
        for ref in prop["evidence_refs"]:
            ref.update(
                evidence_ref_id="evidence:property:v4",
                source_artifact_id="artifact:property:v4",
                source_revision_id="revision:property:v4",
            )
        intent = upgrade_intent(
            f._typed_intent(parent), new_candidate=GraphContributionV4.model_validate(raw)
        )
    if public_subject:
        from dungeonmind.contracts.contribution import GraphContributionV4
        from dungeonmind.contracts.evidence import SourceRevision
        from dungeonmind.contracts.vocabulary import Visibility

        artifact = pg.sources.get_artifact(f.NEW_EVIDENCE_ARTIFACT)
        pg.sources.put_artifact(
            artifact.model_copy(
                update={
                    "source_artifact_id": "artifact:public-subject:v4",
                    "visibility": Visibility.PLAYER,
                    "current_revision_id": "revision:public-subject:v4",
                }
            )
        )
        pg.sources.put_revision(
            SourceRevision(
                source_revision_id="revision:public-subject:v4",
                source_artifact_id="artifact:public-subject:v4",
                content_sha256="d" * 64,
                body_storage="object_store",
                locator="repo://public-subject-evidence",
                created_at=f.REVIEWED_AT,
            )
        )
        raw = intent.candidate_contribution.model_dump(mode="json")
        for assertion in raw["assertions"]:
            if assertion["assertion_kind"] == "property":
                continue
            assertion.update(
                source_artifact_id="artifact:public-subject:v4",
                source_revision_id="revision:public-subject:v4",
                visibility="player",
            )
            for ref in assertion["evidence_refs"]:
                ref.update(
                    evidence_ref_id=ref["evidence_ref_id"] + ":public-subject",
                    source_artifact_id="artifact:public-subject:v4",
                    source_revision_id="revision:public-subject:v4",
                )
        intent = upgrade_intent(
            f._typed_intent(parent), new_candidate=GraphContributionV4.model_validate(raw)
        )
    state = finalize_contribution_review_v4(
        submission(intent),
        capability_policy=policy(intent),
        world_graph_repository=pg.world_graph,
        review_repository=pg.contribution_reviews,
    )
    return intent, state


def test_installed_schema_and_fresh_process_admitted_property_read(pg, migrated_database):
    assert PostgresDatabase(migrated_database)
    parent = f._seed(pg)
    _intent, state = finalize(pg, parent, independent_property_source=True, public_subject=True)
    assert finalize(pg, parent, independent_property_source=True, public_subject=True)[1] == state
    receipt = f._publish(pg, state.record.review_id)
    before = f._table_counts(pg)
    assert (
        f._publish(
            PostgresRepositoryBundle(PostgresDatabase(migrated_database)), state.record.review_id
        )
        == receipt
    )
    assert f._table_counts(pg) == before
    with pg.database.connect() as conn:
        rows = conn.execute(
            "SELECT table_name,data_type FROM information_schema.columns "
            "WHERE table_schema='dungeonmind' AND column_name='schema_version' "
            "AND table_name IN ('graph_contributions','contribution_reviews',"
            "'finalized_review_publications')"
        ).fetchall()
        assert len(rows) == 3 and all(r["data_type"] == "text" for r in rows)
        assert (
            conn.execute(
                "SELECT schema_version FROM dungeonmind.contribution_reviews WHERE review_id=%s",
                (state.record.review_id,),
            ).fetchone()["schema_version"]
            == "dm_contribution_review_record_v4"
        )
    code = """
import os
from dungeonmind.infrastructure.postgres import PostgresDatabase, PostgresRepositoryBundle
from dungeonmind.contracts.contribution_review_v4 import ContributionReviewStateV4
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import WorldGraphRetrievalService
from dungeonmind.contracts.projection_v2 import WorldGraphProjectionRequestV2
from tests.integration.test_postgres_review_publication_v3 import (
 WORLD_ID,CAMPAIGN_ID,eldyrwild_graph_reader)
from tests.integration.test_postgres_review_publication_v6 import NEW_OBJECT_ID
from tests.unit.test_contribution_review_v4 import PROPERTY_ID, VALUE
pg=PostgresRepositoryBundle(PostgresDatabase(os.environ['DUNGEONMIND_DATABASE_URL']))
state=pg.contribution_reviews.get(WORLD_ID,os.environ['V4_REVIEW_ID'])
assert isinstance(state,ContributionReviewStateV4)
projection=WorldGraphProjectionService(world_graph=pg.world_graph,sources=pg.sources,
 graph_reader=eldyrwild_graph_reader(),reviewed_world_initializations=pg.reviewed_world_initializations)
service=WorldGraphRetrievalService(projection=projection,sources=pg.sources,world_graph=pg.world_graph,
 contribution_reviews=pg.contribution_reviews,finalized_review_publications=pg.finalized_review_publications)
request=WorldGraphProjectionRequestV2(world_id=WORLD_ID,campaign_id=CAMPAIGN_ID,scope_mode='campaign',
 admissibility=os.environ.get('V4_ADMISSIBILITY','gm'),revision_pin=os.environ['V4_REVISION_ID'])
result=service.get_complete_object(request,object_id=NEW_OBJECT_ID)
assert result.found
rows=[p for p in result.property_assertions if p.assertion_id==PROPERTY_ID]
if os.environ.get('V4_EXPECT_WITHDRAWN') or os.environ.get('V4_ADMISSIBILITY')=='player':
 assert not rows
 assert not any(PROPERTY_ID in a.supporting_assertion_ids for a in result.anchors)
else:
 assert len(rows)==1 and rows[0].property_value==VALUE
 assert rows[0].property_term=='dnd5e:test_fact'
 assert rows[0].evidence_ref_ids==('evidence:property:v4',)
 assert any(a.source_span_ref_id=='paragraph:099' and
   PROPERTY_ID in a.supporting_assertion_ids for a in result.anchors)
assert not any(o.assertion_id==PROPERTY_ID for o in result.reviewed_source_observations)
print('fresh-process admitted V4 property read passed')
"""
    env = dict(
        os.environ,
        V4_REVIEW_ID=state.record.review_id,
        V4_REVISION_ID=receipt.published_revision_id,
    )
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "fresh-process admitted V4 property read passed" in result.stdout
    player = subprocess.run(
        [sys.executable, "-c", code],
        env=dict(env, V4_ADMISSIBILITY="player"),
        capture_output=True,
        text=True,
    )
    assert player.returncode == 0, player.stderr
    from dungeonmind.contracts.evidence import SourceStatus
    from dungeonmind.infrastructure.postgres.database import jsonb
    from dungeonmind.infrastructure.postgres.serialization import dump_payload, model_fingerprint

    artifact = pg.sources.get_artifact("artifact:property:v4")
    withdrawn = artifact.model_copy(update={"status": SourceStatus.RETRACTED})
    # Synthetic owner lifecycle fixture, isolated to this test's disposable DB.
    with pg.database.connect() as conn:
        conn.execute(
            "UPDATE dungeonmind.source_artifacts SET status=%s,payload=%s,record_fingerprint=%s "
            "WHERE source_artifact_id=%s",
            (
                withdrawn.status.value,
                jsonb(dump_payload(withdrawn)),
                model_fingerprint(withdrawn),
                withdrawn.source_artifact_id,
            ),
        )
        conn.commit()
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=dict(env, V4_EXPECT_WITHDRAWN="1"),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("mutation", ["changed", "tuple"])
def test_locked_publication_rejects_changed_property_with_zero_head_revision_receipt_writes(
    pg, mutation
):
    parent = f._seed(pg)
    _, state = finalize(pg, parent)
    artifacts, revisions = __import__(
        "dungeonmind.application.review_materialization_v4", fromlist=["review_source_refs_v4"]
    ).review_source_refs_v4(state)
    snapshot = pg.sources.get_provenance_snapshot(artifact_ids=artifacts, revision_ids=revisions)
    materialized = materialize_finalized_review_v4(
        state, parent=parent, graph_reader=f.eldyrwild_graph_reader(), source_snapshot=snapshot
    )
    payload = copy.deepcopy(materialized.graph_payload)
    if mutation == "changed":
        next(o for o in payload["objects"] if o["object_id"] == NEW_OBJECT_ID)["properties"][0][
            "value"
        ] = "tampered after review"
    digest = canonical_sha256(payload)
    record = state.record
    command = FinalizedReviewPublicationCommand(
        world_id=f.WORLD_ID,
        review_id=record.review_id,
        reviewed_contribution_id=record.reviewed_contribution_id,
        reviewed_contribution_sha256=record.reviewed_contribution_sha256,
        review_intent_sha256=record.review_intent_sha256,
        confirmation_id=record.confirmation_id,
        operation_id=record.operation_id,
        expected_parent_revision_id=parent.revision.revision_id,
        parent_graph_payload_sha256=parent.revision.graph_payload_sha256,
        expected_published_revision_id=compute_revision_id(
            world_id=f.WORLD_ID,
            parent_revision_id=parent.revision.revision_id,
            operation_ids=[record.operation_id],
            graph_schema=parent.revision.graph_schema,
            graph_payload_sha256=digest,
        ),
        graph_schema=parent.revision.graph_schema,
        graph_payload=payload,
        graph_payload_sha256=digest,
        requested_published_at=f.PUBLISHED_AT,
    )
    if mutation == "tuple":
        row = next(o for o in command.graph_payload["objects"] if o["object_id"] == NEW_OBJECT_ID)[
            "properties"
        ][0]
        row["value"]["flags"] = (True, False)
    before = f._table_counts(pg)
    with pytest.raises(ContributionMaterializationError) as caught:
        pg.finalized_review_publications.publish(command)
    assert caught.value.details["reason"] == (
        "property_literal_validation" if mutation == "tuple" else "reviewed_property_delta_mismatch"
    )
    assert f._table_counts(pg) == before
    assert pg.world_graph.get_head(f.WORLD_ID).head_revision_id == parent.revision.revision_id
