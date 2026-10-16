"""Atomic multi-subject selection through real reviewed publication authority."""

from dataclasses import replace

import pytest

from dungeonmind.application.world_graph_retrieval import (
    ReviewedObservationSelectionRequest,
    _selection_wire_value,
)
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.domain.canonical import canonical_json
from dungeonmind.domain.errors import HeadNotFoundError
from tests.conformance import test_reviewed_source_observation_retrieval as f
from tests.conformance import test_source_description_withdrawal as w


def request(pin, ids=(f.ASSERTION_ID,), **updates):
    fields = dict(
        projection=f._request(pin),
        source_artifact_id=f.SOURCE_ARTIFACT_ID,
        source_revision_id=f.SOURCE_REVISION_ID,
        assertion_ids=ids,
    )
    fields.update(updates)
    return ReviewedObservationSelectionRequest(**fields)


def test_complete_exact_selection_has_full_qualifications_and_only_own_anchors(monkeypatch):
    text = "A source-qualified belief. " * 40
    service, graph, _, _, pin = f._fixture(
        text=text, count=3, authored_summary="Unrelated authored summary"
    )
    before = graph.get_revision(f.WORLD_ID, pin)
    establish = service._projection.open_read_context
    calls = []

    def counted(projection):
        calls.append(projection)
        return establish(projection)

    monkeypatch.setattr(service._projection, "open_read_context", counted)
    ids = (f.ASSERTION_ID + ":02", f.ASSERTION_ID + ":00")
    result = service.select_reviewed_source_observations(request(pin, ids))
    assert len(calls) == 1 and result.status == "complete"
    assert result.requested_assertion_ids == tuple(sorted(ids))
    assert tuple(o.assertion_id for o in result.observations) == tuple(sorted(ids))
    assert all(
        o.text == text and len(o.text) > 240 and o.epistemic_kind for o in result.observations
    )
    assert len(result.subjects) == 1
    assert result.subjects[0].subject_object_id == f.EXISTING_OBJECT_ID
    for observation in result.observations:
        for evidence in observation.evidence_ref_ids:
            assert any(
                a.evidence_ref_id == evidence
                and observation.assertion_id in a.supporting_assertion_ids
                for a in result.anchors
            )
    assert all(not a.supporting_relationship_ids for a in result.anchors)
    assert all(set(a.supporting_assertion_ids).issubset(ids) for a in result.anchors)
    assert result.required_bytes == len(
        canonical_json(_selection_wire_value(result)).encode("utf-8")
    )
    assert result.required_bytes <= result.max_bytes
    again = service.select_reviewed_source_observations(request(pin, tuple(reversed(ids))))
    assert again == replace(result, snapshot=again.snapshot, required_bytes=again.required_bytes)
    assert graph.get_revision(f.WORLD_ID, pin) == before


def test_multiple_distinct_subjects_and_disjoint_support_are_preserved(monkeypatch):
    original = f._candidate_with_observation

    def candidate(**kwargs):
        value, verdicts = original(**kwargs)
        raw = value.model_dump(mode="json")
        row = next(a for a in raw["assertions"] if a["assertion_id"].endswith(":01"))
        row["subject_object_id"] = "npc:new_npc"
        row["evidence_refs"][0]["evidence_ref_id"] += ":second"
        return f.GraphContributionV2.model_validate(raw), verdicts

    monkeypatch.setattr(f, "_candidate_with_observation", candidate)
    service, _, _, _, pin = f._fixture(count=2)
    result = service.select_reviewed_source_observations(
        request(pin, (f.ASSERTION_ID + ":00", f.ASSERTION_ID + ":01"))
    )
    assert result.status == "complete"
    assert {s.subject_object_id for s in result.subjects} == {f.EXISTING_OBJECT_ID, "npc:new_npc"}
    assert len({o.evidence_ref_ids for o in result.observations}) == 2
    assert len(result.anchors) == 2
    for anchor in result.anchors:
        assert len(anchor.supporting_assertion_ids) == 1


@pytest.mark.parametrize(
    "updates",
    [
        {"source_artifact_id": "foreign"},
        {"source_revision_id": "foreign"},
        {"assertion_ids": (f.ASSERTION_ID, "not-admitted")},
    ],
)
def test_foreign_or_missing_selection_is_atomic(updates):
    service, _, _, _, pin = f._fixture()
    result = service.select_reviewed_source_observations(request(pin, **updates))
    assert result.status == "unavailable" and result.unavailable_assertion_ids
    assert not result.observations and not result.anchors and not result.subjects


def test_aggregate_overflow_is_distinct_and_never_truncates_records():
    service, _, _, _, pin = f._fixture(text="Full description. " * 100, count=2)
    ids = (f.ASSERTION_ID + ":00", f.ASSERTION_ID + ":01")
    full = service.select_reviewed_source_observations(request(pin, ids))
    assert full.status == "complete"
    overflow = service.select_reviewed_source_observations(
        request(pin, ids, max_bytes=full.required_bytes - 100)
    )
    assert overflow.status == "overflow" and overflow.required_bytes > overflow.max_bytes
    assert not overflow.observations and not overflow.anchors and not overflow.subjects
    assert not overflow.unavailable_assertion_ids


