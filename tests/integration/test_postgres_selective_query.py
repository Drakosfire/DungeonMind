"""Selective query reads use the same exact-pin admission and ordering."""

import pytest

from dungeonmind.application.vnext.entity_reads import EntityReadService
from dungeonmind.application.vnext.evidence_reads import EvidenceReadService
from dungeonmind.application.vnext.materialization import encode_native_graph_payload
from dungeonmind.application.vnext.native_source_access import (
    open_native_text_source_access_context,
)
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.application.vnext.search import SearchReadService
from dungeonmind.contracts.vnext.common import LabelsAllVisibility, ScopeSelector
from dungeonmind.contracts.vnext.domain import Entity, LiteralValue
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError
from dungeonmind.infrastructure.postgres.selective_native_sources import (
    open_selective_native_text_source_access_context,
)
from dungeonmind.infrastructure.postgres.selective_query import (
    open_selective_query,
    open_selective_source_query,
)
from tests.integration import test_postgres_selective_neighborhood as neighborhood
from tests.unit.test_vnext_neighborhood import _literal

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

@pytest.fixture
def dense_search(pg, selective_graph):
    repo, parent, context = selective_graph
    pin = context.request.revision_id
    entities = {"topic": Entity(entity_id="topic")}
    assertions = {}
    for rank in range(40):
        subject = f"entity:{rank:02d}"
        entities[subject] = Entity(entity_id=subject)
        # The first wave appears strongest, but its sources are private to the
        # hidden audience. Equal-strength admitted entities resolve by identity.
        for index in range(12 if rank < 8 else 9):
            key = f"assertion:{rank:02d}:{index:02d}"
            template = _literal(key, subject)
            metadata = template.metadata.model_dump(mode="json")
            metadata["evidence_ref_ids"] = []
            if rank < 8:
                metadata["visibility"] = LabelsAllVisibility(labels=["test:hidden"]).model_dump(
                    mode="json"
                )
            values = template.model_dump(mode="json")
            values["metadata"] = metadata
            values["value"] = LiteralValue(value="topic").model_dump(mode="json")
            assertions[key] = type(template).model_validate(values)
    stored = repo.publish_revision(parent.model_copy(update={
        "parent_revision_id": pin,
        "expected_parent_revision_id": pin,
        "operation_ids": ["op:dense"],
        "graph_payload": encode_native_graph_payload(
            entities=entities, assertions=assertions, aliases={}, evidence={},
        ),
    }))
    revision = stored.revision.revision_id
    source = open_native_text_source_access_context(
        repository=repo, **(_source_options(context) | {"revision_id": revision}),
    )
    expected = KnowledgeReadContext(
        parsed=source.parsed, request=context.request.model_copy(update={"revision_id": revision}),
        domain_contract=context.domain_contract, semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy, source_reader=source.source_view,
    )
    neighborhood._publish(pg.database, expected)
    return source, expected, len(assertions)


@pytest.mark.parametrize("query", ["topic", "topic topic", "test:title"])
def test_dense_bounded_search_matches_order_after_denied_high_rank_entities(
    pg, dense_search, monkeypatch, query,
):
    from dungeonmind.infrastructure.postgres.selective_query import SelectiveQueryRead

    source, context, total = dense_search
    load = SelectiveQueryRead._facts
    pulled = []

    def track(reader, family, identifiers):
        if family == "assertions":
            pulled.extend(identifiers)
        return load(reader, family, identifiers)

    monkeypatch.setattr(SelectiveQueryRead, "_facts", track)
    with _open(pg.database, source, context) as reader:
        assert reader is not None
        expected = SearchReadService().search_entities(context, query, limit=5)
        assert len(expected.hits) == 5
        assert len([hit for hit in expected.hits if hit.entity.entity_id == "topic"]) == (
            1 if query == "topic" else 0
        )
        assert reader.search_entities(query, limit=5) == expected
    assert 96 < len(pulled) < total // 2


def test_dense_bounded_search_rejects_forged_subject_assignment(pg, dense_search):
    source, context, _ = dense_search
    with pg.database.transaction() as connection:
        connection.execute(
            """UPDATE dungeonmind.selective_read_records
            SET value=jsonb_set(value, '{subject_entity_id}', '"entity:00"')
            WHERE family='assertions' AND key='assertion:09:00'"""
        )
    with _open(pg.database, source, context) as reader:
        assert reader is not None
        with pytest.raises(PersistenceIntegrityError, match="subject assignment seal mismatch"):
            reader.search_entities("topic", limit=5)
