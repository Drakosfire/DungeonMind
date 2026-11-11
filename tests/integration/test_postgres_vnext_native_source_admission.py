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
    refresh_native_text_source_access_context,
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

    # A newer head does not widen this read's Graph membership. The source
    # authority is reopened while the exact parsed child is reused.
    refreshed = refresh_native_text_source_access_context(repository=repository, context=context)
    assert refreshed.parsed is context.parsed
    assert refreshed.revision_id == receipt.published_revision_id
    assert refreshed.source_view is not context.source_view
    assert open_admitted_native_text(refreshed, receipt.bindings[0].evidence_ref_id) == access


def test_postgres_lost_post_commit_response_recovers_and_replays_fresh_repository(pg):
    hook_calls = 0

    def lose_response_after_commit() -> None:
        nonlocal hook_calls
        hook_calls += 1
        if hook_calls == 1:
            raise RuntimeError("injected response loss after commit")

    repository = PostgresNativeSourceEvidenceRepository(
        pg.database,
        after_publication_commit=lose_response_after_commit,
    )
    domain, profile, genesis = _init(repository)
    request = _request(
        space_id="space:postgres-native-source",
        parent_revision_id=genesis.published_revision_id,
    )
    events_before = _knowledge(repository).head_events(request.space_id)
    epoch_before = repository.open_native_source_view(request.space_id).epoch

    # The repository commits, then loses the response. The public operation
    # must recover the exact companion receipt instead of reporting failure.
    recovered = publish_native_text_source_evidence(
        repository=repository,
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
    )
    assert hook_calls == 1
    assert recovered.published_revision_id != genesis.published_revision_id
    assert recovered.publication_receipt.published_revision_id == recovered.published_revision_id

    # Simulate a process/repository restart and exact retry. No second child,
    # event, admission row or epoch increment may be introduced.
    fresh_repository = _repository(pg)
    assert (
        fresh_repository.get_native_source_admission_receipt(request.space_id, request.admission_id)
        == recovered
    )
    assert (
        fresh_repository.get_publication_receipt(request.space_id, request.admission_id)
        == recovered.publication_receipt
    )
    head_after_commit = fresh_repository.get_head(request.space_id)
    events_after_commit = _knowledge(fresh_repository).head_events(request.space_id)
    epoch_after_commit = fresh_repository.open_native_source_view(request.space_id).epoch
    assert head_after_commit is not None
    assert head_after_commit.head_revision_id == recovered.published_revision_id
    assert len(events_after_commit) == len(events_before) + 1
    assert epoch_after_commit == epoch_before + 1

    replay = publish_native_text_source_evidence(
        repository=fresh_repository,
        request=request,
        domain_contract=domain,
        semantic_profile=profile,
    )
    assert replay == recovered
    assert fresh_repository.get_head(request.space_id) == head_after_commit
    assert _knowledge(fresh_repository).head_events(request.space_id) == events_after_commit
    assert fresh_repository.open_native_source_view(request.space_id).epoch == epoch_after_commit
    with pg.database.transaction() as conn:
        assert (
            conn.execute(
                """
                SELECT COUNT(*) AS n FROM dungeonmind.knowledge_native_source_admissions
                WHERE space_id = %s AND admission_id = %s
                """,
                (request.space_id, request.admission_id),
            ).fetchone()["n"]
            == 1
        )


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


def test_postgres_source_metadata_reads_no_body_and_defers_byte_verification(pg, monkeypatch):
    from dungeonmind.application.vnext import list_admitted_native_text_sources
    from dungeonmind.application.vnext.errors import NativeTextSourceAccessIntegrityError
    from dungeonmind.contracts.vnext.native_source import NativeTextSourceOriginV1
    from dungeonmind.infrastructure.postgres import vnext_sources as storage

    repository = _repository(pg)
    domain, profile, genesis = _init(repository)
    request = _request(
        space_id="space:postgres-native-source", parent_revision_id=genesis.published_revision_id
    )
    origin = NativeTextSourceOriginV1(
        namespace="test.producer", object_id="object:1", revision_id="r:1"
    )
    request = request.model_copy(update={"origin": origin})
    receipt = publish_native_text_source_evidence(
        repository=repository, request=request, domain_contract=domain, semantic_profile=profile
    )
    context = open_native_text_source_access_context(
        repository=repository,
        space_id=request.space_id,
        revision_id=receipt.published_revision_id,
        domain_contract=domain,
    )
    actual = storage._read_native_record
    reads = []

    def record(conn, space_id, admission_id, *, include_body):
        result = actual(conn, space_id, admission_id, include_body=include_body)
        reads.append(include_body)
        if not include_body:
            assert result["body"] is None
        return result

    monkeypatch.setattr(storage, "_read_native_record", record)
    result = list_admitted_native_text_sources(context)
    assert result.complete and len(result.sources) == 1 and reads == [False]
    assert result.sources[0].origin == origin
    result.sources[0].origin.object_id = "changed"
    assert list_admitted_native_text_sources(context).sources[0].origin == origin
    assert reads == [False, False]
    evidence_id = result.sources[0].evidence_ref_ids[0]
    assert open_admitted_native_text(context, evidence_id).status == "available"
    assert reads == [False, False, True]

    # Metadata is not proof of byte integrity. Exact opening retains that check.
    with pg.database.transaction() as conn:
        conn.execute(
            "UPDATE dungeonmind.knowledge_native_source_admissions "
            "SET body_bytes=%s WHERE space_id=%s AND admission_id=%s",
            (b"corrupted bytes", request.space_id, request.admission_id),
        )
    assert list_admitted_native_text_sources(context).complete
    with pytest.raises(NativeTextSourceAccessIntegrityError):
        open_admitted_native_text(context, evidence_id)


