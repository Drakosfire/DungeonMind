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
from dungeonmind.infrastructure.postgres.selective_query import (
    open_selective_query,
    open_selective_source_query,
)
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

def test_one_projection_backs_source_query_and_retained_claim_reads(
    pg, selective_graph, monkeypatch,
):
    repo, _, ordinary = selective_graph
    full_source = open_native_text_source_access_context(
        repository=repo, **_source_options(ordinary),
    )
    options = dict(
        request=ordinary.request,
        resolve_descriptors=lambda *_: (ordinary.domain_contract, ordinary.semantic_profile),
        domain_policy=ordinary.domain_policy,
        source_audience_labels=ordinary.request.audience_labels,
    )
    with open_selective_source_query(repo, **options) as inactive:
        assert inactive is None
    neighborhood._publish(pg.database, ordinary)
    from dungeonmind.infrastructure.postgres import selective_query

    load = selective_query._load_activation
    opens = []

    def track(connection, pin):
        opens.append(pin)
        return load(connection, pin)

    def forbidden(*args, **kwargs):
        pytest.fail("the selective path built the full Graph or reloaded already verified records")

    monkeypatch.setattr(selective_query, "_load_activation", track)
    monkeypatch.setattr(
        "dungeonmind.application.vnext._read_artifact._build_parsed_knowledge_revision_from_records",
        forbidden,
    )
    with open_selective_source_query(repo, **options) as opened:
        assert opened is not None
        source, reader = opened
        assert source.parsed.evidence_by_id == full_source.parsed.evidence_by_id
        assert source.source_view.epoch == full_source.source_view.epoch
        for query in ("b b", "test:edge", "unknown phrase"):
            assert reader.search_entities(query) == (
                SearchReadService().search_entities(ordinary, query)
            )
        # Separate waves deliberately keep ab and cb in different contexts.
        reader.get_complete_entities(("a",))
        reader.get_complete_entities(("c",))
        retained = reader.retain_complete_facts()
    assert opens == [(ordinary.request.space_id, ordinary.request.revision_id)]
    monkeypatch.setattr(selective_query, "_fetch", forbidden)
    ids = ("cb", "ab", "cb")
    assert retained.get_assertions_evidence(ids) == (
        EvidenceReadService().get_assertions_evidence(ordinary, ids)
    )
    assert retained.get_complete_entity("a") == EntityReadService().get_complete_entity(
        ordinary, "a",
    )
    with pytest.raises(PersistenceIntegrityError, match="assertion was not captured"):
        retained.get_assertions_evidence(("bd",))
    with pytest.raises(PersistenceIntegrityError, match="entity was not captured"):
        retained.get_complete_entity("b")
