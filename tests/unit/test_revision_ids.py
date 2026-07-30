"""Canonical hashing and content-addressed revision identity."""

import math

import pytest

from dungeonmind.domain import canonical_json, canonical_sha256, compute_revision_id

MATERIAL = {
    "world_id": "world:demo",
    "parent_revision_id": None,
    "operation_ids": ["op:1"],
    "graph_schema": "dm_union_graph_v1",
    "graph_payload_sha256": "ab" * 32,
}


def test_canonical_json_is_order_independent() -> None:
    a = {"x": 1, "y": [2, 3], "z": {"b": 2, "a": 1}}
    b = {"z": {"a": 1, "b": 2}, "y": [2, 3], "x": 1}
    assert canonical_json(a) == canonical_json(b)
    assert canonical_sha256(a) == canonical_sha256(b)


def test_canonical_json_rejects_nan() -> None:
    with pytest.raises(ValueError):
        canonical_json({"bad": math.nan})


def test_revision_id_shape_and_determinism() -> None:
    first = compute_revision_id(**MATERIAL)
    second = compute_revision_id(**MATERIAL)
    assert first == second
    assert first.startswith("rev:")
    assert len(first) == 4 + 32


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("world_id", "world:other"),
        ("parent_revision_id", "rev:parent"),
        ("operation_ids", ["op:1", "op:2"]),
        ("graph_schema", "dm_union_graph_v2"),
        ("graph_payload_sha256", "cd" * 32),
    ],
)
def test_revision_id_sensitive_to_every_input(field: str, value: object) -> None:
    changed = dict(MATERIAL)
    changed[field] = value
    assert compute_revision_id(**changed) != compute_revision_id(**MATERIAL)


def test_operation_id_order_is_significant() -> None:
    changed = dict(MATERIAL)
    changed["operation_ids"] = ["op:2", "op:1"]
    assert compute_revision_id(**changed) != compute_revision_id(**MATERIAL)
