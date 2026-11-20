"""Exact current-row proof reuse through the public repository boundary."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta, timezone
from importlib import import_module
from unittest.mock import patch

import pytest

from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError

pytest.importorskip("psycopg")
k = import_module("dungeonmind.infrastructure.postgres.vnext_knowledge")
native = import_module("dungeonmind.infrastructure.postgres.vnext_sources")
_row = import_module("tests.unit.test_postgres_vnext_revision_reconstruction")._row


class Database:
    def __init__(self):
        self.row, _, _ = _row()
        self.reads = 0
        self.graph_text = None
        self.error = None

    @contextmanager
    def transaction(self):
        yield self

    def execute(self, query, params):
        self.reads += 1
        if self.error:
            raise self.error
        row = deepcopy(self.row)
        if row is not None and "::text" in query.as_string():
            row["graph_payload"] = self.graph_text or json.dumps(row["graph_payload"])
            row["revision_payload"] = json.dumps(row["revision_payload"])
        return type("Result", (), {"fetchone": lambda _: row})()


def repo(db, cache):
    return k.PostgresKnowledgeRevisionRepository(db, verification_cache=cache)


def read(reader, db):
    row = db.row
    return reader.get_revision(row["space_id"], row["revision_id"])


def test_fresh_source_every_read_but_full_proof_once_across_repository_instances():
    db = Database()
    cache = k.VerifiedKnowledgeRevisionCache(max_bytes=1_000_000)
    original = k._reconstruct
    with patch.object(k, "_reconstruct", wraps=original) as reconstruct:
        first = read(repo(db, cache), db)
        second = read(repo(db, cache), db)
        third = read(repo(db, cache), db)
        assert reconstruct.call_count == 1
    assert db.reads == 3
    assert first == second == third
    assert first is not second and first.revision is not second.revision
    assert first.revision.domain_contract_ref is not second.revision.domain_contract_ref
    assert 0 < cache.retained_bytes <= cache.max_bytes


def test_default_path_is_uncached_and_native_repository_forwards_injection():
    db = Database()
    with patch.object(k, "_reconstruct", wraps=k._reconstruct) as reconstruct:
        for _ in range(2):
            read(repo(db, None), db)
        assert reconstruct.call_count == 2
    cache = k.VerifiedKnowledgeRevisionCache(max_bytes=1_000_000)
    with patch.object(k, "_reconstruct", wraps=k._reconstruct) as reconstruct:
        for _ in range(2):
            read(native.PostgresNativeSourceEvidenceRepository(db, verification_cache=cache), db)
        assert reconstruct.call_count == 1


@pytest.mark.parametrize("field", list(k._KEY_FIELDS))
def test_changed_source_field_cannot_hide_behind_proof(field):
    db = Database()
    cache = k.VerifiedKnowledgeRevisionCache(max_bytes=1_000_000)
    reader = repo(db, cache)
    first = read(reader, db)
    previous = deepcopy(db.row)
    if field in ("graph_payload", "revision_payload"):
        db.row[field]["forged"] = True
    elif field == "created_at":
        db.row[field] += timedelta(seconds=1)
    else:
        db.row[field] = "tampered"
    # Compare to unchanged ordinary reconstruction's typed failure.
    with pytest.raises(PersistenceIntegrityError) as expected:
        k._reconstruct(db.row)
    with pytest.raises(PersistenceIntegrityError) as actual:
        reader.get_revision(previous["space_id"], previous["revision_id"])
    assert str(actual.value) == str(expected.value)
    db.row = previous
    assert read(reader, db) == first  # Failed loads preserved the last good proof.


def test_exact_text_and_namespace_changes_force_full_proof():
    db = Database()
    cache = k.VerifiedKnowledgeRevisionCache(max_bytes=1_000_000)
    with patch.object(k, "_reconstruct", wraps=k._reconstruct) as reconstruct:
        read(repo(db, cache), db)
        db.graph_text = json.dumps(db.row["graph_payload"], indent=4)
        read(repo(db, cache), db)
        with patch.object(k, "_VERIFIER_VERSION", "incompatible-verifier"):
            read(repo(db, cache), db)
        assert reconstruct.call_count == 3


def test_offset_spelling_is_not_equal_instant_key_equality():
    db = Database()
    cache = k.VerifiedKnowledgeRevisionCache(max_bytes=1_000_000)
    with patch.object(k, "_reconstruct", wraps=k._reconstruct) as reconstruct:
        first = read(repo(db, cache), db)
        shifted = first.revision.created_at.astimezone(timezone(timedelta(hours=1)))
        db.row["revision_payload"]["created_at"] = shifted.isoformat()
        db.row["record_fingerprint"] = canonical_sha256(
            {
                "graph_payload": db.row["graph_payload"],
                "revision": db.row["revision_payload"],
            }
        )
        second = read(repo(db, cache), db)
        assert first.revision.created_at == second.revision.created_at
        assert first.revision.created_at.isoformat() != second.revision.created_at.isoformat()
        assert reconstruct.call_count == 2


def test_caller_model_mutation_and_missing_or_unavailable_source():
    db = Database()
    cache = k.VerifiedKnowledgeRevisionCache(max_bytes=1_000_000)
    reader = repo(db, cache)
    first = read(reader, db)
    expected = deepcopy(first)
    first.revision.domain_contract_ref.domain_id = "poison"
    assert read(reader, db) == expected
    saved = db.row
    db.row = None
    assert reader.get_revision(expected.revision.space_id, expected.revision.revision_id) is None
    db.row = saved
    db.error = PersistenceUnavailableError("source unavailable")
    with pytest.raises(PersistenceUnavailableError):
        read(reader, db)


@pytest.mark.parametrize("limit", [0, -1, True, 1.0])
def test_invalid_byte_budget_is_rejected(limit):
    with pytest.raises(ValueError):
        k.VerifiedKnowledgeRevisionCache(max_bytes=limit)


def test_byte_bypass_clear_and_stale_generation_cannot_repopulate():
    db = Database()
    cache = k.VerifiedKnowledgeRevisionCache(max_bytes=1)
    with patch.object(k, "_reconstruct", wraps=k._reconstruct) as reconstruct:
        read(repo(db, cache), db)
        read(repo(db, cache), db)
        assert reconstruct.call_count == 2 and cache.retained_bytes == 0
    cache = k.VerifiedKnowledgeRevisionCache(max_bytes=1_000_000)
    stored = read(repo(db, cache), db)
    key, proof, size = cache._entry
    assert size == sum(len(s.encode("utf-8")) for s in key if s is not None) + sum(
        len(s.encode("utf-8")) for s in (proof.envelope, proof.payload, proof.payload_sha256)
    )
    _, generation = cache._lookup(key)
    cache.clear()
    cache._store(key, stored, generation)
    assert cache.retained_bytes == 0
    assert cache._lookup(key)[0] is None


def test_concurrent_reads_return_fresh_models_with_complete_source_reads():
    db = Database()
    cache = k.VerifiedKnowledgeRevisionCache(max_bytes=1_000_000)
    expected = read(repo(db, cache), db)
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda _: read(repo(db, cache), db), range(32)))
    assert db.reads == 33
    assert all(value == expected for value in values)
    assert len({id(value.revision.domain_contract_ref) for value in values}) == len(values)


def test_deep_payload_returns_to_original_read_path():
    db = Database()
    payload = 1
    for _ in range(80):
        payload = [payload]
    db.row, _, _ = _row({"opaque": payload})
    cache = k.VerifiedKnowledgeRevisionCache(max_bytes=1_000_000)
    expected = k._reconstruct(db.row)
    with patch.object(k, "_read_revision", wraps=k._read_revision) as ordinary:
        assert read(repo(db, cache), db) == expected
        ordinary.assert_called_once()
    assert db.reads == 2 and cache.retained_bytes == 0


def test_equal_instant_scalar_timestamp_and_numeric_types_force_reverification():
    db = Database()
    cache = k.VerifiedKnowledgeRevisionCache(max_bytes=1_000_000)
    with patch.object(k, "_reconstruct", wraps=k._reconstruct) as reconstruct:
        read(repo(db, cache), db)
        db.row["created_at"] = db.row["created_at"].astimezone(timezone(timedelta(hours=1)))
        read(repo(db, cache), db)
        for value in (True, 1, 1.0):
            db.row, _, _ = _row({"value": value})
            read(repo(db, cache), db)
        assert reconstruct.call_count == 5


def test_ordinary_and_deep_bypass_preserve_reconstruction_stack_depth():
    import inspect

    db = Database()
    nested = 1
    for _ in range(80):
        nested = [nested]
    db.row, _, _ = _row({"opaque": nested})
    depths = []
    parents = []
    original = k._reconstruct

    def counted(row):
        stack = inspect.stack()
        depths.append(len(stack))
        parents.append(stack[1].function)
        return original(row)

    with patch.object(k, "_reconstruct", counted):
        read(repo(db, None), db)
        read(repo(db, k.VerifiedKnowledgeRevisionCache(max_bytes=1_000_000)), db)
    assert depths[0] == depths[1]
    assert parents == ["_read_revision", "_read_revision"]


@pytest.mark.parametrize("replacement", [1, 1.0])
def test_python_equal_json_numbers_do_not_reuse_prior_proof(replacement):
    db = Database()
    db.row, _, _ = _row({"value": True})
    cache = k.VerifiedKnowledgeRevisionCache(max_bytes=1_000_000)
    reader = repo(db, cache)
    read(reader, db)
    db.row["graph_payload"] = {"value": replacement}
    # Python equality conflates these; exact current source representation must not.
    assert db.row["graph_payload"] == {"value": True}
    with pytest.raises(PersistenceIntegrityError, match="record_fingerprint drift"):
        read(reader, db)
