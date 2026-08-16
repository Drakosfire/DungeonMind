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
    ExistingWorldAdoptionAuthorityRefV1,
    ExistingWorldAdoptionBundleV1,
    ExistingWorldAdoptionSourceProvenanceV1,
    existing_world_adoption_bundle_canonical_bytes,
    sha256_bytes,
)
from dungeonmind.contracts.graph import PublishRevisionCommand
from dungeonmind.contracts.identity import (
    IdentityDecisionKind,
    IdentityDecisionRecord,
    IdentityDecisionStatus,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import (
    ExistingWorldAdoptionOutcomeUnknownError,
    IdempotencyConflictError,
    PersistenceIntegrityError,
    PersistenceUnavailableError,
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


def _artifact(source_artifact_id: str, revision_id: str) -> SourceArtifactV2:
    return SourceArtifactV2(
        source_artifact_id=source_artifact_id,
        source_domain_key="producer.worldbuilding",
        source_domain=SourceDomain.WORLDBUILDING,
        world_id=WORLD_ID,
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


def _contribution(contribution_id: str, artifact_id: str, revision_id: str) -> GraphContribution:
    return GraphContribution(
        contribution_id=contribution_id,
        world_id=WORLD_ID,
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
    decision_id: str, *, kind: IdentityDecisionKind, alias: str
) -> IdentityDecisionRecord:
    return IdentityDecisionRecord(
        decision_id=decision_id,
        world_id=WORLD_ID,
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
    assert "ContributionReviewState" not in postgres
    assert "compute_revision_id" not in postgres
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
