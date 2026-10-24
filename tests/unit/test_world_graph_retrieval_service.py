"""Service-level tests for the direct World Graph retrieval seam (R.2).

Every test runs through the synthetic ``dm_union_graph_v6`` authority fixture
(world-owned + two campaigns + GM-only content + broken-provenance row) parsed
by ``VersionedUnionGraphSnapshotReader`` under the bundled D&D v3 profile, and
composed through the landed v2 projection service.
"""

from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

import dungeonmind.application.world_graph_retrieval as retrieval_module
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
    SelectedObjectCompleteness,
    SelectedSourceAnchorIndexRequest,
    SourceAnchorIndexRequest,
    SourceContextIndexRequest,
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
from dungeonmind.contracts.knowledge_assertion import TemporalScopeKind
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
from tests.unit.null_reviewed_world_initialization import (
    NullReviewedWorldInitializationRepository,
)

WORLD_ID = "world:test"
CAMPAIGN_A = "camp:alpha"
CAMPAIGN_B = "camp:beta"
NOW = datetime(2026, 8, 22, 18, 0, tzinfo=UTC)
HUB_OBJECT_ID = "obj:hub-plaza"
ISOLATED_OBJECT_ID = "obj:isolated-well"
HUB_DEGREE = 30
HUB_PROPERTY_COUNT = 33
HUB_ANCHOR_COUNT = 33
HUB_OUTGOING = 15
_HARD_RETRIEVAL_BOUNDS = RetrievalBounds(
    max_objects=12,
    max_relationships=24,
    max_assertions=32,
    max_anchors=32,
)


class _FixedClock:
    def now(self):
        return NOW


class _CountingProjectionService(WorldGraphProjectionService):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.project_calls = 0

    def open_read_context(self, request):
        self.project_calls += 1
        return super().open_read_context(request)


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
    session_refs: list[str] | None = None,
    temporal_scope: dict | None = None,
) -> dict:
    return {
        "schema_version": "dm_knowledge_assertion_metadata_v1",
        "assertion_id": assertion_id,
        "campaign_scope": campaign_scope,
        "visibility": visibility,
        "epistemic_kind": "asserted",
        "canon_state": "canonical",
        "evidence_ref_ids": list(evidence),
        "session_refs": list(session_refs or []),
        "temporal_scope": temporal_scope
        or {"schema_version": "dm_temporal_scope_ref_v1", "kind": "unknown"},
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
    properties: list[tuple[str, object, str, str] | tuple[str, object, str, str, str]]
    | None = None,
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
                "property_term": item[0],
                "value": item[1],
                "assertion_metadata": _meta(
                    item[2],
                    evidence=(item[4] if len(item) > 4 else evidence,),
                    visibility=item[3],
                    campaign_scope=campaign_scope,
                ),
            }
            for item in (properties or [])
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
    session_refs: list[str] | None = None,
    temporal_scope: dict | None = None,
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
            session_refs=session_refs,
            temporal_scope=temporal_scope,
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


def _complete_object_payload() -> dict:
    payload = _payload()
    payload["objects"].append(
        _object(
            ISOLATED_OBJECT_ID,
            "Isolated Well",
            assertion_id="asrt:isolated-well",
            evidence="ev:world",
            campaign_scope=None,
            properties=[
                ("dnd5e:depth", "shallow", "asrt:prop-isolated-depth", "player"),
            ],
        )
    )
    payload["objects"][-1]["aspects"] = [
        {
            "aspect_key": "site",
            "kind": "dnd5e:location",
            "assertion_metadata": _meta(
                "asrt:isolated-well-site",
                evidence=("ev:world",),
                campaign_scope=None,
            ),
        }
    ]
    timeless = {
        "schema_version": "dm_temporal_scope_ref_v1",
        "kind": "world_timeless",
    }
    hub_properties: list[tuple[str, object, str, str] | tuple[str, object, str, str, str]] = [
        (
            "dnd5e:population",
            "crowded",
            "asrt:prop-hub-population",
            "player",
            "ev:hub-anchor-00",
        ),
    ]
    for index in range(HUB_PROPERTY_COUNT - 1):
        hub_properties.append(
            (
                f"dnd5e:tag_{index:02d}",
                f"v{index:02d}",
                f"asrt:prop-hub-tag-{index:02d}",
                "player",
                f"ev:hub-anchor-{index + 1:02d}",
            )
        )
    payload["objects"].append(
        _object(
            HUB_OBJECT_ID,
            "Hub Plaza",
            assertion_id="asrt:hub-plaza",
            evidence="ev:world",
            campaign_scope=None,
            properties=hub_properties,
        )
    )
    # Override the first hub property's temporal scope after object build.
    for prop in payload["objects"][-1]["properties"]:
        if prop["property_term"] == "dnd5e:population":
            prop["assertion_metadata"]["temporal_scope"] = timeless
            prop["assertion_metadata"]["session_refs"] = ["sess:world-fair"]
            break
    for index in range(HUB_DEGREE):
        leaf_id = f"obj:hub-leaf-{index:02d}"
        payload["objects"].append(
            _object(
                leaf_id,
                f"Spoke {index:02d}",
                assertion_id=f"asrt:hub-leaf-{index:02d}",
                evidence="ev:world",
                campaign_scope=None,
            )
        )
        if index < HUB_OUTGOING:
            payload["relationships"].append(
                _relationship(
                    f"rel:hub-out-{index:02d}",
                    HUB_OBJECT_ID,
                    leaf_id,
                    "dnd5e:near",
                    assertion_id=f"asrt:rel-hub-out-{index:02d}",
                    evidence="ev:world",
                )
            )
        else:
            inbound_index = index - HUB_OUTGOING
            payload["relationships"].append(
                _relationship(
                    f"rel:hub-in-{inbound_index:02d}",
                    leaf_id,
                    HUB_OBJECT_ID,
                    "dnd5e:connected_to",
                    assertion_id=f"asrt:rel-hub-in-{inbound_index:02d}",
                    evidence="ev:world",
                )
            )
    payload["relationships"].append(
        _relationship(
            "rel:hub-keep-timed",
            HUB_OBJECT_ID,
            "obj:alpha-keep",
            "dnd5e:located_in",
            assertion_id="asrt:rel-hub-keep-timed",
            evidence="ev:alpha",
            campaign_scope=CAMPAIGN_A,
            session_refs=["sess:alpha-12"],
            temporal_scope={
                "schema_version": "dm_temporal_scope_ref_v1",
                "kind": "fictional_time_ref",
                "fictional_time_ref": {
                    "schema_version": "dm_fictional_time_anchor_ref_v1",
                    "bundle_id": "ftb:alpha-siege",
                    "campaign_id": CAMPAIGN_A,
                    "anchor_id": "fta:siege-night",
                },
            },
        )
    )
    for index in range(HUB_ANCHOR_COUNT):
        payload["evidence_refs"].append(
            _evidence_row(
                f"ev:hub-anchor-{index:02d}",
                f"src:hub-anchor-{index:02d}",
                f"srcrev:hub-anchor-{index:02d}",
                span=f"span:hub-{index:02d}",
            )
        )
    return payload


def _put_source(
    sources: InMemorySourceRepository,
    *,
    artifact_id: str,
    revision_id: str,
    campaign_id: str | None,
) -> None:
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


def _seed_sources() -> InMemorySourceRepository:
    sources = InMemorySourceRepository()
    for artifact_id, revision_id, campaign_id in (
        ("src:world-lore", "srcrev:world-lore-v1", None),
        ("src:alpha-notes", "srcrev:alpha-notes-v1", CAMPAIGN_A),
        ("src:beta-notes", "srcrev:beta-notes-v1", CAMPAIGN_B),
    ):
        _put_source(
            sources,
            artifact_id=artifact_id,
            revision_id=revision_id,
            campaign_id=campaign_id,
        )
    return sources


def _complete_object_sources() -> InMemorySourceRepository:
    sources = _seed_sources()
    for index in range(HUB_ANCHOR_COUNT):
        _put_source(
            sources,
            artifact_id=f"src:hub-anchor-{index:02d}",
            revision_id=f"srcrev:hub-anchor-{index:02d}",
            campaign_id=None,
        )
    return sources


def _services(
    world_graph: InMemoryWorldGraphRepository,
    sources: InMemorySourceRepository | None = None,
) -> tuple[WorldGraphRetrievalService, _CountingProjectionService]:
    sources = sources if sources is not None else _seed_sources()
    projection = _CountingProjectionService(
        world_graph=world_graph,
        sources=sources,
        graph_reader=VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([_v6_descriptor()])
        ),
        reviewed_world_initializations=NullReviewedWorldInitializationRepository(),
        clock=_FixedClock(),
    )
    return WorldGraphRetrievalService(projection=projection, sources=sources), projection


def _complete_object_services(
    world_graph: InMemoryWorldGraphRepository,
) -> tuple[WorldGraphRetrievalService, _CountingProjectionService]:
    return _services(world_graph, sources=_complete_object_sources())


