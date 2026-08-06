"""Separate bearer-gated FastAPI host for exact Threat mechanics hydration."""

# pyright: reportMissingImports=false

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from dungeonmind.application.graph_snapshot import GraphSnapshotReader
from dungeonmind.application.repositories import WorldGraphRepository

from ..application.threat_mechanics_transport import (
    DndThreatMechanicsTransportError,
    hydrate_threat_mechanics_request,
)
from ..contracts.mechanics_resources import DndMechanicsResourceResolver
from ..contracts.mechanics_transport import DndThreatMechanicsHydrationRequest

_HYDRATION_PATH = "/v1/dnd/threat-mechanics-hydrations"
_PUBLIC_MESSAGES = {
    "graph_revision_not_found": "Pinned graph revision was not found.",
    "graph_repository_unavailable": "Graph repository is temporarily unavailable.",
    "threat_mechanics_binding_invalid": "Threat mechanics binding validation failed.",
    "mechanics_resource_not_found": "Mechanics resource was not found.",
    "mechanics_resource_unavailable": "Mechanics resource provider is temporarily unavailable.",
    "mechanics_resource_integrity_failure": "Mechanics resource integrity validation failed.",
    "internal_error": "An unexpected error occurred.",
}
_STATUS_BY_REASON = {
    "graph_revision_not_found": 404,
    "graph_repository_unavailable": 503,
    "threat_mechanics_binding_invalid": 409,
    "mechanics_resource_not_found": 404,
    "mechanics_resource_unavailable": 503,
    "mechanics_resource_integrity_failure": 502,
    "internal_error": 500,
}


class _AccessFailure(Exception):
    def __init__(self, *, status_code: Literal[401, 403]) -> None:
        self.status_code = status_code
        super().__init__("Threat mechanics access denied.")


@dataclass(frozen=True, repr=False)
class ThreatMechanicsAccessBinding:
    """One configured world and bearer digest; the raw secret is never retained."""

    world_id: str
    bearer_token_sha256: str

    def __repr__(self) -> str:
        return (
            "ThreatMechanicsAccessBinding("
            "world_id=<redacted>, bearer_token_sha256=<redacted>)"
        )

    @classmethod
    def from_secret(
        cls,
        world_id: str,
        bearer_token: str,
    ) -> ThreatMechanicsAccessBinding:
        if not world_id.strip():
            raise ValueError("threat mechanics world must be non-blank")
        if not bearer_token.strip():
            raise ValueError("threat mechanics bearer token must be non-blank")
        return cls(
            world_id=world_id,
            bearer_token_sha256=hashlib.sha256(
                bearer_token.encode("utf-8")
            ).hexdigest(),
        )

    def authenticate(self, authorization_header: str | None) -> None:
        if authorization_header is None or not authorization_header.startswith("Bearer "):
            raise _AccessFailure(status_code=401)
        supplied_token = authorization_header.removeprefix("Bearer ")
        if not supplied_token or any(character.isspace() for character in supplied_token):
            raise _AccessFailure(status_code=401)
        supplied_digest = hashlib.sha256(supplied_token.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(supplied_digest, self.bearer_token_sha256):
            raise _AccessFailure(status_code=401)

    def authorize(self, request: DndThreatMechanicsHydrationRequest) -> None:
        if request.world_id != self.world_id:
            raise _AccessFailure(status_code=403)


@dataclass
class _ThreatMechanicsAppState:
    graph_repository: WorldGraphRepository
    graph_reader: GraphSnapshotReader
    resource_resolver: DndMechanicsResourceResolver
    access_binding: ThreatMechanicsAccessBinding
    readiness_probe: Callable[[], dict[str, Any]]


def _error_body(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


def _validation_body(errors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    del errors
    return _error_body(
        "request_validation_error",
        "Request validation failed.",
        details={"errors": [{"type": "request_validation_error"}]},
    )


def _access_body() -> dict[str, Any]:
    return _error_body("capability_denied", "Threat mechanics access denied.")


def _transport_body(error: DndThreatMechanicsTransportError) -> dict[str, Any]:
    return _error_body(
        error.reason,
        _PUBLIC_MESSAGES[error.reason],
        details=error.details,
    )


def create_threat_mechanics_app(
    *,
    graph_repository: WorldGraphRepository,
    graph_reader: GraphSnapshotReader,
    resource_resolver: DndMechanicsResourceResolver,
    access_binding: ThreatMechanicsAccessBinding,
    readiness_probe: Callable[[], dict[str, Any]],
) -> FastAPI:
    """Create a separate, read-only, server-to-server mechanics host."""
    app = FastAPI(
        title="DungeonMind D&D Threat Mechanics",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )
    app.state.threat_mechanics = _ThreatMechanicsAppState(
        graph_repository=graph_repository,
        graph_reader=graph_reader,
        resource_resolver=resource_resolver,
        access_binding=access_binding,
        readiness_probe=readiness_probe,
    )

    @app.exception_handler(Exception)
    async def _unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", _PUBLIC_MESSAGES["internal_error"]),
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        state: _ThreatMechanicsAppState = app.state.threat_mechanics
        try:
            return JSONResponse(status_code=200, content=state.readiness_probe())
        except Exception:
            return JSONResponse(
                status_code=503,
                content=_error_body(
                    "graph_repository_unavailable",
                    _PUBLIC_MESSAGES["graph_repository_unavailable"],
                ),
            )

    @app.post(
        _HYDRATION_PATH,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": DndThreatMechanicsHydrationRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def hydrate(request: Request) -> JSONResponse:
        state: _ThreatMechanicsAppState = app.state.threat_mechanics
        try:
            state.access_binding.authenticate(request.headers.get("authorization"))
        except _AccessFailure as error:
            headers = {"WWW-Authenticate": "Bearer"} if error.status_code == 401 else {}
            return JSONResponse(
                status_code=error.status_code,
                content=_access_body(),
                headers=headers,
            )

        try:
            raw_body = await request.json()
            body = DndThreatMechanicsHydrationRequest.model_validate(raw_body)
        except ValidationError as error:
            return JSONResponse(
                status_code=422,
                content=_validation_body(error.errors()),
            )
        except Exception:
            return JSONResponse(
                status_code=422,
                content=_validation_body(
                    [
                        {
                            "type": "json_invalid",
                            "loc": ["body"],
                            "msg": "Invalid JSON.",
                        }
                    ]
                ),
            )

        try:
            state.access_binding.authorize(body)
        except _AccessFailure as error:
            return JSONResponse(
                status_code=error.status_code,
                content=_access_body(),
            )

        try:
            hydration = hydrate_threat_mechanics_request(
                body,
                graph_repository=state.graph_repository,
                graph_reader=state.graph_reader,
                resource_resolver=state.resource_resolver,
            )
        except DndThreatMechanicsTransportError as error:
            return JSONResponse(
                status_code=_STATUS_BY_REASON[error.reason],
                content=_transport_body(error),
            )
        return JSONResponse(
            status_code=200,
            content=hydration.model_dump(mode="json"),
            headers={"Cache-Control": "no-store"},
        )

    return app


__all__ = [
    "ThreatMechanicsAccessBinding",
    "create_threat_mechanics_app",
]
