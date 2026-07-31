"""Trusted demo-access policy for the local Mind Turn host."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts.mind_turn import CallerScope, MindTurnRequest, SurfaceContext
from ..contracts.projection import Admissibility
from ..domain.errors import CapabilityDeniedError


@dataclass(frozen=True)
class DemoAccessBinding:
    caller_id: str
    tenant_id: str | None
    roles: tuple[str, ...]
    world_id: str
    campaign_id: str | None
    thread_id: str
    admissibility: Admissibility
    surface_id: str

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> DemoAccessBinding:
        roles = raw.get("roles") or []
        return cls(
            caller_id=str(raw["caller_id"]),
            tenant_id=raw.get("tenant_id"),
            roles=tuple(str(role) for role in roles),
            world_id=str(raw["world_id"]),
            campaign_id=raw.get("campaign_id"),
            thread_id=str(raw["thread_id"]),
            admissibility=Admissibility(str(raw["admissibility"])),
            surface_id=str(raw["surface_id"]),
        )


def authorize_demo_request(
    request: MindTurnRequest,
    *,
    binding: DemoAccessBinding,
) -> MindTurnRequest:
    """Require the request to match the server-configured demo binding exactly.

    Authorization lives at the transport boundary. MindTurnService receives only
    already-authorized requests.
    """
    mismatches: list[str] = []
    if request.caller_scope.caller_id != binding.caller_id:
        mismatches.append("caller_id")
    if request.caller_scope.tenant_id != binding.tenant_id:
        mismatches.append("tenant_id")
    if tuple(request.caller_scope.roles) != binding.roles:
        mismatches.append("roles")
    if request.world_id != binding.world_id:
        mismatches.append("world_id")
    if request.campaign_id != binding.campaign_id:
        mismatches.append("campaign_id")
    if request.thread_id != binding.thread_id:
        mismatches.append("thread_id")
    if request.admissibility != binding.admissibility:
        mismatches.append("admissibility")
    if request.surface_context.surface_id != binding.surface_id:
        mismatches.append("surface_id")
    if mismatches:
        raise CapabilityDeniedError(
            "demo caller/scope mismatch",
            details={"mismatches": mismatches},
        )
    return MindTurnRequest.for_authorized(
        request_id=request.request_id,
        thread_id=binding.thread_id,
        caller_scope=CallerScope(
            caller_id=binding.caller_id,
            tenant_id=binding.tenant_id,
            roles=list(binding.roles),
        ),
        world_id=binding.world_id,
        campaign_id=binding.campaign_id,
        requested_revision_id=request.requested_revision_id,
        admissibility=binding.admissibility,
        focus=request.focus,
        surface_context=SurfaceContext(
            surface_id=binding.surface_id,
            mode=request.surface_context.mode,
            selected_object_ids=list(request.surface_context.selected_object_ids),
            selected_document_ref=request.surface_context.selected_document_ref,
            active_artifact_refs=list(request.surface_context.active_artifact_refs),
        ),
        message=request.message,
    )
