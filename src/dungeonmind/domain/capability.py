"""Fail-closed capability evaluation.

Pure evaluation of a ``CapabilityPolicy`` against a requested tool effect.
Denial is the default: unknown tool, disabled tool, undeclared effect, and
missing required graph scope all deny. Commit effects additionally require a
``confirm_commit`` category rule — read-scoped policies can never authorize
durable writes, which is the enforcement point for "no agent is a privileged
writer".

``CapabilityPolicy`` is the sole authority for the agent-visible tool set.
Derive names with ``permitted_tool_names``; never accept a caller-supplied list.
"""

from ..contracts.capability import (
    CapabilityCategory,
    CapabilityEffect,
    CapabilityPolicy,
)
from .errors import CapabilityDeniedError


def permitted_tool_names(policy: CapabilityPolicy) -> list[str]:
    """Derive the model-visible tool set from the sole authority: ``CapabilityPolicy``.

    Fail-closed: enabled + matching rule required; graph-touching tools that
    require scope are excluded when the policy has no graph scope. Order follows
    ``enabled_tools``.
    """
    names: list[str] = []
    rules_by_name = {rule.tool_name: rule for rule in policy.tool_rules}
    for tool_name in policy.enabled_tools:
        rule = rules_by_name.get(tool_name)
        if rule is None:
            continue
        if rule.require_graph_scope and policy.graph_scope is None:
            continue
        names.append(tool_name)
    return names


def evaluate_capability(
    policy: CapabilityPolicy,
    *,
    tool_name: str,
    effect: CapabilityEffect,
) -> None:
    """Return None when allowed; raise ``CapabilityDeniedError`` otherwise."""
    rule = next((r for r in policy.tool_rules if r.tool_name == tool_name), None)
    if rule is None:
        raise CapabilityDeniedError(f"tool {tool_name!r} has no capability rule")
    if tool_name not in policy.enabled_tools:
        raise CapabilityDeniedError(f"tool {tool_name!r} is not enabled by this policy")
    if effect not in rule.allowed_effects:
        raise CapabilityDeniedError(
            f"tool {tool_name!r} may not perform effect {effect.value!r}",
            details={"tool_name": tool_name, "effect": effect.value},
        )
    if rule.require_graph_scope and policy.graph_scope is None:
        raise CapabilityDeniedError(
            f"tool {tool_name!r} requires a bound graph scope",
            details={"tool_name": tool_name},
        )
    if effect is CapabilityEffect.COMMIT and rule.category is not CapabilityCategory.CONFIRM_COMMIT:
        raise CapabilityDeniedError(
            f"tool {tool_name!r} is not a confirm_commit capability; durable writes "
            "require an explicit confirm_commit rule and confirmation receipt",
            details={"tool_name": tool_name},
        )
