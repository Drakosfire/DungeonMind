"""Indexed alias discovery followed by fresh, existing alias authorization.

Structural index state is reusable; admission/provenance and authorized results
are never cached. Alias identities retain their accepted space-wide semantics.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass

from dungeonmind.domain.canonical import canonical_sha256

from .alias_search_index import (
    ALIAS_SEARCH_INDEX_VERSION,
    AliasSearchIndexCache,
    _build_alias_search_index,
    alias_match_text,
    alias_query_tokens,
    alias_token_variants,
    index_key_for_parsed,
    normalize_alias_query,
)
from .entity_reads import _authorize_aliases
from .errors import SearchReadIntegrityError
from .read_context import KnowledgeReadContext
from .records import ParsedIdentityAlias
from .search import SearchCompleteness, SearchReadIdentity


@dataclass(frozen=True, slots=True)
class AliasSearchHit:
    alias: ParsedIdentityAlias
    match_kinds: tuple[str, ...]
    matched_tokens: tuple[str, ...]
    ambiguous: bool


@dataclass(frozen=True, slots=True)
class AliasSearchResult:
    identity: SearchReadIdentity
    normalized_query: str
    request_sha256: str
    matching_policy_version: str
    limit: int
    hits: tuple[AliasSearchHit, ...]
    completeness: SearchCompleteness
    result_digest: str


@dataclass(frozen=True, slots=True)
class _AliasSearchReadTrace:
    index_cache_hit: bool
    index_build_aliases_visited: int
    structural_candidate_aliases: int
    matched_aliases: int
    authorized_aliases: int
    evidence_refs_requested: int
    source_artifact_ids_requested: int
    source_revision_ids_requested: int
    provenance_snapshot_calls: int
    returned_aliases: int


_ACTIVE_TRACE: ContextVar[list[_AliasSearchReadTrace] | None] = ContextVar(
    "vnext_alias_search_trace",
    default=None,
)


@contextmanager
def _capture_alias_search_trace() -> Iterator[list[_AliasSearchReadTrace]]:
    """Package-private work characterization, never public retrieval metadata."""
    traces: list[_AliasSearchReadTrace] = []
    token = _ACTIVE_TRACE.set(traces)
    try:
        yield traces
    finally:
        _ACTIVE_TRACE.reset(token)


def _sort_key(hit: AliasSearchHit) -> tuple[int, int, str, str, str]:
    strength = 0 if "exact" in hit.match_kinds else 1 if "phrase" in hit.match_kinds else 2
    return (
        strength,
        -len(hit.matched_tokens),
        hit.alias.alias_text.strip().casefold(),
        hit.alias.entity_id,
        hit.alias.alias_id,
    )


def _hit_payload(hit: AliasSearchHit) -> dict[str, object]:
    alias = hit.alias
    return {
        "alias_id": alias.alias_id,
        "entity_id": alias.entity_id,
        "alias_text": alias.alias_text,
        "standing": alias.standing.value,
        "evidence_ref_ids": list(alias.evidence_ref_ids),
        "match_kinds": list(hit.match_kinds),
        "matched_tokens": list(hit.matched_tokens),
        "ambiguous": hit.ambiguous,
    }


class AliasSearchReadService:
    """Read authorized alias witnesses before applying an explicit result limit.

    A caller-owned cache optionally reuses structural postings. Each call still
    evaluates its matching alias records through the current read context.
    """

    __slots__ = ()

    def search_aliases(
        self,
        context: KnowledgeReadContext,
        query: str,
        *,
        limit: int = 20,
        index_cache: AliasSearchIndexCache | None = None,
    ) -> AliasSearchResult:
        normalized = normalize_alias_query(query)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            raise SearchReadIntegrityError("alias search limit must be a nonnegative integer")
        if index_cache is not None and not isinstance(index_cache, AliasSearchIndexCache):
            raise SearchReadIntegrityError("alias search cache must be an AliasSearchIndexCache")
        parsed = context.parsed
        if index_cache is None:
            index, cache_hit = _build_alias_search_index(parsed), False
        else:
            index, cache_hit = index_cache.get_or_build(parsed)
        if index.key != index_key_for_parsed(parsed):
            raise SearchReadIntegrityError(
                "alias search index differs from the pinned parsed revision"
            )
        tokens = alias_query_tokens(normalized)
        terms = tuple(
            sorted(
                {
                    normalized,
                    *(variant for token in tokens for variant in alias_token_variants(token)),
                }
            )
        )
        candidate_ids = index.candidate_ids(terms)
        matched: dict[str, tuple[ParsedIdentityAlias, tuple[str, ...], tuple[str, ...]]] = {}
        for alias_id in candidate_ids:
            alias = parsed.get_alias(alias_id)
            if alias is None or parsed.get_entity(alias.entity_id) is None:
                raise SearchReadIntegrityError(
                    "alias search index references a missing alias or entity"
                )
            kinds, matched_tokens = alias_match_text(alias.alias_text, normalized, tokens)
            if kinds:
                matched[alias_id] = alias, kinds, matched_tokens

        candidates = tuple(matched[alias_id][0] for alias_id in sorted(matched))
        # The shared owner applies standing and coherent evidence/source checks.
        # No scope or assertion-presence policy is added to identity aliases.
        (
            authorized,
            _provenance,
            _evaluated,
            evidence_refs,
            artifact_ids,
            revision_ids,
            snapshot_calls,
        ) = _authorize_aliases(context=context, candidates=candidates)
        groups: dict[str, set[str]] = {}
        for alias in authorized:
            if alias.alias_id not in matched:
                raise SearchReadIntegrityError("alias admission returned an unrequested witness")
            groups.setdefault(alias.alias_text.strip().casefold(), set()).add(alias.entity_id)
        all_hits = tuple(
            sorted(
                (
                    AliasSearchHit(
                        alias=alias,
                        match_kinds=matched[alias.alias_id][1],
                        matched_tokens=matched[alias.alias_id][2],
                        ambiguous=len(groups[alias.alias_text.strip().casefold()]) > 1,
                    )
                    for alias in authorized
                ),
                key=_sort_key,
            )
        )
        hits = all_hits[:limit]
        completeness = (
            SearchCompleteness(status="partial", reason="result_limit")
            if len(all_hits) > limit
            else SearchCompleteness(status="complete")
        )
        identity = SearchReadIdentity(
            space_id=parsed.space_id,
            revision_id=parsed.revision_id,
            domain_contract_id=parsed.domain_contract_ref.domain_id,
            domain_contract_revision=parsed.domain_contract_ref.domain_revision,
            semantic_profile_id=parsed.semantic_profile_ref.profile_id,
            semantic_profile_revision=parsed.semantic_profile_ref.profile_revision,
        )
        request_sha256 = canonical_sha256(context.request.model_dump(mode="json"))
        digest = canonical_sha256(
            {
                "identity": asdict(identity),
                "normalized_query": normalized,
                "request_sha256": request_sha256,
                "limit": limit,
                "matching_policy_version": ALIAS_SEARCH_INDEX_VERSION,
                "hits": [_hit_payload(hit) for hit in hits],
                "completeness": asdict(completeness),
            }
        )
        traces = _ACTIVE_TRACE.get()
        if traces is not None:
            traces.append(
                _AliasSearchReadTrace(
                    index_cache_hit=cache_hit,
                    index_build_aliases_visited=0 if cache_hit else index.alias_count,
                    structural_candidate_aliases=len(candidate_ids),
                    matched_aliases=len(matched),
                    authorized_aliases=len(authorized),
                    evidence_refs_requested=evidence_refs,
                    source_artifact_ids_requested=artifact_ids,
                    source_revision_ids_requested=revision_ids,
                    provenance_snapshot_calls=snapshot_calls,
                    returned_aliases=len(hits),
                )
            )
        return AliasSearchResult(
            identity=identity,
            normalized_query=normalized,
            request_sha256=request_sha256,
            matching_policy_version=ALIAS_SEARCH_INDEX_VERSION,
            limit=limit,
            hits=hits,
            completeness=completeness,
            result_digest=digest,
        )
