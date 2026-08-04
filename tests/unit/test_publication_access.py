"""Tests for the one-world bearer access boundary."""

from __future__ import annotations

import hashlib
import hmac
import traceback

import pytest

from dungeonmind.contracts import FinalizedReviewPublicationRequest
from dungeonmind.domain.errors import CapabilityDeniedError
from dungeonmind.service.publication_access import (
    PublicationAccessBinding,
    authorize_publication_request,
)

SECRET = "sentinel-publication-secret"


def _request(world_id: str = "world:synthetic-gatewatch") -> FinalizedReviewPublicationRequest:
    return FinalizedReviewPublicationRequest(world_id=world_id, review_id="review:example")


def test_correct_token_and_world_are_accepted_as_a_copy() -> None:
    request = _request()
    binding = PublicationAccessBinding.from_secret(request.world_id, SECRET)
    authorized = authorize_publication_request(
        request,
        authorization_header=f"Bearer {SECRET}",
        binding=binding,
    )
    assert authorized == request
    assert authorized is not request
    assert binding.bearer_token_sha256 == hashlib.sha256(SECRET.encode()).hexdigest()
    representation = f"{binding!r} {binding!s}"
    assert SECRET not in representation
    assert binding.bearer_token_sha256 not in representation
    assert binding.world_id not in representation


@pytest.mark.parametrize(
    "header",
    [None, "", "Basic sentinel", "Bearer", "Bearer ", "Bearer wrong", f"Bearer {SECRET} "],
)
def test_missing_malformed_blank_and_wrong_tokens_are_generic_denials(
    header: str | None,
) -> None:
    binding = PublicationAccessBinding.from_secret(
        "world:synthetic-gatewatch",
        SECRET,
    )
    with pytest.raises(CapabilityDeniedError) as raised:
        authorize_publication_request(
            _request(),
            authorization_header=header,
            binding=binding,
        )
    error = raised.value
    rendered = "\n".join(
        [
            str(error),
            repr(error),
            traceback.format_exc(),
            str(error.details),
        ]
    )
    assert SECRET not in rendered
    assert error.details == {"reason": "publication_access_denied"}


def test_correct_token_for_wrong_world_is_denied_without_world_or_token_oracle() -> None:
    binding = PublicationAccessBinding.from_secret(
        "world:synthetic-gatewatch",
        SECRET,
    )
    with pytest.raises(CapabilityDeniedError) as raised:
        authorize_publication_request(
            _request("world:other"),
            authorization_header=f"Bearer {SECRET}",
            binding=binding,
        )
    assert str(raised.value) == "Publication access denied."
    assert raised.value.details == {"reason": "publication_access_denied"}


def test_digest_is_compared_with_constant_time_comparison(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    original_compare = hmac.compare_digest

    def compare(left: str, right: str) -> bool:
        calls.append((left, right))
        return original_compare(left, right)

    monkeypatch.setattr(
        "dungeonmind.service.publication_access.hmac.compare_digest",
        compare,
    )
    binding = PublicationAccessBinding.from_secret("world:synthetic-gatewatch", SECRET)
    authorize_publication_request(
        _request(),
        authorization_header=f"Bearer {SECRET}",
        binding=binding,
    )
    assert calls == [(binding.bearer_token_sha256, binding.bearer_token_sha256)]


def test_secret_configuration_is_required_but_not_stored() -> None:
    with pytest.raises(ValueError):
        PublicationAccessBinding.from_secret("world:synthetic-gatewatch", " ")
    with pytest.raises(ValueError):
        PublicationAccessBinding.from_secret(" ", SECRET)
