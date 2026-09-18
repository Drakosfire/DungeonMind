"""Shared deterministic query/index normalization for vNext search.

Builder index construction and SearchReadService lookup must use the same rule.
"""

from __future__ import annotations

import re

SEARCH_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def normalize_search_query(query: str) -> str:
    """Trim and lowercase a caller query. Empty after trim is the empty-query signal."""
    return query.strip().lower()


def tokenize_search_text(text: str) -> tuple[str, ...]:
    """Return deterministic lowercase alphanumeric tokens in encounter order."""
    return tuple(SEARCH_TOKEN_PATTERN.findall(text.lower()))
