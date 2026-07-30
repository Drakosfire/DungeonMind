"""Capability policy contracts (schema ``dm_capability_policy_v1``).

No agent or surface receives silent durable write authority. Every tool call
is classified against a policy bound to an explicit graph scope; evaluation
is fail-closed (unknown tool, unknown effect, or missing required scope means
denial). Categories follow the closed DungeonMindBuddy architecture decision:
read_only | draft_only | preview_write | confirm_commit | admin_diagnostic.
"""

from enum import StrEnum
from typing import Literal

from .base import DungeonMindModel
from .projection import Admissibility, ProjectionFocus

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
    """The scope a policy is bound to. Required for any graph-touching tool."""

    world_id: str
    campaign_id: str | None = None
    focus: ProjectionFocus = ProjectionFocus()
    admissibility: Admissibility = Admissibility.GM
    revision_pin: str | None = None


class ToolCapabilityRule(DungeonMindModel):
    tool_name: str
    category: CapabilityCategory
    require_graph_scope: bool = True
    allowed_effects: list[CapabilityEffect]


class CapabilityPolicy(DungeonMindModel):
    schema_version: Literal["dm_capability_policy_v1"] = CAPABILITY_POLICY_SCHEMA
    policy_id: str
    graph_scope: GraphScope | None = None
    enabled_tools: list[str] = []
    tool_rules: list[ToolCapabilityRule] = []
