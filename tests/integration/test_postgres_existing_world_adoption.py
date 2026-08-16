"""PostgreSQL owning-boundary proofs for existing-world adoption."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

import pytest

from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    ExistingWorldAdoptionOutcomeUnknownError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
)
from dungeonmind.domain.revision_ids import compute_revision_id
from tests.unit.test_existing_world_adoption import (
    ADOPTION_ID,
    ART_A,
    ART_B,
    LATER,
    NOW,
    REV_A,
    REV_B,
    WORLD_ID,
    bundle_bytes,
    graph_reader,
    make_bundle,
    make_command,
    make_isolated_bundle,
)

pytestmark = pytest.mark.integration


def _counts(pg, world_id: str = WORLD_ID) -> dict[str, int]:
    queries = {
        "heads": (
            "SELECT COUNT(*) AS count FROM dungeonmind.world_graph_heads WHERE world_id = %s"
        ),
        "revisions": (
            "SELECT COUNT(*) AS count FROM dungeonmind.graph_revisions WHERE world_id = %s"
        ),
        "head_events": (
            "SELECT COUNT(*) AS count FROM dungeonmind.world_graph_head_events WHERE world_id = %s"
        ),
        "contributions": (
            "SELECT COUNT(*) AS count FROM dungeonmind.graph_contributions WHERE world_id = %s"
        ),
        "identity": (
            "SELECT COUNT(*) AS count FROM dungeonmind.identity_decisions WHERE world_id = %s"
        ),
        "artifacts": (
            "SELECT COUNT(*) AS count FROM dungeonmind.source_artifacts WHERE world_id = %s"
        ),
        "receipts": (
            "SELECT COUNT(*) AS count FROM dungeonmind.existing_world_adoptions WHERE world_id = %s"
        ),
    }
    counts: dict[str, int] = {}
    with pg.database.connect() as conn:
        for name, query in queries.items():
            row = conn.execute(query, (world_id,)).fetchone()
            counts[name] = int(row["count"])
        rev_row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM dungeonmind.source_revisions
            WHERE source_artifact_id IN (
                SELECT source_artifact_id FROM dungeonmind.source_artifacts WHERE world_id = %s
            )
            """,
            (world_id,),
        ).fetchone()
        counts["revisions_source"] = int(rev_row["count"])
    return counts


def _adopt(pg, raw: bytes | None = None, *, adopted_at: datetime = NOW):
    return adopt_existing_world(
        raw if raw is not None else bundle_bytes(),
        adopted_at=adopted_at,
        adoption_repository=pg.existing_world_adoptions,
        graph_reader=graph_reader(),
    )


