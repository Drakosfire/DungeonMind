"""Synthetic governed world fixture for the K0.2 semantic witness.

Payload helpers are copied from tests/unit/test_world_graph_retrieval_service.py
so the witness world matches already-proven v6 read semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V6,
    RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.application.world_graph_projection import WorldGraphProjectionService
from dungeonmind.application.world_graph_retrieval import WorldGraphRetrievalService
from dungeonmind.contracts.evidence import (
    SourceArtifactV2,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.projection import Admissibility
from dungeonmind.contracts.projection_v2 import ScopeModeV2, WorldGraphProjectionRequestV2
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryContributionReviewRepository,
    InMemoryExistingWorldAdoptionRepository,
    InMemoryFinalizedReviewPublicationRepository,
    InMemoryIdentityDecisionRepository,
    InMemoryReviewedWorldInitializationRepository,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind_dnd.application.world_object_vocabulary import (
    load_builtin_v3_descriptor,
)

FIXTURE_ID = "k0_synthetic_governed_world_v1"
WORLD_ID = "world:test"


CAMPAIGN_A = "camp:alpha"
CAMPAIGN_B = "camp:beta"
NOW = datetime(2026, 8, 22, 18, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


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


@dataclass
class WitnessStores:
    world_graph: Any
    sources: Any
    contributions: Any
    identity: Any
    reviews: Any
    publications: Any
    adoptions: Any
    initializations: Any


class AdapterBundle(Protocol):
    world_graph: Any
    sources: Any
    contributions: Any
    identity_decisions: Any
    contribution_reviews: Any
    finalized_review_publications: Any
    existing_world_adoptions: Any
    reviewed_world_initializations: Any


def make_memory_stores() -> WitnessStores:
    graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    contributions = InMemoryContributionRepository()
    identity = InMemoryIdentityDecisionRepository()
    reviews = InMemoryContributionReviewRepository(contributions)
    publications = InMemoryFinalizedReviewPublicationRepository(reviews, graph)
    adoptions = InMemoryExistingWorldAdoptionRepository(graph, sources, contributions, identity)
    initializations = InMemoryReviewedWorldInitializationRepository(
        graph, sources, contributions, identity
    )
    return WitnessStores(
        world_graph=graph,
        sources=sources,
        contributions=contributions,
        identity=identity,
        reviews=reviews,
        publications=publications,
        adoptions=adoptions,
        initializations=initializations,
    )


def stores_from_postgres_bundle(bundle: AdapterBundle) -> WitnessStores:
    return WitnessStores(
        world_graph=bundle.world_graph,
        sources=bundle.sources,
        contributions=bundle.contributions,
        identity=bundle.identity_decisions,
        reviews=bundle.contribution_reviews,
        publications=bundle.finalized_review_publications,
        adoptions=bundle.existing_world_adoptions,
        initializations=bundle.reviewed_world_initializations,
    )


def publish_synthetic_head(stores: WitnessStores) -> str:
    sources = _seed_sources()
    # Copy seeded artifacts into stores.sources
    for artifact in sources.list_artifacts_for_world(WORLD_ID):
        stores.sources.put_artifact(artifact)
    # Revisions: enumerate via known IDs
    for revision_id in (
        "srcrev:world-lore-v1",
        "srcrev:alpha-notes-v1",
        "srcrev:beta-notes-v1",
    ):
        rev = sources.get_revision(revision_id)
        if rev is not None:
            stores.sources.put_revision(rev)
    revision = _publish(stores.world_graph)
    return str(revision.revision_id)


def make_services(
    stores: WitnessStores,
) -> tuple[WorldGraphProjectionService, WorldGraphRetrievalService]:
    projection = WorldGraphProjectionService(
        world_graph=stores.world_graph,
        sources=stores.sources,
        graph_reader=VersionedUnionGraphSnapshotReader(
            profile_registry=StaticSemanticProfileRegistry([_v6_descriptor()])
        ),
        reviewed_world_initializations=stores.initializations,
        clock=FixedClock(),
    )
    retrieval = WorldGraphRetrievalService(projection=projection, sources=stores.sources)
    return projection, retrieval


def request(
    *,
    scope_mode: ScopeModeV2,
    campaign_id: str | None = None,
    admissibility: Admissibility = Admissibility.GM,
    revision_pin: str | None = None,
) -> WorldGraphProjectionRequestV2:
    return _request(
        scope_mode=scope_mode,
        campaign_id=campaign_id,
        admissibility=admissibility,
        revision_pin=revision_pin,
    )


def synthetic_graph_payload() -> dict[str, Any]:
    return _payload()


def fixture_manifest(*, head_revision_id: str) -> dict[str, Any]:
    return {
        "id": FIXTURE_ID,
        "world_id": WORLD_ID,
        "campaigns": [CAMPAIGN_A, CAMPAIGN_B],
        "head_revision_id": head_revision_id,
        "graph_schema": GRAPH_SCHEMA_V6,
        "gm_only_object_ids": ["obj:alpha-secret"],
        "player_visible_campaign_a_object_ids": [
            "obj:world-tavern",
            "obj:world-gate",
            "obj:alpha-keep",
        ],
        "provenance_invalid_object_id": "obj:broken-lore",
        "derivation": "tests/unit/test_world_graph_retrieval_service.py payload helpers",
    }
