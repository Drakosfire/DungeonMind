"""Owning strict literal and explicit-family contract evidence."""

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from dungeonmind.contracts.contribution import (
    GraphContributionAssertionV4,
    ReviewedPropertyLiteralV1,
    parse_reviewed_property_literal,
)


def envelope(value=None, **extra):
    return {
        "schema_version": "dm_reviewed_property_literal_v1",
        "property_term": "dnd5e:test_fact",
        "value": value,
        **extra,
    }


@pytest.mark.parametrize(
    "value", [None, True, False, 0, -1, 1.5, "text", [], {}, {"a": [1, None, True]}]
)
def test_strict_json_roundtrip(value):
    raw = json.dumps(envelope(value), ensure_ascii=False)
    assert parse_reviewed_property_literal(raw).value == value


@pytest.mark.parametrize(
    "value", [(1,), Decimal("1"), {1: "key"}, float("nan"), float("inf"), 1 << 4096, b"x", object()]
)
def test_python_values_rejected_before_coercive_serialization(value):
    with pytest.raises((ValidationError, ValueError)):
        ReviewedPropertyLiteralV1.model_validate(envelope(value))


@pytest.mark.parametrize(
    "raw",
    [
        '{"schema_version":"dm_reviewed_property_literal_v1","property_term":"dnd5e:x","value":{"a":1,"a":2}}',
        '{"schema_version":"dm_reviewed_property_literal_v1","property_term":"dnd5e:x","value":NaN}',
        '{"schema_version":"dm_reviewed_property_literal_v1","property_term":"dnd5e:x","value":1e999}',
    ],
)
def test_duplicate_keys_and_nonfinite_json_rejected(raw):
    with pytest.raises((ValidationError, ValueError)):
        parse_reviewed_property_literal(raw)


@pytest.mark.parametrize(
    "update",
    [
        {"metadata": {}},
        {"property_term": ""},
        {"property_term": "x" * 513},
        {"value": "é" * 8193},
        {"value": [0] * 1025},
        {"value": {str(i): i for i in range(257)}},
        {"value": {"x" * 1025: 1}},
        {"value": ["x" * 16384] * 5},
        {"value": [[0] * 1024] * 4},
    ],
)
def test_closed_envelope_and_resource_bounds(update):
    with pytest.raises((ValidationError, ValueError)):
        ReviewedPropertyLiteralV1.model_validate(envelope() | update)


def test_depth_boundary_and_mutated_literal_extra_state():
    value = None
    for _ in range(31):
        value = [value]
    ReviewedPropertyLiteralV1.model_validate(envelope(value))
    with pytest.raises(ValidationError):
        ReviewedPropertyLiteralV1.model_validate(envelope([[value]]))
    model = ReviewedPropertyLiteralV1.model_validate(envelope())
    object.__setattr__(model, "__pydantic_extra__", {"metadata": {}})
    with pytest.raises(ValidationError):
        ReviewedPropertyLiteralV1.model_validate(model)


def test_property_bytes_and_mutated_state_are_not_coerced():
    from tests.unit.test_contribution_review_v4 import candidate

    raw = candidate().assertions[0].model_dump()
    raw["value"] = raw["value"].encode()
    with pytest.raises(ValidationError):
        GraphContributionAssertionV4.model_validate(raw)
    raw["assertion_kind"] = b"property"
    with pytest.raises(ValidationError):
        GraphContributionAssertionV4.model_validate(raw)
    item = candidate().assertions[0]
    item.value = b"{}"
    with pytest.raises(ValidationError):
        GraphContributionAssertionV4.model_validate(item)


def test_every_literal_resource_bound_at_and_one_over():
    def check(at, over):
        ReviewedPropertyLiteralV1.model_validate(at)
        with pytest.raises((ValidationError, ValueError)):
            ReviewedPropertyLiteralV1.model_validate(over)

    check(envelope([0] * 1024), envelope([0] * 1025))
    check(envelope({str(i): 0 for i in range(256)}), envelope({str(i): 0 for i in range(257)}))
    check(envelope("é" * 8192), envelope("é" * 8192 + "x"))
    check(envelope({"é" * 512: 0}), envelope({"é" * 512 + "x": 0}))
    check(
        envelope() | {"property_term": "dnd5e:" + "x" * 506},
        envelope() | {"property_term": "dnd5e:" + "x" * 507},
    )
    check(envelope(1 << 4095), envelope(1 << 4096))
    depth = None
    for _ in range(31):
        depth = [depth]
    check(envelope(depth), envelope([depth]))
    at_nodes = [[0] * n for n in (1024, 1024, 1024, 1013)]
    over_nodes = [[0] * n for n in (1024, 1024, 1024, 1014)]
    check(envelope(at_nodes), envelope(over_nodes))

    # Independent standard-library canonical encoding, not the production bound helper.
    def canonical(raw):
        return json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    value = ["", "", "", ""]
    remaining = 65536 - len(canonical(envelope(value)).encode("utf-8"))
    for i in range(4):
        take = min(16384, remaining)
        value[i] = "x" * take
        remaining -= take
    assert remaining == 0
    at = envelope(value)
    assert len(canonical(at).encode("utf-8")) == 65536
    over = envelope([*value[:3], value[3] + "x"])
    assert len(canonical(over).encode("utf-8")) == 65537
    check(at, over)


def test_root_duplicate_and_missing_required_null_are_rejected():
    with pytest.raises(ValueError):
        parse_reviewed_property_literal(
            '{"schema_version":"dm_reviewed_property_literal_v1",'
            '"property_term":"dnd5e:x","value":null,"value":false}'
        )
    raw = envelope()
    del raw["value"]
    with pytest.raises(ValidationError):
        ReviewedPropertyLiteralV1.model_validate(raw)


def test_intent_digest_cannot_serialize_a_mutated_nonstring_property():
    from dungeonmind.contracts.contribution_review_v4 import derive_review_intent_sha256_v4
    from tests.unit.test_contribution_review_v4 import upgrade_intent

    intent = upgrade_intent()
    intent.candidate_contribution.assertions[0].value = b"{}"
    fields = {
        key: getattr(intent, key)
        for key in [
            "operation_id",
            "world_id",
            "campaign_id",
            "plan_ref",
            "candidate_contribution",
            "identity_proposals",
            "identity_verdicts",
            "assertion_verdicts",
            "reviewer_id",
            "reviewed_at",
        ]
    }
    with pytest.raises(ValidationError):
        derive_review_intent_sha256_v4(**fields)
