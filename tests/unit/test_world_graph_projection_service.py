from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from dungeonmind.application.graph_scope import (
    CampaignScope,
    public_coverage_gaps_for_exclusion,
)
from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V6,
    RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
    UnionGraphV1SnapshotReader,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.contracts.evidence import (
    SourceArtifactV2,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.graph import (
    PublishRevisionCommand,
    StoredGraphRevision,
    WorldGraphHead,
    WorldGraphRevision,
)
from dungeonmind.contracts.projection import (
    Admissibility,
    FocusKind,
    ProjectionFocus,
    ScopeMode,
    WorldGraphProjectionRequest,
)
from dungeonmind.contracts.projection_v2 import (
    ScopeModeV2,
    WorldGraphProjectionRequestV2,
)
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import (
    HeadNotFoundError,
    RevisionNotFoundError,
    ScopeResolutionError,
)
from dungeonmind.infrastructure.memory import (
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.world_object_vocabulary import (
    load_builtin_v3_descriptor,
)

WORLD_ID = "world:test"
NOW = datetime(2026, 8, 22, 18, 0, tzinfo=UTC)


class _FixedClock:
    def now(self):
        return NOW


def _empty_graph(world_id: str = WORLD_ID) -> dict:
    return {
        "world_id": world_id,
        "nodes": [],
        "relationships": [],
        "evidence_refs": [],
    }


def _publish(
    world_graph: InMemoryWorldGraphRepository,
    *,
    parent_revision_id: str | None = None,
    operation_id: str = "op:first",
    graph_world_id: str = WORLD_ID,
    created_at: datetime = NOW,
) -> WorldGraphRevision:
    return world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=parent_revision_id,
            expected_parent_revision_id=parent_revision_id,
            operation_ids=[operation_id],
            graph_schema="dm_union_graph_v1",
            graph_payload=_empty_graph(graph_world_id),
            created_at=created_at,
        )
    )


def _service(world_graph) -> WorldGraphProjectionService:
    return WorldGraphProjectionService(
        world_graph=world_graph,
        sources=InMemorySourceRepository(),
        graph_reader=UnionGraphV1SnapshotReader(),
        clock=_FixedClock(),
    )


def _world_request(*, revision_pin: str | None = None) -> WorldGraphProjectionRequestV2:
    return WorldGraphProjectionRequestV2(
        world_id=WORLD_ID,
        admissibility=Admissibility.GM,
        revision_pin=revision_pin,
        scope_mode=ScopeModeV2.WORLD,
    )


def test_unpinned_projection_resolves_and_reports_current_head():
    world_graph = InMemoryWorldGraphRepository()
    published = _publish(world_graph)

    result = _service(world_graph).project(_world_request())

    assert result.snapshot.revision_id == published.revision_id
    assert result.snapshot.head_revision_id == published.revision_id
    assert result.snapshot.is_head is True
    assert result.snapshot.projected_at == NOW
    assert result.graph.world_id == WORLD_ID
    assert result.graph.objects == {}
    assert result.graph.relationships == {}


def test_exact_historical_pin_is_repinable_while_current_head_is_reported():
    world_graph = InMemoryWorldGraphRepository()
    first = _publish(world_graph)
    second = _publish(
        world_graph,
        parent_revision_id=first.revision_id,
        operation_id="op:second",
        created_at=NOW + timedelta(seconds=1),
    )

    result = _service(world_graph).project(
        _world_request(revision_pin=first.revision_id)
    )

    assert result.snapshot.revision_id == first.revision_id
    assert result.snapshot.head_revision_id == second.revision_id
    assert result.snapshot.is_head is False


def test_projection_preserves_authorized_campaign_focus_and_admissibility_identity():
    world_graph = InMemoryWorldGraphRepository()
    published = _publish(world_graph)
    request = WorldGraphProjectionRequestV2(
        world_id=WORLD_ID,
        campaign_id="campaign:test",
        focus=ProjectionFocus(kind=FocusKind.SESSION, session_id="session:test"),
        admissibility=Admissibility.PLAYER,
        revision_pin=published.revision_id,
        query_text="context carried for successor retrieval",
        scope_mode=ScopeModeV2.CAMPAIGN,
    )

    result = _service(world_graph).project(request)

    assert result.snapshot.campaign_id == request.campaign_id
    assert result.snapshot.focus == request.focus
    assert result.snapshot.admissibility is Admissibility.PLAYER
    assert result.snapshot.scope_mode is ScopeModeV2.CAMPAIGN


def test_missing_world_head_fails_closed():
    with pytest.raises(HeadNotFoundError):
        _service(InMemoryWorldGraphRepository()).project(_world_request())


def test_missing_revision_pin_fails_closed():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)

    with pytest.raises(RevisionNotFoundError):
        _service(world_graph).project(_world_request(revision_pin="rev:not-present"))


def test_payload_world_mismatch_fails_closed():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph, graph_world_id="world:other")

    with pytest.raises(ScopeResolutionError) as excinfo:
        _service(world_graph).project(_world_request())

    assert excinfo.value.details["reason"] == "payload_world_mismatch"


