"""FT1b transport contract and access proofs."""

from __future__ import annotations

import hashlib
import hmac
import json
import traceback
from pathlib import Path

import pytest
from pydantic import ValidationError

from dungeonmind.application.fictional_time_query_service import (
    query_fictional_time_shadow_at_revision,
)
from dungeonmind.application.graph_snapshot import UnionGraphV1SnapshotReader
from dungeonmind.contracts.fictional_time import (
    FICTIONAL_TIME_QUERY_SCHEMA,
    FictionalTimeClaimBundle,
    FictionalTimeQuery,
)
from dungeonmind.contracts.fictional_time_transport import (
    FICTIONAL_TIME_SHADOW_QUERY_REQUEST_SCHEMA,
    FictionalTimeShadowQueryRequest,
)
from dungeonmind.contracts.graph import StoredGraphRevision
from dungeonmind.domain.errors import (
    CapabilityDeniedError,
    FictionalTimeIntegrityError,
)
from dungeonmind.service.fictional_time_access import (
    FictionalTimeQueryAccessBinding,
    authorize_fictional_time_query_request,
)

FIX = Path(__file__).resolve().parents[1] / "fixtures/fictional_time"
SECRET = "sentinel-fictional-time-bearer"
WORLD = "world:ft1-fictional-time"
REV = "rev:79c9791e9fcab4515d4cf5f09cc61f10"
TREE = "anchor:hempholm-tree-felled"
BEETLES = "anchor:hempholm-root-beetle-attack"


@pytest.fixture(scope="module")
def bundle() -> FictionalTimeClaimBundle:
    return FictionalTimeClaimBundle.model_validate(
        json.loads((FIX / "ft1-two-case-claim-bundle-v1.json").read_text())
    )


@pytest.fixture(scope="module")
def revision() -> StoredGraphRevision:
    return StoredGraphRevision.model_validate(
        json.loads((FIX / "ft1-two-case-graph-v1.json").read_text())
    )


def _query() -> dict[str, object]:
    return {
        "schema_version": FICTIONAL_TIME_QUERY_SCHEMA,
        "query_id": "query:hempholm-tree-before-beetles",
        "query_kind": "strict_before",
        "before_anchor_id": TREE,
        "after_anchor_id": BEETLES,
    }


def _request(
    bundle: FictionalTimeClaimBundle,
    *,
    world_id: str = WORLD,
    revision_id: str = REV,
) -> FictionalTimeShadowQueryRequest:
    bound = bundle
    if revision_id != bundle.graph_revision_id or world_id != bundle.world_id:
        bound = bundle.model_copy(
            update={
                "world_id": world_id,
                "graph_revision_id": revision_id,
            }
        )
    return FictionalTimeShadowQueryRequest(
        world_id=world_id,
        graph_revision_id=revision_id,
        claim_bundle=bound,
        query=FictionalTimeQuery.model_validate(_query()),
    )


def _request_json(bundle: FictionalTimeClaimBundle, **kwargs) -> dict[str, object]:
    return _request(bundle, **kwargs).model_dump(mode="json", exclude_unset=True)


def test_schema_constant_and_fixture_roundtrip(bundle, revision) -> None:
    assert FICTIONAL_TIME_SHADOW_QUERY_REQUEST_SCHEMA == (
        "dm_fictional_time_shadow_query_request_v1"
    )
    request = _request(bundle)
    assert request.world_id == revision.revision.world_id
    assert request.graph_revision_id == revision.revision.revision_id
    reloaded = FictionalTimeShadowQueryRequest.model_validate(
        request.model_dump(mode="json", exclude_unset=True)
    )
    assert reloaded == request


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda b: {**_request_json(b), "extra": 1}, "extra"),
        (lambda b: {**_request_json(b), "world_id": " "}, "non-blank"),
        (lambda b: {**_request_json(b), "graph_revision_id": ""}, "non-blank"),
        (
            lambda b: {
                **_request_json(b),
                "world_id": "world:other",
            },
            "claim_bundle.world_id",
        ),
        (
            lambda b: {
                **_request_json(b),
                "graph_revision_id": "rev:other",
            },
            "claim_bundle.graph_revision_id",
        ),
    ],
)
def test_request_validation_rejects_invalid_locators(
    bundle, mutator, match: str
) -> None:
    with pytest.raises(ValidationError, match=match):
        FictionalTimeShadowQueryRequest.model_validate(mutator(bundle))