def _recap_context_services(
    *, extra_recap: bool = False, recap_digest: str = "ab" * 32,
    recap_can_open: bool = True, beta_recap: bool = False,
):
    """Synthetic recap pair; no private recap bytes or real source IDs."""
    payload = _payload()
    recap_evidence = next(
        row for row in payload["evidence_refs"] if row["evidence_ref_id"] == "ev:alpha"
    )
    recap_evidence.update(
        source_domain_key="fixture.recap",
        source_domain="session_recap",
        session_id="session-22",
        can_open_source=recap_can_open,
    )
    if beta_recap:
        beta_evidence = next(
            row for row in payload["evidence_refs"] if row["evidence_ref_id"] == "ev:beta"
        )
        beta_evidence.update(
            source_domain_key="fixture.recap",
            source_domain="session_recap",
            session_id="session-23",
        )
    if extra_recap:
        payload["evidence_refs"].append(
            {
                **recap_evidence,
                "evidence_ref_id": "ev:alpha-extra",
                "source_artifact_id": "src:alpha-extra",
                "source_revision_id": "srcrev:alpha-extra-v1",
            }
        )
        payload["objects"].append(
            _object(
                "obj:alpha-extra",
                "Extra Recap Location",
                assertion_id="asrt:alpha-extra",
                evidence="ev:alpha-extra",
                campaign_scope=CAMPAIGN_A,
            )
        )
    graph = InMemoryWorldGraphRepository()
    published = _publish(graph, payload)
    sources = InMemorySourceRepository()
    ordinary_sources = [("src:world-lore", "srcrev:world-lore-v1", None)]
    if not beta_recap:
        ordinary_sources.append(("src:beta-notes", "srcrev:beta-notes-v1", CAMPAIGN_B))
    for artifact_id, revision_id, campaign_id in ordinary_sources:
        _put_source(
            sources,
            artifact_id=artifact_id,
            revision_id=revision_id,
            campaign_id=campaign_id,
        )

    def put_recap(
        artifact_id: str,
        revision_id: str,
        *,
        campaign_id: str = CAMPAIGN_A,
        session_id: str = "session-22",
        world_id: str = WORLD_ID,
    ) -> None:
        sources.put_artifact(
            SourceArtifactV2(
                source_artifact_id=artifact_id,
                source_domain_key="fixture.recap",
                source_domain=SourceDomain.SESSION_RECAP,
                world_id=world_id,
                campaign_id=campaign_id,
                session_id=session_id,
                uri=f"fixture://{artifact_id}",
                current_revision_id=revision_id,
                authority=None,
                visibility=Visibility.GM,
                artifact_kind="recap_markdown",
                document_class="recap",
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
                content_sha256=recap_digest,
                body_storage="external",
                locator=f"fixture://{artifact_id}/revision",
                created_at=NOW,
            )
        )

    put_recap("src:alpha-notes", "srcrev:alpha-notes-v1")
    put_recap("src:catalog-only", "srcrev:catalog-only-v1")
    put_recap("src:foreign-catalog", "srcrev:foreign-catalog-v1", world_id="world:foreign")
    if beta_recap:
        put_recap(
            "src:beta-notes", "srcrev:beta-notes-v1",
            campaign_id=CAMPAIGN_B, session_id="session-23",
        )
    if extra_recap:
        put_recap("src:alpha-extra", "srcrev:alpha-extra-v1")
    service, projection = _services(graph, sources)
    return service, projection, published, graph


def test_recap_context_pair_selection_requires_admitted_provenance():
    service, projection, published, _graph = _recap_context_services()
    request = _campaign_a(revision_pin=published.revision_id)
    result, context = service._establish(request)

    pairs = service._admitted_recap_source_pairs(result, context)

    assert len(pairs) == 1
    assert pairs[0].source_artifact_id == "src:alpha-notes"
    assert pairs[0].source_revision_id == "srcrev:alpha-notes-v1"
    assert pairs[0].source_uri == "fixture://src:alpha-notes/revision"
    assert pairs[0].content_sha256 == "ab" * 32
    assert pairs[0].session_id == "session-22"
    assert projection.project_calls == 1
    assert "catalog-only" not in repr(pairs)

    wrong_scope, wrong_context = service._establish(
        _request(
            scope_mode=ScopeModeV2.CAMPAIGN,
            campaign_id=CAMPAIGN_B,
            revision_pin=published.revision_id,
        )
    )
    assert service._admitted_recap_source_pairs(wrong_scope, wrong_context) == ()


def test_recap_context_cross_campaign_union_preserves_world_and_campaign_scopes():
    service, _projection, published, graph = _recap_context_services(beta_recap=True)
    revision_pin = published.revision_id
    cross = _request(
        scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN, revision_pin=revision_pin
    )
    world = _request(scope_mode=ScopeModeV2.WORLD, revision_pin=revision_pin)
    campaign_a = _campaign_a(revision_pin=revision_pin)
    campaign_b = _request(
        scope_mode=ScopeModeV2.CAMPAIGN,
        campaign_id=CAMPAIGN_B,
        revision_pin=revision_pin,
    )

    cross_index = service.list_source_context_index(SourceContextIndexRequest(cross))
    assert cross_index.status == "complete"
    assert {entry.source_artifact_id for entry in cross_index.entries} == {
        "src:alpha-notes", "src:beta-notes"
    }
    assert {entry.campaign_id for entry in cross_index.entries} == {CAMPAIGN_A, CAMPAIGN_B}
    assert all(entry.world_id == WORLD_ID for entry in cross_index.entries)
    assert "catalog-only" not in repr(cross_index.entries)
    assert "foreign-catalog" not in repr(cross_index.entries)
    rejected, _projection, rejected_revision, _graph = _recap_context_services(
        beta_recap=True, recap_can_open=False
    )
    rejected_cross = _request(
        scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
        revision_pin=rejected_revision.revision_id,
    )
    assert {
        entry.source_artifact_id
        for entry in rejected.list_source_context_index(
            SourceContextIndexRequest(rejected_cross)
        ).entries
    } == {"src:beta-notes"}

    assert service.list_source_context_index(SourceContextIndexRequest(world)).entries == ()
    a_entry, = service.list_source_context_index(SourceContextIndexRequest(campaign_a)).entries
    b_entry, = service.list_source_context_index(SourceContextIndexRequest(campaign_b)).entries
    assert a_entry.source_artifact_id == "src:alpha-notes"
    assert b_entry.source_artifact_id == "src:beta-notes"
    cross_by_artifact = {entry.source_artifact_id: entry for entry in cross_index.entries}
    cross_result, cross_context = service._establish(cross)
    alpha_pair = next(
        pair for pair in service._admitted_recap_source_pairs(cross_result, cross_context)
        if pair.source_artifact_id == "src:alpha-notes"
    )
    alpha_selector = cross_by_artifact["src:alpha-notes"].section_selector
    selector_identity = retrieval_module.canonical_sha256(alpha_selector.identity_payload())
    assert retrieval_module._derive_context_anchor_id(
        snapshot=cross_result.snapshot,
        pair=replace(alpha_pair, campaign_id=CAMPAIGN_B),
        section_selector_identity=selector_identity,
    ) != cross_by_artifact["src:alpha-notes"].context_anchor_id
    for local, opposite in ((a_entry, campaign_b), (b_entry, campaign_a)):
        cross_entry = cross_by_artifact[local.source_artifact_id]
        assert cross_entry.context_anchor_id != local.context_anchor_id
        assert service.resolve_source_context(
            cross, context_anchor_id=cross_entry.context_anchor_id
        ).found
        assert not service.resolve_source_context(
            opposite, context_anchor_id=cross_entry.context_anchor_id
        ).found
        assert not service.resolve_source_context(
            world, context_anchor_id=cross_entry.context_anchor_id
        ).found
        assert not service.resolve_source_context(
            cross, context_anchor_id=local.context_anchor_id
        ).found

    child = _publish(
        graph, _payload(), parent_revision_id=revision_pin,
        operation_id="op:cross-recap-child",
    )
    stale_cross = cross.model_copy(update={"revision_pin": child.revision_id})
    assert not service.resolve_source_context(
        stale_cross,
        context_anchor_id=cross_index.entries[0].context_anchor_id,
    ).found


def test_recap_context_identity_is_distinct_and_revision_scope_bound():
    service, _projection, published, _graph = _recap_context_services()
    request = _campaign_a(revision_pin=published.revision_id)
    result, context = service._establish(request)
    pair = service._admitted_recap_source_pairs(result, context)[0]

    token = retrieval_module._derive_context_anchor_id(
        snapshot=result.snapshot,
        pair=pair,
        section_selector_identity="test-recap-section-v1",
    )
    assert token.startswith(retrieval_module.CONTEXT_ANCHOR_ID_PREFIX)
    assert not token.startswith(SOURCE_ANCHOR_ID_PREFIX)
    assert token == retrieval_module._derive_context_anchor_id(
        snapshot=result.snapshot,
        pair=pair,
        section_selector_identity="test-recap-section-v1",
    )
    assert token != retrieval_module._derive_context_anchor_id(
        snapshot=result.snapshot,
        pair=pair,
        section_selector_identity="different-section",
    )
    assert token != retrieval_module._derive_context_anchor_id(
        snapshot=result.snapshot,
        pair=replace(pair, campaign_id=CAMPAIGN_B),
        section_selector_identity="test-recap-section-v1",
    )
    assert token != retrieval_module._derive_context_anchor_id(
        snapshot=result.snapshot.model_copy(
            update={"campaign_id": None, "scope_mode": ScopeModeV2.WORLD}
        ),
        pair=pair,
        section_selector_identity="test-recap-section-v1",
    )
    assert token != retrieval_module._derive_context_anchor_id(
        snapshot=result.snapshot.model_copy(update={"revision_id": "rev:other", "is_head": False}),
        pair=pair,
        section_selector_identity="test-recap-section-v1",
    )


def test_recap_context_index_and_resolution_are_context_only():
    service, projection, published, graph = _recap_context_services()
    pinned = _campaign_a(revision_pin=published.revision_id)
    index = service.list_source_context_index(SourceContextIndexRequest(pinned))

    assert index.status == "complete"
    assert index.eligible_count == 1
    descriptor = index.entries[0]
    assert descriptor.schema_version == "dm_recap_source_context_v1"
    assert descriptor.world_id == WORLD_ID
    assert descriptor.campaign_id == CAMPAIGN_A
    assert descriptor.graph_revision_id == published.revision_id
    assert descriptor.source_artifact_id == "src:alpha-notes"
    assert descriptor.source_revision_id == "srcrev:alpha-notes-v1"
    assert descriptor.source_uri == "fixture://src:alpha-notes/revision"
    assert descriptor.content_sha256 == "ab" * 32
    assert descriptor.section_selector.expected_session_id == "session-22"
    assert descriptor.section_selector.expected_heading == "# Session 22 Recap"
    assert descriptor.section_selector.kind == "recap_section"
    assert descriptor.section_selector.policy == "markdown-session-recap-v1"
    assert descriptor.context_anchor_id.startswith(retrieval_module.CONTEXT_ANCHOR_ID_PREFIX)
    assert not hasattr(descriptor, "evidence_ref_id")
    assert not hasattr(descriptor, "supporting_assertion_ids")
    assert not hasattr(descriptor, "body")
    assert not hasattr(descriptor, "start_line")
    assert projection.project_calls == 1

    resolved = service.resolve_source_context(
        pinned, context_anchor_id=descriptor.context_anchor_id
    )
    assert resolved.found and resolved.context == descriptor
    assert service.resolve_source_context(
        pinned, context_anchor_id=f"{retrieval_module.CONTEXT_ANCHOR_ID_PREFIX}{'0' * 64}"
    ).found is False
    assert service.resolve_source_anchor(
        pinned, anchor_id=descriptor.context_anchor_id
    ).found is False
    assert service.get_evidence(
        pinned,
        target=EvidenceTarget(kind="assertion", target_id=descriptor.context_anchor_id),
    ).found is False
    assert service.resolve_source_context(
        _world().model_copy(update={"revision_pin": published.revision_id}),
        context_anchor_id=descriptor.context_anchor_id,
    ).found is False
    assert service.resolve_source_context(
        _request(
            scope_mode=ScopeModeV2.CAMPAIGN,
            campaign_id=CAMPAIGN_B,
            revision_pin=published.revision_id,
        ),
        context_anchor_id=descriptor.context_anchor_id,
    ).found is False

    second = _publish(
        graph,
        _payload(),
        parent_revision_id=published.revision_id,
        operation_id="op:recap-second",
    )
    assert service.resolve_source_context(
        _campaign_a(revision_pin=second.revision_id),
        context_anchor_id=descriptor.context_anchor_id,
    ).found is False