def test_visibility_foreign_world_and_unpublished_are_not_admitted():
    service, _, _, _, pin = f._fixture()
    result = service.select_reviewed_source_observations(
        request(pin, projection=f._request(pin, admissibility=Admissibility.PLAYER))
    )
    assert result.status == "unavailable"
    with pytest.raises(HeadNotFoundError):
        service.select_reviewed_source_observations(
            request(pin, projection=f._request(pin).model_copy(update={"world_id": "foreign"}))
        )
    service, _, _, _, pin = f._fixture(publish=False)
    assert service.select_reviewed_source_observations(request(pin)).status == "unavailable"


def test_withdrawn_description_rejects_now_but_historical_selection_remains(monkeypatch):
    service, graph, _, reviews, publications, prior, child = w.setup(monkeypatch)
    old = service.select_reviewed_source_observations(request(child, (w.n.NODE_ASSERTION,)))
    assert old.status == "complete"
    parent = graph.get_revision(f.WORLD_ID, child)
    state = w.finalize(w.withdrawal(prior, parent), graph, reviews)
    receipt = w.publish(state, graph, reviews, publications)
    now = service.select_reviewed_source_observations(
        request(receipt.published_revision_id, (w.n.NODE_ASSERTION,))
    )
    assert now.status == "unavailable" and not now.anchors
    historical = service.select_reviewed_source_observations(request(child, (w.n.NODE_ASSERTION,)))
    assert historical == replace(
        old, snapshot=historical.snapshot, required_bytes=historical.required_bytes
    )
    for anchor in historical.anchors:
        assert service.resolve_source_anchor(f._request(child), anchor_id=anchor.anchor_id).found


@pytest.mark.parametrize(
    "updates",
    [
        {"assertion_ids": ()},
        {"assertion_ids": ("a",) * 2},
        {"assertion_ids": tuple(str(i) for i in range(9))},
        {"assertion_ids": ["a"]},
        {"assertion_ids": (" a",)},
        {"assertion_ids": (False,)},
        {"max_bytes": True},
        {"max_bytes": 255},
        {"max_bytes": 262145},
        {"source_revision_id": " x"},
        {"source_artifact_id": ""},
        {"projection": f._request("pin").model_copy(update={"revision_pin": None})},
    ],
)
def test_invalid_request_rejects_before_any_service_read(updates):
    with pytest.raises(ValueError):
        request("pin", **updates)


def test_missing_publication_ports_are_not_an_empty_success():
    service, _, _, _, pin = f._fixture()
    service._world_graph = None
    with pytest.raises(ValueError, match="publication authority"):
        service.select_reviewed_source_observations(request(pin))


def test_eight_individually_bounded_records_can_overflow_only_as_a_union():
    service, _, _, _, pin = f._fixture(text="灯" * 2000, count=8)
    ids = tuple(f.ASSERTION_ID + f":{i:02d}" for i in range(8))
    for value in ids:
        single = service.select_reviewed_source_observations(
            request(pin, (value,), max_bytes=24000)
        )
        assert single.status == "complete"
    combined = service.select_reviewed_source_observations(request(pin, ids, max_bytes=24000))
    assert combined.status == "overflow" and combined.required_bytes > 24000
    assert not combined.observations and not combined.anchors


def test_campaign_bound_selection_matches_complete_object_under_each_scope():
    service, _, _, _, pin = f._fixture()
    campaign = f._request(pin)
    world = f._request(pin, campaign_id=None)
    cross = world.model_copy(update={"scope_mode": f.ScopeModeV2.WORLD_CROSS_CAMPAIGN})
    for projection in (campaign, world, cross):
        complete = service.get_complete_object(projection, object_id=f.EXISTING_OBJECT_ID)
        selected = service.select_reviewed_source_observations(request(pin, projection=projection))
        expected = any(
            o.assertion_id == f.ASSERTION_ID for o in complete.reviewed_source_observations
        )
        assert (selected.status == "complete") == expected
    assert (
        service.select_reviewed_source_observations(request(pin, projection=world)).status
        == "unavailable"
    )
    assert (
        service.select_reviewed_source_observations(request(pin, projection=cross)).status
        == "complete"
    )


def test_unresolved_published_correction_is_unavailable_without_losing_history(monkeypatch):
    original = f._fixture
    checked = []

    def fixture(**kwargs):
        service, *rest = original(**kwargs)
        complete = service.get_complete_object

        def check(projection, *, object_id):
            result = complete(projection, object_id=object_id)
            selected = service.select_reviewed_source_observations(
                request(projection.revision_pin, projection=projection)
            )
            expected = any(
                o.assertion_id == f.ASSERTION_ID for o in result.reviewed_source_observations
            )
            assert (selected.status == "complete") == expected
            checked.append(expected)
            return result

        monkeypatch.setattr(service, "get_complete_object", check)
        return service, *rest

    monkeypatch.setattr(f, "_fixture", fixture)
    f.test_later_published_correction_marks_observation_unresolved(monkeypatch)
    assert checked == [False, True]
