"""Service-level tests for the direct World Graph retrieval seam (R.2).

Every test runs through the synthetic ``dm_union_graph_v6`` authority fixture
(world-owned + two campaigns + GM-only content + broken-provenance row) parsed
by ``VersionedUnionGraphSnapshotReader`` under the bundled D&D v3 profile, and
composed through the landed v2 projection service.
"""

from datetime import UTC, datetime

import pytest

from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V6,
    RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import (
    SOURCE_ANCHOR_ID_PREFIX,
    EvidenceTarget,
    RetrievalBounds,
    WorldGraphRetrievalService,
    derive_source_anchor_id,
)
from dungeonmind.contracts.evidence import (
    SourceArtifactV2,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.identity import IdentityOutcome
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2, WorldGraphProjectionRequestV2
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.infrastructure.memory import (
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.world_object_vocabulary import (
    load_builtin_v3_descriptor,
)

WORLD_ID = "world:test"
CAMPAIGN_A = "camp:alpha"
CAMPAIGN_B = "camp:beta"
NOW = datetime(2026, 8, 22, 18, 0, tzinfo=UTC)


class _FixedClock:
    def now(self):
        return NOW


class _CountingProjectionService(WorldGraphProjectionService):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.project_calls = 0

    def project(self, request):
        self.project_calls += 1
        return super().project(request)


def _v6_descriptor():
    return load_builtin_v3_descriptor()


def _v6_profile_ref() -> dict:
    descriptor = _v6_descriptor()
    return {
        "schema_version": "dm_semantic_profile_ref_v1",
        "profile_id": descriptor.profile_id,
        "profile_revision": descriptor.profile_revision,
        "descriptor_sha256": descriptor_sha256(descriptor),
    }


def _meta(
    assertion_id: str,
    *,
    evidence: tuple[str, ...],
    visibility: str = "player",
    campaign_scope: str | None = None,
) -> dict:
    return {
        "schema_version": "dm_knowledge_assertion_metadata_v1",
        "assertion_id": assertion_id,
        "campaign_scope": campaign_scope,
        "visibility": visibility,
        "epistemic_kind": "asserted",
        "canon_state": "canonical",
        "evidence_ref_ids": list(evidence),
        "session_refs": [],
        "temporal_scope": {"schema_version": "dm_temporal_scope_ref_v1", "kind": "unknown"},
    }


def _evidence_row(evidence_ref_id: str, artifact_id: str, revision_id: str, *, span=None) -> dict:
    return {
        "schema_version": "dm_evidence_ref_v2",
        "evidence_ref_id": evidence_ref_id,
        "source_artifact_id": artifact_id,
        "source_revision_id": revision_id,
        "source_domain_key": "buddy.worldbuilding",
        "source_domain": "worldbuilding",
        "evidence_role": "support",
        "can_open_source": True,
        "can_highlight_span": span is not None,
        "session_id": None,
        "source_span_ref_id": span,
        "locator": f"fixture://{artifact_id}",
        "uri": None,
        "source_locator": None,
        "line_ref": None,
    }


def _object(
    object_id: str,
    label: str,
    *,
    assertion_id: str,
    evidence: str,
    campaign_scope: str | None,
    visibility: str = "player",
    aliases: list[tuple[str, str, str]] | None = None,
    summary: str | None = None,
    properties: list[tuple[str, object, str, str]] | None = None,
) -> dict:
    return {
        "object_id": object_id,
        "kind": "dnd5e:location",
        "label": label,
        "assertion_metadata": _meta(
            assertion_id,
            evidence=(evidence,),
            visibility=visibility,
            campaign_scope=campaign_scope,
        ),
        "aliases": [
            {
                "value": alias_value,
                "assertion_metadata": _meta(
                    alias_id,
                    evidence=(evidence,),
                    visibility=alias_visibility,
                    campaign_scope=campaign_scope,
                ),
            }
            for alias_value, alias_id, alias_visibility in (aliases or [])
        ],
        "summary": (
            {
                "value": summary,
                "assertion_metadata": _meta(
                    f"{assertion_id}:summary",
                    evidence=(evidence,),
                    visibility=visibility,
                    campaign_scope=campaign_scope,
                ),
            }
            if summary
            else None
        ),
        "properties": [
            {
                "property_term": term,
                "value": value,
                "assertion_metadata": _meta(
                    prop_id,
                    evidence=(evidence,),
                    visibility=prop_visibility,
                    campaign_scope=campaign_scope,
                ),
            }
            for term, value, prop_id, prop_visibility in (properties or [])
        ],
        "aspects": [],
    }


def _relationship(
    relationship_id: str,
    source: str,
    target: str,
    predicate: str,
    *,
    assertion_id: str,
    evidence: str,
    visibility: str = "player",
    campaign_scope: str | None = None,
) -> dict:
    return {
        "relationship_id": relationship_id,
        "source_object_id": source,
        "target_object_id": target,
        "predicate": predicate,
        "assertion_metadata": _meta(
            assertion_id,
            evidence=(evidence,),
            visibility=visibility,
            campaign_scope=campaign_scope,
        ),
    }


def _payload() -> dict:
    return {
        "world_id": WORLD_ID,
        "semantic_profile": _v6_profile_ref(),
        "relationship_endpoint_aspect_schema": RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
        "objects": [
            _object(
                "obj:world-tavern",
                "World Tavern",
                assertion_id="asrt:world-tavern",
                evidence="ev:world",
                campaign_scope=None,
                aliases=[
                    ("The Prancing Pony", "asrt:tavern-alias-pony", "player"),
                    ("The Local Spot", "asrt:tavern-alias-spot", "player"),
                ],
                summary="A bustling tavern at the crossroads.",
                properties=[
                    ("dnd5e:population", "bustling", "asrt:prop-tavern-population", "player"),
                ],
            ),
            _object(
                "obj:world-gate",
                "North Gate",
                assertion_id="asrt:world-gate",
                evidence="ev:world",
                campaign_scope=None,
                aliases=[("The Local Spot", "asrt:gate-alias-spot", "player")],
            ),
            _object(
                "obj:alpha-keep",
                "Alpha Keep",
                assertion_id="asrt:alpha-keep",
                evidence="ev:alpha",
                campaign_scope=CAMPAIGN_A,
                aliases=[("The Traitor's Keep", "asrt:keep-alias-traitor", "gm")],
                properties=[
                    ("dnd5e:threat_level", "low", "asrt:prop-keep-threat", "player"),
                ],
            ),
            _object(
                "obj:beta-crypt",
                "Beta Crypt",
                assertion_id="asrt:beta-crypt",
                evidence="ev:beta",
                campaign_scope=CAMPAIGN_B,
            ),
            _object(
                "obj:alpha-secret",
                "Alpha Secret Vault",
                assertion_id="asrt:alpha-secret",
                evidence="ev:alpha",
                campaign_scope=CAMPAIGN_A,
                visibility="gm",
                aliases=[("The Hidden Cache", "asrt:secret-alias-cache", "gm")],
            ),
            _object(
                "obj:broken-lore",
                "Broken Lore",
                assertion_id="asrt:broken-lore",
                evidence="ev:broken",
                campaign_scope=None,
            ),
        ],
        "relationships": [
            _relationship(
                "rel:tavern-gate",
                "obj:world-tavern",
                "obj:world-gate",
                "dnd5e:near",
                assertion_id="asrt:rel-tavern-gate",
                evidence="ev:world",
            ),
            _relationship(
                "rel:tavern-keep",
                "obj:world-tavern",
                "obj:alpha-keep",
                "dnd5e:located_in",
                assertion_id="asrt:rel-tavern-keep",
                evidence="ev:alpha",
                campaign_scope=CAMPAIGN_A,
            ),
            _relationship(
                "rel:keep-secret",
                "obj:alpha-keep",
                "obj:alpha-secret",
                "dnd5e:conceals",
                assertion_id="asrt:rel-keep-secret",
                evidence="ev:alpha",
                visibility="gm",
                campaign_scope=CAMPAIGN_A,
            ),
            _relationship(
                "rel:keep-crypt",
                "obj:alpha-keep",
                "obj:beta-crypt",
                "dnd5e:connected_to",
                assertion_id="asrt:rel-keep-crypt",
                evidence="ev:alpha",
            ),
        ],
        "evidence_refs": [
            _evidence_row(
                "ev:world", "src:world-lore", "srcrev:world-lore-v1", span="span:tavern-1"
            ),
            _evidence_row("ev:alpha", "src:alpha-notes", "srcrev:alpha-notes-v1"),
            _evidence_row("ev:beta", "src:beta-notes", "srcrev:beta-notes-v1"),
            _evidence_row("ev:broken", "src:world-lore", "srcrev:missing-rev"),
        ],
    }


def _seed_sources() -> InMemorySourceRepository:
    sources = InMemorySourceRepository()
    for artifact_id, revision_id, campaign_id in (
        ("src:world-lore", "srcrev:world-lore-v1", None),
        ("src:alpha-notes", "srcrev:alpha-notes-v1", CAMPAIGN_A),
        ("src:beta-notes", "srcrev:beta-notes-v1", CAMPAIGN_B),
    ):
        sources.put_artifact(
            SourceArtifactV2(
                source_artifact_id=artifact_id,
                source_domain_key="buddy.worldbuilding",
                source_domain=SourceDomain.WORLDBUILDING,
                world_id=WORLD_ID,
                campaign_id=campaign_id,
                session_id=None,
                uri=None,
                current_revision_id=revision_id,
                authority=None,
                visibility=Visibility.PLAYER,
                artifact_kind=None,
                document_class=None,
                review_state=None,
                source_visibility_state=None,
                workspace_document_ref=None,
                lineage={},
                status=SourceStatus.ACTIVE,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        sources.put_revision(
            SourceRevision(
                source_revision_id=revision_id,
                source_artifact_id=artifact_id,
                content_sha256="dd" * 32,
                body_storage="external",
                locator=f"fixture://{artifact_id}",
                created_at=NOW,
            )
        )
    return sources


def _services(
    world_graph: InMemoryWorldGraphRepository,
) -> tuple[WorldGraphRetrievalService, _CountingProjectionService]:
    sources = _seed_sources()
    projection = _CountingProjectionService(
        world_graph=world_graph,
        sources=sources,
        graph_reader=VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([_v6_descriptor()])
        ),
        clock=_FixedClock(),
    )
    return WorldGraphRetrievalService(projection=projection, sources=sources), projection


def _publish(
    world_graph: InMemoryWorldGraphRepository,
    payload: dict | None = None,
    *,
    parent_revision_id: str | None = None,
    operation_id: str = "op:fixture",
):
    return world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=parent_revision_id,
            expected_parent_revision_id=parent_revision_id,
            operation_ids=[operation_id],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=payload if payload is not None else _payload(),
            created_at=NOW,
        )
    )


def _request(
    *,
    scope_mode: ScopeModeV2,
    campaign_id: str | None = None,
    admissibility: Admissibility = Admissibility.GM,
    revision_pin: str | None = None,
) -> WorldGraphProjectionRequestV2:
    return WorldGraphProjectionRequestV2(
        world_id=WORLD_ID,
        campaign_id=campaign_id,
        admissibility=admissibility,
        revision_pin=revision_pin,
        scope_mode=scope_mode,
    )


def _world() -> WorldGraphProjectionRequestV2:
    return _request(scope_mode=ScopeModeV2.WORLD)


def _campaign_a(**kwargs) -> WorldGraphProjectionRequestV2:
    return _request(scope_mode=ScopeModeV2.CAMPAIGN, campaign_id=CAMPAIGN_A, **kwargs)


def _cross(**kwargs) -> WorldGraphProjectionRequestV2:
    return _request(scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN, **kwargs)


# ---------------------------------------------------------------------------
# Exact object lookup
# ---------------------------------------------------------------------------


def test_object_lookup_returns_exact_admitted_object_with_identity():
    world_graph = InMemoryWorldGraphRepository()
    revision = _publish(world_graph)
    service, projection = _services(world_graph)

    result = service.get_object(_world(), object_id="obj:world-tavern")

    assert result.found is True
    assert result.object is not None
    assert result.object.label == "World Tavern"
    assert result.object.aliases == ["The Prancing Pony", "The Local Spot"]
    assert result.object.summary == "A bustling tavern at the crossroads."
    assert result.snapshot.revision_id == revision.revision_id
    assert result.snapshot.head_revision_id == revision.revision_id
    assert result.snapshot.is_head is True
    assert result.snapshot.schema_version == "dm_projection_snapshot_v2"
    # Exactly one projection composition per operation.
    assert projection.project_calls == 1
    # Campaign-scoped relationship is excluded under the world-only scope.
    assert [rel.relationship_id for rel in result.relationships] == ["rel:tavern-gate"]
    # Claim-ledger-ready property assertion row.
    assert [row.assertion_id for row in result.property_assertions] == [
        "asrt:prop-tavern-population"
    ]
    row = result.property_assertions[0]
    assert row.subject_object_id == "obj:world-tavern"
    assert row.property_term == "dnd5e:population"
    assert row.property_value == "bustling"
    assert row.evidence_ref_ids == ("ev:world",)
    assert row.assertion_metadata is not None
    assert row.assertion_metadata.campaign_scope is None
    # Anchor derived from admitted provenance with the span locator identity.
    assert len(result.anchors) == 1
    anchor = result.anchors[0]
    assert anchor.anchor_id.startswith(SOURCE_ANCHOR_ID_PREFIX)
    assert anchor.evidence_ref_id == "ev:world"
    assert anchor.source_artifact_id == "src:world-lore"
    assert anchor.source_revision_id == "srcrev:world-lore-v1"
    assert anchor.locator_identity == "span:tavern-1"
    assert anchor.source_span_ref_id == "span:tavern-1"
    assert anchor.can_open_source is True
    assert "obj:world-tavern" in anchor.supporting_object_ids
    assert "rel:tavern-gate" in anchor.supporting_relationship_ids
    assert "rel:tavern-gate" not in anchor.supporting_object_ids
    assert "asrt:prop-tavern-population" in anchor.supporting_assertion_ids


def test_object_lookup_miss_is_explicit_without_search_fallback():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    absent = service.get_object(_world(), object_id="obj:nonexistent")
    assert absent.found is False
    assert absent.object is None
    assert absent.coverage.gap_codes == ()
    assert absent.coverage.missing_ids == ()

    # A label is never silently reinterpreted as an object ID lookup.
    by_label = service.get_object(_world(), object_id="World Tavern")
    assert by_label.found is False


def test_object_lookup_out_of_scope_id_stays_silent():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    result = service.get_object(_campaign_a(), object_id="obj:beta-crypt")
    assert result.found is False
    # Out-of-scope exclusion: no codes, no identifiers echoed.
    assert result.coverage.gap_codes == ()
    assert result.coverage.missing_ids == ()


def test_object_lookup_rejects_blank_id():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)
    with pytest.raises(ValueError, match="non-blank"):
        service.get_object(_world(), object_id="  ")


