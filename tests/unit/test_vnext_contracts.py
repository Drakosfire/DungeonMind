from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dungeonmind.contracts.vnext import (
    Assertion,
    AssertionMetadata,
    EntityRefValue,
    EpistemicBasis,
    KnowledgeStanding,
    LabelsAnyVisibility,
    ScopeBinding,
    ScopeSelector,
    TimelessTemporalScope,
    UtcIntervalTemporalScope,
)


def _metadata() -> AssertionMetadata:
    return AssertionMetadata(
        scope=[ScopeBinding(axis="organization:project", value="retrieval")],
        visibility=LabelsAnyVisibility(labels=["organization:team"]),
        epistemic_basis=EpistemicBasis.ASSERTED,
        claim_mode="organization:fact",
        standing=KnowledgeStanding.ESTABLISHED,
        evidence_ref_ids=["evidence-1"],
        temporal_scope=TimelessTemporalScope(),
    )


def test_generic_assertion_round_trips_relationship_and_governance_axes() -> None:
    assertion = Assertion(
        assertion_id="a-1",
        subject_entity_id="priya",
        predicate="organization:owns",
        value=EntityRefValue(entity_id="retrieval-evaluation"),
        metadata=_metadata(),
    )
    assert Assertion.model_validate_json(assertion.model_dump_json()) == assertion


def test_scope_selector_rejects_duplicate_and_wildcard_overlap() -> None:
    with pytest.raises(ValidationError):
        ScopeSelector(
            bindings=[
                ScopeBinding(axis="organization:team", value="research"),
                ScopeBinding(axis="organization:team", value="research"),
            ]
        )
    with pytest.raises(ValidationError):
        ScopeSelector(
            bindings=[ScopeBinding(axis="organization:team", value="research")],
            wildcard_axes=["organization:team"],
        )


def test_temporal_interval_requires_ordered_bound() -> None:
    with pytest.raises(ValidationError):
        UtcIntervalTemporalScope(
            valid_from=datetime(2026, 9, 8, tzinfo=UTC),
            valid_until=datetime(2026, 9, 7, tzinfo=UTC),
        )


def test_unknown_fields_and_malformed_terms_fail_closed() -> None:
    with pytest.raises(ValidationError):
        Assertion(
            assertion_id="a-1",
            subject_entity_id="p",
            predicate="Bad Term",
            value=EntityRefValue(entity_id="r"),
            metadata=_metadata(),
            extra="drift",
        )