class _RevisionWorldMismatchRepository:
    def get_head(self, world_id: str) -> WorldGraphHead:
        return WorldGraphHead(
            world_id=world_id,
            head_revision_id="rev:foreign",
            updated_at=NOW,
        )

    def get_revision(self, world_id: str, revision_id: str) -> StoredGraphRevision:
        return StoredGraphRevision(
            revision=WorldGraphRevision(
                world_id="world:other",
                revision_id=revision_id,
                parent_revision_id=None,
                created_at=NOW,
                operation_ids=["op:foreign"],
                graph_schema="dm_union_graph_v1",
                graph_payload_sha256="sha256:foreign",
            ),
            graph_payload=_empty_graph("world:other"),
        )


def test_repository_revision_world_mismatch_fails_before_graph_parse():
    with pytest.raises(ScopeResolutionError) as excinfo:
        _service(_RevisionWorldMismatchRepository()).project(_world_request())

    assert excinfo.value.details["reason"] == "revision_world_mismatch"

CAMPAIGN_A = "camp:alpha"
CAMPAIGN_B = "camp:beta"


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


def _v6_meta(
    assertion_id: str,
    *,
    evidence: tuple[str, ...],
    visibility: str = "player",
    campaign_scope: str | None,
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


def _v6_evidence_row(evidence_ref_id: str, artifact_id: str, revision_id: str) -> dict:
    return {
        "schema_version": "dm_evidence_ref_v2",
        "evidence_ref_id": evidence_ref_id,
        "source_artifact_id": artifact_id,
        "source_revision_id": revision_id,
        "source_domain_key": "buddy.worldbuilding",
        "source_domain": "worldbuilding",
        "evidence_role": "support",
        "can_open_source": True,
        "can_highlight_span": False,
        "session_id": None,
        "source_span_ref_id": None,
        "locator": f"fixture://{artifact_id}",
        "uri": None,
        "source_locator": None,
        "line_ref": None,
    }


def _v6_object(
    object_id: str,
    label: str,
    *,
    assertion_id: str,
    evidence_ref_id: str,
    campaign_scope: str | None,
    visibility: str = "player",
) -> dict:
    return {
        "object_id": object_id,
        "kind": "dnd5e:location",
        "label": label,
        "assertion_metadata": _v6_meta(
            assertion_id,
            evidence=(evidence_ref_id,),
            visibility=visibility,
            campaign_scope=campaign_scope,
        ),
        "aliases": [],
        "summary": None,
        "properties": [],
        "aspects": [],
    }


def _v6_payload() -> dict:
    return {
        "world_id": WORLD_ID,
        "semantic_profile": _v6_profile_ref(),
        "relationship_endpoint_aspect_schema": RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
        "objects": [
            _v6_object(
                "obj:world-tavern",
                "World Tavern",
                assertion_id="asrt:world-tavern",
                evidence_ref_id="ev:world",
                campaign_scope=None,
            ),
            _v6_object(
                "obj:alpha-keep",
                "Alpha Keep",
                assertion_id="asrt:alpha-keep",
                evidence_ref_id="ev:alpha",
                campaign_scope=CAMPAIGN_A,
            ),
            _v6_object(
                "obj:beta-crypt",
                "Beta Crypt",
                assertion_id="asrt:beta-crypt",
                evidence_ref_id="ev:beta",
                campaign_scope=CAMPAIGN_B,
            ),
            _v6_object(
                "obj:alpha-secret",
                "Alpha Secret Vault",
                assertion_id="asrt:alpha-secret",
                evidence_ref_id="ev:alpha",
                campaign_scope=CAMPAIGN_A,
                visibility="gm",
            ),
        ],
        "relationships": [],
        "evidence_refs": [
            _v6_evidence_row("ev:world", "src:world-lore", "srcrev:world-lore-v1"),
            _v6_evidence_row("ev:alpha", "src:alpha-notes", "srcrev:alpha-notes-v1"),
            _v6_evidence_row("ev:beta", "src:beta-notes", "srcrev:beta-notes-v1"),
        ],
    }


def _seed_v6_sources() -> InMemorySourceRepository:
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


def _v6_service(world_graph) -> WorldGraphProjectionService:
    return WorldGraphProjectionService(
        world_graph=world_graph,
        sources=_seed_v6_sources(),
        graph_reader=VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([_v6_descriptor()])
        ),
        clock=_FixedClock(),
    )


def _publish_v6(world_graph: InMemoryWorldGraphRepository) -> WorldGraphRevision:
    return world_graph.publish_revision(
        PublishRevisionCommand(
            world_id=WORLD_ID,
            parent_revision_id=None,
            expected_parent_revision_id=None,
            operation_ids=["op:v6-scope-fixture"],
            graph_schema=GRAPH_SCHEMA_V6,
            graph_payload=_v6_payload(),
            created_at=NOW,
        )
    )


