"""JSON validation retains its contract without per-value cyclic callables."""

from __future__ import annotations

import gc
from datetime import datetime
from decimal import Decimal
from types import FunctionType

import pytest
from pydantic import ValidationError

from dungeonmind.contracts.vnext import common
from dungeonmind.contracts.vnext.common import DomainMetadataEntry
from dungeonmind.contracts.vnext.domain import LiteralValue
from dungeonmind.domain.canonical import canonical_json


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        0,
        1,
        -1,
        1.0,
        0.0,
        -0.0,
        1e308,
        '🧙\n\\"',
        [],
        {},
        [None, True, -0.0, {"items": [1, 1.0, "é"]}],
        {"nested": {"integer": 1, "bool": True, "float": 1.0, "zero": -0.0}},
    ],
)
def test_valid_json_preserves_identity_representation_and_public_models(value):
    assert common._json_value(value) is value
    literal = LiteralValue(value=value)
    metadata = DomainMetadataEntry(schema="test:metadata", payload=value)
    assert literal.value is value and metadata.payload is value
    assert type(literal.value) is type(value)
    assert canonical_json(literal.model_dump(mode="json")["value"]) == canonical_json(value)
    assert canonical_json(metadata.model_dump(mode="json")["payload"]) == canonical_json(value)


@pytest.mark.parametrize(
    "value,message",
    [
        (float("nan"), "JSON values must contain finite numbers"),
        (float("inf"), "JSON values must contain finite numbers"),
        (float("-inf"), "JSON values must contain finite numbers"),
        ([{"x": [float("nan")]}], "JSON values must contain finite numbers"),
        ({1: "bad"}, "JSON object keys must be strings"),
        ({"nested": [{False: None}]}, "JSON object keys must be strings"),
        ({1: float("inf")}, "JSON object keys must be strings"),
        ((1, 2), "value is not canonical JSON-compatible"),
        ({1, 2}, "value is not canonical JSON-compatible"),
        (Decimal("1"), "value is not canonical JSON-compatible"),
        (datetime(2026, 1, 1), "value is not canonical JSON-compatible"),
        (b"data", "value is not canonical JSON-compatible"),
        ({"nested": [object()]}, "value is not canonical JSON-compatible"),
    ],
)
def test_rejection_order_messages_and_model_error_locations(value, message):
    with pytest.raises(ValueError) as error:
        common._json_value(value)
    assert str(error.value) == message
    for model, argument in ((LiteralValue, "value"), (DomainMetadataEntry, "payload")):
        kwargs = {argument: value}
        if argument == "payload":
            kwargs["schema"] = "test:metadata"
        with pytest.raises(ValidationError) as error:
            model(**kwargs)
        first = error.value.errors(include_url=False)[0]
        assert first["loc"] == (argument,)
        assert first["type"] == "value_error"
        assert first["msg"] == "Value error, " + message


def _self_recursive_callable_count():
    count = 0
    for function in gc.get_objects():
        if (
            not isinstance(function, FunctionType)
            or function.__module__ != common.__name__
            or not function.__closure__
        ):
            continue
        for cell in function.__closure__:
            try:
                recursive = cell.cell_contents is function
            except ValueError:
                recursive = False
            if recursive:
                count += 1
                break
    return count


def test_repeated_public_validation_leaves_no_per_value_callable_cycles():
    # Scoped test-only GC control lets unreachable closures remain observable.
    # The production validator never changes GC settings.
    was_enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        before = _self_recursive_callable_count()
        for value in ("Object", 1, True, -0.0, None) * 200:
            assert LiteralValue(value=value).value is value
        assert _self_recursive_callable_count() == before
    finally:
        if was_enabled:
            gc.enable()
        gc.collect()


def test_unknown_public_fields_still_fail_closed():
    with pytest.raises(ValidationError) as error:
        LiteralValue.model_validate({"kind": "literal", "value": True, "future": 1})
    assert error.value.errors(include_url=False)[0]["type"] == "extra_forbidden"
