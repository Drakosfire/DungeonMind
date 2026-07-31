"""FastAPI application factory for the thin Mind Turn host.

Importing this module requires the ``api`` extra.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..application.mind_turn import MindTurnService
from ..contracts.mind_turn import MindTurnRequest, MindTurnResponse
from ..domain.errors import DungeonMindError
from .demo_access import DemoAccessBinding, authorize_demo_request
from .error_mapping import error_envelope, http_status_for


class MindTurnAppState:
    def __init__(
        self,
        *,
        service: MindTurnService,
        demo_binding: DemoAccessBinding,
        readiness_probe: Callable[[], dict[str, Any]],
    ) -> None:
        self.service = service
        self.demo_binding = demo_binding
        self.readiness_probe = readiness_probe


def create_app(
    *,
    service: MindTurnService,
    demo_binding: DemoAccessBinding,
    readiness_probe: Callable[[], dict[str, Any]],
    cors_origin: str | None = None,
) -> FastAPI:
    app = FastAPI(title="DungeonMind Mind Turn", version="0.1.0")
    app.state.mind_turn = MindTurnAppState(
        service=service,
        demo_binding=demo_binding,
        readiness_probe=readiness_probe,
    )

    if cors_origin:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[cors_origin],
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    @app.exception_handler(DungeonMindError)
    async def _dungeonmind_error(_request: Request, exc: DungeonMindError) -> JSONResponse:
        return JSONResponse(status_code=http_status_for(exc), content=error_envelope(exc))

    @app.exception_handler(ValidationError)
    async def _validation_error(_request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "request_validation_error",
                    "message": "Request validation failed.",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, Any]:
        state: MindTurnAppState = app.state.mind_turn
        return state.readiness_probe()

    @app.post("/v1/mind-turn", response_model=MindTurnResponse)
    def mind_turn(body: MindTurnRequest) -> MindTurnResponse:
        state: MindTurnAppState = app.state.mind_turn
        authorized = authorize_demo_request(body, binding=state.demo_binding)
        return state.service.execute(authorized)

    return app
