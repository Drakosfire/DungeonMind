"""Stored-row integrity and bounded reconstruction work for native reads."""

from copy import deepcopy

import pytest

from dungeonmind.application.vnext.authority import revision_from_command
from dungeonmind.domain.canonical import canonical_json, canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres import vnext_knowledge
from tests.unit.test_vnext_cas_publication import genesis_command


def _row():
    command = genesis_command(origin=None)
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
