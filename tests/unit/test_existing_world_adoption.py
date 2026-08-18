"""Contract, application, and in-memory proofs for existing-world adoption."""

from __future__ import annotations

import ast
import inspect
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from dungeonmind.application.existing_world_adoption import (
    adopt_existing_world,
    parse_existing_world_adoption_bundle,
    promote_existing_world_adoption_receipt_v3,
)
from dungeonmind.application.existing_world_correspondence import (
    ExistingWorldCorrespondenceService,
)
from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V6,
    RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts.contribution import (
    AcceptanceState,
    ContributionSourceKind,
    GraphContribution,
    GraphContributionAssertion,
    GraphContributionAssertionCorrection,
    GraphContributionAssertionCorrectionKind,
    GraphContributionAssertionV2,
    GraphContributionV2,
)
from dungeonmind.contracts.evidence import (
    SourceArtifactV2,
    SourceAuthority,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.existing_world_adoption import (
    EXISTING_WORLD_ADOPTION_BUNDLE_SCHEMA,
    EXISTING_WORLD_ADOPTION_BUNDLE_V2_SCHEMA,
    EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA,
    ExistingWorldAdoptionAuthorityRefV1,
    ExistingWorldAdoptionBundleV1,
    ExistingWorldAdoptionBundleV2,
    ExistingWorldAdoptionCommandV1,
    ExistingWorldAdoptionReceiptV2,
    ExistingWorldAdoptionReceiptV3,
    ExistingWorldAdoptionSourceProvenanceV1,
    existing_world_adoption_bundle_canonical_bytes,
    existing_world_adoption_bundle_v2_canonical_bytes,
    sha256_bytes,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.identity import (
    IdentityAliasMapRewrite,
    IdentityDecisionKind,
    IdentityDecisionRecord,
    IdentityDecisionRecordV2,
    IdentityDecisionStatus,
    IdentityMergeSideEffects,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.contracts.vocabulary import ContributionEpistemicKind, Visibility
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    ExistingWorldAdoptionOutcomeUnknownError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
)
from dungeonmind.domain.existing_world_membership import (
    EXISTING_WORLD_ADOPTION_MEMBERSHIP_SCHEMA,
    existing_world_adoption_membership_sha256,
)
from dungeonmind.domain.revision_ids import compute_revision_id
from dungeonmind.infrastructure.memory import (
    InMemoryContributionRepository,
    InMemoryExistingWorldAdoptionRepository,
    InMemoryIdentityDecisionRepository,
    InMemorySourceRepository,
    InMemoryWorldGraphRepository,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry

WORLD_ID = "world:existing-adoption-fixture"
CAMPAIGN_ID = "camp:existing-adoption-fixture"
ADOPTION_ID = "adopt:existing-fixture-v1"
NOW = datetime(2026, 8, 15, 19, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
SRC = Path(__file__).resolve().parents[2] / "src" / "dungeonmind"
DESCRIPTOR_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "semantic_profiles" / "test-kernel-v1.json"
)
ART_A = "src:notes-a"
ART_B = "src:notes-b"
REV_A = "srcrev:notes-a-v1"
REV_B = "srcrev:notes-b-v1"
BODY_A = "a" * 64
BODY_B = "b" * 64


def _descriptor() -> SemanticProfileDescriptor:
    return SemanticProfileDescriptor.model_validate(
        json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    )


def _registry() -> StaticSemanticProfileRegistry:
    return StaticSemanticProfileRegistry([_descriptor()])


def graph_reader() -> VersionedUnionGraphSnapshotReader:
    return VersionedUnionGraphSnapshotReader(profile_registry=_registry())


def _profile_ref() -> dict[str, Any]:
    descriptor = _descriptor()
    return {
        "schema_version": "dm_semantic_profile_ref_v1",
        "profile_id": descriptor.profile_id,
        "profile_revision": descriptor.profile_revision,
        "descriptor_sha256": descriptor_sha256(descriptor),
    }


def _meta(assertion_id: str, *, evidence: tuple[str, ...] = ("ev:a",)) -> dict[str, Any]:
    return {
        "schema_version": "dm_knowledge_assertion_metadata_v1",
        "assertion_id": assertion_id,
        "campaign_scope": CAMPAIGN_ID,
        "visibility": "player",
        "epistemic_kind": "asserted",
        "canon_state": "canonical",
        "evidence_ref_ids": list(evidence),
        "session_refs": [],
        "temporal_scope": {"schema_version": "dm_temporal_scope_ref_v1", "kind": "unknown"},
    }


def _evidence(evidence_ref_id: str, artifact_id: str, revision_id: str) -> dict[str, Any]:
    return {
        "schema_version": "dm_evidence_ref_v2",
        "evidence_ref_id": evidence_ref_id,
        "source_artifact_id": artifact_id,
        "source_revision_id": revision_id,
        "source_domain_key": "producer.worldbuilding",
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


def v6_graph_payload(*, world_id: str = WORLD_ID) -> dict[str, Any]:
    return {
        "world_id": world_id,
        "semantic_profile": _profile_ref(),
        "relationship_endpoint_aspect_schema": RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
        "objects": [
            {
                "object_id": "obj:college",
                "kind": "test:location",
                "label": "Wizard College",
                "assertion_metadata": _meta("asrt:college-exists"),
                "aliases": [],
                "summary": None,
                "properties": [],
                "aspects": [
                    {
                        "aspect_key": "organization",
                        "kind": "test:faction",
                        "assertion_metadata": _meta("asrt:college-org", evidence=("ev:b",)),
                    }
                ],
            },
            {
                "object_id": "obj:headmaster",
                "kind": "test:person",
                "label": "Headmaster",
                "assertion_metadata": _meta("asrt:headmaster-exists"),
                "aliases": [],
                "summary": None,
                "properties": [],
                "aspects": [],
            },
        ],
        "relationships": [
            {
                "relationship_id": "rel:leads",
                "source_object_id": "obj:headmaster",
                "target_object_id": "obj:college",
                "predicate": "test:leads",
                "assertion_metadata": _meta("asrt:leads"),
                "source_aspect_assertion_id": None,
                "target_aspect_assertion_id": "asrt:college-org",
            },
            {
                "relationship_id": "rel:travels",
                "source_object_id": "obj:headmaster",
                "target_object_id": "obj:college",
                "predicate": "test:travels_to",
                "assertion_metadata": _meta("asrt:travels"),
            },
        ],
        "evidence_refs": [
            _evidence("ev:a", ART_A, REV_A),
            _evidence("ev:b", ART_B, REV_B),
        ],
    }


def _artifact(
    source_artifact_id: str, revision_id: str, *, world_id: str = WORLD_ID
) -> SourceArtifactV2:
    return SourceArtifactV2(
        source_artifact_id=source_artifact_id,
        source_domain_key="producer.worldbuilding",
        source_domain=SourceDomain.WORLDBUILDING,
        world_id=world_id,
        campaign_id=None,
        session_id=None,
        uri=None,
        current_revision_id=revision_id,
        authority=SourceAuthority.PRIMARY,
        visibility=Visibility.GM,
        artifact_kind="note",
        document_class=None,
        review_state=None,
        source_visibility_state=None,
        workspace_document_ref=None,
        lineage={},
        status=SourceStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
    )


def _revision(source_revision_id: str, source_artifact_id: str, digest: str) -> SourceRevision:
    return SourceRevision(
        source_revision_id=source_revision_id,
        source_artifact_id=source_artifact_id,
        content_sha256=digest,
        body_storage="object_store",
        locator=f"object://{source_revision_id}",
        created_at=NOW,
    )


def _contribution(
    contribution_id: str,
    artifact_id: str,
    revision_id: str,
    *,
    world_id: str = WORLD_ID,
) -> GraphContribution:
    return GraphContribution(
        contribution_id=contribution_id,
        world_id=world_id,
        source_kind=ContributionSourceKind.MANUAL_IMPORT,
        source_artifact_id=artifact_id,
        source_revision_id=revision_id,
        produced_at=NOW,
        campaign_scope=CAMPAIGN_ID,
        assertions=[
            GraphContributionAssertion(
                assertion_id=f"asrt:{contribution_id}",
                assertion_kind="attribute",
                subject_object_id="obj:college",
                label="imported",
                source_artifact_id=artifact_id,
                source_revision_id=revision_id,
                campaign_scope=CAMPAIGN_ID,
                acceptance_state=AcceptanceState.ACCEPTED,
            )
        ],
    )


def _alias_decision(
    decision_id: str,
    *,
    kind: IdentityDecisionKind,
    alias: str,
    world_id: str = WORLD_ID,
) -> IdentityDecisionRecord:
    return IdentityDecisionRecord(
        decision_id=decision_id,
        world_id=world_id,
        decision_kind=kind,
        subject_object_ids=["obj:college"],
        alias=alias,
        status=IdentityDecisionStatus.ACTIVE,
        created_at=NOW,
    )


def make_bundle(
    *,
    adoption_id: str = ADOPTION_ID,
    world_id: str = WORLD_ID,
    graph_payload: dict[str, Any] | None = None,
    source_artifacts: list[SourceArtifactV2] | None = None,
    source_revisions: list[SourceRevision] | None = None,
    contributions: list[GraphContribution] | None = None,
    identity_decisions: list[IdentityDecisionRecord] | None = None,
    extra_authority: bool = True,
) -> ExistingWorldAdoptionBundleV1:
    refs = [
        ExistingWorldAdoptionAuthorityRefV1(
            schema="dm_producer_package_v1",
            identifier="pkg:alpha",
            sha256="11" * 32,
        ),
        ExistingWorldAdoptionAuthorityRefV1(
            schema="dm_producer_package_v1",
            identifier="pkg:beta",
            sha256="22" * 32,
        ),
    ]
    if not extra_authority:
        refs = refs[:1]
    payload = graph_payload if graph_payload is not None else v6_graph_payload(world_id=world_id)
    return ExistingWorldAdoptionBundleV1(
        adoption_id=adoption_id,
        world_id=world_id,
        source_provenance=ExistingWorldAdoptionSourceProvenanceV1(
            producer_id="producer:test-kernel",
            producer_revision="rev:test-1",
            source_world_revision_id="rev:producer-head",
            source_graph_payload_sha256=canonical_sha256(payload),
            authority_refs=refs,
        ),
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload=payload,
        source_artifacts=source_artifacts or [_artifact(ART_A, REV_A), _artifact(ART_B, REV_B)],
        source_revisions=source_revisions
        or [_revision(REV_A, ART_A, BODY_A), _revision(REV_B, ART_B, BODY_B)],
        contributions=contributions
        or [
            _contribution("contrib:import-1", ART_A, REV_A),
            _contribution("contrib:import-2", ART_B, REV_B),
        ],
        identity_decisions=identity_decisions
        or [
            _alias_decision(
                "iddec:alias-add",
                kind=IdentityDecisionKind.ALIAS_ADD,
                alias="College",
            ),
            _alias_decision(
                "iddec:alias-remove",
                kind=IdentityDecisionKind.ALIAS_REMOVE,
                alias="Old College",
            ),
        ],
    )


def bundle_bytes(bundle: ExistingWorldAdoptionBundleV1 | None = None) -> bytes:
    return existing_world_adoption_bundle_canonical_bytes(bundle or make_bundle())


def make_isolated_bundle(
    *,
    world_id: str,
    adoption_id: str,
    token: str,
) -> ExistingWorldAdoptionBundleV1:
    art_a = f"{ART_A}:{token}"
    art_b = f"{ART_B}:{token}"
    rev_a = f"{REV_A}:{token}"
    rev_b = f"{REV_B}:{token}"
    payload = v6_graph_payload(world_id=world_id)
    payload["evidence_refs"][0]["source_artifact_id"] = art_a
    payload["evidence_refs"][0]["source_revision_id"] = rev_a
    payload["evidence_refs"][1]["source_artifact_id"] = art_b
    payload["evidence_refs"][1]["source_revision_id"] = rev_b
    return make_bundle(
        adoption_id=adoption_id,
        world_id=world_id,
        graph_payload=payload,
        source_artifacts=[
            _artifact(art_a, rev_a, world_id=world_id),
            _artifact(art_b, rev_b, world_id=world_id),
        ],
        source_revisions=[
            _revision(rev_a, art_a, BODY_A),
            _revision(rev_b, art_b, BODY_B),
        ],
        contributions=[
            _contribution(f"contrib:import-1:{token}", art_a, rev_a, world_id=world_id),
            _contribution(f"contrib:import-2:{token}", art_b, rev_b, world_id=world_id),
        ],
        identity_decisions=[
            _alias_decision(
                f"iddec:alias-add:{token}",
                kind=IdentityDecisionKind.ALIAS_ADD,
                alias="College",
                world_id=world_id,
            ),
            _alias_decision(
                f"iddec:alias-remove:{token}",
                kind=IdentityDecisionKind.ALIAS_REMOVE,
                alias="Old College",
                world_id=world_id,
            ),
        ],
    )


def make_command(
    bundle: ExistingWorldAdoptionBundleV1 | None = None,
    *,
    bundle_sha256: str | None = None,
    graph_payload_sha256: str | None = None,
    expected_published_revision_id: str | None = None,
    requested_adopted_at: datetime = NOW,
) -> ExistingWorldAdoptionCommandV1:
    resolved = bundle or make_bundle()
    raw = existing_world_adoption_bundle_canonical_bytes(resolved)
    graph_sha = canonical_sha256(resolved.graph_payload)
    revision_id = compute_revision_id(
        world_id=resolved.world_id,
        parent_revision_id=None,
        operation_ids=[resolved.adoption_id],
        graph_schema=resolved.graph_schema,
        graph_payload_sha256=graph_sha,
    )
    return ExistingWorldAdoptionCommandV1(
        bundle=resolved,
        bundle_sha256=bundle_sha256 if bundle_sha256 is not None else sha256_bytes(raw),
        graph_payload_sha256=(
            graph_payload_sha256 if graph_payload_sha256 is not None else graph_sha
        ),
        expected_published_revision_id=(
            expected_published_revision_id
            if expected_published_revision_id is not None
            else revision_id
        ),
        requested_adopted_at=requested_adopted_at,
    )


def make_stores(
    *,
    failure_hook=None,
) -> tuple[
    InMemoryWorldGraphRepository,
    InMemorySourceRepository,
    InMemoryContributionRepository,
    InMemoryIdentityDecisionRepository,
    InMemoryExistingWorldAdoptionRepository,
]:
    graph = InMemoryWorldGraphRepository()
    sources = InMemorySourceRepository()
    contributions = InMemoryContributionRepository()
    identity = InMemoryIdentityDecisionRepository()
    adoptions = InMemoryExistingWorldAdoptionRepository(
        graph,
        sources,
        contributions,
        identity,
        failure_hook=failure_hook,
    )
    return graph, sources, contributions, identity, adoptions


def _v2_assertion(
    assertion_id: str,
    artifact_id: str,
    revision_id: str,
    *,
    epistemic_kind: ContributionEpistemicKind = ContributionEpistemicKind.ASSERTED,
    acceptance_state: AcceptanceState = AcceptanceState.ACCEPTED,
) -> GraphContributionAssertionV2:
    return GraphContributionAssertionV2(
        assertion_id=assertion_id,
        assertion_kind="attribute",
        subject_object_id="obj:college",
        label="imported",
        source_artifact_id=artifact_id,
        source_revision_id=revision_id,
        campaign_scope=CAMPAIGN_ID,
        epistemic_kind=epistemic_kind,
        acceptance_state=acceptance_state,
    )


def _v2_contribution(
    contribution_id: str,
    artifact_id: str,
    revision_id: str,
    *,
    world_id: str = WORLD_ID,
    assertions: list[GraphContributionAssertionV2] | None = None,
    corrections: list[GraphContributionAssertionCorrection] | None = None,
) -> GraphContributionV2:
    return GraphContributionV2(
        contribution_id=contribution_id,
        world_id=world_id,
        source_kind=ContributionSourceKind.MANUAL_IMPORT,
        source_artifact_id=artifact_id,
        source_revision_id=revision_id,
        produced_at=NOW,
        campaign_scope=CAMPAIGN_ID,
        assertions=assertions
        or [_v2_assertion(f"asrt:{contribution_id}", artifact_id, revision_id)],
        assertion_corrections=corrections or [],
    )


def _merge_side_effects() -> IdentityMergeSideEffects:
    return IdentityMergeSideEffects(
        aliases_added_to_target=["College of Wizardry"],
        evidence_ref_ids_added_to_target=["ev:a"],
        source_domains_added_to_target=["worldbuilding"],
        alias_map_rewrites=[
            IdentityAliasMapRewrite(
                alias_key="merged-headmaster",
                prior_owner_node_id="obj:merged-away",
                new_owner_node_id="obj:college",
            ),
            IdentityAliasMapRewrite(
                alias_key="college",
                prior_owner_node_id=None,
                new_owner_node_id="obj:college",
            ),
        ],
    )


def make_v2_bundle(
    *,
    adoption_id: str = "adopt:existing-fixture-v2",
    world_id: str = WORLD_ID,
    contributions: list[GraphContributionV2] | None = None,
    identity_decisions: list[IdentityDecisionRecordV2] | None = None,
) -> ExistingWorldAdoptionBundleV2:
    v1 = make_bundle(adoption_id=adoption_id, world_id=world_id)
    if contributions is None:
        target = _v2_contribution("contrib:target", ART_A, REV_A, world_id=world_id)
        corrector = _v2_contribution(
            "contrib:corrector",
            ART_B,
            REV_B,
            world_id=world_id,
            assertions=[
                _v2_assertion("asrt:replacement", ART_B, REV_B),
                _v2_assertion(
                    "asrt:source-derived",
                    ART_B,
                    REV_B,
                    epistemic_kind=ContributionEpistemicKind.SOURCE_DERIVED_CANDIDATE,
                    acceptance_state=AcceptanceState.CANDIDATE,
                ),
            ],
            corrections=[
                GraphContributionAssertionCorrection(
                    correction_kind=GraphContributionAssertionCorrectionKind.CONTRADICTS,
                    target_contribution_id="contrib:target",
                    target_assertion_id="asrt:contrib:target",
                ),
                GraphContributionAssertionCorrection(
                    correction_kind=GraphContributionAssertionCorrectionKind.CONTRADICTS_AND_REPLACES,
                    target_contribution_id="contrib:target",
                    target_assertion_id="asrt:contrib:target",
                    replacement_assertion_id="asrt:replacement",
                ),
            ],
        )
        contributions = [target, corrector]
    if identity_decisions is None:
        identity_decisions = [
            IdentityDecisionRecordV2(
                decision_id="iddec:alias-add",
                world_id=world_id,
                decision_kind=IdentityDecisionKind.ALIAS_ADD,
                subject_object_ids=["obj:college"],
                alias="College",
                status=IdentityDecisionStatus.ACTIVE,
                created_at=NOW,
                merge_side_effects=None,
            ),
            IdentityDecisionRecordV2(
                decision_id="iddec:merge",
                world_id=world_id,
                decision_kind=IdentityDecisionKind.MERGE,
                subject_object_ids=["obj:merged-away", "obj:college"],
                target_object_ids=["obj:college"],
                status=IdentityDecisionStatus.ACTIVE,
                created_at=NOW,
                merge_side_effects=_merge_side_effects(),
            ),
        ]
    return ExistingWorldAdoptionBundleV2(
        adoption_id=v1.adoption_id,
        world_id=v1.world_id,
        source_provenance=v1.source_provenance,
        graph_schema=v1.graph_schema,
        graph_payload=v1.graph_payload,
        source_artifacts=v1.source_artifacts,
        source_revisions=v1.source_revisions,
        contributions=contributions,
        identity_decisions=identity_decisions,
    )


def v2_bundle_bytes(bundle: ExistingWorldAdoptionBundleV2 | None = None) -> bytes:
    return existing_world_adoption_bundle_v2_canonical_bytes(bundle or make_v2_bundle())


class _SpyAdoption:
    def __init__(self, inner: InMemoryExistingWorldAdoptionRepository) -> None:
        self.inner = inner
        self.adopt_calls = 0
        self.get_for_world_calls = 0

    def adopt(self, command):
        self.adopt_calls += 1
        return self.inner.adopt(command)

    def get(self, world_id: str, adoption_id: str):
        return self.inner.get(world_id, adoption_id)

    def get_for_world(self, world_id: str):
        self.get_for_world_calls += 1
        return self.inner.get_for_world(world_id)

    def promote_to_v3_receipt(
        self, world_id: str, *, expected, promoted, current_membership_sha256
    ):
        return self.inner.promote_to_v3_receipt(
            world_id,
            expected=expected,
            promoted=promoted,
            current_membership_sha256=current_membership_sha256,
        )


class _BoomReader:
    def parse(self, *, graph_schema: str, graph_payload: dict[str, Any]):
        raise AssertionError("graph_reader must not run on exact replay")


def test_t1_strict_bundle_shape() -> None:
    bundle = make_bundle()
    parsed = ExistingWorldAdoptionBundleV1.model_validate(
        bundle.model_dump(mode="json", by_alias=True)
    )
    assert parsed.schema_version == EXISTING_WORLD_ADOPTION_BUNDLE_SCHEMA
    payload = json.loads(bundle_bytes(bundle))
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        ExistingWorldAdoptionBundleV1.model_validate(payload)
    payload = json.loads(bundle_bytes(bundle))
    payload["schema_version"] = "dm_existing_world_adoption_bundle_v0"
    with pytest.raises(ValidationError):
        ExistingWorldAdoptionBundleV1.model_validate(payload)
    payload = json.loads(bundle_bytes(bundle))
    payload["adoption_id"] = "   "
    blank = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    with pytest.raises(PersistenceIntegrityError):
        parse_existing_world_adoption_bundle(blank, graph_reader=graph_reader())


def test_t2_canonical_bytes_sort_lists_and_refuse_unsorted() -> None:
    forward = make_bundle()
    reversed_artifacts = list(reversed(forward.source_artifacts))
    reversed_bundle = forward.model_copy(update={"source_artifacts": reversed_artifacts})
    assert bundle_bytes(forward) == bundle_bytes(reversed_bundle)
    payload = json.loads(bundle_bytes(forward))
    payload["source_artifacts"] = list(reversed(payload["source_artifacts"]))
    noncanonical = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    assert noncanonical != bundle_bytes(forward)
    with pytest.raises(PersistenceIntegrityError):
        parse_existing_world_adoption_bundle(noncanonical, graph_reader=graph_reader())


def test_t3_application_owns_bundle_sha() -> None:
    parameters = inspect.signature(adopt_existing_world).parameters
    assert "bundle_sha256" not in parameters
    assert "raw_bundle" in parameters
    raw = bundle_bytes()
    _, _, _, _, adoptions = make_stores()
    receipt = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    assert receipt.bundle_sha256 == sha256_bytes(raw)


def test_t4_duplicate_durable_ids_refuse() -> None:
    bundle = make_bundle()
    duplicate = bundle.model_copy(
        update={"source_artifacts": [*bundle.source_artifacts, bundle.source_artifacts[0]]}
    )
    with pytest.raises(PersistenceIntegrityError):
        parse_existing_world_adoption_bundle(bundle_bytes(duplicate), graph_reader=graph_reader())


def test_t5_world_drift_refuses_before_repository() -> None:
    spy = _SpyAdoption(make_stores()[4])
    drifted = _artifact(ART_A, REV_A).model_copy(update={"world_id": "world:other"})
    bundle = make_bundle(source_artifacts=[drifted, _artifact(ART_B, REV_B)])
    with pytest.raises(PersistenceIntegrityError):
        adopt_existing_world(
            bundle_bytes(bundle),
            adopted_at=NOW,
            adoption_repository=spy,
            graph_reader=graph_reader(),
        )
    assert spy.adopt_calls == 0


def test_t6_source_revision_closure_refuses() -> None:
    artifact = _artifact(ART_A, "srcrev:missing")
    bundle = make_bundle(source_artifacts=[artifact, _artifact(ART_B, REV_B)])
    with pytest.raises(PersistenceIntegrityError):
        parse_existing_world_adoption_bundle(bundle_bytes(bundle), graph_reader=graph_reader())


def test_t7_contribution_source_closure_refuses() -> None:
    contribution = _contribution("contrib:import-1", "src:missing", REV_A)
    bundle = make_bundle(
        contributions=[contribution, _contribution("contrib:import-2", ART_B, REV_B)]
    )
    with pytest.raises(PersistenceIntegrityError):
        parse_existing_world_adoption_bundle(bundle_bytes(bundle), graph_reader=graph_reader())


def test_t8_v6_graph_parse_refuses_malformed() -> None:
    payload = v6_graph_payload()
    del payload["relationship_endpoint_aspect_schema"]
    with pytest.raises(PersistenceIntegrityError):
        parse_existing_world_adoption_bundle(
            bundle_bytes(make_bundle(graph_payload=payload)),
            graph_reader=graph_reader(),
        )
    payload = v6_graph_payload()
    payload["relationships"][0]["target_aspect_assertion_id"] = "asrt:missing"
    with pytest.raises(PersistenceIntegrityError):
        parse_existing_world_adoption_bundle(
            bundle_bytes(make_bundle(graph_payload=payload)),
            graph_reader=graph_reader(),
        )


def test_t9_graph_evidence_must_close_over_bundle_sources() -> None:
    payload = v6_graph_payload()
    payload["evidence_refs"][0]["source_artifact_id"] = "src:outside"
    with pytest.raises(PersistenceIntegrityError):
        parse_existing_world_adoption_bundle(
            bundle_bytes(make_bundle(graph_payload=payload)),
            graph_reader=graph_reader(),
        )


def test_t10_first_revision_identity_uses_existing_helper() -> None:
    raw = bundle_bytes()
    bundle = parse_existing_world_adoption_bundle(raw, graph_reader=graph_reader())
    expected = compute_revision_id(
        world_id=bundle.world_id,
        parent_revision_id=None,
        operation_ids=[bundle.adoption_id],
        graph_schema=GRAPH_SCHEMA_V6,
        graph_payload_sha256=canonical_sha256(bundle.graph_payload),
    )
    _, _, _, _, adoptions = make_stores()
    receipt = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    assert receipt.published_revision_id == expected


def test_t11_durable_first_replay_skips_reader_and_mutation() -> None:
    raw = bundle_bytes()
    _, _, _, _, adoptions = make_stores()
    first = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    spy = _SpyAdoption(adoptions)
    replayed = adopt_existing_world(
        raw,
        adopted_at=LATER,
        adoption_repository=spy,
        graph_reader=_BoomReader(),  # type: ignore[arg-type]
    )
    assert spy.adopt_calls == 0
    assert replayed == first
    assert replayed.adopted_at == NOW


def test_t12_same_world_different_bundle_conflicts() -> None:
    _, _, _, _, adoptions = make_stores()
    adopt_existing_world(
        bundle_bytes(),
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    other = make_bundle()
    other = other.model_copy(
        update={
            "source_provenance": other.source_provenance.model_copy(
                update={"producer_revision": "rev:test-2"}
            )
        }
    )
    with pytest.raises(IdempotencyConflictError):
        adopt_existing_world(
            bundle_bytes(other),
            adopted_at=NOW,
            adoption_repository=adoptions,
            graph_reader=graph_reader(),
        )


def test_t13_different_adoption_on_adopted_world_refuses() -> None:
    _, _, _, _, adoptions = make_stores()
    adopt_existing_world(
        bundle_bytes(),
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    other = make_bundle(adoption_id="adopt:second")
    other = other.model_copy(
        update={
            "source_provenance": other.source_provenance.model_copy(
                update={"producer_id": "producer:other"}
            )
        }
    )
    with pytest.raises(IdempotencyConflictError):
        adopt_existing_world(
            bundle_bytes(other),
            adopted_at=NOW,
            adoption_repository=adoptions,
            graph_reader=graph_reader(),
        )


def test_t14_recovery_does_not_infer_from_head() -> None:
    source = inspect.getsource(adopt_existing_world)
    assert "get_head" not in source
    assert "get_revision" not in source


def test_t15_response_loss_recovery_returns_receipt() -> None:
    raw = bundle_bytes()
    _, _, _, _, inner = make_stores()

    class _CommitThenUnavailable:
        def adopt(self, command):
            inner.adopt(command)
            raise PersistenceUnavailableError("response lost")

        def get(self, world_id: str, adoption_id: str):
            return inner.get(world_id, adoption_id)

        def get_for_world(self, world_id: str):
            return inner.get_for_world(world_id)

    receipt = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=_CommitThenUnavailable(),  # type: ignore[arg-type]
        graph_reader=graph_reader(),
    )
    assert receipt.world_id == WORLD_ID
    assert receipt.bundle_sha256 == sha256_bytes(raw)


def test_t15_v2_response_loss_recovery_returns_v3_receipt() -> None:
    raw = v2_bundle_bytes()
    _, _, _, _, inner = make_stores()

    class _CommitThenUnavailable:
        def __init__(self) -> None:
            self.adopt_calls = 0
            self.recovery_probes = 0

        def adopt(self, command):
            self.adopt_calls += 1
            inner.adopt(command)
            raise PersistenceUnavailableError("response lost")

        def get(self, world_id: str, adoption_id: str):
            return inner.get(world_id, adoption_id)

        def get_for_world(self, world_id: str):
            receipt = inner.get_for_world(world_id)
            if self.adopt_calls:
                self.recovery_probes += 1
            return receipt

    wrapper = _CommitThenUnavailable()
    receipt = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=wrapper,  # type: ignore[arg-type]
        graph_reader=graph_reader(),
    )
    assert wrapper.adopt_calls == 1
    assert wrapper.recovery_probes == 1
    assert receipt.schema_version == EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA
    assert receipt.world_id == WORLD_ID
    assert receipt.bundle_sha256 == sha256_bytes(raw)
    replayed = adopt_existing_world(
        raw,
        adopted_at=LATER,
        adoption_repository=inner,
        graph_reader=_BoomReader(),  # type: ignore[arg-type]
    )
    assert replayed == receipt
    assert wrapper.adopt_calls == 1


def test_t16_unknown_outcome_when_recovery_unavailable() -> None:
    class _Unavailable:
        def __init__(self) -> None:
            self.gets = 0

        def get_for_world(self, world_id: str):
            self.gets += 1
            if self.gets == 1:
                return None
            raise PersistenceUnavailableError("probe failed")

        def adopt(self, command):
            raise PersistenceUnavailableError("mutate failed")

        def get(self, world_id: str, adoption_id: str):
            return None

    with pytest.raises(ExistingWorldAdoptionOutcomeUnknownError) as exc:
        adopt_existing_world(
            bundle_bytes(),
            adopted_at=NOW,
            adoption_repository=_Unavailable(),  # type: ignore[arg-type]
            graph_reader=graph_reader(),
        )
    assert exc.value.details["retry_safe"] is True
    assert exc.value.details["world_id"] == WORLD_ID
    assert exc.value.details["adoption_id"] == ADOPTION_ID
    assert "bundle_sha256" in exc.value.details
    assert "expected_published_revision_id" in exc.value.details


def test_t17_known_failure_is_preserved() -> None:
    class _Known:
        def get_for_world(self, world_id: str):
            return None

        def adopt(self, command):
            raise PersistenceIntegrityError(
                "existing-world adoption target is not pristine",
                details={"reason": "non_pristine_target"},
            )

        def get(self, world_id: str, adoption_id: str):
            return None

    with pytest.raises(PersistenceIntegrityError, match="not pristine"):
        adopt_existing_world(
            bundle_bytes(),
            adopted_at=NOW,
            adoption_repository=_Known(),  # type: ignore[arg-type]
            graph_reader=graph_reader(),
        )


def test_t18_atomic_successful_adoption_exposes_all_families() -> None:
    graph, sources, contributions, identity, adoptions = make_stores()
    raw = bundle_bytes()
    receipt = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    bundle = parse_existing_world_adoption_bundle(raw, graph_reader=graph_reader())
    assert graph.get_head(WORLD_ID) is not None
    assert graph.get_head(WORLD_ID).head_revision_id == receipt.published_revision_id
    stored = graph.get_revision(WORLD_ID, receipt.published_revision_id)
    assert stored is not None
    assert stored.revision.parent_revision_id is None
    assert stored.revision.operation_ids == [ADOPTION_ID]
    assert sources.get_artifact(ART_A) is not None
    assert sources.get_revision(REV_B) is not None
    assert len(contributions.list_for_world(WORLD_ID)) == 2
    assert len(identity.list_for_world(WORLD_ID)) == 2
    assert adoptions.get_for_world(WORLD_ID) == receipt
    assert receipt.source_artifact_count == len(bundle.source_artifacts)


def test_t19_same_bundle_concurrency_converges() -> None:
    _, _, _, _, adoptions = make_stores()
    raw = bundle_bytes()
    barrier = threading.Barrier(2)
    results: list[Any] = []
    errors: list[BaseException] = []

    def _run() -> None:
        barrier.wait()
        try:
            results.append(
                adopt_existing_world(
                    raw,
                    adopted_at=NOW,
                    adoption_repository=adoptions,
                    graph_reader=graph_reader(),
                )
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(results) == 2
    assert results[0] == results[1]
    assert adoptions.get_for_world(WORLD_ID) == results[0]


def test_t20_different_bundle_concurrency_one_winner() -> None:
    graph, sources, contributions, identity, adoptions = make_stores()
    first = bundle_bytes()
    other = make_bundle(adoption_id="adopt:contender")
    other = other.model_copy(
        update={
            "source_provenance": other.source_provenance.model_copy(
                update={"producer_revision": "rev:contender"}
            )
        }
    )
    second = bundle_bytes(other)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def _run(raw: bytes) -> None:
        barrier.wait()
        try:
            adopt_existing_world(
                raw,
                adopted_at=NOW,
                adoption_repository=adoptions,
                graph_reader=graph_reader(),
            )
            outcomes.append("won")
        except IdempotencyConflictError:
            outcomes.append("refused")

    threads = [
        threading.Thread(target=_run, args=(first,)),
        threading.Thread(target=_run, args=(second,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["refused", "won"]
    receipt = adoptions.get_for_world(WORLD_ID)
    assert receipt is not None
    assert len(graph._revisions) == 1
    assert len(contributions.list_for_world(WORLD_ID)) == 2
    assert len(identity.list_for_world(WORLD_ID)) == 2
    assert sources.get_artifact(ART_A) is not None


@pytest.mark.parametrize(
    "family",
    ["graph", "contribution", "identity", "source"],
)
def test_t21_non_pristine_world_refuses(family: str) -> None:
    graph, sources, contributions, identity, adoptions = make_stores()
    if family == "graph":
        graph.publish_revision(
            PublishRevisionCommand(
                world_id=WORLD_ID,
                parent_revision_id=None,
                expected_parent_revision_id=None,
                operation_ids=["op:preseed"],
                graph_schema="dm_union_graph_v1",
                graph_payload={"world_id": WORLD_ID, "objects": [], "relationships": []},
                created_at=NOW,
            )
        )
    elif family == "contribution":
        contributions.append(_contribution("contrib:preseed", ART_A, REV_A))
    elif family == "identity":
        identity.append(
            _alias_decision("iddec:preseed", kind=IdentityDecisionKind.ALIAS_ADD, alias="Pre")
        )
    else:
        sources.put_artifact(_artifact(ART_A, REV_A))
    with pytest.raises(PersistenceIntegrityError, match="not pristine"):
        adopt_existing_world(
            bundle_bytes(),
            adopted_at=NOW,
            adoption_repository=adoptions,
            graph_reader=graph_reader(),
        )
    assert adoptions.get_for_world(WORLD_ID) is None


def test_in_memory_rollback_after_source_history() -> None:
    def hook(stage: str) -> None:
        if stage == "source_history":
            raise RuntimeError("injected source-history failure")

    graph, sources, contributions, identity, adoptions = make_stores(failure_hook=hook)
    with pytest.raises(ExistingWorldAdoptionOutcomeUnknownError):
        adopt_existing_world(
            bundle_bytes(),
            adopted_at=NOW,
            adoption_repository=adoptions,
            graph_reader=graph_reader(),
        )
    assert graph.get_head(WORLD_ID) is None
    assert sources.get_artifact(ART_A) is None
    assert contributions.list_for_world(WORLD_ID) == []
    assert identity.list_for_world(WORLD_ID) == []
    assert adoptions.get_for_world(WORLD_ID) is None


def test_direct_port_refuses_unbound_command_on_fresh_adopt() -> None:
    cases = (
        (make_command(bundle_sha256="ab" * 32), "unbound_bundle_sha256"),
        (make_command(graph_payload_sha256="cd" * 32), "unbound_graph_payload_sha256"),
        (
            make_command(expected_published_revision_id="rev:" + ("0" * 32)),
            "unbound_expected_published_revision_id",
        ),
    )
    for command, reason in cases:
        _, _, _, _, adoptions = make_stores()
        with pytest.raises(PersistenceIntegrityError) as exc:
            adoptions.adopt(command)
        assert exc.value.details["reason"] == reason
        assert adoptions.get_for_world(WORLD_ID) is None
        assert adoptions.get(WORLD_ID, ADOPTION_ID) is None


def test_direct_port_refuses_spoofed_bundle_sha_on_replay() -> None:
    _, _, _, _, adoptions = make_stores()
    first = adoptions.adopt(make_command())
    other = make_isolated_bundle(
        world_id=WORLD_ID,
        adoption_id="adopt:spoofed-bundle",
        token="spoof",
    )
    spoofed = make_command(other, bundle_sha256=first.bundle_sha256)
    with pytest.raises(PersistenceIntegrityError) as exc:
        adoptions.adopt(spoofed)
    assert exc.value.details["reason"] == "unbound_bundle_sha256"
    assert adoptions.get_for_world(WORLD_ID) == first


def test_direct_port_cross_world_adoption_id_conflicts() -> None:
    _, _, _, _, adoptions = make_stores()
    first = adoptions.adopt(make_command())
    other = make_isolated_bundle(
        world_id="world:existing-adoption-other",
        adoption_id=ADOPTION_ID,
        token="other",
    )
    with pytest.raises(IdempotencyConflictError, match="already exists for another world"):
        adoptions.adopt(make_command(other))
    assert adoptions.get_for_world(WORLD_ID) == first
    assert adoptions.get_for_world(other.world_id) is None


def test_t34_production_files_have_no_buddy_runtime() -> None:
    forbidden = ("DungeonMindBuddy", "graph_memory", "apps.", "/DungeonMindBuddy/")
    leased = [
        SRC / "application" / "existing_world_adoption.py",
        SRC / "contracts" / "existing_world_adoption.py",
        SRC / "infrastructure" / "postgres" / "existing_world_adoption.py",
        SRC / "infrastructure" / "memory" / "repositories.py",
    ]
    for path in leased:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("graph_memory")
                    assert not alias.name.startswith("apps")
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("graph_memory")
                assert not node.module.startswith("apps")


def test_t35_no_finalized_review_fabrication() -> None:
    text = (SRC / "application" / "existing_world_adoption.py").read_text(encoding="utf-8")
    assert "ContributionReviewState" not in text
    assert "materialize_finalized_review" not in text
    assert "CommitConfirmationReceipt" not in text
    postgres = (SRC / "infrastructure" / "postgres" / "existing_world_adoption.py").read_text(
        encoding="utf-8"
    )
    memory = (SRC / "infrastructure" / "memory" / "repositories.py").read_text(encoding="utf-8")
    assert "ContributionReviewState" not in postgres
    assert "compute_revision_id" not in postgres
    assert "bind_existing_world_adoption_command" in postgres
    assert "bind_existing_world_adoption_command" in memory
    assert "_append_contribution_in_transaction" in postgres
    assert "PostgresSourceRepository" not in postgres
    assert "PostgresContributionRepository" not in postgres
    assert "PostgresIdentityDecisionRepository" not in postgres
    assert ".put_artifact(" not in postgres
    assert ".put_revision(" not in postgres


def test_t36_no_transport_added() -> None:
    service_root = SRC / "service"
    if service_root.exists():
        for path in service_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "existing_world_adoption" not in text
            assert "adopt_existing_world" not in text


def test_t37_fixture_is_synthetic_not_eldyrwild() -> None:
    raw = bundle_bytes()
    assert b"eldyrwild" not in raw.lower()
    assert WORLD_ID == "world:existing-adoption-fixture"
    bundle = make_bundle()
    assert len(bundle.source_artifacts) >= 2
    assert len(bundle.contributions) >= 2
    assert any(
        decision.decision_kind is IdentityDecisionKind.ALIAS_ADD
        for decision in bundle.identity_decisions
    )
    payload = bundle.graph_payload
    assert any(
        rel.get("target_aspect_assertion_id") == "asrt:college-org"
        for rel in payload["relationships"]
    )
    assert any(
        rel.get("target_aspect_assertion_id") in (None,)
        or "target_aspect_assertion_id" not in rel
        or rel.get("relationship_id") == "rel:travels"
        for rel in payload["relationships"]
    )


BASELINE_V1_BUNDLE_SHA256 = "a98e3f833fd0cae43581f435a84916727f0a75dd7a27e6216b5e187b1b588f08"
BASELINE_V1_BUNDLE_LEN = 9079


def test_v1_canonical_bytes_unchanged_from_dispatch_base() -> None:
    raw = bundle_bytes()
    assert len(raw) == BASELINE_V1_BUNDLE_LEN
    assert sha256_bytes(raw) == BASELINE_V1_BUNDLE_SHA256
    parsed = parse_existing_world_adoption_bundle(raw, graph_reader=graph_reader())
    assert isinstance(parsed, ExistingWorldAdoptionBundleV1)
    assert "assertion_corrections" not in parsed.contributions[0].model_dump(mode="json")
    assert "merge_side_effects" not in parsed.identity_decisions[0].model_dump(mode="json")


def test_v2_canonical_bytes_are_order_independent() -> None:
    forward = make_v2_bundle()
    reversed_bundle = forward.model_copy(
        update={"contributions": list(reversed(forward.contributions))}
    )
    assert v2_bundle_bytes(forward) == v2_bundle_bytes(reversed_bundle)
    parsed = parse_existing_world_adoption_bundle(
        v2_bundle_bytes(forward), graph_reader=graph_reader()
    )
    assert parsed.schema_version == EXISTING_WORLD_ADOPTION_BUNDLE_V2_SCHEMA


def test_unknown_adoption_bundle_schema_fails_before_mutation() -> None:
    payload = json.loads(bundle_bytes())
    payload["schema_version"] = "dm_existing_world_adoption_bundle_v9"
    raw = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    spy = _SpyAdoption(make_stores()[4])
    with pytest.raises(PersistenceIntegrityError) as exc:
        adopt_existing_world(
            raw,
            adopted_at=NOW,
            adoption_repository=spy,
            graph_reader=graph_reader(),
        )
    assert exc.value.details["reason"] == "unsupported_adoption_bundle_schema"
    assert spy.adopt_calls == 0


def test_v2_correction_missing_target_contribution_refuses() -> None:
    bundle = make_v2_bundle()
    broken = bundle.contributions[1].assertion_corrections[0].model_copy(
        update={"target_contribution_id": "contrib:missing"}
    )
    corrector = bundle.contributions[1].model_copy(update={"assertion_corrections": [broken]})
    with pytest.raises(PersistenceIntegrityError) as exc:
        parse_existing_world_adoption_bundle(
            v2_bundle_bytes(
                bundle.model_copy(update={"contributions": [bundle.contributions[0], corrector]})
            ),
            graph_reader=graph_reader(),
        )
    assert exc.value.details["reason"] == "correction_target_contribution_missing"


def test_v2_correction_missing_target_assertion_refuses() -> None:
    bundle = make_v2_bundle()
    broken = bundle.contributions[1].assertion_corrections[0].model_copy(
        update={"target_assertion_id": "asrt:missing"}
    )
    corrector = bundle.contributions[1].model_copy(update={"assertion_corrections": [broken]})
    with pytest.raises(PersistenceIntegrityError) as exc:
        parse_existing_world_adoption_bundle(
            v2_bundle_bytes(
                bundle.model_copy(update={"contributions": [bundle.contributions[0], corrector]})
            ),
            graph_reader=graph_reader(),
        )
    assert exc.value.details["reason"] == "correction_target_assertion_missing"


def test_v2_correction_missing_replacement_assertion_refuses() -> None:
    bundle = make_v2_bundle()
    broken = bundle.contributions[1].assertion_corrections[1].model_copy(
        update={"replacement_assertion_id": "asrt:missing-replacement"}
    )
    corrections = [bundle.contributions[1].assertion_corrections[0], broken]
    corrector = bundle.contributions[1].model_copy(update={"assertion_corrections": corrections})
    with pytest.raises(PersistenceIntegrityError) as exc:
        parse_existing_world_adoption_bundle(
            v2_bundle_bytes(
                bundle.model_copy(update={"contributions": [bundle.contributions[0], corrector]})
            ),
            graph_reader=graph_reader(),
        )
    assert exc.value.details["reason"] == "correction_replacement_assertion_missing"


def test_v2_replacement_on_wrong_contribution_refuses() -> None:
    bundle = make_v2_bundle()
    broken = bundle.contributions[1].assertion_corrections[1].model_copy(
        update={"replacement_assertion_id": "asrt:contrib:target"}
    )
    corrections = [bundle.contributions[1].assertion_corrections[0], broken]
    corrector = bundle.contributions[1].model_copy(update={"assertion_corrections": corrections})
    with pytest.raises(PersistenceIntegrityError) as exc:
        parse_existing_world_adoption_bundle(
            v2_bundle_bytes(
                bundle.model_copy(update={"contributions": [bundle.contributions[0], corrector]})
            ),
            graph_reader=graph_reader(),
        )
    assert exc.value.details["reason"] == "correction_replacement_assertion_missing"


def test_memory_v2_history_and_adoption_round_trip() -> None:
    raw = v2_bundle_bytes()
    graph, _, contributions, identity, adoptions = make_stores()
    receipt = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    assert receipt.schema_version == EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA
    loaded_contrib = contributions.get(WORLD_ID, "contrib:corrector")
    assert isinstance(loaded_contrib, GraphContributionV2)
    assert loaded_contrib.model_dump(mode="json") == make_v2_bundle().contributions[1].model_dump(
        mode="json"
    )
    assert (
        loaded_contrib.assertions[1].epistemic_kind
        is ContributionEpistemicKind.SOURCE_DERIVED_CANDIDATE
    )
    loaded_merge = identity.get(WORLD_ID, "iddec:merge")
    assert isinstance(loaded_merge, IdentityDecisionRecordV2)
    assert loaded_merge.merge_side_effects == _merge_side_effects()
    replayed = adopt_existing_world(
        raw,
        adopted_at=LATER,
        adoption_repository=adoptions,
        graph_reader=_BoomReader(),  # type: ignore[arg-type]
    )
    assert replayed == receipt
    assert graph.get_head(WORLD_ID) is not None


def test_cross_version_replay_conflicts() -> None:
    _, _, _, _, adoptions = make_stores()
    v1_receipt = adopt_existing_world(
        bundle_bytes(),
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    with pytest.raises(IdempotencyConflictError) as exc:
        adopt_existing_world(
            v2_bundle_bytes(),
            adopted_at=LATER,
            adoption_repository=adoptions,
            graph_reader=graph_reader(),
        )
    assert exc.value.details["stored_receipt_schema"] == v1_receipt.schema_version
    other_graph, _, _, _, other_adoptions = make_stores()
    v2_receipt = adopt_existing_world(
        v2_bundle_bytes(),
        adopted_at=NOW,
        adoption_repository=other_adoptions,
        graph_reader=graph_reader(),
    )
    with pytest.raises(IdempotencyConflictError):
        adopt_existing_world(
            bundle_bytes(),
            adopted_at=LATER,
            adoption_repository=other_adoptions,
            graph_reader=graph_reader(),
        )
    assert v2_receipt.schema_version == EXISTING_WORLD_ADOPTION_RECEIPT_V3_SCHEMA
    assert other_graph.get_head(WORLD_ID) is not None


def test_merged_away_id_is_not_rejected_for_missing_graph_object() -> None:
    bundle = make_v2_bundle()
    parsed = parse_existing_world_adoption_bundle(
        v2_bundle_bytes(bundle), graph_reader=graph_reader()
    )
    merge = next(
        decision
        for decision in parsed.identity_decisions
        if decision.decision_kind is IdentityDecisionKind.MERGE
    )
    assert merge.merge_side_effects is not None
    assert merge.merge_side_effects.alias_map_rewrites[0].prior_owner_node_id == "obj:merged-away"
    object_ids = {item["object_id"] for item in parsed.graph_payload["objects"]}
    assert "obj:merged-away" not in object_ids


def test_memory_v2_record_repos_append_get_list() -> None:
    _, _, contributions, identity, _ = make_stores()
    target, contrib = make_v2_bundle().contributions
    decision = make_v2_bundle().identity_decisions[1]
    assert contributions.append(target) == target
    assert contributions.append(contrib) == contrib
    assert contributions.get(WORLD_ID, contrib.contribution_id) == contrib
    assert contributions.list_for_world(WORLD_ID) == [contrib, target]
    assert identity.append(decision) == decision
    assert identity.get(WORLD_ID, decision.decision_id) == decision
    assert identity.list_for_world(WORLD_ID) == [decision]


def test_memory_v2_append_rejects_dangling_correction_target() -> None:
    _, _, contributions, _, _ = make_stores()
    corrector = make_v2_bundle().contributions[1]
    with pytest.raises(PersistenceIntegrityError) as exc:
        contributions.append(corrector)
    assert exc.value.details["reason"] == "correction_target_contribution_missing"
    assert contributions.get(WORLD_ID, corrector.contribution_id) is None
    assert contributions.list_for_world(WORLD_ID) == []


def test_memory_v2_append_rejects_missing_target_assertion() -> None:
    _, _, contributions, _, _ = make_stores()
    target, corrector = make_v2_bundle().contributions
    contributions.append(target)
    broken = corrector.assertion_corrections[0].model_copy(
        update={"target_assertion_id": "asrt:missing"}
    )
    dangling = corrector.model_copy(update={"assertion_corrections": [broken]})
    with pytest.raises(PersistenceIntegrityError) as exc:
        contributions.append(dangling)
    assert exc.value.details["reason"] == "correction_target_assertion_missing"
    assert contributions.get(WORLD_ID, dangling.contribution_id) is None
    assert contributions.list_for_world(WORLD_ID) == [target]


def _bundle_membership_sha256(bundle: ExistingWorldAdoptionBundleV2) -> str:
    return existing_world_adoption_membership_sha256(
        source_artifacts=bundle.source_artifacts,
        source_revisions=bundle.source_revisions,
        contributions=bundle.contributions,
        identity_decisions=bundle.identity_decisions,
    )


def _parse_v2(raw: bytes) -> ExistingWorldAdoptionBundleV2:
    bundle = parse_existing_world_adoption_bundle(raw, graph_reader=graph_reader())
    assert isinstance(bundle, ExistingWorldAdoptionBundleV2)
    return bundle


def _correspondence(
    graph: InMemoryWorldGraphRepository,
    sources: InMemorySourceRepository,
    contributions: InMemoryContributionRepository,
    identity: InMemoryIdentityDecisionRepository,
    adoptions: InMemoryExistingWorldAdoptionRepository,
) -> ExistingWorldCorrespondenceService:
    return ExistingWorldCorrespondenceService(
        adoption_repository=adoptions,
        world_graph_repository=graph,
        contribution_repository=contributions,
        identity_repository=identity,
        source_repository=sources,
        graph_reader=graph_reader(),
    )


def _downgrade_receipt_to_v2(
    adoptions: InMemoryExistingWorldAdoptionRepository, world_id: str
) -> ExistingWorldAdoptionReceiptV2:
    """Simulate a pre-V3 durable receipt for promotion-path proofs."""
    stored = adoptions.get_for_world(world_id)
    assert isinstance(stored, ExistingWorldAdoptionReceiptV3)
    downgraded = ExistingWorldAdoptionReceiptV2(
        **{
            key: value
            for key, value in stored.model_dump().items()
            if key not in {"schema_version", "membership_sha256"}
        }
    )
    adoptions._receipts_by_world[world_id] = downgraded
    adoptions._receipts_by_adoption[downgraded.adoption_id] = downgraded
    return downgraded


def test_membership_digest_is_order_independent() -> None:
    bundle = make_v2_bundle()
    shuffled = bundle.model_copy(
        update={
            "source_artifacts": list(reversed(bundle.source_artifacts)),
            "source_revisions": list(reversed(bundle.source_revisions)),
            "contributions": list(reversed(bundle.contributions)),
            "identity_decisions": list(reversed(bundle.identity_decisions)),
        }
    )
    assert _bundle_membership_sha256(bundle) == _bundle_membership_sha256(shuffled)


def test_membership_digest_changes_with_record_id() -> None:
    bundle = make_v2_bundle()
    renamed = bundle.source_revisions[0].model_copy(
        update={"source_revision_id": "srcrev:renamed"}
    )
    changed = existing_world_adoption_membership_sha256(
        source_artifacts=bundle.source_artifacts,
        source_revisions=[renamed, *bundle.source_revisions[1:]],
        contributions=bundle.contributions,
        identity_decisions=bundle.identity_decisions,
    )
    assert changed != _bundle_membership_sha256(bundle)


def test_membership_digest_changes_with_record_payload() -> None:
    bundle = make_v2_bundle()
    mutated = bundle.source_revisions[0].model_copy(
        update={"content_sha256": "0" * 64}
    )
    changed = existing_world_adoption_membership_sha256(
        source_artifacts=bundle.source_artifacts,
        source_revisions=[mutated, *bundle.source_revisions[1:]],
        contributions=bundle.contributions,
        identity_decisions=bundle.identity_decisions,
    )
    assert changed != _bundle_membership_sha256(bundle)


def test_membership_digest_rejects_duplicate_record_ids() -> None:
    bundle = make_v2_bundle()
    with pytest.raises(PersistenceIntegrityError) as exc:
        existing_world_adoption_membership_sha256(
            source_artifacts=bundle.source_artifacts,
            source_revisions=[bundle.source_revisions[0], bundle.source_revisions[0]],
            contributions=bundle.contributions,
            identity_decisions=bundle.identity_decisions,
        )
    assert exc.value.details["reason"] == "membership_duplicate_record_id"
    assert exc.value.details["family"] == "source_revisions"


def test_membership_digest_is_domain_separated() -> None:
    bundle = make_v2_bundle()
    digest = _bundle_membership_sha256(bundle)
    pair = {
        "record_id": bundle.source_revisions[0].source_revision_id,
        "record_fingerprint": canonical_sha256(
            bundle.source_revisions[0].model_dump(mode="json")
        ),
    }
    other_schema = canonical_sha256(
        {
            "schema_version": "dm_existing_world_adoption_membership_v0",
            "source_artifacts": [],
            "source_revisions": [pair],
            "contributions": [],
            "identity_decisions": [],
        }
    )
    assert digest != other_schema
    moved_family = canonical_sha256(
        {
            "schema_version": EXISTING_WORLD_ADOPTION_MEMBERSHIP_SCHEMA,
            "source_artifacts": [pair],
            "source_revisions": [],
            "contributions": [],
            "identity_decisions": [],
        }
    )
    assert digest != moved_family


def test_v2_adoption_emits_v3_receipt_with_membership_checkpoint() -> None:
    raw = v2_bundle_bytes()
    _, _, _, _, adoptions = make_stores()
    receipt = adopt_existing_world(
        raw,
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    assert isinstance(receipt, ExistingWorldAdoptionReceiptV3)
    assert receipt.membership_sha256 == _bundle_membership_sha256(_parse_v2(raw))
    reloaded = adoptions.get_for_world(WORLD_ID)
    assert isinstance(reloaded, ExistingWorldAdoptionReceiptV3)
    assert reloaded == receipt


def test_promotion_upgrades_v2_receipt_to_v3_without_history_mutation() -> None:
    raw = v2_bundle_bytes()
    graph, sources, contributions, identity, adoptions = make_stores()
    adopt_existing_world(
        raw, adopted_at=NOW, adoption_repository=adoptions, graph_reader=graph_reader()
    )
    _downgrade_receipt_to_v2(adoptions, WORLD_ID)
    before = adoptions._snapshot_world(WORLD_ID)

    promoted = promote_existing_world_adoption_receipt_v3(
        raw,
        world_id=WORLD_ID,
        adoption_repository=adoptions,
        source_repository=sources,
        contribution_repository=contributions,
        identity_repository=identity,
        graph_reader=graph_reader(),
        correspondence_service=_correspondence(
            graph, sources, contributions, identity, adoptions
        ),
    )
    assert isinstance(promoted, ExistingWorldAdoptionReceiptV3)
    assert promoted.membership_sha256 == _bundle_membership_sha256(_parse_v2(raw))
    after = adoptions._snapshot_world(WORLD_ID)
    for family in (
        "artifacts",
        "revisions",
        "contributions",
        "identity",
        "revisions_graph",
        "head",
    ):
        assert after[family] == before[family]
    assert isinstance(after["receipt"], ExistingWorldAdoptionReceiptV3)


def test_promotion_replay_is_exact_noop() -> None:
    raw = v2_bundle_bytes()
    graph, sources, contributions, identity, adoptions = make_stores()
    original = adopt_existing_world(
        raw, adopted_at=NOW, adoption_repository=adoptions, graph_reader=graph_reader()
    )
    assert isinstance(original, ExistingWorldAdoptionReceiptV3)
    replayed = promote_existing_world_adoption_receipt_v3(
        raw,
        world_id=WORLD_ID,
        adoption_repository=adoptions,
        source_repository=sources,
        contribution_repository=contributions,
        identity_repository=identity,
        graph_reader=graph_reader(),
        correspondence_service=_correspondence(
            graph, sources, contributions, identity, adoptions
        ),
    )
    assert replayed == original


def test_promotion_rejects_identity_divergent_bundle() -> None:
    raw = v2_bundle_bytes()
    graph, sources, contributions, identity, adoptions = make_stores()
    adopt_existing_world(
        raw, adopted_at=NOW, adoption_repository=adoptions, graph_reader=graph_reader()
    )
    _downgrade_receipt_to_v2(adoptions, WORLD_ID)
    other = v2_bundle_bytes(make_v2_bundle(adoption_id="adopt:existing-fixture-other"))
    with pytest.raises(PersistenceIntegrityError) as exc:
        promote_existing_world_adoption_receipt_v3(
            other,
            world_id=WORLD_ID,
            adoption_repository=adoptions,
            source_repository=sources,
            contribution_repository=contributions,
            identity_repository=identity,
            graph_reader=graph_reader(),
            correspondence_service=_correspondence(
                graph, sources, contributions, identity, adoptions
            ),
        )
    assert exc.value.details["reason"] == "adoption_receipt_promotion_identity_mismatch"
    assert not isinstance(adoptions.get_for_world(WORLD_ID), ExistingWorldAdoptionReceiptV3)


def test_promotion_fails_after_same_cardinality_substitution() -> None:
    raw = v2_bundle_bytes()
    graph, sources, contributions, identity, adoptions = make_stores()
    adopt_existing_world(
        raw, adopted_at=NOW, adoption_repository=adoptions, graph_reader=graph_reader()
    )
    _downgrade_receipt_to_v2(adoptions, WORLD_ID)
    bundle = _parse_v2(raw)
    removed = bundle.source_revisions[0]
    sources._revisions.pop(removed.source_revision_id)
    substitute = removed.model_copy(
        update={"source_revision_id": "srcrev:substitute-after-adoption"}
    )
    sources._revisions[substitute.source_revision_id] = substitute
    with pytest.raises(PersistenceIntegrityError) as exc:
        promote_existing_world_adoption_receipt_v3(
            raw,
            world_id=WORLD_ID,
            adoption_repository=adoptions,
            source_repository=sources,
            contribution_repository=contributions,
            identity_repository=identity,
            graph_reader=graph_reader(),
            correspondence_service=_correspondence(
                graph, sources, contributions, identity, adoptions
            ),
        )
    assert exc.value.details["reason"] == "adoption_promotion_membership_mismatch"
    assert not isinstance(adoptions.get_for_world(WORLD_ID), ExistingWorldAdoptionReceiptV3)


class _GapCommitAdoptions:
    """Pause at the repository boundary and commit a valid history mutation
    in the gap before delegating — the review cycle 1 exit-proof shape."""

    def __init__(
        self,
        inner: InMemoryExistingWorldAdoptionRepository,
        identity: InMemoryIdentityDecisionRepository,
    ) -> None:
        self._inner = inner
        self._identity = identity

    def adopt(self, command):
        return self._inner.adopt(command)

    def get(self, world_id: str, adoption_id: str):
        return self._inner.get(world_id, adoption_id)

    def get_for_world(self, world_id: str):
        return self._inner.get_for_world(world_id)

    def promote_to_v3_receipt(
        self, world_id: str, *, expected, promoted, current_membership_sha256
    ):
        gap_decision = (
            _parse_v2(v2_bundle_bytes())
            .identity_decisions[0]
            .model_copy(update={"decision_id": "decision:committed-in-promotion-gap"})
        )
        self._identity.append(gap_decision)
        return self._inner.promote_to_v3_receipt(
            world_id,
            expected=expected,
            promoted=promoted,
            current_membership_sha256=current_membership_sha256,
        )


def test_promotion_fails_when_history_commits_in_the_gap() -> None:
    """Pause after the application's pre-boundary membership proof, commit a
    valid history mutation, resume: the in-boundary re-proof must fail the
    promotion with the receipt still V2."""
    raw = v2_bundle_bytes()
    graph, sources, contributions, identity, adoptions = make_stores()
    adopt_existing_world(
        raw, adopted_at=NOW, adoption_repository=adoptions, graph_reader=graph_reader()
    )
    _downgrade_receipt_to_v2(adoptions, WORLD_ID)
    gap_adoptions = _GapCommitAdoptions(adoptions, identity)
    decisions_before = len(identity.list_for_world(WORLD_ID))
    with pytest.raises(PersistenceIntegrityError) as exc:
        promote_existing_world_adoption_receipt_v3(
            raw,
            world_id=WORLD_ID,
            adoption_repository=gap_adoptions,
            source_repository=sources,
            contribution_repository=contributions,
            identity_repository=identity,
            graph_reader=graph_reader(),
            correspondence_service=_correspondence(
                graph, sources, contributions, identity, adoptions
            ),
        )
    assert exc.value.details["reason"] == "adoption_promotion_membership_mismatch"
    assert isinstance(adoptions.get_for_world(WORLD_ID), ExistingWorldAdoptionReceiptV2)
    # The gap commit is a valid independent write and remains; promotion
    # itself mutated nothing.
    assert len(identity.list_for_world(WORLD_ID)) == decisions_before + 1


def test_promotion_port_reproofs_membership_under_the_lock() -> None:
    """Direct port contract: the provider is re-invoked inside the boundary,
    so a mutation visible at enumeration time fails the swap with zero
    receipt mutation."""
    raw = v2_bundle_bytes()
    _graph, sources, contributions, identity, adoptions = make_stores()
    adopt_existing_world(
        raw, adopted_at=NOW, adoption_repository=adoptions, graph_reader=graph_reader()
    )
    expected = _downgrade_receipt_to_v2(adoptions, WORLD_ID)
    bundle = _parse_v2(raw)
    promoted = ExistingWorldAdoptionReceiptV3(
        **{
            key: value
            for key, value in expected.model_dump().items()
            if key != "schema_version"
        },
        membership_sha256=_bundle_membership_sha256(bundle),
    )

    def mutating_provider() -> str:
        identity.append(
            bundle.identity_decisions[0].model_copy(
                update={"decision_id": "decision:committed-inside-boundary"}
            )
        )
        artifacts = sources.list_artifacts_for_world(WORLD_ID)
        return existing_world_adoption_membership_sha256(
            source_artifacts=artifacts,
            source_revisions=[
                revision
                for artifact in artifacts
                for revision in sources.list_revisions(artifact.source_artifact_id)
            ],
            contributions=contributions.list_for_world(WORLD_ID),
            identity_decisions=identity.list_for_world(WORLD_ID),
        )

    with pytest.raises(PersistenceIntegrityError) as exc:
        adoptions.promote_to_v3_receipt(
            WORLD_ID,
            expected=expected,
            promoted=promoted,
            current_membership_sha256=mutating_provider,
        )
    assert exc.value.details["reason"] == "adoption_promotion_membership_mismatch"
    assert isinstance(adoptions.get_for_world(WORLD_ID), ExistingWorldAdoptionReceiptV2)


def test_promotion_requires_an_existing_receipt() -> None:
    raw = v2_bundle_bytes()
    graph, sources, contributions, identity, adoptions = make_stores()
    with pytest.raises(PersistenceIntegrityError) as exc:
        promote_existing_world_adoption_receipt_v3(
            raw,
            world_id=WORLD_ID,
            adoption_repository=adoptions,
            source_repository=sources,
            contribution_repository=contributions,
            identity_repository=identity,
            graph_reader=graph_reader(),
            correspondence_service=_correspondence(
                graph, sources, contributions, identity, adoptions
            ),
        )
    assert exc.value.details["reason"] == "adoption_receipt_missing"


def test_promotion_rejects_v1_bundle() -> None:
    graph, sources, contributions, identity, adoptions = make_stores()
    adopt_existing_world(
        bundle_bytes(),
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    with pytest.raises(PersistenceIntegrityError) as exc:
        promote_existing_world_adoption_receipt_v3(
            bundle_bytes(),
            world_id=WORLD_ID,
            adoption_repository=adoptions,
            source_repository=sources,
            contribution_repository=contributions,
            identity_repository=identity,
            graph_reader=graph_reader(),
            correspondence_service=_correspondence(
                graph, sources, contributions, identity, adoptions
            ),
        )
    assert exc.value.details["reason"] == "adoption_promotion_bundle_schema_unsupported"


def test_promotion_rejects_v1_receipt() -> None:
    graph, sources, contributions, identity, adoptions = make_stores()
    adopt_existing_world(
        bundle_bytes(),
        adopted_at=NOW,
        adoption_repository=adoptions,
        graph_reader=graph_reader(),
    )
    with pytest.raises(PersistenceIntegrityError) as exc:
        promote_existing_world_adoption_receipt_v3(
            v2_bundle_bytes(),
            world_id=WORLD_ID,
            adoption_repository=adoptions,
            source_repository=sources,
            contribution_repository=contributions,
            identity_repository=identity,
            graph_reader=graph_reader(),
            correspondence_service=_correspondence(
                graph, sources, contributions, identity, adoptions
            ),
        )
    assert exc.value.details["reason"] == "adoption_receipt_promotion_unsupported_schema"
