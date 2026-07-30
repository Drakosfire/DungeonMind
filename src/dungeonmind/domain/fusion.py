"""Deterministic candidate rank fusion.

The retrieval sequence (ADR-0003) fuses exact / lexical / dense channels into
one candidate list before graph resolution. Two fusers are provided:

- ``reciprocal_rank_fusion``: score-free, robust default.
- ``weighted_minmax_fusion``: preserves the DungeonMindServer RulesLawyer
  hybrid behavior (per-channel min-max normalization, weighted sum, e.g.
  lexical 0.3 / semantic 0.7) as a *comparison baseline* for benchmarks.
  It is not the presumed production default; that choice is benchmark-gated.

Both are total and deterministic: ties break by (score desc, id asc).
"""

from collections.abc import Mapping, Sequence


def _sorted_scored(scores: Mapping[str, float]) -> list[tuple[str, float]]:
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]],
    *,
    k: int = 60,
) -> list[tuple[str, float]]:
    """Fuse ranked id lists into ``[(id, rrf_score)]`` sorted deterministically."""
    if k <= 0:
        raise ValueError("k must be positive")
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return _sorted_scored(scores)


def _minmax(channel: Mapping[str, float]) -> dict[str, float]:
    if not channel:
        return {}
    lo = min(channel.values())
    hi = max(channel.values())
    if hi == lo:
        return {doc_id: 0.0 for doc_id in channel}
    span = hi - lo
    return {doc_id: (score - lo) / span for doc_id, score in channel.items()}


def weighted_minmax_fusion(
    channels: Mapping[str, Mapping[str, float]],
    weights: Mapping[str, float],
) -> list[tuple[str, float]]:
    """Fuse raw per-channel scores via min-max normalization + weighted sum.

    ``channels`` maps channel name → {doc_id: raw_score}; ``weights`` maps
    channel name → weight. Channels missing from ``weights`` contribute 0.
    """
    fused: dict[str, float] = {}
    for name, scores in channels.items():
        weight = weights.get(name, 0.0)
        if weight == 0.0:
            continue
        for doc_id, norm in _minmax(scores).items():
            fused[doc_id] = fused.get(doc_id, 0.0) + weight * norm
    return _sorted_scored(fused)
