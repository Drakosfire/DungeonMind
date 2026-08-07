"""Exact DungeonMind statblock-v1 mechanics-resource resolution.

This module owns one concrete provider adapter.  It admits only the exact
DungeonMind statblock identity grammar, performs one bounded authenticated
request, and returns an observed mapping for the unchanged B.3a seam to
reload and adjudicate.
"""

# pyright: reportMissingImports=false

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from ..contracts.mechanics_resources import DndMechanicsResourceRef

STATBLOCKS_BASE_URL_ENV = "DUNGEONMIND_STATBLOCKS_BASE_URL"
STATBLOCKS_INTERNAL_API_KEY_ENV = "DUNGEONMIND_STATBLOCKS_INTERNAL_API_KEY"
STATBLOCKS_TIMEOUT_SECONDS_ENV = "DUNGEONMIND_STATBLOCKS_TIMEOUT_SECONDS"

STATBLOCKS_PROVIDER_ID = "dungeonmind.statblocks"
STATBLOCKS_RESOURCE_SCHEMA = "dungeonmind.dungeonbuddy-statblocks.1.0.0"
STATBLOCKS_MEDIA_TYPE = "application/json"
STATBLOCKS_ROUTE_PREFIX = "/api/internal/dungeonbuddy/v1/statblocks"
STATBLOCKS_AUTH_HEADER = "X-DungeonBuddy-Internal-Key"
STATBLOCKS_DEFAULT_TIMEOUT_SECONDS = 90.0
STATBLOCKS_MAX_TIMEOUT_SECONDS = 120.0
STATBLOCKS_MAX_RESPONSE_BODY_BYTES = 1_048_576

_SUPPORTED_SCHEMES = frozenset({"http", "https"})
_STATBLOCK_ID = re.compile(r"^sb_[a-z0-9]+$")
_REVISION_ID = re.compile(r"^rev_[a-z0-9]+$")

ResolverFailureCategory = Literal[
    "resolver_misconfigured",
    "resolver_unavailable",
    "resolver_response_invalid",
]


class DndStatblockResourceResolverError(Exception):
    """Sanitized resolver-owned failure with no provider diagnostics."""

    def __init__(
        self,
        category: ResolverFailureCategory,
        *,
        status_code: int | None = None,
    ) -> None:
        details: dict[str, str | int] = {"category": category}
        if status_code is not None:
            details["status_code"] = status_code
        self.category = category
        self.status_code = status_code
        self.details = details
        super().__init__("DungeonMind statblock resource resolution failed.")


def _resolver_failure(
    category: ResolverFailureCategory,
    *,
    status_code: int | None = None,
) -> DndStatblockResourceResolverError:
    return DndStatblockResourceResolverError(category, status_code=status_code)


def _invalid_config() -> DndStatblockResourceResolverError:
    return _resolver_failure("resolver_misconfigured")


