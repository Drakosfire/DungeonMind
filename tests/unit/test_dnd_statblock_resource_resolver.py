"""Unit proofs for the exact DungeonMind statblock resource resolver."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("httpx")
import httpx

from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind_dnd.contracts.mechanics_resources import DndMechanicsResourceRef
from dungeonmind_dnd.integration.statblock_resource_resolver import (
    STATBLOCKS_AUTH_HEADER,
    STATBLOCKS_BASE_URL_ENV,
    STATBLOCKS_DEFAULT_TIMEOUT_SECONDS,
    STATBLOCKS_INTERNAL_API_KEY_ENV,
    STATBLOCKS_MAX_RESPONSE_BODY_BYTES,
    STATBLOCKS_MEDIA_TYPE,
    STATBLOCKS_PROVIDER_ID,
    STATBLOCKS_RESOURCE_SCHEMA,
    STATBLOCKS_ROUTE_PREFIX,
    STATBLOCKS_TIMEOUT_SECONDS_ENV,
    DndStatblockResourceResolver,
    DndStatblockResourceResolverConfig,
    DndStatblockResourceResolverError,
    _resolver_for_test,
    load_dnd_statblock_resource_resolver_config,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures/dungeonmind_dnd/dungeonmind-statblock-exact-revision-v1.json"
)
SECRET = "dungeonbuddy-internal-secret-sentinel"
BASE_URL = "https://dungeonbuddy.invalid/"
EXPECTED_DIGEST = "935dc0dff1ac7cc8405836764469761a1d26e9e38dd74cd856b8a8a31f0fae51"


def _provider_response() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _resource_ref() -> DndMechanicsResourceRef:
    return DndMechanicsResourceRef(
        ruleset_id="dnd5e",
        provider_id=STATBLOCKS_PROVIDER_ID,
        resource_id="sb_000001",
        resource_revision="rev_000002",
        resource_schema=STATBLOCKS_RESOURCE_SCHEMA,
        media_type=STATBLOCKS_MEDIA_TYPE,
        payload_sha256=EXPECTED_DIGEST,
    )


def _config() -> DndStatblockResourceResolverConfig:
    return DndStatblockResourceResolverConfig(
        base_url=BASE_URL,
        internal_api_key=SECRET,
        timeout_seconds=12,
    )


def _resolver(
    handler,
) -> tuple[DndStatblockResourceResolver, list[httpx.Request]]:
    calls: list[httpx.Request] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    resolver = _resolver_for_test(
        config=_config(),
        transport=httpx.MockTransport(recording_handler),
    )
    return resolver, calls


def _error_surfaces(error: DndStatblockResourceResolverError) -> tuple[str, ...]:
    return (
        str(error),
        repr(error),
        json.dumps(error.details, sort_keys=True),
    )


def test_captured_fixture_maps_observed_fields_and_canonical_mechanics() -> None:
    provider_response = _provider_response()
    resolver, calls = _resolver(
        lambda _: httpx.Response(200, json=provider_response)
    )
    try:
        observed = resolver.resolve(_resource_ref())
    finally:
        resolver.close()

    assert observed is not None
    assert observed["schema_version"] == "dmdnd_mechanics_resource_envelope_v1"
    observed_ref = observed["resource_ref"]
    assert observed_ref == {
        "schema_version": "dmdnd_mechanics_resource_ref_v1",
        "ruleset_id": "dnd5e",
        "provider_id": STATBLOCKS_PROVIDER_ID,
        "resource_id": "sb_000001",
        "resource_revision": "rev_000002",
        "resource_schema": STATBLOCKS_RESOURCE_SCHEMA,
        "media_type": STATBLOCKS_MEDIA_TYPE,
        "payload_sha256": EXPECTED_DIGEST,
    }
    expected_payload = json.loads(provider_response["canonical_definition"])
    assert observed["mechanics_payload"] == expected_payload
    assert canonical_sha256(expected_payload) == EXPECTED_DIGEST
    assert "definition" not in observed
    assert len(calls) == 1
    assert calls[0].method == "GET"
    assert calls[0].url == (
        f"{BASE_URL.rstrip('/')}{STATBLOCKS_ROUTE_PREFIX}/"
        "sb_000001/revisions/rev_000002"
    )
    assert calls[0].headers[STATBLOCKS_AUTH_HEADER] == SECRET


def test_fixture_mapping_does_not_use_definition_fallback() -> None:
    provider_response = _provider_response()
    provider_response["definition"]["identity"]["name"] = SECRET
    resolver, _ = _resolver(
        lambda _: httpx.Response(200, json=provider_response)
    )
    try:
        observed = resolver.resolve(_resource_ref())
    finally:
        resolver.close()

    assert observed is not None
    assert observed["mechanics_payload"]["identity"]["name"] == "Ironhide Brute"
    assert SECRET not in json.dumps(observed, sort_keys=True)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_id", "other.statblocks"),
        ("resource_schema", "dungeonmind.dungeonbuddy-statblocks.1.0.1"),
        ("resource_id", "generic:resource"),
        ("resource_revision", "generic:revision"),
    ],
)
def test_unsupported_ref_is_a_zero_call_miss(field: str, value: str) -> None:
    resolver, calls = _resolver(
        lambda _: pytest.fail("unsupported ref must not issue HTTP")
    )
    ref = _resource_ref().model_copy(update={field: value})
    try:
        assert resolver.resolve(ref) is None
    finally:
        resolver.close()
    assert calls == []


@pytest.mark.parametrize("status_code", [404, 410])
def test_exact_provider_miss_is_one_call_and_returns_none(status_code: int) -> None:
    resolver, calls = _resolver(
        lambda _: httpx.Response(status_code, text="secret provider body")
    )
    try:
        assert resolver.resolve(_resource_ref()) is None
    finally:
        resolver.close()
    assert len(calls) == 1


@pytest.mark.parametrize("status_code", [302, 401, 403, 408, 409, 422, 429, 500, 503])
def test_non_miss_status_is_one_shot_and_sanitized(status_code: int, caplog) -> None:
    redirect_target_calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/credential-leak-target":
            redirect_target_calls.append(request)
        return httpx.Response(
            status_code,
            headers={"location": "https://dungeonbuddy.invalid/credential-leak-target"},
            text=SECRET,
        )

    resolver, calls = _resolver(handler)
    try:
        with pytest.raises(DndStatblockResourceResolverError) as raised:
            resolver.resolve(_resource_ref())
    finally:
        resolver.close()

    error = raised.value
    assert error.category == "resolver_unavailable"
    assert error.status_code == status_code
    assert len(calls) == 1
    assert redirect_target_calls == []
    assert all(SECRET not in surface for surface in _error_surfaces(error))
    assert SECRET not in caplog.text
    assert error.__cause__ is None
    assert error.__context__ is None


@pytest.mark.parametrize(
    "transport_error",
    [
        httpx.ConnectError(SECRET),
        httpx.ReadTimeout(SECRET),
    ],
)
def test_transport_failure_is_one_shot_and_has_no_exception_context(
    transport_error: httpx.HTTPError,
) -> None:
    resolver, calls = _resolver(lambda _: (_ for _ in ()).throw(transport_error))
    try:
        with pytest.raises(DndStatblockResourceResolverError) as raised:
            resolver.resolve(_resource_ref())
    finally:
        resolver.close()

    error = raised.value
    assert error.category == "resolver_unavailable"
    assert len(calls) == 1
    assert all(SECRET not in surface for surface in _error_surfaces(error))
    assert error.__cause__ is None
    assert error.__context__ is None


@pytest.mark.parametrize(
    "body",
    [
        SECRET.encode("utf-8"),
        b"[]",
    ],
)
def test_invalid_response_body_is_closed_without_echoing_body(body: bytes) -> None:
    resolver, calls = _resolver(
        lambda _: httpx.Response(200, content=body)
    )
    try:
        with pytest.raises(DndStatblockResourceResolverError) as raised:
            resolver.resolve(_resource_ref())
    finally:
        resolver.close()

    error = raised.value
    assert error.category == "resolver_response_invalid"
    assert len(calls) == 1
    assert all(SECRET not in surface for surface in _error_surfaces(error))


@pytest.mark.parametrize(
    "body",
    [
        b'{"diagnostic":NaN}',
        b'{"canonical_definition":"{}","canonical_definition":"{}"}',
        json.dumps(
            {"canonical_definition": '{"diagnostic":NaN}'},
            separators=(",", ":"),
        ).encode("utf-8"),
        json.dumps(
            {
                "canonical_definition": (
                    '{"identity":{"name":"Ironhide Brute"},'
                    '"identity":{"name":"ignored"}}'
                )
            },
            separators=(",", ":"),
        ).encode("utf-8"),
    ],
)
def test_strict_json_rejects_non_finite_constants_and_duplicate_keys(
    body: bytes,
) -> None:
    resolver, calls = _resolver(lambda _: httpx.Response(200, content=body))
    try:
        with pytest.raises(DndStatblockResourceResolverError) as raised:
            resolver.resolve(_resource_ref())
    finally:
        resolver.close()

    assert raised.value.category == "resolver_response_invalid"
    assert len(calls) == 1


def test_invalid_canonical_definition_is_not_repaired() -> None:
    resolver, calls = _resolver(
        lambda _: httpx.Response(
            200,
            json={"canonical_definition": "not-json"},
        )
    )
    try:
        observed = resolver.resolve(_resource_ref())
    finally:
        resolver.close()

    assert observed is not None
    assert observed["mechanics_payload"] == "not-json"
    assert len(calls) == 1


def test_declared_oversized_response_is_rejected_before_reading_body() -> None:
    resolver, calls = _resolver(
        lambda _: httpx.Response(
            200,
            headers={"content-length": str(STATBLOCKS_MAX_RESPONSE_BODY_BYTES + 1)},
            content=SECRET.encode("utf-8"),
        )
    )
    try:
        with pytest.raises(DndStatblockResourceResolverError) as raised:
            resolver.resolve(_resource_ref())
    finally:
        resolver.close()

    assert raised.value.category == "resolver_response_invalid"
    assert len(calls) == 1
    assert all(SECRET not in surface for surface in _error_surfaces(raised.value))


def test_streamed_oversized_response_stops_after_first_over_limit_chunk() -> None:
    yielded: list[bytes] = []

    class OversizedStream(httpx.SyncByteStream):
        def __iter__(self):
            first = b"x" * STATBLOCKS_MAX_RESPONSE_BODY_BYTES
            second = SECRET.encode("utf-8")
            yielded.append(first)
            yield first
            yielded.append(second)
            yield second
            yielded.append(b"should-not-be-read")
            yield b"should-not-be-read"

    resolver, calls = _resolver(
        lambda _: httpx.Response(200, stream=OversizedStream())
    )
    try:
        with pytest.raises(DndStatblockResourceResolverError) as raised:
            resolver.resolve(_resource_ref())
    finally:
        resolver.close()

    assert raised.value.category == "resolver_response_invalid"
    assert len(calls) == 1
    assert len(yielded) == 2
    assert all(SECRET not in surface for surface in _error_surfaces(raised.value))


@pytest.mark.parametrize(
    ("value", "environ"),
    [
        ("", {}),
        ("ftp://provider.invalid", {}),
        ("https://", {}),
        ("https://user:pass@provider.invalid", {}),
        ("https://provider.invalid/path", {}),
        ("https://provider.invalid?secret=query", {}),
        ("https://provider.invalid#fragment", {}),
        ("https://provider.invalid", {STATBLOCKS_TIMEOUT_SECONDS_ENV: "nan"}),
        ("https://provider.invalid", {STATBLOCKS_TIMEOUT_SECONDS_ENV: "0"}),
        (
            "https://provider.invalid",
            {STATBLOCKS_TIMEOUT_SECONDS_ENV: "121"},
        ),
    ],
)
def test_invalid_configuration_fails_without_secret_or_http(
    value: str,
    environ: dict[str, str],
) -> None:
    values = {
        STATBLOCKS_BASE_URL_ENV: value,
        STATBLOCKS_INTERNAL_API_KEY_ENV: SECRET,
        **environ,
    }
    with pytest.raises(DndStatblockResourceResolverError) as raised:
        load_dnd_statblock_resource_resolver_config(environ=values)

    error = raised.value
    assert error.category == "resolver_misconfigured"
    assert all(SECRET not in surface for surface in _error_surfaces(error))
    assert error.__cause__ is None
    assert error.__context__ is None


def test_configuration_is_frozen_redacted_and_uses_grounded_default() -> None:
    config = load_dnd_statblock_resource_resolver_config(
        environ={
            STATBLOCKS_BASE_URL_ENV: BASE_URL,
            STATBLOCKS_INTERNAL_API_KEY_ENV: SECRET,
        }
    )
    assert config.base_url == BASE_URL.rstrip("/")
    assert config.timeout_seconds == STATBLOCKS_DEFAULT_TIMEOUT_SECONDS
    assert SECRET not in repr(config)
    with pytest.raises((AttributeError, TypeError)):
        config.base_url = "https://changed.invalid"


def test_repeated_resolution_is_fresh_and_observed_mapping_is_isolated() -> None:
    provider_response = _provider_response()
    resolver, calls = _resolver(
        lambda _: httpx.Response(200, json=provider_response)
    )
    try:
        first = resolver.resolve(_resource_ref())
        assert first is not None
        first["mechanics_payload"]["identity"]["name"] = "client mutation"
        second = resolver.resolve(_resource_ref())
    finally:
        resolver.close()

    assert second is not None
    assert second["mechanics_payload"]["identity"]["name"] == "Ironhide Brute"
    assert len(calls) == 2
