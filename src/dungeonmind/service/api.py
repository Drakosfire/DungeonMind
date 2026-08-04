"""FastAPI application factory for the thin Mind Turn host.

Importing this module requires the ``api`` extra.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..application.graph_snapshot import GraphSnapshotReader
from ..application.mind_turn import Clock, MindTurnService
from ..application.repositories import (
    ContributionReviewRepository,
    FinalizedReviewPublicationRepository,
    WorldGraphRepository,
)
from ..application.review_publication import publish_finalized_review
from ..contracts.mind_turn import MindTurnRequest, MindTurnResponse
from ..contracts.review_publication import FinalizedReviewPublication
from ..contracts.review_publication_transport import FinalizedReviewPublicationRequest
from ..domain.errors import DungeonMindError, PersistenceIntegrityError
from .demo_access import DemoAccessBinding, authorize_demo_request
from .error_mapping import error_envelope, http_status_for
from .publication_access import PublicationAccessBinding, authorize_publication_request


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

    def _validation_envelope(errors: list[Any]) -> dict[str, Any]:
        return {
            "error": {
                "code": "request_validation_error",
                "message": "Request validation failed.",
                "details": {"errors": errors},
            }
        }

    @app.exception_handler(RequestValidationError)
    async def _request_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content=_validation_envelope(exc.errors()))

    @app.exception_handler(ValidationError)
    async def _validation_error(_request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content=_validation_envelope(exc.errors()))

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


class PublicationAppState:
    def __init__(
        self,
        *,
        review_repository: ContributionReviewRepository,
        world_graph_repository: WorldGraphRepository,
        publication_repository: FinalizedReviewPublicationRepository,
        graph_reader: GraphSnapshotReader,
        clock: Clock,
        access_binding: PublicationAccessBinding,
        readiness_probe: Callable[[], dict[str, Any]],
    ) -> None:
        self.review_repository = review_repository
        self.world_graph_repository = world_graph_repository
        self.publication_repository = publication_repository
        self.graph_reader = graph_reader
        self.clock = clock
        self.access_binding = access_binding
        self.readiness_probe = readiness_probe


def create_publication_app(
    *,
    review_repository: ContributionReviewRepository,
    world_graph_repository: WorldGraphRepository,
    publication_repository: FinalizedReviewPublicationRepository,
    graph_reader: GraphSnapshotReader,
    clock: Clock,
    access_binding: PublicationAccessBinding,
    readiness_probe: Callable[[], dict[str, Any]],
) -> FastAPI:
    """Create the separate bearer-gated finalized-review publication host."""

    app = FastAPI(title="DungeonMind Finalized Review Publication", version="0.1.0")
    app.state.publication = PublicationAppState(
        review_repository=review_repository,
        world_graph_repository=world_graph_repository,
        publication_repository=publication_repository,
        graph_reader=graph_reader,
        clock=clock,
        access_binding=access_binding,
        readiness_probe=readiness_probe,
    )

    @app.exception_handler(DungeonMindError)
    async def _dungeonmind_error(_request: Request, exc: DungeonMindError) -> JSONResponse:
        return JSONResponse(status_code=http_status_for(exc), content=error_envelope(exc))

    def _validation_envelope(errors: list[Any]) -> dict[str, Any]:
        safe_errors = [
            {
                key: value
                for key, value in error.items()
                if key not in {"input", "ctx", "url"}
            }
            for error in errors
        ]
        return {
            "error": {
                "code": "request_validation_error",
                "message": "Request validation failed.",
                "details": {"errors": safe_errors},
            }
        }

    @app.exception_handler(RequestValidationError)
    async def _request_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content=_validation_envelope(exc.errors()))

    @app.exception_handler(ValidationError)
    async def _validation_error(_request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content=_validation_envelope(exc.errors()))

    @app.exception_handler(Exception)
    async def _unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content=error_envelope(exc))

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, Any]:
        state: PublicationAppState = app.state.publication
        return state.readiness_probe()

    @app.post(
        "/v1/finalized-review-publications",
        response_model=FinalizedReviewPublication,
    )
    def publish(body: FinalizedReviewPublicationRequest, request: Request) -> JSONResponse:
        state: PublicationAppState = app.state.publication
        authorized = authorize_publication_request(
            body,
            authorization_header=request.headers.get("authorization"),
            binding=state.access_binding,
        )
        published_at = state.clock.now()
        if published_at.tzinfo is None or published_at.utcoffset() is None:
            raise PersistenceIntegrityError(
                "publication clock returned a naive datetime",
                details={"reason": "publication_clock_not_timezone_aware"},
            )
        publication = publish_finalized_review(
            authorized.world_id,
            authorized.review_id,
            published_at=published_at,
            review_repository=state.review_repository,
            world_graph_repository=state.world_graph_repository,
            publication_repository=state.publication_repository,
            graph_reader=state.graph_reader,
        )
        return JSONResponse(
            status_code=200,
            content=publication.model_dump(mode="json"),
            headers={"Cache-Control": "no-store"},
        )

    return app
