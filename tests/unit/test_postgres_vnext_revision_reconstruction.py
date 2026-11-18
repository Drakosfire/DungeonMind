"""Stored-row integrity and bounded reconstruction work for native reads."""

from copy import deepcopy
from importlib import import_module

import pytest

from dungeonmind.application.vnext.authority import revision_from_command
from dungeonmind.domain.canonical import canonical_json, canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from tests.unit.test_vnext_cas_publication import genesis_command

pytest.importorskip("psycopg")
vnext_knowledge = import_module("dungeonmind.infrastructure.postgres.vnext_knowledge")


def _row(payload=None):
    command = genesis_command(origin=None, payload=payload)
    revision = revision_from_command(command)
    payload = deepcopy(command.graph_payload)
    row = revision.model_dump(mode="python")
    row.update(
        revision_payload=revision.model_dump(mode="json"),
        graph_payload=payload,
        record_fingerprint=canonical_sha256({
            "graph_payload": payload,
            "revision": revision.model_dump(mode="json"),
        }),
    )
    return row, revision, payload


def test_reconstruction_reuses_canonical_payload_without_publication_validation(monkeypatch):
    row, revision, payload = _row()

    def forbidden(*args, **kwargs):
        pytest.fail("a stored read must not validate a new publication command")

    monkeypatch.setattr(vnext_knowledge, "PublishKnowledgeRevisionCommand", forbidden)
    stored = vnext_knowledge._reconstruct(row)

    assert stored.revision == revision
    assert stored.graph_payload == payload
    assert stored._payload_json == canonical_json(payload)
    assert stored.graph_payload_sha256 == canonical_sha256(payload)


@pytest.mark.parametrize("field", [
    "space_id", "revision_id", "parent_revision_id", "graph_schema",
    "graph_payload_sha256", "schema_version", "created_at", "record_fingerprint",
])
def test_reconstruction_rejects_column_drift(field):
    row, _, _ = _row()
    row[field] = "tampered"
    with pytest.raises(PersistenceIntegrityError):
        vnext_knowledge._reconstruct(row)


def test_reconstruction_rejects_payload_drift_even_with_updated_record_fingerprint():
    row, revision, _ = _row()
    row["graph_payload"]["entities"] = []
    row["record_fingerprint"] = canonical_sha256({
        "graph_payload": row["graph_payload"],
        "revision": revision.model_dump(mode="json"),
    })
    with pytest.raises(PersistenceIntegrityError, match="payload hash mismatch"):
        vnext_knowledge._reconstruct(row)


def test_reconstruction_rejects_revision_identity_drift_with_updated_fingerprint():
    row, _, _ = _row()
    row["revision_id"] = "rev:forged"
    row["revision_payload"]["revision_id"] = row["revision_id"]
    row["record_fingerprint"] = canonical_sha256({
        "graph_payload": row["graph_payload"],
        "revision": row["revision_payload"],
    })
    with pytest.raises(PersistenceIntegrityError, match="recomputed native revision id"):
        vnext_knowledge._reconstruct(row)


@pytest.mark.parametrize("payload", [
    {"value": None},
    {"value": [True, False, 1, 1.0, 0.0, -0.0]},
    {"value": [1e-20, 1e20, 1.2345678901234567]},
    {"Ω": "雪\n\u2028", "a": {"z": [], "b": {}}},
    {"value": '","revision":{"space_id":"forged"}'},
    {"value": [{"nested": {"b": 2, "a": 1}}, "é", "😀"]},
])
def test_streamed_record_fingerprint_matches_canonical_wrapper(payload):
    row, revision, expected_payload = _row(payload)
    # _row uses the unchanged canonical_sha256 wrapper used by persisted rows.
    stored = vnext_knowledge._reconstruct(row)
    assert stored.revision == revision
    assert stored._payload_json == canonical_json(expected_payload)
    assert stored.graph_payload_sha256 == canonical_sha256(expected_payload)


def test_reconstruction_serializes_the_graph_only_once(monkeypatch):
    canonical = import_module("dungeonmind.domain.canonical")
    row, _, _ = _row()
    serialize = canonical.canonical_json
    graph_passes = []

    def counted(value):
        if value is row["graph_payload"] or (
            isinstance(value, dict) and value.get("graph_payload") is row["graph_payload"]
        ):
            graph_passes.append(value)
        return serialize(value)

    monkeypatch.setattr(canonical, "canonical_json", counted)
    monkeypatch.setattr(vnext_knowledge, "canonical_json", counted)
    vnext_knowledge._reconstruct(row)
    assert len(graph_passes) == 1
