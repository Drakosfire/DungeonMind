"""New-process V2 replay, corruption and historical/current source separation."""

import json
import os
import subprocess
import sys

import pytest

from dungeonmind.contracts.publication_admission import CONTEXT_BYTES, bounded_sha256
from dungeonmind.contracts.review_publication import FinalizedReviewPublicationV2
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres import PostgresFinalizedReviewPublicationRepository
from dungeonmind.infrastructure.postgres.database import jsonb
from tests.integration.test_postgres_publication_admission import counts, setup_pg
from tests.unit.test_contribution_review_v2 import WORLD_ID
from tests.unit.test_publication_admission import SyntheticValidator

pytestmark = pytest.mark.integration


def test_new_process_replay_without_validator_and_historical_snapshot_after_withdrawal(
    pg, migrated_database
):
    lane = setup_pg(pg, validator=SyntheticValidator())
    receipt = lane.publications.publish(lane.command)
    with pg.database.transaction() as conn:
        conn.execute(
            "UPDATE dungeonmind.source_artifacts SET status='retracted', "
            "payload=jsonb_set(payload,'{status}','\"retracted\"'::jsonb) "
            "WHERE source_artifact_id=%s",
            (receipt.admission_context.source_snapshot.artifacts[0].source_artifact_id,),
        )
        # Repair ordinary source record fingerprint as its lifecycle writer does.
        from dungeonmind.contracts.evidence import SourceArtifactV2
        from dungeonmind.infrastructure.postgres.serialization import model_fingerprint

        row = conn.execute(
            "SELECT payload FROM dungeonmind.source_artifacts WHERE source_artifact_id=%s",
            (receipt.admission_context.source_snapshot.artifacts[0].source_artifact_id,),
        ).fetchone()
        fingerprint = model_fingerprint(SourceArtifactV2.model_validate(row["payload"]))
        conn.execute(
            "UPDATE dungeonmind.source_artifacts SET record_fingerprint=%s "
            "WHERE source_artifact_id=%s",
            (
                fingerprint,
                receipt.admission_context.source_snapshot.artifacts[0].source_artifact_id,
            ),
        )
    before = counts(pg)
    env = dict(
        os.environ,
        ADMISSION_TEST_DSN=migrated_database,
        ADMISSION_TEST_COMMAND=json.dumps(lane.command.model_dump(mode="json")),
        PYTHONDONTWRITEBYTECODE="1",
    )
    script = """
import json, os
from dungeonmind.contracts.review_publication import decode_finalized_review_publication_command
from dungeonmind.infrastructure.postgres import (
    PostgresDatabase, PostgresFinalizedReviewPublicationRepository,
)
repo=PostgresFinalizedReviewPublicationRepository(PostgresDatabase(os.environ["ADMISSION_TEST_DSN"]))
command=decode_finalized_review_publication_command(json.loads(os.environ["ADMISSION_TEST_COMMAND"]))
receipt=repo.get_for_review(command.world_id,command.review_id)
assert repo.publish(command) == receipt
assert receipt.schema_version == "dm_finalized_review_publication_v2"
assert receipt.admission_context.source_snapshot.artifacts[0].status == "active"
print(receipt.admission_context_sha256)
"""
    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == receipt.admission_context_sha256
    assert counts(pg) == before
    # Current source authority remains withdrawn rather than resurrected by replay.
    assert (
        pg.sources.get_artifact(
            receipt.admission_context.source_snapshot.artifacts[0].source_artifact_id
        ).status
        == "retracted"
    )