def _v6_request(
    *,
    scope_mode: ScopeMode,
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


def _projected_object_ids(result) -> set[str]:
    return set(result.graph.objects.keys())


def test_v6_revision_resolves_and_projects_through_versioned_reader():
    """The service resolves an exact v6 revision and returns admitted content."""
    world_graph = InMemoryWorldGraphRepository()
    published = _publish_v6(world_graph)

    result = _v6_service(world_graph).project(
        _v6_request(scope_mode=ScopeModeV2.CAMPAIGN, campaign_id=CAMPAIGN_A)
    )

    assert result.snapshot.revision_id == published.revision_id
    assert result.snapshot.is_head is True
    assert result.graph.graph_schema == GRAPH_SCHEMA_V6
    assert result.graph.semantic_profile_ref is not None
    assert "obj:world-tavern" in _projected_object_ids(result)


def test_campaign_scope_admits_requested_campaign_plus_world_owned_only():
    world_graph = InMemoryWorldGraphRepository()
    _publish_v6(world_graph)

    result = _v6_service(world_graph).project(
        _v6_request(scope_mode=ScopeModeV2.CAMPAIGN, campaign_id=CAMPAIGN_A)
    )

    assert _projected_object_ids(result) == {
        "obj:world-tavern",
        "obj:alpha-keep",
        "obj:alpha-secret",
    }
    assert result.snapshot.scope_mode is ScopeModeV2.CAMPAIGN
    assert result.snapshot.campaign_id == CAMPAIGN_A


def test_world_scope_remains_world_owned_only():
    """The original v1 WORLD meaning is deliberately unchanged."""
    world_graph = InMemoryWorldGraphRepository()
    _publish_v6(world_graph)

    result = _v6_service(world_graph).project(_v6_request(scope_mode=ScopeModeV2.WORLD))

    assert _projected_object_ids(result) == {"obj:world-tavern"}


def test_world_cross_campaign_lens_admits_all_campaigns_in_one_exact_revision():
    world_graph = InMemoryWorldGraphRepository()
    published = _publish_v6(world_graph)

    result = _v6_service(world_graph).project(
        _v6_request(scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN)
    )

    assert _projected_object_ids(result) == {
        "obj:world-tavern",
        "obj:alpha-keep",
        "obj:beta-crypt",
        "obj:alpha-secret",
    }
    # One exact revision read: the cross-campaign lens is not a fan-out merge.
    assert result.snapshot.revision_id == published.revision_id
    assert result.snapshot.scope_mode is ScopeModeV2.WORLD_CROSS_CAMPAIGN
    assert result.snapshot.campaign_id is None
    assert result.snapshot.schema_version == "dm_projection_snapshot_v2"


def test_world_cross_campaign_player_admissibility_still_fails_closed():
    world_graph = InMemoryWorldGraphRepository()
    _publish_v6(world_graph)

    player = _v6_service(world_graph).project(
        _v6_request(
            scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
            admissibility=Admissibility.PLAYER,
        )
    )
    gm = _v6_service(world_graph).project(
        _v6_request(
            scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
            admissibility=Admissibility.GM,
        )
    )

    assert "obj:alpha-secret" not in _projected_object_ids(player)
    assert "obj:alpha-secret" in _projected_object_ids(gm)
    # Widening the campaign lens must not leak hidden identities publicly.
    exclusion = player.scoped_graph.object_exclusions["obj:alpha-secret"]
    assert exclusion.out_of_scope is True
    assert public_coverage_gaps_for_exclusion(exclusion) == ([], [])


def test_world_cross_campaign_requires_no_campaign_id():
    with pytest.raises(ValidationError, match="campaign_id"):
        _v6_request(
            scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
            campaign_id=CAMPAIGN_A,
        )


def test_cross_campaign_scope_contradiction_fails_closed_at_projection():
    """An explicit mode that contradicts campaign_id fails closed, never guesses."""
    with pytest.raises(ScopeResolutionError):
        CampaignScope.resolve(
            scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
            campaign_id=CAMPAIGN_A,
        )
    with pytest.raises(ScopeResolutionError):
        CampaignScope.resolve(scope_mode=ScopeModeV2.CAMPAIGN, campaign_id=None)


def test_v1_contract_vocabulary_is_frozen_without_cross_campaign():
    """v1 is frozen: a v1 reader must reject what only v2 accepts."""
    assert [mode.value for mode in ScopeMode] == ["campaign", "world"]
    with pytest.raises(ValidationError):
        WorldGraphProjectionRequest.model_validate(
            {
                "world_id": WORLD_ID,
                "admissibility": "gm",
                "scope_mode": "world_cross_campaign",
            }
        )


def test_v2_contract_accepts_the_cross_campaign_vocabulary():
    request = WorldGraphProjectionRequestV2.model_validate(
        {
            "world_id": WORLD_ID,
            "admissibility": "gm",
            "scope_mode": "world_cross_campaign",
        }
    )
    assert request.scope_mode is ScopeModeV2.WORLD_CROSS_CAMPAIGN
    assert request.schema_version == "dm_projection_request_v2"
