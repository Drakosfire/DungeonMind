"""Hash laziness is private optimization state, never mutable knowledge content."""

from __future__ import annotations

import copy
import pickle
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from dungeonmind.application.vnext._read_artifact import decode_read_artifact
from dungeonmind.application.vnext._source_wire import encode_source_wire
from dungeonmind.application.vnext.frozen_json import FrozenDict, _deferred_frozen_dict
from dungeonmind.application.vnext.records import ParsedAssertion, ParsedAssertionMetadata
from tests.unit.test_vnext_source_wire import _parsed, _payload, _source


class CountedHash:
    def __init__(self):
        self.calls = 0

    def __hash__(self):
        self.calls += 1
        return 37


def test_public_construction_keeps_eager_hash_behavior():
    value = CountedHash()
    frozen = FrozenDict({"value": value})
    assert value.calls == 1
    assert hash(frozen) == hash(frozen)
    assert value.calls == 1


def test_private_construction_defers_then_caches_requested_hash():
    value = CountedHash()
    frozen = _deferred_frozen_dict({"value": value})
    assert value.calls == 0
    assert list(frozen) == ["value"] and frozen["value"] is value
    expected = hash((("value", value),))
    assert hash(frozen) == expected
    assert value.calls == 2  # One explicit reference hash and one mapping hash.
    assert hash(frozen) == expected
    assert value.calls == 2


@pytest.mark.parametrize(
    "source",
    [
        {},
        {"b": 2, "a": 1},
        {"x": (True, -0.0, "🧙")},
        {"nested": FrozenDict({"x": (1, 1.0, False)})},
    ],
)
def test_copy_pickle_order_and_hash_match_public_constructor(source):
    expected = FrozenDict(source)
    actual = _deferred_frozen_dict(source)
    source["later"] = 3
    assert actual == expected
    assert list(actual.items()) == list(expected.items())
    assert repr(actual) == repr(expected)
    assert hash(actual) == hash(expected)
    assert copy.copy(actual) is actual
    assert copy.deepcopy(actual) is actual
    restored = pickle.loads(pickle.dumps(actual))
    assert restored == expected and hash(restored) == hash(expected)
    with pytest.raises(TypeError):
        actual._hash_ready = False
    with pytest.raises(TypeError):
        actual["later"] = 4


def test_unhashable_values_raise_same_error_and_remain_unhashable():
    for frozen in (FrozenDict({"x": []}), _deferred_frozen_dict({"x": []})):
        for _ in range(2):
            with pytest.raises(TypeError, match="contains unhashable values"):
                hash(frozen)


def test_copy_does_not_request_hash_and_pickle_preserves_hash_result():
    actual = _deferred_frozen_dict({"a": (1, 2)})
    assert copy.deepcopy(actual) is actual
    assert not actual._hash_ready
    restored = pickle.loads(pickle.dumps(actual))
    assert hash(restored) == hash(actual)


def test_concurrent_first_hash_is_stable_and_cannot_mutate_data():
    source = {str(i): (i, "value") for i in range(100)}
    frozen = _deferred_frozen_dict(source)
    expected = hash(FrozenDict(source))
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(lambda _: hash(frozen), range(32))) == [expected] * 32
    assert dict(frozen) == source


def test_fast_factory_removes_record_hashes_until_requested():
    payload = _payload()
    template = payload["assertions"][0]
    payload["assertions"] = [dict(template, assertion_id=f"assertion:{i}") for i in range(100)]
    source = _source(payload)
    body = encode_source_wire(source)
    assertion_hash = ParsedAssertion.__hash__
    metadata_hash = ParsedAssertionMetadata.__hash__
    with (
        patch.object(ParsedAssertion, "__hash__", autospec=True, side_effect=assertion_hash) as ah,
        patch.object(
            ParsedAssertionMetadata, "__hash__", autospec=True, side_effect=metadata_hash
        ) as mh,
    ):
        parsed = decode_read_artifact(body, source)
        assert ah.call_count == mh.call_count == 0
        expected = _parsed(source, payload)
        assert ah.call_count == mh.call_count == 100
        assert parsed == expected
        assert parsed.semantic_digest == expected.semantic_digest
        ah.reset_mock()
        mh.reset_mock()
        assert hash(parsed.assertions_by_id) == hash(expected.assertions_by_id)
        assert ah.call_count == mh.call_count == 100
        assert hash(parsed.assertions_by_id) == hash(expected.assertions_by_id)
        assert ah.call_count == mh.call_count == 100
    assert hash(parsed) == hash(expected)
    assertion = next(iter(parsed.assertions_by_id.values()))
    with pytest.raises((TypeError, FrozenInstanceError)):
        assertion.metadata.claim_mode = "test:changed"


@pytest.mark.parametrize("size", [0, 10, 50_000])
def test_private_record_maps_do_not_retain_pair_tuples(size):
    source = {f"entity:{i}": i for i in range(size)}
    expected = FrozenDict(source)
    actual = _deferred_frozen_dict(source)
    source.clear()
    assert actual._items is None  # Removed work: no second per-record pair graph.
    assert list(actual.items()) == list(expected.items())
    assert dict(actual) == dict(expected)
    assert hash(actual) == hash(expected)
    assert actual._items is None
    assert copy.copy(actual) is actual and copy.deepcopy(actual) is actual
    restored = pickle.loads(pickle.dumps(actual))
    assert restored == expected and hash(restored) == hash(expected)
    assert actual._items is None


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
def test_private_pair_elision_preserves_pickle_representation(protocol):
    source = {"z": (True, -0.0), "a": FrozenDict({"nested": (1, False)})}
    expected = FrozenDict(source)
    actual = _deferred_frozen_dict(source)
    assert pickle.dumps(actual, protocol) == pickle.dumps(expected, protocol)
    assert actual._items is None and not actual._hash_ready
    assert hash(actual) == hash(expected)
    assert pickle.dumps(actual, protocol) == pickle.dumps(expected, protocol)
    assert actual._items is None