def test_recap_context_request_rejects_non_gm_and_unpinned():
    service, _projection, published, _graph = _recap_context_services()
    with pytest.raises(ValueError, match="exact revision pin"):
        SourceContextIndexRequest(_campaign_a())
    with pytest.raises(ValueError, match="GM admissibility"):
        SourceContextIndexRequest(
            _campaign_a(admissibility=Admissibility.PLAYER, revision_pin=published.revision_id)
        )
    with pytest.raises(ValueError, match="GM admissibility"):
        SourceContextIndexRequest(
            _request(
                scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
                admissibility=Admissibility.PLAYER,
                revision_pin=published.revision_id,
            )
        )
    with pytest.raises(ValueError, match="GM admissibility"):
        service.resolve_source_context(
            _campaign_a(
                admissibility=Admissibility.PLAYER,
                revision_pin=published.revision_id,
            ),
            context_anchor_id=f"{retrieval_module.CONTEXT_ANCHOR_ID_PREFIX}{'0' * 64}",
        )


def test_recap_context_index_overflow_is_empty_not_partial():
    service, _projection, published, _graph = _recap_context_services(extra_recap=True)
    request = SourceContextIndexRequest(
        _campaign_a(revision_pin=published.revision_id), max_entries=1
    )
    index = service.list_source_context_index(request)
    assert index.status == "overflow"
    assert index.eligible_count == 2
    assert index.entries == ()


def test_recap_context_digest_change_invalidates_token():
    first, _projection, first_revision, _graph = _recap_context_services()
    first_request = _campaign_a(revision_pin=first_revision.revision_id)
    token = first.list_source_context_index(
        SourceContextIndexRequest(first_request)
    ).entries[0].context_anchor_id

    changed, _projection, changed_revision, _graph = _recap_context_services(
        recap_digest="cd" * 32
    )
    changed_request = _campaign_a(revision_pin=changed_revision.revision_id)
    assert changed.resolve_source_context(
        changed_request, context_anchor_id=token
    ).found is False


def test_recap_context_never_infers_domain_from_opaque_key():
    graph = InMemoryWorldGraphRepository()
    published = _publish(graph)
    service, _projection = _services(graph)
    index = service.list_source_context_index(
        SourceContextIndexRequest(_campaign_a(revision_pin=published.revision_id))
    )
    assert index.status == "complete"
    assert index.entries == ()


def test_recap_context_does_not_bypass_source_openability_flag():
    service, _projection, published, _graph = _recap_context_services(
        recap_can_open=False
    )
    index = service.list_source_context_index(
        SourceContextIndexRequest(_campaign_a(revision_pin=published.revision_id))
    )
    assert index.entries == ()


def test_recap_v1_descriptor_and_id_match_frozen_prechange_output():
    service, _projection, published, _graph = _recap_context_services()
    pinned = _campaign_a(revision_pin=published.revision_id)
    expected = {
        "campaign_id": CAMPAIGN_A,
        "content_sha256": "ab" * 32,
        "context_anchor_id": (
            "dm-context-anchor:v1:"
            "3070342db692edda2e2591557e68c99a7c1aca6fc623bbdd55b5d8725b345dd1"
        ),
        "graph_revision_id": "rev:9ac160f730afa9439f4c2cb7308d3750",
        "schema_version": "dm_recap_source_context_v1",
        "section_selector": {
            "expected_heading": "# Session 22 Recap",
            "expected_session_id": "session-22",
            "kind": "recap_section",
            "policy": "markdown-session-recap-v1",
            "schema_version": "dm_recap_context_section_selector_v1",
        },
        "source_artifact_id": "src:alpha-notes",
        "source_revision_id": "srcrev:alpha-notes-v1",
        "source_uri": "fixture://src:alpha-notes/revision",
        "world_id": WORLD_ID,
    }
    default = service.list_source_context_index(SourceContextIndexRequest(pinned))
    explicit = service.list_source_context_index(SourceContextIndexRequest(
        pinned, selector_policy="markdown-session-recap-v1",
    ))
    assert default == explicit
    assert asdict(default.entries[0]) == expected
    service.list_source_context_index(SourceContextIndexRequest(
        pinned, selector_policy="markdown-session-recap-v2",
    ))
    assert service.list_source_context_index(SourceContextIndexRequest(pinned)) == default
    resolved = service.resolve_source_context(
        pinned, context_anchor_id=expected["context_anchor_id"], allow_selector_v2=True,
    )
    assert resolved.found and asdict(resolved.context) == expected


def test_recap_v2_explicit_discovery_and_saved_id_policy_resolution(monkeypatch):
    service, _projection, published, _graph = _recap_context_services()
    pinned = _campaign_a(revision_pin=published.revision_id)

    def no_body_read(*_args, **_kwargs):
        pytest.fail("Core context discovery/resolution must not open source bodies")

    monkeypatch.setattr(Path, "read_bytes", no_body_read)
    monkeypatch.setattr(Path, "read_text", no_body_read)
    v1 = service.list_source_context_index(SourceContextIndexRequest(pinned)).entries[0]
    v2 = service.list_source_context_index(SourceContextIndexRequest(
        pinned, selector_policy="markdown-session-recap-v2",
    )).entries[0]
    assert isinstance(v1, retrieval_module.RecapSourceContextV1)
    assert isinstance(v2, retrieval_module.RecapSourceContextV2)
    assert v2.schema_version == "dm_recap_source_context_v2"
    assert v2.context_anchor_id.startswith("dm-context-anchor:v2:")
    assert v2.context_anchor_id != v1.context_anchor_id
    assert v2.section_selector.identity_payload() == {
        "schema_version": "dm_recap_context_section_selector_v2",
        "kind": "recap_section",
        "policy": "markdown-session-recap-v2",
        "expected_session_id": "session-22",
        "canonical_heading": "# Session 22 Recap",
        "legacy_session_heading": "## Session 22:",
        "legacy_recap_marker": "**Recap**:",
    }
    for field in ("world_id", "campaign_id", "graph_revision_id", "source_artifact_id",
                  "source_revision_id", "source_uri", "content_sha256"):
        assert getattr(v2, field) == getattr(v1, field)
    assert not hasattr(v2, "body") and not hasattr(v2, "selected_form")
    assert not service.resolve_source_context(pinned, context_anchor_id=v2.context_anchor_id).found
    assert service.resolve_source_context(
        pinned, context_anchor_id=v2.context_anchor_id, allow_selector_v2=True,
    ).context == v2
    assert service.resolve_source_context(
        pinned, context_anchor_id=v1.context_anchor_id, allow_selector_v2=True,
    ).context == v1
    assert not service.resolve_source_context(
        pinned, context_anchor_id=v1.context_anchor_id.replace(":v1:", ":v2:"),
        allow_selector_v2=True,
    ).found
    assert not service.resolve_source_context(
        pinned, context_anchor_id=v2.context_anchor_id.replace(":v2:", ":v3:"),
        allow_selector_v2=True,
    ).found
    assert not service.resolve_source_anchor(pinned, anchor_id=v2.context_anchor_id).found
    assert not service.get_evidence(
        pinned, target=EvidenceTarget(kind="assertion", target_id=v2.context_anchor_id),
    ).found


@pytest.mark.parametrize("policy", ["markdown-session-recap-v3", "", None, True, []])
def test_recap_context_rejects_unsupported_discovery_policy(policy):
    with pytest.raises(ValueError, match=r"unsupported.*selector policy"):
        SourceContextIndexRequest(_campaign_a(revision_pin="rev:pinned"), selector_policy=policy)


@pytest.mark.parametrize("capability", ["true", 1, None])
def test_recap_context_v2_capability_requires_boolean(capability):
    service, _projection, published, _graph = _recap_context_services()
    with pytest.raises(ValueError, match="explicit boolean"):
        service.resolve_source_context(
            _campaign_a(revision_pin=published.revision_id),
            context_anchor_id="dm-context-anchor:v2:forged", allow_selector_v2=capability,
        )


@pytest.mark.parametrize("changes", [
    {"expected_session_id": "session-0"},
    {"canonical_heading": "# Session 23 Recap"},
    {"legacy_session_heading": "## Session 22"},
    {"legacy_recap_marker": "Recap:"},
    {"policy": "markdown-session-recap-v1"},
    {"schema_version": "dm_recap_context_section_selector_v1"},
    {"kind": "whole_document"},
])
def test_recap_v2_selector_accepts_only_authorized_literal_policy(changes):
    selector = retrieval_module.RecapContextSectionSelectorV2(
        expected_session_id="session-22", canonical_heading="# Session 22 Recap",
        legacy_session_heading="## Session 22:", legacy_recap_marker="**Recap**:",
    )
    with pytest.raises(ValueError, match="exact session policy"):
        replace(selector, **changes)


