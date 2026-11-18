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
import re
from collections.abc import Callable, Iterator
from json.encoder import encode_basestring
from typing import Any

from dungeonmind.domain.canonical import canonical_json, canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

from .model import PARSED_REVISION_FORMAT_VERSION
from .records import StoredKnowledgeRevision

_FORMAT = "dm_native_source_wire_v1"
_FIELDS = frozenset(
    {
        "format",
        "parsed_format",
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
_STRUCTURE_TOKEN = re.compile(r'["{}\[\]]')


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


def _depth(text: str, limit: int) -> int:
    """Bound nesting before allocation, skipping string bodies in C via find.

    Escaped quotes are identified by the immediately preceding backslash run.
    The scanner is linear and allocates no nested containers or token list.
    json.loads subsequently checks the full syntax and bracket types.
    """
    depth = maximum = position = 0
    while True:
        token = _STRUCTURE_TOKEN.search(text, position)
        if token is None:
            return maximum
        position = token.start()
        char = token[0]
        if char == '"':
            start = position + 1
            while True:
                end = text.find('"', start)
                if end < 0:
                    return maximum  # json.loads reports the unterminated string.
                back = end - 1
                while back >= start and text[back] == "\\":
                    back -= 1
                if (end - 1 - back) % 2 == 0:
                    break
                start = end + 1
            position = end + 1
            continue
        if char in "[{":
            depth += 1
            if depth > maximum:
                maximum = depth
            if depth > limit:
                raise ValueError("JSON nesting limit exceeded")
        elif char in "]}":
            depth -= 1
        position += 1


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
    # Complete canonical source equivalence is proved by the reconstructed root
    # hash. Re-serializing each chunk here repeats that proof without adding it.
    return _load(value, _MAX_CHUNK_DEPTH)


def _reference(table: list[Any], index: Any, used: set[int]) -> Any:
    if type(index) is not int or not 0 <= index < len(table):
        raise ValueError("invalid wire reference")
    used.add(index)
    return table[index]


def _rows(packet: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any], bytes]]:
    """Expand and hash exactly the same validated chunks, once per distinct text.

    Shared mutable JSON stays private until contract conversion freezes it. The
    wire-only inspection wrapper deep-copies its result before returning it.
    """
    strings = packet["strings"]
    metadata = packet["metadata"]
    used_strings: set[int] = set()
    used_metadata: set[int] = set()
    chunks: dict[str, Any] = {}
    quoted: dict[str, bytes] = {}

    def chunk(text: str) -> Any:
        if text not in chunks:
            chunks[text] = _chunk(text)
        return chunks[text]

    def quote(text: str) -> bytes:
        if text not in quoted:
            quoted[text] = _text(text)
        return quoted[text]

    for key in ("aliases", "assertions", "entities", "evidence"):
        for row in packet[key]:
            if key in ("aliases", "evidence"):
                if type(row) is not str:
                    raise ValueError("wire record chunk must be a string")
                expanded = chunk(row)
                if type(expanded) is not dict:
                    raise ValueError("wire record must be an object")
                encoded = row.encode("utf-8")
            elif key == "entities":
                eid = _reference(strings, row, used_strings)
                expanded = {"entity_id": eid, "schema_version": "dm_entity_v1"}
                encoded = b'{"entity_id":' + quote(eid) + b',"schema_version":"dm_entity_v1"}'
            else:
                if type(row) is not list or len(row) != 5:
                    raise ValueError("invalid assertion wire row")
                aid, subject, predicate, value, meta = row
                aid = _reference(strings, aid, used_strings)
                subject = _reference(strings, subject, used_strings)
                predicate = _reference(strings, predicate, used_strings)
                raw_value = _reference(strings, value, used_strings)
                raw_meta = _reference(metadata, meta, used_metadata)
                expanded = {
                    "assertion_id": aid,
                    "metadata": chunk(raw_meta),
                    "predicate": predicate,
                    "schema_version": "dm_assertion_v1",
                    "subject_entity_id": subject,
                    "value": chunk(raw_value),
                }
                encoded = b"".join(
                    (
                        b'{"assertion_id":',
                        quote(aid),
                        b',"metadata":',
                        raw_meta.encode("utf-8"),
                        b',"predicate":',
                        quote(predicate),
                        b',"schema_version":"dm_assertion_v1","subject_entity_id":',
                        quote(subject),
                        b',"value":',
                        raw_value.encode("utf-8"),
                        b"}",
                    )
                )
            yield key, expanded, encoded
    if used_strings != set(range(len(strings))) or used_metadata != set(range(len(metadata))):
        raise ValueError("unused wire table entries")


def _expand(
    packet: dict[str, Any],
    source: StoredKnowledgeRevision,
    consume: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if set(packet) != _FIELDS:
        raise ValueError("unexpected wire fields")
    if packet["envelope_sha256"] != canonical_sha256(source.revision.model_dump(mode="json")):
        raise ValueError("wire source envelope mismatch")
    if packet["graph_sha256"] != source.graph_payload_sha256:
        raise ValueError("wire source graph mismatch")
    if source.revision.graph_schema != "dm_vnext_graph_v1":
        raise ValueError("wire source graph schema mismatch")
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
            encoded = pending[2]
            emit((b"" if first else b",") + encoded)
            if consume is None:
                result[key].append(row)
            else:
                consume(key, row)
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
            "parsed_format": PARSED_REVISION_FORMAT_VERSION,
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


def _decode_source_wire(
    data: bytes,
    source: StoredKnowledgeRevision,
    consume: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any] | None:
    """Return verified source facts, or None for an unsupported format.

    This is not a parsed-model factory. The caller must still apply the ordinary
    contract validation, structural checks, indexes and semantic digest builder.
    """
    try:
        byte_limit = 8 * len(source._payload_json.encode("utf-8")) + 4096
        if type(data) is not bytes or len(data) > byte_limit:
            raise ValueError("wire artifact byte limit exceeded")
        # Generic allocation bounds apply before identifying the version; v1
        # packet framing must not constrain an otherwise unsupported version.
        text = data.decode("utf-8")
        maximum = _depth(text, _MAX_CHUNK_DEPTH)
        packet = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_float=_float,
            parse_constant=_constant,
        )
        if type(packet) is not dict or type(packet.get("format")) is not str:
            raise ValueError("invalid wire format header")
        if packet["format"] != _FORMAT:
            return None
        if maximum > 3:
            raise ValueError("JSON nesting limit exceeded")
        if type(packet.get("parsed_format")) is not str:
            raise ValueError("invalid parsed format header")
        if packet["parsed_format"] != PARSED_REVISION_FORMAT_VERSION:
            return None
        return _expand(packet, source, consume)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
        raise PersistenceIntegrityError(f"native source wire integrity failure: {exc}") from exc


def decode_source_wire(data: bytes, source: StoredKnowledgeRevision) -> dict[str, Any] | None:
    """Inspection path: return isolated primary wire, still requiring contracts/structure.

    The fast parsed factory consumes the private pooled expansion directly. Neither
    path may bypass the source proof or use separately supplied normalized facts.
    """
    payload = _decode_source_wire(data, source)
    # A deepcopy preserves aliases in the pooled graph. A JSON roundtrip gives
    # every mutable occurrence its own container, like ordinary source loading.
    return json.loads(canonical_json(payload)) if payload is not None else None
