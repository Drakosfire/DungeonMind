"""Source equivalence is required independently of a cache blob's own checksum."""

from __future__ import annotations

import copy
import json
from dataclasses import replace

import pytest

from dungeonmind.application.vnext._source_wire import (
    UnsupportedSourceWire,
    decode_source_wire,
    encode_source_wire,
)
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.materialization import (
    decode_native_graph_payload,
    encode_native_graph_payload,
)
from dungeonmind.application.vnext.records import StoredKnowledgeRevision
from dungeonmind.domain.canonical import canonical_json, canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from tests.unit.test_vnext_parsed_knowledge_revision import (
    _make_base_revision,
    _make_sample_aliases,
    _make_sample_assertions,
    _make_sample_entities,
    _make_sample_evidence,
)


def _payload():
    return encode_native_graph_payload(
        entities={x.entity_id: x for x in _make_sample_entities()},
        assertions={x.assertion_id: x for x in _make_sample_assertions()},
        aliases={x.alias_id: x for x in _make_sample_aliases()},
        evidence={x.evidence_ref_id: x for x in _make_sample_evidence()},
    )


def _source(payload):
    revision = _make_base_revision().model_copy(
        update={
            "graph_payload_sha256": canonical_sha256(payload),
        }
    )
    return StoredKnowledgeRevision.seal(revision, payload)


def _packet(source):
    return json.loads(encode_source_wire(source))


def _bytes(packet):
    return canonical_json(packet).encode()


def _parsed(source, payload):
    return build_parsed_knowledge_revision(
        revision=source.revision,
        decoded_content=decode_native_graph_payload(payload),
    )


def test_complete_source_and_parsed_index_digest_equality():
    source = _source(_payload())
    wire = encode_source_wire(source)
    restored = decode_source_wire(wire, source)
    assert canonical_json(restored) == source._payload_json
    assert _parsed(source, restored) == _parsed(source, source.graph_payload)
    assert encode_source_wire(source) == wire
    restored["entities"].clear()
    assert decode_source_wire(wire, source)["entities"]


@pytest.mark.parametrize("values", [(True, 1), (1, 1.0), (0.0, -0.0)])
def test_pooling_preserves_numeric_representation(values):
    payload = _payload()
    for assertion, value in zip(payload["assertions"], values, strict=False):
        assertion["value"] = {"kind": "literal", "value": value}
        assertion["metadata"]["domain_metadata"] = [{"schema": "test:value", "payload": value}]
    source = _source(payload)
    restored = decode_source_wire(encode_source_wire(source), source)
    for original, actual in zip(payload["assertions"], restored["assertions"], strict=True):
        assert canonical_json(original) == canonical_json(actual)
    assert _parsed(source, restored) == _parsed(source, payload)
    assert canonical_json(restored) == canonical_json(payload)


@pytest.mark.parametrize(
    "variant", ["reverse", "offset", "defaults", "coercion", "unicode", "empty"]
)
def test_lossless_source_forms(variant):
    payload = _payload()
    if variant == "reverse":
        for rows in payload.values():
            rows.reverse()
    elif variant == "offset":
        for row in payload["assertions"]:
            row["metadata"]["temporal_scope"] = {
                "kind": "utc_interval",
                "valid_from": "2026-01-01T01:00:00+01:00",
                "valid_until": None,
            }
    elif variant == "defaults":
        for row in payload["assertions"]:
            row["metadata"].pop("domain_metadata")
    elif variant == "coercion":
        payload["evidence"][0]["can_open_source"] = 1
    elif variant == "unicode":
        payload["assertions"][0]["value"] = {
            "kind": "literal",
            "value": {"🧙": ['\\"[]{}', "é\n", -0.0, True]},
        }
    elif variant == "empty":
        payload = {key: [] for key in payload}
    source = _source(payload)
    restored = decode_source_wire(encode_source_wire(source), source)
    assert canonical_json(restored) == canonical_json(payload)
    assert _parsed(source, restored) == _parsed(source, payload)


@pytest.mark.parametrize("variant", ["root", "entity", "assertion", "schema", "deep"])
def test_unsupported_source_does_not_replace_ordinary_parser(variant):
    payload = _payload()
    if variant == "root":
        payload["extension"] = "ignored by ordinary parser"
    elif variant in ("entity", "assertion"):
        key = "entities" if variant == "entity" else "assertions"
        payload[key][0].pop("schema_version")
    elif variant == "deep":
        value = []
        for _ in range(65):
            value = [value]
        payload["assertions"][0]["value"] = {"kind": "literal", "value": value}
    source = _source(payload)
    if variant == "schema":
        source = replace(
            source, revision=source.revision.model_copy(update={"graph_schema": "other"})
        )
    else:
        decode_native_graph_payload(payload)
    with pytest.raises(UnsupportedSourceWire):
        encode_source_wire(source)


