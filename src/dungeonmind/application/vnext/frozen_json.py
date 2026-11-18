"""Recursively immutable JSON data structures and utilities for vNext parsed models.

Ensures that caller-owned or nested mutable JSON structures (dictionaries, lists)
cannot mutate, poison, or leak state into or out of `ParsedKnowledgeRevision`.
"""

from __future__ import annotations

import json
from collections.abc import Collection, ItemsView, Iterator, KeysView, Mapping, ValuesView
from types import MappingProxyType
from typing import Any, TypeVar, overload

KT = TypeVar("KT")
VT = TypeVar("VT")
T = TypeVar("T")


class FrozenDict(Mapping[KT, VT]):
    """An immutable, hashable mapping implementation with deterministic iteration order.

    Backing data is copied on initialization into an immutable tuple representation
    and exposed via a privately owned, read-only mapping proxy. There is no reachable
    mutable backing dictionary or attribute slot.

    All mutation methods and attribute assignments raise ``TypeError``.
    """

    __slots__ = ("_hash", "_hash_ready", "_items", "_proxy")

    _hash: int | None
    _hash_ready: bool

    def __init__(
        self,
        mapping_or_iterable: (
            Mapping[KT, VT] | list[tuple[KT, VT]] | tuple[tuple[KT, VT], ...] | None
        ) = None,
    ) -> None:
        if mapping_or_iterable is None:
            sorted_pairs: tuple[tuple[KT, VT], ...] = ()
            items_dict: dict[KT, VT] = {}
        elif isinstance(mapping_or_iterable, Mapping):
            sorted_list = sorted(mapping_or_iterable.items(), key=lambda kv: str(kv[0]))
            sorted_pairs = tuple(sorted_list)
            items_dict = dict(sorted_list)
        else:
            sorted_list = sorted(mapping_or_iterable, key=lambda kv: str(kv[0]))
            sorted_pairs = tuple(sorted_list)
            items_dict = dict(sorted_list)

        object.__setattr__(self, "_proxy", MappingProxyType(items_dict))
        object.__setattr__(self, "_items", sorted_pairs)
        try:
            computed_hash = hash(sorted_pairs)
        except TypeError:
            computed_hash = None
        object.__setattr__(self, "_hash", computed_hash)
        object.__setattr__(self, "_hash_ready", True)

    def __getitem__(self, key: KT) -> VT:
        return self._proxy[key]

    def __iter__(self) -> Iterator[KT]:
        return iter(self._proxy)

    def __len__(self) -> int:
        return len(self._proxy)

    def __contains__(self, key: object) -> bool:
        return key in self._proxy

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return dict(self._proxy) == dict(other)
        return False

    def __hash__(self) -> int:
        if not self._hash_ready:
            try:
                computed_hash = hash(self._items)
            except TypeError:
                computed_hash = None
            # Only a private optimization cache changes; mapping data stays
            # immutable. Concurrent computations produce the same result.
            object.__setattr__(self, "_hash", computed_hash)
            object.__setattr__(self, "_hash_ready", True)
        if self._hash is None:
            raise TypeError(
                f"unhashable type: '{self.__class__.__name__}' (contains unhashable values)"
            )
        return self._hash

    def __repr__(self) -> str:
        return f"FrozenDict({dict(self._proxy)!r})"

    def __setitem__(self, key: KT, value: VT) -> None:
        raise TypeError(f"'{self.__class__.__name__}' object does not support item assignment")

    def __delitem__(self, key: KT) -> None:
        raise TypeError(f"'{self.__class__.__name__}' object does not support item deletion")

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError(f"'{self.__class__.__name__}' attributes are immutable")

    def __delattr__(self, name: str) -> None:
        raise TypeError(f"'{self.__class__.__name__}' attributes are immutable")

    @overload
    def get(self, key: KT) -> VT | None: ...

    @overload
    def get(self, key: KT, default: VT) -> VT: ...

    @overload
    def get(self, key: KT, default: T) -> VT | T: ...

    def get(self, key: KT, default: Any = None) -> Any:
        return self._proxy.get(key, default)

    def keys(self) -> KeysView[KT]:
        return self._proxy.keys()

    def values(self) -> ValuesView[VT]:
        return self._proxy.values()

    def items(self) -> ItemsView[KT, VT]:
        return self._proxy.items()

    def __reduce__(self) -> tuple[type, tuple[tuple[tuple[KT, VT], ...]]]:
        return (self.__class__, (self._items,))

    def __copy__(self) -> FrozenDict[KT, VT]:
        return self

    def __deepcopy__(self, memo: dict[Any, Any]) -> FrozenDict[KT, VT]:
        return self

    def to_dict(self) -> dict[KT, Any]:
        """Convert recursively back to mutable python dictionaries and lists."""
        return thaw_json_value(self)


def _deferred_frozen_dict(mapping: Mapping[KT, VT]) -> FrozenDict[KT, VT]:
    """Freeze owner-validated immutable records without unrequested hashing.

    This private path copies the same sorted items/proxy as the public Mapping
    constructor. It is not for caller-owned mutable payloads. Public construction
    remains eager; copy/pickle/equality and requested hash semantics are unchanged.
    """
    sorted_items = sorted(mapping.items(), key=lambda item: str(item[0]))
    result: FrozenDict[KT, VT] = object.__new__(FrozenDict)
    object.__setattr__(result, "_proxy", MappingProxyType(dict(sorted_items)))
    object.__setattr__(result, "_items", tuple(sorted_items))
    object.__setattr__(result, "_hash", None)
    object.__setattr__(result, "_hash_ready", False)
    return result


def _frozen_dense_index(
    empty_items: tuple[tuple[str, tuple[str, ...]], ...],
    memberships: Mapping[str, Collection[str]],
) -> FrozenDict[str, tuple[str, ...]]:
    """Freeze owner-validated index buckets over a complete sorted key domain.

    The builder validates references first and supplies one immutable empty pair
    per primary key, sorted by the public constructor's str(key) ordering. Reuse
    those pairs without exposing mutable buckets or changing dense index values.
    Public FrozenDict construction remains unchanged; index hashes remain eager.
    """
    if memberships:
        pairs: list[tuple[str, tuple[str, ...]]] = []
        for empty in empty_items:
            values = memberships.get(empty[0])
            pairs.append((empty[0], tuple(sorted(values))) if values else empty)
        items = tuple(pairs)
    else:
        items = empty_items
    items_dict = dict(items)
    if not memberships.keys() <= items_dict.keys():
        raise ValueError("index membership outside primary key domain")
    result: FrozenDict[str, tuple[str, ...]] = object.__new__(FrozenDict)
    object.__setattr__(result, "_proxy", MappingProxyType(items_dict))
    object.__setattr__(result, "_items", items)
    try:
        computed_hash = hash(items)
    except TypeError:
        computed_hash = None
    object.__setattr__(result, "_hash", computed_hash)
    object.__setattr__(result, "_hash_ready", True)
    return result


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
