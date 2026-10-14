"""Worldbuilding observations use finalized review authority, never node replacement."""

import pytest

from dungeonmind.contracts.evidence import SourceDomain
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.domain.errors import HeadNotFoundError
from tests.conformance.test_reviewed_source_observation_retrieval import (
    EXISTING_OBJECT_ID,
    SOURCE_REVISION_ID,
    WORLD_ID,
    _fixture,
    _request,
)

VALUES = (
    *(
        (
            "worldbuilding_observation",
            f"Section {i}: some communities believe goats float; Example: a cloak {i}.",
        )
        for i in range(6)
    ),
    ("session_observation", "The keeper saw a blue lantern."),
)


def test_six_worldbuilding_sections_and_session_survive_reviewed_publication():
    service, graph, _sources, parent, child = _fixture(
        observation_values=VALUES,
        source_domain=SourceDomain.WORLDBUILDING,
    )
    before = graph.get_revision(WORLD_ID, child).graph_payload
    result = service.get_complete_object(_request(child), object_id=EXISTING_OBJECT_ID)
    rows = result.reviewed_source_observations
    assert len(rows) == len({r.assertion_id for r in rows}) == 7
    assert sorted((r.observation_kind, r.text) for r in rows) == sorted(VALUES)
    assert all(r.subject_object_id == EXISTING_OBJECT_ID for r in rows)
    assert all(r.source_revision_id == SOURCE_REVISION_ID for r in rows)
    assert all(r.review_id and r.contribution_id and r.evidence_ref_ids for r in rows)
    assert all(r.publication_revision_id == child for r in rows)
    prior = service.get_complete_object(_request(parent), object_id=EXISTING_OBJECT_ID)
    assert result.object.summary == prior.object.summary
    assert graph.get_revision(WORLD_ID, child).graph_payload == before
    assert (
        service.get_complete_object(
            _request(child), object_id=EXISTING_OBJECT_ID
        ).reviewed_source_observations
        == rows
    )
    for row in rows:
        anchors = [a for a in result.anchors if row.assertion_id in a.supporting_assertion_ids]
        assert anchors
        assert all(
            service.resolve_source_anchor(_request(child), anchor_id=a.anchor_id).found
            for a in anchors
        )
    assert prior.reviewed_source_observations == ()


@pytest.mark.parametrize(
    "kwargs", [{"publish": False}, {"accepted": False}, {"subject_id": "npc:other"}]
)
def test_worldbuilding_does_not_bypass_publication_acceptance_or_subject(kwargs):
    service, _, _, _, child = _fixture(observation_values=VALUES[:6], **kwargs)
    assert (
        service.get_complete_object(
            _request(child), object_id=EXISTING_OBJECT_ID
        ).reviewed_source_observations
        == ()
    )


def test_worldbuilding_scope_visibility_and_source_integrity_remain_binding():
    service, _, sources, _, child = _fixture(observation_values=VALUES[:6])
    assert (
        service.get_complete_object(
            _request(child, admissibility=Admissibility.PLAYER), object_id=EXISTING_OBJECT_ID
        ).reviewed_source_observations
        == ()
    )
    assert (
        service.get_complete_object(
            _request(child, campaign_id=None), object_id=EXISTING_OBJECT_ID
        ).reviewed_source_observations
        == ()
    )
    other = _request(child).model_copy(update={"world_id": "world:other"})
    with pytest.raises(HeadNotFoundError):
        service.get_complete_object(other, object_id=EXISTING_OBJECT_ID)
    sources._revisions.pop(SOURCE_REVISION_ID)
    result = service.get_complete_object(_request(child), object_id=EXISTING_OBJECT_ID)
    assert result.reviewed_source_observations == ()
    assert "evidence_source_revision_missing" in result.coverage.gap_codes


def test_unknown_observation_discriminator_is_not_admitted():
    service, _, _, _, child = _fixture(
        observation_values=(("invented_observation", "Not supported"),)
    )
    assert (
        service.get_complete_object(
            _request(child), object_id=EXISTING_OBJECT_ID
        ).reviewed_source_observations
        == ()
    )
