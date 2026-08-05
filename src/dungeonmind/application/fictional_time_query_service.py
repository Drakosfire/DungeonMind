"""Exact-revision fictional-time shadow query application seam (FT1b)."""

from __future__ import annotations

from ..contracts.fictional_time import FictionalTimeQueryResult
from ..contracts.fictional_time_transport import FictionalTimeShadowQueryRequest
from ..domain.errors import FictionalTimeIntegrityError, RevisionNotFoundError
from .fictional_time import evaluate_fictional_time_query
from .graph_snapshot import GraphSnapshotReader
from .repositories import WorldGraphRepository


def _reload_request(
    request: FictionalTimeShadowQueryRequest,
) -> FictionalTimeShadowQueryRequest:
    try:
        return FictionalTimeShadowQueryRequest.model_validate(
            request.model_dump(mode="json", exclude_unset=True)
        )
    except Exception:
        raise FictionalTimeIntegrityError(reason="request_reload_validation") from None


def query_fictional_time_shadow_at_revision(
    request: FictionalTimeShadowQueryRequest,
    *,
    world_graph_repository: WorldGraphRepository,
    graph_reader: GraphSnapshotReader,
) -> FictionalTimeQueryResult:
    """Load one exact stored revision and evaluate the caller-supplied shadow query."""

    verified = _reload_request(request)
    stored = world_graph_repository.get_revision(
        verified.world_id,
        verified.graph_revision_id,
    )
    if stored is None:
        raise RevisionNotFoundError(
            "Pinned graph revision was not found.",
            details={
                "world_id": verified.world_id,
                "revision_id": verified.graph_revision_id,
            },
        )
    return evaluate_fictional_time_query(
        stored_revision=stored,
        claim_bundle=verified.claim_bundle,
        query=verified.query,
        graph_reader=graph_reader,
    )
