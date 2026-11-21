"""Selective query reads use the same exact-pin admission and ordering."""

import pytest

from dungeonmind.application.vnext.entity_reads import EntityReadService
from dungeonmind.application.vnext.evidence_reads import EvidenceReadService
from dungeonmind.application.vnext.native_source_access import (
    open_native_text_source_access_context,
)
from dungeonmind.application.vnext.search import SearchReadService
from dungeonmind.contracts.vnext.common import ScopeSelector
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError
from dungeonmind.infrastructure.postgres.selective_native_sources import (
    open_selective_native_text_source_access_context,
)
from dungeonmind.infrastructure.postgres.selective_query import open_selective_query
from tests.integration import test_postgres_selective_neighborhood as neighborhood

selective_graph = neighborhood.selective_graph

pytestmark = pytest.mark.integration


def _source_options(context):
    return dict(
        space_id=context.request.space_id,
        revision_id=context.request.revision_id,
        domain_contract=context.domain_contract,
        audience_labels=context.request.audience_labels,
    )


def _open(database, source, context):
    return open_selective_query(
        database,
        request=context.request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_context=source,
    )


@pytest.mark.parametrize("strict_scope", [True, False])
def test_selective_query_matches_search_entities_and_selected_claims(
    pg, selective_graph, strict_scope,
):
    repo, _, ordinary = selective_graph
    if not strict_scope:
        ordinary = type(ordinary)(
            parsed=ordinary.parsed,
            request=ordinary.request.model_copy(update={"scope_selector": ScopeSelector()}),
            domain_contract=ordinary.domain_contract,
            semantic_profile=ordinary.semantic_profile,
            domain_policy=ordinary.domain_policy,
            source_reader=ordinary.source_reader,
        )
    full_source = open_native_text_source_access_context(
        repository=repo, **_source_options(ordinary),
    )
    with _open(pg.database, full_source, ordinary) as inactive:
        assert inactive is None
    neighborhood._publish(pg.database, ordinary)
    source = open_selective_native_text_source_access_context(repo, **_source_options(ordinary))
    assert source is not None

    queries = ("a", "b", "b b", "related", "test:edge", "nothing matches")
    entities = ("b", "a", "missing", "b")
    claims = ("ab", "bd", "be", "missing", "ab")
    with _open(pg.database, source, ordinary) as reader:
        assert reader is not None
        for query in queries:
            assert reader.search_entities(query) == SearchReadService().search_entities(
                ordinary, query,
            )
        assert reader.get_complete_entities(entities) == (
            EntityReadService().get_complete_entities(ordinary, entities)
        )
        assert reader.get_assertions_evidence(claims) == (
            EvidenceReadService().get_assertions_evidence(ordinary, claims)
        )
    with pytest.raises(PersistenceUnavailableError, match="scope is closed"):
        reader.search_entities("b")


def test_selective_query_fails_closed_when_an_incoming_bucket_disappears(pg, selective_graph):
    repo, _, ordinary = selective_graph
    neighborhood._publish(pg.database, ordinary)
    source = open_selective_native_text_source_access_context(repo, **_source_options(ordinary))
    assert source is not None
    with pg.database.transaction() as connection:
        connection.execute(
            "DELETE FROM dungeonmind.selective_read_buckets WHERE family='incoming' AND key='b'"
        )
    with _open(pg.database, source, ordinary) as reader:
        assert reader is not None
        with pytest.raises(PersistenceIntegrityError, match="posting bucket seal mismatch"):
            reader.get_complete_entities(("b",))
