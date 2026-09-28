from __future__ import annotations

import pytest
from benchmarks.vnext_scale_characterization import (
    _digest,
    _measure_tiny_delta,
    _tiny_delta_state,
)
from benchmarks.vnext_scale_fixtures import make_payload
from benchmarks.vnext_scale_validate import BASE_OPERATIONS, REQUIRED_CORE, SHAPES, SIZES, validate


def _valid_document() -> dict:
    matrix = []
    for shape in SHAPES:
        for size in SIZES:
            for operation in BASE_OPERATIONS:
                matrix.append({
                        "shape": shape,
                        "size": size,
                        "operation": operation,
                        "adapter": "memory",
                        "api_family": (
                            "native_vnext"
                            if operation == "tiny_delta_publication"
                            else "classic_v6_world_graph"
                        ),
                        "disposition": "measured",
                        "input_sha256": "a" * 64,
                        "result_sha256": "b" * 64,
                        "samples_seconds": [0.001],
                        "median_seconds": 0.001,
                        "peak_tracemalloc_bytes": 1,
                    })
                matrix.append({
                    "shape": shape,
                    "size": size,
                    "operation": operation,
                    "adapter": "postgresql",
                    "api_family": "inactive_postgresql",
                    "disposition": "not_measured",
                    "reason": "No PostgreSQL target authorized by PR #91 activation.",
                })
    return {
        "schema": "dungeonmind.vnext-scale-characterization.v1",
        "matrix": matrix,
        "acceptance_status": "ACCEPTED",
        "postgresql": {
            "activated": False,
            "disposition": "not_measured",
            "reason": "No PostgreSQL target authorized by PR #91 activation.",
        },
    }


@pytest.mark.parametrize("shape", SHAPES)
def test_fixture_contract_has_independently_predictable_counts_and_ids(shape: str) -> None:
    payload, params = make_payload(shape=shape, size=100)
    repeated, repeated_params = make_payload(shape=shape, size=100)
    assert _digest(repeated) == _digest(payload)
    assert repeated_params == params
    assert params["shape"] == shape
    assert len(payload["objects"]) == 100
    assert len(payload["relationships"]) == 150
    assert len(payload["evidence_refs"]) == 250
    assert payload["objects"][0]["object_id"] == "obj:000000"
    assert payload["objects"][-1]["label"] == "Hold 00099"
    if shape == "rules_like":
        assert all(
            len(rel["assertion_metadata"]["evidence_ref_ids"]) == 2
            for rel in payload["relationships"]
        )


def test_tiny_delta_publication_measures_repeated_governed_children() -> None:
    state = _tiny_delta_state(shape="world_like", size=100)
    measured = _measure_tiny_delta(state, "a" * 64, repeats=2)

    assert measured["input_sha256"] == "a" * 64
    assert len(measured["samples_seconds"]) == 2
    assert len(measured["publication_receipt_sha256_samples"]) == 3
    assert measured["parent_entity_counts_before_samples"] == [100, 101]
    assert measured["memory_sample_parent_entity_count"] == 102
    assert measured["delta_entities_per_sample"] == 1
    assert measured["peak_tracemalloc_bytes"] > 0


def test_validator_accepts_complete_matrix() -> None:
    validate(_valid_document())


def test_validator_rejects_missing_and_duplicate_cells() -> None:
    doc = _valid_document()
    doc["matrix"].pop()
    with pytest.raises(ValueError, match="missing matrix cells"):
        validate(doc)
    doc = _valid_document()
    doc["matrix"].append(dict(doc["matrix"][0]))
    with pytest.raises(ValueError, match="duplicate matrix cells"):
        validate(doc)


def test_validator_rejects_malformed_digest_and_silent_disposition() -> None:
    doc = _valid_document()
    doc["matrix"][0]["result_sha256"] = "not-a-digest"
    with pytest.raises(ValueError, match="malformed result_sha256"):
        validate(doc)


def test_validator_rejects_missing_postgresql_cells_and_invalid_samples() -> None:
    doc = _valid_document()
    doc["matrix"] = [row for row in doc["matrix"] if row["adapter"] != "postgresql"]
    with pytest.raises(ValueError, match="missing matrix cells"):
        validate(doc)
    doc = _valid_document()
    doc["matrix"][0]["samples_seconds"] = [-1]
    with pytest.raises(ValueError, match="finite nonnegative"):
        validate(doc)
    doc = _valid_document()
    doc["acceptance_status"] = "MAYBE"
    with pytest.raises(ValueError, match="unknown acceptance status"):
        validate(doc)
    doc = _valid_document()
    doc["matrix"][0]["disposition"] = "not_measured"
    with pytest.raises(ValueError, match="must state reason"):
        validate(doc)


def test_validator_requires_accepted_large_scale_core_operations() -> None:
    doc = _valid_document()
    for row in doc["matrix"]:
        if (
                row["shape"] == "world_like"
                and row["size"] == 100_000
                and row["adapter"] == "memory"
                and row["operation"] in REQUIRED_CORE
        ):
            row["disposition"] = "resource_limited"
            row["reason"] = "Recorded bounded resource result."
    validate(doc)
    doc["matrix"][0]["samples_seconds"] = [-1]
    with pytest.raises(ValueError, match="finite nonnegative"):
        validate(doc)
