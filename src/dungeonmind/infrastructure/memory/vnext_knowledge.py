"""In-memory native knowledge authority with the same CAS rules as PostgreSQL."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence

from dungeonmind.contracts.vnext.knowledge import KnowledgeHead, PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.prospective import (
    KnowledgeProspectivePublication,
    KnowledgeProspectivePublicationResult,
    ProspectiveResultBinding,
)
from dungeonmind.contracts.vnext.publication import KnowledgePublicationReceipt
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

from ...application.vnext.authority import commit_expected_parent, verify_stored_revision
from ...application.vnext.errors import KnowledgePublicationIdempotencyConflictError
from ...application.vnext.records import KnowledgeHeadEvent, StoredKnowledgeRevision


def _detached(stored: StoredKnowledgeRevision) -> StoredKnowledgeRevision:
    """Return a revision the caller cannot use to mutate stored authority."""
    return StoredKnowledgeRevision(
        revision=stored.revision.model_copy(deep=True),
        graph_payload_sha256=stored.graph_payload_sha256,
        _payload_json=stored._payload_json,
    )


class InMemoryKnowledgeRevisionRepository:
    """One lock covers the atomic publication. Failed calls leave prior authority."""

    def __init__(
        self,
        *,
        after_revision_insert: Callable[[], None] | None = None,
        after_publication_commit: Callable[[], None] | None = None,
        after_prospective_result_insert: Callable[[], None] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._revisions: dict[tuple[str, str], StoredKnowledgeRevision] = {}
        self._heads: dict[str, KnowledgeHead] = {}
        self._events: list[KnowledgeHeadEvent] = []
        self._receipts: dict[tuple[str, str], KnowledgePublicationReceipt] = {}
        self._prospective_results: dict[
            tuple[str, str], KnowledgeProspectivePublicationResult
        ] = {}
        self._prospective_fingerprints: dict[tuple[str, str], str] = {}
        self._after_revision_insert = after_revision_insert
        self._after_publication_commit = after_publication_commit
        self._after_prospective_result_insert = after_prospective_result_insert

    def get_head(self, space_id: str) -> KnowledgeHead | None:
        with self._lock:
            head = self._heads.get(space_id)
            return None if head is None else head.model_copy(deep=True)

    def get_revision(self, space_id: str, revision_id: str) -> StoredKnowledgeRevision | None:
        with self._lock:
            stored = self._revisions.get((space_id, revision_id))
            if stored is None:
                return None
            verify_stored_revision(stored)
            return _detached(stored)

    def head_events(self, space_id: str) -> tuple[KnowledgeHeadEvent, ...]:
        with self._lock:
            return tuple(event for event in self._events if event.space_id == space_id)

    def publish_revision(self, command: PublishKnowledgeRevisionCommand) -> StoredKnowledgeRevision:
        with self._lock:
            inserted: list[tuple[str, str]] = []
            heads_before = dict(self._heads)
            events_before = len(self._events)

            def insert_revision(stored: StoredKnowledgeRevision) -> None:
                key = (stored.revision.space_id, stored.revision.revision_id)
                self._revisions[key] = stored
                inserted.append(key)
                if self._after_revision_insert is not None:
                    self._after_revision_insert()

            def advance_head(head: KnowledgeHead, event: KnowledgeHeadEvent) -> None:
                self._heads[head.space_id] = head
                self._events.append(event)

            try:
                stored = commit_expected_parent(
                    command,
                    read_head=lambda: self._heads.get(command.space_id),
                    read_revision=lambda revision_id: self._revisions.get(
                        (command.space_id, revision_id)
                    ),
                    insert_revision=insert_revision,
                    advance_head=advance_head,
                )
            except Exception:
                for key in inserted:
                    self._revisions.pop(key, None)
                self._heads.clear()
                self._heads.update(heads_before)
                del self._events[events_before:]
                raise
            return _detached(stored)

    def get_publication_receipt(
        self, space_id: str, publication_id: str
    ) -> KnowledgePublicationReceipt | None:
        with self._lock:
            receipt = self._receipts.get((space_id, publication_id))
            return None if receipt is None else receipt.model_copy(deep=True)

    def publish_publication(
        self, command: PublishKnowledgeRevisionCommand, publication_id: str
    ) -> KnowledgePublicationReceipt:
        command_sha = canonical_sha256(command.model_dump(mode="json"))
        with self._lock:
            key = (command.space_id, publication_id)
            existing = self._receipts.get(key)
            if existing is not None:
                if existing.command_sha256 != command_sha:
                    raise KnowledgePublicationIdempotencyConflictError(
                        space_id=command.space_id, publication_id=publication_id
                    )
                return existing.model_copy(deep=True)
            inserted: list[tuple[str, str]] = []
            heads_before = dict(self._heads)
            events_before = len(self._events)

            def insert_revision(value: StoredKnowledgeRevision) -> None:
                self._revisions[(value.revision.space_id, value.revision.revision_id)] = value
                inserted.append((value.revision.space_id, value.revision.revision_id))
                if self._after_revision_insert is not None:
                    self._after_revision_insert()

            def advance_head(head: KnowledgeHead, event: KnowledgeHeadEvent) -> None:
                self._heads[head.space_id] = head
                self._events.append(event)

            try:
                stored = commit_expected_parent(
                    command,
                    read_head=lambda: self._heads.get(command.space_id),
                    read_revision=lambda revision_id: self._revisions.get(
                        (command.space_id, revision_id)
                    ),
                    insert_revision=insert_revision,
                    advance_head=advance_head,
                )
                receipt = KnowledgePublicationReceipt(
                    space_id=command.space_id,
                    publication_id=publication_id,
                    command_sha256=command_sha,
                    expected_parent_revision_id=command.expected_parent_revision_id,
                    published_revision_id=stored.revision.revision_id,
                    graph_payload_sha256=stored.graph_payload_sha256,
                )
                self._receipts[key] = receipt
            except Exception:
                for revision_key in inserted:
                    self._revisions.pop(revision_key, None)
                self._heads.clear()
                self._heads.update(heads_before)
                del self._events[events_before:]
                raise
            if self._after_publication_commit is not None:
                self._after_publication_commit()
            return receipt.model_copy(deep=True)

    def get_prospective_publication(
        self, space_id: str, publication_id: str
    ) -> KnowledgeProspectivePublication | None:
        with self._lock:
            key = (space_id, publication_id)
            receipt = self._receipts.get(key)
            result = self._prospective_results.get(key)
            fingerprint = self._prospective_fingerprints.get(key)
            if result is not None and receipt is None:
                raise PersistenceIntegrityError("prospective result exists without receipt")
            if result is not None and (
                fingerprint is None
                or canonical_sha256(result.model_dump(mode="json")) != fingerprint
            ):
                raise PersistenceIntegrityError("prospective result fingerprint drift")
            if result is None and fingerprint is not None:
                raise PersistenceIntegrityError("prospective result fingerprint without result")
            if receipt is not None and result is None:
                raise KnowledgePublicationIdempotencyConflictError(
                    space_id=space_id, publication_id=publication_id
                )
            if result is None:
                return None
            assert receipt is not None
            return KnowledgeProspectivePublication(
                publication_receipt=receipt,
                prospective_result=result,
            ).model_copy(deep=True)

    def publish_prospective_publication(
        self,
        command: PublishKnowledgeRevisionCommand,
        publication_id: str,
        prospective_request_sha256: str,
        result_bindings: Sequence[ProspectiveResultBinding],
    ) -> KnowledgeProspectivePublication:
        command_sha = canonical_sha256(command.model_dump(mode="json"))
        key = (command.space_id, publication_id)
        with self._lock:
            existing_receipt = self._receipts.get(key)
            existing_result = self._prospective_results.get(key)
            existing_fingerprint = self._prospective_fingerprints.get(key)
            if existing_result is not None and existing_receipt is None:
                raise PersistenceIntegrityError("prospective result exists without receipt")
            if existing_result is not None and (
                existing_fingerprint is None
                or canonical_sha256(existing_result.model_dump(mode="json"))
                != existing_fingerprint
            ):
                raise PersistenceIntegrityError("prospective result fingerprint drift")
            if existing_receipt is not None:
                if (
                    existing_result is None
                    or existing_receipt.command_sha256 != command_sha
                    or existing_result.prospective_request_sha256
                    != prospective_request_sha256
                ):
                    raise KnowledgePublicationIdempotencyConflictError(
                        space_id=command.space_id, publication_id=publication_id
                    )
                return KnowledgeProspectivePublication(
                    publication_receipt=existing_receipt,
                    prospective_result=existing_result,
                ).model_copy(deep=True)

            inserted: list[tuple[str, str]] = []
            heads_before = dict(self._heads)
            events_before = len(self._events)

            def insert_revision(value: StoredKnowledgeRevision) -> None:
                revision_key = (value.revision.space_id, value.revision.revision_id)
                self._revisions[revision_key] = value
                inserted.append(revision_key)
                if self._after_revision_insert is not None:
                    self._after_revision_insert()

            def advance_head(head: KnowledgeHead, event: KnowledgeHeadEvent) -> None:
                self._heads[head.space_id] = head
                self._events.append(event)

            try:
                stored = commit_expected_parent(
                    command,
                    read_head=lambda: self._heads.get(command.space_id),
                    read_revision=lambda revision_id: self._revisions.get(
                        (command.space_id, revision_id)
                    ),
                    insert_revision=insert_revision,
                    advance_head=advance_head,
                )
                receipt = KnowledgePublicationReceipt(
                    space_id=command.space_id,
                    publication_id=publication_id,
                    command_sha256=command_sha,
                    expected_parent_revision_id=command.expected_parent_revision_id,
                    published_revision_id=stored.revision.revision_id,
                    graph_payload_sha256=stored.graph_payload_sha256,
                )
                result = KnowledgeProspectivePublicationResult(
                    space_id=command.space_id,
                    publication_id=publication_id,
                    prospective_request_sha256=prospective_request_sha256,
                    published_revision_id=stored.revision.revision_id,
                    results=list(result_bindings),
                )
                self._receipts[key] = receipt
                self._prospective_results[key] = result
                self._prospective_fingerprints[key] = canonical_sha256(
                    result.model_dump(mode="json")
                )
                if self._after_prospective_result_insert is not None:
                    self._after_prospective_result_insert()
            except Exception:
                for revision_key in inserted:
                    self._revisions.pop(revision_key, None)
                self._heads.clear()
                self._heads.update(heads_before)
                del self._events[events_before:]
                self._receipts.pop(key, None)
                self._prospective_results.pop(key, None)
                self._prospective_fingerprints.pop(key, None)
                raise
            if self._after_publication_commit is not None:
                self._after_publication_commit()
            return KnowledgeProspectivePublication(
                publication_receipt=receipt,
                prospective_result=result,
            ).model_copy(deep=True)
