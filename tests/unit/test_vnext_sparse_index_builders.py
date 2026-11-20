"""Sparse temporary work must retain complete, deterministic public indexes."""

from __future__ import annotations

from collections import defaultdict

import pytest

from dungeonmind.application.vnext import builder
from dungeonmind.application.vnext._read_artifact import decode_read_artifact
from dungeonmind.application.vnext._source_wire import encode_source_wire
from dungeonmind.application.vnext.model import compute_semantic_digest
from dungeonmind.application.vnext.records import ParsedEntityRefValue
from tests.unit.test_vnext_source_wire import _parsed, _payload, _source


def _graph(shape, isolated):
    payload = _payload()
    ids = [row["entity_id"] for row in payload["entities"]]
    template = payload["assertions"][0]
    payload["assertions"] = []
    payload["aliases"] = payload["aliases"] if shape == "aliases" else []
    pairs = {
        "empty": [],
        "aliases": [],
        "sparse": [(ids[0], ids[1])],
        "self-loop": [(ids[0], ids[0]), (ids[0], ids[0])],
        "dense": [(left, right) for left in ids for right in ids],
    }[shape]
    for index, (left, right) in enumerate(pairs):
        payload["assertions"].append(
            {
                **template,
                "assertion_id": f"assertion:edge-{index}",
                "subject_entity_id": left,
                "value": {"kind": "entity_ref", "entity_id": right},
            }
        )
    for index in range(isolated):
        payload["entities"].append(
            {
                "entity_id": f"ent:isolated-{index}",
                "schema_version": "dm_entity_v1",
            }
        )
        payload["evidence"].append(
            {
                **payload["evidence"][0],
                "evidence_ref_id": f"ev:unused-{index}",
            }
        )
    return payload


def _assert_complete_indexes(parsed):
    entities = set(parsed.entities_by_id)
    assertions = parsed.assertions_by_id
    refs = {aid: a for aid, a in assertions.items() if isinstance(a.value, ParsedEntityRefValue)}
    for name in (
        "assertions_by_subject",
        "entity_ref_outgoing",
        "entity_ref_incoming",
        "entity_ref_outgoing_assertions",
        "entity_ref_incoming_assertions",
        "entity_adjacency",
        "aliases_by_entity",
    ):
        assert set(getattr(parsed, name)) == entities
    for eid in entities:
        outgoing = {a.value.entity_id for a in refs.values() if a.subject_entity_id == eid}
        incoming = {a.subject_entity_id for a in refs.values() if a.value.entity_id == eid}
        assert parsed.entity_ref_outgoing[eid] == tuple(sorted(outgoing))
        assert parsed.entity_ref_incoming[eid] == tuple(sorted(incoming))
        assert parsed.entity_adjacency[eid] == tuple(sorted(outgoing | incoming))
        assert parsed.assertions_by_subject[eid] == tuple(
            sorted(aid for aid, a in assertions.items() if a.subject_entity_id == eid)
        )
        assert parsed.entity_ref_outgoing_assertions[eid] == tuple(
            sorted(aid for aid, a in refs.items() if a.subject_entity_id == eid)
        )
        assert parsed.entity_ref_incoming_assertions[eid] == tuple(
            sorted(aid for aid, a in refs.items() if a.value.entity_id == eid)
        )
        assert parsed.aliases_by_entity[eid] == tuple(
            sorted(aid for aid, a in parsed.aliases_by_id.items() if a.entity_id == eid)
        )
    assert set(parsed.evidence_supporters) == set(parsed.evidence_by_id)
    for evid in parsed.evidence_by_id:
        assert parsed.evidence_supporters[evid] == tuple(
            sorted(aid for aid, a in assertions.items() if evid in a.metadata.evidence_ref_ids)
        )


@pytest.mark.parametrize("shape", ["empty", "sparse", "self-loop", "dense", "aliases"])
@pytest.mark.parametrize("reverse", [False, True])
def test_sparse_builders_preserve_all_index_keys_memberships_and_digest(shape, reverse):
    payload = _graph(shape, 15)
    source = _source(payload)
    reference = _parsed(source, payload)
    if reverse:
        for rows in payload.values():
            rows.reverse()
    # Raw array permutation changes the source digest. Test record order with
    # the same identity, and independently verify the newly sealed wire below.
    decoded = _parsed(_source(payload), payload)
    parsed = builder.build_parsed_knowledge_revision_from_records(
        reference.identity,
        entities=list(decoded.entities_by_id.values())[::-1] if reverse else decoded.entities_by_id,
        assertions=list(decoded.assertions_by_id.values())[::-1]
        if reverse
        else decoded.assertions_by_id,
        aliases=decoded.aliases_by_id,
        evidence=list(decoded.evidence_by_id.values())[::-1] if reverse else decoded.evidence_by_id,
    )
    assert parsed == reference
    _assert_complete_indexes(parsed)
    assert parsed.semantic_digest == compute_semantic_digest(
        parsed.identity,
        parsed.entities_by_id,
        parsed.assertions_by_id,
        parsed.aliases_by_id,
        parsed.evidence_by_id,
    )
    wire_source = _source(payload)
    artifact = decode_read_artifact(encode_source_wire(wire_source), wire_source)
    assert artifact == _parsed(wire_source, payload)


