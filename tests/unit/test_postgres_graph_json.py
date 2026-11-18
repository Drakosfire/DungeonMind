"""Differential source-byte proof and bounded full-graph allocation regression."""

from __future__ import annotations

import json
import random
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from dungeonmind.domain.canonical import canonical_json
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres import _graph_json as graph


def _native(rows):
    return {"entities": rows, "assertions": [], "aliases": [], "evidence": []}


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        1,
        1.0,
        -0.0,
        1e-20,
        1e20,
        2**200,
        '雪\n\u2028😀\\"',
        [],
        {},
        {"z": [1, False], "a": {"x": "é"}},
    ],
)
def test_native_canonical_bytes_match_ordinary(value):
    payload = _native([value, {"nested": value}])
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    assert graph.canonical_graph_json(text) == canonical_json(json.loads(text))
    assert graph.canonical_graph_json(
        json.dumps(dict(reversed(list(payload.items()))))
    ) == canonical_json(payload)


def test_supported_native_path_does_not_load_a_whole_graph():
    payload = _native([{"id": str(i), "value": [i, True, -0.0]} for i in range(5000)])
    text, expected = json.dumps(payload), canonical_json(payload)
    with patch.object(graph.json, "loads", side_effect=AssertionError("whole graph allocated")):
        assert graph.canonical_graph_json(text) == expected


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"opaque": [1, {"a": False}]},
        {"entities": {}, "assertions": [], "aliases": [], "evidence": []},
        {**_native([]), "future": {"field": 1}},
    ],
)
def test_opaque_shapes_use_ordinary_fallback(payload):
    text = json.dumps(payload)
    with patch.object(graph.json, "loads", wraps=json.loads) as load:
        assert graph.canonical_graph_json(text) == canonical_json(payload)
        load.assert_called_once_with(text)


def test_deep_records_fall_back_without_changing_canonical_bytes():
    nested = 1
    for _ in range(80):
        nested = [nested]
    payload = _native([nested])
    text = json.dumps(payload)
    with patch.object(graph.json, "loads", wraps=json.loads) as load:
        assert graph.canonical_graph_json(text) == canonical_json(payload)
        load.assert_called_once_with(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ",
        "{",
        '{"entities":[1,],"assertions":[],"aliases":[],"evidence":[]}',
        '{"entities":[],"assertions":[],"aliases":[],"evidence":[],}',
        json.dumps(_native([])) + "\u2003",
        json.dumps(_native([])) + " false",
        json.dumps(_native([])).replace('"entities": []', '"entities": [1 2]'),
        json.dumps(_native([])).replace('"entities": []', '"entities": ["bad\\q"]'),
    ],
)
def test_malformed_input_is_rejected_by_ordinary_decoder(text):
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
    with pytest.raises(json.JSONDecodeError):
        graph.canonical_graph_json(text)


def test_every_truncated_prefix_fails_closed():
    text = json.dumps(_native([{"x": [1, 'escaped\\"', False]}]))
    for end in range(len(text)):
        with pytest.raises(json.JSONDecodeError):
            graph.canonical_graph_json(text[:end])


@pytest.mark.parametrize(
    "text",
    [
        '{"entities":[],"entities":[1],"aliases":[],"assertions":[],"evidence":[]}',
        '{"entities":[{"x":1,"x":2}],"aliases":[],"assertions":[],"evidence":[]}',
    ],
)
def test_duplicate_keys_match_ordinary_decoder(text):
    assert graph.canonical_graph_json(text) == canonical_json(json.loads(text))


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity", "1e9999"])
def test_nonfinite_values_remain_rejected(constant):
    text = json.dumps(_native([])).replace('"entities": []', f'"entities": [{constant}]')
    with pytest.raises(ValueError):
        canonical_json(json.loads(text))
    with pytest.raises(ValueError):
        graph.canonical_graph_json(text)


@pytest.mark.parametrize("text", ["null", "[]", "1", '"text"', "true"])
def test_nonobject_graphs_remain_integrity_errors(text):
    with pytest.raises(PersistenceIntegrityError, match="not an object"):
        graph.canonical_graph_json(text)


def test_deterministic_random_nested_values_and_concurrent_calls():
    rng = random.Random(2271)

    def value(depth):
        if depth > 4 or rng.randrange(3) == 0:
            return rng.choice([None, True, -0.0, 2**70, '😀\\"', rng.random()])
        if rng.randrange(2):
            return [value(depth + 1) for _ in range(rng.randrange(4))]
        return {f"k{i}": value(depth + 1) for i in range(rng.randrange(4))}

    packets = [
        json.dumps(_native([value(0) for _ in range(8)]), ensure_ascii=False) for _ in range(100)
    ]
    expected = [canonical_json(json.loads(text)) for text in packets]
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(graph.canonical_graph_json, packets)) == expected
