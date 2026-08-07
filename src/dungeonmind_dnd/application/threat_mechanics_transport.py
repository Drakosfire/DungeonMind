"""Exact-revision Threat mechanics transport orchestration.

This seam owns only exact repository loading and failure categorization.  The
profile-owned B.3a binding and hydration functions remain the sole authority
for graph, Threat, resource, and digest semantics.
"""

from __future__ import annotations

from typing import Literal, NoReturn

from dungeonmind.application.graph_snapshot import GraphSnapshotReader
from dungeonmind.application.repositories import WorldGraphRepository
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError

from ..contracts.mechanics_resources import (
    DndMechanicsResourceResolver,
    DndThreatMechanicsHydration,
)
from ..contracts.mechanics_transport import DndThreatMechanicsHydrationRequest
from ..domain.errors import DndThreatMechanicsHydrationError
from .threat_mechanics import (
    derive_threat_mechanics_binding,
    hydrate_threat_mechanics,
)

TransportFailureReason = Literal[
    "graph_revision_not_found",
    "graph_repository_unavailable",
    "threat_mechanics_binding_invalid",
    "mechanics_resource_not_found",
    "mechanics_resource_unavailable",
    "mechanics_resource_integrity_failure",
    "internal_error",
]

_BINDING_FAILURE_REASONS = frozenset(
    {
        "binding_reload_validation",
        "binding_identity_mismatch",
        "graph_revision_reload_validation",
        "graph_revision_binding_mismatch",
        "graph_payload_digest_mismatch",
        "unsupported_graph_schema",
        "semantic_profile_mismatch",
        "threat_vocabulary_mismatch",
        "object_not_found",
        "object_kind_not_creature",
        "object_not_threatening",
        "resource_ref_validation",
        "hydration_contract_validation",
    }
)
_RESOURCE_INTEGRITY_REASONS = frozenset(
    {
        "resource_envelope_reload_validation",
        "resource_identity_mismatch",
        "resource_payload_digest_mismatch",
    }
)


class DndThreatMechanicsTransportError(Exception):
    """Closed, sanitized failure raised by the transport-neutral seam."""

    def __init__(
        self,
        reason: TransportFailureReason,
        *,
        world_id: str | None = None,
        graph_revision_id: str | None = None,
        object_id: str | None = None,
    ) -> None:
        details: dict[str, str] = {"reason": reason}
        for key, value in (
            ("world_id", world_id),
            ("graph_revision_id", graph_revision_id),
            ("object_id", object_id),
        ):
            if isinstance(value, str) and value:
                details[key] = value
        self.reason = reason
        self.details = details
        super().__init__("Threat mechanics hydration transport failed.")


def _failure(
    reason: TransportFailureReason,
    *,
    world_id: str | None = None,
    graph_revision_id: str | None = None,
    object_id: str | None = None,
) -> NoReturn:
    raise DndThreatMechanicsTransportError(
        reason,
        world_id=world_id,
        graph_revision_id=graph_revision_id,
        object_id=object_id,
    ) from None


def _reload_request(
    request: DndThreatMechanicsHydrationRequest,
) -> DndThreatMechanicsHydrationRequest:
    try:
        return DndThreatMechanicsHydrationRequest.model_validate(
            request.model_dump(mode="json")
        )
    except Exception:
        _failure("internal_error")


def _b3a_failure_reason(error: DndThreatMechanicsHydrationError) -> str | None:
    reason = error.details.get("reason")
    return reason if isinstance(reason, str) else None


def _raise_b3a_failure(
    error: DndThreatMechanicsHydrationError,
    *,
    request: DndThreatMechanicsHydrationRequest,
) -> NoReturn:
    reason = _b3a_failure_reason(error)
    if reason == "resource_not_found":
        _failure(
            "mechanics_resource_not_found",
            world_id=request.world_id,
            graph_revision_id=request.graph_revision_id,
            object_id=request.object_id,
        )
    if reason == "resource_resolver_failure":
        _failure(
            "mechanics_resource_unavailable",
            world_id=request.world_id,
            graph_revision_id=request.graph_revision_id,
            object_id=request.object_id,
        )
    if reason in _RESOURCE_INTEGRITY_REASONS:
        _failure(
            "mechanics_resource_integrity_failure",
            world_id=request.world_id,
            graph_revision_id=request.graph_revision_id,
            object_id=request.object_id,
        )
    if reason in _BINDING_FAILURE_REASONS:
        _failure(
            "threat_mechanics_binding_invalid",
            world_id=request.world_id,
            graph_revision_id=request.graph_revision_id,
            object_id=request.object_id,
        )
    _failure("internal_error")


def hydrate_threat_mechanics_request(
    request: DndThreatMechanicsHydrationRequest,
    *,
    graph_repository: WorldGraphRepository,
    graph_reader: GraphSnapshotReader,
    resource_resolver: DndMechanicsResourceResolver,
) -> DndThreatMechanicsHydration:
    """Hydrate one exact graph revision through the unchanged B.3a seam."""
    verified = _reload_request(request)
    try:
        stored = graph_repository.get_revision(
            verified.world_id,
            verified.graph_revision_id,
        )
    except PersistenceIntegrityError:
        _failure(
            "threat_mechanics_binding_invalid",
            world_id=verified.world_id,
            graph_revision_id=verified.graph_revision_id,
            object_id=verified.object_id,
        )
    except PersistenceUnavailableError:
        _failure(
            "graph_repository_unavailable",
            world_id=verified.world_id,
            graph_revision_id=verified.graph_revision_id,
            object_id=verified.object_id,
        )
    except Exception:
        _failure("internal_error")
    if stored is None:
        _failure(
            "graph_revision_not_found",
            world_id=verified.world_id,
            graph_revision_id=verified.graph_revision_id,
            object_id=verified.object_id,
        )

    try:
        binding = derive_threat_mechanics_binding(
            verified.object_id,
            verified.resource_ref,
            graph_revision=stored,
            graph_reader=graph_reader,
        )
    except DndThreatMechanicsHydrationError as error:
        _raise_b3a_failure(error, request=verified)
    except Exception:
        _failure("internal_error")

    if (
        binding.world_id != verified.world_id
        or binding.graph_revision_id != verified.graph_revision_id
    ):
        _failure(
            "threat_mechanics_binding_invalid",
            world_id=verified.world_id,
            graph_revision_id=verified.graph_revision_id,
            object_id=verified.object_id,
        )

    try:
        return hydrate_threat_mechanics(
            binding,
            admissibility=Admissibility.GM,
            graph_revision=stored,
            graph_reader=graph_reader,
            resource_resolver=resource_resolver,
        )
    except DndThreatMechanicsHydrationError as error:
        _raise_b3a_failure(error, request=verified)
    except Exception:
        _failure("internal_error")


__all__ = ["hydrate_threat_mechanics_request"]
