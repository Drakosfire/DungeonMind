"""Live PostgreSQL parity and fail-closed selective neighborhood reads."""

import pytest

from dungeonmind.application.vnext._read_artifact import parse_verified_source_rows
from dungeonmind.application.vnext.admission import AlwaysAdmitPolicy
from dungeonmind.application.vnext.entity_reads import EntityReadService
from dungeonmind.application.vnext.materialization import encode_native_graph_payload
from dungeonmind.application.vnext.native_source_access import NativeParsedRevisionCache
from dungeonmind.application.vnext.neighborhood import NeighborhoodReadService
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.contracts.vnext.common import (
    KnowledgeStanding, LabelsAllVisibility, ScopeBinding, ScopeSelector,
)
from dungeonmind.contracts.vnext.domain import Entity
from dungeonmind.contracts.vnext.projection import ProjectionRequest
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.postgres.selective_neighborhood import (
    open_selective_neighborhood,
    read_selective_neighborhood,
)
from dungeonmind.infrastructure.postgres.selective_read_projection import publish_selective_read_projection
from dungeonmind.infrastructure.postgres.vnext_sources import PostgresNativeSourceEvidenceRepository
from tests.unit.test_vnext_cas_publication import SPACE, genesis_command
from tests.unit.test_vnext_neighborhood import _edge, _lab_contract, _lab_profile, _literal

pytestmark = pytest.mark.integration


@pytest.fixture
def selective_graph(pg):
    domain, profile = _lab_contract(), _lab_profile()
    policy = AlwaysAdmitPolicy(policy_id=domain.admission_policy_id)
    edges = [
        _edge("ab", "a", "b"),
        _edge("cb", "c", "b"),
        _edge("bd", "b", "d", visibility=LabelsAllVisibility(labels=["test:hidden"])),
        _edge("be", "b", "e", scope_value="two"),
        _literal("b-title", "b"),
    ]
    assertions = {
        edge.assertion_id: edge.model_copy(update={
            "metadata": edge.metadata.model_copy(update={"evidence_ref_ids": []}),
        })
        for edge in edges
    }
    payload = encode_native_graph_payload(
        entities={key: Entity(entity_id=key) for key in "abcde"},
        assertions=assertions, aliases={}, evidence={},
    )
    command = genesis_command(payload=payload)
    command = command.model_copy(update={
        "domain_contract_ref": command.domain_contract_ref.model_copy(update={
            "domain_id": domain.domain_id,
            "descriptor_sha256": canonical_sha256(domain.model_dump(mode="json")),
        }),
        "semantic_profile_ref": command.semantic_profile_ref.model_copy(update={
            "profile_id": profile.profile_id,
            "descriptor_sha256": canonical_sha256(profile.model_dump(mode="json")),
        }),
    })
    repo = PostgresNativeSourceEvidenceRepository(pg.database)
    stored = repo.publish_revision(command)
    revision_id = stored.revision.revision_id
    request = ProjectionRequest(
        space_id=SPACE, revision_id=revision_id,
        scope_selector=ScopeSelector(bindings=[ScopeBinding(axis="test:scope", value="one")]),
        audience_labels=["test:audience"], standing_selector=[KnowledgeStanding.ESTABLISHED],
    )
    parsed = parse_verified_source_rows(stored, stored.graph_payload)
    context = KnowledgeReadContext(
        parsed=parsed, request=request, domain_contract=domain, semantic_profile=profile,
        domain_policy=policy, source_reader=repo.open_native_source_view(SPACE),
    )
    return repo, command, context


def _read(database, context, **options):
    return read_selective_neighborhood(
        database,
        request=context.request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        seed_entity_ids=["a", "missing"], depth=2, require_admitted_seeds=True,
        **options,
    )


def _publish(database, context):
    return publish_selective_read_projection(
        database, space_id=SPACE, revision_id=context.parsed.revision_id,
    )


def test_selective_depth_two_old_pin_matches_authorized_order(pg, selective_graph):
    repo, command, context = selective_graph
    assert _read(pg.database, context) is None
    _publish(pg.database, context)
    revision_id = context.parsed.revision_id
    repo.publish_revision(command.model_copy(update={
        "parent_revision_id": revision_id, "expected_parent_revision_id": revision_id,
        "operation_ids": ["op:child"],
    }))
    assert repo.get_head(SPACE).head_revision_id != revision_id
    expected = NeighborhoodReadService().get_neighborhood(
        context, ["a", "missing"], depth=2, require_admitted_seeds=True,
    )
    assert tuple(a.assertion_id for a in expected.traversal_assertions) == ("ab", "cb")
    assert _read(pg.database, context) == expected


@pytest.mark.parametrize(
    ("mutation", "failure"),
    [
        ("DELETE FROM dungeonmind.selective_read_proofs", "proof is missing"),
        ("DELETE FROM dungeonmind.selective_read_buckets WHERE family='outgoing' AND key='a'",
         "bucket seal mismatch"),
        ("DELETE FROM dungeonmind.selective_read_records WHERE family='assertions' AND key='ab'",
         "records missing"),
        ("UPDATE dungeonmind.knowledge_revisions SET graph_payload = graph_payload || '{\"bad\":true}'::jsonb",
         "primary revision drift"),
    ],
)
def test_active_projection_refuses_corruption(pg, selective_graph, mutation, failure):
    _, _, context = selective_graph
    _publish(pg.database, context)
    with pg.database.transaction() as connection:
        connection.execute(mutation)
    with pytest.raises(PersistenceIntegrityError, match=failure):
        _read(pg.database, context)


def test_parsed_pin_routes_to_ordinary_read_without_touching_projection(pg, selective_graph):
    repo, _, context = selective_graph
    _publish(pg.database, context)
    revision_id = context.parsed.revision_id
    cache = NativeParsedRevisionCache()
    cache.parse(repo.get_revision(SPACE, revision_id))

    class NeverConnect:
        def transaction(self):
            pytest.fail("warm selective routing opened a database connection")

    assert _read(NeverConnect(), context, parsed_cache=cache) is None
    assert _read(pg.database, context, parsed_cache=NativeParsedRevisionCache()) is not None


def test_presentation_is_ordered_authorized_and_request_scoped(pg, selective_graph):
    _, _, context = selective_graph
    _publish(pg.database, context)
    with open_selective_neighborhood(
        pg.database,request=context.request,domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,domain_policy=context.domain_policy,
        seed_entity_ids=["a"],depth=2,require_admitted_seeds=True,
    ) as opened:
        assert opened is not None
        ids = ["b", "a", "b"]
        expected = tuple(EntityReadService().get_entity(context, entity_id) for entity_id in ids)
        actual = opened.read_entities(ids)
        assert actual == expected
        assert "b-title" in {item.assertion_id for item in actual[0].assertions}
        assert opened.read_entities([]) == ()
        with pytest.raises(ValueError, match="authorized neighborhood"):
            opened.read_entities(["d"])
    with pytest.raises(PersistenceIntegrityError, match="read is closed"):
        opened.read_entities(["a"])
