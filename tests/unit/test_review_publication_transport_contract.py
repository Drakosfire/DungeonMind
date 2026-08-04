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
