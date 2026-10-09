"""Tests for the narrow finalized-review publication request contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dungeonmind.contracts import (
    FINALIZED_REVIEW_PUBLICATION_REQUEST_SCHEMA,
    FinalizedReviewPublicationRequest,
)


def test_canonical_request_has_only_public_identity_fields() -> None:
    request = FinalizedReviewPublicationRequest(
        world_id="world:synthetic-gatewatch",
        review_id="review:example",
    )
    assert request.model_dump() == {
        "schema_version": FINALIZED_REVIEW_PUBLICATION_REQUEST_SCHEMA,
        "world_id": "world:synthetic-gatewatch",
        "review_id": "review:example",
    }


@pytest.mark.parametrize("field", ["world_id", "review_id"])
def test_blank_identity_is_rejected(field: str) -> None:
    values = {"world_id": "world:ok", "review_id": "review:ok"}
    values[field] = " \t"
    with pytest.raises(ValidationError):
        FinalizedReviewPublicationRequest.model_validate(values)


@pytest.mark.parametrize(
    "field",
    [
        "published_at",
        "operation_id",
        "expected_parent_revision_id",
        "expected_published_revision_id",
        "confirmation_id",
        "reviewer_id",
        "review_intent_sha256",
        "reviewed_contribution_id",
        "graph_schema",
        "graph_payload",
        "graph_payload_sha256",
        "status",
        "retry",
        "force",
        "rebase",
    ],
)
def test_authority_and_graph_fields_are_rejected_as_extras(field: str) -> None:
    values = {
        "world_id": "world:synthetic-gatewatch",
        "review_id": "review:example",
        field: "sentinel-authority-input",
    }
    with pytest.raises(ValidationError) as raised:
        FinalizedReviewPublicationRequest.model_validate(values)
    assert "sentinel-authority-input" not in str(raised.value)


def test_request_contract_does_not_accept_metadata_or_token() -> None:
    with pytest.raises(ValidationError):
        FinalizedReviewPublicationRequest.model_validate(
            {
                "world_id": "world:synthetic-gatewatch",
                "review_id": "review:example",
                "metadata": {"token": "sentinel-token"},
                "token": "sentinel-token",
            }
        )


def _review_command_fixture(*, guarded=True):
    from dungeonmind.application.review_materialization_v6 import materialize_finalized_review_v6
    from dungeonmind.contracts.review_publication import (
        FinalizedReviewPublicationCommand,
        GuardedFinalizedReviewPublicationCommand,
    )
    from dungeonmind.domain.canonical import canonical_sha256
    from dungeonmind.domain.revision_ids import compute_revision_id
    from tests.unit.test_contribution_review_v2 import (
        _build_review_state,
        _guarded_identity_fixture,
        _intent,
        _reader,
        _stored_parent,
        _submission,
    )

    if guarded:
        intent, parent, decision, artifact, revision = _guarded_identity_fixture()
    else:
        parent = _stored_parent()
        intent = _intent(parent=parent)
        decision = artifact = revision = None
    state = _build_review_state(_submission(intent))
    record = state.record
    result = materialize_finalized_review_v6(state, parent=parent, graph_reader=_reader())
    digest = canonical_sha256(result.graph_payload)
    cls = GuardedFinalizedReviewPublicationCommand if guarded else FinalizedReviewPublicationCommand
    extra = (
        {"reviewed_identity_preconditions": intent.reviewed_identity_preconditions}
        if guarded
        else {}
    )
    command = cls(
        world_id=record.world_id,
        review_id=record.review_id,
        reviewed_contribution_id=record.reviewed_contribution_id,
        reviewed_contribution_sha256=record.reviewed_contribution_sha256,
        review_intent_sha256=record.review_intent_sha256,
        confirmation_id=record.confirmation_id,
        operation_id=record.operation_id,
        expected_parent_revision_id=parent.revision.revision_id,
        parent_graph_payload_sha256=parent.revision.graph_payload_sha256,
        expected_published_revision_id=compute_revision_id(
            world_id=record.world_id,
            parent_revision_id=parent.revision.revision_id,
            operation_ids=[record.operation_id],
            graph_schema=result.graph_schema,
            graph_payload_sha256=digest,
        ),
        graph_schema=result.graph_schema,
        graph_payload=result.graph_payload,
        graph_payload_sha256=digest,
        requested_published_at=record.reviewed_at,
        **extra,
    )
    return command, state, parent, decision, artifact, revision


def test_guarded_internal_command_roundtrip_and_no_downgrade():
    from dungeonmind.application.review_publication import validate_guarded_command_binding
    from dungeonmind.contracts.review_publication import decode_finalized_review_publication_command
    from dungeonmind.domain.errors import IdempotencyConflictError

    command, state, *_ = _review_command_fixture()
    assert decode_finalized_review_publication_command(command.model_dump(mode="json")) == command
    stripped = command.model_dump(mode="json")
    del stripped["reviewed_identity_preconditions"]
    with pytest.raises(IdempotencyConflictError):
        validate_guarded_command_binding(
            decode_finalized_review_publication_command(stripped), state.record
        )
    changed = command.model_copy(
        update={
            "reviewed_identity_preconditions": command.reviewed_identity_preconditions.model_copy(
                update={"decision_sha256": "a" * 64}
            )
        }
    )
    with pytest.raises(IdempotencyConflictError):
        validate_guarded_command_binding(changed, state.record)


def test_entire_legacy_publication_family_canonical_bytes_keep_frozen_hashes():
    from dungeonmind.contracts.review_publication import FinalizedReviewPublication
    from dungeonmind.domain.canonical import canonical_sha256
    from tests.unit.test_contribution_review_v2 import _intent

    command, state, *_ = _review_command_fixture(guarded=False)
    values = command.model_dump(mode="python")
    values.pop("schema_version")
    values.pop("graph_payload")
    values["published_revision_id"] = values.pop("expected_published_revision_id")
    values["published_at"] = values.pop("requested_published_at")
    receipt = FinalizedReviewPublication(**values)
    expected = {
        "intent": "bbc90fd504e81b9a40364444e92d9ee7d82e9003da37751ee9cfe62cfdcc944c",
        "record": "744c7684f6277766a5ad1d78deed6f14ff1172105db12f8ed1674ea93909b853",
        "command": "4687aea14e426f1a327461a8f9384339286f7b0a8affe29d259c8f2f5416627c",
        "receipt": "7fe762eff7dd115e21cb3931a6211fa7488359e97f356e05c4da9a082f89f15a",
    }
    assert {
        name: canonical_sha256(value.model_dump(mode="json"))
        for name, value in [
            ("intent", _intent()),
            ("record", state.record),
            ("command", command),
            ("receipt", receipt),
        ]
    } == expected
