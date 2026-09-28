"""PostgreSQL acceptance for public empty native KnowledgeSpace initialization."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest

from dungeonmind.application.vnext import initialize_empty_knowledge_space
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.errors import (
    KnowledgePublicationIdempotencyConflictError,
    KnowledgePublicationOutcomeUnknownError,
    KnowledgeStaleParentRevisionError,
)
from dungeonmind.application.vnext.materialization import (
    GovernedPublicationIdentity,
    decode_native_graph_payload,
    materialize_governed_revision,
)
from dungeonmind.application.vnext.publication import publish_governed_materialization
from dungeonmind.contracts.vnext.contribution import (
    ContributionDisposition,
    KnowledgeContribution,
    ProposeEntity,
)
from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    Entity,
    SemanticProfileDescriptorV2,
)
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres.database import PostgresDatabase
from dungeonmind.infrastructure.postgres.vnext_knowledge import (
    PostgresKnowledgeRevisionRepository,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def _repo(database_url: str, **kwargs) -> PostgresKnowledgeRevisionRepository:
    return PostgresKnowledgeRevisionRepository(PostgresDatabase(database_url), **kwargs)


def _domain() -> DomainContractDescriptor:
    return DomainContractDescriptor(
        domain_id="test.empty",
        domain_revision="1",
        admission_policy_id="test.empty.always",
    )


def _profile() -> SemanticProfileDescriptorV2:
    return SemanticProfileDescriptorV2(
        profile_id="test.empty.profile",
        profile_revision="2",
        term_namespaces=["test"],
    )


def _initialize(database_url: str, space_id: str, initialization_id: str, *, repo=None):
    return initialize_empty_knowledge_space(
        repository=repo or _repo(database_url),
        space_id=space_id,
        initialization_id=initialization_id,
        created_at=NOW,
        domain_contract=_domain(),
        semantic_profile=_profile(),
    )


def _authority_counts(database_url: str, space_ids: tuple[str, ...]) -> tuple[int, int, int]:
    with PostgresDatabase(database_url).connect() as conn:
        revisions = conn.execute(
            "SELECT COUNT(*) AS n FROM dungeonmind.knowledge_revisions WHERE space_id = ANY(%s)",
            (list(space_ids),),
        ).fetchone()
        events = conn.execute(
            "SELECT COUNT(*) AS n FROM dungeonmind.knowledge_head_events WHERE space_id = ANY(%s)",
            (list(space_ids),),
        ).fetchone()
        receipts = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM dungeonmind.knowledge_publication_receipts
            WHERE space_id = ANY(%s)
            """,
            (list(space_ids),),
        ).fetchone()
    assert revisions and events and receipts
    return int(revisions["n"]), int(events["n"]), int(receipts["n"])


