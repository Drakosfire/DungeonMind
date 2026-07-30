"""Canonical JSON serialization and content hashing.

Every durable hash in DungeonMind is computed over canonical JSON: sorted
keys, tight separators, UTF-8, NaN/Infinity rejected. Two records with the
same meaning must hash identically regardless of dict insertion order or
producer. Changing this function changes every content address in the system;
it is therefore deliberately tiny and frozen by test.
"""

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Serialize a JSON-compatible value in its single canonical form."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    """SHA-256 hex digest of the canonical JSON form of ``value``."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    """SHA-256 hex digest of raw text (source bodies, chunk content)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