def test_recap_v2_preserves_scope_order_overflow_and_openability():
    service, _projection, published, graph = _recap_context_services(beta_recap=True)
    cross = _request(scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
                     revision_pin=published.revision_id)
    index = service.list_source_context_index(SourceContextIndexRequest(
        cross, selector_policy="markdown-session-recap-v2",
    ))
    assert index.status == "complete" and index.eligible_count == 2
    assert [entry.source_artifact_id for entry in index.entries] == [
        "src:alpha-notes", "src:beta-notes",
    ]
    assert all(isinstance(entry, retrieval_module.RecapSourceContextV2) for entry in index.entries)
    overflow = service.list_source_context_index(SourceContextIndexRequest(
        cross, max_entries=1, selector_policy="markdown-session-recap-v2",
    ))
    assert overflow.status == "overflow" and overflow.eligible_count == 2 and not overflow.entries
    alpha = index.entries[0]
    for wrong_scope in (
        _campaign_a(revision_pin=published.revision_id),
        _request(scope_mode=ScopeModeV2.WORLD, revision_pin=published.revision_id),
        _request(scope_mode=ScopeModeV2.CAMPAIGN, campaign_id=CAMPAIGN_B,
                 revision_pin=published.revision_id),
    ):
        assert not service.resolve_source_context(
            wrong_scope, context_anchor_id=alpha.context_anchor_id, allow_selector_v2=True,
        ).found
    with pytest.raises(ValueError, match="GM admissibility"):
        service.resolve_source_context(
            cross.model_copy(update={"admissibility": Admissibility.PLAYER}),
            context_anchor_id=alpha.context_anchor_id, allow_selector_v2=True,
        )
    with pytest.raises(ValueError, match="exact revision pin"):
        SourceContextIndexRequest(_campaign_a(), selector_policy="markdown-session-recap-v2")
    denied, _projection, revision, _graph = _recap_context_services(recap_can_open=False)
    assert not denied.list_source_context_index(SourceContextIndexRequest(
        _campaign_a(revision_pin=revision.revision_id), selector_policy="markdown-session-recap-v2",
    )).entries
    ordinary_graph = InMemoryWorldGraphRepository()
    ordinary_revision = _publish(ordinary_graph)
    ordinary, _projection = _services(ordinary_graph)
    assert not ordinary.list_source_context_index(SourceContextIndexRequest(
        _campaign_a(revision_pin=ordinary_revision.revision_id),
        selector_policy="markdown-session-recap-v2",
    )).entries
    child = _publish(graph, _payload(), parent_revision_id=published.revision_id,
                     operation_id="op:v2-context-child")
    assert not service.resolve_source_context(
        cross.model_copy(update={"revision_pin": child.revision_id}),
        context_anchor_id=alpha.context_anchor_id, allow_selector_v2=True,
    ).found


@pytest.mark.parametrize("mutation", ["status", "uri", "digest", "revision_binding"])
def test_recap_v2_revalidates_current_source_standing_and_tuple(mutation):
    service, _projection, published, _graph = _recap_context_services()
    pinned = _campaign_a(revision_pin=published.revision_id)
    old = service.list_source_context_index(SourceContextIndexRequest(
        pinned, selector_policy="markdown-session-recap-v2",
    )).entries[0]
    sources = service._sources
    if mutation == "status":
        artifact = sources.get_artifact(old.source_artifact_id)
        sources._artifacts[old.source_artifact_id] = artifact.model_copy(
            update={"status": SourceStatus.SUPERSEDED}
        )
    else:
        revision = sources.get_revision(old.source_revision_id)
        changes = {"uri": {"locator": "fixture://changed/revision"},
                   "digest": {"content_sha256": "cd" * 32},
                   "revision_binding": {"source_artifact_id": "src:other"}}[mutation]
        sources._revisions[old.source_revision_id] = revision.model_copy(update=changes)
    assert not service.resolve_source_context(
        pinned, context_anchor_id=old.context_anchor_id, allow_selector_v2=True,
    ).found


@pytest.mark.parametrize(("owner", "field", "value"), [
    ("pair", "source_artifact_id", "src:other"),
    ("pair", "source_revision_id", "srcrev:other"),
    ("pair", "campaign_id", CAMPAIGN_B),
    ("pair", "source_uri", "fixture://other"),
    ("pair", "content_sha256", "cd" * 32),
    ("snapshot", "world_id", "world:other"),
    ("snapshot", "campaign_id", CAMPAIGN_B),
    ("snapshot", "revision_id", "rev:other"),
    ("snapshot", "scope_mode", ScopeModeV2.WORLD_CROSS_CAMPAIGN),
    ("snapshot", "admissibility", Admissibility.PLAYER),
    ("snapshot", "focus", "session"),
])
def test_recap_v2_identity_binds_source_and_projection(owner, field, value):
    service, _projection, published, _graph = _recap_context_services()
    result, context = service._establish(_campaign_a(revision_pin=published.revision_id))
    pair = service._admitted_recap_source_pairs(result, context)[0]
    derive = retrieval_module._derive_context_anchor_id_v2
    old = derive(snapshot=result.snapshot, pair=pair, section_selector_identity="selector-v2")
    if field == "focus":
        value = result.snapshot.focus.model_copy(update={
            "kind": type(result.snapshot.focus.kind)("session"), "session_id": "session-99",
        })
    changed_pair = replace(pair, **{field: value}) if owner == "pair" else pair
    changed_snapshot = (result.snapshot.model_copy(update={field: value})
                        if owner == "snapshot" else result.snapshot)
    assert derive(snapshot=changed_snapshot, pair=changed_pair,
                  section_selector_identity="selector-v2") != old
    assert derive(snapshot=result.snapshot, pair=pair,
                  section_selector_identity="different-selector") != old


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


def test_resolved_subject_precedes_incidental_lexical_matches():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, projection = _services(world_graph)
    result = service.search(
        _cross(),
        query_text="Does Alpha Keep have a bustling tavern at the crossroads with population?",
        bounds=RetrievalBounds(max_objects=1),
    )
    assert result.matched_object_ids == ("obj:alpha-keep",)
    assert "resolved_mention" in result.match_reasons["obj:alpha-keep"]
    assert "objects" in result.coverage.truncated_fields
    assert projection.project_calls == 1


def test_explicit_seed_precedes_resolved_subject_with_no_remaining_budget():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)
    result = service.search(
        _cross(), query_text="Tell me about Alpha Keep",
        seed_object_ids=["obj:world-gate"], bounds=RetrievalBounds(max_objects=1),
    )
    assert result.matched_object_ids == ("obj:world-gate",)
    assert "objects" in result.coverage.truncated_fields


def test_multiple_resolved_subjects_remain_bounded_and_deterministic():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)
    kwargs = {
        "query_text": "Compare Alpha Keep and Beta Crypt",
        "bounds": RetrievalBounds(max_objects=1),
    }
    first = service.search(_cross(), **kwargs)
    second = service.search(_cross(), **kwargs)
    assert len(first.matched_object_ids) == 1
    assert first.matched_object_ids == second.matched_object_ids
    assert "objects" in first.coverage.truncated_fields


def test_resolved_subject_cannot_cross_campaign_scope():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)
    result = service.search(_campaign_a(), query_text="Tell me about Beta Crypt")
    assert "obj:beta-crypt" not in result.matched_object_ids
    assert not any(r.object_id == "obj:beta-crypt" for r in result.referents)


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


def test_source_anchor_index_is_one_projection_sorted_unique_and_metadata_only():
    world_graph = InMemoryWorldGraphRepository()
    published = _publish(world_graph, _complete_object_payload())
    service, projection = _services(world_graph, _complete_object_sources())
    request = SourceAnchorIndexRequest(
        _request(
            scope_mode=ScopeModeV2.WORLD,
            revision_pin=published.revision_id,
        )
    )

    indexed = service.list_source_anchor_index(request)

    assert projection.project_calls == 1
    assert indexed.snapshot.revision_id == published.revision_id
    assert indexed.status == "complete"
    assert indexed.eligible_count == len(indexed.entries) == HUB_ANCHOR_COUNT + 1
    assert len({entry.anchor_id for entry in indexed.entries}) == indexed.eligible_count
    assert {entry.evidence_ref_id for entry in indexed.entries} >= {
        "ev:world",
        "ev:hub-anchor-00",
        f"ev:hub-anchor-{HUB_ANCHOR_COUNT - 1:02d}",
    }
    assert all(entry.source_revision_id for entry in indexed.entries)
    assert all(
        not hasattr(entry, "uri") and not hasattr(entry, "path")
        for entry in indexed.entries
    )
    assert indexed.entries == tuple(
        sorted(
            indexed.entries,
            key=lambda item: (
                item.anchor_id,
                item.evidence_ref_id,
                item.source_artifact_id,
                item.source_revision_id,
            ),
        )
    )


def test_source_anchor_index_requires_pinned_gm_projection():
    with pytest.raises(ValueError, match="exact revision pin"):
        SourceAnchorIndexRequest(_world())
    with pytest.raises(ValueError, match="GM admissibility"):
        SourceAnchorIndexRequest(
            _request(
                scope_mode=ScopeModeV2.WORLD,
                admissibility=Admissibility.PLAYER,
                revision_pin="rev:exact",
            )
        )


def test_source_anchor_index_omits_provenance_without_known_revision():
    world_graph = InMemoryWorldGraphRepository()
    published = _publish(world_graph)
    service, _ = _services(world_graph)
    request = SourceAnchorIndexRequest(
        _request(scope_mode=ScopeModeV2.WORLD, revision_pin=published.revision_id),
    )

    indexed = service.list_source_anchor_index(request)

    # The fixture's broken-lore evidence points at a nonexistent revision;
    # the index never invents a replacement from the artifact's current head.
    assert all(entry.source_revision_id != "srcrev:missing-rev" for entry in indexed.entries)


def test_source_anchor_index_filters_native_unreadable_locator_metadata():
    world_graph = InMemoryWorldGraphRepository()
    payload = _payload()
    next(row for row in payload["evidence_refs"] if row["evidence_ref_id"] == "ev:world")[
        "can_open_source"
    ] = False
    published = _publish(world_graph, payload)
    service, _ = _services(world_graph)

    indexed = service.list_source_anchor_index(
        SourceAnchorIndexRequest(
            _request(scope_mode=ScopeModeV2.WORLD, revision_pin=published.revision_id)
        )
    )

    assert indexed.eligible_count == 0
    assert indexed.entries == ()