# ---------------------------------------------------------------------------
# Search / referent resolution
# ---------------------------------------------------------------------------


def test_search_exact_identity_precedence_and_determinism():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, projection = _services(world_graph)
    request = _cross()

    by_id = service.search(request, query_text="obj:alpha-keep")
    assert by_id.matched_object_ids[0] == "obj:alpha-keep"
    assert "exact_object_id" in by_id.match_reasons["obj:alpha-keep"]

    by_label = service.search(request, query_text="Alpha Keep")
    assert by_label.matched_object_ids[0] == "obj:alpha-keep"
    assert "exact_label" in by_label.match_reasons["obj:alpha-keep"]

    by_alias = service.search(request, query_text="the prancing pony")
    assert by_alias.matched_object_ids[0] == "obj:world-tavern"
    assert "exact_alias" in by_alias.match_reasons["obj:world-tavern"]

    again = service.search(request, query_text="Alpha Keep")
    assert again.matched_object_ids == by_label.matched_object_ids
    assert again.match_reasons == by_label.match_reasons
    assert projection.project_calls == 4


def test_search_matches_property_value_and_term_text():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)
    request = _campaign_a()

    by_value = service.search(request, query_text="low")
    assert "obj:alpha-keep" in by_value.matched_object_ids
    assert "property_phrase" in by_value.match_reasons["obj:alpha-keep"]

    by_term = service.search(request, query_text="dnd5e:threat_level")
    assert "obj:alpha-keep" in by_term.matched_object_ids


