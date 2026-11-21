"""Rank bounds from authenticated search and subject postings."""

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import TypeAlias

from dungeonmind.application.vnext.search import (
    RANK_CLASS_EXACT_ID,
    RANK_CLASS_LEXICAL,
    RANK_CLASS_PREDICATE_OR_TERM,
    SCORE_ADMITTED_ASSERTION,
    SCORE_LEXICAL_TOKEN,
    SearchHit,
    SearchResult,
    _hit_sort_key,
    _result_digest,
)

Postings: TypeAlias = Mapping[tuple[str, str], frozenset[str]]


def read_bounded_search(
    *,
    raw_query: str,
    normalized_query: str,
    limit: int,
    exact_entity_exists: bool,
    postings: Postings,
    subject_assertions: Mapping[str, set[str]],
    read_wave: Callable[[set[str], Mapping[tuple[str, str], tuple[str, ...]]], SearchResult],
) -> SearchResult:
    """Run complete per-entity admission only while a candidate can still rank."""
    groups = dict(subject_assertions)
    if exact_entity_exists:
        groups.setdefault(raw_query, set())
    predicate_or_term = postings["predicate", normalized_query] | postings["term", normalized_query]
    lexical = tuple(values for (family, _), values in postings.items() if family == "lexical")
    ranked = []
    for subject, assertion_ids in groups.items():
        if subject == raw_query and exact_entity_exists:
            rank_class = RANK_CLASS_EXACT_ID
        elif not assertion_ids.isdisjoint(predicate_or_term):
            rank_class = RANK_CLASS_PREDICATE_OR_TERM
        else:
            rank_class = RANK_CLASS_LEXICAL
        score = SCORE_LEXICAL_TOKEN * sum(not x.isdisjoint(assertion_ids) for x in lexical)
        score += SCORE_ADMITTED_ASSERTION * len(assertion_ids)
        ranked.append((rank_class, -score, subject))
    ranked.sort()

    hits: list[SearchHit] = []
    first: SearchResult | None = None
    for offset in range(0, len(ranked), limit):
        if len(hits) == limit and ranked[offset] > _hit_sort_key(hits[-1]):
            break
        subjects = {subject for _, _, subject in ranked[offset : offset + limit]}
        keys = {key for subject in subjects for key in groups[subject]}
        subset = {key: tuple(sorted(values & keys)) for key, values in postings.items()}
        wave = read_wave(subjects, subset)
        if first is None:
            first = wave
        hits.extend(hit for hit in wave.hits if hit.entity.entity_id in subjects)
        hits = sorted(hits, key=_hit_sort_key)[:limit]
    if first is None:
        return read_wave(set(), {key: () for key in postings})
    return replace(
        first,
        hits=tuple(hits),
        result_digest=_result_digest(
            identity=first.identity, normalized_query=normalized_query, limit=limit,
            hits=hits, completeness=first.completeness,
        ),
    )