def test_source_anchor_index_rejects_conflicting_authority_for_anchor_id(monkeypatch):
    world_graph = InMemoryWorldGraphRepository()
    published = _publish(world_graph, _complete_object_payload())
    service, _ = _services(world_graph, _complete_object_sources())
    monkeypatch.setattr(
        retrieval_module,
        "derive_source_anchor_id",
        lambda **_kwargs: "dm-source-anchor:v1:collision",
    )

    with pytest.raises(ValueError, match="conflicting authority tuples"):
        service.list_source_anchor_index(
            SourceAnchorIndexRequest(
                _request(scope_mode=ScopeModeV2.WORLD, revision_pin=published.revision_id)
            )
        )


def test_source_anchor_index_is_bound_to_revision_and_scope():
    world_graph = InMemoryWorldGraphRepository()
    first = _publish(world_graph)
    second_payload = _payload()
    second_payload["objects"][0]["label"] = "World Tavern Updated"
    second = _publish(
        world_graph,
        second_payload,
        parent_revision_id=first.revision_id,
        operation_id="op:second-index-revision",
    )
    service, _ = _services(world_graph)

    def ids(request):
        return {
            item.anchor_id
            for item in service.list_source_anchor_index(SourceAnchorIndexRequest(request)).entries
        }

    first_ids = ids(
        _request(scope_mode=ScopeModeV2.WORLD, revision_pin=first.revision_id)
    )
    second_ids = ids(
        _request(scope_mode=ScopeModeV2.WORLD, revision_pin=second.revision_id)
    )
    cross_campaign_ids = ids(
        _request(
            scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN,
            revision_pin=second.revision_id,
        )
    )

    assert first_ids.isdisjoint(second_ids)
    assert second_ids.isdisjoint(cross_campaign_ids)


def test_source_anchor_index_reports_513_eligible_anchors_as_empty_overflow():
    world_graph = InMemoryWorldGraphRepository()
    payload = _payload()
    sources = _seed_sources()
    for index in range(512):
        evidence_id = f"ev:index-{index:03d}"
        artifact_id = f"src:index-{index:03d}"
        revision_id = f"srcrev:index-{index:03d}"
        payload["evidence_refs"].append(
            _evidence_row(evidence_id, artifact_id, revision_id, span=f"span:{index}")
        )
        payload["objects"].append(
            _object(
                f"obj:index-{index:03d}",
                f"Index {index}",
                assertion_id=f"asrt:index-{index:03d}",
                evidence=evidence_id,
                campaign_scope=None,
            )
        )
        _put_source(
            sources,
            artifact_id=artifact_id,
            revision_id=revision_id,
            campaign_id=None,
        )
    published = _publish(world_graph, payload)
    service, projection = _services(world_graph, sources)
    request = SourceAnchorIndexRequest(
        _request(scope_mode=ScopeModeV2.WORLD, revision_pin=published.revision_id)
    )

    indexed = service.list_source_anchor_index(request)

    assert projection.project_calls == 1
    assert indexed.eligible_count == 513
    assert indexed.status == "overflow"
    assert indexed.entries == ()


# ---------------------------------------------------------------------------
# Complete selected-object one-hop read
# ---------------------------------------------------------------------------


def _endpoint_ids(result) -> set[str]:
    ids = {result.object.object_id}
    ids.update(obj.object_id for obj in result.related_objects)
    return ids


def test_complete_object_miss_is_explicit_and_not_partial():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, projection = _services(world_graph)

    result = service.get_complete_object(_world(), object_id="obj:absent")

    assert result.found is False
    assert result.object is None
    assert result.related_objects == ()
    assert result.relationships == ()
    assert result.completeness.status == "complete"
    assert result.completeness.reason is None
    assert result.coverage.truncated_fields == ()
    assert projection.project_calls == 1


def test_complete_object_out_of_scope_id_stays_silent():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    result = service.get_complete_object(_campaign_a(), object_id="obj:beta-crypt")
    assert result.found is False
    assert result.completeness.status == "complete"
    assert result.coverage.gap_codes == ()
    assert result.coverage.missing_ids == ()


def test_complete_object_rejects_blank_id():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)
    with pytest.raises(ValueError, match="non-blank"):
        service.get_complete_object(_world(), object_id="  ")


def test_complete_object_zero_relationships_is_complete():
    world_graph = InMemoryWorldGraphRepository()
    revision = _publish(world_graph, _complete_object_payload())
    service, _ = _complete_object_services(world_graph)

    result = service.get_complete_object(_world(), object_id=ISOLATED_OBJECT_ID)

    assert result.found is True
    assert result.object is not None
    assert result.relationships == ()
    assert result.related_objects == ()
    assert [row.assertion_id for row in result.property_assertions] == [
        "asrt:isolated-well",
        "asrt:prop-isolated-depth",
        "asrt:isolated-well-site",
    ]
    assert [row.assertion_kind for row in result.property_assertions] == [
        "existence",
        "property",
        "aspect",
    ]
    aspect = result.property_assertions[2]
    assert aspect.aspect_key == "site"
    assert aspect.aspect_kind == "dnd5e:location"
    assert aspect.evidence_ref_ids == ("ev:world",)
    assert aspect.assertion_metadata is not None
    supporting = {
        assertion_id
        for anchor in result.anchors
        for assertion_id in anchor.supporting_assertion_ids
    }
    assert {
        "asrt:isolated-well",
        "asrt:prop-isolated-depth",
        "asrt:isolated-well-site",
    } <= supporting
    assert result.completeness.status == "complete"
    assert result.coverage.truncated_fields == ()
    assert result.snapshot.revision_id == revision.revision_id
    assert result.snapshot.is_head is True


def test_complete_object_returns_every_edge_when_degree_exceeds_bounded_cap():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph, _complete_object_payload())
    service, projection = _complete_object_services(world_graph)

    capped = service.get_object(
        _world(), object_id=HUB_OBJECT_ID, bounds=_HARD_RETRIEVAL_BOUNDS
    )
    assert "relationships" in capped.coverage.truncated_fields
    assert len(capped.relationships) == 24

    result = service.get_complete_object(_world(), object_id=HUB_OBJECT_ID)

    assert result.found is True
    assert result.completeness.status == "complete"
    assert result.completeness.truncated_fields == ()
    assert result.coverage.truncated_fields == ()
    assert len(result.relationships) == HUB_DEGREE
    assert len(result.related_objects) == HUB_DEGREE
    outgoing = [
        rel for rel in result.relationships if rel.subject_object_id == HUB_OBJECT_ID
    ]
    incoming = [
        rel for rel in result.relationships if rel.object_object_id == HUB_OBJECT_ID
    ]
    assert len(outgoing) == HUB_OUTGOING
    assert len(incoming) == HUB_DEGREE - HUB_OUTGOING
    assert all(rel.predicate for rel in result.relationships)
    related_ids = {obj.object_id for obj in result.related_objects}
    assert related_ids == {f"obj:hub-leaf-{index:02d}" for index in range(HUB_DEGREE)}
    for rel in result.relationships:
        assert rel.subject_object_id in _endpoint_ids(result)
        assert rel.object_object_id in _endpoint_ids(result)
    assert [row.assertion_id for row in result.property_assertions] == [
        "asrt:hub-plaza",
        "asrt:prop-hub-population",
        *[f"asrt:prop-hub-tag-{index:02d}" for index in range(HUB_PROPERTY_COUNT - 1)],
    ]
    assert result.property_assertions[0].assertion_kind == "existence"
    assert all(
        row.assertion_kind == "property" for row in result.property_assertions[1:]
    )
    assert len(result.property_assertions) == 1 + HUB_PROPERTY_COUNT
    assert len(result.property_assertions) > 32
    assert projection.project_calls == 2


def test_complete_object_ignores_retrieval_bounds_hard_caps():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph, _complete_object_payload())
    service, _ = _complete_object_services(world_graph)

    first = service.get_complete_object(_world(), object_id=HUB_OBJECT_ID)
    second = service.get_complete_object(_world(), object_id=HUB_OBJECT_ID)

    assert first.completeness.status == "complete"
    assert [rel.relationship_id for rel in first.relationships] == [
        rel.relationship_id for rel in second.relationships
    ]
    assert [obj.object_id for obj in first.related_objects] == [
        obj.object_id for obj in second.related_objects
    ]
    assert [row.assertion_id for row in first.property_assertions] == [
        row.assertion_id for row in second.property_assertions
    ]
    assert [anchor.anchor_id for anchor in first.anchors] == [
        anchor.anchor_id for anchor in second.anchors
    ]
    assert len(first.relationships) > _HARD_RETRIEVAL_BOUNDS.max_relationships
    assert len(first.property_assertions) > _HARD_RETRIEVAL_BOUNDS.max_assertions
    assert len(first.anchors) > _HARD_RETRIEVAL_BOUNDS.max_anchors


def test_complete_object_returns_every_distinct_anchor_beyond_old_cap():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph, _complete_object_payload())
    service, _ = _complete_object_services(world_graph)

    capped = service.get_object(
        _world(), object_id=HUB_OBJECT_ID, bounds=_HARD_RETRIEVAL_BOUNDS
    )
    assert "anchors" in capped.coverage.truncated_fields
    assert len(capped.anchors) == _HARD_RETRIEVAL_BOUNDS.max_anchors

    result = service.get_complete_object(_world(), object_id=HUB_OBJECT_ID)
    anchor_ids = [anchor.anchor_id for anchor in result.anchors]
    evidence_ids = {anchor.evidence_ref_id for anchor in result.anchors}

    assert result.found is True
    assert result.completeness.status == "complete"
    assert result.completeness.reason is None
    assert result.coverage.truncated_fields == ()
    assert len(result.anchors) > 32
    assert len(anchor_ids) == len(set(anchor_ids))
    assert len(evidence_ids) > 32
    assert {f"ev:hub-anchor-{index:02d}" for index in range(HUB_ANCHOR_COUNT)} <= evidence_ids


