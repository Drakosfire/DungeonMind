"""Bulk native decoding keeps the existing contract-validation boundary."""

from copy import deepcopy

import pytest

from dungeonmind.application.vnext.errors import GovernedMaterializationIntegrityError
from dungeonmind.application.vnext.materialization import decode_native_graph_payload
from dungeonmind.contracts.vnext.domain import Assertion, Entity
from dungeonmind.contracts.vnext.knowledge import IdentityAlias
from dungeonmind.contracts.vnext.source import EvidenceRefV3
from tests.unit.test_vnext_parsed_knowledge_revision import (
    _make_sample_aliases,
    _make_sample_assertions,
    _make_sample_entities,
    _make_sample_evidence,
)

CONTRACTS = {
    "entities": Entity, "assertions": Assertion,
    "aliases": IdentityAlias, "evidence": EvidenceRefV3,
}


def _payload():
    return {
        key: [item.model_dump(mode="json") for item in items]
        for key, items in (
            ("entities", _make_sample_entities()),
            ("assertions", _make_sample_assertions()),
            ("aliases", _make_sample_aliases()),
            ("evidence", _make_sample_evidence()),
        )
    }


def test_bulk_decoding_matches_individual_contract_validation():
    payload = _payload()
    decoded = decode_native_graph_payload(payload)
    for key, contract in CONTRACTS.items():
        assert getattr(decoded, key) == tuple(
            contract.model_validate(row) for row in payload[key]
        )


def test_bulk_decoding_removes_per_record_model_validate_dispatch(monkeypatch):
    payload = _payload()

    def forbidden(*args, **kwargs):
        pytest.fail("decode must use compiled list validation")

    for contract in CONTRACTS.values():
        monkeypatch.setattr(contract, "model_validate", forbidden)
    decoded = decode_native_graph_payload(payload)
    assert len(decoded.assertions) == len(payload["assertions"])


@pytest.mark.parametrize("key", CONTRACTS)
def test_bulk_decoding_rejects_unknown_record_fields(key):
    payload = _payload()
    payload[key][0]["unexpected"] = True
    with pytest.raises(GovernedMaterializationIntegrityError) as caught:
        decode_native_graph_payload(payload)
    assert caught.value.details["reason"] == "native_payload_decode"


@pytest.mark.parametrize(
    "mutation", ["duplicate_evidence", "invalid_visibility", "missing_subject"]
)
def test_bulk_decoding_preserves_nested_assertion_constraints(mutation):
    payload = _payload()
    assertion = payload["assertions"][0]
    if mutation == "duplicate_evidence":
        evidence = assertion["metadata"]["evidence_ref_ids"][0]
        assertion["metadata"]["evidence_ref_ids"] = [evidence, evidence]
    elif mutation == "invalid_visibility":
        assertion["metadata"]["visibility"] = {"kind": "unexpected"}
    else:
        del assertion["subject_entity_id"]
    with pytest.raises(GovernedMaterializationIntegrityError) as caught:
        decode_native_graph_payload(payload)
    assert caught.value.details["reason"] == "native_payload_decode"


def test_bulk_decoding_keeps_separate_mutable_contract_metadata():
    payload = _payload()
    second = deepcopy(payload["assertions"][0])
    second["assertion_id"] = "asrt:second"
    payload["assertions"] = [payload["assertions"][0], second]
    decoded = decode_native_graph_payload(payload)
    decoded.assertions[0].metadata.domain_metadata[0].payload["approved"] = False
    assert decoded.assertions[1].metadata.domain_metadata[0].payload["approved"] is True
