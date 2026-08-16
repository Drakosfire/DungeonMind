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
    """How a claim is known. Confidence is not authority; this is provenance.

    Historical v1 contribution/assertion vocabulary. Do not add members here;
    contribution-history v2 uses :class:`ContributionEpistemicKind`.
    """

    ASSERTED = "asserted"  # directly stated by an admitted source or GM
    INFERRED = "inferred"  # derived by a governed process from asserted facts
    SPECULATIVE = "speculative"  # hypothesis; never presented as fact


class ContributionEpistemicKind(StrEnum):
    """Contribution-history epistemic vocabulary for ``dm_graph_contribution_v2``.

    Additive admission of ``source_derived_candidate``. This is not a remapping
    of :class:`EpistemicKind`: the extra member is not equivalent to asserted,
    inferred, or speculative, and must not be normalized to those values.
    """

    ASSERTED = "asserted"
    INFERRED = "inferred"
    SPECULATIVE = "speculative"
    SOURCE_DERIVED_CANDIDATE = "source_derived_candidate"


class CanonState(StrEnum):
    """Canonical standing of an object or assertion."""

    CANONICAL = "canonical"
    PROVISIONAL = "provisional"  # exists but not yet canon; excluded from canon reads
    RETRACTED = "retracted"
