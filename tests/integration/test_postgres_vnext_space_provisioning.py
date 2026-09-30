"""PostgreSQL race and rollback proof for MIND-owned empty-space provisioning."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from dungeonmind.application.vnext import (
    KnowledgeSpaceProvisioningConflictError,
    create_empty_space,
    initialize_empty_knowledge_space,
)
from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    SemanticProfileDescriptorV2,
)
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres.database import PostgresDatabase
from dungeonmind.infrastructure.postgres.vnext_knowledge import (
    PostgresKnowledgeRevisionRepository,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _repo(database_url: str, **kwargs) -> PostgresKnowledgeRevisionRepository:
    return PostgresKnowledgeRevisionRepository(PostgresDatabase(database_url), **kwargs)


def _domain() -> DomainContractDescriptor:
    return DomainContractDescriptor(
        domain_id="test.space-provisioning",
        domain_revision="1",
        admission_policy_id="test.space-provisioning.always",
    )


def _profile(revision: str = "1") -> SemanticProfileDescriptorV2:
    return SemanticProfileDescriptorV2(
        profile_id="test.space-provisioning.profile",
        profile_revision=revision,
        term_namespaces=["test"],
    )


def _create(database_url: str, allocation_id: str, *, repo=None, profile=None):
    return create_empty_space(
        repository=repo or _repo(database_url),
        allocation_id=allocation_id,
        created_at=NOW,
        domain_contract=_domain(),
        semantic_profile=profile or _profile(),
    )


def _counts(database_url: str, allocation_id: str, space_id: str) -> tuple[int, ...]:
    with PostgresDatabase(database_url).connect() as conn:
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM dungeonmind.knowledge_space_provisioning_receipts
                    WHERE allocation_id = %s) AS allocations,
                (SELECT COUNT(*) FROM dungeonmind.knowledge_spaces
                    WHERE space_id = %s) AS spaces,
                (SELECT COUNT(*) FROM dungeonmind.knowledge_revisions
                    WHERE space_id = %s) AS revisions,
                (SELECT COUNT(*) FROM dungeonmind.knowledge_heads
                    WHERE space_id = %s) AS heads,
                (SELECT COUNT(*) FROM dungeonmind.knowledge_head_events
                    WHERE space_id = %s) AS events,
                (SELECT COUNT(*) FROM dungeonmind.knowledge_publication_receipts
                    WHERE space_id = %s) AS publications
            """,
            (allocation_id, space_id, space_id, space_id, space_id, space_id),
        ).fetchone()
    assert row is not None
    return tuple(int(row[key]) for key in (
        "allocations", "spaces", "revisions", "heads", "events", "publications"
    ))


