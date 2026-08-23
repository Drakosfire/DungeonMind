"""Unit tests for the existing-world adoption source-classification repair."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from dungeonmind.application.existing_world_adoption_repair import (
    repair_existing_world_adoption_source_classification,
)
from dungeonmind.application.graph_snapshot import (
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.semantic_profiles import (
    SemanticProfileDescriptor,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry
from dungeonmind.contracts.existing_world_adoption import (
    ExistingWorldAdoptionBundleV2,
    ExistingWorldAdoptionReceiptV3,
    ExistingWorldAdoptionReceiptV4,
)
from dungeonmind.contracts.existing_world_adoption_repair import (
    ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1,
    ExistingWorldAdoptionSourceClassificationRepairIntentV1,
)
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.memory.repositories import (
    InMemoryContributionRepository,
    InMemoryExistingWorldAdoptionRepository,
    InMemoryIdentityDecisionRepository,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "dungeonmind_dnd" / "eldyrwild_existing_world_adoption_bundle_v2.json"
DESCRIPTOR_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "semantic_profiles" / "dnd5e-profile-v3.json"
)


def _descriptor() -> SemanticProfileDescriptor:
    return SemanticProfileDescriptor.model_validate(
        json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    )


def _registry() -> StaticSemanticProfileRegistry:
    return StaticSemanticProfileRegistry([_descriptor()])


@pytest.fixture
def raw_bundle() -> bytes:
    return FIXTURE_PATH.read_bytes()


@pytest.fixture
def bundle(raw_bundle: bytes) -> ExistingWorldAdoptionBundleV2:
    payload = json.loads(raw_bundle.decode("utf-8"))
    return ExistingWorldAdoptionBundleV2.model_validate(payload)


@pytest.fixture
def graph_reader() -> VersionedUnionGraphSnapshotReader:
    return VersionedUnionGraphSnapshotReader(profile_registry=_registry())


@pytest.fixture
def repositories():
    world_graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    contributions = InMemoryContributionRepository()
    identity = InMemoryIdentityDecisionRepository()
    adoption = InMemoryExistingWorldAdoptionRepository(
        world_graph, sources, contributions, identity
    )
    return adoption, sources, contributions, identity


def test_repair_intent_validation_success(
    raw_bundle: bytes,
    bundle: ExistingWorldAdoptionBundleV2,
    graph_reader: GraphSnapshotReader,
    repositories,
):
    """Test that a valid repair intent passes validation."""
    adoption, sources, contributions, identity = repositories

    # Find an artifact with visibility=None
    target_artifact = next(
        (a for a in bundle.source_artifacts if a.visibility is None), None
    )
    assert target_artifact is not None, "No artifact with visibility=None found"

    repair_intent = ExistingWorldAdoptionSourceClassificationRepairIntentV1(
        world_id=bundle.world_id,
        adoption_id=bundle.adoption_id,
        repairs=[
            ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1(
                source_artifact_id=target_artifact.source_artifact_id,
                set_visibility_to_gm=True,
            )
        ],
    )

    # The repair should succeed (but will fail because the world is not adopted)
    with pytest.raises(PersistenceIntegrityError) as exc_info:
        repair_existing_world_adoption_source_classification(
            raw_bundle,
            repair_intent=repair_intent,
            repaired_at=datetime.now(timezone.utc),
            adoption_repository=adoption,
            graph_reader=graph_reader,
        )
    assert "adoption_receipt_missing" in str(exc_info.value) or "found no receipt" in str(exc_info.value)


def test_repair_intent_validation_unknown_artifact(
    raw_bundle: bytes,
    bundle: ExistingWorldAdoptionBundleV2,
    graph_reader: GraphSnapshotReader,
    repositories,
):
    """Test that an unknown artifact ID fails validation."""
    adoption, sources, contributions, identity = repositories

    repair_intent = ExistingWorldAdoptionSourceClassificationRepairIntentV1(
        world_id=bundle.world_id,
        adoption_id=bundle.adoption_id,
        repairs=[
            ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1(
                source_artifact_id="unknown:artifact",
                set_visibility_to_gm=True,
            )
        ],
    )

    with pytest.raises(PersistenceIntegrityError) as exc_info:
        repair_existing_world_adoption_source_classification(
            raw_bundle,
            repair_intent=repair_intent,
            repaired_at=datetime.now(timezone.utc),
            adoption_repository=adoption,
            graph_reader=graph_reader,
        )
    assert exc_info.value.details.get("reason") == "repair_intent_unknown_artifact"


def test_repair_intent_validation_visibility_not_none(
    raw_bundle: bytes,
    bundle: ExistingWorldAdoptionBundleV2,
    graph_reader: GraphSnapshotReader,
    repositories,
):
    """Test that a visibility repair on an artifact with visibility != None fails."""
    adoption, sources, contributions, identity = repositories

    # Find an artifact with visibility != None
    target_artifact = next(
        (a for a in bundle.source_artifacts if a.visibility is not None), None
    )
    if target_artifact is None:
        pytest.skip("No artifact with visibility != None found in fixture")

    repair_intent = ExistingWorldAdoptionSourceClassificationRepairIntentV1(
        world_id=bundle.world_id,
        adoption_id=bundle.adoption_id,
        repairs=[
            ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1(
                source_artifact_id=target_artifact.source_artifact_id,
                set_visibility_to_gm=True,
            )
        ],
    )

    with pytest.raises(PersistenceIntegrityError) as exc_info:
        repair_existing_world_adoption_source_classification(
            raw_bundle,
            repair_intent=repair_intent,
            repaired_at=datetime.now(timezone.utc),
            adoption_repository=adoption,
            graph_reader=graph_reader,
        )
    assert exc_info.value.details.get("reason") == "repair_intent_visibility_not_none"


def test_repair_intent_validation_campaign_already_none(
    raw_bundle: bytes,
    bundle: ExistingWorldAdoptionBundleV2,
    graph_reader: GraphSnapshotReader,
    repositories,
):
    """Test that a campaign repair on an artifact with campaign_id=None fails."""
    adoption, sources, contributions, identity = repositories

    # Find an artifact with campaign_id=None
    target_artifact = next(
        (a for a in bundle.source_artifacts if a.campaign_id is None), None
    )
    if target_artifact is None:
        pytest.skip("No artifact with campaign_id=None found in fixture")

    repair_intent = ExistingWorldAdoptionSourceClassificationRepairIntentV1(
        world_id=bundle.world_id,
        adoption_id=bundle.adoption_id,
        repairs=[
            ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1(
                source_artifact_id=target_artifact.source_artifact_id,
                clear_campaign_id=True,
            )
        ],
    )

    with pytest.raises(PersistenceIntegrityError) as exc_info:
        repair_existing_world_adoption_source_classification(
            raw_bundle,
            repair_intent=repair_intent,
            repaired_at=datetime.now(timezone.utc),
            adoption_repository=adoption,
            graph_reader=graph_reader,
        )
    assert exc_info.value.details.get("reason") == "repair_intent_campaign_already_none"


def test_repair_intent_validation_campaign_not_worldbuilding(
    raw_bundle: bytes,
    bundle: ExistingWorldAdoptionBundleV2,
    graph_reader: GraphSnapshotReader,
    repositories,
):
    """Test that a campaign repair on a non-worldbuilding artifact fails."""
    adoption, sources, contributions, identity = repositories

    # Find an artifact with campaign_id != None and source_domain != worldbuilding
    target_artifact = next(
        (
            a
            for a in bundle.source_artifacts
            if a.campaign_id is not None and a.source_domain != "worldbuilding"
        ),
        None,
    )
    if target_artifact is None:
        pytest.skip("No artifact with campaign_id != None and source_domain != worldbuilding found")

    repair_intent = ExistingWorldAdoptionSourceClassificationRepairIntentV1(
        world_id=bundle.world_id,
        adoption_id=bundle.adoption_id,
        repairs=[
            ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1(
                source_artifact_id=target_artifact.source_artifact_id,
                clear_campaign_id=True,
            )
        ],
    )

    with pytest.raises(PersistenceIntegrityError) as exc_info:
        repair_existing_world_adoption_source_classification(
            raw_bundle,
            repair_intent=repair_intent,
            repaired_at=datetime.now(timezone.utc),
            adoption_repository=adoption,
            graph_reader=graph_reader,
        )
    assert exc_info.value.details.get("reason") == "repair_intent_campaign_not_worldbuilding"


def test_repair_intent_validation_campaign_has_session(
    raw_bundle: bytes,
    bundle: ExistingWorldAdoptionBundleV2,
    graph_reader: GraphSnapshotReader,
    repositories,
):
    """Test that a campaign repair on an artifact with session_id != None fails."""
    adoption, sources, contributions, identity = repositories

    # Find an artifact with campaign_id != None, session_id != None, and source_domain == worldbuilding
    target_artifact = next(
        (
            a
            for a in bundle.source_artifacts
            if a.campaign_id is not None
            and a.session_id is not None
            and a.source_domain == "worldbuilding"
        ),
        None,
    )
    if target_artifact is None:
        pytest.skip("No artifact with campaign_id != None, session_id != None, and source_domain == worldbuilding found")

    repair_intent = ExistingWorldAdoptionSourceClassificationRepairIntentV1(
        world_id=bundle.world_id,
        adoption_id=bundle.adoption_id,
        repairs=[
            ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1(
                source_artifact_id=target_artifact.source_artifact_id,
                clear_campaign_id=True,
            )
        ],
    )

    with pytest.raises(PersistenceIntegrityError) as exc_info:
        repair_existing_world_adoption_source_classification(
            raw_bundle,
            repair_intent=repair_intent,
            repaired_at=datetime.now(timezone.utc),
            adoption_repository=adoption,
            graph_reader=graph_reader,
        )
    assert "repair_intent_campaign_has_session" in str(exc_info.value) or exc_info.value.details.get("reason") == "repair_intent_campaign_has_session"