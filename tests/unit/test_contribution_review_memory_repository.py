"""In-memory contribution-review repository atomicity and reload proof."""

from __future__ import annotations

import pytest

from dungeonmind.application.contribution_review import finalize_contribution_review
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryContributionReviewRepository,
)

from .test_contribution_review_service import (
    _GraphRepository,
    _intent,
    _policy,
    _repositories,
    _submission,
)


def test_failure_after_candidate_insert_rolls_back_everything() -> None:
    intent = _intent()
    contributions = InMemoryContributionRepository()

    def fail() -> None:
        raise RuntimeError("injected")

    reviews = InMemoryContributionReviewRepository(
        contributions,
        failure_hook=fail,
    )
    with pytest.raises(RuntimeError):
        finalize_contribution_review(
            _submission(intent),
            capability_policy=_policy(intent),
            world_graph_repository=_GraphRepository(),
            review_repository=reviews,
        )
    assert contributions.list_for_world(intent.world_id) == []
    assert reviews.get_for_plan(intent.world_id, intent.plan_ref.source_plan_id) is None


def test_missing_child_on_reload_is_persistence_integrity_error() -> None:
    intent = _intent()
    reviews, contributions = _repositories()
    state = finalize_contribution_review(
        _submission(intent),
        capability_policy=_policy(intent),
        world_graph_repository=_GraphRepository(),
        review_repository=reviews,
    )
    contributions._items.pop(
        (intent.world_id, state.reviewed_contribution.contribution_id)
    )
    with pytest.raises(PersistenceIntegrityError):
        reviews.get(intent.world_id, state.record.review_id)