@pytest.mark.parametrize("shape", ["empty", "sparse", "self-loop", "dense", "aliases"])
def test_isolated_entities_and_evidence_allocate_no_mutable_index_buckets(shape, monkeypatch):
    allocations = []

    def tracked_defaultdict(factory):
        def create():
            bucket = factory()
            allocations.append(bucket)
            return bucket

        return defaultdict(create)

    monkeypatch.setattr(builder, "defaultdict", tracked_defaultdict)
    counts = []
    for isolated in (0, 1000):
        allocations.clear()
        payload = _graph(shape, isolated)
        parsed = _parsed(_source(payload), payload)
        _assert_complete_indexes(parsed)
        assert all(bucket for bucket in allocations), "never retain an empty mutable bucket"
        counts.append(len(allocations))
    assert counts[0] == counts[1]
    if shape == "empty":
        assert counts == [0, 0]
    else:
        assert counts[0] > 0


@pytest.mark.parametrize("shape", ["empty", "sparse", "self-loop", "dense", "aliases"])
def test_dense_indexes_avoid_pair_storage_and_preserve_hashes(shape):
    import copy
    import pickle

    from dungeonmind.application.vnext.frozen_json import FrozenDict

    payload = _graph(shape, 12)
    parsed = _parsed(_source(payload), payload)
    _assert_complete_indexes(parsed)
    names = (
        "assertions_by_subject",
        "entity_ref_outgoing",
        "entity_ref_incoming",
        "entity_ref_outgoing_assertions",
        "entity_ref_incoming_assertions",
        "entity_adjacency",
        "aliases_by_entity",
    )
    for name in names:
        index = getattr(parsed, name)
        reference = FrozenDict(dict(index.items()))
        assert type(index) is FrozenDict
        assert list(index.items()) == list(reference.items())
        assert index._items is None and not index._hash_ready
        assert index == reference and hash(index) == hash(reference)
        assert index._items is None and index._hash_ready
        assert copy.copy(index) is index and copy.deepcopy(index) is index
        restored = pickle.loads(pickle.dumps(index))
        assert restored == reference and hash(restored) == hash(reference)
        with pytest.raises(TypeError):
            index._items = ()
        with pytest.raises(TypeError):
            index._proxy["ent:injected"] = ()
    restored = pickle.loads(pickle.dumps(parsed))
    assert restored == parsed and hash(restored) == hash(parsed)


def test_private_dense_index_copies_buckets_and_preserves_empty_domain_order():
    from dungeonmind.application.vnext.frozen_json import FrozenDict, _frozen_dense_index

    entity_ids = ("ent:a", "ent:b", "ent:c")
    buckets = {"ent:b": ["assertion:z", "assertion:a"]}
    actual = _frozen_dense_index(entity_ids, buckets)
    expected = FrozenDict({"ent:a": (), "ent:b": ("assertion:a", "assertion:z"), "ent:c": ()})
    buckets["ent:b"].clear()
    buckets["ent:c"] = ["assertion:later"]
    assert actual == expected and hash(actual) == hash(expected)
    assert tuple(actual) == entity_ids and actual._items is None
    assert _frozen_dense_index((), {}) == FrozenDict()


def test_concurrent_builds_keep_index_mappings_local():
    from concurrent.futures import ThreadPoolExecutor

    payload = _graph("sparse", 20)
    source = _source(payload)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: _parsed(source, payload), range(12)))
    assert all(parsed == results[0] for parsed in results)
    for parsed in results:
        _assert_complete_indexes(parsed)
    left = results[0].aliases_by_entity
    right = results[1].aliases_by_entity
    assert left == right and left._proxy is not right._proxy
    assert left._items is None and right._items is None


def test_dense_index_rejects_memberships_outside_its_primary_domain():
    from dungeonmind.application.vnext.frozen_json import _frozen_dense_index

    with pytest.raises(ValueError, match="outside primary key domain"):
        _frozen_dense_index(("ent:a",), {"ent:unknown": ["assertion:one"]})
