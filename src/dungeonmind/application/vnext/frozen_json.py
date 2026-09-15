"""Recursively immutable JSON data structures and utilities for vNext parsed models.

Ensures that caller-owned or nested mutable JSON structures (dictionaries, lists)
cannot mutate, poison, or leak state into or out of `ParsedKnowledgeRevision`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import Any, TypeVar

KT = TypeVar("KT")
VT = TypeVar("VT")


class FrozenDict(Mapping[KT, VT]):
    """An immutable, hashable mapping implementation with deterministic iteration order.

    Backing data is copied on initialization and cannot be modified after construction.
    All mutation methods (e.g. ``__setitem__``, ``__delitem__``, ``update``, ``clear``)
    raise ``TypeError`` or ``AttributeError``.
    """

    __slots__ = ("_data", "_hash")

    def __init__(
        self,
        mapping_or_iterable: (
            Mapping[KT, VT]
            | list[tuple[KT, VT]]
            | tuple[tuple[KT, VT], ...]
            | None
        ) = None,
    ) -> None:
        if mapping_or_iterable is None:
            self._data: dict[KT, VT] = {}
        elif isinstance(mapping_or_iterable, Mapping):
            # Sort keys for deterministic iteration order
            sorted_items = sorted(mapping_or_iterable.items(), key=lambda kv: str(kv[0]))
            self._data = dict(sorted_items)
        else:
            sorted_items = sorted(mapping_or_iterable, key=lambda kv: str(kv[0]))
            self._data = dict(sorted_items)
        self._hash: int | None = None

    def __getitem__(self, key: KT) -> VT:
        return self._data[key]

    def __iter__(self) -> Iterator[KT]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return dict(self._data) == dict(other)
        return False

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash(tuple(self._data.items()))
        return self._hash

    def __repr__(self) -> str:
        return f"FrozenDict({self._data!r})"

    def __setitem__(self, key: KT, value: VT) -> None:
        raise TypeError(f"'{self.__class__.__name__}' object does not support item assignment")

    def __delitem__(self, key: KT) -> None:
        raise TypeError(f"'{self.__class__.__name__}' object does not support item deletion")

    def to_dict(self) -> dict[KT, Any]:
        """Convert recursively back to mutable python dictionaries and lists."""
        return thaw_json_value(self)


FrozenJsonValue = (
    None
    | bool
    | int
    | float
    | str
    | tuple["FrozenJsonValue", ...]
    | FrozenDict[str, "FrozenJsonValue"]
)


def freeze_json_value(val: Any) -> FrozenJsonValue:
    """Recursively freeze arbitrary JSON payloads into immutable structures."""
    if val is None or isinstance(val, (bool, int, float, str)):
        return val
    if isinstance(val, Mapping):
        return FrozenDict({str(k): freeze_json_value(v) for k, v in val.items()})
    if isinstance(val, (list, tuple, set, frozenset)):
        return tuple(freeze_json_value(item) for item in val)
    if hasattr(val, "model_dump"):
        return freeze_json_value(val.model_dump(mode="json"))
    raise TypeError(f"Cannot freeze non-JSON value of type {type(val)}: {val!r}")


def thaw_json_value(val: Any) -> Any:
    """Recursively convert FrozenDict and tuple structures back to dict and list."""
    if isinstance(val, FrozenDict):
        return {str(k): thaw_json_value(v) for k, v in val.items()}
    if isinstance(val, tuple):
        return [thaw_json_value(item) for item in val]
    return val


def canonical_json_text(val: Any) -> str:
    """Produce deterministic canonical JSON text (sorted keys, compact separators)."""
    thawed = thaw_json_value(val)
    return json.dumps(thawed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_json_bytes(val: Any) -> bytes:
    """Produce deterministic canonical JSON bytes (UTF-8 encoded)."""
    return canonical_json_text(val).encode("utf-8")
