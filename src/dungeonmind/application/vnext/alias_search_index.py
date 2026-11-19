"""Versioned structural alias lookup; this module grants no read authority."""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock

from .errors import SearchReadIntegrityError
from .frozen_json import FrozenDict
from .model import ParsedKnowledgeRevision

ALIAS_SEARCH_INDEX_VERSION = "dm_alias_search_index_v1"
_WORDS = re.compile(r"[a-z0-9]+")
_CONTINUATION = r"A-Za-z0-9_:\-"


def normalize_alias_query(query: str) -> str:
    if not isinstance(query, str) or not query.strip():
        raise SearchReadIntegrityError("alias query must be a non-empty string")
    return query.strip().casefold()


def alias_query_tokens(normalized_query: str) -> tuple[str, ...]:
    return tuple(sorted({token for token in _WORDS.findall(normalized_query) if len(token) > 1}))


def alias_token_variants(token: str) -> tuple[str, ...]:
    variants = {token}
    if token.endswith("s"):
        if len(token) > 3:
            variants.add(token[:-1])
    else:
        variants.add(token + "s")
    return tuple(sorted(variants))


def _phrase(text: str, phrase: str) -> bool:
    return bool(re.search(rf"(?<![{_CONTINUATION}]){re.escape(phrase)}(?![{_CONTINUATION}])", text))


def alias_match_text(
    text: str, normalized_query: str, tokens: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    folded = text.casefold()
    matched = tuple(
        sorted(
            {
                token
                for token in tokens
                if any(_phrase(folded, variant) for variant in alias_token_variants(token))
            }
        )
    )
    kinds = []
    if folded.strip() == normalized_query:
        kinds.append("exact")
    if _phrase(folded, normalized_query):
        kinds.append("phrase")
    if matched:
        kinds.append("token")
    return tuple(kinds), matched


@dataclass(frozen=True, slots=True)
class AliasSearchIndexKey:
    space_id: str
    revision_id: str
    graph_payload_sha256: str
    semantic_digest: str
    parsed_format: str
    compatibility_key: str
    algorithm_version: str


def index_key_for_parsed(parsed: ParsedKnowledgeRevision) -> AliasSearchIndexKey:
    if not isinstance(parsed, ParsedKnowledgeRevision):
        raise SearchReadIntegrityError("alias index requires a parsed revision")
    try:
        values = (
            parsed.space_id,
            parsed.revision_id,
            parsed.graph_payload_sha256,
            parsed.semantic_digest,
            parsed.format_version,
            parsed.compatibility_key,
            ALIAS_SEARCH_INDEX_VERSION,
        )
    except (AttributeError, TypeError) as exc:
        raise SearchReadIntegrityError("alias index identity is malformed") from exc
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise SearchReadIntegrityError("alias index identity must contain non-empty strings")
    return AliasSearchIndexKey(*values)


def _grams(text: str, width: int) -> set[str]:
    return {text[start : start + width] for start in range(len(text) - width + 1)}


@dataclass(frozen=True, slots=True)
class AliasSearchIndex:
    key: AliasSearchIndexKey
    postings: FrozenDict[str, tuple[str, ...]]
    posting_count: int
    alias_count: int

    def candidate_ids(self, terms: tuple[str, ...]) -> tuple[str, ...]:
        candidates: set[str] = set()
        for term in terms:
            text = normalize_alias_query(term)
            grams = _grams(text, min(3, len(text)))
            rows = sorted((self.postings.get(gram, ()) for gram in grams), key=len)
            if not rows or not rows[0]:
                continue
            matches = set(rows[0])
            for row in rows[1:]:
                matches.intersection_update(row)
                if not matches:
                    break
            candidates.update(matches)
        return tuple(sorted(candidates))


def _build_alias_search_index(parsed: ParsedKnowledgeRevision) -> AliasSearchIndex:
    key = index_key_for_parsed(parsed)
    postings: dict[str, set[str]] = {}
    for alias_id, alias in parsed.aliases_by_id.items():
        text = alias.alias_text.strip().casefold()
        for width in (1, 2, 3):
            for gram in _grams(text, width):
                postings.setdefault(gram, set()).add(alias_id)
    frozen = FrozenDict({gram: tuple(sorted(ids)) for gram, ids in postings.items()})
    return AliasSearchIndex(key, frozen, sum(map(len, frozen.values())), len(parsed.aliases_by_id))


class AliasSearchIndexCache:
    """Explicit posting/entry-bounded LRU; no parsed object or admission retained.

    Builds are serialized with clear/eviction. The lock is released on return,
    before a caller can authorize aliases. Oversized indexes are served uncached.
    Posting limits bound retained memberships, not Python heap bytes or build peak.
    """

    def __init__(self, max_entries: int, max_postings: int) -> None:
        if (
            type(max_entries) is not int
            or max_entries < 1
            or type(max_postings) is not int
            or max_postings < 1
        ):
            raise SearchReadIntegrityError("alias cache capacities must be positive integers")
        self._max_entries = max_entries
        self._max_postings = max_postings
        self._lock = Lock()
        self._entries: OrderedDict[AliasSearchIndexKey, AliasSearchIndex] = OrderedDict()
        self._posting_count = 0

    def get_or_build(self, parsed: ParsedKnowledgeRevision) -> tuple[AliasSearchIndex, bool]:
        key = index_key_for_parsed(parsed)
        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                self._entries.move_to_end(key)
                return cached, True
            index = _build_alias_search_index(parsed)
            if index.key != key:
                raise SearchReadIntegrityError("alias index identity changed during construction")
            if index.posting_count > self._max_postings:
                return index, False
            while self._entries and (
                len(self._entries) >= self._max_entries
                or self._posting_count + index.posting_count > self._max_postings
            ):
                _, evicted = self._entries.popitem(last=False)
                self._posting_count -= evicted.posting_count
            self._entries[key] = index
            self._posting_count += index.posting_count
            return index, False

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._posting_count = 0

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._entries)

    @property
    def posting_count(self) -> int:
        with self._lock:
            return self._posting_count