@pytest.mark.parametrize(
    "field",
    [
        "context_digest",
        "accepted_set",
        "source_identity",
        "source_revision",
        "policy_ref",
        "family",
    ],
)
def test_reloaded_corrupt_receipt_fails_even_after_ordinary_fingerprint_rehash(pg, field):
    lane = setup_pg(pg, validator=SyntheticValidator())
    receipt = lane.publications.publish(lane.command)
    raw = receipt.model_dump(mode="json")
    if field == "context_digest":
        raw["admission_context_sha256"] = "0" * 64
    elif field == "family":
        raw["schema_version"] = "dm_finalized_review_publication_v99"
    else:
        context = raw["admission_context"]
        if field == "accepted_set":
            context["accepted_assertions"][0]["label"] = "corrupt role"
            context["accepted_assertions_sha256"] = canonical_sha256(context["accepted_assertions"])
        elif field == "source_identity":
            context["source_snapshot"]["artifacts"][0]["world_id"] = "another-world"
        elif field == "source_revision":
            context["source_snapshot"]["revisions"][0]["content_sha256"] = "0" * 64
        else:
            raw["admission_policy_ref"]["policy_sha256"] = "0" * 64
            context["admission_policy_ref"]["policy_sha256"] = "0" * 64
        context["source_snapshot_sha256"] = canonical_sha256(context["source_snapshot"])
        raw["admission_context_sha256"] = bounded_sha256(context, max_bytes=CONTEXT_BYTES)
    with pg.database.transaction() as conn:
        conn.execute(
            "UPDATE dungeonmind.finalized_review_publications SET payload=%s, "
            "record_fingerprint=%s, schema_version=%s WHERE world_id=%s AND review_id=%s",
            (jsonb(raw), canonical_sha256(raw), raw["schema_version"], WORLD_ID, receipt.review_id),
        )
    repo = PostgresFinalizedReviewPublicationRepository(pg.database)
    with pytest.raises(PersistenceIntegrityError):
        repo.get_for_review(WORLD_ID, receipt.review_id)
    with pytest.raises(PersistenceIntegrityError):
        repo.publish(lane.command)


def test_current_projection_filters_withdrawn_source_while_admission_history_stays_exact(pg):
    from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
    from dungeonmind.application.world_graph_retrieval import WorldGraphRetrievalService
    from dungeonmind.contracts.projection_v2 import WorldGraphProjectionRequestV2
    from tests.integration.test_postgres_publication_admission import retract_source
    from tests.unit.test_contribution_review_v2 import CAMPAIGN_ID, NEW_OBJECT_ID
    from tests.unit.test_contribution_review_v4 import PROPERTY_ID

    lane = setup_pg(pg, validator=SyntheticValidator())
    receipt = lane.publications.publish(lane.command)
    projection = WorldGraphProjectionService(
        world_graph=pg.world_graph,
        sources=pg.sources,
        graph_reader=lane.reader,
        reviewed_world_initializations=pg.reviewed_world_initializations,
    )
    service = WorldGraphRetrievalService(
        projection=projection,
        sources=pg.sources,
        world_graph=pg.world_graph,
        contribution_reviews=pg.contribution_reviews,
        finalized_review_publications=lane.publications,
    )
    request = WorldGraphProjectionRequestV2(
        world_id=WORLD_ID,
        campaign_id=CAMPAIGN_ID,
        scope_mode="campaign",
        admissibility="gm",
        revision_pin=receipt.published_revision_id,
    )
    before = service.get_complete_object(request, object_id=NEW_OBJECT_ID)
    assert PROPERTY_ID in [p.assertion_id for p in before.property_assertions]
    retract_source(pg, next(iter(lane.snapshot.artifacts)))
    after = service.get_complete_object(request, object_id=NEW_OBJECT_ID)
    assert PROPERTY_ID not in [p.assertion_id for p in after.property_assertions]
    assert lane.publications.get_for_review(WORLD_ID, receipt.review_id) == receipt
    assert lane.publications.publish(lane.command) == receipt


