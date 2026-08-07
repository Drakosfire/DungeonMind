"""Contract and canonical-serialization proofs for Threat mechanics transport."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind_dnd.contracts.mechanics_transport import (
    THREAT_MECHANICS_HYDRATION_REQUEST_SCHEMA,
    DndThreatMechanicsHydrationRequest,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dungeonmind_dnd"
REQUEST_FIXTURE = FIXTURES / "tripod-null-calf-threat-mechanics-request-v1.json"
EXAMPLE_REQUEST = (
    Path(__file__).resolve().parents[2] / "examples" / "dnd_threat_mechanics_request.json"
)
REQUEST_SHA256 = "a78a1648fae75937b5b775d6ef0d385ab620eace249a6b618334ab1868ae134e"


def _raw_request() -> dict[str, Any]:
    return json.loads(REQUEST_FIXTURE.read_text(encoding="utf-8"))


def _request() -> DndThreatMechanicsHydrationRequest:
    return DndThreatMechanicsHydrationRequest.model_validate(_raw_request())


def test_request_fixture_and_example_are_byte_equivalent_contracts() -> None:
    fixture = _raw_request()
    example = json.loads(EXAMPLE_REQUEST.read_text(encoding="utf-8"))
    request = _request()

    assert fixture == example
    assert request.model_dump(mode="json") == fixture
    assert request.schema_version == THREAT_MECHANICS_HYDRATION_REQUEST_SCHEMA
    assert canonical_sha256(fixture) == REQUEST_SHA256
    assert canonical_sha256(request.model_dump(mode="json")) == REQUEST_SHA256
    assert request.model_dump(mode="json")["resource_ref"]["schema_version"] == (
        "dmdnd_mechanics_resource_ref_v1"
    )


@pytest.mark.parametrize(
    "field",
    [
        "admissibility",
        "binding",
        "binding_id",
        "current_head",
        "graph_payload_sha256",
        "latest",
        "mechanics_payload",
        "provider_locator",
        "semantic_profile",
        "threat_relationship_ids",
        "threat_vocabulary",
        "visibility",
    ],
)
def test_request_rejects_caller_authority_or_resolution_fields(field: str) -> None:
    payload = _raw_request()
    payload[field] = "SENTINEL_AUTHORITY_FIELD"

    with pytest.raises(ValidationError) as raised:
        DndThreatMechanicsHydrationRequest.model_validate(payload)

    assert "SENTINEL_AUTHORITY_FIELD" not in str(raised.value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("world_id", "world/with/path"),
        ("world_id", "latest"),
        ("world_id", "https://world.invalid"),
        ("graph_revision_id", "rev:UPPER"),
        ("graph_revision_id", "latest"),
        ("object_id", "object:wrong-prefix"),
        ("object_id", "obj:"),
    ],
)
def test_request_rejects_invalid_exact_id_shapes(field: str, value: str) -> None:
    payload = _raw_request()
    payload[field] = value

    with pytest.raises(ValidationError):
        DndThreatMechanicsHydrationRequest.model_validate(payload)


def test_request_rejects_nested_resource_ref_mutation() -> None:
    payload = copy.deepcopy(_raw_request())
    payload["resource_ref"]["payload_sha256"] = "not-a-digest"

    with pytest.raises(ValidationError):
        DndThreatMechanicsHydrationRequest.model_validate(payload)
