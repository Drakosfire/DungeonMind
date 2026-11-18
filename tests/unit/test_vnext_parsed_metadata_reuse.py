"""Immutable metadata reuse preserves parsed content and input isolation."""

from copy import deepcopy
from dataclasses import replace

import pytest

from dungeonmind.application.vnext import builder
from dungeonmind.application.vnext.model import compute_semantic_digest
from tests.unit.test_vnext_parsed_knowledge_revision import (
    _build_standard_parsed,
    _make_base_revision,
    _make_sample_assertions,
    _make_sample_entities,
    _make_sample_evidence,
)


def _build(assertions):
    return builder.build_parsed_knowledge_revision(
        _make_base_revision(), entities=_make_sample_entities(),
        evidence=_make_sample_evidence(), assertions=assertions,
    )


def _copies(count=20):
    original = _make_sample_assertions()[0]
    return [
        original.model_copy(deep=True, update={"assertion_id": f"asrt:copy-{i:03}"})
        for i in range(count)
    ]


def test_equal_metadata_is_built_once_and_shared_as_immutable_records(monkeypatch):
    assertions = _copies()
    calls = []
    constructor = builder.ParsedAssertionMetadata

    def counted(**kwargs):
        calls.append(kwargs)
        return constructor(**kwargs)

    monkeypatch.setattr(builder, "ParsedAssertionMetadata", counted)
    parsed = _build(assertions)
    assert len(calls) == 1
    records = tuple(parsed.assertions_by_id.values())
    assert all(row.metadata is records[0].metadata for row in records)
    assert len(parsed.get_subject_assertions("ent:alice")) == len(assertions)

    assertions[0].metadata.domain_metadata[0].payload["approved"] = False
    assert records[0].metadata.domain_metadata[0].payload["approved"] is True
    with pytest.raises(TypeError):
        records[0].metadata.domain_metadata[0].payload["approved"] = False


def test_changed_metadata_does_not_reuse_previous_visibility_or_evidence():
    assertions = _copies(3)
    assertions[1].metadata = _make_sample_assertions()[1].metadata.model_copy(deep=True)
    parsed = _build(assertions)
    rows = tuple(parsed.assertions_by_id.values())
    assert rows[0].metadata != rows[1].metadata
    assert rows[0].metadata == rows[2].metadata
    assert rows[1].metadata.evidence_ref_ids == ("ev:doc-2",)


def test_cache_key_snapshots_mutable_contract_metadata():
    original = _make_sample_assertions()[0]

    class MutatingAssertions(list):
        def __iter__(self):
            yield original.model_copy(update={"assertion_id": "asrt:first"})
            original.metadata.domain_metadata[0].payload["approved"] = False
            yield original.model_copy(update={"assertion_id": "asrt:second"})

    parsed = _build(MutatingAssertions())
    assert parsed.assertions_by_id["asrt:first"].metadata.domain_metadata[0].payload[
        "approved"
    ] is True
    assert parsed.assertions_by_id["asrt:second"].metadata.domain_metadata[0].payload[
        "approved"
    ] is False


def test_shared_and_separately_allocated_metadata_have_the_same_semantic_digest():
    parsed = _build(_copies())
    separate = {
        key: replace(row, metadata=deepcopy(row.metadata))
        for key, row in parsed.assertions_by_id.items()
    }
    assert compute_semantic_digest(
        parsed.identity, dict(parsed.entities_by_id), separate,
        dict(parsed.aliases_by_id), dict(parsed.evidence_by_id),
    ) == parsed.semantic_digest


def test_full_variant_fixture_keeps_parent_implementation_digest():
    assert _build_standard_parsed().semantic_digest == (
        "fccb1c53dd917a73b3925d4a76917de221d1bd5d9f3d9198135b474299728786"
    )