def test_search_matches_through_relationship_and_related_object_text():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    result = service.search(_world(), query_text="north gate")
    assert result.matched_object_ids[0] == "obj:world-gate"
    assert "obj:world-tavern" in result.matched_object_ids
    assert (
        "relationship_or_related_object_phrase"
        in result.match_reasons["obj:world-tavern"]
    )


def test_search_seeds_admitted_before_ranking_and_missing_reported():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    result = service.search(
        _cross(),
        query_text="",
        seed_object_ids=["obj:beta-crypt", "obj:missing"],
    )
    assert result.matched_object_ids == ("obj:beta-crypt",)
    assert result.match_reasons["obj:beta-crypt"] == ("exact_seed",)
    assert result.coverage.requested_seed_object_ids == ("obj:beta-crypt", "obj:missing")
    assert result.coverage.missing_seed_object_ids == ("obj:missing",)
    # Referent resolution records the explicit seed and the rejected miss.
    outcomes = {r.mention_text: r.outcome for r in result.referents}
    assert outcomes["obj:beta-crypt"] == IdentityOutcome.RESOLVED_EXISTING
    assert outcomes["obj:missing"] == IdentityOutcome.REJECTED


def test_search_never_recovers_object_through_omitted_gm_alias():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    player = service.search(
        _campaign_a(admissibility=Admissibility.PLAYER),
        query_text="the traitor's keep",
    )
    assert "obj:alpha-keep" not in player.matched_object_ids
    assert all(r.object_id != "obj:alpha-keep" for r in player.referents)

    gm = service.search(_campaign_a(), query_text="the traitor's keep")
    assert gm.matched_object_ids[0] == "obj:alpha-keep"
    assert "exact_alias" in gm.match_reasons["obj:alpha-keep"]


