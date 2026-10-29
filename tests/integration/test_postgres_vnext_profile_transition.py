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


def source_counts(pg):
    with pg.database.connect() as conn:
        return conn.execute(
            "SELECT (SELECT count(*) FROM dungeonmind.knowledge_native_source_admissions), "
            "(SELECT count(*) FROM dungeonmind.knowledge_native_source_spans), "
            "(SELECT count(*) FROM dungeonmind.source_admission_receipts)"
        ).fetchone()


def test_postgres_preserves_unrelated_world_sources_and_future_publication(pg):
    repo = PostgresKnowledgeRevisionRepository(pg.database)
    other = repo.publish_publication(
        genesis_command().model_copy(update={"space_id": "space:other"}), "other-init"
    )
    other_before = repo.get_revision("space:other", other.published_revision_id)
    f = fixture(repo)
    before_counts = source_counts(pg)
    assert_preservation_and_future_publication(f)
    assert source_counts(pg) == before_counts
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
