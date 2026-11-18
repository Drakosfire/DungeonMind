"""Private, lossless primary-wire codec for derived native read artifacts.

Callers must retrieve and verify the source revision normally first. This module
proves source equivalence; it neither supplies parsed indexes nor caches admission.
Unsupported source shapes produce no artifact. Malformed supported artifacts fail
closed, including when an attacker recomputes a separate blob checksum.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterator
from json.encoder import encode_basestring
from typing import Any

from dungeonmind.domain.canonical import canonical_json, canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

from .records import StoredKnowledgeRevision

_FORMAT = "dm_native_source_wire_v1"
_FIELDS = frozenset(
    {
        "format",
        "envelope_sha256",
        "graph_sha256",
        "strings",
        "metadata",
        "entities",
        "assertions",
        "aliases",
        "evidence",
    }
)
_ROOT_FIELDS = frozenset({"entities", "assertions", "aliases", "evidence"})
_ENTITY_FIELDS = frozenset({"entity_id", "schema_version"})
_ASSERTION_FIELDS = frozenset(
    {
        "assertion_id",
        "subject_entity_id",
        "predicate",
        "schema_version",
        "value",
        "metadata",
    }
)
_MAX_CHUNK_DEPTH = 64


class UnsupportedSourceWire(ValueError):
    """The ordinary source parser remains authoritative for this representation."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("nonfinite JSON number")
    return value


def _constant(text: str) -> Any:
    raise ValueError(f"nonfinite JSON constant {text}")


def _depth(text: str, limit: int) -> None:
    """Bound nesting before json.loads allocates nested Python containers."""
    depth = 0
    quoted = False
    escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > limit:
                raise ValueError("JSON nesting limit exceeded")
        elif char in "]}":
            depth -= 1
    # Syntax completeness, matching bracket types and control characters are
    # checked by json.loads, after this allocation bound has been established.


def _load(text: str, depth: int) -> Any:
    _depth(text, depth)
    return json.loads(text, object_pairs_hook=_pairs, parse_float=_float, parse_constant=_constant)


def _text(value: Any) -> bytes:
    if type(value) is not str:
        raise ValueError("wire string required")
    return encode_basestring(value).encode("utf-8")


def _chunk(value: Any) -> Any:
    if type(value) is not str:
        raise ValueError("wire JSON chunk required")
    parsed = _load(value, _MAX_CHUNK_DEPTH)
    if canonical_json(parsed) != value:
        raise ValueError("noncanonical JSON chunk")
    return parsed


def _reference(table: list[Any], index: Any, used: set[int]) -> Any:
    if type(index) is not int or not 0 <= index < len(table):
        raise ValueError("invalid wire reference")
    used.add(index)
    return table[index]


