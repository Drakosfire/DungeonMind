"""Selective query reads use the same exact-pin admission and ordering."""

import pytest

from dungeonmind.application.vnext.admission import AlwaysAdmitPolicy
from dungeonmind.application.vnext.entity_reads import EntityClaimsResult, EntityReadService
from dungeonmind.application.vnext.evidence_reads import EvidenceReadService
from dungeonmind.application.vnext.materialization import encode_native_graph_payload
from dungeonmind.application.vnext.native_source_access import (
    open_native_text_source_access_context,
)
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.application.vnext.records import ParsedEntity
from dungeonmind.application.vnext.search import SearchReadService
from dungeonmind.contracts.vnext.common import LabelsAllVisibility, ScopeSelector
from dungeonmind.contracts.vnext.domain import Entity, LiteralValue
from dungeonmind.domain.errors import PersistenceIntegrityError, PersistenceUnavailableError
from dungeonmind.infrastructure.postgres.selective_native_sources import (
    open_selective_native_text_source_access_context,
)
from dungeonmind.infrastructure.postgres.selective_query import (
    SelectiveFactCache,
    SelectiveQueryRead,
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


def test_claim_projection_matches_complete_claims_without_alias_work(
    pg, selective_graph, monkeypatch,
):
    repo, _, ordinary = selective_graph
    neighborhood._publish(pg.database, ordinary)
    source = open_selective_native_text_source_access_context(repo, **_source_options(ordinary))
    ids = ("b", "missing", "a", "b")
    expected = EntityReadService().get_complete_entities(ordinary, ids)
    projected = tuple(
        EntityClaimsResult(item.identity, item.found, item.assertions, item.completeness)
        for item in expected
    )
    evidence = EvidenceReadService().get_assertions_evidence(ordinary, ("cb", "ab", "cb"))
    original = SelectiveQueryRead._buckets

    def watch(reader, family, keys):
        assert family != "aliases"
        return original(reader, family, keys)

    monkeypatch.setattr(SelectiveQueryRead, "_buckets", watch)
    with _open(pg.database, source, ordinary) as reader:
        assert reader.get_entity_claims(ids) == projected
        retained = reader.retain_complete_facts()
    assert tuple(a.assertion_id for a in projected[0].assertions) == ("ab", "b-title", "cb")
    assert retained.get_entity_claim("b") == projected[0]
    assert retained.get_assertions_evidence(("cb", "ab", "cb")) == evidence
    with pytest.raises(PersistenceIntegrityError, match="was not captured"):
        retained.get_complete_entity("b")


def test_claim_projection_respects_withdrawal_at_acquisition_epoch(pg):
    from dungeonmind.application.vnext._read_artifact import parse_verified_source_rows
    from dungeonmind.application.vnext.initialization import initialize_empty_knowledge_space
    from dungeonmind.application.vnext.native_source_admission import (
        publish_native_text_source_evidence,
    )
    from dungeonmind.contracts.vnext.knowledge import PublishKnowledgeRevisionCommand
    from dungeonmind.contracts.vnext.projection import ProjectionRequest
    from tests.integration.test_postgres_vnext_native_source_admission import (
        _knowledge,
        _repository,
    )
    from tests.unit.test_vnext_native_source_admission import NOW, _domain, _profile, _request

    repo = _repository(pg)
    domain = _domain().model_copy(update={"claim_modes": ["test:fact"]})
    profile = _profile()
    genesis = initialize_empty_knowledge_space(
        repository=repo,
        space_id="space:selective-source-claims",
        initialization_id="init:selective-source-claims",
        created_at=NOW,
        domain_contract=domain,
        semantic_profile=profile,
    )
    request = _request(
        space_id=genesis.space_id, parent_revision_id=genesis.published_revision_id,
    )
    source = publish_native_text_source_evidence(
        repository=repo, request=request, domain_contract=domain, semantic_profile=profile,
    )
    parent = _knowledge(repo).get_revision(source.space_id, source.published_revision_id)
    assert parent is not None
    assertion = _literal("claim", "a", evidence_id=source.bindings[0].evidence_ref_id)
    assertion = assertion.model_copy(update={
        "metadata": assertion.metadata.model_copy(update={"scope": []}),
    })
    payload = {
        **parent.graph_payload,
        "entities": [Entity(entity_id="a").model_dump(mode="json")],
        "assertions": [assertion.model_dump(mode="json")],
    }
    stored = repo.publish_revision(PublishKnowledgeRevisionCommand(
        space_id=source.space_id,
        parent_revision_id=source.published_revision_id,
        expected_parent_revision_id=source.published_revision_id,
        operation_ids=["op:source-claim"],
        graph_schema=parent.revision.graph_schema,
        graph_payload=payload,
        domain_contract_ref=parent.revision.domain_contract_ref,
        semantic_profile_ref=parent.revision.semantic_profile_ref,
        created_at=NOW.replace(minute=2),
    ))
    projection_request = ProjectionRequest(
        space_id=source.space_id, revision_id=stored.revision.revision_id,
        scope_selector=ScopeSelector(include_unscoped=True),
        standing_selector=[assertion.metadata.standing],
    )
    context = KnowledgeReadContext(
        parsed=parse_verified_source_rows(stored, stored.graph_payload),
        request=projection_request,
        domain_contract=domain,
        semantic_profile=profile,
        domain_policy=AlwaysAdmitPolicy(policy_id=domain.admission_policy_id),
        source_reader=repo.open_native_source_view(source.space_id),
    )
    from dungeonmind.infrastructure.postgres.selective_read_projection import (
        publish_selective_read_projection,
    )
    publish_selective_read_projection(
        pg.database, space_id=source.space_id, revision_id=stored.revision.revision_id,
    )

    before = open_selective_native_text_source_access_context(repo, **_source_options(context))
    repo.withdraw_native_source(
        space_id=source.space_id, source_artifact_id=source.source_artifact_id,
        source_revision_id=source.source_revision_id,
    )
    after = open_selective_native_text_source_access_context(repo, **_source_options(context))
    for access, expected in ((before, ("claim",)), (after, ())):
        assert access is not None
        with _open(pg.database, access, context) as reader:
            assert reader is not None
            projected, = reader.get_entity_claims(("a",))
            assert projected.found
            assert tuple(item.assertion_id for item in projected.assertions) == expected


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
        with pytest.raises(PersistenceIntegrityError, match="posting bucket seal mismatch"):
            reader.get_entity_claims(("b",))


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

def test_warm_facts_skip_payload_reads_but_reverify_primary(pg, selective_graph, monkeypatch):
    repo, _, ordinary = selective_graph
    neighborhood._publish(pg.database, ordinary)
    options = dict(
        request=ordinary.request,
        resolve_descriptors=lambda *_: (ordinary.domain_contract, ordinary.semantic_profile),
        domain_policy=ordinary.domain_policy,
        source_audience_labels=ordinary.request.audience_labels,
        fact_cache=SelectiveFactCache(),
    )
    from dungeonmind.infrastructure.postgres import selective_query

    fetch = selective_query._fetch
    loads = []

    def track(connection, pin, table, family, keys):
        if table == "selective_read_records" and keys:
            loads.append((family, tuple(keys)))
        return fetch(connection, pin, table, family, keys)

    monkeypatch.setattr(selective_query, "_fetch", track)
    expected = SearchReadService().search_entities(ordinary, "test:relates")
    assert expected.hits
    for _ in range(2):
        with open_selective_source_query(repo, **options) as opened:
            assert opened is not None
            _, reader = opened
            assert reader.search_entities("test:relates") == expected
    assert sum(family == 'assertions' for family, _ in loads) == 1

    with pg.database.transaction() as connection:
        connection.execute(
            "UPDATE dungeonmind.knowledge_revisions "
            "SET graph_payload = graph_payload || jsonb_build_object('corrupt', true) "
            "WHERE revision_id = %s",
            (ordinary.request.revision_id,),
        )
    with (
        pytest.raises(PersistenceIntegrityError, match="primary revision drift"),
        open_selective_source_query(repo, **options),
    ):
        pytest.fail("warm cache bypassed exact primary verification")


def test_cache_bounds_and_partition_use_current_per_record_seal():
    cache = SelectiveFactCache(max_records=2, max_wire_bytes=3)
    pin = ("s", "r1")
    rows = {name: (ParsedEntity(name), 2) for name in ("a", "b")}
    cache._remember(pin, "entities", rows, {"a": "first", "b": "second"})
    assert cache._read(pin, "entities", ("a", "b"), {"a": "first", "b": "second"}) == {
        "b": ParsedEntity("b"),
    }
    assert not cache._read(pin, "entities", ("b",), {"b": "changed"})
    assert not cache._read(("s", "r2"), "entities", ("b",), {"b": "second"})
    cache._remember(pin, "entities", {"too-large": (ParsedEntity("too-large"), 4)},
                    {"too-large": "large"})
    assert not cache._read(pin, "entities", ("too-large",), {"too-large": "large"})