def _namespace_head_counts(database_url: str, space_id: str) -> tuple[int, int]:
    with PostgresDatabase(database_url).connect() as conn:
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM dungeonmind.knowledge_spaces WHERE space_id = %s) AS spaces,
                (SELECT COUNT(*) FROM dungeonmind.knowledge_heads WHERE space_id = %s) AS heads
            """,
            (space_id, space_id),
        ).fetchone()
    assert row is not None
    return int(row["spaces"]), int(row["heads"])


def _assert_no_source_or_legacy_rows(database_url: str) -> None:
    with PostgresDatabase(database_url).connect() as conn:
        rows = conn.execute(
            """
            SELECT 'source_artifacts' AS table_name, COUNT(*) AS n
            FROM dungeonmind.source_artifacts
            UNION ALL SELECT 'source_revisions', COUNT(*) FROM dungeonmind.source_revisions
            UNION ALL SELECT 'evidence_refs', COUNT(*) FROM dungeonmind.evidence_refs
            UNION ALL SELECT 'worlds', COUNT(*) FROM dungeonmind.worlds
            UNION ALL SELECT 'campaigns', COUNT(*) FROM dungeonmind.campaigns
            UNION ALL SELECT 'graph_revisions', COUNT(*) FROM dungeonmind.graph_revisions
            UNION ALL SELECT 'world_graph_heads', COUNT(*) FROM dungeonmind.world_graph_heads
            UNION ALL SELECT 'world_graph_head_events', COUNT(*)
                FROM dungeonmind.world_graph_head_events
            """
        ).fetchall()
    assert len(rows) == 8
    assert {row["table_name"]: int(row["n"]) for row in rows} == {
        "source_artifacts": 0,
        "source_revisions": 0,
        "evidence_refs": 0,
        "worlds": 0,
        "campaigns": 0,
        "graph_revisions": 0,
        "world_graph_heads": 0,
        "world_graph_head_events": 0,
    }


def test_two_spaces_initialize_in_one_database_and_survive_reconnect(
    migrated_database: str, pg
) -> None:
    del pg
    first = _initialize(migrated_database, "space:empty-one", "init:one")
    second = _initialize(migrated_database, "space:empty-two", "init:two")
    restarted = _repo(migrated_database)

    assert restarted.get_head("space:empty-one").head_revision_id == first.published_revision_id  # type: ignore[union-attr]
    assert restarted.get_head("space:empty-two").head_revision_id == second.published_revision_id  # type: ignore[union-attr]
    assert _initialize(migrated_database, "space:empty-one", "init:one") == first
    assert _authority_counts(
        migrated_database, ("space:empty-one", "space:empty-two")
    ) == (2, 2, 2)
    for space_id, receipt in (
        ("space:empty-one", first),
        ("space:empty-two", second),
    ):
        stored = restarted.get_revision(space_id, receipt.published_revision_id)
        assert stored is not None
        assert stored.graph_payload == {
            "entities": [], "assertions": [], "aliases": [], "evidence": []
        }
        assert _namespace_head_counts(migrated_database, space_id) == (1, 1)
    _assert_no_source_or_legacy_rows(migrated_database)


def test_concurrent_distinct_initializations_create_one_root_without_orphan(
    migrated_database: str, pg
) -> None:
    del pg
    barrier = threading.Barrier(2)
    receipts = []
    errors: list[BaseException] = []

    def run(initialization_id: str) -> None:
        try:
            barrier.wait(timeout=5)
            receipts.append(
                _initialize(migrated_database, "space:race-empty", initialization_id)
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(value,)) for value in ("init:left", "init:right")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert all(not thread.is_alive() for thread in threads)
    assert len(receipts) == 1
    assert len(errors) == 1 and isinstance(errors[0], KnowledgeStaleParentRevisionError)
    assert _authority_counts(migrated_database, ("space:race-empty",)) == (1, 1, 1)


def test_transaction_failure_leaves_no_namespace_authority(
    migrated_database: str, pg
) -> None:
    del pg

    def fail_after_revision() -> None:
        raise RuntimeError("injected initialization rollback")

    repo = _repo(migrated_database, after_receipt_insert=fail_after_revision)
    with pytest.raises(KnowledgePublicationOutcomeUnknownError):
        _initialize(
            migrated_database,
            "space:rollback-empty",
            "init:rollback",
            repo=repo,
        )
    assert _repo(migrated_database).get_head("space:rollback-empty") is None
    assert _authority_counts(migrated_database, ("space:rollback-empty",)) == (0, 0, 0)
    assert _namespace_head_counts(migrated_database, "space:rollback-empty") == (0, 0)
    _assert_no_source_or_legacy_rows(migrated_database)


def test_commit_success_response_loss_recovers_exact_receipt(
    migrated_database: str, pg
) -> None:
    del pg
    real = _repo(migrated_database)

    class ResponseLoss:
        def publish_publication(self, command, publication_id):
            real.publish_publication(command, publication_id)
            raise RuntimeError("response lost")

        def get_publication_receipt(self, space_id, publication_id):
            return real.get_publication_receipt(space_id, publication_id)

        def get_revision(self, space_id, revision_id):
            return real.get_revision(space_id, revision_id)

    repo = ResponseLoss()
    receipt = _initialize(
        migrated_database,
        "space:lost-response-empty",
        "init:lost-response",
        repo=repo,
    )
    assert _repo(migrated_database).get_publication_receipt(
        "space:lost-response-empty", "init:lost-response"
    ) == receipt
    assert _authority_counts(migrated_database, ("space:lost-response-empty",)) == (1, 1, 1)


def test_replay_after_governed_descendant_does_not_rewind_postgres_head(
    migrated_database: str, pg
) -> None:
    del pg
    space_id = "space:descendant-empty"
    repo = _repo(migrated_database)
    original = _initialize(migrated_database, space_id, "init:descendant")
    stored = repo.get_revision(space_id, original.published_revision_id)
    assert stored is not None
    parent = build_parsed_knowledge_revision(
        revision=stored.revision,
        decoded_content=decode_native_graph_payload(stored.graph_payload),
    )
    materialization = materialize_governed_revision(
        parent=parent,
        contribution=KnowledgeContribution(
            contribution_id="contrib:descendant",
            space_id=space_id,
            producer="test:initializer",
            produced_at=NOW,
            status="finalized",
            items=[
                ProposeEntity(
                    item_id="item:descendant",
                    entity=Entity(entity_id="entity:descendant"),
                )
            ],
        ),
        dispositions=[
            ContributionDisposition(item_id="item:descendant", disposition="accepted")
        ],
        publication=GovernedPublicationIdentity(
            operation_ids=("op:descendant",),
            created_at=datetime(2026, 9, 28, 13, 0, tzinfo=UTC),
            expected_parent_revision_id=original.published_revision_id,
        ),
        domain_contract=_domain(),
        semantic_profile=_profile(),
    )
    descendant = publish_governed_materialization(
        materialization,
        repository=repo,
        publication_id="publication:descendant",
    )

    assert _initialize(migrated_database, space_id, "init:descendant") == original
    assert repo.get_head(space_id).head_revision_id == descendant.published_revision_id  # type: ignore[union-attr]
    assert _authority_counts(migrated_database, (space_id,)) == (2, 2, 2)


def test_same_initialization_concurrent_replay_returns_one_receipt(
    migrated_database: str, pg
) -> None:
    del pg
    barrier = threading.Barrier(2)
    receipts = []
    errors: list[BaseException] = []

    def run() -> None:
        try:
            barrier.wait(timeout=5)
            receipts.append(_initialize(migrated_database, "space:same-intent", "init:same"))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert len(receipts) == 2 and receipts[0] == receipts[1]
    assert _authority_counts(migrated_database, ("space:same-intent",)) == (1, 1, 1)
    assert _namespace_head_counts(migrated_database, "space:same-intent") == (1, 1)
    _assert_no_source_or_legacy_rows(migrated_database)


def test_changed_time_same_postgres_intent_preserves_all_authority(
    migrated_database: str, pg
) -> None:
    del pg
    space_id = "space:changed-time"
    original = _initialize(migrated_database, space_id, "init:changed-time")
    repo = _repo(migrated_database)
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        initialize_empty_knowledge_space(
            repository=repo,
            space_id=space_id,
            initialization_id="init:changed-time",
            created_at=NOW + timedelta(seconds=1),
            domain_contract=_domain(),
            semantic_profile=_profile(),
        )
    assert repo.get_publication_receipt(space_id, "init:changed-time") == original
    assert _authority_counts(migrated_database, (space_id,)) == (1, 1, 1)
    assert _namespace_head_counts(migrated_database, space_id) == (1, 1)


@pytest.mark.parametrize(
    "fault", ["receipt_missing", "receipt_corrupt", "revision_missing", "probe_down"]
)
def test_postgres_recovery_faults_fail_closed_and_preserve_committed_authority(
    migrated_database: str, pg, fault
) -> None:
    del pg
    space_id = "space:recovery-fault"
    real = _repo(migrated_database)
    original = _initialize(migrated_database, space_id, "init:recovery-fault")
    publish_error = RuntimeError("lost publication response")

    class FaultedReads:
        def publish_publication(self, *_args):
            raise publish_error

        def get_publication_receipt(self, *args):
            if fault == "receipt_missing":
                return None
            if fault == "probe_down":
                raise RuntimeError("receipt probe unavailable")
            receipt = real.get_publication_receipt(*args)
            assert receipt is not None
            if fault == "receipt_corrupt":
                return receipt.model_copy(update={"graph_payload_sha256": "0" * 64})
            return receipt

        def get_revision(self, *args):
            if fault == "revision_missing":
                return None
            return real.get_revision(*args)

    # Inject failure only at the read/transport seam; SQL remains read-only.
    expected_error = (
        KnowledgePublicationOutcomeUnknownError
        if fault in {"receipt_missing", "probe_down"}
        else PersistenceIntegrityError
    )
    with pytest.raises(expected_error) as caught:
        _initialize(
            migrated_database, space_id, "init:recovery-fault", repo=FaultedReads()
        )
    if expected_error is KnowledgePublicationOutcomeUnknownError:
        assert caught.value.__cause__ is publish_error
    assert real.get_publication_receipt(space_id, "init:recovery-fault") == original
    assert _authority_counts(migrated_database, (space_id,)) == (1, 1, 1)
    assert _namespace_head_counts(migrated_database, space_id) == (1, 1)
