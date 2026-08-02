"""PostgreSQL atomic/reload proof for finalized contribution reviews."""

from __future__ import annotations

import pytest

from dungeonmind.application.contribution_review import finalize_contribution_review
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.domain.errors import (
    ContributionReviewAlreadyFinalizedError,
    IdempotencyConflictError,
    InvalidLifecycleTransitionError,
    PersistenceIntegrityError,
)
from dungeonmind.infrastructure.postgres.database import jsonb
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


def _bundle_counts(pg, world_id: str) -> tuple[int, int, int, str | None]:
    with pg.database.connect() as conn:
        contributions = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM dungeonmind.graph_contributions
            WHERE world_id = %s
            """,
            (world_id,),
        ).fetchone()["n"]
        reviews = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM dungeonmind.contribution_reviews
            WHERE world_id = %s
            """,
            (world_id,),
        ).fetchone()["n"]
        revisions = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM dungeonmind.graph_revisions
            WHERE world_id = %s
            """,
            (world_id,),
        ).fetchone()["n"]
        head = conn.execute(
            """
            SELECT head_revision_id
            FROM dungeonmind.world_graph_heads
            WHERE world_id = %s
            """,
            (world_id,),
        ).fetchone()
    return contributions, reviews, revisions, None if head is None else head["head_revision_id"]


def _install_failure_trigger(
    pg, table: str, *, source_kind: str | None = None
) -> None:
    condition = (
        f"IF NEW.source_kind = '{source_kind}' THEN"
        if source_kind is not None
        else "IF TRUE THEN"
    )
    with pg.database.connect() as conn:
        conn.execute(
            f"""
            CREATE OR REPLACE FUNCTION dungeonmind.b2e_fail_review_write()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
            {condition}
                    RAISE EXCEPTION 'B.2e injected PostgreSQL failure';
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
        conn.execute(
            f"DROP TRIGGER IF EXISTS b2e_fail_review_write ON dungeonmind.{table}"
        )
        conn.execute(
            f"""
            CREATE TRIGGER b2e_fail_review_write
            AFTER INSERT ON dungeonmind.{table}
            FOR EACH ROW EXECUTE FUNCTION dungeonmind.b2e_fail_review_write()
            """
        )


def _remove_failure_trigger(pg, table: str) -> None:
    with pg.database.connect() as conn:
        conn.execute(
            f"DROP TRIGGER IF EXISTS b2e_fail_review_write ON dungeonmind.{table}"
        )
        conn.execute("DROP FUNCTION IF EXISTS dungeonmind.b2e_fail_review_write()")


