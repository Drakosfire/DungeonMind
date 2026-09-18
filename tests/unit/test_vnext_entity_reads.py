"""Acceptance matrix for V3 exact / complete entity reads (HANDOFF §11)."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from dungeonmind.application.vnext.admission import (
    AlwaysAdmitPolicy,
    ClaimModeFilterPolicy,
    ExcludeByAssertionIdPolicy,
)
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.entity_reads import EntityReadCompleteness, EntityReadService
from dungeonmind.application.vnext.errors import (
    CandidateAdmissionIntegrityError,
    EntityReadIntegrityError,
)
from dungeonmind.application.vnext.frozen_json import FrozenDict
from dungeonmind.application.vnext.model import ParsedKnowledgeRevision
from dungeonmind.application.vnext.provenance import InMemoryKnowledgeSourceReader
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.application.vnext.records import ParsedEntityRefValue
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
    EpistemicBasis,
    KnowledgeStanding,
    PublicVisibility,
    ScopeBinding,
    ScopeSelector,
    TimelessTemporalScope,
)
from dungeonmind.contracts.vnext.domain import (
    Assertion,
    AssertionMetadata,
    DomainContractDescriptor,
    DomainContractRef,
    Entity,
    EntityRefValue,
    LiteralValue,
    SemanticProfileDescriptorV2,
    SemanticProfilePredicate,
)
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.contracts.vnext.projection import FocusRef, ProjectionRequest
from dungeonmind.contracts.vnext.source import EvidenceRefV3, SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256
from tests.unit.test_vnext_knowledge_read_context import (
    BUDDY_CONTRACT_DIGEST,
    BUDDY_PROFILE_DIGEST,
    CANONICAL_V0_AGGREGATE,
    ORG_CONTRACT_DIGEST,
    ORG_PROFILE_DIGEST,
    REPO_ROOT,
    VNEXT_SRC,
    _buddy_context,
    _buddy_domain_contract,
    _buddy_request,
    _buddy_semantic_profile,
    _build_from_fixture,
    _load_fixture,
    _org_domain_contract,
    _org_semantic_profile,
    _refresh_org_context,
)

STEWARD_PATH = REPO_ROOT / "Docs" / "Handoffs" / "HANDOFF-STEWARDSHIP-vnext-roadmap.md"
V3_HANDOFF_PATH = REPO_ROOT / "Docs" / "Handoffs" / "HANDOFF-v3-lazy-exact-complete-entity-reads.md"
V2_BENCH_PATH = REPO_ROOT / "Docs" / "Benchmarks" / "vnext_candidate_admission_10k_v1.json"
ENTITY_BENCH_PATH = REPO_ROOT / "Docs" / "Benchmarks" / "vnext_entity_reads_10k_v1.json"

V2_MERGE_SHA = "8af28bf359fa2044dbda23e674653edc9ebe3e6d"
V2_ACCEPTED_HEAD = "121419e9d0823533306d6a9ca6586c769d82f6b0"
V2_FINAL_REVIEW = "5217813591"
ACTIVATION_MAIN_SHA = "d409a2000e4608208cb8cfeed0c6907f3568abe2"

_SVC = EntityReadService()


def _lab_contract() -> DomainContractDescriptor:
    return DomainContractDescriptor(
        domain_id="test.entity-reads",
        domain_revision="1",
        scope_axes=["test:scope"],
        visibility_labels=["test:audience"],
        claim_modes=["test:fact"],
        admission_policy_id="test.always",
    )


def _lab_profile() -> SemanticProfileDescriptorV2:
    return SemanticProfileDescriptorV2(
        profile_id="test.entity-reads.profile",
        profile_revision="1",
        term_namespaces=["test"],
        predicates=[
            SemanticProfilePredicate(term="test:relates", allowed_value_kinds=["entity_ref"]),
            SemanticProfilePredicate(term="test:title", allowed_value_kinds=["literal"]),
        ],
    )


def _lab_context(
    *,
    entities: list[Entity],
    assertions: list[Assertion],
    evidence: list[EvidenceRefV3],
    artifacts: dict[str, SourceArtifactV3] | None = None,
    revisions: dict[str, SourceRevisionV2] | None = None,
    request: ProjectionRequest | None = None,
    policy: AlwaysAdmitPolicy | ExcludeByAssertionIdPolicy | ClaimModeFilterPolicy | None = None,
    space_id: str = "space:lab",
    revision_id: str = "rev:lab",
) -> tuple[KnowledgeReadContext, InMemoryKnowledgeSourceReader]:
    domain_contract = _lab_contract()
    semantic_profile = _lab_profile()
    contract_digest = canonical_sha256(domain_contract.model_dump(mode="json"))
    profile_digest = canonical_sha256(semantic_profile.model_dump(mode="json"))
    if artifacts is None:
        artifacts = {
            "src:lab": SourceArtifactV3(
                source_artifact_id="src:lab",
                source_classification="test:doc",
                current_revision_id="srcrev:lab",
                authority="primary",
                visibility=PublicVisibility(),
                status="active",
            )
        }
    if revisions is None:
        revisions = {
            "srcrev:lab": SourceRevisionV2(
                source_revision_id="srcrev:lab",
                source_artifact_id="src:lab",
                content_sha256="c" * 64,
                body_storage="inline",
                created_at=datetime(2026, 9, 15, tzinfo=UTC),
            )
        }
    revision = KnowledgeRevision(
        space_id=space_id,
        revision_id=revision_id,
        created_at=datetime(2026, 9, 15, tzinfo=UTC),
        operation_ids=["op:lab"],
        graph_schema="dm_vnext_graph_v1",
        graph_payload_sha256="0" * 64,
        domain_contract_ref=DomainContractRef(
            domain_id=domain_contract.domain_id,
            domain_revision=domain_contract.domain_revision,
            descriptor_sha256=contract_digest,
        ),
        semantic_profile_ref=SemanticProfileRef(
            profile_id=semantic_profile.profile_id,
            profile_revision=semantic_profile.profile_revision,
            descriptor_sha256=profile_digest,
        ),
    )
    parsed = build_parsed_knowledge_revision(
        revision=revision,
        entities=entities,
        assertions=assertions,
        evidence=evidence,
    )
    reader = InMemoryKnowledgeSourceReader(artifacts=artifacts, revisions=revisions)
    resolved_request = request or ProjectionRequest(
        space_id=space_id,
        revision_id=revision_id,
        scope_selector=ScopeSelector(
            include_unscoped=True,
            bindings=[ScopeBinding(axis="test:scope", value="one")],
        ),
        audience_labels=["test:audience"],
        standing_selector=[KnowledgeStanding.ESTABLISHED],
    )
    resolved_policy = policy or AlwaysAdmitPolicy(policy_id=domain_contract.admission_policy_id)
    context = KnowledgeReadContext(
        parsed=parsed,
        request=resolved_request,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
        domain_policy=resolved_policy,
        source_reader=reader,
    )
    return context, reader


def _org_with_isolated_entity() -> tuple[KnowledgeReadContext, InMemoryKnowledgeSourceReader]:
    data = _load_fixture("organizational_memory_v1.json")
    entities = [Entity.model_validate(item) for item in data["entities"]]
    entities.append(Entity(entity_id="ent:isolated-zero-assertions"))
    assertions = [Assertion.model_validate(item) for item in data["assertions"]]
    evidence = [EvidenceRefV3.model_validate(item) for item in data["sources"]["evidence"]]
    artifact = SourceArtifactV3.model_validate(data["sources"]["artifact"])
    revisions = [SourceRevisionV2.model_validate(item) for item in data["sources"]["revisions"]]
    domain_contract = _org_domain_contract()
    semantic_profile = _org_semantic_profile()
    revision = KnowledgeRevision(
        space_id=data["space_id"],
        revision_id="rev:org-isolated",
        created_at=datetime(2026, 9, 15, tzinfo=UTC),
        operation_ids=["op:fixture"],
        graph_schema="dm_vnext_graph_v1",
        graph_payload_sha256="0" * 64,
        domain_contract_ref=DomainContractRef(
            domain_id=domain_contract.domain_id,
            domain_revision=domain_contract.domain_revision,
            descriptor_sha256=ORG_CONTRACT_DIGEST,
        ),
        semantic_profile_ref=SemanticProfileRef(
            profile_id=semantic_profile.profile_id,
            profile_revision=semantic_profile.profile_revision,
            descriptor_sha256=ORG_PROFILE_DIGEST,
        ),
    )
    parsed = build_parsed_knowledge_revision(
        revision=revision,
        entities=entities,
        assertions=assertions,
        evidence=evidence,
    )
    reader = InMemoryKnowledgeSourceReader(
        artifacts={artifact.source_artifact_id: artifact},
        revisions={item.source_revision_id: item for item in revisions},
    )
    request = ProjectionRequest(
        space_id=data["space_id"],
        revision_id=revision.revision_id,
        scope_selector=ScopeSelector(
            include_unscoped=True,
            bindings=[
                ScopeBinding(axis="organization:project", value="retrieval"),
                ScopeBinding(axis="organization:team", value="research"),
            ],
        ),
        audience_labels=["organization:team"],
        standing_selector=[KnowledgeStanding.ESTABLISHED],
    )
    context = KnowledgeReadContext(
        parsed=parsed,
        request=request,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
        domain_policy=AlwaysAdmitPolicy(policy_id=domain_contract.admission_policy_id),
        source_reader=reader,
    )
    return context, reader


def _high_degree_lab(*, edge_count: int = 30) -> KnowledgeReadContext:
    entities = [Entity(entity_id="ent:hub")]
    targets = [Entity(entity_id=f"ent:target-{index:02d}") for index in range(edge_count)]
    entities.extend(targets)
    evidence: list[EvidenceRefV3] = []
    assertions: list[Assertion] = []
    artifacts: dict[str, SourceArtifactV3] = {}
    revisions: dict[str, SourceRevisionV2] = {}
    for index in range(edge_count):
        artifact_id = f"src:edge-{index:02d}"
        revision_row_id = f"srcrev:edge-{index:02d}"
        artifacts[artifact_id] = SourceArtifactV3(
            source_artifact_id=artifact_id,
            source_classification="test:doc",
            current_revision_id=revision_row_id,
            authority="primary",
            visibility=PublicVisibility(),
            status="active",
        )
        revisions[revision_row_id] = SourceRevisionV2(
            source_revision_id=revision_row_id,
            source_artifact_id=artifact_id,
            content_sha256=f"{index:064x}"[:64],
            body_storage="inline",
            created_at=datetime(2026, 9, 15, tzinfo=UTC),
        )
        evidence_id = f"evidence:edge-{index:02d}"
        evidence.append(
            EvidenceRefV3(
                evidence_ref_id=evidence_id,
                source_artifact_id=artifact_id,
                source_revision_id=revision_row_id,
                evidence_role="support",
                can_open_source=True,
                can_highlight_span=False,
                locator=f"loc:{index}",
            )
        )
        assertions.append(
            Assertion(
                assertion_id=f"asrt:hub-edge-{index:02d}",
                subject_entity_id="ent:hub",
                predicate="test:relates",
                value=EntityRefValue(entity_id=f"ent:target-{index:02d}"),
                metadata=AssertionMetadata(
                    scope=[ScopeBinding(axis="test:scope", value="one")],
                    visibility=PublicVisibility(),
                    epistemic_basis=EpistemicBasis.ASSERTED,
                    claim_mode="test:fact",
                    standing=KnowledgeStanding.ESTABLISHED,
                    evidence_ref_ids=[evidence_id],
                    temporal_scope=TimelessTemporalScope(),
                ),
            )
        )
    context, _ = _lab_context(
        entities=entities,
        assertions=assertions,
        evidence=evidence,
        artifacts=artifacts,
        revisions=revisions,
    )
    return context


def _many_evidence_lab(*, evidence_count: int = 33) -> KnowledgeReadContext:
    entities = [Entity(entity_id="ent:evidence-heavy")]
    evidence: list[EvidenceRefV3] = []
    evidence_ids: list[str] = []
    artifacts: dict[str, SourceArtifactV3] = {}
    revisions: dict[str, SourceRevisionV2] = {}
    for index in range(evidence_count):
        artifact_id = f"src:ev-{index:02d}"
        revision_row_id = f"srcrev:ev-{index:02d}"
        evidence_id = f"evidence:heavy-{index:02d}"
        evidence_ids.append(evidence_id)
        artifacts[artifact_id] = SourceArtifactV3(
            source_artifact_id=artifact_id,
            source_classification="test:doc",
            current_revision_id=revision_row_id,
            authority="primary",
            visibility=PublicVisibility(),
            status="active",
        )
        revisions[revision_row_id] = SourceRevisionV2(
            source_revision_id=revision_row_id,
            source_artifact_id=artifact_id,
            content_sha256=f"{index + 10:064x}"[:64],
            body_storage="inline",
            created_at=datetime(2026, 9, 15, tzinfo=UTC),
        )
        evidence.append(
            EvidenceRefV3(
                evidence_ref_id=evidence_id,
                source_artifact_id=artifact_id,
                source_revision_id=revision_row_id,
                evidence_role="support",
                can_open_source=True,
                can_highlight_span=False,
                locator=f"§{index}",
                uri=f"doc://heavy/{index}",
            )
        )
    assertion = Assertion(
        assertion_id="asrt:evidence-heavy",
        subject_entity_id="ent:evidence-heavy",
        predicate="test:title",
        value=LiteralValue(value={"note": "heavy"}),
        metadata=AssertionMetadata(
            scope=[ScopeBinding(axis="test:scope", value="one")],
            visibility=PublicVisibility(),
            epistemic_basis=EpistemicBasis.ASSERTED,
            claim_mode="test:fact",
            standing=KnowledgeStanding.ESTABLISHED,
            evidence_ref_ids=evidence_ids,
            temporal_scope=TimelessTemporalScope(),
        ),
    )
    context, _ = _lab_context(
        entities=entities,
        assertions=[assertion],
        evidence=evidence,
        artifacts=artifacts,
        revisions=revisions,
    )
    return context


def _decoy_heavy_lab(*, decoy_assertions: int) -> tuple[KnowledgeReadContext, KnowledgeReadContext]:
    selected_entities = [Entity(entity_id="ent:selected")]
    decoy_entities = [
        Entity(entity_id=f"ent:decoy-{index:04d}") for index in range(decoy_assertions)
    ]
    entities = [*selected_entities, *decoy_entities]
    evidence: list[EvidenceRefV3] = []
    assertions: list[Assertion] = []
    artifacts = {
        "src:selected": SourceArtifactV3(
            source_artifact_id="src:selected",
            source_classification="test:doc",
            current_revision_id="srcrev:selected",
            authority="primary",
            visibility=PublicVisibility(),
            status="active",
        )
    }
    revisions = {
        "srcrev:selected": SourceRevisionV2(
            source_revision_id="srcrev:selected",
            source_artifact_id="src:selected",
            content_sha256="d" * 64,
            body_storage="inline",
            created_at=datetime(2026, 9, 15, tzinfo=UTC),
        )
    }
    evidence.append(
        EvidenceRefV3(
            evidence_ref_id="evidence:selected",
            source_artifact_id="src:selected",
            source_revision_id="srcrev:selected",
            evidence_role="support",
            can_open_source=True,
            can_highlight_span=False,
        )
    )
    assertions.append(
        Assertion(
            assertion_id="asrt:selected",
            subject_entity_id="ent:selected",
            predicate="test:title",
            value=LiteralValue(value={"role": "selected"}),
            metadata=AssertionMetadata(
                scope=[ScopeBinding(axis="test:scope", value="one")],
                visibility=PublicVisibility(),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="test:fact",
                standing=KnowledgeStanding.ESTABLISHED,
                evidence_ref_ids=["evidence:selected"],
                temporal_scope=TimelessTemporalScope(),
            ),
        )
    )
    for index in range(decoy_assertions):
        decoy_artifact = f"src:decoy-{index:04d}"
        decoy_revision = f"srcrev:decoy-{index:04d}"
        artifacts[decoy_artifact] = SourceArtifactV3(
            source_artifact_id=decoy_artifact,
            source_classification="test:doc",
            current_revision_id=decoy_revision,
            authority="primary",
            visibility=PublicVisibility(),
            status="active",
        )
        revisions[decoy_revision] = SourceRevisionV2(
            source_revision_id=decoy_revision,
            source_artifact_id=decoy_artifact,
            content_sha256=f"{index:064x}"[:64],
            body_storage="inline",
            created_at=datetime(2026, 9, 15, tzinfo=UTC),
        )
        evidence_id = f"evidence:decoy-{index:04d}"
        evidence.append(
            EvidenceRefV3(
                evidence_ref_id=evidence_id,
                source_artifact_id=decoy_artifact,
                source_revision_id=decoy_revision,
                evidence_role="support",
                can_open_source=True,
                can_highlight_span=False,
            )
        )
        assertions.append(
            Assertion(
                assertion_id=f"asrt:decoy-{index:04d}",
                subject_entity_id=f"ent:decoy-{index:04d}",
                predicate="test:title",
                value=LiteralValue(value={"n": index}),
                metadata=AssertionMetadata(
                    scope=[ScopeBinding(axis="test:scope", value="one")],
                    visibility=PublicVisibility(),
                    epistemic_basis=EpistemicBasis.ASSERTED,
                    claim_mode="test:fact",
                    standing=KnowledgeStanding.ESTABLISHED,
                    evidence_ref_ids=[evidence_id],
                    temporal_scope=TimelessTemporalScope(),
                ),
            )
        )
    small, _ = _lab_context(
        entities=[Entity(entity_id="ent:selected")],
        assertions=[assertions[0]],
        evidence=[evidence[0]],
        artifacts={"src:selected": artifacts["src:selected"]},
        revisions={"srcrev:selected": revisions["srcrev:selected"]},
        space_id="space:small",
        revision_id="rev:small",
    )
    large, _ = _lab_context(
        entities=entities,
        assertions=assertions,
        evidence=evidence,
        artifacts=artifacts,
        revisions=revisions,
        space_id="space:large",
        revision_id="rev:large",
    )
    return small, large


def _incoming_neighbor_heavy_lab(*, neighbor_subject_count: int) -> KnowledgeReadContext:
    """One incoming edge from a neighbor that also has a large unrelated subject set."""

    entities = [Entity(entity_id="ent:selected"), Entity(entity_id="ent:noisy-neighbor")]
    assertions = [
        Assertion(
            assertion_id=f"asrt:neighbor-noise-{index:04d}",
            subject_entity_id="ent:noisy-neighbor",
            predicate="test:relates",
            value=EntityRefValue(entity_id="ent:noisy-neighbor"),
            metadata=AssertionMetadata(
                scope=[ScopeBinding(axis="test:scope", value="one")],
                visibility=PublicVisibility(),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="test:fact",
                standing=KnowledgeStanding.ESTABLISHED,
                evidence_ref_ids=[],
                temporal_scope=TimelessTemporalScope(),
            ),
        )
        for index in range(neighbor_subject_count)
    ]
    assertions.append(
        Assertion(
            assertion_id="asrt:neighbor-points-at-selected",
            subject_entity_id="ent:noisy-neighbor",
            predicate="test:relates",
            value=EntityRefValue(entity_id="ent:selected"),
            metadata=AssertionMetadata(
                scope=[ScopeBinding(axis="test:scope", value="one")],
                visibility=PublicVisibility(),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="test:fact",
                standing=KnowledgeStanding.ESTABLISHED,
                evidence_ref_ids=["evidence:incoming"],
                temporal_scope=TimelessTemporalScope(),
            ),
        )
    )
    artifacts = {
        "src:incoming": SourceArtifactV3(
            source_artifact_id="src:incoming",
            source_classification="test:doc",
            current_revision_id="srcrev:incoming",
            authority="primary",
            visibility=PublicVisibility(),
            status="active",
        )
    }
    revisions = {
        "srcrev:incoming": SourceRevisionV2(
            source_revision_id="srcrev:incoming",
            source_artifact_id="src:incoming",
            content_sha256="e" * 64,
            body_storage="inline",
            created_at=datetime(2026, 9, 15, tzinfo=UTC),
        )
    }
    evidence = [
        EvidenceRefV3(
            evidence_ref_id="evidence:incoming",
            source_artifact_id="src:incoming",
            source_revision_id="srcrev:incoming",
            evidence_role="support",
            can_open_source=True,
            can_highlight_span=False,
        )
    ]
    context, _ = _lab_context(
        entities=entities,
        assertions=assertions,
        evidence=evidence,
        artifacts=artifacts,
        revisions=revisions,
        space_id="space:incoming-heavy",
        revision_id="rev:incoming-heavy",
    )
    return context


def _rebind_lab_context(
    context: KnowledgeReadContext,
    reader: InMemoryKnowledgeSourceReader,
) -> KnowledgeReadContext:
    return KnowledgeReadContext(
        parsed=context.parsed,
        request=context.request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=reader,
    )


def _excluded_incoming_source_lab() -> tuple[KnowledgeReadContext, InMemoryKnowledgeSourceReader]:
    artifacts = {
        "src:visible": SourceArtifactV3(
            source_artifact_id="src:visible",
            source_classification="test:doc",
            current_revision_id="srcrev:visible",
            authority="primary",
            visibility=PublicVisibility(),
            status="active",
        ),
        "src:hidden": SourceArtifactV3(
            source_artifact_id="src:hidden",
            source_classification="test:doc",
            current_revision_id="srcrev:hidden",
            authority="primary",
            visibility=PublicVisibility(),
            status="active",
        ),
    }
    revisions = {
        "srcrev:visible": SourceRevisionV2(
            source_revision_id="srcrev:visible",
            source_artifact_id="src:visible",
            content_sha256="1" * 64,
            body_storage="inline",
            created_at=datetime(2026, 9, 15, tzinfo=UTC),
        ),
        "srcrev:hidden": SourceRevisionV2(
            source_revision_id="srcrev:hidden",
            source_artifact_id="src:hidden",
            content_sha256="2" * 64,
            body_storage="inline",
            created_at=datetime(2026, 9, 15, tzinfo=UTC),
        ),
    }
    entities = [Entity(entity_id="ent:selected"), Entity(entity_id="ent:neighbor")]
    assertions = [
        Assertion(
            assertion_id="asrt:visible-subject",
            subject_entity_id="ent:selected",
            predicate="test:title",
            value=LiteralValue(value={"role": "selected"}),
            metadata=AssertionMetadata(
                scope=[ScopeBinding(axis="test:scope", value="one")],
                visibility=PublicVisibility(),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="test:fact",
                standing=KnowledgeStanding.ESTABLISHED,
                evidence_ref_ids=["evidence:visible"],
                temporal_scope=TimelessTemporalScope(),
            ),
        ),
        Assertion(
            assertion_id="asrt:hidden-incoming",
            subject_entity_id="ent:neighbor",
            predicate="test:relates",
            value=EntityRefValue(entity_id="ent:selected"),
            metadata=AssertionMetadata(
                scope=[ScopeBinding(axis="test:scope", value="one")],
                visibility=PublicVisibility(),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="test:fact",
                standing=KnowledgeStanding.ESTABLISHED,
                evidence_ref_ids=["evidence:hidden"],
                temporal_scope=TimelessTemporalScope(),
            ),
        ),
    ]
    evidence = [
        EvidenceRefV3(
            evidence_ref_id="evidence:visible",
            source_artifact_id="src:visible",
            source_revision_id="srcrev:visible",
            evidence_role="support",
            can_open_source=True,
            can_highlight_span=False,
        ),
        EvidenceRefV3(
            evidence_ref_id="evidence:hidden",
            source_artifact_id="src:hidden",
            source_revision_id="srcrev:hidden",
            evidence_role="support",
            can_open_source=True,
            can_highlight_span=False,
        ),
    ]
    return _lab_context(
        entities=entities,
        assertions=assertions,
        evidence=evidence,
        artifacts=artifacts,
        revisions=revisions,
        policy=ExcludeByAssertionIdPolicy(
            policy_id="test.always",
            excluded_assertion_ids=frozenset({"asrt:hidden-incoming"}),
        ),
    )


@pytest.fixture(name="org_context")
def fixture_org_context() -> tuple[KnowledgeReadContext, InMemoryKnowledgeSourceReader]:
    return _build_from_fixture(
        "organizational_memory_v1.json",
        domain_contract=_org_domain_contract(),
        semantic_profile=_org_semantic_profile(),
        contract_digest=ORG_CONTRACT_DIGEST,
        profile_digest=ORG_PROFILE_DIGEST,
    )


# --- A. Dispatch / authority (1-8) ---


def test_01_v2_merge_sha_recorded_in_stewardship() -> None:
    text = STEWARD_PATH.read_text(encoding="utf-8")
    assert V2_MERGE_SHA in text


def test_02_v2_predecessor_recorded_in_authority_docs() -> None:
    steward = STEWARD_PATH.read_text(encoding="utf-8")
    handoff = V3_HANDOFF_PATH.read_text(encoding="utf-8")
    assert V2_MERGE_SHA in steward
    assert V2_MERGE_SHA in handoff


def test_03_steward_rewrite_not_required_on_first_v3_impl_commit() -> None:
    text = V3_HANDOFF_PATH.read_text(encoding="utf-8")
    assert "not a first implementation commit" in text


def test_04_steward_records_accepted_v2_head_and_review() -> None:
    text = STEWARD_PATH.read_text(encoding="utf-8")
    assert V2_ACCEPTED_HEAD in text
    assert V2_FINAL_REVIEW in text
    assert "V2_KNOWLEDGE_READ_CONTEXT_ADMISSION_ACCEPTED" in text


def test_05_steward_records_v2_benchmark_structural_gate() -> None:
    text = STEWARD_PATH.read_text(encoding="utf-8")
    assert "vnext_candidate_admission_10k_v1.json" in text
    bench = json.loads(V2_BENCH_PATH.read_text(encoding="utf-8"))
    assert bench["structural_gate"]["passes"] is True


def test_06_steward_phase_v3_complete_v5_1_active() -> None:
    text = STEWARD_PATH.read_text(encoding="utf-8")
    assert "V3 COMPLETE" in text
    assert "V4 COMPLETE" in text
    assert "V4.1 COMPLETE" in text
    assert "V4.2 COMPLETE" in text
    assert "V4.3 COMPLETE" in text
    assert "V5 ACTIVE" in text
    assert "V5.1 ACTIVE" in text


def test_07_frozen_v0_aggregate_remains_exact() -> None:
    bundle_path = REPO_ROOT / "Docs" / "Contracts" / "vnext" / "dm_vnext_contract_v1.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert bundle["aggregate_sha256"] == CANONICAL_V0_AGGREGATE


def test_08_activation_anchor_recorded_in_authority_docs() -> None:
    handoff = V3_HANDOFF_PATH.read_text(encoding="utf-8")
    assert ACTIVATION_MAIN_SHA in handoff
    assert "current main at activation sync" in handoff.lower()


# --- B. Exact entity read (9-20) ---


def test_09_exact_hit_returns_selected_entity(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_entity(context, "priya")
    assert result.found is True
    assert result.entity is not None
    assert result.entity.entity_id == "priya"


def test_10_exact_miss_without_fallback(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, _ = org_context
    result = _SVC.get_entity(context, "missing-entity")
    assert result.found is False
    assert result.entity is None
    assert result.work.entity_lookups == 1


def test_11_zero_assertion_entity_found_with_empty_assertions() -> None:
    context, _ = _org_with_isolated_entity()
    result = _SVC.get_entity(context, "ent:isolated-zero-assertions")
    assert result.found is True
    assert result.assertions == ()


def test_12_all_excluded_assertions_still_return_entity(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    policy = ExcludeByAssertionIdPolicy(
        policy_id=context.domain_contract.admission_policy_id,
        excluded_assertion_ids=frozenset(
            {
                "asrt:priya-owns-retrieval-apr",
                "asrt:priya-member-research",
                "asrt:priya-title",
            }
        ),
    )
    adjusted = KnowledgeReadContext(
        parsed=context.parsed,
        request=context.request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=policy,
        source_reader=context.source_reader,
    )
    result = _SVC.get_entity(adjusted, "priya")
    assert result.found is True
    assert result.assertions == ()


def test_13_get_entity_candidates_only_subject_index(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    parsed = context.parsed
    result = _SVC.get_entity(context, "retrieval-evaluation")
    assert result.work.incoming_entity_ref_candidates == 0
    assert result.work.outgoing_entity_ref_candidates == 0
    assert result.work.subject_assertion_candidates == len(
        parsed.assertions_by_subject.get("retrieval-evaluation", ())
    )


def test_14_get_entity_excludes_incoming_touching(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    exact = _SVC.get_entity(context, "retrieval-evaluation")
    complete = _SVC.get_complete_entity(context, "retrieval-evaluation")
    assert len(complete.assertions) > len(exact.assertions)
    assert "asrt:priya-owns-retrieval-apr" not in {item.assertion_id for item in exact.assertions}
    assert "asrt:priya-owns-retrieval-apr" in {item.assertion_id for item in complete.assertions}


def test_15_subject_candidates_evaluated_via_v2_admission(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_entity(context, "priya")
    assert result.work.assertions_evaluated == result.work.deduped_candidate_assertions
    assert result.work.policy_evaluations >= 0


def test_16_kernel_excluded_assertions_not_returned(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, reader = org_context
    reader._artifacts.clear()
    refreshed = _refresh_org_context(context, reader)
    result = _SVC.get_entity(refreshed, "priya")
    assert result.found is True
    assert result.assertions == ()


def test_17_domain_policy_excluded_assertions_not_returned(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    policy = ExcludeByAssertionIdPolicy(
        policy_id=context.domain_contract.admission_policy_id,
        excluded_assertion_ids=frozenset({"asrt:priya-title"}),
    )
    adjusted = KnowledgeReadContext(
        parsed=context.parsed,
        request=context.request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=policy,
        source_reader=context.source_reader,
    )
    result = _SVC.get_entity(adjusted, "priya")
    assert all(item.assertion_id != "asrt:priya-title" for item in result.assertions)


def test_18_inactive_source_excludes_supporting_assertion(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, reader = org_context
    artifact = reader._artifacts["src:ownership-document"]
    reader._artifacts["src:ownership-document"] = artifact.model_copy(
        update={"status": "retracted"}
    )
    refreshed = _refresh_org_context(context, reader)
    result = _SVC.get_entity(refreshed, "priya")
    assert "asrt:priya-owns-retrieval-apr" not in {item.assertion_id for item in result.assertions}


def test_19_exact_read_assertion_ordering_deterministic(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    first = _SVC.get_entity(context, "priya")
    second = _SVC.get_entity(context, "priya")
    assert [item.assertion_id for item in first.assertions] == [
        item.assertion_id for item in second.assertions
    ]
    assert tuple(sorted(item.assertion_id for item in first.assertions)) == tuple(
        item.assertion_id for item in first.assertions
    )


def test_20_exact_read_result_digest_stable(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, _ = org_context
    first = _SVC.get_entity(context, "priya")
    second = _SVC.get_entity(context, "priya")
    assert first.result_digest == second.result_digest


# --- C. Complete entity candidate discovery (21-30) ---


def test_21_complete_includes_subject_assertions(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "retrieval-evaluation")
    assert "asrt:retrieval-classification" in {item.assertion_id for item in result.assertions}


def test_22_complete_includes_outgoing_entity_ref(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "priya")
    assert "asrt:priya-owns-retrieval-apr" in {item.assertion_id for item in result.assertions}


def test_23_complete_includes_incoming_entity_ref(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "retrieval-evaluation")
    incoming = {"asrt:priya-owns-retrieval-apr", "asrt:marco-owns-retrieval-sep"}
    assert incoming.issubset({item.assertion_id for item in result.assertions})


def test_24_candidate_ids_deduplicated() -> None:
    entities = [Entity(entity_id="ent:a"), Entity(entity_id="ent:b")]
    assertions = [
        Assertion(
            assertion_id="asrt:self-loop",
            subject_entity_id="ent:a",
            predicate="test:relates",
            value=EntityRefValue(entity_id="ent:a"),
            metadata=AssertionMetadata(
                scope=[ScopeBinding(axis="test:scope", value="one")],
                visibility=PublicVisibility(),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="test:fact",
                standing=KnowledgeStanding.ESTABLISHED,
                evidence_ref_ids=[],
                temporal_scope=TimelessTemporalScope(),
            ),
        )
    ]
    context, _ = _lab_context(entities=entities, assertions=assertions, evidence=[])
    result = _SVC.get_complete_entity(context, "ent:a")
    assert result.work.deduped_candidate_assertions == 1


def test_25_subject_and_outgoing_index_overlap_evaluated_once(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "priya")
    ids = [item.assertion_id for item in result.assertions]
    assert len(ids) == len(set(ids))
    assert result.work.assertions_evaluated == result.work.deduped_candidate_assertions


def test_26_incoming_discovery_uses_index_not_full_scan(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "retrieval-evaluation")
    assert result.work.incoming_entity_ref_candidates == 2
    assert result.work.deduped_candidate_assertions < len(context.parsed.assertions_by_id)
    assert context.parsed.get_incoming_entity_ref_assertion_ids("retrieval-evaluation") == (
        "asrt:marco-owns-retrieval-sep",
        "asrt:priya-owns-retrieval-apr",
    )


def test_27_self_loop_touching_assertion_returned_once() -> None:
    entities = [Entity(entity_id="ent:loop")]
    assertions = [
        Assertion(
            assertion_id="asrt:loop",
            subject_entity_id="ent:loop",
            predicate="test:relates",
            value=EntityRefValue(entity_id="ent:loop"),
            metadata=AssertionMetadata(
                scope=[ScopeBinding(axis="test:scope", value="one")],
                visibility=PublicVisibility(),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="test:fact",
                standing=KnowledgeStanding.ESTABLISHED,
                evidence_ref_ids=[],
                temporal_scope=TimelessTemporalScope(),
            ),
        )
    ]
    context, _ = _lab_context(entities=entities, assertions=assertions, evidence=[])
    result = _SVC.get_complete_entity(context, "ent:loop")
    assert [item.assertion_id for item in result.assertions] == ["asrt:loop"]


def test_28_incoming_direction_not_swapped(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "retrieval-evaluation")
    incoming = next(
        item for item in result.assertions if item.assertion_id == "asrt:priya-owns-retrieval-apr"
    )
    assert incoming.subject_entity_id == "priya"
    assert isinstance(incoming.value, ParsedEntityRefValue)
    assert incoming.value.entity_id == "retrieval-evaluation"


def test_29_outgoing_direction_not_swapped(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "priya")
    outgoing = next(
        item for item in result.assertions if item.assertion_id == "asrt:priya-owns-retrieval-apr"
    )
    assert outgoing.subject_entity_id == "priya"
    assert isinstance(outgoing.value, ParsedEntityRefValue)
    assert outgoing.value.entity_id == "retrieval-evaluation"


def test_30_non_entity_ref_subject_assertions_in_complete_read(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "priya")
    assert "asrt:priya-title" in {item.assertion_id for item in result.assertions}


# --- D. Endpoint semantics (31-38) ---


def test_31_admitted_touching_endpoints_returned(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "retrieval-evaluation")
    related_ids = {item.entity_id for item in result.related_entities}
    assert {"priya", "marco"}.issubset(related_ids)


def test_32_excluded_touching_does_not_disclose_unique_endpoint() -> None:
    data = _load_fixture("buddy_shaped_admission_v1.json")
    entities = [Entity.model_validate(item) for item in data["entities"]]
    entities.append(Entity(entity_id="loc:c3-secret-only"))
    assertions = [Assertion.model_validate(item) for item in data["assertions"]]
    assertions.append(
        Assertion(
            assertion_id="asrt:c3-secret-endpoint",
            subject_entity_id="npc:hero",
            predicate="dungeonbuddy:located_at",
            value=EntityRefValue(entity_id="loc:c3-secret-only"),
            metadata=AssertionMetadata(
                scope=[ScopeBinding(axis="dungeonbuddy.scope:campaign", value="C3")],
                visibility=PublicVisibility(),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="dungeonbuddy:fact",
                standing=KnowledgeStanding.ESTABLISHED,
                evidence_ref_ids=[],
                temporal_scope=TimelessTemporalScope(),
            ),
        )
    )
    evidence = [EvidenceRefV3.model_validate(item) for item in data["sources"]["evidence"]]
    artifact = SourceArtifactV3.model_validate(data["sources"]["artifact"])
    revisions = [SourceRevisionV2.model_validate(item) for item in data["sources"]["revisions"]]
    domain_contract = _buddy_domain_contract()
    semantic_profile = _buddy_semantic_profile()
    revision = KnowledgeRevision(
        space_id=data["space_id"],
        revision_id="rev:buddy-secret",
        created_at=datetime(2026, 9, 15, tzinfo=UTC),
        operation_ids=["op:buddy"],
        graph_schema="dm_vnext_graph_v1",
        graph_payload_sha256="0" * 64,
        domain_contract_ref=DomainContractRef(
            domain_id=domain_contract.domain_id,
            domain_revision=domain_contract.domain_revision,
            descriptor_sha256=BUDDY_CONTRACT_DIGEST,
        ),
        semantic_profile_ref=SemanticProfileRef(
            profile_id=semantic_profile.profile_id,
            profile_revision=semantic_profile.profile_revision,
            descriptor_sha256=BUDDY_PROFILE_DIGEST,
        ),
    )
    parsed = build_parsed_knowledge_revision(
        revision=revision,
        entities=entities,
        assertions=assertions,
        evidence=evidence,
    )
    reader = InMemoryKnowledgeSourceReader(
        artifacts={artifact.source_artifact_id: artifact},
        revisions={item.source_revision_id: item for item in revisions},
    )
    request = _buddy_request(campaign="C2", audience=["dungeonbuddy.visibility:player"])
    request = request.model_copy(update={"revision_id": revision.revision_id})
    context = KnowledgeReadContext(
        parsed=parsed,
        request=request,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
        domain_policy=AlwaysAdmitPolicy(policy_id=domain_contract.admission_policy_id),
        source_reader=reader,
    )
    result = _SVC.get_complete_entity(context, "npc:hero")
    assert "loc:c3-secret-only" not in {item.entity_id for item in result.related_entities}


def test_33_endpoint_lookup_uses_exact_entity_id(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "retrieval-evaluation")
    for related in result.related_entities:
        assert context.parsed.get_entity(related.entity_id) is not None


def test_34_no_endpoint_lexical_fallback(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, _ = org_context
    miss = _SVC.get_complete_entity(context, "Priya")
    assert miss.found is False


def test_35_self_loop_not_duplicated_in_related_entities() -> None:
    entities = [Entity(entity_id="ent:loop")]
    assertions = [
        Assertion(
            assertion_id="asrt:loop",
            subject_entity_id="ent:loop",
            predicate="test:relates",
            value=EntityRefValue(entity_id="ent:loop"),
            metadata=AssertionMetadata(
                scope=[ScopeBinding(axis="test:scope", value="one")],
                visibility=PublicVisibility(),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="test:fact",
                standing=KnowledgeStanding.ESTABLISHED,
                evidence_ref_ids=[],
                temporal_scope=TimelessTemporalScope(),
            ),
        )
    ]
    context, _ = _lab_context(entities=entities, assertions=assertions, evidence=[])
    result = _SVC.get_complete_entity(context, "ent:loop")
    assert result.related_entities == ()


def test_36_related_endpoints_sorted_and_deduped(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "retrieval-evaluation")
    related_ids = [item.entity_id for item in result.related_entities]
    assert related_ids == sorted(related_ids)
    assert len(related_ids) == len(set(related_ids))


def test_37_endpoint_subject_assertions_not_recursively_expanded(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "retrieval-evaluation")
    priya_related = next(item for item in result.related_entities if item.entity_id == "priya")
    assert priya_related.entity_id == "priya"
    assert "asrt:priya-member-research" not in {item.assertion_id for item in result.assertions}


def test_38_dangling_admitted_endpoint_fails_closed() -> None:
    entities = [Entity(entity_id="ent:src"), Entity(entity_id="ent:dst")]
    assertions = [
        Assertion(
            assertion_id="asrt:link",
            subject_entity_id="ent:src",
            predicate="test:relates",
            value=EntityRefValue(entity_id="ent:dst"),
            metadata=AssertionMetadata(
                scope=[ScopeBinding(axis="test:scope", value="one")],
                visibility=PublicVisibility(),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="test:fact",
                standing=KnowledgeStanding.ESTABLISHED,
                evidence_ref_ids=[],
                temporal_scope=TimelessTemporalScope(),
            ),
        )
    ]
    context, _ = _lab_context(entities=entities, assertions=assertions, evidence=[])
    parsed = context.parsed
    corrupted_entities = FrozenDict(
        {key: value for key, value in parsed.entities_by_id.items() if key != "ent:dst"}
    )
    corrupted = replace(parsed, entities_by_id=corrupted_entities)
    broken = KnowledgeReadContext(
        parsed=corrupted,
        request=context.request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=context.source_reader,
    )
    with pytest.raises(EntityReadIntegrityError, match="dangling"):
        _SVC.get_complete_entity(broken, "ent:src")


# --- E. Completeness (39-46) ---


def test_39_low_degree_complete_reports_complete(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "ownership-document")
    assert result.completeness.status == "complete"


def test_40_high_degree_complete_returns_all_touching_assertions() -> None:
    context = _high_degree_lab(edge_count=30)
    result = _SVC.get_complete_entity(context, "ent:hub")
    assert result.completeness.status == "complete"
    assert len(result.assertions) == 30
    assert len(result.related_entities) == 30


def test_41_no_relationship_cap_applied() -> None:
    context = _high_degree_lab(edge_count=30)
    result = _SVC.get_complete_entity(context, "ent:hub")
    assert result.completeness.status == "complete"
    assert len(result.assertions) > 24


def test_42_required_related_endpoints_present() -> None:
    context = _high_degree_lab(edge_count=26)
    result = _SVC.get_complete_entity(context, "ent:hub")
    assert len(result.related_entities) == 26


def test_43_excluded_assertions_do_not_force_partial(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, reader = org_context
    reader._artifacts.clear()
    refreshed = _refresh_org_context(context, reader)
    result = _SVC.get_complete_entity(refreshed, "priya")
    assert result.completeness.status == "complete"


def test_44_partial_completeness_rejects_inconsistent_states() -> None:
    with pytest.raises(EntityReadIntegrityError):
        EntityReadCompleteness(status="complete", reason="support_unavailable")
    with pytest.raises(EntityReadIntegrityError):
        EntityReadCompleteness(status="partial", reason=None)
    with pytest.raises(EntityReadIntegrityError):
        EntityReadCompleteness(status="partial", reason="example")
    named = EntityReadCompleteness(status="partial", reason="support_unavailable")
    assert named.reason == "support_unavailable"


def test_45_no_truncation_behind_complete() -> None:
    context = _high_degree_lab(edge_count=30)
    result = _SVC.get_complete_entity(context, "ent:hub")
    assert len(result.assertions) == 30


def test_46_no_client_side_union_required(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "retrieval-evaluation")
    assert {"asrt:priya-owns-retrieval-apr", "asrt:marco-owns-retrieval-sep"}.issubset(
        {item.assertion_id for item in result.assertions}
    )


# --- F. Evidence / provenance (47-57) ---


def test_47_evidence_only_from_admitted_assertions(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, reader = org_context
    reader._artifacts.clear()
    refreshed = _refresh_org_context(context, reader)
    result = _SVC.get_entity(refreshed, "priya")
    assert result.evidence == ()


def test_48_excluded_candidate_evidence_not_exposed(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    full = _SVC.get_entity(context, "priya")
    policy = ExcludeByAssertionIdPolicy(
        policy_id=context.domain_contract.admission_policy_id,
        excluded_assertion_ids=frozenset({"asrt:priya-title"}),
    )
    adjusted = KnowledgeReadContext(
        parsed=context.parsed,
        request=context.request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=policy,
        source_reader=context.source_reader,
    )
    narrowed = _SVC.get_entity(adjusted, "priya")
    assert len(narrowed.evidence) <= len(full.evidence)
    assert "asrt:priya-title" not in {item.assertion_id for item in narrowed.assertions}


def test_49_evidence_identity_preserved(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, _ = org_context
    result = _SVC.get_entity(context, "priya")
    locators = {item.locator for item in result.evidence if item.locator}
    assert "§ownership" in locators


def test_50_source_artifact_and_revision_identity_preserved(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_entity(context, "priya")
    assert result.source_artifacts
    assert result.source_revisions
    assert result.source_revisions[0].content_sha256


def test_51_locator_metadata_survives() -> None:
    context = _many_evidence_lab(evidence_count=33)
    result = _SVC.get_entity(context, "ent:evidence-heavy")
    assert len(result.evidence) == 33
    assert any(item.uri == "doc://heavy/0" for item in result.evidence)


def test_52_more_than_32_support_records_not_truncated() -> None:
    context = _many_evidence_lab(evidence_count=33)
    result = _SVC.get_entity(context, "ent:evidence-heavy")
    assert len(result.evidence) == 33
    assert result.work.evidence_ids_returned == 33


def test_53_one_entity_read_one_provenance_epoch(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_entity(context, "priya")
    assert result.work.provenance_snapshot_calls == 1


def test_54_single_provenance_snapshot_for_entity_read(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_complete_entity(context, "retrieval-evaluation")
    assert result.work.provenance_snapshot_calls == 1


def test_55_new_context_observes_changed_source_state(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context_a, reader = org_context
    assert _SVC.get_entity(context_a, "priya").assertions
    artifact = reader._artifacts["src:ownership-document"]
    reader._artifacts["src:ownership-document"] = artifact.model_copy(
        update={"status": "retracted"}
    )
    context_b = _refresh_org_context(context_a, reader)
    result_b = _SVC.get_entity(context_b, "priya")
    assert result_b.assertions == ()


def test_56_existing_context_remains_coherent(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context_a, reader = org_context
    first = _SVC.get_entity(context_a, "priya")
    artifact = reader._artifacts["src:ownership-document"]
    reader._artifacts["src:ownership-document"] = artifact.model_copy(
        update={"status": "retracted"}
    )
    second = _SVC.get_entity(context_a, "priya")
    assert len(first.assertions) == len(second.assertions)


def test_57_no_revision_only_entity_read_cache(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context_a, reader = org_context
    _SVC.get_entity(context_a, "priya")
    artifact = reader._artifacts["src:ownership-document"]
    reader._artifacts["src:ownership-document"] = artifact.model_copy(
        update={"status": "retracted"}
    )
    context_b = _refresh_org_context(context_a, reader)
    assert _SVC.get_entity(context_b, "priya").assertions == ()


# --- G. Domain/genericity (58-66) ---


def test_58_org_and_buddy_use_same_entity_read_engine(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    org_result = _SVC.get_entity(org_context[0], "priya")
    buddy_ctx, _ = _buddy_context(_buddy_request(campaign="C2"))
    buddy_result = _SVC.get_entity(buddy_ctx, "npc:hero")
    assert type(org_result) is type(buddy_result)


def test_59_no_dnd_imports_in_vnext_modules() -> None:
    for path in VNEXT_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("dungeonmind_dnd")
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("dungeonmind_dnd")


def test_60_no_gm_player_enums_in_entity_reads_module() -> None:
    text = (VNEXT_SRC / "entity_reads.py").read_text(encoding="utf-8")
    assert "PLAYER" not in text
    assert "GM" not in text


def test_61_player_labels_exclude_gm_only_assertion() -> None:
    context, _ = _buddy_context(
        _buddy_request(campaign="C2", audience=["dungeonbuddy.visibility:player"])
    )
    result = _SVC.get_complete_entity(context, "npc:hero")
    assert "asrt:c2-gm-only" not in {item.assertion_id for item in result.assertions}


def test_62_gm_labels_admit_player_and_gm_assertions() -> None:
    context, _ = _buddy_context(
        _buddy_request(
            campaign="C2",
            audience=["dungeonbuddy.visibility:player", "dungeonbuddy.visibility:gm"],
        )
    )
    result = _SVC.get_complete_entity(context, "npc:hero")
    ids = {item.assertion_id for item in result.assertions}
    assert "asrt:c2-player-fact" in ids
    assert "asrt:c2-gm-only" in ids


def test_63_campaign_scope_excludes_other_campaign_touching() -> None:
    context, _ = _buddy_context(
        _buddy_request(campaign="C2", audience=["dungeonbuddy.visibility:player"])
    )
    result = _SVC.get_complete_entity(context, "npc:hero")
    assert "asrt:c3-gm-secret" not in {item.assertion_id for item in result.assertions}


def test_64_wildcard_campaign_admits_valid_touching() -> None:
    context, _ = _buddy_context(
        _buddy_request(
            wildcard=True,
            audience=["dungeonbuddy.visibility:player", "dungeonbuddy.visibility:gm"],
        )
    )
    result = _SVC.get_complete_entity(context, "npc:hero")
    assert "asrt:c3-gm-secret" in {item.assertion_id for item in result.assertions}


def test_65_hidden_touching_does_not_leak_secret_endpoint() -> None:
    test_32_excluded_touching_does_not_disclose_unique_endpoint()


def test_66_focus_and_domain_context_do_not_change_authority() -> None:
    baseline_ctx, _ = _buddy_context(_buddy_request(campaign="C2"))
    baseline = _SVC.get_complete_entity(baseline_ctx, "npc:hero")
    focused_ctx, _ = _buddy_context(
        _buddy_request(
            campaign="C2",
            focus=[FocusRef(kind="dungeonbuddy:session", id="sess-42")],
            domain_context=["dungeonbuddy:session"],
        )
    )
    focused = _SVC.get_complete_entity(focused_ctx, "npc:hero")
    assert {item.assertion_id for item in baseline.assertions} == {
        item.assertion_id for item in focused.assertions
    }


# --- H. Immutability / integrity (67-74) ---


def test_67_result_does_not_mutate_parsed_revision(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    before = context.parsed.semantic_digest
    _SVC.get_entity(context, "priya")
    assert context.parsed.semantic_digest == before


def test_68_result_does_not_mutate_provenance_snapshot(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = _SVC.get_entity(context, "priya")
    if result.source_artifacts:
        with pytest.raises((AttributeError, TypeError)):
            result.source_artifacts[0].status = "retracted"  # type: ignore[misc]


def test_69_caller_mutation_of_result_dto_does_not_poison_followup(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    first = _SVC.get_entity(context, "priya")
    if first.assertions:
        with pytest.raises((AttributeError, TypeError)):
            first.assertions[0].subject_entity_id = "poison"  # type: ignore[misc]
    second = _SVC.get_entity(context, "priya")
    assert first.result_digest == second.result_digest


def test_70_parsed_revision_mutation_guards_remain() -> None:
    context = _high_degree_lab(edge_count=2)
    with pytest.raises(TypeError):
        context.parsed.entities_by_id["ent:hub"] = context.parsed.entities_by_id["ent:hub"]  # type: ignore[index]


def test_71_context_sealed_request_mutation_guard(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    request = context.request
    request.audience_labels.append("organization:leadership")
    again = _SVC.get_entity(context, "priya")
    assert again.found is True


def test_72_unknown_candidate_assertion_fails_closed(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    parsed = context.parsed
    corrupted_subject = dict(parsed.assertions_by_subject)
    corrupted_subject["priya"] = (*corrupted_subject.get("priya", ()), "asrt:missing")
    corrupted = replace(parsed, assertions_by_subject=FrozenDict(corrupted_subject))
    broken = KnowledgeReadContext(
        parsed=corrupted,
        request=context.request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=context.source_reader,
    )
    with pytest.raises(CandidateAdmissionIntegrityError):
        _SVC.get_entity(broken, "priya")


def test_73_result_digest_changes_with_semantic_provenance_state(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, reader = org_context
    first = _SVC.get_entity(context, "priya")
    revision = next(iter(reader._revisions.values()))
    reader._revisions[revision.source_revision_id] = revision.model_copy(
        update={"content_sha256": "f" * 64}
    )
    refreshed = _refresh_org_context(context, reader)
    second = _SVC.get_entity(refreshed, "priya")
    assert first.result_digest != second.result_digest


def test_73b_result_digest_ignores_excluded_candidate_provenance() -> None:
    context, reader = _excluded_incoming_source_lab()
    first = _SVC.get_complete_entity(context, "ent:selected")
    assert {item.assertion_id for item in first.assertions} == {"asrt:visible-subject"}
    hidden = reader._revisions["srcrev:hidden"]
    reader._revisions["srcrev:hidden"] = hidden.model_copy(update={"content_sha256": "f" * 64})
    second = _SVC.get_complete_entity(_rebind_lab_context(context, reader), "ent:selected")
    assert first.result_digest == second.result_digest
    visible = reader._revisions["srcrev:visible"]
    reader._revisions["srcrev:visible"] = visible.model_copy(update={"content_sha256": "a" * 64})
    third = _SVC.get_complete_entity(_rebind_lab_context(context, reader), "ent:selected")
    assert third.result_digest != first.result_digest


def test_73c_result_digest_binds_returned_source_artifact_metadata() -> None:
    context, reader = _excluded_incoming_source_lab()
    first = _SVC.get_complete_entity(context, "ent:selected")
    assert {item.source_artifact_id for item in first.source_artifacts} == {"src:visible"}
    hidden = reader._artifacts["src:hidden"]
    reader._artifacts["src:hidden"] = hidden.model_copy(
        update={"authority": "derived", "source_classification": "test:hidden"}
    )
    second = _SVC.get_complete_entity(_rebind_lab_context(context, reader), "ent:selected")
    assert first.result_digest == second.result_digest
    visible = reader._artifacts["src:visible"]
    reader._artifacts["src:visible"] = visible.model_copy(update={"authority": "derived"})
    third = _SVC.get_complete_entity(_rebind_lab_context(context, reader), "ent:selected")
    assert third.result_digest != first.result_digest
    reader._artifacts["src:visible"] = visible.model_copy(
        update={"source_classification": "test:note"}
    )
    fourth = _SVC.get_complete_entity(_rebind_lab_context(context, reader), "ent:selected")
    assert fourth.result_digest != first.result_digest
    assert fourth.result_digest != third.result_digest


def test_74_result_digest_independent_of_work_counters(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    first = _SVC.get_entity(context, "priya")
    second = _SVC.get_entity(context, "priya")
    assert first.result_digest == second.result_digest
    assert first.work.entity_lookups == second.work.entity_lookups


# --- I. Structural work / performance (75-84) ---


def test_75_get_entity_work_proportional_to_subject_support() -> None:
    small, large = _decoy_heavy_lab(decoy_assertions=400)
    small_result = _SVC.get_entity(small, "ent:selected")
    large_result = _SVC.get_entity(large, "ent:selected")
    assert (
        small_result.work.deduped_candidate_assertions
        == large_result.work.deduped_candidate_assertions
    )
    assert small_result.work.artifact_ids_requested == large_result.work.artifact_ids_requested


def test_76_complete_work_proportional_to_touching_support() -> None:
    context = _high_degree_lab(edge_count=26)
    result = _SVC.get_complete_entity(context, "ent:hub")
    assert result.work.deduped_candidate_assertions == 26
    assert result.work.endpoint_entity_lookups == 26


def test_76b_incoming_heavy_neighbor_does_not_scan_unrelated_subject_assertions() -> None:
    small = _incoming_neighbor_heavy_lab(neighbor_subject_count=80)
    large = _incoming_neighbor_heavy_lab(neighbor_subject_count=2_000)
    small_result = _SVC.get_complete_entity(small, "ent:selected")
    lookup_count = {"n": 0}
    original = ParsedKnowledgeRevision.get_assertion

    def counting(self, assertion_id: str):
        lookup_count["n"] += 1
        return original(self, assertion_id)

    with patch.object(ParsedKnowledgeRevision, "get_assertion", counting):
        large_result = _SVC.get_complete_entity(large, "ent:selected")
    assert large_result.work.incoming_entity_ref_candidates == 1
    assert large_result.work.deduped_candidate_assertions == 1
    assert large_result.work.assertions_evaluated == 1
    assert small_result.work.deduped_candidate_assertions == (
        large_result.work.deduped_candidate_assertions
    )
    assert lookup_count["n"] < 20
    assert lookup_count["n"] < 2_000
    assert {item.assertion_id for item in large_result.assertions} == {
        "asrt:neighbor-points-at-selected"
    }


def test_77_unrelated_assertion_growth_does_not_expand_candidates() -> None:
    test_75_get_entity_work_proportional_to_subject_support()


def test_78_unrelated_source_growth_does_not_expand_requested_sources() -> None:
    test_75_get_entity_work_proportional_to_subject_support()


def test_79_no_full_space_projection_calls() -> None:
    context, _ = _decoy_heavy_lab(decoy_assertions=500)
    result = _SVC.get_entity(context, "ent:selected")
    assert result.work.provenance_snapshot_calls == 1


def test_80_no_full_assertion_scan_witness() -> None:
    context, _ = _decoy_heavy_lab(decoy_assertions=500)
    result = _SVC.get_entity(context, "ent:selected")
    assert result.work.deduped_candidate_assertions == 1
    assert result.work.assertions_evaluated == 1


def test_81_no_full_evidence_scan_witness() -> None:
    context = _many_evidence_lab(evidence_count=33)
    result = _SVC.get_entity(context, "ent:evidence-heavy")
    assert result.work.evidence_ids_returned == 33


def test_82_no_full_source_snapshot_witness(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, _ = org_context
    result = _SVC.get_entity(context, "priya")
    assert result.work.provenance_snapshot_calls == 1


def test_83_entity_reads_10k_benchmark_records_shape() -> None:
    if not ENTITY_BENCH_PATH.is_file():
        subprocess.run(
            [
                sys.executable,
                "benchmarks/vnext_entity_reads_10k.py",
                "--out",
                str(ENTITY_BENCH_PATH),
                "--iterations",
                "20",
            ],
            cwd=REPO_ROOT,
            check=True,
        )
    payload = json.loads(ENTITY_BENCH_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "vnext_entity_reads_10k_v1"
    assert "runs" in payload
    assert payload["structural_gate"]["passes"] is True
    for key in (
        "get_entity_low_degree_10k",
        "get_complete_entity_high_degree_10k",
        "get_complete_entity_incoming_heavy_10k",
    ):
        run = payload["runs"][key]
        assert "p50_ms" in run
        assert "p95_ms" in run
        assert "result_digest" in run


def test_84_benchmark_semantic_digests_present() -> None:
    payload = json.loads(ENTITY_BENCH_PATH.read_text(encoding="utf-8"))
    assert payload["workloads"]["space_10k"]["parsed_semantic_digest"]
    assert payload["workloads"]["space_10k"]["workload_digest"]


# --- J. Regression / scope (85-92) ---


def test_85_v2_candidate_admission_suite_remains_green() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/unit/test_vnext_knowledge_read_context.py"],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0


def test_86_v1_parsed_revision_suite_remains_green() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/unit/test_vnext_parsed_knowledge_revision.py",
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0


def test_87_legacy_compat_suite_remains_green() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/unit/test_vnext_legacy_compatibility.py"],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0


def test_88_frozen_vnext_contract_generator_check_remains_exact() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/generate_vnext_contract_bundle.py", "--check"],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0


def test_89_world_public_services_unchanged() -> None:
    expected = {
        "src/dungeonmind/application/world_graph_retrieval.py": (
            "adb84dbf48c8a05c5b35ad6ef786f7da5cc58153528f015b5eb5c5642c1ba9b6"
        ),
        "src/dungeonmind/application/world_graph_projection.py": (
            "d694be39929cb84dcdeb02ecae2da9447f6a1ca4c96045b40a152c1e3a2d39a4"
        ),
    }
    for rel_path, digest in expected.items():
        assert hashlib.sha256((REPO_ROOT / rel_path).read_bytes()).hexdigest() == digest


def test_90_no_write_or_publication_path_changes() -> None:
    assert not any(VNEXT_SRC.glob("*write*"))
    text = (VNEXT_SRC / "entity_reads.py").read_text(encoding="utf-8")
    assert "get_entity" in text
    assert "get_incoming_entity_ref_assertion_ids" in text
    assert "_incoming_touching_assertion_ids" not in text
    assert "assertions_by_subject.get(source_entity_id" not in text


def test_91_no_storage_migration_changes_in_entity_reads_scope() -> None:
    text = (VNEXT_SRC / "entity_reads.py").read_text(encoding="utf-8")
    assert "migration" not in text.lower()


def test_92_no_v43_search_api_exported() -> None:
    exported = (REPO_ROOT / "src/dungeonmind/application/vnext/__init__.py").read_text(
        encoding="utf-8"
    )
    assert "EvidenceReadService" in exported
    assert "get_evidence" not in exported.lower()
    assert "source_anchor" not in exported.lower()
    assert "anchor_search" not in exported.lower()
    assert "search(" not in exported.lower()
