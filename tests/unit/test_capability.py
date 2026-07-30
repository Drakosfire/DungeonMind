"""Fail-closed capability evaluation: no silent durable write authority."""

import pytest

from dungeonmind.contracts import (
    Admissibility,
    CapabilityCategory,
    CapabilityEffect,
    CapabilityPolicy,
    GraphScope,
    ToolCapabilityRule,
)
from dungeonmind.domain import CapabilityDeniedError
from dungeonmind.domain.capability import evaluate_capability


def make_policy(**overrides: object) -> CapabilityPolicy:
    base: dict[str, object] = {
        "policy_id": "pol:test",
        "graph_scope": GraphScope(
            world_id="world:demo", admissibility=Admissibility.GM
        ),
        "enabled_tools": ["graph.search", "graph.read_source", "contrib.commit"],
        "tool_rules": [
            ToolCapabilityRule(
                tool_name="graph.search",
                category=CapabilityCategory.READ_ONLY,
                allowed_effects=[CapabilityEffect.READ],
            ),
            ToolCapabilityRule(
                tool_name="graph.read_source",
                category=CapabilityCategory.READ_ONLY,
                allowed_effects=[CapabilityEffect.READ],
            ),
            ToolCapabilityRule(
                tool_name="contrib.commit",
                category=CapabilityCategory.CONFIRM_COMMIT,
                allowed_effects=[CapabilityEffect.READ, CapabilityEffect.COMMIT],
            ),
        ],
    }
    base.update(overrides)
    return CapabilityPolicy(**base)  # type: ignore[arg-type]


def test_read_allowed() -> None:
    evaluate_capability(make_policy(), tool_name="graph.search", effect=CapabilityEffect.READ)


def test_commit_allowed_only_for_confirm_commit_category() -> None:
    evaluate_capability(make_policy(), tool_name="contrib.commit", effect=CapabilityEffect.COMMIT)
    with pytest.raises(CapabilityDeniedError):
        evaluate_capability(make_policy(), tool_name="graph.search", effect=CapabilityEffect.COMMIT)


def test_unknown_tool_denied() -> None:
    with pytest.raises(CapabilityDeniedError):
        evaluate_capability(
            make_policy(), tool_name="graph.drop_world", effect=CapabilityEffect.READ
        )


def test_disabled_tool_denied() -> None:
    policy = make_policy(enabled_tools=["graph.search"])
    with pytest.raises(CapabilityDeniedError):
        evaluate_capability(policy, tool_name="contrib.commit", effect=CapabilityEffect.COMMIT)


def test_undeclared_effect_denied() -> None:
    with pytest.raises(CapabilityDeniedError):
        evaluate_capability(make_policy(), tool_name="graph.search", effect=CapabilityEffect.DRAFT)


def test_missing_required_scope_denied() -> None:
    policy = make_policy(graph_scope=None)
    with pytest.raises(CapabilityDeniedError):
        evaluate_capability(policy, tool_name="graph.search", effect=CapabilityEffect.READ)
