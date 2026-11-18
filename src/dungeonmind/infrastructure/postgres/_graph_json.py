"""Private canonicalization with bounded mutable lifetimes for native JSONB text.

This supplies canonical source bytes, not authority or validated knowledge. The
repository must still check the complete envelope, fingerprints and identities.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ...domain.canonical import canonical_json
from ...domain.errors import PersistenceIntegrityError

_WHITESPACE = re.compile(r"[ \t\r\n]*")
_DECODER = json.JSONDecoder()
_NATIVE_FIELDS = frozenset({"entities", "assertions", "aliases", "evidence"})


def _shallow(value: Any, depth: int = 0) -> bool:
    # Deep/opaque shapes take the ordinary whole-object path. Keep the fast path
    # far below the interpreter's recursive JSON decoding/serialization limit.
    if type(value) not in (dict, list):
        return True
    if depth >= 64:
        return False
    return all(
        _shallow(item, depth + 1) for item in (value.values() if type(value) is dict else value)
    )


def _native_json(text: str) -> str | None:
    position = _WHITESPACE.match(text, 0).end()  # type: ignore[union-attr]
    if text[position] != "{":
        return None
    position += 1
    parts: dict[str, str] = {}
    # A key must follow every comma; a closing brace is allowed only after a
    # complete value. Empty/duplicate/other root shapes use ordinary decoding.
    while True:
        position = _WHITESPACE.match(text, position).end()  # type: ignore[union-attr]
        key, position = _DECODER.raw_decode(text, position)
        if type(key) is not str or key not in _NATIVE_FIELDS or key in parts:
            return None
        position = _WHITESPACE.match(text, position).end()  # type: ignore[union-attr]
        if text[position] != ":":
            return None
        position = _WHITESPACE.match(text, position + 1).end()  # type: ignore[union-attr]
        if text[position] != "[":
            return None
        position = _WHITESPACE.match(text, position + 1).end()  # type: ignore[union-attr]
        rows: list[str] = []
        if text[position] != "]":
            while True:
                row, position = _DECODER.raw_decode(text, position)
                if not _shallow(row):
                    return None
                rows.append(canonical_json(row))
                del row
                position = _WHITESPACE.match(text, position).end()  # type: ignore[union-attr]
                if text[position] == "]":
                    break
                if text[position] != ",":
                    return None
                position = _WHITESPACE.match(text, position + 1).end()  # type: ignore[union-attr]
        parts[key] = "[" + ",".join(rows) + "]"
        position = _WHITESPACE.match(text, position + 1).end()  # type: ignore[union-attr]
        if text[position] == "}":
            position = _WHITESPACE.match(text, position + 1).end()  # type: ignore[union-attr]
            if position != len(text) or parts.keys() != _NATIVE_FIELDS:
                return None
            return "{" + ",".join(canonical_json(k) + ":" + parts[k] for k in sorted(parts)) + "}"
        if text[position] != ",":
            return None
        position += 1


def canonical_graph_json(text: str) -> str:
    """Match ordinary object decoding/canonicalization; optimize native arrays.

    Unsupported shapes and malformed fast-path syntax use the ordinary decoder,
    which remains responsible for rejection. No global decoder/GC configuration
    changes, memoized verification or persistent mutable source graph.
    """
    try:
        native = _native_json(text)
        if native is not None:
            return native
    except (ValueError, IndexError, RecursionError):
        pass
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise PersistenceIntegrityError("knowledge revision graph_payload is not an object")
    return canonical_json(payload)
