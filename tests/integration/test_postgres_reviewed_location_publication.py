"""Exercise location preconditions inside the actual publication transaction."""

import copy

import pytest

import tests.integration.test_postgres_review_publication_v6 as publication
import tests.unit.test_contribution_review_v2 as review_fixture
from dungeonmind.contracts.contribution_review_v2 import (
    GuardedContributionReviewIntentV2,
    ReviewedIdentityPublicationPreconditionsV2,
    derive_review_intent_sha256_v2,
)
from dungeonmind.domain.canonical import canonical_sha256

pytestmark = pytest.mark.integration


def prepare_location(pg, monkeypatch):
    original = review_fixture._guarded_identity_fixture

    def fixture(parent_override=None):
        intent, parent, decision, artifact, revision = original(parent_override)
        payload = copy.deepcopy(parent.graph_payload)
        old_guard = intent.reviewed_identity_preconditions
        target = next(o for o in payload["objects"] if o["object_id"] == old_guard.target_object_id)
        target["kind"] = "dnd5e:location"
        parent = parent.model_copy(update={"graph_payload": payload})
        data = old_guard.model_dump(mode="json")
        data.update(
            schema_version="dm_reviewed_identity_publication_preconditions_v2",
            target_kind="dnd5e:location",
            target_object_sha256=canonical_sha256(target),
        )
        guard = ReviewedIdentityPublicationPreconditionsV2.model_validate(data)
        fields = {
            name: getattr(intent, name)
            for name in (
                "operation_id",
                "world_id",
                "campaign_id",
                "plan_ref",
                "candidate_contribution",
                "identity_proposals",
                "identity_verdicts",
                "assertion_verdicts",
                "reviewer_id",
                "reviewed_at",
            )
        }
        digest = derive_review_intent_sha256_v2(**fields, reviewed_identity_preconditions=guard)
        updated = intent.model_dump(mode="json")
        updated.update(
            reviewed_identity_preconditions=guard.model_dump(mode="json"),
            review_intent_sha256=digest,
        )
        return (
            GuardedContributionReviewIntentV2.model_validate(updated),
            parent,
            decision,
            artifact,
            revision,
        )

    monkeypatch.setattr(review_fixture, "_guarded_identity_fixture", fixture)
    return publication._guarded_pg_review(pg)


def test_location_publication_and_durable_receipt_replay(pg, monkeypatch):
    state, parent, _, _ = prepare_location(pg, monkeypatch)
    receipt = publication._publish(pg, state.record.review_id)
    assert publication._publish(pg, state.record.review_id) == receipt
    assert pg.world_graph.get_revision(publication.WORLD_ID, parent.revision.revision_id) == parent
    assert (
        pg.world_graph.get_head(publication.WORLD_ID).head_revision_id
        != parent.revision.revision_id
    )


@pytest.mark.parametrize("kind", ["decision", "source"])
def test_location_publication_refuses_changed_authority_without_partial_state(
    pg, monkeypatch, kind
):
    from dungeonmind.domain.errors import PersistenceIntegrityError

    state, parent, decision, artifact = prepare_location(pg, monkeypatch)
    publication._mutate_guard_authority(pg, decision, artifact, kind)
    with pytest.raises(PersistenceIntegrityError):
        publication._publish(pg, state.record.review_id)
    assert (
        pg.world_graph.get_head(publication.WORLD_ID).head_revision_id
        == parent.revision.revision_id
    )
    assert pg.world_graph.get_revision(publication.WORLD_ID, parent.revision.revision_id) == parent
    assert (
        pg.finalized_review_publications.get_for_review(
            publication.WORLD_ID, state.record.review_id
        )
        is None
    )
