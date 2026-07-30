"""Fail-closed capability evaluation.

Pure evaluation of a ``CapabilityPolicy`` against a requested tool effect.
Denial is the default: unknown tool, disabled tool, undeclared effect, and
missing required graph scope all deny. Commit effects additionally require a
``confirm_commit`` category rule — read-scoped policies can never authorize
durable writes, which is the enforcement point for "no agent is a privileged
writer".
"""

from ..contracts.capability import (
    CapabilityCategory,
    CapabilityEffect,
    CapabilityPolicy,
)
from .errors import CapabilityDeniedError


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