def test_search_ambiguous_admitted_alias_stays_ambiguous():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    result = service.search(_world(), query_text="the local spot")
    ambiguous = [r for r in result.referents if r.outcome == IdentityOutcome.AMBIGUOUS]
    assert len(ambiguous) == 1
    assert ambiguous[0].object_id is None
    assert "obj:world-tavern" not in result.matched_object_ids
    assert "obj:world-gate" not in result.matched_object_ids


def test_search_player_admissibility_never_surfaces_gm_only_object():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    player = service.search(
        _campaign_a(admissibility=Admissibility.PLAYER),
        query_text="alpha secret vault",
    )
    # The GM-only object is never recovered; other player-visible objects may
    # legitimately token-match through their own admitted fields.
    assert "obj:alpha-secret" not in player.matched_object_ids
    assert all(r.object_id != "obj:alpha-secret" for r in player.referents)

    gm = service.search(_campaign_a(), query_text="alpha secret vault")
    assert gm.matched_object_ids[0] == "obj:alpha-secret"


def test_search_cross_campaign_spans_campaigns_in_one_exact_revision():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    cross = service.search(_cross(), query_text="dnd5e:location")
    assert {"obj:alpha-keep", "obj:beta-crypt"} <= set(cross.matched_object_ids)

    campaign_only = service.search(_campaign_a(), query_text="beta crypt")
    assert "obj:beta-crypt" not in campaign_only.matched_object_ids