@pytest.mark.parametrize("corruption", ["fingerprint", "origin"])
def test_postgres_metadata_does_not_skip_record_integrity(pg, corruption):
    from dungeonmind.application.vnext import list_admitted_native_text_sources
    from dungeonmind.application.vnext.errors import NativeTextSourceAccessIntegrityError

    repository = _repository(pg)
    domain, profile, genesis = _init(repository)
    request = _request(
        space_id="space:postgres-native-source", parent_revision_id=genesis.published_revision_id
    )
    receipt = publish_native_text_source_evidence(
        repository=repository, request=request, domain_contract=domain, semantic_profile=profile
    )
    context = open_native_text_source_access_context(
        repository=repository,
        space_id=request.space_id,
        revision_id=receipt.published_revision_id,
        domain_contract=domain,
    )
    with pg.database.transaction() as conn:
        if corruption == "fingerprint":
            conn.execute(
                "UPDATE dungeonmind.knowledge_native_source_admissions "
                "SET record_fingerprint=%s WHERE space_id=%s AND admission_id=%s",
                ("0" * 64, request.space_id, request.admission_id),
            )
        else:
            conn.execute(
                "UPDATE dungeonmind.knowledge_native_source_admissions "
                "SET origin=%s::jsonb WHERE space_id=%s AND admission_id=%s",
                ('{"namespace":"other","object_id":"foreign","revision_id":"other"}',
                 request.space_id, request.admission_id),
            )
    with pytest.raises(NativeTextSourceAccessIntegrityError):
        list_admitted_native_text_sources(context)


def test_postgres_retains_pdf_before_publication(pg):
    from hashlib import sha256
    from io import BytesIO

    from pypdf import PdfWriter

    from dungeonmind.application.vnext.native_pdf_access import open_native_pdf_region
    from dungeonmind.contracts.vnext.pdf_region import NativePdfRegionV1, NativePdfSourceAdmissionV1

    repository = _repository(pg)
    _init(repository)
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(output)
    body = output.getvalue()
    request = NativePdfSourceAdmissionV1.model_validate({
        "space_id": "space:postgres-native-source",
        "admission_id": "admission:pdf",
        "created_at": NOW,
        "content_sha256": sha256(body).hexdigest(),
        "source_classification": "test:pdf",
        "authority": "primary",
        "visibility": {"kind": "public"},
    })
    head = repository.get_head(request.space_id)
    old_view = repository.open_native_source_view(request.space_id)
    revision = repository.retain_native_pdf_source(request, body)
    assert repository.retain_native_pdf_source(request, body) == revision
    current_view = repository.open_native_source_view(request.space_id)
    assert current_view.epoch == old_view.epoch + 1
    keys = dict(artifact_ids=[revision.source_artifact_id], revision_ids=[revision.source_revision_id])
    assert old_view.get_provenance_snapshot(**keys).get_revision(revision.source_revision_id) is None
    current = current_view.get_provenance_snapshot(**keys)
    assert current.get_revision(revision.source_revision_id) == revision
    assert current.get_artifact(revision.source_artifact_id) is not None
    unrelated = repository.open_native_source_view("space:unrelated")
    assert unrelated.get_provenance_snapshot(**keys).get_revision(revision.source_revision_id) is None
    locator = NativePdfRegionV1(
        source_revision_id=revision.source_revision_id,
        content_sha256=revision.content_sha256,
        page=1, left=0, top=0, right=1, bottom=1,
    )
    assert open_native_pdf_region(
        locator, authorized_space_id=request.space_id,
        audience=frozenset(), declared_labels=frozenset(),
        load=repository.get_native_pdf_source,
    ) == body
    with pytest.raises(ValueError, match="outside"):
        open_native_pdf_region(
            locator.model_copy(update={"page": 2}), authorized_space_id=request.space_id,
            audience=frozenset(), declared_labels=frozenset(),
            load=repository.get_native_pdf_source,
        )
    truncated = b"%PDF-1.7\n"
    with pytest.raises(ValueError, match="Invalid PDF"):
        repository.retain_native_pdf_source(
            request.model_copy(update={"content_sha256": sha256(truncated).hexdigest()}),
            truncated,
        )
    assert repository.get_head(request.space_id) == head
