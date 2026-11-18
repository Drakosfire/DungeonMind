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