def test_search_result_caps_and_truncation_are_explicit():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    result = service.search(
        _cross(),
        query_text="dnd5e:location",
        bounds=RetrievalBounds(max_objects=2),
    )
    assert len(result.matched_object_ids) == 2
    assert "objects" in result.coverage.truncated_fields
    # Deterministic tie-break: ascending object_id at equal score.
    assert result.matched_object_ids == tuple(sorted(result.matched_object_ids))


def test_search_seeds_survive_result_bounds():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    seeds = ["obj:alpha-keep", "obj:beta-crypt", "obj:world-gate"]
    result = service.search(
        _cross(),
        query_text="tavern",
        seed_object_ids=seeds,
        bounds=RetrievalBounds(max_objects=1),
    )
    # All three admitted seeds survive even though max_objects=1; non-seed
    # matches consume only the remaining budget (here zero).
    assert set(result.matched_object_ids) == set(seeds)
    assert "obj:world-tavern" not in result.matched_object_ids
    assert "objects" in result.coverage.truncated_fields
    assert "exact_seed" in result.match_reasons["obj:beta-crypt"]


# ---------------------------------------------------------------------------
# Neighborhood
# ---------------------------------------------------------------------------


def test_neighborhood_depth_one_and_two():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, projection = _services(world_graph)
    request = _cross()

    depth1 = service.get_neighborhood(request, seed_object_ids=["obj:alpha-keep"], depth=1)
    assert set(depth1.object_depths) == {
        "obj:alpha-keep",
        "obj:world-tavern",
        "obj:alpha-secret",
        "obj:beta-crypt",
    }
    assert depth1.object_depths["obj:alpha-keep"] == 0
    assert all(
        depth1.object_depths[oid] == 1
        for oid in depth1.object_depths
        if oid != "obj:alpha-keep"
    )
    assert depth1.seed_object_ids == ("obj:alpha-keep",)

    depth2 = service.get_neighborhood(request, seed_object_ids=["obj:alpha-keep"], depth=2)
    assert depth2.object_depths["obj:world-gate"] == 2
    assert {rel.relationship_id for rel in depth2.relationships} == {
        "rel:tavern-keep",
        "rel:keep-secret",
        "rel:keep-crypt",
        "rel:tavern-gate",
    }
    assert projection.project_calls == 2


