"""Explicitly owned immutable proof reuse; never a source/admission authority."""

from __future__ import annotations

import json
from dataclasses import dataclass
from threading import Lock

from ...application.vnext.records import StoredKnowledgeRevision
from ...contracts.vnext.knowledge import KnowledgeRevision
from ...domain.canonical import canonical_json
from ...domain.errors import PersistenceIntegrityError

_SourceKey = tuple[str | None, ...]


@dataclass(frozen=True, slots=True)
class _Proof:
    envelope: str
    payload: str
    payload_sha256: str

    def restore(self) -> StoredKnowledgeRevision:
        try:
            revision = KnowledgeRevision.model_validate(json.loads(self.envelope))
        except Exception as exc:
            raise PersistenceIntegrityError(
                f"failed to reconstruct KnowledgeRevision: {exc}"
            ) from exc
        return StoredKnowledgeRevision(revision, self.payload_sha256, self.payload)


class VerifiedKnowledgeRevisionCache:
    """One exact-source proof with a required retained UTF-8 content byte budget.

    Inject explicitly into readers; no default global instance. Internal methods
    accept only repository-owned full row keys and successfully verified records.
    Database reads and verification happen outside the cache lock.
    """

    def __init__(self, *, max_bytes: int) -> None:
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("verification cache max_bytes must be a positive integer")
        self._max_bytes = max_bytes
        self._lock = Lock()
        self._generation = 0
        self._entry: tuple[_SourceKey, _Proof, int] | None = None

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    @property
    def retained_bytes(self) -> int:
        with self._lock:
            return 0 if self._entry is None else self._entry[2]

    def clear(self) -> None:
        with self._lock:
            self._generation += 1
            self._entry = None

    def _lookup(self, key: _SourceKey) -> tuple[_Proof | None, int]:
        with self._lock:
            proof = self._entry[1] if self._entry is not None and self._entry[0] == key else None
            return proof, self._generation

    def _store(self, key: _SourceKey, stored: StoredKnowledgeRevision, generation: int) -> None:
        proof = _Proof(
            canonical_json(stored.revision.model_dump(mode="json")),
            stored._payload_json,
            stored.graph_payload_sha256,
        )
        # Count both retained raw and canonical content, including scalar/version
        # strings. This is a content budget, not a claim about total Python RSS.
        size = sum(len(item.encode("utf-8")) for item in key if item is not None)
        size += sum(
            len(item.encode("utf-8"))
            for item in (
                proof.envelope,
                proof.payload,
                proof.payload_sha256,
            )
        )
        if size > self.max_bytes:
            return
        with self._lock:
            if generation == self._generation:
                self._entry = (key, proof, size)