def test_complete_object_world_scope_excludes_campaign_edges():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    world = service.get_complete_object(_world(), object_id="obj:world-tavern")
    campaign = service.get_complete_object(_campaign_a(), object_id="obj:world-tavern")
    cross = service.get_complete_object(_cross(), object_id="obj:alpha-keep")

    assert [rel.relationship_id for rel in world.relationships] == ["rel:tavern-gate"]
    assert {rel.relationship_id for rel in campaign.relationships} == {
        "rel:tavern-gate",
        "rel:tavern-keep",
    }
    assert world.completeness.status == campaign.completeness.status == "complete"
    assert "rel:keep-crypt" in {rel.relationship_id for rel in cross.relationships}
    assert "obj:beta-crypt" in {obj.object_id for obj in cross.related_objects}
    keep_world = service.get_complete_object(_world(), object_id="obj:alpha-keep")
    assert keep_world.found is False


def test_complete_object_player_fails_closed_on_gm_only_material():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)
    player = _campaign_a(admissibility=Admissibility.PLAYER)

    secret = service.get_complete_object(player, object_id="obj:alpha-secret")
    keep = service.get_complete_object(player, object_id="obj:alpha-keep")

    assert secret.found is False
    assert secret.completeness.status == "complete"
    assert keep.found is True
    assert keep.completeness.status == "complete"
    assert "rel:keep-secret" not in {rel.relationship_id for rel in keep.relationships}
    assert "obj:alpha-secret" not in {obj.object_id for obj in keep.related_objects}
    assert [row.assertion_id for row in keep.property_assertions] == [
        "asrt:alpha-keep",
        "asrt:prop-keep-threat",
    ]
    assert [row.assertion_kind for row in keep.property_assertions] == [
        "existence",
        "property",
    ]
    assert "asrt:keep-alias-traitor" not in {
        row.assertion_id for row in keep.property_assertions
    }


def test_complete_object_returns_all_selected_object_assertion_kinds():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    bounded = service.get_object(_world(), object_id="obj:world-tavern")
    result = service.get_complete_object(_world(), object_id="obj:world-tavern")

    assert [row.assertion_id for row in bounded.property_assertions] == [
        "asrt:prop-tavern-population"
    ]
    assert [row.assertion_kind for row in bounded.property_assertions] == ["property"]
    by_id = {row.assertion_id: row for row in result.property_assertions}
    assert [row.assertion_id for row in result.property_assertions] == [
        "asrt:world-tavern",
        "asrt:tavern-alias-pony",
        "asrt:tavern-alias-spot",
        "asrt:world-tavern:summary",
        "asrt:prop-tavern-population",
    ]
    assert [row.assertion_kind for row in result.property_assertions] == [
        "existence",
        "alias",
        "alias",
        "summary",
        "property",
    ]
    for assertion_id in (
        "asrt:world-tavern",
        "asrt:tavern-alias-pony",
        "asrt:tavern-alias-spot",
        "asrt:world-tavern:summary",
        "asrt:prop-tavern-population",
    ):
        row = by_id[assertion_id]
        assert row.subject_object_id == "obj:world-tavern"
        assert row.evidence_ref_ids == ("ev:world",)
        assert row.assertion_metadata is not None
        assert row.assertion_metadata.assertion_id == assertion_id
        assert row.assertion_metadata.temporal_scope is not None
    assert by_id["asrt:prop-tavern-population"].property_term == "dnd5e:population"
    assert by_id["asrt:tavern-alias-pony"].alias == "The Prancing Pony"
    assert by_id["asrt:tavern-alias-spot"].alias == "The Local Spot"
    assert by_id["asrt:world-tavern:summary"].summary == (
        "A bustling tavern at the crossroads."
    )
    supporting = {
        assertion_id
        for anchor in result.anchors
        for assertion_id in anchor.supporting_assertion_ids
    }
    assert {
        "asrt:world-tavern",
        "asrt:tavern-alias-pony",
        "asrt:tavern-alias-spot",
        "asrt:world-tavern:summary",
        "asrt:prop-tavern-population",
    } <= supporting
    assert result.completeness.status == "complete"


def test_complete_object_preserves_temporal_metadata_unchanged():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph, _complete_object_payload())
    service, _ = _complete_object_services(world_graph)

    world = service.get_complete_object(_world(), object_id=HUB_OBJECT_ID)
    population = next(
        row
        for row in world.property_assertions
        if row.assertion_id == "asrt:prop-hub-population"
    )
    assert population.assertion_metadata is not None
    assert population.assertion_metadata.temporal_scope.kind is TemporalScopeKind.WORLD_TIMELESS
    assert population.assertion_metadata.session_refs == ["sess:world-fair"]
    assert "rel:hub-keep-timed" not in {
        rel.relationship_id for rel in world.relationships
    }

    campaign = service.get_complete_object(_campaign_a(), object_id=HUB_OBJECT_ID)
    timed = next(
        rel
        for rel in campaign.relationships
        if rel.relationship_id == "rel:hub-keep-timed"
    )
    metadata = timed.assertion_metadata
    assert metadata is not None
    assert metadata.temporal_scope.kind is TemporalScopeKind.FICTIONAL_TIME_REF
    assert metadata.temporal_scope.fictional_time_ref is not None
    assert metadata.temporal_scope.fictional_time_ref.bundle_id == "ftb:alpha-siege"
    assert metadata.temporal_scope.fictional_time_ref.campaign_id == CAMPAIGN_A
    assert metadata.temporal_scope.fictional_time_ref.anchor_id == "fta:siege-night"
    assert metadata.session_refs == ["sess:alpha-12"]
    assert metadata.campaign_scope == CAMPAIGN_A
    assert campaign.completeness.status == "complete"
    assert "obj:alpha-keep" in {obj.object_id for obj in campaign.related_objects}
    assert len(campaign.relationships) == HUB_DEGREE + 1


def test_complete_object_anchors_fail_closed_without_invented_revisions():
    world_graph = InMemoryWorldGraphRepository()
    _publish(world_graph)
    service, _ = _services(world_graph)

    tavern = service.get_complete_object(_world(), object_id="obj:world-tavern")
    assert tavern.found is True
    assert tavern.completeness.status == "complete"
    assert len(tavern.anchors) == 1
    assert tavern.anchors[0].source_revision_id == "srcrev:world-lore-v1"
    assert tavern.anchors[0].evidence_ref_id == "ev:world"

    broken = service.get_complete_object(_world(), object_id="obj:broken-lore")
    assert broken.found is False
    assert broken.completeness.status == "complete"
    assert broken.anchors == ()


def test_complete_object_does_not_advance_world_head():
    world_graph = InMemoryWorldGraphRepository()
    published = _publish(world_graph, _complete_object_payload())
    service, _ = _complete_object_services(world_graph)
    before = world_graph.get_head(WORLD_ID)
    assert before is not None
    assert before.head_revision_id == published.revision_id

    result = service.get_complete_object(_world(), object_id=HUB_OBJECT_ID)
    after = world_graph.get_head(WORLD_ID)

    assert result.found is True
    assert after is not None
    assert after.head_revision_id == before.head_revision_id == published.revision_id
    assert result.snapshot.head_revision_id == published.revision_id
    assert result.snapshot.is_head is True


def test_selected_object_completeness_rejects_unknown_partial_reason():
    with pytest.raises(ValueError, match="known reason"):
        SelectedObjectCompleteness(
            status="partial",
            reason="try_again_later",
            truncated_fields=("relationships",),
        )
    with pytest.raises(ValueError, match="cannot name a partial reason"):
        SelectedObjectCompleteness(status="complete", reason="missing_related_endpoint")


def _selected(service, projection_request, *targets, max_entries=512):
    return service.list_selected_source_anchor_index(
        SelectedSourceAnchorIndexRequest(
            projection_request,
            tuple(EvidenceTarget(kind, target_id) for kind, target_id in targets),
            max_entries,
        )
    )


def test_selected_index_small_search_survives_unrelated_global_overflow():
    repo = InMemoryWorldGraphRepository()
    payload = _payload()
    sources = _seed_sources()
    for index in range(512):
        evidence = f"ev:unrelated-{index:03d}"
        artifact = f"src:unrelated-{index:03d}"
        revision = f"srcrev:unrelated-{index:03d}"
        payload["evidence_refs"].append(
            _evidence_row(evidence, artifact, revision, span=f"span:{index}")
        )
        payload["objects"].append(
            _object(
                f"obj:unrelated-{index:03d}",
                f"Unrelated {index}",
                assertion_id=f"asrt:unrelated-{index:03d}",
                evidence=evidence,
                campaign_scope=None,
            )
        )
        _put_source(sources, artifact_id=artifact, revision_id=revision, campaign_id=None)
    published = _publish(repo, payload)
    service, projection = _services(repo, sources)
    request = _request(scope_mode=ScopeModeV2.WORLD, revision_pin=published.revision_id)
    global_index = service.list_source_anchor_index(SourceAnchorIndexRequest(request))
    assert global_index.status == "overflow" and global_index.eligible_count == 513
    assert global_index.entries == ()
    search = service.search(request, seed_object_ids=("obj:world-tavern",))
    assert "obj:world-tavern" in search.matched_object_ids
    before = projection.project_calls
    selected = _selected(service, request, ("object", "obj:world-tavern"))
    assert projection.project_calls == before + 1
    assert selected.status == "complete" and selected.eligible_count == 1
    assert selected.requested_count == selected.admitted_count == 1
    assert selected.not_visible_count == selected.provenance_gap_count == 0
    assert selected.snapshot.revision_id == search.snapshot.revision_id
    assert len(selected.selector_sha256) == len(selected.index_sha256) == 64
    entry = selected.entries[0]
    assert entry.evidence_ref_id == "ev:world"
    assert not any(
        hasattr(entry, field) for field in ("uri", "path", "locator", "body", "text", "content")
    )
    # The existing opaque-anchor revalidation API admits the same selected tuple.
    resolved = service.resolve_source_anchor(request, anchor_id=entry.anchor_id)
    assert resolved.found and resolved.anchor.evidence_ref_id == entry.evidence_ref_id


def test_selected_index_overflow_returns_no_partial_entries():
    repo = InMemoryWorldGraphRepository()
    payload = _payload()
    sources = _seed_sources()
    own = payload["objects"][0]["assertion_metadata"]["evidence_ref_ids"]
    for index in range(512):
        evidence = f"ev:own-{index:03d}"
        artifact = f"src:own-{index:03d}"
        revision = f"srcrev:own-{index:03d}"
        own.append(evidence)
        payload["evidence_refs"].append(
            _evidence_row(evidence, artifact, revision, span=f"span:{index}")
        )
        _put_source(sources, artifact_id=artifact, revision_id=revision, campaign_id=None)
    published = _publish(repo, payload)
    service, _ = _services(repo, sources)
    indexed = _selected(
        service,
        _request(scope_mode=ScopeModeV2.WORLD, revision_pin=published.revision_id),
        ("object", "obj:world-tavern"),
    )
    assert indexed.status == "overflow" and indexed.eligible_count == 513
    assert indexed.entries == ()


