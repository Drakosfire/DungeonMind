"""Optional acceleration must preserve exact pins and fresh source authority."""

from dataclasses import replace
from datetime import datetime

import pytest

from dungeonmind.application.vnext import native_source_access as access
from dungeonmind.application.vnext._source_wire import encode_source_wire
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError
from tests.unit.test_vnext_native_source_metadata import source_case
from tests.unit.test_vnext_source_wire import _payload, _source


def test_memory_key_snapshots_mutable_envelope_and_equal_instant_offset():
    stored = _source(_payload())
    cache = access.NativeParsedRevisionCache()
    first = cache.parse(stored)
    # Mutate the very model the old key retained. The absolute instant is equal.
    stored.revision.created_at = datetime.fromisoformat("2026-09-15T13:00:00+01:00")
    second = cache.parse(stored)
    assert first.created_at == second.created_at
    assert first.created_at.isoformat() != second.created_at.isoformat()
    assert first is not second
    stored.revision.operation_ids.append("op:new")
    assert cache.parse(stored).operation_ids[-1] == "op:new"


def test_source_corruption_cannot_hide_behind_a_memory_hit():
    stored = _source(_payload())
    cache = access.NativeParsedRevisionCache()
    cache.parse(stored)
    corrupt = replace(
        stored, _payload_json=stored._payload_json.replace('approved":true', 'approved":false')
    )
    with pytest.raises(PersistenceIntegrityError):
        cache.parse(corrupt)


def _open_args():
    repo, domain, _, original, receipt = source_case()
    stored = repo.get_revision(original.space_id, original.revision_id)
    body = encode_source_wire(stored)
    args = dict(
        repository=repo,
        space_id=original.space_id,
        revision_id=original.revision_id,
        domain_contract=domain,
        parsed_cache=access.NativeParsedRevisionCache(),
    )
    return repo, args, body, receipt


def test_artifact_memory_hit_reverifies_revision_and_refreshes_withdrawal(monkeypatch):
    repo, args, body, receipt = _open_args()
    reads = []
    revisions = []
    get = repo.get_revision

    def revision(*arguments):
        revisions.append(arguments)
        return get(*arguments)

    def artifact(stored):
        reads.append(stored.revision.revision_id)
        return body

    monkeypatch.setattr(repo, "get_revision", revision)
    monkeypatch.setattr(repo, "get_native_read_artifact", artifact, raising=False)
    first = access.open_native_text_source_access_context(**args)
    evidence = receipt.bindings[0].evidence_ref_id
    assert access.open_admitted_native_text(first, evidence).status == "available"
    repo.withdraw_native_source(
        space_id=receipt.space_id,
        source_artifact_id=receipt.source_artifact_id,
        source_revision_id=receipt.source_revision_id,
    )
    second = access.open_native_text_source_access_context(**args)
    assert second.parsed is first.parsed
    assert access.open_admitted_native_text(second, evidence).status == "unavailable"
    assert len(reads) == 1 and len(revisions) == 2


def test_absent_or_unsupported_stored_artifact_falls_back(monkeypatch):
    blob = None
    repo, args, _, _ = _open_args()
    monkeypatch.setattr(repo, "get_native_read_artifact", lambda stored: blob, raising=False)
    context = access.open_native_text_source_access_context(**args)
    assert context.parsed == access._parse_revision(
        repo.get_revision(args["space_id"], args["revision_id"])
    )


def test_corrupt_artifact_does_not_publish_memory_entry(monkeypatch):
    repo, args, body, _ = _open_args()
    monkeypatch.setattr(repo, "get_native_read_artifact", lambda stored: b"{", raising=False)
    with pytest.raises(PersistenceIntegrityError):
        access.open_native_text_source_access_context(**args)
    assert args["parsed_cache"]._entry is None
    monkeypatch.setattr(repo, "get_native_read_artifact", lambda stored: body)
    assert access.open_native_text_source_access_context(**args).parsed


def test_optional_reader_storage_failure_is_not_fallback(monkeypatch):
    repo, args, _, _ = _open_args()

    def offline(stored):
        raise PersistenceUnavailableError("offline")

    monkeypatch.setattr(repo, "get_native_read_artifact", offline, raising=False)
    with pytest.raises(PersistenceUnavailableError):
        access.open_native_text_source_access_context(**args)


def test_current_reader_body_with_future_format_is_integrity_failure(monkeypatch):
    repo, args, _, _ = _open_args()
    monkeypatch.setattr(
        repo, "get_native_read_artifact", lambda stored: b'{"format":"future"}', raising=False
    )
    with pytest.raises(PersistenceIntegrityError, match="format mismatch"):
        access.open_native_text_source_access_context(**args)


@pytest.mark.parametrize("body", [object(), [], bytearray(b"bad")])
def test_optional_reader_rejects_non_bytes_as_integrity_failure(monkeypatch, body):
    repo, args, _, _ = _open_args()
    monkeypatch.setattr(repo, "get_native_read_artifact", lambda stored: body, raising=False)
    with pytest.raises(PersistenceIntegrityError, match="non-byte"):
        access.open_native_text_source_access_context(**args)