def test_neighborhood_missing_seed_reported_never_replaced():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    result = service.get_neighborhood(
        _cross(),
        seed_object_ids=["obj:alpha-keep", "obj:gone"],
        depth=1,
    )
    assert result.coverage.missing_seed_object_ids == ("obj:gone",)
    assert "obj:gone" not in result.object_depths
    assert result.seed_object_ids == ("obj:alpha-keep",)


def test_neighborhood_player_never_crosses_gm_only_edge():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    result = service.get_neighborhood(
        _campaign_a(admissibility=Admissibility.PLAYER),
        seed_object_ids=["obj:alpha-keep"],
        depth=2,
    )
    assert set(result.object_depths) == {
        "obj:alpha-keep",
        "obj:world-tavern",
        "obj:world-gate",
    }
    assert all("secret" not in rel.relationship_id for rel in result.relationships)


def test_neighborhood_campaign_scope_excludes_other_campaign():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    result = service.get_neighborhood(
        _campaign_a(),
        seed_object_ids=["obj:alpha-keep"],
        depth=1,
    )
    assert "obj:beta-crypt" not in result.object_depths
    assert "rel:keep-crypt" not in {rel.relationship_id for rel in result.relationships}


def test_neighborhood_input_validation():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)
    request = _cross()

    with pytest.raises(ValueError, match="at least one seed"):
        service.get_neighborhood(request, seed_object_ids=[], depth=1)
    with pytest.raises(ValueError, match="at most 8"):
        service.get_neighborhood(
            request,
            seed_object_ids=[f"obj:s{i}" for i in range(9)],
            depth=1,
        )
    with pytest.raises(ValueError, match="depth must be 1 or 2"):
        service.get_neighborhood(request, seed_object_ids=["obj:alpha-keep"], depth=3)


def test_neighborhood_seeds_survive_result_bounds():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    seeds = ["obj:world-tavern", "obj:world-gate", "obj:alpha-keep", "obj:beta-crypt"]
    result = service.get_neighborhood(
        _cross(),
        seed_object_ids=seeds,
        depth=1,
        bounds=RetrievalBounds(max_objects=2),
    )
    # All four admitted seeds survive even though max_objects=2: expansion
    # results consume only the remaining budget (here zero), so
    # seed_object_ids never claims a seed absent from objects/object_depths.
    assert set(result.seed_object_ids) == set(seeds)
    assert set(result.object_depths) == set(seeds)
    assert all(depth == 0 for depth in result.object_depths.values())
    assert {obj.object_id for obj in result.objects} == set(seeds)
    # The one-hop expansion to the GM-owned vault was reachable but unfunded.
    assert "obj:alpha-secret" not in result.object_depths
    assert "objects" in result.coverage.truncated_fields


