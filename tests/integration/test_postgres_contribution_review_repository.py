"""PostgreSQL atomic/reload proof for finalized contribution reviews."""

from __future__ import annotations

import pytest

from dungeonmind.application.contribution_review import finalize_contribution_review
from dungeonmind.contracts.graph import PublishRevisionCommand
from tests.unit.test_contribution_review_service import (
    _intent,
    _policy,
    _submission,
)
from tests.unit.test_dnd_threat_contribution_planning import _stored_revision


def _publish_fixture_revision(pg) -> None:
    stored = _stored_revision()
    envelope = stored.revision
    pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=envelope.world_id,
            parent_revision_id=envelope.parent_revision_id,
            expected_parent_revision_id=envelope.parent_revision_id,
            operation_ids=envelope.operation_ids,
            graph_schema=envelope.graph_schema,
            graph_payload=stored.graph_payload,
            created_at=envelope.created_at,
        )
    )


@pytest.mark.integration
def test_postgres_review_finalize_reload_and_replay(pg) -> None:
    intent = _intent()
    _publish_fixture_revision(pg)
    submission = _submission(intent)
    state = finalize_contribution_review(
        submission,
        capability_policy=_policy(intent),
        world_graph_repository=pg.world_graph,
        review_repository=pg.contribution_reviews,
    )
    assert pg.contribution_reviews.get(intent.world_id, state.record.review_id) == state
    assert (
        pg.contribution_reviews.get_for_plan(
            intent.world_id, intent.plan_ref.source_plan_id
        )
        == state
    )
    assert pg.contributions.get(
        intent.world_id, state.candidate_contribution.contribution_id
    ).status.value == "superseded"
    assert pg.contributions.get(
        intent.world_id, state.reviewed_contribution.contribution_id
    ).status.value == "active"
    assert (
        finalize_contribution_review(
            submission,
            capability_policy=_policy(intent),
            world_graph_repository=pg.world_graph,
            review_repository=pg.contribution_reviews,
        )
        == state
    )