@pytest.mark.integration
def test_postgres_review_finalize_reload_and_replay(pg) -> None:
    intent = _intent()
    _publish_fixture_revision(pg)
    submission = _submission(intent)
    before = _bundle_counts(pg, intent.world_id)
    state = finalize_contribution_review(
        submission,
        capability_policy=_policy(intent),
        world_graph_repository=pg.world_graph,
        review_repository=pg.contribution_reviews,
    )
    after = _bundle_counts(pg, intent.world_id)
    assert before[2:] == after[2:]
    assert before[3] == after[3]
    with pg.database.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM dungeonmind.identity_decisions WHERE world_id = %s",
            (intent.world_id,),
        ).fetchone()["n"] == 0
    assert pg.contribution_reviews.get(intent.world_id, state.record.review_id) == state
    assert (
        pg.contribution_reviews.get_for_plan(
            intent.world_id, intent.plan_ref.source_plan_id
        )
        == state
    )
    for contribution_id, status in (
        (state.candidate_contribution.contribution_id, "active"),
        (state.reviewed_contribution.contribution_id, "retracted"),
    ):
        with pytest.raises(InvalidLifecycleTransitionError):
            pg.contributions.update_status(
                intent.world_id,
                contribution_id,
                type(state.candidate_contribution.status)(status),
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


@pytest.mark.integration
def test_postgres_review_conflicts_are_typed(pg) -> None:
    intent = _intent()
    _publish_fixture_revision(pg)
    submission = _submission(intent)
    state = finalize_contribution_review(
        submission,
        capability_policy=_policy(intent),
        world_graph_repository=pg.world_graph,
        review_repository=pg.contribution_reviews,
    )

    changed_operation_intent = _intent(
        reviewer_id="operator:changed-reviewer",
    )
    with pytest.raises(IdempotencyConflictError):
        finalize_contribution_review(
            _submission(changed_operation_intent),
            capability_policy=_policy(changed_operation_intent),
            world_graph_repository=pg.world_graph,
            review_repository=pg.contribution_reviews,
        )

    second_operation_intent = _intent(operation_id="reviewop:" + "2" * 32)
    with pytest.raises(ContributionReviewAlreadyFinalizedError):
        finalize_contribution_review(
            _submission(second_operation_intent),
            capability_policy=_policy(second_operation_intent),
            world_graph_repository=pg.world_graph,
            review_repository=pg.contribution_reviews,
        )
    assert pg.contribution_reviews.get(intent.world_id, state.record.review_id) == state


@pytest.mark.integration
@pytest.mark.parametrize(
    ("table", "source_kind"),
    [
        ("graph_contributions", "extraction"),
        ("graph_contributions", "graph_review"),
        ("contribution_reviews", None),
    ],
)
def test_postgres_review_failure_rolls_back_all_children(
    pg, table: str, source_kind: str | None
) -> None:
    intent = _intent()
    _publish_fixture_revision(pg)
    before = _bundle_counts(pg, intent.world_id)
    _install_failure_trigger(
        pg,
        table,
        source_kind=source_kind,
    )
    try:
        with pytest.raises(PersistenceIntegrityError):
            finalize_contribution_review(
                _submission(intent),
                capability_policy=_policy(intent),
                world_graph_repository=pg.world_graph,
                review_repository=pg.contribution_reviews,
            )
    finally:
        _remove_failure_trigger(pg, table)
    assert _bundle_counts(pg, intent.world_id) == before
    assert pg.contribution_reviews.get_for_plan(
        intent.world_id, intent.plan_ref.source_plan_id
    ) is None


@pytest.mark.integration
def test_postgres_review_reload_detects_record_and_child_corruption(pg) -> None:
    intent = _intent()
    _publish_fixture_revision(pg)
    state = finalize_contribution_review(
        _submission(intent),
        capability_policy=_policy(intent),
        world_graph_repository=pg.world_graph,
        review_repository=pg.contribution_reviews,
    )
    with pg.database.connect() as conn:
        conn.execute(
            """
            UPDATE dungeonmind.contribution_reviews
            SET payload = jsonb_set(
                payload,
                '{identity_verdicts,0,target_object_id}',
                '"obj:tampered"'
            )
            WHERE world_id = %s AND review_id = %s
            """,
            (intent.world_id, state.record.review_id),
        )
    with pytest.raises(PersistenceIntegrityError):
        pg.contribution_reviews.get(intent.world_id, state.record.review_id)

    # Restore the review row through a clean fixture write, then corrupt a child.
    with pg.database.connect() as conn:
        conn.execute(
            """
            UPDATE dungeonmind.contribution_reviews
            SET payload = %s
            WHERE world_id = %s AND review_id = %s
            """,
            (
                jsonb(state.record.model_dump(mode="json")),
                intent.world_id,
                state.record.review_id,
            ),
        )
        conn.execute(
            """
            UPDATE dungeonmind.graph_contributions
            SET status = 'retracted'
            WHERE world_id = %s AND contribution_id = %s
            """,
            (intent.world_id, state.reviewed_contribution.contribution_id),
        )
    with pytest.raises(PersistenceIntegrityError):
        pg.contribution_reviews.get(intent.world_id, state.record.review_id)
