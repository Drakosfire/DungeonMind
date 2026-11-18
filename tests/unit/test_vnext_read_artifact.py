"""Immutable factory differential and removed-work regression checks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from unittest.mock import patch

import pytest

from dungeonmind.application.vnext import _read_artifact as artifact_module
from dungeonmind.application.vnext import builder, model
from dungeonmind.application.vnext._read_artifact import decode_read_artifact
from dungeonmind.application.vnext._source_wire import encode_source_wire
from dungeonmind.application.vnext.frozen_json import canonical_json_text, thaw_json_value
from dungeonmind.application.vnext.model import _stream_semantic_digest, compute_semantic_digest
from dungeonmind.domain.errors import PersistenceIntegrityError
from tests.unit.test_vnext_source_wire import _bytes, _packet, _parsed, _payload, _source


def _digest_arguments(parsed):
    return (
        parsed.identity,
        dict(parsed.entities_by_id),
        dict(parsed.assertions_by_id),
        dict(parsed.aliases_by_id),
        dict(parsed.evidence_by_id),
    )


@pytest.mark.parametrize("value", [True, 1, 1.0, 0.0, -0.0, None, "🧙", {"a": [1, False, -0.0]}])
def test_actual_frozen_values_preserve_representation(value):
    payload = _payload()
    for row in payload["assertions"]:
        row["value"] = {"kind": "literal", "value": value}
        row["metadata"]["domain_metadata"] = [{"schema": "test:value", "payload": value}]
    source = _source(payload)
    parsed = decode_read_artifact(encode_source_wire(source), source)
    ordinary = _parsed(source, payload)
    assert parsed == ordinary
    for aid, assertion in parsed.assertions_by_id.items():
        expected = ordinary.assertions_by_id[aid]
        assert canonical_json_text(assertion.value.value) == canonical_json_text(
            expected.value.value
        )
        assert canonical_json_text(
            assertion.metadata.domain_metadata[0].payload
        ) == canonical_json_text(
            expected.metadata.domain_metadata[0].payload,
        )
    assert _stream_semantic_digest(*_digest_arguments(parsed)) == compute_semantic_digest(
        *_digest_arguments(ordinary),
    )


@pytest.mark.parametrize(
    "visibility",
    [
        {"kind": "public"},
        {"kind": "labels_any", "labels": ["role:a"]},
        {"kind": "labels_all", "labels": ["role:a", "role:b"]},
    ],
)
@pytest.mark.parametrize(
    "temporal",
    [
        {"kind": "timeless"},
        {"kind": "unknown"},
        {"kind": "utc_interval", "valid_from": "2026-01-01T01:00:00+01:00", "valid_until": None},
        {"kind": "domain_ref", "schema": "test:clock", "payload": {"epoch": [1, True]}},
    ],
)
def test_metadata_variant_matrix(visibility, temporal):
    payload = _payload()
    for row in payload["assertions"]:
        row["metadata"]["visibility"] = visibility
        row["metadata"]["temporal_scope"] = temporal
    source = _source(payload)
    parsed = decode_read_artifact(encode_source_wire(source), source)
    assert parsed == _parsed(source, payload)
    assert parsed.semantic_digest == compute_semantic_digest(*_digest_arguments(parsed))


def test_utc_offset_envelope_is_not_conflated():
    source = _source(_payload())
    body = encode_source_wire(source)
    shifted = source.revision.model_copy(
        update={
            "created_at": datetime.fromisoformat("2026-09-15T13:00:00+01:00"),
        }
    )
    assert source.revision.created_at == shifted.created_at
    with pytest.raises(PersistenceIntegrityError, match="envelope"):
        decode_read_artifact(body, replace(source, revision=shifted))


def test_pooling_is_once_per_distinct_source_bytes_and_digest_object():
    payload = _payload()
    template = payload["assertions"][0]
    payload["assertions"] = [dict(template, assertion_id=f"assertion:{i}") for i in range(30)]
    source = _source(payload)
    body = encode_source_wire(source)
    with (
        patch.object(
            artifact_module, "_parse_assertion_metadata", wraps=builder._parse_assertion_metadata
        ) as freeze,
        patch.object(
            model, "_normalized_assertion_metadata", wraps=model._normalized_assertion_metadata
        ) as norm,
    ):
        parsed = decode_read_artifact(body, source)
    assert freeze.call_count == 1
    assert norm.call_count == 1
    assert len({id(a.metadata) for a in parsed.assertions_by_id.values()}) == 1
    assert len({id(a.value) for a in parsed.assertions_by_id.values()}) == 1
    assert parsed == _parsed(source, payload)


def test_private_models_do_not_escape_or_cross_calls():
    source = _source(_payload())
    body = encode_source_wire(source)
    first = decode_read_artifact(body, source)
    second = decode_read_artifact(body, source)
    assert first == second
    aid = next(iter(first.assertions_by_id))
    with pytest.raises((TypeError, AttributeError)):
        first.assertions_by_id[aid].metadata.claim_mode = "test:changed"
    frozen = first.assertions_by_id[aid].metadata.domain_metadata
    if frozen:
        thawed = thaw_json_value(frozen[0].payload)
        if isinstance(thawed, dict):
            thawed["unrelated"] = True
    assert first == decode_read_artifact(body, source)
    assert first.assertions_by_id[aid].metadata is not second.assertions_by_id[aid].metadata


@pytest.mark.parametrize(
    "variant", ["subject", "target", "evidence", "alias", "duplicate", "contract"]
)
def test_source_with_valid_proof_still_requires_contract_and_structure(variant):
    payload = _payload()
    if variant == "subject":
        payload["assertions"][0]["subject_entity_id"] = "ent:missing"
    elif variant == "target":
        payload["assertions"][0]["value"] = {"kind": "entity_ref", "entity_id": "ent:missing"}
    elif variant == "evidence":
        payload["assertions"][0]["metadata"]["evidence_ref_ids"] = ["ev:missing"]
    elif variant == "alias":
        payload["aliases"][0]["entity_id"] = "ent:missing"
    elif variant == "duplicate":
        payload["assertions"].append(payload["assertions"][0].copy())
    else:
        payload["assertions"][0]["metadata"]["standing"] = "invalid"
    source = _source(payload)
    with pytest.raises(PersistenceIntegrityError):
        decode_read_artifact(encode_source_wire(source), source)


def test_concurrent_decoding_has_no_global_function_substitution():
    source = _source(_payload())
    body = encode_source_wire(source)
    reference = _parsed(source, source.graph_payload)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: decode_read_artifact(body, source), range(20)))
    assert all(result == reference for result in results)


def test_digest_uses_actual_literal_not_a_supplied_canonical_text():
    parsed = _parsed(_source(_payload()), _payload())
    aid = next(aid for aid, a in parsed.assertions_by_id.items() if a.value.kind == "literal")
    args = list(_digest_arguments(parsed))
    original = args[2][aid]
    args[2][aid] = replace(original, value=replace(original.value, canonical_json_text='"forged"'))
    assert _stream_semantic_digest(*args) == compute_semantic_digest(*args)


def test_manifest_fallback_and_malformed_header():
    source = _source(_payload())
    packet = _packet(source)
    packet["parsed_format"] = "future"
    assert decode_read_artifact(_bytes(packet), source) is None
    packet.pop("parsed_format")
    with pytest.raises(PersistenceIntegrityError):
        decode_read_artifact(_bytes(packet), source)
