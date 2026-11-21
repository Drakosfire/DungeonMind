"""Bounded process-local cache of exact immutable projection facts."""

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from threading import Lock
from typing import TypeAlias

from dungeonmind.application.vnext.records import (
    ParsedAssertion,
    ParsedEntity,
    ParsedEvidenceRef,
    ParsedIdentityAlias,
)

Fact: TypeAlias = ParsedAssertion | ParsedEntity | ParsedEvidenceRef | ParsedIdentityAlias
_CacheKey: TypeAlias = tuple[str, str, str, str, str]


@dataclass(frozen=True, slots=True)
class _Entry:
    fact: Fact
    wire_bytes: int


class SelectiveFactCache:
    """Reuse only facts decoded after verification against their current exact seals.

    The caller still owns revision and activation verification on each open.
    The wire budget counts UTF-8 record representations. Python overhead is separate.
    This cache never stores a source view, admission result, or absence decision.
    """

    def __init__(self, *, max_records: int = 16384, max_wire_bytes: int = 24 * 1024 * 1024) -> None:
        if type(max_records) is not int or max_records < 1:
            raise ValueError("max_records must be a positive integer")
        if type(max_wire_bytes) is not int or max_wire_bytes < 1:
            raise ValueError("max_wire_bytes must be a positive integer")
        self._max_records = max_records
        self._max_wire_bytes = max_wire_bytes
        self._entries: OrderedDict[_CacheKey, _Entry] = OrderedDict()
        self._wire_bytes = 0
        self._lock = Lock()

    def _read(
        self,
        pin: tuple[str, str],
        family: str,
        identifiers: Sequence[str],
        seals: Mapping[str, str],
    ) -> dict[str, Fact]:
        found = {}
        with self._lock:
            for identifier in identifiers:
                seal = seals.get(identifier)
                if seal is None:
                    continue
                key = (*pin, family, identifier, seal)
                entry = self._entries.get(key)
                if entry is not None:
                    self._entries.move_to_end(key)
                    found[identifier] = entry.fact
        return found

    def _remember(
        self,
        pin: tuple[str, str],
        family: str,
        verified: Mapping[str, tuple[Fact, int]],
        seals: Mapping[str, str],
    ) -> None:
        with self._lock:
            for identifier, (fact, wire_bytes) in verified.items():
                if wire_bytes > self._max_wire_bytes:
                    continue
                key = (*pin, family, identifier, seals[identifier])
                previous = self._entries.pop(key, None)
                if previous is not None:
                    self._wire_bytes -= previous.wire_bytes
                self._entries[key] = _Entry(fact, wire_bytes)
                self._wire_bytes += wire_bytes
                while (
                    len(self._entries) > self._max_records
                    or self._wire_bytes > self._max_wire_bytes
                ):
                    _, old = self._entries.popitem(last=False)
                    self._wire_bytes -= old.wire_bytes