# ---------------------------------------------------------------------------
# Evidence retrieval
# ---------------------------------------------------------------------------


def test_evidence_for_object_target_revalidates_and_returns_admitted():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, projection = _services(world_graph)

    result = service.get_evidence(
        _world(),
        target=EvidenceTarget(kind="object", target_id="obj:world-tavern"),
    )
    assert result.found is True
    assert result.object is not None
    assert [ev.evidence_ref_id for ev in result.evidence] == ["ev:world"]
    assert result.evidence[0].schema_version == "dm_evidence_ref_v2"
    assert len(result.anchors) == 1
    assert result.anchors[0].locator_identity == "span:tavern-1"
    assert result.coverage.gap_codes == ()
    assert projection.project_calls == 1


def test_evidence_for_assertion_target_returns_claim_ready_row():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    result = service.get_evidence(
        _world(),
        target=EvidenceTarget(kind="assertion", target_id="asrt:prop-tavern-population"),
    )
    assert result.found is True
    assert result.assertion is not None
    assert result.assertion.assertion_kind == "property"
    assert result.assertion.subject_object_id == "obj:world-tavern"
    assert result.assertion.property_term == "dnd5e:population"
    assert result.assertion.property_value == "bustling"
    assert result.assertion.evidence_ref_ids == ("ev:world",)
    assert result.assertion.assertion_metadata is not None
    assert [ev.evidence_ref_id for ev in result.evidence] == ["ev:world"]
    assert result.anchors[0].supporting_assertion_ids == ("asrt:prop-tavern-population",)


def test_evidence_for_relationship_target():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    result = service.get_evidence(
        _campaign_a(),
        target=EvidenceTarget(kind="relationship", target_id="rel:tavern-keep"),
    )
    assert result.found is True
    assert result.relationship is not None
    assert result.relationship.predicate == "dnd5e:located_in"
    assert [ev.evidence_ref_id for ev in result.evidence] == ["ev:alpha"]
    assert result.anchors[0].supporting_relationship_ids == ("rel:tavern-keep",)
    assert result.anchors[0].supporting_object_ids == ()


def test_evidence_broken_provenance_produces_explicit_safe_coverage():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    result = service.get_evidence(
        _world(),
        target=EvidenceTarget(kind="object", target_id="obj:broken-lore"),
    )
    assert result.found is False
    # In-scope broken chain: the missing revision ID is safe to name.
    assert "evidence_source_revision_missing" in result.coverage.gap_codes
    assert "srcrev:missing-rev" in result.coverage.missing_ids


def test_evidence_hidden_target_miss_never_echoes_identifiers():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)
    player = _campaign_a(admissibility=Admissibility.PLAYER)

    by_object = service.get_evidence(
        player, target=EvidenceTarget(kind="object", target_id="obj:alpha-secret")
    )
    assert by_object.found is False
    assert by_object.coverage.gap_codes == ()
    assert by_object.coverage.missing_ids == ()

    by_assertion = service.get_evidence(
        player, target=EvidenceTarget(kind="assertion", target_id="asrt:alpha-secret")
    )
    assert by_assertion.found is False
    assert by_assertion.coverage.gap_codes == ()


def test_evidence_unknown_target_is_a_plain_miss():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    result = service.get_evidence(
        _world(), target=EvidenceTarget(kind="object", target_id="obj:nowhere")
    )
    assert result.found is False
    assert result.coverage.gap_codes == ()


# ---------------------------------------------------------------------------
# Source anchors
# ---------------------------------------------------------------------------


