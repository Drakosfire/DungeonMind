"""Bounded reuse of parsed immutable World Graph revisions (R.3a).

Graph revisions are content-addressed and never mutate. Successfully parsed
snapshots are therefore safe to reuse across reads of the same
``(parse_compatibility_id, world_id, revision_id)``.

The compatibility id binds a cached parse to the exact ``GraphSnapshotReader``
/ semantic-profile registry that produced it. A parse that passed profile
verification under one registry must not be served to a reader that would
fail closed on the same payload.

This cache is service-local, memory-bounded, and never a process-global
semantic singleton. Head movement cannot mutate a cached historical parse: a
new head is a different revision id. Parse failures are not stored, so one
bad payload cannot poison unrelated revisions.

Returned snapshots are isolated copies. Mutating a caller's objects,
relationships, evidence, or indexes cannot poison the cached revision.

Scoped/authorized projections are not stored here. Those consult live source
state and must not be keyed by revision identity alone.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable

from .graph_snapshot import ParsedGraphSnapshot

DEFAULT_PARSED_REVISION_CACHE_MAX_ENTRIES = 8

_ParsedRevisionKey = tuple[str, str, str]


def graph_reader_parse_compatibility_id(reader: object) -> str:
    """Identity that must match for a cached parse to be reused."""

    value = getattr(reader, "parse_compatibility_id", None)
    if callable(value):
        value = value()
    if isinstance(value, str) and value:
        return value
    return f"{type(reader).__module__}.{type(reader).__qualname__}:{id(reader)}"


def isolate_parsed_graph(snapshot: ParsedGraphSnapshot) -> ParsedGraphSnapshot:
    """Deep-copy a parsed snapshot so callers cannot mutate cached state."""

    profile_ref = snapshot.semantic_profile_ref
    profile_descriptor = snapshot.semantic_profile_descriptor
    return ParsedGraphSnapshot(
        world_id=snapshot.world_id,
        graph_schema=snapshot.graph_schema,
        objects={
            object_id: obj.model_copy(deep=True)
            for object_id, obj in snapshot.objects.items()
        },
        relationships={
            relationship_id: rel.model_copy(deep=True)
            for relationship_id, rel in snapshot.relationships.items()
        },
        evidence={
            evidence_id: record.model_copy(deep=True)
            for evidence_id, record in snapshot.evidence.items()
        },
        label_index={key: list(ids) for key, ids in snapshot.label_index.items()},
        alias_index={key: list(ids) for key, ids in snapshot.alias_index.items()},
        semantic_profile_ref=(
            None if profile_ref is None else profile_ref.model_copy(deep=True)
        ),
        semantic_profile_descriptor=(
            None
            if profile_descriptor is None
            else profile_descriptor.model_copy(deep=True)
        ),
    )


class ParsedImmutableRevisionCache:
    """LRU cache of successfully parsed immutable graph revisions.

    Entries are keyed by parse-compatibility identity plus revision identity.
    Sharing one cache object across incompatible readers cannot bypass
    profile verification: those readers occupy different key namespaces.
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

    def get(
        self,
        world_id: str,
        revision_id: str,
        *,
        compatibility_id: str,
    ) -> ParsedGraphSnapshot | None:
        key = (compatibility_id, world_id, revision_id)
        with self._lock:
            parsed = self._entries.get(key)
            if parsed is None:
                return None
            self._entries.move_to_end(key)
            stored = parsed
        return isolate_parsed_graph(stored)

    def put(
        self,
        world_id: str,
        revision_id: str,
        parsed: ParsedGraphSnapshot,
        *,
        compatibility_id: str,
    ) -> None:
        key = (compatibility_id, world_id, revision_id)
        isolated = isolate_parsed_graph(parsed)
        with self._lock:
            self._entries[key] = isolated
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def get_or_load(
        self,
        world_id: str,
        revision_id: str,
        loader: Callable[[], ParsedGraphSnapshot],
        *,
        compatibility_id: str,
    ) -> tuple[ParsedGraphSnapshot, bool]:
        """Return ``(parsed, cache_hit)``. Failures from ``loader`` are not cached."""

        key = (compatibility_id, world_id, revision_id)
        with self._lock:
            parsed = self._entries.get(key)
            if parsed is not None:
                self._entries.move_to_end(key)
                self._hits += 1
                stored = parsed
                hit = True
            else:
                self._misses += 1
                stored = None
                hit = False
        if hit:
            assert stored is not None
            return isolate_parsed_graph(stored), True
        loaded = isolate_parsed_graph(loader())
        with self._lock:
            self._entries[key] = loaded
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
        return isolate_parsed_graph(loaded), False


__all__ = [
    "DEFAULT_PARSED_REVISION_CACHE_MAX_ENTRIES",
    "ParsedImmutableRevisionCache",
    "graph_reader_parse_compatibility_id",
    "isolate_parsed_graph",
]
