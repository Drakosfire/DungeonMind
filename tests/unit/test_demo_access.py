"""Unit tests for trusted demo-access authorization."""

import pytest

from dungeonmind.contracts.mind_turn import CallerScope, MindTurnRequest, SurfaceContext
from dungeonmind.contracts.projection import Admissibility, ProjectionFocus
from dungeonmind.domain.errors import CapabilityDeniedError
from dungeonmind.infrastructure.fixtures.curated_mind_turn import load_curated_mind_turn_fixture
from dungeonmind.service.demo_access import DemoAccessBinding, authorize_demo_request


def _binding() -> DemoAccessBinding:
    fixture = load_curated_mind_turn_fixture()
    return DemoAccessBinding.from_mapping(fixture.authorized_demo_binding)


def _request(**overrides: object) -> MindTurnRequest:
    binding = _binding()
    kwargs: dict[str, object] = {
        "request_id": "req:demo-1",
        "thread_id": binding.thread_id,
        "caller_scope": CallerScope(
            caller_id=binding.caller_id,
            tenant_id=binding.tenant_id,
            roles=list(binding.roles),
        ),
        "world_id": binding.world_id,
        "campaign_id": binding.campaign_id,
        "admissibility": binding.admissibility,
        "focus": ProjectionFocus(),
        "surface_context": SurfaceContext(surface_id=binding.surface_id, mode="ask"),
        "message": "Who safeguards the Sun Ledger?",
    }
    kwargs.update(overrides)
    return MindTurnRequest(**kwargs)  # type: ignore[arg-type]


def test_matching_binding_authorizes() -> None:
    binding = _binding()
    authorized = authorize_demo_request(_request(), binding=binding)
    assert authorized.caller_scope.caller_id == binding.caller_id
    assert authorized.caller_scope.tenant_id == binding.tenant_id
    assert authorized.caller_scope.roles == list(binding.roles)
    assert authorized.world_id == binding.world_id
    assert authorized.campaign_id == binding.campaign_id
    assert authorized.thread_id == binding.thread_id
    assert authorized.admissibility == binding.admissibility
    assert authorized.surface_context.surface_id == binding.surface_id


def test_caller_mismatch_denied() -> None:
    with pytest.raises(CapabilityDeniedError, match="mismatch") as exc:
        authorize_demo_request(
            _request(
                caller_scope=CallerScope(
                    caller_id="caller:other",
                    tenant_id=None,
                    roles=["landing-demo"],
                )
            ),
            binding=_binding(),
        )
    assert "caller_id" in exc.value.details["mismatches"]


def test_tenant_mismatch_denied() -> None:
    with pytest.raises(CapabilityDeniedError) as exc:
        authorize_demo_request(
            _request(
                caller_scope=CallerScope(
                    caller_id="caller:landing-demo",
                    tenant_id="tenant:intruder",
                    roles=["landing-demo"],
                )
            ),
            binding=_binding(),
        )
    assert "tenant_id" in exc.value.details["mismatches"]


def test_admissibility_mismatch_denied() -> None:
    with pytest.raises(CapabilityDeniedError) as exc:
        authorize_demo_request(
            _request(admissibility=Admissibility.PLAYER),
            binding=_binding(),
        )
    assert "admissibility" in exc.value.details["mismatches"]


def test_world_mismatch_denied() -> None:
    with pytest.raises(CapabilityDeniedError) as exc:
        authorize_demo_request(_request(world_id="world:other"), binding=_binding())
    assert "world_id" in exc.value.details["mismatches"]


def test_thread_mismatch_denied() -> None:
    with pytest.raises(CapabilityDeniedError) as exc:
        authorize_demo_request(_request(thread_id="thr:other"), binding=_binding())
    assert "thread_id" in exc.value.details["mismatches"]