def test_selected_index_own_supports_are_nontransitive_for_each_kind():
    repo = InMemoryWorldGraphRepository()
    published = _publish(repo, _complete_object_payload())
    service, _ = _complete_object_services(repo)
    request = _request(
        scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN, revision_pin=published.revision_id
    )
    obj = _selected(service, request, ("object", "obj:world-tavern"))
    relation = _selected(service, request, ("relationship", "rel:tavern-keep"))
    assertion = _selected(service, request, ("assertion", "asrt:prop-hub-tag-00"))
    assert {e.evidence_ref_id for e in obj.entries} == {"ev:world"}
    assert {e.evidence_ref_id for e in relation.entries} == {"ev:alpha"}
    assert {e.evidence_ref_id for e in assertion.entries} == {"ev:hub-anchor-01"}
    assert all(result.admitted_count == 1 for result in (obj, relation, assertion))


def test_selected_index_hidden_absent_and_kind_mismatch_share_not_visible():
    repo = InMemoryWorldGraphRepository()
    published = _publish(repo)
    service, _ = _services(repo)
    request = _request(scope_mode=ScopeModeV2.WORLD, revision_pin=published.revision_id)
    for kind, target in [
        ("object", "obj:alpha-secret"),
        ("object", "obj:absent"),
        ("assertion", "obj:world-tavern"),
    ]:
        indexed = _selected(service, request, (kind, target))
        assert indexed.status == "unavailable" and indexed.entries == ()
        assert indexed.requested_count == indexed.not_visible_count == 1
        assert indexed.admitted_count == indexed.eligible_count == indexed.provenance_gap_count == 0
        assert indexed.not_visible_targets == (EvidenceTarget(kind, target),)


def test_selected_index_reports_public_provenance_gap_without_source_ids():
    repo = InMemoryWorldGraphRepository()
    published = _publish(repo)
    service, _ = _services(repo)
    indexed = _selected(
        service,
        _request(scope_mode=ScopeModeV2.WORLD, revision_pin=published.revision_id),
        ("object", "obj:broken-lore"),
    )
    assert indexed.entries == () and indexed.status == "unavailable"
    assert indexed.not_visible_count == 1 and indexed.provenance_gap_count == 1
    assert not hasattr(indexed, "missing_ids") and not hasattr(indexed, "locators")


def test_selected_index_valid_but_unreadable_binding_is_explicit():
    repo = InMemoryWorldGraphRepository()
    payload = _payload()
    next(row for row in payload["evidence_refs"] if row["evidence_ref_id"] == "ev:world")[
        "can_open_source"
    ] = False
    published = _publish(repo, payload)
    service, _ = _services(repo)
    indexed = _selected(
        service,
        _request(scope_mode=ScopeModeV2.WORLD, revision_pin=published.revision_id),
        ("object", "obj:world-tavern"),
    )
    assert indexed.status == "unavailable" and indexed.entries == ()
    assert indexed.admitted_count == indexed.unavailable_binding_count == 1
    assert indexed.provenance_gap_count == 0


def test_selected_index_hashes_bind_selection_revision_scope_and_capacity():
    repo = InMemoryWorldGraphRepository()
    first = _publish(repo)
    second = _publish(repo, parent_revision_id=first.revision_id, operation_id="op:second-selected")
    service, _ = _services(repo)
    request = _request(scope_mode=ScopeModeV2.WORLD, revision_pin=first.revision_id)
    targets = [("object", "obj:world-tavern"), ("object", "obj:world-gate")]
    forward = _selected(service, request, *targets)
    reverse = _selected(service, request, *reversed(targets))
    assert forward == reverse
    changed = [
        _selected(service, request, targets[0]),
        _selected(service, request, *targets, max_entries=1),
        _selected(
            service,
            _request(scope_mode=ScopeModeV2.WORLD, revision_pin=second.revision_id),
            *targets,
        ),
        _selected(
            service,
            _request(scope_mode=ScopeModeV2.WORLD_CROSS_CAMPAIGN, revision_pin=first.revision_id),
            *targets,
        ),
    ]
    assert all(result.selector_sha256 != forward.selector_sha256 for result in changed)
    assert all(result.index_sha256 != forward.index_sha256 for result in changed)


def test_selected_index_request_rejects_unpinned_player_and_malformed_selection():
    pinned = _request(scope_mode=ScopeModeV2.WORLD, revision_pin="rev:test")
    with pytest.raises(ValueError, match="revision pin"):
        SelectedSourceAnchorIndexRequest(
            _request(scope_mode=ScopeModeV2.WORLD), (EvidenceTarget("object", "obj:test"),)
        )
    with pytest.raises(ValueError, match="GM"):
        SelectedSourceAnchorIndexRequest(
            _request(
                scope_mode=ScopeModeV2.WORLD,
                revision_pin="rev:test",
                admissibility=Admissibility.PLAYER,
            ),
            (EvidenceTarget("object", "obj:test"),),
        )
    for targets in [
        (),
        (EvidenceTarget("object", "obj:test"),) * 2,
        tuple(EvidenceTarget("object", f"obj:{n}") for n in range(9)),
        (EvidenceTarget("unsupported", "obj:test"),),
        (EvidenceTarget("object", " obj:test"),),
    ]:
        with pytest.raises(ValueError):
            SelectedSourceAnchorIndexRequest(pinned, targets)
    with pytest.raises(ValueError):
        SelectedSourceAnchorIndexRequest(
            pinned, (EvidenceTarget("object", "obj:test"),), max_entries=True
        )


def test_selected_index_wrong_world_revision_never_falls_back_to_head():
    from dungeonmind.domain.errors import RevisionNotFoundError

    repo = InMemoryWorldGraphRepository()
    _publish(repo)
    service, _ = _services(repo)
    with pytest.raises(RevisionNotFoundError):
        _selected(
            service,
            _request(scope_mode=ScopeModeV2.WORLD, revision_pin="rev:does-not-exist"),
            ("object", "obj:world-tavern"),
        )


def test_selected_index_rejects_changed_selector_and_conflicting_coverage():
    from dataclasses import replace

    repo = InMemoryWorldGraphRepository()
    published = _publish(repo)
    service, _ = _services(repo)
    result = _selected(
        service,
        _request(scope_mode=ScopeModeV2.WORLD, revision_pin=published.revision_id),
        ("object", "obj:world-tavern"),
    )
    assert result.index_scope == "selected_targets"
    with pytest.raises(ValueError, match="commitment"):
        replace(result, selector_sha256="0" * 64)
    with pytest.raises(ValueError, match="coverage"):
        replace(result, not_visible_targets=result.admitted_targets)
    with pytest.raises(ValueError, match="status/count"):
        replace(result, status="overflow")
    with pytest.raises(ValueError, match="authority tuples"):
        replace(result, entries=(result.entries[0], result.entries[0]), eligible_count=2)


def test_selected_index_campaign_scope_does_not_recover_other_campaign_targets():
    repo = InMemoryWorldGraphRepository()
    published = _publish(repo)
    service, _ = _services(repo)
    request = _request(
        scope_mode=ScopeModeV2.CAMPAIGN, campaign_id=CAMPAIGN_A, revision_pin=published.revision_id
    )
    selected = _selected(
        service, request, ("object", "obj:alpha-keep"), ("object", "obj:beta-crypt")
    )
    assert selected.admitted_count == selected.not_visible_count == 1
    assert selected.not_visible_targets == (EvidenceTarget("object", "obj:beta-crypt"),)
    assert {entry.source_artifact_id for entry in selected.entries} == {"src:alpha-notes"}
    assert selected.snapshot.campaign_id == CAMPAIGN_A




def test_selected_index_wrong_world_does_not_reuse_another_world_revision():
    from dungeonmind.domain.errors import HeadNotFoundError

    repo = InMemoryWorldGraphRepository()
    published = _publish(repo)
    service, _ = _services(repo)
    request = WorldGraphProjectionRequestV2(
        world_id="world:unavailable", scope_mode=ScopeModeV2.WORLD,
        admissibility=Admissibility.GM, revision_pin=published.revision_id,
    )
    with pytest.raises(HeadNotFoundError):
        _selected(service, request, ("object", "obj:world-tavern"))


# One pinned context, two independently useful owning views.
@pytest.mark.parametrize(
    "object_id,scope,admissibility",
    [
        ("obj:world-tavern", ScopeModeV2.WORLD, Admissibility.GM),
        ("obj:absent", ScopeModeV2.WORLD, Admissibility.GM),
        ("obj:beta-crypt", ScopeModeV2.CAMPAIGN, Admissibility.GM),
        ("obj:alpha-secret", ScopeModeV2.CAMPAIGN, Admissibility.PLAYER),
        ("obj:broken-lore", ScopeModeV2.WORLD, Admissibility.GM),
        ("obj:alpha-keep", ScopeModeV2.WORLD_CROSS_CAMPAIGN, Admissibility.GM),
    ],
)
def test_object_views_equal_independent_reads(object_id, scope, admissibility):
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph)
    service, projection = _services(graph)
    request = _request(
        scope_mode=scope, revision_pin=revision.revision_id,
        campaign_id=CAMPAIGN_A if scope == ScopeModeV2.CAMPAIGN else None,
        admissibility=admissibility,
    )
    bounds = RetrievalBounds(max_objects=1, max_relationships=1, max_assertions=1, max_anchors=1)
    pair = service.get_object_views(request, object_id=object_id, bounds=bounds)
    assert projection.project_calls == 1
    assert pair.bounded == service.get_object(request, object_id=object_id, bounds=bounds)
    assert pair.complete == service.get_complete_object(request, object_id=object_id)
    assert pair.bounded.snapshot == pair.complete.snapshot
    assert pair.bounded.found == pair.complete.found
    assert pair.bounded.object == pair.complete.object
    assert projection.project_calls == 3
    assert service.get_object_views(request, object_id=object_id, bounds=bounds) == pair
    assert projection.project_calls == 4  # no cross-call cache