def _assert_empty_genesis(database_url: str, receipt) -> None:
    stored = _repo(database_url).get_revision(
        receipt.space_id, receipt.publication_receipt.published_revision_id
    )
    assert stored is not None
    assert stored.graph_payload == {
        "entities": [],
        "assertions": [],
        "aliases": [],
        "evidence": [],
    }
    with PostgresDatabase(database_url).connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM dungeonmind.knowledge_native_source_admissions
            WHERE space_id = %s
            """,
            (receipt.space_id,),
        ).fetchone()
    assert row is not None and int(row["n"]) == 0


def test_same_key_concurrent_replay_returns_one_space_and_one_genesis(
    migrated_database: str, pg
) -> None:
    del pg
    workers = 8
    barrier = threading.Barrier(workers)

    def provision(_index: int):
        barrier.wait(timeout=10)
        return _create(migrated_database, "allocation:pg-concurrent-same-key")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        receipts = list(pool.map(provision, range(workers)))

    assert all(item == receipts[0] for item in receipts)
    assert _counts(
        migrated_database, "allocation:pg-concurrent-same-key", receipts[0].space_id
    ) == (1, 1, 1, 1, 1, 1)
    _assert_empty_genesis(migrated_database, receipts[0])


def test_distinct_concurrent_keys_create_distinct_empty_spaces(
    migrated_database: str, pg
) -> None:
    del pg
    workers = 6
    barrier = threading.Barrier(workers)

    def provision(index: int):
        barrier.wait(timeout=10)
        return _create(migrated_database, f"allocation:pg-distinct-{index}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        receipts = list(pool.map(provision, range(workers)))

    assert len({item.space_id for item in receipts}) == workers
    for index, receipt in enumerate(receipts):
        assert _counts(
            migrated_database, f"allocation:pg-distinct-{index}", receipt.space_id
        ) == (1, 1, 1, 1, 1, 1)
        _assert_empty_genesis(migrated_database, receipt)


def test_same_key_changed_semantics_conflicts_without_second_space(
    migrated_database: str, pg
) -> None:
    del pg
    first = _create(migrated_database, "allocation:pg-conflict")

    with pytest.raises(KnowledgeSpaceProvisioningConflictError):
        _create(
            migrated_database,
            "allocation:pg-conflict",
            profile=_profile("changed"),
        )

    assert _counts(migrated_database, "allocation:pg-conflict", first.space_id) == (
        1, 1, 1, 1, 1, 1
    )


def test_existing_space_collision_retries_without_aliasing(
    migrated_database: str, pg, monkeypatch
) -> None:
    del pg
    existing_id = "space:dm:pg-occupied"
    existing = initialize_empty_knowledge_space(
        repository=_repo(migrated_database),
        space_id=existing_id,
        initialization_id="init:pg-occupied",
        created_at=NOW,
        domain_contract=_domain(),
        semantic_profile=_profile(),
    )
    candidates = iter([existing_id, "space:dm:pg-fresh"])
    monkeypatch.setattr(
        "dungeonmind.application.vnext.space_provisioning._new_space_id",
        lambda: next(candidates),
    )

    provisioned = _create(migrated_database, "allocation:pg-after-collision")

    assert provisioned.space_id == "space:dm:pg-fresh"
    assert _repo(migrated_database).get_publication_receipt(
        existing_id, "init:pg-occupied"
    ) == existing
    assert _counts(
        migrated_database, "allocation:pg-after-collision", provisioned.space_id
    ) == (1, 1, 1, 1, 1, 1)
    assert _counts(migrated_database, "allocation:pg-after-collision", existing_id) == (
        1, 1, 1, 1, 1, 1
    )


def test_failure_inside_transaction_leaves_no_allocation_or_genesis(
    migrated_database: str, pg, monkeypatch
) -> None:
    del pg
    def fail_after_publication_receipt() -> None:
        raise RuntimeError("injected rollback before allocation receipt")

    monkeypatch.setattr(
        "dungeonmind.application.vnext.space_provisioning._new_space_id",
        lambda: "space:dm:pg-rollback",
    )
    repo = _repo(migrated_database, after_receipt_insert=fail_after_publication_receipt)

    with pytest.raises(RuntimeError, match="injected rollback"):
        _create(migrated_database, "allocation:pg-rollback", repo=repo)

    assert _counts(
        migrated_database, "allocation:pg-rollback", "space:dm:pg-rollback"
    ) == (0, 0, 0, 0, 0, 0)


def test_repository_recomputes_request_digest_before_any_mutation(
    migrated_database: str, pg, monkeypatch
) -> None:
    del pg
    space_id = "space:dm:pg-forged-request"
    monkeypatch.setattr(
        "dungeonmind.application.vnext.space_provisioning._new_space_id",
        lambda: space_id,
    )
    repo = _repo(migrated_database)

    class ForgedRequestDigestRepository:
        def provision_empty_space(self, command, **kwargs):
            return repo.provision_empty_space(
                command,
                allocation_id=kwargs["allocation_id"],
                request_sha256="0" * 64,
                publication_id=kwargs["publication_id"],
            )

    with pytest.raises(PersistenceIntegrityError, match="request digest mismatch"):
        _create(
            migrated_database,
            "allocation:pg-forged-request",
            repo=ForgedRequestDigestRepository(),
        )

    assert _counts(
        migrated_database, "allocation:pg-forged-request", space_id
    ) == (0, 0, 0, 0, 0, 0)


def test_post_commit_response_loss_retry_recovers_same_durable_space(
    migrated_database: str, pg, monkeypatch
) -> None:
    del pg
    calls = 0

    def lose_response_once() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated response loss after commit")

    candidates = iter(["space:dm:pg-committed", "space:dm:pg-unused"])
    monkeypatch.setattr(
        "dungeonmind.application.vnext.space_provisioning._new_space_id",
        lambda: next(candidates),
    )
    repo = _repo(migrated_database, after_space_provisioning_commit=lose_response_once)

    with pytest.raises(RuntimeError, match="response loss"):
        _create(migrated_database, "allocation:pg-response-loss", repo=repo)
    recovered = _create(migrated_database, "allocation:pg-response-loss", repo=repo)

    assert recovered.space_id == "space:dm:pg-committed"
    assert _counts(
        migrated_database, "allocation:pg-response-loss", recovered.space_id
    ) == (1, 1, 1, 1, 1, 1)
    _assert_empty_genesis(migrated_database, recovered)
