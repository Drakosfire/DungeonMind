"""Capability policy contracts (schema ``dm_capability_policy_v1``).

No agent or surface receives silent durable write authority. Every tool call
is classified against a policy bound to an explicit graph scope; evaluation
is fail-closed (unknown tool, unknown effect, or missing required scope means
denial). Categories follow the closed DungeonMindBuddy architecture decision:
read_only | draft_only | preview_write | confirm_commit | admin_diagnostic.

``CapabilityPolicy`` is the sole authority for the agent-visible tool set.
``enabled_tools`` and ``tool_rules`` must name exactly the same tools.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import DungeonMindModel
from .projection import Admissibility, FocusKind, ProjectionFocus

CAPABILITY_POLICY_SCHEMA = "dm_capability_policy_v1"


class CapabilityCategory(StrEnum):
    READ_ONLY = "read_only"
    DRAFT_ONLY = "draft_only"
    PREVIEW_WRITE = "preview_write"
    CONFIRM_COMMIT = "confirm_commit"
    ADMIN_DIAGNOSTIC = "admin_diagnostic"


class CapabilityEffect(StrEnum):
    READ = "read"
    DRAFT = "draft"
    PREVIEW_WRITE = "preview_write"
    COMMIT = "commit"  # durable write; requires explicit confirmation receipt
    ADMIN = "admin"


class GraphScope(DungeonMindModel):
    """The scope a policy is bound to. Required for any graph-touching tool.

    ``admissibility`` is required with no default — absence never means GM.
    Campaign ownership lives only on ``campaign_id`` here; focus is chronology.
    """

    world_id: str
    campaign_id: str | None = None
    focus: ProjectionFocus = Field(default_factory=ProjectionFocus)
    admissibility: Admissibility
    revision_pin: str | None = None

    @model_validator(mode="after")
    def _session_focus_requires_campaign(self) -> Self:
        if self.focus.kind is FocusKind.SESSION and not self.campaign_id:
            raise ValueError("session focus requires campaign_id on GraphScope")
        return self


class ToolCapabilityRule(DungeonMindModel):
    tool_name: str
    category: CapabilityCategory
    require_graph_scope: bool = True
    allowed_effects: list[CapabilityEffect] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_allowed_effects(self) -> Self:
        if len(self.allowed_effects) != len(set(self.allowed_effects)):
            raise ValueError("duplicate allowed_effects are rejected")
        return self


class CapabilityPolicy(DungeonMindModel):
    schema_version: Literal["dm_capability_policy_v1"] = CAPABILITY_POLICY_SCHEMA
    policy_id: str
    graph_scope: GraphScope | None = None
    enabled_tools: list[str] = []
    tool_rules: list[ToolCapabilityRule] = []

    @model_validator(mode="after")
    def _tools_and_rules_are_one_set(self) -> Self:
        if len(self.enabled_tools) != len(set(self.enabled_tools)):
            raise ValueError("enabled_tools must be unique")
        rule_names = [rule.tool_name for rule in self.tool_rules]
        if len(rule_names) != len(set(rule_names)):
            raise ValueError("tool_rules must have unique tool_name values")
        enabled = set(self.enabled_tools)
        rules = set(rule_names)
        if enabled != rules:
            raise ValueError(
                "enabled_tools and tool_rules must describe the same set of tool names"
            )
        return self
