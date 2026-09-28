from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from dungeonmind.application.vnext.errors import (
    KnowledgePublicationOutcomeUnknownError,
    KnowledgeStaleParentRevisionError,
)
from dungeonmind.application.vnext.initialization import initialize_empty_knowledge_space
from dungeonmind.application.vnext.native_source_access import (
    open_admitted_native_text,
    open_native_text_source_access_context,
)
from dungeonmind.application.vnext.native_source_admission import (
    publish_native_text_source_evidence,
)
from dungeonmind.infrastructure.postgres import PostgresNativeSourceEvidenceRepository
from dungeonmind.infrastructure.postgres.vnext_knowledge import (
    PostgresKnowledgeRevisionRepository,
)
from tests.unit.test_vnext_native_source_admission import (
    BODY,
    NOW,
    _domain,
    _profile,
    _request,
)

pytestmark = pytest.mark.integration


def _repository(pg) -> PostgresNativeSourceEvidenceRepository:
    return PostgresNativeSourceEvidenceRepository(pg.database)


def _knowledge(repository: PostgresNativeSourceEvidenceRepository):
    return PostgresKnowledgeRevisionRepository(repository._database)


def _init(repository):
    domain, profile = _domain(), _profile()
    receipt = initialize_empty_knowledge_space(
        repository=repository,
        space_id="space:postgres-native-source",
        initialization_id="init:postgres-native-source",
        created_at=NOW,
        domain_contract=domain,
        semantic_profile=profile,
    )
    return domain, profile, receipt


def test_postgres_commits_exact_source_and_replays_after_descendant(pg):
    repository = _repository(pg)
    domain, profile, genesis = _init(repository)
    request = _request(
        space_id="space:postgres-native-source",
        parent_revision_id=genesis.published_revision_id,
    )
    receipt = publish_native_text_source_evidence(
        repository=repository,
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
    )
    context = open_native_text_source_access_context(
        repository=repository,
        space_id=request.space_id,
        revision_id=receipt.published_revision_id,
        domain_contract=domain,
    )
    access = open_admitted_native_text(context, receipt.bindings[0].evidence_ref_id)
    assert access.status == "available"
    assert access.body_text == BODY

    child = _knowledge(repository).get_revision(request.space_id, receipt.published_revision_id)
    assert child is not None
    from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand

    next_command = PublishKnowledgeRevisionCommand(
        space_id=request.space_id,
        parent_revision_id=receipt.published_revision_id,
        expected_parent_revision_id=receipt.published_revision_id,
        operation_ids=["op:descendant"],
        graph_schema=child.revision.graph_schema,
        graph_payload=child.graph_payload,
        domain_contract_ref=child.revision.domain_contract_ref,
        semantic_profile_ref=child.revision.semantic_profile_ref,
        migration_origin_ref=child.revision.migration_origin_ref,
        created_at=NOW.replace(minute=2),
    )
    _knowledge(repository).publish_publication(next_command, "pub:descendant")
    replay = publish_native_text_source_evidence(
        repository=repository,
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
    )
    assert replay == receipt
    assert repository.get_head(request.space_id).head_revision_id != receipt.published_revision_id


@pytest.mark.parametrize("failure_stage", ["revision", "publication_receipt", "source", "receipt"])
def test_postgres_failure_rolls_back_child_receipts_event_and_epoch(pg, failure_stage: str):
    domain, profile = _domain(), _profile()

    def fail() -> None:
        raise RuntimeError("injected transaction failure")

    repository = PostgresNativeSourceEvidenceRepository(
        pg.database,
        after_native_source_insert=fail if failure_stage == "source" else None,
        after_native_receipt_insert=fail if failure_stage == "receipt" else None,
    )
    genesis = initialize_empty_knowledge_space(
        repository=repository,
        space_id="space:postgres-native-source",
        initialization_id="init:postgres-native-source",
        created_at=NOW,
        domain_contract=domain,
        semantic_profile=profile,
    )
    repository._after_revision_insert = fail if failure_stage == "revision" else None
    repository._after_receipt_insert = fail if failure_stage == "publication_receipt" else None
    before_epoch = repository.open_native_source_view("space:postgres-native-source").epoch
    before_events = repository.head_events("space:postgres-native-source")
    request = _request(
        space_id="space:postgres-native-source",
        parent_revision_id=genesis.published_revision_id,
    )

    with pytest.raises(KnowledgePublicationOutcomeUnknownError):
        publish_native_text_source_evidence(
            repository=repository,
            request=request,
            domain_contract=domain,
            semantic_profile=profile,
        )

    assert (
        repository.get_head("space:postgres-native-source").head_revision_id
        == genesis.published_revision_id
    )
    assert repository.head_events("space:postgres-native-source") == before_events
    assert (
        repository.get_native_source_admission_receipt(
            "space:postgres-native-source", request.admission_id
        )
        is None
    )
    assert repository.open_native_source_view("space:postgres-native-source").epoch == before_epoch
    with pg.database.transaction() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) AS n FROM dungeonmind.knowledge_native_source_admissions"
            ).fetchone()["n"]
            == 0
        )


def test_postgres_same_id_concurrent_replay_has_one_committed_result(pg):
    repository = _repository(pg)
    domain, profile, genesis = _init(repository)
    request = _request(
        space_id="space:postgres-native-source",
        parent_revision_id=genesis.published_revision_id,
    )

    def publish():
        return publish_native_text_source_evidence(
            repository=_repository(pg),
            request=request,
            domain_contract=domain,
            semantic_profile=profile,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = tuple(pool.map(lambda _: publish(), range(2)))
    assert first == second
    assert len(_knowledge(repository).head_events(request.space_id)) == 2
    assert (
        repository.open_native_source_view(request.space_id).epoch >= first.source_authority_epoch
    )


def test_postgres_different_admissions_racing_same_parent_have_one_winner(pg):
    repository = _repository(pg)
    domain, profile, genesis = _init(repository)
    requests = (
        _request(
            space_id="space:postgres-native-source",
            admission_id="admit:first",
            parent_revision_id=genesis.published_revision_id,
        ),
        _request(
            space_id="space:postgres-native-source",
            admission_id="admit:second",
            parent_revision_id=genesis.published_revision_id,
        ),
    )

    def publish(request):
        try:
            return publish_native_text_source_evidence(
                repository=_repository(pg),
                request=request,
                domain_contract=domain,
                semantic_profile=profile,
            )
        except KnowledgeStaleParentRevisionError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(pool.map(publish, requests))
    assert sum(not isinstance(item, KnowledgeStaleParentRevisionError) for item in outcomes) == 1
    assert sum(isinstance(item, KnowledgeStaleParentRevisionError) for item in outcomes) == 1
    assert len(_knowledge(repository).head_events("space:postgres-native-source")) == 2
