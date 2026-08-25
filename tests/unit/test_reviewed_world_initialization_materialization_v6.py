"""Pure first-world v6 materialization proofs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dungeonmind.application.graph_snapshot import (
    GRAPH_SCHEMA_V6,
    RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA,
    VersionedUnionGraphSnapshotReader,
)
from dungeonmind.application.reviewed_world_initialization import (
    materialize_reviewed_world_initialization_v6,
    reviewed_world_initialization_command_sha256,
)
from dungeonmind.application.semantic_profiles import descriptor_sha256
from dungeonmind.contracts.contribution import (
    AcceptanceState,
    ContributionSourceKind,
    GraphContributionAssertionCorrection,
    GraphContributionAssertionCorrectionKind,
    GraphContributionAssertionV2,
    GraphContributionV2,
)
from dungeonmind.contracts.evidence import (
    EvidenceRef,
    EvidenceRole,
    SourceArtifactV2,
    SourceAuthority,
    SourceDomain,
    SourceRevision,
    SourceStatus,
)
from dungeonmind.contracts.identity import IdentityOutcome
from dungeonmind.contracts.reviewed_world_initialization import (
    ReviewedWorldInitializationCommandV1,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor, SemanticProfileRef
from dungeonmind.contracts.vocabulary import Visibility
from dungeonmind.domain.errors import (
    ContributionMaterializationError,
    PersistenceIntegrityError,
)
from dungeonmind.infrastructure.semantic_profiles import StaticSemanticProfileRegistry

WORLD_ID = "world:reviewed-init-fixture"
CAMPAIGN_ID = "camp:reviewed-init-fixture"
INIT_ID = "init:reviewed-fixture-v1"
NOW = datetime(2026, 8, 25, 18, 0, tzinfo=UTC)
ART = "src:notes-a"
REV = "srcrev:notes-a-v1"
BODY = "a" * 64
DESCRIPTOR_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "semantic_profiles" / "test-kernel-v1.json"
)


def _descriptor() -> SemanticProfileDescriptor:
    return SemanticProfileDescriptor.model_validate(
        json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    )


def graph_reader() -> VersionedUnionGraphSnapshotReader:
    return VersionedUnionGraphSnapshotReader(
        profile_registry=StaticSemanticProfileRegistry([_descriptor()])
    )


def _profile_ref() -> dict[str, Any]:
    descriptor = _descriptor()
    return {
        "schema_version": "dm_semantic_profile_ref_v1",
        "profile_id": descriptor.profile_id,
        "profile_revision": descriptor.profile_revision,
        "descriptor_sha256": descriptor_sha256(descriptor),
    }


def _artifact(*, world_id: str = WORLD_ID) -> SourceArtifactV2:
    return SourceArtifactV2(
        source_artifact_id=ART,
        source_domain_key="producer.worldbuilding",
        source_domain=SourceDomain.WORLDBUILDING,
        world_id=world_id,
        campaign_id=None,
        session_id=None,
        uri=None,
        current_revision_id=REV,
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


def _revision() -> SourceRevision:
    return SourceRevision(
        source_revision_id=REV,
        source_artifact_id=ART,
        content_sha256=BODY,
        body_storage="object_store",
        locator=f"object://{REV}",
        created_at=NOW,
    )


def _node(
    *,
    assertion_id: str = "asrt:college",
    object_id: str = "obj:college",
    kind: str = "test:location",
    label: str = "Wizard College",
    acceptance: AcceptanceState = AcceptanceState.ACCEPTED,
    identity: IdentityOutcome | None = IdentityOutcome.CREATED_NEW,
) -> GraphContributionAssertionV2:
    return GraphContributionAssertionV2(
        assertion_id=assertion_id,
        assertion_kind="node",
        subject_object_id=object_id,
        label=label,
        value=json.dumps({"dm_kind": kind, "label": label, "aliases": [label]}),
        source_artifact_id=ART,
        source_revision_id=REV,
        campaign_scope=CAMPAIGN_ID,
        acceptance_state=acceptance,
        identity_resolution_outcome=identity,
    )


def _edge(
    *,
    assertion_id: str = "asrt:leads",
    subject: str = "obj:headmaster",
    target: str = "obj:college",
    edge_id: str = "rel:leads",
    predicate: str = "leads",
    dm_predicate: str = "test:leads",
    acceptance: AcceptanceState = AcceptanceState.ACCEPTED,
) -> GraphContributionAssertionV2:
    return GraphContributionAssertionV2(
        assertion_id=assertion_id,
        assertion_kind="edge",
        subject_object_id=subject,
        object_object_id=target,
        predicate=predicate,
        value=json.dumps({"dm_predicate": dm_predicate, "edge_id": edge_id}),
        source_artifact_id=ART,
        source_revision_id=REV,
        campaign_scope=CAMPAIGN_ID,
        acceptance_state=acceptance,
        identity_resolution_outcome=IdentityOutcome.CREATED_NEW,
    )


def _contribution(
    assertions: list[GraphContributionAssertionV2] | None = None,
    *,
    world_id: str = WORLD_ID,
    identity_decision_ids: list[str] | None = None,
    corrections: list[GraphContributionAssertionCorrection] | None = None,
) -> GraphContributionV2:
    resolved_assertions = (
        assertions
        if assertions is not None
        else [
            _node(),
            _node(
                assertion_id="asrt:headmaster",
                object_id="obj:headmaster",
                kind="test:person",
                label="Headmaster",
            ),
            _edge(),
        ]
    )
    return GraphContributionV2(
        contribution_id="contrib:reviewed-init-1",
        world_id=world_id,
        source_kind=ContributionSourceKind.GRAPH_REVIEW,
        source_artifact_id=ART,
        source_revision_id=REV,
        produced_at=NOW,
        campaign_scope=CAMPAIGN_ID,
        assertions=resolved_assertions,
        identity_decision_ids=identity_decision_ids or [],
        assertion_corrections=corrections or [],
    )


def make_command(
    *,
    initialization_id: str = INIT_ID,
    world_id: str = WORLD_ID,
    contribution: GraphContributionV2 | None = None,
    artifacts: list[SourceArtifactV2] | None = None,
    revisions: list[SourceRevision] | None = None,
    actor: str = "gm:reviewed-init",
) -> ReviewedWorldInitializationCommandV1:
    descriptor = _descriptor()
    return ReviewedWorldInitializationCommandV1(
        initialization_id=initialization_id,
        world_id=world_id,
        campaign_id=CAMPAIGN_ID,
        source_plan_schema="dmb_reviewed_world_initialization_plan_v1",
        source_plan_id="plan:reviewed-init-1",
        source_plan_sha256="ab" * 32,
        semantic_profile=SemanticProfileRef(
            profile_id=descriptor.profile_id,
            profile_revision=descriptor.profile_revision,
            descriptor_sha256=descriptor_sha256(descriptor),
        ),
        source_artifacts=artifacts or [_artifact(world_id=world_id)],
        source_revisions=revisions or [_revision()],
        reviewed_contribution=contribution or _contribution(world_id=world_id),
        actor=actor,
        requested_initialized_at=NOW,
    )


def test_command_digest_is_deterministic() -> None:
    first = reviewed_world_initialization_command_sha256(make_command())
    second = reviewed_world_initialization_command_sha256(make_command())
    assert first == second
    assert len(first) == 64
    other = reviewed_world_initialization_command_sha256(
        make_command(actor="gm:other-reviewer")
    )
    assert other != first


def test_empty_and_zero_accepted_refused() -> None:
    empty = make_command(contribution=_contribution(assertions=[]))
    with pytest.raises(PersistenceIntegrityError) as exc:
        materialize_reviewed_world_initialization_v6(empty, graph_reader=graph_reader())
    assert exc.value.details["reason"] == "no_accepted_materializable_assertion"

    rejected_only = make_command(
        contribution=_contribution(
            assertions=[_node(acceptance=AcceptanceState.REJECTED)]
        )
    )
    with pytest.raises(PersistenceIntegrityError) as exc:
        materialize_reviewed_world_initialization_v6(
            rejected_only, graph_reader=graph_reader()
        )
    assert exc.value.details["reason"] == "no_accepted_materializable_assertion"


def test_world_and_source_mismatch_refused() -> None:
    mismatched_artifact = make_command(artifacts=[_artifact(world_id="world:other")])
    with pytest.raises(PersistenceIntegrityError) as exc:
        materialize_reviewed_world_initialization_v6(
            mismatched_artifact, graph_reader=graph_reader()
        )
    assert exc.value.details["reason"] == "world_id_drift"

    contribution = _contribution(world_id="world:other")
    mismatched_contribution = make_command(contribution=contribution)
    with pytest.raises(PersistenceIntegrityError) as exc:
        materialize_reviewed_world_initialization_v6(
            mismatched_contribution, graph_reader=graph_reader()
        )
    assert exc.value.details["reason"] == "world_id_drift"


def test_unresolved_source_revision_ownership_refused() -> None:
    orphan = SourceRevision(
        source_revision_id="srcrev:orphan",
        source_artifact_id="src:missing",
        content_sha256=BODY,
        body_storage="object_store",
        locator="object://orphan",
        created_at=NOW,
    )
    command = make_command(revisions=[_revision(), orphan])
    with pytest.raises(PersistenceIntegrityError) as exc:
        materialize_reviewed_world_initialization_v6(command, graph_reader=graph_reader())
    assert exc.value.details["reason"] == "revision_artifact_missing"


def test_accepted_resolved_existing_refused() -> None:
    command = make_command(
        contribution=_contribution(
            assertions=[_node(identity=IdentityOutcome.RESOLVED_EXISTING)]
        )
    )
    with pytest.raises(PersistenceIntegrityError) as exc:
        materialize_reviewed_world_initialization_v6(command, graph_reader=graph_reader())
    assert exc.value.details["reason"] == "accepted_resolved_existing"


@pytest.mark.parametrize(
    "outcome",
    [
        None,
        IdentityOutcome.AMBIGUOUS,
        IdentityOutcome.BLOCKED_COLLISION,
        IdentityOutcome.REJECTED,
        IdentityOutcome.PROVISIONAL_NEW,
        IdentityOutcome.HUMAN_OVERRIDE,
    ],
)
def test_accepted_non_create_new_identity_fails_closed(
    outcome: IdentityOutcome | None,
) -> None:
    command = make_command(
        contribution=_contribution(
            assertions=[
                _node(identity=IdentityOutcome.CREATED_NEW),
                _node(
                    assertion_id="asrt:ambiguous-college",
                    object_id="obj:ambiguous",
                    kind="test:location",
                    label="Ambiguous Hall",
                    identity=outcome,
                ),
            ]
        )
    )
    with pytest.raises(PersistenceIntegrityError) as exc:
        materialize_reviewed_world_initialization_v6(command, graph_reader=graph_reader())
    assert exc.value.details["reason"] == "accepted_identity_not_create_new"


def test_revision_only_assertion_derives_artifact_from_revision_owner() -> None:
    revision_only = _node().model_copy(update={"source_artifact_id": None})
    headmaster = _node(
        assertion_id="asrt:headmaster",
        object_id="obj:headmaster",
        kind="test:person",
        label="Headmaster",
    ).model_copy(update={"source_artifact_id": None})
    command = make_command(
        contribution=_contribution(assertions=[revision_only, headmaster, _edge()])
    )
    result = materialize_reviewed_world_initialization_v6(
        command, graph_reader=graph_reader()
    )
    evidence = result.graph_payload["evidence_refs"]
    assert evidence
    for record in evidence:
        assert record["source_artifact_id"] == ART
        assert record["source_revision_id"] == REV
        assert record["source_artifact_id"] != (
            f"artifact:{command.reviewed_contribution.contribution_id}"
        )


def test_unreferenced_source_artifact_is_refused() -> None:
    extra = _artifact().model_copy(
        update={
            "source_artifact_id": "src:unused",
            "current_revision_id": None,
        }
    )
    command = make_command(artifacts=[_artifact(), extra])
    with pytest.raises(PersistenceIntegrityError) as exc:
        materialize_reviewed_world_initialization_v6(command, graph_reader=graph_reader())
    assert exc.value.details["reason"] == "unreferenced_source_artifact"


def test_unreferenced_source_revision_is_refused() -> None:
    extra = SourceRevision(
        source_revision_id="srcrev:unused",
        source_artifact_id=ART,
        content_sha256="c" * 64,
        body_storage="object_store",
        locator="object://unused",
        created_at=NOW,
    )
    command = make_command(revisions=[_revision(), extra])
    with pytest.raises(PersistenceIntegrityError) as exc:
        materialize_reviewed_world_initialization_v6(command, graph_reader=graph_reader())
    assert exc.value.details["reason"] == "unreferenced_source_revision"


def test_corrections_refused() -> None:
    command = make_command(
        contribution=_contribution(
            corrections=[
                GraphContributionAssertionCorrection(
                    correction_kind=GraphContributionAssertionCorrectionKind.CONTRADICTS,
                    target_contribution_id="contrib:prior",
                    target_assertion_id="asrt:prior",
                )
            ]
        )
    )
    with pytest.raises(PersistenceIntegrityError) as exc:
        materialize_reviewed_world_initialization_v6(command, graph_reader=graph_reader())
    assert exc.value.details["reason"] == "assertion_corrections_not_empty"


def test_accepted_edge_missing_endpoint_refused() -> None:
    command = make_command(
        contribution=_contribution(assertions=[_node(), _edge()])
    )
    with pytest.raises(PersistenceIntegrityError) as exc:
        materialize_reviewed_world_initialization_v6(command, graph_reader=graph_reader())
    assert exc.value.details["reason"] == "accepted_edge_missing_endpoint"


def test_valid_node_and_edge_materializes_strict_v6_and_reparses() -> None:
    command = make_command()
    result = materialize_reviewed_world_initialization_v6(
        command, graph_reader=graph_reader()
    )
    assert result.graph_schema == GRAPH_SCHEMA_V6
    assert result.world_id == WORLD_ID
    payload = result.graph_payload
    assert payload["world_id"] == WORLD_ID
    assert payload["semantic_profile"] == _profile_ref()
    assert payload["relationship_endpoint_aspect_schema"] == (
        RELATIONSHIP_ENDPOINT_ASPECT_SCHEMA
    )
    object_ids = {item["object_id"] for item in payload["objects"]}
    assert object_ids == {"obj:college", "obj:headmaster"}
    assert payload["objects"][0]["kind"].startswith("test:")
    rels = payload["relationships"]
    assert len(rels) == 1
    assert rels[0]["relationship_id"] == "rel:leads"
    assert rels[0]["predicate"] == "test:leads"
    snapshot = graph_reader().parse(
        graph_schema=GRAPH_SCHEMA_V6, graph_payload=payload
    )
    assert snapshot.world_id == WORLD_ID
    assert snapshot.graph_schema == GRAPH_SCHEMA_V6
    assert "obj:college" in snapshot.objects
    assert "rel:leads" in snapshot.relationships
    assert result.accepted_assertion_ids == (
        "asrt:college",
        "asrt:headmaster",
        "asrt:leads",
    )
    for record in payload["evidence_refs"]:
        assert record["source_artifact_id"] == ART
        assert record["source_revision_id"] == REV


def test_output_is_not_taken_from_command_bytes() -> None:
    command = make_command()
    dumped = command.model_dump(mode="json")
    assert "graph_payload" not in dumped
    result = materialize_reviewed_world_initialization_v6(
        command, graph_reader=graph_reader()
    )
    assert result.graph_payload not in (dumped, command.model_dump(mode="json"))
    assert result.graph_payload["objects"]
    command.reviewed_contribution.assertions[0].label = "mutated-after-bind"
    assert result.graph_payload["objects"][0]["label"] == "Wizard College"


def test_rejected_history_does_not_materialize() -> None:
    extra = GraphContributionAssertionV2(
        assertion_id="asrt:rejected-alias",
        assertion_kind="alias",
        subject_object_id="obj:college",
        label="Old College",
        source_artifact_id=ART,
        source_revision_id=REV,
        campaign_scope=CAMPAIGN_ID,
        acceptance_state=AcceptanceState.REJECTED,
    )
    command = make_command(
        contribution=_contribution(
            assertions=[
                _node(),
                _node(
                    assertion_id="asrt:headmaster",
                    object_id="obj:headmaster",
                    kind="test:person",
                    label="Headmaster",
                ),
                _edge(),
                extra,
            ]
        )
    )
    result = materialize_reviewed_world_initialization_v6(
        command, graph_reader=graph_reader()
    )
    aliases = [
        alias["value"]
        for obj in result.graph_payload["objects"]
        for alias in obj["aliases"]
    ]
    assert "Old College" not in aliases


def test_mechanics_binding_is_rejected() -> None:
    command = make_command(
        contribution=_contribution(
            assertions=[
                _node(),
                _node(
                    assertion_id="asrt:headmaster",
                    object_id="obj:headmaster",
                    kind="test:person",
                    label="Headmaster",
                ),
                _edge(dm_predicate="test:uses_statblock"),
            ]
        )
    )
    with pytest.raises(ContributionMaterializationError) as exc:
        materialize_reviewed_world_initialization_v6(command, graph_reader=graph_reader())
    assert exc.value.details["reason"] == "unsupported_assertion_kind"


def test_explicit_evidence_ref_is_lifted() -> None:
    node = _node()
    node = node.model_copy(
        update={
            "evidence_refs": [
                EvidenceRef(
                    evidence_ref_id="ev:college",
                    source_artifact_id=ART,
                    source_revision_id=REV,
                    source_domain=SourceDomain.WORLDBUILDING,
                    evidence_role=EvidenceRole.SUPPORT,
                )
            ]
        }
    )
    command = make_command(contribution=_contribution(assertions=[node]))
    result = materialize_reviewed_world_initialization_v6(
        command, graph_reader=graph_reader()
    )
    evidence_ids = {item["evidence_ref_id"] for item in result.graph_payload["evidence_refs"]}
    assert "ev:college" in evidence_ids
