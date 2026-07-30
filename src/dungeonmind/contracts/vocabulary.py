"""Shared seed vocabularies for durable contracts.

These are the v1 enums every durable assertion/evidence record needs. They are
intentionally small; when the DungeonMindBuddy kernel models move (see
Docs/Roadmaps/ROADMAP.md), conformance fixtures will pin the full vocabulary
and these enums may only be extended, never narrowed, without a schema
version bump.
"""

from enum import StrEnum


class Visibility(StrEnum):
    """Who may see a piece of knowledge. Fail-closed: unknown means hidden."""

    GM = "gm"
    PLAYER = "player"


class EpistemicKind(StrEnum):
    """How a claim is known. Confidence is not authority; this is provenance."""

    ASSERTED = "asserted"  # directly stated by an admitted source or GM
    INFERRED = "inferred"  # derived by a governed process from asserted facts
    SPECULATIVE = "speculative"  # hypothesis; never presented as fact


class CanonState(StrEnum):
    """Canonical standing of an object or assertion."""

    CANONICAL = "canonical"
    PROVISIONAL = "provisional"  # exists but not yet canon; excluded from canon reads
    RETRACTED = "retracted"