@pytest.mark.integration
def test_t22_migration_and_constraints(pg) -> None:
    with pg.database.connect() as conn:
        columns = {
            row["column_name"]
            for row in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'dungeonmind'
                  AND table_name = 'existing_world_adoptions'
                """
            ).fetchall()
        }
        assert {
            "world_id",
            "adoption_id",
            "bundle_sha256",
            "published_revision_id",
            "graph_schema",
            "graph_payload_sha256",
            "adopted_at",
            "source_artifact_count",
            "source_revision_count",
            "contribution_count",
            "identity_decision_count",
            "schema_version",
            "record_fingerprint",
            "payload",
        } <= columns
        constraints = {
            row["constraint_type"]
            for row in conn.execute(
                """
                SELECT constraint_type
                FROM information_schema.table_constraints
                WHERE table_schema = 'dungeonmind'
                  AND table_name = 'existing_world_adoptions'
                """
            ).fetchall()
        }
        assert "PRIMARY KEY" in constraints
        assert "FOREIGN KEY" in constraints
        assert "UNIQUE" in constraints


@pytest.mark.integration
def test_t23_postgres_adopts_all_families(pg) -> None:
    receipt = _adopt(pg)
    counts = _counts(pg)
    assert counts["receipts"] == 1
    assert counts["heads"] == 1
    assert counts["revisions"] == 1
    assert counts["head_events"] == 1
    assert counts["contributions"] == 2
    assert counts["identity"] == 2
    assert counts["artifacts"] == 2
    assert counts["revisions_source"] == 2
    assert receipt.adoption_id == ADOPTION_ID
    assert pg.world_graph.get_head(WORLD_ID).head_revision_id == receipt.published_revision_id


@pytest.mark.integration
def test_t24_graph_helper_owns_revision_identity(pg) -> None:
    receipt = _adopt(pg)
    stored = pg.world_graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert stored is not None
    expected = compute_revision_id(
        world_id=WORLD_ID,
        parent_revision_id=None,
        operation_ids=[ADOPTION_ID],
        graph_schema=stored.revision.graph_schema,
        graph_payload_sha256=canonical_sha256(stored.graph_payload),
    )
    assert stored.revision.revision_id == expected
    assert stored.revision.revision_id == receipt.published_revision_id
    assert stored.revision.parent_revision_id is None
    assert stored.revision.operation_ids == [ADOPTION_ID]


@pytest.mark.integration
@pytest.mark.parametrize("stage", ["source_history", "graph"])
def test_t28_t29_rollback_leaves_zero_adoption_rows(
    migrated_database: str,
    pg,
    stage: str,
) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresExistingWorldAdoptionRepository,
    )

    def hook(current: str) -> None:
        if current == stage:
            raise RuntimeError(f"injected {stage} abort")

    repository = PostgresExistingWorldAdoptionRepository(
        PostgresDatabase(migrated_database),
        failure_hook=hook,
    )
    with pytest.raises(ExistingWorldAdoptionOutcomeUnknownError):
        adopt_existing_world(
            bundle_bytes(),
            adopted_at=NOW,
            adoption_repository=repository,
            graph_reader=graph_reader(),
        )
    counts = _counts(pg)
    assert counts == {
        "heads": 0,
        "revisions": 0,
        "head_events": 0,
        "contributions": 0,
        "identity": 0,
        "artifacts": 0,
        "receipts": 0,
        "revisions_source": 0,
    }


@pytest.mark.integration
def test_t30_same_bundle_race_converges(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresRepositoryBundle,
    )

    raw = bundle_bytes()
    bundle_a = PostgresRepositoryBundle(PostgresDatabase(migrated_database))
    bundle_b = PostgresRepositoryBundle(PostgresDatabase(migrated_database))
    barrier = threading.Barrier(2)
    successes: list[Any] = []
    errors: list[BaseException] = []

    def call(bundle: Any) -> None:
        try:
            barrier.wait(timeout=5)
            successes.append(
                adopt_existing_world(
                    raw,
                    adopted_at=NOW,
                    adoption_repository=bundle.existing_world_adoptions,
                    graph_reader=graph_reader(),
                )
            )
        except BaseException as exc:
            errors.append(exc)

    first = threading.Thread(target=call, args=(bundle_a,))
    second = threading.Thread(target=call, args=(bundle_b,))
    first.start()
    second.start()
    first.join(timeout=30)
    second.join(timeout=30)
    assert not first.is_alive() and not second.is_alive()
    assert errors == []
    assert len(successes) == 2
    assert successes[0] == successes[1]
    assert _counts(pg)["receipts"] == 1
    assert _counts(pg)["revisions"] == 1
    assert _counts(pg)["contributions"] == 2


@pytest.mark.integration
def test_t31_different_bundle_race_one_winner(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresRepositoryBundle,
    )

    first_raw = bundle_bytes()
    other = make_bundle(adoption_id="adopt:contender")
    other = other.model_copy(
        update={
            "source_provenance": other.source_provenance.model_copy(
                update={"producer_revision": "rev:contender"}
            )
        }
    )
    second_raw = bundle_bytes(other)
    bundle_a = PostgresRepositoryBundle(PostgresDatabase(migrated_database))
    bundle_b = PostgresRepositoryBundle(PostgresDatabase(migrated_database))
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def call(bundle: Any, raw: bytes) -> None:
        barrier.wait(timeout=5)
        try:
            adopt_existing_world(
                raw,
                adopted_at=NOW,
                adoption_repository=bundle.existing_world_adoptions,
                graph_reader=graph_reader(),
            )
            outcomes.append("won")
        except (IdempotencyConflictError, PersistenceIntegrityError):
            outcomes.append("refused")

    first = threading.Thread(target=call, args=(bundle_a, first_raw))
    second = threading.Thread(target=call, args=(bundle_b, second_raw))
    first.start()
    second.start()
    first.join(timeout=30)
    second.join(timeout=30)
    assert not first.is_alive() and not second.is_alive()
    assert sorted(outcomes) == ["refused", "won"]
    counts = _counts(pg)
    assert counts["receipts"] == 1
    assert counts["revisions"] == 1
    assert counts["contributions"] == 2
    assert counts["artifacts"] == 2


@pytest.mark.integration
def test_t32_reconstruct_through_normal_repositories(pg) -> None:
    receipt = _adopt(pg)
    stored = pg.world_graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert stored is not None
    assert stored.revision.graph_schema == receipt.graph_schema
    assert canonical_sha256(stored.graph_payload) == receipt.graph_payload_sha256
    assert pg.sources.get_artifact(ART_A) is not None
    assert pg.sources.get_revision(REV_A) is not None
    assert pg.sources.get_artifact(ART_B) is not None
    assert pg.sources.get_revision(REV_B) is not None
    assert pg.contributions.get(WORLD_ID, "contrib:import-1") is not None
    assert pg.contributions.get(WORLD_ID, "contrib:import-2") is not None
    assert pg.identity_decisions.get(WORLD_ID, "iddec:alias-add") is not None
    assert pg.identity_decisions.get(WORLD_ID, "iddec:alias-remove") is not None
    loaded = pg.existing_world_adoptions.get(WORLD_ID, ADOPTION_ID)
    assert loaded == receipt
    assert pg.existing_world_adoptions.get_for_world(WORLD_ID) == receipt


@pytest.mark.integration
@pytest.mark.parametrize("later_state", ["descendant", "rollback"])
def test_t33_receipt_survives_descendant_or_rollback(pg, later_state: str) -> None:
    original = _adopt(pg)
    parent = pg.world_graph.get_revision(WORLD_ID, original.published_revision_id)
    assert parent is not None
    pg.world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=original.published_revision_id,
            expected_parent_revision_id=original.published_revision_id,
            operation_ids=["op:descendant"],
            graph_schema=parent.revision.graph_schema,
            graph_payload=parent.graph_payload,
            created_at=LATER,
        )
    )
    if later_state == "rollback":
        pg.world_graph.rollback_head(
            WORLD_ID,
            original.published_revision_id,
            updated_at=LATER,
        )
        assert pg.world_graph.get_head(WORLD_ID).head_revision_id == original.published_revision_id
    else:
        assert pg.world_graph.get_head(WORLD_ID).head_revision_id != original.published_revision_id
    loaded = pg.existing_world_adoptions.get_for_world(WORLD_ID)
    assert loaded == original
    replayed = adopt_existing_world(
        bundle_bytes(),
        adopted_at=LATER,
        adoption_repository=pg.existing_world_adoptions,
        graph_reader=graph_reader(),
    )
    assert replayed == original
    assert replayed.adopted_at == NOW
    assert _counts(pg)["receipts"] == 1
    assert _counts(pg)["revisions"] == 2


@pytest.mark.integration
def test_direct_port_refuses_spoofed_bundle_sha_on_replay(pg) -> None:
    first = pg.existing_world_adoptions.adopt(make_command())
    other = make_isolated_bundle(
        world_id=WORLD_ID,
        adoption_id="adopt:spoofed-bundle",
        token="spoof",
    )
    spoofed = make_command(other, bundle_sha256=first.bundle_sha256)
    with pytest.raises(PersistenceIntegrityError) as exc:
        pg.existing_world_adoptions.adopt(spoofed)
    assert exc.value.details["reason"] == "unbound_bundle_sha256"
    assert pg.existing_world_adoptions.get_for_world(WORLD_ID) == first
    counts = _counts(pg)
    assert counts["receipts"] == 1
    assert counts["revisions"] == 1


@pytest.mark.integration
def test_direct_port_refuses_unbound_bundle_sha_on_fresh_adopt(pg) -> None:
    command = make_command(bundle_sha256="ab" * 32)
    with pytest.raises(PersistenceIntegrityError) as exc:
        pg.existing_world_adoptions.adopt(command)
    assert exc.value.details["reason"] == "unbound_bundle_sha256"
    assert pg.existing_world_adoptions.get_for_world(WORLD_ID) is None
    assert _counts(pg)["receipts"] == 0
    assert _counts(pg)["revisions"] == 0


@pytest.mark.integration
def test_cross_world_adoption_id_is_idempotency_conflict(pg) -> None:
    first = _adopt(pg)
    other = make_isolated_bundle(
        world_id="world:existing-adoption-other",
        adoption_id=ADOPTION_ID,
        token="other",
    )
    with pytest.raises(IdempotencyConflictError):
        adopt_existing_world(
            bundle_bytes(other),
            adopted_at=NOW,
            adoption_repository=pg.existing_world_adoptions,
            graph_reader=graph_reader(),
        )
    with pytest.raises(IdempotencyConflictError):
        adopt_existing_world(
            bundle_bytes(other),
            adopted_at=NOW,
            adoption_repository=pg.existing_world_adoptions,
            graph_reader=graph_reader(),
        )
    assert pg.existing_world_adoptions.get_for_world(WORLD_ID) == first
    assert pg.existing_world_adoptions.get_for_world(other.world_id) is None
    assert _counts(pg)["receipts"] == 1
    assert _counts(pg, other.world_id)["receipts"] == 0


@pytest.mark.integration
def test_cross_world_adoption_id_race_one_winner(migrated_database: str, pg) -> None:
    from dungeonmind.infrastructure.postgres import (
        PostgresDatabase,
        PostgresRepositoryBundle,
    )

    shared_adoption_id = "adopt:shared-cross-world"
    first_bundle = make_isolated_bundle(
        world_id="world:adopt-race-a",
        adoption_id=shared_adoption_id,
        token="race-a",
    )
    second_bundle = make_isolated_bundle(
        world_id="world:adopt-race-b",
        adoption_id=shared_adoption_id,
        token="race-b",
    )
    bundle_a = PostgresRepositoryBundle(PostgresDatabase(migrated_database))
    bundle_b = PostgresRepositoryBundle(PostgresDatabase(migrated_database))
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    errors: list[BaseException] = []

    def call(store: Any, raw: bytes) -> None:
        barrier.wait(timeout=5)
        try:
            adopt_existing_world(
                raw,
                adopted_at=NOW,
                adoption_repository=store.existing_world_adoptions,
                graph_reader=graph_reader(),
            )
            outcomes.append("won")
        except IdempotencyConflictError:
            outcomes.append("refused")
        except BaseException as exc:
            errors.append(exc)

    first = threading.Thread(target=call, args=(bundle_a, bundle_bytes(first_bundle)))
    second = threading.Thread(target=call, args=(bundle_b, bundle_bytes(second_bundle)))
    first.start()
    second.start()
    first.join(timeout=30)
    second.join(timeout=30)
    assert not first.is_alive() and not second.is_alive()
    assert errors == []
    assert sorted(outcomes) == ["refused", "won"]
    winner_a = pg.existing_world_adoptions.get_for_world(first_bundle.world_id)
    winner_b = pg.existing_world_adoptions.get_for_world(second_bundle.world_id)
    assert (winner_a is None) != (winner_b is None)
    assert (
        _counts(pg, first_bundle.world_id)["receipts"]
        + _counts(pg, second_bundle.world_id)["receipts"]
        == 1
    )