def test_existing_http_host_refuses_internal_v2_replay_without_exposing_context(pg, monkeypatch):
    from fastapi.testclient import TestClient

    from dungeonmind.application.mind_turn import FixedClock
    from dungeonmind.service.api import create_publication_app
    from dungeonmind.service.publication_access import PublicationAccessBinding
    from tests.unit.test_contribution_review_v2 import REVIEWED_AT

    validator = SyntheticValidator()
    lane = setup_pg(pg, validator=validator)
    receipt = lane.publications.publish(lane.command)
    # Real repository reconstruction happens first. The application/route must
    # refuse the verified result before serializing it for transport.
    actual_get = pg.finalized_review_publications.get_for_review

    class SerializationSentinel(FinalizedReviewPublicationV2):
        def model_dump(self, *args, **kwargs):
            raise AssertionError("internal-v2-serialization-sentinel")

    def verified_get(world_id, review_id):
        verified = actual_get(world_id, review_id)
        return SerializationSentinel.model_construct(**verified.__dict__)

    monkeypatch.setattr(pg.finalized_review_publications, "get_for_review", verified_get)
    before = counts(pg)
    app = create_publication_app(
        review_repository=pg.contribution_reviews,
        world_graph_repository=pg.world_graph,
        publication_repository=pg.finalized_review_publications,  # default empty registry
        graph_reader=lane.reader,
        clock=FixedClock(REVIEWED_AT),
        access_binding=PublicationAccessBinding.from_secret(WORLD_ID, "synthetic-test-token"),
        readiness_probe=lambda: {"ready": True},
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/finalized-review-publications",
            json={
                "schema_version": "dm_finalized_review_publication_request_v1",
                "world_id": WORLD_ID,
                "review_id": lane.state.record.review_id,
            },
            headers={"Authorization": "Bearer synthetic-test-token"},
        )
    assert response.status_code == 403
    assert "admission_context" not in response.text
    assert "source_snapshot" not in response.text
    assert counts(pg) == before

    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "capability_denied"
    assert response.json()["error"]["message"] == "Publication access denied."
    assert response.json()["error"]["details"] == {
        "reason": "publication_receipt_transport_unsupported"
    }
    for secret in (
        "internal-v2-serialization-sentinel",
        lane.command.review_id,
        receipt.admission_context.source_snapshot.artifacts[0].source_artifact_id,
    ):
        assert secret not in response.text and secret not in str(response.headers)
    assert len(validator.calls) == 1
    assert lane.publications.publish(lane.command) == receipt


def test_v1_http_fresh_protected_custom_registry_denies_before_dispatch_then_library_works(pg):
    from fastapi.testclient import TestClient

    from dungeonmind.application.mind_turn import FixedClock
    from dungeonmind.application.review_publication import publish_finalized_review
    from dungeonmind.service.api import create_publication_app
    from dungeonmind.service.publication_access import PublicationAccessBinding
    from tests.unit.test_contribution_review_v2 import REVIEWED_AT

    validator = SyntheticValidator()
    lane = setup_pg(pg, validator=validator)
    before = counts(pg)
    app = create_publication_app(
        review_repository=pg.contribution_reviews,
        world_graph_repository=pg.world_graph,
        publication_repository=lane.publications,
        graph_reader=lane.reader,
        clock=FixedClock(REVIEWED_AT),
        access_binding=PublicationAccessBinding.from_secret(WORLD_ID, "synthetic-test-token"),
        readiness_probe=lambda: {"ready": True},
    )
    body = {
        "schema_version": "dm_finalized_review_publication_request_v1",
        "world_id": WORLD_ID,
        "review_id": lane.state.record.review_id,
    }
    with TestClient(app) as client:
        response = client.post(
            "/v1/finalized-review-publications",
            json=body,
            headers={"Authorization": "Bearer synthetic-test-token"},
        )
        assert response.status_code == 403 and response.headers["cache-control"] == "no-store"
        assert response.json()["error"]["code"] == "capability_denied"
        assert response.json()["error"]["details"] == {
            "reason": "publication_receipt_transport_unsupported"
        }
        override = client.post(
            "/v1/finalized-review-publications",
            json=dict(body, allowed_receipt_schemas=["dm_finalized_review_publication_v2"]),
            headers={"Authorization": "Bearer synthetic-test-token"},
        )
        assert override.status_code == 422
    assert counts(pg) == before and not validator.calls
    receipt = publish_finalized_review(
        WORLD_ID,
        lane.state.record.review_id,
        published_at=REVIEWED_AT,
        review_repository=pg.contribution_reviews,
        world_graph_repository=pg.world_graph,
        publication_repository=lane.publications,
        graph_reader=lane.reader,
    )
    assert isinstance(receipt, FinalizedReviewPublicationV2) and len(validator.calls) == 1


