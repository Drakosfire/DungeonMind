"""In-memory native knowledge authority with the same CAS rules as PostgreSQL."""

from __future__ import annotations

import threading
from collections.abc import Callable

from dungeonmind.contracts.vnext.knowledge import KnowledgeHead, PublishKnowledgeRevisionCommand

from ...application.vnext.authority import commit_expected_parent, verify_stored_revision
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

    def __init__(self, *, after_revision_insert: Callable[[], None] | None = None) -> None:
        self._lock = threading.RLock()
        self._revisions: dict[tuple[str, str], StoredKnowledgeRevision] = {}
        self._heads: dict[str, KnowledgeHead] = {}
        self._events: list[KnowledgeHeadEvent] = []
        self._after_revision_insert = after_revision_insert

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