def test_object_views_keep_complete_high_degree_ledger_beyond_bounded_view():
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph, _complete_object_payload())
    service, projection = _complete_object_services(graph)
    request = _world().model_copy(update={"revision_pin": revision.revision_id})
    bounds = RetrievalBounds(max_objects=1, max_relationships=1, max_assertions=1, max_anchors=1)
    pair = service.get_object_views(request, object_id=HUB_OBJECT_ID, bounds=bounds)
    assert projection.project_calls == 1
    assert len(pair.bounded.relationships) == len(pair.bounded.property_assertions) == 1
    assert pair.bounded.coverage.truncated_fields
    assert len(pair.complete.relationships) == HUB_DEGREE
    assert len(pair.complete.anchors) > 1
    assert pair.complete.completeness.status == "complete"
    assert pair.bounded == service.get_object(
        request, object_id=HUB_OBJECT_ID, bounds=bounds,
    )
    assert pair.complete == service.get_complete_object(request, object_id=HUB_OBJECT_ID)


@pytest.mark.parametrize(
    "pin,object_id",
    [(None, "obj:x"), ("", "obj:x"), ("  ", "obj:x"), ("revision:x", " ")],
)
def test_object_views_reject_invalid_identity_before_projection(pin, object_id):
    service, projection = _services(InMemoryWorldGraphRepository())
    request = _world().model_copy(update={"revision_pin": pin})
    with pytest.raises(ValueError, match="non-blank"):
        service.get_object_views(request, object_id=object_id)
    assert projection.project_calls == 0


def test_object_views_capture_request_and_snapshot_before_observer_moves_head():
    graph = InMemoryWorldGraphRepository()
    original = _publish(graph)
    service, projection = _services(graph)
    request = _world().model_copy(update={"revision_pin": original.revision_id})
    expected = service.get_complete_object(request, object_id="obj:world-tavern")
    events = []

    class MovingObserver:
        def observe(self, event):
            events.append(event)
            if event.operation == "get_object":
                newer = _publish(
                    graph, parent_revision_id=original.revision_id, operation_id="op:new-head",
                )
                request.revision_pin = newer.revision_id
                request.world_id = "world:foreign"
                request.admissibility = Admissibility.PLAYER

    service._read_observer = MovingObserver()
    pair = service.get_object_views(request, object_id="obj:world-tavern")
    assert projection.project_calls == 2  # independent expected read + one pair
    assert pair.complete == expected
    assert pair.bounded.snapshot == expected.snapshot
    assert [event.operation for event in events] == ["get_object", "get_complete_object"]
    assert all(event.outcome == "success" for event in events)
    assert request.revision_pin != original.revision_id


def test_object_views_propagate_projection_failure_with_owning_error_observation():
    from dungeonmind.domain.errors import RevisionNotFoundError

    graph = InMemoryWorldGraphRepository()
    _publish(graph)
    service, projection = _services(graph)
    events = []

    class Observer:
        def observe(self, event):
            events.append(event)

    service._read_observer = Observer()
    with pytest.raises(RevisionNotFoundError):
        service.get_object_views(
            _world().model_copy(update={"revision_pin": "revision:missing"}),
            object_id="obj:world-tavern",
        )
    assert projection.project_calls == 1
    assert [(event.operation, event.outcome) for event in events] == [("get_object", "error")]


def test_object_views_complete_failure_cannot_return_partial_pair(monkeypatch):
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph)
    service, projection = _services(graph)
    events = []

    class Observer:
        def observe(self, event):
            events.append(event)

    service._read_observer = Observer()

    def fail(*args, **kwargs):
        raise RuntimeError("review authority unavailable")

    monkeypatch.setattr(service, "_reviewed_source_observations", fail)
    with pytest.raises(RuntimeError, match="review authority unavailable"):
        service.get_object_views(
            _world().model_copy(update={"revision_pin": revision.revision_id}),
            object_id="obj:world-tavern",
        )
    assert projection.project_calls == 1
    assert [(event.operation, event.outcome) for event in events] == [
        ("get_object", "success"), ("get_complete_object", "error"),
    ]


def test_object_views_account_for_establishment_in_first_view(monkeypatch):
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph)
    service, projection = _services(graph)
    events = []

    class Clock:
        now = 0

        def now_ns(self):
            return self.now

    class Observer:
        def observe(self, event):
            events.append(event)

    clock = Clock()
    establish = projection.open_read_context

    def delayed(request):
        clock.now += 2_000_000_000
        return establish(request)

    monkeypatch.setattr(projection, "open_read_context", delayed)
    service._read_clock = clock
    service._read_observer = Observer()
    service.get_object_views(
        _world().model_copy(update={"revision_pin": revision.revision_id}),
        object_id="obj:world-tavern",
    )
    assert projection.project_calls == 1
    assert [event.duration_seconds for event in events] == [2.0, 0.0]
    projection_durations = [
        next(p.duration_seconds for p in event.phase_durations if p.phase == "projection")
        for event in events
    ]
    assert projection_durations == [2.0, 0.0]


@pytest.mark.parametrize("ids", [(), ("",), (" ",), ("obj:x", "obj:x"), "obj:x"])
def test_object_session_rejects_invalid_catalog_without_io(ids):
    service, projection = _services(InMemoryWorldGraphRepository())
    request = _world().model_copy(update={"revision_pin": "rev:pin"})
    with pytest.raises(ValueError, match="object_ids"), service.object_read_session(
        request, object_ids=ids,
    ):
        pytest.fail("invalid session entered")
    assert projection.project_calls == 0


def test_object_session_is_lazy_fresh_and_closed():
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph)
    service, projection = _services(graph)
    request = _cross(revision_pin=revision.revision_id)
    ids = ("obj:world-tavern", "obj:alpha-keep")
    with service.object_read_session(request, object_ids=ids) as session:
        assert projection.project_calls == 0
    assert projection.project_calls == 0
    with pytest.raises(RuntimeError, match="closed"):
        session.get_object_views(object_id=ids[0])
    with service.object_read_session(request, object_ids=ids) as session:
        first = session.get_object_views(object_id=ids[0])
        second = session.get_object_views(object_id=ids[1])
        assert first.complete.found and second.complete.found
        assert first.bounded.snapshot == second.complete.snapshot
        assert projection.project_calls == 1
    with service.object_read_session(request, object_ids=ids) as fresh:
        fresh.get_object_views(object_id=ids[1])
    assert projection.project_calls == 2


def test_object_session_isolates_nested_results_and_captured_request():
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph)
    service, projection = _services(graph)
    request = _cross(revision_pin=revision.revision_id)
    ids = ("obj:world-tavern", "obj:alpha-keep")
    expected = service.get_object_views(request, object_id=ids[0])
    with service.object_read_session(request, object_ids=ids) as session:
        request.world_id = "world:foreign"
        request.revision_pin = "rev:foreign"
        first = session.get_object_views(object_id=ids[0])
        first.bounded.snapshot.world_id = "world:mutated"
        first.bounded.object.label = "Mutated label"
        first.complete.object.aliases.append("Mutated alias")
        for obj in first.complete.related_objects:
            obj.label = "Mutated related label"
        repeated = session.get_object_views(object_id=ids[0])
        related = session.get_object_views(object_id=ids[1])
        assert repeated == expected
        assert related.complete.object.label != "Mutated related label"
        assert related.complete.snapshot.world_id == WORLD_ID
    assert projection.project_calls == 2


def test_object_session_foreign_request_poisons_before_io():
    service, projection = _services(InMemoryWorldGraphRepository())
    request = _world().model_copy(update={"revision_pin": "rev:pin"})
    with service.object_read_session(request, object_ids=("obj:allowed",)) as session:
        with pytest.raises(ValueError, match="outside"):
            session.get_object_views(object_id="obj:foreign")
        with pytest.raises(RuntimeError, match="failed"):
            session.get_object_views(object_id="obj:allowed")
    assert projection.project_calls == 0


def test_object_session_failed_read_cannot_repeat_io(monkeypatch):
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph)
    service, projection = _services(graph)
    request = _world().model_copy(update={"revision_pin": revision.revision_id})
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic authority failure")
    monkeypatch.setattr(service, "_reviewed_source_observations", fail)
    with service.object_read_session(request, object_ids=("obj:world-tavern",)) as session:
        with pytest.raises(RuntimeError, match="synthetic authority"):
            session.get_object_views(object_id="obj:world-tavern")
        with pytest.raises(RuntimeError, match="session failed"):
            session.get_object_views(object_id="obj:world-tavern")
    assert projection.project_calls == 1


def test_object_session_result_copy_time_is_in_logical_operation_total(monkeypatch):
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph)
    service, _ = _services(graph)
    events = []
    class Clock:
        ticks = 0
        def now_ns(self):
            return self.ticks
    class Observer:
        def observe(self, event):
            events.append(event)
    clock = Clock()
    original = retrieval_module.deepcopy
    def copied(value):
        if isinstance(value, retrieval_module.ObjectLookupResult):
            clock.ticks += 200_000_000
        elif isinstance(value, retrieval_module.CompleteObjectLookupResult):
            clock.ticks += 300_000_000
        return original(value)
    monkeypatch.setattr(retrieval_module, "deepcopy", copied)
    service._read_clock = clock
    service._read_observer = Observer()
    service.get_object_views(
        _world().model_copy(update={"revision_pin": revision.revision_id}),
        object_id="obj:world-tavern",
    )
    assert [event.duration_seconds for event in events] == [0.2, 0.3]


def test_object_session_closed_by_observer_cannot_reopen_for_complete_view():
    graph = InMemoryWorldGraphRepository()
    revision = _publish(graph)
    service, projection = _services(graph)
    with service.object_read_session(
        _world().model_copy(update={"revision_pin": revision.revision_id}),
        object_ids=("obj:world-tavern",),
    ) as session:
        class Observer:
            def observe(self, event):
                session.close()
        service._read_observer = Observer()
        with pytest.raises(RuntimeError, match="closed"):
            session.get_object_views(object_id="obj:world-tavern")
    assert projection.project_calls == 1
