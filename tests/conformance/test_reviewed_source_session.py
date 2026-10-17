"""Session reuse exercises real projection, publication admission and source closure."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from unittest.mock import Mock

import pytest

from dungeonmind.application import ReviewedSourceSessionRequest
from dungeonmind.application.world_graph_retrieval import (
    ReviewedObservationSelectionRequest,
    SourceAnchorBatchRequest,
)
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.domain.errors import PersistenceUnavailableError
from tests.conformance import test_reviewed_source_observation_retrieval as f
from tests.conformance import test_source_description_withdrawal as w


def request(pin, **changes):
    fields = dict(
        projection=f._request(pin),
        source_artifact_id=f.SOURCE_ARTIFACT_ID,
        source_revision_id=f.SOURCE_REVISION_ID,
    )
    fields.update(changes)
    return ReviewedSourceSessionRequest(**fields)


def test_one_context_history_across_overflow_partitions_and_resolution(monkeypatch):
    service, _, _, _, pin = f._fixture(count=3, text="A qualified belief. " * 40)
    ids = tuple(f.ASSERTION_ID + f":{i:02d}" for i in range(3))
    expected = [
        service.select_reviewed_source_observations(
            ReviewedObservationSelectionRequest(
                f._request(pin), f.SOURCE_ARTIFACT_ID, f.SOURCE_REVISION_ID, (key,)
            )
        )
        for key in ids
    ]
    establish = Mock(wraps=service._establish)
    reviewed = Mock(wraps=service._reviewed_source_observations)
    derive = Mock(wraps=service._source_anchor_map_in_context)
    monkeypatch.setattr(service, "_establish", establish)
    monkeypatch.setattr(service, "_reviewed_source_observations", reviewed)
    monkeypatch.setattr(service, "_source_anchor_map_in_context", derive)
    with service.reviewed_source_session(request(pin)) as session:
        overflow = session.select_observations(ids, max_bytes=256)
        assert overflow.status == "overflow" and not overflow.observations
        actual = [session.select_observations((key,)) for key in ids]
        for before, after in zip(expected, actual, strict=True):
            assert after == replace(
                before, snapshot=after.snapshot, required_bytes=after.required_bytes
            )
        anchor_ids = tuple(dict.fromkeys(a.anchor_id for row in actual for a in row.anchors))
        resolved = session.resolve_anchors(anchor_ids)
        assert all(row.found for row in resolved.resolutions)
        assert session.resolve_anchors(anchor_ids) == resolved
    assert establish.call_count == reviewed.call_count == derive.call_count == 1
    with pytest.raises(RuntimeError, match="closed"):
        session.select_observations(ids)
    with pytest.raises(RuntimeError, match="closed"):
        session.resolve_anchors(anchor_ids)


def test_nested_results_and_captured_request_are_isolated():
    service, _, _, _, pin = f._fixture()
    captured = request(pin)
    with service.reviewed_source_session(captured) as session:
        captured.projection.world_id = "world:changed-by-caller"
        first = session.select_observations((f.ASSERTION_ID,))
        anchor_id = first.anchors[0].anchor_id
        expected = session.resolve_anchors((anchor_id,))
        first.snapshot.world_id = "world:forged"
        first.anchors[0].artifact.source_artifact_id = "artifact:forged"
        expected.resolutions[0].anchor.evidence.evidence_ref_id = "evidence:forged"
        again = session.select_observations((f.ASSERTION_ID,))
        reopened = session.resolve_anchors((anchor_id,))
        assert again.snapshot.world_id == f.WORLD_ID
        assert again.anchors[0].artifact.source_artifact_id == f.SOURCE_ARTIFACT_ID
        assert reopened.resolutions[0].anchor.evidence.evidence_ref_id != "evidence:forged"


def test_source_pair_scope_and_missing_selectors_are_not_broadened():
    service, _, _, _, pin = f._fixture()
    with service.reviewed_source_session(request(pin)) as session:
        selected = session.select_observations((f.ASSERTION_ID,))
        anchor = selected.anchors[0]
        missing = session.select_observations(("missing", f.ASSERTION_ID))
        assert missing.status == "unavailable" and not missing.observations
        result = session.resolve_anchors(("missing", anchor.anchor_id))
        assert [item.found for item in result.resolutions] == [False, True]
        with pytest.raises(TypeError):
            session.select_observations((f.ASSERTION_ID,), source_artifact_id="foreign")
    with service.reviewed_source_session(request(pin, source_artifact_id="foreign")) as foreign:
        assert foreign.select_observations((f.ASSERTION_ID,)).status == "unavailable"
        assert not foreign.resolve_anchors((anchor.anchor_id,)).resolutions[0].found
    ordinary = service.resolve_source_anchors(
        SourceAnchorBatchRequest(f._request(pin), (anchor.anchor_id,))
    )
    assert ordinary.resolutions[0].found


@pytest.mark.parametrize("ids", [(), ("x", "x"), ("",), tuple(str(i) for i in range(9))])
def test_selection_bounds_are_preserved(ids):
    service, _, _, _, pin = f._fixture()
    with service.reviewed_source_session(request(pin)) as session, pytest.raises(ValueError):
        session.select_observations(ids)


@pytest.mark.parametrize("ids", [(), ("x", "x"), ("",), tuple(str(i) for i in range(129))])
def test_anchor_bounds_are_preserved(ids):
    service, _, _, _, pin = f._fixture()
    with service.reviewed_source_session(request(pin)) as session, pytest.raises(ValueError):
        session.resolve_anchors(ids)


def test_requires_exact_pin():
    with pytest.raises(ValueError, match="exact Graph revision"):
        request(" ")


@pytest.mark.parametrize("operation", ["select", "resolve"])
def test_failure_closes_session_and_resolution_emits_terminal_error(monkeypatch, operation):
    service, _, _, _, pin = f._fixture()
    observations = []
    monkeypatch.setattr(service, "_emit", observations.append)
    with service.reviewed_source_session(request(pin)) as session:

        def fail(*args, **kwargs):
            raise PersistenceUnavailableError("synthetic failure")

        target = (
            "_source_anchor_map_in_context"
            if operation == "resolve"
            else "_select_reviewed_observations_in_context"
        )
        monkeypatch.setattr(service, target, fail)
        with pytest.raises(PersistenceUnavailableError):
            if operation == "resolve":
                session.resolve_anchors(("unknown",))
            else:
                session.select_observations((f.ASSERTION_ID,))
        with pytest.raises(RuntimeError, match="closed"):
            session.select_observations((f.ASSERTION_ID,))
    if operation == "resolve":
        assert len(observations) == 1
        assert observations[0].operation == "resolve_source_anchors"
        assert observations[0].outcome == "error"
    else:
        assert not observations  # Existing selection has no terminal observer vocabulary.


def test_exception_in_wave_closes_retained_handle():
    service, _, _, _, pin = f._fixture()
    with (
        pytest.raises(RuntimeError, match="user exit"),
        service.reviewed_source_session(request(pin)) as session,
    ):
        raise RuntimeError("user exit")
    with pytest.raises(RuntimeError, match="closed"):
        session.resolve_anchors(("unknown",))


def test_concurrent_visibility_sessions_do_not_share_admission():
    service, _, _, _, pin = f._fixture()
    barrier = Barrier(2)

    def read(admissibility):
        projection = f._request(pin, admissibility=admissibility)
        with service.reviewed_source_session(request(pin, projection=projection)) as session:
            barrier.wait(timeout=5)
            return session.select_observations((f.ASSERTION_ID,))

    with ThreadPoolExecutor(max_workers=2) as pool:
        gm, player = list(pool.map(read, [Admissibility.GM, Admissibility.PLAYER]))
    assert gm.status == "complete" and player.status == "unavailable"
    assert gm.snapshot.admissibility == Admissibility.GM
    assert player.snapshot.admissibility == Admissibility.PLAYER


def test_open_historical_session_stays_historical_new_pin_sees_withdrawal(monkeypatch):
    service, graph, _, reviews, publications, prior, child = w.setup(monkeypatch)
    with service.reviewed_source_session(request(child)) as historical:
        old = historical.select_observations((w.n.NODE_ASSERTION,))
        assert old.status == "complete"
        parent = graph.get_revision(f.WORLD_ID, child)
        state = w.finalize(w.withdrawal(prior, parent), graph, reviews)
        receipt = w.publish(state, graph, reviews, publications)
        assert historical.select_observations((w.n.NODE_ASSERTION,)) == old
        with service.reviewed_source_session(request(receipt.published_revision_id)) as current:
            now = current.select_observations((w.n.NODE_ASSERTION,))
            assert now.status == "unavailable" and not now.anchors
            assert all(
                not row.found
                for row in current.resolve_anchors(
                    tuple(a.anchor_id for a in old.anchors)
                ).resolutions
            )
    with service.reviewed_source_session(request(child)) as reopened:
        result = reopened.select_observations((w.n.NODE_ASSERTION,))
        assert result == replace(
            old, snapshot=result.snapshot, required_bytes=result.required_bytes
        )