@pytest.mark.parametrize(
    "variant",
    [
        "negative",
        "bool",
        "float",
        "out_of_range",
        "arity",
        "table",
        "extra",
        "missing",
        "unused",
        "duplicate",
        "envelope",
        "graph",
        "metadata",
        "literal",
        "entity",
        "alias",
        "evidence",
        "noncanonical",
        "chunk_duplicate",
        "chunk_infinite",
        "chunk_overflow",
        "chunk_depth",
        "expansion",
        "normalized_extra",
    ],
)
def test_matching_version_corruption_fails_closed(variant):
    source = _source(_payload())
    packet = _packet(source)
    if variant in ("negative", "bool", "float", "out_of_range"):
        packet["entities"][0] = {
            "negative": -1,
            "bool": True,
            "float": 0.0,
            "out_of_range": len(packet["strings"]),
        }[variant]
    elif variant == "arity":
        packet["assertions"][0].append(0)
    elif variant == "table":
        packet["strings"] = {}
    elif variant == "extra":
        packet["extra"] = 1
    elif variant == "missing":
        packet.pop("metadata")
    elif variant == "unused":
        packet["strings"].append("unused")
    elif variant == "duplicate":
        packet["metadata"].append(packet["metadata"][0])
    elif variant == "envelope":
        packet["envelope_sha256"] = "0" * 64
    elif variant == "graph":
        packet["graph_sha256"] = "0" * 64
    elif variant == "entity":
        packet["strings"][packet["entities"][0]] = "ent:forged"
    elif variant == "metadata":
        metadata = json.loads(packet["metadata"][0])
        metadata["claim_mode"] = "test:forged"
        packet["metadata"][0] = canonical_json(metadata)
    elif variant == "literal":
        packet["strings"][packet["assertions"][0][3]] = '{"kind":"literal","value":false}'
    elif variant in ("alias", "evidence"):
        key = "aliases" if variant == "alias" else "evidence"
        row = json.loads(packet[key][0])
        row["alias_text" if variant == "alias" else "locator"] = "forged"
        packet[key][0] = canonical_json(row)
    elif variant.startswith("chunk_") or variant == "noncanonical":
        packet["metadata"][0] = {
            "noncanonical": '{ "a": 1}',
            "chunk_duplicate": '{"a":1,"a":2}',
            "chunk_infinite": '{"a":NaN}',
            "chunk_overflow": '{"a":1e9999}',
            "chunk_depth": "[" * 65 + "0" + "]" * 65,
        }[variant]
    elif variant == "expansion":
        packet["assertions"] *= 10
    elif variant == "normalized_extra":
        packet["normalized"] = {"entity_id": "ent:forged"}
    body = _bytes(packet)
    # Supply replacement bytes directly, without relying on a stale blob checksum.
    with pytest.raises(PersistenceIntegrityError):
        decode_source_wire(body, source)


@pytest.mark.parametrize(
    "body",
    [
        b"{",
        b"[]",
        b'{"format":1}',
        b'{"format":"dm_native_source_wire_v1","format":"other"}',
        b"\xff",
        b"[" * 100,
    ],
)
def test_invalid_framing_is_typed(body):
    with pytest.raises(PersistenceIntegrityError):
        decode_source_wire(body, _source(_payload()))


def test_size_bound_precedes_json_parsing(monkeypatch):
    source = _source({key: [] for key in _payload()})

    def forbidden(*args, **kwargs):
        pytest.fail("oversized blob reached JSON parser")

    monkeypatch.setattr("dungeonmind.application.vnext._source_wire.json.loads", forbidden)
    with pytest.raises(PersistenceIntegrityError, match="byte limit"):
        decode_source_wire(b" " * 10000, source)


@pytest.mark.parametrize("nesting", [0, 3, 40])
def test_unknown_version_falls_back(nesting):
    source = _source(_payload())
    body = b'{"format":"future","body":' + b"[" * nesting + b"0" + b"]" * nesting + b"}"
    assert decode_source_wire(body, source) is None


def test_matching_version_keeps_its_strict_packet_depth():
    source = _source(_payload())
    packet = _packet(source)
    packet["entities"] = [[[]]]
    with pytest.raises(PersistenceIntegrityError, match="nesting"):
        decode_source_wire(_bytes(packet), source)


@pytest.mark.parametrize(
    "field,value",
    [
        ("operation_ids", ["op:changed"]),
        ("space_id", "space:other"),
        ("revision_id", "rev:other"),
        ("parent_revision_id", "rev:other-parent"),
        ("graph_schema", "other"),
    ],
)
def test_source_envelope_representation_bound(field, value):
    source = _source(_payload())
    wire = encode_source_wire(source)
    changed = source.revision.model_copy(update={field: value})
    with pytest.raises(PersistenceIntegrityError, match="envelope"):
        decode_source_wire(wire, replace(source, revision=changed))


def test_no_source_or_packet_mutation():
    source = _source(_payload())
    before = copy.deepcopy(source)
    wire = encode_source_wire(source)
    decode_source_wire(wire, source)
    assert source == before