def test_anchor_id_is_stable_and_matches_direct_derivation():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)
    request = _world()

    first = service.get_object(request, object_id="obj:world-tavern")
    second = service.get_object(request, object_id="obj:world-tavern")
    assert first.anchors[0].anchor_id == second.anchors[0].anchor_id

    direct = derive_source_anchor_id(
        snapshot=first.snapshot,
        evidence_ref_id="ev:world",
        source_artifact_id="src:world-lore",
        source_revision_id="srcrev:world-lore-v1",
        locator_identity="span:tavern-1",
    )
    assert first.anchors[0].anchor_id == direct


def test_anchor_resolution_roundtrip():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)
    request = _world()
    anchor_id = service.get_object(request, object_id="obj:world-tavern").anchors[0].anchor_id

    resolved = service.resolve_source_anchor(request, anchor_id=anchor_id)
    assert resolved.found is True
    assert resolved.anchor is not None
    assert resolved.anchor.evidence_ref_id == "ev:world"
    assert resolved.anchor.artifact.source_artifact_id == "src:world-lore"
    assert resolved.anchor.source_revision_id == "srcrev:world-lore-v1"
    assert resolved.anchor.locator_identity == "span:tavern-1"
    assert resolved.snapshot.revision_id == request.revision_pin or resolved.snapshot.is_head


def test_anchor_never_resolves_under_a_changed_context():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)
    world_request = _world()
    anchor_id = service.get_object(world_request, object_id="obj:world-tavern").anchors[0].anchor_id

    # Admissibility change.
    assert service.resolve_source_anchor(
        _request(scope_mode=ScopeModeV2.WORLD, admissibility=Admissibility.PLAYER),
        anchor_id=anchor_id,
    ).found is False
    # Scope mode change.
    assert service.resolve_source_anchor(_cross(), anchor_id=anchor_id).found is False
    # Campaign change.
    assert service.resolve_source_anchor(_campaign_a(), anchor_id=anchor_id).found is False
    # Unknown anchor.
    assert service.resolve_source_anchor(
        world_request, anchor_id=f"{SOURCE_ANCHOR_ID_PREFIX}{'0' * 64}"
    ).found is False


def test_historical_pin_remains_exact_for_retrieval_and_anchors():
    world_graph = InMemoryWorldGraphRepository()
    first = _publish(world_graph)
    payload_v2 = _payload()
    payload_v2["objects"].append(
        _object(
            "obj:world-mill",
            "Old Mill",
            assertion_id="asrt:world-mill",
            evidence="ev:world",
            campaign_scope=None,
        )
    )
    second = _publish(
        world_graph,
        payload_v2,
        parent_revision_id=first.revision_id,
        operation_id="op:second",
    )
    service, _ = _services(world_graph)

    pinned = _request(scope_mode=ScopeModeV2.WORLD, revision_pin=first.revision_id)
    pinned_result = service.get_object(pinned, object_id="obj:world-mill")
    assert pinned_result.found is False
    assert pinned_result.snapshot.revision_id == first.revision_id
    assert pinned_result.snapshot.head_revision_id == second.revision_id
    assert pinned_result.snapshot.is_head is False

    head_result = service.get_object(_world(), object_id="obj:world-mill")
    assert head_result.found is True
    assert head_result.snapshot.is_head is True

    # An anchor minted on the pinned revision resolves only under that pin.
    anchor_id = service.get_object(pinned, object_id="obj:world-tavern").anchors[0].anchor_id
    assert service.resolve_source_anchor(pinned, anchor_id=anchor_id).found is True
    assert service.resolve_source_anchor(_world(), anchor_id=anchor_id).found is False


def test_anchor_metadata_carries_no_source_body_content():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)
    request = _world()
    resolved = service.resolve_source_anchor(
        request,
        anchor_id=service.get_object(request, object_id="obj:world-tavern").anchors[0].anchor_id,
    )
    assert resolved.found is True
    anchor = resolved.anchor
    assert anchor is not None
    # Identity records only: no body/prose fields exist on the metadata shape.
    assert not hasattr(anchor, "body")
    assert not hasattr(anchor, "content")
    assert not hasattr(anchor, "text")
    assert anchor.artifact.source_artifact_id == "src:world-lore"
