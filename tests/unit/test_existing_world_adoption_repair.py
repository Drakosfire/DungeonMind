"""Unit tests for existing-world adoption source-classification repair."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from dungeonmind.application.existing_world_adoption import adopt_existing_world
from dungeonmind.application.existing_world_adoption_repair import (
    derive_membership_manifest,
    repair_existing_world_adoption_source_classification,
    sealed_membership_sha256,
)
from dungeonmind.application.existing_world_correspondence import (
    ExistingWorldCorrespondenceService,
)
from dungeonmind.contracts.evidence import SourceDomain, SourceStatus
from dungeonmind.contracts.existing_world_adoption import (
    EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA,
    ExistingWorldAdoptionReceiptV3,
    ExistingWorldAdoptionReceiptV4,
    ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1,
    sha256_bytes,
)
from dungeonmind.contracts.existing_world_adoption_repair import (
    ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1,
    ExistingWorldAdoptionSourceClassificationRepairIntentV1,
)
from dungeonmind.contracts.identity import (
    IdentityDecisionKind,
    IdentityDecisionRecordV2,
    IdentityDecisionStatus,
)
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import (
    ExistingWorldAdoptionOutcomeUnknownError,
    PersistenceIntegrityError,
)
from dungeonmind.domain.existing_world_membership import (
    existing_world_adoption_membership_sha256,
)
from dungeonmind.infrastructure.memory.repositories import (
    InMemoryExistingWorldAdoptionRepository,
)
from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
    BUNDLE_SHA256 as ELDYRWILD_BUNDLE_SHA256,
)
from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
    EXPECTED_CONTRIBUTIONS,
    EXPECTED_IDENTITY_DECISIONS,
    EXPECTED_SOURCE_ARTIFACTS,
    EXPECTED_SOURCE_REVISIONS,
    eldyrwild_graph_reader,
    parse_sealed_bundle,
)
from tests.unit.test_eldyrwild_existing_world_adoption_bundle_v2 import (
    raw_bundle as eldyrwild_raw_bundle,
)
from tests.unit.test_existing_world_adoption import (
    ART_A,
    ART_B,
    CAMPAIGN_ID,
    NOW,
    WORLD_ID,
    _artifact,
    _revision,
    _v2_contribution,
    graph_reader,
    make_stores,
    make_v2_bundle,
    v2_bundle_bytes,
)

DESCENDANT_ARTIFACT_ID = "src:descendant"
DESCENDANT_REVISION_ID = "srcrev:descendant"
DESCENDANT_ON_ADOPTED_REVISION_ID = "srcrev:post-adoption-on-a"
DESCENDANT_CONTRIBUTION_ID = "contrib:descendant"
DESCENDANT_IDENTITY_ID = "iddec:descendant"

REPAIRED_AT = datetime(2026, 8, 23, 18, 0, tzinfo=UTC)


def _repairable_bundle():
    bundle = make_v2_bundle()
    first, second, *rest = bundle.source_artifacts
    artifacts = [
        first.model_copy(update={"visibility": None}),
        second.model_copy(
            update={
                "campaign_id": CAMPAIGN_ID,
                "session_id": None,
                "source_domain": SourceDomain.WORLDBUILDING,
            }
        ),
        *rest,
    ]
    return bundle.model_copy(update={"source_artifacts": artifacts})


def _intent(bundle, *, visibility: bool = True, campaign: bool = True):
    repairs = []
    if visibility:
        repairs.append(
            ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1(
                source_artifact_id=bundle.source_artifacts[0].source_artifact_id,
                set_visibility_to_gm=True,
            )
        )
    if campaign:
        repairs.append(
            ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1(
                source_artifact_id=bundle.source_artifacts[1].source_artifact_id,
                clear_campaign_id=True,
            )
        )
    return ExistingWorldAdoptionSourceClassificationRepairIntentV1(
        world_id=bundle.world_id,
        adoption_id=bundle.adoption_id,
        repairs=repairs,
    )


def _adopt_repairable():
    bundle = _repairable_bundle()
    raw = v2_bundle_bytes(bundle)
    graph, sources, contributions, identity, adoptions = make_stores()
    receipt = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    assert isinstance(receipt, ExistingWorldAdoptionReceiptV3)
    return bundle, raw, graph, sources, contributions, identity, adoptions, receipt


def _world_membership(sources, contributions, identity, world_id: str) -> str:
    artifacts = [
        artifact
        for artifact in sources._artifacts.values()
        if artifact.world_id == world_id
    ]
    artifact_ids = {artifact.source_artifact_id for artifact in artifacts}
    return existing_world_adoption_membership_sha256(
        source_artifacts=artifacts,
        source_revisions=[
            revision
            for revision in sources._revisions.values()
            if revision.source_artifact_id in artifact_ids
        ],
        contributions=[
            item for key, item in contributions._items.items() if key[0] == world_id
        ],
        identity_decisions=[
            item for key, item in identity._items.items() if key[0] == world_id
        ],
    )


def _inject_allowed_corruption(sources, contributions, identity, adoptions, bundle) -> str:
    first = bundle.source_artifacts[0]
    second = bundle.source_artifacts[1]
    sources._artifacts[first.source_artifact_id] = first.model_copy(
        update={"visibility": Visibility.GM}
    )
    sources._artifacts[second.source_artifact_id] = second.model_copy(
        update={"campaign_id": None}
    )
    digest = _world_membership(sources, contributions, identity, bundle.world_id)
    stored = adoptions._receipts_by_world[bundle.world_id]
    rewritten = stored.model_copy(update={"membership_sha256": digest})
    adoptions._receipts_by_world[bundle.world_id] = rewritten
    adoptions._receipts_by_adoption[rewritten.adoption_id] = rewritten
    return digest


def _repair(raw, intent, adoptions, *, apply: bool = True, repaired_at=REPAIRED_AT):
    return repair_existing_world_adoption_source_classification(
        raw,
        repair_intent=intent,
        repaired_at=repaired_at,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
        apply=apply,
    )


def _correspondence(graph, sources, contributions, identity, adoptions):
    return ExistingWorldCorrespondenceService(
        adoption_repository=adoptions,
        world_graph_repository=graph,
        contribution_repository=contributions,
        identity_repository=identity,
        source_repository=sources,
        graph_reader=graph_reader(),
    )


def _append_post_adoption_descendants(sources, contributions, identity) -> None:
    descendant = _artifact(DESCENDANT_ARTIFACT_ID, DESCENDANT_REVISION_ID)
    sources.put_artifact(descendant)
    sources.put_revision(
        _revision(DESCENDANT_REVISION_ID, DESCENDANT_ARTIFACT_ID, "c" * 64)
    )
    sources.put_revision(
        _revision(DESCENDANT_ON_ADOPTED_REVISION_ID, ART_A, "d" * 64)
    )
    contributions.append(
        _v2_contribution(
            DESCENDANT_CONTRIBUTION_ID,
            DESCENDANT_ARTIFACT_ID,
            DESCENDANT_REVISION_ID,
        )
    )
    identity.append(
        IdentityDecisionRecordV2(
            decision_id=DESCENDANT_IDENTITY_ID,
            world_id=WORLD_ID,
            decision_kind=IdentityDecisionKind.ALIAS_ADD,
            subject_object_ids=["obj:college"],
            alias="PostAdoption",
            status=IdentityDecisionStatus.ACTIVE,
            created_at=NOW,
            merge_side_effects=None,
        )
    )


def _tamper_v4_effective_fingerprint(adoptions, world_id: str = WORLD_ID) -> None:
    stored = adoptions._receipts_by_world[world_id]
    assert isinstance(stored, ExistingWorldAdoptionReceiptV4)
    repair = stored.source_classification_repair
    first, *rest = repair.corrections
    tampered = first.model_copy(update={"effective_record_fingerprint": "f" * 64})
    rewritten = stored.model_copy(
        update={
            "source_classification_repair": repair.model_copy(
                update={"corrections": [tampered, *rest]}
            )
        }
    )
    adoptions._receipts_by_world[world_id] = rewritten
    adoptions._receipts_by_adoption[rewritten.adoption_id] = rewritten


def test_v3_round_trip_unchanged() -> None:
    payload = {
        "adoption_id": "adopt:x",
        "world_id": "world:x",
        "bundle_sha256": "a" * 64,
        "source_provenance": {
            "schema_version": "dm_existing_world_adoption_source_provenance_v1",
            "producer_id": "buddy",
            "producer_revision": "rev",
            "source_world_revision_id": "rev:src",
            "source_graph_payload_sha256": "b" * 64,
            "authority_refs": [],
        },
        "published_revision_id": "rev:da",
        "graph_schema": "dm_union_graph_v6",
        "graph_payload_sha256": "c" * 64,
        "adopted_at": NOW.isoformat(),
        "source_artifact_count": 1,
        "source_revision_count": 1,
        "contribution_count": 1,
        "identity_decision_count": 1,
        "membership_sha256": "d" * 64,
    }
    receipt = ExistingWorldAdoptionReceiptV3.model_validate(payload)
    assert receipt.schema_version == EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA
    assert (
        ExistingWorldAdoptionReceiptV3.model_validate(receipt.model_dump(mode="json"))
        == receipt
    )


def test_v4_rejects_missing_effective_digest() -> None:
    with pytest.raises(ValidationError):
        ExistingWorldAdoptionReceiptV4.model_validate(
            {
                "adoption_id": "adopt:x",
                "world_id": "world:x",
                "bundle_sha256": "a" * 64,
                "source_provenance": {
                    "schema_version": "dm_existing_world_adoption_source_provenance_v1",
                    "producer_id": "buddy",
                    "producer_revision": "rev",
                    "source_world_revision_id": "rev:src",
                    "source_graph_payload_sha256": "b" * 64,
                    "authority_refs": [],
                },
                "published_revision_id": "rev:da",
                "graph_schema": "dm_union_graph_v6",
                "graph_payload_sha256": "c" * 64,
                "adopted_at": NOW.isoformat(),
                "source_artifact_count": 1,
                "source_revision_count": 1,
                "contribution_count": 1,
                "identity_decision_count": 1,
                "membership_sha256": "d" * 64,
                "membership_manifest": {
                    "source_artifact_ids": ["src:a"],
                    "source_revision_ids": ["srcrev:a"],
                    "contribution_ids": ["contrib:a"],
                    "identity_decision_ids": ["iddec:a"],
                },
                "source_classification_repair": {
                    "repair_id": "repair:x",
                    "repaired_at": REPAIRED_AT.isoformat(),
                    "observed_pre_repair_membership_sha256": "e" * 64,
                    "effective_membership_sha256": "f" * 64,
                    "corrections": [
                        {
                            "source_artifact_id": "src:a",
                            "original_record_fingerprint": "a" * 64,
                            "effective_record_fingerprint": "b" * 64,
                            "changed_fields": ["visibility"],
                            "original_visibility": None,
                            "effective_visibility": "gm",
                            "original_campaign_id": None,
                            "effective_campaign_id": None,
                        }
                    ],
                },
            }
        )


def test_correction_changed_fields_are_closed() -> None:
    with pytest.raises(ValidationError):
        ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1(
            source_artifact_id="src:a",
            original_record_fingerprint="a" * 64,
            effective_record_fingerprint="b" * 64,
            changed_fields=["uri"],  # type: ignore[list-item]
            original_visibility=None,
            effective_visibility="gm",
            original_campaign_id=None,
            effective_campaign_id=None,
        )


def test_repair_intent_unknown_artifact_fails() -> None:
    bundle, raw, _graph, _sources, _contrib, _ident, adoptions, _receipt = (
        _adopt_repairable()
    )
    intent = ExistingWorldAdoptionSourceClassificationRepairIntentV1(
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
        _repair(raw, intent, adoptions)
    assert exc_info.value.details.get("reason") == "repair_intent_unknown_artifact"


def test_visibility_repair_requires_none() -> None:
    bundle, raw, _graph, _sources, _contrib, _ident, adoptions, _receipt = (
        _adopt_repairable()
    )
    already_gm = next(
        artifact
        for artifact in bundle.source_artifacts
        if artifact.visibility is Visibility.GM
    )
    intent = ExistingWorldAdoptionSourceClassificationRepairIntentV1(
        world_id=bundle.world_id,
        adoption_id=bundle.adoption_id,
        repairs=[
            ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1(
                source_artifact_id=already_gm.source_artifact_id,
                set_visibility_to_gm=True,
            )
        ],
    )
    with pytest.raises(PersistenceIntegrityError) as exc_info:
        _repair(raw, intent, adoptions)
    assert exc_info.value.details.get("reason") == "repair_intent_visibility_not_none"


def test_corrupted_v3_fix_forward_and_dry_run() -> None:
    bundle, raw, graph, sources, contributions, identity, adoptions, v3 = (
        _adopt_repairable()
    )
    head_before = graph.get_head(WORLD_ID)
    da_before = v3.published_revision_id
    m0 = sealed_membership_sha256(bundle)
    assert v3.membership_sha256 == m0
    observed = _inject_allowed_corruption(
        sources, contributions, identity, adoptions, bundle
    )
    assert observed != m0
    intent = _intent(bundle)
    dry = _repair(raw, intent, adoptions, apply=False)
    assert isinstance(dry, ExistingWorldAdoptionReceiptV4)
    stored = adoptions.get_for_world(WORLD_ID)
    assert isinstance(stored, ExistingWorldAdoptionReceiptV3)
    assert not isinstance(stored, ExistingWorldAdoptionReceiptV4)
    repaired = _repair(raw, intent, adoptions, apply=True)
    assert isinstance(repaired, ExistingWorldAdoptionReceiptV4)
    assert repaired.membership_sha256 == m0
    assert repaired.effective_membership_sha256 != m0
    assert repaired.published_revision_id == da_before
    assert graph.get_head(WORLD_ID) == head_before
    assert sources._artifacts[ART_A].visibility is Visibility.GM
    assert sources._artifacts[ART_B].campaign_id is None
    assert (
        repaired.source_classification_repair.observed_pre_repair_membership_sha256
        == observed
    )
    replayed = _repair(raw, intent, adoptions, apply=True)
    assert (
        replayed.source_classification_repair.repair_id
        == repaired.source_classification_repair.repair_id
    )


def test_changed_intent_after_v4_conflicts() -> None:
    bundle, raw, _graph, sources, contributions, identity, adoptions, _v3 = (
        _adopt_repairable()
    )
    _inject_allowed_corruption(sources, contributions, identity, adoptions, bundle)
    _repair(raw, _intent(bundle), adoptions)
    with pytest.raises(PersistenceIntegrityError) as exc_info:
        _repair(raw, _intent(bundle, campaign=False), adoptions)
    assert exc_info.value.details.get("reason") == "adoption_repair_identity_mismatch"


@pytest.mark.parametrize(
    "mutator",
    [
        "uri",
        "status",
        "current_revision_id",
        "revision_digest",
        "contribution",
        "identity",
        "bundle_sha256",
        "graph_payload",
        "published_payload",
    ],
)
def test_unexpected_corruption_fails_closed(mutator: str) -> None:
    bundle, raw, graph, sources, contributions, identity, adoptions, v3 = (
        _adopt_repairable()
    )
    _inject_allowed_corruption(sources, contributions, identity, adoptions, bundle)
    if mutator == "uri":
        artifact = sources._artifacts[ART_A]
        sources._artifacts[ART_A] = artifact.model_copy(update={"uri": "https://x"})
    elif mutator == "status":
        artifact = sources._artifacts[ART_A]
        sources._artifacts[ART_A] = artifact.model_copy(
            update={"status": SourceStatus.SUPERSEDED}
        )
    elif mutator == "current_revision_id":
        artifact = sources._artifacts[ART_A]
        sources._artifacts[ART_A] = artifact.model_copy(
            update={"current_revision_id": "srcrev:forged"}
        )
    elif mutator == "revision_digest":
        revision = sources._revisions[bundle.source_revisions[0].source_revision_id]
        sources._revisions[revision.source_revision_id] = revision.model_copy(
            update={"content_sha256": "f" * 64}
        )
    elif mutator == "contribution":
        key = next(iter(contributions._items))
        item = contributions._items[key]
        contributions._items[key] = item.model_copy(
            update={"campaign_scope": "camp:forged"}
        )
    elif mutator == "identity":
        key = (WORLD_ID, "iddec:alias-add")
        item = identity._items[key]
        identity._items[key] = item.model_copy(update={"alias": "forged"})
    elif mutator == "bundle_sha256":
        stored = adoptions._receipts_by_world[WORLD_ID]
        rewritten = stored.model_copy(update={"bundle_sha256": "f" * 64})
        adoptions._receipts_by_world[WORLD_ID] = rewritten
        adoptions._receipts_by_adoption[rewritten.adoption_id] = rewritten
    elif mutator == "graph_payload":
        stored = adoptions._receipts_by_world[WORLD_ID]
        rewritten = stored.model_copy(update={"graph_payload_sha256": "f" * 64})
        adoptions._receipts_by_world[WORLD_ID] = rewritten
        adoptions._receipts_by_adoption[rewritten.adoption_id] = rewritten
    elif mutator == "published_payload":
        stored_rev = graph._revisions[(WORLD_ID, v3.published_revision_id)]
        graph._revisions[(WORLD_ID, v3.published_revision_id)] = stored_rev.model_copy(
            update={"graph_payload": {"forged": True}}
        )
    before = sources._artifacts[ART_A].model_dump(mode="json")
    schema_before = adoptions._receipts_by_world[WORLD_ID].schema_version
    with pytest.raises(PersistenceIntegrityError):
        _repair(raw, _intent(bundle), adoptions)
    assert sources._artifacts[ART_A].model_dump(mode="json") == before
    assert adoptions._receipts_by_world[WORLD_ID].schema_version == schema_before


def test_receipt_membership_must_equal_observed_digest() -> None:
    bundle, raw, _graph, sources, _contrib, _ident, adoptions, v3 = _adopt_repairable()
    sources._artifacts[ART_A] = bundle.source_artifacts[0].model_copy(
        update={"visibility": Visibility.GM}
    )
    assert v3.membership_sha256 == sealed_membership_sha256(bundle)
    with pytest.raises(PersistenceIntegrityError) as exc_info:
        _repair(raw, _intent(bundle), adoptions)
    assert exc_info.value.details.get("reason") == "adoption_repair_membership_mismatch"


def test_atomic_failure_rolls_back() -> None:
    bundle = _repairable_bundle()
    raw = v2_bundle_bytes(bundle)

    def hook(stage: str) -> None:
        if stage == "repaired_artifacts":
            raise RuntimeError("injected repaired_artifacts abort")

    _graph, sources, contributions, identity, adoptions = make_stores(failure_hook=hook)
    adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    _inject_allowed_corruption(sources, contributions, identity, adoptions, bundle)
    with pytest.raises(ExistingWorldAdoptionOutcomeUnknownError):
        _repair(raw, _intent(bundle), adoptions)
    stored = adoptions.get_for_world(WORLD_ID)
    assert isinstance(stored, ExistingWorldAdoptionReceiptV3)
    assert not isinstance(stored, ExistingWorldAdoptionReceiptV4)


def test_recovery_requires_exact_v4_not_unchanged_v3() -> None:
    bundle, raw, _graph, sources, contributions, identity, inner, _v3 = (
        _adopt_repairable()
    )
    _inject_allowed_corruption(sources, contributions, identity, inner, bundle)

    class _FailingRepair:
        def __init__(self, wrapped: InMemoryExistingWorldAdoptionRepository) -> None:
            self.inner = wrapped

        def repair_source_classification(self, command: Any, *, dry_run: bool = False):
            raise RuntimeError("lost before commit")

        def get_for_world(self, world_id: str):
            return self.inner.get_for_world(world_id)

    with pytest.raises(ExistingWorldAdoptionOutcomeUnknownError):
        repair_existing_world_adoption_source_classification(
            raw,
            repair_intent=_intent(bundle),
            repaired_at=REPAIRED_AT,
            adoption_repository=_FailingRepair(inner),  # type: ignore[arg-type]
            graph_reader=graph_reader(),
        )
    stored = inner.get_for_world(WORLD_ID)
    assert isinstance(stored, ExistingWorldAdoptionReceiptV3)
    assert not isinstance(stored, ExistingWorldAdoptionReceiptV4)


def test_recovery_returns_committed_v4() -> None:
    bundle, raw, _graph, sources, contributions, identity, inner, _v3 = (
        _adopt_repairable()
    )
    _inject_allowed_corruption(sources, contributions, identity, inner, bundle)

    class _LostResponse:
        def __init__(self, wrapped: InMemoryExistingWorldAdoptionRepository) -> None:
            self.inner = wrapped

        def repair_source_classification(self, command: Any, *, dry_run: bool = False):
            self.inner.repair_source_classification(command, dry_run=dry_run)
            raise RuntimeError("lost after commit")

        def get_for_world(self, world_id: str):
            return self.inner.get_for_world(world_id)

    recovered = repair_existing_world_adoption_source_classification(
        raw,
        repair_intent=_intent(bundle),
        repaired_at=REPAIRED_AT,
        adoption_repository=_LostResponse(inner),  # type: ignore[arg-type]
        graph_reader=graph_reader(),
    )
    assert isinstance(recovered, ExistingWorldAdoptionReceiptV4)


def test_v4_correspondence_uses_effective_checkpoint() -> None:
    bundle, raw, graph, sources, contributions, identity, adoptions, _v3 = (
        _adopt_repairable()
    )
    _inject_allowed_corruption(sources, contributions, identity, adoptions, bundle)
    repaired = _repair(raw, _intent(bundle), adoptions)
    result = _correspondence(
        graph, sources, contributions, identity, adoptions
    ).check(raw, world_id=WORLD_ID)
    assert result.classification == "CORRESPONDING"
    assert repaired.membership_sha256 == sealed_membership_sha256(bundle)


def test_tampered_v4_correction_is_not_authority() -> None:
    bundle, raw, graph, sources, contributions, identity, adoptions, _v3 = (
        _adopt_repairable()
    )
    _inject_allowed_corruption(sources, contributions, identity, adoptions, bundle)
    _repair(raw, _intent(bundle), adoptions)
    _tamper_v4_effective_fingerprint(adoptions)
    service = _correspondence(graph, sources, contributions, identity, adoptions)
    with pytest.raises(PersistenceIntegrityError) as correspondence_info:
        service.check(raw, world_id=WORLD_ID)
    assert correspondence_info.value.details.get("reason") in {
        "v4_repair_correction_fingerprint_mismatch",
        "v4_repair_effective_fingerprint_mismatch",
    }
    with pytest.raises(PersistenceIntegrityError) as replay_info:
        _repair(raw, _intent(bundle), adoptions)
    assert replay_info.value.details.get("reason") in {
        "v4_repair_correction_fingerprint_mismatch",
        "v4_repair_effective_fingerprint_mismatch",
    }


def test_v4_correspondence_ignores_post_adoption_descendants() -> None:
    bundle, raw, graph, sources, contributions, identity, adoptions, _v3 = (
        _adopt_repairable()
    )
    _inject_allowed_corruption(sources, contributions, identity, adoptions, bundle)
    repaired = _repair(raw, _intent(bundle), adoptions)
    m1 = repaired.effective_membership_sha256
    _append_post_adoption_descendants(sources, contributions, identity)
    result = _correspondence(
        graph, sources, contributions, identity, adoptions
    ).check(raw, world_id=WORLD_ID)
    assert result.classification == "CORRESPONDING"
    assert sources.get_artifact(DESCENDANT_ARTIFACT_ID) is not None
    assert sources.get_revision(DESCENDANT_REVISION_ID) is not None
    assert sources.get_revision(DESCENDANT_ON_ADOPTED_REVISION_ID) is not None
    assert contributions.get(WORLD_ID, DESCENDANT_CONTRIBUTION_ID) is not None
    assert identity.get(WORLD_ID, DESCENDANT_IDENTITY_ID) is not None
    manifest = repaired.membership_manifest
    assert DESCENDANT_ARTIFACT_ID not in manifest.source_artifact_ids
    assert DESCENDANT_REVISION_ID not in manifest.source_revision_ids
    assert DESCENDANT_ON_ADOPTED_REVISION_ID not in manifest.source_revision_ids
    assert DESCENDANT_CONTRIBUTION_ID not in manifest.contribution_ids
    assert DESCENDANT_IDENTITY_ID not in manifest.identity_decision_ids
    current_m1 = existing_world_adoption_membership_sha256(
        source_artifacts=[
            sources._artifacts[item_id] for item_id in manifest.source_artifact_ids
        ],
        source_revisions=[
            sources._revisions[item_id] for item_id in manifest.source_revision_ids
        ],
        contributions=[
            contributions._items[(WORLD_ID, item_id)]
            for item_id in manifest.contribution_ids
        ],
        identity_decisions=[
            identity._items[(WORLD_ID, item_id)]
            for item_id in manifest.identity_decision_ids
        ],
    )
    assert current_m1 == m1
    assert (
        _world_membership(sources, contributions, identity, WORLD_ID) != m1
    )


def test_v3_correspondence_still_treats_descendants_as_extras() -> None:
    _bundle, raw, graph, sources, contributions, identity, adoptions, receipt = (
        _adopt_repairable()
    )
    assert isinstance(receipt, ExistingWorldAdoptionReceiptV3)
    assert not isinstance(receipt, ExistingWorldAdoptionReceiptV4)
    _append_post_adoption_descendants(sources, contributions, identity)
    result = _correspondence(
        graph, sources, contributions, identity, adoptions
    ).check(raw, world_id=WORLD_ID)
    assert result.classification == "MISMATCH"
    checks = {check.check: check for check in result.checks}
    assert DESCENDANT_ARTIFACT_ID in (checks["source_history"].detail or "")
    assert DESCENDANT_CONTRIBUTION_ID in (
        checks["contribution_history"].detail or ""
    )
    assert DESCENDANT_IDENTITY_ID in (checks["identity_history"].detail or "")


def test_eldyrwild_fixture_manifest_and_deterministic_m0_m1() -> None:
    raw = eldyrwild_raw_bundle()
    assert sha256_bytes(raw) == ELDYRWILD_BUNDLE_SHA256
    bundle = parse_sealed_bundle()
    manifest = derive_membership_manifest(bundle)
    assert len(manifest.source_artifact_ids) == EXPECTED_SOURCE_ARTIFACTS
    assert len(manifest.source_revision_ids) == EXPECTED_SOURCE_REVISIONS
    assert len(manifest.contribution_ids) == EXPECTED_CONTRIBUTIONS
    assert len(manifest.identity_decision_ids) == EXPECTED_IDENTITY_DECISIONS
    m0 = sealed_membership_sha256(bundle)
    unnamed = next(
        artifact for artifact in bundle.source_artifacts if artifact.visibility is None
    )
    intent = ExistingWorldAdoptionSourceClassificationRepairIntentV1(
        world_id=bundle.world_id,
        adoption_id=bundle.adoption_id,
        repairs=[
            ExistingWorldAdoptionSourceArtifactClassificationRepairIntentV1(
                source_artifact_id=unnamed.source_artifact_id,
                set_visibility_to_gm=True,
            )
        ],
    )
    _graph, sources, contributions, identity, adoptions = make_stores()
    adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=eldyrwild_graph_reader(),
    )
    sources._artifacts[unnamed.source_artifact_id] = unnamed.model_copy(
        update={"visibility": Visibility.GM}
    )
    digest = _world_membership(sources, contributions, identity, bundle.world_id)
    stored = adoptions._receipts_by_world[bundle.world_id]
    rewritten = stored.model_copy(update={"membership_sha256": digest})
    adoptions._receipts_by_world[bundle.world_id] = rewritten
    adoptions._receipts_by_adoption[rewritten.adoption_id] = rewritten
    repaired = repair_existing_world_adoption_source_classification(
        raw,
        repair_intent=intent,
        repaired_at=REPAIRED_AT,
        adoption_repository=adoptions,
        graph_reader=eldyrwild_graph_reader(),
    )
    assert repaired.membership_sha256 == m0
    assert repaired.effective_membership_sha256 != m0
    assert repaired.membership_manifest == manifest
    replayed = repair_existing_world_adoption_source_classification(
        raw,
        repair_intent=intent,
        repaired_at=REPAIRED_AT,
        adoption_repository=adoptions,
        graph_reader=eldyrwild_graph_reader(),
    )
    assert replayed.effective_membership_sha256 == repaired.effective_membership_sha256
