"""Immutable factory differential and removed-work regression checks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from unittest.mock import patch

import pytest

from dungeonmind.application.vnext import _read_artifact as artifact_module
from dungeonmind.application.vnext import builder, model
from dungeonmind.application.vnext._read_artifact import (
    decode_read_artifact,
    parse_verified_source_rows,
)
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
    assert parse_verified_source_rows(source, source.graph_payload) == ordinary
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


def test_source_proof_finishes_before_index_construction():
    source = _source(_payload())
    packet = _packet(source)
    reference = packet["entities"][0]
    text = packet["strings"][reference]
    packet["strings"][reference] = text[:-1] + ("x" if text[-1] != "x" else "y")
    with (
        patch.object(artifact_module, "_build_parsed_knowledge_revision_from_records") as build,
        pytest.raises(PersistenceIntegrityError, match="reconstructed source"),
    ):
        decode_read_artifact(_bytes(packet), source)
    build.assert_not_called()


@pytest.mark.parametrize(
    "order", [list(range(40)), [0, 1, 0, 2, 1, 3, 2, 3], [3, 2, 3, 1, 2, 0, 1, 0]]
)
def test_validation_models_release_at_last_use_without_revalidation(order, monkeypatch):
    import weakref

    from dungeonmind.domain.canonical import canonical_json

    payload = _payload()
    template = payload["assertions"][0]
    payload["assertions"] = []
    for index, value in enumerate(order):
        row = dict(template, assertion_id=f"assertion:{index}")
        row["value"] = {"kind": "literal", "value": {"number": value}}
        row["metadata"] = {
            **template["metadata"],
            "domain_metadata": [{"schema": "test:pool", "payload": value}],
        }
        payload["assertions"].append(row)
    source = _source(payload)
    body = encode_source_wire(source)
    expected = _parsed(source, payload)
    value_refs = {}
    metadata_refs = {}
    value_validation = artifact_module._VALUE_ADAPTER.validate_python
    metadata_validation = artifact_module.AssertionMetadata.model_validate
    assertion_validation = artifact_module.Assertion.model_validate
    build = artifact_module._build_parsed_knowledge_revision_from_records
    seen = 0

    def validate_value(raw):
        key = canonical_json(raw)
        assert key not in value_refs, "each distinct source value validates once"
        validated = value_validation(raw)
        value_refs[key] = weakref.ref(validated)
        return validated

    def validate_metadata(raw):
        key = canonical_json(raw)
        assert key not in metadata_refs, "each distinct metadata chunk validates once"
        validated = metadata_validation(raw)
        metadata_refs[key] = weakref.ref(validated)
        return validated

    def validate_assertion(raw):
        nonlocal seen
        # At the next row, every previously final-used public model is already
        # gone. No gc.collect or heap/timing threshold is needed to prove this.
        remaining = payload["assertions"][seen:]
        for key, ref in value_refs.items():
            assert (ref() is not None) == any(canonical_json(r["value"]) == key for r in remaining)
        for key, ref in metadata_refs.items():
            assert (ref() is not None) == any(
                canonical_json(r["metadata"]) == key for r in remaining
            )
        seen += 1
        return assertion_validation(raw)

    def build_after_release(*args, **kwargs):
        assert seen == len(order)
        assert len(value_refs) == len(set(order))
        assert len(metadata_refs) == len(set(order))
        assert all(ref() is None for ref in [*value_refs.values(), *metadata_refs.values()])
        return build(*args, **kwargs)

    monkeypatch.setattr(artifact_module._VALUE_ADAPTER, "validate_python", validate_value)
    monkeypatch.setattr(artifact_module.AssertionMetadata, "model_validate", validate_metadata)
    monkeypatch.setattr(artifact_module.Assertion, "model_validate", validate_assertion)
    monkeypatch.setattr(
        artifact_module, "_build_parsed_knowledge_revision_from_records", build_after_release
    )
    parsed = decode_read_artifact(body, source)
    assert parsed == expected
    assert parsed.semantic_digest == compute_semantic_digest(*_digest_arguments(expected))
    for left, row in enumerate(payload["assertions"]):
        for right, other in enumerate(payload["assertions"]):
            if row["value"] == other["value"]:
                first = parsed.assertions_by_id[f"assertion:{left}"]
                second = parsed.assertions_by_id[f"assertion:{right}"]
                assert first.value is second.value
                assert first.metadata is second.metadata


@pytest.mark.parametrize("column", [3, 4])
@pytest.mark.parametrize("reference", [True, -1, 999999, "0", None, 0.0])
def test_lifetime_prepass_rejects_malformed_references_before_indexes(column, reference):
    source = _source(_payload())
    packet = _packet(source)
    packet["assertions"][-1][column] = reference
    with (
        patch.object(artifact_module, "_build_parsed_knowledge_revision_from_records") as build,
        pytest.raises(PersistenceIntegrityError, match="invalid wire reference"),
    ):
        decode_read_artifact(_bytes(packet), source)
    build.assert_not_called()



def test_alias_search_reuses_existing_artifact_without_eager_index_work(monkeypatch):
    from dataclasses import asdict

    from dungeonmind.application.vnext import alias_search as reads
    from dungeonmind.application.vnext import alias_search_index as indexes
    from dungeonmind.application.vnext.materialization import encode_native_graph_payload
    from dungeonmind.application.vnext.neighborhood import NeighborhoodReadService
    from dungeonmind.application.vnext.provenance import InMemoryKnowledgeSourceReader
    from dungeonmind.application.vnext.read_context import KnowledgeReadContext
    from dungeonmind.application.vnext.records import StoredKnowledgeRevision
    from dungeonmind.contracts.vnext.domain import Entity
    from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
    from dungeonmind.domain.canonical import canonical_sha256
    from tests.unit.test_vnext_alias_search import alias, context

    item = alias("alias:artifact", "Cobalt keeper")
    template, _ = context([item], evidence=[], artifacts={}, revisions={})
    payload = encode_native_graph_payload(
        entities={"ent:one": Entity(entity_id="ent:one")},
        assertions={},
        aliases={item.alias_id: item},
        evidence={},
    )
    header = asdict(template.parsed.identity)
    header["graph_payload_sha256"] = canonical_sha256(payload)
    source = StoredKnowledgeRevision.seal(KnowledgeRevision.model_validate(header), payload)
    wire = encode_source_wire(source)

    def forbidden(*args, **kwargs):
        pytest.fail("ordinary/artifact preparation eagerly built alias-search index")

    with monkeypatch.context() as guard:
        guard.setattr(indexes, "_build_alias_search_index", forbidden)
        guard.setattr(reads, "_build_alias_search_index", forbidden)
        decoded = decode_read_artifact(wire, source)
        ordinary = _parsed(source, payload)
        assert decoded is not None
        prepared = KnowledgeReadContext(
            parsed=decoded, request=template.request,
            domain_contract=template.domain_contract, semantic_profile=template.semantic_profile,
            domain_policy=template.domain_policy, source_reader=InMemoryKnowledgeSourceReader(),
        )
        neighborhood = NeighborhoodReadService().get_neighborhood(prepared, ["ent:one"])
        assert neighborhood.found_seed_entity_ids == ("ent:one",)
    assert decoded is not None and decoded == ordinary
    assert decoded.compatibility_key == ordinary.compatibility_key
    assert decoded.semantic_digest == ordinary.semantic_digest
    assert decoded.format_version == ordinary.format_version == model.PARSED_REVISION_FORMAT_VERSION
    structural = indexes.AliasSearchIndexCache(max_entries=1, max_postings=10_000)

    def read(parsed):
        ctx = KnowledgeReadContext(
            parsed=parsed,
            request=template.request,
            domain_contract=template.domain_contract,
            semantic_profile=template.semantic_profile,
            domain_policy=template.domain_policy,
            source_reader=InMemoryKnowledgeSourceReader(),
        )
        return reads.AliasSearchReadService().search_aliases(ctx, "cobalt", index_cache=structural)

    with reads._capture_alias_search_trace() as traces:
        from_ordinary, from_artifact = read(ordinary), read(decoded)
    assert from_ordinary == from_artifact and from_artifact.hits[0].alias.alias_id == item.alias_id
    assert not traces[0].index_cache_hit and traces[1].index_cache_hit
    assert encode_source_wire(source) == wire
