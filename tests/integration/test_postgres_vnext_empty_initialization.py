"""PostgreSQL acceptance for public empty native KnowledgeSpace initialization."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

import pytest

from dungeonmind.application.vnext import initialize_empty_knowledge_space
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.errors import (
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
