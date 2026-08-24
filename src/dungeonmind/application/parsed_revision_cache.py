"""Bounded reuse of parsed immutable World Graph revisions (R.3a).

Graph revisions are content-addressed and never mutate. Successfully parsed
snapshots are therefore safe to reuse across reads of the same
``(world_id, revision_id)`` through one ``GraphSnapshotReader``.

This cache is service-local, memory-bounded, and never a process-global
semantic singleton. Head movement cannot mutate a cached historical parse: a
new head is a different revision id. Parse failures are not stored, so one
bad payload cannot poison unrelated revisions.

Scoped/authorized projections are not stored here. Those consult live source
state and must not be keyed by revision identity alone.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable

from .graph_snapshot import ParsedGraphSnapshot

DEFAULT_PARSED_REVISION_CACHE_MAX_ENTRIES = 8

_ParsedRevisionKey = tuple[str, str]


class ParsedImmutableRevisionCache:
    """LRU cache of successfully parsed immutable graph revisions.

    Bound to one projection service / configured graph reader. Not safe to
    share across readers with different profile registries.
    """

    def __init__(self, *, max_entries: int = DEFAULT_PARSED_REVISION_CACHE_MAX_ENTRIES) -> None:
        if max_entries < 1:
            raise ValueError("parsed revision cache max_entries must be >= 1")
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._entries: OrderedDict[_ParsedRevisionKey, ParsedGraphSnapshot] = OrderedDict()
        self._hits = 0
        self._misses = 0

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    @property
    def hits(self) -> int:
        with self._lock:
            return self._hits

    @property
    def misses(self) -> int:
        with self._lock:
            return self._misses

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def get(self, world_id: str, revision_id: str) -> ParsedGraphSnapshot | None:
        key = (world_id, revision_id)
        with self._lock:
            parsed = self._entries.get(key)
            if parsed is None:
                return None
            self._entries.move_to_end(key)
            return parsed

    def put(self, world_id: str, revision_id: str, parsed: ParsedGraphSnapshot) -> None:
        key = (world_id, revision_id)
        with self._lock:
            self._entries[key] = parsed
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def get_or_load(
        self,
        world_id: str,
        revision_id: str,
        loader: Callable[[], ParsedGraphSnapshot],
    ) -> tuple[ParsedGraphSnapshot, bool]:
        """Return ``(parsed, cache_hit)``. Failures from ``loader`` are not cached."""

        key = (world_id, revision_id)
        with self._lock:
            parsed = self._entries.get(key)
            if parsed is not None:
                self._entries.move_to_end(key)
                self._hits += 1
                return parsed, True
            self._misses += 1
        parsed = loader()
        self.put(world_id, revision_id, parsed)
        return parsed, False


__all__ = [
    "DEFAULT_PARSED_REVISION_CACHE_MAX_ENTRIES",
    "ParsedImmutableRevisionCache",
]