def _normalize_base_url(value: str) -> str:
    if not isinstance(value, str):
        raise _invalid_config() from None
    cleaned = value.strip()
    try:
        parsed = urlparse(cleaned)
        has_host = bool(parsed.hostname)
        has_credentials = parsed.username is not None or parsed.password is not None
        has_forbidden_suffix = bool(
            parsed.path.rstrip("/") or parsed.params or parsed.query or parsed.fragment
        )
        if (
            parsed.scheme not in _SUPPORTED_SCHEMES
            or not has_host
            or has_credentials
            or has_forbidden_suffix
        ):
            raise ValueError
        # Accessing port rejects malformed ports without exposing the value.
        _ = parsed.port
    except (TypeError, ValueError):
        raise _invalid_config() from None
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _normalize_api_key(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid_config() from None
    return value.strip()


def _normalize_timeout(value: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise _invalid_config() from None
    timeout = float(value)
    if (
        not math.isfinite(timeout)
        or timeout <= 0
        or timeout > STATBLOCKS_MAX_TIMEOUT_SECONDS
    ):
        raise _invalid_config() from None
    return timeout


def _parse_timeout(value: str | None) -> float:
    if value is None or not value.strip():
        return STATBLOCKS_DEFAULT_TIMEOUT_SECONDS
    try:
        parsed = float(value.strip())
    except (TypeError, ValueError):
        raise _invalid_config() from None
    return _normalize_timeout(parsed)


@dataclass(frozen=True, slots=True, repr=False)
class DndStatblockResourceResolverConfig:
    """Frozen provider endpoint configuration with a redacted representation."""

    base_url: str
    internal_api_key: str
    timeout_seconds: float = STATBLOCKS_DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_url", _normalize_base_url(self.base_url))
        object.__setattr__(
            self,
            "internal_api_key",
            _normalize_api_key(self.internal_api_key),
        )
        object.__setattr__(
            self,
            "timeout_seconds",
            _normalize_timeout(self.timeout_seconds),
        )

    def __repr__(self) -> str:
        return (
            "DndStatblockResourceResolverConfig("
            f"base_url={self.base_url!r}, "
            "internal_api_key=<redacted>, "
            f"timeout_seconds={self.timeout_seconds!r})"
        )


def load_dnd_statblock_resource_resolver_config(
    *,
    environ: Mapping[str, str] | None = None,
) -> DndStatblockResourceResolverConfig:
    """Load the explicit resolver capability from the existing env names."""
    values = os.environ if environ is None else environ
    return DndStatblockResourceResolverConfig(
        base_url=values.get(STATBLOCKS_BASE_URL_ENV, ""),
        internal_api_key=values.get(STATBLOCKS_INTERNAL_API_KEY_ENV, ""),
        timeout_seconds=_parse_timeout(values.get(STATBLOCKS_TIMEOUT_SECONDS_ENV)),
    )


def _supports_exact_ref(resource_ref: DndMechanicsResourceRef) -> bool:
    try:
        return (
            resource_ref.ruleset_id == "dnd5e"
            and resource_ref.provider_id == STATBLOCKS_PROVIDER_ID
            and resource_ref.resource_schema == STATBLOCKS_RESOURCE_SCHEMA
            and resource_ref.media_type == STATBLOCKS_MEDIA_TYPE
            and bool(_STATBLOCK_ID.fullmatch(resource_ref.resource_id))
            and bool(_REVISION_ID.fullmatch(resource_ref.resource_revision))
        )
    except Exception:
        return False


def _resource_path(resource_ref: DndMechanicsResourceRef) -> str:
    return (
        f"{STATBLOCKS_ROUTE_PREFIX}/"
        f"{resource_ref.resource_id}/revisions/{resource_ref.resource_revision}"
    )


def _observed_mechanics_payload(
    provider_response: Mapping[str, Any],
) -> Any:
    canonical_definition = provider_response.get("canonical_definition")
    if not isinstance(canonical_definition, str):
        return canonical_definition
    try:
        return json.loads(canonical_definition)
    except (TypeError, ValueError):
        return canonical_definition


def _observed_payload_digest(provider_response: Mapping[str, Any]) -> Any:
    digest = provider_response.get("definition_digest")
    if isinstance(digest, str) and digest.startswith("sha256:"):
        return digest.removeprefix("sha256:")
    return digest


def _observed_resource_schema(provider_response: Mapping[str, Any]) -> str | None:
    contract = provider_response.get("contract")
    contract_version = provider_response.get("contract_version")
    if not isinstance(contract, str) or not isinstance(contract_version, str):
        return None
    return f"{contract}.{contract_version}"


def _observed_envelope(provider_response: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "dmdnd_mechanics_resource_envelope_v1",
        "resource_ref": {
            "schema_version": "dmdnd_mechanics_resource_ref_v1",
            "ruleset_id": "dnd5e",
            "provider_id": STATBLOCKS_PROVIDER_ID,
            "resource_id": provider_response.get("statblock_id"),
            "resource_revision": provider_response.get("revision_id"),
            "resource_schema": _observed_resource_schema(provider_response),
            "media_type": STATBLOCKS_MEDIA_TYPE,
            "payload_sha256": _observed_payload_digest(provider_response),
        },
        "mechanics_payload": _observed_mechanics_payload(provider_response),
    }


def _read_bounded_body(response: httpx.Response) -> bytes | None:
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > STATBLOCKS_MAX_RESPONSE_BODY_BYTES:
                response.close()
                return None
        except ValueError:
            pass

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > STATBLOCKS_MAX_RESPONSE_BODY_BYTES:
            response.close()
            return None
        chunks.append(chunk)
    return b"".join(chunks)


class DndStatblockResourceResolver:
    """One exact, authenticated, bounded statblock-v1 provider adapter."""

    def __init__(
        self,
        *,
        config: DndStatblockResourceResolverConfig | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._config = (
            config
            if config is not None
            else load_dnd_statblock_resource_resolver_config()
        )
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            timeout=self._config.timeout_seconds,
            follow_redirects=False,
        )

    @property
    def config(self) -> DndStatblockResourceResolverConfig:
        return self._config

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> DndStatblockResourceResolver:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def resolve(
        self,
        resource_ref: DndMechanicsResourceRef,
    ) -> Mapping[str, Any] | None:
        """Resolve one supported ref without repair, retry, or fallback."""
        if not _supports_exact_ref(resource_ref):
            return None

        failure: DndStatblockResourceResolverError | None = None
        result: Mapping[str, Any] | None = None
        try:
            with self._client.stream(
                "GET",
                f"{self._config.base_url}{_resource_path(resource_ref)}",
                headers={STATBLOCKS_AUTH_HEADER: self._config.internal_api_key},
                timeout=self._config.timeout_seconds,
                follow_redirects=False,
            ) as response:
                status_code = response.status_code
                if status_code in {404, 410}:
                    return None
                if status_code != 200:
                    response.close()
                    failure = _resolver_failure(
                        "resolver_unavailable",
                        status_code=status_code,
                    )
                else:
                    body = _read_bounded_body(response)
                    if body is None:
                        failure = _resolver_failure("resolver_response_invalid")
                    else:
                        decoded: Any = None
                        decoded_ok = True
                        try:
                            decoded = json.loads(body)
                        except (TypeError, ValueError):
                            decoded_ok = False
                        if not decoded_ok or not isinstance(decoded, Mapping):
                            failure = _resolver_failure("resolver_response_invalid")
                        else:
                            result = _observed_envelope(decoded)
        except httpx.TimeoutException:
            failure = _resolver_failure("resolver_unavailable")
        except httpx.HTTPError:
            failure = _resolver_failure("resolver_unavailable")
        except Exception:
            failure = _resolver_failure("resolver_unavailable")

        if failure is not None:
            raise failure from None
        return result


__all__ = [
    "STATBLOCKS_AUTH_HEADER",
    "STATBLOCKS_BASE_URL_ENV",
    "STATBLOCKS_DEFAULT_TIMEOUT_SECONDS",
    "STATBLOCKS_INTERNAL_API_KEY_ENV",
    "STATBLOCKS_MAX_RESPONSE_BODY_BYTES",
    "STATBLOCKS_MAX_TIMEOUT_SECONDS",
    "STATBLOCKS_MEDIA_TYPE",
    "STATBLOCKS_PROVIDER_ID",
    "STATBLOCKS_RESOURCE_SCHEMA",
    "STATBLOCKS_ROUTE_PREFIX",
    "STATBLOCKS_TIMEOUT_SECONDS_ENV",
    "DndStatblockResourceResolver",
    "DndStatblockResourceResolverConfig",
    "DndStatblockResourceResolverError",
    "ResolverFailureCategory",
    "load_dnd_statblock_resource_resolver_config",
]