@pytest.mark.parametrize(
    "ceiling",
    [
        frozenset(),
        frozenset({"unknown"}),
        frozenset({"dm_finalized_review_publication_v1", "unknown"}),
        ["dm_finalized_review_publication_v2"],
    ],
)
def test_empty_unknown_or_mutable_ceiling_refuses_before_any_dispatch(pg, ceiling):
    from dungeonmind.application.review_publication import publish_finalized_review
    from dungeonmind.domain.errors import CapabilityDeniedError
    from tests.unit.test_contribution_review_v2 import REVIEWED_AT

    validator = SyntheticValidator()
    lane = setup_pg(pg, validator=validator)
    before = counts(pg)
    with pytest.raises(CapabilityDeniedError) as exc:
        publish_finalized_review(
            WORLD_ID,
            lane.state.record.review_id,
            published_at=REVIEWED_AT,
            review_repository=pg.contribution_reviews,
            world_graph_repository=pg.world_graph,
            publication_repository=lane.publications,
            graph_reader=lane.reader,
            allowed_receipt_schemas=ceiling,
        )
    assert exc.value.details == {"reason": "publication_receipt_transport_unsupported"}
    assert counts(pg) == before and not validator.calls


def test_route_guard_checks_actual_v1_type_before_serialization_even_if_app_faults(pg, monkeypatch):
    from fastapi.testclient import TestClient

    from dungeonmind.application.mind_turn import FixedClock
    from dungeonmind.service import api
    from dungeonmind.service.publication_access import PublicationAccessBinding
    from tests.unit.test_contribution_review_v2 import REVIEWED_AT

    lane = setup_pg(pg, validator=SyntheticValidator())
    receipt = lane.publications.publish(lane.command)

    class OutputSentinel(FinalizedReviewPublicationV2):
        def model_dump(self, *args, **kwargs):
            raise AssertionError("forbidden-v2-output-serialization")

    # Even a faulty app returning a V2 instance with a relabeled V1 tag cannot
    # make the actual route serialize the internal context.
    sentinel = OutputSentinel.model_construct(
        **dict(receipt.__dict__, schema_version="dm_finalized_review_publication_v1")
    )
    monkeypatch.setattr(api, "publish_finalized_review", lambda *args, **kwargs: sentinel)
    app = api.create_publication_app(
        review_repository=pg.contribution_reviews,
        world_graph_repository=pg.world_graph,
        publication_repository=lane.publications,
        graph_reader=lane.reader,
        clock=FixedClock(REVIEWED_AT),
        access_binding=PublicationAccessBinding.from_secret(WORLD_ID, "synthetic-test-token"),
        readiness_probe=lambda: {"ready": True},
    )
    before = counts(pg)
    with TestClient(app) as client:
        response = client.post(
            "/v1/finalized-review-publications",
            json={
                "schema_version": "dm_finalized_review_publication_request_v1",
                "world_id": WORLD_ID,
                "review_id": lane.state.record.review_id,
            },
            headers={"Authorization": "Bearer synthetic-test-token"},
        )
    assert response.status_code == 403 and response.headers["cache-control"] == "no-store"
    assert "forbidden-v2-output-serialization" not in response.text
    assert "admission_context" not in response.text and counts(pg) == before
