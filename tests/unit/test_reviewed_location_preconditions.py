"""Location authority is explicit and does not broaden legacy NPC authority."""

import copy

import pytest
from pydantic import ValidationError

from dungeonmind.application.review_publication import (
    validate_reviewed_identity_publication_preconditions,
)
from dungeonmind.contracts.contribution_review_v2 import (
    ReviewedIdentityPublicationPreconditionsV1,
    ReviewedIdentityPublicationPreconditionsV2,
)
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.memory import InMemorySourceRepository
from tests.unit.test_contribution_review_v2 import _guarded_identity_fixture


def fixture():
    intent, parent, decision, artifact, revision = _guarded_identity_fixture()
    payload = copy.deepcopy(parent.graph_payload)
    guard = intent.reviewed_identity_preconditions
    target = next(o for o in payload["objects"] if o["object_id"] == guard.target_object_id)
    target["kind"] = "dnd5e:location"
    parent = parent.model_copy(update={"graph_payload": payload})
    data = guard.model_dump(mode="json")
    data.update(
        schema_version="dm_reviewed_identity_publication_preconditions_v2",
        target_kind="dnd5e:location",
        target_object_sha256=canonical_sha256(target),
    )
    guard = ReviewedIdentityPublicationPreconditionsV2.model_validate(data)
    sources = InMemorySourceRepository()
    sources.put_artifact(artifact)
    sources.put_revision(revision)
    snapshot = sources.get_provenance_snapshot(
        artifact_ids=[artifact.source_artifact_id], revision_ids=[revision.source_revision_id]
    )
    return guard, parent, decision, snapshot


def test_exact_reviewed_location_preconditions_pass():
    guard, parent, decision, sources = fixture()
    validate_reviewed_identity_publication_preconditions(
        guard, parent=parent, decisions=[decision], sources=sources
    )


def test_legacy_guard_does_not_gain_location_authority():
    guard, parent, decision, sources = fixture()
    data = guard.model_dump(mode="json")
    data.pop("target_kind")
    data["schema_version"] = "dm_reviewed_identity_publication_preconditions_v1"
    legacy = ReviewedIdentityPublicationPreconditionsV1.model_validate(data)
    with pytest.raises(PersistenceIntegrityError):
        validate_reviewed_identity_publication_preconditions(
            legacy, parent=parent, decisions=[decision], sources=sources
        )


@pytest.mark.parametrize("kind", ["dnd5e:npc", "dnd5e:item", "dnd5e:party"])
def test_location_guard_refuses_other_kinds_even_with_matching_fingerprint(kind):
    guard, parent, decision, sources = fixture()
    payload = copy.deepcopy(parent.graph_payload)
    target = next(o for o in payload["objects"] if o["object_id"] == guard.target_object_id)
    target["kind"] = kind
    parent = parent.model_copy(update={"graph_payload": payload})
    guard = guard.model_copy(update={"target_object_sha256": canonical_sha256(target)})
    with pytest.raises(PersistenceIntegrityError):
        validate_reviewed_identity_publication_preconditions(
            guard, parent=parent, decisions=[decision], sources=sources
        )


@pytest.mark.parametrize("field", ["schema_version", "target_kind"])
def test_location_guard_rejects_unrecognized_contract(field):
    guard, *_ = fixture()
    data = guard.model_dump(mode="json")
    data[field] = "unrecognized"
    with pytest.raises(ValidationError):
        ReviewedIdentityPublicationPreconditionsV2.model_validate(data)


@pytest.mark.parametrize("campaign_scope", [None, "unrelated-campaign"])
def test_location_target_scope_is_world_or_same_campaign(campaign_scope):
    guard, parent, decision, sources = fixture()
    payload = copy.deepcopy(parent.graph_payload)
    target = next(o for o in payload["objects"] if o["object_id"] == guard.target_object_id)
    target["assertion_metadata"]["campaign_scope"] = campaign_scope
    parent = parent.model_copy(update={"graph_payload": payload})
    guard = guard.model_copy(update={"target_object_sha256": canonical_sha256(target)})
    if campaign_scope is None:
        validate_reviewed_identity_publication_preconditions(
            guard, parent=parent, decisions=[decision], sources=sources
        )
    else:
        with pytest.raises(PersistenceIntegrityError):
            validate_reviewed_identity_publication_preconditions(
                guard, parent=parent, decisions=[decision], sources=sources
            )