def _rows(packet: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """One expansion feeds both the source proof and the returned source facts."""
    strings = packet["strings"]
    metadata = packet["metadata"]
    used_strings: set[int] = set()
    used_metadata: set[int] = set()
    for key in ("aliases", "assertions", "entities", "evidence"):
        for row in packet[key]:
            if key in ("aliases", "evidence"):
                expanded = _chunk(row)
                if type(expanded) is not dict:
                    raise ValueError("wire record must be an object")
            elif key == "entities":
                expanded = {
                    "entity_id": _reference(strings, row, used_strings),
                    "schema_version": "dm_entity_v1",
                }
            else:
                if type(row) is not list or len(row) != 5:
                    raise ValueError("invalid assertion wire row")
                aid, subject, predicate, value, meta = row
                expanded = {
                    "assertion_id": _reference(strings, aid, used_strings),
                    "metadata": _chunk(_reference(metadata, meta, used_metadata)),
                    "predicate": _reference(strings, predicate, used_strings),
                    "schema_version": "dm_assertion_v1",
                    "subject_entity_id": _reference(strings, subject, used_strings),
                    "value": _chunk(_reference(strings, value, used_strings)),
                }
            yield key, expanded
    if used_strings != set(range(len(strings))) or used_metadata != set(range(len(metadata))):
        raise ValueError("unused wire table entries")


def _expand(packet: dict[str, Any], source: StoredKnowledgeRevision) -> dict[str, Any]:
    if set(packet) != _FIELDS:
        raise ValueError("unexpected wire fields")
    if packet["envelope_sha256"] != canonical_sha256(source.revision.model_dump(mode="json")):
        raise ValueError("wire source envelope mismatch")
    if packet["graph_sha256"] != source.graph_payload_sha256:
        raise ValueError("wire source graph mismatch")
    for key in ("strings", "metadata", "entities", "assertions", "aliases", "evidence"):
        if type(packet[key]) is not list:
            raise ValueError("wire tables must be arrays")
    for key in ("strings", "metadata"):
        if any(type(text) is not str for text in packet[key]):
            raise ValueError("wire tables must contain strings")
        if len(set(packet[key])) != len(packet[key]):
            raise ValueError("duplicate wire table entries")

    # The canonical source text is the existing verifier's immutable snapshot.
    # Only read it here; do not replace get_revision or its independent checks.
    ceiling = len(source._payload_json.encode("utf-8"))
    size = 0
    digest = hashlib.sha256()

    def emit(data: bytes) -> None:
        nonlocal size
        size += len(data)
        if size > ceiling:
            raise ValueError("wire expansion exceeds verified source size")
        digest.update(data)

    result: dict[str, Any] = {key: [] for key in ("aliases", "assertions", "entities", "evidence")}
    emit(b"{")
    rows = iter(_rows(packet))
    pending = next(rows, None)
    for index, key in enumerate(result):
        emit((b"," if index else b"") + _text(key) + b":[")
        first = True
        while pending is not None and pending[0] == key:
            row = pending[1]
            # This exact row is hashed, then returned to contract validation.
            encoded = canonical_json(row).encode("utf-8")
            emit((b"" if first else b",") + encoded)
            result[key].append(row)
            first = False
            pending = next(rows, None)
        emit(b"]")
    emit(b"}")
    if size != ceiling or digest.hexdigest() != source.graph_payload_sha256:
        raise ValueError("wire reconstructed source mismatch")
    return result


def encode_source_wire(source: StoredKnowledgeRevision) -> bytes:
    """Produce a private artifact only when exact source reconstruction succeeds."""
    payload = source.graph_payload
    try:
        if set(payload) != _ROOT_FIELDS:
            raise ValueError("unsupported root fields")
        if source.revision.graph_schema != "dm_vnext_graph_v1":
            raise ValueError("unsupported graph schema")
        if any(type(payload[key]) is not list for key in _ROOT_FIELDS):
            raise ValueError("unsupported source table")
        for row in payload["entities"]:
            if (
                type(row) is not dict
                or set(row) != _ENTITY_FIELDS
                or row["schema_version"] != "dm_entity_v1"
            ):
                raise ValueError("unsupported entity fields")
        for row in payload["assertions"]:
            if (
                type(row) is not dict
                or set(row) != _ASSERTION_FIELDS
                or row["schema_version"] != "dm_assertion_v1"
            ):
                raise ValueError("unsupported assertion fields")
        strings: list[str] = []
        metadata: list[str] = []
        positions: dict[str, int] = {}
        meta_positions: dict[str, int] = {}

        def intern(value: str, table: list[str], lookup: dict[str, int]) -> int:
            if type(value) is not str:
                raise ValueError("unsupported source string")
            if value not in lookup:
                lookup[value] = len(table)
                table.append(value)
            return lookup[value]

        def string(value: str) -> int:
            return intern(value, strings, positions)

        packet = {
            "format": _FORMAT,
            "envelope_sha256": canonical_sha256(source.revision.model_dump(mode="json")),
            "graph_sha256": source.graph_payload_sha256,
            "strings": strings,
            "metadata": metadata,
            "entities": [string(row["entity_id"]) for row in payload["entities"]],
            "assertions": [
                [
                    string(row["assertion_id"]),
                    string(row["subject_entity_id"]),
                    string(row["predicate"]),
                    string(canonical_json(row["value"])),
                    intern(canonical_json(row["metadata"]), metadata, meta_positions),
                ]
                for row in payload["assertions"]
            ],
            "aliases": [canonical_json(row) for row in payload["aliases"]],
            "evidence": [canonical_json(row) for row in payload["evidence"]],
        }
        _expand(packet, source)
        return canonical_json(packet).encode("utf-8")
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
        raise UnsupportedSourceWire(str(exc)) from exc


def decode_source_wire(data: bytes, source: StoredKnowledgeRevision) -> dict[str, Any] | None:
    """Return verified source facts, or None for an unsupported format.

    This is not a parsed-model factory. The caller must still apply the ordinary
    contract validation, structural checks, indexes and semantic digest builder.
    """
    try:
        byte_limit = 8 * len(source._payload_json.encode("utf-8")) + 4096
        if type(data) is not bytes or len(data) > byte_limit:
            raise ValueError("wire artifact byte limit exceeded")
        packet = _load(data.decode("utf-8"), 3)
        if type(packet) is not dict or type(packet.get("format")) is not str:
            raise ValueError("invalid wire format header")
        if packet["format"] != _FORMAT:
            return None
        return _expand(packet, source)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
        raise PersistenceIntegrityError(f"native source wire integrity failure: {exc}") from exc
