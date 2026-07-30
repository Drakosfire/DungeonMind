"""Base model for all DungeonMind public contracts.

Strict by default: unknown fields are rejected so wire contracts fail closed
rather than silently dropping or accepting drift. This is a deliberate
correction of the looseness observed in DungeonMindBuddy's evidence models
(`extra="allow"`), which softened mandatory-metadata guarantees.
"""

from pydantic import BaseModel, ConfigDict


class DungeonMindModel(BaseModel):
    """Strict base for every durable or wire contract."""

    model_config = ConfigDict(extra="forbid")
