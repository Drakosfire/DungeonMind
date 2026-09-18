"""Deterministic indexed entity search over one pinned KnowledgeReadContext.

Search indexes discover match-witness assertions. They never authorize them.
Public ranking uses admitted witnesses only; hidden matches cannot occupy a
pre-admission result slot.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal

from dungeonmind.domain.canonical import canonical_sha256

from .errors import SearchReadIntegrityError
from .read_context import KnowledgeReadContext
from .records import (
    ParsedAssertion,
    ParsedEntity,
    ParsedLiteralValue,
    ParsedTermRefValue,
)
from .search_normalize import normalize_search_query, tokenize_search_text

MATCH_KIND_EXACT_ID = "exact_id"
MATCH_KIND_PREDICATE = "predicate"
MATCH_KIND_TERM_REF = "term_ref"
MATCH_KIND_LEXICAL = "lexical"

# Integer ranking weights. Higher wins; entity_id ascending is the final tie-break.
SCORE_EXACT_ENTITY_ID = 1_000_000
SCORE_PREDICATE_OR_TERM = 10_000
SCORE_LEXICAL_TOKEN = 10
SCORE_ADMITTED_ASSERTION = 1

_MATCH_KIND_ORDER = (
    MATCH_KIND_EXACT_ID,
    MATCH_KIND_PREDICATE,
    MATCH_KIND_TERM_REF,
    MATCH_KIND_LEXICAL,
)


@dataclass(frozen=True, slots=True)
class SearchReadIdentity:
    space_id: str
    revision_id: str
    domain_contract_id: str
    domain_contract_revision: str
    semantic_profile_id: str
    semantic_profile_revision: str


@dataclass(frozen=True, slots=True)
class SearchCompleteness:
    status: Literal["complete", "partial"]
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status == "complete":
            if self.reason is not None:
                raise SearchReadIntegrityError("complete search cannot carry a partial reason")
            return
        if self.reason is None:
            raise SearchReadIntegrityError("partial search requires an explicit reason")


@dataclass(frozen=True, slots=True)
class SearchHit:
    entity: ParsedEntity
    admitted_match_assertions: tuple[ParsedAssertion, ...]
    match_kinds: tuple[str, ...]
    deterministic_score: int


@dataclass(frozen=True, slots=True)
class SearchResult:
    identity: SearchReadIdentity
    normalized_query: str
    limit: int
    hits: tuple[SearchHit, ...]
    completeness: SearchCompleteness
    result_digest: str


@dataclass(frozen=True, slots=True)
class SearchReadTrace:
    index_lookups: int
    exact_id_lookups: int
    structural_assertion_candidates: int
    deduped_match_witness_assertions: int
    assertions_evaluated: int
    policy_evaluations: int
    unique_artifact_ids_requested: int
    unique_revision_ids_requested: int
    provenance_snapshot_calls: int
    admitted_match_assertions: int
    returned_entities: int


_ACTIVE_TRACE: ContextVar[list[SearchReadTrace] | None] = ContextVar(
    "dungeonmind_vnext_search_read_trace", default=None
)


@contextmanager
def _capture_search_read_trace() -> Iterator[list[SearchReadTrace]]:
    """Package-private characterization capture. Not part of the exported API."""
    bucket: list[SearchReadTrace] = []
    token = _ACTIVE_TRACE.set(bucket)
    try:
        yield bucket
    finally:
        _ACTIVE_TRACE.reset(token)


def _record_trace(trace: SearchReadTrace) -> None:
    bucket = _ACTIVE_TRACE.get()
    if bucket is None:
        return
    bucket.clear()
    bucket.append(trace)


def _identity(context: KnowledgeReadContext) -> SearchReadIdentity:
    parsed = context.parsed
    return SearchReadIdentity(
        space_id=parsed.space_id,
        revision_id=parsed.revision_id,
        domain_contract_id=parsed.domain_contract_ref.domain_id,
        domain_contract_revision=parsed.domain_contract_ref.domain_revision,
        semantic_profile_id=parsed.semantic_profile_ref.profile_id,
        semantic_profile_revision=parsed.semantic_profile_ref.profile_revision,
    )


def _identity_payload(identity: SearchReadIdentity) -> dict[str, str]:
    return {
        "space_id": identity.space_id,
        "revision_id": identity.revision_id,
        "domain_contract_id": identity.domain_contract_id,
        "domain_contract_revision": identity.domain_contract_revision,
        "semantic_profile_id": identity.semantic_profile_id,
        "semantic_profile_revision": identity.semantic_profile_revision,
    }


def _require_query(query: object) -> str:
    if not isinstance(query, str):
        raise SearchReadIntegrityError("search query must be a string")
    normalized = normalize_search_query(query)
    if normalized == "":
        raise SearchReadIntegrityError("search query must be non-empty after trim")
    return normalized


def _require_limit(limit: object) -> int:
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise SearchReadIntegrityError("search limit must be an integer")
    if limit < 0:
        raise SearchReadIntegrityError("search limit must be >= 0")
    return limit


def _literal_tokens(assertion: ParsedAssertion) -> tuple[str, ...]:
    value = assertion.value
    if not isinstance(value, ParsedLiteralValue):
        return ()
    if not isinstance(value.value, str):
        return ()
    return tokenize_search_text(value.value)


def _score_and_kinds(
    *,
    entity_id: str,
    normalized_query: str,
    query_tokens: tuple[str, ...],
    admitted: Sequence[ParsedAssertion],
    exact_id: bool,
) -> tuple[int, tuple[str, ...]]:
    kinds: list[str] = []
    score = 0
    if exact_id:
        kinds.append(MATCH_KIND_EXACT_ID)
        score += SCORE_EXACT_ENTITY_ID
    has_predicate = any(item.predicate == normalized_query for item in admitted)
    if has_predicate:
        kinds.append(MATCH_KIND_PREDICATE)
        score += SCORE_PREDICATE_OR_TERM
    has_term = any(
        isinstance(item.value, ParsedTermRefValue) and item.value.term == normalized_query
        for item in admitted
    )
    if has_term:
        kinds.append(MATCH_KIND_TERM_REF)
        score += SCORE_PREDICATE_OR_TERM
    witnessed_tokens: set[str] = set()
    query_token_set = set(query_tokens)
    for assertion in admitted:
        witnessed_tokens.update(tok for tok in _literal_tokens(assertion) if tok in query_token_set)
    if witnessed_tokens:
        kinds.append(MATCH_KIND_LEXICAL)
        score += SCORE_LEXICAL_TOKEN * len(witnessed_tokens)
    score += SCORE_ADMITTED_ASSERTION * len(admitted)
    ordered_kinds = tuple(kind for kind in _MATCH_KIND_ORDER if kind in kinds)
    if not ordered_kinds:
        raise SearchReadIntegrityError(
            f"admitted search hit {entity_id!r} has no authorized match kind"
        )
    return score, ordered_kinds


def _result_digest(
    *,
    identity: SearchReadIdentity,
    normalized_query: str,
    limit: int,
    hits: Sequence[SearchHit],
    completeness: SearchCompleteness,
) -> str:
    return canonical_sha256(
        {
            **_identity_payload(identity),
            "normalized_query": normalized_query,
            "limit": limit,
            "hits": [
                {
                    "entity_id": hit.entity.entity_id,
                    "admitted_match_assertion_ids": [
                        assertion.assertion_id for assertion in hit.admitted_match_assertions
                    ],
                    "match_kinds": list(hit.match_kinds),
                    "deterministic_score": hit.deterministic_score,
                }
                for hit in hits
            ],
            "completeness": {
                "status": completeness.status,
                "reason": completeness.reason,
            },
        }
    )


class SearchReadService:
    """Revision-local indexed search with candidate-local V2 admission."""

    __slots__ = ()

    def search_entities(
        self,
        context: KnowledgeReadContext,
        query: str,
        *,
        limit: int = 20,
    ) -> SearchResult:
        normalized_query = _require_query(query)
        resolved_limit = _require_limit(limit)
        identity = _identity(context)
        parsed = context.parsed
        query_tokens = tokenize_search_text(normalized_query)

        index_lookups = 0
        witness_ids: set[str] = set()

        index_lookups += 1
        witness_ids.update(parsed.lookup_predicate_assertions(normalized_query))
        index_lookups += 1
        witness_ids.update(parsed.lookup_term_ref_assertions(normalized_query))
        for token in query_tokens:
            index_lookups += 1
            witness_ids.update(parsed.lookup_lexical_assertions(token))

        exact_id_lookups = 1
        exact_entity = parsed.get_entity(normalized_query)

        ordered_witnesses = tuple(sorted(witness_ids))
        assertions_evaluated = 0
        policy_evaluations = 0
        unique_artifact_ids_requested = 0
        unique_revision_ids_requested = 0
        provenance_snapshot_calls = 0
        admitted_ids: tuple[str, ...] = ()

        if ordered_witnesses:
            admission, _provenance = context.evaluate_candidates(ordered_witnesses)
            assertions_evaluated = admission.work.assertions_evaluated
            policy_evaluations = admission.work.policy_evaluations
            unique_artifact_ids_requested = admission.work.artifact_ids_requested
            unique_revision_ids_requested = admission.work.revision_ids_requested
            provenance_snapshot_calls = admission.work.provenance_snapshot_calls
            admitted_ids = admission.admitted_assertion_ids

        grouped: dict[str, list[ParsedAssertion]] = {}
        for assertion_id in admitted_ids:
            assertion = parsed.get_assertion(assertion_id)
            if assertion is None:
                raise SearchReadIntegrityError(
                    f"admitted match witness {assertion_id!r} is missing from the revision"
                )
            subject_id = assertion.subject_entity_id
            if parsed.get_entity(subject_id) is None:
                raise SearchReadIntegrityError(
                    f"admitted match witness {assertion_id!r} references missing "
                    f"entity {subject_id!r}"
                )
            grouped.setdefault(subject_id, []).append(assertion)

        ranked: list[SearchHit] = []
        entity_ids = set(grouped)
        if exact_entity is not None:
            entity_ids.add(exact_entity.entity_id)

        for entity_id in entity_ids:
            entity = parsed.get_entity(entity_id)
            if entity is None:
                raise SearchReadIntegrityError(
                    f"search hit entity {entity_id!r} is missing from the revision"
                )
            admitted = tuple(sorted(grouped.get(entity_id, ()), key=lambda item: item.assertion_id))
            exact_id = exact_entity is not None and entity_id == exact_entity.entity_id
            if not admitted and not exact_id:
                continue
            score, kinds = _score_and_kinds(
                entity_id=entity_id,
                normalized_query=normalized_query,
                query_tokens=query_tokens,
                admitted=admitted,
                exact_id=exact_id,
            )
            ranked.append(
                SearchHit(
                    entity=entity,
                    admitted_match_assertions=admitted,
                    match_kinds=kinds,
                    deterministic_score=score,
                )
            )

        ranked.sort(key=lambda hit: (-hit.deterministic_score, hit.entity.entity_id))
        hits = tuple(ranked[:resolved_limit])
        completeness = SearchCompleteness(status="complete")
        digest = _result_digest(
            identity=identity,
            normalized_query=normalized_query,
            limit=resolved_limit,
            hits=hits,
            completeness=completeness,
        )
        _record_trace(
            SearchReadTrace(
                index_lookups=index_lookups,
                exact_id_lookups=exact_id_lookups,
                structural_assertion_candidates=len(ordered_witnesses),
                deduped_match_witness_assertions=len(ordered_witnesses),
                assertions_evaluated=assertions_evaluated,
                policy_evaluations=policy_evaluations,
                unique_artifact_ids_requested=unique_artifact_ids_requested,
                unique_revision_ids_requested=unique_revision_ids_requested,
                provenance_snapshot_calls=provenance_snapshot_calls,
                admitted_match_assertions=len(admitted_ids),
                returned_entities=len(hits),
            )
        )
        return SearchResult(
            identity=identity,
            normalized_query=normalized_query,
            limit=resolved_limit,
            hits=hits,
            completeness=completeness,
            result_digest=digest,
        )
