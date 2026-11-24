import pytest

from dungeonmind.application.vnext.initialization import initialize_empty_knowledge_space
from dungeonmind.application.vnext.native_source_access import (
    open_admitted_native_text,
    open_native_text_source_access_context,
)
from dungeonmind.infrastructure.postgres import PostgresNativeSourceEvidenceRepository
from tests.unit.test_vnext_native_source_admission import BODY, NOW, _domain, _profile
from tests.unit.test_vnext_world_copy import _copy, _source

pytestmark = pytest.mark.integration


def test_postgres_copy_preserves_evidence_and_isolates_sessions(pg):
    repo = PostgresNativeSourceEvidenceRepository(pg.database)
    domain, profile = _domain(), _profile()
    genesis = initialize_empty_knowledge_space(
        repository=repo,
        space_id="space:native-source",
        initialization_id="init:native-source",
        created_at=NOW,
        domain_contract=domain,
        semantic_profile=profile,
    )
    repo, domain, profile, source, _, original = _source((repo, domain, profile, genesis))
    first = _copy(repo, domain, profile, original)
    second = _copy(repo, domain, profile, original, operation="session:two")
    assert first.space_id != second.space_id != source.space_id
    assert _copy(repo, domain, profile, original) == first
    graph = repo.get_revision(first.space_id, first.revision_id).graph_payload
    assert len(graph["assertions"]) == 2 and len(graph["aliases"]) == 1
    context = open_native_text_source_access_context(
        repository=repo,
        space_id=first.space_id,
        revision_id=first.revision_id,
        domain_contract=domain,
    )
    assert (
        open_admitted_native_text(context, graph["evidence"][0]["evidence_ref_id"]).body_text
        == BODY
    )
    assert repo.get_head(source.space_id).head_revision_id == original.published_revision_id
