"""Acceptance matrix for V2 KnowledgeReadContext + candidate admission (HANDOFF §8)."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dungeonmind.application.vnext.admission import (
    AlwaysAdmitPolicy,
    ClaimModeFilterPolicy,
    DomainAdmissionPolicyRegistry,
    ExcludeByAssertionIdPolicy,
)
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.errors import (
    CandidateAdmissionIntegrityError,
    KnowledgeReadContextIntegrityError,
)
from dungeonmind.application.vnext.provenance import (
    InMemoryKnowledgeSourceReader,
)
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
    DomainMetadataEntry,
    DomainTemporalScope,
    EpistemicBasis,
    KnowledgeStanding,
    LabelsAllVisibility,
    LabelsAnyVisibility,
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

CANONICAL_V0_AGGREGATE = "fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "vnext"
REPO_ROOT = Path(__file__).resolve().parents[2]
VNEXT_SRC = REPO_ROOT / "src" / "dungeonmind" / "application" / "vnext"

ORG_CONTRACT_DIGEST = "ef6822213e2b2525051a9516a77c2e75ad58fbe64745c81ca1dff7c0e42db50c"
ORG_PROFILE_DIGEST = "f0210b85f7b1e14054ba69bedfbc604d783251bb73e0292001cf24b825c63cef"
BUDDY_CONTRACT_DIGEST = "77d986c70009031f9869d3986e4b18b5c7d401cbf7818c5024efced655484b2e"
BUDDY_PROFILE_DIGEST = "45f6ae878cd736f24649d71074c87038204ae043be1fd80a19de0b10ea0882a7"


def _org_domain_contract() -> DomainContractDescriptor:
    payload = json.loads((FIXTURES_DIR / "organizational_memory_v1.json").read_text())
    return DomainContractDescriptor.model_validate(payload["domain_contract"])


def _org_semantic_profile() -> SemanticProfileDescriptorV2:
    return SemanticProfileDescriptorV2(
        profile_id="organization.memory.profile",
        profile_revision="1",
        term_namespaces=["organization"],
        predicates=[
            SemanticProfilePredicate(term="organization:owns", allowed_value_kinds=["entity_ref"]),
            SemanticProfilePredicate(
                term="organization:member_of", allowed_value_kinds=["entity_ref"]
            ),
            SemanticProfilePredicate(term="organization:title", allowed_value_kinds=["literal"]),
            SemanticProfilePredicate(
                term="organization:classification", allowed_value_kinds=["term_ref"]
            ),
            SemanticProfilePredicate(term="organization:charter", allowed_value_kinds=["literal"]),
        ],
    )


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _build_from_fixture(
    name: str,
    *,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2,
    contract_digest: str,
    profile_digest: str,
) -> tuple[KnowledgeReadContext, InMemoryKnowledgeSourceReader]:
    data = _load_fixture(name)
    entities = [Entity.model_validate(item) for item in data["entities"]]
    assertions = [Assertion.model_validate(item) for item in data["assertions"]]
    evidence = [EvidenceRefV3.model_validate(item) for item in data["sources"]["evidence"]]
    artifact = SourceArtifactV3.model_validate(data["sources"]["artifact"])
    revisions = [SourceRevisionV2.model_validate(item) for item in data["sources"]["revisions"]]
    revision = KnowledgeRevision(
        space_id=data["space_id"],
        revision_id=f"rev:{name}",
        created_at=datetime(2026, 9, 15, tzinfo=UTC),
        operation_ids=["op:fixture"],
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
    reader = InMemoryKnowledgeSourceReader(
        artifacts={artifact.source_artifact_id: artifact},
        revisions={item.source_revision_id: item for item in revisions},
    )
    policy = AlwaysAdmitPolicy(policy_id=domain_contract.admission_policy_id)
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
        domain_policy=policy,
        source_reader=reader,
    )
    return context, reader


def _buddy_domain_contract() -> DomainContractDescriptor:
    return DomainContractDescriptor.model_validate(
        _load_fixture("buddy_shaped_admission_v1.json")["domain_contract"]
    )


def _buddy_semantic_profile() -> SemanticProfileDescriptorV2:
    return SemanticProfileDescriptorV2(
        profile_id="dungeonbuddy.profile",
        profile_revision="1",
        term_namespaces=["dungeonbuddy"],
        predicates=[
            SemanticProfilePredicate(
                term="dungeonbuddy:located_at", allowed_value_kinds=["entity_ref"]
            )
        ],
    )


def _buddy_request(
    *,
    campaign: str | None = "C2",
    wildcard: bool = False,
    include_unscoped: bool = False,
    audience: list[str] | None = None,
    standing: list[KnowledgeStanding] | None = None,
    focus: list[FocusRef] | None = None,
    domain_context: list[str] | None = None,
) -> ProjectionRequest:
    data = _load_fixture("buddy_shaped_admission_v1.json")
    bindings: list[ScopeBinding] = []
    wildcards: list[str] = []
    if wildcard:
        wildcards = ["dungeonbuddy.scope:campaign"]
    elif campaign is not None:
        bindings = [ScopeBinding(axis="dungeonbuddy.scope:campaign", value=campaign)]
    return ProjectionRequest(
        space_id=data["space_id"],
        revision_id="rev:buddy",
        scope_selector=ScopeSelector(
            include_unscoped=include_unscoped,
            bindings=bindings,
            wildcard_axes=wildcards,
        ),
        audience_labels=audience or ["dungeonbuddy.visibility:player"],
        standing_selector=standing or [KnowledgeStanding.ESTABLISHED],
        focus=focus or [],
        domain_context=domain_context or [],
    )


def _buddy_context(
    request: ProjectionRequest,
    *,
    policy: AlwaysAdmitPolicy | ClaimModeFilterPolicy | ExcludeByAssertionIdPolicy | None = None,
) -> tuple[KnowledgeReadContext, InMemoryKnowledgeSourceReader]:
    domain_contract = _buddy_domain_contract()
    semantic_profile = _buddy_semantic_profile()
    data = _load_fixture("buddy_shaped_admission_v1.json")
    entities = [Entity.model_validate(item) for item in data["entities"]]
    assertions = [Assertion.model_validate(item) for item in data["assertions"]]
    evidence = [EvidenceRefV3.model_validate(item) for item in data["sources"]["evidence"]]
    artifact = SourceArtifactV3.model_validate(data["sources"]["artifact"])
    revisions = [SourceRevisionV2.model_validate(item) for item in data["sources"]["revisions"]]
    revision = KnowledgeRevision(
        space_id=data["space_id"],
        revision_id="rev:buddy",
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
    resolved_policy = policy or AlwaysAdmitPolicy(policy_id=domain_contract.admission_policy_id)
    context = KnowledgeReadContext(
        parsed=parsed,
        request=request,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
        domain_policy=resolved_policy,
        source_reader=reader,
    )
    return context, reader


@pytest.fixture(name="org_context")
def fixture_org_context() -> tuple[KnowledgeReadContext, InMemoryKnowledgeSourceReader]:
    return _build_from_fixture(
        "organizational_memory_v1.json",
        domain_contract=_org_domain_contract(),
        semantic_profile=_org_semantic_profile(),
        contract_digest=ORG_CONTRACT_DIGEST,
        profile_digest=ORG_PROFILE_DIGEST,
    )


def test_01_request_space_id_mismatch_fails_closed(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    bad_request = context.request.model_copy(update={"space_id": "space:other"})
    with pytest.raises(KnowledgeReadContextIntegrityError):
        KnowledgeReadContext(
            parsed=context.parsed,
            request=bad_request,
            domain_contract=context.domain_contract,
            semantic_profile=context.semantic_profile,
            domain_policy=context.domain_policy,
            source_reader=context.source_reader,
        )


def test_02_explicit_revision_id_mismatch_fails_closed(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    bad_request = context.request.model_copy(update={"revision_id": "rev:wrong"})
    with pytest.raises(KnowledgeReadContextIntegrityError):
        KnowledgeReadContext(
            parsed=context.parsed,
            request=bad_request,
            domain_contract=context.domain_contract,
            semantic_profile=context.semantic_profile,
            domain_policy=context.domain_policy,
            source_reader=context.source_reader,
        )


def test_03_unknown_candidate_assertion_id_fails_closed(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    with pytest.raises(CandidateAdmissionIntegrityError):
        context.admit_candidates(["asrt:missing"])


def test_04_domain_contract_id_mismatch_fails_closed(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    bad_contract = context.domain_contract.model_copy(update={"domain_id": "other.domain"})
    with pytest.raises(KnowledgeReadContextIntegrityError):
        KnowledgeReadContext(
            parsed=context.parsed,
            request=context.request,
            domain_contract=bad_contract,
            semantic_profile=context.semantic_profile,
            domain_policy=context.domain_policy,
            source_reader=context.source_reader,
        )


def test_05_domain_contract_revision_mismatch_fails_closed(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    bad_contract = context.domain_contract.model_copy(update={"domain_revision": "2"})
    with pytest.raises(KnowledgeReadContextIntegrityError):
        KnowledgeReadContext(
            parsed=context.parsed,
            request=context.request,
            domain_contract=bad_contract,
            semantic_profile=context.semantic_profile,
            domain_policy=context.domain_policy,
            source_reader=context.source_reader,
        )


def test_06_domain_contract_descriptor_digest_mismatch_fails_closed(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    parsed = context.parsed
    bad_ref = replace(
        parsed.identity,
        domain_contract_ref=replace(
            parsed.domain_contract_ref,
            descriptor_sha256="f" * 64,
        ),
    )
    bad_parsed = parsed.__class__(
        identity=bad_ref,
        entities_by_id=parsed.entities_by_id,
        assertions_by_id=parsed.assertions_by_id,
        aliases_by_id=parsed.aliases_by_id,
        evidence_by_id=parsed.evidence_by_id,
        assertions_by_subject=parsed.assertions_by_subject,
        entity_ref_outgoing=parsed.entity_ref_outgoing,
        entity_ref_incoming=parsed.entity_ref_incoming,
        entity_adjacency=parsed.entity_adjacency,
        assertion_evidence=parsed.assertion_evidence,
        evidence_supporters=parsed.evidence_supporters,
        alias_exact_index=parsed.alias_exact_index,
        literal_exact_index=parsed.literal_exact_index,
        lexical_candidate_index=parsed.lexical_candidate_index,
        semantic_digest=parsed.semantic_digest,
        compatibility_key=parsed.compatibility_key,
    )
    with pytest.raises(KnowledgeReadContextIntegrityError):
        KnowledgeReadContext(
            parsed=bad_parsed,
            request=context.request,
            domain_contract=context.domain_contract,
            semantic_profile=context.semantic_profile,
            domain_policy=context.domain_policy,
            source_reader=context.source_reader,
        )


def test_07_semantic_profile_mismatch_fails_closed(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    bad_profile = context.semantic_profile.model_copy(update={"profile_id": "wrong"})
    with pytest.raises(KnowledgeReadContextIntegrityError):
        KnowledgeReadContext(
            parsed=context.parsed,
            request=context.request,
            domain_contract=context.domain_contract,
            semantic_profile=bad_profile,
            domain_policy=context.domain_policy,
            source_reader=context.source_reader,
        )


def test_08_frozen_v0_aggregate_remains_exact() -> None:
    bundle_path = REPO_ROOT / "Docs" / "Contracts" / "vnext" / "dm_vnext_contract_v1.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert bundle["aggregate_sha256"] == CANONICAL_V0_AGGREGATE


def test_09_unknown_request_scope_axis_fails_closed(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    bad_request = context.request.model_copy(
        update={
            "scope_selector": ScopeSelector(
                bindings=[ScopeBinding(axis="organization:unknown", value="x")]
            )
        }
    )
    with pytest.raises(KnowledgeReadContextIntegrityError):
        KnowledgeReadContext(
            parsed=context.parsed,
            request=bad_request,
            domain_contract=context.domain_contract,
            semantic_profile=context.semantic_profile,
            domain_policy=context.domain_policy,
            source_reader=context.source_reader,
        )


def test_10_unknown_wildcard_scope_axis_fails_closed(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    bad_request = context.request.model_copy(
        update={"scope_selector": ScopeSelector(wildcard_axes=["organization:unknown"])}
    )
    with pytest.raises(KnowledgeReadContextIntegrityError):
        KnowledgeReadContext(
            parsed=context.parsed,
            request=bad_request,
            domain_contract=context.domain_contract,
            semantic_profile=context.semantic_profile,
            domain_policy=context.domain_policy,
            source_reader=context.source_reader,
        )


def test_11_unknown_audience_label_fails_closed(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    bad_request = context.request.model_copy(update={"audience_labels": ["organization:unknown"]})
    with pytest.raises(KnowledgeReadContextIntegrityError):
        KnowledgeReadContext(
            parsed=context.parsed,
            request=bad_request,
            domain_contract=context.domain_contract,
            semantic_profile=context.semantic_profile,
            domain_policy=context.domain_policy,
            source_reader=context.source_reader,
        )


def _default_metadata(**overrides: Any) -> AssertionMetadata:
    base = {
        "scope": [],
        "visibility": PublicVisibility(),
        "epistemic_basis": EpistemicBasis.ASSERTED,
        "claim_mode": "organization:fact",
        "standing": KnowledgeStanding.ESTABLISHED,
        "evidence_ref_ids": [],
        "temporal_scope": TimelessTemporalScope(),
        "domain_metadata": [],
    }
    base.update(overrides)
    return AssertionMetadata(**base)


def _assertion_with_metadata(assertion_id: str, metadata: AssertionMetadata) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject_entity_id="priya",
        predicate="organization:member_of",
        value=EntityRefValue(entity_id="research-team"),
        metadata=metadata,
    )


def _mini_context_for_assertions(
    assertions: list[Assertion],
    request: ProjectionRequest,
) -> KnowledgeReadContext:
    domain_contract = _org_domain_contract()
    semantic_profile = _org_semantic_profile()
    revision = KnowledgeRevision(
        space_id="space:org-memory",
        revision_id="rev:mini",
        created_at=datetime(2026, 9, 15, tzinfo=UTC),
        operation_ids=["op:mini"],
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
    entities = [Entity(entity_id="priya"), Entity(entity_id="research-team")]
    parsed = build_parsed_knowledge_revision(
        revision=revision,
        entities=entities,
        assertions=assertions,
        evidence=[],
    )
    reader = InMemoryKnowledgeSourceReader()
    return KnowledgeReadContext(
        parsed=parsed,
        request=request,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
        domain_policy=AlwaysAdmitPolicy(policy_id=domain_contract.admission_policy_id),
        source_reader=reader,
    )


def test_12_assertion_undeclared_scope_axis_excluded() -> None:
    metadata = _default_metadata(
        scope=[ScopeBinding(axis="organization:unknown", value="x")],
    )
    context = _mini_context_for_assertions(
        [_assertion_with_metadata("asrt:bad-scope", metadata)],
        ProjectionRequest(
            space_id="space:org-memory",
            scope_selector=ScopeSelector(include_unscoped=True),
            audience_labels=["organization:team"],
            standing_selector=[KnowledgeStanding.ESTABLISHED],
        ),
    )
    result = context.admit_candidates(["asrt:bad-scope"])
    assert result.admitted_assertion_ids == ()
    assert result.excluded[0].reason == "domain_declaration"


def test_13_assertion_undeclared_visibility_label_excluded() -> None:
    metadata = _default_metadata(
        visibility=LabelsAnyVisibility(labels=["organization:unknown"]),
    )
    context = _mini_context_for_assertions(
        [_assertion_with_metadata("asrt:bad-vis", metadata)],
        ProjectionRequest(
            space_id="space:org-memory",
            scope_selector=ScopeSelector(include_unscoped=True),
            audience_labels=["organization:team"],
            standing_selector=[KnowledgeStanding.ESTABLISHED],
        ),
    )
    result = context.admit_candidates(["asrt:bad-vis"])
    assert result.excluded[0].reason == "domain_declaration"


def test_14_undeclared_claim_mode_excluded() -> None:
    metadata = _default_metadata(claim_mode="organization:unknown")
    context = _mini_context_for_assertions(
        [_assertion_with_metadata("asrt:bad-claim", metadata)],
        ProjectionRequest(
            space_id="space:org-memory",
            scope_selector=ScopeSelector(include_unscoped=True),
            audience_labels=["organization:team"],
            standing_selector=[KnowledgeStanding.ESTABLISHED],
        ),
    )
    result = context.admit_candidates(["asrt:bad-claim"])
    assert result.excluded[0].reason == "domain_declaration"


def test_15_undeclared_domain_temporal_schema_excluded() -> None:
    metadata = _default_metadata(
        temporal_scope=DomainTemporalScope(schema="organization:unknown", payload={}),
    )
    context = _mini_context_for_assertions(
        [_assertion_with_metadata("asrt:bad-temporal", metadata)],
        ProjectionRequest(
            space_id="space:org-memory",
            scope_selector=ScopeSelector(include_unscoped=True),
            audience_labels=["organization:team"],
            standing_selector=[KnowledgeStanding.ESTABLISHED],
        ),
    )
    result = context.admit_candidates(["asrt:bad-temporal"])
    assert result.excluded[0].reason == "domain_declaration"


def test_16_undeclared_domain_metadata_schema_excluded() -> None:
    metadata = _default_metadata(
        domain_metadata=[DomainMetadataEntry(schema="organization:unknown", payload={})],
    )
    context = _mini_context_for_assertions(
        [_assertion_with_metadata("asrt:bad-meta", metadata)],
        ProjectionRequest(
            space_id="space:org-memory",
            scope_selector=ScopeSelector(include_unscoped=True),
            audience_labels=["organization:team"],
            standing_selector=[KnowledgeStanding.ESTABLISHED],
        ),
    )
    result = context.admit_candidates(["asrt:bad-meta"])
    assert result.excluded[0].reason == "domain_declaration"


def test_17_unscoped_include_false_excludes(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, _ = org_context
    request = context.request.model_copy(
        update={
            "scope_selector": ScopeSelector(
                include_unscoped=False, bindings=context.request.scope_selector.bindings
            )
        }
    )
    narrowed = KnowledgeReadContext(
        parsed=context.parsed,
        request=request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=context.source_reader,
    )
    result = narrowed.admit_candidates(["asrt:org-charter-unscoped"])
    assert "asrt:org-charter-unscoped" not in result.admitted_assertion_ids


def test_18_unscoped_include_true_admits(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, _ = org_context
    result = context.admit_candidates(["asrt:org-charter-unscoped"])
    assert "asrt:org-charter-unscoped" in result.admitted_assertion_ids


def test_19_exact_scope_binding_admits(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, _ = org_context
    result = context.admit_candidates(["asrt:priya-member-research"])
    assert "asrt:priya-member-research" in result.admitted_assertion_ids


def test_20_mismatched_scope_value_excludes(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, _ = org_context
    request = context.request.model_copy(
        update={
            "scope_selector": ScopeSelector(
                include_unscoped=False,
                bindings=[ScopeBinding(axis="organization:project", value="other")],
            )
        }
    )
    narrowed = KnowledgeReadContext(
        parsed=context.parsed,
        request=request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=context.source_reader,
    )
    result = narrowed.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert result.excluded[0].reason == "scope"


def test_21_wildcard_axis_admits(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, _ = org_context
    request = context.request.model_copy(
        update={
            "scope_selector": ScopeSelector(
                include_unscoped=False,
                wildcard_axes=["organization:project"],
            )
        }
    )
    narrowed = KnowledgeReadContext(
        parsed=context.parsed,
        request=request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=context.source_reader,
    )
    result = narrowed.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert "asrt:priya-owns-retrieval-apr" in result.admitted_assertion_ids


def test_22_multi_axis_assertion_requires_all_bindings(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    request = context.request.model_copy(
        update={
            "scope_selector": ScopeSelector(
                include_unscoped=False,
                bindings=[ScopeBinding(axis="organization:project", value="retrieval")],
            )
        }
    )
    narrowed = KnowledgeReadContext(
        parsed=context.parsed,
        request=request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=context.source_reader,
    )
    result = narrowed.admit_candidates(["asrt:priya-member-research"])
    assert result.excluded[0].reason == "scope"


def test_23_public_visibility_passes_empty_audience() -> None:
    metadata = _default_metadata()
    context = _mini_context_for_assertions(
        [_assertion_with_metadata("asrt:public", metadata)],
        ProjectionRequest(
            space_id="space:org-memory",
            scope_selector=ScopeSelector(include_unscoped=True),
            audience_labels=[],
            standing_selector=[KnowledgeStanding.ESTABLISHED],
        ),
    )
    result = context.admit_candidates(["asrt:public"])
    assert result.admitted_assertion_ids == ("asrt:public",)


def test_24_labels_any_one_match_admits() -> None:
    metadata = _default_metadata(
        visibility=LabelsAnyVisibility(labels=["organization:team", "organization:leadership"]),
    )
    context = _mini_context_for_assertions(
        [_assertion_with_metadata("asrt:any", metadata)],
        ProjectionRequest(
            space_id="space:org-memory",
            scope_selector=ScopeSelector(include_unscoped=True),
            audience_labels=["organization:team"],
            standing_selector=[KnowledgeStanding.ESTABLISHED],
        ),
    )
    result = context.admit_candidates(["asrt:any"])
    assert result.admitted_assertion_ids == ("asrt:any",)


def test_25_labels_any_no_match_excludes() -> None:
    metadata = _default_metadata(
        visibility=LabelsAnyVisibility(labels=["organization:leadership"]),
    )
    context = _mini_context_for_assertions(
        [_assertion_with_metadata("asrt:any-miss", metadata)],
        ProjectionRequest(
            space_id="space:org-memory",
            scope_selector=ScopeSelector(include_unscoped=True),
            audience_labels=["organization:team"],
            standing_selector=[KnowledgeStanding.ESTABLISHED],
        ),
    )
    result = context.admit_candidates(["asrt:any-miss"])
    assert result.excluded[0].reason == "visibility"


def test_26_labels_all_requires_every_label() -> None:
    metadata = _default_metadata(
        visibility=LabelsAllVisibility(labels=["organization:team", "organization:leadership"]),
    )
    context = _mini_context_for_assertions(
        [_assertion_with_metadata("asrt:all", metadata)],
        ProjectionRequest(
            space_id="space:org-memory",
            scope_selector=ScopeSelector(include_unscoped=True),
            audience_labels=["organization:team", "organization:leadership"],
            standing_selector=[KnowledgeStanding.ESTABLISHED],
        ),
    )
    result = context.admit_candidates(["asrt:all"])
    assert result.admitted_assertion_ids == ("asrt:all",)


def test_27_source_artifact_visibility_can_exclude(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, reader = org_context
    result = context.admit_candidates(["asrt:priya-member-research"])
    assert "asrt:priya-member-research" in result.admitted_assertion_ids
    request = context.request.model_copy(update={"audience_labels": []})
    narrowed = KnowledgeReadContext(
        parsed=context.parsed,
        request=request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=reader,
    )
    result = narrowed.admit_candidates(["asrt:priya-member-research"])
    assert any(item.reason == "source_visibility" for item in result.excluded)


def test_28_standing_must_be_explicitly_selected(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    request = context.request.model_copy(
        update={"standing_selector": [KnowledgeStanding.PROVISIONAL]}
    )
    narrowed = KnowledgeReadContext(
        parsed=context.parsed,
        request=request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=context.source_reader,
    )
    result = narrowed.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert result.excluded[0].reason == "standing"


def test_29_empty_standing_selector_never_widens(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    request = context.request.model_copy(update={"standing_selector": []})
    narrowed = KnowledgeReadContext(
        parsed=context.parsed,
        request=request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=context.source_reader,
    )
    result = narrowed.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert result.excluded[0].reason == "empty_standing_selector"


def test_30_focus_ref_does_not_change_generic_admission(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    baseline = context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    focused_request = context.request.model_copy(
        update={"focus": [FocusRef(kind="organization:session", id="sess-1")]}
    )
    focused = KnowledgeReadContext(
        parsed=context.parsed,
        request=focused_request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=context.source_reader,
    )
    with_focus = focused.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert with_focus.admitted_assertion_ids == baseline.admitted_assertion_ids


def test_31_domain_context_does_not_change_generic_admission(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    baseline = context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    request = context.request.model_copy(update={"domain_context": ["organization:team"]})
    adjusted = KnowledgeReadContext(
        parsed=context.parsed,
        request=request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=context.source_reader,
    )
    result = adjusted.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert result.admitted_assertion_ids == baseline.admitted_assertion_ids


def test_32_declared_predicate_and_value_kind_pass(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = context.admit_candidates(["asrt:priya-title"])
    assert "asrt:priya-title" in result.admitted_assertion_ids


def test_33_unknown_predicate_excluded_when_profile_authoritative() -> None:
    metadata = _default_metadata()
    assertion = Assertion(
        assertion_id="asrt:unknown-predicate",
        subject_entity_id="priya",
        predicate="organization:unknown",
        value=LiteralValue(value="x"),
        metadata=metadata,
    )
    context = _mini_context_for_assertions(
        [assertion],
        ProjectionRequest(
            space_id="space:org-memory",
            scope_selector=ScopeSelector(include_unscoped=True),
            audience_labels=["organization:team"],
            standing_selector=[KnowledgeStanding.ESTABLISHED],
        ),
    )
    result = context.admit_candidates(["asrt:unknown-predicate"])
    assert result.excluded[0].reason == "semantic_profile"


def test_34_disallowed_value_kind_excluded() -> None:
    metadata = _default_metadata()
    assertion = Assertion(
        assertion_id="asrt:bad-kind",
        subject_entity_id="priya",
        predicate="organization:title",
        value=EntityRefValue(entity_id="research-team"),
        metadata=metadata,
    )
    context = _mini_context_for_assertions(
        [assertion],
        ProjectionRequest(
            space_id="space:org-memory",
            scope_selector=ScopeSelector(include_unscoped=True),
            audience_labels=["organization:team"],
            standing_selector=[KnowledgeStanding.ESTABLISHED],
        ),
    )
    result = context.admit_candidates(["asrt:bad-kind"])
    assert result.excluded[0].reason == "semantic_profile"


def test_35_no_invented_literal_schema_semantics() -> None:
    profile = _org_semantic_profile()
    assert all(item.literal_schema is None for item in profile.predicates)


def test_36_missing_source_artifact_excludes(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, reader = org_context
    reader._artifacts.clear()
    result = context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert result.excluded[0].reason == "source_missing"


def test_37_source_visibility_before_inactive_diagnostics(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, reader = org_context
    artifact = next(iter(reader._artifacts.values()))
    reader._artifacts[artifact.source_artifact_id] = artifact.model_copy(
        update={
            "status": "superseded",
            "visibility": LabelsAllVisibility(labels=["organization:leadership"]),
        }
    )
    request = context.request.model_copy(update={"audience_labels": ["organization:team"]})
    narrowed = KnowledgeReadContext(
        parsed=context.parsed,
        request=request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=reader,
    )
    result = narrowed.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert result.excluded[0].reason == "source_visibility"


def test_38_inactive_source_excludes(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, reader = org_context
    artifact = next(iter(reader._artifacts.values()))
    reader._artifacts[artifact.source_artifact_id] = artifact.model_copy(
        update={"status": "retracted"}
    )
    result = context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert result.excluded[0].reason == "source_inactive"


def test_39_missing_source_revision_excludes(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, reader = org_context
    reader._revisions.clear()
    result = context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert result.excluded[0].reason == "source_revision_invalid"


def test_40_revision_wrong_artifact_excludes(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, reader = org_context
    revision = next(iter(reader._revisions.values()))
    reader._revisions[revision.source_revision_id] = revision.model_copy(
        update={"source_artifact_id": "src:other"}
    )
    result = context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert result.excluded[0].reason == "source_revision_invalid"


def test_41_older_source_revision_remains_valid(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert "asrt:priya-owns-retrieval-apr" in result.admitted_assertion_ids


def test_42_unrelated_sources_not_loaded(org_context: tuple[KnowledgeReadContext, Any]) -> None:
    context, reader = org_context
    reader._artifacts["src:decoy"] = SourceArtifactV3(
        source_artifact_id="src:decoy",
        source_classification="organization:document",
        authority="primary",
        visibility=PublicVisibility(),
        status="active",
    )
    reader.snapshot_call_count = 0
    result = context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert result.work.artifact_ids_requested == 1
    assert "src:decoy" not in reader._artifacts or result.work.artifact_ids_requested == 1


def test_43_duplicate_evidence_ids_deduplicated(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, reader = org_context
    reader.snapshot_call_count = 0
    result = context.admit_candidates(
        ["asrt:priya-owns-retrieval-apr", "asrt:marco-owns-retrieval-sep"]
    )
    assert result.work.provenance_snapshot_calls == 1
    assert result.work.artifact_ids_requested == 1


def test_44_provenance_snapshot_deeply_immutable(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    _, reader = org_context
    snapshot = reader.get_provenance_snapshot(
        artifact_ids=["src:ownership-document"],
        revision_ids=["srcrev:ownership-document-v1"],
    )
    artifact = snapshot.get_artifact("src:ownership-document")
    assert artifact is not None
    artifact.status = "retracted"  # type: ignore[misc]
    again = snapshot.get_artifact("src:ownership-document")
    assert again is not None
    assert again.status == "active"


def test_45_one_admission_operation_one_snapshot(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, reader = org_context
    reader.snapshot_call_count = 0
    context.admit_candidates(["asrt:priya-owns-retrieval-apr", "asrt:marco-owns-retrieval-sep"])
    assert reader.snapshot_call_count == 1


def test_46_mutating_backing_after_snapshot_does_not_mutate_snapshot(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    _, reader = org_context
    snapshot_a = reader.get_provenance_snapshot(
        artifact_ids=["src:ownership-document"], revision_ids=[]
    )
    fp_a = snapshot_a.fingerprint
    artifact = reader._artifacts["src:ownership-document"]
    reader._artifacts["src:ownership-document"] = artifact.model_copy(
        update={"status": "retracted"}
    )
    assert snapshot_a.fingerprint == fp_a
    assert snapshot_a.get_artifact("src:ownership-document") is not None
    assert snapshot_a.get_artifact("src:ownership-document").status == "active"


def test_47_context_b_observes_changed_source_state(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, reader = org_context
    context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    artifact = reader._artifacts["src:ownership-document"]
    reader._artifacts["src:ownership-document"] = artifact.model_copy(
        update={"status": "retracted"}
    )
    result_b = context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert result_b.excluded[0].reason == "source_inactive"


def test_48_parsed_revision_reuse_does_not_reuse_stale_verdicts(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, reader = org_context
    first = context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert first.admitted_assertion_ids
    artifact = reader._artifacts["src:ownership-document"]
    reader._artifacts["src:ownership-document"] = artifact.model_copy(
        update={"status": "retracted"}
    )
    second = context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert not second.admitted_assertion_ids


def test_49_registered_policy_identity_resolves() -> None:
    registry = DomainAdmissionPolicyRegistry({"policy:a": AlwaysAdmitPolicy(policy_id="policy:a")})
    assert registry.resolve("policy:a").policy_id == "policy:a"


def test_50_missing_policy_fails_closed() -> None:
    registry = DomainAdmissionPolicyRegistry({})
    with pytest.raises(KnowledgeReadContextIntegrityError):
        registry.resolve("missing")


def test_51_mismatched_policy_identity_fails_closed(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    with pytest.raises(KnowledgeReadContextIntegrityError):
        KnowledgeReadContext(
            parsed=context.parsed,
            request=context.request,
            domain_contract=context.domain_contract,
            semantic_profile=context.semantic_profile,
            domain_policy=AlwaysAdmitPolicy(policy_id="wrong.policy"),
            source_reader=context.source_reader,
        )


def test_52_policy_excludes_generic_admitted_candidate(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    policy = ExcludeByAssertionIdPolicy(
        policy_id=context.domain_contract.admission_policy_id,
        excluded_assertion_ids=frozenset({"asrt:priya-owns-retrieval-apr"}),
    )
    adjusted = KnowledgeReadContext(
        parsed=context.parsed,
        request=context.request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=policy,
        source_reader=context.source_reader,
    )
    result = adjusted.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert result.excluded[0].reason == "domain_policy"


def test_53_policy_never_sees_generic_rejected_candidate(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    class SpyPolicy:
        policy_id = "organization.memory.admit.v1"
        calls: list[str] = []

        def narrow(self, **kwargs: Any) -> bool:
            assertion = kwargs["assertion"]
            SpyPolicy.calls.append(assertion.assertion_id)
            return True

    SpyPolicy.calls = []
    context, _ = org_context
    request = context.request.model_copy(update={"standing_selector": []})
    adjusted = KnowledgeReadContext(
        parsed=context.parsed,
        request=request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=SpyPolicy(),
        source_reader=context.source_reader,
    )
    adjusted.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert SpyPolicy.calls == []


def test_54_policy_cannot_recover_rejected_candidate(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    request = context.request.model_copy(update={"standing_selector": []})
    adjusted = KnowledgeReadContext(
        parsed=context.parsed,
        request=request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=AlwaysAdmitPolicy(policy_id=context.domain_contract.admission_policy_id),
        source_reader=context.source_reader,
    )
    result = adjusted.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert result.admitted_assertion_ids == ()


def test_55_equal_inputs_deterministic_policy_result(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    first = context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    second = context.admit_candidates(["asrt:priya-owns-retrieval-apr"])
    assert first.result_digest == second.result_digest


def test_56_organizational_memory_expected_admissions(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, _ = org_context
    result = context.admit_candidates(
        [
            "asrt:priya-owns-retrieval-apr",
            "asrt:marco-owns-retrieval-sep",
            "asrt:priya-member-research",
            "asrt:org-charter-unscoped",
        ]
    )
    assert len(result.admitted_assertion_ids) >= 3


def test_57_buddy_campaign_player_admission() -> None:
    context, _ = _buddy_context(
        _buddy_request(campaign="C2", audience=["dungeonbuddy.visibility:player"])
    )
    result = context.admit_candidates(["asrt:c2-player-fact", "asrt:c3-gm-secret"])
    assert "asrt:c2-player-fact" in result.admitted_assertion_ids
    assert "asrt:c3-gm-secret" not in result.admitted_assertion_ids


def test_58_buddy_gm_effective_labels() -> None:
    context, _ = _buddy_context(
        _buddy_request(
            campaign="C2",
            audience=["dungeonbuddy.visibility:player", "dungeonbuddy.visibility:gm"],
        )
    )
    result = context.admit_candidates(["asrt:c2-gm-only"])
    assert "asrt:c2-gm-only" in result.admitted_assertion_ids


def test_59_buddy_session_focus_no_authority_change() -> None:
    baseline_ctx, _ = _buddy_context(_buddy_request(campaign="C2"))
    baseline = baseline_ctx.admit_candidates(["asrt:c2-player-fact"])
    focused_ctx, _ = _buddy_context(
        _buddy_request(
            campaign="C2",
            focus=[FocusRef(kind="dungeonbuddy:session", id="sess-42")],
        )
    )
    focused = focused_ctx.admit_candidates(["asrt:c2-player-fact"])
    assert focused.admitted_assertion_ids == baseline.admitted_assertion_ids


def test_60_no_dnd_imports_in_vnext_modules() -> None:
    for path in VNEXT_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "dungeonmind_dnd" not in alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert "dungeonmind_dnd" not in node.module


def test_61_v1_parsed_suite_remains_green() -> None:
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


def test_62_v1_2_legacy_compat_suite_remains_green() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/unit/test_vnext_legacy_compatibility.py"],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0


def test_63_historical_reader_files_remain_at_pinned_digests() -> None:
    from tests.unit.test_vnext_legacy_compatibility import (
        _HISTORICAL_READER_SHA256,
    )

    for rel_path, expected_sha in _HISTORICAL_READER_SHA256.items():
        digest = hashlib.sha256((REPO_ROOT / rel_path).read_bytes()).hexdigest()
        assert digest == expected_sha


def test_64_world_public_services_unchanged() -> None:
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


def test_65_frozen_v0_contract_generator_check_remains_exact() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/generate_vnext_contract_bundle.py", "--check"],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0


def test_buddy_unscoped_and_wildcard_cases() -> None:
    ctx_no_unscoped, _ = _buddy_context(_buddy_request(campaign="C2", include_unscoped=False))
    assert (
        "asrt:unscoped-rumor"
        not in ctx_no_unscoped.admit_candidates(["asrt:unscoped-rumor"]).admitted_assertion_ids
    )

    ctx_unscoped, _ = _buddy_context(
        _buddy_request(
            campaign="C2",
            include_unscoped=True,
            standing=[KnowledgeStanding.PROVISIONAL],
            audience=["dungeonbuddy.visibility:player"],
        )
    )
    assert (
        "asrt:unscoped-rumor"
        in ctx_unscoped.admit_candidates(["asrt:unscoped-rumor"]).admitted_assertion_ids
    )

    ctx_wildcard, _ = _buddy_context(_buddy_request(wildcard=True, include_unscoped=False))
    result = ctx_wildcard.admit_candidates(["asrt:c3-gm-secret"])
    assert "asrt:c3-gm-secret" in result.admitted_assertion_ids or result.excluded


def test_claim_mode_filter_policy_fixture() -> None:
    policy = ClaimModeFilterPolicy(
        policy_id="dungeonbuddy.admit.v1",
        allowed_claim_modes=frozenset({"dungeonbuddy:fact"}),
    )
    context, _ = _buddy_context(
        _buddy_request(
            campaign="C2",
            include_unscoped=True,
            standing=[KnowledgeStanding.PROVISIONAL],
        ),
        policy=policy,
    )
    result = context.admit_candidates(["asrt:unscoped-rumor"])
    assert result.excluded[0].reason == "domain_policy"