def test_explicit_null_nested_query_field_rejected(bundle) -> None:
    body = _request_json(bundle)
    body["query"] = {**body["query"], "state_id": None}
    with pytest.raises(ValidationError, match="must be absent"):
        FictionalTimeShadowQueryRequest.model_validate(body)


def test_access_accepts_valid_bearer_as_deep_copy(bundle) -> None:
    request = _request(bundle)
    binding = FictionalTimeQueryAccessBinding.from_secret(WORLD, SECRET)
    authorized = authorize_fictional_time_query_request(
        request,
        authorization_header=f"Bearer {SECRET}",
        binding=binding,
    )
    assert authorized == request
    assert authorized is not request
    assert binding.bearer_token_sha256 == hashlib.sha256(SECRET.encode()).hexdigest()
    rendered = f"{binding!r} {binding!s}"
    assert SECRET not in rendered
    assert binding.bearer_token_sha256 not in rendered
    assert binding.world_id not in rendered


@pytest.mark.parametrize(
    "header",
    [None, "", "Basic x", "Bearer", "Bearer ", "Bearer wrong", f"Bearer {SECRET} "],
)
def test_access_denies_missing_malformed_and_wrong_tokens(
    bundle, header: str | None
) -> None:
    binding = FictionalTimeQueryAccessBinding.from_secret(WORLD, SECRET)
    with pytest.raises(CapabilityDeniedError) as raised:
        authorize_fictional_time_query_request(
            _request(bundle),
            authorization_header=header,
            binding=binding,
        )
    error = raised.value
    blob = "\n".join([str(error), repr(error), traceback.format_exc(), str(error.details)])
    assert SECRET not in blob
    assert error.details == {"reason": "fictional_time_query_access_denied"}


def test_access_denies_correct_token_for_wrong_world(bundle) -> None:
    binding = FictionalTimeQueryAccessBinding.from_secret(WORLD, SECRET)
    other = bundle.model_copy(update={"world_id": "world:other"})
    with pytest.raises(CapabilityDeniedError) as raised:
        authorize_fictional_time_query_request(
            _request(other, world_id="world:other"),
            authorization_header=f"Bearer {SECRET}",
            binding=binding,
        )
    assert str(raised.value) == "Fictional-time query access denied."


def test_access_uses_constant_time_digest_compare(bundle, monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    original = hmac.compare_digest

    def compare(left: str, right: str) -> bool:
        calls.append((left, right))
        return original(left, right)

    monkeypatch.setattr(
        "dungeonmind.service.fictional_time_access.hmac.compare_digest",
        compare,
    )
    binding = FictionalTimeQueryAccessBinding.from_secret(WORLD, SECRET)
    authorize_fictional_time_query_request(
        _request(bundle),
        authorization_header=f"Bearer {SECRET}",
        binding=binding,
    )
    assert calls == [(binding.bearer_token_sha256, binding.bearer_token_sha256)]


class _NeverCalledRepo:
    def get_revision(self, *_args, **_kwargs):
        raise AssertionError("repository must not be called")


def test_post_validation_null_query_mutation_fails_reload(bundle) -> None:
    request = _request(bundle)
    poisoned = request.model_copy(
        update={
            "query": request.query.model_copy(update={"state_id": None}),
        }
    )
    with pytest.raises(FictionalTimeIntegrityError) as raised:
        query_fictional_time_shadow_at_revision(
            poisoned,
            world_graph_repository=_NeverCalledRepo(),
            graph_reader=UnionGraphV1SnapshotReader(),
        )
    assert raised.value.reason == "request_reload_validation"
