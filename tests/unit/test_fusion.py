"""Deterministic rank fusion, including the RulesLawyer min-max baseline."""

import pytest

from dungeonmind.domain import reciprocal_rank_fusion, weighted_minmax_fusion


def test_rrf_deterministic_and_tie_broken() -> None:
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "a"]])
    assert fused == [("a", pytest.approx(1 / 61 + 1 / 62)), ("b", pytest.approx(1 / 61 + 1 / 62))]
    fused_again = reciprocal_rank_fusion([["b", "a"], ["a", "b"]])
    assert fused == fused_again


def test_rrf_prefers_consistently_high_ranks() -> None:
    fused = reciprocal_rank_fusion([["x", "y", "z"], ["x", "z"], ["y"]])
    assert fused[0][0] == "x"


def test_rrf_rejects_nonpositive_k() -> None:
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"]], k=0)


def test_weighted_minmax_matches_ruleslawyer_baseline() -> None:
    lexical = {"d1": 2.0, "d2": 0.0}
    semantic = {"d1": 0.5, "d2": 1.0}
    fused = weighted_minmax_fusion(
        {"lexical": lexical, "semantic": semantic},
        {"lexical": 0.3, "semantic": 0.7},
    )
    assert fused[0] == ("d2", pytest.approx(0.3 * 0.0 + 0.7 * 1.0))
    assert fused[1] == ("d1", pytest.approx(0.3 * 1.0 + 0.7 * 0.0))


def test_weighted_minmax_degenerate_channel_is_zero() -> None:
    fused = weighted_minmax_fusion({"dense": {"d1": 0.4, "d2": 0.4}}, {"dense": 1.0})
    assert fused == [("d1", 0.0), ("d2", 0.0)]


def test_weighted_minmax_ignores_unweighted_channels() -> None:
    fused = weighted_minmax_fusion(
        {"dense": {"d1": 1.0, "d3": 0.5}, "lexical": {"d2": 1.0}},
        {"dense": 1.0},
    )
    assert "d2" not in dict(fused)
    assert fused[0] == ("d1", 1.0)
