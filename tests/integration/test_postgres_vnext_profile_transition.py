"""Real PostgreSQL CAS/receipt and unrelated-authority conservation."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from dungeonmind.application.vnext.errors import KnowledgeStaleParentRevisionError
from dungeonmind.infrastructure.postgres.vnext_knowledge import PostgresKnowledgeRevisionRepository
from tests.unit.test_vnext_cas_publication import SPACE, genesis_command
from tests.unit.test_vnext_profile_transition import (
    assert_preservation_and_future_publication,
    fixture,
    transition,
)

pytestmark = pytest.mark.integration


def source_snapshot(pg):
    # Compare actual nonempty authority rows and epoch, not only row counts.
    from psycopg import sql

    with pg.database.connect() as conn:
        return {
            table: conn.execute(
                sql.SQL(
                    "SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text), "
                    "'[]'::jsonb) "
                    "AS rows FROM dungeonmind.{} t"
                ).format(sql.Identifier(table))
            ).fetchone()["rows"]
            for table in (
                "knowledge_native_source_admissions",
                "knowledge_native_source_spans",
                "source_admission_receipts",
                "knowledge_native_source_authority",
            )
        }


def test_postgres_preserves_unrelated_world_sources_and_future_publication(pg):
    repo = PostgresKnowledgeRevisionRepository(pg.database)
    other = repo.publish_publication(
        genesis_command().model_copy(update={"space_id": "space:other"}), "other-init"
    )
    other_before = repo.get_revision("space:other", other.published_revision_id)
    f = fixture(repo)
    from datetime import timedelta

    from dungeonmind.application.vnext import publish_native_text_source_evidence
    from dungeonmind.application.vnext.native_source_access import (
        open_admitted_native_text,
        open_native_text_source_access_context,
    )
    from dungeonmind.infrastructure.postgres.vnext_sources import (
        PostgresNativeSourceEvidenceRepository,
    )
    from tests.unit.test_vnext_native_source_admission import BODY, _request

    sources = PostgresNativeSourceEvidenceRepository(pg.database)
    request = _request(space_id=SPACE, parent_revision_id=f.parent.published_revision_id)
    admitted = publish_native_text_source_evidence(
        repository=sources, request=request, domain_contract=f.domain, semantic_profile=f.current
    )
    f.parent = admitted.publication_receipt
    f.request = f.request.model_copy(
        update={
            "expected_parent_revision_id": admitted.published_revision_id,
            "created_at": request.created_at + timedelta(minutes=1),
        }
    )
    before = source_snapshot(pg)
    assert before["knowledge_native_source_admissions"]
    epoch = sources.open_native_source_view(SPACE).epoch
    receipt = assert_preservation_and_future_publication(f)
    assert source_snapshot(pg) == before
    assert sources.open_native_source_view(SPACE).epoch == epoch
    for revision in (admitted.published_revision_id, receipt.published_revision_id):
        context = open_native_text_source_access_context(
            repository=sources, space_id=SPACE, revision_id=revision, domain_contract=f.domain
        )
        opened = open_admitted_native_text(context, admitted.bindings[0].evidence_ref_id)
        assert opened.status == "available" and opened.body_text == BODY
        assert opened.body_sha256 == request.expected_body_sha256
    assert repo.get_head("space:other").head_revision_id == other.published_revision_id
    assert repo.get_revision("space:other", other.published_revision_id) == other_before


def test_postgres_concurrent_profile_transitions_only_one_child(pg):
    repo = PostgresKnowledgeRevisionRepository(pg.database)
    f = fixture(repo)

    def attempt(identity):
        try:
            return transition(f, request=f.request.model_copy(update={"publication_id": identity}))
        except KnowledgeStaleParentRevisionError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["first", "second"]))
    assert sum(r is not None for r in results) == 1
    assert len(repo.head_events(SPACE)) == 2


def test_postgres_lost_ack_recovers_then_fresh_repository_replays(pg):
    plain = PostgresKnowledgeRevisionRepository(pg.database)
    f = fixture(plain)

    class LostAcknowledgement:
        def __getattr__(self, name):
            return getattr(plain, name)

        def publish_publication(self, command, publication_id):
            plain.publish_publication(command, publication_id)
            raise RuntimeError("post-commit acknowledgement lost")

    f.repo = LostAcknowledgement()
    receipt = transition(f)
    f.repo = PostgresKnowledgeRevisionRepository(pg.database)
    assert transition(f) == receipt
    assert len(f.repo.head_events(SPACE)) == 2
