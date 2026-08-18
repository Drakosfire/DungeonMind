"""Existing-world observational correspondence contracts.

A read-only check classifies whether one supplied Buddy authority snapshot
(exact ``ExistingWorldAdoptionBundleV2`` bytes) and one adopted DungeonMind
world are observationally the same, observably stale, or divergent. The
result is a returned classification, never an error: malformed input,
integrity-invalid durable state, dangling adoption receipts, and persistence
outages raise typed ``DungeonMindError`` subclasses instead (see
``application.existing_world_correspondence``).

``source_identity`` pins the exact adopted bundle identity, not a field
subset: the supplied bytes' SHA-256, the bundle's ``adoption_id``, and the
full ``source_provenance`` must all equal the adoption receipt's pins. A
snapshot that is merely revision-compatible — same source revision, graph,
and history but a different adoption identity — is ``STALE``, never
``CORRESPONDING``.

The classification algebra is closed and enforced by the result model:

- ``CORRESPONDING``: all six checks ``match``.
- ``STALE``: ``source_identity`` ``diverged``; every other check
  ``not_evaluated``.
- ``MISMATCH``: ``source_identity`` ``match`` and at least one other check
  ``diverged``; ``not_evaluated`` entries may appear only after the first
  divergence (short-circuit order is part of the closed algebra).
- ``NOT_ADOPTED``: no adoption receipt for the world; every ``adopted_*``
  field is null and ``checks`` is empty.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .base import DungeonMindModel

EXISTING_WORLD_CORRESPONDENCE_RESULT_SCHEMA = "dm_existing_world_correspondence_result_v1"
EXISTING_WORLD_CORRESPONDENCE_CHECK_SCHEMA = "dm_existing_world_correspondence_check_v1"

CorrespondenceClassification = Literal["CORRESPONDING", "STALE", "MISMATCH", "NOT_ADOPTED"]
CorrespondenceCheckName = Literal[
    "source_identity",
    "graph_payload",
    "source_history",
    "contribution_history",
    "identity_history",
    "evidence_identity",
]
CorrespondenceCheckOutcome = Literal["match", "diverged", "not_evaluated"]

CORRESPONDENCE_CHECK_ORDER: tuple[CorrespondenceCheckName, ...] = (
    "source_identity",
    "graph_payload",
    "source_history",
    "contribution_history",
    "identity_history",
    "evidence_identity",
)


def _require_nonblank(value: str, *, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must be a non-blank string")
    return value


class ExistingWorldCorrespondenceCheckV1(DungeonMindModel):
    """One named diagnostic check inside a correspondence result."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["dm_existing_world_correspondence_check_v1"] = (
        EXISTING_WORLD_CORRESPONDENCE_CHECK_SCHEMA
    )
    check: CorrespondenceCheckName
    outcome: CorrespondenceCheckOutcome
    detail: str = ""

    @model_validator(mode="after")
    def _detail_matches_outcome(self) -> ExistingWorldCorrespondenceCheckV1:
        if self.outcome == "match":
            if self.detail != "":
                raise ValueError("detail must be empty when outcome is match")
        elif not self.detail.strip():
            raise ValueError(f"detail must name the {self.outcome} diagnostic")
        return self


class ExistingWorldCorrespondenceResultV1(DungeonMindModel):
    """Terminal classification of one snapshot↔adopted-world correspondence check."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["dm_existing_world_correspondence_result_v1"] = (
        EXISTING_WORLD_CORRESPONDENCE_RESULT_SCHEMA
    )
    classification: CorrespondenceClassification
    world_id: str
    observed_source_revision: str
    adopted_source_revision: str | None = None
    adoption_id: str | None = None
    adopted_revision: str | None = None
    checks: list[ExistingWorldCorrespondenceCheckV1] = Field(default_factory=list)

    @field_validator("world_id", "observed_source_revision")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        return _require_nonblank(value, field_name="correspondence identity field")

    @field_validator("adopted_source_revision", "adoption_id", "adopted_revision")
    @classmethod
    def _nonblank_when_present(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_nonblank(value, field_name="adopted identity field")

    @model_validator(mode="after")
    def _closed_classification_algebra(self) -> ExistingWorldCorrespondenceResultV1:
        adopted_fields = (
            self.adopted_source_revision,
            self.adoption_id,
            self.adopted_revision,
        )
        if self.classification == "NOT_ADOPTED":
            if any(field is not None for field in adopted_fields):
                raise ValueError("NOT_ADOPTED results must null every adopted_* field")
            if self.checks:
                raise ValueError("NOT_ADOPTED results must carry no checks")
            return self
        if any(field is None for field in adopted_fields):
            raise ValueError(f"{self.classification} results must populate every adopted_* field")
        names = [check.check for check in self.checks]
        if names != list(CORRESPONDENCE_CHECK_ORDER):
            raise ValueError(
                "checks must carry exactly one entry per check name in canonical order"
            )
        source_identity = self.checks[0]
        remaining = self.checks[1:]
        if self.classification == "CORRESPONDING":
            if any(check.outcome != "match" for check in self.checks):
                raise ValueError("CORRESPONDING requires every check to match")
        elif self.classification == "STALE":
            if source_identity.outcome != "diverged":
                raise ValueError("STALE requires source_identity to diverge")
            if any(check.outcome != "not_evaluated" for check in remaining):
                raise ValueError("STALE requires every other check to be not_evaluated")
        elif self.classification == "MISMATCH":
            if source_identity.outcome != "match":
                raise ValueError("MISMATCH requires source_identity to match")
            outcomes = [check.outcome for check in remaining]
            if "diverged" not in outcomes:
                raise ValueError("MISMATCH requires at least one diverged check")
            first_diverged = outcomes.index("diverged")
            if any(outcome == "not_evaluated" for outcome in outcomes[:first_diverged]):
                raise ValueError(
                    "MISMATCH not_evaluated checks must follow the first divergence"
                )
        return self
